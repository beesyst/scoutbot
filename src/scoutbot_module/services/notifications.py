from __future__ import annotations

import logging
import os
from typing import Any

import httpx

LOG = logging.getLogger("scoutbot.services.notifications")


async def send_telegram_alert_async(
    settings: dict,
    signal: dict[str, Any],
    target_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    telegram_cfg = settings["telegram"]
    token_env = telegram_cfg["token_env"]
    chat_id_env = telegram_cfg["chat_id_env"]

    token = os.environ.get(token_env)
    chat_id = os.environ.get(chat_id_env)

    if not token:
        LOG.warning("Telegram token not set; alert skipped")
        return {"sent": False, "reason": "token_missing"}

    if not chat_id:
        LOG.warning("Telegram alert chat ID not set; alert skipped")
        return {"sent": False, "reason": "chat_id_missing"}

    message = format_alert(signal, target_info)

    try:
        result = await _send_telegram_message(token, chat_id, message)
        LOG.info("Telegram alert sent: signal=%s", signal.get("signal_id"))
        return {"sent": True, "message_id": result.get("message_id")}
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        LOG.warning(
            "Telegram alert HTTP error: signal=%s status_code=%s",
            signal.get("signal_id"),
            status_code,
        )
        return {
            "sent": False,
            "reason": "telegram_http_error",
            "status_code": status_code,
        }
    except httpx.RequestError:
        LOG.warning(
            "Telegram alert network error: signal=%s",
            signal.get("signal_id"),
        )
        return {"sent": False, "reason": "telegram_network_error"}
    except Exception:
        LOG.error("Telegram alert failed: signal=%s", signal.get("signal_id"))
        return {"sent": False, "reason": "telegram_send_failed"}


def send_telegram_alert(
    settings: dict,
    signal: dict[str, Any],
    target_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    import asyncio

    return asyncio.run(send_telegram_alert_async(settings, signal, target_info))


def format_alert(
    signal: dict[str, Any],
    target_info: dict[str, Any] | None = None,
) -> str:
    project = (target_info or {}).get("project_name", "Unknown")
    target_title = (target_info or {}).get("title", signal.get("url", "Unknown"))
    category = str(signal.get("category") or "unknown")
    priority = str(signal.get("priority") or "low")
    url = str(signal.get("url") or "")
    summary = str(signal.get("summary") or "No summary available")

    lines = [
        "ScoutBot alert",
        "",
        f"Project: {project}",
        f"Target: {target_title}",
        f"Category: {category}",
        f"Priority: {priority}",
    ]
    if url:
        lines.append(f"URL: {url}")
    lines.append("")
    lines.append("Summary:")
    lines.append(summary)

    return "\n".join(lines)


async def _send_telegram_message(token: str, chat_id: str, text: str) -> dict[str, Any]:
    import httpx

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            url,
            json={
                "chat_id": chat_id,
                "text": text,
            },
        )
        resp.raise_for_status()
        return resp.json()
