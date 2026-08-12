---
phase: 34-historical-recompute-consumer-cutover
plan: 05
subsystem: api
tags: [sqlalchemy, fastapi, feature-flag, risk-scoring, cutover, rbac, audit, gap-closure]

# Dependency graph
requires:
  - phase: 34-historical-recompute-consumer-cutover
    provides: "Tenant.cutover_risk_exposure_scoring (migration 044), RiskExposureBackfillJob + risk_backfill_service.enqueue_backfill_job (Plan 01); flag-gated service.py branch pattern (Plan 02); risk_cutover_service.py + risk_cutover_router.py admin/RBAC/audit shape (Plan 03); capture_daily_snapshot unconditional dual-write (Plan 04)"
provides:
  - "get_risk_score_trend's PRIMARY avg_risk series flag-gated on Tenant.cutover_risk_exposure_scoring — OFF byte-identical (avg_risk_score only, no extra key), ON swaps to avg_risk_exposure_score, mirroring service.py's sort=\"triage\"/get_top_findings_for_ai_batch pattern (closes RISK-08's third named consumer, 34-VERIFICATION.md GAP 1)"
  - "POST /api/v1/risk-cutover/backfill/enqueue — admin-only production trigger for RISK-07's backfill machinery, wrapping the already-idempotent enqueue_backfill_job with audit()-then-commit (closes 34-VERIFICATION.md GAP 2 / Human Verification #2)"
  - "test_risk_trend_cutover.py: 3-test RISK-08 trend-chart fixture suite (OFF-byte-identical, ON-new-series, OFF-insulated-from-missing-new-field)"
  - "test_risk_backfill_enqueue_endpoint.py: 4-test RISK-07 admin-endpoint fixture suite (RBAC 403, create+audit, idempotent-when-active, idempotent-when-completed)"
  - "Updated test_risk_boundary_guard.py::test_trend_no_cliff — re-scoped from asserting the old unconditional dual-key shape to proving continuity under the flag a tenant actually reads with"
affects: [35-source-aware-filtering-provenance-badges]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Primary-series flag swap (trend/read consumers): same key name, source flag-gated, zero extra keys on either path — the third application of the 34-02 once-per-call scalar Tenant fetch + branch-only-the-primary-key idiom, now proven reusable beyond ORDER BY clauses (a plain dict-value read)"
    - "Idempotent-enqueue audit gating: audit only a genuinely NEW mutation (existing-row check before calling the idempotent factory function), never a repeated no-op — keeps the audit log meaningful when wrapping an already-idempotent lower-layer function in an admin endpoint"

key-files:
  created:
    - backend/tests/test_risk_trend_cutover.py
    - backend/tests/test_risk_backfill_enqueue_endpoint.py
  modified:
    - backend/app/vulnerabilities/trends.py
    - backend/app/vulnerabilities/risk_cutover_service.py
    - backend/app/vulnerabilities/risk_cutover_router.py
    - backend/app/audit.py
    - backend/tests/test_risk_boundary_guard.py

key-decisions:
  - "get_risk_score_trend's ON path does NOT add a separate avg_risk_exposure key (the shape 34-04 shipped) — it swaps what avg_risk itself reads from, exactly mirroring service.py's primary-order-key-swap pattern with zero extra keys on either branch. This is a stricter, more literal reading of 34-VERIFICATION.md GAP 1's fix instruction (\"do NOT add extra keys on the OFF path\" + \"exactly like the 34-02 pattern\") than a design that kept both keys and only gated one of them."
  - "capture_daily_snapshot's RISK-10 dual-write stays completely unconditional — only get_risk_score_trend (the READ/consumer function) references the flag. Re-grepped post-fix: both flag references in trends.py are inside get_risk_score_trend (lines 166-217); capture_daily_snapshot (lines 247+) has none."
  - "test_risk_boundary_guard.py::test_trend_no_cliff was rewritten, not left as-is — its old assertions (avg_risk_exposure key present unconditionally) directly contradicted the corrected flag-gated design, so leaving it green would have required NOT closing the gap. The rewritten test proves the more meaningful property: a tenant reading under the flag it actually cut over with sees a continuous primary series, while a tenant that never cut over sees its own (possibly cliffed) old series — which is the correct, expected RISK-08 behavior for an un-flipped tenant."
  - "enqueue_backfill audits only on a genuinely new enqueue (checked via _backfill_status returning None before the call) — a repeat call while a job is pending/in_progress/completed is a harmless idempotent no-op and does not add a second audit row, keeping the audit trail meaningful (one row per tenant's actual backfill start, not one per admin click)."
  - "Discovered and fixed a test-only issue (not a router/service bug): the client_factory-based HTTP tests hit the endpoint through a SEPARATE DB session (app.db.session.async_session_factory) from the test's own db_session fixture (documented WR-13 in conftest.py) — tenant_a/admin_user fixtures only flush (uncommitted) by default, so an explicit db_session.commit() is required before the fixture rows are visible cross-connection. Added the missing commits, mirroring test_risk_cutover_ack.py's existing seeding pattern; verified via a live traceback repro (FK violation on risk_exposure_backfill_jobs.tenant_id) before concluding it was a test-fixture gap, not an application bug."

patterns-established:
  - "Primary-series flag swap for read-only trend/report consumers: reusable for any future dashboard/report field that needs to cut over from an old to a new scoring model behind the same tenant flag."

requirements-completed: [RISK-08]

coverage:
  - id: D1
    description: "get_risk_score_trend's avg_risk series reads avg_risk_score (OLD) when cutover_risk_exposure_scoring is OFF (default) — byte-identical to pre-Phase-34, no avg_risk_exposure key present"
    requirement: "RISK-08"
    verification:
      - kind: unit
        ref: "backend/tests/test_risk_trend_cutover.py#test_trend_flag_off_is_byte_identical"
        status: pass
      - kind: unit
        ref: "backend/tests/test_risk_trend_cutover.py#test_trend_flag_off_missing_new_score_defaults_zero"
        status: pass
    human_judgment: false
  - id: D2
    description: "get_risk_score_trend's avg_risk series reads avg_risk_exposure_score (NEW) when cutover_risk_exposure_scoring is ON"
    requirement: "RISK-08"
    verification:
      - kind: unit
        ref: "backend/tests/test_risk_trend_cutover.py#test_trend_flag_on_surfaces_new_series"
        status: pass
    human_judgment: false
  - id: D3
    description: "test_trend_no_cliff (34-04's boundary-guard fixture) re-proven under the corrected flag-gated design: a tenant reading with the flag OFF sees the old (possibly cliffed) series; a tenant reading with the flag ON sees the new continuous series for its whole trend window"
    requirement: "RISK-08"
    verification:
      - kind: unit
        ref: "backend/tests/test_risk_boundary_guard.py#test_trend_no_cliff"
        status: pass
    human_judgment: false
  - id: D4
    description: "POST /api/v1/risk-cutover/backfill/enqueue is admin-only (403 for analyst/viewer) and never creates a job row on a rejected request"
    requirement: "RISK-07"
    verification:
      - kind: unit
        ref: "backend/tests/test_risk_backfill_enqueue_endpoint.py#test_admin_gate_rejects_non_admin"
        status: pass
    human_judgment: false
  - id: D5
    description: "The endpoint creates a real RiskExposureBackfillJob row for the caller's tenant and writes exactly one risk_cutover.backfill_enqueue audit row"
    requirement: "RISK-07"
    verification:
      - kind: unit
        ref: "backend/tests/test_risk_backfill_enqueue_endpoint.py#test_enqueue_creates_job_and_audit_row"
        status: pass
    human_judgment: false
  - id: D6
    description: "A repeat call while a job is already pending/in_progress returns the SAME job (never a duplicate row) and does not add a second audit row"
    requirement: "RISK-07"
    verification:
      - kind: unit
        ref: "backend/tests/test_risk_backfill_enqueue_endpoint.py#test_enqueue_idempotent_when_already_active"
        status: pass
    human_judgment: false
  - id: D7
    description: "A repeat call against an already-completed job returns the existing completed job's status rather than re-enqueuing a fresh pending job"
    requirement: "RISK-07"
    verification:
      - kind: unit
        ref: "backend/tests/test_risk_backfill_enqueue_endpoint.py#test_enqueue_idempotent_when_completed"
        status: pass
    human_judgment: false

# Metrics
duration: 26min
completed: 2026-08-12
status: complete
---

# Phase 34 Plan 05: Gap Closure — RISK-08 Trend-Chart Flag-Gate + RISK-07 Backfill-Enqueue Admin Endpoint Summary

**Closed both gaps 34-VERIFICATION.md found (score 3.5/4): the trend chart's primary `avg_risk` series now genuinely branches on `Tenant.cutover_risk_exposure_scoring` (mirroring the already-verified `sort="triage"`/`get_top_findings_for_ai_batch` pattern), and a new admin-only `POST /api/v1/risk-cutover/backfill/enqueue` endpoint gives RISK-07's previously test-only-invoked backfill machinery a real production trigger.**

## Performance

- **Duration:** ~26 min
- **Started:** 2026-08-12T11:10:00+03:00 (verification + context read)
- **Completed:** 2026-08-12T11:50:23+03:00 (GAP 2 GREEN commit)
- **Tasks:** 4 completed (GAP 1 RED, GAP 1 GREEN, GAP 2 RED, GAP 2 GREEN)
- **Files modified:** 7 (2 created, 5 modified)

## Accomplishments

- **GAP 1 (RISK-08, blocker):** `get_risk_score_trend` (`app/vulnerabilities/trends.py`) now does a once-per-call scalar `Tenant.cutover_risk_exposure_scoring` fetch and branches its metric key: OFF reads `avg_risk_score` (byte-identical to pre-Phase-34 — no extra key), ON reads `avg_risk_exposure_score` instead, surfaced under the SAME `avg_risk` key name. `capture_daily_snapshot`'s RISK-10 dual-write remains completely unconditional — re-grepped post-fix, both flag references in the file live inside `get_risk_score_trend`, none inside `capture_daily_snapshot`.
- Rewrote `test_risk_boundary_guard.py::test_trend_no_cliff` (34-04's boundary-guard fixture), whose old assertions (`avg_risk_exposure` key present unconditionally regardless of flag) directly contradicted the corrected design. The updated test proves a stronger, more correct property: a tenant reading with the flag OFF sees the OLD series (including its own cliff, if any — expected for a tenant that hasn't cut over); a tenant reading with the flag ON sees the NEW series continuously across the same boundary, for its entire trend window (not just days after the flip), because RISK-10's dual-write already populated the new metric historically.
- New `test_risk_trend_cutover.py` (3 tests, all green): OFF-byte-identical (asserts the exact key set — no `avg_risk_exposure`), ON-surfaces-new-series, and an OFF-insulation test (a snapshot missing `avg_risk_exposure_score` entirely doesn't affect the OFF path's `avg_risk` value).
- **GAP 2 (RISK-07, operability):** New `POST /api/v1/risk-cutover/backfill/enqueue` admin endpoint (`require_role("admin")`) wraps `risk_backfill_service.enqueue_backfill_job` — already fully correct and fixture-proven, but previously reachable only from tests. `risk_cutover_service.enqueue_backfill` calls `audit()` before `db.commit()` (fail-closed, AUDIT-01) ONLY when the job is genuinely new (no existing row before the call); a repeat call while a job is pending/in_progress/completed returns the existing job's status unchanged — no duplicate row, no second audit entry.
- New `test_risk_backfill_enqueue_endpoint.py` (4 tests, all green): RBAC 403 for analyst/viewer (and confirms a rejected request creates zero job rows), create+audit-row assertion, idempotent-when-already-active, idempotent-when-completed.
- Full regression: 21/21 in the combined RISK-08/09/10/trend/dashboard window (`test_risk_cutover.py` + `test_risk_cutover_ack.py` + `test_risk_boundary_guard.py` + `test_risk_trend_cutover.py` + `test_risk_backfill_enqueue_endpoint.py`), 23/23 flag-OFF `test_vulnerabilities.py`/`test_sla_service.py`/`test_top_findings_for_ai_batch.py`, 8/8 `test_severity_trends.py`/`test_dashboard_tiles.py`. `ruff check`/`ruff format --check` clean on all touched files, 0 new mypy-baseline violations, single alembic head unchanged (`044_add_risk_backfill_job` — no new migration needed for either gap).

## Task Commits

Each task was committed atomically:

1. **Task 1: RED — GAP 1 trend-chart cutover fixture** - `359cca4` (test)
2. **Task 2: GREEN — flag-gate get_risk_score_trend's primary series + update test_trend_no_cliff** - `d61ddc6` (feat)
3. **Task 3: RED — GAP 2 backfill-enqueue admin endpoint fixture** - `9655aef` (test)
4. **Task 4: GREEN — admin backfill-enqueue endpoint + service + audit action** - `42177f1` (feat)

_No REFACTOR commit needed for either gap — GREEN required no post-implementation cleanup beyond the ruff-clean state already verified per-commit._

## Files Created/Modified

- `backend/app/vulnerabilities/trends.py` - `get_risk_score_trend` now does a scalar `Tenant.cutover_risk_exposure_scoring` fetch and branches the `avg_risk` metric key (`avg_risk_score` OFF / `avg_risk_exposure_score` ON); `capture_daily_snapshot` untouched
- `backend/app/vulnerabilities/risk_cutover_service.py` - new `enqueue_backfill(db, user)` — idempotent-aware wrapper around `risk_backfill_service.enqueue_backfill_job` with new-enqueue-only audit
- `backend/app/vulnerabilities/risk_cutover_router.py` - new `POST /backfill/enqueue` admin endpoint; module docstring updated to "four endpoints"
- `backend/app/audit.py` - `## Actions` comment block gains `risk_cutover.backfill_enqueue`
- `backend/tests/test_risk_trend_cutover.py` - new 3-test RISK-08 trend-chart fixture suite
- `backend/tests/test_risk_backfill_enqueue_endpoint.py` - new 4-test RISK-07 admin-endpoint fixture suite
- `backend/tests/test_risk_boundary_guard.py` - `test_trend_no_cliff` rewritten for the corrected flag-gated design; module docstring's step-3 description updated

## Decisions Made

1. **No extra `avg_risk_exposure` key on the ON path either** — the corrected design swaps what `avg_risk` itself reads from (mirroring service.py's primary-order-key swap literally), rather than keeping 34-04's additive-key shape and only gating one of two keys. This is the strictest reading of the verification's fix instruction and keeps the trend-chart consumer structurally identical in shape to the other two RISK-08 consumers.
2. **`capture_daily_snapshot` left completely untouched** — RISK-10's unconditional dual-write is a correctness requirement (trend continuity across a flip) independent of RISK-08's read-gating; conflating them would have been a regression.
3. **Rewrote (not just patched) `test_trend_no_cliff`** rather than deleting/weakening it — its old assertions were incompatible with the corrected design by construction, so the fix required proving the equivalent-but-correct property (continuity under the flag a tenant actually reads with) instead of silently dropping continuity coverage.
4. **Audit only a genuinely new enqueue** in `enqueue_backfill` — checked via `_backfill_status` returning `None` before calling the idempotent `enqueue_backfill_job`, so a repeated admin click against an active/completed job doesn't inflate the audit log with duplicate no-op rows while still auditing the one action that actually starts a tenant's backfill.
5. **Test-only fix, not a router/service bug:** the four new endpoint tests initially 500'd with a `ForeignKeyViolationError` because the HTTP client hits the app through a separate DB session (`app.db.session.async_session_factory`) from the test's own `db_session` fixture — `tenant_a`/`admin_user` fixtures only `flush()` (uncommitted) by default. Diagnosed via a live traceback repro (debug-mode app + direct ASGI call) before concluding it was a missing `db_session.commit()` in the new test file, mirroring `test_risk_cutover_ack.py`'s existing seeding pattern, not an application-code defect.

## Deviations from Plan

This is a gap-closure plan responding directly to `34-VERIFICATION.md`'s findings, not a plan-first execution — both "deviations" below are the gap-closure work itself, tracked here per the deviation-rules process since they weren't pre-specified as a PLAN.md:

### Auto-fixed Issues

**1. [Rule 1 - Bug] `test_risk_boundary_guard.py::test_trend_no_cliff` contradicted the corrected GAP 1 design**
- **Found during:** Task 2 (GAP 1 GREEN), running the full regression suite after the trends.py fix
- **Issue:** The pre-existing 34-04 test asserted `avg_risk_exposure` present unconditionally (regardless of the tenant's cutover flag) — a direct consequence of the OLD unconditional-dual-key design this gap closure corrects. Leaving it as-is would have either broken CI or required not closing the gap.
- **Fix:** Rewrote the test to assert the equivalent-but-corrected property: flag OFF reads the old series (including its own cliff); flag ON reads the new series continuously across the same boundary, for the tenant's entire window.
- **Files modified:** `backend/tests/test_risk_boundary_guard.py`
- **Verification:** `pytest tests/test_risk_boundary_guard.py` 5/5 green after the rewrite.
- **Committed in:** `d61ddc6` (GAP 1 GREEN commit)

**2. [Rule 3 - Blocking] New endpoint tests 500'd on a cross-session FK violation**
- **Found during:** Task 4 (GAP 2 GREEN), first test run of `test_risk_backfill_enqueue_endpoint.py`
- **Issue:** `client_factory`-based HTTP requests use the app's own separate DB session; `tenant_a`/`admin_user` fixtures only `flush()` by default (WR-13, documented in `conftest.py`), so those rows weren't visible cross-connection when the endpoint's own session tried to insert a `RiskExposureBackfillJob` referencing that `tenant_id`.
- **Fix:** Added explicit `await db_session.commit()` calls before the HTTP requests in the 3 affected tests, mirroring `test_risk_cutover_ack.py`'s existing seeding pattern.
- **Files modified:** `backend/tests/test_risk_backfill_enqueue_endpoint.py`
- **Verification:** Reproduced the exact traceback via a debug-mode ASGI call before fixing (confirmed `asyncpg.exceptions.ForeignKeyViolationError`, not an application bug); `pytest tests/test_risk_backfill_enqueue_endpoint.py` 4/4 green afterward.
- **Committed in:** `9655aef` (RED commit, since the fix was applied before the RED→GREEN transition was finalized for this file)

---

**Total deviations:** 2 auto-fixed (1 test-contradiction bug, 1 test-fixture cross-session gap)
**Impact on plan:** Both fixes are test-file-only with zero production-code impact beyond the two gap-closure changes themselves. No scope creep.

## Issues Encountered

None beyond the two auto-fixed items above.

## Verification Evidence

- `cd backend && ENCRYPTION_KEY=... JWT_SECRET_KEY=... .venv/bin/python -m pytest tests/test_risk_trend_cutover.py -v` → 3 passed.
- `pytest tests/test_risk_backfill_enqueue_endpoint.py -v` → 4 passed.
- `pytest tests/test_risk_boundary_guard.py tests/test_risk_trend_cutover.py tests/test_risk_cutover.py tests/test_severity_trends.py tests/test_dashboard_tiles.py -v` → 21 passed (combined regression window).
- `pytest tests/test_risk_cutover_ack.py tests/test_risk_backfill_enqueue_endpoint.py -v` → 12 passed (proves the new endpoint coexists cleanly with the existing risk-cutover router endpoints in the same file/module).
- Flag-OFF regression gate: `pytest tests/test_vulnerabilities.py tests/test_sla_service.py tests/test_top_findings_for_ai_batch.py -v` → 23 passed, unmodified, no live behavior change.
- GAP 1 write-path safety gate: `grep -n cutover_risk_exposure_scoring app/vulnerabilities/trends.py` → both matches (lines 173, 190) are inside `get_risk_score_trend` (166-217); zero matches inside `capture_daily_snapshot` (247+).
- Single alembic head unchanged: `alembic heads` → `044_add_risk_backfill_job (head)`.
- `mypy app/ | mypy-baseline filter --allow-unsynced` → 0 new violations (649 pre-existing, unchanged).
- `ruff check` + `ruff format --check` on all 7 touched files → clean.

## User Setup Required

None — no external service configuration required, no new migration. The new `POST /api/v1/risk-cutover/backfill/enqueue` endpoint exists and is fixture-tested but, consistent with 34-CONTEXT.md's locked decision, is not invoked against live tenant data in this environment — a human operator on a validated live stack is the intended caller.

## Next Phase Readiness

- Both gaps `34-VERIFICATION.md` flagged (GAP 1 blocker, GAP 2 operability) are closed. RISK-08 is flipped to Complete in `REQUIREMENTS.md`; ROADMAP.md's Phase 34 entry and traceability row are now internally consistent with REQUIREMENTS.md.
- Phase 34 is now 5/5 plans complete (34-01 through 34-05). Recommended next step: `/gsd-verify-phase 34` to re-verify against the closed gaps, then `/gsd-plan-phase 35`.
- No blockers for Phase 35 (Source-Aware Filtering & Provenance Badges) — this plan touched only `trends.py`, `risk_cutover_service.py`, `risk_cutover_router.py`, and `audit.py`, none of which Phase 35's scope (correlation-array filtering, `SourceBadgeGroup`) depends on.

---
*Phase: 34-historical-recompute-consumer-cutover*
*Completed: 2026-08-12*

## Self-Check: PASSED

All created/modified files verified present on disk (trends.py, risk_cutover_service.py, risk_cutover_router.py, audit.py, test_risk_trend_cutover.py, test_risk_backfill_enqueue_endpoint.py, test_risk_boundary_guard.py); all 4 task commit hashes (`359cca4`, `d61ddc6`, `9655aef`, `42177f1`) verified present in `git log`.
