"""Add exceptions table (Phase 39 Plan 01 -- EXC-01/EXC-02/EXC-03/EXC-04
tracer slice).

An `exceptions` row is a governed false-positive / accepted-risk record:
justification + a named approver + an explicit CVE x scope + a mandatory
future expiry (D-06). It is the exclusion SOURCE OF TRUTH (D-01) -- exclusion
itself is a compute-on-read join (`app/exceptions/service.py::
active_exception_subquery`), so this table never mutates
`vulnerabilities.status`.

D-12 (LOCKED): deliberately NO partial-unique index -- unlike campaigns'
`uq_campaign_active_remediation`, multiple simultaneously-ACTIVE exceptions
covering the same finding/scope are explicitly permitted (OR-exclusion
semantics; latest expiry governs resurface). That piece of the 049
campaigns migration analog does NOT transfer here.

Pitfall 2: `ix_exceptions_not_revoked`'s partial-index predicate is a pure
`revoked_at IS NULL` NULL-check -- `now()` is STABLE, not IMMUTABLE, so it
can never appear in a partial-index predicate; `expires_at > :now` stays a
plain runtime WHERE clause backed by the ordinary (non-partial)
`ix_exceptions_expires_at` index instead.

Standalone migration chained off 049_add_campaigns (the current head,
confirmed via `ls backend/alembic/versions | sort | tail`).

Revision id kept <= 32 chars: alembic_version.version_num is varchar(32).
"050_add_exceptions" is 19 chars -- safe.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "050_add_exceptions"
down_revision = "049_add_campaigns"


def upgrade() -> None:
    op.create_table(
        "exceptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("scope_type", sa.String(20), nullable=False),
        sa.Column("cve_id", sa.String(20), nullable=False),
        sa.Column(
            "vulnerability_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vulnerabilities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assets.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "asset_group_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("asset_groups.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column(
            "approver_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "granted_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "revoked_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("resurfaced_audited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_exceptions_tenant_id", "exceptions", ["tenant_id"])
    op.create_index("ix_exceptions_vulnerability_id", "exceptions", ["vulnerability_id"])
    op.create_index("ix_exceptions_asset_scope", "exceptions", ["tenant_id", "asset_id"])
    op.create_index("ix_exceptions_group_scope", "exceptions", ["tenant_id", "asset_group_id"])
    op.create_index("ix_exceptions_cve", "exceptions", ["tenant_id", "cve_id"])
    op.create_index("ix_exceptions_expires_at", "exceptions", ["expires_at"])
    op.create_index(
        "ix_exceptions_not_revoked",
        "exceptions",
        ["tenant_id"],
        postgresql_where=sa.text("revoked_at IS NULL"),  # pure NULL check -- no volatile fn (Pitfall 2)
    )


def downgrade() -> None:
    op.drop_index("ix_exceptions_not_revoked", table_name="exceptions")
    op.drop_index("ix_exceptions_expires_at", table_name="exceptions")
    op.drop_index("ix_exceptions_cve", table_name="exceptions")
    op.drop_index("ix_exceptions_group_scope", table_name="exceptions")
    op.drop_index("ix_exceptions_asset_scope", table_name="exceptions")
    op.drop_index("ix_exceptions_vulnerability_id", table_name="exceptions")
    op.drop_index("ix_exceptions_tenant_id", table_name="exceptions")
    op.drop_table("exceptions")
