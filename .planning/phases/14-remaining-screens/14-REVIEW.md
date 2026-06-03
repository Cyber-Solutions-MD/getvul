---
phase: 14-remaining-screens
reviewed: 2026-06-03T00:00:00Z
depth: standard
files_reviewed: 43
files_reviewed_list:
  - frontend/src/app/(authed)/dashboard/connectors/page.tsx
  - frontend/src/app/(authed)/dashboard/cspm/page.tsx
  - frontend/src/app/(authed)/dashboard/settings/page.tsx
  - frontend/src/app/(authed)/dashboard/users/page.tsx
  - frontend/src/app/globals.css
  - frontend/src/components/connectors/connector-card.tsx
  - frontend/src/components/connectors/connector-form.tsx
  - frontend/src/components/connectors/connector-mark.tsx
  - frontend/src/components/connectors/microcopy.ts
  - frontend/src/components/connectors/sync-status-pill.tsx
  - frontend/src/components/connectors/types.ts
  - frontend/src/components/cspm/compliance-framework-strip.tsx
  - frontend/src/components/cspm/cspm-bulk-bar.tsx
  - frontend/src/components/cspm/cspm-status-pill.tsx
  - frontend/src/components/cspm/finding-card.tsx
  - frontend/src/components/cspm/finding-drill-content.tsx
  - frontend/src/components/cspm/microcopy.ts
  - frontend/src/components/settings/api-tokens-pane.tsx
  - frontend/src/components/settings/audit-log-pane.tsx
  - frontend/src/components/settings/microcopy.ts
  - frontend/src/components/settings/notifications-pane.tsx
  - frontend/src/components/settings/profile-pane.tsx
  - frontend/src/components/settings/saml-pane.tsx
  - frontend/src/components/settings/save-bar.tsx
  - frontend/src/components/settings/settings-sidebar-shell.tsx
  - frontend/src/components/settings/use-dirty-state.ts
  - frontend/src/components/settings/workspace-pane.tsx
  - frontend/src/components/ui/ConfirmModal.tsx
  - frontend/src/components/ui/ExportButton.tsx
  - frontend/src/components/users/directory-table.tsx
  - frontend/src/components/users/microcopy.ts
  - frontend/src/components/users/source-pill.tsx
  - frontend/src/components/users/users-export-bar.tsx
  - frontend/src/lib/queries/keys.ts
  - frontend/src/lib/queries/use-audit-log.ts
  - frontend/src/lib/queries/use-connectors-admin.ts
  - frontend/src/lib/queries/use-cspm-detail.ts
  - frontend/src/lib/queries/use-cspm-findings.ts
  - frontend/src/lib/queries/use-directory-users.ts
  - frontend/src/lib/queries/use-tenant-groups.ts
  - frontend/src/lib/queries/use-tenant-settings.ts
  - frontend/src/lib/queries/use-tenant-users.ts
findings:
  critical: 1
  warning: 9
  info: 6
  total: 16
status: issues_found
---

# Phase 14: Code Review Report

**Reviewed:** 2026-06-03T00:00:00Z
**Depth:** standard
**Files Reviewed:** 43
**Status:** issues_found

## Summary

Phase 14 rebuilds the /connectors, /cspm, /users, and /settings dashboard screens plus shared connector/settings primitives. The credential-handling story is largely sound: the connector form's sentinel-passthrough logic (omit untouched credentials, never send the `••••••` literal) is correctly implemented, the `ConnectorMark`/`SourcePill`/`CspmStatusPill` literal-lookup injection guards hold, and the remediation URL is rendered as a plain `href` text node with no `dangerouslySetInnerHTML`. RBAC gating is consistently documented as UX-only with backend enforcement.

The one BLOCKER is a real data-correctness defect in the SMTP notifications pane: the password sentinel is keyed off an `8-bullet` mask but the displayed sentinel in the placeholder differs, and the seeding path can re-submit a stored mask as the real password under a plausible backend contract — see CR-01. Beyond that, the most impactful issues are a broken directory pagination contract (fetch hardcoded to page 1 while the table renders a paginated response), a stale-closure `handleSelectAll`, and a fragile DOM-polling dirty-state bridge in the settings page. Several copy and a11y issues round out the list.

## Critical Issues

### CR-01: SMTP password sentinel can be persisted as the real secret

**File:** `frontend/src/components/settings/notifications-pane.tsx:79,140` (and contract in `frontend/src/lib/queries/use-tenant-settings.ts:49`)
**Issue:** `defaultSmtp` seeds the form password field directly from `cfg.password` (`password: String(cfg.password ?? '')`). The save guard then omits the password only when `values.smtp.password === SMTP_SENTINEL` where `SMTP_SENTINEL = '••••••••'` (exactly 8 bullets). This is brittle in two ways:

1. The backend contract is only documented in a comment ("Backend returns the sentinel mask"). If the backend ever returns a mask of a different length (e.g. masks to the real secret length, or returns `'********'`, or 6 bullets), the equality check fails and the **masked value is sent back to the backend as the new password**, silently corrupting the stored SMTP credential. For a security product persisting outbound mail credentials, a mask-as-password write is a credential-integrity defect.
2. The `password` input's `placeholder` is `SMTP_SENTINEL` but the field `value` is also seeded with the sentinel, so the placeholder never shows — the masked bullets are the actual editable value. A user who clicks into the field, types one char, and deletes it leaves a value that differs from the exact sentinel and gets persisted.

The connector form (`connector-form.tsx`) solves the equivalent problem correctly with explicit per-field `touched` tracking; the SMTP pane should use the same approach instead of value-equality against a hardcoded mask.

**Fix:** Track whether the password field was edited rather than comparing against a literal mask. Seed the field empty and rely on a `touched` flag:
```ts
// seed empty, never the mask
password: '',
passwordTouched: false,
// on change:
setSmtpField('password', val); setSmtpField('passwordTouched', true);
// on save:
if (values.smtp.passwordTouched && values.smtp.password) {
  smtpPayload.password = values.smtp.password;
}
// else omit — backend keeps stored value
```
If the masked value must be displayed for UX, store it separately from the submit value and never include the displayed mask in the payload under any code path.

## Warnings

### WR-01: Directory pagination is broken — fetch is hardcoded to page 1

**File:** `frontend/src/app/(authed)/dashboard/users/page.tsx:147-157`
**Issue:** `useDirectoryUsers` is called with `page: 1` as a literal, with no page state and no pagination controls anywhere on the page. The response type (`DirectoryUsersResponse`) carries `total`, `page`, `page_size`, and `pages`, and the audit pane implements next/prev — but the directory silently shows only the first page. Any tenant with more than `page_size` users cannot see or select the rest, and "select all" (WR-02) only ever covers page 1.
**Fix:** Add page state (`const [page, setPage] = useState(1)`), pass it to `useDirectoryUsers`, and render prev/next controls driven by `data.pages` (mirroring `audit-log-pane.tsx:226-249`).

### WR-02: `handleSelectAll` reads stale data via empty-deps useCallback

**File:** `frontend/src/app/(authed)/dashboard/users/page.tsx:133-139`
**Issue:** `handleSelectAll` is wrapped in `useCallback(..., [])` with an `eslint-disable react-hooks/exhaustive-deps`, but it closes over `directoryQuery.data`. Because the dependency array is empty, the callback captures the `directoryQuery` reference from the first render. With TanStack Query the query object identity is recreated on data changes, so the captured `.data.items` can be stale (e.g. empty on first paint, or a previous filter's result), causing select-all to select the wrong rows or nothing.
**Fix:** Add `directoryQuery.data?.items` to the dependency array (or derive the id list from a stable memo and depend on it), and remove the eslint-disable:
```ts
const items = directoryQuery.data?.items ?? [];
const handleSelectAll = useCallback(() => {
  setSelectedIds((prev) => prev.length === items.length ? [] : items.map((u) => u.id));
}, [items]);
```

### WR-03: Settings dirty-state bridge relies on global DOM polling

**File:** `frontend/src/app/(authed)/dashboard/settings/page.tsx:143-147,189-196`
**Issue:** The unsaved-changes guard determines dirtiness by querying `document.querySelector('[data-save-bar]')` from both a page-level `onClickCapture` and a per-pane `setTimeout(0)` after every click/change/input. This is fragile:
- It couples the guard to a CSS selector emitted by an unrelated component (`SaveBar`), so a markup rename silently disables the guard (data loss: user switches category and loses edits with no prompt).
- `setTimeout(0)` after input is racy — if the user clicks the sidebar button before the timer fires, `paneDirtyRef` may be stale; the page-level `onClickCapture` partially mitigates this but the two mechanisms can disagree.
- Any other `[data-save-bar]` in the DOM (future reuse) yields false positives.
**Fix:** Have each editable pane report its `isDirty` up via the existing `onDirtyChange` prop (the prop is already threaded through `PaneWithDirtyBridge` but never called by the panes). Pass a real callback from `useDirtyState.isDirty` instead of inferring state from the DOM.

### WR-04: Modals lack focus trap / `role="dialog"` / `aria-modal`

**File:** `frontend/src/components/ui/ConfirmModal.tsx:53-61`, `frontend/src/app/(authed)/dashboard/connectors/page.tsx:343-364`
**Issue:** `ConfirmModal` and the connector add/edit overlay render a backdrop + panel but neither sets `role="dialog"`/`aria-modal="true"` nor traps focus. `ConfirmModal` focuses the confirm button on open but Tab can move focus to the page behind the backdrop, and the connector overlay has no Escape handler and no initial focus. For destructive flows (delete connector, deactivate user) this is an accessibility and mis-click risk. The connector overlay also closes on any backdrop click while the user is mid-credential-entry, discarding typed secrets with no confirmation.
**Fix:** Add `role="dialog" aria-modal="true" aria-labelledby={...}` to the panel, trap focus within the dialog while open, and for the connector form prefer an explicit close affordance over backdrop-click dismissal (or confirm-on-dirty) so in-progress credential input is not lost.

### WR-05: Audit log can render an out-of-range page after filtering

**File:** `frontend/src/components/settings/audit-log-pane.tsx:58-70,226-249`
**Issue:** `useAuditLog` uses `placeholderData: (prev) => prev` (keepPreviousData). When a filter changes, `handleFilterChange` resets `page` to 1 — but the three filter setters call `handleFilterChange()` synchronously alongside `setAction/setResourceType/setUserEmail`, and `page` reset and filter change are batched into the same render, which is fine. However, `totalPages` is read from possibly-stale placeholder data during the transition, so the Next button can briefly enable/disable incorrectly and `Page {page} of {totalPages}` can show `Page 1 of 0` momentarily. More importantly, there is no effect clamping `page` when a new filter result has fewer pages than the current page if the user paginates then filters.
**Fix:** Clamp page against `data.pages` after fetch (`useEffect(() => { if (totalPages > 0 && page > totalPages) setPage(totalPages); }, [totalPages])`), and guard the count display against `totalPages === 0`.

### WR-06: ExportButton falls back to a hardcoded `"dev-token"` bearer

**File:** `frontend/src/components/ui/ExportButton.tsx:19,35`
**Issue:** When no `getvul_token` is in `localStorage`, the component sends `Authorization: Bearer dev-token`. This mirrors the existing `api.ts` convention, but in a production build it means an unauthenticated export request is issued with a literal `dev-token` string rather than redirecting to login. If a backend ever honors `dev-token` in a non-prod-but-internet-reachable environment, this is an auth-bypass vector. The refresh path is also duplicated from `api.ts` rather than reused, so the two can drift (e.g. the `api.ts` BL-06 safe-method retry restriction is not reflected here — though export is GET, so acceptable today).
**Fix:** Route the export through the shared `api`/auth layer, or at minimum redirect to `/login` when no token is present instead of sending a placeholder bearer. Do not ship `dev-token` as a runtime fallback in production builds (gate behind `NODE_ENV !== 'production'`).

### WR-07: `useDirectoryStats` / `useTenantGroups` swallow errors silently

**File:** `frontend/src/lib/queries/use-directory-users.ts:112-119`, `frontend/src/lib/queries/use-tenant-groups.ts:22-29`
**Issue:** `useDirectoryStats` and `useTenantGroups` set `staleTime` but neither sets `retry` nor is the `isError` state consumed in the page. In `users/page.tsx`, the groups view renders `groupsQuery.data ? '...groups' : 'Loading groups…'` — on error, `data` is undefined so the UI is stuck showing "Loading groups…" forever (no error state, violating the mandatory D-X-01 error pattern that CLAUDE.md calls the v1 audit's top pain point). The chip-bar axes silently degrade to static fallback when stats error, which is acceptable, but the groups view has no error branch at all.
**Fix:** Add an `isError` → `PartialFailureBanner` branch in the groups view and replace the `data ? … : 'Loading…'` ternary with explicit `isPending` / `isError` / data states.

### WR-08: WorkspacePane role select offers OWNER for any user (privilege escalation surface)

**File:** `frontend/src/components/settings/workspace-pane.tsx:119-124`
**Issue:** The per-row role `<select>` exposes an `OWNER` option for every non-self user, letting an owner promote arbitrary users to OWNER, while the Add-user form deliberately omits OWNER (`workspace-pane.tsx:425-428`). This inconsistency, combined with no confirmation on role change (PATCH fires immediately on `onChange` at line 117), makes accidental owner-promotion a one-misclick action. Backend enforces auth, but UX-layer guardrails for owner promotion are warranted given the blast radius.
**Fix:** Either remove `OWNER` from the per-row options (transfer-ownership should be a deliberate, confirmed flow) or gate the OWNER selection behind a ConfirmModal, consistent with the deactivate flow.

### WR-09: `handleRoleChange` does not optimistically guard against no-op / invalid transitions and leaves select desynced on failure

**File:** `frontend/src/components/settings/workspace-pane.tsx:240-252`
**Issue:** The role `<select>` is a controlled component bound to `u.role` from the query cache. `handleRoleChange` PATCHes then `refetchUsers()`. If the PATCH fails, the toast fires but the `<select>` already visually shows the new role (the change event updated the DOM value) until the refetch completes; if the refetch also fails the select stays on the wrong role with no rollback. There is also no guard against selecting the same role (fires a redundant PATCH).
**Fix:** Make the select value authoritative from cache and only commit on confirmed success (or invalidate the query so React Query re-derives the value), and early-return when `e.target.value === u.role`.

## Info

### IN-01: Copy violates project "no Please" rule

**File:** `frontend/src/components/cspm/microcopy.ts:32`
**Issue:** `error: 'Bulk action failed. Please try again.'` uses "Please", which CLAUDE.md / copy-voice.md explicitly forbids ("Don't compose generic SaaS copy ... 'Please...'").
**Fix:** Reword to peer-voice, e.g. `'Bulk action failed — try again.'`.

### IN-02: Connector add can submit empty credentials

**File:** `frontend/src/components/connectors/connector-form.tsx:142-153`
**Issue:** In add mode, `buildCredentials()` returns `undefined` when all fields are empty, and `handleSave` then sends `credentials: credentials ?? {}` — i.e. an empty object. There is no client-side validation that required fields are present, so the user can create a connector with no credentials and only learns of the failure via the backend error toast.
**Fix:** Disable the Save button (or show inline validation) until at least the required credential fields are non-empty.

### IN-03: Dead/redundant ternary renders identical branches

**File:** `frontend/src/components/settings/profile-pane.tsx:182`
**Issue:** `{idp_source ? idp_source : (isPending ? '—' : '—')}` — both branches of the inner ternary return `'—'`, so the `isPending` check is dead code.
**Fix:** Simplify to `{idp_source ?? '—'}`.

### IN-04: SMTP `use_starttls` / `use_tls` contract handled inconsistently

**File:** `frontend/src/components/settings/notifications-pane.tsx:81,130-137`; `frontend/src/lib/queries/use-tenant-settings.ts:53`
**Issue:** `defaultSmtp` reads TLS from `cfg.tls || cfg.use_tls`, the `SmtpConfig` type declares `tls` plus optional `use_starttls`, but the save payload only ever writes `tls`. The `use_starttls`/`use_tls` variants are read but never written, so a round-trip can drop the distinction the backend cares about. The checkbox label "Use TLS (port 465)" also conflates implicit TLS (465) with STARTTLS (587), which is misleading next to a free-text port field defaulting to 587.
**Fix:** Settle on a single canonical field name with the backend and write it back explicitly; clarify the label/port relationship.

### IN-05: Unused `isAdmin` in WorkspacePane / unused imports

**File:** `frontend/src/components/settings/workspace-pane.tsx:176,476`
**Issue:** `isAdmin` is computed but only used in the zero-users empty-state condition (`users.length === 0 && isAdmin`), which is reachable only when the admin-gated users fetch already succeeded — making the extra `isAdmin` guard effectively dead. Minor unused-logic smell.
**Fix:** Drop the redundant `isAdmin` guard on the empty state, or document why non-admins should not see "No users found".

### IN-06: `formatRelativeDate` produces negative durations for future timestamps

**File:** `frontend/src/components/settings/profile-pane.tsx:32-47`, `frontend/src/components/connectors/connector-card.tsx:20-33`, `frontend/src/components/settings/audit-log-pane.tsx:34-48`
**Issue:** All three relative-time helpers compute `Date.now() - timestamp` with no guard for future timestamps (clock skew between server and client is common). A `last_sync_at` or `last_login_at` slightly in the future renders as `-1m ago` / `Synced -1m ago`. Three near-identical implementations also duplicate logic.
**Fix:** Clamp negative diffs to "just now" and extract a single shared `formatRelative` util.

---

_Reviewed: 2026-06-03T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
