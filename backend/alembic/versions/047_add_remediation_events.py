"""Add remediation_events table (Phase 36 Plan 04 -- SLA-04, D-09).

Captures MTTR-by-tier durably: a `remediation_events` row is written by the
new `mark_vulnerability_remediated()` helper (app/vulnerabilities/
service.py) on EVERY REMEDIATED transition, at every scattered write site
(36-RESEARCH.md Pitfall 6: vulnerabilities/service.py x2, ticketing/
service.py x2, ticketing/daily_sync.py x3), freezing `tier_at_remediation`
(the final risk tier via `tier_for_score`, severity fallback if the score
was NULL, or "not_tracked" for a scored-but-below-floor finding, D-12) +
`duration_seconds` (first_detected_at -> remediated_at).

Per the Task 1 reversibility-gate decision (option-a, matching Plan 02's
identical Task 1 resolution): this is a STANDALONE migration chained off
046_add_sla_escalation_events -- the sibling `sla_escalation_events` table
(D-07 / SLA-03) already landed in its own migration in Plan 02; this
phase's two new event tables stay independent, each owned by the plan that
needs it.

No UniqueConstraint on this table (unlike sla_escalation_events' once-only
gate) -- correctness here is enforced entirely by routing every REMEDIATED
write through the single `mark_vulnerability_remediated()` helper, not a DB
constraint; a vuln legitimately reaching REMEDIATED exactly once per
remediation lifecycle produces exactly one row via that helper.

Reversibility: one-way in practice (36-CONTEXT.md D-09) -- `downgrade()` is
provided for symmetry/local dev rollback, but running it in a deployed
environment discards MTTR history that Phase 42/43 consume directly.

Revision id kept <= 32 chars: alembic_version.version_num is varchar(32).
"047_add_remediation_events" is 27 chars -- safe.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "047_add_remediation_events"
down_revision = "046_add_sla_escalation_events"


def upgrade() -> None:
    op.create_table(
        "remediation_events",
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
        sa.Column("tier_at_remediation", sa.String(20), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("first_detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("remediated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_remediation_events_tenant_id", "remediation_events", ["tenant_id"])
    op.create_index("ix_remediation_events_vulnerability_id", "remediation_events", ["vulnerability_id"])


def downgrade() -> None:
    op.drop_index("ix_remediation_events_vulnerability_id", table_name="remediation_events")
    op.drop_index("ix_remediation_events_tenant_id", table_name="remediation_events")
    op.drop_table("remediation_events")
