"""회원가입 이메일 본인인증(2-2) 로직.

email_verifications 테이블에 이메일당 최신 인증번호 1건을 저장해두고,
확인 요청이 오면 코드/만료시각을 검사해 verified 플래그를 올린다.
"""
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from db import engine

from auth.emp_config import EMP_EMAIL_VERIFICATION_TTL_MINUTES
from auth.emp_mailer import send_verification_email
from auth.emp_tables import EMAIL_VERIFICATIONS


def _generate_code() -> str:
    return f"{random.randint(0, 999999):06d}"


def request_verification_code(email: str) -> str:
    code = _generate_code()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=EMP_EMAIL_VERIFICATION_TTL_MINUTES)

    with engine.begin() as conn:
        conn.execute(
            text(
                f"INSERT INTO {EMAIL_VERIFICATIONS} (email, code, expires_at, verified) "
                "VALUES (:email, :code, :expires_at, FALSE) "
                "ON CONFLICT (email) DO UPDATE SET "
                "code = EXCLUDED.code, expires_at = EXCLUDED.expires_at, "
                "verified = FALSE, created_at = now()"
            ),
            {"email": email, "code": code, "expires_at": expires_at},
        )

    send_verification_email(email, code)
    return code


def confirm_verification_code(email: str, code: str) -> bool:
    with engine.begin() as conn:
        row = conn.execute(
            text(f"SELECT code, expires_at FROM {EMAIL_VERIFICATIONS} WHERE email = :email"),
            {"email": email},
        ).mappings().first()

        if not row or row["code"] != code:
            return False
        if row["expires_at"] < datetime.now(timezone.utc):
            return False

        conn.execute(
            text(f"UPDATE {EMAIL_VERIFICATIONS} SET verified = TRUE WHERE email = :email"),
            {"email": email},
        )

    return True


def is_email_verified(email: str) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            text(f"SELECT verified FROM {EMAIL_VERIFICATIONS} WHERE email = :email"),
            {"email": email},
        ).mappings().first()
    return bool(row and row["verified"])
