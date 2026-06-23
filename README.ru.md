# ScoutBot — Telegram-first мониторинг конкурентов и публичных источников

**ScoutBot** — self-hosted проект мониторинга публичных источников.

Iteration 1 реализована: Telegram MVP end-to-end с `/add <url>`, bounded discovery v0, `target_links` persistence, auto-queue child targets, changedetection watch sync, webhook receiver, signal persistence, JSONL/artifacts и Telegram alerts.

Текущий статус: Iteration 1 DONE — Telegram MVP end-to-end реализован и покрыт тестами. Полный runtime smoke с реальными Telegram/changedetection.io сервисами требует настроенных env secrets и запущенного self-hosted `changedetection.io`: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ADMIN_IDS`, `TELEGRAM_ALERT_CHAT_ID`, `CHANGEDETECTION_API_KEY`, `SCOUTBOT_WEBHOOK_SECRET`, `SCOUTBOT_WEBHOOK_URL`.

Текущий MVP поток после Iteration 1:

> Указать публичный URL в Telegram → сохранить target в SQLite → bounded discovery на связанные источники → синхронизировать watches в changedetection.io → принять webhook → сохранить signal → отправить alert в Telegram.

Первый прикладной кейс — мониторинг конкурентов для **NODERS**: node operators, validators, staking/delegation campaigns, blockchain infrastructure, networks, docs, changelog, GitHub, public announcements.

Проект не завязан на NODERS и может использоваться для других компаний.

## Ключевая идея

ScoutBot не пишет собственный crawler/diff-engine.

Сейчас ScoutBot управляет:

- settings validation;
- SQLite state;
- seed import/export;
- changedetection sync;
- Telegram UX;
- bounded discovery v0;
- webhook processing;
- signal persistence;
- Telegram alerts;
- reproducible artifacts в `storage/`.

Низкоуровневый fetch/diff/snapshot слой делегируется внешнему self-hosted `changedetection.io`.

Текущая схема после Iteration 1:

```text
Telegram
  → ScoutBot bot
  → SQLite
  → bounded discovery
  → changedetection.io REST API
  → changedetection.io watches/diff
  → ScoutBot webhook
  → signals/artifacts
  → Telegram alerts
```

## Текущий статус

Iteration 0 — DONE:

- `start.sh` / `config/start.py`;
- settings validation;
- logs / storage;
- SQLite schema;
- seed import/export;
- changedetection REST client;
- sync path;
- `doctor` / `init-db` / `import-seed` / `export-seed` / `sync` / `routes`;
- degraded artifacts when changedetection API key is missing.

Iteration 1 — DONE:

- Telegram bot;
- webhook receiver;
- bounded discovery v0;
- Telegram alerts;
- pause/resume/delete/check from Telegram;
- inline keyboard target actions;
- dedupe/classification placeholder;
- signal JSONL/artifacts.

## Слои проекта

- **core** — запуск, settings validation, logging, paths, CLI dispatch;
- **SQLite state** — runtime source of truth для workspaces, projects, targets, target links, watches, signals, audit log;
- **changedetection.io** — внешний engine для fetch/diff/snapshots/change detection;
- **Telegram UI** — add/list/pause/resume/delete/check, inline actions, alerts;
- **discovery** — bounded extraction public links, RSS, sitemap, common paths, socials, link aggregators;
- **webhook** — приём событий от changedetection.io;
- **intelligence** — dedupe, category, priority, placeholder rules;
- **services** — use-case слой между Telegram, DB, discovery, changedetection и notifications;
- **artifacts** — воспроизводимые evidence-файлы в `storage/`.

## Что делает ScoutBot

### Сейчас реализовано

- запуск через `./start.sh -> config/start.py`;
- fail-fast validation `config/settings.yml`;
- logging и базовые директории `logs/` и `storage/`;
- SQLite schema и runtime state в `storage/db/scoutbot.sqlite3`;
- import seed YAML в SQLite;
- export workspace из SQLite в YAML;
- REST client boundary к self-hosted `changedetection.io`;
- sync queued/active/paused/deleted targets из SQLite в `changedetection.io`;
- `./start.sh telegram`;
- `./start.sh webhook`;
- Telegram commands;
- bounded discovery;
- auto-queue allowed links;
- webhook signal processing;
- signal JSONL/artifacts;
- Telegram alerts;
- pause/resume/delete sync behavior.

### MVP flow после Iteration 1

- добавить target из Telegram;
- принять URL и поставить его в runtime state;
- автоматически найти связанные официальные ссылки;
- сохранить `target_links`;
- auto-queue allowed child targets;
- создать/обновить watches в self-hosted `changedetection.io`;
- принять webhook при изменении;
- сохранить signal в SQLite и `storage/`;
- отправить alert в Telegram;
- управлять targets из Telegram: pause / resume / delete / check.

## Что ScoutBot НЕ делает в MVP

ScoutBot в MVP не должен:

- писать свой crawler/diff-engine;
- обходить auth/anti-bot;
- скрапить private social data;
- требовать AI/LLM;
- требовать DeepSeek/OpenAI/Gemini;
- требовать n8n;
- хранить runtime state в YAML;
- открывать `changedetection.io` наружу без hardening;
- использовать paid API без отдельного решения;
- обещать стабильный scraping X/LinkedIn/Instagram;
- превращаться в web-admin/platform до появления реальной боли.

## Бесплатно ли решение

Software-cost MVP может быть бесплатным:

| Компонент                        | Стоимость                      |
| -------------------------------- | ------------------------------ |
| ScoutBot                         | свой open-source/private код   |
| self-hosted `changedetection.io` | бесплатно                      |
| SQLite                           | бесплатно                      |
| Telegram Bot API                 | бесплатно                      |
| n8n self-hosted                  | опционально, не нужен для MVP  |
| AI / DeepSeek / OpenAI           | не нужен для MVP               |
| VPS                              | нужен, если нет своего сервера |

`changedetection.io` может использоваться как self-hosted сервис. Платный сайт/подписка — это hosted cloud вариант. Для ScoutBot MVP используется self-hosted engine.

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

## changedetection.io

`changedetection.io` используется как внешний engine.

ScoutBot не импортирует его как Python library и не добавляет `changedetection.io` в `pyproject.toml`.

Правильная схема:

```text
ScoutBot
  → REST API
changedetection.io
```

`changedetection.io` отвечает за:

- periodic checks;
- HTML/JSON/PDF/RSS monitoring;
- diff;
- snapshots;
- CSS/XPath/JSONPath/jq filters;
- ignore filters;
- trigger filters;
- notification webhook.

ScoutBot отвечает за:

- Telegram UX;
- source graph;
- SQLite state;
- sync targets → watches;
- webhook processing;
- dedupe;
- classification;
- Telegram formatting;
- artifacts.

## n8n

n8n не нужен как core.

Допустимый future-вариант:

```text
changedetection.io
  → n8n webhook
  → Telegram / Slack / CRM
```

Но в MVP n8n не должен хранить:

- workspaces;
- projects;
- targets;
- discovered links;
- watch UUIDs;
- signals;
- audit log;
- business rules.

Это состояние должно жить в SQLite внутри ScoutBot.

## Source of truth

В ScoutBot есть три разных уровня данных.

### Runtime/config source of truth

```text
config/settings.yml
```

Там живут:

- logging;
- storage paths;
- workspace defaults;
- Telegram env key names;
- changedetection URL/API key env names;
- webhook settings;
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

## Как работает добавление сайта

Пример:

```text
User:
/add https://example-validator.com
```

Текущий flow:

1. проверяет Telegram admin allowlist;
2. валидирует URL;
3. нормализует URL;
4. создаёт workspace/project/target в SQLite;
5. пишет audit log;
6. запускает bounded discovery;
7. ищет:
   - homepage links;
   - RSS/Atom;
   - sitemap candidates;
   - blog/news;
   - docs/changelog;
   - pricing/services;
   - careers;
   - GitHub;
   - Telegram;
   - YouTube;
   - social profile links;
   - link aggregators;
8. сохраняет найденные links как `target_links`;
9. auto-queues allowed links;
10. синхронизирует root/child targets в `changedetection.io`;
11. отправляет отчёт в Telegram с summary и inline actions.

## Target не обязательно сайт в Iteration 1

Target может быть любым публичным URL.

Примеры:

```text
https://example-validator.com
https://x.com/examplevalidator
https://t.me/examplevalidator
https://github.com/examplevalidator
https://youtube.com/@examplevalidator
https://linktr.ee/examplevalidator
```

Если пользователь добавляет social profile или link aggregator, ScoutBot:

1. сохраняет его как root target;
2. определяет `source_kind`;
3. пытается извлечь публичные links;
4. если находит официальный сайт, GitHub, Telegram, YouTube, docs, blog — сохраняет их под project;
5. allowed links ставит в очередь мониторинга;
6. если источник недоступен — фиксирует degraded status.

ScoutBot не должен обходить auth/anti-bot и не должен гарантировать стабильность social scraping.

## Source kinds

Поддерживаемые типы источников v0:

| Kind              | Описание                                    |
| ----------------- | ------------------------------------------- |
| `website`         | обычная web-страница                        |
| `blog`            | блог/news                                   |
| `docs`            | документация                                |
| `changelog`       | changelog/releases                          |
| `pricing`         | pricing/services                            |
| `careers`         | вакансии                                    |
| `rss`             | RSS/Atom feed                               |
| `github`          | GitHub org/repo/releases                    |
| `telegram`        | публичный Telegram channel                  |
| `social_profile`  | X/LinkedIn/YouTube/etc. public profile page |
| `link_aggregator` | Linktree/Beacons/etc.                       |
| `custom`          | ручной источник                             |

## Telegram UX

Implemented in Iteration 1:

- `/start`;
- `/help`;
- `/add`;
- `/projects`;
- `/targets`;
- `/pause`;
- `/resume`;
- `/delete`;
- `/check`;
- inline keyboard UX;
- Telegram alerts.

## Архитектура runtime

Текущий runtime:

```text
./start.sh routes
./start.sh doctor
./start.sh init-db
./start.sh import-seed
./start.sh export-seed
./start.sh sync
./start.sh telegram
./start.sh webhook
changedetection.io
```

## Структура проекта

```text
scoutbot/
├── start.sh
├── pyproject.toml
├── uv.lock
├── .python-version
├── .env.example
├── compose.changedetection.yml
├── README.ru.md
│
├── config/
│   ├── start.py
│   ├── settings.yml
│   └── seeds/
│       └── noders.yml
│
├── docs/
│   ├── ROADMAP.md
│   ├── ARCHITECTURE.md
│   ├── SPEC.md
│   ├── DEV_GUIDE.md
│   ├── SDLC.md
│   └── SECURITY.md
│
├── logs/
│   └── app.log
│
├── storage/
│   ├── db/
│   │   └── scoutbot.sqlite3
│   ├── discovery/
│   ├── exports/
│   ├── interfaces/
│   ├── runs/
│   └── signals/
│
├── src/
│   └── scoutbot_module/
│       ├── bot/
│       ├── changedetection/
│       ├── core/
│       ├── db/
│       ├── discovery/
│       ├── intelligence/
│       ├── services/
│       └── web/
│
└── tests/
    ├── test_changedetection_payloads.py
    ├── test_config.py
    ├── test_db_models.py
    ├── test_dedupe.py
    ├── test_discovery.py
    ├── test_smoke.py
    ├── test_telegram.py
    └── test_webhook.py
```

## Технологический стек

- **Python 3.14+**
- **uv**
- **src-layout**
- **python-telegram-bot** — Telegram bot
- **FastAPI + Uvicorn** — webhook receiver
- **SQLite + SQLModel** — runtime state
- **httpx** — REST API client к `changedetection.io`
- **PyYAML** — settings/seed import/export
- **python-dotenv** — `.env` loading
- **BeautifulSoup4 + lxml** — bounded HTML discovery
- **pytest** — тесты
- **ruff** — lint
- **changedetection.io** — external website change detection engine

## pyproject baseline

```toml
[build-system]
requires = ["setuptools", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "scoutbot"
version = "0.0.0"
description = "Telegram-first self-hosted competitor and source monitoring assistant"
readme = "README.ru.md"
requires-python = ">=3.14"
dependencies = [
    "pyyaml>=6.0.3",
    "python-dotenv>=1.2.2",
    "python-telegram-bot>=22.8,<23",
    "pydantic>=2.13.0,<3",
    "fastapi>=0.136.0,<0.137",
    "uvicorn>=0.49.0,<0.50",
    "httpx>=0.28.0,<0.29",
    "sqlmodel>=0.0.27,<0.1",
    "beautifulsoup4>=4.14.0,<5",
    "lxml>=6.0.0,<7",
]
```

Важно:

```text
changedetection.io не добавляется в dependencies.
```

Он запускается отдельным сервисом и управляется через REST API.

## Release / versioning

Версия проекта управляется через release-please.

Файлы release-please:

```text
.github/release-please/config.json
.github/release-please/manifest.json
.github/workflows/release-please.yml
```

Правила:

- `pyproject.toml.version` не меняется вручную в обычных feature/fix/docs задачах;
- стартовая версия проекта — `0.0.0`;
- version bump делает release-please;
- dependency changes обновляют `pyproject.toml` и `uv.lock`, но не версию пакета;
- release-related файлы не трогаются, если задача явно не про release/versioning.

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

### 3. Поднять changedetection.io

```bash
docker compose -f compose.changedetection.yml up -d
```

Минимальный `compose.changedetection.yml`:

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

По умолчанию `changedetection.io` должен быть доступен только локально:

```text
127.0.0.1:5000
```

Не открывать его наружу без reverse proxy/auth/HTTPS.

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

### 7. Экспортировать workspace в YAML backup

```bash
./start.sh export-seed storage/exports/noders.export.yml
```

### 8. Синхронизировать targets в changedetection.io

```bash
./start.sh sync
```

Если `CHANGEDETECTION_API_KEY` не задан, `sync` должен завершаться как explicit degraded artifact, а не как silent success.

### 9. Запустить Telegram bot

```bash
./start.sh telegram
```

Требует `TELEGRAM_BOT_TOKEN` и `TELEGRAM_ADMIN_IDS`. Без env должен завершаться explicit error.

### 10. Запустить webhook receiver

```bash
./start.sh webhook
```

Требует `SCOUTBOT_WEBHOOK_SECRET`. Без секрета пишет warning и отклоняет запросы.

## start.sh

Единая точка запуска:

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
uv run --frozen --extra dev python3 config/start.py "$@"
```

Обычный запуск не должен менять `pyproject.toml` или `uv.lock`.

## Команды

```bash
./start.sh
```

Запускает режим из `config/settings.yml → run.mode`.

Текущие команды:

```bash
./start.sh
./start.sh routes
./start.sh doctor
./start.sh init-db
./start.sh import-seed config/seeds/noders.yml
./start.sh export-seed storage/exports/noders.export.yml
./start.sh sync
./start.sh telegram
./start.sh webhook
```

```bash
./start.sh doctor
```

Проверяет окружение, settings, storage, SQLite, Telegram env, changedetection API.

```bash
./start.sh init-db
```

Создаёт SQLite schema.

```bash
./start.sh import-seed config/seeds/noders.yml
```

Импортирует seed YAML в SQLite.

```bash
./start.sh export-seed storage/exports/noders.export.yml
```

Экспортирует текущее SQLite state в YAML backup.

```bash
./start.sh sync
```

Синхронизирует targets из SQLite в `changedetection.io`. Без `CHANGEDETECTION_API_KEY` должен быть explicit degraded.

```bash
./start.sh telegram
```

Запускает Telegram bot. Требует Telegram env.

```bash
./start.sh webhook
```

Запускает webhook receiver. Требует `SCOUTBOT_WEBHOOK_SECRET`; без секрета запросы будут отклоняться.

```bash
./start.sh routes
```

Показывает доступные CLI routes.

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
  mode: "routes"

workspace:
  default_name: "NODERS"

logging:
  level: "INFO"
  clear_logs: true
  utc: true

storage:
  root: "storage"
  db_path: "storage/db/scoutbot.sqlite3"

telegram:
  token_env: "TELEGRAM_BOT_TOKEN"
  admin_ids_env: "TELEGRAM_ADMIN_IDS"
  chat_id_env: "TELEGRAM_ALERT_CHAT_ID"

webhook:
  host: "127.0.0.1"
  port: 8000
  path: "/webhooks/changedetection"
  body_bytes_max: 131072

changedetection:
  base_url: "http://127.0.0.1:5000"
  api_key_env: "CHANGEDETECTION_API_KEY"
  timeout: 20
  default_interval:
    hours: 6
  default_fetch_backend: "html_requests"
  webhook_secret_env: "SCOUTBOT_WEBHOOK_SECRET"
  webhook_url_env: "SCOUTBOT_WEBHOOK_URL"

discovery:
  enabled: true
  auto_queue: true
  target_links_max: 30
  max_depth: 1
  request_timeout: 10
  max_response_bytes: 1000000
  allow_private_networks: false

signals:
  dedupe_enabled: true
  body_excerpt_chars: 1000
  categories:
    pricing: ["pricing", "price"]
    delegation: ["delegation", "staking"]
    product: ["feature", "api"]

ai:
  enabled: false

integrations:
  n8n:
    enabled: false
```

Правила:

- новые обязательные ключи добавляются в `config/settings.yml`;
- новые обязательные ключи валидируются fail-fast в `src/scoutbot_module/core/settings.py`;
- secrets читаются только через env;
- `.env` не коммитится.

## Seed для NODERS

Пример:

```yaml
workspace:
  name: "NODERS"
  description: "Node operators, validators, staking, and blockchain infrastructure monitoring"

projects:
  - name: "NodeOps"
    homepage_url: "https://nodeops.xyz"
    tags:
      - "node-operators"
      - "staking"
    targets:
      - title: "NodeOps Homepage"
        url: "https://nodeops.xyz"
        kind: "website"
        priority: "high"
```

После импорта этот YAML уже не рабочее состояние. Runtime edits идут в SQLite.

## SQLite модель

Минимальные таблицы:

### `workspaces`

```text
workspace_id
name
description
created_at
updated_at
```

### `projects`

```text
project_id
workspace_id
name
homepage_url
tags_json
created_at
updated_at
```

### `targets`

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

### `target_links`

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

### `watches`

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

### `signals`

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

### `audit_log`

```text
audit_id
actor_telegram_id
action
entity_type
entity_id
payload_json
created_at
```

## Артефакты и storage

Когда ScoutBot выполняет runtime-действия, он пишет evidence artifacts.

### SQLite

```text
storage/db/scoutbot.sqlite3
```

### Iteration 1 artifacts

```text
storage/interfaces/changedetection_status.json
storage/interfaces/sync_result.json
storage/exports/<workspace>.export.yml
storage/discovery/<run_id>/discovered_links.json
storage/discovery/<run_id>/source_graph.json
storage/runs/<run_id>/target_sync.json
storage/runs/<run_id>/webhook_event.json
storage/runs/<run_id>/signal_classification.json
storage/signals/<YYYY-MM-DD>.jsonl
```

Artifacts — это evidence, а не runtime source of truth.

## Пример signal JSONL

Iteration 1:

```json
{
  "signal_id": "sig_20260622_120001_ab12cd",
  "target_id": "tgt_networks",
  "category": "delegation",
  "priority": "high",
  "diff_hash": "7fdab1...",
  "detected_at": "2026-06-22T12:00:01Z",
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

Noise marking как полноценное поведение — следующий шаг после MVP baseline.

## Webhook contract

Текущий контракт:

```text
POST /webhooks/changedetection?secret=<SCOUTBOT_WEBHOOK_SECRET>
```

Или через header:

```text
x-webhook-secret: <SCOUTBOT_WEBHOOK_SECRET>
```

Webhook receiver:

- проверяет secret;
- ограничивает payload size;
- читает body bounded read;
- извлекает changedetection UUID;
- ищет watch/target;
- возвращает `422` при missing UUID;
- возвращает `404` при unknown watch;
- пишет raw-safe event artifact;
- считает diff hash;
- проверяет dedupe;
- сохраняет signal;
- пишет classification artifact и JSONL;
- диспатчит Telegram alert.

## Безопасность

Главные правила:

- secrets только в `.env` / env;
- `.env` не коммитить;
- не логировать токены/API keys;
- `changedetection.io` не открывать наружу по умолчанию;
- Telegram state-changing и inventory команды доступны только admin allowlist;
- URL валидировать;
- discovery response size ограничивать;
- webhook body size ограничивать;
- не обходить auth/anti-bot;
- не запускать arbitrary JS из Telegram;
- не позволять произвольные jq/filter rules неадминам;
- artifacts не должны содержать secrets.

Admin allowlist:

```bash
TELEGRAM_ADMIN_IDS=111111111,222222222
```

## Диагностика и тесты

### Все тесты

```bash
uv run pytest -q
```

### Диагностика

```bash
./start.sh doctor
```

Проверяет:

- Python/uv environment;
- settings validation;
- storage paths;
- SQLite path;
- Telegram env presence;
- changedetection API reachability;
- safe config assumptions.

### Runtime smoke

```bash
./start.sh routes
./start.sh doctor
./start.sh init-db
./start.sh import-seed config/seeds/noders.yml
./start.sh export-seed storage/exports/noders.export.yml
./start.sh sync
./start.sh telegram
./start.sh webhook
```

Уточнения:

- `telegram` без токена должен завершаться explicit error;
- `sync` без `CHANGEDETECTION_API_KEY` должен быть degraded;
- `webhook` без секрета стартует с warning и отклоняет запросы.

## Development workflow

Текущий рабочий процесс для ScoutBot — direct-main SDLC-light:

```text
ROADMAP iteration
  → code
  → tests
  → logs/artifacts check
  → commit
  → main
```

Issue, branch и PR не являются обязательными на текущем этапе.

При этом дисциплина остаётся:

- работать только в scope текущей итерации из `docs/ROADMAP.md`;
- определять change level:
  - `low-risk`;
  - `runtime-risk`;
  - `security-sensitive`;
- запускать нужные checks;
- проверять logs/artifacts;
- не менять `pyproject.toml.version` вручную;
- не менять release-related файлы без задачи про релиз;
- не добавлять зависимости без необходимости;
- не превращать seed YAML в runtime state;
- не добавлять AI/n8n/crawler сверх MVP.

Минимум перед заливкой в `main`:

```bash
uv run pytest -q
./start.sh doctor
```

Если затронут конкретный entrypoint, нужно проверить его:

```bash
./start.sh init-db
./start.sh sync
./start.sh telegram
./start.sh webhook
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

Если меняется runtime behavior, config contract, SQLite schema, storage artifacts, Telegram UX, webhook, changedetection sync или security boundary — нужно проверить, требуется ли обновить docs.

## ROADMAP кратко

### Iteration 0 — Foundation — DONE

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

### Iteration 1 — Telegram MVP — DONE

Цель:

- Telegram add/list/pause/resume/delete/check;
- bounded discovery v0;
- webhook receiver;
- Telegram alerts;
- dedupe.

После Iteration 1 проект является MVP-ready для базового self-hosted мониторинга, но production use требует manual smoke с реальными Telegram/changedetection.io env.

### Iteration 2 — Signal quality and discovery hardening

Цель:

- меньше шума;
- categories;
- priority;
- mark-as-noise;
- source graph;
- degraded statuses;
- confirmation mode;
- digest v0.

### Iteration 3 — Source expansion and operations

Цель:

- RSS / GitHub / public Telegram / link aggregator adapters;
- backup / export;
- audit diagnostics;
- optional routing hooks.

### Iteration 4 — Productization later

- web dashboard;
- optional AI summaries;
- optional n8n router;
- multi-workspace hardening.

## Текущий MVP-контракт

После Iteration 1 гарантируется flow:

```text
Telegram /add URL
→ SQLite target
→ bounded discovery
→ target_links / child targets
→ changedetection.io watch sync
→ changedetection webhook
→ ScoutBot signal
→ Telegram alert
→ artifacts
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

Сначала надо добиться:

```text
clean targets
clean discovery
clean watches
clean webhook receiver
clean alerts
dedupe
noise control
```

Только потом можно добавлять LLM summaries.

### n8n

n8n не нужен для core.

Возможен как optional router позже, но не как source of truth.

## Краткое резюме

ScoutBot after Iteration 1 — это:

```text
Telegram-first MVP + SQLite + bounded discovery + changedetection.io REST boundary + webhook + alerts
```

Главные правила:

- `changedetection.io` — external engine;
- ScoutBot — settings, state, discovery, webhook, sync, signals and artifacts;
- Telegram UX, webhook, discovery and alerts — implemented as MVP baseline;
- SQLite — runtime state;
- YAML — seed/import/export;
- AI — disabled in MVP;
- n8n — optional later, not core;
- social scraping — cautious, public-only, degraded-aware;
- security — secrets only in env, no leaks in logs/storage;
- release versioning — через release-please, без ручных version bumps.
