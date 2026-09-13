from sqlalchemy import create_engine

from backend_app.config import DB_URL

engine = create_engine(DB_URL)
