from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class WebhookEvent(BaseModel):
    uuid: str | None = None
    watch_uuid: str | None = None
    changedetection_uuid: str | None = None
    watch: dict[str, Any] | None = None
    title: str | None = None
    url: str | None = None
    text: str | None = None
    diff: str | None = None
    screenshot: str | None = None
    current_screenshot: str | None = None
    previous_screenshot: str | None = None
    summary: str | None = None
    timestamp: str | None = None


class WebhookResponse(BaseModel):
    status: str = "ok"
    deduped: bool = False
    signal_id: str | None = None
