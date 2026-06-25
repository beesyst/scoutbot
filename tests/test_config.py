from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scoutbot_module.core.settings import load_settings


def _write_settings(tmp_path: Path, overrides: dict | None = None) -> Path:
    base = {
        "app": {"name": "ScoutBot", "env": "test"},
        "run": {"mode": "routes"},
        "logging": {
            "level": "INFO",
            "clear_logs": True,
            "utc": True,
        },
        "storage": {
            "root": "storage",
            "db_path": "storage/db/scoutbot.sqlite3",
        },
        "workspace": {
            "default_name": "NODERS",
        },
        "telegram": {
            "token_env": "TELEGRAM_BOT_TOKEN",
            "admin_ids_env": "TELEGRAM_ADMIN_IDS",
            "allowed_user_ids_env": "TELEGRAM_ALLOWED_USER_IDS",
            "chat_id_env": "TELEGRAM_ALERT_CHAT_ID",
        },
        "webhook": {
            "host": "127.0.0.1",
            "port": 8000,
            "path": "/webhooks/changedetection",
            "body_bytes_max": 131072,
        },
        "changedetection": {
            "base_url": "http://127.0.0.1:5000",
            "api_key_env": "CHANGEDETECTION_API_KEY",
            "timeout": 20,
            "interval": {"hours": 6},
            "fetch_backend": "html_requests",
            "webhook_secret_env": "SCOUTBOT_WEBHOOK_SECRET",
            "webhook_url_env": "SCOUTBOT_WEBHOOK_URL",
        },
        "discovery": {
            "enabled": True,
            "auto_queue": True,
            "conf_min": 0.7,
            "target_links_max": 30,
            "max_depth": 1,
            "request_timeout": 10,
            "max_response_bytes": 1000000,
            "allowed_kinds": [
                "website",
                "blog",
                "rss",
                "github_repo",
                "github_releases",
                "telegram_public",
                "link_aggregator",
            ],
            "require_confirmation_kinds": ["social_profile"],
            "blocked_domains": [],
            "allow_private_networks": False,
        },
        "signals": {
            "profile": "noders",
            "dedupe_enabled": True,
            "body_excerpt_chars": 1000,
            "categories": {
                "pricing": ["pricing", "price"],
                "product": ["feature", "api"],
                "delegation": ["delegation", "staking"],
                "validator_network": ["validator", "network"],
                "positioning": ["positioning"],
                "hiring": ["careers", "jobs"],
                "legal": ["privacy", "terms"],
                "social": ["announcement"],
                "noise": ["©", "All rights reserved"],
            },
            "priority": {
                "high_categories": ["pricing", "delegation", "validator_network"],
                "medium_categories": [
                    "product",
                    "positioning",
                    "hiring",
                    "legal",
                    "social",
                ],
            },
            "noise": {
                "ignore_text": ["©", "All rights reserved"],
                "ignore_selectors": ["nav", "footer"],
            },
        },
        "ai": {"enabled": False},
        "integrations": {"n8n": {"enabled": False, "webhook_url_env": "N8N_WEBHOOK_URL"}},
    }
    if overrides:
        _deep_merge(base, overrides)
    path = tmp_path / "settings.yml"
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(base, f)
    return path


def _deep_merge(base: dict, overrides: dict) -> None:
    for key, value in overrides.items():
        if (
            key in base
            and isinstance(base[key], dict)
            and isinstance(value, dict)
            and value
        ):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def test_settings_load_ok(tmp_path: Path) -> None:
    path = _write_settings(tmp_path)
    cfg = load_settings(path)
    assert cfg["app"]["name"] == "ScoutBot"
    assert cfg["app"]["env"] == "test"
    assert cfg["run"]["mode"] == "routes"
    assert cfg["logging"]["level"] == "INFO"
    assert cfg["logging"]["clear_logs"] is True
    assert cfg["logging"]["utc"] is True
    assert cfg["telegram"]["chat_id_env"] == "TELEGRAM_ALERT_CHAT_ID"
    assert "alert_chat_id_env" not in cfg["telegram"]
    assert cfg["discovery"]["target_links_max"] == 30
    assert "max_links_per_target" not in cfg["discovery"]
    assert cfg["workspace"]["default_name"] == "NODERS"
    assert cfg["webhook"]["host"] == "127.0.0.1"
    assert cfg["webhook"]["port"] == 8000
    assert cfg["webhook"]["path"] == "/webhooks/changedetection"
    assert cfg["webhook"]["body_bytes_max"] == 131072
    assert cfg["integrations"]["n8n"]["webhook_url_env"] == "N8N_WEBHOOK_URL"


def test_supported_modes_include_backup_and_audit(tmp_path: Path) -> None:
    for mode in ("backup", "audit"):
        path = _write_settings(tmp_path, {"run": {"mode": mode}})
        cfg = load_settings(path)
        assert cfg["run"]["mode"] == mode


def test_missing_workspace_default_name_fails(tmp_path: Path) -> None:
    path = _write_settings(tmp_path, {"workspace": {"default_name": ""}})
    with pytest.raises(ValueError, match="workspace.default_name"):
        load_settings(path)


def test_missing_webhook_host_fails(tmp_path: Path) -> None:
    path = _write_settings(tmp_path, {"webhook": {}})
    with pytest.raises(ValueError, match="webhook.host"):
        load_settings(path)


def test_webhook_port_zero_fails(tmp_path: Path) -> None:
    path = _write_settings(tmp_path, {"webhook": {"port": 0}})
    with pytest.raises(ValueError, match="webhook.port"):
        load_settings(path)


def test_missing_required_key_fails(tmp_path: Path) -> None:
    path = _write_settings(tmp_path, {"app": {"name": ""}})
    with pytest.raises(ValueError, match="app.name"):
        load_settings(path)


def test_missing_app_name_fails(tmp_path: Path) -> None:
    path = _write_settings(tmp_path, {"app": {}})
    with pytest.raises(ValueError, match="app.name"):
        load_settings(path)


def test_invalid_changedetection_url_fails(tmp_path: Path) -> None:
    path = _write_settings(tmp_path, {"changedetection": {"base_url": "not-a-url"}})
    with pytest.raises(ValueError, match="changedetection.base_url"):
        load_settings(path)


def test_invalid_changedetection_url_ftp_fails(tmp_path: Path) -> None:
    path = _write_settings(
        tmp_path, {"changedetection": {"base_url": "ftp://example.com"}}
    )
    with pytest.raises(ValueError, match="changedetection.base_url"):
        load_settings(path)


def test_ai_enabled_false_baseline(tmp_path: Path) -> None:
    path = _write_settings(tmp_path)
    cfg = load_settings(path)
    assert cfg["ai"]["enabled"] is False


def test_ai_enabled_true_fails(tmp_path: Path) -> None:
    path = _write_settings(tmp_path, {"ai": {"enabled": True}})
    with pytest.raises(ValueError, match="ai.enabled"):
        load_settings(path)


def test_n8n_enabled_false_baseline(tmp_path: Path) -> None:
    path = _write_settings(tmp_path)
    cfg = load_settings(path)
    assert cfg["integrations"]["n8n"]["enabled"] is False
    assert cfg["integrations"]["n8n"]["webhook_url_env"] == "N8N_WEBHOOK_URL"


def test_n8n_enabled_true_fails(tmp_path: Path) -> None:
    path = _write_settings(tmp_path, {"integrations": {"n8n": {"enabled": True}}})
    with pytest.raises(ValueError, match="integrations.n8n.enabled"):
        load_settings(path)


def test_invalid_run_mode_fails(tmp_path: Path) -> None:
    path = _write_settings(tmp_path, {"run": {"mode": "invalid_mode"}})
    with pytest.raises(ValueError, match="run.mode"):
        load_settings(path)


def test_missing_logging_level_fails(tmp_path: Path) -> None:
    path = _write_settings(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    del data["logging"]["level"]
    path.write_text(yaml.dump(data), encoding="utf-8")

    with pytest.raises(ValueError, match="logging.level"):
        load_settings(path)


def test_invalid_logging_level_fails(tmp_path: Path) -> None:
    path = _write_settings(tmp_path, {"logging": {"level": "TRACE"}})
    with pytest.raises(ValueError, match="logging.level"):
        load_settings(path)


def test_missing_logging_clear_logs_fails(tmp_path: Path) -> None:
    path = _write_settings(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    del data["logging"]["clear_logs"]
    path.write_text(yaml.dump(data), encoding="utf-8")

    with pytest.raises(ValueError, match="logging.clear_logs"):
        load_settings(path)


def test_missing_logging_utc_fails(tmp_path: Path) -> None:
    path = _write_settings(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    del data["logging"]["utc"]
    path.write_text(yaml.dump(data), encoding="utf-8")

    with pytest.raises(ValueError, match="logging.utc"):
        load_settings(path)


def test_invalid_logging_clear_logs_string_fails(tmp_path: Path) -> None:
    path = _write_settings(tmp_path, {"logging": {"clear_logs": "false"}})
    with pytest.raises(ValueError, match="logging.clear_logs"):
        load_settings(path)


def test_invalid_logging_utc_string_fails(tmp_path: Path) -> None:
    path = _write_settings(tmp_path, {"logging": {"utc": "true"}})
    with pytest.raises(ValueError, match="logging.utc"):
        load_settings(path)


def test_missing_storage_root_fails(tmp_path: Path) -> None:
    path = _write_settings(tmp_path, {"storage": {}})
    with pytest.raises(ValueError, match="storage.root"):
        load_settings(path)


def test_negative_timeout_fails(tmp_path: Path) -> None:
    path = _write_settings(tmp_path, {"changedetection": {"timeout": -1}})
    with pytest.raises(ValueError, match="changedetection.timeout"):
        load_settings(path)


def test_missing_telegram_env_keys_fails(tmp_path: Path) -> None:
    path = _write_settings(tmp_path, {"telegram": {}})
    with pytest.raises(ValueError, match="telegram.token_env"):
        load_settings(path)


@pytest.mark.parametrize(
    ("section", "key", "expected"),
    [
        ("app", "name", "app.name"),
        ("app", "env", "app.env"),
        ("run", "mode", "run.mode"),
        ("logging", "level", "logging.level"),
        ("logging", "clear_logs", "logging.clear_logs"),
        ("logging", "utc", "logging.utc"),
        ("storage", "root", "storage.root"),
        ("storage", "db_path", "storage.db_path"),
        ("telegram", "token_env", "telegram.token_env"),
        ("telegram", "admin_ids_env", "telegram.admin_ids_env"),
        ("telegram", "allowed_user_ids_env", "telegram.allowed_user_ids_env"),
        ("telegram", "chat_id_env", "telegram.chat_id_env"),
        ("webhook", "host", "webhook.host"),
        ("webhook", "port", "webhook.port"),
        ("webhook", "path", "webhook.path"),
        ("webhook", "body_bytes_max", "webhook.body_bytes_max"),
        ("changedetection", "base_url", "changedetection.base_url"),
        ("changedetection", "api_key_env", "changedetection.api_key_env"),
        ("changedetection", "timeout", "changedetection.timeout"),
        ("changedetection", "fetch_backend", "changedetection.fetch_backend"),
        ("changedetection", "webhook_secret_env", "changedetection.webhook_secret_env"),
        ("changedetection", "webhook_url_env", "changedetection.webhook_url_env"),
        ("discovery", "enabled", "discovery.enabled"),
        ("discovery", "auto_queue", "discovery.auto_queue"),
        ("discovery", "conf_min", "discovery.conf_min"),
        ("discovery", "target_links_max", "discovery.target_links_max"),
        ("discovery", "max_depth", "discovery.max_depth"),
        ("discovery", "request_timeout", "discovery.request_timeout"),
        ("discovery", "max_response_bytes", "discovery.max_response_bytes"),
        ("discovery", "allowed_kinds", "discovery.allowed_kinds"),
        (
            "discovery",
            "require_confirmation_kinds",
            "discovery.require_confirmation_kinds",
        ),
        ("discovery", "blocked_domains", "discovery.blocked_domains"),
        ("discovery", "allow_private_networks", "discovery.allow_private_networks"),
        ("signals", "dedupe_enabled", "signals.dedupe_enabled"),
        ("signals", "body_excerpt_chars", "signals.body_excerpt_chars"),
        ("signals", "categories", "signals.categories"),
        ("ai", "enabled", "ai.enabled"),
        ("integrations", "n8n", "integrations.n8n"),
    ],
)
def test_required_keys_have_no_hidden_defaults(
    tmp_path: Path,
    section: str,
    key: str,
    expected: str,
) -> None:
    path = _write_settings(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    del data[section][key]
    path.write_text(yaml.dump(data), encoding="utf-8")

    with pytest.raises(ValueError, match=expected):
        load_settings(path)


def test_missing_changedetection_interval_hours_fails(tmp_path: Path) -> None:
    path = _write_settings(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    del data["changedetection"]["interval"]["hours"]
    path.write_text(yaml.dump(data), encoding="utf-8")

    with pytest.raises(ValueError, match="changedetection.interval.hours"):
        load_settings(path)


def test_missing_discovery_conf_min_fails(tmp_path: Path) -> None:
    path = _write_settings(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    del data["discovery"]["conf_min"]
    path.write_text(yaml.dump(data), encoding="utf-8")

    with pytest.raises(ValueError, match="discovery.conf_min"):
        load_settings(path)


def test_missing_integrations_n8n_enabled_fails(tmp_path: Path) -> None:
    path = _write_settings(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    del data["integrations"]["n8n"]["enabled"]
    path.write_text(yaml.dump(data), encoding="utf-8")

    with pytest.raises(ValueError, match="integrations.n8n.enabled"):
        load_settings(path)


def test_missing_integrations_n8n_webhook_url_env_fails(tmp_path: Path) -> None:
    path = _write_settings(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    del data["integrations"]["n8n"]["webhook_url_env"]
    path.write_text(yaml.dump(data), encoding="utf-8")

    with pytest.raises(ValueError, match="integrations.n8n.webhook_url_env"):
        load_settings(path)


def test_missing_required_signal_category_fails(tmp_path: Path) -> None:
    path = _write_settings(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    del data["signals"]["categories"]["product"]
    path.write_text(yaml.dump(data), encoding="utf-8")

    with pytest.raises(ValueError, match="signals.categories.product"):
        load_settings(path)


def test_supported_modes_are_registered() -> None:
    from scoutbot_module.core.settings import _SUPPORTED_MODES

    assert "backup" in _SUPPORTED_MODES
    assert "audit" in _SUPPORTED_MODES


def test_n8n_webhook_url_env_is_required(tmp_path: Path) -> None:
    path = _write_settings(tmp_path)
    cfg = load_settings(path)
    n8n = cfg["integrations"]["n8n"]
    assert n8n["webhook_url_env"] == "N8N_WEBHOOK_URL"
