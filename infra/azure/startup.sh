#!/bin/bash
# GetVul VM startup script — runs once on first boot (Azure custom data)
# Installs Docker, clones repo, starts the app, sets up daily auto-update

set -e

APP_DIR="/opt/${app_name}"
REPO="https://github.com/${github_repo}.git"
LOG="/var/log/${app_name}-startup.log"

exec > >(tee -a "$LOG") 2>&1
echo "=== GetVul startup $(date) ==="

# -- Install Docker --
if ! command -v docker &>/dev/null; then
    echo "Installing Docker..."
    apt-get update -y
    apt-get install -y ca-certificates curl gnupg
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
fi

# Install Docker Compose plugin if missing
if ! docker compose version &>/dev/null; then
    echo "Installing Docker Compose plugin..."
    mkdir -p /usr/local/lib/docker/cli-plugins
    curl -fsSL "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
        -o /usr/local/lib/docker/cli-plugins/docker-compose
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
fi

# -- Clone repo --
if [ ! -d "$APP_DIR" ]; then
    echo "Cloning repository..."
    git clone "$REPO" "$APP_DIR"
else
    echo "Repository already exists, pulling latest..."
    cd "$APP_DIR" && git pull origin main
fi

cd "$APP_DIR"

# -- Create .env if not exists --
if [ ! -f .env ]; then
    echo "Creating .env from template..."
    cat > .env << 'ENVEOF'
# === GetVul Production Environment ===
# IMPORTANT: Change all secrets before going live

DATABASE_URL=postgresql+asyncpg://getvul:getvul@postgres:5432/getvul
REDIS_URL=redis://redis:6379/0
ENVIRONMENT=production
DEBUG=false

# Auth — CHANGE THIS
JWT_SECRET_KEY=CHANGE-ME-use-openssl-rand-base64-32
ENCRYPTION_KEY=CHANGE-ME-use-python-c-from-cryptography.fernet-import-Fernet-Fernet.generate_key

# Google OIDC (optional)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

# Azure Entra ID OIDC (optional)
AZURE_CLIENT_ID=
AZURE_CLIENT_SECRET=
ENVEOF
    echo "WARNING: Edit .env with real secrets before production use!"
fi

# -- Start the app --
echo "Starting GetVul..."
docker compose up -d --build

# -- Install auto-update cron --
echo "Setting up daily auto-update..."
cp scripts/auto-update.sh /usr/local/bin/getvul-update
chmod +x /usr/local/bin/getvul-update

# Run daily at 3:00 AM UTC
(crontab -l 2>/dev/null | grep -v getvul-update; echo "0 3 * * * /usr/local/bin/getvul-update >> /var/log/${app_name}-update.log 2>&1") | crontab -

echo "=== Startup complete $(date) ==="
echo "App running at http://$(curl -s ifconfig.me)"
