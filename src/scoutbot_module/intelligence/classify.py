from __future__ import annotations

from typing import Any


def classify_signal(
    payload: dict[str, Any],
    categories: dict[str, list[str]],
) -> dict[str, Any]:
    text = _extract_text(payload)
    url = str(payload.get("url", "")).lower()
    title = str(payload.get("title", "")).lower()

    combined = f"{title} {text} {url}".lower()

    pricing_keywords = categories["pricing"]
    if any(kw in combined for kw in pricing_keywords):
        return {
            "category": "pricing",
            "priority": "high",
            "title": title or "Pricing change",
        }

    delegation_keywords = categories["delegation"]
    if any(kw in combined for kw in delegation_keywords):
        return {
            "category": "delegation",
            "priority": "high",
            "title": title or "Delegation update",
        }

    product_keywords = categories["product"]
    if any(kw in combined for kw in product_keywords):
        return {
            "category": "product",
            "priority": "medium",
            "title": title or "Product update",
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
            "priority": "medium",
            "title": title or "Social update",
        }

    return {
        "category": "unknown",
        "priority": "low",
        "title": title or "Change detected",
    }


def _extract_text(payload: dict[str, Any]) -> str:
    text = payload.get("text") or payload.get("diff") or payload.get("summary") or ""
    if not isinstance(text, str):
        text = str(text)
    return text
