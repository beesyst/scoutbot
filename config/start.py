from __future__ import annotations

import argparse
import logging
import sys
import time as _time
from collections.abc import Callable
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT_DIR / "config"
SRC_DIR = ROOT_DIR / "src"
LOGS_DIR = ROOT_DIR / "logs"
STORAGE_DIR = ROOT_DIR / "storage"

sys.path.insert(0, str(SRC_DIR))

Handler = Callable[[dict, list[str]], int]
SUPPORTED_COMMANDS = {
    "run",
    "doctor",
    "init-db",
    "import-seed",
    "export-seed",
    "sync",
    "telegram",
    "webhook",
    "routes",
    "digest",
}


def _bootstrap_env_file_if_missing() -> None:
    env_path = ROOT_DIR / ".env"
    example_path = ROOT_DIR / ".env.example"
    if env_path.exists() or not example_path.exists():
        return
    env_path.write_text(example_path.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"[env] Created {env_path.name} from {example_path.name}")
    print("[env] Please edit .env and set real secrets")


def _load_env() -> None:
    env_path = ROOT_DIR / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)


def _load_raw_settings(config_path: Path) -> dict:
    with config_path.open("r", encoding="utf-8") as f:
        payload = yaml.safe_load(f) or {}
    if not isinstance(payload, dict):
        raise ValueError("settings.yml must be a YAML mapping")
    return payload


def _load_settings(config_path: Path) -> dict:
    from scoutbot_module.core.settings import load_settings

    return load_settings(config_path)


def _setup_logging(settings: dict) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    logging_cfg = settings["logging"]
    level = str(logging_cfg["level"]).upper()
    utc = logging_cfg["utc"]
    clear_logs = logging_cfg["clear_logs"]

    try:
        from scoutbot_module.core.log import setup_logging

        setup_logging(
            logs_dir=LOGS_DIR,
            level=level,
            utc=utc,
            clear_logs=clear_logs,
        )
        return
    except ImportError:
        pass

    log_path = LOGS_DIR / "app.log"
    if clear_logs and log_path.exists():
        log_path.unlink()

    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_path, encoding="utf-8"),
        ],
    )

    if utc:
        logging.Formatter.converter = _time.gmtime


def _prepare_dirs(settings: dict) -> None:
    storage_root = Path(str(settings["storage"]["root"]))

    if not storage_root.is_absolute():
        storage_root = ROOT_DIR / storage_root

    storage_root.mkdir(parents=True, exist_ok=True)
    (storage_root / "db").mkdir(parents=True, exist_ok=True)
    (storage_root / "runs").mkdir(parents=True, exist_ok=True)
    (storage_root / "discovery").mkdir(parents=True, exist_ok=True)
    (storage_root / "signals").mkdir(parents=True, exist_ok=True)
    (storage_root / "interfaces").mkdir(parents=True, exist_ok=True)
    (storage_root / "exports").mkdir(parents=True, exist_ok=True)


def _resolve_command(raw_command: str | None, settings: dict) -> str:
    command = raw_command or "run"

    if command == "run":
        run_cfg = settings["run"]
        command = str(run_cfg["mode"]).strip()

    if command not in SUPPORTED_COMMANDS or command == "run":
        supported = ", ".join(sorted(SUPPORTED_COMMANDS - {"run"}))
        raise ValueError(
            f"Unsupported command: {command!r}. Supported commands: run, {supported}"
        )

    return command


def _run_routes(settings: dict, argv: list[str]) -> int:
    """Display available CLI routes."""
    del settings, argv
    print("ScoutBot routes:")
    print("  ./start.sh doctor")
    print("  ./start.sh init-db")
    print("  ./start.sh import-seed config/seeds/noders.yml")
    print("  ./start.sh export-seed storage/exports/noders.export.yml")
    print("  ./start.sh sync")
    print("  ./start.sh telegram")
    print("  ./start.sh webhook")
    print("  ./start.sh digest")
    print("  ./start.sh routes")
    return 0


def _load_handler(command: str) -> Handler:
    if command == "routes":
        return _run_routes

    if command == "doctor":
        from scoutbot_module.core.cli import run_doctor

        return run_doctor

    if command == "init-db":
        from scoutbot_module.core.cli import run_init_db

        return run_init_db

    if command == "import-seed":
        from scoutbot_module.core.cli import run_import_seed

        return run_import_seed

    if command == "export-seed":
        from scoutbot_module.core.cli import run_export_seed

        return run_export_seed

    if command == "sync":
        from scoutbot_module.core.cli import run_sync

        return run_sync

    if command == "telegram":
        from scoutbot_module.bot.app import run_telegram

        return run_telegram

    if command == "webhook":
        from scoutbot_module.web.app import run_webhook

        return run_webhook

    if command == "digest":
        from scoutbot_module.core.cli import run_digest

        return run_digest

    raise ValueError(f"Unsupported command: {command}")


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="scoutbot",
        description="ScoutBot — Telegram-first monitoring assistant",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default=None,
        help=(
            "command: doctor, init-db, import-seed, export-seed, "
            "sync, telegram, webhook, routes. "
            "If omitted, uses run.mode from config/settings.yml."
        ),
    )

    args, remaining_args = parser.parse_known_args()

    _bootstrap_env_file_if_missing()
    _load_env()

    config_path = CONFIG_DIR / "settings.yml"
    if not config_path.exists():
        raise FileNotFoundError(f"Missing config file: {config_path}")

    _load_raw_settings(config_path)

    settings = _load_settings(config_path)
    _prepare_dirs(settings)
    _setup_logging(settings)

    command = _resolve_command(args.command, settings)
    logging.getLogger("scoutbot.start").info("Starting command=%s", command)

    handler = _load_handler(command)
    return handler(settings, remaining_args)


if __name__ == "__main__":
    sys.exit(main() or 0)
