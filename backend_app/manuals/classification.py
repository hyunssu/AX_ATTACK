from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from pydantic import BaseModel, Field

from llm_clients import llm, strong_llm
from manuals.prompts import SECTION_CATEGORY_PROMPT, TITLE_SUB_SUGGEST_PROMPT

SECTION_CATEGORIES = ["여신", "수신", "외환", "자금", "카드", "고객", "기타"]
MAX_CATEGORY_INPUT_CHARS = 3000
CLASSIFY_MAX_WORKERS = 5

TAXONOMY_SUBS: dict[str, list[str]] = {
    "여신": ["심사", "실행", "담보", "한도", "연체", "회수", "금리", "보증"],
    "수신": ["예금", "적금", "청약", "이자", "만기", "신탁", "펀드", "해지"],
    "외환": ["환전", "송금", "무역금융", "외화예금", "파생상품", "수출입", "LC"],
    "자금": ["조달", "운용", "유동성", "결제", "콜", "채권", "RP", "리스크"],
    "카드": ["발급", "인증", "승인", "청구", "결제", "매출", "포인트", "분실"],
    "고객": ["신규개설", "실명인증", "불만처리", "마케팅", "CRM", "휴면", "해지", "상속"],
    "기타": ["보안", "컴플라이언스", "내부통제", "IT시스템", "인사", "회계", "감사"],
}


class SectionCategory(BaseModel):
    reasoning: str = Field(description="이 섹션을 해당 분류로 고른 핵심 근거를 1문장으로")
    categories: list[Literal["여신", "수신", "외환", "자금", "카드", "고객", "기타"]] = Field(
        min_length=1,
        description="이 섹션 내용에 해당하는 업무 분류를 하나 이상. 명확히 맞는 게 없으면 '기타'"
    )
    sub_category: str | None = Field(
        default=None,
        description="첫 번째 대분류(categories[0])에 해당하는 소분류. 소분류 목록 중 하나를 선택하거나 맞는 것이 없으면 null"
    )
    confidence: Literal["high", "low"] = Field(
        description="분류에 대한 확신도. 분류가 애매하면 'low'"
    )


section_category_llm = llm.with_structured_output(SectionCategory)
section_category_llm_strong = strong_llm.with_structured_output(SectionCategory)


class SubSuggestion(BaseModel):
    sub_category: str | None = Field(
        default=None,
        description="소분류 목록 중 가장 적합한 하나. 판단하기 어렵거나 맞는 것이 없으면 null",
    )


sub_suggestion_llm = llm.with_structured_output(SubSuggestion)


def suggest_sub_from_title(title: str, category: str) -> str | None:
    """매뉴얼 제목만으로 소분류를 추천한다. 확신이 없으면 None을 반환한다."""
    subs = TAXONOMY_SUBS.get(category, [])
    if not subs:
        return None
    try:
        prompt = TITLE_SUB_SUGGEST_PROMPT.format(
            category=category,
            subs=", ".join(subs),
            title=title,
        )
        result = sub_suggestion_llm.invoke(prompt)
        if result.sub_category and result.sub_category in subs:
            return result.sub_category
        return None
    except Exception:
        return None


def _build_extra_subs_addendum(extra_subs: dict[str, list[str]]) -> str:
    """custom trail 등 추가 소분류를 프롬프트 끝에 붙인다."""
    if not extra_subs:
        return ""
    lines = []
    for cat, subs in extra_subs.items():
        new_subs = [s for s in subs if s not in TAXONOMY_SUBS.get(cat, [])]
        if new_subs:
            lines.append(f"- {cat}: {', '.join(new_subs)}")
    if not lines:
        return ""
    return (
        "\n\n[추가 소분류 안내]\n"
        "아래 소분류도 기존 목록에 포함된 것으로 간주하고 선택에 활용하세요.\n"
        + "\n".join(lines)
    )


def _run_section_classifier(model, title: str, content: str, prompt_addendum: str = "") -> SectionCategory:
    prompt = SECTION_CATEGORY_PROMPT.format(
        section_title=title or "(제목 없음)",
        section_content=content,
    ) + prompt_addendum
    return model.invoke(prompt)


def _classify_section(title: str, content: str, extra_subs: dict[str, list[str]] | None = None) -> tuple[list[str], str | None, bool]:
    """저비용 모델 + 잘린 내용으로 1차 분류만 수행한다. confidence가 낮으면 needs_review=True로 표시하고,
    실제 재분류(강한 모델 + 전체 내용)는 검토 모달에서 사용자가 명시적으로 요청할 때 reclassify_section_strong()으로 수행한다."""
    addendum = _build_extra_subs_addendum(extra_subs or {})
    try:
        result = _run_section_classifier(section_category_llm, title, content[:MAX_CATEGORY_INPUT_CHARS], addendum)
        return result.categories, result.sub_category, result.confidence != "high"
    except Exception:
        return ["기타"], None, True


def reclassify_section_strong(title: str, content: str) -> tuple[list[str], str | None, bool]:
    """검토 모달의 '정밀 재분류 요청' 버튼용: 강한 모델 + 전체 내용으로 다시 분류한다."""
    try:
        result = _run_section_classifier(section_category_llm_strong, title, content)
        return result.categories, result.sub_category, result.confidence != "high"
    except Exception:
        return ["기타"], None, True


def classify_sections(sections: list[dict], extra_subs: dict[str, list[str]] | None = None) -> list[dict]:
    """split_into_major_sections() 결과에 categories, sub_category, needs_review를 부여한다.
    섹션마다 LLM 호출이 필요해서, 병렬로 분류한다."""
    with ThreadPoolExecutor(max_workers=CLASSIFY_MAX_WORKERS) as executor:
        results = list(executor.map(
            lambda section: _classify_section(section["title"], section["content"], extra_subs),
            sections,
        ))
    return [
        {**section, "categories": categories, "sub_category": sub_category, "needs_review": needs_review}
        for section, (categories, sub_category, needs_review) in zip(sections, results)
    ]
