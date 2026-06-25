from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from scoutbot_module.discovery.kinds import normalize_source_url, resolve_kind

LOG = logging.getLogger("scoutbot.discovery.socials")


def extract_socials(html: str, base_url: str) -> list[dict[str, Any]]:
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    socials: list[dict[str, Any]] = []
    seen: set[str] = set()

    social_patterns = {
        "github.com": ("github", "social"),
        "t.me": ("telegram", "social"),
        "youtube.com": ("social_profile", "social"),
        "youtu.be": ("social_profile", "social"),
        "x.com": ("social_profile", "social"),
        "twitter.com": ("social_profile", "social"),
        "linkedin.com": ("social_profile", "social"),
        "discord.gg": ("social_profile", "social"),
        "discord.com": ("social_profile", "social"),
        "medium.com": ("social_profile", "social"),
        "reddit.com": ("social_profile", "social"),
        "linktr.ee": ("link_aggregator", "link_aggregator_child"),
        "bio.link": ("link_aggregator", "link_aggregator_child"),
        "beacons.ai": ("link_aggregator", "link_aggregator_child"),
        "campsite.bio": ("link_aggregator", "link_aggregator_child"),
    }

    for tag in soup.find_all("a", href=True):
        href = str(tag.get("href", "")).strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)
        hostname = parsed.hostname or ""

        for pattern, (kind, relationship) in social_patterns.items():
            if pattern in hostname:
                if full_url not in seen:
                    seen.add(full_url)
                    kind_info = resolve_kind(full_url)
                    socials.append(
                        {
                            "url": normalize_source_url(full_url, kind_info),
                            "kind": (
                                str(kind_info["kind"])
                                if pattern in {"github.com", "t.me"}
                                else kind
                            ),
                            "relationship": relationship,
                            "confidence": (
                                float(kind_info["confidence"])
                                if pattern in {"github.com", "t.me"}
                                else 0.7
                            ),
                            "source": "social_link",
                        }
                    )
                break

    return socials
