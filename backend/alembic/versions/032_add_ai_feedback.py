"""Add ai_feedback table.

Phase 24 Plan 07 -- D-21/D-22: capture-only analyst feedback (thumbs +
optional correction note) on an AI explanation. tenant_id is an explicit
column (not resolved via a join) so every query is directly tenant-scoped
(T-24-28). Composite UNIQUE on (resource_type, resource_id, user_id) is the
D-22 upsert target: a second submission for the same (resource, user)
UPDATES this row via ON CONFLICT DO UPDATE rather than inserting a
duplicate -- so an analyst can change their own verdict.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "032_add_ai_feedback"
down_revision = "031_rename_audit_tenant_idx"


def upgrade() -> None:
    op.create_table(
        "ai_feedback",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("resource_type", sa.String(20), nullable=False),
        sa.Column("resource_id", sa.String(200), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("verdict", sa.String(8), nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("resource_type", "resource_id", "user_id", name="uq_ai_feedback_resource_user"),
    )
    op.create_index("ix_ai_feedback_tenant", "ai_feedback", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_feedback_tenant", table_name="ai_feedback")
    op.drop_table("ai_feedback")
