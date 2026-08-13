---
phase: 33-risk-exposure-model-definition
plan: 01
subsystem: api
tags: [fastapi, sqlalchemy, alembic, postgres, scoring, risk-model]

# Dependency graph
requires:
  - phase: 30-cross-scanner-correlation
    provides: VulnerabilityCorrelation.sources_count (consumed for real starting Plan 33-02)
  - phase: 31-enrichment-signals
    provides: epss_score/cisa_kev/native_priority_score/native_priority_rating on Vulnerability
  - phase: 32-asset-exposure-context
    provides: business_criticality/data_sensitivity/internet_facing on Asset
provides:
  - "Vulnerability.risk_exposure_score / risk_exposure_breakdown (JSONB) / risk_model_version columns"
  - "Asset.risk_exposure_score / risk_model_version shadow-rollup columns (left NULL this plan)"
  - "app/vulnerabilities/risk_exposure_service.py: score_finding (pure) + compute_finding_risk_scores (DB-orchestration)"
  - "Single post-sync shadow-compute hook (sync.py) wired alongside compute_risk_scores"
  - "GET /vulnerabilities/{id} response fields: risk_exposure_score, risk_exposure_breakdown, risk_model_version"
affects: [33-02-full-formula, 33-03-asset-rollup-tier-centralization, 33-05-drillpanel-breakdown-ui, phase-34-cutover]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pure/impure split for scoring modules (score_finding pure, compute_finding_risk_scores DB-orchestration), mirroring app/assets/risk_score.py"
    - "KEV floor via max(subtotal, KEV_FLOOR_SCORE), never additive"
    - "Additive weighted-points component list (never renormalized when an input is missing)"
    - "Shadow-computed schema columns (nullable, no server_default) read directly at response time, never live-recomputed"

key-files:
  created:
    - backend/alembic/versions/042_add_risk_exposure_score.py
    - backend/app/vulnerabilities/risk_exposure_service.py
    - backend/tests/test_risk_exposure_service.py
  modified:
    - backend/app/vulnerabilities/models.py
    - backend/app/assets/models.py
    - backend/app/vulnerabilities/schemas.py
    - backend/app/vulnerabilities/service.py
    - backend/app/connectors/sync.py

key-decisions:
  - "Tracer scope: severity/CVSS (35pts) + EPSS (20pts) + KEV floor (90) are REAL; native_exploitability (15pts), exposure_* (10+6+4pts), corroboration (10pts) are zeroed placeholder components tagged '# PLAN 33-02', never renormalized"
  - "sources_count hardcoded to 1 for every row this plan (no VulnerabilityCorrelation join yet) -- Plan 33-02 adds the bulk correlation join"
  - "risk_exposure_breakdown persisted as list[dict] (the serialized RiskBreakdownComponent list), not the full RiskBreakdown envelope -- matches the response schema's list[RiskBreakdownComponent] shape directly, zero server-side reshaping on read"
  - "Asset.risk_exposure_score / risk_model_version added to the schema spine this plan but left NULL -- Plan 33-03 owns the MAX rollup"
  - "Single sync-hook wire only (sync.py post-sync block) -- the ~9 other compute_risk_scores call sites (vulnerabilities/router.py, ticketing/router.py, seed.py, dev_routes.py) are untouched per 33-CONTEXT.md RESOLVED Q1"

patterns-established:
  - "New scoring modules mirror risk_score.py's pure/impure split and structlog event-logging convention (logger.info(\"finding_risk_scores_computed\", tenant_id=..., findings_updated=...))"
  - "Shadow/preview columns: nullable, no server_default, doc-commented with the requirement ID + which future plan resolves the gap"

requirements-completed: [RISK-01, RISK-02, RISK-03, RISK-06]

# Metrics
duration: 55min
completed: 2026-08-11
---

# Phase 33 Plan 01: Risk-Exposure Model Definition — LEAD TRACER Summary

**Per-finding risk-exposure scoring spine landed end-to-end: migration → model columns → pure `score_finding` (severity/CVSS + EPSS + KEV floor real, everything else a zeroed Plan-33-02 placeholder) → `compute_finding_risk_scores` DB-orchestration → single post-sync shadow-compute hook → persisted-column read on `GET /vulnerabilities/{id}` — zero automated consumer, grep-provable.**

## Performance

- **Duration:** ~55 min
- **Started:** 2026-08-11T12:22:51+03:00 (first task commit)
- **Completed:** 2026-08-11T13:17:08+03:00
- **Tasks:** 3/3
- **Files modified:** 8 (3 created, 5 modified)

## Accomplishments
- Migration `042_add_risk_exposure_score` lands the full 5-column schema spine (3 on `vulnerabilities`, 2 on `assets`), applied cleanly against dev Postgres with a single resulting head.
- `risk_exposure_service.py` implements `score_finding` (pure, deterministic, 100-point additive weighted-sum with a KEV floor via `max()`) and `compute_finding_risk_scores` (bulk-fetch + per-row persist, mirroring `risk_score.py`'s existing shape).
- KEV-floor fixture proves a LOW-severity KEV finding lands at EXACTLY 90, >60pts above its non-KEV twin (RISK-03).
- `compute_finding_risk_scores` wired into the single `sync.py` post-sync hook, alongside (not replacing) `compute_risk_scores` — the first sync after this ships covers every open finding (RISK-06 shadow-compute contract).
- `GET /vulnerabilities/{id}` now returns `risk_exposure_score` / `risk_exposure_breakdown` / `risk_model_version`, read directly off the already-fetched ORM row (zero new query, zero live recompute).
- Zero-consumer grep gate confirmed: only `models.py` / `schemas.py` / `service.py` (display read) reference the new columns outside the service module and migration.

## Task Commits

Each task was committed atomically (TDD: RED → GREEN):

1. **Task 1: RED — determinism + KEV-floor fixture + persistence + response-shape tests** - `59a9066` (test)
2. **Task 2: GREEN part 1 — migration 042, model columns, risk_exposure_service.py** - `40e9e58` (feat)
3. **Task 3: GREEN part 2 — schema fields + persisted-column read + sync hook** - `d59b619` (feat)
4. **Deviation fix — mypy-baseline gate** - `12a12ab` (fix)

**Plan metadata:** (this commit)

## Files Created/Modified
- `backend/alembic/versions/042_add_risk_exposure_score.py` - 5 nullable columns (3 vulnerabilities, 2 assets), no server_default, symmetric downgrade
- `backend/app/vulnerabilities/risk_exposure_service.py` - `FindingScoreInputs`/`RiskBreakdownComponent`/`RiskBreakdown` dataclasses, `score_finding` (pure), `compute_finding_risk_scores` (DB-orchestration)
- `backend/app/vulnerabilities/models.py` - 3 new `Vulnerability` columns (`risk_exposure_score`, `risk_exposure_breakdown` typed `list[dict[str, Any]] | None`, `risk_model_version`)
- `backend/app/assets/models.py` - 2 new `Asset` columns (`risk_exposure_score`, `risk_model_version`), left NULL this plan
- `backend/app/vulnerabilities/schemas.py` - new `RiskBreakdownComponent(BaseModel)` + 3 optional fields on `VulnerabilityResponse`
- `backend/app/vulnerabilities/service.py` - `get_vulnerability` reads the 3 new fields directly off the persisted `vuln` ORM object
- `backend/app/connectors/sync.py` - single call to `compute_finding_risk_scores` added immediately after `compute_risk_scores` in the post-sync block; `"finding_risk_scores"` added to `log.details`
- `backend/tests/test_risk_exposure_service.py` - determinism, KEV-floor, EPSS, persistence, and response-shape tests (5 tests, all green)

## Decisions Made
- **Breakdown persistence shape:** `risk_exposure_breakdown` stores the serialized `list[RiskBreakdownComponent]` (a `list[dict]`), not the full `RiskBreakdown` envelope (final_score/subtotal/kev_floor_applied/version) — this lets Pydantic coerce the persisted JSONB directly into the response's `list[RiskBreakdownComponent] | None` field with zero server-side reshaping on read.
- **Exposure sub-split:** kept the research's 10/6/4-point exposure sub-components (business_criticality/internet_facing/data_sensitivity) as 3 separate zeroed placeholder rows rather than one combined "exposure" row, so Plan 33-02 can fill each independently without changing the breakdown's shape.
- **Asset rollup columns landed but NULL:** per the migration's own schema spine, `Asset.risk_exposure_score`/`risk_model_version` exist now but are never written by this plan (Plan 33-03's MAX rollup owns that).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] mypy-baseline gate flagged 2 new type-arg violations**
- **Found during:** post-Task-3 verification pass (ran the project's actual CI invocation, `mypy app/ | mypy-baseline filter --allow-unsynced`, not just a bare `mypy` on the touched files)
- **Issue:** `Vulnerability.risk_exposure_breakdown: Mapped[dict | None]` (bare `dict`, matching the plan interfaces block verbatim) and `compute_finding_risk_scores(...) -> dict` both tripped mypy strict's "Missing type arguments for generic type dict" as NEW baseline entries — the file already has 2 baselined occurrences of the same message for pre-existing columns, so a 3rd occurrence counts as new and would fail CI's mypy-baseline gate.
- **Fix:** Typed `risk_exposure_breakdown` as `Mapped[list[dict[str, Any]] | None]` (the column's true shape — a list of serialized components, not a nested dict) and gave `compute_finding_risk_scores` an explicit `-> dict[str, int]` return type.
- **Files modified:** `backend/app/vulnerabilities/models.py`, `backend/app/vulnerabilities/risk_exposure_service.py`
- **Verification:** `mypy app/ | mypy-baseline filter --allow-unsynced` reports 0 new errors (was 2); full test file + `test_vulnerability_enrichment.py` regression still green; `ruff check`/`ruff format --check` clean.
- **Committed in:** `12a12ab`

---

**Total deviations:** 1 auto-fixed (1 blocking — CI type-check gate)
**Impact on plan:** No scope creep; the interfaces block's `dict | None` annotation was a simplification for the plan doc, not a literal requirement to use the bare builtin generic. No behavior change, no test changes required.

## Issues Encountered
None beyond the mypy deviation above.

## User Setup Required
None - no external service configuration required. Migration 042 must be applied to any other environment via `alembic upgrade head` (already applied and verified against the local dev Postgres in this session).

## Next Phase Readiness
- The schema + pure/impure split + version + sync-hook + persisted-read spine is fully landed and tested — Plan 33-02 (full formula: native normalization + corroboration + real exposure context) can replace the zeroed placeholder components without touching the schema, the hook, or the response wiring.
- Plan 33-03 (asset MAX rollup + severity-tier centralization) can start independently; `Asset.risk_exposure_score`/`risk_model_version` columns already exist, NULL until that plan writes them.
- Plan 33-05 (DrillPanel breakdown UI) can consume `GET /vulnerabilities/{id}`'s new fields as-is — the response shape (`list[RiskBreakdownComponent]` with `key`/`label`/`raw_value`/`points`/`max_points`) will not change shape when Plan 33-02 lands, only the placeholder rows' `points`/`raw_value` values will become real.
- No blockers.

---
*Phase: 33-risk-exposure-model-definition*
*Completed: 2026-08-11*

## Self-Check: PASSED

All 4 created/referenced files found on disk; all 4 task commit hashes (59a9066, 40e9e58, d59b619, 12a12ab) found in git log.
