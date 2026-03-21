# Deployment & Configuration

## Local Development

### Prerequisites
- Docker and Docker Compose

### Quick Start
```bash
git clone <repo-url> && cd getvul
cp .env.example .env  # Edit with your secrets
docker compose up --build
```

### Services
| Service | Port | Description |
|---------|------|-------------|
| nginx | 80, 443 | Reverse proxy with TLS |
| backend | 8000 | FastAPI API |
| frontend | 3000 | Next.js app |
| postgres | 5432 | PostgreSQL 16 |
| redis | 6379 | Redis 7 |

### Access
- **HTTPS**: https://localhost (self-signed cert auto-generated)
- **HTTP**: http://localhost (redirects to HTTPS)
- **API docs**: http://localhost:8000/docs
- **Direct frontend**: http://localhost:3000

## Docker Compose Services

### nginx
- Image: nginx:alpine
- Custom entrypoint generates self-signed cert if none exists
- TLS 1.2/1.3 with security headers
- Rate limiting (30 req/s API, 5 req/s auth)
- Proxies to backend (API/auth) and frontend (UI)

### backend
- Built from `backend/Dockerfile`
- Runs Alembic migrations on startup
- Uvicorn with --reload for development
- Mounts `./nginx/certs` for certificate management

### frontend
- Built from `frontend/Dockerfile`
- Next.js 15 with React 19
- Hot reload via volume mount

## Environment Variables

### Required
| Variable | Description |
|----------|-------------|
| DATABASE_URL | PostgreSQL connection string |
| REDIS_URL | Redis connection string |
| JWT_SECRET_KEY | Secret for signing JWTs |
| ENCRYPTION_KEY | Fernet key for encrypting connector credentials |

### Optional
| Variable | Default | Description |
|----------|---------|-------------|
| ENVIRONMENT | development | development or production |
| DEBUG | true | Enable debug mode |
| JWT_ACCESS_TOKEN_EXPIRE_MINUTES | 15 | Access token lifetime |
| JWT_REFRESH_TOKEN_EXPIRE_DAYS | 7 | Refresh token lifetime |
| GOOGLE_CLIENT_ID/SECRET | | Google OIDC credentials |
| AZURE_CLIENT_ID/SECRET | | Azure OIDC credentials |

## TLS Certificate Management

### Via UI (Settings → General → TLS Certificate)
1. **Upload custom cert**: Paste PEM certificate + private key
2. **Generate self-signed**: Enter hostname, auto-generates with OpenSSL
3. **Remove**: Delete installed cert (reverts to HTTP only)

### Via command line
```bash
# Let's Encrypt
certbot certonly --webroot -w ./certbot-webroot -d yourdomain.com
cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem nginx/certs/server.crt
cp /etc/letsencrypt/live/yourdomain.com/privkey.pem nginx/certs/server.key
docker compose restart nginx

# Microsoft CA
# Export cert chain as PEM, copy to nginx/certs/
```

## Database Migrations

```bash
# Apply all migrations
docker compose exec backend alembic upgrade head

# Current migrations (16):
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
```

## Background Scheduler

The backend runs a background scheduler that:
1. Checks all enabled connectors every 60 seconds
2. Triggers sync when interval has elapsed
3. Runs ticket automation rules
4. Syncs in parallel (one task per connector)

## Production Checklist

- [ ] Change JWT_SECRET_KEY to a strong random value
- [ ] Generate unique ENCRYPTION_KEY
- [ ] Set ENVIRONMENT=production, DEBUG=false
- [ ] Install proper TLS certificate (Let's Encrypt or CA-signed)
- [ ] Configure CORS for production domain
- [ ] Set up Google/Azure OIDC credentials
- [ ] Enable SSO enforcement
- [ ] Configure syslog forwarding to SIEM
- [ ] Set password policy (complexity + history)
- [ ] Review and restrict database access
- [ ] Enable automated backups for PostgreSQL
