import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from faq import intake as faq_intake  # 대화 맥락 요약, 업무 질문 판정, 추가질문, FAQ 등록 확인·수정·취소, 담당자 선정, 최종 언어 통일
from faq import mailer as faq_mailer  # Ask AI에서 FAQ 접수가 완료되면 예상 담당자에게 배정 메일 발송
from chat.language import detect_response_language, select_response_language_sample
from chat import word_dictionary
from chat.workflow import run_chat_workflow
from auth.service import get_current_user
from db import engine
from db_tables import CHAT_MESSAGES, CHAT_ROOMS

router = APIRouter(prefix="/api/chat", tags=["chat"])


class SendMessageRequest(BaseModel):
    input_message: str


class ResumeTermRegistrationRequest(BaseModel):
    skip_registration: bool = False


def _row_to_room(row) -> dict:
    return {
        "room_id": row["room_id"],
        "status": row["status"] if "status" in row else "10",
        "title": row["title"],
        "summary": row["summary"],
        "last_summarized_message_id": row["last_summarized_message_id"],
        "regis_date": row["regis_date"],
        "regis_time": row["regis_time"],
        "last_change_date": row["last_change_date"],
        "last_change_time": row["last_change_time"],
        "has_faq_agent_update": (
            bool(row["has_faq_agent_update"])
            if "has_faq_agent_update" in row
            else False
        ),
        "latest_faq_agent_chat_id": (
            row["latest_faq_agent_chat_id"]
            if "latest_faq_agent_chat_id" in row
            else None
        ),
    }


def _row_to_message(row) -> dict:
    return {
        "chat_id": row["chat_id"],
        "role": row["role"],
        "text": row["text"],
        "type": row["type"],
        "options": row["options"] or [],
        "trace": row["trace"],
        "sources": row["sources"] or [],
        "regis_date": row["regis_date"],
        "regis_time": row["regis_time"],
    }


@router.post("/rooms")
def create_room(username: str = Depends(get_current_user)):
    with engine.begin() as conn:
        row = conn.execute(
            text(f"""
                INSERT INTO {CHAT_ROOMS} (room_user, status)
                VALUES (:username, '10')
                RETURNING room_id, status, title, summary, last_summarized_message_id,
                          regis_date, regis_time, last_change_date, last_change_time
            """),
            {"username": username},
        ).mappings().one()
    return _row_to_room(row)


@router.get("/rooms")
def list_rooms(username: str = Depends(get_current_user)):
    with engine.begin() as conn:
        # Ask AI 진입/목록 갱신 시 각 방의 마지막 메시지 등록시각을 원장에 반영한다.
        conn.execute(
            text(f"""
                WITH latest AS (
                    SELECT DISTINCT ON (m.room_id)
                           m.room_id, m.regis_date, m.regis_time
                    FROM {CHAT_MESSAGES} m
                    ORDER BY m.room_id, m.chat_id DESC
                )
                UPDATE {CHAT_ROOMS} r
                SET last_change_date = latest.regis_date,
                    last_change_time = latest.regis_time
                FROM latest
                WHERE r.room_id = latest.room_id
                  AND r.room_user = :username
                  AND r.status = '10'
                  AND (r.last_change_date, r.last_change_time)
                      IS DISTINCT FROM (latest.regis_date, latest.regis_time)
            """),
            {"username": username},
        )
        rows = conn.execute(
            text(f"""
                SELECT r.room_id, r.status, r.title, r.summary, r.last_summarized_message_id,
                       r.regis_date, r.regis_time, r.last_change_date, r.last_change_time,
                       EXISTS (
                           SELECT 1
                           FROM {CHAT_MESSAGES} update_message
                           WHERE update_message.room_id = r.room_id
                             AND update_message.role = 'ai'
                             AND update_message.trace ->> 'source' = 'faq_agent'
                       ) AS has_faq_agent_update,
                       (
                           SELECT MAX(update_message.chat_id)
                           FROM {CHAT_MESSAGES} update_message
                           WHERE update_message.room_id = r.room_id
                             AND update_message.role = 'ai'
                             AND update_message.trace ->> 'source' = 'faq_agent'
                       ) AS latest_faq_agent_chat_id
                FROM {CHAT_ROOMS} r
                WHERE r.room_user = :username
                  AND r.status = '10'
                ORDER BY r.room_id DESC
            """),
            {"username": username}
        ).mappings().all()
    return [_row_to_room(r) for r in rows]


def _get_room(room_id: int, username: str):
    with engine.connect() as conn:
        row = conn.execute(
            text(f"""
                SELECT r.room_id, r.status, r.title, r.summary, r.last_summarized_message_id,
                       r.regis_date, r.regis_time, r.last_change_date, r.last_change_time
                FROM {CHAT_ROOMS} r
                WHERE r.room_id = :room_id
                  AND r.room_user = :username
                  AND r.status = '10'
            """),
            {"room_id": room_id, "username": username},
        ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="채팅방을 찾을 수 없습니다.")
    return row


@router.delete("/rooms/{room_id}")
def delete_room(room_id: int, username: str = Depends(get_current_user)):
    _get_room(room_id, username)
    with engine.begin() as conn:
        updated = conn.execute(
            text(f"""
                UPDATE {CHAT_ROOMS}
                SET status = '90'
                WHERE room_id = :room_id
                  AND room_user = :username
                  AND status = '10'
            """),
            {"room_id": room_id, "username": username},
        )
    return {"deleted": updated.rowcount > 0, "soft_deleted": True, "status": "90"}


@router.get("/rooms/{room_id}/messages")
def list_messages(room_id: int, username: str = Depends(get_current_user)):
    _get_room(room_id, username)
    with engine.connect() as conn:
        rows = conn.execute(
            text(f"""
                SELECT m.chat_id, m.role, m.text, m.type, m.options, m.trace, m.sources,
                       m.regis_date, m.regis_time
                FROM {CHAT_MESSAGES} m
                WHERE m.room_id = :room_id
                ORDER BY m.chat_id ASC
            """),
            {"room_id": room_id}
        ).mappings().all()
    return [_row_to_message(r) for r in rows]


def _run_and_store_ai_message(
    *,
    room_id: int,
    message: str,
    username: str,
    history: list[dict],
    language: str,
    response_language_sample: str,
    background_tasks: BackgroundTasks,
    original_user_chat_id: int | None = None,
    ignored_unknown_terms: list[str] | None = None,
) -> dict:
    """채팅 workflow를 실행하고 최종 AI 메시지를 저장한다."""
    conversation_context = None
    workflow_steps = []
    try:
        workflow_run = run_chat_workflow(
            message=message,
            room_id=room_id,
            username=username,
            history=history,
            language=language,
            manual_id=None,
            ignored_unknown_terms=ignored_unknown_terms,
        )
        conversation_context = workflow_run.conversation_context
        workflow_steps = workflow_run.transitions
        result = workflow_run.result
    except Exception as e:
        error_text = (
            f"요청 처리 오류: {str(e)}"
            if language == "ko"
            else f"Request processing error: {str(e)}"
        )
        result = {"type": "answer", "text": error_text, "options": [], "sources": []}

    trace = result.get("trace")
    if trace and trace.get("term_registration") and original_user_chat_id is not None:
        trace = {
            **trace,
            "term_registration": {
                **trace["term_registration"],
                "original_user_chat_id": original_user_chat_id,
            },
        }

    localization_step = None
    try:
        original_text = result["text"]
        original_options = result.get("options") or []
        localized = faq_intake.localize_chat_response(
            original_text,
            original_options,
            language,
            response_language_sample,
        )
        result["text"] = localized.text
        result["options"] = localized.options
        localization_step = {
            "node": "localize_chat_response",
            "label": "최종 응답 언어 통일" if language == "ko" else "Localize final response",
            "input": {
                "language": language,
                "language_source": "current_or_previous_user_message",
                "text": original_text,
                "options": original_options,
            },
            "output": localized.model_dump(),
        }
    except Exception as localization_error:
        localization_step = {
            "node": "localize_chat_response",
            "label": "최종 응답 언어 통일" if language == "ko" else "Localize final response",
            "input": {"language": language},
            "output": {
                "localized": False,
                "fallback": "original_response",
                "error": str(localization_error),
            },
        }

    if conversation_context is not None:
        context_step = {
            "node": "summarize_conversation_context",
            "label": "최종 대화 맥락 요약" if language == "ko" else "Condense conversation context",
            "input": {
                "current_message": message,
                "history_turn_count": len(history),
            },
            "output": conversation_context.model_dump(),
        }
        if trace is None:
            trace = {
                "engine": "chat_pipeline",
                "steps": [context_step, *workflow_steps, localization_step],
            }
        else:
            trace = {
                **trace,
                "steps": [
                    context_step,
                    *workflow_steps,
                    *(trace.get("steps") or []),
                    localization_step,
                ],
            }
    elif localization_step is not None:
        if trace is None:
            trace = {"engine": "chat_pipeline", "steps": [localization_step]}
        else:
            trace = {**trace, "steps": [*(trace.get("steps") or []), localization_step]}

    sources = result.get("sources") or []
    with engine.begin() as conn:
        ai_row = conn.execute(
            text(f"""
                INSERT INTO {CHAT_MESSAGES} (room_id, role, text, type, options, trace, sources)
                VALUES (:room_id, 'ai', :text, :type, :options, :trace, :sources)
                RETURNING chat_id, role, text, type, options, trace, sources,
                          regis_date, regis_time
            """),
            {
                "room_id": room_id,
                "text": result["text"],
                "type": result["type"],
                "options": json.dumps(result.get("options") or []),
                "trace": json.dumps(trace) if trace is not None else None,
                "sources": json.dumps(sources),
            },
        ).mappings().one()

    email_request_id = result.get("faq_assignment_email_request_id")
    if email_request_id:
        background_tasks.add_task(faq_mailer.send_assignment_email, int(email_request_id))

    return _row_to_message(ai_row)


@router.post("/rooms/{room_id}/messages")
def send_message(
    room_id: int,
    req: SendMessageRequest,
    background_tasks: BackgroundTasks,
    username: str = Depends(get_current_user),
):
    room = _get_room(room_id, username)

    with engine.begin() as conn:
        history_rows = conn.execute(
            text(f"SELECT role, text, type, options, trace FROM {CHAT_MESSAGES} WHERE room_id = :room_id ORDER BY chat_id ASC"),
            {"room_id": room_id}
        ).mappings().all()
        history = [
            {"role": r["role"], "text": r["text"], "type": r["type"], "options": r["options"] or [], "trace": r["trace"]}
            for r in history_rows
        ]
        language = detect_response_language(req.input_message, history)
        response_language_sample = select_response_language_sample(req.input_message, history)

        user_row = conn.execute(
            text(f"""
                INSERT INTO {CHAT_MESSAGES} (room_id, role, text)
                VALUES (:room_id, 'user', :text)
                RETURNING chat_id
            """),
            {"room_id": room_id, "text": req.input_message}
        ).mappings().one()

        if room["title"] == "새 대화":
            new_title = req.input_message[:30]
            conn.execute(
                text(f"UPDATE {CHAT_ROOMS} SET title = :title WHERE room_id = :room_id"),
                {"title": new_title, "room_id": room_id},
            )

    return _run_and_store_ai_message(
        room_id=room_id,
        message=req.input_message,
        username=username,
        history=history,
        language=language,
        response_language_sample=response_language_sample,
        background_tasks=background_tasks,
        original_user_chat_id=int(user_row["chat_id"]),
    )


@router.post("/rooms/{room_id}/term-registration/resume")
def resume_after_term_registration(
    room_id: int,
    background_tasks: BackgroundTasks,
    req: ResumeTermRegistrationRequest | None = None,
    username: str = Depends(get_current_user),
):
    """신규단어 저장 후 원 사용자 질문을 중복 적재하지 않고 재개한다."""
    _get_room(room_id, username)
    with engine.connect() as conn:
        latest = conn.execute(
            text(f"""
                SELECT chat_id, role, type, trace
                FROM {CHAT_MESSAGES}
                WHERE room_id = :room_id
                ORDER BY chat_id DESC
                LIMIT 1
            """),
            {"room_id": room_id},
        ).mappings().first()

    trace = (latest or {}).get("trace") or {}
    registration = trace.get("term_registration") or {}
    if not latest or latest["role"] != "ai" or not registration:
        raise HTTPException(status_code=409, detail="재개할 신규단어 등록 요청이 없습니다.")

    current_term = str(registration.get("current_term") or "").strip()
    skip_registration = bool(req and req.skip_registration)
    if (
        not skip_registration
        and (not current_term or word_dictionary.missing_terms(word_dictionary.lookup_terms([current_term])))
    ):
        raise HTTPException(status_code=409, detail="신규단어를 먼저 등록해 주세요.")

    original_question = str(registration.get("original_question") or "").strip()
    original_user_chat_id = registration.get("original_user_chat_id")
    if not original_question or not original_user_chat_id:
        raise HTTPException(status_code=409, detail="원래 질문을 복원할 수 없습니다.")

    with engine.connect() as conn:
        history_rows = conn.execute(
            text(f"""
                SELECT role, text, type, options, trace
                FROM {CHAT_MESSAGES}
                WHERE room_id = :room_id
                  AND chat_id < :original_user_chat_id
                ORDER BY chat_id ASC
            """),
            {"room_id": room_id, "original_user_chat_id": original_user_chat_id},
        ).mappings().all()
    history = [
        {"role": row["role"], "text": row["text"], "type": row["type"], "options": row["options"] or [], "trace": row["trace"]}
        for row in history_rows
    ]
    language = detect_response_language(original_question, history)
    response_language_sample = select_response_language_sample(original_question, history)
    return _run_and_store_ai_message(
        room_id=room_id,
        message=original_question,
        username=username,
        history=history,
        language=language,
        response_language_sample=response_language_sample,
        background_tasks=background_tasks,
        original_user_chat_id=int(original_user_chat_id),
        ignored_unknown_terms=(
            list(registration.get("pending_terms") or [])
            if skip_registration
            else []
        ),
    )


def _checkpoint_room(room_id: int, username: str) -> dict:
    room = _get_room(room_id, username)
    with engine.connect() as conn:
        rows = conn.execute(
            text(f"SELECT chat_id, role, text FROM {CHAT_MESSAGES} WHERE room_id = :room_id ORDER BY chat_id ASC"),
            {"room_id": room_id},
        ).mappings().all()

    if not rows:
        return {"room_id": room_id, "checkpointed": False, "reason": "no_messages", "faq_count": 0}

    target_message_id = rows[-1]["chat_id"]
    last_summarized_message_id = room["last_summarized_message_id"] or 0
    if target_message_id <= last_summarized_message_id:
        return {
            "room_id": room_id,
            "checkpointed": False,
            "reason": "already_summarized",
            "faq_count": 0,
        }

    new_rows = [row for row in rows if row["chat_id"] > last_summarized_message_id]
    new_roles = {row["role"] for row in new_rows}
    if not {"user", "ai"}.issubset(new_roles):
        return {"room_id": room_id, "checkpointed": False, "reason": "incomplete_exchange", "faq_count": 0}

    with engine.begin() as conn:
        conn.execute(
            text(f"""
                UPDATE {CHAT_ROOMS}
                SET last_summarized_message_id = :target_message_id
                WHERE room_id = :room_id
                  AND COALESCE(last_summarized_message_id, 0) < :target_message_id
            """),
            {"room_id": room_id, "target_message_id": target_message_id},
        )

    return {
        "room_id": room_id,
        "checkpointed": True,
        "last_summarized_message_id": target_message_id,
        "faq_count": 0,
        "reason": "answered_conversations_are_not_promoted_to_faq",
    }


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
                SELECT r.room_id
                FROM {CHAT_ROOMS} r
                JOIN LATERAL (
                    SELECT MAX(m.chat_id) AS last_message_id,
                           MAX(
                               to_timestamp(m.regis_date || m.regis_time, 'YYYYMMDDHH24MISS')
                               AT TIME ZONE 'Asia/Seoul'
                           ) AS last_message_at
                    FROM {CHAT_MESSAGES} m
                    WHERE m.room_id = r.room_id
                ) latest ON true
                WHERE r.room_user = :username
                  AND r.status = '10'
                  AND latest.last_message_id > COALESCE(r.last_summarized_message_id, 0)
                  AND latest.last_message_at <= (now() AT TIME ZONE 'Asia/Seoul') - interval '30 minutes'
                ORDER BY r.room_id
            """),
            {"username": username},
        ).scalars().all()
    return _checkpoint_room_ids(list(room_ids), username)


@router.post("/checkpoints/all")
def checkpoint_all_rooms(username: str = Depends(get_current_user)):
    with engine.connect() as conn:
        room_ids = conn.execute(
            text(f"""
                SELECT r.room_id
                FROM {CHAT_ROOMS} r
                WHERE r.room_user = :username
                  AND r.status = '10'
                  AND EXISTS (
                      SELECT 1
                      FROM {CHAT_MESSAGES} m
                      WHERE m.room_id = r.room_id
                        AND m.chat_id > COALESCE(r.last_summarized_message_id, 0)
                  )
                ORDER BY r.room_id
            """),
            {"username": username},
        ).scalars().all()
    return _checkpoint_room_ids(list(room_ids), username)
