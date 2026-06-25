# SPEC — ScoutBot

## 0. Термины

- Репозиторий: `scoutbot`
- Python-пакет: `scoutbot_module`
- Workspace: логическая область мониторинга, например `NODERS`
- Project: наблюдаемая организация, конкурент, продукт или команда
- Target: конкретный URL/source, который мониторится или поставлен в очередь
- Target link: найденная связь между исходным target и другим URL
- Watch: запись в `changedetection.io`
- Signal: зафиксированное изменение, полученное от `changedetection.io` и сохранённое ScoutBot
- Discovery run: запуск поиска связанных источников для target
- Sync run: запуск синхронизации SQLite targets с `changedetection.io`
- Seed: YAML файл для bootstrap/import/export
- Runtime/config source of truth: `config/settings.yml`
- Runtime state source of truth: SQLite
- External engine: self-hosted `changedetection.io`
- Source kind: тип источника (`website`, `blog`, `docs`, `rss`, `github`, `telegram`, `social_profile`, etc.)
- Source kind resolver: функция определения типа источника по URL
- Adapter: модуль нормализации публичного источника (`rss`, `github`, `telegram`, `link_aggregator`)
- Backup: копия SQLite в `storage/backups/<backup_id>/` с manifest
- Audit: диагностический отчёт о работе ScoutBot
- Artifact: воспроизводимый runtime/debug файл в `storage/`
- Degraded state: явное состояние частичной/неполной обработки без silent success

## 1. Цель

ScoutBot — Telegram-first self-hosted система мониторинга публичных источников.

Система должна позволять оператору через Telegram:

- добавить сайт или публичный URL;
- автоматически найти официальные связанные источники;
- поставить allowed sources в мониторинг;
- получать Telegram push при изменениях;
- управлять списком targets без ручной правки файлов;
- использовать проект для NODERS и других компаний;
- не писать собственный crawler/diff-engine, пока задачу закрывает `changedetection.io`.

MVP должен закрыть end-to-end поток:

```text
Telegram /add <url>
→ SQLite target/source graph
→ bounded discovery
→ changedetection watch creation
→ changedetection webhook on change
→ ScoutBot signal
→ Telegram alert
```

## 2. Основной runtime contract

Канонический запуск:

```text
./start.sh
  → config/start.py
  → scoutbot_module.core.app
```

`config/start.py` — единственная главная точка запуска.

Он должен:

- найти project root;
- загрузить `.env` без перезаписи уже существующих env-переменных;
- загрузить `config/settings.yml`;
- валидировать settings fail-fast;
- создать необходимые директории;
- настроить logging;
- распарсить CLI args;
- dispatch в нужный runtime/CLI mode.

Поддерживаемые команды MVP:

```text
doctor
init-db
import-seed
export-seed
sync
telegram
webhook
routes
digest
backup
audit
```

Если `./start.sh` вызван без аргументов, используется `run.mode` из `config/settings.yml`.

Явные CLI args имеют приоритет только на текущий запуск и не меняют `config/settings.yml`.

## 3. Source of truth

### Runtime/config

```text
config/settings.yml
```

`config/settings.yml` задаёт runtime/config contract:

- active runtime mode;
- logging/storage settings;
- Telegram env key names;
- changedetection API boundary;
- discovery policy;
- signal/dedupe policy;
- optional integrations.

Обязательные config keys не должны иметь скрытых дефолтов в коде.

Если добавляется новый обязательный ключ:

- он должен быть явно описан в `config/settings.yml`;
- он должен валидироваться в `src/scoutbot_module/core/settings.py`;
- при отсутствии или неверном значении приложение должно падать fail-fast с понятной ошибкой.

### Runtime state

```text
storage/db/scoutbot.sqlite3
```

SQLite — источник правды для runtime state.

В SQLite должны жить:

- workspaces;
- projects;
- targets;
- target links;
- watches;
- signals;
- audit log;
- Telegram-driven state changes;
- changedetection watch UUID linkage.

### Seed/import/export

```text
config/seeds/*.yml
storage/exports/*.yml
```

Seed YAML используется только для:

- bootstrap;
- import;
- export;
- backup;
- fixtures/examples.

YAML seed не является runtime source of truth.

После import рабочее состояние меняется через SQLite, Telegram UX и sync flow, а не через ручную правку seed YAML.

## 4. Технологический стек

MVP stack:

- Python 3.14+
- `uv`
- `setuptools` + src-layout
- SQLite
- `python-dotenv`
- `PyYAML`
- `pydantic` or explicit manual validation
- `httpx` for HTTP clients
- `python-telegram-bot`
- `FastAPI` + `uvicorn` for webhook receiver
- `beautifulsoup4` / `lxml` for bounded HTML parsing
- `pytest`

External service:

- self-hosted `changedetection.io`

Важно:

- `changedetection.io` не является Python dependency ScoutBot;
- ScoutBot общается с ним только через REST API;
- `changedetection.io` должен быть приватным по умолчанию.

## 5. Core entities

### Workspace

Fields:

```text
workspace_id
name
description
created_at
updated_at
```

### Project

Fields:

```text
project_id
workspace_id
name
homepage_url
tags_json
created_at
updated_at
```

### Target

Fields:

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

Allowed `status`:

```text
active
queued
paused
deleted
degraded
```

Allowed `kind`:

```text
website
blog
docs
changelog
pricing
careers
rss
github
github_repo
github_releases
github_changelog
telegram
telegram_public
social_profile
link_aggregator
custom
```

Allowed `priority`:

```text
low
medium
high
critical
```

### TargetLink

Fields:

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

Allowed `relationship`:

```text
official
same_domain
social
rss
sitemap
link_aggregator_child
manual
unknown
```

Allowed `status`:

```text
discovered
queued
active
requires_confirmation
degraded
rejected
```

### Watch

Fields:

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

Allowed `status`:

```text
active
paused
deleted
sync_pending
sync_failed
degraded
```

### Signal

Fields:

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

Allowed `category` baseline:

```text
delegation
validator_network
product
pricing
docs
github
hiring
legal
social
noise
unknown
```

### AuditLog

Fields:

```text
audit_id
actor_telegram_id
action
entity_type
entity_id
payload_json
created_at
```

Audit log is required for state-changing operations:

```text
add_target
pause_target
resume_target
delete_target
manual_check
import_seed
export_seed
sync_changedetection
mark_as_noise
```

## 6. Settings contract

Expected top-level blocks:

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
  allowed_user_ids_env: "TELEGRAM_ALLOWED_USER_IDS"
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
  allowed_kinds:
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
  require_confirmation_kinds:
    - social_profile
  blocked_domains: []
  allow_private_networks: false

signals:
  dedupe_enabled: true
  body_excerpt_chars: 1000
  categories:
    delegation:
      - delegation
      - validator
      - staking
      - commission
      - mainnet
      - testnet
      - governance
      - restaking
    product:
      - feature
      - integration
      - api
      - dashboard
      - network
      - chain
    pricing:
      - pricing
      - price
      - plan
      - enterprise
      - discount
    hiring:
      - careers
      - jobs
      - engineer
      - devops
      - sales
      - bd

ai:
  enabled: false

integrations:
  n8n:
    enabled: false
```

Validation rules:

- `app.name` required string;
- `app.env` required string;
- `run.mode` must be one of supported commands/modes;
- `storage.root` required;
- `storage.db_path` required;
- `telegram.token_env`, `telegram.admin_ids_env`, `telegram.allowed_user_ids_env`, `telegram.chat_id_env` required;
- `changedetection.base_url` required HTTP/HTTPS URL;
- `changedetection.api_key_env` required env key name;
- `changedetection.timeout` must be positive;
- `changedetection.webhook_secret_env` required env key name;
- `discovery.target_links_max` must be positive;
- `discovery.max_depth` must be `0` or positive;
- `discovery.max_response_bytes` must be positive and bounded;
- `discovery.allow_private_networks` must be explicit boolean;
- `ai.enabled` must default to `false` in MVP;
- `integrations.n8n.enabled` must default to `false` in MVP.

## 7. Directory and artifact contract

Required directories:

```text
logs/
storage/
storage/db/
storage/runs/
storage/discovery/
storage/signals/
storage/interfaces/
storage/exports/
```

Logs:

```text
logs/app.log
```

Runtime artifacts:

```text
storage/runs/<run_id>/
```

Discovery artifacts:

```text
storage/discovery/<run_id>/
```

Signal artifacts:

```text
storage/signals/<YYYY-MM-DD>.jsonl
```

Interface/external boundary artifacts:

```text
storage/interfaces/changedetection_status.json
storage/interfaces/sync_result.json
```

Export artifacts:

```text
storage/exports/<workspace_or_project>.export.yml
```

Artifacts must not contain secrets.

## 8. Run identity

Commands that produce runtime artifacts should create or accept a `run_id`.

Recommended format:

```text
run_<YYYYMMDD_HHMMSS>_<suffix>
```

Examples:

```text
run_20260622_141530_a1b2c3
```

`run_id` must be safe for filesystem use:

- only letters, numbers, `_`, `-`;
- no path separators;
- no `..`;
- bounded length.

## 9. Discovery behavior

When a target is added:

1. validate URL;
2. normalize URL;
3. reject unsafe URL if policy requires;
4. create target in SQLite;
5. create audit log entry;
6. create discovery run if discovery is enabled;
7. fetch safe bounded HTML if direct discovery is allowed;
8. extract candidate links;
9. classify links;
10. store target links in SQLite;
11. write discovery artifact;
12. auto-queue allowed links according to config policy;
13. sync active/queued targets to changedetection.

Discovery must not:

- execute page JavaScript inside ScoutBot;
- bypass auth;
- bypass anti-bot mechanisms;
- scrape private social data;
- use paid APIs without explicit config and roadmap decision;
- create unlimited child targets.

Degraded statuses:

```text
ok
no_links_found
blocked
auth_required
anti_bot
unsupported
fetch_error
parse_error
private_network_rejected
too_many_links
response_too_large
```

Discovery artifacts:

```text
storage/discovery/<run_id>/discovered_links.json
storage/discovery/<run_id>/source_graph.json
storage/discovery/<run_id>/degraded_sources.json
```

Minimum `discovered_links.json` shape:

```json
{
  "run_id": "run_20260622_141530_a1b2c3",
  "source_target_id": "target_example_homepage",
  "source_url": "https://example.com",
  "status": "ok",
  "links": [
    {
      "url": "https://example.com/blog",
      "normalized_url": "https://example.com/blog",
      "kind": "blog",
      "relationship": "same_domain",
      "confidence": 0.9,
      "status": "queued",
      "reason_code": "auto_queued_allowed_kind"
    }
  ],
  "degraded": []
}
```

## 10. changedetection sync behavior

Sync direction:

```text
SQLite targets → changedetection watches
```

ScoutBot must persist changedetection watch UUIDs back into SQLite.

Sync must:

- read active/queued targets from SQLite;
- create missing watches;
- update existing watches when target config changes;
- pause/delete watches when target state requires it;
- write sync result artifact;
- report degraded state if changedetection is unavailable;
- avoid duplicate watches for the same target.

Sync artifacts:

```text
storage/interfaces/changedetection_status.json
storage/interfaces/sync_result.json
storage/runs/<run_id>/target_sync.json
```

Minimum `sync_result.json` shape:

```json
{
  "run_id": "run_20260622_141530_a1b2c3",
  "status": "ok",
  "created": 3,
  "updated": 1,
  "paused": 0,
  "deleted": 0,
  "failed": 0,
  "errors": []
}
```

Allowed status:

```text
ok
partial
degraded
failed
```

## 11. changedetection watch payload

Minimum payload:

```json
{
  "url": "https://example.com",
  "title": "Example / Homepage",
  "time_between_check": {
    "hours": 6
  },
  "fetch_backend": "html_requests",
  "processor": "text_json_diff",
  "include_filters": [],
  "subtractive_selectors": ["nav", "footer", ".cookie", ".newsletter"],
  "ignore_text": ["©", "All rights reserved", "Accept cookies"],
  "notification_urls": ["json://<scoutbot-webhook-url>"],
  "notification_format": "json"
}
```

Rules:

- real webhook secret must come from env;
- real secret must not be written to logs/artifacts;
- artifacts may contain redacted notification URL only;
- ScoutBot must not let non-admin Telegram users configure arbitrary raw jq filters;
- changedetection API key must never be serialized.

## 12. Webhook behavior

Changedetection webhook receiver:

```text
./start.sh webhook
```

Webhook receiver must:

1. validate webhook secret;
2. reject missing/invalid secret;
3. cap payload size;
4. parse payload safely;
5. map payload to `watch` and `target`;
6. compute deterministic `diff_hash`;
7. dedupe repeated changes;
8. create signal in SQLite;
9. append signal JSONL artifact;
10. send Telegram alert if signal is new and not ignored;
11. handle malformed payload gracefully.

Webhook artifact:

```text
storage/runs/<run_id>/webhook_event.json
```

Minimum safe artifact shape:

```json
{
  "run_id": "run_20260622_141530_a1b2c3",
  "status": "ok",
  "target_id": "target_example_homepage",
  "watch_id": "watch_example_homepage",
  "changedetection_uuid": "redacted-or-uuid",
  "diff_hash": "sha256:...",
  "dedupe": {
    "is_duplicate": false
  },
  "signal_id": "signal_...",
  "telegram": {
    "sent": true,
    "message_id": 123
  }
}
```

Webhook artifact must not contain:

- webhook secret;
- raw auth headers;
- full unbounded payload;
- raw HTML diff if it is large or sensitive.

## 13. Signal classification and dedupe

Signal handling is deterministic in MVP.

When a webhook event arrives:

1. extract relevant change data;
2. compute `diff_hash`;
3. check dedupe by `target_id + diff_hash`;
4. classify category by deterministic keyword rules;
5. compute priority;
6. save signal to SQLite;
7. append JSONL artifact;
8. send Telegram alert.

Signal artifact:

```text
storage/signals/<YYYY-MM-DD>.jsonl
```

Minimum JSONL row:

```json
{
  "signal_id": "signal_...",
  "target_id": "target_example_homepage",
  "watch_id": "watch_example_homepage",
  "detected_at": "2026-06-22T14:15:30Z",
  "category": "delegation",
  "priority": "high",
  "diff_hash": "sha256:...",
  "title": "Example / Homepage changed",
  "summary": "Detected delegation-related update.",
  "url": "https://example.com",
  "dedupe": {
    "is_duplicate": false
  }
}
```

Dedupe rule:

```text
same target_id + same diff_hash = duplicate
```

Duplicate signals must not spam Telegram.

## 14. Telegram behavior

Telegram is the primary operator interface in MVP.

Runtime command:

```text
./start.sh telegram
```

Commands:

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

State-changing commands require admin allowlist.

State-changing commands include:

```text
/add
/pause
/resume
/delete
/check
```

where `/check` is state-changing if it triggers sync/discovery/fetch.

Admin identity source:

```text
TELEGRAM_ADMIN_IDS
```

Alert chat source:

```text
TELEGRAM_ALERT_CHAT_ID
```

Telegram token source:

```text
TELEGRAM_BOT_TOKEN
```

Token, admin IDs and alert chat ID must not be logged as secrets. Numeric IDs may appear only when necessary and should not be dumped in bulk.

### Target add flow

Example:

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
⚠ X profile: discovered, confirmation required or degraded

Created watches: 5
Need confirmation: 1
```

### Alert format

```text
🔔 ScoutBot signal

Project: Example Validator
Target: Networks
Category: Delegation
Priority: High

Detected:
- Added mainnet/delegation section

Why it matters:
Potential validator/delegation campaign update.

URL:
https://example.com/networks

[Open] [Pause target] [Mark as noise]
```

Telegram alerts must be concise and operator-readable.

## 15. Import/export behavior

Import:

```text
YAML seed → SQLite
```

Export:

```text
SQLite → YAML export
```

Commands:

```text
./start.sh import-seed config/seeds/noders.yml
./start.sh export-seed storage/exports/noders.export.yml
```

Import rules:

- validate YAML structure;
- validate URLs;
- reject malformed workspace/project/target IDs;
- create or update SQLite records deterministically;
- do not create runtime state in YAML;
- create audit log entry.

Export rules:

- export current SQLite state;
- do not export secrets;
- do not include env values;
- keep output deterministic where practical.

## 16. CLI diagnostics

Command:

```text
./start.sh doctor
```

Doctor must check:

- Python/uv environment;
- settings load;
- required config keys;
- DB path and writability;
- Telegram env presence, without printing token;
- changedetection API reachability;
- changedetection API key presence, without printing key;
- storage/logs directories;
- basic security posture:
  - changedetection URL not obviously public unless intentionally configured;
  - discovery private networks disabled by default.

Doctor artifacts:

```text
storage/interfaces/changedetection_status.json
```

Optional doctor run artifact:

```text
storage/runs/<run_id>/doctor.json
```

Doctor status:

```text
ok
partial
degraded
failed
```

## 17. Routes diagnostics

Command:

```text
./start.sh routes
```

Purpose:

- list available CLI/runtime routes;
- list FastAPI webhook routes if web app is importable;
- help verify entrypoints without starting long-running services.

Routes command must not:

- call changedetection API;
- call Telegram API;
- mutate SQLite;
- write secrets.

## 18. AI

AI is disabled in MVP.

Config:

```yaml
ai:
  enabled: false
```

Allowed later:

- optional summaries;
- optional daily digest;
- optional relevance scoring after deterministic filters.

Not allowed in MVP:

- AI as source of truth for whether a page changed;
- AI-triggered external actions;
- AI-required MVP path;
- AI-based target mutation without deterministic validation;
- AI bypassing Telegram admin boundary.

AI, if added later, must be bounded and assistive only.

## 19. n8n

n8n is optional and not part of core MVP.

Allowed later:

```text
changedetection.io → n8n webhook → Telegram/Slack/CRM
```

Not allowed in MVP:

- storing target state in n8n;
- Telegram management via n8n workflows;
- source graph in n8n;
- business logic in n8n;
- replacing SQLite as runtime state source of truth.

If n8n is added later, it must be an optional router/integration, not the ScoutBot core.

## 20. Security constraints

Required:

- secrets only from env;
- no secrets in logs/artifacts;
- validate URLs;
- reject unsafe local/private URLs by default for direct ScoutBot fetches;
- cap discovery response size;
- cap discovered links;
- cap webhook payload size;
- webhook requires secret;
- changedetection kept private by default;
- no auth/anti-bot bypass;
- no paid API without explicit config and decision;
- no arbitrary user-provided code execution;
- no arbitrary jq/filter authority for normal Telegram users;
- no raw unbounded HTML dumps in artifacts.

## 21. Development and verification contract

ScoutBot currently uses direct-main SDLC-light:

```text
ROADMAP iteration → code → tests → artifacts/logs → commit → main
```

Issue, branch and PR are optional later process upgrades, not required for the current local workflow.

Before pushing to `main`, developer must verify:

- change stays inside current ROADMAP iteration;
- change level is known:
  - `low-risk`;
  - `runtime-risk`;
  - `security-sensitive`;

- required checks for that change level are performed;
- `uv run pytest -q` passes unless explicitly documented otherwise;
- relevant entrypoint smoke-check passes;
- `logs/app.log` is inspected when runtime changed;
- artifacts in `storage/` are inspected when artifact behavior changed;
- secrets do not appear in logs/artifacts;
- `pyproject.toml.version` is not changed unless the task is release/versioning;
- `uv.lock` is not changed unless dependencies changed.

Normal versioning note for non-release tasks:

```text
version not changed
```

Normal dependency note when dependencies did not change:

```text
uv.lock not changed
```

## 22. MVP acceptance

MVP is ready when:

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

Minimum acceptance checks:

```bash
uv run pytest -q
./start.sh doctor
./start.sh init-db
./start.sh import-seed config/seeds/noders.yml
./start.sh sync
./start.sh telegram
./start.sh webhook
```

Manual verification:

- `logs/app.log` has understandable runtime events;
- `storage/db/scoutbot.sqlite3` exists and contains expected state;
- `storage/interfaces/changedetection_status.json` exists after doctor/sync;
- `storage/interfaces/sync_result.json` or `storage/runs/<run_id>/target_sync.json` exists after sync;
- `storage/discovery/<run_id>/discovered_links.json` exists after discovery;
- `storage/signals/<YYYY-MM-DD>.jsonl` exists after webhook/signal flow;
- changedetection watches exist for active targets;
- Telegram alert is delivered;
- repeated same diff does not spam;
- secrets are absent from logs/storage.

## 23. Out of scope for MVP

Not included in MVP:

- custom crawler/diff-engine;
- AI summaries;
- AI decision making;
- n8n as core state/runtime layer;
- paid APIs;
- private social scraping;
- bypassing auth/anti-bot;
- web dashboard;
- multi-user SaaS;
- RBAC;
- browser automation written by ScoutBot;
- arbitrary jq/xpath/css editing from Telegram;
- PostgreSQL or external DB;
- public exposure of changedetection UI.
