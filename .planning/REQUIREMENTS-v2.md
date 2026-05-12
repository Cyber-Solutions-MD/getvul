# Requirements: GetVul v2.0 UI/UX Redesign

**Defined:** 2026-05-12
**Source:** 43 design decisions from 6 sketches — see `.claude/skills/sketch-findings-getvul/SKILL.md` + `.planning/sketches/MANIFEST.md`
**Core Value preserved:** A vuln-triage analyst can open one dashboard, see the same CVE-on-host correlated across multiple scanners, identify the asset's owner from IdP/MDM/HR, and ship a Jira/Asana ticket — without ever opening a scanner console.

This file lives alongside (not replaces) `REQUIREMENTS.md`, which contains v1.0 Production Readiness requirements. v1.0 phases 2–8 are deferred while v2.0 ships.

## Active Milestone — v2.0 UI/UX Redesign

Each requirement maps to one phase in [ROADMAP.md](ROADMAP.md). Sourced from the validated sketch findings.

### Login screen (UX-01)

- [ ] **UX-01-01**: `/login` uses split-screen layout — gradient mesh visual on left (drifting `--gradient-mesh`, marketing copy, product-peek vuln rows), clean dark form panel on right. Tested at 360/768/1280px viewports (mobile collapses to vertical stack).
- [ ] **UX-01-02**: SSO buttons (Google + Microsoft) appear above the email/password form, with an `or with email` divider between. Email/password retained as secondary auth path.
- [ ] **UX-01-03**: Gradient CTA pill ("Sign in" → "Create account" depending on mode) is the only "fancy" element in the form panel. Loading state shows brief "Signing in…" copy.
- [ ] **UX-01-04**: Forgot-password and password-reset modes inherit the same panel chrome; SSO buttons hide in those modes.
- [ ] **UX-01-05**: Error states use the warm-palette-aware error bar pattern (`bg-danger-soft` + `border-danger`).

### Dashboard screen (UX-02)

- [ ] **UX-02-01**: `/dashboard` uses the action-first hero pattern — pulsing-dot eyebrow + headline-with-numeric-emphasis + sub-line with mono-formatted host references + primary CTA (Start triage) + secondary (Snooze 1h).
- [ ] **UX-02-02**: Below the hero: 4-tile stat strip — `Critical · open` / `SLA · at risk` / `CISA KEV` / `MTTR · 30d` — with deltas (`▲ +3 from yesterday`).
- [ ] **UX-02-03**: 30-day vulnerability trend chart with severity-stacked bars (critical/high/medium/low). Bars nudge on hover. Range toggle (7d/30d/90d).
- [ ] **UX-02-04**: "Top 5 to triage" card with severity-glyph rows + SLA pills. Click row to navigate to that CVE's drill.
- [ ] **UX-02-05**: Activity feed in the right sidebar (340px). Sunset-tinted icon variants (pink/amber/violet/success). Last 5 events.
- [ ] **UX-02-06**: When all critical CVEs are resolved/snoozed, hero swaps to the "quiet win" empty state ("Nothing critical right now") instead of the urgency framing.

### Vulnerabilities screen (UX-03)

- [ ] **UX-03-01**: `/vulnerabilities` uses chip-bar filters above the table (search input + severity chips with counts + source chips + saved-filter pill + clear-all). No persistent left filter drawer.
- [ ] **UX-03-02**: Table columns: Severity (pill+glyph) · CVE (mono) · Title/Product · Asset (mono) · CVSS Score (mono, color-by-band) · Status (KEV+exploit badges) · SLA (mono, color-tiered).
- [ ] **UX-03-03**: Click row to open 420px side-panel drill-down on the right. Table area transitions to `1fr 420px` grid. Panel shows description, CVSS vector, affected hosts, remediation, action buttons.
- [ ] **UX-03-04**: Saved filters live in the chip bar as a violet pill (`★ Today's triage`). Filter state URL-synced (production: every change updates `?` query string).
- [ ] **UX-03-05**: Toggle between By-CVE and By-Host views via segmented control in the page-head-actions zone.
- [ ] **UX-03-06**: On mobile (<900px), table collapses to card view (severity pill + CVE on row 1, product on row 2, asset + SLA on row 3) and drill panel becomes a full-screen overlay.

### Asset list + detail (UX-04)

- [ ] **UX-04-01**: `/assets` list uses the same chip-bar + side-panel pattern as `/vulnerabilities`. Columns: Hostname (mono) · OS · Owner (avatar+name) · Risk Score · Tags · Sources.
- [ ] **UX-04-02**: `/assets/[id]` detail uses two-column layout — main column with vulnerabilities-on-this-host (severity breakdown ribbon + rows) + remediation timeline. Right rail (340px, sticky) with risk card + owner card + identity/host metadata.
- [ ] **UX-04-03**: Risk score visualization is a **circular gradient ring** (SVG with sunset-gradient stroke + number in center + 4-row breakdown: Critical exposures · SLA breaches · CISA KEV count · 7d delta).
- [ ] **UX-04-04**: Owner card shows 40px sunset-gradient avatar with initials + name + role + IdP source pill (`Okta` / `Google` / `Azure` in mono small chrome) + email in mono. Reassign action available.
- [ ] **UX-04-05**: Breadcrumb above the detail title (`Assets / prod-db-01`). Tag list inline with hostname.

### Ticket list + detail (UX-05)

- [ ] **UX-05-01**: `/tickets` list uses the same chip-bar + side-panel pattern. Columns: Severity · Provider · ID (mono) · Title · Vulns (count + critical/high breakdown) · Assignee · Status · SLA.
- [ ] **UX-05-02**: Provider identity uses **gradient marks + tinted chips, not real logos**: Jira (cool blue), Asana (coral), GitHub (violet). Provider chip with small gradient square mark prefix.
- [ ] **UX-05-03**: Status workflow uses color family separate from severity: Open (violet) · In progress (amber) · Completed (green) · Blocked (red). Pill with leading dot.
- [ ] **UX-05-04**: `/tickets/[id]` detail inherits the `/assets/[id]` two-column pattern. Main column: linked vulnerabilities (3+ rich rows) · description · activity timeline with comment input · status. Right rail: Details + People (assignee+reporter+watchers with avatar stack) + linked Asset card.
- [ ] **UX-05-05**: Watcher / contributor lists use avatar stacks with `+N` overflow.
- [ ] **UX-05-06**: Kanban "Board view" placeholder — segmented toggle (List / Board) in page-head-actions, Board view deferred (sketched but not implemented; visible as toggle UI only).

### Remaining screens (UX-06)

- [ ] **UX-06-01**: `/dashboard/cspm` rebuilt against the same chrome and patterns. Compliance frameworks list + cloud-segmented top control + finding cards. Inherits chip-bar + side-panel for findings.
- [ ] **UX-06-02**: `/dashboard/connectors` rebuilt. Each connector as a card with provider mark + last-sync timestamp + status pill + actions (sync now, edit, delete). New-connector flow uses a multi-step form (placeholder; full wizard deferred to a future phase).
- [ ] **UX-06-03**: `/dashboard/users` rebuilt — list with IdP-source pill on each user, bulk actions toolbar, role pills.
- [ ] **UX-06-04**: `/dashboard/settings` rebuilt against the **sidebar-of-categories** pattern (not v1's tabbed mess). Categories: Profile · Workspace · SAML/OIDC · Notifications · API tokens · Audit log. Each category fills the right pane.

### State patterns (UX-S — cross-cutting)

These are enforced across every screen built in UX-01..UX-06. Verified in each phase's UAT.

- [ ] **UX-S-01**: Every list / data screen has a loading state with skeleton chip bar + skeleton table rows + per-source connector progress strip ("3 of 4 sources · 312 found so far"). Skeleton uses `--surface-2` shimmer; pill placeholders use sunset-tinted shimmer.
- [ ] **UX-S-02**: Every list / data screen has an empty state with explained-why body + active-filter summary card + 3-tier CTAs (clear-all gradient / broaden-one-axis secondary / broaden-everything secondary) + violet "lightbulb" suggestion (save-as-watch).
- [ ] **UX-S-03**: Every list / data screen has a partial-failure error state — amber inline banner (HTTP code + last sync + retry count + request ID + View trace / Retry now actions) + per-source status cards + stale rows tinted amber + footer caveat.
- [ ] **UX-S-04**: Total-failure error state (all sources down) defaults to the empty-state shell with retry-specific CTAs. Sketched conceptually, executed per screen as needed.
- [ ] **UX-S-05**: Toast notifications for transient events (ticket created, filter saved, connector retried, row resolved) — bottom-right, sunset-tinted variants, auto-dismiss (4s success / 6s info / manual error).

### Mobile + a11y + perf (UX-07 — closing milestone gate)

- [ ] **UX-07-01**: Every screen tested at 360 / 390 / 768 / 1280 viewport widths. No horizontal scroll. Sidebar collapses to hamburger below 1000px. Tables collapse to card view.
- [ ] **UX-07-02**: 4-slot bottom nav on mobile (Dashboard / Vulnerabilities / Tickets / More) with safe-area handling. Modals convert to bottom sheets via `vaul`.
- [ ] **UX-07-03**: WCAG 2.1 AA public commitment, WCAG 2.2 AA internal target (24×24 touch min, focus-not-obscured, dragging-movements). `eslint-plugin-jsx-a11y` at error; axe-core in Playwright per route.
- [ ] **UX-07-04**: `prefers-reduced-motion: reduce` substitutes — cross-fade only, skip mount-stagger, no pulses.
- [ ] **UX-07-05**: `prefers-color-scheme` honored on first visit; user toggle persists in `localStorage`. FOUC-prevention blocking script before hydration.
- [ ] **UX-07-06**: Lighthouse mobile target ≥ 90 perf + ≥ 90 a11y on `/login` and `/dashboard`. JS budget ≤ 250 KB gzipped per route initial. Charts code-split to `/dashboard` and `/cspm` only.
- [ ] **UX-07-07**: Cross-browser tested (Chrome, Safari, Firefox) on the smoke test suite. Real DPR rendering verified for severity glyphs (`■ ▲ ◆ ○ □`) at 14px and below.

## Foundation requirements (embedded in Phase 1, not standalone)

These ship as part of UX-01 (`/login` vertical slice) so they're consumed by real code on day one:

- [ ] **UX-F-01**: Token system implemented — CSS variables for color (sunset palette + severity + semantic), typography (Inter + JetBrains Mono via `next/font` with `font-display: swap`), spacing (4px base), shapes, motion (4 cubic-beziers + 4 durations), shadows + glow. Consumed by `tailwind.config.ts` via `theme.extend`.
- [ ] **UX-F-02**: Theme architecture — `:root[data-theme="dark"]` (default) + `:root[data-theme="light"]` swap CSS variables. **Zero `!important`** anywhere. v1's `globals.css` light overrides deleted entirely.
- [ ] **UX-F-03**: Persistent UI shell built — sidebar (220px with gradient brand mark + section labels + gradient-strip active indicator) + topbar (search-as-input with ⌘K + bell + help + avatar chip). Used by every authenticated screen.
- [ ] **UX-F-04**: First primitive set extracted from `/login` needs — Button (cta / secondary / ghost / icon-btn variants), Input (field-input), SsoButton, GradientText utility. Each with all states (default, hover, focus-visible, disabled, loading, error).

## Future Requirements (deferred from this milestone)

- **UX-D-01**: Drag-and-drop kanban view for tickets (sketched in sketch 006 variant C; placeholder toggle ships in UX-05 but actual board implementation deferred)
- **UX-D-02**: Connector onboarding wizard (multi-step form pattern; basic add-connector ships in UX-06-02, full wizard deferred)
- **UX-D-03**: Light-theme polish pass (architecture supports it; visual QA of every screen in light mode deferred)
- **UX-D-04**: Toast notification component (UX-S-05 covers requirement; component lib build deferred to whichever phase first needs it)
- **UX-D-05**: Charts beyond severity-stacked bars (sankey for connector health, ring for risk distribution) — `recharts` v3 + `visx` already in deps; specific visualizations deferred to a v2.x polish phase
- **UX-D-06**: Page-transition motion (cross-fade between routes; deferred — current scope is static-route polish only)

## Out of Scope (explicit exclusions)

- **Storybook component playground** — Manifest-driven development; if QA needs it, add later.
- **Tremor / Chakra / MUI / Headless UI** — shadcn/ui as vendored seed is the locked component-library decision (per `.claude/skills/sketch-findings-getvul/SKILL.md`).
- **Real provider logos** (Jira / Atlassian / Asana / GitHub trademarks) — gradient-mark substitution is the locked design decision (UX-05-02).
- **A v2.x backend change** — this milestone is frontend-only. Backend endpoints v1 already exposes are consumed as-is.

## Traceability

To be filled in by the roadmapper after roadmap creation:

| Requirement | Phase |
|-------------|-------|
| UX-01-* | _TBD_ |
| UX-02-* | _TBD_ |
| UX-03-*, UX-S-* | _TBD_ |
| UX-04-* | _TBD_ |
| UX-05-* | _TBD_ |
| UX-06-* | _TBD_ |
| UX-07-* | _TBD_ |
| UX-F-* | _TBD (embedded in first vertical slice)_ |
