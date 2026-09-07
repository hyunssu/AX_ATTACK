"""현재 사용자 메시지를 기준으로 채팅 응답 언어를 결정한다."""

import re


def _language_from_text(text: str) -> str | None:
    # 업무 질문에는 SWIFT, FAQ 같은 영문 용어가 길게 섞일 수 있으므로
    # 한글 문자가 하나라도 있으면 한국어 문장으로 판정한다.
    if re.search(r"[ㄱ-ㅎㅏ-ㅣ가-힣]", text or ""):
        return "ko"
    if re.search(r"[A-Za-z]", text or ""):
        return "en"
    return None


def detect_response_language(message: str, history: list[dict] | None = None) -> str:
    """현재 발화 언어를 사용하고, 숫자·기호뿐이면 직전 사용자 발화를 따른다."""
    detected = _language_from_text(message)
    if detected:
        return detected

    for item in reversed(history or []):
        if item.get("role") != "user":
            continue
        detected = _language_from_text(str(item.get("text", "")))
        if detected:
            return detected
    return "ko"
