# Roadmap: GetVul

## Overview

GetVul shipped its v0.1 feature set (vuln aggregation, correlation, ticketing, SLA, CSPM, notifications, reports). Its first GSD milestone is **v1.0 Production Readiness** — closing the blockers identified in the 2026-05-08 audit so a real customer can run this beyond the demo VM. Phase 1 (Multi-Replica State) shipped 2026-05-09; phases 2–8 are deferred while **v2.0 UI/UX Redesign** takes precedence. v2.0 rebuilds every authenticated screen against the validated Wiz-inspired sunset-palette design system (43 design decisions from 6 sketches, captured in `.claude/skills/sketch-findings-getvul/`). v2.0 ships as **vertical-slice phases**: each phase delivers one fully redesigned screen end-to-end (tokens + primitives + page wired to real backend + a11y + tests). Foundation requirements (UX-F-01..F-04) are embedded inside Phase 9 (the `/login` slice) — there is no foundation-only phase, by deliberate design. v1.0 phases 2–8 do not share files with the frontend rebuild and can resume in parallel or sequentially as a future v1.1 milestone.

## Milestones

- 🚧 **v1.0 Production Readiness** — Phases 1–8 (Phase 1 complete; Phases 2–8 deferred)
- 🚧 **v2.0 UI/UX Redesign** — Phases 9–15 (active)

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

**v1.0 Production Readiness (deferred phases 2–8):**

- [x] **Phase 1: Multi-Replica State** — Move OIDC state and rate limiter from in-process dicts to Redis
- [ ] **Phase 2: CI Gating** — Re-enable push/PR triggers and remove `|| true` masks so CI can block bad merges *(deferred)*
- [ ] **Phase 3: Update Path Reconciliation** — Pick one canonical update mechanism; document rollback *(deferred)*
- [ ] **Phase 4: Doc/Code Parity** — Ship missing CSP/COOP headers, fix scanner-count drift, extend `VulnSource` enum, decide on Secrets Manager *(deferred)*
- [ ] **Phase 5: Encryption Key Lifecycle** — Backup, rotation, and operator alerting for `ENCRYPTION_KEY` *(deferred)*
- [ ] **Phase 6: Default Admin Hardening** — Force password change on first login for the install.sh-created admin *(deferred)*
- [ ] **Phase 7: Health and Observability** — Split liveness/readiness, add JSON structured logs in prod *(deferred)*
- [ ] **Phase 8: Test Coverage Floor** — At least one test per connector, plus rule-engine and SLA tests *(deferred)*

**v2.0 UI/UX Redesign (active phases 9–15):**

- [ ] **Phase 9: `/login` + Foundation** — Split-screen sunset login + token system + first primitive set
- [ ] **Phase 10: `/dashboard`** — Action-first hero + stat strip + trend chart + activity feed sidebar
- [ ] **Phase 11: `/vulnerabilities` + State Patterns** — Chip-bar filters + side-panel drill-down + cross-cutting loading/empty/error patterns
- [ ] **Phase 12: `/assets` List + Detail** — List inherits Phase 11; two-column detail with risk ring + owner card + metadata rail
- [ ] **Phase 13: `/tickets` List + Detail** — Reuses list + detail patterns; adds provider gradient marks, status pills, watcher stacks
- [ ] **Phase 14: Remaining Screens** — CSPM, connectors, users, settings (sidebar-of-categories) against established primitives
- [ ] **Phase 15: Mobile + a11y + Perf Quality Gate** — 360/390/768/1280 viewport audit, bottom-nav, Lighthouse ≥ 90, axe pass per route, cross-browser, reduce-motion — closes the milestone

## Phase Details

<details>
<summary>✅ v1.0 Production Readiness — Phase 1 complete; Phases 2–8 deferred</summary>

### Phase 1: Multi-Replica State
**Goal**: Two backend replicas behind a load balancer can complete an OIDC login and share rate-limit budget without race conditions or lost state.
**Depends on**: Nothing (greenfield against current code)
**Requirements**: PROD-01-01, PROD-01-02, PROD-01-03
**Success Criteria** (what must be TRUE):
  1. `_pending_states` dict is gone from [backend/app/auth/router.py](backend/app/auth/router.py); state lives in Redis with TTL
  2. `_rate_limit_store` defaultdict is gone from [backend/app/main.py](backend/app/main.py); counter lives in Redis
  3. Integration test boots two backend processes against one Redis and verifies (a) OIDC callback succeeds when initiated by replica A and finished by replica B, and (b) rate-limit budget is shared
  4. [doc/security.md:20](doc/security.md#L20) claim "Redis-backed rate limiting" is now true
**Plans**: 4 plans

Plans:
- [x] 01-00-PLAN.md — Wave 0 foundation: asgi-lifespan dev dep, create_app() factory, Redis client in lifespan, get_redis dep, shared test fixtures
- [x] 01-01-PLAN.md — Redis-backed OIDC state store (SET NX EX 600 + GETDEL) with PROD-01-01 unit tests
- [x] 01-02-PLAN.md — Redis-backed per-tenant rate limiter (sorted-set sliding window) + PROD-01-02 tests + doc/security.md parity
- [x] 01-03-PLAN.md — Cross-replica integration test suite (2 apps + 1 Redis) for PROD-01-03

### Phase 2: CI Gating *(deferred)*
**Goal**: A PR with a failing test, type error, or lint error cannot be merged to main.
**Depends on**: Phase 1 (so the new tests are wired in before CI is enforced)
**Requirements**: PROD-02-01, PROD-02-02, PROD-02-03, PROD-02-04
**Success Criteria** (what must be TRUE):
  1. [.github/workflows/ci.yml](.github/workflows/ci.yml) runs on push to main and on every PR
  2. Backend mypy step fails the workflow when types are wrong (no `|| true`)
  3. Frontend lint and tsc steps fail the workflow on errors
  4. ZAP findings have an explicit policy: either gate the build above an agreed severity, or run as a labeled non-blocking workflow
  5. Branch protection on `main` requires CI green (documented in [doc/deployment.md](doc/deployment.md))
**Plans**: TBD (likely 2)

Plans:
- [ ] 02-01: Re-enable triggers and remove failure masks
- [ ] 02-02: ZAP policy decision and branch-protection docs

### Phase 3: Update Path Reconciliation *(deferred)*
**Goal**: There is exactly one way that production gets new code, and operators have a tested rollback procedure.
**Depends on**: Phase 2 (CI must gate releases first)
**Requirements**: PROD-03-01, PROD-03-02, PROD-03-03, PROD-03-04
**Success Criteria** (what must be TRUE):
  1. Either the hourly auto-update cron in [install.sh](install.sh) or the GH-Actions release CD in [.github/workflows/cd.yml](.github/workflows/cd.yml) is removed (or made strictly opt-in via flag); they no longer race
  2. CD pinning is to a release tag, not `git reset --hard origin/main`
  3. [doc/deployment.md](doc/deployment.md) has a "Rollback" section with the exact commands to revert to the prior release
  4. A dry-run rollback has been performed on a test VM and recorded in the phase verification
**Plans**: TBD (likely 2)

Plans:
- [ ] 03-01: Choose canonical update mechanism + remove the other
- [ ] 03-02: Tag-pinned CD + rollback runbook

### Phase 4: Doc/Code Parity *(deferred)*
**Goal**: README, security docs, source code, and the API surface tell the same story about what the product is and what it does.
**Depends on**: Nothing (independent of 1–3, can run in parallel)
**Requirements**: PROD-04-01, PROD-04-02, PROD-04-03, PROD-04-04, PROD-04-05
**Success Criteria** (what must be TRUE):
  1. Every header listed in [doc/security.md](doc/security.md) is actually emitted by either Nginx or the FastAPI middleware (verified by curl + ZAP rule)
  2. [README.md](README.md) lists 6 scanner sources, matching [doc/overview.md](doc/overview.md)
  3. `VulnSource` enum at [backend/app/vulnerabilities/models.py:31](backend/app/vulnerabilities/models.py#L31) includes `QUALYS` and `RAPID7`; existing rows backfilled or migrated
  4. Filtering vulns by `source=QUALYS` and `source=RAPID7` returns expected rows in a regression test
  5. `aws_region` / `secrets_manager_prefix` config and `boto3` dep are either implemented end-to-end or removed (no dead config)
**Plans**: TBD (likely 3)

Plans:
- [ ] 04-01: Ship CSP and COOP headers + ZAP regression
- [ ] 04-02: VulnSource enum + Qualys/Rapid7 source filter regression
- [ ] 04-03: Secrets Manager — implement or remove (decision in discuss-phase)

### Phase 5: Encryption Key Lifecycle *(deferred)*
**Goal**: An operator can confidently lose, restore, and rotate `ENCRYPTION_KEY` without losing connector credentials.
**Depends on**: Nothing
**Requirements**: PROD-05-01, PROD-05-02, PROD-05-03, PROD-05-04
**Success Criteria** (what must be TRUE):
  1. [doc/security.md](doc/security.md) has a section "Encryption Key Backup & Rotation" with concrete commands and an RTO statement
  2. A rotation CLI exists (e.g. `python -m app.encryption rotate --new-key <key>`) that re-encrypts every `connector_config.credentials_secret_arn` row in a single transaction with verification
  3. Backend startup logs a loud warning if `settings.encryption_key` matches the placeholder value or is unset
  4. End-to-end test: encrypt with key A → rotate to key B → decrypt all rows successfully → revert to key A → fail to decrypt (verifying rotation actually rotated)
**Plans**: TBD (likely 2)

Plans:
- [ ] 05-01: Rotation CLI + transactional re-encryption
- [ ] 05-02: Operator runbook + startup placeholder check

### Phase 6: Default Admin Hardening *(deferred)*
**Goal**: A fresh install.sh deploy cannot remain on the default `Admin123!` password by accident; the operator is forced through a rotation.
**Depends on**: Nothing (orthogonal to other phases)
**Requirements**: PROD-06-01, PROD-06-02, PROD-06-03, PROD-06-04
**Success Criteria** (what must be TRUE):
  1. New `users.must_change_password` column (boolean, default false) added by Alembic migration
  2. [backend/create_admin.py](backend/create_admin.py) sets the flag to true on the seeded admin
  3. Auth dependency rejects all non-`/auth/change-password` calls with 403 + `password_change_required` reason while the flag is set
  4. Frontend login flow reads the flag from `/auth/me` and routes to a force-rotation page
  5. Successful rotation clears the flag and emits an `auth.first_login_rotation` audit event
**Plans**: TBD (likely 2)

Plans:
- [ ] 06-01: Migration + backend enforcement
- [ ] 06-02: Frontend force-rotation flow

### Phase 7: Health and Observability *(deferred)*
**Goal**: Operators and load balancers can distinguish a starting backend from a healthy one, and production logs are machine-parseable.
**Depends on**: Nothing
**Requirements**: PROD-07-01, PROD-07-02, PROD-07-03, PROD-07-04
**Success Criteria** (what must be TRUE):
  1. `GET /health` is a no-dependency liveness probe (always 200 if the process is alive)
  2. `GET /ready` checks Postgres `SELECT 1` and Redis `PING`, each with ≤500ms timeout, returns 503 on failure
  3. Nginx `proxy_pass` for backend uses `/ready` for upstream health
  4. structlog output is JSON when `ENVIRONMENT=production`, human-readable in dev
  5. Failure modes have a documented operator response (DB down → 503 + alert; Redis down → 503 + alert)
**Plans**: TBD (likely 1–2)

Plans:
- [ ] 07-01: Split liveness/readiness probes + Nginx wiring
- [ ] 07-02: JSON structlog in production

### Phase 8: Test Coverage Floor *(deferred)*
**Goal**: A regression in any implemented connector, the rule engine, or SLA logic is caught by CI.
**Depends on**: Phase 2 (CI must actually run the tests)
**Requirements**: PROD-08-01, PROD-08-02, PROD-08-03, PROD-08-04
**Success Criteria** (what must be TRUE):
  1. `backend/tests/test_connectors/` has at least one happy-path test per implemented connector type, using mocked HTTP responses
  2. Ticket rule engine has tests for: rule fires when schedule due, daily-cap enforced (commit `b92ebf4` regression), dedup against existing tickets
  3. SLA breach detection has tests for: due-date computation per severity, OPEN→breached transition, at-risk window 72h before due
  4. Tenant-isolation regression suite extended to cover `/api/v1/search`, `/api/v1/notifications`, `/api/v1/reports`
  5. Backend coverage ratchets up by ≥10% from baseline (record baseline in Phase 2)
**Plans**: TBD (likely 3)

Plans:
- [ ] 08-01: Connector happy-path tests with mocked HTTP
- [ ] 08-02: Ticket rule engine + SLA service tests
- [ ] 08-03: Tenant-isolation regression for search/notifications/reports

</details>

## 🚧 v2.0 UI/UX Redesign (Active)

**Milestone Goal:** Replace v1's `!important`-hack light theme and missing-primitives frontend with a Wiz-inspired sunset-palette redesign across every authenticated screen. Each phase ships one screen end-to-end (tokens + primitives + page + state patterns + tests). No foundation-only phase — UX-F-01..F-04 ride inside Phase 9 (the `/login` slice).

**Design contract:** `.claude/skills/sketch-findings-getvul/` (43 validated decisions across 7 reference files). Auto-loaded during UI work per CLAUDE.md routing.

**Requirements source:** [.planning/REQUIREMENTS-v2.md](REQUIREMENTS-v2.md) — 50 items across UX-01..UX-07 plus cross-cutting UX-S-* and embedded UX-F-*.

### Phase 9: `/login` + Foundation
**Goal**: A visitor can open `/login` and see the redesigned split-screen sunset experience powered by a real token system and the first primitive set, with SSO buttons primary and the existing backend auth path unchanged.
**Depends on**: Nothing (first v2.0 vertical slice; no foundation phase precedes it)
**Requirements**: UX-01-01, UX-01-02, UX-01-03, UX-01-04, UX-01-05, UX-F-01, UX-F-02, UX-F-03, UX-F-04
**Success Criteria** (what must be TRUE):
  1. `/login` renders the split-screen layout — drifting `--gradient-mesh` + product-peek vuln rows on the left panel, clean dark form panel on the right — on a fresh browser tab at 1280px
  2. CSS variables defined in `:root[data-theme="dark"]` resolve correctly across the form panel (sunset palette visible); `grep -c '!important' frontend/src/app/globals.css` returns 0
  3. SSO buttons (Google + Microsoft) render above the email/password form with an `or with email` divider; forgot-password / password-reset modes hide the SSO row
  4. Inter (body) + JetBrains Mono (identifiers) load via `next/font` with `font-display: swap` (no FOIT on cold paint; verified in DevTools Network panel)
  5. Form submits successfully against the existing backend `/auth/login` endpoint (no backend changes); error states render with `bg-danger-soft` + `border-danger`
  6. Persistent shell scaffold (sidebar 220px + topbar with ⌘K + bell + avatar chip) renders behind protected routes ready for Phase 10 to consume
  7. Phase 9 ships Button, Input, SsoButton, GradientText primitives with all states (default / hover / focus-visible / disabled / loading / error) — re-usable by Phase 10+
**Plans**: TBD
**UI hint**: yes

### Phase 10: `/dashboard`
**Goal**: After logging in, an analyst lands on a redesigned dashboard whose hero answers "what should I do now?" first, with stats demoted to a strip and the activity feed in a right sidebar.
**Depends on**: Phase 9 (consumes tokens, shell, Button/GradientText primitives)
**Requirements**: UX-02-01, UX-02-02, UX-02-03, UX-02-04, UX-02-05, UX-02-06
**Success Criteria** (what must be TRUE):
  1. `/dashboard` renders the action-first hero — pulsing-dot eyebrow + numeric headline + mono host references + "Start triage" gradient CTA + "Snooze 1h" secondary
  2. 4-tile stat strip (Critical · open / SLA · at risk / CISA KEV / MTTR · 30d) renders below the hero with deltas (`▲ +3 from yesterday`)
  3. 30-day severity-stacked trend chart renders with hover nudge + range toggle (7d/30d/90d); chart code is route-split (not in the shared bundle)
  4. "Top 5 to triage" card renders with severity-glyph rows + SLA pills; clicking a row navigates to that CVE's drill view (stub link OK until Phase 11)
  5. Activity feed renders in the 340px right sidebar with sunset-tinted icon variants and the last 5 events from the existing `/api/v1/notifications` endpoint
  6. When the open-critical-CVE count is 0, hero swaps to the "Nothing critical right now" quiet-win empty state (no urgency framing)
  7. New primitives added in this phase (Card, Stat, StatStrip, ActivityFeed, TrendChart) are reusable and documented in `frontend/src/components/ui/`
**Plans**: 6 plans

Plans:
- [x] 10-01-PLAN.md — Backend extensions: severity_trends, dashboard_tiles + onboarding_state on /stats, ?sort=triage, POST /snooze + 6 pytest files
- [x] 10-02-PLAN.md — Frontend data layer: install TanStack Query v5, QueryClientProvider wire-up, 4 query hooks + snooze mutation + 3 utility hooks + microcopy.ts + logout cache-clear
- [x] 10-03-PLAN.md — Five presentation primitives: Card, Stat, StatStrip, ActivityFeed, ErrorBoundary + /dev/primitives state matrix
- [x] 10-04-PLAN.md — TrendChart primitive (recharts stacked BarChart + sr-only table + range toggle) + reduce-motion test + check-bundle.mjs budget enforcer
- [x] 10-05-PLAN.md — Dashboard page composition: Hero / StatStripWired / TrendSection / Top5Card / ActivityRail / OnboardingPanel + per-section ErrorBoundary + tab title + page-level + a11y tests
- [x] 10-06-PLAN.md — Sidebar nav-chip wiring (Vulnerabilities/Assets/Tickets counts) + 10-HUMAN-UAT.md checklist

**UI hint**: yes

### Phase 11: `/vulnerabilities` + State Patterns
**Goal**: An analyst can filter and drill into vulnerabilities through chip-bar filters and a 420px side-panel, and every list screen built from this phase forward has consistent loading / empty / error patterns.
**Depends on**: Phase 10 (consumes Card primitives + chart tokens; establishes Table primitive that Phase 12+ reuse)
**Requirements**: UX-03-01, UX-03-02, UX-03-03, UX-03-04, UX-03-05, UX-03-06, UX-S-01, UX-S-02, UX-S-03, UX-S-04, UX-S-05
**Success Criteria** (what must be TRUE):
  1. `/vulnerabilities` renders the chip-bar filter row (search + severity chips with counts + source chips + saved-filter violet pill + clear-all) above the table; no persistent left drawer exists
  2. Table renders the 7 spec columns (Severity pill+glyph · CVE mono · Title/Product · Asset mono · CVSS mono+banded · Status with KEV+exploit badges · SLA mono+tiered) and clicking a row opens a 420px right-side panel with description, CVSS vector, hosts, remediation, and action buttons
  3. Filter state is URL-synced (production: every chip/search change updates `?` query); reloading the URL restores filter state; "★ Today's triage" saved-filter pill restores in one click
  4. Segmented control toggle in the page-head actions switches between By-CVE and By-Host views without losing filter state
  5. At <900px viewport, the table collapses to card view (3-row card per row) and the drill panel becomes a full-screen overlay
  6. Loading state shows skeleton chip-bar + skeleton rows + per-source progress strip ("3 of 4 sources · 312 found so far"); empty state shows explained-why card + 3-tier CTAs + violet lightbulb suggestion; partial-failure error state shows amber inline banner with HTTP code + request ID + per-source status cards + stale-row tinting; toast notifications fire on saved-filter/snooze/ticket-created events (UX-S-01..S-05 satisfied)
  7. State patterns ship as reusable components (SkeletonTable, EmptyState, PartialFailureBanner, PerSourceStatusStrip, Toast) consumed by Phase 12+ verbatim
**Plans**: 8 plans

Plans:
- [x] 11-01-PLAN.md — Backend extensions: ?facets= / ?group=host / expanded ?sort= + ?order= + verify POST /tickets (4 pytest files)
- [x] 11-02-PLAN.md — Wave 0 scaffold: vaul@1.1.2 exact pin + Tailwind shimmer alias + 14 RED frontend test files matching the VALIDATION inventory
- [x] 11-03-PLAN.md — Data layer: useUrlStateList + useQueryErrors + useVulnerabilities/Detail + useConnectors + useSavedFilters + useCreateTicketMutation (401 surface)
- [x] 11-04-PLAN.md — 4 state primitives: SkeletonTable / EmptyState compound / PartialFailureBanner hybrid / PerSourceStatusStrip + barrel — all axe-clean
- [x] 11-05-PLAN.md — Vuln-page components: ChipBar (250ms debounce) + ViewToggle + VulnTable (keyboard nav + stale-row) + DrillPanel desktop + DrillPanelMobile (vaul)
- [x] 11-06-PLAN.md — Page rewrite: /dashboard/vulnerabilities page composition (~658→~150 lines) + delete v1 surface + restyle Pagination to sunset tokens
- [x] 11-07-PLAN.md — Phase 10 retrofit: 5 dashboard sites swap inline-minimal UI for canonical primitives (D-S-06; atomic commits per site)
- [x] 11-08-PLAN.md — Dev primitives showcase extension + 11-HUMAN-UAT.md manual verification checklist (8 manual-only items)

**UI hint**: yes

### Phase 12: `/assets` List + Detail
**Goal**: An analyst can scan an asset list with chip-bar filters and drill into a two-column detail page whose right rail keeps owner/identity context sticky while they scroll vulnerabilities and remediation on the left.
**Depends on**: Phase 11 (consumes Table, FilterChipBar, DrillPanel, state-pattern components)
**Requirements**: UX-04-01, UX-04-02, UX-04-03, UX-04-04, UX-04-05
**Success Criteria** (what must be TRUE):
  1. `/assets` list renders chip-bar + table with the 6 spec columns (Hostname mono · OS · Owner avatar+name · Risk Score · Tags · Sources) and reuses Phase 11's side-panel drill-down
  2. `/assets/[id]` renders the two-column detail pattern: main column with severity-breakdown ribbon (■2 · ▲3 · ◆1 · ○1) + vulnerabilities-on-this-host rows + remediation timeline; 340px sticky right rail with risk card + owner card + identity/host metadata
  3. Risk score renders as a circular SVG ring with sunset-gradient stroke, score number centered, and a 4-row breakdown (Critical exposures · SLA breaches · CISA KEV count · 7-day delta with `▲/▼` direction)
  4. Owner card shows 40px sunset-gradient avatar with initials + name + role + IdP source pill (`Okta` / `Google` / `Azure` in mono small chrome) + email; "Reassign" action available in the card header
  5. Breadcrumb (`Assets / prod-db-01`) renders above the page title; tag list renders inline with hostname
  6. State patterns (loading / empty / partial-failure / toast) reused from Phase 11 with no new variants required
**Plans**: TBD
**UI hint**: yes

### Phase 13: `/tickets` List + Detail
**Goal**: An analyst can review remediation work as a list with provider-aware identity chips and open a two-column detail that ties the ticket to its linked vulnerabilities, asset, and people.
**Depends on**: Phase 12 (inherits list + side-panel from Phase 11 and detail two-column pattern from Phase 12)
**Requirements**: UX-05-01, UX-05-02, UX-05-03, UX-05-04, UX-05-05, UX-05-06
**Success Criteria** (what must be TRUE):
  1. `/tickets` list renders chip-bar + table with the 8 spec columns (Severity · Provider · ID mono · Title · Vulns count+critical/high breakdown · Assignee · Status · SLA); rows open the side-panel drill from Phase 11
  2. Provider identity renders as gradient-mark chips, not real logos: Jira (cool-blue gradient square), Asana (coral), GitHub (violet) — verified zero references to Atlassian/Jira/Asana/GitHub trademark assets in `frontend/public/`
  3. Status pills use the separate color family from severity (Open violet · In progress amber · Completed green · Blocked red) with leading colored dot
  4. `/tickets/[id]` inherits the `/assets/[id]` two-column shape — main column: linked vulnerabilities (3+ rich rows) + description + activity timeline with comment input + status; right rail: Details + People (assignee + reporter + watcher avatar stack with `+N` overflow) + linked Asset card cross-referencing the asset detail page
  5. List / Board segmented toggle renders in the page-head-actions zone; Board view shows the placeholder copy (full kanban deferred to UX-D-01)
  6. State patterns reused from Phase 11 with no new variants; vuln-count column uses condensed format (`3 ·2 ·1` total·critical·high)
**Plans**: TBD
**UI hint**: yes

### Phase 14: Remaining Screens
**Goal**: Every remaining authenticated screen (CSPM, connectors, users, settings) is rebuilt against the established patterns so there's zero v1-styling left in the authenticated surface.
**Depends on**: Phase 13 (all primitives + patterns + state components landed; this phase is integration)
**Requirements**: UX-06-01, UX-06-02, UX-06-03, UX-06-04
**Success Criteria** (what must be TRUE):
  1. `/dashboard/cspm` renders chip-bar + side-panel for findings (inherited from Phase 11) + compliance frameworks list + cloud-segmented top control + finding cards
  2. `/dashboard/connectors` renders each connector as a card with provider gradient mark + last-sync timestamp + status pill + actions (sync now / edit / delete); the basic add-connector entry uses a multi-step form placeholder (full wizard deferred per UX-D-02)
  3. `/dashboard/users` renders a list with IdP-source pill on each user, bulk-actions toolbar, and role pills using the status-color family from Phase 13
  4. `/dashboard/settings` renders the sidebar-of-categories pattern (Profile / Workspace / SAML-OIDC / Notifications / API tokens / Audit log); the previous v1 tabbed-mess layout is fully replaced
  5. `grep -r "tab" frontend/src/app/dashboard/settings/` returns no horizontal-tab pattern usages; sidebar category is the only navigation
  6. Every screen in this phase passes the state-pattern audit (loading / empty / partial-failure / toast all present)
**Plans**: TBD
**UI hint**: yes

### Phase 15: Mobile + a11y + Perf Quality Gate
**Goal**: Every authenticated screen meets the milestone's mobile, accessibility, and performance bar — and the milestone is shippable.
**Depends on**: Phase 14 (all screens must exist before the closing audit)
**Requirements**: UX-07-01, UX-07-02, UX-07-03, UX-07-04, UX-07-05, UX-07-06, UX-07-07
**Success Criteria** (what must be TRUE):
  1. Every screen passes the viewport-audit at 360 / 390 / 768 / 1280 widths with no horizontal scroll; sidebar collapses to hamburger below 1000px; tables collapse to card view at <900px
  2. 4-slot bottom-nav (Dashboard / Vulnerabilities / Tickets / More) renders on mobile with `env(safe-area-inset-bottom)` padding; modals render as bottom sheets via `vaul` on mobile
  3. axe-core in Playwright passes on every route (no critical or serious violations); `eslint-plugin-jsx-a11y` is at `error` level in CI; 24×24 touch-min target verified on bottom-nav and chip-bar; focus-visible never obscured
  4. `prefers-reduced-motion: reduce` is honored: gradient-mesh drift stops, mount-stagger skips, pulsing dot becomes static — verified via DevTools rendering panel toggle
  5. `prefers-color-scheme` honored on first visit; theme toggle persists in `localStorage`; the FOUC-prevention blocking script runs before hydration (verified by no white flash on cold load of `/login` in dark-OS mode)
  6. Lighthouse mobile run on `/login` and `/dashboard` reports ≥ 90 performance AND ≥ 90 accessibility; per-route initial JS budget ≤ 250 KB gzipped (verified via `next build` analyzer output committed to the verification report)
  7. Cross-browser smoke pass — `/login` + `/dashboard` + `/vulnerabilities` + one detail page work in Chrome, Safari, Firefox (latest stable); severity glyphs (■ ▲ ◆ ○ □) render legibly at 14px on each browser's default rendering
**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
v1.0 Phase 1 shipped. v1.0 Phases 2–8 are deferred. v2.0 phases execute in numeric order 9 → 10 → 11 → 12 → 13 → 14 → 15. Phases 10–14 each depend on the prior phase's primitives / patterns; Phase 15 is the closing gate and depends on Phase 14.

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Multi-Replica State | v1.0 Production Readiness | 4/4 | Complete | 2026-05-09 |
| 2. CI Gating | v1.0 Production Readiness | 0/2 | Deferred | - |
| 3. Update Path Reconciliation | v1.0 Production Readiness | 0/2 | Deferred | - |
| 4. Doc/Code Parity | v1.0 Production Readiness | 0/3 | Deferred | - |
| 5. Encryption Key Lifecycle | v1.0 Production Readiness | 0/2 | Deferred | - |
| 6. Default Admin Hardening | v1.0 Production Readiness | 0/2 | Deferred | - |
| 7. Health and Observability | v1.0 Production Readiness | 0/2 | Deferred | - |
| 8. Test Coverage Floor | v1.0 Production Readiness | 0/3 | Deferred | - |
| 9. `/login` + Foundation | v2.0 UI/UX Redesign | 0/TBD | Not started | - |
| 10. `/dashboard` | v2.0 UI/UX Redesign | 6/6 | Complete    | 2026-05-18 |
| 11. `/vulnerabilities` + State Patterns | v2.0 UI/UX Redesign | 8/8 | Complete    | 2026-05-27 |
| 12. `/assets` List + Detail | v2.0 UI/UX Redesign | 8/8 | Complete    | 2026-06-01 |
| 13. `/tickets` List + Detail | v2.0 UI/UX Redesign | 4/9 | In Progress|  |
| 14. Remaining Screens | v2.0 UI/UX Redesign | 0/TBD | Not started | - |
| 15. Mobile + a11y + Perf Quality Gate | v2.0 UI/UX Redesign | 0/TBD | Not started | - |

---
*Roadmap created: 2026-05-08 from audit findings. v2.0 UI/UX Redesign section added 2026-05-12 from sketch findings.*
