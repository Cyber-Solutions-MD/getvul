# Phase 31: Connector Enrichment Rewrite - Pattern Map

**Mapped:** 2026-08-05
**Files analyzed:** 18 (2 new migrations, 1 model file w/ 2 new classes, 1 dataclass, 1 write-path, 6 connector parsers, 1 new module, 1 scheduler, 1 bulk-update site, 1 schema, 3 test-file groups)
**Analogs found:** 15 exact/role-match / 18 (2 flagged no-analog, 1 composed-from-multiple)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|-----------------|---------------|
| `backend/alembic/versions/035_add_enrichment_columns.py` (NEW) | migration | batch/transform (DDL, add columns) | `backend/alembic/versions/034_add_correlation_sources.py` | role-match |
| `backend/alembic/versions/036_add_enrichment_ref_tables.py` (NEW) | migration | batch/transform (DDL, create tables) | `backend/alembic/versions/033_add_ai_batch_job.py` | role-match |
| `backend/app/vulnerabilities/models.py` §`Vulnerability` (4 new columns) | model | CRUD | `backend/app/assets/models.py:67` (`mdm_details`) + self (`models.py:56,70-71`) | exact |
| `backend/app/vulnerabilities/models.py` (NEW `EpssScore`/`CisaKev` classes) | model | CRUD / batch | none — first natural-key, non-tenant-scoped tables in codebase (see No Analog Found) | no-analog |
| `backend/app/connectors/base.py` §`NormalizedVulnerability` | model (DTO/dataclass) | transform | self (same file, existing fields) | exact |
| `backend/app/connectors/sync.py` §`_upsert_vulnerability` | service (ingestion write-path) | CRUD (upsert) | self (`sync.py:313-366`, both branches) | exact |
| `backend/app/connectors/crowdstrike.py` §`_normalize_vuln` | service (parser/transform) | transform | self (`crowdstrike.py:295-408`) | exact |
| `backend/app/connectors/nessus.py` §`_normalize_vuln`/`_check_exploit_available` | service (parser/transform) | transform | self (`nessus.py:233-299`) | exact |
| `backend/app/connectors/defender.py` §`_normalize_vuln` | service (parser/transform) | transform | self (`defender.py:192-288`) | exact |
| `backend/app/connectors/wiz.py` §`VULNERABILITY_QUERY` + `fetch_vulnerabilities` | service (parser/transform) | transform | self (`wiz.py:23-65`, `266-294`) | exact |
| `backend/app/connectors/qualys.py` §`_fetch_all_detections` + `_normalize_detection` | service (parser/transform) | transform | self (`qualys.py:190-244`, `555-604`) | exact |
| `backend/app/connectors/rapid7.py` §`fetch_vulnerabilities` | service (parser/transform) | transform | self (`rapid7.py:170-258`) | exact |
| `backend/app/connectors/enrichment_feeds.py` (NEW) | service (external feed fetch+parse+swap) | file-I/O / batch | composed: `defender.py:105-138` (retry loop) + `nessus.py:67-71`/`rapid7.py:67-71`/`wiz.py:169` (httpx client/timeout) + `correlation_service.py:66-77` (pg_insert upsert idiom) | composed (no single analog) |
| `backend/app/connectors/scheduler.py` (`_dispatch_enrichment_refresh` + eager-run in `start_scheduler`) | scheduler/dispatcher | event-driven / batch | self: `_dispatch_ai_batch_prewarm` (`scheduler.py:72-105`) + `_last_ticket_sync` gate block (`scheduler.py:210-223`) + `start_scheduler` (`scheduler.py:263-268`) | exact |
| Bulk re-propagation UPDATE (new function; recommend co-locating in `enrichment_feeds.py`) | service (bulk data maintenance) | batch (`UPDATE … FROM`) | `backend/app/vulnerabilities/sla_service.py:41-61` (`backfill_sla_due_dates`) + call site `router.py:202-213` + scheduler per-tenant loop `scheduler.py:194-208` | role-match |
| `backend/app/vulnerabilities/schemas.py` §`VulnerabilityResponse` | schema (Pydantic) | request-response | self (`schemas.py:15-48`, esp. `exploit_status_id`/`exploit_status_name` precedent at 34-35) | exact |
| `backend/tests/test_connector_normalization.py` (extend, all 6 connectors) | test | n/a | self (`test_connector_normalization.py:83-122`, per-connector unit shape) | exact |
| `backend/tests/test_connectors/test_*_connector.py` (extend all 6 files) | test | n/a | `test_defender_connector.py:32-42` (`_install_mock_transport`) | exact |
| `backend/tests/test_scheduler_enrichment_refresh.py` (NEW) | test | n/a | `backend/tests/test_scheduler_ai_batch.py` (full file, esp. lines 32-89) | exact |

---

## Pattern Assignments

### `backend/alembic/versions/035_add_enrichment_columns.py` (migration, DDL)

**Analog:** `backend/alembic/versions/034_add_correlation_sources.py` (full file, 117 lines)

**Header/docstring + revision chaining pattern** (lines 1-31):
```python
"""Replace hardcoded 4-source FK columns on vulnerability_correlations with a
generalized sources ARRAY(String) + GIN index, plus a source_vuln_ids JSONB
linkage map covering all 6 VulnSource values (Phase 30, CORR-01/02/03).
...
Revision id kept <= 32 chars: alembic_version.version_num is varchar(32)
(empirically confirmed once already -- see 031_rename_audit_tenant_idx.py's
docstring for the StringDataRightTruncationError it hit).
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import ARRAY

from alembic import op

revision = "034_add_correlation_sources"
down_revision = "033_add_ai_batch_job"


def upgrade() -> None:
    op.add_column("vulnerability_correlations", sa.Column("sources", ARRAY(sa.String()), nullable=True))
```

**CRITICAL — revision-id length gotcha (verified this session, not just cited):** `"036_add_enrichment_reference_tables"` is **35 characters** — over the 32-char `alembic_version.version_num` limit and would reproduce the exact `StringDataRightTruncationError` `031_rename_audit_tenant_idx.py` already hit once. Use a shorter id, e.g. `"036_add_enrichment_ref_tables"` (29 chars, verified safe) instead. `"035_add_enrichment_columns"` (26 chars) is already safe.

**Simple `add_column` shape to mirror for the 4 new `vulnerabilities` columns:**
```python
op.add_column("vulnerabilities", sa.Column("epss_percentile", sa.Numeric(5, 4), nullable=True))
op.add_column("vulnerabilities", sa.Column("native_priority_score", sa.Numeric(7, 2), nullable=True))
op.add_column("vulnerabilities", sa.Column("native_priority_rating", sa.String(50), nullable=True))
op.add_column("vulnerabilities", sa.Column("source_signals", postgresql.JSONB, nullable=True))
```
(034's own `op.add_column(..., ARRAY(sa.String()), nullable=True)` at line 35 and `op.add_column(..., postgresql.JSONB, nullable=True)` at line 42 are the exact two column-type idioms needed here — no new idiom required.)

**Index-choice precedent** (034, lines 36-41) — if the planner opts to index `native_priority_score`/`epss_score` for sort (CONTEXT.md flags this as likely-yes, Claude's Discretion):
```python
op.create_index(
    "ix_vulnerability_correlations_sources",
    "vulnerability_correlations",
    ["sources"],
    postgresql_using="gin",
)
```
For a plain sortable numeric column, the simpler `op.create_index("ix_vulnerabilities_native_priority_score", "vulnerabilities", ["native_priority_score"])` (no `postgresql_using="gin"` — that's ARRAY/JSONB-specific) is the right shape; see `034`'s own contrast between the GIN index (line 36-41, for the ARRAY column) and its plain `nullable=True` JSONB add with no index (line 42, `source_vuln_ids` — "no GIN index — not filtered on", per `models.py:96` comment) as the precedent for when NOT to index a JSONB column. `source_signals` should likely follow the same no-index-by-default choice unless a specific `?`-operator query is planned.

**Downgrade symmetry pattern** (034, lines 79-117): every `add_column`/`create_index` in `upgrade()` has a matching `drop_column`/`drop_index` in `downgrade()`, in reverse order.

---

### `backend/alembic/versions/036_add_enrichment_ref_tables.py` (migration, new tables)

**Analog:** `backend/alembic/versions/033_add_ai_batch_job.py` (full file, 74 lines) — this is the only existing migration in the codebase that calls `op.create_table` (034 only adds columns to an existing table).

**Full create_table + index shape to mirror** (lines 31-67):
```python
def upgrade() -> None:
    op.create_table(
        "ai_batch_jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("anthropic_batch_id", sa.String(64), nullable=False),
        ...
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_ai_batch_jobs_tenant", "ai_batch_jobs", ["tenant_id"])
    op.create_index("ix_ai_batch_jobs_anthropic_batch_id", "ai_batch_jobs", ["anthropic_batch_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_ai_batch_jobs_anthropic_batch_id", table_name="ai_batch_jobs")
    op.drop_index("ix_ai_batch_jobs_tenant", table_name="ai_batch_jobs")
    op.drop_table("ai_batch_jobs")
```

**Deliberate deviation to call out in the new migration's docstring** (mirrors 034's own precedent of explaining schema deviations inline, per RESEARCH.md's Security Domain V1 note): `epss_scores`/`cisa_kev` must NOT copy the `id`+`tenant_id`+FK columns above — per D-11 they use `cve_id` (`String(20)`) as the primary key directly, and have no `tenant_id` column at all. Only the `created_at`/`updated_at` `server_default=sa.text("now()")` columns and the `op.create_index(...)` call shape carry over unchanged.

---

### `backend/app/vulnerabilities/models.py` §`Vulnerability` (4 new columns)

**Analog 1 (JSONB shape):** `backend/app/assets/models.py:67`
```python
mdm_details: Mapped[dict | None] = mapped_column(JSONB, default=dict)
```
This is the D-07-cited precedent: sparse dict, `default=dict` (not `nullable=True` alone), same "field present vs absent" semantics for `source_signals`.

**Analog 2 (self — existing numeric/string typed-signal columns to extend), `models.py:53-58,70-71`:**
```python
cvss_v3_score: Mapped[Decimal | None] = mapped_column(Numeric(3, 1))
cvss_v3_vector: Mapped[str | None] = mapped_column(String(100))
severity: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
epss_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
exploit_available: Mapped[bool] = mapped_column(Boolean, default=False)
cisa_kev: Mapped[bool] = mapped_column(Boolean, default=False)
...
exploit_status_id: Mapped[int | None] = mapped_column(Integer)
exploit_status_name: Mapped[str | None] = mapped_column(String(100))
```
`exploit_status_id`/`exploit_status_name` (a CrowdStrike-only int+string pair promoted beyond the boolean) is the direct, already-shipped precedent for the generic `native_priority_score`/`native_priority_rating` pair (D-05) — same "typed column pair sits alongside the boolean" shape, just generalized across all 6 sources instead of being CrowdStrike-specific.

All needed SQLAlchemy types (`Numeric`, `String`, `JSONB`) are **already imported** at the top of this file (`models.py:8-9`) — no new imports required for the 4 new columns.

**Imports already present** (`models.py:1-12`):
```python
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
```

---

### `backend/app/vulnerabilities/models.py` (NEW `EpssScore`/`CisaKev` classes)

**No close analog — see "No Analog Found" section.** Building blocks to recompose (from `backend/app/db/base.py`, full file, 34 lines):
```python
class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
```
Every existing model in the codebase composes `Base, UUIDPrimaryKeyMixin, TimestampMixin` (verified — `Vulnerability`, `Asset`, `VulnerabilityCorrelation`, `AiBatchJob` all do). The new global tables should compose **`Base, TimestampMixin` only** (deliberately skip `UUIDPrimaryKeyMixin` — `cve_id` IS the primary key, per D-11 + RESEARCH's recommended shape). `Base` is a bare `DeclarativeBase` with no hidden tenant_id enforcement (verified directly), so this is a clean, unobstructed departure — no framework fight.

---

### `backend/app/connectors/base.py` §`NormalizedVulnerability`

**Analog:** self — same file, full dataclass (`base.py:9-44`):
```python
@dataclass
class NormalizedVulnerability:
    """Normalized vulnerability finding from any source."""

    cve_id: str | None
    vulnerability_name: str | None
    cvss_v3_score: float | None
    severity: str
    exploit_available: bool = False
    cisa_kev: bool = False
    source_vuln_id: str | None = None
    ...
    file_paths: list[str] | None = None  # Paths where the vulnerable software was detected
```
New fields append to the end of the existing optional-with-default block, matching the file's own style (all fields after `severity` have defaults):
```python
native_priority_score: float | None = None
native_priority_rating: str | None = None
source_signals: dict | None = None
```

---

### `backend/app/connectors/sync.py` §`_upsert_vulnerability`

**Analog:** self — same file, both branches (`sync.py:313-366`):
```python
async def _upsert_vulnerability(
    db: AsyncSession, tenant_id: uuid.UUID, v: NormalizedVulnerability, asset_id: uuid.UUID, source: str
) -> bool:
    now = datetime.now(UTC)
    result = await db.execute(
        select(Vulnerability).where(
            Vulnerability.tenant_id == tenant_id,
            Vulnerability.cve_id == v.cve_id,
            Vulnerability.asset_id == asset_id,
            Vulnerability.source == source,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.last_seen_at = now
        existing.severity = v.severity
        existing.exploit_available = v.exploit_available
        existing.cisa_kev = v.cisa_kev
        existing.remediation_id = getattr(v, "remediation_id", None)
        ...
        return False
    else:
        vuln = Vulnerability(
            tenant_id=tenant_id,
            cve_id=v.cve_id,
            ...
            exploit_available=v.exploit_available,
            cisa_kev=v.cisa_kev,
            asset_id=asset_id,
            source=source,
            ...
            status="OPEN",
            first_detected_at=now,
            last_seen_at=now,
        )
        db.add(vuln)
        await db.flush()
        return True
```
This is the **single choke point** — the `existing.cisa_kev = v.cisa_kev` line (update branch) and `cisa_kev=v.cisa_kev` kwarg (insert branch) are the exact two spots that must be replaced with the ref-table-sourced value per D-04 (the connector's own `v.cisa_kev` guess must NOT win — only `source_signals` gets it, per D-07/D-08). `existing.epss_score`/`epss_score=` do not exist yet in either branch today — this is new, not a replacement.

**Select-then-`scalar_one_or_none()` idiom** (lines 317-325 above) is exactly the shape to reuse for the new EPSS/KEV ref-table lookups (same idiom used everywhere else in this codebase, e.g. `sla_service.py:43`, `correlation_service.py`). No new query idiom is needed.

**`getattr(v, "field", None)` defensive-read idiom** (lines 332, 334-335, 354, 357-358) is the established pattern for "this dataclass attribute may not exist on older call sites / may be None" — mirror this exact idiom for `native_priority_score`/`native_priority_rating`/`source_signals` reads off `v`.

**Imports already in this file** (`sync.py:1-28`) — `select` from `sqlalchemy`, `AsyncSession`, `structlog` logger, and the `Vulnerability` model are all already imported; a ref-table lookup only needs to add `EpssScore`/`CisaKev` to the existing `from app.vulnerabilities.models import Vulnerability` line.

---

### 6 Connector Parsers

Each connector's `_normalize_vuln`/equivalent is a pure-transform function (no DB access — verified via grep, zero `sqlalchemy`/`AsyncSession` imports in any of the 6 files) that builds a `NormalizedVulnerability`. New fields are added at the same call site as the existing `exploit_available=`/`cisa_kev=` kwargs.

#### `backend/app/connectors/crowdstrike.py`

**Analog:** self (`crowdstrike.py:350-408`). Native signal: ExPRT.AI `cve.exprt_rating` — already-fetched, cached in `self._vuln_metadata_cache`, read right next to the existing `exploit_status` read — **zero new API calls**.
```python
# Exploit status from vuln metadata
vuln_id = item.get("id", "")
meta = self._vuln_metadata_cache.get(vuln_id, {})
exploit_status_id = 0
cisa_kev = False

if meta:
    cve_meta = meta.get("cve", {})
    if isinstance(cve_meta, dict):
        exploit_status_id = cve_meta.get("exploit_status", 0) or 0
        # CISA KEV: exploit_status 50 = "Used in the Wild" (CISA KEV level)
        # Also check for explicit CISA KEV flag
        cisa_kev = exploit_status_id >= 50 or bool(cve_meta.get("cisa_kev", False))
...
vuln = NormalizedVulnerability(
    cve_id=cve_id,
    ...
    exploit_available=exploit_available,
    cisa_kev=cisa_kev,
    ...
)
# Attach extra fields via ad-hoc attributes
vuln.remediation_id = remediation_id
vuln.exploit_status_id = exploit_status_id
vuln.exploit_status_name = exploit_status_name
return vuln
```
`cve_meta.get("exprt_rating")` should be read at line 359 right alongside `cve_meta.get("exploit_status", 0)`, and `native_priority_rating`/`native_priority_score` set via the same **"ad-hoc attribute attach after construction"** idiom already used for `remediation_id`/`exploit_status_id` (lines 404-407) rather than as dataclass constructor kwargs — this file's own established idiom for "field computed after the main constructor call."

**PITFALL (verified this session, matches RESEARCH.md Pitfall 3):** module docstring line 11 says `"CISA KEV: derived from exploit_status >= 30"` but the actual code at line 362 checks `>= 50`. Trust the code. Do not "fix" the docstring number into the code (would silently change existing behavior); the docstring itself may be worth a comment-only fix during this phase since D-04 replaces this column's authority anyway, but the `>= 50` threshold value must be preserved verbatim when moved into `source_signals` (it's now provenance-only, not authoritative).

**Imports** (`crowdstrike.py:15-24`, unchanged — no new imports needed for reading `exprt_rating` off an already-cached dict):
```python
from __future__ import annotations

import asyncio

import httpx
import structlog

from app.connectors.base import BaseConnector, NormalizedMisconfiguration, NormalizedVulnerability

logger = structlog.get_logger()
```

#### `backend/app/connectors/nessus.py`

**Analog:** self (`nessus.py:233-299`). No native VPR read exists yet — the file already demonstrates the exact defensive-probe idiom to copy for the new (unverified field-name) VPR read:
```python
def _check_exploit_available(vuln: dict[str, Any]) -> bool:
    """Heuristic check for exploit availability."""
    # Check plugin attributes if present
    attrs = vuln.get("plugin_attributes", {})
    if isinstance(attrs, dict):
        if attrs.get("exploit_available", "") in ("true", True, "1"):
            return True
        if attrs.get("exploitability_ease", "") not in ("", "No known exploits are available"):
            return True
    ...

def _normalize_vuln(
    vuln: dict[str, Any],
    *,
    hostname: str,
    host_ip: str,
    os_name: str,
    os_version: str,
) -> list[NormalizedVulnerability]:
    ...
    exploit_available = _check_exploit_available(vuln)
    ...
    base = dict(
        vulnerability_name=plugin_name,
        cvss_v3_score=cvss3_score,
        severity=severity,
        source_vuln_id=str(plugin_id),
        remediation_info=solution or None,
        ...
        exploit_available=exploit_available,
    )
```
Mirror `_check_exploit_available`'s `attrs = vuln.get("plugin_attributes", {})` defensive dict-probe for VPR (candidates: `attrs.get("vpr_score")`, `attrs.get("vpr")` — see RESEARCH.md Assumptions Log A1) — add the result to the `base` dict alongside `exploit_available=` so it flows into every CVE-fanout `NormalizedVulnerability(cve_id=cve, **base)` call automatically (see lines below the excerpt, where `base` is spread across a per-CVE loop) — this is Nessus's one-emit-per-CVE fanout shape, so putting the new fields in `base` (not per-CVE-specific) is required for correctness.

**Imports** (`nessus.py:1-12`, unchanged):
```python
from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx
import structlog

from app.connectors.base import BaseConnector, NormalizedVulnerability
```

#### `backend/app/connectors/defender.py`

**Analog:** self (`defender.py:192-288`) — the canonical ENRICH-02 proof case (its `cisa_kev=False` hardcode):
```python
def _normalize_vuln(self, record: dict) -> NormalizedVulnerability | None:
    cve_id = record.get("cveId")
    if not cve_id:
        return None
    ...
    # Exploit info
    exploit_available = bool(record.get("exploitVerified") or record.get("publicExploit"))
    ...
    return NormalizedVulnerability(
        cve_id=cve_id,
        vulnerability_name=None,
        cvss_v3_score=cvss_v3_score,
        severity=severity,
        exploit_available=exploit_available,
        cisa_kev=False,
        source_vuln_id=str(record.get("id", "")),
        ...
    )
```
`cisa_kev=False` (the hardcode) **stays exactly as-is in this dataclass field** per D-04 — the fix happens downstream in `_upsert_vulnerability`, not here. What DOES change here: `record.get("exploitVerified")`/`record.get("publicExploit")` (already read, line 257) plus the NOT-yet-read `exploitInKit`/`exploitTypes`/`exploitUris`/native `EPSS` fields must be captured into a `source_signals` dict built inline in this same function (raw dict access, before any `bool()` coercion collapses missing-vs-negative — see Shared Patterns "Tri-state JSONB" below). Per RESEARCH.md Pitfall 6, `native_priority_score`/`native_priority_rating` stay **`None`** for Defender — do not synthesize a composite.

**Imports** (`defender.py:11-20`, unchanged):
```python
from __future__ import annotations

import asyncio

import httpx
import structlog

from app.connectors.base import BaseConnector, NormalizedVulnerability

logger = structlog.get_logger()
```

**Retry-loop pattern also lives in this file** (`defender.py:105-137`, reused as the closest analog for the new feed-fetcher's own retry — see `enrichment_feeds.py` below):
```python
async def _request_with_retry(self, url: str) -> httpx.Response | None:
    """GET with retry on 429 rate limits."""
    for attempt in range(MAX_RETRIES):
        try:
            if url.startswith("https://"):
                resp = await self.client.request("GET", url, headers=self._headers())
            else:
                resp = await self.client.get(url, headers=self._headers())

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", RETRY_BACKOFF))
                logger.warning("defender_rate_limited", retry_after=retry_after, attempt=attempt + 1)
                await asyncio.sleep(retry_after)
                continue
            if resp.status_code == 403:
                logger.warning("defender_forbidden", url=url)
                return None
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError:
            raise
        except Exception as e:
            logger.warning("defender_request_error", url=url, attempt=attempt + 1, error=str(e))
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_BACKOFF)
                continue
            return None
    logger.error("defender_request_exhausted_retries", url=url)
    return None
```

#### `backend/app/connectors/wiz.py`

**Analog:** self (`wiz.py:23-65`, `266-294`). GraphQL query gains new fields; `fetch_vulnerabilities` reads them off each node:
```python
VULNERABILITY_QUERY = """
query VulnerabilityFindings($after: String) {
  vulnerabilityFindings(
    first: 500
    after: $after
    filterBy: { status: [OPEN, IN_PROGRESS] }
  ) {
    nodes {
      id
      name
      CVEDescription
      severity
      score
      exploitAvailable
      hasExploit
      hasCisaKevExploit
      status
      remediation
      ...
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""
...
async def fetch_vulnerabilities(self) -> list[NormalizedVulnerability]:
    nodes = await self._paginate(VULNERABILITY_QUERY, "vulnerabilityFindings")
    results: list[NormalizedVulnerability] = []
    for node in nodes:
        asset = node.get("vulnerableAsset") or {}
        results.append(
            NormalizedVulnerability(
                cve_id=node.get("name"),
                vulnerability_name=node.get("detailedName") or node.get("name"),
                cvss_v3_score=node.get("score"),
                severity=_map_vuln_severity(node.get("severity")),
                exploit_available=bool(node.get("exploitAvailable") or node.get("hasExploit")),
                cisa_kev=bool(node.get("hasCisaKevExploit")),
                source_vuln_id=node.get("id"),
                ...
            )
        )
    return results
```
Add `epssSeverity`/`epssPercentile`/`epssProbability`/`exploitabilityScore`/`impactScore` to the `nodes { ... }` block (after `hasCisaKevExploit`, line 38) and read them off `node` in the loop, into `source_signals`. `native_priority_score`/`native_priority_rating` stay **`None`** for Wiz (same as Defender, per Pitfall 6).

**HIGH-RISK PITFALL (RESEARCH.md Assumption A4, unconfirmed field names):** GraphQL fails the **entire query** on an unknown field name (unlike REST's typical tolerant-of-extra-params behavior) — verify these 5 field names against Wiz's actual schema (introspection or dev portal) before shipping, or wrap in a try/fallback-to-current-query-shape on a GraphQL schema error.

**Imports** (`wiz.py:1-17`, unchanged):
```python
from __future__ import annotations

import asyncio
from typing import Any

import httpx
import structlog

from app.connectors.base import (
    BaseConnector,
    NormalizedMisconfiguration,
    NormalizedVulnerability,
)
```

#### `backend/app/connectors/qualys.py`

**Analog:** self (`qualys.py:190-244` for the fetch-params site, `555-604` for the normalize site) — QDS is a **per-detection** field, not a per-QID KB field (Pitfall 4), so it must NOT be read from `kb_cache`:
```python
async def _fetch_all_detections(self) -> list[dict[str, Any]]:
    ...
    while True:
        params: dict[str, Any] = {
            "action": "list",
            "truncation_limit": 1000,
            "status": "New,Active,Re-Opened",
            "show_igs": 0,
        }
        if id_min > 0:
            params["id_min"] = id_min
        resp = await self._request_with_rate_limit(
            "GET",
            "/api/2.0/fo/asset/host/vm/detection/",
            params=params,
        )
        ...

def _normalize_detection(
    detection: dict[str, Any],
    host: dict[str, Any],
    kb_cache: dict[int, dict[str, Any]],
) -> list[NormalizedVulnerability]:
    """Convert a single Qualys detection into one or more NormalizedVulnerability."""
    qid = _int(detection.get("qid") or detection.get("QID"))
    ...
    kb = kb_cache.get(qid, {})
    vuln_name = str(kb.get("TITLE") or kb.get("title") or f"QID {qid}")
    cvss3 = _kb_cvss3(kb)
    cves = _kb_cves(kb)
    exploit_available = _kb_exploit_available(kb)
    solution = _kb_solution(kb)

    base = dict(
        vulnerability_name=vuln_name,
        cvss_v3_score=cvss3,
        severity=severity,
        source_vuln_id=str(qid),
        remediation_info=solution,
        ...
        exploit_available=exploit_available,
    )
    results: list[NormalizedVulnerability] = []
    if cves:
        for cve in cves:
            results.append(NormalizedVulnerability(cve_id=cve, **base))
    else:
        results.append(NormalizedVulnerability(cve_id=f"QID-{qid}", **base))
    return results
```
Add `"show_qds_factors": 1` to the `params` dict in `_fetch_all_detections` (line ~198-203) and read the QDS value from the **`detection` dict** inside `_normalize_detection` (NOT `kb_cache`/`kb`) — add it to the `base` dict alongside `exploit_available=` so it flows into every per-CVE `NormalizedVulnerability(cve_id=cve, **base)` call, same fanout shape as Nessus.

**Imports** (`qualys.py:1-15`, unchanged):
```python
from __future__ import annotations

import asyncio
import re
import xml.etree.ElementTree as ET
from typing import Any

import httpx
import structlog

from app.connectors.base import BaseConnector, NormalizedVulnerability
```

#### `backend/app/connectors/rapid7.py`

**Analog:** self (`rapid7.py:170-258`) — Risk Score is asset-context-dependent, so it lives on the **AssetVulnerability** association entry (`vuln_entry`), not the vendor-neutral `detail` resource, per Pitfall 5:
```python
async def _fetch_asset_vulns(self, asset_id: int) -> list[dict]:
    return await self._paginate(f"/api/3/assets/{asset_id}/vulnerabilities")

async def _fetch_vuln_detail(self, vuln_id: str) -> dict:
    if vuln_id in self._vuln_detail_cache:
        return self._vuln_detail_cache[vuln_id]
    detail = await self._get_json(f"/api/3/vulnerabilities/{vuln_id}")
    self._vuln_detail_cache[vuln_id] = detail
    return detail
...
            for vuln_entry in asset_vulns:
                vuln_id: str = vuln_entry.get("id", "")
                if not vuln_id:
                    continue

                detail = self._vuln_detail_cache.get(vuln_id, {})
                title = detail.get("title", vuln_id)
                cvss_block = detail.get("cvss", {})
                v3_block = cvss_block.get("v3", {})
                cvss_score: float | None = v3_block.get("score")
                severity = self._severity_from_cvss(cvss_score)
                exploit_count = detail.get("exploits", 0)
                exploit_available = exploit_count > 0 if isinstance(exploit_count, int) else False
                ...
                for cve_id in cves:
                    results.append(
                        NormalizedVulnerability(
                            cve_id=cve_id,
                            vulnerability_name=title,
                            cvss_v3_score=cvss_score,
                            severity=severity,
                            source_vuln_id=vuln_id,
                            ...
                            exploit_available=exploit_available,
                        )
                    )
```
Read `vuln_entry.get("riskScore")` directly (the per-asset-association entry, currently ONLY `vuln_entry.get("id", "")` is extracted at line 213 — everything else is discarded) — NOT off `detail`. `detail` is fetched once per unique `vuln_id` and reused across the per-CVE fanout loop (same shape as Qualys/Nessus); `vuln_entry`'s `riskScore` must be captured **before** entering the inner `for cve_id in cves:` loop so it's available at each `NormalizedVulnerability(...)` construction.

**Imports** (`rapid7.py:1-17`, unchanged):
```python
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.connectors.base import BaseConnector, NormalizedVulnerability

logger = logging.getLogger(__name__)
```

---

### `backend/app/connectors/enrichment_feeds.py` (NEW module)

**No single analog** — this is genuinely new external I/O (verified: zero prior EPSS/KEV code exists anywhere in the codebase). Composes three existing idioms:

**1. httpx client construction with explicit `Timeout` (3 existing precedents, all identical shape) — `nessus.py:67-71`:**
```python
self._client = httpx.AsyncClient(
    ...
    timeout=httpx.Timeout(60.0),
)
```
Same shape at `rapid7.py:67-71` and `wiz.py:169` (`httpx.AsyncClient(timeout=httpx.Timeout(60.0))`). **None of the 3 pass `follow_redirects=True`** — this is new for `enrichment_feeds.py` (required per RESEARCH.md Pitfall 1: the EPSS URL 302-redirects and httpx does not follow redirects by default).

**2. Manual retry-loop (not `tenacity`, despite it being an installed dependency) — `defender.py:105-137`** (full excerpt above, under the Defender connector section) — mirror this shape rather than introducing `tenacity` (verified zero `tenacity` imports anywhere in `app/` today — would be a new, inconsistent pattern for one call site).

**3. Bulk upsert / chunked insert idiom — `backend/app/vulnerabilities/correlation_service.py:66-77`:**
```python
# Upsert on (tenant_id, cve_id, asset_id)
stmt = pg_insert(VulnerabilityCorrelation).values(**values)
stmt = stmt.on_conflict_do_update(
    constraint="uq_correlation",
    set_={
        "sources_count": stmt.excluded.sources_count,
        "confidence": stmt.excluded.confidence,
        "sources": stmt.excluded.sources,
        "source_vuln_ids": stmt.excluded.source_vuln_ids,
    },
)
result = await db.execute(stmt)
```
This is the codebase's existing `sqlalchemy.dialects.postgresql.insert(...).on_conflict_do_update(...)` idiom (3 call sites total: here, `app/api/v1/ai/feedback.py:76-93`, `app/ticketing/router.py:700+`). For the 355k-row EPSS atomic swap specifically, D-09 + the TRUNCATE-then-fresh-insert design means a plain chunked `insert()` (no `on_conflict_do_update` needed — the table is empty post-delete) is simpler; this analog is cited for the **general bulk-write idiom family** in this codebase (parameterized, no hand-rolled SQL string building), not because on-conflict semantics are needed here.

**Structlog logger convention** (used identically in every connector + `scheduler.py` + `sync.py`):
```python
import structlog
logger = structlog.get_logger()
```

---

### `backend/app/connectors/scheduler.py` (`_dispatch_enrichment_refresh` + eager-run)

**Analog:** self — `_dispatch_ai_batch_prewarm` (`scheduler.py:72-105`), the extractable-`async def` + 24h-gate idiom to mirror exactly:
```python
_last_ai_batch_prewarm: datetime | None = None

async def _dispatch_ai_batch_prewarm() -> None:
    """AIP-02/D-05 (RESEARCH Pattern 2): nightly, 24h-gated dispatch...
    Extracted to its own top-level function (rather than inlined directly
    in `_scheduler_loop()`'s body) so it is directly unit-testable via the
    established `from app.connectors import scheduler as scheduler_module;
    await scheduler_module.<fn>(...)` convention
    (test_connector_health.py::test_scheduler_path_failure_parity) --
    `_scheduler_loop()`'s own infinite `while True:` loop cannot be awaited
    to completion in a test.
    """
    global _last_ai_batch_prewarm
    try:
        now = datetime.now(UTC)
        if _last_ai_batch_prewarm is None or (now - _last_ai_batch_prewarm).total_seconds() >= 86400:
            from app.ai.batch import run_batch_prewarm

            asyncio.create_task(run_batch_prewarm())
            _last_ai_batch_prewarm = now
    except Exception as e:
        logger.error("ai_batch_prewarm_dispatch_error", error=str(e))
```

**Second analog — the inline-`await` 24h-gate variant** (`scheduler.py:210-223`, "Daily ticket status sync"), which is the shape to copy INSTEAD of the above for the enrichment refresh specifically (per RESEARCH.md Pattern 2's explicit, reasoned deviation: the atomic-swap transaction must run to completion as one unit before the gate timestamp advances, so `asyncio.create_task`-detaching it would let the gate advance before the swap actually commits):
```python
# Daily ticket status sync (every 24 hours)
global _last_ticket_sync
try:
    now = datetime.now(UTC)
    if _last_ticket_sync is None or (now - _last_ticket_sync).total_seconds() >= 86400:
        async with async_session_factory() as db:
            from app.ticketing.daily_sync import run_daily_ticket_sync

            result = await run_daily_ticket_sync(db)
            if result.get("comments_added", 0) > 0 or result.get("resolved", 0) > 0:
                logger.info("daily_ticket_sync_completed", **result)
        _last_ticket_sync = now
except Exception as e:
    logger.error("daily_ticket_sync_error", error=str(e))
```
New module-level sentinel: `_last_enrichment_refresh: datetime | None = None` (next to `_last_ticket_sync`/`_last_ai_batch_prewarm` at `scheduler.py:20-21`). New dispatcher `_dispatch_enrichment_refresh()` follows the ticket-sync shape (`async with async_session_factory() as db: ... await db.commit()`, gate advances only after the `async with` block completes) — called from `_scheduler_loop()` alongside the other per-tick dispatches (near line 254-255, where `_dispatch_ai_batch_prewarm()`/`_dispatch_ai_batch_poll()` are already awaited inline).

**`start_scheduler` eager-first-run wiring point** (`scheduler.py:263-268`):
```python
def start_scheduler() -> None:
    """Start the background scheduler. Call once at app startup."""
    global _scheduler_task
    if _scheduler_task is None or _scheduler_task.done():
        _scheduler_task = asyncio.create_task(_scheduler_loop())
        logger.info("sync_scheduler_registered")
```
D-10's eager-first-run ("if ref table is empty or stale (>24h), run refresh immediately") needs new logic here — this function currently only starts the loop; it does not check any table state before the loop's first natural tick. The eager check (e.g. `asyncio.create_task(_dispatch_enrichment_refresh())` dispatched immediately, ahead of/alongside `_scheduler_loop()`) is new code with no exact precedent in this function, but composes directly with `_dispatch_enrichment_refresh` itself once that exists (calling it once at startup is just an extra call site).

**Imports already in this file** (`scheduler.py:1-15`, unchanged — new module import added inline, matching the file's existing "import inside the function body" convention seen at lines 100, 122, 175, 186, 199-200, 216, 229, 241):
```python
from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import structlog
from sqlalchemy import select

from app.connectors.sync import run_sync
from app.db.session import async_session_factory
from app.ticketing.models import ConnectorConfig
```

---

### Bulk re-propagation UPDATE (D-01/D-02, new function)

**Analog:** `backend/app/vulnerabilities/sla_service.py:41-61` (`backfill_sla_due_dates`, full function):
```python
async def backfill_sla_due_dates(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    """Set sla_due_at for all open vulns that don't have one yet."""
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    sla_days = get_sla_days(tenant)

    updated = 0
    for severity, days in sla_days.items():
        result = await db.execute(
            update(Vulnerability)
            .where(
                Vulnerability.tenant_id == tenant_id,
                Vulnerability.severity == severity,
                Vulnerability.sla_due_at.is_(None),
                Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
                Vulnerability.first_detected_at.isnot(None),
            )
            .values(sla_due_at=Vulnerability.first_detected_at + timedelta(days=days))
        )
        updated += result.rowcount

    return {"backfilled": updated}
```
Note this precedent is **per-tenant** (loops tenants in the scheduler) and uses ORM-level `update(Vulnerability).where(...).values(...)` — not a raw `UPDATE ... FROM` SQL string. The EPSS/KEV re-propagation is explicitly keyed on `cve_id` **joined against the new global `epss_scores`/`cisa_kev` tables** (D-01's literal `UPDATE vulnerabilities … FROM epss_scores WHERE cve_id = …`), which is NOT tenant-scoped and NOT expressible as a simple `.values(sla_due_at=...)` column-to-column-plus-constant assignment — it needs a correlated value from a second table. Recommend `db.execute(text("UPDATE vulnerabilities v SET epss_score = e.epss_score, epss_percentile = e.percentile FROM epss_scores e WHERE v.cve_id = e.cve_id"))` (raw SQL via SQLAlchemy `text()`, since this specific shape has no existing ORM-level analog in this codebase) rather than forcing the ORM `update().values()` shape sla_service.py uses — flag this explicitly as a deliberate deviation from the literal `backfill_sla_due_dates` code shape, while still keeping the **function signature style, docstring style, and `{"key": count}` dict return convention** identical.

**Call-site analog** — `backend/app/vulnerabilities/router.py:202-213`:
```python
@router.post("/sla/backfill")
async def sla_backfill(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
):
    """Backfill SLA due dates for vulns that don't have one."""
    from app.vulnerabilities.sla_service import backfill_sla_due_dates, check_sla_breaches

    result = await backfill_sla_due_dates(db, user.tenant_id)
    breaches = await check_sla_breaches(db, user.tenant_id)
    await db.commit()
    return {**result, **breaches}
```
The EPSS/KEV re-propagation is scheduler-driven only (no manual-trigger HTTP endpoint requirement in CONTEXT.md/RESEARCH.md) — this router analog is cited for the **local-import + commit-after-call** convention, not because a new endpoint is required.

**Scheduler-tick per-tenant loop analog** — `backend/app/connectors/scheduler.py:194-208`:
```python
# SLA breach check (runs every loop — lightweight query)
try:
    async with async_session_factory() as db:
        from sqlalchemy import select as _sel  # noqa: N814

        from app.tenants.models import Tenant as TenantModel
        from app.vulnerabilities.sla_service import backfill_sla_due_dates, check_sla_breaches

        tenants = (await db.execute(_sel(TenantModel).where(TenantModel.is_active.is_(True)))).scalars().all()
        for t in tenants:
            await backfill_sla_due_dates(db, t.id)
            await check_sla_breaches(db, t.id)
        await db.commit()
except Exception as e:
    logger.error("sla_check_error", error=str(e))
```
Since the new re-propagation is **not tenant-scoped** (it updates `vulnerabilities` globally by `cve_id`, matching rows across ALL tenants in one statement), it does NOT need the `for t in tenants:` per-tenant loop this analog shows — call it once, unscoped, inside the `_dispatch_enrichment_refresh` transaction (see scheduler.py section above), immediately after the ref-table swap commits.

---

### `backend/app/vulnerabilities/schemas.py` §`VulnerabilityResponse`

**Analog:** self (`schemas.py:15-48`) — the existing `exploit_status_id`/`exploit_status_name` fields are the direct precedent for "promote a new typed column into the response schema before any scoring model consumes it":
```python
class VulnerabilityResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    cve_id: str | None
    ...
    epss_score: Decimal | None
    exploit_available: bool
    cisa_kev: bool
    ...
    remediation_id: str | None = None
    remediation_action: str | None = None
    exploit_status_id: int | None = None
    exploit_status_name: str | None = None
    remediation_info: str | None
    ...
    model_config = {"from_attributes": True}
```
Add `epss_percentile: Decimal | None = None`, `native_priority_score: Decimal | None = None`, `native_priority_rating: str | None = None`, `source_signals: dict | None = None` following the same `= None`-defaulted trailing-field style already used for `exploit_status_id`/`exploit_status_name`. Per RESEARCH.md Open Question 1: do NOT touch `VulnerabilityFilter.sort` (`schemas.py:98-107`) or add new filter fields this phase — that's Phase 33+ territory (D-06 explicitly defers consumption).

---

### Tests

**Mock-transport convention** — `backend/tests/test_connectors/test_defender_connector.py:32-42` (reused verbatim across all 6 connector test files):
```python
def _install_mock_transport(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    """Force every httpx.AsyncClient constructed during the test to use a MockTransport,
    mirroring test_crowdstrike_connector.py's idiom (Defender builds its client
    inside authenticate(), not __init__)."""
    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)
```
New EPSS/KEV fetch tests in `enrichment_feeds.py`'s test file should use this exact convention (no `respx`/`pytest-httpx` — verified absent from the codebase).

**Scheduler dispatch test convention** — `backend/tests/test_scheduler_ai_batch.py:1-89` (full file is the direct template for `test_scheduler_enrichment_refresh.py`):
```python
from app.connectors import scheduler as scheduler_module


async def test_batch_blocks_are_non_blocking(monkeypatch):
    monkeypatch.setattr(scheduler_module, "_last_ai_batch_prewarm", None)
    ...
    await scheduler_module._dispatch_ai_batch_prewarm()
    ...

async def test_nightly_submit_24h_gated(monkeypatch):
    """A second call immediately after the first must NOT re-dispatch --
    the 24h gate mirrors this file's own `_last_ticket_sync` idiom."""
    monkeypatch.setattr(scheduler_module, "_last_ai_batch_prewarm", None)
    calls: list[None] = []

    async def fake_prewarm(*args, **kwargs):
        calls.append(None)

    monkeypatch.setattr("app.ai.batch.run_batch_prewarm", fake_prewarm)

    await scheduler_module._dispatch_ai_batch_prewarm()
    await asyncio.sleep(0)  # let the created task actually run
    assert len(calls) == 1
    assert scheduler_module._last_ai_batch_prewarm is not None

    await scheduler_module._dispatch_ai_batch_prewarm()
    await asyncio.sleep(0)
    assert len(calls) == 1  # NOT re-dispatched
```
For `_dispatch_enrichment_refresh` specifically (inline-`await`, not `create_task` — see scheduler.py deviation above), the "non-blocking" test (`test_batch_blocks_are_non_blocking`) does NOT apply the same way; instead mirror `test_nightly_submit_24h_gated`'s **gate-check** shape (call once, assert dispatched + gate advanced; call again immediately, assert NOT re-dispatched) plus a new **atomic-swap-keeps-last-good** test (monkeypatch the fetcher to raise mid-parse, assert the ref table's prior contents are untouched and the gate does NOT advance on failure — this is D-09's core contract and has no existing test-shape precedent to copy, since no prior dispatcher in this file has a "partial failure must not corrupt state" requirement).

**Per-connector unit-test shape** — `backend/tests/test_connector_normalization.py:83-122` (extend with new assertions, one block per connector, following the existing bare-function-call-then-assert style, no DB/session fixture needed since these are pure-transform tests):
```python
def test_nessus_normalize_vuln_maps_severity_and_cves():
    vuln = {
        "plugin_id": 12345,
        "plugin_name": "Some RCE",
        "severity": 4,  # → CRITICAL
        "cvss3_base_score": 9.8,
        "cve": ["CVE-2024-0001", "CVE-2024-0002"],
        "solution": "Patch it",
    }
    out = nessus_normalize(vuln, hostname="host-1", host_ip="10.0.0.1", os_name="Linux", os_version="5.4")
    assert {v.cve_id for v in out} == {"CVE-2024-0001", "CVE-2024-0002"}  # one per CVE
    assert all(v.severity == "CRITICAL" for v in out)
    assert all(v.hostname == "host-1" for v in out)


def test_defender_normalize_vuln_maps_fields():
    conn = DefenderConnector()
    conn._machine_cache = {"m1": {"computerDnsName": "win-box", "ipAddresses": [{"ipAddress": "10.0.0.5"}]}}
    rec = {"cveId": "CVE-2024-1234", "machineId": "m1", "severity": "High", "cvssV3": "7.5"}
    v = conn._normalize_vuln(rec)
    assert v is not None
    assert v.cve_id == "CVE-2024-1234"
```
**SC#4 fixture recommendation (mirrors RESEARCH.md's own recommendation):** anchor the missing-vs-negative fixture on Defender specifically — construct a `rec` dict with `exploitVerified=False` present but no VPR-equivalent key at all, call `conn._normalize_vuln(rec)`, then assert on the returned `source_signals`: `'vpr' not in v.source_signals` (or connector-appropriate equivalent key) AND `v.source_signals['exploit_verified'] is False` in the same test.

---

## Shared Patterns

### Structlog logger initialization
**Source:** every connector file + `sync.py:30` + `scheduler.py:15`
**Apply to:** `enrichment_feeds.py` (new module)
```python
import structlog
logger = structlog.get_logger()
```
(Rapid7 is the one outlier using stdlib `logging.getLogger(__name__)` instead — not the convention to copy for new code.)

### Select-then-`scalar_one_or_none()` idiom
**Source:** `sync.py:317-325`, `sla_service.py:43`, `correlation_service.py`
**Apply to:** the new `_lookup_enrichment`-style helper in `_upsert_vulnerability` (EPSS/KEV ref-table lookup)
```python
result = await db.execute(
    select(Vulnerability).where(
        Vulnerability.tenant_id == tenant_id,
        Vulnerability.cve_id == v.cve_id,
        Vulnerability.asset_id == asset_id,
        Vulnerability.source == source,
    )
)
existing = result.scalar_one_or_none()
```

### Sparse-JSONB "missing vs present-but-falsy" idiom (D-07)
**Source:** `backend/app/assets/models.py:67` (`mdm_details`)
**Apply to:** `source_signals` column + all 6 connectors' allowlist-building code
```python
mdm_details: Mapped[dict | None] = mapped_column(JSONB, default=dict)
```
Build the dict with plain Python — a key is either added (present, even if `False`/`0`) or never added (missing) — never write an explicit `None`/sentinel. Per RESEARCH.md Pitfall 2: read the **raw vendor payload key** (e.g. `node.get("hasCisaKevExploit")` before any `bool()` coercion, or `"hasCisaKevExploit" in node`) when building `source_signals`, never the already-`bool()`-defaulted `NormalizedVulnerability` field — this means allowlist-building code needs the raw dict in scope, i.e. build `source_signals` inline inside `_normalize_vuln`/equivalent, not as post-processing over the finished dataclass.

### Extractable `async def` + 24h-gate dispatched from `_scheduler_loop`
**Source:** `scheduler.py:20-21` (sentinels), `72-105` (`_dispatch_ai_batch_prewarm`), `210-223` (ticket-sync inline-await variant)
**Apply to:** `_dispatch_enrichment_refresh` (new)
- Module-level `datetime | None` sentinel next to `_last_ticket_sync`/`_last_ai_batch_prewarm`.
- Top-level (not nested) `async def`, directly unit-testable via `from app.connectors import scheduler as scheduler_module; await scheduler_module._dispatch_enrichment_refresh()`.
- `try/except Exception as e: logger.error(...)` wrapping the whole body — every dispatcher in this file follows this shape, none let an exception propagate out of the tick.

### Error sanitization before persisting/logging
**Source:** `sync.py:41-59` (`_sanitize_error`)
**Apply to:** the new `feed_refresh_failed` log flag (D-09) — reuse `_sanitize_error`-style truncation/redaction if any upstream response body/exception text is logged, per RESEARCH.md Security Domain V7 (don't leak raw upstream content verbatim).
```python
def _sanitize_error(exc: Exception, cap: int = 500) -> str:
    wrapped = _redact_value({"exception_type": type(exc).__name__, "message": str(exc)})
    message = wrapped["message"] if isinstance(wrapped, dict) else str(exc)
    scrubbed = _SECRET_PATTERN.sub("[REDACTED]", str(message))
    return scrubbed[:cap]
```

### httpx client construction with explicit Timeout
**Source:** `nessus.py:67-71`, `rapid7.py:67-71`, `wiz.py:169`
**Apply to:** `enrichment_feeds.py`'s EPSS/KEV fetch client — but ADD `follow_redirects=True` (none of the 3 existing precedents need it; the EPSS URL does — RESEARCH.md Pitfall 1)
```python
self._client = httpx.AsyncClient(
    timeout=httpx.Timeout(60.0),
)
```

### `pg_insert(...).on_conflict_do_update(...)` bulk-write idiom
**Source:** `correlation_service.py:66-77`, `app/api/v1/ai/feedback.py:76-93`, `app/ticketing/router.py:700+`
**Apply to:** general bulk-write family reference for `enrichment_feeds.py`'s chunked EPSS insert (though the TRUNCATE-first design means plain `insert()` without `on_conflict_do_update` suffices there — no conflicts possible against an empty table).

---

## No Analog Found

Files/patterns with no close match in the codebase (planner should rely on RESEARCH.md's directly-composed recommendations instead):

| File/Pattern | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `EpssScore`/`CisaKev` ORM models (natural-key `cve_id` primary key, no `tenant_id`) | model | CRUD/batch | Every existing model in the codebase (verified: `Vulnerability`, `Asset`, `VulnerabilityCorrelation`, `AiBatchJob`) composes `Base, UUIDPrimaryKeyMixin, TimestampMixin` with a UUID surrogate key + `tenant_id` FK. These 2 tables are the first departure from both conventions (D-11, deliberately signed off). Compose `Base, TimestampMixin` only (skip `UUIDPrimaryKeyMixin`) — see `db/base.py` mixins cited above. |
| `enrichment_feeds.py`'s fetch→parse→atomic-swap→re-propagate pipeline as a whole | service | file-I/O + batch | No prior external-public-feed integration exists in this codebase (verified: zero EPSS/KEV/similar code anywhere). Composed from 3 separate existing idioms (httpx timeout construction, manual retry loop, bulk-insert idiom) — see `enrichment_feeds.py` Pattern Assignment above for the full composition. Treat RESEARCH.md's Pattern 3 code example (`refresh_enrichment_reference_data`) as the authoritative shape since no direct in-repo precedent exists. |
| Eager first-run check inside `start_scheduler()` (D-10) | scheduler | event-driven | `start_scheduler()` today unconditionally starts `_scheduler_loop()` with no pre-loop state check of any kind — this is new logic, though it composes trivially with `_dispatch_enrichment_refresh` once that function exists (just an extra call site). |
| Cross-table raw `UPDATE ... FROM` SQL (D-01 re-propagation) | service | batch | Every existing bulk-update in this codebase (`backfill_sla_due_dates`, `recalculate_sla_due_dates`, `check_sla_breaches`) uses single-table ORM `update(Model).where(...).values(...)` — none join a second table into the `SET` clause. This is a new (small) idiom: raw SQL via SQLAlchemy `text()`, cited directly in RESEARCH.md's Summary/Architecture Diagram as `UPDATE vulnerabilities … FROM epss_scores WHERE cve_id = …`. |

## Metadata

**Analog search scope:** `backend/app/vulnerabilities/`, `backend/app/assets/`, `backend/app/connectors/` (all 6 connector files + `base.py`/`sync.py`/`scheduler.py`), `backend/app/db/`, `backend/alembic/versions/` (all 34 prior migrations, targeted grep + 2 full reads), `backend/tests/` (`test_connector_health.py`, `test_scheduler_ai_batch.py`, `test_connector_normalization.py`, `test_connectors/test_defender_connector.py`)
**Files scanned (read, full or targeted):** 22 — `vulnerabilities/models.py`, `vulnerabilities/schemas.py`, `vulnerabilities/sla_service.py`, `vulnerabilities/router.py` (targeted), `vulnerabilities/correlation_service.py` (targeted), `assets/models.py`, `db/base.py`, `connectors/base.py`, `connectors/sync.py` (targeted), `connectors/scheduler.py`, `connectors/crowdstrike.py` (targeted), `connectors/nessus.py` (targeted), `connectors/defender.py` (targeted), `connectors/wiz.py` (targeted), `connectors/qualys.py` (targeted), `connectors/rapid7.py` (targeted), `alembic/versions/034_add_correlation_sources.py`, `alembic/versions/033_add_ai_batch_job.py`, `tests/test_connector_health.py` (targeted), `tests/test_scheduler_ai_batch.py` (targeted), `tests/test_connector_normalization.py` (targeted), `tests/test_connectors/test_defender_connector.py` (targeted)
**Pattern extraction date:** 2026-08-05
