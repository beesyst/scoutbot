from __future__ import annotations

import logging
import os

from scoutbot_module.core.paths import resolve_project_path

LOG = logging.getLogger("scoutbot.bot.app")


def run_telegram(settings: dict, argv: list[str]) -> int:
    del argv

    telegram_cfg = settings["telegram"]
    token_env = telegram_cfg["token_env"]
    admin_ids_env = telegram_cfg["admin_ids_env"]

    token = os.environ.get(token_env)
    if not token:
        LOG.error(
            "Telegram bot token not found in env. "
            "Set the token env variable in .env to start bot."
        )
        return 1

    admin_ids_raw = os.environ.get(admin_ids_env, "")
    admin_ids = _parse_admin_ids(admin_ids_raw)

    if not admin_ids:
        LOG.warning(
            "No admin IDs parsed from env. State-changing commands will be unavailable."
        )

    LOG.info("Starting Telegram bot (admins=%d)", len(admin_ids))

    db_path = resolve_project_path(settings["storage"]["db_path"])

    from scoutbot_module.bot.handlers import create_bot_app

    app = create_bot_app(
        token=token, admin_ids=admin_ids, settings=settings, db_path=db_path
    )

    LOG.info("Telegram bot polling started")
    app.run_polling()
    return 0


def _parse_admin_ids(raw: str) -> set[int]:
    ids: set[int] = set()
    for part in raw.replace(",", " ").split():
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError:
            LOG.warning("Invalid admin ID: %r", part)
    return ids
