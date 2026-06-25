from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlmodel import Session

from scoutbot_module.changedetection.client import CDClient
from scoutbot_module.changedetection.payloads import build_watch_payload
from scoutbot_module.db.models import Target, Watch
from scoutbot_module.db.repo import (
    get_or_create_watch,
    get_watch_by_target_id,
    list_targets_by_status,
    mark_watch_failed,
    mark_watch_removed_or_inactive,
    update_watch_uuid,
    write_audit_log,
)

LOG = logging.getLogger("scoutbot.changedetection.sync")


def _make_run_id() -> str:
    return f"run_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"


def _write_json_artifact(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


class SyncResult:
    def __init__(self) -> None:
        self.run_id: str = _make_run_id()
        self.status: str = "ok"
        self.reason_code: str | None = None
        self.summary: dict[str, int] = {
            "total": 0,
            "created": 0,
            "updated": 0,
            "failed": 0,
            "skipped": 0,
        }
        self.errors: list[str] = []
        self.timestamp: str = datetime.now(UTC).isoformat()

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "reason_code": self.reason_code,
            "summary": self.summary,
            "errors": self.errors,
            "timestamp": self.timestamp,
        }


async def run_sync(
    settings: dict,
    db_session: Session,
    storage_root: Path,
) -> SyncResult:
    result = SyncResult()

    cd_cfg = settings["changedetection"]
    base_url: str = cd_cfg["base_url"]
    api_key_env: str = cd_cfg["api_key_env"]
    webhook_url_env: str = cd_cfg["webhook_url_env"]
    webhook_secret_env: str = cd_cfg["webhook_secret_env"]
    timeout: int = cd_cfg["timeout"]
    interval = cd_cfg["interval"]
    interval_hours: int = interval["hours"]
    fetch_backend: str = cd_cfg["fetch_backend"]

    targets = list_targets_by_status(
        db_session, ("active", "queued", "paused", "deleted")
    )
    result.summary["total"] = len(targets)

    api_key: str | None = os.environ.get(api_key_env)
    if not api_key:
        result.status = "degraded"
        result.reason_code = "api_key_missing"
        result.errors.append("changedetection API key missing")
        _write_artifact(result, storage_root)
        _write_detail_artifact(
            result,
            storage_root,
            targets,
            notification_configured=False,
        )
        _write_sync_audit_log(db_session, result)
        return result

    webhook_url = os.environ.get(webhook_url_env, "").strip()
    if not webhook_url:
        result.status = "degraded"
        result.reason_code = "webhook_url_missing"
        result.errors.append("changedetection webhook URL missing")
        _write_artifact(result, storage_root)
        _write_detail_artifact(
            result,
            storage_root,
            targets,
            notification_configured=False,
        )
        _write_sync_audit_log(db_session, result)
        return result

    webhook_secret = os.environ.get(webhook_secret_env, "").strip()
    if not webhook_secret:
        result.status = "degraded"
        result.reason_code = "webhook_secret_missing"
        result.errors.append("changedetection webhook secret missing")
        _write_artifact(result, storage_root)
        _write_detail_artifact(
            result,
            storage_root,
            targets,
            notification_configured=False,
            notification_url=webhook_url,
        )
        _write_sync_audit_log(db_session, result)
        return result

    try:
        authenticated_webhook_url = _build_authenticated_webhook_url(
            webhook_url,
            webhook_secret,
        )
    except ValueError:
        result.status = "degraded"
        result.reason_code = "webhook_url_invalid"
        result.errors.append("changedetection webhook URL invalid")
        _write_artifact(result, storage_root)
        _write_detail_artifact(
            result,
            storage_root,
            targets,
            notification_configured=False,
            notification_url=webhook_url,
        )
        _write_sync_audit_log(db_session, result)
        return result

    client = CDClient(
        base_url=base_url,
        api_key=api_key,
        timeout=timeout,
    )

    health_result = await client.system_info()
    if not health_result.ok:
        result.status = "degraded"
        result.reason_code = "changedetection_unreachable"
        result.errors.append(f"changedetection.io unreachable: {health_result.error}")
        _write_artifact(result, storage_root)
        _write_detail_artifact(
            result,
            storage_root,
            targets,
            notification_configured=True,
            notification_url=authenticated_webhook_url,
        )
        _write_sync_audit_log(db_session, result)
        await client.close()
        return result

    LOG.info("changedetection.io reachable — starting sync")

    for tgt in targets:
        try:
            if tgt.status in ("paused", "deleted"):
                watch = get_watch_by_target_id(db_session, tgt.target_id)
                if watch is None or not watch.changedetection_uuid:
                    result.summary["skipped"] += 1
                    continue

                deleted = await client.delete_watch(watch.changedetection_uuid)
                if deleted.ok:
                    mark_watch_removed_or_inactive(db_session, watch, tgt.status)
                    result.summary["updated"] += 1
                else:
                    result.summary["failed"] += 1
                    _handle_failure(
                        db_session,
                        watch,
                        result,
                        deleted.error or "unknown changedetection error",
                    )
                continue

            watch = get_or_create_watch(db_session, tgt.target_id)

            interval_sec = interval_hours * 3600

            ignore_text_list: list[str] = []
            if tgt.ignore_text_json:
                try:
                    parsed = json.loads(tgt.ignore_text_json)
                    if isinstance(parsed, list):
                        ignore_text_list = [
                            str(i) for i in parsed if isinstance(i, str) and i.strip()
                        ]
                except json.JSONDecodeError, TypeError:
                    pass

            payload = build_watch_payload(
                url=tgt.url,
                title=tgt.title,
                interval_seconds=interval_sec,
                fetch_backend=tgt.fetch_backend or fetch_backend,
                notification_urls=[authenticated_webhook_url],
                ignore_text=ignore_text_list or None,
            )

            if watch.changedetection_uuid:
                upd = await client.update_watch(watch.changedetection_uuid, payload)
                if upd.ok:
                    result.summary["updated"] += 1
                else:
                    result.summary["failed"] += 1
                    _handle_failure(
                        db_session,
                        watch,
                        result,
                        upd.error or "unknown changedetection error",
                    )
            else:
                created = await client.create_watch(payload)
                if created.ok:
                    cd_uuid = _extract_uuid(created.data)
                    if cd_uuid:
                        update_watch_uuid(db_session, watch, cd_uuid)
                        result.summary["created"] += 1
                    else:
                        result.summary["failed"] += 1
                        mark_watch_failed(
                            db_session, watch, "No UUID in create response"
                        )
                        result.errors.append(
                            f"No UUID in create response for target {tgt.target_id}"
                        )
                else:
                    result.summary["failed"] += 1
                    _handle_failure(
                        db_session,
                        watch,
                        result,
                        created.error or "unknown changedetection error",
                    )
        except Exception as exc:
            LOG.exception("Sync error for target %s", tgt.target_id)
            result.summary["failed"] += 1
            result.errors.append(f"target {tgt.target_id}: {exc}")

    if result.summary["failed"] > 0 and result.summary["created"] == 0:
        result.status = "failed"
    elif result.summary["failed"] > 0:
        result.status = "partial"

    _write_artifact(result, storage_root)
    _write_detail_artifact(
        result,
        storage_root,
        targets,
        notification_configured=True,
        notification_url=authenticated_webhook_url,
    )
    _write_sync_audit_log(db_session, result)

    await client.close()
    return result


def _extract_uuid(data: Any) -> str | None:
    if isinstance(data, dict):
        uuid = data.get("uuid") or (data.get("watch") or {}).get("uuid")
        if uuid:
            return str(uuid)
        return None
    if isinstance(data, str):
        return data if data.strip() else None
    if isinstance(data, list) and data:
        return _extract_uuid(data[0])
    return None


def _handle_failure(
    db_session: Session,
    watch: Watch,
    result: SyncResult,
    error: str,
) -> None:
    mark_watch_failed(db_session, watch, error)
    result.errors.append(f"watch {watch.watch_id}: {error}")


def _write_artifact(result: SyncResult, storage_root: Path) -> None:
    path = storage_root / "interfaces" / "sync_result.json"
    _write_json_artifact(path, result.to_dict())
    LOG.info("Sync result written: %s", path)


def _write_detail_artifact(
    result: SyncResult,
    storage_root: Path,
    targets: list[Target],
    notification_configured: bool,
    notification_url: str | None = None,
) -> None:
    run_dir = storage_root / "runs" / result.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    detail = {
        "run_id": result.run_id,
        "notification_configured": notification_configured,
        "notification_url": _redact_url(notification_url),
        "targets": [
            {
                "target_id": t.target_id,
                "title": t.title,
                "url": t.url,
                "kind": t.kind,
                "status": t.status,
            }
            for t in targets
        ],
    }
    path = run_dir / "target_sync.json"
    _write_json_artifact(path, detail)


def _redact_url(url: str | None) -> str | None:
    if not url:
        return None
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _build_authenticated_webhook_url(base_url: str, secret: str) -> str:
    parts = urlsplit(base_url)
    if parts.scheme not in ("http", "https", "json") or not parts.netloc:
        raise ValueError("invalid_webhook_url")
    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key != "secret"
    ]
    query_pairs.append(("secret", secret))
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query_pairs, doseq=True),
            parts.fragment,
        )
    )


def _write_sync_audit_log(db_session: Session, result: SyncResult) -> None:
    write_audit_log(
        db_session,
        action="sync_changedetection",
        entity_type="sync",
        entity_id=result.run_id,
        payload={
            "status": result.status,
            "reason_code": result.reason_code,
            "summary": result.summary,
        },
    )
