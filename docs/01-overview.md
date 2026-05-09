# GetVul -- Project Overview

## What is GetVul?

GetVul is a **unified vulnerability management platform** that aggregates vulnerability data from multiple enterprise security scanners, normalizes it into a single database, enriches it with identity/MDM data, and enables teams to act through automated ticketing and remediation workflows.

## Core Features

### Vulnerability Management
- Aggregate vulnerabilities from 6 scanner sources: CrowdStrike Falcon Spotlight, Tenable Nessus, Microsoft Defender for Endpoint, Wiz, Qualys VMDR, Rapid7 InsightVM
- Normalize into a common schema with CVE, severity, CVSS, exploit status, CISA KEV
- Cross-source correlation: same CVE detected by 2+ scanners on the same asset
- Severity-based views with drill-down filtering and device category (asset type) filter
- CVE ignore: exclude specific CVEs from remediations and ticket automation
- Saved search filters with automation rule creation

### Asset Intelligence
- Automatic device classification: WORKSTATION, SERVER, NETWORK, MOBILE, OTHER
- Risk scoring: piecewise log curve (knee at raw=120, score=45) with severity weights, exploit multiplier, and KEV multiplier
- Asset ignore: exclude assets from remediations and ticket automation
- CrowdStrike containment status tracking (normal, contained, etc.) displayed in asset detail
- Scanner enrichment: serial number, last login user, host status, model, file paths
- Jamf Pro MDM enrichment: FileVault, SIP, Gatekeeper, building, department
- Humaans HR enrichment: full name, email, GitHub, LinkedIn, Element handles, teams
- Microsoft Intune enrichment: device compliance, management state
- Per-asset vulnerability impact summary with risk scoring

### Remediation Grouping
- Per-remediation view: all affected hosts for one fix action
- Per-host view: all remediations needed for one asset
- Suppress/unsuppress remediations
- Filters carry through all drill-down levels

### Ticketing and Automation
- Asana + Jira integration: create, update, close, comment, delete tasks
- Per-host tickets (all remediations for one host)
- Per-remediation tickets (all affected hosts for one fix)
- Automation rules: saved filter conditions trigger ticket creation on schedule
- Daily ticket status sync: checks open tickets, posts progress comments, auto-closes when resolved
- Bulk actions: close, comment, sync-update, delete
- SLA-based due dates derived from severity

### SLA Tracking
- Configurable deadlines per severity level
- Breach detection with at-risk alerts (72-hour warning)
- Compliance percentage calculation (within SLA vs total)
- Dashboard widget: breached, at-risk, within SLA, compliance %

### Trend Analytics
- New vs resolved vulnerability timeline
- Severity breakdown over time
- Weekly MTTR (Mean Time to Remediate)
- Risk score history
- Daily metric snapshots for historical data

### Notifications and Alerting
- In-app notification system with bell icon in header showing unread badge
- Alert engine with 4 automated checks running on schedule:
  - New critical vulnerabilities (detected in last 2 hours)
  - SLA breach warnings (due within 24 hours)
  - Connector sync failures
  - Risk score spikes (20+ point increase since previous day)
- Email delivery to Owner and Admin users for critical alerts
- Notification filtering by category and read status
- Mark read, mark all read, delete actions
- Deduplication: prevents duplicate alerts within configurable lookback windows

### Authentication and Access Control
- Local email/password login with configurable password policy
- Email-based password reset flow (request token, receive email, confirm reset)
- SSO: Google Workspace OIDC + Azure Entra ID OIDC
- SSO enforcement with per-user password login override
- JWT access tokens (15 min) + refresh tokens (7 days) with auto-refresh
- RBAC: Owner > Admin > Analyst > Viewer
- Per-tenant API rate limiting (200 requests per 60 seconds)
- Multi-tenant isolation (all queries scoped by tenant_id)

### Export and Reporting
- CSV export: vulnerabilities, assets, users, tickets, remediations
- Executive summary: PDF (fpdf2), CSV, TXT with configurable sections and filters
- Executive PDF branding: custom logo upload, company name, tagline, primary/accent colors
- Scheduled reports: daily/weekly/monthly with SMTP email delivery
- Report sections: vulns, assets, risk, top hosts, top remediations, tickets

### Audit and Compliance
- Full audit logging of all user actions
- SIEM forwarding via syslog in CEF format (configurable per tenant)
- SLA compliance tracking with breach alerts
- Daily metric snapshots

### Global Search
- Cross-category search across vulnerabilities, assets, users, tickets, and CSPM findings
- Keyboard shortcut: Cmd+K (Mac) / Ctrl+K (Windows) to focus search bar
- Debounced input with categorized dropdown results
- Results limited to 5 per category for fast navigation

### Dashboard
- Overview: stat cards, severity/risk/status breakdown, top 10 hosts, connector health
- SLA compliance widget
- Trend charts: new vs resolved, severity trend, MTTR weekly, risk score over time
- Executive Report tab with schedule management

### Users Dashboard
- Unified directory view merging identity provider users and device owners
- Active/Suspended/All status filter
- Department filter from directory data
- Google avatar sync with profile images
- Groups export to CSV
- Expandable rows showing all devices per user with vuln counts and risk scores

### Automated Setup
- Single `install.sh` script handles full deployment (8 steps: Docker, TLS, .env, build, health check, admin user, seed data, auto-update cron)
- Default admin account created automatically: `admin@getvul.local` / `Admin123!`
- Seed demo data: 25 assets, 150+ vulnerabilities, 20 CSPM findings, 10 Jira tickets, 15 users, 5 notifications, 7 connectors
- Hourly auto-update cron keeps the deployment current

### Dark/Light Theme
- Theme toggle (Sun/Moon icon) in the header
- Persists user preference in localStorage
- CSS variable overrides for seamless switching between dark and light modes

### Mobile Responsive
- Collapsible sidebar with hamburger menu on small screens
- Responsive dropdown menus and filter bars
- Responsive padding and grid layouts across all pages

### Settings
- Organization: name, slug, domain, timezone
- Authentication: IdP config, SSO enforcement, password policy
- SLA Policy: per-severity remediation deadlines
- TLS/SSL certificate management (upload, self-signed, remove)
- SMTP email config with test connection
- Branding: custom logo upload, company name, tagline, primary/accent colors for PDF reports
- Users: add/edit/delete, role management, password toggle (shows only app users with login access; directory users visible in Users > Directory tab)
- Audit log: filterable table + syslog/SIEM forwarding config

## Supported Integrations

| Connector | Category | Data |
|-----------|----------|------|
| CrowdStrike Falcon Spotlight | Vulnerability Scanner | Vulns, devices, file paths, exploit/KEV, CSPM |
| Tenable Nessus | Vulnerability Scanner | Scan results, vulns |
| Microsoft Defender for Endpoint | Vulnerability Scanner | Machines, vulns |
| Wiz | Vulnerability Scanner | Cloud vulns, CSPM |
| Qualys VMDR | Vulnerability Scanner | Vulns, assets |
| Rapid7 InsightVM | Vulnerability Scanner | Vulns, assets |
| Asana | Ticketing | Create/manage vulnerability tickets |
| Jira | Ticketing | Create/manage vulnerability tickets |
| Google Workspace | Identity Provider | Users, groups, SSO |
| Azure Entra ID | Identity Provider | Users, groups, SSO |
| Okta | Identity Provider | Users, groups |
| Humaans | Enrichment/HR | Names, emails, GitHub/LinkedIn/Element, teams |
| Jamf Pro | MDM | Device security, user assignments |
| Microsoft Intune | MDM | Device compliance, management |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15, React 19, TypeScript, Tailwind CSS |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 (async) |
| Database | PostgreSQL 16 with JSONB columns |
| Cache | Redis 7 |
| Reverse Proxy | Nginx with TLS 1.2/1.3 termination |
| Auth | JWT + bcrypt + OIDC (Google/Azure) |
| Containers | Docker + Docker Compose (5 services) |
| IaC | Terraform (AWS + GCP) |
| CI/CD | GitHub Actions (5 jobs) |
