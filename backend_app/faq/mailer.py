"""FAQ 요청 배정 메일 발송.

요청 저장 트랜잭션과 분리된 FastAPI 백그라운드 작업에서 호출된다.
"""

import html
import logging
import smtplib
import ssl
import time
from email.message import EmailMessage

from sqlalchemy import text

from config import (
    FAQ_MAIL_ENABLED,
    FAQ_MAIL_FROM,
    FAQ_MAIL_RETRY_COUNT,
    FAQ_SMTP_APP_PASSWORD,
    FAQ_SMTP_HOST,
    FAQ_SMTP_PORT,
    FAQ_SMTP_USERNAME,
)
from db import engine
from db_tables import FAQ_REQUESTS, USERS


logger = logging.getLogger(__name__)


def _load_mail_context(request_id: int) -> dict | None:
    with engine.connect() as conn:
        row = conn.execute(
            text(f"""
                SELECT r.faq_id,
                       r.requester_username,
                       COALESCE(requester.display_name, r.requester_username) AS requester_name,
                       r.original_question,
                       r.refined_question,
                       r.target_business,
                       r.screen_number,
                       r.country,
                       r.assignee_username,
                       COALESCE(r.assignee_display_name, r.assignee_username) AS assignee_name,
                       r.assignee_team,
                       r.assignment_reason,
                       r.assignment_confidence,
                       r.regis_date,
                       r.regis_time,
                       assignee.email AS assignee_email
                FROM {FAQ_REQUESTS} r
                LEFT JOIN {USERS} requester ON requester.username = r.requester_username
                JOIN {USERS} assignee ON assignee.username = r.assignee_username
                WHERE r.faq_id = :request_id
            """),
            {"request_id": request_id},
        ).mappings().first()
    return dict(row) if row else None


def _format_compact_datetime(date_value: str, time_value: str) -> str:
    date_text = str(date_value).strip()
    time_text = str(time_value).strip()
    if len(date_text) != 8 or len(time_text) != 6:
        return f"{date_text} {time_text}".strip()
    return (
        f"{date_text[:4]}-{date_text[4:6]}-{date_text[6:8]} "
        f"{time_text[:2]}:{time_text[2:4]}:{time_text[4:6]} KST"
    )


def _build_message(context: dict) -> EmailMessage:
    registered_at = _format_compact_datetime(context["regis_date"], context["regis_time"])
    subject = f"[아이테르 FAQ] 새 요청 #{context['faq_id']}이 배정되었습니다"
    fields = [
        ("요청 번호", f"#{context['faq_id']}"),
        ("요청자 아이디", context["requester_username"]),
        ("요청자 이름", context["requester_name"]),
        ("등록 일시", registered_at),
        ("원본 질문", context["original_question"]),
        ("정제 질문", context["refined_question"]),
        ("대상 업무", context.get("target_business") or "미확인"),
        ("화면 번호", context.get("screen_number") or "미확인"),
        ("담당 국가", context.get("country") or "미확인"),
        ("배정 담당자", context["assignee_name"]),
        ("담당팀", context.get("assignee_team") or "미확인"),
        ("배정 근거", context.get("assignment_reason") or "미확인"),
        ("신뢰도", context.get("assignment_confidence") or "미확인"),
    ]

    plain_lines = [
        f"{context['assignee_name']}님, 새로운 FAQ 확인 요청이 배정되었습니다.",
        "",
        *[f"{label}: {value}" for label, value in fields],
        "",
        "아이테르 FAQ 검수 화면에서 답변 작성, 추가질의, 재배정, 승인 또는 반려를 진행해 주세요.",
    ]
    rows = "".join(
        "<tr>"
        f"<th style='text-align:left;padding:7px;border:1px solid #ddd;background:#f5f7fa'>{html.escape(label)}</th>"
        f"<td style='padding:7px;border:1px solid #ddd'>{html.escape(str(value))}</td>"
        "</tr>"
        for label, value in fields
    )
    html_body = f"""
    <html>
      <body style="font-family:Arial,'Noto Sans KR',sans-serif;color:#1f2937">
        <p><strong>{html.escape(context['assignee_name'])}</strong>님,
           새로운 FAQ 확인 요청이 배정되었습니다.</p>
        <table style="border-collapse:collapse;width:100%;max-width:760px">{rows}</table>
        <p>아이테르 FAQ 검수 화면에서 답변 작성, 추가질의, 재배정, 승인 또는 반려를 진행해 주세요.</p>
      </body>
    </html>
    """

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = FAQ_MAIL_FROM
    message["To"] = context["assignee_email"]
    message.set_content("\n".join(plain_lines))
    message.add_alternative(html_body, subtype="html")
    return message


def _send_once(message: EmailMessage):
    tls_context = ssl.create_default_context()
    with smtplib.SMTP(FAQ_SMTP_HOST, FAQ_SMTP_PORT, timeout=20) as smtp:
        smtp.ehlo()
        smtp.starttls(context=tls_context)
        smtp.ehlo()
        smtp.login(FAQ_SMTP_USERNAME, FAQ_SMTP_APP_PASSWORD)
        smtp.send_message(message)


def send_assignment_email(request_id: int) -> bool:
    """배정 메일을 보내고 일시 오류면 제한적으로 재시도한다.

    예외는 호출자에게 전파하지 않아 FAQ 등록 결과를 되돌리지 않는다.
    """
    if not FAQ_MAIL_ENABLED:
        logger.info("FAQ assignment email disabled; request_id=%s", request_id)
        return False
    if not FAQ_SMTP_APP_PASSWORD:
        logger.error(
            "FAQ mail is enabled but FAQ_SMTP_APP_PASSWORD is empty; request_id=%s",
            request_id,
        )
        return False

    context = _load_mail_context(request_id)
    if not context:
        logger.error("FAQ request not found for assignment email; request_id=%s", request_id)
        return False
    if not context.get("assignee_email"):
        logger.error("Assignee email is missing; request_id=%s", request_id)
        return False

    message = _build_message(context)
    retries = max(1, FAQ_MAIL_RETRY_COUNT)
    for attempt in range(1, retries + 1):
        try:
            _send_once(message)
            logger.info(
                "FAQ assignment email sent; request_id=%s recipient=%s",
                request_id,
                context["assignee_email"],
            )
            return True
        except Exception:
            logger.exception(
                "FAQ assignment email failed; request_id=%s attempt=%s/%s",
                request_id,
                attempt,
                retries,
            )
            if attempt < retries:
                time.sleep(min(2 ** (attempt - 1), 8))
    return False


def _load_completion_context(request_id: int) -> dict | None:
    with engine.connect() as conn:
        row = conn.execute(
            text(f"""
                SELECT r.faq_id,
                       r.requester_username,
                       COALESCE(requester.display_name, r.requester_username) AS requester_name,
                       requester.email AS requester_email,
                       r.summarized_question,
                       r.summarized_answer,
                       r.target_business,
                       r.screen_number,
                       r.country,
                       r.regis_date,
                       r.regis_time,
                       r.last_change_date,
                       r.last_change_time,
                       r.last_change_user
                FROM {FAQ_REQUESTS} r
                LEFT JOIN {USERS} requester ON requester.username = r.requester_username
                WHERE r.faq_id = :request_id
                  AND r.status = 'approved'
            """),
            {"request_id": request_id},
        ).mappings().first()
    return dict(row) if row else None


def _build_completion_message(context: dict) -> EmailMessage:
    completed_at = _format_compact_datetime(
        context["last_change_date"],
        context["last_change_time"],
    )
    fields = [
        ("요청 번호", f"#{context['faq_id']}"),
        ("요청자 아이디", context["requester_username"]),
        ("요청자 이름", context["requester_name"]),
        ("답변 완료 일시", completed_at),
        ("대상 업무", context.get("target_business") or "미확인"),
        ("화면 번호", context.get("screen_number") or "미확인"),
        ("대상 국가", context.get("country") or "미확인"),
        ("최종 질문", context.get("summarized_question") or ""),
        ("등록 답변", context.get("summarized_answer") or ""),
    ]
    plain_lines = [
        f"{context['requester_name']}님이 요청한 FAQ의 답변 등록이 완료되었습니다.",
        "",
        *[f"{label}: {value}" for label, value in fields],
        "",
        "아이테르의 원본 채팅방에서도 완료 답변을 확인할 수 있습니다.",
    ]
    rows = "".join(
        "<tr>"
        f"<th style='text-align:left;padding:7px;border:1px solid #ddd;background:#f5f7fa'>{html.escape(label)}</th>"
        f"<td style='padding:7px;border:1px solid #ddd;white-space:pre-wrap'>{html.escape(str(value))}</td>"
        "</tr>"
        for label, value in fields
    )
    html_body = f"""
    <html>
      <body style="font-family:Arial,'Noto Sans KR',sans-serif;color:#1f2937">
        <p><strong>{html.escape(context['requester_name'])}</strong>님이 요청한
           FAQ의 답변 등록이 완료되었습니다.</p>
        <table style="border-collapse:collapse;width:100%;max-width:760px">{rows}</table>
        <p>아이테르의 원본 채팅방에서도 완료 답변을 확인할 수 있습니다.</p>
      </body>
    </html>
    """

    message = EmailMessage()
    message["Subject"] = f"[아이테르 FAQ] 요청 #{context['faq_id']} 답변이 완료되었습니다"
    message["From"] = FAQ_MAIL_FROM
    message["To"] = context["requester_email"]
    message.set_content("\n".join(plain_lines))
    message.add_alternative(html_body, subtype="html")
    return message


def send_completion_email(request_id: int) -> bool:
    """승인 완료된 FAQ의 요청자에게만 결과 메일을 보낸다."""
    if not FAQ_MAIL_ENABLED:
        logger.info("FAQ completion email disabled; request_id=%s", request_id)
        return False
    if not FAQ_SMTP_APP_PASSWORD:
        logger.error(
            "FAQ mail is enabled but FAQ_SMTP_APP_PASSWORD is empty; request_id=%s",
            request_id,
        )
        return False

    context = _load_completion_context(request_id)
    if not context:
        logger.error("Approved FAQ request not found for completion email; request_id=%s", request_id)
        return False
    if not context.get("requester_email"):
        logger.error("Requester email is missing; request_id=%s", request_id)
        return False

    message = _build_completion_message(context)
    retries = max(1, FAQ_MAIL_RETRY_COUNT)
    for attempt in range(1, retries + 1):
        try:
            _send_once(message)
            logger.info(
                "FAQ completion email sent; request_id=%s recipient=%s",
                request_id,
                context["requester_email"],
            )
            return True
        except Exception:
            logger.exception(
                "FAQ completion email failed; request_id=%s attempt=%s/%s",
                request_id,
                attempt,
                retries,
            )
            if attempt < retries:
                time.sleep(min(2 ** (attempt - 1), 8))
    return False
