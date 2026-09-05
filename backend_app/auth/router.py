from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth.service import (
    create_access_token, create_user, get_current_user,
    get_user_language, get_user_role, user_exists, verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(req: LoginRequest):
    if not verify_password(req.username, req.password):
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")

    token = create_access_token(req.username)
    return {
        "access_token": token,
        "username": req.username,
        "role": get_user_role(req.username),
        "lang_c": get_user_language(req.username),
    }


class RegisterRequest(BaseModel):
    username: str
    password: str
    email: str


@router.post("/register", status_code=201)
def register(req: RegisterRequest):
    if not req.username or not req.password or not req.email:
        raise HTTPException(status_code=422, detail="모든 항목을 입력해 주세요.")
    if user_exists(req.username):
        raise HTTPException(status_code=409, detail="이미 사용 중인 아이디입니다.")
    try:
        create_user(req.username, req.password, req.email)
    except Exception:
        raise HTTPException(status_code=500, detail="회원가입에 실패했습니다.")

    token = create_access_token(req.username)
    return {
        "access_token": token,
        "username": req.username,
        "role": "User",
        "lang_c": "ko",
    }


@router.get("/me")
def get_me(username: str = Depends(get_current_user)):
    return {"username": username, "role": get_user_role(username), "lang_c": get_user_language(username)}
