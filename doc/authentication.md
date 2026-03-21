# Authentication & Authorization

## Authentication Methods

### Email/Password
- Registration: `POST /auth/register` (requires existing tenant domain)
- Login: `POST /auth/login` → returns JWT access + refresh tokens
- Password hashed with bcrypt
- Password validated against tenant policy (length, complexity, history)

### SSO (Single Sign-On)
- Google Workspace OIDC: `GET /auth/login/google` → redirect → callback
- Azure Entra ID OIDC: `GET /auth/login/azure` → redirect → callback
- Requires the corresponding directory connector to be configured first
- SSO enforcement toggle: when enabled, password login disabled (with per-user override)

### Token Management
- Access tokens: 15 minutes (JWT, HS256)
- Refresh tokens: 7 days
- Auto-refresh: frontend automatically refreshes on 401
- Token payload: user_id, tenant_id, email, role, jti
- Refresh: `POST /auth/refresh` with refresh token

## SSO Enforcement

### Setup Flow
1. Configure Google Workspace or Azure Entra ID connector in Connectors page
2. Go to Settings → Authentication → select the IdP
3. Enable "Enforce SSO" toggle
4. All users must now login via SSO

### Password Login Override
- Owner can set `allow_password_login = true` per user in Settings → Users
- These users can still use email/password even when SSO is enforced
- Useful for admin accounts, service accounts, or emergency access

### Backend Guard
- API rejects `sso_enforced=true` if IdP is LOCAL
- Switching IdP back to LOCAL auto-disables SSO enforcement

## Password Policy

Configurable per tenant in Settings → Authentication:

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
| OWNER | 40 | Full control: settings, IdP, SSO, user management, certificates |
| ADMIN | 30 | Connectors, user list, audit log, bulk actions |
| ANALYST | 20 | Update vuln status, create tickets, manage rules, change own password |
| VIEWER | 10 | Read-only access to all dashboards and data |

## Tenant Isolation
- Every table has `tenant_id` foreign key
- All queries scoped by authenticated user's tenant
- One tenant per deployment (multi-tenant model exists but single-org enforced)

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
| `/auth/config` | GET | Public | Available auth methods |
