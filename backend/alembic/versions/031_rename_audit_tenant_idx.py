"""Rename the existing audit_logs composite index to the Phase 24 name.

Phase 24 Plan 03 (D-06): `check_tenant_budget()` needs an index-backed SUM
over `audit_logs` filtered by `tenant_id` + `created_at >= month_start` for
Plan 04's per-call hot path. RESEARCH.md proposed a NEW composite index
`ix_audit_logs_tenant_created` on `(tenant_id, created_at)` — but
`013_add_audit_log.py` already created exactly this index (identical
columns, identical order) when the `audit_logs` table itself was created,
under the name `idx_audit_tenant_created`. A second, identically-shaped
index would be pure duplication: extra disk space and write overhead on
every audit-log insert for zero additional query-planner benefit (Postgres
would simply pick one of the two). This migration RENAMES the existing
index instead — a fast, metadata-only operation (no table/index rebuild,
no downtime) — so the name matches what this phase's docs/artifacts
reference without creating a wasteful duplicate.

NOTE on this file's own (short) name: the originally-planned revision id
`031_add_audit_logs_tenant_created_index` is 39 characters — this repo's
`alembic_version.version_num` column is `varchar(32)` (alembic's own
default; every existing revision id in this repo is <= 32 chars, e.g.
`030_add_connector_health_columns` sits exactly at 32), so that revision id
would raise `StringDataRightTruncationError` on `alembic upgrade head`
(confirmed empirically — the first attempt failed exactly this way, and
Postgres's transactional DDL cleanly rolled back both the bookkeeping
UPDATE and the index rename together, leaving the DB at 030 with no manual
cleanup needed). This file's revision id is shortened to fit.

Revision ID: 031_rename_audit_tenant_idx
Revises: 030_add_connector_health_columns
"""

from alembic import op

revision = "031_rename_audit_tenant_idx"
down_revision = "030_add_connector_health_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER INDEX idx_audit_tenant_created RENAME TO ix_audit_logs_tenant_created")


def downgrade() -> None:
    op.execute("ALTER INDEX ix_audit_logs_tenant_created RENAME TO idx_audit_tenant_created")
