---
phase: 39-exception-risk-acceptance-workflow
plan: 05
subsystem: api
tags: [fastapi, sqlalchemy, postgres, exceptions, risk-acceptance, compute-on-read, dashboards, export, risk-exposure]

# Dependency graph
requires:
  - phase: 39-01
    provides: active_exception_subquery(tenant_id, now) exclusion seam, reused verbatim by every consumer this plan touches
  - phase: 39-03
    provides: run_sla_tier_pass's D-15 exclusion, which stopped updating the persisted sla_due_at/sla_breached mirror for actively-excepted rows -- the prerequisite this plan's asset sla_breach badge fix depends on (read-time exclusion must agree with the now-frozen persisted mirror)
provides:
  - "Asset list/detail vuln-count/critical/high/exploitable/kev/sla_breach badges (assets/router.py) exclude actively-excepted findings"
  - "Owner-risk aggregate badges (users/router.py, both root list_users and /directory) exclude actively-excepted findings"
  - "/dashboard tiles (critical_open/sla_at_risk/kev), top-vuln spotlight, persistent nav vuln_open_count, and get_dashboard_stats' open_vulnerabilities all exclude actively-excepted findings"
  - "CSV remediations export + exec-summary export (export.py) exclude actively-excepted findings via a single shared open_filter list edit"
  - "Asset.risk_exposure_score MAX rollup (risk_exposure_service.py) excludes actively-excepted findings' scores -- the per-finding write loop remains untouched (an excepted finding still gets its own score written)"
  - "backend/tests/test_exceptions_dashboards.py -- 7 tests covering every surface above plus a Tier 3 non-regression guard (search.py still returns an excepted CVE)"
affects: [39-08-closing-plan]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Same compute-on-read exclusion (~active_exception_subquery(tenant_id, now)) applied verbatim across 6 new files -- identical 1-3 line WHERE addition per surface, matching Plan 04's consumer-sweep shape exactly"
    - "Shared predicate-list pattern (export.py's open_filter, spread via *open_filter into 5 count queries + the top-remediations query) means ONE exclusion edit propagates to every query that reuses the list -- no need to touch each query individually"

key-files:
  created:
    - backend/tests/test_exceptions_dashboards.py
  modified:
    - backend/app/assets/router.py
    - backend/app/users/router.py
    - backend/app/vulnerabilities/dashboard.py
    - backend/app/vulnerabilities/service.py
    - backend/app/export.py
    - backend/app/vulnerabilities/risk_exposure_service.py

key-decisions:
  - "Investigated and consciously excluded vulnerabilities/dashboard.py's `get_overview_stats` (its top_hosts_q vuln_count/critical/exploitable) from this plan's scope. The plan's own interfaces citation ('dashboard.py:43,189-208,311') traces to a stale grep hit inside get_overview_stats, not the three named functions (compute_dashboard_tiles_v10/compute_top_vuln_v10/compute_nav_counts_v10) -- confirmed via git log (dashboard.py's line count last shifted in Phase 33's severity-tier-centralization refactor, unrelated to Phase 39) and via a live grep showing service.py's own '750' citation is off by 16 lines for the same reason. get_overview_stats is also confirmed NOT frontend-consumed (no caller in frontend/src) and is separately covered by test_risk_tier_distribution.py for an unrelated concern (Asset.risk_score bucket boundaries, not vuln-count exclusion). Left untouched -- not named in must_haves, not user-facing, and PATTERNS.md itself flags this exact citation as 'not independently re-read this session.'"
  - "EXC-02 left unmarked [ ] in REQUIREMENTS.md despite being this plan's frontmatter requirement -- mirrors the 39-01/39-02/39-03 precedent (39-08 is the phase's last declaring plan for all four EXC-* IDs, confirmed via its depends_on:[39-03,39-05,39-06,39-07])."
  - "Split the single test file into two commits matching the two tasks: wrote a Task-1-only version (4 tests) first, committed it with the 4 Task-1 source files, then wrote back the full 7-test version and committed it with the 2 Task-2 source files -- preserves atomic per-task commits even though both tasks touch the same test file."
  - "test_excluded_from_dashboard_tiles_and_nav seeds a CRITICAL vulnerability with first_detected_at 10 days in the past (not just a hand-set sla_breached=True flag) because the client fixture's app lifespan starts the real background scheduler, which independently recomputes sla_breached on its own tick and would otherwise race a flag-only seed back to False before the assertion runs. Making the seed genuinely breached under the real 7-day critical SLA tier makes the test correct regardless of scheduler timing."

patterns-established: []  # No new patterns -- this plan is a pure application of Plan 04's established consumer-sweep shape to the remaining Tier 2 surfaces

requirements-completed: []  # EXC-02 spans all 8 plans in this phase; 39-08 is the last declaring plan (see key-decisions)

# Metrics
duration: 29min
completed: 2026-08-19
---

# Phase 39 Plan 05: Dashboards, Export & Risk-Exposure Rollup Consumer Sweep Summary

**Threaded the `active_exception_subquery` exclusion seam into 6 files (asset badges incl. sla_breach, owner-risk aggregates, dashboard tiles/top-vuln/nav, CSV/exec-summary export, and the risk_exposure_score MAX rollup) with a 7-test suite proving each exclusion plus a Tier 3 non-regression guard.**

## Performance

- **Duration:** 29 min
- **Started:** 2026-08-19T09:47:43Z
- **Completed:** 2026-08-19T10:16:31Z
- **Tasks:** 2/2
- **Files modified:** 7 (1 created, 6 modified)

## Accomplishments

- `assets/router.py`: both the asset list and asset detail vuln-count/critical/high/exploitable/kev/**sla_breach** badge queries now exclude actively-excepted findings -- the sla_breach fix specifically closes the loop with 39-03's `run_sla_tier_pass` change, which stopped updating the persisted `sla_due_at` mirror for excepted rows
- `users/router.py`: both owner-risk aggregate surfaces (the root Humaans-merged `list_users` AND the `/directory` endpoint) exclude actively-excepted findings from a person's total/critical/high/exploitable vuln counts
- `dashboard.py` + `service.py`: the `/dashboard` page's tiles (critical_open/sla_at_risk/kev), the top-vuln Hero spotlight, the persistent nav `vuln_open_count`, and `get_dashboard_stats`' `open_vulnerabilities` all exclude actively-excepted findings -- deliberately NOT applied to `mttr_30d`'s REMEDIATED-status query or to `total_vulnerabilities` (both are historical/raw-inventory counts outside the "active work" exclusion's scope)
- `export.py`: `export_remediations_csv` and `_collect_summary_data`'s shared `open_filter` list both exclude actively-excepted findings -- the shared-list edit means the exec summary's vuln counts AND its top-remediations breakdown pick up the fix from one line
- `risk_exposure_service.py`: the `Asset.risk_exposure_score` MAX rollup subquery excludes actively-excepted findings' scores, while the per-finding write loop (untouched) still scores every OPEN/IN_PROGRESS finding individually regardless of exception status -- proven by a test showing an excepted CRITICAL finding keeps its own score but no longer drives the asset-level MAX
- 7-test `backend/tests/test_exceptions_dashboards.py`: 4 tests for Task 1's surfaces, 3 for Task 2's (export/rollup/Tier-3-guard) -- the Tier 3 test proves `search.py` was NOT touched (an excepted CVE still surfaces in search results, D-01)
- Investigated and confirmed out-of-scope: `dashboard.py`'s legacy `get_overview_stats` (`/overview` endpoint) is unrouted from the frontend and not named in this plan's must_haves -- left untouched rather than over-applying the exclusion beyond what was asked

## Task Commits

Each task was committed atomically:

1. **Task 1: asset + owner + dashboard + nav badge/count exclusion** - `4d16e72` (feat)
2. **Task 2: export + risk_exposure_score rollup exclusion + Tier-3-untouched assertion** - `38a0443` (feat)

**Plan metadata:** _pending — this commit follows_

## Files Created/Modified

- `backend/app/assets/router.py` - list + detail vuln_q WHERE clauses gain `~active_exception_subquery(user.tenant_id, datetime.now(UTC))`
- `backend/app/users/router.py` - both owner-aggregate vuln_q WHERE clauses gain the same exclusion; new `datetime`/`active_exception_subquery` imports
- `backend/app/vulnerabilities/dashboard.py` - `compute_dashboard_tiles_v10`'s 3 "today" queries, `compute_top_vuln_v10`, and `compute_nav_counts_v10`'s `vuln_open` query all gain the exclusion
- `backend/app/vulnerabilities/service.py` - `get_dashboard_stats`' `open_q` (derived from `total_q`, not mutating `total_q` itself) gains the exclusion
- `backend/app/export.py` - `export_remediations_csv`'s WHERE and `_collect_summary_data`'s `open_filter` list both gain the exclusion
- `backend/app/vulnerabilities/risk_exposure_service.py` - `compute_finding_risk_scores`' `rollup_sub` subquery gains the exclusion; new `datetime`/`active_exception_subquery` imports
- `backend/tests/test_exceptions_dashboards.py` - 7 tests: 4 Task-1 (asset badges, asset sla_breach badge, owner aggregate, dashboard tiles/nav) + 3 Task-2 (export, risk_exposure rollup, Tier 3 search guard)

## Decisions Made

- `get_overview_stats` (dashboard.py's legacy `/overview` endpoint) was investigated and deliberately left unmodified -- see key-decisions in frontmatter for the full citation-drift root-cause (confirmed via git log + a live line-number cross-check against `service.py`'s equally-stale `:750` citation, and confirmed the endpoint has zero frontend callers).
- EXC-02 requirement checkbox intentionally left unmarked; 39-08 is this phase's last declaring plan for all four EXC-* IDs (mirrors 39-01/39-02/39-03 precedent).
- The test file was written in two passes (Task-1-only, then the full 7-test version) so each task's commit accurately reflects only that task's contribution to the shared file.
- `test_excluded_from_dashboard_tiles_and_nav` seeds a genuinely-10-day-stale finding rather than relying on a hand-set `sla_breached` flag, to avoid a race against the app's real background SLA scheduler (started by the `client` fixture's app lifespan).

## Deviations from Plan

None - plan executed exactly as written. Both tasks' action text, `<read_first>` line ranges (where still accurate against the current file state), and `<verify>` commands were followed literally; the one citation drift found (dashboard.py's "43") was investigated and resolved by following the task's own literal action text (which names the 3 functions unambiguously) rather than the imprecise line-number hint.

## Issues Encountered

- **mypy pre-existing drift (not fixed, confirmed unrelated):** `mypy app/ | mypy-baseline filter` shows 9 violations in `backend/app/ticketing/daily_sync.py` (untouched by this plan). Verified via `git stash` of all 6 of this plan's modified files that the identical 9 violations reproduce with zero of this plan's changes present -- the exact same pre-existing drift already documented by 39-01 and 39-03's summaries. Not fixed (out of scope, `daily_sync.py` is not in this plan's `files_modified`).
- **Full-suite regression (1123 passed, 1 known flake):** ran the complete backend suite (`pytest tests/`, 1124 tests) after both tasks; the only failure was `test_connector_health.py::test_scheduler_path_error_message_and_log_are_sanitized`, which passes cleanly in isolation (confirmed by re-running the file alone) -- this is the exact pre-existing, full-suite-only log-ordering flake already documented in 39-03's summary as unrelated to this phase's changes.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All Tier 2 consumer-sweep surfaces named in EXC-02's "dashboards" clause and the research emphasis "exports" are now wired to the shared exclusion seam; the Tier 3 grep gate (`search.py`/`connectors/sync.py`/`trends.py`) confirms zero over-application.
- 39-08 (the closing plan) can now proceed once 39-06 also completes -- its `depends_on:[39-03,39-05,39-06,39-07]` barrier has one remaining dependency.
- No blockers. Full backend regression suite (1124 tests) green except the one pre-existing, already-documented full-suite-only flake noted above.

## Self-Check: PASSED

- `backend/app/assets/router.py` — FOUND (contains `active_exception_subquery`)
- `backend/app/users/router.py` — FOUND (contains `active_exception_subquery`)
- `backend/app/vulnerabilities/dashboard.py` — FOUND (contains `active_exception_subquery`)
- `backend/app/vulnerabilities/service.py` — FOUND (open_q exclusion present)
- `backend/app/export.py` — FOUND (contains `active_exception_subquery`)
- `backend/app/vulnerabilities/risk_exposure_service.py` — FOUND (contains `active_exception_subquery`)
- `backend/tests/test_exceptions_dashboards.py` — FOUND (7 tests, all passing)
- Commit `4d16e72` — FOUND in git log
- Commit `38a0443` — FOUND in git log

---
*Phase: 39-exception-risk-acceptance-workflow*
*Completed: 2026-08-19*
