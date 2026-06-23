from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

LOG = logging.getLogger("scoutbot.discovery.feeds")


def extract_feeds(html: str, base_url: str) -> list[dict[str, Any]]:
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    feeds: list[dict[str, Any]] = []

    for tag in soup.find_all("link"):
        rel = tag.get("rel") or []
        if isinstance(rel, list):
            rel = " ".join(rel).lower()
        else:
            rel = str(rel).lower()

        link_type = str(tag.get("type", "")).lower()
        href = str(tag.get("href", "")).strip()

        if not href:
            continue

        if "alternate" in rel and any(
            t in link_type for t in ("rss", "atom", "xml", "feed")
        ):
            full_url = urljoin(base_url, href)
            feeds.append(
                {
                    "url": full_url,
                    "kind": "rss",
                    "relationship": "rss",
                    "confidence": 0.9,
                    "source": "link_rel_alternate",
                }
            )

    return feeds
