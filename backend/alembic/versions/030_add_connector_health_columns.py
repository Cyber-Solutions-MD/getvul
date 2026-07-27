"""Add connector_configs health columns (last_error, consecutive_failure_count).

Phase 23 — REL-06 (D-18/D-19/D-20): storage prerequisites for the connector
health surface. `last_error` holds a sanitized, truncated, secret-redacted
error string (populated by Plan 07's sync-harness capture logic — this
migration only adds the empty column). `consecutive_failure_count` tracks
"failed N times in a row" so the UI can distinguish a blip from a persistent
outage; incremented on failure / reset on success by the sync harness.

`server_default="0"` backfills every existing row's counter atomically in
the same ALTER (D-20) — no separate UPDATE needed. `last_error` is nullable
with no default (NULL for both existing rows and healthy connectors).

Revision ID: 030_add_connector_health_columns
Revises: 029_add_must_change_password
"""

import sqlalchemy as sa

from alembic import op

revision = "030_add_connector_health_columns"
down_revision = "029_add_must_change_password"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("connector_configs", sa.Column("last_error", sa.Text(), nullable=True))
    op.add_column(
        "connector_configs",
        sa.Column("consecutive_failure_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("connector_configs", "consecutive_failure_count")
    op.drop_column("connector_configs", "last_error")
