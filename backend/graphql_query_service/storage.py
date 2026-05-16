from __future__ import annotations

import os
import time
from typing import Any

import pymysql
from pymysql.cursors import DictCursor


def connect() -> pymysql.connections.Connection:
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "ruchki"),
        password=os.getenv("MYSQL_PASSWORD", "ruchki"),
        database=os.getenv("MYSQL_DATABASE", "ruchki"),
        charset="utf8mb4",
        autocommit=True,
        cursorclass=DictCursor,
    )


def init_db() -> None:
    last_error: Exception | None = None
    for _ in range(int(os.getenv("MYSQL_CONNECT_RETRIES", "30"))):
        try:
            with connect() as db:
                with db.cursor() as cursor:
                    cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS workspaces (
                            chat_id VARCHAR(255) PRIMARY KEY,
                            `schema` LONGTEXT NOT NULL
                        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
                        """
                    )
                    drop_legacy_table(cursor, "messages")
            return
        except pymysql.MySQLError as exc:
            last_error = exc
            time.sleep(float(os.getenv("MYSQL_CONNECT_RETRY_SECONDS", "1")))

    raise RuntimeError(f"connect to mysql: {last_error}") from last_error


def drop_legacy_table(cursor: Any, table: str) -> None:
    cursor.execute("DROP TABLE IF EXISTS `%s`" % table)


def save_schema(chat_id: str, schema: str) -> dict[str, str]:
    with connect() as db:
        with db.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO workspaces (chat_id, `schema`)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE `schema` = VALUES(`schema`)
                """,
                (chat_id, schema),
            )
            cursor.execute(
                "SELECT chat_id, `schema` FROM workspaces WHERE chat_id = %s",
                (chat_id,),
            )
            row = cursor.fetchone()
    return dict(row)


def get_schema(chat_id: str) -> str | None:
    with connect() as db:
        with db.cursor() as cursor:
            cursor.execute(
                "SELECT `schema` FROM workspaces WHERE chat_id = %s",
                (chat_id,),
            )
            row = cursor.fetchone()
    return str(row["schema"]) if row else None
