# SDLC — ScoutBot

## Purpose

This document defines the lightweight SDLC used in `ScoutBot`.

The goal is to keep development:

- disciplined;
- reproducible;
- easy to follow;
- safe enough for a self-hosted monitoring tool;
- free from unnecessary bureaucracy.

ScoutBot uses a practical direct-main workflow:

```text
ROADMAP iteration → main worktree → code → tests → artifacts → commit → push to main
```

This document does not replace `docs/ROADMAP.md`.

- `ROADMAP` defines where the project goes by stages and iterations.
- `Code` implements the current iteration scope.
- `Tests` verify behavior at the required risk level.
- `Artifacts` prove runtime behavior where applicable.
- `Commit` records what was delivered, checked and pushed.
- `SDLC` defines the working rules.

ScoutBot does not currently require:

- GitHub Issues;
- separate feature branches;
- Pull Requests;
- formal merge review.

Those can be introduced later if project risk, team size or deployment process requires them. For now, the project optimizes for fast solo/operator development with enough verification discipline.

## Core principles

Development in ScoutBot should follow these rules:

- make small iteration-sized changes;
- stay inside the current ROADMAP scope;
- use `config/settings.yml` as runtime/config source of truth;
- use SQLite as runtime state source of truth;
- use `config/seeds/*.yml` only for seed/import/export;
- validate new required config keys fail-fast;
- prefer simple solutions over unnecessary abstractions;
- keep logs understandable;
- keep artifacts reproducible;
- do not leak secrets into logs or storage;
- keep external engine boundary explicit;
- verify changes before pushing to `main`;
- keep commit evidence clear enough to understand what was changed and checked.

## Workflow

### 1. ROADMAP

`docs/ROADMAP.md` defines:

- stage;
- iteration;
- goal;
- scope;
- deliverable;
- artifacts;
- checks;
- DoD.

Before coding, map the task to the current ROADMAP iteration.

Do not implement work that belongs to a later iteration unless the ROADMAP is explicitly updated first.

### 2. Main worktree

Implementation happens directly in the current main worktree.

This is intentional for the current project phase.

Rules:

- keep the working set small;
- avoid mixing several roadmap iterations in one commit;
- do not refactor unrelated areas;
- do not carry unfinished future architecture;
- keep changes easy to inspect through `git diff`.

### 3. Code

Implementation rules:

- stay within current iteration scope;
- do not mix unrelated features in one change set;
- do not add future architecture without current need;
- do not hide required runtime values inside code;
- do not weaken existing boundaries without reason;
- do not remove existing checks without reason.

Preferred style:

- KISS;
- minimal changes;
- predictable behavior;
- PEP 8;
- explicit validation;
- explicit failure modes.

### 4. Tests

Every change should be verified at the appropriate risk level.

Common checks:

- `uv run pytest -q`;
- smoke through expected entrypoint;
- manual log inspection;
- manual artifact inspection.

If the change affects runtime behavior, config contract, DB schema, Telegram UX, changedetection API boundary, webhook handling, URL parsing, HTML parsing or dependencies, stronger checks may be required.

### 5. Artifacts

When applicable, results should be visible through artifacts.

Typical places:

- `logs/app.log`;
- `storage/db/scoutbot.sqlite3`;
- `storage/runs/<run_id>/...`;
- `storage/discovery/<run_id>/...`;
- `storage/signals/<YYYY-MM-DD>.jsonl`;
- `storage/interfaces/...`;
- `storage/exports/...`.

Artifacts should be:

- reproducible;
- understandable;
- aligned with logs;
- aligned with the current iteration;
- safe for operator inspection.

Artifacts should not contain:

- Telegram bot token;
- changedetection API key;
- webhook secret;
- raw request headers with sensitive data;
- `.env` content;
- unbounded sensitive external payloads.

### 6. Commit

A commit is the main delivery/evidence unit in the current workflow.

The commit should be small enough to answer:

- what changed;
- which ROADMAP iteration it belongs to;
- what was tested;
- which artifacts/logs were checked;
- whether security-sensitive boundaries were touched.

For docs-only or low-risk changes, a short conventional commit is enough:

```text
docs(sdlc): align process with direct-main workflow
```

For runtime-risk or security-sensitive changes, prefer a commit body:

```text
Iteration: 1 — Telegram MVP
Change level: runtime-risk

Summary:
- Added Telegram /add target flow
- Persisted targets in SQLite
- Added changedetection watch sync for active targets

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

### 7. Push to main

A task or iteration item is done only after:

- scope is satisfied;
- required checks are completed;
- artifacts/logs are consistent;
- docs are updated if needed;
- changes are committed;
- changes are pushed to `main`.

Direct push to `main` is acceptable only after verification.

## Definition of Done

A task is considered done when:

- behavior is implemented within declared scope;
- config is read from `config/settings.yml`;
- runtime state lives in SQLite, not YAML;
- new required keys are validated fail-fast in `src/scoutbot_module/core/settings.py`;
- the feature runs through intended entrypoint;
- logs are written and understandable;
- artifacts are written when expected;
- tests and manual checks are completed;
- secrets do not leak into logs/artifacts;
- external engine boundary remains explicit;
- docs are updated if behavior, contract, artifacts or checks changed;
- commit clearly records the change and verification evidence where needed.

## Minimal required checks

### Base checks

Default checks:

```bash
uv run pytest -q
./start.sh doctor
```

Also inspect:

- `logs/app.log`;
- relevant files in `storage/`.

For docs-only changes, `./start.sh doctor` may be unnecessary. That should be an intentional decision, not a silent skip.

### Entry-point related checks

If entrypoint behavior changed, also run the affected command:

```bash
./start.sh
./start.sh telegram
./start.sh webhook
./start.sh init-db
./start.sh sync
./start.sh import-seed config/seeds/noders.yml
./start.sh export-seed storage/exports/noders.export.yml
```

### Artifact-related checks

If artifacts changed, verify:

- file exists where expected;
- JSON/JSONL structure is correct;
- artifact matches logs and scenario;
- secrets are absent;
- sensitive payload is bounded/redacted.

### SQLite-related checks

If SQLite schema or persistence logic changed, verify:

- DB initializes cleanly;
- expected tables exist;
- migrations or schema init are reproducible;
- seed import works;
- Telegram/runtime edits write to SQLite, not YAML;
- export-seed works if export behavior is affected.

Relevant commands:

```bash
./start.sh init-db
./start.sh import-seed config/seeds/noders.yml
./start.sh export-seed storage/exports/noders.export.yml
```

### changedetection-related checks

If changedetection sync changed, verify:

- API key is read only from env;
- API key is not logged;
- watch create/update/delete calls are bounded;
- duplicate watches are not created accidentally;
- changedetection watch UUID is persisted back to SQLite;
- external engine degraded state is visible;
- sync artifact is written when expected.

Relevant command:

```bash
./start.sh sync
```

### Telegram-related checks

If Telegram UX or handlers changed, verify:

- state-changing commands check admin allowlist;
- commands write to SQLite;
- YAML seed is not mutated;
- audit log is written where expected;
- user-facing messages are clear;
- Telegram token is not logged.

Relevant command:

```bash
./start.sh telegram
```

### Webhook-related checks

If webhook behavior changed, verify:

- webhook secret is required;
- invalid secret is rejected;
- malformed payload is handled safely;
- duplicate diff does not spam;
- signal is persisted;
- Telegram alert is sent only after validation/dedupe.

Relevant command:

```bash
./start.sh webhook
```

## Change levels

### Low-risk

Use this when the change is local and does not affect runtime behavior.

Examples:

- docs;
- comments;
- test-only additions;
- formatting;
- non-runtime refactor.

Usually required:

- targeted tests if applicable;
- docs review;
- no full smoke required unless behavior is touched.

### Runtime-risk

Use this when the change affects normal application behavior.

Examples:

- settings validation;
- SQLite schema/repo;
- Telegram handlers;
- changedetection sync;
- webhook handling;
- artifacts;
- signal classification;
- import/export;
- CLI dispatch;
- storage paths.

Usually required:

- `uv run pytest -q`;
- smoke through affected entrypoint;
- log inspection;
- artifact inspection.

### Security-sensitive

Use this when the change affects trust boundaries or sensitive paths.

Examples:

- env/secrets;
- changedetection API key handling;
- Telegram token handling;
- webhook secret handling;
- URL validation;
- HTML parsing from untrusted pages;
- social/link discovery;
- file/path handling;
- dependency changes;
- network-facing routes;
- external connector behavior;
- untrusted payload parsing.

Usually required:

- all runtime-risk checks;
- SAST mindset review;
- SCA if dependencies changed;
- DAST-style route checks if network-facing behavior changed;
- malformed input checks;
- fuzzing only for fragile parsers if useful.

## Security-aware development rule

Not every task needs every security practice.

Use only what matches the change:

- SAST for code changes touching runtime/trust boundaries;
- SCA for dependency changes;
- DAST for network-facing behavior;
- IAST only for high-risk runtime instrumentation cases;
- fuzzing for parsers/serializers/input-normalizers.

The goal is not to tick every box. The goal is to apply the right check for the risk.

See `docs/SECURITY.md`.

## Roadmap update rules

Update `docs/ROADMAP.md` when:

- iteration status changes;
- goal/scope/deliverable changes;
- DoD changes;
- artifact contract changes;
- checks change;
- stage wording becomes outdated.

Do not update ROADMAP for tiny implementation details that do not affect iteration contract.

## Docs update rules

Usually check these files:

- `docs/ROADMAP.md`;
- `docs/ARCHITECTURE.md`;
- `docs/SPEC.md`;
- `docs/DEV_GUIDE.md`;
- `docs/SECURITY.md`;
- `README.ru.md`.

Update them if one of the following changed:

- config contract;
- runtime behavior;
- entrypoint usage;
- database schema contract;
- artifact structure;
- Telegram UX contract;
- changedetection API boundary;
- verification flow;
- security expectations;
- dependency surface.

## Commit rules

Each meaningful commit should include or imply:

- iteration reference when useful;
- change level when runtime/security-sensitive;
- summary;
- tests/checks;
- artifacts if applicable;
- security notes if applicable;
- limitations if known.

Good rule:

- `ROADMAP` explains the iteration-level target.
- `Commit` explains what was delivered and verified.

## Commit message examples

### Docs-only

```text
docs(sdlc): align process with direct-main workflow
```

### Runtime feature

```text
feat(telegram): add target creation flow
```

### Runtime fix

```text
fix(sync): handle changedetection unavailable state
```

### Security-sensitive fix

```text
fix(webhook): reject invalid changedetection secrets
```

### Dependency change

```text
chore(deps): add sqlmodel
```

## KISS rule for process

To keep the process simple:

- one change should map to one ROADMAP iteration item where practical;
- do not mix several roadmap iterations in one commit;
- do not require documents nobody will read;
- do not add process steps unless they improve quality or safety;
- do not create Issue/branch/PR overhead unless the project actually needs it;
- do not skip verification just because the process is lightweight.

## Typical developer flow

A normal development cycle in ScoutBot looks like this:

1. Open `docs/ROADMAP.md`.
2. Select the current iteration.
3. Confirm the task fits the iteration scope.
4. Determine change level:
   - `low-risk`;
   - `runtime-risk`;
   - `security-sensitive`.

5. Implement the change in the main worktree.
6. Run required checks.
7. Inspect logs and artifacts.
8. Update docs if needed.
9. Check `git diff`.
10. Commit with clear message/evidence.
11. Push to `main`.

## Verification checklist mindset

Before pushing, the developer should be able to answer:

- does this stay inside iteration scope?
- is config still source of truth?
- is SQLite still runtime state source of truth?
- are seed YAML files still import/export/bootstrap only?
- are required keys validated fail-fast?
- are logs/artifacts understandable?
- are secrets safe?
- are external boundaries explicit?
- are tests/checks appropriate for the risk?
- is the solution simple enough?
- does the commit explain what was changed and verified?

## Direct-main risk controls

Because ScoutBot currently uses direct pushes to `main`, keep these safeguards:

- small commits;
- no mixed iteration scope;
- no unverified runtime changes;
- no dependency changes hidden inside feature commits;
- no manual version bump unless the task is explicitly release-related;
- no `uv.lock` changes unless dependencies changed;
- no secret-bearing files committed;
- no `.env` committed;
- no generated local DB/log artifacts committed unless explicitly intended as fixtures.

## Release/versioning rule

ScoutBot uses release automation.

Rules:

- do not manually bump `pyproject.toml.version` for normal feature/fix/docs work;
- do not edit release metadata unless the task is explicitly release-related;
- do not mix dependency changes with release/versioning changes unless the task requires it.

For normal tasks, verification note should say:

```text
version not changed
```

If dependencies did not change:

```text
uv.lock not changed
```

If dependencies changed, `pyproject.toml` and `uv.lock` must be committed together.

## What not to do

Do not:

- write a custom crawler/diff engine while `changedetection.io` solves the need;
- add AI/LLM into MVP unless the iteration is explicitly about optional AI summaries;
- store runtime state in YAML;
- use `config/seeds/*.yml` as live state;
- log secrets;
- bypass auth/anti-bot protections of social platforms;
- add paid APIs without a separate product decision;
- add n8n as core state/runtime layer;
- add a second runtime/orchestrator without an explicit ROADMAP decision;
- add process steps that nobody will follow.

## Summary

ScoutBot uses lightweight but real SDLC.

The key discipline is:

- small scoped iterations;
- config as runtime/config source of truth;
- SQLite as runtime state source of truth;
- YAML as seed/import/export only;
- fail-fast validation;
- reproducible artifacts;
- understandable logs;
- direct-main workflow with verification before push;
- evidence in tests, logs, artifacts and commit messages;
- security checks only where they matter.
