from __future__ import annotations

import logging
from typing import Any

from sqlmodel import Session

from scoutbot_module.db.repo import (
    create_target_link,
    get_existing_target_link,
    get_or_create_project,
    get_or_create_target,
    get_or_create_workspace,
    get_workspace_by_name,
    list_projects,
    list_targets,
    update_target_status,
    write_audit_log,
)

LOG = logging.getLogger("scoutbot.services.targets")


def add_target(
    session: Session,
    url: str,
    workspace_name: str,
    actor_telegram_id: str,
    kind: str = "website",
    priority: str = "medium",
    title: str | None = None,
) -> dict[str, Any]:
    ws = get_or_create_workspace(session, workspace_name)
    hostname = _extract_hostname(url)
    project_name = hostname or "unknown"
    proj = get_or_create_project(
        session, ws.workspace_id, project_name, homepage_url=url
    )

    target_title = title or url
    tgt, created = get_or_create_target(
        session,
        proj.project_id,
        title=target_title,
        url=url,
        kind=kind,
        priority=priority,
        status="queued",
    )

    write_audit_log(
        session,
        action="add_target" if created else "update_target",
        actor_telegram_id=actor_telegram_id,
        entity_type="target",
        entity_id=tgt.target_id,
        payload={"url": url, "kind": kind},
    )

    LOG.info(
        "Target %s %s: %s [%s]",
        "created" if created else "updated",
        tgt.target_id,
        url,
        kind,
    )

    return {
        "target_id": tgt.target_id,
        "project_id": proj.project_id,
        "project_name": proj.name,
        "workspace_name": ws.name,
        "title": tgt.title,
        "url": tgt.url,
        "kind": tgt.kind,
        "status": tgt.status,
        "created": created,
    }


def pause_target(
    session: Session, target_id: str, actor_telegram_id: str
) -> dict[str, Any] | None:
    from sqlmodel import select

    from scoutbot_module.db.models import Target

    tgt = session.exec(select(Target).where(Target.target_id == target_id)).first()
    if not tgt:
        return None
    update_target_status(session, tgt, "paused")
    write_audit_log(
        session,
        action="pause_target",
        actor_telegram_id=actor_telegram_id,
        entity_type="target",
        entity_id=target_id,
    )
    return {"target_id": tgt.target_id, "title": tgt.title, "status": tgt.status}


def resume_target(
    session: Session, target_id: str, actor_telegram_id: str
) -> dict[str, Any] | None:
    from sqlmodel import select

    from scoutbot_module.db.models import Target

    tgt = session.exec(select(Target).where(Target.target_id == target_id)).first()
    if not tgt:
        return None
    update_target_status(session, tgt, "queued")
    write_audit_log(
        session,
        action="resume_target",
        actor_telegram_id=actor_telegram_id,
        entity_type="target",
        entity_id=target_id,
    )
    return {"target_id": tgt.target_id, "title": tgt.title, "status": tgt.status}


def delete_target(
    session: Session, target_id: str, actor_telegram_id: str
) -> dict[str, Any] | None:
    from sqlmodel import select

    from scoutbot_module.db.models import Target

    tgt = session.exec(select(Target).where(Target.target_id == target_id)).first()
    if not tgt:
        return None
    update_target_status(session, tgt, "deleted")
    write_audit_log(
        session,
        action="delete_target",
        actor_telegram_id=actor_telegram_id,
        entity_type="target",
        entity_id=target_id,
    )
    return {"target_id": tgt.target_id, "title": tgt.title, "status": tgt.status}


def get_projects_list(session: Session, workspace_name: str) -> list[dict[str, Any]]:
    ws = get_workspace_by_name(session, workspace_name)
    if not ws:
        return []
    projects = list_projects(session, ws.workspace_id)
    return [
        {
            "project_id": p.project_id,
            "name": p.name,
            "homepage_url": p.homepage_url,
        }
        for p in projects
    ]


def get_targets_list(
    session: Session, project_id: str | None = None, limit: int = 50
) -> list[dict[str, Any]]:
    targets = list_targets(session, project_id=project_id, limit=limit)
    return [
        {
            "target_id": t.target_id,
            "title": t.title,
            "url": t.url,
            "kind": t.kind,
            "status": t.status,
            "priority": t.priority,
        }
        for t in targets
    ]


def store_target_link(
    session: Session,
    source_target_id: str,
    url: str,
    kind: str = "unknown",
    relationship: str = "unknown",
    confidence: float | None = None,
    status: str = "discovered",
    reason_code: str | None = None,
) -> dict[str, Any]:
    existing = get_existing_target_link(session, source_target_id, url)
    if existing:
        return {"link_id": existing.link_id, "created": False}
    link = create_target_link(
        session,
        source_target_id=source_target_id,
        url=url,
        kind=kind,
        relationship=relationship,
        confidence=confidence,
        status=status,
        reason_code=reason_code,
    )
    return {"link_id": link.link_id, "created": True}


def _extract_hostname(url: str) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    return parsed.hostname or ""
