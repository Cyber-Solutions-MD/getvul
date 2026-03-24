#!/bin/bash
# GetVul VM startup script — runs once on first boot (Ubuntu 22.04)
# Installs Docker, clones repo, starts the app, sets up daily auto-update

set -e

APP_DIR="/opt/${app_name}"
REPO="https://github.com/${github_repo}.git"
LOG="/var/log/${app_name}-startup.log"

exec > >(tee -a "$LOG") 2>&1
echo "=== GetVul startup $(date) ==="

# ── Install Docker via apt ──
if ! command -v docker &>/dev/null; then
    echo "Installing Docker..."
    apt-get update -y
    apt-get install -y ca-certificates curl gnupg

    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
        | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
        https://download.docker.com/linux/ubuntu \
        $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        | tee /etc/apt/sources.list.d/docker.list > /dev/null

    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

    systemctl enable docker
    systemctl start docker
fi

# ── Configure deploy key (if provided) ──
if [ -n "${deploy_key}" ]; then
    echo "Configuring GitHub deploy key..."
    mkdir -p /root/.ssh
    echo "${deploy_key}" > /root/.ssh/deploy_key
    chmod 600 /root/.ssh/deploy_key
    cat > /root/.ssh/config << 'SSHEOF'
Host github.com
    HostName github.com
    User git
    IdentityFile /root/.ssh/deploy_key
    StrictHostKeyChecking no
SSHEOF
    chmod 600 /root/.ssh/config
    REPO="git@github.com:${github_repo}.git"
fi

# ── Clone repo ──
if [ ! -d "$APP_DIR" ]; then
    echo "Cloning repository..."
    git clone "$REPO" "$APP_DIR"
else
    echo "Repository already exists, pulling latest..."
    cd "$APP_DIR" && git pull origin main
fi

cd "$APP_DIR"

# ── Create .env if not exists ──
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

# ── Start the app ──
echo "Starting GetVul..."
docker compose up -d --build

# ── Install auto-update cron ──
echo "Setting up daily auto-update..."
cp scripts/auto-update.sh /usr/local/bin/getvul-update
chmod +x /usr/local/bin/getvul-update

# Run daily at 3:00 AM UTC
(crontab -l 2>/dev/null | grep -v getvul-update; echo "0 3 * * * /usr/local/bin/getvul-update >> /var/log/${app_name}-update.log 2>&1") | crontab -

echo "=== Startup complete $(date) ==="
echo "App running at http://$(curl -s ifconfig.me)"
