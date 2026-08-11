"""Add RiskExposureBackfillJob table + Phase-34 Tenant cutover columns
(Phase 34 Plan 01 — LEAD TRACER, RISK-07/08/09 schema spine).

Lands the FULL Phase-34 schema in one migration so Plans 02 (RISK-08 flag
read), 03 (RISK-09 ack columns + job.status gate), and 04 (RISK-10, flag
read) only ever READ this shape, never re-touch the migration/models:

- `risk_exposure_backfill_jobs` — one durable row per tenant (mirrors
  `AiBatchJob`'s shape, `app/ai/models.py:52-90`), the resumable per-tenant
  chunked-backfill job state. `UniqueConstraint(tenant_id)` — one job per
  tenant, ever, updated in place every chunk.
- `tenants.cutover_risk_exposure_scoring` — the RISK-08 flag (mirrors
  `exposure_hard_cap_enabled`'s exact schema shape, 038_add_exposure_cal_
  cfg.py). Default OFF; UNLIKE `exposure_hard_cap_enabled` this is a REAL
  behavioral branch in every consumer (34-CONTEXT.md locked decision), not
  an inert stub — wired starting Plan 02.
- `tenants.risk_cutover_threshold_ack_at` / `risk_cutover_threshold_ack_
  diff_hash` — the RISK-09 pre/post-diff acknowledgment gate (Plan 03);
  landed here, purely additive, so Plan 03 never needs its own migration.

PURELY ADDITIVE — no raw-SQL row recompute of any kind here (anti-pattern:
never a blocking Alembic data migration; all historical recompute runs via
the scheduler-tick dispatcher in `risk_backfill_service.py`, Task 3).

Revision id kept <= 32 chars: alembic_version.version_num is varchar(32).
"044_add_risk_backfill_job" is 25 chars — safe.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "044_add_risk_backfill_job"
down_revision = "043_index_risk_exposure_score"


def upgrade() -> None:
    op.create_table(
        "risk_exposure_backfill_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("cursor_vuln_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rows_migrated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_total_estimate", sa.Integer(), nullable=True),
        sa.Column("chunk_size", sa.Integer(), nullable=False, server_default="500"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", name="uq_risk_backfill_job_tenant"),
    )
    op.create_index("ix_risk_exposure_backfill_jobs_tenant_id", "risk_exposure_backfill_jobs", ["tenant_id"])

    op.add_column(
        "tenants", sa.Column("cutover_risk_exposure_scoring", sa.Boolean(), server_default="false", nullable=False)
    )
    op.add_column("tenants", sa.Column("risk_cutover_threshold_ack_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tenants", sa.Column("risk_cutover_threshold_ack_diff_hash", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "risk_cutover_threshold_ack_diff_hash")
    op.drop_column("tenants", "risk_cutover_threshold_ack_at")
    op.drop_column("tenants", "cutover_risk_exposure_scoring")

    op.drop_index("ix_risk_exposure_backfill_jobs_tenant_id", table_name="risk_exposure_backfill_jobs")
    op.drop_table("risk_exposure_backfill_jobs")
