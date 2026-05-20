---
sketch: 006
name: tickets-sunset
question: "How should tickets be listed and detailed — and how should provider identity (Jira / Asana / GitHub) read in the sunset world?"
winner: "A (primary view); B inherits asset-detail pattern for /tickets/[id]; C deferred as future 'Board view' toggle"
tags: [tickets, list, detail, kanban, provider-identity, sla, status-workflow]
---

# Sketch 006: Tickets — Sunset Palette

## Design Question

Tickets are GetVul's outbound integration — the moment a vulnerability becomes work for someone in Jira / Asana / GitHub. The screen has to handle:

- **Provider identity** — Jira blue, Asana red, GitHub purple — without losing the sunset palette
- **SLA color coding** — overdue (red) / soon (amber) / ok (green) at a glance
- **Status workflow** — Open → In progress → Completed
- **Cross-reference to vulnerabilities** — each ticket links to 1–N CVEs

Unlike previous sketches, the 3 variants here are **different views of the same data**, not competing aesthetics:

1. List view with side-panel drill-down (same pattern as `/vulnerabilities`)
2. Dedicated detail page (a single ticket as its own route)
3. Kanban board (drag between status columns)

You'll probably want a primary view + a secondary/alternate, not just one.

## How to View

```
open .planning/sketches/006-tickets-sunset/index.html
```

Three variants. 10 realistic tickets across Jira, Asana, GitHub. Mix of severities, statuses, SLA states.

## Variants

- **A — List + side panel** — Tickets table with chip-bar filters (status, provider, "only SLA-at-risk"). Columns: Severity · Provider · ID · Title · Vulns (count + critical/high breakdown) · Assignee · Status · SLA. Click any row → 420px right-side detail panel slides in showing linked vulnerabilities (3 mini-rows), description, full activity timeline, details grid, and action buttons (Open in Jira / Edit / Mark completed). **Same pattern as the `/vulnerabilities` winner.**

- **B — Dedicated detail page** — Single ticket `JIRA-2841` as its own URL. Two-column layout matching the asset-detail pattern: main column has linked vulnerabilities (3 rich rows), description, activity timeline with a comment input. Right sticky rail has: Details card (status, priority, SLA, due date, created), People card (assignee + reporter + watchers with avatars), Asset card (linked host with View asset → link). **Same shape as `/assets/[id]`.** Most space for context.

- **C — Kanban board** — Three status columns (Open · In progress · Completed) with provider-branded cards. Each card shows: provider chip with ID, SLA pill, title, severity glyph + vuln count breakdown, assignee avatar, provider source. Drag-to-update status (mock — visual only). Filter strip above: search + provider chips + Mine/All. **Workflow tool pattern** — Linear/Jira/Trello family.

## What to Look For

**Provider identity:**
- Jira gets cool blue (`#5C9CFF`-tinted background + bordered chip + small gradient mark)
- Asana gets warm coral (`#FF8AA0`-tinted, three-dot mark)
- GitHub gets violet (matches sunset palette accent)
- Each is a `<span class="provider ${name}">` with a `provider-mark` square containing the brand glyph. Does this read as "Jira" without using actual Jira logos?

**SLA color hierarchy:**
- Overdue: red pill (matches critical severity)
- Soon (<24h): amber pill
- OK: green pill
- Compare against severity pills in the same row — does the eye separate them?

**Status workflow visual:**
- Open: violet dot pill
- In progress: amber dot pill
- Completed: green dot pill
- These are *different* from severity colors (deliberately) so the eye knows status ≠ severity

**Vuln count column:**
- In A: `3 ·2 ·1` (total + critical count + high count, color-coded)
- In Kanban cards: severity glyph + total + breakdown
- Useful condensed information or too cryptic?

**Across variants:**
- **A's drill panel** — same pattern as `/vulnerabilities`, deliberately reusable. The mini-vuln rows are compact (severity pill + CVE + score).
- **B's detail page** — comment input at the bottom of the activity timeline. Watchers row with avatar stack.
- **C's kanban cards** — feel productive (drag to advance work). Overdue cards stand out with red SLA pill. Provider chip up top, severity glyph in the middle, assignee at the bottom.

**Mobile (toggle 375):**
- A: drill panel becomes full-screen overlay
- B: right rail moves below main column
- C: columns stack vertically (one per row) — kanban becomes a long list

## Open variables

- For Kanban: is "Blocked" a status worth showing as a 4th column? Currently not modeled — could be a state filter or a 4th column.
- Provider chips currently use small gradient marks; would real provider logos be more recognizable, or do gradient marks feel more cohesive with the brand?
- "Mine vs All" filter (in C) — should that be in the topbar globally so it persists across screens?
- Comments in B: rich text or plain text? v1 likely plain. The Markdown affordance is a v2-Y decision.
- Watcher stack: currently shows 2 avatars + "+3". Hover to expand?
- Cross-screen consistency: A's drill panel matches `/vulnerabilities`. B matches `/assets/[id]`. The intended pattern is: list pages get side panels for quick scan, detail pages get dedicated routes for deep work. Both are valid; the question is *when* to use which.

## Likely outcome

The list+side-panel (A) probably wins for the LIST route (`/tickets`) — consistent with `/vulnerabilities`. The dedicated detail page (B) probably wins for the DETAIL route (`/tickets/[id]`) — consistent with `/assets/[id]`. Kanban (C) is interesting as an alternative *view* of the same list ("List view / Board view" toggle in the top-right) rather than the primary view.

So this sketch might validate **all three** with a clear role split, not pick one. We'll see.
