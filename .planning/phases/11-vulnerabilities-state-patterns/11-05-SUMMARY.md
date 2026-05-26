---
phase: 11
plan: 05
subsystem: frontend / vulnerabilities-page components
tags: [frontend, vuln-page, components, wave-2, tdd-green]

dependency_graph:
  requires:
    - 11-02 (RED tests for chip-bar + view-toggle + vuln-table + drill-panel + drill-panel-mobile; vaul@1.1.2 pin)
    - 11-03 (useUrlStateList + useSavedFilters + useVulnerabilityDetail + useCreateTicketMutation + useSnoozeMutation)
    - 11-04 (state primitives — consumed by Plan 06, not Plan 05 directly)
  provides:
    - "@/components/vulnerabilities/chip-bar — facet-driven multi-value chip filter (severity/source) with 250ms search debounce + read-only saved-filter pill"
    - "@/components/vulnerabilities/view-toggle — By CVE / By Host segmented control bound to ?group="
    - "@/components/vulnerabilities/vuln-table — 7-column plain-semantic table with keyboard nav + stale-row tinting + cycle sort"
    - "@/components/vulnerabilities/drill-panel — desktop 420px right aside with URL-driven open/close + clickaway + Esc"
    - "@/components/vulnerabilities/drill-panel-mobile — vaul bottom-sheet variant gated on <900px"
    - "@/components/vulnerabilities/drill-content — shared 7-section content (Header / CVSS / Hosts / Description / Remediation / Activity / Actions)"
    - "@/components/vulnerabilities/microcopy — single source of vuln-page strings (copy-voice.md compliance)"
    - "@/hooks/use-media-query — SSR-safe matchMedia hook"
  affects:
    - Phase 11-06 (page rewrite) — consumes ALL of the above
    - Phase 12 (assets) — inherits ChipBar shape, DrillPanel pattern verbatim
    - Phase 13 (tickets) — inherits DrillPanel pattern verbatim

tech_stack:
  added: []  # vaul was already pinned by Plan 02
  patterns:
    - "Multi-value URL-driven filter chips via useUrlStateList (allow-list XSS clamp on read AND write)"
    - "250ms debounced search via useState + useEffect + setTimeout; chip clicks flush synchronously alongside via single URLSearchParams batch (Pitfall 10)"
    - "Plain <table> with tr[tabindex=0] for keyboard nav (Pitfall 5 — no role=grid)"
    - "Uncontrolled sort cycle (asc → desc → clear) using local state mirrored when no sort/order prop"
    - "URL-driven open/close for drill panel — open derived from ?open=drill; row-swap is a content-only update, never a URL flip"
    - "Mobile branch gated on useMediaQuery('(max-width: 899px)') — Pitfall 3 (desktop branch covers ≥900px)"
    - "Nested confirmation inside vaul drawer via Drawer.NestedRoot + plain role=dialog inner content (jsdom-compatible)"

key_files:
  created:
    - frontend/src/components/vulnerabilities/microcopy.ts
    - frontend/src/components/vulnerabilities/chip-bar.tsx
    - frontend/src/components/vulnerabilities/view-toggle.tsx
    - frontend/src/components/vulnerabilities/vuln-table.tsx
    - frontend/src/components/vulnerabilities/drill-content.tsx
    - frontend/src/components/vulnerabilities/drill-panel.tsx
    - frontend/src/components/vulnerabilities/drill-panel-mobile.tsx
    - frontend/src/hooks/use-media-query.ts
  modified: []

decisions:
  - "ChipBar uses lowercase severity tokens ('critical', 'high', ...) in the URL allow-list to match the Plan 02 RED test contract (`severity=critical`) and the vuln-table test data (row.severity = 'critical'). Backend payloads using uppercase enum values still map cleanly because the table's normalizeSeverity() lowercases before lookup."
  - "Severity / source chip rendering merges label + count into a single text node (`Critical · 12`) so the Plan 02 test `getByText(/Critical/).textContent.toContain('12')` passes. Separating the count into a sibling span breaks the deepest-text-element heuristic in testing-library."
  - "VulnTable uses an uncontrolled sort cycle (local state) when no sort/order prop is supplied. The Plan 02 test calls onSort and re-clicks without re-rendering with new props, so a purely-controlled implementation would always see sort=null and never cycle past 'asc'. The controlled path remains available for Plan 06's page wiring."
  - "VulnTable click target for sortable headers is the <th> itself (not an inner <button>). The Plan 02 test fires `fireEvent.click(cveHeader)` directly on the columnheader element; a button-inside-th would not receive that click."
  - "DrillContent uses a ref + useEffect to focus the close button on mount instead of the React `autoFocus` JSX prop. jsdom doesn't honor autoFocus consistently across React versions, so the test contract `expect(document.activeElement).toBe(close)` requires explicit focus()."
  - "DrillPanel mousedown listener attaches synchronously (no setTimeout(0) deferral). Pitfall 4 only matters when `open` is driven by a synchronous useState toggle in the same handler as the opening click; here `open` derives from `?open=drill` via router.replace, which is always a separate frame from the row click event."
  - "DrillPanelMobile returns null when not open (in addition to controlling vaul's open prop). vaul keeps focus-guard chrome mounted while open={false}, which leaks a residual role=dialog node and breaks the Plan 02 test contract `queryByRole('dialog')` === null after URL close."
  - "Nested confirmation inside the mobile drawer uses `Drawer.NestedRoot` wrapper with a plain `<div role=dialog>` inner content. jsdom doesn't promote Drawer.NestedRoot itself to a dialog node, so the second-dialog test contract requires the inner aside. In production this still gives gesture-inheritance from vaul."

metrics:
  duration: "~20 minutes"
  completed_date: "2026-05-26"
  tasks_completed: 3
  files_created: 8
  files_modified: 0
  total_commits: 3
  red_tests_to_green: 41
---

# Phase 11 Plan 05: Vulnerabilities-Page Component Family Summary

Ship the user-visible chip-bar / view-toggle / table / drill-panel components that close UX-03-01..06. All 41 RED tests from Plan 02 Task 04 (5 component test files: chip-bar, view-toggle, vuln-table, drill-panel, drill-panel-mobile) turn GREEN against the locked Phase 11 visual / interaction / a11y / keyboard / copy-voice contracts.

## Locked API surface (Phase 11-06 consumes these verbatim)

### `ChipBar` — UX-03-01 + D-F-01/02/03/05

```typescript
export type ChipBarFacets = {
  severity: Record<string, number>;
  source: Record<string, number>;
  status?: Record<string, number>;
};
export function ChipBar(props: { facets: ChipBarFacets }): JSX.Element;
```

- Searchbox (`role="search"` parent + `type="search"` input) with 250ms debounce on the URL flush. Each keystroke resets the debounce window via `setTimeout` cleanup.
- 5 severity chips (`critical`/`high`/`medium`/`low`/`info`) — synchronous click → URL flip via `useUrlStateList('severity', SEVERITIES, [])`. The Unicode glyph + label + count render as a single text node so the test's `getByText(/Critical/).textContent.toContain('12')` passes.
- Source chips rendered from `Object.keys(facets.source)` (D-F-03 — derived, not hardcoded). XSS clamp held by `useUrlStateList`'s allow-list on both read and write (T-11-17 mitigation).
- Saved-filter pill (D-F-04) — read-only; renders only when `useSavedFilters().data?.[0]` exists. Pill writes loaded blob via merged URLSearchParams (each value still re-validated on the next render).
- Clear all wipes severity / source / status / search atomically via one `router.replace` (T-11-19 race mitigation — single setter call carries all clears together).

### `ViewToggle` — D-V-01

```typescript
export function ViewToggle(): JSX.Element;
```

- Two `<button>` segments (`aria-pressed` toggled by current `?group=` value) — clicking the inactive segment fires `useUrlState('group', ['cve','host'], 'cve')` setter.
- Switching only mutates `?group=`; severity / source / status / search keys are independent URL keys and survive the toggle by construction.

### `VulnTable` — UX-03-02 + UX-07-03 + D-V-04

```typescript
export type VulnTableSortField = 'severity' | 'cve_id' | 'cvss_v3_score' | 'sla_due_at' | null;
export type VulnTableSortOrder = 'asc' | 'desc' | null;
export type VulnTableRow = { /* loose row shape; accepts both test and backend payloads */ };
export function VulnTable(props: {
  rows: VulnTableRow[];
  sort?: VulnTableSortField;     // controlled mode (Plan 06 wires ?sort=)
  order?: 'asc' | 'desc' | null; // controlled mode (Plan 06 wires ?order=)
  onSort: (field: VulnTableSortField, order: VulnTableSortOrder) => void;
  onRowOpen: (idOrCve: string) => void;
  failedSources?: string[];
}): JSX.Element;
```

- 7 columns: Severity / CVE / Title / Asset / CVSS / Status / SLA. Plain semantic `<table>` — no `role=grid` (Pitfall 5).
- Sticky `<thead>`: `sticky top-0 z-10 bg-surface` (D-T-04).
- Sortable cycle on 4 columns (Severity / CVE / CVSS / SLA): asc → desc → clear (null, null). Click target is the `<th>` itself so the test's `fireEvent.click(cveHeader)` flows.
- Severity cell renders Unicode glyph (`■▲◆○□`) colored by token + capitalized label inside a pill.
- CVE cell: `data-col="cve"` + `font-mono`.
- SLA cell: `data-col="sla"` + `font-mono text-right` + 3-tier tone (overdue=critical / soon=high / ok=success).
- KEV badge inline in Status when `row.cisa_kev=true`; exploit-available badge when `row.exploit_available=true`.
- Row keyboard nav per RESEARCH §Pattern 6 — `tr[tabindex=0]`: ArrowDown/Up move row-to-row, Home/End jump first/last, Enter/Space fire `onRowOpen(row.cve_id ?? row.id)`. Click also opens.
- Stale-row tinting (D-V-04): `failedSources.includes(row.source)` → `data-stale="true"` + `bg-amber-soft`.

### `DrillPanel` — UX-03-03 + D-P-01/02/05/06 (desktop)

```typescript
export function DrillPanel(props: {
  cveId: string | null;
  originRowRef?: React.RefObject<HTMLElement | null> | null;
}): JSX.Element | null;
```

- Fixed right-aside, `w-[420px]`, `data-drill-panel` marker (testable selector).
- Open derived from URL `?open=drill` (D-P-02). Row-swap is a content-only update (new `cveId` prop) and NEVER calls `router.replace`.
- D-P-01 close paths: × button onClick / Esc keydown on document / mousedown outside the panel — all delete `?open=drill&cve=…` via one `router.replace` call.
- D-P-06: focus moves to close button on mount via `closeBtnRef.current.focus()`; on close, focus returns to `originRowRef.current`.

### `DrillPanelMobile` — UX-03-06 + D-P-03 (vaul)

```typescript
export function DrillPanelMobile(props: { cveId: string | null }): JSX.Element | null;
```

- Gated on `useMediaQuery('(max-width: 899px)')` (Pitfall 3) — returns null at ≥900px so the desktop branch handles those viewports.
- Returns null when `open=false` (in addition to vaul's `open` prop) so vaul's focus-guard chrome doesn't leak a residual `role=dialog` node.
- Wraps shared `DrillContent` inside `Drawer.Root` + `Drawer.Portal` + `Drawer.Overlay` + `Drawer.Content` (`direction="bottom"`, `h-[92dvh]`).
- Esc closes via document keydown listener (parity with desktop) + vaul native handling. Both paths route through the same `close()` → `router.replace` URL flip.
- Nested confirm uses `Drawer.NestedRoot` wrapper containing a plain `<div role="dialog">` (Pitfall 7 — jsdom doesn't always promote NestedRoot itself to dialog).

### `DrillContent` — D-P-05 (shared)

```typescript
export const DrillContent: ForwardRefExoticComponent<{
  idOrCve: string;
  onClose: () => void;
  renderConfirm?: (args: {
    open: boolean;
    onConfirm: () => void;
    onCancel: () => void;
    cveLabel: string;
  }) => React.ReactNode;
} & RefAttributes<HTMLDivElement>>;
```

- Header (CVE label as `<h3>` mono) + severity pill + KEV/exploit badges.
- Six section `<h4>` blocks in D-P-05 order: CVSS / Affected hosts / Description / Remediation / Activity / Actions.
- Actions: gradient `btn-cta` "Create ticket" (gated by ConfirmModal or `renderConfirm` slot) + secondary "Snooze 24h" wired to `useCreateTicketMutation` + `useSnoozeMutation`.
- Pending state → `aria-busy="true"` loader; error → `role="alert"` inline message.

### `useMediaQuery` — D-P-03 driver

```typescript
export function useMediaQuery(query: string): boolean;
```

- SSR-safe: returns `false` on server / first client render.
- Subscribes via `mql.addEventListener('change', handler)`.

## Keyboard-nav coverage map (D-T-02 + UX-07-03 slice)

| Element | Key | Behavior |
|---|---|---|
| `<tr tabindex="0">` (any body row) | `ArrowDown` | Focus next `tr[tabindex=0]`; clamped at last row |
| `<tr tabindex="0">` | `ArrowUp` | Focus previous; clamped at first row |
| `<tr tabindex="0">` | `Home` | Focus first body row |
| `<tr tabindex="0">` | `End` | Focus last body row |
| `<tr tabindex="0">` | `Enter` / `Space` | `e.preventDefault()` + fire `onRowOpen(row.cve_id ?? row.id)` |
| `<th>` sort header | `Click` | Cycle this column's sort: asc → desc → clear |
| ChipBar chip `<button>` | `Click` / native `Enter`+`Space` | Toggle multi-value URL state via `useUrlStateList` |
| ViewToggle `<button>` | `Click` / native `Enter`+`Space` | Set `?group=` |
| DrillPanel close `<button>` | `Click` | Close panel + return focus to `originRowRef` |
| DrillContent close `<button>` | `Tab` | Focus next interactive inside the panel (minimal focus trap) |
| Document (while panel open) | `Escape` | Close panel |

## Focus-management trace for D-P-06

1. User clicks row → page-level handler sets `?cve=…&open=drill` (Plan 06 wires this).
2. URL change triggers `DrillPanel` to derive `isOpen=true` and mount.
3. `DrillContent` mounts; `closeBtnRef.current.focus()` runs in `useEffect` → close button receives focus.
4. User presses Esc / clicks ×  / mouses-down outside / clicks another row.
5. `close()` removes `?open=drill&cve=…` from URL via `router.replace`.
6. `DrillPanel` derives `isOpen=false`, unmounts; `originRowRef?.current?.focus()` returns focus to the row that originated the open.

## Pitfall mitigations applied

| Pitfall | Mitigation present |
|---|---|
| Pitfall 5 (no `role=grid`) | VulnTable renders plain `<table><thead><tbody>` only; verified by grep returning zero `role="grid"` matches. |
| Pitfall 6 (saved-filter shape drift) | ChipBar applies saved filters via URLSearchParams merge; useUrlStateList read-side allow-list still clamps each value on the next render (T-11-17). |
| Pitfall 7 (vaul Esc cascade) | DrillPanelMobile installs document-level Esc listener while open (parity with desktop) AND uses Drawer.NestedRoot for the nested confirm — both paths route through the same `close()` URL flip. |
| Pitfall 10 (debounce-chip race / T-11-19) | Chip toggles fire synchronously through `useUrlStateList` which writes one URLSearchParams batch via `router.replace`. The pending search debounce, if any, sees `searchInput === lastFlushedRef.current` after the round-trip and no-ops. Clear all wipes all four keys (severity/source/status/search) in one setter call. |
| Pitfall 3 (mobile vs desktop branch double-mount) | DrillPanelMobile returns `null` at ≥900px (`useMediaQuery` false); DrillPanel covers ≥900px from the page-level wire-up. No viewport renders both. |

## Threat mitigations applied (from plan threat_model)

| Threat | Mitigation present |
|---|---|
| T-11-17 (saved-filter blob shape drift) | useUrlStateList's allow-list re-validates each value on read; v1 param names not in SEVERITIES/SOURCES are silently dropped. |
| T-11-18 (DoS via per-keystroke URL update) | Explicit 250ms debounce via `useEffect + setTimeout` with cleanup-cancel on the next keystroke. |
| T-11-19 (debounce-chip race) | Chip clicks bypass the debounce entirely (synchronous router.replace via useUrlStateList). Clear all writes one batch carrying all key deletions atomically. |
| T-11-20 (DrillPanel destroys focus on close) | `originRowRef.current.focus()` runs in `close()` after `router.replace`; D-P-06 trace verified in test 6 of drill-panel.test.tsx. |

## Verification

```
$ cd frontend && npx vitest run src/components/vulnerabilities/ --reporter=dot

 Test Files  5 passed (5)
      Tests  41 passed (41)

# Breakdown:
# - chip-bar.test.tsx          7 GREEN
# - view-toggle.test.tsx       5 GREEN
# - vuln-table.test.tsx       13 GREEN
# - drill-panel.test.tsx      10 GREEN
# - drill-panel-mobile.test.tsx 6 GREEN
```

Full vitest suite: 48 / 49 files pass. The 1 failing file is `src/app/(authed)/dashboard/vulnerabilities/page.test.tsx` — owned by Plan 11-06 (page rewrite, next wave). No Phase 9 / Phase 10 / Phase 11-Wave1 regressions.

Acceptance criteria sweeps:

```bash
$ grep -i 'welcome\|please\|click here\|!' frontend/src/components/vulnerabilities/microcopy.ts | wc -l
0
$ grep "useUrlStateList" frontend/src/components/vulnerabilities/chip-bar.tsx | wc -l   # >= 1
8
$ grep "250" frontend/src/components/vulnerabilities/chip-bar.tsx | wc -l               # >= 1
3
$ grep "tabIndex={0}" frontend/src/components/vulnerabilities/vuln-table.tsx
              tabIndex={0}
$ grep -c "ArrowDown\|ArrowUp\|Home\|End\|Enter" frontend/src/components/vulnerabilities/vuln-table.tsx
6
$ grep "role=\"grid\"" frontend/src/components/vulnerabilities/vuln-table.tsx
(no matches)
$ grep "w-\[420px\]" frontend/src/components/vulnerabilities/drill-panel.tsx
      className="fixed right-0 top-0 z-30 h-full w-[420px] border-l border-border bg-surface shadow-elevated"
$ grep "Drawer.Root\|from 'vaul'" frontend/src/components/vulnerabilities/drill-panel-mobile.tsx | wc -l  # >= 2
3
$ grep "max-width: 899" frontend/src/components/vulnerabilities/drill-panel-mobile.tsx
  const isMobile = useMediaQuery('(max-width: 899px)');
$ grep -r '!important' frontend/src/components/vulnerabilities/*.tsx frontend/src/components/vulnerabilities/*.ts
(no matches)
$ grep -rE '#[0-9a-fA-F]{6}|bg-red-[0-9]+|text-emerald-[0-9]+|bg-gray-[0-9]+|bg-indigo-[0-9]+' \
    frontend/src/components/vulnerabilities/chip-bar.tsx \
    frontend/src/components/vulnerabilities/view-toggle.tsx \
    frontend/src/components/vulnerabilities/vuln-table.tsx \
    frontend/src/components/vulnerabilities/drill-content.tsx \
    frontend/src/components/vulnerabilities/drill-panel.tsx \
    frontend/src/components/vulnerabilities/drill-panel-mobile.tsx \
    frontend/src/components/vulnerabilities/microcopy.ts
(no matches)
```

## Commits

| Task | Commit | Message |
|------|--------|---------|
| 11-05-01 | `24a2375` | `feat(11-05): microcopy + useMediaQuery + ChipBar + ViewToggle GREEN` |
| 11-05-02 | `d33e0de` | `feat(11-05): VulnTable with 7 columns + keyboard nav + stale-row tinting GREEN` |
| 11-05-03 | `760d6eb` | `feat(11-05): DrillContent + DrillPanel desktop + DrillPanelMobile (vaul) GREEN` |

## Deviations from Plan

### Auto-fixed (Rule 1 — Bug-shaped contract drift between plan outline and canonical RED tests)

**1. [Rule 1] VulnTable callback shape: `onSort` not `onSortChange`**
- **Found during:** Task 11-05-02
- **Issue:** Plan outline named the sort callback `onSortChange`; the Plan 02 RED test exports `onSort` and asserts `onSort.toHaveBeenCalledWith('cve_id', 'asc')`. The canonical test is the locked contract.
- **Fix:** Renamed prop to `onSort: (field, order) => void` matching the test.
- **Files modified:** `frontend/src/components/vulnerabilities/vuln-table.tsx`
- **Commit:** `d33e0de`

**2. [Rule 1] VulnTable sort cycle requires local state when uncontrolled**
- **Found during:** Task 11-05-02 (after first test run — 12/13 pass)
- **Issue:** Plan outline used purely-controlled `sort/order` props. The Plan 02 RED test calls `onSort` three times without re-rendering with updated props; a purely-controlled implementation always sees `sort=null, order=null` and always emits `(clicked, 'asc')`.
- **Fix:** Added local `useState` mirrors that update on each click in uncontrolled mode (when `sortProp === undefined`). Controlled mode (Plan 06 page wiring) still honors props if supplied.
- **Files modified:** `frontend/src/components/vulnerabilities/vuln-table.tsx`
- **Commit:** `d33e0de`

**3. [Rule 1] ChipBar severity label + count must share a single text node**
- **Found during:** Task 11-05-01 (after first test run — 11/12 pass)
- **Issue:** Plan outline rendered label and count in sibling `<span>` elements. The Plan 02 RED test `getByText(/Critical/).textContent.toContain('12')` finds the deepest matching element — when label and count are siblings, the `<span>Critical</span>` is the deepest match and its textContent is just "Critical".
- **Fix:** Merged label + ` · ` + count into a single text node inside one `<span>` (`Critical · 12`). Source chip uses the same pattern.
- **Files modified:** `frontend/src/components/vulnerabilities/chip-bar.tsx`
- **Commit:** `24a2375`

**4. [Rule 1] DrillPanel mousedown listener must attach synchronously**
- **Found during:** Task 11-05-03 (after first test run — 12/16 pass)
- **Issue:** Plan outline deferred the outside-click `mousedown` listener via `setTimeout(0)` to "avoid the same-tick opening click closing the panel." The Plan 02 RED test fires `fireEvent.mouseDown` immediately after render; the deferred listener hasn't attached yet.
- **Fix:** Attach `mousedown` listener synchronously while `isOpen`. Pitfall 4 only matters when `open` is driven by a synchronous useState toggle in the same handler as the opening click; here `open` derives from `?open=drill` via `router.replace`, a separate frame from the row click.
- **Files modified:** `frontend/src/components/vulnerabilities/drill-panel.tsx`
- **Commit:** `760d6eb`

**5. [Rule 1] DrillContent uses ref + useEffect for initial focus, not `autoFocus` JSX prop**
- **Found during:** Task 11-05-03 (initial draft)
- **Issue:** Plan outline used the React `autoFocus` JSX prop. jsdom doesn't honor `autoFocus` consistently across React versions; the test's `expect(document.activeElement).toBe(close)` is brittle against it.
- **Fix:** `closeBtnRef.current?.focus()` inside `useEffect(() => {...}, [idOrCve])`.
- **Files modified:** `frontend/src/components/vulnerabilities/drill-content.tsx`
- **Commit:** `760d6eb`

**6. [Rule 1] DrillPanelMobile must return null when open=false (in addition to vaul prop)**
- **Found during:** Task 11-05-03 (after first test run)
- **Issue:** vaul's `Drawer.Root` with `open={false}` keeps focus-guard chrome mounted (a `[data-radix-focus-guard]` span and sometimes a `role="dialog"` stub). The Plan 02 RED test asserts `queryByRole('dialog')` === null after the URL flips closed.
- **Fix:** Added an early `if (!open) return null` before rendering `Drawer.Root`, so the entire portal stays unmounted.
- **Files modified:** `frontend/src/components/vulnerabilities/drill-panel-mobile.tsx`
- **Commit:** `760d6eb`

**7. [Rule 1] Nested confirm uses Drawer.NestedRoot + inner role=dialog (not Drawer.Content alone)**
- **Found during:** Task 11-05-03 (after first test run)
- **Issue:** Plan outline used `Drawer.NestedRoot` + `Drawer.Content` for the nested confirmation. jsdom doesn't reliably promote `Drawer.NestedRoot` itself to a `role="dialog"` node, so the test's `getAllByRole('dialog').length >= 2` fails (only 1 dialog visible).
- **Fix:** Wrapped a plain `<div role="dialog">` inside `Drawer.NestedRoot`. In production this still inherits vaul gestures; in jsdom it guarantees the second-dialog contract.
- **Files modified:** `frontend/src/components/vulnerabilities/drill-panel-mobile.tsx`
- **Commit:** `760d6eb`

**8. [Rule 1] ChipBar severity URL allow-list uses lowercase tokens**
- **Found during:** Task 11-05-01 (when reading the test)
- **Issue:** Plan outline had `SEVERITIES = ['CRITICAL', 'HIGH', ...]` uppercase. The Plan 02 RED test asserts `expect(target).toContain('severity=critical')` (lowercase) and the vuln-table test data uses `severity: 'critical'` (lowercase). Uppercase tokens would be clamped by the XSS allow-list on write.
- **Fix:** Switched to lowercase severity tokens. VulnTable's `normalizeSeverity()` lowercases backend payloads before lookup, so uppercase enum values from `/api/v1/vulnerabilities` still render correctly.
- **Files modified:** `frontend/src/components/vulnerabilities/chip-bar.tsx`, `frontend/src/components/vulnerabilities/vuln-table.tsx`
- **Commits:** `24a2375`, `d33e0de`

### Auto-fixed (Rule 3 — Blocking issue)

**9. [Rule 3] Worktree base needed rebase onto 48b2c1b**
- **Found during:** Worktree startup
- **Issue:** Worktree HEAD was at `4d8b1974` (pre-Wave-1 / pre-Wave-0 merge). Expected base `48b2c1b…` (post-Wave-1 merge) carries Plans 02, 03, 04 outputs that Plan 05 depends on.
- **Fix:** `git rebase --onto 48b2c1b…` then `git checkout -B worktree-agent-…` to reattach the branch pointer. `node_modules` was empty; ran `npm ci --legacy-peer-deps` to install (including the vaul@1.1.2 pin from Plan 02).
- **Files modified:** none (pure git/npm housekeeping).
- **Commit:** none.

**No Rule 2 / Rule 4 deviations.** No architectural changes proposed. All threat-model mitigations from the plan are implemented (T-11-17 / 18 / 19 / 20).

### Auth gates

None encountered.

### Deferred Issues

None. All 41 RED tests in scope are GREEN. The 8 failing tests in `src/app/(authed)/dashboard/vulnerabilities/page.test.tsx` are owned by Plan 11-06 (next wave) — they import the page module that Plan 06 will create.

## Self-Check: PASSED

Verified inline:

- `frontend/src/components/vulnerabilities/microcopy.ts` exists (FOUND)
- `frontend/src/components/vulnerabilities/chip-bar.tsx` exists (FOUND)
- `frontend/src/components/vulnerabilities/view-toggle.tsx` exists (FOUND)
- `frontend/src/components/vulnerabilities/vuln-table.tsx` exists (FOUND)
- `frontend/src/components/vulnerabilities/drill-content.tsx` exists (FOUND)
- `frontend/src/components/vulnerabilities/drill-panel.tsx` exists (FOUND)
- `frontend/src/components/vulnerabilities/drill-panel-mobile.tsx` exists (FOUND)
- `frontend/src/hooks/use-media-query.ts` exists (FOUND)
- Commit `24a2375` (Task 1) — FOUND in `git log`
- Commit `d33e0de` (Task 2) — FOUND in `git log`
- Commit `760d6eb` (Task 3) — FOUND in `git log`
- `npx vitest run src/components/vulnerabilities/` — Test Files 5 passed, Tests 41 passed.

## Threat Flags

None — Plan 05 introduces no new network endpoints, auth paths, or schema changes. All chip/drill consumer surfaces route through Wave 1's already-threat-modeled hooks / queries / mutations (Plan 03 covered T-11-06/07/13/14 + BL-06 401 surface for ticket creation).
