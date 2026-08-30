from typing import Optional, List, Dict, Any
from sqlalchemy import text as sql_text

from db import engine

def create_term(term_name: str, definition: str, synonyms: Optional[str] = None, category: Optional[str] = None) -> int:
    """새로운 용어를 등록하고 생성된 term_id를 반환한다."""
    with engine.begin() as conn:
        result = conn.execute(
            sql_text(f"""
                INSERT INTO TERMS (term_name, synonyms, definition, category, created_at, updated_at)
                VALUES (:term_name, :synonyms, :definition, :category, now(), now())
                RETURNING term_id
            """),
            {
                "term_name": term_name,
                "synonyms": synonyms,
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
                SELECT term_id, term_name, synonyms, definition, category, created_at, updated_at
                FROM TERMS
                WHERE term_id = :term_id
            """),
            {"term_id": term_id}
        ).mappings().first()
        
        return dict(row) if row else None


def search_terms(keyword: str) -> List[Dict[str, Any]]:
    """용어 명칭이나 동의어에 키워드가 포함된 목록을 조회한다."""
    with engine.connect() as conn:
        rows = conn.execute(
            sql_text(f"""
                SELECT term_id, term_name, synonyms, definition, category, created_at, updated_at
                FROM TERMS
                WHERE term_name LIKE :keyword OR synonyms LIKE :keyword
                ORDER BY term_id DESC
            """),
            {"keyword": f"%{keyword}%"}
        ).mappings().all()
        
        return [dict(row) for row in rows]