import json
import logging
import os
import re
import shutil
from pathlib import Path
from uuid import uuid4
from typing import Any

import requests
from flask import Flask, jsonify, request, send_from_directory
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
    "Не используй GraphQL variables в query. Подставляй значения из тела request или "
    "текста пользователя прямо в GraphQL operation: name: \"Rick\", id: \"1\", page: 2. "
    "Поле variables всегда возвращай пустым объектом {}. "
    "Если значения для аргумента нет, верни пустой query и причину в note. "
    "Если невозможно составить GraphQL operation, верни query пустой строкой, variables "
    "пустым объектом, operationName null, note с причиной и hints с вариантами исправления."
)


def create_app() -> Flask:
    load_dotenv()

    app = Flask(__name__, static_folder=None)
    configure_cors(app)
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    init_db()
    reports_dir().mkdir(parents=True, exist_ok=True)

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    @app.get("/static/<path:filename>")
    def static_file(filename: str):
        ensure_report_file(filename)
        return send_from_directory(reports_dir(), filename)

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

        graphql = normalize_graphql_answer(
            parse_graphql_answer(result["answer"]),
            request_body=request_body,
        )
        graphql["report_link"] = publish_report(chat_id)
        graphql.pop("variables", None)
        return jsonify(
            {
                "success": True,
                "chat_id": chat_id,
                "graphql": graphql,
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


def normalize_graphql_answer(
    parsed: dict[str, Any] | None,
    request_body: Any = None,
) -> dict[str, Any]:
    if parsed is None:
        return {
            "query": "",
            "variables": {},
            "operationName": None,
            "note": "Модель вернула ответ не в JSON-формате.",
            "hints": [],
            "report_link": None,
        }

    query = parsed.get("query")
    variables = parsed.get("variables")
    operation_name = parsed.get("operationName")
    note = parsed.get("note")
    hints = parsed.get("hints")

    normalized_hints = [str(hint).strip() for hint in hints if str(hint).strip()] if isinstance(hints, list) else []

    normalized = {
        "query": str(query or ""),
        "variables": variables if isinstance(variables, dict) else {},
        "operationName": operation_name if operation_name is None else str(operation_name),
        "note": str(note or ""),
        "hints": normalized_hints,
        "report_link": None,
    }
    complete_graphql_variables(normalized, request_body)
    inline_graphql_variables(normalized)
    return normalized


def complete_graphql_variables(graphql: dict[str, Any], request_body: Any) -> None:
    query = str(graphql.get("query") or "")
    variables = graphql.get("variables")
    if not query or not isinstance(variables, dict):
        return

    declared_variables = declared_graphql_variables(query)
    if not declared_variables:
        return

    if isinstance(request_body, dict):
        for variable_name in declared_variables:
            if variable_name not in variables and variable_name in request_body:
                variables[variable_name] = request_body[variable_name]

    missing_variables = [name for name in declared_variables if name not in variables]
    if missing_variables:
        note = str(graphql.get("note") or "").strip()
        missing_text = ", ".join(f"${name}" for name in missing_variables)
        auto_note = f"Не хватает значений для GraphQL variables: {missing_text}."
        graphql["note"] = f"{note} {auto_note}".strip()


def declared_graphql_variables(query: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"\$([A-Za-z_][A-Za-z0-9_]*)\s*:", query)))


def inline_graphql_variables(graphql: dict[str, Any]) -> None:
    query = str(graphql.get("query") or "")
    variables = graphql.get("variables")
    if not query or not isinstance(variables, dict):
        return

    declared_variables = declared_graphql_variables(query)
    if not declared_variables:
        graphql["variables"] = {}
        return

    missing_variables = [name for name in declared_variables if name not in variables]
    if missing_variables:
        note = str(graphql.get("note") or "").strip()
        missing_text = ", ".join(f"${name}" for name in missing_variables)
        auto_note = f"Нельзя подставить значения в GraphQL query: не хватает {missing_text}."
        graphql["query"] = ""
        graphql["variables"] = {}
        graphql["note"] = f"{note} {auto_note}".strip()
        return

    inlined_query = query
    for variable_name in declared_variables:
        inlined_query = re.sub(
            rf"\${re.escape(variable_name)}\b",
            graphql_literal(variables[variable_name]),
            inlined_query,
        )

    inlined_query = re.sub(
        r"\b(query|mutation|subscription)(\s+[A-Za-z_][A-Za-z0-9_]*)?\s*\([^)]*\)",
        lambda match: f"{match.group(1)}{match.group(2) or ''}",
        inlined_query,
        count=1,
    )

    graphql["query"] = inlined_query
    graphql["variables"] = {}


def graphql_literal(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(graphql_literal(item) for item in value) + "]"
    if isinstance(value, dict):
        fields = [f"{key}: {graphql_literal(item)}" for key, item in value.items()]
        return "{" + ", ".join(fields) + "}"
    return json.dumps(str(value), ensure_ascii=False)


def publish_report(chat_id: str) -> str | None:
    source_path = report_source_path()
    filename = f"{safe_report_id(chat_id)}.pdf"
    if source_path is None:
        return None

    if not copy_report(source_path, filename):
        return None
    return f"{request.host_url.rstrip('/')}/static/{filename}"


def ensure_report_file(filename: str) -> None:
    target_path = reports_dir() / filename
    if target_path.is_file() or "/" in filename or not filename.endswith(".pdf"):
        return

    source_path = report_source_path()
    if source_path is not None:
        copy_report(source_path, filename)


def copy_report(source_path: Path, filename: str) -> bool:
    target_path = reports_dir() / filename
    try:
        shutil.copyfile(source_path, target_path)
    except OSError:
        return False
    return True


def report_source_path() -> Path | None:
    configured = os.getenv("REPORT_SOURCE_PATH", "").strip()
    candidates = [configured] if configured else []
    candidates.extend(
        [
            "/app/core/product_report.pdf",
            "../../core/product_report.pdf",
            "../core/product_report.pdf",
            "product_report.pdf",
        ]
    )

    for candidate in candidates:
        path = Path(candidate)
        if path.is_file():
            return path
    return None


def reports_dir() -> Path:
    return Path(os.getenv("REPORTS_DIR", "static"))


def safe_report_id(value: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value).strip(".-")
    return safe or uuid4().hex


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
