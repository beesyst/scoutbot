from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Session

from scoutbot_module.core.paths import resolve_project_path
from scoutbot_module.db.migrations import run_migrations
from scoutbot_module.db.repo import export_workspace_to_yaml, import_seed_yaml
from scoutbot_module.db.session import create_db_engine, get_session

LOG = logging.getLogger("scoutbot.cli")


# Doctor: чек окружения, настроек, путей, SQLite и changedetection.io
def run_doctor(settings: dict, argv: list[str]) -> int:
    del argv
    logger = logging.getLogger("scoutbot.doctor")
    errors: list[str] = []
    warnings: list[str] = []

    logger.info("Python: %s", sys.version.split()[0])
    logger.info(
        "uv:    %s", os.popen("uv --version 2>/dev/null").read().strip() or "not found"
    )

    app_ = settings.get("app", {})
    logger.info("App:   %s env=%s", app_.get("name"), app_.get("env"))

    storage_cfg = settings.get("storage", {})
    storage_root = resolve_project_path(storage_cfg["root"])
    db_path = resolve_project_path(storage_cfg["db_path"])
    logger.info("DB:    %s", db_path)

    telegram_ = settings.get("telegram", {})
    telegram_env_labels = {
        "token_env": "telegram token env",
        "admin_ids_env": "telegram admin ids env",
        "chat_id_env": "telegram alert chat id env",
    }
    for key_name in ("token_env", "admin_ids_env", "chat_id_env"):
        env_key = telegram_.get(key_name, "")
        if env_key:
            val = os.environ.get(env_key)
            if val:
                logger.info("Telegram %s: set", key_name)
            else:
                warnings.append(f"{telegram_env_labels[key_name]} is not set")

    cd_ = settings.get("changedetection", {})
    cd_url = cd_["base_url"]
    logger.info("CD URL: %s", cd_url)

    cd_status = asyncio.run(_check_changedetection_status(settings))
    _write_changedetection_status(
        storage_root=storage_root,
        status=cd_status["status"],
        reason_code=cd_status["reason_code"],
        base_url=str(cd_url),
    )
    if cd_status["status"] == "ok":
        logger.info("changedetection.io reachable")
    else:
        warnings.append(cd_status["message"])

    discovery_ = settings.get("discovery", {})
    logger.info(
        "Discovery: enabled=%s target_links_max=%s",
        discovery_.get("enabled"),
        discovery_.get("target_links_max"),
    )

    ai_ = settings.get("ai", {})
    n8n_ = settings.get("integrations", {}).get("n8n", {})
    logger.info("AI:  enabled=%s", ai_.get("enabled", False))
    logger.info("n8n: enabled=%s", n8n_.get("enabled", False))

    if errors:
        for e in errors:
            logger.error("ERROR: %s", e)
        logger.error("Doctor: %d error(s), %d warning(s)", len(errors), len(warnings))
        return 1
    for w in warnings:
        logger.warning("WARNING: %s", w)
    logger.info("Doctor: ok (%d warning(s))", len(warnings))
    return 0


def _write_changedetection_status(
    storage_root: Path,
    status: str,
    reason_code: str,
    base_url: str,
) -> None:
    path = storage_root / "interfaces" / "changedetection_status.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": status,
        "reason_code": reason_code,
        "base_url": base_url,
        "checked_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


# Чек статуса changedetection.io и запись в артефакт JSON для doctor и sync
async def _check_changedetection_status(settings: dict) -> dict:
    cd_ = settings.get("changedetection", {})
    cd_key_env = cd_.get("api_key_env", "")
    cd_key = os.environ.get(cd_key_env) if cd_key_env else None

    if not cd_key:
        return {
            "status": "degraded",
            "reason_code": "api_key_missing",
            "message": "changedetection API key is not set in env; sync will be degraded",
        }

    from scoutbot_module.changedetection.client import CDClient

    cd_url = cd_["base_url"]
    timeout = cd_.get("timeout", 20)
    client = CDClient(base_url=cd_url, api_key=cd_key, timeout=timeout)
    try:
        result = await client.system_info()
        if result.ok:
            return {
                "status": "ok",
                "reason_code": "systeminfo_ok",
                "message": "",
            }
        return {
            "status": "degraded",
            "reason_code": "changedetection_unreachable",
            "message": f"changedetection.io unreachable: {result.error}",
        }
    finally:
        await client.close()


# Init DB: создание/чек схемы SQLite (идемпотентно)
def run_init_db(settings: dict, argv: list[str]) -> int:
    del argv
    logger = logging.getLogger("scoutbot.init_db")

    storage_cfg = settings.get("storage", {})
    db_path = resolve_project_path(storage_cfg["db_path"])

    db_path.parent.mkdir(parents=True, exist_ok=True)

    run_migrations(db_path)
    logger.info("Schema initialised: %s", db_path)
    return 0


# Import seed: загрузка целей из YAML в SQLite
def run_import_seed(settings: dict, argv: list[str]) -> int:
    logger = logging.getLogger("scoutbot.import_seed")

    if not argv:
        logger.error("Usage: import-seed <path-to-seed.yml>")
        return 1

    seed_path = resolve_project_path(argv[0])
    if not seed_path.exists():
        logger.error("Seed file not found: %s", seed_path)
        return 1

    storage_cfg = settings.get("storage", {})
    db_path = resolve_project_path(storage_cfg["db_path"])

    engine = create_db_engine(db_path)
    session = get_session(engine)

    try:
        count = import_seed_yaml(session, seed_path)
        logger.info("Imported %d targets from %s", count, seed_path)
        return 0
    except (ValueError, KeyError) as exc:
        logger.error("Import failed: %s", exc)
        return 1
    finally:
        session.close()
        engine.dispose()


# Импорт из seed YAML
def run_export_seed(settings: dict, argv: list[str]) -> int:
    logger = logging.getLogger("scoutbot.export_seed")

    if not argv:
        logger.error("Usage: export-seed <output-path.yml>")
        return 1

    output_path = resolve_project_path(argv[0])
    workspace_name = argv[1] if len(argv) > 1 else "NODERS"

    storage_cfg = settings.get("storage", {})
    db_path = resolve_project_path(storage_cfg["db_path"])

    engine = create_db_engine(db_path)
    session = get_session(engine)

    try:
        result = export_workspace_to_yaml(session, workspace_name, output_path)
        logger.info("Exported workspace %r to %s", workspace_name, result)
        return 0
    except ValueError as exc:
        logger.error("Export failed: %s", exc)
        return 1
    finally:
        session.close()
        engine.dispose()


# Результат синхронизации для основного артефакта
def run_sync(settings: dict, argv: list[str]) -> int:
    del argv
    logger = logging.getLogger("scoutbot.sync")

    storage_cfg = settings.get("storage", {})
    db_path = resolve_project_path(storage_cfg["db_path"])
    storage_root = resolve_project_path(storage_cfg["root"])

    engine = create_db_engine(db_path)
    session = get_session(engine)

    try:
        result = asyncio.run(run_sync_async(settings, session, storage_root))
        logger.info(
            "Sync %s: created=%d updated=%d failed=%d",
            result.status,
            result.summary["created"],
            result.summary["updated"],
            result.summary["failed"],
        )
        if result.errors:
            for err in result.errors:
                logger.warning("Sync error: %s", err)
        return 0 if result.status in ("ok", "partial", "degraded") else 1
    finally:
        session.close()
        engine.dispose()


# Async wrapper для sync flow
async def run_sync_async(settings: dict, session: Session, storage_root: Path):
    from scoutbot_module.changedetection.sync import run_sync

    return await run_sync(settings, session, storage_root)
