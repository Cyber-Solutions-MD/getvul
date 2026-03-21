# Security

## Authentication Security
- Passwords hashed with bcrypt (salt per user)
- JWT tokens with short-lived access (15 min) and longer refresh (7 days)
- Auto-refresh on 401 with login redirect on failure
- SSO enforcement available (Google Workspace / Azure Entra ID)
- Configurable password policy (length, complexity, history)
- Password history prevents reuse of last N passwords

## Audit Logging
All user actions are recorded in the `audit_logs` table:
- auth.login, auth.register, auth.password_change
- vuln.status_update, vuln.bulk_status, vuln.suppress, vuln.unsuppress
- ticket.create, ticket.close, ticket.delete, ticket.comment
- user.create, user.update, user.delete, user.role_change, user.deactivate
- settings.update (all org/auth/policy changes)
- cert.upload, cert.generate, cert.delete
- export.csv, export.summary

### SIEM / Syslog Forwarding
- Configurable in Settings → Audit Log
- Forwards all audit events in **CEF (Common Event Format)**
- Supports UDP and TCP protocols
- Configurable facility (local0-7, auth, authpriv)
- Compatible with: Splunk, IBM QRadar, Microsoft Sentinel, Elastic SIEM

CEF format example:
```
CEF:0|GetVul|VulnMgmt|1.0|auth.login|auth.login|5|suser=igor@parity.io act=auth.login cs1=user cs1Label=ResourceType msg={"method":"password"} rt=2026-03-20T13:55:47Z
```

## TLS / SSL
- Nginx reverse proxy with TLS 1.2/1.3 termination
- HTTP → HTTPS redirect when certificate installed
- Custom certificate upload (PEM format) — supports Microsoft CA, Let's Encrypt, any CA
- Self-signed certificate generation for testing
- Certificate management UI in Settings → General
- HSTS headers enabled

## Credential Encryption
- Connector credentials (API keys, secrets) encrypted with Fernet symmetric encryption
- Decrypted only in memory during sync operations
- Never logged or exposed in API responses

## Network Security
- Nginx rate limiting: 30 req/s for API, 5 req/s for auth endpoints
- Security headers: X-Frame-Options, X-Content-Type-Options, X-XSS-Protection, Referrer-Policy
- CORS restricted to configured origins
- PostgreSQL connections via asyncpg

## Tenant Isolation
- All queries scoped by `tenant_id`
- RBAC enforced on all write endpoints
- Owner-only operations: settings, certificates, user management, SSO enforcement

## Input Validation
- Pydantic schemas validate all API requests
- SQLAlchemy ORM prevents SQL injection (parameterized queries)
- File uploads limited to PEM text (no binary uploads)

## Container Security
- All services in Docker containers
- Database in private network (only accessible from backend)
- Redis in private network
- Nginx as the only public-facing service
