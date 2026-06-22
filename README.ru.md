# ScoutBot — Telegram-first мониторинг конкурентов и публичных источников

**ScoutBot** — self-hosted Telegram-first бот для мониторинга изменений на сайтах, публичных страницах, RSS, GitHub, публичных Telegram-каналах и связанных источниках конкурентов.

Проект решает задачу:

> Указать конкурента или источник в Telegram → автоматически найти связанные официальные ссылки → поставить источники в мониторинг → получать push-уведомления в Telegram при изменениях.

Первый прикладной кейс — мониторинг конкурентов для **NODERS**: node operators, validators, staking/delegation campaigns, blockchain infrastructure, networks, docs, changelog, GitHub, public announcements.

Проект не завязан на NODERS и может использоваться для других компаний.

## Ключевая идея

ScoutBot не пишет собственный crawler/diff-engine.

ScoutBot управляет:

- Telegram UX;
- source graph;
- SQLite state;
- target lifecycle;
- changedetection sync;
- webhook processing;
- dedupe;
- category/priority rules;
- Telegram alerts;
- воспроизводимыми artifacts в `storage/`.

Низкоуровневый fetch/diff/snapshot слой делегируется внешнему self-hosted `changedetection.io`.

Базовая схема:

```text
Telegram
  → ScoutBot bot
  → SQLite
  → changedetection.io REST API
  → changedetection.io watches/diff
  → ScoutBot webhook
  → Telegram alerts
```

## Слои проекта

ScoutBot разделён на независимые слои:

- **Telegram UI** — добавление, список, pause/resume/delete targets, просмотр сигналов;
- **core** — запуск, settings validation, logging, paths, CLI dispatch;
- **SQLite state** — runtime source of truth для workspaces, projects, targets, discovered links, watches, signals;
- **discovery** — поиск официальных ссылок, RSS, GitHub, Telegram, link aggregators и публичных social profile links;
- **changedetection.io** — внешний engine для fetch/diff/snapshots/change detection;
- **webhook** — приём событий от changedetection.io;
- **intelligence** — dedupe, category, priority, noise rules;
- **services** — use-case слой между Telegram, DB, discovery, changedetection и notifications;
- **artifacts** — воспроизводимые evidence-файлы в `storage/`.

## Что делает ScoutBot

### MVP

ScoutBot должен уметь:

- добавлять workspace/project/target из Telegram;

- добавлять target по URL;

- принимать не только сайты, но и публичные профили/источники:
  - website;
  - blog/news;
  - docs/changelog;
  - pricing/services;
  - careers;
  - RSS/Atom;
  - GitHub org/repo/releases;
  - публичный Telegram channel;
  - YouTube channel;
  - X/Twitter public profile page;
  - link aggregator;
  - arbitrary public page;

- автоматически искать официальные связанные ссылки на добавленной странице;

- сохранять найденные links под исходным target;

- ставить allowed links в очередь мониторинга;

- создавать watches в self-hosted `changedetection.io`;

- принимать webhook при изменении;

- сохранять signal в SQLite и `storage/`;

- отправлять понятный alert в Telegram;

- управлять targets из Telegram:
  - pause;
  - resume;
  - delete;
  - check/list.

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

## Как работает добавление сайта

Пример:

```text
User:
/add https://example-validator.com
```

ScoutBot:

1. проверяет Telegram admin allowlist;

2. валидирует URL;

3. нормализует URL;

4. создаёт project/target в SQLite;

5. пишет audit log;

6. запускает discovery;

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

10. создаёт watches в `changedetection.io`;

11. отправляет отчёт в Telegram.

Пример ответа:

```text
ScoutBot

Target saved:
Example Validator / Homepage

Discovered official links:
✅ Blog
✅ Docs
✅ GitHub
✅ Telegram
⚠ X profile — queued as public profile page, may be degraded

Created watches: 5
Need confirmation: 1
```

## Target не обязательно сайт

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

Основной интерфейс — Telegram.

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

Alert example:

```text
🔔 ScoutBot signal

Project: Example Validator
Target: Networks
Category: Delegation
Priority: High

Detected:
- Added new mainnet section
- Added delegation CTA
- Added validator commission mention

Why it matters:
Possible validator/delegation campaign update.

URL:
https://example-validator.com/networks

[Open] [Pause target] [Mark as noise]
```

## Архитектура runtime

MVP состоит из трёх процессов/сервисов:

```text
./start.sh telegram
./start.sh webhook
changedetection.io
```

### `telegram`

Telegram bot:

- принимает команды;
- проверяет admin allowlist;
- создаёт projects/targets;
- показывает списки;
- управляет pause/resume/delete;
- отправляет alerts.

### `webhook`

FastAPI webhook receiver:

- принимает события от `changedetection.io`;
- проверяет secret;
- находит target/watch;
- делает dedupe;
- сохраняет signal;
- отправляет Telegram alert.

### `changedetection.io`

External engine:

- периодически проверяет URL;
- хранит snapshots;
- вычисляет diff;
- отправляет notification webhook в ScoutBot.

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
│       ├── core/
│       │   ├── app.py
│       │   ├── cli.py
│       │   ├── settings.py
│       │   ├── log.py
│       │   └── paths.py
│       │
│       ├── db/
│       │   ├── models.py
│       │   ├── session.py
│       │   ├── repo.py
│       │   └── migrations.py
│       │
│       ├── changedetection/
│       │   ├── client.py
│       │   ├── payloads.py
│       │   └── sync.py
│       │
│       ├── bot/
│       │   ├── app.py
│       │   ├── handlers.py
│       │   ├── keyboards.py
│       │   ├── states.py
│       │   ├── formatters.py
│       │   └── auth.py
│       │
│       ├── web/
│       │   ├── app.py
│       │   ├── routes.py
│       │   └── schemas.py
│       │
│       ├── discovery/
│       │   ├── homepage.py
│       │   ├── links.py
│       │   ├── feeds.py
│       │   ├── socials.py
│       │   └── link_aggregators.py
│       │
│       ├── intelligence/
│       │   ├── classify.py
│       │   ├── dedupe.py
│       │   ├── noise.py
│       │   └── score.py
│       │
│       └── services/
│           ├── projects.py
│           ├── targets.py
│           ├── discovery.py
│           ├── signals.py
│           └── notifications.py
│
└── tests/
    ├── test_config.py
    ├── test_db_models.py
    ├── test_changedetection_payloads.py
    ├── test_discovery.py
    ├── test_dedupe.py
    ├── test_webhook.py
    └── test_smoke.py
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

[project.optional-dependencies]
dev = [
    "pytest>=9.0.0",
    "ruff>=0.14.0",
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

Синхронизирует active/queued targets из SQLite в `changedetection.io`.

```bash
./start.sh telegram
```

Запускает Telegram bot.

```bash
./start.sh webhook
```

Запускает FastAPI webhook receiver.

```bash
./start.sh routes
```

Показывает доступные webhook/API routes.

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

### Discovery

```text
storage/discovery/<run_id>/discovered_links.json
storage/discovery/<run_id>/source_graph.json
storage/discovery/<run_id>/degraded_sources.json
```

### Sync

```text
storage/runs/<run_id>/target_sync.json
storage/interfaces/changedetection_status.json
storage/interfaces/sync_result.json
```

### Webhook / signals

```text
storage/runs/<run_id>/webhook_event.json
storage/runs/<run_id>/signal_classification.json
storage/signals/<YYYY-MM-DD>.jsonl
```

### Export

```text
storage/exports/<workspace>.export.yml
```

Artifacts — это evidence, а не runtime source of truth.

## Пример signal JSONL

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

## Безопасность

Главные правила:

- secrets только в `.env` / env;
- `.env` не коммитить;
- не логировать токены/API keys;
- `changedetection.io` не открывать наружу по умолчанию;
- Telegram state-changing команды доступны только admin allowlist;
- URL валидировать;
- discovery response size ограничивать;
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
- read-only dashboard;
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

Сначала надо добиться:

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

## Краткое резюме

ScoutBot — это:

```text
Telegram + SQLite + changedetection.io + FastAPI webhook
```

Главные правила:

- `changedetection.io` — external engine;
- ScoutBot — Telegram UX, state, discovery, dedupe, alerts;
- SQLite — runtime state;
- YAML — seed/import/export;
- AI — disabled in MVP;
- n8n — optional later, not core;
- social scraping — cautious, public-only, degraded-aware;
- security — secrets only in env, no leaks in logs/storage;
- release versioning — через release-please, без ручных version bumps.
