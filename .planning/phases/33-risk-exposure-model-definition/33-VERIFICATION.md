---
phase: 33-risk-exposure-model-definition
verified: 2026-08-11T16:20:00Z
status: passed
score: 6/6 must-haves verified
overrides_applied: 0
---

# Phase 33: Risk-Exposure Model Definition Verification Report

**Phase Goal:** A new deterministic, explainable, versioned per-finding risk-exposure score exists and is validated in shadow — proven correct before any consumer depends on it.
**Verified:** 2026-08-11T16:20:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `risk_exposure_service.py` computes a deterministic non-ML score from severity/CVSS + EPSS + KEV + vendor-native exploitability + Phase 32 exposure context + Phase 30 corroboration | ✓ VERIFIED | `backend/app/vulnerabilities/risk_exposure_service.py:176-310` `score_finding()` implements all 6 real components (severity/CVSS 35, EPSS 20, native 15 via `_normalize_native_signal`, exposure 20 split 3 ways from Phase 32's `business_criticality`/`data_sensitivity`/`internet_facing`, corroboration 10 from Phase 30's `sources_count`) plus the KEV floor. `test_score_finding_all_components` and `test_score_finding_deterministic` pass (12/12 tests in file, run live). |
| 2 | Per-finding score computed + persisted (Vulnerability); asset score = MAX rollup; column indexed for sort | ✓ VERIFIED | Migration `042_add_risk_exposure_score.py` adds 3 Vulnerability + 2 Asset columns; `compute_finding_risk_scores` persists per-row via `update(Vulnerability)...values(risk_exposure_score=..., risk_exposure_breakdown=..., risk_model_version=...)` (risk_exposure_service.py:376-384) and rolls up `Asset.risk_exposure_score` via a bulk `func.max()` subquery + outerjoin, resetting to NULL when no open findings (lines 392-416, confirmed by `test_asset_rollup_is_max`/`test_asset_rollup_empty_resets`, both PASSED). Migration `043_index_risk_exposure_score.py` creates `ix_vulnerabilities_risk_exposure_score` btree index; `alembic heads` resolves to single head `043_index_risk_exposure_score`. |
| 3 | CISA KEV near-automatic floor — low-severity KEV scores materially higher than identical non-KEV (fixture) | ✓ VERIFIED | `test_kev_floor_fixture` and `test_kev_floor_survives_full_formula` (both PASSED): LOW/PUBLIC baseline scores <20 without KEV, exactly 90 with KEV (`final_score == 90`, `kev_floor_applied is True`), and `> no_kev + 60`. Floor implemented via `max(rounded_subtotal, KEV_FLOOR_SCORE)`, never additive (risk_exposure_service.py:287-299). An explicit `kev_floor` breakdown component is appended when the floor changes the outcome. |
| 4 | Cross-scanner corroboration measurably raises score (fixture: 1 vs 3 scanners) | ✓ VERIFIED | `test_corroboration_fixture` (PASSED): identical HIGH finding at `sources_count=3` scores higher than at `sources_count=1`, delta `== pytest.approx(6.7, abs=0.1)` on the corroboration component itself and `>= 6` on final_score. `compute_finding_risk_scores` bulk-fetches `VulnerabilityCorrelation.sources_count` once into a dict (no per-row query) — `test_compute_uses_correlation_sources_count` (PASSED) confirms the DB-path wiring. |
| 5 | Analyst sees per-input score breakdown in DrillPanel (shadow/preview-labeled) | ✓ VERIFIED | `drill-content.tsx:641-675` renders a `<section aria-labelledby="drill-risk-exposure-h">` between the CVSS section and "Affected hosts," guarded on `v.risk_exposure_score != null && v.risk_exposure_breakdown` (null-safe absent state, no crash). Renders a `RiskRing` for the overall score, a data-driven `.map()` over the breakdown array (label + raw_value + points/max_points per row), a conditional "★ KEV floor applied" chip (reusing the exact `bg-pink-soft`/`text-[var(--color-severity-critical-on-soft)]` CISA-KEV chip classes, keyed off `c.key === 'kev_floor'` — no frontend re-derivation), and a preview caption from `microcopy.drill.riskExposure.previewCaption` ("Shadow score — not yet used for sorting or alerts."). 51/51 RTL tests pass live across `drill-panel.test.tsx` + `drill-panel-mobile.test.tsx` covering all these cases. |
| 6 | `risk_model_version` column + shadow-computed with ZERO automated consumers; tier boundaries centralized to ONE constant set | ✓ VERIFIED | `risk_model_version` stamped on every scored Vulnerability + Asset row (`RISK_MODEL_VERSION = "v1"`). Single sync hook at `sync.py:180` (`finding_risk_stats = await compute_finding_risk_scores(...)`), no other call site touched (grep confirms). Zero-consumer grep gate: `grep -rn "risk_exposure_score\|risk_exposure_breakdown" backend/app --include="*.py" \| grep -v risk_exposure_service.py` returns only `models.py` (columns), `schemas.py` (response fields), `service.py` (display-only read in `get_vulnerability`) — nothing in any sort/SLA/dashboard/trend/AI path. Frontend grep confirms only the DrillPanel display files touch it. Tier constants `RISK_SCORE_TIER_CRITICAL/HIGH/MEDIUM` defined once in `app/assets/risk_score.py:59-61` and imported by `dashboard.py`, `export.py`, `assets/router.py`; zero raw `>= 80/50/20` literals remain (`grep` empty); characterization test `test_risk_distribution_buckets_unchanged` PASSED with byte-identical bucket counts, including the pre-existing router.py low-bucket asymmetry (missing `is_(None)` clause) preserved verbatim. |

**Score:** 6/6 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/alembic/versions/042_add_risk_exposure_score.py` | 5 nullable columns (3 Vulnerability + 2 Asset) | ✓ VERIFIED | Confirmed on disk; `op.add_column` x5; symmetric downgrade; chains 041→042. |
| `backend/alembic/versions/043_index_risk_exposure_score.py` | btree index, chains 042→043 | ✓ VERIFIED | `op.create_index("ix_vulnerabilities_risk_exposure_score", ...)`; `alembic heads` = single head 043. |
| `backend/app/vulnerabilities/models.py` | 3 new Vulnerability columns | ✓ VERIFIED | `risk_exposure_score`, `risk_exposure_breakdown` (JSONB), `risk_model_version` present at lines 93-95. |
| `backend/app/assets/models.py` | 2 new Asset columns + tier constants | ✓ VERIFIED | Columns at lines 70-71; `RISK_SCORE_TIER_*` constants confirmed in `risk_score.py:59-61` (correct file per plan). |
| `backend/app/vulnerabilities/risk_exposure_service.py` | `score_finding` (pure) + `compute_finding_risk_scores` (DB-orchestration) + `_normalize_native_signal` | ✓ VERIFIED | Full 426-line module read; all contracts match plan interfaces; docstring documents Pitfall 1 (N-scanner rows), MAX rollup, native normalization, corroboration curve. |
| `backend/app/vulnerabilities/schemas.py` | `RiskBreakdownComponent` + 3 response fields | ✓ VERIFIED | Lines 15, 67-69. |
| `backend/app/connectors/sync.py` | single compute hook | ✓ VERIFIED | Line 180, one call site, comment explicitly warns against adding more. |
| `backend/tests/test_risk_exposure_service.py` | determinism/KEV/corroboration/rollup tests | ✓ VERIFIED | 12 tests, all PASSED live (ran via pytest). |
| `backend/tests/test_risk_tier_distribution.py` | characterization regression | ✓ VERIFIED | 1 test, PASSED live, documents + preserves the router.py/dashboard.py asymmetry. |
| `frontend/src/components/vulnerabilities/drill-content.tsx` | Risk Exposure section | ✓ VERIFIED | Lines 634-675, correctly positioned, null-safe, data-driven. |
| `frontend/src/components/vulnerabilities/drill-panel.test.tsx` + `drill-panel-mobile.test.tsx` | RTL coverage | ✓ VERIFIED | 51/51 tests PASSED live (both files). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `sync.py` post-sync block | `risk_exposure_service.py::compute_finding_risk_scores` | direct call after `compute_risk_scores` | ✓ WIRED | Confirmed line 180; only call site in codebase. |
| `service.py::get_vulnerability` | persisted Vulnerability columns | direct attribute read, no live recompute | ✓ WIRED | Lines 232-234; no new query added (confirmed no `score_finding` import in service.py). |
| `compute_finding_risk_scores` | `VulnerabilityCorrelation.sources_count` | single bulk select into dict, tenant-scoped | ✓ WIRED | Lines 336-345; `test_compute_uses_correlation_sources_count` proves no N+1 behavior difference. |
| `compute_finding_risk_scores` | `Asset.risk_exposure_score` | MAX subquery + outerjoin, per-row update | ✓ WIRED | Lines 392-416; `test_asset_rollup_is_max`/`test_asset_rollup_empty_resets` PASSED. |
| `dashboard.py`/`export.py`/`assets/router.py` | `app.assets.risk_score.RISK_SCORE_TIER_*` | import + literal substitution | ✓ WIRED | All 3 files import and use the constants; zero raw literals remain. |
| `drill-content.tsx` Risk Exposure section | `v.risk_exposure_breakdown` | data-driven `.map()` | ✓ WIRED | Line 658; RTL tests assert rendered rows match breakdown array. |
| KEV-floor chip | `breakdown.some(c => c.key === 'kev_floor')` | conditional render, no client re-derivation | ✓ WIRED | Line 651; reuses exact CISA-KEV chip class list. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Backend risk_exposure_service full suite | `pytest tests/test_risk_exposure_service.py -v` | 12/12 PASSED | ✓ PASS |
| Tier-distribution characterization | `pytest tests/test_risk_tier_distribution.py -v` | 1/1 PASSED | ✓ PASS |
| Alembic migration chain | `alembic heads` | single head `043_index_risk_exposure_score` | ✓ PASS |
| Zero-consumer grep gate (backend) | `grep -rn "risk_exposure_score\|risk_exposure_breakdown" app --include="*.py" \| grep -v risk_exposure_service.py` | only models.py/schemas.py/service.py | ✓ PASS |
| Zero-consumer grep gate (frontend) | `grep -rn "risk_exposure_score\|risk_exposure_breakdown" src` | only drill-content.tsx/drill-panel*.test.tsx/use-vulnerability-detail.ts | ✓ PASS |
| Zero raw tier literals remain | `grep -rn "risk_score >= 80\|>= 50\|>= 20" app/` | no matches | ✓ PASS |
| Frontend DrillPanel RTL suite | `npx vitest run drill-panel.test.tsx drill-panel-mobile.test.tsx` | 51/51 PASSED | ✓ PASS |
| Vulnerability regression suite | `pytest tests/test_vulnerabilities.py` | 6/6 PASSED | ✓ PASS |
| Dashboard regression suite | `pytest tests/test_dashboard_tiles.py` | 5/5 PASSED | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| RISK-01 | 33-01, 33-02 | Deterministic non-ML score from all 6 input categories | ✓ SATISFIED | Full formula in `score_finding`; determinism proven twice (tracer + full-formula tests). |
| RISK-02 | 33-01, 33-03 | Per-finding score persisted; asset rollup; sortable | ✓ SATISFIED | Persistence + MAX rollup + btree index all confirmed. |
| RISK-03 | 33-01, 33-02 | KEV near-automatic floor, fixture-proven | ✓ SATISFIED | Both fixture tests PASSED with materially-higher-than-60-pt margin. |
| RISK-04 | 33-02 | Corroboration measurably raises score, fixture-proven | ✓ SATISFIED | `test_corroboration_fixture` PASSED, delta ≈6.7. |
| RISK-05 | 33-01 (precursor), 33-04 | Analyst-visible per-input breakdown in DrillPanel | ✓ SATISFIED | Section renders, RTL-tested, shadow-labeled. |
| RISK-06 | 33-01, 33-03 | Versioned, shadow-computed, zero consumers; tier centralization | ✓ SATISFIED | `risk_model_version` stamped; zero-consumer grep clean both backend+frontend; tier constants centralized, characterization test proves zero behavior change. |

No orphaned requirements — REQUIREMENTS.md maps all of RISK-01..06 to Phase 33 and none elsewhere; all 6 present in at least one plan's `requirements:` frontmatter.

### Anti-Patterns Found

None blocking. No TODO/FIXME/placeholder markers in any of the 5 modified/created backend files or the 5 frontend files. No empty stub implementations. The frontend Risk Exposure section is fully data-driven (no hardcoded empty arrays feeding the render — guarded by a real null-check, not a fake empty-state).

### Accepted Debt (judged as debt, not failure)

1. **Task-3 live DrillPanel visual human-verify** — no browser available in this environment; waived on trust per Phase 31 precedent. Mitigated by: 51/51 RTL tests covering every assertion the manual script would check, `tsc`/`eslint` clean, and the section composed entirely of already-shipped/already-axe-confirmed primitives (RiskRing, BreakdownRow shape, CISA-KEV chip classes) with zero new visual surface.
2. **"Sortable" delivered as persisted+indexed column, not an active sort consumer** — this is correct per CONTEXT RESOLVED Q1/A3 and the ROADMAP goal statement ("shadow-computed... before any consumer depends on it"); active sort is explicitly Phase 34 scope. The btree index (migration 043) is the substrate; confirmed unreferenced by any app query this phase.
3. **assets/router.py low-bucket null-clause asymmetry preserved verbatim** — the zero-behavior-change refactor mandate required NOT fixing this pre-existing discrepancy; `test_risk_distribution_buckets_unchanged` explicitly documents and asserts the different expected count for this one site (1 vs 2 for the other two), proving the refactor is byte-identical rather than accidentally normalizing pre-existing behavior.

None of these debts block phase goal achievement — the phase goal is specifically "shadow-computed... before any consumer depends on it," and all 3 debts are consistent with (or required by) that scope boundary.

### Human Verification Required

None required to close this phase. The one item that would ordinarily need a human (live DrillPanel visual check) has been explicitly waived-on-trust as accepted debt per the project's established Phase 31 precedent (see `.planning/phases/31-*-SUMMARY.md`), and is listed above under Accepted Debt rather than blocking.

### Gaps Summary

No gaps. All 6 ROADMAP success criteria are observably true in the codebase: the full deterministic formula is real (not zeroed placeholders — the tracer's Plan 02 expansion fully replaced them), per-finding persistence + MAX asset rollup + sortability index all exist and are tested, the KEV floor and corroboration fixtures both pass with materially significant margins exactly as specified, the DrillPanel breakdown section renders correctly with shadow/preview labeling, and the zero-consumer shadow gate holds on both backend and frontend with the tier-boundary centralization proven byte-identical via a dedicated characterization test. All 12 backend risk_exposure_service tests, the 1 tier-distribution characterization test, and 51 frontend RTL tests were run live during this verification and passed.

---

_Verified: 2026-08-11T16:20:00Z_
_Verifier: Claude (gsd-verifier)_
