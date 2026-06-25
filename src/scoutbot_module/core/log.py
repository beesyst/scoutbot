from __future__ import annotations

import logging
import time
from pathlib import Path


def setup_logging(
    logs_dir: Path,
    level: str = "INFO",
    utc: bool = True,
    clear_logs: bool = False,
) -> None:
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / "app.log"

    if clear_logs and log_path.exists():
        log_path.unlink()

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    for h in list(root.handlers):
        root.removeHandler(h)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

    stream_h = logging.StreamHandler()
    stream_h.setFormatter(fmt)
    root.addHandler(stream_h)

    file_h = logging.FileHandler(log_path, encoding="utf-8")
    file_h.setFormatter(fmt)
    root.addHandler(file_h)

    if utc:
        logging.Formatter.converter = time.gmtime

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram.httpx").setLevel(logging.WARNING)

    logging.getLogger("scoutbot").info(
        "Logging configured: level=%s utc=%s file=%s",
        level,
        utc,
        log_path,
    )
