import re
from typing import Literal

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel, Field
from sqlalchemy import text as sql_text

import jobs
from config import OPENAI_CHAT_MODEL, OPENAI_EMBEDDING_MODEL
from db import engine
from prompts import CHUNK_META_PROMPT, QA_SYSTEM_PROMPT

embeddings = OpenAIEmbeddings(model=OPENAI_EMBEDDING_MODEL)
llm = ChatOpenAI(model=OPENAI_CHAT_MODEL, temperature=0)


class ClarifyOrAnswer(BaseModel):
    type: Literal["clarify", "answer"] = Field(
        description="매뉴얼 내용과 대화 맥락만으로 바로 답변할 수 있으면 'answer', "
        "질문이 모호하거나 추가 정보가 필요하면 'clarify'"
    )
    text: str = Field(description="사용자에게 보여줄 답변 또는 되묻는 질문 내용")
    options: list[str] = Field(
        default_factory=list,
        description="type이 clarify일 때 사용자가 고를 수 있는 2~4개의 선택지. answer일 때는 빈 배열",
    )


structured_llm = llm.with_structured_output(ClarifyOrAnswer)


class ChunkMeta(BaseModel):
    section_title: str = Field(description="이 청크가 속한 섹션/항목의 제목. 알 수 없으면 빈 문자열")
    keywords: list[str] = Field(
        description="이 청크의 핵심 키워드 3~7개. 사용자가 검색할 때 쓸 법한 용어 위주로"
    )


chunk_meta_llm = llm.with_structured_output(ChunkMeta)


def _embedding_to_sql(vector: list[float]) -> str:
    return "[" + ",".join(str(x) for x in vector) + "]"


def _extract_chunk_meta(chunk_text: str) -> ChunkMeta:
    prompt = CHUNK_META_PROMPT.format(chunk_text=chunk_text)
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
    """3단계(임베딩/저장): 청크를 임베딩하고 manual_chunks_khs에 upsert한다."""
    vectors = embeddings.embed_documents([chunk["content"] for chunk in chunks])
    with engine.begin() as conn:
        for chunk_index, (chunk, vector) in enumerate(zip(chunks, vectors)):
            conn.execute(
                sql_text("""
                    INSERT INTO manual_chunks_khs
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
    job_id가 주어지면 단계마다 manual_upload_jobs_khs에 진행 상황을 기록해 프론트 폴링에 노출한다."""
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
    manual_filter = "AND manual_id = :manual_id" if manual_id is not None else ""
    with engine.connect() as conn:
        rows = conn.execute(
            sql_text(f"""
                SELECT
                    content,
                    section_title,
                    (1 - (embedding <=> CAST(:query_vector AS vector))) AS vector_score,
                    ts_rank(content_tsv, plainto_tsquery('simple', :question)) AS keyword_score
                FROM manual_chunks_khs
                WHERE embedding IS NOT NULL {manual_filter}
                ORDER BY
                    (0.7 * (1 - (embedding <=> CAST(:query_vector AS vector))))
                    + (0.3 * ts_rank(content_tsv, plainto_tsquery('simple', :question))) DESC
                LIMIT :k
            """),
            {"query_vector": query_vector, "question": question, "manual_id": manual_id, "k": k}
        ).mappings().all()
    return rows


def answer_question(question: str, manual_id: int | None, history: list[dict] | None = None) -> dict:
    top_chunks = _search_candidates(question, manual_id, k=4)
    context = "\n\n".join(
        f"[{row['section_title'] or '제목 없음'}]\n{row['content']}"
        for row in top_chunks
    )

    system_prompt = QA_SYSTEM_PROMPT.format(context=context)

    messages = [SystemMessage(content=system_prompt)]
    for turn in history or []:
        if turn.get("role") == "user":
            messages.append(HumanMessage(content=turn.get("text", "")))
        else:
            messages.append(AIMessage(content=turn.get("text", "")))
    messages.append(HumanMessage(content=question))

    result: ClarifyOrAnswer = structured_llm.invoke(messages)

    trace = {
        "steps": [
            {
                "label": "1. 후보 청크 검색",
                "detail": f"벡터 유사도(70%) + 키워드 검색(30%) 점수로 상위 {len(top_chunks)}개 청크를 선택했어요.",
                "chunks": [
                    {
                        "section_title": row["section_title"] or "제목 없음",
                        "excerpt": row["content"][:150] + ("…" if len(row["content"]) > 150 else ""),
                        "vector_score": round(float(row["vector_score"]), 3),
                        "keyword_score": round(float(row["keyword_score"]), 3),
                    }
                    for row in top_chunks
                ],
            },
            {
                "label": "2. 컨텍스트 구성",
                "detail": f"선택된 {len(top_chunks)}개 청크를 섹션 제목과 함께 하나로 합쳐 LLM에 전달할 컨텍스트를 만들었어요.",
            },
            {
                "label": "3. LLM 응답 생성",
                "detail": f"시스템 프롬프트 + 최근 대화 {len(history or [])}건 + 이번 질문을 LLM에 전달해 '{result.type}' 형태로 응답을 받았어요.",
            },
        ]
    }
    return {"type": result.type, "text": result.text, "options": result.options, "trace": trace}
