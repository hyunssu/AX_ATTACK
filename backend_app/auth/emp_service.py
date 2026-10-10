"""users 기반 인증과 사용자 프로필 조회. JWT는 auth/service.py를 재사용한다."""
import bcrypt
from sqlalchemy import text

from db import engine

from db_tables import USERS
from auth.profiles import read_profiles


def verify_employee_password(employee_id: str, password: str) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            text(f"SELECT password_hash FROM {USERS} WHERE username = :id"),
            {"id": employee_id},
        ).mappings().first()

    if not row:
        return False
    return bcrypt.checkpw(password.encode(), row["password_hash"].encode())


def get_employee(username: str):
    """username(로그인 ID)으로 조회한다. 반환되는 id는 users.id(8자리 사번,
    헤더 표시용)이지 로그인 ID가 아니다 — 둘은 별개 컬럼이다."""
    profiles = read_profiles(username)
    if not profiles:
        return None
    profile = profiles[0]
    profile['permission_code'] = profile.get('role')
    profile['lang_code'] = profile.get('lang_c')
    return profile
