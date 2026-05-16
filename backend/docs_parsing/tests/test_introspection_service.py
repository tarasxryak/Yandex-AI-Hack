from __future__ import annotations

import responses

from introspection_service import fetch_introspection


ENDPOINT = "https://example.com/graphql"


@responses.activate
def test_fetch_introspection_returns_sdl() -> None:
    responses.add(responses.POST, ENDPOINT, json=valid_introspection(), status=200)

    result = fetch_introspection(ENDPOINT)

    assert result["success"] is True
    assert result["status"] == "ok"
    assert "type Query" in result["sdl"]
    assert "user(id: ID!): User" in result["sdl"]
    assert "introspection" not in result


@responses.activate
def test_fetch_introspection_sends_auth_headers() -> None:
    responses.add(responses.POST, ENDPOINT, json=valid_introspection(), status=200)

    fetch_introspection(ENDPOINT, token="secret", headers={"X-API-Key": "key"})

    request = responses.calls[0].request
    assert request.headers["Authorization"] == "Bearer secret"
    assert request.headers["X-API-Key"] == "key"


@responses.activate
def test_fetch_introspection_classifies_auth_required() -> None:
    responses.add(responses.POST, ENDPOINT, json={"errors": [{"message": "missing token"}]}, status=401)

    result = fetch_introspection(ENDPOINT)

    assert result["success"] is False
    assert result["status"] == "auth_required"
    assert result["http_status"] == 401
    assert "response" in result


@responses.activate
def test_fetch_introspection_classifies_disabled_introspection() -> None:
    responses.add(
        responses.POST,
        ENDPOINT,
        json={"errors": [{"message": "GraphQL introspection is disabled"}]},
        status=200,
    )

    result = fetch_introspection(ENDPOINT)

    assert result["success"] is False
    assert result["status"] == "introspection_disabled"
    assert result["hint"]


@responses.activate
def test_fetch_introspection_handles_invalid_json() -> None:
    responses.add(responses.POST, ENDPOINT, body="<html>nope</html>", status=200)

    result = fetch_introspection(ENDPOINT)

    assert result["success"] is False
    assert result["status"] == "invalid_response"
    assert result["response_text"] == "<html>nope</html>"


@responses.activate
def test_fetch_introspection_handles_http_error() -> None:
    responses.add(responses.POST, ENDPOINT, json={"errors": [{"message": "boom"}]}, status=500)

    result = fetch_introspection(ENDPOINT)

    assert result["success"] is False
    assert result["status"] == "http_error"
    assert result["http_status"] == 500


def test_fetch_introspection_rejects_empty_endpoint() -> None:
    result = fetch_introspection(" ")

    assert result["success"] is False
    assert result["status"] == "invalid_request"


def valid_introspection() -> dict:
    return {
        "data": {
            "__schema": {
                "queryType": {"name": "Query"},
                "mutationType": None,
                "subscriptionType": None,
                "types": [
                    {
                        "kind": "OBJECT",
                        "name": "Query",
                        "description": None,
                        "fields": [
                            {
                                "name": "user",
                                "description": "Find user",
                                "args": [
                                    {
                                        "name": "id",
                                        "description": None,
                                        "type": {
                                            "kind": "NON_NULL",
                                            "name": None,
                                            "ofType": {"kind": "SCALAR", "name": "ID", "ofType": None},
                                        },
                                        "defaultValue": None,
                                    }
                                ],
                                "type": {"kind": "OBJECT", "name": "User", "ofType": None},
                                "isDeprecated": False,
                                "deprecationReason": None,
                            }
                        ],
                        "inputFields": None,
                        "interfaces": [],
                        "enumValues": None,
                        "possibleTypes": None,
                    },
                    {
                        "kind": "OBJECT",
                        "name": "User",
                        "description": "Application user",
                        "fields": [
                            {
                                "name": "id",
                                "description": None,
                                "args": [],
                                "type": {
                                    "kind": "NON_NULL",
                                    "name": None,
                                    "ofType": {"kind": "SCALAR", "name": "ID", "ofType": None},
                                },
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "name",
                                "description": None,
                                "args": [],
                                "type": {"kind": "SCALAR", "name": "String", "ofType": None},
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                        ],
                        "inputFields": None,
                        "interfaces": [],
                        "enumValues": None,
                        "possibleTypes": None,
                    },
                    {
                        "kind": "SCALAR",
                        "name": "ID",
                        "description": None,
                        "fields": None,
                        "inputFields": None,
                        "interfaces": None,
                        "enumValues": None,
                        "possibleTypes": None,
                    },
                    {
                        "kind": "SCALAR",
                        "name": "String",
                        "description": None,
                        "fields": None,
                        "inputFields": None,
                        "interfaces": None,
                        "enumValues": None,
                        "possibleTypes": None,
                    },
                    {
                        "kind": "SCALAR",
                        "name": "Boolean",
                        "description": None,
                        "fields": None,
                        "inputFields": None,
                        "interfaces": None,
                        "enumValues": None,
                        "possibleTypes": None,
                    },
                    {
                        "kind": "OBJECT",
                        "name": "__Schema",
                        "description": None,
                        "fields": [],
                        "inputFields": None,
                        "interfaces": [],
                        "enumValues": None,
                        "possibleTypes": None,
                    },
                    {
                        "kind": "OBJECT",
                        "name": "__Type",
                        "description": None,
                        "fields": [],
                        "inputFields": None,
                        "interfaces": [],
                        "enumValues": None,
                        "possibleTypes": None,
                    },
                ],
                "directives": [],
            }
        }
    }
