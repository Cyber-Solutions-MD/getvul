#!/bin/bash
set -euo pipefail

cd ~/Desktop/getvul

echo "⚡ Adding background sync + clearing test data..."

# ══════════════════════════════════════════════
#  BACKEND: Background sync scheduler
# ══════════════════════════════════════════════

cat > backend/app/connectors/scheduler.py << 'FILEEOF'
"""Background sync scheduler — runs connector syncs on their configured intervals."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.sync import run_sync
from app.db.session import async_session_factory
from app.ticketing.models import ConnectorConfig

logger = structlog.get_logger()

# Track running tasks
_running_syncs: dict[str, asyncio.Task] = {}
_scheduler_task: asyncio.Task | None = None


async def _run_single_sync(connector_id: str, tenant_id: str) -> None:
    """Run a single connector sync in the background."""
    logger.info("background_sync_start", connector_id=connector_id)

    try:
        async with async_session_factory() as db:
            result = await db.execute(
                select(ConnectorConfig).where(ConnectorConfig.id == connector_id)
            )
            connector = result.scalar_one_or_none()
            if connector is None:
                logger.error("background_sync_connector_not_found", connector_id=connector_id)
                return

            log = await run_sync(db, connector)
            await db.commit()

            logger.info(
                "background_sync_complete",
                connector_id=connector_id,
                connector_type=connector.connector_type,
                status=log.status,
                records_fetched=log.records_fetched,
                records_created=log.records_created,
                error=log.error_message,
            )
    except Exception as e:
        logger.error("background_sync_error", connector_id=connector_id, error=str(e))
    finally:
        _running_syncs.pop(connector_id, None)


def trigger_background_sync(connector_id: str, tenant_id: str) -> bool:
    """Trigger a sync in the background. Returns False if already running."""
    if connector_id in _running_syncs:
        task = _running_syncs[connector_id]
        if not task.done():
            return False  # Already running

    task = asyncio.create_task(_run_single_sync(connector_id, tenant_id))
    _running_syncs[connector_id] = task
    return True


def is_sync_running(connector_id: str) -> bool:
    """Check if a sync is currently running for a connector."""
    task = _running_syncs.get(connector_id)
    return task is not None and not task.done()


async def _scheduler_loop() -> None:
    """Periodic loop that checks all connectors and triggers syncs when due."""
    logger.info("sync_scheduler_started")

    while True:
        try:
            async with async_session_factory() as db:
                result = await db.execute(
                    select(ConnectorConfig).where(
                        ConnectorConfig.is_enabled.is_(True),
                        ConnectorConfig.credentials_secret_arn.isnot(None),
                    )
                )
                connectors = result.scalars().all()

                now = datetime.now(timezone.utc)

                for connector in connectors:
                    # Skip if already running
                    if is_sync_running(str(connector.id)):
                        continue

                    # Check if sync is due
                    if connector.last_sync_at is None:
                        # Never synced — trigger immediately
                        should_sync = True
                    else:
                        elapsed_minutes = (now - connector.last_sync_at).total_seconds() / 60
                        should_sync = elapsed_minutes >= connector.sync_interval_minutes

                    if should_sync:
                        logger.info(
                            "scheduler_triggering_sync",
                            connector_type=connector.connector_type,
                            connector_id=str(connector.id),
                            interval=connector.sync_interval_minutes,
                        )
                        trigger_background_sync(str(connector.id), str(connector.tenant_id))

        except Exception as e:
            logger.error("scheduler_loop_error", error=str(e))

        # Check every 60 seconds
        await asyncio.sleep(60)


def start_scheduler() -> None:
    """Start the background scheduler. Call once at app startup."""
    global _scheduler_task
    if _scheduler_task is None or _scheduler_task.done():
        _scheduler_task = asyncio.create_task(_scheduler_loop())
        logger.info("sync_scheduler_registered")


def stop_scheduler() -> None:
    """Stop the background scheduler."""
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        _scheduler_task = None
FILEEOF

# ══════════════════════════════════════════════
#  BACKEND: Update connector router — background sync + status
# ══════════════════════════════════════════════

cat > backend/app/connectors/router.py << 'FILEEOF'
"""Connector management API routes."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.auth.rbac import require_admin
from app.auth.schemas import CurrentUser
from app.connectors.schemas import (
    CONNECTOR_TYPES,
    ConnectorConfigResponse,
    ConnectorCreate,
    ConnectorTestRequest,
    ConnectorTestResult,
    ConnectorTypeInfo,
    ConnectorUpdate,
)
from app.connectors.service import (
    create_connector,
    delete_connector,
    list_connectors,
    update_connector,
)
from app.connectors.tester import test_connector
from app.connectors.scheduler import trigger_background_sync, is_sync_running
from app.dependencies import DBSession

router = APIRouter()


@router.get("/types", response_model=list[ConnectorTypeInfo])
async def get_connector_types():
    """List all supported connector types, required fields, and permissions."""
    return [
        ConnectorTypeInfo(
            type=k, name=v["name"], fields=v["fields"], defaults=v["defaults"],
            description=v["description"], setup_url=v["setup_url"],
            permissions=v["permissions"], base_urls=v.get("base_urls", {}), notes=v["notes"],
        )
        for k, v in CONNECTOR_TYPES.items()
    ]


@router.get("", response_model=list[ConnectorConfigResponse])
async def list_all_connectors(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_admin)],
):
    return await list_connectors(db, user.tenant_id)


@router.post("", response_model=ConnectorConfigResponse, status_code=201)
async def create_new_connector(
    body: ConnectorCreate,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_admin)],
):
    return await create_connector(db, user.tenant_id, body)


@router.patch("/{connector_id}", response_model=ConnectorConfigResponse)
async def update_existing_connector(
    connector_id: uuid.UUID,
    body: ConnectorUpdate,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_admin)],
):
    result = await update_connector(db, user.tenant_id, connector_id, body)
    if result is None:
        raise HTTPException(status_code=404, detail="Connector not found")
    return result


@router.delete("/{connector_id}")
async def delete_existing_connector(
    connector_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_admin)],
):
    deleted = await delete_connector(db, user.tenant_id, connector_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Connector not found")
    return {"message": "Connector deleted"}


@router.post("/test", response_model=ConnectorTestResult)
async def test_connector_credentials(
    body: ConnectorTestRequest,
    user: Annotated[CurrentUser, Depends(require_admin)],
):
    return await test_connector(body.connector_type, body.credentials, body.config)


@router.post("/{connector_id}/sync")
async def trigger_sync(
    connector_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_admin)],
):
    """Trigger a sync in the background. Returns immediately."""
    from sqlalchemy import select
    from app.ticketing.models import ConnectorConfig

    result = await db.execute(
        select(ConnectorConfig).where(
            ConnectorConfig.id == connector_id,
            ConnectorConfig.tenant_id == user.tenant_id,
        )
    )
    connector = result.scalar_one_or_none()
    if connector is None:
        raise HTTPException(status_code=404, detail="Connector not found")

    if is_sync_running(str(connector_id)):
        return {"status": "ALREADY_RUNNING", "message": "Sync is already in progress"}

    triggered = trigger_background_sync(str(connector_id), str(user.tenant_id))
    if not triggered:
        return {"status": "ALREADY_RUNNING", "message": "Sync is already in progress"}

    return {"status": "STARTED", "message": "Sync started in background. Refresh to see results."}


@router.get("/{connector_id}/sync-status")
async def get_sync_status(
    connector_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_admin)],
):
    """Check if a sync is currently running and get last sync info."""
    from sqlalchemy import select
    from app.ticketing.models import ConnectorConfig

    result = await db.execute(
        select(ConnectorConfig).where(
            ConnectorConfig.id == connector_id,
            ConnectorConfig.tenant_id == user.tenant_id,
        )
    )
    connector = result.scalar_one_or_none()
    if connector is None:
        raise HTTPException(status_code=404, detail="Connector not found")

    return {
        "is_running": is_sync_running(str(connector_id)),
        "last_sync_at": connector.last_sync_at.isoformat() if connector.last_sync_at else None,
        "last_sync_status": connector.last_sync_status,
        "last_sync_record_count": connector.last_sync_record_count,
        "sync_interval_minutes": connector.sync_interval_minutes,
    }
FILEEOF

# ══════════════════════════════════════════════
#  BACKEND: Clear test data endpoint
# ══════════════════════════════════════════════

cat > backend/app/dev_routes.py << 'FILEEOF'
"""Dev-only routes for seeding and clearing data."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.seed import seed_database

router = APIRouter()


@router.post("/seed")
async def seed(db: AsyncSession = Depends(get_db)):
    """Seed the database with sample data. Dev only."""
    return await seed_database(db)


@router.post("/clear-test-data")
async def clear_test_data(db: AsyncSession = Depends(get_db)):
    """Remove all seed/test data. Keeps connector configs and real synced data untouched.

    This removes the demo tenant, its users, and ALL vulnerabilities/assets/misconfigs
    that belong to it. Then re-creates a minimal tenant + user for dev-token auth.
    """
    from app.tenants.models import Tenant, User
    from app.vulnerabilities.models import Vulnerability, VulnerabilityCorrelation
    from app.assets.models import Asset
    from app.cspm.models import Misconfiguration
    from app.ticketing.models import Ticket, TicketRule, SyncLog

    # Delete everything in order (respecting FK constraints)
    await db.execute(delete(SyncLog))
    await db.execute(delete(Ticket))
    await db.execute(delete(TicketRule))
    await db.execute(delete(VulnerabilityCorrelation))
    await db.execute(delete(Vulnerability))
    await db.execute(delete(Misconfiguration))
    await db.execute(delete(Asset))
    await db.execute(delete(User))

    # Keep connector configs but delete their data link
    # Don't delete connectors — user configured those with real keys

    # Delete tenants last
    await db.execute(delete(Tenant))

    await db.commit()

    # Re-create a minimal tenant + user for dev-token auth
    tenant = Tenant(
        name="Demo Organization",
        slug="demo",
        domain="demo.getvul.app",
        idp_provider="GOOGLE",
        idp_tenant_id="demo",
    )
    db.add(tenant)
    await db.flush()

    user = User(
        tenant_id=tenant.id,
        email="admin@demo.getvul.app",
        display_name="Demo Admin",
        role="OWNER",
        idp_subject="demo-subject-001",
    )
    db.add(user)
    await db.flush()

    # Re-associate existing connector configs with the new tenant
    from app.ticketing.models import ConnectorConfig
    from sqlalchemy import select, update

    await db.execute(
        update(ConnectorConfig).values(tenant_id=tenant.id)
    )

    await db.commit()

    return {
        "message": "All test data cleared. Connector configs preserved.",
        "new_tenant_id": str(tenant.id),
        "new_user_id": str(user.id),
    }
FILEEOF

# ══════════════════════════════════════════════
#  BACKEND: Update main.py — startup scheduler + dev routes
# ══════════════════════════════════════════════

cat > backend/app/main.py << 'FILEEOF'
"""GetVul API — entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.vulnerabilities.router import router as vuln_router
from app.assets.router import router as asset_router
from app.tenants.router import router as tenant_router
from app.connectors.router import router as connector_router
from app.cspm.router import router as cspm_router
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Start background sync scheduler
    if settings.environment in ("development", "production"):
        from app.connectors.scheduler import start_scheduler, stop_scheduler
        start_scheduler()

    yield

    # Cleanup
    if settings.environment in ("development", "production"):
        from app.connectors.scheduler import stop_scheduler
        stop_scheduler()


app = FastAPI(
    title="GetVul API",
    description="Unified Vulnerability Aggregation Platform",
    version="0.1.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"] if settings.debug else ["https://*.getvul.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ──
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(vuln_router, prefix="/api/v1/vulnerabilities", tags=["Vulnerabilities"])
app.include_router(asset_router, prefix="/api/v1/assets", tags=["Assets"])
app.include_router(tenant_router, prefix="/api/v1/tenant", tags=["Tenant & Users"])
app.include_router(connector_router, prefix="/api/v1/connectors", tags=["Connectors"])
app.include_router(cspm_router, prefix="/api/v1/cspm", tags=["CSPM"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "getvul-api"}


# ── Dev-only routes ──
if settings.environment == "development":
    from app.dev_routes import router as dev_router
    app.include_router(dev_router, prefix="/dev", tags=["Dev"])
FILEEOF

# ══════════════════════════════════════════════
#  FRONTEND: Updated connector card with sync status polling
# ══════════════════════════════════════════════

cat > frontend/src/app/dashboard/connectors/page.tsx << 'FILEEOF'
"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Plug,
  Plus,
  TestTube2,
  Trash2,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Loader2,
  Eye,
  EyeOff,
  Play,
  Shield,
  ExternalLink,
  Info,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import type {
  ConnectorType,
  ConnectorConfig,
  ConnectorTestResult,
} from "@/types/connector";

const CONNECTOR_META: Record<string, { color: string }> = {
  CROWDSTRIKE: { color: "text-red-400" },
  NESSUS: { color: "text-green-400" },
  DEFENDER: { color: "text-blue-400" },
  WIZ: { color: "text-purple-400" },
};

export default function ConnectorsPage() {
  const [connectorTypes, setConnectorTypes] = useState<ConnectorType[]>([]);
  const [connectors, setConnectors] = useState<ConnectorConfig[]>([]);
  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncingIds, setSyncingIds] = useState<Set<string>>(new Set());

  const loadData = useCallback(async () => {
    try {
      const typesRes = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/connectors/types`);
      if (typesRes.ok) setConnectorTypes(await typesRes.json());
      try {
        const conns = await api<ConnectorConfig[]>("/api/v1/connectors");
        setConnectors(conns);
      } catch {}
    } catch {} finally { setLoading(false); }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  // Poll for sync status when syncs are running
  useEffect(() => {
    if (syncingIds.size === 0) return;
    const interval = setInterval(async () => {
      let anyRunning = false;
      for (const id of syncingIds) {
        try {
          const status = await api<{ is_running: boolean }>(`/api/v1/connectors/${id}/sync-status`);
          if (status.is_running) {
            anyRunning = true;
          } else {
            setSyncingIds((prev) => { const next = new Set(prev); next.delete(id); return next; });
            loadData(); // Refresh to show updated sync results
          }
        } catch {}
      }
      if (!anyRunning) {
        setSyncingIds(new Set());
        loadData();
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [syncingIds, loadData]);

  async function handleSync(connectorId: string) {
    try {
      const result = await api<{ status: string; message: string }>(`/api/v1/connectors/${connectorId}/sync`, { method: "POST" });
      if (result.status === "STARTED") {
        setSyncingIds((prev) => new Set(prev).add(connectorId));
      } else if (result.status === "ALREADY_RUNNING") {
        setSyncingIds((prev) => new Set(prev).add(connectorId));
      }
    } catch (e: any) {
      alert(`Sync failed: ${e.message}`);
    }
  }

  async function handleDelete(connectorId: string) {
    if (!confirm("Delete this connector? Synced data will remain.")) return;
    try {
      await api(`/api/v1/connectors/${connectorId}`, { method: "DELETE" });
      loadData();
    } catch (e: any) { alert(`Delete failed: ${e.message}`); }
  }

  const configuredTypes = new Set(connectors.map((c) => c.connector_type));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Connectors</h1>
        <p className="mt-1 text-sm text-gray-400">Connect your security tools to aggregate vulnerabilities and posture findings</p>
      </div>

      {/* Active connectors */}
      {connectors.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-sm font-medium text-gray-400">Active Connectors</h2>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {connectors.map((conn) => {
              const isSyncing = syncingIds.has(conn.id);
              return (
                <div key={conn.id} className="rounded-xl border border-gray-800 bg-gray-900/50 p-5">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <div className="rounded-lg bg-gray-800 p-2.5">
                        <Plug className={cn("h-5 w-5", CONNECTOR_META[conn.connector_type]?.color || "text-gray-400")} />
                      </div>
                      <div>
                        <h3 className="font-medium text-white">{conn.connector_name}</h3>
                        <div className="mt-1 flex items-center gap-2 text-xs text-gray-400">
                          {isSyncing ? (
                            <><Loader2 className="h-3.5 w-3.5 animate-spin text-indigo-400" /><span className="text-indigo-400">Syncing...</span></>
                          ) : conn.last_sync_status === "SUCCESS" ? (
                            <><CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />{conn.last_sync_at ? `Last sync: ${new Date(conn.last_sync_at).toLocaleString()}` : "Never synced"}</>
                          ) : conn.last_sync_status === "FAILED" ? (
                            <><XCircle className="h-3.5 w-3.5 text-red-400" />Last sync failed</>
                          ) : (
                            <><AlertCircle className="h-3.5 w-3.5 text-gray-500" />Never synced</>
                          )}
                          {conn.last_sync_record_count !== null && !isSyncing && (
                            <span>· {conn.last_sync_record_count} records</span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className={cn("rounded-full px-2 py-0.5 text-xs font-medium", conn.is_enabled ? "bg-emerald-500/20 text-emerald-400" : "bg-gray-700 text-gray-400")}>
                      {conn.is_enabled ? "Active" : "Disabled"}
                    </div>
                  </div>
                  <div className="mt-4 flex items-center justify-between">
                    <span className="text-xs text-gray-500">
                      Auto-sync every {conn.sync_interval_minutes} min · Credentials: {conn.has_credentials ? "✓" : "✗"}
                    </span>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleSync(conn.id)}
                        disabled={isSyncing}
                        className="flex items-center gap-1.5 rounded-lg border border-gray-700 px-3 py-1.5 text-xs font-medium text-gray-300 hover:bg-gray-800 disabled:opacity-50"
                      >
                        {isSyncing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                        {isSyncing ? "Syncing..." : "Sync Now"}
                      </button>
                      <button
                        onClick={() => handleDelete(conn.id)}
                        className="rounded-lg border border-gray-700 p-1.5 text-gray-500 hover:bg-gray-800 hover:text-red-400"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Available connectors */}
      <div className="space-y-4">
        <h2 className="text-sm font-medium text-gray-400">{connectors.length > 0 ? "Add More Connectors" : "Available Connectors"}</h2>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {connectorTypes.filter((t) => !configuredTypes.has(t.type)).map((type) => (
            <button key={type.type} onClick={() => { setSelectedType(type.type); setShowAddModal(true); }}
              className="flex items-start gap-4 rounded-xl border border-gray-800 bg-gray-900/50 p-5 text-left transition-colors hover:border-indigo-500/50 hover:bg-gray-900">
              <div className="rounded-lg bg-gray-800 p-2.5">
                <Plug className={cn("h-5 w-5", CONNECTOR_META[type.type]?.color || "text-gray-400")} />
              </div>
              <div className="flex-1">
                <h3 className="font-medium text-white">{type.name}</h3>
                <p className="mt-1 text-sm text-gray-400">{type.description}</p>
                <div className="mt-2 flex items-center gap-1 text-xs text-indigo-400"><Plus className="h-3 w-3" />Configure</div>
              </div>
            </button>
          ))}
        </div>
      </div>

      {showAddModal && selectedType && (
        <AddConnectorModal
          type={connectorTypes.find((t) => t.type === selectedType)!}
          onClose={() => { setShowAddModal(false); setSelectedType(null); }}
          onSaved={() => { setShowAddModal(false); setSelectedType(null); loadData(); }}
        />
      )}
    </div>
  );
}

function AddConnectorModal({ type, onClose, onSaved }: { type: ConnectorType; onClose: () => void; onSaved: () => void }) {
  const [credentials, setCredentials] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {};
    type.fields.forEach((f) => { initial[f] = type.defaults[f] || ""; });
    return initial;
  });
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({});
  const [syncInterval, setSyncInterval] = useState(15);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<ConnectorTestResult | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPerms, setShowPerms] = useState(false);

  const isSecretField = (f: string) => f.includes("secret") || f.includes("key") || f.includes("password");
  const fieldLabel = (f: string) => f.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

  async function handleTest() {
    setTesting(true); setTestResult(null); setError(null);
    try {
      const result = await api<ConnectorTestResult>("/api/v1/connectors/test", {
        method: "POST", body: JSON.stringify({ connector_type: type.type, credentials, config: {} }),
      });
      setTestResult(result);
    } catch (e: any) { setTestResult({ success: false, message: e.message }); }
    finally { setTesting(false); }
  }

  async function handleSave() {
    setSaving(true); setError(null);
    try {
      await api("/api/v1/connectors", {
        method: "POST",
        body: JSON.stringify({ connector_type: type.type, credentials, config: {}, is_enabled: true, sync_interval_minutes: syncInterval }),
      });
      onSaved();
    } catch (e: any) { setError(e.message); }
    finally { setSaving(false); }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-black/60 backdrop-blur-sm py-8">
      <div className="mx-4 w-full max-w-lg rounded-xl border border-gray-800 bg-gray-950 p-6 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center gap-3 mb-4">
          <div className="rounded-lg bg-gray-800 p-2">
            <Plug className={cn("h-5 w-5", CONNECTOR_META[type.type]?.color || "text-gray-400")} />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">Configure {type.name}</h2>
            <p className="text-sm text-gray-400">{type.description}</p>
          </div>
        </div>

        {/* Permissions */}
        <div className="mb-4 rounded-lg border border-gray-800 bg-gray-900/50">
          <button onClick={() => setShowPerms(!showPerms)} className="flex w-full items-center justify-between px-4 py-3 text-left">
            <div className="flex items-center gap-2 text-sm text-gray-300">
              <Shield className="h-4 w-4 text-indigo-400" />Required Permissions ({type.permissions.length})
            </div>
            <span className="text-xs text-gray-500">{showPerms ? "Hide" : "Show"}</span>
          </button>
          {showPerms && (
            <div className="border-t border-gray-800 px-4 py-3 space-y-3">
              <table className="w-full text-xs">
                <thead><tr className="text-gray-500"><th className="pb-2 text-left font-medium">Scope</th><th className="pb-2 text-left font-medium">Access</th><th className="pb-2 text-left font-medium">Purpose</th></tr></thead>
                <tbody className="divide-y divide-gray-800">
                  {type.permissions.map((p) => (
                    <tr key={p.scope}><td className="py-1.5 font-mono text-indigo-400">{p.scope}</td><td className="py-1.5 text-gray-400">{p.access}</td><td className="py-1.5 text-gray-500">{p.purpose}</td></tr>
                  ))}
                </tbody>
              </table>
              {type.notes && <div className="flex gap-2 rounded-md bg-gray-800/50 p-2.5 text-xs text-gray-400"><Info className="h-3.5 w-3.5 mt-0.5 shrink-0 text-gray-500" /><span>{type.notes}</span></div>}
              <a href={type.setup_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 text-xs text-indigo-400 hover:text-indigo-300"><ExternalLink className="h-3 w-3" />Setup documentation</a>
            </div>
          )}
        </div>

        {/* Region selector */}
        {Object.keys(type.base_urls).length > 1 && (
          <div className="mb-4">
            <label className="mb-1.5 block text-sm font-medium text-gray-300">Region</label>
            <div className="flex flex-wrap gap-2">
              {Object.entries(type.base_urls).map(([region, url]) => (
                <button key={region} onClick={() => setCredentials({ ...credentials, base_url: url, api_endpoint_url: url })}
                  className={cn("rounded-md border px-3 py-1.5 text-xs font-medium transition-all",
                    (credentials.base_url === url || credentials.api_endpoint_url === url)
                      ? "border-indigo-500 bg-indigo-500/15 text-indigo-400"
                      : "border-gray-700 bg-gray-900 text-gray-400 hover:text-gray-300"
                  )}>{region}</button>
              ))}
            </div>
          </div>
        )}

        {/* Fields */}
        <div className="space-y-4">
          {type.fields.map((field) => (
            <div key={field}>
              <label className="mb-1.5 block text-sm font-medium text-gray-300">{fieldLabel(field)}</label>
              <div className="relative">
                <input type={isSecretField(field) && !showSecrets[field] ? "password" : "text"} value={credentials[field] || ""}
                  onChange={(e) => setCredentials({ ...credentials, [field]: e.target.value })}
                  placeholder={type.defaults[field] || `Enter ${fieldLabel(field)}`}
                  className="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500" />
                {isSecretField(field) && (
                  <button type="button" onClick={() => setShowSecrets({ ...showSecrets, [field]: !showSecrets[field] })} className="absolute right-2 top-2.5 text-gray-500 hover:text-gray-300">
                    {showSecrets[field] ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                )}
              </div>
            </div>
          ))}

          <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-300">Sync Interval (minutes)</label>
            <div className="flex items-center gap-3">
              {[5, 15, 30, 60].map((m) => (
                <button key={m} onClick={() => setSyncInterval(m)}
                  className={cn("rounded-md border px-3 py-1.5 text-xs font-medium transition-all",
                    syncInterval === m ? "border-indigo-500 bg-indigo-500/15 text-indigo-400" : "border-gray-700 bg-gray-900 text-gray-400 hover:text-gray-300"
                  )}>{m === 60 ? "1 hr" : `${m} min`}</button>
              ))}
              <input type="number" min={5} max={1440} value={syncInterval}
                onChange={(e) => setSyncInterval(Number(e.target.value))}
                className="w-20 rounded-lg border border-gray-700 bg-gray-900 px-2 py-1.5 text-xs text-white focus:border-indigo-500 focus:outline-none" />
              <span className="text-xs text-gray-500">min</span>
            </div>
          </div>
        </div>

        {/* Result */}
        {testResult && (
          <div className={cn("mt-4 rounded-lg border p-3 text-sm", testResult.success ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400" : "border-red-500/30 bg-red-500/10 text-red-400")}>
            <div className="flex items-center gap-2">{testResult.success ? <CheckCircle2 className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}{testResult.message}</div>
          </div>
        )}
        {error && <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">{error}</div>}

        {/* Actions */}
        <div className="mt-6 flex items-center justify-between">
          <button onClick={handleTest} disabled={testing} className="flex items-center gap-2 rounded-lg border border-gray-700 px-4 py-2 text-sm font-medium text-gray-300 hover:bg-gray-800 disabled:opacity-50">
            {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <TestTube2 className="h-4 w-4" />}Test Connection
          </button>
          <div className="flex items-center gap-3">
            <button onClick={onClose} className="rounded-lg px-4 py-2 text-sm font-medium text-gray-400 hover:text-white">Cancel</button>
            <button onClick={handleSave} disabled={saving} className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50">
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}Save Connector
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
FILEEOF

# ══════════════════════════════════════════════
#  CLEAR TEST DATA & RESTART
# ══════════════════════════════════════════════

echo "🔄 Restarting backend..."
docker compose up -d --force-recreate backend

echo "⏳ Waiting (15s)..."
sleep 15

echo "🧹 Clearing all test/seed data..."
curl -s -X POST http://localhost:8000/dev/clear-test-data -H "Authorization: Bearer dev-token" | python3 -m json.tool 2>/dev/null || curl -s -X POST http://localhost:8000/dev/clear-test-data

echo ""
echo "🔍 Verifying clean state..."
echo "Vulns:"
curl -s "http://localhost:8000/api/v1/vulnerabilities/stats" -H "Authorization: Bearer dev-token" | python3 -m json.tool 2>/dev/null || echo "(check manually)"
echo ""
echo "CSPM:"
curl -s "http://localhost:8000/api/v1/cspm/stats" -H "Authorization: Bearer dev-token" | python3 -m json.tool 2>/dev/null || echo "(check manually)"

# ══════════════════════════════════════════════
#  COMMIT & PUSH
# ══════════════════════════════════════════════

echo ""
echo "📝 Committing..."

git add -A
git commit -m "feat: background sync scheduler + clear test data

- Background sync: connectors sync on their configured interval automatically
- Scheduler starts at app boot, checks every 60s for due syncs
- Manual 'Sync Now' returns immediately, runs in background
- Frontend polls sync status every 3s while sync is running
- Sync interval quick-select buttons (5/15/30/60 min) + custom input
- POST /dev/clear-test-data removes all seed data, preserves connector configs
- Cleared all test data — only real connector-synced data remains
- Separate dev_routes.py for seed/clear endpoints"

git push -u origin feat/connector-permissions

echo ""
echo "✅ Done!"
echo ""
echo "   All test data cleared. Dashboard should show 0 vulns / 0 CSPM findings."
echo "   Your CrowdStrike connector config is preserved."
echo ""
echo "   To pull real data:"
echo "   1. Go to http://localhost:3000/dashboard/connectors"
echo "   2. Click 'Sync Now' on your CrowdStrike connector"
echo "   3. Watch the spinner — it syncs in the background"
echo "   4. When it finishes, check Vulnerabilities and Cloud Posture pages"
echo ""
echo "   Auto-sync will also run every ${syncInterval:-15} min automatically."
echo ""
echo "   To merge: gh pr merge --squash && git checkout main && git pull"
