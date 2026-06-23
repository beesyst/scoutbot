from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import ClassVar

from sqlalchemy.orm import declared_attr
from sqlmodel import Column, Field, SQLModel, Text


def _ts() -> datetime:
    return datetime.now(UTC)


def _short_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


class _TableNameMixin:
    _table_name: ClassVar[str]

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return cls._table_name


class Workspace(_TableNameMixin, SQLModel, table=True):
    _table_name: ClassVar[str] = "workspaces"

    workspace_id: str = Field(
        default_factory=lambda: _short_id("ws_"), primary_key=True
    )
    name: str = Field(..., max_length=255)
    description: str | None = Field(default=None, max_length=1024)
    created_at: datetime = Field(default_factory=_ts)
    updated_at: datetime = Field(default_factory=_ts)


class Project(_TableNameMixin, SQLModel, table=True):
    _table_name: ClassVar[str] = "projects"

    project_id: str = Field(
        default_factory=lambda: _short_id("proj_"), primary_key=True
    )
    workspace_id: str = Field(..., foreign_key="workspaces.workspace_id", index=True)
    name: str = Field(..., max_length=255)
    homepage_url: str | None = Field(default=None, max_length=2048)
    tags_json: str | None = Field(default="[]", sa_column=Column(Text, default="[]"))
    created_at: datetime = Field(default_factory=_ts)
    updated_at: datetime = Field(default_factory=_ts)


class Target(_TableNameMixin, SQLModel, table=True):
    _table_name: ClassVar[str] = "targets"

    target_id: str = Field(default_factory=lambda: _short_id("tgt_"), primary_key=True)
    project_id: str | None = Field(
        default=None, foreign_key="projects.project_id", index=True
    )
    parent_target_id: str | None = Field(
        default=None, foreign_key="targets.target_id", index=True
    )
    title: str = Field(..., max_length=512)
    url: str = Field(..., max_length=2048)
    normalized_url: str | None = Field(default=None, max_length=2048)
    kind: str = Field(default="website", max_length=64)
    priority: str = Field(default="medium", max_length=32)
    status: str = Field(default="queued", max_length=32)
    discovery_status: str | None = Field(default=None, max_length=64)
    confidence: float | None = Field(default=None)
    interval_json: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    fetch_backend: str | None = Field(default="html_requests", max_length=64)
    include_filters_json: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    subtractive_selectors_json: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    ignore_text_json: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    keywords_json: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    created_at: datetime = Field(default_factory=_ts)
    updated_at: datetime = Field(default_factory=_ts)


class TargetLink(_TableNameMixin, SQLModel, table=True):
    _table_name: ClassVar[str] = "target_links"

    link_id: str = Field(default_factory=lambda: _short_id("lnk_"), primary_key=True)
    source_target_id: str = Field(..., foreign_key="targets.target_id", index=True)
    target_id: str | None = Field(
        default=None, foreign_key="targets.target_id", index=True
    )
    url: str = Field(..., max_length=2048)
    normalized_url: str | None = Field(default=None, max_length=2048)
    kind: str = Field(default="unknown", max_length=64)
    relationship: str = Field(default="unknown", max_length=64)
    confidence: float | None = Field(default=None)
    status: str = Field(default="discovered", max_length=32)
    reason_code: str | None = Field(default=None, max_length=128)
    discovered_at: datetime = Field(default_factory=_ts)


class Watch(_TableNameMixin, SQLModel, table=True):
    _table_name: ClassVar[str] = "watches"

    watch_id: str = Field(default_factory=lambda: _short_id("wch_"), primary_key=True)
    target_id: str = Field(..., foreign_key="targets.target_id", index=True)
    changedetection_uuid: str | None = Field(default=None, max_length=128)
    status: str = Field(default="sync_pending", max_length=32)
    last_sync_at: datetime | None = Field(default=None)
    last_error: str | None = Field(default=None, max_length=1024)
    created_at: datetime = Field(default_factory=_ts)
    updated_at: datetime = Field(default_factory=_ts)


class Signal(_TableNameMixin, SQLModel, table=True):
    _table_name: ClassVar[str] = "signals"

    signal_id: str = Field(default_factory=lambda: _short_id("sig_"), primary_key=True)
    target_id: str | None = Field(
        default=None, foreign_key="targets.target_id", index=True
    )
    watch_id: str | None = Field(
        default=None, foreign_key="watches.watch_id", index=True
    )
    changedetection_uuid: str | None = Field(default=None, max_length=128)
    detected_at: datetime = Field(default_factory=_ts)
    category: str | None = Field(default=None, max_length=64)
    priority: str | None = Field(default=None, max_length=32)
    diff_hash: str | None = Field(default=None, max_length=128)
    title: str | None = Field(default=None, max_length=512)
    summary: str | None = Field(default=None, max_length=4096)
    raw_excerpt: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    url: str | None = Field(default=None, max_length=2048)
    telegram_message_id: int | None = Field(default=None)
    created_at: datetime = Field(default_factory=_ts)


class AuditLog(_TableNameMixin, SQLModel, table=True):
    _table_name: ClassVar[str] = "audit_log"

    audit_id: str = Field(default_factory=lambda: _short_id("aud_"), primary_key=True)
    actor_telegram_id: str | None = Field(default=None, max_length=128)
    action: str = Field(..., max_length=128)
    entity_type: str | None = Field(default=None, max_length=64)
    entity_id: str | None = Field(default=None, max_length=128)
    payload_json: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    created_at: datetime = Field(default_factory=_ts)
