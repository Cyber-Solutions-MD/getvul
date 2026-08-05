"""EPSS/CISA KEV external reference-feed fetch, atomic-swap refresh, and
re-propagation (ENRICH-01/02/05, D-01/D-02/D-09/D-10).

Fetches the two global reference feeds every connector's ingest reads at
`sync.py::_lookup_enrichment` (landed by Phase 31 Plan 01):
  - EPSS (Exploit Prediction Scoring System) -- FIRST.org's daily CSV.
  - CISA KEV (Known Exploited Vulnerabilities) -- CISA's JSON catalog.

D-09 atomic-swap-keeps-last-good contract: `refresh_enrichment_reference_
data` fetches+parses BOTH feeds FULLY IN MEMORY FIRST (`_fetch_and_parse_
epss`/`_fetch_and_parse_kev`, pure fetch+parse, no DB access -- directly
mockable in tests). Only after BOTH succeed does it touch the database
(delete-then-chunked-bulk-insert on `epss_scores`/`cisa_kev`, inside the
CALLER's transaction -- this function never commits itself, so the whole
swap is one atomic unit with whatever the caller does next, e.g.
`repropagate_enrichment`). Any fetch/parse exception aborts BEFORE a single
DB statement is issued -- the prior good reference data is left completely
untouched, and the caller (scheduler.py's `_dispatch_enrichment_refresh`)
must not advance its 24h gate on a `{"status": "failed"}` result.

D-01/D-02: `repropagate_enrichment` re-syncs the now-current ref-table
values onto EVERY existing `vulnerabilities` row keyed on `cve_id` (not
"ingested this run") -- this is what backfills historical findings for
free (no separate one-time migration) and keeps EPSS's daily drift from
leaving previously-ingested findings permanently stale.
"""

from __future__ import annotations

import csv
import gzip
import io
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
import structlog
from sqlalchemy import delete, insert, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.sync import _sanitize_error
from app.vulnerabilities.models import CisaKev, EpssScore

logger = structlog.get_logger()

# [VERIFIED live 2026-08-05, 31-RESEARCH.md] "current" 302-redirects to a
# dated snapshot with an EMPTY body -- httpx.AsyncClient must be built with
# follow_redirects=True (Pitfall 1) or this silently "succeeds" with 0 bytes.
EPSS_URL = "https://epss.empiricalsecurity.com/epss_scores-current.csv.gz"
KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"

# T-31-02/V12 DoS guard: a sanity ceiling applied to BOTH the raw response
# body and the fully decompressed CSV text. The real feed is ~2.5MB
# compressed / a few MB decompressed -- 50MB is generous headroom against a
# malicious/corrupted upstream response without risking unbounded memory
# growth on a single-VM deploy.
_MAX_FEED_BYTES = 50 * 1024 * 1024

# T-31-01/V5: tolerate a tiny fraction of unparseable EPSS rows (e.g. one
# stray corrupted line) without aborting an otherwise-legitimate refresh --
# but a broadly corrupt feed (>1% bad rows) still aborts the whole refresh,
# per D-09's "fetch+parse fully first" contract.
_MAX_MALFORMED_ROW_FRACTION = 0.01

# Stay comfortably under Postgres's ~65535 bound-parameter-per-statement
# limit for the ~355k-row EPSS bulk insert (SQLAlchemy 2.0 insertmanyvalues
# auto-batches within a single execute(), but chunking at the call site
# keeps each individual statement's parameter count bounded and predictable).
_CHUNK_SIZE = 5000


async def _fetch_and_parse_epss() -> list[dict[str, Any]]:
    """Fetch + parse the FIRST.org EPSS CSV feed. Returns row dicts shaped
    for bulk-insert into `EpssScore`. Raises on ANY failure -- never
    returns a partial/degraded result; D-09 requires the caller to treat
    any exception here as "abort, don't touch the DB"."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0), follow_redirects=True) as client:
        resp = await client.get(EPSS_URL)

    # Pitfall 1 belt-and-suspenders: httpx follows the 302 automatically
    # (follow_redirects=True above), but a 3xx is not an "error" status to
    # httpx's own raise_for_status() -- explicitly re-check status/length so
    # a redirect-terminal 200-with-empty-body is treated as a failed fetch,
    # never silently as "0 legitimate rows today".
    if resp.status_code != 200:
        raise ValueError(f"EPSS feed returned unexpected status {resp.status_code}")
    if len(resp.content) == 0:
        raise ValueError("EPSS feed returned an empty body")
    if len(resp.content) > _MAX_FEED_BYTES:
        raise ValueError(f"EPSS feed response exceeds the {_MAX_FEED_BYTES} byte sanity cap")

    decompressed = gzip.decompress(resp.content)
    if len(decompressed) > _MAX_FEED_BYTES:
        raise ValueError(f"EPSS feed decompressed body exceeds the {_MAX_FEED_BYTES} byte sanity cap")

    text_body = decompressed.decode("utf-8")
    # Line 1 is a `#model_version:...,score_date:...` comment, not CSV data
    # -- skip it before csv.DictReader sees the real `cve,epss,percentile`
    # header on line 2.
    comment_line, _, rest = text_body.partition("\n")
    model_version, score_date = _parse_epss_comment(comment_line)

    reader = csv.DictReader(io.StringIO(rest))
    rows: list[dict[str, Any]] = []
    malformed = 0
    total = 0
    for record in reader:
        total += 1
        try:
            rows.append(
                {
                    "cve_id": record["cve"],
                    "epss_score": Decimal(record["epss"]),
                    "percentile": Decimal(record["percentile"]),
                    "model_version": model_version,
                    "score_date": score_date,
                }
            )
        except (KeyError, InvalidOperation, TypeError):
            malformed += 1

    if total == 0:
        raise ValueError("EPSS feed parsed zero data rows")
    if malformed / total > _MAX_MALFORMED_ROW_FRACTION:
        raise ValueError(
            f"EPSS feed had {malformed}/{total} unparseable rows -- exceeds the "
            f"{_MAX_MALFORMED_ROW_FRACTION:.0%} tolerance, aborting refresh (D-09)"
        )

    return rows


def _parse_epss_comment(line: str) -> tuple[str | None, datetime | None]:
    """Best-effort parse of the EPSS CSV's leading `#model_version:...,
    score_date:...` comment line. Metadata only -- never raises; a
    malformed/missing comment line degrades to (None, None). Only the DATA
    rows are load-bearing for D-09, not this bookkeeping metadata."""
    model_version: str | None = None
    score_date: datetime | None = None
    for part in line.lstrip("#").split(","):
        key, _, value = part.partition(":")
        key = key.strip()
        value = value.strip()
        if key == "model_version" and value:
            model_version = value
        elif key == "score_date" and value:
            try:
                score_date = datetime.fromisoformat(value)
            except ValueError:
                score_date = None
    return model_version, score_date


async def _fetch_and_parse_kev() -> list[dict[str, Any]]:
    """Fetch + parse the CISA KEV JSON catalog. Returns row dicts shaped for
    bulk-insert into `CisaKev`. Raises on ANY failure."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0), follow_redirects=True) as client:
        resp = await client.get(KEV_URL)

    if resp.status_code != 200:
        raise ValueError(f"CISA KEV feed returned unexpected status {resp.status_code}")
    if len(resp.content) == 0:
        raise ValueError("CISA KEV feed returned an empty body")
    if len(resp.content) > _MAX_FEED_BYTES:
        raise ValueError(f"CISA KEV feed response exceeds the {_MAX_FEED_BYTES} byte sanity cap")

    payload = resp.json()
    entries = payload.get("vulnerabilities")
    if not isinstance(entries, list) or len(entries) == 0:
        raise ValueError("CISA KEV feed had no vulnerabilities[] entries")

    catalog_version = payload.get("catalogVersion")
    rows: list[dict[str, Any]] = []
    for entry in entries:
        cve_id = entry.get("cveID")
        if not cve_id:
            continue
        rows.append(
            {
                "cve_id": cve_id,
                "date_added": _parse_date_only(entry.get("dateAdded")),
                "vendor_project": entry.get("vendorProject"),
                "product": entry.get("product"),
                "vulnerability_name": entry.get("vulnerabilityName"),
                "due_date": _parse_date_only(entry.get("dueDate")),
                "known_ransomware_campaign_use": entry.get("knownRansomwareCampaignUse"),
                "catalog_version": catalog_version,
            }
        )
    return rows


def _parse_date_only(value: str | None) -> datetime | None:
    """CISA KEV's `dateAdded`/`dueDate` are date-only `YYYY-MM-DD` strings."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).replace(tzinfo=UTC)
    except ValueError:
        return None


def _chunks(rows: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [rows[i : i + size] for i in range(0, len(rows), size)]


async def refresh_enrichment_reference_data(db: AsyncSession) -> dict[str, Any]:
    """D-09 atomic swap: fetch+parse BOTH feeds fully before any DB write.
    Any exception here means the prior good `epss_scores`/`cisa_kev` data is
    left completely untouched -- returns `{"status": "failed", ...}`
    without issuing a single DB statement. On success, delete-then-chunked-
    bulk-insert both tables; does NOT commit (the caller commits, making the
    whole swap one atomic transaction alongside whatever it does next, e.g.
    `repropagate_enrichment`)."""
    try:
        epss_rows = await _fetch_and_parse_epss()
        kev_rows = await _fetch_and_parse_kev()
    except Exception as e:
        logger.error("feed_refresh_failed", error=_sanitize_error(e))
        return {"status": "failed", "error": _sanitize_error(e)}

    await db.execute(delete(EpssScore))
    for chunk in _chunks(epss_rows, _CHUNK_SIZE):
        await db.execute(insert(EpssScore), chunk)

    await db.execute(delete(CisaKev))
    for chunk in _chunks(kev_rows, _CHUNK_SIZE):
        await db.execute(insert(CisaKev), chunk)

    return {"status": "ok", "epss_rows": len(epss_rows), "kev_rows": len(kev_rows)}


async def repropagate_enrichment(db: AsyncSession) -> dict[str, int]:
    """D-01/D-02: recompute EPSS score/percentile + authoritative CISA KEV
    on EVERY existing `vulnerabilities` row, keyed on `cve_id` (not
    "ingested this run") -- this single unconditional statement pair also
    backfills historical findings for free, with no separate one-time
    migration. Unscoped by tenant_id -- these are CVE-level facts shared
    across every tenant's findings (D-11), and the CISA KEV catalog is the
    SOLE authority for the column (D-04): the recompute flips a finding's
    `cisa_kev` both ways (True when its cve_id newly enters the catalog,
    False when it's absent), never just OR-ing in a one-directional flag.
    CR-01: the KEV UPDATE excludes `cve_id IS NULL` rows -- `NULL IN
    (<non-empty subquery>)` evaluates to SQL NULL (not FALSE) per
    three-valued logic, which would otherwise silently corrupt `cisa_kev`
    (both `VulnerabilityResponse`/`VulnerabilitySummary` declare it a
    non-Optional `bool`) for any row lacking a `cve_id` (a state CrowdStrike/
    Wiz can both persist). Those rows simply keep whatever `cisa_kev` value
    they already had."""
    epss_result = await db.execute(
        text(
            "UPDATE vulnerabilities v SET epss_score = e.epss_score, "
            "epss_percentile = e.percentile FROM epss_scores e WHERE v.cve_id = e.cve_id"
        )
    )
    kev_result = await db.execute(
        text("UPDATE vulnerabilities SET cisa_kev = (cve_id IN (SELECT cve_id FROM cisa_kev)) WHERE cve_id IS NOT NULL")
    )
    return {
        "repropagated": epss_result.rowcount or 0,
        "kev_recomputed": kev_result.rowcount or 0,
    }
