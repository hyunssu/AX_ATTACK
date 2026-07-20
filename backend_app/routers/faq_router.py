from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from langchain_openai import OpenAIEmbeddings
from pydantic import BaseModel, Field
from sqlalchemy import text

from auth import get_current_user, get_user_role
from config import OPENAI_EMBEDDING_MODEL
from db import engine
from db_tables import CHAT_MESSAGES, FAQ_HISTORY


router = APIRouter(prefix="/api/faqs", tags=["faqs"])
embeddings = OpenAIEmbeddings(model=OPENAI_EMBEDDING_MODEL)


class FAQEditRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    answer: str = Field(min_length=1, max_length=10000)
    keywords: list[str] = Field(default_factory=list, max_length=20)


def _require_reviewer(username: str = Depends(get_current_user)) -> str:
    if get_user_role(username) not in {"Admin", "Developer"}:
        raise HTTPException(status_code=403, detail="FAQ 검수 권한이 없습니다.")
    return username


def _embedding_to_sql(vector: list[float]) -> str:
    return "[" + ",".join(str(value) for value in vector) + "]"


def _serialize_faq(row) -> dict:
    result = dict(row)
    for key in ("created_at", "updated_at", "approved_at", "rejected_at"):
        if result.get(key):
            result[key] = result[key].isoformat()
    result["keywords"] = result.get("keywords") or []
    return result


FAQ_COLUMNS = """
    id, source_room_id, username, manual_id, conversation_summary,
    question, answer, keywords, status, faq_type, created_at, updated_at,
    approved_by, approved_at, rejected_by, rejected_at
"""


@router.get("")
def list_faqs(
    status: Literal["pending", "approved", "rejected"] = "pending",
    query: str = Query(default="", max_length=200),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _username: str = Depends(_require_reviewer),
):
    search_filter = """
        AND (question ILIKE :query OR answer ILIKE :query OR :query = '')
    """
    params = {"status": status, "query": f"%{query.strip()}%" if query.strip() else "", "limit": limit, "offset": offset}
    with engine.connect() as conn:
        total = conn.execute(
            text(f"SELECT COUNT(*) FROM {FAQ_HISTORY} WHERE status = :status {search_filter}"),
            params,
        ).scalar_one()
        rows = conn.execute(
            text(f"""
                SELECT {FAQ_COLUMNS}
                FROM {FAQ_HISTORY}
                WHERE status = :status {search_filter}
                ORDER BY created_at DESC, id DESC
                LIMIT :limit OFFSET :offset
            """),
            params,
        ).mappings().all()
    return {"items": [_serialize_faq(row) for row in rows], "total": total}


@router.get("/{faq_id}")
def get_faq(faq_id: int, _username: str = Depends(_require_reviewer)):
    with engine.connect() as conn:
        row = conn.execute(
            text(f"SELECT {FAQ_COLUMNS} FROM {FAQ_HISTORY} WHERE id = :faq_id"),
            {"faq_id": faq_id},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="FAQ를 찾을 수 없습니다.")
        messages = []
        if row["source_room_id"]:
            messages = conn.execute(
                text(f"""
                    SELECT id, role, text, created_at
                    FROM {CHAT_MESSAGES}
                    WHERE room_id = :room_id
                    ORDER BY id
                """),
                {"room_id": row["source_room_id"]},
            ).mappings().all()

    result = _serialize_faq(row)
    result["source_messages"] = [
        {
            "id": message["id"],
            "role": message["role"],
            "text": message["text"],
            "created_at": message["created_at"].isoformat(),
        }
        for message in messages
    ]
    return result


@router.post("/{faq_id}/approve")
def approve_faq(faq_id: int, req: FAQEditRequest, username: str = Depends(_require_reviewer)):
    with engine.connect() as conn:
        faq_row = conn.execute(
            text(f"SELECT faq_type FROM {FAQ_HISTORY} WHERE id = :faq_id"),
            {"faq_id": faq_id},
        ).mappings().first()
    if not faq_row:
        raise HTTPException(status_code=404, detail="FAQ를 찾을 수 없습니다.")

    embedding_value = None
    if faq_row["faq_type"] != "screen_owner_change":
        vector = embeddings.embed_query(req.question.strip())
        embedding_value = _embedding_to_sql(vector)
    keywords = list(dict.fromkeys(keyword.strip() for keyword in req.keywords if keyword.strip()))
    with engine.begin() as conn:
        row = conn.execute(
            text(f"""
                UPDATE {FAQ_HISTORY}
                SET question = :question,
                    answer = :answer,
                    keywords = :keywords,
                    status = 'approved',
                    embedding = CAST(:embedding AS vector),
                    approved_by = :username,
                    approved_at = now(),
                    rejected_by = NULL,
                    rejected_at = NULL,
                    updated_at = now()
                WHERE id = :faq_id
                RETURNING {FAQ_COLUMNS}
            """),
            {
                "faq_id": faq_id,
                "username": username,
                "question": req.question.strip(),
                "answer": req.answer.strip(),
                "keywords": keywords,
                "embedding": embedding_value,
            },
        ).mappings().one()
    return _serialize_faq(row)


@router.post("/{faq_id}/reject")
def reject_faq(faq_id: int, username: str = Depends(_require_reviewer)):
    with engine.begin() as conn:
        row = conn.execute(
            text(f"""
                UPDATE {FAQ_HISTORY}
                SET status = 'rejected',
                    embedding = NULL,
                    approved_by = NULL,
                    approved_at = NULL,
                    rejected_by = :username,
                    rejected_at = now(),
                    updated_at = now()
                WHERE id = :faq_id
                RETURNING {FAQ_COLUMNS}
            """),
            {"faq_id": faq_id, "username": username},
        ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="FAQ를 찾을 수 없습니다.")
    return _serialize_faq(row)
