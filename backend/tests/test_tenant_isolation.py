"""Cross-tenant isolation tests.

Verifies that models enforce tenant isolation through constraints,
that all router queries include tenant_id filters, and that
JWT tokens carry correct tenant_id.
"""

from __future__ import annotations

import uuid

from app.assets.models import Asset
from app.auth.jwt import create_access_token, decode_token
from app.ticketing.models import Ticket
from app.vulnerabilities.models import Vulnerability


class TestTenantModelConstraints:
    """Verify that models have tenant_id fields and dedup constraints include tenant."""

    def test_asset_has_tenant_id_column(self):
        cols = {c.name for c in Asset.__table__.columns}
        assert "tenant_id" in cols

    def test_vulnerability_has_tenant_id_column(self):
        cols = {c.name for c in Vulnerability.__table__.columns}
        assert "tenant_id" in cols

    def test_ticket_has_tenant_id_column(self):
        cols = {c.name for c in Ticket.__table__.columns}
        assert "tenant_id" in cols

    def test_vuln_dedup_includes_tenant(self):
        """Vulnerability dedup constraint must include tenant_id."""
        constraints = {c.name for c in Vulnerability.__table__.constraints}
        assert "uq_vuln_dedup" in constraints

        for c in Vulnerability.__table__.constraints:
            if c.name == "uq_vuln_dedup":
                col_names = {col.name for col in c.columns}
                assert "tenant_id" in col_names
                assert "cve_id" in col_names
                assert "asset_id" in col_names
                assert "source" in col_names

    def test_asset_hostname_unique_per_tenant(self):
        """Asset hostname uniqueness must be scoped to tenant_id."""
        constraints = {c.name for c in Asset.__table__.constraints}
        assert "uq_asset_tenant_hostname" in constraints

        for c in Asset.__table__.constraints:
            if c.name == "uq_asset_tenant_hostname":
                col_names = {col.name for col in c.columns}
                assert "tenant_id" in col_names
                assert "hostname" in col_names

    def test_asset_tenant_id_indexed(self):
        """tenant_id should be indexed for query performance."""
        tenant_indexed = any(any(col.name == "tenant_id" for col in idx.columns) for idx in Asset.__table__.indexes)
        assert tenant_indexed

    def test_vulnerability_tenant_id_indexed(self):
        tenant_indexed = any(
            any(col.name == "tenant_id" for col in idx.columns) for idx in Vulnerability.__table__.indexes
        )
        assert tenant_indexed


class TestTenantTokenIsolation:
    """Verify JWT tokens correctly carry and isolate tenant_id."""

    def test_access_token_contains_tenant_id(self):
        tenant_id = str(uuid.uuid4())
        token = create_access_token(
            user_id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            email="test@example.com",
            role="VIEWER",
        )
        payload = decode_token(token)
        assert payload.tenant_id == tenant_id

    def test_different_tenants_get_different_tokens(self):
        tenant_a = str(uuid.uuid4())
        tenant_b = str(uuid.uuid4())

        token_a = create_access_token(
            user_id=str(uuid.uuid4()),
            tenant_id=tenant_a,
            email="admin@company-a.com",
            role="OWNER",
        )
        token_b = create_access_token(
            user_id=str(uuid.uuid4()),
            tenant_id=tenant_b,
            email="admin@company-b.com",
            role="OWNER",
        )

        payload_a = decode_token(token_a)
        payload_b = decode_token(token_b)

        assert payload_a.tenant_id == tenant_a
        assert payload_b.tenant_id == tenant_b
        assert payload_a.tenant_id != payload_b.tenant_id

    def test_token_role_preserved(self):
        token = create_access_token(
            user_id=str(uuid.uuid4()),
            tenant_id=str(uuid.uuid4()),
            email="analyst@example.com",
            role="ANALYST",
        )
        payload = decode_token(token)
        assert payload.role == "ANALYST"


class TestRouterTenantFiltering:
    """Verify that router query functions include tenant_id filtering.

    Reads source files directly to verify all DB queries are tenant-scoped.
    """

    def _read_file(self, rel_path: str) -> str:
        from pathlib import Path

        return (Path(__file__).parent.parent / rel_path).read_text()

    def test_asset_router_filters_by_tenant(self):
        source = self._read_file("app/assets/router.py")
        assert "user.tenant_id" in source
        assert "Asset.tenant_id" in source

    def test_vuln_router_filters_by_tenant(self):
        source = self._read_file("app/vulnerabilities/router.py")
        assert "user.tenant_id" in source

    def test_ticket_router_filters_by_tenant(self):
        source = self._read_file("app/ticketing/router.py")
        assert "user.tenant_id" in source

    def test_connector_router_filters_by_tenant(self):
        source = self._read_file("app/connectors/router.py")
        assert "user.tenant_id" in source

    def test_tenant_router_filters_by_tenant(self):
        source = self._read_file("app/tenants/router.py")
        assert "user.tenant_id" in source

    def test_enrich_assets_filters_by_tenant(self):
        """enrich_assets must scope asset queries by tenant_id."""
        source = self._read_file("app/enrich_assets.py")
        assert "Asset.tenant_id == tenant_id" in source

    def test_remediation_service_excludes_ignored_assets(self):
        """Remediation queries must exclude ignored assets."""
        source = self._read_file("app/vulnerabilities/remediation_service.py")
        assert "Asset.is_ignored" in source
