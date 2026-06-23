from __future__ import annotations

from pathlib import Path

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine


def create_db_engine(db_path: Path) -> Engine:
    url = f"sqlite:///{db_path.resolve()}"
    engine = create_engine(url, echo=False)
    return engine


def init_schema(engine: Engine) -> None:

    SQLModel.metadata.create_all(engine)


def get_session(engine: Engine) -> Session:
    return Session(engine)
