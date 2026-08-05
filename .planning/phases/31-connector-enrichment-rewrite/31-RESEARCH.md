# Phase 31: Connector Enrichment Rewrite - Research

**Researched:** 2026-08-05
**Domain:** Vulnerability-scanner connector ingestion, external threat-intel feed integration (EPSS/CISA KEV), Postgres bulk-upsert/atomic-swap patterns, in-process asyncio scheduler
**Confidence:** MEDIUM-HIGH (external feed URLs/schemas VERIFIED live; ingestion write-path VERIFIED via direct code read; per-vendor native-signal field names are a mix of VERIFIED/CITED/ASSUMED — see per-connector table)

## Summary

This phase threads six new capabilities through the existing connector pipeline: (1) EPSS score+percentile snapshotted from a new global `epss_scores` table, (2) authoritative CISA KEV status from a new global `cisa_kev` table (replacing every connector's own KEV-ish guess), (3) a generic `native_priority_score`/`native_priority_rating` column pair for vendor-proprietary composite ratings (Nessus VPR, CrowdStrike ExPRT.AI, Qualys QDS, Rapid7 Risk Score), (4) a curated per-connector `source_signals` JSONB allowlist, and (5) a daily scheduler job that refreshes the two new reference tables independent of connector sync cadence. All of this threads through exactly one choke point already in the codebase: `_upsert_vulnerability` in `backend/app/connectors/sync.py:313-367`, which is the single place all 6 connectors' normalized output becomes a `Vulnerability` row.

The most important researched correction to the phase's framing: **not all 6 connectors have a vendor-proprietary composite priority score to promote.** Direct verification of vendor API docs shows CrowdStrike (`cve.exprt_rating`), Qualys (QDS, 1-100), Rapid7 (Risk/Active Risk Score, 0-1000), and Nessus (VPR, 0.1-10.0, confirmed added to Nessus Professional in v10.5.0) each have a genuine composite signal. Microsoft Defender and Wiz do **not** — their APIs expose only granular booleans/sub-scores (`publicExploit`/`exploitVerified`/`exploitInKit`/native `EPSS` for Defender; `epssSeverity`/`epssPercentile`/`exploitabilityScore` for Wiz), no single vendor-authored composite rating. The `native_priority_score`/`native_priority_rating` columns must be nullable (already anticipated as Claude's Discretion in CONTEXT.md) and should be left `NULL` for Defender and Wiz findings — their richer signal belongs in `source_signals` instead. This is not a re-litigation of D-05's column shape, only an evidence-based finding about which connectors can populate it.

The external feeds were verified live today (2026-08-05) by direct download, not just documentation search: EPSS's CSV is reachable at a stable "current" URL that 302-redirects to a dated snapshot (`https://epss.empiricalsecurity.com/epss_scores-current.csv.gz`, currently ~355,000 CVE rows — notably more than the ~200k estimate in CONTEXT.md), and CISA KEV's JSON catalog (`https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json`) currently holds 1,660 entries (also above the ~1.2k estimate). Both schemas, exact parse gotchas, and field-length bounds are documented below from the real downloaded files.

**Primary recommendation:** Add EPSS/KEV lookups to `_upsert_vulnerability` (not to the connectors — connectors have zero DB access today and should stay that way); add `native_priority_score`/`native_priority_rating`/`source_signals` to `NormalizedVulnerability` and populate them per-connector from already-fetched-but-currently-discarded API response fields; implement the daily refresh job as a new extractable `async def` in `scheduler.py` following the exact `_dispatch_ai_batch_prewarm`/24h-gate idiom already proven in this codebase, with a fetch/parse-first, swap-only-on-full-success transaction for D-09's atomic-swap requirement.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| EPSS/KEV feed fetch + parse | API/Backend (scheduler job) | — | New outbound HTTP to public feeds; no UI, no per-tenant logic — a scheduled background task |
| `epss_scores`/`cisa_kev` global ref tables | Database/Storage | — | D-11: deliberately global, no `tenant_id`; CVE-level fact, not tenant-owned data |
| EPSS/KEV snapshot-onto-finding | API/Backend (`_upsert_vulnerability`) | Database/Storage | D-01: single choke point already owns every write to `Vulnerability`; must NOT live inside each connector (connectors have no DB session today) |
| Vendor-native priority signal capture (VPR/ExPRT/QDS/RiskScore) | API/Backend (per-connector parser) | — | Each connector already parses its own vendor payload; the raw field lives only in that payload, nowhere else |
| `source_signals` allowlist population | API/Backend (per-connector parser) | — | Same reasoning — connector-local knowledge of its own raw field names |
| Daily re-propagation UPDATE (D-01/D-02) | API/Backend (scheduler job) | Database/Storage | Bulk `UPDATE...FROM` idiom already established in `sla_service.py`; runs in the scheduler tick, not per-request |
| Sort/filter on new columns | Database/Storage (index only) | — | This phase makes columns *sortable-capable* (typed + indexed); wiring an actual `sort=` API param is Phase 33+ (D-06 defers consumption) |

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**EPSS / KEV data flow**
- **D-01:** EPSS/KEV are snapshotted onto each finding at ingest (connector copies the value from the global ref table into the finding's own `epss_score`/`cisa_kev` columns), **and** the daily job bulk-re-propagates the refreshed ref-table values to existing findings via `UPDATE vulnerabilities … FROM epss_scores WHERE cve_id = …`. Chosen over read-time JOIN and hybrid split. Reversibility: costly.
- **D-02:** The unconditional daily re-propagation UPDATE (keyed on `cve_id`, not "ingested this run") also backfills historical findings for free — no separate one-time historical-backfill migration needed. Reversibility: reversible.
- **D-03:** Add a new `epss_percentile` typed column alongside the existing `epss_score` (`models.py:56`). Reversibility: one-way (additive migration).
- **D-04:** For a finding's `cisa_kev` column, the CISA KEV reference table is the sole authority: `finding.cisa_kev = (cve_id ∈ KEV catalog)`. Every connector's own KEV-ish guess is discarded from the column but preserved in `source_signals` for provenance. Rejected OR-ing catalog with connector guess. Reversibility: costly.

**Vendor exploitability / priority columns (ENRICH-03)**
- **D-05:** Native priority signals land in a generic two-column pair every finding populates — `native_priority_score` (Numeric, raw vendor number) + `native_priority_rating` (String, raw vendor category verbatim). The existing single-valued `source` column disambiguates scale/vocabulary. Chosen over 8-10 sparse vendor-specific columns. Reversibility: one-way (additive migration).
- **D-06:** Cross-scale normalization/weighting is deliberately DEFERRED to Phase 33. This phase captures native values faithfully and raw — no VPR-0-10 vs Rapid7-0-1000 vs ExPRT-categorical mapping. Reversibility: reversible.

**`source_signals` JSONB (ENRICH-04)**
- **D-07:** Omission = missing. Only keys the vendor actually returned are written. Key absent → "missing"; key present with `false`/`0` → "negative". Mirrors `Asset.mdm_details` precedent. Rejected explicit-null-sentinel and `{value, present}` wrapper. Reversibility: costly.
- **D-08:** `source_signals` populated from a curated per-connector allowlist, keyed by the raw vendor field name. Fields already promoted to columns are NOT duplicated. Rejected "dump entire raw record minus promoted". Reversibility: reversible (allowlist easy to extend).

**Daily reference-data refresh job (ENRICH-05)**
- **D-09:** Atomic swap that keeps last-good data: fetch+parse the full feed, only replace ref-table contents on fully-successful fetch+parse; any failure/partial feed leaves previous good data intact and logs/flags the miss (`feed_refresh_failed`). Connector syncs/ingestion NEVER block on the feed. Rejected in-place best-effort upsert. Reversibility: reversible.
- **D-10:** Eager first-run + self-healing daily: on scheduler startup, if ref table is empty or stale (>24h), run refresh immediately. Findings that still ingested null in that window self-heal via D-01's re-propagation. Reversibility: reversible.
- **D-11:** `epss_scores`/`cisa_kev` reference tables are global — no `tenant_id` (deliberate, signed-off exception). Reversibility: one-way (schema shape).

### Claude's Discretion
- Exact new-column nullability/defaults, index choices (e.g. whether `native_priority_score`/`epss_score` get btree indexes for sort — likely yes given RISK-02 intent), Alembic revision chaining, and ref-table PK/index shape (cve_id-keyed).
- Exact external feed endpoints + parse details for EPSS (FIRST.org daily CSV, ~200k CVEs) and CISA KEV (CISA JSON catalog, ~1.2k CVEs) — researcher/planner to pin the authoritative URLs and formats. **(Resolved below — see External Feeds section; actual verified counts are ~355k and 1,660 respectively.)**
- Precise scheduler wiring of the daily job (which extractable `async def` + 24h-gate variable) following the existing `_last_ticket_sync`/snapshot idioms in `scheduler.py`.
- Exact per-connector allowlist field sets (which raw vendor fields each connector routes to `source_signals` vs promotes) — bounded by D-05/D-07/D-08.
- Whether the re-propagation UPDATE (D-01) and eager refresh (D-10) reuse the `backfill_sla_due_dates` bulk-`UPDATE … FROM` + scheduler-tick idiom (encouraged; same family as RISK-07's cited pattern).

### Deferred Ideas (OUT OF SCOPE)
- Cross-scanner normalization/weighting of native priority signals onto a common scale → Phase 33.
- Cross-vendor `native_priority_rating` vocabulary unification → Phase 33.
- Consuming these signals in a risk-exposure score / per-finding score → Phase 33 (define) + Phase 34 (recompute + cutover).
- Source-provenance badges & per-entity source filtering on the new/richer signals → Phase 35.
- Vendor/third-party ML exploit-prediction as an added signal → RISK-11 (v2, future).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ENRICH-01 | EPSS score + percentile captured per finding, populated for every connector | External Feeds (EPSS CSV schema, VERIFIED live); Ingestion Write-Path section — lookup belongs in `_upsert_vulnerability`, not per-connector |
| ENRICH-02 | Real CISA KEV status from an authoritative feed, fixing Defender's `cisa_kev=False` hardcode | External Feeds (KEV JSON schema, VERIFIED live); Common Pitfalls #2 (tri-state missing-vs-negative for connector's own KEV guess going into `source_signals`) |
| ENRICH-03 | Vendor-native exploitability/priority signals in promoted typed columns, sortable/filterable | Per-Connector Native Signal table — 4 of 6 connectors have a genuine composite signal (CrowdStrike ExPRT rating, Nessus VPR, Qualys QDS, Rapid7 Risk Score); Defender/Wiz do not (columns stay null, richer data goes to `source_signals`) |
| ENRICH-04 | Long-tail scanner-native fields in queryable `source_signals` JSONB, missing vs. negative fixture | Per-connector allowlist table; Validation Architecture SC#4 fixture design (Defender `exploitVerified`/`publicExploit` vs absent VPR-equivalent) |
| ENRICH-05 | Global `epss_scores`/`cisa_kev` reference tables refreshed by dedicated daily scheduler job | Scheduler Wiring section — exact `_dispatch_ai_batch_prewarm` idiom to mirror; D-09 atomic-swap transaction pattern; D-10 eager-first-run design |
| ENRICH-06 | All 6 connectors thread native signals through ingestion, never permanently null/inconsistent | Ingestion Write-Path (`NormalizedVulnerability` dataclass + both `_upsert_vulnerability` branches); Per-Connector table covers all 6 explicitly, including the 2 that legitimately stay null |
</phase_requirements>

## Standard Stack

### Core (all already installed — zero new pip dependencies needed)

| Library | Version (verified in `pyproject.toml`) | Purpose | Why Standard |
|---------|------|---------|--------------|
| httpx | `>=0.27` | Fetch EPSS CSV + KEV JSON | Already the sole HTTP client across all 6 connectors; consistent client construction/retry style |
| SQLAlchemy | `>=2.0` (asyncio extra) | New models, bulk upsert, `insertmanyvalues` batching for the 355k-row EPSS load | Already the ORM; `sqlalchemy.dialects.postgresql.insert(...).on_conflict_do_update(...)` idiom already used 3x in this codebase (`correlation_service.py:68`, `app/api/v1/ai/feedback.py:87`, `app/ticketing/router.py:702`) |
| Alembic | `>=1.14` | New columns + 2 new tables | Existing migration chain, currently at `034_add_correlation_sources` |
| Python stdlib `gzip` + `csv` | 3.12 stdlib | Decompress + parse EPSS CSV | [VERIFIED] The EPSS file has NO `Content-Encoding: gzip` HTTP header — httpx will NOT auto-decompress it; the gzip is the file payload itself, requiring manual `gzip.decompress()` before `csv.DictReader` |
| structlog | `>=24.0` | Logging for the new refresh job, incl. the `feed_refresh_failed` flag (D-09) | Already used everywhere in `scheduler.py`/`sync.py` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic | `>=2.9` | Optional: validate parsed KEV JSON entries into a typed model before DB write | Codebase already uses pydantic extensively for schemas; a `KevEntry(BaseModel)` gives free defensive validation against malformed upstream data (see Security Domain) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Batched SQLAlchemy Core `insert()` (relies on SQLAlchemy 2.0's `insertmanyvalues` auto-batching) for the 355k-row EPSS bulk load | Raw asyncpg `copy_records_to_table` (COPY protocol) | COPY is materially faster (roughly an order of magnitude) for 350k+ rows, but it means bypassing the SQLAlchemy session/ORM entirely for this one job — a new pattern with zero precedent elsewhere in the codebase. Recommend starting with batched `insert()` (simpler, consistent with existing code) and only reaching for COPY if the daily job's real-world runtime proves too slow (it runs once/day in the background — a few seconds to ~1 minute is very likely acceptable on a single-VM). |
| `tenacity` (already a declared dependency, `>=9.0`) for feed-fetch retry/backoff | Manual `asyncio.sleep()` retry loop matching `defender.py`'s `_request_with_retry` | [VERIFIED] `tenacity` is declared in `pyproject.toml` but is not imported/used anywhere in `app/` today (`grep -rl tenacity app/` returns nothing). Using it here would introduce a new pattern for a single call site inconsistent with every existing connector's manual-retry convention. Recommend the manual-loop convention for consistency unless the planner has an appetite to start migrating connectors to `tenacity` broadly (out of this phase's scope). |

**Installation:**
```bash
# No new packages required — httpx, SQLAlchemy 2.0, gzip, csv, json are all already available.
```

**Version verification:** No new packages to verify against the registry — this phase only uses dependencies already pinned in `backend/pyproject.toml` (confirmed via direct read: `fastapi>=0.115,<1.0`, `sqlalchemy[asyncio]>=2.0`, `httpx>=0.27`, `alembic>=1.14`, `structlog>=24.0`, `pydantic>=2.9`, Python `>=3.12`).

## Architecture Patterns

### System Architecture Diagram

```
                         ┌─────────────────────────────────────────┐
                         │   External feeds (public, no auth)       │
                         │   FIRST.org EPSS CSV   CISA KEV JSON      │
                         └───────────────┬───────────────────────────┘
                                         │ httpx GET (daily / eager-first-run)
                                         ▼
                    ┌────────────────────────────────────────┐
                    │  scheduler.py: _dispatch_enrichment_    │
                    │  refresh()  (NEW — mirrors              │
                    │  _dispatch_ai_batch_prewarm 24h-gate)   │
                    └───────────┬──────────────────────────────┘
                                │ fetch + parse FULLY in memory first
                                │ (fail here = no DB write, D-09)
                                ▼
                    ┌────────────────────────────────────────┐
                    │  Single DB transaction:                 │
                    │  TRUNCATE + chunked bulk INSERT          │
                    │  epss_scores (~355k rows)                 │
                    │  cisa_kev    (~1.6k rows)                  │
                    │  (atomic — commit only on full success)  │
                    └───────────┬──────────────────────────────┘
                                │
             ┌──────────────────┼───────────────────────────────┐
             │                  │                                │
             ▼                  ▼                                ▼
  ┌─────────────────┐  ┌──────────────────────┐   ┌─────────────────────────┐
  │ Daily re-        │  │ 6 connectors          │   │ (existing, unchanged)   │
  │ propagation      │  │ (CrowdStrike/Nessus/  │   │ every other scheduler   │
  │ UPDATE           │  │ Defender/Wiz/Qualys/  │   │ tick job                │
  │ vulnerabilities  │  │ Rapid7) fetch + parse │   └─────────────────────────┘
  │ ...FROM          │  │ their OWN vendor       │
  │ epss_scores/      │  │ payload — NO DB access │
  │ cisa_kev          │  │ (unchanged today)      │
  │ WHERE cve_id=...  │  └───────────┬────────────┘
  └────────┬──────────┘              │ NormalizedVulnerability
           │                          │ (+ native_priority_score/rating,
           │                          │    + source_signals — NEW fields)
           │                          ▼
           │              ┌─────────────────────────────────┐
           └─────────────▶│  sync.py: _upsert_vulnerability   │◀── SINGLE CHOKE POINT
                          │  (existing/insert branches)        │    for ALL 6 connectors
                          │  1. lookup epss_scores by cve_id   │    (line 313-367)
                          │  2. lookup cisa_kev by cve_id       │
                          │  3. write native_priority_*/        │
                          │     source_signals from the         │
                          │     connector's own dataclass        │
                          └──────────────┬──────────────────────┘
                                         ▼
                              ┌─────────────────────┐
                              │  vulnerabilities      │
                              │  table (Postgres)     │
                              │  epss_score            │
                              │  epss_percentile (NEW)  │
                              │  cisa_kev                │
                              │  native_priority_score   │
                              │  native_priority_rating   │
                              │  source_signals (JSONB)   │
                              └─────────────────────┘
```

A reader can trace the primary use case: a connector fetches its vendor payload → normalizes it into a `NormalizedVulnerability` with the 3 new fields set from ITS OWN payload → `_upsert_vulnerability` (which now ALSO does a fast keyed lookup against the two new global ref tables) writes the final row with EPSS/KEV coming from the global tables and native-priority/source_signals coming from the connector. The daily job runs independently, refreshing the global tables and then re-propagating into all existing rows — completely decoupled from any individual connector's sync cadence, exactly as ENRICH-05 requires.

### Recommended Project Structure

No new top-level modules are needed — this phase is additive within existing files:

```
backend/app/
├── connectors/
│   ├── base.py              # NormalizedVulnerability gains 3 new fields
│   ├── sync.py               # _upsert_vulnerability gains ref-table lookups (both branches)
│   ├── scheduler.py           # new _dispatch_enrichment_refresh() + eager first-run in start_scheduler()
│   ├── enrichment_feeds.py    # NEW — EPSS/KEV fetch+parse+refresh logic (recommended new module,
│   │                           #        keeps scheduler.py focused on dispatch/gating, mirrors how
│   │                           #        app.ai.batch is a separate module the scheduler only dispatches to)
│   ├── crowdstrike.py          # _normalize_vuln reads cve_meta.get("exprt_rating") — already-fetched response
│   ├── nessus.py                # _normalize_vuln probes plugin_attributes for a VPR-shaped key
│   ├── defender.py               # native_priority_* stays null; source_signals allowlist added
│   ├── wiz.py                     # native_priority_* stays null; GraphQL query gains epssSeverity/epssPercentile etc.
│   ├── qualys.py                   # detection dict gains QDS via show_qds_factors=1 param
│   └── rapid7.py                    # native_priority_score = riskScore read off asset_vulns entries (not detail)
├── vulnerabilities/
│   ├── models.py                # Vulnerability gains 4 columns; 2 new global ref-table models
│   └── schemas.py                # VulnerabilityResponse gains the 4 new fields (read-model completeness,
│                                  #   NOT sort=/filter wiring — mirrors existing exploit_status_id precedent)
└── alembic/versions/
    └── 035_add_enrichment_columns.py  # (or split 035/036 — see Open Questions)
```

### Pattern 1: Single-choke-point enrichment (mirrors D-04's own reasoning)
**What:** All ref-table-sourced fields (EPSS score/percentile, authoritative KEV) are set exactly once, in `_upsert_vulnerability`, never inside a connector.
**When to use:** Any signal whose source of truth is NOT the vendor's own payload (i.e., anything global/cross-connector).
**Example:**
```python
# Source: backend/app/connectors/sync.py:313-367 (existing, to be extended)
# NEW: both branches call this shared helper first.
async def _lookup_enrichment(db: AsyncSession, cve_id: str | None) -> tuple[Decimal | None, Decimal | None, bool]:
    """Returns (epss_score, epss_percentile, cisa_kev) from the global ref tables.
    A miss (unscored/unlisted CVE) returns (None, None, False) — never raises."""
    if not cve_id:
        return None, None, False
    epss_row = (await db.execute(select(EpssScore).where(EpssScore.cve_id == cve_id))).scalar_one_or_none()
    kev_hit = (await db.execute(select(CisaKev.cve_id).where(CisaKev.cve_id == cve_id))).scalar_one_or_none()
    epss_score = epss_row.epss_score if epss_row else None
    epss_percentile = epss_row.percentile if epss_row else None
    return epss_score, epss_percentile, kev_hit is not None
```
Both the `existing.*` update branch and the `Vulnerability(...)` insert branch call this once and assign the 3 return values — this is the ENTIRE ENRICH-01/02 implementation surface within `sync.py`.

### Pattern 2: Extractable async def + 24h-gate (exact codebase idiom to copy)
**What:** A dedicated top-level `async def` in `scheduler.py`, gated by its own module-level `datetime | None` sentinel, dispatched via a thin check in `_scheduler_loop()`.
**When to use:** Any new daily/periodic background job in this codebase — this is now a 3rd instance of the same pattern (ticket sync, AI batch prewarm, this).
**Example:**
```python
# Source: backend/app/connectors/scheduler.py:72-105 (existing _dispatch_ai_batch_prewarm — the pattern to mirror)
_last_enrichment_refresh: datetime | None = None

async def _dispatch_enrichment_refresh() -> None:
    """ENRICH-05/D-09/D-10: nightly, 24h-gated refresh of epss_scores/cisa_kev.
    Extracted to a top-level function (not inlined in _scheduler_loop) so it is
    directly unit-testable via `from app.connectors import scheduler as scheduler_module;
    await scheduler_module._dispatch_enrichment_refresh()` — the established
    test_connector_health.py::test_scheduler_path_failure_parity convention."""
    global _last_enrichment_refresh
    try:
        now = datetime.now(UTC)
        if _last_enrichment_refresh is None or (now - _last_enrichment_refresh).total_seconds() >= 86400:
            from app.connectors.enrichment_feeds import refresh_enrichment_reference_data

            async with async_session_factory() as db:
                result = await refresh_enrichment_reference_data(db)
                await db.commit()
                logger.info("enrichment_refresh_completed", **result)
            _last_enrichment_refresh = now
    except Exception as e:
        logger.error("enrichment_refresh_dispatch_error", error=str(e))
```
Note this differs slightly from `_dispatch_ai_batch_prewarm` in one respect: it `await`s the refresh inline rather than `asyncio.create_task`-ing it, because (unlike the AI batch dispatch, which explicitly must never block the tick) D-09's atomic-swap-transaction needs to run to completion as one unit before the gate timestamp advances — dispatching it as a detached task risks the gate advancing before the swap actually committed. This is a deliberate, reasoned deviation, not an oversight — flag it clearly in the plan.

### Pattern 3: Atomic swap that keeps last-good (D-09)
**What:** Fetch + parse fully in memory (any exception here aborts before touching the DB); then, in a single transaction, `TRUNCATE` + chunked bulk `INSERT`; commit only after every chunk succeeds.
**When to use:** Exactly this job — global reference data refresh where "half-updated" is worse than "a day stale".
**Example:**
```python
# Recommended shape — no direct precedent in this codebase (this is genuinely new I/O),
# but composes the `pg_insert(...).on_conflict_do_update(...)` idiom already used in
# correlation_service.py:68 / app/api/v1/ai/feedback.py:87 / app/ticketing/router.py:702.
async def refresh_enrichment_reference_data(db: AsyncSession) -> dict:
    try:
        epss_rows = await _fetch_and_parse_epss()      # pure fetch+parse, no DB — mockable in tests
        kev_rows = await _fetch_and_parse_kev()          # same
    except Exception as e:
        logger.error("feed_refresh_failed", error=str(e))
        return {"status": "failed", "error": str(e)}      # D-09: prior good data untouched — no DB call made

    await db.execute(delete(EpssScore))
    for chunk in _chunks(epss_rows, 5000):                  # stay under Postgres's ~65535 param limit
        await db.execute(insert(EpssScore), chunk)            # SQLAlchemy 2.0 insertmanyvalues auto-batches
    await db.execute(delete(CisaKev))
    await db.execute(insert(CisaKev), kev_rows)                # ~1.6k rows — no chunking needed
    # NOT committed here — caller commits once, making the whole swap one atomic unit.
    return {"status": "ok", "epss_rows": len(epss_rows), "kev_rows": len(kev_rows)}
```

### Anti-Patterns to Avoid
- **Per-connector DB lookups for EPSS/KEV:** Every connector class today (`CrowdStrikeConnector`, `NessusConnector`, etc.) is a pure `httpx` client with zero `sqlalchemy`/`AsyncSession` imports [VERIFIED — grepped all 6 files]. Giving connectors DB access to look up their own EPSS/KEV would be a significant, unnecessary architecture change and would duplicate the lookup 6 times. Keep it in `_upsert_vulnerability`.
- **Row-by-row upsert for the 355k-row EPSS table:** A `for row in epss_rows: await db.execute(pg_insert(...).on_conflict_do_update(...))` loop (355k round trips) would make the daily job unacceptably slow. Use chunked bulk `insert()` (relying on SQLAlchemy 2.0's `insertmanyvalues`) inside the TRUNCATE-based atomic swap instead — an upsert isn't even needed post-TRUNCATE since the table is empty.
- **Conflating "vendor returned false" with "vendor never mentioned it" when populating `source_signals`:** see Common Pitfall #2 below — this is the single most important correctness risk for SC#4.
- **Assuming `httpx.AsyncClient()` follows redirects by default:** it does not (see Common Pitfall #1) — the EPSS "current" URL is a 302 with an empty body.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Gzip decompression of the EPSS file | Manual byte-stream deflate parsing | stdlib `gzip.decompress(resp.content)` | [VERIFIED] No `Content-Encoding` header is set — the bytes ARE a valid standalone gzip file; stdlib handles this in one call |
| CSV parsing with a leading comment line | Manual `str.split(",")` per line | stdlib `csv.DictReader` over `io.StringIO(decompressed_text.split("\n", 1)[1])` (skip the `#model_version:...` line first) | Handles quoting/edge cases the naive split won't; this file's actual header only needs the comment line skipped once, verified structurally simple |
| Bulk Postgres upsert for 355k rows | Hand-rolled multi-VALUES SQL string concatenation | `sqlalchemy.dialects.postgresql.insert()` + SQLAlchemy 2.0's `insertmanyvalues` auto-batching, OR the already-3x-used `.on_conflict_do_update()` idiom | Existing, tested idiom in this exact codebase; avoids manual SQL-injection-adjacent string building and respects Postgres's parameter-count limit automatically |
| Feed-fetch retry/backoff | New bespoke retry wrapper | Mirror `defender.py`'s existing `_request_with_retry` manual-sleep-loop pattern | Consistency with every other connector's established convention (tenacity is available but unused everywhere else — see Alternatives Considered) |
| Missing-vs-negative JSONB semantics | A custom sentinel/wrapper object | Plain Python dict construction where a key is `del`eted or simply never added when the vendor field is absent (mirrors `Asset.mdm_details`, D-07) | Native JSONB/Postgres `?` operator already gives you this for free — building a wrapper type is the "over-engineered" option D-07 explicitly rejected |

**Key insight:** Every "hard part" of this phase already has a live precedent inside this exact codebase (upsert idiom, 24h-gate idiom, sparse-JSONB idiom, bulk-`UPDATE...FROM` idiom). The actual novel work is limited to (1) the two new HTTP fetches and (2) correctly reading a handful of new fields out of already-fetched vendor payloads.

## Common Pitfalls

### Pitfall 1: httpx does not follow redirects by default
**What goes wrong:** `https://epss.empiricalsecurity.com/epss_scores-current.csv.gz` returns HTTP 302 with `content-length: 0` [VERIFIED via direct `curl -sI`]. A plain `httpx.AsyncClient().get(url)` will return the empty 302 response, and `resp.raise_for_status()` will NOT raise (3xx is not an error status to httpx) — the code will silently "succeed" with zero bytes of CSV.
**Why it happens:** httpx defaults `follow_redirects=False`, unlike `requests` which defaults to following redirects.
**How to avoid:** Construct the client with `httpx.AsyncClient(follow_redirects=True)`, or pass `follow_redirects=True` on the specific `.get()` call. Additionally check `resp.status_code == 200` and `len(resp.content) > 0` explicitly before attempting `gzip.decompress` — a defensive belt-and-suspenders check that also serves D-09 (a truncated/empty response should abort the parse, not silently produce zero rows).
**Warning signs:** `refresh_enrichment_reference_data` reporting `epss_rows: 0` in its scheduler log with no exception raised.

### Pitfall 2: Tri-state "missing vs negative" gets silently collapsed by dataclass defaults
**What goes wrong:** `NormalizedVulnerability.exploit_available: bool = False` and `cisa_kev: bool = False` [VERIFIED, `base.py:17-18`] mean 3 of the 6 connectors (Nessus, Qualys, Rapid7) never explicitly set `cisa_kev` at all and get `False` by default — this is fine (they genuinely have nothing to say about KEV, so their `source_signals` allowlist simply omits a KEV-guess key, correctly modeling "missing"). But **Wiz's** `cisa_kev=bool(node.get("hasCisaKevExploit"))` [VERIFIED, `wiz.py:283`] coerces a GraphQL `null` to `False` — if Wiz's schema can return `null` for this field (unconfirmed either way), the current code cannot distinguish "Wiz said no" from "Wiz didn't have data," which would defeat D-07's entire contract if this raw value is later routed into `source_signals`.
**Why it happens:** The existing dataclass fields were designed for one thing only — populating the OLD lossy boolean columns — where "missing" and "false" were never meaningfully different. D-07 needs that distinction for the FIRST time.
**How to avoid:** When building each connector's `source_signals` allowlist entries, read the **raw vendor payload key** directly (e.g., `node.get("hasCisaKevExploit")` before the `bool()` coercion, or check `"hasCisaKevExploit" in node`), never the already-defaulted `NormalizedVulnerability` field. This likely means the allowlist-population code needs access to the raw dict, not just the finished dataclass — plan for `_normalize_vuln`/equivalent to build `source_signals` inline, in the same function that has the raw payload in scope, not as a later post-processing step over the dataclass.
**Warning signs:** SC#4's fixture (assert `'x' not in source_signals` for a genuinely-absent field) passing only by accident because the test fixture happens to use a connector where the raw-vs-defaulted distinction doesn't matter (e.g., Defender, where every relevant field is always present) — masking a real bug in a connector where the distinction does matter (Wiz).

### Pitfall 3: CrowdStrike's own docstring is stale/wrong about its KEV threshold
**What goes wrong:** `crowdstrike.py`'s module docstring (line 11) says "CISA KEV: derived from exploit_status >= 30", but the actual code (line 362) checks `exploit_status_id >= 50`. [VERIFIED by direct read — genuine discrepancy in the live file.]
**Why it happens:** Comment drift — the code was changed at some point and the docstring wasn't updated.
**How to avoid:** When implementing/reviewing CrowdStrike's `source_signals` capture of its own KEV-ish guess (D-04's provenance requirement), trust the code (`>= 50`), not the docstring. Don't "fix" the docstring's number into the code — that would silently change existing behavior (more findings would flip from `exploit_available=True/cisa_kev=False` to `cisa_kev=True` at the 30-49 band) as an unplanned side effect.
**Warning signs:** A new contributor reading only the docstring and writing a test fixture that expects the (wrong) `>=30` threshold.

### Pitfall 4: Qualys's QDS is a per-detection field, not a per-QID knowledge-base field
**What goes wrong:** The existing `qualys.py` architecture caches KB entries by QID (`self._kb_cache: dict[int, dict]`, populated once and shared across every host that has that QID). QDS incorporates "vulnerability temporal details" (external threat intel, exploit maturity) which Qualys computes at **detection time**, not as a static KB attribute — naively adding QDS reads to `_kb_cache`/`kb_cvss3`-style helper functions would silently return stale/wrong-context data, or simply never populate (KB endpoint may not even return it).
**Why it happens:** The existing code's 3 fields sourced from KB (`vuln_name`, `cvss3`, `solution`) really are QID-level constants; QDS is a fundamentally different kind of field that happens to live in a sibling API response.
**How to avoid:** Add `show_qds_factors=1` (param name CITED at MEDIUM confidence — verify empirically) to the existing `_fetch_all_detections` request params (line ~198-203), and read the QDS value from the `det` dict inside `_normalize_detection(detection, host, kb_cache)` — NOT from `kb_cache`.
**Warning signs:** `native_priority_score` for Qualys findings is always `None` despite the API call apparently succeeding — a sign the code is looking in the KB cache instead of the detection record.

### Pitfall 5: Rapid7's risk score lives on the asset-vulnerability association, not the vulnerability definition
**What goes wrong:** The existing code fetches `/api/3/vulnerabilities/{vuln_id}` (`_fetch_vuln_detail`) for CVSS/title/exploits-count — this is Rapid7's **vulnerability definition** resource (vendor-neutral: same for every asset that has this CVE). Risk/Active Risk Score is asset-context-dependent (it can incorporate asset criticality/exposure), so [ASSUMED, based on API shape + training knowledge, not directly schema-verified this session] it is far more likely to live on the **AssetVulnerability** resource already being fetched at `_fetch_asset_vulns` (`/api/3/assets/{asset_id}/vulnerabilities`) — whose entries the current code loops over as `vuln_entry` (line 212) but only extracts `vuln_entry["id"]` from, discarding the rest.
**Why it happens:** The current code was written to source everything from the vendor-neutral detail resource, which never needed asset-contextual data before.
**How to avoid:** Read a `riskScore`-shaped field directly off `vuln_entry` (the per-asset association entry), not off `detail`. Verify the exact field name empirically against a real InsightVM instance or account (public schema fetch attempts this session were inconclusive — see Assumptions Log A4).
**Warning signs:** `native_priority_score` is always `None` for Rapid7 despite `detail` clearly containing other fields successfully.

### Pitfall 6: `native_priority_score`/`native_priority_rating` genuinely cannot be populated for 2 of 6 connectors
**What goes wrong:** A literal reading of D-05 ("a generic two-column pair every finding populates") plus ENRICH-03's phrasing ("each other scanner's equivalent") could be misread as "all 6 connectors must produce a non-null value here." Direct verification of Microsoft's and (via search) Wiz's public API schemas found **no vendor-authored composite priority rating** for either — only granular booleans/sub-scores that are CVSS-adjacent or EPSS-adjacent, not a distinct "vendor opinion" score.
**Why it happens:** CONTEXT.md's "Specifics" section itself only names 4 scanners for this signal (Nessus VPR, CrowdStrike ExPRT.AI, Qualys QDS, Rapid7 Risk Score) — Defender and Wiz were never named, likely for exactly this reason.
**How to avoid:** Treat `native_priority_score`/`native_priority_rating` as nullable and leave them `NULL` for Defender/Wiz findings — do not invent a synthetic composite (e.g., don't average `exploitVerified`+`publicExploit`+`exploitInKit` into a fake 0-3 "Defender score"; that would violate D-06's "raw, no cross-scale mapping/opinion" principle by definition, since it would BE an invented opinion). Route their genuinely richer signals (Defender: `publicExploit`/`exploitVerified`/`exploitInKit`/`exploitTypes`/`exploitUris`/native `EPSS`; Wiz: `epssSeverity`/`epssPercentile`/`epssProbability`/`exploitabilityScore`/`impactScore`) into `source_signals` instead — this still satisfies ENRICH-06's "threaded through ingestion, never permanently null/inconsistent" in spirit, because the richer data DOES land somewhere queryable, just not in the two promoted columns.
**Warning signs:** A plan task that says "compute a synthetic native_priority_score for Defender/Wiz" — this should be flagged and pushed back on during planning, not implemented.

## Code Examples

### Per-Connector Native Signal Reference (verified this session)

| Connector | Native composite signal? | Field / mechanism | Confidence | Where to read it |
|-----------|---------------------------|--------------------|------------|-------------------|
| CrowdStrike | Yes — ExPRT.AI rating (categorical only; no confirmed numeric companion) | `cve.exprt_rating` — enum `UNKNOWN`/`LOW`/`MEDIUM`/`HIGH`/`CRITICAL` | [CITED: developer.crowdstrike.com official API reference — confirmed as a *filterable* field; full response-body schema not published, so presence at this exact path in the actual JSON response is inferred, not directly observed] | Already-fetched `/spotlight/entities/vulnerabilities/v2` response, cached in `self._vuln_metadata_cache` — read `cve_meta.get("exprt_rating")` right next to the existing `cve_meta.get("exploit_status", 0)` read at `crowdstrike.py:359` — **zero new API calls needed** |
| Nessus | Yes — VPR (numeric, 0.1-10.0) | Exact REST JSON field name **not verified** this session | [CITED: docs.tenable.com — VPR "expanded for Tenable Nessus Professional...in version 10.5.0" confirms availability in the Professional (non-cloud) product line, contradicting an initial assumption that VPR is Tenable.io/tenable.sc-only] / [ASSUMED: exact field name — candidates to probe empirically: `vpr_score`, `vpr`, nested under `plugin_attributes`] | Probe `vuln.get("plugin_attributes", {})` defensively (same dict `_check_exploit_available` already reads at `nessus.py:236`) — treat as nullable if absent |
| Defender | **No** — no vendor-authored composite; only granular booleans + sub-scores | `publicExploit`, `exploitVerified`, `exploitInKit` (bools), `exploitTypes`/`exploitUris` (string collections), native `EPSS` (numeric probability) | [CITED: raw.githubusercontent.com/MicrosoftDocs/defender-docs — `vulnerability.md` property list, directly fetched] | `native_priority_score`/`rating` → `NULL`. Route all 5 fields into `source_signals` (2 of 3 booleans already read today at `defender.py:257`, `exploitInKit`/`exploitTypes`/`exploitUris`/`EPSS` are new reads on the same already-fetched `/api/vulnerabilities/machinesVulnerabilities` record) |
| Wiz | **No** — no vendor-authored composite | `epssSeverity`, `epssPercentile`, `epssProbability`, `exploitabilityScore`, `impactScore` (CVSS sub-scores, not vendor-proprietary) | [CITED: WebSearch-surfaced GraphQL field names, not a primary schema document — MEDIUM confidence] | `native_priority_score`/`rating` → `NULL`. Add these fields to the existing `VULNERABILITY_QUERY` GraphQL document (`wiz.py:23-65`) and route into `source_signals` |
| Qualys | Yes — QDS (numeric, 1-100) | `QDS` element/field on the per-**detection** record (not the KB entry) | [CITED: docs.qualys.com / blog.qualys.com — QDS concept + 1-100 scale + `show_qds_factors=1` param name confirmed via search; exact XML/JSON element tag NOT directly verified (404 on the specific doc page attempted)] | Add `show_qds_factors=1` to the existing `_fetch_all_detections` params (`qualys.py:198-203`); read from the `detection` dict inside `_normalize_detection`, NOT `kb_cache` (see Pitfall 4) |
| Rapid7 | Yes — Risk Score / "Active Risk" (numeric, 0-1000 scale) | Likely `riskScore`, on the **AssetVulnerability** association resource | [CITED: help.rapid7.com/docs.rapid7.com concept pages confirm the 0-1000 scale; exact JSON field name NOT directly schema-verified this session — WebFetch attempts against the API docs returned empty/JS-rendered content] [ASSUMED: exact field name `riskScore`, based on training knowledge of the InsightVM v3 API shape] | Already-fetched `asset_vulns` entries at `rapid7.py:212` (currently only `vuln_entry["id"]` is extracted) — read `vuln_entry.get("riskScore")` directly, verify empirically |

### External Feeds — EPSS (ENRICH-01)

**URL:** `https://epss.empiricalsecurity.com/epss_scores-current.csv.gz` [VERIFIED via live `curl` on 2026-08-05]
- Returns HTTP 302 (empty body, `content-length: 0`) redirecting to a dated snapshot, e.g. `epss_scores-2026-08-04.csv.gz` — **must set `follow_redirects=True`** (see Pitfall 1).
- Final response: `content-type: binary/octet-stream`, **no `Content-Encoding` header** — the payload IS the gzip file; httpx will not auto-decompress, call `gzip.decompress(resp.content)` manually.
- Compressed size: ~2.5 MB. Decompressed: ~355,094 data rows (**355,096 total lines including 2 header lines** — VERIFIED by direct download+`wc -l` today; notably higher than the ~200k estimate carried in CONTEXT.md/roadmap docs, since EPSS coverage has grown to cover nearly the full published CVE corpus, not just a curated subset).
- **Line 1** is a comment, not CSV data: `#model_version:v2026.06.15,score_date:2026-08-04T12:00:14Z` — must be skipped before `csv.DictReader` sees the real header. Simple parse: strip leading `#`, split on `,`, split each piece on `:` for `model_version`/`score_date` metadata (optional to capture; not required for the phase's success criteria, but useful for the ref table's own freshness bookkeeping).
- **Line 2** is the real CSV header: `cve,epss,percentile`.
- **Data rows**, e.g.: `CVE-1999-0001,0.03351,0.87494` — both `epss` and `percentile` are decimal strings with **5 digits after the decimal point** [VERIFIED]. The existing `Vulnerability.epss_score` column is `Numeric(5, 4)` (`models.py:56`) — only 4 digits after the decimal. Storing a genuine 5-decimal value into a `Numeric(5,4)` column causes Postgres to round it (e.g. `0.03351` → `0.0335`). This is a minor precision loss (≤0.00005 absolute), likely immaterial for triage sorting/display, but the planner should make this an **explicit** choice — either accept it (keep `epss_percentile` also `Numeric(5,4)` for consistency with the existing column) or widen both to `Numeric(6,5)` (requires an `ALTER COLUMN` on the pre-existing `epss_score` too, outside D-03's stated scope).
- Free API alternative (not recommended for bulk refresh): `https://api.first.org/data/v1/epss` — explicitly documented as intended for single/small-batch CVE lookups, not bulk sync; the CSV is FIRST.org's own recommended mechanism for exactly this use case.

### External Feeds — CISA KEV (ENRICH-02)

**URL:** `https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json` [VERIFIED via live `curl`+download on 2026-08-05]
- HTTP 200, `content-type: application/json`, ~1.5 MB, no auth required.
- **Envelope:** `{"title": ..., "catalogVersion": "2026.08.04", "dateReleased": "2026-08-04T16:45:52.0783Z", "count": 1660, "vulnerabilities": [...]}` — `count` **matches** `len(vulnerabilities)` exactly [VERIFIED]. `catalogVersion` is a date-shaped string, not semver.
- **Verified live count: 1,660 entries** (2026-08-05) — above the ~1.2k estimate carried in CONTEXT.md; the catalog grows continuously (CISA adds entries "multiple times per week" per CISA's own description).
- **Per-entry keys** [VERIFIED across all 1,660 entries]: `cveID`, `vendorProject`, `product`, `vulnerabilityName`, `dateAdded` (date-only `YYYY-MM-DD`), `shortDescription`, `requiredAction`, `dueDate` (date-only), `knownRansomwareCampaignUse` (exactly 2 distinct values across the whole catalog: `"Known"`/`"Unknown"`), `notes` (freeform, semicolon/pipe-separated URLs), `cwes` (array of CWE-id strings — **missing/empty on 171 of 1,660 entries, ~10%** — treat as optional).
- **Field length bounds** [VERIFIED, for column sizing]: `cveID` ≤ 16 chars, `vendorProject` ≤ 32, `product` ≤ 179, `vulnerabilityName` ≤ 161.
- No gzip/redirect complications — a plain `httpx.AsyncClient().get(url)` (with the usual `follow_redirects=True` for defense-in-depth) followed by `resp.json()` works directly.
- D-04's actual requirement is minimal: `finding.cisa_kev = (cve_id ∈ KEV catalog)` — only `cveID` is strictly required for the ref table's join key. The descriptive fields (`dateAdded`, `vulnerabilityName`, etc.) are optional nice-to-haves for a future display surface, not required by this phase's success criteria; storing them costs nothing extra (the whole catalog is ~1.5MB) and avoids a future migration if a later phase wants to show "why is this in KEV."

### Ingestion Write-Path — recommended schema additions

```python
# Source: backend/app/vulnerabilities/models.py (existing Vulnerability class, lines 46-81)
# NEW columns (D-03, D-05, ENRICH-04):
epss_percentile: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))          # mirrors epss_score's existing precision
native_priority_score: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))     # covers QDS(1-100)/VPR(0.1-10)/RiskScore(0-1000) with headroom
native_priority_rating: Mapped[str | None] = mapped_column(String(50))           # raw vendor label verbatim, e.g. "HIGH", "ExploitIsPublic"
source_signals: Mapped[dict | None] = mapped_column(JSONB, default=dict)         # mirrors Asset.mdm_details (assets/models.py:67) exactly

# NEW global reference tables (D-11 — deliberately skip UUIDPrimaryKeyMixin;
# cve_id is a natural key and every access pattern is "upsert/lookup by cve_id").
# Base.py's Base/TimestampMixin have NO hidden tenant_id enforcement [VERIFIED —
# read app/db/base.py directly; Base is a bare DeclarativeBase, tenant_id is a
# per-model convention, not framework-enforced], so this is a clean, unobstructed departure.

class EpssScore(Base, TimestampMixin):
    __tablename__ = "epss_scores"
    cve_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    epss_score: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)   # full published precision
    percentile: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(20))
    score_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class CisaKev(Base, TimestampMixin):
    __tablename__ = "cisa_kev"
    cve_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    date_added: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    vendor_project: Mapped[str | None] = mapped_column(String(50))
    product: Mapped[str | None] = mapped_column(String(200))
    vulnerability_name: Mapped[str | None] = mapped_column(String(200))
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    known_ransomware_campaign_use: Mapped[str | None] = mapped_column(String(10))
    catalog_version: Mapped[str | None] = mapped_column(String(20))
```

```python
# Source: backend/app/connectors/base.py (existing NormalizedVulnerability, lines 9-44)
# NEW fields (ENRICH-03/04/06) — populated per-connector from the vendor's OWN payload:
native_priority_score: float | None = None
native_priority_rating: str | None = None
source_signals: dict | None = None
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| CISA KEV directive referenced in training-era knowledge: BOD 22-01 | CISA's live catalog's own `requiredAction` text now cites **BOD 26-04** ("Prioritizing Security Updates Based on Risk") [VERIFIED — read directly from the downloaded catalog, 2026-08-05] | Superseded before this session | The directive numbering has moved on since training; don't hardcode "BOD 22-01" anywhere if the phase or a future phase surfaces this text to users — read it from the feed, don't embed a stale reference. Notably, REQUIREMENTS.md's own RISK-03 already correctly cites "BOD-26-04 guidance," confirming the project's requirements doc is already current on this point. |
| Assumption: VPR is a Tenable.io/Tenable.sc-only feature, unavailable in standalone Nessus Professional | VPR was "expanded for Tenable Nessus Professional...in version 10.5.0" [CITED: docs.tenable.com release notes search] | ~2023 (Nessus 10.5.0) | De-risks ENRICH-03's Nessus requirement — the connector's target product line does support VPR, assuming the deployed instance is 10.5.0+. Exact API field name still needs empirical confirmation (see Assumptions Log). |
| EPSS coverage estimated at ~200k CVEs (per CONTEXT.md's own discretion note) | ~355,000 CVEs currently scored [VERIFIED live download, 2026-08-05] | Ongoing — EPSS has steadily expanded coverage since its public launch | Bulk-load chunking/performance planning should size for ~355k rows, not ~200k — roughly 1.75x more data than the original estimate assumed. |
| CISA KEV estimated at ~1.2k entries | 1,660 entries currently [VERIFIED live download, 2026-08-05] | Ongoing — catalog grows continuously | Negligible practical impact (table is tiny either way), but worth correcting the estimate for the planner's mental model. |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Nessus VPR's exact REST API JSON field name (candidates: `vpr_score`, `vpr`, nested under `plugin_attributes`) | Per-Connector Native Signal Reference | If wrong, Nessus's `native_priority_score` silently stays `NULL` post-implementation — SC#3's "each scanner's equivalent" would be unmet for 1 of 4 populatable connectors. Mitigation already built in: defensive `.get()` probing (mirrors existing `_check_exploit_available` pattern) means a wrong guess fails soft (null), not a crash. Recommend verifying against a live/trial Nessus 10.5+ instance or a captured real scan-result JSON sample early in implementation (Wave 0 spike). |
| A2 | Rapid7's exact risk-score JSON field name (assumed `riskScore`) and that it lives on the AssetVulnerability association resource (`/api/3/assets/{id}/vulnerabilities`) rather than the Vulnerability definition resource | Per-Connector Native Signal Reference, Pitfall 5 | Same failure mode as A1 — soft-null, not a crash, if the field name/location guess is wrong. Recommend a live-account spike or checking Rapid7's interactive Swagger UI directly (`help.rapid7.com/insightvm/en-us/api/`) during implementation — this session's automated fetch of that page returned no usable content (likely JS-rendered SPA). |
| A3 | Qualys QDS's exact XML/JSON element name inside a detection record, and that `show_qds_factors=1` is the correct/complete query parameter | Per-Connector Native Signal Reference, Pitfall 4 | If the param name is slightly wrong, the API call likely just ignores the unrecognized param (Qualys APIs are generally tolerant of unknown params) and QDS stays absent — soft failure. Recommend testing the param addition against a real Qualys account/sandbox early, inspecting the raw XML response structure directly (the existing `_xml_to_dict` fallback will surface whatever key Qualys actually uses, even if it's not what's guessed here). |
| A4 | Wiz's GraphQL schema includes `epssSeverity`/`epssPercentile`/`epssProbability`/`exploitabilityScore`/`impactScore` on `vulnerabilityFindings` nodes | Per-Connector Native Signal Reference | This came from a WebSearch synthesis, not a primary Wiz API reference document. If wrong, adding these fields to `VULNERABILITY_QUERY` (`wiz.py:23-65`) would cause Wiz's GraphQL API to return a schema error for the whole query (GraphQL fails the entire request on an unknown field, unlike REST's typical "ignore extra params" tolerance) — this is a **harder** failure mode than A1-A3. Recommend verifying field names against Wiz's actual GraphQL schema (introspection query or Wiz's own developer portal) BEFORE adding them to the live query, or wrapping the addition in its own error-handling fallback (try the enriched query, fall back to the current field set on a GraphQL error). |
| A5 | Whether the daily refresh job should `await` the atomic-swap inline (this research's recommendation) vs. `asyncio.create_task` it (matching `_dispatch_ai_batch_prewarm`'s literal pattern) | Architecture Patterns, Pattern 2 | Low risk either way functionally, but if dispatched as a detached task, the 24h-gate timestamp (`_last_enrichment_refresh`) would need to be set INSIDE the task after successful completion, not at dispatch time — otherwise a failed swap would still "consume" that day's refresh window, contradicting D-09's resilience intent. This research recommends inline `await` specifically to sidestep that subtlety; flagging it as an assumption since it's a deliberate deviation from the most superficially similar existing pattern. |

**If this table is empty:** N/A — see entries above.

## Open Questions (RESOLVED)

> All three resolved during planning (verified by gsd-plan-checker against the actual plan actions): Q1 → Plan 31-01 Task 2 adds the 4 columns to `VulnerabilityResponse` and leaves `sort=`/`VulnerabilityFilter` untouched; Q2 → two migrations (`035`, `036`); Q3 → new `enrichment_feeds.py` module with a thin scheduler dispatcher.

1. **RESOLVED — Does this phase update `VulnerabilityResponse`/`VulnerabilitySummary` (API schemas) to expose the 4 new columns?**
   - What we know: `VulnerabilityResponse` is an explicit Pydantic allowlist (`schemas.py:15-45`) that already exposes `exploit_status_id`/`exploit_status_name` — a typed signal promoted beyond a boolean that, like this phase's new columns, isn't yet "consumed" by any scoring model (that's Phase 33's job). This is direct precedent for exposing new columns before they're consumed.
   - What's unclear: whether the planner should also add the new fields to the `sort=` `Literal` (`router.py:66-72`) and `VulnerabilityFilter` (enabling `?sort=native_priority_score` or `?native_priority_score_min=`) — CONTEXT.md's D-06 explicitly defers "consuming" these signals, and sort/filter wiring arguably counts as consumption-adjacent.
   - Recommendation: Add the 4 fields to `VulnerabilityResponse` (completes the persistence contract, matches precedent, zero scoring-model risk) but leave `sort=`/`VulnerabilityFilter` untouched this phase — that's squarely Phase 33+ territory. Flag this explicitly for the discuss-phase/planner to confirm rather than silently deciding.

2. **Single migration or two?**
   - What we know: the phase touches two conceptually distinct things — 4 new columns on the existing `vulnerabilities` table, and 2 brand-new global tables. The Phase 30 precedent (`034_add_correlation_sources.py`) combined a column-add + backfill + column-drop into one migration because they were causally linked (backfill needed the old columns present).
   - What's unclear: here, the 4 new `vulnerabilities` columns and the 2 new ref tables have no such causal coupling — either could ship independently.
   - Recommendation: two migrations (e.g. `035_add_enrichment_columns.py` for the 4 `vulnerabilities` columns + `036_add_enrichment_reference_tables.py` for `epss_scores`/`cisa_kev`) for cleaner independent rollback, but this is explicitly Claude's Discretion per CONTEXT.md ("Alembic revision chaining") — either is acceptable. Remember the `alembic_version.version_num` is `varchar(32)` [VERIFIED via two prior migrations' own docstrings hitting this] — keep revision id strings ≤ 32 characters (e.g. `"035_add_enrichment_columns"` is 27 chars, safe).

3. **Should the daily refresh job live in a new `enrichment_feeds.py` module or inline in `scheduler.py`?**
   - What we know: `scheduler.py` currently dispatches to sibling modules for anything non-trivial (`app.ai.batch`, `app.ticketing.daily_sync`, `app.ticketing.rule_engine`, `app.reports`, `app.notifications.alerts`) rather than inlining substantial logic — `scheduler.py` itself stays a thin dispatch/gating layer.
   - What's unclear: nothing really — this is a strong, consistent pattern across the entire file.
   - Recommendation: follow the established pattern — new `app/connectors/enrichment_feeds.py` (or `app/vulnerabilities/enrichment_feeds.py`, either tier is defensible) housing fetch/parse/swap logic; `scheduler.py` only gains the thin `_dispatch_enrichment_refresh()` gate function.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Outbound HTTPS to `epss.empiricalsecurity.com` | ENRICH-01 daily EPSS fetch | ✓ (verified reachable from this research session's environment, 2026-08-05) | — | None documented — if the production single-VM's network/firewall policy restricts egress to only vendor-scanner hosts, this is a **new** egress target requiring an allowlist update. Recommend the planner add an explicit verification step (`curl` from inside the deployed container/VM) rather than assuming parity with this research environment. |
| Outbound HTTPS to `www.cisa.gov` | ENRICH-02 daily KEV fetch | ✓ (verified reachable, 2026-08-05) | — | Same egress-allowlist caveat as above. |
| httpx, SQLAlchemy 2.0, Alembic, structlog, pydantic | All | ✓ | Per `pyproject.toml` (httpx>=0.27, sqlalchemy[asyncio]>=2.0, alembic>=1.14, structlog>=24.0, pydantic>=2.9) | — |
| Postgres (target of new tables/columns) | ENRICH-01..06 | ✓ (existing service, Docker Compose) | Not re-verified this session (no schema change requires a version bump) | — |

**Missing dependencies with no fallback:**
- None identified — no new dependency is required beyond what's already installed.

**Missing dependencies with fallback:**
- None — the only real environment risk is the production VM's outbound egress policy for the 2 new public feed hosts, flagged above as a verification step, not a blocker.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest `>=8.3` + `pytest-asyncio>=0.24` [VERIFIED, `pyproject.toml` dev deps] |
| Config file | `backend/pyproject.toml` (dev extras) — no separate `pytest.ini` found |
| Quick run command | `ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") JWT_SECRET_KEY=test-secret pytest tests/test_connectors/test_defender_connector.py -x` (per-file — MEMORY.md `getvul-backend-pytest-env`: running the whole `tests/` directory at once produces false failures; per-file is required) |
| Full suite command | Same env vars, run each affected test file individually per the same memory note, not `pytest tests/` in one invocation |

**HTTP mocking convention** [VERIFIED across `test_crowdstrike_connector.py`, `test_wiz_connector.py`, etc.]: no `respx`/`pytest-httpx` dependency exists in this codebase. The established pattern is monkeypatching `httpx.AsyncClient.__init__` to transparently inject an `httpx.MockTransport(handler)` (see `_install_mock_transport` helper, reused verbatim across every connector test file). **New EPSS/KEV fetch tests should follow this exact convention**, not introduce a new mocking library.

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ENRICH-01 | EPSS score+percentile populated at `_upsert_vulnerability` for a finding from any of the 6 sources | integration (seeded `EpssScore` row + `db_session` fixture) | `pytest tests/test_connector_normalization.py -k epss -x` (new tests, existing file) | ❌ Wave 0 |
| ENRICH-02 | KEV-listed CVE → `cisa_kev=True` regardless of connector; Defender specifically flips from its old hardcode | integration (seeded `CisaKev` row) | `pytest tests/test_connector_normalization.py -k kev -x` | ❌ Wave 0 |
| ENRICH-03 | `native_priority_score`/`rating` populated per-connector's own fixture; DB-level sortability | unit (per-connector `_normalize_vuln`) + integration (`ORDER BY native_priority_score`) | `pytest tests/test_connectors/test_crowdstrike_connector.py -k exprt -x` (+ sibling files per connector) | ❌ Wave 0 (extends existing files) |
| ENRICH-04 | Missing vs. negative fixture — Defender's always-present `exploitVerified`/`publicExploit` booleans vs. its confirmed-absent VPR-equivalent | unit | `pytest tests/test_connectors/test_defender_connector.py -k source_signals -x` | ❌ Wave 0 |
| ENRICH-05 | 24h-gate + eager-first-run + atomic-swap-keeps-last-good | unit (scheduler dispatch, mirrors `test_scheduler_ai_batch.py`) + integration (transaction rollback proof) | `pytest tests/test_scheduler_enrichment_refresh.py -x` (new file, mirrors `test_scheduler_ai_batch.py`'s structure) | ❌ Wave 0 |
| ENRICH-06 | All 6 connectors' `_normalize_vuln` set the 3 new dataclass fields (even if `None` for Defender/Wiz — intentionally, not by omission/crash) | unit (parametrized across all 6, extends `test_connector_normalization.py`'s existing per-connector coverage-floor pattern) | `pytest tests/test_connector_normalization.py -x` | ✅ (extends existing file) |

### Sampling Rate
- **Per task commit:** the specific per-file quick-run command for whatever file(s) that task touched (per-file convention, not whole-suite).
- **Per wave merge:** run every touched test file individually (`test_connector_normalization.py`, all 6 `tests/test_connectors/test_*_connector.py` files, `test_scheduler_enrichment_refresh.py`, plus `test_connector_health.py`/`test_scheduler_ai_batch.py` as regression guards that the new scheduler function doesn't disturb the existing dispatch idioms).
- **Phase gate:** full suite green (per-file) before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_scheduler_enrichment_refresh.py` — new file, mirrors `test_scheduler_ai_batch.py`'s exact structure (24h-gate test, eager-first-run test, atomic-swap-keeps-last-good test via a monkeypatched fetcher that raises mid-parse)
- [ ] New EPSS/KEV fixture rows for `db_session` — a small, hand-authored 3-5-CVE fixture (not the full 355k/1.6k real feed) for integration tests
- [ ] SC#4 fixture design — recommend anchoring on **Defender** specifically: `exploitVerified`/`publicExploit` are confirmed-always-present booleans on its API [VERIFIED via Microsoft's own docs], and Defender has no VPR-equivalent field at all [VERIFIED absent] — this makes the "missing" half of the assertion (`'vpr' not in source_signals` or equivalent) a structurally guaranteed true negative, not a fixture-authoring accident
- [ ] No new test framework/config install needed — pytest/pytest-asyncio/httpx are already present

*(Framework install: none — existing test infrastructure covers all phase requirements; only new test files/fixtures are needed.)*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V1 Architecture | Yes | The global no-`tenant_id` exception (D-11) is a deliberate, signed-off architectural decision — document it explicitly in the migration's docstring (mirroring `034_add_correlation_sources.py`'s own precedent of explaining schema deviations inline) so it reads as intentional, not a missed convention, on future audit. |
| V5 Input Validation | Yes | Both external feeds are public and unauthenticated — treat every parsed row as untrusted input. Recommend a lightweight Pydantic model (`KevEntry`/`EpssRow`) to validate each row on parse, skipping (and logging) malformed individual rows rather than failing the entire batch on one bad row, OR failing the entire batch per D-09's "fully successful fetch+parse" wording (the CONTEXT.md decision explicitly favors all-or-nothing — recommend the latter, consistent with D-09, but cap the acceptable malformed-row tolerance at a low threshold, e.g., abort only if >X% of rows fail to parse, to avoid one single stray blank line aborting a legitimate refresh). |
| V12 File and Resources | Yes (network resource, not local file) | SSRF is **not applicable** here — the two feed URLs are hardcoded constants in the codebase, never derived from user/tenant input, so there is no attacker-controlled-URL vector to defend against. Worth stating explicitly to preempt a false-positive SSRF flag during a later security review. Do apply a reasonable response-size sanity cap (e.g., abort if decompressed EPSS content exceeds ~50MB) as a defensive measure against a compromised/malicious upstream serving an oversized payload that could exhaust memory on a single-VM deployment. |
| V8 Data Protection | Yes | The `source_signals` per-connector allowlist (D-08) is itself the control here — it is a curated allowlist specifically so that host/user/PII-shaped fields already modeled elsewhere (hostname, IPs, last_login_user, etc. — all already on `Vulnerability`/`Asset`) are never accidentally duplicated into this new JSONB blob. When building each connector's allowlist, explicitly exclude anything that overlaps `NormalizedVulnerability`'s existing PII-adjacent fields (`hostname`, `ip_addresses`, `last_login_user`, `serial_number`, etc.). |
| V7 Error Handling / Logging | Yes | D-09's `feed_refresh_failed` log flag must not leak upstream response bodies verbatim into logs (a malformed/adversarial feed response is untrusted content) — reuse the existing `_sanitize_error`-style truncation/redaction convention already established in `sync.py:41-59` for any exception message derived from feed-fetch failures, for consistency with how connector sync errors are already handled. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed/truncated external feed causing partial reference data | Tampering / Denial of Service | D-09's atomic-swap-only-on-full-success design is itself the mitigation — already locked in CONTEXT.md |
| Oversized or slow upstream response exhausting memory/time on a single-VM deployment | Denial of Service | `httpx` client-level timeout (already the convention: `httpx.Timeout(60.0)` used by every existing connector) + a sane response-size sanity check before `gzip.decompress`/`json.loads` |
| GraphQL schema-error from an incorrect Wiz field addition breaking the ENTIRE Wiz sync (not just the new fields) | Tampering (of a different, self-inflicted kind — a code-correctness risk, not an external attacker) | See Assumptions Log A4 — verify Wiz field names before shipping, or wrap in a query-level fallback |
| PII/host-identifying data leaking into `source_signals` via an overly broad allowlist | Information Disclosure | Curated allowlist (D-08) + explicit per-connector exclusion of already-modeled PII-adjacent fields (see V8 above) |

## Sources

### Primary (VERIFIED — direct tool execution, this session)
- Direct file reads: `backend/app/vulnerabilities/models.py`, `backend/app/connectors/{base,sync,scheduler,crowdstrike,nessus,defender,wiz,qualys,rapid7}.py`, `backend/app/vulnerabilities/{sla_service,correlation_service,router,schemas}.py`, `backend/app/assets/models.py`, `backend/app/db/base.py`, `backend/alembic/versions/034_add_correlation_sources.py`, `backend/pyproject.toml`, `backend/tests/test_connector_health.py`, `backend/tests/test_scheduler_ai_batch.py`, `backend/tests/test_connectors/test_crowdstrike_connector.py`, `backend/tests/test_connector_normalization.py`
- Live `curl`/download verification (2026-08-05): `https://epss.empiricalsecurity.com/epss_scores-current.csv.gz` (headers + full download + decompress + row count), `https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json` (headers + full download + schema inspection across all 1,660 entries)
- `grep`-based codebase-wide checks: `on_conflict_do_update`/`pg_insert` usage (3 call sites), `tenacity` usage (0 call sites), `respx`/`MockTransport` usage (6 connector test files), `epss`/`cisa_kev`/`KEV` mentions app-wide (confirmed zero prior EPSS/KEV code exists)

### Secondary (CITED — official documentation, WebFetch/WebSearch verified against an authoritative domain)
- [developer.crowdstrike.com Spotlight Vulnerabilities API reference](https://developer.crowdstrike.com/api-reference/collections/spotlight-vulnerabilities/) — `cve.exprt_rating` filter field confirmed
- [Microsoft Defender for Endpoint `vulnerability.md` schema (raw GitHub)](https://raw.githubusercontent.com/MicrosoftDocs/defender-docs/public/defender-endpoint/api/vulnerability.md) — full property list including native `EPSS`, `publicExploit`, `exploitVerified`, `exploitInKit`, `exploitTypes`, `exploitUris`
- [Microsoft Defender for Endpoint `get-recommendation-vulnerabilities.md`](https://raw.githubusercontent.com/MicrosoftDocs/defender-docs/public/defender-endpoint/api/get-recommendation-vulnerabilities.md) — confirms NO `exploitabilityLevel` field exists (corrects an initial hypothesis)
- [Tenable Nessus CVSS vs. VPR documentation](https://docs.tenable.com/nessus/Content/RiskMetrics.htm) — VPR concept confirmed, API schema not covered
- [Qualys — Understanding the Qualys Detection Score](https://qualysguard.qg2.apps.qualys.com/portal-help/en/vm/threat/understanding_the_qualys_detection_score.htm) / [Qualys API Best Practices: Host List Detection API](https://blog.qualys.com/product-tech/2021/07/09/qualys-api-best-practices-host-list-detection) — QDS 1-100 scale, `show_qds_factors` param concept
- FIRST.org EPSS: [Get the Data](https://www.first.org/epss/data), [EPSS API](https://www.first.org/epss/api) — corroborates the CSV URL/format independently verified live
- CISA KEV: [Known Exploited Vulnerabilities Catalog](https://www.cisa.gov/known-exploited-vulnerabilities-catalog), [cisagov/kev-data mirror](https://github.com/cisagov/kev-data) — corroborates the JSON schema independently verified live

### Tertiary (WebSearch synthesis only — flagged for validation, see Assumptions Log)
- CrowdStrike ExPRT numeric-score companion field (existence unconfirmed)
- Nessus VPR exact REST API field name (A1)
- Rapid7 `riskScore` exact field name and resource location (A2)
- Qualys QDS exact XML/JSON element name (A3)
- Wiz GraphQL `epssSeverity`/`epssPercentile`/`epssProbability`/`exploitabilityScore`/`impactScore` field existence (A4)

## Metadata

**Confidence breakdown:**
- External feed endpoints/schemas (EPSS, KEV): HIGH — verified via direct live download and inspection today, not just documentation
- Ingestion write-path architecture (single choke point, dataclass threading): HIGH — verified via direct code read, exact line numbers confirmed against CONTEXT.md's citations
- Scheduler wiring idiom: HIGH — verified via direct code read of 2 already-shipped instances of the same pattern (`_dispatch_ai_batch_prewarm`, ticket sync) plus their exact test file
- Per-connector native-priority field names (CrowdStrike/Nessus/Qualys/Rapid7): MEDIUM — concept and scale confirmed via official docs; exact JSON field name/path unconfirmed for 3 of 4 (flagged in Assumptions Log, all with documented soft-failure/verification paths)
- Defender/Wiz "no composite signal" finding: MEDIUM-HIGH for Defender (direct official schema fetch), MEDIUM for Wiz (WebSearch synthesis, not a primary schema document)
- Validation architecture: HIGH — every recommended test pattern mirrors an already-shipped, already-tested precedent in this exact codebase

**Research date:** 2026-08-05
**Valid until:** External feed schemas are stable/versioned (EPSS model_version, KEV catalogVersion) and unlikely to break — treat as valid ~90 days. Per-connector vendor API field names (the MEDIUM-confidence items) should be re-verified at implementation time regardless of this date, since they were never fully confirmed to begin with.
