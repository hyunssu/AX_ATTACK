import json
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from langchain_openai import OpenAIEmbeddings
from pydantic import BaseModel, Field
from sqlalchemy import text

from faq import intake as faq_intake
from faq import mailer as faq_mailer
from auth.service import get_current_user, get_user_language, get_user_role
from config import OPENAI_EMBEDDING_MODEL
from db import engine
from db_tables import (
    CHAT_MESSAGES,
    FAQ_REQUEST_MESSAGES,
    FAQ_REQUESTS,
    USERS,
)


router = APIRouter(prefix="/api/faqs", tags=["faqs"])
embeddings = OpenAIEmbeddings(model=OPENAI_EMBEDDING_MODEL)


class FAQApprovalRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    answer: str = Field(min_length=1, max_length=10000)
    keywords: list[str] = Field(default_factory=list, max_length=20)
    knowledge_search_allowed: bool = True


class FAQRejectRequest(BaseModel):
    reason: str = Field(min_length=2, max_length=2000)


class FAQMessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10000)
    message_type: Literal["answer", "additional_question", "note"] = "answer"


class FAQReassignRequest(BaseModel):
    assignee_username: str = Field(min_length=1, max_length=100)


def _require_reviewer(username: str = Depends(get_current_user)) -> str:
    if get_user_role(username) not in {"Admin", "Developer"}:
        raise HTTPException(status_code=403, detail="FAQ 검수 권한이 없습니다.")
    return username


def _embedding_to_sql(vector: list[float]) -> str:
    return "[" + ",".join(str(value) for value in vector) + "]"


def _serialize(row) -> dict:
    result = dict(row)
    for key, value in list(result.items()):
        if hasattr(value, "isoformat"):
            result[key] = value.isoformat()
    result["keywords"] = result.get("keywords") or []
    return result


def _get_request(conn, request_id: int, username: str, *, lock: bool = False):
    role = get_user_role(username)
    visibility = "" if role == "Admin" else "AND r.assignee_username = :username"
    lock_clause = "FOR UPDATE" if lock else ""
    row = conn.execute(
        text(f"""
            SELECT r.*
            FROM {FAQ_REQUESTS} r
            WHERE r.faq_id = :request_id
              {visibility}
            {lock_clause}
        """),
        {"request_id": request_id, "username": username},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="FAQ 요청을 찾을 수 없거나 접근 권한이 없습니다.")
    return row


def _notify_requester(
    conn,
    request_id: int,
    message: str,
    *,
    event_type: str,
    faq_chat_id: int | None = None,
):
    trace = json.dumps(
        {
            "source": "faq_agent",
            "event_type": event_type,
            "faq_request_id": request_id,
            "faq_chat_id": faq_chat_id,
        }
    )
    room_id = conn.execute(
        text(f"""
            SELECT requester_chat_room_id
            FROM {FAQ_REQUESTS}
            WHERE faq_id = :faq_id
        """),
        {"faq_id": request_id},
    ).scalar_one_or_none()
    if room_id is not None:
        conn.execute(
            text(f"""
                INSERT INTO {CHAT_MESSAGES} (room_id, role, text, type, options, trace, sources)
                VALUES (
                    :room_id, 'ai', :message, 'answer', '[]'::jsonb,
                    CAST(:trace AS jsonb), '[]'::jsonb
                )
            """),
            {"room_id": room_id, "message": message, "trace": trace},
        )


@router.get("")
def list_faqs(
    status: Literal["all", "pending", "assigned", "approved", "rejected"] = "pending",
    query: str = Query(default="", max_length=200),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    username: str = Depends(_require_reviewer),
):
    role = get_user_role(username)
    visibility = "" if role == "Admin" else "AND assignee_username = :username"
    status_filter = "" if status == "all" else "status = :status AND"
    search = query.strip()
    params = {
        "status": status,
        "query": f"%{search}%" if search else "",
        "limit": limit,
        "offset": offset,
        "username": username,
    }
    where = f"""
        {status_filter}
        TRUE
        {visibility}
        AND (:query = '' OR refined_question ILIKE :query OR original_question ILIKE :query
             OR COALESCE(assignee_display_name, '') ILIKE :query)
    """
    with engine.connect() as conn:
        total = conn.execute(text(f"SELECT COUNT(*) FROM {FAQ_REQUESTS} WHERE {where}"), params).scalar_one()
        rows = conn.execute(
            text(f"""
                SELECT *
                FROM {FAQ_REQUESTS}
                WHERE {where}
                ORDER BY last_change_date DESC, last_change_time DESC, faq_id DESC
                LIMIT :limit OFFSET :offset
            """),
            params,
        ).mappings().all()
    return {"items": [_serialize(row) for row in rows], "total": total}


@router.get("/assignees")
def list_assignees(_username: str = Depends(_require_reviewer)):
    with engine.connect() as conn:
        rows = conn.execute(
            text(f"""
                SELECT username, role, COALESCE(display_name, username) AS display_name,
                       COALESCE(department, '') AS department
                FROM {USERS}
                WHERE role IN ('Admin', 'Developer')
                ORDER BY display_name, username
            """)
        ).mappings().all()
    return [dict(row) for row in rows]


@router.get("/{request_id}")
def get_faq(request_id: int, username: str = Depends(_require_reviewer)):
    with engine.connect() as conn:
        row = _get_request(conn, request_id, username)
        messages = conn.execute(
            text(f"""
                SELECT faq_chat_id, author_username, author_role, message_type, message_text,
                       regis_date, regis_time
                FROM {FAQ_REQUEST_MESSAGES}
                WHERE faq_id = :faq_id
                ORDER BY faq_chat_id
            """),
            {"faq_id": request_id},
        ).mappings().all()
    result = _serialize(row)
    result["messages"] = [_serialize(item) for item in messages]
    return result


@router.post("/{request_id}/messages")
def add_message(
    request_id: int,
    req: FAQMessageRequest,
    username: str = Depends(_require_reviewer),
):
    author_role = "admin" if get_user_role(username) == "Admin" else "assignee"
    with engine.begin() as conn:
        row = _get_request(conn, request_id, username, lock=True)
        if row["status"] not in {"pending", "assigned"}:
            raise HTTPException(status_code=409, detail="종료된 FAQ 요청에는 메시지를 추가할 수 없습니다.")
        message = conn.execute(
            text(f"""
                INSERT INTO {FAQ_REQUEST_MESSAGES}
                    (faq_id, author_username, author_role, message_type, message_text)
                VALUES (:faq_id, :username, :author_role, :message_type, :message_text)
                RETURNING faq_chat_id, author_username, author_role, message_type, message_text,
                          regis_date, regis_time
            """),
            {
                "faq_id": request_id,
                "username": username,
                "author_role": author_role,
                "message_type": req.message_type,
                "message_text": req.text.strip(),
            },
        ).mappings().one()
        conn.execute(
            text(f"""
                UPDATE {FAQ_REQUESTS}
                SET last_change_user = :username,
                    last_change_date = to_char(clock_timestamp() AT TIME ZONE 'Asia/Seoul', 'YYYYMMDD'),
                    last_change_time = to_char(clock_timestamp() AT TIME ZONE 'Asia/Seoul', 'HH24MISS')
                WHERE faq_id = :request_id
            """),
            {"request_id": request_id, "username": username},
        )
        if req.message_type == "additional_question":
            _notify_requester(
                conn,
                request_id,
                f"FAQ 요청 #{request_id} 담당자의 추가 질문입니다.\n\n{req.text.strip()}\n\n이 채팅방에 답변해 주세요.",
                event_type="additional_question",
                faq_chat_id=message["faq_chat_id"],
            )
    return _serialize(message)


@router.delete("/{request_id}/messages/{faq_chat_id}")
def delete_message(
    request_id: int,
    faq_chat_id: int,
    username: str = Depends(_require_reviewer),
):
    with engine.begin() as conn:
        request_row = _get_request(conn, request_id, username, lock=True)
        if request_row["status"] not in {"pending", "assigned"}:
            raise HTTPException(status_code=409, detail="완료된 FAQ의 대화는 삭제할 수 없습니다.")

        message = conn.execute(
            text(f"""
                SELECT faq_chat_id, message_type
                FROM {FAQ_REQUEST_MESSAGES}
                WHERE faq_chat_id = :faq_chat_id AND faq_id = :faq_id
                FOR UPDATE
            """),
            {"faq_chat_id": faq_chat_id, "faq_id": request_id},
        ).mappings().first()
        if not message:
            raise HTTPException(status_code=404, detail="삭제할 FAQ 메시지를 찾을 수 없습니다.")
        if message["message_type"] not in {"answer", "additional_question", "note"}:
            raise HTTPException(status_code=409, detail="최초 질문과 시스템 요약은 삭제할 수 없습니다.")

        # 추가질의처럼 원본 채팅방으로 전달된 AI 메시지도 연결 정보로 함께 삭제한다.
        conn.execute(
            text(f"""
                DELETE FROM {CHAT_MESSAGES}
                WHERE trace ->> 'source' = 'faq_agent'
                  AND trace ->> 'faq_request_id' = :request_id
                  AND trace ->> 'faq_chat_id' = :faq_chat_id
            """),
            {"request_id": str(request_id), "faq_chat_id": str(faq_chat_id)},
        )
        conn.execute(
            text(f"""
                DELETE FROM {FAQ_REQUEST_MESSAGES}
                WHERE faq_chat_id = :faq_chat_id AND faq_id = :faq_id
            """),
            {"faq_chat_id": faq_chat_id, "faq_id": request_id},
        )
        conn.execute(
            text(f"""
                UPDATE {FAQ_REQUESTS}
                SET last_change_user = :username,
                    last_change_date = to_char(clock_timestamp() AT TIME ZONE 'Asia/Seoul', 'YYYYMMDD'),
                    last_change_time = to_char(clock_timestamp() AT TIME ZONE 'Asia/Seoul', 'HH24MISS')
                WHERE faq_id = :request_id
            """),
            {"request_id": request_id, "username": username},
        )
    return {"deleted": True}


@router.post("/{request_id}/refine")
def refine_faq(request_id: int, username: str = Depends(_require_reviewer)):
    with engine.connect() as conn:
        row = _get_request(conn, request_id, username)
        messages = conn.execute(
            text(f"""
                SELECT author_username, author_role, message_type, message_text,
                       to_timestamp(regis_date || regis_time, 'YYYYMMDDHH24MISS')
                           AT TIME ZONE 'Asia/Seoul' AS created_at
                FROM {FAQ_REQUEST_MESSAGES}
                WHERE faq_id = :faq_id
                ORDER BY faq_chat_id
            """),
            {"faq_id": request_id},
        ).mappings().all()
        source_messages = conn.execute(
            text(f"""
                SELECT role AS author_username,
                       role AS author_role,
                       COALESCE(type, 'chat') AS message_type,
                       text AS message_text,
                       to_timestamp(regis_date || regis_time, 'YYYYMMDDHH24MISS')
                           AT TIME ZONE 'Asia/Seoul' AS created_at
                FROM {CHAT_MESSAGES}
                WHERE room_id = :room_id
                ORDER BY chat_id
            """),
            {"room_id": row["requester_chat_room_id"]},
        ).mappings().all()
    def message_timestamp(item: dict) -> datetime:
        value = item.get("created_at")
        if value is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    all_messages = sorted(
        [dict(item) for item in source_messages] + [dict(item) for item in messages],
        key=message_timestamp,
    )
    pair = faq_intake.refine_request_pair(
        dict(row),
        all_messages,
        language=get_user_language(username),
    )
    with engine.begin() as conn:
        updated = conn.execute(
            text(f"""
                UPDATE {FAQ_REQUESTS}
                SET summarized_question = :question,
                    summarized_answer = :answer,
                    final_keywords = :keywords,
                    last_change_user = :username,
                    last_change_date = to_char(clock_timestamp() AT TIME ZONE 'Asia/Seoul', 'YYYYMMDD'),
                    last_change_time = to_char(clock_timestamp() AT TIME ZONE 'Asia/Seoul', 'HH24MISS')
                WHERE faq_id = :request_id
                RETURNING *
            """),
            {
                "request_id": request_id,
                "question": pair.question.strip(),
                "answer": pair.answer.strip(),
                "keywords": list(dict.fromkeys(pair.keywords)),
                "username": username,
            },
        ).mappings().one()
    return _serialize(updated)


@router.post("/{request_id}/reassign")
def reassign_faq(
    request_id: int,
    req: FAQReassignRequest,
    background_tasks: BackgroundTasks,
    username: str = Depends(_require_reviewer),
):
    with engine.begin() as conn:
        _get_request(conn, request_id, username, lock=True)
        assignee = conn.execute(
            text(f"""
                SELECT username, COALESCE(display_name, username) AS display_name,
                       COALESCE(department, '') AS department
                FROM {USERS}
                WHERE username = :username
                  AND role IN ('Admin', 'Developer')
            """),
            {"username": req.assignee_username},
        ).mappings().first()
        if not assignee:
            raise HTTPException(status_code=404, detail="재배정할 담당자를 찾을 수 없습니다.")
        row = conn.execute(
            text(f"""
                UPDATE {FAQ_REQUESTS}
                SET assignee_username = :assignee_username,
                    assignee_display_name = :display_name,
                    assignee_team = :department,
                    assignment_reason = :reason,
                    assignment_confidence = '높음',
                    status = 'assigned',
                    last_change_user = :username,
                    last_change_date = to_char(clock_timestamp() AT TIME ZONE 'Asia/Seoul', 'YYYYMMDD'),
                    last_change_time = to_char(clock_timestamp() AT TIME ZONE 'Asia/Seoul', 'HH24MISS')
                WHERE faq_id = :request_id
                RETURNING *
            """),
            {
                "request_id": request_id,
                "assignee_username": assignee["username"],
                "display_name": assignee["display_name"],
                "department": assignee["department"],
                "reason": f"{username}의 수동 재배정",
                "username": username,
            },
        ).mappings().one()
    background_tasks.add_task(faq_mailer.send_assignment_email, request_id)
    return _serialize(row)


@router.post("/{request_id}/approve")
def approve_faq(
    request_id: int,
    req: FAQApprovalRequest,
    background_tasks: BackgroundTasks,
    username: str = Depends(_require_reviewer),
):
    question = req.question.strip()
    answer = req.answer.strip()
    keywords = list(dict.fromkeys(item.strip() for item in req.keywords if item.strip()))
    knowledge_value = "Y" if req.knowledge_search_allowed else "N"
    if req.knowledge_search_allowed:
        question_vector, answer_vector = embeddings.embed_documents([question, answer])
        question_embedding = _embedding_to_sql(question_vector)
        answer_embedding = _embedding_to_sql(answer_vector)
    else:
        question_embedding = None
        answer_embedding = None
    with engine.begin() as conn:
        request_row = _get_request(conn, request_id, username, lock=True)
        if request_row["status"] not in {"pending", "assigned"}:
            raise HTTPException(status_code=409, detail="이미 처리 완료된 FAQ 요청입니다.")
        row = conn.execute(
            text(f"""
                UPDATE {FAQ_REQUESTS}
                SET status = 'approved',
                    summarized_question = :question,
                    summarized_answer = :answer,
                    summarized_question_embedding = CAST(:question_embedding AS vector),
                    summarized_answer_embedding = CAST(:answer_embedding AS vector),
                    final_keywords = :keywords,
                    last_change_user = :username,
                    knowledge_search_allowed = :knowledge_search_allowed,
                    rejection_reason = NULL,
                    last_change_date = to_char(clock_timestamp() AT TIME ZONE 'Asia/Seoul', 'YYYYMMDD'),
                    last_change_time = to_char(clock_timestamp() AT TIME ZONE 'Asia/Seoul', 'HH24MISS')
                WHERE faq_id = :request_id
                RETURNING *
            """),
            {
                "request_id": request_id,
                "question": question,
                "answer": answer,
                "question_embedding": question_embedding,
                "answer_embedding": answer_embedding,
                "keywords": keywords,
                "username": username,
                "knowledge_search_allowed": knowledge_value,
            },
        ).mappings().one()
        _notify_requester(
            conn,
            request_id,
            f"FAQ 요청 #{request_id}이 승인되었습니다.\n\n질문: {question}\n\n답변: {answer}",
            event_type="approved",
        )
    background_tasks.add_task(faq_mailer.send_completion_email, request_id)
    return _serialize(row)


@router.post("/{request_id}/reject")
def reject_faq(
    request_id: int,
    req: FAQRejectRequest,
    username: str = Depends(_require_reviewer),
):
    with engine.begin() as conn:
        request_row = _get_request(conn, request_id, username, lock=True)
        if request_row["status"] not in {"pending", "assigned"}:
            raise HTTPException(status_code=409, detail="이미 처리 완료된 FAQ 요청입니다.")
        row = conn.execute(
            text(f"""
                UPDATE {FAQ_REQUESTS}
                SET status = 'rejected',
                    rejection_reason = :reason,
                    last_change_user = :username,
                    last_change_date = to_char(clock_timestamp() AT TIME ZONE 'Asia/Seoul', 'YYYYMMDD'),
                    last_change_time = to_char(clock_timestamp() AT TIME ZONE 'Asia/Seoul', 'HH24MISS')
                WHERE faq_id = :request_id
                RETURNING *
            """),
            {"request_id": request_id, "reason": req.reason.strip(), "username": username},
        ).mappings().one()
        _notify_requester(
            conn,
            request_id,
            f"FAQ 요청 #{request_id}이 반려되었습니다.\n\n반려 사유: {req.reason.strip()}",
            event_type="rejected",
        )
    return _serialize(row)
