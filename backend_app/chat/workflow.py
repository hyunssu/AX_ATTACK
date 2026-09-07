"""Ask AI 거래를 next_action 기반으로 실행하는 작은 상태머신."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

import screen_owners
from faq import intake as faq_intake
from faq import knowledge as knowledge_router


class ChatAction(str, Enum):
    SUMMARIZE_CONTEXT = "summarize_context"
    HANDLE_PRE_SEARCH = "handle_pre_search"
    ROUTE_BUSINESS = "route_business"
    HANDLE_OWNER_CHANGE = "handle_owner_change"
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
    next_action: ChatAction = ChatAction.SUMMARIZE_CONTEXT
    conversation_context: faq_intake.ConversationContext | None = None
    result: dict | None = None
    transitions: list[dict] = field(default_factory=list)


ActionHandler = Callable[[ChatWorkflowState], ChatAction]


def summarize_context(state: ChatWorkflowState) -> ChatAction:
    state.conversation_context = faq_intake.summarize_conversation_context(
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
    state.result = faq_intake.redirect_non_business_chat_if_applicable(
        state.message,
        state.history,
        state.language,
        state.conversation_context,
    )
    return ChatAction.COMPLETE if state.result is not None else ChatAction.HANDLE_OWNER_CHANGE


def handle_owner_change(state: ChatWorkflowState) -> ChatAction:
    state.result = screen_owners.answer_screen_owner_request(
        state.message,
        room_id=state.room_id,
        username=state.username,
        history=state.history,
        # 담당자 조회는 FAQ·매뉴얼 지식검색으로 보내고 확인된 변경만 여기서 처리한다.
        allow_lookup=False,
    )
    return ChatAction.COMPLETE if state.result is not None else ChatAction.SEARCH_KNOWLEDGE


def search_knowledge(state: ChatWorkflowState) -> ChatAction:
    context_summary = (
        state.conversation_context.summary if state.conversation_context is not None else ""
    )
    state.result = knowledge_router.answer_from_latest_knowledge(
        state.message,
        manual_id=state.manual_id,
        history=state.history,
        language=state.language,
        conversation_context=context_summary,
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
    return ChatAction.COMPLETE


# action 이름과 실제 실행 함수의 연결점이다. 새 단계를 추가할 때 이 registry에 등록한다.
ACTION_HANDLERS: dict[ChatAction, ActionHandler] = {
    ChatAction.SUMMARIZE_CONTEXT: summarize_context,
    ChatAction.HANDLE_PRE_SEARCH: handle_pre_search,
    ChatAction.ROUTE_BUSINESS: route_business,
    ChatAction.HANDLE_OWNER_CHANGE: handle_owner_change,
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
