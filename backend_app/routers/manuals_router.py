import os
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy import text

import jobs
from auth import get_current_user
from db import engine
from rag import index_document, split_into_major_sections
from storage import upload_file

router = APIRouter(prefix="/api/manuals", tags=["manuals"])

ALLOWED_EXTENSIONS = (".pdf", ".md")


def _save_temp_file(file_bytes: bytes, filename: str) -> str:
    tmp_path = f"/tmp/{uuid.uuid4()}_{filename}"
    with open(tmp_path, "wb") as f:
        f.write(file_bytes)
    return tmp_path


def _validate_extension(filename: str):
    if not filename.lower().endswith(ALLOWED_EXTENSIONS):
        raise HTTPException(status_code=400, detail="PDF 또는 Markdown(.md) 파일만 업로드할 수 있습니다.")


def _run_indexing_job(tmp_path: str, manual_id: int, version_id: int, job_id: int):
    try:
        index_document(tmp_path, manual_id, version_id, job_id=job_id)
    finally:
        os.remove(tmp_path)


@router.post("/preview-sections")
async def preview_manual_sections(
    file: UploadFile = File(...),
    username: str = Depends(get_current_user),
):
    _validate_extension(file.filename)
    file_bytes = await file.read()
    tmp_path = _save_temp_file(file_bytes, file.filename)
    try:
        sections = split_into_major_sections(tmp_path)
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="파일 인코딩을 읽을 수 없습니다. UTF-8 텍스트 파일인지 확인해 주세요.")
    finally:
        os.remove(tmp_path)
    source_type = "pdf" if file.filename.lower().endswith(".pdf") else "md"
    return {"sections": sections, "section_count": len(sections), "source_type": source_type}


@router.post("")
async def create_manual(
    background_tasks: BackgroundTasks,
    title: str,
    file: UploadFile = File(...),
    username: str = Depends(get_current_user),
):
    _validate_extension(file.filename)
    file_bytes = await file.read()
    file_url = upload_file(file_bytes, file.filename, file.content_type)
    tmp_path = _save_temp_file(file_bytes, file.filename)

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

    job_id = jobs.create_job(manual_id, version_id)
    background_tasks.add_task(_run_indexing_job, tmp_path, manual_id, version_id, job_id)

    return {"manual_id": manual_id, "version_id": version_id, "file_url": file_url, "job_id": job_id}


@router.post("/{manual_id}/versions")
async def create_manual_version(
    manual_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    username: str = Depends(get_current_user),
):
    _validate_extension(file.filename)
    with engine.begin() as conn:
        exists = conn.execute(text("SELECT id FROM manuals WHERE id = :id"), {"id": manual_id}).first()
        if not exists:
            raise HTTPException(status_code=404, detail="Manual not found")

        next_version = conn.execute(
            text("SELECT COALESCE(MAX(version_no), 0) + 1 FROM manual_versions WHERE manual_id = :id"),
            {"id": manual_id}
        ).scalar_one()

    file_bytes = await file.read()
    file_url = upload_file(file_bytes, file.filename, file.content_type)
    tmp_path = _save_temp_file(file_bytes, file.filename)

    with engine.begin() as conn:
        version_id = conn.execute(
            text("""
                INSERT INTO manual_versions (manual_id, version_no, file_name, file_url)
                VALUES (:manual_id, :version_no, :file_name, :file_url)
                RETURNING id
            """),
            {"manual_id": manual_id, "version_no": next_version, "file_name": file.filename, "file_url": file_url}
        ).scalar_one()

    job_id = jobs.create_job(manual_id, version_id)
    background_tasks.add_task(_run_indexing_job, tmp_path, manual_id, version_id, job_id)

    return {"manual_id": manual_id, "version_id": version_id, "version_no": next_version, "file_url": file_url, "job_id": job_id}


@router.get("/jobs/{job_id}")
def get_job_status(job_id: int, username: str = Depends(get_current_user)):
    job = jobs.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"step": job["step"], "error_message": job["error_message"]}


@router.get("")
def list_manuals(username: str = Depends(get_current_user)):
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT m.id, m.title, m.created_at, COUNT(mv.id) AS version_count
                FROM manuals m
                LEFT JOIN manual_versions mv ON mv.manual_id = m.id
                GROUP BY m.id
                ORDER BY m.id DESC
            """)
        ).mappings().all()
    return [dict(r) for r in rows]


@router.get("/{manual_id}/versions")
def list_versions(manual_id: int, username: str = Depends(get_current_user)):
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT id, version_no, file_name, file_url, created_at
                FROM manual_versions WHERE manual_id = :id ORDER BY version_no DESC
            """),
            {"id": manual_id}
        ).mappings().all()
    return [dict(r) for r in rows]


@router.get("/{manual_id}/versions/{version_id}/content")
def get_version_content(manual_id: int, version_id: int, username: str = Depends(get_current_user)):
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT chunk_index, section_title, content
                FROM manual_chunks_khs
                WHERE manual_id = :manual_id AND version_id = :version_id
                ORDER BY chunk_index
            """),
            {"manual_id": manual_id, "version_id": version_id}
        ).mappings().all()
    return {"chunks": [dict(r) for r in rows]}
