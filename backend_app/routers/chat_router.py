import json
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

import faq
import knowledge_router
import screen_owners
from auth import get_current_user
from db import engine
from db_tables import CHAT_MESSAGES, CHAT_ROOMS, FAQ_HISTORY

router = APIRouter(prefix="/api/chat", tags=["chat"])


class CreateRoomRequest(BaseModel):
    engine: Literal["langchain", "langgraph", "dify"] = "langchain"
    manual_id: Optional[int] = None


class SendMessageRequest(BaseModel):
    input_message: str


def _row_to_room(row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "engine": row["engine"],
        "manual_id": row["manual_id"],
        "ended_at": row["ended_at"].isoformat() if row["ended_at"] else None,
        "created_at": row["created_at"].isoformat(),
    }


def _row_to_message(row) -> dict:
    return {
        "id": row["id"],
        "role": row["role"],
        "text": row["text"],
        "type": row["type"],
        "options": row["options"] or [],
        "trace": row["trace"],
        "sources": row["sources"] or [],
        "created_at": row["created_at"].isoformat(),
    }


@router.post("/rooms")
def create_room(req: CreateRoomRequest, username: str = Depends(get_current_user)):
    with engine.begin() as conn:
        row = conn.execute(
            text(f"""
                INSERT INTO {CHAT_ROOMS} (username, engine, manual_id)
                VALUES (:username, :engine, :manual_id)
                RETURNING id, title, engine, manual_id, ended_at, created_at
            """),
            {"username": username, "engine": req.engine, "manual_id": req.manual_id}
        ).mappings().one()
    return _row_to_room(row)


@router.get("/rooms")
def list_rooms(username: str = Depends(get_current_user)):
    with engine.connect() as conn:
        rows = conn.execute(
            text(f"""
                SELECT r.id, r.title, r.engine, r.manual_id, r.ended_at,
                       r.conversation_summary, r.last_summarized_message_id,
                       r.last_summarized_at, r.created_at
                FROM {CHAT_ROOMS} r
                WHERE r.username = :username ORDER BY r.id DESC
            """),
            {"username": username}
        ).mappings().all()
    return [_row_to_room(r) for r in rows]


def _get_room(room_id: int, username: str):
    with engine.connect() as conn:
        row = conn.execute(
            text(f"""
                SELECT r.id, r.title, r.engine, r.manual_id, r.ended_at,
                       r.conversation_summary, r.last_summarized_message_id,
                       r.last_summarized_at, r.created_at
                FROM {CHAT_ROOMS} r
                WHERE r.id = :id AND r.username = :username
            """),
            {"id": room_id, "username": username}
        ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="채팅방을 찾을 수 없습니다.")
    return row


@router.delete("/rooms/{room_id}")
def delete_room(room_id: int, username: str = Depends(get_current_user)):
    _get_room(room_id, username)
    with engine.begin() as conn:
        conn.execute(text(f"DELETE FROM {CHAT_ROOMS} WHERE id = :id"), {"id": room_id})
    return {"deleted": True}


@router.get("/rooms/{room_id}/messages")
def list_messages(room_id: int, username: str = Depends(get_current_user)):
    _get_room(room_id, username)
    with engine.connect() as conn:
        rows = conn.execute(
            text(f"""
                SELECT id, role, text, type, options, trace, sources, created_at
                FROM {CHAT_MESSAGES} WHERE room_id = :room_id ORDER BY id ASC
            """),
            {"room_id": room_id}
        ).mappings().all()
    return [_row_to_message(r) for r in rows]


@router.post("/rooms/{room_id}/messages")
def send_message(room_id: int, req: SendMessageRequest, username: str = Depends(get_current_user)):
    room = _get_room(room_id, username)
    if room["ended_at"] is not None:
        raise HTTPException(status_code=409, detail="이미 종료된 대화입니다.")

    with engine.begin() as conn:
        history_rows = conn.execute(
            text(f"SELECT role, text, type, options FROM {CHAT_MESSAGES} WHERE room_id = :room_id ORDER BY id ASC"),
            {"room_id": room_id}
        ).mappings().all()
        history = [
            {"role": r["role"], "text": r["text"], "type": r["type"], "options": r["options"] or []}
            for r in history_rows
        ]

        conn.execute(
            text(f"INSERT INTO {CHAT_MESSAGES} (room_id, role, text) VALUES (:room_id, 'user', :text)"),
            {"room_id": room_id, "text": req.input_message}
        )

        if room["title"] == "새 대화":
            new_title = req.input_message[:30]
            conn.execute(
                text(f"UPDATE {CHAT_ROOMS} SET title = :title WHERE id = :id"),
                {"title": new_title, "id": room_id}
            )

    try:
        result = screen_owners.answer_screen_owner_request(
            req.input_message,
            room_id=room_id,
            username=username,
            history=history,
        )
        if result is not None:
            pass
        else:
            result = knowledge_router.answer_from_latest_knowledge(
                req.input_message,
                manual_id=room["manual_id"],
                history=history,
                engine_name=room["engine"],
            )
    except Exception as e:
        result = {"type": "answer", "text": f"요청 처리 오류: {str(e)}", "options": [], "sources": []}

    trace = result.get("trace")
    sources = result.get("sources") or []
    with engine.begin() as conn:
        ai_row = conn.execute(
            text(f"""
                INSERT INTO {CHAT_MESSAGES} (room_id, role, text, type, options, trace, sources)
                VALUES (:room_id, 'ai', :text, :type, :options, :trace, :sources)
                RETURNING id, role, text, type, options, trace, sources, created_at
            """),
            {
                "room_id": room_id,
                "text": result["text"],
                "type": result["type"],
                "options": json.dumps(result["options"]),
                "trace": json.dumps(trace) if trace is not None else None,
                "sources": json.dumps(sources),
            }
        ).mappings().one()

    return _row_to_message(ai_row)


def _faq_rows_for_room(room_id: int) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(f"""
                SELECT id, question, answer, keywords, status, conversation_summary, created_at
                FROM {FAQ_HISTORY}
                WHERE source_room_id = :room_id
                ORDER BY id ASC
            """),
            {"room_id": room_id},
        ).mappings().all()
    return [dict(row) for row in rows]


def _faq_response(room_id: int, rows: list[dict], summary: str = "") -> dict:
    return {
        "room_id": room_id,
        "summary": rows[0]["conversation_summary"] if rows else summary,
        "faq_count": len(rows),
        "faqs": [
            {
                "id": row["id"],
                "question": row["question"],
                "answer": row["answer"],
                "keywords": row["keywords"] or [],
                "status": row["status"],
                "created_at": row["created_at"].isoformat(),
            }
            for row in rows
        ],
    }


def _checkpoint_room(room_id: int, username: str) -> dict:
    room = _get_room(room_id, username)
    with engine.connect() as conn:
        rows = conn.execute(
            text(f"SELECT id, role, text FROM {CHAT_MESSAGES} WHERE room_id = :room_id ORDER BY id ASC"),
            {"room_id": room_id},
        ).mappings().all()

    if not rows:
        return {"room_id": room_id, "checkpointed": False, "reason": "no_messages", "faq_count": 0}

    target_message_id = rows[-1]["id"]
    last_summarized_message_id = room["last_summarized_message_id"] or 0
    if target_message_id <= last_summarized_message_id:
        return {
            "room_id": room_id,
            "checkpointed": False,
            "reason": "already_summarized",
            "faq_count": len(_faq_rows_for_room(room_id)),
        }

    new_rows = [row for row in rows if row["id"] > last_summarized_message_id]
    new_roles = {row["role"] for row in new_rows}
    if not {"user", "ai"}.issubset(new_roles):
        return {"room_id": room_id, "checkpointed": False, "reason": "incomplete_exchange", "faq_count": 0}

    messages = [{"role": row["role"], "text": row["text"]} for row in rows]

    try:
        result = faq.summarize_conversation(messages)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"FAQ 요약 중 오류가 발생했습니다: {exc}") from exc

    with engine.begin() as conn:
        for item in result.faqs:
            conn.execute(
                text(f"""
                    INSERT INTO {FAQ_HISTORY}
                        (source_room_id, username, manual_id, conversation_summary,
                         question, answer, keywords, status, faq_type)
                    VALUES
                        (:source_room_id, :username, :manual_id, :summary,
                         :question, :answer, :keywords, 'pending', 'conversation')
                    ON CONFLICT DO NOTHING
                """),
                {
                    "source_room_id": room_id,
                    "username": username,
                    "manual_id": room["manual_id"],
                    "summary": result.summary,
                    "question": item.question,
                    "answer": item.answer,
                    "keywords": item.keywords,
                },
            )
        conn.execute(
            text(f"""
                UPDATE {CHAT_ROOMS}
                SET conversation_summary = :summary,
                    last_summarized_message_id = :target_message_id,
                    last_summarized_at = now()
                WHERE id = :room_id
                  AND COALESCE(last_summarized_message_id, 0) < :target_message_id
            """),
            {"room_id": room_id, "summary": result.summary, "target_message_id": target_message_id},
        )

    response = _faq_response(room_id, _faq_rows_for_room(room_id), result.summary)
    response.update({"checkpointed": True, "last_summarized_message_id": target_message_id})
    return response


@router.post("/rooms/{room_id}/checkpoint")
def checkpoint_room(room_id: int, username: str = Depends(get_current_user)):
    return _checkpoint_room(room_id, username)


def _checkpoint_room_ids(room_ids: list[int], username: str) -> dict:
    results = []
    for room_id in room_ids:
        try:
            results.append(_checkpoint_room(room_id, username))
        except HTTPException as exc:
            results.append({"room_id": room_id, "checkpointed": False, "reason": exc.detail})
        except Exception as exc:
            results.append({"room_id": room_id, "checkpointed": False, "reason": str(exc)})
    return {
        "checked_room_count": len(room_ids),
        "checkpointed_room_count": sum(1 for result in results if result.get("checkpointed")),
        "results": results,
    }


@router.post("/checkpoints/stale")
def checkpoint_stale_rooms(username: str = Depends(get_current_user)):
    with engine.connect() as conn:
        room_ids = conn.execute(
            text(f"""
                SELECT r.id
                FROM {CHAT_ROOMS} r
                JOIN LATERAL (
                    SELECT MAX(m.id) AS last_message_id,
                           MAX(m.created_at) AS last_message_at
                    FROM {CHAT_MESSAGES} m
                    WHERE m.room_id = r.id
                ) latest ON true
                WHERE r.username = :username
                  AND r.ended_at IS NULL
                  AND latest.last_message_id > COALESCE(r.last_summarized_message_id, 0)
                  AND latest.last_message_at <= now() - interval '30 minutes'
                ORDER BY r.id
            """),
            {"username": username},
        ).scalars().all()
    return _checkpoint_room_ids(list(room_ids), username)


@router.post("/checkpoints/all")
def checkpoint_all_rooms(username: str = Depends(get_current_user)):
    with engine.connect() as conn:
        room_ids = conn.execute(
            text(f"""
                SELECT r.id
                FROM {CHAT_ROOMS} r
                WHERE r.username = :username
                  AND r.ended_at IS NULL
                  AND EXISTS (
                      SELECT 1
                      FROM {CHAT_MESSAGES} m
                      WHERE m.room_id = r.id
                        AND m.id > COALESCE(r.last_summarized_message_id, 0)
                  )
                ORDER BY r.id
            """),
            {"username": username},
        ).scalars().all()
    return _checkpoint_room_ids(list(room_ids), username)
