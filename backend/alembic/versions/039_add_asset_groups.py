"""Add AssetGroup entity + membership table (Phase 32 Plan 03 — EXPO-04).

CONTEXT.md's [USER] decision: a real tenant-scoped AssetGroup entity (not a
tag-containment query). `asset_groups` mirrors ConnectorConfig's
tenant-scoped-entity shape (UUID PK, tenant_id FK CASCADE, unique
(tenant_id, name)); `asset_group_members` mirrors TicketWatcher's
composite-PK membership shape (028_add_ticket_watchers.py).

Revision id kept <= 32 chars: alembic_version.version_num is varchar(32).
"039_add_asset_groups" is 21 chars — safe.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "039_add_asset_groups"
down_revision = "038_add_exposure_cal_cfg"


def upgrade() -> None:
    op.create_table(
        "asset_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("tenant_id", "name", name="uq_asset_group_tenant_name"),
    )
    op.create_index("ix_asset_groups_tenant_id", "asset_groups", ["tenant_id"])

    op.create_table(
        "asset_group_members",
        sa.Column(
            "group_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("asset_groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("group_id", "asset_id"),
    )


def downgrade() -> None:
    op.drop_table("asset_group_members")
    op.drop_index("ix_asset_groups_tenant_id", table_name="asset_groups")
    op.drop_table("asset_groups")
