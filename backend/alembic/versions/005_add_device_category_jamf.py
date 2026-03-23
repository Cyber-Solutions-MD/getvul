"""005 - Add device_category, JAMF fields to assets.

Revision ID: 005_add_device_category_jamf
Revises: 004_add_remediation_fields
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "005_add_device_category_jamf"
down_revision = "004_add_remediation_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "assets", sa.Column("device_category", sa.String(30), comment="WORKSTATION, SERVER, NETWORK, MOBILE, OTHER")
    )
    op.add_column("assets", sa.Column("jamf_id", sa.String(100)))
    op.add_column("assets", sa.Column("serial_number", sa.String(100)))
    op.add_column("assets", sa.Column("model", sa.String(200)))
    op.add_column("assets", sa.Column("department", sa.String(200)))
    op.add_column("assets", sa.Column("building", sa.String(200)))
    op.add_column("assets", sa.Column("assigned_user", sa.String(300)))
    op.add_column(
        "assets", sa.Column("managed_by", sa.String(30), comment="Source that manages this device: JAMF, INTUNE, etc.")
    )
    op.add_column("assets", sa.Column("last_checkin_at", sa.DateTime(timezone=True)))
    op.add_column("assets", sa.Column("mdm_details", postgresql.JSONB, server_default="{}"))
    op.create_index("idx_asset_device_category", "assets", ["tenant_id", "device_category"])
    op.create_index("idx_asset_jamf_id", "assets", ["jamf_id"])


def downgrade() -> None:
    op.drop_index("idx_asset_jamf_id", table_name="assets")
    op.drop_index("idx_asset_device_category", table_name="assets")
    op.drop_column("assets", "mdm_details")
    op.drop_column("assets", "last_checkin_at")
    op.drop_column("assets", "managed_by")
    op.drop_column("assets", "assigned_user")
    op.drop_column("assets", "building")
    op.drop_column("assets", "department")
    op.drop_column("assets", "model")
    op.drop_column("assets", "serial_number")
    op.drop_column("assets", "jamf_id")
    op.drop_column("assets", "device_category")
