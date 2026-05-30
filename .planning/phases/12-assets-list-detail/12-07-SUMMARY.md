---
phase: 12-assets-list-detail
plan: 07
subsystem: frontend
tags: [ui, react, asset-detail, right-rail, reassign, mutation, combobox, optimistic-update]
dependency_graph:
  requires:
    - 12-03  # RiskRing + Avatar primitives
    - 12-05  # useAsset / useAssignableUsers / queryKeys.assets namespace
  provides:
    - "RiskCard composes RiskRing + 4 breakdown rows (Critical / SLA / KEV / Trend unavailable)"
    - "OwnerCard with flip-to-edit ReassignCombobox"
    - "ReassignCombobox bound to useAssignableUsers + useReassignAsset (D-A-01 contract)"
    - "useReassignAsset mutation hook with optimistic patch + rollback + toast"
  affects:
    - 12-08  # /assets/[id] page composes these three rail components
tech_stack:
  added: []
  patterns:
    - "Optimistic cache patch + snapshot rollback (Phase 11 mutation pattern extended)"
    - "Inline combobox flip-edit (no modal, D-A-01)"
    - "Hardcoded IDP_LABEL map for XSS-safe label mapping (T-12-04)"
    - "Debounce → debounced → query (250ms) layered with hook-level >=2-char gate (T-12-17 + W9)"
key_files:
  created:
    - frontend/src/lib/queries/use-reassign-asset.ts
    - frontend/src/lib/queries/use-reassign-asset.test.tsx
    - frontend/src/components/assets/risk-card.tsx
    - frontend/src/components/assets/risk-card.test.tsx
    - frontend/src/components/assets/owner-card.tsx
    - frontend/src/components/assets/owner-card.test.tsx
    - frontend/src/components/assets/reassign-combobox.tsx
    - frontend/src/components/assets/reassign-combobox.test.tsx
  modified: []
key_decisions:
  - "Trend row renders '—' + 'Trend unavailable' verbatim — no graph stub, no zero placeholder (locked_decisions item 2)"
  - "OwnerCard fallback hierarchy: display_name → assigned_user (email) → 'Unassigned'; role → 'Unassigned in directory' | 'No owner set'"
  - "IdP pill HIDDEN when directory_user is null (no orphan source label)"
  - "Email line suppressed when displayName equals assigned_user (avoids duplicate render in Pitfall 4 fallback)"
  - "Mutation emits toasts directly (not the consumer's responsibility) — single source for SC-6 confirmation surface"
metrics:
  duration: "~10min"
  completed: "2026-05-30"
  tasks_completed: 2
  files_created: 8
  lines_of_code: 452 # implementation only (4 .tsx/.ts), tests separate
  tests_passing: 24
---

# Phase 12 Plan 07: Asset Detail Rail Composition — Summary

Build the right-rail composition for `/assets/[id]` (UX-04-03 RiskCard + UX-04-04 OwnerCard with inline Reassign flow), plus the `useReassignAsset` mutation hook that powers the reassign optimistic-update flow.

## What ships

### Components

**`<RiskCard asset={AssetDetail} />`** (`frontend/src/components/assets/risk-card.tsx`)
- Composes `<RiskRing score={asset.risk_score} />` (Plan 12-03 primitive) inside a `bg-surface-2 / border-border-subtle` card with `aria-label="Risk score"`.
- 4 breakdown rows below the ring, in this locked order:
  1. **Critical** — mono `vuln_counts.critical`, tinted `text-severity-critical`
  2. **SLA breach** — mono `sla_breach`, tinted `text-severity-high` (amber)
  3. **KEV** — mono `vuln_counts.kev`, tinted `text-severity-medium` (pink)
  4. **Trend unavailable** — mono `"—"`, tinted `text-text-muted` (history table deferred)
- Edge cases: null `risk_score` → RiskRing shows "Risk unavailable"; missing `vuln_counts` → all counts default to `0`.

**`<OwnerCard asset={AssetDetail} />`** (`frontend/src/components/assets/owner-card.tsx`)
- Default mode: `<Avatar />` (40px) + display name + role + (conditional) email line + (conditional) IdP pill + "Reassign" button.
- Edit mode: renders `<ReassignCombobox />` inline; flip-back happens via the combobox's `onDone()` callback.
- Locked fallback hierarchy when `directory_user` is null (Pitfall 4):
  | Field         | Fallback                                                                          |
  |---------------|-----------------------------------------------------------------------------------|
  | `displayName` | `directory_user.display_name` → `assigned_user` (email) → `"Unassigned"`           |
  | `role`        | `directory_user.role` → `"Unassigned in directory"` (when email present) → `"No owner set"` |
  | IdP pill      | hidden when `directory_user.idp_source` is null                                   |
- Email line is suppressed when `displayName === assigned_user` (avoids duplicate-email render in the Pitfall 4 fallback case).
- `IdP_LABEL` map (T-12-04): `google` → `Google`, `azure` → `Azure`, `okta` → `Okta`, `humaans` → `Humaans`, `microsoft` → `Microsoft`, `local` → `Local`. Unknown sources fall through as raw text (no innerHTML, no eval).

**`<ReassignCombobox assetId initialEmail onDone />`** (`frontend/src/components/assets/reassign-combobox.tsx`)
- D-A-01 keyboard contract:
  - **Esc** → `onDone()`, no mutation.
  - **Enter** → mutate(`items[highlightIdx]?.email ?? input`), then `onDone()` on success.
  - **ArrowDown / ArrowUp** → move highlight within `items.length` window.
  - **Click outside** → `mousedown` listener on `document` calls `onDone()` (no mutation). Toast portal is intentionally not excluded — clicks on the toast cancel just like any other outside click; that's the desired UX (toast confirms, click anywhere else continues the analyst's flow).
- 250ms debounce on input → debounced state → `useAssignableUsers(debounced)`. Hook's own `enabled: search.length >= 2` gate (Plan 12-05) prevents first-focus directory dump (W9).
- Empty / loading / no-results states inline in the listbox (state-patterns.md compliance for this micro-surface).
- ARIA: `role="combobox"`, `role="listbox"`, `role="option"` + `aria-selected` tracks highlight; input has `aria-label="Search assignable users"`.
- Mutation pending → input disabled. Mutation error → inline `role="alert"` below input.

### Hook

**`useReassignAsset(assetId)`** (`frontend/src/lib/queries/use-reassign-asset.ts`)
- Returns a TanStack `useMutation` over `POST /api/v1/assets/{assetId}/owner` with body `{ assigned_user_email }`.
- `onMutate(email)`:
  1. `cancelQueries({ queryKey: queryKeys.assets.byId(assetId) })`
  2. snapshot current cache entry
  3. optimistically patch `assigned_user` to `email`
  4. return `{ snapshot }` for rollback
- `onError`: roll back via `setQueryData(snapshot)` + `toast({ variant: 'error', message: 'Could not reassign owner. Try again.' })`.
- `onSuccess(data)`:
  - `invalidateQueries({ queryKey: queryKeys.assets.byId(assetId) })`
  - `invalidateQueries({ queryKey: queryKeys.assets.all })`
  - `toast({ variant: 'success', message: 'Owner reassigned to <email>' })` (ROADMAP SC-6).
- `retry: 0` (BL-06 inheritance — POSTs must not silently re-fire; audit attribution > convenience).

## Contract for 12-08 wiring (asset detail page)

12-08 composes the rail like so:

```tsx
const { data: asset } = useAsset(id);
// ...page chrome, main column...
<aside className="space-y-4">
  <RiskCard asset={asset} />
  <OwnerCard asset={asset} />
  {/* IdentityCard / MetadataCard ship in 12-08 itself */}
</aside>
```

`<OwnerCard>` and `<RiskCard>` both expect the **full `AssetDetail`** shape from `useAsset` (Plan 12-05); they do not accept partials. If `useAsset` hasn't resolved yet, 12-08 is responsible for rendering a skeleton in this slot — neither card has its own loading state.

`<ReassignCombobox>` is exported but internal to OwnerCard's flow. 12-08 should NOT consume it directly.

## Threat mitigations applied (from 12-07-PLAN `<threat_model>`)

| Threat   | Where mitigated                                                                                                      |
|----------|----------------------------------------------------------------------------------------------------------------------|
| T-12-04 (XSS via Avatar / IdP label) | Avatar XSS guard inherited from Plan 12-03. IdpPill maps `source.toLowerCase()` through `IDP_LABEL`; unknown values render as raw text (no `dangerouslySetInnerHTML`). React escapes all text children by default. |
| T-12-08 (mass assignment via reassign body) | `useReassignAsset.mutationFn` posts ONLY `{ assigned_user_email }`. The implementation passes a literal `JSON.stringify({ assigned_user_email: email })` — no `{ ...formData }` spread. Backend `_AssetOwnerUpdate` Pydantic model from Plan 12-02 rejects extras. |
| T-12-09 (audit miss on owner change) | Backend writes `asset.owner_changed` (Plan 12-02). Frontend has no role. |
| T-12-17 (DoS via per-keystroke spam) | ReassignCombobox 250ms debounces input → `debounced` state → `useAssignableUsers(debounced)`. Hook's `enabled: search.length >= 2` gate trims trivial scans. |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plan pseudocode called `api.post(...)` but `api` is a function**

- **Found during:** Task 1 implementation.
- **Issue:** Plan's pseudocode body was `api.post(\`/api/v1/assets/${id}/owner\`, { assigned_user_email })`. The actual `api` export in `frontend/src/lib/api.ts` is a `function api<T>(path, options)` — there is no `.post` method.
- **Fix:** Translated to `api<T>(path, { method: 'POST', body: JSON.stringify({...}), headers: { 'Content-Type': 'application/json' } })` per the established Phase 10/11 mutation pattern (see `use-snooze.ts`, `use-create-ticket.ts`).
- **Files modified:** `frontend/src/lib/queries/use-reassign-asset.ts`
- **Commit:** 8b54da6

**2. [Rule 1 - Bug] Plan used the non-existent `text-text-subtle` token**

- **Found during:** Both tasks.
- **Issue:** Plan's pseudocode repeatedly references `text-text-subtle`. `tailwind.config.ts` defines only `text-text-muted` and `text-text-faint`. The UI guardrails block also explicitly flagged this: "Valid text tokens: `text-text-faint`, `text-text-muted` (NOT `text-text-subtle`)". RiskRing (Plan 12-03) made the same swap.
- **Fix:** All `text-text-subtle` swapped to `text-text-muted` (semantically closer than `text-text-faint`).
- **Files modified:** `risk-card.tsx`, `owner-card.tsx`, `reassign-combobox.tsx`
- **Commits:** 8b54da6, ecfe458

**3. [Rule 1 - Bug] Plan used Toast `variant: 'danger'` but the contract is `'error'`**

- **Found during:** Task 1.
- **Issue:** Plan said `toast({ variant: 'danger', ... })`. `ToastProvider` accepts only `"success" | "error" | "info"`.
- **Fix:** Swapped to `variant: 'error'`.
- **Files modified:** `use-reassign-asset.ts`
- **Commit:** 8b54da6

### Composition tweak (not a deviation per se)

OwnerCard suppresses the email-only line when `displayName === assigned_user`. The plan would have rendered the email both AS the display name AND on its own line in the Pitfall 4 fallback case (no `directory_user`). Now the email renders exactly once. The test asserts this explicitly (`owner-name.textContent === 'alice@example.com'`).

## Tests

24 tests total across 4 files, all passing:

| File                                 | Tests | Covers                                                                                  |
|--------------------------------------|-------|-----------------------------------------------------------------------------------------|
| `use-reassign-asset.test.tsx`        | 5     | POST body shape; invalidation key set; optimistic cache patch before resolve; rollback on error + error toast; success toast |
| `risk-card.test.tsx`                 | 5     | RiskRing aria-label; 4-row order/labels/counts; missing `vuln_counts` fallback; null score; region label |
| `owner-card.test.tsx`                | 6     | display chrome; null directory_user fallback; "Unassigned" + "No owner set"; flip-to-edit; onDone returns; IDP_LABEL mapping |
| `reassign-combobox.test.tsx`         | 8     | auto-focus; Esc cancels; Enter commits; mousedown outside cancels; ArrowDown highlight; click-option commits; empty-input hint; ARIA roles |

```bash
$ pnpm vitest run src/lib/queries/use-reassign-asset src/components/assets/risk-card src/components/assets/owner-card src/components/assets/reassign-combobox
Test Files  4 passed (4)
     Tests  24 passed (24)
```

## Verification

- [x] Tests pass: 24/24 green.
- [x] `pnpm tsc --noEmit` clean (no errors in this plan's files).
- [x] No raw hex codes in any of the 4 implementation files (`grep -rE '#[0-9a-fA-F]{6}'` returns empty).
- [x] Acceptance grep criteria from plan: all satisfied (POST endpoint ref, queryKeys.assets.byId ≥1, "Trend unavailable", BreakdownRow ≥5, ReassignCombobox import+render ≥2, idp_source ≥1, "Unassigned in directory" ≥1, Escape+Enter ≥2, mousedown ≥1, ARIA roles ≥3).

## Self-Check: PASSED

**Files exist:**
- ✓ `frontend/src/components/assets/risk-card.tsx`
- ✓ `frontend/src/components/assets/risk-card.test.tsx`
- ✓ `frontend/src/components/assets/owner-card.tsx`
- ✓ `frontend/src/components/assets/owner-card.test.tsx`
- ✓ `frontend/src/components/assets/reassign-combobox.tsx`
- ✓ `frontend/src/components/assets/reassign-combobox.test.tsx`
- ✓ `frontend/src/lib/queries/use-reassign-asset.ts`
- ✓ `frontend/src/lib/queries/use-reassign-asset.test.tsx`

**Commits exist:**
- ✓ `8b54da6` — feat(12-07): useReassignAsset + RiskCard with 4 breakdown rows
- ✓ `ecfe458` — feat(12-07): OwnerCard + ReassignCombobox (Esc/Enter/blur contract)
