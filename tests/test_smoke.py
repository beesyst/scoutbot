from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from sqlalchemy import inspect as sa_inspect
from sqlmodel import select

from scoutbot_module.core.settings import load_settings


def _load_test_settings() -> dict:
    config_path = Path(__file__).resolve().parent.parent / "config" / "settings.yml"
    return load_settings(config_path)


def test_routes_command_works() -> None:
    settings = _load_test_settings()
    assert settings is not None
    assert settings["run"]["mode"] in (
        "routes",
        "doctor",
        "init-db",
        "telegram",
        "webhook",
        "backup",
        "audit",
    )


def test_routes_includes_telegram_and_webhook() -> None:
    settings = _load_test_settings()
    assert "telegram" in settings
    assert "webhook" in settings
    assert "workspace" in settings
    assert settings["workspace"]["default_name"]


def test_telegram_boot_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    from scoutbot_module.bot.app import run_telegram

    settings = _load_test_settings()
    token_env = settings["telegram"]["token_env"]
    monkeypatch.delenv(token_env, raising=False)

    exit_code = run_telegram(settings, [])
    assert exit_code == 1


def test_admin_ids_parsing() -> None:
    from scoutbot_module.bot.app import _parse_ids

    assert _parse_ids("123 456") == {123, 456}
    assert _parse_ids("123,456,789") == {123, 456, 789}
    assert _parse_ids("") == set()
    assert _parse_ids("abc") == set()
    assert _parse_ids("123 abc 456") == {123, 456}


def test_webhook_boot_resolves(monkeypatch: pytest.MonkeyPatch) -> None:

    settings = _load_test_settings()
    secret_env = settings["changedetection"]["webhook_secret_env"]
    monkeypatch.setenv(secret_env, "test-secret")

    settings["webhook"]["port"] = 0
    import uvicorn

    assert uvicorn is not None


@pytest.mark.slow
def test_doctor_command_returns_non_crashing_status() -> None:
    from scoutbot_module.core.cli import run_doctor

    settings = _load_test_settings()
    exit_code = run_doctor(settings, [])
    assert exit_code in (0, 1)


def test_doctor_writes_changedetection_status_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scoutbot_module.core.cli import run_doctor

    settings = _load_test_settings()
    settings["storage"]["root"] = str(tmp_path / "storage")
    settings["storage"]["db_path"] = str(
        tmp_path / "storage" / "db" / "scoutbot.sqlite3"
    )
    monkeypatch.delenv(settings["changedetection"]["api_key_env"], raising=False)

    assert run_doctor(settings, []) == 0

    path = tmp_path / "storage" / "interfaces" / "changedetection_status.json"
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["status"] == "degraded"
    assert data["reason_code"] == "api_key_missing"
    assert data["base_url"] == settings["changedetection"]["base_url"]


def test_doctor_missing_env_logs_do_not_include_literal_telegram_env_names(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from scoutbot_module.core.cli import run_doctor

    settings = _load_test_settings()
    settings["storage"]["root"] = str(tmp_path / "storage")
    settings["storage"]["db_path"] = str(
        tmp_path / "storage" / "db" / "scoutbot.sqlite3"
    )
    for env_name in settings["telegram"].values():
        monkeypatch.delenv(env_name, raising=False)
    monkeypatch.delenv(settings["changedetection"]["api_key_env"], raising=False)

    caplog.set_level(logging.WARNING)
    assert run_doctor(settings, []) == 0

    captured = caplog.text
    assert "telegram token env is not set" in captured
    assert "telegram admin ids env is not set" in captured
    assert "telegram alert chat id env is not set" in captured
    assert "TELEGRAM_BOT_TOKEN" not in captured
    assert "TELEGRAM_ADMIN_IDS" not in captured
    assert "TELEGRAM_ALERT_CHAT_ID" not in captured


def test_init_db_is_idempotent(tmp_path: Path) -> None:
    from sqlmodel import create_engine

    from scoutbot_module.db.session import init_schema

    engine = create_engine("sqlite://", echo=False)
    init_schema(engine)
    init_schema(engine)

    inspector = sa_inspect(engine)
    tables = inspector.get_table_names()
    assert len(tables) > 0
    assert "workspaces" in tables


def test_init_db_creates_db_file(tmp_path: Path) -> None:
    from scoutbot_module.db.migrations import run_migrations

    db_path = tmp_path / "test.db"
    run_migrations(db_path)
    assert db_path.exists()
    assert db_path.stat().st_size > 0


def test_resolve_project_path_relative_storage_db_path() -> None:
    from scoutbot_module.core.paths import ROOT_DIR, resolve_project_path

    resolved = resolve_project_path("storage/db/scoutbot.sqlite3")
    assert resolved == ROOT_DIR / "storage" / "db" / "scoutbot.sqlite3"
    assert ROOT_DIR in resolved.parents


def test_resolve_project_path_absolute_path_is_unchanged(tmp_path: Path) -> None:
    from scoutbot_module.core.paths import resolve_project_path

    absolute_path = tmp_path / "scoutbot.sqlite3"
    assert resolve_project_path(absolute_path) == absolute_path


def test_sync_missing_api_key_reports_sqlite_targets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scoutbot_module.core.cli import run_sync
    from scoutbot_module.db.migrations import run_migrations
    from scoutbot_module.db.models import AuditLog
    from scoutbot_module.db.repo import (
        create_target,
        get_or_create_project,
        get_or_create_workspace,
    )
    from scoutbot_module.db.session import create_db_engine, get_session

    settings = _load_test_settings()
    settings["storage"]["root"] = str(tmp_path / "storage")
    settings["storage"]["db_path"] = str(
        tmp_path / "storage" / "db" / "scoutbot.sqlite3"
    )
    monkeypatch.delenv(settings["changedetection"]["api_key_env"], raising=False)

    db_path = Path(settings["storage"]["db_path"])
    db_path.parent.mkdir(parents=True, exist_ok=True)
    run_migrations(db_path)
    engine = create_db_engine(db_path)
    session = get_session(engine)
    try:
        ws = get_or_create_workspace(session, "Smoke")
        proj = get_or_create_project(session, ws.workspace_id, "SmokeProject")
        create_target(session, proj.project_id, "Queued", "https://example.com/queued")
    finally:
        session.close()
        engine.dispose()

    assert run_sync(settings, []) == 0

    path = tmp_path / "storage" / "interfaces" / "sync_result.json"
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["status"] == "degraded"
    assert data["reason_code"] == "api_key_missing"
    assert data["summary"]["total"] > 0

    engine = create_db_engine(db_path)
    session = get_session(engine)
    try:
        audit = session.exec(
            select(AuditLog).where(AuditLog.action == "sync_changedetection")
        ).all()
        assert len(audit) == 1
        payload = json.loads(audit[0].payload_json or "{}")
        assert payload["status"] == "degraded"
        assert payload["reason_code"] == "api_key_missing"
    finally:
        session.close()
        engine.dispose()


def test_backup_no_db_returns_error(tmp_path: Path) -> None:
    from scoutbot_module.core.cli import run_backup

    settings = _load_test_settings()
    settings["storage"]["root"] = str(tmp_path / "storage")
    settings["storage"]["db_path"] = str(
        tmp_path / "storage" / "db" / "scoutbot.sqlite3"
    )

    exit_code = run_backup(settings, [])
    assert exit_code == 1


def test_backup_creates_manifest_and_db_copy(tmp_path: Path) -> None:
    from scoutbot_module.core.cli import run_backup

    db_path = tmp_path / "storage" / "db" / "scoutbot.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.write_text("test sqlite content", encoding="utf-8")

    settings = _load_test_settings()
    settings["storage"]["root"] = str(tmp_path / "storage")
    settings["storage"]["db_path"] = str(db_path)

    exit_code = run_backup(settings, [])
    assert exit_code == 0

    backup_dirs = list((tmp_path / "storage" / "backups").iterdir())
    assert len(backup_dirs) == 1

    backup_dir = backup_dirs[0]
    assert (backup_dir / "scoutbot.sqlite3").exists()
    assert (backup_dir / "manifest.json").exists()

    manifest = json.loads((backup_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["backup_id"].startswith("backup_")
    assert manifest["db_size_bytes"] > 0
    assert manifest["source_db_path"] == "storage/db/scoutbot.sqlite3"
    assert manifest["backup_db_path"].startswith("storage/backups/backup_")


def test_audit_no_db_returns_error(tmp_path: Path) -> None:
    from scoutbot_module.core.cli import run_audit

    settings = _load_test_settings()
    settings["storage"]["root"] = str(tmp_path / "storage")
    settings["storage"]["db_path"] = str(
        tmp_path / "storage" / "db" / "scoutbot.sqlite3"
    )

    exit_code = run_audit(settings, [])
    assert exit_code == 1


def test_audit_creates_summary_artifact(tmp_path: Path) -> None:
    from scoutbot_module.core.cli import run_audit
    from scoutbot_module.db.migrations import run_migrations

    db_path = tmp_path / "storage" / "db" / "scoutbot.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    run_migrations(db_path)

    settings = _load_test_settings()
    settings["storage"]["root"] = str(tmp_path / "storage")
    settings["storage"]["db_path"] = str(db_path)

    exit_code = run_audit(settings, [])
    assert exit_code == 0

    run_dirs = list((tmp_path / "storage" / "runs").iterdir())
    assert len(run_dirs) >= 1
    latest_run = sorted(run_dirs)[-1]

    audit_path = latest_run / "audit_summary.json"
    assert audit_path.exists()

    summary = json.loads(audit_path.read_text(encoding="utf-8"))
    assert summary["run_id"].startswith("run_")
    assert "recent_actions" in summary
    assert "target_changes" in summary
    assert "sync_results" in summary
    assert "webhook_events" in summary
