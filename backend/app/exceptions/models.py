"""ExceptionRecord SQLAlchemy model (Phase 39 Plan 01 --
EXC-01/EXC-02/EXC-03/EXC-04 tracer slice).

Pitfall 10: the Python class MUST be named `ExceptionRecord`, never
`Exception` -- that shadows `builtins.Exception` and would silently break
any `except Exception:` clause in this module or any importer. The table
name `exceptions` is fine; only the Python class name collides.

D-01/D-04: this table is the exclusion SOURCE OF TRUTH; exclusion itself is
a compute-on-read join (`app/exceptions/service.py::active_exception_
subquery`) -- granting/revoking/expiring never flips `Vulnerability.status`.
D-12: deliberately NO partial-unique index here -- unlike
`Campaign.uq_campaign_active_remediation`, overlapping ACTIVE exceptions on
the same finding/scope are explicitly permitted (OR-exclusion semantics).

Analog: `backend/app/campaigns/models.py` (Phase 38) -- same
`Base, UUIDPrimaryKeyMixin, TimestampMixin` base shape, same tenant_id
FK-CASCADE-indexed column, same DB-nullable `ondelete="SET NULL"` user-FK
shape (Pitfall 3, see below).
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ExceptionRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A governed false-positive / accepted-risk exception (EXC-01).

    Scope is always a CVE x target predicate (D-10 -- never a blanket
    whole-target silence):
      - FINDING: pins the exact `vulnerability_id` (the detected row the
        drill panel is anchored on).
      - ASSET: pins `(cve_id, asset_id)` -- any current/future SOURCE
        reporting this CVE on this asset (D-11 live/forward-looking).
      - ASSET_GROUP: pins `(cve_id, asset_group_id)`, resolved live through
        `AssetGroupMember` -- covers current AND future group members
        (D-11), no frozen snapshot table.

    `type`/`scope_type` are plain `String(20)` columns, never a native
    Postgres enum (zero precedent in this codebase -- mirrors
    `VulnStatus`'s `str, enum.Enum` + plain-string-column convention).
    Pydantic's `Literal[...]` enforces the closed set at the API boundary
    (see schemas.py).

    Pitfall 3: `approver_user_id` / `granted_by_user_id` /
    `revoked_by_user_id` are DB-nullable with `ondelete="SET NULL"` even
    though D-08 makes `approver_user_id` APPLICATION-required -- exact
    precedent: `Campaign.created_by_user_id`. A NOT NULL user FK with
    `ondelete="SET NULL"` is a contradiction that only surfaces the first
    time the referenced user row is deleted.

    `resurfaced_audited_at` is the Pattern 4 lazy-on-read expiry-audit
    stamp (RESEARCH Open Question Q2, ADOPTED) -- written by
    `GET /api/v1/exceptions`'s sweep (`service.py::sweep_expired_audits`)
    the first time a naturally-lapsed (unrevoked) exception is observed,
    guarding the one-time `exception.expire` audit write (EXC-03/EXC-04).
    """

    __tablename__ = "exceptions"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False)
    cve_id: Mapped[str] = mapped_column(String(20), nullable=False)
    vulnerability_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vulnerabilities.id", ondelete="SET NULL")
    )
    asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="SET NULL"))
    asset_group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("asset_groups.id", ondelete="SET NULL")
    )
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    approver_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    granted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    # Pattern 4 (lazy-on-read expiry audit, ADOPTED) -- NULL until the
    # first GET /api/v1/exceptions sweep observes this row past its
    # expires_at with no revoke; then stamped `now` in the same write that
    # emits the one-time "exception.expire" audit row.
    resurfaced_audited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
