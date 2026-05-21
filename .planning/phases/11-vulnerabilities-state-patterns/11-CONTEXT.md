# Phase 11: `/vulnerabilities` + State Patterns — Context

**Gathered:** 2026-05-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Ship the redesigned `/vulnerabilities` page **and** the canonical state-pattern primitives (UX-S-01..05) that Phases 12–14 reuse verbatim. The phase has two interlocking deliverables:

1. **`/vulnerabilities` rebuild** against the sunset design system — chip-bar filter row above a 7-column table with a 420px right-side drill panel, By-CVE ↔ By-Host segmented toggle, URL-synced filter state, mobile card view + bottom-sheet drill below 900px.
2. **State-pattern primitive set** in `frontend/src/components/states/` — `SkeletonTable`, `EmptyState`, `PartialFailureBanner`, `PerSourceStatusStrip`. (Toast already shipped in Phase 9 + extended in Phase 10; treated as already-canonical for Phase 11 consumers.)

The state-pattern primitives are the load-bearing cross-phase contract: Phases 12 (`/assets`), 13 (`/tickets`), 14 (remaining screens) consume them as-is. Their APIs lock in Phase 11.

The phase also **retrofits Phase 10**'s inline-minimal loading / empty / error UI to use the canonical primitives (per Phase 10 D-D-11 commitment).

**In scope:**

- Rewrite of `frontend/src/app/(authed)/dashboard/vulnerabilities/page.tsx` (v1 658-line tab+filter+table replaced)
- Delete v1 `frontend/src/components/vulnerabilities/` (`VulnFilters.tsx`, `VulnTable.tsx`, `BulkActions.tsx` — bulk deferred per D-V-03)
- New state-pattern primitives under `frontend/src/components/states/`:
  - `skeleton-table.tsx` (column-aware)
  - `empty-state.tsx` (slot subcomponents: `<EmptyState>` + `.Title` + `.Body` + `.Actions` + `.Suggestion`)
  - `partial-failure-banner.tsx` (hybrid hook + props override)
  - `per-source-status-strip.tsx`
- New `useQueryErrors` hook (drives `PartialFailureBanner` default mode)
- New vulnerabilities-specific components: `chip-bar.tsx`, `vuln-table.tsx`, `drill-panel.tsx`, `view-toggle.tsx`
- New TanStack Query hooks under `frontend/src/lib/queries/`: `use-vulnerabilities`, `use-vulnerabilities-facets`, `use-vulnerability-detail`, `use-saved-filters` (read-only)
- New mutation: `useCreateTicketMutation`
- Extend `frontend/src/hooks/use-url-state.ts` (or add `use-url-state-list.ts`) for multi-value filter chips
- Phase 10 retrofit: replace inline-minimal skeletons in `dashboard/page.tsx`, `top5-card.tsx`, `trend-section.tsx`, `activity-rail.tsx`, `stat-strip-wired.tsx`, `onboarding-panel.tsx` with the canonical primitives where they apply
- Add `vaul` dep + integrate for mobile bottom-sheet drill panel
- `/dev/primitives` extended with state-pattern primitives showcase
- Backend extensions:
  - `?facets=severity,source,status` on `/api/v1/vulnerabilities` returning per-chip counts contextual to other applied filters
  - `?group=host` on `/api/v1/vulnerabilities` returning by-host grouping (server-side; paginates correctly)
  - `?sort=field&order=asc|desc` extended to support `severity`, `cve_id`, `cvss_v3_score`, `sla_due_at` (Phase 10 already shipped `?sort=triage`)
  - `POST /api/v1/tickets` (or equivalent ticketing endpoint) wired through from the drill panel — if endpoint already exists, just consume it
- Per-primitive `.test.tsx` with axe + integration test at `vulnerabilities/page.test.tsx` + a11y test for keyboard nav (UX-07-03 partial)
- Backend pytest per endpoint extension

**Out of scope (other phases / future):**

- Bulk actions (deferred per D-V-03 — port back when a user actually requests it)
- Saved-filter CRUD beyond reading the default `★ Today's triage` pill (deferred — full CRUD is its own surface)
- Table virtualization (deferred per D-T-03 — pagination handles most tenants; revisit if profiling shows pain at >2k rows per page)
- Real-time per-source SSE / WebSocket updates (out of scope per PROJECT.md no-websocket constraint)
- Light-mode visual polish (UX-D-03 — still deferred milestone-wide)
- Phase 15 a11y full pass (touch sizing, focus-not-obscured, full bottom-nav, etc.) — Phase 11 does the keyboard-nav slice via D-T-02; the rest stays in Phase 15
- Storybook
- Per-user table preferences (column order, density, default sort) — future polish
- Print stylesheet

</domain>

<decisions>
## Implementation Decisions

### State-pattern primitives API (cross-phase contract)

- **D-S-01:** `SkeletonTable` takes **column-aware props**, not generic row/col counts. Signature: `<SkeletonTable rows={8} columns={[{kind:'pill', width:80}, {kind:'mono', width:130}, {kind:'text', width:200}, ...]} />`. `kind` values: `'pill'` (rounded shimmer), `'mono'` (mono-width text shimmer), `'text'` (proportional text shimmer). Skeleton mirrors the real table's column shape per route. Matches the sketch's column-shaped placeholders. Phase 12+ describe their columns once when calling.
- **D-S-02:** `EmptyState` uses **slot subcomponents** (mirrors Phase 10's `Card` pattern): `<EmptyState>` + `<EmptyState.Title>` + `<EmptyState.Body>` + `<EmptyState.Actions>` + `<EmptyState.Suggestion>`. Flexible composition; consumers can omit slots they don't need. The "violet lightbulb suggestion" (UX-S-02) is rendered via `<EmptyState.Suggestion>` and is optional.
- **D-S-03:** `PartialFailureBanner` is **hybrid — hook by default, props override**. Default mode: `<PartialFailureBanner />` reads errors via a new `useQueryErrors([queryKey, ...])` hook that reaches into the `QueryClient`. Escape hatch: `<PartialFailureBanner errors={errorsArray} requestId={...} onRetry={...} />` for cases where one specific query is the "main" failure source (e.g., bulk operations). Tightly couples the default mode to TanStack — acceptable since TanStack is the v2.0 standard (Phase 10 D-D-01).
- **D-S-04:** State-pattern primitives live in **`frontend/src/components/states/`**, not mixed with `components/ui/`. Consumers import from `@/components/states`. Clear thematic grouping; distinct from pure-presentation primitives.
- **D-S-05:** `Toast` is treated as already-canonical (shipped in Phase 9, extended with `duration` + `action` slot in Phase 10). No further extension in Phase 11 unless drill-panel ticket-creation flow surfaces a gap. The UX-S-05 toast notification requirement is satisfied by the existing primitive.
- **D-S-06:** Phase 10 retrofit happens **in Phase 11**, not deferred again. The Phase 10 inline-minimal skeletons/empty states in `dashboard/page.tsx` + 5 dashboard components get replaced with the canonical primitives (D-D-11 commitment). Each retrofit is its own atomic commit so it's easy to verify the dashboard's visual continuity didn't regress.
- **D-S-07:** Every state primitive ships with axe-core test coverage; the `EmptyState` + `PartialFailureBanner` have explicit `role="status"` / `role="alert"` semantics; `PerSourceStatusStrip` uses `aria-live="polite"` so screen readers announce source updates without yanking focus.

### Chip-bar filter UX

- **D-F-01:** URL sync is **immediate per-chip, 250ms debounced on search**. Severity / source / status / KEV chips update `?` query params synchronously on click. Search input pushes after 250ms idle. Implements UX-03-04 "every change updates ?query" faithfully without thrashing the router on each keystroke.
- **D-F-02:** Chips show **live counts contextual to other applied filters**: `Critical · 12` / `High · 47` / `Qualys · 287`. Counts reflect "how many would match if this chip were toggled" \ — facet calculation under all OTHER applied filters. Backend returns `facets: { severity: {critical:12, high:47, ...}, source: {qualys:287, ...} }` alongside the result list.
- **D-F-03:** Source chip list is **fetched live** from the facet endpoint, not hardcoded. A tenant with only AWS Inspector connectors sees `[AWS Inspector]`; a tenant with Qualys + Tenable sees both. Avoids visible-but-irrelevant chips.
- **D-F-04:** Saved filters: **read-only** in Phase 11. Backend `/api/v1/vulnerabilities/saved-filters` already exists. The violet `★ Today's triage` pill in the chip bar applies the user's first saved filter (or stays hidden if none). Save / rename / delete UX deferred — adds when a user actually asks.
- **D-F-05:** `useUrlState` hook (Phase 10 fix WR-04 — null-clamp before allow-list `includes`) is reused for single-value params. A new `useUrlStateList<T>(key, allowed, default)` variant is added for multi-value filter chips (e.g., `?severity=critical&severity=high`). XSS clamp pattern carries forward identically.

### Drill-panel behavior

- **D-P-01:** Panel closes via **all four**: × button (top-right of panel), Esc key, click on the table area outside the panel, OR click another row (which swaps content instead of closing — "row-swap"). Matches the validated `interaction-patterns.md` sketch + WCAG keyboard nav expectations.
- **D-P-02:** Panel state is **URL-encoded**: `?cve=CVE-2024-3094&open=drill`. Reload restores the open panel; the URL is link-shareable. This **closes the Phase 10 stubs** — Top5Card row links to `?cve=...&open=drill` already exist in `frontend/src/components/dashboard/top5-card.tsx`; Phase 11 honoring this URL completes the contract.
- **D-P-03:** Mobile (<900px): panel becomes a **`vaul` bottom sheet** sliding up from the bottom. Adds `vaul@^1.x` as a new frontend dep. Aligns with Phase 15's `vaul` commitment for modals→sheets (UX-07-02) so Phase 15 doesn't have to rip-and-replace.
- **D-P-04:** Action confirmation semantics:
  - **Snooze**: immediate via `useSnoozeMutation` (Phase 10) + undo toast (existing `Toast.action` slot, default 3000ms). Reuses the Phase 10 pattern verbatim. Undo calls `useUndoSnoozeMutation`.
  - **Create ticket**: **confirmation modal** (existing `ConfirmModal` primitive in `components/ui/`). Side-effect on Jira/Asana — irreversible from our side. Modal shows the target provider + which CVE; confirm fires `useCreateTicketMutation`, which on success toasts `Ticket JIRA-1234 created · View` and on failure surfaces the API error inline.
- **D-P-05:** Panel content order (top→bottom, per `interaction-patterns.md`): Drill header (CVE + severity pill + KEV badge + close ×) → CVSS section → Affected hosts → Description → Remediation → Activity (audit log scope) → Actions (Snooze / Create ticket).
- **D-P-06:** Focus management: when the panel opens, focus moves to the panel's close button (not auto-focus to first interactive — avoids accidentally triggering an action). Tab cycles through panel interactives; Shift-Tab from close button returns to the originating row. Esc returns focus to the originating row (or first row if origin was removed by a filter change).

### Table view + interactions

- **D-T-01:** Sortable columns: **Severity, CVE, CVSS Score, SLA**. Backend `?sort=<field>&order=asc|desc` extended (Phase 10 already shipped `?sort=triage`). Click column header cycles asc → desc → clear (back to default `?sort=triage`). The other 3 columns (Title/Product, Asset, Status) stay unsorted in Phase 11 — they're not sort axes analysts use enough to justify the backend surface.
- **D-T-02:** Full keyboard table for UX-07-03: rows are `<tr tabindex="0">`; `Enter` or `Space` opens the drill panel; `↑` / `↓` move focus row-to-row (wraps within page); `Home` / `End` jump to first / last row of the page; `Esc` closes panel + returns focus to originating row; `Tab` after panel-open moves focus into the panel. Implements Phase 15's keyboard requirement for this surface so Phase 15's quality gate doesn't bounce. Sticky header is announced once via `aria-rowindex` for screen readers; mid-table re-announcement skipped to avoid noise.
- **D-T-03:** **Pagination, no virtualization**. Backend paginates (default `page_size=50`, max `200`). Pagination component reused from existing `components/ui/Pagination.tsx` (v1) — restyled for sunset tokens if it isn't already. Add virtualization if profiling later shows pain at large page sizes; explicit non-goal for Phase 11.
- **D-T-04:** Sticky header on table scroll. CSS `position: sticky; top: 0` on `<thead>`. Sticky background matches `--color-surface` so it doesn't pop visually against rows. No scroll-shadow effect (avoid Phase 9 D-39 v1-styled chrome).

### View toggle (By-CVE ↔ By-Host)

- **D-V-01:** Toggle data source: **backend `?group=host`** parameter on `/api/v1/vulnerabilities`. By-CVE (default) returns the flat list; By-Host returns one row per asset with a denormalized severity breakdown (`{ host, ip, severity_counts: { critical, high, medium, low }, top_cve_id, top_cvss, ... }`). Server-side grouping respects pagination correctly (10k vulns on 500 hosts paginates as 500 host-rows, not 10k re-grouped client-side).
- **D-V-02:** Per-source progress strip (`PerSourceStatusStrip`) **composes from existing endpoints**: reads `/api/v1/connectors` for enabled connectors + their `last_sync_status` (done / syncing / failed / never-synced) + per-connector vuln count from the facet endpoint (D-F-02). No new dedicated `source-status` endpoint — composition saves backend surface and reuses data we're already fetching for chips.
- **D-V-03:** **Bulk actions deferred**. V1's `BulkActions.tsx` (checkbox column + bulk-bar for bulk snooze / assign / export) does **not** port to Phase 11. UX-03 doesn't enumerate bulk; bulk re-emerges when a user requests it, in its own phase. Keeps the Phase 11 rewrite clean.
- **D-V-04:** Stale rows (UX-S-03) identified by **`row.source` membership in failed-sources list** propagated from the partial-failure context. No `is_stale` column added to the data model. The `PartialFailureBanner` (via `useQueryErrors`) knows which source(s) failed; each table row's existing `source` field (`'QUALYS'` / `'AWS_INSPECTOR'` / etc.) is matched and `bg-amber-soft` tint is applied to rows whose source is failing. Zero schema change.

### Claude's Discretion

- **"Clear all" scope** — what the clear-all action wipes (search input only / chips only / both) is the planner's call. Default leaning: clear both, since the requirement (UX-03-01) describes clear-all as a chip-bar action sibling to the chips themselves, and analysts toggle search and chips as a unit.
- **Empty-state "violet lightbulb suggestion" content** — UX-S-02 says "save-as-watch suggestion" but with Phase 11 saved-filter being read-only (D-F-04), the suggestion stays static text guiding the user to adjust filters (e.g., "Try broadening severity or removing the date range") rather than offering save-as-watch CTA. Save-as-watch CTA returns when full saved-filter CRUD ships.
- **Pagination control sunset polish** — `components/ui/Pagination.tsx` exists from v1; the planner decides whether to restyle in this phase or carry the v1 styling forward (Phase 9 visual debt note still applies — v1-styled chrome is tolerable between phases).
- **Skeleton column-kind set** — D-S-01 lists `'pill' | 'mono' | 'text'`; planner can extend (e.g., `'avatar'`, `'badge'`) if a state-primitive consumer needs them. The contract is "shape props, not generic counts."

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 11 requirements
- `.planning/REQUIREMENTS-v2.md` §UX-03-01..06 — `/vulnerabilities` screen requirements
- `.planning/REQUIREMENTS-v2.md` §UX-S-01..05 — state patterns (loading / empty / partial-failure / total-failure / toasts)
- `.planning/REQUIREMENTS-v2.md` §UX-07-03 — keyboard / a11y commitments (D-T-02 implements the row-nav slice)
- `.planning/ROADMAP.md` "Phase 11" entry — goal + 7 success criteria

### Design system + sketches (Phase 9/10 + Phase 11 owns its slice)
- `.claude/skills/sketch-findings-getvul/references/state-patterns.md` — loading / empty / error visual language (mandatory reading; defines the look of D-S-01..04 primitives)
- `.claude/skills/sketch-findings-getvul/references/interaction-patterns.md` — drill panel, chip bar, segmented control, row keyboard nav (D-P-01..06, D-T-02)
- `.claude/skills/sketch-findings-getvul/references/page-layouts.md` — list-with-side-panel layout pattern
- `.claude/skills/sketch-findings-getvul/references/visual-language.md` — severity pills, KEV badge, SLA tiering, status family
- `.claude/skills/sketch-findings-getvul/references/foundation.md` — sunset CSS variables (consumed via Tailwind)
- `.claude/skills/sketch-findings-getvul/references/copy-voice.md` — empty-state / error-state copy tone
- `.claude/skills/sketch-findings-getvul/sources/003-vulnerabilities-sunset/index.html` — variant C (chip bar + side panel) HTML mockup (chosen variant)
- `.claude/skills/sketch-findings-getvul/sources/004-states-sunset/index.html` — state patterns mockup (loading / empty / partial-failure)

### Prior phase context (load-bearing decisions inherited)
- `.planning/phases/09-login-foundation/09-CONTEXT.md` — sunset tokens, `data-theme` architecture, AppShell, primitive set
- `.planning/phases/10-dashboard/10-CONTEXT.md` — TanStack Query setup, query-key convention, URL-sync pattern, snooze mutation, Card/Stat/StatStrip/ActivityFeed/ErrorBoundary primitives
- `.planning/phases/10-dashboard/10-REVIEW.md` + `.planning/phases/10-dashboard/10-REVIEW-FIX.md` — Phase 10 code-review findings and fixes (BL-06 401-retry restriction + WR-04 useUrlState clamp are directly relevant to Phase 11)

### Backend
- `backend/app/vulnerabilities/router.py` — current `/vulnerabilities` endpoint signatures (must extend for `?facets=`, `?group=host`, expanded `?sort=`)
- `backend/app/vulnerabilities/schemas.py` — `VulnerabilitySummary` Pydantic model (Phase 11 may add a `VulnerabilityByHost` variant)
- `backend/app/vulnerabilities/saved_filters.py` — existing saved-filter endpoints consumed read-only by D-F-04
- `backend/app/connectors/router.py` — `/api/v1/connectors` consumed by `PerSourceStatusStrip` per D-V-02

### Project-level
- `CLAUDE.md` — auto-loads `sketch-findings-getvul` skill on UI work; non-negotiables (no `!important`, no font substitution, mandatory empty/loading/error states)
- `.planning/PROJECT.md` — vision, milestone goals, no-websocket constraint (forecloses SSE option in D-V-02)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable assets (carry forward verbatim)

- **`frontend/src/components/ui/Card.tsx`** (Phase 10 D-P-01) — used as the EmptyState container shell; the slot pattern in D-S-02 mirrors `Card` / `Card.Header` / `Card.Body` / `Card.Footer`
- **`frontend/src/components/ui/Toast.tsx`** + **`ToastProvider.tsx`** (Phase 9 + Phase 10 extensions) — UX-S-05 already satisfied; consumers fire `toast({ variant, message, action })`
- **`frontend/src/components/ui/ConfirmModal.tsx`** (v1) — drives the D-P-04 ticket-create confirmation
- **`frontend/src/components/ui/Pagination.tsx`** (v1) — reused for table pagination, possibly restyled for sunset
- **`frontend/src/hooks/use-url-state.ts`** (Phase 10 + WR-04 fix) — single-value URL state. Phase 11 adds `use-url-state-list.ts` variant for multi-value chips
- **`frontend/src/lib/api.ts`** (Phase 10 BL-06 fix) — 401-retry restricted to safe methods is the right baseline; the new ticket-create mutation must throw `Session expired during mutation` cleanly on auth loss
- **`frontend/src/lib/queries/keys.ts`** (Phase 10 D-D-03) — extend with `vulnerabilities.list({filters, group, page})`, `vulnerabilities.facets({filters})`, `vulnerabilities.detail(id)`
- **`frontend/src/lib/mutations/use-snooze.ts`** + **`use-undo-snooze.ts`** (Phase 10) — drill-panel snooze action reuses these unchanged
- **`frontend/src/components/ui/error-boundary.tsx`** (Phase 10 D-P-06 + WR-11) — wraps the page for catastrophic failure isolation
- **`frontend/src/components/ui/activity-feed.tsx`** (Phase 10) — drill-panel's "Activity" section may consume this primitive directly if the audit-log API shape aligns

### Established patterns (cannot deviate)

- **TanStack Query v5** (Phase 10 D-D-01) — domain-first query keys, 60s `staleTime` for stats-y queries, 0–1 retry, refetch-on-focus, logout clears cache
- **Sunset tokens via Tailwind utilities** (Phase 9 D-04) — never hex literals; consume `bg-surface` / `text-text` / `border-border` / `bg-severity-critical` / `bg-danger-soft` / etc.
- **No `!important`** anywhere (Phase 9 D-04)
- **Forced-colors / reduce-motion gates** (Phase 9 a11y commitments) — every animation respects `prefers-reduced-motion`; every interactive element survives forced-colors
- **TDD discipline** — Phase 10 ran 2 commits per multi-file task (RED test → GREEN impl); Phase 11 follows the same pattern
- **No raw palette utilities** (`emerald-400`, `red-400`, `bg-gray-900`) in production code — only sunset tokens (Phase 10 lesson from code review)
- **Frontend → backend type drift surfaces in tests only with happy-path data** — Phase 10 BL-01/BL-02 lesson: align frontend types to backend nullability and write tests against the actual wire shape, not idealized fixtures

### Integration points

- **`frontend/src/app/(authed)/dashboard/vulnerabilities/page.tsx`** — full rewrite (was 658 lines in v1)
- **`frontend/src/components/vulnerabilities/`** — v1 surface deleted (`VulnFilters.tsx`, `VulnTable.tsx`, `BulkActions.tsx`)
- **`frontend/src/app/(authed)/dashboard/page.tsx`** + **5 dashboard components** — Phase 10 retrofit: swap inline-minimal skeletons for canonical primitives (D-S-06)
- **`frontend/src/app/dev/primitives/page.tsx`** — extend with the new state-pattern primitives showcase (Phase 10 has the dev-primitives split + lazy loader from BL-05 fix; new entries land in the lazy showcase)
- **`backend/app/vulnerabilities/router.py`** — extend `list_vulns` for `?facets=`, `?group=host`, expanded `?sort=`
- **`backend/app/vulnerabilities/schemas.py`** — add `FacetsResponse`, possibly `VulnerabilityByHost` schemas

</code_context>

<specifics>
## Specific Ideas

- **Variant C of sketch-003** (`.claude/skills/sketch-findings-getvul/sources/003-vulnerabilities-sunset/index.html`) is the chosen chip-bar + side-panel design. Planner reads the HTML directly for layout fidelity.
- **Sketch-004 mockup** (`004-states-sunset/index.html`) is the canonical reference for skeleton row shapes, partial-failure banner layout (HTTP code + last sync + retry count + request ID + Retry / View trace actions), per-source status cards, and stale-row amber tinting.
- **Phase 10's Top5Card row links to `?cve=...&open=drill`** — Phase 11 must honor this URL contract literally so the dashboard deep links work after Phase 11 lands.

</specifics>

<deferred>
## Deferred Ideas

- **Saved-filter CRUD** (save current filter / rename / delete / dropdown of saved filters) — emerges when a user actually asks for it
- **Bulk actions** (multi-row select + bulk snooze / assign / export) — v1 surface dropped; revives when needed in its own phase
- **Table virtualization** (`@tanstack/react-virtual`) — pagination handles most tenants; revisit at the v2.x perf phase if profiling shows pain
- **Real-time per-source SSE / WebSocket progress streaming** — out of scope per PROJECT.md no-websocket constraint; per-source strip stays poll-driven
- **Light-theme polish** — UX-D-03 milestone-wide deferral still applies
- **Save-as-watch lightbulb suggestion** — depends on saved-filter CRUD; static text replaces it for Phase 11
- **Column reordering / column-visibility toggle / saved table layouts** — power-user features that haven't been validated
- **Per-row preview-on-hover** — UX-friendly but not requested; row-click → drill panel is sufficient
- **Backend `is_stale` column on rows** — D-V-04 keeps staleness derived from `row.source` membership; making it explicit on rows is bigger surface for negligible benefit
- **Drill-panel comment-on-vulnerability surface** — v1 has activity log; v2 keeps it read-only in the panel. Comment-on-vuln is a separate workflow when needed

</deferred>

---

*Phase: 11-vulnerabilities-state-patterns*
*Context gathered: 2026-05-21*
