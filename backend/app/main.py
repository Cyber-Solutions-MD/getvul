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
