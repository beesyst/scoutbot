from __future__ import annotations

from pathlib import Path


# Поиск корневой директории проекта (где лежит pyproject.toml)
def find_project_root(start_path: Path | None = None) -> Path:
    start = (start_path or Path(__file__).resolve()).resolve()
    for ancestor in [start] + list(start.parents):
        if (ancestor / "pyproject.toml").exists():
            return ancestor
    raise FileNotFoundError(
        f"Cannot find ScoutBot project root: no pyproject.toml found from {start}"
    )


ROOT_DIR = find_project_root()
CONFIG_DIR = ROOT_DIR / "config"
LOGS_DIR = ROOT_DIR / "logs"
STORAGE_DIR = ROOT_DIR / "storage"


def resolve_project_path(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT_DIR / p


# Создание директории, если ее нет, и вернуть путь
def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path
