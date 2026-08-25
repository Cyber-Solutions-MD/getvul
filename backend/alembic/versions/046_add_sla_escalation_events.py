"""Add sla_escalation_events table (Phase 36 Plan 02 -- SLA-03, D-07).

The durable once-only escalation-fire gate AND the user-visible, auditable
escalation history: one row per (tenant, vulnerability, to_state, channel)
EVER fired. `UniqueConstraint(tenant_id, vulnerability_id, to_state,
channel)` is both the identity key and the correctness backstop for
"exactly once per transition" (36-RESEARCH.md Pattern 2, mirrors
`RiskExposureBackfillJob.uq_risk_backfill_job_tenant`,
044_add_risk_backfill_job.py). `delivery_status`/`error_message` capture a
channel POST's outcome per row (Pattern 1 -- a failed send is recorded here,
never raised).

This migration lands the table shape only -- the transition-detection +
firing loop that actually INSERTs a row is Plan 03's job. Per the Task 1
reversibility-gate decision (option-a, selected over combining both new
Phase 36 tables into one migration): this is a STANDALONE migration for the
escalation-event table. The sibling `remediation_events` table (D-09 /
SLA-04) gets its OWN separate migration in Plan 04, chained off this one --
not combined here, so each plan owns its own schema change with a smaller
blast radius per migration.

Reversibility: one-way in practice (36-CONTEXT.md D-07) -- `downgrade()` is
provided for symmetry/local dev rollback, but running it in a deployed
environment discards escalation history and the once-only gate along with
it.

Revision id kept <= 32 chars: alembic_version.version_num is varchar(32).
"046_add_sla_escalation_events" is 29 chars -- safe.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "046_add_sla_escalation_events"
down_revision = "045_add_seen_by_sources_gin"


def upgrade() -> None:
    op.create_table(
        "sla_escalation_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "vulnerability_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vulnerabilities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_state", sa.String(20), nullable=False),
        sa.Column("to_state", sa.String(20), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("fired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivery_status", sa.String(20), nullable=False, server_default="sent"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "vulnerability_id", "to_state", "channel", name="uq_escalation_once"),
    )
    op.create_index("ix_sla_escalation_events_tenant_id", "sla_escalation_events", ["tenant_id"])
    op.create_index("ix_sla_escalation_events_vulnerability_id", "sla_escalation_events", ["vulnerability_id"])


def downgrade() -> None:
    op.drop_index("ix_sla_escalation_events_vulnerability_id", table_name="sla_escalation_events")
    op.drop_index("ix_sla_escalation_events_tenant_id", table_name="sla_escalation_events")
    op.drop_table("sla_escalation_events")
