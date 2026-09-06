from pydantic import BaseModel
from typing import Optional

class TermCreateRequest(BaseModel):
    term_name: str
    keyword: str = None  # 동의어 및 약어 (keyword 필드 대응)
    definition: str
    category: Optional[str] = None  # 카테고리가 있다면 선택 입력