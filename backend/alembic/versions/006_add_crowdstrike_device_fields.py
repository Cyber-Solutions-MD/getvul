"""006 - Add CrowdStrike device enrichment fields to assets.

Adds: last_login_user, last_login_at, last_seen_at, host_status,
      system_manufacturer, external_ip.

Revision ID: 006_add_crowdstrike_device_fields
Revises: 005_add_device_category_jamf
"""

import sqlalchemy as sa

from alembic import op

revision = "006_add_cs_device_fields"
down_revision = "005_add_device_category_jamf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assets", sa.Column("last_login_user", sa.String(300)))
    op.add_column("assets", sa.Column("last_login_at", sa.DateTime(timezone=True)))
    op.add_column("assets", sa.Column("last_seen_at", sa.DateTime(timezone=True)))
    op.add_column("assets", sa.Column("host_status", sa.String(30)))
    op.add_column("assets", sa.Column("system_manufacturer", sa.String(200)))
    op.add_column("assets", sa.Column("external_ip", sa.String(50)))


def downgrade() -> None:
    op.drop_column("assets", "external_ip")
    op.drop_column("assets", "system_manufacturer")
    op.drop_column("assets", "host_status")
    op.drop_column("assets", "last_seen_at")
    op.drop_column("assets", "last_login_at")
    op.drop_column("assets", "last_login_user")
