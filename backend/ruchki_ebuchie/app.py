import json
import logging
import os
from typing import Any

import requests
from flask import Flask, jsonify, request

from env_loader import load_dotenv
from introspection_service import fetch_introspection
from storage import get_schema, init_db, save_schema
from yandex_client import YandexClientError, ask_yandex


SYSTEM_PROMPT = (
    "Ты GraphQL query builder. По телу входящего request и текстовому описанию задачи "
    "составляй корректный GraphQL operation для API из workspace. Учитывай контекст "
    "workspace: схему, доступные query/mutation, типы, поля и ограничения. "
    "Возвращай только JSON без markdown, без ``` и без поясняющего текста: "
    '{"query":"<GraphQL operation>","variables":{...},"operationName":"<name or null>"}. '
    "Если данных недостаточно или нужного поля нет в схеме, верни JSON с ключом error и "
    "коротким explanation."
)


def create_app() -> Flask:
    load_dotenv()

    app = Flask(__name__)
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    init_db()

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    @app.post("/create_workspace")
    def create_workspace_route():
        payload: dict[str, Any] = request.get_json(silent=True) or {}
        chat_id = extract_chat_id(payload)
        endpoint = str(
            payload.get("endpoint") or payload.get("url") or payload.get("graphql_endpoint") or ""
        ).strip()
        token = str(payload.get("token") or "").strip()
        headers = payload.get("headers", {})

        if not chat_id:
            return jsonify({"success": False, "error": "chat_id is required"}), 400
        if not endpoint:
            return jsonify({"success": False, "error": "endpoint is required"}), 400
        if not isinstance(headers, dict):
            return jsonify({"success": False, "error": "headers must be an object"}), 400

        introspection = run_introspection(endpoint=endpoint, token=token, headers=headers)
        if not introspection.get("success"):
            status = str(introspection.get("status") or "introspection_failed")
            http_status = introspection_status_code(status)
            return jsonify({"success": False, "introspection": introspection}), http_status

        workspace = save_schema(chat_id=chat_id, schema=str(introspection.get("sdl") or ""))
        return jsonify({"success": True, "workspace": workspace, "introspection": introspection}), 201

    @app.post("/query")
    def query_route():
        payload: dict[str, Any] = request.get_json(silent=True) or {}
        chat_id = extract_chat_id(payload)
        query = str(payload.get("query") or "").strip()
        request_body = payload.get("request_body", payload.get("body"))

        if not chat_id:
            return jsonify({"success": False, "error": "chat_id is required"}), 400
        if not query and request_body is None:
            return jsonify({"success": False, "error": "query or request_body is required"}), 400

        schema = get_schema(chat_id)
        if schema is None:
            return jsonify({"success": False, "error": "schema not found for chat_id"}), 404

        user_prompt = build_user_prompt(query=query, request_body=request_body)
        messages = build_messages(schema, user_prompt)

        try:
            result = ask_yandex(messages)
        except YandexClientError as exc:
            app.logger.warning("query failed chat_id=%s error=%s", chat_id, exc)
            return jsonify({"success": False, "error": str(exc)}), 502

        graphql = parse_graphql_answer(result["answer"])
        return jsonify(
            {
                "success": True,
                "chat_id": chat_id,
                "answer": result["answer"],
                "graphql": graphql,
                "raw": result["raw"],
            }
        )

    return app


def build_messages(schema: str, query: str) -> list[dict[str, str]]:
    system_text = SYSTEM_PROMPT
    system_text = f"{system_text}\n\nGraphQL SDL schema:\n{schema}"

    messages = [{"role": "system", "text": system_text}]
    messages.append({"role": "user", "text": query})
    return messages


def build_user_prompt(query: str, request_body: Any) -> str:
    parts = []
    if query:
        parts.append(f"Описание задачи:\n{query}")
    if request_body is not None:
        body = json.dumps(request_body, ensure_ascii=False, indent=2)
        parts.append(f"Тело request:\n{body}")
    return "\n\n".join(parts)


def parse_graphql_answer(answer: str) -> dict[str, Any] | None:
    text = answer.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, dict):
        return None
    return parsed


def run_introspection(
    endpoint: str,
    token: str | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    docs_parser_url = os.getenv("DOCS_PARSER_URL", "").strip().rstrip("/")
    if not docs_parser_url:
        return fetch_introspection(endpoint=endpoint, token=token, headers=headers)

    try:
        response = requests.post(
            f"{docs_parser_url}/introspect",
            json={"endpoint": endpoint, "token": token or "", "headers": headers or {}},
            timeout=35,
        )
    except requests.RequestException as exc:
        return {
            "success": False,
            "status": "docs_parser_unavailable",
            "message": f"docs-parser request failed: {exc}",
            "endpoint": endpoint,
        }

    try:
        result = response.json()
    except ValueError:
        return {
            "success": False,
            "status": "docs_parser_invalid_response",
            "message": "docs-parser returned non-json response",
            "http_status": response.status_code,
            "endpoint": endpoint,
            "response_text": response.text.strip(),
        }

    if response.status_code >= 500 and result.get("success") is not False:
        result["success"] = False
        result["status"] = "docs_parser_error"
        result["http_status"] = response.status_code
    return result


def introspection_status_code(status: str) -> int:
    if status == "ok":
        return 200
    if status == "invalid_request":
        return 400
    if status == "auth_required":
        return 401
    if status in {"introspection_disabled", "graphql_error", "preprocess_failed"}:
        return 422
    return 502


def extract_chat_id(payload: dict[str, Any]) -> str:
    return str(payload.get("chat_id") or payload.get("workspace_id") or payload.get("id") or "").strip()


app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
