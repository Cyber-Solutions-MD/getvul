"""004 - Add remediation_id, exploit_status_id, cisa_kev fields.

Revision ID: 004_add_remediation_fields
Revises: 003_widen_credentials_column
"""

import sqlalchemy as sa

from alembic import op

revision = "004_add_remediation_fields"
down_revision = "003_widen_credentials_column"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("vulnerabilities", sa.Column("remediation_id", sa.String(200)))
    op.add_column("vulnerabilities", sa.Column("remediation_action", sa.Text))
    op.add_column("vulnerabilities", sa.Column("exploit_status_id", sa.Integer))
    op.add_column("vulnerabilities", sa.Column("exploit_status_name", sa.String(100)))
    op.create_index("idx_vuln_remediation_id", "vulnerabilities", ["remediation_id"])
    op.create_index("idx_vuln_exploit_available", "vulnerabilities", ["tenant_id", "exploit_available"])
    op.create_index("idx_vuln_cisa_kev", "vulnerabilities", ["tenant_id", "cisa_kev"])


def downgrade() -> None:
    op.drop_index("idx_vuln_cisa_kev", table_name="vulnerabilities")
    op.drop_index("idx_vuln_exploit_available", table_name="vulnerabilities")
    op.drop_index("idx_vuln_remediation_id", table_name="vulnerabilities")
    op.drop_column("vulnerabilities", "exploit_status_name")
    op.drop_column("vulnerabilities", "exploit_status_id")
    op.drop_column("vulnerabilities", "remediation_action")
    op.drop_column("vulnerabilities", "remediation_id")
