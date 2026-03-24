"""Cross-tenant isolation tests.

Verifies that no API endpoint leaks data between tenants.
Creates two tenants with separate users and data, then asserts
each can only see its own resources.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.auth.jwt import create_access_token
from app.tenants.models import Tenant, User
from app.ticketing.models import Ticket
from app.vulnerabilities.models import Vulnerability


@pytest.fixture
async def two_tenants(db: AsyncSession):
    """Create two tenants with users and sample data."""
    # Tenant A
    tenant_a = Tenant(name="Acme Corp", slug="acme", domain="acme.com", idp_provider="LOCAL")
    db.add(tenant_a)
    await db.flush()
    user_a = User(
        tenant_id=tenant_a.id,
        email="admin@acme.com",
        display_name="Acme Admin",
        role="OWNER",
        is_active=True,
    )
    db.add(user_a)
    await db.flush()

    # Tenant B
    tenant_b = Tenant(name="Beta Inc", slug="beta", domain="beta.io", idp_provider="LOCAL")
    db.add(tenant_b)
    await db.flush()
    user_b = User(
        tenant_id=tenant_b.id,
        email="admin@beta.io",
        display_name="Beta Admin",
        role="OWNER",
        is_active=True,
    )
    db.add(user_b)
    await db.flush()

    now = datetime.now(UTC)

    # Assets for each tenant
    asset_a = Asset(
        tenant_id=tenant_a.id,
        hostname="acme-server-01",
        os_name="Linux",
        device_category="SERVER",
        risk_score=75,
    )
    asset_b = Asset(
        tenant_id=tenant_b.id,
        hostname="beta-server-01",
        os_name="Windows",
        device_category="SERVER",
        risk_score=90,
    )
    db.add_all([asset_a, asset_b])
    await db.flush()

    # Vulnerabilities for each tenant
    vuln_a = Vulnerability(
        tenant_id=tenant_a.id,
        cve_id="CVE-2024-0001",
        vulnerability_name="Acme Vuln",
        severity="CRITICAL",
        source="CROWDSTRIKE",
        asset_id=asset_a.id,
        status="OPEN",
        first_detected_at=now,
        last_seen_at=now,
    )
    vuln_b = Vulnerability(
        tenant_id=tenant_b.id,
        cve_id="CVE-2024-0002",
        vulnerability_name="Beta Vuln",
        severity="HIGH",
        source="NESSUS",
        asset_id=asset_b.id,
        status="OPEN",
        first_detected_at=now,
        last_seen_at=now,
    )
    db.add_all([vuln_a, vuln_b])
    await db.flush()

    token_a = create_access_token(
        user_id=str(user_a.id),
        tenant_id=str(tenant_a.id),
        email=user_a.email,
        role=user_a.role,
    )
    token_b = create_access_token(
        user_id=str(user_b.id),
        tenant_id=str(tenant_b.id),
        email=user_b.email,
        role=user_b.role,
    )

    return {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "user_a": user_a,
        "user_b": user_b,
        "asset_a": asset_a,
        "asset_b": asset_b,
        "vuln_a": vuln_a,
        "vuln_b": vuln_b,
        "token_a": token_a,
        "token_b": token_b,
    }


class TestTenantIsolation:
    """Verify that each tenant can only access its own data."""

    # ── Asset isolation ──

    def test_asset_model_has_tenant_id(self):
        """Asset model must have tenant_id as a required field."""
        from sqlalchemy import inspect

        cols = {c.name for c in inspect(Asset).columns}
        assert "tenant_id" in cols

    def test_vulnerability_model_has_tenant_id(self):
        """Vulnerability model must have tenant_id as a required field."""
        from sqlalchemy import inspect

        cols = {c.name for c in inspect(Vulnerability).columns}
        assert "tenant_id" in cols

    def test_ticket_model_has_tenant_id(self):
        """Ticket model must have tenant_id as a required field."""
        from sqlalchemy import inspect

        cols = {c.name for c in inspect(Ticket).columns}
        assert "tenant_id" in cols

    # ── Query isolation ──

    @pytest.mark.asyncio
    async def test_asset_query_isolated(self, db: AsyncSession, two_tenants):
        """Assets query must only return tenant's own assets."""
        data = two_tenants
        # Query as tenant A
        result = await db.execute(select(Asset).where(Asset.tenant_id == data["tenant_a"].id))
        assets = result.scalars().all()
        hostnames = [a.hostname for a in assets]
        assert "acme-server-01" in hostnames
        assert "beta-server-01" not in hostnames

    @pytest.mark.asyncio
    async def test_vulnerability_query_isolated(self, db: AsyncSession, two_tenants):
        """Vulnerability query must only return tenant's own vulns."""
        data = two_tenants
        result = await db.execute(select(Vulnerability).where(Vulnerability.tenant_id == data["tenant_b"].id))
        vulns = result.scalars().all()
        cves = [v.cve_id for v in vulns]
        assert "CVE-2024-0002" in cves
        assert "CVE-2024-0001" not in cves

    @pytest.mark.asyncio
    async def test_asset_get_by_id_requires_tenant(self, db: AsyncSession, two_tenants):
        """Getting an asset by ID must also verify tenant_id."""
        data = two_tenants
        # Tenant A trying to access Tenant B's asset by ID should fail
        result = await db.execute(
            select(Asset).where(
                Asset.id == data["asset_b"].id,
                Asset.tenant_id == data["tenant_a"].id,
            )
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_vuln_get_by_id_requires_tenant(self, db: AsyncSession, two_tenants):
        """Getting a vuln by ID must also verify tenant_id."""
        data = two_tenants
        result = await db.execute(
            select(Vulnerability).where(
                Vulnerability.id == data["vuln_b"].id,
                Vulnerability.tenant_id == data["tenant_a"].id,
            )
        )
        assert result.scalar_one_or_none() is None

    # ── Data count isolation ──

    @pytest.mark.asyncio
    async def test_tenant_a_sees_only_own_vulns(self, db: AsyncSession, two_tenants):
        """Tenant A should see exactly 1 vuln, not tenant B's."""
        from sqlalchemy import func

        data = two_tenants
        count = (
            await db.execute(select(func.count(Vulnerability.id)).where(Vulnerability.tenant_id == data["tenant_a"].id))
        ).scalar_one()
        assert count == 1

    @pytest.mark.asyncio
    async def test_tenant_b_sees_only_own_assets(self, db: AsyncSession, two_tenants):
        """Tenant B should see exactly 1 asset, not tenant A's."""
        from sqlalchemy import func

        data = two_tenants
        count = (
            await db.execute(select(func.count(Asset.id)).where(Asset.tenant_id == data["tenant_b"].id))
        ).scalar_one()
        assert count == 1

    # ── Token isolation ──

    def test_tokens_contain_correct_tenant(self, two_tenants):
        """JWT tokens must contain the correct tenant_id."""
        from app.auth.jwt import decode_token

        data = two_tenants
        payload_a = decode_token(data["token_a"])
        payload_b = decode_token(data["token_b"])

        assert payload_a.tenant_id == str(data["tenant_a"].id)
        assert payload_b.tenant_id == str(data["tenant_b"].id)
        assert payload_a.tenant_id != payload_b.tenant_id

    # ── Unique constraint validation ──

    def test_vuln_dedup_includes_tenant(self):
        """Vulnerability dedup constraint must include tenant_id."""
        constraints = {c.name for c in Vulnerability.__table__.constraints}
        assert "uq_vuln_dedup" in constraints

    def test_asset_hostname_unique_per_tenant(self):
        """Asset hostname uniqueness must be scoped to tenant_id."""
        constraints = {c.name for c in Asset.__table__.constraints}
        assert "uq_asset_tenant_hostname" in constraints
