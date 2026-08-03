---
phase: 28-eval-cost-observability-gate
plan: 03
subsystem: api
tags: [fastapi, sqlalchemy, jsonb-aggregation, rbac, audit-log, cost-observability, ai]

# Dependency graph
requires:
  - phase: 24-ai-foundation-explain-this-vuln
    provides: check_tenant_budget()/get_month_to_date_spend() fail-closed budget guard, the ai.*-namespaced AuditLog schema (audit_log_ai_call), get_tenant_anthropic_key() BYOK resolution, get_model_and_budget()
  - phase: 26-prioritization-narrative
    provides: batch.py's user_email="system:scheduler" discriminator (the only reliable batch/on-demand split signal) + the batch-cost booking the month-to-date SUM depends on
  - phase: 28-02
    provides: sibling AIE-03 no-bypass coverage precedent (same phase, no direct code dependency)
provides:
  - "GET /api/v1/ai/usage — require_admin-gated, tenant-scoped aggregation endpoint over the EXISTING ai.* AuditLog rows (D-08, no new telemetry)"
  - "The derived breaker_tripped boolean exposed to the frontend for the first time (AIE-03's frontend-exposure delta), computed with check_tenant_budget()'s EXACT comparison"
  - "6 fixed capability_breakdown rows (vuln/host/remediation/remediation-guidance/prioritization-on-demand/prioritization-batch) with calls/cost_usd/tokens per row"
  - "degraded_calls_count footnote figure per 28-UI-SPEC.md's exact formula"
affects: [28-04 (frontend admin pane consumes this exact response shape), 28-05 (CI wiring)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "breaker_tripped reuses check_tenant_budget()'s exact comparison (monthly_cap_usd is not None and spent >= monthly_cap_usd) — never a second, independently re-derived comparison, so the admin pane can never disagree with the backend guard (D-09)"
    - "user_email == / != 'system:scheduler' as the SOLE batch/on-demand discriminator — never status (a successful batch call also audits status='ok', byte-identical to a successful on-demand call)"
    - "6 small per-capability AuditLog aggregation queries (readability) over one combined GROUP BY query, given this is a human-triggered, admin-only, low-frequency read over a small monthly row count"

key-files:
  created:
    - backend/app/api/v1/ai/usage.py
    - backend/tests/test_ai_usage.py
  modified:
    - backend/app/api/v1/ai/__init__.py
    - .planning/phases/28-eval-cost-observability-gate/deferred-items.md

key-decisions:
  - "degraded_calls_count implements 28-UI-SPEC.md's exact formula (status NOT IN ('ok') AND status NOT LIKE 'batch_%'), not RESEARCH.md's simpler `status != 'ok'` code-example sketch — the plan's own <action> text and the UI-SPEC are authoritative; a bare != 'ok' would over-count batch_skipped_budget_exceeded/batch_errored/etc rows the breaker banner already surfaces elsewhere"
  - "AIE-03/AIE-04 left [ ] Pending in REQUIREMENTS.md — AIE-04 needs Plan 04's frontend pane, AIE-03 needs Plan 05's CI wiring (shared-ID gate: both IDs are declared by more than one plan in this phase), mirroring the AIE-01/02 precedent already established by Plans 01-02"

requirements-completed: []  # AIE-03/AIE-04 intentionally NOT marked complete — see key-decisions; AIE-04 needs Plan 04, AIE-03 needs Plan 05

# Metrics
duration: 35min
completed: 2026-08-03
---

# Phase 28 Plan 03: AIE-04 Usage/Cost Aggregation Endpoint Summary

**A require_admin, tenant-scoped `GET /api/v1/ai/usage` aggregating the existing `ai.*` AuditLog rows into month-to-date spend, a 6-row per-capability breakdown split on `user_email` (not `status`), the derived `breaker_tripped` boolean, and a degraded-calls footnote — zero new telemetry, zero schema changes.**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-08-03T08:33:39Z (approx, immediately following 28-02)
- **Completed:** 2026-08-03T08:56:17Z
- **Tasks:** 2 completed
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments

- **AIE-04 backend (`backend/app/api/v1/ai/usage.py`):** A thin `require_admin`-gated route mirroring `status.py`'s shape. Resolves `model`/`monthly_budget_usd` via `get_model_and_budget()`, `spent_this_month_usd` via `get_month_to_date_spend()`, and `configured` via `get_tenant_anthropic_key()` — all pre-existing reads, zero new queries beyond the per-capability breakdown itself. Every aggregation query is scoped by `AuditLog.tenant_id == user.tenant_id` and `AuditLog.action.like("ai.%")` (T-28-03: no cross-tenant leakage).
- **AIE-03 frontend-exposure delta:** `breaker_tripped = monthly_cap_usd is not None and spent >= monthly_cap_usd` — the byte-identical comparison `check_tenant_budget()` uses internally (D-09), never a second, independently-authored one. This is the first time the derived breaker state is exposed outside the fail-closed guard itself.
- **6-row capability breakdown:** `vuln` / `host` / `remediation` / `remediation-guidance` / `prioritization` (on-demand) / `prioritization` (batch), each with `calls`/`cost_usd`/`tokens`. The two prioritization rows split on `AuditLog.user_email == / != "system:scheduler"` — proven by a test that seeds BOTH rows with `status="ok"` (a status-based split could not tell them apart; batch.py:511's real success path also audits `status="ok"`).
- **degraded_calls_count:** implements 28-UI-SPEC.md's exact formula (`status NOT IN ('ok') AND status NOT LIKE 'batch_%'`), proven by a test that seeds a genuinely-degraded row (counted) alongside a `batch_skipped_budget_exceeded` row (excluded) and a plain `ok` row (excluded).
- **Registration:** `usage.router` added to `app/api/v1/ai/__init__.py`, mirroring `status.router`'s registration exactly (last position, matching the newest-router convention).
- **Tests (`backend/tests/test_ai_usage.py`, 9 cases):** RBAC (viewer/analyst 403, admin 200 + confirms 6 fixed rows), tenant isolation (tenant B's seeded spend absent from tenant A's totals/breakdown), the user_email batch/on-demand split, `breaker_tripped` true/false/false for over-cap/under-cap/null-cap, and the degraded-count formula's inclusion/exclusion cases. All 9 passed against the already-implemented Task 1 endpoint on first run.

## Task Commits

Each task was committed atomically:

1. **Task 1: GET /api/v1/ai/usage aggregation endpoint + registration** - `48726f8` (feat)
2. **Task 2: usage endpoint tests (RBAC, tenant scope, batch split, breaker derivation)** - `06abd80` (test)

**Plan metadata:** (this commit) `docs(28-03): complete AIE-04 usage/cost aggregation endpoint plan`

## Files Created/Modified

- `backend/app/api/v1/ai/usage.py` - New `GET /api/v1/ai/usage` require_admin aggregation endpoint (6-row breakdown, breaker_tripped, degraded_calls_count)
- `backend/app/api/v1/ai/__init__.py` - Registers `usage.router`, mirroring `status.router`
- `backend/tests/test_ai_usage.py` - New 9-test suite: RBAC, tenant isolation, batch split, breaker derivation, degraded-count formula
- `.planning/phases/28-eval-cost-observability-gate/deferred-items.md` - Logs a confirmed-pre-existing, unrelated `mypy-baseline.txt` note-line drift found while verifying Task 1

## Decisions Made

- **degraded_calls_count formula sourced from 28-UI-SPEC.md, not RESEARCH.md's simpler sketch:** the plan's own `<action>` text specifies `status NOT IN ('ok') AND status NOT LIKE 'batch_%'` (28-UI-SPEC.md line ~153's exact wording), which is more precise than RESEARCH.md's illustrative `status != "ok"` code example — the UI-SPEC's formula deliberately excludes `batch_`-prefixed skip/error statuses the breaker banner already surfaces elsewhere, so it was implemented exactly as specified, not the earlier RESEARCH sketch.
- **`_seed_anthropic_connector` reused verbatim** from `test_ai_budget_coverage.py` (same exact signature this file needs) rather than re-derived; `_seed_ai_usage_row` adapted from `test_ai_budget.py::_seed_ai_spend` to additionally parametrize `resource_type`/`user_email`/`status`/tokens, which the 6-row breakdown + degraded-count tests both need.
- **AIE-03/AIE-04 left `[ ]` Pending in REQUIREMENTS.md:** AIE-04 is declared by both this plan and Plan 04 (frontend pane) — the shared-ID gate holds it open until Plan 04 lands. AIE-03 is declared by Plans 02, 03, AND 05 (CI wiring) — held open until Plan 05 lands. Both mirror the AIE-01/02 precedent already established by Plans 01-02 this phase.
- **Task 2 tests passed against the already-implemented Task 1 endpoint on first run** (no separate literal RED-must-fail phase) — this mirrors the already-documented Phase 25-03/26-03 precedent for the identical "route built in one task, its own test suite written in the next task within the same plan" shape, where a genuine pre-implementation RED would be structurally impossible (the implementation already exists as of Task 1's commit).

## Deviations from Plan

None - plan executed exactly as written. One out-of-scope, confirmed-pre-existing discovery was logged (not fixed) per the deviation rules' scope boundary:

### Logged, Not Fixed (Out of Scope)

**1. Pre-existing `mypy-baseline.txt` note-line drift (local environment, unrelated to this plan)**

- **Found during:** Task 1 post-implementation verification (`mypy app/ | mypy-baseline filter --allow-unsynced`, mirroring `ci.yml`'s exact invocation).
- **Issue:** The filter reports a false "Your changes introduced new violations" banner (`note 27 -3 +6`) — all 6 "new" lines are `note:` sub-lines attached to an already-baselined `Library stubs not installed for "jose"` error, whose first-occurrence file (and therefore which file's note-trio survives mypy's own duplicate-note suppression) shifts with mypy's internal file-processing order.
- **Confirmed pre-existing, not caused by this plan:** Reverted `usage.py`/`__init__.py` to clean HEAD (temporarily, then restored) and re-ran the identical command — the SAME `note 27 -3 +6` delta appears with ZERO Plan 03 changes present. Also reproduced running mypy against only the two untouched sibling files `status.py`/`feedback.py`. Both `usage.py` and `__init__.py` produce ZERO mypy errors when checked directly in isolation.
- **Why not fixed:** Root cause is environment/tooling drift (local mypy/mypy-baseline versions vs. whatever produced the committed baseline), not a real type violation in any file this plan touches — out of this narrowly-scoped endpoint task.
- **Logged in:** `deferred-items.md` (28-03 entry), committed as part of Task 1's commit (`48726f8`).

---

**Total deviations:** 0 auto-fixed. 1 out-of-scope discovery logged per the scope-boundary rule (confirmed pre-existing via a clean-HEAD control test, not caused by this plan).
**Impact on plan:** None — the plan's implementation was correct and complete as specified; the logged item is environment noise unrelated to any file this plan created or modified.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. The endpoint reads exclusively from the already-provisioned local Postgres via the existing `AuditLog`/`ConnectorConfig` tables.

## Next Phase Readiness

- The response shape is locked for Plan 04's frontend hook: `{configured: bool, model: str, monthly_budget_usd: float | None, spent_this_month_usd: float, breaker_tripped: bool, capability_breakdown: [{resource_type: str, is_batch: bool | None, calls: int, cost_usd: float, tokens: int}] (6 entries), degraded_calls_count: int}`.
- Plan 04 (the admin "AI usage & settings" pane) can proceed independently against this exact shape — no further backend changes expected.
- Backend regression is fully clean: `pytest --collect-only` reports 733/733 tests collected (up from 724 pre-plan), full `tests/test_ai_*.py` + `tests/evals/` sweep 340/340 green (331 prior + 9 new), `ruff check .` clean, and the route mounts cleanly at app-creation time.

---
*Phase: 28-eval-cost-observability-gate*
*Completed: 2026-08-03*

## Self-Check: PASSED

All 4 claimed files verified present on disk (`backend/app/api/v1/ai/usage.py`, `backend/tests/test_ai_usage.py`, `backend/app/api/v1/ai/__init__.py`, `deferred-items.md`). Both claimed commit hashes (`48726f8`, `06abd80`) verified present in `git log --oneline --all`. All plan-level `<verification>` items re-confirmed: route mounted + admin-gated, user_email-based batch split (not status), `breaker_tripped` matches `check_tenant_budget()`'s exact comparison, zero new tables/migrations.
