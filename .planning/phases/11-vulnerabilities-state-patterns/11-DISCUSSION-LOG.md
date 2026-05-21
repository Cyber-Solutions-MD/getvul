# Phase 11: `/vulnerabilities` + State Patterns — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in [11-CONTEXT.md](11-CONTEXT.md) — this log preserves the alternatives considered.

**Date:** 2026-05-21
**Phase:** 11-vulnerabilities-state-patterns
**Areas discussed:** State-pattern primitives API, Chip-bar filter UX, Drill-panel behavior, View toggle + per-source data, Sort + keyboard + virtualization (follow-up round)

---

## State-pattern primitives API

| Option | Description | Selected |
|--------|-------------|----------|
| Column-aware props | `<SkeletonTable rows={8} columns={[{kind:'pill', width:80}, ...]}/>` — caller passes column shape | ✓ |
| Generic rows + cols | `<SkeletonTable rows={8} cols={7} />` — simple count | |
| Render-prop / table mirror | Wraps the actual table component and replaces row contents with shimmer | |

**User's choice:** Column-aware props
**Rationale captured in D-S-01.** Matches the sketch's column-shaped placeholders.

| Option | Description | Selected |
|--------|-------------|----------|
| Slot subcomponents | `<EmptyState>` + `.Title` + `.Body` + `.Actions` + `.Suggestion` (mirrors Phase 10 Card) | ✓ |
| Props bag | `<EmptyState title body ctas suggestion icon />` | |
| Variant + render prop | `<EmptyState variant="filtered-zero">` with render-prop child | |

**User's choice:** Slot subcomponents
**Rationale captured in D-S-02.**

| Option | Description | Selected |
|--------|-------------|----------|
| Props (caller passes) | `<PartialFailureBanner errors={…} requestId={…} onRetry={…} />` | |
| `useQueryErrors()` hook | `<PartialFailureBanner />` reads errors via a hook that reaches into QueryClient | |
| Hybrid — hook with override | Default to hook-based; accept optional props for caller override | ✓ |

**User's choice:** Hybrid — hook with override
**Rationale captured in D-S-03.**

| Option | Description | Selected |
|--------|-------------|----------|
| `components/states/` | Thematic grouping for state primitives | ✓ |
| `components/ui/` (with primitives) | Mixed with existing primitives | |
| `components/list/` | Couples to list-page concept | |

**User's choice:** `components/states/`
**Rationale captured in D-S-04.**

---

## Chip-bar filter UX

| Option | Description | Selected |
|--------|-------------|----------|
| Immediate per-chip, debounced search | Chips: instant. Search: 250ms debounce | ✓ |
| All immediate | Every keystroke + every chip click | |
| Enter / blur only on search | Search waits for Enter/blur; chips immediate | |

**User's choice:** Immediate per-chip, debounced search
**Rationale captured in D-F-01.**

| Option | Description | Selected |
|--------|-------------|----------|
| Live counts per chip (contextual) | `Critical · 12` — counts under all OTHER applied filters | ✓ |
| Static labels only | No counts; label only | |
| Global counts (filter-agnostic) | Counts ignore other filters | |

**User's choice:** Live counts per chip (contextual)
**Rationale captured in D-F-02.**

| Option | Description | Selected |
|--------|-------------|----------|
| From facet endpoint (live) | `?facets=severity,source,status` returns tenant-active sources + counts | ✓ |
| From connector configs | Read enabled connectors from `/api/v1/connectors` | |
| Hardcoded enum | Frontend ships fixed list of all supported sources | |

**User's choice:** From facet endpoint (live)
**Rationale captured in D-F-03.**

| Option | Description | Selected |
|--------|-------------|----------|
| Read-only `★ Today's triage` default | Wire violet pill to first saved-filter; no CRUD | ✓ |
| Full CRUD | Save / rename / delete UI | |
| Save + restore only | Save and apply; management deferred | |

**User's choice:** Read-only `★ Today's triage` default
**Rationale captured in D-F-04.**

---

## Drill-panel behavior

| Option | Description | Selected |
|--------|-------------|----------|
| All four: × / Esc / outside / row-swap | Full keyboard + mouse coverage | ✓ |
| × button + Esc only | No outside-click close; safer against accidental dismissal | |
| × + Esc + row-swap (no outside) | Skip outside-click but keep row-swap | |

**User's choice:** All four
**Rationale captured in D-P-01.**

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — `?cve=…&open=drill` | URL-encoded; link-shareable | ✓ |
| No — component-state only | React state; refresh loses panel | |

**User's choice:** Yes — URL-encoded
**Rationale captured in D-P-02. Closes the Phase 10 Top5Card link stubs.**

| Option | Description | Selected |
|--------|-------------|----------|
| Bottom sheet (slide up) — `vaul` | Native-feeling mobile drill | ✓ |
| Full-screen overlay | Spec wording verbatim; no new dep | |
| Full-screen now, vaul in Phase 15 | Defer vaul integration | |

**User's choice:** Bottom sheet (`vaul`)
**Rationale captured in D-P-03.**

| Option | Description | Selected |
|--------|-------------|----------|
| Snooze: immediate + undo. Ticket: modal | Reversible vs irreversible asymmetry | ✓ |
| Both immediate with undo | Aggressive on speed | |
| Both with confirmation modal | Maximum safety | |

**User's choice:** Snooze immediate + undo; Ticket with confirmation modal
**Rationale captured in D-P-04.**

---

## View toggle + per-source data

| Option | Description | Selected |
|--------|-------------|----------|
| Backend `?group=host` param | Server-side grouping; paginates correctly | ✓ |
| Client-side reshape | Fetch flat list, group in frontend | |
| Two separate endpoints | `/vulnerabilities` and `/vulnerabilities/by-host` | |

**User's choice:** Backend `?group=host` param
**Rationale captured in D-V-01.**

| Option | Description | Selected |
|--------|-------------|----------|
| Read connector last-sync state | Composition from `/connectors` + facet endpoint | ✓ |
| New `/vulnerabilities/source-status` endpoint | Dedicated endpoint | |
| SSE stream | Real-time; out-of-scope per PROJECT.md | |

**User's choice:** Read connector last-sync state
**Rationale captured in D-V-02.**

| Option | Description | Selected |
|--------|-------------|----------|
| Defer to a later phase | Drop v1 BulkActions; revive when requested | ✓ |
| Ship in Phase 11 | Port BulkActions to chip-bar layout | |
| Stub the toggle, defer the bar | Worst of both | |

**User's choice:** Defer
**Rationale captured in D-V-03.**

| Option | Description | Selected |
|--------|-------------|----------|
| Per-row `source` field + failed-source list | `row.source` matched against partial-failure context | ✓ |
| Backend marks `is_stale` on rows | More authoritative but bigger backend change | |
| Last-seen timestamp threshold | Computes real staleness; more work | |

**User's choice:** Per-row `source` field + failed-source list
**Rationale captured in D-V-04.**

---

## Follow-up round: sort + keyboard + virtualization

| Option | Description | Selected |
|--------|-------------|----------|
| Sort 4 columns, sticky header | Severity, CVE, CVSS, SLA; sticky `<thead>` | ✓ |
| No sort; sticky header | Only Phase 10's `?sort=triage` default | |
| Sort all 7 columns; no sticky | All sortable; header scrolls with content | |

**User's choice:** Sort 4 columns + sticky header
**Rationale captured in D-T-01 + D-T-04.**

| Option | Description | Selected |
|--------|-------------|----------|
| Full keyboard table | `tabindex=0` rows, Enter/Space opens, ↑/↓ moves, Esc closes, Tab into panel | ✓ |
| Basic only | Click + tab order; arrow-key nav in Phase 15 | |

**User's choice:** Full keyboard table
**Rationale captured in D-T-02. UX-07-03 slice satisfied now to avoid Phase 15 bounce.**

| Option | Description | Selected |
|--------|-------------|----------|
| Pagination, no virtualization | 50/page default, 200 max; revisit if needed | ✓ |
| `@tanstack/react-virtual` | Virtualize 10k rows | |
| Cursor-style infinite scroll | IntersectionObserver next-page | |

**User's choice:** Pagination only
**Rationale captured in D-T-03.**

---

## Claude's Discretion

Per user direction:
- "Clear all" scope (search input only vs chips only vs both)
- Empty-state lightbulb suggestion content (UX-S-02)
- Pagination control sunset polish (restyle now or carry v1 styling)
- Skeleton column-kind set extension beyond `'pill' | 'mono' | 'text'`

Documented in `<decisions>` § Claude's Discretion in CONTEXT.md.

## Deferred Ideas

- Saved-filter CRUD
- Bulk actions
- Table virtualization
- Real-time SSE / WebSocket per-source progress
- Light-theme polish (UX-D-03)
- Save-as-watch lightbulb CTA (depends on saved-filter CRUD)
- Column reordering / visibility toggle / saved table layouts
- Per-row preview-on-hover
- Backend `is_stale` column on rows
- Drill-panel comment-on-vulnerability surface

All preserved in `<deferred>` § Deferred Ideas in CONTEXT.md.
