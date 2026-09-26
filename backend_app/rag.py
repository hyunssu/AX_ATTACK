from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from sqlalchemy import text as sql_text

from config import MANUAL_MATCH_THRESHOLD
from db import engine
from db_tables import MANUAL_CHILD_CHUNKS, MANUAL_PARENT_CHUNKS, MANUALS, MANUAL_VERSIONS
from llm_clients import call_llm, embeddings, embedding_to_sql, llm
from chat.prompts import format_prompt, prompt_label, schema_description
from chat import word_dictionary

class ClarifyOrAnswer(BaseModel):
    type: Literal["clarify", "answer"] = Field(
        description=schema_description("rag.answer_type")
    )
    text: str = Field(description=schema_description("rag.answer_text"))
    options: list[str] = Field(
        default_factory=list,
        description=schema_description("rag.answer_options"),
    )


structured_llm = llm.with_structured_output(ClarifyOrAnswer)


class QueryCheck(BaseModel):
    proceed: bool = Field(
        description=schema_description("rag.query_proceed")
    )
    clarify_text: str = Field(description=schema_description("rag.clarify_text"))
    clarify_options: list[str] = Field(
        default_factory=list,
        description=schema_description("rag.clarify_options"),
    )


query_check_llm = llm.with_structured_output(QueryCheck)


def _format_history_text(history: list[dict] | None, language: str = "ko") -> str:
    return "\n".join(
        f"{turn.get('role')}: {turn.get('text', '')}" for turn in (history or [])
    ) or prompt_label("empty_value", language=language)


def _check_query(
    question: str,
    history: list[dict] | None,
    language: str = "ko",
    conversation_context: str = "",
) -> QueryCheck:
    prompt = format_prompt(
        "query_check",
        language=language,
        conversation_context=conversation_context or prompt_label("empty_value", language=language),
        history_text=_format_history_text(history, language),
        question=question,
    )
    return call_llm(query_check_llm, prompt, label="query_check")


class QueryRewrite(BaseModel):
    standalone_question: str = Field(
        description=schema_description("rag.standalone_question")
    )


query_rewrite_llm = llm.with_structured_output(QueryRewrite)


class QueryPreparation(BaseModel):
    refined_question: str = Field(
        description=schema_description("rag.refined_question")
    )
    unknown_terms: list[str] = Field(
        default_factory=list,
        description=schema_description("rag.unknown_terms"),
    )


query_prepare_llm = llm.with_structured_output(QueryPreparation)


def _rewrite_query(
    question: str,
    refined_question: str,
    dictionary_context: str,
    history: list[dict] | None,
    language: str = "ko",
    conversation_context: str = "",
) -> str:
    prompt = format_prompt(
        "query_rewrite",
        language=language,
        dictionary_context=dictionary_context,
        conversation_context=conversation_context or prompt_label("empty_value", language=language),
        history_text=_format_history_text(history, language),
        question=question,
        refined_question=refined_question,
    )
    rewrite: QueryRewrite = call_llm(query_rewrite_llm, prompt, label="query_rewrite")
    return rewrite.standalone_question or refined_question or question


def prepare_knowledge_query(
    question: str,
    history: list[dict] | None,
    language: str = "ko",
    conversation_context: str = "",
    ignored_unknown_terms: list[str] | None = None,
    allow_term_registration: bool = True,
) -> dict:
    """질문 정제 → 단어사전 → 사전 기반 최종 검색질문을 공통 생성한다."""
    preparation_error = None
    try:
        prepared: QueryPreparation = call_llm(query_prepare_llm, format_prompt(
            "query_prepare",
            language=language,
            conversation_context=(
                conversation_context or prompt_label("empty_value", language=language)
            ),
            history_text=_format_history_text(history, language),
            question=question,
        ), label="query_prepare")
        refined_question = prepared.refined_question.strip() or question
        unknown_terms = list(dict.fromkeys(
            term.strip()
            for term in prepared.unknown_terms
            if term.strip() and word_dictionary.should_lookup_term(term)
        ))[:word_dictionary.MAX_UNKNOWN_TERMS]
    except Exception as exc:
        # 1차 정제 실패 시에도 단어사전 호출 계약과 지식검색 자체는 유지한다.
        preparation_error = str(exc)
        refined_question = question
        unknown_terms = []

    # 검색어 유무와 관계없이 모든 지식검색 턴이 반드시 이 경계를 통과한다.
    dictionary_entries = word_dictionary.lookup_terms(unknown_terms)
    ignored_term_keys = {
        str(term).strip().casefold()
        for term in (ignored_unknown_terms or [])
        if str(term).strip()
    }
    detected_unregistered_terms = [
        term
        for term in word_dictionary.missing_terms(dictionary_entries)
        if term.casefold() not in ignored_term_keys
    ]
    unregistered_terms = detected_unregistered_terms if allow_term_registration else []
    dictionary_context = word_dictionary.format_entries(dictionary_entries, language)

    rewrite_error = None
    try:
        search_query = _rewrite_query(
            question,
            refined_question,
            dictionary_context,
            history,
            language,
            conversation_context,
        )
    except Exception as exc:
        rewrite_error = str(exc)
        search_query = refined_question or question

    return {
        "original_question": question,
        "refined_question": refined_question,
        "unknown_terms": unknown_terms,
        "dictionary_entries": dictionary_entries,
        "unregistered_terms": unregistered_terms,
        "detected_unregistered_terms": detected_unregistered_terms,
        "term_registration_allowed": allow_term_registration,
        "ignored_unknown_terms": list(ignored_unknown_terms or []),
        "dictionary_context": dictionary_context,
        "search_query": search_query,
        "steps": [
            {
                "node": "prepare_knowledge_question",
                "label": "LLM 질문 1차 정제·미지 단어 추출",
                "input": {
                    "question": question,
                    "conversation_context": conversation_context,
                    "history": history or [],
                },
                "output": {
                    "refined_question": refined_question,
                    "unknown_terms": unknown_terms,
                    "fallback_error": preparation_error,
                },
            },
            {
                "node": "lookup_word_dictionary",
                "label": "업무 단어사전 조회",
                "input": {"unknown_terms": unknown_terms},
                "output": {
                    "entries": dictionary_entries,
                    "unregistered_terms": unregistered_terms,
                    "detected_unregistered_terms": detected_unregistered_terms,
                    "term_registration_allowed": allow_term_registration,
                    "ignored_unknown_terms": list(ignored_unknown_terms or []),
                },
            },
            {
                "node": "rewrite_query_with_dictionary",
                "label": "단어사전 기준 최종 검색질문 정제",
                "input": {
                    "question": question,
                    "refined_question": refined_question,
                    "dictionary_entries": dictionary_entries,
                },
                "output": {
                    "search_query": search_query,
                    "fallback_error": rewrite_error,
                },
            },
        ],
    }


def _search_candidates(question: str, manual_id: int | None, k: int):
    """자식 청크로 검색하고, 부모 기준으로 중복 제거한 뒤 부모 내용을 반환한다."""
    query_vector = embedding_to_sql(embeddings.embed_query(question))
    manual_filter = "AND p.manual_id = :manual_id" if manual_id is not None else ""
    with engine.connect() as conn:
        rows = conn.execute(
            sql_text(f"""
                WITH raw AS (
                    SELECT
                        p.id          AS chunk_id,
                        p.content,
                        p.section_title,
                        p.manual_id,
                        m.title       AS manual_title,
                        p.version_id,
                        v.version_no,
                        v.created_at  AS source_created_at,
                        (1 - (c.embedding <=> CAST(:query_vector AS vector)))                              AS vector_score,
                        ts_rank(c.content_tsv, plainto_tsquery('simple', :question))                      AS keyword_score,
                        (0.7 * (1 - (c.embedding <=> CAST(:query_vector AS vector))))
                        + (0.3 * ts_rank(c.content_tsv, plainto_tsquery('simple', :question)))            AS combined_score
                    FROM {MANUAL_CHILD_CHUNKS} c
                    JOIN {MANUAL_PARENT_CHUNKS} p ON p.id = c.parent_id
                    JOIN {MANUALS} m              ON m.id = p.manual_id
                    JOIN {MANUAL_VERSIONS} v      ON v.id = p.version_id
                    WHERE c.embedding IS NOT NULL
                      AND v.index_step = 'done'
                      AND v.version_no = (
                          SELECT MAX(v2.version_no)
                          FROM {MANUAL_VERSIONS} v2
                          WHERE v2.manual_id = p.manual_id AND v2.index_step = 'done'
                      )
                      {manual_filter}
                    ORDER BY combined_score DESC
                    LIMIT :k_expanded
                ),
                deduped AS (
                    SELECT DISTINCT ON (chunk_id) *
                    FROM raw
                    ORDER BY chunk_id, combined_score DESC
                )
                SELECT * FROM deduped
                ORDER BY combined_score DESC
                LIMIT :k
            """),
            {
                "query_vector": query_vector,
                "question": question,
                "manual_id": manual_id,
                "k": k,
                "k_expanded": k * 5,
            },
        ).mappings().all()
    return rows


def _sources_from_chunks(rows) -> list[dict]:
    return [
        {
            "type": "manual",
            "id": row["chunk_id"],
            "title": row["manual_title"],
            "detail": f"버전 {row['version_no']} · {row['section_title'] or '제목 없음'}",
            "created_at": row["source_created_at"].isoformat(),
            "date_label": "매뉴얼 버전 생성일",
            "basis_date": row["source_created_at"].isoformat(),
            "basis_date_label": "매뉴얼 기준일",
        }
        for row in rows
    ]


def answer_question(
    question: str,
    manual_id: int | None,
    history: list[dict] | None = None,
    *,
    force_search: bool = False,
    language: str = "ko",
    conversation_context: str = "",
    prepared_query: dict | None = None,
) -> dict:
    check = (
        QueryCheck(proceed=True, clarify_text="", clarify_options=[])
        if force_search
        else _check_query(question, history, language, conversation_context)
    )
    check_step = {
        "node": "check_query",
        "label": "질문 적합성 판단",
        "input": {"question": question, "history": history or []},
        "output": {
            "proceed": check.proceed,
            "forced": force_search,
            "clarify_text": check.clarify_text,
            "clarify_options": check.clarify_options,
        },
    }
    if not check.proceed:
        return {
            "type": "clarify",
            "text": check.clarify_text,
            "options": check.clarify_options,
            "sources": [],
            "knowledge_match": {
                "matched": False,
                "reason": "query_rejected",
                "threshold": MANUAL_MATCH_THRESHOLD,
            },
            "trace": {"engine": "langchain", "steps": [check_step]},
        }

    query_preparation = prepared_query or prepare_knowledge_query(
        question,
        history,
        language,
        conversation_context,
    )
    search_query = query_preparation["search_query"]

    top_chunks = _search_candidates(search_query, manual_id, k=4)
    context = "\n\n".join(
        f"[{row['section_title'] or '제목 없음'}]\n{row['content']}"
        for row in top_chunks
    )

    system_prompt = format_prompt("qa_system", language=language, context=context)

    messages = [SystemMessage(content=system_prompt)]
    for turn in history or []:
        if turn.get("role") == "user":
            messages.append(HumanMessage(content=turn.get("text", "")))
        else:
            messages.append(AIMessage(content=turn.get("text", "")))
    messages.append(HumanMessage(content=question))

    result: ClarifyOrAnswer = call_llm(structured_llm, messages, label="qa_answer")
    top_score = round(float(top_chunks[0]["combined_score"]), 4) if top_chunks else 0.0
    manual_matched = bool(top_chunks) and top_score >= MANUAL_MATCH_THRESHOLD and result.type == "answer"
    basis_date = top_chunks[0]["source_created_at"].isoformat() if top_chunks else None

    trace = {
        "engine": "langchain",
        "steps": [
            check_step,
            *(query_preparation.get("steps") or []),
            {
                "node": "retrieve_candidates",
                "label": "관련 청크 검색",
                "input": {"search_query": search_query, "manual_id": manual_id, "k": 4},
                "output": [
                    {
                        "section_title": row["section_title"] or "",
                        "content": row["content"],
                        "vector_score": round(float(row["vector_score"]), 4),
                        "keyword_score": round(float(row["keyword_score"]), 4),
                        "combined_score": round(float(row["combined_score"]), 4),
                    }
                    for row in top_chunks
                ],
            },
            {
                "node": "build_context",
                "label": "컨텍스트 조립",
                "input": {"chunk_count": len(top_chunks)},
                "output": {"context": context},
            },
            {
                "node": "llm_invoke",
                "label": "LLM 응답 생성",
                "input": {
                    "system_prompt": system_prompt,
                    "history": history or [],
                    "question": question,
                },
                "output": {"type": result.type, "text": result.text, "options": result.options},
            },
        ]
    }
    return {
        "type": result.type,
        "text": result.text,
        "options": result.options,
        "sources": _sources_from_chunks(top_chunks) if result.type == "answer" else [],
        "knowledge_match": {
            "matched": manual_matched,
            "reason": "matched" if manual_matched else "below_threshold",
            "score": top_score,
            "threshold": MANUAL_MATCH_THRESHOLD,
            "basis_date": basis_date,
        },
        "trace": trace,
    }
