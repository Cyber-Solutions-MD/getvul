# GetVul — Total UI/UX Redesign Plan

**Status:** Phase 1 complete. Awaiting approval before Phase 2 (Design Direction).

---

## 1. Codebase map

| Concern | Reality |
|---------|---------|
| Framework | Next.js 15.5.13 (App Router), React 19, TypeScript 5.5 strict |
| Styling | Tailwind CSS 3.4 (defaults — `theme.extend` only adds `background` / `foreground` CSS-var bindings); no plugin (no shadcn, Headless, Radix, Daisy, Flowbite) |
| Theme | Custom dark/light toggle via `.dark` / `.light` class on `<html>`; **light theme is implemented through ~100 `!important` overrides in `globals.css` lines 75–127** to flip Tailwind dark utilities — fragile and the single biggest CSS smell |
| Tokens | ~12 CSS variables for surfaces/text/borders, plus HSL fallbacks for shadcn-style `--primary` / `--destructive` (defined but mostly unused). No spacing, motion, typography, radius, or elevation tokens. |
| Icons | `lucide-react` exclusively — no mixing |
| Charts | `recharts` declared in `package.json` but **never imported** anywhere; the dashboard's "trend" visuals are pure SVG/CSS placeholders |
| State | React Context for auth + theme. Pages use `useState` + manual `useEffect` for data — no SWR/React Query/Zustand. Filter/tab state is component-local (lost on refresh, not in URL). |
| Routing | App Router; one public route (`/login`), nine protected (`/dashboard/*`); no `middleware.ts` |
| API client | `frontend/src/lib/api.ts` — `fetch` wrapper with auto-refresh on 401 and redirect on refresh failure. Tokens in `localStorage` (`getvul_token`, `getvul_refresh`). |
| Forms | Hand-rolled — every field is `<input className="...">` with manual `onChange`. No form library (no React Hook Form / Formik / TanStack Form). No client-side validation. |
| Tests | Zero. No Jest/Vitest/Playwright config. (Tracked under PROD-08.) |
| Stray files | `frontend/frontend/` and `frontend/tsconfig.tsbuildinfo` were just removed in the docs PR. |

### Dependency surprises

- **`recharts` is dead weight** — declared, never imported. We will either delete it or actually use it (chart redesign).
- **No global state library** is fine, but the lack of URL state for filters is a usability bug we'll fix in the redesign.
- `package.json` overrides pin `picomatch >=4.0.2` and `brace-expansion >=2.0.1` (transitive CVE patches). Keep.

---

## 2. Screens & routes

### Public

| Path | File | LOC |
|------|------|-----|
| `/login` | `frontend/src/app/login/page.tsx` | 227 |

### Protected (`/dashboard/*`, all wrapped in `dashboard/layout.tsx`)

| Path | File | LOC |
|------|------|-----|
| `/` (root) | `frontend/src/app/page.tsx` | redirects → `/login` |
| `/dashboard` | `frontend/src/app/dashboard/page.tsx` | **924** |
| `/dashboard/vulnerabilities` | `…/vulnerabilities/page.tsx` | **658** |
| `/dashboard/cspm` | `…/cspm/page.tsx` | **906** |
| `/dashboard/assets` | `…/assets/page.tsx` | 386 |
| `/dashboard/assets/[id]` | `…/assets/[id]/page.tsx` | 292 |
| `/dashboard/connectors` | `…/connectors/page.tsx` | 618 |
| `/dashboard/users` | `…/users/page.tsx` | 429 |
| `/dashboard/tickets` | `…/tickets/page.tsx` | **1,185** |
| `/dashboard/settings` | `…/settings/page.tsx` | **1,380** |

Total: 7,005 LOC of page code, with three files over 900 lines and one over 1,300 — a strong signal that pages are doing the work components should be doing.

---

## 3. Per-screen audit

### 3.1 `/login`

- **Primary user job:** authenticate (password or SSO), recover account.
- **Layout today:** centered max-w-md card; SSO buttons → divider → email/password form; mode switcher (login / register / forgot / reset) replaces the form in place.
- **Pain points:**
  - Password reset has 3 modes (email → token entry → success) crammed into one form swap — no progress indication.
  - SSO buttons styled inline with `bg-gray-800 hover:bg-gray-700` — generic; no provider visual identity.
  - Errors are raw `error.detail` strings from the API.
  - Loading state on `/auth/me` check is a bare spinner; no skeleton, no message.
  - 16px-but-not-quite input font means iOS Safari may zoom on focus.
  - Tab order is okay but focus rings inherit Tailwind defaults — barely visible on dark.
- **Success state:** SSO is the visually dominant path; password is recessed/secondary. Reset is a clearly stepped flow with a progress indicator. Errors are humanized and field-attached. Inputs render inline validation. Mobile keyboard hints are correct (`autocomplete`, `enterkeyhint`, `inputmode`).

### 3.2 `/dashboard` (overview)

- **Primary user job:** see risk posture at a glance, jump to the most urgent thing.
- **Layout today:** two tabs (Overview, Executive Report). Overview = 8 stat cards in a 2×4 grid, an SLA-compliance card with what looks like a half-implemented bar render (lines 95–119), a "recent tickets" table with horizontal-scroll risk under 768px, and a "top remediations" text list.
- **Pain points:**
  - **No primary action.** The user lands and there is nothing to *do* — only metrics to read. No "Triage 14 critical" CTA, no priority queue.
  - **Stat cards are flat.** Eight cards with thin icons, no hierarchy — everything competes equally.
  - **The "trend chart" doesn't render.** `TrendingUp` is imported; `recharts` is in deps but never used; the SLA bar appears truncated.
  - **Recent tickets is a table.** Horizontal-scrolls on tablet, gives no signal of urgency, dates aren't relative.
  - Color codes for stats (`red-400`, `orange-400`) are inline; not tokenized.
  - No empty/loading/error state on any card — first-load is jarring.
- **Success state:** one or two big "what to do next" cards above the fold (e.g., *14 critical vulnerabilities — start triage* with a real button). KPIs grouped by theme, not equal weight. A real sparkline trend chart. An activity feed (not a table) with time-relative ago strings. Skeletons during load. Empty state when there's nothing wrong ("All clear").

### 3.3 `/dashboard/vulnerabilities`

- **Primary user job:** find specific vulnerabilities, triage them in bulk (suppress, ticket, change status, export).
- **Layout today:** tabs (Vulnerabilities | Remediations); a filter panel; a 10-column table; pagination at 25/page; bulk-action bar.
- **Pain points:**
  - **10 columns is too many** below 1024px — table horizontal-scrolls everywhere.
  - **Filter state isn't in the URL** — refresh/share loses everything.
  - **Drill-down is in-place state**: Remediations → hosts-affected → host-remediations is 3 levels deep, all swapping the same panel. Confusing back behavior; no breadcrumb.
  - Bulk-select column is 10px wide on desktop, far below 44×44 minimum on mobile.
  - Suppressed rows use opacity + strikethrough — fragile, color-only.
  - No date range, no SLA filter, no asset-group filter.
  - Loading = spinner, empty = "No results" with no "clear filters" affordance, error = whatever the API said.
- **Success state:** filter drawer collapsible to icons on mobile; URL-synced filter state with named saved filters; a card/list view as the default below 1024px (table only on desktop); drill-down opens in a side panel/drawer, not a state swap; inline quick actions; sticky bulk-action bar with count + clear.

### 3.4 `/dashboard/cspm`

- **Primary user job:** review cloud misconfigurations, prove compliance to auditors.
- **Layout today:** four tabs (Findings | Resources | Compliance | Trends). Trends tab likely doesn't render (recharts unused). Compliance shows percentage text per framework, no bars.
- **Pain points:**
  - **No multi-cloud separation** — AWS, Azure, GCP all in one filter rather than tabs/segmentation; ops teams typically own one cloud.
  - **Compliance is just numbers** — "92%" with no visual or framework drilldown context.
  - Resources tab is yet another 10-column table.
  - "Last seen" is absolute time, never relative.
  - Tabs share filter state inconsistently; switching tabs may or may not preserve filters depending on which tab.
- **Success state:** cloud as a top-level segmented control (AWS / Azure / GCP / All); compliance as horizontal stacked bars with framework drill-through; trends as a real recharts area chart; findings as cards with embedded severity ribbon.

### 3.5 `/dashboard/assets`

- **Primary user job:** find risky devices and triage them.
- **Layout today:** 4-card stat row (Total / risk-band counts) + filter bar + sparse 4-column table + pagination + a "Classify" button (runs the auto-categorizer).
- **Pain points:**
  - **The risk score is text** (red/orange/yellow/green hex on text). It's the most important data point on the screen and it has no visual weight.
  - **"Classify" button** is one of the most prominent affordances and its label gives no clue what it does.
  - **No risk slider** (state exists, UI doesn't).
  - **Hover-only "Ignore" button** = invisible on mobile.
  - Hostname truncates with no tooltip.
- **Success state:** risk scores rendered as filled bars or rings (not text colors); device cards with 3-line summary on mobile and a denser table on desktop; "Auto-classify" with explicit affordance ("Re-run device classifier — 152 unclassified") and a progress indicator; persistent quick actions (no hover dependency).

### 3.6 `/dashboard/assets/[id]`

- **Primary user job:** investigate a single host, plan remediations.
- **Layout today:** back button → header (icon, hostname, status badges, risk score) → metadata table → tabs (Remediations | Vulnerabilities). Re-uses the giant 10-column vuln table.
- **Pain points:**
  - **Header wraps at small widths** — risk score floats away from the hostname.
  - Re-using the full vulnerability table for one host is overkill and re-introduces the same horizontal-scroll problem.
  - No remediation timeline (when is each due?).
  - No asset health (last scan, antivirus, patch level).
  - Single CTA ("Create Ticket") buried in the header without visual weight.
- **Success state:** compact identity strip + a "what to do" panel (top remediation, due date, owner) + a tabbed body. The vuln list here is short-form (CVE + severity + age) — not the desktop table.

### 3.7 `/dashboard/connectors`

- **Primary user job:** add a connector (scanner / IdP / MDM / ticketing), test it, see which ones are healthy.
- **Layout today:** four category sections (Vulnerability scanners, Ticketing, Identity, Enrichment & MDM). Each connector renders as a card with name, status dot, and 4 buttons (Connect / Edit / Test / Delete).
- **Pain points:**
  - **Status dots without text labels** fail color-only conveyance accessibility.
  - Connected connectors don't show "last synced X ago" — just a green dot.
  - The Test result is in a modal — extra click vs inline.
  - Add/Edit modal has zero inline validation; you click Save and the API yells at you.
  - Error messages come straight from upstream (e.g., the scanner's own "Invalid API token" string).
- **Success state:** category as filter chips, not section headers (less scrolling); each card surfaces last-sync, sync interval, error message inline; Test response is inline ("✓ tested 4s ago"); add/edit form has progressive disclosure with field-level validation and provider help links.

### 3.8 `/dashboard/users`

- **Primary user job:** see who has access, what role, what device they own; manage groups.
- **Layout today:** stats row (5 cards), tabs (Directory | Groups), filter bar (Search / Status / Department / Source), 6-column table.
- **Pain points:**
  - **Source badge is color-coded but not iconized** — Google blue and Azure blue are the same blue.
  - No avatar/identity strip; users are just text rows.
  - No bulk actions — can't disable 50 stale users at once.
  - "Last login" not surfaced (it's the most common reason an admin is on this page).
  - Status is text-only, no visual indicator.
- **Success state:** people-card grid on mobile and dense list on desktop; Last-login as a relative-time chip; bulk select + actions; provider badge with the actual provider mark (Google G, Microsoft tile, Okta wave).

### 3.9 `/dashboard/tickets`

- **Primary user job:** track remediation tickets that GetVul is creating or syncing in Asana / Jira; manage rules.
- **Layout today:** stats row (3 cards) + tabs (Tickets | Rules) + filter bar + manual "Sync Status with Asana" button + 7-column ticket table + bulk-comment via modal. Asana setup is somewhere here too (not surfaced cleanly).
- **Pain points:**
  - **No SLA-color coding on due dates** — everything looks the same urgency.
  - **Manual sync** is the main affordance; should be background and shown as "synced 5 min ago".
  - Asana setup buried (you have to know where it is).
  - Bulk comment requires 4 clicks to finish.
  - 1,185 LOC for one page strongly suggests this is several pages glued together.
- **Success state:** tickets as cards or a denser tabular view (one of, not both); urgency from SLA color; Asana/Jira setup is a CTA when no provider configured; rules tab as toggleable cards; auto-sync visible in the header.

### 3.10 `/dashboard/settings`

- **Primary user job:** organization administration — branding, SLA, TLS, SMTP, SAML/OIDC, users, audit log.
- **Layout today:** tabs (General | Authentication | Users | Audit log) — 1,380 LOC.
- **Pain points:**
  - **One mega-tab** ("General") jams Org info, branding, SLA, TLS, SMTP into a single scroll — the user can't find anything.
  - **Inline edit pattern is inconsistent** — some fields edit-in-place, others want a modal.
  - **SAML/OIDC config is a giant text area** with no validation.
  - **Audit log table** doesn't paginate well; date filters are dropdowns, not chips.
  - Timezone is a hard-coded list of 25 options.
- **Success state:** Settings as a sidebar-of-categories, not tabs (Organization / Branding / Authentication / Integrations / SLA & policy / Users / Audit). Each form has explicit save state and inline validation. SAML/OIDC has a step-by-step assistant. Audit log is a real activity feed with sticky filters.

---

## 4. Reusable components

### Today (`frontend/src/components/`)

| Path | LOC | What it does | Issues |
|------|-----|--------------|--------|
| `ui/Badge.tsx` | 64 | `SeverityBadge` / `StatusBadge` / `SourceBadge` | Color-only; no ARIA; color map duplicated across pages |
| `ui/ConfirmModal.tsx` | 78 | Confirm dialog (3 variants) | Esc + focus trap good; no aria-label; magic offsets |
| `ui/Pagination.tsx` | 84 | Number pagination | No aria-label on nav buttons; no `aria-current="page"`; no ←/→ keyboard nav; `min-w-[32px]` magic |
| `ui/Toast.tsx` | 67 | Toast item | No `role="status"` / `aria-live`; auto-dismiss is hard-coded 3s |
| `ui/ToastProvider.tsx` | (light) | Toast queue | Likely missing live region |
| `ui/ExportButton.tsx` | (light) | CSV trigger | No aria-label |
| `layout/Header.tsx` | 512 | Top bar (search, notifications, theme, user menu) | No focus trap on dropdowns; search results not arrow-key navigable; 3 hard-coded widths; 30s notification poll |
| `layout/Sidebar.tsx` | 72 | Side nav | No `aria-current="page"`; mobile toggle behavior unclear; relies entirely on `pathname` |
| `vulnerabilities/VulnTable.tsx` | 157 | Vuln data table | No `aria-sort`; checkboxes lack labels; `max-w-[150px]` magic on product col |
| `vulnerabilities/VulnFilters.tsx` | 220 | Filter panel | No `<form>`; no `aria-label` on toggle pills; color strings inline |
| `vulnerabilities/BulkActions.tsx` | (light) | Bulk action bar | Likely no `aria-live` for the count badge |

**The whole list of primitives that don't exist yet:** Button, Input, Select, Combobox, Checkbox, Radio, Switch, Textarea, Card, Dialog (modal), Drawer (sheet), Tabs, Tooltip, Avatar, Menu, Popover, ProgressBar, Skeleton, EmptyState, ErrorState, Form (label / hint / error), Table primitives (Header / Row / Cell with sort + selection), Chart wrappers.

Today every page reinvents these inline with raw `<input>`, `<button className="...">`, conditional class merges. The redesign builds the library first.

### Helpers (`frontend/src/lib/`)

| File | Public surface | Notes |
|------|---------------|-------|
| `api.ts` | `api<T>(path, options)` fetch wrapper | Auto-refresh on 401, redirect on refresh failure. Untyped error path. |
| `auth.tsx` | `AuthProvider`, `useAuth()` | login / register / loginSSO / logout. Token in `localStorage`. |
| `theme.tsx` | `ThemeProvider`, `useTheme()` | Default dark; toggles `<html>` class; doesn't read `prefers-color-scheme`. |
| `utils.ts` | `cn()` | clsx + tailwind-merge wrapper. Standard. |

---

## 5. Breakpoints & minimum viewport

- **Tailwind defaults** — `sm 640 / md 768 / lg 1024 / xl 1280 / 2xl 1536`. Not customized.
- **No declared minimum viewport.** No comments, no media queries below 640px. Sidebar hides below `md` (768). Several modals use `w-full` with margins so they sort-of work, but tables horizontal-scroll on every breakpoint below `lg`.
- **Hard-coded widths** found in components: `w-96`, `w-80`, `w-[calc(100vw-2rem)]` (header dropdowns), `max-w-md` / `max-w-lg` (modals), `max-w-[400/300/200/150px]` (table column truncation), `min-w-[32px]` (pagination), `h-[90vh]` (modal max height).

**Plan:** treat **360 × 640** as the floor. Add a `xs: 360` breakpoint or design every layout to flow through 360 unprefixed. Test in DevTools at 360 × 640 and 390 × 844 every screen.

Recommended breakpoint scale for the redesign:

| token | px | Used for |
|-------|----|---------|
| `xs` | 360 | iPhone SE / Galaxy A — base of mobile-first |
| `sm` | 480 | larger phones in landscape |
| `md` | 768 | tablets |
| `lg` | 1024 | small laptops — sidebar appears |
| `xl` | 1280 | desktops |
| `2xl` | 1536 | wide displays |

---

## 6. Cross-cutting issues that drive the redesign

These show up on every screen and need a system-level answer, not a per-page patch:

1. **No design tokens beyond surfaces.** Spacing, type scale, radius, shadow/elevation, motion — all ad hoc.
2. **Light theme is implemented through `!important` overrides.** It needs a real token system that swaps via CSS variables, not class overrides.
3. **Tables for everything.** A vuln-management product needs tables, but the redesign needs to make them responsive (cards on mobile, dense rows on desktop) and add card/list alternatives where appropriate.
4. **No empty / loading / error states.** Spinners and raw error strings dominate.
5. **No primary action per screen.** Most screens have N equal-weight buttons.
6. **Filter state is component-local.** Refresh = lost. URL sync is mandatory for the redesign.
7. **Color-only conveyance** in badges and dots — fails accessibility.
8. **Touch targets are too small** in pagination, bulk-select, hover-revealed actions.
9. **No motion system** at all. Toast slide-in and that's it. Page transitions, list reveals, reduce-motion respect — all missing.
10. **No focus visibility audit.** Default Tailwind focus ring is barely visible on the dark surface.

---

## 7. What I'm proposing for Phase 2

I'll commit to **one** aesthetic direction in `DESIGN_SYSTEM.md` after you approve this plan. To save us a round trip, here are the candidates I think actually fit a security-product workflow tool — strongest first.

### Option A — **Industrial / utilitarian** *(my recommendation)*

A console-flavored aesthetic. Mono display face for stats and CVE IDs (where character density + consistency is part of the meaning), a refined humanist sans for body. Two-tone palette with a single saturated accent (signal) and warning/danger drawn from a specific safety palette, not Tailwind. Sharp corners (`radius` 0–4 px), borders over shadows, dense data tables that earn their density. No purple, no pastel.

**Why it fits:** GetVul is a tool security analysts spend 8 hours a day in. The aesthetic should feel like a piece of equipment, not a marketing site. Industrial direction matches the mental model (terminals, dashboards, instruments) and lets us be honest about information density.

**Display face candidates:** *JetBrains Mono*, *IBM Plex Mono*, *Berkeley Mono* (paid), *Söhne Mono* (paid).
**Body face candidates:** *IBM Plex Sans*, *Söhne*, *Untitled Sans* (paid), *General Sans*.

### Option B — **Editorial / refined minimal**

A magazine layout. Serif display face for page titles and pull quotes (yes, in a security tool — it stops the homogeneity). Generous whitespace. Asymmetric grid. Dense data lives in disciplined corners.

**Why it could fit:** the Executive Report and the dashboard's at-a-glance views actually want this. Risk of fighting the operator's aesthetic in the operational pages.

### Option C — **Brutalist**

Raw grids, system colors used intentionally, exposed structure (visible borders, monospaced text, sharp transitions). Honest, fast, polarizing.

**Why it could fit:** maximum information density and a clear point of view. Risk: brutalist tends to read as "unfinished" to non-design users; in an enterprise security tool that's a liability.

I will pick A unless you steer me to B or C.

---

## 8. Risks & open questions

- **Light theme reset is invasive.** Every component needs to be rebuilt against a token system, not Tailwind utility classes that get `!important`'d away. Estimated: a clean rebuild rather than a refactor.
- **Charts.** `recharts` is in deps but unused — do we keep it or swap to `visx` / pure SVG / `tremor`? Recommendation: keep recharts (already paid for), layer custom theming on top.
- **Asana / Jira setup flows** are buried in `/dashboard/connectors` and `/dashboard/tickets`. They probably want their own dedicated onboarding routes.
- **Saved filters** are referenced in the API but the frontend implementation is unclear. The redesign should make these first-class (URL + named).
- **The `lib/api.ts` 401 → refresh → retry path** has a race condition (multiple simultaneous 401s could trigger multiple redirects). I'll fix this in Phase 6 cleanup, not as part of the visual redesign.
- **Frontend tests don't exist.** The redesign will introduce Vitest + React Testing Library + Playwright at minimum for the new component primitives.

---

## 9. Phases I'll execute after your sign-off

| Phase | Output | Commit |
|-------|--------|--------|
| 2. Direction | `DESIGN_SYSTEM.md` with token set, fonts, motion, colors | `design: commit to <direction> aesthetic` |
| 3. Components | `frontend/src/components/ui/*` rebuilt; primitives only, no screens | `feat(ui): rebuild component primitives against design system` |
| 4. Screens | Each route rebuilt against new components, mobile-first | one commit per screen, e.g. `feat(login): rebuild against design system` |
| 5. Mobile | Audit at 360/390 widths, bottom-sheet conversion of modals, gesture/safe-area pass | `feat(mobile): bottom sheets, safe areas, thumb-zone primary actions` |
| 6. Quality gates | Lighthouse / axe / contrast / reduced-motion / cross-browser fixes | `chore(a11y/perf): pass quality gates` |

Each phase ends in a commit and a status check-in.

---

## 10. Pause point

This is the end of Phase 1. Before I proceed to Phase 2, please confirm:

1. **Aesthetic direction** — go with **A (industrial / utilitarian)**, or steer to **B (editorial)** / **C (brutalist)** / something else?
2. **Light theme** — keep or drop? (Today it costs ~100 `!important` overrides; if we keep it, the new token system will do it cleanly. If we drop it, we save a real amount of complexity.)
3. **Charts library** — keep `recharts` (free, already in deps) or swap to `tremor` / `visx`?
4. **Mobile bottom-nav** — for 9 protected routes, mobile needs either a hamburger drawer or a 4–5 slot bottom nav with a "More" overflow. Which feels right? (Recommendation: bottom nav with the 4 most-used routes — Dashboard, Vulns, Assets, Tickets — and "More" for the rest.)
5. **Anything else** I should fold into the design direction.
