from typing import Optional, List, Dict, Any
from sqlalchemy import text as sql_text

from db import engine

def create_term(term_name: str, definition: str, keyword: str = None, category: Optional[str] = None) -> int:
    """새로운 용어를 등록하고 생성된 term_id를 반환한다."""
    with engine.begin() as conn:
        result = conn.execute(
            sql_text(f"""
                INSERT INTO TERMS (term_name, keyword, definition, category, created_at, updated_at)
                VALUES (:term_name, :keyword, :definition, :category, now(), now())
                RETURNING term_id
            """),
            {
                "term_name": term_name,
                "keyword": keyword,
                "definition": definition,
                "category": category
            }
        )
        # 생성된 term_id 반환
        row = result.fetchone()
        return row[0] if row else None


def get_term_by_id(term_id: int) -> Optional[Dict[str, Any]]:
    """term_id로 특정 용어 정보를 조회한다."""
    with engine.connect() as conn:
        row = conn.execute(
            sql_text(f"""
                SELECT term_id, term_name, keyword, definition, category, created_at, updated_at
                FROM TERMS
                WHERE term_id = :term_id
            """),
            {"term_id": term_id}
        ).mappings().first()
        
        return dict(row) if row else None


def search_terms(inputword: str) -> List[Dict[str, Any]]:
    """용어 명칭이나 동의어에 키워드가 포함된 목록을 조회한다."""
    with engine.connect() as conn:
        rows = conn.execute(
            sql_text(f"""
                SELECT term_id, term_name, keyword, definition, category, created_at, updated_at
                FROM TERMS
                WHERE term_name LIKE :inputword OR keyword LIKE :inputword
                ORDER BY term_id DESC
            """),
            {"inputword": f"%{inputword}%"}
        ).mappings().all()
        
        return [dict(row) for row in rows]


def find_term(inputword: str) -> Optional[Dict[str, Any]]:
    """용어명 또는 쉼표로 구분된 동의어와 정확히 일치하는 최신 용어를 찾는다."""
    normalized = inputword.strip()
    if not normalized:
        return None

    with engine.connect() as conn:
        row = conn.execute(
            sql_text("""
                SELECT term_id, term_name, keyword, definition, category, created_at, updated_at
                FROM terms
                WHERE lower(trim(term_name)) = lower(:inputword)
                   OR EXISTS (
                       SELECT 1
                       FROM unnest(string_to_array(COALESCE(keyword, ''), ',')) AS alias(value)
                       WHERE lower(trim(alias.value)) = lower(:inputword)
                   )
                ORDER BY term_id DESC
                LIMIT 1
            """),
            {"inputword": normalized},
        ).mappings().first()

    return dict(row) if row else None
