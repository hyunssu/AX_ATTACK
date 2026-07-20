"""승인된 FAQ만 검색해 확정 답변으로 반환한다."""

from langchain_openai import OpenAIEmbeddings
from sqlalchemy import text

from config import FAQ_MATCH_THRESHOLD, OPENAI_EMBEDDING_MODEL
from db import engine
from db_tables import FAQ_HISTORY


embeddings = OpenAIEmbeddings(model=OPENAI_EMBEDDING_MODEL)


def _embedding_to_sql(vector: list[float]) -> str:
    return "[" + ",".join(str(value) for value in vector) + "]"


def search_approved_faq(question: str) -> dict:
    """approved FAQ의 최고 후보와 점수·기준일을 반환한다."""
    with engine.connect() as conn:
        has_candidates = conn.execute(
            text(f"""
                SELECT EXISTS (
                    SELECT 1
                    FROM {FAQ_HISTORY}
                    WHERE status = 'approved'
                      AND embedding IS NOT NULL
                      AND faq_type <> 'screen_owner_change'
                )
            """)
        ).scalar_one()

    if not has_candidates:
        return {"matched": False, "reason": "no_approved_faq", "result": None}

    query_vector = _embedding_to_sql(embeddings.embed_query(question))
    with engine.connect() as conn:
        row = conn.execute(
            text(f"""
                SELECT id, question, answer, keywords, faq_type, created_at, updated_at, approved_at,
                       1 - (embedding <=> CAST(:query_vector AS vector)) AS similarity
                FROM {FAQ_HISTORY}
                WHERE status = 'approved'
                  AND embedding IS NOT NULL
                  AND faq_type <> 'screen_owner_change'
                ORDER BY embedding <=> CAST(:query_vector AS vector)
                LIMIT 1
            """),
            {"query_vector": query_vector},
        ).mappings().first()

    if not row:
        return {"matched": False, "reason": "no_candidate", "result": None}

    similarity = round(float(row["similarity"]), 4)
    matched = similarity >= FAQ_MATCH_THRESHOLD
    candidate = {
        "type": "answer",
        "text": row["answer"],
        "options": [],
        "sources": [
            {
                "type": "faq",
                "id": row["id"],
                "title": f"승인 FAQ #{row['id']}",
                "detail": row["question"],
                "created_at": row["created_at"].isoformat(),
                "date_label": "FAQ 생성일",
                "basis_date": row["updated_at"].isoformat(),
                "basis_date_label": "FAQ 기준 갱신일",
                "approved_at": row["approved_at"].isoformat() if row["approved_at"] else None,
            }
        ],
        "trace": {
            "engine": "faq",
            "steps": [
                {
                    "node": "search_approved_faq",
                    "label": "승인 FAQ 검색",
                    "input": {"question": question, "threshold": FAQ_MATCH_THRESHOLD},
                    "output": {
                        "faq_id": row["id"],
                        "similarity": similarity,
                        "matched": matched,
                    },
                }
            ],
        },
    }
    return {
        "matched": matched,
        "reason": "matched" if matched else "below_threshold",
        "score": similarity,
        "threshold": FAQ_MATCH_THRESHOLD,
        "basis_date": row["updated_at"].isoformat(),
        "result": candidate if matched else None,
        "candidate": {
            "faq_id": row["id"],
            "question": row["question"],
            "score": similarity,
            "basis_date": row["updated_at"].isoformat(),
        },
    }


def answer_from_approved_faq(question: str) -> dict | None:
    """기존 호출부 호환용: 임계값을 넘은 FAQ 답변만 반환한다."""
    return search_approved_faq(question)["result"]
