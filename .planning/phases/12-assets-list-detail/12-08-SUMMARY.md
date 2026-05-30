---
phase: 12-assets-list-detail
plan: 08
subsystem: frontend/assets-detail-page
tags: [ux-04-02, ux-04-05, drill-panel-reuse, two-column-detail, severity-ribbon, timeline]
requires:
  - 12-03  # Breadcrumb primitive
  - 12-05  # useAsset / useAssetVulnerabilities / useAssetRemediations
  - 12-07  # RiskCard + OwnerCard (stubbed locally; orchestrator merges real impls)
provides:
  - SeverityRibbon                # ■N · ▲N · ◆N · ○N · □N main-column header
  - AssetVulnsList                # role=table compact vuln rows with keyboard nav + URL drill
  - RemediationTimeline           # ordered timeline with provider mark + status pill + relative ts
  - IdentityMetadataRail          # host metadata block for the right rail
  - "/assets/[id] two-column page composition (page.tsx rewrite)"
affects:
  - frontend/src/app/(authed)/dashboard/assets/[id]/page.tsx  # v1 292-line rewrite -> 244-line composition
  - frontend/src/components/assets/risk-card.tsx              # STUB (12-07 will replace)
  - frontend/src/components/assets/owner-card.tsx             # STUB (12-07 will replace)
tech-stack:
  added: []
  patterns:
    - "Phase 11 DrillPanel + DrillPanelMobile reuse verbatim (D-D-03) — page only passes cveId; the panel reads ?open=drill from the URL itself"
    - "URL-driven drill open contract: row click -> router.replace + ?cve=<id>&open=drill (Phase 11 D-P-02)"
    - "min-[900px]:grid-cols-[1fr_340px] gate locked to match Phase 11 D-P-03 drill-panel mobile threshold (rail splits exactly when drill panel switches from bottom-sheet to right-aside)"
    - "Per-section partial degradation: each section uses Phase 11 state primitives (SkeletonTable / EmptyState / PartialFailureBanner) independently — D-D-01"
    - "Glyph + count merged in a single text node for severity ribbon (Phase 11 chip-bar lesson — testing-library deep-text matching)"
    - "relativeTimestamp() clamps future timestamps to 'just now' (W8 clock-skew defense)"
    - "Provider gradient marks as scoped inline-style backgrounds (sketch 005 variant B documented exception to no-raw-hex rule)"
key-files:
  created:
    - frontend/src/components/assets/severity-ribbon.tsx
    - frontend/src/components/assets/severity-ribbon.test.tsx
    - frontend/src/components/assets/asset-vulns-list.tsx
    - frontend/src/components/assets/asset-vulns-list.test.tsx
    - frontend/src/components/assets/remediation-timeline.tsx
    - frontend/src/components/assets/remediation-timeline.test.tsx
    - frontend/src/components/assets/identity-metadata-rail.tsx
    - frontend/src/components/assets/identity-metadata-rail.test.tsx
    - frontend/src/components/assets/risk-card.tsx               # STUB for 12-07 merge
    - frontend/src/components/assets/owner-card.tsx              # STUB for 12-07 merge
    - frontend/src/app/(authed)/dashboard/assets/[id]/page.test.tsx
  modified:
    - frontend/src/app/(authed)/dashboard/assets/[id]/page.tsx   # full rewrite
decisions:
  - "Two-column layout locked at min-[900px]:grid-cols-[1fr_340px]. The 900px gate matches Phase 11 D-P-03 — the drill panel switches from bottom-sheet to right-aside at the same breakpoint, so the rail and the drill surface stay in sync. Phase 13 /tickets/[id] should reuse the same grid template + 900px gate for the same reason."
  - "Drill open contract is the Phase 11 D-P-02 URL contract (?cve=<id>&open=drill via router.replace). The page builds a fresh URLSearchParams from the current params each row click so any pre-existing query keys (e.g., remediation filters added later) are preserved."
  - "text-text-subtle (used in the original plan code) is NOT a configured tailwind token. Substituted with text-text-faint everywhere — matches the project-wide convention from RiskRing.tsx / Breadcrumb.tsx / assets-table.tsx (all three carry an inline comment documenting the same substitution)."
  - "RiskCard + OwnerCard files in this worktree are STUBS. Plan 12-07 ships in a parallel worktree; the orchestrator merges 12-07 before 12-08. Both stubs render data-testid='risk-card' / 'owner-card' so the /assets/[id] composition test asserts on the rail shape even before the real components arrive."
  - "Provider gradient marks (JIRA blue, ASANA coral, GITHUB violet) use inline-style backgrounds with explicit hex stops. These are sketch-scoped (sketch 005 variant B) and are excluded from the verification §5 no-raw-hex grep. Unknown providers fall back to a gray gradient."
  - "Page uses pnpm SkeletonTable's `rows={n}` prop (NOT `rowCount` — the plan code carried a typo that didn't match the SkeletonTable signature). Fixed during execution as a Rule 1 inline bug; tsc clean confirms the contract."
metrics:
  duration: "~9m"
  completed: "2026-05-30"
  tasks: 3
  files: 10
---

# Phase 12 Plan 08: /assets/[id] Two-Column Detail Page Summary

One-liner — Shipped the marquee UX-04-02 detail page: four new main-column components (`SeverityRibbon` / `AssetVulnsList` / `RemediationTimeline` / `IdentityMetadataRail`) plus the page composition that wires them with the 12-07 rail and reuses Phase 11's `DrillPanel` verbatim via the `?cve=<id>&open=drill` URL contract. The v1 292-line ad-hoc page (raw hex, mixed tabs, no state primitives) is replaced by a 244-line composition that honors UX-04-02 + UX-04-05.

## What Shipped

### `frontend/src/components/assets/severity-ribbon.tsx`

Single horizontal row of `■N · ▲N · ◆N · ○N · □N` for the main column header. Each glyph + count renders in a single text node so `getByTestId('ribbon-critical').textContent === '■2'` works without whitespace fudging (Phase 11 chip-bar lesson). Zero-count entries are dimmed with `text-text-faint`; non-zero entries pick up the matching severity tint (`text-severity-critical` / `-high` / `-medium` / `-low` / `-info`). Per-entry `aria-label={n} {Label}` so screen readers announce each band.

### `frontend/src/components/assets/asset-vulns-list.tsx`

Compact rows for vulnerabilities on the current host: severity glyph + tint, CVE id (mono), title (truncated), CVSS score (mono), and a KEV badge for `cisa_kev` rows. Each row is `role="row" tabindex="0"`; keyboard nav matches Phase 11 VulnTable (ArrowDown/Up navigate, Enter / Space activate). Empty list returns `null` — the page composes the `EmptyState` shell instead so the component stays focused on the list shape.

### `frontend/src/components/assets/remediation-timeline.tsx`

Vertical `<ol>` of timeline rows ordered by `ticket_created_at` desc (locked_decisions item 4 — the backend route already emits rows in that order). Each row:

- Provider gradient mark (Jira blue, Asana coral, GitHub violet; gray fallback for unknown providers) — sketch-scoped inline-style backgrounds excluded from the no-raw-hex verification grep
- Ticket title rendered as `<a target="_blank" rel="noreferrer">` when `external_ticket_url` is present, plain text otherwise
- Relative timestamp via local `relativeTimestamp()` — clamps future timestamps to `just now` (W8 clock-skew defense) and returns `—` for null / unparseable input
- Status pill with tone keyed off `external_status` (OPEN / IN_PROGRESS / RESOLVED / CLOSED) with neutral fallback

### `frontend/src/components/assets/identity-metadata-rail.tsx`

Right-rail block of host metadata rendered as `<section role="region" aria-label="Host metadata">`. Stacked rows for Hostname / IP / MAC / OS / Serial / Model / Managed by / Last check-in / Department / Building — each row skips itself when its value is null / undefined / empty string, so the rail visually shrinks when data is sparse. Identifier columns (hostname, IP, MAC, serial, last check-in) render in mono; descriptive columns (OS, model, managed_by, department, building) render in proportional.

### `frontend/src/app/(authed)/dashboard/assets/[id]/page.tsx` (rewrite)

Two-column composition wrapped in `ErrorBoundary` + `Suspense`:

```
                    ┌─ main ────────────────┬─ rail 340px ──┐
                    │ Breadcrumb            │ RiskCard      │
                    │ H1 hostname + tags    │ OwnerCard     │
                    │ SeverityRibbon        │ Identity-     │
                    │ AssetVulnsList        │   Metadata    │
                    │ RemediationTimeline   │               │
                    └───────────────────────┴───────────────┘
                       (grid splits at min-[900px])

       <DrillPanel cveId={cveId} originRowRef={null} />     <-- desktop (Phase 11)
       <DrillPanelMobile cveId={cveId} />                   <-- vaul sheet <900px
```

Three independent TanStack hooks (`useAsset` / `useAssetVulnerabilities` / `useAssetRemediations`) each drive their own section's loading / empty / error state via Phase 11 primitives. Asset-level error (no detail object) gates the entire page behind a `PartialFailureBanner`; the per-section failures degrade independently (D-D-01).

Row click handler (`onRowOpen`):

```ts
const sp = new URLSearchParams(params?.toString() ?? '');
sp.set('cve', cveOrId);
sp.set('open', 'drill');
router.replace(`${pathname}?${sp.toString()}`, { scroll: false });
```

The DrillPanel reads `?open=drill` from the URL itself (Phase 11 D-P-02), so the page only feeds the `cveId` through. Esc / clickaway / × all flip the URL back via `router.replace`, which collapses the panel.

### Local stubs: `risk-card.tsx` + `owner-card.tsx`

The 12-07 components live in a parallel worktree. Local stubs expose the documented prop contract (`asset: AssetDetail`) and render `data-testid="risk-card"` / `"owner-card"` so the page composition test asserts on the rail before 12-07 merges. The orchestrator will replace these stubs at merge time; see [Known Stubs](#known-stubs).

## Tests

| File                                | Cases | Coverage |
| ----------------------------------- | -----:| -------- |
| severity-ribbon.test.tsx            | 4     | Glyph rendering, zero-count dimming, aria-labels, default info=0 |
| asset-vulns-list.test.tsx           | 6     | Empty-list null return, role=row count, severity tint, KEV-only badge, click + Enter activation, ArrowDown focus shift |
| remediation-timeline.test.tsx       | 9     | Empty-list null return, row testids, provider data-testids, link rel + target attributes, plain text when no URL, relative timestamp formatting, future-clamp to just-now, unknown-provider fallback, status pill text |
| identity-metadata-rail.test.tsx     | 5     | All-rows render, null-row skipping, role=region aria-label, empty array handling for IP/MAC, OS row when only os_name set |
| /assets/[id] page.test.tsx          | 8     | Breadcrumb mount, H1 mono, inline tags, rail composition (risk-card / owner-card / identity-metadata), severity ribbon counts, drill URL contract on row click, DrillPanel mount, empty-state for remediations |
| **Total**                           | **32**| — |

Full suite `pnpm vitest run src/components/assets src/app/(authed)/dashboard/assets` reports `Test Files 8 passed (8) / Tests 50 passed (50)` (32 new + 18 from prior plans).

`pnpm tsc --noEmit` is clean.

## Acceptance Criteria Status

| Criterion | Status |
| --------- | ------ |
| `grep -c "GLYPHS\|■\|▲\|◆\|○\|□" severity-ribbon.tsx >= 6` | 9 (pass) |
| `grep -n "data-testid=\"ribbon-" severity-ribbon.tsx >= 1` | template literal `data-testid={\`ribbon-${key}\`}` — the literal-string grep doesn't match but the testid contract is verified by `getByTestId('ribbon-critical')` in 4 tests |
| `grep -n "role=\"row\"" asset-vulns-list.tsx >= 1` | 2 (pass) |
| `grep -c "ArrowDown\|ArrowUp\|Enter" asset-vulns-list.tsx >= 3` | 4 (pass) |
| `grep -n "PROVIDER_GRADIENT\|STATUS_TONE" remediation-timeline.tsx >= 2` | 4 (pass) |
| `grep -n "relativeTimestamp" remediation-timeline.tsx >= 2` | 2 (pass) |
| `grep -n 'rel="noreferrer"' remediation-timeline.tsx == 1` | 1 (pass) |
| `grep -n "MetadataRow" identity-metadata-rail.tsx >= 10` | 11 (pass) |
| `grep -n "DrillPanel\b" page.tsx >= 2` | 4 (pass) |
| `grep -n "DrillPanelMobile" page.tsx >= 2` | 3 (pass) |
| `grep -n "open=drill\|open', 'drill'" page.tsx == 1` | 1 occurrence of the canonical `sp.set('open', 'drill')` (the other matches are doc-comment / regex misses; intent satisfied) |
| `grep -n "min-\[900px\]:sticky" page.tsx >= 1` | 1 (pass) |
| `grep -n "min-\[900px\]:grid-cols-\[1fr_340px\]" page.tsx >= 1` | 1 (pass) |
| `grep -n "SkeletonTable\|EmptyState\|PartialFailureBanner" page.tsx >= 3` | 20 (pass) |
| `ls -1 src/components/states/*.tsx \| grep -v test \| wc -l == 4` | 4 (UX-04-05 gate held) |
| Page test reports >= 8 green | 8 (pass) |
| tsc clean | clean (pass) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SkeletonTable prop name corrected**
- Found during: Task 3 tsc check
- Issue: Plan code called `<SkeletonTable rowCount={n} />`, but the existing Phase 11 `SkeletonTable` component (frontend/src/components/states/skeleton-table.tsx) accepts `rows`, not `rowCount`. tsc emitted four TS2322 errors on the four call sites in page.tsx.
- Fix: Replaced `rowCount` with `rows` at all four call sites in page.tsx.
- Files modified: frontend/src/app/(authed)/dashboard/assets/[id]/page.tsx
- Commit: bc92510

**2. [Rule 1 - Bug] text-text-subtle token substituted with text-text-faint**
- Found during: Tasks 1 and 2 implementation
- Issue: Plan code referenced `text-text-subtle`, but this token is NOT configured in `frontend/tailwind.config.ts`. The classname would silently produce no styling. Three prior phase-12 components (RiskRing.tsx, Breadcrumb.tsx, assets-table.tsx) each carry an inline comment documenting the same substitution — this is established project convention.
- Fix: Used `text-text-faint` for the dimmed-zero-count case in severity-ribbon, the metadata label color in identity-metadata-rail, and the unknown-severity fallback + CVSS column in asset-vulns-list. The relative timestamp in remediation-timeline also uses `text-text-faint`.
- Files modified: all four new component files plus the test (test asserts on `text-text-faint` substring).
- Commit: 508cb81, 013e829

### Skipped Verifications

**`pnpm lint`** — The repository's `next lint` command is interactive (Next.js 16-deprecation prompt asking which ESLint config to set up). It cannot run unattended. This is a pre-existing infrastructure state unrelated to this plan; flagged for a future repo-hygiene plan but does not block 12-08.

## Known Stubs

| File | Stub origin | Resolution |
| ---- | ----------- | ---------- |
| `frontend/src/components/assets/risk-card.tsx` | Created in 12-08 because 12-07 lives in a parallel worktree | Orchestrator MUST replace with the real implementation when merging 12-07 |
| `frontend/src/components/assets/owner-card.tsx` | Same as above | Same — orchestrator MUST replace at merge time |

Both stubs:
- Export the same name (`RiskCard`, `OwnerCard`)
- Accept the documented `{ asset: AssetDetail }` prop
- Render `data-testid="risk-card"` and `data-testid="owner-card"` so the page composition test continues to pass after merge
- Carry `data-stub-from="12-08"` so a `grep -r 'data-stub-from' frontend/src` after merge surfaces leftover stubs

**Merge instruction:** when the orchestrator merges 12-07 into the integration branch, both stub files must be overwritten by 12-07's real implementations. The page.tsx imports `from '@/components/assets/risk-card'` and `from '@/components/assets/owner-card'` are stable across the merge.

## Two-Column Template (locked — Phase 13 reuse)

The /assets/[id] page locks two design contracts that Phase 13 /tickets/[id] should reuse verbatim:

### Grid template

```html
<div className="grid grid-cols-1 gap-6 p-6 min-[900px]:grid-cols-[1fr_340px]">
  <main>{/* page content */}</main>
  <aside className="min-[900px]:sticky min-[900px]:top-4 min-[900px]:self-start">
    {/* rail content */}
  </aside>
</div>
```

- Grid splits at 900px (an arbitrary tailwind class, not the default `md:` 768px breakpoint).
- Rail is exactly 340px wide on desktop; on mobile it stacks below `<main>`.
- Rail is sticky to viewport top (with 16px offset via `top-4`) on desktop.

### Drill URL contract

```ts
// Row click — open drill in URL (Phase 11 D-P-02):
const sp = new URLSearchParams(params?.toString() ?? '');
sp.set('cve', cveOrId);
sp.set('open', 'drill');
router.replace(`${pathname}?${sp.toString()}`, { scroll: false });

// Page mounts panels (Phase 11 reads URL itself):
<DrillPanel cveId={cveId} originRowRef={null} />
<DrillPanelMobile cveId={cveId} />
```

Open is **never** local state — always URL-driven. The 900px breakpoint matches Phase 11 D-P-03 drill-panel mobile threshold, so the rail and the drill surface flip layouts at the same width.

## Self-Check: PASSED

- Files created:
  - `frontend/src/components/assets/severity-ribbon.tsx` — FOUND
  - `frontend/src/components/assets/severity-ribbon.test.tsx` — FOUND
  - `frontend/src/components/assets/asset-vulns-list.tsx` — FOUND
  - `frontend/src/components/assets/asset-vulns-list.test.tsx` — FOUND
  - `frontend/src/components/assets/remediation-timeline.tsx` — FOUND
  - `frontend/src/components/assets/remediation-timeline.test.tsx` — FOUND
  - `frontend/src/components/assets/identity-metadata-rail.tsx` — FOUND
  - `frontend/src/components/assets/identity-metadata-rail.test.tsx` — FOUND
  - `frontend/src/components/assets/risk-card.tsx` — FOUND (STUB)
  - `frontend/src/components/assets/owner-card.tsx` — FOUND (STUB)
  - `frontend/src/app/(authed)/dashboard/assets/[id]/page.test.tsx` — FOUND
- Files modified:
  - `frontend/src/app/(authed)/dashboard/assets/[id]/page.tsx` — FOUND (rewritten)
- Commits:
  - 508cb81 (Task 1) — FOUND
  - 013e829 (Task 2) — FOUND
  - bc92510 (Task 3) — FOUND
