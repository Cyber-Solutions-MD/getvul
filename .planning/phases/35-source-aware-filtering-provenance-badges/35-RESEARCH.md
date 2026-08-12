# Phase 35: Source-Aware Filtering & Provenance Badges - Research

**Researched:** 2026-08-12
**Domain:** Backend query design (Postgres ARRAY `@>`/`&&` operators, JSONB `.contains()`), FastAPI filter schemas, batched-fetch N+1 prevention, React/Next.js filter chip-bar UI, provenance badge visual design. FINAL phase of v4.0 — no new external dependencies.
**Confidence:** HIGH for existing-code reconnaissance (everything below is read directly, file:line cited, several genuinely surprising findings verified by direct grep — not inferred). MEDIUM for the new CSPM grouping design and the SourceBadgeGroup visual spec (both are genuinely new mechanisms with no exact precedent in this codebase, but each synthesizes an already-shipped sibling pattern). LOW/flagged-assumption only on the ticket "defined rule for multi-source-correlated cases" (SRC-07) — the requirement asks for a rule that must be *invented*, not discovered, so it is logged as an assumption for user/planner confirmation.

## Summary

This phase closes v4.0 by making scanner provenance honest and filterable across 4 entities that today have **four different, mutually inconsistent** implementations of "source" — and at least one of them is a real bug already shipping AND-when-it-should-be-OR semantics. Concretely: **Vulnerabilities** filter with `Vulnerability.source.in_(filters.source)` (`service.py:40-41`) — pure OR across per-source ROWS (not deduplicated findings), and completely ignores the Phase 30 `VulnerabilityCorrelation.sources` ARRAY that already exists and is GIN-indexed for exactly this purpose. **Assets** filter with a `for s in scanners: query.where(Asset.seen_by_sources.contains([s]))` loop (`assets/router.py:157-159`, duplicated in `ticketing/rule_engine.py:71-73`) — each `.where()` call ANDs onto the query, so today's "select CROWDSTRIKE, NESSUS" silently means "asset must be seen by BOTH," the exact opposite of Vulnerabilities' OR default and the exact opposite of what SRC-03 requires. **CSPM** filters with `Misconfiguration.source.in_(filters.source)` (`cspm/service.py:32-33`) — OR-only, and there is no grouping concept at all across tools for the same finding (no `MisconfigurationCorrelation` table exists; `Misconfiguration`'s own `UniqueConstraint(tenant_id, rule_id, resource_id, source)` at `cspm/models.py:48` already proves the same (resource, rule) pair produces one row PER TOOL when multiple CSPM tools flag it — the grouping key already exists as a unique constraint, it is simply never queried as a group). **Tickets** have no source concept at all today — `Ticket` (`ticketing/models.py:79-103`) links to exactly one `Vulnerability` row via a required `vulnerability_id` FK, and `TicketResponse`/`TicketSummary` (`ticketing/schemas.py:13-47`) already join `cve_id`/`severity`/`hostname` off that single vuln but never `source`.

The most important existing-code fact this research surfaces is that **the correlation-array batching precedent already exists and is production-proven**: `risk_exposure_service.compute_finding_risk_scores` (`risk_exposure_service.py:320-345`) does a single tenant-scoped `select(VulnerabilityCorrelation.cve_id, .asset_id, .sources_count).where(tenant_id == ...)`, builds a `dict[(cve_id, asset_id) -> sources_count]` in Python, then does O(1) dict lookups per row — zero N+1. This is the exact shape Phase 35 needs for `SourceBadgeGroup` batching on the Vulnerabilities list (SRC-08) and it should be extended (not reinvented) to also carry the `sources` array itself, not just the count. A second, independent batching precedent lives in `ticketing/service.py:849-853` (WR-05): the ticket list used to run one detail aggregate per grouped row, and was rewritten to "batch ALL per-URL detail aggregates into ONE query keyed by external_ticket_url" — this is the direct precedent for batching per-ticket provenance resolution (SRC-07 + SRC-08 combined).

A second load-bearing fact: **`VulnerabilityCorrelation` rows only exist when 2+ sources see the same (cve_id, asset_id) pair** — `correlation_service._find_correlated_groups` (`correlation_service.py:141`) filters `{k: v for k, v in groups.items() if len(v) >= 2}` before any correlation row is ever written. A single-source finding has **zero** correlation row, by design. Every consumer this phase touches (list badges, filters, ticket provenance) must treat "no correlation row" as "single source = `[vuln.source]`," never as "unknown" or an error — this is also precisely why SRC-01's "never imply confirmed from a single scanner" is enforceable structurally: the absence of a correlation row IS the single-source signal.

A third, more subtle fact with real blast-radius: `backend/app/enrich_assets.py:134` is a standalone `if __name__ == "__main__"` script (not called from the scheduler, only referenced by `tests/test_tenant_isolation.py`) that **overwrites** `asset.seen_by_sources` with a dict shape (`{"CROWDSTRIKE": {...}}`), discarding whatever list of sources was there before and breaking the `.contains([s])` list-shape assumption every other reader relies on. It is dead/manual-only code today, but Phase 35 must not model its new Assets-partition logic on this script's shape, and the planner should flag (not necessarily fix, but at minimum not extend) this landmine.

**Primary recommendation:** For Vulnerabilities and Assets, add a `source_mode: Literal["or","and"] = "or"` filter field (mirroring the existing `order: Literal["asc","desc"]` field shape in `VulnerabilityFilter`, `schemas.py:134`) that branches between `VulnerabilityCorrelation.sources.overlap(filters.source)` (OR / `&&`) and `VulnerabilityCorrelation.sources.contains(filters.source)` (AND / `@>`), joined from `Vulnerability` via `(cve_id, asset_id)` — with an explicit fallback clause for single-source findings (no correlation row) so OR-mode still matches them via `Vulnerability.source.in_(...)` directly, and AND-mode with 2+ selected sources structurally never matches a single-source finding (a real corroboration requirement, not a bug). For Assets, fix the existing AND-when-selecting-multiple bug by switching from N chained `.where(.contains([s]))` calls to a single `or_(*[.contains([s]) for s in scanners])` for OR-mode (default) and keep the existing chained-AND shape for AND-mode (it already computes true AND — it just should not be the unconditional default), and partition `scanner` vs `enrichment` (JAMF/HUMAANS/INTUNE) into two distinct filter axes/params so an enrichment source can never leak into a scanner-source filter's OR/AND semantics (SRC-06). For CSPM, add a new `MisconfigurationCorrelation`-style grouping — either a lightweight computed GROUP BY on `(tenant_id, rule_id, resource_id)` with `array_agg(DISTINCT source)` (no new table, cheaper migration, recommended given CSPM's smaller data volumes and lack of an existing correlation-maintenance job) or a persisted table mirroring `VulnerabilityCorrelation` (higher consistency with the vuln pattern, more machinery) — the planner must choose; this research recommends the computed-GROUP-BY approach and documents why in Pitfall 2. For Tickets, resolve provenance transitively by batching: collect the page's `vulnerability_id`s, bulk-fetch their `(cve_id, asset_id, source)`, then bulk-fetch matching `VulnerabilityCorrelation` rows exactly like `risk_exposure_service.py:320-345` already does, and render `SourceBadgeGroup` using the correlation's `sources` array when present, else `[vuln.source]`. For the new UI, `SourceBadgeGroup` is a new component but every visual primitive it needs already exists: `ProviderMark`'s gradient-square-per-source pattern (`provider-mark.tsx`), the severity-pill/KEV-badge tinted-pill chrome (`visual-language.md`), and the `ChipBar`'s existing multi-select toggle machinery (`ChipBar.tsx`) plus a new sibling `useUrlState`-backed boolean for the AND toggle (mirroring the existing `?order=asc|desc` single-value URL param, not a new hook).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| OR/AND source filter (Vulnerabilities) | API / Backend (`app/vulnerabilities/service.py` `_apply_filters`, schemas.py `VulnerabilityFilter`) | Database (`vulnerability_correlations.sources` GIN index) | Query-building branch on `filters.source_mode`, same shape as existing `filters.sort ==` chain |
| OR/AND source filter (Assets) | API / Backend (`app/assets/router.py` list_assets query builder) | Database (`assets.seen_by_sources` JSONB) | Fixes existing AND-bug; partitions scanner vs enrichment sources |
| CSPM multi-tool AND corroboration | API / Backend (`app/cspm/service.py`, new grouping query) | Database (`misconfigurations` — existing `(rule_id, resource_id)` uniqueness key, no schema change if computed-GROUP-BY approach chosen) | New concept; no existing table models this — computed at query time from the existing unique-constraint key |
| Ticket transitive provenance | API / Backend (`app/ticketing/service.py` list_tickets / get_ticket) | Database (`vulnerability_correlations` join via `vulnerability_id -> cve_id/asset_id`) | Batched bulk-fetch, mirrors WR-05 (`ticketing/service.py:849-853`) and `risk_exposure_service.py:320-345` |
| `SourceBadgeGroup` rendering | Browser / Client (new component under `components/vulnerabilities/`, reused by assets/cspm/tickets surfaces) | API / Backend (batched provenance payload) | Pure presentational; consumes server-computed `sources`/`sources_count`/`confidence`-shaped data, never infers "confirmed" client-side |
| Scanner-source filter chip UI + AND toggle | Browser / Client (`ChipBar.tsx`, `chip-bar.tsx`, `assets-chip-bar.tsx`, new CSPM/tickets chip-bar callers) | API / Backend (`?source=&source_mode=`) | Extends existing `useUrlStateList` (source values) + new `useUrlState` boolean (AND toggle), same URL-state pattern already used for `?order=` |
| Batched provenance/facet queries (no N+1) | API / Backend (all 4 services above) | — | Single bulk `dict[(key) -> value]` lookup pattern, precedent: `risk_exposure_service.py:320-345`, `ticketing/service.py:849-853` |

## Project Constraints (from CLAUDE.md)

Directives extracted from `./CLAUDE.md` that apply to this phase's work:

- **Frontend stack lock:** Next.js 15 App Router + React 19 + TypeScript 5.5 + Tailwind 3.4 — `SourceBadgeGroup` and all chip-bar changes must use these, no new frontend framework/library.
- **Backend stack lock:** FastAPI + Postgres + Redis — no new datastore for CSPM grouping or correlation batching (this research's computed-GROUP-BY recommendation honors this; a new persisted table alternative would still stay within Postgres).
- **Font lock:** Inter + JetBrains Mono only — any new `SourceBadgeGroup` text (mono CVE-style labels, source codes) must use the existing font tokens, no substitution.
- **No freehand hex colors:** Any new badge color (see Pitfall 4 / Assumption A3) MUST resolve through a CSS variable from `sketch-findings-getvul`'s `foundation.md`, never a hardcoded hex — and since no existing token currently means "corroboration," this is an explicit gap to flag to the user/discuss-phase step rather than inventing an ad hoc hex value.
- **No screen ships without empty/loading/error states:** Any new `SourceBadgeGroup`-bearing list view or CSPM grouping UI must follow `state-patterns.md` (mandatory in production) — a page with zero corroborated findings, or a CSPM grouping query returning nothing, needs an explicit empty state, not a blank badge column.
- **No generic SaaS copy:** Any new badge/toggle microcopy (e.g. the AND-toggle label, "single source" vs "N sources" labels) must follow `copy-voice.md` tone rules — avoid generic phrasing like "Confirmed by multiple sources!" (also independently forbidden by SRC-01's "never imply confirmed" requirement — the two constraints reinforce each other here).
- **`sketch-findings-getvul` skill must be read before any frontend UI task** (per CLAUDE.md's "Skills" section) — `references/visual-language.md` for badge/pill chrome, `references/interaction-patterns.md` for the chip-bar/filter-toggle interaction shape, `references/state-patterns.md` for the new empty/loading/error states this phase's new UI needs.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SRC-01 | Every finding row shows a source-provenance badge indicating which scanner(s) reported it, visually distinguishing single-source from multi-source-corroborated (never implies "confirmed" from a single scanner) | "Existing-Code Reconnaissance §1, §8" (confirms zero existing badge/display), "Architecture Patterns → System Architecture Diagram + Pattern 1" (batched data the badge consumes), "Pitfall 4, 5, 6" (visual/data-correctness pitfalls), "Assumption A3" (color mapping needs sign-off) |
| SRC-02 | A scanner-source filter is available on Vulnerabilities, Assets, CSPM, and Tickets | "Existing-Code Reconnaissance §1, §4, §5, §6" (current per-entity state), "Architecture Patterns → Pattern 2, 3" |
| SRC-03 | Selecting multiple sources defaults to OR | "Existing-Code Reconnaissance §1 (already OR for Vulns/CSPM), §4 (Assets is WRONGLY AND today — must fix)", "Pattern 2, 3" |
| SRC-04 | AND toggle filters to findings corroborated by all selected scanners (Vulnerabilities/Assets via `@>`) | "Reconnaissance §2 (GIN index + ARRAY basis)", "Pattern 2", "Pitfall 1" (AND with <2 sources edge case) |
| SRC-05 | CSPM supports true multi-tool AND corroboration via a new resource+rule-id grouping concept, not silent OR | "Reconnaissance §5 (existing `uq_misconfig_dedup` grouping key, no query uses it today)", "Standard Stack § Alternatives Considered (computed GROUP BY vs persisted table)", "Pitfall 2", "Don't Hand-Roll" |
| SRC-06 | Assets source filter partitions scanner sources from non-scanner enrichment sources (JAMF/HUMAANS/Intune) | "Reconnaissance §4 (verified writer sites for JAMF/HUMAANS/INTUNE)", "Pattern 3" |
| SRC-07 | Ticket source provenance resolves transitively through the linked vulnerability's correlation, defined rule for multi-source-correlated cases | "Reconnaissance §6 (Ticket→Vulnerability FK shape, WR-05 batching precedent)", "Assumption A4" (the exact combination rule needs sign-off) |
| SRC-08 | Provenance and source-facet queries are batched (no per-row N+1), provable with a query-count assertion | "Reconnaissance §3 (existing bulk-dict-lookup precedent)", "Pattern 1, Pitfall 2", "Validation Architecture → Phase Requirements → Test Map (new query-count harness, Wave 0 gap)" |
</phase_requirements>


## Standard Stack

No new libraries. This phase is entirely additive query logic (SQLAlchemy Postgres ARRAY/JSONB operators, already imported), Pydantic filter fields, and React/Tailwind components using existing primitives.

### Core (already in use, verified in this codebase)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy | 2.0.50 [VERIFIED: `backend/.venv` `python -c "import sqlalchemy; print(sqlalchemy.__version__)"`] | `ARRAY.contains()` / `.overlap()` compiled to Postgres `@>`/`&&` | Already used identically for `assets.tags` (Phase 12) and `vulnerability_correlations.sources` (Phase 30/33) |
| FastAPI | 0.136.3 [VERIFIED: same command] | Query param binding, Pydantic filter models | Existing pattern throughout `router.py` files |
| Next.js / React | 15 / 19 [CITED: `CLAUDE.md` project conventions] | Frontend chip-bar + new `SourceBadgeGroup` | Existing app shell |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Computed GROUP BY for CSPM corroboration | A persisted `MisconfigurationCorrelation` table (mirrors `VulnerabilityCorrelation` 1:1) | Persisted table needs a maintenance job (mirroring `correlation_service.run_correlations`, itself only invoked per-sync — see `connectors/sync.py`); CSPM findings today have no equivalent recorrelation trigger wired anywhere, so a new persisted table would need a brand-new scheduler hook. A computed `GROUP BY (tenant_id, rule_id, resource_id)` with `array_agg(DISTINCT source)` needs zero new maintenance machinery and is correct-by-construction (always reflects current `Misconfiguration` rows), at the cost of doing the aggregation at read time instead of write time. Given CSPM's likely much smaller per-tenant row count than Vulnerabilities (cloud resources, not every host x CVE), read-time aggregation is very likely cheap enough — recommend computed, flagged MEDIUM confidence pending an actual row-count check against a real tenant's CSPM data (not available in this research pass; ASSUMED, see Assumptions Log A2). |
| New `useToggle`/Switch component for the AND toggle | Reuse the existing chip-button (`aria-pressed`) pattern from `ChipGroup` (`ChipBar.tsx:126-158`) as a single non-multi-select boolean chip | No Switch/Toggle primitive exists anywhere in `components/ui/` (verified: `find components/ui -iname "*switch*" -o -iname "*toggle*"` → empty). Building a bespoke Switch for one boolean is more surface area than reusing the chip-button visual language the analyst already recognizes from severity/source chips. |

## Existing-Code Reconnaissance

### 1. Vulnerabilities — current source filter is per-row OR, ignores the correlation ARRAY

`backend/tests/test_vuln_source_filter.py:1-11` documents the CURRENT behavior explicitly (Phase 04 origin, predates Phase 30's correlation ARRAY entirely): `GET /api/v1/vulnerabilities?source=QUALYS` returns only QUALYS rows; a second value (`?source=X&source=Y`) is never exercised by any existing test.

`backend/app/vulnerabilities/schemas.py:104`: `source: list[str] | None = Field(None, max_length=10)` — **already a list**, capped at 10.

`backend/app/vulnerabilities/service.py:40-41`:
```python
if filters.source:
    query = query.where(Vulnerability.source.in_(filters.source))
```
This is `.in_()` — pure SQL `IN`, i.e. OR across values, applied to the per-source-ROW `Vulnerability.source` column (`models.py:64`, `String(30)`), NOT the correlation ARRAY. Because `Vulnerability` has `UniqueConstraint(tenant_id, cve_id, asset_id, source)` (`models.py:49`), a CVE seen by both QUALYS and RAPID7 on one asset produces **two separate `Vulnerability` rows**. Filtering `?source=QUALYS&source=RAPID7` today returns BOTH rows as two separate list items — it does not deduplicate to one "finding," and it provides no way to express "must be seen by both" (true AND/corroboration) at all. This is the literal SRC-04 gap: there is no AND semantics today, anywhere, for Vulnerabilities.

`get_vulnerability` (single-item GET, `service.py:193-256`) already reads `VulnerabilityCorrelation.sources_count` (line 213-221) for the detail view — but the **list** endpoint (`list_vulnerabilities`, `service.py:70-190`) does not join or return anything correlation-related; `VulnerabilitySummary` (`schemas.py:74-90`) has no `sources`/`sources_count`/`correlation` field at all. **This is the literal SRC-01 gap** — no list row can show a `SourceBadgeGroup` today because the list query never fetches correlation data.

### 2. `vulnerability_correlations.sources` — the ARRAY + GIN basis for `@>`/`&&`

`backend/app/vulnerabilities/models.py:106-123`:
```python
class VulnerabilityCorrelation(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "vulnerability_correlations"
    __table_args__ = (UniqueConstraint("tenant_id", "cve_id", "asset_id", name="uq_correlation"),)
    tenant_id: Mapped[uuid.UUID] = mapped_column(...)
    cve_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    asset_id: Mapped[uuid.UUID] = mapped_column(..., ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    sources: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    source_vuln_ids: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    sources_count: Mapped[int] = mapped_column(Integer, default=1)
    confidence: Mapped[str] = mapped_column(String(10), default=Confidence.LOW.value)
```
GIN index: `backend/alembic/versions/034_add_correlation_sources.py:36-41` — `op.create_index("ix_vulnerability_correlations_sources", "vulnerability_correlations", ["sources"], postgresql_using="gin")`. This is the exact GIN precedent (mirrors `assets.tags`, `025_add_asset_tags.py`, per the migration's own docstring) that makes `sources.contains([...])` (`@>`) and `sources.overlap([...])` (`&&`) index-scan-able rather than seq-scans.

**Critical gap:** `_find_correlated_groups` (`correlation_service.py:101-141`) only considers `Vulnerability.status.in_(["OPEN", "IN_PROGRESS"])` (line 122) and filters to `len(v) >= 2` groups (line 141) — **single-source findings never get a `VulnerabilityCorrelation` row**, and **remediated/suppressed/false-positive findings' correlations are pruned** (`_prune_stale_correlations`, lines 144-167, runs every `run_correlations()` call and deletes any correlation whose (cve_id,asset_id) is no longer in the active OPEN/IN_PROGRESS group set). This means: (a) any OR/AND filter design MUST handle "no correlation row exists" as "treat as single-source, `[vuln.source]`" — never as null/error; (b) a REMEDIATED finding that was previously multi-source-corroborated **loses its correlation row** the next time `run_correlations` runs, so a `SourceBadgeGroup` on a closed/remediated finding can silently regress from "3-source corroborated" to "single source (no correlation)" purely because of status change, not because scanners stopped seeing it. This is a genuine design decision the planner must make explicitly (Assumptions Log A1): either (1) accept this as correct ("badges reflect current corroboration among still-open findings only"), or (2) change `_prune_stale_correlations`/`_find_correlated_groups` to stop excluding closed statuses — which is an existing-Phase-30-behavior change, out of this phase's stated scope unless the planner explicitly takes it on.

`get_correlation_for_vuln` (`correlation_service.py:170-193`) is the existing single-row lookup helper — useful as a reference shape but must NOT be called per-row in a list (that would be exactly the N+1 SRC-08 forbids); the batched dict-lookup shape from `risk_exposure_service.py` (below) is the correct model to extend instead.

### 3. The proven batching precedent — `risk_exposure_service.py:320-345`

```python
# risk_exposure_service.py:320-345 (paraphrased structure, verified read)
corr_rows = (
    await db.execute(
        select(
            VulnerabilityCorrelation.cve_id,
            VulnerabilityCorrelation.asset_id,
            VulnerabilityCorrelation.sources_count,
        ).where(VulnerabilityCorrelation.tenant_id == tenant_id)
    )
).all()
corr_by_key = {(row.cve_id, row.asset_id): row.sources_count for row in corr_rows}
...
sources_count = corr_by_key.get((vuln.cve_id, vuln.asset_id), 1)
```
This is a **single tenant-wide bulk-select**, not scoped to the current page — acceptable for a background batch job (`compute_finding_risk_scores` runs once per sync), but for the interactive list endpoint (`list_vulnerabilities`) the equivalent bulk-select MUST be scoped to only the `(cve_id, asset_id)` pairs present in the CURRENT PAGE (after `.offset().limit()`), not the whole tenant — otherwise a large tenant's list page fetches a whole-tenant correlation table on every request. Recommended shape: fetch the page's rows first, collect `{(v.cve_id, v.asset_id) for v in page_rows if v.cve_id and v.asset_id}`, then one `select(VulnerabilityCorrelation).where(tenant_id==..., tuple_(cve_id, asset_id).in_(list_of_pairs))` (SQLAlchemy `tuple_()` composite IN, verify Postgres compiles this to a real `IN ((a,b),(c,d))` — standard Postgres feature, well-supported by SQLAlchemy 2.0) — exactly 2 queries per page load (1 for vulns, 1 for correlations), regardless of page size. This is the concrete anti-N+1 design for SRC-08 on Vulnerabilities.

### 4. Assets — `seen_by_sources` and the ALREADY-BROKEN AND-when-OR-expected filter

`backend/app/assets/models.py:57`: `seen_by_sources: Mapped[dict | None] = mapped_column(JSONB, default=list)` — JSONB column (not ARRAY — inconsistent with `tags` which is `ARRAY(String)` + GIN, `models.py:103`), storing a JSON array like `["CROWDSTRIKE", "NESSUS"]` in the normal write path. **No GIN index exists on `seen_by_sources`** (verified: `grep` across every migration file for `seen_by_sources` + `gin` finds nothing; only the `001_initial_schema.py:65` column definition with `server_default="[]"`). This is a genuine performance gap the planner should address if scanner-source filtering on Assets becomes a common query pattern — recommend a new migration adding a GIN index on `seen_by_sources` (jsonb_path_ops or default gin) as part of this phase, mirroring `034_add_correlation_sources.py`'s `postgresql_using="gin"` shape.

**The AND bug** — `backend/app/assets/router.py:154-159`:
```python
if scanner:
    scanners = [s.strip().upper() for s in scanner.split(",") if s.strip()]
    for s in scanners:
        query = query.where(Asset.seen_by_sources.contains([s]))
```
Each loop iteration calls `.where()` again — SQLAlchemy ANDs successive `.where()` calls on the same `Select`. So `?scanner=CROWDSTRIKE,NESSUS` today means "asset must be seen by CROWDSTRIKE **AND** NESSUS," not "by either" — the **opposite** of Vulnerabilities' `.in_()` OR default and the opposite of what SRC-03 (OR-default) requires. The IDENTICAL bug is duplicated in `backend/app/ticketing/rule_engine.py:71-73` (ticket-automation-rule asset matching, same for-loop-of-`.where()` shape) — out of this phase's stated entity list (Vulnerabilities/Assets/CSPM/Tickets means "ticket PROVENANCE," not "ticket-rule asset matching"), but the planner should flag it as a related pre-existing bug the same fix could cheaply also correct, or explicitly note as deferred.

**The scanner/enrichment source values that actually get written**, verified via direct grep of every writer:
- `connectors/sync.py:251,275-277` — generic scanner sync path: `seen_by_sources=[source]` on create, `sources + [source]` (append, dedupe-checked) on update. `source` here is a `VulnSource` value (CROWDSTRIKE/NESSUS/DEFENDER/WIZ/QUALYS/RAPID7).
- `connectors/jamf_sync.py:166,199-203` — `seen_by_sources=["JAMF"]` / appends `"JAMF"`.
- `connectors/humaans_sync.py:210-214` — appends `"HUMAANS"`.
- `connectors/intune_sync.py:106-111` — ensures `"INTUNE"` is present (via `sources = asset.seen_by_sources or []`; exact append logic reads a pre-existing list check, not shown length-limited here but confirmed non-destructive).

So the true value universe today is `{CROWDSTRIKE, NESSUS, DEFENDER, WIZ, QUALYS, RAPID7}` (scanner/`VulnSource` values) unioned with `{JAMF, HUMAANS, INTUNE}` (enrichment/non-scanner values) — all coexisting in the SAME `seen_by_sources` JSONB array on one asset. **SRC-06's partition requirement is therefore a pure filtering/UI concern, not a data-model concern** — the data already commingles both categories in one field; the fix is to define a `SCANNER_SOURCES` vs `ENRICHMENT_SOURCES` constant partition (mirroring the frontend's existing hardcoded `SOURCES` allow-list pattern, see Pitfall 3) and expose them as two separate filter axes/params (e.g. `?scanner=` for the scanner-only OR/AND filter per SRC-02/03/04, and a separate `?enrichment_source=` or similar for JAMF/HUMAANS/INTUNE, which SRC-06 implies should NOT get OR/AND corroboration semantics — it is just a facet, not a scanner-source filter).

**Data-corruption landmine (dead code, not in the request path):** `backend/app/enrich_assets.py:130-141` — a standalone script (`if __name__ == "__main__"` at line 187) does:
```python
asset.seen_by_sources = {
    "CROWDSTRIKE": {"product_type_desc": ..., "platform_name": ..., ...}
}
```
This **replaces** the whole field with a dict (not a list, not an append) — if this script is ever run against a real tenant, it destroys every other source's membership in `seen_by_sources` and changes the field's runtime shape from `list[str]` to `dict[str, dict]`, silently breaking every `.contains([s])` call (a JSONB `.contains()` on a dict behaves differently than on a list — `{"a": {...}}.contains(["a"])` is False; dict-containment needs `.contains({"a": ...})` instead). Verified: this script is referenced only by `tests/test_tenant_isolation.py` and is never invoked from `connectors/scheduler.py` (grep confirms zero matches) — it is dead/manual-only, but Phase 35 should not deepen any dependency on `enrich_assets.py`'s shape and the planner may want to flag it for a follow-up fix (out of this phase's scope; noted for awareness only).

### 5. CSPM — no grouping concept exists; same OR-only filter as Vulnerabilities pre-Phase-30

`backend/app/cspm/models.py:44-112` — `Misconfiguration` has `UniqueConstraint("tenant_id", "rule_id", "resource_id", "source")` (line 48) — meaning the schema ALREADY enforces that the same (rule_id, resource_id) pair from two different CSPM tools produces two separate rows differing only by `source`. This is the exact grouping key SRC-05 needs; it is simply never queried as a group anywhere today.

`backend/app/cspm/service.py:32-33`:
```python
if filters.source:
    query = query.where(Misconfiguration.source.in_(filters.source))
```
Pure OR, `.in_()` — identical shape to Vulnerabilities' pre-Phase-35 filter, and the literal "silent OR fallback" SRC-05 explicitly forbids continuing to rely on for "AND corroboration."

No `MisconfigurationCorrelation` table, no correlation-maintenance job, and no service function anywhere computes cross-tool grouping for CSPM findings (verified: no file under `app/cspm/` references "correlation" or "corrobora" in any form). This is a genuinely new mechanism this phase must design (see Standard Stack § Alternatives Considered above for the computed-GROUP-BY vs persisted-table tradeoff).

`cspm/schemas.py:62`: `source: list[str] | None = None` (no `max_length` cap, unlike Vulnerabilities' `max_length=10` — minor inconsistency, cheap to align while touching this filter).

### 6. Tickets — single FK to one Vulnerability row; provenance must be resolved transitively, batched

`backend/app/ticketing/models.py:79-103`:
```python
class Ticket(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tickets"
    tenant_id: Mapped[uuid.UUID] = ...
    vulnerability_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vulnerabilities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ...
```
One ticket -> exactly one `Vulnerability` row (one source's finding, since `Vulnerability` rows are per-source per the `uq_vuln_dedup` constraint noted above). `TicketResponse`/`TicketSummary` (`ticketing/schemas.py:13-47`) already join `cve_id`, `severity`, `hostname` off that vuln — SRC-07's "transitive" provenance means: resolve `ticket.vulnerability_id -> Vulnerability.cve_id, asset_id, source`, then look up `VulnerabilityCorrelation` on `(tenant_id, cve_id, asset_id)` — if a correlation row exists, the ticket's true provenance is that correlation's full `sources` array (e.g. the ticket was filed off a QUALYS-detected finding, but the SAME cve+asset is ALSO seen by RAPID7 — the ticket's badge should show both, since it represents the same underlying vulnerability-on-host, not just the one row that happened to trigger ticket creation); if no correlation row exists, provenance is `[vuln.source]` alone.

**The existing batching precedent for exactly this shape** — `ticketing/service.py:849-853` (comment, WR-05):
> "batch ALL per-URL detail aggregates into ONE query keyed by external_ticket_url (previously this ran one detail_q per grouped row — up to page_size=100 extra round-trips per list call)."

This is a direct, in-repo precedent for "resolve N tickets' derived data via exactly one extra batched query, not N." Phase 35 should mirror this exactly: after `grouped_q`/pagination produces the page's tickets, collect their `vulnerability_id`s, bulk-fetch `(id, cve_id, asset_id, source)` for those vulns (1 query), collect the resulting `(cve_id, asset_id)` pairs, bulk-fetch matching `VulnerabilityCorrelation` rows (1 query) — 2 extra queries total per ticket-list page, independent of page size, matching the existing WR-05 pattern's query-count shape.

`list_tickets` already groups "by Asana task (one row per task, not per CVE)" (`service.py:720`) — meaning a single grouped ticket row can represent MULTIPLE linked vulnerabilities (`vulns_linked` count exists, `service.py:703`). **SRC-07's "defined rule for multi-source-correlated cases" is therefore two nested questions**: (a) for one ticket -> one vuln -> its correlation, which sources show; (b) for one GROUPED task row that aggregates multiple `Ticket` rows (hence multiple `vulnerability_id`s), how do their respective source sets combine into one badge for the grouped row. Neither is answered by existing code — **this is exactly why SRC-07 is flagged LOW/assumption in the Assumptions Log**, not because the mechanism is unclear, but because the exact combination rule (union across all linked vulns' sources? show per-CVE breakdown? show only the "primary"/detecting vuln's provenance?) is a product decision, not something discoverable in the code.

### 7. `VulnSource` enum + normalization

`backend/app/vulnerabilities/models.py:32-38`:
```python
class VulnSource(str, enum.Enum):
    CROWDSTRIKE = "CROWDSTRIKE"
    NESSUS = "NESSUS"
    DEFENDER = "DEFENDER"
    WIZ = "WIZ"
    QUALYS = "QUALYS"
    RAPID7 = "RAPID7"
```
Exactly 6 members, all uppercase strings, `str, enum.Enum` (matches the codebase-wide convention of Python enums over native Postgres enums — same as `DeviceCategory`/`BusinessCriticality` in `assets/models.py`). `correlation_service._SOURCE_ORDER` (`correlation_service.py:18`) derives canonical ordering directly from `[s.value for s in VulnSource]` — forward-compatible with a 7th source with zero code change (per the file's own comment, "CORR-01").

**Frontend/backend drift (real, verified):** `frontend/src/components/vulnerabilities/chip-bar.tsx:26` and `frontend/src/components/assets/assets-chip-bar.tsx:22` both hardcode:
```typescript
const SOURCES = ['QUALYS', 'TENABLE', 'RAPID7', 'CROWDSTRIKE', 'AWS_INSPECTOR', 'WIZ', 'MOCK'] as const;
```
`TENABLE`, `AWS_INSPECTOR`, and `MOCK` are **not** members of the backend `VulnSource` enum (which has CROWDSTRIKE/NESSUS/DEFENDER/WIZ/QUALYS/RAPID7 — note `NESSUS` and `DEFENDER` are backend-real but ABSENT from the frontend list, while `TENABLE`/`AWS_INSPECTOR`/`MOCK` are frontend-only and never emitted by any backend row). This means today's source chip-bar allow-list is already stale/wrong relative to the backend enum — a `?source=NESSUS` chip literally cannot be clicked from the UI today because `NESSUS` isn't in the frontend allow-list, even though the backend fully supports filtering by it. **Phase 35 must reconcile this list** (single source of truth recommendation: derive the frontend allow-list from the same 6-value set the backend enum defines, drop `TENABLE`/`AWS_INSPECTOR`/`MOCK`, add `NESSUS`/`DEFENDER`) as part of building `SourceBadgeGroup`'s and the chip-bar's shared source vocabulary — otherwise the new AND toggle will be built against a wrong/partial source list.

### 8. Frontend — chip-bar, ProviderMark, and the vuln table's total absence of any source/correlation display

`frontend/src/components/ui/ChipBar.tsx` (315 lines, read in full) — generic multi-axis chip primitive. Each axis is independently multi-select via `useUrlStateList` (`use-url-state-list.ts:14-57`), which already handles allow-list-clamped multi-value URL state (`?source=QUALYS&source=RAPID7`) with a `toggle(item)` convenience — this is the exact mechanism the new source-filter chip already needs, no new hook required. **What's missing**: any concept of a second axis-level control (the AND toggle) — `ChipAxis` (`ChipBar.tsx:53-73`) has no boolean/mode field. Recommend adding a small sibling toggle button (mirroring the chip-button visual/`aria-pressed` shape at `ChipBar.tsx:134-157`) rendered next to the source axis specifically, backed by a plain `useUrlState('source_mode', ['or','and'] as const, 'or')` (the existing singular-value hook, `use-url-state.ts`, not read in full this pass but its plural sibling's shape at `use-url-state-list.ts` documents the identical XSS-clamp convention — CITED from the plural hook's own inline comment "mirrors WR-04 from useUrlState").

`frontend/src/components/tickets/provider-mark.tsx` (54 lines, read in full) — `ProviderMark`: 14px gradient square + text glyph, CSS-variable-driven gradient (`var(--gradient-provider-jira)` etc.), literal lookup object (no string concatenation — explicit T-13-14 XSS mitigation), `role="img" aria-label={provider}`. This is the exact visual pattern `SourceBadgeGroup` should reuse for per-scanner marks (e.g. a `Q` gradient square for QUALYS, `R` for RAPID7) — needs 6 new `--gradient-provider-{source}` CSS variables (or a shared neutral scanner-badge treatment if per-source gradients aren't part of the design system yet — flagged for `sketch-findings-getvul` skill gap, see Pitfall 4) plus a grouping wrapper showing count/confidence.

`frontend/src/components/vulnerabilities/vuln-table.tsx` (415 lines, read in full) — the CURRENT vulnerability list row/card renders: severity pill, CVE, title, asset, CVSS, status (with inline CISA-KEV pill `★ KEV` and exploit-available `⚡` badge — visual precedent for a compact provenance badge slotting into the same status cell), SLA. **There is no source or correlation display anywhere in this component** — confirming the SRC-01 gap is total, not partial: not even the single `row.source` string is shown to the analyst today (it's only used internally for the `failedSources`/stale-row tint, `vuln-table.tsx:245,344`). `SourceBadgeGroup` is a wholly new visual element for this table, most naturally placed adjacent to the existing KEV/exploit badge cluster in the Status column (desktop) and Row-3 badge cluster (mobile card), per the `visual-language.md` "always inline alongside the severity pill or the CVE ID" convention for the CISA KEV badge.

`visual-language.md` severity-pill / KEV-badge / SLA-pill CSS (lines 33-188, read) establish the tinted-pill chrome convention (`rgba(color, 0.10-0.15)` background + `1px solid rgba(color, 0.3)` border + mono mixed-case/uppercase text) that any new badge (single-source vs multi-source-corroborated) should visually inherit — e.g. single-source = neutral/muted tinted pill (`text-text-muted` tone, no special color — explicitly NOT implying confidence), multi-source-corroborated = a distinct tinted pill (e.g. the existing `--color-success`/green tint already used for "SLA ok," reusable here to mean "corroborated by N scanners" — but this exact color mapping is a genuinely new design decision, not discoverable from the skill's existing references; flagged in Assumptions Log A3, `sketch-findings-getvul` has no existing "corroboration" visual precedent to cite).

## Version Verification

(No new libraries this phase; see Standard Stack § Alternatives Considered above for the two genuinely open design choices.)

**Version verification:**
```
$ python -c "import sqlalchemy; print(sqlalchemy.__version__)"
2.0.50
$ python -c "import fastapi; print(fastapi.__version__)"
0.136.3
```
Both verified directly against `backend/.venv` (2026-08-12). Postgres reachability verified directly (`SELECT 1` succeeded against the configured `DATABASE_URL`).

## Architecture Patterns

### System Architecture Diagram

```
                         ┌─────────────────────────────────────────┐
                         │   Analyst browser (Vulnerabilities /     │
                         │   Assets / CSPM / Tickets list pages)    │
                         └───────────────┬───────────────────────────┘
                                         │  GET .../?source=QUALYS&source=RAPID7&source_mode=and
                                         ▼
        ┌─────────────────────────────────────────────────────────────────┐
        │  FastAPI router (vulnerabilities/router.py, assets/router.py,     │
        │  cspm/router.py, ticketing/router.py)                             │
        │  - binds ?source= (list[str]) + ?source_mode= (or|and, NEW)       │
        │  - Assets ALSO binds ?scanner= vs ?enrichment_source= (NEW split) │
        └───────────────┬───────────────────────────────────────────────────┘
                         ▼
        ┌─────────────────────────────────────────────────────────────────┐
        │  Service layer filter builder (_apply_filters / list_assets /     │
        │  cspm list / list_tickets)                                        │
        │                                                                    │
        │  source_mode == "or"  → sources.overlap(filters.source)  (&&)     │
        │                          OR Vulnerability.source.in_(...) for      │
        │                          single-source (no-correlation-row) rows  │
        │  source_mode == "and" → sources.contains(filters.source) (@>)     │
        │                          (structurally excludes single-source     │
        │                          rows when len(filters.source) >= 2)      │
        └───────────────┬───────────────────────────────────────────────────┘
                         ▼
        ┌─────────────────────────────────────────────────────────────────┐
        │  Page-scoped batched provenance fetch (NEW, per list call)        │
        │                                                                    │
        │  1. Run the (already-filtered, paginated) primary entity query    │
        │  2. Collect (cve_id, asset_id) keys [Vulns] / (rule_id,           │
        │     resource_id) keys [CSPM] / vulnerability_id keys [Tickets]    │
        │     present ONLY in this page                                     │
        │  3. ONE extra bulk query: correlation rows / GROUP BY / vuln      │
        │     lookup for exactly those keys (tuple_(...).in_(...))          │
        │  4. Build a Python dict[key -> sources/sources_count/confidence]  │
        │  5. O(1) dict lookup per row when assembling the response         │
        │                                                                    │
        │  == exactly 2 queries per list call, independent of page size ==  │
        │  (precedent: risk_exposure_service.py:320-345,                    │
        │   ticketing/service.py:849-853)                                   │
        └───────────────┬───────────────────────────────────────────────────┘
                         ▼
        ┌─────────────────────────────────────────────────────────────────┐
        │  Response schema (VulnerabilitySummary / AssetSummary /           │
        │  MisconfigSummary / TicketSummary) — NEW fields:                  │
        │  sources: list[str], sources_count: int, is_corroborated: bool    │
        └───────────────┬───────────────────────────────────────────────────┘
                         ▼
        ┌─────────────────────────────────────────────────────────────────┐
        │  <SourceBadgeGroup sources={...} count={...}> (NEW component)     │
        │  - 1 source  → neutral tinted pill, single scanner mark, NO        │
        │                "confirmed" language                               │
        │  - 2+ sources → distinct tinted pill (corroboration color) +      │
        │                stacked scanner marks + count                      │
        │  Reused across VulnTable, Assets table, CSPM table, Tickets table │
        └─────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure (additive only — no new top-level dirs)
```
backend/app/
├── vulnerabilities/
│   ├── schemas.py          # + source_mode field on VulnerabilityFilter; + sources/sources_count on VulnerabilitySummary
│   ├── service.py          # + batched correlation fetch in list_vulnerabilities; _apply_filters OR/AND branch
├── assets/
│   ├── router.py           # + source_mode param; split scanner vs enrichment_source; fix AND-bug
├── cspm/
│   ├── service.py          # + resource+rule-id grouping query (computed GROUP BY, recommended)
│   ├── schemas.py           # + source_mode; + grouping fields on response
├── ticketing/
│   ├── service.py          # + batched vuln→correlation provenance resolution in list_tickets/get_ticket
frontend/src/components/
├── vulnerabilities/
│   ├── source-badge-group.tsx   # NEW — shared component
│   ├── source-badge-group.test.tsx
│   ├── chip-bar.tsx             # + AND toggle control; reconcile SOURCES allow-list with backend VulnSource
├── assets/
│   ├── assets-chip-bar.tsx      # + split scanner/enrichment axes; + AND toggle; reconcile SOURCES
├── cspm/ (new chip-bar if none exists yet — verify at plan time)
├── tickets/
│   ├── tickets-chip-bar.tsx     # + source axis using SourceBadgeGroup data
```

### Pattern 1: Batched page-scoped correlation lookup (extends `risk_exposure_service.py:320-345`)
**What:** Fetch the paginated primary rows first, collect their natural keys, then one additional bulk query scoped to exactly those keys, build a dict, do O(1) lookups.
**When to use:** Any list endpoint that needs to attach `VulnerabilityCorrelation`-derived data (sources/count/confidence) to N rows.
**Example (new code, following the cited precedent's shape):**
```python
# Source: pattern synthesized from risk_exposure_service.py:320-345 (verified
# in-repo precedent) — NOT copied verbatim, that precedent is tenant-wide
# (background job); this is page-scoped (interactive endpoint).
page_rows = (await db.execute(data_q)).all()
keys = {(r.Vulnerability.cve_id, r.Vulnerability.asset_id)
        for r in page_rows if r.Vulnerability.cve_id and r.Vulnerability.asset_id}
corr_by_key: dict[tuple[str, uuid.UUID], VulnerabilityCorrelation] = {}
if keys:
    from sqlalchemy import tuple_
    corr_rows = (await db.execute(
        select(VulnerabilityCorrelation).where(
            VulnerabilityCorrelation.tenant_id == tenant_id,
            tuple_(VulnerabilityCorrelation.cve_id, VulnerabilityCorrelation.asset_id).in_(keys),
        )
    )).scalars().all()
    corr_by_key = {(c.cve_id, c.asset_id): c for c in corr_rows}
```

### Pattern 2: OR vs AND source-array filter branch (Vulnerabilities/Assets)
**What:** `source_mode` branches between Postgres `&&` (overlap/OR) and `@>` (contains/AND) on the correlation ARRAY, joined from the primary table by natural key — NOT a per-row equality/`.in_()` filter, which cannot express true corroboration.
**When to use:** Vulnerabilities list filter, Assets scanner filter.
**Example:**
```python
# Source: SQLAlchemy ARRAY comparator docs (contains/overlap compile to
# Postgres @> / &&) — pattern verified against the existing GIN-indexed
# vulnerability_correlations.sources column (034_add_correlation_sources.py).
if filters.source:
    corr_subq = select(VulnerabilityCorrelation.cve_id, VulnerabilityCorrelation.asset_id).where(
        VulnerabilityCorrelation.tenant_id == tenant_id,
        VulnerabilityCorrelation.sources.contains(filters.source)
        if filters.source_mode == "and"
        else VulnerabilityCorrelation.sources.overlap(filters.source),
    )
    if filters.source_mode == "and":
        # AND mode: ONLY rows with a qualifying correlation match (single-source
        # rows structurally cannot satisfy len(selected) >= 2 corroboration).
        query = query.where(tuple_(Vulnerability.cve_id, Vulnerability.asset_id).in_(corr_subq))
    else:
        # OR mode: correlation-array overlap OR direct per-row source match
        # (covers single-source findings with no correlation row at all).
        query = query.where(
            or_(
                tuple_(Vulnerability.cve_id, Vulnerability.asset_id).in_(corr_subq),
                Vulnerability.source.in_(filters.source),
            )
        )
```
Note: this is illustrative of the operator/branch shape — the planner/executor must verify the exact SQLAlchemy 2.0 `tuple_(...).in_(subquery)` compiles correctly against asyncpg in this codebase's test harness before locking the final implementation (not verified end-to-end in this research pass; flagged as an implementation-detail risk, not a design-level unknown).

### Pattern 3: Scanner vs enrichment source partition (Assets)
**What:** Two disjoint constant lists gating two separate filter params, both reading the SAME `seen_by_sources` JSONB column.
**Example:**
```python
# New constants, colocated with the router or a shared assets/constants.py
SCANNER_SOURCES = frozenset(s.value for s in VulnSource)  # CROWDSTRIKE/NESSUS/DEFENDER/WIZ/QUALYS/RAPID7
ENRICHMENT_SOURCES = frozenset({"JAMF", "HUMAANS", "INTUNE"})
```
`?scanner=` only accepts `SCANNER_SOURCES` values and gets OR/AND semantics (SRC-02/03/04); a separate `?enrichment_source=` (or similar) only accepts `ENRICHMENT_SOURCES` and is a plain facet/OR filter (SRC-06 does not ask for AND-corroboration on enrichment sources — they're presence facts, not multi-tool corroboration signals).

### Anti-Patterns to Avoid
- **Per-row correlation query in a list loop:** Calling `get_correlation_for_vuln` (or an equivalent single-key `SELECT`) inside a `for vuln in results:` loop — this is the literal N+1 SRC-08 forbids. Always batch (Pattern 1).
- **Silent OR fallback for CSPM "AND":** Reusing `Misconfiguration.source.in_(filters.source)` and just renaming a param `source_mode=and` without actually querying the (rule_id, resource_id) grouping is exactly the anti-pattern SRC-05 names explicitly — verify the AND path genuinely requires ALL selected sources present in the SAME (rule_id, resource_id) group, not just present somewhere in the result set.
- **Treating "no correlation row" as an error/unknown state:** It is the expected, common (single-source) case — see Reconnaissance §2.
- **Modeling Assets' enrichment-source split on `enrich_assets.py`'s dict-shape:** That script is dead/manual-only and already an inconsistent, destructive outlier — do not treat it as a second source of truth for `seen_by_sources`'s shape (Reconnaissance §4).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Multi-value URL state for source chips | A new custom URL-param hook | `useUrlStateList` (`use-url-state-list.ts`, already used by `chip-bar.tsx`/`assets-chip-bar.tsx`) | Already handles allow-list XSS clamp on read+write; exact fit for `?source=` |
| Boolean AND-toggle URL state | A new hook | `useUrlState` (singular sibling, already referenced/used codebase-wide for `?order=asc|desc`) | Same clamp convention, zero new hook code |
| Array containment/overlap SQL | Hand-written raw SQL string with `ANY()`/`@>` | SQLAlchemy's `ARRAY` comparator `.contains()` / `.overlap()` (already used nowhere yet in application code for `vulnerability_correlations.sources`, but is the documented, parameterized, injection-safe SQLAlchemy 2.0 API for exactly this) | Avoids raw-SQL injection surface; consistent with the rest of the codebase's SQLAlchemy-only query style (verified: zero raw `text()` SQL in `vulnerabilities/service.py`) |
| Per-tool CSPM corroboration grouping | A bespoke correlation-maintenance background job (unless the planner explicitly chooses the persisted-table alternative) | A computed `GROUP BY (tenant_id, rule_id, resource_id)` query with `array_agg(DISTINCT source)`, reusing the EXISTING `uq_misconfig_dedup` unique-constraint key (`cspm/models.py:48`) as the grouping key | The grouping key already exists as a schema constraint; a read-time GROUP BY needs no new maintenance job, migration, or staleness-pruning logic (contrast with `VulnerabilityCorrelation`'s `_prune_stale_correlations`, which CSPM would otherwise need to reinvent) |

**Key insight:** Every mechanism this phase needs except the CSPM grouping and the `SourceBadgeGroup` visual has an exact, already-shipped sibling precedent in this codebase (the correlation ARRAY + GIN index, the bulk-dict-lookup batching pattern, the multi-value URL-state hook, the tinted-pill badge chrome). The work is synthesis and consistency, not invention — except for CSPM's grouping mechanism (genuinely new) and the exact multi-source-corroborated visual treatment (genuinely new design decision).

## Common Pitfalls

### Pitfall 1: AND-mode with a single selected source is meaningless but must not error
**What goes wrong:** If an analyst selects exactly ONE source and flips the AND toggle, `sources.contains(['QUALYS'])` is well-defined (any correlation containing QUALYS, same as OR with 1 value) but doesn't express "corroboration" at all — the UI should probably disable/no-op the AND toggle when fewer than 2 sources are selected, or the backend should silently treat AND with <2 sources as equivalent to OR (both are defensible; pick one and document it, don't leave it ambiguous).
**Why it happens:** OR and AND are mathematically identical for a 1-element set; the meaningful distinction only exists at 2+.
**How to avoid:** Explicit rule in the plan: AND toggle is disabled/hidden (or a no-op) whenever `filters.source` has fewer than 2 entries. Document this in the PLAN's chip-bar task.
**Warning signs:** A test asserting `?source=QUALYS&source_mode=and` returns something different from `?source=QUALYS&source_mode=or` when it shouldn't (or vice versa if the team decides the opposite convention).

### Pitfall 2: CSPM's computed GROUP BY approach needs its OWN batching discipline for the list endpoint
**What goes wrong:** A naive first pass might run the GROUP BY aggregate once per resource-row in a list (N+1 again), exactly the mistake SRC-08 exists to prevent — just relocated to CSPM instead of Vulnerabilities.
**Why it happens:** The GROUP BY-as-corroboration-source is new enough that there's no existing precedent to copy from within CSPM's own codebase; it's tempting to write it as a per-row subquery expression instead of a batched join.
**How to avoid:** Same 2-query page-scoped pattern as Pattern 1: fetch the page's `(rule_id, resource_id)` pairs, then ONE `GROUP BY` query scoped via `tuple_(rule_id, resource_id).in_(page_pairs)`, then a dict lookup.
**Warning signs:** A query-count assertion test (see Validation Architecture) failing specifically on the CSPM list endpoint while Vulnerabilities/Assets/Tickets pass.

### Pitfall 3: The frontend `SOURCES` allow-list is already wrong and duplicated in 2 files
**What goes wrong:** Building the new AND-toggle chip UI against the existing hardcoded `SOURCES` constant (`chip-bar.tsx:26`, `assets-chip-bar.tsx:22`) silently perpetuates the `TENABLE`/`AWS_INSPECTOR`/`MOCK`-present, `NESSUS`/`DEFENDER`-absent drift documented in Reconnaissance §7 — meaning the new filter UI would be unable to select 2 of the 6 real backend sources (NESSUS, DEFENDER) while offering 3 fake ones.
**Why it happens:** No single source of truth for the source-value list is shared between frontend and backend today (no generated types, no shared constants file for this specific enum — verified: no `VulnSource` re-export found anywhere under `frontend/src`).
**How to avoid:** Reconcile both files' `SOURCES` constants to the real 6-value `VulnSource` set (or better: derive from a facets response, since both chip-bars already support `derivedFromCounts: true` for exactly this data-driven-value-space case — prefer deriving from backend facets over a second hardcoded constant, eliminating the drift class entirely going forward).
**Warning signs:** A manual QA pass clicking "NESSUS" or "DEFENDER" chips and finding they don't exist in the UI despite real NESSUS/DEFENDER data being present in facet counts.

### Pitfall 4: No existing visual precedent for "multi-source-corroborated" as a distinct color/treatment
**What goes wrong:** Inventing a badge color on the fly (e.g. reusing `--color-violet` because it "felt right") without checking it against the `sketch-findings-getvul` skill's actual token semantics (violet is reserved for saved-filter/focus-ring/interactive-accent use per `ChipBar.tsx`'s own comments, NOT corroboration state) risks a collision with an existing meaning.
**Why it happens:** `visual-language.md` documents severity/status/SLA/provider pills exhaustively but has zero mention of "corroboration"/"confirmed"/"single source" as a visual concept (verified via direct grep — zero matches).
**How to avoid:** Flag this explicitly to the user/discuss-phase step as a new visual decision needing sign-off, not something to silently invent. This research recommends (not decides): single-source = neutral/muted (no special color, explicitly avoiding any color that could look like "verified"/"safe"), multi-source = the existing `--color-success`/green-tinted pill ALREADY used for "SLA ok" (`sla-pill.ok`, `visual-language.md:150`) — chosen because green already carries a "more assurance" connotation in this design system and is NOT already used to mean "single/basic" anywhere, but this is a genuinely new mapping and should be confirmed, not assumed as locked. See Assumptions Log A3.

### Pitfall 5: `sources_count`/`confidence` bands were tuned for a 6-source scale where LOW is "structurally near-unreachable"
**What goes wrong:** Reusing `VulnerabilityCorrelation.confidence` (HIGH/MEDIUM/LOW, `correlation_service.py:44-52`: `>=4 sources → HIGH`, `>=2 → MEDIUM`, else `LOW`) directly as the `SourceBadgeGroup`'s visual tier without checking its actual value distribution: because `_find_correlated_groups` already filters to `len(v) >= 2` before a correlation row is even created, `confidence == "LOW"` is (per the model's own comment at `correlation_service.py:44-46`) "structurally near-unreachable" — so a naive 3-tier badge (LOW/MEDIUM/HIGH) would show MEDIUM for the overwhelming majority of corroborated findings and almost never show LOW, which may look like a bug to an analyst ("why does everything say MEDIUM?").
**Why it happens:** `confidence` was designed for the Phase 33 risk-scoring formula's internal weighting, not as an analyst-facing display band — reusing it verbatim conflates two different design intents.
**How to avoid:** For `SourceBadgeGroup`, prefer displaying the RAW `sources_count`/`sources` list (e.g. "2 sources: QUALYS, RAPID7" or a stacked-mark + count) over the `confidence` enum — the count is unambiguous and doesn't require reverse-engineering why LOW never appears. Reserve `confidence` for internal risk-scoring use only, per its original Phase 30/33 design intent.

### Pitfall 6: Remediated findings can silently lose their corroboration badge (see Reconnaissance §2)
**What goes wrong:** An analyst reviewing a REMEDIATED finding that was previously "corroborated by 3 scanners" sees only "single source" on the closed item, because `_prune_stale_correlations` deleted the correlation row once the finding left OPEN/IN_PROGRESS status.
**Why it happens:** Correlation maintenance (Phase 30) was scoped to active-triage findings only; Phase 35 is the first phase to surface correlation data on closed items via badges, exposing this as a UX regression that was invisible before (no UI ever showed correlation state for closed items).
**How to avoid:** Explicit design decision needed (Assumptions Log A1) — either accept and document this behavior, or extend `_find_correlated_groups`'s status filter (out of this phase's literal scope but cheap if bundled).

## Code Examples

### Existing bulk-fetch-then-dict-lookup precedent (verbatim structure, not copy-pasted)
```python
# Source: backend/app/vulnerabilities/risk_exposure_service.py:320-345 (read directly)
corr_rows = (
    await db.execute(
        select(
            VulnerabilityCorrelation.cve_id,
            VulnerabilityCorrelation.asset_id,
            VulnerabilityCorrelation.sources_count,
        ).where(VulnerabilityCorrelation.tenant_id == tenant_id)
    )
).all()
corr_by_key = {(row.cve_id, row.asset_id): row.sources_count for row in corr_rows}
# ... later, per vuln row, O(1):
sources_count = corr_by_key.get((vuln.cve_id, vuln.asset_id), 1)
```

### Existing OR-filter precedent (Vulnerabilities, pre-Phase-35, to be extended not replaced)
```python
# Source: backend/app/vulnerabilities/service.py:40-41 (read directly)
if filters.source:
    query = query.where(Vulnerability.source.in_(filters.source))
```

### Existing (buggy) AND-loop precedent to FIX (Assets)
```python
# Source: backend/app/assets/router.py:154-159 (read directly) — AND semantics,
# needs to become OR-default with an explicit AND-mode branch per SRC-03/04.
if scanner:
    scanners = [s.strip().upper() for s in scanner.split(",") if s.strip()]
    for s in scanners:
        query = query.where(Asset.seen_by_sources.contains([s]))
```

### Existing GIN-index migration precedent (mirror for any new index this phase adds)
```python
# Source: backend/alembic/versions/034_add_correlation_sources.py:36-41
op.create_index(
    "ix_vulnerability_correlations_sources",
    "vulnerability_correlations",
    ["sources"],
    postgresql_using="gin",
)
```

### Existing tinted-pill badge chrome (visual precedent for SourceBadgeGroup)
```css
/* Source: .claude/skills/sketch-findings-getvul/references/visual-language.md:42-46 */
.sev-pill { display: inline-flex; align-items: center; gap: 6px; padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 500; }
.sev-pill.critical { background: rgba(248, 113, 113, 0.12); color: var(--color-severity-critical); border: 1px solid rgba(248, 113, 113, 0.3); }
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Per-row `Vulnerability.source.in_()` OR-only filter, no correlation awareness | Correlation-ARRAY-aware `source_mode` OR/AND filter | This phase (Phase 35) | Analysts can finally express true multi-scanner corroboration, not just "seen by any of these" |
| Assets scanner filter silently ANDs multiple selections | Assets scanner filter defaults to OR, explicit AND toggle, matching Vulnerabilities | This phase | Fixes a real pre-existing bug where multi-select scanner filtering on Assets has always meant the opposite of what analysts likely expect |
| CSPM source filter is OR-only, no cross-tool grouping | New (rule_id, resource_id) grouping enables true AND corroboration | This phase | First CSPM-native corroboration concept in the codebase |
| No visible source/correlation data anywhere in the Vulnerabilities list UI | `SourceBadgeGroup` on every finding row | This phase | Closes the single biggest visible provenance gap (SRC-01) |

**Deprecated/outdated:**
- The frontend's hardcoded `SOURCES` constant (both `chip-bar.tsx` and `assets-chip-bar.tsx`) should be considered stale/incorrect as of this research and reconciled (Pitfall 3) — not a formal deprecation, but a real drift bug this phase should not perpetuate.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Correlation-pruning-on-status-change (Reconnaissance §2 / Pitfall 6) is acceptable as-is (badges only reflect corroboration among currently-OPEN/IN_PROGRESS findings; closed findings may show fewer sources than when they were active) — this research recommends accepting it and documenting, not silently fixing `_find_correlated_groups`'s status scope as part of this phase. | Existing-Code Reconnaissance §2, Pitfall 6 | If the user actually wants closed findings to retain their historical corroboration count, this requires extending Phase 30's `correlation_service.py` status filter — a bigger, cross-phase-boundary change than "add filters + badges," and should be raised explicitly rather than assumed. |
| A2 | CSPM's per-tenant `Misconfiguration` row count is small enough that a computed (read-time) `GROUP BY (tenant_id, rule_id, resource_id)` is performant without a persisted correlation table or new maintenance job. | Standard Stack § Alternatives Considered, Pitfall 2 | If a tenant has a very large CSPM finding volume (e.g. hundreds of thousands of cloud-resource findings), a read-time GROUP BY on every list request could be materially slower than the persisted-table alternative — this was not measured against real data in this research pass (no live CSPM data available to profile). |
| A3 | The visual treatment for "multi-source-corroborated" (recommended: reuse the existing `--color-success`/green SLA-ok tint) vs "single-source" (neutral/muted, no color) is a reasonable default mapping, pending explicit sign-off — `sketch-findings-getvul`'s `visual-language.md` has zero existing precedent for a "corroboration" visual concept. | Pitfall 4 | A different, more design-system-consistent color mapping may be preferred (e.g. reusing a specific accent already meant to signal "high confidence" elsewhere) — this needs an explicit design decision, not an assumed default, before implementation. |
| A4 | SRC-07's "defined rule for multi-source-correlated cases" for a GROUPED ticket-task row (one Asana/Jira task representing MULTIPLE linked `Ticket`/`Vulnerability` rows, per `list_tickets`'s "one row per task" grouping) should union all linked vulns' correlation sources into one combined badge, rather than showing only the "primary" (first-created) ticket's vuln's provenance. | Existing-Code Reconnaissance §6 | The union approach could overstate a task's provenance if, e.g., 5 of 6 linked vulns are QUALYS-only and 1 is corroborated by RAPID7 too — showing "QUALYS + RAPID7" on the whole task might read as more corroborated than most of its linked findings actually are. The alternative (show a per-CVE breakdown, or the modal/max, or "mixed") is equally defensible and this is fundamentally a product decision this research cannot resolve from code alone. |

**If this table is empty:** N/A — 4 assumptions logged, all genuinely new design decisions this research could not resolve purely from existing code, flagged for explicit confirmation before being treated as locked.

## Open Questions (RESOLVED)

1. **[RESOLVED — Plan 35-03] Does the planner want to fix the identical AND-loop bug in `ticketing/rule_engine.py:71-73` (ticket-automation-rule asset matching) in this same phase, since it's the same 2-line fix as the Assets router bug?** RESOLVED: YES — Plan 35-03 fixes rule_engine.py to OR-default alongside the Assets router, reusing the shared SCANNER_SOURCES constants.
   - What we know: Same exact bug shape, same root cause, trivially cheap to fix alongside the Assets router fix.
   - What's unclear: Whether "Tickets" in SRC-02's entity list means ticket-provenance-display (this phase's clear scope, per the phase Goal) or also extends to ticket-automation-RULE matching (a different, adjacent surface not explicitly named in the Success Criteria).
   - Recommendation: Treat as out-of-scope-but-flag-for-planner; a one-line note in the plan is cheap insurance either way.

2. **[RESOLVED — Plan 35-03] Should the new GIN index on `assets.seen_by_sources` be added in this phase, given the JSONB column currently has NO index at all for `.contains()` queries?** RESOLVED: YES — Plan 35-03 adds migration 045_add_seen_by_sources_gin (mirrors 034) since this phase makes scanner-source filtering on Assets a first-class, higher-frequency query.
   - What we know: `tags` (also queried via `.contains()`-shaped operations conceptually) has a GIN index; `seen_by_sources` does not, and this phase is about to make scanner-source filtering on Assets a first-class, more heavily-used feature (OR/AND toggle likely increases query frequency, not just changes semantics).
   - What's unclear: Whether current Assets table sizes make this a real performance concern yet, or whether it's premature optimization for this phase specifically.
   - Recommendation: Include the GIN index migration — it's a cheap, mechanically-identical addition to `034_add_correlation_sources.py`'s precedent, and this phase is explicitly increasing filter usage on this exact column.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PostgreSQL | All new query logic (ARRAY `@>`/`&&`, JSONB `.contains()`) | ✓ | Reachable via configured `DATABASE_URL` (verified `SELECT 1`) | — |
| SQLAlchemy | Query construction | ✓ | 2.0.50 | — |
| FastAPI | Router/schema layer | ✓ | 0.136.3 | — |
| Node/Next.js frontend toolchain | `SourceBadgeGroup` + chip-bar work | ✓ | Node v26.5.0 | — |
| Alembic head | New migration(s) this phase adds (e.g. `seen_by_sources` GIN index, any CSPM schema addition) | ✓ | Head is `044_add_risk_backfill_job`; new revisions start at `045_...`, ids ≤32 chars (per backend_test_env note) | — |

**Missing dependencies with no fallback:** None.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.x (backend, async via `pytest-asyncio`) + Vitest/Jest-shaped `*.test.tsx` (frontend, existing convention e.g. `chip-bar.test.tsx`, `provider-mark.test.tsx`) |
| Config file | `backend/pyproject.toml` (`[tool.pytest.ini_options]`, `testpaths = ["tests"]`) |
| Quick run command | `cd backend && ENCRYPTION_KEY=<fernet-key> JWT_SECRET_KEY=<secret> .venv/bin/pytest tests/test_vuln_source_filter.py -x` (per-file — required, see backend_test_env note; running the whole `tests/` dir produces false failures) |
| Full suite command | Per-file loop across every modified/added `tests/test_*.py`, plus frontend `npm test` for new `*.test.tsx` files |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SRC-01 | Every finding row's `SourceBadgeGroup` never implies "confirmed" from 1 scanner | unit (frontend) | `npm test -- source-badge-group.test.tsx` | ❌ Wave 0 |
| SRC-02 | Scanner-source filter param accepted on Vulnerabilities/Assets/CSPM/Tickets endpoints | integration | `pytest tests/test_vuln_source_filter.py -x`, new `test_asset_source_filter.py`, `test_cspm_source_filter.py`, `test_ticket_source_provenance.py` | ❌ Wave 0 (new files for Assets/CSPM/Tickets; extend existing for Vulns) |
| SRC-03 | Multi-select defaults to OR | integration | Same files, `?source=A&source=B` (no `source_mode`) asserts union semantics | ❌ Wave 0 |
| SRC-04 | AND toggle uses `@>`, only matches true corroboration | integration | Same files, `?source=A&source=B&source_mode=and` asserts intersection-only (a single-source-A-only row must NOT appear) | ❌ Wave 0 |
| SRC-05 | CSPM AND corroboration via (resource, rule-id) grouping, not silent OR | integration | New `test_cspm_source_filter.py::test_and_mode_requires_same_resource_rule_group` — seed 2 tools on SAME (rule_id, resource_id) and 2 tools on DIFFERENT (rule_id, resource_id) pairs, assert AND mode only matches the former | ❌ Wave 0 |
| SRC-06 | Assets filter partitions scanner vs enrichment sources | integration | New `test_asset_source_filter.py::test_enrichment_source_does_not_leak_into_scanner_filter` — seed an asset with `seen_by_sources=["JAMF"]` only, assert it's excluded from a scanner-only `?scanner=` filter result | ❌ Wave 0 |
| SRC-07 | Ticket provenance resolves transitively through correlation, defined rule for multi-source | integration | New `test_ticket_source_provenance.py` — seed a ticket linked to a QUALYS vuln that's also RAPID7-correlated, assert the ticket's provenance shows both sources per the rule chosen in Assumptions Log A4 | ❌ Wave 0 |
| SRC-08 | No per-row N+1; batched provenance/facet queries | unit (query-count assertion, NEW harness) | New `test_query_count_assertions.py` (or per-endpoint inline) using a SQLAlchemy `before_cursor_execute` event-listener counter around `app.db.session.engine.sync_engine`, asserting `list_vulnerabilities`/`list_assets`/CSPM-list/`list_tickets` each issue a FIXED, small number of queries regardless of page size (e.g. seed 2 pages worth of rows, assert query count is IDENTICAL between a 5-row and a 50-row page) | ❌ Wave 0 — no query-count-assertion harness exists anywhere in this codebase today (verified: grep for `before_cursor_execute`/`query_count` across `backend/tests` returns zero matches); this is new test infrastructure this phase must build, not reuse |

### Sampling Rate
- **Per task commit:** `pytest tests/test_<touched_file>.py -x` (per-file, per backend_test_env note)
- **Per wave merge:** Full loop over every new/modified `tests/test_*.py` file individually + `npm test` for touched frontend test files
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_query_count_assertions.py` (or equivalent per-endpoint inline fixture) — new SQLAlchemy statement-counting harness; no precedent exists in this codebase (SRC-08's hardest-to-satisfy requirement structurally)
- [ ] `backend/tests/test_asset_source_filter.py` — new file, OR/AND + scanner/enrichment partition (SRC-02/03/04/06)
- [ ] `backend/tests/test_cspm_source_filter.py` — new file, OR/AND + resource+rule-id grouping (SRC-02/03/04/05)
- [ ] `backend/tests/test_ticket_source_provenance.py` — new file, transitive resolution + multi-source rule (SRC-07)
- [ ] `frontend/src/components/vulnerabilities/source-badge-group.test.tsx` — new file (SRC-01)
- [ ] Extend existing `backend/tests/test_vuln_source_filter.py` with OR/AND + `sources`/`sources_count` list-response assertions (SRC-01/03/04/08 for Vulnerabilities specifically)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Unchanged — existing `get_current_user`/`require_role` dependencies on all touched routers, no new auth surface |
| V3 Session Management | No | Unchanged |
| V4 Access Control | Yes | Every new filter/batched query MUST retain the existing `tenant_id == :t` scoping (T-11-04/T-12-21 precedent, e.g. `ticketing/service.py:781-787`'s documented IDOR-safe subquery reasoning) — the new `tuple_(cve_id, asset_id).in_(...)` batched correlation lookups must include `VulnerabilityCorrelation.tenant_id == tenant_id` explicitly, not rely on the outer query's scoping alone, mirroring existing per-table tenant checks |
| V5 Input Validation | Yes | `source_mode` must be a `Literal["or","and"]` Pydantic field (rejects arbitrary values with a 422, not silently defaulting); the `?scanner=`/`?enrichment_source=` split on Assets must retain the existing allow-list clamp pattern (`T-12-05`, `useUrlStateList`'s `allowList` mechanism on the frontend; backend should mirror with an explicit enum/frozenset check, not raw string passthrough into `.contains()`) |
| V6 Cryptography | No | Not applicable — no new secrets/crypto surface |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Cross-tenant correlation-row leakage via unscoped `tuple_(...).in_(...)` batched lookup | Information Disclosure | Always include explicit `tenant_id == :t` on the SECOND (batched correlation/grouping) query, not just the first (primary entity) query — the existing `T-12-21` pattern (`ticketing/service.py:781-787`) already documents why an unscoped subquery is *usually* safe when intersected with an outer tenant-scoped set, but the safer, more auditable practice (and what every other query in this codebase already does) is to scope BOTH queries explicitly. |
| Arbitrary `source_mode`/`scanner`/`enrichment_source` values reaching a raw JSONB/ARRAY operator | Tampering | Reject unknown values at the Pydantic/FastAPI layer (422), matching existing `T-12-05` allow-list conventions — never pass a raw query-string value directly into `.contains()`/`.overlap()` without validating against the `VulnSource`/`SCANNER_SOURCES`/`ENRICHMENT_SOURCES` allow-lists first. |

## Sources

### Primary (HIGH confidence — read directly in this session)
- `backend/app/vulnerabilities/models.py` (full file)
- `backend/app/vulnerabilities/correlation_service.py` (full file)
- `backend/app/vulnerabilities/service.py` (lines 1-360)
- `backend/app/vulnerabilities/schemas.py` (full file)
- `backend/app/vulnerabilities/risk_exposure_service.py` (grep + surrounding context, lines ~50-390)
- `backend/app/assets/models.py` (full file)
- `backend/app/assets/router.py` (lines 1-220)
- `backend/app/cspm/models.py` (full file)
- `backend/app/cspm/service.py`, `router.py`, `schemas.py` (grep + targeted reads)
- `backend/app/ticketing/models.py` (full file)
- `backend/app/ticketing/service.py` (grep + lines 700-853)
- `backend/app/ticketing/schemas.py` (lines 1-55)
- `backend/app/ticketing/rule_engine.py` (lines 55-85)
- `backend/app/enrich_assets.py` (lines 110-155, plus `__main__` check)
- `backend/app/connectors/sync.py`, `jamf_sync.py`, `humaans_sync.py`, `intune_sync.py` (grep for `seen_by_sources`)
- `backend/alembic/versions/034_add_correlation_sources.py` (full file)
- `backend/alembic/versions/044_add_risk_backfill_job.py`, directory listing of `alembic/versions/`
- `backend/tests/test_vuln_source_filter.py` (full file)
- `backend/tests/test_risk_exposure_service.py` (lines 355-395)
- `backend/tests/test_asset_groups.py` (lines 140-180)
- `frontend/src/components/ui/ChipBar.tsx` (full file)
- `frontend/src/components/vulnerabilities/chip-bar.tsx` (full file)
- `frontend/src/components/assets/assets-chip-bar.tsx` (full file)
- `frontend/src/components/tickets/provider-mark.tsx` (full file)
- `frontend/src/components/vulnerabilities/vuln-table.tsx` (full file)
- `frontend/src/hooks/use-url-state-list.ts` (full file)
- `.claude/skills/sketch-findings-getvul/references/visual-language.md` (grep + targeted lines 29-190)
- `.planning/REQUIREMENTS.md` (SRC-01..08 verbatim text)
- `.planning/ROADMAP.md` (Phase 35 goal/success-criteria section)
- Direct shell verification: `python -c "import sqlalchemy, fastapi"` version check; live Postgres `SELECT 1` reachability check

### Secondary (MEDIUM confidence)
- Row-count/performance characteristics of CSPM data at real-tenant scale — not measured in this session; recommendation (computed GROUP BY) is reasoned from schema shape and phase pattern, not profiled (see Assumptions Log A2).

### Tertiary (LOW confidence)
- None — no unverified WebSearch-only claims were used in this research; the entire phase is internal-codebase reconnaissance plus deterministic Postgres/SQLAlchemy operator semantics (well-established, not requiring external verification beyond the version checks already performed).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries; versions verified directly against the live `.venv`.
- Architecture: HIGH for the batching/OR-AND-filter design (both directly extend proven in-repo precedents); MEDIUM for the CSPM grouping mechanism and the SourceBadgeGroup visual spec (both genuinely new, no exact precedent, documented as open design decisions in the Assumptions Log rather than asserted as fact).
- Pitfalls: HIGH — every pitfall listed is grounded in a specific, cited file:line finding from this session's direct code reads, not speculation.

**Research date:** 2026-08-12
**Valid until:** 30 days (stable internal codebase domain; no external dependency churn risk) — but Assumptions A1/A3/A4 should be resolved via `/gsd-discuss-phase` (or explicit planner sign-off) BEFORE this expiry, since they are genuinely open product/design decisions, not time-sensitive facts.
