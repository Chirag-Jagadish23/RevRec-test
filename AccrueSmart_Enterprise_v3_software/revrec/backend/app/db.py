from __future__ import annotations

from typing import Generator

from sqlmodel import SQLModel, Session, create_engine

from sqlalchemy.engine import URL as SA_URL
from .core.config import (
    SUPABASE_DB_HOST, SUPABASE_DB_PORT, SUPABASE_DB_USER,
    SUPABASE_DB_PASSWORD, SUPABASE_DB_NAME,
)

# Import all model modules so SQLModel metadata registers every table before create_all().
try:
    from .models.models import *  # noqa: F401,F403
except Exception:
    pass

try:
    from . import models_enterprise  # noqa: F401
except Exception:
    pass

try:
    from .models.accounting_graph import *  # noqa: F401,F403
except Exception:
    pass


def _build_engine():
    if SUPABASE_DB_HOST:
        # Supabase Postgres via pooler — URL.create() handles special chars in password safely
        url = SA_URL.create(
            drivername="postgresql+psycopg2",
            username=SUPABASE_DB_USER,
            password=SUPABASE_DB_PASSWORD,
            host=SUPABASE_DB_HOST,
            port=SUPABASE_DB_PORT,
            database=SUPABASE_DB_NAME,
        )
        print(f"### DB: Supabase Postgres @ {SUPABASE_DB_HOST}:{SUPABASE_DB_PORT}")
        return create_engine(url, echo=False)
    else:
        # Fallback: local SQLite for dev without .env
        print("### DB: SQLite fallback (no SUPABASE_DB_HOST set)")
        return create_engine("sqlite:///revrec.db", echo=False)


engine = _build_engine()


def init_db() -> None:
    """Create all tables in Supabase Postgres on startup (safe — no-op if tables already exist)."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
