#!/bin/bash
set -euo pipefail

cd ~/Desktop/getvul

echo "🖥️ Building asset inventory page..."

git checkout main 2>/dev/null && git pull 2>/dev/null || true
git checkout -b feat/asset-inventory 2>/dev/null || git checkout feat/asset-inventory

# ══════════════════════════════════════════════
#  Backend: Risk score computation
# ══════════════════════════════════════════════

cat > backend/app/assets/risk.py << 'FILEEOF'
"""Compute risk scores for assets based on open vulnerabilities."""

from __future__ import annotations

import uuid

from sqlalchemy import func, case, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.vulnerabilities.models import Vulnerability


async def compute_risk_score(db: AsyncSession, asset_id: uuid.UUID) -> int:
    """Compute risk score (0-100) for a single asset.

    Formula:
      raw = sum of weights per open vuln:
        CRITICAL=40, HIGH=20, MEDIUM=5, LOW=1
        × 2 if exploit_available
        × 3 if cisa_kev
      score = min(100, raw)
    """
    q = select(
        func.sum(
            case(
                (Vulnerability.severity == "CRITICAL", 40),
                (Vulnerability.severity == "HIGH", 20),
                (Vulnerability.severity == "MEDIUM", 5),
                (Vulnerability.severity == "LOW", 1),
                else_=0,
            )
            * case((Vulnerability.exploit_available.is_(True), 2), else_=1)
            * case((Vulnerability.cisa_kev.is_(True), 3), else_=1)
        )
    ).where(
        Vulnerability.asset_id == asset_id,
        Vulnerability.status == "OPEN",
    )
    raw = (await db.execute(q)).scalar_one() or 0
    return min(100, raw)


async def recompute_all_risk_scores(db: AsyncSession, tenant_id: uuid.UUID) -> int:
    """Recompute risk scores for all assets in a tenant. Returns count updated."""
    result = await db.execute(
        select(Asset.id).where(Asset.tenant_id == tenant_id)
    )
    asset_ids = [r[0] for r in result.all()]

    count = 0
    for aid in asset_ids:
        score = await compute_risk_score(db, aid)
        await db.execute(
            update(Asset).where(Asset.id == aid).values(risk_score=score)
        )
        count += 1

    return count
FILEEOF

# ══════════════════════════════════════════════
#  Backend: Enhanced asset service with stats
# ══════════════════════════════════════════════

cat > backend/app/assets/service.py << 'FILEEOF'
"""Asset business logic and database queries."""

from __future__ import annotations

import uuid

from sqlalchemy import Select, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.assets.schemas import AssetFilter, AssetResponse, AssetSummary
from app.pagination import PaginatedResponse, PaginationParams
from app.vulnerabilities.models import Vulnerability


def _apply_filters(query: Select, tenant_id: uuid.UUID, filters: AssetFilter) -> Select:
    query = query.where(Asset.tenant_id == tenant_id)
    if filters.hostname:
        query = query.where(Asset.hostname.ilike(f"%{filters.hostname}%"))
    if filters.os_name:
        query = query.where(Asset.os_name.ilike(f"%{filters.os_name}%"))
    if filters.asset_type:
        query = query.where(Asset.asset_type == filters.asset_type)
    if filters.cloud_provider:
        query = query.where(Asset.cloud_provider == filters.cloud_provider)
    if filters.source:
        query = query.where(Asset.seen_by_sources.contains([filters.source]))
    if filters.risk_score_min is not None:
        query = query.where(Asset.risk_score >= filters.risk_score_min)
    if filters.search:
        query = query.where(
            or_(
                Asset.hostname.ilike(f"%{filters.search}%"),
                Asset.os_name.ilike(f"%{filters.search}%"),
            )
        )
    return query


async def list_assets(
    db: AsyncSession, tenant_id: uuid.UUID, filters: AssetFilter, pagination: PaginationParams,
) -> PaginatedResponse[AssetSummary]:
    count_q = _apply_filters(select(func.count(Asset.id)), tenant_id, filters)
    total = (await db.execute(count_q)).scalar_one()

    # Subquery: open vuln counts per severity per asset
    vuln_sub = (
        select(
            Vulnerability.asset_id,
            func.count(Vulnerability.id).label("open_vuln_count"),
            func.count(Vulnerability.id).filter(Vulnerability.severity == "CRITICAL").label("critical_count"),
            func.count(Vulnerability.id).filter(Vulnerability.severity == "HIGH").label("high_count"),
            func.count(Vulnerability.id).filter(Vulnerability.exploit_available.is_(True)).label("exploitable_count"),
            func.count(Vulnerability.id).filter(Vulnerability.cisa_kev.is_(True)).label("kev_count"),
        )
        .where(Vulnerability.tenant_id == tenant_id, Vulnerability.status == "OPEN")
        .group_by(Vulnerability.asset_id)
        .subquery()
    )

    data_q = (
        _apply_filters(select(Asset), tenant_id, filters)
        .outerjoin(vuln_sub, Asset.id == vuln_sub.c.asset_id)
        .add_columns(
            func.coalesce(vuln_sub.c.open_vuln_count, 0).label("open_vuln_count"),
            func.coalesce(vuln_sub.c.critical_count, 0).label("critical_count"),
            func.coalesce(vuln_sub.c.high_count, 0).label("high_count"),
            func.coalesce(vuln_sub.c.exploitable_count, 0).label("exploitable_count"),
            func.coalesce(vuln_sub.c.kev_count, 0).label("kev_count"),
        )
        .order_by(Asset.risk_score.desc().nullslast(), Asset.hostname.asc())
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    results = (await db.execute(data_q)).all()

    items = []
    for row in results:
        asset = row[0]
        items.append(AssetSummary(
            id=asset.id,
            hostname=asset.hostname,
            os_name=asset.os_name,
            os_version=asset.os_version,
            asset_type=asset.asset_type,
            cloud_provider=asset.cloud_provider,
            seen_by_sources=asset.seen_by_sources,
            risk_score=asset.risk_score,
            open_vuln_count=row.open_vuln_count,
            critical_count=row.critical_count,
            high_count=row.high_count,
            exploitable_count=row.exploitable_count,
            kev_count=row.kev_count,
        ))

    return PaginatedResponse.create(items=items, total=total, params=pagination)


async def get_asset(db: AsyncSession, tenant_id: uuid.UUID, asset_id: uuid.UUID) -> AssetResponse | None:
    result = await db.execute(
        select(Asset).where(Asset.id == asset_id, Asset.tenant_id == tenant_id)
    )
    asset = result.scalar_one_or_none()
    if asset is None:
        return None

    sev_q = (
        select(Vulnerability.severity, func.count(Vulnerability.id))
        .where(Vulnerability.asset_id == asset_id, Vulnerability.tenant_id == tenant_id, Vulnerability.status == "OPEN")
        .group_by(Vulnerability.severity)
    )
    sev_rows = (await db.execute(sev_q)).all()
    vuln_counts = {r[0]: r[1] for r in sev_rows}

    return AssetResponse(
        id=asset.id, tenant_id=asset.tenant_id, hostname=asset.hostname,
        ip_addresses=asset.ip_addresses, mac_addresses=asset.mac_addresses,
        os_name=asset.os_name, os_version=asset.os_version,
        asset_type=asset.asset_type, cloud_provider=asset.cloud_provider,
        cloud_resource_id=asset.cloud_resource_id,
        seen_by_sources=asset.seen_by_sources, risk_score=asset.risk_score,
        created_at=asset.created_at, updated_at=asset.updated_at,
        vuln_counts=vuln_counts,
    )


async def get_asset_stats(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    """Dashboard stats for assets."""
    total = (await db.execute(
        select(func.count(Asset.id)).where(Asset.tenant_id == tenant_id)
    )).scalar_one()

    # By OS
    os_rows = (await db.execute(
        select(Asset.os_name, func.count(Asset.id))
        .where(Asset.tenant_id == tenant_id, Asset.os_name.isnot(None))
        .group_by(Asset.os_name).order_by(func.count(Asset.id).desc()).limit(10)
    )).all()

    # By risk score range
    risk_q = select(
        case(
            (Asset.risk_score >= 80, "Critical (80-100)"),
            (Asset.risk_score >= 50, "High (50-79)"),
            (Asset.risk_score >= 20, "Medium (20-49)"),
            else_="Low (0-19)",
        ).label("risk_range"),
        func.count(Asset.id),
    ).where(Asset.tenant_id == tenant_id, Asset.risk_score.isnot(None)).group_by("risk_range")
    risk_rows = (await db.execute(risk_q)).all()

    # Scanner coverage
    sources = ["CROWDSTRIKE", "NESSUS", "DEFENDER", "WIZ"]
    coverage = {}
    for src in sources:
        cnt = (await db.execute(
            select(func.count(Asset.id))
            .where(Asset.tenant_id == tenant_id, Asset.seen_by_sources.contains([src]))
        )).scalar_one()
        if cnt > 0:
            coverage[src] = cnt

    # Average risk score
    avg_risk = (await db.execute(
        select(func.avg(Asset.risk_score))
        .where(Asset.tenant_id == tenant_id, Asset.risk_score.isnot(None))
    )).scalar_one()

    return {
        "total_assets": total,
        "average_risk_score": round(float(avg_risk), 1) if avg_risk else 0,
        "by_os": [{"os": r[0], "count": r[1]} for r in os_rows],
        "by_risk_range": [{"range": r[0], "count": r[1]} for r in risk_rows],
        "scanner_coverage": coverage,
    }
FILEEOF

# ══════════════════════════════════════════════
#  Backend: Updated asset schemas
# ══════════════════════════════════════════════

cat > backend/app/assets/schemas.py << 'FILEEOF'
"""Pydantic schemas for asset endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AssetResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    hostname: str | None
    ip_addresses: list | None
    mac_addresses: list | None
    os_name: str | None
    os_version: str | None
    asset_type: str | None
    cloud_provider: str | None
    cloud_resource_id: str | None
    seen_by_sources: list | None
    risk_score: int | None
    created_at: datetime
    updated_at: datetime
    vuln_counts: dict | None = None

    model_config = {"from_attributes": True}


class AssetSummary(BaseModel):
    id: uuid.UUID
    hostname: str | None
    os_name: str | None
    os_version: str | None
    asset_type: str | None
    cloud_provider: str | None
    seen_by_sources: list | None
    risk_score: int | None
    open_vuln_count: int = 0
    critical_count: int = 0
    high_count: int = 0
    exploitable_count: int = 0
    kev_count: int = 0

    model_config = {"from_attributes": True}


class AssetFilter(BaseModel):
    hostname: str | None = None
    os_name: str | None = None
    asset_type: str | None = None
    cloud_provider: str | None = None
    source: str | None = Field(None, description="Filter by scanner source")
    risk_score_min: int | None = Field(None, ge=0, le=100)
    search: str | None = None
FILEEOF

# ══════════════════════════════════════════════
#  Backend: Updated asset router with stats + risk recompute
# ══════════════════════════════════════════════

cat > backend/app/assets/router.py << 'FILEEOF'
"""Asset API routes."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.rbac import require_admin, require_viewer
from app.auth.schemas import CurrentUser
from app.dependencies import AuthenticatedUser, DBSession
from app.pagination import PaginatedResponse, PaginationParams
from app.assets.schemas import AssetFilter, AssetResponse, AssetSummary
from app.assets.service import get_asset, get_asset_stats, list_assets

router = APIRouter()


@router.get("/stats")
async def asset_stats(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
):
    """Get asset dashboard statistics."""
    return await get_asset_stats(db, user.tenant_id)


@router.get("", response_model=PaginatedResponse[AssetSummary])
async def list_all_assets(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    hostname: str | None = Query(None),
    os_name: str | None = Query(None),
    asset_type: str | None = Query(None),
    cloud_provider: str | None = Query(None),
    source: str | None = Query(None),
    risk_score_min: int | None = Query(None, ge=0, le=100),
    search: str | None = Query(None),
):
    filters = AssetFilter(
        hostname=hostname, os_name=os_name, asset_type=asset_type,
        cloud_provider=cloud_provider, source=source,
        risk_score_min=risk_score_min, search=search,
    )
    pagination = PaginationParams(page=page, page_size=page_size)
    return await list_assets(db, user.tenant_id, filters, pagination)


@router.get("/{asset_id}", response_model=AssetResponse)
async def get_single_asset(
    asset_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
):
    asset = await get_asset(db, user.tenant_id, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.get("/{asset_id}/vulnerabilities")
async def get_asset_vulns(
    asset_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    severity: list[str] | None = Query(None),
    status: list[str] | None = Query(None),
):
    from app.vulnerabilities.schemas import VulnerabilityFilter
    from app.vulnerabilities.service import list_vulnerabilities
    filters = VulnerabilityFilter(asset_id=asset_id, severity=severity, status=status)
    pagination = PaginationParams(page=page, page_size=page_size)
    return await list_vulnerabilities(db, user.tenant_id, filters, pagination)


@router.post("/recompute-risk-scores")
async def recompute_risk(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_admin)],
):
    """Recompute risk scores for all assets. Requires Admin."""
    from app.assets.risk import recompute_all_risk_scores
    count = await recompute_all_risk_scores(db, user.tenant_id)
    return {"message": f"Recomputed risk scores for {count} assets", "count": count}
FILEEOF

# ══════════════════════════════════════════════
#  Frontend: Asset types
# ══════════════════════════════════════════════

cat > frontend/src/types/asset.ts << 'FILEEOF'
export interface AssetSummary {
  id: string;
  hostname: string | null;
  os_name: string | null;
  os_version: string | null;
  asset_type: string | null;
  cloud_provider: string | null;
  seen_by_sources: string[] | null;
  risk_score: number | null;
  open_vuln_count: number;
  critical_count: number;
  high_count: number;
  exploitable_count: number;
  kev_count: number;
}

export interface AssetStats {
  total_assets: number;
  average_risk_score: number;
  by_os: { os: string; count: number }[];
  by_risk_range: { range: string; count: number }[];
  scanner_coverage: Record<string, number>;
}
FILEEOF

# ══════════════════════════════════════════════
#  Frontend: Asset inventory page
# ══════════════════════════════════════════════

cat > frontend/src/app/dashboard/assets/page.tsx << 'FILEEOF'
"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Server, Search, X, Filter, RefreshCw, Loader2,
  Shield, AlertTriangle, Flame, ShieldAlert, ChevronRight,
} from "lucide-react";
import { api } from "@/lib/api";
import { SeverityBadge, SourceBadge } from "@/components/ui/Badge";
import Pagination from "@/components/ui/Pagination";
import { cn } from "@/lib/utils";
import type { AssetSummary, AssetStats } from "@/types/asset";

interface PaginatedAssets {
  items: AssetSummary[];
  total: number; page: number; page_size: number; total_pages: number;
}

const SOURCES = ["CROWDSTRIKE", "NESSUS", "DEFENDER", "WIZ"];

function riskColor(score: number | null): string {
  if (score === null) return "text-gray-500";
  if (score >= 80) return "text-red-400";
  if (score >= 50) return "text-orange-400";
  if (score >= 20) return "text-yellow-400";
  return "text-emerald-400";
}

function riskBg(score: number | null): string {
  if (score === null) return "bg-gray-800";
  if (score >= 80) return "bg-red-500";
  if (score >= 50) return "bg-orange-500";
  if (score >= 20) return "bg-yellow-500";
  return "bg-emerald-500";
}

export default function AssetsPage() {
  const [stats, setStats] = useState<AssetStats | null>(null);
  const [data, setData] = useState<PaginatedAssets | null>(null);
  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);
  const [page, setPage] = useState(1);

  // Filters
  const [search, setSearch] = useState("");
  const [sourceFilter, setSourceFilter] = useState<string | null>(null);
  const [riskMin, setRiskMin] = useState<number | null>(null);

  const loadStats = useCallback(async () => {
    try { setStats(await api<AssetStats>("/api/v1/assets/stats")); } catch (e) { console.error(e); }
  }, []);

  const loadAssets = useCallback(async () => {
    setLoading(true);
    try {
      const p = new URLSearchParams();
      p.set("page", String(page)); p.set("page_size", "30");
      if (search) p.set("search", search);
      if (sourceFilter) p.set("source", sourceFilter);
      if (riskMin !== null) p.set("risk_score_min", String(riskMin));
      setData(await api<PaginatedAssets>(`/api/v1/assets?${p}`));
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [page, search, sourceFilter, riskMin]);

  useEffect(() => { loadStats(); }, [loadStats]);
  useEffect(() => {
    const t = setTimeout(loadAssets, 300);
    return () => clearTimeout(t);
  }, [loadAssets]);
  useEffect(() => { setPage(1); }, [search, sourceFilter, riskMin]);

  async function handleRecompute() {
    setRecomputing(true);
    try {
      await api("/api/v1/assets/recompute-risk-scores", { method: "POST" });
      await loadStats();
      await loadAssets();
    } catch (e) { console.error(e); }
    finally { setRecomputing(false); }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Server className="h-6 w-6 text-emerald-400" />
          <div>
            <h1 className="text-2xl font-bold text-white">Asset Inventory</h1>
            {stats && <p className="text-sm text-gray-400">{stats.total_assets.toLocaleString()} assets discovered</p>}
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={handleRecompute} disabled={recomputing}
            className="flex items-center gap-2 rounded-lg border border-gray-700 px-3 py-2 text-sm text-gray-300 hover:bg-gray-800 disabled:opacity-50">
            {recomputing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Shield className="h-4 w-4" />}
            Recompute Risk
          </button>
          <button onClick={() => { loadStats(); loadAssets(); }}
            className="flex items-center gap-2 rounded-lg border border-gray-700 px-3 py-2 text-sm text-gray-300 hover:bg-gray-800">
            <RefreshCw className="h-4 w-4" />Refresh
          </button>
        </div>
      </div>

      {/* Stats cards */}
      {stats && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard icon={<Server className="h-5 w-5 text-emerald-400" />} label="Total Assets" value={stats.total_assets.toLocaleString()} />
          <StatCard icon={<Shield className="h-5 w-5 text-indigo-400" />} label="Avg Risk Score"
            value={stats.average_risk_score.toString()} extra={<RiskBar score={stats.average_risk_score} />} />

          {/* Scanner coverage */}
          <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-5">
            <div className="flex items-center gap-3"><Server className="h-5 w-5 text-sky-400" /><span className="text-sm text-gray-400">Scanner Coverage</span></div>
            <div className="mt-3 space-y-1.5">
              {Object.entries(stats.scanner_coverage).map(([src, cnt]) => (
                <div key={src} className="flex items-center justify-between">
                  <SourceBadge source={src} />
                  <span className="text-sm font-medium text-white">{cnt.toLocaleString()}</span>
                </div>
              ))}
              {Object.keys(stats.scanner_coverage).length === 0 && <span className="text-xs text-gray-500">No scanners connected</span>}
            </div>
          </div>

          {/* Risk distribution */}
          <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-5">
            <div className="flex items-center gap-3"><AlertTriangle className="h-5 w-5 text-orange-400" /><span className="text-sm text-gray-400">Risk Distribution</span></div>
            <div className="mt-3 space-y-1.5">
              {stats.by_risk_range.map((r) => (
                <div key={r.range} className="flex items-center justify-between">
                  <span className="text-xs text-gray-300">{r.range}</span>
                  <span className="text-sm font-medium text-white">{r.count}</span>
                </div>
              ))}
              {stats.by_risk_range.length === 0 && <span className="text-xs text-gray-500">Run "Recompute Risk" first</span>}
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="space-y-3">
        <div className="relative">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-500" />
          <input type="text" value={search} onChange={(e) => setSearch(e.target.value)}
            placeholder="Search hostname, OS..."
            className="w-full rounded-lg border border-gray-700 bg-gray-900 py-2 pl-10 pr-4 text-sm text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none" />
          {search && <button onClick={() => setSearch("")} className="absolute right-3 top-2.5 text-gray-500 hover:text-gray-300"><X className="h-4 w-4" /></button>}
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs text-gray-500"><Filter className="h-3.5 w-3.5" />Filters</div>

          {/* Source filter */}
          <div className="flex gap-1.5">
            {SOURCES.map((s) => (
              <button key={s} onClick={() => setSourceFilter(sourceFilter === s ? null : s)}
                className={cn("rounded-md border px-2 py-0.5 text-xs font-medium transition-all",
                  sourceFilter === s
                    ? "border-indigo-500/40 bg-indigo-500/15 text-indigo-400"
                    : "border-gray-700 bg-gray-900 text-gray-500 hover:text-gray-300"
                )}>
                {s === "CROWDSTRIKE" ? "CS" : s === "DEFENDER" ? "MDE" : s}
              </button>
            ))}
          </div>

          <div className="h-4 w-px bg-gray-700" />

          {/* Risk score filter */}
          <div className="flex gap-1.5">
            {[
              { label: "Critical 80+", min: 80 },
              { label: "High 50+", min: 50 },
              { label: "Medium 20+", min: 20 },
            ].map((r) => (
              <button key={r.min} onClick={() => setRiskMin(riskMin === r.min ? null : r.min)}
                className={cn("rounded-md border px-2 py-0.5 text-xs font-medium transition-all",
                  riskMin === r.min
                    ? "border-red-500/40 bg-red-500/15 text-red-400"
                    : "border-gray-700 bg-gray-900 text-gray-500 hover:text-gray-300"
                )}>
                {r.label}
              </button>
            ))}
          </div>

          {(sourceFilter || riskMin !== null) && (
            <button onClick={() => { setSourceFilter(null); setRiskMin(null); }}
              className="text-xs text-gray-500 hover:text-gray-300">Clear filters</button>
          )}
        </div>
      </div>

      {/* Table */}
      {loading && !data ? (
        <div className="flex justify-center py-20"><Loader2 className="h-8 w-8 animate-spin text-indigo-500" /></div>
      ) : (
        <>
          <div className="overflow-hidden rounded-xl border border-gray-800">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-gray-800 bg-gray-900/70">
                <th className="px-3 py-3 text-left font-medium text-gray-400">Hostname</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">OS</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Scanners</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Risk</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Vulns</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Critical</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">High</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Exploitable</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">KEV</th>
                <th className="w-8 px-3 py-3"></th>
              </tr></thead>
              <tbody className="divide-y divide-gray-800/50">
                {(data?.items || []).map((asset) => (
                  <tr key={asset.id} className="hover:bg-gray-800/30 cursor-pointer"
                    onClick={() => window.location.href = `/dashboard/assets/${asset.id}`}>
                    <td className="px-3 py-2.5 text-white font-medium">{asset.hostname || "—"}</td>
                    <td className="px-3 py-2.5 text-xs text-gray-400">{asset.os_name} {asset.os_version}</td>
                    <td className="px-3 py-2.5">
                      <div className="flex gap-1">
                        {(asset.seen_by_sources || []).map((s) => <SourceBadge key={s} source={s} />)}
                      </div>
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-2">
                        <span className={cn("text-sm font-bold", riskColor(asset.risk_score))}>{asset.risk_score ?? "—"}</span>
                        <div className="h-1.5 w-16 overflow-hidden rounded-full bg-gray-800">
                          <div className={cn("h-full rounded-full", riskBg(asset.risk_score))}
                            style={{ width: `${Math.min(100, asset.risk_score || 0)}%` }} />
                        </div>
                      </div>
                    </td>
                    <td className="px-3 py-2.5 text-white">{asset.open_vuln_count}</td>
                    <td className="px-3 py-2.5">
                      {asset.critical_count > 0 ? (
                        <span className="rounded bg-red-500/20 px-1.5 py-0.5 text-xs font-medium text-red-400">{asset.critical_count}</span>
                      ) : <span className="text-gray-600">0</span>}
                    </td>
                    <td className="px-3 py-2.5">
                      {asset.high_count > 0 ? (
                        <span className="rounded bg-orange-500/20 px-1.5 py-0.5 text-xs font-medium text-orange-400">{asset.high_count}</span>
                      ) : <span className="text-gray-600">0</span>}
                    </td>
                    <td className="px-3 py-2.5">
                      {asset.exploitable_count > 0 ? (
                        <span className="flex items-center gap-1 text-xs font-medium text-orange-400">
                          <Flame className="h-3 w-3" />{asset.exploitable_count}
                        </span>
                      ) : <span className="text-gray-600">0</span>}
                    </td>
                    <td className="px-3 py-2.5">
                      {asset.kev_count > 0 ? (
                        <span className="text-xs font-medium text-red-400">🛡️ {asset.kev_count}</span>
                      ) : <span className="text-gray-600">0</span>}
                    </td>
                    <td className="px-3 py-2.5"><ChevronRight className="h-4 w-4 text-gray-600" /></td>
                  </tr>
                ))}
              </tbody>
            </table>
            {data?.items.length === 0 && <div className="py-12 text-center text-gray-500">No assets match your filters</div>}
          </div>
          {data && data.total_pages > 1 && (
            <Pagination page={data.page} totalPages={data.total_pages} total={data.total} pageSize={data.page_size} onPageChange={setPage} />
          )}
        </>
      )}
    </div>
  );
}

function StatCard({ icon, label, value, extra }: { icon: React.ReactNode; label: string; value: string; extra?: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-5">
      <div className="flex items-center gap-3">{icon}<span className="text-sm text-gray-400">{label}</span></div>
      <p className="mt-3 text-2xl font-bold text-white">{value}</p>
      {extra}
    </div>
  );
}

function RiskBar({ score }: { score: number }) {
  return (
    <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-gray-800">
      <div className={cn("h-full rounded-full transition-all", riskBg(score))}
        style={{ width: `${Math.min(100, score)}%` }} />
    </div>
  );
}
FILEEOF

# ══════════════════════════════════════════════
#  Frontend: Asset detail page
# ══════════════════════════════════════════════

mkdir -p "frontend/src/app/dashboard/assets/[id]"

cat > "frontend/src/app/dashboard/assets/[id]/page.tsx" << 'FILEEOF'
"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Server, ArrowLeft, Shield, Flame, ShieldAlert, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { SeverityBadge, SourceBadge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";

interface AssetDetail {
  id: string; hostname: string | null; ip_addresses: string[];
  os_name: string | null; os_version: string | null;
  asset_type: string | null; cloud_provider: string | null;
  seen_by_sources: string[]; risk_score: number | null;
  vuln_counts: Record<string, number>;
  created_at: string; updated_at: string;
}

interface RemediationForHost {
  remediation_id: string; remediation_action: string | null;
  cve_id: string | null; severity: string; affected_product: string | null;
  exploit_available: boolean; cisa_kev: boolean; exploit_status: string | null;
}

export default function AssetDetailPage() {
  const params = useParams();
  const router = useRouter();
  const assetId = params.id as string;

  const [asset, setAsset] = useState<AssetDetail | null>(null);
  const [remediations, setRemediations] = useState<RemediationForHost[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [a, r] = await Promise.all([
        api<AssetDetail>(`/api/v1/assets/${assetId}`),
        api<RemediationForHost[]>(`/api/v1/vulnerabilities/hosts/${assetId}/remediations`),
      ]);
      setAsset(a);
      setRemediations(r);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [assetId]);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div className="flex justify-center py-20"><Loader2 className="h-8 w-8 animate-spin text-indigo-500" /></div>;
  if (!asset) return <div className="py-20 text-center text-gray-500">Asset not found</div>;

  const riskColor = (asset.risk_score ?? 0) >= 80 ? "text-red-400" :
                    (asset.risk_score ?? 0) >= 50 ? "text-orange-400" :
                    (asset.risk_score ?? 0) >= 20 ? "text-yellow-400" : "text-emerald-400";

  const totalVulns = Object.values(asset.vuln_counts || {}).reduce((a, b) => a + b, 0);

  return (
    <div className="space-y-6">
      <button onClick={() => router.push("/dashboard/assets")}
        className="flex items-center gap-1 text-sm text-indigo-400 hover:text-indigo-300">
        <ArrowLeft className="h-4 w-4" />Back to assets
      </button>

      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-4">
          <div className="rounded-xl bg-gray-800 p-3">
            <Server className="h-6 w-6 text-emerald-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">{asset.hostname || "Unknown"}</h1>
            <p className="text-sm text-gray-400">
              {asset.os_name} {asset.os_version} · {asset.asset_type || "Unknown type"}
              {asset.ip_addresses?.length > 0 && ` · ${asset.ip_addresses[0]}`}
            </p>
          </div>
        </div>
        <div className="text-right">
          <div className={cn("text-3xl font-bold", riskColor)}>{asset.risk_score ?? "—"}</div>
          <div className="text-xs text-gray-400">Risk Score</div>
        </div>
      </div>

      {/* Info cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
          <div className="text-xs text-gray-400">Scanners</div>
          <div className="mt-2 flex gap-1.5 flex-wrap">
            {(asset.seen_by_sources || []).map((s) => <SourceBadge key={s} source={s} />)}
          </div>
        </div>
        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
          <div className="text-xs text-gray-400">Total Open Vulns</div>
          <div className="mt-1 text-2xl font-bold text-white">{totalVulns}</div>
        </div>
        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
          <div className="text-xs text-gray-400">By Severity</div>
          <div className="mt-2 flex gap-2 flex-wrap">
            {Object.entries(asset.vuln_counts || {}).sort((a, b) => {
              const order: Record<string, number> = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };
              return (order[a[0]] ?? 4) - (order[b[0]] ?? 4);
            }).map(([sev, cnt]) => (
              <div key={sev} className="flex items-center gap-1">
                <SeverityBadge severity={sev} /><span className="text-xs text-white">{cnt}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
          <div className="text-xs text-gray-400">Remediations Needed</div>
          <div className="mt-1 text-2xl font-bold text-white">{remediations.length}</div>
        </div>
      </div>

      {/* Remediations table */}
      <div>
        <h2 className="mb-3 text-sm font-medium text-gray-400">Remediations Needed</h2>
        <div className="overflow-hidden rounded-xl border border-gray-800">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-gray-800 bg-gray-900/70">
              <th className="px-3 py-3 text-left font-medium text-gray-400">CVE</th>
              <th className="px-3 py-3 text-left font-medium text-gray-400">Severity</th>
              <th className="px-3 py-3 text-left font-medium text-gray-400">Product</th>
              <th className="px-3 py-3 text-left font-medium text-gray-400">Remediation</th>
              <th className="px-3 py-3 text-left font-medium text-gray-400">Exploit</th>
              <th className="px-3 py-3 text-left font-medium text-gray-400">KEV</th>
            </tr></thead>
            <tbody className="divide-y divide-gray-800/50">
              {remediations.map((r, i) => (
                <tr key={i} className="hover:bg-gray-800/30">
                  <td className="px-3 py-2.5 font-mono text-xs text-gray-300">{r.cve_id}</td>
                  <td className="px-3 py-2.5"><SeverityBadge severity={r.severity} /></td>
                  <td className="px-3 py-2.5 text-xs text-gray-400 max-w-[150px] truncate">{r.affected_product}</td>
                  <td className="px-3 py-2.5 text-xs text-gray-300 max-w-[300px] truncate">{r.remediation_action || "—"}</td>
                  <td className="px-3 py-2.5">
                    {r.exploit_available ? (
                      <span className="flex items-center gap-1 text-xs text-orange-400"><Flame className="h-3 w-3" />{r.exploit_status || "Yes"}</span>
                    ) : <span className="text-gray-600 text-xs">—</span>}
                  </td>
                  <td className="px-3 py-2.5">
                    {r.cisa_kev ? <span className="text-red-400 text-xs font-medium">🛡️ KEV</span> : <span className="text-gray-600">—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {remediations.length === 0 && <div className="py-12 text-center text-gray-500">No open remediations</div>}
        </div>
      </div>
    </div>
  );
}
FILEEOF

# ══════════════════════════════════════════════
#  RESTART + RECOMPUTE
# ══════════════════════════════════════════════

echo "🔄 Restarting..."
docker compose up -d --force-recreate backend frontend

echo "⏳ Waiting (20s)..."
sleep 20

echo "🔢 Recomputing risk scores..."
curl -s -X POST "http://localhost:8000/api/v1/assets/recompute-risk-scores" \
  -H "Authorization: Bearer dev-token" | python3 -m json.tool 2>/dev/null || echo "Recomputed"

echo ""
echo "🔍 Testing..."
echo "Asset stats:"
curl -s "http://localhost:8000/api/v1/assets/stats" -H "Authorization: Bearer dev-token" | python3 -m json.tool 2>/dev/null
echo ""

# ══════════════════════════════════════════════
#  COMMIT
# ══════════════════════════════════════════════

echo "📝 Committing..."
git add -A
git commit -m "feat: asset inventory page with risk scores + scanner coverage

Backend:
- Risk score computation: weighted by severity × exploit × KEV
- Asset stats: total, avg risk, OS breakdown, risk distribution, scanner coverage
- Enhanced asset list: per-asset critical/high/exploitable/KEV counts
- Recompute risk scores endpoint (Admin)
- Asset detail with vuln counts by severity

Frontend:
- Asset inventory page with stat cards (total, avg risk, scanner coverage, risk distribution)
- Filterable table: search, scanner source, risk score minimum
- Risk score color-coded bars (0-19 green, 20-49 yellow, 50-79 orange, 80+ red)
- Per-row: hostname, OS, scanners, risk, vulns, critical, high, exploitable, KEV
- Click row → asset detail page with all remediations needed
- Recompute Risk button"

git push -u origin feat/asset-inventory

gh pr create \
  --title "feat: asset inventory with risk scores + scanner coverage" \
  --body "## Asset Inventory

### Stats Dashboard
- Total assets, average risk score with color bar
- Scanner coverage breakdown (which tools see which assets)
- Risk distribution (Critical 80+, High 50+, Medium 20+, Low 0-19)

### Asset Table
- Per-asset columns: hostname, OS, scanners, risk score, vuln count, critical, high, exploitable, KEV
- Filters: text search, scanner source, risk score minimum
- Click row → detail page

### Asset Detail Page
- Risk score, scanner badges, severity breakdown
- All remediations needed for this host with exploit/KEV status

### Risk Score Formula
\`\`\`
raw = Σ(severity_weight × exploit_multiplier × kev_multiplier)
  CRITICAL=40, HIGH=20, MEDIUM=5, LOW=1
  × 2 if exploit available
  × 3 if CISA KEV
score = min(100, raw)
\`\`\`" \
  --base main

echo ""
echo "✅ Done!"
echo "   Assets: http://localhost:3000/dashboard/assets"
echo "   Click any asset → detail page with remediations"
echo ""
echo "   To merge: gh pr merge --squash && git checkout main && git pull"
