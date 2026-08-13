---
phase: 30-correlation-schema-fix
plan: 02
subsystem: database
tags: [postgresql, sqlalchemy, pytest, correlation, idempotent-backfill, tdd]

# Dependency graph
requires:
  - phase: 30-correlation-schema-fix (plan 01)
    provides: "sources ARRAY(String)+GIN, source_vuln_ids JSONB, generalized correlation_service.py over the full VulnSource enum"
provides:
  - "backend/scripts/recorrelate_all_tenants.py — idempotent, manually-invoked per-tenant re-correlation with a testable `_recorrelate_tenant(db, tenant_id)` helper"
  - "Runtime-proven CORR-02 zero-loss recovery: the exact post-backfill bug signature (sources=[], sources_count=2) is corrected, not pruned, and the per-tenant COALESCE consistency query returns 0 afterwards"
  - "CORR-03 standing regression: sources_count == len(sources) proven across every 1-of-6 through 6-of-6 source combination, with D-08 confidence bands and D-02 canonical order"
  - "Cross-tenant isolation proof for correlation reads"
  - "D-09 HTTP response-shape proof: GET /{vuln_id}/correlation returns sources/sources_count/source_vuln_ids with zero legacy *_vuln_id keys"
affects: [31, 33, 35]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Standalone one-time data-recovery script with a testable helper + _main() entrypoint (mirrors capture_ai_goldens.py + scheduler.py's active-tenant loop + sla_service.py's idempotent per-tenant backfill shape)"
    - "COALESCE(array_length(sources,1),0) != sources_count as the permanent per-tenant zero-loss/count-invariant regression guard"

key-files:
  created:
    - backend/scripts/recorrelate_all_tenants.py
  modified:
    - backend/tests/test_correlation_service.py

key-decisions:
  - "sys.path manipulation (insert backend/ root) used in test_correlation_service.py to import `_recorrelate_tenant` from `scripts.recorrelate_all_tenants` since scripts/ has no __init__.py and sits as a sibling of app/ and tests/, not a package under app/ — implicit namespace package import resolves cleanly with zero new files"
  - "test_correlation_tenant_scoped's cve_id shortened from the plan's illustrative naming to CVE-2024-TSCOPE001 (18 chars) to fit Vulnerability.cve_id's String(20) column limit — a genuine, unplanned bug caught by a real StringDataRightTruncationError, not a stylistic choice"

requirements-completed: [CORR-01, CORR-02, CORR-03]

coverage:
  - id: D1
    description: "backend/scripts/recorrelate_all_tenants.py: idempotent, manually-invoked per-tenant re-correlation script with a testable _recorrelate_tenant(db, tenant_id) helper that _main() calls in its active-tenant loop; no compute_risk_scores call, no new route"
    requirement: "CORR-02"
    verification:
      - kind: other
        ref: "python -c \"import ast; ast.parse(open('backend/scripts/recorrelate_all_tenants.py').read())\" + grep -c COALESCE(array_length(sources,1), 0) == 1 + grep -c compute_risk_scores == 0"
        status: pass
    human_judgment: false
  - id: D2
    description: "Runtime zero-loss recovery: seeded the exact post-backfill bug signature (sources=[], sources_count=2 + the underlying Qualys+Rapid7 vulns), proved the COALESCE consistency query is non-zero pre-recovery, then proved _recorrelate_tenant corrects the row (sources==['QUALYS','RAPID7'], not pruned) and inconsistent_rows_after == 0"
    requirement: "CORR-02"
    verification:
      - kind: integration
        ref: "backend/tests/test_correlation_service.py#test_recorrelate_tenant_corrects_backfill_bug_signature"
        status: pass
    human_judgment: false
  - id: D3
    description: "sources_count == len(sources) proven across every 1-of-6 (no correlation) through 6-of-6 source combination, with D-08 confidence bands (HIGH>=4, MEDIUM 2-3) and D-02 canonical VulnSource-declaration order"
    requirement: "CORR-03"
    verification:
      - kind: integration
        ref: "backend/tests/test_correlation_service.py#test_single_source_does_not_correlate, #test_confidence_bands[2-MEDIUM,3-MEDIUM,4-HIGH,5-HIGH,6-HIGH]"
        status: pass
    human_judgment: false
  - id: D4
    description: "Cross-tenant isolation: a correlation created for tenant_a is never returned for tenant_b"
    verification:
      - kind: integration
        ref: "backend/tests/test_correlation_service.py#test_correlation_tenant_scoped"
        status: pass
    human_judgment: false
  - id: D5
    description: "D-09 HTTP response shape: GET /{vuln_id}/correlation returns sources/sources_count/source_vuln_ids and none of the 4 legacy *_vuln_id keys, under require_viewer auth"
    requirement: "CORR-01"
    verification:
      - kind: integration
        ref: "backend/tests/test_correlation_service.py#test_correlation_route_returns_d09_shape"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-08-05
status: complete
---

# Phase 30 Plan 02: Correlation Schema Fix — Re-correlation Data Recovery + Coverage Summary

**Idempotent per-tenant re-correlation script (`_recorrelate_tenant`) that runtime-proves CORR-02 zero-loss recovery of the previously-silently-dropped Qualys/Rapid7 correlations, plus a 10-test suite locking CORR-03's count/name invariant, D-08 confidence bands, cross-tenant isolation, and the D-09 HTTP contract as standing regressions.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-08-05T08:05:00Z
- **Completed:** 2026-08-05T08:09:21Z
- **Tasks:** 3 (script + testable helper; RED→GREEN runtime recovery test; RED→GREEN combinatorial/tenant/HTTP coverage)
- **Files modified:** 2 (1 new, 1 modified)

## Accomplishments

- `backend/scripts/recorrelate_all_tenants.py` (NEW): a standalone, manually-invoked, idempotent script mirroring `capture_ai_goldens.py`'s docstring/entrypoint convention, `scheduler.py`'s active-tenant loop, and `sla_service.backfill_sla_due_dates`'s idempotent-per-tenant-fn shape. Its core is `async def _recorrelate_tenant(db, tenant_id) -> dict`: a diagnostic "before" blind-spot count (`sources = '{}'`), a call to the already-idempotent `run_correlations(db, tenant_id)`, and the per-tenant `COALESCE(array_length(sources,1),0) != sources_count` zero-loss check — every query scoped by `tenant_id`, never a bare global aggregate (T-30-05). The helper takes an injected session and never commits, so a test can drive it with the `db_session` fixture; `_main()` loops active tenants (`Tenant.is_active.is_(True)`) with per-tenant try/except-continue (one tenant's failure never aborts the rest) and commits once after the loop. No `compute_risk_scores` call, no new API route (D-07).
- `test_correlation_service.py` expanded from 1 test (Plan 01's SC#4) to 10 tests: `test_recorrelate_tenant_corrects_backfill_bug_signature` seeds the *exact* post-backfill bug signature (a `VulnerabilityCorrelation` row with `sources=[]`, `sources_count=2`, plus the real underlying Qualys+Rapid7 vulns) directly via the model, proves the COALESCE consistency query is genuinely non-zero *before* recovery, then proves `_recorrelate_tenant` corrects the row (not prunes it) and drives `inconsistent_rows_after` to 0 — closing the static-only verification gap Plan 01 left open.
- `test_single_source_does_not_correlate` locks the 1-source edge (no correlation row created); `test_confidence_bands` is parametrized over every 2..6-source combination (drawn from `VulnSource` declaration order), asserting `len(sources) == sources_count` (CORR-03), canonical order (D-02), and the D-08 bands (`HIGH>=4`, `MEDIUM 2-3`) simultaneously; `test_correlation_tenant_scoped` proves a tenant_a correlation is invisible under tenant_b; `test_correlation_route_returns_d09_shape` exercises the real `GET /{vuln_id}/correlation` route through the authed `client` fixture and asserts the body contains `sources`/`sources_count`/`source_vuln_ids` and none of the 4 legacy `*_vuln_id` keys.
- CORR-01/CORR-02/CORR-03 are now all satisfied by the combination of Plan 01 (schema + service rewrite) and this plan (runtime recovery proof + combinatorial/tenant/API-contract coverage) — the shared-ID gate from Plan 01's summary resolves here.

## Task Commits

Each task was committed atomically:

1. **Task 1: One-time per-tenant re-correlation script with a testable helper** — `d10bc99` (feat)
2. **Task 2: Runtime re-correlation recovery + per-tenant zero-loss integration test** — `21247ce` (test)
3. **Task 3: Confidence-banding, count-invariant, cross-tenant, and D-09 HTTP-shape coverage** — `1e820d4` (test)

**Plan metadata:** *(this commit)*

## Files Created/Modified

- `backend/scripts/recorrelate_all_tenants.py` (NEW) — idempotent per-tenant re-correlation script; `_recorrelate_tenant(db, tenant_id)` helper + `_main()` entrypoint
- `backend/tests/test_correlation_service.py` — expanded from 1 test (Plan 01's SC#4) to 10 tests covering runtime zero-loss recovery, the 1-source edge, D-08 confidence bands (parametrized 2..6), cross-tenant isolation, and the D-09 HTTP response shape

## Decisions Made

- `scripts/` has no `__init__.py` and is not a package under `app/` — the test file adds `backend/`'s root to `sys.path` (implicit namespace package resolution) to import `_recorrelate_tenant` from `scripts.recorrelate_all_tenants`, rather than adding an `__init__.py` (which would be an unnecessary structural change for a one-off test import) or duplicating the helper's logic inline in the test file.
- `test_correlation_tenant_scoped`'s `cve_id` was shortened to `CVE-2024-TSCOPE001` (18 chars) after a real `StringDataRightTruncationError` against `Vulnerability.cve_id`'s `String(20)` column — the plan's own illustrative test names weren't length-checked against the schema; this is a genuine bug caught during execution, not a style preference.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Shortened an over-length cve_id fixture value**
- **Found during:** Task 3, first full-suite run
- **Issue:** `test_correlation_tenant_scoped` seeded `cve_id = "CVE-2024-TENANTSCOPE001"` (23 characters), exceeding `Vulnerability.cve_id`'s `String(20)` column limit — the INSERT failed with `sqlalchemy.exc.DBAPIError: ... StringDataRightTruncationError: value too long for type character varying(20)`.
- **Fix:** Shortened the fixture's `cve_id` to `"CVE-2024-TSCOPE001"` (18 chars, well under the limit). No production code touched — this is a test-fixture-only fix.
- **Files modified:** `backend/tests/test_correlation_service.py`
- **Verification:** Full suite re-run green (10/10 passed) after the fix.
- **Committed in:** `1e820d4` (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 bug, test-fixture-only, zero production-code impact)
**Impact on plan:** No scope creep — the fix is a one-line test-data length correction caught by a genuine database constraint violation, not a design change.

## Issues Encountered

- **Confirmed pre-existing mypy `note`-line nondeterminism, re-encountered and re-confirmed (not this plan's regression).** `mypy app/ | mypy-baseline filter --allow-unsynced` (CI's exact gate command) reported `fixed=3/new=3` (the same `app/auth/dependencies.py:10` jose-stub-missing hint nondeterministically attaching to a different importing file each run) — byte-identical to the flake already documented in 30-01-SUMMARY.md's "Issues Encountered" and the project's Phase 29 precedent. This plan's actual production-code footprint is zero files under `app/` (only `backend/scripts/` and `backend/tests/`, neither covered by the `mypy app/` CI command), so the flake is unambiguously unrelated to this plan's changes — confirmed by re-running mypy twice with `.mypy_cache` cleared, settling at the identical 3/3 both times. Not fixed (pre-existing, out of scope, already tracked in `deferred-items.md` from Plan 01).
- `scripts/recorrelate_all_tenants.py` needed a `ruff format` pass after the initial `Write` (three raw-SQL `text(...)` calls exceeded the line-length wrap the formatter prefers) — auto-formatted, re-verified the grep-based acceptance criteria (`COALESCE(array_length(sources,1), 0)` count and `compute_risk_scores` absence) still held post-format, and re-ran the full test suite to confirm nothing broke.

## User Setup Required

None — no external service configuration required. The script itself (`docker compose exec backend python scripts/recorrelate_all_tenants.py`) is a manually-invoked, one-time operator step per its own docstring, but that invocation is an operational task for the eventual production deploy, not a "user setup" blocking this plan's completion — the dev Postgres this plan verified against had zero rows in `vulnerability_correlations` needing real recovery (confirmed via Plan 01's own note on the same environment), so the script's correctness is proven entirely by the runtime test (`test_recorrelate_tenant_corrects_backfill_bug_signature`), not by a live production run.

## Next Phase Readiness

- **Phase 30 is now 2/2 plans complete.** CORR-01/CORR-02/CORR-03 are all satisfied: schema + service generalization (Plan 01) + runtime zero-loss recovery proof + combinatorial/tenant/API-contract coverage (this plan).
- **REQUIREMENTS.md:** CORR-01/CORR-02/CORR-03 should now flip from `[ ]` Pending to `[x]` Complete — this is the last declaring plan for the shared-ID gate Plan 01's summary flagged.
- **ROADMAP.md:** Phase 30's plan-progress row updates to 2/2; phase-level completion/verification is deferred to `/gsd-verify-work 30` per the orchestrator's job, not this executor's.
- Ready for Phase 31 (Connector Enrichment Rewrite) — no blockers. Phase 33 (Risk-Exposure Model) can now safely consume the corrected, complete `sources`/`sources_count` cross-scanner corroboration signal once Phases 31/32 also land.
- No auth gates, no user setup pending.

## Self-Check: PASSED

- FOUND: `backend/scripts/recorrelate_all_tenants.py`
- FOUND: `backend/tests/test_correlation_service.py` (10 tests, up from 1)
- FOUND commit: `d10bc99` (Task 1 — script)
- FOUND commit: `21247ce` (Task 2 — runtime recovery test)
- FOUND commit: `1e820d4` (Task 3 — combinatorial/tenant/HTTP coverage)
- Re-ran plan-level `<verification>`: `python -c "import ast; ast.parse(open('backend/scripts/recorrelate_all_tenants.py').read())"` → OK; `grep -c compute_risk_scores backend/scripts/recorrelate_all_tenants.py` → 0; `cd backend && pytest tests/test_correlation_service.py -v` → **10 passed**. All acceptance criteria for Tasks 1-3 re-verified PASS.

---
*Phase: 30-correlation-schema-fix*
*Plan: 02*
*Completed: 2026-08-05*
