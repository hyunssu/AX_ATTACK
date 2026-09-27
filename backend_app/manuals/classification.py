from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from pydantic import BaseModel, Field

from llm_clients import call_llm, llm, strong_llm
from manuals.prompts import SECTION_CATEGORY_PROMPT, TITLE_SUB_SUGGEST_PROMPT

MAX_CATEGORY_INPUT_CHARS = 3000
CLASSIFY_MAX_WORKERS = 5

_CATEGORY_DEFINITIONS = {
    "여신": "대출, 신용평가, 담보, 대출 심사/실행 (예: 주택담보대출 승인 절차, 신용평가 조회)",
    "수신": "예금, 적금, 입출금 계좌 (예: 정기예금 해지, 통장 재발급)",
    "외환": "환전, 해외송금, 외화 계좌 (예: 외화 송금 한도, 환전 수수료)",
    "자금": "자금관리, 유동성, 기업/법인 자금 결제 (예: 법인 자금 집행 승인, 유동성 리스크 관리)",
    "카드": (
        "신용카드/체크카드 발급·분실·이용, 카드론 (예: 카드 재발급 절차, 카드론 한도) "
        "— 대출 성격이 있어도 카드 상품 자체에 관한 내용이면 여신이 아니라 카드로 분류"
    ),
    "고객": "고객 상담, CS, 민원 처리 (예: 고객 불만 접수 프로세스, 상담 응대 매뉴얼)",
    "기타": "위 분류 중 어디에도 명확히 속하지 않는 내용",
}


def _category_definition(category: str) -> str:
    return _CATEGORY_DEFINITIONS.get(category, f"'{category}' 업무와 관련된 내용")


def build_subs_section(subs: list[str]) -> str:
    """해당 카테고리의 소분류 목록을 프롬프트용 텍스트로 변환한다."""
    if not subs:
        return "[소분류 목록]\n정의된 소분류가 없습니다. sub_category는 null로 반환하세요."
    return "[소분류 목록]\n" + ", ".join(subs)


class SectionCategory(BaseModel):
    reasoning: str = Field(description="이 판단의 핵심 근거를 1문장으로")
    in_category: bool = Field(
        description="이 섹션 내용이 실제로 해당 업무 카테고리에 속하는지 여부"
    )
    sub_category: str | None = Field(
        default=None,
        description="in_category가 true일 때, 소분류 목록 중 하나를 선택하거나 맞는 것이 없으면 null"
    )
    confidence: Literal["high", "low"] = Field(
        description="판단에 대한 확신도. 애매하면 'low'"
    )


section_category_llm = llm.with_structured_output(SectionCategory)
section_category_llm_strong = strong_llm.with_structured_output(SectionCategory)


class SubSuggestion(BaseModel):
    sub_category: str | None = Field(
        default=None,
        description="소분류 목록 중 가장 적합한 하나. 판단하기 어렵거나 맞는 것이 없으면 null",
    )


sub_suggestion_llm = llm.with_structured_output(SubSuggestion)


def suggest_sub_from_title(title: str, category: str, subs: list[str]) -> str | None:
    """매뉴얼 제목만으로 소분류를 추천한다. 확신이 없으면 None을 반환한다."""
    if not subs:
        return None
    try:
        prompt = TITLE_SUB_SUGGEST_PROMPT.format(
            category=category,
            subs=", ".join(subs),
            title=title,
        )
        result = call_llm(sub_suggestion_llm, prompt, label="sub_suggest")
        if result.sub_category and result.sub_category in subs:
            return result.sub_category
        return None
    except Exception:
        return None


def _run_section_classifier(model, category: str, title: str, content: str, subs_section: str) -> SectionCategory:
    prompt = SECTION_CATEGORY_PROMPT.format(
        category=category,
        category_definition=_category_definition(category),
        subs_section=subs_section,
        section_title=title or "(제목 없음)",
        section_content=content,
    )
    return call_llm(model, prompt, label="classify_section")


def _classify_section(category: str, title: str, content: str, subs_section: str) -> tuple[bool, str | None, bool]:
    """저비용 모델 + 잘린 내용으로 1차 판단만 수행한다. confidence가 낮으면 needs_review=True로 표시하고,
    실제 재분류(강한 모델 + 전체 내용)는 검토 모달에서 사용자가 명시적으로 요청할 때 reclassify_section_strong()으로 수행한다."""
    try:
        result = _run_section_classifier(section_category_llm, category, title, content[:MAX_CATEGORY_INPUT_CHARS], subs_section)
        return result.in_category, result.sub_category, result.confidence != "high"
    except Exception:
        return True, None, True


def reclassify_section_strong(category: str, title: str, content: str, subs_section: str = "") -> tuple[bool, str | None, bool]:
    """검토 모달의 '정밀 재분류 요청' 버튼용: 강한 모델 + 전체 내용으로 다시 분류한다."""
    try:
        result = _run_section_classifier(section_category_llm_strong, category, title, content, subs_section)
        return result.in_category, result.sub_category, result.confidence != "high"
    except Exception:
        return True, None, True


def classify_sections(sections: list[dict], category: str, subs: list[str] | None = None) -> list[dict]:
    """split_into_major_sections() 결과에 고정된 category, 분류된 sub_category/needs_review를 부여하고,
    실제로 해당 카테고리 업무 내용인 섹션만 기본 포함(include)한다.
    섹션마다 LLM 호출이 필요해서, 병렬로 분류한다."""
    subs_section = build_subs_section(subs or [])
    with ThreadPoolExecutor(max_workers=CLASSIFY_MAX_WORKERS) as executor:
        results = list(executor.map(
            lambda section: _classify_section(category, section["title"], section["content"], subs_section),
            sections,
        ))
    return [
        {
            **section,
            "categories": [category],
            "sub_category": sub_category,
            "needs_review": needs_review,
            "include": in_category,
        }
        for section, (in_category, sub_category, needs_review) in zip(sections, results)
    ]
