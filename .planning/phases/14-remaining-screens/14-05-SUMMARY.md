---
phase: 14-remaining-screens
plan: "05"
subsystem: frontend/settings
tags: [settings, sidebar-of-categories, rbac, dirty-state, saml, audit-log, tdd]
dependency_graph:
  requires:
    - "14-00: queryKeys.settings, ConfirmModal (sunset-restyled)"
    - "14-01: SettingsSidebarShell, SaveBar, useDirtyState, microcopy.ts"
  provides:
    - "use-tenant-settings.ts: useTenantSettings + useUpdateTenantSettings"
    - "use-tenant-users.ts: useTenantUsers + useChangePassword"
    - "use-audit-log.ts: useAuditLog"
    - "profile-pane.tsx: ProfilePane (identity + change-password, SSO-aware)"
    - "saml-pane.tsx: SamlPane (provider-first, gated enforce toggle)"
    - "workspace-pane.tsx: WorkspacePane (Owner-gated accounts + settings)"
    - "notifications-pane.tsx: NotificationsPane (3 cards, one pane)"
    - "audit-log-pane.tsx: AuditLogPane (filtered paginated table)"
    - "api-tokens-pane.tsx: ApiTokensPane (coming-soon placeholder)"
    - "settings/page.tsx: full rewrite — SettingsSidebarShell + 6 panes + unsaved guard"
  affects:
    - "/dashboard/settings route: v1 4-tab layout fully replaced"
tech_stack:
  added: []
  patterns:
    - "TDD RED/GREEN for all 3 tasks"
    - "paneDirtyRef + onClickCapture pattern for page-level dirty detection without prop drilling"
    - "DOM-inspection dirty bridge: document.querySelector('[data-save-bar]') detects pane dirtiness at navigation time"
    - "SMTP password sentinel T-14-17: omit password from PATCH when value equals 8-bullet mask"
    - "Profile sourcing finding #4: useTenantUsers filtered by email for idp_source + last_login_at"
key_files:
  created:
    - frontend/src/lib/queries/use-tenant-settings.ts
    - frontend/src/lib/queries/use-tenant-settings.test.ts
    - frontend/src/lib/queries/use-tenant-users.ts
    - frontend/src/lib/queries/use-audit-log.ts
    - frontend/src/components/settings/profile-pane.tsx
    - frontend/src/components/settings/profile-pane.test.tsx
    - frontend/src/components/settings/saml-pane.tsx
    - frontend/src/components/settings/saml-pane.test.tsx
    - frontend/src/components/settings/workspace-pane.tsx
    - frontend/src/components/settings/notifications-pane.tsx
    - frontend/src/components/settings/audit-log-pane.tsx
    - frontend/src/components/settings/audit-log-pane.test.tsx
    - frontend/src/components/settings/api-tokens-pane.tsx
    - frontend/src/app/(authed)/dashboard/settings/page.test.tsx
  modified:
    - frontend/src/app/(authed)/dashboard/settings/page.tsx
decisions:
  - "paneDirtyRef (ref not state) used for page-level dirty flag so handleCategoryChange reads the latest value synchronously without stale closure issues"
  - "PaneWithDirtyBridge uses onClickCapture at the page level (not pane level) so any DOM click first refreshes the dirty ref before the category-change handler fires"
  - "Profile pane reads idp_source + last_login_at from useTenantUsers() filtered by email (finding #4 / Pitfall 6 — /auth/me lacks these fields)"
  - "SamlPane: disabled Enforce SSO toggle shows inline explainer; LOCAL-from-non-LOCAL triggers amber warning via isDirty + settings baseline check"
  - "NotificationsPane: Alert categories card renders coming-soon EmptyState (Open Question #2 resolved — no backend field exists)"
  - "SMTP password sentinel: password key omitted from PATCH body when value equals 8-bullet mask (T-14-17)"
  - "WorkspacePane allows deviation: UserRow is a local subcomponent (not a split file) — stays under ~100 lines with clear separation"
metrics:
  duration: "~147 minutes"
  completed_date: "2026-06-03"
  tasks_completed: 3
  files_created: 14
  files_modified: 1
  tests_added: 36
---

# Phase 14 Plan 05: Settings Page Rebuild Summary

Rebuilt `/dashboard/settings` (UX-06-04): 6-category sidebar-of-categories layout replacing v1's horizontal-tab mess. All 6 RBAC-gated panes, per-category dirty-state save bar, unsaved-changes guard on dirty category switch, and the hard grep gate (zero tab patterns in settings/).

## One-liner

6-pane settings sidebar (profile/workspace/saml/notifications/api-tokens/audit) with RBAC gating via SettingsSidebarShell, TanStack hooks for tenant settings/users/audit-log, per-category SaveBar dirty-state, unsaved-changes ConfirmModal guard, and zero horizontal-tab patterns; 36 tests green.

## What Was Built

### Task 1: Settings hooks + ProfilePane + SamlPane (`4a545ae`)

**Hooks created:**

`use-tenant-settings.ts`:
- `useTenantSettings()` — GET /tenant/settings (Admin-gated, staleTime 60s)
- `useUpdateTenantSettings()` — PATCH /tenant/settings (Owner-gated); onSuccess invalidates settings.tenant + toasts "Settings updated."; onError toasts error (403 → "You don't have permission…")

`use-tenant-users.ts`:
- `useTenantUsers()` — GET /tenant/users (Admin-gated); provides full UserResponse[] with allow_password_login, idp_source, last_login_at
- `useChangePassword()` — POST /auth/change-password; toasts success/error

**ProfilePane** (`data-pane="profile"`):
- Identity card: display_name/email(mono)/role/tenant_name from useAuth().user
- idp_source + last_login_at from useTenantUsers() filtered by user.email (finding #4 / Pitfall 6)
- Change Password form: HIDDEN when allow_password_login===false (SSO-only accounts per D-SET-06)
- State patterns: SkeletonTable loading, PartialFailureBanner error

**SamlPane** (`data-pane="saml"`):
- Provider-first picker: LOCAL / GOOGLE / AZURE buttons (aria-pressed)
- Enforce SSO toggle: `role="switch"`, DISABLED with inline explainer when idp_provider==='LOCAL' (D-SET-07)
- LOCAL selection: forces sso_enforced=false in local state + shows amber warning when switching from non-LOCAL
- Seeded from useTenantSettings() via useDirtyState; commits via SaveBar → useUpdateTenantSettings

### Task 2: Workspace + Notifications + Audit log + API tokens panes (`f3b0372`)

**`use-audit-log.ts`**:
- `useAuditLog(opts)` — GET /tenant/audit-log with action/resource_type/user_email/page params; page_size=50; placeholderData keepPreviousData pattern

**WorkspacePane** (`data-pane="workspace"`):
- User list: Avatar + display_name + email(mono) + role (select for Owner, pill for non-Owner) + active badge
- Owner-gated controls: Add user form (POST /tenant/users), per-row role change (PATCH .../role), deactivate (PATCH .../deactivate) guarded by ConfirmModal warning variant
- Workspace settings (domain/timezone) editable via SaveBar → useUpdateTenantSettings

**NotificationsPane** (`data-pane="notifications"`):
- 3 section cards in ONE scrollable pane (no nested tabs — D-SET-08)
- Card 1: Email/SMTP — host/port/username/password(sentinel T-14-17)/from_email/tls/enabled toggle
- Card 2: Syslog forwarding — enabled/host/port/protocol/facility
- Card 3: Alert categories — coming-soon EmptyState (Open Question #2 resolved)
- Single SaveBar across all three sections → useUpdateTenantSettings({ smtp_config, syslog_config })

**AuditLogPane** (`data-pane="audit"`):
- Filter inputs: action (select) / resource_type (select) / user_email (text) → debounced via state
- Read-only table: actor(Avatar+email mono) · action(mono) · target(resource_type/resource_id mono) · timestamp(relative)
- State patterns: SkeletonTable loading, EmptyState "No audit events match these filters", PartialFailureBanner error
- Pagination: next/prev controls with page_size=50

**ApiTokensPane** (`data-pane="api-tokens"`):
- EmptyState "Personal API tokens are coming soon." — no create button (D-SET-02)

### Task 3: Settings page composition + grep gate (`f4810c1`)

**`/dashboard/settings/page.tsx`** — full rewrite (1350 lines deleted, 208 lines new):
- `useUrlState('category', CATEGORY_ALLOW_LIST, 'profile')` — URL-driven active category (T-14-20 allow-list clamp)
- `SettingsSidebarShell` wraps all 6 panes; shell computes visibleCategories from useAuth().role internally
- `paneDirtyRef` (useRef, not useState) for synchronous dirty reads in closure-based handlers
- `handlePageClick` (onClickCapture at page root): refreshes paneDirtyRef before any click propagates
- Unsaved-changes guard (D-SET-04): ConfirmModal with UNSAVED_GUARD copy, "Discard"/"Stay" labels
- `PaneWithDirtyBridge`: wrapper for editable panes (saml/workspace/notifications) that schedules dirty-check after interaction

**SUCCESS CRITERION #5 GREP GATE**: zero `border-b-2`, `border-b border-indigo`, `role="tab"` in all 7 settings implementation files (v1's `["general","auth","users","audit"].map(t => ...)` with `border-b-2 border-indigo-500` fully deleted).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Tests used `findByText` with duplicate text matches in SAML pane**
- **Found during:** Task 1 GREEN phase (saml-pane.test.tsx)
- **Issue:** SamlPane renders "Enforce SSO" twice: as an `<h2>` section heading AND as a `<p>` toggle label, causing RTL `findByText(/Enforce SSO/i)` to throw "Found multiple elements"
- **Fix:** Updated tests to use `findAllByText` and targeted `getByRole('switch', { name: /Enforce SSO/i })` for the toggle button
- **Files modified:** `saml-pane.test.tsx`
- **Commit:** same task commit

**2. [Rule 1 - Bug] SamlPane LOCAL warning condition was always true initially**
- **Found during:** Task 1 GREEN phase
- **Issue:** Warning "Switching to local sign-in turns SSO enforcement off." used `isLocalProvider && values.idp_provider === 'LOCAL'` which is redundant and would show on initial render (pane defaults to LOCAL before settings load)
- **Fix:** Changed condition to `isLocalProvider && isDirty && settings?.idp_provider !== 'LOCAL'` — only shows when user actively changed TO local FROM a non-local provider
- **Files modified:** `saml-pane.tsx`
- **Commit:** same task commit

**3. [Rule 1 - Bug] Tests used findByText with duplicate matches in audit log / workspace / notifications panes**
- **Found during:** Task 2 GREEN phase (audit-log-pane.test.tsx)
- **Issue:** Multiple RTL queries matched ambiguous text: `/user/i` in audit table (matches resource type, action, and column headers), `/SMTP|Email/i` in notifications (matches heading and field label), `'member@example.com'` in workspace (appears in both name column and email column)
- **Fix:** Changed to `findAllByText`, `getByRole('heading', { name: ... })`, and `findAllByText` with `.length > 0` assertion
- **Files modified:** `audit-log-pane.test.tsx`
- **Commit:** same task commit

**4. [Rule 1 - Bug] Page-level dirty detection relied on microtask timing — SaveBar not yet rendered**
- **Found during:** Task 3 GREEN phase (page.test.tsx)
- **Issue:** `PaneWithDirtyBridge` fired `checkDirty` via `queueMicrotask` after a user click, but React's state update (rendering the SaveBar) hadn't flushed before the microtask ran, so `paneDirtyRef.current` stayed false
- **Fix:** Moved dirty-detection to a page-root `onClickCapture` handler (`handlePageClick`) that fires BEFORE any child's click event propagates — at this point the SaveBar IS rendered (from a previous interaction) so the DOM check is correct
- **Files modified:** `page.tsx`
- **Commit:** same task commit

**5. [Rule 1 - Bug] Guard test used `queryByText` with multiple matching elements**
- **Found during:** Task 3 GREEN phase (page.test.tsx)
- **Issue:** ConfirmModal renders title "Unsaved changes" AND message body containing "You have unsaved changes. Discard them and switch?" — both match `/unsaved changes|discard/i`, causing `queryByText` to throw "Found multiple elements"
- **Fix:** Changed to `queryAllByText(...).length > 0`
- **Files modified:** `page.test.tsx`
- **Commit:** same task commit

## Known Stubs

**ApiTokensPane**: "Personal API tokens are coming soon." — intentional per D-SET-02. No backend endpoint exists. No future plan has been assigned to resolve this yet; it is a tracked placeholder.

**NotificationsPane Alert categories card**: "Alert category configuration coming soon" — intentional per Open Question #2 resolution (no backend field). Placeholder until a `/tenant/settings` alert_categories field is added.

## Threat Flags

No new threat surface beyond the plan's threat model. All threats in T-14-16 through T-14-20 were handled:

| T-ID | Mitigation implemented |
|------|------------------------|
| T-14-16 | RBAC sidebar gating (UX) + PartialFailureBanner on 403 (backend authoritative) |
| T-14-17 | SMTP password sentinel: password omitted from PATCH when unchanged (8-bullet mask) |
| T-14-18 | Enforce SSO toggle disabled for LOCAL; LOCAL auto-forces sso_enforced=false in local state |
| T-14-19 | AuditLogPane renders only API-returned rows; backend WHERE tenant_id scopes cross-tenant |
| T-14-20 | useUrlState allow-list clamps ?category= to known 6-category union; defaults to 'profile' |

## TDD Gate Compliance

All 3 tasks followed RED/GREEN:
- Task 1: RED (files don't exist → 3 test files fail) → GREEN (`4a545ae`)
- Task 2: RED (files don't exist → test file fails) → GREEN (`f3b0372`)
- Task 3: RED (page.test.tsx fails with import error) → GREEN (`f4810c1`)

## Self-Check

### Files exist:
- FOUND: `frontend/src/lib/queries/use-tenant-settings.ts`
- FOUND: `frontend/src/lib/queries/use-tenant-settings.test.ts`
- FOUND: `frontend/src/lib/queries/use-tenant-users.ts`
- FOUND: `frontend/src/lib/queries/use-audit-log.ts`
- FOUND: `frontend/src/components/settings/profile-pane.tsx`
- FOUND: `frontend/src/components/settings/profile-pane.test.tsx`
- FOUND: `frontend/src/components/settings/saml-pane.tsx`
- FOUND: `frontend/src/components/settings/saml-pane.test.tsx`
- FOUND: `frontend/src/components/settings/workspace-pane.tsx`
- FOUND: `frontend/src/components/settings/notifications-pane.tsx`
- FOUND: `frontend/src/components/settings/audit-log-pane.tsx`
- FOUND: `frontend/src/components/settings/audit-log-pane.test.tsx`
- FOUND: `frontend/src/components/settings/api-tokens-pane.tsx`
- FOUND: `frontend/src/app/(authed)/dashboard/settings/page.tsx`
- FOUND: `frontend/src/app/(authed)/dashboard/settings/page.test.tsx`

### Commits exist:
- `4a545ae` — Task 1 settings/users hooks + ProfilePane + SamlPane — FOUND
- `f3b0372` — Task 2 Workspace + Notifications + Audit log + API tokens — FOUND
- `f4810c1` — Task 3 Settings page composition + grep gate — FOUND

### Tests: 36/36 passing across 7 test files.

### Grep gate: zero `border-b-2`/`border-b border-indigo`/`role="tab"` in all 7 settings implementation files.

## Self-Check: PASSED
