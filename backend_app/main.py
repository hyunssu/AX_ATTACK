from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy.exc import ProgrammingError

from auth.router import router as auth_router
from chat.router import router as chat_router
from manuals.drafts_router import router as drafts_router
from manuals.router import router as manuals_router
from faq.router import router as faq_router

app = FastAPI()


@app.exception_handler(ProgrammingError)
async def handle_database_programming_error(_request, exc: ProgrammingError):
    original_message = str(exc.orig)
    faq_schema_markers = (
        "faq_requests_kyj",
        "faq_request_messages_kyj",
        "display_name",
        "expertise_keywords",
    )
    if any(marker in original_message for marker in faq_schema_markers):
        detail = (
            "미해결 FAQ 요청 기능에 필요한 _kyj DB 마이그레이션이 적용되지 않았습니다. "
            "backend_app/sql/faq_registry_merge_into_requests_kyj.sql을 검토한 뒤 "
            "DBeaver에서 직접 실행해 주세요."
        )
        return JSONResponse(status_code=503, content={"detail": detail, "code": "FAQ_SCHEMA_MIGRATION_REQUIRED"})
    return JSONResponse(
        status_code=500,
        content={"detail": "DB 요청 처리 중 스키마 오류가 발생했습니다.", "code": "DATABASE_SCHEMA_ERROR"},
    )


app.include_router(auth_router)
app.include_router(manuals_router)
app.include_router(drafts_router)
app.include_router(chat_router)
app.include_router(faq_router)
