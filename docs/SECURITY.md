# SECURITY — ScoutBot

## Purpose

This document defines practical security rules for `ScoutBot`.

The goal is to improve runtime safety without unnecessary bureaucracy.

This is not a formal enterprise security program. It is a lightweight engineering guide for deciding:

- what needs security attention;
- which checks are worth running;
- how to keep secrets and runtime artifacts safe;
- how to align security checks with the current direct-main SDLC-light workflow.

ScoutBot is a self-hosted monitoring tool that handles:

- Telegram bot tokens;
- changedetection API keys;
- webhook secrets;
- untrusted URLs;
- untrusted HTML/RSS/JSON/webhook payloads;
- SQLite state;
- logs and artifacts.

Use this document with:

- `docs/ROADMAP.md`
- `docs/ARCHITECTURE.md`
- `docs/SPEC.md`
- `docs/DEV_GUIDE.md`
- `docs/SDLC.md`

## Security principles

Security in ScoutBot should follow these principles:

- protect secrets first;
- validate configuration explicitly;
- fail fast on invalid required inputs;
- treat external pages and webhook payloads as untrusted;
- keep runtime behavior observable but not overexposed;
- avoid hidden defaults for sensitive behavior;
- minimize attack surface;
- prefer simple designs over fragile abstractions;
- apply security checks proportionally to the change;
- keep verification evidence in tests, logs, artifacts and commit messages.

## What we protect

At minimum, the project should protect:

- `TELEGRAM_BOT_TOKEN`;
- `CHANGEDETECTION_API_KEY`;
- webhook secret;
- `.env`;
- SQLite state;
- changedetection watch configuration;
- Telegram admin allowlist;
- Telegram allowed user list;
- Telegram subscriber data;
- source graph and signal artifacts;
- operator/private monitoring lists;
- dependency integrity.

## Security-sensitive areas

Treat changes in these areas carefully:

- `config/settings.yml`
- `config/start.py`
- `.env.example`
- `pyproject.toml`
- `uv.lock`
- `compose.changedetection.yml`
- `src/scoutbot_module/core/settings.py`
- `src/scoutbot_module/core/app.py`
- `src/scoutbot_module/core/cli.py`
- `src/scoutbot_module/core/paths.py`
- `src/scoutbot_module/core/log.py`
- `src/scoutbot_module/db/*`
- `src/scoutbot_module/changedetection/*`
- `src/scoutbot_module/bot/*`
- `src/scoutbot_module/web/*`
- `src/scoutbot_module/discovery/*`
- `src/scoutbot_module/intelligence/*`

## Core rules

### 1. Config is runtime/config source of truth

Required runtime behavior must be controlled by `config/settings.yml`.

If a new required key is introduced:

- it must be present in `config/settings.yml`;
- it must be validated in `src/scoutbot_module/core/settings.py`;
- app must fail fast with a clear error if missing or invalid;
- docs must be updated if the config contract changed.

Do not hide required runtime values inside code.

### 2. SQLite is runtime state source of truth

Telegram edits, discovered links, target state, watch UUIDs and signals must live in SQLite.

Do not use YAML as runtime state.

Allowed YAML use:

- seed/import;
- export/backup;
- examples;
- fixtures.

`config/seeds/*.yml` is bootstrap/import/export material only. It must not become a second runtime state source.

### 3. Secrets must not leak

Secrets must never appear in:

- logs;
- storage artifacts;
- test snapshots;
- committed example payloads;
- terminal output copied into commit messages or reports;
- screenshots committed or shared as verification evidence.

Safe practice:

- read secrets only from env;
- never dump full env;
- never log raw headers;
- never serialize tokens/API keys;
- redact config before writing diagnostics;
- keep `.env` out of git.

### 4. Logs must be useful but safe

Allowed logs:

- high-level runtime events;
- reason codes;
- target IDs;
- watch UUIDs if non-secret;
- artifact paths;
- non-sensitive config choices;
- degraded/failed external engine states.

Not allowed:

- `TELEGRAM_BOT_TOKEN`;
- `CHANGEDETECTION_API_KEY`;
- webhook secret;
- raw auth headers;
- full env/config dumps;
- sensitive payload dumps.

Logs should be in English and should help diagnose the current iteration without exposing secrets.

### 5. Artifacts must be reproducible and safe

Artifacts should be:

- predictable;
- useful for debugging;
- aligned with logs;
- free from secrets;
- bounded in size where they capture external input;
- safe enough for operator inspection.

Before adding an artifact, ask:

- does it help reproduce behavior?
- does it expose private source lists or sensitive signals?
- should it be bounded/redacted?
- does it create a second source of truth?
- does the ROADMAP/SPEC/README need an artifact-contract update?

### 6. External input is untrusted by default

Treat as untrusted:

- Telegram messages;
- CLI args;
- config values;
- seed YAML files;
- URLs;
- HTML pages;
- RSS/Atom feeds;
- sitemap files;
- changedetection webhooks;
- changedetection API responses;
- restored JSON artifacts;
- imported/exported YAML state.

Validate before use where reasonable.

Do not trust restored JSON/YAML artifacts blindly. They are local files, but they are still input.

### 7. Keep changedetection.io private

`changedetection.io` should not be exposed publicly by default.

Recommended Docker binding:

```yaml
ports:
  - "127.0.0.1:5000:5000"
```

or internal Docker network only.

If exposed publicly later:

- put it behind reverse proxy;
- enable authentication;
- use HTTPS;
- restrict admin access;
- rotate API key if leaked;
- document the change in `docs/SECURITY.md` and `docs/DEV_GUIDE.md`.

### 8. Use current patched changedetection.io baseline

Do not pin old vulnerable versions.

Project baseline:

- use `changedetection.io >=0.55.7` unless intentionally changed;
- never use versions below `0.54.7`.

Reason: vulnerable versions below `0.54.7` had an information disclosure issue via jq `env` builtin. ScoutBot should also avoid letting untrusted users configure raw jq filters.

If the changedetection Docker tag changes:

- treat it as dependency/image change;
- run SCA-style review;
- update docs if the baseline changes.

### 9. Restrict jq/filter authority

In MVP, ScoutBot should generate safe default selectors/filters.

Do not allow arbitrary Telegram users to set raw jq/xpath/css rules unless:

- user is admin;
- input is validated;
- change is audited;
- risk is documented;
- changedetection baseline is reviewed;
- the ROADMAP iteration explicitly includes this capability.

### 10. URL safety

For every user-provided URL:

- require `http` or `https`;
- normalize URL;
- reject local/internal IP ranges by default if fetching directly from ScoutBot;
- avoid SSRF-prone direct fetches where possible;
- if changedetection fetches URL, still store URL safely and validate obvious bad inputs;
- do not follow unlimited redirects in ScoutBot discovery;
- cap content size for discovery fetches;
- cap redirects;
- store degraded reason instead of silently accepting unsafe/unsupported inputs.

Internal/local URL protection is especially important if ScoutBot later runs on the same host/network as private services.

### 11. Discovery safety

Discovery parses untrusted HTML/RSS/sitemap content.

Rules:

- cap response size;
- cap number of discovered links;
- normalize and deduplicate links;
- store discovery status/degraded reason;
- do not execute page JavaScript in ScoutBot;
- do not bypass auth/anti-bot;
- do not scrape private social data;
- do not treat social/public-profile data as automatically authoritative;
- keep discovery evidence bounded and redacted where necessary.

Degraded statuses should be explicit, for example:

- `blocked`;
- `auth_required`;
- `anti_bot`;
- `unsupported`;
- `no_links_found`;
- `parse_error`;
- `fetch_error`.

### 12. Telegram access boundary

Telegram bot supports two roles:

- **admin** — полный доступ: `/add`, `/pause`, `/resume`, `/delete`, `/check`, `/subscribers`, `/projects`, `/targets`.
- **allowed user (operator)** — может подписаться на алерты и просматривать свой статус: `/start`, `/help`, `/subscribe`, `/unsubscribe`, `/me`, `/add`, `/projects`, `/targets`, `/check`.

`TELEGRAM_ADMIN_IDS` задаёт полный доступ.
`TELEGRAM_ALLOWED_USER_IDS` задаёт allowed operators/viewers.
Effective allowed = admins ∪ allowed ids.
Неавторизованные пользователи получают `⛔ Access denied.`

Subscribers хранятся в SQLite (`telegram_subscribers`) — runtime state.
Allowed users — env/config, не SQLite.
`TELEGRAM_ALERT_CHAT_ID` — optional global/group alert sink, не источник подписчиков.

### 13. Telegram token must not appear in logs

Telegram Bot API calls produce `https://api.telegram.org/bot<TOKEN>/...` URLs.
These URLs must not appear in runtime logs, storage artifacts, or test output.

Mitigation:

- `httpx`, `httpcore`, `telegram.httpx` loggers set to WARNING level.
- Security check: `rg -n -i "api.telegram.org/bot" logs storage` — expected: empty.

### 14. Telegram admin boundary

Only allowed Telegram admins can mutate state.

Required:

- `TELEGRAM_ADMIN_IDS` in env/settings;
- fail clearly if bot starts without admin allowlist in production-like mode;
- all state-changing commands must check admin;
- audit log for add/pause/resume/delete/import/export/sync;
- no state mutation from non-admin commands.

State-changing commands include at minimum:

- `/add`;
- `/pause`;
- `/resume`;
- `/delete`;
- `/check` if it triggers external sync/fetch side effects;
- import/export;
- manual sync.

### 15. Webhook boundary

Changedetection webhook receiver must:

- require secret;
- reject missing/invalid secret;
- cap payload size;
- validate target/watch mapping;
- avoid writing raw secret/header data;
- handle malformed payload gracefully;
- dedupe repeated diff payloads;
- avoid Telegram spam on duplicate or invalid webhook events.

Webhook failures should be explicit, but error responses must not expose secrets or internal paths unnecessarily.

### 16. changedetection API boundary

ScoutBot controls `changedetection.io` only through REST API.

Rules:

- do not import changedetection internals as a Python library;
- API key must be read from env only;
- API key must not be logged or serialized;
- sync should be deterministic:
  - SQLite targets → changedetection watches;
  - changedetection watch UUID → SQLite watches;
  - sync status → logs/artifacts;

- changedetection unavailable state must be visible as degraded/error, not silent success;
- duplicate watches must not be created accidentally.

### 17. Network-facing routes

Any FastAPI/webhook route is security-sensitive by default.

Rules:

- validate route params and query params;
- cap request body size where practical;
- reject malformed payloads cleanly;
- avoid raw tracebacks in responses;
- do not serve arbitrary files from `storage/`;
- do not expose `.env`, config secrets or raw logs;
- use explicit allowlists for any artifact access.

## Security checks

Use checks that fit the change.

## SAST

### What it means here

Static review of source code for risky patterns.

### Use SAST when

Run or consider SAST when a change touches:

- runtime logic;
- config parsing;
- env/secrets handling;
- URL/discovery parsing;
- webhook handling;
- changedetection API boundary;
- Telegram handlers;
- DB access;
- serialization/deserialization;
- file/path handling;
- network-facing routes.

### Look for

- secret leakage;
- unsafe file/path usage;
- SSRF-prone direct fetches;
- missing validation;
- overly broad exception swallowing;
- insecure debug code;
- dangerous dynamic execution;
- arbitrary filter execution;
- unsafe parsing of untrusted input.

### Lightweight rule

For most code changes, a manual static safety pass is enough.

Use automated static scan if available or if the change is security-sensitive.

## SCA

### What it means here

Software Composition Analysis: dependency and image review.

### Use SCA when

Run or consider SCA when:

- `pyproject.toml` changes;
- `uv.lock` changes;
- dependency is added/removed/upgraded;
- changedetection Docker tag changes;
- Docker/compose runtime surface changes.

### Look for

- known vulnerable packages/images;
- unnecessary packages;
- risky maintenance history;
- broad dependency additions;
- runtime attack surface increase;
- dependency mismatch between `pyproject.toml` and `uv.lock`.

### Lightweight rule

If dependencies or image tags changed, SCA is required.

If dependencies did not change, SCA is usually not needed.

## DAST

### What it means here

Dynamic testing of exposed runtime behavior.

### Use DAST when

Run or consider DAST when change affects:

- FastAPI webhook receiver;
- any web route;
- changedetection webhook handling;
- external connector behavior;
- future dashboard/API endpoints.

### Look for

- malformed input handling;
- bad secret handling;
- crashes under bad payload;
- unsafe error messages;
- route misuse;
- path traversal through route params;
- unexpected mutation from read-only routes.

### Lightweight rule

For ScoutBot, DAST-style checks can be simple:

- send malformed payload;
- send missing/invalid secret;
- send bad route params;
- check response does not leak internals;
- check logs do not leak secrets.

## IAST

IAST is not default.

Consider only for high-risk runtime flows:

- public web exposure;
- complex connector flow;
- high-risk parsing;
- execution-capable actions;
- sensitive webhook flows.

## Fuzzing

Consider fuzzing or malformed-input tests for:

- URL parser;
- HTML/RSS parser;
- sitemap parser;
- seed YAML import;
- webhook payload parser;
- signal diff parser;
- JSON/JSONL artifact restore.

Do not fuzz everything.

Use targeted malformed cases where breakage is realistic.

## Security levels for changes

### Low-risk

Examples:

- docs only;
- comments;
- test-only;
- formatting;
- non-runtime refactor.

Usually enough:

- normal self-review;
- targeted tests if needed;
- no extra security checks unless the docs change security expectations.

### Runtime-risk

Examples:

- settings validation;
- DB schema/repo;
- Telegram commands;
- changedetection sync;
- artifacts;
- signal formatting;
- import/export;
- CLI dispatch.

Usually needed:

- `uv run pytest -q`;
- smoke run through affected entrypoint;
- log inspection;
- artifact inspection;
- SAST mindset review.

### Security-sensitive

Examples:

- secrets/env logic;
- URL fetching/parsing;
- discovery parser;
- webhook receiver;
- changedetection API key handling;
- dependency/image changes;
- file/path handling;
- network-facing behavior;
- untrusted payload parsing.

Usually needed:

- all runtime-risk checks;
- SAST;
- SCA if dependencies/image changed;
- DAST-style checks if network-facing behavior changed;
- targeted malformed input tests.

## Minimal developer checklist

Before commit/push:

- are secrets out of logs/artifacts?
- are required config keys validated fail-fast?
- is SQLite still runtime state source of truth?
- is YAML only seed/import/export?
- are user-provided URLs validated?
- did I avoid hidden sensitive defaults?
- did I avoid unnecessary abstraction?
- if dependencies changed, were they reviewed?
- if external input is parsed, is it bounded?
- are artifacts safe to inspect?
- is changedetection not public by accident?
- does the commit message or commit body record relevant verification evidence?

## Minimal self-review checklist

Ask:

- does this touch secrets, URLs, webhooks, DB, dependencies, parsing or file paths?
- does it introduce a trust boundary?
- are logs safe?
- are artifacts safe?
- is validation explicit?
- is any check missing for this change level?
- is the solution simple enough?
- does the change stay inside the ROADMAP iteration scope?

## Dependency rules

When dependencies change:

- keep changes intentional and minimal;
- commit both `pyproject.toml` and `uv.lock`;
- review why package is needed;
- review runtime/attack surface impact;
- do not add packages “just in case”;
- do not change dependency surface in the same commit as unrelated feature work unless unavoidable.

If dependencies did not change, `uv.lock` should not change.

## Path / file safety rules

When working with files:

- prefer explicit project paths;
- avoid uncontrolled path building from untrusted input;
- validate run IDs / filenames;
- never trust restored JSON blindly;
- avoid serving raw storage files through web routes;
- use allowlists for artifact access;
- reject path traversal attempts.

Bad pattern:

```text
storage / user_input
```

Better pattern:

```text
validate_id(user_input) → known directory / safe filename
```

## Authority boundary rules

ScoutBot has limited authority.

Allowed in MVP:

- create/update/delete watches in self-hosted `changedetection.io`;
- send Telegram messages;
- mutate its own SQLite state;
- write bounded logs/artifacts under project storage.

Not allowed in MVP:

- write to competitor sites;
- bypass social platform auth/ToS;
- use paid APIs without explicit config and decision;
- execute arbitrary user-provided code;
- run arbitrary browser scripts from Telegram;
- expose raw internal secrets;
- use AI/LLM as runtime decision source;
- store runtime state in YAML.

## Telegram safety rules

Telegram is the primary operator UX in MVP, so handler changes are sensitive.

Rules:

- state mutation requires admin allowlist;
- non-admin users should get safe refusal, not stack traces;
- Telegram IDs must be parsed safely;
- no token in logs;
- no raw update dumps unless redacted and bounded;
- no arbitrary user-supplied command execution;
- no arbitrary jq/xpath/css filter updates from normal users.

## SQLite safety rules

SQLite is the runtime state source of truth.

Rules:

- initialize schema reproducibly;
- use parameterized SQL or safe ORM/query helpers;
- avoid string-concatenated SQL;
- keep migrations/schema changes explicit;
- do not store secrets unless there is a specific approved reason;
- do not make seed YAML the live state;
- backup/export should not leak secrets.

## Import/export safety rules

Seed import/export is useful but can become a trust boundary.

Rules:

- treat imported YAML as untrusted input;
- validate required fields;
- reject malformed URLs;
- reject invalid workspace/project/target IDs;
- avoid path traversal through export paths;
- export only intended state;
- do not export env secrets.

## Artifact safety rules

Allowed when useful:

- run metadata;
- sync results;
- discovery evidence;
- source graph;
- degraded reasons;
- signal records;
- safe webhook event summaries;
- diagnostics without secrets.

Not allowed:

- raw API keys;
- Telegram token;
- webhook secret;
- full request headers;
- full `.env`;
- unbounded raw HTML dumps;
- sensitive payloads without redaction.

## changedetection safety rules

When syncing with changedetection:

- API key comes only from env;
- changedetection URL comes from config;
- changedetection should be private by default;
- watch creation/update/delete is bounded;
- watch UUIDs are persisted in SQLite;
- sync result is logged/artifacted without secrets;
- errors/degraded state are explicit.

Do not use changedetection as a hidden source of truth for ScoutBot state. SQLite remains ScoutBot runtime state source of truth.

## Social/public-profile source rules

ScoutBot may discover public social/profile/link aggregator URLs, but must not overstate reliability.

Rules:

- do not bypass auth;
- do not scrape private data;
- do not use paid APIs without explicit decision;
- mark unsupported/auth/anti-bot cases as degraded;
- keep discovery evidence;
- avoid pretending public social profile pages are stable structured APIs.

## Release/versioning safety rules

ScoutBot uses release automation.

Rules:

- do not manually bump `pyproject.toml.version` for normal feature/fix/docs work;
- do not edit release metadata unless the task is explicitly release-related;
- do not mix release workflow changes with unrelated runtime/security changes;
- if dependency changes are made, commit `pyproject.toml` and `uv.lock` together;
- if dependencies did not change, `uv.lock` should remain unchanged.

Normal verification note:

```text
version not changed
```

If dependencies did not change:

```text
uv.lock not changed
```

## Security and SDLC integration

Use security as part of the normal direct-main workflow:

1. identify change level;
2. implement minimally;
3. run required checks;
4. inspect logs/artifacts;
5. commit with relevant verification evidence;
6. push to `main`.

Do not create separate bureaucracy unless the project actually needs it.

Because current workflow pushes directly to `main`, runtime-risk and security-sensitive changes require stricter self-review before push.

## What not to do

Avoid:

- hidden required defaults;
- logging sensitive state;
- dependency additions without review;
- broad refactors mixed with security-sensitive changes;
- future-proof abstractions that increase risk;
- marking every change as requiring every possible security test;
- letting Telegram users configure arbitrary jq filters in MVP;
- exposing changedetection UI publicly by default;
- writing a custom crawler/diff engine while changedetection solves the need;
- bypassing social auth/anti-bot controls;
- adding AI/LLM into MVP runtime.

## Practical defaults

- docs-only changes: docs review and targeted checks if needed;
- most runtime changes: tests + smoke + log/artifact check;
- runtime code changes: add SAST mindset review;
- dependency/image changes: add SCA;
- webhook/web changes: add DAST-style checks;
- parser changes: add malformed/fuzz-style tests where useful;
- security-sensitive direct-main changes: inspect `git diff` carefully before commit and push.

## Summary

Security in ScoutBot is practical:

- protect secrets;
- validate config;
- keep SQLite as state source of truth;
- keep YAML as seed/import/export only;
- treat URLs/pages/webhooks as untrusted;
- keep changedetection private;
- review dependencies/images;
- use only checks that match real risk;
- keep implementation maintainable;
- verify before direct push to `main`.
