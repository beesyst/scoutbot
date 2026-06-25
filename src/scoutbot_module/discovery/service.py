from __future__ import annotations

import asyncio
from typing import Any

from scoutbot_module.discovery.adapters import run_source_adapters


def discover(url: str, settings: dict) -> dict[str, Any]:
    return asyncio.run(discover_async(url, settings))


async def discover_async(url: str, settings: dict) -> dict[str, Any]:
    return await run_source_adapters(url, settings)
