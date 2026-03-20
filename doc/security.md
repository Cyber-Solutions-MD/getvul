# Security

## Credential Encryption

Connector credentials (API keys, client secrets) are encrypted at rest using **Fernet symmetric encryption** from the `cryptography` library.

- Credentials are encrypted before database storage
- Decrypted only in memory during active sync operations
- Never logged, cached, or exposed in API responses
- Encryption key (`ENCRYPTION_KEY`) must be a valid Fernet key (base64-encoded 32 bytes)

```python
# Encryption flow
plaintext_credentials = json.dumps({"client_id": "...", "client_secret": "..."})
encrypted = encrypt_value(plaintext_credentials)  # Fernet encryption
# stored in connector_configs.credentials_secret_arn

# Decryption flow (sync time only)
decrypted = decrypt_value(encrypted)
credentials = json.loads(decrypted)
```

## JWT Security

| Property | Value |
|----------|-------|
| Algorithm | HS256 |
| Access token TTL | 15 minutes |
| Refresh token TTL | 7 days |
| Signing key | `JWT_SECRET_KEY` env var |
| Token ID | `jti` claim (unique per token) |

- Short-lived access tokens limit the window of exposure if a token is compromised
- Refresh tokens allow seamless re-authentication without re-login
- `jti` enables individual token revocation via Redis blocklist
- Failed authentication returns generic errors to prevent user enumeration

## Tenant Isolation

- **Every table** includes a `tenant_id` foreign key
- **Every query** is scoped by the authenticated user's `tenant_id`
- There is no API endpoint that allows cross-tenant data access
- Tenant assignment is determined by email domain during SSO login
- Each user belongs to exactly one tenant

## Role-Based Access Control

- 4-tier hierarchy: OWNER > ADMIN > ANALYST > VIEWER
- All write endpoints require explicit role checks via FastAPI dependencies
- Higher roles inherit all lower role permissions
- Role is embedded in JWT, validated on every request

## Input Validation

- All API requests validated through **Pydantic 2.0** schemas
- Type checking, field constraints, and enum validation enforced automatically
- No raw SQL — all database queries go through **SQLAlchemy ORM** (parameterized)
- No file upload endpoints (eliminates remote code execution vectors)

## CORS Policy

```python
# Development
origins = ["http://localhost:3000"]

# Production
origins = ["https://*.getvul.app"]
```

- Credentials (cookies) allowed
- Methods and headers restricted to what's needed

## Network Security

- PostgreSQL connections via `asyncpg` (can be TLS-encrypted)
- Redis connections configurable with TLS
- CORS restricts browser-based cross-origin access
- Health check endpoint (`/health`) for load balancer probes

## Secret Management

| Secret | Storage | Notes |
|--------|---------|-------|
| JWT signing key | `JWT_SECRET_KEY` env var | Must be strong and unique per environment |
| Encryption key | `ENCRYPTION_KEY` env var | Fernet key for connector credentials |
| OIDC secrets | `GOOGLE_CLIENT_SECRET`, `AZURE_CLIENT_SECRET` | OAuth provider secrets |
| Database password | `DATABASE_URL` env var | In connection string |
| Connector credentials | Encrypted in DB | Fernet-encrypted JSON blobs |

**Production recommendation:** Store all secrets in AWS Secrets Manager and inject via environment at deploy time. Never commit secrets to source control.

## Dependency Security

- **Trivy** scans run in CI for CRITICAL and HIGH vulnerabilities in dependencies
- Python dependencies pinned in `pyproject.toml`
- Node dependencies pinned via `package-lock.json`
- Regular dependency updates recommended

## Known Limitations

| Limitation | Risk | Mitigation |
|------------|------|------------|
| No API rate limiting | DoS potential | Plan to add `slowapi` or API gateway rate limits |
| OIDC state in memory | Session fixation in multi-instance | Move state to Redis in production |
| No audit logging | Compliance gap | Plan to add user action audit trail |
| No 2FA | Account takeover | Relies on SSO provider's 2FA |
| No webhook signature verification | Spoofed webhooks | Implement HMAC verification |

## Security Best Practices for Deployment

1. **Rotate secrets** regularly (JWT key, encryption key)
2. **Enable TLS** for all services (API, database, Redis)
3. **Use private subnets** for database and Redis (no public access)
4. **Enable RDS encryption** at rest and in transit
5. **Configure security groups** to restrict network access
6. **Enable CloudWatch logging** for audit trail
7. **Set `DEBUG=false`** in production (disables dev routes and verbose errors)
8. **Review CORS origins** — only allow your production domain
9. **Monitor sync logs** for failed authentication attempts
10. **Keep dependencies updated** — run Trivy scans regularly
