# Authentication & Authorization

## SSO Login Flow

GetVul uses OAuth 2.0 / OpenID Connect (OIDC) for single sign-on with Google Workspace and Microsoft Azure (Entra ID).

```
1. User clicks "Login with Google/Azure"
       ↓
2. Frontend calls GET /auth/login/{provider}
       ↓
3. Backend generates authorization_url with state token
       ↓
4. Frontend redirects user to provider's OAuth 2.0 consent screen
       ↓
5. User authenticates with Google/Azure
       ↓
6. Provider redirects to GET /auth/callback/{provider}?code=...&state=...
       ↓
7. Backend validates state, exchanges code for tokens
       ↓
8. Backend fetches user info (email, name, picture) from provider
       ↓
9. Backend looks up tenant by email domain
       ↓
10. Backend upserts user record in database
       ↓
11. Backend issues GetVul JWT tokens (access + refresh)
       ↓
12. Frontend stores tokens, adds to Authorization header
```

## JWT Tokens

### Access Token (15 minutes)
```json
{
  "sub": "user-uuid",
  "tenant_id": "tenant-uuid",
  "email": "user@company.com",
  "role": "ADMIN",
  "jti": "unique-token-id",
  "exp": 1710000000,
  "iat": 1709999100
}
```

### Refresh Token (7 days)
```json
{
  "sub": "user-uuid",
  "tenant_id": "tenant-uuid",
  "jti": "unique-token-id",
  "exp": 1710604800,
  "iat": 1709999100
}
```

- **Algorithm:** HS256
- **Signing key:** `JWT_SECRET_KEY` environment variable
- **Token refresh:** `POST /auth/refresh` with refresh token returns new access token
- **Revocation:** Optional Redis-based blocklist for invalidating tokens before expiry

## Role-Based Access Control (RBAC)

### Role Hierarchy

| Role | Level | Description |
|------|-------|-------------|
| **OWNER** | 40 | Full tenant control. Can manage all settings and users. |
| **ADMIN** | 30 | Manage connectors, settings, users. Can do everything except delete tenant. |
| **ANALYST** | 20 | Update vulnerability statuses, create tickets. Read access to all data. |
| **VIEWER** | 10 | Read-only access to dashboards, vulnerabilities, assets. |

Higher roles inherit all permissions of lower roles.

### Route Protection

Routes are protected using FastAPI dependencies:

```python
@router.patch("/{id}/status")
async def update_status(user=Depends(require_analyst)):  # Analyst+
    ...

@router.post("/")
async def create_connector(user=Depends(require_admin)):  # Admin+
    ...
```

### Permission Matrix

| Action | Viewer | Analyst | Admin | Owner |
|--------|--------|---------|-------|-------|
| View dashboard & stats | Yes | Yes | Yes | Yes |
| View vulnerabilities | Yes | Yes | Yes | Yes |
| View assets | Yes | Yes | Yes | Yes |
| View CSPM findings | Yes | Yes | Yes | Yes |
| Update vuln status | — | Yes | Yes | Yes |
| Bulk update statuses | — | Yes | Yes | Yes |
| Create tickets | — | Yes | Yes | Yes |
| Manage connectors | — | — | Yes | Yes |
| Trigger sync | — | — | Yes | Yes |
| Classify assets | — | — | Yes | Yes |
| Manage users | — | — | Yes | Yes |
| Tenant settings | — | — | — | Yes |

## Tenant Isolation

- Every database table includes a `tenant_id` column
- All queries are **automatically scoped** by the authenticated user's `tenant_id`
- There is no way to access another tenant's data through the API
- Tenants are identified by email domain during SSO (e.g., `@acme.com` → Acme tenant)
- Each user belongs to exactly one tenant

## OIDC Provider Configuration

### Google Workspace
```env
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/callback/google
```

### Microsoft Azure (Entra ID)
```env
AZURE_CLIENT_ID=your-azure-client-id
AZURE_CLIENT_SECRET=your-azure-client-secret
AZURE_REDIRECT_URI=http://localhost:8000/auth/callback/azure
```

## Security Notes

- Access tokens are intentionally short-lived (15 min) to limit exposure
- Refresh tokens are longer-lived (7 days) for user convenience
- The `state` parameter in OIDC flow prevents CSRF attacks
- Token `jti` (JWT ID) enables individual token revocation via Redis blocklist
- All sensitive operations require explicit role checks
- Failed authentication returns generic error messages (no user enumeration)
