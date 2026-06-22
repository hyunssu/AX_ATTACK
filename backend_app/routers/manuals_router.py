import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import text

from auth import get_current_user
from db import engine
from rag import index_pdf
from storage import upload_file

router = APIRouter(prefix="/api/manuals", tags=["manuals"])


def _save_temp_file(file_bytes: bytes, filename: str) -> str:
    tmp_path = f"/tmp/{uuid.uuid4()}_{filename}"
    with open(tmp_path, "wb") as f:
        f.write(file_bytes)
    return tmp_path


@router.post("")
async def create_manual(title: str, file: UploadFile = File(...), username: str = Depends(get_current_user)):
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

    index_pdf(tmp_path, manual_id, version_id)
    os.remove(tmp_path)

    return {"manual_id": manual_id, "version_id": version_id, "file_url": file_url}


@router.post("/{manual_id}/versions")
async def create_manual_version(manual_id: int, file: UploadFile = File(...), username: str = Depends(get_current_user)):
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

    index_pdf(tmp_path, manual_id, version_id)
    os.remove(tmp_path)

    return {"manual_id": manual_id, "version_id": version_id, "version_no": next_version, "file_url": file_url}


@router.get("")
def list_manuals(username: str = Depends(get_current_user)):
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, title, created_at FROM manuals ORDER BY id DESC")).mappings().all()
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
