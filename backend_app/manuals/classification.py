from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from pydantic import BaseModel, Field

from llm_clients import llm, strong_llm
from manuals.prompts import SECTION_CATEGORY_PROMPT

SECTION_CATEGORIES = ["여신", "수신", "외환", "자금", "카드", "고객", "기타"]
MAX_CATEGORY_INPUT_CHARS = 3000
CLASSIFY_MAX_WORKERS = 5


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


def _run_section_classifier(model, title: str, content: str) -> SectionCategory:
    prompt = SECTION_CATEGORY_PROMPT.format(
        section_title=title or "(제목 없음)",
        section_content=content,
    )
    return model.invoke(prompt)


def _classify_section(title: str, content: str) -> tuple[list[str], str | None, bool]:
    """저비용 모델 + 잘린 내용으로 1차 분류만 수행한다. confidence가 낮으면 needs_review=True로 표시하고,
    실제 재분류(강한 모델 + 전체 내용)는 검토 모달에서 사용자가 명시적으로 요청할 때 reclassify_section_strong()으로 수행한다."""
    try:
        result = _run_section_classifier(section_category_llm, title, content[:MAX_CATEGORY_INPUT_CHARS])
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


def classify_sections(sections: list[dict]) -> list[dict]:
    """split_into_major_sections() 결과에 categories, sub_category, needs_review를 부여한다.
    섹션마다 LLM 호출이 필요해서, 병렬로 분류한다."""
    with ThreadPoolExecutor(max_workers=CLASSIFY_MAX_WORKERS) as executor:
        results = list(executor.map(
            lambda section: _classify_section(section["title"], section["content"]),
            sections,
        ))
    return [
        {**section, "categories": categories, "sub_category": sub_category, "needs_review": needs_review}
        for section, (categories, sub_category, needs_review) in zip(sections, results)
    ]
