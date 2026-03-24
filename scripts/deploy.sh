#!/bin/bash
# Manual deploy script — run from your local machine
# Usage: ./scripts/deploy.sh <VM_IP> [SSH_USER]
#
# Prerequisites:
#   - SSH key configured for the VM
#   - VM has Docker + Docker Compose installed
#   - Repo cloned at /opt/getvul on the VM

set -e

VM_IP="${1:?Usage: ./scripts/deploy.sh <VM_IP> [SSH_USER]}"
VM_USER="${2:-deploy}"

echo "🚀 Deploying GetVul to $VM_USER@$VM_IP..."

ssh "$VM_USER@$VM_IP" << 'DEPLOY'
  set -e
  cd /opt/getvul

  echo "Pulling latest..."
  git pull origin main

  echo "Rebuilding..."
  docker compose build
  docker compose up -d

  echo "Waiting for health check..."
  for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
      echo "✅ Healthy!"
      break
    fi
    sleep 5
  done

  docker image prune -f
  echo "✅ Deploy complete"
DEPLOY
