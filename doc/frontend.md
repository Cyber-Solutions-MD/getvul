# Frontend Documentation

The GetVul frontend is a **Next.js 15** application with **React 19** and **TypeScript**, styled with **Tailwind CSS**.

## Pages

### Login (`/login`)
- Email/password login form
- SSO buttons for Google and Azure (when configured)
- Forgot password link with email-based reset flow
- Redirects to `/dashboard` after authentication
- Displays tenant auth config (available methods)

### Dashboard (`/dashboard`)
- **Stat cards:** Total vulnerabilities, open count, critical, exploitable, CISA KEV
- **Severity distribution:** Progress bars with counts per severity level
- **Source distribution:** Breakdown by scanner source
- **Correlated CVEs:** Count of CVEs detected by multiple scanners
- **MTTR:** Mean Time to Remediate metric
- **Top 10 riskiest hosts:** Clickable links to asset detail
- **Connector health:** Last sync status per connector
- **SLA compliance widget:** Breached, at-risk (72h), within SLA, compliance %
- **Trend charts:** New vs resolved timeline, severity trend, MTTR weekly, risk score history
- **Executive Report tab:** Generate/schedule PDF/CSV/TXT reports

### Vulnerabilities (`/dashboard/vulnerabilities`)
Tabbed interface with two views:

**Vulnerabilities Tab:**
- Filter bar: search, severity (multi-select), source, status, exploit/KEV checkboxes, device category, min risk score
- Paginated table: CVE ID, severity badge, source, status, product, hostname, last seen, SLA status
- Bulk select with status update actions (remediate, suppress, etc.)
- CVE ignore/unignore actions
- Click row to view full details

**Remediations Tab:**
- Grouped by remediation action
- Columns: action, affected product, host count, vuln count, max severity
- Click remediation to drill into affected hosts
- Click host to see all remediations for that asset
- Suppress/unsuppress remediations
- All filters apply across drill-down levels

### Assets (`/dashboard/assets`)
- Filter bar: hostname search, device category dropdown, risk score slider
- Sortable table: hostname, OS, device category, risk score, vuln counts
- Vuln counts include: open, critical, high, exploitable, CISA KEV
- Risk score color-coded: 80+ red, 50-79 orange, 20-49 yellow, <20 green
- Classify button for bulk device categorization (Admin only)
- Recompute risk scores button (Admin only)
- Ignore/unignore assets
- Click asset for detail view with vulnerability list, MDM info, and CrowdStrike containment status

### Users (`/dashboard/users`)
- Unified directory view merging identity provider users and device owners
- Active/Suspended/All status filter tabs
- Department filter dropdown (populated from directory data)
- Google avatar sync with profile images (referrerPolicy=no-referrer)
- User search with device details, vuln counts, risk scores
- Groups tab with CSV export (synced from Google Workspace, Azure Entra ID, or Okta)
- Expandable rows showing all devices per user

### CSPM (`/dashboard/cspm`)
4-tab interface:

**Findings Tab:**
- Cloud misconfiguration findings
- Filters: severity, category, source, compliance framework, resource type
- Table: rule name, resource, severity, category, frameworks, remediation link
- Bulk status updates

**Compliance Tab:**
- Compliance framework dashboard
- Pass rates for CIS, SOC2, PCI-DSS, HIPAA frameworks
- Per-framework breakdown with pass/fail/total counts

**Resources Tab:**
- Cloud resource inventory
- Filterable by cloud provider, resource type, search
- Shows finding counts per resource

**Trends Tab:**
- CSPM trends timeline (configurable 7-365 days)
- Findings over time by severity and status

### Connectors (`/dashboard/connectors`)
- Card per connector: type, last sync time/status, record count, enabled toggle
- Actions: Test credentials, Trigger sync, Edit config, Delete
- Setup modal with per-connector-type form fields and validation
- All 14 connector types with category grouping
- Polling sync status (3s interval while syncing)
- Permission matrix displayed in setup modal

### Tickets (`/dashboard/tickets`)
- Asana and Jira integration views
- List tickets grouped by task with severity, vuln count, assignee, status
- Create per-host or per-remediation tickets
- Automation rules: create, edit, enable/disable, run immediately
- Bulk actions: close, comment, sync status, delete
- Asana workspace/project configuration

### Settings (`/dashboard/settings`)
- **Organization:** Name, slug, domain, timezone
- **Authentication:** IdP config, SSO enforcement toggle, password policy settings
- **SLA Policy:** Per-severity deadlines (CRITICAL, HIGH, MEDIUM, LOW)
- **TLS/SSL:** Upload custom cert, generate self-signed, remove
- **SMTP:** Email server config with test connection and test email
- **Branding:** Custom logo upload, company name, tagline, primary/accent colors for executive PDF reports
- **Users:** Add/edit/delete app users (with login access), role assignment, password login override. Directory users are shown separately under Users > Directory tab
- **Audit Log:** Filterable table of all actions + syslog/SIEM forwarding config
- **Executive Reports:** Schedule management (daily/weekly/monthly)

## Layout

### Dashboard Shell (`app/dashboard/layout.tsx`)
- Two-column layout: sidebar + main content area
- Persistent across all dashboard pages

### Sidebar
- Navigation links with Lucide icons
- Items: Dashboard, Vulnerabilities, Assets, Users, CSPM, Connectors, Tickets, Settings
- Active link highlighting
- Mobile responsive: collapsible with hamburger menu on small screens

### Header
- Sticky top bar with branding
- Global search bar with Cmd+K (Mac) / Ctrl+K (Windows) keyboard shortcut
- Debounced search input with categorized dropdown results (vulns, assets, users, tickets, CSPM)
- Theme toggle (Sun/Moon icon) for dark/light mode switching, persisted in localStorage
- Notification bell icon with unread count badge (polls `/api/v1/notifications/unread-count`)
- Clicking bell opens notification dropdown with recent alerts
- User menu with profile and logout

## Components

### UI Components
| Component | Purpose |
|-----------|---------|
| SeverityBadge | Color-coded CRITICAL/HIGH/MEDIUM/LOW/INFO badges |
| Pagination | Page navigation with prev/next and page indicator |
| FilterBar | Reusable filter dropdowns and toggles |
| Modal | Dialog overlay for forms and confirmations |
| DataTable | Sortable, selectable table with bulk actions |
| ConfirmModal | Custom in-app confirmation dialog (replaces browser confirm/alert) |
| Toast | In-app toast notifications for success, error, and info feedback |

### Dashboard Components
| Component | Purpose |
|-----------|---------|
| StatsCards | Summary metric cards |
| SeverityChart | Severity distribution visualization |
| TrendChart | New vs resolved timeline (Recharts) |
| SLAWidget | SLA compliance donut/stats |
| TopHostsList | Top 10 riskiest hosts |
| ConnectorHealth | Connector status indicators |
| NotificationBell | Header bell icon with unread badge + dropdown |
| GlobalSearch | Search bar with Cmd+K shortcut + categorized dropdown |
| ThemeToggle | Sun/Moon icon for dark/light mode switching |

## HTTP Client (`lib/api.ts`)

Wrapper around the native `fetch` API:
- All API calls use relative URLs (routed through nginx); no hardcoded backend host
- `NEXT_PUBLIC_API_URL` must be set to `""` (empty string) in docker-compose.yml for production
- Automatically adds `Authorization: Bearer <token>` header
- Auto-refreshes token on 401 response
- Redirects to login on refresh failure
- Throws on non-2xx responses

## Type Definitions (`types/`)

| File | Types |
|------|-------|
| `vulnerability.ts` | VulnerabilitySummary, VulnerabilityDetail, DashboardStats, VulnerabilityFilter |
| `asset.ts` | AssetSummary, AssetDetail, AssetStats |
| `connector.ts` | ConnectorConfig, ConnectorType, ConnectorTestResult |
| `cspm.ts` | Misconfiguration, CSPMStats |
| `user.ts` | User, UserRole |

## State Management

- **Local state only** -- React `useState`, `useEffect`, `useCallback` hooks
- No global state manager
- Async data fetching with loading/error states per page
- Filter state managed locally and passed as query params to API

## Styling

- **Theme:** Dark/light mode toggle with CSS variable overrides; preference stored in localStorage
- **Primary color:** Indigo
- **Data colors:** Red, orange, yellow, green, blue for severity/risk levels
- **Icons:** Lucide React throughout
- **Responsive:** Grid layouts adapt from 1 column (mobile) to 2-4 columns (desktop); responsive dropdowns and padding; collapsible sidebar with hamburger menu on mobile
- **Utilities:** `cn()` helper for conditional class merging (clsx + tailwind-merge)
