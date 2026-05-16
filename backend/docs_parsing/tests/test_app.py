from __future__ import annotations

import responses

from app import create_app
from tests.test_introspection_service import ENDPOINT, valid_introspection


def test_healthz() -> None:
    app = create_app()
    client = app.test_client()

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


@responses.activate
def test_introspect_endpoint() -> None:
    responses.add(responses.POST, ENDPOINT, json=valid_introspection(), status=200)
    app = create_app()
    client = app.test_client()

    response = client.post("/introspect", json={"endpoint": ENDPOINT})

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert "type Query" in body["sdl"]
