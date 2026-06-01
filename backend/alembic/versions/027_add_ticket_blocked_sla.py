"""Add blocked, blocked_reason, sla_due_at columns to tickets.

Phase 13 — D-P-02 (blocked/blocked_reason) + D-SLA-01/D-SLA-03 (sla_due_at + backfill + index).

Backfill: each ticket row has a 1:1 FK to vulnerabilities via vulnerability_id,
so per-row sla_due_at = that vuln's sla_due_at. The group MIN across all rows
sharing an external_ticket_url is computed at read-time by list_tickets (Plan 03).
The per-row backfill is correct: MIN over a group where every row = its own vuln's
value equals the soonest due date across linked vulns.

Index ix_tickets_tenant_sla supports efficient SLA-filtered queries on the
tickets list (D-SLA-01).
"""

import sqlalchemy as sa

from alembic import op

revision = "027_add_ticket_blocked_sla"
down_revision = "026_add_ticket_comments"


def upgrade() -> None:
    op.add_column(
        "tickets",
        sa.Column("blocked", sa.Boolean, nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "tickets",
        sa.Column("blocked_reason", sa.Text, nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("sla_due_at", sa.DateTime(timezone=True), nullable=True),
    )
    # D-SLA-03 backfill: each ticket ROW is 1:1 with its vuln (vulnerability_id FK),
    # so per-row value = that vuln's sla_due_at. The group MIN (per external_ticket_url)
    # is then computed at read time in list_tickets (Plan 03).
    op.execute(
        """
        UPDATE tickets t
        SET sla_due_at = v.sla_due_at
        FROM vulnerabilities v
        WHERE t.vulnerability_id = v.id
          AND v.sla_due_at IS NOT NULL
    """
    )
    op.create_index("ix_tickets_tenant_sla", "tickets", ["tenant_id", "sla_due_at"])


def downgrade() -> None:
    op.drop_index("ix_tickets_tenant_sla", table_name="tickets")
    op.drop_column("tickets", "sla_due_at")
    op.drop_column("tickets", "blocked_reason")
    op.drop_column("tickets", "blocked")
