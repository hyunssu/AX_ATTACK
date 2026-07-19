from fastapi import FastAPI
from backend_app.routers import auth_router, chat_router, manuals_router


# =========================
# FastAPI 앱 생성
# =========================

app = FastAPI()


# 기존 라우터 유지
app.include_router(auth_router.router)
app.include_router(manuals_router.router)
app.include_router(chat_router.router)
