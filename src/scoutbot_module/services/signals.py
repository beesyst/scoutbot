from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlmodel import Session

from scoutbot_module.db.repo import (
    create_signal,
    find_signal_by_target_and_hash,
    write_audit_log,
)
from scoutbot_module.intelligence.dedupe import compute_diff_hash

LOG = logging.getLogger("scoutbot.services.signals")


def process_webhook_event(
    session: Session,
    target_id: str | None,
    watch_id: str | None,
    cd_uuid: str | None,
    payload: dict[str, Any],
    storage_root: str,
    settings: dict,
) -> dict[str, Any]:
    diff_hash = compute_diff_hash(payload)
    signals_cfg = settings["signals"]
    body_excerpt_chars = signals_cfg["body_excerpt_chars"]

    if target_id and diff_hash:
        existing = find_signal_by_target_and_hash(session, target_id, diff_hash)
        if existing:
            if existing.category == "noise":
                LOG.info(
                    "Noise signal suppressed: target=%s hash=%s", target_id, diff_hash
                )
                return {"deduped": True, "signal_id": existing.signal_id, "suppressed": True}
            LOG.info(
                "Duplicate signal suppressed: target=%s hash=%s", target_id, diff_hash
            )
            return {"deduped": True, "signal_id": existing.signal_id}

    from scoutbot_module.intelligence.classify import classify_signal

    priority_config = signals_cfg.get("priority")
    noise_cfg = signals_cfg.get("noise", {})
    noise_ignore_text = list(noise_cfg.get("ignore_text", []))

    if target_id:
        from sqlmodel import select

        from scoutbot_module.db.models import Target

        tgt = session.exec(
            select(Target).where(Target.target_id == target_id)
        ).first()
        if tgt and tgt.ignore_text_json:
            import json

            try:
                extra_ignores = json.loads(tgt.ignore_text_json)
                if isinstance(extra_ignores, list):
                    noise_ignore_text.extend(extra_ignores)
            except (json.JSONDecodeError, TypeError):
                pass

    classification = classify_signal(
        payload,
        categories=signals_cfg["categories"],
        priority_config=priority_config,
        noise_ignore_text=noise_ignore_text,
    )

    sig = create_signal(
        session=session,
        target_id=target_id,
        watch_id=watch_id,
        changedetection_uuid=cd_uuid,
        category=classification.get("category", "unknown"),
        priority=classification.get("priority", "low"),
        diff_hash=diff_hash,
        title=payload.get("title") or classification.get("title", "Change detected"),
        summary=_build_summary(payload),
        raw_excerpt=_safe_excerpt(payload, limit=body_excerpt_chars),
        url=payload.get("url"),
    )

    write_audit_log(
        session,
        action="webhook_signal",
        entity_type="signal",
        entity_id=sig.signal_id,
        payload={"category": sig.category, "priority": sig.priority},
    )

    _write_webhook_artifacts(storage_root, sig.signal_id, payload, classification)

    _append_signal_jsonl(storage_root, sig, classification, payload)

    LOG.info(
        "Signal created: id=%s target=%s category=%s priority=%s",
        sig.signal_id,
        target_id,
        sig.category,
        sig.priority,
    )

    return {
        "deduped": False,
        "signal_id": sig.signal_id,
        "category": sig.category,
        "priority": sig.priority,
        "diff_hash": diff_hash,
        "title": sig.title,
        "summary": sig.summary,
        "url": sig.url,
    }


def _build_summary(payload: dict[str, Any]) -> str | None:
    text = payload.get("text") or payload.get("diff") or payload.get("summary", "")
    if not text or not isinstance(text, str):
        return None
    return text[:500]


def _safe_excerpt(payload: dict[str, Any], limit: int) -> str | None:
    text = payload.get("text") or payload.get("diff") or ""
    if not text or not isinstance(text, str):
        return None
    return text[:limit]


def _write_webhook_artifacts(
    storage_root: str,
    signal_id: str,
    payload: dict[str, Any],
    classification: dict[str, Any],
) -> None:
    run_id = f"run_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
    run_dir = Path(storage_root) / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    event_path = run_dir / "webhook_event.json"
    safe_payload = _redact_secrets(payload)
    with event_path.open("w", encoding="utf-8") as f:
        json.dump(safe_payload, f, indent=2, ensure_ascii=False)

    class_path = run_dir / "signal_classification.json"
    with class_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "signal_id": signal_id,
                "category": classification.get("category"),
                "priority": classification.get("priority"),
                "matched_keywords": classification.get("matched_keywords", []),
                "reason_code": classification.get("reason_code", "unknown"),
            },
            f,
            indent=2,
            ensure_ascii=False,
        )


def _append_signal_jsonl(
    storage_root: str,
    sig: Any,
    classification: dict[str, Any],
    payload: dict[str, Any],
) -> None:
    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    signals_dir = Path(storage_root) / "signals"
    signals_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = signals_dir / f"{date_str}.jsonl"

    entry = {
        "signal_id": sig.signal_id,
        "target_id": sig.target_id,
        "category": sig.category,
        "priority": sig.priority,
        "diff_hash": sig.diff_hash,
        "detected_at": sig.detected_at.isoformat() if sig.detected_at else None,
        "title": sig.title,
        "summary": sig.summary,
        "url": sig.url,
    }
    with jsonl_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _redact_secrets(payload: dict[str, Any]) -> dict[str, Any]:
    return _redact_value(payload)


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if _is_secret_key(key):
                continue
            result[key] = _redact_value(item)
        return result
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    return value


def _is_secret_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    if normalized in {
        "secret",
        "api_key",
        "token",
        "access_token",
        "refresh_token",
        "authorization",
        "proxy_authorization",
        "cookie",
        "set_cookie",
        "x_api_key",
    }:
        return True
    return normalized.endswith("_token") or normalized.endswith("_secret")
