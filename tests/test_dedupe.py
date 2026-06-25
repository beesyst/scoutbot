from __future__ import annotations

from scoutbot_module.intelligence.classify import classify_signal
from scoutbot_module.intelligence.dedupe import compute_diff_hash, is_duplicate

CATEGORIES = {
    "pricing": ["pricing", "price", "plan", "enterprise", "discount"],
    "delegation": [
        "delegation",
        "validator",
        "staking",
        "mainnet",
        "testnet",
        "governance",
        "commission",
        "restaking",
    ],
    "product": ["feature", "integration", "api", "dashboard", "network", "chain"],
    "validator_network": ["validator", "network", "node"],
    "positioning": ["positioning", "roadmap"],
    "hiring": ["careers", "jobs", "engineer"],
    "legal": ["privacy", "terms", "compliance"],
    "social": ["announcement", "community"],
    "noise": ["©", "All rights reserved"],
}

PRIORITY_CONFIG = {
    "high_categories": ["pricing", "delegation", "validator_network"],
    "medium_categories": ["product", "positioning", "hiring", "legal", "social"],
}


def test_diff_hash_consistent() -> None:
    p1 = {"title": "Test", "url": "https://example.com", "text": "abc"}
    p2 = {"title": "Test", "url": "https://example.com", "text": "abc"}
    assert compute_diff_hash(p1) == compute_diff_hash(p2)


def test_diff_hash_different() -> None:
    p1 = {"title": "A", "url": "https://example.com", "text": "abc"}
    p2 = {"title": "B", "url": "https://example.com", "text": "xyz"}
    assert compute_diff_hash(p1) != compute_diff_hash(p2)


def test_is_duplicate_suppresses() -> None:
    h = compute_diff_hash({"text": "abc"})
    existing = {("tgt_1", h)}
    assert is_duplicate("tgt_1", h, existing) is True
    assert is_duplicate("tgt_2", h, existing) is False


def test_classify_pricing() -> None:
    result = classify_signal(
        {"text": "New pricing plans available", "url": "https://example.com/pricing"},
        categories=CATEGORIES,
        priority_config=PRIORITY_CONFIG,
    )
    assert result["category"] == "pricing"
    assert result["priority"] == "high"


def test_classify_delegation() -> None:
    result = classify_signal(
        {"text": "Validator staking update for mainnet", "url": "https://example.com"},
        categories=CATEGORIES,
        priority_config=PRIORITY_CONFIG,
    )
    assert result["category"] == "delegation"
    assert result["priority"] == "high"


def test_classify_product() -> None:
    result = classify_signal(
        {"text": "New API integration feature", "url": "https://example.com"},
        categories=CATEGORIES,
        priority_config=PRIORITY_CONFIG,
    )
    assert result["category"] == "product"
    assert result["priority"] == "medium"


def test_classify_social() -> None:
    result = classify_signal(
        {"text": "Some update", "url": "https://t.me/channel"},
        categories=CATEGORIES,
        priority_config=PRIORITY_CONFIG,
    )
    assert result["category"] == "social"
    assert result["priority"] == "medium"


def test_classify_unknown() -> None:
    result = classify_signal(
        {"text": "Something happened", "url": "https://example.com"},
        categories=CATEGORIES,
        priority_config=PRIORITY_CONFIG,
    )
    assert result["category"] == "unknown"
    assert result["priority"] == "low"
