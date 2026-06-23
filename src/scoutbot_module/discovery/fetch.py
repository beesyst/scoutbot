from __future__ import annotations

import logging
from typing import Any

import httpx

from scoutbot_module.discovery.urls import validate_url

LOG = logging.getLogger("scoutbot.discovery.fetch")


async def fetch_page(
    url: str,
    timeout: int = 10,
    max_response_bytes: int = 1_000_000,
    allow_private_networks: bool = False,
) -> dict[str, Any]:
    validate_url(url, allow_private_networks=allow_private_networks)

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=False,
        ) as client:
            async with client.stream("GET", url) as resp:
                content = await _read_bounded_response(resp, max_response_bytes)
                return {
                    "url": str(resp.url),
                    "status_code": resp.status_code,
                    "content_type": resp.headers.get("content-type", ""),
                    "html": content["html"],
                    "truncated": content["truncated"],
                }
    except httpx.TimeoutException:
        LOG.warning("Timeout fetching %s", url)
        return {"url": url, "error": "timeout", "html": ""}
    except httpx.HTTPStatusError as exc:
        LOG.warning("HTTP error %s for %s", exc.response.status_code, url)
        return {"url": url, "error": f"http_{exc.response.status_code}", "html": ""}
    except Exception as exc:
        LOG.warning("Fetch error for %s: %s", url, exc)
        return {"url": url, "error": "fetch_error", "html": ""}


async def _read_bounded_response(
    resp: httpx.Response,
    max_response_bytes: int,
) -> dict[str, Any]:
    data = bytearray()
    truncated = False

    async for chunk in resp.aiter_bytes():
        if not chunk:
            continue
        remaining = max_response_bytes - len(data)
        if remaining <= 0:
            truncated = True
            break
        if len(chunk) > remaining:
            data.extend(chunk[:remaining])
            truncated = True
            break
        data.extend(chunk)

    encoding = resp.encoding or "utf-8"
    html = data.decode(encoding, errors="replace")
    return {"html": html, "truncated": truncated}
