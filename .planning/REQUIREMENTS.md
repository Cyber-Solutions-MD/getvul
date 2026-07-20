# Milestone v2.2 — Deferred UI Features · Requirements

**Status:** IN PROGRESS (opened 2026-07-15)
**Phases:** 16–19 (continues the v2.x redesign line; v2.0 ended at phase 15)
**Scope source:** [v2.2-SCOPE-DRAFT.md](v2.2-SCOPE-DRAFT.md) + current-state feature map (2026-07-15)
**Locked decisions:** page transitions = **View Transitions API** (native, 0 KB); kanban DnD = **@dnd-kit**.
**Design contract:** `.claude/skills/sketch-findings-getvul/` (authoritative). **Gate:** phase-15 quality
gate applies to every phase — axe WCAG 2.1 AA (now in **both** themes), reduced-motion, ≤250 KB First-Load JS/route.

Requirement IDs anchor to the originating backlog items (UX-D-01/02/03/06) expanded into testable units.

## Phase 16 — Light-theme visual completion (from UX-D-03)

> **Gap closure (2026-07-20):** the v2.2 audit found the light sweep red at HEAD (`text-severity-high` 3.19:1). UX-D-03-02/-03/-05 are re-closed by **Phase 20**; -01/-04 tracking boxes tick once Phase 20's sweep is green.

- [ ] **UX-D-03-01**: Every authenticated route renders visually correct in light mode — no dark-only borders, shadows, hover, or disabled artifacts.
- [ ] **UX-D-03-02**: All text + UI meets WCAG 2.1 AA contrast (4.5:1 text, 3:1 UI/graphics) in light mode on every route. → **Phase 20**
- [ ] **UX-D-03-03**: Severity / status / SLA pills and severity glyphs are legible and mutually distinct on light surfaces. → **Phase 20**
- [ ] **UX-D-03-04**: `text-muted` / `text-faint` / disabled-state tokens pass AA on light surfaces; any source-palette change is reconciled into the design system (per the BL-04 pattern).
- [ ] **UX-D-03-05**: The e2e a11y sweep (`e2e/a11y-routes.spec.ts`) runs under `data-theme="light"` as well as dark, and is green. → **Phase 20**

## Phase 17 — Page-transition motion (from UX-D-06)

> **Gap closure (2026-07-20):** the v2.2 audit found Phase 17 formally unverified (no VERIFICATION.md, perceptual UAT unpersisted, IN-01 proxy test undone). UX-D-06-01/-03/-04 are re-closed by **Phase 21**.

- [ ] **UX-D-06-01**: Route changes within the `(authed)` shell animate with a cross-fade/transition via the **View Transitions API** (single `template.tsx`). → **Phase 21**
- [ ] **UX-D-06-02**: Transitions are fully suppressed under `prefers-reduced-motion` (animation-duration ≤0.02s); `e2e/reduced-motion.spec.ts` stays green.
- [ ] **UX-D-06-03**: A CSS-animation fallback keeps navigation clean in browsers without View Transitions support (no jank/broken nav in Firefox). → **Phase 21**
- [ ] **UX-D-06-04**: Transitions do not race with DrillPanel Esc/clickaway close and cause no layout shift. → **Phase 21**
- [ ] **UX-D-06-05**: No route exceeds the 250 KB First-Load JS budget (native API adds 0 KB).

## Phase 18 — Tickets kanban board (from UX-D-01)

- [x] **UX-D-01-01**: The board view renders four status columns (Open / In progress / Completed / Blocked) populated from `useTickets`, replacing the "coming soon" placeholder.
- [x] **UX-D-01-02**: A ticket can be moved between columns by pointer drag (**@dnd-kit**), persisting the new status via a mutation with optimistic update + rollback on error. _(satisfied; **Phase 22** adds test coverage for the CR-01 Enter-key-drag + WR-02 gated-drop SR fixes)_
- [x] **UX-D-01-03**: The board is fully keyboard-operable — a ticket's status can be changed without a pointer (@dnd-kit keyboard sensor).
- [x] **UX-D-01-04**: Empty columns render the canonical empty-state pattern; the existing status chip filter still applies to the board.
- [x] **UX-D-01-05**: At <768px the board degrades to a non-broken layout (horizontal scroll or column switcher) without regressing the fixed bottom-nav focus behavior.
- [x] **UX-D-01-06**: The list/board URL toggle is preserved; the board route stays ≤250 KB and passes axe in both themes.

## Phase 19 — Add-connector wizard (from UX-D-02)

- [x] **UX-D-02-01**: Adding a connector runs a four-step wizard: provider pick → credentials → test connection → confirm.
- [x] **UX-D-02-02**: Step navigation is gated — the user cannot advance past the test step until the connection test succeeds.
- [x] **UX-D-02-03**: The credentials step reuses the existing sentinel-passthrough (edit mode preserves untouched secrets; only touched fields are sent).
- [x] **UX-D-02-04**: The confirm step shows the connector's required OAuth scopes/permissions before final submit.
- [x] **UX-D-02-05**: The wizard reuses existing endpoints (`POST /connectors/test`, `POST /connectors`) — no new backend.
- [x] **UX-D-02-06**: The wizard works in the ResponsiveDialog/vaul mobile pattern; passes axe in both themes; the connectors route stays ≤250 KB. _(satisfied; **Phase 22** extends the axe sweep to the Test + Confirm steps)_

## Out of scope (this milestone)
- v1.1 backend hardening (unrelated line).
- BL-06 Safari glyph human check (needs a Mac; tracked in 15-HUMAN-UAT.md Item 1).
- Print stylesheet (optional; not committed).
- framer-motion / react-beautiful-dnd (rejected in favor of the locked native/@dnd-kit choices).

## Traceability
Filled by the roadmap below — every REQ maps to exactly one phase (16–19).
