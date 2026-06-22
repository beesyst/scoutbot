#!/usr/bin/env bash
set -euo pipefail

# Если uv не установлен - ставим
if ! command -v uv >/dev/null 2>&1; then
  echo "[install] uv not found, installing..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

# Создаем .env из .env.example, если .env еще нет
if [ ! -f .env ] && [ -f .env.example ]; then
  echo "[init] .env not found, creating from .env.example"
  cp .env.example .env
  echo "[init] Please edit .env and set real secrets"
fi

# Сетап зависимостей строго из uv.lock
echo "[run] syncing dependencies from uv.lock..."
uv sync --frozen --extra dev

# Запуск ScoutBot
echo "[run] starting ScoutBot..."
uv run --frozen --extra dev python config/start.py "$@"
