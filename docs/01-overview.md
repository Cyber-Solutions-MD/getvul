# 01 — Overview

## What GetVul is

GetVul is a **unified vulnerability-management platform** for security teams that operate multiple scanners and want one place to triage, correlate, and act on findings.

It aggregates vulnerabilities from up to six enterprise scanners, normalizes them into a common schema, correlates the same CVE across scanners on the same asset, enriches each asset with identity/MDM/HR data, and turns the result into Jira/Asana tickets — manually, in bulk, or via scheduled automation rules.

The whole thing is a single full-stack web app (FastAPI + Next.js + Postgres + Redis + Nginx) packaged as Docker Compose, deployable to one Linux VM via [install.sh](../install.sh).

## The problem it solves

Security teams that operate CrowdStrike, Nessus, Defender, Wiz, Qualys, and Rapid7 typically face four pains:

1. **Duplicate findings.** The same CVE on the same host shows up in 3+ scanner consoles with different severities and IDs.
2. **No remediation path.** Every scanner exports CSV but no scanner knows what *human* owns each affected machine.
3. **No SLA accountability.** Severity-driven deadlines are tracked in spreadsheets that drift.
4. **Manual ticketing.** Triagers paste findings into Jira/Asana by hand.

GetVul addresses all four: normalized cross-source CVEs in one table, IdP/MDM/HR enrichment so every asset has a known owner, configurable per-severity SLAs with breach detection, and one-click or rule-driven Jira/Asana tickets.

## Who uses it

- **Vuln-triage analysts (Analyst role)** — daily CVE review, status updates, ticket creation.
- **Security admins (Admin role)** — connector configuration, automation rules, audit-log review.
- **Security leadership (Owner role)** — settings, SSO/SLA policy, executive PDF reports.
- **Read-only stakeholders (Viewer role)** — dashboards and exports.

The deployment model is one tenant per VM (single-customer install). The schema is multi-tenant for future SaaS use, but the in-process scheduler and on-host secrets currently make multi-org-per-deploy impractical — see the "Out of Scope" list in [.planning/PROJECT.md](../.planning/PROJECT.md).

## Core capabilities

### Vulnerability management
- Aggregation from 6 scanners (CrowdStrike, Nessus, Defender, Wiz, Qualys, Rapid7)
- Cross-source correlation: same `(tenant_id, cve_id, asset_id)` flagged when seen by 2+ sources
- Severity, CVSS v3, EPSS, exploit availability, CISA KEV
- CVE ignore (per CVE) and asset ignore (per host)
- Saved filters with one-click rule creation

### Asset intelligence
- Auto-classification: WORKSTATION, SERVER, NETWORK, MOBILE, OTHER
- Risk scoring with piecewise-log curve, severity weights, exploit + KEV multipliers
- MDM enrichment from Jamf Pro and Microsoft Intune (FileVault, SIP, Gatekeeper, compliance state)
- HR enrichment from Humaans (full name, email, GitHub, LinkedIn, Element handles, teams)
- IdP enrichment from Google Workspace, Azure Entra ID, Okta (groups, avatars, departments)
- CrowdStrike host containment status surfaced in asset detail

### Ticketing and SLAs
- Asana + Jira: per-host or per-remediation tickets, manual or automated
- Daily ticket-status sync — auto-closes external tasks when GetVul vulns are resolved
- Configurable per-severity SLAs (CRITICAL=3d, HIGH=14d, MEDIUM=30d, LOW=90d defaults)
- Breach detection with 72-hour at-risk warnings

### Notifications
Four scheduled alert checks emit notifications and email digests:
1. New critical vulnerabilities (last 2 hours)
2. SLA breach warnings (due within 24 hours)
3. Connector sync failures
4. Risk score spikes (≥20 points day-over-day)

### CSPM
Cloud misconfiguration findings (Wiz, Defender) with CIS / SOC 2 / PCI-DSS / HIPAA compliance scoring and per-resource drill-down.

### Authentication and tenancy
- Email/password with bcrypt + configurable password policy
- Google Workspace + Azure Entra ID OIDC, with optional SSO enforcement and per-user override
- JWT access (15 min) + refresh (7 days) with frontend auto-refresh
- RBAC: Owner > Admin > Analyst > Viewer
- Tenant isolation: every domain table carries `tenant_id`, every query is scoped from JWT
- Per-tenant API rate limiter: 200 req / 60 s (Redis sorted-set sliding window)

### Reporting and audit
- CSV export for vulnerabilities, assets, users, tickets, remediations
- Executive PDF reports (fpdf2) with custom logo, colors, scheduled SMTP delivery
- Full audit log with optional CEF syslog forwarding (Splunk / QRadar / Sentinel / Elastic)

### Global search
Cross-category search bar with `Cmd+K` / `Ctrl+K` shortcut returning vulns, assets, users, tickets, and CSPM findings, scoped to the user's tenant.

### Theming and responsive UI
Dark/light theme with `localStorage` persistence; mobile-responsive sidebar, dropdowns, and grids.

## Status

Active milestone: **v1.0 — Production Readiness** (see [.planning/ROADMAP.md](../.planning/ROADMAP.md)).

| Phase | Topic | State |
|-------|-------|-------|
| 1 | Multi-replica state (OIDC + rate limiter on Redis) | ✓ Complete (2026-05-09) |
| 2 | CI gating (re-enable triggers, drop `\|\| true` masks) | 🚧 Pending |
| 3 | Update path reconciliation (cron vs. CD) | 🚧 Pending |
| 4 | Doc/code parity (CSP/COOP, README scanner count, VulnSource enum) | 🚧 Pending |
| 5 | Encryption-key lifecycle | 🚧 Pending |
| 6 | Default-admin hardening (force first-login rotation) | 🚧 Pending |
| 7 | Health and observability split | 🚧 Pending |
| 8 | Test coverage floor (connector + rule + SLA tests) | 🚧 Pending |

The v0.1 feature set (everything in "Core capabilities" above) is shipped and validated. v1.0 closes the production blockers identified in the 2026-05-08 audit.

## Where to go next

- New to the codebase? → [04-installation.md](04-installation.md)
- Want the big picture? → [02-architecture.md](02-architecture.md)
- Designing a feature? → [08-core-modules.md](08-core-modules.md) and [09-data-model.md](09-data-model.md)
- Debugging a deploy? → [17-troubleshooting.md](17-troubleshooting.md)
