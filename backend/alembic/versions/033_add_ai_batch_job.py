"""Add ai_batch_jobs table.

Phase 26 Plan 06 -- D-05/D-06 (RESEARCH #2/Pattern 4, T-26-08): the durable
registry for a submitted Anthropic Message Batch. tenant_id is an explicit
column (not resolved via a join), mirroring 032_add_ai_feedback.py. A
Message Batch can legitimately still be in_progress up to 24h later,
spanning a backend restart -- an in-memory dict (like scheduler.py's own
_running_syncs) is provably insufficient, so submitted batches MUST be
persisted here or a restart silently orphans in-flight spend with no way to
retrieve results.

model/prompt_version are frozen at submission time (not recomputed at poll
time) so a completed narrative is always written under the SAME cache key
the submitted requests actually used. custom_id_hash_map (JSONB) maps each
submitted finding_id (the Message Batch custom_id) to its factor-hash,
letting the poller rebuild the exact cache key build_cache_key() would
compute, and letting the GET route's `queued` signal answer "is this
finding in an already-submitted in_progress batch" via a JSONB containment
query (`custom_id_hash_map ? :finding_id`).
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "033_add_ai_batch_job"
down_revision = "032_add_ai_feedback"


def upgrade() -> None:
    op.create_table(
        "ai_batch_jobs",
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
        sa.Column("anthropic_batch_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="in_progress"),
        sa.Column("model", sa.String(50), nullable=False),
        sa.Column("prompt_version", sa.String(64), nullable=False),
        sa.Column("custom_id_hash_map", postgresql.JSONB, nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
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
    )
    op.create_index("ix_ai_batch_jobs_tenant", "ai_batch_jobs", ["tenant_id"])
    op.create_index("ix_ai_batch_jobs_anthropic_batch_id", "ai_batch_jobs", ["anthropic_batch_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_ai_batch_jobs_anthropic_batch_id", table_name="ai_batch_jobs")
    op.drop_index("ix_ai_batch_jobs_tenant", table_name="ai_batch_jobs")
    op.drop_table("ai_batch_jobs")
