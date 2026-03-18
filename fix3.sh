#!/bin/bash
set -euo pipefail

cd ~/Desktop/getvul

echo "🔧 Fixing credentials column size..."

# 1. Update the model to use Text instead of String(500)
sed -i '' 's/credentials_secret_arn: Mapped\[str | None\] = mapped_column(String(500))/credentials_secret_arn: Mapped[str | None] = mapped_column(Text)/' backend/app/ticketing/models.py

# 2. Add Text import if missing
grep -q "from sqlalchemy import.*Text" backend/app/ticketing/models.py || \
  sed -i '' 's/from sqlalchemy import/from sqlalchemy import Text,/' backend/app/ticketing/models.py

# 3. Add a migration to alter the column
cat > backend/alembic/versions/003_widen_credentials_column.py << 'FILEEOF'
"""003 - Widen credentials_secret_arn to TEXT.

Revision ID: 003_widen_credentials_column
Revises: 002_add_misconfigurations
"""

from alembic import op
import sqlalchemy as sa

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
FILEEOF

# 4. Run the migration
docker compose exec -T backend alembic upgrade head

echo "⏳ Waiting (5s)..."
sleep 5

echo "🔍 Testing — try saving your CrowdStrike connector now..."
echo "   http://localhost:3000/dashboard/connectors"
echo ""
echo "✅ Fixed!"
