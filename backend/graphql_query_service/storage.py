from __future__ import annotations

import json
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
                            `schema` LONGTEXT NOT NULL,
                            endpoint TEXT NULL,
                            headers LONGTEXT NULL,
                            token TEXT NULL
                        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
                        """
                    )
                    ensure_column(cursor, "workspaces", "endpoint", "TEXT NULL")
                    ensure_column(cursor, "workspaces", "headers", "LONGTEXT NULL")
                    ensure_column(cursor, "workspaces", "token", "TEXT NULL")
                    drop_legacy_table(cursor, "messages")
            return
        except pymysql.MySQLError as exc:
            last_error = exc
            time.sleep(float(os.getenv("MYSQL_CONNECT_RETRY_SECONDS", "1")))

    raise RuntimeError(f"connect to mysql: {last_error}") from last_error


def drop_legacy_table(cursor: Any, table: str) -> None:
    cursor.execute("DROP TABLE IF EXISTS `%s`" % table)


def ensure_column(cursor: Any, table: str, column: str, definition: str) -> None:
    cursor.execute(
        """
        SELECT COUNT(*) AS count
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = %s
          AND column_name = %s
        """,
        (table, column),
    )
    row = cursor.fetchone()
    if row and int(row["count"]) == 0:
        cursor.execute(f"ALTER TABLE `{table}` ADD COLUMN `{column}` {definition}")


def save_workspace(
    chat_id: str,
    schema: str,
    endpoint: str,
    headers: dict[str, str] | None = None,
    token: str = "",
) -> dict[str, Any]:
    headers_json = json.dumps(headers or {}, ensure_ascii=False)
    with connect() as db:
        with db.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO workspaces (chat_id, `schema`, endpoint, headers, token)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    `schema` = VALUES(`schema`),
                    endpoint = VALUES(endpoint),
                    headers = VALUES(headers),
                    token = VALUES(token)
                """,
                (chat_id, schema, endpoint, headers_json, token),
            )
            cursor.execute(
                "SELECT chat_id, `schema`, endpoint, headers, token FROM workspaces WHERE chat_id = %s",
                (chat_id,),
            )
            row = cursor.fetchone()
    return dict(row)


def save_schema(chat_id: str, schema: str) -> dict[str, Any]:
    return save_workspace(chat_id=chat_id, schema=schema, endpoint="")


def get_schema(chat_id: str) -> str | None:
    workspace = get_workspace(chat_id)
    return workspace["schema"] if workspace else None


def get_workspace(chat_id: str) -> dict[str, Any] | None:
    with connect() as db:
        with db.cursor() as cursor:
            cursor.execute(
                "SELECT chat_id, `schema`, endpoint, headers, token FROM workspaces WHERE chat_id = %s",
                (chat_id,),
            )
            row = cursor.fetchone()
    if not row:
        return None

    headers = {}
    if row.get("headers"):
        try:
            parsed_headers = json.loads(str(row["headers"]))
            if isinstance(parsed_headers, dict):
                headers = {str(key): str(value) for key, value in parsed_headers.items()}
        except json.JSONDecodeError:
            headers = {}

    return {
        "chat_id": str(row["chat_id"]),
        "schema": str(row["schema"]),
        "endpoint": str(row.get("endpoint") or ""),
        "headers": headers,
        "token": str(row.get("token") or ""),
    }
