"""Add branding JSONB to tenants."""

revision = "023_add_branding"
down_revision = "022_add_notifications"

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


def upgrade() -> None:
    op.add_column("tenants", sa.Column("branding", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "branding")
