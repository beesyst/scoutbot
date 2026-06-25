from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from sqlmodel import Session, create_engine

from scoutbot_module.changedetection.client import CDResult
from scoutbot_module.changedetection.payloads import (
    _interval_seconds_to_cd_interval,
    build_watch_payload,
)
from scoutbot_module.changedetection.sync import run_sync
from scoutbot_module.db.repo import (
    create_target,
    get_or_create_watch,
    update_watch_uuid,
)
from scoutbot_module.db.session import init_schema


class TestIntervalSecondsToCdInterval:
    def test_days(self) -> None:
        assert _interval_seconds_to_cd_interval(86400) == {"days": 1}

    def test_hours_6(self) -> None:
        assert _interval_seconds_to_cd_interval(21600) == {"hours": 6}

    def test_hours_1(self) -> None:
        assert _interval_seconds_to_cd_interval(3600) == {"hours": 1}

    def test_minutes(self) -> None:
        assert _interval_seconds_to_cd_interval(60) == {"minutes": 1}

    def test_seconds(self) -> None:
        assert _interval_seconds_to_cd_interval(30) == {"seconds": 30}

    def test_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="interval_seconds must be positive"):
            _interval_seconds_to_cd_interval(0)

    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="interval_seconds must be positive"):
            _interval_seconds_to_cd_interval(-1)


def test_payload_has_required_fields() -> None:
    payload = build_watch_payload(
        url="https://example.com",
        title="Example",
        interval_seconds=21600,
    )
    assert payload["url"] == "https://example.com"
    assert payload["title"] == "Example"
    assert payload["time_between_check"] == {"hours": 6}
    assert payload["time_between_check_use_default"] is False
    assert payload["fetch_backend"] == "html_requests"
    assert payload["processor"] == "text_json_diff"


def test_payload_uses_fetch_backend_field() -> None:
    payload = build_watch_payload(
        url="https://example.com",
        title="Example",
    )
    assert payload["fetch_backend"] == "html_requests"


def test_payload_interval_minimum() -> None:
    payload = build_watch_payload(
        url="https://example.com",
        title="Example",
        interval_seconds=30,
    )
    assert payload["time_between_check"] == {"seconds": 30}
    assert payload["time_between_check_use_default"] is False


def test_notification_url_is_safe_in_artifacts() -> None:
    payload = build_watch_payload(
        url="https://example.com",
        title="Example",
        notification_urls=[
            "https://webhook.scoutbot.internal/hook",
            "",
            None,
        ],
    )
    assert "notification_urls" in payload
    assert len(payload["notification_urls"]) == 1
    assert payload["notification_urls"][0] == "https://webhook.scoutbot.internal/hook"


def test_json_notification_url_is_preserved() -> None:
    payload = build_watch_payload(
        url="https://example.com",
        title="Example",
        notification_urls=["json://scoutbot-webhook:8000/webhooks/changedetection"],
    )

    assert payload["notification_urls"] == [
        "json://scoutbot-webhook:8000/webhooks/changedetection"
    ]


def test_secrets_not_serialized() -> None:
    payload = build_watch_payload(
        url="https://example.com",
        title="Example",
        headers={
            "Authorization": "Bearer secret-token",
            "X-Api-Key": "supersecret",
            "Cookie": "session=abc",
            "User-Agent": "ScoutBot/1.0",
        },
    )
    assert payload.get("headers", {}).get("User-Agent") == "ScoutBot/1.0"
    assert "Authorization" not in (payload.get("headers") or {})
    assert "X-Api-Key" not in (payload.get("headers") or {})
    assert "Cookie" not in (payload.get("headers") or {})


def test_payload_with_filters() -> None:
    payload = build_watch_payload(
        url="https://example.com",
        title="Example",
        css_filter=".content",
        xpath="//div[@class='main']",
        ignore_text=["updated", "loading"],
        trigger_text=["delegation", "staking"],
    )
    assert payload["css_filter"] == ".content"
    assert payload["xpath"] == "//div[@class='main']"
    assert payload["ignore_text"] == ["updated", "loading"]
    assert payload["trigger_text"] == ["delegation", "staking"]


def test_empty_notification_urls_omitted() -> None:
    payload = build_watch_payload(
        url="https://example.com",
        title="Example",
        notification_urls=[],
    )
    assert "notification_urls" not in payload


def test_no_secrets_in_payload_repr() -> None:
    payload = build_watch_payload(
        url="https://example.com",
        title="Example",
        notification_urls=["https://hook.example.com/notify"],
    )
    text = str(payload)
    assert "secret" not in text.lower()
    assert "token" not in text.lower()
    assert "api_key" not in text.lower()


def _make_settings() -> dict:
    return {
        "changedetection": {
            "base_url": "http://127.0.0.1:5000",
            "api_key_env": "CHANGEDETECTION_API_KEY",
            "webhook_url_env": "SCOUTBOT_WEBHOOK_URL",
            "webhook_secret_env": "SCOUTBOT_WEBHOOK_SECRET",
            "timeout": 20,
            "interval": {"hours": 6},
            "fetch_backend": "html_requests",
        }
    }


def test_sync_degraded_when_webhook_url_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = create_engine("sqlite://", echo=False)
    init_schema(engine)
    session = Session(engine)
    try:
        create_target(session, None, "Example", "https://example.com")
        monkeypatch.setenv("CHANGEDETECTION_API_KEY", "test-api-key")
        monkeypatch.delenv("SCOUTBOT_WEBHOOK_URL", raising=False)

        result = asyncio.run(run_sync(_make_settings(), session, tmp_path))

        assert result.status == "degraded"
        assert result.reason_code == "webhook_url_missing"

        detail_paths = list((tmp_path / "runs").glob("*/target_sync.json"))
        assert len(detail_paths) == 1
        detail = json.loads(detail_paths[0].read_text(encoding="utf-8"))
        assert detail["notification_configured"] is False
        assert detail["notification_url"] is None
    finally:
        session.close()
        engine.dispose()


def test_sync_passes_notification_url_to_watch_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = create_engine("sqlite://", echo=False)
    init_schema(engine)
    session = Session(engine)
    captured: dict[str, object] = {}

    class FakeClient:
        def __init__(self, base_url: str, api_key: str, timeout: int) -> None:
            del base_url, api_key, timeout

        async def system_info(self) -> CDResult:
            return CDResult.success({"version": "test"})

        async def create_watch(self, payload: dict) -> CDResult:
            captured["payload"] = payload
            return CDResult.success({"uuid": "cd-uuid-1"})

        async def close(self) -> None:
            return None

    def fake_build_watch_payload(**kwargs: object) -> dict[str, object]:
        captured["notification_urls"] = kwargs.get("notification_urls")
        return {"url": "https://example.com", "title": "Example"}

    try:
        create_target(session, None, "Example", "https://example.com")
        monkeypatch.setenv("CHANGEDETECTION_API_KEY", "test-api-key")
        monkeypatch.setenv(
            "SCOUTBOT_WEBHOOK_URL",
            "https://scoutbot.example/webhooks/changedetection",
        )
        monkeypatch.setenv("SCOUTBOT_WEBHOOK_SECRET", "super-secret")
        monkeypatch.setattr(
            "scoutbot_module.changedetection.sync.CDClient",
            FakeClient,
        )
        monkeypatch.setattr(
            "scoutbot_module.changedetection.sync.build_watch_payload",
            fake_build_watch_payload,
        )

        result = asyncio.run(run_sync(_make_settings(), session, tmp_path))

        assert result.status == "ok"
        assert captured["notification_urls"] == [
            "https://scoutbot.example/webhooks/changedetection?secret=super-secret"
        ]

        detail_paths = list((tmp_path / "runs").glob("*/target_sync.json"))
        assert len(detail_paths) == 1
        detail = json.loads(detail_paths[0].read_text(encoding="utf-8"))
        assert detail["notification_configured"] is True
        assert (
            detail["notification_url"]
            == "https://scoutbot.example/webhooks/changedetection"
        )
    finally:
        session.close()
        engine.dispose()


def test_sync_degraded_when_webhook_secret_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = create_engine("sqlite://", echo=False)
    init_schema(engine)
    session = Session(engine)
    try:
        create_target(session, None, "Example", "https://example.com")
        monkeypatch.setenv("CHANGEDETECTION_API_KEY", "test-api-key")
        monkeypatch.setenv(
            "SCOUTBOT_WEBHOOK_URL",
            "https://scoutbot.example/webhooks/changedetection",
        )
        monkeypatch.delenv("SCOUTBOT_WEBHOOK_SECRET", raising=False)

        result = asyncio.run(run_sync(_make_settings(), session, tmp_path))

        assert result.status == "degraded"
        assert result.reason_code == "webhook_secret_missing"

        detail_paths = list((tmp_path / "runs").glob("*/target_sync.json"))
        detail = json.loads(detail_paths[0].read_text(encoding="utf-8"))
        assert detail["notification_configured"] is False
        assert (
            detail["notification_url"]
            == "https://scoutbot.example/webhooks/changedetection"
        )
    finally:
        session.close()
        engine.dispose()


def test_sync_replaces_existing_secret_query(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = create_engine("sqlite://", echo=False)
    init_schema(engine)
    session = Session(engine)
    captured: dict[str, object] = {}

    class FakeClient:
        def __init__(self, base_url: str, api_key: str, timeout: int) -> None:
            del base_url, api_key, timeout

        async def system_info(self) -> CDResult:
            return CDResult.success({"version": "test"})

        async def create_watch(self, payload: dict) -> CDResult:
            captured["payload"] = payload
            return CDResult.success({"uuid": "cd-uuid-1"})

        async def close(self) -> None:
            return None

    def fake_build_watch_payload(**kwargs: object) -> dict[str, object]:
        captured["notification_urls"] = kwargs.get("notification_urls")
        return {"url": "https://example.com", "title": "Example"}

    try:
        create_target(session, None, "Example", "https://example.com")
        monkeypatch.setenv("CHANGEDETECTION_API_KEY", "test-api-key")
        monkeypatch.setenv(
            "SCOUTBOT_WEBHOOK_URL",
            "https://scoutbot.example/webhooks/changedetection?secret=already-there",
        )
        monkeypatch.setenv("SCOUTBOT_WEBHOOK_SECRET", "fresh-secret")
        monkeypatch.setattr(
            "scoutbot_module.changedetection.sync.CDClient",
            FakeClient,
        )
        monkeypatch.setattr(
            "scoutbot_module.changedetection.sync.build_watch_payload",
            fake_build_watch_payload,
        )

        result = asyncio.run(run_sync(_make_settings(), session, tmp_path))

        assert result.status == "ok"
        assert captured["notification_urls"] == [
            "https://scoutbot.example/webhooks/changedetection?secret=fresh-secret"
        ]
    finally:
        session.close()
        engine.dispose()


def test_sync_removes_existing_watch_for_paused_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = create_engine("sqlite://", echo=False)
    init_schema(engine)
    session = Session(engine)
    captured: dict[str, object] = {}

    class FakeClient:
        def __init__(self, base_url: str, api_key: str, timeout: int) -> None:
            del base_url, api_key, timeout

        async def system_info(self) -> CDResult:
            return CDResult.success({"version": "test"})

        async def delete_watch(self, uuid: str) -> CDResult:
            captured["deleted_uuid"] = uuid
            return CDResult.success(status_code=204)

        async def close(self) -> None:
            return None

    try:
        target = create_target(
            session,
            None,
            "Example",
            "https://example.com",
            status="paused",
        )
        watch = get_or_create_watch(session, target.target_id)
        update_watch_uuid(session, watch, "cd-uuid-paused")
        monkeypatch.setenv("CHANGEDETECTION_API_KEY", "test-api-key")
        monkeypatch.setenv(
            "SCOUTBOT_WEBHOOK_URL",
            "https://scoutbot.example/webhooks/changedetection",
        )
        monkeypatch.setenv("SCOUTBOT_WEBHOOK_SECRET", "super-secret")
        monkeypatch.setattr(
            "scoutbot_module.changedetection.sync.CDClient",
            FakeClient,
        )

        result = asyncio.run(run_sync(_make_settings(), session, tmp_path))

        session.refresh(watch)
        assert captured["deleted_uuid"] == "cd-uuid-paused"
        assert watch.changedetection_uuid is None
        assert watch.status == "paused"
        assert result.status != "failed"
    finally:
        session.close()
        engine.dispose()


class TestAdapterKindPayload:
    def test_rss_kind_payload_is_normal(self) -> None:
        payload = build_watch_payload(
            url="https://example.com/feed.xml",
            title="RSS Feed",
            interval_seconds=21600,
        )
        assert payload["url"] == "https://example.com/feed.xml"
        assert payload["fetch_backend"] == "html_requests"
        assert payload["processor"] == "text_json_diff"

    def test_github_repo_kind_payload_is_normal(self) -> None:
        payload = build_watch_payload(
            url="https://github.com/org/repo",
            title="GitHub Repo",
            interval_seconds=21600,
        )
        assert payload["url"] == "https://github.com/org/repo"
        assert payload["fetch_backend"] == "html_requests"

    def test_telegram_public_kind_payload_is_normal(self) -> None:
        payload = build_watch_payload(
            url="https://t.me/s/channel_name",
            title="Telegram Channel",
            interval_seconds=21600,
        )
        assert payload["url"] == "https://t.me/s/channel_name"
        assert payload["fetch_backend"] == "html_requests"
