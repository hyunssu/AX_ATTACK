"""승인 FAQ와 매뉴얼 RAG를 모두 평가하고 최신 근거 답변을 선택한다."""

from datetime import datetime
from zoneinfo import ZoneInfo

import faq_search
import rag
import rag_graph
from config import KNOWLEDGE_DATE_TIMEZONE


def _date_key(value: str | None) -> float:
    if not value:
        return float("-inf")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(KNOWLEDGE_DATE_TIMEZONE))
    return parsed.timestamp()


def _manual_answer(question: str, manual_id: int | None, history: list[dict], engine_name: str) -> dict:
    if engine_name == "langgraph":
        return rag_graph.answer_question(question, manual_id, history, force_search=True)
    # Dify를 선택한 과거 채팅방도 점수·기준일 비교가 가능한 내부 RAG로 처리한다.
    return rag.answer_question(question, manual_id, history, force_search=True)


def answer_from_latest_knowledge(
    question: str,
    *,
    manual_id: int | None,
    history: list[dict],
    engine_name: str,
) -> dict:
    """FAQ와 매뉴얼을 모두 실행하고 기준치·기준일로 최종 답변을 결정한다."""
    try:
        faq_evaluation = faq_search.search_approved_faq(question)
    except Exception as exc:
        faq_evaluation = {"matched": False, "reason": "search_error", "error": str(exc), "result": None}

    try:
        manual_result = _manual_answer(question, manual_id, history, engine_name)
        manual_evaluation = manual_result.get("knowledge_match") or {
            "matched": False,
            "reason": "missing_match_metadata",
        }
    except Exception as exc:
        manual_result = None
        manual_evaluation = {"matched": False, "reason": "search_error", "error": str(exc)}

    faq_matched = bool(faq_evaluation.get("matched") and faq_evaluation.get("result"))
    manual_matched = bool(manual_evaluation.get("matched") and manual_result)

    if faq_matched and manual_matched:
        faq_is_latest = _date_key(faq_evaluation.get("basis_date")) >= _date_key(
            manual_evaluation.get("basis_date")
        )
        selected_kind = "faq" if faq_is_latest else "manual"
        selected = faq_evaluation["result"] if faq_is_latest else manual_result
        prefix = "**가장 최근 업데이트된 정보를 기준으로 답변합니다.**"
    elif faq_matched:
        selected_kind = "faq"
        selected = faq_evaluation["result"]
        prefix = "**승인 FAQ를 기준으로 답변합니다.**"
    elif manual_matched:
        selected_kind = "manual"
        selected = manual_result
        prefix = "**매뉴얼을 기준으로 답변합니다.**"
    else:
        has_search_error = (
            faq_evaluation.get("reason") == "search_error"
            or manual_evaluation.get("reason") == "search_error"
        )
        message = (
            "FAQ 또는 매뉴얼 검색 중 오류가 발생하여 신뢰할 수 있는 답변을 만들지 못했습니다."
            if has_search_error
            else "승인 FAQ와 매뉴얼 모두 검색 기준치에 미달하여 해당 정보를 찾지 못했습니다."
        )
        return {
            "type": "answer",
            "text": message,
            "options": [],
            "sources": [],
            "trace": {
                "engine": "knowledge_router",
                "steps": [
                    {
                        "node": "compare_knowledge",
                        "label": "FAQ·매뉴얼 검색 결과 비교",
                        "input": {"question": question},
                        "output": {
                            "selected": None,
                            "faq": _evaluation_for_trace(faq_evaluation),
                            "manual": _evaluation_for_trace(manual_evaluation),
                        },
                    }
                ],
            },
        }

    comparison_step = {
        "node": "compare_knowledge",
        "label": "FAQ·매뉴얼 기준치·기준일 비교",
        "input": {"question": question},
        "output": {
            "selected": selected_kind,
            "selection_rule": "기준치를 충족한 결과 중 기준일이 가장 최근인 결과",
            "faq": _evaluation_for_trace(faq_evaluation),
            "manual": _evaluation_for_trace(manual_evaluation),
        },
    }
    selected_trace = selected.get("trace") or {"engine": selected_kind, "steps": []}
    return {
        "type": "answer",
        "text": f"{prefix}\n\n{selected['text']}",
        "options": [],
        "sources": selected.get("sources") or [],
        "trace": {
            "engine": "knowledge_router",
            "steps": (selected_trace.get("steps") or []) + [comparison_step],
        },
    }


def _evaluation_for_trace(evaluation: dict) -> dict:
    return {
        "matched": bool(evaluation.get("matched")),
        "reason": evaluation.get("reason"),
        "score": evaluation.get("score"),
        "threshold": evaluation.get("threshold"),
        "basis_date": evaluation.get("basis_date"),
        "error": evaluation.get("error"),
    }
