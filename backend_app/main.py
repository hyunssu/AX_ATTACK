from fastapi import FastAPI

from auth.router import router as auth_router
from auth.service import ensure_default_user
from chat.router import router as chat_router
from manuals.drafts_router import router as drafts_router
from manuals.router import router as manuals_router

app = FastAPI()

app.include_router(auth_router)
app.include_router(manuals_router)
app.include_router(drafts_router)
app.include_router(chat_router)


@app.on_event("startup")
def on_startup():
    ensure_default_user()
