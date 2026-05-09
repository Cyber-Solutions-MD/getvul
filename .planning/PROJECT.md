# GetVul

## What This Is

GetVul is a unified vulnerability management platform that aggregates findings from ~6 enterprise vulnerability scanners (CrowdStrike Spotlight, Nessus, Defender for Endpoint, Wiz, Qualys VMDR, Rapid7 InsightVM), normalizes them into a multi-tenant Postgres database, enriches assets with identity/MDM/HR data (Google/Azure/Okta/Humaans/Jamf/Intune), and lets a security team triage and create Jira/Asana tickets through a Next.js dashboard. It's a single-repo full-stack web app (FastAPI + Next.js 15 + Nginx + Postgres + Redis) packaged as Docker Compose, deployable to a single Linux VM via [install.sh](install.sh).

## Core Value

A vuln-triage analyst can open one dashboard, see the same CVE-on-host correlated across multiple scanners, identify the asset's owner from IdP/MDM/HR, and ship a Jira/Asana ticket — without ever opening a scanner console.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. Inferred from existing code at audit time (2026-05-08). -->

- ✓ **VULN-01**: Aggregate vulnerabilities from CrowdStrike, Nessus, Defender, Wiz — v0.1
- ✓ **VULN-02**: Cross-source CVE correlation per asset — v0.1
- ✓ **VULN-03**: CVE ignore + remediation suppress with audit trail — v0.1
- ✓ **VULN-04**: Per-host and per-remediation drill-down views — v0.1
- ✓ **ASSET-01**: Auto-classify devices (workstation/server/network/mobile/other) — v0.1
- ✓ **ASSET-02**: Risk score per asset (piecewise log curve, severity weights, exploit/KEV multipliers) — v0.1
- ✓ **ASSET-03**: MDM enrichment (Jamf, Intune) and HR enrichment (Humaans) — v0.1
- ✓ **AUTH-01**: Email/password login with bcrypt + configurable password policy — v0.1
- ✓ **AUTH-02**: Google + Azure OIDC SSO with per-tenant enforcement — v0.1
- ✓ **AUTH-03**: JWT access (15m) + refresh (7d) with auto-refresh — v0.1
- ✓ **AUTH-04**: Email-based password reset with single-use token — v0.1
- ✓ **TENANT-01**: All queries scoped by `tenant_id` from JWT — v0.1
- ✓ **RBAC-01**: Owner > Admin > Analyst > Viewer with per-route enforcement — v0.1
- ✓ **TKT-01**: Jira + Asana ticket create/update/close/comment/delete — v0.1
- ✓ **TKT-02**: Saved-filter automation rules with daily ticket-status sync — v0.1
- ✓ **SLA-01**: Per-severity SLA tracking with breach + at-risk detection — v0.1
- ✓ **CSPM-01**: CSPM findings with compliance frameworks, cloud resources, trends — v0.1
- ✓ **NOTIF-01**: In-app notifications with 4 alert categories + SMTP email — v0.1
- ✓ **AUDIT-01**: Full audit log with CEF-format syslog forwarding — v0.1
- ✓ **EXP-01**: CSV exports + PDF/CSV/TXT executive summary with branding — v0.1
- ✓ **EXP-02**: Scheduled reports via SMTP — v0.1
- ✓ **DEPLOY-01**: One-command install.sh on a single VM (Docker + TLS + admin + seed) — v0.1
- ✓ **SEARCH-01**: Global search across vulns, assets, users, tickets, CSPM (Cmd+K) — v0.1

### Active

<!-- Production-readiness milestone scope, derived from audit blockers (§5) and next steps (§8). -->

- [x] **PROD-01**: Multi-replica safe — OIDC state and rate limiter on Redis (Phase 01, 2026-05-09)
- [ ] **PROD-02**: CI gating — push/PR triggers re-enabled, no `|| true` masks
- [ ] **PROD-03**: Single canonical update path — auto-update cron and CD release flow reconciled
- [ ] **PROD-04**: Doc/code parity — CSP/COOP headers shipped, README scanner count, `VulnSource` enum
- [ ] **PROD-05**: Encryption-key backup/rotation story documented and supported
- [ ] **PROD-06**: Default-admin hardening — force password change on first login
- [ ] **PROD-07**: Health endpoint checks DB + Redis connectivity
- [ ] **PROD-08**: Connector and ticket-rule test coverage above zero

### Out of Scope

- **Multi-region HA / Kubernetes deployment** — single-VM topology is the explicit deployment model; HA is a future major version.
- **Scanner-less CVE feeds (NVD/OSV ingest without a scanner)** — GetVul aggregates *scanner output*, not raw vuln intel.
- **Self-scanning capability** — GetVul orchestrates other scanners, it is not one.
- **Per-tenant SaaS (multiple customer orgs in one deploy)** — multi-tenancy exists in the schema but the single-process scheduler and in-memory state make this unsupported in practice; one VM per customer is the model.
- **Real-time websocket dashboards** — polling is sufficient at current scale.
- **Mobile native apps** — web-responsive UI covers mobile use today.

## Context

**Stack at audit time (commit `8cede77`, 2026-05-08):**
- Backend: Python 3.12, FastAPI ≥0.115, SQLAlchemy 2.0 async, Pydantic v2, Alembic 1.14, asyncpg, Redis, bcrypt, Fernet (cryptography), python-jose, fpdf2, structlog
- Frontend: Next.js 15.5, React 19, TypeScript 5.5, Tailwind 3.4, lucide-react, recharts
- Infra: Docker Compose (5 services: nginx, postgres:16, redis:7, backend, frontend); Terraform under `infra/gcp/` (primary), `infra/aws/`, `infra/azure/` (secondary)
- 24 Alembic migrations
- CI: GitHub Actions — backend (ruff/mypy/pytest), frontend (lint/tsc/build), terraform validate, semgrep SAST, OWASP ZAP DAST. **All triggers are currently `workflow_dispatch` only — push/PR commented out.**

**Recent activity themes (last ~30 commits):**
- asyncpg type-handling fixes in seed data and migrations
- install.sh polish — TLS gen, admin user, seed data, hourly auto-update
- CSPM compliance UI alignment with backend
- Frontend hardening: relative API URLs, dark/light theme, mobile responsive, global search

**Known issues to address (from audit §7):**
- `VulnSource` enum at [backend/app/vulnerabilities/models.py:31](backend/app/vulnerabilities/models.py#L31) is stale — only 4 sources, but Qualys/Rapid7 connectors exist.
- ~~OIDC state in `_pending_states` dict~~ — resolved in Phase 01 (Redis SET NX EX 600 + GETDEL, fail-closed 503 on Redis unreachable).
- ~~Rate limiter in `_rate_limit_store` defaultdict~~ — resolved in Phase 01 (Redis sorted-set sliding window via MULTI/EXEC, fail-OPEN; doc/security.md:20 updated to "Redis-backed sliding window").
- Background scheduler runs in-process ([backend/app/connectors/scheduler.py](backend/app/connectors/scheduler.py)) — multiple replicas would double-execute.
- `aws_region` / `secrets_manager_prefix` in config.py — declared, `boto3` in deps, never used.
- CSP/COOP headers documented but not implemented.
- Default admin `admin@getvul.local / Admin123!` created by [install.sh](install.sh); no first-login forced rotation.

## Constraints

- **Tech stack**: Python 3.12 + FastAPI backend, Next.js 15 + React 19 frontend, Postgres 16, Redis 7, Nginx — locked, no language migrations in current milestone.
- **Deployment topology**: Single VM running Docker Compose — HA / multi-replica is explicitly Out of Scope for now, but PROD-01 must remove the *blockers* to multi-replica even if we don't run multi-replica yet.
- **Tenant isolation**: Every domain table includes `tenant_id`; every query scopes by `user.tenant_id` from JWT. No new feature may bypass this.
- **Compatibility**: Existing tenants' encrypted connector credentials must continue to decrypt — no Fernet key rotation without a documented migration.
- **Security**: No regressions to existing tenant isolation, audit logging, or RBAC. New features must register audit events.
- **Operator UX**: One-command install (`install.sh`) must remain functional; any new env var needs a sensible default.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Single-VM Docker Compose deploy | Target customer is one ops team running one instance; HA is non-goal at this stage | ✓ Good |
| In-process background scheduler (no Celery/Arq) | Simpler ops; one container to scale | ⚠️ Revisit — blocks horizontal scale (PROD-01) |
| Fernet symmetric encryption for connector creds | Simple, no KMS dependency, key in `.env` | ⚠️ Revisit — needs documented backup/rotation (PROD-05) |
| Single-VM auto-update via hourly cron + GH-Actions release CD | Two paths added at different times | ⚠️ Revisit — pick one (PROD-03) |
| Multi-tenant schema even though deploys are single-tenant | Future-proofs SaaS option without rework | — Pending |
| Postgres 16 + JSONB for flexible enrichment payloads | Avoids per-vendor side tables | ✓ Good |
| Cross-source correlation via `vulnerability_correlations` table with FK per source | Materialized for fast read queries | ✓ Good |

---
*Last updated: 2026-05-09 after Phase 01 (multi-replica state) completion*
