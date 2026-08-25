"""Add clean_scan_streak to vulnerabilities (Phase 37 Plan 01 -- SYNC-02, D-02).

Captures the per-finding "absent from N consecutive clean scanner syncs"
bookkeeping that `mark_vulnerability_remediated()`'s new rescan-verified
auto-close path needs (`app/connectors/sync.py::run_sync`'s SUCCESS-branch
absent-sweep, this same plan). A finding whose `last_seen_at` is not
refreshed by a scanner sync that itself completed SUCCESSfully has its
`clean_scan_streak` incremented; a finding re-detected in the same cycle has
its streak reset to 0. At `clean_scan_streak >= 2` (D-02's fixed threshold)
the finding auto-closes as rescan-verified.

Mirrors `ConnectorConfig.consecutive_failure_count`
(`app/ticketing/models.py:55`) exactly: `Integer`, NOT NULL,
`server_default="0"` so every pre-existing row backfills to a safe default
with no data migration needed.

Standalone migration chained off 047_add_remediation_events (the current
head) -- this phase's only new column, no other schema change bundled in.

Revision id kept <= 32 chars: alembic_version.version_num is varchar(32).
"048_add_clean_scan_streak" is 26 chars -- safe.
"""

import sqlalchemy as sa

from alembic import op

revision = "048_add_clean_scan_streak"
down_revision = "047_add_remediation_events"


def upgrade() -> None:
    op.add_column(
        "vulnerabilities",
        sa.Column("clean_scan_streak", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("vulnerabilities", "clean_scan_streak")
