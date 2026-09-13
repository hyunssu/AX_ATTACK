import json
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from langchain_core.documents import Document
from pydantic import BaseModel
from sqlalchemy import text

from auth.service import get_current_user
from db import engine
from manuals import jobs
from manuals.indexing import chunk_document, embed_and_store

router = APIRouter(prefix="/api/manuals", tags=["drafts"])


def _extract_plain_text(blocks: list) -> str:
    lines = []
    for block in blocks:
        for item in block.get("content", []):
            if isinstance(item, dict) and item.get("type") == "text":
                t = item.get("text", "").strip()
                if t:
                    lines.append(t)
        for child in block.get("children", []):
            child_text = _extract_plain_text([child])
            if child_text:
                lines.append(child_text)
    return "\n\n".join(lines)


def _chunks_to_markdown(chunks: list[dict]) -> str:
    """청크 목록을 마크다운 문자열로 합친다. 프론트엔드에서 BlockNote로 파싱한다."""
    parts = []
    prev_section = None
    for chunk in chunks:
        section = (chunk.get("section_title") or "").strip()
        content = (chunk.get("content") or "").strip()
        if section and section != prev_section:
            parts.append(f"## {section}")
            prev_section = section
        if content:
            parts.append(content)
    return "\n\n".join(parts)


def _run_deploy(manual_id: int, version_id: int, job_id: int, plain_text: str, title: str):
    try:
        jobs.update_job_step(job_id, "chunking")
        docs = [Document(page_content=plain_text, metadata={"section_title": title})]
        chunks = chunk_document(docs)

        jobs.update_job_step(job_id, "embedding")
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM manual_chunks_khs WHERE version_id = :vid"), {"vid": version_id})
        embed_and_store(chunks, manual_id, version_id)

        jobs.update_job_step(job_id, "done")
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE manual_drafts SET status = 'deployed', updated_at = now() WHERE manual_id = :mid"),
                {"mid": manual_id},
            )
    except Exception as e:
        jobs.mark_job_failed(job_id, str(e))
        raise


@router.get("/{manual_id}/draft")
def get_draft(manual_id: int, username: str = Depends(get_current_user)):
    with engine.connect() as conn:
        manual = conn.execute(
            text("SELECT id, title FROM manuals WHERE id = :id"), {"id": manual_id}
        ).mappings().first()
        if not manual:
            raise HTTPException(status_code=404, detail="Manual not found")

        draft = conn.execute(
            text("SELECT content, status, updated_at FROM manual_drafts WHERE manual_id = :mid"),
            {"mid": manual_id},
        ).mappings().first()
        if draft:
            return {
                "content": draft["content"],
                "status": draft["status"],
                "updated_at": draft["updated_at"].isoformat() if draft["updated_at"] else None,
                "from_chunks": False,
            }

        chunks = conn.execute(
            text("""
                SELECT mc.section_title, mc.content
                FROM manual_chunks_khs mc
                JOIN manual_versions mv ON mv.id = mc.version_id
                WHERE mv.manual_id = :mid
                ORDER BY mv.version_no DESC, mc.chunk_index
                LIMIT 300
            """),
            {"mid": manual_id},
        ).mappings().all()

    return {
        "content": [],
        "raw_markdown": _chunks_to_markdown([dict(c) for c in chunks]),
        "status": "no_draft",
        "from_chunks": True,
    }


class SaveDraftRequest(BaseModel):
    content: list[Any]


@router.put("/{manual_id}/draft")
def save_draft(manual_id: int, req: SaveDraftRequest, username: str = Depends(get_current_user)):
    with engine.begin() as conn:
        if not conn.execute(text("SELECT id FROM manuals WHERE id = :id"), {"id": manual_id}).first():
            raise HTTPException(status_code=404, detail="Manual not found")
        conn.execute(
            text("""
                INSERT INTO manual_drafts (manual_id, content, edited_by, status, updated_at)
                VALUES (:mid, :content::jsonb, :user, 'draft', now())
                ON CONFLICT (manual_id) DO UPDATE SET
                    content = EXCLUDED.content,
                    edited_by = EXCLUDED.edited_by,
                    status = 'draft',
                    updated_at = now()
            """),
            {"mid": manual_id, "content": json.dumps(req.content), "user": username},
        )
    return {"ok": True}


@router.post("/{manual_id}/deploy")
def deploy_draft(manual_id: int, background_tasks: BackgroundTasks, username: str = Depends(get_current_user)):
    with engine.connect() as conn:
        manual = conn.execute(
            text("SELECT id, title FROM manuals WHERE id = :id"), {"id": manual_id}
        ).mappings().first()
        if not manual:
            raise HTTPException(status_code=404, detail="Manual not found")

        draft = conn.execute(
            text("SELECT content FROM manual_drafts WHERE manual_id = :mid"), {"mid": manual_id}
        ).mappings().first()
        if not draft:
            raise HTTPException(status_code=404, detail="No draft to deploy")

        version = conn.execute(
            text("SELECT id FROM manual_versions WHERE manual_id = :mid ORDER BY version_no DESC LIMIT 1"),
            {"mid": manual_id},
        ).mappings().first()
        if not version:
            raise HTTPException(status_code=404, detail="No version found")

    plain_text = _extract_plain_text(draft["content"])
    if not plain_text.strip():
        raise HTTPException(status_code=400, detail="Draft content is empty")

    job_id = jobs.create_job(manual_id, version["id"])
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE manual_drafts SET status = 'deploying', updated_at = now() WHERE manual_id = :mid"),
            {"mid": manual_id},
        )

    background_tasks.add_task(
        _run_deploy,
        manual_id=manual_id,
        version_id=version["id"],
        job_id=job_id,
        plain_text=plain_text,
        title=manual["title"],
    )
    return {"job_id": job_id}
