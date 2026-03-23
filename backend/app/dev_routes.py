"""Dev-only routes for seeding and clearing data."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.seed import seed_database

router = APIRouter()


@router.post("/seed")
async def seed(db: AsyncSession = Depends(get_db)):
    """Seed the database with sample data. Dev only."""
    return await seed_database(db)


@router.post("/run-correlations")
async def run_correlations_endpoint(db: AsyncSession = Depends(get_db)):
    """Run the correlation engine for the demo tenant. Dev only."""
    from sqlalchemy import select

    from app.assets.risk_score import compute_risk_scores
    from app.tenants.models import Tenant
    from app.vulnerabilities.correlation_service import run_correlations

    tenant = (await db.execute(select(Tenant).limit(1))).scalar_one_or_none()
    if not tenant:
        return {"error": "No tenant found. Seed first."}

    corr_stats = await run_correlations(db, tenant.id)
    risk_stats = await compute_risk_scores(db, tenant.id)
    await db.commit()

    return {
        "message": "Correlations and risk scores computed",
        "tenant_id": str(tenant.id),
        "correlations": corr_stats,
        "risk_scores": risk_stats,
    }


@router.post("/clear-test-data")
async def clear_test_data(db: AsyncSession = Depends(get_db)):
    """Remove all seed/test data. Keeps connector configs and real synced data untouched.

    This removes the demo tenant, its users, and ALL vulnerabilities/assets/misconfigs
    that belong to it. Then re-creates a minimal tenant + user for dev-token auth.
    """
    from app.assets.models import Asset
    from app.cspm.models import Misconfiguration
    from app.tenants.models import Tenant, User
    from app.ticketing.models import SyncLog, Ticket, TicketRule
    from app.vulnerabilities.models import Vulnerability, VulnerabilityCorrelation

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
    from sqlalchemy import update

    from app.ticketing.models import ConnectorConfig

    await db.execute(update(ConnectorConfig).values(tenant_id=tenant.id))

    await db.commit()

    return {
        "message": "All test data cleared. Connector configs preserved.",
        "new_tenant_id": str(tenant.id),
        "new_user_id": str(user.id),
    }
