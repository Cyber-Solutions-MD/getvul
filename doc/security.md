# Security

## Authentication Security
- Passwords hashed with bcrypt (per-user salt)
- JWT tokens with short-lived access (15 min) and longer refresh (7 days)
- Auto-refresh on 401 with login redirect on failure
- SSO enforcement available (Google Workspace / Azure Entra ID OIDC)
- Configurable password policy (length, complexity, history)
- Password history prevents reuse of last N passwords (configurable: 3, 5, 10, 24)
- Email-based password reset with time-limited single-use tokens
- Generic response on forgot-password to prevent email enumeration
- Per-tenant API rate limiting: 200 requests per 60 seconds (Redis-backed)

## Security Headers

Applied by both Nginx and the backend application:

| Header | Value |
|--------|-------|
| X-Content-Type-Options | nosniff |
| X-Frame-Options | DENY |
| Cross-Origin-Resource-Policy | same-origin |
| Cross-Origin-Opener-Policy | same-origin |
| Content-Security-Policy | Restricts script-src, style-src, img-src, connect-src, frame-ancestors, form-action, base-uri, object-src |
| Permissions-Policy | Restricts camera, microphone, geolocation, etc. |
| Referrer-Policy | strict-origin-when-cross-origin |
| Cache-Control | no-store on API routes |
| X-Powered-By | Disabled / removed |

## TLS / SSL
- Nginx reverse proxy with TLS 1.2/1.3 termination
- Modern cipher suites only
- HTTP to HTTPS redirect when certificate installed
- HSTS headers enabled
- H2C smuggling protection in Nginx config
- Custom certificate upload (PEM format) -- supports any CA
- Self-signed certificate generation for testing/development
- Certificate management UI in Settings

## Credential Encryption
- Connector credentials (API keys, client secrets, tokens) encrypted with Fernet symmetric encryption
- SMTP passwords encrypted with Fernet
- Decrypted only in memory during active operations
- Never logged or exposed in API responses
- Encryption key sourced from `ENCRYPTION_KEY` environment variable

## Audit Logging

All user actions are recorded in the `audit_logs` table:

| Category | Actions |
|----------|---------|
| Authentication | auth.login, auth.register, auth.password_change, auth.logout |
| Vulnerabilities | vuln.status_update, vuln.bulk_status, vuln.suppress, vuln.unsuppress, vuln.ignore_cve, vuln.unignore_cve |
| Assets | asset.ignore, asset.unignore, asset.classify, asset.recompute_risk |
| Tickets | ticket.create, ticket.close, ticket.delete, ticket.comment, ticket.bulk_action |
| Automation | rule.create, rule.update, rule.delete, rule.run |
| Users | user.create, user.update, user.delete, user.role_change, user.deactivate |
| Settings | settings.update (org, auth, SLA, syslog, SMTP, password policy) |
| Certificates | cert.upload, cert.generate, cert.delete |
| Export | export.csv, export.summary |
| Reports | report.create, report.update, report.delete, report.send |

### SIEM / Syslog Forwarding
- Configurable in Settings under Audit Log
- Forwards all audit events in **CEF (Common Event Format)**
- Supports UDP and TCP protocols
- Configurable facility (local0-7, auth, authpriv)
- Compatible with: Splunk, IBM QRadar, Microsoft Sentinel, Elastic SIEM, and any CEF-capable SIEM

CEF format example:
```
CEF:0|GetVul|VulnMgmt|1.0|auth.login|auth.login|5|suser=admin@company.com act=auth.login cs1=user cs1Label=ResourceType msg={"method":"password"} rt=2026-03-20T13:55:47Z
```

## Network Security
- Nginx as the only public-facing service
- Rate limiting at Nginx level (configurable per endpoint type)
- Per-tenant application-level rate limiting (200 req/60s via Redis)
- CORS restricted to configured origins
- PostgreSQL and Redis in private Docker network (only accessible from backend)
- H2C request smuggling protection in Nginx

## Tenant Isolation
- All database tables include `tenant_id` column
- All queries scoped by authenticated user's `tenant_id` from JWT
- No cross-tenant data access possible through the API
- Global search (`/api/v1/search`) results are tenant-scoped -- queries only return data belonging to the authenticated user's tenant
- RBAC enforced on all write endpoints
- Owner-only operations: settings, certificates, user management, SSO enforcement, SLA policy

## Input Validation
- Pydantic schemas validate all API request bodies
- SQLAlchemy ORM uses parameterized queries (prevents SQL injection)
- File uploads limited to PEM text content and image files (logo upload for branding); handled via `python-multipart`
- Pagination limits enforced (max 200 per page)
- Bulk operations capped (max 500 per request)

## Container Security
- All services run in Docker containers with minimal base images (Alpine)
- Database in private network (not exposed to host in production)
- Redis in private network
- No root processes in application containers
- Secrets passed via environment variables (not baked into images)

## CI/CD Security Pipeline

### Static Analysis (SAST) -- Semgrep
- Runs on every push and pull request
- Rule sets: p/default, p/owasp-top-ten, p/secrets, p/dockerfile
- Results published to semgrep.dev for tracking
- Catches: SQL injection, XSS, hardcoded secrets, insecure configurations

### Dynamic Analysis (DAST) -- OWASP ZAP
- Runs after backend and frontend CI jobs pass
- Three scan types:
  1. **API Scan:** Scans all endpoints via OpenAPI spec (`/openapi.json`)
  2. **Backend Baseline:** Crawls backend for common vulnerabilities
  3. **Frontend Baseline:** Crawls frontend for common vulnerabilities
- Reports uploaded as CI artifacts (14-day retention)

### Pre-commit Hook
- Semgrep scan runs on staged files before every commit
- Rule sets: `p/default`, `p/owasp-top-ten`, `p/secrets`, `p/dockerfile`
- Catches security issues before they enter the repository
- Prevents hardcoded secrets, SQL injection, XSS, and insecure Dockerfile patterns from being committed

### Backend Checks
- ruff: Python linting and formatting
- mypy: Type checking for type safety
- pytest: 15+ tests with coverage reporting
- Alembic: Migration validation against test database

### Frontend Checks
- TypeScript strict type checking (`tsc --noEmit`)
- ESLint for code quality
- Production build verification

## Notification Security

### Alert Deduplication
Each alert check uses a time-windowed deduplication strategy to prevent notification flooding:

| Alert Type | Lookback Window | Dedup Key |
|------------|----------------|-----------|
| New critical vulnerability | 2 hours | (tenant_id, category, resource_type, cve_id) |
| SLA breach warning | 24 hours | (tenant_id, category, resource_type, cve_id) |
| Connector sync failure | 4 hours | (tenant_id, category, resource_type, connector_id) |
| Risk score spike | 24 hours | (tenant_id, category, resource_type, asset_id) |

### Notification Access Control
- Notifications are scoped by `tenant_id` -- no cross-tenant access
- Broadcast notifications (user_id = null) visible to all tenant users
- Targeted notifications only visible to the specified user
- All notification endpoints require Viewer+ role
- Email delivery uses the tenant's configured SMTP settings

## SLA Compliance Security
- SLA deadlines computed automatically based on tenant policy
- Breach detection runs continuously
- At-risk alerts triggered 72 hours before deadline
- SLA metrics available in dashboard and audit trail
- Daily snapshots preserve historical compliance data
