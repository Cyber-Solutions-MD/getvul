---
phase: 32-asset-exposure-context
plan: 03
subsystem: api
tags: [fastapi, sqlalchemy, alembic, postgres, audit, rbac, asset-groups]

# Dependency graph
requires:
  - phase: 32-asset-exposure-context (Plan 01)
    provides: Asset.business_criticality/data_sensitivity/internet_facing columns + *_source discriminators (migration 037), app/assets/exposure.py's infer_exposure_context/apply_inference_to_asset/EXPOSURE_FIELDS, PATCH /assets/{id}/exposure-context per-asset override endpoint, audit-then-commit convention
  - phase: 32-asset-exposure-context (Plan 02)
    provides: real data_sensitivity/internet_facing inference, check_criticality_calibration (EXPO-06), alembic head 038_add_exposure_cal_cfg
provides:
  - A real, tenant-scoped AssetGroup entity — model + explicit membership + admin CRUD API (migrations 039/040)
  - app/assets/exposure.py::apply_precedence_to_asset — DB-aware per-field precedence resolver (per-asset ASSET_OVERRIDE > group override, most-recently-updated wins > auto-inference), now used by recompute_exposure_context
  - app/assets/groups_service.py — tenant-scoped CRUD + idempotent add_member/remove_member that immediately re-apply precedence to the affected asset
  - app/assets/groups_router.py mounted at /api/v1/asset-groups — CRUD, membership, and PATCH .../exposure-context (group-scope override)
  - Group-override and group-CRUD audit trail (asset_group.create/update/delete/member_add/member_remove/exposure_override)
affects: [33-risk-exposure-model, 32-04-per-connector-internet-facing, 32-05-frontend-exposure-context]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "apply_precedence_to_asset: DB-aware wrapper layered in front of the pure infer_exposure_context — resolves per-field group-override membership via a single JOIN query (AssetGroupMember ⋈ AssetGroupExposureOverride), picks MAX(updated_at) on multi-group conflict, then falls through to the existing auto tier for any field with no applicable group override"
    - "add_member/remove_member call apply_precedence_to_asset synchronously inside the same transaction as the membership mutation — a newly-added member reflects any group override (or a removed member reverts to auto) without waiting for a full-tenant recompute"
    - "Group-scope override PATCH writes exactly ONE audit row for the mutation itself; member-asset value changes it fans out to are NOT individually audited (mirrors the 'auto-inference audits only on change, never floods audit_logs' anti-pattern from 32-PATTERNS.md)"

key-files:
  created:
    - backend/alembic/versions/039_add_asset_groups.py
    - backend/alembic/versions/040_add_group_exposure_ovr.py
    - backend/app/assets/groups_service.py
    - backend/app/assets/groups_router.py
    - backend/tests/test_asset_groups.py
  modified:
    - backend/app/assets/models.py
    - backend/app/assets/exposure.py
    - backend/app/main.py
    - backend/app/audit.py
    - backend/tests/test_asset_exposure.py
    - backend/mypy-baseline.txt

key-decisions:
  - "GROUP_OVERRIDE precedence lives in a new async apply_precedence_to_asset (DB-aware), separate from the existing sync apply_inference_to_asset (pure, no DB) — the latter is left untouched so Plan 01/02's direct unit tests and sync.py/jamf_sync.py/humaans_sync.py's upsert-time call sites (unchanged, out of this plan's scope) keep working exactly as before. Only recompute_exposure_context and the group-mutation call sites (add_member/remove_member/group-override PATCH) use the new group-aware resolver."
  - "A field whose source is GROUP_OVERRIDE but which no longer has an applicable group override (group deleted, or the asset's last group with an override for that field was removed) reverts to the AUTO tier on the next apply_precedence_to_asset call — not left stranded at a stale GROUP_OVERRIDE value/source."
  - "Group CRUD list/detail (GET) endpoints use get_current_user (any authenticated tenant member may view group context); every mutating endpoint (create/update/delete, member add/remove, exposure-context override) uses require_admin — a new router file with no legacy require_role(\"admin\") import to match, so it follows connectors/router.py's newer RBAC convention per 32-PATTERNS.md guidance."
  - "Test infrastructure fix (Rule 3 — blocking issue): the tenant_a/tenant_b fixtures only flush (never commit), which is fine for Asset (no FK to tenants) but breaks AssetGroup (real FK to tenants) across the client_factory app's separate DB session — the FK check fails because the tenant row isn't visible outside its own uncommitted transaction. Fixed by adding `await db_session.commit()` before the first HTTP call in every group-creating test."

requirements-completed: [EXPO-04, EXPO-05]

# Metrics
duration: 45min
completed: 2026-08-10
---

# Phase 32 Plan 03: Asset Exposure Context — AssetGroup Entity & Group Precedence Summary

**A real tenant-scoped AssetGroup entity (model + membership + admin CRUD) with a GROUP_OVERRIDE precedence tier inserted between per-asset override permanence and auto-inference — most-recently-updated group wins on multi-group conflict, and membership add/remove re-applies precedence immediately.**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-08-10T13:45:00Z (approx.)
- **Completed:** 2026-08-10T14:30:00Z
- **Tasks:** 3 (RED / GREEN part 1 / GREEN part 2)
- **Files modified:** 11 (5 created, 6 modified)

## Accomplishments

- Migrations `039_add_asset_groups` (asset_groups + asset_group_members) and `040_add_group_exposure_ovr` (asset_group_exposure_overrides) chain cleanly `038 -> 039 -> 040`; single head confirmed via `alembic heads`; upgrade/downgrade/upgrade round-trip verified.
- Three new ORM models in `app/assets/models.py`: `AssetGroup` (tenant-scoped entity, mirrors `ConnectorConfig`), `AssetGroupMember` (composite-PK membership, mirrors `TicketWatcher`), `AssetGroupExposureOverride` (one row per group+field, `updated_at` is the tiebreak key).
- `app/assets/exposure.py::apply_precedence_to_asset` (new, async, DB-aware): per field, per asset — `ASSET_OVERRIDE` (permanent) skip → group override via membership JOIN (`MAX(updated_at)` on multi-group conflict) → auto-inference fallback. `recompute_exposure_context` now calls it instead of the group-unaware `apply_inference_to_asset`.
- `app/assets/groups_service.py` (new): tenant-scoped CRUD (`list/get/create/update/delete_group`) mirroring `connectors/service.py`'s shape (no encryption step — no secret material), plus idempotent `add_member`/`remove_member` that immediately call `apply_precedence_to_asset` on the affected asset so a newly-added member picks up an existing group override (or a removed member reverts to auto) without waiting for a full recompute — the explicit 32-CONTEXT.md execution-note requirement.
- `app/assets/groups_router.py` (new, mounted at `/api/v1/asset-groups` in `main.py`): full CRUD + membership + `PATCH /{group_id}/exposure-context` (admin-gated via `require_admin`; list/detail via `get_current_user` so analysts can view group context). 404-not-403 on every cross-tenant probe.
- Group-scope override endpoint upserts the `AssetGroupExposureOverride` row, re-applies precedence to every member, and writes exactly one `asset_group.exposure_override` audit row per mutation (member-level changes are not individually audited — avoids flooding `audit_logs` on large groups, same anti-pattern guidance as auto-inference).
- All 24 tests across `test_asset_groups.py` (3) and `test_asset_exposure.py` (21, including 5 new group-precedence tests) pass: CRUD/membership/RBAC/tenant-isolation, group-override-applies-to-members, asset-override-beats-group-override, multi-group tiebreak (most-recently-updated wins, re-tested both directions), group-override audit row, and add-member-immediately-reapplies-precedence.
- `mypy-baseline.txt` re-synced (0 new violations) after fixing one genuine type-narrowing bug (`update_group`'s `AssetGroup | None` return needed an explicit `assert` before use, since `get_group` had already confirmed existence in the same transaction).

## Task Commits

1. **Task 1: RED — AssetGroup CRUD/membership/RBAC/tenant-isolation + group precedence/tiebreak/audit tests** - `41aad55` (test)
2. **Task 2: GREEN part 1 — migrations, models, groups_service, groups_router, GROUP_OVERRIDE precedence tier, registration** - `ba528f1` (feat)
3. **Task 3: GREEN part 2 — audit action registry + mypy-baseline resync, full suite green** - `6baffc9` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified

- `backend/alembic/versions/039_add_asset_groups.py` - `asset_groups` + `asset_group_members` tables, chains `038 -> 039`
- `backend/alembic/versions/040_add_group_exposure_ovr.py` - `asset_group_exposure_overrides` table, chains `039 -> 040`
- `backend/app/assets/models.py` - `AssetGroup`/`AssetGroupMember`/`AssetGroupExposureOverride` ORM models
- `backend/app/assets/exposure.py` - `apply_precedence_to_asset` (new async precedence resolver) + `_resolve_group_overrides_for_asset` helper; `recompute_exposure_context` rewired to use it
- `backend/app/assets/groups_service.py` - tenant-scoped CRUD + membership with immediate precedence re-apply
- `backend/app/assets/groups_router.py` - `/api/v1/asset-groups` CRUD + membership + group-override endpoint
- `backend/app/main.py` - mounts `asset_groups_router` at `/api/v1/asset-groups`
- `backend/app/audit.py` - action-name registry appended (`asset_group.create/update/delete/member_add/member_remove/exposure_override`)
- `backend/tests/test_asset_groups.py` - 3 tests (CRUD/tenant-isolation, RBAC, membership add/remove)
- `backend/tests/test_asset_exposure.py` - 5 new tests (group-override-applies, asset-beats-group, tiebreak, group-audit-row, add-member-reapplies)
- `backend/mypy-baseline.txt` - re-synced (0 new violations)

## Decisions Made

- **`apply_precedence_to_asset` is a new, separate, async function** rather than modifying `apply_inference_to_asset` in place — this keeps Plan 01/02's existing sync unit tests and upsert-time call sites (`sync.py`, `jamf_sync.py`, `humaans_sync.py` — all out of this plan's scope) working unchanged. Only `recompute_exposure_context` and the group-mutation paths (`add_member`/`remove_member`/group-override PATCH) are group-aware.
- **GROUP_OVERRIDE-sourced fields revert to AUTO when no longer covered by any group override** (group deleted, or the last covering membership removed) — `apply_precedence_to_asset` re-infers and re-tags such fields on its next invocation rather than leaving them stranded at a stale value/source.
- **GET (list/detail) is `get_current_user`-gated, not `require_admin`** — per 32-PATTERNS.md's explicit note not to blindly copy `connectors/router.py`'s admin-gated list; analysts may view group context for the exposure card, while every mutating endpoint stays admin-only.
- **One audit row per group-override mutation, not one per affected member** — mirrors the existing "auto-inference audits only on actual change, never floods the log" convention; member-level value changes triggered by a group override are not individually audited.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `tenant_a`/`tenant_b` fixtures' flush-only semantics break AssetGroup's real FK to `tenants`**
- **Found during:** Task 2 (first GREEN run of `test_asset_groups.py`)
- **Issue:** `conftest.py`'s `tenant_a`/`tenant_b` fixtures only `flush()` (never `commit()`) — this is invisible for `Asset` (no FK to `tenants`) but `AssetGroup.tenant_id` has a real `ForeignKey("tenants.id", ...)` per the plan's interfaces block. The `client_factory` app runs its own separate DB session/transaction; Postgres's FK check on `INSERT INTO asset_groups` queries `tenants` in that separate transaction's snapshot, which cannot see the still-uncommitted tenant row, producing a `ForeignKeyViolationError` (surfaced as an opaque 500).
- **Fix:** Added `await db_session.commit()` as the first statement in every test that creates a group before any other seed/commit already covers it (tests that seed+commit an `Asset` first were unaffected, since that commit finalizes the tenant transaction too as a side effect).
- **Files modified:** `backend/tests/test_asset_groups.py`, `backend/tests/test_asset_exposure.py`
- **Verification:** All 24 tests pass; reproduced the FK violation directly via a standalone script with `raise_app_exceptions=True` to confirm root cause before applying the fix.
- **Committed in:** `ba528f1` (Task 2 commit)

**2. [Rule 1 - Bug] `update_group`'s `AssetGroup | None` return used without a null-check before the response builder**
- **Found during:** Task 2, mypy pass after GREEN
- **Issue:** `groups_router.py::update_asset_group` called `update_group(...)` (which can return `None` on a miss) and passed the result straight to `_group_to_dict` (which requires a non-`None` `AssetGroup`) — the preceding `get_group` check made this unreachable in practice, but mypy correctly flagged the type mismatch, and an un-asserted `None` would raise a confusing `AttributeError` rather than failing loudly in the theoretical concurrent-delete race.
- **Fix:** Added an explicit `assert updated is not None` with an explanatory comment.
- **Files modified:** `backend/app/assets/groups_router.py`
- **Verification:** `mypy app/ | mypy-baseline filter` reports the `arg-type` error resolved; full test suite still green.
- **Committed in:** `ba528f1` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 Rule 1, 1 Rule 3)
**Impact on plan:** Both fixes were necessary for correctness of the test harness and the type gate respectively. No scope creep — no behavior changed beyond what the plan specified.

### Task-boundary consolidation (not a scope deviation)

The plan's Task 2 ("GREEN part 1 — migrations, models, groups_service, groups_router, registration") and Task 3 ("GREEN part 2 — group override endpoint + GROUP_OVERRIDE precedence tier") describe two commits, but `groups_service.py::add_member`/`remove_member` have a hard dependency on the group-aware precedence resolver per 32-CONTEXT.md's explicit execution note ("membership add/remove MUST re-apply precedence to the affected asset immediately"). Building `groups_service.py` without `apply_precedence_to_asset` already existing was not possible, so the precedence tier and the group-override endpoint landed together with the CRUD/membership/migrations in the Task 2 commit. Task 3's commit covers the remaining audit-registry finalization and the full-suite green confirmation. No behavior differs from what the plan specified — only which commit each piece landed in.

## Issues Encountered

None beyond the two auto-fixed items above.

## User Setup Required

None - no external service configuration required. Migrations `039_add_asset_groups` and `040_add_group_exposure_ovr` were applied to the local dev Postgres (`alembic upgrade head`) as part of verification; a production/staging deploy still needs to run the same migrations through its normal deploy pipeline.

## Next Phase Readiness

The exposure-context precedence stack (per-asset > group > auto) is fully landed, tested, and audited:
- Plan 04 (per-connector internet-facing detection) replaces the v1 `external_ip`/tag proxy in `infer_exposure_context` — `apply_precedence_to_asset`'s auto-tier fallback needs no changes.
- Plan 05 (frontend) can build the AssetGroup management UI + group-scope override controls against `/api/v1/asset-groups`'s full CRUD/membership/override surface, and the per-asset exposure-context card can read `*_source == "GROUP_OVERRIDE"` to show which group is driving a field's value.
- Phase 33 (risk-exposure model) can consume `business_criticality`/`data_sensitivity`/`internet_facing` knowing the full precedence chain (including group scope) is authoritative.

No blockers.

## Known Stubs

None - this plan's scope (AssetGroup entity + group precedence tier + audit trail) is fully implemented end-to-end, not a placeholder.

## Threat Flags

None - the new surface (AssetGroup CRUD, membership add/remove, group-scope override endpoint) was explicitly covered by this plan's `<threat_model>` (T-32-07 through T-32-10: admin-gating, tenant-isolation/404-not-403, mass-assignment/enum validation, audit fail-closed). No additional network endpoints, auth paths, or schema changes at trust boundaries beyond what the plan specified.

---
*Phase: 32-asset-exposure-context*
*Completed: 2026-08-10*

## Self-Check: PASSED

All 11 created/modified key files verified present on disk; all 3 task commit hashes (`41aad55`, `ba528f1`, `6baffc9`) verified present in `git log`.
