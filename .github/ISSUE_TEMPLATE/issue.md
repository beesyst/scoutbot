---
name: Issue
about: "Use title prefixes: Feature:, Fix:, Bug:, Docs:, Chore:, Idea:"
title: "Feature: <short title>"
labels: []
assignees: []
---

### Summary

One sentence: what needs to be done (or explored).

### Type

Select one primary type:

- [ ] Feature
- [ ] Fix
- [ ] Docs
- [ ] Chore
- [ ] Idea

### Roadmap / iteration

- Iteration:
- Stage:
- Goal from `docs/ROADMAP.md`:

If this is not tied to a roadmap iteration, explain why.

### Context

Why this matters. Links, screenshots, references.

Include:

- current problem / limitation;
- why now;
- related issue / PR / roadmap item / artifact if any.

### Scope

What is included / excluded.

**Included**

- ...
- ...

**Excluded**

- ...
- ...

### Deliverable

What should exist when this is done (behavior, file, doc, etc.).

Examples:

- new runtime behavior;
- updated config contract;
- new artifact in `storage/`;
- updated CLI behavior;
- documentation update.

### Acceptance Criteria

What must be true for this task to be considered done.

- ...
- ...
- ...

Keep criteria observable and testable.

### Change level

Choose one:

- [ ] low-risk
- [ ] runtime-risk
- [ ] security-sensitive

> Use `docs/SDLC.md` / `docs/SECURITY.md` to classify the task.

### Config impact

Mark what is expected:

- [ ] no config change expected
- [ ] `config/settings.yml` will change
- [ ] new required keys must be validated fail-fast
- [ ] artifact contract may change
- [ ] CLI/runtime contract may change
- [ ] docs update likely required

If known already, list affected keys/files:

- `...`
- `...`

### Tests

What must be checked:

**Automated**

- [ ] unit/integration tests
- [ ] `pytest -q`

**Smoke / runtime**

- [ ] smoke checks through expected entrypoint
- [ ] log verification
- [ ] artifact verification

**Quality / security**

Mark what is expected for this task:

- [ ] SAST
- [ ] SCA
- [ ] DAST
- [ ] IAST
- [ ] fuzzing
- [ ] some checks are not applicable

Describe the required scenarios briefly:

- ...
- ...
- ...

### Artifacts

What files / outputs should appear or be updated in `storage/`, `logs/`, docs, etc.

Examples:

- `logs/app.log`
- `storage/runs/<run_id>/...`
- `storage/backtests/<run_id>/...`
- `storage/reports/<report_id>/...`
- `docs/ROADMAP.md`
- `docs/DEV_GUIDE.md`
- `docs/SDLC.md`
- `docs/SECURITY.md`

### Security notes

Fill if relevant:

- secrets / env handling involved:
- external input involved:
- live/broker path involved:
- dependency changes involved:
- serialization/parsing involved:
- abuse/misuse angle to consider:

### Definition of Done

Task is done when:

- [ ] behavior is implemented within the declared scope
- [ ] expected entrypoint/CLI works
- [ ] tests are green
- [ ] logs are understandable
- [ ] artifacts are created/updated and consistent
- [ ] no secrets leak into logs/artifacts
- [ ] checks required for this task by `docs/SDLC.md` / `docs/SECURITY.md` are completed
- [ ] docs are updated if contract/behavior/artifacts changed
- [ ] result is ready to be closed through PR

### Notes

Constraints, assumptions, extra links.

Use this section for:

- follow-up ideas;
- explicit non-goals;
- migration notes;
- reviewer hints;
- implementation constraints.
