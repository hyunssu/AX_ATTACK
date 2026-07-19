from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text

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
