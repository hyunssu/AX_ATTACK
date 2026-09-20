"""회원가입(users_kyj INSERT) 로직."""
import bcrypt
from sqlalchemy import text

from db import engine

from db_tables import USERS


def employee_id_exists(employee_id: str) -> bool:
    with engine.connect() as conn:
        return conn.execute(
            text(f"SELECT 1 FROM {USERS} WHERE username = :id"),
            {"id": employee_id},
        ).first() is not None


def employee_email_exists(email: str) -> bool:
    with engine.connect() as conn:
        return conn.execute(
            text(f"SELECT 1 FROM {USERS} WHERE email = :email"),
            {"email": email},
        ).first() is not None


def employee_no_exists(emp_no: int) -> bool:
    with engine.connect() as conn:
        return conn.execute(
            text(f"SELECT 1 FROM {USERS} WHERE id = :emp_no"),
            {"emp_no": emp_no},
        ).first() is not None


def create_employee(
    *,
    emp_no: int,
    employee_id: str,
    password: str,
    email: str,
    team_code: str,
    position_code: str,
    permission_code: str,
    lang_code: str,
    countries: list[str],
) -> None:
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    with engine.begin() as conn:
        conn.execute(
            text(
                f"INSERT INTO {USERS} "
                "(id, username, password_hash, email, team_code, position_code, role, lang_c, countries) "
                "VALUES (:emp_no, :id, :password_hash, :email, :team_code, :position_code, :role, :lang_c, :countries)"
            ),
            {
                "emp_no": emp_no,
                "id": employee_id,
                "password_hash": password_hash,
                "email": email,
                "team_code": team_code,
                "position_code": position_code,
                "role": permission_code,
                "lang_c": lang_code,
                "countries": countries,
            },
        )
