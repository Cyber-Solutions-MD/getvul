"""Add AssetGroupExposureOverride table (Phase 32 Plan 03 — EXPO-04).

The group-scope override tier that sits between per-asset ASSET_OVERRIDE and
auto-inference (app/assets/exposure.py::apply_precedence_to_asset /
recompute_exposure_context). One row per (group_id, field); `updated_at` is
the tiebreak key when an asset belongs to multiple groups with conflicting
overrides on the same field — the most-recently-updated override wins
(32-CONTEXT.md, unit-tested).

Revision id kept <= 32 chars: alembic_version.version_num is varchar(32).
"040_add_group_exposure_ovr" is 26 chars — safe.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "040_add_group_exposure_ovr"
down_revision = "039_add_asset_groups"


def upgrade() -> None:
    op.create_table(
        "asset_group_exposure_overrides",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "group_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("asset_groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("field", sa.String(30), nullable=False),
        sa.Column("value", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("group_id", "field", name="uq_group_override_field"),
    )
    op.create_index("ix_asset_group_exposure_overrides_group_id", "asset_group_exposure_overrides", ["group_id"])


def downgrade() -> None:
    op.drop_index("ix_asset_group_exposure_overrides_group_id", table_name="asset_group_exposure_overrides")
    op.drop_table("asset_group_exposure_overrides")
