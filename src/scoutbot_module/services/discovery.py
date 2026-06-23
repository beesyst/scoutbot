from __future__ import annotations

import logging
from typing import Any

from sqlmodel import Session

LOG = logging.getLogger("scoutbot.services.discovery")


def run_bounded_discovery(
    session: Session,
    target_id: str,
    url: str,
    settings: dict,
    storage_root: str,
) -> dict:
    from scoutbot_module.discovery.service import discover

    result = discover(url=url, settings=settings)
    return _persist_discovery_result(
        session=session,
        target_id=target_id,
        result=result,
        settings=settings,
        storage_root=storage_root,
    )


async def run_bounded_discovery_async(
    session: Session,
    target_id: str,
    url: str,
    settings: dict,
    storage_root: str,
) -> dict[str, Any]:
    from scoutbot_module.discovery.service import discover_async

    result = await discover_async(url=url, settings=settings)
    return _persist_discovery_result(
        session=session,
        target_id=target_id,
        result=result,
        settings=settings,
        storage_root=storage_root,
    )


def _persist_discovery_result(
    session: Session,
    target_id: str,
    result: dict[str, Any],
    settings: dict,
    storage_root: str,
) -> dict[str, Any]:
    discovery_cfg = settings["discovery"]

    links_stored = 0
    children_created = 0

    for link_info in result.get("links", []):
        link_url = link_info["url"]
        link_kind = link_info.get("kind", "unknown")
        relationship = link_info.get("relationship", "unknown")
        confidence = link_info.get("confidence", None)

        from scoutbot_module.services.targets import store_target_link

        stored = store_target_link(
            session=session,
            source_target_id=target_id,
            url=link_url,
            kind=link_kind,
            relationship=relationship,
            confidence=confidence,
            status="discovered",
        )
        if stored["created"]:
            links_stored += 1

        auto_queue = discovery_cfg["auto_queue"]
        allowed_kinds = discovery_cfg["allowed_kinds"]
        require_confirmation = discovery_cfg["require_confirmation_kinds"]

        if auto_queue and link_kind in allowed_kinds:
            if link_kind not in require_confirmation:
                from scoutbot_module.db.repo import (
                    create_child_target_from_link,
                    get_existing_target_link,
                )

                existing_link = get_existing_target_link(session, target_id, link_url)
                if existing_link and not existing_link.target_id:
                    from sqlmodel import select

                    from scoutbot_module.db.models import Target

                    tgt = session.exec(
                        select(Target).where(Target.target_id == target_id)
                    ).first()
                    project_id = tgt.project_id if tgt else None

                    create_child_target_from_link(
                        session=session,
                        link=existing_link,
                        project_id=project_id,
                        kind=link_kind,
                        priority="medium",
                        status="queued",
                    )
                    children_created += 1

    _write_discovery_artifacts(storage_root, target_id, result)

    return {
        "target_id": target_id,
        "links_found": len(result.get("links", [])),
        "links_stored": links_stored,
        "children_created": children_created,
    }


def _write_discovery_artifacts(storage_root: str, target_id: str, result: dict) -> None:
    import json
    from datetime import UTC, datetime
    from pathlib import Path

    run_id = f"disc_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
    disc_dir = Path(storage_root) / "discovery" / run_id
    disc_dir.mkdir(parents=True, exist_ok=True)

    links_path = disc_dir / "discovered_links.json"
    with links_path.open("w", encoding="utf-8") as f:
        json.dump(
            {"target_id": target_id, "links": result.get("links", [])},
            f,
            indent=2,
            ensure_ascii=False,
        )

    graph_path = disc_dir / "source_graph.json"
    with graph_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "target_id": target_id,
                "url": result.get("url"),
                "links": result.get("links", []),
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
