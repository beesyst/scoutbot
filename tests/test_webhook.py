from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from sqlmodel import Session, create_engine

from scoutbot_module.db.repo import (
    create_target,
    get_or_create_watch,
    update_watch_uuid,
)
from scoutbot_module.db.session import init_schema
from scoutbot_module.web.routes import create_web_app


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine("sqlite://", echo=False)
    init_schema(engine)
    session = Session(engine)
    yield session
    session.close()


def _make_test_app(secret: str = "test-secret", db_path: str = ":memory:") -> Any:
    settings = {
        "storage": {"root": "/tmp/scoutbot-test", "db_path": db_path},
        "webhook": {
            "host": "127.0.0.1",
            "port": 8000,
            "path": "/webhooks/changedetection",
            "body_bytes_max": 131072,
        },
        "telegram": {
            "token_env": "TELEGRAM_BOT_TOKEN",
            "admin_ids_env": "TELEGRAM_ADMIN_IDS",
            "chat_id_env": "TELEGRAM_ALERT_CHAT_ID",
        },
        "changedetection": {
            "webhook_secret_env": "SCOUTBOT_WEBHOOK_SECRET",
        },
        "signals": {
            "dedupe_enabled": True,
            "body_excerpt_chars": 1000,
            "categories": {
                "pricing": ["pricing", "price"],
                "delegation": ["delegation", "staking"],
                "product": ["feature", "api"],
            },
        },
        "workspace": {"default_name": "TEST"},
    }
    app = create_web_app(
        secret=secret,
        settings=settings,
        db_path=db_path,
        body_bytes_max=131072,
    )
    return app


def _post_json(app: Any, path: str, payload: Any) -> httpx.Response:
    async def _request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.post(path, json=payload)

    return asyncio.run(_request())


def test_missing_secret_rejected(tmp_path: Path) -> None:
    db_path = str(tmp_path / "test.db")
    app = _make_test_app(secret="test-secret", db_path=db_path)
    resp = _post_json(app, "/webhooks/changedetection", {})
    assert resp.status_code in (401, 403)


def test_invalid_secret_rejected(tmp_path: Path) -> None:
    db_path = str(tmp_path / "test.db")
    app = _make_test_app(secret="test-secret", db_path=db_path)
    resp = _post_json(app, "/webhooks/changedetection?secret=wrong", {})
    assert resp.status_code == 403


def test_valid_payload_creates_signal(
    tmp_path: Path, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    tgt = create_target(db_session, None, "Test", "https://example.com")
    watch = get_or_create_watch(db_session, tgt.target_id)
    cd_uuid = "cd-uuid-12345"
    update_watch_uuid(db_session, watch, cd_uuid)
    db_session.commit()

    db_path = str(tmp_path / "test.db")

    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    init_schema(engine)
    s = Session(engine)
    tgt2 = create_target(s, None, "Test", "https://example.com")
    w2 = get_or_create_watch(s, tgt2.target_id)
    update_watch_uuid(s, w2, cd_uuid)
    s.commit()
    s.close()
    engine.dispose()

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("SCOUTBOT_WEBHOOK_SECRET", "test-secret")

    app = _make_test_app(secret="test-secret", db_path=db_path)

    payload = {
        "uuid": cd_uuid,
        "title": "Test Change",
        "url": "https://example.com",
        "text": "Some content changed",
        "diff": "+added line",
    }

    resp = _post_json(app, "/webhooks/changedetection?secret=test-secret", payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["deduped"] is False
    assert data["signal_id"] is not None


def test_missing_uuid_returns_422(tmp_path: Path) -> None:
    db_path = str(tmp_path / "test.db")
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    init_schema(engine)
    engine.dispose()

    app = _make_test_app(secret="test-secret", db_path=db_path)
    resp = _post_json(
        app,
        "/webhooks/changedetection?secret=test-secret",
        {"title": "Missing UUID", "url": "https://example.com"},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "Missing changedetection UUID"


def test_unknown_watch_uuid_returns_404(tmp_path: Path) -> None:
    db_path = str(tmp_path / "test.db")
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    init_schema(engine)
    engine.dispose()

    app = _make_test_app(secret="test-secret", db_path=db_path)
    resp = _post_json(
        app,
        "/webhooks/changedetection?secret=test-secret",
        {
            "uuid": "unknown-watch",
            "title": "Unknown",
            "url": "https://example.com",
        },
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Watch not found"


def test_async_alert_dispatch_is_awaited(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = str(tmp_path / "test.db")
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    init_schema(engine)
    s = Session(engine)
    tgt = create_target(s, None, "Test", "https://example.com")
    watch = get_or_create_watch(s, tgt.target_id)
    update_watch_uuid(s, watch, "cd-uuid-alert")
    s.commit()
    s.close()
    engine.dispose()

    captured: dict[str, object] = {}

    async def fake_send(
        settings: dict, signal: dict, target_info: dict | None = None
    ) -> dict:
        captured["signal"] = signal
        captured["target_info"] = target_info
        return {"sent": True}

    monkeypatch.setattr(
        "scoutbot_module.services.notifications.send_telegram_alert_async",
        fake_send,
    )
    monkeypatch.setenv("SCOUTBOT_WEBHOOK_SECRET", "test-secret")

    app = _make_test_app(secret="test-secret", db_path=db_path)
    resp = _post_json(
        app,
        "/webhooks/changedetection?secret=test-secret",
        {
            "uuid": "cd-uuid-alert",
            "title": "Alert title",
            "url": "https://example.com",
            "text": "Alert body",
        },
    )
    assert resp.status_code == 200
    signal = cast(Any, captured["signal"])
    assert isinstance(signal, dict)
    assert signal["url"] == "https://example.com"
    assert signal["title"] == "Alert title"
    assert signal["summary"] == "Alert body"


def test_duplicate_payload_dedupes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = str(tmp_path / "test.db")
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    init_schema(engine)
    s = Session(engine)
    tgt = create_target(s, None, "Test", "https://example.com")
    watch = get_or_create_watch(s, tgt.target_id)
    cd_uuid = "cd-uuid-dedup"
    update_watch_uuid(s, watch, cd_uuid)
    s.commit()
    s.close()
    engine.dispose()

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("SCOUTBOT_WEBHOOK_SECRET", "test-secret")

    app = _make_test_app(secret="test-secret", db_path=db_path)
    payload = {
        "uuid": cd_uuid,
        "title": "Same Change",
        "url": "https://example.com",
        "text": "identical content",
    }

    resp1 = _post_json(app, "/webhooks/changedetection?secret=test-secret", payload)
    assert resp1.status_code == 200
    assert resp1.json()["deduped"] is False

    resp2 = _post_json(app, "/webhooks/changedetection?secret=test-secret", payload)
    assert resp2.status_code == 200
    assert resp2.json()["deduped"] is True


def test_malformed_payload_422(tmp_path: Path) -> None:
    db_path = str(tmp_path / "test.db")
    app = _make_test_app(secret="test-secret", db_path=db_path)

    resp = _post_json(
        app, "/webhooks/changedetection?secret=test-secret", "not an object"
    )
    assert resp.status_code == 422


def test_oversized_payload_413(tmp_path: Path) -> None:
    db_path = str(tmp_path / "test.db")
    app = _make_test_app(secret="test-secret", db_path=db_path)

    resp = _post_json(
        app,
        "/webhooks/changedetection?secret=test-secret",
        {"data": "x" * 200000},
    )
    assert resp.status_code == 413


def test_alert_skipped_when_telegram_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = str(tmp_path / "test.db")
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    init_schema(engine)
    s = Session(engine)
    tgt = create_target(s, None, "Test", "https://example.com")
    watch = get_or_create_watch(s, tgt.target_id)
    cd_uuid = "cd-uuid-no-tg"
    update_watch_uuid(s, watch, cd_uuid)
    s.commit()
    s.close()
    engine.dispose()

    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("SCOUTBOT_WEBHOOK_SECRET", "test-secret")

    app = _make_test_app(secret="test-secret", db_path=db_path)
    payload = {
        "uuid": cd_uuid,
        "title": "Test",
        "url": "https://example.com",
        "text": "content",
    }

    resp = _post_json(app, "/webhooks/changedetection?secret=test-secret", payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
