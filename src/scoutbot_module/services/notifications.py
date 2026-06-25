from __future__ import annotations

import logging
import os
from typing import Any

LOG = logging.getLogger("scoutbot.services.notifications")


def _resolve_recipients(
    settings: dict,
    db_path: str | None = None,
) -> tuple[list[str], list[str]]:
    chat_ids: set[str] = set()
    errors: list[str] = []

    telegram_cfg = settings["telegram"]
    chat_id_env = telegram_cfg["chat_id_env"]

    global_sink = os.environ.get(chat_id_env, "").strip()
    if global_sink:
        chat_ids.add(global_sink)

    if db_path:
        try:
            from pathlib import Path as PPath

            from scoutbot_module.db.repo import list_active_telegram_subscribers
            from scoutbot_module.db.session import create_db_engine, get_session

            engine = create_db_engine(PPath(db_path))
            session = get_session(engine)
            try:
                subscribers = list_active_telegram_subscribers(session)
                for sub in subscribers:
                    if sub.chat_id:
                        chat_ids.add(sub.chat_id)
            finally:
                session.close()
                engine.dispose()
        except Exception as exc:
            errors.append(f"subscriber_resolve_error: {exc}")

    return sorted(chat_ids), errors


def _build_alert_reply_markup(signal: dict[str, Any]) -> dict[str, Any] | None:
    signal_id = str(signal.get("signal_id") or "").strip()
    if not signal_id:
        return None
    return {
        "inline_keyboard": [
            [
                {
                    "text": "Mark as noise",
                    "callback_data": f"signal:noise:{signal_id}",
                }
            ]
        ]
    }


async def send_telegram_alert_async(
    settings: dict,
    signal: dict[str, Any],
    target_info: dict[str, Any] | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    telegram_cfg = settings["telegram"]
    token_env = telegram_cfg["token_env"]

    token = os.environ.get(token_env)

    if not token:
        LOG.warning("Telegram token not set; alert skipped")
        return {"sent": False, "reason": "token_missing"}

    chat_ids, resolve_errors = _resolve_recipients(settings, db_path)

    if not chat_ids:
        LOG.warning("No recipients resolved; alert skipped")
        return {
            "sent": False,
            "reason": "no_recipients",
            "resolve_errors": resolve_errors,
        }

    message = format_alert(signal, target_info)
    reply_markup = _build_alert_reply_markup(signal)
    sent_count = 0
    failed_count = 0
    skipped_count = 0

    for chat_id in chat_ids:
        try:
            await _send_telegram_message(token, chat_id, message, reply_markup)
            sent_count += 1
        except Exception:
            LOG.warning(
                "Telegram delivery failed: chat=%s signal=%s",
                chat_id,
                signal.get("signal_id"),
            )
            failed_count += 1

    LOG.info(
        "Telegram alert: signal=%s sent=%d failed=%d total=%d",
        signal.get("signal_id"),
        sent_count,
        failed_count,
        len(chat_ids),
    )

    return {
        "sent": sent_count > 0,
        "sent_count": sent_count,
        "failed_count": failed_count,
        "skipped_count": skipped_count,
        "recipients_total": len(chat_ids),
    }


def send_telegram_alert(
    settings: dict,
    signal: dict[str, Any],
    target_info: dict[str, Any] | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    import asyncio

    return asyncio.run(
        send_telegram_alert_async(settings, signal, target_info, db_path)
    )


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


async def _send_telegram_message(
    token: str,
    chat_id: str,
    text: str,
    reply_markup: dict[str, Any] | None = None,
) -> dict[str, Any]:
    import httpx

    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()
