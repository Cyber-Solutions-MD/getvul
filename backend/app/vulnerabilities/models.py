"""Vulnerability and Correlation SQLAlchemy models."""

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Severity(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class VulnStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    REMEDIATED = "REMEDIATED"
    SUPPRESSED = "SUPPRESSED"
    FALSE_POSITIVE = "FALSE_POSITIVE"


class VulnSource(str, enum.Enum):
    CROWDSTRIKE = "CROWDSTRIKE"
    NESSUS = "NESSUS"
    DEFENDER = "DEFENDER"
    WIZ = "WIZ"
    QUALYS = "QUALYS"
    RAPID7 = "RAPID7"


class Confidence(str, enum.Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Vulnerability(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "vulnerabilities"
    __table_args__ = (UniqueConstraint("tenant_id", "cve_id", "asset_id", "source", name="uq_vuln_dedup"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    cve_id: Mapped[str | None] = mapped_column(String(20), index=True)
    vulnerability_name: Mapped[str | None] = mapped_column(String(500))
    cvss_v3_score: Mapped[Decimal | None] = mapped_column(Numeric(3, 1))
    cvss_v3_vector: Mapped[str | None] = mapped_column(String(100))
    severity: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    epss_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    epss_percentile: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    exploit_available: Mapped[bool] = mapped_column(Boolean, default=False)
    cisa_kev: Mapped[bool] = mapped_column(Boolean, default=False)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id", ondelete="SET NULL"), index=True
    )
    source: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    source_vuln_id: Mapped[str | None] = mapped_column(String(200))
    source_scan_id: Mapped[str | None] = mapped_column(String(200))
    affected_product: Mapped[str | None] = mapped_column(String(300))
    affected_version: Mapped[str | None] = mapped_column(String(100))
    fixed_version: Mapped[str | None] = mapped_column(String(100))
    remediation_id: Mapped[str | None] = mapped_column(String(200), index=True)
    remediation_action: Mapped[str | None] = mapped_column(Text)
    exploit_status_id: Mapped[int | None] = mapped_column(Integer)
    exploit_status_name: Mapped[str | None] = mapped_column(String(100))
    # ENRICH-03/D-05 (Phase 31 Plan 01): generic vendor-native composite pair --
    # raw value/label verbatim, no cross-scale normalization (that's Phase 33).
    # Nullable: 2 of 6 connectors (Defender, Wiz) have no vendor-authored
    # composite and leave these explicitly None (31-RESEARCH.md Pitfall 6).
    native_priority_score: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    native_priority_rating: Mapped[str | None] = mapped_column(String(50))
    remediation_info: Mapped[str | None] = mapped_column(Text)
    file_paths: Mapped[dict | None] = mapped_column(JSONB)  # ["path1", "path2"]
    # ENRICH-04/D-07/D-08: curated per-connector allowlist, raw vendor field
    # names as keys. Omission = missing (vendor never returned it); a key
    # present with a falsy value = negative (vendor returned it falsy).
    # Mirrors Asset.mdm_details (assets/models.py:67).
    source_signals: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=dict)
    # RISK-01/02/06 (Phase 33): the normalized per-finding score this file's
    # own native_priority_score comment (above) promised. Shadow-computed
    # only -- see risk_exposure_service.py. Nullable, no server_default:
    # None until the first post-Phase-33 sync runs
    # compute_finding_risk_scores. Zero automated consumer reads these in
    # Phase 33 (RISK-06) -- the only reader is the GET /{vuln_id} display.
    risk_exposure_score: Mapped[int | None] = mapped_column(Integer)
    risk_exposure_breakdown: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    risk_model_version: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default=VulnStatus.OPEN.value, index=True)
    # SYNC-02/D-02 (Phase 37 Plan 01): consecutive clean-scan counter, mirrors
    # ConnectorConfig.consecutive_failure_count (ticketing/models.py:55).
    # Incremented by run_sync's SUCCESS-branch absent-sweep when this
    # finding's source completes a successful sync without re-detecting it;
    # reset to 0 on re-detection. At >=2 (fixed threshold) the finding
    # auto-closes as rescan-verified via mark_vulnerability_remediated.
    clean_scan_streak: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    first_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    remediated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sla_breached: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    asset: Mapped["Asset"] = relationship("Asset", back_populates="vulnerabilities")


class VulnerabilityCorrelation(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "vulnerability_correlations"
    __table_args__ = (UniqueConstraint("tenant_id", "cve_id", "asset_id", name="uq_correlation"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    cve_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )
    # Canonical, deduplicated, enum-order-sorted source set (D-01/D-02). GIN-indexed
    # via alembic 034_add_correlation_sources — mirrors assets.tags (025_add_asset_tags.py).
    sources: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    # Linkage-only map {SOURCE: vuln_uuid-as-string} (D-04). No GIN index — not filtered on.
    source_vuln_ids: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    sources_count: Mapped[int] = mapped_column(Integer, default=1)
    confidence: Mapped[str] = mapped_column(String(10), default=Confidence.LOW.value)

    asset: Mapped["Asset"] = relationship("Asset", back_populates="correlations")


class EpssScore(Base, TimestampMixin):
    """Global EPSS reference table (ENRICH-01/ENRICH-05, D-11 signed-off
    exception): CVE-level fact, no tenant_id, cve_id is the primary key
    directly. Refreshed wholesale by the daily scheduler job (a later plan);
    `_upsert_vulnerability` (sync.py) reads it once per ingest via
    `_lookup_enrichment` to snapshot epss_score/epss_percentile onto each
    finding (D-01)."""

    __tablename__ = "epss_scores"

    cve_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    epss_score: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)
    percentile: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(20))
    score_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CisaKev(Base, TimestampMixin):
    """Global CISA KEV catalog reference table (ENRICH-02/ENRICH-05, D-11
    signed-off exception): CVE-level fact, no tenant_id, cve_id is the
    primary key directly. Sole authority for the `Vulnerability.cisa_kev`
    column (D-04) -- a connector's own KEV-ish guess never wins; presence of
    a row (not any column value) determines catalog membership."""

    __tablename__ = "cisa_kev"

    cve_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    date_added: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    vendor_project: Mapped[str | None] = mapped_column(String(50))
    product: Mapped[str | None] = mapped_column(String(200))
    vulnerability_name: Mapped[str | None] = mapped_column(String(200))
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    known_ransomware_campaign_use: Mapped[str | None] = mapped_column(String(10))
    catalog_version: Mapped[str | None] = mapped_column(String(20))


class RiskExposureBackfillJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Phase 34 Plan 01 (RISK-07) — durable, per-tenant, resumable
    historical-recompute job state. Mirrors `AiBatchJob`'s shape
    (`app/ai/models.py:52-90`: Base/mixins, tenant_id FK-CASCADE-index,
    plain String(20) status -- no Python enum, codebase convention) plus a
    `cursor_vuln_id` keyset-resume column `AiBatchJob` doesn't need (that
    job delegates state to Anthropic's own batch API; this job chunks
    within Postgres itself).

    `UniqueConstraint(tenant_id)` -- ONE row per tenant, EVER, updated in
    place every chunk (`cursor_vuln_id`/`rows_migrated`/`last_heartbeat_at`
    advance); this also makes "is tenant X's backfill done" a single
    indexed lookup, which Plan 03's flag-flip gate needs
    (`status == "completed"`).

    Idempotency is NOT this row -- it's the risk_model_version WHERE-guard
    in `risk_backfill_service.process_backfill_chunk`. This row is the
    resumability + throttling + per-tenant-isolation mechanism: `status`
    (pending|in_progress|completed|failed) + `last_heartbeat_at` is the
    claim-row concurrency guard (a stale-or-null heartbeat lets a crashed
    process's job be reclaimed rather than wedging forever); `cursor_vuln_id`
    is an EFFICIENCY optimization only (avoids rescanning an already-done
    prefix), never a correctness requirement.
    """

    __tablename__ = "risk_exposure_backfill_jobs"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_risk_backfill_job_tenant"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending|in_progress|completed|failed
    cursor_vuln_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    rows_migrated: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    rows_total_estimate: Mapped[int | None] = mapped_column(Integer)
    chunk_size: Mapped[int] = mapped_column(Integer, default=500, server_default="500")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)


class SlaEscalationEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Phase 36 Plan 02 (D-07) -- the durable once-only escalation-fire gate
    AND the user-visible, auditable escalation history. One row per
    (tenant, vulnerability, to_state, channel) EVER fired; the
    `UniqueConstraint` below is both the identity key and the correctness
    backstop for "exactly once per transition" (mirrors
    `RiskExposureBackfillJob.uq_risk_backfill_job_tenant` above / 36-RESEARCH
    Pattern 2), even though this project's single-process scheduler has no
    concurrent-writer race today.

    `delivery_status`/`error_message` record a channel POST's outcome per
    row -- a failed send (Pattern 1: caught, never raised) is recorded here,
    not silently dropped.

    This plan defines the table shape + the channel senders
    (`app/notifications/escalation_channels.py`) only. The transition-
    detection + firing loop that actually INSERTs a row -- and the
    `audit()` call that must accompany every fire (D-07) -- is Plan 03's
    job, not this one's.
    """

    __tablename__ = "sla_escalation_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "vulnerability_id", "to_state", "channel", name="uq_escalation_once"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vulnerability_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vulnerabilities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_state: Mapped[str] = mapped_column(String(20), nullable=False)
    to_state: Mapped[str] = mapped_column(String(20), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    fired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    delivery_status: Mapped[str] = mapped_column(String(20), nullable=False, default="sent", server_default="sent")
    error_message: Mapped[str | None] = mapped_column(Text)


class RemediationEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Phase 36 Plan 04 (D-09/SLA-04) -- the durable per-remediation MTTR
    capture row. Written by the single `mark_vulnerability_remediated()`
    helper (`app/vulnerabilities/service.py`) on EVERY REMEDIATED
    transition, across every scattered write site (36-RESEARCH.md Pitfall
    6: vulnerabilities/service.py x2, ticketing/service.py x2, ticketing/
    daily_sync.py x3) -- missing the helper at any one of them silently
    drops MTTR data for that path.

    `tier_at_remediation` freezes the FINAL risk tier at the moment of
    remediation (never tier-at-detection, D-09): `tier_for_score` on the
    frozen `risk_exposure_score` when scored, `severity_to_tier` fallback
    when the score is NULL (D-03), or the literal string "not_tracked" when
    a SCORED finding's tier resolves to None (score < RISK_SCORE_TIER_MEDIUM,
    D-12) -- the row is still written in that case so a below-floor
    finding's remediation isn't silently dropped from the aggregate, it
    just buckets into its own "not_tracked" group rather than a named tier
    (specless SLA-04 probe).

    `duration_seconds` is `remediated_at - first_detected_at`, matching the
    pre-existing flat MTTR queries' definition (service.py's
    `get_dashboard_stats`, dashboard.py, trends.py's `get_mttr_trend`) --
    this table is purely additive per-tier history alongside those, never a
    replacement (Pitfall 11 -- those three queries are untouched by this
    plan).

    No `UniqueConstraint` here (unlike `SlaEscalationEvent.uq_escalation_
    once`) -- the once-only guarantee for THIS table comes from every
    REMEDIATED write routing through the single helper, not a DB
    constraint; a vuln legitimately reaching REMEDIATED exactly once per
    remediation lifecycle produces exactly one row via that helper.
    """

    __tablename__ = "remediation_events"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vulnerability_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vulnerabilities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tier_at_remediation: Mapped[str] = mapped_column(String(20), nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    first_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    remediated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
