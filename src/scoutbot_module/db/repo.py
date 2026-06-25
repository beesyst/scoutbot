from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import yaml
from sqlmodel import Session, col, select

from scoutbot_module.db.models import (
    AuditLog,
    Project,
    Signal,
    Target,
    TargetLink,
    TelegramSubscriber,
    Watch,
    Workspace,
)


def get_workspace_by_name(session: Session, name: str) -> Workspace | None:
    stmt = select(Workspace).where(Workspace.name == name)
    return session.exec(stmt).first()


def get_or_create_workspace(
    session: Session, name: str, description: str = ""
) -> Workspace:
    stmt = select(Workspace).where(Workspace.name == name)
    ws = session.exec(stmt).first()
    if ws:
        return ws
    ws = Workspace(name=name, description=description or None)
    session.add(ws)
    session.commit()
    session.refresh(ws)
    return ws


def list_workspaces(session: Session) -> list[Workspace]:
    return list(session.exec(select(Workspace)).all())


def get_or_create_project(
    session: Session,
    workspace_id: str,
    name: str,
    homepage_url: str | None = None,
    tags: list[str] | None = None,
) -> Project:
    stmt = (
        select(Project)
        .where(Project.workspace_id == workspace_id)
        .where(Project.name == name)
    )
    proj = session.exec(stmt).first()
    if proj:
        return proj
    proj = Project(
        workspace_id=workspace_id,
        name=name,
        homepage_url=homepage_url,
        tags_json=json.dumps(tags or [], ensure_ascii=False),
    )
    session.add(proj)
    session.commit()
    session.refresh(proj)
    return proj


def create_target(
    session: Session,
    project_id: str | None,
    title: str,
    url: str,
    kind: str = "website",
    priority: str = "medium",
    status: str = "queued",
    fetch_backend: str = "html_requests",
    parent_target_id: str | None = None,
) -> Target:
    tgt = Target(
        project_id=project_id,
        parent_target_id=parent_target_id,
        title=title,
        url=url,
        kind=kind,
        priority=priority,
        status=status,
        fetch_backend=fetch_backend,
    )
    session.add(tgt)
    session.commit()
    session.refresh(tgt)
    return tgt


def get_or_create_target(
    session: Session,
    project_id: str | None,
    title: str,
    url: str,
    kind: str = "website",
    priority: str = "medium",
    status: str = "queued",
    fetch_backend: str = "html_requests",
) -> tuple[Target, bool]:
    stmt = (
        select(Target).where(Target.project_id == project_id).where(Target.url == url)
    )
    tgt = session.exec(stmt).first()
    if tgt:
        tgt.title = title or tgt.title
        tgt.kind = kind or tgt.kind
        tgt.priority = priority or tgt.priority
        tgt.status = status or tgt.status
        tgt.fetch_backend = fetch_backend or tgt.fetch_backend
        tgt.updated_at = datetime.now(UTC)
        session.add(tgt)
        session.commit()
        session.refresh(tgt)
        return tgt, False

    tgt = create_target(
        session=session,
        project_id=project_id,
        title=title,
        url=url,
        kind=kind,
        priority=priority,
        status=status,
        fetch_backend=fetch_backend,
    )
    return tgt, True


def list_targets_by_status(session: Session, statuses: tuple[str, ...]) -> list[Target]:
    stmt = select(Target).where(col(Target.status).in_(statuses))
    return list(session.exec(stmt).all())


def list_projects(session: Session, workspace_id: str) -> list[Project]:
    stmt = select(Project).where(Project.workspace_id == workspace_id)
    return list(session.exec(stmt).all())


def list_targets(
    session: Session, project_id: str | None = None, limit: int = 50
) -> list[Target]:
    stmt = select(Target)
    if project_id is not None:
        stmt = stmt.where(Target.project_id == project_id)
    stmt = stmt.order_by(col(Target.updated_at).desc()).limit(limit)
    return list(session.exec(stmt).all())


def update_target_status(session: Session, target: Target, status: str) -> Target:
    target.status = status
    target.updated_at = datetime.now(UTC)
    session.add(target)
    session.commit()
    session.refresh(target)
    return target


def create_target_link(
    session: Session,
    source_target_id: str,
    url: str,
    kind: str = "unknown",
    relationship: str = "unknown",
    confidence: float | None = None,
    status: str = "discovered",
    reason_code: str | None = None,
) -> TargetLink:
    link = TargetLink(
        source_target_id=source_target_id,
        url=url,
        kind=kind,
        relationship=relationship,
        confidence=confidence,
        status=status,
        reason_code=reason_code,
    )
    session.add(link)
    session.commit()
    session.refresh(link)
    return link


def get_existing_target_link(
    session: Session, source_target_id: str, url: str
) -> TargetLink | None:
    stmt = (
        select(TargetLink)
        .where(TargetLink.source_target_id == source_target_id)
        .where(TargetLink.url == url)
    )
    return session.exec(stmt).first()


def create_child_target_from_link(
    session: Session,
    link: TargetLink,
    project_id: str | None,
    kind: str = "website",
    priority: str = "medium",
    status: str = "queued",
) -> Target:
    tgt = create_target(
        session=session,
        project_id=project_id,
        title=link.url,
        url=link.url,
        kind=kind,
        priority=priority,
        status=status,
        parent_target_id=link.source_target_id,
    )
    link.target_id = tgt.target_id
    link.status = "queued"
    session.add(link)
    session.commit()
    session.refresh(link)
    return tgt


def find_watch_by_cd_uuid(session: Session, cd_uuid: str) -> Watch | None:
    stmt = select(Watch).where(Watch.changedetection_uuid == cd_uuid)
    return session.exec(stmt).first()


def get_or_create_watch(session: Session, target_id: str) -> Watch:
    stmt = select(Watch).where(Watch.target_id == target_id)
    w = session.exec(stmt).first()
    if w:
        return w
    w = Watch(target_id=target_id)
    session.add(w)
    session.commit()
    session.refresh(w)
    return w


def get_watch_by_target_id(session: Session, target_id: str) -> Watch | None:
    stmt = select(Watch).where(Watch.target_id == target_id)
    return session.exec(stmt).first()


def update_watch_uuid(session: Session, watch: Watch, cd_uuid: str) -> Watch:
    watch.changedetection_uuid = cd_uuid
    watch.status = "active"
    watch.last_sync_at = datetime.now(UTC)
    watch.last_error = None
    session.add(watch)
    session.commit()
    session.refresh(watch)
    return watch


def mark_watch_failed(session: Session, watch: Watch, error: str) -> Watch:
    watch.status = "sync_failed"
    watch.last_error = error
    watch.last_sync_at = datetime.now(UTC)
    session.add(watch)
    session.commit()
    session.refresh(watch)
    return watch


def mark_watch_removed_or_inactive(
    session: Session, watch: Watch, status: str
) -> Watch:
    watch.changedetection_uuid = None
    watch.status = status
    watch.last_sync_at = datetime.now(UTC)
    watch.last_error = None
    session.add(watch)
    session.commit()
    session.refresh(watch)
    return watch


def create_signal(
    session: Session,
    target_id: str | None = None,
    watch_id: str | None = None,
    changedetection_uuid: str | None = None,
    category: str | None = None,
    priority: str | None = None,
    diff_hash: str | None = None,
    title: str | None = None,
    summary: str | None = None,
    raw_excerpt: str | None = None,
    url: str | None = None,
) -> Signal:
    sig = Signal(
        target_id=target_id,
        watch_id=watch_id,
        changedetection_uuid=changedetection_uuid,
        category=category,
        priority=priority,
        diff_hash=diff_hash,
        title=title,
        summary=summary,
        raw_excerpt=raw_excerpt,
        url=url,
    )
    session.add(sig)
    session.commit()
    session.refresh(sig)
    return sig


def find_signal_by_target_and_hash(
    session: Session, target_id: str, diff_hash: str
) -> Signal | None:
    stmt = (
        select(Signal)
        .where(Signal.target_id == target_id)
        .where(Signal.diff_hash == diff_hash)
    )
    return session.exec(stmt).first()


def write_audit_log(
    session: Session,
    action: str,
    actor_telegram_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    payload: dict | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_telegram_id=actor_telegram_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        payload_json=json.dumps(payload) if payload else None,
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def _require_mapping(value: object, path: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be a mapping")
    return value


def _require_list(value: object, path: str) -> list:
    if not isinstance(value, list):
        raise ValueError(f"{path} must be a list")
    return value


def _require_string(value: object, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path} must be a non-empty string")
    return value.strip()


def _optional_string(value: object, default: str, path: str) -> str:
    if value is None:
        return default
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path} must be a non-empty string")
    return value.strip()


def _optional_string_list(value: object, path: str) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValueError(f"{path} must be a list of strings")
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise ValueError(f"{path}[{index}] must be a string")
    return value


def _validate_http_url(value: object, path: str) -> str:
    url = _require_string(value, path)
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
        raise ValueError(f"{path} must be an http or https URL with host")
    return url


def import_seed_yaml(session: Session, yaml_path: Path) -> int:
    with yaml_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    data = _require_mapping(data, "seed")

    ws_data = _require_mapping(data.get("workspace"), "seed.workspace")
    ws_name = _require_string(ws_data.get("name"), "seed.workspace.name")

    ws = get_or_create_workspace(
        session, ws_name, description=ws_data.get("description", "")
    )

    projects_data = _require_list(data.get("projects"), "seed.projects")

    total = 0
    for project_index, proj_item_raw in enumerate(projects_data):
        project_path = f"seed.projects[{project_index}]"
        proj_item = _require_mapping(proj_item_raw, project_path)
        homepage_url = None
        homepage_url_raw = proj_item.get("homepage_url")
        if homepage_url_raw not in (None, ""):
            homepage_url = _validate_http_url(
                homepage_url_raw, f"{project_path}.homepage_url"
            )
        proj = get_or_create_project(
            session,
            ws.workspace_id,
            name=_require_string(proj_item.get("name"), f"{project_path}.name"),
            homepage_url=homepage_url,
            tags=_optional_string_list(proj_item.get("tags"), f"{project_path}.tags"),
        )
        targets_data = _require_list(
            proj_item.get("targets"), f"{project_path}.targets"
        )
        for target_index, tgt_item_raw in enumerate(targets_data):
            target_path = f"{project_path}.targets[{target_index}]"
            tgt_item = _require_mapping(tgt_item_raw, target_path)
            _, created = get_or_create_target(
                session,
                proj.project_id,
                title=_require_string(tgt_item.get("title"), f"{target_path}.title"),
                url=_validate_http_url(tgt_item.get("url"), f"{target_path}.url"),
                kind=_require_string(tgt_item.get("kind"), f"{target_path}.kind"),
                priority=_require_string(
                    tgt_item.get("priority"), f"{target_path}.priority"
                ),
                status=_optional_string(
                    tgt_item.get("status"), "queued", f"{target_path}.status"
                ),
                fetch_backend=_optional_string(
                    tgt_item.get("fetch_backend"),
                    "html_requests",
                    f"{target_path}.fetch_backend",
                ),
            )
            if created:
                total += 1

    write_audit_log(
        session,
        action="import_seed",
        entity_type="workspace",
        entity_id=ws.workspace_id,
        payload={"path": str(yaml_path), "targets_created": total},
    )
    return total


def export_workspace_to_yaml(
    session: Session, workspace_name: str, output_path: Path
) -> Path:
    stmt = select(Workspace).where(Workspace.name == workspace_name)
    ws = session.exec(stmt).first()
    if not ws:
        raise ValueError(f"Workspace {workspace_name!r} not found")

    stmt = select(Project).where(Project.workspace_id == ws.workspace_id)
    projects = session.exec(stmt).all()

    export_data: dict = {
        "workspace": {
            "name": ws.name,
            "description": ws.description or "",
        },
        "projects": [],
    }

    for proj in projects:
        tags = json.loads(proj.tags_json or "[]")
        stmt_t = select(Target).where(Target.project_id == proj.project_id)
        targets = session.exec(stmt_t).all()

        proj_data = {
            "name": proj.name,
            "homepage_url": proj.homepage_url or "",
            "tags": tags,
            "targets": [],
        }
        for tgt in targets:
            proj_data["targets"].append(
                {
                    "title": tgt.title,
                    "url": tgt.url,
                    "kind": tgt.kind,
                    "priority": tgt.priority,
                    "status": tgt.status,
                    "fetch_backend": tgt.fetch_backend,
                }
            )
        export_data["projects"].append(proj_data)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        yaml.dump(export_data, f, default_flow_style=False, allow_unicode=True)

    write_audit_log(
        session,
        action="export_seed",
        entity_type="workspace",
        entity_id=ws.workspace_id,
        payload={"path": str(output_path)},
    )
    return output_path


def upsert_telegram_subscriber(
    session: Session,
    telegram_user_id: str,
    chat_id: str,
    role: str = "operator",
    username: str | None = None,
    first_name: str | None = None,
) -> TelegramSubscriber:
    stmt = select(TelegramSubscriber).where(
        TelegramSubscriber.telegram_user_id == telegram_user_id
    )
    sub = session.exec(stmt).first()
    if sub:
        sub.chat_id = chat_id
        sub.username = username
        sub.first_name = first_name
        sub.role = role
        sub.is_active = True
        sub.updated_at = datetime.now(UTC)
        session.add(sub)
        session.commit()
        session.refresh(sub)
        return sub
    sub = TelegramSubscriber(
        telegram_user_id=telegram_user_id,
        chat_id=chat_id,
        role=role,
        username=username,
        first_name=first_name,
        is_active=True,
    )
    session.add(sub)
    session.commit()
    session.refresh(sub)
    return sub


def deactivate_telegram_subscriber(
    session: Session, telegram_user_id: str
) -> TelegramSubscriber | None:
    stmt = select(TelegramSubscriber).where(
        TelegramSubscriber.telegram_user_id == telegram_user_id
    )
    sub = session.exec(stmt).first()
    if not sub:
        return None
    sub.is_active = False
    sub.updated_at = datetime.now(UTC)
    session.add(sub)
    session.commit()
    session.refresh(sub)
    return sub


def get_telegram_subscriber_by_user_id(
    session: Session, telegram_user_id: str
) -> TelegramSubscriber | None:
    stmt = select(TelegramSubscriber).where(
        TelegramSubscriber.telegram_user_id == telegram_user_id
    )
    return session.exec(stmt).first()


def list_active_telegram_subscribers(
    session: Session,
) -> list[TelegramSubscriber]:
    stmt = (
        select(TelegramSubscriber)
        .where(col(TelegramSubscriber.is_active))
        .order_by(col(TelegramSubscriber.created_at))
    )
    return list(session.exec(stmt).all())


def list_telegram_subscribers(
    session: Session,
) -> list[TelegramSubscriber]:
    stmt = select(TelegramSubscriber).order_by(
        col(TelegramSubscriber.is_active).desc(),
        col(TelegramSubscriber.created_at),
    )
    return list(session.exec(stmt).all())
