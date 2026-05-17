import json
import logging
import os
from uuid import uuid4
from typing import Any

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.exceptions import BadRequest

from env_loader import load_dotenv
from introspection_service import fetch_introspection
from storage import get_schema, init_db, save_schema
from yandex_client import YandexClientError, ask_yandex


SYSTEM_PROMPT = (
    "Ты GraphQL query builder. По телу входящего request и текстовому описанию задачи "
    "составляй корректный GraphQL operation для API из workspace. Учитывай контекст "
    "workspace: схему, доступные query/mutation, типы, поля и ограничения. "
    "Возвращай только JSON без markdown, без ``` и без поясняющего текста: "
    '{"query":"<GraphQL operation or empty string>","variables":{...},'
    '"operationName":"<name or null>","note":"<short note or empty string>",'
    '"hints":["<related useful request in Russian>",'
    '"<another related useful request in Russian>",'
    '"<another related useful request in Russian>"]}. '
    "Поле note заполняй только если запрос удалось выполнить не полностью, есть "
    "неоднозначность, не хватает данных, поле отсутствует в схеме или нужен комментарий "
    "для клиента; если всё получилось, note должен быть пустой строкой. "
    "Поле hints всегда возвращай массивом из 2-3 коротких подсказок на русском: что ещё "
    "пользователь может запросить по этой схеме. "
    "Если невозможно составить GraphQL operation, верни query пустой строкой, variables "
    "пустым объектом, operationName null, note с причиной и hints с вариантами исправления."
)


def create_app() -> Flask:
    load_dotenv()

    app = Flask(__name__)
    configure_cors(app)
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    init_db()

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    @app.post("/create_workspace")
    def create_workspace_route():
        payload, error_response = parse_json_payload()
        if error_response is not None:
            return error_response

        chat_id = extract_chat_id(payload) or create_workspace_id()
        endpoint = str(
            payload.get("endpoint") or payload.get("url") or payload.get("graphql_endpoint") or ""
        ).strip()
        token = str(payload.get("token") or "").strip()
        headers = payload.get("headers", {})

        if not endpoint:
            return jsonify({"success": False, "error": "endpoint is required"}), 400
        if not isinstance(headers, dict):
            return jsonify({"success": False, "error": "headers must be an object"}), 400

        introspection = run_introspection(endpoint=endpoint, token=token, headers=headers)
        if not introspection.get("success"):
            status = str(introspection.get("status") or "introspection_failed")
            http_status = introspection_status_code(status)
            return jsonify({"success": False, "introspection": introspection}), http_status

        schema = str(introspection.get("sdl") or "")
        save_schema(chat_id=chat_id, schema=schema)
        return jsonify(
            {
                "success": True,
                "id": chat_id,
                "chat_id": chat_id,
                "schema_saved": True,
                "schema_length": len(schema),
                "introspection_status": str(introspection.get("status") or "ok"),
            }
        ), 201

    @app.post("/query")
    def query_route():
        payload, error_response = parse_json_payload()
        if error_response is not None:
            return error_response

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

        graphql = normalize_graphql_answer(parse_graphql_answer(result["answer"]))
        return jsonify(
            {
                "success": True,
                "id": chat_id,
                "chat_id": chat_id,
                "answer": result["answer"],
                "graphql": graphql,
                "raw": result["raw"],
            }
        )

    return app


def configure_cors(app: Flask) -> None:
    origins = parse_cors_origins(
        os.getenv(
            "FRONTEND_ORIGINS",
            "https://yandex-ai-hack.vercel.app/,http://localhost:5173,http://127.0.0.1:5173",
        )
    )
    CORS(
        app,
        resources={r"/*": {"origins": origins}},
        methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )


def parse_cors_origins(value: str) -> list[str] | str:
    origins = [origin.strip() for origin in value.split(",") if origin.strip()]
    if "*" in origins:
        return "*"
    return origins


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


def normalize_graphql_answer(parsed: dict[str, Any] | None) -> dict[str, Any]:
    if parsed is None:
        return {
            "query": "",
            "variables": {},
            "operationName": None,
            "note": "Модель вернула ответ не в JSON-формате.",
            "hints": [],
        }

    query = parsed.get("query")
    variables = parsed.get("variables")
    operation_name = parsed.get("operationName")
    note = parsed.get("note")
    hints = parsed.get("hints")

    normalized_hints = [str(hint).strip() for hint in hints if str(hint).strip()] if isinstance(hints, list) else []

    return {
        "query": str(query or ""),
        "variables": variables if isinstance(variables, dict) else {},
        "operationName": operation_name if operation_name is None else str(operation_name),
        "note": str(note or ""),
        "hints": normalized_hints,
    }


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
    return str(payload.get("chat_id") or payload.get("id") or "").strip()


def create_workspace_id() -> str:
    return uuid4().hex


def parse_json_payload() -> tuple[dict[str, Any], Any]:
    if not request.is_json:
        return {}, (jsonify({"success": False, "error": "content-type must be application/json"}), 400)

    try:
        payload = request.get_json()
    except BadRequest:
        return {}, (jsonify({"success": False, "error": "invalid json body"}), 400)

    if payload is None:
        return {}, (jsonify({"success": False, "error": "json body is required"}), 400)
    if not isinstance(payload, dict):
        return {}, (jsonify({"success": False, "error": "json body must be an object"}), 400)
    return payload, None


app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
