---
phase: 32-asset-exposure-context
verified: 2026-08-11T08:15:55Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
---

# Phase 32: Asset Exposure Context Verification Report

**Phase Goal:** Every asset carries an accurate, admin-overridable exposure-context profile
(business-criticality, data-sensitivity, internet-facing) auto-inferred at upsert, ready to feed
the Phase 33 risk-exposure model.
**Verified:** 2026-08-11T08:15:55Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth (from ROADMAP SC) | Status | Evidence |
|---|--------------------------|--------|----------|
| 1 | Every asset carries business-criticality, data-sensitivity, internet-facing fields, auto-inferred at upsert from MDM/HR enrichment + scanner flags, seeded from — never overwriting — Asset.tags. | ✓ VERIFIED | `Asset` model has 6 columns (3 value + 3 `*_source`, default MEDIUM/INTERNAL/False, all AUTO) in `backend/app/assets/models.py:105-119`. Pure `infer_exposure_context()` (`backend/app/assets/exposure.py:138-191`) reads `tags`/`department`/`job_title` (from `mdm_details["humaans_job_title"]`)/`external_ip`/`internet_facing_detected`, never mutates the input list (copies into a local lower-cased set). `apply_inference_to_asset` is called from all 3 upsert/enrichment touchpoints: `connectors/sync.py:318`, `connectors/jamf_sync.py:171,208`, `connectors/humaans_sync.py:68`. IdP signals correctly NOT wired (per CONTEXT.md deferral) — only MDM/HR/tags/scanner external_ip used. Tests: `test_infer_exposure_context_high_signal_asset`, `test_infer_exposure_context_does_not_mutate_tags`, `test_infer_all_three_fields`, `test_upsert_sets_default_exposure_fields` all pass. |
| 2 | An admin can set a per-field override on a single asset; it permanently wins over future auto re-runs. | ✓ VERIFIED | `PATCH /assets/{id}/exposure-context` (`router.py:565-609`), `require_role("admin")`-gated, flips `*_source` to `ASSET_OVERRIDE`. `apply_inference_to_asset`/`apply_precedence_to_asset` both skip any field whose source is not `AUTO` (models.py comment + exposure.py:219-221, 333-334). Tests: `test_asset_override_wins_over_reinference`, `test_reinference_skips_all_overridden_fields`, `test_asset_override_still_wins_over_detected_signal`, `test_override_requires_admin_role` (403 for analyst/viewer), `test_override_cross_tenant_returns_404_not_403` — all pass. |
| 3 | An admin can set an override at asset-group scope (a real AssetGroup entity), with defined+tested precedence vs a per-asset override (asset > group > auto; multi-group conflict → most-recently-updated wins). | ✓ VERIFIED | Real `AssetGroup`/`AssetGroupMember`/`AssetGroupExposureOverride` ORM models (models.py:132-173), tenant-scoped CRUD + membership service (`groups_service.py`), admin-gated router mounted at `/api/v1/asset-groups` (`main.py:26,311`). Precedence resolver `apply_precedence_to_asset` (exposure.py:311-375): `ASSET_OVERRIDE` always skipped first; group override applied via `_resolve_group_overrides_for_asset`'s most-recently-updated tiebreak (exposure.py:263-289); else auto. `add_member`/`remove_member` re-apply precedence immediately (groups_service.py:117-119, 173-175) per CONTEXT.md's execution note. Tests: `test_group_override_applies_to_group_members`, `test_asset_override_beats_group_override`, `test_conflicting_group_overrides_tiebreak`, `test_add_member_after_override_immediately_applies_precedence`, `test_asset_group_crud_tenant_isolation`, `test_group_endpoints_require_admin` — all pass. |
| 4 | Every exposure-context override (auto or manual) is audit-logged (actor, asset/group, field, old, new); auto via a system actor, logged only on change. | ✓ VERIFIED | Manual per-asset override: `audit(db, user, "asset.exposure_override", "asset", ..., {"field","old","new"})` (router.py:598-605). Group override: `audit(..., "asset_group.exposure_override", "asset_group", ..., {"field","old","new"})` (groups_router.py:301-308). Auto/recompute: direct `AuditLog(...)` construction with `user_email="system:exposure-inference"` (exposure.py:230-260), called only `if changes:` (non-empty) — never a re-affirmation. Tests: `test_asset_override_writes_audit_row`, `test_auto_inference_audits_only_on_change`, `test_group_override_writes_audit_row` — all pass. |
| 5 | A calibration check caps/flags the proportion of assets AUTO-classified at the highest criticality tier (admin/group overrides exempt), provable against a realistic seed fixture. | ✓ VERIFIED | `check_criticality_calibration` (exposure.py:402-456) counts only `business_criticality == CRITICAL AND business_criticality_source == AUTO` against tenant total; reads per-tenant configurable `exposure_criticality_cap` (default 0.15) / `exposure_hard_cap_enabled` (default False, unwired enforcement — flag+report only, matching CONTEXT.md's explicit default). Admin endpoint `GET /assets/exposure-context/calibration` is `require_role("admin")`-gated. Tests: `test_calibration_check_against_realistic_fixture` (realistic seed fixture), `test_calibration_exempts_manual_overrides`, `test_calibration_endpoint_admin_only` — all pass. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/alembic/versions/037_add_exposure_context.py` | 6 exposure columns on assets | ✓ VERIFIED | `op.add_column` x6, chained from `036_add_enrichment_ref_tables`, revision id 24 chars (≤32) |
| `backend/alembic/versions/038_add_exposure_cal_cfg.py` | per-tenant calibration cap + hard-cap-enabled cols | ✓ VERIFIED | Adds `exposure_criticality_cap`/`exposure_hard_cap_enabled` to `tenants`, matches `app/tenants/models.py:51-52` |
| `backend/alembic/versions/039_add_asset_groups.py` | asset_groups + asset_group_members tables | ✓ VERIFIED | `op.create_table` present |
| `backend/alembic/versions/040_add_group_exposure_ovr.py` | asset_group_exposure_overrides table | ✓ VERIFIED | present, chains from 039 |
| `backend/alembic/versions/041_add_inet_facing_signal.py` | internet_facing_detected column | ✓ VERIFIED | `op.add_column`, matches `Asset.internet_facing_detected` (models.py:119) |
| `backend/app/assets/models.py` | enums + 6 Asset columns + AssetGroup/Member/Override models | ✓ VERIFIED | `BusinessCriticality`, `DataSensitivity`, `ExposureFieldSource` enums; `AssetGroup`/`AssetGroupMember`/`AssetGroupExposureOverride` classes present |
| `backend/app/assets/exposure.py` | infer/apply/recompute/calibration/precedence functions | ✓ VERIFIED | `infer_exposure_context`, `apply_inference_to_asset`, `apply_precedence_to_asset`, `recompute_exposure_context`, `check_criticality_calibration`, `audit_auto_inference_changes`, `resolve_group_override_names` all present and substantive (not stubs) |
| `backend/app/assets/router.py` | PATCH override + recompute + calibration endpoints, 6 fields in both inline dicts | ✓ VERIFIED | Lines 565-695; list dict (line 254-259) and detail dict (line 418-426) both extended |
| `backend/app/assets/groups_service.py` | tenant-scoped group CRUD + membership | ✓ VERIFIED | `create_group`/`update_group`/`delete_group`/`add_member`/`remove_member`/`get_group_exposure_overrides` all present, tenant_id-scoped throughout |
| `backend/app/assets/groups_router.py` | AssetGroup CRUD + membership + group override endpoints | ✓ VERIFIED | Mounted at `/api/v1/asset-groups` in `main.py:311`, admin-gated mutations via `require_admin` |
| `backend/tests/test_asset_exposure.py` | inference + override + calibration + group-precedence tests | ✓ VERIFIED | 26 tests, all pass |
| `backend/tests/test_asset_groups.py` | group CRUD + tenant isolation + RBAC tests | ✓ VERIFIED | 5 tests, all pass |
| `backend/tests/test_connector_internet_facing.py` | per-connector coverage documentation tests | ✓ VERIFIED | 6 tests, all pass |
| `frontend/src/components/assets/exposure-context-card.tsx` | 3-field card + source badges + admin flip-edit | ✓ VERIFIED | Renders all 3 fields with `SourceBadge` (auto/manually set/group:{name}), admin-gated inline edit (`isAdmin` from `useAuth`), wired into asset detail page (`assets/[id]/page.tsx:33,230`) |
| `frontend/src/app/(authed)/dashboard/asset-groups/page.tsx` | AssetGroup management surface | ✓ VERIFIED | SkeletonTable/PartialFailureBanner/EmptyState states present, admin-gated CRUD/membership/override affordances, nav entry present (`nav-items.ts:45`) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `connectors/sync.py::_upsert_asset` | `exposure.py::apply_inference_to_asset` | called after asset create/update | ✓ WIRED | `sync.py:318-319` |
| `connectors/jamf_sync.py` | `exposure.py::apply_inference_to_asset` | called after JAMF enrichment | ✓ WIRED | `jamf_sync.py:171-172, 208-209` |
| `connectors/humaans_sync.py` | `exposure.py::apply_inference_to_asset` | called after HR enrichment | ✓ WIRED | `humaans_sync.py:68-69` |
| `router.py PATCH exposure-context` | `audit.py::audit` | audit-then-commit | ✓ WIRED | `router.py:598-606` |
| `groups_router.py PATCH group exposure-context` | `audit.py::audit` | audit-then-commit, resource_type=asset_group | ✓ WIRED | `groups_router.py:301-309` |
| `main.py` | `groups_router` | include_router prefix /api/v1/asset-groups | ✓ WIRED | `main.py:26,311` |
| `exposure.py::recompute_exposure_context` | `asset_group_exposure_overrides` via membership | per-field precedence resolution | ✓ WIRED | `exposure.py:263-289, 311-375` |
| `exposure-context-card.tsx` | `PATCH /assets/{id}/exposure-context` | `useSetExposureOverride` mutation | ✓ WIRED | `use-exposure-override.ts`, invoked from `ExposureRow.save()` |
| `asset-groups/page.tsx` | `/api/v1/asset-groups` | `useAssetGroupsList` + CRUD hooks | ✓ WIRED | imports from `use-asset-groups.ts:24-33` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `exposure-context-card.tsx` | `asset.business_criticality`/`data_sensitivity`/`internet_facing` + `*_source`/`*_group_name` | `AssetDetail` type from `use-asset-detail.ts` (extended, lines 55-65), populated by `router.py::_build_asset_detail` inline dict (line 418-426) which reads real `Asset` ORM columns and `resolve_group_override_names(db, asset.id)` (a live DB join, not static) | Yes | ✓ FLOWING |
| `asset-groups/page.tsx` | `groups` (from `useAssetGroupsList`) | `GET /api/v1/asset-groups` → `list_groups_with_member_counts` — real `SELECT ... JOIN asset_group_members GROUP BY` | Yes | ✓ FLOWING |
| `check_criticality_calibration` | `pct`/`critical_auto`/`total` | Live aggregate `func.count().filter(...)` against the `assets` table (exposure.py:431-437), not a static return | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Backend exposure unit+integration test suite | `pytest tests/test_asset_exposure.py -q` | 26 passed | ✓ PASS |
| Backend asset-groups test suite | `pytest tests/test_asset_groups.py -q` | 5 passed | ✓ PASS |
| Backend connector internet-facing coverage tests | `pytest tests/test_connector_internet_facing.py -q` | 6 passed | ✓ PASS |
| Frontend exposure card + asset-groups page vitest | `vitest run exposure-context-card.test.tsx asset-groups/page.test.tsx` | 13 passed | ✓ PASS |
| Migration chain integrity (037→041, ≤32-char revision ids) | `alembic history` + manual length check | Chain intact from 036 head; all 5 new revision ids ≤26 chars | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| EXPO-01 | 32-01, 32-02, 32-05 | Each asset carries business-criticality, data-sensitivity, internet-facing fields | ✓ SATISFIED | Truths #1; models.py columns + router.py inline dicts + frontend card |
| EXPO-02 | 32-01, 32-02, 32-04 | Auto-inferred at upsert from MDM/HR/scanner flags, seeded from (never overwriting) tags; IdP explicitly narrowed out for v1 per CONTEXT.md | ✓ SATISFIED (with documented scope narrowing) | Truth #1; `infer_exposure_context` uses MDM (`mdm_details`)/HR (`department`)/tags/`external_ip`/`internet_facing_detected`, no IdP join. This is an accepted, explicitly-documented scope reduction (CONTEXT.md "[RESOLVED post-plan-check]"), not a silent gap. |
| EXPO-03 | 32-01, 32-05 | Admin per-field override permanently wins over auto-inference | ✓ SATISFIED | Truth #2 |
| EXPO-04 | 32-03, 32-05 | Group-scope override + defined/tested precedence | ✓ SATISFIED | Truth #3 |
| EXPO-05 | 32-01, 32-03 | Every override audit-logged (actor, asset/group, field, old, new) | ✓ SATISFIED | Truth #4 |
| EXPO-06 | 32-02 | Calibration check caps/flags highest-tier auto-classification proportion | ✓ SATISFIED | Truth #5 |

No orphaned requirements — all 6 EXPO IDs declared across the 5 plans' `requirements` frontmatter and REQUIREMENTS.md's Phase 32 mapping match exactly.

### Anti-Patterns Found

None blocking. A grep for TODO/FIXME/placeholder/empty-return patterns across the phase's key files (`exposure.py`, `groups_service.py`, `groups_router.py`, `models.py`, `exposure-context-card.tsx`, `asset-groups/page.tsx`) returned only one incidental match: an HTML `placeholder="Search hosts by name..."` input attribute in `asset-groups/page.tsx` (a UI text hint, not a stub indicator).

### Human Verification Required

None outstanding as blockers. One item is recorded as **accepted debt** per the phase's own SUMMARY (32-05-SUMMARY.md), consistent with the milestone's established "waived on-trust" precedent (24-06/25-05/26-05/27):

- **Task 3 (visual/role-gating UAT for the exposure card + asset-groups page)** was not run live — no live browser available in this execution environment. The underlying mechanisms (admin-gating via `isAdmin` check, source badges, flip-edit controls, SkeletonTable/PartialFailureBanner/EmptyState states) are implemented and covered by 13 passing vitest tests exercising the same logic non-visually. This is judged as accepted debt, not a failure, per the verification brief's explicit guidance.

### Gaps Summary

No gaps. All 5 ROADMAP success criteria are observably true in the codebase: the exposure-context
schema (6 columns + source discriminators) lands on every asset and is populated at every
upsert/enrichment touchpoint (connectors/sync.py, jamf_sync.py, humaans_sync.py); a real AssetGroup
entity exists with tenant-scoped CRUD, membership, and group-scope overrides; the three-tier
precedence (asset > group > auto, most-recently-updated group tiebreak) is implemented in
`apply_precedence_to_asset` and unit-tested; every override (manual asset, manual group, and
auto-recompute) is audit-logged with the correct actor/old/new shape, auto-logging gated to
changes-only; and the EXPO-06 calibration check correctly exempts admin/group overrides and is
provable against a realistic 100-asset fixture. 37 backend tests + 13 frontend tests all pass.

Three explicitly-scoped, honestly-documented deviations were checked against the phase's own
CONTEXT.md and judged as accepted scope decisions rather than gaps:
1. IdP-directory signals are deferred (documented future work, not a silent drop — EXPO-02's
   MDM/HR/IdP wording was narrowed to MDM/HR for v1 per a 2026-08-10 plan-check).
2. No connector currently exposes a real internet-facing vendor signal — the mechanism
   (`NormalizedVulnerability.internet_facing`, `Asset.internet_facing_detected`, precedence
   preference for the detected signal over the proxy) is fully wired and tested; all 6 connectors
   honestly fall back to the external_ip/tag proxy today, documented per-connector in exposure.py's
   docstring and proven by `test_connector_internet_facing.py`.
3. Task 3's live browser UAT is accepted debt, not a failure, per the milestone's established
   pattern — the underlying admin-gating and state-pattern logic is otherwise test-covered.

---

_Verified: 2026-08-11T08:15:55Z_
_Verifier: Claude (gsd-verifier)_
