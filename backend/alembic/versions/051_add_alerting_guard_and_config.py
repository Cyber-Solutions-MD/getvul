"""Add alerting_guard table + Tenant.alerting_config + Tenant.alerting_last_digest_sent_at
(Phase 40 Plan 01 -- ALERT-01/02/03 schema foundation).

Task 1 one-way-door checkpoint (option-a, locked by human decision): a
dedicated `alerting_guard` table -- not bare existence rows -- with a
nullable `fired_at` timestamptz for observability (a cold-start-seeded-but-
not-fired row has `fired_at IS NULL`; D-06) plus
`Tenant.alerting_last_digest_sent_at` as a durable per-tenant digest-send
marker. The durable marker closes Pitfall 4 (40-RESEARCH.md:302-306): an
in-memory send-gate resets on every process restart on this single-VM stack
and would re-send the day's digest.

`alerting_guard` keys on (tenant_id, cve_id, asset_id, trigger_type) per D-05
-- a NEW dedicated table, not a reuse of `sla_escalation_events` (which keys
on vulnerability_id and doesn't match ALERT-01's cve+asset+trigger identity;
see 40-01-PLAN.md interfaces / Open Question 1).

`Tenant.alerting_config` (JSONB) follows the existing sla_config/smtp_config/
syslog_config precedent (tenants/models.py). Its canonical key set is
defined in `app/notifications/alerting_config.py::DEFAULT_ALERTING_CONFIG`,
NOT in this migration. `Tenant.timezone` (existing column) is reused for
D-12 send-hour timing -- no new timezone column is added here.

Standalone migration chained off 050_add_exceptions (the current head,
confirmed via `ls backend/alembic/versions | sort | tail`).

Revision id kept <= 32 chars: alembic_version.version_num is varchar(32).
The natural stem "051_add_alerting_guard_and_config" is 33 chars -- one over
the limit -- so the revision id below is shortened to
"051_add_alerting_guard_config" (29 chars, safe) while the FILE itself keeps
the descriptive name from 40-01-PLAN.md's files_modified list.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "051_add_alerting_guard_config"
down_revision = "050_add_exceptions"


def upgrade() -> None:
    op.create_table(
        "alerting_guard",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("cve_id", sa.String(20), nullable=False),
        sa.Column(
            "asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assets.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("trigger_type", sa.String(10), nullable=False),  # "kev" | "epss"
        sa.Column("fired_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_alerting_guard_tenant_id", "alerting_guard", ["tenant_id"])
    op.create_index("ix_alerting_guard_asset_id", "alerting_guard", ["asset_id"])
    op.create_unique_constraint(
        "uq_alerting_guard_once", "alerting_guard", ["tenant_id", "cve_id", "asset_id", "trigger_type"]
    )
    op.create_index("ix_alerting_guard_slice", "alerting_guard", ["tenant_id", "trigger_type"])

    op.add_column("tenants", sa.Column("alerting_config", postgresql.JSONB(), nullable=True))
    op.add_column("tenants", sa.Column("alerting_last_digest_sent_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "alerting_last_digest_sent_at")
    op.drop_column("tenants", "alerting_config")

    op.drop_index("ix_alerting_guard_slice", table_name="alerting_guard")
    op.drop_constraint("uq_alerting_guard_once", "alerting_guard", type_="unique")
    op.drop_index("ix_alerting_guard_asset_id", table_name="alerting_guard")
    op.drop_index("ix_alerting_guard_tenant_id", table_name="alerting_guard")
    op.drop_table("alerting_guard")
