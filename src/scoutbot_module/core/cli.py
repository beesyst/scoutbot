from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Session, col

from scoutbot_module.core.paths import ROOT_DIR, resolve_project_path
from scoutbot_module.db.migrations import run_migrations
from scoutbot_module.db.repo import export_workspace_to_yaml, import_seed_yaml
from scoutbot_module.db.session import create_db_engine, get_session

LOG = logging.getLogger("scoutbot.cli")


def run_doctor(settings: dict, argv: list[str]) -> int:
    del argv
    logger = logging.getLogger("scoutbot.doctor")
    errors: list[str] = []
    warnings: list[str] = []

    logger.info("Python: %s", sys.version.split()[0])
    logger.info(
        "uv:    %s", os.popen("uv --version 2>/dev/null").read().strip() or "not found"
    )

    app_ = settings["app"]
    logger.info("App:   %s env=%s", app_["name"], app_["env"])

    storage_root = resolve_project_path(settings["storage"]["root"])
    db_path = resolve_project_path(settings["storage"]["db_path"])
    logger.info("DB:    %s", db_path)

    telegram_ = settings["telegram"]
    telegram_env_labels = {
        "token_env": "telegram token env",
        "admin_ids_env": "telegram admin ids env",
        "allowed_user_ids_env": "telegram allowed user ids env",
        "chat_id_env": "telegram alert chat id env",
    }
    for key_name in (
        "token_env",
        "admin_ids_env",
        "allowed_user_ids_env",
        "chat_id_env",
    ):
        env_key = telegram_[key_name]
        val = os.environ.get(env_key)
        if val:
            logger.info("Telegram %s: set", key_name)
        else:
            warnings.append(f"{telegram_env_labels[key_name]} is not set")

    cd_ = settings["changedetection"]
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

    discovery_ = settings["discovery"]
    logger.info(
        "Discovery: enabled=%s target_links_max=%s",
        discovery_["enabled"],
        discovery_["target_links_max"],
    )

    logger.info("AI:  enabled=%s", settings["ai"]["enabled"])
    logger.info("n8n: enabled=%s", settings["integrations"]["n8n"]["enabled"])

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


async def _check_changedetection_status(settings: dict) -> dict:
    cd_ = settings["changedetection"]
    cd_key_env = cd_["api_key_env"]
    cd_key = os.environ.get(cd_key_env)

    if not cd_key:
        return {
            "status": "degraded",
            "reason_code": "api_key_missing",
            "message": "changedetection API key is not set in env; sync will be degraded",
        }

    from scoutbot_module.changedetection.client import CDClient

    cd_url = cd_["base_url"]
    timeout = cd_["timeout"]
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


def run_init_db(settings: dict, argv: list[str]) -> int:
    del argv
    logger = logging.getLogger("scoutbot.init_db")

    db_path = resolve_project_path(settings["storage"]["db_path"])

    db_path.parent.mkdir(parents=True, exist_ok=True)

    run_migrations(db_path)
    logger.info("Schema initialised: %s", db_path)
    return 0


def run_import_seed(settings: dict, argv: list[str]) -> int:
    logger = logging.getLogger("scoutbot.import_seed")

    if not argv:
        logger.error("Usage: import-seed <path-to-seed.yml>")
        return 1

    seed_path = resolve_project_path(argv[0])
    if not seed_path.exists():
        logger.error("Seed file not found: %s", seed_path)
        return 1

    db_path = resolve_project_path(settings["storage"]["db_path"])

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


def run_export_seed(settings: dict, argv: list[str]) -> int:
    logger = logging.getLogger("scoutbot.export_seed")

    if not argv:
        logger.error("Usage: export-seed <output-path.yml>")
        return 1

    output_path = resolve_project_path(argv[0])
    workspace_name = argv[1] if len(argv) > 1 else settings["workspace"]["default_name"]

    db_path = resolve_project_path(settings["storage"]["db_path"])

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


def run_sync(settings: dict, argv: list[str]) -> int:
    del argv
    logger = logging.getLogger("scoutbot.sync")

    db_path = resolve_project_path(settings["storage"]["db_path"])
    storage_root = resolve_project_path(settings["storage"]["root"])

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


async def run_sync_async(settings: dict, session: Session, storage_root: Path):
    from scoutbot_module.changedetection.sync import run_sync

    return await run_sync(settings, session, storage_root)


def run_digest(settings: dict, argv: list[str]) -> int:
    logger = logging.getLogger("scoutbot.digest")

    date_str: str | None = None
    if argv:
        date_str = argv[0].strip()

    db_path = resolve_project_path(settings["storage"]["db_path"])
    storage_root = resolve_project_path(settings["storage"]["root"])

    engine = create_db_engine(db_path)
    session = get_session(engine)
    try:
        result = asyncio.run(
            _run_digest_async(settings, session, storage_root, date_str, str(db_path))
        )
        logger.info(
            "Digest: groups=%d sent=%d failed=%d",
            len(result.get("groups", [])),
            result.get("delivery", {}).get("sent_count", 0),
            result.get("delivery", {}).get("failed_count", 0),
        )
        return 0
    finally:
        session.close()
        engine.dispose()


async def _run_digest_async(
    settings: dict,
    session: Session,
    storage_root: Path,
    date_str: str | None = None,
    db_path_str: str | None = None,
) -> dict:
    from datetime import UTC, datetime, timedelta

    from sqlmodel import select

    from scoutbot_module.db.models import Project, Signal, Target

    if date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            target_date = datetime.now(UTC).date()
            if isinstance(target_date, datetime):
                target_date = target_date.date()
    else:
        target_date = datetime.now(UTC).date()

    day_start = datetime.combine(target_date, datetime.min.time(), tzinfo=UTC)
    day_end = day_start + timedelta(days=1)

    stmt = (
        select(Signal)
        .where(col(Signal.detected_at) >= day_start)
        .where(col(Signal.detected_at) < day_end)
        .order_by(col(Signal.detected_at))
    )
    signals = session.exec(stmt).all()

    groups: list[dict] = []
    groups_key: dict[tuple, dict] = {}

    for sig in signals:
        target_id = sig.target_id
        project_name = "Unknown"
        if target_id:
            tgt = session.exec(
                select(Target).where(Target.target_id == target_id)
            ).first()
            if tgt and tgt.project_id:
                proj = session.exec(
                    select(Project).where(Project.project_id == tgt.project_id)
                ).first()
                if proj:
                    project_name = proj.name

        category = sig.category or "unknown"
        priority = sig.priority or "low"
        key = (project_name, category, priority)

        signal_entry = {
            "signal_id": sig.signal_id,
            "title": sig.title or "Change detected",
            "url": sig.url or "",
        }

        if key in groups_key:
            groups_key[key]["signals"].append(signal_entry)
        else:
            entry = {
                "project": project_name,
                "category": category,
                "priority": priority,
                "signals": [signal_entry],
            }
            groups_key[key] = entry
            groups.append(entry)

    run_id = f"run_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
    digest_path = storage_root / "runs" / run_id / "digest.json"
    digest_path.parent.mkdir(parents=True, exist_ok=True)

    delivery_result = {"sent_count": 0, "failed_count": 0, "skipped_count": 0}

    if groups:
        from scoutbot_module.services.notifications import (
            send_telegram_alert_async,
        )

        summary_lines = [
            f"ScoutBot digest — {target_date.isoformat()}",
            "",
        ]
        for g in groups:
            summary_lines.append(
                f"{g['project']} / {g['category']} [{g['priority']}]: {len(g['signals'])} signal(s)"
            )

        summary_text = "\n".join(summary_lines)

        delivery_result = await send_telegram_alert_async(
            settings=settings,
            signal={
                "signal_id": f"digest_{run_id}",
                "category": "digest",
                "priority": "medium",
                "title": f"Daily digest {target_date.isoformat()}",
                "summary": summary_text,
                "url": "",
            },
            target_info=None,
            db_path=db_path_str,
        )

    payload = {
        "run_id": run_id,
        "date": target_date.isoformat(),
        "groups": groups,
        "delivery": delivery_result,
    }

    with digest_path.open("w", encoding="utf-8") as f:
        import json

        json.dump(payload, f, indent=2, ensure_ascii=False)

    LOG.info(
        "Digest written: %s (groups=%d sent=%d failed=%d)",
        digest_path,
        len(groups),
        delivery_result.get("sent_count", 0),
        delivery_result.get("failed_count", 0),
    )

    return payload


def run_backup(settings: dict, argv: list[str]) -> int:
    del argv
    logger = logging.getLogger("scoutbot.backup")

    db_path = resolve_project_path(settings["storage"]["db_path"])
    storage_root = resolve_project_path(settings["storage"]["root"])

    if not db_path.exists():
        logger.error("Database file not found: %s", db_path)
        return 1

    backup_id = f"backup_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
    backup_dir = storage_root / "backups" / backup_id
    backup_dir.mkdir(parents=True, exist_ok=True)

    backup_db_path = backup_dir / "scoutbot.sqlite3"
    with sqlite3.connect(db_path) as source:
        with sqlite3.connect(backup_db_path) as destination:
            source.backup(destination)

    db_size = db_path.stat().st_size
    manifest = {
        "backup_id": backup_id,
        "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "source_db_path": _storage_contract_path(storage_root, db_path),
        "backup_db_path": _storage_contract_path(storage_root, backup_db_path),
        "db_size_bytes": db_size,
        "workspace": settings.get("workspace", {}).get("default_name", "unknown"),
    }

    manifest_path = backup_dir / "manifest.json"
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    logger.info(
        "Backup created: %s (size=%d bytes)",
        backup_id,
        db_size,
    )
    return 0


def run_audit(settings: dict, argv: list[str]) -> int:
    logger = logging.getLogger("scoutbot.audit")

    limit = 50
    if argv:
        try:
            limit = int(argv[0].strip())
            if limit <= 0:
                raise ValueError
        except ValueError, IndexError:
            logger.warning("Invalid limit, using default 50")
            limit = 50

    db_path = resolve_project_path(settings["storage"]["db_path"])
    storage_root = resolve_project_path(settings["storage"]["root"])

    if not db_path.exists():
        logger.error("Database file not found: %s", db_path)
        return 1

    engine = create_db_engine(db_path)
    session = get_session(engine)

    try:
        from sqlmodel import select

        from scoutbot_module.db.models import (
            AuditLog,
            Signal,
            Target,
        )

        audit_stmt = (
            select(AuditLog).order_by(col(AuditLog.created_at).desc()).limit(limit)
        )
        recent_actions = session.exec(audit_stmt).all()

        target_stmt = (
            select(Target).order_by(col(Target.updated_at).desc()).limit(limit)
        )
        target_changes = session.exec(target_stmt).all()

        signals = session.exec(
            select(Signal).order_by(col(Signal.detected_at).desc()).limit(limit)
        ).all()

        webhook_events: dict = {
            "signals_total": 0,
            "by_category": {},
            "by_priority": {},
        }
        for sig in signals:
            cat = sig.category or "unknown"
            pri = sig.priority or "unknown"
            webhook_events["signals_total"] += 1
            webhook_events["by_category"][cat] = (
                webhook_events["by_category"].get(cat, 0) + 1
            )
            webhook_events["by_priority"][pri] = (
                webhook_events["by_priority"].get(pri, 0) + 1
            )

        sync_path = storage_root / "interfaces" / "sync_result.json"
        sync_results: list[dict] = []
        if sync_path.exists():
            try:
                sync_data = json.loads(sync_path.read_text(encoding="utf-8"))
                sync_results.append(sync_data)
            except json.JSONDecodeError, OSError:
                pass

        run_id = f"run_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
        summary = {
            "run_id": run_id,
            "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "limit": limit,
            "recent_actions": [
                {
                    "audit_id": a.audit_id,
                    "action": a.action,
                    "entity_type": a.entity_type,
                    "entity_id": a.entity_id,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
                for a in recent_actions
            ],
            "target_changes": [
                {
                    "target_id": t.target_id,
                    "title": t.title,
                    "url": t.url,
                    "kind": t.kind,
                    "status": t.status,
                    "updated_at": t.updated_at.isoformat() if t.updated_at else None,
                }
                for t in target_changes
            ],
            "sync_results": sync_results,
            "webhook_events": webhook_events,
        }

        audit_dir = storage_root / "runs" / run_id
        audit_dir.mkdir(parents=True, exist_ok=True)
        audit_path = audit_dir / "audit_summary.json"
        with audit_path.open("w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        logger.info(
            "Audit summary: actions=%d targets=%d signals=%d",
            len(recent_actions),
            len(target_changes),
            len(signals),
        )
        logger.info("Audit summary written: %s", audit_path)

        print("ScoutBot audit summary")
        print(f"recent_actions={len(recent_actions)}")
        print(f"target_changes={len(target_changes)}")
        print(f"sync_results={len(sync_results)}")
        print(f"signals_total={webhook_events['signals_total']}")
        print(f"by_category={webhook_events['by_category']}")
        print(f"by_priority={webhook_events['by_priority']}")
        print(f"audit_artifact={_display_path(audit_path)}")

        return 0
    finally:
        session.close()
        engine.dispose()


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT_DIR))
    except ValueError:
        return str(path)


def _storage_contract_path(storage_root: Path, path: Path) -> str:
    try:
        return str(
            Path(storage_root.name) / path.resolve().relative_to(storage_root.resolve())
        )
    except ValueError:
        return _display_path(path)
