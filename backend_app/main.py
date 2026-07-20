from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy.exc import ProgrammingError
from backend_app.routers import auth_router, chat_router, faq_router, manuals_router


# =========================
# FastAPI 앱 생성
# =========================

app = FastAPI()


@app.exception_handler(ProgrammingError)
async def handle_database_programming_error(_request, exc: ProgrammingError):
    """DB 스키마 불일치를 일반 텍스트 500 대신 확인 가능한 JSON으로 반환한다."""
    original_message = str(exc.orig)
    if "faq_type" in original_message or "approved_at" in original_message or "sources" in original_message:
        detail = (
            "FAQ 기능에 필요한 _kyj DB 마이그레이션이 적용되지 않았습니다. "
            "backend_app/sql/faq_review_and_search_kyj.sql을 DBeaver에서 실행해 주세요."
        )
        return JSONResponse(status_code=503, content={"detail": detail, "code": "FAQ_SCHEMA_MIGRATION_REQUIRED"})
    return JSONResponse(
        status_code=500,
        content={"detail": "DB 요청 처리 중 스키마 오류가 발생했습니다.", "code": "DATABASE_SCHEMA_ERROR"},
    )


# 기존 라우터 유지
app.include_router(auth_router.router)
app.include_router(manuals_router.router)
app.include_router(chat_router.router)
app.include_router(faq_router.router)
