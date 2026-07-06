from sqlalchemy import text as sql_text

from db import engine


def create_job(manual_id: int, version_id: int) -> int:
    with engine.begin() as conn:
        return conn.execute(
            sql_text("""
                INSERT INTO manual_upload_jobs_khs (manual_id, version_id)
                VALUES (:manual_id, :version_id)
                RETURNING id
            """),
            {"manual_id": manual_id, "version_id": version_id}
        ).scalar_one()


def update_job_step(job_id: int, step: str):
    with engine.begin() as conn:
        conn.execute(
            sql_text("""
                UPDATE manual_upload_jobs_khs
                SET step = :step, updated_at = now()
                WHERE id = :job_id
            """),
            {"job_id": job_id, "step": step}
        )


def mark_job_failed(job_id: int, error_message: str):
    """step은 실패가 발생한 단계 그대로 남겨두고 error_message만 채운다."""
    with engine.begin() as conn:
        conn.execute(
            sql_text("""
                UPDATE manual_upload_jobs_khs
                SET error_message = :error_message, updated_at = now()
                WHERE id = :job_id
            """),
            {"job_id": job_id, "error_message": error_message}
        )


def get_job(job_id: int):
    with engine.connect() as conn:
        return conn.execute(
            sql_text("SELECT step, error_message FROM manual_upload_jobs_khs WHERE id = :id"),
            {"id": job_id}
        ).mappings().first()
