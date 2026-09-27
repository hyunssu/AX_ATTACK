"""users_kyj 기반 인증 로직.

users_kyj로 통합되기 전에는 employee_info 전용이었고 자체 JWT 함수
(create_employee_access_token/get_current_employee_id)를 따로 뒀지만,
이제 로그인 주체가 진짜 users_kyj.username이므로 auth/service.py의
create_access_token()/get_current_user()를 그대로 재사용한다
(emp_router.py에서 import). 여기 남은 건 users_kyj 조회 전용 함수뿐이다.
"""
import bcrypt
from sqlalchemy import text

from db import engine

from db_tables import USERS


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
    """username(로그인 ID)으로 조회한다. 반환되는 id는 users_kyj.id(8자리 사번,
    헤더 표시용)이지 로그인 ID가 아니다 — 둘은 별개 컬럼이다."""
    with engine.connect() as conn:
        return conn.execute(
            text(
                f"SELECT id, username, email, team_code, position_code, "
                f"role AS permission_code, lang_c AS lang_code, countries "
                f"FROM {USERS} WHERE username = :username"
            ),
            {"username": username},
        ).mappings().first()
