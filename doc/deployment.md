# Deployment & Configuration

## Local Development

### Prerequisites
- Docker and Docker Compose
- (Optional) Python 3.12, Node.js 20 for running outside containers

### Quick Start

```bash
# Clone the repository
git clone <repo-url> && cd getvul

# Copy environment template
cp .env.example .env
# Edit .env with your secrets (JWT key, OIDC credentials, encryption key)

# Start all services
make dev
# OR
docker compose up --build
```

- **Frontend:** http://localhost:3000
- **API:** http://localhost:8000
- **Swagger docs:** http://localhost:8000/docs
- **PostgreSQL:** localhost:5432
- **Redis:** localhost:6379

### Seed Demo Data
```bash
curl -X POST http://localhost:8000/dev/seed
```
Creates a demo tenant, admin user, 20 assets, and 300 vulnerabilities with realistic data.

---

## Docker Compose Services

```yaml
services:
  postgres:    # PostgreSQL 16-alpine, port 5432
  redis:       # Redis 7-alpine, port 6379
  backend:     # FastAPI app, port 8000
  frontend:    # Next.js app, port 3000
```

### Service Details

**postgres**
- Image: `postgres:16-alpine`
- Health check: `pg_isready`
- Persistent volume for data
- Default database: `getvul`

**redis**
- Image: `redis:7-alpine`
- Health check: `redis-cli ping`
- Used for caching and optional token blocklist

**backend**
- Built from `backend/Dockerfile`
- Startup: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`
- Volume mount: `./backend:/app` (live reload in dev)
- Depends on: postgres (healthy), redis (healthy)

**frontend**
- Built from `frontend/Dockerfile`
- Startup: `npm run dev`
- Volume mount: `./frontend:/app` with `/app/node_modules` excluded
- Depends on: backend

---

## Environment Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://user:pass@postgres:5432/getvul` |
| `REDIS_URL` | Redis connection string | `redis://redis:6379/0` |
| `JWT_SECRET_KEY` | Secret for signing JWTs (change in prod!) | `your-secret-key-here` |
| `ENCRYPTION_KEY` | Fernet key for encrypting credentials | Base64-encoded 32-byte key |

### Authentication (SSO)

| Variable | Description |
|----------|-------------|
| `GOOGLE_CLIENT_ID` | Google OAuth 2.0 client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth 2.0 client secret |
| `GOOGLE_REDIRECT_URI` | Google callback URL |
| `AZURE_CLIENT_ID` | Azure Entra ID client ID |
| `AZURE_CLIENT_SECRET` | Azure Entra ID client secret |
| `AZURE_REDIRECT_URI` | Azure callback URL |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `development` | `development` or `production` |
| `DEBUG` | `true` | Enable debug mode |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Access token lifetime |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime |
| `SYNC_INTERVAL_MINUTES` | `15` | Default connector sync interval |
| `AWS_REGION` | `us-east-1` | AWS region for Secrets Manager |
| `SECRETS_MANAGER_PREFIX` | | AWS Secrets Manager key prefix |

### Generating an Encryption Key

```python
from cryptography.fernet import Fernet
key = Fernet.generate_key()
print(key.decode())  # Use this as ENCRYPTION_KEY
```

---

## Database Migrations

Migrations are managed by Alembic and run automatically on container startup.

```bash
# Apply all migrations
cd backend && alembic upgrade head

# Create a new migration
alembic revision --autogenerate -m "description"

# View migration history
alembic history

# Rollback one migration
alembic downgrade -1
```

### Migration History
| Version | Description |
|---------|-------------|
| 001 | Initial schema (tenants, users, assets, vulns, connectors, tickets) |
| 002 | Add misconfigurations table (CSPM) |
| 003 | Widen credentials column for encrypted JSON |
| 004 | Add remediation fields (remediation_id, action, exploit status) |
| 005 | Add device_category enum and Jamf MDM fields to assets |

---

## CI/CD Pipeline

GitHub Actions workflow (`.github/workflows/ci.yml`) runs on push to `main` and pull requests.

### Jobs

**Backend**
1. Set up Python 3.12
2. Install dependencies
3. `ruff check` — linting
4. `ruff format --check` — formatting
5. `mypy` — type checking
6. Run database migrations (test DB)
7. `pytest --cov` — tests with coverage

**Frontend**
1. Set up Node.js 20
2. `npm install`
3. `npm run lint` — ESLint
4. `npx tsc --noEmit` — TypeScript type check
5. `npm run build` — production build

**Terraform**
1. `terraform validate` — configuration validation
2. `terraform fmt -check` — formatting check

**Security**
1. Trivy filesystem scan for CRITICAL and HIGH vulnerabilities

---

## Infrastructure (Terraform)

Located in `infra/`. Currently a placeholder with AWS provider setup.

```hcl
terraform {
  required_version = ">= 1.7"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

variable "aws_region" { default = "us-east-1" }
variable "environment" { default = "production" }
```

### Planned Infrastructure
- AWS ECS Fargate for backend and frontend containers
- AWS RDS PostgreSQL for database
- AWS ElastiCache Redis for caching
- AWS ALB for load balancing
- AWS VPC with public/private subnets
- AWS Secrets Manager for credential storage
- AWS CloudWatch for logging and monitoring

---

## Production Considerations

### Security
- Change `JWT_SECRET_KEY` to a strong random value
- Generate a unique `ENCRYPTION_KEY` per environment
- Set `ENVIRONMENT=production` and `DEBUG=false`
- Configure CORS to only allow your production domain
- Use HTTPS/TLS for all traffic
- Store secrets in AWS Secrets Manager (not `.env`)

### Database
- Use AWS RDS with encryption at rest and in transit
- Enable automated backups
- Configure connection pooling (pool_size=20, max_overflow=10 are defaults)
- Monitor with `pool_pre_ping=True` for connection health

### Scaling
- Backend is stateless — horizontally scalable behind a load balancer
- Redis handles shared state (token blocklist, sync coordination)
- Database connection pool tuning for concurrent requests
- Consider read replicas for heavy dashboard queries

### Monitoring
- Health check endpoint: `GET /health`
- Sync logs in `sync_logs` table for connector monitoring
- structlog for structured JSON logging in production
- Plan: Prometheus metrics, Grafana dashboards
