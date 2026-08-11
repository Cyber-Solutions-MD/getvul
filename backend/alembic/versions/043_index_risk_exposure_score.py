"""Index Vulnerability.risk_exposure_score (Phase 33 Plan 03 — RISK-02).

Sortability substrate: a btree index on the per-finding score so a finding
list CAN be sorted by "most urgent finding" efficiently. This is PASSIVE
infrastructure only -- no app query references this column this phase
(RISK-06 zero-consumer gate; Phase 34 owns the cutover to an active sort/
SLA/trend/AI consumer). T-33-09: the index itself leaks nothing across
tenants (it is not a query, just a column-ordering structure).

Revision id kept <= 32 chars: alembic_version.version_num is varchar(32).
"043_index_risk_exposure_score" is 29 chars -- safe.
"""

from alembic import op

revision = "043_index_risk_exposure_score"
down_revision = "042_add_risk_exposure_score"


def upgrade() -> None:
    op.create_index("ix_vulnerabilities_risk_exposure_score", "vulnerabilities", ["risk_exposure_score"])


def downgrade() -> None:
    op.drop_index("ix_vulnerabilities_risk_exposure_score", table_name="vulnerabilities")
