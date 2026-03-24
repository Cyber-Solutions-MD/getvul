# Authentication and Authorization

## Authentication Methods

### Email/Password
- Registration: `POST /auth/register` (requires existing tenant domain)
- Login: `POST /auth/login` returns JWT access + refresh tokens
- Password hashed with bcrypt (per-user salt)
- Password validated against tenant policy (length, complexity, history)

### SSO (Single Sign-On)
- **Google Workspace OIDC:** `GET /auth/login/google` redirects to Google, callback exchanges code for tokens
- **Azure Entra ID OIDC:** `GET /auth/login/azure` redirects to Azure, callback exchanges code for tokens
- Requires the corresponding identity provider connector to be configured first
- SSO enforcement toggle: when enabled, password login is disabled (with per-user override)

### Password Reset
- **Request:** `POST /auth/forgot-password` with email address (public endpoint)
- Server generates a time-limited reset token and sends it via email (SMTP)
- **Confirm:** `POST /auth/reset-password` with token and new password (public endpoint)
- New password is validated against the tenant's password policy
- Token is single-use and expires after a short window
- Always returns a generic success message (prevents email enumeration)

### Token Management
- Access tokens: 15 minutes (JWT, HS256)
- Refresh tokens: 7 days
- Auto-refresh: frontend automatically refreshes on 401, redirects to login on failure
- Token payload: user_id, tenant_id, email, role, jti
- Refresh: `POST /auth/refresh` with refresh token

## SSO Enforcement

### Setup Flow
1. Configure Google Workspace or Azure Entra ID connector in the Connectors page
2. Go to Settings, then Authentication, and select the IdP
3. Enable the "Enforce SSO" toggle
4. All users must now login via SSO

### Password Login Override
- Owner can set `allow_password_login = true` per user in Settings, then Users
- These users can still use email/password even when SSO is enforced
- Useful for admin accounts, service accounts, or emergency access

### Backend Guard
- API rejects `sso_enforced=true` if IdP is LOCAL
- Switching IdP back to LOCAL auto-disables SSO enforcement

## Password Policy

Configurable per tenant in Settings, then Authentication:

| Setting | Options | Default |
|---------|---------|---------|
| Minimum length | 6, 8, 10, 12, 16 | 8 |
| Require uppercase (A-Z) | on/off | off |
| Require lowercase (a-z) | on/off | off |
| Require digit (0-9) | on/off | off |
| Require symbol (!@#$%) | on/off | off |
| Password history | off, 3, 5, 10, 24 | off |

Enforced on: registration, password change (by user or admin).

## Role-Based Access Control (RBAC)

| Role | Level | Permissions |
|------|-------|-------------|
| OWNER | 40 | Full control: settings, IdP, SSO enforcement, user management, certificates, SLA policy |
| ADMIN | 30 | Connectors, user list, audit log, bulk actions, SMTP config |
| ANALYST | 20 | Update vuln status, create tickets, manage rules, change own password, saved filters |
| VIEWER | 10 | Read-only access to all dashboards and data |

### Permission Matrix

| Action | Owner | Admin | Analyst | Viewer |
|--------|-------|-------|---------|--------|
| View dashboards | Yes | Yes | Yes | Yes |
| Export CSV | Yes | Yes | Yes | Yes |
| Update vuln status | Yes | Yes | Yes | No |
| Create tickets | Yes | Yes | Yes | No |
| Manage automation rules | Yes | Yes | Yes | No |
| Ignore CVEs/assets | Yes | Yes | Yes | No |
| Manage connectors | Yes | Yes | No | No |
| View audit log | Yes | Yes | No | No |
| Manage users | Yes | Yes | No | No |
| Change user roles | Yes | No | No | No |
| Update org settings | Yes | No | No | No |
| Manage certificates | Yes | No | No | No |
| Configure SSO enforcement | Yes | No | No | No |
| Set SLA policy | Yes | No | No | No |
| Delete users | Yes | No | No | No |

## Tenant Isolation
- Every table has `tenant_id` foreign key
- All queries scoped by authenticated user's tenant
- RBAC enforced on all write endpoints
- JWT token contains tenant_id, verified on every request

## Rate Limiting
- Per-tenant API rate limiting: 200 requests per 60 seconds
- Tracked via Redis
- Returns HTTP 429 with Retry-After header when exceeded

## API Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/auth/register` | POST | Public | Create account |
| `/auth/login` | POST | Public | Password login |
| `/auth/login/{provider}` | GET | Public | Initiate SSO |
| `/auth/callback/{provider}` | GET | Public | SSO callback |
| `/auth/refresh` | POST | Public | Refresh token |
| `/auth/me` | GET | Bearer | Current user |
| `/auth/change-password` | POST | Bearer | Change password |
| `/auth/forgot-password` | POST | Public | Request password reset email |
| `/auth/reset-password` | POST | Public | Confirm password reset with token |
| `/auth/config` | GET | Public | Available auth methods |
| `/auth/logout` | POST | Bearer | Logout |
