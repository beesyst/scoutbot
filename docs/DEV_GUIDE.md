# DEV_GUIDE — ScoutBot

## Purpose

Этот документ описывает:

- как запускать `ScoutBot`;
- как работать с окружением и зависимостями через `uv`;
- где смотреть логи и артефакты;
- как устроены SQLite, seed YAML и `changedetection.io`;
- как вести разработку в рамках SDLC-light без Issue/PR overhead;
- как формулировать задачи для Copilot / AI.

## Related project docs

Этот документ используется вместе с:

- `docs/ROADMAP.md` — этапы, итерации, scope, artifacts, checks, DoD;
- `docs/ARCHITECTURE.md` — архитектура ScoutBot;
- `docs/SPEC.md` — основные runtime/data contracts;
- `docs/SDLC.md` — lightweight process, change levels, required checks;
- `docs/SECURITY.md` — secure development rules.

Правило:

> `DEV_GUIDE` не заменяет `ROADMAP`, `ARCHITECTURE`, `SPEC`, `SDLC` и `SECURITY`, а помогает применять их на практике.

## Требования

- Python 3.14+
- `uv`
- Self-hosted `changedetection.io`
- Telegram Bot Token
- SQLite

## Процесс разработки

В ScoutBot используется прямой Roadmap-driven workflow без Issue/branch/PR overhead.

Фактический путь:

```text
ROADMAP iteration
→ main worktree
→ code
→ tests
→ logs/artifacts verification
→ commit
→ direct push to main
```

Это осознанно упрощённый процесс для маленького self-hosted проекта.

Главное правило:

> Отсутствие Issue/branch/PR не отменяет дисциплину: каждая итерация должна быть ограничена scope из ROADMAP, проверена тестами, логами и артефактами.

## Роли документов

### ROADMAP

`docs/ROADMAP.md` отвечает на вопросы:

- какая итерация выполняется сейчас;
- зачем она нужна;
- что входит и не входит в scope;
- какие artifacts ожидаются;
- какие checks обязательны;
- что считается DoD.

### DEV_GUIDE

`docs/DEV_GUIDE.md` отвечает на вопросы:

- как запускать проект;
- как выполнять проверки;
- как работать с зависимостями;
- как давать задачи Copilot / AI;
- как не нарушать source-of-truth и security boundaries.

### SDLC / SECURITY

`docs/SDLC.md` и `docs/SECURITY.md` задают:

- change levels;
- required checks;
- security-sensitive зоны;
- правила работы с secrets, env, URL, external payloads, filesystem paths.

## Direct-main development workflow

### Типовой цикл

1. Открыть `docs/ROADMAP.md`.
2. Выбрать текущую итерацию.
3. Убедиться, что задача не выходит за scope итерации.
4. Определить `change level`:
   - `low-risk`;
   - `runtime-risk`;
   - `security-sensitive`.

5. Внести изменения прямо в текущем worktree.
6. Прогнать тесты.
7. Выполнить нужный smoke-check через `./start.sh` или CLI entrypoint.
8. Проверить:
   - `logs/app.log`;
   - `storage/`;
   - SQLite state;
   - отсутствие secret leakage.

9. Обновить docs, если менялся контракт.
10. Сделать атомарный commit.
11. Залить в `main`.

### Что заменяет Issue/PR

Так как Issue и PR не используются, verification evidence фиксируется в трёх местах:

- код и тесты;
- runtime artifacts в `storage/`;
- commit message / commit body.

Рекомендуемый commit body:

```text
Iteration: 1 — Telegram MVP
Change level: runtime-risk

Summary:
- Added Telegram /add flow
- Added target persistence
- Added changedetection sync for active targets

Checks:
- uv run pytest -q
- ./start.sh doctor
- ./start.sh init-db
- ./start.sh sync

Artifacts:
- storage/db/scoutbot.sqlite3
- storage/runs/<run_id>/target_sync.json
- storage/interfaces/sync_result.json

Security:
- No secrets in logs/storage
- Telegram admin allowlist checked
```

### Когда можно делать без длинного commit body

Для `low-risk` docs-only изменений достаточно короткого conventional commit:

```bash
git commit -m "docs(dev-guide): align workflow with direct-main process"
```

Для `runtime-risk` и `security-sensitive` изменений лучше добавлять commit body с verification evidence.

## Change levels

### low-risk

Изменения без влияния на runtime-контракт:

- docs;
- комментарии;
- тестовые fixtures;
- безопасный naming cleanup;
- неисполняемый README/DEV_GUIDE текст.

Минимум проверок:

```bash
uv run pytest -q
```

Если менялись только docs и тесты не затронуты, можно ограничиться ручной проверкой markdown, но это должно быть осознанно.

### runtime-risk

Изменения, влияющие на runtime behavior:

- `config/start.py`;
- CLI dispatch;
- settings validation;
- SQLite schema/state;
- changedetection sync;
- Telegram UX;
- webhook processing;
- discovery;
- dedupe/classification;
- storage artifacts.

Минимум проверок:

```bash
uv run pytest -q
./start.sh doctor
```

Плюс smoke-check того entrypoint, который реально затронут:

```bash
./start.sh init-db
./start.sh import-seed config/seeds/noders.yml
./start.sh sync
./start.sh telegram
./start.sh webhook
```

### security-sensitive

Изменения на trust boundary:

- env/secrets;
- Telegram token/admin allowlist;
- changedetection API key;
- webhook secret;
- external payload parsing;
- URL validation;
- HTML parsing;
- social/link discovery;
- filesystem paths;
- SQLite migrations;
- dependency surface.

Минимум проверок:

```bash
uv run pytest -q
./start.sh doctor
```

Дополнительно проверить:

- secret leakage в `logs/` и `storage/`;
- path traversal;
- malformed URL;
- oversized payload;
- webhook auth failure;
- changedetection unavailable/degraded behavior.

## Установка и зависимости

В проекте используется `uv`.

Источник правды:

- `pyproject.toml` — зависимости и constraints;
- `uv.lock` — зафиксированные версии.

`uv.lock` коммитится в репозиторий и не добавляется в `.gitignore`.

## Обычный запуск

Основной entrypoint:

```bash
./start.sh
```

`start.sh` должен:

- проверить наличие `uv`;
- если `uv` отсутствует — установить его;
- создать `.env` из `.env.example`, если `.env` отсутствует;
- выполнить `uv sync --frozen --extra dev`;
- запустить `config/start.py`;
- не менять `uv.lock`.

Правило:

> Обычный запуск `./start.sh` не должен менять `pyproject.toml` или `uv.lock`.

Если после обычного запуска изменился `uv.lock`, это проблема dependency workflow. Её нужно исправить до push в `main`.

## start.sh

Рекомендуемый стартовый файл:

```bash
#!/usr/bin/env bash
set -euo pipefail

if ! command -v uv >/dev/null 2>&1; then
  echo "[install] uv not found, installing..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

if [ ! -f .env ] && [ -f .env.example ]; then
  echo "[init] .env not found, creating from .env.example"
  cp .env.example .env
  echo "[init] Please edit .env and set real secrets"
fi

echo "[run] syncing dependencies from uv.lock..."
uv sync --frozen --extra dev

echo "[run] starting ScoutBot..."
uv run --frozen --extra dev python config/start.py "$@"
```

## Прямой запуск через uv

Для прямого запуска без `start.sh`:

```bash
uv sync --frozen --extra dev
uv run --frozen --extra dev python config/start.py
```

Для конкретной CLI-команды:

```bash
uv run --frozen --extra dev python config/start.py doctor
uv run --frozen --extra dev python config/start.py init-db
uv run --frozen --extra dev python config/start.py sync
uv run --frozen --extra dev python config/start.py telegram
uv run --frozen --extra dev python config/start.py webhook
uv run --frozen --extra dev python config/start.py digest
uv run --frozen --extra dev python config/start.py backup
uv run --frozen --extra dev python config/start.py audit
```

В обычной разработке предпочтительный entrypoint — `./start.sh`.

## Базовые команды

| Что сделать                    | Команда                                              |
| ------------------------------ | ---------------------------------------------------- |
| Установить зависимости по lock | `uv sync --frozen --extra dev`                       |
| Запустить ScoutBot             | `./start.sh`                                         |
| Прямой запуск                  | `uv run --frozen --extra dev python config/start.py` |
| Запустить тесты                | `uv run pytest -q`                                   |
| Добавить runtime dependency    | `uv add <pkg>`                                       |
| Добавить dev dependency        | `uv add --optional dev <pkg>`                        |
| Добавить docs dependency       | `uv add --optional docs <pkg>`                       |
| Удалить dependency             | `uv remove <pkg>`                                    |
| Дерево зависимостей            | `uv tree`                                            |
| Обновить lock                  | `uv lock --upgrade`                                  |
| Обновить конкретный пакет      | `uv lock --upgrade-package <pkg>`                    |

## Управление зависимостями

### Добавить runtime-зависимость

```bash
uv add <package>
./start.sh
uv run pytest -q
git status
```

Коммитить нужно оба файла:

```bash
git add pyproject.toml uv.lock
git commit -m "chore(deps): add <package>"
```

### Добавить dev-зависимость

Dev-зависимости оформлены как optional extra `dev`:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "ruff>=0.8",
]
```

Добавлять dev-зависимость:

```bash
uv add --optional dev <package>
./start.sh
uv run pytest -q
git status
```

Коммитить нужно оба файла:

```bash
git add pyproject.toml uv.lock
git commit -m "chore(deps): add <package>"
```

### Добавить docs-зависимость

Docs-зависимости оформлены как optional extra `docs`:

```toml
[project.optional-dependencies]
docs = [
    "mkdocs>=1.6,<2.0",
    "mkdocs-material>=9.6,<10.0",
]
```

Добавлять docs-зависимость:

```bash
uv add --optional docs <package>
uv sync --frozen --extra docs
uv run --frozen --extra docs mkdocs build --strict
git status
```

Коммитить нужно оба файла:

```bash
git add pyproject.toml uv.lock
git commit -m "chore(deps): add docs dependency"
```

### Если зависимость добавлена руками в pyproject.toml

Ручное редактирование допустимо, но после него обязательно обновить lockfile:

```bash
uv lock
./start.sh
uv run pytest -q
git status
```

Коммитить нужно оба файла:

```bash
git add pyproject.toml uv.lock
git commit -m "chore(deps): update dependencies"
```

### Удалить зависимость

```bash
uv remove <package>
./start.sh
uv run pytest -q
git status
```

Коммитить нужно оба файла:

```bash
git add pyproject.toml uv.lock
git commit -m "chore(deps): remove <package>"
```

### Обновить конкретную зависимость

```bash
uv lock --upgrade-package <package>
./start.sh
uv run pytest -q
git status
```

Если менялся только lockfile:

```bash
git add uv.lock
git commit -m "chore(deps): update <package>"
```

Если вместе с этим менялся `pyproject.toml`, коммитить оба файла:

```bash
git add pyproject.toml uv.lock
git commit -m "chore(deps): update <package>"
```

### Массовое обновление зависимостей

Массовый апгрейд делать отдельным commit, не смешивать с feature/fix задачами:

```bash
uv lock --upgrade
./start.sh
uv run pytest -q
git status
```

Коммит:

```bash
git add uv.lock
git commit -m "chore(deps): update locked dependencies"
```

## Release / versioning

В проекте используется `release-please`.

Файлы:

```text
.github/release-please/config.json
.github/release-please/manifest.json
.github/workflows/release-please.yml
```

Правила:

- `pyproject.toml.version` не менять вручную в обычных feature/fix/docs задачах;
- release bump делает `release-please`;
- `CHANGELOG.md`, tags и release metadata не трогать, если задача явно не про релиз;
- если задача не про релиз, в verification note писать:

```text
version not changed
```

Если dependencies не менялись:

```text
uv.lock not changed
```

Если dependencies менялись, `uv.lock` должен быть обновлён и закоммичен вместе с `pyproject.toml`.

## pyproject.toml baseline

Актуальный baseline должен быть согласован с `release-please` manifest.

```toml
[build-system]
requires = ["setuptools", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "scoutbot"
version = "0.0.0"
description = "Telegram-first self-hosted competitor and public source monitoring assistant"
readme = "README.ru.md"
requires-python = ">=3.14"
dependencies = [
    "pyyaml>=6.0.3",
    "python-dotenv>=1.2.0",
    "python-telegram-bot>=22.0,<23.0",
    "pydantic>=2.0,<3.0",
    "fastapi>=0.115,<1.0",
    "uvicorn>=0.30,<1.0",
    "httpx>=0.28,<1.0",
    "sqlmodel>=0.0.22,<0.1",
    "beautifulsoup4>=4.12,<5.0",
    "lxml>=5.0,<7.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "ruff>=0.8",
    "httpx>=0.28,<1.0",
]
docs = [
    "mkdocs>=1.6,<2.0",
    "mkdocs-material>=9.6,<10.0",
]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
markers = [
    "slow: tests that involve external services, webhook flows, network calls, or slow filesystem checks",
    "integration: tests that require changedetection.io, Telegram, or other external service boundaries",
]

[tool.ruff]
line-length = 100
target-version = "py314"

[tool.ruff.lint]
select = [
    "E",
    "F",
    "I",
    "B",
    "UP",
]
ignore = []

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
line-ending = "lf"
```

Важно:

```text
changedetection.io не добавляется в dependencies.
```

Он запускается отдельным сервисом и управляется через REST API.

## Локальный preview docs

```bash
uv sync --frozen --extra docs
uv run --frozen --extra docs mkdocs serve
```

Strict build:

```bash
uv sync --frozen --extra docs
uv run --frozen --extra docs mkdocs build --strict
```

## changedetection.io

### Важное решение

`changedetection.io` не подключается как Python dependency внутри ScoutBot.

Правильно:

```text
ScoutBot
  → REST API
changedetection.io
```

Неправильно:

```text
import changedetectionio
```

Причина: `changedetection.io` — отдельное приложение/engine. ScoutBot должен управлять им через HTTP API и не зависеть от его внутренних Python-модулей.

### Dev запуск changedetection.io

Рекомендуемый dev-путь:

```bash
docker compose -f compose.changedetection.yml up -d
```

Минимальный compose:

```yaml
services:
  changedetection:
    image: dgtlmoon/changedetection.io:0.55.7
    container_name: scoutbot-changedetection
    restart: unless-stopped
    ports:
      - "127.0.0.1:5000:5000"
    volumes:
      - changedetection-data:/datastore

volumes:
  changedetection-data:
```

Правила:

- не открывать `changedetection.io` в публичный интернет без auth/reverse-proxy hardening;
- API key хранить только в env;
- не логировать API key;
- не использовать `changedetection.io` как runtime state source of truth для ScoutBot;
- changedetection watch UUID синхронизировать обратно в SQLite.

## Установка и запуск

### 1. Клонировать проект

```bash
git clone <repo-url> scoutbot
cd scoutbot
```

### 2. Создать `.env`

```bash
cp .env.example .env
```

Заполнить:

```bash
TELEGRAM_BOT_TOKEN=
TELEGRAM_ADMIN_IDS=
TELEGRAM_ALERT_CHAT_ID=

CHANGEDETECTION_BASE_URL=http://127.0.0.1:5000
CHANGEDETECTION_API_KEY=

SCOUTBOT_WEBHOOK_SECRET=change-me
SCOUTBOT_WEBHOOK_URL=http://127.0.0.1:8000/webhooks/changedetection

AI_ENABLED=false
```

`.env` не коммитится.

### 3. Поднять changedetection.io

```bash
docker compose -f compose.changedetection.yml up -d
```

По умолчанию `changedetection.io` должен быть доступен только локально:

```text
127.0.0.1:5000
```

### 4. Запустить диагностику

```bash
./start.sh doctor
```

### 5. Создать SQLite DB

```bash
./start.sh init-db
```

### 6. Импортировать seed

```bash
./start.sh import-seed config/seeds/noders.yml
```

### 7. Синхронизировать targets в changedetection.io

```bash
./start.sh sync
```

### 8. Запустить Telegram bot

```bash
./start.sh telegram
```

### 9. Запустить webhook receiver

Во втором терминале:

```bash
./start.sh webhook
```

## CLI modes

```bash
./start.sh
./start.sh doctor
./start.sh init-db
./start.sh import-seed config/seeds/noders.yml
./start.sh export-seed storage/exports/noders.export.yml
./start.sh sync
./start.sh telegram
./start.sh webhook
./start.sh routes
```

## Runtime mode

`config/settings.yml` содержит:

```yaml
run:
  mode: "telegram"
```

Если `./start.sh` вызван без аргументов, `config/start.py` использует `run.mode`.

Явные CLI args имеют приоритет на один запуск и не меняют `config/settings.yml`.

## config/start.py contract

`config/start.py` — единственная главная точка запуска.

Он должен:

- найти project root;
- загрузить `.env`;
- загрузить `config/settings.yml`;
- валидировать settings fail-fast;
- создать директории;
- настроить logging;
- распарсить CLI args;
- dispatch в нужный runtime/CLI mode.

Ожидаемые команды:

```text
no args       → run.mode из settings
telegram      → Telegram bot
webhook       → FastAPI webhook receiver
doctor        → diagnostics
init-db       → SQLite schema init
sync          → SQLite targets → changedetection watches
import-seed   → YAML seed → SQLite
export-seed   → SQLite → YAML
routes        → route diagnostics
```

## Конфигурация

Главный конфиг:

```text
config/settings.yml
```

Пример верхнего уровня:

```yaml
app:
  name: "ScoutBot"
  env: "dev"

run:
  mode: "telegram"

logging:
  level: "INFO"
  clear_logs: false
  utc: true

storage:
  root: "storage"
  db_path: "storage/db/scoutbot.sqlite3"

telegram:
  token_env: "TELEGRAM_BOT_TOKEN"
  admin_ids_env: "TELEGRAM_ADMIN_IDS"
  chat_id_env: "TELEGRAM_ALERT_CHAT_ID"

changedetection:
  base_url: "http://127.0.0.1:5000"
  api_key_env: "CHANGEDETECTION_API_KEY"
  timeout: 20
  interval:
    hours: 6
  fetch_backend: "html_requests"
  webhook_secret_env: "SCOUTBOT_WEBHOOK_SECRET"
  webhook_url_env: "SCOUTBOT_WEBHOOK_URL"

discovery:
  enabled: true
  auto_queue: true
  conf_min: 0.7
  target_links_max: 30
  max_depth: 1
  request_timeout: 10
  max_response_bytes: 1000000
  allow_private_networks: false

ai:
  enabled: false

integrations:
  n8n:
    enabled: false
```

Правила:

- `config/settings.yml` — runtime/config source of truth;
- новые обязательные ключи добавляются в `config/settings.yml`;
- новые обязательные ключи валидируются fail-fast в `src/scoutbot_module/core/settings.py`;
- secrets читаются только через env names;
- `.env` не коммитится;
- обязательные ключи не должны иметь скрытых дефолтов в коде.

## Source of truth

В ScoutBot есть три разных уровня данных.

### Runtime/config source of truth

```text
config/settings.yml
```

Там живут:

- logging;
- storage paths;
- Telegram env key names;
- changedetection URL/API key env name;
- discovery policy;
- signal categories;
- integration flags;
- AI disabled flag.

### Runtime state source of truth

```text
storage/db/scoutbot.sqlite3
```

Там живут:

- workspaces;
- projects;
- targets;
- discovered links;
- changedetection watch UUIDs;
- target status;
- signals;
- audit log.

### Seed/import/export

```text
config/seeds/*.yml
storage/exports/*.yml
```

YAML нужен только для:

- стартового импорта;
- примеров;
- backup/export;
- переноса между окружениями.

YAML не является runtime state.

Правильный flow:

```text
config/seeds/noders.yml
  → import
  → SQLite
  → Telegram edits
  → export YAML backup if needed
```

## Seed YAML

Пример `config/seeds/noders.yml`:

```yaml
workspace:
  workspace_id: "noders"
  name: "NODERS"
  description: "Crypto node operators, validators, delegation and blockchain infrastructure monitoring"

projects:
  - project_id: "example-validator"
    name: "Example Validator"
    homepage_url: "https://example-validator.com"
    tags:
      - validator
      - staking
      - delegation

    targets:
      - title: "Homepage"
        url: "https://example-validator.com"
        kind: "website"
        priority: "medium"
        interval:
          hours: 6
        discovery:
          enabled: true
          auto_queue: true
          source_kinds:
            - website
            - blog
            - docs
            - changelog
            - pricing
            - careers
            - rss
            - github
            - telegram
            - social_profile
            - link_aggregator

        children:
          - title: "X profile"
            url: "https://x.com/examplevalidator"
            kind: "social_profile"
            priority: "medium"

          - title: "GitHub"
            url: "https://github.com/examplevalidator"
            kind: "github"
            priority: "high"

          - title: "Telegram"
            url: "https://t.me/examplevalidator"
            kind: "telegram"
            priority: "medium"
```

После импорта этот YAML уже не рабочее состояние. Runtime edits идут в SQLite.

## SQLite модель

Минимальные таблицы:

### workspaces

```text
workspace_id
name
description
created_at
updated_at
```

### projects

```text
project_id
workspace_id
name
homepage_url
tags_json
created_at
updated_at
```

### targets

```text
target_id
project_id
parent_target_id
title
url
normalized_url
kind
priority
status
discovery_status
confidence
interval_json
fetch_backend
include_filters_json
subtractive_selectors_json
ignore_text_json
keywords_json
created_at
updated_at
```

### target_links

```text
link_id
source_target_id
target_id
url
normalized_url
kind
relationship
confidence
status
reason_code
discovered_at
```

### watches

```text
watch_id
target_id
changedetection_uuid
status
last_sync_at
last_error
created_at
updated_at
```

### signals

```text
signal_id
target_id
watch_id
changedetection_uuid
detected_at
category
priority
diff_hash
title
summary
raw_excerpt
url
telegram_message_id
created_at
```

### audit_log

```text
audit_id
actor_telegram_id
action
entity_type
entity_id
payload_json
created_at
```

## Структура проекта

```text
scoutbot/
  start.sh
  pyproject.toml
  uv.lock
  .python-version
  .env.example
  compose.changedetection.yml
  README.ru.md

  config/
    start.py
    settings.yml
    seeds/
      noders.yml

  docs/
    ROADMAP.md
    ARCHITECTURE.md
    SPEC.md
    DEV_GUIDE.md
    SDLC.md
    SECURITY.md

  logs/
    app.log

  storage/
    db/
      scoutbot.sqlite3
    discovery/
    exports/
    interfaces/
    runs/
    signals/

  src/
    scoutbot_module/
      core/
        app.py
        cli.py
        settings.py
        log.py
        paths.py

      db/
        models.py
        session.py
        repo.py
        migrations.py

      changedetection/
        client.py
        payloads.py
        sync.py

      bot/
        app.py
        handlers.py
        keyboards.py
        states.py
        formatters.py
        auth.py

      web/
        app.py
        routes.py
        schemas.py

      discovery/
        homepage.py
        links.py
        feeds.py
        socials.py
        link_aggregators.py

      intelligence/
        classify.py
        dedupe.py
        noise.py
        score.py

      services/
        projects.py
        targets.py
        discovery.py
        signals.py
        notifications.py

  tests/
    test_config.py
    test_db_models.py
    test_changedetection_payloads.py
    test_discovery.py
    test_dedupe.py
    test_webhook.py
    test_smoke.py
```

## Telegram UX

MVP команды:

```text
/start
/help
/add
/projects
/targets
/pause
/resume
/delete
/check
```

Главное меню:

```text
ScoutBot

Projects: 4
Targets: 37
Active: 34
Paused: 3
Signals today: 5

[➕ Add target]
[📋 Projects]
[🎯 Targets]
[🔎 Discovery queue]
[🧪 Check now]
[⚙ Settings]
```

Добавление:

```text
User: /add https://competitor.com

ScoutBot:
Target saved.

Discovered official links:
✅ Homepage
✅ Blog
✅ Docs
✅ GitHub
✅ Telegram
⚠ X profile: queued as public profile page, discovery may be degraded

Created watches: 5
Need confirmation: 1
```

State-changing Telegram commands должны:

- проверять admin allowlist;
- писать изменения в SQLite;
- при необходимости писать audit log;
- не менять YAML seed;
- не логировать Telegram token или sensitive payload.

## Discovery rules

Когда пользователь добавляет URL:

1. ScoutBot сохраняет root target.
2. ScoutBot создаёт discovery run.
3. HTML/RSS/sitemap/link parser ищет ссылки.
4. Найденные links сохраняются в `target_links`.
5. Links с allowlisted `source_kind` и достаточным confidence становятся child targets.
6. Active child targets синхронизируются в `changedetection.io`.

Allowed source kinds v0:

```text
website
blog
docs
changelog
pricing
careers
rss
github
telegram
social_profile
link_aggregator
custom
```

Risky/degraded behavior:

- если source требует auth — status `auth_required`;
- если anti-bot — status `blocked`;
- если URL не поддержан — status `unsupported`;
- если links не найдены — status `no_links_found`.

ScoutBot не должен:

- обходить auth;
- обходить anti-bot;
- скрапить private social data;
- использовать paid APIs без отдельного решения;
- обещать стабильный scraping X/LinkedIn/Instagram.

## Signals

При webhook от `changedetection.io` ScoutBot:

1. валидирует secret;
2. ограничивает payload size;
3. находит watch/target;
4. строит diff hash;
5. проверяет dedupe;
6. классифицирует category/priority простыми правилами;
7. сохраняет `signals`;
8. пишет safe artifact;
9. отправляет Telegram alert.

## Webhook contract

`changedetection.io` отправляет notification webhook в ScoutBot:

```text
POST /webhooks/changedetection?secret=<SCOUTBOT_WEBHOOK_SECRET>
```

Webhook receiver должен:

- проверить secret;
- ограничить payload size;
- найти watch/target;
- сохранить raw-safe event artifact;
- посчитать diff hash;
- проверить dedupe;
- классифицировать signal;
- отправить Telegram alert.

## Signal JSONL example

```json
{
  "signal_id": "sig_20260622_120001_ab12cd",
  "project_id": "example-validator",
  "target_id": "target_networks",
  "watch_id": "watch_123",
  "detected_at": "2026-06-22T12:00:01Z",
  "category": "delegation",
  "priority": "high",
  "diff_hash": "7fdab1...",
  "title": "Example Validator / Networks changed",
  "summary": "Added mainnet/delegation section.",
  "url": "https://example-validator.com/networks"
}
```

## Категории сигналов

Базовые категории:

| Category      | Примеры                                                      |
| ------------- | ------------------------------------------------------------ |
| `delegation`  | delegation, validator, staking, commission, mainnet, testnet |
| `product`     | feature, integration, API, dashboard, network, chain         |
| `pricing`     | pricing, price, enterprise, plan, discount                   |
| `positioning` | leading, secure, institutional, infrastructure               |
| `hiring`      | jobs, careers, engineer, DevOps, BD, sales                   |
| `legal`       | terms, privacy, policy                                       |
| `social`      | Telegram, GitHub, YouTube, X                                 |
| `noise`       | footer, cookie, date, tracking, nav                          |

NODERS-specific keywords:

```text
validator
delegation
staking
commission
uptime
slashing
mainnet
testnet
governance
proposal
IBC
RPC
endpoint
node operator
restaking
AVS
Cosmos
Ethereum
Solana
Polkadot
Near
```

## Noise control

Базовые default filters:

```yaml
subtractive_selectors:
  - "nav"
  - "footer"
  - ".cookie"
  - ".cookies"
  - ".banner"
  - ".newsletter"
  - ".subscribe"
  - ".chat"
  - "script"
  - "style"

ignore_text:
  - "©"
  - "All rights reserved"
  - "Accept cookies"
  - "Subscribe"
```

Telegram action:

```text
[Mark as noise]
```

После mark-as-noise ScoutBot может:

- записать signal как noise;
- обновить target-level ignore rules;
- не спамить аналогичным diff повторно.

## Логи

Основные места:

- `stdout`;
- `logs/app.log`.

Логи на английском языке.

Запрещено логировать:

- `TELEGRAM_BOT_TOKEN`;
- `CHANGEDETECTION_API_KEY`;
- webhook secret;
- raw request headers;
- полный `.env`;
- sensitive payload без необходимости.

Логи должны быть:

- понятными;
- достаточными для диагностики текущей итерации;
- без лишнего debug noise;
- без secret/env dumps.

## Артефакты

Типовые директории:

```text
storage/db/scoutbot.sqlite3
storage/runs/<run_id>/
storage/discovery/<run_id>/
storage/signals/<YYYY-MM-DD>.jsonl
storage/interfaces/
storage/exports/
```

Примеры:

```text
storage/discovery/<run_id>/discovered_links.json
storage/discovery/<run_id>/source_graph.json
storage/discovery/<run_id>/degraded_sources.json
storage/runs/<run_id>/target_sync.json
storage/runs/<run_id>/webhook_event.json
storage/runs/<run_id>/signal_classification.json
storage/signals/2026-06-22.jsonl
storage/interfaces/changedetection_status.json
storage/interfaces/sync_result.json
storage/exports/<workspace>.export.yml
```

Артефакты должны быть:

- воспроизводимыми;
- explainable;
- согласованными с логами;
- согласованными с текущей итерацией ROADMAP;
- безопасными по содержимому.

Не допускается:

- утечка секретов;
- неочевидное изменение JSON/JSONL contract без обновления docs;
- скрытая смена путей или смысла артефакта;
- хранение runtime state в YAML вместо SQLite.

## AI / LLM

AI отключён по умолчанию:

```yaml
ai:
  enabled: false
```

ScoutBot MVP работает детерминированно:

```text
URL
→ fetch/diff через changedetection.io
→ webhook
→ dedupe
→ keyword/category rules
→ Telegram alert
```

AI можно добавить позже только как optional bounded layer:

- краткое human-readable summary;
- daily/weekly digest;
- relevance scoring;
- объяснение “почему это важно”.

AI не должен быть source of truth для факта изменения.

## n8n

n8n не нужен как core.

Допустимый future-вариант:

```text
changedetection.io
  → n8n webhook
  → Telegram / Slack / CRM
```

Но в MVP n8n не должен хранить:

- projects;
- targets;
- discovered links;
- watch UUIDs;
- signals;
- audit log;
- business rules.

Это состояние должно жить в SQLite внутри ScoutBot.

## Проверки перед push в main

Минимум для обычного runtime-risk изменения:

```bash
uv run pytest -q
./start.sh doctor
```

Если затронут SQLite:

```bash
./start.sh init-db
```

Если затронут seed import/export:

```bash
./start.sh import-seed config/seeds/noders.yml
./start.sh export-seed storage/exports/noders.export.yml
```

Если затронут changedetection sync:

```bash
./start.sh sync
```

Если затронут Telegram:

```bash
./start.sh telegram
```

Если затронут webhook:

```bash
./start.sh webhook
```

Проверить:

- `logs/app.log`;
- relevant artifacts in `storage/`;
- no secret leakage;
- SQLite state;
- changedetection watch state;
- docs alignment, если менялся контракт.

## Runtime smoke

1. Поднять `changedetection.io`:

```bash
docker compose -f compose.changedetection.yml up -d
```

2. Запустить:

```bash
./start.sh doctor
./start.sh init-db
./start.sh import-seed config/seeds/noders.yml
./start.sh sync
```

3. Запустить Telegram bot:

```bash
./start.sh telegram
```

4. Во втором терминале:

```bash
./start.sh webhook
```

5. В Telegram:

```text
/start
/add https://example-validator.com
/projects
/targets
```

6. Проверить:

```text
logs/app.log
storage/db/scoutbot.sqlite3
storage/discovery/
storage/runs/
storage/signals/
```

## Документация

Основные документы:

| Файл                   | Назначение                             |
| ---------------------- | -------------------------------------- |
| `docs/ROADMAP.md`      | этапы, итерации, scope, DoD            |
| `docs/ARCHITECTURE.md` | архитектура и ключевые решения         |
| `docs/SPEC.md`         | сущности, контракты, expected behavior |
| `docs/DEV_GUIDE.md`    | запуск, окружение, dev-flow            |
| `docs/SDLC.md`         | lightweight process, checks            |
| `docs/SECURITY.md`     | security rules, trust boundaries       |

Если меняется хотя бы одно из этого:

- runtime behavior;
- config contract;
- CLI;
- Telegram UX;
- SQLite schema;
- changedetection sync;
- webhook contract;
- storage artifacts;
- security boundary;
- dependency surface;

нужно проверить, требуется ли обновить:

- `docs/ROADMAP.md`;
- `README.ru.md`;
- `docs/DEV_GUIDE.md`;
- `docs/ARCHITECTURE.md`;
- `docs/SPEC.md`;
- `docs/SDLC.md`;
- `docs/SECURITY.md`.

## ROADMAP кратко

### Iteration 0 — Skeleton + engine boundary

Цель:

- repo;
- `./start.sh`;
- `config/start.py`;
- `src/scoutbot_module`;
- settings validation;
- logs/storage;
- SQLite schema;
- changedetection client;
- seed import/export;
- sync.

### Iteration 1 — Telegram MVP

Цель:

- Telegram add/list/pause/resume/delete;
- auto-discovery v0;
- child targets;
- changedetection watches;
- webhook receiver;
- Telegram alerts;
- dedupe.

После Iteration 1 проект уже должен быть MVP.

### Iteration 2 — Signal quality

Цель:

- меньше шума;
- categories;
- priority;
- mark-as-noise;
- daily digest v0.

### Iteration 3 — Discovery hardening

Цель:

- source graph v1;
- link aggregator support;
- degraded statuses;
- confirmation mode.

### Later

- RSS/GitHub/public Telegram adapters;
- optional n8n router;
- export/import/workspaces;
- web dashboard;
- optional AI summaries.

## Текущий MVP-контракт

ScoutBot считается MVP-ready, если работает цепочка:

```text
User adds URL in Telegram
→ target saved in SQLite
→ official links/socials discovered and stored
→ allowed links auto-queued
→ changedetection watches created
→ webhook received on change
→ signal saved
→ Telegram alert sent
→ pause/resume/delete works
```

## Практические ограничения

### Social platforms

Соцсети нестабильны как источник:

- могут требовать auth;
- могут ломать HTML;
- могут блокировать automated access;
- могут менять layout;
- могут запрещать scraping ToS.

Поэтому ScoutBot:

- фиксирует найденные social links;
- ставит public profile pages в monitoring только по allowlist/policy;
- не обходит auth/anti-bot;
- помечает проблемные sources как degraded.

### AI

AI не нужен для MVP.

Сначала нужно добиться:

```text
clean targets
clean discovery
clean watches
clean webhook
clean alerts
dedupe
noise control
```

Только потом можно добавлять LLM summaries.

### n8n

n8n не нужен для core.

Возможен как optional router позже, но не как source of truth.

## Copilot / AI usage

Правильный подход:

1. Дать AI контекст текущей ROADMAP-итерации.
2. Ограничить scope.
3. Указать change level.
4. Потребовать проверяемый результат:
   - code;
   - tests;
   - logs;
   - artifacts;
   - commit-ready summary.

5. Не давать AI раздувать архитектуру за пределы итерации.

Неправильный подход:

- просить “сделай как лучше” без итерации и scope;
- не указывать affected files;
- не требовать fail-fast validation;
- не просить сверку с artifacts / logs / DoD;
- не просить указать change level и required checks.

## Copilot / AI prompt template

```text
Нужно внести изменения в проект `scoutbot` (НЕ только в текущий файл).

### Контекст

- Проект: `scoutbot` (`Python 3.14+`, `uv`)
- Архитектура: Telegram-first self-hosted мониторинг публичных источников
- Основной entrypoint: `./start.sh → config/start.py`
- Python package: `src/scoutbot_module`
- External engine: self-hosted `changedetection.io`
- Runtime/config source of truth: `config/settings.yml`
- Runtime state source of truth: SQLite (`storage/db/scoutbot.sqlite3`)
- YAML seed/import/export: `config/seeds/*.yml`, `storage/exports/*.yml`
- Артефакты: `storage/`
- Runtime-логи: `logs/app.log`
- Development workflow: `ROADMAP iteration → main worktree → code → tests → artifacts → commit → direct push to main`
- Основные process/security rules:
  - `docs/ROADMAP.md`
  - `docs/ARCHITECTURE.md`
  - `docs/SPEC.md`
  - `docs/SDLC.md`
  - `docs/SECURITY.md`
  - `docs/DEV_GUIDE.md`
- Issue/branch/PR flow не используется. Verification evidence должно быть отражено в tests, logs, artifacts и commit summary.

### Правила

- Сначала прочитай все перечисленные файлы, потом предлагай и вноси правки.
- Если по ходу нужен ещё файл — добавь его в список и тоже прочитай.
- Сначала соотнеси задачу с текущей итерацией из `docs/ROADMAP.md`; не выходи за её scope.
- Сначала определи `change level`:
  - `low-risk`
  - `runtime-risk`
  - `security-sensitive`
- Для выбранного `change level` определи required checks по `docs/SDLC.md` и `docs/SECURITY.md`.
- Делай только минимально необходимые изменения по KISS.
- Не рефактори вне задачи.
- Не меняй чужой scope итерации.
- Не протаскивай “на будущее” недоделанную архитектуру.
- Не убирай существующие проверки без явной причины.
- Не пиши свой crawler/diff-engine, если задачу закрывает `changedetection.io`.
- Не добавляй AI/LLM в MVP, если задача явно не про optional AI summaries.
- Не добавляй n8n как core/runtime state layer.
- Не превращай YAML seed в runtime state.
- Не добавляй `changedetection.io` как Python dependency в `pyproject.toml`; ScoutBot должен работать с ним через REST API.

### Config / source of truth rules

- Runtime/config source of truth: `config/settings.yml`.
- Runtime state source of truth: SQLite (`storage/db/scoutbot.sqlite3`).
- Seed YAML (`config/seeds/*.yml`) используется только для import/export/bootstrap.
- Обязательные config keys не должны иметь скрытых дефолтов в коде.
- Перед добавлением нового config-блока сначала проверь, нельзя ли переиспользовать уже существующий top-level/shared контракт.
- Не создавай второй source of truth.
- Не дублируй общий runtime/system-level контракт внутри отдельного module/service, если это не требуется текущей итерацией.
- Если добавляется новый обязательный config key, он должен:
  - быть явно описан в `config/settings.yml`;
  - валидироваться в `src/scoutbot_module/core/settings.py`;
  - падать fail-fast с понятной ошибкой при отсутствии.
- Если предлагаешь новый config key, сначала объясни, почему нельзя переиспользовать существующий контракт.
- В ответе явно укажи, какой блок после изменения является source of truth.

### Runtime / changedetection rules

- `changedetection.io` — внешний engine, не часть Python package.
- ScoutBot управляет `changedetection.io` только через REST API.
- `CHANGEDETECTION_API_KEY` читается только из env.
- API key, Telegram token и webhook secret не должны попадать в logs/storage/artifacts.
- Sync path должен быть воспроизводимым:
  - SQLite targets → changedetection watches;
  - changedetection watch UUID → SQLite watches;
  - sync result → `storage/interfaces/` или `storage/runs/<run_id>/`.
- Если changedetection недоступен, должен быть explicit degraded/error state, а не silent success.

### Telegram / state rules

- State-changing Telegram commands должны проверять admin allowlist.
- Telegram edits меняют SQLite, не YAML.
- Добавление target из Telegram должно сохранять audit log.
- Если target порождает discovered links/socials, они должны сохраняться как source graph в SQLite и artifacts.
- Не обходи auth/anti-bot соцсетей.
- Public social/profile/link aggregator sources должны иметь degraded status, если их нельзя корректно обработать.

### Docs / contracts / artifacts

- Если меняется runtime-поведение, config-контракт, CLI, Telegram UX, SQLite schema, changedetection sync, webhook, storage artifacts или docs-contract, проверь, нужно ли обновить:
  - `docs/ROADMAP.md`
  - `README.ru.md`
  - `docs/DEV_GUIDE.md`
  - `docs/ARCHITECTURE.md`
  - `docs/SPEC.md`
  - `docs/SDLC.md`
  - `docs/SECURITY.md`
- Если меняются артефакты, покажи какие именно файлы появятся/изменятся в `storage/`.
- Если меняется JSON/JSONL/meta-контракт, покажи пример одной строки/объекта.
- Если меняется SQLite schema, перечисли таблицы/поля и миграционное поведение.
- После работы дай короткий чеклист для commit/verification note.

### Code style / execution rules

- Соблюдай PEP 8: имена, длина строк, структура.
- Не добавляй никаких комментариев в код.
- Логи, имена полей, JSON/JSONL, runtime messages — на английском языке.
- Все команды запуска, тестов и smoke-check указывай через `uv run` или `./start.sh`.
- Не предлагай второй runtime, второй orchestrator или отдельный сервис без явной необходимости по текущей итерации.

### Release / versioning rules

- Не меняй `version` в `pyproject.toml`, не трогай release metadata, changelog, tags, release workflows и другие release-related файлы, если задача явно не про релиз/версионирование.
- Version bump не делается в обычной feature/fix/docs задаче.
- Если добавляешь зависимости, обнови только dependency declarations и укажи required SCA checks; версию пакета не меняй без явного указания задачи.

### Формат ответа

Ответ строго в формате:

1. `Что прочитал`
2. `План`
3. `Change level`
4. `Required checks`
5. `Source of truth after change`
6. `Было`
7. `Стало`
8. `Почему`
9. `Чеклист`
10. `Commit note`

### Дополнительно к формату

- Без diff.
- Без лишних рассуждений.
- Если нужна новая функция/класс — укажи точное место вставки: файл, класс/функция, до/после какого блока.
- Для тестов перечисли, какие именно тесты нужно добавить/обновить.
- Для каждого нового или изменённого config key укажи:
  - где он живёт;
  - почему именно там;
  - почему это не создаёт второй source of truth.
- Для commit note кратко перечисли, что должно попасть в:
  - `Summary`
  - `Tests`
  - `Artifacts`
  - `Security review`
- Отдельно явно укажи:
  - менялся ли `pyproject.toml.version`;
  - если задача не про релиз, ответ должен быть `version not changed`;

### Задача

<опиши задачу одной фразой>

### Итерация

<укажи номер и название итерации из `docs/ROADMAP.md`>

### Iteration context

<вставь кратко Goal / Scope / Deliverable / Checks / DoD из ROADMAP>

### Файлы

Обязательно прочитай:

- `docs/ROADMAP.md`
- `docs/ARCHITECTURE.md`
- `docs/SPEC.md`
- `docs/SDLC.md`
- `docs/SECURITY.md`
- `docs/DEV_GUIDE.md`
- `README.ru.md`
- `pyproject.toml`
- `config/start.py`
- `config/settings.yml`
- `src/scoutbot_module/core/settings.py`
- `src/scoutbot_module/core/app.py`
- `src/scoutbot_module/core/paths.py`
- `src/scoutbot_module/core/log.py`

Если нужно, добавь и прочитай также:

- `src/scoutbot_module/core/cli.py`
- `src/scoutbot_module/db/models.py`
- `src/scoutbot_module/db/session.py`
- `src/scoutbot_module/db/repo.py`
- `src/scoutbot_module/changedetection/client.py`
- `src/scoutbot_module/changedetection/payloads.py`
- `src/scoutbot_module/changedetection/sync.py`
- `src/scoutbot_module/bot/handlers.py`
- `src/scoutbot_module/bot/keyboards.py`
- `src/scoutbot_module/bot/auth.py`
- `src/scoutbot_module/web/routes.py`
- `src/scoutbot_module/discovery/links.py`
- `src/scoutbot_module/discovery/feeds.py`
- `src/scoutbot_module/discovery/socials.py`
- `src/scoutbot_module/intelligence/dedupe.py`
- `src/scoutbot_module/intelligence/classify.py`
- `tests/test_smoke.py`
- `tests/test_config.py`
- `tests/test_db_models.py`
- `tests/test_changedetection_payloads.py`
- `tests/test_discovery.py`
- `tests/test_webhook.py`
- `tests/test_dedupe.py`

### Ожидаемый результат

- работает ожидаемый entrypoint:
  - `./start.sh`
  - `./start.sh doctor`
  - `./start.sh init-db`
  - `./start.sh sync`
  - `./start.sh telegram`
  - `./start.sh webhook`
  - или другой нужный CLI path;
- `uv run pytest -q` проходит;
- логи остаются понятными;
- артефакты в `storage/` создаются и консистентны;
- SQLite state консистентен;
- новые обязательные keys валидируются fail-fast;
- secrets не попадают в logs/storage;
- required checks для данного `change level` определены и перечислены;
- изменение готово к commit/push в main.
```

## Мини-шаблон для быстрой задачи AI

```text
Project: scoutbot
Iteration: <номер и название из ROADMAP>
Task: <одна фраза>
Change level: <low-risk | runtime-risk | security-sensitive>

Scope:
- Include:
  - ...
- Exclude:
  - ...

Files to read:
- docs/ROADMAP.md
- docs/SDLC.md
- docs/SECURITY.md
- README.ru.md
- config/start.py
- config/settings.yml
- src/scoutbot_module/core/settings.py
- ...

Expected changes:
- ...

Expected checks:
- uv run pytest -q
- ./start.sh doctor
- ...

Expected artifacts:
- storage/...

Output format:
1. Что прочитал
2. План
3. Change level
4. Required checks
5. Source of truth after change
6. Было
7. Стало
8. Почему
9. Чеклист
10. Commit note
```

## Чего не делать

Не делай так:

- не добавляй обязательные ключи только в коде без `settings.yml`;
- не хардкодь runtime-значения без необходимости;
- не смешивай scope нескольких итераций в одном commit;
- не закрывай итерацию только словами “вроде работает”;
- не оставляй изменения без tests / smoke / artifact check;
- не допускай утечки секретов в логи и storage;
- не требуй все security-checks всегда, если они не нужны для данного change level;
- не усложняй решение сверх scope итерации;
- не добавляй `changedetection.io` как Python dependency;
- не пиши собственный crawler/diff-engine;
- не подключай AI в MVP;
- не храни runtime state в YAML;
- не открывай changedetection публично без hardening;
- не обходи auth/ToS соцсетей;
- не добавляй платные API без отдельного решения.

## Быстрый рабочий сценарий

Типовой цикл для разработчика:

1. Открыть `docs/ROADMAP.md`.
2. Выбрать текущую итерацию.
3. Определить `change level`.
4. Внести изменения.
5. Прогнать:

```bash
./start.sh doctor
uv run pytest -q
```

6. Прогнать affected smoke-check:

```bash
./start.sh init-db
./start.sh sync
./start.sh telegram
./start.sh webhook
```

7. Проверить:

```text
logs/app.log
storage/
storage/db/scoutbot.sqlite3
```

8. Проверить secret leakage.
9. Проверить `git status`.
10. Сделать атомарный commit.
11. Push в `main`.

## Commit checklist

Перед commit:

- [ ] scope соответствует текущей ROADMAP-итерации;
- [ ] change level определён;
- [ ] `uv run pytest -q` выполнен или осознанно не нужен для docs-only;
- [ ] нужный `./start.sh ...` smoke выполнен;
- [ ] `logs/app.log` проверен;
- [ ] artifacts в `storage/` проверены;
- [ ] SQLite state проверен, если менялась DB/schema/state logic;
- [ ] secrets не попали в logs/storage;
- [ ] docs обновлены, если менялся контракт;
- [ ] `pyproject.toml.version` не менялся без release-задачи;
- [ ] `uv.lock` менялся только если менялись dependencies.

## Commit message examples

Docs-only:

```bash
git commit -m "docs(dev-guide): align workflow with direct-main process"
```

Runtime feature:

```bash
git commit -m "feat(telegram): add target creation flow"
```

Bug fix:

```bash
git commit -m "fix(sync): handle changedetection unavailable state"
```

Security-sensitive fix:

```bash
git commit -m "fix(webhook): reject invalid changedetection secrets"
```

Dependency update:

```bash
git commit -m "chore(deps): add sqlmodel"
```

## Краткое резюме

ScoutBot развивается маленькими проверяемыми итерациями:

- Telegram-first;
- SQLite state;
- YAML seed/import/export;
- changedetection.io как external engine;
- no AI in MVP;
- KISS;
- logs/artifacts explainability;
- security proportional to change level;
- direct push to main допустим только после tests / smoke / artifact verification.

Главная дисциплина проекта:

```text
ROADMAP scope
→ minimal implementation
→ tests
→ logs/artifacts
→ no secrets
→ atomic commit
→ main
```
