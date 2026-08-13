---
phase: 32-asset-exposure-context
plan: 05
subsystem: ui
tags: [nextjs, react, tanstack-query, tailwind, fastapi, sqlalchemy, exposure-context, asset-groups]

# Dependency graph
requires:
  - phase: 32-asset-exposure-context (Plan 01)
    provides: Asset.business_criticality/data_sensitivity/internet_facing columns + *_source discriminators, PATCH /assets/{id}/exposure-context per-asset override endpoint
  - phase: 32-asset-exposure-context (Plan 02)
    provides: real data_sensitivity/internet_facing inference, EXPO-06 calibration check
  - phase: 32-asset-exposure-context (Plan 03)
    provides: the real AssetGroup entity (model + membership + admin CRUD API at /api/v1/asset-groups) + GROUP_OVERRIDE precedence tier
  - phase: 32-asset-exposure-context (Plan 04)
    provides: real per-connector internet-facing detection spine (frontend-invisible — same internet_facing/internet_facing_source contract as Plan 01)
provides:
  - ExposureContextCard — asset detail page rail component surfacing business_criticality/data_sensitivity/internet_facing with a per-field source badge (auto / manually set / group: {name}) and admin inline flip-edit override
  - /dashboard/asset-groups — AssetGroup management page (list + admin CRUD + membership + per-group exposure override), sunset design system, mandatory loading/error/explained-empty states, admin-gated mutating affordances
  - Backend read-side additions (Rule 2/3 deviation, no schema change): member_count on group list/detail, GET /{group_id}/members, GET /{group_id}/exposure-context, exposure.py::resolve_group_override_names surfaced as {field}_group_name on the asset detail response
affects: [33-risk-exposure-model]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Source badge idiom: reuses owner-card.tsx's IdpPill shape (neutral bordered pill, mono uppercase) rather than inventing a new tinted badge — a data-provenance label, not a severity/status signal, stays visually neutral per visual-language.md"
    - "Mutation response IS the new GET shape: useSetExposureOverride's PATCH response is the full AssetDetail dict (backend shares _build_asset_detail between GET and PATCH) — onSuccess writes it directly into the byId cache via setQueryData AND invalidates, faster than invalidate-and-refetch alone while still satisfying the plan's literal 'invalidate' instruction"
    - "Read-side group-name lookup instead of a persisted column: resolve_group_override_names re-runs the existing most-recently-updated-wins tiebreak query (no new state) to answer 'which group currently drives this field' at GET-time only — avoids a migration for a value that's cheap to recompute and only needed for display"

key-files:
  created:
    - frontend/src/lib/queries/use-exposure-override.ts
    - frontend/src/lib/queries/use-asset-groups.ts
    - frontend/src/components/assets/exposure-context-card.tsx
    - frontend/src/components/assets/exposure-context-card.test.tsx
    - frontend/src/components/assets/asset-group-form.tsx
    - frontend/src/app/(authed)/dashboard/asset-groups/page.tsx
    - frontend/src/app/(authed)/dashboard/asset-groups/page.test.tsx
  modified:
    - frontend/src/lib/queries/use-asset-detail.ts
    - frontend/src/lib/queries/keys.ts
    - frontend/src/app/(authed)/dashboard/assets/[id]/page.tsx
    - frontend/src/app/(authed)/dashboard/assets/[id]/page.test.tsx
    - frontend/src/components/assets/owner-card.test.tsx
    - frontend/src/components/assets/risk-card.test.tsx
    - frontend/src/components/assets/identity-metadata-rail.test.tsx
    - frontend/src/components/shell/nav-items.ts
    - backend/app/assets/groups_service.py
    - backend/app/assets/groups_router.py
    - backend/app/assets/exposure.py
    - backend/app/assets/router.py
    - backend/tests/test_asset_groups.py
    - backend/tests/test_asset_exposure.py

key-decisions:
  - "Backend deviation (Rule 2/3): Plan 03's /api/v1/asset-groups surface had no GET for member count/list or current group overrides — added member_count (list+detail), GET /{id}/members, GET /{id}/exposure-context (all get_current_user-gated, matching the existing view-gating convention), no schema change"
  - "Backend deviation (Rule 2): the exposure card's 'group: {name}' badge needs to know which group currently drives a GROUP_OVERRIDE field — added exposure.py::resolve_group_override_names, a pure read-side lookup reusing the existing tiebreak query, surfaced as {field}_group_name on GET /assets/{id}; no new persisted column"
  - "Admin gating is UI-layer defense-in-depth only (T-32-13) — every mutating affordance (override edit, group create/edit/delete, member add/remove, group-override edit) is hidden behind isAdmin, but the real boundary is the backend's require_admin/require_role('admin'), unchanged by this plan"
  - "Add-member search reuses the existing useAssets({filters:{search}}) list hook (debounced 250ms, mirroring ReassignCombobox) instead of adding a new search-scoped endpoint"
  - "Task 3 (human-verify checkpoint) recorded as accepted verification debt rather than blocking execution — no live browser in this environment, matching the milestone's established manual-UAT pattern (24-06/25-05/26-05/27's waived-on-trust precedent)"

requirements-completed: [EXPO-01, EXPO-03, EXPO-04]

# Metrics
duration: ~40min
completed: 2026-08-11
---

# Phase 32 Plan 05: Asset Exposure Context — Frontend (Exposure Card + AssetGroup Management) Summary

**Asset detail page gains an ExposureContextCard (3 fields + auto/manually-set/group:{name} source badges + admin inline override), and a new /dashboard/asset-groups page delivers full AssetGroup CRUD + membership + per-group override management — both admin-gated in the UI as defense-in-depth, backed by two small, additive backend read endpoints this plan discovered were missing.**

## Performance

- **Duration:** ~40 min
- **Started:** 2026-08-11T10:20:00Z (approx.)
- **Completed:** 2026-08-11T11:00:00Z
- **Tasks:** 3 (Task 1 exposure card, Task 2 asset-groups page, Task 3 human-verify checkpoint — recorded as accepted debt)
- **Files modified:** 21 (7 created, 14 modified)

## Accomplishments

- `ExposureContextCard` (`frontend/src/components/assets/exposure-context-card.tsx`) renders `business_criticality`/`data_sensitivity`/`internet_facing` as stacked rows (owner-card.tsx flip-edit + identity-metadata-rail.tsx row shape), each with a source badge — `AUTO` → "auto", `ASSET_OVERRIDE` → "manually set", `GROUP_OVERRIDE` → "group: {name}" (real group name, not a placeholder — see backend deviation below). Admins get a per-row flip-edit control (enum `<select>` for criticality/sensitivity, Yes/No toggle for internet-facing) wired to `useSetExposureOverride`; non-admins see the identical rows with no edit affordance. Wired into `assets/[id]/page.tsx`'s right rail beside `OwnerCard`.
- `use-exposure-override.ts`'s `useSetExposureOverride` PATCHes `/assets/{id}/exposure-context` with `{field, value}` only (T-32-13 mass-assignment guard, mirrors `useReassignAsset`'s T-12-08 precedent), writes the full-detail response straight into the `byId` cache on success, invalidates for good measure, and toasts success/error.
- `AssetDetail` (`use-asset-detail.ts`) extended with the 6 Phase 32 exposure fields plus 3 new `{field}_group_name` fields (this plan's backend addition) — snake_case, no transform layer, matching the codebase-wide convention.
- New `/dashboard/asset-groups` page (`frontend/src/app/(authed)/dashboard/asset-groups/page.tsx`) lists groups (name, description, member count) with mandatory `SkeletonTable`/`PartialFailureBanner`/explained-`EmptyState` per D-X-01; admins get create/edit (`AssetGroupForm` in a `ResponsiveDialog`) and delete (`ConfirmModal`); every group has a "Manage" panel (any tenant member may view) covering membership (list + admin add/remove, debounced add-member search reusing `useAssets`) and the group-scope exposure override (3 rows, admin inline edit, mirrors the card's flip-edit shape). Nav entry added to `WORKFLOW_ITEMS` in `nav-items.ts` (no chip, per D-N-01).
- `use-asset-groups.ts` — full list/create/update/delete + members + exposure-context query/mutation hook set against `/api/v1/asset-groups`, mirroring `use-connectors-admin.ts`'s toast-on-settle shape; `queryKeys.assetGroups` (list/members/exposureContext) added to `keys.ts`.
- **Backend deviation (Rule 2/3 — discovered during Task 2 read_first):** Plan 03's `/api/v1/asset-groups` surface had create/update/delete/add-member/remove-member/set-override but **no GET** for member count, member list, or current group overrides — the frontend literally could not show "member_count", let an admin see-then-remove existing members, or see-then-edit an existing override. Added (no schema change):
  - `member_count` on both the list and detail group responses (single outer-join + `GROUP BY`, no N+1 per-group count query)
  - `GET /{group_id}/members` — list of member assets (`id`, `hostname`)
  - `GET /{group_id}/exposure-context` — current `{field: value}` override dict
  - All three `get_current_user`-gated (matching the existing list/detail view-gating convention — any tenant member may view group context; every mutating endpoint stays `require_admin`)
- **Backend deviation (Rule 2 — discovered during Task 1):** the exposure card's "group: {name}" badge (32-CONTEXT.md's explicit truths wording) needs to know *which* group currently wins the multi-group tiebreak, but no `Asset` column persists that (the tiebreak in `apply_precedence_to_asset` is resolved transiently). Added `exposure.py::resolve_group_override_names` — a pure read-side lookup reusing the existing `_resolve_group_overrides_for_asset` tiebreak query plus a name join — surfaced as `{field}_group_name` on `GET /assets/{id}` (and the per-asset override PATCH response, since both share `_build_asset_detail`). No new persisted state.
- 18 new frontend tests (9 `exposure-context-card.test.tsx` + 6 `asset-groups/page.test.tsx` + 3 pre-existing fixture updates for the extended `AssetDetail` type) all green; full frontend suite 922/922 green; `tsc --noEmit` + `eslint` clean on every touched file.
- 6 new backend tests (`test_group_list_and_detail_include_member_count`, `test_group_members_and_exposure_context_read_endpoints` incl. non-admin read + cross-tenant 404, `test_asset_detail_surfaces_driving_group_name`) all green; full `test_asset_exposure.py` + `test_asset_groups.py` suites green (31 tests total); `ruff check`/`ruff format --check` clean; `mypy-baseline.txt` shows 0 new violations.

## Task Commits

1. **Backend deviation — group member_count + GET members/exposure-context read endpoints** - `076fe81` (feat)
2. **Backend deviation — surface the driving group's name on GROUP_OVERRIDE-sourced fields** - `eee47e4` (feat)
3. **Task 1: Exposure-context card + per-asset override controls on the asset detail page** - `e2fee77` (feat)
4. **Task 2: AssetGroup management page + hooks + form + nav entry** - `e1fb6bc` (feat)
5. **Task 3: checkpoint:human-verify** — recorded as accepted verification debt (see below), no separate commit

**Plan metadata:** (this commit)

## Files Created/Modified

- `frontend/src/lib/queries/use-exposure-override.ts` - `useSetExposureOverride` PATCH mutation (T-32-13 field/value-only body, cache write + invalidate + toast)
- `frontend/src/lib/queries/use-asset-groups.ts` - full AssetGroup CRUD + membership + exposure-override query/mutation hooks
- `frontend/src/components/assets/exposure-context-card.tsx` - 3-field exposure card with source badges + admin flip-edit overrides
- `frontend/src/components/assets/exposure-context-card.test.tsx` - 9 tests (values+badges, admin/non-admin gating, select+toggle submit, cancel, null display)
- `frontend/src/components/assets/asset-group-form.tsx` - name/description add/edit form
- `frontend/src/app/(authed)/dashboard/asset-groups/page.tsx` - management page (list/CRUD/membership/override)
- `frontend/src/app/(authed)/dashboard/asset-groups/page.test.tsx` - 6 tests (loading/error/empty×2/admin affordances/non-admin read-only)
- `frontend/src/lib/queries/use-asset-detail.ts` - `AssetDetail` extended with 6 exposure fields + 3 group-name fields
- `frontend/src/lib/queries/keys.ts` - `queryKeys.assetGroups` added
- `frontend/src/app/(authed)/dashboard/assets/[id]/page.tsx` - `ExposureContextCard` wired into the right rail
- `frontend/src/app/(authed)/dashboard/assets/[id]/page.test.tsx` - mock asset fixture + rail assertion extended
- `frontend/src/components/assets/owner-card.test.tsx`, `risk-card.test.tsx`, `identity-metadata-rail.test.tsx` - fixture extended for the new `AssetDetail` fields (tsc fix)
- `frontend/src/components/shell/nav-items.ts` - "Asset groups" nav entry
- `backend/app/assets/groups_service.py` - `list_groups_with_member_counts`, `count_members`, `list_members`, `get_group_exposure_overrides`
- `backend/app/assets/groups_router.py` - `member_count` on list/detail + 2 new GET endpoints
- `backend/app/assets/exposure.py` - `resolve_group_override_names`
- `backend/app/assets/router.py` - `_build_asset_detail` wires in `{field}_group_name`
- `backend/tests/test_asset_groups.py`, `test_asset_exposure.py` - 6 new tests for the above

## Decisions Made

- See `key-decisions` in frontmatter — summarized: two backend read-endpoint additions (Rule 2/3, no schema change) were necessary for the frontend to deliver what the plan's `must_haves` literally describe (member count, membership management, "group: {name}" badge); admin gating stays UI-only defense-in-depth; the add-member search reuses the existing asset-list hook rather than a new endpoint.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2/3 - Missing critical functionality / blocking] AssetGroup API had no read endpoints for member count, member list, or current group overrides**
- **Found during:** Task 2 read_first (reading `groups_router.py`/`groups_service.py` before building the management page)
- **Issue:** The plan's Task 2 `<behavior>` requires the page to show member count and let an admin manage members (implying seeing current members to remove them) and set a per-group override (implying seeing the current value to edit it) — but Plan 03's backend only exposed mutating `POST`/`DELETE` member endpoints and a mutating `PATCH` override endpoint, with zero `GET` for any of the three.
- **Fix:** Added `member_count` to the list/detail group responses, `GET /{group_id}/members`, and `GET /{group_id}/exposure-context` — all `get_current_user`-gated (matching the pre-existing list/detail view convention), no schema change.
- **Files modified:** `backend/app/assets/groups_service.py`, `backend/app/assets/groups_router.py`, `backend/tests/test_asset_groups.py`
- **Verification:** 5 new/updated backend tests green (`member_count` in list+detail; both new GET endpoints incl. non-admin read + cross-tenant 404); `ruff`/`mypy-baseline` clean (0 new violations).
- **Committed in:** `076fe81`

**2. [Rule 2 - Missing critical functionality] No way to know which group drives a GROUP_OVERRIDE-sourced field**
- **Found during:** Task 1 (building the exposure card's source badge)
- **Issue:** 32-CONTEXT.md's truths literally specify the badge text "group: {name}", but `apply_precedence_to_asset`'s multi-group tiebreak resolution is transient (never persisted) — the asset detail response had no way to answer "which group is currently winning this field."
- **Fix:** Added `exposure.py::resolve_group_override_names` — reuses the existing `_resolve_group_overrides_for_asset` tiebreak query plus a name join (pure read-side, no new column) — wired into `_build_asset_detail` as `{field}_group_name`.
- **Files modified:** `backend/app/assets/exposure.py`, `backend/app/assets/router.py`, `backend/tests/test_asset_exposure.py`
- **Verification:** 1 new backend test proving the group name surfaces for an overridden field and is `null` for an `AUTO` field; full `test_asset_exposure.py` suite green.
- **Committed in:** `eee47e4`

---

**Total deviations:** 2 auto-fixed (both Rule 2/3 — missing critical functionality / blocking, backend read-side additions)
**Impact on plan:** Both additions were necessary for the frontend to deliver the plan's own literal `must_haves` (member count, manageable membership, an accurate "group: {name}" badge) — no schema changes, no new trust boundaries, no scope creep beyond what Task 1/2's stated behavior already required.

## Issues Encountered

None beyond the two backend gaps documented above as deviations.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 32 (Asset Exposure Context) is now fully executed — all 5 plans complete, all 6 EXPO requirements (`EXPO-01` through `EXPO-06`) marked Complete in REQUIREMENTS.md. The full exposure-context stack (auto-inference, per-asset override, AssetGroup entity + group override + precedence, real per-connector internet-facing detection spine, and now the frontend surfaces for all of it) is ready for Phase 33 (Risk-Exposure Model Definition) to consume `business_criticality`/`data_sensitivity`/`internet_facing` as stable, admin-overridable inputs.

No blockers. Ready for `/gsd-verify-work 32`.

## Known Stubs

None - both surfaces (exposure card, asset-groups page) are fully wired to real data with no hardcoded/placeholder values.

## Manual-Only Verifications (Accepted Debt)

**Task 3 (checkpoint:human-verify) was not run live** — no live browser is available in this execution environment. Per the milestone's established manual-UAT precedent (24-06/25-05/26-05/27's "waived on-trust" checkpoints, see STATE.md Deferred Items), this is recorded as accepted verification debt rather than a blocker:

1. Live visual confirmation of the exposure card on `/dashboard/assets/{id}` (all 3 fields + source badges, "auto" reads correctly for an unmodified asset, override submit → success toast → value updates → badge flips to "manually set").
2. Live confirmation of `/dashboard/asset-groups` (loading skeleton → list/empty state, create/add-member/set-override → a member asset's own card badge shows "group", delete via confirm modal).
3. Live confirmation of non-admin (analyst/viewer) read-only behavior on both surfaces.
4. Live visual sweep for raw hex/non-sunset styling and copy-voice compliance.

All automated coverage (18 new frontend tests + 6 new backend tests, full frontend suite 922/922, full backend exposure/groups suites, tsc/eslint/ruff/mypy-baseline) is green — see Accomplishments above. Close this debt via a future live-stack pass or `/gsd-verify-work 32`.

## Threat Flags

None beyond what 32-05-PLAN's own `<threat_model>` already covers (T-32-13 elevation-of-privilege via UI gating, T-32-14 XSS via rendered group name/field values — both addressed as specified: `isAdmin` hides every mutating affordance, backend `require_admin` is the real boundary; all rendered text is React text children, no `dangerouslySetInnerHTML`). The two backend read endpoints added as deviations (`GET .../members`, `GET .../exposure-context`) are read-only, `get_current_user`-gated, tenant-scoped (404-not-403 on cross-tenant probe, tested), and expose no new sensitive data beyond what the mutating endpoints already implied was visible to an admin who created the override.

---
*Phase: 32-asset-exposure-context*
*Completed: 2026-08-11*

## Self-Check: PASSED

All 11 created/modified key files verified present on disk; all 4 task commit hashes (`076fe81`, `eee47e4`, `e2fee77`, `e1fb6bc`) verified present in `git log`.
