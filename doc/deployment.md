# Deployment Guide

GetVul runs as five Docker Compose services on a single VM. This guide covers local development and production deployment on GCP, AWS, and Azure with detailed step-by-step instructions.

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

### Step 1: Install prerequisites

```bash
# Install Google Cloud CLI
# macOS:
brew install --cask google-cloud-sdk

# Linux:
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# Verify installation
gcloud --version
terraform --version
```

### Step 2: Authenticate and select project

```bash
# Login to GCP
gcloud auth login

# Set application default credentials (used by Terraform)
gcloud auth application-default login

# List your projects
gcloud projects list

# Set your project
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable compute.googleapis.com
gcloud services enable iam.googleapis.com
```

### Step 3: Prepare SSH key

```bash
# Generate a new SSH key pair if you don't have one
ssh-keygen -t ed25519 -C "getvul-deploy" -f ~/.ssh/getvul

# Or use your existing key
cat ~/.ssh/id_rsa.pub  # verify it exists
```

### Step 4: Deploy with Terraform

```bash
# Navigate to the GCP infrastructure directory
cd infra/gcp

# Initialize Terraform (downloads the Google provider)
terraform init

# Preview what will be created
terraform plan \
  -var="project_id=YOUR_PROJECT_ID" \
  -var="ssh_public_key=$(cat ~/.ssh/getvul.pub)"

# Review the plan carefully, then apply
terraform apply \
  -var="project_id=YOUR_PROJECT_ID" \
  -var="ssh_public_key=$(cat ~/.ssh/getvul.pub)"

# Type 'yes' when prompted
```

### Step 5: Verify the deployment

```bash
# Get the public IP
terraform output ip_address

# SSH into the VM (wait 2-3 minutes for startup script to complete)
ssh -i ~/.ssh/getvul getvul@$(terraform output -raw ip_address)

# Once inside the VM, check Docker containers are running
docker compose -f /opt/getvul/docker-compose.yml ps

# Check the startup script log for any errors
sudo cat /var/log/syslog | grep startup-script | tail -50

# View application logs
docker compose -f /opt/getvul/docker-compose.yml logs -f backend
```

### Step 6: Access the application

```bash
# Open in browser (self-signed cert warning is expected)
open https://$(terraform output -raw ip_address)
```

### Step 7: Configure the environment

```bash
# SSH into the VM
ssh -i ~/.ssh/getvul getvul@$(terraform output -raw ip_address)

# Edit the environment file
sudo nano /opt/getvul/.env

# Set these required values:
# JWT_SECRET_KEY=<run: openssl rand -hex 32>
# ENCRYPTION_KEY=<run: python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
# DATABASE_URL=postgresql+asyncpg://getvul:getvul@postgres:5432/getvul
# REDIS_URL=redis://redis:6379/0

# Restart after editing
cd /opt/getvul && docker compose up -d
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

### Restrict SSH access (recommended)

```bash
# Only allow SSH from your office IP
terraform apply \
  -var="project_id=YOUR_PROJECT_ID" \
  -var="ssh_public_key=$(cat ~/.ssh/getvul.pub)" \
  -var='ssh_allowed_cidrs=["203.0.113.0/24"]'
```

### Teardown

```bash
cd infra/gcp
terraform destroy \
  -var="project_id=YOUR_PROJECT_ID" \
  -var="ssh_public_key=$(cat ~/.ssh/getvul.pub)"
```

---

## Amazon Web Services (AWS)

### Step 1: Install prerequisites

```bash
# Install AWS CLI
# macOS:
brew install awscli

# Linux:
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip && sudo ./aws/install

# Verify installation
aws --version
terraform --version
```

### Step 2: Configure AWS credentials

```bash
# Option A: Interactive configuration
aws configure
# Enter: AWS Access Key ID, Secret Access Key, Region (eu-west-1), Output format (json)

# Option B: Environment variables
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="eu-west-1"

# Verify credentials work
aws sts get-caller-identity
```

### Step 3: Prepare SSH key

```bash
# Generate a new SSH key pair if you don't have one
ssh-keygen -t ed25519 -C "getvul-deploy" -f ~/.ssh/getvul

# Or use your existing key
cat ~/.ssh/id_rsa.pub  # verify it exists
```

### Step 4: Deploy with Terraform

```bash
# Navigate to the AWS infrastructure directory
cd infra/aws

# Initialize Terraform (downloads the AWS provider)
terraform init

# Preview what will be created
terraform plan \
  -var="ssh_public_key=$(cat ~/.ssh/getvul.pub)"

# Review the plan carefully, then apply
terraform apply \
  -var="ssh_public_key=$(cat ~/.ssh/getvul.pub)"

# Type 'yes' when prompted
```

### Step 5: Verify the deployment

```bash
# Get the Elastic IP
terraform output instance_ip

# SSH into the instance (wait 3-5 minutes for user data script to complete)
ssh -i ~/.ssh/getvul ubuntu@$(terraform output -raw instance_ip)

# Once inside, check Docker containers
docker compose -f /opt/getvul/docker-compose.yml ps

# Check the user data startup log
sudo cat /var/log/cloud-init-output.log | tail -100

# View application logs
docker compose -f /opt/getvul/docker-compose.yml logs -f backend
```

### Step 6: Access the application

```bash
# Open in browser (self-signed cert warning is expected)
open https://$(terraform output -raw instance_ip)
```

### Step 7: Configure the environment

```bash
# SSH into the instance
ssh -i ~/.ssh/getvul ubuntu@$(terraform output -raw instance_ip)

# Edit the environment file
sudo nano /opt/getvul/.env

# Set these required values:
# JWT_SECRET_KEY=<run: openssl rand -hex 32>
# ENCRYPTION_KEY=<run: python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
# DATABASE_URL=postgresql+asyncpg://getvul:getvul@postgres:5432/getvul
# REDIS_URL=redis://redis:6379/0

# Restart after editing
cd /opt/getvul && docker compose up -d
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

### Deploy to a different region

```bash
terraform apply \
  -var="ssh_public_key=$(cat ~/.ssh/getvul.pub)" \
  -var="region=us-east-1"
```

### Restrict SSH access (recommended)

```bash
terraform apply \
  -var="ssh_public_key=$(cat ~/.ssh/getvul.pub)" \
  -var='ssh_allowed_cidrs=["203.0.113.0/24"]'
```

### Teardown

```bash
cd infra/aws
terraform destroy \
  -var="ssh_public_key=$(cat ~/.ssh/getvul.pub)"
```

---

## Microsoft Azure

### Step 1: Install prerequisites

```bash
# Install Azure CLI
# macOS:
brew install azure-cli

# Linux (Ubuntu/Debian):
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Windows:
# Download from https://learn.microsoft.com/en-us/cli/azure/install-azure-cli-windows

# Verify installation
az --version
terraform --version
```

### Step 2: Authenticate to Azure

```bash
# Login to Azure (opens browser for authentication)
az login

# List your subscriptions
az account list --output table

# Set the subscription to use (if you have multiple)
az account set --subscription "YOUR_SUBSCRIPTION_ID"

# Verify the active subscription
az account show --output table
```

### Step 3: Prepare SSH key

```bash
# Generate a new SSH key pair if you don't have one
ssh-keygen -t ed25519 -C "getvul-deploy" -f ~/.ssh/getvul

# Or use your existing key
cat ~/.ssh/id_rsa.pub  # verify it exists
```

### Step 4: Deploy with Terraform

```bash
# Navigate to the Azure infrastructure directory
cd infra/azure

# Initialize Terraform (downloads the Azure provider)
terraform init

# Preview what will be created
terraform plan \
  -var="ssh_public_key=$(cat ~/.ssh/getvul.pub)"

# Review the plan carefully — note the resource group, VM, VNet, NSG, and public IP
# Then apply
terraform apply \
  -var="ssh_public_key=$(cat ~/.ssh/getvul.pub)"

# Type 'yes' when prompted
# This typically takes 2-4 minutes to provision all Azure resources
```

### Step 5: Verify the deployment

```bash
# Get the public IP address
terraform output vm_ip

# SSH into the VM (wait 3-5 minutes for custom_data script to complete)
ssh -i ~/.ssh/getvul getvul@$(terraform output -raw vm_ip)

# Once inside the VM, check Docker containers are running
docker compose -f /opt/getvul/docker-compose.yml ps

# Expected output: 5 containers (nginx, backend, frontend, postgres, redis) all "Up"

# If containers aren't running yet, check the startup script progress
sudo cat /var/log/cloud-init-output.log | tail -100

# Look for "Docker Compose started successfully" at the end of the log

# View application logs
docker compose -f /opt/getvul/docker-compose.yml logs -f backend
```

### Step 6: Access the application

```bash
# Open in browser (self-signed cert warning is expected)
open https://$(terraform output -raw vm_ip)

# In Chrome: click "Advanced" > "Proceed to <ip> (unsafe)" to bypass self-signed cert warning
# In Firefox: click "Advanced" > "Accept the Risk and Continue"
```

### Step 7: Configure the environment

```bash
# SSH into the VM
ssh -i ~/.ssh/getvul getvul@$(terraform output -raw vm_ip)

# Edit the environment file
sudo nano /opt/getvul/.env

# Set these required values:
# JWT_SECRET_KEY=<run: openssl rand -hex 32>
# ENCRYPTION_KEY=<run: python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
# DATABASE_URL=postgresql+asyncpg://getvul:getvul@postgres:5432/getvul
# REDIS_URL=redis://redis:6379/0

# Restart after editing
cd /opt/getvul && docker compose up -d
```

### Step 8: Set up a custom domain (optional)

```bash
# 1. Get the public IP
terraform output vm_ip

# 2. Create a DNS A record pointing your domain to this IP
#    Example: getvul.your-company.com → <public-ip>

# 3. SSH into the VM and install Let's Encrypt
ssh -i ~/.ssh/getvul getvul@$(terraform output -raw vm_ip)
sudo apt install -y certbot
sudo certbot certonly --standalone -d getvul.your-company.com
sudo cp /etc/letsencrypt/live/getvul.your-company.com/fullchain.pem /opt/getvul/nginx/certs/server.crt
sudo cp /etc/letsencrypt/live/getvul.your-company.com/privkey.pem /opt/getvul/nginx/certs/server.key
cd /opt/getvul && docker compose restart nginx
```

### What it creates

| Resource | Details |
|----------|---------|
| Resource group | `getvul-rg` in your chosen region |
| Virtual network | `getvul-vnet` (10.0.0.0/16) with subnet `getvul-subnet` (10.0.1.0/24) |
| Network security group | `getvul-nsg` with rules for HTTP (80), HTTPS (443), and SSH (22) |
| Public IP address | Static Standard SKU (`getvul-ip`) |
| Network interface | `getvul-nic` with NSG and public IP attached |
| Linux VM | `getvul-vm`, Standard_B2s (2 vCPU, 4 GB RAM), 30 GB Premium SSD, Ubuntu 22.04 LTS |
| Auto-update cron | Daily at 3:00 AM UTC (pulls latest code, rebuilds containers) |

### Terraform variables

| Variable | Default | Description |
|----------|---------|-------------|
| `location` | `westeurope` | Azure region (e.g., `eastus`, `westus2`, `northeurope`) |
| `vm_size` | `Standard_B2s` | VM size (2 vCPU, 4 GB RAM) |
| `disk_size_gb` | `30` | OS disk size in GB |
| `admin_username` | `getvul` | VM admin username for SSH |
| `ssh_public_key` | (required) | Your SSH public key content |
| `ssh_allowed_cidrs` | `["0.0.0.0/0"]` | IP ranges allowed for SSH (restrict in production) |
| `github_repo` | (repo default) | GitHub repository in `owner/repo` format |
| `deploy_key` | `""` | SSH deploy key for private repos |

### Deploy to a different region

```bash
terraform apply \
  -var="ssh_public_key=$(cat ~/.ssh/getvul.pub)" \
  -var="location=eastus"
```

### Use a larger VM

```bash
# For larger deployments (500+ assets)
terraform apply \
  -var="ssh_public_key=$(cat ~/.ssh/getvul.pub)" \
  -var="vm_size=Standard_B2ms" \
  -var="disk_size_gb=50"
```

### Restrict SSH access (recommended for production)

```bash
# Only allow SSH from your office IP range
terraform apply \
  -var="ssh_public_key=$(cat ~/.ssh/getvul.pub)" \
  -var='ssh_allowed_cidrs=["203.0.113.0/24"]'
```

### Verify Azure resources via CLI

```bash
# List all resources in the resource group
az resource list --resource-group getvul-rg --output table

# Check VM status
az vm show --resource-group getvul-rg --name getvul-vm --show-details --output table

# View NSG rules
az network nsg rule list --resource-group getvul-rg --nsg-name getvul-nsg --output table
```

### Teardown

```bash
cd infra/azure
terraform destroy \
  -var="ssh_public_key=$(cat ~/.ssh/getvul.pub)"

# Or delete the entire resource group via Azure CLI (faster)
az group delete --name getvul-rg --yes --no-wait
```

---

## Private Repository Access

If your GetVul repository is private, you need a deploy key so the VM can clone and pull updates.

### Generate a deploy key

```bash
# Generate a dedicated key (no passphrase)
ssh-keygen -t ed25519 -C "getvul-deploy-key" -f ~/.ssh/getvul-deploy -N ""

# Add the PUBLIC key to your GitHub repo:
# GitHub > Repo > Settings > Deploy keys > Add deploy key
cat ~/.ssh/getvul-deploy.pub

# Pass the PRIVATE key to Terraform
terraform apply \
  -var="ssh_public_key=$(cat ~/.ssh/getvul.pub)" \
  -var="deploy_key=$(cat ~/.ssh/getvul-deploy)"
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

### Let's Encrypt

```bash
# SSH into the VM
ssh -i ~/.ssh/getvul <user>@<ip>

# Stop nginx temporarily to free port 80
cd /opt/getvul && docker compose stop nginx

# Install certbot and obtain certificate
sudo apt install -y certbot
sudo certbot certonly --standalone -d your-domain.example.com

# Copy to nginx cert directory
sudo cp /etc/letsencrypt/live/your-domain.example.com/fullchain.pem /opt/getvul/nginx/certs/server.crt
sudo cp /etc/letsencrypt/live/your-domain.example.com/privkey.pem /opt/getvul/nginx/certs/server.key

# Restart nginx
docker compose up -d nginx

# Set up auto-renewal (runs twice daily)
echo "0 */12 * * * root certbot renew --quiet --deploy-hook 'cd /opt/getvul && docker compose restart nginx'" | sudo tee /etc/cron.d/certbot-renew
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
- **Total migrations:** 24 (from initial schema through containment status)

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

### Disable auto-update

```bash
# Remove the cron job
sudo rm /etc/cron.d/getvul-update
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

## Troubleshooting

### Containers not starting after deploy

```bash
# Check startup script output
sudo cat /var/log/cloud-init-output.log | tail -100  # AWS/Azure
sudo cat /var/log/syslog | grep startup-script        # GCP

# Check Docker is running
sudo systemctl status docker

# Try starting manually
cd /opt/getvul && docker compose up -d --build
```

### Backend crashes on startup

```bash
# Check backend logs
docker compose -f /opt/getvul/docker-compose.yml logs backend

# Common issues:
# - Missing .env file → copy .env.example and set values
# - Database not ready → wait for postgres healthcheck, then restart backend
# - Migration conflict → docker compose exec backend alembic upgrade head
```

### Cannot access the web UI

```bash
# Verify nginx is running
docker compose -f /opt/getvul/docker-compose.yml ps nginx

# Check if ports are open (from your local machine)
curl -k https://<vm-ip>

# Check firewall/security group rules
# GCP: gcloud compute firewall-rules list
# AWS: aws ec2 describe-security-groups
# Azure: az network nsg rule list --resource-group getvul-rg --nsg-name getvul-nsg
```

### Auto-update not working

```bash
# Check the cron job exists
cat /etc/cron.d/getvul-update

# Run manually and check output
sudo /usr/local/bin/getvul-update

# Check update logs
sudo tail -50 /var/log/getvul-update.log

# Verify git access
cd /opt/getvul && git pull
```

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
- [ ] Set up database backup schedule
- [ ] Review rate limiting configuration
- [ ] Run the CI pipeline (Semgrep + ZAP) before going live
