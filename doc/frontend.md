# Frontend Documentation

The GetVul frontend is a **Next.js 14.2** application with **React 18.3** and **TypeScript 5.5**, styled with **Tailwind CSS**.

## Pages

### Login (`/`)
- Entry point and login page
- SSO buttons for Google and Azure
- Redirects to `/dashboard` after authentication

### Dashboard (`/dashboard`)
- **Stats cards:** Total vulnerabilities, open count, exploitable, CISA KEV
- **Severity distribution:** Progress bars with counts per severity level
- **Source distribution:** Breakdown by scanner source
- **Correlated CVEs:** Count of CVEs detected by multiple scanners
- **MTTR:** Mean Time to Remediate metric
- **Seed button:** Populates demo data (development only)

### Vulnerabilities (`/dashboard/vulnerabilities`)
Tabbed interface with two views:

**Vulnerabilities Tab:**
- Filter bar: search, severity (multi-select), source, status, exploit/KEV checkboxes
- Paginated table: CVE ID, severity badge, source, status, product, hostname, last seen
- Bulk select with status update actions (remediate, suppress, etc.)
- Click row to view full details

**Remediations Tab:**
- Grouped by remediation action
- Columns: action, affected product, host count, vuln count, max severity
- Click remediation → drill into affected hosts
- Click host → see all remediations for that asset
- All filters apply across drill-down levels

### Assets (`/dashboard/assets`)
- Filter bar: hostname search, device category dropdown, risk score slider
- Sortable table: hostname, OS, device category, risk score, vuln counts
- Vuln counts include: open, critical, high, exploitable, CISA KEV
- Risk score color-coded: 80+ red, 50–79 orange, 20–49 yellow, <20 green
- Classify button for bulk device categorization (Admin only)
- Click asset for detail view with vulnerability list

### CSPM (`/dashboard/cspm`)
- Cloud misconfiguration findings
- Filters: severity, category, source, compliance framework, resource type
- Table: rule name, resource, severity, category, frameworks, remediation link

### Connectors (`/dashboard/connectors`)
- View and manage data source integrations
- Card per connector: type, last sync time/status, record count, enabled toggle
- Actions: Test credentials, Trigger sync, Edit config, Delete
- Setup modal with per-connector-type form fields and validation
- Polling sync status (3s interval while syncing)
- Permission matrix displayed in setup modal

### Tickets (`/dashboard/tickets`)
- Jira and GitHub Issues integration
- List, create, update, resolve tickets linked to vulnerabilities
- Automation rules for auto-ticket creation

### Settings (`/dashboard/settings`)
- Tenant configuration
- User management (add/remove, role assignment)
- Session timeout settings

## Layout

### Dashboard Shell (`app/dashboard/layout.tsx`)
- Two-column layout: sidebar + main content area
- Persistent across all dashboard pages

### Sidebar (`components/layout/Sidebar.tsx`)
- Navigation links with Lucide icons
- Items: Dashboard, Vulnerabilities, Assets, CSPM, Connectors, Tickets, Settings
- Active link highlighting
- Responsive (collapses on mobile)

### Header (`components/layout/Header.tsx`)
- Sticky top bar with GetVul branding
- User menu with profile and logout

## Components

### UI Components
| Component | Location | Purpose |
|-----------|----------|---------|
| SeverityBadge | `components/ui/Badge.tsx` | Color-coded CRITICAL/HIGH/MEDIUM/LOW/INFO badges |
| Pagination | `components/ui/Pagination.tsx` | Page navigation with prev/next and page indicator |

### Vulnerability Components
| Component | Location | Purpose |
|-----------|----------|---------|
| VulnTable | `components/vulnerabilities/VulnTable.tsx` | Sortable vulnerability table with bulk select |
| VulnFilters | `components/vulnerabilities/VulnFilters.tsx` | Filter bar with dropdowns and checkboxes |
| BulkActions | `components/vulnerabilities/BulkActions.tsx` | Status update for selected vulnerabilities |

### Dashboard Components
| Component | Location | Purpose |
|-----------|----------|---------|
| StatsCards | `components/dashboard/` | Summary metric cards |
| SeverityChart | `components/dashboard/` | Severity distribution visualization |

## HTTP Client (`lib/api.ts`)

Simple wrapper around the native `fetch` API:

```typescript
const data = await api<ResponseType>("/api/v1/endpoint");
const result = await api<T>("/api/v1/endpoint", {
  method: "POST",
  body: JSON.stringify(payload),
});
```

- Automatically adds `Authorization: Bearer <token>` header
- Throws on non-2xx responses
- Default token: `"dev-token"` for development

## Type Definitions (`types/`)

| File | Types |
|------|-------|
| `vulnerability.ts` | VulnerabilitySummary, VulnerabilityDetail, DashboardStats, VulnerabilityFilter |
| `asset.ts` | AssetSummary, AssetDetail, AssetStats |
| `connector.ts` | ConnectorConfig, ConnectorType, ConnectorTestResult |
| `cspm.ts` | Misconfiguration, CSPMStats |
| `user.ts` | User, UserRole |

## State Management

- **Local state only** — React `useState`, `useEffect`, `useCallback` hooks
- No global state manager (Redux, Zustand, etc.)
- Async data fetching with loading/error states per page
- Filter state managed locally and passed as query params to API

## Styling

- **Theme:** Dark mode (gray-950/gray-900 backgrounds)
- **Primary color:** Indigo
- **Data colors:** Red, orange, yellow, green, blue for severity/risk levels
- **Icons:** Lucide React throughout
- **Responsive:** Grid layouts adapt from 1 column (mobile) to 2–4 columns (desktop)
- **Utilities:** `cn()` helper for conditional class merging (clsx + tailwind-merge)
