from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel, Field
from sqlalchemy import text as sql_text

from config import OPENAI_EMBEDDING_MODEL
from db import engine
from db_tables import MANUAL_CHILD_CHUNKS, MANUAL_PARENT_CHUNKS
from llm_clients import call_llm, embedding_to_sql, embeddings, llm
from manuals import jobs
from manuals.prompts import CHUNK_META_PROMPT
from manuals.splitting import convert_document

PARENT_CHUNK_SIZE = 1500
PARENT_CHUNK_OVERLAP = 200
CHILD_CHUNK_SIZE = 300
CHILD_CHUNK_OVERLAP = 50


class ChunkMeta(BaseModel):
    section_title: str = Field(description="이 청크가 속한 섹션/항목의 제목. 알 수 없으면 빈 문자열")
    keywords: list[str] = Field(
        description="이 청크의 핵심 키워드 3~7개. 사용자가 검색할 때 쓸 법한 용어 위주로"
    )


chunk_meta_llm = llm.with_structured_output(ChunkMeta)


def _extract_chunk_meta(chunk_text: str) -> ChunkMeta:
    prompt = CHUNK_META_PROMPT.format(chunk_text=chunk_text)
    try:
        return call_llm(chunk_meta_llm, prompt, label="chunk_meta")
    except Exception:
        return ChunkMeta(section_title="", keywords=[])


def chunk_document(docs: list) -> list[dict]:
    """문서를 부모-자식 청크로 분할한다.

    반환 형식:
        [{"content": str, "section_title": str, "keywords": list[str],
          "children": [{"content": str}, ...]}, ...]
    """
    parent_splitter = RecursiveCharacterTextSplitter(
        chunk_size=PARENT_CHUNK_SIZE,
        chunk_overlap=PARENT_CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    child_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHILD_CHUNK_SIZE,
        chunk_overlap=CHILD_CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    parent_docs = parent_splitter.split_documents(docs)
    result = []
    for parent_doc in parent_docs:
        meta = _extract_chunk_meta(parent_doc.page_content)
        child_docs = child_splitter.split_documents([parent_doc])
        result.append({
            "content": parent_doc.page_content,
            "section_title": meta.section_title,
            "keywords": meta.keywords,
            "children": [{"content": c.page_content} for c in child_docs],
        })
    return result


def embed_and_store(parent_chunks: list[dict], manual_id: int, version_id: int):
    """부모 청크를 저장하고 자식 청크를 임베딩·저장한다."""
    all_child_texts = [c["content"] for p in parent_chunks for c in p["children"]]
    child_vectors = embeddings.embed_documents(all_child_texts) if all_child_texts else []

    child_vec_idx = 0
    with engine.begin() as conn:
        for parent_idx, parent in enumerate(parent_chunks):
            parent_id = conn.execute(
                sql_text(f"""
                    INSERT INTO {MANUAL_PARENT_CHUNKS}
                        (manual_id, version_id, chunk_index, section_title, keywords, content)
                    VALUES
                        (:manual_id, :version_id, :chunk_index, :section_title, :keywords, :content)
                    ON CONFLICT (version_id, chunk_index) DO UPDATE SET
                        section_title = EXCLUDED.section_title,
                        keywords      = EXCLUDED.keywords,
                        content       = EXCLUDED.content
                    RETURNING id
                """),
                {
                    "manual_id": manual_id,
                    "version_id": version_id,
                    "chunk_index": parent_idx,
                    "section_title": parent["section_title"],
                    "keywords": parent["keywords"],
                    "content": parent["content"],
                },
            ).scalar_one()

            for child_idx, child in enumerate(parent["children"]):
                vector = child_vectors[child_vec_idx]
                child_vec_idx += 1
                conn.execute(
                    sql_text(f"""
                        INSERT INTO {MANUAL_CHILD_CHUNKS}
                            (parent_id, chunk_index, content, embedding, embedding_model)
                        VALUES
                            (:parent_id, :chunk_index, :content, CAST(:embedding AS vector), :embedding_model)
                        ON CONFLICT (parent_id, chunk_index) DO UPDATE SET
                            content         = EXCLUDED.content,
                            embedding       = EXCLUDED.embedding,
                            embedding_model = EXCLUDED.embedding_model
                    """),
                    {
                        "parent_id": parent_id,
                        "chunk_index": child_idx,
                        "content": child["content"],
                        "embedding": embedding_to_sql(vector),
                        "embedding_model": OPENAI_EMBEDDING_MODEL,
                    },
                )


def index_document(file_path: str, manual_id: int, version_id: int, job_id: int | None = None):
    try:
        if job_id is not None:
            jobs.update_job_step(job_id, "converting")
        docs = convert_document(file_path)

        if job_id is not None:
            jobs.update_job_step(job_id, "chunking")
        parent_chunks = chunk_document(docs)

        if job_id is not None:
            jobs.update_job_step(job_id, "embedding")
        embed_and_store(parent_chunks, manual_id, version_id)

        if job_id is not None:
            jobs.update_job_step(job_id, "done")
    except Exception as e:
        if job_id is not None:
            jobs.mark_job_failed(job_id, str(e))
        raise


def index_section(
    section_title: str,
    section_content: str,
    manual_id: int,
    version_id: int,
    job_id: int | None = None,
):
    try:
        if job_id is not None:
            jobs.update_job_step(job_id, "converting")
        docs = [Document(page_content=section_content, metadata={"section_title": section_title})]

        if job_id is not None:
            jobs.update_job_step(job_id, "chunking")
        parent_chunks = chunk_document(docs)

        if job_id is not None:
            jobs.update_job_step(job_id, "embedding")
        embed_and_store(parent_chunks, manual_id, version_id)

        if job_id is not None:
            jobs.update_job_step(job_id, "done")
    except Exception as e:
        if job_id is not None:
            jobs.mark_job_failed(job_id, str(e))
        raise
