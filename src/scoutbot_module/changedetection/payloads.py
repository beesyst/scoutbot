from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def _interval_seconds_to_cd_interval(interval_seconds: int) -> dict[str, int]:
    if interval_seconds <= 0:
        raise ValueError(f"interval_seconds must be positive, got {interval_seconds}")
    if interval_seconds % 86400 == 0:
        return {"days": interval_seconds // 86400}
    if interval_seconds % 3600 == 0:
        return {"hours": interval_seconds // 3600}
    if interval_seconds % 60 == 0:
        return {"minutes": interval_seconds // 60}
    return {"seconds": interval_seconds}


def build_watch_payload(
    url: str,
    title: str,
    interval_seconds: int | None = None,
    fetch_backend: str = "html_requests",
    notification_urls: Sequence[str | None] | None = None,
    headers: dict[str, str] | None = None,
    body: str | None = None,
    css_filter: str | None = None,
    xpath: str | None = None,
    ignore_text: list[str] | None = None,
    trigger_text: list[str] | None = None,
    extract_rules: list[str] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "url": url,
        "title": title,
        "fetch_backend": fetch_backend,
    }

    if interval_seconds is not None:
        payload["time_between_check"] = _interval_seconds_to_cd_interval(
            interval_seconds
        )
        payload["time_between_check_use_default"] = False

    if notification_urls:
        safe_urls = [
            u
            for u in notification_urls
            if u and u.startswith(("http://", "https://", "json://"))
        ]
        if safe_urls:
            payload["notification_urls"] = safe_urls

    if headers:
        safe_headers = {k: v for k, v in headers.items() if _is_safe_header(k)}
        if safe_headers:
            payload["headers"] = safe_headers

    if body is not None:
        payload["body"] = body

    if css_filter:
        payload["css_filter"] = css_filter
    if xpath:
        payload["xpath"] = xpath
    if ignore_text:
        payload["ignore_text"] = ignore_text
    if trigger_text:
        payload["trigger_text"] = trigger_text
    if extract_rules:
        payload["extract_rules"] = extract_rules

    payload["processor"] = "text_json_diff"

    return payload


def _is_safe_header(key: str) -> bool:
    lower = key.lower()
    blocked = {
        "authorization",
        "x-api-key",
        "cookie",
        "set-cookie",
        "proxy-authorization",
    }
    return lower not in blocked
