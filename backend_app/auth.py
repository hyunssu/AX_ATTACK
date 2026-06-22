from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text

from config import DEFAULT_ADMIN_PASSWORD, DEFAULT_ADMIN_USER, JWT_ALGORITHM, JWT_EXPIRE_HOURS, JWT_SECRET
from db import engine

bearer_scheme = HTTPBearer()


def ensure_default_user():
    with engine.begin() as conn:
        exists = conn.execute(
            text("SELECT id FROM users WHERE username = :username"),
            {"username": DEFAULT_ADMIN_USER}
        ).first()
        if not exists:
            password_hash = bcrypt.hashpw(DEFAULT_ADMIN_PASSWORD.encode(), bcrypt.gensalt()).decode()
            conn.execute(
                text("INSERT INTO users (username, password_hash) VALUES (:username, :password_hash)"),
                {"username": DEFAULT_ADMIN_USER, "password_hash": password_hash}
            )


def verify_password(username: str, password: str) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT password_hash FROM users WHERE username = :username"),
            {"username": username}
        ).mappings().first()

    if not row:
        return False
    return bcrypt.checkpw(password.encode(), row["password_hash"].encode())


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
