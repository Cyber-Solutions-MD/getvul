# Stack Research

**Domain:** Scanner-signal enrichment + EPSS/KEV sourcing + source-aware filtering (GetVul v4.0)
**Researched:** 2026-08-04
**Confidence:** HIGH (verified against current source, current EPSS/KEV feed schemas, and existing pinned dependency versions)

## Context this research is scoped to

This is **not** a green-field stack pick. GetVul's backend is already Python 3.12 / FastAPI ≥0.115 / SQLAlchemy 2.0 async / Pydantic v2 / Alembic ≥1.14 / asyncpg / Postgres 16 / Redis 7, deployed as a single-VM Docker Compose stack with an in-process `asyncio` scheduler (no Celery/Arq — this is a standing Key Decision in `PROJECT.md`, not up for revisit this milestone).

Everything below is framed as **additive changes** to that stack: new columns, two new small reference tables, and code using libraries the backend already depends on. There is exactly **zero** new third-party runtime dependency required for this milestone — the existing `httpx`, `tenacity`, `orjson`, and stdlib `gzip`/`csv` cover it.

Two things read directly from source materially shaped this research:
- `backend/app/vulnerabilities/models.py`: `Vulnerability` already has typed `epss_score` (`Numeric(5,4)`), `exploit_available` (bool), `cisa_kev` (bool) columns, plus one `file_paths` JSONB column. There is **no existing catch-all JSONB column** on `Vulnerability` for arbitrary scanner-native signal payloads — `Asset.mdm_details JSONB` is the closest existing precedent for that pattern.
- `VulnerabilityCorrelation` (same file) has **explicit per-source FK columns** (`crowdstrike_vuln_id`, `nessus_vuln_id`, `defender_vuln_id`, `wiz_vuln_id`) but is **missing `qualys_vuln_id` and `rapid7_vuln_id`** — a real, pre-existing gap (Qualys/Rapid7 connectors were added later; `VulnSource` enum was extended for them in v1.0 Phase 4, but this table wasn't). Any "true multi-scanner corroboration" (the AND toggle) work in v4.0 walks straight into this gap and must close it.
- `backend/app/assets/models.py` already has a proven **`ARRAY(String)` + GIN index** pattern (`tags`, alembic `025_add_asset_tags`) for exactly the kind of set-membership filtering (`@>` contains-all / `&&` overlaps-with) that "OR default + AND toggle" scanner-source filtering needs. This is the strongest piece of existing evidence for how to build the new filtering — don't invent a new pattern, extend this one.

## Recommended Stack

### Core additions (schema-level, not new technology)

| Addition | Where | Purpose | Why this shape |
|----------|-------|---------|-----------------|
| `vulnerabilities.source_signals` (JSONB) | `Vulnerability` model, additive column | Catch-all for scanner-native fields that don't warrant their own column yet (ExPRT.AI rationale strings, Nessus VPR driver breakdown, Rapid7/Qualys vendor risk metadata, raw threat-intel flags) | Mirrors the proven `Asset.mdm_details JSONB` pattern already in this codebase — no new pattern to review |
| `vulnerabilities.vpr_score` (`Numeric(3,1)`), `vulnerabilities.exprt_rating` (`String(20)`), `vulnerabilities.exprt_score` (`Numeric(4,2)`) | `Vulnerability` model, additive typed columns | Promote the specific signals product/roadmap actually needs to **filter and sort on** to first-class typed columns | Matches the existing convention: `severity`, `cvss_v3_score`, `epss_score`, `exploit_available`, `cisa_kev` are already typed columns, not buried in JSON — a value you sort/filter by should be a column, not a JSONB path expression |
| `epss_scores` (new table: `cve_id` PK, `score` Numeric(5,4), `percentile` Numeric(5,4), `as_of_date` Date) | New Alembic migration | Global, tenant-independent EPSS reference data | EPSS scores are CVE-level facts, identical for every tenant. Storing them per-tenant means re-fetching/re-writing the same ~280k-row FIRST.org feed once per tenant on every sync — wasteful and pointless. **This is a deliberate, explicit exception to the "every domain table has `tenant_id`" rule** (CLAUDE.md constraint) because it is reference data, not a tenant-owned finding — flag this for roadmap/requirements sign-off |
| `cisa_kev` (new table: `cve_id` PK, `date_added` Date, `vendor_project`, `product`, `vulnerability_name`, `known_ransomware_use` Boolean, `due_date` Date, `notes` Text) | New Alembic migration | Global CISA KEV catalog mirror | Same rationale as above — one shared ~1,650-row catalog (verified `count: 1657` as of 2026-08-03), not per-tenant |
| A refresh job that re-derives `vulnerabilities.epss_score` / `cisa_kev` (existing columns) from the two new global tables via a batched `UPDATE ... FROM` | `backend/app/connectors/scheduler.py` | Keeps existing consumers (risk score, SLA, sort) working unchanged while sourcing truth from the fresh global feed instead of stale per-connector values | Reuses the exact 24h-gate timing idiom already in `_scheduler_loop()` (see `_dispatch_ai_batch_prewarm`'s documented pattern) — same file, same idiom, zero new infra |
| `vulnerability_correlations.qualys_vuln_id`, `.rapid7_vuln_id` (FK columns) | Additive migration, closes the pre-existing gap | Completes 6/6-source correlation | Was already missed once (v1.0 Phase 4 fixed the enum but not this table) — must be closed before AND-toggle corroboration logic can be correct for Qualys/Rapid7 |
| `vulnerability_correlations.sources` (`ARRAY(String)`) + GIN index, populated alongside the existing `sources_count`/`confidence` fields in `run_correlations()` | Additive migration + service change | O(1) set-membership queries backing both OR (`&&`, "overlaps with") and AND (`@>`, "contains all of") scanner-source filters | This is the **exact same pattern** as `assets.tags` (alembic `025_add_asset_tags`) — proven, already GIN-indexed in this codebase, same operators (`&&`/`@>`) do double duty for OR/AND without two separate index strategies |

### Supporting Libraries (all already dependencies — verify only, no `pip install`)

| Library | Version (pinned in `pyproject.toml`) | Purpose in v4.0 | When to use |
|---------|---------|---------|-------------|
| `httpx` | `>=0.27` (already used by every connector) | Fetch the EPSS daily CSV and the CISA KEV JSON feed | Both feeds are plain unauthenticated HTTP GETs — no SDK needed |
| `tenacity` | `>=9.0` (already a dependency, check usage — likely underused elsewhere) | Wrap the EPSS/KEV fetch in retry-with-backoff | Both feeds are external and occasionally flaky/rate-limited; `tenacity.retry(wait=wait_exponential(), stop=stop_after_attempt(3))` is the idiomatic use |
| `orjson` | `>=3.10` (already a dependency) | Parse the ~1,650-entry CISA KEV JSON payload fast | Already the project's JSON library elsewhere; no reason to use stdlib `json` for this one endpoint |
| `gzip` + `csv` (stdlib) | Python 3.12 stdlib | Decompress + parse the EPSS `epss_scores-current.csv.gz` (comment header + 3 columns: `cve`, `epss`, `percentile`) | No library beats stdlib for a 3-column CSV; adding a dependency here is pure overhead |
| `sqlalchemy.dialects.postgresql.insert(...).on_conflict_do_update(...)` | Already available via `sqlalchemy[asyncio]>=2.0` | Bulk upsert ~280k EPSS rows and ~1,650 KEV rows, chunked (e.g. 1,000 rows/statement) | Standard SQLAlchemy 2.0 async bulk-upsert idiom; avoids a per-row round trip for a quarter-million rows |
| `croniter` | `>=3.0` (already a dependency, used for scheduled reports) | Optional: express the EPSS/KEV refresh cadence as a cron string in config (e.g. daily at 14:00 UTC, after EPSS's ~13:30 UTC daily publish) instead of a bare interval-minutes gate | Only if you want operator-configurable cadence; a fixed 24h gate (matching the existing `_dispatch_ai_batch_prewarm` idiom) is simpler and sufficient if configurability isn't a real requirement |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| Existing Alembic migration flow | New tables (`epss_scores`, `cisa_kev`) + additive columns | Follow the numbered-file convention already in `backend/alembic/versions/` (next would be `034_...`) |
| Existing `pytest` + `httpx`-mock harness pattern (per `PROJECT.md` Phase 8 notes) | Test the EPSS/KEV fetch+parse+upsert path against a fixture CSV/JSON, not the live feed | The v1.0 audit already flagged connector tests needing an httpx-mock harness — reuse it for these two new fetchers rather than inventing a second mocking approach |

## Installation

No new packages. Confirm existing versions are already present (they are, per `backend/pyproject.toml` read 2026-08-04):

```bash
# Nothing to install — httpx, tenacity, orjson, croniter, sqlalchemy[asyncio], alembic
# are already pinned dependencies. Only new Alembic migration files are needed:

cd backend
alembic revision -m "add_source_signals_and_epss_kev_tables"
alembic revision -m "add_correlation_qualys_rapid7_and_sources_array"
```

## Alternatives Considered

| Recommended | Alternative | When to use the alternative |
|-------------|-------------|-------------------------|
| Global `epss_scores` / `cisa_kev` reference tables, refreshed once for all tenants | Store EPSS score / KEV flag inline per-tenant, fetched during each connector sync | Never, at this milestone's scale (single-VM, few tenants) — but if GetVul ever became true multi-tenant SaaS with per-tenant network egress isolation requirements, per-tenant fetch might become a compliance requirement, not just a performance question |
| `httpx` + stdlib `gzip`/`csv` direct feed fetch | A PyPI EPSS client (`epss-api`, `epss-checker`) or CISA KEV SDK | If the team wants CVE-level point lookups (single CVE → score) via `api.first.org/data/v1/epss?cve=...` interactively (e.g., an ad-hoc admin tool) rather than a bulk daily refresh — but bulk CSV/JSON is strictly better for a scheduled batch job over ~280k CVEs |
| `ARRAY(String)` + GIN (`&&`/`@>`) for `vulnerability_correlations.sources` | JSONB array + GIN with `?|`/`?&` operators on `assets.seen_by_sources` (already JSONB today) | If you don't want to touch the existing `seen_by_sources` column's type: leave it JSONB and add a GIN index (`jsonb_path_ops`) using it as-is with `?|` (OR) / `?&` (AND) — functionally equivalent, slightly less idiomatic than the `tags` precedent but zero migration risk to an existing populated column |
| Typed `vpr_score`/`exprt_rating`/`exprt_score` columns for filter/sort-critical signals + one JSONB catch-all for the rest | One large JSONB "raw scanner payload" column for everything, no new typed columns | If the roadmap decides these fields are display-only (never filtered/sorted/used in the risk model) — then a single JSONB blob is simpler and this milestone's "queryable per finding + per source" requirement would need re-scoping down to "displayable" |
| Reuse the existing in-process `asyncio` scheduler for the EPSS/KEV refresh, gated on a 24h timer | A dedicated APScheduler instance, or a Celery Beat task | Only if the single-VM/no-new-infra constraint is lifted — it currently isn't (explicit Key Decision) |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|--------------|
| Celery / Redis-as-broker task queue, Kafka, or any new message-queue infra | Explicitly out of scope per the single-VM Docker Compose constraint and the standing Key Decision ("In-process background scheduler (no Celery/Arq)") — this milestone doesn't need it: EPSS/KEV refresh is a once-daily HTTP GET + bulk upsert, not a high-throughput job queue problem | Extend the existing `_scheduler_loop()` in `backend/app/connectors/scheduler.py` with one more 24h-gated branch |
| A dedicated EPSS/KEV microservice or sidecar container | Adds a 6th+ Docker Compose service for what is, at most, a few hundred lines of fetch/parse/upsert code that runs once a day | A module inside the existing `backend/app/connectors/` package, invoked from the scheduler |
| Third-party EPSS Python client packages (`epss-api`, `epss-checker`, similar) | Small, thinly-maintained personal projects wrapping a 3-column CSV or a single-endpoint REST API that `httpx` + stdlib `csv` already handles in ~20 lines; adds a supply-chain dependency for near-zero value | `httpx.get(...)` + `gzip.decompress(...)` + `csv.reader(...)` |
| Elasticsearch / OpenSearch / a search-specific data store for scanner-source filtering | Postgres GIN indexes on `ARRAY`/`JSONB` columns already give O(log n) set-membership queries at this data scale (tens of thousands of findings per tenant, not billions) — this would be new infra with no scale justification | `ARRAY(String)` + GIN (matching the `tags` precedent), or JSONB + GIN as a fallback |
| TimescaleDB / a time-series extension for EPSS score history | Nothing in this milestone's scope (per `PROJECT.md`) asks for EPSS score trend-over-time; only "current" EPSS/KEV state feeds the risk model | Plain Postgres tables keyed by `cve_id`, overwritten on each refresh; if historical EPSS trending becomes a real requirement later, a simple `epss_scores_history` append-only table is enough — still no new extension |
| An EAV ("entity-attribute-value") generic signals table (`vuln_id, key, value` rows) | Tempting for "arbitrary per-scanner signals," but destroys indexability, makes every query an app-level join/pivot, and is a well-known anti-pattern for exactly this kind of heterogeneous-but-bounded data | The hybrid: typed columns for the handful of signals that are actually filtered/sorted (VPR, ExPRT rating/score) + one JSONB catch-all column (`source_signals`) for the long tail |
| NVD API / raw CVE feed ingestion as an EPSS/KEV substitute | Out of scope per `PROJECT.md` ("Scanner-less CVE feeds (NVD/OSV ingest without a scanner)" is explicitly Out of Scope — GetVul aggregates scanner output, not raw vuln intel) — and NVD doesn't provide EPSS or KEV data anyway, those are separate FIRST.org / CISA feeds | The two feeds researched here: `epss.empiricalsecurity.com` CSV and `cisa.gov/.../known_exploited_vulnerabilities.json` |
| Re-fetching EPSS/KEV per-tenant, per-connector-sync | Multiplies identical external HTTP calls by tenant count and by number of active connectors per tenant, for data that is identical across all of them — risks FIRST.org/CISA rate-limiting a single-VM install with several tenants | One global refresh job, decoupled from per-connector sync timing, whose output (`epss_scores`, `cisa_kev` tables) every tenant's recompute reads from |

## Stack Patterns by Variant

**If the roadmap wants EPSS/KEV data available immediately after a fresh `install.sh` deploy (cold start):**
- Run the refresh job once synchronously at first application startup (in addition to the daily gate), guarded so it doesn't block app readiness — mirror the existing `configure_logging()`-runs-first-in-lifespan pattern, but as a fire-and-forget `asyncio.create_task`, not a blocking `await`.
- Because both feeds are unauthenticated and public, no new env var / credential is needed — satisfies the "sensible defaults for any new env var" `install.sh` constraint by requiring none.

**If the team wants the refresh cadence operator-configurable (not just a fixed 24h gate):**
- Add one new env var (e.g. `EPSS_KEV_REFRESH_INTERVAL_MINUTES`, default `1440`) read via the existing `pydantic-settings` `Settings` class, and gate on it the same way `connector.sync_interval_minutes` already gates per-connector syncs in `_scheduler_loop()`. Don't introduce `croniter` unless real cron-expression flexibility (e.g. "only refresh on weekdays") is an actual requirement — a bare interval is simpler and matches the existing per-connector precedent more closely than a cron string would.

**If cross-source AND-corroboration ("2+ scanners agree") needs to extend beyond Vulnerabilities to CSPM findings:**
- `Misconfiguration` (in `backend/app/cspm/models.py`) has no correlation table equivalent today — it's dedup'd by `(tenant_id, rule_id, resource_id, source)` directly, one row per source, no cross-source merge. Building AND-toggle corroboration there would require either (a) a new `misconfiguration_correlations` table mirroring `vulnerability_correlations`'s new `sources ARRAY` shape, or (b) a `GROUP BY resource_id, rule_id HAVING array_agg(source) @> ...` query computed on read rather than materialized. Given CSPM findings are typically resource+rule keyed (not CVE-keyed), and this milestone's stated CSPM requirement is source **filtering**, not corroboration, start with OR-only filtering on the existing indexed `source` column and defer AND-corroboration modeling for CSPM to a follow-up phase if the requirement is confirmed to extend that far.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `sqlalchemy[asyncio]>=2.0` | `ARRAY(String)` + `postgresql_using="gin"` index, `JSONB`, `postgresql.insert(...).on_conflict_do_update(...)` | All three are already exercised elsewhere in this codebase (`assets.tags`, `assets.mdm_details`, and the connector upsert pattern in `sync.py`) — no new compatibility surface |
| `asyncpg>=0.30` | Postgres 16 `ARRAY`/`JSONB`/GIN | Already the driver in production; no version bump needed |
| `alembic>=1.14` | Two new tables + additive columns + new indexes | Purely additive migrations — no downgrade complexity beyond `drop_table`/`drop_column`, matching the existing `025_add_asset_tags.py` style |
| EPSS daily CSV feed | No auth, no version pinning needed — URL is stable (`epss.empiricalsecurity.com/epss_scores-current.csv.gz`) | Verified live 2026-08-04: 3-column CSV (`cve`, `epss`, `percentile`), refreshed daily ~13:30 UTC |
| CISA KEV JSON feed | `catalogVersion` field increments per release (e.g. `"2026.08.03"`) — not a package version, just a payload marker | Verified live 2026-08-04: `count: 1657`, updated continuously (not a fixed schedule) — refresh job should treat "no new entries since last check" as the normal case, not an error |

## Sources

- Direct source read (HIGH confidence): `/Users/chemencedji/Desktop/getvul/backend/app/vulnerabilities/models.py`, `/Users/chemencedji/Desktop/getvul/backend/app/assets/models.py`, `/Users/chemencedji/Desktop/getvul/backend/app/assets/risk_score.py`, `/Users/chemencedji/Desktop/getvul/backend/app/connectors/{base,crowdstrike,nessus,sync,scheduler}.py`, `/Users/chemencedji/Desktop/getvul/backend/app/cspm/models.py`, `/Users/chemencedji/Desktop/getvul/backend/app/ticketing/models.py`, `/Users/chemencedji/Desktop/getvul/backend/alembic/versions/025_add_asset_tags.py`, `/Users/chemencedji/Desktop/getvul/backend/pyproject.toml`
- [FIRST.org EPSS API](https://www.first.org/epss/api) — MEDIUM/HIGH, endpoint + bulk-CSV shape confirmed via web search, cross-checked against FIRST.org's own data page
- [FIRST.org EPSS — Get the Data](https://www.first.org/epss/data) — daily CSV URL and cadence (~13:30 UTC daily) confirmed
- CISA KEV JSON feed (`https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json`) — HIGH, fetched live 2026-08-04, exact top-level (`catalogVersion`, `dateReleased`, `count`) and per-entry (`cveID`, `vendorProject`, `product`, `vulnerabilityName`, `dateAdded`, `shortDescription`, `requiredAction`, `dueDate`, `knownRansomwareCampaignUse`, `notes`, `cwes`) schema verified directly against the live feed, not training data
- [CISA Known Exploited Vulnerabilities Catalog](https://www.cisa.gov/known-exploited-vulnerabilities-catalog) — HIGH, official source confirming CSV/JSON/JSON-Schema availability and real-time (not batch-scheduled) update model
- PyPI EPSS client packages (`epss-api`, `epss-checker`) — LOW confidence on maintenance quality, surfaced only to explicitly rule out as unnecessary given `httpx` + stdlib already covers the need

---
*Stack research for: GetVul v4.0 — Enriched Risk Exposure & Source-Aware Triage*
*Researched: 2026-08-04*
