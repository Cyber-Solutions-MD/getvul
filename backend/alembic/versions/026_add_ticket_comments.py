"""Add ticket_comments table.

Phase 13 — D-C-02: first-class local audit notes for tickets.
Comments FK to tickets(id) with CASCADE; user_id FK to users(id) with CASCADE.
edited_at column present but UI for edit/delete deferred to a future plan.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "026_add_ticket_comments"
down_revision = "025_add_asset_tags"


def upgrade() -> None:
    op.create_table("ticket_comments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "ticket_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tickets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_ticket_comments_ticket_created",
        "ticket_comments",
        ["ticket_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ticket_comments_ticket_created", table_name="ticket_comments")
    op.drop_table("ticket_comments")
