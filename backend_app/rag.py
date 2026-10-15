import json
import re
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from sqlalchemy import text as sql_text

from config import MANUAL_MATCH_THRESHOLD, OPENAI_EMBEDDING_MODEL
from db import engine
from db_tables import MANUAL_CHILD_CHUNKS, MANUAL_PARENT_CHUNKS, MANUALS, MANUAL_VERSIONS, MANUAL_CHUNK_TABLE_VERSION
from llm_clients import call_llm, embeddings, embedding_to_sql, llm
from chat.prompts import format_prompt, prompt_label, schema_description
from chat import terms

class SearchPlan(BaseModel):
    intent: Literal['screen_business_list', 'general'] = 'general'
    keywords: list[str] = Field(default_factory=list, max_length=5)
    queries: list[str] = Field(default_factory=list, max_length=3)


class EvidenceDecision(BaseModel):
    chunk_id: int
    relevant: bool
    score: float = Field(ge=0, le=1)
    quote: str = ''


class EvidenceReview(BaseModel):
    decisions: list[EvidenceDecision] = Field(default_factory=list)


plan_llm = llm.with_structured_output(SearchPlan)
review_llm = llm.with_structured_output(EvidenceReview)


def is_discovery_question(question: str) -> bool:
    return bool(
        re.search(r'(?:화면|업무|메뉴|기능|screen|business|menu|function)', question, re.I)
        and re.search(r'어떤|어느|무슨|어디|목록|찾|할\s*수|가능|화면이나|업무는|화면은|which|what|where|list|find', question, re.I)
        # 특정 화면 가능 여부 확인은 기존 일반 검색으로 처리한다.
        and not re.search(r'#?\d{3,}\s*(?:번\s*)?화면|screen\s*#?\d+', question, re.I)
    )


def build_plan(question: str, search_query: str, language: str) -> tuple[SearchPlan, dict]:
    plan = SearchPlan()
    error = None
    if is_discovery_question(question) or is_discovery_question(search_query):
        try:
            plan = call_llm(plan_llm, format_prompt('manual_search_plan', language=language,
                            question=question, search_query=search_query), label='manual_search_plan')
        except Exception as exc:
            error = str(exc)
            # LLM 장애 시에도 질문에서 명시된 거래 표현만 사용한다.
            subject = re.split(r'(?:을|를)?\s*(?:할\s*수|가능한|가능\s*한)', question, maxsplit=1)[0]
            if subject != question and subject.strip():
                plan = SearchPlan(intent='screen_business_list', keywords=[subject.strip()])
    plan.keywords = list(dict.fromkeys(value.strip()[:80] for value in plan.keywords if value.strip()))[:5]
    plan.queries = list(dict.fromkeys(value.strip()[:300] for value in [search_query, *plan.queries, *plan.keywords] if value.strip()))[:4]
    return plan, {'node': 'manual_search_plan', 'label': '검색 의도·핵심어·다중 검색어 구성',
                  'input': {'question': question}, 'output': {**plan.model_dump(), 'error': error}}


def review_candidates(question: str, candidates: list[dict], language: str, threshold: float) -> tuple[list[dict], dict]:
    """후보를 빠짐없이 배치 평가하고 실제 인용문이 있는 관련 근거만 채택한다."""
    accepted = []
    evaluations = []
    errors = []
    for start in range(0, len(candidates), 8):
        batch = candidates[start:start + 8]
        documents = [{'chunk_id': row['chunk_id'], 'title': row['section_title'],
                      'content': row['content']} for row in batch]
        try:
            review = call_llm(review_llm, format_prompt('manual_evidence_review', language=language,
                              question=question, documents=json.dumps(documents, ensure_ascii=False)),
                              label='manual_evidence_review')
            # 중복 ID는 채택하지 않으며 다른 배치의 ID도 사용할 수 없다.
            by_id = {}
            for item in review.decisions:
                if item.chunk_id in by_id:
                    by_id[item.chunk_id] = None
                else:
                    by_id[item.chunk_id] = item
            for row in batch:
                decision = by_id.get(row['chunk_id'])
                valid_quote = bool(decision and decision.quote.strip()
                                   and decision.quote.strip() in row['content'])
                keep = bool(decision and decision.relevant and valid_quote and decision.score >= threshold)
                evaluations.append({'chunk_id': row['chunk_id'], 'accepted': keep,
                                    'score': decision.score if decision else None,
                                    'quote': decision.quote if valid_quote else None})
                if keep:
                    accepted.append({**row, 'retrieval_score': row['combined_score'],
                                     'combined_score': decision.score, 'evidence_quote': decision.quote.strip()})
        except Exception as exc:
            # 재평가 실패를 '지식 없음'으로 오인해 FAQ 접수로 넘기지 않는다.
            errors.append(str(exc))
    if errors:
        raise RuntimeError('매뉴얼 근거 재평가에 실패했습니다. 검색을 다시 시도해 주세요.')
    accepted.sort(key=lambda row: (-row['combined_score'], row['chunk_id']))
    return accepted, {'node': 'manual_evidence_review', 'label': '질문 관련성·원문 인용 근거 재평가',
                      'input': {'candidate_count': len(candidates)}, 'output': evaluations}


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
    excluded_terms: list[str] = Field(
        default_factory=list,
        description="현재 사용자 원문에 있는 사람이름(직함 없어도 포함), 팀·부서·지명, 숫자, 일반 금융단어. 신규단어 후보보다 먼저 분류하며 unknown_terms에 넣지 않는다.",
    )
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
                prompt_label("empty_value", language=language)
            ),
            history_text=_format_history_text([], language),
            question=question,
        ), label="query_prepare")
        refined_question = prepared.refined_question.strip() or question
        unknown_terms = list(dict.fromkeys(
            term.strip()
            for term in prepared.unknown_terms
            if allow_term_registration and term.strip()
            and term.strip().casefold() not in {value.strip().casefold() for value in prepared.excluded_terms}
            and terms.should_lookup_term(term, question)
        ))[:terms.MAX_UNKNOWN_TERMS]
    except Exception as exc:
        # 1차 정제 실패 시에도 단어사전 호출 계약과 지식검색 자체는 유지한다.
        preparation_error = str(exc)
        refined_question = question
        unknown_terms = []

    # 등록 생략 후 재개할 때도 기존 후보의 뜻(null 포함)을 LLM에 전달한다.
    unknown_terms = list(dict.fromkeys([
        *(term.strip() for term in (ignored_unknown_terms or []) if term.strip()),
        *unknown_terms,
    ]))
    # 검색어 유무와 관계없이 모든 지식검색 턴이 반드시 이 경계를 통과한다.
    dictionary_entries = terms.lookup_terms(unknown_terms)
    ignored_term_keys = {
        str(term).strip().casefold()
        for term in (ignored_unknown_terms or [])
        if str(term).strip()
    }
    detected_unregistered_terms = [
        term
        for term in terms.missing_terms(dictionary_entries)
        if term.casefold() not in ignored_term_keys
    ]
    # 생략을 선택한 이번 재검색에서는 LLM의 후보가 바뀌어도 등록을 다시 요구하지 않는다.
    unregistered_terms = detected_unregistered_terms if allow_term_registration and not ignored_unknown_terms else []
    dictionary_context = terms.format_entries(dictionary_entries, language)

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
                    "conversation_context": "",
                    "history": [],
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


def _search_candidates(question: str, manual_id: int | None, k: int | None = None,
                       *, keyword_terms: list[str] | None = None, candidate_threshold: float | None = None):
    """부모 본문 키워드와 자식 임베딩을 독립 검색하고 가장 높은 점수로 정렬한다."""
    query_vector = embedding_to_sql(embeddings.embed_query(question))
    with engine.connect() as conn:
        rows = conn.execute(sql_text(f"""
            WITH parents AS (
                SELECT p.id AS chunk_id, p.content, p.section_title, p.manual_id, p.keywords,
                       setweight(to_tsvector('simple', COALESCE(array_to_string(p.keywords, ' '), '')), 'A')
                         || setweight(to_tsvector('simple', p.content), 'B') AS keyword_document,
                       m.title AS manual_title, p.version_id, v.version_no,
                       v.created_at AS source_created_at
                FROM {MANUAL_PARENT_CHUNKS} p
                JOIN {MANUALS} m ON m.id = p.manual_id
                JOIN {MANUAL_VERSIONS} v ON v.id = p.version_id
                WHERE m.deleted_at IS NULL AND v.index_step = 'done'
                  AND (CAST(:manual_id AS integer) IS NULL OR p.manual_id = :manual_id)
                  AND v.version_no = (
                      SELECT MAX(v2.version_no) FROM {MANUAL_VERSIONS} v2
                      WHERE v2.manual_id = p.manual_id AND v2.index_step = 'done'
                        AND EXISTS (SELECT 1 FROM {MANUAL_PARENT_CHUNKS} p2 WHERE p2.version_id = v2.id)
                  )
            ), vector_candidates AS (
                SELECT p.chunk_id,
                       MAX(GREATEST(0, 1 - (c.embedding <=> CAST(:query_vector AS vector)))) AS vector_score
                FROM {MANUAL_CHILD_CHUNKS} c
                JOIN parents p ON p.chunk_id = c.parent_id
                WHERE c.embedding IS NOT NULL
                  AND c.embedding_model = :embedding_model
                GROUP BY p.chunk_id
                ORDER BY vector_score DESC {"LIMIT :expanded" if k is not None else ""}
            ), core_matches AS (
                SELECT p.chunk_id,
                       COALESCE((SELECT AVG(CASE WHEN position(lower(term.value) IN
                           lower(COALESCE(p.section_title, '') || ' ' || p.content || ' ' ||
                           COALESCE(array_to_string(p.keywords, ' '), ''))) > 0
                           THEN 1.0 ELSE 0.0 END)
                           FROM jsonb_array_elements_text(CAST(:keyword_terms AS jsonb)) AS term(value)), 0) AS core_score
                FROM parents p
            ), keyword_candidates AS (
                SELECT p.chunk_id,
                       GREATEST(ts_rank_cd(p.keyword_document,
                                  plainto_tsquery('simple', :question)), cm.core_score) AS raw_score
                FROM parents p
                JOIN core_matches cm ON cm.chunk_id = p.chunk_id
                WHERE p.keyword_document @@ plainto_tsquery('simple', :question) OR cm.core_score > 0
                ORDER BY raw_score DESC {"LIMIT :expanded" if k is not None else ""}
            ), scores AS (
                SELECT p.*, COALESCE(vc.vector_score, 0) AS vector_score,
                       COALESCE(kc.raw_score / (kc.raw_score + 0.1), 0) AS keyword_score
                FROM parents p
                LEFT JOIN vector_candidates vc ON vc.chunk_id = p.chunk_id
                LEFT JOIN keyword_candidates kc ON kc.chunk_id = p.chunk_id
                WHERE vc.chunk_id IS NOT NULL OR kc.chunk_id IS NOT NULL
            )
            SELECT *, GREATEST(vector_score, keyword_score) AS combined_score,
                   CASE WHEN keyword_score > vector_score THEN 'keyword' ELSE 'embedding' END AS matched_method
            FROM scores
            WHERE GREATEST(vector_score, keyword_score) >= :threshold
            ORDER BY combined_score DESC, chunk_id {"LIMIT :k" if k is not None else ""}
        """), {"query_vector": query_vector, "question": question,
               "manual_id": manual_id, "embedding_model": OPENAI_EMBEDDING_MODEL,
               "keyword_terms": json.dumps(keyword_terms or [], ensure_ascii=False),
               "threshold": MANUAL_MATCH_THRESHOLD if candidate_threshold is None else candidate_threshold,
               "expanded": k * 5 if k is not None else None, "k": k}).mappings().all()
    return rows


def _sources_from_chunks(rows) -> list[dict]:
    return [
        {
            "type": "manual",
            "id": row["chunk_id"],
            "title": row["manual_title"],
            "manual_id": row["manual_id"],
            "url": f"/mindmap?manual_id={row['manual_id']}",
            "matched_method": row.get("matched_method"),
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

    plan, plan_step = build_plan(question, search_query, language)
    search_steps = [plan_step]
    if plan.intent == 'screen_business_list':
        candidates = {}
        query_errors = []
        for expression in plan.queries:
            try:
                rows = _search_candidates(expression, manual_id, keyword_terms=plan.keywords,
                                          candidate_threshold=min(MANUAL_MATCH_THRESHOLD, 0.40))
                search_steps.append({'node': 'manual_multi_search', 'label': '표현별 임베딩·핵심어 검색',
                                     'input': {'query': expression, 'keywords': plan.keywords},
                                     'output': {'candidate_count': len(rows)}})
                for row in rows:
                    current = candidates.get(row['chunk_id'])
                    if current is None or row['combined_score'] > current['combined_score']:
                        candidates[row['chunk_id']] = dict(row)
            except Exception as exc:
                query_errors.append(str(exc))
        if query_errors:
            # 실패를 미검색으로 숨기거나 불완전한 목록을 완전한 결과처럼 반환하지 않는다.
            raise RuntimeError('매뉴얼 다중 검색에 실패했습니다. 검색을 다시 시도해 주세요.')
        top_chunks, review_step = review_candidates(
            search_query, list(candidates.values()), language, MANUAL_MATCH_THRESHOLD)
        search_steps.append(review_step)
    else:
        top_chunks = _search_candidates(search_query, manual_id)
    context = "\n\n".join(
        f"[매뉴얼: {row['manual_title']} / {row['section_title'] or '제목 없음'}]\n"
        + (f"[검증된 원문 근거]\n{row['evidence_quote']}\n" if row.get('evidence_quote') else '')
        + row['content']
        for row in top_chunks
    )

    system_prompt = format_prompt("qa_system", language=language, context=context)
    if plan.intent == 'screen_business_list':
        system_prompt += '\n\n' + format_prompt('manual_discovery_answer', language=language)

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
            *search_steps,
            {
                "node": "retrieve_candidates",
                "label": "관련 청크 검색",
                "input": {"search_query": search_query, "manual_id": manual_id, "threshold": MANUAL_MATCH_THRESHOLD, "k": None},
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
