import re

from langchain_community.document_loaders import PyPDFLoader, TextLoader


def convert_document(file_path: str):
    """1단계(파일 변환): PDF/Markdown 원본을 저장하기 좋은 순수 텍스트 문서로 변환한다."""
    if file_path.lower().endswith(".md"):
        return TextLoader(file_path, encoding="utf-8").load()
    return PyPDFLoader(file_path).load()


MD_HEADING_RE = re.compile(r'^(#{1,6})\s+(.*)$')
MD_MAJOR_HEADING_MAX_LEVEL = 2  # #, ## 까지만 "대 단위" 경계로 취급

HEADING_PATTERNS = [
    re.compile(r'^\s*제\s*\d+\s*장'),                  # 제1장
    re.compile(r'^\s*\d+\s*장\b'),                      # 1장
    re.compile(r'^\s*Chapter\s+\d+', re.IGNORECASE),   # Chapter 1
    re.compile(r'^\s*\d+\.\d+\s+.{2,}$'),               # 1.2 Title (소절 번호, 일반 번호 목록과 구분하기 위해 소수점 필수)
]
MAX_PDF_LINE_LEN_FOR_HEADING = 80
MIN_SECTION_LEN = 30


def _merge_tiny_sections(sections: list[dict]) -> list[dict]:
    """짧은 섹션(오탐 가능성 높음)은 이전 섹션에 합친다."""
    merged: list[dict] = []
    for section in sections:
        if merged and section["char_count"] < MIN_SECTION_LEN:
            prev = merged[-1]
            prev["content"] = (prev["content"] + "\n" + section["content"]).strip()
            prev["char_count"] = len(prev["content"])
        else:
            merged.append(section)
    return merged


def _split_markdown_sections(text: str) -> list[dict]:
    sections: list[dict] = []
    current_title = ""
    current_lines: list[str] = []

    def _flush():
        content = "\n".join(current_lines).strip()
        if content:
            sections.append({"title": current_title, "content": content, "char_count": len(content)})

    for line in text.splitlines():
        match = MD_HEADING_RE.match(line)
        if match and len(match.group(1)) <= MD_MAJOR_HEADING_MAX_LEVEL:
            _flush()
            current_title = match.group(2).strip()
            current_lines = []
        else:
            current_lines.append(line)
    _flush()

    return _merge_tiny_sections(sections)


def _split_pdf_sections(file_path: str) -> list[dict]:
    docs = convert_document(file_path)
    full_text = "\n".join(doc.page_content for doc in docs)

    sections: list[dict] = []
    current_title = ""
    current_lines: list[str] = []

    def _flush():
        content = "\n".join(current_lines).strip()
        if content:
            sections.append({"title": current_title, "content": content, "char_count": len(content)})

    for line in full_text.splitlines():
        stripped = line.strip()
        is_heading = (
            len(stripped) <= MAX_PDF_LINE_LEN_FOR_HEADING
            and stripped
            and any(pattern.match(stripped) for pattern in HEADING_PATTERNS)
        )
        if is_heading:
            _flush()
            current_title = stripped
            current_lines = []
        else:
            current_lines.append(line)
    _flush()

    if not sections:
        if full_text.strip():
            return [{"title": "전체 문서", "content": full_text.strip(), "char_count": len(full_text.strip())}]
        return []

    return _merge_tiny_sections(sections)


def split_into_major_sections(file_path: str) -> list[dict]:
    """대 단위(장/챕터 수준) 분할 미리보기. 임베딩용 chunk_document와는 별개의 순수 파싱 로직."""
    if file_path.lower().endswith(".md"):
        text = TextLoader(file_path, encoding="utf-8").load()[0].page_content
        return _split_markdown_sections(text)
    return _split_pdf_sections(file_path)
