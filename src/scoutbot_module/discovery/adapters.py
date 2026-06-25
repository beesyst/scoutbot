from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from scoutbot_module.discovery.feeds import extract_feeds
from scoutbot_module.discovery.fetch import fetch_page
from scoutbot_module.discovery.kinds import (
    derive_github_changelog_candidates,
    derive_github_releases_atom,
    derive_github_releases_url,
    is_private_or_invite_telegram,
    normalize_source_url,
    resolve_kind,
)
from scoutbot_module.discovery.links import extract_links
from scoutbot_module.discovery.socials import extract_socials
from scoutbot_module.discovery.urls import normalize_url, validate_url


async def run_source_adapters(url: str, settings: dict) -> dict[str, Any]:
    discovery_cfg = settings["discovery"]
    allow_private = discovery_cfg["allow_private_networks"]
    max_links = discovery_cfg["target_links_max"]
    timeout = discovery_cfg["request_timeout"]
    max_bytes = discovery_cfg["max_response_bytes"]

    validate_url(url, allow_private_networks=allow_private)

    kind_info = resolve_kind(url)
    normalized_url = normalize_source_url(url, kind_info)
    result: dict[str, Any] = {
        "url": normalized_url,
        "input_url": url,
        "kind": str(kind_info["kind"]),
        "kind_confidence": float(kind_info["confidence"]),
        "kind_reason_code": str(kind_info["reason_code"]),
        "links": [],
        "degraded": [],
    }

    if is_private_or_invite_telegram(kind_info):
        result["degraded"].append(
            {
                "url": url,
                "kind": str(kind_info["kind"]),
                "status": "degraded",
                "reason_code": str(kind_info["reason_code"]),
                "confidence": float(kind_info["confidence"]),
            }
        )
        return result

    if result["kind"] == "rss":
        return result

    if str(result["kind"]).startswith("github"):
        if str(result["kind"]).startswith("github"):
            releases_url = derive_github_releases_url(normalized_url)
            releases_atom = derive_github_releases_atom(normalized_url)
            candidates = []
            if releases_url:
                candidates.append(
                    _make_link(
                        url=releases_url,
                        kind="github_releases",
                        relationship="official",
                        confidence=0.9,
                        source="github_adapter",
                    )
                )
            if releases_atom:
                candidates.append(
                    _make_link(
                        url=releases_atom,
                        kind="rss",
                        relationship="official",
                        confidence=0.85,
                        source="github_adapter",
                    )
                )
            for candidate in derive_github_changelog_candidates(normalized_url):
                candidates.append(
                    _make_link(
                        url=candidate,
                        kind="github_changelog",
                        relationship="official",
                        confidence=0.6,
                        source="github_adapter_guess",
                    )
                )
            _extend_unique_links(result["links"], candidates, max_links)
        releases_url = derive_github_releases_url(normalized_url)
        releases_atom = derive_github_releases_atom(normalized_url)
        candidates = []
        if releases_url:
            candidates.append(
                _make_link(
                    url=releases_url,
                    kind="github_releases",
                    relationship="official",
                    confidence=0.9,
                    source="github_adapter",
                )
            )
        if releases_atom:
            candidates.append(
                _make_link(
                    url=releases_atom,
                    kind="rss",
                    relationship="official",
                    confidence=0.85,
                    source="github_adapter",
                )
            )
        for candidate in derive_github_changelog_candidates(normalized_url):
            candidates.append(
                _make_link(
                    url=candidate,
                    kind="github_changelog",
                    relationship="official",
                    confidence=0.6,
                    source="github_adapter_guess",
                )
            )
        _extend_unique_links(result["links"], candidates, max_links)

    if result["kind"] == "telegram_public":
        return result

    fetch_result = await fetch_page(
        url=normalized_url,
        timeout=timeout,
        max_response_bytes=max_bytes,
        allow_private_networks=allow_private,
    )
    if fetch_result.get("error"):
        result["degraded"].append(
            {
                "url": normalized_url,
                "kind": str(result["kind"]),
                "status": "degraded",
                "reason_code": fetch_result["error"],
            }
        )
        return result

    actual_url = str(fetch_result.get("url") or normalized_url)
    content_type = str(fetch_result.get("content_type") or "").lower()
    html = str(fetch_result.get("html") or "")
    result["url"] = normalize_source_url(actual_url)

    if _is_feed_content_type(content_type) and result["kind"] != "rss":
        result["kind"] = "rss"
        _extend_unique_links(
            result["links"],
            [
                _make_link(
                    url=result["url"],
                    kind="rss",
                    relationship="official",
                    confidence=0.95,
                    source="content_type_hint",
                )
            ],
            max_links,
        )
        return result

    if html:
        extracted = _extract_public_links(
            html, result["url"], max_links, result["kind"]
        )
        _extend_unique_links(result["links"], extracted, max_links)

    if not result["links"] and result["kind"] in {"website", "blog", "docs", "pricing"}:
        result["degraded"].append(
            {
                "url": result["url"],
                "kind": str(result["kind"]),
                "status": "degraded",
                "reason_code": "no_links_found",
            }
        )

    return result


def _extract_public_links(
    html: str,
    base_url: str,
    max_links: int,
    root_kind: str,
) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    if root_kind == "link_aggregator":
        _extend_unique_links(
            links, _extract_aggregator_links(html, base_url, max_links), max_links
        )
    else:
        _extend_unique_links(links, extract_feeds(html, base_url), max_links)
        _extend_unique_links(links, extract_socials(html, base_url), max_links)
        _extend_unique_links(
            links, extract_links(html, base_url, max_links=max_links), max_links
        )
        _extend_unique_links(links, _extract_html_head_links(html, base_url), max_links)
    return links[:max_links]


def _extract_aggregator_links(
    html: str,
    base_url: str,
    max_links: int,
) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    links: list[dict[str, Any]] = []
    for tag in soup.find_all("a", href=True):
        href = str(tag.get("href", "")).strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        full_url = urljoin(base_url, href)
        safe_link = _safe_outbound_link(full_url)
        if safe_link is None:
            continue
        kind_info = resolve_kind(safe_link)
        links.append(
            _make_link(
                url=normalize_source_url(safe_link, kind_info),
                kind=str(kind_info["kind"]),
                relationship="link_aggregator_child",
                confidence=float(kind_info["confidence"]),
                source="link_aggregator_adapter",
                reason_code=str(kind_info["reason_code"]),
            )
        )
        if len(links) >= max_links:
            break
    return links


def _extract_html_head_links(html: str, base_url: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    links: list[dict[str, Any]] = []
    for tag in soup.find_all("link", href=True):
        href = str(tag.get("href", "")).strip()
        if not href:
            continue
        full_url = urljoin(base_url, href)
        safe_link = _safe_outbound_link(full_url)
        if safe_link is None:
            continue
        kind_info = resolve_kind(safe_link)
        if str(kind_info["kind"]) == "website":
            continue
        links.append(
            _make_link(
                url=normalize_source_url(safe_link, kind_info),
                kind=str(kind_info["kind"]),
                relationship="head_link",
                confidence=float(kind_info["confidence"]),
                source="html_head_link",
                reason_code=str(kind_info["reason_code"]),
            )
        )
    return links


def _extend_unique_links(
    target: list[dict[str, Any]],
    candidates: Iterable[dict[str, Any]],
    max_links: int,
) -> None:
    seen = {item["url"] for item in target}
    for candidate in candidates:
        url = str(candidate.get("url") or "").strip()
        if not url or url in seen:
            continue
        target.append(candidate)
        seen.add(url)
        if len(target) >= max_links:
            break


def _safe_outbound_link(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return None
    try:
        validate_url(url, allow_private_networks=False)
    except ValueError:
        return None
    return normalize_url(url)


def _is_feed_content_type(content_type: str) -> bool:
    return any(
        marker in content_type
        for marker in (
            "application/rss+xml",
            "application/atom+xml",
            "application/xml",
            "text/xml",
        )
    )


def _make_link(
    *,
    url: str,
    kind: str,
    relationship: str,
    confidence: float,
    source: str,
    reason_code: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "url": url,
        "kind": kind,
        "relationship": relationship,
        "confidence": confidence,
        "source": source,
    }
    if reason_code:
        payload["reason_code"] = reason_code
    return payload
