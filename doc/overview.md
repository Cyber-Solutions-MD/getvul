# GetVul — Project Overview

## What is GetVul?

GetVul is a **unified vulnerability aggregation platform** that collects vulnerability and cloud security data from multiple enterprise security tools, normalizes it into a single database, enriches it with HR/MDM data, and enables teams to take action through automated ticketing and remediation workflows.

## Key Features

### Vulnerability Management
- Aggregate vulnerabilities from CrowdStrike Spotlight (+ Nessus, Defender, Wiz planned)
- Normalize into common schema with CVE, severity, CVSS, exploit status, CISA KEV
- Cross-source correlation (same CVE detected by multiple scanners)
- Computed risk scores per asset (piecewise log curve based on severity/exploit/KEV)
- File path detection showing where vulnerable software is installed
- Remediation grouping with ignore/restore capability
- Saved search filters with automation rule creation

### Asset Intelligence
- Automatic device classification (workstation, server, network, mobile)
- CrowdStrike enrichment: serial number, last login user, host status, model, file paths
- Jamf Pro MDM enrichment: FileVault, SIP, Gatekeeper, building, department
- Humaans HR enrichment: full name, email, GitHub, LinkedIn, Element handles, teams
- Per-asset vulnerability impact summary with risk scoring

### Users Dashboard
- Merged view of CrowdStrike devices + Humaans HR data
- User search with device details, vuln counts, risk scores
- Groups tab (synced from Google Workspace or Azure Entra ID)
- Expandable rows showing all devices per user

### Ticketing & Automation
- Asana integration: create/close/comment/delete tasks
- Per-host tickets (all remediations for one host)
- Per-remediation tickets (all affected hosts for one fix)
- Automation rules with saved filter conditions
- Configurable schedule (1h to 7 days), max ticket limits
- Auto-assignment via Humaans email
- SLA-based due dates (CRITICAL=3d, HIGH=14d, MEDIUM=30d, LOW=90d)
- Bulk actions: close, comment, sync status, delete
- Bidirectional sync: task completion in Asana → vuln remediated in GetVul

### Authentication & Access Control
- Email/password login with bcrypt hashing
- SSO framework: Google Workspace + Azure Entra ID
- SSO enforcement (requires configured IdP connector)
- Configurable password policy (length, complexity, history)
- RBAC: Owner > Admin > Analyst > Viewer
- Per-user password login override when SSO enforced
- JWT access tokens (15 min) + refresh tokens (7 days)
- Auto-refresh on expiry with login redirect

### Settings & Administration
- Editable org config (name, domain, slug, timezone, IdP)
- User management (add from HR directory, edit, roles, delete, deactivate)
- TLS/SSL certificate management (upload custom or generate self-signed)
- Audit logging with syslog/SIEM forwarding (CEF format)
- Password policy configuration

### Export & Reporting
- CSV export on every table (vulnerabilities, assets, users, tickets, remediations)
- Executive Report builder with configurable sections and filters
- PDF, CSV, and TXT output formats
- Filter by severity, device type, exploit/KEV, min risk, top N count

### Enhanced Dashboard
- Vulnerability overview (total, open, critical, exploitable, KEV)
- Asset risk distribution with breakdown by type
- Top 10 riskiest hosts (clickable)
- Connector health monitoring
- Ticket status (open, resolved, overdue)
- Executive Report builder tab

## Supported Integrations

| Connector | Type | Status | Data |
|-----------|------|--------|------|
| CrowdStrike Falcon | Vulnerability scanner | Implemented | Vulns, devices, file paths, CSPM |
| Jamf Pro | Apple MDM | Implemented | Device security, user assignments |
| Humaans | HR platform | Implemented | Names, emails, GitHub/LinkedIn/Element, teams |
| Asana | Ticketing | Implemented | Create/manage vulnerability tickets |
| Google Workspace | SSO directory | Implemented | Users, groups |
| Azure Entra ID | SSO directory | Implemented | Users, groups |
| Nessus Professional | Vulnerability scanner | Planned | Scan results |
| Microsoft Defender | Endpoint security | Planned | Machines, vulns |
| Wiz | Cloud security | Planned | Cloud vulns, CSPM |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15, React 19, TypeScript, Tailwind CSS |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 (async) |
| Database | PostgreSQL 16 |
| Cache | Redis 7 |
| Reverse Proxy | Nginx with TLS termination |
| Auth | JWT + bcrypt + OIDC (Google/Azure) |
| Containers | Docker + Docker Compose |
| IaC | Terraform (AWS, planned) |
