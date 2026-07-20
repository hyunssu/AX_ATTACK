from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import create_access_token, get_current_user, get_user_role, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(req: LoginRequest):
    if not verify_password(req.username, req.password):
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")

    token = create_access_token(req.username)
    return {"access_token": token, "username": req.username, "role": get_user_role(req.username)}


@router.get("/me")
def get_me(username: str = Depends(get_current_user)):
    return {"username": username, "role": get_user_role(username)}
