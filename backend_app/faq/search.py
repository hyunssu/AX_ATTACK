"""승인된 FAQ만 검색해 확정 답변으로 반환한다."""

from datetime import datetime
from zoneinfo import ZoneInfo

from langchain_openai import OpenAIEmbeddings
from sqlalchemy import text

from config import (
    FAQ_MATCH_THRESHOLD,
    KNOWLEDGE_DATE_TIMEZONE,
    OPENAI_EMBEDDING_DIMENSIONS,
    OPENAI_EMBEDDING_MODEL,
)
from db import engine
from db_tables import FAQ_REQUESTS


embeddings = OpenAIEmbeddings(
    model=OPENAI_EMBEDDING_MODEL,
    dimensions=OPENAI_EMBEDDING_DIMENSIONS,
)


def _embedding_to_sql(vector: list[float]) -> str:
    return "[" + ",".join(str(value) for value in vector) + "]"


def _compact_datetime_iso(date_value: str, time_value: str) -> str:
    compact = f"{str(date_value).strip()}{str(time_value).strip()}"
    parsed = datetime.strptime(compact, "%Y%m%d%H%M%S")
    return parsed.replace(tzinfo=ZoneInfo(KNOWLEDGE_DATE_TIMEZONE)).isoformat()


def search_approved_faq(question: str) -> dict:
    """approved FAQ의 최고 후보와 점수·기준일을 반환한다."""
    with engine.connect() as conn:
        has_candidates = conn.execute(
            text(f"""
                SELECT EXISTS (
                    SELECT 1
                    FROM {FAQ_REQUESTS}
                    WHERE status = 'approved'
                      AND knowledge_search_allowed = 'Y'
                      AND embedding_model = :embedding_model
                      AND (summarized_question_embedding IS NOT NULL
                           OR summarized_answer_embedding IS NOT NULL)
                )
            """),
            {"embedding_model": OPENAI_EMBEDDING_MODEL},
        ).scalar_one()

    if not has_candidates:
        return {
            "matched": False,
            "reason": "no_approved_faq_for_embedding_model",
            "embedding_model": OPENAI_EMBEDDING_MODEL,
            "result": None,
        }

    query_vector = _embedding_to_sql(embeddings.embed_query(question))
    with engine.connect() as conn:
        row = conn.execute(
            text(f"""
                WITH question_candidate AS (
                    SELECT faq_id, summarized_question, summarized_answer, final_keywords, embedding_model,
                           regis_date, regis_time, last_change_date, last_change_time,
                           1 - (summarized_question_embedding <=> CAST(:query_vector AS vector)) AS similarity,
                           'summarized_question' AS matched_field
                    FROM {FAQ_REQUESTS}
                    WHERE status = 'approved'
                      AND knowledge_search_allowed = 'Y'
                      AND embedding_model = :embedding_model
                      AND summarized_question_embedding IS NOT NULL
                    ORDER BY summarized_question_embedding <=> CAST(:query_vector AS vector)
                    LIMIT 1
                ),
                answer_candidate AS (
                    SELECT faq_id, summarized_question, summarized_answer, final_keywords, embedding_model,
                           regis_date, regis_time, last_change_date, last_change_time,
                           1 - (summarized_answer_embedding <=> CAST(:query_vector AS vector)) AS similarity,
                           'summarized_answer' AS matched_field
                    FROM {FAQ_REQUESTS}
                    WHERE status = 'approved'
                      AND knowledge_search_allowed = 'Y'
                      AND embedding_model = :embedding_model
                      AND summarized_answer_embedding IS NOT NULL
                    ORDER BY summarized_answer_embedding <=> CAST(:query_vector AS vector)
                    LIMIT 1
                )
                SELECT *
                FROM (
                    SELECT * FROM question_candidate
                    UNION ALL
                    SELECT * FROM answer_candidate
                ) candidates
                ORDER BY similarity DESC
                LIMIT 1
            """),
            {
                "query_vector": query_vector,
                "embedding_model": OPENAI_EMBEDDING_MODEL,
            },
        ).mappings().first()

    if not row:
        return {"matched": False, "reason": "no_candidate", "result": None}

    similarity = round(float(row["similarity"]), 4)
    matched = similarity >= FAQ_MATCH_THRESHOLD
    registered_at = _compact_datetime_iso(row["regis_date"], row["regis_time"])
    basis_date = _compact_datetime_iso(row["last_change_date"], row["last_change_time"])
    candidate = {
        "type": "answer",
        "text": row["summarized_answer"],
        "options": [],
        "sources": [
            {
                "type": "faq",
                "id": row["faq_id"],
                "title": f"승인 FAQ 요청 #{row['faq_id']}",
                "detail": row["summarized_question"],
                "created_at": registered_at,
                "date_label": "FAQ 요청 등록일",
                "basis_date": basis_date,
                "basis_date_label": "FAQ 기준 갱신일",
                "approved_at": basis_date,
                "embedding_model": row["embedding_model"],
            }
        ],
        "trace": {
            "engine": "faq",
            "steps": [
                {
                    "node": "search_approved_faq",
                    "label": "승인 FAQ 검색",
                    "input": {
                        "question": question,
                        "threshold": FAQ_MATCH_THRESHOLD,
                        "embedding_model": OPENAI_EMBEDDING_MODEL,
                    },
                    "output": {
                        "faq_id": row["faq_id"],
                        "similarity": similarity,
                        "matched": matched,
                        "matched_field": row["matched_field"],
                        "embedding_model": row["embedding_model"],
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
        "basis_date": basis_date,
        "result": candidate if matched else None,
        "candidate": {
            "faq_id": row["faq_id"],
            "question": row["summarized_question"],
            "score": similarity,
            "basis_date": basis_date,
            "matched_field": row["matched_field"],
            "embedding_model": row["embedding_model"],
        },
    }


def answer_from_approved_faq(question: str) -> dict | None:
    """기존 호출부 호환용: 임계값을 넘은 FAQ 답변만 반환한다."""
    return search_approved_faq(question)["result"]
