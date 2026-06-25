from __future__ import annotations

from pathlib import Path
from typing import Any, NoReturn
from urllib.parse import urlparse

import yaml

_SUPPORTED_MODES = frozenset(
    {
        "doctor",
        "init-db",
        "import-seed",
        "export-seed",
        "sync",
        "telegram",
        "webhook",
        "routes",
        "digest",
        "backup",
        "audit",
    }
)

_SUPPORTED_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


def _fail(msg: str) -> NoReturn:
    raise ValueError(msg)


def _required_mapping(parent: dict[str, Any], key: str) -> dict[str, Any]:
    val = parent.get(key)
    if not isinstance(val, dict):
        _fail(f"{key}: must be a mapping")
    return val


def _check_positive_int(val: object, path: str) -> int:
    if type(val) is not int:
        _fail(f"{path}: expected int, got {type(val).__name__}")
    if val <= 0:
        _fail(f"{path}: must be positive, got {val}")
    return val


def _check_nonnegative_int(val: object, path: str) -> int:
    if type(val) is not int:
        _fail(f"{path}: expected int, got {type(val).__name__}")
    if val < 0:
        _fail(f"{path}: must be >= 0, got {val}")
    return val


def _check_required_string(val: object, path: str) -> str:
    if not isinstance(val, str):
        _fail(f"{path}: expected str, got {type(val).__name__}")
    if not val.strip():
        _fail(f"{path}: must be non-empty string")
    return val.strip()


def _check_log_level(val: object, path: str) -> str:
    level = _check_required_string(val, path)
    if level not in _SUPPORTED_LOG_LEVELS:
        _fail(
            f"{path}: unsupported {level!r}, "
            f"expected one of {sorted(_SUPPORTED_LOG_LEVELS)}"
        )
    return level


def _check_http_url(val: object, path: str) -> str:
    s = _check_required_string(val, path)
    parsed = urlparse(s)
    if parsed.scheme not in ("http", "https"):
        _fail(f"{path}: must be HTTP/HTTPS URL, got {s!r}")
    if not parsed.netloc:
        _fail(f"{path}: missing host in URL {s!r}")
    return s


def _check_env_key_name(val: object, path: str) -> str:
    s = _check_required_string(val, path)
    if not s.isidentifier():
        _fail(f"{path}: must be a valid env key name, got {s!r}")
    return s


def _check_bool(val: object, path: str) -> bool:
    if type(val) is not bool:
        _fail(f"{path}: expected bool, got {type(val).__name__}")
    return val


def _check_string_list(val: object, path: str) -> list[str]:
    if not isinstance(val, list):
        _fail(f"{path}: expected list[str], got {type(val).__name__}")
    result: list[str] = []
    for index, item in enumerate(val):
        result.append(_check_required_string(item, f"{path}[{index}]"))
    return result


def _check_categories_mapping(val: object, path: str) -> dict[str, list[str]]:
    if not isinstance(val, dict):
        _fail(f"{path}: expected mapping[str, list[str]]")
    result: dict[str, list[str]] = {}
    for key, item in val.items():
        category_name = _check_required_string(key, f"{path}.<key>")
        result[category_name] = _check_string_list(item, f"{path}.{category_name}")
    return result


def load_settings(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(f"Settings file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as f:
        raw: object = yaml.safe_load(f)

    if not isinstance(raw, dict):
        _fail(f"{config_path}: must be a YAML mapping")

    cfg: dict[str, Any] = raw

    app_ = _required_mapping(cfg, "app")
    _check_required_string(app_.get("name"), "app.name")
    _check_required_string(app_.get("env"), "app.env")

    run_ = _required_mapping(cfg, "run")
    mode = _check_required_string(run_.get("mode"), "run.mode")
    if mode not in _SUPPORTED_MODES:
        _fail(
            f"run.mode: unsupported {mode!r}, "
            f"expected one of {sorted(_SUPPORTED_MODES)}"
        )

    logging_ = _required_mapping(cfg, "logging")
    _check_log_level(logging_.get("level"), "logging.level")
    _check_bool(logging_.get("clear_logs"), "logging.clear_logs")
    _check_bool(logging_.get("utc"), "logging.utc")

    storage_ = _required_mapping(cfg, "storage")
    _check_required_string(storage_.get("root"), "storage.root")
    _check_required_string(storage_.get("db_path"), "storage.db_path")

    workspace_ = _required_mapping(cfg, "workspace")
    _check_required_string(workspace_.get("default_name"), "workspace.default_name")

    telegram_ = _required_mapping(cfg, "telegram")
    _check_env_key_name(telegram_.get("token_env"), "telegram.token_env")
    _check_env_key_name(telegram_.get("admin_ids_env"), "telegram.admin_ids_env")
    _check_env_key_name(
        telegram_.get("allowed_user_ids_env"), "telegram.allowed_user_ids_env"
    )
    _check_env_key_name(telegram_.get("chat_id_env"), "telegram.chat_id_env")

    webhook_ = _required_mapping(cfg, "webhook")
    _check_required_string(webhook_.get("host"), "webhook.host")
    _check_positive_int(webhook_.get("port"), "webhook.port")
    _check_required_string(webhook_.get("path"), "webhook.path")
    _check_positive_int(webhook_.get("body_bytes_max"), "webhook.body_bytes_max")

    cd_ = _required_mapping(cfg, "changedetection")
    _check_http_url(cd_.get("base_url"), "changedetection.base_url")
    _check_env_key_name(cd_.get("api_key_env"), "changedetection.api_key_env")
    _check_positive_int(cd_.get("timeout"), "changedetection.timeout")
    cd_interval_ = cd_.get("interval")
    if not isinstance(cd_interval_, dict):
        _fail("changedetection.interval: must be a mapping")
    _check_positive_int(cd_interval_.get("hours"), "changedetection.interval.hours")
    _check_required_string(cd_.get("fetch_backend"), "changedetection.fetch_backend")
    _check_env_key_name(
        cd_.get("webhook_secret_env"), "changedetection.webhook_secret_env"
    )
    _check_env_key_name(cd_.get("webhook_url_env"), "changedetection.webhook_url_env")

    discovery_ = _required_mapping(cfg, "discovery")
    _check_bool(discovery_.get("enabled"), "discovery.enabled")
    _check_bool(discovery_.get("auto_queue"), "discovery.auto_queue")
    conf_min = discovery_.get("conf_min")
    if type(conf_min) is not float and type(conf_min) is not int:
        _fail(f"discovery.conf_min: expected float, got {type(conf_min).__name__}")
    if not (0.0 <= conf_min <= 1.0):
        _fail(f"discovery.conf_min: must be between 0.0 and 1.0, got {conf_min}")
    _check_positive_int(
        discovery_.get("target_links_max"), "discovery.target_links_max"
    )
    _check_nonnegative_int(discovery_.get("max_depth"), "discovery.max_depth")
    _check_positive_int(discovery_.get("request_timeout"), "discovery.request_timeout")
    _check_positive_int(
        discovery_.get("max_response_bytes"), "discovery.max_response_bytes"
    )
    _check_bool(
        discovery_.get("allow_private_networks"),
        "discovery.allow_private_networks",
    )
    _check_string_list(discovery_.get("allowed_kinds"), "discovery.allowed_kinds")
    _check_string_list(
        discovery_.get("require_confirmation_kinds"),
        "discovery.require_confirmation_kinds",
    )
    _check_string_list(discovery_.get("blocked_domains"), "discovery.blocked_domains")

    signals_ = _required_mapping(cfg, "signals")
    _check_bool(signals_.get("dedupe_enabled"), "signals.dedupe_enabled")
    _check_positive_int(
        signals_.get("body_excerpt_chars"), "signals.body_excerpt_chars"
    )
    categories_ = _check_categories_mapping(
        signals_.get("categories"), "signals.categories"
    )
    for category_name in (
        "pricing",
        "delegation",
        "validator_network",
        "product",
        "positioning",
        "hiring",
        "legal",
        "social",
        "noise",
    ):
        values = categories_.get(category_name)
        if not values:
            _fail(f"signals.categories.{category_name}: must be a non-empty list[str]")
    priority_val = signals_.get("priority")
    if not isinstance(priority_val, dict):
        _fail(
            f"signals.priority: must be a mapping, "
            f"got {type(priority_val).__name__} "
            f"keys={list(signals_.keys())}"
        )
    _check_string_list(
        priority_val.get("high_categories"), "signals.priority.high_categories"
    )
    _check_string_list(
        priority_val.get("medium_categories"), "signals.priority.medium_categories"
    )

    ai_ = _required_mapping(cfg, "ai")
    ai_enabled = ai_.get("enabled")
    _check_bool(ai_enabled, "ai.enabled")
    if ai_enabled is not False:
        _fail("ai.enabled: must be false in MVP baseline")

    integrations_ = _required_mapping(cfg, "integrations")
    n8n_ = integrations_.get("n8n")
    if not isinstance(n8n_, dict):
        _fail("integrations.n8n: must be a mapping")
    n8n_enabled = n8n_.get("enabled")
    _check_bool(n8n_enabled, "integrations.n8n.enabled")
    _check_env_key_name(
        n8n_.get("webhook_url_env"),
        "integrations.n8n.webhook_url_env",
    )
    if n8n_enabled is not False:
        _fail("integrations.n8n.enabled: must be false in MVP baseline")

    return cfg
