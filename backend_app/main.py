import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy.exc import ProgrammingError

from auth.router import router as auth_router
from chat.router import router as chat_router
from manuals.drafts_router import router as drafts_router
from manuals.router import router as manuals_router
from faq.router import router as faq_router
from etc.router import router as terms_router # 신규용어 router

app = FastAPI()
logger = logging.getLogger(__name__)


@app.exception_handler(ProgrammingError)
async def handle_database_programming_error(_request, exc: ProgrammingError):
    logger.error(
        "Database programming error",
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "DB 요청 처리 중 스키마 오류가 발생했습니다.", "code": "DATABASE_SCHEMA_ERROR"},
    )


app.include_router(auth_router)
app.include_router(manuals_router)
app.include_router(drafts_router)
app.include_router(chat_router)
app.include_router(faq_router)
app.include_router(terms_router) # 신규용어 router
