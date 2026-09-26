from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from pydantic import BaseModel, Field

from llm_clients import call_llm, llm, strong_llm
from manuals.prompts import SECTION_CATEGORY_PROMPT, TITLE_SUB_SUGGEST_PROMPT

_DEFAULT_CATEGORIES = ["여신", "수신", "외환", "자금", "카드", "고객", "기타"]
MAX_CATEGORY_INPUT_CHARS = 3000
CLASSIFY_MAX_WORKERS = 5


def build_subs_section(subs_by_cat: dict[str, list[str]], categories: list[str] | None = None) -> str:
    """DB에서 조회한 소분류 목록을 프롬프트용 텍스트로 변환한다."""
    cat_order = categories if categories else _DEFAULT_CATEGORIES
    filled = {cat: subs for cat, subs in subs_by_cat.items() if subs}
    if not filled:
        return "[소분류 목록]\n정의된 소분류가 없습니다. sub_category는 null로 반환하세요."
    lines = [
        "[소분류 목록]",
        "첫 번째 대분류(categories[0])에 따라 아래 소분류 중 가장 적합한 하나를 선택해. 맞는 소분류가 없으면 null.",
    ]
    for cat in cat_order:
        subs = subs_by_cat.get(cat, [])
        if subs:
            lines.append(f"- {cat}: {', '.join(subs)}")
    return "\n".join(lines)


class SectionCategory(BaseModel):
    reasoning: str = Field(description="이 섹션을 해당 분류로 고른 핵심 근거를 1문장으로")
    categories: list[str] = Field(
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


def _run_section_classifier(model, title: str, content: str, subs_section: str) -> SectionCategory:
    prompt = SECTION_CATEGORY_PROMPT.format(
        subs_section=subs_section,
        section_title=title or "(제목 없음)",
        section_content=content,
    )
    return call_llm(model, prompt, label="classify_section")


def _classify_section(title: str, content: str, subs_section: str) -> tuple[list[str], str | None, bool]:
    """저비용 모델 + 잘린 내용으로 1차 분류만 수행한다. confidence가 낮으면 needs_review=True로 표시하고,
    실제 재분류(강한 모델 + 전체 내용)는 검토 모달에서 사용자가 명시적으로 요청할 때 reclassify_section_strong()으로 수행한다."""
    try:
        result = _run_section_classifier(section_category_llm, title, content[:MAX_CATEGORY_INPUT_CHARS], subs_section)
        return result.categories, result.sub_category, result.confidence != "high"
    except Exception:
        return ["기타"], None, True


def reclassify_section_strong(title: str, content: str, subs_section: str = "") -> tuple[list[str], str | None, bool]:
    """검토 모달의 '정밀 재분류 요청' 버튼용: 강한 모델 + 전체 내용으로 다시 분류한다."""
    try:
        result = _run_section_classifier(section_category_llm_strong, title, content, subs_section)
        return result.categories, result.sub_category, result.confidence != "high"
    except Exception:
        return ["기타"], None, True


def classify_sections(sections: list[dict], subs_by_cat: dict[str, list[str]] | None = None, categories: list[str] | None = None) -> list[dict]:
    """split_into_major_sections() 결과에 categories, sub_category, needs_review를 부여한다.
    섹션마다 LLM 호출이 필요해서, 병렬로 분류한다."""
    subs_section = build_subs_section(subs_by_cat or {}, categories=categories)
    with ThreadPoolExecutor(max_workers=CLASSIFY_MAX_WORKERS) as executor:
        results = list(executor.map(
            lambda section: _classify_section(section["title"], section["content"], subs_section),
            sections,
        ))
    return [
        {**section, "categories": categories, "sub_category": sub_category, "needs_review": needs_review}
        for section, (categories, sub_category, needs_review) in zip(sections, results)
    ]
