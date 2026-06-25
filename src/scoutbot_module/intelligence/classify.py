from __future__ import annotations

from typing import Any


def classify_signal(
    payload: dict[str, Any],
    categories: dict[str, list[str]],
    priority_config: dict[str, list[str]] | None = None,
    noise_ignore_text: list[str] | None = None,
) -> dict[str, Any]:
    text = _extract_text(payload)
    url = str(payload.get("url", "")).lower()
    title = str(payload.get("title", "")).lower()

    combined = f"{title} {text} {url}".lower()

    matched_keywords: list[str] = []
    reason_code: str = "unknown"

    if noise_ignore_text:
        for phrase in noise_ignore_text:
            if phrase.lower() in combined:
                matched_keywords.append(phrase)
        if matched_keywords:
            return {
                "category": "noise",
                "priority": "low",
                "matched_keywords": matched_keywords,
                "reason_code": "noise_rule",
                "title": title or "Noise",
            }

    category_order = [
        "pricing",
        "delegation",
        "validator_network",
        "product",
        "positioning",
        "hiring",
        "legal",
        "social",
    ]

    for cat in category_order:
        keywords = categories.get(cat, [])
        for kw in keywords:
            if kw.lower() in combined:
                matched_keywords.append(kw)
        if matched_keywords:
            priority = _resolve_priority(cat, priority_config)
            reason_code = "keyword_match"
            if cat == "social":
                reason_code = "social_source"
            return {
                "category": cat,
                "priority": priority,
                "matched_keywords": matched_keywords,
                "reason_code": reason_code,
                "title": title or f"{cat.capitalize()} update",
            }

    social_domains = [
        "t.me",
        "github.com",
        "youtube.com",
        "youtu.be",
        "x.com",
        "twitter.com",
        "linkedin.com",
        "discord.gg",
        "medium.com",
        "reddit.com",
    ]
    if any(domain in url for domain in social_domains):
        return {
            "category": "social",
            "priority": _resolve_priority("social", priority_config),
            "matched_keywords": [],
            "reason_code": "social_source",
            "title": title or "Social update",
        }

    return {
        "category": "unknown",
        "priority": "low",
        "matched_keywords": [],
        "reason_code": "unknown",
        "title": title or "Change detected",
    }


def _resolve_priority(
    category: str, priority_config: dict[str, list[str]] | None
) -> str:
    if priority_config:
        if category in priority_config.get("high_categories", []):
            return "high"
        if category in priority_config.get("medium_categories", []):
            return "medium"
    return "low"


def _extract_text(payload: dict[str, Any]) -> str:
    text = payload.get("text") or payload.get("diff") or payload.get("summary") or ""
    if not isinstance(text, str):
        text = str(text)
    return text
