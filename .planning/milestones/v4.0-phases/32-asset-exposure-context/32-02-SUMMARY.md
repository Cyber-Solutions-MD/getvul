---
phase: 32-asset-exposure-context
plan: 02
subsystem: api
tags: [fastapi, sqlalchemy, alembic, postgres, calibration, rbac]

# Dependency graph
requires:
  - phase: 32-asset-exposure-context (Plan 01)
    provides: Asset.business_criticality/data_sensitivity/internet_facing columns + *_source discriminators (migration 037), app/assets/exposure.py's infer_exposure_context/apply_inference_to_asset/recompute_exposure_context/EXPOSURE_FIELDS, PATCH /assets/{id}/exposure-context override endpoint, audit-then-commit convention, _build_asset_detail() shared helper
provides:
  - Real data_sensitivity inference (pii/phi/restricted -> RESTRICTED; pci/confidential/finance/legal -> CONFIDENTIAL; public/www/marketing -> PUBLIC; default INTERNAL)
  - Real internet_facing v1 proxy ("internet-facing" tag OR external_ip IS NOT NULL) — documented Plan 04 upgrade point for real per-connector detection
  - app/assets/exposure.py::check_criticality_calibration(db, tenant_id) — EXPO-06 AUTO-only CRITICAL-proportion calibration
  - Tenant.exposure_criticality_cap / Tenant.exposure_hard_cap_enabled (migration 038, per-tenant configurable, default 0.15 / False)
  - GET /assets/exposure-context/calibration (admin-only) report endpoint
affects: [32-03-asset-groups, 32-04-per-connector-internet-facing, 32-05-frontend-exposure-context, 33-risk-exposure-model]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "check_criticality_calibration mirrors asset_stats's risk_distribution single-aggregate-query shape (func.count().filter(...) for the numerator alongside a plain func.count() for the denominator) rather than two round-trips"
    - "Per-tenant numeric config columns (Float + Boolean with server_default) read inline inside the function that needs them, not hoisted into a separate config-loading service — mirrors how existing per-tenant JSONB config columns (sla_config, smtp_config) are read directly off the Tenant row"

key-files:
  created:
    - backend/alembic/versions/038_add_exposure_cal_cfg.py
  modified:
    - backend/app/assets/exposure.py
    - backend/app/assets/router.py
    - backend/app/tenants/models.py
    - backend/tests/test_asset_exposure.py
    - backend/mypy-baseline.txt

key-decisions:
  - "data_sensitivity tier mapping (Claude's Discretion, documented in exposure.py's module docstring): RESTRICTED = tags contain pii/phi/restricted; CONFIDENTIAL = tags contain pci/confidential OR department in {finance, legal}; PUBLIC = tags contain public/www OR department is marketing; INTERNAL = default. First-match-wins ordered priority, same shape as Plan 01's business_criticality mapping."
  - "internet_facing v1 proxy formula: (\"internet-facing\" in tags) OR (external_ip is not None) — the exact CONTEXT.md-mandated fallback. Plan 04 is the documented owner of real per-connector detection (Wiz publicExposure / cloud security-group signals); no existing connector currently extracts such a signal (re-verified this session, matches 32-PATTERNS' 'No Analog Found' finding)."
  - "check_criticality_calibration reads cap/hard_cap_enabled directly off the Tenant row inside the function (a plain select-by-id, not a separate config service) — matches the codebase's existing pattern of reading per-tenant JSONB config columns (sla_config, smtp_config) inline where needed."
  - "hard_cap_enabled is surfaced in the calibration report dict but has NO enforcement code path wired anywhere — a deliberate, documented stub per CONTEXT.md's explicit flag+report default (silently down-ranking a genuinely critical asset is worse than flagging). Even when a tenant sets the flag True, check_criticality_calibration only reports over_cap; nothing in this plan mutates business_criticality based on it."
  - "Calibration test fixture builds 100 real Asset rows and calls apply_inference_to_asset on each (not hand-set business_criticality='CRITICAL' values) so the 20/100 CRITICAL proportion is proven against actual infer_exposure_context output — a stronger, more honest test than asserting against manually-stamped values."

requirements-completed: [EXPO-06]  # EXPO-01/EXPO-02 remain Pending — shared-ID gate (mirrors Plan 01's precedent): EXPO-01 also needs Plan 05 (frontend surfacing) and EXPO-02 also needs Plan 04 (real per-connector internet-facing detection); both flip once their last contributing plan lands. EXPO-06 appears only in this plan's requirements and is fully, provably complete.

# Metrics
duration: 25min
completed: 2026-08-10
---

# Phase 32 Plan 02: Asset Exposure Context — Data Sensitivity, Internet Facing & Calibration Summary

**Real data_sensitivity + internet_facing inference completing the exposure-context triad, plus EXPO-06's AUTO-only criticality calibration report with a per-tenant configurable 15% cap (flag+report, hard-cap deliberately unwired).**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-08-10T13:15:00Z (approx.)
- **Completed:** 2026-08-10T13:40:00Z
- **Tasks:** 2
- **Files modified:** 6 (1 created, 5 modified)

## Accomplishments

- Replaced Plan 01's two documented `# PLAN 02:` static-default returns in `infer_exposure_context` with real ordered-priority logic: `data_sensitivity` (RESTRICTED/CONFIDENTIAL/PUBLIC/INTERNAL from tag + department signals) and `internet_facing` (the v1 "internet-facing" tag / `external_ip` proxy). `apply_inference_to_asset` needed zero changes — it already iterates `EXPOSURE_FIELDS`, so both newly-real fields now propagate on every AUTO-gated re-run automatically.
- Added a test proving `apply_inference_to_asset` skips **all three** fields (not just `business_criticality`) once each has been individually flipped to `ASSET_OVERRIDE` — closing a gap Plan 01's tests didn't cover (it only exercised the one-field override case).
- `check_criticality_calibration(db, tenant_id)` (new function in `app/assets/exposure.py`): a single aggregate query (mirrors `asset_stats`'s `risk_distribution` shape) counting `total` assets vs. `critical_auto` (business_criticality == CRITICAL AND source == AUTO only — admin/group overrides exempt). Reads `cap`/`hard_cap_enabled` from the tenant row (migration 038, default 0.15/False). Returns `{pct, cap, over_cap, critical_auto, total, hard_cap_enabled}`; never mutates any asset regardless of `hard_cap_enabled`.
- Migration `038_add_exposure_cal_cfg` adds `exposure_criticality_cap` (Float, default 0.15) + `exposure_hard_cap_enabled` (Boolean, default False) to `tenants`; chains `037 -> 038` cleanly, single head confirmed via `alembic heads`, applied to the local dev Postgres.
- `GET /assets/exposure-context/calibration` (admin-only via `require_role("admin")`) returns the report; analyst/viewer get 403 (T-32-05).
- Proved against a realistic inline 100-asset fixture (20 assets with a genuine Finance-department + CFO-job_title signal, run through the real `apply_inference_to_asset` — not hand-stamped): `pct == 0.20`, `over_cap == True` against the 0.15 default cap, then `over_cap` flips to `False` after raising the tenant's cap to 0.25 (proving tenant-configurability) without any asset's `critical_auto` count changing (proving flag+report never mutates).
- Proved override exemption end-to-end: an admin PATCHing one asset's `business_criticality` to `CRITICAL` via the real `/exposure-context` endpoint does **not** increment `critical_auto` — only the one genuinely `AUTO`-sourced CRITICAL asset counts.
- All 16 tests in `test_asset_exposure.py` green (13 from Plan 01 + 3 new calibration tests + the 3 new Task-1 inference/override tests are additive to the file's running total — see Task Commits for the exact per-task count).
- Re-synced `mypy-baseline.txt` (0 new violations) after the `Tenant` model's two new columns and `exposure.py`'s new function shifted line numbers.

## Task Commits

1. **Task 1: RED + GREEN — real data_sensitivity + internet_facing inference** - `fa9abaa` (feat)
2. **Task 2: RED + GREEN — calibration check + per-tenant cap config + admin report endpoint** - `940fe07` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified

- `backend/alembic/versions/038_add_exposure_cal_cfg.py` - 2 scalar columns on `tenants` (`exposure_criticality_cap` Float default 0.15, `exposure_hard_cap_enabled` Boolean default false), chains `037 -> 038`
- `backend/app/assets/exposure.py` - real `data_sensitivity`/`internet_facing` inference logic (replacing the two Plan-01 placeholders) + new `check_criticality_calibration` function + expanded module docstring documenting both tier mappings and the calibration numerator/denominator
- `backend/app/assets/router.py` - `GET /assets/exposure-context/calibration` admin endpoint
- `backend/app/tenants/models.py` - `exposure_criticality_cap` / `exposure_hard_cap_enabled` columns on `Tenant`
- `backend/tests/test_asset_exposure.py` - 3 new Task-1 tests (all-three-fields inference, internet_facing tag/external_ip proxy, all-fields-skip-when-overridden) + 3 new Task-2 tests (100-asset realistic fixture, override exemption, admin-only RBAC)
- `backend/mypy-baseline.txt` - re-synced to absorb line-number shifts (0 new violations after sync)

## Decisions Made

- **data_sensitivity tier mapping** — documented in full in `exposure.py`'s module docstring (see key-decisions above). Ordered-priority, first-match-wins, same shape as Plan 01's `business_criticality` mapping.
- **internet_facing v1 proxy** — exactly CONTEXT.md's mandated fallback formula; Plan 04 explicitly owns upgrading this to real per-connector detection.
- **Calibration reads tenant config inline** — `check_criticality_calibration` does a plain `select(Tenant).where(Tenant.id == tenant_id)` inside the function rather than routing through a separate config-loading service, matching how `sla_config`/`smtp_config` (existing per-tenant JSONB columns) are read elsewhere in the codebase.
- **hard_cap_enabled is a pure, unwired flag in this plan** — deliberately no enforcement code path exists anywhere, even when the flag is True. This matches CONTEXT.md's explicit "flag+report only" default and avoids any risk of the calibration check silently contradicting EXPO-03's override-permanence guarantee.
- **Calibration test fixture proves real inference, not hand-set values** — the 100-asset fixture calls the actual `apply_inference_to_asset` (using a genuine Finance/CFO signal) rather than setting `business_criticality = "CRITICAL"` directly on the ORM object, so the test is provably exercising the same code path a real scanner upsert would hit.

## Deviations from Plan

None - plan executed exactly as written. The interfaces block's exact function signatures, migration shape, and endpoint contract were followed as specified; no architectural changes, no blocking issues beyond the routine mypy-baseline resync (which Plan 01 already established as the expected post-implementation step for this codebase's CI gate, not a deviation from this plan's scope).

## Issues Encountered

One test-authoring correction during Task 2 development (not a plan deviation, an internal test-writing fix before the commit): the calibration and override-exemption tests initially called `apply_inference_to_asset` on a brand-new, not-yet-flushed `Asset` object — at that point SQLAlchemy's Python-side column defaults (`business_criticality_source = "AUTO"`, etc.) have not yet been applied to the in-memory instance, so the AUTO-gate's `getattr(asset, f"{field}_source", "AUTO")` read `None` instead of `"AUTO"` and silently skipped every field. Fixed by reordering to `add` + `commit` first (establishing the DB-materialized `AUTO`/`MEDIUM` defaults), then mutating signal fields and calling `apply_inference_to_asset` — matching the exact convention Plan 01's `test_reinference_updates_auto_field` already established. Caught and fixed before either test was committed; no commit needed reverting.

## User Setup Required

None - no external service configuration required. Migration `038_add_exposure_cal_cfg` was applied to the local dev Postgres (`alembic upgrade head`) as part of verification; a production/staging deploy still needs to run the same migration through its normal deploy pipeline.

## Next Phase Readiness

The full exposure-context inference triad (business_criticality, data_sensitivity, internet_facing) now infers real values from real signals, and EXPO-06's calibration is fully provable. Ready for:
- Plan 03 (AssetGroup entity + GROUP_OVERRIDE precedence) — inserts the middle tier into `apply_inference_to_asset`'s per-field AUTO-gate with zero changes needed to the two fields this plan added logic for.
- Plan 04 (per-connector internet-facing detection) — replaces this plan's v1 `external_ip`/tag proxy with real per-connector signals wherever the vendor payload supports it; `EXPOSURE_FIELDS`/`apply_inference_to_asset`'s AUTO-gate mechanism needs no changes.
- Plan 05 (frontend) — consumes the same 6 inline-dict keys (already surfaced since Plan 01) plus the new `GET /assets/exposure-context/calibration` report for an admin-facing calibration widget.

No blockers.

## Known Stubs

- **`hard_cap_enabled` has no enforcement path** (`backend/app/assets/exposure.py::check_criticality_calibration`). This is the plan's explicit, CONTEXT.md-mandated scope: flag+report only, hard-cap enforcement deliberately never wired even when the tenant flag is set True. Not an oversight — a documented permanent design boundary unless a future plan explicitly revisits it.

## Threat Flags

None - the one new endpoint (`GET /assets/exposure-context/calibration`) was explicitly covered by this plan's `<threat_model>` (T-32-05 admin-gate + tenant-scoping; T-32-06 accepts the hard-cap-path-not-wired disposition). No additional network endpoints, auth paths, or schema changes at trust boundaries beyond what the plan specified.

---
*Phase: 32-asset-exposure-context*
*Completed: 2026-08-10*

## Self-Check: PASSED

All 5 created/modified key files verified present on disk; both task commit hashes (`fa9abaa`, `940fe07`) verified present in `git log`.
