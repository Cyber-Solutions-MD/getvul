# Roadmap: GetVul

## Overview

GetVul shipped its v0.1 feature set (vuln aggregation, correlation, ticketing, SLA, CSPM, notifications, reports). Its first GSD milestone is **v1.0 Production Readiness** — closing the blockers identified in the 2026-05-08 audit so a real customer can run this beyond the demo VM. Phase 1 (Multi-Replica State) shipped 2026-05-09; phases 2–8 are deferred while **v2.0 UI/UX Redesign** takes precedence. v2.0 rebuilds every authenticated screen against the validated Wiz-inspired sunset-palette design system (43 design decisions from 6 sketches, captured in `.claude/skills/sketch-findings-getvul/`). v2.0 ships as **vertical-slice phases**: each phase delivers one fully redesigned screen end-to-end (tokens + primitives + page wired to real backend + a11y + tests). Foundation requirements (UX-F-01..F-04) are embedded inside Phase 9 (the `/login` slice) — there is no foundation-only phase, by deliberate design. v1.0 phases 2–8 do not share files with the frontend rebuild and can resume in parallel or sequentially as a future v1.1 milestone.

## Milestones

- ✅ **v1.0 Production Readiness** — Phases 1–8 (all complete 2026-07-14)
- ✅ **v2.0 UI/UX Redesign** — Phases 9–15 (SHIPPED 2026-06-30) — archived: [milestones/v2.0-ROADMAP.md](milestones/v2.0-ROADMAP.md)
- ✅ **v2.1 Polish & Tech Debt** — BL-01..05 (SHIPPED 2026-07-15; no new phases — backlog cleanup) — see [MILESTONES.md](MILESTONES.md)
- 🚧 **v2.2 Deferred UI Features** — Phases 16–19 (opened 2026-07-15) — [milestones/v2.2-ROADMAP.md](milestones/v2.2-ROADMAP.md)

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

**v1.0 Production Readiness (phases 2–8 resumed 2026-06-30 — active):**

- [x] **Phase 1: Multi-Replica State** — Move OIDC state and rate limiter from in-process dicts to Redis
- [x] **Phase 2: CI Gating** — Re-enable push/PR triggers and remove `|| true` masks so CI can block bad merges (complete 2026-07-01)
- [x] **Phase 3: Update Path Reconciliation** — Pick one canonical update mechanism; document rollback (complete 2026-07-02)
- [x] **Phase 4: Doc/Code Parity** — Ship missing CSP/COOP headers, fix scanner-count drift, extend `VulnSource` enum, decide on Secrets Manager (complete 2026-07-03)
- [x] **Phase 5: Encryption Key Lifecycle** — Backup, rotation, and operator alerting for `ENCRYPTION_KEY` (complete 2026-07-08)
- [x] **Phase 6: Default Admin Hardening** — Force password change on first login for the install.sh-created admin (complete 2026-07-09)
- [x] **Phase 7: Health and Observability** — Split liveness/readiness, add JSON structured logs in prod (complete 2026-07-10)
- [x] **Phase 8: Test Coverage Floor** — At least one test per connector, plus rule-engine and SLA tests (complete 2026-07-14)
**v2.0 UI/UX Redesign (SHIPPED 2026-06-30 — Phases 9–15):** full detail archived in [milestones/v2.0-ROADMAP.md](milestones/v2.0-ROADMAP.md).

- [x] **Phase 9: `/login` + Foundation** — Split-screen sunset login + token system + first primitive set
- [x] **Phase 10: `/dashboard`** — Action-first hero + stat strip + trend chart + activity feed sidebar
- [x] **Phase 11: `/vulnerabilities` + State Patterns** — Chip-bar filters + side-panel drill-down + cross-cutting loading/empty/error patterns
- [x] **Phase 12: `/assets` List + Detail** — List inherits Phase 11; two-column detail with risk ring + owner card + metadata rail
- [x] **Phase 13: `/tickets` List + Detail** — Reuses list + detail patterns; adds provider gradient marks, status pills, watcher stacks
- [x] **Phase 14: Remaining Screens** — CSPM, connectors, users, settings (sidebar-of-categories) against established primitives
- [x] **Phase 15: Mobile + a11y + Perf Quality Gate** — 360/390/768/1280 viewport audit, bottom-nav, Lighthouse ≥ 90, axe pass per route, cross-browser, reduce-motion — closed the milestone

**v2.2 Deferred UI Features (opened 2026-07-15 — Phases 16–19):** full detail in [milestones/v2.2-ROADMAP.md](milestones/v2.2-ROADMAP.md).

- [x] **Phase 16: Light-theme visual completion** — per-route light-mode QA + axe AA in both themes (UX-D-03) (executed 2026-07-15; gap-closure 16-03 + WR-04 systemic on-soft migration 2026-07-16; verification passed 4/4 SC, live axe sweep green in both themes — see 16-VERIFICATION.md) (completed 2026-07-16)
- [x] **Phase 17: Page-transition motion** — View Transitions API cross-fade, reduced-motion-safe (UX-D-06) (completed 2026-07-16)
- [ ] **Phase 18: Tickets kanban board** — @dnd-kit status columns replacing the placeholder (UX-D-01)
- [ ] **Phase 19: Add-connector wizard** — 4-step provider → credentials → test → confirm (UX-D-02)

## Phase Details

## 🚧 v1.0 Production Readiness — Phase 1 complete; Phases 2–8 active (resumed 2026-06-30)

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

### Phase 2: CI Gating
**Goal**: A PR with a failing test, type error, or lint error cannot be merged to main.
**Depends on**: Phase 1 (so the new tests are wired in before CI is enforced)
**Requirements**: PROD-02-01, PROD-02-02, PROD-02-03, PROD-02-04
**Success Criteria** (what must be TRUE):
  1. [.github/workflows/ci.yml](.github/workflows/ci.yml) runs on push to main and on every PR
  2. Backend mypy step fails the workflow when types are wrong (no `|| true`)
  3. Frontend lint and tsc steps fail the workflow on errors
  4. ZAP findings have an explicit policy: either gate the build above an agreed severity, or run as a labeled non-blocking workflow
  5. Branch protection on `main` requires CI green (documented in [doc/deployment.md](doc/deployment.md))
**Plans**: 2 plans

Plans:
- [x] 02-01-PLAN.md — Arm ci.yml (push/PR/nightly triggers), remove frontend masks + fix 6 tsc casts, wire mypy baseline gate, gate DAST off PRs + bump ZAP pins
- [x] 02-02-PLAN.md — Branch protection via gh api (4 required checks) + empirical failing-PR/merge-block test + CI-gating docs

### Phase 3: Update Path Reconciliation
**Goal**: There is exactly one way that production gets new code, and operators have a tested rollback procedure.
**Depends on**: Phase 2 (CI must gate releases first)
**Requirements**: PROD-03-01, PROD-03-02, PROD-03-03, PROD-03-04
**Success Criteria** (what must be TRUE):
  1. Either the hourly auto-update cron in [install.sh](install.sh) or the GH-Actions release CD in [.github/workflows/cd.yml](.github/workflows/cd.yml) is removed (or made strictly opt-in via flag); they no longer race
  2. CD pinning is to a release tag, not `git reset --hard origin/main`
  3. [doc/deployment.md](doc/deployment.md) has a "Rollback" section with the exact commands to revert to the prior release
  4. A dry-run rollback has been performed on a test VM and recorded in the phase verification
**Plans**: 2 plans

Plans:
- [x] 03-01-PLAN.md — Hard-remove the auto-update cron (install.sh + all 3 cloud startup.sh + git rm auto-update.sh) and clean cron references in architecture/structure/troubleshooting docs (PROD-03-01, PROD-03-02)
- [x] 03-02-PLAN.md — Tag-pinned CD (cd.yml checkout rewrite + release_tag dispatch input) and rollback runbook in docs/13-deployment.md with migration caveat + docs/12 & mermaid reconciliation (PROD-03-03, PROD-03-04)

### Phase 4: Doc/Code Parity
**Goal**: README, security docs, source code, and the API surface tell the same story about what the product is and what it does.
**Depends on**: Nothing (independent of 1–3, can run in parallel)
**Requirements**: PROD-04-01, PROD-04-02, PROD-04-03, PROD-04-04, PROD-04-05
**Success Criteria** (what must be TRUE):
  1. Every header listed in [doc/security.md](doc/security.md) is actually emitted by either Nginx or the FastAPI middleware (verified by curl + ZAP rule)
  2. [README.md](README.md) lists 6 scanner sources, matching [doc/overview.md](doc/overview.md)
  3. `VulnSource` enum at [backend/app/vulnerabilities/models.py:31](backend/app/vulnerabilities/models.py#L31) includes `QUALYS` and `RAPID7`; existing rows backfilled or migrated
  4. Filtering vulns by `source=QUALYS` and `source=RAPID7` returns expected rows in a regression test
  5. `aws_region` / `secrets_manager_prefix` config and `boto3` dep are either implemented end-to-end or removed (no dead config)
**Plans**: 3 plans

Plans:
- [x] 04-01-PLAN.md — Ship CSP + COOP headers on SecurityHeadersMiddleware, flip docs/16-security.md drift rows, verify README scanner parity (PROD-04-01, PROD-04-02)
- [x] 04-02-PLAN.md — Extend VulnSource enum (QUALYS + RAPID7) + API source-filter regression incl. tenant scope (PROD-04-03, PROD-04-04)
- [x] 04-03-PLAN.md — Exhaustive AWS Secrets Manager / boto3 removal + doc scrub + pip reinstall + repo-wide grep verification (PROD-04-05)

### Phase 5: Encryption Key Lifecycle
**Goal**: An operator can confidently lose, restore, and rotate `ENCRYPTION_KEY` without losing connector credentials.
**Depends on**: Nothing
**Requirements**: PROD-05-01, PROD-05-02, PROD-05-03, PROD-05-04
**Success Criteria** (what must be TRUE):
  1. [doc/security.md](doc/security.md) has a section "Encryption Key Backup & Rotation" with concrete commands and an RTO statement
  2. A rotation CLI exists (e.g. `python -m app.encryption rotate --new-key <key>`) that re-encrypts every `connector_config.credentials_secret_arn` row in a single transaction with verification
  3. Backend startup logs a loud warning if `settings.encryption_key` matches the placeholder value or is unset
  4. End-to-end test: encrypt with key A → rotate to key B → decrypt all rows successfully → revert to key A → fail to decrypt (verifying rotation actually rotated)
**Plans**: 3 plans (2 original + 1 gap closure)

Plans:
- [x] 05-01-PLAN.md — Rotation CLI (`_fernet_for` refactor + rotate/verify/generate-key via `python -m app.encryption`) + transactional abort-all re-encryption with pre-flight/post-verify, dry-run, confirmation, backup reminder, `encryption.key_rotated` audit, and SC#4 E2E test (PROD-05-02, PROD-05-03)
- [x] 05-02-PLAN.md — Startup placeholder/invalid-key check in `main.py` lifespan (encryption + JWT, hard-fail prod / warn dev) + backup & rotation runbook in `docs/16-security.md` (PROD-05-01, PROD-05-03, PROD-05-04)
- [x] 05-03-PLAN.md — Gap closure (UAT Test 5 blocker): register User+Tenant models in `rotate_credentials()` before the AuditLog write so the standalone `python -m app.encryption rotate` CLI no longer crashes with NoReferencedTableError, + subprocess regression test reproducing the real operator path (PROD-05-02, PROD-05-03)

### Phase 6: Default Admin Hardening
**Goal**: A fresh install.sh deploy cannot remain on the default `Admin123!` password by accident; the operator is forced through a rotation.
**Depends on**: Nothing (orthogonal to other phases)
**Requirements**: PROD-06-01, PROD-06-02, PROD-06-03, PROD-06-04
**Success Criteria** (what must be TRUE):
  1. New `users.must_change_password` column (boolean, default false) added by Alembic migration
  2. [backend/create_admin.py](backend/create_admin.py) sets the flag to true on the seeded admin
  3. Auth dependency rejects all non-`/auth/change-password` calls with 403 + `password_change_required` reason while the flag is set
  4. Frontend login flow reads the flag from `/auth/me` and routes to a force-rotation page
  5. Successful rotation clears the flag and emits an `auth.first_login_rotation` audit event
**Plans**: 4 plans (0 Wave 0 test scaffold + 3 execution waves)

Plans:
- [x] 06-00-PLAN.md — Wave 0: create backend + frontend test scaffolds (RED targets for Nyquist)
- [x] 06-01-PLAN.md — Migration 029 + User column + create_admin seed flag + apply (PROD-06-01)
- [x] 06-02-PLAN.md — JWT claim + CurrentUser + 403 enforcement gate/allowlist + rotation completion (clear flag, audit, fresh tokens) (PROD-06-02, PROD-06-04)
- [x] 06-03-PLAN.md — Frontend /change-password page + auth.tsx redirect gate (PROD-06-03)

### Phase 7: Health and Observability
**Goal**: Operators and load balancers can distinguish a starting backend from a healthy one, and production logs are machine-parseable.
**Depends on**: Nothing
**Requirements**: PROD-07-01, PROD-07-02, PROD-07-03, PROD-07-04
**Success Criteria** (what must be TRUE):
  1. `GET /health` is a no-dependency liveness probe (always 200 if the process is alive)
  2. `GET /ready` checks Postgres `SELECT 1` and Redis `PING`, each with ≤500ms timeout, returns 503 on failure
  3. Nginx `proxy_pass` for backend uses `/ready` for upstream health
  4. structlog output is JSON when `ENVIRONMENT=production`, human-readable in dev
  5. Failure modes have a documented operator response (DB down → 503 + alert; Redis down → 503 + alert)
**Plans**: 3 plans (1 Wave 0 test scaffold + 2 execution plans in Wave 1)

Plans:
- [x] 07-00-PLAN.md — Wave 0: RED test scaffold (test_health_observability.py, full D-21 matrix + D-13/14/17) + importable logging.py stub
- [x] 07-01-PLAN.md — /health + /ready split (JSONResponse 503, 500ms bound), RequestIdMiddleware, configure_logging() call-site, nginx upstream + /ready, compose healthcheck flip (PROD-07-01, PROD-07-02, PROD-07-03)
- [x] 07-02-PLAN.md — structlog unified JSON stream + redaction + probe access-log suppression + Failure Modes operator runbook (PROD-07-04)

### Phase 8: Test Coverage Floor
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

## ✅ v2.0 UI/UX Redesign — SHIPPED 2026-06-30

Phases 9–15 redesigned every authenticated screen against the Wiz-inspired sunset-palette design system (vertical slices: tokens + primitives + page + state patterns + a11y + tests). Quality gate green on the production build (Playwright 28 passed; bundle 15/15 ≤ 250 KB; Lighthouse /login 97/95, /dashboard 90/95). Audit: `tech_debt`, 0 blockers, 48/48 requirements wired.

**Full phase detail + accomplishments + decisions + tech-debt:** [milestones/v2.0-ROADMAP.md](milestones/v2.0-ROADMAP.md) · **Requirements:** [milestones/v2.0-REQUIREMENTS.md](milestones/v2.0-REQUIREMENTS.md) · **Audit:** [milestones/v2.0-MILESTONE-AUDIT.md](milestones/v2.0-MILESTONE-AUDIT.md)

## 🚧 v2.2 Deferred UI Features — IN PROGRESS (opened 2026-07-15)

Finishing the four features deferred out of v2.0. Every phase holds the phase-15 gate (axe WCAG 2.1 AA in both themes, reduced-motion, ≤250 KB First-Load JS/route) and the `sketch-findings-getvul` design contract. Locked: View Transitions API (motion) + @dnd-kit (kanban). Full detail: [milestones/v2.2-ROADMAP.md](milestones/v2.2-ROADMAP.md).

### Phase 16: Light-theme visual completion
**Goal**: Every authenticated route is visually correct and WCAG 2.1 AA in light mode — not just architecturally themed.
**Depends on**: Nothing (unblocks the axe-in-both-themes requirement for phases 17–19)
**Requirements**: UX-D-03-01, UX-D-03-02, UX-D-03-03, UX-D-03-04, UX-D-03-05
**Success Criteria** (what must be TRUE):
  1. A per-route light-mode sweep shows no dark-only visual artifacts (borders/shadows/hover/disabled) on any of the ~15 routes
  2. `e2e/a11y-routes.spec.ts` runs under `data-theme="light"` and reports 0 serious/critical axe violations on every route
  3. Severity/status/SLA pills and glyphs are legible and distinct on light surfaces; muted/faint/disabled tokens pass AA (source-palette changes reconciled into the design system)
  4. Zero First-Load-JS delta (CSS-only); the existing dark-mode gate stays green
**Plans**: 3 plans (2 waves + 1 gap-closure)
- [x] 16-01-PLAN.md — light-mode token overrides + component literal fixes + light-theme axe sweep (the joint UX-D-03-01..05 gate)
- [x] 16-02-PLAN.md — reconcile axe-confirmed light values into the design-system skill (BL-04 mirror) + enable the Theme: Light toggle
- [x] 16-03-PLAN.md — gap closure: --color-info light override (WR-01) + amber-on-soft migration (WR-02) + executed light+dark axe sweep evidence (SC#2)

### Phase 17: Page-transition motion
**Goal**: Route changes within the app shell cross-fade smoothly, reduced-motion-safe, at zero bundle cost.
**Depends on**: Phase 16 (both-themes axe baseline)
**Requirements**: UX-D-06-01, UX-D-06-02, UX-D-06-03, UX-D-06-04, UX-D-06-05
**Success Criteria** (what must be TRUE):
  1. Navigating between authed routes shows a View-Transitions cross-fade via a single `(authed)/template.tsx`
  2. Under `prefers-reduced-motion: reduce`, transitions are suppressed (animation-duration ≤0.02s) and `e2e/reduced-motion.spec.ts` stays green
  3. A CSS fallback keeps navigation clean in non-supporting browsers (Firefox) — no jank or broken paint
  4. DrillPanel Esc/clickaway close still works during/after a transition; no layout shift; no route over 250 KB
**Plans**: 2 plans (Wave 0 tests-first + Wave 1 implementation)

Plans:
- [x] 17-01-PLAN.md — Wave 0 tests-first: NEW e2e/page-transitions.spec.ts (UX-D-06-01) + EXTEND e2e/reduced-motion.spec.ts with VT-pseudo-element suppression (UX-D-06-02); both RED
- [x] 17-02-PLAN.md — Wave 1: globals.css VT cross-fade + explicit reduced-motion suppressor (corrects D-06) + Firefox fallback, (authed)/template.tsx pathname-keyed trigger, RED→GREEN + 250 KB budget, human-verify checkpoint (UX-D-06-01..05)

### Phase 18: Tickets kanban board
**Goal**: Replace the board-view placeholder with a real, keyboard-accessible status kanban backed by a persisting mutation.
**Depends on**: Phase 16
**Requirements**: UX-D-01-01, UX-D-01-02, UX-D-01-03, UX-D-01-04, UX-D-01-05, UX-D-01-06
**Success Criteria** (what must be TRUE):
  1. The board renders four status columns populated from `useTickets`; the list/board URL toggle is preserved
  2. Dragging a ticket to another column (pointer or keyboard, via @dnd-kit) persists its status with optimistic update and rolls back on error
  3. Empty columns show the canonical empty-state; the status chip filter still applies
  4. At <768px the board degrades cleanly without regressing the fixed bottom-nav; the route stays ≤250 KB and passes axe in both themes
**Plans**: 5 plans (Waves 0-3)

Plans:
- [x] 18-00-PLAN.md — Wave 0: install @dnd-kit/core + pure bucketTickets() (+tests) + useMarkBlocked optimistic list-cache-key fix (Pitfall 1) +guard
- [x] 18-01-PLAN.md — Wave 0: RED test scaffolds (NEW e2e/tickets-kanban.spec.ts + kanban-reason-prompt.test.tsx; EXTEND a11y-routes both-themes + reduced-motion to board view)
- [x] 18-02-PLAN.md — Wave 1: kanban leaf components (shared severity-glyph module, draggable KanbanCard, droppable KanbanColumn, KanbanReasonPrompt)
- [x] 18-03-PLAN.md — Wave 2: DndContext board container (sensors, onDragEnd block/unblock gating, DragOverlay reduced-motion, a11y announcements, mobile scroll-snap) + page.tsx next/dynamic wiring
- [ ] 18-04-PLAN.md — Wave 3: full gate run w/ pasted evidence (bundle 250KB + axe both themes + board e2e + reduced-motion) + human-verify touch/DrillPanel checkpoint

### Phase 19: Add-connector wizard
**Goal**: Replace the single-step connector form with a guided four-step wizard, reusing existing endpoints.
**Depends on**: Phase 16
**Requirements**: UX-D-02-01, UX-D-02-02, UX-D-02-03, UX-D-02-04, UX-D-02-05, UX-D-02-06
**Success Criteria** (what must be TRUE):
  1. Adding a connector runs provider pick → credentials → test → confirm, with step navigation gated on a successful connection test
  2. The credentials step preserves the sentinel-passthrough (untouched secrets not resent); the confirm step shows required scopes before submit
  3. The wizard reuses `POST /connectors/test` and `POST /connectors` (no new backend) and works in the ResponsiveDialog/vaul mobile pattern
  4. The connectors route passes axe in both themes and stays ≤250 KB
**Plans**: TBD

## Progress

**Execution Order:**
v1.0 Phase 1 shipped. v1.0 Phases 2–8 are deferred. v2.0 phases execute in numeric order 9 → 10 → 11 → 12 → 13 → 14 → 15. Phases 10–14 each depend on the prior phase's primitives / patterns; Phase 15 is the closing gate and depends on Phase 14.

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Multi-Replica State | v1.0 Production Readiness | 4/4 | Complete | 2026-05-09 |
| 2. CI Gating | v1.0 Production Readiness | 2/2 | Complete | 2026-07-01 |
| 3. Update Path Reconciliation | v1.0 Production Readiness | 2/2 | Complete | 2026-07-02 |
| 4. Doc/Code Parity | v1.0 Production Readiness | 0/3 | Planned | - |
| 5. Encryption Key Lifecycle | v1.0 Production Readiness | 0/2 | Deferred | - |
| 6. Default Admin Hardening | v1.0 Production Readiness | 4/4 | Complete | 2026-07-09 |
| 7. Health and Observability | v1.0 Production Readiness | 3/3 | Complete | 2026-07-10 |
| 8. Test Coverage Floor | v1.0 Production Readiness | 0/3 | Deferred | - |
| 9. `/login` + Foundation | v2.0 UI/UX Redesign | 6/6 | Complete | 2026-05-13 |
| 10. `/dashboard` | v2.0 UI/UX Redesign | 6/6 | Complete    | 2026-05-18 |
| 11. `/vulnerabilities` + State Patterns | v2.0 UI/UX Redesign | 8/8 | Complete    | 2026-05-27 |
| 12. `/assets` List + Detail | v2.0 UI/UX Redesign | 8/8 | Complete    | 2026-06-01 |
| 13. `/tickets` List + Detail | v2.0 UI/UX Redesign | 9/9 | Complete    | 2026-06-02 |
| 14. Remaining Screens | v2.0 UI/UX Redesign | 6/6 | Complete    | 2026-06-03 |
| 15. Mobile + a11y + Perf Quality Gate | v2.0 UI/UX Redesign | 6/6 | Complete   | 2026-06-29 |

---
*Roadmap created: 2026-05-08 from audit findings. v2.0 UI/UX Redesign section added 2026-05-12 from sketch findings.*
