import json
import os
import re
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel
from sqlalchemy import text

from auth.service import get_current_user
from db import engine
from db_tables import MANUALS, MANUAL_PARENT_CHUNKS, MANUAL_VERSIONS, MANUAL_CHUNK_TABLE_VERSION
from llm_clients import call_llm, strong_llm
from manuals import jobs
from manuals.content import active_manual_sql, active_version_sql, public_version_content, read_version_chunks, stored_version_content
from manuals.indexing import index_document, index_section
from manuals.permissions import require_manual_edit
from storage import download_file

router = APIRouter(prefix="/api/manuals", tags=["drafts"])


def _extract_plain_text(blocks: list) -> str:
    if MANUAL_CHUNK_TABLE_VERSION == "v2":
        from manuals.structured_content import blocks_to_markdown
        return blocks_to_markdown(blocks)
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


def _run_deploy_editor(manual_id: int, version_id: int, job_id: int, plain_text: str, title: str):
    try:
        if MANUAL_CHUNK_TABLE_VERSION == "v1":
            with engine.begin() as conn:
                conn.execute(
                    text(f"DELETE FROM {MANUAL_PARENT_CHUNKS} WHERE version_id = :vid"),
                    {"vid": version_id},
                )
        index_section(title, plain_text, manual_id, version_id, job_id)
    except Exception as e:
        jobs.mark_job_failed(job_id, str(e))
        raise


def _run_deploy_file(manual_id: int, version_id: int, job_id: int, storage_path: str, file_name: str):
    tmp_path = f"/tmp/{uuid.uuid4()}_{file_name}"
    try:
        file_bytes = download_file(storage_path)
        with open(tmp_path, "wb") as f:
            f.write(file_bytes)
        if MANUAL_CHUNK_TABLE_VERSION == "v1":
            with engine.begin() as conn:
                conn.execute(
                    text(f"DELETE FROM {MANUAL_PARENT_CHUNKS} WHERE version_id = :vid"),
                    {"vid": version_id},
                )
        index_document(tmp_path, manual_id, version_id, job_id)
    except Exception as e:
        jobs.mark_job_failed(job_id, str(e))
        raise
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


class VerifyRequest(BaseModel):
    content: list[Any]
    original_content: list[Any] | None = None


@router.post("/{manual_id}/verify")
def verify_draft(manual_id: int, req: VerifyRequest, username: str = Depends(get_current_user)):
    import difflib

    require_manual_edit(username, manual_id)
    with engine.connect() as conn:
        manual = conn.execute(
            text(f"SELECT id, title FROM {MANUALS} WHERE id = :id AND deleted_at IS NULL"), {"id": manual_id}
        ).mappings().first()
        if not manual:
            raise HTTPException(status_code=404, detail="Manual not found")

    plain_text = _extract_plain_text(req.content)
    if not plain_text.strip():
        raise HTTPException(status_code=400, detail="검증할 내용이 없습니다.")

    added_section = ""
    if req.original_content is not None:
        original_text = _extract_plain_text(req.original_content)
        diff = list(difflib.unified_diff(
            original_text.splitlines(), plain_text.splitlines(), lineterm="", n=0
        ))
        added_lines = [line[1:] for line in diff if line.startswith("+") and not line.startswith("+++")]
        added_text = "\n".join(ln for ln in added_lines if ln.strip())
        if added_text:
            added_section = f"\n\n[이번 편집에서 추가/수정된 내용]\n{added_text}"

    # DB 등록 용어 로드 및 텍스트 매칭
    with engine.connect() as conn:
        all_terms = conn.execute(
            text("SELECT term, aliases, description FROM manual_terms")
        ).mappings().all()

    text_lower = plain_text.lower()
    matched_terms = []
    for t in all_terms:
        keys = [t["term"]] + list(t["aliases"] or [])
        if any(k.lower() in text_lower for k in keys):
            matched_terms.append({"term": t["term"], "description": t["description"]})

    known_terms_block = ""
    if matched_terms:
        lines = "\n".join(f"- {t['term']}: {t['description']}" for t in matched_terms)
        known_terms_block = f"\n\n[등록된 내부 용어 - 아래 용어는 정상적인 내부 시스템/용어이므로 오류로 판단하지 마세요]\n{lines}"

    system_prompt = f"""당신은 금융 업무 매뉴얼 전문 검토자입니다.
주어진 매뉴얼 내용을 다음 기준으로 검토하고 JSON 형식으로만 응답하세요.{known_terms_block}{added_section}

검토 기준:
1. 완성도: 내용이 충분히 구체적이고 완결되어 있는가?
2. 명확성: 용어와 절차가 명확하게 설명되어 있는가?
3. 일관성: 내용 간 논리적 일관성이 있는가?
4. 준수성: 금융 업무 매뉴얼로서 필요한 항목이 포함되어 있는가?

added_review 규칙:
- [이번 편집에서 추가/수정된 내용]이 제공된 경우, 해당 내용이 기존 매뉴얼과 일관성이 있는지, 금융 업무 절차에 적합한지 1~2문장으로 검토하세요.
- 추가된 내용이 없거나 제공되지 않은 경우 null로 설정하세요.

반드시 다음 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
{{
  "score": <0-100 사이 정수>,
  "summary": "<2-3줄 전체 평가 요약>",
  "strengths": ["<강점1>", "<강점2>"],
  "issues": ["<문제점1>", "<문제점2>"],
  "suggestions": ["<개선제안1>", "<개선제안2>"],
  "added_review": "<이번 편집 추가/수정 내용 검토 또는 null>"
}}"""

    user_prompt = f"""매뉴얼 제목: {manual['title']}

매뉴얼 내용:
{plain_text}"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    response = call_llm(strong_llm, messages)
    raw = response.content.strip()

    json_match = re.search(r'\{[\s\S]*\}', raw)
    if not json_match:
        raise HTTPException(status_code=500, detail="AI 응답을 파싱할 수 없습니다.")

    try:
        result = json.loads(json_match.group())
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="AI 응답 JSON 파싱 실패")

    return result


@router.get("/{manual_id}/draft")
def get_draft(manual_id: int, username: str = Depends(get_current_user)):
    with engine.connect() as conn:
        manual = conn.execute(
            text(f"SELECT id, title FROM {MANUALS} m WHERE id = :id AND deleted_at IS NULL AND {active_manual_sql('m')}"), {"id": manual_id}
        ).mappings().first()
        if not manual:
            raise HTTPException(status_code=404, detail="Manual not found")

        draft_version = conn.execute(
            text(f"""
                SELECT id, content_json, updated_at, index_step, error_message, source_type, storage_path, file_name
                FROM {MANUAL_VERSIONS} v
                WHERE manual_id = :mid
                  AND {active_version_sql('v')}
                  AND {"TRUE" if MANUAL_CHUNK_TABLE_VERSION == "v2" else "(index_step IN ('draft', 'done') OR error_message IS NOT NULL)"}
                ORDER BY version_no DESC
                LIMIT 1
            """),
            {"mid": manual_id},
        ).mappings().first()

        if draft_version and draft_version["content_json"] is not None:
            content = public_version_content(draft_version["content_json"])
            response = {
                "content": content,
                "status": "draft" if draft_version["error_message"] else draft_version["index_step"],
                "updated_at": draft_version["updated_at"].isoformat() if draft_version["updated_at"] else None,
                "from_chunks": False,
            }
            if (MANUAL_CHUNK_TABLE_VERSION == "v2"
                    and (draft_version["source_type"] == "md" or (draft_version["file_name"] or "").lower().endswith(".md"))
                    and all(not block.get("id") for block in content if isinstance(block, dict))):
                response["raw_markdown"] = _extract_plain_text(content)
            return response

        if (MANUAL_CHUNK_TABLE_VERSION == "v2" and draft_version and draft_version["storage_path"]
                and (draft_version["file_name"] or "").lower().endswith(".md")):
            source = download_file(draft_version["storage_path"]).decode("utf-8-sig")
            return {"content": [], "raw_markdown": source, "status": draft_version["index_step"], "from_chunks": False}

        published = conn.execute(text(f"""
            SELECT id FROM {MANUAL_VERSIONS} v WHERE manual_id = :mid AND index_step = 'done'
              AND {active_version_sql('v')}
            ORDER BY version_no DESC LIMIT 1
        """), {"mid": manual_id}).first()
        chunks = read_version_chunks(conn, manual_id, published[0], limit=300) if published else []

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
    require_manual_edit(username, manual_id)
    with engine.begin() as conn:
        lock_row = conn.execute(
            text(f"SELECT locked_by FROM {MANUALS} WHERE id = :id AND deleted_at IS NULL FOR UPDATE"),
            {"id": manual_id},
        ).first()
        if not lock_row:
            raise HTTPException(status_code=404, detail="매뉴얼을 찾을 수 없습니다.")
        if lock_row[0] and lock_row[0] != username:
            raise HTTPException(status_code=403, detail=f"현재 {lock_row[0]}님이 편집 중입니다. 잠금이 해제된 후 수정할 수 있습니다.")
        latest = conn.execute(
            text(f"""
                SELECT id, version_no, index_step, error_message,
                       file_name, file_url, storage_path, source_type
                FROM {MANUAL_VERSIONS} v
                WHERE manual_id = :mid AND {active_version_sql('v')}
                ORDER BY version_no DESC LIMIT 1
            """),
            {"mid": manual_id},
        ).mappings().first()
        content = json.dumps(stored_version_content(req.content))
        if latest and latest["index_step"] != "done":
            if latest["index_step"] != "draft" and not latest["error_message"]:
                raise HTTPException(status_code=409, detail="운영반영 처리 중에는 내용을 수정할 수 없습니다. 완료 후 다시 시도해 주세요.")
            conn.execute(
                text(f"""
                    UPDATE {MANUAL_VERSIONS}
                    SET content_json = CAST(:content AS jsonb), index_step = 'draft',
                        error_message = NULL, updated_at = now()
                    WHERE id = :id
                """),
                {"id": latest["id"], "content": content},
            )
        else:
            # Keep the published version intact and serialize draft creation on the manual row.
            next_version = conn.execute(
                text(f"SELECT COALESCE(MAX(version_no), 0) + 1 FROM {MANUAL_VERSIONS} WHERE manual_id = :mid"),
                {"mid": manual_id},
            ).scalar_one()
            conn.execute(
                text(f"""
                    INSERT INTO {MANUAL_VERSIONS}
                        (manual_id, version_no, file_name, file_url, storage_path,
                         source_type, index_step, content_json)
                    VALUES (:mid, :version, :file_name, :file_url, :storage_path,
                            :source_type, 'draft', CAST(:content AS jsonb))
                """),
                {
                    "mid": manual_id,
                    "version": next_version,
                    "file_name": latest["file_name"] if latest else "",
                    "file_url": latest["file_url"] if latest else "",
                    "storage_path": latest["storage_path"] if latest else None,
                    "source_type": latest["source_type"] if latest else "editor",
                    "content": content,
                },
            )
    return {"ok": True}


@router.post("/{manual_id}/deploy")
def deploy_draft(manual_id: int, background_tasks: BackgroundTasks, username: str = Depends(get_current_user)):
    require_manual_edit(username, manual_id)
    with engine.begin() as conn:
        manual = conn.execute(
            text(f"SELECT id, title, locked_by FROM {MANUALS} WHERE id = :id AND deleted_at IS NULL FOR UPDATE"), {"id": manual_id}
        ).mappings().first()
        if not manual:
            raise HTTPException(status_code=404, detail="Manual not found")
        if manual["locked_by"] and manual["locked_by"] != username:
            raise HTTPException(status_code=403, detail="다른 사용자가 편집 중인 매뉴얼입니다.")

        draft_version = conn.execute(
            text(f"""
                SELECT id, content_json, storage_path, file_name, index_step, error_message
                FROM {MANUAL_VERSIONS} v WHERE manual_id = :mid AND {active_version_sql('v')}
                ORDER BY version_no DESC
                LIMIT 1
            """),
            {"mid": manual_id},
        ).mappings().first()
        if not draft_version or draft_version["index_step"] == "done":
            raise HTTPException(status_code=404, detail="배포할 드래프트가 없습니다. 수정 내용을 먼저 저장해 주세요.")
        if draft_version["index_step"] != "draft" and not draft_version["error_message"]:
            raise HTTPException(status_code=409, detail="이미 운영반영 처리 중입니다.")
        plain_text = _extract_plain_text(draft_version["content_json"]) if draft_version["content_json"] else ""
        if draft_version["content_json"] and not plain_text.strip():
            raise HTTPException(status_code=400, detail="드래프트 내용이 비어 있습니다.")
        if not plain_text and not draft_version["storage_path"]:
            raise HTTPException(status_code=400, detail="배포할 내용이 없습니다. 에디터 작성 또는 파일 업로드가 필요합니다.")
        version_id = draft_version["id"]
        job_id = jobs.create_job(manual_id, version_id)
        conn.execute(
            text(f"UPDATE {MANUAL_VERSIONS} SET index_step = 'converting', error_message = NULL, updated_at = now() WHERE id = :id"),
            {"id": version_id},
        )

    if draft_version["content_json"]:
        background_tasks.add_task(
            _run_deploy_editor,
            manual_id=manual_id,
            version_id=version_id,
            job_id=job_id,
            plain_text=plain_text,
            title=manual["title"],
        )
    elif draft_version["storage_path"]:
        background_tasks.add_task(
            _run_deploy_file,
            manual_id=manual_id,
            version_id=version_id,
            job_id=job_id,
            storage_path=draft_version["storage_path"],
            file_name=draft_version["file_name"],
        )
    return {"job_id": job_id}
