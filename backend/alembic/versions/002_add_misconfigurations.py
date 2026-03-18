"""002 - Add misconfigurations table for CSPM.

Revision ID: 002_add_misconfigurations
Revises: 001_initial_schema
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002_add_misconfigurations"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "misconfigurations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("rule_id", sa.String(300), nullable=False, index=True),
        sa.Column("rule_name", sa.String(500), nullable=False),
        sa.Column("rule_description", sa.Text),
        sa.Column("category", sa.String(30), nullable=False, index=True),
        sa.Column("severity", sa.String(10), nullable=False, index=True),
        sa.Column("frameworks", postgresql.JSONB, server_default="[]"),
        sa.Column("resource_id", sa.String(500), nullable=False, index=True),
        sa.Column("resource_name", sa.String(300)),
        sa.Column("resource_type", sa.String(100)),
        sa.Column("resource_region", sa.String(50)),
        sa.Column("cloud_provider", sa.String(20)),
        sa.Column("cloud_account_id", sa.String(100)),
        sa.Column("cloud_account_name", sa.String(200)),
        sa.Column("source", sa.String(30), nullable=False, index=True),
        sa.Column("source_finding_id", sa.String(300)),
        sa.Column("remediation_info", sa.Text),
        sa.Column("remediation_url", sa.String(500)),
        sa.Column("status", sa.String(20), server_default="OPEN", index=True),
        sa.Column("first_detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("remediated_at", sa.DateTime(timezone=True)),
        sa.Column("details", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "rule_id", "resource_id", "source", name="uq_misconfig_dedup"),
    )
    op.create_index("idx_misconfig_tenant_severity", "misconfigurations", ["tenant_id", "severity"])
    op.create_index("idx_misconfig_tenant_category", "misconfigurations", ["tenant_id", "category"])
    op.create_index("idx_misconfig_tenant_source", "misconfigurations", ["tenant_id", "source"])


def downgrade() -> None:
    op.drop_index("idx_misconfig_tenant_source", table_name="misconfigurations")
    op.drop_index("idx_misconfig_tenant_category", table_name="misconfigurations")
    op.drop_index("idx_misconfig_tenant_severity", table_name="misconfigurations")
    op.drop_table("misconfigurations")
