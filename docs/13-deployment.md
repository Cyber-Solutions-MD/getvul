# Deployment Guide

GetVul runs as five Docker Compose services on a single VM. This guide covers deployment using each cloud provider's native CLI — no Terraform required. All commands run in the browser-based cloud shell.

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

- **nginx** — Reverse proxy with TLS termination, security headers, rate limiting
- **backend** — FastAPI application server, runs Alembic migrations on startup
- **frontend** — Next.js 15 with React 19
- **postgres** — PostgreSQL 16, data persisted via Docker volume
- **redis** — Redis 7 for rate limiting and caching

---

## Local Development

```bash
git clone https://github.com/Cyber-Solutions-MD/getvul.git
cd getvul
cp .env.example .env   # Edit with your secrets
docker compose up -d --build
```

| Endpoint | URL |
|----------|-----|
| Application (HTTPS) | `https://localhost` |
| Frontend direct | `http://localhost:3000` |
| Backend API | `http://localhost:8000/docs` |

---

## Microsoft Azure

Deploy using Azure Cloud Shell (browser-based, no local tools needed).

### Step 1: Open Azure Cloud Shell

1. Go to [https://portal.azure.com](https://portal.azure.com)
2. Click the **Cloud Shell** icon (terminal icon) in the top navigation bar
3. Select **Bash** (not PowerShell)
4. If prompted, create a storage account for Cloud Shell

### Step 2: Set variables

```bash
# Choose your settings
RESOURCE_GROUP="getvul-rg"
LOCATION="germanywestcentral"   # Change to your preferred region
VM_NAME="getvul-vm"
VM_SIZE="Standard_D2s_v3"       # 2 vCPU, 8 GB RAM (~$84/mo)
# If unavailable, try: Standard_B2ms, Standard_D2s_v5, Standard_D2as_v5
# Tip: check available sizes with: az vm list-sizes --location $LOCATION --output table
ADMIN_USER="getvul"
REPO_URL="https://github.com/Cyber-Solutions-MD/getvul.git"
```

### Step 3: Create resource group

```bash
az group create \
  --name $RESOURCE_GROUP \
  --location $LOCATION
```

### Step 4: Generate SSH key (if you don't have one)

```bash
# Generate SSH key in Cloud Shell
ssh-keygen -t ed25519 -f ~/.ssh/getvul -N ""

# Display the public key (you'll need this)
cat ~/.ssh/getvul.pub
```

### Step 5: Create the VM

```bash
az vm create \
  --resource-group $RESOURCE_GROUP \
  --name $VM_NAME \
  --image Canonical:ubuntu-24_04-lts:server:latest \
  --size $VM_SIZE \
  --admin-username $ADMIN_USER \
  --ssh-key-values ~/.ssh/getvul.pub \
  --os-disk-size-gb 30 \
  --public-ip-sku Standard \
  --output table
```

> **Quota errors?** New Azure subscriptions often have 0 vCPU quota. If you get `QuotaExceeded` or `SkuNotAvailable`:
> 1. Try a different region: `az group delete --name $RESOURCE_GROUP --yes && az group create --name $RESOURCE_GROUP --location eastus`
> 2. Try a different size: `Standard_D2s_v3`, `Standard_D2s_v5`, `Standard_B2ms`
> 3. Request quota increase: Portal → Quotas → Compute → select region → increase the VM family to 4 cores
> 4. Or create the VM via the **Azure Portal UI** instead (Marketplace → Ubuntu Server 24.04 LTS → Create)

Save the **publicIpAddress** from the output.

### Step 6: Open firewall ports

```bash
# Open HTTP and HTTPS
az vm open-port \
  --resource-group $RESOURCE_GROUP \
  --name $VM_NAME \
  --port 80,443 \
  --priority 100
```

### Step 7: SSH into the VM and install the app

```bash
# Option A: From Azure Cloud Shell (no key needed)
az ssh vm --resource-group getvul-rg --name getvul-vm

# Option B: Direct SSH
ssh -i ~/.ssh/getvul $ADMIN_USER@<PUBLIC_IP>
```

Once inside the VM, run the install script:

```bash
sudo git clone https://github.com/Cyber-Solutions-MD/getvul.git /opt/getvul
sudo chown -R $USER:$USER /opt/getvul
bash /opt/getvul/install.sh
```

The install script runs 8 steps automatically:
1. Installs Docker and Docker Compose
2. Generates a self-signed TLS certificate
3. Creates `.env` with auto-generated secrets (JWT key, encryption key, `NEXT_PUBLIC_API_URL=""`)
4. Builds and starts all 5 containers (2-5 minutes)
5. Waits for backend health check to pass
6. Creates default admin user (`admin@getvul.local` / `Admin123!`) via `create_admin.py`
7. Seeds demo data via `seed_data.py` (25 assets, 150+ vulns, 20 CSPM findings, 10 Jira tickets, 15 users, 5 notifications, 7 connectors)
8. Sets up hourly auto-update cron

### Step 8: Access the application

Open in your browser (use the IP from the install script output):

```
https://<PUBLIC_IP>
```

Accept the self-signed certificate warning and log in with the default admin account:
- **Email:** `admin@getvul.local`
- **Password:** `Admin123!`

**Change the password immediately after first login.**

### Restrict SSH access (recommended)

```bash
# From Azure Cloud Shell — find NSG name and restrict SSH to your IP
NSG_NAME=$(az network nsg list --resource-group getvul-rg --query "[0].name" --output tsv)
MY_IP=$(curl -s ifconfig.me)
az network nsg rule update \
  --resource-group getvul-rg \
  --nsg-name $NSG_NAME \
  --name default-allow-ssh \
  --source-address-prefixes $MY_IP
```

### Teardown

```bash
# Delete everything (VM, disk, network, IP — all in one command)
az group delete --name $RESOURCE_GROUP --yes --no-wait
```

---

## Amazon Web Services (AWS)

Deploy using AWS CloudShell (browser-based, no local tools needed).

### Step 1: Open AWS CloudShell

1. Go to [https://console.aws.amazon.com](https://console.aws.amazon.com)
2. Click the **CloudShell** icon (terminal icon) in the top navigation bar
3. Wait for the shell to initialize

### Step 2: Set variables

```bash
# Choose your settings
REGION="eu-west-1"              # Change to your preferred region
INSTANCE_TYPE="t3.medium"       # 2 vCPU, 4 GB RAM
KEY_NAME="getvul-key"
SG_NAME="getvul-sg"
REPO_URL="https://github.com/Cyber-Solutions-MD/getvul.git"
```

### Step 3: Create SSH key pair

```bash
# Create key pair (saves private key locally)
aws ec2 create-key-pair \
  --region $REGION \
  --key-name $KEY_NAME \
  --query 'KeyMaterial' \
  --output text > ~/.ssh/getvul.pem

chmod 400 ~/.ssh/getvul.pem
```

### Step 4: Create security group

```bash
# Get default VPC ID
VPC_ID=$(aws ec2 describe-vpcs \
  --region $REGION \
  --filters Name=isDefault,Values=true \
  --query 'Vpcs[0].VpcId' \
  --output text)

# Create security group
SG_ID=$(aws ec2 create-security-group \
  --region $REGION \
  --group-name $SG_NAME \
  --description "GetVul - HTTP, HTTPS, SSH" \
  --vpc-id $VPC_ID \
  --query 'GroupId' \
  --output text)

# Allow HTTP (80), HTTPS (443), SSH (22)
aws ec2 authorize-security-group-ingress --region $REGION --group-id $SG_ID --protocol tcp --port 80 --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --region $REGION --group-id $SG_ID --protocol tcp --port 443 --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --region $REGION --group-id $SG_ID --protocol tcp --port 22 --cidr 0.0.0.0/0

echo "Security Group: $SG_ID"
```

### Step 5: Find Ubuntu 22.04 AMI

```bash
AMI_ID=$(aws ec2 describe-images \
  --region $REGION \
  --owners 099720109477 \
  --filters "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*" \
  --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
  --output text)

echo "AMI: $AMI_ID"
```

### Step 6: Launch the instance

```bash
# Get a subnet
SUBNET_ID=$(aws ec2 describe-subnets \
  --region $REGION \
  --filters Name=vpc-id,Values=$VPC_ID \
  --query 'Subnets[0].SubnetId' \
  --output text)

# Launch EC2 instance
INSTANCE_ID=$(aws ec2 run-instances \
  --region $REGION \
  --image-id $AMI_ID \
  --instance-type $INSTANCE_TYPE \
  --key-name $KEY_NAME \
  --security-group-ids $SG_ID \
  --subnet-id $SUBNET_ID \
  --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=30,VolumeType=gp3}' \
  --metadata-options 'HttpTokens=required,HttpEndpoint=enabled' \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=getvul}]' \
  --query 'Instances[0].InstanceId' \
  --output text)

echo "Instance: $INSTANCE_ID"

# Wait for it to be running
aws ec2 wait instance-running --region $REGION --instance-ids $INSTANCE_ID
echo "Instance is running"
```

### Step 7: Allocate and associate Elastic IP

```bash
# Allocate static IP
ALLOC_ID=$(aws ec2 allocate-address \
  --region $REGION \
  --query 'AllocationId' \
  --output text)

# Associate with instance
aws ec2 associate-address \
  --region $REGION \
  --instance-id $INSTANCE_ID \
  --allocation-id $ALLOC_ID

# Get the public IP
PUBLIC_IP=$(aws ec2 describe-addresses \
  --region $REGION \
  --allocation-ids $ALLOC_ID \
  --query 'Addresses[0].PublicIp' \
  --output text)

echo "Public IP: $PUBLIC_IP"
```

### Step 8: SSH into the instance and install the app

```bash
# Wait 30 seconds for SSH to be ready
sleep 30

# SSH into the instance
ssh -i ~/.ssh/getvul.pem -o StrictHostKeyChecking=no ubuntu@$PUBLIC_IP
```

Once inside the instance, run the install script:

```bash
sudo git clone https://github.com/Cyber-Solutions-MD/getvul.git /opt/getvul
sudo chown -R $USER:$USER /opt/getvul
bash /opt/getvul/install.sh
```

The script runs 8 steps: Docker install, TLS cert generation, `.env` creation with auto-generated secrets, container build, backend health check, admin user creation, seed demo data, and hourly auto-update cron.

### Step 9: Access the application

Open in your browser (use the IP from Step 7):

```
https://<PUBLIC_IP>
```

Accept the self-signed certificate warning and log in with the default admin account:
- **Email:** `admin@getvul.local`
- **Password:** `Admin123!`

**Change the password immediately after first login.**

### Restrict SSH (recommended)

```bash
# From AWS CloudShell — restrict SSH to your IP
MY_IP=$(curl -s ifconfig.me)/32
aws ec2 revoke-security-group-ingress --region $REGION --group-id $SG_ID --protocol tcp --port 22 --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --region $REGION --group-id $SG_ID --protocol tcp --port 22 --cidr $MY_IP
```

### Teardown

```bash
# Terminate instance
aws ec2 terminate-instances --region $REGION --instance-ids $INSTANCE_ID

# Wait for termination
aws ec2 wait instance-terminated --region $REGION --instance-ids $INSTANCE_ID

# Release Elastic IP
aws ec2 release-address --region $REGION --allocation-id $ALLOC_ID

# Delete security group
aws ec2 delete-security-group --region $REGION --group-id $SG_ID

# Delete key pair
aws ec2 delete-key-pair --region $REGION --key-name $KEY_NAME
```

---

## Google Cloud Platform (GCP)

Deploy using GCP Cloud Shell (browser-based, no local tools needed).

### Step 1: Open GCP Cloud Shell

1. Go to [https://console.cloud.google.com](https://console.cloud.google.com)
2. Select your project from the top dropdown
3. Click the **Activate Cloud Shell** icon (terminal icon) in the top navigation bar
4. Wait for the shell to initialize

### Step 2: Set variables

```bash
# Choose your settings
PROJECT_ID=$(gcloud config get-value project)
ZONE="us-central1-a"            # Change to your preferred zone
MACHINE_TYPE="e2-medium"        # 2 vCPU, 4 GB RAM
VM_NAME="getvul-vm"
REPO_URL="https://github.com/Cyber-Solutions-MD/getvul.git"

echo "Project: $PROJECT_ID"
```

### Step 3: Enable required APIs

```bash
gcloud services enable compute.googleapis.com
```

### Step 4: Create firewall rules

```bash
# Allow HTTP and HTTPS from anywhere
gcloud compute firewall-rules create getvul-web \
  --allow tcp:80,tcp:443 \
  --target-tags getvul \
  --description "GetVul HTTP/HTTPS" \
  --quiet

# Allow SSH (restrict later)
gcloud compute firewall-rules create getvul-ssh \
  --allow tcp:22 \
  --target-tags getvul \
  --description "GetVul SSH" \
  --quiet
```

### Step 5: Create the VM

```bash
gcloud compute instances create $VM_NAME \
  --zone=$ZONE \
  --machine-type=$MACHINE_TYPE \
  --boot-disk-size=30GB \
  --boot-disk-type=pd-ssd \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --tags=getvul \
  --metadata=enable-oslogin=true

# Get the external IP
PUBLIC_IP=$(gcloud compute instances describe $VM_NAME \
  --zone=$ZONE \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo "Public IP: $PUBLIC_IP"
```

### Step 6: Reserve a static IP (so it doesn't change on restart)

```bash
# Reserve a static IP
gcloud compute addresses create getvul-ip \
  --region=$(echo $ZONE | sed 's/-[a-z]$//') \
  --quiet

STATIC_IP=$(gcloud compute addresses describe getvul-ip \
  --region=$(echo $ZONE | sed 's/-[a-z]$//') \
  --format='get(address)')

# Assign to the VM
gcloud compute instances delete-access-config $VM_NAME \
  --zone=$ZONE \
  --access-config-name="external-nat" \
  --quiet

gcloud compute instances add-access-config $VM_NAME \
  --zone=$ZONE \
  --address=$STATIC_IP

echo "Static IP: $STATIC_IP"
```

### Step 7: SSH into the VM and install the app

```bash
# GCP Cloud Shell has built-in SSH — no keys needed
gcloud compute ssh $VM_NAME --zone=$ZONE
```

Once inside the VM, run the install script:

```bash
sudo git clone https://github.com/Cyber-Solutions-MD/getvul.git /opt/getvul
sudo chown -R $USER:$USER /opt/getvul
bash /opt/getvul/install.sh
```

The script runs 8 steps: Docker install, TLS cert generation, `.env` creation with auto-generated secrets, container build, backend health check, admin user creation, seed demo data, and hourly auto-update cron.

### Step 8: Access the application

Open in your browser (use the IP from Step 6):

```
https://<STATIC_IP>
```

Accept the self-signed certificate warning and log in with the default admin account:
- **Email:** `admin@getvul.local`
- **Password:** `Admin123!`

**Change the password immediately after first login.**

### Restrict SSH (recommended)

```bash
# From GCP Cloud Shell — restrict SSH to your IP
MY_IP=$(curl -s ifconfig.me)
gcloud compute firewall-rules update getvul-ssh \
  --source-ranges=$MY_IP/32
```

### Teardown

```bash
# Delete the VM
gcloud compute instances delete $VM_NAME --zone=$ZONE --quiet

# Delete static IP
gcloud compute addresses delete getvul-ip \
  --region=$(echo $ZONE | sed 's/-[a-z]$//') --quiet

# Delete firewall rules
gcloud compute firewall-rules delete getvul-web --quiet
gcloud compute firewall-rules delete getvul-ssh --quiet
```

---

## Post-Deployment: First Login

After the app is running:

1. Open `https://<PUBLIC_IP>` in your browser
2. Accept the self-signed certificate warning
3. Log in with the default admin account:
   - **Email:** `admin@getvul.local`
   - **Password:** `Admin123!`
4. **Change the password immediately** (profile dropdown → Change Password)
5. Go to **Settings > General** to set your organization name, domain, and timezone
6. Go to **Connectors** to add your first vulnerability scanner
7. Trigger a sync and review findings in the **Vulnerabilities** dashboard

---

## TLS / SSL Certificates

### Self-signed (default)

Generated automatically on first boot. Browsers show a security warning — this is expected.

### Custom certificate (via UI)

1. Go to **Settings > General > TLS Certificate**
2. Paste the PEM-encoded certificate chain and private key
3. Nginx reloads automatically

### Let's Encrypt (free, auto-renewing)

```bash
# SSH into the VM, then:

# Stop nginx to free port 80
cd /opt/getvul && docker compose stop nginx

# Install certbot
sudo apt install -y certbot

# Get certificate (replace with your domain)
sudo certbot certonly --standalone -d getvul.your-company.com

# Install the certificate
sudo cp /etc/letsencrypt/live/getvul.your-company.com/fullchain.pem /opt/getvul/nginx/certs/server.crt
sudo cp /etc/letsencrypt/live/getvul.your-company.com/privkey.pem /opt/getvul/nginx/certs/server.key

# Restart nginx
docker compose up -d nginx

# Set up auto-renewal
echo "0 */12 * * * root certbot renew --quiet --deploy-hook 'cd /opt/getvul && docker compose restart nginx'" | sudo tee /etc/cron.d/certbot-renew
```

---

## Database

- **Engine:** PostgreSQL 16 (`postgres:16-alpine`)
- **Persistence:** Docker named volume (survives restarts)
- **Migrations:** Alembic runs `upgrade head` on backend startup (24 total)

### Backup

```bash
docker compose exec postgres pg_dump -U getvul getvul > backup_$(date +%Y%m%d).sql
```

### Restore

```bash
docker compose exec -T postgres psql -U getvul getvul < backup_20260101.sql
```

---

## Environment Variables

### Required

| Variable | Description | How to generate |
|----------|-------------|-----------------|
| `DATABASE_URL` | PostgreSQL connection | `postgresql+asyncpg://getvul:getvul@postgres:5432/getvul` |
| `REDIS_URL` | Redis connection | `redis://redis:6379/0` |
| `JWT_SECRET_KEY` | JWT signing secret | `openssl rand -hex 32` |
| `ENCRYPTION_KEY` | Credential encryption | `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | `""` | Must be empty string for production (frontend uses relative API paths through nginx) |
| `ENVIRONMENT` | `development` | Set to `production` |
| `DEBUG` | `true` | Set to `false` in production |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed origins (JSON array) |

SMTP, SSO, and SLA settings are configured in the app UI under **Settings**.

---

## Troubleshooting

### Containers not starting

```bash
# Check Docker is running
sudo systemctl status docker

# View build/startup errors
docker compose logs backend

# Common fix: restart everything
docker compose down && docker compose up -d --build
```

### Cannot access web UI

```bash
# Check nginx is running
docker compose ps nginx

# Test locally on the VM
curl -k https://localhost

# Check firewall rules allow 80/443
# Azure: az network nsg rule list ...
# AWS:   aws ec2 describe-security-groups ...
# GCP:   gcloud compute firewall-rules list
```

### Database migration error

```bash
# Run migrations manually
docker compose exec backend alembic upgrade head

# Check migration status
docker compose exec backend alembic current
```

---

## Production Checklist

- [ ] Set strong `JWT_SECRET_KEY` and `ENCRYPTION_KEY` in `.env`
- [ ] Set `ENVIRONMENT=production` and `DEBUG=false`
- [ ] Install TLS certificate (Let's Encrypt or CA-signed)
- [ ] Restrict SSH to known IP ranges
- [ ] Configure SMTP for email (Settings > General > SMTP)
- [ ] Change default admin password (`admin@getvul.local` / `Admin123!`)
- [ ] Add at least one vulnerability connector
- [ ] Set SLA policy per severity (Settings > General > SLA)
- [ ] Configure syslog forwarding to SIEM (Settings > Audit Log)
- [ ] Set up database backup schedule
- [ ] Verify hourly auto-update cron is active (set up by install.sh)
- [ ] Run CI pipeline before going live
