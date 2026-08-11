---
phase: 33-risk-exposure-model-definition
plan: 02
subsystem: api
tags: [fastapi, sqlalchemy, scoring, risk-model, normalization]

# Dependency graph
requires:
  - phase: 33-risk-exposure-model-definition
    plan: 01
    provides: "score_finding tracer (severity/CVSS + EPSS + KEV floor real), FindingScoreInputs/RiskBreakdown dataclasses, compute_finding_risk_scores DB-orchestration, single sync-hook wire, persisted-column response fields"
  - phase: 30-cross-scanner-correlation
    provides: VulnerabilityCorrelation.sources_count (now consumed for real)
  - phase: 32-asset-exposure-context
    provides: Asset.business_criticality/data_sensitivity/internet_facing (now consumed for real)
provides:
  - "score_finding: FULL 6-category deterministic formula (severity/CVSS 35 + EPSS 20 + native-exploitability 15 + exposure 20 + corroboration 10, KEV floor via max())"
  - "_normalize_native_signal: per-source 0-1 normalization with soft-null, never raises"
  - "compute_finding_risk_scores: single bulk VulnerabilityCorrelation select (no N+1), feeds real sources_count"
  - "kev_floor breakdown component row emitted when the floor actually changes the outcome"
affects: [33-03-asset-rollup-tier-centralization, 33-05-drillpanel-breakdown-ui, phase-34-cutover]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-source normalization dispatch table with a single try/except soft-null wrapper (mirrors connectors' own defensive idiom)"
    - "Capped linear fraction for corroboration: min((n-1)/3, 1.0) — 1 source contributes 0, 4+ sources contribute the full budget"
    - "Conditional breakdown row (kev_floor) appended only when it changes the reported outcome, not unconditionally"

key-files:
  created: []
  modified:
    - backend/app/vulnerabilities/risk_exposure_service.py
    - backend/tests/test_risk_exposure_service.py

key-decisions:
  - "CrowdStrike native signal uses ONLY native_priority_rating (categorical, confirmed field) — its numeric native_priority_score (exprt_score) is never touched, per CONTEXT lock and Phase 31's own flagged unverified-field risk"
  - "Exposure emitted as 3 separate breakdown rows (exposure_business_criticality/exposure_internet_facing/exposure_data_sensitivity), not one combined row — matches the shape Plan 01 already reserved"
  - "corroboration test fixture asserts on the underlying breakdown component's exact point delta (6.67, pre-rounding) rather than the rounded int final_score delta — the RESEARCH-verbatim base fixture (HIGH/cvss 7.5/QUALYS native 60/MEDIUM/INTERNAL) produces two independently-rounded subtotals (41.87→42, 48.54→49) that land 7 apart, not 6.7; this is a real int-rounding boundary artifact of the final_score type (int), not a formula bug — the component-level assertion is the precise, deterministic RISK-04 proof, the final_score assertion (>= 6 pts higher) proves direction/magnitude at the reported-score level"
  - "kev_floor row uses max_points=0.0 by design (per interfaces block) even though its points can be positive when the floor actually raises the score — this is intentionally a display-only annotation row, not a scored input, so it is excluded from the 'points <= max_points' invariant check in test_score_finding_all_components (that test's fixture has cisa_kev=False, so no kev_floor row is present there)"

requirements-completed: [RISK-01, RISK-03, RISK-04]

# Metrics
duration: 32min
completed: 2026-08-11
---

# Phase 33 Plan 02: Risk-Exposure Model Definition — Full Formula Expansion Summary

**`score_finding` now computes the complete 6-category, 100-point deterministic formula — per-source native-exploitability normalization (Nessus/Qualys/Rapid7 numeric scales + CrowdStrike categorical, soft-null everywhere else), the full Phase 32 exposure sub-split, and Phase 30 cross-scanner corroboration — with `compute_finding_risk_scores` now bulk-fetching real `sources_count` in a single tenant-scoped query (no N+1), and the KEV floor emitting an explicit breakdown row when it actually changes the outcome.**

## Performance

- **Duration:** ~32 min
- **Started:** 2026-08-11T13:28:58+03:00 (Task 1 commit)
- **Completed:** 2026-08-11T14:00:27+03:00 (Task 2 commit)
- **Tasks:** 2/2
- **Files modified:** 2

## Accomplishments

- `_normalize_native_signal(source, score, rating)` lands the highest-risk task in the phase: each of 6 connectors' incompatible native-priority scales normalized to a common 0.0-1.0 fraction — NESSUS VPR (÷10), QUALYS QDS (÷100), RAPID7 Risk Score (÷1000), CROWDSTRIKE via its confirmed categorical `native_priority_rating` (never the unverified numeric `exprt_score`), DEFENDER/WIZ/missing/garbage/out-of-range soft-null to 0.0 — the function is wrapped in `try/except (TypeError, ValueError)` and provably never raises.
- Exposure context now emits 3 real breakdown rows (`exposure_business_criticality` ×10, `exposure_internet_facing` ×6, `exposure_data_sensitivity` ×4) driven by the actual Phase 32 `Asset` fields via `_CRITICALITY_FRACTION`/`_SENSITIVITY_FRACTION` lookup tables.
- Cross-scanner corroboration is real: `min((sources_count - 1) / 3, 1.0) * 10` — a capped linear fraction where a single-source finding contributes 0 and 4+ sources contribute the full 10-point budget.
- `compute_finding_risk_scores` adds exactly ONE new tenant-scoped bulk `select` of `VulnerabilityCorrelation.cve_id/asset_id/sources_count` into a Python dict keyed by `(cve_id, asset_id)` — zero per-row queries; a finding with no correlation row correctly defaults to `sources_count=1`.
- The KEV floor now appends an explicit `kev_floor` breakdown component (`raw_value="raised {subtotal} -> 90"`) whenever it actually changes the reported outcome — Plan 33-05's DrillPanel can render "★ KEV floor applied" directly off this row without re-deriving business logic from `kev_floor_applied` + component math.
- RISK-03 re-proven under the FULL formula (not just the tracer's 2 real components): a genuinely zero-contribution LOW/PUBLIC baseline scores `< 20`, its KEV twin scores exactly `90`, a `> 60`-point escalation.
- RISK-04 proven: the corroboration breakdown component's exact contribution delta between 1 and 3 sources is `6.67` points (pre-rounding), and the reported `final_score` is measurably (`>= 6` pts) higher — see Decisions Made for why the final_score delta isn't asserted at a tight `6.7 ± 0.1` tolerance.
- All 10 tests green: the 5 Plan 33-01 regression tests (determinism, KEV floor, EPSS, persistence, response shape) plus 5 new Plan 33-02 tests (native per-source normalization, all-6-components determinism, corroboration, KEV-floor-under-full-formula, correlation-driven scoring via `compute_finding_risk_scores`).

## Task Commits

Each task was committed atomically (TDD: RED → GREEN):

1. **Task 1: RED — native-per-source, corroboration, all-components, KEV-under-full-formula** - `482eab3` (test)
2. **Task 2: GREEN — full formula + native normalization + corroboration bulk-join** - `656b81b` (feat)

**Plan metadata:** (this commit)

## Files Modified

- `backend/app/vulnerabilities/risk_exposure_service.py` — added `_normalize_native_signal`, `_CRITICALITY_FRACTION`/`_SENSITIVITY_FRACTION`/`_CROWDSTRIKE_RATING_FRACTION` tables; replaced the 3 zeroed placeholder component blocks in `score_finding` with real logic; added the conditional `kev_floor` breakdown row; `compute_finding_risk_scores` now bulk-selects `VulnerabilityCorrelation` once per tenant and feeds real `sources_count` into every `FindingScoreInputs`.
- `backend/tests/test_risk_exposure_service.py` — added `test_normalize_native_signal_per_source`, `test_score_finding_all_components`, `test_corroboration_fixture`, `test_kev_floor_survives_full_formula`, `test_compute_uses_correlation_sources_count`.

## Exact Normalization Divisors (for Plan 33-04/33-05 reference)

| Source | Divisor | Notes |
|---|---|---|
| NESSUS | `score / 10.0` | Tenable VPR 0-10 |
| QUALYS | `score / 100.0` | Qualys QDS 0-100 |
| RAPID7 | `score / 1000.0` | Rapid7 Risk Score 0-1000 |
| CROWDSTRIKE | categorical lookup, not divided | `native_priority_rating` only — `{"UNKNOWN":0.0,"LOW":0.25,"MEDIUM":0.5,"HIGH":0.75,"CRITICAL":1.0}` |
| DEFENDER / WIZ | n/a | Always soft-nulls to 0.0 (fields never populated) |

All numeric divisions are clamped to `[0.0, 1.0]` after division — an out-of-scale or garbage vendor value (e.g. NESSUS score=999) clamps to 1.0 rather than exceeding the weight budget; a negative value clamps to 0.0.

## Exposure Sub-Split Point Allocation

- `exposure_business_criticality`: `{CRITICAL: 1.0, HIGH: 0.67, MEDIUM: 0.33, LOW: 0.0} × 10`
- `exposure_internet_facing`: `6.0 if internet_facing else 0.0` (binary, no fraction table)
- `exposure_data_sensitivity`: `{RESTRICTED: 1.0, CONFIDENTIAL: 0.67, INTERNAL: 0.33, PUBLIC: 0.0} × 4`

## Corroboration Curve

`min(max(sources_count - 1, 0) / 3.0, 1.0) × 10` — a capped linear ramp: 1 source → 0 pts, 2 sources → 3.33 pts, 3 sources → 6.67 pts, 4+ sources → 10 pts (capped).

## kev_floor Component Shape (for Plan 33-05)

Appended to the `components` list ONLY when `cisa_kev` is true AND the floor actually changed the outcome (`round(subtotal) < KEV_FLOOR_SCORE`):

```python
RiskBreakdownComponent(
    key="kev_floor",
    label="CISA KEV floor",
    raw_value=f"raised {rounded_subtotal} -> {KEV_FLOOR_SCORE}",
    points=float(KEV_FLOOR_SCORE - rounded_subtotal),
    max_points=0.0,
)
```

`max_points=0.0` is intentional (an annotation row, not a scored budget input) — the DrillPanel can key off `component.key == "kev_floor"` to render the "★ KEV floor applied" chip without re-deriving `kev_floor_applied` from the raw score math.

## Correlation Bulk-Join Confirmation (no N+1)

`compute_finding_risk_scores` issues exactly ONE new query per call:

```python
corr_rows = (await db.execute(
    select(VulnerabilityCorrelation.cve_id, VulnerabilityCorrelation.asset_id,
           VulnerabilityCorrelation.sources_count)
    .where(VulnerabilityCorrelation.tenant_id == tenant_id)
)).all()
corr_by_key = {(r.cve_id, r.asset_id): r.sources_count for r in corr_rows}
```

then reads `corr_by_key.get((vuln.cve_id, vuln.asset_id), 1)` per row inside the existing loop — zero additional queries per Vulnerability row. Verified via `test_compute_uses_correlation_sources_count`: a 3-source finding (with a seeded `VulnerabilityCorrelation` row) scores strictly higher than a single-source finding (no correlation row, defaults to `sources_count=1`), all else equal.

## Decisions Made

See `key-decisions` in frontmatter for the full list. The one substantive judgment call: the RESEARCH-verbatim corroboration fixture (`HIGH`/cvss 7.5/QUALYS native 60/`MEDIUM`/`INTERNAL`, comparing `sources_count=1` vs `3`) produces a `final_score` delta of exactly `7`, not `6.7`, because `RiskBreakdown.final_score` is a rounded `int` (established in Plan 33-01) and the two subtotals (41.87 and 48.54) independently round across an integer boundary in opposite directions. This is a real, expected consequence of rounding two different sums to the nearest int — not a formula bug (confirmed via manual arithmetic: the underlying corroboration component's exact, pre-rounding contribution delta is `6.667`, matching RISK-04's spec precisely). I adjusted the test to assert the exact delta on the `corroboration` breakdown component (the value the DrillPanel will actually render) plus a directional/magnitude check on `final_score` (`>= 6` pts higher), rather than asserting `final_score` delta to a `± 0.1-0.2` tolerance that cannot be satisfied by an integer subtraction landing on a rounding boundary.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corroboration fixture's final_score-delta assertion was untestable as literally specified**
- **Found during:** Task 2 GREEN verification (first full test run after implementing the formula)
- **Issue:** The plan's Task 1 behavior spec (mirroring 33-RESEARCH.md's "Corroboration Mechanics" section verbatim) asserts `score_finding(three_sources).final_score - score_finding(one_source).final_score == pytest.approx(6.7, abs=0.2)`. With the exact base fixture values specified, the true result is `7` (subtotals 41.87→42 and 48.54→49 round in opposite directions across an integer boundary), which fails the `± 0.2` tolerance by `0.1`.
- **Fix:** Rewrote the test to assert on the underlying `corroboration` breakdown component's exact point delta (`6.67`, computed before the final `round()` — deterministic and precise) plus a looser, correct directional assertion on `final_score` (`>= 6` pts higher, which always holds). No change to the production formula — the math is correct; only the test's assertion target moved from the rounded aggregate to the precise, un-rounded component that actually drives it.
- **Files modified:** `backend/tests/test_risk_exposure_service.py`
- **Verification:** Full test suite green (10/10); manually verified via `python3` one-off arithmetic that the discrepancy is a rounding-boundary artifact, not a bug in `_normalize_native_signal`, the exposure fractions, or the corroboration formula.
- **Committed in:** `656b81b` (same commit as the GREEN implementation — test and fix were resolved together during the RED→GREEN cycle)

---

**Total deviations:** 1 auto-fixed (1 bug — test-tolerance mismatch with correct int-rounding behavior, not a scoring bug)
**Impact on plan:** No scope creep, no production behavior change. The formula itself matches the plan's interfaces block exactly.

## Issues Encountered

None beyond the rounding-tolerance deviation above.

## User Setup Required

None. No new migration, no new environment configuration.

## Next Phase Readiness

- Plan 33-03 (asset MAX rollup + severity-tier centralization) can proceed: `score_finding` now returns real, meaningful per-finding scores across all 6 categories, so the MAX rollup will reflect genuinely differentiated finding urgency rather than the tracer's severity+EPSS-only signal.
- Plan 33-05 (DrillPanel breakdown UI) has everything it needs: the `kev_floor` component shape is finalized and documented above; the exposure 3-row split, native-exploitability row, and corroboration row all now carry real `raw_value`/`points`/`max_points` — no further backend changes anticipated for that plan's read side.
- Zero-consumer grep gate re-confirmed unchanged from Plan 01 (`grep -rn "risk_exposure_score\|risk_exposure_breakdown" backend/app --include="*.py" | grep -v risk_exposure_service.py` → only `models.py`/`schemas.py`/`service.py`).
- No blockers.

---
*Phase: 33-risk-exposure-model-definition*
*Completed: 2026-08-11*

## Self-Check: PASSED

Both files (`backend/app/vulnerabilities/risk_exposure_service.py`, `backend/tests/test_risk_exposure_service.py`) found on disk with the expected content (`_normalize_native_signal`, `test_corroboration_fixture` confirmed present via grep). Both task commit hashes (`482eab3`, `656b81b`) found in `git log`.
