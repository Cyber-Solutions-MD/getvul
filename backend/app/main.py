"""GetVul API — entry point."""

import asyncio
import re
import time
import uuid
import uuid as _uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timezone
from typing import Any

import structlog
from cryptography.fernet import Fernet
from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from structlog.contextvars import bind_contextvars, clear_contextvars

from app.api.v1.ai import ai_router
from app.assets.groups_router import router as asset_groups_router
from app.assets.router import router as asset_router
from app.auth.dependencies import get_current_user
from app.auth.router import router as auth_router
from app.auth.schemas import CurrentUser
from app.campaigns.router import router as campaigns_router
from app.config import settings
from app.connectors.router import router as connector_router
from app.coverage.router import router as coverage_router
from app.cspm.router import router as cspm_router
from app.db.session import get_db
from app.exceptions.router import router as exceptions_router
from app.logging import configure_logging
from app.notifications.router import router as notifications_router
from app.redis_client import get_redis_client
from app.search import search_router
from app.tenants.router import router as tenant_router
from app.ticketing.router import router as tickets_router
from app.users.router import router as users_router
from app.vulnerabilities.risk_cutover_router import router as risk_cutover_router
from app.vulnerabilities.router import router as vuln_router

logger = structlog.get_logger()

# Placeholder literals — copied verbatim from config.py defaults so we can
# detect when an operator has not replaced them with real values.
ENCRYPTION_KEY_PLACEHOLDER = (
    "CHANGE-ME-generate-with-python-c-from-cryptography.fernet-import-Fernet-Fernet.generate_key"
)
JWT_SECRET_PLACEHOLDER = "CHANGE-ME-IN-PRODUCTION"


def _check_secrets_at_startup() -> list[str]:
    """Validate ENCRYPTION_KEY and JWT_SECRET_KEY at startup.

    Returns a list of issue strings. In development, issues are logged as
    warnings and the list is returned. In production, any issues cause a
    RuntimeError (hard-fail boot). Key material is never logged.
    """
    issues: list[str] = []

    # --- ENCRYPTION_KEY check ---
    if not settings.encryption_key or settings.encryption_key == ENCRYPTION_KEY_PLACEHOLDER:
        issues.append("ENCRYPTION_KEY is unset or uses the default placeholder")
    else:
        try:
            Fernet(settings.encryption_key.encode())
        except (ValueError, TypeError):
            # Fernet raises ValueError (binascii.Error is a ValueError subclass)
            # for malformed keys; TypeError for non-bytes input.
            issues.append("ENCRYPTION_KEY is set but is not a valid Fernet key")

    # --- JWT_SECRET_KEY check ---
    if settings.jwt_secret_key == JWT_SECRET_PLACEHOLDER:
        issues.append("JWT_SECRET_KEY uses the default placeholder")

    # Log each issue (without key material)
    for msg in issues:
        if settings.environment == "production":
            logger.critical("startup_secret_check_failed", issue=msg)
        else:
            logger.warning("startup_secret_check_warning", issue=msg)

    # Hard-fail in production
    if issues and settings.environment == "production":
        raise RuntimeError(
            "Backend refused to start: insecure secrets detected. "
            "Set ENCRYPTION_KEY and JWT_SECRET_KEY to non-placeholder values."
        )

    return issues


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Configure structured logging first — before any other startup work so
    # every subsequent log line (including secrets check) uses the right renderer.
    configure_logging()

    # Validate secrets before any other startup work (T-05-05).
    # Raises RuntimeError in production if ENCRYPTION_KEY or JWT_SECRET_KEY
    # are unset / placeholder / invalid. Warns and continues in development.
    _check_secrets_at_startup()

    # Start background sync scheduler
    if settings.environment in ("development", "production"):
        from app.connectors.scheduler import start_scheduler

        start_scheduler()

    # Single construction site (Phase 26 Plan 07): app.redis_client.get_redis_client()
    # builds the SAME BlockingConnectionPool-backed client this lifespan used to
    # construct inline — see that function's docstring for the PROD-01-02
    # rationale. The connector scheduler's batch pre-warm/poll tasks (app.ai.batch,
    # Plan 08) call the identical factory to obtain their own client outside any
    # FastAPI request.
    app.state.redis = get_redis_client()

    # Load syslog config from first tenant (if configured)
    try:
        from sqlalchemy import select

        from app.db.session import async_session_factory

        async with async_session_factory() as db:
            from app.tenants.models import Tenant

            tenant = (await db.execute(select(Tenant).limit(1))).scalar_one_or_none()
            if tenant and tenant.syslog_config and tenant.syslog_config.get("enabled"):
                from app.audit import configure_syslog

                cfg = tenant.syslog_config
                configure_syslog(
                    cfg["host"], int(cfg.get("port", 514)), cfg.get("protocol", "udp"), cfg.get("facility", "local0")
                )
    except Exception:
        logger.exception("syslog_setup_failed_at_startup")

    yield

    try:
        await app.state.redis.aclose()
    except Exception:
        logger.exception("redis_aclose_failed")

    # Cleanup
    if settings.environment in ("development", "production"):
        try:
            from app.connectors.scheduler import stop_scheduler

            stop_scheduler()
        except Exception:
            logger.exception("scheduler_stop_failed")


# ── Security headers middleware ──

# Swagger UI (/docs), ReDoc (/redoc) and the OpenAPI schema (/openapi.json) are
# mounted only when settings.debug is True. Their HTML pages load JS/CSS from a
# CDN and fetch the schema, so the strict API CSP (default-src 'none') would
# render them blank. These routes never exist in production (debug=False).
DOCS_PATHS = frozenset({"/docs", "/redoc", "/openapi.json"})


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        # Lock the JSON API surface down to nothing, but skip the strict policy
        # for the debug-only interactive docs routes so Swagger UI / ReDoc render.
        if not (settings.debug and request.url.path in DOCS_PATHS):
            response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        # Prevent caching of API responses
        if request.url.path.startswith("/api/") or request.url.path.startswith("/auth/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
        return response


# ── Tenant rate limiting middleware ──

RATE_LIMIT_REQUESTS = 200  # max requests per window
RATE_LIMIT_WINDOW = 60  # seconds


class TenantRateLimitMiddleware(BaseHTTPMiddleware):
    """Per-tenant rate limiting via Redis sorted-set sliding window."""

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        # Extract tenant from JWT (lightweight — just parse, don't validate DB)
        auth = request.headers.get("authorization", "")
        tenant_key = "anonymous"
        if auth.startswith("Bearer "):
            try:
                from app.auth.jwt import decode_token

                payload = decode_token(auth[7:])
                tenant_key = payload.tenant_id
            except Exception:
                pass

        redis_client = request.app.state.redis
        key = f"ratelimit:{tenant_key}"
        now_ms = int(time.time() * 1000)
        window_start_ms = now_ms - RATE_LIMIT_WINDOW * 1000
        # Unique member defeats sub-ms ZADD duplicate-member coalescing (Pitfall 1).
        member = f"{now_ms}:{uuid.uuid4().hex[:8]}"

        try:
            async with redis_client.pipeline(transaction=True) as pipe:
                pipe.zremrangebyscore(key, 0, window_start_ms)
                pipe.zadd(key, {member: now_ms})
                pipe.zcard(key)
                pipe.expire(key, RATE_LIMIT_WINDOW)
                results = await pipe.execute()
        except RedisError as e:
            logger.warning(
                "redis_unavailable",
                subsystem="rate_limiter",
                error=str(e),
                tenant_id=tenant_key if tenant_key != "anonymous" else None,
            )
            return await call_next(request)

        count = results[2]
        if count > RATE_LIMIT_REQUESTS:
            from starlette.responses import JSONResponse

            return JSONResponse(
                {"detail": "Rate limit exceeded. Try again later."},
                status_code=429,
                headers={"Retry-After": str(RATE_LIMIT_WINDOW)},
            )

        return await call_next(request)


# ── Request ID middleware ──

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Generate or validate X-Request-ID and bind it to structlog contextvars."""

    async def dispatch(self, request: Request, call_next):
        clear_contextvars()
        inbound = request.headers.get("X-Request-ID", "")
        if inbound and _REQUEST_ID_RE.match(inbound):  # noqa: SIM108 — explicit if/else keeps the per-branch comments
            request_id = inbound  # honor sanitized inbound (len<=128, charset [A-Za-z0-9._-])
        else:
            request_id = str(uuid.uuid4())  # invalid/oversized/missing -> mint UUID4
        bind_contextvars(request_id=request_id)
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


def create_app() -> FastAPI:
    """Build a fresh FastAPI instance with the full middleware/router stack.

    Each call returns an independent app whose route handlers close over its
    own local `app`. The module-level `app = create_app()` at the bottom is
    the one uvicorn imports; tests call create_app() to spin up isolated
    replicas (PROD-01-03).
    """
    app = FastAPI(
        title="GetVul API",
        description="Unified Vulnerability Aggregation Platform",
        version="0.1.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    cors_origin_kwargs: dict[str, Any]
    if settings.debug:
        cors_origin_kwargs = {"allow_origins": ["http://localhost:3000"]}
    else:
        # Starlette matches allow_origins literally, so a "https://*.getvul.app"
        # entry never matches a real subdomain. Use allow_origin_regex (matched
        # via re.fullmatch) to accept any single-label https subdomain of getvul.app.
        cors_origin_kwargs = {"allow_origin_regex": r"https://[a-z0-9-]+\.getvul\.app"}

    app.add_middleware(
        CORSMiddleware,
        **cors_origin_kwargs,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(TenantRateLimitMiddleware)
    app.add_middleware(RequestIdMiddleware)

    # ── Routes ──
    app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
    app.include_router(vuln_router, prefix="/api/v1/vulnerabilities", tags=["Vulnerabilities"])
    app.include_router(asset_router, prefix="/api/v1/assets", tags=["Assets"])
    app.include_router(asset_groups_router, prefix="/api/v1/asset-groups", tags=["Asset Groups"])
    app.include_router(tenant_router, prefix="/api/v1/tenant", tags=["Tenant & Users"])
    app.include_router(connector_router, prefix="/api/v1/connectors", tags=["Connectors"])
    app.include_router(cspm_router, prefix="/api/v1/cspm", tags=["CSPM"])
    app.include_router(users_router, prefix="/api/v1/users", tags=["Users"])
    app.include_router(tickets_router, prefix="/api/v1/tickets", tags=["Tickets"])
    app.include_router(campaigns_router, prefix="/api/v1/campaigns", tags=["Campaigns"])
    app.include_router(exceptions_router, prefix="/api/v1/exceptions", tags=["Exceptions"])
    app.include_router(coverage_router, prefix="/api/v1/coverage", tags=["Coverage"])

    app.include_router(notifications_router, prefix="/api/v1/notifications", tags=["Notifications"])
    app.include_router(search_router, prefix="/api/v1", tags=["Search"])
    app.include_router(ai_router)
    app.include_router(risk_cutover_router, prefix="/api/v1/risk-cutover", tags=["Risk Cutover"])

    @app.get("/health")
    async def health_check():
        return {"status": "ok", "service": "getvul-api"}

    @app.get("/ready")
    async def readiness_check(request: Request):
        """Readiness probe — Postgres SELECT 1 + Redis PING, 500ms bound each (D-06)."""
        checks: dict = {}
        overall_ok = True

        t0 = time.monotonic()
        try:
            # Resolve the factory at call time (mirrors the lifespan import at the
            # top of this module) so a live-swapped session factory — e.g. a test
            # simulating a Postgres outage — is honored instead of a stale binding.
            from app.db.session import async_session_factory

            async with async_session_factory() as session:
                await asyncio.wait_for(session.execute(text("SELECT 1")), timeout=0.5)
            checks["postgres"] = {"ok": True, "latency_ms": round((time.monotonic() - t0) * 1000)}
        except TimeoutError:
            checks["postgres"] = {"ok": False, "error": "timeout"}
            overall_ok = False
        except Exception as exc:
            checks["postgres"] = {"ok": False, "error": type(exc).__name__}
            overall_ok = False

        t0 = time.monotonic()
        try:
            await asyncio.wait_for(request.app.state.redis.ping(), timeout=0.5)
            checks["redis"] = {"ok": True, "latency_ms": round((time.monotonic() - t0) * 1000)}
        except TimeoutError:
            checks["redis"] = {"ok": False, "error": "timeout"}
            overall_ok = False
        except Exception as exc:
            checks["redis"] = {"ok": False, "error": type(exc).__name__}
            overall_ok = False

        status = "ready" if overall_ok else "not_ready"
        if not overall_ok:
            logger.error(
                "readiness_check_failed",
                postgres_ok=checks["postgres"]["ok"],
                redis_ok=checks["redis"]["ok"],
            )
        return JSONResponse(
            content={"status": status, "checks": checks},
            status_code=200 if overall_ok else 503,
        )

    # ── Export routes ──

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
        from app.audit import audit
        from app.export import (
            export_assets_csv,
            export_remediations_csv,
            export_tickets_csv,
            export_users_csv,
            export_vulnerabilities_csv,
            generate_executive_summary,
        )

        filters = {"format": format}
        if severity:
            filters["severity"] = severity
        if status:
            filters["status"] = status
        if source:
            filters["source"] = source
        if exploit_available:
            filters["exploit_available"] = True
        if cisa_kev:
            filters["cisa_kev"] = True
        if device_type:
            filters["device_type"] = device_type
        if section:
            filters["section"] = section
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

    # ── Scheduled Reports ──

    @app.get("/api/v1/reports")
    async def list_scheduled_reports(db=Depends(get_db), user=Depends(get_current_user)):
        from app.reports import list_reports

        return await list_reports(db, user.tenant_id)

    @app.post("/api/v1/reports")
    async def create_scheduled_report(body: dict, db=Depends(get_db), user=Depends(get_current_user)):
        from app.audit import audit
        from app.reports import create_report

        result = await create_report(db, user.tenant_id, body)
        await audit(db, user, "report.create", "report", result["id"], {"name": result["name"]})
        await db.commit()
        return result

    @app.patch("/api/v1/reports/{report_id}")
    async def update_scheduled_report(report_id: str, body: dict, db=Depends(get_db), user=Depends(get_current_user)):
        from app.reports import update_report

        result = await update_report(db, user.tenant_id, _uuid.UUID(report_id), body)
        if not result:
            from fastapi import HTTPException

            raise HTTPException(404, "Report not found")
        await db.commit()
        return result

    @app.delete("/api/v1/reports/{report_id}")
    async def delete_scheduled_report(report_id: str, db=Depends(get_db), user=Depends(get_current_user)):
        from app.reports import delete_report

        if not await delete_report(db, user.tenant_id, _uuid.UUID(report_id)):
            from fastapi import HTTPException

            raise HTTPException(404, "Report not found")
        await db.commit()
        return {"message": "Deleted"}

    @app.post("/api/v1/reports/{report_id}/send")
    async def send_report_now(report_id: str, db=Depends(get_db), user=Depends(get_current_user)):
        """Manually trigger a scheduled report."""
        from sqlalchemy import select

        from app.reports import ScheduledReport, _send_report

        r = (
            await db.execute(
                select(ScheduledReport).where(
                    ScheduledReport.id == _uuid.UUID(report_id), ScheduledReport.tenant_id == user.tenant_id
                )
            )
        ).scalar_one_or_none()
        if not r:
            from fastapi import HTTPException

            raise HTTPException(404, "Report not found")
        await _send_report(db, r)
        r.last_sent_at = datetime.now(UTC)
        r.last_send_status = "SUCCESS"
        await db.commit()
        return {"message": f"Report '{r.name}' generated", "format": r.format}

    # ── SMTP / Email ──

    @app.post("/api/v1/smtp/test")
    async def test_smtp(
        body: dict,
        db=Depends(get_db),
        user=Depends(get_current_user),
    ):
        """Test SMTP connection with the provided config."""
        from app.email import test_smtp_connection

        cfg = body.get("smtp_config")
        if not cfg:
            # Use saved config from tenant
            from sqlalchemy import select

            from app.tenants.models import Tenant

            tenant = (await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))).scalar_one()
            cfg = tenant.smtp_config
        if not cfg or not cfg.get("host"):
            from fastapi import HTTPException

            raise HTTPException(400, "No SMTP configuration provided")
        return test_smtp_connection(cfg)

    @app.post("/api/v1/smtp/test-email")
    async def send_test_email(
        body: dict,
        db=Depends(get_db),
        user=Depends(get_current_user),
    ):
        """Send a test email to verify SMTP config works end-to-end."""
        from sqlalchemy import select

        from app.email import send_email
        from app.tenants.models import Tenant

        tenant = (await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))).scalar_one()
        cfg = tenant.smtp_config
        if not cfg or not cfg.get("host"):
            from fastapi import HTTPException

            raise HTTPException(400, "SMTP is not configured. Save SMTP settings first.")

        recipient = body.get("to") or user.email
        result = send_email(
            smtp_config=cfg,
            to=[recipient],
            subject="GetVul — SMTP Test",
            body=f"This is a test email from GetVul.\n\nIf you received this, your SMTP configuration is working correctly.\n\nSent by: {user.email}",
        )
        from app.audit import audit

        await audit(db, user, "smtp.test", "email", None, {"to": recipient, "ok": result.get("ok")})
        await db.commit()
        return result

    # ── Certificate management ──

    @app.get("/api/v1/certificates")
    async def get_certificate_info(user=Depends(get_current_user)):
        """Get info about the installed TLS certificate."""
        from app.certificates import get_cert_info

        return get_cert_info()

    @app.post("/api/v1/certificates/upload")
    async def upload_certificate(
        body: dict[str, Any],
        db: AsyncSession = Depends(get_db),
        user: CurrentUser = Depends(get_current_user),
    ) -> dict[str, Any]:
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

        from app.audit import audit
        from app.certificates import save_certificate

        result = save_certificate(cert_pem, key_pem)
        await audit(db, user, "cert.upload", "certificate", None, {"subject": result.get("subject")})
        await db.commit()
        return result

    @app.post("/api/v1/certificates/self-signed")
    async def generate_self_signed_cert(
        body: dict[str, Any],
        db: AsyncSession = Depends(get_db),
        user: CurrentUser = Depends(get_current_user),
    ) -> dict[str, Any]:
        """Generate a self-signed TLS certificate."""
        from app.auth.rbac import ROLE_HIERARCHY

        if ROLE_HIERARCHY.get(user.role.lower(), 0) < ROLE_HIERARCHY.get("owner", 4):
            from fastapi import HTTPException as HE

            raise HE(403, "Only owners can manage certificates")

        from app.audit import audit
        from app.certificates import generate_self_signed

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

        from app.audit import audit
        from app.certificates import delete_certificate

        result = delete_certificate()
        await audit(db, user, "cert.delete", "certificate")
        await db.commit()
        return result

    # ── Dev-only routes ──
    if settings.environment == "development":
        from app.dev_routes import router as dev_router

        app.include_router(dev_router, prefix="/dev", tags=["Dev"])

    return app


app = create_app()
