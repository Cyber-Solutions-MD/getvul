# Deployment Guide

GetVul runs as five Docker Compose services on a single VM. This guide covers local development and production deployment on GCP, AWS, and Azure.

## Prerequisites

- Docker and Docker Compose v2
- Terraform >= 1.7
- Git access to the repository
- Domain name (optional, for TLS with Let's Encrypt)

## Architecture

```
┌─────────────────────────────────────────────┐
│  Single VM (2 vCPU, 4 GB RAM, 30 GB SSD)   │
│                                             │
│  ┌─────────┐   ┌──────────┐   ┌─────────┐  │
│  │  nginx   │──>│ backend  │   │ frontend│  │
│  │  :80/443 │   │  :8000   │   │  :3000  │  │
│  └─────────┘   └──────────┘   └─────────┘  │
│                  │       │                  │
│           ┌──────┘       └──────┐           │
│           v                     v           │
│  ┌──────────────┐      ┌─────────────┐      │
│  │  postgres     │      │    redis    │      │
│  │  :5432        │      │    :6379    │      │
│  └──────────────┘      └─────────────┘      │
└─────────────────────────────────────────────┘
```

- **nginx** -- Reverse proxy with TLS termination, security headers, rate limiting
- **backend** -- FastAPI application server, runs Alembic migrations on startup
- **frontend** -- Next.js 15 with React 19
- **postgres** -- PostgreSQL 16, data persisted via Docker volume
- **redis** -- Redis 7 for rate limiting and caching

Daily auto-update from GitHub checks for new commits at 3:00 AM UTC, rebuilds containers, and restarts. TLS is provided via a self-signed certificate generated on first boot, with options for custom certs or Let's Encrypt.

---

## Local Development

```bash
git clone <repo-url> && cd getvul
cp .env.example .env   # Edit with your secrets
docker compose up -d --build
```

### Access

| Endpoint | URL |
|----------|-----|
| Application (HTTPS) | `https://localhost` |
| Application (HTTP, redirects) | `http://localhost` |
| Frontend direct | `http://localhost:3000` |
| Backend API | `http://localhost:8000` |
| API docs (Swagger) | `http://localhost:8000/docs` |

Hot reload is enabled for both backend (Uvicorn `--reload`) and frontend (Next.js dev server with volume mount).

---

## Google Cloud Platform (GCP)

### Prerequisites

- GCP project with billing enabled
- `gcloud` CLI installed and authenticated (`gcloud auth application-default login`)
- SSH key pair (`~/.ssh/id_rsa` / `~/.ssh/id_rsa.pub`)

### Deploy

```bash
cd infra/gcp
terraform init
terraform plan \
  -var="project_id=YOUR_PROJECT_ID" \
  -var="ssh_public_key=$(cat ~/.ssh/id_rsa.pub)"
terraform apply \
  -var="project_id=YOUR_PROJECT_ID" \
  -var="ssh_public_key=$(cat ~/.ssh/id_rsa.pub)"
```

### What it creates

| Resource | Details |
|----------|---------|
| GCE VM | e2-medium (2 vCPU, 4 GB RAM), 30 GB SSD, Container-Optimized OS |
| Static external IP | `google_compute_address` |
| Firewall (web) | Ports 80 and 443 open to 0.0.0.0/0 |
| Firewall (SSH) | Port 22, restricted to `ssh_allowed_cidrs` |
| Service account | Dedicated SA with `cloud-platform` scope |
| Auto-update cron | Daily at 3:00 AM UTC |

### Terraform variables

| Variable | Default | Description |
|----------|---------|-------------|
| `project_id` | (required) | GCP project ID |
| `region` | `us-central1` | GCP region |
| `zone` | `us-central1-a` | GCP zone |
| `machine_type` | `e2-medium` | VM size |
| `disk_size_gb` | `30` | Boot disk size |
| `ssh_user` | `getvul` | SSH username |
| `ssh_public_key` | (required) | SSH public key |
| `ssh_allowed_cidrs` | `["0.0.0.0/0"]` | Restrict SSH source IPs |
| `github_repo` | (repo default) | GitHub repository (owner/repo) |
| `deploy_key` | `""` | SSH deploy key for private repos |

### Post-deploy

```bash
# SSH into the VM
ssh user@$(terraform output -raw ip_address)

# View the application
open https://$(terraform output -raw ip_address)

# View logs
docker compose -f /opt/getvul/docker-compose.yml logs -f

# Trigger a manual update
sudo /usr/local/bin/getvul-update
```

---

## Amazon Web Services (AWS)

### Prerequisites

- AWS account with credentials configured (`aws configure` or environment variables)
- SSH key pair (`~/.ssh/id_rsa` / `~/.ssh/id_rsa.pub`)

### Deploy

```bash
cd infra/aws
terraform init
terraform plan \
  -var="ssh_public_key=$(cat ~/.ssh/id_rsa.pub)"
terraform apply \
  -var="ssh_public_key=$(cat ~/.ssh/id_rsa.pub)"
```

### What it creates

| Resource | Details |
|----------|---------|
| EC2 instance | t3.medium (2 vCPU, 4 GB RAM), 30 GB gp3, Ubuntu 22.04 LTS |
| Elastic IP | `aws_eip` attached to the instance |
| Security group | Ports 80, 443 open to 0.0.0.0/0; port 22 restricted to `ssh_allowed_cidrs` |
| Key pair | Created from provided SSH public key |
| Auto-update cron | Daily at 3:00 AM UTC |

Uses the default VPC and first available subnet.

### Terraform variables

| Variable | Default | Description |
|----------|---------|-------------|
| `region` | `eu-west-1` | AWS region |
| `instance_type` | `t3.medium` | EC2 instance type |
| `disk_size_gb` | `30` | Root EBS volume size |
| `ssh_public_key` | (required) | SSH public key |
| `ssh_allowed_cidrs` | `["0.0.0.0/0"]` | Restrict SSH source IPs |
| `github_repo` | (repo default) | GitHub repository (owner/repo) |
| `deploy_key` | `""` | SSH deploy key for private repos |

### Post-deploy

```bash
# SSH into the instance
ssh ubuntu@$(terraform output -raw ip_address)

# View the application
open https://$(terraform output -raw ip_address)

# View logs
docker compose -f /opt/getvul/docker-compose.yml logs -f

# Trigger a manual update
sudo /usr/local/bin/getvul-update
```

---

## Microsoft Azure

### Prerequisites

- Azure subscription
- `az` CLI installed and authenticated (`az login`)
- SSH key pair (`~/.ssh/id_rsa` / `~/.ssh/id_rsa.pub`)

### Deploy

```bash
cd infra/azure
terraform init
terraform plan \
  -var="ssh_public_key=$(cat ~/.ssh/id_rsa.pub)"
terraform apply \
  -var="ssh_public_key=$(cat ~/.ssh/id_rsa.pub)"
```

### What it creates

| Resource | Details |
|----------|---------|
| Resource group | `getvul-rg` |
| Virtual network | `getvul-vnet` (10.0.0.0/16) with subnet (10.0.1.0/24) |
| Linux VM | Standard_B2s (2 vCPU, 4 GB RAM), 30 GB Premium SSD, Ubuntu 22.04 LTS |
| Public IP | Static, Standard SKU |
| NSG | Ports 80, 443 open; port 22 restricted to `ssh_allowed_cidrs` |
| NIC | With NSG association |
| Auto-update cron | Daily at 3:00 AM UTC |

### Terraform variables

| Variable | Default | Description |
|----------|---------|-------------|
| `location` | `westeurope` | Azure region |
| `vm_size` | `Standard_B2s` | VM size |
| `disk_size_gb` | `30` | OS disk size |
| `admin_username` | `getvul` | VM admin username |
| `ssh_public_key` | (required) | SSH public key |
| `ssh_allowed_cidrs` | `["0.0.0.0/0"]` | Restrict SSH source IPs |
| `github_repo` | (repo default) | GitHub repository (owner/repo) |
| `deploy_key` | `""` | SSH deploy key for private repos |

### Post-deploy

```bash
# SSH into the VM
ssh getvul@$(terraform output -raw ip_address)

# View the application
open https://$(terraform output -raw ip_address)

# View logs
docker compose -f /opt/getvul/docker-compose.yml logs -f

# Trigger a manual update
sudo /usr/local/bin/getvul-update
```

---

## Environment Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://user:pass@postgres:5432/getvul` |
| `REDIS_URL` | Redis connection string | `redis://redis:6379/0` |
| `JWT_SECRET_KEY` | Secret for signing JWTs (64+ random characters) | (generate with `openssl rand -hex 32`) |
| `ENCRYPTION_KEY` | Fernet key for encrypting stored credentials | (generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`) |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `development` | Set to `production` for production deployments |
| `DEBUG` | `true` | Set to `false` in production |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Access token lifetime |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed CORS origins (JSON array) |
| `RATE_LIMIT_REQUESTS` | `200` | Max requests per rate limit window |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Rate limit window in seconds |

### SMTP (for email and scheduled reports)

| Variable | Description |
|----------|-------------|
| SMTP host | Mail server hostname |
| SMTP port | Mail server port (587 for STARTTLS, 465 for SSL) |
| SMTP username | Authentication username |
| SMTP password | Authentication password |
| SMTP TLS | Enable TLS (toggle) |
| Sender email | From address for outgoing emails |

Configure these in **Settings > SMTP** within the application.

### SSO / OIDC

| Variable | Description |
|----------|-------------|
| `GOOGLE_CLIENT_ID` | Google OIDC client ID |
| `GOOGLE_CLIENT_SECRET` | Google OIDC client secret |
| `AZURE_CLIENT_ID` | Azure AD OIDC client ID |
| `AZURE_CLIENT_SECRET` | Azure AD OIDC client secret |
| `AZURE_TENANT_ID` | Azure AD tenant ID |

---

## TLS / SSL Certificates

### Self-signed (default)

A self-signed certificate is generated automatically on first boot by the nginx entrypoint. No action required. Browsers will show a security warning.

### Custom certificate (via UI)

1. Go to **Settings > General > TLS Certificate**
2. Paste the PEM-encoded certificate chain and private key
3. Nginx reloads automatically

### Let's Encrypt (manual)

```bash
# Install certbot on the VM
sudo apt install certbot

# Obtain certificate
sudo certbot certonly --webroot -w /opt/getvul/certbot-webroot -d your-domain.example.com

# Copy to nginx cert directory
sudo cp /etc/letsencrypt/live/your-domain.example.com/fullchain.pem /opt/getvul/nginx/certs/server.crt
sudo cp /etc/letsencrypt/live/your-domain.example.com/privkey.pem /opt/getvul/nginx/certs/server.key

# Restart nginx
docker compose -f /opt/getvul/docker-compose.yml restart nginx
```

### Any CA-signed certificate

```bash
cp your-cert-chain.pem /opt/getvul/nginx/certs/server.crt
cp your-private-key.pem /opt/getvul/nginx/certs/server.key
docker compose -f /opt/getvul/docker-compose.yml restart nginx
```

---

## Database

- **Engine:** PostgreSQL 16 running in Docker (`postgres:16-alpine`)
- **Persistence:** Docker named volume (survives container restarts)
- **Migrations:** Alembic runs `upgrade head` automatically on backend startup
- **Total migrations:** 22 (from initial schema through notifications)

### Backup

```bash
# Dump the database
docker compose -f /opt/getvul/docker-compose.yml exec postgres \
  pg_dump -U getvul getvul > backup_$(date +%Y%m%d).sql

# Restore from backup
docker compose -f /opt/getvul/docker-compose.yml exec -T postgres \
  psql -U getvul getvul < backup_20260101.sql
```

### Manual migration commands

```bash
# Apply all pending migrations
docker compose exec backend alembic upgrade head

# Rollback one migration
docker compose exec backend alembic downgrade -1

# Create a new migration
docker compose exec backend alembic revision --autogenerate -m "description"
```

---

## Auto-Update System

A cron job installed by the startup script runs daily at **3:00 AM UTC**:

1. Checks the GitHub repository for new commits on the default branch
2. Pulls the latest code to `/opt/getvul`
3. Rebuilds Docker images and restarts containers (`docker compose up -d --build`)
4. Runs a health check against the backend API
5. Logs all activity to `/var/log/getvul-update.log`

### Manual trigger

```bash
sudo /usr/local/bin/getvul-update
```

### View update logs

```bash
sudo tail -f /var/log/getvul-update.log
```

---

## CI/CD Pipeline

The repository includes a GitHub Actions workflow with five jobs, triggered on push/PR to `main` or manually via `workflow_dispatch`.

| Job | What it does |
|-----|-------------|
| **Backend** | ruff lint + format, mypy type check, Alembic migrations, pytest with coverage |
| **Frontend** | npm install, ESLint, TypeScript type check (`tsc`), production build |
| **Terraform Validate** | `terraform fmt -check`, `terraform init`, `terraform validate` |
| **Semgrep SAST** | Static analysis with p/default, p/owasp-top-ten, p/secrets, p/dockerfile rulesets |
| **OWASP ZAP DAST** | API scan (OpenAPI spec), baseline scan against backend and frontend |

---

## Production Checklist

- [ ] Generate and set a strong `JWT_SECRET_KEY` (`openssl rand -hex 32`)
- [ ] Generate and set a unique `ENCRYPTION_KEY` (Fernet key)
- [ ] Set `ENVIRONMENT=production` and `DEBUG=false`
- [ ] Configure SMTP for email delivery (scheduled reports, notifications)
- [ ] Install a proper TLS certificate (Let's Encrypt or CA-signed)
- [ ] Restrict `ssh_allowed_cidrs` to known IP ranges
- [ ] Configure `CORS_ORIGINS` for your production domain
- [ ] Set up Google and/or Azure OIDC credentials for SSO
- [ ] Create the initial admin user
- [ ] Configure at least one vulnerability connector
- [ ] Set SLA policy per severity level
- [ ] Configure syslog forwarding to your SIEM
- [ ] Verify database backup strategy
- [ ] Review rate limiting configuration
- [ ] Run the CI pipeline (Semgrep + ZAP) before going live
