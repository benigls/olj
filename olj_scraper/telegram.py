from __future__ import annotations

from typing import Any

import dlt
import requests

from .config import TELEGRAM_API_BASE, TELEGRAM_MAX_MESSAGE_LENGTH


def get_secret(name: str) -> str:
    try:
        value = dlt.secrets[name]
    except Exception as exc:
        raise RuntimeError(f"Missing dlt secret: {name}") from exc

    if value is None:
        raise RuntimeError(f"Missing dlt secret: {name}")

    value = str(value).strip()
    if not value:
        raise RuntimeError(f"Empty dlt secret: {name}")

    return value


def send_telegram_message(
    token: str, chat_id: str, text: str, parse_mode: str = "MarkdownV2"
) -> None:
    token = token.strip()
    chat_id = chat_id.strip()
    text = text.strip()

    if not token:
        raise RuntimeError("Telegram bot token is empty.")
    if not chat_id:
        raise RuntimeError("Telegram chat id is empty.")
    if not text:
        raise RuntimeError("Telegram message text is empty.")

    url = f"{TELEGRAM_API_BASE}/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text[:TELEGRAM_MAX_MESSAGE_LENGTH],
        "disable_web_page_preview": False,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    response = requests.post(url, json=payload, timeout=30)
    if response.ok:
        return

    try:
        error_detail: Any = response.json()
    except ValueError:
        error_detail = response.text

    raise RuntimeError(
        f"Telegram sendMessage failed with status {response.status_code}: "
        f"{error_detail}"
    )
