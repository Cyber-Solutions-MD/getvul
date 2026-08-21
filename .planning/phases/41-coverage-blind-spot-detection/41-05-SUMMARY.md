---
phase: 41-coverage-blind-spot-detection
plan: 05
subsystem: ui
tags: [react, nextjs, tanstack-query, coverage, drill-panel, rbac]

# Dependency graph
requires:
  - phase: 41-04
    provides: "POST /api/v1/coverage/assets/{asset_id}/route-to-owner (require_analyst) -> RouteToOwnerResponse {hostname, routed_to}, D-07/D-09 resolve-then-notify-with-fallback"
  - phase: 41-01
    provides: "/dashboard/coverage page (blind-spot list) + useBlindSpotAssets + BlindSpotAsset type + coverage query-key group"
provides:
  - "CoverageAssetDrillContent — DrillPanel renderContent slot for idKey='asset' (3-region shape mirroring ticket-drill-content.tsx)"
  - "RouteToOwnerDialog — 2-branch (D-07 resolved / D-09 unresolvable) confirm-only dialog, secondary/violet-focus chrome"
  - "useRouteToOwner(assetId) mutation hook (retry:0, coverage.all invalidation, exact UI-SPEC toast copy)"
  - "coverage/page.tsx wired end-to-end: row click opens DrillPanel(idKey='asset'); per-row + drill-footer 'Route to owner' actions share one dialog/mutation instance; canRouteToOwner RBAC gate"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "RouteToOwnerDialog wraps ResponsiveDialog directly (not ConfirmModal, whose variant->color map has no violet-secondary option; not ExceptionGrantDialog, which is a real form) — the thin-wrapper option 41-PATTERNS.md flagged as reasonable for a 0-field, 2-copy-branch confirm dialog"
    - "A single shared dialog + mutation instance (routeToOwnerTarget state) serves BOTH the per-row action and the drill-footer action, rather than each owning an independent pair — avoids double-instantiating useRouteToOwner and keeps exactly one in-flight mutation per page"

key-files:
  created:
    - frontend/src/lib/queries/use-route-to-owner.ts
    - frontend/src/lib/queries/use-route-to-owner.test.tsx
    - frontend/src/components/coverage/route-to-owner-dialog.tsx
    - frontend/src/components/coverage/route-to-owner-dialog.test.tsx
    - frontend/src/components/coverage/coverage-asset-drill-content.tsx
  modified:
    - "frontend/src/app/(authed)/dashboard/coverage/page.tsx"
    - "frontend/src/app/(authed)/dashboard/coverage/page.test.tsx"
    - frontend/src/components/coverage/microcopy.ts

key-decisions:
  - "No BlindSpotAsset row carries owner-preview data (no assigned_user/directory-email field on BlindSpotAssetResponse), and the plan's reversibility scope explicitly forbids a schema/contract change beyond consuming the Plan 04 endpoint — so every real call site on coverage/page.tsx passes ownerResolved={false}, rendering the D-09 unresolvable-owner dialog copy unconditionally. The RouteToOwnerDialog component itself is fully generic/two-branch and unit-tested with both ownerResolved values; only the WIRING currently has no data to select the resolved branch. The eventual outcome is always correct regardless (the success toast reflects the real server-resolved routed_to)."
  - "Per-row and drill-footer 'Route to owner' actions share ONE RouteToOwnerDialog + ONE useRouteToOwner(assetId) instance at the page level (routeToOwnerTarget state), per the plan's explicit instruction to instantiate the mutation once for 'the active asset'."

patterns-established:
  - "coverage/page.tsx's BlindSpotTable rows are now interactive (tabIndex=0, click + Enter/Space opens the DrillPanel via ?asset=<id>&open=drill), matching tickets-table.tsx's row-click convention at a smaller scale (no arrow-key nav, since this is an inline table not a shared component)."

requirements-completed: [COV-03]

# Metrics
duration: ~50min
completed: 2026-08-21
---

# Phase 41 Plan 05: Route-to-Owner Frontend (COV-03) Summary

**Wires COV-03's write path end-to-end on the client: a per-row and drill-footer "Route to owner" action that opens a 2-branch confirm dialog (D-07 resolved / D-09 unresolvable copy) and fires the Plan 04 endpoint, with exact UI-SPEC success/error toasts and analyst-only RBAC gating — composing DrillPanel/ResponsiveDialog/useToast verbatim, zero new primitives.**

## Performance

- **Duration:** ~50 min
- **Tasks:** 2 completed
- **Files modified:** 8 (5 created, 3 modified)

## Accomplishments

- `useRouteToOwner(assetId)` (`frontend/src/lib/queries/use-route-to-owner.ts`): `POST /api/v1/coverage/assets/{id}/route-to-owner` with no body, `retry: 0`, invalidates `queryKeys.coverage.all` on success, toasts the exact UI-SPEC copy on both success (`"{hostname} routed to {routed_to}"`) and error.
- `RouteToOwnerDialog` (`frontend/src/components/coverage/route-to-owner-dialog.tsx`): confirm-only (no form fields), 2 copy branches — resolved (D-07: `"Notify {owner} about this device?"` / `"Notify owner"`) and unresolvable (D-09: `"No owner found for this device"` / `"Notify admins"`) — wraps `ResponsiveDialog` directly, secondary/`.btn-secondary`-equivalent chrome with a violet focus ring, `"Notifying…"` disabled pending state, never `bg-gradient-sunset`.
- `CoverageAssetDrillContent` (`frontend/src/components/coverage/coverage-asset-drill-content.tsx`): 3-region `DrillPanel` slot content (header/body sections/sticky footer) mirroring `ticket-drill-content.tsx`, paired with `idKey="asset"`; presentational only, delegates the "Route to owner" click to a caller-supplied `onRouteToOwner` callback.
- `coverage/page.tsx` wired end-to-end: `canRouteToOwner` (`OWNER`/`ADMIN`/`ANALYST`) computed once via `useAuth()`; blind-spot rows are now clickable (opens `DrillPanel` at `?asset=<id>&open=drill`, the tickets-page precedent — never `/assets`'s full-page navigation, Pitfall 8) and carry a per-row "Route to owner" button; the drill footer's action and the row action share ONE `RouteToOwnerDialog` + ONE `useRouteToOwner(assetId)` instance (`routeToOwnerTarget` state) rather than duplicating the dialog/mutation pair.
- `microcopy.ts` extended additively with the `routeToOwner` copy group (dialog title/body/confirm-label for both branches, pending label, error toast, disabled-action hint).
- 18 new frontend tests (5 mutation-hook, 5 dialog, 8 page-level: row-click-opens-drill, pre-opened-drill-renders-content, viewer-disabled, analyst-enabled, plus the 5 hook/5 dialog files) — 30/30 green across the touched test files. `tsc --noEmit` and `npm run lint` both clean on every touched/created file (project-wide lint shows only the pre-existing, unrelated Phase 39 `approver-combobox.tsx` warning).

## Task Commits

1. **Task 1: useRouteToOwner mutation hook + route-to-owner-dialog (2-branch) + microcopy** — `0e498b6` (feat)
2. **Task 2: Asset DrillPanel content + row action + RBAC gating on the page** — `c56b689` (feat)

**Plan metadata:** _(pending — this commit)_

## Files Created/Modified

- `frontend/src/lib/queries/use-route-to-owner.ts` — `useRouteToOwner(assetId)` mutation hook
- `frontend/src/lib/queries/use-route-to-owner.test.tsx` — POST-shape, retry:0, invalidation, success/error toast tests
- `frontend/src/components/coverage/route-to-owner-dialog.tsx` — 2-branch confirm dialog
- `frontend/src/components/coverage/route-to-owner-dialog.test.tsx` — both copy branches + pending state + no-pink-CTA tests
- `frontend/src/components/coverage/coverage-asset-drill-content.tsx` — `DrillPanel` slot content for `idKey="asset"`
- `frontend/src/app/(authed)/dashboard/coverage/page.tsx` — `DrillPanel` + row/drill "Route to owner" wiring + `canRouteToOwner` RBAC gate
- `frontend/src/app/(authed)/dashboard/coverage/page.test.tsx` — drill-open + viewer-disabled + analyst-enabled tests
- `frontend/src/components/coverage/microcopy.ts` — `routeToOwner` copy group

## Decisions Made

- See `key-decisions` in frontmatter — the `ownerResolved={false}` default wiring choice (no owner-preview data available client-side without a schema change the plan's reversibility scope forbids) and the single shared dialog/mutation instance.
- `BlindSpotTable`'s new row-click handler uses a lightweight `tabIndex`/`onClick`/`onKeyDown` (Enter/Space) pattern rather than `tickets-table.tsx`'s fuller arrow-key row-navigation — this is a small inline table (not a shared, heavily-reused component), and the plan didn't call for arrow-key nav here.
- Row action button gets an explicit accessible name via its own text content ("Route to owner"), disambiguated from the drill footer's identically-labeled button only by DOM scope (`within(dialog)` in tests) — no `aria-label` override needed since only one is ever visible at a time in the row-click test scenarios that matter.

## Deviations from Plan

None — plan executed exactly as written. The plan's own task text explicitly hedged on how the dialog's copy branch would be selected in real wiring ("...or by whether a resolved-owner name is known for the row") — resolving that hedge (documented above under Decisions/key-decisions) is normal execution judgment within the plan's stated ambiguity, not a deviation from it.

## Issues Encountered

None. All new/modified files pass `tsc --noEmit`, `npm run lint`, and their own test files on the first clean run after the design above was implemented.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- COV-03 is now fully closed (backend 41-04 + frontend 41-05) — marked `[x]` in REQUIREMENTS.md.
- Phase 41 (coverage-blind-spot-detection) is now 5/5 plans complete. No blockers for the next phase.
- Future note for whichever plan eventually adds an owner-preview signal to `BlindSpotAssetResponse` (or a dedicated preview endpoint): `RouteToOwnerDialog`'s `ownerResolved`/`ownerName` props are already fully wired and tested — only `coverage/page.tsx`'s two call sites need their `ownerResolved={false}` literal replaced with the real signal.

## Known Stubs

- `coverage/page.tsx`'s two `<RouteToOwnerDialog ownerResolved={false} ... />` call sites always render the D-09 "No owner found for this device" pre-confirm copy, regardless of whether the backend will actually resolve a real directory owner (which it frequently will — `get_directory_user`'s precedence checks `assigned_user`/`humaans_email`/`last_login_user` against real tenant `User` rows). This does **not** affect correctness of the end-to-end outcome: the mutation still calls the real Plan 04 endpoint, which independently resolves the owner server-side and notifies them correctly; only the pre-confirm dialog's copy is a conservative default rather than a true preview. Not fixable within this plan's frontend-only, no-schema-change scope (see Decisions above) — flagged here for a future plan that might add an owner-preview signal.

## Threat Flags

None — no new security-relevant surface beyond what the plan's own `<threat_model>` (T-41-15/16/17) already anticipated. `canRouteToOwner` is UX-only gating (server `require_analyst` remains authoritative, T-41-15); the mutation is `retry: 0` (T-41-16); the drill panel renders only the tenant's own already-fetched blind-spot summary (T-41-17).

## Self-Check: PASSED

- All 5 created files verified present on disk.
- Both commit hashes (`0e498b6`, `c56b689`) verified present in `git log --oneline`.
- `grep -q "idKey=\"asset\""` and `grep -q "canRouteToOwner"` both confirmed present in `coverage/page.tsx`.
- `grep -L "bg-gradient-sunset"` confirmed absent (as real class usage) in both `route-to-owner-dialog.tsx` and `coverage-asset-drill-content.tsx` (only doc-comment mentions explaining its deliberate absence).
- `npx vitest run` on all 4 touched/created test files: 30/30 passed. `npx tsc --noEmit -p .`: 0 errors. `npm run lint`: 0 new warnings/errors (only the pre-existing, unrelated Phase 39 `approver-combobox.tsx` warning).

---
*Phase: 41-coverage-blind-spot-detection*
*Completed: 2026-08-21*
