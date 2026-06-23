from __future__ import annotations

import asyncio
import logging
from typing import Any

from scoutbot_module.discovery.feeds import extract_feeds
from scoutbot_module.discovery.fetch import fetch_page
from scoutbot_module.discovery.links import extract_links
from scoutbot_module.discovery.socials import extract_socials
from scoutbot_module.discovery.urls import validate_url

LOG = logging.getLogger("scoutbot.discovery.service")


def discover(url: str, settings: dict) -> dict[str, Any]:
    return asyncio.run(discover_async(url, settings))


async def discover_async(url: str, settings: dict) -> dict[str, Any]:
    discovery_cfg = settings["discovery"]
    timeout = discovery_cfg["request_timeout"]
    max_bytes = discovery_cfg["max_response_bytes"]
    max_links = discovery_cfg["target_links_max"]
    allow_private = discovery_cfg["allow_private_networks"]

    validate_url(url, allow_private_networks=allow_private)

    fetch_result = await fetch_page(
        url=url,
        timeout=timeout,
        max_response_bytes=max_bytes,
        allow_private_networks=allow_private,
    )

    if fetch_result.get("error"):
        return {
            "url": url,
            "links": [],
            "error": fetch_result["error"],
        }

    html = fetch_result.get("html", "")
    actual_url = fetch_result.get("url", url)
    links = extract_links(html, actual_url, max_links=max_links)
    feeds = extract_feeds(html, actual_url)
    links.extend(feeds)
    socials = extract_socials(html, actual_url)
    links.extend(socials)

    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for link in links:
        if link["url"] not in seen:
            seen.add(link["url"])
            unique.append(link)

    return {
        "url": actual_url,
        "links": unique[:max_links],
    }
