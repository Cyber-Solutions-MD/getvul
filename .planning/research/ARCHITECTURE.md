# Architecture Research

**Domain:** GetVul v4.0 — Enriched Risk Exposure & Source-Aware Triage (integration into existing FastAPI/Postgres/Next.js monolith)
**Researched:** 2026-08-04
**Confidence:** HIGH — every claim below is grounded in the actual files read (`backend/app/vulnerabilities/`, `backend/app/assets/`, `backend/app/connectors/`, `backend/app/cspm/`, `backend/app/ticketing/models.py`, `frontend/src/components/{ui,vulnerabilities,assets,connectors,states}/`). Two items (CSPM AND-toggle semantics, AI-prioritization read-path cutover) are flagged LOW/MEDIUM and called out explicitly as open questions rather than asserted as fact.

## Standard Architecture

### System Overview — existing pipeline with v4.0 additions overlaid

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ CONNECTORS (app/connectors/*.py)                                              │
│  CrowdStrike · Nessus · Defender · Wiz · Qualys · Rapid7                      │
│  BaseConnector.fetch_vulnerabilities() → list[NormalizedVulnerability]        │
│  ★ NEW: NormalizedVulnerability gains `native_risk: dict | None` (additive)   │
├──────────────────────────────┬─────────────────────────────────────────────────┤
│                               ▼
│ SYNC ORCHESTRATOR (app/connectors/sync.py :: run_sync)                       │
│  _upsert_asset()  →  Asset row (device fields, seen_by_sources)              │
│  _upsert_vulnerability() → Vulnerability row (severity/cvss/kev/★native_risk)│
│  post-sync: run_correlations() → compute_risk_scores()                      │
│  ★ NEW post-sync step: compute_finding_risk_exposure() (inline, per-row)     │
├───────────────────────────────┼────────────────────────────────────────────────┤
│               ▼                                ▼
│ VULNERABILITY  (one row per tenant+cve+asset+source)   ASSET (one row/host)  │
│  severity, cvss_v3_score, epss_score,                  seen_by_sources[]     │
│  exploit_available, cisa_kev, source (typed, indexed)  risk_score (aggregate)│
│  ★ native_risk JSONB (VPR/ExPRT.AI/threat-intel)       ★ exposure_context    │
│  ★ risk_exposure_score, risk_model_version             ★ risk_exposure_score │
│                               │                                │              │
│                               ▼                                │              │
│ VULNERABILITY_CORRELATION (cve_id, asset_id) → cross-source dedup             │
│  today: 4 fixed nullable FK columns (crowdstrike/nessus/defender/wiz_vuln_id) │
│  ★ REPLACED: sources ARRAY(String) + source_vuln_ids JSONB (all 6 sources)   │
├───────────────────────────────┴────────────────────────────────────────────────┤
│ SLA SERVICE · TRENDS · DASHBOARD (consumers of severity / risk_score)         │
│  ★ cut over to risk_exposure_score where they currently read severity/       │
│    Asset.risk_score directly (see Pattern 4 below for the named seams)       │
├────────────────────────────────────────────────────────────────────────────────┤
│ FACETED LIST API (app/vulnerabilities/service.py, app/assets/service.py, …)   │
│  _apply_filters() · get_facets() · VulnerabilityFilter/AssetFilter            │
│  ★ NEW: source_mode=or|and branch; ★ NEW: sources[] on summary responses     │
├────────────────────────────────────────────────────────────────────────────────┤
│ FRONTEND (Next.js, TanStack Query)                                            │
│  ChipBar (generic, descriptor-driven) → per-screen thin wrappers             │
│  DrillPanel (idKey/renderContent generalized) → per-screen *-drill-content   │
│  ConnectorMark (14-provider gradient+glyph, all 6 scanners already defined)  │
│  ★ NEW: SourceBadgeGroup (row provenance) · source-mode toggle in ChipBar    │
│  ★ NEW: exposure-context override UI on asset detail rail                    │
└────────────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Status |
|-----------|----------------|--------|
| `app/connectors/base.py::NormalizedVulnerability` | Vendor-agnostic finding shape emitted by every connector | MODIFIED — add `native_risk: dict \| None` |
| `app/connectors/{qualys,rapid7,...}.py` | Per-vendor fetch + normalize | MODIFIED — populate `native_risk` from vendor-specific fields (e.g. Qualys `TRUERISK`/ExPRT.AI block, Rapid7 `riskScore`, EPSS lookups) |
| `app/connectors/sync.py::_upsert_vulnerability` | Upsert one Vulnerability row per (tenant, cve, asset, source) | MODIFIED — persist `native_risk`; call new inline scorer |
| `app/vulnerabilities/models.py::Vulnerability` | Per-source finding row, source-typed & indexed | MODIFIED — new columns (below) |
| `app/vulnerabilities/models.py::VulnerabilityCorrelation` | Cross-source dedup per (cve_id, asset_id) | MODIFIED (schema change) — replace 4 fixed FK columns with `sources ARRAY(String)` |
| `app/vulnerabilities/correlation_service.py` | Rebuild correlation rows from open vulns | MODIFIED — `SOURCE_COLUMN_MAP` only covers 4/6 sources today (confirmed gap); generalize to loop over `VulnSource` enum |
| `app/assets/models.py::Asset` | One row per host/cloud resource | MODIFIED — add exposure-context columns |
| `app/assets/risk_score.py` | Old asset-aggregate risk formula | REPLACED by clean-slate model (kept as legacy reference during cutover, then removed) |
| **NEW** `app/vulnerabilities/risk_exposure_service.py` (or `app/risk/service.py`) | Versioned, idempotent finding-level + asset-rollup scorer | NEW |
| **NEW** `app/assets/exposure_context.py` | Auto-infer criticality/data-sensitivity/internet-facing + admin override merge | NEW |
| `app/vulnerabilities/service.py::_apply_filters` / `get_facets` | Faceted list query builder | MODIFIED — OR/AND source-mode branch, `sources[]` on response |
| `app/assets/service.py::_apply_filters` | Asset list query builder | MODIFIED — same OR/AND treatment via `seen_by_sources` |
| `app/cspm/service.py` | CSPM finding list | MODIFIED — OR only (see Pitfall below) |
| `app/ticketing/*` | Ticket list/detail | MODIFIED — join through Vulnerability→Correlation for provenance |
| `app/connectors/scheduler.py::_scheduler_loop` | In-process 60s tick; per-tenant SLA/snapshot/AI-batch dispatch | MODIFIED — add one more per-tenant backfill call, same idiom as `backfill_sla_due_dates` |
| `frontend/.../ui/ChipBar.tsx` | Generic descriptor-driven chip-filter primitive | MODIFIED — additive `mode`/`onModeChange` on source axis |
| `frontend/.../vulnerabilities/drill-panel.tsx` + `drill-content.tsx` | Generalized side panel | MODIFIED — new "signals & provenance" section |
| `frontend/.../connectors/connector-mark.tsx` | 14-provider gradient+glyph badge | REUSED AS-IS — all 6 scanner gradients already defined |
| **NEW** `frontend/.../components/shared/source-badge-group.tsx` | Row-level provenance badge composing `ConnectorMark`s + overflow | NEW |
| **NEW** exposure-context panel on `/assets/[id]` right rail | Admin override UI for criticality/sensitivity/internet-facing | NEW |

## Recommended Project Structure (delta only — existing tree is unchanged elsewhere)

```
backend/app/
├── vulnerabilities/
│   ├── models.py                  # MODIFIED: Vulnerability + VulnerabilityCorrelation
│   ├── correlation_service.py     # MODIFIED: cover all 6 VulnSource values
│   ├── risk_exposure_service.py   # NEW: versioned scorer + backfill()
│   ├── service.py                 # MODIFIED: source_mode OR/AND, sources[] field
│   └── schemas.py                 # MODIFIED: native_risk, sources, risk_exposure_score
├── assets/
│   ├── models.py                  # MODIFIED: exposure_context columns
│   ├── exposure_context.py        # NEW: auto-infer + override merge
│   ├── risk_score.py              # REPLACED (rollup reads new finding scores)
│   └── service.py                 # MODIFIED: seen_by_sources → ARRAY + OR/AND
├── connectors/
│   ├── base.py                    # MODIFIED: NormalizedVulnerability.native_risk
│   ├── scheduler.py                # MODIFIED: one more per-tenant backfill call
│   └── sync.py                     # MODIFIED: persist native_risk, inline score
├── cspm/service.py                 # MODIFIED: source OR filter only
└── alembic/versions/
    ├── 034_add_native_risk_and_exposure_score.py   # NEW — additive nullable cols
    ├── 035_replace_correlation_source_columns.py    # NEW — schema-only, data copy
    └── 036_add_asset_exposure_context.py            # NEW — additive nullable cols

frontend/src/
├── components/
│   ├── ui/ChipBar.tsx                      # MODIFIED: axis.mode (or|and)
│   ├── shared/source-badge-group.tsx       # NEW
│   ├── vulnerabilities/drill-content.tsx    # MODIFIED: signals/provenance section
│   ├── assets/exposure-context-panel.tsx    # NEW
│   └── connectors/connector-mark.tsx        # unchanged, reused
```

### Structure Rationale

- New backend logic lives beside its existing sibling (`risk_exposure_service.py` next to `risk_score.py`, `exposure_context.py` next to `classification.py`) — the codebase already organizes by domain module, not by feature-flag folder, so v4.0 should not introduce a new top-level `app/risk/` package unless the scoring logic needs to be shared cross-module (it doesn't — it's consumed by `vulnerabilities` and `assets` only, which already import each other's models).
- Three Alembic migrations, not one: (034) additive columns are safe/fast and can ship independently; (035) the correlation schema replacement is the riskiest change (touches an existing table with a `UniqueConstraint`) and should be isolated so it can be reviewed/rolled back on its own; (036) asset exposure context is independent of both and can land in parallel.
- Frontend: exactly one new shared component (`source-badge-group.tsx`) is needed — everything else (ChipBar, DrillPanel, ConnectorMark, state primitives) is extended additively in place, consistent with the "Phase 11 state primitives are the single source for all list screens" Key Decision already governing this codebase.

## Architectural Patterns

### Pattern 1 — Per-scanner native signals: extend the finding row's JSONB, not a side table

**What:** Add `native_risk: Mapped[dict | None] = mapped_column(JSONB)` directly to `Vulnerability` (`backend/app/vulnerabilities/models.py`), holding source-varying keys (`vpr`, `expr_ai`, `epss`, `exploit_maturity`, `threat_intel_flags`, …). Promote any signal that needs to be **sorted or faceted** to a real typed column, exactly the way `cvss_v3_score`, `epss_score`, `exploit_available`, and `cisa_kev` already sit as typed columns next to the JSONB `file_paths` blob on the same row.

**When to use:** Any time signal shape varies per vendor and the row already has a natural 1:1 owner. `Vulnerability` is that owner here — each source produces its own row (`UniqueConstraint("tenant_id", "cve_id", "asset_id", "source")`), so there is no ambiguity about which JSONB blob a given signal belongs to.

**Why not a typed per-source-signal table:** A `vulnerability_native_signals(vuln_id FK, source, key, value)` table adds a join to every list/facet/sort query. The existing faceted API (`get_facets`) is built around a strict "one query per facet group, `<50ms` on an indexed `GROUP BY`" invariant (see the docstring in `service.py`) — that invariant depends on querying `Vulnerability` directly. A side table breaks it. JSONB with a targeted expression index (`CREATE INDEX ... ON vulnerabilities ((native_risk->>'vpr')::numeric)`) gets sortability on the handful of signals that need it without a join, and matches the project's own explicit Key Decision: *"Postgres 16 + JSONB for flexible enrichment payloads | Avoids per-vendor side tables | ✓ Good."*

**Why not the correlation table:** `VulnerabilityCorrelation` is a many-to-one aggregate over multiple `Vulnerability` rows (one correlation row can point at up to 4 — soon 6 — source rows). Native signals are inherently per-source, per-finding facts; storing them on the aggregate row would either duplicate them per source (defeating the point of the aggregate) or force the aggregate to pick a "winning" source's signal, silently losing the others. Confidence: HIGH.

**Trade-offs:** JSONB queries on unindexed keys are slower than a typed column; mitigate by promoting only signals that actually drive sort/facet/filter to typed columns (mirrors the existing severity/cvss/epss/exploit/kev split — 5 promoted fields, everything else JSONB).

### Pattern 2 — Fix the correlation table's source representation (forced dependency, not optional)

**What:** `VulnerabilityCorrelation` currently has exactly 4 nullable FK columns — `crowdstrike_vuln_id`, `nessus_vuln_id`, `defender_vuln_id`, `wiz_vuln_id` — and `correlation_service.py::SOURCE_COLUMN_MAP` only maps those same 4 sources. `_find_correlated_groups()` groups by **every** source it sees in open vulns (including QUALYS and RAPID7, which the `VulnSource` enum has included since Phase 04), and correctly counts them into `sources_count`/`confidence` — but `run_correlations()` then only reads `source_vulns.get("CROWDSTRIKE")` / `.get("NESSUS")` / `.get("DEFENDER")` / `.get("WIZ")` when building the upsert payload, so a Qualys- or Rapid7-only-detected CVE-on-host contributes to the correlation *count* but its `vuln_id` is silently dropped — there is no column to put it in. This is a real, currently-live gap, confirmed by reading the code, not a hypothetical.

**Why this blocks v4.0 specifically:** The milestone's AND-toggle ("show only findings confirmed by ALL selected sources") and the "source provenance badges … tied to the filters" requirement both need an accurate, complete list of *which* sources see a given (cve_id, asset_id) pair. A fixed-column-per-source schema that already can't represent 2 of the 6 live sources cannot be the foundation for either feature.

**What to build instead:** Replace the 4 FK columns with `sources: Mapped[list[str]] = mapped_column(ARRAY(String), server_default="{}")` (list of source names present) plus `source_vuln_ids: Mapped[dict] = mapped_column(JSONB, default=dict)` (`{source: vuln_id}` map, for the optional per-source drill-through link the old FK columns provided). `correlation_service.py` loses its hardcoded `SOURCE_COLUMN_MAP` and instead iterates whatever sources are present in `source_vulns.keys()` — automatically forward-compatible with a 7th connector.

**Trade-offs:** This is a schema migration on a live table with an existing `UniqueConstraint("tenant_id", "cve_id", "asset_id")` — the constraint itself is untouched (only the FK columns move), so the migration is additive-then-drop rather than a rebuild: add `sources`/`source_vuln_ids`, backfill from the 4 old columns in a data migration step, then drop the old columns in a follow-up release once the frontend/API no longer reference them. Confidence: HIGH (grounded directly in `correlation_service.py` and `models.py`).

### Pattern 3 — OR/AND source filtering: row-level `IN` for OR, correlation-array `@>` for AND

**What:** For **OR** (default), nothing changes structurally — `Vulnerability.source.in_(filters.source)` already does this (`_apply_filters` in `service.py`), because OR-across-sources is just "any row whose own `source` column matches." For **AND** ("show only CVE-on-host pairs confirmed by every selected source simultaneously"), a single `Vulnerability` row can never satisfy this alone — it only knows its own source. The query must instead constrain to `(cve_id, asset_id)` pairs whose `VulnerabilityCorrelation.sources` array is a superset of the selected sources, via Postgres's array-contains operator: `VulnerabilityCorrelation.sources.contains(filters.source)` (SQLAlchemy `ARRAY.contains()` compiles to `@>`). Add this as an `EXISTS` subquery (or a join) in `_apply_filters` gated by a new `source_mode: Literal["or","and"] = "or"` field on `VulnerabilityFilter`.

**For Assets:** `Asset.seen_by_sources` already plays this role today, as a JSONB list with `.contains([filters.source])` (single value only, in `assets/service.py`). Recommend migrating it from `JSONB` to `ARRAY(String)` with a GIN index — mirroring the exact precedent already in this codebase for `Asset.tags` (`alembic 025_add_asset_tags`, GIN-indexed) — which gives clean `&&` (overlap = OR) and `@>` (contains-all = AND) operators without JSONB path gymnastics, and reuses a pattern this team has already shipped once.

**For CSPM:** `Misconfiguration.source` is a single typed column (no correlation table exists for CSPM findings — there is no cross-tool CSPM dedup anywhere in this codebase). OR-mode is trivial (`source IN (...)`). **AND-mode is degenerate**: a single-source row cannot simultaneously satisfy "detected by source A AND source B." Flag this to the roadmap as an open product question rather than silently building dead UI — either disable the AND toggle on the CSPM screen, or define its semantics as a no-op that behaves identically to OR when CSPM is the active screen. Confidence: MEDIUM (architecturally sound, but the correct *product* behavior needs a decision, not just an engineering one).

**For Tickets:** `Ticket.vulnerability_id` is a single FK to one `Vulnerability` row (`ticketing/models.py`). A ticket's underlying CVE may be correlated across more sources than the one it happened to be created from. Provenance badges on the Tickets screen should therefore resolve via `Ticket.vulnerability_id → Vulnerability.(cve_id, asset_id) → VulnerabilityCorrelation.sources`, not `Vulnerability.source` directly — otherwise a ticket created from a CrowdStrike-only detection would show only "CrowdStrike" even after Qualys later confirms the same CVE on the same host. Source *filtering* on Tickets follows the same OR/AND rules as Vulnerabilities, applied through this same join.

### Pattern 4 — Versioned, idempotent risk-exposure scoring; safe one-time cutover without Celery

**What:** Two persisted score surfaces exist today and both need rebuilding: (1) `Asset.risk_score` — a per-asset aggregate, computed by `assets/risk_score.py::compute_risk_scores()` by summing severity/exploit/KEV-weighted open vulns; (2) an *implicit*, never-persisted per-finding ranking used ad hoc by `service.py`'s `sort=triage` (KEV → CVSS → SLA-due tiebreak) and by `get_top_findings_for_ai_batch` (which orders by `Asset.risk_score` first, then the same tiebreak, and says so explicitly in its own docstring: *"Vulnerability has no risk_score field at all"*). v4.0's clean-slate model should make the per-finding score **real and persisted** — the asset aggregate then becomes a rollup *of* the new finding scores, not an independently-tuned formula, so the two surfaces can never drift apart.

**Schema (additive, migration 034):**
```python
# Vulnerability
risk_exposure_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
risk_score_components: Mapped[dict | None] = mapped_column(JSONB)  # for DrillPanel breakdown
risk_model_version: Mapped[int | None] = mapped_column(Integer, index=True)

# Asset
risk_exposure_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
risk_model_version: Mapped[int | None] = mapped_column(Integer, index=True)
```
A single module constant, `RISK_MODEL_VERSION = 1` in the new `risk_exposure_service.py`, gates every recompute. Recompute is a **pure function** of `(severity, cvss, native_risk JSONB, asset exposure context) → (score, components)` — no hidden state — which is what makes it safe to re-run: the `WHERE risk_model_version IS NULL OR risk_model_version != RISK_MODEL_VERSION` predicate means re-running against already-current rows matches zero rows and is a true no-op.

**The one-time cutover — two safe, precedented mechanisms, not a new one:**

1. **New findings, scored inline at ingestion.** `sync.py::_upsert_vulnerability` already sets `severity`/`exploit_available`/`cisa_kev` at upsert time — add one more call to compute and set `risk_exposure_score`/`risk_model_version` in the same function, so every finding synced *after* deploy is scored immediately, with zero backfill lag.

2. **Existing rows, backfilled by the scheduler's proven idiom.** This codebase already has the exact pattern needed: `sla_service.py::backfill_sla_due_dates()` finds rows missing a value and fills them in batches, called every tick from `scheduler.py::_scheduler_loop`'s per-tenant SLA block (`for t in tenants: await backfill_sla_due_dates(db, t.id); await check_sla_breaches(db, t.id)`). Add a new `risk_exposure_service.py::backfill_risk_exposure(db, tenant_id, batch_size=500)` with the identical shape — `UPDATE ... WHERE risk_model_version != CURRENT LIMIT 500` in a loop until 0 rows affected — and call it from the same per-tenant loop, right alongside the SLA calls it's modeled on. Because the scheduler tick already runs every 60 seconds and this codebase's install topology is one VM per tenant (per the `PROJECT.md` constraint — multi-tenant SaaS on one deploy is explicitly out of scope), a realistic backlog (tens of thousands of vulnerabilities) clears in a small number of ticks with no risk of a long-held transaction or lock, and no new infrastructure (Celery/Arq) is needed.

**Why not a blocking Alembic data migration:** possible, but riskier for large tenants — a data-migration step inside a schema migration either blocks `alembic upgrade head` (and therefore `install.sh`'s update path) for however long the backfill takes, or requires its own batching logic duplicated outside the app's normal session/transaction handling. The scheduler-tick approach reuses code the team has already shipped and tested (`backfill_sla_due_dates`), self-throttles, and requires no operator awareness beyond "give it a few minutes after upgrading."

**Asset rollup:** `compute_risk_scores()` in `risk_score.py` is rewritten to aggregate `Vulnerability.risk_exposure_score` (already scored) instead of re-deriving severity weights from scratch, and is invoked from the identical two call sites it already has today (`sync.py`'s post-sync hook, and anywhere else that currently imports it) — no new call sites needed, only a new formula body.

**Named consumer cutover points (the roadmap should treat each as its own reviewable diff):**
- `vulnerabilities/service.py::list_vulnerabilities` — `sort="triage"` branch: switch its `ORDER BY` from the 3-column tiebreak (`cisa_kev desc, cvss_v3_score desc, sla_due_at asc`) to `risk_exposure_score desc` (falling back to the old tiebreak only for rows where `risk_model_version IS NULL`, i.e. mid-backfill).
- `vulnerabilities/service.py::get_top_findings_for_ai_batch` — its own docstring already documents the exact assumption v4.0 breaks ("Assumption A1: … a per-asset aggregate … Vulnerability has no risk_score field at all"). Once the column exists, its `ORDER BY` should read `Vulnerability.risk_exposure_score desc` directly instead of joining through `Asset.risk_score`.
- `vulnerabilities/sla_service.py` — SLA due-date computation keys off `severity` today; decide explicitly whether v4.0's SLA policy stays severity-keyed or moves to a `risk_exposure_score`-banded policy (this is a product decision, not purely technical — flag for the roadmap).
- `vulnerabilities/trends.py::capture_daily_snapshot` / `get_risk_score_trend` — historical `daily_snapshots.metrics` rows were captured under the OLD formula and must **not** be rewritten (they're point-in-time facts). The cutover will show as a one-time step change in the trend chart on the day the new model activates — document this as expected rather than a bug, and consider tagging new snapshot rows with `risk_model_version` so the frontend can annotate the discontinuity.
- **Cross-cutting, outside this milestone's stated scope but a real dependency:** `app/ai/batch.py`, `app/ai/grounding.py`, and `app/ai/prompt_builder.py` (v3.0's "prioritization narrative," which explicitly "augments/explains but never replaces the deterministic score") all read risk-score data today. Since the deterministic score's *definition* is changing, these three files need at minimum a read-path review even though no AI-facing requirement is listed for v4.0 — flag as a required regression check, not a new feature.

### Pattern 5 — Asset exposure context: auto-infer additively, override explicitly

**What:** Add nullable columns to `Asset`: `criticality: str | None`, `data_sensitivity: str | None`, `internet_facing: bool | None`, each paired with a same-named `*_source: Literal["auto","override"]` (or a single `exposure_overrides: JSONB` map naming which fields an admin has pinned). Auto-inference runs in a new `app/assets/exposure_context.py`, called from the same place `classification.py::classify_asset_from_data` is already called in `sync.py::_upsert_asset` — i.e., additively, at upsert time, using hints already available on the connector payload (cloud_provider/external_ip presence → internet-facing hint; hostname/tag patterns → criticality hint, extending the existing regex-based `classification.py` approach rather than inventing a second classification mechanism).

**Override semantics:** exactly the precedent already shipped for `Asset.tags` and the Phase-14 settings panes' `useDirtyState`/`SaveBar` pattern — an admin-set value must never be silently overwritten by the next sync. Store the override flag per field; `_upsert_asset`'s auto-inference step checks the flag and skips any field marked `override` before writing.

## Data Flow

### Enrichment → scoring → filtering → UI (the full v4.0 loop)

```
Connector.fetch_vulnerabilities()
    ↓ (NormalizedVulnerability.native_risk populated per-vendor)
sync.py::_upsert_vulnerability()
    ↓ persists native_risk JSONB + severity/cvss/kev (unchanged)
    ↓ NEW: risk_exposure_service.compute_finding_score(vuln, asset.exposure_context)
    ↓ writes risk_exposure_score / risk_score_components / risk_model_version
sync.py post-sync hook
    ↓ correlation_service.run_correlations()  → VulnerabilityCorrelation.sources[] (all 6)
    ↓ risk_score.compute_risk_scores()         → Asset.risk_score rollup of new finding scores
scheduler.py tick (every 60s, per active tenant)
    ↓ risk_exposure_service.backfill_risk_exposure()  — catches any rows the inline path missed
    ↓ sla_service.backfill_sla_due_dates() / check_sla_breaches()  — reads cut-over score
GET /api/v1/vulnerabilities?source=QUALYS&source=RAPID7&source_mode=and&facets=source,severity,status
    ↓ vulnerabilities/service.py::_apply_filters
    │   OR: Vulnerability.source.in_(...)
    │   AND: EXISTS(VulnerabilityCorrelation WHERE sources @> [...])
    ↓ get_facets() — contextual counts (existing Pitfall-1 pattern: drop own axis before counting)
    ↓ VulnerabilitySummary.sources[]  — resolved via correlation lookup for the row's (cve,asset)
Frontend: ChipBar (source axis + mode toggle) ←→ URL params ←→ TanStack Query
    ↓ list rows render <SourceBadgeGroup sources={row.sources} activeFilter={selected}/>
    ↓ DrillPanel → drill-content.tsx "Signals & provenance" section
        (native_risk breakdown, risk_score_components, full correlation source list)
```

### Key Data Flows

1. **Enrichment persistence is additive at every layer** — `NormalizedVulnerability` gains one optional field, `Vulnerability` gains three nullable columns, nothing existing is renamed or removed. This is deliberate: it means the ingestion path keeps working unmodified for any connector that hasn't been updated to populate `native_risk` yet (`getattr(v, "native_risk", None)` mirrors the existing `getattr(v, "serial_number", None)`-style defensive reads already used throughout `sync.py`).
2. **Scoring is a pure, versioned function** consumed from two call sites (inline-at-upsert for new data, scheduler-tick-backfill for existing data) — both call the *same* function, so there is exactly one formula to reason about, never two implementations drifting apart.
3. **Provenance is resolved once, at the correlation layer, and consumed everywhere** — Vulnerabilities, Assets, Tickets, and (for OR-only) CSPM all trace back to the same `VulnerabilityCorrelation.sources` array or `Asset.seen_by_sources` array; the frontend never needs vendor-specific badge logic because `ConnectorMark` already has all 6 scanner gradients defined.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| Single tenant, current data volumes (the deployed reality — one VM per customer) | Everything above works unmodified. Scheduler-tick backfill clears in minutes. |
| One tenant, very large history (100k+ open vulns) | Batch size in `backfill_risk_exposure` (start at 500, matching the existing `PAGE_SIZE` precedent in `rapid7.py`) may need tuning down to keep each scheduler tick's transaction short; the loop-until-zero-rows shape already bounds this safely regardless of the exact number. |
| Hypothetical multi-tenant SaaS (explicitly out of scope per `PROJECT.md`) | The per-tenant loop already iterates `Tenant` rows one at a time — no code change needed if this ever became in-scope, but the in-process scheduler itself remains the actual scaling blocker (documented pre-existing constraint, not introduced by v4.0). |

### Scaling Priorities

1. **First bottleneck:** a single tenant's backfill running inside the 60-second scheduler tick alongside the SLA check, ticket sync, and AI batch dispatch — if `backfill_risk_exposure` isn't capped per-tick, a huge tenant could make one tick run long enough to delay the next tick's other jobs. Mitigate with the `LIMIT 500`-per-call shape already specified above (one batch per tick, not "until done" per tick).
2. **Second bottleneck:** the `VulnerabilityCorrelation` schema migration (Pattern 2) on a live table — mitigate by making it additive-then-drop across two releases rather than one atomic rewrite.

## Anti-Patterns

### Anti-Pattern 1 — Adding a 7th/8th fixed FK column to `VulnerabilityCorrelation`

**What people do:** Extend the existing pattern by adding `qualys_vuln_id`/`rapid7_vuln_id` columns to match the (already extended) `VulnSource` enum, treating the current 4-column gap as "just needs two more columns."
**Why it's wrong:** Every future connector repeats this migration forever, and the underlying bug (`SOURCE_COLUMN_MAP` silently dropping unmapped sources) would need to be fixed at every step anyway. It also can't represent "detected by 3 of 6 possible sources" as a queryable set — you'd need a 6-way `OR` of `IS NOT NULL` checks to even count sources, which is exactly the kind of query the array-based redesign avoids.
**Instead:** Pattern 2 above — `sources ARRAY(String)`.

### Anti-Pattern 2 — Two independently-tuned risk formulas (per-asset and per-finding)

**What people do:** Build the new per-finding `risk_exposure_score` for sort/filter purposes while leaving `Asset.risk_score`'s existing severity-weight-sum formula untouched, on the theory that "the asset score already works, don't touch it."
**Why it's wrong:** The two scores will silently diverge over time (different weight tuning, different exploit/KEV handling), and any UI or AI consumer that shows both (e.g. an asset's risk ring next to its top finding's score) will look inconsistent with no way to explain why.
**Instead:** Make the per-asset score a deterministic rollup *of* the new per-finding scores (Pattern 4), computed by the same versioned pass.

### Anti-Pattern 3 — Treating the one-time recompute as a fire-and-forget background task with no idempotency guard

**What people do:** Kick off `asyncio.create_task(recompute_everything())` once at app startup and trust it to finish.
**Why it's wrong:** A process restart mid-recompute (deploy, crash, `docker compose restart`) either loses progress silently or, without a `risk_model_version` predicate, re-scores already-current rows on every restart forever.
**Instead:** The `WHERE risk_model_version != CURRENT` predicate makes every call idempotent by construction — restart-safe with zero extra bookkeeping, which is exactly why Pattern 4 recommends it over a stateful "have I done this yet" flag.

## Integration Points

### External Services

No new external services are introduced by this milestone — `native_risk` fields (VPR/ExPRT.AI/EPSS/threat-intel) come from data the existing 6 connectors already pull from their vendor APIs (Qualys KB detail, Rapid7 vuln detail, etc.) but currently discard during normalization; no new vendor credentials or endpoints are required.

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Qualys VMDR API | Extend existing `qualys.py` KB-detail parsing (`_kb_cvss3` and neighbors) to also extract ExPRT.AI / TruRisk fields already present in the same response payload | No new API calls — data is likely already in the fetched response and simply not mapped today; verify per-connector during implementation |
| Rapid7 InsightVM API | Extend `rapid7.py::_fetch_vuln_detail` to extract the existing `detail` dict's VPR/risk fields (the connector already fetches this payload for CVSS; VPR is typically a sibling field) | Same call, additional field extraction |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `connectors` ↔ `vulnerabilities` | Direct function call (`_upsert_vulnerability`), same process | Additive field only — no contract break |
| `vulnerabilities` ↔ `assets` | `risk_exposure_service` reads `Asset.exposure_context`; `risk_score.py` reads `Vulnerability.risk_exposure_score` | Both directions already exist today (Vulnerability has `asset_id` FK, `risk_score.py` already imports `Vulnerability`) — no new coupling shape, just new fields crossing it |
| `vulnerabilities` ↔ `ticketing` | New: Ticket provenance badge resolves `Ticket.vulnerability_id → Vulnerability → VulnerabilityCorrelation` | Read-only join, no schema change to `Ticket` |
| `connectors/scheduler.py` ↔ everything | Per-tenant loop, one more call added alongside the existing SLA backfill call | Matches established idiom exactly — lowest-risk integration point in this milestone |
| `vulnerabilities`/`assets` ↔ `ai` | v3.0's prioritization narrative reads deterministic score fields | Not a stated v4.0 requirement, but a real read-path dependency — flag for regression testing (see Pattern 4) |
| Frontend `ChipBar` ↔ 4 list screens (Vulnerabilities/Assets/CSPM/Tickets) | Each screen has a thin descriptor wrapper (`vulnerabilities/chip-bar.tsx`, `assets/assets-chip-bar.tsx`, `tickets/tickets-chip-bar.tsx`, + a CSPM equivalent) over the shared generic `ui/ChipBar.tsx` | New `mode` prop added once to the generic primitive is inherited by all 4 wrappers — no per-screen duplication needed |

## Suggested Build Order (dependency-respecting)

1. **Enrichment persistence (foundation).** Migration 034 (additive `native_risk`/score columns on `Vulnerability`), `NormalizedVulnerability.native_risk`, per-connector extraction (Qualys/Rapid7 first — they're named explicitly in the milestone; CrowdStrike/Nessus/Defender/Wiz as time allows), `_upsert_vulnerability` persists it. No scoring or filtering logic yet — ships independently and is safe to deploy on its own.
2. **Asset exposure context.** Migration 036, `exposure_context.py` auto-inference wired into `_upsert_asset`, admin-override API + UI. Independent of (1) but needed *before* (3), since the risk-exposure model consumes exposure context as an input.
3. **Correlation schema fix.** Migration 035 (`sources ARRAY` + `source_vuln_ids` JSONB, data-copy from the 4 old columns, then a follow-up migration to drop them), `correlation_service.py` generalized off the `VulnSource` enum instead of `SOURCE_COLUMN_MAP`. Needed before (5) — AND-mode filtering and accurate provenance both depend on this being correct first. Can be built in parallel with (1)/(2) since it doesn't depend on either, but must land before (5).
4. **Risk-exposure model + one-time recompute.** `risk_exposure_service.py` (depends on (1) native signals + (2) exposure context existing), inline scoring at upsert, scheduler-tick backfill (mirrors `backfill_sla_due_dates`), `risk_score.py` rewritten as a rollup. This is the "clean slate" — do it once (1) and (2) are both in place so the formula has real inputs from day one rather than being retrofitted.
5. **SLA/sort/trend consumer cutover.** Named seams from Pattern 4: `sort="triage"`, `get_top_findings_for_ai_batch`, SLA due-date policy (product decision needed), trend snapshot tagging. Depends entirely on (4) being live and backfilled.
6. **Source filtering (OR/AND) + provenance badges.** Backend: `source_mode` filter branch + `sources[]` on response schemas (depends on (3)). Frontend: `ChipBar` mode toggle, `SourceBadgeGroup`, `DrillPanel` provenance section. This is the natural last step — it surfaces data that steps 1–3 make available, and its correctness (especially AND-mode) is only as good as step 3's schema fix.

This order front-loads the two schema fixes that unlock everything else (enrichment columns, correlation array) before building any user-facing behavior on top of them, defers the riskiest live-table migration (correlation columns) to its own isolated step, and holds the SLA/sort/trend cutover until the new score has real data to serve — avoiding a window where consumers read a freshly-added-but-still-empty column.

## Sources

- `backend/app/vulnerabilities/models.py`, `service.py`, `correlation_service.py`, `sla_service.py`, `trends.py`, `schemas.py` — read directly, current on-disk state
- `backend/app/assets/models.py`, `risk_score.py`, `service.py`, `classification.py` — read directly
- `backend/app/connectors/base.py`, `sync.py`, `scheduler.py`, `rapid7.py`, `qualys.py` — read directly
- `backend/app/cspm/models.py`, `backend/app/ticketing/models.py` — read directly
- `frontend/src/components/ui/ChipBar.tsx`, `vulnerabilities/chip-bar.tsx`, `vulnerabilities/drill-panel.tsx`, `states/per-source-status-strip.tsx`, `connectors/connector-mark.tsx` — read directly
- `.planning/PROJECT.md` — v4.0 requirement list, Key Decisions table, deployment constraints

---
*Architecture research for: GetVul v4.0 — Enriched Risk Exposure & Source-Aware Triage*
*Researched: 2026-08-04*
