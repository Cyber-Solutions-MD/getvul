# Phase 10: `/dashboard` - Context

**Gathered:** 2026-05-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Ship `/dashboard` as the analyst's post-login landing screen against the validated sunset design system. The page is **action-first**: an urgency hero (or quiet-win empty state) replaces the conventional page-head; a 4-tile stat strip with day-over-day deltas sits below; a 30-day severity-stacked trend chart with 7d/30d/90d range toggle follows; a Top 5 to triage card and a 340px right-rail activity feed close out the main column.

Phase 10 also introduces the **shared data layer** (TanStack Query v5) that every authed screen in v2.0 consumes, the **first set of pure-presentation primitives** (Card, Stat, StatStrip, ActivityFeed, TrendChart, ErrorBoundary) that Phases 11–14 reuse verbatim, and **five concrete backend extensions** (severity-stacked trend buckets, dashboard tile data with deltas + onboarding state, top-vuln field, triage-sorted vulnerabilities, nav count chips) supporting that page.

**In scope:**

- Rewrite of `frontend/src/app/(authed)/dashboard/page.tsx` (v1 tab+stat-grid replaced)
- New `(authed)/layout.tsx` change: mount `QueryClientProvider` next to AppShell
- New primitives in `frontend/src/components/ui/`: `card.tsx`, `stat.tsx`, `stat-strip.tsx`, `activity-feed.tsx`, `trend-chart.tsx`, `error-boundary.tsx`
- `/dev/primitives` extended with entries for the new primitives
- New TanStack Query hooks under `frontend/src/lib/queries/`: `useStats`, `useTrends`, `useTopTriage`, `useRecentNotifications` (domain-first key convention)
- Snooze mutation hook + cache invalidation for `Snooze 1h`
- `useDocumentTitle` hook for dynamic `(N) Dashboard · GetVul` tab title
- Sidebar nav-chip wiring (Vulnerabilities open count, Assets total, Tickets open) replacing Phase 9 placeholder `—`
- Per-primitive `.test.tsx` with axe + a `dashboard.test.tsx` page-level integration test
- Backend Wave 0: `severity_trends` field on `/api/v1/vulnerabilities/trends`; `dashboard_tiles` + `top_vuln` + nav counts + `onboarding_state` on `/api/v1/vulnerabilities/stats`; `?sort=triage&limit=N` on `/api/v1/vulnerabilities`
- Backend pytest per endpoint extension

**Out of scope (other phases / future):**

- Working `⌘K` command palette (still visual scaffold per Phase 9 D-37)
- Phase 11+ canonical state-pattern primitives (SkeletonTable, EmptyState, PartialFailureBanner, Toast) — Phase 10 ships inline-minimal versions for retrofit later
- Vulnerabilities `?cve=&open=drill` URL contract honoring — Phase 11 owns the chip-bar + drill panel; Phase 10's Top-5 row links land as stubs that 404 until then
- Light-mode visual polish on the new primitives (UX-D-03 / D-06 — still deferred)
- Real-time push (websocket / SSE) — explicitly Out of Scope in PROJECT.md
- Telemetry / product-analytics events
- Storybook
- Per-user dashboard preferences (range toggle persistence beyond URL)
- CI bundle-size gating (PROD-02 territory)
- Lighthouse pass/fail gates (Phase 15)
- Print stylesheet

</domain>

<decisions>
## Implementation Decisions

### Data layer + state patterns

- **D-D-01:** TanStack Query v5 is the v2.0 client data layer for every authed screen. ~13 kB gzipped, replaces v1's `useEffect + Promise.all`. Sets the convention for Phases 11–14.
- **D-D-02:** `QueryClientProvider` mounts inside `(authed)/layout.tsx` next to AppShell. Single shared client. Cache survives navigation across authed routes. `/login` stays outside the group so QueryClient is not in that bundle.
- **D-D-03:** Query-key convention is domain-first: `['vulnerabilities', 'stats']`, `['vulnerabilities', 'trends', { range }]`, `['notifications', 'recent', { limit }]`. First segment = domain, second = sub-resource, third = params object. Enables bulk-invalidate by domain.
- **D-D-04:** Range toggle (`7d`/`30d`/`90d`) is URL-synced via `?range=30d`. `useSearchParams` + `router.replace({ scroll: false })` pattern. Anticipates Phase 11's URL-synced chip-bar filters.
- **D-D-05:** URL is the only source of truth for the range. Reload-without-URL defaults to 30d. No localStorage fallback — per-user persistence is a future feature.
- **D-D-06:** `staleTime` per query: 60s for `/stats`, `/overview`, `/trends`; 30s for `/notifications`. Both refetch on window focus + on mount (TanStack defaults).
- **D-D-07:** Retry policy: 1× retry on 5xx for `/stats` + dashboard-tiles queries (most-visible); 0 retries elsewhere. No retries on 4xx.
- **D-D-08:** On 401 from any dashboard query: trigger silent token refresh via the existing `useAuth` path (AUTH-03). On refresh failure, redirect to `/login?next=/dashboard`.
- **D-D-09:** Logout clears the entire TanStack cache: `useAuth().logout()` calls `queryClient.clear()`. Per-tenant isolation when a different user signs in same browser.
- **D-D-10:** Per-fetch partial-failure handling. Use `Promise.allSettled`-style independent queries (TanStack does this natively per-`useQuery`). Failed Card shows muted bg + inline `<error code> · [Retry]` block; sibling cards continue rendering their own data.
- **D-D-11:** Loading states are inline-minimal in Phase 10 — skeleton hero, skeleton tiles, skeleton chart container. Render top-down as data arrives. Phase 11's canonical SkeletonTable / EmptyState / PartialFailureBanner / Toast retrofit Phase 10 later.
- **D-D-12:** Cross-tab sync via TanStack's refetch-on-focus (≤30s for activity, ≤60s for stats). No BroadcastChannel in Phase 10 — acceptable lag for the polling model.
- **D-D-13:** Snooze mutation invalidates `['vulnerabilities', 'stats']`, `['vulnerabilities', 'dashboard-tiles']`, and `['vulnerabilities']` queries on success. Hero refetches naturally. No optimistic update in Phase 10 — that's a future upgrade.

### Chart implementation

- **D-C-01:** Use existing `recharts ^2.12.0`. No new chart lib. Tremor/Visx considered and rejected (same weight or more code).
- **D-C-02:** Wrap recharts behind a `TrendChart` primitive (`components/ui/trend-chart.tsx`) with a typed `<TrendChart data range onRangeChange />` API. Hides the lib so a future swap is local. Listed in `/dev/primitives`.
- **D-C-03:** Bundle-split via `dynamic(() => import('@/components/ui/trend-chart'), { ssr: false, loading: () => <ChartSkeleton /> })`. recharts only loads when the chart enters the route, satisfying success criterion #3.
- **D-C-04:** Custom tooltip rendering sunset chrome with severity glyphs (`■ ▲ ◆ ○`) + counts. Range toggle is a 3-segment control wired to `?range=`. Hover nudge = scale 1.04 + slight y-translate on the hovered stack via recharts' `onMouseOver`. Honors `prefers-reduced-motion`.
- **D-C-05:** Series colors bind to `var(--color-severity-critical/high/medium/low)` per visual-language.md. Severity is also encoded by glyph in the tooltip (survives grayscale).
- **D-C-06:** y-axis auto-scales to the nearest 10 above peak; 4 evenly-spaced horizontal gridlines in `--color-border-subtle`. Y-axis labels right-aligned, mono font, `--color-text-muted`.
- **D-C-07:** x-axis: day 30 is **today** (rightmost bar = today, may be partial). Tooltip reads `Today (so far)` for the rightmost bar.
- **D-C-08:** Time-zone strategy: browser-local everywhere (`Intl.DateTimeFormat` with browser TZ). Chart dates, activity timestamps all local. `12m ago` relative format is TZ-free.
- **D-C-09:** Backend `/trends` extended with `severity_trends: { 'YYYY-MM-DD': { critical, high, medium, low }, … }` field. Single round-trip; shape matches the chart 1:1.
- **D-C-10:** Chart on mobile: ResponsiveContainer width; reduce y-axis to 2 gridlines below 640px. Hover nudge becomes tap-to-reveal.

### Hero semantics

- **D-H-01:** Headline number = count of **Open + Critical** vulnerabilities, ignoring snoozes. Drives all hero state. Sourced from `/stats.dashboard_tiles.critical_open.value`.
- **D-H-02:** Headline grammar: `1 critical CVE needs your eyes` / `N critical CVEs need your eyes`. Plural picked client-side from the count.
- **D-H-03:** Sub-line: highest-CVSS open-critical CVE with its host + path, copy-voice exemplar (`Top one is on prod-db-01 — Postgres path, CVSS 9.8, exploited in the wild.`). Backend `/stats.top_vuln` field returns `{ cve_id, host, path, cvss, on_kev, exploited }`.
- **D-H-04:** Sub-line truncation: CSS `line-clamp: 2` + ellipsis. Mono identifiers (hostnames, paths) never broken mid-word. Tooltip on hover shows the full string.
- **D-H-05:** Pulsing dot eyebrow: `--color-severity-critical` red when count > 0 (pulses; honors `prefers-reduced-motion` — color stays, animation stops). `--color-success` green solid when count = 0.
- **D-H-06:** `Start triage` primary CTA routes to `/dashboard/vulnerabilities?status=open&severity=critical`. Phase 11 chip-bar honors the URL convention. On Phase 10 ship the link lands on the existing (still-v1-styled or empty) vulnerabilities route.
- **D-H-07:** `Snooze 1h` secondary CTA snoozes the **top sub-line CVE** for 1h via the existing per-CVE snooze API. Hero refetches.
- **D-H-08:** Snooze flow: **immediate fire-and-forget + Undo toast**. Toast copy `Snoozed CVE-2024-… for 1h · [Undo]`. 8s undo window before auto-dismiss. Undo button calls the same snooze API to reverse.
- **D-H-09:** Quiet-win trigger: open-critical count = 0 (same definition as the headline). Hero swaps to `Nothing critical right now` framing. Stat strip + chart still render so the analyst can verify.
- **D-H-10:** Hero CTAs side-by-side, triage left (primary `cta` variant), snooze right (secondary). Wrap to stacked at <640px.
- **D-H-11:** Icon prefix on CTAs per copy-voice.md: `Zap` on Start triage, `Clock` on Snooze 1h. 14px lucide icons via `Button.leftIcon` from Phase 9 D-25.
- **D-H-12:** Hero is the page header — no separate page-head row above with title + actions. Page-level actions live in the hero CTA pair only.

### Stat strip

- **D-S-01:** Backend computes day-over-day deltas from `DailySnapshot` table. `/stats` returns `dashboard_tiles: { critical_open: {value, delta, delta_direction}, sla_at_risk: {…}, kev: {…}, mttr_30d: {…} }`. Single round-trip.
- **D-S-02:** SLA-at-risk definition: vulnerabilities within **25%** of their per-severity SLA deadline, not yet breached. Scales across severities naturally.
- **D-S-03:** Delta direction-aware coloring: red `▲` when "up is bad" (critical_open up, sla_at_risk up, kev up, mttr up), green `▼` when "down is good". Color paired with the `▲`/`▼` glyph and signed number for grayscale survival.
- **D-S-04:** Delta rendering: unicode `▲`/`▼` glyph + signed number + `from yesterday`. Hidden during loading (no spinner inside the tile).
- **D-S-05:** Each tile gets a muted 16px lucide icon top-right in `--color-text-muted`: ShieldAlert (critical_open) / Clock (sla_at_risk) / Flame (kev) / TrendingDown (mttr). Icon is de-emphasized so the number stays the hero.

### Top 5 to triage

- **D-T-01:** Ranking algorithm: (1) CISA KEV listed first, (2) within KEV/non-KEV bucket by CVSS desc, (3) ties broken by SLA hours-to-breach asc.
- **D-T-02:** Backend wiring: reuse `/api/v1/vulnerabilities` with `?sort=triage&limit=5`. Server-side sort. Same pattern Phase 11 uses for filtered lists.
- **D-T-03:** Row click destination: `/dashboard/vulnerabilities?cve=CVE-2024-…&open=drill`. Phase 11 will honor `?open=drill` to pre-open the side-panel.
- **D-T-04:** Fewer than 5 criticals: pad with next-highest severity (High → Medium → Low). Always show 5 rows if any open vulns exist. Each row shows its real severity glyph.
- **D-T-05:** Top-5 mobile: same 5 rows; rows wrap to 2 lines if needed. Severity glyph + CVE ID stay on row 1.

### Activity feed

- **D-A-01:** Category → icon-variant mapping: `new_critical_vuln` → pink, `sla_breach` → amber, `sync_failure` → violet, `risk_change` → success.
- **D-A-02:** Lucide icons per category: `ShieldAlert` (critical) / `Clock` (sla) / `WifiOff` (sync) / `TrendingUp`-or-`TrendingDown` (risk, picked by direction). Rendered inside a 28px rounded-square tinted background.
- **D-A-03:** Empty state copy: `No recent activity. We'll show events here as they happen.` Sentence case, no exclamation per copy-voice.md.
- **D-A-04:** 1–4 events render as-is. Don't pad to 5 with placeholders. Backend returns N from `/notifications?limit=5`.
- **D-A-05:** Row click navigates to context: `new_critical_vuln` → vuln drill, `sla_breach` → ticket detail (or vuln drill fallback), `sync_failure` → `/dashboard/connectors`, `risk_change` → asset detail. Routes that don't exist until later phases are `<Link>` stubs that 404 cleanly until then.
- **D-A-06:** Activity rail width 340px per ROADMAP. Sticky right-rail behavior — scrolls with page (no independent scrollbar).
- **D-A-07:** When stacked below main content (<1280px), rail renders as full-width section with `Recent activity` heading + 5 rows.

### Sidebar nav-chip wiring

- **D-N-01:** Three chips wired: Vulnerabilities (open count), Assets (total), Tickets (open count). CSPM / Connectors / Users / Settings do not get chips. Dashboard does not get a chip (the page IS the dashboard).
- **D-N-02:** Counts come from a single shared `/stats` query. Add `vuln_open_count`, `asset_total_count`, `ticket_open_count` to the response. AppShell calls `useStats()` once. Cache stays warm across navigation.
- **D-N-03:** Loading state: dash (`—`) per Phase 9 D-35 until first load resolves. On error, leave dash. No skeleton bar to avoid layout shift.

### Onboarding empty state (distinct from quiet-win)

- **D-O-01:** Detect via backend flag: `/stats` returns `onboarding_state: 'no_scanners' | 'no_data_yet' | 'ready'`.
- **D-O-02:** `no_scanners`: dedicated full-page panel — short copy explaining there's nothing yet + single `Connect a scanner` CTA linking to `/dashboard/connectors`. Replaces the entire dashboard.
- **D-O-03:** `no_data_yet`: `Your first sync is in progress` panel with last-sync-attempted timestamp + `[Refresh]` button.
- **D-O-04:** `ready`: render the dashboard normally (hero / strip / chart / top-5 / activity).

### Tab title

- **D-Tab-01:** Dynamic browser tab `<title>`: `(N) Dashboard · GetVul` when open-critical count > 0, else `Dashboard · GetVul`. Set via a small client-only `useDocumentTitle` hook that writes to `document.title`. Phase 11 may reuse for `(12) Vulnerabilities · GetVul`.

### Accessibility + motion

- **D-Ax-01:** Heading hierarchy — sr-only h1 `Dashboard` + h2 per section (Hero h2 = headline; Stat strip h2 `Today at a glance`; Chart h2 `30-day vulnerability trend`; Top-5 h2 `Top 5 to triage`; Activity h2 `Recent activity`).
- **D-Ax-02:** Landmarks: AppShell provides `<main>` from Phase 9. Each section is `<section aria-labelledby="…">`. Activity sidebar is `<aside aria-label="Recent activity">`. Skip-link from Phase 9 reaches `<main>`.
- **D-Ax-03:** Chart screen-reader accessibility — TrendChart renders a visually-hidden `<table>` below with date columns × severity rows × counts. Tab-reachable.
- **D-Ax-04:** Reduce-motion handling: pulsing dot stops (color stays); chart bar-rise renders at final height; tile counter shows final number immediately. Each primitive owns its own preference check beyond `globals.css` zero-out.
- **D-Ax-05:** Initial focus on /dashboard load: no programmatic focus. Browser default puts focus on `<body>`. Skip-link still works. Avoids screen-reader auto-announce annoyance.
- **D-Ax-06:** Forced-colors mode handling: `@media (forced-colors: active)` block in `globals.css` maps surfaces, borders, text, CTA backgrounds to system keywords (`Canvas`, `CanvasText`, `ButtonFace`, etc.). Sunset gradient becomes a single accent the OS picks. Severity glyphs survive grayscale (already there). Pragmatic WCAG 1.4.8 baseline.
- **D-Ax-07:** Dark-mode-only visually for Phase 10. Light theme architecture wired but disabled in UserChip (Phase 9 WR-03 mitigation stands). D-06 / UX-D-03 still tracks full light pass later.

### Mobile breakpoints

- **D-M-01:** Activity sidebar (340px right rail) stacks below main content at <1280px. Above 1280px: 2-column with activity on the right.
- **D-M-02:** Stat strip columns: 4 cols at ≥1280px → 2 cols at 768–1279px → 1 col at ≤640px. Inherits StatStrip's auto-grid from D-P-03.
- **D-M-03:** Sidebar (Phase 9 D-41) already hides ≤999px — Phase 10 honors. Mobile replacement nav remains scoped to Phase 15.

### Performance

- **D-Perf-01:** First-Load JS budget for `/dashboard`: **180 kB**. /login is 145 kB; +13 kB for TanStack Query + ~22 kB headroom for new primitives + page-level code. recharts is route-split (not in first-load).
- **D-Perf-02:** Vitals: soft targets in Phase 10 (LCP < 2.5s, INP < 200ms). Phase 15 owns pass/fail gates.
- **D-Perf-03:** Bundle visibility: `npm run build` First-Load JS column captured in `10-VERIFICATION.md` against the 180 kB budget. No CI fail-on-regression check yet (PROD-02 territory).

### Initial render strategy

- **D-R-01:** `/dashboard/page.tsx` is a full client component (`'use client'`). Matches Phase 9 because `useAuth` reads localStorage; RSC can't see localStorage. Sets v2.0 convention.
- **D-R-02:** Skeleton priority: skeleton hero + skeleton stat strip + skeleton chart container render at mount. As each query resolves, its block paints. Reduces perceived latency vs single page-wide spinner (v1).

### Error handling

- **D-E-01:** Per-section `<ErrorBoundary>` primitive (React 19 native) wraps Hero, StatStrip, TrendChart, Top5, ActivityFeed. A crash in one section doesn't unmount others. Fallback UI matches D-E-02's inline error pattern. Phase 11+ reuses.
- **D-E-02:** Inline error block within the failed section: `<section> [icon] Trend unavailable. HTTP <code> · Request ID <req_…> · [Retry now]`. Per copy-voice.md error pattern. Rest of dashboard renders normally.
- **D-E-03:** Hero query failure: inline error block in the hero region. Rest of page below tries to load independently (D-D-10 partial-failure).
- **D-E-04:** Toasts only for user-initiated events (Snooze success/failure). Reuse existing `ToastProvider`. Don't toast background fetch failures — those are inline.

### Test floor

- **D-Test-01:** Per-primitive `.test.tsx` with axe assertions for Card, Stat, StatStrip, ActivityFeed, TrendChart, ErrorBoundary. Same shape as Phase 9 D-30.
- **D-Test-02:** Page-level `dashboard.test.tsx` mocks the four queries and asserts the page renders all blocks (hero / strip / chart / top-5 / activity) + the partial-failure path.
- **D-Test-03:** Backend pytest per endpoint extension: `test_severity_trends.py`, `test_dashboard_tiles.py`, `test_triage_sort.py`, `test_top_vuln.py`. Each tests shape + SQL math (delta accuracy, ranking).
- **D-Test-04:** `/dev/primitives` extended with entries for all six new primitives. No Storybook (out of scope per REQUIREMENTS-v2).

### Primitive API shape

- **D-P-01:** `<Card variant="surface|elevated|outline" padding="sm|md|lg">{children}</Card>` — single primitive, variant prop. `<Card.Header>` / `<Card.Body>` / `<Card.Footer>` subcomponents via composition.
- **D-P-02:** `<Stat label value delta deltaDirection deltaIsGood hint? icon?>` — typed props. Handles `prefers-reduced-motion` count-up internally.
- **D-P-03:** `<StatStrip>{children}</StatStrip>` — wraps 1–6 `<Stat>` children in a responsive grid (1col mobile / 2col tablet / N-col desktop where N = child count up to 4). Caller doesn't manage breakpoint columns.
- **D-P-04:** `<ActivityFeed items emptyCopy?>` — items typed as `{ id, category, title, body?, occurredAt, href? }[]`. Primitive owns row layout (icon variant + glyph + `Xm ago` per copy-voice). Caller provides items.
- **D-P-05:** `<TrendChart data range onRangeChange>` — typed wrapper around recharts. See D-C-* for behavior.
- **D-P-06:** `<ErrorBoundary fallback={…}>` — React 19 native boundary primitive. Used per-section in `/dashboard`. Reused Phase 11+.

### Backend changes (consolidated)

- **D-B-01:** `GET /api/v1/vulnerabilities/trends?days=N` — add `severity_trends: { 'YYYY-MM-DD': { critical, high, medium, low }, … }` field.
- **D-B-02:** `GET /api/v1/vulnerabilities/stats` — add `dashboard_tiles: { critical_open: {value, delta, delta_direction}, sla_at_risk: {…}, kev: {…}, mttr_30d: {…} }`, `top_vuln: { cve_id, host, path, cvss, on_kev, exploited }`, `vuln_open_count`, `asset_total_count`, `ticket_open_count`, `onboarding_state: 'no_scanners' | 'no_data_yet' | 'ready'`.
- **D-B-03:** `GET /api/v1/vulnerabilities` — add `?sort=triage&limit=N`. Server-side ranking: KEV → CVSS desc → SLA-urgency.
- **D-B-04:** Confirm `POST /api/v1/vulnerabilities/{id}/snooze` exists for the hero CTA (planner verifies; not a discuss-phase decision).
- **D-B-05:** Existing `/api/v1/notifications?limit=5` is already shaped correctly (`category` + `occurred_at` + body); no change.
- **D-B-06:** Backend changes land in **Wave 0** before any frontend work. Frontend Wave 1+ consumes live backend. No mock-data risk.

### Real-time

- **D-RT-01:** No websocket / SSE / push. Polling-only via TanStack staleTime + refetch-on-focus (D-D-06). Honors PROJECT.md `Out of Scope` listing.

### Telemetry

- **D-Tel-01:** Skip telemetry / product analytics in Phase 10. No PostHog / Segment / Mixpanel. No `/audit-events` repurpose for product events. Belongs in its own future phase if/when scoped.

### Keyboard shortcuts

- **D-K-01:** No new keyboard shortcuts on /dashboard. `⌘K` stays visual-scaffold-only per Phase 9 D-37. No `G`-to-triage, no `S`-to-snooze. Future command-palette phase decides.

### Claude's Discretion

- Exact spacing rhythm between hero / strip / chart / top-5 — consume `--space-*` tokens; planner picks the rhythm.
- Specific gradient stops for hero CTA hover state — consume `--gradient-sunset`.
- Skeleton shape details (height, radius, shimmer) — within `--motion-*` + `--radius-*` tokens.
- Stat tile internal layout (label-on-top vs label-on-side) — planner picks per visual-language.md guidance.
- Pulse-urgency keyframe specifics — defined in `globals.css` per Phase 9 D-15; consumed here.

### Folded Todos

None — no pending todos surfaced for Phase 10 scope.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap + Requirements

- `.planning/ROADMAP.md` — Phase 10 success criteria (7 items)
- `.planning/REQUIREMENTS-v2.md` — UX-02-01..06 acceptance criteria
- `.planning/PROJECT.md` — milestone framing, Out-of-Scope list, constraints

### Design system (sketch findings skill)

- `.claude/skills/sketch-findings-getvul/sources/002-dashboard-sunset/index.html` — the dashboard sketch (urgency hero, stat strip, trend chart, top-5, activity rail)
- `.claude/skills/sketch-findings-getvul/references/page-layouts.md` — hero / list / detail patterns
- `.claude/skills/sketch-findings-getvul/references/visual-language.md` — severity (color + glyph + size), status pills, SLA tokens, providers, CTA chrome, severity-breakdown ribbon
- `.claude/skills/sketch-findings-getvul/references/state-patterns.md` — loading / empty / error patterns (Phase 10 ships inline-minimal; Phase 11 canonicalizes)
- `.claude/skills/sketch-findings-getvul/references/copy-voice.md` — every line of copy on this page must match (headline grammar, CTA verbs, error sentences, activity timeline format, no exclamation marks, no "Please"/"Welcome", numbers in numerals)
- `.claude/skills/sketch-findings-getvul/references/interaction-patterns.md` — chip bar, drill panel, bulk bar, timeline (mostly Phase 11+ but defines the URL-sync convention Phase 10 anticipates)
- `.claude/skills/sketch-findings-getvul/references/foundation.md` — sunset tokens (consumed; established Phase 9)
- `.claude/skills/sketch-findings-getvul/references/app-shell.md` — sidebar (Phase 9) + topbar (Phase 9)

### Prior phase context

- `.planning/phases/09-login-foundation/09-CONTEXT.md` — token system, theme, primitives, shell that Phase 10 consumes (D-01..D-53)
- `.planning/phases/09-login-foundation/09-REVIEW.md` — WR-01..WR-04 warnings to keep in mind (Input password wrap + dropdown border + light theme + json catch)
- `.planning/phases/09-login-foundation/09-HUMAN-UAT.md` — gaps surfaced: mobile-nav scoped to Phase 15; Light radio disabled until D-06; middleware location fix

### Code surface

- `frontend/src/app/(authed)/layout.tsx` — wire `QueryClientProvider` here
- `frontend/src/app/(authed)/dashboard/page.tsx` — rewrite target (currently v1 tab-based)
- `frontend/src/components/ui/` — six new primitives land here (Card, Stat, StatStrip, ActivityFeed, TrendChart, ErrorBoundary)
- `frontend/src/components/shell/sidebar.tsx` — wire count chips
- `frontend/src/lib/auth.tsx` — call `queryClient.clear()` from `logout()`; integrate 401 refresh-then-retry
- `frontend/src/app/dev/primitives/page.tsx` — extend with new primitive entries
- `backend/app/vulnerabilities/router.py` + `backend/app/vulnerabilities/trends.py` + `backend/app/vulnerabilities/stats.py` — endpoint extensions (D-B-01..D-B-03)
- `backend/app/notifications/router.py` — existing `/notifications?limit=N` shape confirmed adequate (D-B-05)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets (Phase 9 + earlier)

- `frontend/src/components/ui/button.tsx` — `cta` (gradient), `secondary`, `ghost`, `icon` variants + `asChild` + `loading + loadingText` + `leftIcon`/`rightIcon`. Hero CTAs use `cta`/`secondary` + `leftIcon`.
- `frontend/src/components/ui/dropdown-menu.tsx` — existing primitive (range toggle's segmented control may compose from this or be its own thing — planner's call).
- `frontend/src/components/ui/ToastProvider.tsx` — v1 toast surface still wired; reused for Snooze undo toast.
- `frontend/src/styles/sunset.css` — every token (severity / status / SLA / providers / spacing / motion / gradients) Phase 10 consumes. No new tokens added by Phase 10.
- `frontend/src/lib/auth.tsx` — `useAuth()` with `login`, `logout`, `loginSSO`, refresh-token-bearer pattern; localStorage-based session.
- `recharts ^2.12.0` — already a dep.

### Established Patterns (Phase 9)

- File naming: kebab-case, flat in `components/ui/` (D-29).
- shadcn-style primitives with CVA variants + class-variance-authority + clsx + tailwind-merge (D-19, D-20).
- Vitest + Testing Library + axe-core per primitive (D-30).
- `/dev/primitives` is the living state matrix gated by NODE_ENV (D-31).
- `(authed)/layout.tsx` + AppShell hosts the persistent chrome (D-33, D-36, D-37).
- Theme via `data-theme` on `<html>` (D-02); FOUC bootstrap script (D-13).
- Reduce-motion honored globally + per-primitive (D-12).
- Skip-link from topbar to `<main>` (Phase 9 shell).
- Sidebar nav active state via `usePathname()` exact / prefix matching (D-35).
- Auth route guard via middleware redirecting to `/login?next=…` (Phase 9 + middleware location fix).

### Integration Points

- `(authed)/layout.tsx` — new `QueryClientProvider` wrapper around AppShell.
- `useAuth().logout()` — add `queryClient.clear()` call.
- AppShell sidebar — wire `useStats()` for nav chips.
- `/dev/primitives/page.tsx` — append six new primitive state-matrix entries.
- `dashboard/page.tsx` — full rewrite (v1 file becomes the Phase 10 page).
- Backend `vulnerabilities/router.py` + `trends.py` + `stats.py` — Wave 0 endpoint extensions.

### Creative Options Enabled by Existing Architecture

- Recharts already in deps + sunset tokens already defined → TrendChart can theme purely via CSS-variable consumption.
- TanStack Query's per-`useQuery` retry overrides → D-D-07 differentiated retry policy is one line per hook.
- Existing skip-link + landmark setup from Phase 9 → Phase 10's per-section landmarks compose cleanly.

</code_context>

<specifics>
## Specific Ideas

- **Copy-voice exemplars to reuse verbatim:** `3 critical CVEs need your eyes` (headline pattern), `Top one is on prod-db-01 — Postgres path, CVSS 9.8, exploited in the wild.` (sub-line shape), `Nothing critical right now` (quiet-win), `Snoozed CVE-2024-… for 1h · [Undo]` (success toast shape), `Tenable connector is unreachable` (error pattern: name what failed).
- **Sketch 002 is the visual North Star** — every block in Phase 10 should render side-by-side faithful to `sources/002-dashboard-sunset/index.html`. Visual fidelity check in verification.
- **Mobile rail stacking + `Recent activity` heading** — explicit because mobile drops the right-side spatial context that "this is activity" carries on desktop.
- **Activity icon variants by category, not by severity** — pink for critical-vuln events, amber for SLA breach, violet for system, success for risk-down. The variant matches the *event kind*, not the vuln severity inside the event.

</specifics>

<deferred>
## Deferred Ideas

### Surfaced during discussion but out of Phase 10 scope

- **BroadcastChannel for instant cross-tab sync** — Phase 10 relies on refetch-on-focus (≤30s lag for activity, ≤60s for stats). BroadcastChannel could ship later if cross-tab UX feedback warrants.
- **Optimistic update on Snooze** — Phase 10 invalidates + refetches. Optimistic mutation would be a future UX upgrade.
- **Per-user dashboard preferences** — range toggle persistence beyond URL (localStorage / per-user). Future feature.
- **CI bundle-size gating** — depends on PROD-02 (CI gating phase). Phase 10 captures the number in the verification log; no automated gate.
- **Storybook playground** — explicit out-of-scope per REQUIREMENTS-v2.md (`/dev/primitives` is the substitute).
- **Print stylesheet** — no clear customer ask. Reports surface (EXP-01) already covers PDF/CSV.
- **Telemetry / product-analytics events** — needs its own scoping decision (which provider, privacy review for self-hosted deploys).
- **Tenant-configured time zone** — currently browser-local. Would need a tenant TZ setting + a UI to configure. Future.
- **Real-time push (websocket / SSE)** — PROJECT.md `Out of Scope`.
- **Light-theme polish for the new primitives** — UX-D-03 / D-06 scope. Phase 10 ships dark-only visuals; light architecture stays wired but disabled in UserChip.
- **Top-5 inline expansion in the card** — conflicts with Phase 11's drill-panel architecture; routes to `/vulnerabilities?cve=…&open=drill` instead.
- **Keyboard shortcut layer (G to triage, S to snooze, ⌘K palette)** — future phase decides.
- **Mobile-replacement nav (hamburger / bottom-nav / drawer)** — Phase 15 scope (Phase 9 UAT gap).

### Reviewed Todos (not folded)

None — no pending todos relevant to /dashboard surfaced from intake.

</deferred>

---

*Phase: 10-dashboard*
*Context gathered: 2026-05-15*
