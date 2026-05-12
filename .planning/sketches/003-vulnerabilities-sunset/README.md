---
sketch: 003
name: vulnerabilities-sunset
question: "Does the sunset palette survive a dense data table? Which filter UX + density + drill-down combination matches GetVul's workflow best?"
winner: null
tags: [vulnerabilities, table, filters, density, drill-down]
---

# Sketch 003: Vulnerabilities — Sunset Palette

## Design Question

`/dashboard/vulnerabilities` is the product's defining screen: 1000+ rows, filters, severity at scale, bulk actions, drill-down to CVE details. Per the REDESIGN_PLAN it's the hardest visual challenge for the redesign — the warm sunset palette has to coexist with a lot of red/orange severity data without muddying.

Three variants test three orthogonal axes at once:

1. **Filter UX** — persistent drawer / collapsible rail / chip bar
2. **Row density** — comfortable / dense / comfortable
3. **Drill-down** — modal-future / row-future / **side panel (variant C)**

## How to View

```
open .planning/sketches/003-vulnerabilities-sunset/index.html
```

Three variants. Same data (10 real CVEs from 2024 + 6 extra for the dense variant). Same view-toggle (By CVE / By host), export, Triage queue CTA.

## Variants

- **A — Pinned drawer + comfortable rows** — 280px filter drawer always visible on the left, table on the right with comfortable padding. Filter drawer has: search · severity chips with counts · quick toggles (KEV / Exploit / Hide-snoozed) with sunset-gradient switches · source chips · status chips · saved filters list. Table includes a checkbox column — selecting rows reveals a floating bulk-action bar (rounded-pill, glass, gradient pink count). Best for "I open this page and immediately start filtering."

- **B — Collapsible rail + dense table** — Filter rail starts collapsed to a 54px icon strip with red-dot indicators for active filters. Click the funnel icon to expand to the full drawer. Table is dense (single-line rows, smaller padding, 16 rows visible above the fold). Best for "I know what I'm looking for and want to see as many rows as possible."

- **C — Chip bar + side-panel drill-down** — No persistent drawer. Filters live as chips in a header bar above the table. Clicking a row opens a 420px side panel on the right with the CVE detail (description, CVSS vector breakdown, affected hosts, remediation, actions). The table dims to ~60% width while the panel is open. Best for "I scan, I drill, I act — without ever leaving this screen." Most "Linear / Cursor / Notion" workflow.

## What to Look For

**Warm palette + severity color coexistence (the big question):**
- Severity pills (red/orange/yellow/violet) are the loudest non-CTA color on the page. Does the deep-plum background let them breathe, or does it feel like a fruit salad?
- The gradient CTA ("Triage queue") sits at the top right. Does it compete with the red severity pills below?
- "Critical" score numbers are red. Watch for: do they read as urgent, or does everything red just blur together?

**Filter UX comparison:**
- A · pinned: chunks of vertical real estate are gone. Trade for permanence.
- B · collapsed: rail has dots indicating active filters — discoverable enough?
- C · chip bar: filters are inline and visible at a glance. Saved-filter pill in violet (★ Today's triage). Easiest to share via URL.

**Density:**
- A and C use comfortable rows (~12px padding, line + sub-line per row would be possible).
- B uses dense rows (~7px padding, single-line). How many more items above the fold is the tradeoff for what amount of scanability loss?

**Drill-down (variant C):**
- Click any row in C → side panel opens with CVE-2024-3094 details. Try a few rows; the panel stays at the same CVE (it's a mock, not really swapping data).
- Close button top-right of panel. Or click row again to re-anchor.
- Panel includes: severity + KEV + exploit pills · description · CVSS 9.8 with vector · affected hosts (3 listed) · remediation paragraph · action buttons (Create Jira ticket [gradient] + Snooze 24h + Copy NVD link).

**Bulk action bar (variant A):**
- Click row checkboxes in A → floating bar appears at the bottom with "N selected · Create tickets · Snooze · Tag · Resolve · ×".
- Slide-up animation from below.

**Mobile (toggle 375 in toolbar):**
- All three collapse the sidebar.
- Tables collapse to card view (severity pill + CVE on row 1, product on row 2, asset + SLA pill on row 3).
- Variant A's filter drawer drops above the cards.
- Variant B's rail hides entirely; chip bar above cards would need to be added (deferred).
- Variant C's drill panel becomes a full-screen overlay on mobile.

## Open variables (for next sketch round if needed)

- The bulk-action bar (currently variant A only) — should it appear in all variants? Probably yes for consistency.
- Sort UI — currently no sort affordance on column headers. Click-to-sort with arrow indicator?
- Column visibility — power users will want to add/hide columns. A settings popover off the table header?
- The "Hide snoozed" toggle implies a snooze concept — is that real or aspirational? (Aspirational right now.)
- Row hover reveals quick-actions on the right (snooze, ticket)? Currently no.
- Empty state when filters return 0 results — would need a separate sketch (see option in next-sketch prompt).
- Light theme support for this screen — deferred until a global light-theme decision lands.
