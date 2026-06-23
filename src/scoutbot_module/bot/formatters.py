from __future__ import annotations

from typing import Any


def format_add_result(result: dict[str, Any]) -> str:
    lines = [
        "✅ Target added",
        "",
        f"Project: {result.get('project_name', 'N/A')}",
        f"Title: {result.get('title', 'N/A')}",
        f"URL: {result.get('url', 'N/A')}",
        f"Kind: {result.get('kind', 'website')}",
        f"Status: {result.get('status', 'queued')}",
        f"ID: {result.get('target_id', '')}",
    ]
    if result.get("links_found"):
        lines.append(f"Links found: {result['links_found']}")
    if result.get("children_created"):
        lines.append(f"Child targets: {result['children_created']}")
    if result.get("sync_status"):
        lines.append(f"Sync: {result['sync_status']}")
    return "\n".join(lines)


def format_projects_list(projects: list[dict[str, Any]]) -> str:
    if not projects:
        return "No projects found."

    lines = ["Projects:"]
    for p in projects:
        url = p.get("homepage_url", "")
        line = f"• {p['name']}"
        if url:
            line += f" — {url}"
        lines.append(line)
    return "\n".join(lines)


def format_targets_list(targets: list[dict[str, Any]]) -> str:
    if not targets:
        return "No targets found."

    status_emoji = {
        "active": "🟢",
        "queued": "🟡",
        "paused": "⏸",
        "deleted": "🗑",
        "degraded": "⚠",
    }

    lines = ["Recent targets:"]
    for t in targets:
        emoji = status_emoji.get(t.get("status", ""), "❓")
        lines.append(
            f"{emoji} {t['title']} [{t.get('kind', '?')}]"
            f"\n   {t['target_id']} — {t['url']}"
        )
    return "\n".join(lines)


def format_signal_alert(
    signal: dict[str, Any],
    target_info: dict[str, Any] | None = None,
) -> str:
    project = (target_info or {}).get("project_name", "Unknown")
    target_title = (target_info or {}).get("title", signal.get("url", "Unknown"))
    category = str(signal.get("category") or "unknown")
    priority = str(signal.get("priority") or "low")
    url = str(signal.get("url") or "")
    summary = str(signal.get("summary") or "No summary available")

    lines = [
        "🚨 ScoutBot alert",
        "",
        f"Project: {project}",
        f"Target: {target_title}",
        f"Category: {category}",
        f"Priority: {priority}",
    ]
    if url:
        lines.append(f"URL: {url}")
    lines.append("")
    lines.append("Summary:")
    lines.append(summary[:500])

    return "\n".join(lines)
