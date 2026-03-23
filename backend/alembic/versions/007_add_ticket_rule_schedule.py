"""007 - Add schedule fields to ticket_rules.

Revision ID: 007_ticket_rule_schedule
Revises: 006_add_cs_device_fields
"""

import sqlalchemy as sa

from alembic import op

revision = "007_ticket_rule_schedule"
down_revision = "006_add_cs_device_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ticket_rules", sa.Column("schedule_minutes", sa.Integer(), server_default="1440"))
    op.add_column("ticket_rules", sa.Column("last_run_at", sa.DateTime(timezone=True)))
    op.add_column("ticket_rules", sa.Column("last_run_status", sa.String(20)))
    op.add_column("ticket_rules", sa.Column("last_run_tickets_created", sa.Integer()))


def downgrade() -> None:
    op.drop_column("ticket_rules", "last_run_tickets_created")
    op.drop_column("ticket_rules", "last_run_status")
    op.drop_column("ticket_rules", "last_run_at")
    op.drop_column("ticket_rules", "schedule_minutes")
