"""Add per-tenant EXPO-06 calibration config columns to tenants.

Phase 32 Plan 02 — EXPO-06. `exposure_criticality_cap` is the tenant-
configurable proportion (default 0.15 / 15%) of auto-classified CRITICAL
assets above which `check_criticality_calibration` reports `over_cap`.
`exposure_hard_cap_enabled` is a documented, deliberately unwired flag —
default OFF (flag+report only, per 32-CONTEXT.md's EXPO-06 decision: silently
down-ranking a genuinely critical asset is worse than flagging).

Mirrors 037_add_exposure_context's shape: plain scalar columns with
`server_default` (not just a Python-side `default`) so existing tenant rows
backfill without a data migration.

Revision id kept <= 32 chars: alembic_version.version_num is varchar(32).
"038_add_exposure_cal_cfg" is 24 chars — safe.
"""

import sqlalchemy as sa

from alembic import op

revision = "038_add_exposure_cal_cfg"
down_revision = "037_add_exposure_context"


def upgrade() -> None:
    op.add_column(
        "tenants", sa.Column("exposure_criticality_cap", sa.Float(), server_default="0.15", nullable=False)
    )
    op.add_column(
        "tenants", sa.Column("exposure_hard_cap_enabled", sa.Boolean(), server_default="false", nullable=False)
    )


def downgrade() -> None:
    op.drop_column("tenants", "exposure_hard_cap_enabled")
    op.drop_column("tenants", "exposure_criticality_cap")
