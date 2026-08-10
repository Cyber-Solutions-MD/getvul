"""Add Asset.internet_facing_detected (Phase 32 Plan 04 — EXPO-02).

Durable, nullable raw-provenance column capturing a REAL per-connector
internet-facing/public-exposure signal, mirroring `external_ip`'s shape
(models.py — no `server_default`, `None` until a vendor signal arrives).
`app/assets/exposure.py::infer_exposure_context` prefers this detected
signal over the Plan 02 `external_ip`/tag proxy when it is not None; an
ASSET_OVERRIDE/GROUP_OVERRIDE on `internet_facing` still permanently wins
over both (EXPO-03/04 unchanged).

Revision id kept <= 32 chars: alembic_version.version_num is varchar(32).
"041_add_inet_facing_signal" is 27 chars — safe.
"""

import sqlalchemy as sa

from alembic import op

revision = "041_add_inet_facing_signal"
down_revision = "040_add_group_exposure_ovr"


def upgrade() -> None:
    op.add_column("assets", sa.Column("internet_facing_detected", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("assets", "internet_facing_detected")
