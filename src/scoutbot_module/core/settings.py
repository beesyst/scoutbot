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
    }
)

_SUPPORTED_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


# Настройки
def _fail(msg: str) -> NoReturn:
    raise ValueError(msg)


# Чекер для обязательных секций
def _required_mapping(parent: dict[str, Any], key: str) -> dict[str, Any]:
    val = parent.get(key)
    if not isinstance(val, dict):
        _fail(f"{key}: must be a mapping")
    return val


# Чекеры конкретных типов и значений
def _check_positive_int(val: object, path: str) -> int:
    if type(val) is not int:
        _fail(f"{path}: expected int, got {type(val).__name__}")
    if val <= 0:
        _fail(f"{path}: must be positive, got {val}")
    return val


# Чекер для неотрицательных целых чисел
def _check_nonnegative_int(val: object, path: str) -> int:
    if type(val) is not int:
        _fail(f"{path}: expected int, got {type(val).__name__}")
    if val < 0:
        _fail(f"{path}: must be >= 0, got {val}")
    return val


# Чекер для обязательных непустых строк
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


# Чекер для обязательных HTTP/HTTPS URL
def _check_http_url(val: object, path: str) -> str:
    s = _check_required_string(val, path)
    parsed = urlparse(s)
    if parsed.scheme not in ("http", "https"):
        _fail(f"{path}: must be HTTP/HTTPS URL, got {s!r}")
    if not parsed.netloc:
        _fail(f"{path}: missing host in URL {s!r}")
    return s


# Валидация имени переменной окружения (env key name)
def _check_env_key_name(val: object, path: str) -> str:
    s = _check_required_string(val, path)
    if not s.isidentifier():
        _fail(f"{path}: must be a valid env key name, got {s!r}")
    return s


# Чекер для булевых значений
def _check_bool(val: object, path: str) -> bool:
    if type(val) is not bool:
        _fail(f"{path}: expected bool, got {type(val).__name__}")
    return val


# Загрузка и валидация настроек из YAML
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

    telegram_ = _required_mapping(cfg, "telegram")
    _check_env_key_name(telegram_.get("token_env"), "telegram.token_env")
    _check_env_key_name(telegram_.get("admin_ids_env"), "telegram.admin_ids_env")
    _check_env_key_name(telegram_.get("chat_id_env"), "telegram.chat_id_env")

    cd_ = _required_mapping(cfg, "changedetection")
    _check_http_url(cd_.get("base_url"), "changedetection.base_url")
    _check_env_key_name(cd_.get("api_key_env"), "changedetection.api_key_env")
    _check_positive_int(cd_.get("timeout"), "changedetection.timeout")
    cd_interval_ = cd_.get("default_interval")
    if not isinstance(cd_interval_, dict):
        _fail("changedetection.default_interval: must be a mapping")
    _check_positive_int(
        cd_interval_.get("hours"), "changedetection.default_interval.hours"
    )
    _check_required_string(
        cd_.get("default_fetch_backend"), "changedetection.default_fetch_backend"
    )
    _check_env_key_name(
        cd_.get("webhook_secret_env"), "changedetection.webhook_secret_env"
    )
    _check_env_key_name(cd_.get("webhook_url_env"), "changedetection.webhook_url_env")

    discovery_ = _required_mapping(cfg, "discovery")
    _check_bool(discovery_.get("enabled"), "discovery.enabled")
    _check_bool(discovery_.get("auto_queue"), "discovery.auto_queue")
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
    if n8n_enabled is not False:
        _fail("integrations.n8n.enabled: must be false in MVP baseline")

    return cfg
