"""001 - Initial schema.

Revision ID: 001_initial_schema
Revises: -
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(63), unique=True, nullable=False, index=True),
        sa.Column("domain", sa.String(255), unique=True),
        sa.Column("idp_provider", sa.String(30), nullable=False),
        sa.Column("idp_tenant_id", sa.String(255)),
        sa.Column("session_timeout_minutes", sa.Integer, server_default="15"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("email", sa.String(320), nullable=False, index=True),
        sa.Column("display_name", sa.String(255)),
        sa.Column("avatar_url", sa.String(500)),
        sa.Column("role", sa.String(20), nullable=False, server_default="VIEWER"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("idp_subject", sa.String(255), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "email", name="uq_user_tenant_email"),
    )
    op.create_table(
        "assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("hostname", sa.String(255), index=True),
        sa.Column("ip_addresses", postgresql.JSONB, server_default="[]"),
        sa.Column("mac_addresses", postgresql.JSONB, server_default="[]"),
        sa.Column("os_name", sa.String(100)),
        sa.Column("os_version", sa.String(50)),
        sa.Column("asset_type", sa.String(30)),
        sa.Column("cloud_provider", sa.String(20)),
        sa.Column("cloud_resource_id", sa.String(300)),
        sa.Column("seen_by_sources", postgresql.JSONB, server_default="[]"),
        sa.Column("crowdstrike_aid", sa.String(100)),
        sa.Column("defender_device_id", sa.String(100)),
        sa.Column("wiz_asset_id", sa.String(100)),
        sa.Column("nessus_host_id", sa.String(100)),
        sa.Column("risk_score", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "hostname", name="uq_asset_tenant_hostname"),
    )
    op.create_table(
        "vulnerabilities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cve_id", sa.String(20)),
        sa.Column("vulnerability_name", sa.String(500)),
        sa.Column("cvss_v3_score", sa.Numeric(3, 1)),
        sa.Column("cvss_v3_vector", sa.String(100)),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("epss_score", sa.Numeric(5, 4)),
        sa.Column("exploit_available", sa.Boolean, server_default="false"),
        sa.Column("cisa_kev", sa.Boolean, server_default="false"),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assets.id", ondelete="SET NULL")),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("source_vuln_id", sa.String(200)),
        sa.Column("source_scan_id", sa.String(200)),
        sa.Column("affected_product", sa.String(300)),
        sa.Column("affected_version", sa.String(100)),
        sa.Column("fixed_version", sa.String(100)),
        sa.Column("remediation_info", sa.Text),
        sa.Column("status", sa.String(20), server_default="OPEN"),
        sa.Column("first_detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("remediated_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "cve_id", "asset_id", "source", name="uq_vuln_dedup"),
    )
    op.create_index("idx_vuln_tenant_severity", "vulnerabilities", ["tenant_id", "severity"])
    op.create_index("idx_vuln_cve", "vulnerabilities", ["cve_id"])
    op.create_index("idx_vuln_status", "vulnerabilities", ["tenant_id", "status"])
    op.create_index("idx_vuln_source", "vulnerabilities", ["tenant_id", "source"])
    op.create_index("idx_vuln_asset", "vulnerabilities", ["asset_id"])
    op.create_index("idx_vuln_last_seen", "vulnerabilities", ["last_seen_at"])
    op.create_table(
        "vulnerability_correlations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("cve_id", sa.String(20), nullable=False, index=True),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("crowdstrike_vuln_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vulnerabilities.id", ondelete="SET NULL")),
        sa.Column("nessus_vuln_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vulnerabilities.id", ondelete="SET NULL")),
        sa.Column("defender_vuln_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vulnerabilities.id", ondelete="SET NULL")),
        sa.Column("wiz_vuln_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vulnerabilities.id", ondelete="SET NULL")),
        sa.Column("sources_count", sa.Integer, server_default="1"),
        sa.Column("confidence", sa.String(10), server_default="'LOW'"),
        sa.UniqueConstraint("tenant_id", "cve_id", "asset_id", name="uq_correlation"),
    )
    op.create_index("idx_correlation_cve", "vulnerability_correlations", ["tenant_id", "cve_id"])
    op.create_table(
        "connector_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("connector_type", sa.String(30), nullable=False),
        sa.Column("is_enabled", sa.Boolean, server_default="true"),
        sa.Column("credentials_secret_arn", sa.String(500)),
        sa.Column("config", postgresql.JSONB, server_default="{}"),
        sa.Column("last_sync_at", sa.DateTime(timezone=True)),
        sa.Column("last_sync_status", sa.String(20)),
        sa.Column("last_sync_record_count", sa.Integer),
        sa.Column("sync_interval_minutes", sa.Integer, server_default="15"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "connector_type", name="uq_connector_tenant_type"),
    )
    op.create_table(
        "sync_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("connector_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("connector_configs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("records_fetched", sa.Integer, server_default="0"),
        sa.Column("records_created", sa.Integer, server_default="0"),
        sa.Column("records_updated", sa.Integer, server_default="0"),
        sa.Column("error_message", sa.Text),
        sa.Column("details", postgresql.JSONB, server_default="{}"),
    )
    op.create_table(
        "tickets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("vulnerability_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vulnerabilities.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("external_ticket_id", sa.String(200), nullable=False),
        sa.Column("external_ticket_url", sa.String(500), nullable=False),
        sa.Column("external_status", sa.String(50)),
        sa.Column("project_key", sa.String(50)),
        sa.Column("assignee", sa.String(255)),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_by_rule", sa.String(200)),
        sa.Column("detected_at", sa.DateTime(timezone=True)),
        sa.Column("ticket_created_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "external_ticket_id", "provider", name="uq_ticket_external"),
    )
    op.create_table(
        "ticket_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("is_enabled", sa.Boolean, server_default="true"),
        sa.Column("conditions", postgresql.JSONB, nullable=False),
        sa.Column("action", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("ticket_rules")
    op.drop_table("tickets")
    op.drop_table("sync_logs")
    op.drop_table("connector_configs")
    op.drop_table("vulnerability_correlations")
    op.drop_index("idx_vuln_last_seen", table_name="vulnerabilities")
    op.drop_index("idx_vuln_asset", table_name="vulnerabilities")
    op.drop_index("idx_vuln_source", table_name="vulnerabilities")
    op.drop_index("idx_vuln_status", table_name="vulnerabilities")
    op.drop_index("idx_vuln_cve", table_name="vulnerabilities")
    op.drop_index("idx_vuln_tenant_severity", table_name="vulnerabilities")
    op.drop_table("vulnerabilities")
    op.drop_table("assets")
    op.drop_table("users")
    op.drop_table("tenants")
