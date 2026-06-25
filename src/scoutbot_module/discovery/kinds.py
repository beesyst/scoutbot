from __future__ import annotations

from urllib.parse import urlparse

from scoutbot_module.discovery.urls import normalize_url

_LINK_AGGREGATOR_DOMAINS = {
    "linktr.ee",
    "bio.link",
    "beacons.ai",
    "campsite.bio",
}

_SOCIAL_PROFILE_DOMAINS = {
    "x.com",
    "twitter.com",
    "youtube.com",
    "youtu.be",
    "linkedin.com",
    "medium.com",
    "reddit.com",
}


def resolve_kind(url: str) -> dict[str, str | float]:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/")
    path_lower = path.lower()

    if hostname == "github.com":
        return _resolve_github_kind(path_lower)

    if hostname == "t.me":
        return _resolve_telegram_kind(path)

    if hostname in _LINK_AGGREGATOR_DOMAINS:
        return {
            "kind": "link_aggregator",
            "confidence": 0.9,
            "reason_code": "domain_match",
        }

    if hostname in _SOCIAL_PROFILE_DOMAINS:
        return {
            "kind": "social_profile",
            "confidence": 0.8,
            "reason_code": "domain_match",
        }

    if _looks_like_feed(path_lower):
        return {"kind": "rss", "confidence": 0.95, "reason_code": "path_hint"}

    if any(token in path_lower for token in ("/blog", "/news")):
        return {"kind": "blog", "confidence": 0.8, "reason_code": "path_hint"}

    if any(token in path_lower for token in ("/docs", "/documentation")):
        return {"kind": "docs", "confidence": 0.8, "reason_code": "path_hint"}

    if any(token in path_lower for token in ("/changelog", "/release-notes")):
        return {"kind": "changelog", "confidence": 0.8, "reason_code": "path_hint"}

    if any(token in path_lower for token in ("/pricing", "/plans", "/services")):
        return {"kind": "pricing", "confidence": 0.8, "reason_code": "path_hint"}

    if any(token in path_lower for token in ("/careers", "/jobs")):
        return {"kind": "careers", "confidence": 0.8, "reason_code": "path_hint"}

    return {"kind": "website", "confidence": 0.6, "reason_code": "default"}


def normalize_source_url(
    url: str, kind_info: dict[str, str | float] | None = None
) -> str:
    resolved = kind_info or resolve_kind(url)
    kind = str(resolved["kind"])
    if kind == "telegram_public":
        return normalize_telegram_url(url)
    return normalize_url(url)


def normalize_telegram_url(url: str) -> str:
    parsed = urlparse(url)
    segments = [segment for segment in parsed.path.split("/") if segment]
    if not segments:
        return normalize_url(url)
    if segments[0] == "s" and len(segments) >= 2:
        channel = segments[1]
    else:
        channel = segments[0]
    return f"https://t.me/s/{channel}"


def derive_github_releases_url(url: str) -> str | None:
    owner, repo = _extract_github_owner_repo(url)
    if not owner or not repo:
        return None
    return f"https://github.com/{owner}/{repo}/releases"


def derive_github_releases_atom(url: str) -> str | None:
    owner, repo = _extract_github_owner_repo(url)
    if not owner or not repo:
        return None
    return f"https://github.com/{owner}/{repo}/releases.atom"


def derive_github_changelog_candidates(url: str) -> list[str]:
    owner, repo = _extract_github_owner_repo(url)
    if not owner or not repo:
        return []
    base = f"https://github.com/{owner}/{repo}"
    return [
        f"{base}/blob/main/CHANGELOG.md",
        f"{base}/blob/master/CHANGELOG.md",
        f"{base}/blob/main/docs/changelog.md",
    ]


def is_private_or_invite_telegram(kind_info: dict[str, str | float]) -> bool:
    return str(kind_info.get("reason_code", "")).startswith("telegram_private") or (
        str(kind_info.get("reason_code", "")) == "telegram_invite_link"
    )


def _resolve_github_kind(path_lower: str) -> dict[str, str | float]:
    segments = [segment for segment in path_lower.split("/") if segment]
    if len(segments) == 1:
        return {"kind": "github", "confidence": 0.8, "reason_code": "github_org"}

    if len(segments) == 2:
        return {
            "kind": "github_repo",
            "confidence": 0.95,
            "reason_code": "github_repo",
        }

    if len(segments) >= 3 and segments[2] == "releases":
        return {
            "kind": "github_releases",
            "confidence": 0.95,
            "reason_code": "github_releases",
        }

    if _looks_like_github_changelog_path(segments):
        return {
            "kind": "github_changelog",
            "confidence": 0.8,
            "reason_code": "github_changelog",
        }

    return {
        "kind": "github",
        "confidence": 0.3,
        "reason_code": "github_unsupported_path",
    }


def _looks_like_github_changelog_path(segments: list[str]) -> bool:
    path = "/".join(segments)
    filename = segments[-1] if segments else ""
    return (
        "changelog" in path
        or "release-notes" in path
        or filename in {"changelog.md", "changes.md", "release-notes.md"}
    )


def _resolve_telegram_kind(path: str) -> dict[str, str | float]:
    segments = [segment for segment in path.split("/") if segment]
    if not segments:
        return {
            "kind": "telegram",
            "confidence": 0.2,
            "reason_code": "telegram_missing_channel",
        }
    first = segments[0]
    if first == "joinchat":
        return {
            "kind": "telegram",
            "confidence": 0.1,
            "reason_code": "telegram_invite_link",
        }
    if first.startswith("+"):
        return {
            "kind": "telegram",
            "confidence": 0.1,
            "reason_code": "telegram_private_invite",
        }
    if first == "s" and len(segments) >= 2:
        return {
            "kind": "telegram_public",
            "confidence": 0.95,
            "reason_code": "telegram_public",
        }
    if len(segments) != 1:
        return {
            "kind": "telegram",
            "confidence": 0.2,
            "reason_code": "telegram_invalid_path",
        }
    return {
        "kind": "telegram_public",
        "confidence": 0.95,
        "reason_code": "telegram_public",
    }


def _looks_like_feed(path_lower: str) -> bool:
    segments = [segment for segment in path_lower.split("/") if segment]
    return path_lower.endswith((".xml", ".rss", ".atom")) or any(
        segment in {"feed", "rss", "atom"} for segment in segments
    )


def _extract_github_owner_repo(url: str) -> tuple[str | None, str | None]:
    parsed = urlparse(url)
    if (parsed.hostname or "").lower() != "github.com":
        return None, None
    segments = [segment for segment in parsed.path.split("/") if segment]
    if len(segments) < 2:
        return None, None
    return segments[0], segments[1]
