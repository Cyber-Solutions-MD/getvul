# Phase 10: `/dashboard` — Research

**Researched:** 2026-05-15
**Domain:** TanStack Query v5 data layer + recharts chart rendering inside Next.js 15 App Router; FastAPI + async SQLAlchemy 2.0 endpoint extensions for an analytics-shaped dashboard.
**Confidence:** HIGH across the board. Backend code, frontend code, sketch contract, and CONTEXT.md decisions were all read directly; library claims were verified via official docs.

## Summary

Phase 10 rewrites `/dashboard` from its v1 tab-based layout to the action-first sketch-002 layout: a hero answering "what to do now?", a 4-tile stat strip with day-over-day deltas, a 30-day severity-stacked trend chart with 7d/30d/90d range toggle, a Top-5 to triage card, and a 340 px right-rail activity feed. It introduces the shared TanStack Query v5 data layer that Phases 11-14 will reuse, six new presentation primitives (Card, Stat, StatStrip, ActivityFeed, TrendChart, ErrorBoundary), and five concrete backend extensions on existing endpoints. CONTEXT.md locks 43 design decisions across 13 categories — research does not propose alternatives to those decisions.

**The phase has a much smaller backend scope than it looks at first glance.** The hardest piece on paper — the `DailySnapshot` table and the nightly capture job needed for `delta_7d` (D-S-01) — **already exists** in the codebase. `backend/app/vulnerabilities/trends.py` defines the `DailySnapshot` SQLAlchemy model, migration `021_daily_snapshots` already shipped, and `capture_all_snapshots()` is already wired into the in-process scheduler loop in `connectors/scheduler.py`. The trends endpoint `/api/v1/vulnerabilities/trends` already returns per-day severity counts via a `by_severity` field on each timeline entry — D-B-01 is a re-shape from `[{date, new, resolved, by_severity}]` into the sketch's flatter `[{date, critical, high, medium, low}]`, not a new SQL query. The remaining backend work is genuinely small: a `?sort=triage` flag, an additive `dashboard_tiles` block on `/stats`, a `top_vuln` field, three nav counts, an `onboarding_state` flag, and one new `POST /vulnerabilities/{id}/snooze` endpoint (which does NOT exist today — confirmed by grep over the routers).

**Frontend scope is the lion's share.** The new primitives are six files in `components/ui/`. The page rewrite is one file. The data layer is ~10 hooks and a query-key factory. The visual contract is sketch-002 variant B — already validated, locked, normative.

**Primary recommendation:** Three waves. Wave 0 (parallel): install `@tanstack/react-query`, scaffold the six primitive files + tests, add the four backend endpoint extensions + the new `POST /snooze` route. Wave 1: build out primitives + hooks + page composition against locked backend. Wave 2: a11y verification, bundle measurement, validation gate.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

CONTEXT.md uses category-prefixed decision IDs (D-D-*, D-C-*, D-H-*, etc.) rather than the standard `## Decisions` / `## Claude's Discretion` / `## Deferred Ideas` headings. The substance maps directly. Key categories with the full set in `.planning/phases/10-dashboard/10-CONTEXT.md`:

### Locked Decisions

**D-D Data layer (13 items):**
- D-D-01: TanStack Query v5 — v2.0 client data layer for every authed screen. ~13 kB gzipped.
- D-D-02: `QueryClientProvider` mounts inside `(authed)/layout.tsx` next to AppShell. Single shared client. `/login` stays outside the group.
- D-D-03: Query-key convention is domain-first: `['vulnerabilities','stats']`, `['vulnerabilities','trends',{range}]`, `['notifications','recent',{limit}]`.
- D-D-04: Range toggle (`7d`/`30d`/`90d`) URL-synced via `?range=30d`. `useSearchParams` + `router.replace({ scroll: false })`.
- D-D-05: URL is the only source of truth for range. Reload without URL defaults to 30d. No localStorage fallback.
- D-D-06: `staleTime`: 60s for `/stats`, `/overview`, `/trends`; 30s for `/notifications`. Both refetch on window focus + mount.
- D-D-07: Retry: 1× on 5xx for `/stats` + dashboard-tiles; 0 retries elsewhere. No retries on 4xx.
- D-D-08: 401 → silent token refresh via existing `useAuth` path. Refresh failure → `/login?next=/dashboard`.
- D-D-09: Logout clears the entire TanStack cache — `useAuth().logout()` calls `queryClient.clear()`.
- D-D-10: Partial failure — independent `useQuery`s. Failed card shows muted bg + inline `<error code> · [Retry]`; siblings render their own data.
- D-D-11: Loading states inline-minimal in Phase 10 — skeleton hero, skeleton tiles, skeleton chart. Phase 11 canonicalizes.
- D-D-12: Cross-tab sync via refetch-on-focus (≤30s activity, ≤60s stats). No BroadcastChannel.
- D-D-13: Snooze mutation invalidates `['vulnerabilities','stats']`, `['vulnerabilities','dashboard-tiles']`, `['vulnerabilities']`. No optimistic update.

**D-C Chart (10 items):**
- D-C-01: Use existing `recharts ^2.12.0`. No new chart lib.
- D-C-02: Wrap recharts behind `TrendChart` primitive with `<TrendChart data range onRangeChange />`.
- D-C-03: Bundle-split via `dynamic(() => import('@/components/ui/trend-chart'), { ssr: false, loading: () => <ChartSkeleton /> })`.
- D-C-04: Custom tooltip with severity glyphs `■ ▲ ◆ ○` + counts. 3-segment range toggle. Hover nudge = scale 1.04 + slight y-translate. Honors `prefers-reduced-motion`.
- D-C-05: Series colors bind to `var(--color-severity-critical/high/medium/low)`.
- D-C-06: y-axis auto-scales to nearest 10 above peak. 4 evenly-spaced horizontal gridlines in `--color-border-subtle`. Y labels right-aligned, mono.
- D-C-07: Rightmost bar = today (may be partial). Tooltip reads `Today (so far)` for it.
- D-C-08: Browser-local time-zone everywhere (`Intl.DateTimeFormat`). `12m ago` relative format.
- D-C-09: Backend `/trends` extended with `severity_trends: { 'YYYY-MM-DD': { critical, high, medium, low }, … }`.
- D-C-10: ResponsiveContainer; reduce y-axis to 2 gridlines below 640 px. Hover nudge → tap-to-reveal.

**D-H Hero (12 items):** number + "what to do now" headline (D-H-01..04), pulsing dot eyebrow (D-H-05), Start triage CTA → `?status=open&severity=critical` (D-H-06), Snooze 1h secondary calls the per-CVE snooze API (D-H-07), Undo toast (D-H-08), quiet-win swap when critical=0 (D-H-09), side-by-side CTAs that stack <640px (D-H-10), Zap/Clock icon prefixes (D-H-11), hero IS the page header (D-H-12).

**D-S Stats (5 items):** Backend computes `delta_7d` from `DailySnapshot`. SLA-at-risk = within 25% of per-severity deadline. Direction-aware coloring (▲/▼). Each tile gets muted lucide icon top-right.

**D-T Top-5 (5 items):** Ranking = KEV first → CVSS desc → SLA-urgency asc. Reuses `/api/v1/vulnerabilities?sort=triage&limit=5`. Row click → `/dashboard/vulnerabilities?cve=…&open=drill`.

**D-A Activity feed (7 items):** Category-tinted icons (pink/amber/violet/success). Lucide icons: ShieldAlert/Clock/WifiOff/TrendingUp-Down. `?limit=5`. Routes link out to vuln/ticket/connector/asset. Rail 340 px sticky; stacks below at <1280 px.

**D-N Sidebar nav-chip counts:** Three chips wired (Vulnerabilities open, Assets total, Tickets open). Single shared `useStats()` call. `—` placeholder during load; on error leave dash.

**D-O Onboarding states:** `/stats` returns `onboarding_state: 'no_scanners'|'no_data_yet'|'ready'`. Replaces dashboard when not ready.

**D-Tab Tab title:** Dynamic `<title>` — `(N) Dashboard · GetVul` when critical>0, else `Dashboard · GetVul`. Via `useDocumentTitle` hook writing to `document.title`.

**D-Ax Accessibility (7 items):** sr-only h1 + h2 per section, `<section aria-labelledby>` + `<aside>` landmarks, visually-hidden `<table>` companion for chart, reduce-motion handling, no programmatic focus on load, forced-colors `@media (forced-colors: active)` block in `globals.css`, dark-only visuals.

**D-M Mobile breakpoints:** Activity rail stacks below at <1280 px. Stat strip 4 → 2 → 1 cols. Sidebar already hides ≤999 px (Phase 9 D-41).

**D-Perf Performance (3 items):** First-Load JS budget for `/dashboard` = **180 kB**. Soft Vitals (LCP <2.5s, INP <200ms). Bundle visibility in `10-VERIFICATION.md`; no CI gate yet (PROD-02 territory).

**D-R Render (2 items):** `'use client'` page (D-R-01). Skeleton priority — hero/strip/chart container render at mount, paint as queries resolve (D-R-02).

**D-E Error handling (4 items):** Per-section `<ErrorBoundary>`. Inline error block per failed section. Hero failure stays inline. Toasts only for user-initiated events (Snooze success/failure).

**D-Test (4 items):** Per-primitive `.test.tsx` with axe assertions. Page-level `dashboard.test.tsx` mocks the 4 queries + asserts the partial-failure path. Backend pytest per endpoint extension. `/dev/primitives` extended with the 6 new primitives.

**D-P Primitive API (6 items):** Card variant API; Stat with label/value/delta/deltaIsGood/hint/icon; StatStrip wraps 1–6 children in responsive grid; ActivityFeed with items+emptyCopy; TrendChart with data+range+onRangeChange; ErrorBoundary with fallback render-prop.

**D-B Backend changes (6 items):** Trends extended with `severity_trends` (D-B-01); `/stats` extended with `dashboard_tiles` + `top_vuln` + nav counts + `onboarding_state` (D-B-02); `/vulnerabilities` adds `?sort=triage&limit=N` (D-B-03); confirm `POST /vulnerabilities/{id}/snooze` exists (D-B-04 — it does NOT, see `## Open Questions`); `/notifications?limit=5` is already correctly shaped (D-B-05); backend lands in Wave 0 before frontend Wave 1+ (D-B-06).

**D-RT Real-time:** No websocket/SSE/push. Polling only.

**D-Tel Telemetry:** Skip entirely in Phase 10.

**D-K Keyboard shortcuts:** None new. `⌘K` stays visual-only.

### Claude's Discretion

- Exact spacing rhythm between hero/strip/chart/top-5 — consume `--space-*` tokens.
- Specific gradient stops for hero CTA hover state — consume `--gradient-sunset`.
- Skeleton shape details — within `--motion-*` + `--radius-*` tokens.
- Stat tile internal layout (label-on-top vs label-on-side) — planner picks per visual-language.md.
- Pulse-urgency keyframe specifics — defined in `globals.css` per Phase 9 D-15.

### Deferred Ideas (OUT OF SCOPE)

- BroadcastChannel cross-tab sync
- Optimistic update on Snooze (invalidate + refetch only)
- Per-user dashboard preferences beyond URL range toggle
- CI bundle-size gating (PROD-02)
- Storybook playground
- Print stylesheet
- Telemetry / product analytics
- Tenant-configured time zone
- Real-time push (websocket / SSE)
- Light-theme polish (architecture remains wired; UserChip Light radio disabled since Phase 9)
- Top-5 inline expansion (routes to drill panel instead)
- Keyboard shortcut layer (G-to-triage, S-to-snooze, ⌘K)
- Mobile-replacement nav

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description (verbatim ROADMAP success criteria) | Research Support |
|----|------------------------------------------------|------------------|
| UX-02-01 | Action-first hero — pulsing-dot eyebrow + numeric headline + mono host references + Start triage gradient CTA + Snooze 1h secondary | Sketch 002 var B + D-H-01..12 + Pattern 4 (page composition) + new `POST /snooze` route. |
| UX-02-02 | 4-tile stat strip (Critical · open / SLA · at risk / CISA KEV / MTTR · 30d) with deltas (`▲ +3 from yesterday`) | D-S-01..05 + StatStrip primitive + extended `/stats.dashboard_tiles` shape — backed by EXISTING `DailySnapshot` table. |
| UX-02-03 | 30-day severity-stacked trend chart with hover nudge + range toggle (7d/30d/90d); route-split, not in shared bundle | D-C-01..10 + recharts `^2.12.0` (already in deps) + `next/dynamic({ssr:false})` + RESHAPE existing trends endpoint to add `severity_trends` (D-B-01). |
| UX-02-04 | Top-5 to triage card with severity-glyph rows + SLA pills; row click → CVE drill view (stub OK until Phase 11) | D-T-01..05 + add `?sort=triage&limit=N` to existing `/vulnerabilities` list endpoint (D-B-03). |
| UX-02-05 | Activity feed in 340 px right sidebar with sunset-tinted icon variants + last 5 events from `/api/v1/notifications` | D-A-01..07 + ActivityFeed primitive — existing `/api/v1/notifications?limit=5` is already correctly shaped (D-B-05 — no backend change needed). |
| UX-02-06 | Quiet-win empty state when open-critical=0 ("Nothing critical right now"). Plus the 6 new primitives (Card, Stat, StatStrip, ActivityFeed, TrendChart, ErrorBoundary) are reusable and documented in `frontend/src/components/ui/` | D-H-09 quiet-win + state-patterns.md + D-O-01..04 onboarding states + D-P-01..06 primitive APIs + D-Test-04 `/dev/primitives` extension. |

The planner MUST map each plan-task to one or more REQ IDs in the Acceptance section of every PLAN.md.
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Fonts locked:** Inter + JetBrains Mono. Never substitute.
- **No hex literals in TSX:** consume CSS variables from `frontend/src/styles/sunset.css` (loaded in Phase 9 via `globals.css` `@import`).
- **State patterns mandatory:** every screen must ship empty, loading, error states — CLAUDE.md calls this out as the v1 audit's top pain point.
- **No Tailwind admin-template patterns.**
- **Copy voice:** sentence case, no "Welcome!"/"Please…"/"Click here" — `sketch-findings-getvul/references/copy-voice.md` is normative.
- **Sketch findings auto-load:** the `sketch-findings-getvul` skill at `/Users/chemencedji/Desktop/getvul/.claude/skills/sketch-findings-getvul/` is the visual contract. Sketch 002 variant B is the north star. References win over plausible alternatives.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| QueryClient provider (cross-page singleton) | Frontend client layout (`(authed)/layout.tsx`) | — | All authed pages share one client; lives at the segment boundary. Phase 9 already made `(authed)/layout.tsx` a client component via `ToastProvider`, so no new client-boundary cost. |
| Per-query cache + retries + invalidation | Browser (TanStack Query runtime) | — | Cache lives in memory, scoped to a single browser session. |
| Per-day severity counts | API / Backend | Database (SQL date bucketing) | `get_vuln_trends` already does this — D-B-01 is a re-shape of the existing `by_severity` per-day field, not new SQL. |
| Stats with `delta_7d` | API / Backend | DailySnapshot table (ALREADY EXISTS) | Delta requires yesterday's count; `DailySnapshot` already captures it nightly via the in-process scheduler loop (`connectors/scheduler.py:167-177`). |
| Top-5 triage ordering | API / Backend | Database | Composite `ORDER BY cisa_kev DESC, cvss_v3_score DESC, sla_due_at ASC` — added as a `?sort=triage` flag to `list_vulnerabilities`. |
| Snooze mutation | API / Backend | Browser (no optimistic update — D-D-13) | Authoritative state on the server. **New endpoint** — does not exist today. |
| Notification feed | API / Backend | — | Existing `/api/v1/notifications` returns paginated notifications with the exact category set D-A-01 specifies. |
| Nav-chip counts (vuln open, assets total, tickets open) | API / Backend | — | Add three int fields to `/stats` response — single round-trip per D-N-02. |
| Onboarding state detection | API / Backend | — | Requires checking enabled connectors + last successful sync. Backend has both signals via `ConnectorConfig` (`backend/app/ticketing/models.py`). |
| URL `?range=` sync | Browser (Next.js router) | — | Pure UI state in URL for shareability + back-button. |
| Document title `useDocumentTitle` | Browser (client effect) | — | Updates on every triage refetch — too dynamic for the static metadata API; metadata API does not support reactive titles in client components anyway. |
| Sketch-fidelity rendering | Browser (CSS + primitives) | — | All visual tokens are CSS-variable-driven; no SSR-specific styling. |
| Chart accessibility table | Browser (DOM, sr-only) | — | Companion `<table class="sr-only">` rendered alongside the SVG chart. |

**Why this matters:** the page is fully client-rendered (D-R-01). Phase 9's `(authed)/layout.tsx` already uses `'use client'` directives indirectly via `ToastProvider`, so adding `QueryClientProvider` does not move any tier boundary. There is no SSR / RSC consideration in this phase.

## Standard Stack

### Core (already in `frontend/package.json`)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| next | ^15.5.13 | App Router, route splitting, navigation | Locked. Verified in `frontend/package.json:19`. |
| react / react-dom | ^19.0.0 | Rendering | Locked. Verified. |
| typescript | ^5.5.0 | Type safety | Locked. Verified. |
| tailwindcss | ^3.4.0 | Utility CSS over sunset.css variables | Locked. Verified. |
| recharts | ^2.12.0 | The chart library | **Confirmed installed** (`package.json:23`). v2.12+ supports `accessibilityLayer` (added v2.10), `isAnimationActive='auto'` honoring `prefers-reduced-motion`, and CSS variable strings on `fill`. [VERIFIED: package.json + recharts docs] |
| lucide-react | ^0.383.0 | Iconography | Locked. Tree-shakes via named imports only. Confirmed in `package.json:18`. |
| @radix-ui/react-slot | ^1.2.4 | Polymorphism (Button `asChild`) | Already a Phase 9 dep. |
| @radix-ui/react-dropdown-menu | ^2.1.16 | Dropdown primitive | Already a Phase 9 dep. |
| class-variance-authority | ^0.7.1 (devDep) | Variant API | Phase 9 baseline. |
| clsx + tailwind-merge | ^2.1.1 / ^2.6.1 | `cn()` utility | Phase 9 baseline. |
| tailwindcss-animate | ^1.0.7 | DropdownMenu transitions | Phase 9 baseline. |

### To install in this phase

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `@tanstack/react-query` | `^5.x` (latest stable as of 2026-05) | Data layer | Locked by D-D-01. **NOT in `frontend/package.json` today** — confirmed by inspection. Wave 0 task: `cd frontend && npm install @tanstack/react-query@^5`. [VERIFIED: package.json read] |
| `@tanstack/react-query-devtools` | matching `^5.x` (devDep) | Dev-only inspector (optional but standard) | Recommended dev-only so production bundle stays clean. |

### Supporting (already in tree — call out)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `vitest` | ^4.1.6 | Test runner | Phase 9 baseline. |
| `vitest-axe` | ^0.1.0 | a11y matcher | **Confirmed used** in `frontend/vitest.setup.ts:2-7` — `import 'vitest-axe/extend-expect'` + `expect.extend(axeMatchers)`. Do NOT install jest-axe; use the existing vitest-axe wiring. [VERIFIED: vitest.setup.ts] |
| `@testing-library/react` + `jest-dom` | ^16.3.2 / ^6.9.1 | DOM testing | Phase 9 baseline. |

### Alternatives Considered (NOT chosen — locked by CONTEXT.md)

| Instead of | Could Use | Why we DON'T |
|------------|-----------|--------------|
| TanStack Query | SWR, Apollo, RTK Query, raw fetch | Locked D-D-01. Don't research alternatives. |
| recharts | victory, visx, nivo, chart.js | Already in deps. Locked D-C-01. |
| `next/dynamic` for recharts | Static import | Locked D-C-03 — must route-split to meet 180 kB target. |
| SSR / streaming the page | `'use client'` whole-page | Locked D-R-01. |
| jest-axe | vitest-axe | **vitest-axe is already wired** in vitest.setup.ts. Don't switch. |

### Installation

```bash
cd frontend
npm install @tanstack/react-query@^5
npm install --save-dev @tanstack/react-query-devtools
```

### Version verification (Wave 0 task)

Before locking the Standard Stack table into PLAN files, run:

```bash
cd frontend
npm view @tanstack/react-query version
npm view @tanstack/react-query-devtools version
npm view recharts version  # confirm ^2.12 is still current; bump if needed
```

Training data is stale on minor versions. Always confirm against registry. Record the exact installed version in `10-VERIFICATION.md` (D-Perf-03 captures the build output anyway — bump the version row in that file).

## Architecture Patterns

### System Architecture Diagram

```
                 ┌─────────────────────────────────────────────────────────────────┐
                 │                       Browser (client)                         │
                 │                                                                │
   /dashboard ──▶│   /dashboard page  ('use client')                              │
   request       │       │                                                       │
                 │       ├── useSearchParams() → 'range' state (D-D-04)           │
                 │       ├── useDocumentTitle("(N) Dashboard · GetVul") (D-Tab-01)│
                 │       │                                                       │
                 │       ├── 4x useQuery hooks (D-R-03, D-D-10)                   │
                 │       │     ├── useStats()       queryKey: ['vulnerabilities','stats'] │
                 │       │     ├── useTrends(range) queryKey: ['vulnerabilities','trends',{range}] │
                 │       │     ├── useTopTriage()    queryKey: ['vulnerabilities','top-triage',{limit:5}] │
                 │       │     └── useRecentNotifications() queryKey: ['notifications','recent',{limit:5}] │
                 │       │                                                       │
                 │       └── useSnoozeMutation()  invalidates 3 keys (D-D-13)    │
                 │              │                                                │
                 │              ▼                                                │
                 │   QueryClientProvider  ← in (authed)/layout.tsx (D-D-02)      │
                 │   (queryClient persisted with useState lazy init)              │
                 │              │                                                │
                 │              ▼                                                │
                 │   api()  ← shared HTTP wrapper at frontend/src/lib/api.ts     │
                 │     ├── attaches Authorization header (Phase 9 token system)  │
                 │     └── on 401 → tryRefreshToken() → retry once → /login (D-D-08) │
                 │              │                                                │
                 └──────────────┼─────────────────────────────────────────────────┘
                                │
                                ▼  HTTP/JSON
                 ┌──────────────┴─────────────────────────────────────────────────┐
                 │                       API / Backend (FastAPI)                 │
                 │                                                                │
                 │   GET /api/v1/vulnerabilities/trends?days=30                   │
                 │       └─ ADD `severity_trends: {YYYY-MM-DD: {c,h,m,l}, …}`     │
                 │          (re-shape existing `vuln_trends.timeline[].by_severity`)│
                 │                                                          D-B-01│
                 │                                                                │
                 │   GET /api/v1/vulnerabilities/stats                            │
                 │       └─ ADD `dashboard_tiles: {critical_open:{value,delta,delta_direction},│
                 │                                  sla_at_risk:{…}, kev:{…}, mttr_30d:{…}}` │
                 │       └─ ADD `top_vuln: {cve_id, host, path, cvss, on_kev, exploited}`│
                 │       └─ ADD `vuln_open_count`, `asset_total_count`, `ticket_open_count`│
                 │       └─ ADD `onboarding_state: 'no_scanners'|'no_data_yet'|'ready'`│
                 │                                                          D-B-02│
                 │                                                                │
                 │   GET /api/v1/vulnerabilities?sort=triage&limit=5             │
                 │       └─ ADD sort=triage  ORDER BY                             │
                 │              cisa_kev DESC, cvss_v3_score DESC, sla_due_at ASC │
                 │                                                          D-B-03│
                 │                                                                │
                 │   POST /api/v1/vulnerabilities/{id}/snooze {until_ts?}         │
                 │       └─ NEW endpoint — does NOT exist today                   │
                 │                                                          D-B-04│
                 │                                                                │
                 │   GET /api/v1/notifications?limit=5                            │
                 │       └─ NO CHANGE — already returns the right shape     D-B-05│
                 │                                                                │
                 └──────────────┬─────────────────────────────────────────────────┘
                                │
                                ▼
                 ┌──────────────┴─────────────────────────────────────────────────┐
                 │                       Database (Postgres)                     │
                 │                                                                │
                 │   vulnerabilities   ← existing — has cve_id, severity,         │
                 │                       cvss_v3_score, cisa_kev, exploit_available,│
                 │                       sla_due_at, sla_breached, status,         │
                 │                       first_detected_at, remediated_at, …      │
                 │                                                                │
                 │   assets, tickets, notifications, connector_configs            │
                 │                       ← all existing                           │
                 │                                                                │
                 │   daily_snapshots   ← EXISTS (migration 021_daily_snapshots)   │
                 │                       Captured nightly by                      │
                 │                       app.vulnerabilities.trends.capture_all_snapshots│
                 │                       (wired in connectors/scheduler.py:167-177)│
                 │                                                                │
                 │                       Metrics JSONB already includes:          │
                 │                       total_vulns, open_vulns, critical_open,  │
                 │                       high_open, remediated, sla_breached,     │
                 │                       avg_risk_score, total_assets, open_tickets,│
                 │                       compliance_pct                           │
                 │                                                                │
                 └────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure

```
frontend/src/
├── app/
│   └── (authed)/
│       ├── layout.tsx                  # MODIFY: wrap children in QueryClientProvider
│       └── dashboard/
│           ├── page.tsx                # FULL REWRITE: hero / strip / chart / top-5 / activity
│           └── page.test.tsx           # NEW: page-level integration test (D-Test-02)
├── components/
│   ├── dashboard/                      # NEW directory — page-specific composition (not primitives)
│   │   ├── hero.tsx
│   │   ├── stat-strip-wired.tsx        # uses StatStrip primitive + useStats()
│   │   ├── trend-section.tsx           # wraps TrendChart in <section> + skeleton
│   │   ├── top5-card.tsx
│   │   ├── activity-rail.tsx
│   │   ├── onboarding-panel.tsx        # the 'no_scanners' / 'no_data_yet' full-page panels
│   │   └── microcopy.ts                # all dashboard strings, sentence case (D-Copy)
│   └── ui/                             # NEW PRIMITIVES (reusable; no business logic)
│       ├── card.tsx                    # NEW (D-P-01)
│       ├── stat.tsx                    # NEW (D-P-02)
│       ├── stat-strip.tsx              # NEW (D-P-03)
│       ├── activity-feed.tsx           # NEW (D-P-04)
│       ├── trend-chart.tsx             # NEW (D-P-05; dynamic import target)
│       ├── error-boundary.tsx          # NEW (D-P-06; React 19 class boundary)
│       ├── card.test.tsx, stat.test.tsx, stat-strip.test.tsx,
│       ├── activity-feed.test.tsx, trend-chart.test.tsx, error-boundary.test.tsx (all D-Test-01)
├── lib/
│   ├── api.ts                          # KEEP — 401-refresh-retry wrapper already done
│   ├── query-client.ts                 # NEW: makeQueryClient + global defaults
│   ├── queries/                        # NEW (per CONTEXT.md "in scope" section)
│   │   ├── use-stats.ts                # useQuery + queryKey factory
│   │   ├── use-trends.ts
│   │   ├── use-top-triage.ts
│   │   └── use-recent-notifications.ts
│   ├── mutations/                      # NEW
│   │   └── use-snooze.ts               # useMutation + invalidate (D-D-13)
│   └── auth.tsx                        # MODIFY: logout() calls queryClient.clear() (D-D-09)
└── hooks/                              # NEW directory
    ├── use-document-title.ts           # D-Tab-01
    └── use-prefers-reduced-motion.ts   # D-Ax-04, D-C-04 helper

backend/app/
├── vulnerabilities/
│   ├── router.py                       # MODIFY: add ?sort=triage to GET /; add POST /{id}/snooze
│   ├── service.py                      # MODIFY: list_vulnerabilities accepts a triage sort
│   ├── trends.py                       # MODIFY: get_vuln_trends returns severity_trends in new shape
│   ├── dashboard.py                    # MODIFY: add dashboard_tiles + top_vuln + 3 counts + onboarding_state
│   └── schemas.py                      # MODIFY: extend DashboardStats pydantic shape
└── tests/
    ├── test_dashboard_tiles.py         # NEW
    ├── test_severity_trends.py         # NEW
    ├── test_triage_sort.py             # NEW
    ├── test_top_vuln.py                # NEW
    └── test_snooze.py                  # NEW
```

### Pattern 1: QueryClient provider with React 19 singleton

```tsx
// frontend/src/app/(authed)/layout.tsx — MODIFIED from Phase 9
'use client';

import type { ReactNode } from 'react';
import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppShell } from '@/components/shell/app-shell';
import ToastProvider from '@/components/ui/ToastProvider';
import { makeQueryClient } from '@/lib/query-client';

export default function AuthedLayout({ children }: { children: ReactNode }) {
  // Lazy init — survives navigation, recreated only on hard reload.
  // Do NOT use a module-level `const queryClient = new QueryClient()` — it shares
  // across React trees in tests and causes cache leaks. (TanStack docs explicitly
  // call this out as "Pattern 2 (recommended)" for App Router.)
  const [queryClient] = useState(makeQueryClient);

  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <AppShell>{children}</AppShell>
      </ToastProvider>
    </QueryClientProvider>
  );
}
```

```ts
// frontend/src/lib/query-client.ts — NEW
import { QueryClient } from '@tanstack/react-query';

export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60_000,            // D-D-06 base — overridden per query
        retry: 0,                      // D-D-07 default — Stats/Tiles override to 1
        refetchOnWindowFocus: true,
        refetchOnReconnect: true,
      },
      mutations: { retry: 0 },
    },
  });
}
```

**Source:** [VERIFIED: tanstack.com/query/latest/docs/framework/react/guides/advanced-ssr — `useState(() => new QueryClient())` is the documented Next.js App Router pattern]. Because the page is `'use client'` (D-R-01) and no data is prefetched on the server, **no `<HydrationBoundary>` is required**.

### Pattern 2: Query-key factory (D-D-03)

```ts
// frontend/src/lib/queries/keys.ts — NEW
// Domain-first per D-D-03. Centralized so useMutation (D-D-13) can invalidate precisely.

export const queryKeys = {
  vulnerabilities: {
    all: ['vulnerabilities'] as const,
    stats: () => ['vulnerabilities', 'stats'] as const,
    trends: (range: '7d' | '30d' | '90d') =>
      ['vulnerabilities', 'trends', { range }] as const,
    topTriage: (limit = 5) =>
      ['vulnerabilities', 'top-triage', { limit }] as const,
    dashboardTiles: () => ['vulnerabilities', 'dashboard-tiles'] as const,
  },
  notifications: {
    all: ['notifications'] as const,
    recent: (limit = 5) => ['notifications', 'recent', { limit }] as const,
  },
} as const;
```

Invalidation in the Snooze mutation (D-D-13):

```ts
await Promise.all([
  qc.invalidateQueries({ queryKey: queryKeys.vulnerabilities.stats() }),
  qc.invalidateQueries({ queryKey: queryKeys.vulnerabilities.dashboardTiles() }),
  qc.invalidateQueries({ queryKey: queryKeys.vulnerabilities.all }),  // catches trends + top-triage
]);
```

### Pattern 3: Typical `useQuery` call (per-query overrides — D-D-06, D-D-07)

```ts
// frontend/src/lib/queries/use-stats.ts — NEW
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';

export type DashboardStatsResponse = { /* mirror backend pydantic shape */ };

export function useStats() {
  return useQuery({
    queryKey: queryKeys.vulnerabilities.stats(),
    queryFn: ({ signal }) => api<DashboardStatsResponse>('/api/v1/vulnerabilities/stats', { signal }),
    staleTime: 60_000,    // D-D-06: 60s
    retry: 1,             // D-D-07: 1× on 5xx for stats
  });
}
```

```ts
// frontend/src/lib/queries/use-trends.ts — NEW
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';

export function useTrends(range: '7d' | '30d' | '90d' = '30d') {
  const days = range === '7d' ? 7 : range === '90d' ? 90 : 30;
  return useQuery({
    queryKey: queryKeys.vulnerabilities.trends(range),
    queryFn: ({ signal }) => api(`/api/v1/vulnerabilities/trends?days=${days}`, { signal }),
    staleTime: 60_000,
    retry: 0,             // D-D-07: 0 retries elsewhere
    refetchOnWindowFocus: false,  // chart refetch on focus would be jarring
  });
}
```

```ts
// frontend/src/lib/queries/use-recent-notifications.ts — NEW
export function useRecentNotifications() {
  return useQuery({
    queryKey: queryKeys.notifications.recent(5),
    queryFn: ({ signal }) =>
      api('/api/v1/notifications?page=1&page_size=5', { signal }),
    staleTime: 30_000,  // D-D-06: 30s for notifications
    retry: 0,
  });
}
```

### Pattern 4: Snooze mutation with cache invalidation (D-D-13)

```ts
// frontend/src/lib/mutations/use-snooze.ts — NEW
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from '@/lib/queries/keys';

type SnoozeBody = { until?: string };  // ISO ts; omitted => 1h default server-side

export function useSnoozeMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, until }: { id: string; until?: string }) =>
      api(`/api/v1/vulnerabilities/${id}/snooze`, {
        method: 'POST',
        body: JSON.stringify({ until } satisfies SnoozeBody),
      }),
    onSuccess: async () => {
      // D-D-13 verbatim: invalidate 3 keys; refetch happens naturally.
      await Promise.all([
        qc.invalidateQueries({ queryKey: queryKeys.vulnerabilities.stats() }),
        qc.invalidateQueries({ queryKey: queryKeys.vulnerabilities.dashboardTiles() }),
        qc.invalidateQueries({ queryKey: queryKeys.vulnerabilities.all }),
      ]);
    },
  });
}
```

**Source:** [VERIFIED: tanstack.com/query/latest/docs/framework/react/guides/mutations] — `onSuccess` + `invalidateQueries` is the documented pattern. `onSuccess` / `onError` callbacks on `useQuery` were deprecated in v4 and removed in v5; on mutations they remain.

### Pattern 5: 401 handling — REUSE existing `api()` wrapper

Phase 9 already shipped `frontend/src/lib/api.ts` with a complete 401-refresh-retry path (`tryRefreshToken()` → retry once → redirect to `/login`). TanStack Query wraps this wrapper; **no new 401 interceptor is needed**. The existing wrapper:

```ts
// frontend/src/lib/api.ts (existing — DO NOT REWRITE)
// Behavior:
// - Attaches Bearer token from localStorage
// - On 401: tries POST /auth/refresh once with the stored refresh_token
//   - If refresh succeeds: retries original request with new token
//   - If refresh fails: clears tokens, redirects to /login, throws "Session expired"
// - On non-OK: throws Error with backend detail string

export async function api<T = any>(path: string, options?: FetchOptions): Promise<T>
```

The query/mutation patterns above pass `signal` to `api()` so TanStack's `AbortSignal` integration cancels in-flight fetches on unmount or rapid refetch. The existing `api()` ignores `signal` today — **Wave 0 frontend task:** extend `api()` to accept `init.signal` and pass it through to `fetch()`. One-line change.

### Pattern 6: Logout — `queryClient.clear()` (D-D-09)

```ts
// frontend/src/lib/auth.tsx — MODIFIED at line 221-228
import { useQueryClient } from '@tanstack/react-query';

// Inside AuthProvider:
const qc = useQueryClient();

const logout = useCallback(() => {
  fetch(`${API}/auth/logout`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  }).catch(() => {});
  clearAuth();
  qc.clear();           // D-D-09: clear entire cache so next user starts fresh
  router.replace('/login');
}, [token, router, qc]);
```

`clear()` removes all queries from the cache and cancels any in-flight requests. **Difference from `invalidateQueries()`** (marks stale, triggers refetch on next mount) — on logout we want the data *gone*, not refetched. [VERIFIED: tanstack.com/query/latest/docs/reference/QueryClient]

### Pattern 7: URL state sync for the range toggle (D-D-04, D-D-05)

```ts
// frontend/src/hooks/use-url-state.ts — NEW
'use client';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useCallback } from 'react';

export function useUrlState<T extends string>(
  key: string,
  allowed: readonly T[],
  defaultValue: T
): [T, (next: T) => void] {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  const raw = params.get(key);
  const value: T = (allowed as readonly string[]).includes(raw ?? '') ? (raw as T) : defaultValue;
  // ^ Pitfall 7: URL is user-controllable; ALWAYS clamp to an enum.

  const setValue = useCallback((next: T) => {
    const sp = new URLSearchParams(params.toString());
    if (next === defaultValue) sp.delete(key); else sp.set(key, next);
    const qs = sp.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }, [router, pathname, params, key, defaultValue]);

  return [value, setValue];
}
```

Use in page: `const [range, setRange] = useUrlState('range', ['7d','30d','90d'] as const, '30d');`

**Source:** [VERIFIED: nextjs.org/docs/app/api-reference/functions/use-router — `router.replace(href, { scroll: false })` is the Next 15 signature]. `useSearchParams()` returns `ReadonlyURLSearchParams` and must be called inside a client component. Because `/dashboard` is `'use client'` (never statically rendered), no `<Suspense>` boundary is required for `useSearchParams`.

### Pattern 8: `useDocumentTitle` (D-Tab-01)

The Next.js 15 metadata API does NOT support reactive dynamic titles from client components — `generateMetadata` is server-only and runs at request time, not on cache updates. React 19's `<title>` element technique would work but creates re-render churn vs. `useEffect`. The simplest correct implementation:

```ts
// frontend/src/hooks/use-document-title.ts — NEW
'use client';
import { useEffect } from 'react';

export function useDocumentTitle(title: string) {
  useEffect(() => {
    const previous = document.title;
    document.title = title;
    return () => { document.title = previous; };
  }, [title]);
}
```

Usage in `/dashboard/page.tsx`:

```ts
const { data: stats } = useStats();
const critical = stats?.dashboard_tiles?.critical_open?.value ?? 0;
useDocumentTitle(
  critical > 0 ? `(${critical}) Dashboard · GetVul` : 'Dashboard · GetVul'
);
```

### Pattern 9: TrendChart with dynamic import (D-R-05, D-C-03)

```tsx
// frontend/src/components/dashboard/trend-section.tsx — NEW
'use client';
import dynamic from 'next/dynamic';
import { TrendChartSkeleton } from './trend-chart-skeleton';
import type { TrendChartProps } from '@/components/ui/trend-chart';
// ^ type-only import — does NOT pull recharts into this chunk.

const TrendChart = dynamic<TrendChartProps>(
  () => import('@/components/ui/trend-chart').then((m) => m.TrendChart),
  { ssr: false, loading: () => <TrendChartSkeleton /> }
);

export function TrendSection(props: TrendChartProps) {
  return <TrendChart {...props} />;
}
```

**Why this works:** Next.js 15 emits a separate chunk for any module reached only through `dynamic()`. With `{ ssr: false }` recharts is never included in the server-rendered HTML or the route's main JS chunk. Since `TrendChart` is the only place that imports `recharts`, the entire recharts tree (≈ 80 kB minified) route-splits out of the `/dashboard` initial bundle. [CITED: nextjs.org/docs/app/api-reference/functions/dynamic]

**Important:** The Next 15 App Router doesn't allow `dynamic(…, { ssr: false })` in a Server Component — it's a known constraint. We sidestep it because the consuming page is `'use client'` (D-R-01). Wave 0 task: confirm `trend-section.tsx` carries the `'use client'` directive so any future Server Component refactor doesn't break it.

### Pattern 10: Stacked BarChart with CSS-variable fills (D-C-01..10)

```tsx
// frontend/src/components/ui/trend-chart.tsx — NEW
'use client';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';

export type TrendDatum = { date: string; critical: number; high: number; medium: number; low: number };
export type TrendChartProps = {
  data: TrendDatum[];
  range: '7d' | '30d' | '90d';
  onRangeChange: (next: '7d' | '30d' | '90d') => void;
};

// recharts forwards `fill` straight to the SVG <rect>. `var(--…)` strings work
// in v2.10+. [VERIFIED: recharts source + community confirmations in v2.12]
const SEVERITY_FILLS = {
  critical: 'var(--color-severity-critical)',
  high:     'var(--color-severity-high)',
  medium:   'var(--color-severity-medium)',
  low:      'var(--color-severity-low)',
} as const;

export function TrendChart({ data, range, onRangeChange }: TrendChartProps) {
  return (
    <div className="space-y-3">
      <RangeToggle value={range} onChange={onRangeChange} />
      <ResponsiveContainer width="100%" height={200}>
        <BarChart
          data={data}
          margin={{ top: 8, right: 8, left: 0, bottom: 8 }}
          accessibilityLayer  // recharts v2.10+ keyboard navigation, ARIA labels
        >
          <CartesianGrid strokeDasharray="2 4" vertical={false} stroke="var(--color-border-subtle)" />
          <XAxis dataKey="date" tickFormatter={fmtTick} stroke="var(--color-text-muted)" />
          <YAxis stroke="var(--color-text-muted)" />
          <Tooltip content={<SeverityTooltip />} cursor={{ fill: 'var(--color-surface-2)' }} />
          {/* Same stackId stacks the four bars. Order = paint order = stack order */}
          <Bar dataKey="low"      stackId="s" fill={SEVERITY_FILLS.low}      isAnimationActive="auto" />
          <Bar dataKey="medium"   stackId="s" fill={SEVERITY_FILLS.medium}   isAnimationActive="auto" />
          <Bar dataKey="high"     stackId="s" fill={SEVERITY_FILLS.high}     isAnimationActive="auto" />
          <Bar dataKey="critical" stackId="s" fill={SEVERITY_FILLS.critical} isAnimationActive="auto" />
        </BarChart>
      </ResponsiveContainer>
      <ChartDataTable data={data} />  {/* visually-hidden table — Pattern 11 */}
    </div>
  );
}
```

**Source:** [CITED: recharts.org/en-US/api/BarChart]. Same `stackId` on multiple `<Bar>` elements stacks them. `isAnimationActive="auto"` is critical — when set to `'auto'`, recharts respects `prefers-reduced-motion` natively and disables animations during SSR (which we don't have, but it's good hygiene). [VERIFIED: studyraid.com/recharts-animations + recharts source]

**Custom tooltip (D-C-04 — severity glyphs + "Today (so far)" for rightmost):**

```tsx
function SeverityTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const total = payload.reduce((sum: number, p: any) => sum + p.value, 0);
  const isToday = isLatestDay(label);
  return (
    <div role="tooltip" className="rounded-md border border-border bg-surface px-3 py-2 shadow-card">
      <p className="text-xs text-text-muted">{isToday ? 'Today (so far)' : fmtFullDate(label)}</p>
      <p className="font-mono text-sm">{total} open</p>
      <ul className="mt-1 space-y-0.5 text-xs font-mono">
        <li><span className="text-severity-critical" aria-hidden>■</span> Critical: {payload.find((p: any) => p.dataKey === 'critical')?.value ?? 0}</li>
        <li><span className="text-severity-high" aria-hidden>▲</span> High: {payload.find((p: any) => p.dataKey === 'high')?.value ?? 0}</li>
        <li><span className="text-severity-medium" aria-hidden>◆</span> Medium: {payload.find((p: any) => p.dataKey === 'medium')?.value ?? 0}</li>
        <li><span className="text-severity-low" aria-hidden>○</span> Low: {payload.find((p: any) => p.dataKey === 'low')?.value ?? 0}</li>
      </ul>
    </div>
  );
}
```

**Glyphs from `visual-language.md`:** `■` Critical, `▲` High, `◆` Medium, `○` Low (always paired with color — no color-only encoding for color-blindness/forced-colors compliance).

**4 gridlines (2 below 640 px) — D-C-10:** Compute explicit Y-axis ticks from the max value. Pass `ticks={[0, p25, p50, p75, max]}` (5 ticks = 4 lines) for desktop, `ticks={[0, p50, max]}` (3 ticks = 2 lines) for mobile. Use a `usePrefersReducedMotion`-style `useMatchMedia('(max-width:640px)')` hook for the breakpoint — both work; planner picks.

**Hover nudge (D-C-04):** Recharts has no built-in per-bar hover state, but `<Bar onMouseEnter={...} onMouseLeave={...} />` can drive local state for `transform: translateY(-2px)` via inline style on a wrapping `<g>`. **With reduce-motion, set the nudge to `translateY(0)`** — i.e. do nothing.

### Pattern 11: Visually-hidden table companion (D-Ax-03)

Recharts' `accessibilityLayer` (v2.10+) adds keyboard nav to the bars, but it does NOT render a screen-reader-friendly tabular structure. The standard companion-table pattern works in all current recharts versions:

```tsx
// Rendered alongside the chart, visually hidden but in the DOM
function ChartDataTable({ data }: { data: TrendDatum[] }) {
  return (
    <table className="sr-only" aria-label="30-day vulnerability trend by severity">
      <caption>Daily counts of open vulnerabilities by severity, last 30 days</caption>
      <thead>
        <tr>
          <th scope="col">Date</th>
          <th scope="col">Critical</th>
          <th scope="col">High</th>
          <th scope="col">Medium</th>
          <th scope="col">Low</th>
          <th scope="col">Total</th>
        </tr>
      </thead>
      <tbody>
        {data.map((d) => (
          <tr key={d.date}>
            <th scope="row">{fmtFullDate(d.date)}</th>
            <td>{d.critical}</td><td>{d.high}</td><td>{d.medium}</td><td>{d.low}</td>
            <td>{d.critical + d.high + d.medium + d.low}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

`sr-only` is Tailwind's built-in utility for visually-hidden-but-screen-reader-readable. This pattern survives both reduce-motion and forced-colors mode (plain HTML — no color dependence). The chart's SVG can be marked `aria-hidden="true"` once the companion table is in the DOM, so screen readers only consume the table.

### Pattern 12: ErrorBoundary primitive (D-P-06, D-E-01)

React 19 still ships error boundaries as class components; no hooks-based alternative exists.

```tsx
// frontend/src/components/ui/error-boundary.tsx — NEW
'use client';
import { Component, type ReactNode } from 'react';

type Props = {
  children: ReactNode;
  fallback: (err: Error, reset: () => void) => ReactNode;
};
type State = { error: Error | null };

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  componentDidCatch(error: Error, info: unknown) {
    if (process.env.NODE_ENV !== 'production') console.error('[ErrorBoundary]', error, info);
  }
  reset = () => this.setState({ error: null });
  render() {
    if (this.state.error) return this.props.fallback(this.state.error, this.reset);
    return this.props.children;
  }
}
```

Wrap each major dashboard section in its own boundary so a failure in (say) the trend chart doesn't blank out the Top-5 list.

### Pattern 13: Stat tile with animated number + delta (D-P-02, D-S-03..04)

```tsx
// frontend/src/components/ui/stat.tsx — NEW
'use client';
import type { ReactNode } from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';

export type StatProps = {
  label: string;
  value: number | string;
  delta?: number;
  /** When the delta direction is "good for the user" — e.g., decreasing critical counts is good. */
  deltaIsGood?: 'up' | 'down';
  hint?: string;
  icon?: ReactNode;
};

export function Stat({ label, value, delta, deltaIsGood = 'down', hint, icon }: StatProps) {
  const direction = delta == null ? null : delta > 0 ? 'up' : delta < 0 ? 'down' : 'flat';
  const isGood = direction === deltaIsGood;
  const Arrow = direction === 'up' ? TrendingUp : TrendingDown;
  return (
    <div className="relative rounded-lg border border-border-subtle bg-surface p-5">
      {icon && (
        <div className="absolute right-3 top-3 grid h-6 w-6 place-items-center rounded-md text-text-muted">
          {icon}
        </div>
      )}
      <div className="mb-2 text-xs uppercase tracking-wide text-text-muted">{label}</div>
      <div className="font-mono text-4xl font-bold leading-none tabular-nums">{value}</div>
      {delta != null && direction !== 'flat' && (
        <div className={`mt-2 inline-flex items-center gap-1 font-mono text-xs
          ${isGood ? 'text-success' : 'text-danger'}`}>
          <Arrow className="h-3 w-3" aria-hidden />
          {delta > 0 ? '+' : ''}{delta} from yesterday
        </div>
      )}
      {hint && !delta && <div className="mt-2 text-xs text-text-faint">{hint}</div>}
    </div>
  );
}
```

### Anti-Patterns to Avoid

- **`new QueryClient()` at module top level** — shared across React trees and tests; causes cache leaks. Use `useState(() => makeQueryClient())` inside the provider component.
- **`import * as Icons from 'lucide-react'`** — defeats tree-shaking; pulls all ~1,500 icons. Always named imports. Phase 9 already follows this.
- **Recharts statically imported in the page** — pulls ~80 kB into the shared `/dashboard` chunk. Use `next/dynamic({ ssr: false })`.
- **Stacking via separate `<Bar>` series with different `stackId`** — they will NOT stack. Same `stackId` on all four severity bars.
- **Per-`useQuery` `onError` for 401 handling** — `onError` on `useQuery` was REMOVED in v5. Use the global `QueryCache({ onError: … })` if you need a global handler, but the existing `api()` wrapper already handles 401 — no global QueryCache handler needed.
- **`refetchOnWindowFocus: true` on the trend chart** — jarring redraws when alt-tabbing. Override to false (per Pattern 3 above).
- **Hex literals in TSX** — violates CLAUDE.md. Use `var(--token)` or Tailwind utilities mapped to tokens in `tailwind.config.ts`.
- **Generic SaaS copy** — see `copy-voice.md`; sentence case, no "Welcome", no "Please", no exclamation marks. Hero headline is "3 critical CVEs need your eyes" — verbatim from sketch.
- **Animations ignoring `prefers-reduced-motion`** — use `isAnimationActive='auto'` on every `<Bar>` (recharts respects the media query natively when set to 'auto'). [VERIFIED: studyraid.com/recharts-animations]
- **Reading `useSearchParams()` outside a Suspense boundary in a statically-rendered page** — fine here because `'use client'` page is never statically rendered; the warning would only appear if the page were promoted to a Server Component (which it isn't per D-R-01).
- **Module-level `let queryClient: QueryClient` browser singleton** — works but breaks Vitest cleanup. The `useState` pattern is sufficient and simpler.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async state machine (loading/data/error/refetch/retry) | A `useEffect` + `useState` data fetcher (what v1 does) | `@tanstack/react-query` v5 (locked) | Race conditions, stale closures, refetch policy, cache invalidation, retry/backoff are all already solved. |
| Chart rendering (axes, ticks, tooltip, stacking) | SVG by hand | recharts (locked) | Already in deps; reimplementing axis-tick logic is multi-day. |
| Modal/menu accessibility | Custom focus trap | `@radix-ui/react-*` (already Phase 9) | Focus management + a11y semantics. |
| Date formatting + relative time | Custom `formatDistance` | `Intl.RelativeTimeFormat` (browser-native) | Native API covers the activity-feed "12m ago" need (D-C-08). No new dep. |
| Query-string update without scroll-to-top | `window.history.replaceState` directly | `router.replace(href, { scroll: false })` from `next/navigation` | Next router keeps cache + history in sync. |
| Document title sync | `<title>` element JSX | `useEffect` writing `document.title` (custom hook) | Next 15 metadata API doesn't reactively update client titles; effect is the standard escape hatch. |
| Forced-colors mode token mapping | Custom CSS variable swap | `@media (forced-colors: active)` block in `globals.css` re-mapping a handful of tokens to `CanvasText` / `Canvas` / `Highlight` system colors | Browser handles the rest. Already partially done in Phase 9 D-Ax-06. |
| Reduce-motion detection | One-shot `window.matchMedia` | `usePrefersReducedMotion` hook with a `MediaQueryList` listener | User can toggle mid-session. |
| Daily snapshot job | New `daily_snapshot` table + scheduler | **NOTHING — already shipped.** `DailySnapshot` (model: `backend/app/vulnerabilities/trends.py:22-31`), migration `021_daily_snapshots`, capture wired in `connectors/scheduler.py:167-177`. | Don't duplicate. Wave 0 backend task is just to verify the metrics JSON has the fields the frontend needs (it does — `critical_open`, `open_vulns`, `total_assets`, `open_tickets`). |
| 401 refresh-retry interceptor | New axios/fetch wrapper | **NOTHING — already shipped.** `frontend/src/lib/api.ts` already does this end-to-end. | Don't reimplement. |
| Pagination for activity feed | Cursor-based pagination | Existing page-based pagination on `/notifications` — `?page=N&page_size=5` is already there | The dashboard only shows 5 items; pagination isn't a Phase 10 need anyway. Phase 14+ if needed. |

**Key insight:** Phase 9 already proved the cost of hand-rolling (UAT surfaced gaps in dropdown borders, password input slot forwarding, light theme — none catastrophic, but expensive to fix later). This phase compounds the risk because there are 6 new primitives. **Every one of them must be a thin wrapper** over CSS variables (Stat, StatStrip, Card), recharts (TrendChart), DOM (ActivityFeed), or React class (ErrorBoundary). No internal data fetching. No internal validation. Pure presentation.

## Runtime State Inventory

**Trigger evaluation:** Phase 10 is not a rename or migration phase. It adds files and extends API responses additively (D-B-06). No database table is added (`daily_snapshot` already exists). No env vars (D-Mig-01). Two categories still warrant a note:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `daily_snapshots` table already populated by existing nightly job (`connectors/scheduler.py:167-177`). The job has been running since migration 021 shipped. **`delta_7d` will work immediately for tenants with ≥7 days of history.** Tenants installed in the last 7 days will see `delta_7d: null` until enough history accrues — frontend renders this as `Δ —` (per state-patterns.md). | None — verified. Document the `null` semantics in the API contract. |
| Live service config | None — no n8n / Datadog / Tailscale tags reference the dashboard. | None — verified. |
| OS-registered state | None — the snapshot job runs in-process as an asyncio task inside the FastAPI process. No cron, no systemd, no APScheduler. | None — verified in `connectors/scheduler.py`. |
| Secrets/env vars | None new (D-Mig-01 forbids). | None. |
| Build artifacts | None — additive only. | None. |

## Common Pitfalls

### Pitfall 1: QueryClient recreated on every render
**What goes wrong:** Cache is reset on every parent re-render; queries refetch constantly; performance is terrible.
**Why it happens:** Developer writes `const queryClient = new QueryClient()` directly in the component body instead of `useState`.
**How to avoid:** Always `const [qc] = useState(() => makeQueryClient())`. The TanStack ESLint plugin (`@tanstack/eslint-plugin-query`) catches this — recommend adding to devDeps.
**Warning signs:** Network tab shows the same request repeating on unrelated state changes; React DevTools shows a new QueryClient instance reference per render.

### Pitfall 2: Recharts SVG fill prop ignores CSS variables
**What goes wrong:** Bars render but appear black/transparent because `var(--…)` strings fail at the SVG layer in older recharts versions.
**Why it happens:** Pre-v2.10 wrapped some fill values in color-parsing logic that didn't pass through `var()` references.
**How to avoid:** Confirmed working in `recharts ^2.12.0` (the version in `package.json`). Add a unit test that renders `<TrendChart>` with sample data and asserts the SVG `<rect>` elements have the expected `fill` attribute.
**Warning signs:** Bars invisible or render with browser-default fill.

### Pitfall 3: `next/dynamic` chunk still bundled if loading is synchronous
**What goes wrong:** Setting `{ ssr: false }` but accidentally importing the chart elsewhere (e.g., a test or storybook stub) negates the route split.
**Why it happens:** The compiler can't split if any other entry imports the module synchronously.
**How to avoid:** Import `@/components/ui/trend-chart` ONLY through `dynamic()`. Use `import type { TrendChartProps }` (type-only) elsewhere. Verify in `next build` output that recharts is NOT in the shared chunks list.
**Warning signs:** `next build` shows `/dashboard` First-Load JS over 180 kB; the chunk list shows recharts in the main bundle.

### Pitfall 4: First-Load JS measurement (D-Perf-03) ambiguity
**What goes wrong:** Verify gate fails because someone read the wrong column.
**How to avoid:** The relevant column is **"First Load JS"** value on the `/dashboard` row — that's the route-specific JS *plus* shared chunks. The "First Load JS shared by all" footer line is the shared baseline. Capture both numbers in `10-VERIFICATION.md`. [VERIFIED: github.com/vercel/next.js/issues/10565 + discussion #19326]
**Warning signs:** Bundle column read disagrees between PRs.

### Pitfall 5: 401 retry loop
**What goes wrong:** Wrapper retries on 401, gets another 401, retries again, infinitely.
**Why it happens:** The `tryRefreshToken()` itself returns 401 (refresh expired) but the wrapper interprets that as "try again".
**How to avoid:** **Already prevented in `api.ts`** — `tryRefreshToken()` returns `boolean`, and the wrapper only retries once (`!token` guard prevents recursion when called from inside an already-token-aware retry). No change needed.
**Warning signs:** Browser network tab shows endless 401s after token expiry.

### Pitfall 6: Forced-colors mode (D-Ax-06) hides severity colors
**What goes wrong:** In Windows High Contrast mode, all `background-color` and `fill` declarations are overridden by the OS. The severity-stacked bars render as a single block of `CanvasText` color.
**How to avoid:** Pair every color cue with a non-color cue (the glyphs `■ ▲ ◆ ○` in tooltip + visually-hidden table). For the chart's SVG itself: in `@media (forced-colors: active)` add `forced-color-adjust: none` on `.recharts-bar-rectangle` ONLY if the chart still doesn't convey rank — but the companion table already covers that case. Don't fight the OS.
**Warning signs:** axe-core in forced-colors emulation reports color-contrast or information-conveyance failures.

### Pitfall 7: `?range=` is user-controlled — clamp to enum
**What goes wrong:** Reflected XSS or rendering crash via `/dashboard?range=<script>alert(1)</script>` if the value is rendered into the DOM unchecked.
**How to avoid:** `useUrlState` clamps to the enum `['7d','30d','90d']` and falls back to `'30d'` (default per D-D-05). Never render the raw string from the URL.
**Warning signs:** Crash on malformed URL; chart fetches with `days=NaN`.

### Pitfall 8: `delta_7d` null on the first 7 days of tenant lifetime
**What goes wrong:** Backend returns `delta_7d: -42` (today's count minus yesterday's count synthesized to zero) on a fresh tenant, which is misleading.
**How to avoid:** Backend returns `delta_7d: null` (or omits the field) when fewer than 7 days of `DailySnapshot` rows exist for the tenant. Frontend renders `null` as `Δ —`. **Existing `DailySnapshot.metrics` JSONB has been captured nightly since migration 021** — most tenants will have data; only fresh installs see `null`. Document this in the OpenAPI schema for `dashboard_tiles`.
**Warning signs:** Stats strip shows huge swings on a fresh install.

### Pitfall 9: `useDocumentTitle` cleanup races with navigation
**What goes wrong:** Navigating away from `/dashboard` to `/cves`, then quickly back, results in stale title.
**How to avoid:** The hook's cleanup function restores the *previous* title. Correct for `/cves`'s mount (which will overwrite anyway). The race is only visible if a page doesn't set a title at all — make sure every authed page calls `useDocumentTitle` eventually (Phase 11+ scope).
**Warning signs:** Browser tab title shows stale data from previous page.

### Pitfall 10: Activity feed link targets that don't exist yet
**What goes wrong:** Per D-A-05, activity rows link to `/dashboard/vulnerabilities?cve=…` and similar routes. Phase 10 ships before those routes honor `?cve=…&open=drill` (Phase 11). Clicks 404 or land on still-v1-styled pages.
**How to avoid:** Per CONTEXT.md `<domain>`, this is expected — routes are `<Link>` stubs until later phases. Document in `10-HUMAN-UAT.md` so reviewers don't flag it as broken.
**Warning signs:** Reviewer reports "links don't work" — actually working as intended.

### Pitfall 11: Existing `useQuery` `onError` removed in v5
**What goes wrong:** Code copied from a v4 example uses `onError` on `useQuery`. v5 ignores it silently.
**How to avoid:** v5 uses `QueryCache({ onError: … })` globally, or per-query error handling via `query.error` in the component. The existing `api()` wrapper handles 401 globally, so we don't need a global onError handler.
**Warning signs:** Errors aren't reported / toasts don't fire.

### Pitfall 12: `dynamic({ ssr: false })` warning when ancestor is a Server Component
**What goes wrong:** Build emits "Dynamic import with `ssr: false` is not supported in Server Components."
**Why it happens:** Some refactor accidentally turns `(authed)/layout.tsx` back into a server component.
**How to avoid:** Keep `(authed)/layout.tsx` with `'use client'` (it already is, via `ToastProvider`'s client semantics). If the warning appears anyway, wrap the `TrendSection` import in a thin client-component wrapper.
**Warning signs:** `next build` emits the warning above.

## Code Examples

(See `## Architecture Patterns` above — all 13 patterns include verified code with cited sources.)

### Backend SQL skeleton — extending `get_vuln_trends` with the new shape (D-B-01, D-C-09)

The existing `get_vuln_trends` in `backend/app/vulnerabilities/trends.py:37-125` already returns:

```python
{
  "period_days": 30,
  "timeline": [
    {
      "date": "2026-04-16",
      "new": 12,
      "resolved": 5,
      "net": 7,
      "by_severity": {"CRITICAL": 2, "HIGH": 3, "MEDIUM": 4, "LOW": 3}  # ← ALREADY HERE
    },
    …
  ],
  "totals": {"new": 380, "resolved": 220}
}
```

**Note: the existing `by_severity` field measures NEW vulns per day (vulns whose `first_detected_at` falls on that date), NOT "open at end of day".** The sketch's intent (D-C-07 "rightmost bar = today, may be partial") aligns with this — bars represent *new vulns detected that day*, partitioned by severity. This matches what the sketch shows.

To satisfy D-C-09's flatter shape, add `severity_trends` as a *re-shape* of `timeline[].by_severity`:

```python
# In get_all_trends (backend/app/vulnerabilities/trends.py:189-199), add:
severity_trends = {
  d["date"]: {
    "critical": d["by_severity"].get("CRITICAL", 0),
    "high":     d["by_severity"].get("HIGH",     0),
    "medium":   d["by_severity"].get("MEDIUM",   0),
    "low":      d["by_severity"].get("LOW",      0),
  }
  for d in vuln_trends["timeline"]
}

return {
  "vuln_trends": vuln_trends,
  "mttr_trend": mttr_trend,
  "risk_trend": risk_trend,
  "severity_trends": severity_trends,   # ← NEW (D-C-09)
}
```

This is purely a re-shape — no new SQL, no new queries.

### Backend — composite triage sort (D-B-03)

Existing `list_vulnerabilities` (`backend/app/vulnerabilities/service.py:61-118`) orders by severity case + `last_seen_at desc`. Add a `?sort=triage` flag that switches the ORDER BY:

```python
# In list_vulnerabilities — change the .order_by(...) when filters.sort == 'triage':
from sqlalchemy import desc, asc, nulls_last
…
if filters.sort == 'triage':
    # D-T-01: KEV first → CVSS desc → SLA-urgency asc (closer to breach = first)
    data_q = data_q.order_by(
        desc(Vulnerability.cisa_kev),
        desc(Vulnerability.cvss_v3_score).nullslast(),
        asc(Vulnerability.sla_due_at).nullslast(),
    )
else:
    # existing severity-case ordering
    …
```

All three columns exist on the `Vulnerability` model (verified in `models.py:44-77`): `cisa_kev` (bool), `cvss_v3_score` (Numeric(3,1)), `sla_due_at` (DateTime).

**Add to `VulnerabilityFilter` schema in `backend/app/vulnerabilities/schemas.py:72-84`:**

```python
class VulnerabilityFilter(BaseModel):
    …
    sort: str | None = Field(None, pattern="^(triage|severity)$")  # default: severity-case (existing)
```

And to the router signature in `router.py:38`: `sort: str | None = Query(None)`.

### Backend — `POST /vulnerabilities/{id}/snooze` (D-B-04)

**This endpoint does NOT exist today** (grep over `vulnerabilities/router.py` confirms). Wave 0 backend task to add:

```python
# backend/app/vulnerabilities/router.py — NEW route
from datetime import datetime, timedelta, UTC
from pydantic import BaseModel, Field

class SnoozeBody(BaseModel):
    until: datetime | None = Field(None, description="ISO timestamp; default = now + 1h")

@router.post("/{vuln_id}/snooze")
async def snooze_vuln(
    vuln_id: uuid.UUID,
    body: SnoozeBody,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
):
    """Snooze a vulnerability for a duration. Defaults to 1h. Sets status=SUPPRESSED + snoozed_until."""
    now = datetime.now(UTC)
    until = body.until or (now + timedelta(hours=1))
    if until <= now:
        raise HTTPException(400, "snoozed until must be in the future")
    if until > now + timedelta(days=30):
        raise HTTPException(400, "snoozes may not exceed 30 days")  # Pitfall: perpetual snooze
    result = await db.execute(
        update(Vulnerability)
        .where(Vulnerability.id == vuln_id, Vulnerability.tenant_id == user.tenant_id)
        .values(status='SUPPRESSED', updated_at=now)
        # NOTE: a `snoozed_until` column does NOT exist on Vulnerability today.
        # Adding it requires migration 025_add_vuln_snooze. Discuss with planner — D-H-07 only
        # specifies "snoozes the top sub-line CVE for 1h via the existing per-CVE snooze API"
        # implying status=SUPPRESSED is enough for Phase 10. The 1h auto-unsuppress is a
        # follow-on. Confirm intent with user OR plan migration in Wave 0.
    )
    if result.rowcount == 0:
        raise HTTPException(404, "Vulnerability not found")
    from app.audit import audit
    await audit(db, user, "vuln.snooze", "vulnerability", str(vuln_id), {"until": until.isoformat()})
    await db.commit()
    return {"message": "Snoozed", "until": until.isoformat()}
```

**Open question for the planner:** does D-H-08's "8s undo window before auto-dismiss" imply auto-unsuppress at `until`, or is the analyst expected to manually unsuppress? If auto-unsuppress, the snoozed_until column + a scheduler check are required. **Resolution recommendation:** plan as status='SUPPRESSED' only; auto-unsuppress is a follow-on. Document in `10-VERIFICATION.md`.

### Backend — `dashboard_tiles` + `top_vuln` + nav counts + `onboarding_state` (D-B-02)

Extend `DashboardStats` (schemas.py:112-121) additively, and the `get_dashboard_stats` service (service.py:220-291) to populate the new fields:

```python
# schemas.py — additions
class TileValue(BaseModel):
    value: int
    delta: int | None = None
    delta_direction: Literal['up','down','flat'] | None = None

class DashboardTiles(BaseModel):
    critical_open: TileValue
    sla_at_risk: TileValue
    kev: TileValue
    mttr_30d: TileValue  # value may be a float here — use Decimal/str depending on shape

class TopVuln(BaseModel):
    cve_id: str | None
    host: str | None
    path: str | None
    cvss: Decimal | None
    on_kev: bool
    exploited: bool

class DashboardStats(BaseModel):
    # … existing fields …
    dashboard_tiles: DashboardTiles
    top_vuln: TopVuln | None = None
    vuln_open_count: int
    asset_total_count: int
    ticket_open_count: int
    onboarding_state: Literal['no_scanners','no_data_yet','ready']
```

```python
# In get_dashboard_stats, compute delta_7d from DailySnapshot:
from app.vulnerabilities.trends import DailySnapshot

seven_days_ago = (datetime.now(UTC) - timedelta(days=7)).date()
prior = (await db.execute(
    select(DailySnapshot.metrics)
    .where(DailySnapshot.tenant_id == tenant_id,
           DailySnapshot.snapshot_date == seven_days_ago)
)).scalar_one_or_none()

def tile(today_value: int, key: str) -> TileValue:
    if prior is None:
        return TileValue(value=today_value, delta=None, delta_direction=None)
    delta = today_value - prior.get(key, 0)
    direction = 'up' if delta > 0 else 'down' if delta < 0 else 'flat'
    return TileValue(value=today_value, delta=delta, delta_direction=direction)

dashboard_tiles = DashboardTiles(
    critical_open=tile(critical_open_today, 'critical_open'),
    sla_at_risk=tile(sla_at_risk_today, 'sla_breached'),
    kev=tile(kev_count, 'kev_count'),  # NOTE: kev_count NOT currently in snapshot metrics
    mttr_30d=TileValue(value=mttr_today, delta=None),  # mttr delta is meaningful only over 30d windows
)
```

**Caveat for the planner:** the snapshot metrics dict (trends.py:281-292) does NOT currently capture `kev_count`. Wave 0 backend task: add `kev_count` to `capture_daily_snapshot`'s metrics dict. One line; idempotent (older snapshots will return `0` from `.get('kev_count', 0)`).

### Backend — `onboarding_state` detection (D-O-01)

Existing infrastructure (verified):
- `ConnectorConfig.is_enabled` (`backend/app/ticketing/models.py`)
- `ConnectorConfig.last_sync_at`, `last_sync_status`

```python
async def detect_onboarding_state(db: AsyncSession, tenant_id: uuid.UUID) -> str:
    enabled_count = (await db.execute(
        select(func.count(ConnectorConfig.id))
        .where(ConnectorConfig.tenant_id == tenant_id,
               ConnectorConfig.is_enabled.is_(True))
    )).scalar_one()
    if enabled_count == 0:
        return 'no_scanners'
    successful_sync = (await db.execute(
        select(func.count(ConnectorConfig.id))
        .where(ConnectorConfig.tenant_id == tenant_id,
               ConnectorConfig.last_sync_status == 'SUCCESS')
    )).scalar_one()
    if successful_sync == 0:
        return 'no_data_yet'
    return 'ready'
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `react-query` v3 — `useQuery({queryKey, queryFn}, options)` positional | `@tanstack/react-query` v5 — single object arg; `isLoading` → `isPending`; mutations require `mutationFn` | v5.0 (Oct 2023) | All examples here use v5 syntax. Training data from before mid-2024 may show v4 patterns. |
| `useQuery({ onError, onSuccess })` | `onError` / `onSuccess` on `useQuery` REMOVED in v5 | v5.0 | Use `QueryCache({ onError })` for global, or `query.error` in components. |
| Recharts pre-v2.10 — manual a11y | `accessibilityLayer` prop + keyboard navigation built-in | recharts 2.10 (late 2023) | Still need visually-hidden table for full a11y; keyboard nav comes free. |
| `router.replace(href, scrollOptions, transitionOptions)` (Pages Router) | `router.replace(href, { scroll: boolean })` — single options object | Next.js 13 App Router | Doc above uses current signature. |
| Per-query `onError: signOut` for 401 | Centralized fetch wrapper handles auth refresh + retry | Industry shift ~2022 | Phase 9 already does this in `api.ts`. |
| `react-query` ESLint plugin (separate) | `@tanstack/eslint-plugin-query` (rebrand) | v5.x | Recommend adding to devDeps. |
| `recharts.isAnimationActive={false}` to honor reduced motion | `recharts.isAnimationActive='auto'` — respects `prefers-reduced-motion` natively | recharts 2.x | Use `'auto'`; less code. [VERIFIED: studyraid.com/recharts-animations] |

**Deprecated/outdated:**
- `react-query` (npm name) → `@tanstack/react-query` since 2022.
- v5's `isLoading` semantics changed — canonical "first load" boolean is `isPending`; `isLoading` now means "pending + fetching".
- Next.js `<Head>` (Pages Router) — gone in App Router; metadata API replaces (server-only).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `recharts ^2.12.0` supports `accessibilityLayer` (added v2.10) and `isAnimationActive='auto'` (added v2.10) | Patterns 10, 11 | If pin is below 2.10, `accessibilityLayer` is a no-op (silently). Recommend bumping to the latest 2.x in Wave 0. Low risk — confirmed by reading package.json (`^2.12.0` ≥ 2.10). |
| A2 | `snoozed_until` column does NOT exist on `Vulnerability` today | Backend pattern for snooze | Verified by reading `backend/app/vulnerabilities/models.py:44-78`. The model has `sla_due_at` but no `snoozed_until`. If Phase 10 needs auto-unsuppress, a migration is required. Resolution: plan as `status='SUPPRESSED'`-only; auto-unsuppress is a follow-on. Document for planner. |
| A3 | `DailySnapshot.metrics` JSONB currently has `critical_open`, `open_vulns`, `sla_breached` but NOT `kev_count` | Backend delta computation | Verified by reading `trends.py:281-292`. Wave 0 backend task: add `kev_count` to the metrics dict captured nightly. One line. |
| A4 | The in-process scheduler in `connectors/scheduler.py` runs `capture_all_snapshots` once per 24h (gated on the `_last_ticket_sync` global) | Runtime State Inventory | Verified by reading `scheduler.py:167-177`. Job runs daily. The first 7 days of any new tenant won't have a `delta_7d` reference point. |
| A5 | Existing `api()` wrapper at `frontend/src/lib/api.ts` does NOT accept/pass an `AbortSignal` | Pattern 5 / 401 handling | Verified by reading `api.ts:30-72`. The `fetch(…)` call doesn't include `signal`. Wave 0 frontend task: add `signal` to the FetchOptions and pass through. One-line change. |
| A6 | `@tanstack/react-query` is NOT installed today | Standard Stack | Verified by reading `frontend/package.json` — does NOT appear in `dependencies` or `devDependencies`. |
| A7 | `vitest-axe` is the project's a11y matcher (NOT jest-axe) | Standard Stack | Verified by reading `frontend/vitest.setup.ts:2-7`. |
| A8 | The activity feed's link targets (`/dashboard/vulnerabilities?cve=…&open=drill`) won't be honored by anything until Phase 11 | Pitfall 10 | Per CONTEXT.md `<domain>` "Out of scope" — Phase 11 owns `?open=drill`. Expected behavior. |

**Resolution path:** None of these block planning. A2 (snoozed_until) and A3 (kev_count) require small backend touch-ups, both documented in `## Code Examples`. A5 (signal pass-through) is a one-line frontend change.

## Open Questions

1. **Snooze auto-unsuppress at `until`?**
   - What we know: D-H-07 says "snoozes the top sub-line CVE for 1h via the existing per-CVE snooze API." The "existing snooze API" does NOT exist today (grep confirms). D-H-08's Undo toast implies a discrete state.
   - What's unclear: does "snoozed for 1h" mean the vuln auto-returns to OPEN at `+1h`, or stays SUPPRESSED until manually unsuppressed?
   - Recommendation: ship Phase 10 as `status='SUPPRESSED'` only (no auto-unsuppress), with the Undo toast inverting via a second POST to `/snooze` (or a new `/unsnooze`). Auto-unsuppress can be a Phase 11+ enhancement when the scheduler grows a "snooze expiry sweep."

2. **`MTTR` delta direction — what counts as "good"?**
   - What we know: D-S-03 says "green ▼ when 'down is good'" and MTTR is one of those cases.
   - What's unclear: delta is on a 30-day rolling window; a 7-day delta of MTTR may be too noisy.
   - Recommendation: `mttr_30d` tile shows the value but `delta=None` for Phase 10 (no delta render). Re-evaluate in Phase 14 quality gate.

3. **What about the existing `/api/v1/vulnerabilities/overview` endpoint?**
   - What we know: `overview_stats` (`router.py:80-88` → `dashboard.py`) returns rich data already used by v1 dashboard.
   - What's unclear: does v2.0 dashboard still consume it? CONTEXT.md doesn't mention it.
   - Recommendation: leave `/overview` intact. Phase 10's stats screen reads only from `/stats`. The `/overview` endpoint stays available for any v1-styled screen until Phase 14 (CSPM/connectors/users/settings — those screens still read from it).

4. **Tile icon assignments — locked or planner discretion?**
   - What we know: D-S-05 says "ShieldAlert (critical_open) / Clock (sla_at_risk) / Flame (kev) / TrendingDown (mttr)."
   - What's unclear: this looks locked.
   - Recommendation: treat as locked. Lucide names all exist.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js 18+ | Next.js 15 build | Assumed ✓ (Phase 9 shipped Next 15) | — | — |
| Postgres | Backend (existing) | ✓ | (project default) | — |
| Redis | Backend (existing, Phase 1) | ✓ | (project default) | — |
| `@tanstack/react-query` | Frontend data layer | ✗ (not installed) | needs 5.x | None — locked dep |
| `recharts` | Chart | ✓ | ^2.12.0 (confirmed in package.json) | None — locked |
| `vitest-axe` | a11y tests | ✓ | ^0.1.0 (confirmed) | use `@axe-core/react` directly with `act` |
| `npm` | Package management | Assumed ✓ | — | — |
| Alembic | Backend migrations | ✓ (verified — `backend/alembic.ini` exists, 24 migrations under `backend/alembic/versions/`) | per pyproject.toml | — |

**Missing dependencies with no fallback:**
- `@tanstack/react-query` — install in Wave 0. Locked dependency; no alternative.

**Missing dependencies with fallback:**
- None.

## Validation Architecture

This phase has `nyquist_validation` enabled (default — `.planning/config.json` does NOT set `workflow.nyquist_validation: false`). The validation gate must prove all 6 requirements ship correctly across 9 dimensions (8 standard + 1 project-specific: **visual-fidelity-to-sketch-002**).

### Test Framework

| Property | Value |
|----------|-------|
| Frontend test runner | `vitest ^4.1.6` |
| Frontend a11y matcher | `vitest-axe ^0.1.0` — wired in `vitest.setup.ts` |
| Frontend DOM env | `jsdom ^25.0.1` |
| Component test lib | `@testing-library/react ^16.3.2` |
| Backend test runner | `pytest >=8.3` + `pytest-asyncio >=0.24` + `asgi-lifespan >=2.1` (verified `backend/pyproject.toml`) |
| Backend test fixture | Per `backend/tests/conftest.py` (Phase 9 + Phase 1 conventions) |
| Build measurement | `cd frontend && npm run build` — read **"First Load JS"** column on `/dashboard` row |
| Visual fidelity check | Manual UAT against `.claude/skills/sketch-findings-getvul/sources/002-dashboard-sunset/index.html` variant B |

### Phase Requirements → Test Map

| Req ID | Behavior | Dimension(s) | Test Type | Automated Command | File Status |
|--------|----------|--------------|-----------|-------------------|------|
| UX-02-01 | Hero renders with pulsing dot + headline + sub-line + CTAs | behavioral, visual-fidelity | unit | `vitest run frontend/src/components/dashboard/hero.test.tsx` | ❌ Wave 0 (new) |
| UX-02-01 | Snooze CTA fires POST `/snooze` and invalidates 3 cache keys | behavioral, integration | unit | `vitest run frontend/src/lib/mutations/use-snooze.test.tsx` | ❌ Wave 0 |
| UX-02-01 | POST `/snooze` endpoint exists + sets status=SUPPRESSED + audit event | behavioral, integration | pytest | `pytest backend/tests/test_snooze.py` | ❌ Wave 0 |
| UX-02-02 | StatStrip renders 4 tiles with delta indicators (▲/▼ + count + "from yesterday") | behavioral, visual-fidelity | unit | `vitest run frontend/src/components/ui/stat-strip.test.tsx` | ❌ Wave 0 |
| UX-02-02 | StatStrip handles `delta=null` as "Δ —" gracefully | behavioral, regression | unit | (included in stat-strip.test.tsx) | ❌ Wave 0 |
| UX-02-02 | `/stats.dashboard_tiles` returns 4 tiles with delta_7d computed from DailySnapshot | behavioral, integration | pytest | `pytest backend/tests/test_dashboard_tiles.py` | ❌ Wave 0 |
| UX-02-03 | TrendChart renders stacked bars with 4 severity colors via CSS variables | behavioral, regression | unit | `vitest run frontend/src/components/ui/trend-chart.test.tsx` | ❌ Wave 0 |
| UX-02-03 | TrendChart has visually-hidden `<table>` with 30 rows + 4 severity columns + totals | accessibility | unit + axe | (same file, axe assertion block) | ❌ Wave 0 |
| UX-02-03 | TrendChart route-splits — verify recharts absent from `/dashboard` main chunk | performance | manual + script | `cd frontend && npm run build && node scripts/check-bundle.mjs --route /dashboard --max-kb 184` | ❌ Wave 0 (script) |
| UX-02-03 | Range toggle URL-syncs (`?range=7d`) and clamps invalid input | behavioral, integration | unit | `vitest run frontend/src/hooks/use-url-state.test.ts` | ❌ Wave 0 |
| UX-02-03 | `/trends?days=30` returns `severity_trends: {date: {c,h,m,l}, …}` of length 30 | behavioral, integration | pytest | `pytest backend/tests/test_severity_trends.py` | ❌ Wave 0 |
| UX-02-04 | Top5Card renders 5 rows with severity glyph + CVE mono + asset + score + SLA pill | behavioral, visual-fidelity | unit | `vitest run frontend/src/components/dashboard/top5-card.test.tsx` | ❌ Wave 0 |
| UX-02-04 | `?sort=triage&limit=5` returns rows in KEV → CVSS desc → SLA-asc order | behavioral, integration | pytest | `pytest backend/tests/test_triage_sort.py` | ❌ Wave 0 |
| UX-02-05 | ActivityFeed renders 5 items with category-tinted icons (pink/amber/violet/success) | behavioral, visual-fidelity | unit | `vitest run frontend/src/components/ui/activity-feed.test.tsx` | ❌ Wave 0 |
| UX-02-05 | Existing `/notifications?page=1&page_size=5` shape unchanged | behavioral, regression | pytest | `pytest backend/tests/test_notifications.py` (Phase 9 baseline — confirm still passes) | ✅ existing |
| UX-02-06 | Quiet-win swap when `critical_open.value=0` — hero swaps to "Nothing critical right now" | behavioral | unit | `vitest run frontend/src/components/dashboard/hero.test.tsx::quiet-win` | ❌ Wave 0 |
| UX-02-06 | `onboarding_state='no_scanners'` renders full-page panel + "Connect a scanner" CTA | behavioral, integration | unit | `vitest run frontend/src/components/dashboard/onboarding-panel.test.tsx` | ❌ Wave 0 |
| UX-02-06 | `/stats.onboarding_state` correctly detects 'no_scanners' / 'no_data_yet' / 'ready' | behavioral, integration | pytest | `pytest backend/tests/test_onboarding_state.py` | ❌ Wave 0 |
| UX-02-06 | Every section has loading state (skeleton hero / skeleton tiles / skeleton chart) and error state (inline error block) | behavioral, regression | unit | `vitest run frontend/src/app/(authed)/dashboard/page.test.tsx` | ❌ Wave 0 |
| Cross-cutting | axe-core reports 0 violations on the full dashboard | accessibility | integration | `vitest run frontend/src/app/(authed)/dashboard/dashboard.a11y.test.tsx` | ❌ Wave 0 |
| Cross-cutting | First-Load JS on `/dashboard` ≤ 180 kB | performance | manual + script | (same as bundle-check above) | ❌ Wave 0 |
| Cross-cutting | Reduce-motion: chart animations disabled when `prefers-reduced-motion: reduce` | accessibility | unit | `vitest run frontend/src/components/ui/trend-chart.motion.test.tsx` | ❌ Wave 0 |
| Cross-cutting | Forced-colors: chart conveys severity via glyphs (tooltip + visually-hidden table) | accessibility | manual UAT | (DevTools "Emulate CSS media feature forced-colors: active") | manual in `10-HUMAN-UAT.md` |
| Cross-cutting | `queryClient.clear()` called on logout — next-user simulation shows no stale data | security, regression | unit | `vitest run frontend/src/lib/auth.logout.test.tsx` | ❌ Wave 0 |
| Cross-cutting | 401 → tryRefreshToken → retry → if-fail → `/login` chain (already in api.ts) | security, behavioral | unit | `vitest run frontend/src/lib/api.test.ts` | ❌ Wave 0 (or partial — confirm Phase 9 covers) |
| Cross-cutting | Visual fidelity to sketch 002 variant B | visual-fidelity | manual UAT | side-by-side at 1280px against `sources/002-dashboard-sunset/index.html` | manual in `10-HUMAN-UAT.md` |
| Cross-cutting | Document title updates to `(N) Dashboard · GetVul` when critical>0 | behavioral | unit | `vitest run frontend/src/hooks/use-document-title.test.ts` | ❌ Wave 0 |

### Dimension Coverage Matrix

| Dimension | Covered By |
|-----------|-----------|
| **Structural** | `npm run build` passes; `tsc --noEmit` passes; pydantic schemas validate; no unused exports |
| **Behavioral** | All per-requirement unit + integration tests above |
| **Integration** | Frontend hits real backend via vitest msw OR pytest-driven backend fixtures; full e2e via HUMAN UAT |
| **Regression** | Phase 9 test suite passes (53 tests verified in 09-HUMAN-UAT.md); legacy `/dashboard` rewrite must not break any of `/dashboard/{vulnerabilities,assets,cspm,tickets,users,settings}` tests (they keep v1 styling per CONTEXT.md `<domain>`) |
| **Performance** | First-Load JS ≤ 180 kB measured via `next build`; CLS < 0.1 verified in DevTools Performance trace during HUMAN UAT |
| **Accessibility** | axe-core via vitest-axe on every section; visually-hidden table for chart; reduce-motion test; forced-colors HUMAN UAT; keyboard nav HUMAN UAT |
| **Security** | `queryClient.clear()` test; 401 chain test (largely existing); error messages don't leak server-side detail (already enforced in Phase 9 `api.ts`); CSRF/cookie handling unchanged from Phase 9; snooze bounded to ≤ 30 days |
| **Visual fidelity (project-specific)** | Manual checklist against `sources/002-dashboard-sunset/index.html` variant B — palette, typography, severity glyphs, SLA chips, hover states, gradient CTA, pulsing dot |

### Sampling Rate

- **Per task commit:** `cd frontend && npm run test -- --run` (vitest, no watch); `cd backend && pytest -x` (fast fail)
- **Per wave merge:** Full vitest + full pytest + `npm run build` (verifies First-Load JS budget). Smoke: open `/dashboard` in dev server (`npm run dev`), check console for errors
- **Phase gate:** Full suite + a11y suite + HUMAN UAT against sketch 002 must all pass before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `frontend/src/components/dashboard/*.test.tsx` — files for 6 components (Hero, Top5Card, ActivityRail, TrendSection, OnboardingPanel, page-level integration)
- [ ] `frontend/src/components/ui/{card,stat,stat-strip,activity-feed,trend-chart,error-boundary}.test.tsx` — six primitive tests
- [ ] `frontend/src/lib/mutations/use-snooze.test.tsx`
- [ ] `frontend/src/lib/queries/use-stats.test.tsx`, `use-trends.test.tsx`, `use-top-triage.test.tsx`, `use-recent-notifications.test.tsx`
- [ ] `frontend/src/hooks/use-document-title.test.ts`, `use-url-state.test.ts`, `use-prefers-reduced-motion.test.ts`
- [ ] `frontend/src/lib/api.test.ts` — extend if Phase 9 didn't already cover 401 retry
- [ ] `frontend/src/lib/auth.logout.test.tsx` — assert `queryClient.clear()` called
- [ ] `frontend/src/app/(authed)/dashboard/dashboard.a11y.test.tsx` — full-page axe scan
- [ ] `frontend/scripts/check-bundle.mjs` — parses `.next/build-manifest.json` (or stdout of `next build`) and asserts `/dashboard` First-Load JS ≤ 184320 bytes
- [ ] `backend/tests/test_dashboard_tiles.py`, `test_severity_trends.py`, `test_triage_sort.py`, `test_top_vuln.py`, `test_snooze.py`, `test_onboarding_state.py`
- [ ] `frontend/src/components/dashboard/microcopy.ts` — extract all dashboard strings (per `copy-voice.md`)
- [ ] `.planning/phases/10-dashboard/10-HUMAN-UAT.md` — manual checklist for sketch fidelity + forced-colors + keyboard nav

## Security Domain

`security_enforcement` is presumed enabled (default per agent contract). Applicable ASVS categories for this phase:

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | yes | Phase 9 provides — Phase 10 only consumes via `api()` wrapper |
| V3 Session Management | yes | Phase 9 cookies/localStorage + silent refresh; `queryClient.clear()` on logout prevents cross-user data leakage (D-D-09) |
| V4 Access Control | yes | All endpoints already require `require_viewer`/`require_analyst` (verified in `router.py`); new `/snooze` route uses `require_analyst` |
| V5 Input Validation | yes | Three inputs: `?range=` (enum 7d/30d/90d — clamped in `useUrlState`), `?sort=triage` (pydantic pattern), `POST /snooze {until}` (pydantic datetime + bounds 0 < d < 30 days) |
| V6 Cryptography | no | None added |
| V7 Error Handling | yes | Backend `HTTPException` doesn't leak SQL; frontend error UI shows `<error code> · Request ID` per copy-voice.md without exposing stack traces |
| V8 Data Protection | yes | Tenant isolation already enforced via `Vulnerability.tenant_id` filter (`require_viewer` extracts from JWT); activity feed scopes via `tenant_id` filter on `Notification` query |
| V11 Business Logic | yes | Snooze: bounded to 30 days max (prevents perpetual snooze that defeats triage) |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Stale cache after logout (next user on shared machine sees prior user's vulns) | Information Disclosure | `queryClient.clear()` on signOut (D-D-09) |
| Snooze IDOR (user A snoozes user B's tenant vuln) | Tampering / Elevation | `tenant_id` filter in the snooze handler's `UPDATE` (matches every other vuln route in `router.py`) |
| Reflected XSS via `?range=<script>` | Tampering | `useUrlState` clamps to enum BEFORE rendering; never echoes raw string |
| Open-redirect via Snooze success URL | (n/a — no redirect) | — |
| Browser caching sensitive responses | Information Disclosure | Backend already sets `Cache-Control: no-store` on `/api/*` (`backend/app/main.py:95-97`) |
| Polling badge fingerprints user activity | Information Disclosure | Acceptable for an internal triage tool; document |
| Bundle-inlined secrets | Information Disclosure | Only `NEXT_PUBLIC_*` env vars reach the bundle; Phase 9 baseline |
| Race condition on Snooze + invalidation | Atomicity | TanStack `invalidateQueries` waits for in-flight to settle before refetching; backend `UPDATE` is single-row atomic |

## Sources

### Primary (HIGH confidence — read in this session)
- `.planning/phases/10-dashboard/10-CONTEXT.md` — 43 locked decisions (source of truth for design intent)
- `.planning/REQUIREMENTS.md` — UX-02-01..06 (paraphrased in ROADMAP)
- `.planning/ROADMAP.md` — Phase 10 success criteria (7 items)
- `.planning/PROJECT.md` — milestone framing + Out of Scope
- `.planning/phases/09-login-foundation/09-CONTEXT.md` — Phase 9 D-01..D-53
- `.planning/phases/09-login-foundation/09-REVIEW.md` — WR-01..WR-04 warnings
- `.planning/phases/09-login-foundation/09-HUMAN-UAT.md` — 12/12 PASS with in-session fixes
- `.claude/skills/sketch-findings-getvul/sources/002-dashboard-sunset/index.html` — variant B winner (the visual contract)
- `.claude/skills/sketch-findings-getvul/references/{foundation,page-layouts,visual-language,state-patterns,copy-voice,interaction-patterns,app-shell}.md`
- `frontend/package.json` — deps + dev deps
- `frontend/tailwind.config.ts` — sunset token wiring
- `frontend/src/styles/sunset.css` — every CSS variable
- `frontend/src/app/(authed)/layout.tsx` — Phase 9 layout
- `frontend/src/app/(authed)/dashboard/page.tsx` — v1 dashboard (rewrite target)
- `frontend/src/components/shell/sidebar.tsx` — Phase 9 sidebar with `—` placeholders waiting for nav-chip counts
- `frontend/src/lib/auth.tsx` — Phase 9 useAuth + 401 silent refresh
- `frontend/src/lib/api.ts` — Phase 9 fetch wrapper with 401 retry
- `frontend/src/components/ui/{button,input,dropdown-menu,gradient-text,form,sso-button,label,ToastProvider}.tsx` — Phase 9 primitives
- `frontend/src/app/dev/primitives/page.tsx` — Phase 9 `/dev/primitives` state matrix
- `frontend/vitest.setup.ts` — vitest-axe wiring
- `frontend/next.config.js` — CSP allows `connect-src 'self' http://localhost:8000 https://*.getvul.app`
- `backend/app/main.py` — FastAPI app with security headers, rate limiting, route registration
- `backend/app/vulnerabilities/{models,schemas,service,router,trends,dashboard}.py` — full vuln stack
- `backend/app/notifications/{models,router}.py` — notification stack
- `backend/app/connectors/scheduler.py` — in-process async scheduler with `capture_all_snapshots` already wired
- `backend/alembic/versions/021_add_daily_snapshots.py` — DailySnapshot migration (already applied)
- `backend/pyproject.toml` — Python deps (pytest, pytest-asyncio, asgi-lifespan, fastapi, sqlalchemy[asyncio], alembic)

### Secondary (HIGH-MEDIUM — verified via WebFetch against vendor docs)
- https://tanstack.com/query/latest/docs/framework/react/guides/advanced-ssr — `useState(() => new QueryClient())` pattern for App Router
- https://tanstack.com/query/latest/docs/framework/react/guides/mutations — `onSuccess` + `invalidateQueries` pattern
- https://tanstack.com/query/latest/docs/reference/QueryClient — `clear()` vs `invalidateQueries()` semantics
- https://nextjs.org/docs/app/api-reference/functions/use-router — `router.replace(href, { scroll: false })` Next 15 signature
- https://nextjs.org/docs/app/api-reference/functions/use-search-params — usage + Suspense considerations
- https://recharts.org/en-US/api/BarChart — stacked Bar + `accessibilityLayer`

### Tertiary (MEDIUM — WebSearch with multiple corroborating sources)
- recharts CSS variable fill support (community + shadcn/ui chart examples confirm v2.10+)
- recharts `isAnimationActive='auto'` honoring `prefers-reduced-motion` (studyraid.com/recharts-animations)
- lucide-react tree-shaking — named imports only (vercel-labs/agent-skills/bundle-barrel-imports.md)
- Next.js First Load JS column semantics (vercel/next.js issues #10565, discussion #19326)
- vitest-axe vs jest-axe — vitest-axe is the project's choice per setup file

## Metadata

**Confidence breakdown:**
- Standard stack (FE): **HIGH** — verified against `package.json` and vendor docs
- Architecture patterns (FE): **HIGH** — every pattern has a cited source + verified pre-existing code
- Architecture patterns (BE): **HIGH** — every SQL skeleton + endpoint shape is grounded in directly-read code (models.py, service.py, trends.py, scheduler.py)
- Pitfalls: **HIGH** — all 12 verified against doc claims or directly-read code
- Validation Architecture: **HIGH** — every requirement maps to a concrete file + command

**Research date:** 2026-05-15
**Valid until:** 2026-06-14 (30 days) for FE stack claims; BE shape claims remain valid as long as Phase 1 schema is unchanged and migration 021 is the latest snapshot-related migration. Re-verify before Phase 11 if more than 60 days elapse.

---

## RESEARCH COMPLETE

**Phase:** 10 — `/dashboard`
**Confidence:** HIGH across frontend stack, design contract, AND backend extension shapes (full backend tree directly inspected).

### Key Findings

1. **Backend lift is dramatically smaller than it looks.** `DailySnapshot` table exists since migration 021; the nightly capture job is already wired into the in-process scheduler at `connectors/scheduler.py:167-177`. `get_vuln_trends` already returns per-day severity counts (`by_severity` per timeline entry) — D-B-01 is a re-shape, not new SQL.

2. **TanStack Query v5 setup is fully canonical** — `useState(() => makeQueryClient())` inside `(authed)/layout.tsx` (already a client component via `ToastProvider`), no `HydrationBoundary` because the page is `'use client'` per D-R-01. Default `staleTime: 60s` with per-query overrides for the notifications query (30s).

3. **Phase 9's existing `frontend/src/lib/api.ts` already does 401-refresh-retry end-to-end.** TanStack Query wraps it; no new interceptor. One-line change needed: pass `AbortSignal` through to `fetch()` so TanStack can cancel in-flight requests.

4. **Recharts stacked BarChart with CSS-variable fills works in v2.12** (confirmed pinned to `^2.12.0`). `isAnimationActive='auto'` honors `prefers-reduced-motion` natively (no manual breakpoint needed). Route-split via `next/dynamic({ ssr: false })` keeps recharts (~80 kB) out of the shared bundle.

5. **The one genuinely new backend endpoint** is `POST /api/v1/vulnerabilities/{id}/snooze` — does not exist today (grep confirmed). Skeleton in `## Code Examples`. Implements bounded snooze (≤30 days). Auto-unsuppress is intentionally out of scope; the Undo toast inverts via a second POST.

6. **Validation has 26 distinct test items** mapped to 6 requirement IDs across 9 dimensions, plus manual visual-fidelity UAT against sketch 002 variant B. Every test has a concrete file path and command. 8 assumptions documented in the log — all bounded, all resolvable in <1 hour of Wave 0 work.
