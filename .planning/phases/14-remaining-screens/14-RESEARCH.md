# Phase 14: Remaining Screens — Research

**Researched:** 2026-06-02
**Domain:** Frontend integration — CSPM, Connectors, Users directory, Settings rebuilt against Phase 11–13 primitives
**Confidence:** HIGH (primary research is codebase reading of exact source; minimal assumptions)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Connectors (D-CONN):**
- D-CONN-01: Gradient marks for all 14 providers — add 11 new `--gradient-provider-*` CSS tokens for CrowdStrike, Nessus, Defender, Wiz, Qualys, Rapid7, Google Workspace, Azure Entra, Okta, Jamf, Intune, Humaans. Hex lives once in `globals.css`. `<ProviderMark>` reads `var(--gradient-provider-{type})`.
- D-CONN-02: New-connector flow is a functional, sunset-restyled form (NOT a thin placeholder). Add/edit/test/sync/delete stay fully wired. Basic functionality loses nothing vs v1.
- D-CONN-03: Category-sectioned card grid — Vulnerability scanners / Identity / MDM / Ticketing sections.
- D-CONN-04: Masked + sentinel passthrough for credentials. Edit form shows `••••••`; untouched field sends sentinel; typing replaces it. Eye/EyeOff reveal only on active entry.
- D-CONN-05: 4-state status pill (ok/green, failed/red, never-synced/gray, running/amber animated) driven by `last_sync_status`. Reuse Phase 11 `PerSourceStatusStrip` for live sync feedback. `last_sync_at` + `last_sync_record_count` as card metadata.
- D-CONN-06: Enable/disable toggle (via `is_enabled`) + delete guarded by `ConfirmModal`. Delete gated Owner/Admin. Disable is low-risk default; delete is escape hatch.
- D-CONN-07: Per-category empty-states + inbound deep-link handling. Page reads `?provider=<x>` from `/tickets` (Phase 13 D-S-02) to pre-open/scroll add flow.

**Settings (D-SET):**
- D-SET-01: Sidebar-of-categories, 6 categories: Profile · Workspace · SAML/OIDC · Notifications · API tokens · Audit log. No horizontal tabs anywhere.
- D-SET-02: API tokens = coming-soon placeholder. `EmptyState` ("Personal API tokens are coming soon").
- D-SET-03: Login-account + RBAC management under Workspace category. `/tenant/users` (Owner/Admin-gated). `/dashboard/users` stays people directory.
- D-SET-04: Per-category sticky save bar with dirty-state tracking. Unsaved-changes guard on category switch.
- D-SET-05: RBAC gating hides categories below the current role. Profile always; Workspace / SAML-OIDC / Notifications / Audit gated Admin/Owner.
- D-SET-06: Profile pane = read-only identity (name, email, role, tenant, IdP source, last login from `/auth/me`) + Change Password form (`/change-password`, hidden for SSO-only accounts).
- D-SET-07: SAML/OIDC pane provider-first — IdP picker (Google/Azure/LOCAL); "Enforce SSO" toggle disabled until non-LOCAL. LOCAL auto-disables enforcement.
- D-SET-08: Notifications = three labeled sub-sections in one scrollable pane. Email/SMTP · Syslog forwarding · Alert categories. No nested tabs.
- D-SET-09: Audit log pane = filtered + paginated read-only table. Rows: actor + action + target + timestamp. Filters: action, resource_type, user_email. Server pagination page_size 50.
- D-SET-10: Settings mobile (<900px) = category list → pane drill (master-detail).

**Users directory (D-USR):**
- D-USR-01: `/dashboard/users` is the people DIRECTORY from `/api/v1/users/directory`. "role pill" maps to job-title/department chip; "IdP-source pill" maps to `idp_source`.
- D-USR-02: Export-only bulk bar via `ExportButton`. Writable RBAC actions live under Workspace settings.
- D-USR-03: Directory and Groups as segmented toggle (NOT tabs). Groups list reusing `ChipBar`/state primitives. Backed by `/tenant/groups` + `/groups/export`.

**CSPM (D-CSPM):**
- D-CSPM-01: Reuse generalized `<DrillPanel>` with `idKey='finding'`, URL `?finding=...&open=drill`. Mirror the `ticket` slot pattern.
- D-CSPM-02: Cloud segmented control (All/AWS/Azure/GCP from `/cspm/stats` `by_cloud_provider`) + compliance frameworks rail above finding list.
- D-CSPM-03: `BulkActionBar` for Resolve/Ignore/Reopen via `/cspm/bulk-status`. Finding card: cloud provider gradient mark + severity glyph + resource_id mono + title + framework tags + status pill.
- D-CSPM-04: Defer trend charts (UX-D-05).

**Cross-cutting (D-X):**
- D-X-01: Every screen state-pattern compliant: loading (SkeletonTable + chip-bar skeleton), empty (EmptyState), partial-failure (PartialFailureBanner), toast (useToast/ToastProvider).
- D-X-02: snake_case frontend↔backend, no camelCase transform shim.

**Plan sequencing (D-SEQ):**
- D-SEQ-01: Foundation-first. Wave 0: 11 new provider gradient tokens + new primitives (connector card, finding card, settings sidebar shell, per-category save bar, sync status pill). Four screens parallelizable after Wave 0.

### Claude's Discretion
- Exact primitive APIs and file placement (follow Phase 11–13 conventions + sketch-findings references).
- Whether the connectors category-section also gets a chip-filter.
- Notification "Alert categories" field shape — map to whatever existing tenant-settings payload exposes.
- Skeleton/shimmer specifics per `state-patterns.md`.

### Deferred Ideas (OUT OF SCOPE)
- Full connector onboarding wizard (UX-D-02)
- API token issuance (D-SET-02: placeholder only)
- CSPM trend charts (UX-D-05 / D-CSPM-04)
- Self-serve display-name editing (no self endpoint)
- Formal mobile/a11y/perf audit (Phase 15)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UX-06-01 | `/dashboard/cspm` rebuilt — chip-bar + side-panel for findings + compliance frameworks list + cloud-segmented top control + finding cards | `DrillPanel` (idKey='finding'), `ChipBar` axes, CSPM endpoint shapes documented below |
| UX-06-02 | `/dashboard/connectors` rebuilt — connector cards with provider mark + last-sync + status pill + actions | `ConnectorConfigResponse` fields, 14 provider token map, sentinel pattern documented |
| UX-06-03 | `/dashboard/users` rebuilt — list with IdP-source pill + bulk actions + role pills | `/users/directory` response shape, `ExportButton` API, `TicketBulkBar` pattern documented |
| UX-06-04 | `/dashboard/settings` rebuilt — sidebar-of-categories pattern; old tabbed layout fully replaced | `/tenant/settings` shape, `/auth/me`, role hierarchy, `ConfirmModal` API documented |
</phase_requirements>

---

## Summary

Phase 14 is a pure integration phase: it consumes the complete primitive library shipped in Phases 11–13 and applies it to the four remaining v1 screens. No backend changes are required. The planner's primary job is sequencing Wave 0 (new tokens + new primitives) before the four parallelizable screen rewrites. This research documents the exact ground truth the planner needs: verified prop signatures, endpoint shapes, token locations, and the current state of each v1 screen being replaced.

The four v1 screens are each full-page components using raw Tailwind palette utilities (`gray-800`, `indigo-500`, etc.), inline `useState`/`useEffect` data fetching (no TanStack Query), and horizontal tabs. They are full rewrites — delete the v1 surface after the sunset component is live.

Settings is the most complex: it has 6 categories, RBAC-gated sidebar, a dirty-state save bar, a masked-credential contract, and must pass the hard grep gate (`grep -r "tab" frontend/src/app/dashboard/settings/` returns zero horizontal-tab usages). CSPM is the most structurally new, adding a `finding` content slot to the generalized `DrillPanel`.

**Primary recommendation:** Wave 0 first (tokens → provider mark extension → new shared primitives), then four screens in parallel plans consuming those primitives. The settings pane shell is the most reusable Wave 0 output — extract it before writing any category pane.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Provider gradient tokens | Browser/Client CSS | — | CSS vars consumed at render; no server involvement |
| Connector card + sync status pill | Frontend Client Component | API (GET /connectors) | Card is pure UI; sync trigger POST calls backend |
| CSPM finding drill | Frontend Client (DrillPanel) | API (GET /cspm/{id}) | DrillPanel chrome handles URL state; content fetches on open |
| Settings category routing | Frontend Client (URL-state) | API (GET+PATCH /tenant/settings) | Sidebar/pane split is pure client routing |
| RBAC sidebar gating | Frontend Client (useAuth role check) | Backend (403 on restricted endpoints) | Defense-in-depth: hide category + backend enforces |
| Export (users/groups) | Browser (ExportButton) | API (GET /export/) | ExportButton triggers a CSV blob download |
| Dirty-state save bar | Frontend Client Component | API (PATCH /tenant/settings) | Dirty state is local component state; save triggers PATCH |
| Audit log table | Frontend Client Component | API (GET /tenant/audit-log) | Paginated read-only fetch |

---

## Standard Stack

### Core (all inherited from Phases 11–13; verified by reading source)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| TanStack Query v5 | `^5.x` | Data fetching + cache invalidation | Phase 10 D-D-01 — milestone-wide; all hooks use this pattern [VERIFIED: grep of package.json] |
| Next.js App Router | 15 | Routing + Server Components shell | Project standard; all authed screens are Client Components under `(authed)/` layout [VERIFIED: codebase] |
| Tailwind CSS | 3.4 | Utility tokens mapped to CSS vars | Phase 9 token discipline; no raw palette utilities allowed [VERIFIED: tailwind.config.ts] |
| vaul | `^1.x` | Mobile bottom-sheet for DrillPanel | Phase 11 D-P-03 pin; already in deps [VERIFIED: drill-panel-mobile.tsx imports vaul] |

### Supporting (all pre-existing; no new installs for Phase 14)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `lucide-react` | existing | Icons | Used across all components; no new icons needed |
| `@tanstack/react-query` | v5 | Query client + devtools | Already in package.json |

**Installation:** No new dependencies. Phase 14 is an integration phase — zero new packages.

---

## Exact Primitive APIs (VERIFIED by reading source)

### `SkeletonTable`
**File:** `frontend/src/components/states/skeleton-table.tsx`

```typescript
// [VERIFIED: frontend/src/components/states/skeleton-table.tsx]
export type SkeletonColumnKind = 'pill' | 'mono' | 'text' | 'badge';
export type SkeletonColumn = { kind: SkeletonColumnKind; width: number };

type Props = { rows?: number; columns: SkeletonColumn[]; className?: string };

// Usage:
<SkeletonTable
  rows={8}
  columns={[
    { kind: 'pill', width: 80 },
    { kind: 'mono', width: 130 },
    { kind: 'text', width: 200 },
  ]}
/>
```

- `rows` defaults to 8
- `columns` is required — describes shape of the real table per screen
- Test contract: rows carry `data-skeleton-row`, cells carry `data-skeleton-cell`
- Animate: `motion-safe:animate-shimmer` (reduced-motion strips animation, gradient remains)

---

### `EmptyState`
**File:** `frontend/src/components/states/empty-state.tsx`

```typescript
// [VERIFIED: frontend/src/components/states/empty-state.tsx]
// Compound subcomponent pattern (Phase 11 D-S-02):
<EmptyState className?={string}>
  <EmptyState.Title>No connectors yet</EmptyState.Title>
  <EmptyState.Body>Add a connector to start aggregating findings.</EmptyState.Body>
  <EmptyState.Actions>
    <button>Add connector</button>
    <button>View docs</button>
  </EmptyState.Actions>
  <EmptyState.Suggestion>
    💡 Tip: Start with a vulnerability scanner.
  </EmptyState.Suggestion>
</EmptyState>
```

- `role="status"` + `aria-live="polite"` are baked in — do not add again
- `EmptyState.Suggestion` is optional (violet lightbulb style)
- All sub-components accept `className` and `...HTMLAttributes`
- Import from `@/components/states`

---

### `PartialFailureBanner`
**File:** `frontend/src/components/states/partial-failure-banner.tsx`

```typescript
// [VERIFIED: frontend/src/components/states/partial-failure-banner.tsx]
export type PartialFailureBannerProps = {
  watchKeys?: readonly QueryKey[];   // hook mode (default): watches TanStack cache
  errors?: ReadonlyArray<{           // props mode: bypasses TanStack
    code: number | string;
    requestId: string;
    message?: string;
  }>;
  onRetry?: () => void;
  source?: string;   // connector name shown in copy, e.g. "Tenable"
  className?: string;
};

// Hook mode (preferred for list pages):
<PartialFailureBanner
  watchKeys={[queryKeys.cspm.list(filters), queryKeys.cspm.stats()]}
  onRetry={refetch}
/>

// Props mode (for targeted single-query failure):
<PartialFailureBanner
  errors={[{ code: 503, requestId: 'abc123', message: 'Upstream timeout' }]}
  source="CrowdStrike"
  onRetry={handleRetry}
/>
```

- `role="alert"` is baked in
- Amber, not red — partial failure = degraded, not down
- Renders nothing when `rows.length === 0`

---

### `PerSourceStatusStrip`
**File:** `frontend/src/components/states/per-source-status-strip.tsx`

```typescript
// [VERIFIED: frontend/src/components/states/per-source-status-strip.tsx]
type Props = {
  facets: Record<string, number>;  // { connectorTypeName: count }
  className?: string;
};

// Usage:
<PerSourceStatusStrip facets={{ CROWDSTRIKE: 287, WIZ: 144 }} />
```

- Internally calls `useConnectors()` — must be inside `QueryClientProvider`
- Returns `null` if connectors are pending or errored (silent)
- Status classes: `ok` → success-soft/success, `failed` → danger-soft/danger, `syncing` → pink-soft/pink, default → surface-2/text-muted
- Test contract: chips carry `data-status-chip`; connector type name in `.font-mono` span

---

### `DrillPanel` (desktop) + Adding a New Content Slot
**File:** `frontend/src/components/vulnerabilities/drill-panel.tsx`

```typescript
// [VERIFIED: frontend/src/components/vulnerabilities/drill-panel.tsx]
type Props = {
  cveId?: string | null;        // back-compat alias for vuln callers
  id?: string | null;           // generic entity id (takes precedence over cveId)
  idKey?: string;               // URL param key; defaults to 'cve'
  renderContent?: (args: { id: string; onClose: () => void }) => React.ReactNode;
  ariaLabel?: string;           // defaults to 'Vulnerability detail'
  originRowRef?: React.RefObject<HTMLElement | null> | null;
};
```

**To add the CSPM `finding` content slot** (mirror of the `ticket` slot pattern in Phase 13):

```typescript
// [ASSUMED: pattern mirrors Phase 13 D-D-02 — ticket slot]
// New file: frontend/src/components/cspm/finding-drill-content.tsx
// (same dir pattern as ticket-drill-content.tsx)

// In the CSPM page:
<DrillPanel
  id={selectedFindingId}
  idKey="finding"            // URL: ?finding=<id>&open=drill
  ariaLabel="Finding detail"
  renderContent={({ id, onClose }) => (
    <FindingDrillContent findingId={id} onClose={onClose} />
  )}
  originRowRef={originRowRef}
/>
```

- `DrillPanel` is `position: fixed; right: 0; top: 0; z-30; h-full; w-[420px]`
- `isOpen` is URL-driven: `params.get('open') === 'drill' && effectiveId !== null`
- Close removes both `?open` and `?{idKey}` from URL atomically
- Esc, ×, outside-click all close (three of D-P-01's four close paths)
- Row-swap: caller updates the URL `?finding=<newId>` — panel re-renders with new content

**DrillPanelMobile:** `frontend/src/components/vulnerabilities/drill-panel-mobile.tsx` — vaul bottom sheet, same idKey pattern.

---

### `ChipBar` (generic descriptor-driven)
**File:** `frontend/src/components/ui/ChipBar.tsx`

```typescript
// [VERIFIED: frontend/src/components/ui/ChipBar.tsx]

export type ChipDescriptor = {
  value: string;              // URL value (must be in allowList)
  label: string;
  glyph?: string;             // e.g. '■' for severity
  glyphClassName?: string;
};

export type ChipAxis = {
  key: string;                // URL key, e.g. 'severity', 'cloud_provider'
  label?: string;             // optional group label before chips
  allowList: readonly string[];  // REQUIRED — XSS clamp (T-12-05)
  counts?: Record<string, number>;
  chips?: ChipDescriptor[];   // explicit chip set
  derivedFromCounts?: boolean; // derive chip set from Object.keys(counts)
};

export type ChipBarProps = {
  axes: ChipAxis[];
  savedFilter?: { label: string; query: string } | null;
  showSearch?: boolean;       // default true
  searchPlaceholder?: string; // default 'Search…'
  searchAriaLabel?: string;
};
```

**CSPM axes example:**
```typescript
const CSPM_AXES: ChipAxis[] = [
  {
    key: 'severity',
    allowList: ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] as const,
    chips: [
      { value: 'CRITICAL', label: 'Critical', glyph: '■', glyphClassName: 'text-severity-critical' },
      { value: 'HIGH',     label: 'High',     glyph: '▲', glyphClassName: 'text-severity-high' },
      { value: 'MEDIUM',   label: 'Medium',   glyph: '◆', glyphClassName: 'text-severity-medium' },
      { value: 'LOW',      label: 'Low',      glyph: '○', glyphClassName: 'text-severity-low' },
    ],
  },
  {
    key: 'status',
    allowList: ['OPEN', 'IN_PROGRESS', 'REMEDIATED', 'SUPPRESSED'] as const,
    chips: [/* ... */],
  },
];
```

- `data-chip-bar="generic"` attribute on container (test hook)
- `data-axis={axis.key}` on chip groups
- `data-saved-filter-pill` on the saved filter button
- 250ms search debounce, immediate chip toggle (D-F-01)

---

### `ConfirmModal`
**File:** `frontend/src/components/ui/ConfirmModal.tsx`

```typescript
// [VERIFIED: frontend/src/components/ui/ConfirmModal.tsx]
// NOTE: uses v1 dark CSS (gray-*/indigo-*) — needs sunset restyling in Phase 14 Wave 0
interface ConfirmModalProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;   // default "Confirm"
  cancelLabel?: string;    // default "Cancel"
  variant?: 'danger' | 'warning' | 'info';  // affects confirm button color
  onConfirm: () => void;
  onCancel: () => void;
}
```

**Important:** `ConfirmModal` still uses v1 raw palette utilities (`gray-800`, `gray-900`, `red-600`, etc.). The planner should include a Wave 0 task to restyle it with sunset tokens before Phase 14 screens use it — otherwise the modal will visually clash.

---

### `useToast` / `ToastProvider`
**File:** `frontend/src/components/ui/ToastProvider.tsx`

```typescript
// [VERIFIED: frontend/src/components/ui/ToastProvider.tsx]
interface ToastInput {
  title?: string;
  message: string;
  variant?: 'success' | 'error' | 'info';
  duration?: number;    // ms; default 3000 in Toast.tsx
  action?: ToastAction; // { label: string; onClick: () => void }
}

// Usage:
const { toast } = useToast();
toast({ variant: 'success', message: 'Connector deleted.' });
toast({ variant: 'error', title: 'Sync Failed', message: error.message });
toast({ variant: 'info', message: 'Syncing…', duration: 6000 });
```

- `ToastProvider` is already mounted in the app root layout — callers just call `useToast()`.
- Container is `fixed top-4 right-4 z-[60]` — above DrillPanel (z-30) and modals (z-50).

---

### `ExportButton`
**File:** `frontend/src/components/ui/ExportButton.tsx`

```typescript
// [VERIFIED: frontend/src/components/ui/ExportButton.tsx]
// NOTE: uses v1 styling (gray-700 border, gray-300 text) — needs sunset restyle in Wave 0
interface Props {
  resource: string;   // maps to /api/v1/export/{resource}
  label?: string;     // default "Export CSV"
  filters?: Record<string, string | string[] | boolean>;
}

// Usage — users export:
<ExportButton resource="users" label="Export selected" filters={{ ids: selectedIds }} />

// Groups export:
<ExportButton resource="groups" label="Export groups" />
```

**Important:** `ExportButton` uses localStorage-based auth token (pre-TanStack pattern). It should work as-is; the planner should note it has not been migrated to TanStack auth headers. Do not refactor in Phase 14 — use as-is, restyle only.

---

### `ProviderMark` (existing + extension for 14 providers)
**File:** `frontend/src/components/tickets/provider-mark.tsx`

```typescript
// [VERIFIED: frontend/src/components/tickets/provider-mark.tsx]
// Current: 3 providers (jira, asana, github) — TicketProvider type
export type ProviderMarkProps = {
  provider: TicketProvider;  // currently: 'jira' | 'asana' | 'github'
  className?: string;
};
```

**Extension plan for Phase 14 (D-CONN-01):**
The `TicketProvider` type in `frontend/src/components/tickets/types.ts` is currently:
```typescript
export type TicketProvider = 'jira' | 'asana' | 'github';
```

For connectors, a new broader type is needed:
```typescript
// New: frontend/src/components/connectors/types.ts (or extend tickets/types.ts)
export type ConnectorProvider =
  | 'crowdstrike' | 'nessus' | 'defender' | 'wiz' | 'qualys' | 'rapid7'
  | 'google_workspace' | 'azure_entra_id' | 'okta' | 'jamf' | 'intune' | 'humaans'
  | 'jira' | 'asana' | 'github';
```

A new `<ConnectorMark provider={ConnectorProvider} />` component at `frontend/src/components/connectors/connector-mark.tsx` should extend the same pattern (literal lookup object, no string interpolation) to all 14 providers. The existing `ProviderMark` stays unchanged for tickets.

---

### `TicketBulkBar` pattern (template for CSPM and Users bulk bars)
**File:** `frontend/src/components/tickets/ticket-bulk-bar.tsx`

```typescript
// [VERIFIED: frontend/src/components/tickets/ticket-bulk-bar.tsx]
export type TicketBulkBarProps = {
  selectedCount: number;
  onBulkAction: (action: BulkAction, blockedReason?: string | null) => void;
  onClearSelection: () => void;
  isPending?: boolean;
};
```

The bulk bar pattern for Phase 14:
- **CSPM bulk bar:** `<CspmBulkBar selectedCount={n} onBulkAction={fn} .../>` with actions: Resolve / Ignore / Reopen → calls `POST /api/v1/cspm/bulk-status`
- **Users export bulk bar:** Much simpler — just an "Export selected" button (no ConfirmModal needed for CSV export)

Both follow the same bottom-anchored `fixed inset-x-0 bottom-0 z-30` pattern with `animate-in slide-in-from-bottom-2`.

---

### `ReassignCombobox` / Inline-edit pattern (template for save-bar / toggle interactions)
**File:** `frontend/src/components/assets/reassign-combobox.tsx`

The inline-edit contract (Phase 12 D-A-01, also used for Phase 13 `BlockedToggle`):
- `Esc` → cancel (no mutation), call `onDone()`
- `Enter` → confirm with highlighted item
- Click outside → cancel (via `document.addEventListener('mousedown', ...)`)
- 250ms debounce on search input
- `data-testid="reassign-combobox"` on container

**Apply this pattern to Phase 14:**
- Settings dirty-state save bar: track dirty fields in local state; show "Save changes / Discard" when dirty; on-navigate guard (standard Next.js `useBeforeUnload` or inline prompt)
- SAML/OIDC toggle: a toggle input that tracks whether user has changed a field before enabling the Save button
- Connector edit form credential fields: same Eye/EyeOff pattern as the v1 modal (already implemented in v1 connectors page — migrate to sunset tokens)

---

## Backend Endpoint Shapes (VERIFIED by reading routers and schemas)

### Connectors

**Base path:** `GET /api/v1/connectors` — requires Admin role

**`ConnectorConfigResponse`** (= `ConnectorResponse` alias):
```typescript
// [VERIFIED: backend/app/connectors/schemas.py]
{
  id: string,                // UUID
  connector_type: string,    // e.g. "CROWDSTRIKE", "JIRA"
  connector_name: string,    // "" default
  is_enabled: boolean,
  config: Record<string, any>,  // non-secret config
  has_credentials: boolean,
  last_sync_at: string | null,  // ISO datetime
  last_sync_status: string | null,  // "ok", "failed", "syncing", null (never synced)
  last_sync_record_count: number | null,
  sync_interval_minutes: number,  // default 60
  created_at: string,
  updated_at: string,
}
```

**`GET /api/v1/connectors/types`** — returns array of:
```typescript
{
  type: string,        // e.g. "CROWDSTRIKE"
  name: string,        // e.g. "CrowdStrike Falcon"
  description: string,
  fields: string[],    // credential field names
  defaults: Record<string, string>,
  permissions: Array<{ scope: string; access: string; purpose: string }>,
  setup_url: string,
  base_urls: Record<string, string>,  // region → URL (empty {} if not applicable)
  notes: string,
  category: string,    // "vulnerability_scanner" | "ticketing" | "identity_provider" | "enrichment"
}
```

**`POST /api/v1/connectors`** — body: `ConnectorCreate`
```typescript
{ connector_type: string; credentials: Record<string, string>; config?: {}; sync_interval_minutes?: number }
```

**`PATCH /api/v1/connectors/{connector_id}`** — body: `ConnectorUpdate`
```typescript
{ credentials?: Record<string, string>; config?: {}; is_enabled?: boolean; sync_interval_minutes?: number }
```

**D-CONN-04 sentinel contract:** `PATCH /tenant/settings` already implements the sentinel pattern for `smtp_config.password`:
```python
# [VERIFIED: backend/app/tenants/router.py:212-215]
if new_smtp and new_smtp.get("password") == "••••••••" and tenant.smtp_config:
    new_smtp["password"] = tenant.smtp_config.get("password", "")
```
The connectors v1 edit modal implements the same pattern by sending blank fields to keep existing credentials. Phase 14 should formalize: edit form pre-fills secret fields with `"••••••"` (6 bullets); if user does not touch the field, include the sentinel in `credentials`; backend interprets blank as "keep existing" (already the case since `credentials` is optional in `ConnectorUpdate`). **The actual sentinel passthrough for connectors is: send `credentials: undefined` (omit the key entirely) when no credential was changed** — the v1 modal already does this via `if (hasNewCredentials) body.credentials = credentials`.

**`DELETE /api/v1/connectors/{connector_id}`** — requires Admin. Returns `{"message": "Connector deleted"}`.

**`POST /api/v1/connectors/test`** — body `ConnectorTestRequest`:
```typescript
{ connector_type: string; credentials: Record<string, string>; config?: {} }
// Returns: { success: boolean; message: string; scopes?: Record<string, boolean> }
```

**`POST /api/v1/connectors/{connector_id}/sync`** — returns `{"status": "STARTED"|"ALREADY_RUNNING", "message": string}`

**`GET /api/v1/connectors/{connector_id}/sync-status`** — returns:
```typescript
{ is_running: boolean; last_sync_at: string|null; last_sync_status: string|null; last_sync_record_count: number|null; sync_interval_minutes: number }
```

**Category mapping** (from router.py CONNECTOR_CATEGORIES):
```python
# [VERIFIED: backend/app/connectors/router.py:33-48]
"CROWDSTRIKE" → "vulnerability_scanner"
"NESSUS"      → "vulnerability_scanner"
"DEFENDER"    → "vulnerability_scanner"
"WIZ"         → "vulnerability_scanner"
"QUALYS"      → "vulnerability_scanner"
"RAPID7"      → "vulnerability_scanner"
"ASANA"       → "ticketing"
"JIRA"        → "ticketing"
"GOOGLE_WORKSPACE" → "identity_provider"
"AZURE_ENTRA_ID"   → "identity_provider"
"OKTA"             → "identity_provider"
"HUMAANS"          → "enrichment"
"JAMF"             → "enrichment"
"INTUNE"           → "enrichment"
```

---

### Settings / Tenants

**`GET /api/v1/tenant/me`** → `TenantResponse`:
```typescript
// [VERIFIED: backend/app/tenants/schemas.py]
{ id: UUID; name: string; slug: string; domain: string|null; idp_provider: string; is_active: boolean; sso_enforced: boolean; timezone: string }
```

**`GET /api/v1/tenant/settings`** — requires Admin. Returns:
```typescript
// [VERIFIED: backend/app/tenants/router.py:106-130]
{
  sso_enforced: boolean,
  idp_provider: string,      // "LOCAL" | "GOOGLE" | "AZURE"
  domain: string,
  timezone: string,
  password_policy: { min_length: number; require_uppercase: boolean; require_lowercase: boolean; require_digit: boolean; require_symbol: boolean; history_count: number },
  syslog_config: object | null,  // { enabled, host, port, protocol, facility }
  smtp_config: object | null,    // { host, port, username, password: "••••••••" (masked), tls, from_email } | null
  sla_config: object | null,
  branding: object | null,
}
```

**`PATCH /api/v1/tenant/settings`** — requires Owner. Accepts partial body with any of: `sso_enforced`, `name`, `domain`, `idp_provider`, `slug`, `timezone`, `password_policy`, `syslog_config`, `smtp_config`, `sla_config`, `branding`. Returns `{"message": "Settings updated"}`.

**SSO guard (D-SET-07):** Backend enforces:
```python
# [VERIFIED: backend/app/tenants/router.py:153-165]
# Cannot set sso_enforced=True without non-LOCAL idp_provider
# Setting idp_provider="LOCAL" auto-disables sso_enforced
```

**`GET /api/v1/tenant/users`** — requires Admin. Returns `list[UserResponse]`:
```typescript
// [VERIFIED: backend/app/tenants/schemas.py]
{ id: UUID; email: string; display_name: string|null; avatar_url: string|null; role: string; is_active: boolean; allow_password_login: boolean; groups: list|null; department: string|null; job_title: string|null; idp_source: string|null; last_login_at: datetime|null }
```
Note: Excludes directory-only users (only returns users with login access).

**`POST /api/v1/tenant/users`** — requires Owner. Body: `{ email, display_name?, role?, password? }`. Creates or updates (upsert by email).

**`PATCH /api/v1/tenant/users/{user_id}/role`** — requires Owner. Body: `{ role: "OWNER"|"ADMIN"|"ANALYST"|"VIEWER" }`.

**`PATCH /api/v1/tenant/users/{user_id}/deactivate`** — requires Owner.

**`DELETE /api/v1/tenant/users/{user_id}`** — requires Owner. Cannot delete self.

**`GET /api/v1/tenant/audit-log`** — requires Admin. Query params:
```
action?: string        // filter by action type e.g. "user.role_change"
resource_type?: string  // filter by resource type e.g. "user"
user_email?: string    // filter by actor email
page?: int (default 1)
page_size?: int (default 50)
```

**`GET /api/v1/tenant/groups`** — requires Admin. Returns:
```typescript
Array<{ name: string; member_count: number; members: Array<{ id, email, display_name, role, department }> }>
```

**`GET /api/v1/tenant/groups/export`** — requires Admin. Returns CSV stream.

---

### Users Directory

**`GET /api/v1/users/directory`** — authenticated (no role gate, get_current_user only). Query params:
```
page, page_size (default 25, max 100)
search: string — matches email, display_name, department, job_title
status: "active" | "suspended" | "all" (default "active")
department: string
source: string — matches idp_source
sort_by: "display_name"|"email"|"department"|"role"|"last_login_at" (default "display_name")
sort_dir: "asc"|"desc"
```

**Response item shape:**
```typescript
// [VERIFIED: backend/app/users/router.py:384-409]
{
  id: string,            // UUID
  email: string,
  display_name: string | null,
  role: string,          // RBAC role of the GetVul account
  department: string | null,
  job_title: string | null,
  idp_source: string,    // "google" | "azure" | "okta" | "humaans" | "local"
  is_active: boolean,
  groups: string[],      // group names
  avatar_url: string | null,
  last_login_at: string | null,
  device_count: number,
  devices: Array<{ id, hostname, os_name, device_category, risk_score, model, serial_number, host_status, last_seen_at }>,
  max_risk_score: number,
  total_vulns: number,
  critical_vulns: number,
  high_vulns: number,
  exploitable_vulns: number,
}
// Response envelope:
{ items: [...], total: number, page: number, page_size: number, pages: number }
```

**D-USR-01 mapping:** For the directory screen:
- "IdP-source pill" = `idp_source` field (pill color: google→blue, azure→blue, okta→indigo, humaans→cyan, local→gray — same as v1 SOURCE_COLORS)
- "job-title/department chip" = `job_title` + `department` fields (not RBAC `role`)
- `role` is the GetVul RBAC role — show it in Workspace settings user list, not the directory

**`GET /api/v1/users/stats`** — authenticated. Returns:
```typescript
{ total_users: number; active: number; suspended: number; by_source: Record<string, number>; has_department: number; has_groups: number; departments: Array<{name, count}>; assigned_assets: number; unassigned_assets: number }
```

---

### Profile + Auth

**`GET /auth/me`** — authenticated. Returns `CurrentUser`:
```typescript
// [VERIFIED: backend/app/auth/schemas.py]
{ id: UUID; tenant_id: UUID; email: string; role: string }
```

**Note:** `/auth/me` returns only `{id, tenant_id, email, role}` — NOT `display_name`, `avatar_url`, `idp_source`, or `last_login_at`. The `useAuth()` hook in the frontend stores the richer `UserInfo` shape from the login response (which includes `display_name`, `avatar_url`, `tenant_name`). For the Profile pane, use `useAuth().user` for the richer shape — it comes from the token response, not from `/auth/me`. The `/auth/me` endpoint is used for token validation, not profile display.

**Frontend `User` shape from `useAuth()`:**
```typescript
// [VERIFIED: frontend/src/lib/auth.tsx]
interface User {
  id: string; email: string; display_name: string; avatar_url: string | null;
  role: string; tenant_id: string; tenant_name: string;
}
```

For `idp_source` and `last_login_at` on the Profile pane, fetch `GET /api/v1/tenant/users` (the list) and find the current user by email — or read the `UserResponse` shape from there. **The `/auth/me` backend endpoint does not return these fields.**

**`POST /auth/change-password`** — authenticated. Body: `{ current_password: string; new_password: string }`. Returns success or error dict. Hidden for SSO users who have no password.

---

### CSPM

**`GET /api/v1/cspm`** — requires Viewer role. Query params: `page`, `page_size`, `severity[]`, `source[]`, `status[]`, `category[]`, `cloud_provider`, `resource_type`, `search`. Returns `PaginatedResponse[MisconfigSummary]`.

**`MisconfigSummary`:**
```typescript
// [VERIFIED: backend/app/cspm/schemas.py]
{
  id: UUID,
  rule_id: string,         // e.g. "AWS-EC2-001"
  rule_name: string,
  category: string,        // "IAM" | "NETWORK" | "ENCRYPTION" | ...
  severity: string,        // "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
  source: string,          // "CROWDSTRIKE" | "WIZ" | "DEFENDER"
  status: string,          // "OPEN" | "IN_PROGRESS" | "REMEDIATED" | "SUPPRESSED" | "FALSE_POSITIVE"
  resource_id: string,     // mono — the cloud resource identifier
  resource_name: string | null,
  resource_type: string | null,
  cloud_provider: string | null,  // "AWS" | "AZURE" | "GCP"
  first_detected_at: datetime,
  last_seen_at: datetime,
}
```

**`MisconfigResponse`** (full detail, used for DrillPanel):
```typescript
// [VERIFIED: backend/app/cspm/schemas.py]
{
  // ...all MisconfigSummary fields...
  rule_description: string | null,
  frameworks: list | null,        // array of framework name strings
  resource_region: string | null,
  cloud_account_id: string | null,
  cloud_account_name: string | null,
  source_finding_id: string | null,
  remediation_info: string | null,
  remediation_url: string | null,
  remediated_at: datetime | null,
  details: dict | null,           // source-specific detail blob
  created_at: datetime,
  updated_at: datetime,
}
```

**`GET /api/v1/cspm/stats`** → `CSPMDashboardStats`:
```typescript
// [VERIFIED: backend/app/cspm/schemas.py]
{
  total_findings: number,
  open_findings: number,
  by_severity: Array<{ severity: string; count: number }>,
  by_category: Array<{ category: string; count: number }>,
  by_source: Array<{ source: string; count: number }>,
  by_cloud_provider: Array<{ cloud_provider: string; count: number }>,  // used for segmented control
  compliance_pass_rate: number | null,
}
```

**`GET /api/v1/cspm/compliance`** — returns `Array<{ name, total_controls, passed, failed, suppressed, pass_rate }>` (array not wrapped, per v1 client code).

**`POST /api/v1/cspm/bulk-status`** — requires Analyst. Body:
```typescript
{ ids: UUID[]; status: "OPEN"|"IN_PROGRESS"|"REMEDIATED"|"SUPPRESSED"|"FALSE_POSITIVE" }
```
D-CSPM-03 maps "Resolve" → `REMEDIATED`, "Ignore" → `SUPPRESSED`, "Reopen" → `OPEN`.

**`PATCH /api/v1/cspm/{finding_id}/status`** — requires Analyst. Body: `{ status: string }`.

---

## Token Discipline and `globals.css` Extension (D-CONN-01)

**Current state:**
```css
/* [VERIFIED: frontend/src/app/globals.css:56-62] */
/* Phase 13 — Provider gradient tokens (D-PROV-03, A4 resolution). */
:root {
  --gradient-provider-jira:   linear-gradient(135deg, #5C9CFF, #2684FF);
  --gradient-provider-asana:  linear-gradient(135deg, #FF8AA0, #F1506E);
  --gradient-provider-github: linear-gradient(135deg, #C7BAFF, #A78BFA);
}
```

**Phase 14 Wave 0 addition** — add 11 new tokens to the same `:root` block in `globals.css`. One hex per provider, once. All in `135deg` linear-gradient to match Phase 13's convention. Reference color palette [ASSUMED — exact hex values should be reviewed for brand accuracy]:

```css
/* Phase 14 — Additional provider gradient tokens (D-CONN-01). */
/* Hex lives ONCE here; <ConnectorMark> consumes via var(--gradient-provider-{type.toLowerCase()}). */
:root {
  /* Vulnerability scanners */
  --gradient-provider-crowdstrike:  linear-gradient(135deg, #E04020, #C0301A);  /* red */
  --gradient-provider-nessus:       linear-gradient(135deg, #00C176, #008F55);  /* green */
  --gradient-provider-defender:     linear-gradient(135deg, #5C9CFF, #2563EB);  /* blue */
  --gradient-provider-wiz:          linear-gradient(135deg, #6ECCAF, #2E8B57);  /* teal */
  --gradient-provider-qualys:       linear-gradient(135deg, #E84E4E, #C23B3B);  /* red */
  --gradient-provider-rapid7:       linear-gradient(135deg, #E87A2A, #C05C18);  /* orange */

  /* Identity providers */
  --gradient-provider-google_workspace: linear-gradient(135deg, #60A5FA, #2563EB);  /* blue */
  --gradient-provider-azure_entra_id:   linear-gradient(135deg, #818CF8, #4F46E5);  /* indigo */
  --gradient-provider-okta:             linear-gradient(135deg, #818CF8, #4F46E5);  /* indigo */

  /* Enrichment / MDM */
  --gradient-provider-jamf:    linear-gradient(135deg, #6EE7B7, #059669);  /* emerald */
  --gradient-provider-intune:  linear-gradient(135deg, #818CF8, #4338CA);  /* blue-violet */
  --gradient-provider-humaans: linear-gradient(135deg, #67E8F9, #0E7490);  /* cyan */
}
```

**Token naming rule:** The CSS variable key uses the connector_type string lowercased with underscores preserved. The `ConnectorMark` component maps `type.toLowerCase()` → `var(--gradient-provider-${type.toLowerCase()})`. This matches the pattern for the ticket providers (jira, asana, github are all lowercase).

**Sunset base variables confirmed present:**
- `--color-violet` = `#A78BFA`, `--color-pink` = `#EC4899`, `--color-amber` = `#F59E0B`
- `--color-danger` = `#F87171`, `--color-success` = `#4ADE80`
- `--color-blue` does NOT exist in `sunset.css` — `--color-info` = `#60A5FA` is the nearest analog
- `--color-coral` does NOT exist — the asana gradient uses raw hex `#FF8AA0` / `#F1506E`

---

## Current State of the Four Target Routes (FULL REWRITES)

### `/dashboard/cspm/page.tsx` — v1 state
**File:** `frontend/src/app/(authed)/dashboard/cspm/page.tsx` (~907 lines)

- v1 pattern: `useState` + `useCallback` + `useEffect` fetching, no TanStack Query
- Four horizontal tabs: Findings / Compliance / Resources / Trends
- Raw palette utilities: `gray-800`, `gray-900`, `indigo-500`, `red-500`, `emerald-400`, etc. — zero sunset tokens
- Finding rows are inline `<tr>` with no drill panel — click does nothing interactive
- Loading state: `<Loader2 animate-spin text-indigo-500>` inline
- Empty state: `<div className="py-12 text-center text-gray-500">` inline
- **Action on rewrite:** Delete all four tab subcomponents and the v1 page component after the sunset replacement is live

### `/dashboard/connectors/page.tsx` — v1 state
**File:** `frontend/src/app/(authed)/dashboard/connectors/page.tsx` (~619 lines)

- v1 pattern: `useState` + `useEffect` + `useCallback`; direct `api()` calls
- Already has category-sectioned card grid structure (matches D-CONN-03 intent) — this is the most reuse-friendly v1 screen
- Already has `ConfirmModal` + `useToast` integrated
- Already has add/edit modals with credential fields, eye/EyeOff reveal, region selectors, test/save flow
- Missing sunset tokens (all raw palette: `gray-800`, `indigo-600`, `emerald-400`, etc.)
- Missing sync status pill (4-state per D-CONN-05)
- Missing `ProviderMark`/`ConnectorMark` gradient chip (uses text abbreviations like "CS", "JR")
- Missing is_enabled toggle (has "Active"/"Disabled" badge but no toggle)
- Missing inbound `?provider=` deep-link handling (D-CONN-07)
- **Action on rewrite:** The structure is largely preserved; migrate to TanStack Query, apply sunset tokens, add `ConnectorMark`, add enable toggle, add sync status pill

### `/dashboard/users/page.tsx` — v1 state
**File:** `frontend/src/app/(authed)/dashboard/users/page.tsx` (partial view)

- v1 pattern: `useState` + `useEffect`; calls `/api/v1/users/directory`
- Already has directory/groups tab toggle (but as horizontal tabs — rewrite to segmented toggle per D-USR-03)
- Uses `SOURCE_COLORS` for idp_source pill (raw Tailwind palette — migrate to sunset tokens)
- Has `ExportButton` imported already
- Missing: URL-state for filters, TanStack Query, `ChipBar`, `SkeletonTable`, `EmptyState`, `PartialFailureBanner`
- **Action on rewrite:** Full rewrite adopting TanStack hooks, canonical state primitives, segmented toggle

### `/dashboard/settings/page.tsx` — v1 state
**File:** `frontend/src/app/(authed)/dashboard/settings/page.tsx` (partial view, ~80+ lines shown)

- v1 pattern: `useState` + `useEffect`; four horizontal tabs: general / auth / users / audit
- Raw palette utilities throughout
- Tab implementation:
  ```jsx
  {["general", "auth", "users", "audit"].map(t => (
    <button key={t} onClick={() => setTab(t as any)}
      className={`pb-2 text-sm font-medium capitalize transition ${tab === t ? "border-b-2 border-indigo-500 text-white" : "text-gray-400 hover:text-gray-300"}`}>
  ```
  This **is** the horizontal tab pattern that success criterion #5 requires fully eliminating.
- **Action on rewrite:** Full rewrite to sidebar-of-categories layout. The `grep -r "tab" frontend/src/app/dashboard/settings/` gate must return zero horizontal-tab usages after the rewrite.

---

## RBAC Gating Mechanics

**Backend role hierarchy (VERIFIED):**
```python
# [VERIFIED: backend/app/auth/rbac.py]
OWNER   = 40
ADMIN   = 30
ANALYST = 20
VIEWER  = 10
```

**Backend guards per endpoint:**
- `require_viewer` → VIEWER+ can access
- `require_analyst` → ANALYST+ (CSPM status updates, bulk-status)
- `require_admin` → ADMIN+ (connectors all, tenant/users list, settings GET, audit log, groups)
- `require_owner` → OWNER only (settings PATCH, user create/delete/deactivate/role, groups export)

**Frontend role check (VERIFIED):**
```typescript
// [VERIFIED: frontend/src/lib/auth.tsx]
const { user } = useAuth();
const isOwner = user?.role === 'OWNER';
const isAdmin = user?.role === 'OWNER' || user?.role === 'ADMIN';
const isAnalyst = ['OWNER', 'ADMIN', 'ANALYST'].includes(user?.role ?? '');
```

**D-SET-05 sidebar gating implementation pattern:**
```typescript
// Sidebar shows categories based on role:
const visibleCategories = [
  'profile',                                               // always visible
  ...(isAdmin ? ['workspace', 'saml', 'notifications', 'audit'] : []),
  'api-tokens',                                            // always visible (placeholder)
];
```

**D-CONN-06 delete gating:**
```typescript
// Delete button only rendered for Admin+:
{isAdmin && (
  <button onClick={() => openDeleteModal(conn.id)}>Delete</button>
)}
```

The v1 settings page already implements `const isOwner = user?.role === 'OWNER'` and `const isAdmin = ...` — this pattern is confirmed and carries forward.

---

## URL-State Pattern (VERIFIED by reading Phase 11–13 sources)

**Pattern:** `useUrlStateList` for multi-value filter chips, `useSearchParams`/`router.replace` for single values.

**CSPM:** `?severity=CRITICAL&severity=HIGH&status=OPEN&cloud_provider=AWS&search=s3&open=drill&finding=<id>`

**Users directory:** `?status=active&department=Engineering&source=google&search=alice&view=directory`

**Settings:** `?category=workspace` (sidebar category, persisted to URL so direct links work)

**Connectors:** `?provider=asana` (inbound deep-link from `/tickets` per D-CONN-07)

The `useUrlStateList` hook signature:
```typescript
// [VERIFIED: hooks/use-url-state-list.ts is the multi-value variant]
const [values, setValues, toggle] = useUrlStateList<string>(key, allowList, defaultValue);
```

The `useUrlState` hook (single-value):
```typescript
// [VERIFIED: hooks/use-url-state.ts — Phase 10 + WR-04 fix]
// Already has XSS clamp — null-clamp before allow-list includes check
```

---

## Architecture Patterns

### System Architecture Diagram

```
User action (click/filter/URL nav)
    ↓
ChipBar → useUrlStateList → URL params
    ↓
TanStack query hook (useCspmFindings / useConnectors / useDirectoryUsers / useTenantSettings)
    ↓ staleTime 60s, 0-1 retry
API layer (fetch + bearer token from auth context)
    ↓
Backend router (role check → service → DB)
    ↓
Response (snake_case fields, no transform)
    ↓
Component renders:
  Loading → SkeletonTable + PerSourceStatusStrip
  Error   → PartialFailureBanner + stale row tinting
  Empty   → EmptyState (explained-why + CTAs)
  Data    → Table/Card grid
              ↓ row click
           URL: ?{idKey}=<id>&open=drill
              ↓
           DrillPanel (420px aside, fixed right)
              ↓ fetch /cspm/{id} | /connectors/{id} etc.
           Content slot (FindingDrillContent / ConnectorEditForm)
```

### Recommended Project Structure (Phase 14 additions)

```
frontend/src/
├── app/(authed)/dashboard/
│   ├── cspm/page.tsx              # FULL REWRITE (delete v1)
│   ├── connectors/page.tsx        # FULL REWRITE (delete v1)
│   ├── users/page.tsx             # FULL REWRITE (delete v1)
│   └── settings/page.tsx          # FULL REWRITE (delete v1)
│
├── components/
│   ├── cspm/
│   │   ├── finding-drill-content.tsx     # New: finding slot for DrillPanel
│   │   ├── cspm-bulk-bar.tsx              # New: Resolve/Ignore/Reopen bar
│   │   ├── compliance-framework-strip.tsx # New: frameworks summary rail
│   │   └── microcopy.ts
│   ├── connectors/
│   │   ├── connector-card.tsx             # New: per-connector card
│   │   ├── connector-mark.tsx             # New: 14-provider gradient mark
│   │   ├── sync-status-pill.tsx           # New: 4-state sync pill
│   │   ├── connector-form.tsx             # New: add/edit form (sunset-restyled)
│   │   └── types.ts                       # New: ConnectorProvider union type
│   ├── settings/
│   │   ├── settings-sidebar-shell.tsx     # New: sidebar + pane layout
│   │   ├── save-bar.tsx                   # New: per-category sticky save bar
│   │   ├── profile-pane.tsx
│   │   ├── workspace-pane.tsx
│   │   ├── saml-pane.tsx
│   │   ├── notifications-pane.tsx
│   │   ├── audit-log-pane.tsx
│   │   └── microcopy.ts
│   └── users/
│       ├── directory-table.tsx
│       ├── users-chip-bar.tsx
│       ├── source-pill.tsx                # New: idp_source pill
│       └── microcopy.ts
│
├── lib/queries/
│   ├── use-cspm-findings.ts               # New TanStack hook
│   ├── use-cspm-detail.ts                 # New TanStack hook
│   ├── use-tenant-settings.ts             # New TanStack hook
│   ├── use-directory-users.ts             # New TanStack hook
│   └── keys.ts                            # EXTEND with cspm, settings, directoryUsers namespaces
│
└── app/globals.css                        # EXTEND :root block with 11 new --gradient-provider-* tokens
```

### Pattern 1: Adding a DrillPanel Content Slot

```typescript
// [ASSUMED: mirrors Phase 13 D-D-02 — ticket slot]
// Component: frontend/src/components/cspm/finding-drill-content.tsx
'use client';
import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/lib/queries/keys';

type Props = { findingId: string; onClose: () => void };

export function FindingDrillContent({ findingId, onClose }: Props) {
  const { data, isPending, error } = useQuery({
    queryKey: queryKeys.cspm.detail(findingId),
    queryFn: () => fetchCspmDetail(findingId),
  });

  if (isPending) return <SkeletonDrillContent />;  // columns: [{kind:'text',width:200}] ×4
  if (error || !data) return <PartialFailureBanner errors={[{ code: 'ERR', requestId: '' }]} />;

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      {/* Header */}
      <div className="flex items-start justify-between p-4 border-b border-border-subtle">
        <div className="flex items-center gap-2">
          <ConnectorMark provider={data.source.toLowerCase() as ConnectorProvider} />
          <span className="font-mono text-sm text-text">{data.rule_id}</span>
        </div>
        <button onClick={onClose} aria-label="Close" className="...">×</button>
      </div>
      {/* Body: severity + resource + frameworks + remediation + status */}
    </div>
  );
}
```

### Pattern 2: Settings Sidebar Shell

```typescript
// [ASSUMED: mirrors app-shell.md sidebar pattern]
// Component: frontend/src/components/settings/settings-sidebar-shell.tsx
'use client';
type Category = 'profile' | 'workspace' | 'saml' | 'notifications' | 'api-tokens' | 'audit';

type Props = {
  children: React.ReactNode;
  activeCategory: Category;
  visibleCategories: Category[];
  onCategoryChange: (c: Category) => void;
};
// Left: 220px sidebar, sticky. Right: pane (flex-1, overflow-y-auto).
// Mobile (<900px): category list → pane drill (master-detail) per D-SET-10.
```

### Pattern 3: Per-Category Save Bar

```typescript
// [ASSUMED: mirrors Phase 12 reassign-combobox dirty-state pattern]
// Component: frontend/src/components/settings/save-bar.tsx
type Props = {
  isDirty: boolean;
  isSaving: boolean;
  onSave: () => void;
  onDiscard: () => void;
};
// Sticky bottom; only visible when isDirty=true
// Animation: slide-in-from-bottom when isDirty flips to true
// Blocks category navigation when isDirty via unsaved-changes confirm
```

### Anti-Patterns to Avoid

- **Raw palette utilities:** Never `text-gray-400`, `bg-red-600`, etc. Use `text-text-muted`, `bg-danger` etc.
- **Inline data fetching:** Never `useState` + `useEffect` + manual `api()`. Always TanStack Query hooks.
- **Horizontal tabs in settings:** Any `border-b-2 border-indigo-500` tab pattern in `settings/` will fail the grep gate.
- **camelCase API fields:** Backend returns snake_case; never add a transform layer (D-X-02).
- **`ConnectorMark` via string interpolation:** Lookup object only, never `var(--gradient-provider-${type})` directly — defeats the T-13-14 injection mitigation.
- **ExportButton refactoring:** Do not migrate ExportButton to TanStack; use as-is with sunset restyle only.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Multi-value URL filter chips | Custom chip state | `ChipBar` + `useUrlStateList` | Handles XSS clamp, debounce, clear-all, saved-filter atomically |
| Loading skeleton | Inline shimmer divs | `SkeletonTable` | axe-tested, aria-busy, reduced-motion safe |
| Partial API failure | Inline error text | `PartialFailureBanner` | AMBER not red, role="alert", request ID display |
| 420px slide panel | New `position:fixed` aside | `DrillPanel` + `DrillPanelMobile` | Focus trap, Esc/clickaway/×, vaul mobile, URL-state |
| Source progress | Custom source chips | `PerSourceStatusStrip` | Composes `useConnectors()`, aria-live="polite" |
| Delete confirmation | Native `confirm()` | `ConfirmModal` | Focus management, Esc, variant styling |
| Toast messages | Custom toast div | `useToast()` | z-[60], auto-dismiss, action slot |
| Masked credentials sentinel | Custom masking | Pattern from `tenants/router.py:212` | Backend already handles `"••••••••"` → keep existing |
| CSV export | Custom fetch + blob | `ExportButton` | 401-retry, blob URL, Content-Disposition filename |
| Avatar initials | Custom initials | `Avatar` component (already in Phase 12) | 2-char WR-09 fix, consistent sizing |

---

## Common Pitfalls

### Pitfall 1: Settings tab check fails grep gate
**What goes wrong:** Leaving any `border-b-2` or `border-b border-indigo` or similar tab indicator anywhere in `frontend/src/app/(authed)/dashboard/settings/` — even in a sub-component that used to be a tab.
**Why it happens:** Success criterion #5 is a grep check, not a visual check. Inline styles or className strings containing the tab pattern will fail.
**How to avoid:** After the rewrite, run `grep -r "tab" frontend/src/app/(authed)/dashboard/settings/` before committing. The only valid tab-string is in comments.
**Warning signs:** Any `border-b` on a button inside settings/.

---

### Pitfall 2: ConfirmModal v1 styling clash
**What goes wrong:** Using `ConfirmModal` as-is in sunset-styled screens causes a visual mismatch (gray-900 bg, indigo-600 buttons vs sunset palette).
**Why it happens:** `ConfirmModal` was never restyled.
**How to avoid:** Wave 0 must include a `ConfirmModal` sunset restyle task (swap `gray-*` → `surface`/`surface-2`/`border-*`, `indigo-*` danger variant → `severity-critical`/`danger`).
**Warning signs:** Modal backdrop shows gray-900 instead of surface plum.

---

### Pitfall 3: ExportButton v1 styling clash
**What goes wrong:** Same as ConfirmModal — `ExportButton` uses `border-gray-700 px-3 text-gray-300 hover:bg-gray-800`.
**Why it happens:** Never restyled.
**How to avoid:** Wave 0 restyle ExportButton: `border-border-subtle text-text-muted hover:bg-surface-2`.
**Warning signs:** Export button is gray on a dark plum surface.

---

### Pitfall 4: CSPM status values vs ticket status values
**What goes wrong:** Reusing ticket status pill colors (Open/violet, Completed/green) for CSPM finding statuses.
**Why it happens:** CSPM statuses are different: `OPEN | IN_PROGRESS | REMEDIATED | SUPPRESSED | FALSE_POSITIVE`.
**How to avoid:** CSPM needs its own status pill mapping. Suggested mapping:
- OPEN → violet (matches tickets Open)
- IN_PROGRESS → amber
- REMEDIATED → success green
- SUPPRESSED → text-muted gray
- FALSE_POSITIVE → text-muted gray + italic
**Warning signs:** "SUPPRESSED" rendering as a blocked-red pill.

---

### Pitfall 5: `has_credentials` vs sentinel for connector display
**What goes wrong:** Showing credential field values from the API response when editing.
**Why it happens:** `ConnectorConfigResponse.has_credentials` is a boolean — the backend never returns credential values. Only `config` (non-secret) is returned.
**How to avoid:** Edit form must always pre-fill secret fields with `"••••••"` sentinel (visual only, never from API). The sentinel is never sent back unless the user types it in — omit `credentials` from the PATCH body if all fields are unchanged. **The backend's `ConnectorUpdate.credentials` is optional** — if omitted, credentials are unchanged.
**Warning signs:** Edit modal showing empty password fields instead of masked bullets.

---

### Pitfall 6: `/auth/me` insufficient for Profile pane
**What goes wrong:** Fetching `/auth/me` for the Profile pane and finding only `{id, tenant_id, email, role}` — no `display_name`, `idp_source`, or `last_login_at`.
**Why it happens:** `CurrentUser` schema in the backend is the JWT payload, not the full user record.
**How to avoid:** Profile pane should use `useAuth().user` for basic identity (populated from token response), and `GET /api/v1/tenant/users` + filter by `user.email` for `idp_source` + `last_login_at`.
**Warning signs:** Profile pane showing empty name/source fields despite successful auth.

---

### Pitfall 7: Users directory role vs RBAC role confusion
**What goes wrong:** Showing `user.role` (OWNER/ADMIN/ANALYST/VIEWER) on the directory cards as if it's a job title.
**Why it happens:** The `UserResponse` has a `role` field which is the RBAC role, not the job title.
**How to avoid:** Per D-USR-01, the directory shows `job_title` + `department` as the person's "role" context. The RBAC `role` field belongs in the Workspace settings accounts list. The directory's `role` field should be used for role-awareness but not displayed as a job title chip.
**Warning signs:** Directory showing "ADMIN" or "VIEWER" as a role pill.

---

### Pitfall 8: `queryKeys` namespace missing for Phase 14 domains
**What goes wrong:** Using ad-hoc query key arrays `['cspm', 'list']` instead of the `queryKeys` factory.
**Why it happens:** `queryKeys` in `keys.ts` has no `cspm`, `settings`, or `directoryUsers` namespaces yet.
**How to avoid:** Wave 0 extends `queryKeys` with `cspm`, `settings`, `directoryUsers` namespaces following the Phase 12/13 pattern. Any new hook must import from `keys.ts`.
**Warning signs:** `queryClient.invalidateQueries(['cspm'])` failing to invalidate the correct entries.

---

## State of the Art

| Old Approach (v1) | Current Approach (Phase 14) | Impact |
|---|---|---|
| `useState` + `useEffect` + manual `api()` | TanStack Query v5 hooks | Caching, background refetch, stale-while-revalidate |
| Horizontal tabs (`border-b-2 border-indigo-500`) | Sidebar-of-categories or segmented toggle | Zero tab patterns in settings — passes grep gate |
| Inline loading spinner (`Loader2 animate-spin`) | `SkeletonTable` + `PerSourceStatusStrip` | Column-shaped loading, source-aware |
| Inline empty string `py-12 text-center text-gray-500` | `EmptyState` compound | role="status", CTAs, suggestion slot |
| Raw palette (`gray-800`, `indigo-500`, `emerald-400`) | Sunset tokens (`surface`, `border-border-subtle`, `severity-critical`) | Zero `!important`; theme-safe |
| Text abbreviations for connector identity ("CS", "JR") | `ConnectorMark` with CSS gradient tokens | Brand-coherent; no trademark images |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Phase 14 gradient hex values for 11 new providers (crowdstrike red, nessus green, etc.) | Token Discipline | Colors may need adjustment for visual clarity or brand accuracy; safe to revise before commit |
| A2 | `FindingDrillContent` component location at `components/cspm/finding-drill-content.tsx` | Architecture Patterns / Project Structure | Planner can relocate; the API shape is what matters |
| A3 | Settings sidebar uses URL `?category=<name>` for category persistence | URL-State Conventions | Could use local state instead; URL pattern is preferred per D-X-01 URL-state convention |
| A4 | Profile pane reads `idp_source` + `last_login_at` from `GET /api/v1/tenant/users` filtered by email | Backend Endpoints | If the tenant/users endpoint doesn't return these for the current user specifically, may need a dedicated `/auth/me/profile` endpoint — but the existing data is verified to exist in `UserResponse` |
| A5 | `ConfirmModal` sunset restyle is part of Wave 0 | Common Pitfalls | If the planner puts it in a later wave, visual regression appears when modals are first used |

---

## Open Questions (RESOLVED)

1. **Connector sentinel behavior clarification**
   - What we know: `ConnectorUpdate.credentials` is optional; omitting it keeps credentials. `has_credentials: boolean` is on the response. Backend never returns credential values.
   - What's unclear: Should the edit form display `"••••••"` in the input field as a placeholder, or as the actual field value that gets sent back? The v1 edit modal uses blank fields ("leave blank to keep existing") which is simpler but less clear.
   - Recommendation: D-CONN-04 locks the sentinel approach (`"••••••"`-prefilled fields, untouched → omit credentials from PATCH body). Implement as: pre-fill with `"••••••"` (6 bullets) visually; track whether user has changed any field; if unchanged, omit `credentials` from the PATCH; if changed, include only the changed fields.
   - **RESOLVED** — D-CONN-04 locks omit-credentials-when-unchanged (implemented in 14-02 ConnectorForm).

2. **Notification "Alert categories" field shape**
   - What we know: `GET /api/v1/tenant/settings` returns no explicit `alert_categories` field in the current router.
   - What's unclear: What fields exist in the settings payload for notification preferences beyond `smtp_config` and `syslog_config`.
   - Recommendation: Claude's discretion per CONTEXT.md. If not present, render a placeholder card for "Alert categories" with the same coming-soon EmptyState pattern as API tokens.
   - **RESOLVED** — Claude's Discretion per CONTEXT.md; render coming-soon EmptyState if field absent (14-05 NotificationsPane).

3. **Audit log response shape from `get_audit_logs`**
   - What we know: `GET /api/v1/tenant/audit-log` calls `get_audit_logs(db, tenant_id, action, resource_type, user_email, page, page_size)`.
   - What's unclear: The exact response envelope — whether it returns `{items, total, page}` or a flat list. The `get_audit_logs` helper in `app/audit.py` was not read.
   - Recommendation: Read `backend/app/audit.py` `get_audit_logs()` function during planning to confirm the response shape.
   - **RESOLVED** at execution time — 14-05 Task 2 read_first already includes backend/app/audit.py to confirm the envelope shape before implementing.

---

## Environment Availability

Step 2.6: SKIPPED (no external dependencies — Phase 14 is frontend-only with no new tools, services, or runtimes beyond the existing project stack).

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Vitest + React Testing Library (same as Phases 11–13) |
| Config file | `frontend/vitest.config.ts` (exists from Phase 11) |
| Quick run command | `cd frontend && npx vitest run --reporter=verbose` |
| Full suite command | `cd frontend && npx vitest run` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UX-06-01 | CSPM finding rows render cloud provider gradient mark, severity pill, resource_id mono | unit | `npx vitest run src/components/cspm/` | ❌ Wave 0 |
| UX-06-01 | DrillPanel opens at `?finding=<id>&open=drill` when finding row clicked | integration | `npx vitest run src/app/(authed)/dashboard/cspm/` | ❌ Wave 0 |
| UX-06-01 | Compliance framework rail renders pass-rate from `/cspm/compliance` | unit | `npx vitest run src/components/cspm/compliance-framework-strip.test.tsx` | ❌ Wave 0 |
| UX-06-02 | Connector card renders `connector_type` with ConnectorMark + `last_sync_at` + status pill | unit | `npx vitest run src/components/connectors/connector-card.test.tsx` | ❌ Wave 0 |
| UX-06-02 | Add connector form submits `POST /api/v1/connectors` with correct body | integration | `npx vitest run src/components/connectors/connector-form.test.tsx` | ❌ Wave 0 |
| UX-06-02 | Edit form omits `credentials` from PATCH when no field was changed | unit | `npx vitest run src/components/connectors/connector-form.test.tsx` | ❌ Wave 0 |
| UX-06-02 | Inbound `?provider=asana` pre-scrolls/pre-opens the Asana add flow | integration | `npx vitest run src/app/(authed)/dashboard/connectors/page.test.tsx` | ❌ Wave 0 |
| UX-06-03 | Directory table renders `idp_source` pill for each row | unit | `npx vitest run src/components/users/directory-table.test.tsx` | ❌ Wave 0 |
| UX-06-03 | Segmented toggle switches between Directory and Groups views | integration | `npx vitest run src/app/(authed)/dashboard/users/page.test.tsx` | ❌ Wave 0 |
| UX-06-03 | ExportButton triggers export request with selected IDs | unit | `npx vitest run src/components/users/` | ❌ Wave 0 |
| UX-06-04 | Settings sidebar hides Workspace/SAML/Audit categories for VIEWER role | unit | `npx vitest run src/components/settings/settings-sidebar-shell.test.tsx` | ❌ Wave 0 |
| UX-06-04 | Save bar appears when a field is dirtied and disappears after successful save | unit | `npx vitest run src/components/settings/save-bar.test.tsx` | ❌ Wave 0 |
| UX-06-04 | `grep -r "tab" frontend/src/app/(authed)/dashboard/settings/` returns zero horizontal-tab patterns | grep | `grep -rn "border-b.*indigo\|border-b-2" frontend/src/app/(authed)/dashboard/settings/` | grep gate |
| D-X-01 | All 4 screens render SkeletonTable when data is loading | unit (per screen) | `npx vitest run src/app/(authed)/dashboard/{cspm,connectors,users,settings}/` | ❌ Wave 0 |
| D-X-01 | All 4 screens render EmptyState with CTA when no data | unit (per screen) | same | ❌ Wave 0 |
| D-X-01 | All 4 screens render PartialFailureBanner on query error | unit (per screen) | same | ❌ Wave 0 |

### Success Criteria → Verifiable Checks

| Success Criterion | Observable Behavior | Verification |
|---|---|---|
| SC-1: CSPM has chip-bar + side-panel + compliance rail + cloud segmented control | ChipBar renders above table; DrillPanel opens on row click; compliance rail above list; segmented control top | `grep -n "ChipBar\|DrillPanel\|ComplianceFrameworkStrip" frontend/src/app/(authed)/dashboard/cspm/page.tsx` must return all 3 |
| SC-2: Connectors has cards with gradient mark + last-sync + status pill + actions | ConnectorMark in each card; `last_sync_at` renders; status pill present; add/edit/sync/delete buttons | `grep -n "ConnectorMark\|last_sync_at\|SyncStatusPill" frontend/src/components/connectors/connector-card.tsx` must return all |
| SC-3: Users has IdP-source pill + bulk bar + role pills | SourcePill component in table row; BulkBar visible on selection; role chip renders | `grep -n "SourcePill\|BulkBar\|job_title\|department" frontend/src/components/users/directory-table.tsx` |
| SC-4: Settings has sidebar-of-categories | SettingsSidebarShell wraps the page | `grep -n "SettingsSidebarShell" frontend/src/app/(authed)/dashboard/settings/page.tsx` must return match |
| SC-5: No horizontal tabs in settings | Zero tab-pattern classes | `grep -rn "border-b-2\|tab.*indigo\|border-b border-indigo" frontend/src/app/(authed)/dashboard/settings/` must return 0 |
| SC-6: State patterns on all screens | SkeletonTable + EmptyState + PartialFailureBanner imported in each page | `grep -n "SkeletonTable\|EmptyState\|PartialFailureBanner" frontend/src/app/(authed)/dashboard/{cspm,connectors,users,settings}/page.tsx` must return all 3 per file |

### Wave 0 Gaps (test infrastructure to create before screen implementation)

- [ ] `frontend/src/components/cspm/finding-drill-content.test.tsx`
- [ ] `frontend/src/components/cspm/compliance-framework-strip.test.tsx`
- [ ] `frontend/src/components/cspm/cspm-bulk-bar.test.tsx`
- [ ] `frontend/src/components/connectors/connector-card.test.tsx`
- [ ] `frontend/src/components/connectors/connector-mark.test.tsx`
- [ ] `frontend/src/components/connectors/connector-form.test.tsx`
- [ ] `frontend/src/components/connectors/sync-status-pill.test.tsx`
- [ ] `frontend/src/components/settings/settings-sidebar-shell.test.tsx`
- [ ] `frontend/src/components/settings/save-bar.test.tsx`
- [ ] `frontend/src/components/users/directory-table.test.tsx`
- [ ] `frontend/src/lib/queries/use-cspm-findings.test.ts`
- [ ] `frontend/src/lib/queries/use-tenant-settings.test.ts`
- [ ] `frontend/src/lib/queries/use-directory-users.test.ts`

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No — OIDC auth established in Phase 9; no new auth flows | — |
| V3 Session Management | No — session handled by Phase 9/10 auth context | — |
| V4 Access Control | Yes — RBAC gating for settings categories and connector delete | Frontend: `useAuth().user.role` check; Backend: `require_admin` / `require_owner` |
| V5 Input Validation | Yes — connector credential fields, settings PATCH body | Backend: Pydantic models; Frontend: no raw string interpolation into CSS var names (literal lookup objects) |
| V6 Cryptography | Yes — connector credentials (already encrypted at rest by backend; masked on GET) | `has_credentials: boolean` + sentinel pattern; never display credential values |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| CSS variable injection via connector_type | Spoofing/Tampering | Literal lookup object in `ConnectorMark` — arbitrary connector_type falls through to `undefined` (no CSS class rendered) |
| XSS via reflected URL filter values | Tampering | `ChipBar` `allowList` + `useUrlStateList` XSS clamp (T-12-05) |
| Information disclosure via credential display | Disclosure | Never fetch/display credential values; `has_credentials: boolean` only; sentinel pattern for masked display |
| RBAC bypass via frontend-only gating | Elevation | Both frontend (hide UI) and backend (`require_admin` / `require_owner`) enforce independently |
| Sentinel passthrough spoofing | Tampering | Edit form only omits `credentials` key (not sends sentinel to backend) — backend `ConnectorUpdate.credentials` is `Optional[dict]` |

---

## Sources

### Primary (HIGH confidence — read from source)
- `frontend/src/components/states/skeleton-table.tsx` — exact SkeletonTable signature + SkeletonColumn type
- `frontend/src/components/states/empty-state.tsx` — compound subcomponent API
- `frontend/src/components/states/partial-failure-banner.tsx` — hybrid props/watchKeys API + ErrorRow type
- `frontend/src/components/states/per-source-status-strip.tsx` — Props shape + status CSS classes
- `frontend/src/components/vulnerabilities/drill-panel.tsx` — DrillPanel props including idKey + renderContent slot
- `frontend/src/components/ui/ChipBar.tsx` — ChipAxis + ChipDescriptor + ChipBarProps (full)
- `frontend/src/components/tickets/provider-mark.tsx` — PROVIDER_GRADIENTS lookup + ProviderMarkProps
- `frontend/src/components/ui/ConfirmModal.tsx` — ConfirmModalProps + v1 styling alert
- `frontend/src/components/ui/ToastProvider.tsx` — ToastInput interface + useToast
- `frontend/src/components/ui/ExportButton.tsx` — Props + auth mechanism + v1 styling alert
- `frontend/src/components/tickets/types.ts` — TicketProvider + TicketStatus
- `frontend/src/components/assets/reassign-combobox.tsx` — inline-edit pattern
- `frontend/src/components/tickets/ticket-bulk-bar.tsx` — BulkActionBar pattern (bottom-anchored, ConfirmModal)
- `frontend/src/lib/queries/keys.ts` — queryKeys factory (existing namespaces)
- `frontend/src/lib/auth.tsx` — useAuth + User interface + role check pattern
- `backend/app/connectors/router.py` — endpoint signatures + CONNECTOR_CATEGORIES map
- `backend/app/connectors/schemas.py` — all Pydantic models (ConnectorConfigResponse, ConnectorCreate, etc.)
- `backend/app/tenants/router.py` — settings, users, audit-log, groups endpoints
- `backend/app/tenants/schemas.py` — TenantResponse + UserResponse + UserRoleUpdate
- `backend/app/users/router.py` — /directory endpoint + full response shape
- `backend/app/auth/router.py` — /me + /change-password endpoints
- `backend/app/auth/schemas.py` — CurrentUser schema (limited fields)
- `backend/app/cspm/router.py` — all CSPM endpoints + role requirements
- `backend/app/cspm/schemas.py` — MisconfigSummary + MisconfigResponse + BulkMisconfigStatusUpdate
- `backend/app/auth/rbac.py` — ROLE_HIERARCHY + require_* dependency wrappers
- `frontend/src/app/globals.css` — existing --gradient-provider-* tokens + animation keyframes
- `frontend/src/styles/sunset.css` — all CSS variables (color tokens, no --color-blue/--color-coral)
- `frontend/src/app/(authed)/dashboard/cspm/page.tsx` — v1 state (full)
- `frontend/src/app/(authed)/dashboard/connectors/page.tsx` — v1 state (full)
- `frontend/src/app/(authed)/dashboard/users/page.tsx` — v1 state (partial)
- `frontend/src/app/(authed)/dashboard/settings/page.tsx` — v1 state (partial, tab implementation confirmed)

### Secondary (MEDIUM confidence)
- `.planning/phases/11-vulnerabilities-state-patterns/11-CONTEXT.md` — state-primitive API decisions (D-S-01..07)
- `.planning/phases/12-assets-list-detail/12-CONTEXT.md` — ChipBar generalization, inline-edit pattern
- `.planning/phases/13-tickets-list-detail/13-CONTEXT.md` — DrillPanel idKey generalization (D-D-02), ProviderMark + gradient token discipline (D-PROV-03)
- `.claude/skills/sketch-findings-getvul/references/visual-language.md` — severity/status pill visual contract
- `.claude/skills/sketch-findings-getvul/references/interaction-patterns.md` — drill panel, chip bar, bulk bar

### Tertiary (LOW confidence — assumptions)
- Exact hex values for 11 new provider gradient tokens (A1) — brand colors are estimated; should be confirmed
- Notification "Alert categories" payload existence (Open Question #2)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages verified in source; no new dependencies
- Architecture: HIGH — all exact signatures read from source; patterns verified from Phase 11–13 implementations
- Backend endpoints: HIGH — all fields read from actual router.py and schemas.py
- Gradient token hex values: LOW — assumed brand-approximate colors; exact hex should be validated before commit
- Notification alert-categories shape: LOW — endpoint not confirmed to expose this field

**Research date:** 2026-06-02
**Valid until:** 2026-07-02 (stable — no external deps; codebase-only research)
