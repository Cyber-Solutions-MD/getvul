# Requirements: GetVul

**Defined:** 2026-05-08
**Core Value:** A vuln-triage analyst can open one dashboard, see the same CVE-on-host correlated across multiple scanners, identify the asset's owner from IdP/MDM/HR, and ship a Jira/Asana ticket — without ever opening a scanner console.

## Active Milestone — Production-Readiness Blockers

Each requirement maps to one phase in [ROADMAP.md](ROADMAP.md). Sourced from the 2026-05-08 codebase audit (§5 blockers and §8 next steps).

### Multi-Replica State (PROD-01)

- [ ] **PROD-01-01**: OIDC state parameter store moves from `_pending_states` dict to Redis with TTL (≤10 min) — covers [backend/app/auth/router.py:31](backend/app/auth/router.py#L31)
- [ ] **PROD-01-02**: Per-tenant rate limiter moves from `_rate_limit_store` defaultdict to Redis sorted-set or fixed-window counter — covers [backend/app/main.py:103](backend/app/main.py#L103) and [doc/security.md:20](doc/security.md#L20) drift
- [ ] **PROD-01-03**: Both implementations have integration tests proving correctness across two backend processes hitting one Redis

### CI Gating (PROD-02)

- [x] **PROD-02-01**: `.github/workflows/ci.yml` push and pull_request triggers re-enabled — covers [.github/workflows/ci.yml:3-8](.github/workflows/ci.yml#L3-L8)
- [x] **PROD-02-02**: Remove `|| true` from mypy, frontend lint, frontend typecheck steps so failures block the workflow (mypy via committed baseline gate)
- [x] **PROD-02-03**: ZAP scan steps run as a non-blocking advisory job (continue-on-error), gated off PRs onto post-merge + nightly schedule
- [x] **PROD-02-04**: Branch-protection on `main` requires CI green (applied live, empirically proven, documented in docs/13-deployment.md)

### Update Path Reconciliation (PROD-03)

- [ ] **PROD-03-01**: One canonical update mechanism chosen (GH-Actions release CD **or** hourly cron — not both) — covers [install.sh:97-109](install.sh#L97-L109) and [.github/workflows/cd.yml:32-64](.github/workflows/cd.yml#L32-L64)
- [ ] **PROD-03-02**: `install.sh` no longer registers a competing cron when GH-Actions CD is used (or vice versa, by config flag)
- [ ] **PROD-03-03**: CD flow uses `git fetch && git checkout <tag>` against a release tag, not `git reset --hard origin/main`
- [ ] **PROD-03-04**: Rollback procedure documented in [doc/deployment.md](doc/deployment.md)

### Doc/Code Parity (PROD-04)

- [ ] **PROD-04-01**: Backend security middleware emits `Content-Security-Policy` and `Cross-Origin-Opener-Policy` headers — covers [doc/security.md:31](doc/security.md#L31) drift
- [ ] **PROD-04-02**: Top-level [README.md](README.md) updated to reflect 6 scanner sources (CrowdStrike, Nessus, Defender, Wiz, Qualys, Rapid7), matching [doc/overview.md:10](doc/overview.md#L10)
- [ ] **PROD-04-03**: `VulnSource` enum extended to include `QUALYS` and `RAPID7` — [backend/app/vulnerabilities/models.py:31](backend/app/vulnerabilities/models.py#L31); migration + backfill if needed
- [ ] **PROD-04-04**: Verify Qualys/Rapid7 vulns persist and surface in dashboard filters (regression test)
- [ ] **PROD-04-05**: Either implement Secrets Manager support OR remove `aws_region` / `secrets_manager_prefix` config + `boto3` dep — pick one in discuss-phase

### Encryption Key Lifecycle (PROD-05)

- [ ] **PROD-05-01**: Documented backup procedure for `ENCRYPTION_KEY` (where it lives, who restores it, RTO)
- [ ] **PROD-05-02**: Key rotation runbook — generate new key, re-encrypt all connector credentials in a transaction, verify decrypt round-trip
- [ ] **PROD-05-03**: Optional CLI command (`python -m app.encryption rotate`) implementing the rotation
- [ ] **PROD-05-04**: Operator alert if `.env` is missing or contains a placeholder `ENCRYPTION_KEY`

### Default Admin Hardening (PROD-06)

- [ ] **PROD-06-01**: New users with the `OWNER` role created by `create_admin.py` are flagged `must_change_password` on first login
- [ ] **PROD-06-02**: Auth flow enforces password change before any non-`/auth/change-password` call succeeds when flag is set
- [ ] **PROD-06-03**: Login UI surfaces a forced-rotation banner and routes to change-password
- [ ] **PROD-06-04**: Audit event recorded on first-login rotation (`auth.first_login_rotation`)

### Health and Observability (PROD-07)

- [ ] **PROD-07-01**: `GET /health` becomes a liveness probe (no dependencies)
- [ ] **PROD-07-02**: `GET /ready` is a readiness probe checking Postgres connectivity + Redis ping with bounded timeout
- [ ] **PROD-07-03**: Nginx upstream health check uses `/ready` (not `/health`) so a sick backend de-registers
- [ ] **PROD-07-04**: structlog output is JSON in production (`ENVIRONMENT=production`); env-gated

### Test Coverage (PROD-08)

- [ ] **PROD-08-01**: At least one happy-path test per implemented connector under `backend/tests/test_connectors/` (mocked HTTP, no live API)
- [ ] **PROD-08-02**: Ticket rule engine has tests for: rule fires on schedule, daily-cap enforced, dedup against existing tickets
- [ ] **PROD-08-03**: SLA breach detection has tests for: due-date computation per severity, breach state transition, at-risk window
- [ ] **PROD-08-04**: Tenant-isolation regression test for newly added endpoints (search, notifications, reports)

## Future (Out of Current Milestone)

These are tracked but **not** in scope for the production-readiness milestone. Promote with `/gsd-add-backlog`.

### Horizontal Scale (v1.1+)

- **SCALE-01**: Background scheduler extracted to a separate worker process / dedicated container
- **SCALE-02**: Postgres connection pooler (PgBouncer) for the multi-replica case
- **SCALE-03**: Stateless backend behind a load balancer

### SaaS Multi-Tenancy (v2+)

- **SAAS-01**: Tenant onboarding API + signup self-service
- **SAAS-02**: Per-tenant resource quotas and billing hooks
- **SAAS-03**: Tenant-level audit-log retention policies

### Connector Coverage (v1.x)

- **CONN-01**: Tenable.io / Tenable.sc support beyond on-prem Nessus
- **CONN-02**: GitHub Dependabot / GHAS as a vuln source
- **CONN-03**: ServiceNow as a ticketing target

## Out of Scope

| Feature | Reason |
|---------|--------|
| Multi-region active-active | Single-VM deploy is the explicit topology; would invalidate the entire scheduler model |
| Self-scanning (running our own CVE scans) | GetVul orchestrates *other* scanners by design |
| Native mobile apps | Mobile-responsive web is sufficient |
| Real-time websocket push | Polling sufficient at current data volumes |
| Multiple customer orgs in one deploy | Single-process scheduler + in-memory state make this unsafe; one VM per customer |
| Replacing existing SIEM | We forward audit events via CEF; we don't compete with Splunk/Sentinel |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| PROD-01-01 | Phase 1 | Pending |
| PROD-01-02 | Phase 1 | Pending |
| PROD-01-03 | Phase 1 | Pending |
| PROD-02-01 | Phase 2 | Complete |
| PROD-02-02 | Phase 2 | Complete |
| PROD-02-03 | Phase 2 | Complete |
| PROD-02-04 | Phase 2 | Complete |
| PROD-03-01 | Phase 3 | Pending |
| PROD-03-02 | Phase 3 | Pending |
| PROD-03-03 | Phase 3 | Pending |
| PROD-03-04 | Phase 3 | Pending |
| PROD-04-01 | Phase 4 | Pending |
| PROD-04-02 | Phase 4 | Pending |
| PROD-04-03 | Phase 4 | Pending |
| PROD-04-04 | Phase 4 | Pending |
| PROD-04-05 | Phase 4 | Pending |
| PROD-05-01 | Phase 5 | Pending |
| PROD-05-02 | Phase 5 | Pending |
| PROD-05-03 | Phase 5 | Pending |
| PROD-05-04 | Phase 5 | Pending |
| PROD-06-01 | Phase 6 | Pending |
| PROD-06-02 | Phase 6 | Pending |
| PROD-06-03 | Phase 6 | Pending |
| PROD-06-04 | Phase 6 | Pending |
| PROD-07-01 | Phase 7 | Pending |
| PROD-07-02 | Phase 7 | Pending |
| PROD-07-03 | Phase 7 | Pending |
| PROD-07-04 | Phase 7 | Pending |
| PROD-08-01 | Phase 8 | Pending |
| PROD-08-02 | Phase 8 | Pending |
| PROD-08-03 | Phase 8 | Pending |
| PROD-08-04 | Phase 8 | Pending |

**Coverage:**
- Active milestone requirements: 32 total
- Mapped to phases: 32
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-08*
*Last updated: 2026-05-08 after initial definition from audit*
