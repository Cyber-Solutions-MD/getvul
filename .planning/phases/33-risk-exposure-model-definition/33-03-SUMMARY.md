---
phase: 33-risk-exposure-model-definition
plan: 03
subsystem: api
tags: [sqlalchemy, fastapi, alembic, scoring, risk-model, refactor]

# Dependency graph
requires:
  - phase: 33-risk-exposure-model-definition
    plan: 01
    provides: "score_finding tracer, FindingScoreInputs/RiskBreakdown dataclasses, compute_finding_risk_scores DB-orchestration, persisted-column response fields, migration 042 (5 nullable columns)"
  - phase: 33-risk-exposure-model-definition
    plan: 02
    provides: "score_finding FULL 6-category formula (severity/CVSS + EPSS + native-exploitability + exposure + corroboration + KEV floor), real per-source normalization, real correlation-driven sources_count"
provides:
  - "Asset.risk_exposure_score = MAX(risk_exposure_score) across an asset's OPEN/IN_PROGRESS findings, computed by a single bulk subquery + outerjoin inside compute_finding_risk_scores; resets to NULL (not stale) when an asset has zero open findings"
  - "Migration 043_index_risk_exposure_score: btree index on vulnerabilities.risk_exposure_score — sortability substrate, zero app-query consumer this phase"
  - "RISK_SCORE_TIER_CRITICAL/HIGH/MEDIUM (80/50/20) centralized in app/assets/risk_score.py, imported by dashboard.py/export.py/assets/router.py, replacing the byte-identical triplicated literals"
  - "test_risk_tier_distribution.py: characterization regression proving byte-identical bucket counts across all 3 sites before/after the centralization refactor"
affects: [33-04-drillpanel-shadow-preview, 33-05-drillpanel-breakdown-ui, phase-34-cutover]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Rollup-via-bulk-subquery-outerjoin: identical shape to risk_score.py's own compute_risk_scores, applied to a MAX aggregate instead of a SUM — assets with no matching rows outerjoin to NULL, explicitly written back (not skipped) so a prior stale value is cleared"
    - "Named-constant substitution refactor: literal->constant swap verified zero-behavior-change via a characterization test asserting exact output equality, not just 'still returns 200'"

key-files:
  created:
    - backend/alembic/versions/043_index_risk_exposure_score.py
    - backend/tests/test_risk_tier_distribution.py
  modified:
    - backend/app/vulnerabilities/risk_exposure_service.py
    - backend/app/assets/models.py
    - backend/app/assets/risk_score.py
    - backend/app/vulnerabilities/dashboard.py
    - backend/app/export.py
    - backend/app/assets/router.py
    - backend/tests/test_risk_exposure_service.py

key-decisions:
  - "Asset MAX-rollup test asserts against the ACTUAL persisted per-finding scores (max() over the two seeded findings' real risk_exposure_score), not hardcoded numbers — more robust than pinning exact formula output, and still proves a genuine MAX (one finding is asserted >= 90 via the KEV floor, guaranteeing the two scores are meaningfully different, not a coincidental tie)."
  - "Empty-asset reset test seeds a stale prior value (Asset.risk_exposure_score=77, risk_model_version='v0-stale') before running compute — proving the rollup actively RESETS rather than merely 'never sets', which a naive 'only update assets with open findings' implementation would fail."
  - "assets/router.py's low-bucket has no `| is_(None)` clause (unlike dashboard.py/export.py) — a genuine PRE-EXISTING discrepancy across the 3 'byte-identical' sites, confirmed by direct read. The characterization test intentionally asserts DIFFERENT expected counts for assets/router.py (low=1) vs. the other two (low=2) at the same boundary-value seed, documenting rather than silently fixing this asymmetry — Task 3's scope is literal->constant substitution only, zero behavior change, not bug-fixing a pre-existing inconsistency."
  - "Chose to call dashboard.py's get_overview_stats and export.py's _collect_summary_data directly (as plain async functions) in the characterization test rather than routing through HTTP, since neither is itself a FastAPI route (they're internal service functions invoked by other routes) — only assets/router.py's asset_stats is hit via the `client` HTTP fixture since it IS the route (GET /api/v1/assets/stats)."

requirements-completed: [RISK-02, RISK-06]

coverage:
  - id: D1
    description: "Asset.risk_exposure_score rolls up to the MAX of its OPEN/IN_PROGRESS findings (not a volume curve); resets to NULL when an asset has no open findings; Asset.risk_model_version stamped alongside"
    requirement: "RISK-02"
    verification:
      - kind: integration
        ref: "backend/tests/test_risk_exposure_service.py#test_asset_rollup_is_max"
        status: pass
      - kind: integration
        ref: "backend/tests/test_risk_exposure_service.py#test_asset_rollup_empty_resets"
        status: pass
    human_judgment: false
  - id: D2
    description: "Vulnerability.risk_exposure_score carries a btree index (migration 043) making the column efficiently sortable, with zero automated consumer wired this phase"
    requirement: "RISK-02"
    verification:
      - kind: other
        ref: "alembic heads (single head 043_index_risk_exposure_score) + grep -rn risk_exposure_score backend/app --include=*.py | grep -v risk_exposure_service.py (only models.py/schemas.py/service.py display-read matches)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Severity-tier boundaries (>=80/>=50/>=20) centralized into RISK_SCORE_TIER_CRITICAL/HIGH/MEDIUM in risk_score.py, imported by dashboard.py/export.py/assets/router.py, zero behavior change"
    requirement: "RISK-06"
    verification:
      - kind: integration
        ref: "backend/tests/test_risk_tier_distribution.py#test_risk_distribution_buckets_unchanged"
        status: pass
      - kind: other
        ref: "grep -rn 'Asset.risk_score >= 80|>= 50|>= 20' backend/app (zero matches)"
        status: pass
    human_judgment: false

# Metrics
duration: 9min
completed: 2026-08-11
status: complete
---

# Phase 33 Plan 03: Asset MAX Rollup + Severity-Tier Centralization Summary

**`compute_finding_risk_scores` now rolls each asset's `Asset.risk_exposure_score` up to the MAX of its open findings (resetting to NULL when none remain), `Vulnerability.risk_exposure_score` carries a passive sortability index (migration 043), and the `>=80/>=50/>=20` severity-tier boundary — previously hand-synced across 3 files — collapses into one named-constant set, proven zero-behavior-change by a characterization regression.**

## Performance

- **Duration:** ~9 min
- **Started:** 2026-08-11T15:03:41+03:00 (Task 1 commit)
- **Completed:** 2026-08-11T15:12:21+03:00 (Task 3 commit)
- **Tasks:** 3/3
- **Files modified:** 7 (2 new, 5 edited)

## Accomplishments

- `compute_finding_risk_scores` gains a single bulk `MAX(risk_exposure_score)` subquery grouped by `asset_id`, outer-joined to every tenant `Asset` so an asset with zero OPEN/IN_PROGRESS findings resets to `NULL` — never a stale carryover from a prior compute cycle. `Asset.risk_model_version` is stamped on every touched asset. No per-row lookup; the rollup is one additional query per tenant-wide recompute, mirroring `risk_score.py`'s own bulk-subquery shape.
- Migration `043_index_risk_exposure_score` (29 chars, chains `042 -> 043`) adds a btree index on `vulnerabilities.risk_exposure_score` — purely passive infrastructure. Confirmed via `alembic heads` (single head) and a grep sweep that no app query references the column outside `risk_exposure_service.py`'s own write path and the display-only read sites (`models.py`, `schemas.py`, `service.py`) — the RISK-06 zero-consumer gate remains intact.
- `RISK_SCORE_TIER_CRITICAL=80` / `RISK_SCORE_TIER_HIGH=50` / `RISK_SCORE_TIER_MEDIUM=20` now live once in `app/assets/risk_score.py` (next to `SEVERITY_WEIGHTS`) and are imported by `dashboard.py`, `export.py`, and `assets/router.py`, replacing the byte-identical raw literals at each site. Zero raw tier literals remain in `backend/app` (grep-verified).
- New `test_risk_tier_distribution.py` seeds 8 assets at the exact tier boundaries (`{85, 80, 79, 50, 49, 20, 19, None}`) and asserts the bucket counts returned by all 3 sites — this test passed BEFORE the centralization refactor (baseline/golden) and passes IDENTICALLY AFTER (Task 3), proving the refactor changed zero behavior.
- Discovered and documented a genuine pre-existing discrepancy: `assets/router.py`'s low-bucket filter (`Asset.risk_score < 20`) does NOT include an `| is_(None)` clause, unlike `dashboard.py`/`export.py` — so a `NULL`-scored asset is silently excluded from every bucket at that one site. This is NOT something Task 3 fixes (out of the pure-refactor scope; the interfaces block explicitly says "keep verbatim") — it's called out in the characterization test's own comments and in this summary for a future phase to decide on.
- `test_asset_rollup_is_max` / `test_asset_rollup_empty_resets` added to `test_risk_exposure_service.py` (RED against Plan 33-02's tracer, GREEN after Task 2) — 12/12 tests in that file pass.

## Task Commits

Each task was committed atomically (TDD: RED → GREEN, then a pure refactor):

1. **Task 1: RED (rollup) + characterization baseline (tier buckets)** - `cdf8746` (test)
2. **Task 2: GREEN — asset MAX rollup + index migration 043** - `c7dccdf` (feat)
3. **Task 3: Severity-tier centralization (constants + 3 call sites)** - `b6432fb` (refactor)

**Plan metadata:** (this commit)

## Files Created/Modified

- `backend/alembic/versions/043_index_risk_exposure_score.py` (new) - btree index on `vulnerabilities.risk_exposure_score`, chains from 042.
- `backend/tests/test_risk_tier_distribution.py` (new) - characterization regression: golden bucket counts at boundary values, asserted across all 3 tier-boundary sites.
- `backend/app/vulnerabilities/risk_exposure_service.py` - added the MAX rollup query + write-back after the per-finding update loop; updated module + function docstrings; `assets_rolled_up` added to the stats dict.
- `backend/app/assets/models.py` - updated the `Asset.risk_exposure_score` doc-comment (was stale after this plan populates the rollup).
- `backend/app/assets/risk_score.py` - added `RISK_SCORE_TIER_CRITICAL/HIGH/MEDIUM` constants.
- `backend/app/vulnerabilities/dashboard.py` - `get_overview_stats`'s risk-distribution query now imports and uses the 3 named constants.
- `backend/app/export.py` - `_collect_summary_data`'s risk-distribution query now imports and uses the 3 named constants.
- `backend/app/assets/router.py` - `asset_stats`'s risk-distribution query now imports and uses the 3 named constants.
- `backend/tests/test_risk_exposure_service.py` - added `test_asset_rollup_is_max` + `test_asset_rollup_empty_resets`.

## Decisions Made

See `key-decisions` in frontmatter for the full list. The one substantive judgment call: rather than silently "fixing" the `assets/router.py` low-bucket's missing `| is_(None)` clause to match the other two sites (which would be a behavior change outside Task 3's explicit pure-refactor scope), the characterization test documents the asymmetry as expected, current behavior — a future phase can decide whether to unify it.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test fixture cve_id values exceeded the 20-char column limit**
- **Found during:** Task 1 RED verification (first test run of the new rollup tests)
- **Issue:** `Vulnerability.cve_id` is `String(20)`; the initially-written fixture IDs (`"CVE-2024-ROLLUP-LOW"`, `"CVE-2024-ROLLUP-HIGH"`, `"CVE-2024-ROLLUP-CLOSED"`) — 19/20/22 characters — caused a `StringDataRightTruncationError` on the 22-char one, and would have been fragile at 19-20 for any future rename.
- **Fix:** Shortened to numbered IDs (`"CVE-2024-9001"`, `"CVE-2024-9002"`, `"CVE-2024-9003"`), well under the 20-char limit.
- **Files modified:** `backend/tests/test_risk_exposure_service.py`
- **Verification:** Both rollup tests confirmed RED for the real reason (assertion failure on `risk_exposure_score`, not a DB insert error) before Task 2's implementation.
- **Committed in:** `cdf8746` (Task 1 RED commit — fixed before the RED commit landed, so this is not visible as a separate diff)

---

**Total deviations:** 1 auto-fixed (1 bug — test-fixture column-length mismatch, not a scoring or rollup bug)
**Impact on plan:** No scope creep, no production behavior change.

## Issues Encountered

None beyond the fixture-length deviation above.

## User Setup Required

None. Migration 043 is additive-only (a single index); no environment configuration changes.

## Next Phase Readiness

- RISK-02's MAX rollup and sortability index, and RISK-06's centralization, are both complete — Phase 33's remaining plans (33-04/33-05, DrillPanel shadow/preview UI) can build on a stable, fully-populated `Asset.risk_exposure_score` and a single source of truth for the tier boundaries.
- Zero-consumer gate re-confirmed unchanged: `grep -rn "risk_exposure_score|risk_exposure_breakdown" backend/app --include="*.py" | grep -v risk_exposure_service.py` → only `models.py`/`schemas.py`/`service.py` (display-only reads).
- `alembic heads` resolves to a single head (`043_index_risk_exposure_score`); no branching migration state for Phase 34 to resolve.
- Flagged for a future phase: the `assets/router.py` low-bucket's missing `| is_(None)` clause (documented above) — worth a deliberate fix + regression update if/when that endpoint's exact semantics matter, but explicitly out of this plan's zero-behavior-change scope.
- No blockers.

---
*Phase: 33-risk-exposure-model-definition*
*Completed: 2026-08-11*

## Self-Check: PASSED

All 4 key files found on disk (`043_index_risk_exposure_score.py`, `test_risk_tier_distribution.py`, `risk_exposure_service.py`, `risk_score.py`) plus this SUMMARY.md. All 3 task commit hashes (`cdf8746`, `c7dccdf`, `b6432fb`) found in `git log`.
