from __future__ import annotations

import os
from typing import Any

import requests

from env_loader import load_dotenv


YANDEX_OPENAI_BASE_URL = "https://llm.api.cloud.yandex.net/v1"


class YandexClientError(RuntimeError):
    pass


def ask_yandex(messages: list[dict[str, str]]) -> dict[str, Any]:
    load_dotenv()

    api_key = os.getenv("YANDEX_API_KEY", "").strip()
    folder_id = os.getenv("YANDEX_FOLDER_ID", "").strip()
    model_uri = os.getenv("YANDEX_MODEL_URI", "").strip()
    base_url = os.getenv("YANDEX_OPENAI_BASE_URL", YANDEX_OPENAI_BASE_URL).rstrip("/")

    if not api_key:
        raise YandexClientError("YANDEX_API_KEY is required")
    if not model_uri:
        if not folder_id:
            raise YandexClientError("YANDEX_FOLDER_ID or YANDEX_MODEL_URI is required")
        model_uri = f"gpt://{folder_id}/yandexgpt/latest"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if folder_id:
        headers["OpenAI-Project"] = folder_id

    request_body = {
        "model": model_uri,
        "messages": [
            {
                "role": message["role"],
                "content": message["text"],
            }
            for message in messages
        ],
        "temperature": float(os.getenv("YANDEX_TEMPERATURE", "0.3")),
        "max_tokens": int(os.getenv("YANDEX_MAX_TOKENS", "2000")),
        "stream": False,
    }

    try:
        response = requests.post(
            f"{base_url}/chat/completions",
            json=request_body,
            headers=headers,
            timeout=float(os.getenv("YANDEX_TIMEOUT_SECONDS", "60")),
        )
    except requests.RequestException as exc:
        raise YandexClientError(f"YandexGPT request failed: {exc}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise YandexClientError(
            f"YandexGPT returned non-json response with status {response.status_code}"
        ) from exc

    if response.status_code < 200 or response.status_code >= 300:
        message = payload.get("message") or payload.get("error") or "YandexGPT returned an error"
        raise YandexClientError(f"{message} (status {response.status_code})")

    choices = payload.get("choices") or []
    if not choices:
        raise YandexClientError("YandexGPT response has no choices")

    message = choices[0].get("message") or {}
    answer = str(message.get("content") or "").strip()
    if not answer:
        raise YandexClientError("YandexGPT response is empty")

    return {
        "answer": answer,
        "raw": payload,
    }
