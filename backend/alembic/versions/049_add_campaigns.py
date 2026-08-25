"""Add campaigns table (Phase 38 Plan 01 -- CAMP-01/CAMP-04, D-11 partial unique index).

A `campaigns` row is a thin, persisted identity+lifecycle wrapper around an
existing `Vulnerability.remediation_id` group (D-01/D-02) -- it stores NO
label snapshot and NO progress/percentage/MTTR/member-count column (D-07);
every display value is live-joined off `vulnerabilities`/`remediation_events`
at read time (app/campaigns/service.py).

D-11 (LOCKED, confirmed via this plan's Task 1 reversibility checkpoint):
exactly one ACTIVE campaign per (tenant_id, remediation_id) -- enforced by a
Postgres PARTIAL UNIQUE INDEX (`WHERE closed_at IS NULL`), not a
`UniqueConstraint` (Postgres/SQLAlchemy has no `postgresql_where` on
`UniqueConstraint` -- 38-RESEARCH.md Pitfall 3). Precedent for the
`postgresql_where` mechanic: `020_add_sla_tracking.py:27-32`
(`ix_vuln_sla_due_at`, non-unique there; this migration adds `unique=True`).
A closed campaign's remediation_id is NOT blocked by this index, so
re-launching a campaign after an earlier one closed stays possible (D-13
auto-complete / D-17 manual-close-is-sticky both depend on this).

Reversibility: one-way in practice (38-CONTEXT.md D-11) -- relaxing this
constraint later requires a new migration plus deduplication of any rows
that would then violate a laxer index.

Standalone migration chained off 048_add_clean_scan_streak (the current
head, confirmed via `ls backend/alembic/versions | tail -3` + `alembic
current` at plan/execute time).

Revision id kept <= 32 chars: alembic_version.version_num is varchar(32).
"049_add_campaigns" is 18 chars -- safe.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "049_add_campaigns"
down_revision = "048_add_clean_scan_streak"


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("remediation_id", sa.String(200), nullable=False),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "closed_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("close_trigger", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_campaigns_tenant_id", "campaigns", ["tenant_id"])
    op.create_index("ix_campaigns_remediation_id", "campaigns", ["remediation_id"])
    # D-11: Postgres has no "UNIQUE CONSTRAINT ... WHERE" -- a partial UNIQUE
    # INDEX is the only way to express this (38-RESEARCH.md Pitfall 3).
    op.create_index(
        "uq_campaign_active_remediation",
        "campaigns",
        ["tenant_id", "remediation_id"],
        unique=True,
        postgresql_where=sa.text("closed_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_campaign_active_remediation", table_name="campaigns")
    op.drop_index("ix_campaigns_remediation_id", table_name="campaigns")
    op.drop_index("ix_campaigns_tenant_id", table_name="campaigns")
    op.drop_table("campaigns")
