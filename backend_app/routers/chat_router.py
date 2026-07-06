import json
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

import dify_client
import rag
from auth import get_current_user
from db import engine

router = APIRouter(prefix="/api/chat", tags=["chat"])


class CreateRoomRequest(BaseModel):
    engine: Literal["langchain", "dify"] = "langchain"
    manual_id: Optional[int] = None


class SendMessageRequest(BaseModel):
    input_message: str


def _row_to_room(row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "engine": row["engine"],
        "manual_id": row["manual_id"],
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
        "created_at": row["created_at"].isoformat(),
    }


@router.post("/rooms")
def create_room(req: CreateRoomRequest, username: str = Depends(get_current_user)):
    with engine.begin() as conn:
        row = conn.execute(
            text("""
                INSERT INTO chat_rooms (username, engine, manual_id)
                VALUES (:username, :engine, :manual_id)
                RETURNING id, title, engine, manual_id, created_at
            """),
            {"username": username, "engine": req.engine, "manual_id": req.manual_id}
        ).mappings().one()
    return _row_to_room(row)


@router.get("/rooms")
def list_rooms(username: str = Depends(get_current_user)):
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT id, title, engine, manual_id, created_at
                FROM chat_rooms WHERE username = :username ORDER BY id DESC
            """),
            {"username": username}
        ).mappings().all()
    return [_row_to_room(r) for r in rows]


def _get_room(room_id: int, username: str):
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id, title, engine, manual_id, created_at FROM chat_rooms WHERE id = :id AND username = :username"),
            {"id": room_id, "username": username}
        ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="채팅방을 찾을 수 없습니다.")
    return row


@router.delete("/rooms/{room_id}")
def delete_room(room_id: int, username: str = Depends(get_current_user)):
    _get_room(room_id, username)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM chat_rooms WHERE id = :id"), {"id": room_id})
    return {"deleted": True}


@router.get("/rooms/{room_id}/messages")
def list_messages(room_id: int, username: str = Depends(get_current_user)):
    _get_room(room_id, username)
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT id, role, text, type, options, trace, created_at
                FROM chat_messages WHERE room_id = :room_id ORDER BY id ASC
            """),
            {"room_id": room_id}
        ).mappings().all()
    return [_row_to_message(r) for r in rows]


@router.post("/rooms/{room_id}/messages")
def send_message(room_id: int, req: SendMessageRequest, username: str = Depends(get_current_user)):
    room = _get_room(room_id, username)

    with engine.begin() as conn:
        history_rows = conn.execute(
            text("SELECT role, text FROM chat_messages WHERE room_id = :room_id ORDER BY id ASC"),
            {"room_id": room_id}
        ).mappings().all()
        history = [{"role": r["role"], "text": r["text"]} for r in history_rows]

        conn.execute(
            text("INSERT INTO chat_messages (room_id, role, text) VALUES (:room_id, 'user', :text)"),
            {"room_id": room_id, "text": req.input_message}
        )

        if room["title"] == "새 대화":
            new_title = req.input_message[:30]
            conn.execute(
                text("UPDATE chat_rooms SET title = :title WHERE id = :id"),
                {"title": new_title, "id": room_id}
            )

    try:
        if room["engine"] == "dify":
            result = dify_client.answer_question(req.input_message, room["manual_id"], history, username)
        else:
            result = rag.answer_question(req.input_message, room["manual_id"], history)
    except Exception as e:
        result = {"type": "answer", "text": f"LLM 호출 에러: {str(e)}", "options": []}

    trace = result.get("trace")
    with engine.begin() as conn:
        ai_row = conn.execute(
            text("""
                INSERT INTO chat_messages (room_id, role, text, type, options, trace)
                VALUES (:room_id, 'ai', :text, :type, :options, :trace)
                RETURNING id, role, text, type, options, trace, created_at
            """),
            {
                "room_id": room_id,
                "text": result["text"],
                "type": result["type"],
                "options": json.dumps(result["options"]),
                "trace": json.dumps(trace) if trace is not None else None,
            }
        ).mappings().one()

    return _row_to_message(ai_row)
