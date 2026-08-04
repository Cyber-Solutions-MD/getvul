# Project Research Summary

**Project:** GetVul v4.0 — Enriched Risk Exposure & Source-Aware Triage
**Domain:** Risk-based vulnerability management (RBVM) — scanner-signal enrichment, deterministic risk-exposure scoring, and multi-scanner source-aware filtering/provenance, layered onto an existing production FastAPI/Postgres/Next.js monolith
**Researched:** 2026-08-04
**Confidence:** HIGH

## Executive Summary

This is not a green-field feature build — it is an extension and partial rebuild of infrastructure that already exists and is already live in production. GetVul already has `epss_score`/`exploit_available`/`cisa_kev` columns on `Vulnerability`, a documented deterministic asset risk formula (`risk_score.py`), a `vulnerability_correlations` cross-source dedup table, and an OR-semantics source chip-filter on `/vulnerabilities`. All four research streams (stack, features, architecture, pitfalls) independently converged on the same conclusion: **the headline v4.0 features (deeper enrichment, a rebuilt risk model, AND-toggle corroboration, provenance badges) cannot be built correctly on top of the current schema** because two concrete, verified defects sit directly in their path — `VulnerabilityCorrelation` only has FK columns for 4 of the 6 live scanners (Qualys and Rapid7 correlation data is silently dropped today), and all six connectors already flatten every vendor-native risk signal (VPR, ExPRT.AI, exploit counts, real KEV status) down to two lossy booleans at ingestion, with `epss_score` populated by zero of them. Both are prerequisite fixes, not part of the "new" work — the milestone's own success criteria (accurate AND-toggle, honest provenance badges, a risk model with real inputs) are unreachable without closing them first.

The recommended approach is entirely additive at the schema/stack level (no new infrastructure, no new third-party dependency — `httpx`/`tenacity`/`orjson`/stdlib `gzip`/`csv` already cover EPSS/KEV ingestion) but requires a genuine, carefully-sequenced rebuild at the model/behavior level. The single highest-risk piece of work is the "clean slate" risk-exposure model, because `Asset.risk_score` today is not a UI nicety — it is read, sorted, or thresholded against in at least 11 backend call sites, plus **tenant-authored data** (automation-rule and saved-filter `min_risk_score` thresholds) whose meaning silently changes the moment the formula changes underneath it. Research strongly recommends splitting this into two distinct phases — "define the new model" (versioned, shadow-computed, reusing the existing chip-bar/JSONB/GIN-index patterns already proven in this codebase) and "recompute + cut over" (a throttled, idempotent, per-tenant backfill reusing the exact `backfill_sla_due_dates` + scheduler-tick idiom already shipped) — because conflating them risks pegging the single VM, corrupting tenant isolation, or leaving no rollback path if the formula turns out to be miscalibrated.

The second major risk is treating "scanner-source filtering across 4 screens" as one reusable query pattern. It is not: Vulnerabilities has a real per-CVE-per-asset correlation table (once fixed) that can support true AND-semantics; Assets has a JSONB array shared between scanners and non-scanner enrichment sources (JAMF/HUMAANS/Intune) that must be partitioned before it becomes a scanner-source filter; CSPM has no correlation concept at all, making its AND-toggle architecturally degenerate and requiring an explicit product decision (disable it, or define a new resource+rule-id grouping); and Tickets has no source column of its own — provenance there is entirely transitive through a linked vulnerability's correlation. Each of these needs its own design sign-off and its own regression test, not a single shared filter helper.

## Key Findings

### Recommended Stack

No new stack: this milestone is purely additive schema work on the existing Python 3.12 / FastAPI / SQLAlchemy 2.0 async / Postgres 16 / Redis stack, using libraries already pinned in `pyproject.toml`. The strongest existing precedent to reuse is `assets.tags` (`ARRAY(String)` + GIN index, migration `025_add_asset_tags`) as the exact shape for `vulnerability_correlations.sources` (OR via `&&`, AND via `@>`) — this is a proven pattern in this codebase already, not a new one to review.

**Core technologies/additions:**
- `vulnerabilities.source_signals` (JSONB) + a small number of promoted typed columns (`vpr_score`, `exprt_rating`, `exprt_score`) — mirrors the existing `severity`/`cvss_v3_score`/`epss_score` split of "typed for sort/filter, JSONB for the long tail," and the existing `Asset.mdm_details` JSONB precedent
- Two new global, tenant-independent reference tables — `epss_scores` and `cisa_kev` — refreshed once daily via the existing in-process scheduler (`_scheduler_loop`), not per-tenant; this is a deliberate, explicit exception to the "every table has `tenant_id`" convention and needs roadmap/requirements sign-off
- `vulnerability_correlations.sources ARRAY(String)` + GIN index (replacing the 4 hardcoded FK columns) — same operators/index strategy as `assets.tags`
- `httpx` + `tenacity` + stdlib `gzip`/`csv` for the EPSS CSV and CISA KEV JSON feeds — zero new dependencies
- Reuse the existing in-process `asyncio` scheduler for the daily refresh; explicitly rejected: Celery/Arq, a dedicated microservice, Elasticsearch/OpenSearch, TimescaleDB, an EAV signals table, third-party EPSS SDKs — none justified at this scale/deployment topology

### Expected Features

**Must have (table stakes for a v4.0 that doesn't read as "still CVSS-only"):**
- EPSS score + percentile surfaced per finding, ingestion made consistent (column exists, is currently unpopulated by every connector)
- CISA KEV as a near-automatic escalation/floor signal (not just a multiplier), matching BOD 26-04 guidance
- Vendor-native exploitability signal (Tenable VPR / CrowdStrike ExPRT.AI / Qualys QDS-equivalent) captured per finding, not thrown away at ingestion
- Asset criticality / data sensitivity / internet-facing exposure context, at minimum a manual override
- A real per-finding risk-exposure score, not only a per-asset aggregate (current model is asset-only; the finding-level list can't sort by "most urgent finding" without one)
- Deterministic, explainable formula — not an ML black box; consistent with the v3.0 "AI augments, never replaces the score" invariant
- Source-provenance badge per finding row, and an OR-semantics source filter extended from Vulnerabilities to Assets/CSPM/Tickets

**Should have (differentiators):**
- AND-toggle for true multi-scanner corroboration — the single most novel ask in the milestone; no vendor UI precedent exists because single-scanner tools structurally can't need it
- Corroboration count as an explicit scoring input (confidence/urgency bump for cross-validated findings) — a genuine GetVul-only innovation enabled by being a 6-scanner aggregator
- Auto-inferred exposure context mined from existing MDM/HR/IdP enrichment (no new connector needed), with admin override + audit trail
- DrillPanel score breakdown ("why is this an 82") showing each contributing input

**Defer (beyond this milestone):**
- In-house ML exploit-prediction model (no defensible training data at single-tenant scale; consume vendor ML output instead)
- Wiz-style toxic-combination/attack-path reachability signals — explicitly out of scope per PROJECT.md
- Group-scope exposure-context override UI — ship per-asset override first
- Compound "why exposed" summary chips beyond the DrillPanel — presentation polish, sequence after fields are stable

### Architecture Approach

Every new piece of backend logic lands beside its existing sibling module (`risk_exposure_service.py` next to `risk_score.py`, `exposure_context.py` next to `classification.py`) — no new top-level package is justified. Three separate, independently-reviewable Alembic migrations are recommended rather than one: additive enrichment/score columns (safe, fast), the correlation-table schema replacement (riskiest — touches a live table with an existing `UniqueConstraint`, should be isolated and additive-then-drop across two releases), and asset exposure-context columns (independent, can land in parallel). On the frontend, exactly one new shared component is needed (`SourceBadgeGroup`) — `ChipBar`, `DrillPanel`, and `ConnectorMark` (all 6 scanner gradients already defined) are extended additively in place.

**Major components:**
1. `risk_exposure_service.py` (new) — a pure, versioned scoring function consumed from two call sites (inline at ingestion for new data, scheduler-tick backfill for existing data), gated by a `risk_model_version` column so recompute is idempotent and restart-safe by construction
2. `exposure_context.py` (new) — auto-infer criticality/data-sensitivity/internet-facing at asset-upsert time, with an explicit per-field override discriminator that permanently wins over auto-inference once set
3. `correlation_service.py` (modified) — replace the hardcoded 4-source `SOURCE_COLUMN_MAP` with a `sources ARRAY(String)` + `source_vuln_ids JSONB` shape that generalizes over the full `VulnSource` enum (all 6, forward-compatible with a 7th)
4. Per-connector ingestion rewrites (all 6: CrowdStrike, Nessus, Defender, Wiz, Qualys, Rapid7) — thread native signals through from the raw vendor payload, not the already-boolean-ized intermediate dataclass
5. `_apply_filters`/`get_facets` per entity (Vulnerabilities, Assets, CSPM, Tickets) — OR via row-level `IN`/array-overlap, AND via correlation-array `@>` (Vulnerabilities/Assets), CSPM/Tickets requiring their own explicitly-designed semantics

Suggested build order (dependency-respecting, per Architecture research): enrichment persistence → asset exposure context → correlation schema fix → risk-exposure model + one-time recompute → SLA/sort/trend consumer cutover → source filtering + provenance badges. The correlation fix and enrichment rewrite can proceed in parallel but both must land before the model rebuild and before source filtering/badges.

### Critical Pitfalls

1. **Tenant-authored automation-rule/saved-filter `min_risk_score` thresholds silently reinterpret the new score** — these live in tenant data, not code, and nothing forces a review when the formula's numeric meaning changes. Avoid by shipping a pre/post diff report per tenant and requiring explicit re-tuning acknowledgment before cutover, not a silent reinterpretation.
2. **No `risk_model_version` column makes the recompute non-idempotent and unrollbackable** — without it there is no way to tell which assets/findings reflect the old vs. new formula, no safe resume point after a partial failure, and no rollback path. This is the single most important prerequisite before any recompute code is written.
3. **The recompute can peg the single VM and starve the in-process scheduler** — `compute_risk_scores()` already does a per-row Python-loop `UPDATE`, and a heavier, more-joined formula makes this strictly worse. Fix: convert to bulk `UPDATE ... FROM`, run the one-time migration outside the scheduler's tick as a standalone chunked script (reusing the `backfill_sla_due_dates` idiom for steady-state, not the historical bulk pass), and load-test against a realistic fixture.
4. **All six connectors already flatten native signals into lossy booleans, and `epss_score` is populated by none of them** (Defender additionally hardcodes `cisa_kev=False` unconditionally, a live correctness bug). A schema migration alone changes nothing — the six ingestion rewrites are a mandatory, atomic part of the same deliverable, not an optional follow-up.
5. **"Source" is a structurally different data shape on each of the 4 target screens**, and the existing correlation table's 4-of-6-source gap means an AND-filter built on it today would double-count (or silently drop) Qualys/Rapid7-only findings. Each entity (Vulnerabilities, Assets, CSPM, Tickets) needs its own explicit OR/AND design and its own multi-source-seeded regression test — not one shared filter helper.

## Implications for Roadmap

Based on combined research, suggested phase structure:

### Phase 1: Correlation Schema Fix (prerequisite, blocking)
**Rationale:** `VulnerabilityCorrelation`'s `SOURCE_COLUMN_MAP` only covers 4 of 6 `VulnSource` values today — a live, verified bug (Qualys/Rapid7 correlation data is silently dropped). Every downstream v4.0 feature that reads "which sources see this finding" (AND-toggle, provenance badges, corroboration-as-scoring-input) inherits this gap if not fixed first.
**Delivers:** `vulnerability_correlations.sources ARRAY(String)` + GIN index (replacing the 4 fixed FK columns), `correlation_service.py` generalized to loop over the full enum instead of a hardcoded map, backfill/data-copy from the old columns.
**Addresses:** Foundation for source-provenance badges and AND-toggle filtering (FEATURES.md).
**Avoids:** Pitfall 11 (JSONB/correlation drift + hardcoded 4-source columns) and the double-counting failure mode named in Pitfall 15.

### Phase 2: Connector Enrichment Rewrite
**Rationale:** Deeper connector enrichment is a stated milestone centerpiece, but adding schema without rewriting all six connectors' ingestion parsing leaves new fields permanently null/inconsistent — indistinguishable from a real absence.
**Delivers:** `NormalizedVulnerability.native_risk` (or `source_signals` JSONB) threaded through each of the six connectors' raw-payload parsing; promoted typed columns for filter/sort-critical signals (`vpr_score`, `exprt_rating`/`exprt_score`); fix the Defender `cisa_kev=False` hardcode; populate the currently-dead `epss_score` column or explicitly deprecate it; new global `epss_scores`/`cisa_kev` reference tables refreshed daily via the existing scheduler.
**Uses:** `httpx`/`tenacity`/`orjson`/stdlib `gzip`+`csv` (STACK.md) — no new dependencies.
**Implements:** Per-connector ingestion rewrite pattern (ARCHITECTURE.md Pattern 1); explicit signal-presence modeling to avoid conflating "missing" with "negative" (Pitfall 10).

### Phase 3: Asset Exposure Context
**Rationale:** The risk-exposure model needs exposure context as an input; sequencing this before the model rebuild avoids building the formula twice. Independent of Phases 1–2, but must land before Phase 4.
**Delivers:** `criticality`/`data_sensitivity`/`internet_facing` columns on `Asset` with a per-field override discriminator; auto-inference wired into asset upsert, seeded from (not overwriting) existing `Asset.tags`; admin override UI + audit trail; a calibration sanity check bounding the proportion of assets auto-classified as highest-criticality.
**Addresses:** Auto-inferred exposure context + admin override (FEATURES.md differentiator).
**Avoids:** Pitfall 13 (override/tags precedence conflicts) and Pitfall 14 (criticality inflation cascading into SLA/score distortion).

### Phase 4: Risk-Exposure Model Definition (formula only — no recompute yet)
**Rationale:** Research strongly recommends separating "define the model" from "recompute/cutover" into distinct phases — conflating them is how a miscalibrated formula reaches every tenant with no safety net (Pitfall 4).
**Delivers:** `risk_exposure_service.py` — a pure, versioned function consuming Phase 1–3 outputs (native signals, exposure context, correlation-count) plus existing severity/CVSS/EPSS/KEV; new nullable `risk_exposure_score`/`risk_score_components`/`risk_model_version` columns on both `Vulnerability` and `Asset`; computed into a shadow column for at least one sync cycle before any consumer reads it; centralizes the currently-triplicated hardcoded severity-tier boundaries (`export.py`, `assets/router.py`, `dashboard.py`) into one constant.
**Implements:** ARCHITECTURE.md Pattern 4 (versioned, idempotent scoring).
**Avoids:** Pitfall 2 (duplicated tier boundaries), Pitfall 3 (no version tag), Pitfall 4 (no shadow/comparison period).

### Phase 5: Historical Recompute & Consumer Cutover
**Rationale:** This is the highest-risk phase in the milestone — `Asset.risk_score` has 11+ backend call sites plus tenant-authored automation-rule/saved-filter thresholds that will silently reinterpret under a new formula. Must run after Phase 4's shadow period produces a reviewed diff report, and must not conflate with model definition.
**Delivers:** Chunked, throttled, resumable per-tenant backfill (reusing the `backfill_sla_due_dates` + scheduler-tick idiom, `LIMIT`-per-tick, never a blocking Alembic data migration); bulk `UPDATE ... FROM` instead of the existing per-row Python loop; per-tenant isolation regression test; a pre/post diff report for every tenant's `min_risk_score` automation rules and saved filters, requiring explicit re-tuning acknowledgment; version-boundary guards on `_check_risk_score_changes()` and the trend chart to prevent an alert-storm/cliff on cutover day; named consumer cutover diffs for `sort="triage"`, `get_top_findings_for_ai_batch`, SLA due-date policy (explicit product decision needed on severity-keyed vs. score-banded), and a regression-check pass on the v3.0 AI read paths that consume the deterministic score.
**Avoids:** Pitfalls 1, 5, 6, 7, 8 (tenant-threshold reinterpretation, trend/alert discontinuity, cross-tenant bleed, VM-pegging, partial-failure mixed state) — this phase's completion criteria should explicitly include a load test and a kill-mid-run-and-resume test, not just correctness tests on seed rows.

### Phase 6: Source-Aware Filtering & Provenance Badges (per-entity design)
**Rationale:** "Source" is a genuinely different data shape on each of the four target screens — this is not one reusable query pattern reused four times, and building it as if it were risks double-counting (Vulnerabilities), leaking non-scanner sources into the filter (Assets), building dead UI (CSPM has no correlation concept), or an undefined transitive rule (Tickets).
**Delivers:** Per-entity OR/AND design sign-off: Vulnerabilities (correlation-array `@>`/`&&`, depends on Phase 1), Assets (partition `seen_by_sources` to scanner-only values, migrate to `ARRAY`+GIN mirroring `tags`), CSPM (explicit product decision: disable AND toggle or define a new resource+rule-id grouping — do not silently degrade to OR-only without documenting it), Tickets (transitive rule through `Vulnerability`→`VulnerabilityCorrelation`, explicitly defined for multi-source-correlated cases). `SourceBadgeGroup` frontend component, batched (not per-row/N+1) provenance queries, and a visually-distinct single-source vs. multi-source-confirmed badge state.
**Addresses:** Scanner-source filter OR/AND (FEATURES.md table stakes + differentiator), provenance badges.
**Avoids:** Pitfall 15 (per-entity semantics/double-counting) and Pitfall 16 (badges overclaiming confirmation + N+1 performance).

### Phase Ordering Rationale

- Phases 1–2 (correlation fix, connector enrichment) can proceed in parallel — neither depends on the other — but both are hard prerequisites for Phase 4 (the model needs real inputs) and Phase 6 (badges/AND-toggle need the correlation fix specifically).
- Phase 3 (exposure context) is independent of 1–2 but must land before Phase 4, since the model consumes exposure context as a multiplier input.
- Phases 4 and 5 are deliberately split (not one "rebuild the model" phase) per the explicit recommendation in both FEATURES.md and PITFALLS.md — defining the formula and running the one-time cutover have different risk profiles and different verification criteria (shadow-period review vs. load-test/isolation-test).
- Phase 6 is sequenced last because its correctness depends entirely on Phase 1 (correlation completeness) and benefits from Phase 4/5 being stable (so the DrillPanel breakdown reflects the final formula, not a moving target).
- This order front-loads the two riskiest schema fixes (correlation array, enrichment rewrite) before any user-facing behavior is built on top of them, and holds the SLA/sort/trend cutover until the new score has real, backfilled data to serve.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 5 (Historical Recompute & Cutover):** Needs concrete load-test sizing against realistic single-VM tenant fleet sizes, and a decided product policy for SLA due-date computation (severity-keyed vs. score-banded) — this is a product decision the roadmap should surface explicitly, not leave implicit.
- **Phase 6 (Source-Aware Filtering):** CSPM's AND-toggle semantics is an open product question (disable vs. new resource+rule-id correlation concept) that needs sign-off before implementation, not discovery mid-build.
- **Phase 3 (Exposure Context):** The auto-inference heuristic's calibration/proportion thresholds need validation against realistic seed data before the criticality-inflation risk (Pitfall 14) can be assessed as resolved.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Correlation Schema Fix):** Directly mirrors the already-shipped `assets.tags` ARRAY+GIN pattern; no new pattern to research.
- **Phase 2 (Connector Enrichment):** Uses only already-pinned dependencies (`httpx`, `tenacity`, `orjson`, stdlib); the JSONB-plus-promoted-typed-columns pattern already exists on `Vulnerability` today.
- **Phase 4 (Risk-Exposure Model Definition):** The versioned/idempotent scoring pattern directly reuses the existing `backfill_sla_due_dates` idiom already shipped in this codebase.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Verified directly against current source (`models.py`, `risk_score.py`, connector files, `pyproject.toml`) and live-fetched EPSS/CISA KEV feed schemas on 2026-08-04; zero new dependencies needed |
| Features | MEDIUM-HIGH | Vendor methodology descriptions (Tenable VPR, Qualys TruRisk, CrowdStrike ExPRT.AI, Rapid7 Active Risk, Kenna) are HIGH confidence from official docs; exact proprietary ML weights are undisclosed (LOW), but GetVul's deterministic-formula approach sidesteps needing them |
| Architecture | HIGH | Every claim grounded in direct reads of the actual backend/frontend files; two items (CSPM AND-toggle semantics, AI-read-path cutover scope) explicitly flagged as open product questions rather than asserted as fact |
| Pitfalls | HIGH for GetVul-specific findings | All verified by direct code inspection (`risk_score.py`, `correlation_service.py`, `scheduler.py`, all six connectors, `alerts.py`, `rule_engine.py`); MEDIUM for general migration/shadow-period industry framing (standard SRE practice, not tied to a single external doc) |

**Overall confidence:** HIGH

### Gaps to Address

- **CSPM AND-toggle product decision:** Architecture and Pitfalls research both flag this as unresolved — the roadmap should require an explicit decision (disable vs. new correlation concept) before Phase 6 planning, not leave it to be discovered mid-implementation.
- **SLA due-date policy under the new model:** Whether SLA windows stay severity-keyed or move to a risk-exposure-score-banded policy is a product decision, not a technical one — flag for roadmap/requirements sign-off before Phase 5.
- **Global EPSS/KEV reference-table exception to per-tenant data modeling:** This is a deliberate, explicit deviation from the "every domain table has `tenant_id`" convention (correct for this data, since it's CVE-level fact, not tenant-owned) — needs explicit requirements sign-off so it isn't flagged as an oversight later.
- **EPSS/KEV refresh cadence vs. connector sync cadence:** Pitfall 12 notes that if EPSS/KEV values are only refreshed on a connector's next sync (not the dedicated daily feed job), signals can lag by as much as a connector's configured sync interval — the roadmap should confirm the dedicated refresh job (Phase 2) is authoritative and decouple it explicitly from any individual connector's cadence.
- **v3.0 AI subsystem read-path regression:** `app/ai/batch.py`, `grounding.py`, `prompt_builder.py` all read deterministic score fields today; not a stated v4.0 requirement, but a real dependency that needs at minimum a regression-test pass once the score's definition changes (flagged in both Architecture and Pitfalls research).

## Sources

### Primary (HIGH confidence)
- Direct source reads: `backend/app/vulnerabilities/models.py`, `correlation_service.py`, `service.py`, `sla_service.py`, `trends.py`, `saved_filters.py`; `backend/app/assets/models.py`, `risk_score.py`, `service.py`, `classification.py`; `backend/app/connectors/{base,sync,scheduler,crowdstrike,nessus,defender,wiz,qualys,rapid7}.py`; `backend/app/cspm/models.py`; `backend/app/ticketing/models.py`, `rule_engine.py`; `backend/app/notifications/alerts.py`; `backend/app/export.py`; `backend/alembic/versions/025_add_asset_tags.py`; `backend/pyproject.toml`; `frontend/src/components/{ui/ChipBar.tsx, vulnerabilities/, connectors/connector-mark.tsx, states/per-source-status-strip.tsx}`; `.planning/PROJECT.md`
- Live-fetched feed schemas (2026-08-04): FIRST.org EPSS daily CSV (`epss.empiricalsecurity.com`), CISA KEV JSON feed (`count: 1657`, `catalogVersion` 2026.08.03)
- Vendor documentation: Tenable VPR docs/blog, Qualys TruRisk/QDS/ACS docs, CrowdStrike ExPRT.AI blog/product page, Rapid7 Active Risk whitepaper, Kenna/Cisco risk-scoring docs, Wiz toxic-combination/attack-path docs, CISA KEV catalog docs

### Secondary (MEDIUM confidence)
- FIRST.org EPSS API/data pages — endpoint and cadence cross-checked across multiple pages
- General CTEM (Gartner-derived) framing and standard SRE score-migration/shadow-period practice — industry consensus, not a single citable source

### Tertiary (LOW confidence)
- PyPI EPSS client packages (`epss-api`, `epss-checker`) — surfaced only to explicitly rule out as unnecessary; not recommended for use

---
*Research completed: 2026-08-04*
*Ready for roadmap: yes*
