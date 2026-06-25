# ROADMAP — ScoutBot

## Назначение

Этот документ фиксирует маршрут разработки `ScoutBot` по этапам и итерациям.

`ScoutBot` — Telegram-first self-hosted система мониторинга конкурентных и публичных источников:

- сайтов;
- страниц pricing/services;
- блогов/news/changelog;
- документации;
- careers;
- RSS/Atom;
- GitHub;
- публичных Telegram-каналов;
- link aggregators;
- публичных social profile pages там, где это технически и юридически допустимо.

ROADMAP используется как lightweight SDLC-артефакт:

- задаёт направление разработки;
- фиксирует цель каждой итерации;
- определяет ожидаемое поведение, артефакты и проверки;
- помогает держать разработку в рамках KISS;
- показывает, что считается готовностью по итерациям.

Текущий рабочий процесс проекта:

```text
ROADMAP iteration → code → tests → logs/artifacts → commit → main
```

Issue, branch и PR не являются обязательными для текущего ScoutBot workflow.

Допустимо использовать Issue/branch/PR позже, если проект вырастет или появится внешняя команда, но текущая дисциплина проще:

- работаем по текущей итерации ROADMAP;
- не выходим за scope итерации;
- делаем минимальный полезный increment;
- запускаем tests/smoke;
- проверяем logs/storage/SQLite/changedetection state;
- фиксируем результат коммитом в `main`.

ROADMAP не дублирует полные правила процесса и безопасности:

- практический workflow описан в `docs/DEV_GUIDE.md`;
- change levels и required checks описаны в `docs/SDLC.md`;
- secure development rules описаны в `docs/SECURITY.md`.

## Видение

| Блок                          | Формулировка                                                                                                                                                                                           |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Идентичность продукта**     | `ScoutBot` развивается как Telegram-first, self-hosted, low-cost competitor/source monitoring assistant.                                                                                               |
| **Основная цель**             | Автоматически отслеживать изменения в публичных источниках и отправлять полезные сигналы в Telegram без ручной проверки сайтов.                                                                        |
| **Философия исполнения**      | Низкоуровневый fetch/diff/snapshot слой делегируется `changedetection.io`; ScoutBot управляет источниками, состоянием, Telegram UX, нормализацией сигналов и артефактами.                              |
| **Источник истины**           | Runtime state source of truth — SQLite. `config/settings.yml` задаёт runtime/config contract. `config/seeds/*.yml` используются только для seed/import/export, не как рабочее состояние.               |
| **Discovery principle**       | Если пользователь добавляет сайт или публичный профиль, ScoutBot фиксирует найденные официальные ссылки/соцсети/link aggregators и ставит их в очередь мониторинга по правилам конфигурации.           |
| **KISS rule**                 | Не писать собственный crawler/diff-engine, пока `changedetection.io` закрывает задачу.                                                                                                                 |
| **AI rule**                   | AI не нужен в MVP. AI допускается позже только как bounded summary/classification layer поверх уже чистых deterministic signals.                                                                       |
| **Security rule**             | Secrets, Telegram token, changedetection API key и webhook secrets читаются только из env и не попадают в logs/storage/artifacts/API responses.                                                        |
| **Operator principle**        | Основной интерфейс в MVP — Telegram. Web UI не нужен до появления реальной боли.                                                                                                                       |
| **External engine principle** | `changedetection.io` — внешний engine/service, а не Python-library dependency внутри ScoutBot. ScoutBot общается с ним через REST API.                                                                 |
| **Social source principle**   | Соцсети не считаются автоматически стабильными источниками. ScoutBot добавляет найденные ссылки по allowlist/политике, фиксирует discovery evidence и degraded state, но не обходит auth/anti-bot/ToS. |

## Принципы разработки

Делаем маленькие, но содержательные итерации.

Каждая итерация должна:

- запускаться через `./start.sh` или ожидаемый CLI entrypoint;
- писать понятные логи;
- оставлять воспроизводимые артефакты в `storage/`, если это предполагается задачей;
- не ломать структуру пакета `scoutbot_module`;
- использовать `config/settings.yml` как runtime/config source of truth;
- использовать SQLite как runtime state source of truth;
- валидировать новые обязательные ключи fail-fast;
- проходить tests/smoke/log/artifact checks;
- проходить quality/security checks из `docs/SDLC.md` и `docs/SECURITY.md` в зависимости от типа изменения;
- сохранять explicit authority boundary.

ScoutBot имеет ограниченную authority:

Разрешено в MVP:

- создавать/обновлять/удалять watches в self-hosted `changedetection.io`;
- отправлять Telegram сообщения;
- читать публичные источники в рамках bounded discovery;
- изменять собственное SQLite state.

Не разрешено в MVP:

- писать на сайты конкурентов;
- обходить auth/anti-bot/ToS;
- использовать платные APIs без отдельного решения;
- использовать AI как source of truth;
- хранить runtime state в YAML;
- переносить business logic в n8n.

## SDLC-light workflow для ROADMAP items

Текущий упрощённый цикл:

1. **Select iteration**
   Выбрать текущую итерацию в ROADMAP.

2. **Define task scope**
   Сформулировать конкретный scope внутри итерации.

3. **Classify change level**
   Определить уровень изменения:
   - `low-risk`;
   - `runtime-risk`;
   - `security-sensitive`.

4. **Implement**
   Внести изменения прямо в рамках текущей итерации. Не протаскивать future architecture.

5. **Verify**
   Выполнить tests, smoke-check, проверку логов, storage, SQLite state, changedetection state и security checks по уровню риска.

6. **Record evidence**
   Зафиксировать в отчёте/commit message/AI summary:
   - что сделано;
   - какие tests прошли;
   - какие artifacts появились;
   - какие ограничения остались.

7. **Commit to main**
   Коммитить только после проверки DoD.

Issue/branch/PR optional. Они могут использоваться позже, но не являются обязательной частью текущего ScoutBot workflow.

## Значения статусов

Допустимые статусы итераций:

- **PLANNED** — запланировано;
- **IN PROGRESS** — в работе;
- **DONE** — завершено;
- **DONE (partial)** — завершено частично, есть осознанные ограничения;
- **FUTURE** — возможно позже, не входит в ближайший MVP/scope.

## Глобальное Definition of Done

Итерация считается завершённой, если:

- поведение реализовано в рамках заявленного scope;
- `./start.sh` или ожидаемый CLI path работает;
- новые обязательные ключи читаются из `config/settings.yml`;
- fail-fast validation добавлена в `src/scoutbot_module/core/settings.py`;
- SQLite schema/state работает и не конфликтует с seed/config;
- логи записываются в `logs/app.log`;
- артефакты создаются там, где это ожидается;
- tests и ручные проверки выполнены;
- required checks из `docs/SDLC.md` и `docs/SECURITY.md` выполнены по уровню изменения;
- secrets не попадают в logs/storage/artifacts/API responses;
- docs обновлены, если менялся config/runtime/artifact/CLI/Telegram/webhook contract;
- `changedetection.io` не открыт наружу без необходимости;
- `pyproject.toml.version` не меняется без отдельной release-задачи.

## Уровни изменений для проверки

Для lightweight SDLC в проекте используются три уровня изменений:

- **low-risk** — docs, тесты, безопасные косметические изменения без влияния на runtime-контракт;
- **runtime-risk** — settings, DB, CLI, Telegram UX, changedetection sync, webhook handling, discovery, signal processing, artifacts;
- **security-sensitive** — env/secrets, external connector boundary, webhook auth, URL/path handling, HTML parsing, dependencies, social/link discovery, untrusted payload parsing, serialization/deserialization.

Для каждого уровня обязательность quality/security checks определяется в:

- `docs/SDLC.md`;
- `docs/SECURITY.md`.

## Продуктовые фазы

| Фаза                                              | Статус  | Что это значит                                                                                                                 |
| ------------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------ |
| **Фаза A — Foundation + engine boundary**         | DONE    | Репозиторий, запуск, settings, logs, storage, SQLite, seed import/export, changedetection REST client/sync.                    |
| **Фаза B — Telegram MVP**                         | PLANNED | Telegram add/list/pause/resume/delete, discovery v0, changedetection watches, webhook receiver, Telegram alerts, basic dedupe. |
| **Фаза C — Signal quality + discovery hardening** | DONE | Noise control, categories, priority, mark-as-noise, source graph, degraded statuses, confirmation mode, digest v0.             |
| **Фаза D — Operations and source expansion**      | PLANNED | RSS/GitHub/public Telegram/link aggregator adapters, backup/export, audit diagnostics, optional routing hooks.                 |
| **Фаза E — Productization later**                 | FUTURE  | Web dashboard, optional AI summaries, optional n8n router, multi-workspace hardening.                                          |

## Этап 1 — MVP foundation

### Итерация 0 — Каркас, config, SQLite и changedetection boundary

**Статус:** DONE

#### Goal

Поднять минимальный каркас ScoutBot с каноническим запуском через `./start.sh → config/start.py`, структурой `src/scoutbot_module`, settings validation, логами, storage, SQLite state и REST-boundary к `changedetection.io`.

#### Scope

Включено:

- `start.sh`;
- `config/start.py`;
- `config/settings.yml`;
- `.env.example`;
- `pyproject.toml`;
- `uv.lock`;
- пакет `src/scoutbot_module`;
- базовые директории:
  - `logs/`;
  - `storage/`;
  - `storage/db/`;
  - `storage/runs/`;
  - `storage/discovery/`;
  - `storage/signals/`;
  - `storage/interfaces/`;
  - `storage/exports/`;
- core modules:
  - `core/settings.py`;
  - `core/log.py`;
  - `core/paths.py`;
  - `core/app.py`;
  - `core/cli.py`;
- SQLite schema v0:
  - `workspaces`;
  - `projects`;
  - `targets`;
  - `target_links`;
  - `watches`;
  - `signals`;
  - `audit_log`;
- DB helpers:
  - `db/models.py`;
  - `db/session.py`;
  - `db/repo.py`;
  - `db/migrations.py`;
- changedetection REST client skeleton:
  - health/check;
  - list watches;
  - create watch;
  - update watch;
  - delete watch;
- seed import/export:
  - `config/seeds/noders.yml`;
  - import seed YAML → SQLite;
  - export SQLite workspace → YAML backup;
- sync path:
  - queued/active targets in SQLite → changedetection watches;
  - watch UUID saved in SQLite;
  - sync result artifact;
- CLI commands:
  - `doctor`;
  - `init-db`;
  - `import-seed`;
  - `export-seed`;
  - `sync`.

Не включено:

- Telegram bot;
- webhook receiver;
- auto-discovery from live HTML;
- signal classification;
- AI;
- n8n;
- Docker image для ScoutBot;
- web UI.

#### Deliverable

Проект запускается, валидирует настройки, создаёт SQLite DB, импортирует seed, проверяет доступность `changedetection.io` и умеет синхронизировать seed targets в external engine.

#### Expected commands

```bash
./start.sh doctor
./start.sh init-db
./start.sh import-seed config/seeds/noders.yml
./start.sh export-seed storage/exports/noders.export.yml
./start.sh sync
```

#### Artifacts

- `logs/app.log`
- `storage/db/scoutbot.sqlite3`
- `storage/interfaces/changedetection_status.json`
- `storage/interfaces/sync_result.json`
- `storage/exports/<workspace>.export.yml`

#### Checks

- `uv run pytest -q`
- `./start.sh doctor`
- `./start.sh init-db`
- `./start.sh import-seed config/seeds/noders.yml`
- `./start.sh export-seed storage/exports/noders.export.yml`
- `./start.sh sync`
- manual log inspection
- SQLite state inspection
- changedetection watch creation inspection
- secret leakage check

#### DoD

- `./start.sh` работает без CLI args и использует `run.mode` из settings;
- `./start.sh doctor` проверяет Python/uv env, settings, storage paths, SQLite path, Telegram env presence и changedetection API reachability;
- `changedetection.io` API key не пишется в logs/storage;
- SQLite schema создаётся воспроизводимо;
- seed import не становится вторым runtime source of truth;
- sync создаёт/обновляет watches и сохраняет watch UUID в SQLite;
- `config/seeds/*.yml` остаётся seed/import/export, а не runtime state.

### Итерация 1 — Telegram MVP end-to-end: add target → discovery → watch → webhook → alert

**Статус:** DONE

#### Goal

Сделать рабочий MVP: пользователь из Telegram добавляет сайт или публичный target, ScoutBot сохраняет project/target в SQLite, выполняет bounded discovery v0, создаёт watches в `changedetection.io`, принимает webhook при изменениях, сохраняет signal и отправляет Telegram alert.

После этой итерации ScoutBot должен быть MVP-ready.

#### Scope

Включено:

- Telegram bot runtime:
  - `./start.sh telegram`;
- FastAPI webhook receiver:
  - `./start.sh webhook`;
- Telegram commands:
  - `/start`;
  - `/help`;
  - `/add`;
  - `/projects`;
  - `/targets`;
  - `/pause`;
  - `/resume`;
  - `/delete`;
  - `/check`;
- inline-button UX для управления targets:
  - pause;
  - resume;
  - delete;
  - mark as noise placeholder, если полностью не реализуется до Iteration 2;
- allowlist Telegram admin IDs;
- add target flow:
  - website URL;
  - X/Twitter public profile URL as public page;
  - Telegram public channel URL as public page;
  - GitHub org/repo URL;
  - YouTube/channel URL;
  - link aggregator URL;
  - arbitrary public page URL;
- URL validation:
  - allowed schemes only;
  - private networks blocked by default;
  - response size limits;
  - timeout limits;
  - no auth bypass;
- auto-discovery v0:
  - HTML links;
  - `<link rel="alternate" type="application/rss+xml">`;
  - `sitemap.xml` candidate;
  - common pages:
    - blog;
    - news;
    - docs;
    - changelog;
    - careers;
    - pricing/services;
  - official social links found on page;
  - GitHub links;
  - Telegram links;
  - YouTube links;
  - link aggregators;
- discovery policy:
  - found links are stored in SQLite under the source target;
  - allowed source kinds are auto-queued for monitoring if `discovery.auto_queue: true`;
  - risky/degraded source kinds are stored as `discovered` and require confirmation if configured so;
- changedetection watch creation for active/queued targets;
- changedetection notification URL points to ScoutBot webhook;
- webhook receiver:
  - secret validation;
  - payload size limit;
  - target/watch lookup;
  - raw-safe event artifact;
  - diff hash calculation;
  - basic dedupe by `target_id + diff_hash`;
  - signal save to SQLite;
  - signal append to JSONL;
  - Telegram alert formatting;
- basic deterministic category/priority placeholder:
  - category can be `unknown|social|product|pricing|delegation|noise`;
  - detailed quality improvement moves to Iteration 2.

Не включено:

- advanced social scraping;
- bypassing auth/anti-bot;
- AI summaries;
- web UI;
- n8n workflows;
- proxies;
- Playwright automation written by ScoutBot;
- complex source graph heuristics;
- full digest system.

#### Deliverable

MVP работает end-to-end:

```text
Telegram /add <url>
→ SQLite project/target/link graph
→ discovery v0
→ changedetection watch creation
→ page changes
→ ScoutBot webhook
→ signal saved
→ Telegram alert
→ pause/resume/delete works
```

#### Expected commands

```bash
./start.sh telegram
./start.sh webhook
./start.sh sync
./start.sh doctor
```

#### Artifacts

- `storage/discovery/<run_id>/discovered_links.json`
- `storage/discovery/<run_id>/source_graph.json`
- `storage/runs/<run_id>/target_sync.json`
- `storage/runs/<run_id>/webhook_event.json`
- `storage/runs/<run_id>/signal_classification.json`
- `storage/signals/<YYYY-MM-DD>.jsonl`
- `logs/app.log`

#### Checks

- `uv run pytest -q`
- Telegram smoke:
  - `/start`;
  - `/add https://example.com`;
  - `/projects`;
  - `/targets`;
  - pause/resume/delete;
- discovery smoke with local HTML fixture;
- link aggregator fixture smoke;
- changedetection fake client tests;
- webhook fake payload tests;
- dedupe test;
- Telegram formatter test;
- URL validation/path safety review;
- private network URL rejection test;
- malformed URL test;
- webhook secret rejection test;
- secret leakage check;
- manual end-to-end smoke with self-hosted changedetection.

#### DoD

- пользователь может добавить target из Telegram;
- target сохраняется в SQLite;
- найденные официальные ссылки/соцсети фиксируются под исходным target;
- auto-queued links создают child targets;
- changedetection watches создаются для active targets;
- webhook создаёт signal;
- Telegram получает alert;
- повторный webhook с тем же diff не спамит;
- pause/resume/delete отражаются в SQLite и changedetection sync;
- secrets не попадают в logs/storage/artifacts;
- `config/seeds/*.yml` не становится runtime state;
- ScoutBot считается MVP-ready.

## Этап 2 — Signal quality and discovery hardening

### Итерация 2 — Telegram subscriptions, noise control, source graph and digest v0

**Статус:** DONE

#### Goal

Перевести ScoutBot от single-chat MVP к управляемому Telegram-first monitoring flow: allowed users могут подписаться на личные алерты, alerts становятся короче и полезнее, шум можно подавлять из Telegram, source graph становится объяснимым, а daily digest можно отправить вручную через CLI.

#### Scope

Включено:

- Telegram access and subscription model:
  - `TELEGRAM_ADMIN_IDS`;
  - `TELEGRAM_ALLOWED_USER_IDS`;
  - active personal subscribers in SQLite;
  - `TELEGRAM_ALERT_CHAT_ID` as optional global/group alert sink;

- SQLite runtime state:
  - `telegram_subscribers`;

- Telegram commands:
  - `/subscribe`;
  - `/unsubscribe`;
  - `/me`;
  - `/subscribers`;

- multi-recipient alert delivery:
  - active personal subscribers;
  - optional global/group sink from `TELEGRAM_ALERT_CHAT_ID`;
  - chat ID dedupe;
  - per-recipient delivery failure must not break webhook ingestion;

- Telegram logging safety:
  - Telegram Bot API token must not appear in `logs/`;
  - third-party HTTP logs must not expose token-bearing Bot API URLs;

- source kind classification:
  - `website`;
  - `blog`;
  - `docs`;
  - `changelog`;
  - `pricing`;
  - `careers`;
  - `rss`;
  - `github`;
  - `telegram`;
  - `social_profile`;
  - `link_aggregator`;
  - `custom`;

- keyword/category classifier:
  - `pricing`;
  - `product`;
  - `delegation`;
  - `validator_network`;
  - `positioning`;
  - `hiring`;
  - `legal`;
  - `social`;
  - `noise`;

- NODERS-specific keyword profile in config;

- priority score:
  - `low`;
  - `medium`;
  - `high`;

- configurable ignore selectors/text;

- Telegram button:
  - `Mark as noise`;

- real noise handling:
  - update signal category to `noise`;
  - update per-target ignore rules;
  - suppress repeated noise;
  - write noise update artifact;

- duplicate/noise suppression improvements;

- source graph artifact:
  - root target;
  - discovered links;
  - child targets;
  - confidence;
  - status;
  - reason codes;

- degraded discovery statuses:
  - `blocked`;
  - `auth_required`;
  - `anti_bot`;
  - `unsupported`;
  - `timeout`;
  - `too_large`;
  - `no_links_found`;

- bounded Telegram confirmation mode v0 for medium/low-confidence links:
  - low/medium-confidence links are stored but not auto-queued without policy;
  - operator can confirm queued candidates through a simple Telegram action or command;
  - no complex conversation state;

- daily digest v0:
  - manual CLI command;
  - grouped by project/category/priority;
  - Telegram send path through the same multi-recipient delivery layer.

Не включено:

- LLM;
- complex ML;
- custom crawler/diff-engine;
- browser automation;
- paid APIs;
- web dashboard;
- per-user notification filters;
- billing;
- Telegram Mini App;
- workspace RBAC;
- scheduler/cron for digest;
- n8n as core/runtime state layer.

#### Deliverable

ScoutBot получает управляемую модель Telegram alerts:

```text
allowed users
→ /subscribe
→ personal Telegram alerts
→ optional group/global sink
```

Alerts становятся короче, полезнее и менее шумными. Discovery становится объяснимым: оператор видит, что найдено, что auto-queued, что требует подтверждения и что degraded. Daily digest работает вручную и отправляется тем же безопасным multi-recipient delivery path.

#### Expected commands

```bash
./start.sh digest
./start.sh sync
./start.sh telegram
./start.sh webhook
./start.sh doctor
```

#### Config contract

Добавить/использовать:

```yaml
telegram:
  token_env: "TELEGRAM_BOT_TOKEN"
  admin_ids_env: "TELEGRAM_ADMIN_IDS"
  allowed_user_ids_env: "TELEGRAM_ALLOWED_USER_IDS"
  chat_id_env: "TELEGRAM_ALERT_CHAT_ID"
```

Правила:

- `TELEGRAM_ADMIN_IDS` — полный доступ;
- `TELEGRAM_ALLOWED_USER_IDS` — пользователи, которым разрешено пользоваться ботом и подписываться на alerts;
- `TELEGRAM_ALERT_CHAT_ID` — optional global/group sink, не source of truth для подписчиков;
- active subscribers хранятся только в SQLite.

#### SQLite schema

Добавить таблицу:

```text
telegram_subscribers
```

Минимальные поля:

```text
subscriber_id
telegram_user_id
chat_id
username
first_name
role
is_active
created_at
updated_at
```

#### Artifacts

- `storage/signals/<YYYY-MM-DD>.jsonl`
- `storage/runs/<run_id>/signal_classification.json`
- `storage/runs/<run_id>/noise_update.json`
- `storage/discovery/<run_id>/source_graph.json`
- `storage/discovery/<run_id>/degraded_sources.json`
- `storage/runs/<run_id>/digest.json`

#### Checks

- `uv run pytest -q`
- `uv run ruff check src tests`
- `./start.sh routes`
- `./start.sh doctor`
- `./start.sh init-db`
- `./start.sh sync`
- `./start.sh digest`
- Telegram subscription tests;
- multi-recipient alert delivery tests;
- per-recipient Telegram failure test;
- unauthorized user tests;
- classifier tests;
- priority scoring tests;
- dedupe/noise suppression tests;
- mark-as-noise smoke;
- digest smoke;
- source graph fixture tests;
- degraded status fixture tests;
- malformed URL tests;
- corrupted artifact graceful handling;
- secret leakage check;
- Telegram Bot API token leakage check in `logs/` and `storage/`.

#### DoD

- `TELEGRAM_ALLOWED_USER_IDS` is configured and validated fail-fast;
- `telegram_subscribers` table is created reproducibly;
- allowed user can `/subscribe`, `/unsubscribe`, and `/me`;
- admin can use `/subscribers`;
- unauthorized user cannot subscribe or mutate state;
- alerts are sent to active personal subscribers;
- optional `TELEGRAM_ALERT_CHAT_ID` still works as global/group sink;
- duplicate chat IDs are deduped;
- Telegram delivery failure for one recipient does not break webhook ingestion;
- Telegram Bot API token does not appear in logs/storage;
- alert contains category/priority;
- noise can be marked from Telegram;
- per-target ignore rules are updated after noise marking;
- repeated noise does not spam;
- daily digest works manually through CLI;
- digest is grouped by project/category/priority;
- source graph is reproducible;
- degraded discovery statuses are explicit;
- auto-queue does not add low-confidence garbage without confidence/policy;
- Telegram shows discovered/degraded/needs-confirmation status;
- source graph and signal classification are built without AI;
- SQLite remains runtime state source of truth;
- `config/settings.yml` remains runtime/config source of truth;
- YAML seed/import/export does not become runtime state.

## Этап 3 — Source expansion and operations

### Итерация 3 — RSS/GitHub/public Telegram/link aggregator adapters + backup operations v0

**Статус:** PLANNED

#### Goal

Добавить bounded adapters для стабильных публичных источников и минимальные operational tools, чтобы ScoutBot можно было безопасно использовать для разных компаний без ручного ковыряния SQLite/storage.

#### Scope

Включено:

- RSS/Atom target handling;

- GitHub releases target handling;

- GitHub repo/changelog target handling;

- public Telegram channel webpage handling where available;

- link aggregator parser v0:
  - Linktree-like pages;
  - Beacons-like pages;
  - generic link page fallback;

- normalized target kind mapping to changedetection watches;

- adapter-specific confidence/reason codes;

- adapter-specific degraded statuses;

- seed/import support for adapter target kinds;

- Telegram `/add` support for adapter target kinds;

- sync support for adapter target kinds;

- workspace-scoped import/export;

- explicit backup command for SQLite;

- export current workspace to seed YAML;

- import workspace from seed YAML with conflict handling;

- audit log visibility through CLI:
  - recent actions;
  - target changes;
  - sync results;
  - webhook events summary;

- operational diagnostics:
  - DB health;
  - changedetection health;
  - Telegram env health;
  - webhook URL/secret config health;

- optional outbound router hook:
  - n8n webhook URL as optional notification route;
  - disabled by default;
  - no state in n8n;
  - no domain logic in n8n;

- docs for source adapters, backup/restore/operations.

Не включено:

- GitHub API token requirement;
- Telegram userbot;
- private channels;
- X/LinkedIn/Instagram private/API scraping;
- paid APIs;
- browser automation written by ScoutBot;
- direct replacement of changedetection.io;
- SaaS multi-tenancy;
- billing;
- public web admin;
- mandatory n8n;
- migration from SQLite to Postgres;
- AI summaries.

#### Deliverable

ScoutBot умеет работать с RSS/GitHub/public Telegram/link aggregators, а также может безопасно экспортироваться, бэкапиться и переноситься на другой workspace/company. n8n может быть optional router, но не становится source of truth.

#### Expected commands

```bash
./start.sh backup
./start.sh export-seed storage/exports/<workspace>.export.yml
./start.sh import-seed config/seeds/<workspace>.yml
./start.sh audit
./start.sh doctor
./start.sh sync
```

#### Artifacts

- `storage/backups/<backup_id>/scoutbot.sqlite3`
- `storage/backups/<backup_id>/manifest.json`
- `storage/exports/<workspace>.export.yml`
- `storage/runs/<run_id>/audit_summary.json`
- `storage/discovery/<run_id>/source_graph.json`
- `storage/discovery/<run_id>/degraded_sources.json`
- `storage/runs/<run_id>/target_sync.json`
- `storage/signals/<YYYY-MM-DD>.jsonl`
- `logs/app.log`

#### Checks

- `uv run pytest -q`
- RSS fixture tests;
- GitHub releases/changelog fixture tests;
- public Telegram page fixture tests where applicable;
- link aggregator fixture tests;
- sync tests;
- Telegram add tests;
- degraded source tests;
- backup/restore smoke;
- export/import roundtrip;
- audit summary smoke;
- optional n8n disabled-by-default check;
- optional n8n webhook payload shape check if enabled;
- no state written to n8n;
- no paid API / no secret requirement check;
- secret leakage check.

#### DoD

- adapter target kinds work through Telegram and seed import;
- adapter output is normalized into existing target/watch model;
- unsupported/private/degraded cases are explicit;
- no auth bypass or paid API dependency is introduced;
- changedetection.io remains external fetch/diff engine;
- SQLite backup is reproducible;
- workspace export/import roundtrip works;
- audit CLI helps inspect recent operational actions;
- n8n remains optional routing layer only;
- SQLite remains runtime state source of truth;
- config/settings.yml remains runtime/config source of truth;
- no second source of truth is introduced.

## Этап 4 — Productization later

### Итерация 4 — Web dashboard and optional AI summaries

**Статус:** FUTURE

#### Goal

Добавить productization features только после стабильного Telegram MVP, signal quality and operations: read-only web dashboard and optional AI summaries.

#### Scope

Включено later:

- read-only web dashboard over SQLite/signals/artifacts;
- project/target/signal views;
- source graph view;
- signal feed;
- degraded source diagnostics;
- optional AI summaries:
  - disabled by default;
  - generated only after deterministic filtering;
  - never source of truth for fact of change;
  - provider-configurable;
  - no automatic external actions.

Не включено:

- execution/control UI;
- arbitrary crawler controls;
- social auth bypass;
- SaaS auth/RBAC unless separate product decision;
- AI as decision source;
- AI-triggered target mutation without operator confirmation.

#### Deliverable

ScoutBot получает optional read-only product layer. AI используется только как assistive summarization layer, не как источник истины и не как authority path.

#### Artifacts

- existing SQLite/signals/artifacts reused;
- optional:
  - `storage/runs/<run_id>/ai_summary.json`;
  - `storage/runs/<run_id>/dashboard_snapshot.json`.

#### Checks

- web read-only checks;
- no mutation through dashboard;
- AI disabled-by-default check;
- AI no-source-of-truth check;
- no secrets in AI payload/logs;
- provider failure degraded behavior.

#### DoD

- web dashboard is read-only;
- AI remains optional and disabled by default;
- deterministic signal remains source of truth;
- no external mutation is introduced by AI or web UI.

## MVP readiness contract

ScoutBot считается MVP-ready после Iteration 1, если работает цепочка:

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

Минимальный MVP не требует:

- AI;
- n8n;
- web dashboard;
- custom crawler;
- paid APIs;
- private social scraping;
- browser automation.

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
- помечает проблемные sources как degraded;
- не обещает стабильный scraping X/LinkedIn/Instagram.

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

Возможен как optional router позже:

```text
changedetection.io
  → n8n webhook
  → Telegram / Slack / CRM
```

Но n8n не должен хранить:

- projects;
- targets;
- discovered links;
- watch UUIDs;
- signals;
- audit log;
- business rules.

Это состояние должно жить в SQLite внутри ScoutBot.

## Связанные process documents

Для выполнения итераций вместе с этим ROADMAP используются:

- `docs/DEV_GUIDE.md` — как запускать проект и как работать с AI/Copilot в рамках проекта;
- `docs/SDLC.md` — lightweight process, change levels, required checks, DoD flow;
- `docs/SECURITY.md` — secure development rules и security checks для разных типов изменений;
- `docs/ARCHITECTURE.md` — архитектура и границы компонентов;
- `docs/SPEC.md` — продуктовый и технический контракт MVP.
