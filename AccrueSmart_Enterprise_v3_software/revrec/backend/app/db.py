from __future__ import annotations

from typing import Generator

from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy import text

# IMPORTANT:
# Import model modules so SQLModel metadata registers all tables before create_all().
# Adjust these imports to match your actual project files.
#
# If you have a single models package/file:
# from .models.models import *  # noqa: F401,F403
#
# If you added enterprise/graph models in a separate file:
# from . import models_enterprise  # noqa: F401
#
# You can keep BOTH if both exist.

try:
    from .models.models import *  # noqa: F401,F403
except Exception:
    pass

try:
    from . import models_enterprise  # noqa: F401
except Exception:
    pass

# If your graph models are in a separate file like app/models/accounting_graph.py,
# make sure they are imported too (so tables get created).
try:
    from .models.accounting_graph import *  # noqa: F401,F403
except Exception:
    pass


DB_URL = "sqlite:///revrec.db"
engine = create_engine(DB_URL, echo=False)


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    result = conn.execute(text(f"PRAGMA table_info({table_name})"))
    cols = result.fetchall()
    return any(str(row[1]) == column_name for row in cols)


def _safe_add_column(conn, table_name: str, column_name: str, column_sql: str) -> None:
    if not _column_exists(conn, table_name, column_name):
        conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}"))
        print(f"### MIGRATION: added {table_name}.{column_name}")
    else:
        print(f"### MIGRATION: exists {table_name}.{column_name}")


def run_sqlite_migrations() -> None:
    """
    Lightweight SQLite auto-migrations for existing local DBs.
    Safe to run on every startup.
    """
    with engine.begin() as conn:
        # Ensure all known tables exist first
        SQLModel.metadata.create_all(engine)

        # Existing migration: schedule_rows audit-friendly columns
        tables = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='schedule_rows'")
        ).fetchall()

        if not tables:
            print("### MIGRATION: schedule_rows table not found yet (skipping column migration)")
            return

        _safe_add_column(conn, "schedule_rows", "event_type", "event_type TEXT")
        _safe_add_column(conn, "schedule_rows", "is_adjustment", "is_adjustment INTEGER DEFAULT 0")
        _safe_add_column(conn, "schedule_rows", "notes", "notes TEXT")
        _safe_add_column(conn, "schedule_rows", "effective_date", "effective_date TEXT")
        _safe_add_column(conn, "schedule_rows", "reference_row_id", "reference_row_id INTEGER")


def init_db() -> None:
    """
    Keep this function name because main.py calls it on startup.
    """
    SQLModel.metadata.create_all(engine)
    run_sqlite_migrations()


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


print("### USING DB FILE:", __file__)
print("### USING DB URL:", DB_URL)
