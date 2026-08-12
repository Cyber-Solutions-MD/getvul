---
phase: 34-historical-recompute-consumer-cutover
plan: 03
subsystem: api
tags: [fastapi, sqlalchemy, rbac, audit, risk-scoring, cutover]

# Dependency graph
requires:
  - phase: 34-historical-recompute-consumer-cutover (Plan 01)
    provides: "RiskExposureBackfillJob table + Tenant.cutover_risk_exposure_scoring / risk_cutover_threshold_ack_at / risk_cutover_threshold_ack_diff_hash columns (migration 044)"
provides:
  - "risk_cutover_service.py: compute_threshold_diff (backfill-gated pre/post min_risk_score diff report), record_threshold_ack (audited ack stamp+hash), enable_cutover (both-gates-enforced flag flip, admin-audited, never invoked live here)"
  - "3 admin endpoints under /api/v1/risk-cutover: GET /threshold-diff, POST /threshold-ack, POST /enable"
  - "2 new audit action strings: risk_cutover.threshold_ack, risk_cutover.flag_enable"
affects: [34-04-boundary-guards]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "diff_hash staleness gate: sha256 over sorted-JSON diff items, stamped on ack, re-checked on every enable — a threshold edit after acking silently invalidates the stored hash, forcing re-ack (no separate 'dirty' flag needed)"
    - "409 with a gate-specific string detail (backfill_incomplete / threshold_ack_missing / threshold_ack_stale) for business-rule gate failures on an admin mutation endpoint — first use of this response shape in the codebase (34-PATTERNS.md flagged as genuinely new, not a missing precedent)"

key-files:
  created:
    - backend/app/vulnerabilities/risk_cutover_service.py
    - backend/app/vulnerabilities/risk_cutover_router.py
    - backend/tests/test_risk_cutover_ack.py
  modified:
    - backend/app/main.py
    - backend/app/audit.py

key-decisions:
  - "diff_hash algorithm: hashlib.sha256(json.dumps(items, sort_keys=True, default=str)).hexdigest() over the diff's `items` list, itself sorted by (source_type, source_id) before hashing so the hash is stable across repeated calls regardless of the DB's row-return order (mirrors app/ai/cache.py::record_hash's sorted-JSON idiom)."
  - "409 detail strings are gate-specific, not a generic 'gate failed': backfill_incomplete (gate a), threshold_ack_missing (gate b, no ack recorded yet), threshold_ack_stale (gate b, ack recorded but diff_hash no longer matches — a threshold changed after acking). Distinguishing missing-vs-stale lets a future UI tell the admin exactly what to do next."
  - "compute_threshold_diff replicates rule_engine.py's exact `min_risk is not None and min_risk > 0` check for TicketRule.conditions and saved_filters.py's exact truthy `if filters.get('min_risk_score')` check for SavedFilter.filters — deliberately NOT unified into one check, to stay a faithful read-only mirror of each source file's own interpretation (in case they ever diverge)."
  - "enable_cutover re-checks compute_threshold_diff's readiness even though _backfill_status was already checked, and re-derives the current diff_hash rather than trusting a client-supplied value — the only source of truth for 'is the ack still fresh' is a server-side recomputation, never a request parameter."

patterns-established:
  - "Business-rule 409 with a string `detail` naming the specific failed gate — reusable for any future admin mutation endpoint with multiple preconditions."

requirements-completed: [RISK-09]

# Metrics
duration: 9min
completed: 2026-08-12
status: complete
---

# Phase 34 Plan 03: RISK-09 Threshold Diff + Ack + Gated Cutover Flip Summary

**Read-only pre/post `min_risk_score` diff report (old `Asset.risk_score` vs new `Asset.risk_exposure_score`) plus an audited per-tenant re-tuning acknowledgment that structurally gates the admin cutover flag flip — the flip cannot succeed without both a completed historical backfill AND a fresh (hash-matching) ack, and `rule_engine.py`/`saved_filters.py` are untouched.**

## Performance

- **Duration:** ~9 min
- **Started:** 2026-08-12T07:37:33Z (RED commit)
- **Completed:** 2026-08-12T07:46:40Z (final GREEN commit)
- **Tasks:** 3 completed (RED, service GREEN, router+wiring GREEN)
- **Files modified:** 5 (3 created, 2 modified)

## Accomplishments

- `risk_cutover_service.py` implements `compute_threshold_diff` (backfill-completion gated per Pitfall 3 — a missing or non-`completed` `RiskExposureBackfillJob` returns `{"ready": False, "reason": "backfill_incomplete"}`, never a misleading undercount), `record_threshold_ack` (stamps `risk_cutover_threshold_ack_at` + `risk_cutover_threshold_ack_diff_hash`, audited before commit), and `enable_cutover` (the only path that can set `Tenant.cutover_risk_exposure_scoring = True`, requiring both the backfill-complete gate and a fresh hash-matching ack, else a gate-specific 409).
- 3 new admin-only endpoints under `/api/v1/risk-cutover`: `GET /threshold-diff`, `POST /threshold-ack`, `POST /enable`, wired into `main.py` after the existing v1 includes.
- `audit.py`'s `## Actions` comment block documents the 2 new action strings (`risk_cutover.threshold_ack`, `risk_cutover.flag_enable`); both mutations call `audit()` before `db.commit()` (fail-closed, AUDIT-01).
- 8/8 RISK-09 fixture tests green: diff computation with hand-computed old/new match counts + a stable `diff_hash`, backfill-incomplete refusal (with and without a job row at all), ack stamp+hash, ack refused when backfill incomplete, stale-ack invalidation after a threshold change (409, flag stays False), both-gates flip requiring backfill-complete AND fresh ack (409/409/200 across the three states), and admin RBAC (403 for analyst/viewer on all three endpoints).
- `rule_engine.py` and `saved_filters.py` are confirmed untouched (`git diff --stat` empty for both) — RISK-09 remains a diff+ack artifact only, no live threshold retargeting (Pitfall 4).

## Task Commits

Each task was committed atomically:

1. **Task 1: RED — RISK-09 fixture suite** - `bae3930` (test)
2. **Task 2: GREEN part 1 — risk_cutover_service.py** - `e799982` (feat)
3. **Task 3: GREEN part 2 — admin router + main.py wire + audit actions** - `2c54629` (feat)

_No separate REFACTOR commit — the only post-RED changes were the router-file type annotations (fixed inline during Task 3's own mypy-baseline check, not a distinct cleanup pass) and one test-fixture arithmetic fix (also folded into the Task 3 commit, see Deviations)._

## Files Created/Modified

- `backend/app/vulnerabilities/risk_cutover_service.py` - `compute_threshold_diff`, `record_threshold_ack`, `enable_cutover`, `_diff_hash`, `_threshold_item`, `_backfill_status`
- `backend/app/vulnerabilities/risk_cutover_router.py` - 3 `require_role("admin")` endpoints, thin handler → service shape
- `backend/app/main.py` - import + `include_router(risk_cutover_router, prefix="/api/v1/risk-cutover", tags=["Risk Cutover"])`
- `backend/app/audit.py` - `## Actions` comment block extended with `risk_cutover.threshold_ack` / `risk_cutover.flag_enable`
- `backend/tests/test_risk_cutover_ack.py` - 8-test RISK-09 fixture suite

## Decisions Made

1. **diff_hash algorithm:** `hashlib.sha256(json.dumps(items, sort_keys=True, default=str)).hexdigest()` over the diff's `items` list. The `items` list is itself sorted by `(source_type, source_id)` before hashing (not just relying on `sort_keys=True`, which only sorts dict keys within each item, not the list order) so the hash is stable across repeated calls regardless of the order the DB happens to return `TicketRule`/`SavedFilter` rows in. Mirrors `app/ai/cache.py::record_hash`'s sorted-JSON idiom per the plan's interfaces block.
2. **409 detail strings, one per failed gate:** `backfill_incomplete` (gate a — the job isn't `completed`), `threshold_ack_missing` (gate b — no ack has ever been recorded), `threshold_ack_stale` (gate b — an ack exists but its stored `diff_hash` no longer matches the current diff, because a threshold changed after acking). Distinguishing "missing" from "stale" — rather than one generic `ack_gate_failed` — gives a future admin UI the exact next action (ack for the first time vs. re-ack after a change) without an extra round-trip.
3. **Faithful, non-unified replication of the two read sites:** `compute_threshold_diff` copies `rule_engine.py:65-67`'s `min_risk is not None and min_risk > 0` check for `TicketRule.conditions` and `saved_filters.py:104-105`'s truthy `if filters.get("min_risk_score")` check for `SavedFilter.filters` verbatim, rather than normalizing both to one shared predicate. If the two source files' own interpretations of "no threshold set" ever diverge (e.g. one starts treating `0` as meaningful), this reporting service keeps mirroring each one exactly instead of silently reconciling a difference that might be intentional.
4. **`enable_cutover` re-derives the diff server-side, never trusts a client value:** even though `_backfill_status` is already checked once, `enable_cutover` calls `compute_threshold_diff` again and compares its freshly-computed `diff_hash` against the tenant's stored `risk_cutover_threshold_ack_diff_hash` — the request itself carries no diff/hash parameter at all, closing off any path where a client could claim an ack is fresh when it isn't (T-34-10).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test-fixture arithmetic error in `test_threshold_diff_computation`**
- **Found during:** Task 3, first GREEN run
- **Issue:** The RED-phase test seeded asset `a3` with `risk_score=55`, which made the OLD `>= 50` match count 3 (a1, a2, a3) instead of the intended 2 — the test's own hand-computed expectation was wrong, not the implementation.
- **Fix:** Changed `a3`'s `risk_score` to `45` (still `>= 50` on the NEW `risk_exposure_score=55` side, preserving the intended old=2/new=3 delta for the filter threshold).
- **Files modified:** `backend/tests/test_risk_cutover_ack.py`
- **Verification:** All 8 tests green afterward.
- **Committed in:** `2c54629` (Task 3 commit)

**2. [Rule 3 - Blocking] mypy-baseline flagged 6 new `no-untyped-def` violations in the new router file**
- **Found during:** Task 3, running the project's `mypy | mypy-baseline filter --allow-unsynced` gate
- **Issue:** The router's 3 handlers used bare `user=Depends(...)` params and no return-type annotations — a pervasive pre-existing style elsewhere in the codebase, but flagged as NEW for a brand-new file (same class of issue Plan 01 hit with `risk_backfill_service.py`).
- **Fix:** Added `user: CurrentUser = Depends(require_role("admin"))` and `-> dict[str, Any]` return annotations to all 3 handlers.
- **Files modified:** `backend/app/vulnerabilities/risk_cutover_router.py`
- **Verification:** `mypy app/ | mypy-baseline filter --allow-unsynced` reports 0 new violations (649 pre-existing, unchanged); `ruff check` / `ruff format --check` clean.
- **Committed in:** `2c54629` (Task 3 commit)

---

**Total deviations:** 2 auto-fixed (1 test-fixture bug, 1 blocking lint gate)
**Impact on plan:** Neither touched the service's business logic — no scope creep, no files beyond those named in the plan.

## RISK-09 Machinery Detail (per plan's `<output>` spec)

- **diff_hash algorithm:** `hashlib.sha256(json.dumps(items, sort_keys=True, default=str).encode()).hexdigest()`, where `items` is pre-sorted by `(source_type, source_id)`.
- **409 detail strings:**
  - `"backfill_incomplete"` — `RiskExposureBackfillJob.status != "completed"` (or no job row at all).
  - `"threshold_ack_missing"` — backfill complete, but `risk_cutover_threshold_ack_at` is `None`.
  - `"threshold_ack_stale"` — an ack exists, but its `risk_cutover_threshold_ack_diff_hash` no longer matches the current diff's hash.
- **`rule_engine.py` / `saved_filters.py`:** confirmed untouched — `git diff --stat` for both files is empty.
- **Endpoint paths:** `GET /api/v1/risk-cutover/threshold-diff`, `POST /api/v1/risk-cutover/threshold-ack`, `POST /api/v1/risk-cutover/enable`. The `/enable` flip is fixture-tested only and is never called against live tenant data in this environment (34-CONTEXT.md, locked) — accepted debt for a human on a validated live stack, consistent with Phases 31/32/33's on-trust waivers.
- **Audit action strings added:** `risk_cutover.threshold_ack`, `risk_cutover.flag_enable` (both documented in `audit.py`'s `## Actions` comment block and asserted via audit-row queries in the test suite).

## User Setup Required

None — no external service configuration, no migration (this plan only adds application code reading Plan 01's already-landed schema).

## Next Phase Readiness

- Plan 04 (boundary guards, RISK-10) can proceed independently — it reads `Tenant.cutover_risk_exposure_scoring` (still default False) and the dual-write / spike-notification fix path, neither of which this plan touched.
- The full RISK-09 acceptance criterion (SC#3) is met: each tenant gets a pre/post diff, an explicit audited ack is required, and the flip is structurally impossible without backfill-complete + fresh-ack. No live threshold retarget occurred or will occur in this environment.
- No blockers for Plan 04.

---
*Phase: 34-historical-recompute-consumer-cutover*
*Completed: 2026-08-12*

## Self-Check: PASSED

All created files verified present on disk; all 3 task commit hashes (`bae3930`, `e799982`, `2c54629`) verified present in `git log`.
