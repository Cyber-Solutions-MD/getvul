"""029 - Add users.must_change_password (forced first-login rotation).

Phase 06 — PROD-06-01: persistence layer for forced default-admin password
rotation. Adds a boolean flag on users that Waves 2-3 read to gate every
authenticated request behind a mandatory password change.

Boolean, NOT NULL, server_default false so every existing row gets a concrete
false (T-06-01-02: no NULL-bypass of the enforcement gate). The seed
(create_admin.py) sets it true on the OWNER admin so the shipped
admin@getvul.local / Admin123! default cannot be used past first login.

Revision ID: 029_add_must_change_password
Revises: 028_add_ticket_watchers
"""

import sqlalchemy as sa

from alembic import op

revision = "029_add_must_change_password"
down_revision = "028_add_ticket_watchers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("must_change_password", sa.Boolean(), server_default="false", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "must_change_password")
