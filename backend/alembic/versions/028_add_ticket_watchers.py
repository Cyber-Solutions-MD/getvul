"""Add ticket_watchers table.

Phase 13 — D-W-02: local GetVul subscription watchers for tickets.
Composite PK (ticket_id, user_id) enforces idempotency at the DB layer —
no duplicate watch rows possible (T-13-03), backing the idempotent
POST/DELETE /api/v1/tickets/{id}/watch in Plan 03.
Both FKs have CASCADE so watcher rows are cleaned up automatically if the
ticket or user is deleted.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "028_add_ticket_watchers"
down_revision = "027_add_ticket_blocked_sla"


def upgrade() -> None:
    op.create_table(
        "ticket_watchers",
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
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("ticket_id", "user_id"),
    )


def downgrade() -> None:
    op.drop_table("ticket_watchers")
