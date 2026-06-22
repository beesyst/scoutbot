from __future__ import annotations

import pytest

from scoutbot_module.changedetection.payloads import (
    _interval_seconds_to_cd_interval,
    build_watch_payload,
)


# Тест: helper конвертирует сек в объект интервала changedetection
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


# Тест: пэйлоад содержит обязательные поля url, title, interval и fetch_backend
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


# Тест: параметр fetch_backend равен html_requests
def test_payload_default_fetch_backend() -> None:
    payload = build_watch_payload(
        url="https://example.com",
        title="Example",
    )
    assert payload["fetch_backend"] == "html_requests"


# Тест: interval 30 секунд превращается в {"seconds": 30}
def test_payload_interval_minimum() -> None:
    payload = build_watch_payload(
        url="https://example.com",
        title="Example",
        interval_seconds=30,
    )
    assert payload["time_between_check"] == {"seconds": 30}
    assert payload["time_between_check_use_default"] is False


# Тест: notification URLs фильтруются от пустых значений
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


# Тест: notification URL с json:// сохраняется в пэйлоад
def test_json_notification_url_is_preserved() -> None:
    payload = build_watch_payload(
        url="https://example.com",
        title="Example",
        notification_urls=["json://scoutbot-webhook:8000/webhooks/changedetection"],
    )

    assert payload["notification_urls"] == [
        "json://scoutbot-webhook:8000/webhooks/changedetection"
    ]


# Тест: небезопасные заголовки не включаются в пэйлоад
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


# Тест: CSS фильтр, xpath, ignore_text и trigger_text включаются в пэйлоад
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


# Тест: пустой список notification_urls не включается в пэйлоад
def test_empty_notification_urls_omitted() -> None:
    payload = build_watch_payload(
        url="https://example.com",
        title="Example",
        notification_urls=[],
    )
    assert "notification_urls" not in payload


# Тест: None в notification_urls не включается в пэйлоад
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
