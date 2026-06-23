from __future__ import annotations

from pathlib import Path

from scoutbot_module.db.session import create_db_engine, init_schema


def run_migrations(db_path: Path) -> None:
    engine = create_db_engine(db_path)
    init_schema(engine)
    engine.dispose()
