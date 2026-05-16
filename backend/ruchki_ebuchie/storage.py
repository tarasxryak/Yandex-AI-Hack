from __future__ import annotations

import os
import sqlite3
from pathlib import Path


DB_PATH = Path(os.getenv("SQLITE_PATH", "sqlite.db"))


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with connect() as db:
        current_columns = table_columns(db, "workspaces")
        if current_columns and current_columns != {"chat_id", "schema"}:
            db.execute("DROP TABLE workspaces")
            current_columns = set()
        if table_columns(db, "messages"):
            db.execute("DROP TABLE messages")
        if not current_columns:
            db.execute(
                """
                CREATE TABLE workspaces (
                    chat_id TEXT PRIMARY KEY,
                    schema TEXT NOT NULL
                )
                """
            )


def table_columns(db: sqlite3.Connection, table: str) -> set[str]:
    rows = db.execute(f"PRAGMA table_info({table})").fetchall()
    return {row["name"] for row in rows}


def save_schema(chat_id: str, schema: str) -> dict[str, str]:
    with connect() as db:
        db.execute(
            """
            INSERT INTO workspaces (chat_id, schema)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET schema = excluded.schema
            """,
            (chat_id, schema),
        )
        row = db.execute(
            "SELECT chat_id, schema FROM workspaces WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()
    return dict(row)


def get_schema(chat_id: str) -> str | None:
    with connect() as db:
        row = db.execute(
            "SELECT schema FROM workspaces WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()
    return str(row["schema"]) if row else None
