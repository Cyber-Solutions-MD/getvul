#!/bin/bash
set -e

echo "=============================="
echo "  GetVul Installation Script  "
echo "=============================="
echo ""

APP_DIR="/opt/getvul"

# Check if running from the repo
if [ -f "$(dirname "$0")/docker-compose.yml" ]; then
    APP_DIR="$(cd "$(dirname "$0")" && pwd)"
fi

cd "$APP_DIR"

# ── Step 1: Install Docker ──
if ! command -v docker &> /dev/null; then
    echo "[1/5] Installing Docker..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq ca-certificates curl gnupg > /dev/null
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update -qq
    sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin > /dev/null
    sudo usermod -aG docker "$USER"
    echo "    Docker installed."
else
    echo "[1/5] Docker already installed — skipping."
fi

# ── Step 2: Generate self-signed TLS cert if missing ──
if [ ! -f "$APP_DIR/nginx/certs/server.key" ]; then
    echo "[2/6] Generating self-signed TLS certificate..."
    mkdir -p "$APP_DIR/nginx/certs"
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
      -keyout "$APP_DIR/nginx/certs/server.key" \
      -out "$APP_DIR/nginx/certs/server.crt" \
      -subj "/CN=getvul" 2>/dev/null
    echo "    Self-signed certificate created."
else
    echo "[2/6] TLS certificate exists — skipping."
fi

# ── Step 3: Create .env if it doesn't exist ──
if [ ! -f "$APP_DIR/.env" ]; then
    echo "[3/6] Creating environment file..."
    cat > "$APP_DIR/.env" << 'ENVEOF'
DATABASE_URL=postgresql+asyncpg://getvul:getvul@postgres:5432/getvul
REDIS_URL=redis://redis:6379/0
ENVIRONMENT=production
DEBUG=false
ENVEOF
    # Generate secrets
    echo "JWT_SECRET_KEY=$(openssl rand -hex 32)" >> "$APP_DIR/.env"
    ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || openssl rand -base64 32)
    echo "ENCRYPTION_KEY=$ENCRYPTION_KEY" >> "$APP_DIR/.env"
    echo "    Environment file created with generated secrets."
else
    echo "[3/6] Environment file exists — skipping."
fi

# ── Step 3: Build and start containers ──
echo "[4/6] Building and starting containers (this takes 2-5 minutes)..."
sudo docker compose up -d --build

# ── Step 4: Wait for backend to be ready ──
echo "[5/6] Waiting for backend to start..."
for i in $(seq 1 30); do
    if sudo docker compose exec -T backend python3 -c "print('ok')" &>/dev/null; then
        break
    fi
    sleep 2
done

# Check health
if curl -sf http://localhost:8000/docs > /dev/null 2>&1; then
    echo "    Backend is healthy."
else
    echo "    Backend is starting... check logs with: docker compose logs -f backend"
fi

# ── Step 5: Set up auto-update cron ──
if [ ! -f /usr/local/bin/getvul-update ]; then
    echo "[6/6] Setting up daily auto-update..."
    sudo tee /usr/local/bin/getvul-update > /dev/null << SCRIPT
#!/bin/bash
set -e
LOG="/var/log/getvul-update.log"
echo "\$(date) — Checking for updates..." >> \$LOG
cd $APP_DIR
git pull >> \$LOG 2>&1
docker compose up -d --build >> \$LOG 2>&1
echo "\$(date) — Update complete" >> \$LOG
SCRIPT
    sudo chmod +x /usr/local/bin/getvul-update
    echo "0 * * * * root /usr/local/bin/getvul-update" | sudo tee /etc/cron.d/getvul-update > /dev/null
    echo "    Auto-update scheduled hourly."
else
    echo "[6/6] Auto-update already configured — skipping."
fi

# ── Done ──
echo ""
echo "=============================="
echo "  GetVul is running!"
echo "=============================="
echo ""
echo "  Access:  https://$(curl -sf ifconfig.me 2>/dev/null || echo '<your-vm-ip>')"
echo "  Logs:    sudo docker compose -f $APP_DIR/docker-compose.yml logs -f"
echo "  Update:  sudo /usr/local/bin/getvul-update"
echo ""
echo "  First time? Open the URL above, accept the cert warning,"
echo "  and register your admin account."
echo ""
