"""아이테르 업무용 단어사전 연동 경계.

TermManager가 사용하는 ``public.terms`` 원장을 조회한다. 등록되지 않은 단어는
빈 뜻과 ``registered=False``로 반환해 채팅 workflow가 신규단어 등록 단계로
전환할 수 있게 한다.
"""

import re
from typing import TypedDict

from etc.terms import find_term


MAX_UNKNOWN_TERMS = 3
COMMON_NON_DICTIONARY_TERMS = {
    "메시지", "알림", "서비스", "업무", "화면", "화면번호", "번호", "처리", "방법", "오류",
    "질문", "답변", "등록", "국가", "담당자", "담당팀", "메뉴", "권한", "환경설정",
    "message", "notification", "service", "business", "screen", "screen number", "number", "error",
    "question", "answer", "country", "assignee", "team", "menu", "permission", "configuration",
}
COMMON_NON_DICTIONARY_TERM_KEYS = {
    value.casefold() for value in COMMON_NON_DICTIONARY_TERMS
}
SCREEN_IDENTIFIER_PATTERN = re.compile(
    r"^(?:(?:화면(?:번호)?|screen(?:number|no\.?)?)[:#]?)?"
    r"[\(\[]?#?\d+[\)\]]?(?:번|화면)?$",
    re.IGNORECASE,
)


class DictionaryEntry(TypedDict):
    term: str
    meaning: str
    registered: bool
    lookup_error: str


def is_common_term(term: str) -> bool:
    """업무 단어사전에 등록할 필요가 없는 일반 표현인지 판정한다."""
    return str(term or "").strip().casefold() in COMMON_NON_DICTIONARY_TERM_KEYS


def should_lookup_term(term: str) -> bool:
    """LLM 후보 중 실제 업무 단어사전에서 확인할 값만 허용한다."""
    normalized = re.sub(r"\s+", "", str(term or "").strip())
    if not normalized or is_common_term(term):
        return False
    # 9009, #9009, 화면번호(9009), 9009번 같은 화면 식별자는 용어가 아니다.
    if SCREEN_IDENTIFIER_PATTERN.fullmatch(normalized):
        return False
    return bool(re.search(r"[A-Za-zㄱ-ㅎㅏ-ㅣ가-힣]", normalized))


def lookup_terms(unknown_terms: list[str]) -> list[DictionaryEntry]:
    """최대 3개 단어를 받아 ``{term, meaning}`` 목록으로 반환한다."""
    normalized_terms: list[str] = []
    for value in unknown_terms:
        term = str(value).strip()
        if not term or term in normalized_terms:
            continue
        normalized_terms.append(term)
        if len(normalized_terms) >= MAX_UNKNOWN_TERMS:
            break

    entries: list[DictionaryEntry] = []
    for term in normalized_terms:
        lookup_error = ""
        try:
            matched = find_term(term)
        except Exception as exc:
            # 사전 DB의 일시 장애가 일반 FAQ 추가질문으로 잘못 이어지지 않게 한다.
            # 의미를 확인하지 못했으므로 신규단어 등록 단계에서 다시 확인받는다.
            matched = None
            lookup_error = str(exc)
        entries.append({
            "term": term,
            "meaning": str(matched.get("definition") or "") if matched else "",
            "registered": bool(matched and matched.get("definition")),
            "lookup_error": lookup_error,
        })
    return entries


def missing_terms(entries: list[DictionaryEntry]) -> list[str]:
    """사전에 뜻이 등록되지 않은 용어만 반환한다."""
    return [entry["term"] for entry in entries if not entry["registered"]]


def format_entries(entries: list[DictionaryEntry], language: str = "ko") -> str:
    """LLM 프롬프트에 그대로 넣을 수 있는 단어사전 텍스트를 만든다."""
    if not entries:
        return "(조회 대상 단어 없음)" if language == "ko" else "(No terms to look up)"

    missing_meaning = "(뜻 미등록)" if language == "ko" else "(Meaning not registered)"
    return "\n".join(
        f"- {entry['term']}: {entry['meaning'] or missing_meaning}"
        for entry in entries
    )
