# Backend API Reference

The GetVul backend is a FastAPI application (Python 3.12) serving a REST API.

Interactive API docs (Swagger): `http://localhost:8000/docs`

## Route Overview

| Prefix | Module | Description |
|--------|--------|-------------|
| `/auth` | auth | Login, SSO, token management, password, user info |
| `/api/v1/vulnerabilities` | vulnerabilities | Vulnerability CRUD, stats, SLA, remediations, correlations, saved filters |
| `/api/v1/assets` | assets | Asset inventory, classification, risk scores, ignore |
| `/api/v1/connectors` | connectors | Connector config, sync, testing |
| `/api/v1/cspm` | cspm | Cloud posture findings |
| `/api/v1/tickets` | ticketing | Ticketing integration, automation rules |
| `/api/v1/tenant` | tenants | Tenant settings, user management, audit log, groups |
| `/api/v1/users` | users | User directory views, stats, directory |
| `/api/v1/notifications` | notifications | In-app notifications, alert bell |
| `/api/v1/export` | main | CSV export for all resources |
| `/api/v1/reports` | main | Scheduled report CRUD and delivery |
| `/api/v1/smtp` | main | SMTP config testing |
| `/api/v1/certificates` | main | TLS certificate management |
| `/api/v1/search` | search | Global cross-category search |
| `/api/v1/branding` | branding | PDF report branding (logo upload, colors) |
| `/dev` | dev_routes | Seed data (development only) |
| `/health` | main | Health check |

---

## Authentication (`/auth`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/auth/register` | Public | Create account (requires existing tenant domain) |
| POST | `/auth/login` | Public | Password login, returns JWT tokens |
| GET | `/auth/login/{provider}` | Public | Initiate SSO (google or azure) |
| GET | `/auth/callback/{provider}` | Public | OAuth 2.0 callback, exchanges code for tokens |
| POST | `/auth/refresh` | Public | Refresh expired access token |
| GET | `/auth/me` | Bearer | Current user profile |
| POST | `/auth/logout` | Bearer | Logout (optional server-side blocklist) |
| POST | `/auth/change-password` | Bearer | Change password (validates policy) |
| POST | `/auth/forgot-password` | Public | Request password reset email |
| POST | `/auth/reset-password` | Public | Confirm password reset with token |
| GET | `/auth/config` | Public | Available auth methods for tenant |

---

## Vulnerabilities (`/api/v1/vulnerabilities`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/` | Viewer+ | List with filtering and pagination |
| GET | `/stats` | Viewer+ | Dashboard statistics (totals, by severity/source, MTTR) |
| GET | `/overview` | Viewer+ | Overview metrics |
| GET | `/trends` | Viewer+ | Trend data for charts (new vs resolved, severity over time) |
| GET | `/sla/metrics` | Viewer+ | SLA compliance stats (breached, at-risk, within) |
| POST | `/sla/backfill` | Admin+ | Backfill SLA deadlines on existing vulns |
| POST | `/sla/recalculate` | Admin+ | Recalculate SLA after policy change |
| GET | `/saved-filters` | Viewer+ | List saved filters |
| POST | `/saved-filters` | Analyst+ | Create saved filter |
| PATCH | `/saved-filters/{filter_id}` | Analyst+ | Update saved filter |
| DELETE | `/saved-filters/{filter_id}` | Analyst+ | Delete saved filter |
| POST | `/saved-filters/{filter_id}/create-rule` | Analyst+ | Create automation rule from filter |
| GET | `/{vuln_id}` | Viewer+ | Single vulnerability detail |
| PATCH | `/{vuln_id}/status` | Analyst+ | Update vulnerability status |
| POST | `/cve/{cve_id}/ignore` | Analyst+ | Ignore CVE (exclude from remediations) |
| POST | `/cve/{cve_id}/unignore` | Analyst+ | Restore ignored CVE |
| POST | `/bulk-ignore-cve` | Analyst+ | Bulk ignore multiple CVEs |
| POST | `/bulk-status` | Analyst+ | Bulk status update (max 500) |
| GET | `/correlations/stats` | Viewer+ | Cross-source correlation statistics |
| GET | `/{vuln_id}/correlation` | Viewer+ | Correlation details for a vulnerability |
| GET | `/remediations/grouped` | Viewer+ | Remediations grouped by action |
| POST | `/remediations/{remediation_id}/suppress` | Analyst+ | Suppress a remediation |
| POST | `/remediations/{remediation_id}/unsuppress` | Analyst+ | Unsuppress a remediation |
| GET | `/remediations/{remediation_id}/hosts` | Viewer+ | Hosts affected by a remediation |
| GET | `/hosts/{asset_id}/remediations` | Viewer+ | Remediations for a specific host |

### Vulnerability Filters (query params)
- `page` (default 1), `page_size` (default 50, max 200)
- `severity` -- CRITICAL, HIGH, MEDIUM, LOW, INFO
- `source` -- CROWDSTRIKE, NESSUS, DEFENDER, WIZ, QUALYS, RAPID7
- `status` -- OPEN, IN_PROGRESS, REMEDIATED, SUPPRESSED, FALSE_POSITIVE
- `cve_id` -- exact CVE match
- `exploit_available` -- boolean
- `cisa_kev` -- boolean
- `asset_id` -- filter by asset UUID
- `search` -- partial match on CVE ID or product
- `age_days_min`, `age_days_max` -- filter by age
- `device_category` -- filter by asset type
- `min_risk_score` -- minimum asset risk score

---

## Assets (`/api/v1/assets`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/` | Viewer+ | List assets with filtering and pagination |
| GET | `/stats` | Viewer+ | Asset statistics (by category, OS, risk range, coverage) |
| GET | `/{asset_id}` | Viewer+ | Asset detail with vulnerability breakdown |
| POST | `/{asset_id}/ignore` | Analyst+ | Ignore asset (exclude from remediations) |
| POST | `/{asset_id}/unignore` | Analyst+ | Restore ignored asset |
| POST | `/bulk-ignore` | Analyst+ | Bulk ignore multiple assets |
| POST | `/recompute-risk-scores` | Admin+ | Recompute risk scores for all assets |
| POST | `/classify` | Admin+ | Bulk device classification |

---

## Connectors (`/api/v1/connectors`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/types` | Admin+ | Metadata for all 14 connector types |
| GET | `/` | Admin+ | List configured connectors (credentials masked) |
| POST | `/` | Admin+ | Create connector (credentials encrypted) |
| PATCH | `/{id}` | Admin+ | Update connector config or credentials |
| DELETE | `/{id}` | Admin+ | Delete connector |
| POST | `/test` | Admin+ | Test credentials without saving |
| POST | `/{id}/sync` | Admin+ | Trigger immediate sync |
| GET | `/{id}/sync-status` | Admin+ | Current sync status and last run info |

---

## CSPM (`/api/v1/cspm`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/` | Viewer+ | List misconfigurations with filters |
| GET | `/stats` | Viewer+ | CSPM summary statistics |
| GET | `/compliance` | Viewer+ | Compliance framework dashboard (CIS, SOC2, PCI-DSS, HIPAA pass rates) |
| GET | `/resources` | Viewer+ | Cloud resource inventory (filterable by provider, type, search) |
| GET | `/trends` | Viewer+ | CSPM trends timeline (configurable 7-365 days) |
| GET | `/{finding_id}` | Viewer+ | Single misconfiguration detail |
| PATCH | `/{finding_id}/status` | Analyst+ | Update status |
| POST | `/bulk-status` | Analyst+ | Bulk status update |

---

## Tickets (`/api/v1/tickets`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/` | Viewer+ | List tickets (grouped by task) |
| POST | `/` | Analyst+ | Create tickets for vulnerabilities |
| POST | `/host` | Analyst+ | Create per-host ticket |
| GET | `/stats` | Viewer+ | Ticket statistics |
| GET | `/assignees` | Viewer+ | List available assignees |
| POST | `/sync-status` | Analyst+ | Sync status from ticketing provider |
| POST | `/bulk-action` | Analyst+ | Bulk close/comment/sync/delete |
| POST | `/close` | Analyst+ | Close a ticket |
| GET | `/asana/config` | Admin+ | Fast Asana config check |
| GET | `/asana/setup` | Admin+ | Full Asana setup (workspaces/projects) |
| PATCH | `/asana/config` | Admin+ | Update Asana workspace/project selection |
| GET | `/rules` | Viewer+ | List automation rules |
| POST | `/rules` | Analyst+ | Create automation rule |
| PATCH | `/rules/{rule_id}` | Analyst+ | Update rule |
| DELETE | `/rules/{rule_id}` | Analyst+ | Delete rule |
| POST | `/rules/{rule_id}/run` | Analyst+ | Run rule immediately |

---

## Tenant Management (`/api/v1/tenant`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/me` | Bearer | Current tenant info |
| GET | `/settings` | Admin+ | Full tenant settings |
| PATCH | `/settings` | Owner | Update settings (org, auth, SLA, syslog) |
| GET | `/users` | Admin+ | List tenant users |
| POST | `/users` | Admin+ | Create user |
| PATCH | `/users/{user_id}` | Admin+ | Update user |
| PATCH | `/users/{user_id}/role` | Owner | Change user role |
| PATCH | `/users/{user_id}/deactivate` | Admin+ | Deactivate user |
| PATCH | `/users/{user_id}/allow-password` | Owner | Toggle password login override |
| DELETE | `/users/{user_id}` | Owner | Delete user |
| GET | `/audit-log` | Admin+ | Filterable audit log |
| GET | `/groups` | Viewer+ | User groups (from IdP sync) |

---

## Users (`/api/v1/users`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/` | Viewer+ | Unified user list (directory + device owners, Active/Suspended/All filter, department filter) |
| GET | `/stats` | Viewer+ | User statistics |
| GET | `/directory` | Viewer+ | Full directory view with Google avatar sync |

---

## Notifications (`/api/v1/notifications`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/` | Viewer+ | List notifications (paginated, filterable by category and read status) |
| GET | `/unread-count` | Viewer+ | Unread notification count (for bell icon badge) |
| POST | `/{notification_id}/read` | Viewer+ | Mark a single notification as read |
| POST | `/read-all` | Viewer+ | Mark all notifications as read |
| DELETE | `/{notification_id}` | Viewer+ | Delete a single notification |

---

## Export (`/api/v1/export`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/{resource}` | Viewer+ | CSV export (vulnerabilities, assets, users, tickets, remediations) |

---

## Reports (`/api/v1/reports`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/` | Viewer+ | List scheduled reports |
| POST | `/` | Analyst+ | Create scheduled report |
| PATCH | `/{report_id}` | Analyst+ | Update report config |
| DELETE | `/{report_id}` | Analyst+ | Delete report |
| POST | `/{report_id}/send` | Analyst+ | Send report immediately |

---

## SMTP (`/api/v1/smtp`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/test` | Admin+ | Test SMTP connection |
| POST | `/test-email` | Admin+ | Send test email |

---

## Certificates (`/api/v1/certificates`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/` | Admin+ | Current certificate info |
| POST | `/upload` | Owner | Upload custom PEM cert + key |
| POST | `/self-signed` | Owner | Generate self-signed certificate |
| DELETE | `/` | Owner | Remove installed certificate |

---

## Search (`/api/v1/search`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/?q=QUERY&limit=5` | Viewer+ | Global search across vulnerabilities, assets, users, tickets, and CSPM findings |

Query parameters:
- `q` -- search term (required)
- `limit` -- max results per category (default 5)

Returns categorized results from all five categories in a single response. Results are scoped to the authenticated user's tenant.

---

## Branding (`/api/v1/branding`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/logo` | Admin+ | Upload custom logo for PDF reports (multipart file upload) |

Logo and branding configuration (company name, tagline, primary/accent colors) are managed through tenant settings and applied to executive PDF reports.

---

## Shared Utilities

### Pagination (`pagination.py`)
- `PaginationParams` -- page (default 1), page_size (default 50, max 200)
- `PaginatedResponse[T]` -- generic response with items, total, page, pages

### Encryption (`encryption.py`)
- `encrypt_value(plaintext)` -- Fernet-encrypted string
- `decrypt_value(ciphertext)` -- original plaintext
- Key from `ENCRYPTION_KEY` environment variable

### Rate Limiting
- Per-tenant rate limiting: 200 requests per 60 seconds
- Tracked via Redis
- Returns HTTP 429 when exceeded
