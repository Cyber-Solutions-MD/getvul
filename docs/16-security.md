# 16 — Security

This combines what used to live in `doc/security.md` and `doc/authentication.md`. Authentication, authorization, secret handling, security headers, and the CI/CD security pipeline are all here.

For threat-model artefacts produced during phase development see `.planning/phases/<N>/<N>-SECURITY.md` (currently optional — `workflow.security_enforcement` is on by default but no SECURITY.md has been produced for Phase 1 yet; the four review-warning items in `.planning/phases/01-multi-replica-state/01-REVIEW.md` are the working list).

## Authentication

### Methods

**Email + password**
- Registration: `POST /auth/register` (requires existing tenant domain)
- Login: `POST /auth/login` returns JWT access + refresh tokens
- Passwords hashed with bcrypt (per-user salt) — [backend/app/auth/password.py](../backend/app/auth/password.py)
- Validated against the tenant `password_policy` JSONB (length, complexity, history)

**SSO (OIDC)**
- Google Workspace: `GET /auth/login/google?tenant_id=...`
- Azure Entra ID: `GET /auth/login/azure?tenant_id=...`
- After Phase 1, OIDC state is stored in Redis with `SET ... NX EX 600` and consumed atomically with `GETDEL` — see [02-architecture.md](02-architecture.md#authentication-flow-oidc-post-phase-1). This makes the flow safe across replicas; the previous in-memory `_pending_states` dict was a single-replica defect (D-06).
- If Redis is unreachable, the callback **fails closed** with HTTP 503 — bypassing state validation would be a CSRF defect.
- SSO **enforcement** can be enabled per tenant; per-user `allow_password_login` overrides it for break-glass accounts.

**Password reset**
- `POST /auth/forgot-password` (public) — generates time-limited single-use token, emails it via tenant SMTP
- `POST /auth/reset-password` (public) — validates token, applies new password against policy
- Always returns a generic success response — prevents email enumeration

### Token management

| Token | Default TTL | Algorithm | Where |
|-------|-------------|-----------|-------|
| Access | 15 min | HS256 | `JWT_SECRET_KEY` env var |
| Refresh | 7 days | HS256 | same |

Frontend ([frontend/src/lib/api.ts](../frontend/src/lib/api.ts)) auto-refreshes on 401 and redirects to `/login` if the refresh fails. Token payload includes `sub`, `tenant_id`, `email`, `role`, `type`, `jti`, `iat`, `exp`.

### Default admin credentials

The install script creates a default admin account:
- **Email:** `admin@getvul.local`
- **Password:** `Admin123!`

**Change this password immediately after first login.** The default credentials are well-known and must not be used in production without being changed. Phase 6 (PROD-06) will force a first-login rotation.

## Authorization (RBAC)

Roles and integer levels defined in [backend/app/auth/rbac.py](../backend/app/auth/rbac.py):

| Role | Level | Typical permissions |
|------|-------|---------------------|
| OWNER | 40 | Full control: settings, IdP, SSO enforcement, user management, certificates, SLA policy |
| ADMIN | 30 | Connectors, user list, audit log, bulk actions, SMTP config |
| ANALYST | 20 | Update vuln status, create tickets, manage rules, change own password, saved filters |
| VIEWER | 10 | Read-only access to all dashboards and data |

### Permission matrix

| Action | Owner | Admin | Analyst | Viewer |
|--------|:-----:|:-----:|:-------:|:------:|
| View dashboards | ✓ | ✓ | ✓ | ✓ |
| Export CSV | ✓ | ✓ | ✓ | ✓ |
| Update vuln status | ✓ | ✓ | ✓ | — |
| Create tickets | ✓ | ✓ | ✓ | — |
| Manage automation rules | ✓ | ✓ | ✓ | — |
| Ignore CVEs / assets | ✓ | ✓ | ✓ | — |
| Manage connectors | ✓ | ✓ | — | — |
| View audit log | ✓ | ✓ | — | — |
| Manage users | ✓ | ✓ | — | — |
| Change user roles | ✓ | — | — | — |
| Update org settings | ✓ | — | — | — |
| Manage certificates | ✓ | — | — | — |
| Configure SSO enforcement | ✓ | — | — | — |
| Set SLA policy | ✓ | — | — | — |
| Delete users | ✓ | — | — | — |

`Depends(require_role(min_role))` is the standard pattern — every protected endpoint declares its minimum role.

## Password policy

Configurable per tenant in `Settings → Authentication`. Stored in `tenants.password_policy` (JSONB).

| Setting | Options | Default |
|---------|---------|---------|
| Minimum length | 6, 8, 10, 12, 16 | 8 |
| Require uppercase (A-Z) | on/off | off |
| Require lowercase (a-z) | on/off | off |
| Require digit (0-9) | on/off | off |
| Require symbol (!@#$%) | on/off | off |
| Password history | off, 3, 5, 10, 24 | off |

Enforced on registration and password change. Old hashes are kept in `users.password_history` and compared on change.

---

## Security headers

### From the FastAPI `SecurityHeadersMiddleware` ([main.py:86-98](../backend/app/main.py#L86-L98))

| Header | Value | Notes |
|--------|-------|-------|
| `X-Content-Type-Options` | `nosniff` | applied to all responses |
| `X-Frame-Options` | `DENY` | applied to all responses |
| `Cross-Origin-Resource-Policy` | `same-origin` | applied to all responses |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | applied to all responses |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` | applied to all responses |
| `Content-Security-Policy` | `default-src 'none'; frame-ancestors 'none'; base-uri 'none'` | applied to every response except the debug-only docs routes `/docs`, `/redoc`, `/openapi.json` (PROD-04-01) |
| `Cross-Origin-Opener-Policy` | `same-origin` | applied to all responses (PROD-04-01) |
| `Cache-Control` | `no-store, no-cache, must-revalidate, max-age=0` | only on `/api/` and `/auth/` paths |
| `Pragma` | `no-cache` | only on `/api/` and `/auth/` paths |

Note: the frontend's [frontend/next.config.js](../frontend/next.config.js) also ships its own CSP covering HTML routes — that policy includes `script-src`/`style-src` directives appropriate for HTML resource loading. The backend CSP (`default-src 'none'`) is deliberately stricter because the backend serves JSON on all production routes. The one exception is the interactive API docs (`/docs`, `/redoc`, `/openapi.json`), which are HTML/JS and mounted **only** when `DEBUG=true`; the middleware skips the strict CSP on those paths so Swagger UI and ReDoc render during local development. In production (`DEBUG=false`) those routes do not exist, so the strict policy covers the entire live surface.

### From Nginx ([nginx/nginx.conf:29-32](../nginx/nginx.conf#L29-L32) and `:119`)

| Header | Value | Where |
|--------|-------|-------|
| `X-Frame-Options` | `SAMEORIGIN` | `add_header always` (HTTP and HTTPS) |
| `X-Content-Type-Options` | `nosniff` | `add_header always` |
| `X-XSS-Protection` | `1; mode=block` | `add_header always` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | `add_header always` |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | HTTPS server only ([line 119](../nginx/nginx.conf#L119)) |

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
