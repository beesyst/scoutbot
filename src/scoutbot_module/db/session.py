from __future__ import annotations

from pathlib import Path

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine


# Создание SQLite Engine и инициализация схемы
def create_db_engine(db_path: Path) -> Engine:
    url = f"sqlite:///{db_path.resolve()}"
    engine = create_engine(url, echo=False)
    return engine


# Инициализация схемы (создание таблиц)
def init_schema(engine: Engine) -> None:
    from scoutbot_module.db.models import (  # noqa: F401  register models
        AuditLog,
        Project,
        Signal,
        Target,
        TargetLink,
        Watch,
        Workspace,
    )

    SQLModel.metadata.create_all(engine)


# Получение сессии
def get_session(engine: Engine) -> Session:
    return Session(engine)
