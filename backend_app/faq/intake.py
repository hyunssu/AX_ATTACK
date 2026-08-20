"""지식으로 답하지 못한 질문만 FAQ 요청으로 접수하는 워크플로."""

import re
from typing import Literal

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from sqlalchemy import text

from config import OPENAI_CHAT_MODEL
from db import engine
from db_tables import (
    FAQ_REQUEST_MESSAGES,
    FAQ_REQUESTS,
    SCREEN_OWNERS,
    USERS,
)
from chat.prompts import format_prompt, prompt_label, schema_description


class IntakeAnalysis(BaseModel):
    target_business: Literal["수신", "여신", "고객", "외환", "채널", "공통", "총무", "카드", "UMS", "기타"] = Field(
        description=schema_description("intake.target_business"),
    )
    screen_number: str = Field(default="", description=schema_description("intake.screen_number"))
    country: str = Field(default="", description=schema_description("intake.country"))
    refined_question: str = Field(description=schema_description("intake.refined_question"))
    missing_information: list[str] = Field(
        default_factory=list,
        description=schema_description("intake.missing_information"),
    )
    assignment_keywords: list[str] = Field(
        default_factory=list,
        description=schema_description("intake.assignment_keywords"),
    )
    preferred_assignee_names: list[str] = Field(
        default_factory=list,
        description=schema_description("intake.preferred_assignee_names"),
    )
    preferred_team: str = Field(default="", description=schema_description("intake.preferred_team"))


class RefinedPair(BaseModel):
    question: str = Field(description=schema_description("refined_pair.question"))
    answer: str = Field(description=schema_description("refined_pair.answer"))
    keywords: list[str] = Field(default_factory=list, description=schema_description("refined_pair.keywords"))


class MainChatRoute(BaseModel):
    route: Literal["business_manual", "general_chat"] = Field(
        description=schema_description("main_route.route"),
    )
    reason: str = Field(default="", description=schema_description("common.reason"))


class ConversationContext(BaseModel):
    summary: str = Field(description=schema_description("conversation.summary"))
    active_business_question: str = Field(
        default="", description=schema_description("conversation.active_business_question")
    )
    confirmed_facts: list[str] = Field(
        default_factory=list, description=schema_description("conversation.confirmed_facts")
    )
    pending_clarification: str = Field(
        default="", description=schema_description("conversation.pending_clarification")
    )
    is_aither_business_context: bool = Field(
        default=False, description=schema_description("conversation.is_aither_business_context")
    )
    current_message_is_followup: bool = Field(
        default=False, description=schema_description("conversation.current_message_is_followup")
    )


class RegistrationFollowUp(BaseModel):
    action: Literal["confirm", "cancel", "revise", "new_message"] = Field(
        description=schema_description("registration.action"),
    )
    reason: str = Field(default="", description=schema_description("common.reason"))


class LocalizedChatResponse(BaseModel):
    text: str = Field(description=schema_description("localization.text"))
    options: list[str] = Field(
        default_factory=list,
        description=schema_description("localization.options"),
    )


llm = ChatOpenAI(model=OPENAI_CHAT_MODEL, temperature=0)
intake_llm = llm.with_structured_output(IntakeAnalysis)
pair_llm = llm.with_structured_output(RefinedPair)
main_route_llm = llm.with_structured_output(MainChatRoute)
conversation_context_llm = llm.with_structured_output(ConversationContext)
registration_followup_llm = llm.with_structured_output(RegistrationFollowUp)
localization_llm = llm.with_structured_output(LocalizedChatResponse)
def _history_text(history: list[dict], language: str) -> str:
    user_label = prompt_label("user", language=language)
    ai_label = prompt_label("ai", language=language)
    return "\n".join(
        f"{user_label if item.get('role') == 'user' else ai_label}: {item.get('text', '')}"
        for item in history[-12:]
    ) or prompt_label("empty_history", language=language)


def summarize_conversation_context(
    message: str,
    history: list[dict],
    language: str,
) -> ConversationContext:
    """Create one reusable context snapshot for every LLM stage in this turn."""
    prompt = format_prompt(
        "conversation_context_summary",
        language=language,
        history_text=_history_text(history, language),
        message=message,
    )
    try:
        return conversation_context_llm.invoke(prompt)
    except Exception:
        last_ai = next((item for item in reversed(history) if item.get("role") == "ai"), {})
        is_followup = bool(last_ai and last_ai.get("type") == "clarify")
        prior_user = next((item for item in history if item.get("role") == "user"), {})
        return ConversationContext(
            summary=" | ".join(
                value for value in (prior_user.get("text", ""), message) if value
            ) or message,
            active_business_question=prior_user.get("text", "") if is_followup else "",
            confirmed_facts=[],
            pending_clarification=last_ai.get("text", "") if is_followup else "",
            is_aither_business_context=is_followup,
            current_message_is_followup=is_followup,
        )


def localize_chat_response(
    response_text: str,
    options: list[str],
    language: str,
) -> LocalizedChatResponse:
    """Localize the completed response so interpolated DB values cannot mix languages."""
    prompt = format_prompt(
        "localize_chat_response",
        language=language,
        text=response_text,
        options_text="\n".join(f"- {option}" for option in options)
        or prompt_label("empty_value", language=language),
    )
    return localization_llm.invoke(prompt)


def _analyse(
    question: str,
    history: list[dict],
    language: str,
    conversation_context: ConversationContext,
) -> IntakeAnalysis:
    prompt = format_prompt(
        "intake_analysis",
        language=language,
        conversation_context=conversation_context.summary,
        history_text=_history_text(history, language),
        question=question,
    )
    result: IntakeAnalysis = intake_llm.invoke(prompt)
    country = result.country.strip()
    missing = [item for item in result.missing_information if item.strip()]
    if not country or country in {"미확인", "알 수 없음", "없음"}:
        missing = [item for item in missing if "국가" not in item]
        missing.insert(0, (
            "어느 국가에서 발생한 업무인지 대상 국가를 알려주세요."
            if language == "ko"
            else "Which country is this business issue occurring in?"
        ))
    result.missing_information = missing[:3]
    return result


def _analyse_registration_revision(instruction: str, history: list[dict], language: str) -> IntakeAnalysis:
    prompt = format_prompt(
        "registration_revision",
        language=language,
        history_text=_history_text(history, language),
        instruction=instruction or prompt_label("no_revision", language=language),
    )
    result: IntakeAnalysis = intake_llm.invoke(prompt)
    country = result.country.strip()
    missing = [item for item in result.missing_information if item.strip()]
    if not country or country in {"미확인", "알 수 없음", "없음"}:
        missing = [item for item in missing if "국가" not in item]
        missing.insert(0, (
            "어느 국가에서 발생한 업무인지 대상 국가를 알려주세요."
            if language == "ko"
            else "Which country is this business issue occurring in?"
        ))
    result.missing_information = missing[:3]
    return result


def _registration_follow_up_action(message: str, history: list[dict], language: str) -> str:
    normalized = re.sub(r"\s+", " ", message.strip().lower())
    if normalized in {
        "yes", "y", "네", "예", "응", "그대로", "그대로 등록해줘", "등록해줘", "등록",
        "register as shown", "register", "confirm",
    }:
        return "confirm"
    if "그대로" in normalized and "등록" in normalized:
        return "confirm"
    if normalized in {"아니요", "아니오", "no", "취소"} or re.search(
        r"(등록|faq).*(안\s*할|하지\s*마|보내지\s*마|취소)|안\s*할래",
        normalized,
    ):
        return "cancel"

    prompt = format_prompt(
        "registration_followup",
        language=language,
        history_text=_history_text(history[-8:], language),
        message=message,
    )
    decision: RegistrationFollowUp = registration_followup_llm.invoke(prompt)
    return decision.action


def redirect_non_business_chat_if_applicable(
    message: str,
    history: list[dict],
    language: str,
    conversation_context: ConversationContext,
) -> dict | None:
    """Aither 업무 질문이 아니면 업무 문의로 다시 질문하도록 안내한다."""
    if (
        conversation_context.is_aither_business_context
        and conversation_context.current_message_is_followup
    ):
        return None

    route_prompt = format_prompt(
        "main_chat_route",
        language=language,
        conversation_context=conversation_context.summary,
        history_text=_history_text(history[-8:], language),
        message=message,
    )
    route: MainChatRoute = main_route_llm.invoke(route_prompt)
    if route.route == "business_manual":
        return None

    response = llm.invoke(format_prompt(
        "business_scope_redirect",
        language=language,
        history_text=_history_text(history[-8:], language),
        message=message,
    ))
    content = response.content
    if not isinstance(content, str):
        content = "\n".join(
            str(item.get("text", item)) if isinstance(item, dict) else str(item)
            for item in content
        )
    return {
        "type": "answer",
        "answerable": True,
        "text": content,
        "options": [],
        "sources": [],
        "trace": {
            "engine": "business_scope_redirect",
            "steps": [
                {
                    "node": "classify_message",
                    "label": "Aither 업무 문의 여부 판정",
                    "input": {"message": message},
                    "output": {"route": route.route, "reason": route.reason},
                }
            ],
        },
    }


def refine_request_pair(request_row: dict, messages: list[dict], language: str = "ko") -> RefinedPair:
    conversation = "\n".join(
        (
            f"[{item.get('message_type', 'chat')}] "
            f"{item.get('author_username') or item.get('author_role', prompt_label('participant', language=language))}: "
            f"{item.get('message_text', '')}"
        )
        for item in messages
        if item.get("message_text", "").strip()
    )
    prompt = format_prompt(
        "faq_refinement",
        language=language,
        original_question=request_row.get("original_question", ""),
        refined_question=request_row.get("refined_question", ""),
        conversation=conversation or prompt_label("empty_value", language=language),
    )
    pair: RefinedPair = pair_llm.invoke(prompt)
    if not pair.answer.strip():
        pair.answer = (
            "현재 대화에서 확정된 답변은 없으며, 담당자의 추가 확인이 필요합니다."
            if language == "ko"
            else "No answer has been confirmed in the conversation; further confirmation from the assignee is required."
        )
    return pair


def _assignment_candidates() -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(f"""
                SELECT username, role, COALESCE(display_name, username) AS display_name,
                       COALESCE(department, '') AS department,
                       COALESCE(countries, ARRAY[]::text[]) AS countries,
                       COALESCE(expertise_keywords, ARRAY[]::text[]) AS expertise_keywords
                FROM {USERS}
                WHERE role IN ('Admin', 'Developer')
                ORDER BY CASE role WHEN 'Admin' THEN 2 WHEN 'Developer' THEN 1 ELSE 0 END, username
            """)
        ).mappings().all()
    return [dict(row) for row in rows]


def _screen_owner(screen_number: str) -> dict | None:
    if not screen_number:
        return None
    with engine.connect() as conn:
        row = conn.execute(
            text(f"""
                SELECT screen_number, owner_name, owner_team, country
                FROM {SCREEN_OWNERS}
                WHERE screen_number = :screen_number
                LIMIT 1
            """),
            {"screen_number": screen_number},
        ).mappings().first()
    return dict(row) if row else None


def _choose_assignee(analysis: IntakeAnalysis) -> dict:
    candidates = _assignment_candidates()
    owner = _screen_owner(analysis.screen_number)
    if owner:
        for candidate in candidates:
            if candidate["display_name"] == owner["owner_name"] or candidate["username"] == owner["owner_name"]:
                return {
                    **candidate,
                    "display_name": owner["owner_name"],
                    "department": owner["owner_team"] or candidate["department"],
                    "country": owner["country"] or analysis.country,
                    "reason": f"화면번호 {analysis.screen_number} 담당자 원장 일치",
                    "confidence": "높음",
                }

    words = {word.lower() for word in analysis.assignment_keywords if word}
    country = analysis.country.strip().lower()
    scored: list[tuple[int, dict, list[str]]] = []
    for candidate in candidates:
        matched = [
            keyword for keyword in candidate["expertise_keywords"]
            if keyword.lower() in words or any(keyword.lower() in word for word in words)
        ]
        score = len(matched) * 2
        if country and any(country == item.lower() for item in candidate["countries"]):
            score += 3
            matched.append(f"담당 국가 {analysis.country}")
        if score:
            scored.append((score, candidate, matched))
    if scored:
        score, candidate, matched = max(scored, key=lambda item: item[0])
        return {
            **candidate,
            "country": analysis.country,
            "reason": ", ".join(matched),
            "confidence": "높음" if score >= 4 else "보통",
        }

    admin = next((item for item in candidates if item["role"] == "Admin"), None)
    if not admin:
        raise RuntimeError("FAQ 요청을 우선 배정할 Admin 사용자가 없습니다.")
    return {
        **admin,
        "country": analysis.country,
        "reason": "일치하는 담당자 프로필이 없어 관리자에게 우선 배정",
        "confidence": "낮음",
    }


def _assignment_text(assignee: dict) -> str:
    return "\n".join([
        f"예상 담당자: {assignee['display_name']}",
        f"담당 국가: {assignee.get('country') or '미확인'}",
        f"담당팀: {assignee.get('department') or '미확인'}",
        f"배정 근거: {assignee['reason']}",
        f"신뢰도: {assignee['confidence']}",
    ])


def _choose_assignees(analysis: IntakeAnalysis) -> list[dict]:
    candidates = _assignment_candidates()
    preferred: list[dict] = []
    missing_names: list[str] = []
    for name in analysis.preferred_assignee_names:
        normalized = name.strip().lower()
        matched = next(
            (
                candidate for candidate in candidates
                if normalized in candidate["display_name"].lower()
                or candidate["display_name"].lower() in normalized
                or candidate["username"].lower() in normalized
            ),
            None,
        )
        if matched and all(item["username"] != matched["username"] for item in preferred):
            preferred.append({
                **matched,
                "department": analysis.preferred_team or matched["department"],
                "country": analysis.country,
                "reason": "질문자가 예상 담당자로 지정",
                "confidence": "낮음",
            })
        elif not matched:
            missing_names.append(name.strip())
    if missing_names:
        admin = next((item for item in candidates if item["role"] == "Admin"), None)
        if not admin:
            raise RuntimeError("FAQ 요청을 우선 배정할 Admin 사용자가 없습니다.")
        missing_label = ", ".join(missing_names)
        return [{
            **admin,
            "country": analysis.country,
            "department": admin["department"],
            "reason": f"사용자가 언급한 담당자({missing_label})가 users_kyj에 없어 관리자에게 우선 배정",
            "confidence": "낮음",
            "notice": f"예상 담당자 {missing_label}은(는) DB 사용자에서 찾을 수 없어 관리자에게 배정합니다.",
        }]
    return preferred or [_choose_assignee(analysis)]


def _assignment_text_many(assignees: list[dict], language: str) -> str:
    names = ", ".join(item["display_name"] for item in assignees)
    teams = ", ".join(dict.fromkeys(
        item.get("department") or "미확인" for item in assignees
    ))
    confidence = "낮음" if any(item["confidence"] == "낮음" for item in assignees) else assignees[0]["confidence"]
    if language == "en":
        return "  \n".join([
            f"Expected assignee: {names}",
            f"Responsible country: {assignees[0].get('country') or 'Unknown'}",
            f"Responsible team: {teams}",
            f"Confidence: {confidence}",
        ])
    return "  \n".join([
        f"예상 담당자: {names}",
        f"담당 국가: {assignees[0].get('country') or '미확인'}",
        f"담당팀: {teams}",
        f"신뢰도: {confidence}",
    ])


def _proposal_result(analysis: IntakeAnalysis, assignees: list[dict], language: str) -> dict:
    notice = assignees[0].get("notice")
    notice_text = f"{notice}\n\n" if notice else ""
    if language == "en":
        return {
            "type": "clarify",
            "text": (
                "I could not find an answer in the manuals or approved FAQs. "
                "Would you like to register an FAQ request with the following details for assignee review?\n\n"
                f"{notice_text}"
                f"Business scope: {analysis.target_business}  \n"
                f"Screen number: {analysis.screen_number or 'Unknown'}  \n"
                f"Refined question: {analysis.refined_question}  \n"
                f"{_assignment_text_many(assignees, language)}\n\n"
                "To change the assignee, ask to reassign it and include the username or display name."
            ),
            "options": ["Register as shown"],
            "sources": [],
        }
    return {
        "type": "clarify",
        "text": (
            "매뉴얼과 승인 FAQ에서 답을 찾지 못했습니다. "
            "아래 내용으로 FAQ를 등록하여 담당자에게 확인 요청할까요?\n\n"
            f"{notice_text}"
            f"대상업무: {analysis.target_business}  \n"
            f"화면번호: {analysis.screen_number or '미확인'}  \n"
            f"정제 질문: {analysis.refined_question}  \n"
            f"{_assignment_text_many(assignees, language)}\n\n"
            "담당자를 바꾸려면 사용자명 또는 표시 이름과 함께 담당자를 변경해 달라고 말씀해 주세요."
        ),
        "options": ["그대로 등록해줘"],
        "sources": [],
    }


def _original_question(current_message: str, history: list[dict]) -> str:
    # 같은 방에서 이전에 인사·잡담을 했더라도 현재 FAQ 문의가 시작된 지점만 찾는다.
    candidates: list[str] = []
    for item in reversed(history):
        text_value = item.get("text", "").strip()
        if not text_value:
            continue
        if item.get("role") == "user":
            candidates.append(text_value)
            continue
        is_faq_continuation = (
            text_value.startswith("답변을 다시 찾기 위해")
            or "아래 내용으로 FAQ를 등록하여 담당자에게 확인 요청할까요?" in text_value
            or "비슷한 질문이 이미 등록되어 있습니다." in text_value
        )
        if candidates and not is_faq_continuation:
            break
    return candidates[-1] if candidates else current_message


def _create_request(
    *,
    analysis: IntakeAnalysis,
    assignees: list[dict],
    original_question: str,
    room_id: int,
    username: str,
) -> int:
    primary = assignees[0]
    display_names = ", ".join(item["display_name"] for item in assignees)
    teams = ", ".join(dict.fromkeys(
        item.get("department") or "미확인" for item in assignees
    ))
    reasons = ", ".join(dict.fromkeys(item["reason"] for item in assignees))
    confidence = "낮음" if any(item["confidence"] == "낮음" for item in assignees) else primary["confidence"]
    with engine.begin() as conn:
        row = conn.execute(
            text(f"""
                INSERT INTO {FAQ_REQUESTS}
                    (requester_username, requester_chat_room_id, knowledge_search_allowed,
                     original_question, refined_question,
                     target_business, screen_number, country, assignee_username,
                     assignee_display_name, assignee_team, assignment_reason,
                     assignment_confidence, status, last_change_user)
                VALUES
                    (:requester_username, :room_id, 'Y', :original_question, :refined_question,
                     :target_business, :screen_number, :country, :assignee_username,
                     :assignee_display_name, :assignee_team, :assignment_reason,
                     :assignment_confidence, 'pending', 'system')
                RETURNING faq_id
            """),
            {
                "requester_username": username,
                "room_id": room_id,
                "original_question": original_question,
                "refined_question": analysis.refined_question,
                "target_business": analysis.target_business,
                "screen_number": analysis.screen_number or None,
                "country": analysis.country or None,
                "assignee_username": primary["username"],
                "assignee_display_name": display_names,
                "assignee_team": teams,
                "assignment_reason": reasons,
                "assignment_confidence": confidence,
            },
        ).mappings().one()
        conn.execute(
            text(f"""
                INSERT INTO {FAQ_REQUEST_MESSAGES}
                    (faq_id, faq_chat_id, author_username, author_role, message_type, message_text)
                VALUES
                    (:faq_id, 1, :username, 'requester', 'question', :question),
                    (:faq_id, 2, 'AI', 'agent', 'summary', :summary)
            """),
            {
                "faq_id": row["faq_id"],
                "username": username,
                "question": original_question,
                "summary": analysis.refined_question,
            },
        )
    return int(row["faq_id"])


def _active_request_for_room(room_id: int) -> dict | None:
    with engine.connect() as conn:
        row = conn.execute(
            text(f"""
                SELECT *
                FROM {FAQ_REQUESTS}
                WHERE requester_chat_room_id = :room_id
                  AND status IN ('pending', 'assigned')
                ORDER BY faq_id DESC
                LIMIT 1
            """),
            {"room_id": room_id},
        ).mappings().first()
    return dict(row) if row else None


def handle_pre_search_action(
    message: str,
    *,
    room_id: int,
    username: str,
    history: list[dict],
    language: str,
) -> dict | None:
    """담당자 변경과 담당자의 추가질의 답변을 지식 검색보다 먼저 처리한다."""
    last_message = history[-1] if history else {}
    is_registration_proposal = (
        last_message.get("role") == "ai"
        and any(marker in last_message.get("text", "") for marker in (
            "아래 내용으로 FAQ를 등록하여 담당자에게 확인 요청할까요?",
            "Would you like to register an FAQ request",
        ))
    )
    if is_registration_proposal:
        action = _registration_follow_up_action(message, history, language)
        if action == "cancel":
            return {
                "type": "answer",
                "text": "FAQ 등록을 취소합니다." if language == "ko" else "The FAQ registration has been cancelled.",
                "options": [],
                "sources": [],
            }
        if action == "new_message":
            # 기존 FAQ 등록 제안은 여기서 종료하고 현재 메시지를 새 메인 채팅으로 처리한다.
            return None

        analysis = _analyse_registration_revision(
            message if action == "revise" else "",
            history,
            language,
        )
        assignees = _choose_assignees(analysis)
        if action == "confirm":
            request_id = _create_request(
                analysis=analysis,
                assignees=assignees,
                original_question=_original_question(message, history),
                room_id=room_id,
                username=username,
            )
            return {
                "type": "answer",
                "text": (
                    f"FAQ에 등록 완료하였습니다. 요청 번호는 #{request_id}입니다."
                    if language == "ko"
                    else f"The FAQ request has been registered. The request number is #{request_id}."
                ),
                "options": [],
                "sources": [],
                "faq_assignment_email_request_id": request_id,
            }
        # 기타 자유입력 또는 일반 입력이 등록 내용 보완으로 판정된 경우 수정안을 다시 확인받는다.
        return _proposal_result(analysis, assignees, language)

    active = _active_request_for_room(room_id)
    if not active:
        return None

    if "담당자" in message and any(word in message for word in ("바꿔", "변경", "수정", "재배정")):
        candidates = _assignment_candidates()
        target = next(
            (
                item for item in candidates
                if item["username"].lower() in message.lower()
                or item["display_name"].lower() in message.lower()
            ),
            None,
        )
        if not target:
            return {
                "type": "clarify",
                "text": (
                    "변경할 담당자를 찾지 못했습니다. 사용자명 또는 표시 이름을 포함해 다시 말씀해 주세요."
                    if language == "ko"
                    else "I could not find the requested assignee. Please include their username or display name."
                ),
                "options": [],
                "sources": [],
            }
        with engine.begin() as conn:
            conn.execute(
                text(f"""
                    UPDATE {FAQ_REQUESTS}
                    SET assignee_username = :assignee_username,
                        assignee_display_name = :display_name,
                        assignee_team = :department,
                        assignment_reason = '질문자 요청으로 담당자 변경',
                        assignment_confidence = '높음',
                        status = 'assigned',
                        last_change_user = :changed_by,
                        last_change_date = to_char(clock_timestamp() AT TIME ZONE 'Asia/Seoul', 'YYYYMMDD'),
                        last_change_time = to_char(clock_timestamp() AT TIME ZONE 'Asia/Seoul', 'HH24MISS')
                    WHERE faq_id = :request_id
                """),
                {
                    "request_id": active["faq_id"],
                    "assignee_username": target["username"],
                    "display_name": target["display_name"],
                    "department": target["department"],
                    "changed_by": username,
                },
            )
        return {
            "type": "answer",
            "text": (
                f"FAQ 요청 #{active['faq_id']} 담당자를 {target['display_name']}({target['username']})로 변경했습니다."
                if language == "ko"
                else f"FAQ request #{active['faq_id']} was reassigned to {target['display_name']} ({target['username']})."
            ),
            "options": [],
            "sources": [],
            "faq_assignment_email_request_id": active["faq_id"],
        }

    with engine.connect() as conn:
        pending_question = conn.execute(
            text(f"""
                SELECT faq_chat_id, message_text
                FROM {FAQ_REQUEST_MESSAGES} m
                WHERE m.faq_id = :faq_id
                  AND m.message_type = 'additional_question'
                  AND NOT EXISTS (
                      SELECT 1 FROM {FAQ_REQUEST_MESSAGES} reply
                      WHERE reply.faq_id = m.faq_id
                        AND reply.faq_chat_id > m.faq_chat_id
                        AND reply.author_role = 'requester'
                  )
                ORDER BY m.faq_chat_id DESC
                LIMIT 1
            """),
            {"faq_id": active["faq_id"]},
        ).mappings().first()
    if pending_question:
        with engine.begin() as conn:
            conn.execute(
                text(f"""
                    INSERT INTO {FAQ_REQUEST_MESSAGES}
                        (faq_id, author_username, author_role, message_type, message_text)
                    VALUES (:faq_id, :username, 'requester', 'answer', :message)
                """),
                {"faq_id": active["faq_id"], "username": username, "message": message},
            )
            conn.execute(
                text(f"""
                    UPDATE {FAQ_REQUESTS}
                    SET last_change_user = :changed_by,
                        last_change_date = to_char(clock_timestamp() AT TIME ZONE 'Asia/Seoul', 'YYYYMMDD'),
                        last_change_time = to_char(clock_timestamp() AT TIME ZONE 'Asia/Seoul', 'HH24MISS')
                    WHERE faq_id = :request_id
                      AND status IN ('pending', 'assigned')
                """),
                {"request_id": active["faq_id"], "changed_by": username},
            )
        return {
            "type": "answer",
            "text": (
                f"추가 답변을 FAQ 요청 #{active['faq_id']} 담당자에게 전달했습니다."
                if language == "ko"
                else f"Your additional response was sent to the assignee for FAQ request #{active['faq_id']}."
            ),
            "options": [],
            "sources": [],
        }
    return None


def handle_unresolved_question(
    question: str,
    *,
    room_id: int,
    username: str,
    history: list[dict],
    language: str,
    conversation_context: ConversationContext,
) -> dict:
    active = _active_request_for_room(room_id)
    if active:
        waiting_text = (
            f"이미 이 채팅방에서 FAQ 요청 #{active['faq_id']}이 접수되어 담당자 답변을 기다리고 있습니다.\n\n"
            f"예상 담당자: {active['assignee_display_name'] or active['assignee_username']}\n"
            f"담당팀: {active['assignee_team'] or '미확인'}"
            if language == "ko"
            else f"FAQ request #{active['faq_id']} has already been submitted from this chat and is waiting for an assignee response.\n\n"
            f"Expected assignee: {active['assignee_display_name'] or active['assignee_username']}\n"
            f"Responsible team: {active['assignee_team'] or 'Unknown'}"
        )
        return {
            "type": "answer",
            "text": waiting_text,
            "options": [],
            "sources": [],
        }

    analysis = _analyse(question, history, language, conversation_context)
    clarification_rounds = sum(
        1
        for item in history
        if item.get("role") == "ai"
        and item.get("type") == "clarify"
        and item.get("text", "").startswith(("답변을 다시 찾기 위해", "Please provide one"))
    )

    if clarification_rounds < 2:
        fallback_questions = ([
            "해당 화면은 어떤 업무에 해당하나요? 예: 수신, 여신, 공통, 환경설정",
            "예상되는 담당자나 담당팀이 있으신가요?",
        ] if language == "ko" else [
            "Which business area does this screen belong to? For example: deposits, loans, common services, or configuration.",
            "Do you know the expected assignee or responsible team?",
        ])
        follow_up = (
            analysis.missing_information[0]
            if analysis.missing_information
            else fallback_questions[clarification_rounds]
        )
        return {
            "type": "clarify",
            "text": (
                f"답변을 다시 찾기 위해 한 가지만 더 알려주세요.\n\n{follow_up}"
                if language == "ko"
                else f"Please provide one more detail so I can search again.\n\n{follow_up}"
            ),
            "options": [],
            "sources": [],
        }

    if clarification_rounds < 3 and analysis.missing_information:
        return {
            "type": "clarify",
            "text": (
                "답변을 다시 찾기 위해 마지막으로 한 가지만 더 알려주세요.\n\n"
                f"{analysis.missing_information[0]}"
                if language == "ko"
                else "Please provide one final detail so I can search again.\n\n"
                f"{analysis.missing_information[0]}"
            ),
            "options": [],
            "sources": [],
        }

    return _proposal_result(analysis, _choose_assignees(analysis), language)
