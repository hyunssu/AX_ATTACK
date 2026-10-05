"""Ask AI 거래를 next_action 기반으로 실행하는 작은 상태머신."""

import re

from pydantic import BaseModel, Field
from llm_clients import llm
from chat.prompts import format_prompt, prompt_label, schema_description
from chat import terms
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from faq import intake as faq_intake
from faq import knowledge as knowledge_router


class ConversationContext(BaseModel):
    final_user_question: str = Field(
        default="", description="현재 사용자 메시지와 이전 맥락을 반영한 최종 독립형 질문. 답변이나 추측은 포함하지 않는다."
    )
    summary: str = Field(description=schema_description("conversation.summary"))
    active_business_question: str = Field(
        default="", description=schema_description("conversation.active_business_question")
    )
    confirmed_facts: list[str] = Field(
        default_factory=list, description=schema_description("conversation.confirmed_facts")
    )
    target_country: str = Field(
        default="", description=schema_description("conversation.target_country")
    )
    business_context: str = Field(
        default="", description=schema_description("conversation.business_context")
    )
    expected_assignee: str = Field(
        default="", description=schema_description("conversation.expected_assignee")
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

    def to_search_text(self, language: str) -> str:
        return format_conversation_context_for_search(self, language)


conversation_context_llm = llm.with_structured_output(ConversationContext)


def summarize_conversation_context(
    message: str,
    history: list[dict],
    language: str,
) -> ConversationContext:
    """Create one reusable context snapshot for every LLM stage in this turn."""
    prompt = format_prompt(
        "conversation_context_summary",
        language=language,
        history_text="\n".join(
            f"{item.get('role')}: {item.get('text', '')}" for item in history
        ) or prompt_label("empty_history", language=language),
        message=message,
    )
    try:
        context: ConversationContext = conversation_context_llm.invoke(prompt)
        return _normalize_conversation_context(context, message, history, language)
    except Exception:
        last_ai = next((item for item in reversed(history) if item.get("role") == "ai"), {})
        is_followup = bool(last_ai and last_ai.get("type") == "clarify")
        prior_user = next((item for item in history if item.get("role") == "user"), {})
        context = ConversationContext(
            final_user_question=message,
            summary=" | ".join(
                value for value in (prior_user.get("text", ""), message) if value
            ) or message,
            active_business_question=prior_user.get("text", "") if is_followup else "",
            confirmed_facts=[],
            target_country="",
            business_context="",
            expected_assignee="",
            pending_clarification=last_ai.get("text", "") if is_followup else "",
            is_aither_business_context=is_followup,
            current_message_is_followup=is_followup,
        )
        return _normalize_conversation_context(context, message, history, language)


def _explicit_intake_answers(history: list[dict], message: str, language: str) -> dict[str, str]:
    """추가질문 답변을 복원한다. 모름은 정규화하고 나머지는 원문을 보존한다."""
    fields: dict[str, str] = {}
    pending_field = None
    for item in [*history, {"role": "user", "text": message}]:
        raw_text = str(item.get("text") or "")
        text = raw_text.strip()
        if item.get("role") == "ai":
            pending_field = None
            if not text.startswith(("답변을 다시 찾기 위해", "보다 정확한 검색을 위해", "Please provide one")):
                fields.clear()
                continue
            if re.search(r"담당자|담당팀|assignee|team", text, re.I):
                pending_field = "expected_assignee"
            elif re.search(r"국가|country", text, re.I):
                pending_field = "target_country"
            elif re.search(r"업무|business", text, re.I):
                pending_field = "business_context"
        elif item.get("role") == "user" and pending_field:
            # 짧은 명시적 모름 응답만 인정하여 새 질문/부정문을 잘못 분류하지 않는다.
            if re.fullmatch(
                r"\s*(?:(?:잘|아직|저도|저는|그건)\s*)*(?:몰라(?:요|요오)?|모름|모르겠(?:어|어요|습니다)|모르(?:는데요|겠는데요)|알\s*수\s*없(?:어|어요|습니다)|(?:i\s+)?(?:don't|do\s+not)\s+know|unknown)\s*[.!?。]*\s*",
                text, re.I,
            ):
                fields[pending_field] = "모름" if language == "ko" else "Unknown"
            else:
                fields[pending_field] = raw_text
            pending_field = None
    return fields


def _normalize_conversation_context(
    context: ConversationContext,
    message: str,
    history: list[dict],
    language: str,
) -> ConversationContext:
    """LLM이 미응답 항목에 임의로 넣은 '모름'을 제거하고 업무 맥락을 보완한다."""
    explicit_answers = _explicit_intake_answers(history, message, language)
    unknown_values = {"모름", "모르겠음", "미확인", "알 수 없음", "unknown", "n/a"}
    for field_name in ("target_country", "business_context", "expected_assignee"):
        value = str(getattr(context, field_name, "") or "").strip()
        if field_name in explicit_answers:
            setattr(context, field_name, explicit_answers[field_name])
        elif value.lower() in unknown_values and not re.search(
            r"몰라|모름|모르|알\s*수\s*없|don't\s+know|do not know|unknown",
            message, re.I,
        ):
            setattr(context, field_name, "")

    if not context.business_context.strip() and context.active_business_question.strip():
        context.business_context = context.active_business_question.strip()
    if context.pending_clarification.strip().lower() in unknown_values:
        context.pending_clarification = ""

    generic_summary_prefixes = (
        "최초 업무 질문의 목적을 유지하면서",
        "Preserve the goal of the original business question",
    )
    if not context.summary.strip() or context.summary.startswith(generic_summary_prefixes):
        if language == "ko":
            facts = [
                f"문의 업무: {context.business_context}" if context.business_context else "",
                f"대상국가: {context.target_country}" if context.target_country else "",
                f"예상담당자/담당팀: {context.expected_assignee}" if context.expected_assignee else "",
            ]
        else:
            facts = [
                f"Business: {context.business_context}" if context.business_context else "",
                f"Target country: {context.target_country}" if context.target_country else "",
                f"Expected assignee/team: {context.expected_assignee}" if context.expected_assignee else "",
            ]
        context.summary = " | ".join(value for value in facts if value) or message
    context.final_user_question = context.final_user_question.strip() or message
    return context


def format_conversation_context_for_search(
    context: ConversationContext,
    language: str,
) -> str:
    """RAG 질문 정제에 대화 요약과 세 가지 접수정보를 함께 전달한다."""
    if language == "ko":
        labels = ("대상국가", "업무", "예상담당자/담당팀")
        empty = "미확인"
    else:
        labels = ("Target country", "Business", "Expected assignee/team")
        empty = "Unknown"
    return "\n".join([
        context.summary,
        f"{'최종 유저 질문' if language == 'ko' else 'Final user question'}: {context.final_user_question}",
        f"{labels[0]}: {context.target_country or empty}",
        f"{labels[1]}: {context.business_context or empty}",
        f"{labels[2]}: {context.expected_assignee or empty}",
    ])


class ChatAction(str, Enum):
    SUMMARIZE_CONTEXT = "summarize_context"
    HANDLE_PRE_SEARCH = "handle_pre_search"
    ROUTE_BUSINESS = "route_business"
    SEARCH_KNOWLEDGE = "search_knowledge"
    HANDLE_UNRESOLVED = "handle_unresolved"
    COMPLETE = "complete"


@dataclass
class ChatWorkflowState:
    message: str
    room_id: int
    username: str
    history: list[dict]
    language: str
    manual_id: int | None = None
    ignored_unknown_terms: list[str] = field(default_factory=list)
    next_action: ChatAction = ChatAction.SUMMARIZE_CONTEXT
    conversation_context: ConversationContext | None = None
    result: dict | None = None
    transitions: list[dict] = field(default_factory=list)


ActionHandler = Callable[[ChatWorkflowState], ChatAction]


def summarize_context(state: ChatWorkflowState) -> ChatAction:
    state.conversation_context = summarize_conversation_context(
        state.message,
        state.history,
        state.language,
    )
    return ChatAction.HANDLE_PRE_SEARCH


def handle_pre_search(state: ChatWorkflowState) -> ChatAction:
    state.result = faq_intake.handle_pre_search_action(
        state.message,
        room_id=state.room_id,
        username=state.username,
        history=state.history,
        language=state.language,
    )
    return ChatAction.COMPLETE if state.result is not None else ChatAction.ROUTE_BUSINESS


def route_business(state: ChatWorkflowState) -> ChatAction:
    if terms.definition_subject(state.message):
        return ChatAction.SEARCH_KNOWLEDGE
    state.result = faq_intake.redirect_non_business_chat_if_applicable(
        state.message,
        state.history,
        state.language,
        state.conversation_context,
    )
    return ChatAction.COMPLETE if state.result is not None else ChatAction.SEARCH_KNOWLEDGE



def search_knowledge(state: ChatWorkflowState) -> ChatAction:
    context_summary = (
        format_conversation_context_for_search(
            state.conversation_context,
            state.language,
        )
        if state.conversation_context is not None
        else ""
    )
    latest_ai = next(
        (item for item in reversed(state.history) if item.get("role") == "ai"),
        {},
    )
    latest_trace = latest_ai.get("trace") or {}
    after_intake_clarification = bool(
        latest_trace.get("intake_clarification")
        or str(latest_ai.get("text") or "").startswith((
            "답변을 다시 찾기 위해",
            "보다 정확한 검색을 위해",
            "Please provide one",
        ))
    )
    allow_term_registration = not (
        after_intake_clarification
        and state.conversation_context is not None
        and state.conversation_context.is_aither_business_context
    )
    state.result = knowledge_router.answer_from_latest_knowledge(
        state.message,
        manual_id=state.manual_id,
        history=state.history,
        language=state.language,
        conversation_context=context_summary,
        ignored_unknown_terms=state.ignored_unknown_terms,
        allow_term_registration=allow_term_registration,
    )
    if state.result.get("answerable", True):
        return ChatAction.COMPLETE
    return ChatAction.HANDLE_UNRESOLVED


def handle_unresolved(state: ChatWorkflowState) -> ChatAction:
    if state.conversation_context is None:
        raise RuntimeError("미해결 질문 처리에 필요한 대화 맥락이 없습니다.")
    state.result = faq_intake.handle_unresolved_question(
        state.message,
        room_id=state.room_id,
        username=state.username,
        history=state.history,
        language=state.language,
        conversation_context=state.conversation_context,
    )
    if (
        state.result.get("type") == "clarify"
        and str(state.result.get("text") or "").startswith((
            "답변을 다시 찾기 위해",
            "보다 정확한 검색을 위해",
            "Please provide one",
        ))
    ):
        state.result["trace"] = {
            **(state.result.get("trace") or {}),
            "intake_clarification": True,
        }
    return ChatAction.COMPLETE


# action 이름과 실제 실행 함수의 연결점이다. 새 단계를 추가할 때 이 registry에 등록한다.
ACTION_HANDLERS: dict[ChatAction, ActionHandler] = {
    ChatAction.SUMMARIZE_CONTEXT: summarize_context,
    ChatAction.HANDLE_PRE_SEARCH: handle_pre_search,
    ChatAction.ROUTE_BUSINESS: route_business,
    ChatAction.SEARCH_KNOWLEDGE: search_knowledge,
    ChatAction.HANDLE_UNRESOLVED: handle_unresolved,
}


def run_chat_workflow(
    *,
    message: str,
    room_id: int,
    username: str,
    history: list[dict],
    language: str,
    manual_id: int | None = None,
    ignored_unknown_terms: list[str] | None = None,
    max_steps: int = 12,
) -> ChatWorkflowState:
    """각 action이 지정한 다음 함수를 registry에서 찾아 루프로 실행한다."""
    state = ChatWorkflowState(
        message=message,
        room_id=room_id,
        username=username,
        history=history,
        language=language,
        manual_id=manual_id,
        ignored_unknown_terms=list(ignored_unknown_terms or []),
    )

    for sequence in range(1, max_steps + 1):
        current_action = state.next_action
        if current_action == ChatAction.COMPLETE:
            break

        handler = ACTION_HANDLERS.get(current_action)
        if handler is None:
            raise RuntimeError(f"등록되지 않은 채팅 action입니다: {current_action}")

        next_action = handler(state)
        state.transitions.append({
            "node": f"chat_workflow.{current_action.value}",
            "label": f"거래 단계: {current_action.value}",
            "input": {
                "sequence": sequence,
                "action": current_action.value,
                "handler": handler.__name__,
            },
            "output": {
                "next_action": next_action.value,
                "resolved": state.result is not None,
            },
        })
        state.next_action = next_action

    if state.next_action != ChatAction.COMPLETE:
        raise RuntimeError(
            f"채팅 workflow가 최대 실행 횟수({max_steps}) 안에 완료되지 않았습니다: "
            f"{state.next_action.value}"
        )
    if state.result is None:
        raise RuntimeError("채팅 workflow가 응답 없이 완료되었습니다.")
    return state
