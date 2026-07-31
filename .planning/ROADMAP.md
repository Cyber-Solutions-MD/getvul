# Roadmap: GetVul

## Overview

GetVul shipped its v0.1 feature set (vuln aggregation, correlation, ticketing, SLA, CSPM, notifications, reports). Its first GSD milestone is **v1.0 Production Readiness** — closing the blockers identified in the 2026-05-08 audit so a real customer can run this beyond the demo VM. Phase 1 (Multi-Replica State) shipped 2026-05-09; phases 2–8 are deferred while **v2.0 UI/UX Redesign** takes precedence. v2.0 rebuilds every authenticated screen against the validated Wiz-inspired sunset-palette design system (43 design decisions from 6 sketches, captured in `.claude/skills/sketch-findings-getvul/`). v2.0 ships as **vertical-slice phases**: each phase delivers one fully redesigned screen end-to-end (tokens + primitives + page wired to real backend + a11y + tests). Foundation requirements (UX-F-01..F-04) are embedded inside Phase 9 (the `/login` slice) — there is no foundation-only phase, by deliberate design. v1.0 phases 2–8 do not share files with the frontend rebuild and can resume in parallel or sequentially as a future v1.1 milestone. **v3.0 AI-Assisted Triage ("Triage Copilot")** is the current milestone: it adds a BYOK (bring-your-own-key, tenant-supplied Anthropic key only) LLM-assistance layer — grounded in the tenant's own correlated data, guardrailed against prompt injection/PII leakage/cost blowup, and gated by evals — so an analyst gets help *deciding and act*ing, not just seeing. It continues phase numbering from 22 (Phases 23–28).

## Milestones

- ✅ **v1.0 Production Readiness** — Phases 1–8 (all complete 2026-07-14)
- ✅ **v2.0 UI/UX Redesign** — Phases 9–15 (SHIPPED 2026-06-30) — archived: [milestones/v2.0-ROADMAP.md](milestones/v2.0-ROADMAP.md)
- ✅ **v2.1 Polish & Tech Debt** — BL-01..05 (SHIPPED 2026-07-15; no new phases — backlog cleanup) — see [MILESTONES.md](MILESTONES.md)
- ✅ **v2.2 Deferred UI Features** — Phases 16–22 (SHIPPED 2026-07-22; gap-closure phases 20–22 added 2026-07-20 from v2.2-MILESTONE-AUDIT) — archived: [milestones/v2.2-ROADMAP.md](milestones/v2.2-ROADMAP.md)
- 🚧 **v3.0 AI-Assisted Triage ("Triage Copilot")** — Phases 23–28 (IN PROGRESS, opened 2026-07-25) — BYOK LLM assistance: ingestion-reliability precursor, "Explain this vuln," remediation guidance, prioritization narrative, ticket auto-drafting, eval/cost/observability gate

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

**v2.2 Deferred UI Features (SHIPPED 2026-07-22 — Phases 16–22):** full detail archived in [milestones/v2.2-ROADMAP.md](milestones/v2.2-ROADMAP.md).

- [x] **Phase 16: Light-theme visual completion** — per-route light-mode QA + axe AA in both themes (UX-D-03) (executed 2026-07-15; gap-closure 16-03 + WR-04 systemic on-soft migration 2026-07-16; verification passed 4/4 SC, live axe sweep green in both themes — see 16-VERIFICATION.md) (completed 2026-07-16 — but see Phase 20: the live gate found `text-severity-high` still red at HEAD)
- [x] **Phase 17: Page-transition motion** — View Transitions API cross-fade, reduced-motion-safe (UX-D-06) (completed 2026-07-16 — but formally unverified; see Phase 21)
- [x] **Phase 18: Tickets kanban board** — @dnd-kit status columns replacing the placeholder (UX-D-01) (completed 2026-07-17)
- [x] **Phase 19: Add-connector wizard** — 4-step provider → credentials → test → confirm (UX-D-02) (completed 2026-07-20)
- [x] **Phase 20: Light-theme severity-high AA fix** — GAP CLOSURE: `-on-soft` variant for `--color-severity-high` across ~15 sites + live axe sweep green (UX-D-03-02/-03/-05) (added 2026-07-20) (completed 2026-07-21)
- [x] **Phase 21: Page-transition verification** — GAP CLOSURE: real DrillPanel-during-VT test + persisted human-UAT + 17-VERIFICATION.md (UX-D-06-01/-03/-04) (added 2026-07-20) (completed 2026-07-21)
- [x] **Phase 22: Kanban + wizard test-coverage hardening** — GAP CLOSURE (warnings): Enter-key-drag + gated-drop SR test; wizard axe sweep extended to Test + Confirm steps (UX-D-01-02, UX-D-02-06 coverage) (added 2026-07-20) (completed 2026-07-22)

**v3.0 AI-Assisted Triage ("Triage Copilot") (IN PROGRESS, opened 2026-07-25 — Phases 23–28):**

- [ ] **Phase 23: Ingestion Reliability Precursor** — Fix Wiz/Rapid7 connector wiring, add scanner HTTP-layer integration tests, wire Jira ticket-create, finish-or-retire GitHub ticketing, surface per-connector sync health
- [x] **Phase 24: AI Foundation + "Explain This Vuln"** — BYOK key config, grounding/cache/client/guardrail/cost scaffold, streamed plain-English + business-risk summary in the drill panel (completed 2026-07-29 — 10/10 plans; 9 original + gap-closure 24-10 closing the D-23 no-key role-gating gap; re-verification passed 12/14 with 4 live-verification items accepted as tracked debt per the 24-06 proceed-on-trust decision — see 24-UAT.md / close via /gsd-verify-work 24)
- [x] **Phase 25: Asset-Aware Remediation Guidance** — OS/package-aware remediation citing the scanner's own solution text, cite-or-refuse, populates ticket-draft description (completed 2026-07-30)
- [ ] **Phase 26: Prioritization Narrative** — "What to fix first and why" narrative augmenting (never replacing) the deterministic risk score, generated in bulk via the Message Batches API
- [ ] **Phase 27: Ticket Auto-Drafting** — AI-drafted title/description/remediation/asset-context pre-fills the existing Jira/Asana create flow; analyst edits and ships
- [ ] **Phase 28: Eval + Cost + Observability Gate** — DeepEval CI harness, promptfoo red-team CI job, fail-closed per-tenant cost circuit breaker, admin usage/settings UI

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

## ✅ v2.2 Deferred UI Features — SHIPPED 2026-07-22

Phases 16–22 finished the four features deferred out of v2.0, each holding the phase-15 quality gate (axe WCAG 2.1 AA in **both** themes, reduced-motion, ≤250 KB First-Load JS/route) and the `sketch-findings-getvul` design contract. Phases 16–19 shipped the features (light-theme completion UX-D-03, page-transition motion UX-D-06, tickets kanban UX-D-01, add-connector wizard UX-D-02); the 2026-07-20 audit found three verification gaps, which gap-closure Phases 20–22 closed. Locked decisions: native View Transitions API (0 KB motion) + @dnd-kit (board). Audit: `passed` (22/22 UX-D requirements, 9/9 integration seams, 5/5 flows).

**Full phase detail + success criteria + plans:** [milestones/v2.2-ROADMAP.md](milestones/v2.2-ROADMAP.md) · **Requirements:** [milestones/v2.2-REQUIREMENTS.md](milestones/v2.2-REQUIREMENTS.md) · **Audit:** [milestones/v2.2-MILESTONE-AUDIT.md](milestones/v2.2-MILESTONE-AUDIT.md) · **Summary:** [MILESTONES.md](MILESTONES.md)

## 🚧 v3.0 AI-Assisted Triage ("Triage Copilot") — IN PROGRESS (opened 2026-07-25 — Phases 23–28)

**Foundational principle (applies to every phase below): BYOK.** All AI functionality is client-provided-key only — each tenant supplies their own Anthropic API key; there is no GetVul-owned/shared/fallback key and no GetVul-proxied inference. AI features stay inert (graceful "configure AI" state, never an error) for a tenant until they configure their own key. Other hard constraints threaded through every phase: caching is tenant-scoped only (no cross-tenant serving), the deterministic risk score (ASSET-02) is augmented/explained but never replaced, prompt-injection defense is first-class (untrusted scanner text is delivered as data, never instructions), and the cost guardrail fails closed. See `.planning/research/SUMMARY.md` and `.planning/research/PITFALLS.md` for full rationale.

### Phase 23: Ingestion Reliability Precursor

**Goal**: Analysts can rely on every scanner connector actually syncing, every ticketing path actually working, and can see per-connector health at a glance — the grounding data every later AI phase depends on is trustworthy.
**Depends on**: Nothing (independent connector/ticketing fixes; first phase of the milestone)
**Requirements**: REL-01, REL-02, REL-03, REL-04, REL-05, REL-06
**Success Criteria** (what must be TRUE):

  1. Wiz and Rapid7 connectors each complete a full sync end-to-end (the `authenticate()` return-type wiring bug and the no-arg instantiation `TypeError` are both fixed) — REL-01, REL-02
  2. All six scanner connectors (CrowdStrike, Nessus, Defender, Wiz, Qualys, Rapid7) have HTTP-layer integration tests covering auth, pagination, and `fetch_vulnerabilities` mapping against a mocked transport — REL-03
  3. An analyst can create a Jira ticket directly from a vulnerability, not just receive status-sync updates for tickets created elsewhere — REL-04
  4. GitHub ticketing works end-to-end (create + sync) or is explicitly retired with no dead stub referenced anywhere in the codebase — REL-05
  5. The Connectors UI shows each connector's last sync time, last error, and status — REL-06

**Plans**: 11/11 plans executed

Plans:

- [x] 23-01-PLAN.md — Connector sync bug fixes (Wiz REL-01, Rapid7 REL-02) + verify_tls TLS hardening across 4 sites
- [x] 23-02-PLAN.md — HTTP-layer integration tests for CrowdStrike, Defender, Nessus, Qualys (REL-03)
- [x] 23-03-PLAN.md — Ticketing provider enum + dispatch Protocol/adapters + JiraClient consolidation + GitHub client methods (REL-04/05 contracts)
- [x] 23-04-PLAN.md — Provider dispatch wiring (service + rule engine + router) + tenant-scoped configured-providers endpoint (REL-04/05)
- [x] 23-05-PLAN.md — GitHub connector registration (4 backend points) + daily_sync GitHub branch + auto-close (REL-05)
- [x] 23-06-PLAN.md — Health prerequisites: migration 030 + model/schema columns + status-mapping fix (SyncStatusPill crash) (REL-06)
- [x] 23-07-PLAN.md — Sync-harness failure counter + redacted/truncated last_error capture + scheduler parity (REL-06)
- [x] 23-08-PLAN.md — Drill-panel provider picker create UX + configured-providers query hook (REL-04)
- [x] 23-09-PLAN.md — Connector-card health surface: inline last-error, next-sync, consecutive-failure count (REL-06)
- [x] 23-10-PLAN.md — Gap closure (CR-03, REL-06): sanitize SyncLog.error_message + scheduler-log secret-leak regression test
- [x] 23-11-PLAN.md — Gap closure (CR-01, REL-04): wire TicketProviderPicker into mobile drill-panel confirm + gated-provider regression test

**UI hint**: yes

### Phase 24: AI Foundation + "Explain This Vuln"

**Goal**: A tenant admin can turn AI on with their own key, and an analyst gets a grounded, safely-guardrailed, streamed plain-English explanation of any vulnerability — proving the full integration risk (streaming, encrypted per-tenant config, guardrails) end-to-end at minimum blast radius before it's multiplied across four more capabilities.
**Depends on**: Phase 23 (AI is only as good as its grounding data; also reuses the now-complete Jira/GitHub ticketing paths)
**Requirements**: AI-01, AI-02, AI-03, AI-04, AI-05, AI-06
**Success Criteria** (what must be TRUE):

  1. A tenant admin can configure their own Anthropic API key and model preferences, encrypted at rest via the existing Fernet/`ConnectorConfig` pattern; every AI feature stays in a graceful "configure AI" UI state until that key is set — no shared or fallback key exists anywhere in the system — AI-01
  2. Opening a vulnerability's drill panel and clicking "Explain this vuln" streams a plain-English summary + business-risk framing into the panel token-by-token — AI-03, AI-04
  3. The summary visibly distinguishes verbatim scanner-sourced text from AI-interpreted framing (two-tier citation) — AI-04
  4. Untrusted scanner text (CVE descriptions, hostnames, finding titles) — including adversarially crafted text — is delivered to the model only as data (never as instructions), and every model response is schema-validated before it reaches the UI — AI-02
  5. Every AI call, including scheduler-originated ones, is audit-logged with model/tokens/cost-estimate/prompt provenance, and AI output cached for one tenant is never served to another tenant — AI-05, AI-06

**Plans**: 10 executed (9 original + 1 gap-closure, 24-10)

Plans:
**Wave 1**

- [x] 24-01-PLAN.md — Foundations: anthropic dep + incremental-SSE spike (nginx) + ANTHROPIC connector type (wizard reuse, zero migration)
- [x] 24-02-PLAN.md — Backend contracts (TDD): response schemas (validation gate) + untrusted-content-as-data prompt builder + AI audit writer

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 24-03-PLAN.md — Data wiring (TDD): BYOK key resolution + tenant-scoped cache (cross-tenant isolation) + fail-closed budget + audit_logs index migration

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 24-04-PLAN.md — TRACER engine (TDD): buffer-validate-replay SSE core + per-vuln explain endpoint (RBAC, retry-once, no-key inert)

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 24-05-PLAN.md — TRACER frontend (TDD): fetch+ReadableStream hook + drill-panel AI Explanation section (8 states) + inline two-tier citations

**Wave 5** *(blocked on Wave 4 completion)*

- [x] 24-06-PLAN.md — TRACER gate: human-verify end-to-end through nginx/Docker + checkpoint:decision on per-remediation grounding shape

**Wave 6** *(blocked on Wave 5 completion)*

- [x] 24-07-PLAN.md — Feedback capture (TDD): ai_feedback table + editable per-user upsert endpoint + thumbs/note control (capture-only)

**Wave 7** *(blocked on Wave 6 completion)*

- [x] 24-08-PLAN.md — Expansion backend (TDD): host + remediation schema variants + PII-excluding prompt builders + grounding assemblers + thin routes

**Wave 8** *(blocked on Wave 7 completion)*

- [x] 24-09-PLAN.md — Expansion frontend (TDD): generalize the AI Explanation section + mount on host (asset-detail) and remediation surfaces (D-15 complete)

**Wave 9 — gap closure** *(closes verification truth #2: D-23 no-key role-gating)*

- [x] 24-10-PLAN.md — Gap closure: require_viewer GET /api/v1/ai/status boolean signal + useAiStatus hook replacing the isError optimistic guess, so the no-key state is correctly role-gated for Analyst/Viewer (AI-01)

**UI hint**: yes
**Pitfalls owned** (see research/PITFALLS.md): #1 prompt injection (headline threat — untrusted-content-as-data contract established here for reuse by every later phase), #3 PII/secret leakage (prompt-builder field allowlist), #4 cross-tenant cache/prompt bleed, #6 non-determinism breaking CI (schema/property-test convention established here), #9 drill-panel latency regression (Suspense-bounded async region).

### Phase 25: Asset-Aware Remediation Guidance

**Goal**: An analyst gets remediation guidance grounded strictly in the scanner's own solution text plus asset facts — never a fabricated fix — and can carry it straight into a draft ticket.
**Depends on**: Phase 24 (reuses the grounding/cache/client/guardrail scaffold entirely)
**Requirements**: AIR-01, AIR-02
**Success Criteria** (what must be TRUE):

  1. An analyst can request remediation guidance for a finding and see OS/package-aware steps that cite the scanner's own solution text verbatim before any AI-authored interpretation, surfaced in the drill panel UI — AIR-01
  2. When no vendor remediation guidance exists for a finding, the assistant says so explicitly (cites insufficient evidence) rather than inventing a plausible-sounding fix — AIR-01
  3. An analyst can populate a draft ticket description from the remediation guidance and still review/edit it before anything is created — AIR-02

**Plans**: 5/7 plans executed

- [x] 25-01-PLAN.md — Backend: dangerous-command denylist (safety.py) + refuse predicate + tenant-scoped/PII-excluding grounding query [wave 1]
- [x] 25-02-PLAN.md — Backend: remediation-guidance schema variant + allowlist/prompt-builder quadruplet [wave 2]
- [x] 25-03-PLAN.md — Backend: engine dangerous_pattern_check param (before set_cached) + new explain-remediation-guidance route (D-01 gate + groundable) [wave 3]
- [x] 25-04-PLAN.md — Frontend tracer: unsafe/groundable types + safety-refusal + insufficient-evidence cards + drill-panel section mount [wave 4]
- [x] 25-05-PLAN.md — TRACER GATE (checkpoint): verify the end-to-end per-vuln slice before AIR-02 expansion [wave 5]
- [x] 25-06-PLAN.md — AIR-02 backend: TicketCreateRequest.description field + create_tickets() WYSIWYG override [wave 6]
- [x] 25-07-PLAN.md — AIR-02 frontend: copy-in affordance + description Textarea (desktop ConfirmModal + mobile renderConfirm) [wave 7]

**UI hint**: yes
**Pitfalls owned**: #2 hallucinated/unsafe remediation guidance — enforced via "cite or refuse" as an output-schema contract (not prompt wording) plus a post-generation dangerous-pattern regex (`rm -rf`, `DROP TABLE`, "disable firewall/EDR").

### Phase 26: Prioritization Narrative

**Goal**: An analyst sees a "what to fix first and why" narrative — built from exploit/KEV/owner/SLA factors — that explains and augments the existing deterministic risk score without ever competing with or replacing it, generated cost-efficiently in bulk.
**Depends on**: Phase 24 (reuses the scaffold; first phase to touch the scheduler's batch pre-warm path, sequenced after the request-path phases 24–25 so a known-good single-request reference already exists)
**Requirements**: AIP-01, AIP-02
**Success Criteria** (what must be TRUE):

  1. An analyst can see a "what to fix first and why" narrative for a finding, built from exploit/KEV/owner/SLA factors fed to the model as structured facts, never raw free reasoning — AIP-01
  2. The deterministic risk score (ASSET-02) remains the one sortable/authoritative number in every list and view; there is no independently-sortable AI-generated rank anywhere in the UI — AIP-01
  3. Prioritization narratives for a tenant's backlog are pre-generated in bulk on a schedule via the Message Batches API, dispatched via `asyncio.create_task` (never inline, never stalling a connector-sync tick), using only that tenant's own configured key — AIP-02

**Plans**: 8 plans in 8 waves (strict chain — executes sequentially on main; worktrees auto-disabled)

Plans:
- [x] 26-01-PLAN.md (wave 1) — grounding query `get_prioritization_context()` (owner-PII excluded) + the no-rank `ExplainPrioritizationResponse` schema
- [x] 26-02-PLAN.md (wave 2) — the prioritization prompt-builder quadruplet (allowlist, Allowlisted model, system prompt, few-shot, builder, version hash)
- [x] 26-03-PLAN.md (wave 3) — on-demand `explain-prioritization/{finding_id}` route (POST require_analyst SSE + GET require_viewer cache-check)
- [x] 26-04-PLAN.md (wave 4) — frontend Prioritization drill section + signal-driven queued card + the no-ai-rank CI check
- [x] 26-05-PLAN.md (wave 5) — TRACER GATE: verify the on-demand slice (cited narrative, no AI rank) before batch expansion [checkpoint]
- [x] 26-06-PLAN.md (wave 6) — durable `AiBatchJob` table + migration 033 + the `queued` GET cache-check signal
- [x] 26-07-PLAN.md (wave 7) — batch submitter `batch.py`: D-01 top-N query, budget pre-estimate (50%), Redis factory, submit + single-pass validator
- [ ] 26-08-PLAN.md (wave 8) — scheduler integration: `poll_pending_batches()` + nightly/poll dispatch via `asyncio.create_task` (batch goes live)

**UI hint**: yes
**Pitfalls owned**: #7 over-trusting AI over the deterministic score — "augment, never replace" enforced as a literal output-schema/prompt constraint and a UI constraint (no AI-rank sort control), not just a design intention.

### Phase 27: Ticket Auto-Drafting

**Goal**: An analyst creating a Jira/Asana ticket gets an AI-drafted title/description/remediation/asset-context pre-filled into the existing create flow, edits it, and ships it — a human click always creates the ticket.
**Depends on**: Phase 24, Phase 25 (pure consumer of the explain + remediation outputs; no new backend risk surface, no `Ticket` model changes)
**Requirements**: AID-01
**Success Criteria** (what must be TRUE):

  1. Opening the ticket-create flow for a vulnerability pre-fills the form with an AI-drafted title, description, remediation, and asset context — AID-01
  2. An analyst can edit every drafted field before submission — AID-01
  3. No ticket is ever created without an explicit human click on Create/Submit — the draft never auto-submits — AID-01

**Plans**: TBD
**UI hint**: yes

### Phase 28: Eval + Cost + Observability Gate

**Goal**: The milestone closes with a real, CI-enforced quality gate — evals, red-team injection resistance, a fail-closed cost breaker, and admin-visible usage — seeded from real usage data now that every capability exists.
**Depends on**: Phases 24–27 (golden-set fixtures are seeded from real observed outputs, not purely synthetic cases; the red-team suite runs against real system prompts)
**Requirements**: AIE-01, AIE-02, AIE-03, AIE-04
**Success Criteria** (what must be TRUE):

  1. A DeepEval pytest-native eval suite runs in CI against golden sets seeded from real Phase 24–27 outputs and fails the build when schema/grounding/citation assertions regress (never brittle exact-prose snapshots) — AIE-01
  2. A promptfoo red-team job runs as its own CI check (alongside semgrep/ZAP) and asserts prompt-injection resistance over adversarial scanner text across every AI capability shipped so far — AIE-02
  3. When a tenant exceeds their configured token/cost budget, further AI calls for that tenant halt immediately (fail-closed) and the product degrades to deterministic-score-only — never silently overspending — AIE-03
  4. A tenant admin can view their AI usage and cost, and manage their key/model/budget settings, in the UI — AIE-04

**Plans**: TBD
**UI hint**: yes
**Pitfalls owned**: #5 cost blowup at scale (fail-closed circuit breaker + cheap-model-first routing already established, hard budget enforced here as a release gate), #6 non-determinism (nightly golden-dataset re-run policy), #8 shipping without evals (evals are the arbiter, matching this codebase's "the sweep, not the file list, is the arbiter" discipline).

## Progress

**Execution Order:**
v1.0 Phase 1 shipped. v1.0 Phases 2–8 are deferred. v2.0 phases execute in numeric order 9 → 10 → 11 → 12 → 13 → 14 → 15. Phases 10–14 each depend on the prior phase's primitives / patterns; Phase 15 is the closing gate and depends on Phase 14. v3.0 phases execute in numeric order 23 → 24 → 25 → 26 → 27 → 28: Phase 23 is an independent precursor; Phase 24 concentrates the integration risk and every later phase (25–27) reuses its scaffold; Phase 28 is the milestone-closing gate and depends on 24–27.

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Multi-Replica State | v1.0 Production Readiness | 4/4 | Complete | 2026-05-09 |
| 2. CI Gating | v1.0 Production Readiness | 2/2 | Complete | 2026-07-01 |
| 3. Update Path Reconciliation | v1.0 Production Readiness | 2/2 | Complete | 2026-07-02 |
| 4. Doc/Code Parity | v1.0 Production Readiness | 3/3 | Complete | 2026-07-03 |
| 5. Encryption Key Lifecycle | v1.0 Production Readiness | 3/3 | Complete | 2026-07-08 |
| 6. Default Admin Hardening | v1.0 Production Readiness | 4/4 | Complete | 2026-07-09 |
| 7. Health and Observability | v1.0 Production Readiness | 3/3 | Complete | 2026-07-10 |
| 8. Test Coverage Floor | v1.0 Production Readiness | 3/3 | Complete | 2026-07-14 |
| 9. `/login` + Foundation | v2.0 UI/UX Redesign | 6/6 | Complete | 2026-05-13 |
| 10. `/dashboard` | v2.0 UI/UX Redesign | 6/6 | Complete    | 2026-05-18 |
| 11. `/vulnerabilities` + State Patterns | v2.0 UI/UX Redesign | 8/8 | Complete    | 2026-05-27 |
| 12. `/assets` List + Detail | v2.0 UI/UX Redesign | 8/8 | Complete    | 2026-06-01 |
| 13. `/tickets` List + Detail | v2.0 UI/UX Redesign | 9/9 | Complete    | 2026-06-02 |
| 14. Remaining Screens | v2.0 UI/UX Redesign | 6/6 | Complete    | 2026-06-03 |
| 15. Mobile + a11y + Perf Quality Gate | v2.0 UI/UX Redesign | 6/6 | Complete   | 2026-06-29 |
| 16. Light-theme visual completion | v2.2 Deferred UI Features | 3/3 | Complete | 2026-07-16 |
| 17. Page-transition motion | v2.2 Deferred UI Features | 2/2 | Complete | 2026-07-16 |
| 18. Tickets kanban board | v2.2 Deferred UI Features | 5/5 | Complete | 2026-07-18 |
| 19. Add-connector wizard | v2.2 Deferred UI Features | 5/5 | Complete | 2026-07-20 |
| 20. Light-theme severity-high AA fix | v2.2 Deferred UI Features | 4/4 | Complete | 2026-07-21 |
| 21. Page-transition verification | v2.2 Deferred UI Features | 2/2 | Complete | 2026-07-21 |
| 22. Kanban + wizard test-coverage hardening | v2.2 Deferred UI Features | 2/2 | Complete | 2026-07-22 |
| 23. Ingestion Reliability Precursor | v3.0 AI-Assisted Triage | 11/11 | Complete    | 2026-07-28 |
| 24. AI Foundation + "Explain This Vuln" | v3.0 AI-Assisted Triage | 10/10 | Complete    | 2026-07-29 |
| 25. Asset-Aware Remediation Guidance | v3.0 AI-Assisted Triage | 7/7 | Complete    | 2026-07-30 |
| 26. Prioritization Narrative | v3.0 AI-Assisted Triage | 7/8 | In Progress | - |
| 27. Ticket Auto-Drafting | v3.0 AI-Assisted Triage | 0/? | Not started | - |
| 28. Eval + Cost + Observability Gate | v3.0 AI-Assisted Triage | 0/? | Not started | - |

## Backlog

### Phase 999.1: Re-vendor sunset.css & collapse duplicated on-soft/faint token overrides (BACKLOG)

**Goal:** Re-sync `frontend/src/styles/sunset.css` from the `sketch-findings-getvul` skill source (`references/foundation.md` / `sources/themes/sunset.css`) so the vendored copy carries the newer design tokens directly. Once re-synced, delete the accumulated "retire on re-vendor" override groups in `frontend/src/app/globals.css` — the `--color-text-faint` dark override (~lines 63–73), the `--color-{violet,pink,amber}-on-soft` dark overrides (~lines 84–86), and the `--color-severity-{high,critical}-on-soft` dark no-op overrides added in Phase 20 — collapsing three locations of duplicated tokens back to a single source of truth.
**Requirements:** TBD
**Plans:** 8/9 plans executed

Plans:

- [ ] TBD (promote with /gsd-review-backlog when ready)

_Source: Phase 16 REVIEW IN-02 (advisory Info, no per-phase change needed), reinforced by Phase 20 carrying the same retire-on-resync pattern._

### Phase 999.2: Harden forced-rotation password policy (complexity + history) (BACKLOG)

**Goal:** Replace the ad-hoc default-credential rejection on the forced-rotation endpoint (`backend/app/auth/router.py`) with a real password policy. Phase 06 WR-01 closed the exact-literal and whitespace/case-variant + current-password-reuse bypasses, but near-variants like `Admin1234!` still pass because `DEFAULT_POLICY` has `history_count=0` and all complexity flags `False`. Introduce configurable complexity requirements (length/character-class), a password-history check (`history_count > 0`), and optionally a similarity/edit-distance guard against the known default and the previous password.
**Requirements:** TBD
**Plans:** 0 plans

Plans:

- [ ] TBD (promote with /gsd-review-backlog when ready)

_Source: Phase 06 REVIEW re-review (2026-07-23) WR-01 residual — the fixer flagged full complexity/history policy as follow-up beyond the safe subset it applied._

---
*Roadmap created: 2026-05-08 from audit findings. v2.0 UI/UX Redesign section added 2026-05-12 from sketch findings. v2.2 collapsed to archive 2026-07-22 on milestone completion. v3.0 AI-Assisted Triage section added 2026-07-27 from research/SUMMARY.md's validated 6-phase build order — Phases 23–28, continuing phase numbering from 22; coverage 21/21 v1 requirements mapped.*
