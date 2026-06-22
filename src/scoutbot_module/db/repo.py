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
    Target,
    Watch,
    Workspace,
)


# Поиск или создание Workspace
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


# Список всех Workspaces
def list_workspaces(session: Session) -> list[Workspace]:
    return list(session.exec(select(Workspace)).all())


# Поиск или создание Project
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


# Список проектов по статусу
def create_target(
    session: Session,
    project_id: str | None,
    title: str,
    url: str,
    kind: str = "website",
    priority: str = "medium",
    status: str = "queued",
    fetch_backend: str = "html_requests",
) -> Target:
    tgt = Target(
        project_id=project_id,
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


# Поиск или создание Target
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


# Список целей по статусу
def list_targets_by_status(session: Session, statuses: tuple[str, ...]) -> list[Target]:
    stmt = select(Target).where(col(Target.status).in_(statuses))
    return list(session.exec(stmt).all())


# Поиск или создание Watch для цели
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


# Обновление Watch с UUID от changedetection и активация
def update_watch_uuid(session: Session, watch: Watch, cd_uuid: str) -> Watch:
    watch.changedetection_uuid = cd_uuid
    watch.status = "active"
    watch.last_sync_at = datetime.now(UTC)
    watch.last_error = None
    session.add(watch)
    session.commit()
    session.refresh(watch)
    return watch


# Пометка Watch как синхронизационной ошибки
def mark_watch_failed(session: Session, watch: Watch, error: str) -> Watch:
    watch.status = "sync_failed"
    watch.last_error = error
    watch.last_sync_at = datetime.now(UTC)
    session.add(watch)
    session.commit()
    session.refresh(watch)
    return watch


# Запись события в AuditLog
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


# Проверка YAML mapping
def _require_mapping(value: object, path: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be a mapping")
    return value


# Проверка YAML list
def _require_list(value: object, path: str) -> list:
    if not isinstance(value, list):
        raise ValueError(f"{path} must be a list")
    return value


# Обязательная непустая строка
def _require_string(value: object, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path} must be a non-empty string")
    return value.strip()


# Optional непустая строка с default
def _optional_string(value: object, default: str, path: str) -> str:
    if value is None:
        return default
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path} must be a non-empty string")
    return value.strip()


# Optional список строк
def _optional_string_list(value: object, path: str) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValueError(f"{path} must be a list of strings")
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise ValueError(f"{path}[{index}] must be a string")
    return value


# Валидация URL для передачи в changedetection.io
def _validate_http_url(value: object, path: str) -> str:
    url = _require_string(value, path)
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
        raise ValueError(f"{path} must be an http or https URL with host")
    return url


# Импорт из seed YAML
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


# Экспорт в seed YAML
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
