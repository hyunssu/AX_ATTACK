import re
from typing import Literal

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel, Field
from sqlalchemy import text as sql_text

from manuals import jobs
from config import (
    MANUAL_MATCH_THRESHOLD,
    OPENAI_CHAT_MODEL,
    OPENAI_EMBEDDING_DIMENSIONS,
    OPENAI_EMBEDDING_MODEL,
)
from db import engine
from db_tables import MANUAL_CHUNKS, MANUALS, MANUAL_VERSIONS
from chat.prompts import format_prompt, prompt_label, schema_description
from chat import word_dictionary

embeddings = OpenAIEmbeddings(
    model=OPENAI_EMBEDDING_MODEL,
    dimensions=OPENAI_EMBEDDING_DIMENSIONS,
)
llm = ChatOpenAI(model=OPENAI_CHAT_MODEL, temperature=0)


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
    return query_check_llm.invoke(prompt)


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
    rewrite: QueryRewrite = query_rewrite_llm.invoke(prompt)
    return rewrite.standalone_question or refined_question or question


def prepare_knowledge_query(
    question: str,
    history: list[dict] | None,
    language: str = "ko",
    conversation_context: str = "",
) -> dict:
    """질문 정제 → 단어사전 → 사전 기반 최종 검색질문을 공통 생성한다."""
    preparation_error = None
    try:
        prepared: QueryPreparation = query_prepare_llm.invoke(format_prompt(
            "query_prepare",
            language=language,
            conversation_context=(
                conversation_context or prompt_label("empty_value", language=language)
            ),
            history_text=_format_history_text(history, language),
            question=question,
        ))
        refined_question = prepared.refined_question.strip() or question
        unknown_terms = list(dict.fromkeys(
            term.strip() for term in prepared.unknown_terms if term.strip()
        ))[:word_dictionary.MAX_UNKNOWN_TERMS]
    except Exception as exc:
        # 1차 정제 실패 시에도 단어사전 호출 계약과 지식검색 자체는 유지한다.
        preparation_error = str(exc)
        refined_question = question
        unknown_terms = []

    # 검색어 유무와 관계없이 모든 지식검색 턴이 반드시 이 경계를 통과한다.
    dictionary_entries = word_dictionary.lookup_terms(unknown_terms)
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
                "output": {"entries": dictionary_entries},
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


class ChunkMeta(BaseModel):
    section_title: str = Field(description=schema_description("rag.section_title"))
    keywords: list[str] = Field(
        description=schema_description("rag.chunk_keywords")
    )


chunk_meta_llm = llm.with_structured_output(ChunkMeta)


def _embedding_to_sql(vector: list[float]) -> str:
    return "[" + ",".join(str(x) for x in vector) + "]"


def _extract_chunk_meta(chunk_text: str) -> ChunkMeta:
    prompt = format_prompt("chunk_meta", chunk_text=chunk_text)
    try:
        return chunk_meta_llm.invoke(prompt)
    except Exception:
        return ChunkMeta(section_title="", keywords=[])


def convert_document(file_path: str):
    """1단계(파일 변환): PDF/Markdown 원본을 저장하기 좋은 순수 텍스트 문서로 변환한다."""
    if file_path.lower().endswith(".md"):
        return TextLoader(file_path, encoding="utf-8").load()
    return PyPDFLoader(file_path).load()


MD_HEADING_RE = re.compile(r'^(#{1,6})\s+(.*)$')
MD_MAJOR_HEADING_MAX_LEVEL = 2  # #, ## 까지만 "대 단위" 경계로 취급

HEADING_PATTERNS = [
    re.compile(r'^\s*제\s*\d+\s*장'),                  # 제1장
    re.compile(r'^\s*\d+\s*장\b'),                      # 1장
    re.compile(r'^\s*Chapter\s+\d+', re.IGNORECASE),   # Chapter 1
    re.compile(r'^\s*\d+\.\d+\s+.{2,}$'),               # 1.2 Title (소절 번호, 일반 번호 목록과 구분하기 위해 소수점 필수)
]
MAX_PDF_LINE_LEN_FOR_HEADING = 80
MIN_SECTION_LEN = 30


def _merge_tiny_sections(sections: list[dict]) -> list[dict]:
    """짧은 섹션(오탐 가능성 높음)은 이전 섹션에 합친다."""
    merged: list[dict] = []
    for section in sections:
        if merged and section["char_count"] < MIN_SECTION_LEN:
            prev = merged[-1]
            prev["content"] = (prev["content"] + "\n" + section["content"]).strip()
            prev["char_count"] = len(prev["content"])
        else:
            merged.append(section)
    return merged


def _split_markdown_sections(text: str) -> list[dict]:
    sections: list[dict] = []
    current_title = ""
    current_lines: list[str] = []

    def _flush():
        content = "\n".join(current_lines).strip()
        if content:
            sections.append({"title": current_title, "content": content, "char_count": len(content)})

    for line in text.splitlines():
        match = MD_HEADING_RE.match(line)
        if match and len(match.group(1)) <= MD_MAJOR_HEADING_MAX_LEVEL:
            _flush()
            current_title = match.group(2).strip()
            current_lines = []
        else:
            current_lines.append(line)
    _flush()

    return _merge_tiny_sections(sections)


def _split_pdf_sections(file_path: str) -> list[dict]:
    docs = convert_document(file_path)
    full_text = "\n".join(doc.page_content for doc in docs)

    sections: list[dict] = []
    current_title = ""
    current_lines: list[str] = []

    def _flush():
        content = "\n".join(current_lines).strip()
        if content:
            sections.append({"title": current_title, "content": content, "char_count": len(content)})

    for line in full_text.splitlines():
        stripped = line.strip()
        is_heading = (
            len(stripped) <= MAX_PDF_LINE_LEN_FOR_HEADING
            and stripped
            and any(pattern.match(stripped) for pattern in HEADING_PATTERNS)
        )
        if is_heading:
            _flush()
            current_title = stripped
            current_lines = []
        else:
            current_lines.append(line)
    _flush()

    if not sections:
        if full_text.strip():
            return [{"title": "전체 문서", "content": full_text.strip(), "char_count": len(full_text.strip())}]
        return []

    return _merge_tiny_sections(sections)


def split_into_major_sections(file_path: str) -> list[dict]:
    """대 단위(장/챕터 수준) 분할 미리보기. 임베딩용 chunk_document와는 별개의 순수 파싱 로직."""
    if file_path.lower().endswith(".md"):
        text = TextLoader(file_path, encoding="utf-8").load()[0].page_content
        return _split_markdown_sections(text)
    return _split_pdf_sections(file_path)


def chunk_document(docs: list) -> list[dict]:
    """2단계(청킹): 문서를 청크로 자르고, 청크마다 section_title/keywords 메타데이터를 추출한다."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=150,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    raw_chunks = splitter.split_documents(docs)
    chunks = []
    for raw_chunk in raw_chunks:
        meta = _extract_chunk_meta(raw_chunk.page_content)
        chunks.append({
            "content": raw_chunk.page_content,
            "section_title": meta.section_title,
            "keywords": meta.keywords,
        })
    return chunks


def embed_and_store(chunks: list[dict], manual_id: int, version_id: int):
    """3단계(임베딩/저장): 청크를 임베딩하고 manual_chunks_kyj에 upsert한다."""
    vectors = embeddings.embed_documents([chunk["content"] for chunk in chunks])
    with engine.begin() as conn:
        for chunk_index, (chunk, vector) in enumerate(zip(chunks, vectors)):
            conn.execute(
                sql_text(f"""
                    INSERT INTO {MANUAL_CHUNKS}
                        (manual_id, version_id, chunk_index, section_title, keywords, content, embedding)
                    VALUES
                        (:manual_id, :version_id, :chunk_index, :section_title, :keywords, :content, CAST(:embedding AS vector))
                    ON CONFLICT (version_id, chunk_index) DO UPDATE SET
                        section_title = EXCLUDED.section_title,
                        keywords = EXCLUDED.keywords,
                        content = EXCLUDED.content,
                        embedding = EXCLUDED.embedding
                """),
                {
                    "manual_id": manual_id,
                    "version_id": version_id,
                    "chunk_index": chunk_index,
                    "section_title": chunk["section_title"],
                    "keywords": chunk["keywords"],
                    "content": chunk["content"],
                    "embedding": _embedding_to_sql(vector),
                }
            )


def index_document(file_path: str, manual_id: int, version_id: int, job_id: int | None = None):
    """파일 변환 -> 청킹 -> 임베딩/저장 3단계를 순서대로 실행한다.
    job_id가 주어지면 단계마다 manual_versions_kyj에 진행 상황을 기록해 프론트 폴링에 노출한다."""
    try:
        if job_id is not None:
            jobs.update_job_step(job_id, "converting")
        docs = convert_document(file_path)

        if job_id is not None:
            jobs.update_job_step(job_id, "chunking")
        chunks = chunk_document(docs)

        if job_id is not None:
            jobs.update_job_step(job_id, "embedding")
        embed_and_store(chunks, manual_id, version_id)

        if job_id is not None:
            jobs.update_job_step(job_id, "done")
    except Exception as e:
        if job_id is not None:
            jobs.mark_job_failed(job_id, str(e))
        raise


def _search_candidates(question: str, manual_id: int | None, k: int):
    query_vector = _embedding_to_sql(embeddings.embed_query(question))
    manual_filter = "AND c.manual_id = :manual_id" if manual_id is not None else ""
    with engine.connect() as conn:
        rows = conn.execute(
            sql_text(f"""
                SELECT
                    c.id AS chunk_id,
                    c.content,
                    c.section_title,
                    c.manual_id,
                    m.title AS manual_title,
                    c.version_id,
                    v.version_no,
                    v.created_at AS source_created_at,
                    (1 - (c.embedding <=> CAST(:query_vector AS vector))) AS vector_score,
                    ts_rank(c.content_tsv, plainto_tsquery('simple', :question)) AS keyword_score,
                    (0.7 * (1 - (c.embedding <=> CAST(:query_vector AS vector))))
                    + (0.3 * ts_rank(c.content_tsv, plainto_tsquery('simple', :question))) AS combined_score
                FROM {MANUAL_CHUNKS} c
                JOIN {MANUALS} m ON m.id = c.manual_id
                JOIN {MANUAL_VERSIONS} v ON v.id = c.version_id
                WHERE c.embedding IS NOT NULL {manual_filter}
                ORDER BY
                    (0.7 * (1 - (c.embedding <=> CAST(:query_vector AS vector))))
                    + (0.3 * ts_rank(c.content_tsv, plainto_tsquery('simple', :question))) DESC
                LIMIT :k
            """),
            {"query_vector": query_vector, "question": question, "manual_id": manual_id, "k": k}
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

    result: ClarifyOrAnswer = structured_llm.invoke(messages)
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
