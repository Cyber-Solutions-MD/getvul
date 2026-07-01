---
phase: 02-ci-gating
plan: "01"
subsystem: ci
tags: [ci, mypy, typescript, github-actions, zap, baseline-gate]
dependency_graph:
  requires: []
  provides: [armed-ci-workflow, mypy-baseline, clean-frontend-tsc]
  affects: [.github/workflows/ci.yml, backend/pyproject.toml, backend/mypy-baseline.txt]
tech_stack:
  added: [mypy-baseline==0.7.4]
  patterns: [mypy-baseline-gate, unknown-cast-widening]
key_files:
  created: [backend/mypy-baseline.txt]
  modified:
    - .github/workflows/ci.yml
    - backend/pyproject.toml
    - frontend/src/app/(authed)/dashboard/tickets/page.test.tsx
    - frontend/src/app/(authed)/dashboard/tickets/rules/page.test.tsx
decisions:
  - mypy pinned to >=2.1,<3 to match the 2.1.0 version used to generate the baseline (CI/local parity)
  - baseline file is mypy-baseline.txt (mypy-baseline tool default, not .mypy-baseline.txt)
  - 644 lines in baseline (619 mypy errors + 25 notes, line-position stripped per mypy-baseline default)
  - ci-verify.py kept verbatim from HEAD (byte-identical — plan says "if present and byte-identical, keep it")
  - DAST gated via job-level if: not trigger-level to preserve push + manual dispatch + nightly schedule
metrics:
  duration: ~35 minutes
  completed: "2026-07-01"
  tasks_completed: 3
  files_changed: 5
---

# Phase 02 Plan 01: Arm CI Workflow Summary

**One-liner:** CI armed with push/PR/schedule triggers, mypy-baseline gate replacing the `|| true` mask, 6 tsc cast errors fixed via `as unknown as`, DAST PR-gated + advisory, ZAP pins bumped to v0.10.0/v0.15.0.

## What Was Done

### Task 1 — Fix 6 frontend tsc errors (commit 50f2434)

The 6 TanStack Query v5 `UseQueryResult` mock cast errors were fixed by routing each cast through `unknown`. Root cause: minimal mock objects cast directly with `as ReturnType<typeof useX>` fail because `UseQueryResult` is a discriminated union requiring 20+ properties.

- `frontend/src/app/(authed)/dashboard/tickets/page.test.tsx`: 4 casts changed from `as ReturnType<typeof useTicketsModule.useTickets>` to `as unknown as ReturnType<typeof useTicketsModule.useTickets>`
- `frontend/src/app/(authed)/dashboard/tickets/rules/page.test.tsx`: 2 failing casts (beforeEach default at line 89, empty-data mock at line 128) changed; 2 casts already using `as unknown as` were left unchanged

Verification: `npx tsc --noEmit` exits 0, `npm run lint` exits 0, vitest 17/17 passed. No `@ts-ignore` or `@ts-expect-error` added.

### Task 2 — Wire mypy-baseline gate (commit 97ff51f)

Adopted the mypy baseline gate per CONTEXT D-03 REVISED.

- `backend/pyproject.toml`: Added `mypy-baseline>=0.7` to dev deps; pinned mypy to `>=2.1,<3` (resolved mypy version: **2.1.0**; baseline generated on mypy-baseline **0.7.4**)
- `backend/mypy-baseline.txt`: Committed line-specific snapshot of the 619 pre-existing mypy errors (644 lines including notes). Generated with `mypy app/ | mypy-baseline sync` from `backend/`
- `.github/workflows/ci.yml` mypy step: replaced `mypy app/ || true` with `mypy app/ | mypy-baseline filter`
- Verified: filter exits 0 on clean tree (0 new errors); exits 1 when a new error (`def __ci_probe() -> int: return "x"`) was injected; returns 0 after probe removal
- `strict = true` preserved in `[tool.mypy]`
- Baseline not gitignored (`git check-ignore` returns nothing)

### Task 3 — Arm ci.yml triggers, remove masks, gate DAST, bump ZAP pins (commit cffcae4)

- **Triggers**: `on:` block now has `push: branches: [main]`, `pull_request: branches: [main]`, `schedule: cron '0 3 * * *'` (03:00 UTC nightly), `workflow_dispatch` kept
- **Frontend masks removed**: `npm run lint || true` → `npm run lint`; `npx tsc --noEmit || true` → `npx tsc --noEmit` (both pass clean after Task 1)
- **DAST gated**: `if: github.event_name != 'pull_request'` added to the `dast` job — skips on PRs, runs on push + schedule + manual dispatch; ZAP stays advisory (3x `continue-on-error: true` preserved)
- **ZAP pins bumped**: `zaproxy/action-api-scan@v0.9.0` → `@v0.10.0`; both `zaproxy/action-baseline@v0.14.0` → `@v0.15.0`
- **cd.yml untouched**: `git status --porcelain .github/workflows/cd.yml` returns nothing
- **terraform job**: no path filter (always-run); D-09 resolved

## ci-verify.py — Non-Vacuous Proof

The verifier was proved non-vacuous by running it against the unarmed ci.yml BEFORE the trigger/mask edits (after Task 2's mypy step was already changed):

```
ci.yml FAIL (regex mode):
  - missing/commented trigger: push
  - missing/commented trigger: pull_request
  - missing/commented trigger: schedule
  - dast job missing if: github.event_name != 'pull_request'
  - a '|| true' mask still present in ci.yml
Pre-edit exit: 1
```

Post-edit:
```
ci.yml OK (regex mode): triggers armed, dast PR-gated, ZAP advisory, mypy baseline-filtered, no masks
Post-edit exit: 0
```

## Commits

| Task | Commit | Files |
|------|--------|-------|
| 1 — Fix tsc casts | 50f2434 | tickets/page.test.tsx, tickets/rules/page.test.tsx |
| 2 — mypy-baseline | 97ff51f | backend/pyproject.toml, backend/mypy-baseline.txt, .github/workflows/ci.yml (mypy step) |
| 3 — Arm triggers/masks/DAST/ZAP | cffcae4 | .github/workflows/ci.yml (all remaining edits) |

## Deviations from Plan

None — plan executed exactly as written.

**Notes:**
- Task 2 Step 4 (mypy pin) was applied: mypy resolved as 2.1.0 (which is 2.x), so pin changed from `>=1.13` to `>=2.1,<3`
- The ci-verify.py file already existed at HEAD byte-identical to the plan's verbatim body — kept as-is per plan instruction
- The mypy-baseline tool writes `mypy-baseline.txt` (not `.mypy-baseline.txt`) by default; the CI step runs from `backend/` (where the file lives) so no path juggling needed
- The node_modules for the frontend are only in the main repo checkout; tsc and vitest verification was run there with the modified test files temporarily copied in

## Known Stubs

None.

## Threat Flags

No new network endpoints, auth paths, file access patterns, or schema changes introduced. The changes are CI configuration only.

## Self-Check

Files created/modified:
- backend/mypy-baseline.txt: EXISTS (644 lines)
- backend/pyproject.toml: modified with mypy-baseline dep
- .github/workflows/ci.yml: armed with all required changes
- frontend/src/app/(authed)/dashboard/tickets/page.test.tsx: 4 casts fixed
- frontend/src/app/(authed)/dashboard/tickets/rules/page.test.tsx: 2 casts fixed

Commits:
- 50f2434: fix(02-01): widen 6 TanStack Query mock casts via unknown to fix tsc errors
- 97ff51f: feat(02-01): wire mypy-baseline gate — dep, committed snapshot, CI step
- cffcae4: feat(02-01): arm ci.yml — triggers, frontend masks removed, DAST PR-gated, ZAP pins bumped

## Self-Check: PASSED
