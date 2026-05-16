import logging
import os
from typing import Any

from flask import Flask, jsonify, request

from introspection_service import fetch_introspection


def create_app() -> Flask:
    app = Flask(__name__)
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    @app.post("/introspect")
    def introspect():
        payload: dict[str, Any] = request.get_json(silent=True) or {}
        endpoint = payload.get("endpoint", "")
        token = payload.get("token", "")
        headers = payload.get("headers") or {}

        app.logger.info(
            "introspect started endpoint=%r remote=%s token=%s headers=%s",
            endpoint,
            request.remote_addr,
            bool(str(token).strip()),
            list(headers.keys()) if isinstance(headers, dict) else [],
        )

        result = fetch_introspection(
            endpoint=endpoint,
            token=token,
            headers=headers,
        )

        app.logger.info(
            "introspect finished endpoint=%r success=%s status=%s upstream_status=%s",
            endpoint,
            result.get("success"),
            result.get("status"),
            result.get("http_status"),
        )
        return jsonify(result)

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
