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
    auto_queue = discovery_cfg["auto_queue"]
    allowed_kinds = discovery_cfg["allowed_kinds"]
    require_confirmation = discovery_cfg["require_confirmation_kinds"]
    conf_min = discovery_cfg["conf_min"]

    links_stored = 0
    children_created = 0
    child_targets: list[dict[str, Any]] = []
    degraded_sources: list[dict[str, Any]] = []

    for link_info in result.get("links", []):
        link_url = link_info["url"]
        link_kind = link_info.get("kind", "unknown")
        relationship = link_info.get("relationship", "unknown")
        confidence = link_info.get("confidence", None)
        reason_code = link_info.get("reason_code") or link_info.get("source")

        from scoutbot_module.services.targets import store_target_link

        stored = store_target_link(
            session=session,
            source_target_id=target_id,
            url=link_url,
            kind=link_kind,
            relationship=relationship,
            confidence=confidence,
            status="discovered",
            reason_code=reason_code,
        )
        if stored["created"]:
            links_stored += 1

        can_auto_queue = (
            auto_queue
            and link_kind in allowed_kinds
            and link_kind not in require_confirmation
            and (confidence is None or confidence >= conf_min)
        )

        if can_auto_queue:
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

                new_tgt = create_child_target_from_link(
                    session=session,
                    link=existing_link,
                    project_id=project_id,
                    kind=link_kind,
                    priority="medium",
                    status="queued",
                )
                children_created += 1
                child_targets.append(
                    {
                        "target_id": new_tgt.target_id,
                        "parent_target_id": target_id,
                        "url": link_url,
                        "kind": link_kind,
                        "status": "queued",
                    }
                )
        elif (
            auto_queue
            and link_kind in allowed_kinds
            and link_kind in require_confirmation
        ):
            pass
        elif auto_queue and confidence is not None and confidence < conf_min:
            pass

    error = result.get("error")
    if error:
        degraded_mapping: dict[str, str] = {
            "timeout": "timeout",
            "fetch_error": "blocked",
            "http_401": "auth_required",
            "http_403": "blocked",
            "http_429": "anti_bot",
            "too_large": "too_large",
        }
        degraded_status = degraded_mapping.get(error, "blocked")
        degraded_sources.append(
            {
                "url": result.get("url", ""),
                "kind": result.get("kind", "custom"),
                "status": degraded_status,
                "reason_code": error,
            }
        )

    for degraded in result.get("degraded", []):
        degraded_sources.append(degraded)
        from scoutbot_module.services.targets import store_target_link

        stored = store_target_link(
            session=session,
            source_target_id=target_id,
            url=degraded.get("url", result.get("url", "")),
            kind=degraded.get("kind", "custom"),
            relationship="degraded",
            confidence=degraded.get("confidence"),
            status="degraded",
            reason_code=degraded.get("reason_code"),
        )
        if stored["created"]:
            links_stored += 1

    _write_discovery_artifacts(
        storage_root, target_id, result, child_targets, degraded_sources
    )

    return {
        "target_id": target_id,
        "links_found": len(result.get("links", [])),
        "links_stored": links_stored,
        "children_created": children_created,
    }


def _write_discovery_artifacts(
    storage_root: str,
    target_id: str,
    result: dict,
    child_targets: list[dict[str, Any]] | None = None,
    degraded_sources: list[dict[str, Any]] | None = None,
) -> None:
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

    source_url = result.get("url", "")
    source_links = result.get("links", [])

    graph_links = []
    for link in source_links:
        graph_links.append(
            {
                "link_id": link.get("url", ""),
                "url": link.get("url", ""),
                "kind": link.get("kind", "unknown"),
                "relationship": link.get("relationship", "unknown"),
                "confidence": link.get("confidence"),
                "status": "discovered",
                "reason_code": link.get("source", "discovered"),
            }
        )

    graph_path = disc_dir / "source_graph.json"
    with graph_path.open("w", encoding="utf-8") as f:
        payload = {
            "root_target": {
                "target_id": target_id,
                "url": source_url,
                "kind": result.get("kind", "website"),
                "status": "active",
            },
            "links": graph_links,
            "child_targets": child_targets or [],
        }
        json.dump(payload, f, indent=2, ensure_ascii=False)

    if degraded_sources:
        degraded_path = disc_dir / "degraded_sources.json"
        with degraded_path.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "target_id": target_id,
                    "sources": degraded_sources,
                },
                f,
                indent=2,
                ensure_ascii=False,
            )
