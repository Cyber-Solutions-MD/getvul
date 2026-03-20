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
from app.users.router import router as users_router
from app.ticketing.router import router as tickets_router
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Start background sync scheduler
    if settings.environment in ("development", "production"):
        from app.connectors.scheduler import start_scheduler, stop_scheduler
        start_scheduler()

    # Load syslog config from first tenant (if configured)
    try:
        from app.db.session import async_session_factory
        from sqlalchemy import select
        async with async_session_factory() as db:
            from app.tenants.models import Tenant
            tenant = (await db.execute(select(Tenant).limit(1))).scalar_one_or_none()
            if tenant and tenant.syslog_config and tenant.syslog_config.get("enabled"):
                from app.audit import configure_syslog
                cfg = tenant.syslog_config
                configure_syslog(cfg["host"], int(cfg.get("port", 514)), cfg.get("protocol", "udp"), cfg.get("facility", "local0"))
    except Exception:
        pass

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
app.include_router(users_router, prefix="/api/v1/users", tags=["Users"])
app.include_router(tickets_router, prefix="/api/v1/tickets", tags=["Tickets"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "getvul-api"}


# ── Export routes ──

from fastapi import Depends, Query
from fastapi.responses import StreamingResponse
from app.auth.dependencies import get_current_user
from app.db.session import get_db


@app.get("/api/v1/export/{resource}")
async def export_resource(
    resource: str,
    db=Depends(get_db),
    user=Depends(get_current_user),
    severity: list[str] | None = Query(None),
    status: list[str] | None = Query(None),
    source: list[str] | None = Query(None),
    exploit_available: bool | None = Query(None),
    cisa_kev: bool | None = Query(None),
    format: str = Query("csv"),
    device_type: list[str] | None = Query(None),
    section: list[str] | None = Query(None),
    top_count: int = Query(5),
    min_risk: int = Query(0),
):
    """Export data. Resources: vulnerabilities, assets, users, tickets, remediations, summary."""
    from app.export import (
        export_vulnerabilities_csv, export_assets_csv, export_users_csv,
        export_tickets_csv, export_remediations_csv, generate_executive_summary,
    )
    from app.audit import audit

    filters = {"format": format}
    if severity: filters["severity"] = severity
    if status: filters["status"] = status
    if source: filters["source"] = source
    if exploit_available: filters["exploit_available"] = True
    if cisa_kev: filters["cisa_kev"] = True
    if device_type: filters["device_type"] = device_type
    if section: filters["section"] = section
    filters["top_count"] = top_count
    filters["min_risk"] = min_risk

    now = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")

    if resource == "vulnerabilities":
        content = await export_vulnerabilities_csv(db, user.tenant_id, filters)
        filename = f"getvul_vulnerabilities_{now}.csv"
    elif resource == "assets":
        content = await export_assets_csv(db, user.tenant_id)
        filename = f"getvul_assets_{now}.csv"
    elif resource == "users":
        content = await export_users_csv(db, user.tenant_id)
        filename = f"getvul_users_{now}.csv"
    elif resource == "tickets":
        content = await export_tickets_csv(db, user.tenant_id)
        filename = f"getvul_tickets_{now}.csv"
    elif resource == "remediations":
        content = await export_remediations_csv(db, user.tenant_id)
        filename = f"getvul_remediations_{now}.csv"
    elif resource == "summary":
        fmt = filters.get("format", "txt") if isinstance(filters.get("format"), str) else "txt"
        await audit(db, user, "export.summary", "report", f"summary.{fmt}", filters)
        await db.commit()

        report_filters = {
            "severity": filters.get("severity"),
            "device_type": filters.get("device_type"),
            "exploit_available": filters.get("exploit_available"),
            "cisa_kev": filters.get("cisa_kev"),
            "sections": filters.get("section"),
            "top_count": filters.get("top_count", 5),
            "min_risk": filters.get("min_risk", 0),
        }

        if fmt == "pdf":
            from app.export import generate_executive_summary_pdf
            pdf_bytes = await generate_executive_summary_pdf(db, user.tenant_id, report_filters)
            return StreamingResponse(
                iter([bytes(pdf_bytes)]),
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename=getvul_executive_summary_{now}.pdf"},
            )
        elif fmt == "csv":
            from app.export import generate_executive_summary_csv
            content = await generate_executive_summary_csv(db, user.tenant_id, report_filters)
            return StreamingResponse(
                iter([content]),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=getvul_executive_summary_{now}.csv"},
            )
        else:
            content = await generate_executive_summary(db, user.tenant_id, report_filters)
            return StreamingResponse(
                iter([content]),
                media_type="text/plain",
                headers={"Content-Disposition": f"attachment; filename=getvul_executive_summary_{now}.txt"},
            )
    else:
        from fastapi import HTTPException
        raise HTTPException(400, f"Unknown resource: {resource}")

    await audit(db, user, "export.csv", resource, filename, filters)
    await db.commit()

    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


from datetime import datetime, timezone


# ── Dev-only routes ──
if settings.environment == "development":
    from app.dev_routes import router as dev_router
    app.include_router(dev_router, prefix="/dev", tags=["Dev"])
