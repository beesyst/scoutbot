### Summary

What was done in this PR.

Include short, concrete statements:

- what behavior changed;
- what files/modules were touched;
- what was intentionally not changed.

### Related issue

Closes #

If relevant, also reference:

- ROADMAP iteration:
- related docs:
- follow-up issues:

### Iteration

- Iteration:
- Goal:
- Change level:
  - [ ] low-risk
  - [ ] runtime-risk
  - [ ] security-sensitive

> Use the current iteration from `docs/ROADMAP.md`.
> Change level should match `docs/SDLC.md` / `docs/SECURITY.md`.

### Scope

What is included / excluded.

**Included**

- ...
- ...

**Excluded**

- ...
- ...

### Changes

- ...
- ...
- ...

### Config / Contract impact

Mark what changed:

- [ ] no config changes
- [ ] `config/settings.yml` contract changed
- [ ] fail-fast validation updated in `src/scoutbot_module/core/settings.py`
- [ ] storage artifact contract changed
- [ ] CLI/runtime behavior changed
- [ ] docs must be updated

If applicable, specify:

**New / changed config keys**

- `...`

**New / changed artifacts**

- `...`

**New / changed JSONL/meta fields**

- `...`

### Verification level

Required checks for this PR:

**Base checks**

- [ ] `pytest -q`
- [ ] smoke run completed
- [ ] logs checked
- [ ] artifacts checked manually

**Quality / security checks**

Mark only what is required for this PR:

- [ ] SAST completed
- [ ] SCA completed
- [ ] DAST completed
- [ ] IAST completed
- [ ] fuzzing completed
- [ ] not applicable (explained in Notes)

> Only mark checks that are required for this change level.
> Use `docs/SDLC.md` and `docs/SECURITY.md` as source of truth.

#### Test details

Commands / scenarios used:

- `...`
- `...`

Include both automated and manual verification when relevant.

#### Manual scenarios checked

- ...
- ...
- ...

### Artifacts

What was created or verified:

- ...
- ...
- ...

If applicable, list exact files, for example:

- `storage/runs/<run_id>/signals.jsonl`
- `storage/runs/<run_id>/orders.jsonl`
- `storage/runs/<run_id>/trades.jsonl`
- `storage/runs/<run_id>/portfolio_summary.json`
- `logs/app.log`

### Security review

Fill only if relevant for this PR:

- secret handling affected:
- external input / payload parsing affected:
- broker/live path affected:
- dependency surface changed:
- serialization / deserialization changed:
- user-controlled paths / files affected:

### Checklist

#### SDLC / scope

- [ ] change stays within current iteration scope
- [ ] issue, code, tests, artifacts, and PR are aligned
- [ ] docs/ROADMAP updated if behavior/contract/artifacts changed
- [ ] related docs updated if needed (`DEV_GUIDE`, `README.ru.md`, `SDLC`, `SECURITY`)

#### Config / runtime

- [ ] config keys are validated fail-fast
- [ ] no hidden defaults were introduced for required keys
- [ ] entrypoint/CLI behavior works as expected
- [ ] storage artifacts are consistent

#### Security

- [ ] no secrets in logs/artifacts
- [ ] no unsafe debug output added
- [ ] dependency changes were reviewed
- [ ] security checks required for this PR were completed

#### Code quality

- [ ] change follows KISS
- [ ] no unnecessary abstraction/refactor was added
- [ ] PEP 8 / project style respected

### Limitations / follow-ups

Anything intentionally left out of scope:

- ...
- ...

### Notes

Anything important for reviewer.

Examples:

- why some checks are marked not applicable;
- known limitations;
- migration/deprecation notes;
- what to inspect first during review.
