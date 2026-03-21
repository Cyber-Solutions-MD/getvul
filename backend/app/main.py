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


# ── Scheduled Reports ──

@app.get("/api/v1/reports")
async def list_scheduled_reports(db=Depends(get_db), user=Depends(get_current_user)):
    from app.reports import list_reports
    return await list_reports(db, user.tenant_id)

@app.post("/api/v1/reports")
async def create_scheduled_report(body: dict, db=Depends(get_db), user=Depends(get_current_user)):
    from app.reports import create_report
    from app.audit import audit
    result = await create_report(db, user.tenant_id, body)
    await audit(db, user, "report.create", "report", result["id"], {"name": result["name"]})
    await db.commit()
    return result

@app.patch("/api/v1/reports/{report_id}")
async def update_scheduled_report(report_id: str, body: dict, db=Depends(get_db), user=Depends(get_current_user)):
    import uuid as _uuid
    from app.reports import update_report
    result = await update_report(db, user.tenant_id, _uuid.UUID(report_id), body)
    if not result:
        from fastapi import HTTPException
        raise HTTPException(404, "Report not found")
    await db.commit()
    return result

@app.delete("/api/v1/reports/{report_id}")
async def delete_scheduled_report(report_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    import uuid as _uuid
    from app.reports import delete_report
    if not await delete_report(db, user.tenant_id, _uuid.UUID(report_id)):
        from fastapi import HTTPException
        raise HTTPException(404, "Report not found")
    await db.commit()
    return {"message": "Deleted"}

@app.post("/api/v1/reports/{report_id}/send")
async def send_report_now(report_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    """Manually trigger a scheduled report."""
    import uuid as _uuid
    from app.reports import ScheduledReport, _send_report
    from sqlalchemy import select
    r = (await db.execute(select(ScheduledReport).where(
        ScheduledReport.id == _uuid.UUID(report_id), ScheduledReport.tenant_id == user.tenant_id
    ))).scalar_one_or_none()
    if not r:
        from fastapi import HTTPException
        raise HTTPException(404, "Report not found")
    await _send_report(db, r)
    r.last_sent_at = datetime.now(timezone.utc)
    r.last_send_status = "SUCCESS"
    await db.commit()
    return {"message": f"Report '{r.name}' generated", "format": r.format}


# ── Certificate management ──

@app.get("/api/v1/certificates")
async def get_certificate_info(user=Depends(get_current_user)):
    """Get info about the installed TLS certificate."""
    from app.certificates import get_cert_info
    return get_cert_info()


@app.post("/api/v1/certificates/upload")
async def upload_certificate(
    body: dict,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    """Upload a custom TLS certificate (PEM format)."""
    from app.auth.rbac import ROLE_HIERARCHY
    if ROLE_HIERARCHY.get(user.role.lower(), 0) < ROLE_HIERARCHY.get("owner", 4):
        from fastapi import HTTPException as HE
        raise HE(403, "Only owners can manage certificates")

    cert_pem = body.get("certificate", "")
    key_pem = body.get("private_key", "")
    if not cert_pem or not key_pem:
        from fastapi import HTTPException as HE
        raise HE(400, "Certificate and private key are required (PEM format)")

    from app.certificates import save_certificate
    from app.audit import audit
    result = save_certificate(cert_pem, key_pem)
    await audit(db, user, "cert.upload", "certificate", None, {"subject": result.get("subject")})
    await db.commit()
    return result


@app.post("/api/v1/certificates/self-signed")
async def generate_self_signed_cert(
    body: dict,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    """Generate a self-signed TLS certificate."""
    from app.auth.rbac import ROLE_HIERARCHY
    if ROLE_HIERARCHY.get(user.role.lower(), 0) < ROLE_HIERARCHY.get("owner", 4):
        from fastapi import HTTPException as HE
        raise HE(403, "Only owners can manage certificates")

    from app.certificates import generate_self_signed
    from app.audit import audit
    hostname = body.get("hostname", "getvul.local")
    result = generate_self_signed(hostname)
    await audit(db, user, "cert.generate", "certificate", None, {"hostname": hostname, "type": "self-signed"})
    await db.commit()
    return result


@app.delete("/api/v1/certificates")
async def remove_certificate(
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    """Remove the installed certificate."""
    from app.auth.rbac import ROLE_HIERARCHY
    if ROLE_HIERARCHY.get(user.role.lower(), 0) < ROLE_HIERARCHY.get("owner", 4):
        from fastapi import HTTPException as HE
        raise HE(403, "Only owners can manage certificates")

    from app.certificates import delete_certificate
    from app.audit import audit
    result = delete_certificate()
    await audit(db, user, "cert.delete", "certificate")
    await db.commit()
    return result


# ── Dev-only routes ──
if settings.environment == "development":
    from app.dev_routes import router as dev_router
    app.include_router(dev_router, prefix="/dev", tags=["Dev"])
