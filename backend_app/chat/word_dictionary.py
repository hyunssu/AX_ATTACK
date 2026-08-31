"""아이테르 업무용 단어사전 연동 경계.

현재는 실제 사전 저장소가 정해지지 않았으므로 입력 단어를 그대로 반환하고
뜻은 빈 문자열로 둔다. 이후 DB/API/파일 사전을 붙일 때 lookup_terms 내부만
교체하면 채팅 지식검색 흐름은 그대로 유지된다.
"""

from typing import TypedDict


MAX_UNKNOWN_TERMS = 3


class DictionaryEntry(TypedDict):
    term: str
    meaning: str


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

    # TODO: 실제 단어사전 저장소가 정해지면 여기에서 meaning을 조회한다.
    return [{"term": term, "meaning": ""} for term in normalized_terms]


def format_entries(entries: list[DictionaryEntry], language: str = "ko") -> str:
    """LLM 프롬프트에 그대로 넣을 수 있는 단어사전 텍스트를 만든다."""
    if not entries:
        return "(조회 대상 단어 없음)" if language == "ko" else "(No terms to look up)"

    missing_meaning = "(뜻 미등록)" if language == "ko" else "(Meaning not registered)"
    return "\n".join(
        f"- {entry['term']}: {entry['meaning'] or missing_meaning}"
        for entry in entries
    )
