#!/bin/bash
# GetVul auto-update script — runs daily via cron
# Checks GitHub for new releases, pulls and rebuilds if updated
#
# Usage: /usr/local/bin/getvul-update
# Cron:  0 3 * * * /usr/local/bin/getvul-update >> /var/log/getvul-update.log 2>&1

set -e

APP_DIR="/opt/getvul"
REPO="Cyber-Solutions-MD/getvul"
BRANCH="main"
STATE_FILE="/var/lib/getvul/last-deployed-sha"
LOG_PREFIX="[getvul-update $(date '+%Y-%m-%d %H:%M:%S')]"

echo "$LOG_PREFIX Starting update check..."

# Ensure state directory exists
mkdir -p /var/lib/getvul

# Get latest commit SHA from GitHub API (no auth needed for public repos)
LATEST_SHA=$(curl -sf "https://api.github.com/repos/${REPO}/commits/${BRANCH}" | grep '"sha"' | head -1 | cut -d'"' -f4)

if [ -z "$LATEST_SHA" ]; then
    echo "$LOG_PREFIX ERROR: Could not fetch latest SHA from GitHub"
    exit 1
fi

# Check if we've already deployed this version
DEPLOYED_SHA=""
if [ -f "$STATE_FILE" ]; then
    DEPLOYED_SHA=$(cat "$STATE_FILE")
fi

if [ "$LATEST_SHA" = "$DEPLOYED_SHA" ]; then
    echo "$LOG_PREFIX Already up to date (${LATEST_SHA:0:8})"
    exit 0
fi

echo "$LOG_PREFIX New version detected: ${DEPLOYED_SHA:0:8} → ${LATEST_SHA:0:8}"
echo "$LOG_PREFIX Pulling latest code..."

cd "$APP_DIR"

# Pull latest code
git fetch origin "$BRANCH"
git reset --hard "origin/$BRANCH"

# Rebuild and restart containers
echo "$LOG_PREFIX Rebuilding containers..."
docker compose build --no-cache
docker compose up -d

# Wait for health check
echo "$LOG_PREFIX Waiting for health check..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo "$LOG_PREFIX Health check passed!"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "$LOG_PREFIX ERROR: Health check failed after 30 attempts"
        exit 1
    fi
    sleep 5
done

# Prune old images
docker image prune -f

# Save deployed SHA
echo "$LATEST_SHA" > "$STATE_FILE"

echo "$LOG_PREFIX Update complete: now running ${LATEST_SHA:0:8}"
