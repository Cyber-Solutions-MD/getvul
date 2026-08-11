"""Add per-finding + asset risk-exposure score columns (Phase 33 Plan 01 —
RISK-01/02/06 LEAD TRACER).

Purely additive schema spine for the new deterministic per-finding
risk-exposure model (`app/vulnerabilities/risk_exposure_service.py`). Adds 3
columns to `vulnerabilities` (the per-finding score + breakdown + version)
and 2 columns to `assets` (the shadow MAX-rollup + version — separate from
the existing live `Asset.risk_score` / `risk_score.py` curve, untouched).

All 5 columns are nullable with NO `server_default` — genuinely NULL until
the first post-Phase-33 sync runs `compute_finding_risk_scores`, mirroring
`Asset.internet_facing_detected` (041_add_inet_facing_signal.py). No index:
shadow-only, zero automated consumer this phase (RISK-06), so no query
pattern exists yet to justify one (YAGNI).

Revision id kept <= 32 chars: alembic_version.version_num is varchar(32).
"042_add_risk_exposure_score" is 27 chars — safe.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "042_add_risk_exposure_score"
down_revision = "041_add_inet_facing_signal"


def upgrade() -> None:
    # vulnerabilities first — the finding is primary, the asset column below is the rollup.
    op.add_column("vulnerabilities", sa.Column("risk_exposure_score", sa.Integer(), nullable=True))
    op.add_column("vulnerabilities", sa.Column("risk_exposure_breakdown", postgresql.JSONB(), nullable=True))
    op.add_column("vulnerabilities", sa.Column("risk_model_version", sa.String(20), nullable=True))

    op.add_column("assets", sa.Column("risk_exposure_score", sa.Integer(), nullable=True))
    op.add_column("assets", sa.Column("risk_model_version", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("assets", "risk_model_version")
    op.drop_column("assets", "risk_exposure_score")

    op.drop_column("vulnerabilities", "risk_model_version")
    op.drop_column("vulnerabilities", "risk_exposure_breakdown")
    op.drop_column("vulnerabilities", "risk_exposure_score")
