---
phase: 13-tickets-list-detail
plan: "05"
subsystem: frontend
tags: [drill-panel, generalization, tdd, ticket-drill, D-D-01, D-D-02]
dependency_graph:
  requires:
    - Plan 04 (ProviderMark, StatusPill, SlaPill from components/tickets)
  provides:
    - Generalized DrillPanel/DrillPanelMobile with idKey/renderContent/ariaLabel slot props
    - TicketDrillContent component (D-D-01 — header/body/footer composing Plan 04 primitives)
    - TicketDrillData type (Plan 07 list page contract)
  affects:
    - Plan 07 (tickets list page opens drill with idKey="ticket" + renderContent=TicketDrillContent)
    - Plans 06/08 (renderBlockedToggle slot wired with real BlockedToggle)
tech_stack:
  added: []
  patterns:
    - Additive-only refactor (no forking) for shared chrome generalization (D-D-02)
    - Render-prop/slot injection (renderContent, renderBlockedToggle)
    - TDD RED/GREEN/REFACTOR per plan spec
    - Parameterized URL key (idKey ?? 'cve') for multi-entity drill panels
key_files:
  modified:
    - frontend/src/components/vulnerabilities/drill-panel.tsx
    - frontend/src/components/vulnerabilities/drill-panel-mobile.tsx
  created:
    - frontend/src/components/tickets/ticket-drill-content.tsx
    - frontend/src/components/tickets/ticket-drill-content.test.tsx
decisions:
  - DrillPanel chrome generalized additively (D-D-02) — idKey/id/renderContent/ariaLabel props with vuln-preserving defaults; cveId kept as back-compat alias
  - close() now deletes 'open' + active idKey (default 'cve'); ticket callers will pass idKey='ticket'
  - TicketDrillData type exported from ticket-drill-content.tsx for Plan 07 contract
  - renderBlockedToggle slot renders disabled placeholder when absent (Plan 06/08 wires real BlockedToggle)
  - No inline hex anywhere — severity glyph colors via text-severity-* Tailwind tokens
metrics:
  duration: "~10 minutes"
  completed: "2026-06-02"
  tasks_completed: 2
  tasks_total: 2
  tests_added: 15
  files_created: 2
  files_modified: 2
---

# Phase 13 Plan 05: Drill Panel Generalization + TicketDrillContent Summary

**One-liner:** DrillPanel/DrillPanelMobile chrome generalized additively with idKey/renderContent/ariaLabel slots (D-D-02, regression gate: 16 vuln tests unchanged) + TicketDrillContent composing ProviderMark/StatusPill/SlaPill for the D-D-01 header/body/footer with 15 tests green.

## What Was Built

### Task 1: Generalized DrillPanel + DrillPanelMobile chrome (additive refactor)

Both `drill-panel.tsx` and `drill-panel-mobile.tsx` received additive prop additions per D-D-02. The refactor is strictly additive — no default behaviors changed:

**New props:**
```ts
cveId?: string | null;       // back-compat alias (unchanged for vuln callers)
id?: string | null;          // generic entity id
idKey?: string;              // URL param key (default 'cve')
renderContent?: (args: { id: string; onClose: () => void }) => React.ReactNode;
ariaLabel?: string;          // default 'Vulnerability detail'
```

**Resolution logic:**
- `effectiveId = id ?? cveId ?? null` — vuln callers get their cveId transparently
- `key = idKey ?? 'cve'` — vuln URL contract `?cve=...` preserved by default
- `close()` deletes `'open'` + `key` — ticket callers passing `idKey='ticket'` will have `?ticket=` cleaned up
- `renderContent ? renderContent({ id: effectiveId, onClose: close }) : <DrillContent .../>` — DrillContent default when no slot provided

**Regression gate:** Existing `drill-panel.test.tsx` (9 tests) + `drill-panel-mobile.test.tsx` (7 tests) = 16 tests, all green, zero edits to those files.

### Task 2: TicketDrillContent (D-D-01)

`frontend/src/components/tickets/ticket-drill-content.tsx` implements the slot content for the shared DrillPanel chrome. Purely presentational — no data fetching.

**`TicketDrillData` type** (exported for Plan 07 contract):
```ts
type TicketDrillData = {
  provider: TicketProvider;
  externalId: string;
  title: string;
  externalUrl: string;         // backend-controlled (T-13-16)
  externalStatus: string | null;
  blocked: boolean;
  slaDueAt: string | null;
  description: string | null;
  linkedVulns: LinkedVuln[];   // top 3 by severity (caller pre-sorts)
  totalVulns: number;          // for +N more
};
```

**Header:** `<ProviderMark provider={...}/>` + `<span class="font-mono text-sm font-semibold">` external ID + truncated title (`truncate`) + `<button aria-label="Close">` with lucide `X`.

**Body — linked-vulns mini-list:** Maps `linkedVulns.slice(0,3)` into 28px rows: severity glyph (■▲◆○□ from visual-language.md) in `text-severity-*` class + CVE mono + CVSS score. `moreCount = totalVulns - slice.length`; if `> 0` renders `<Link href="/tickets/[id]">+{N} more</Link>`.

**Body — status/SLA/description:** `<StatusPill externalStatus={...} blocked={...}/>` + `<SlaPill dueAt={...}/>` row; description with `line-clamp-6`; `<Link>Show full →</Link>` to `/tickets/[id]`.

**Footer (sticky bottom):**
- `"Open in {provider}"` — `<a href={externalUrl} target="_blank" rel="noopener noreferrer">` (T-13-16)
- `"Open full detail"` — `<Link href="/tickets/[id]">` (gradient CTA)
- Blocked toggle slot — `renderBlockedToggle?.({ ticketId })` or disabled `"Mark blocked"` placeholder

**Copy:** "Open in Jira", "Open full detail" — peer-not-butler (copy-voice.md). No "Click to...".

## Tests

**15 new tests** in `ticket-drill-content.test.tsx` (TDD RED → GREEN):
- Header: ProviderMark aria-label, mono externalId, close button calls onClose, title in DOM
- Linked vulns: top-3 glyphs (■▲◆), CVE IDs, CVSS scores, "+N more" link to /tickets/[id], absent when ≤3
- Status/SLA: StatusPill "Open", SlaPill "Unknown" (null dueAt), description text, "Show full →" link href
- Footer: "Open in Jira" target=_blank rel=noopener noreferrer href, "Open full detail" href, disabled placeholder, custom renderBlockedToggle slot, provider name in copy

**Total 31 tests** passing (16 existing vuln regression gate + 15 new ticket drill tests).

## Threat Surface Scan

**T-13-16 mitigated:** `externalUrl` is a backend-controlled URL from the ticket connector. Rendered as `href` in a text node (`<a href={externalUrl}>`). React escapes text nodes; no `dangerouslySetInnerHTML`. `rel="noopener noreferrer"` applied.

**T-13-17:** `ticketId` prop is passed by the list row caller, not directly from URL params. The raw `?ticket=` URL param is consumed by the parent (DrillPanel) and passed as a typed prop — no class or var derived from the raw param.

**T-13-18 mitigated:** Additive-only refactor with vuln-preserving defaults. Existing vuln drill tests are the unmodified regression gate (16 tests, all green, no test file edits).

No new network endpoints, auth paths, file access patterns, or schema changes introduced.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

### Files exist:
- frontend/src/components/vulnerabilities/drill-panel.tsx: FOUND (modified)
- frontend/src/components/vulnerabilities/drill-panel-mobile.tsx: FOUND (modified)
- frontend/src/components/tickets/ticket-drill-content.tsx: FOUND (created)
- frontend/src/components/tickets/ticket-drill-content.test.tsx: FOUND (created)

### Commits:
- b108c53: refactor(13-05): generalize DrillPanel/DrillPanelMobile chrome (D-D-02 additive)
- 0cbb148: test(13-05): add failing tests for TicketDrillContent (D-D-01 RED)
- b47b3b3: feat(13-05): implement TicketDrillContent (D-D-01 GREEN)

## Self-Check: PASSED
