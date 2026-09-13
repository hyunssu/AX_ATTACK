from sqlalchemy import text as sql_text

from db import engine
from db_tables import MANUAL_VERSIONS


def create_job(manual_id: int, version_id: int) -> int:
    """별도 작업 테이블 없이 버전 ID를 작업 ID로 사용한다."""
    return version_id


def update_job_step(job_id: int, step: str):
    with engine.begin() as conn:
        conn.execute(
            sql_text(f"""
                UPDATE {MANUAL_VERSIONS}
                SET index_step = :step, error_message = NULL, updated_at = now()
                WHERE id = :job_id
            """),
            {"job_id": job_id, "step": step}
        )


def mark_job_failed(job_id: int, error_message: str):
    with engine.begin() as conn:
        conn.execute(
            sql_text(f"""
                UPDATE {MANUAL_VERSIONS}
                SET error_message = :error_message, updated_at = now()
                WHERE id = :job_id
            """),
            {"job_id": job_id, "error_message": error_message}
        )


def get_job(job_id: int):
    with engine.connect() as conn:
        return conn.execute(
            sql_text(f"""
                SELECT index_step AS step, error_message
                FROM {MANUAL_VERSIONS}
                WHERE id = :id
            """),
            {"id": job_id}
        ).mappings().first()
