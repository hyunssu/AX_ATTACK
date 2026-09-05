from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel, Field
from sqlalchemy import text as sql_text

from db import engine
from llm_clients import embedding_to_sql, embeddings, llm
from manuals import jobs
from manuals.prompts import CHUNK_META_PROMPT
from manuals.splitting import convert_document


class ChunkMeta(BaseModel):
    section_title: str = Field(description="이 청크가 속한 섹션/항목의 제목. 알 수 없으면 빈 문자열")
    keywords: list[str] = Field(
        description="이 청크의 핵심 키워드 3~7개. 사용자가 검색할 때 쓸 법한 용어 위주로"
    )


chunk_meta_llm = llm.with_structured_output(ChunkMeta)


def _extract_chunk_meta(chunk_text: str) -> ChunkMeta:
    prompt = CHUNK_META_PROMPT.format(chunk_text=chunk_text)
    try:
        return chunk_meta_llm.invoke(prompt)
    except Exception:
        return ChunkMeta(section_title="", keywords=[])


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
                    "embedding": embedding_to_sql(vector),
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


def index_section(section_title: str, section_content: str, manual_id: int, version_id: int, job_id: int | None = None):
    """이미 분할된 섹션 텍스트를 청킹 -> 임베딩/저장한다. 원본 파일을 다시 읽지 않는다."""
    try:
        if job_id is not None:
            jobs.update_job_step(job_id, "converting")
        docs = [Document(page_content=section_content, metadata={"section_title": section_title})]

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
