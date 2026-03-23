"""003 - Widen credentials_secret_arn to TEXT.

Revision ID: 003_widen_credentials_column
Revises: 002_add_misconfigurations
"""

import sqlalchemy as sa

from alembic import op

revision = "003_widen_credentials_column"
down_revision = "002_add_misconfigurations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "connector_configs",
        "credentials_secret_arn",
        type_=sa.Text(),
        existing_type=sa.String(500),
    )


def downgrade() -> None:
    op.alter_column(
        "connector_configs",
        "credentials_secret_arn",
        type_=sa.String(500),
        existing_type=sa.Text(),
    )
