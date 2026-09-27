"""마이페이지(내 정보 조회/수정) 로직.

ID(username)와 permission_code(role)는 여기서 변경하지 않는다 — 그 두 값을
바꾸는 API는 의도적으로 만들지 않았다.
"""
import bcrypt
from sqlalchemy import text

from db import engine

from db_tables import USERS


def employee_email_taken_by_other(employee_id: str, email: str) -> bool:
    with engine.connect() as conn:
        return conn.execute(
            text(f"SELECT 1 FROM {USERS} WHERE email = :email AND username <> :id"),
            {"email": email, "id": employee_id},
        ).first() is not None


def update_employee_profile(
    employee_id: str,
    *,
    password: str | None,
    email: str,
    team_code: str,
    position_code: str,
    lang_code: str,
    countries: list[str],
) -> None:
    params = {
        "id": employee_id,
        "email": email,
        "team_code": team_code,
        "position_code": position_code,
        "lang_c": lang_code,
        "countries": countries,
    }
    set_clauses = [
        "email = :email",
        "team_code = :team_code",
        "position_code = :position_code",
        "lang_c = :lang_c",
        "countries = :countries",
    ]
    if password:
        params["password_hash"] = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        set_clauses.append("password_hash = :password_hash")

    with engine.begin() as conn:
        conn.execute(
            text(f"UPDATE {USERS} SET {', '.join(set_clauses)} WHERE username = :id"),
            params,
        )
