from fastapi import FastAPI

from auth import ensure_default_user
from routers import auth_router, chat_router, manuals_router

app = FastAPI()

app.include_router(auth_router.router)
app.include_router(manuals_router.router)
app.include_router(chat_router.router)


@app.on_event("startup")
def on_startup():
    ensure_default_user()
