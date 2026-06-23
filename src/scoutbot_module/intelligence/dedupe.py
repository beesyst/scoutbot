from __future__ import annotations

import hashlib
import json
from typing import Any


def compute_diff_hash(payload: dict[str, Any]) -> str:
    parts = []
    for key in (
        "uuid",
        "watch_uuid",
        "changedetection_uuid",
        "title",
        "url",
        "text",
        "diff",
        "summary",
    ):
        val = payload.get(key)
        if val and isinstance(val, str):
            parts.append(val)
    if not parts:
        parts.append(json.dumps(payload, sort_keys=True, default=str))
    combined = "|".join(parts)
    return hashlib.sha256(combined.encode()).hexdigest()[:32]


def is_duplicate(
    target_id: str,
    diff_hash: str,
    existing_hashes: set[tuple[str, str]],
) -> bool:
    return (target_id, diff_hash) in existing_hashes
