---
phase: 14-remaining-screens
fixed_at: 2026-06-03T00:00:00Z
review_path: .planning/phases/14-remaining-screens/14-REVIEW.md
iteration: 1
findings_in_scope: 10
fixed: 10
skipped: 0
status: all_fixed
---

# Phase 14: Code Review Fix Report

**Fixed at:** 2026-06-03
**Source review:** .planning/phases/14-remaining-screens/14-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope (Critical + Warning): 10
- Fixed: 10
- Skipped: 0

All fixes verified via `tsc --noEmit` (no new errors in modified files) and the
full vitest suite (676 tests passing, 113 files). Each fix was committed
atomically on `main` with the semgrep pre-commit hook running (0 findings each).
Info findings (IN-01 .. IN-06) were out of scope (critical_warning) and not touched.

## Fixed Issues

### CR-01: SMTP password sentinel can be persisted as the real secret

**Files modified:** `frontend/src/components/settings/notifications-pane.tsx`
**Commit:** 973a9a5
**Applied fix:** Replaced the brittle mask-literal equality check with explicit
`passwordTouched` tracking, mirroring the connector form's per-field `touched`
pattern. The password field is now seeded EMPTY (never the mask); the
`••••••••` bullets are a placeholder-only hint. The password is included in the
PATCH body solely when `passwordTouched && password` is true, so a displayed
mask of any length/shape can never round-trip back as the stored secret.
Updated the type, `defaultSmtp`, the onChange handler, the save guard, and the
file header doc.

### WR-01: Directory pagination is broken — fetch hardcoded to page 1

**Files modified:** `frontend/src/app/(authed)/dashboard/users/page.tsx`
**Commit:** 01171ba
**Applied fix:** Added `page` state wired into `useDirectoryUsers` (was literal
`1`), a reset-to-1 effect on filter change, a clamp effect when the result set
shrinks below the current page, and prev/next pagination controls mirroring
`audit-log-pane.tsx`.

### WR-02: `handleSelectAll` reads stale data via empty-deps useCallback

**Files modified:** `frontend/src/app/(authed)/dashboard/users/page.tsx`
**Commit:** 01171ba (same atomic commit as WR-01 — both edit interleaved regions of the same file)
**Applied fix:** Derived a stable `items` list from `directoryQuery.data?.items`
and depend on it in `handleSelectAll`, removing the empty dependency array and
the `eslint-disable react-hooks/exhaustive-deps`.

### WR-03: Settings dirty-state bridge relies on global DOM polling

**Files modified:** `frontend/src/app/(authed)/dashboard/settings/page.tsx`, `frontend/src/components/settings/notifications-pane.tsx`, `frontend/src/components/settings/saml-pane.tsx`, `frontend/src/components/settings/workspace-pane.tsx`
**Commit:** 4e68ea1
**Applied fix:** Each editable pane now accepts an optional `onDirtyChange` prop
and reports `useDirtyState.isDirty` up via `useEffect`. The settings page passes
`handleDirtyChange` directly to the panes and deletes the `PaneWithDirtyBridge`
`document.querySelector('[data-save-bar]')` polling wrapper, the page-level
`onClickCapture`, and the `setTimeout(0)` race. The guard is no longer coupled
to SaveBar markup.

### WR-04: Modals lack focus trap / `role="dialog"` / `aria-modal`

**Files modified:** `frontend/src/components/ui/ConfirmModal.tsx`, `frontend/src/components/ui/focus-trap.ts` (new), `frontend/src/app/(authed)/dashboard/connectors/page.tsx`
**Commit:** 3a785cd
**Applied fix:** Added a shared `focus-trap` helper (`getFocusable` +
`trapTabKey`). `ConfirmModal` now sets `role="dialog" aria-modal="true"
aria-labelledby` and traps Tab. The connector add/edit overlay gains the same
dialog semantics, an explicit X close button, Escape handling, and initial
focus — and no longer dismisses on backdrop click, so typed credentials are not
silently discarded. New file `focus-trap.ts` was required (a reusable trap was
the cleanest way to cover both modals).

### WR-05: Audit log can render an out-of-range page after filtering

**Files modified:** `frontend/src/components/settings/audit-log-pane.tsx`
**Commit:** 291bc92
**Applied fix:** Added a `useEffect` clamping `page` to `totalPages` when the
fetched result set has fewer pages than the current page (guarded by
`totalPages > 0` to ignore the transient placeholder state). The existing
`totalPages > 1` guard on the pagination block already prevented the
`Page 1 of 0` count display.

### WR-06: ExportButton falls back to a hardcoded `"dev-token"` bearer

**Files modified:** `frontend/src/components/ui/ExportButton.tsx`
**Commit:** 31f6a92
**Applied fix:** When no `getvul_token` is stored, the component now redirects to
`/login` in production builds instead of issuing a request with a literal
`dev-token` bearer. The `dev-token` convenience fallback is gated behind
`process.env.NODE_ENV !== 'production'`.

### WR-07: `useDirectoryStats` / `useTenantGroups` swallow errors silently

**Files modified:** `frontend/src/app/(authed)/dashboard/users/page.tsx`, `frontend/src/lib/queries/use-tenant-groups.ts`, `frontend/src/lib/queries/use-directory-users.ts`
**Commit:** 06d8ad4
**Applied fix:** Replaced the `data ? … : 'Loading groups…'` ternary in the
groups view with explicit `isPending` / `isError` / data branches, added a
`PartialFailureBanner` with retry on error (the view previously hung on
"Loading groups…" forever, violating D-X-01), and added `retry: 1` to
`useTenantGroups` and `useDirectoryStats`.

### WR-08: WorkspacePane role select offers OWNER for any user

**Files modified:** `frontend/src/components/settings/workspace-pane.tsx`
**Commit:** f20945b
**Applied fix:** Removed `OWNER` from the per-row role `<select>` options for
non-owners (mirrors the Add-user form). The OWNER option is rendered only when
the row already is an OWNER, so the controlled select stays in sync while
ownership can no longer be granted via a one-misclick change.

### WR-09: `handleRoleChange` no-op / desync on failure

**Files modified:** `frontend/src/components/settings/workspace-pane.tsx`
**Commit:** f20945b (same atomic commit as WR-08 — both edit the same role-change surface)
**Status:** fixed: requires human verification (state-resync logic)
**Applied fix:** Early-return when the selected role equals the current cached
role (avoids a redundant PATCH), and `refetchUsers()` after a failed PATCH so
the controlled `<select>` re-derives the authoritative role from cache instead
of stranding on the rejected value. Flagged for human verification because the
fix is a logic/state-handling change (the on-failure re-sync path) that syntax
and unit checks cannot fully validate — confirm the select visibly reverts on a
rejected role change.

## Skipped Issues

None — all in-scope findings were fixed.

---

_Fixed: 2026-06-03_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
