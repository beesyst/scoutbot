from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from scoutbot_module.discovery.kinds import normalize_source_url, resolve_kind

LOG = logging.getLogger("scoutbot.discovery.links")


def extract_links(
    html: str,
    base_url: str,
    max_links: int = 30,
) -> list[dict[str, Any]]:
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    base_domain = urlparse(base_url).hostname or ""
    links: dict[str, dict[str, Any]] = {}
    for tag in soup.find_all("a", href=True):
        href = str(tag.get("href", "")).strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)
        if parsed.scheme not in ("http", "https"):
            continue
        if full_url in links:
            continue
        if len(links) >= max_links:
            break

        kind, relationship, confidence = _classify_link(full_url, base_domain)
        links[full_url] = {
            "url": normalize_source_url(full_url),
            "kind": kind,
            "relationship": relationship,
            "confidence": confidence,
            "source": "a_href",
        }

    _add_common_pages(base_url, base_domain, links, max_links)

    return list(links.values())[:max_links]


def _add_common_pages(
    base_url: str,
    base_domain: str,
    links: dict[str, dict[str, Any]],
    max_links: int,
) -> None:
    common_paths = [
        ("/blog", "blog", "same_domain"),
        ("/news", "blog", "same_domain"),
        ("/docs", "docs", "same_domain"),
        ("/documentation", "docs", "same_domain"),
        ("/changelog", "changelog", "same_domain"),
        ("/careers", "careers", "same_domain"),
        ("/pricing", "pricing", "same_domain"),
        ("/services", "pricing", "same_domain"),
        ("/sitemap.xml", "website", "sitemap"),
    ]
    for path, kind, relationship in common_paths:
        if len(links) >= max_links:
            break
        url = urljoin(base_url, path)
        if url not in links:
            links[url] = {
                "url": url,
                "kind": kind,
                "relationship": relationship,
                "confidence": 0.9,
                "source": (
                    "sitemap_candidate" if path == "/sitemap.xml" else "common_path"
                ),
            }


def _classify_link(url: str, base_domain: str) -> tuple[str, str, float]:
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    path = parsed.path.lower()
    same_domain = hostname == base_domain

    if hostname == "github.com" or hostname == "t.me" or hostname.endswith(".t.me"):
        kind_info = resolve_kind(url)
        return (
            str(kind_info["kind"]),
            "social",
            float(kind_info["confidence"]),
        )

    if "youtube.com" in hostname or "youtu.be" in hostname:
        return "social_profile", "social", 0.7

    if hostname in ("x.com", "twitter.com"):
        return "social_profile", "social", 0.7

    if path.endswith((".xml", ".rss", ".atom")) or "rss" in path or "feed" in path:
        return "rss", "rss", 0.85

    if "sitemap" in path and path.endswith(".xml"):
        return "website", "sitemap", 0.9

    if hostname in ("linktr.ee", "bio.link", "beacons.ai", "campsite.bio"):
        return "link_aggregator", "link_aggregator_child", 0.6

    if same_domain:
        for pattern, kind in [
            ("/blog", "blog"),
            ("/news", "blog"),
            ("/docs", "docs"),
            ("/documentation", "docs"),
            ("/changelog", "changelog"),
            ("/careers", "careers"),
            ("/pricing", "pricing"),
            ("/services", "pricing"),
        ]:
            if pattern in path:
                return kind, "same_domain", 0.9
        return "website", "same_domain", 0.7

    return "custom", "unknown", 0.3
