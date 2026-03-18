#!/bin/bash
set -euo pipefail

cd ~/Desktop/getvul

echo "🔍 Building vulnerability explorer..."

git checkout main
git pull
git checkout -b feat/vuln-explorer

# ══════════════════════════════════════════════
#  BACKEND: Seed data endpoint (dev only)
# ══════════════════════════════════════════════

cat > backend/app/seed.py << 'FILEEOF'
"""Seed database with sample data for development."""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.tenants.models import Tenant, User, UserRole, IdPProvider
from app.vulnerabilities.models import Vulnerability


SAMPLE_CVES = [
    ("CVE-2024-3094", "xz-utils", "5.6.0", "5.6.2", 10.0, "CRITICAL"),
    ("CVE-2024-21887", "Ivanti Connect Secure", "9.x", "9.1R18.3", 9.1, "CRITICAL"),
    ("CVE-2024-1709", "ConnectWise ScreenConnect", "23.9.7", "23.9.8", 10.0, "CRITICAL"),
    ("CVE-2023-44487", "HTTP/2 Rapid Reset", None, None, 7.5, "HIGH"),
    ("CVE-2024-0204", "GoAnywhere MFT", "7.4.0", "7.4.1", 9.8, "CRITICAL"),
    ("CVE-2023-46805", "Ivanti Policy Secure", "9.x", "22.6R1.2", 8.2, "HIGH"),
    ("CVE-2024-23917", "TeamCity", "2023.11.2", "2023.11.3", 9.8, "CRITICAL"),
    ("CVE-2024-27198", "TeamCity", "2023.11.3", "2023.11.4", 9.8, "CRITICAL"),
    ("CVE-2023-22527", "Confluence Server", "8.5.3", "8.5.4", 9.8, "CRITICAL"),
    ("CVE-2024-21762", "FortiOS", "7.4.2", "7.4.3", 9.6, "CRITICAL"),
    ("CVE-2023-4966", "Citrix NetScaler", "14.1-8.50", "14.1-12.35", 9.4, "CRITICAL"),
    ("CVE-2024-6387", "OpenSSH", "8.5p1", "9.8p1", 8.1, "HIGH"),
    ("CVE-2023-38545", "curl", "7.69.0", "8.4.0", 7.5, "HIGH"),
    ("CVE-2023-36884", "Microsoft Office", "2019", "patched", 7.5, "HIGH"),
    ("CVE-2024-28255", "OpenMetadata", "1.2.4", "1.3.1", 9.8, "CRITICAL"),
    ("CVE-2023-20198", "Cisco IOS XE", "16.x", "17.9.4a", 10.0, "CRITICAL"),
    ("CVE-2024-4577", "PHP CGI", "8.1.28", "8.1.29", 9.8, "CRITICAL"),
    ("CVE-2023-48788", "FortiClient EMS", "7.2.2", "7.2.3", 9.3, "CRITICAL"),
    ("CVE-2024-5806", "MOVEit Transfer", "2024.0.0", "2024.0.2", 9.1, "CRITICAL"),
    ("CVE-2023-34362", "MOVEit Transfer", "2023.0.1", "2023.0.2", 9.8, "CRITICAL"),
    ("CVE-2024-1234", "nginx", "1.25.0", "1.25.4", 6.5, "MEDIUM"),
    ("CVE-2024-2345", "PostgreSQL", "15.2", "15.6", 5.3, "MEDIUM"),
    ("CVE-2024-3456", "Redis", "7.0.0", "7.2.4", 4.3, "MEDIUM"),
    ("CVE-2024-4567", "Node.js", "20.0.0", "20.11.1", 3.1, "LOW"),
    ("CVE-2024-5678", "Python", "3.11.0", "3.11.8", 3.7, "LOW"),
    ("CVE-2024-6789", "OpenSSL", "3.0.0", "3.0.13", 5.9, "MEDIUM"),
    ("CVE-2024-7890", "Apache httpd", "2.4.58", "2.4.59", 4.0, "MEDIUM"),
    ("CVE-2024-8901", "Docker Engine", "24.0.0", "24.0.9", 6.1, "MEDIUM"),
    ("CVE-2024-9012", "Kubernetes", "1.28.0", "1.28.6", 2.5, "LOW"),
    ("CVE-2024-0123", "Git", "2.43.0", "2.43.2", 3.3, "LOW"),
]

HOSTNAMES = [
    "web-prod-01", "web-prod-02", "web-prod-03",
    "api-prod-01", "api-prod-02",
    "db-prod-01", "db-prod-02",
    "cache-prod-01",
    "worker-prod-01", "worker-prod-02",
    "ci-runner-01", "ci-runner-02",
    "monitoring-01",
    "bastion-01",
    "vpn-gateway-01",
    "mail-01",
    "dev-server-01", "dev-server-02",
    "staging-web-01", "staging-api-01",
]

SOURCES = ["CROWDSTRIKE", "NESSUS", "DEFENDER", "WIZ"]
STATUSES = ["OPEN", "OPEN", "OPEN", "OPEN", "IN_PROGRESS", "REMEDIATED", "SUPPRESSED"]
OS_OPTIONS = [
    ("Ubuntu", "22.04"), ("Ubuntu", "20.04"),
    ("Windows Server", "2022"), ("Windows Server", "2019"),
    ("Amazon Linux", "2023"), ("RHEL", "9.3"),
    ("Debian", "12"), ("CentOS", "8"),
]


async def seed_database(db: AsyncSession) -> dict:
    """Seed the database with sample vulnerability data."""

    # Check if already seeded
    result = await db.execute(select(Tenant).limit(1))
    if result.scalar_one_or_none() is not None:
        return {"message": "Database already seeded", "seeded": False}

    # Create tenant
    tenant = Tenant(
        name="Demo Organization",
        slug="demo",
        domain="demo.getvul.app",
        idp_provider=IdPProvider.GOOGLE,
        idp_tenant_id="demo",
    )
    db.add(tenant)
    await db.flush()

    # Create demo user
    user = User(
        tenant_id=tenant.id,
        email="admin@demo.getvul.app",
        display_name="Demo Admin",
        role=UserRole.OWNER,
        idp_subject="demo-subject-001",
    )
    db.add(user)
    await db.flush()

    # Create assets
    assets = []
    for hostname in HOSTNAMES:
        os_name, os_version = random.choice(OS_OPTIONS)
        asset = Asset(
            tenant_id=tenant.id,
            hostname=hostname,
            ip_addresses=[f"10.0.{random.randint(1,20)}.{random.randint(1,254)}"],
            os_name=os_name,
            os_version=os_version,
            asset_type=random.choice(["SERVER", "ENDPOINT", "VM"]),
            cloud_provider=random.choice(["AWS", "AZURE", None]),
            seen_by_sources=random.sample(SOURCES, k=random.randint(1, 3)),
            risk_score=random.randint(0, 100),
        )
        db.add(asset)
        assets.append(asset)
    await db.flush()

    # Create vulnerabilities
    vuln_count = 0
    now = datetime.now(timezone.utc)

    for _ in range(300):
        cve_data = random.choice(SAMPLE_CVES)
        cve_id, product, affected_ver, fixed_ver, cvss, severity = cve_data
        asset = random.choice(assets)
        source = random.choice(SOURCES)
        status = random.choice(STATUSES)
        days_ago = random.randint(1, 180)

        first_detected = now - timedelta(days=days_ago)
        last_seen = now - timedelta(days=random.randint(0, min(3, days_ago)))
        remediated = (now - timedelta(days=random.randint(0, days_ago // 2))) if status == "REMEDIATED" else None

        vuln = Vulnerability(
            tenant_id=tenant.id,
            cve_id=cve_id,
            vulnerability_name=f"{product} vulnerability",
            cvss_v3_score=cvss,
            severity=severity,
            exploit_available=random.random() < 0.3,
            cisa_kev=random.random() < 0.15,
            asset_id=asset.id,
            source=source,
            source_vuln_id=f"{source}-{uuid.uuid4().hex[:8]}",
            affected_product=product,
            affected_version=affected_ver,
            fixed_version=fixed_ver,
            status=status,
            first_detected_at=first_detected,
            last_seen_at=last_seen,
            remediated_at=remediated,
        )
        try:
            db.add(vuln)
            await db.flush()
            vuln_count += 1
        except Exception:
            await db.rollback()
            continue

    return {
        "message": "Database seeded",
        "seeded": True,
        "tenant_id": str(tenant.id),
        "user_id": str(user.id),
        "user_email": user.email,
        "assets_created": len(assets),
        "vulnerabilities_created": vuln_count,
    }
FILEEOF

# Add seed endpoint + dev token bypass to main.py
cat > backend/app/main.py << 'FILEEOF'
"""GetVul API — entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.vulnerabilities.router import router as vuln_router
from app.assets.router import router as asset_router
from app.tenants.router import router as tenant_router
from app.connectors.router import router as connector_router
from app.config import settings

app = FastAPI(
    title="GetVul API",
    description="Unified Vulnerability Aggregation Platform",
    version="0.1.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"] if settings.debug else ["https://*.getvul.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(vuln_router, prefix="/api/v1/vulnerabilities", tags=["Vulnerabilities"])
app.include_router(asset_router, prefix="/api/v1/assets", tags=["Assets"])
app.include_router(tenant_router, prefix="/api/v1/tenant", tags=["Tenant & Users"])
app.include_router(connector_router, prefix="/api/v1/connectors", tags=["Connectors"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "getvul-api"}


# ── Dev-only endpoints ──
if settings.environment == "development":
    from app.db.session import get_db
    from app.seed import seed_database
    from fastapi import Depends
    from sqlalchemy.ext.asyncio import AsyncSession

    @app.post("/dev/seed", tags=["Dev"])
    async def seed(db: AsyncSession = Depends(get_db)):
        """Seed the database with sample data. Dev only."""
        return await seed_database(db)
FILEEOF

# Add dev token bypass to auth dependencies (for frontend dev without SSO)
cat > backend/app/auth/dependencies.py << 'FILEEOF'
"""FastAPI dependencies for authentication."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import decode_token
from app.auth.schemas import CurrentUser
from app.config import settings
from app.db.session import get_db

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CurrentUser:
    """Extract and validate the current user from the JWT bearer token."""

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # Dev mode: accept "dev-token" and return the first owner user
    if settings.environment == "development" and token == "dev-token":
        from app.tenants.models import User
        result = await db.execute(
            select(User).where(User.role == "OWNER", User.is_active.is_(True)).limit(1)
        )
        user = result.scalar_one_or_none()
        if user:
            return CurrentUser(
                id=user.id,
                tenant_id=user.tenant_id,
                email=user.email,
                role=user.role.value if hasattr(user.role, "value") else user.role,
            )
        raise HTTPException(status_code=401, detail="No dev user found. Run POST /dev/seed first.")

    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.token_type != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    return CurrentUser(
        id=uuid.UUID(payload.sub),
        tenant_id=uuid.UUID(payload.tenant_id),
        email=payload.email,
        role=payload.role,
    )
FILEEOF

# ══════════════════════════════════════════════
#  FRONTEND: API client with dev token
# ══════════════════════════════════════════════

cat > frontend/src/lib/api.ts << 'FILEEOF'
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Dev token for local development (bypasses SSO)
const DEV_TOKEN = "dev-token";

interface FetchOptions extends RequestInit {
  token?: string;
}

export async function api<T = any>(
  path: string,
  options: FetchOptions = {}
): Promise<T> {
  const { token, headers: customHeaders, ...rest } = options;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token || DEV_TOKEN}`,
    ...(customHeaders as Record<string, string>),
  };

  const res = await fetch(`${API_URL}${path}`, {
    headers,
    ...rest,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `API error: ${res.status}`);
  }

  return res.json();
}

export { API_URL, DEV_TOKEN };
FILEEOF

# ══════════════════════════════════════════════
#  FRONTEND: Shared UI components
# ══════════════════════════════════════════════

cat > frontend/src/components/ui/Badge.tsx << 'FILEEOF'
import { cn } from "@/lib/utils";

const severityStyles: Record<string, string> = {
  CRITICAL: "bg-red-500/20 text-red-400 border-red-500/30",
  HIGH: "bg-orange-500/20 text-orange-400 border-orange-500/30",
  MEDIUM: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  LOW: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  INFO: "bg-gray-500/20 text-gray-400 border-gray-500/30",
};

const statusStyles: Record<string, string> = {
  OPEN: "bg-red-500/15 text-red-400 border-red-500/20",
  IN_PROGRESS: "bg-yellow-500/15 text-yellow-400 border-yellow-500/20",
  REMEDIATED: "bg-emerald-500/15 text-emerald-400 border-emerald-500/20",
  SUPPRESSED: "bg-gray-500/15 text-gray-400 border-gray-500/20",
  FALSE_POSITIVE: "bg-gray-500/15 text-gray-500 border-gray-500/20",
};

const sourceStyles: Record<string, string> = {
  CROWDSTRIKE: "bg-red-500/10 text-red-300 border-red-500/20",
  NESSUS: "bg-green-500/10 text-green-300 border-green-500/20",
  DEFENDER: "bg-blue-500/10 text-blue-300 border-blue-500/20",
  WIZ: "bg-purple-500/10 text-purple-300 border-purple-500/20",
};

export function SeverityBadge({ severity }: { severity: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium",
        severityStyles[severity] || "bg-gray-700 text-gray-300 border-gray-600"
      )}
    >
      {severity}
    </span>
  );
}

export function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium",
        statusStyles[status] || "bg-gray-700 text-gray-300 border-gray-600"
      )}
    >
      {status.replace("_", " ")}
    </span>
  );
}

export function SourceBadge({ source }: { source: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-1.5 py-0.5 text-[10px] font-medium",
        sourceStyles[source] || "bg-gray-700 text-gray-300 border-gray-600"
      )}
    >
      {source === "CROWDSTRIKE" ? "CS" : source === "DEFENDER" ? "MDE" : source}
    </span>
  );
}
FILEEOF

cat > frontend/src/components/ui/Pagination.tsx << 'FILEEOF'
"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

interface PaginationProps {
  page: number;
  totalPages: number;
  total: number;
  pageSize: number;
  onPageChange: (page: number) => void;
}

export default function Pagination({
  page,
  totalPages,
  total,
  pageSize,
  onPageChange,
}: PaginationProps) {
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);

  return (
    <div className="flex items-center justify-between border-t border-gray-800 px-1 pt-4">
      <span className="text-sm text-gray-400">
        {total > 0 ? `${start}–${end} of ${total.toLocaleString()}` : "No results"}
      </span>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          className={cn(
            "rounded-lg p-1.5 transition-colors",
            page <= 1
              ? "text-gray-600 cursor-not-allowed"
              : "text-gray-400 hover:bg-gray-800 hover:text-white"
          )}
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
          let pageNum: number;
          if (totalPages <= 5) {
            pageNum = i + 1;
          } else if (page <= 3) {
            pageNum = i + 1;
          } else if (page >= totalPages - 2) {
            pageNum = totalPages - 4 + i;
          } else {
            pageNum = page - 2 + i;
          }
          return (
            <button
              key={pageNum}
              onClick={() => onPageChange(pageNum)}
              className={cn(
                "min-w-[32px] rounded-lg px-2.5 py-1 text-sm font-medium transition-colors",
                pageNum === page
                  ? "bg-indigo-600 text-white"
                  : "text-gray-400 hover:bg-gray-800 hover:text-white"
              )}
            >
              {pageNum}
            </button>
          );
        })}
        <button
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
          className={cn(
            "rounded-lg p-1.5 transition-colors",
            page >= totalPages
              ? "text-gray-600 cursor-not-allowed"
              : "text-gray-400 hover:bg-gray-800 hover:text-white"
          )}
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
FILEEOF

# ══════════════════════════════════════════════
#  FRONTEND: Vulnerability Filters component
# ══════════════════════════════════════════════

cat > frontend/src/components/vulnerabilities/VulnFilters.tsx << 'FILEEOF'
"use client";

import { Search, X, Filter } from "lucide-react";
import { cn } from "@/lib/utils";

export interface VulnFilterState {
  search: string;
  severity: string[];
  source: string[];
  status: string[];
  exploit_available: boolean | null;
  cisa_kev: boolean | null;
}

const SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];
const SOURCES = ["CROWDSTRIKE", "NESSUS", "DEFENDER", "WIZ"];
const STATUSES = ["OPEN", "IN_PROGRESS", "REMEDIATED", "SUPPRESSED", "FALSE_POSITIVE"];

const sevColors: Record<string, string> = {
  CRITICAL: "border-red-500/40 bg-red-500/10 text-red-400 data-[active=true]:bg-red-500/25",
  HIGH: "border-orange-500/40 bg-orange-500/10 text-orange-400 data-[active=true]:bg-orange-500/25",
  MEDIUM: "border-yellow-500/40 bg-yellow-500/10 text-yellow-400 data-[active=true]:bg-yellow-500/25",
  LOW: "border-blue-500/40 bg-blue-500/10 text-blue-400 data-[active=true]:bg-blue-500/25",
};

interface Props {
  filters: VulnFilterState;
  onChange: (filters: VulnFilterState) => void;
}

export default function VulnFilters({ filters, onChange }: Props) {
  const toggleArray = (arr: string[], value: string) =>
    arr.includes(value) ? arr.filter((v) => v !== value) : [...arr, value];

  const activeCount =
    filters.severity.length +
    filters.source.length +
    filters.status.length +
    (filters.exploit_available !== null ? 1 : 0) +
    (filters.cisa_kev !== null ? 1 : 0);

  return (
    <div className="space-y-4">
      {/* Search bar */}
      <div className="relative">
        <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-500" />
        <input
          type="text"
          value={filters.search}
          onChange={(e) => onChange({ ...filters, search: e.target.value })}
          placeholder="Search CVE ID, product name..."
          className="w-full rounded-lg border border-gray-700 bg-gray-900 py-2 pl-10 pr-4 text-sm text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        />
        {filters.search && (
          <button
            onClick={() => onChange({ ...filters, search: "" })}
            className="absolute right-3 top-2.5 text-gray-500 hover:text-gray-300"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Filter pills */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1.5 text-xs text-gray-500">
          <Filter className="h-3.5 w-3.5" />
          Filters{activeCount > 0 && ` (${activeCount})`}
        </div>

        {/* Severity */}
        <div className="flex gap-1.5">
          {SEVERITIES.map((sev) => (
            <button
              key={sev}
              data-active={filters.severity.includes(sev)}
              onClick={() =>
                onChange({ ...filters, severity: toggleArray(filters.severity, sev) })
              }
              className={cn(
                "rounded-md border px-2 py-0.5 text-xs font-medium transition-all",
                filters.severity.includes(sev)
                  ? sevColors[sev]
                  : "border-gray-700 bg-gray-900 text-gray-500 hover:text-gray-300"
              )}
            >
              {sev}
            </button>
          ))}
        </div>

        <div className="h-4 w-px bg-gray-700" />

        {/* Source */}
        <div className="flex gap-1.5">
          {SOURCES.map((src) => (
            <button
              key={src}
              onClick={() =>
                onChange({ ...filters, source: toggleArray(filters.source, src) })
              }
              className={cn(
                "rounded-md border px-2 py-0.5 text-xs font-medium transition-all",
                filters.source.includes(src)
                  ? "border-indigo-500/40 bg-indigo-500/15 text-indigo-400"
                  : "border-gray-700 bg-gray-900 text-gray-500 hover:text-gray-300"
              )}
            >
              {src === "CROWDSTRIKE" ? "CS" : src === "DEFENDER" ? "MDE" : src}
            </button>
          ))}
        </div>

        <div className="h-4 w-px bg-gray-700" />

        {/* Status */}
        <div className="flex gap-1.5">
          {STATUSES.map((st) => (
            <button
              key={st}
              onClick={() =>
                onChange({ ...filters, status: toggleArray(filters.status, st) })
              }
              className={cn(
                "rounded-md border px-2 py-0.5 text-xs font-medium transition-all",
                filters.status.includes(st)
                  ? "border-emerald-500/40 bg-emerald-500/15 text-emerald-400"
                  : "border-gray-700 bg-gray-900 text-gray-500 hover:text-gray-300"
              )}
            >
              {st.replace("_", " ")}
            </button>
          ))}
        </div>

        <div className="h-4 w-px bg-gray-700" />

        {/* Toggles */}
        <button
          onClick={() =>
            onChange({
              ...filters,
              exploit_available: filters.exploit_available === true ? null : true,
            })
          }
          className={cn(
            "rounded-md border px-2 py-0.5 text-xs font-medium transition-all",
            filters.exploit_available === true
              ? "border-red-500/40 bg-red-500/15 text-red-400"
              : "border-gray-700 bg-gray-900 text-gray-500 hover:text-gray-300"
          )}
        >
          🔥 Exploitable
        </button>

        <button
          onClick={() =>
            onChange({
              ...filters,
              cisa_kev: filters.cisa_kev === true ? null : true,
            })
          }
          className={cn(
            "rounded-md border px-2 py-0.5 text-xs font-medium transition-all",
            filters.cisa_kev === true
              ? "border-red-500/40 bg-red-500/15 text-red-400"
              : "border-gray-700 bg-gray-900 text-gray-500 hover:text-gray-300"
          )}
        >
          🛡️ CISA KEV
        </button>

        {/* Clear all */}
        {activeCount > 0 && (
          <button
            onClick={() =>
              onChange({
                search: filters.search,
                severity: [],
                source: [],
                status: [],
                exploit_available: null,
                cisa_kev: null,
              })
            }
            className="text-xs text-gray-500 hover:text-gray-300"
          >
            Clear filters
          </button>
        )}
      </div>
    </div>
  );
}
FILEEOF

# ══════════════════════════════════════════════
#  FRONTEND: Vulnerability Table component
# ══════════════════════════════════════════════

cat > frontend/src/components/vulnerabilities/VulnTable.tsx << 'FILEEOF'
"use client";

import { useState } from "react";
import { ExternalLink, Flame, ShieldAlert, ChevronDown } from "lucide-react";
import { SeverityBadge, StatusBadge, SourceBadge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";
import type { VulnerabilitySummary } from "@/types/vulnerability";

interface Props {
  vulnerabilities: VulnerabilitySummary[];
  selectedIds: Set<string>;
  onSelectToggle: (id: string) => void;
  onSelectAll: (ids: string[]) => void;
}

export default function VulnTable({
  vulnerabilities,
  selectedIds,
  onSelectToggle,
  onSelectAll,
}: Props) {
  const allSelected =
    vulnerabilities.length > 0 &&
    vulnerabilities.every((v) => selectedIds.has(v.id));

  return (
    <div className="overflow-hidden rounded-xl border border-gray-800">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-800 bg-gray-900/70">
            <th className="w-10 px-3 py-3">
              <input
                type="checkbox"
                checked={allSelected}
                onChange={() => {
                  if (allSelected) {
                    onSelectAll([]);
                  } else {
                    onSelectAll(vulnerabilities.map((v) => v.id));
                  }
                }}
                className="rounded border-gray-600 bg-gray-800 text-indigo-600 focus:ring-indigo-500 focus:ring-offset-0"
              />
            </th>
            <th className="px-3 py-3 text-left font-medium text-gray-400">CVE / Name</th>
            <th className="px-3 py-3 text-left font-medium text-gray-400">Severity</th>
            <th className="px-3 py-3 text-left font-medium text-gray-400">Source</th>
            <th className="px-3 py-3 text-left font-medium text-gray-400">Status</th>
            <th className="px-3 py-3 text-left font-medium text-gray-400">Asset</th>
            <th className="px-3 py-3 text-left font-medium text-gray-400">Product</th>
            <th className="w-10 px-3 py-3 text-left font-medium text-gray-400"></th>
            <th className="px-3 py-3 text-left font-medium text-gray-400">Detected</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-800/50">
          {vulnerabilities.map((vuln) => (
            <tr
              key={vuln.id}
              className={cn(
                "transition-colors hover:bg-gray-800/30",
                selectedIds.has(vuln.id) && "bg-indigo-500/5"
              )}
            >
              <td className="px-3 py-2.5">
                <input
                  type="checkbox"
                  checked={selectedIds.has(vuln.id)}
                  onChange={() => onSelectToggle(vuln.id)}
                  className="rounded border-gray-600 bg-gray-800 text-indigo-600 focus:ring-indigo-500 focus:ring-offset-0"
                />
              </td>
              <td className="px-3 py-2.5">
                <span className="font-mono text-sm text-white">
                  {vuln.cve_id || "N/A"}
                </span>
              </td>
              <td className="px-3 py-2.5">
                <SeverityBadge severity={vuln.severity} />
              </td>
              <td className="px-3 py-2.5">
                <SourceBadge source={vuln.source} />
              </td>
              <td className="px-3 py-2.5">
                <StatusBadge status={vuln.status} />
              </td>
              <td className="px-3 py-2.5">
                <span className="text-gray-300">
                  {vuln.asset_hostname || "—"}
                </span>
              </td>
              <td className="max-w-[180px] truncate px-3 py-2.5 text-gray-400">
                {vuln.affected_product || "—"}
              </td>
              <td className="px-3 py-2.5">
                <div className="flex items-center gap-1">
                  {vuln.exploit_available && (
                    <Flame className="h-3.5 w-3.5 text-red-400" title="Exploit available" />
                  )}
                  {vuln.cisa_kev && (
                    <ShieldAlert className="h-3.5 w-3.5 text-orange-400" title="CISA KEV" />
                  )}
                </div>
              </td>
              <td className="px-3 py-2.5 text-gray-500">
                {new Date(vuln.first_detected_at).toLocaleDateString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {vulnerabilities.length === 0 && (
        <div className="py-12 text-center text-gray-500">
          No vulnerabilities match your filters
        </div>
      )}
    </div>
  );
}
FILEEOF

# ══════════════════════════════════════════════
#  FRONTEND: Bulk Actions bar
# ══════════════════════════════════════════════

cat > frontend/src/components/vulnerabilities/BulkActions.tsx << 'FILEEOF'
"use client";

import { useState } from "react";
import { CheckCircle2, XCircle, AlertTriangle, Loader2 } from "lucide-react";
import { api } from "@/lib/api";

interface Props {
  selectedCount: number;
  selectedIds: string[];
  onComplete: () => void;
}

const ACTIONS = [
  { status: "IN_PROGRESS", label: "Mark In Progress", icon: AlertTriangle, color: "text-yellow-400" },
  { status: "REMEDIATED", label: "Mark Remediated", icon: CheckCircle2, color: "text-emerald-400" },
  { status: "SUPPRESSED", label: "Suppress", icon: XCircle, color: "text-gray-400" },
  { status: "FALSE_POSITIVE", label: "False Positive", icon: XCircle, color: "text-gray-500" },
];

export default function BulkActions({ selectedCount, selectedIds, onComplete }: Props) {
  const [loading, setLoading] = useState(false);

  async function handleAction(status: string) {
    setLoading(true);
    try {
      await api("/api/v1/vulnerabilities/bulk-status", {
        method: "POST",
        body: JSON.stringify({
          vulnerability_ids: selectedIds,
          status,
        }),
      });
      onComplete();
    } catch (e) {
      console.error("Bulk action failed:", e);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex items-center gap-3 rounded-xl border border-indigo-500/30 bg-indigo-500/10 px-4 py-2.5">
      <span className="text-sm font-medium text-indigo-400">
        {selectedCount} selected
      </span>
      <div className="h-4 w-px bg-indigo-500/30" />
      {ACTIONS.map((action) => (
        <button
          key={action.status}
          onClick={() => handleAction(action.status)}
          disabled={loading}
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-gray-300 transition-colors hover:bg-gray-800"
        >
          {loading ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <action.icon className={`h-3.5 w-3.5 ${action.color}`} />
          )}
          {action.label}
        </button>
      ))}
    </div>
  );
}
FILEEOF

# ══════════════════════════════════════════════
#  FRONTEND: Vulnerabilities page (full explorer)
# ══════════════════════════════════════════════

cat > frontend/src/app/dashboard/vulnerabilities/page.tsx << 'FILEEOF'
"use client";

import { useCallback, useEffect, useState } from "react";
import { Bug, Download, RefreshCw, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import VulnFilters, {
  type VulnFilterState,
} from "@/components/vulnerabilities/VulnFilters";
import VulnTable from "@/components/vulnerabilities/VulnTable";
import BulkActions from "@/components/vulnerabilities/BulkActions";
import Pagination from "@/components/ui/Pagination";
import type { VulnerabilitySummary } from "@/types/vulnerability";

interface PaginatedVulns {
  items: VulnerabilitySummary[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

const DEFAULT_FILTERS: VulnFilterState = {
  search: "",
  severity: [],
  source: [],
  status: [],
  exploit_available: null,
  cisa_kev: null,
};

export default function VulnerabilitiesPage() {
  const [data, setData] = useState<PaginatedVulns | null>(null);
  const [filters, setFilters] = useState<VulnFilterState>(DEFAULT_FILTERS);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(25);
  const [loading, setLoading] = useState(true);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("page", String(page));
      params.set("page_size", String(pageSize));

      if (filters.search) params.set("search", filters.search);
      filters.severity.forEach((s) => params.append("severity", s));
      filters.source.forEach((s) => params.append("source", s));
      filters.status.forEach((s) => params.append("status", s));
      if (filters.exploit_available !== null)
        params.set("exploit_available", String(filters.exploit_available));
      if (filters.cisa_kev !== null)
        params.set("cisa_kev", String(filters.cisa_kev));

      const result = await api<PaginatedVulns>(
        `/api/v1/vulnerabilities?${params.toString()}`
      );
      setData(result);
    } catch (e) {
      console.error("Failed to fetch vulnerabilities:", e);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, filters]);

  useEffect(() => {
    const debounce = setTimeout(fetchData, 300);
    return () => clearTimeout(debounce);
  }, [fetchData]);

  // Reset page when filters change
  useEffect(() => {
    setPage(1);
    setSelectedIds(new Set());
  }, [filters]);

  function handleSelectToggle(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function handleSelectAll(ids: string[]) {
    if (ids.length === 0) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(ids));
    }
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Bug className="h-6 w-6 text-indigo-400" />
          <div>
            <h1 className="text-2xl font-bold text-white">Vulnerabilities</h1>
            {data && (
              <p className="text-sm text-gray-400">
                {data.total.toLocaleString()} total vulnerabilities
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchData}
            disabled={loading}
            className="flex items-center gap-2 rounded-lg border border-gray-700 px-3 py-2 text-sm text-gray-300 transition-colors hover:bg-gray-800"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Filters */}
      <VulnFilters filters={filters} onChange={setFilters} />

      {/* Bulk actions */}
      {selectedIds.size > 0 && (
        <BulkActions
          selectedCount={selectedIds.size}
          selectedIds={Array.from(selectedIds)}
          onComplete={() => {
            setSelectedIds(new Set());
            fetchData();
          }}
        />
      )}

      {/* Table */}
      {loading && !data ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
        </div>
      ) : (
        <>
          <VulnTable
            vulnerabilities={data?.items || []}
            selectedIds={selectedIds}
            onSelectToggle={handleSelectToggle}
            onSelectAll={handleSelectAll}
          />

          {data && data.total_pages > 1 && (
            <Pagination
              page={data.page}
              totalPages={data.total_pages}
              total={data.total}
              pageSize={data.page_size}
              onPageChange={setPage}
            />
          )}
        </>
      )}
    </div>
  );
}
FILEEOF

# ══════════════════════════════════════════════
#  FRONTEND: Update dashboard overview to use API
# ══════════════════════════════════════════════

cat > frontend/src/app/dashboard/page.tsx << 'FILEEOF'
"use client";

import { useEffect, useState } from "react";
import {
  Bug,
  AlertTriangle,
  ShieldAlert,
  Flame,
  Link2,
  Clock,
  Loader2,
} from "lucide-react";
import { api } from "@/lib/api";
import type { DashboardStats } from "@/types/vulnerability";

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);

  useEffect(() => {
    loadStats();
  }, []);

  async function loadStats() {
    try {
      const data = await api<DashboardStats>("/api/v1/vulnerabilities/stats");
      setStats(data);
    } catch (e) {
      console.error("Failed to load stats:", e);
    } finally {
      setLoading(false);
    }
  }

  async function handleSeed() {
    setSeeding(true);
    try {
      await api("/dev/seed", { method: "POST" });
      await loadStats();
    } catch (e) {
      console.error("Seed failed:", e);
    } finally {
      setSeeding(false);
    }
  }

  const severityColors: Record<string, string> = {
    CRITICAL: "bg-red-500/20 text-red-400 border-red-500/30",
    HIGH: "bg-orange-500/20 text-orange-400 border-orange-500/30",
    MEDIUM: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
    LOW: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
      </div>
    );
  }

  // Show seed button if no data
  if (!stats || stats.total_vulnerabilities === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <Bug className="h-12 w-12 text-gray-600" />
        <h2 className="mt-4 text-lg font-medium text-white">No vulnerability data yet</h2>
        <p className="mt-2 text-sm text-gray-400">
          Seed the database with sample data to explore the dashboard
        </p>
        <button
          onClick={handleSeed}
          disabled={seeding}
          className="mt-6 flex items-center gap-2 rounded-lg bg-indigo-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
        >
          {seeding && <Loader2 className="h-4 w-4 animate-spin" />}
          {seeding ? "Seeding..." : "Seed Sample Data"}
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Dashboard</h1>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={<Bug className="h-5 w-5 text-indigo-400" />}
          label="Total Vulnerabilities"
          value={stats.total_vulnerabilities.toLocaleString()}
        />
        <StatCard
          icon={<AlertTriangle className="h-5 w-5 text-orange-400" />}
          label="Open"
          value={stats.open_vulnerabilities.toLocaleString()}
        />
        <StatCard
          icon={<Flame className="h-5 w-5 text-red-400" />}
          label="Exploitable"
          value={stats.exploitable_count.toLocaleString()}
        />
        <StatCard
          icon={<ShieldAlert className="h-5 w-5 text-red-400" />}
          label="CISA KEV"
          value={stats.cisa_kev_count.toLocaleString()}
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
          <h2 className="mb-4 text-sm font-medium text-gray-400">By Severity</h2>
          <div className="space-y-3">
            {stats.by_severity.map((s) => (
              <div key={s.severity} className="flex items-center justify-between">
                <span
                  className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${
                    severityColors[s.severity] || "bg-gray-700 text-gray-300"
                  }`}
                >
                  {s.severity}
                </span>
                <div className="flex items-center gap-3">
                  <div className="h-2 w-32 overflow-hidden rounded-full bg-gray-800">
                    <div
                      className="h-full rounded-full bg-indigo-500"
                      style={{
                        width: `${Math.max(2, (s.count / stats.total_vulnerabilities) * 100)}%`,
                      }}
                    />
                  </div>
                  <span className="w-16 text-right text-sm font-medium text-white">
                    {s.count.toLocaleString()}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
          <h2 className="mb-4 text-sm font-medium text-gray-400">By Source</h2>
          <div className="space-y-3">
            {stats.by_source.map((s) => (
              <div key={s.source} className="flex items-center justify-between">
                <span className="text-sm text-gray-300">{s.source}</span>
                <div className="flex items-center gap-3">
                  <div className="h-2 w-32 overflow-hidden rounded-full bg-gray-800">
                    <div
                      className="h-full rounded-full bg-emerald-500"
                      style={{
                        width: `${Math.max(2, (s.count / stats.total_vulnerabilities) * 100)}%`,
                      }}
                    />
                  </div>
                  <span className="w-16 text-right text-sm font-medium text-white">
                    {s.count.toLocaleString()}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <StatCard
          icon={<Link2 className="h-5 w-5 text-emerald-400" />}
          label="Correlated CVEs (2+ sources)"
          value={stats.correlated_cves.toLocaleString()}
        />
        <StatCard
          icon={<Clock className="h-5 w-5 text-blue-400" />}
          label="Mean Time to Remediate"
          value={stats.mttr_days ? `${stats.mttr_days} days` : "N/A"}
        />
      </div>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-5">
      <div className="flex items-center gap-3">
        {icon}
        <span className="text-sm text-gray-400">{label}</span>
      </div>
      <p className="mt-3 text-2xl font-bold text-white">{value}</p>
    </div>
  );
}
FILEEOF

# ══════════════════════════════════════════════
#  REBUILD & TEST
# ══════════════════════════════════════════════

echo "🔄 Rebuilding..."
docker compose down
docker compose build --no-cache
docker compose up -d

echo "⏳ Waiting for services (35s)..."
sleep 35

echo "🔍 Seeding sample data..."
curl -s -X POST http://localhost:8000/dev/seed | python3 -m json.tool 2>/dev/null || curl -s -X POST http://localhost:8000/dev/seed

echo ""
echo "🔍 Testing vulnerability list..."
curl -s "http://localhost:8000/api/v1/vulnerabilities?page_size=3" -H "Authorization: Bearer dev-token" | head -c 500

echo ""
echo ""

# ══════════════════════════════════════════════
#  COMMIT & PUSH
# ══════════════════════════════════════════════

echo "📝 Committing..."

git add -A
git commit -m "feat: vulnerability explorer + sample data + dev auth

Frontend:
- Vulnerability explorer with filterable table
- Filter by severity, source, status, exploit, CISA KEV
- Text search across CVE ID, product name
- Bulk actions: mark in progress, remediated, suppress, false positive
- Pagination with page navigation
- Severity/Status/Source badge components
- Dashboard now loads live data from API
- Seed button when database is empty

Backend:
- Dev token auth bypass (dev-token) for frontend development
- Sample data seeder: 20 assets, 300 vulnerabilities with real CVEs
- POST /dev/seed endpoint (dev environment only)"

git push -u origin feat/vuln-explorer

gh pr create \
  --title "feat: vulnerability explorer + sample data seeder" \
  --body "## Vulnerability Explorer

Full vulnerability explorer page with:
- **Filterable table** — severity, source, status, exploitable, CISA KEV
- **Text search** — CVE ID, product name
- **Bulk actions** — mark in progress, remediated, suppress, false positive
- **Pagination** — 25 per page with navigation
- **Badge components** — severity, status, source with color coding
- **Live API data** — dashboard overview + vuln list from backend

## Dev Tooling
- \`dev-token\` auth bypass for frontend dev without SSO
- Sample data seeder with 20 assets + 300 vulns (real CVEs)
- \`POST /dev/seed\` endpoint (dev only)

## How to Test
\`\`\`bash
make dev
# Open http://localhost:3000/dashboard
# Click 'Seed Sample Data' button
# Navigate to Vulnerabilities page
# Try the filters!
\`\`\`" \
  --base main

echo ""
echo "✅ Done! PR created."
echo ""
echo "   Dashboard: http://localhost:3000/dashboard"
echo "   Vuln Explorer: http://localhost:3000/dashboard/vulnerabilities"
echo ""
echo "   1. Open the dashboard"
echo "   2. Click 'Seed Sample Data' to populate"
echo "   3. Go to Vulnerabilities — filter, search, bulk actions"
echo ""
echo "   To merge: gh pr merge --squash && git checkout main && git pull"
