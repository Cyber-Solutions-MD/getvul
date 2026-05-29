"""Add tags ARRAY(String) column to assets.

Phase 12 — UX-04-02 requires tag chips inline with hostname on /assets/[id]
and on /assets list rows. Empty default; no backfill required.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

from alembic import op

revision = "025_add_asset_tags"
down_revision = "024_add_containment_status"


def upgrade() -> None:
    op.add_column("assets", sa.Column("tags", ARRAY(sa.String()), nullable=True))
    # GIN index supports future tag-search containment + ILIKE queries
    # (12-RESEARCH-AGENT.md addition #1 — avoid a follow-up migration).
    op.create_index(
        "ix_assets_tags",
        "assets",
        ["tags"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_assets_tags", table_name="assets")
    op.drop_column("assets", "tags")
