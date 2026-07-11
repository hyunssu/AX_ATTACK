import os
import uuid
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import text

from auth.service import get_current_user
from db import engine
from manuals import jobs
from manuals.classification import classify_sections, reclassify_section_strong
from manuals.indexing import index_document, index_section
from manuals.splitting import split_into_major_sections
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


class ConfirmSectionInput(BaseModel):
    title: str
    content: str
    category: Literal["여신", "수신", "외환", "자금", "카드", "고객", "기타"]
    include: bool = True


class ConfirmSectionsRequest(BaseModel):
    source_document_id: int
    sections: list[ConfirmSectionInput]


@router.post("/analyze")
async def analyze_manual(
    file: UploadFile = File(...),
    username: str = Depends(get_current_user),
):
    _validate_extension(file.filename)
    file_bytes = await file.read()
    source_type = "pdf" if file.filename.lower().endswith(".pdf") else "md"

    file_url = upload_file(file_bytes, file.filename, file.content_type)
    tmp_path = _save_temp_file(file_bytes, file.filename)
    try:
        sections = split_into_major_sections(tmp_path)
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="파일 인코딩을 읽을 수 없습니다. UTF-8 텍스트 파일인지 확인해 주세요.")
    finally:
        os.remove(tmp_path)

    classified = classify_sections(sections)

    with engine.begin() as conn:
        source_document_id = conn.execute(
            text("""
                INSERT INTO source_documents (file_name, file_url, source_type, uploaded_by)
                VALUES (:file_name, :file_url, :source_type, :uploaded_by)
                RETURNING id
            """),
            {"file_name": file.filename, "file_url": file_url, "source_type": source_type, "uploaded_by": username}
        ).scalar_one()

    return {
        "source_document_id": source_document_id,
        "source_type": source_type,
        "sections": classified,
        "section_count": len(classified),
    }


class ReclassifySectionRequest(BaseModel):
    title: str
    content: str


@router.post("/reclassify-section")
async def reclassify_section(
    req: ReclassifySectionRequest,
    username: str = Depends(get_current_user),
):
    category, needs_review = reclassify_section_strong(req.title, req.content)
    return {"category": category, "needs_review": needs_review}


@router.post("/confirm")
async def confirm_manual_sections(
    req: ConfirmSectionsRequest,
    background_tasks: BackgroundTasks,
    username: str = Depends(get_current_user),
):
    with engine.begin() as conn:
        source = conn.execute(
            text("SELECT file_name, file_url FROM source_documents WHERE id = :id"),
            {"id": req.source_document_id}
        ).mappings().first()
    if not source:
        raise HTTPException(status_code=404, detail="원본 문서를 찾을 수 없습니다.")

    included = [s for s in req.sections if s.include]
    if not included:
        raise HTTPException(status_code=400, detail="포함할 섹션이 하나도 없습니다.")

    created = []
    with engine.begin() as conn:
        for section in included:
            manual_id = conn.execute(
                text("""
                    INSERT INTO manuals (title, source_document_id, category)
                    VALUES (:title, :source_document_id, :category)
                    RETURNING id
                """),
                {"title": section.title, "source_document_id": req.source_document_id, "category": section.category}
            ).scalar_one()
            version_id = conn.execute(
                text("""
                    INSERT INTO manual_versions (manual_id, version_no, file_name, file_url)
                    VALUES (:manual_id, 1, :file_name, :file_url)
                    RETURNING id
                """),
                {"manual_id": manual_id, "file_name": source["file_name"], "file_url": source["file_url"]}
            ).scalar_one()
            created.append((manual_id, version_id))

    # jobs.create_job() opens its own transaction, so it must run after the block above
    # commits — otherwise it can't see the manuals/manual_versions rows just inserted.
    results = []
    for section, (manual_id, version_id) in zip(included, created):
        job_id = jobs.create_job(manual_id, version_id)
        results.append({"manual_id": manual_id, "version_id": version_id, "job_id": job_id, "title": section.title})

    for section, result in zip(included, results):
        background_tasks.add_task(
            index_section, section.title, section.content, result["manual_id"], result["version_id"], result["job_id"]
        )

    return {"results": results}


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
