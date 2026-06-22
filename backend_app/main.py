from fastapi import FastAPI, File, UploadFile, HTTPException
from pydantic import BaseModel
from typing import Optional
from minio import Minio
import uuid
import io
import os
from datetime import timedelta

from sqlalchemy import create_engine, text
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_postgres import PGVector
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

app = FastAPI()

MINIO_USER = os.getenv("MINIO_USER")
MINIO_PASSWORD = os.getenv("MINIO_PASSWORD")
MINIO_EXT_ENDPOINT = os.getenv("MINIO_EXT_ENDPOINT")
BUCKET_NAME = "chat-attachments"

minio_ext_client = Minio(
    MINIO_EXT_ENDPOINT,
    access_key=MINIO_USER,
    secret_key=MINIO_PASSWORD,
    secure=False
)

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DB_URL)

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

COLLECTION_NAME = "manual_chunks"
vector_store = PGVector(
    embeddings=embeddings,
    collection_name=COLLECTION_NAME,
    connection=DB_URL,
)


def upload_to_minio(file_bytes: bytes, filename: str, content_type: str) -> str:
    unique_filename = f"{uuid.uuid4()}_{filename}"
    minio_ext_client.put_object(
        BUCKET_NAME, unique_filename, io.BytesIO(file_bytes), len(file_bytes), content_type=content_type
    )
    url = minio_ext_client.get_presigned_url("GET", BUCKET_NAME, unique_filename, expires=timedelta(days=7))
    return url


def index_pdf(file_path: str, manual_id: int, version_id: int):
    loader = PyPDFLoader(file_path)
    docs = loader.load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = splitter.split_documents(docs)
    for chunk in chunks:
        chunk.metadata["manual_id"] = manual_id
        chunk.metadata["version_id"] = version_id
    vector_store.add_documents(chunks)


@app.post("/api/manuals")
async def create_manual(title: str, file: UploadFile = File(...)):
    file_bytes = await file.read()
    file_url = upload_to_minio(file_bytes, file.filename, file.content_type)

    tmp_path = f"/tmp/{uuid.uuid4()}_{file.filename}"
    with open(tmp_path, "wb") as f:
        f.write(file_bytes)

    with engine.begin() as conn:
        manual_id = conn.execute(
            text("INSERT INTO manuals (title) VALUES (:title) RETURNING id"),
            {"title": title}
        ).scalar_one()
        version_id = conn.execute(
            text("""
                INSERT INTO manual_versions (manual_id, version_no, file_name, file_url)
                VALUES (:manual_id, 1, :file_name, :file_url)
                RETURNING id
            """),
            {"manual_id": manual_id, "file_name": file.filename, "file_url": file_url}
        ).scalar_one()

    index_pdf(tmp_path, manual_id, version_id)
    os.remove(tmp_path)

    return {"manual_id": manual_id, "version_id": version_id, "file_url": file_url}


@app.post("/api/manuals/{manual_id}/versions")
async def create_manual_version(manual_id: int, file: UploadFile = File(...)):
    with engine.begin() as conn:
        exists = conn.execute(text("SELECT id FROM manuals WHERE id = :id"), {"id": manual_id}).first()
        if not exists:
            raise HTTPException(status_code=404, detail="Manual not found")

        next_version = conn.execute(
            text("SELECT COALESCE(MAX(version_no), 0) + 1 FROM manual_versions WHERE manual_id = :id"),
            {"id": manual_id}
        ).scalar_one()

    file_bytes = await file.read()
    file_url = upload_to_minio(file_bytes, file.filename, file.content_type)

    tmp_path = f"/tmp/{uuid.uuid4()}_{file.filename}"
    with open(tmp_path, "wb") as f:
        f.write(file_bytes)

    with engine.begin() as conn:
        version_id = conn.execute(
            text("""
                INSERT INTO manual_versions (manual_id, version_no, file_name, file_url)
                VALUES (:manual_id, :version_no, :file_name, :file_url)
                RETURNING id
            """),
            {"manual_id": manual_id, "version_no": next_version, "file_name": file.filename, "file_url": file_url}
        ).scalar_one()

    index_pdf(tmp_path, manual_id, version_id)
    os.remove(tmp_path)

    return {"manual_id": manual_id, "version_id": version_id, "version_no": next_version, "file_url": file_url}


@app.get("/api/manuals")
def list_manuals():
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, title, created_at FROM manuals ORDER BY id DESC")).mappings().all()
    return [dict(r) for r in rows]


@app.get("/api/manuals/{manual_id}/versions")
def list_versions(manual_id: int):
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT id, version_no, file_name, file_url, created_at
                FROM manual_versions WHERE manual_id = :id ORDER BY version_no DESC
            """),
            {"id": manual_id}
        ).mappings().all()
    return [dict(r) for r in rows]


class ChatRequest(BaseModel):
    input_message: str
    manual_id: Optional[int] = None


@app.post("/api/chat")
def chat(req: ChatRequest):
    search_kwargs = {"k": 4}
    if req.manual_id is not None:
        search_kwargs["filter"] = {"manual_id": req.manual_id}

    retriever = vector_store.as_retriever(search_kwargs=search_kwargs)
    relevant_docs = retriever.invoke(req.input_message)

    context = "\n\n".join(doc.page_content for doc in relevant_docs)
    prompt = (
        "다음 매뉴얼 내용을 참고해서 질문에 답해줘. 내용에 없는 건 모른다고 답해.\n\n"
        f"[매뉴얼 내용]\n{context}\n\n[질문]\n{req.input_message}"
    )

    try:
        response = llm.invoke(prompt)
        return {"output_message": response.content}
    except Exception as e:
        return {"output_message": f"LLM 호출 에러: {str(e)}"}
