"""Tiny database helper.

SQLite (the default) uses Python's built-in sqlite3, so nothing extra to install.
PostgreSQL URLs use SQLAlchemy, which is imported only when needed:
    pip install sqlalchemy psycopg2-binary
    postgresql+psycopg2://user:password@localhost:5432/olist
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pandas as pd


def connect(db_url: str):
    """Return a sqlite3 connection for sqlite:/// URLs, otherwise a SQLAlchemy engine."""
    if db_url.startswith("sqlite:///"):
        path = Path(db_url.replace("sqlite:///", "", 1))
        path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(path)
    from sqlalchemy import create_engine  # optional dependency
    return create_engine(db_url)


def _statements(ddl_text: str) -> list[str]:
    sql = "\n".join(line for line in ddl_text.splitlines() if not line.strip().startswith("--"))
    return [s.strip() for s in re.split(r";\s*(?:\n|$)", sql) if s.strip()]


def run_script(conn, ddl_path: Path) -> None:
    """Execute every statement in a .sql file (used for the schema)."""
    ddl_text = Path(ddl_path).read_text()
    if isinstance(conn, sqlite3.Connection):
        conn.executescript(ddl_text)
        conn.commit()
        return
    from sqlalchemy import text
    with conn.begin() as c:
        for stmt in _statements(ddl_text):
            c.execute(text(stmt))


def read_df(conn, sql: str) -> pd.DataFrame:
    if isinstance(conn, sqlite3.Connection):
        return pd.read_sql(sql, conn)
    from sqlalchemy import text
    with conn.connect() as c:
        return pd.read_sql(text(sql), c)
