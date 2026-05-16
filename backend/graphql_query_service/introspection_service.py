from __future__ import annotations

from typing import Any

import requests
from graphql import build_client_schema, get_introspection_query, print_schema


INTROSPECTION_QUERY = get_introspection_query(descriptions=True)


def fetch_introspection(
    endpoint: str,
    token: str | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    endpoint = (endpoint or "").strip()
    if not endpoint:
        return {
            "success": False,
            "status": "invalid_request",
            "message": "endpoint is required",
        }

    request_headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "ruchki-ebuchie/0.1",
    }
    if token and str(token).strip():
        request_headers["Authorization"] = f"Bearer {str(token).strip()}"
    if headers:
        request_headers.update(
            {str(name).strip(): str(value) for name, value in headers.items() if str(name).strip()}
        )

    try:
        response = requests.post(
            endpoint,
            json={"query": INTROSPECTION_QUERY, "operationName": "IntrospectionQuery"},
            headers=request_headers,
            timeout=30,
        )
    except requests.RequestException as exc:
        return {
            "success": False,
            "status": "request_failed",
            "message": f"send introspection request: {exc}",
            "endpoint": endpoint,
        }

    if response.status_code in (401, 403):
        result = {
            "success": False,
            "status": "auth_required",
            "message": "GraphQL endpoint requires authorization for introspection",
            "hint": 'retry with token or headers, for example {"token":"..."} or {"headers":{"Authorization":"Bearer ..."}}',
            "http_status": response.status_code,
            "endpoint": endpoint,
        }
        attach_response(result, response)
        return result

    try:
        payload = response.json()
    except ValueError:
        return {
            "success": False,
            "status": "invalid_response",
            "message": "introspection response is not valid json",
            "http_status": response.status_code,
            "endpoint": endpoint,
            "response_text": response.text.strip(),
        }

    if response.status_code < 200 or response.status_code >= 300:
        return {
            "success": False,
            "status": "http_error",
            "message": "GraphQL endpoint returned non-success status",
            "http_status": response.status_code,
            "endpoint": endpoint,
            "response": payload,
        }

    schema_payload = payload.get("data", {}).get("__schema")
    if not schema_payload:
        status = classify_graphql_error(payload.get("errors") or [])
        result = {
            "success": False,
            "status": status,
            "message": "GraphQL endpoint did not return introspection schema",
            "http_status": response.status_code,
            "endpoint": endpoint,
            "response": payload,
        }
        if status == "introspection_disabled":
            result["message"] = "GraphQL introspection is disabled by the server"
            result["hint"] = "provide authorization if introspection is private, or import schema SDL instead"
        return result

    try:
        client_schema = build_client_schema(payload["data"])
        sdl = print_schema(client_schema)
    except Exception as exc:
        return {
            "success": False,
            "status": "preprocess_failed",
            "message": f"build client schema: {exc}",
            "http_status": response.status_code,
            "endpoint": endpoint,
            "response": payload,
        }

    return {
        "success": True,
        "status": "ok",
        "message": "introspection fetched and converted to SDL successfully",
        "http_status": response.status_code,
        "endpoint": endpoint,
        "sdl": sdl,
    }


def attach_response(result: dict[str, Any], response: requests.Response) -> None:
    try:
        result["response"] = response.json()
    except ValueError:
        if response.text:
            result["response_text"] = response.text.strip()


def classify_graphql_error(errors: list[dict[str, Any]]) -> str:
    for error in errors:
        message = str(error.get("message", "")).lower()
        if "introspection" in message and any(
            part in message for part in ("disabled", "not allowed", "disallow", "forbidden")
        ):
            return "introspection_disabled"
        if "__schema" in message or "__type" in message:
            return "introspection_disabled"
        if any(part in message for part in ("unauthorized", "unauthenticated", "authentication", "token")):
            return "auth_required"

    return "graphql_error"
