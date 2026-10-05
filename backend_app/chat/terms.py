"""아이테르 업무용 단어사전 연동 경계.

TermManager가 사용하는 ``public.terms`` 원장을 조회한다. 등록되지 않은 단어는
빈 뜻과 ``registered=False``로 반환해 채팅 workflow가 신규단어 등록 단계로
전환할 수 있게 한다.
"""

import json
import re
from typing import TypedDict

from etc.terms import find_term


MAX_UNKNOWN_TERMS = 3
COMMON_NON_DICTIONARY_TERMS = {
    "메시지", "알림", "서비스", "업무", "화면", "화면번호", "번호", "처리", "방법", "오류",
    "질문", "답변", "등록", "국가", "담당자", "담당팀", "메뉴", "권한", "환경설정",
    "message", "notification", "service", "business", "screen", "screen number", "number", "error",
    "question", "answer", "country", "assignee", "team", "menu", "permission", "configuration",
    "상환대출", "대출상환", "상환", "대출", "디폴트", "예금", "적금", "수신", "여신", "금리",
    "이자", "원금", "원리금", "담보", "신용", "연체", "만기", "중도상환", "송금", "환율", "외환",
    "입금", "출금", "계좌", "잔액", "채무", "채권", "보증", "카드", "결제", "수수료",
    "loan", "repayment", "default", "deposit", "interest", "swift", "iban", "kyc", "aml",
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


def should_lookup_term(term: str, original_question: str | None = None) -> bool:
    """LLM 후보 중 실제 업무 단어사전에서 확인할 값만 허용한다."""
    normalized = re.sub(r"\s+", "", str(term or "").strip())
    if not normalized or is_common_term(term):
        return False
    if is_common_term(normalized):
        return False
    if original_question is not None:
        # LLM이 만든 표현이나 과거 대화의 용어는 후보로 허용하지 않는다.
        if not re.search(r"(?<![A-Za-z0-9])" + re.escape(term.strip()) + r"(?![A-Za-z0-9])", original_question, re.I):
            return False
        if re.search(re.escape(term.strip()) + r"\s*(?:프로|수석|책임|선임|대리|과장|차장|부장|님|씨)", original_question):
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
            "registered": bool(matched),
            "lookup_error": lookup_error,
        })
    return entries


def missing_terms(entries: list[DictionaryEntry]) -> list[str]:
    """사전에 뜻이 등록되지 않은 용어만 반환한다."""
    return [entry["term"] for entry in entries if not entry["registered"] and not entry["lookup_error"]]


def definition_subject(question: str) -> str | None:
    """정의 질문의 대상만 추출한다. 검색질문 요약으로 대상을 바꾸지 않는다."""
    value = str(question or "").strip().rstrip("?？!.。 ")
    patterns = (
        r"^(.+?)(?:이|가)\s*(?:뭐야|뭐예요|무엇인가요|무엇이야|뭔가요)$",
        r"^(.+?)(?:이란|란)(?:\s*(?:뭐야|무엇인가요|무엇입니까))?$",
        r"^(.+?)(?:에\s*대해|에\s*대해서)\s*(?:알려줘|알려주세요|설명해줘|설명해주세요)$",
        r"^(?:what\s+is|what\s+does)\s+(.+?)(?:\s+mean)?$",
        r"^(?:tell\s+me\s+about|explain|define)\s+(.+)$",
    )
    for pattern in patterns:
        matched = re.fullmatch(pattern, value, re.I)
        if matched:
            subject = matched.group(1).strip().strip('\"\'` ')
            return subject if subject else None
    return None


def answer_definition(question: str, language: str = "ko") -> dict | None:
    subject = definition_subject(question)
    if not subject:
        return None
    matched = find_term(subject)
    if not matched or not str(matched.get("definition") or "").strip():
        return None
    name = str(matched["term_name"])
    keyword = str(matched.get("keyword") or "")
    definition = str(matched["definition"])
    return {
        "type": "answer", "answerable": True,
        "text": (
            f"해당 질문에 대한 내용을 신규단어 원장에서 확인하였습니다.\n\n단어: {name}\n유의어: {keyword or '없음'}\n설명: {definition}"
            if language == "ko" else
            f"I found information for this question in the terminology registry.\n\nTerm: {name}\nSynonyms: {keyword or 'None'}\nDescription: {definition}"
        ),
        "options": [],
        "sources": [{"kind": "term", "title": name, "detail": keyword, "created_at": str(matched.get("created_at") or "") or None}],
        "trace": {"engine": "terms", "steps": [{"node": "lookup_definition", "label": "신규단어 원장 정의 조회", "input": {"subject": subject}, "output": {"term_id": matched["term_id"], "matched": True}}]},
    }


def format_entries(entries: list[DictionaryEntry], language: str = "ko") -> str:
    """문장에 병합하지 않고 term/meaning JSON 배열로 전달한다. 미등록 뜻은 null."""
    return json.dumps([
        {"term": entry["term"], "meaning": entry["meaning"] if entry["registered"] and entry["meaning"] else None}
        for entry in entries
    ], ensure_ascii=False)
