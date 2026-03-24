# Deployment and Configuration

## Local Development

### Prerequisites
- Docker and Docker Compose

### Quick Start
```bash
git clone <repo-url> && cd getvul
cp .env.example .env  # Edit with your secrets
docker compose up --build
```

### Services (5 total)
| Service | Port | Description |
|---------|------|-------------|
| nginx | 80, 443 | Reverse proxy with TLS termination |
| backend | 8000 | FastAPI API server |
| frontend | 3000 | Next.js application |
| postgres | 5432 | PostgreSQL 16 database |
| redis | 6379 | Redis 7 cache |

### Access
- **HTTPS:** `https://localhost` (self-signed cert auto-generated)
- **HTTP:** `http://localhost` (redirects to HTTPS)
- **API docs:** `http://localhost:8000/docs`
- **Direct frontend:** `http://localhost:3000`

## Docker Compose Services

### nginx
- Image: nginx:alpine
- Custom entrypoint generates self-signed cert if none exists
- TLS 1.2/1.3 with modern cipher suites
- Security headers on all responses
- Rate limiting: configurable per endpoint type
- H2C smuggling protection
- Proxies `/api` and `/auth` to backend, everything else to frontend

### backend
- Built from `backend/Dockerfile`
- Runs Alembic migrations on startup (`alembic upgrade head`)
- Uvicorn with `--reload` for development
- Mounts `./nginx/certs` for certificate management
- APScheduler background jobs for connector sync, ticket automation, daily snapshots

### frontend
- Built from `frontend/Dockerfile`
- Next.js 15 with React 19
- Hot reload via volume mount in development

### postgres
- Image: postgres:16-alpine
- Data persisted via Docker volume
- JSONB columns for flexible metadata

### redis
- Image: redis:7-alpine
- Used for rate limiting and caching

## Environment Variables

### Required
| Variable | Description | Example |
|----------|-------------|---------|
| DATABASE_URL | PostgreSQL connection string | `postgresql+asyncpg://user:pass@postgres:5432/getvul` |
| REDIS_URL | Redis connection string | `redis://redis:6379/0` |
| JWT_SECRET_KEY | Secret for signing JWTs | (random 64-char string) |
| ENCRYPTION_KEY | Fernet key for encrypting credentials | (use `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`) |

### Optional
| Variable | Default | Description |
|----------|---------|-------------|
| ENVIRONMENT | development | `development` or `production` |
| DEBUG | true | Enable debug mode |
| JWT_ACCESS_TOKEN_EXPIRE_MINUTES | 15 | Access token lifetime |
| JWT_REFRESH_TOKEN_EXPIRE_DAYS | 7 | Refresh token lifetime |
| GOOGLE_CLIENT_ID | | Google OIDC client ID |
| GOOGLE_CLIENT_SECRET | | Google OIDC client secret |
| AZURE_CLIENT_ID | | Azure OIDC client ID |
| AZURE_CLIENT_SECRET | | Azure OIDC client secret |
| AZURE_TENANT_ID | | Azure AD tenant ID |
| CORS_ORIGINS | `["http://localhost:3000"]` | Allowed CORS origins |
| RATE_LIMIT_REQUESTS | 200 | Max requests per window |
| RATE_LIMIT_WINDOW_SECONDS | 60 | Rate limit window |

## TLS Certificate Management

### Via UI (Settings, then TLS Certificate)
1. **Upload custom cert:** Paste PEM certificate + private key
2. **Generate self-signed:** Enter hostname, auto-generates with OpenSSL
3. **Remove:** Delete installed cert

### Via command line
```bash
# Let's Encrypt
certbot certonly --webroot -w ./certbot-webroot -d your-org.example.com
cp /etc/letsencrypt/live/your-org.example.com/fullchain.pem nginx/certs/server.crt
cp /etc/letsencrypt/live/your-org.example.com/privkey.pem nginx/certs/server.key
docker compose restart nginx

# Any CA-signed certificate
# Export cert chain as PEM, copy to nginx/certs/
cp your-cert.pem nginx/certs/server.crt
cp your-key.pem nginx/certs/server.key
docker compose restart nginx
```

## Database Migrations

```bash
# Apply all migrations
docker compose exec backend alembic upgrade head

# Current migrations (21):
# 001 Initial schema
# 002 Misconfigurations (CSPM)
# 003 Widen credentials column
# 004 Remediation fields
# 005 Device category + Jamf
# 006 CrowdStrike device fields
# 007 Ticket rule schedule
# 008 Saved filters
# 009 Link rules to filters
# 010 Vulnerability file paths
# 011 Password authentication
# 012 User groups
# 013 Audit log
# 014 Syslog config
# 015 Tenant timezone
# 016 Password policy
# 017 Scheduled reports
# 018 SMTP config
# 019 Asset ignored flag
# 020 SLA tracking
# 021 Daily snapshots

# Create a new migration
docker compose exec backend alembic revision --autogenerate -m "description"

# Rollback one migration
docker compose exec backend alembic downgrade -1
```

## Background Scheduler

The backend runs APScheduler background tasks that:
1. Check all enabled connectors every 60 seconds, trigger sync when interval has elapsed
2. Run ticket automation rules on their configured schedules
3. Execute daily status sync for open tickets (check external providers, post progress, auto-close)
4. Generate daily metric snapshots for trend analytics
5. Send scheduled reports via SMTP

## SMTP Configuration

Configure email delivery for scheduled reports in Settings:
- SMTP host and port
- Authentication (username/password)
- TLS toggle
- Sender email address
- Test connection and test email buttons available

## CI/CD Pipeline (5 Jobs)

| Job | Description |
|-----|-------------|
| **Backend** | ruff lint + format, mypy type check, alembic migrations, pytest with coverage |
| **Frontend** | npm install, lint, type check (tsc), production build |
| **Terraform** | fmt check, init, validate |
| **Semgrep SAST** | p/default + p/owasp-top-ten + p/secrets + p/dockerfile (published to semgrep.dev) |
| **OWASP ZAP DAST** | API scan (OpenAPI), baseline scan (backend), baseline scan (frontend) |

## Production Checklist

- [ ] Set `JWT_SECRET_KEY` to a strong random value (64+ characters)
- [ ] Generate unique `ENCRYPTION_KEY` with Fernet
- [ ] Set `ENVIRONMENT=production`, `DEBUG=false`
- [ ] Install proper TLS certificate (Let's Encrypt or CA-signed)
- [ ] Configure `CORS_ORIGINS` for production domain
- [ ] Set up Google/Azure OIDC credentials for SSO
- [ ] Enable SSO enforcement for the organization
- [ ] Configure password policy (complexity + history)
- [ ] Set SLA policy per severity level
- [ ] Configure syslog forwarding to SIEM
- [ ] Configure SMTP for scheduled report delivery
- [ ] Review and restrict database network access
- [ ] Enable automated backups for PostgreSQL
- [ ] Set up monitoring and alerting for connector sync failures
- [ ] Review rate limiting configuration
- [ ] Run Semgrep scan before deploying
- [ ] Configure pre-commit hook for developer workstations
