from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from sqlmodel import Session, create_engine, select

from scoutbot_module.bot.formatters import (
    format_add_result,
    format_projects_list,
    format_signal_alert,
    format_targets_list,
)
from scoutbot_module.bot.handlers import (
    cmd_add,
    cmd_check,
    cmd_delete,
    cmd_pause,
    cmd_projects,
    cmd_resume,
    cmd_subscribers,
    cmd_targets,
    handle_signal_action_callback,
)
from scoutbot_module.bot.keyboards import build_target_actions_keyboard
from scoutbot_module.db.models import AuditLog, Target
from scoutbot_module.db.repo import (
    create_signal,
    create_target,
)
from scoutbot_module.db.session import init_schema
from scoutbot_module.services.notifications import send_telegram_alert_async
from scoutbot_module.services.targets import (
    add_target,
    delete_target,
    pause_target,
    resume_target,
)


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine("sqlite://", echo=False)
    init_schema(engine)
    session = Session(engine)
    yield session
    session.close()


def test_admin_ids_parsing() -> None:
    from scoutbot_module.bot.app import _parse_ids

    assert _parse_ids("123 456") == {123, 456}
    assert _parse_ids("123,456,789") == {123, 456, 789}
    assert _parse_ids("") == set()
    assert _parse_ids("abc") == set()
    assert _parse_ids("123 abc 456") == {123, 456}


def test_add_target_saves_to_sqlite(db_session: Session) -> None:
    result = add_target(
        session=db_session,
        url="https://example.com",
        workspace_name="TestWS",
        actor_telegram_id="12345",
    )
    assert result["target_id"].startswith("tgt_")
    assert result["url"] == "https://example.com"
    assert result["status"] == "queued"

    tgt = db_session.exec(
        select(Target).where(Target.target_id == result["target_id"])
    ).first()
    assert tgt is not None
    assert tgt.url == "https://example.com"


def test_pause_target_updates_status(db_session: Session) -> None:
    tgt = create_target(
        db_session, None, "Test", "https://example.com", status="queued"
    )
    result = pause_target(db_session, tgt.target_id, "12345")
    assert result is not None
    assert result["status"] == "paused"

    db_session.refresh(tgt)
    assert tgt.status == "paused"


def test_resume_target_updates_status(db_session: Session) -> None:
    tgt = create_target(
        db_session, None, "Test", "https://example.com", status="paused"
    )
    result = resume_target(db_session, tgt.target_id, "12345")
    assert result is not None
    assert result["status"] == "queued"

    db_session.refresh(tgt)
    assert tgt.status == "queued"


def test_delete_target_updates_status(db_session: Session) -> None:
    tgt = create_target(db_session, None, "Test", "https://example.com")
    result = delete_target(db_session, tgt.target_id, "12345")
    assert result is not None
    assert result["status"] == "deleted"

    db_session.refresh(tgt)
    assert tgt.status == "deleted"


def test_format_add_result_no_secrets() -> None:
    result = {
        "target_id": "tgt_abc123",
        "project_name": "Test",
        "title": "Example",
        "url": "https://example.com",
        "kind": "website",
        "status": "queued",
        "links_found": 5,
        "children_created": 2,
        "sync_status": "ok",
    }
    text = format_add_result(result)
    assert "token" not in text.lower()
    assert "secret" not in text.lower()
    assert "api_key" not in text.lower()
    assert "tgt_abc123" in text


def test_format_targets_list() -> None:
    targets = [
        {
            "target_id": "tgt_1",
            "title": "Site A",
            "url": "https://a.com",
            "kind": "website",
            "status": "active",
            "priority": "high",
        },
        {
            "target_id": "tgt_2",
            "title": "Site B",
            "url": "https://b.com",
            "kind": "blog",
            "status": "queued",
            "priority": "medium",
        },
    ]
    text = format_targets_list(targets)
    assert "Site A" in text
    assert "Site B" in text
    assert "tgt_1" in text
    assert "tgt_2" in text
    assert "token" not in text.lower()


def test_format_projects_list() -> None:
    projects = [
        {"project_id": "p1", "name": "Project A", "homepage_url": "https://a.com"},
        {"project_id": "p2", "name": "Project B", "homepage_url": None},
    ]
    text = format_projects_list(projects)
    assert "Project A" in text
    assert "Project B" in text


def test_format_signal_alert_no_secrets() -> None:
    signal = {
        "signal_id": "sig_1",
        "category": "pricing",
        "priority": "high",
        "url": "https://example.com/pricing",
        "summary": None,
    }
    target_info = {
        "project_name": "TestProject",
        "title": "Example Site",
    }
    text = format_signal_alert(signal, target_info)
    assert "token" not in text.lower()
    assert "secret" not in text.lower()
    assert "api_key" not in text.lower()
    assert "TELEGRAM" not in text
    assert "CHANGEDETECTION" not in text
    assert "No summary available" in text


def test_cmd_add_rejects_private_url_before_target_creation(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    replies: list[str] = []

    class DummyMessage:
        async def reply_text(self, text: str, **kwargs: object) -> None:
            del kwargs
            replies.append(text)

    class DummyUser:
        id = 123

    class DummyUpdate:
        effective_user = DummyUser()
        effective_message = DummyMessage()

    class DummyContext:
        args = ["http://127.0.0.1/private"]
        bot_data = {
            "allowed_user_ids": {123},
            "settings": {
                "workspace": {"default_name": "TEST"},
                "discovery": {"allow_private_networks": False, "enabled": False},
            },
            "db_path": "sqlite://",
        }

    def fail_add_target(**kwargs: object) -> None:
        raise AssertionError("add_target must not be called for private URL")

    class DummyEngine:
        def dispose(self) -> None:
            return None

    monkeypatch.setattr(
        "scoutbot_module.bot.handlers.get_session", lambda engine: db_session
    )
    monkeypatch.setattr(
        "scoutbot_module.bot.handlers.create_db_engine", lambda db_path: DummyEngine()
    )
    monkeypatch.setattr("scoutbot_module.bot.handlers.add_target", fail_add_target)

    asyncio.run(cmd_add(cast(Any, DummyUpdate()), cast(Any, DummyContext())))

    assert any("Invalid URL" in reply for reply in replies)
    assert db_session.exec(select(Target)).all() == []


def test_cmd_check_awaits_run_sync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    replies: list[str] = []
    captured: dict[str, object] = {}

    class DummyMessage:
        async def reply_text(self, text: str, **kwargs: object) -> None:
            del kwargs
            replies.append(text)

    class DummyUser:
        id = 123

    class DummyUpdate:
        effective_user = DummyUser()
        effective_message = DummyMessage()

    class DummySession:
        def close(self) -> None:
            return None

    class DummyEngine:
        def dispose(self) -> None:
            return None

    class DummyResult:
        status = "ok"
        summary = {"created": 1, "updated": 2, "failed": 0}

    class DummyContext:
        bot_data = {
            "allowed_user_ids": {123},
            "settings": {"storage": {"root": "storage"}},
            "db_path": "sqlite://",
        }

    async def fake_run_sync(
        settings: dict, db_session: object, storage_root: object
    ) -> DummyResult:
        captured["settings"] = settings
        captured["db_session"] = db_session
        captured["storage_root"] = storage_root
        return DummyResult()

    monkeypatch.setattr(
        "scoutbot_module.bot.handlers.create_db_engine", lambda db_path: DummyEngine()
    )
    monkeypatch.setattr(
        "scoutbot_module.bot.handlers.get_session", lambda engine: DummySession()
    )
    monkeypatch.setattr("scoutbot_module.bot.handlers.run_sync", fake_run_sync)

    asyncio.run(cmd_check(cast(Any, DummyUpdate()), cast(Any, DummyContext())))

    assert captured["db_session"] is not None
    assert replies
    assert "Sync: ok" in replies[0]


@pytest.mark.parametrize(
    ("handler", "reply_text"),
    [
        (cmd_projects, "Projects OK"),
        (cmd_targets, "Targets OK"),
    ],
)
def test_allowed_user_can_access_list_commands(
    monkeypatch: pytest.MonkeyPatch,
    handler: Any,
    reply_text: str,
) -> None:
    replies: list[str] = []

    class DummyMessage:
        async def reply_text(self, text: str, **kwargs: object) -> None:
            del kwargs
            replies.append(text)

    class DummyUser:
        id = 123

    class DummyUpdate:
        effective_user = DummyUser()
        effective_message = DummyMessage()

    class DummySession:
        def close(self) -> None:
            return None

    class DummyEngine:
        def dispose(self) -> None:
            return None

    class DummyContext:
        bot_data = {
            "allowed_user_ids": {123},
            "settings": {"workspace": {"default_name": "TEST"}},
            "db_path": "sqlite://",
        }

    monkeypatch.setattr(
        "scoutbot_module.bot.handlers.create_db_engine", lambda db_path: DummyEngine()
    )
    monkeypatch.setattr(
        "scoutbot_module.bot.handlers.get_session", lambda engine: DummySession()
    )
    monkeypatch.setattr(
        "scoutbot_module.services.targets.get_projects_list",
        lambda session, workspace_name: [{"name": "Project A", "homepage_url": ""}],
    )
    monkeypatch.setattr(
        "scoutbot_module.services.targets.get_targets_list",
        lambda session, limit=20: [
            {
                "target_id": "tgt_1",
                "title": "Example",
                "url": "https://example.com",
                "kind": "website",
                "status": "active",
            }
        ],
    )

    asyncio.run(handler(cast(Any, DummyUpdate()), cast(Any, DummyContext())))

    assert replies
    assert "⛔" not in replies[0]


@pytest.mark.parametrize(
    ("handler", "args"),
    [
        (cmd_pause, ["tgt_1"]),
        (cmd_resume, ["tgt_1"]),
        (cmd_delete, ["tgt_1"]),
        (cmd_subscribers, []),
    ],
)
def test_non_admin_cannot_access_destructive_or_admin_commands(
    handler: Any,
    args: list[str],
) -> None:
    replies: list[str] = []

    class DummyMessage:
        async def reply_text(self, text: str, **kwargs: object) -> None:
            del kwargs
            replies.append(text)

    class DummyUser:
        id = 123

    class DummyUpdate:
        effective_user = DummyUser()
        effective_message = DummyMessage()

    class DummyContext:
        def __init__(self, args: list[str]) -> None:
            self.args = args
            self.bot_data = {
                "allowed_user_ids": {123},
                "admin_ids": set(),
                "db_path": "sqlite://",
            }

    context = DummyContext(args)

    asyncio.run(handler(cast(Any, DummyUpdate()), cast(Any, context)))

    assert replies == ["⛔ Admin only."]


def test_send_telegram_alert_async_awaitable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_ALERT_CHAT_ID", "chat")

    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {"message_id": "42"}

    class FakeAsyncClient:
        def __init__(self, **kwargs: object) -> None:
            captured["client_kwargs"] = kwargs

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            del exc_type, exc, tb

        async def post(self, url: str, json: dict[str, object]) -> FakeResponse:
            captured["url"] = url
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    result = asyncio.run(
        send_telegram_alert_async(
            settings={
                "telegram": {
                    "token_env": "TELEGRAM_BOT_TOKEN",
                    "chat_id_env": "TELEGRAM_ALERT_CHAT_ID",
                }
            },
            signal={
                "signal_id": "sig-1",
                "url": "https://example.com",
                "summary": "Updated",
                "category": "product",
                "priority": "high",
            },
        )
    )

    assert result["sent"] is True
    payload = cast(Any, captured["json"])
    assert payload["chat_id"] == "chat"
    assert payload["text"]
    assert (
        payload["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
        == "signal:noise:sig-1"
    )
    assert "parse_mode" not in payload


def test_build_target_actions_keyboard() -> None:
    markup = build_target_actions_keyboard("tgt_123")
    rows = markup.inline_keyboard
    assert rows[0][0].callback_data == "target:pause:tgt_123"
    assert rows[0][1].callback_data == "target:resume:tgt_123"
    assert rows[1][0].callback_data == "target:delete:tgt_123"
    assert rows[1][1].callback_data == "target:noise:tgt_123"


def test_cmd_add_reply_includes_inline_keyboard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_reply: dict[str, Any] = {}

    class DummyMessage:
        async def reply_text(self, text: str, **kwargs: object) -> None:
            captured_reply["text"] = text
            captured_reply["kwargs"] = kwargs

    class DummyUser:
        id = 123

    class DummyUpdate:
        effective_user = cast(Any, DummyUser())
        effective_message = cast(Any, DummyMessage())

    class DummySession:
        def close(self) -> None:
            return None

    class DummyEngine:
        def dispose(self) -> None:
            return None

    class DummySyncResult:
        status = "ok"

    class DummyContext:
        args = ["https://example.com"]
        bot_data = {
            "allowed_user_ids": {123},
            "settings": {
                "workspace": {"default_name": "TEST"},
                "discovery": {"allow_private_networks": True, "enabled": False},
                "storage": {"root": "storage"},
            },
            "db_path": "sqlite://",
        }

    async def fake_run_sync(
        settings: dict, db_session: object, storage_root: object
    ) -> DummySyncResult:
        del settings, db_session, storage_root
        return DummySyncResult()

    monkeypatch.setattr(
        "scoutbot_module.bot.handlers.create_db_engine", lambda db_path: DummyEngine()
    )
    monkeypatch.setattr(
        "scoutbot_module.bot.handlers.get_session", lambda engine: DummySession()
    )
    monkeypatch.setattr("scoutbot_module.bot.handlers.run_sync", fake_run_sync)
    monkeypatch.setattr(
        "scoutbot_module.bot.handlers.add_target",
        lambda **kwargs: {
            "target_id": "tgt_123",
            "project_name": "TEST",
            "title": "Example",
            "url": "https://example.com/",
            "kind": "website",
            "status": "queued",
        },
    )

    asyncio.run(cmd_add(cast(Any, DummyUpdate()), cast(Any, DummyContext())))

    markup = cast(Any, captured_reply["kwargs"])["reply_markup"]
    assert markup.inline_keyboard[0][0].callback_data == "target:pause:tgt_123"


def test_cmd_add_uses_async_discovery_without_to_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class DummyMessage:
        async def reply_text(self, text: str, **kwargs: object) -> None:
            del text, kwargs

    class DummyUser:
        id = 123

    class DummyUpdate:
        effective_user = cast(Any, DummyUser())
        effective_message = cast(Any, DummyMessage())

    class DummySession:
        def close(self) -> None:
            return None

    class DummyEngine:
        def dispose(self) -> None:
            return None

    class DummySyncResult:
        status = "ok"

    class DummyContext:
        args = ["https://example.com"]
        bot_data = {
            "allowed_user_ids": {123},
            "settings": {
                "workspace": {"default_name": "TEST"},
                "discovery": {"allow_private_networks": True, "enabled": True},
                "storage": {"root": "storage"},
            },
            "db_path": "sqlite://",
        }

    async def fake_run_discovery_async(**kwargs: object) -> dict[str, int]:
        captured["session"] = kwargs["session"]
        return {"links_found": 1, "children_created": 0}

    async def fake_run_sync(
        settings: dict, db_session: object, storage_root: object
    ) -> DummySyncResult:
        del settings, db_session, storage_root
        return DummySyncResult()

    async def fail_to_thread(*args: object, **kwargs: object) -> None:
        raise AssertionError("asyncio.to_thread must not be used in cmd_add discovery")

    monkeypatch.setattr(
        "scoutbot_module.bot.handlers.create_db_engine", lambda db_path: DummyEngine()
    )
    monkeypatch.setattr(
        "scoutbot_module.bot.handlers.get_session", lambda engine: DummySession()
    )
    monkeypatch.setattr("scoutbot_module.bot.handlers.run_sync", fake_run_sync)
    monkeypatch.setattr(
        "scoutbot_module.bot.handlers.add_target",
        lambda **kwargs: {
            "target_id": "tgt_123",
            "project_name": "TEST",
            "title": "Example",
            "url": "https://example.com/",
            "kind": "website",
            "status": "queued",
        },
    )
    monkeypatch.setattr(
        "scoutbot_module.services.discovery.run_bounded_discovery_async",
        fake_run_discovery_async,
    )
    monkeypatch.setattr("asyncio.to_thread", fail_to_thread)

    asyncio.run(cmd_add(cast(Any, DummyUpdate()), cast(Any, DummyContext())))

    assert captured["session"] is not None


def test_handle_signal_action_callback_marks_exact_signal_as_noise(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "test.sqlite3"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    init_schema(engine)
    session = Session(engine)
    try:
        target = create_target(session, None, "Example", "https://example.com")
        older = create_signal(
            session,
            target_id=target.target_id,
            category="product",
            priority="medium",
            title="Older",
        )
        newer = create_signal(
            session,
            target_id=target.target_id,
            category="pricing",
            priority="high",
            title="Newer",
        )
        replies: list[str] = []

        class DummyQuery:
            data = f"signal:noise:{older.signal_id}"
            message = None

            async def answer(self) -> None:
                return None

            async def edit_message_text(self, text: str, **kwargs: object) -> None:
                del kwargs
                replies.append(text)

        class DummyUser:
            id = 123

        class DummyUpdate:
            effective_user = DummyUser()
            callback_query = DummyQuery()

        class DummyContext:
            bot_data = {
                "allowed_user_ids": {123},
                "db_path": db_path,
                "settings": {"storage": {"root": str(tmp_path / "storage")}},
            }

        asyncio.run(
            handle_signal_action_callback(
                cast(Any, DummyUpdate()),
                cast(Any, DummyContext()),
            )
        )

        session.refresh(older)
        session.refresh(newer)
        session.refresh(target)

        assert older.category == "noise"
        assert older.priority == "low"
        assert newer.category == "pricing"
        assert newer.priority == "high"
        assert older.signal_id in (target.ignore_text_json or "")

        audit = session.exec(
            select(AuditLog).where(AuditLog.entity_id == older.signal_id)
        ).all()
        assert any(item.action == "mark_as_noise" for item in audit)
        noise_files = list((tmp_path / "storage" / "runs").glob("*/noise_update.json"))
        assert len(noise_files) == 1
        assert replies
        assert "Marked as noise" in replies[0]
    finally:
        session.close()
        engine.dispose()
