from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from backend_app.config import JWT_ALGORITHM, JWT_EXPIRE_HOURS, JWT_SECRET
from backend_app.db import engine
from backend_app.db_tables import USERS

bearer_scheme = HTTPBearer()


def verify_password(username: str, password: str) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            text(f"SELECT password_hash FROM {USERS} WHERE username = :username"),
            {"username": username}
        ).mappings().first()

    if not row:
        return False
    return bcrypt.checkpw(password.encode(), row["password_hash"].encode())


def get_user_role(username: str) -> str | None:
    try:
        with engine.connect() as conn:
            return conn.execute(
                text(f"SELECT role FROM {USERS} WHERE username = :username"),
                {"username": username},
            ).scalar_one_or_none()
    except ProgrammingError as exc:
        # 역할 마이그레이션 전에도 기존 사용자의 로그인 자체는 유지한다.
        if "role" in str(exc.orig) and "does not exist" in str(exc.orig):
            return "LocalUser"
        raise


def create_access_token(username: str) -> str:
    payload = {
        "sub": username,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> str:
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload["sub"]
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="유효하지 않은 인증 정보입니다.")
