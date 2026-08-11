# Phase 33: Risk-Exposure Model Definition - Research

**Researched:** 2026-08-11
**Domain:** Backend deterministic scoring service (FastAPI/SQLAlchemy/Alembic) + explainability surface (Next.js DrillPanel). No ML, no new external dependencies.
**Confidence:** MEDIUM-HIGH — all existing-code reconnaissance is HIGH confidence (read directly, file:line cited below). The recommended scoring *weights* (how many of the 100 points go to EPSS vs. exposure vs. corroboration) are inherently a business judgment call with no external authority to verify against — those are flagged `[ASSUMED]` throughout and summarized in the Assumptions Log for explicit confirmation before the planner locks task-level detail.

## Summary

No code for a per-finding risk-exposure score exists today. `backend/app/assets/risk_score.py` (147 lines) computes a **per-asset aggregate** by summing weighted severity contributions (with exploit/KEV multipliers) across all of an asset's open vulnerabilities and squashing the sum through a piecewise power/log curve into 0-100. It has no concept of EPSS, no concept of cross-scanner corroboration, and no per-finding breakdown — a `Vulnerability` row has no risk-score column at all today (confirmed directly in `service.py:527-554`'s own docstring: *"Vulnerability has no risk_score field at all"*).

Phases 30-32 already landed exactly the inputs this phase needs to consume: `VulnerabilityCorrelation.sources_count` (Phase 30, cross-scanner corroboration), `epss_score`/`epss_percentile`/`cisa_kev`/`native_priority_score`/`native_priority_rating`/`source_signals` on `Vulnerability` (Phase 31), and `business_criticality`/`data_sensitivity`/`internet_facing` on `Asset` (Phase 32). None of these are normalized against each other today — in particular, `native_priority_score` is explicitly documented as "raw value verbatim, no cross-scale normalization (that's Phase 33)" (`models.py:75`) and is populated on 4 wildly different vendor scales (Nessus VPR 0-10, Qualys QDS 0-100, Rapid7 Risk Score 0-1000, CrowdStrike ExPRT — scale unverified) while Defender and Wiz never populate it at all. Building the per-source normalization table is this phase's least-obvious, highest-risk task.

The severity-tier boundary triplication named in the phase goal is confirmed exactly: `dashboard.py:125-128`, `export.py:368-371`, and `assets/router.py:297-300` all independently hardcode the identical `>=80 / >=50 / >=20` thresholds against `Asset.risk_score`. A fourth, frontend copy of the same boundaries also exists (`RiskRing.tsx:22-25`, `getRiskBand`) — out of the phase's explicit backend-only scope, but worth flagging to the planner as a related decision point.

The codebase already has two directly-reusable idioms this phase should mirror rather than invent: (1) `risk_score.py`'s split between a pure, DB-free normalization function (`_normalize_raw_score`) and a DB-orchestration function (`compute_risk_scores`) — this split is exactly what makes the new formula unit-testable via fixtures without a database; and (2) `service.py::get_vulnerability`'s existing live per-request `VulnerabilityCorrelation.sources_count` lookup (`service.py:191-200`), which is the wiring precedent for surfacing correlation data on the detail response (though for the *persisted* shadow score itself, this research recommends writing at compute time, not recomputing on every read — see "Shadow-Compute Design" below).

**Primary recommendation:** Add a new `backend/app/vulnerabilities/risk_exposure_service.py` with a pure `score_finding(...) -> RiskBreakdown` function (0-100, additive weighted components: severity/CVSS 35pts + EPSS 20pts + native-exploitability 15pts + exposure-context 20pts + corroboration 10pts) plus a KEV floor applied after weighting (`max(raw, 90)` if `cisa_kev`), and a DB-orchestration `compute_finding_risk_scores(db, tenant_id)` that mirrors `compute_risk_scores`'s existing full-tenant-recompute-every-sync shape. Persist three new nullable columns on `Vulnerability` (`risk_exposure_score`, `risk_exposure_breakdown` JSONB, `risk_model_version`) plus two new nullable columns on `Asset` (`risk_exposure_score`, `risk_model_version`) for the future rollup — all populated by the new function, called alongside (not replacing) `compute_risk_scores` at the exact same `sync.py:172-173` hook point. Zero existing consumer reads any of these five new columns; the *only* place they surface in Phase 33 is a new read-only "Risk Exposure" section in the DrillPanel (RISK-05) — an intentional, documented carve-out from the "zero consumers" gate (RISK-06), since a human-only display is not an automated decision system. Centralize the `80/50/20` tier boundaries into three named constants in `app/assets/risk_score.py` (the file that already owns `SEVERITY_WEIGHTS` for the asset score) and import them into the three call sites, with zero behavior change.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Per-finding score computation | API / Backend (`app/vulnerabilities/risk_exposure_service.py`, new) | Database (reads `Vulnerability`/`VulnerabilityCorrelation`/`Asset`) | Pure function + DB-orchestration split, mirrors `assets/risk_score.py` |
| Per-source native-signal normalization | API / Backend (same new module) | — | Business logic, no DB access needed once inputs are fetched |
| Score + breakdown persistence | Database / Storage (`vulnerabilities`, `assets` tables) | — | New nullable columns, materialized at compute time — same precedent as `Asset.risk_score`/`device_category` |
| Shadow-compute trigger | API / Backend (`app/connectors/sync.py:172-173`) | — | Same hook point as existing `run_correlations`/`compute_risk_scores` post-sync call |
| Severity-tier constant centralization | API / Backend (`app/assets/risk_score.py`) | — | Already owns `SEVERITY_WEIGHTS`; the 3 call sites (`dashboard.py`, `export.py`, `assets/router.py`) import from it |
| Explainability display | Browser / Client (`drill-content.tsx`, new "Risk Exposure" section) | API / Backend (`VulnerabilityResponse` schema, new fields) | Read-only display of already-persisted breakdown JSON — mirrors `RiskCard`'s existing per-asset breakdown-row pattern |
| Consumer cutover (SLA/sort/trend/AI-batch/automation-rules) | — | — | Explicitly OUT OF SCOPE — Phase 34 (RISK-08) |
| Historical bulk backfill (idempotent/resumable/throttled) | — | — | Explicitly OUT OF SCOPE — Phase 34 (RISK-07) |

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RISK-01 | Deterministic, explainable (non-ML) model from severity/CVSS + EPSS + KEV + native exploitability + exposure context + corroboration | "Recommended Deterministic Scoring Formula" section — full weighted-component design with per-source native-signal normalization table |
| RISK-02 | Real per-finding score persisted; asset score becomes a rollup; finding list sortable by "most urgent finding" | "Per-Finding Persistence + Asset Rollup Design" — new `Vulnerability.risk_exposure_score` column + `Asset.risk_exposure_score` MAX-rollup (shadow only in this phase; sort cutover is Phase 34/RISK-08) |
| RISK-03 | CISA KEV acts as near-automatic escalation/floor, provable with a fixture | "KEV Floor Mechanics" section — `max(raw, KEV_FLOOR)` design + exact fixture shape |
| RISK-04 | Cross-scanner corroboration measurably raises the score, provable with a fixture | "Corroboration Mechanics" section — `VulnerabilityCorrelation.sources_count` → capped linear fraction + exact fixture shape |
| RISK-05 | Analyst can see per-input breakdown ("why is this an 82") in the DrillPanel | "DrillPanel Breakdown Approach" section — new section + wire contract + component reuse |
| RISK-06 | `risk_model_version` column, shadow-computed ≥1 full sync cycle, zero consumers before cutover; severity-tier boundaries centralized | "Shadow-Compute + Versioning Contract" + "Severity-Tier Centralization" sections |
</phase_requirements>

## Existing-Code Reconnaissance

### `backend/app/assets/risk_score.py` (147 lines) — the CURRENT per-asset model

- **What it computes:** For each tenant, sums a weighted contribution per OPEN/IN_PROGRESS vulnerability on each asset: `SEVERITY_WEIGHTS[severity] × (2.0 if exploit_available else 1.0) × (3.0 if cisa_kev else 1.0)` (`risk_score.py:44-54, 92-110`). `SEVERITY_WEIGHTS = {CRITICAL: 40, HIGH: 20, MEDIUM: 5, LOW: 1, INFO: 0}`.
- **How it normalizes:** The raw weighted sum (unbounded, can be very large for an asset with many vulns) is squashed into 0-100 via a piecewise curve — sub-linear power curve below `KNEE_RAW=120` (caps at `KNEE_SCORE=45`), then a log curve from 45→100 up to `MAX_RAW=1500` (`risk_score.py:62-81`). This is a genuinely different mathematical shape than an additive point budget — it exists specifically to prevent volume of low-severity vulns from ever reaching "critical" territory while letting a handful of exploitable/KEV criticals reach 80-100 fast.
- **Where persisted:** `Asset.risk_score: int | None` (`assets/models.py:62`), a bare materialized column with no companion `*_source` discriminator (unlike the Phase 32 exposure fields) and no versioning.
- **What invokes it:** `POST /assets/recompute-risk-scores` (`assets/router.py:650-660`, admin-only). Also called inline after nearly every write path that could change severity/status: `connectors/sync.py:173` (post-sync), `seed.py:242`, `dev_routes.py:35`, `ticketing/router.py:463` (after ticket-triggered status change), and **four separate call sites inside `vulnerabilities/router.py`** (status update, bulk status update, snooze/unsnooze paths — lines 508/523, 544/557, 576/609, 745/770, 804/818). This fan-out matters: the new per-finding function does **not** need to mirror all ~10 call sites in Phase 33 (it is shadow-only, and the authoritative "at least one full sync cycle" guarantee only requires the `sync.py:172-173` hook), but the planner should be aware `compute_risk_scores` itself is called far more often than just at sync time — Phase 34's cutover will need to decide whether the new function also needs that same fan-out, or whether a periodic full recompute (already what `sync.py` does — it's a full-tenant recompute, not incremental) is sufficient. Flagged as an Open Question below, not a Phase 33 blocker.
- **Reconciliation with the new per-finding model:** The new model does not replace or modify `risk_score.py` in Phase 33 — it is entirely additive. The existing `Asset.risk_score` column, its `_normalize_raw_score` curve, and all ~10 call sites are untouched. RISK-02's "asset-level score becomes a rollup of its findings" is satisfied by a **new, separate, shadow** `Asset.risk_exposure_score` column (see "Per-Finding Persistence + Asset Rollup Design"), not by mutating the live one. Phase 34 owns the actual cutover of `Asset.risk_score` reads to the new value.

### Inputs available from Phases 30-32 (all `[VERIFIED: codebase]`)

| Field | Model:Line | Type | Notes |
|-------|-----------|------|-------|
| `sources_count` | `VulnerabilityCorrelation` (`models.py:111`) | `int`, default 1 | Only has a row when 2+ scanners see the same `(cve_id, asset_id)` — `_find_correlated_groups` (`correlation_service.py:141`) filters to `len(v) >= 2`. **A finding with no correlation row is single-source (count=1)**, not "unknown." |
| `confidence` | `VulnerabilityCorrelation` (`models.py:112`) | `str` LOW/MEDIUM/HIGH | D-08 bands: `>=4 sources → HIGH`, `>=2 → MEDIUM`, else `LOW` (structurally near-unreachable given the 2+ filter) — `correlation_service.py:44-52`. Useful as a display label alongside the raw count, not as the scoring input itself (raw count gives finer fixture granularity). |
| `epss_score` / `epss_percentile` | `Vulnerability` (`models.py:57-58`) | `Decimal(5,4)` / `Decimal(5,4)`, nullable | Native 0-1 probability, snapshotted once per finding at ingest via `_lookup_enrichment` (`sync.py:334-349`). `None` when the CVE isn't in the global EPSS table. |
| `cisa_kev` | `Vulnerability` (`models.py:60`) | `bool`, default False | Sole authority is the global `CisaKev` catalog table (`models.py:134-150`) — a connector's own KEV-ish guess never wins (D-04, `sync.py:334-349` docstring). |
| `native_priority_score` / `native_priority_rating` | `Vulnerability` (`models.py:78-79`) | `Decimal(7,2)` / `String(50)`, both nullable | **NOT normalized across sources** (`models.py:75` docstring, verbatim: *"no cross-scale normalization (that's Phase 33)"*) — see per-source table below. |
| `source_signals` | `Vulnerability` (`models.py:86`) | `JSONB`, default `{}` | Curated raw per-connector allowlist. Not directly used in the score formula (too heterogeneous/unstructured across 6 connectors) but available for the DrillPanel breakdown to cite a raw value if useful later. Out of scope for the formula itself. |
| `business_criticality` | `Asset` (`models.py:105-106`) | `String(20)`, default `MEDIUM` | Enum-like: CRITICAL/HIGH/MEDIUM/LOW (Phase 32, `exposure.py` docstring). |
| `data_sensitivity` | `Asset` (`models.py:107-108`) | `String(20)`, default `INTERNAL` | Enum-like: RESTRICTED/CONFIDENTIAL/INTERNAL/PUBLIC. |
| `internet_facing` | `Asset` (`models.py:109-110`) | `bool`, default False | Auto-inferred (external_ip/tag proxy) or per-connector-detected (`internet_facing_detected`). |

### Per-source `native_priority_score` scale reconnaissance `[VERIFIED: codebase, scale documentation ASSUMED where flagged]`

| Source | Field populated? | Documented scale | Verification status |
|--------|-------------------|-------------------|----------------------|
| NESSUS | Yes — VPR (`nessus.py:262-280`) | 0-10 | `[CITED: Tenable VPR docs, per Phase 31 comment]` — but exact JSON field name (`vpr_score`/`vpr`) is itself flagged `[ASSUMED]` in 31-RESEARCH.md (Assumption A1), unverified against a live instance |
| QUALYS | Yes — QDS (`qualys.py:590-605`) | 0-100 | `[CITED: Qualys QDS docs, per Phase 31 comment]` — exact `QDS`/`qds` tag name flagged `[ASSUMED]` in 31-RESEARCH.md (Assumption A3) |
| RAPID7 | Yes — Risk/Active Risk Score (`rapid7.py:309-321`) | 0-1000, asset-context-dependent, theoretically unbounded in practice | `[ASSUMED]` — field name `riskScore` itself flagged unverified in 31-RESEARCH.md (Assumption A2) |
| CROWDSTRIKE | Partial — `native_priority_rating` (ExPRT categorical: UNKNOWN/LOW/MEDIUM/HIGH/CRITICAL) is populated from `exprt_rating` (a real, documented field); `native_priority_score` (`exprt_score`) is a **defensive probe with NO confirmed field name or scale** (`crowdstrike.py:378-391` comment: *"No CONFIRMED numeric ExPRT companion field exists in CrowdStrike's published schema"*) | Rating: categorical, confirmed. Score: unknown/unverified | `[ASSUMED]` for the numeric score only |
| DEFENDER | No — both fields explicitly `None` (`defender.py:318-319`) | N/A | `[VERIFIED: codebase]` |
| WIZ | No — both fields explicitly `None` (`wiz.py:420-421`) | N/A | `[VERIFIED: codebase]` |

**Design implication:** Do not trust `native_priority_score`'s numeric value for CrowdStrike (unverified scale compounds Phase 31's own unverified field-name risk). Use `native_priority_rating` (the categorical, confirmed field) for CrowdStrike's contribution instead. For Nessus/Qualys/Rapid7, normalize the (already Phase-31-flagged-uncertain) numeric score against its documented scale, defensively clamped, soft-nulling to 0 contribution on any parse failure — never crashing, exactly mirroring the connectors' own `try/except (TypeError, ValueError)` soft-null idiom.

### Severity-tier boundary triplication (exact values, confirmed)

| File | Lines | Exact code |
|------|-------|-----------|
| `backend/app/vulnerabilities/dashboard.py` | 125-128 | `func.count().filter(Asset.risk_score >= 80)` / `(Asset.risk_score >= 50) & (< 80)` / `(>= 20) & (< 50)` / `(< 20) \| (is None)` |
| `backend/app/export.py` | 368-371 | Identical four-way split, same literals, same structure |
| `backend/app/assets/router.py` | 297-300 | Identical four-way split, same literals, same structure |
| *(related, out of explicit scope)* `frontend/src/components/ui/RiskRing.tsx` | 22-25 | `getRiskBand()` — same `>=80/>=50/>=20` boundaries client-side |

All three backend occurrences are **behaviorally identical** (same four bands, same boundary values) — safe to centralize into named constants with zero behavior change. Recommend adding to `app/assets/risk_score.py` (already the natural home — it owns `SEVERITY_WEIGHTS` for the very column these boundaries bucket):

```python
# app/assets/risk_score.py — new constants, RISK-06
RISK_SCORE_TIER_CRITICAL = 80
RISK_SCORE_TIER_HIGH = 50
RISK_SCORE_TIER_MEDIUM = 20
```

Then in each of the 3 call sites, replace the literal `80`/`50`/`20` with `RISK_SCORE_TIER_CRITICAL`/`RISK_SCORE_TIER_HIGH`/`RISK_SCORE_TIER_MEDIUM` imported from `app.assets.risk_score`. This is a pure refactor — no test should observe any output change. The frontend `RiskRing.tsx` copy is flagged for the planner to decide whether to include (it wasn't named in the phase's explicit success criteria, which lists only the 3 backend files).

### `Vulnerability` model + relations (`backend/app/vulnerabilities/models.py`)

- `Vulnerability` (line 47) has no existing risk-score column. Unique constraint `uq_vuln_dedup` is `(tenant_id, cve_id, asset_id, source)` (`models.py:49`) — meaning **the same logical CVE-on-asset finding produces one `Vulnerability` ROW PER SCANNER SOURCE** when seen by multiple scanners (e.g., 3 scanners seeing the same CVE on the same host = 3 separate `Vulnerability` rows, unified only by a single shared `VulnerabilityCorrelation` row).
  - **Design implication (important, easy to miss):** the per-finding score is computed **per `Vulnerability` row** (per source-instance), not per logical `(cve_id, asset_id)` pair. All 3 of those rows will receive the *same* corroboration bonus (since `sources_count` is looked up per `(cve_id, asset_id)`, not per row) — this is intentional and matches "cross-scanner corroboration raises the score" literally, but means a finding-list sorted by "most urgent finding" will show 3 near-identical rows for one real issue unless/until a later phase dedupes the by-CVE list view. Flagged as a pitfall below.
- `VulnerabilityCorrelation` (line 97) is keyed on `(tenant_id, cve_id, asset_id)` — exactly the join key needed to look up `sources_count` per finding.

### DrillPanel + existing explainability precedent (frontend)

- `frontend/src/components/vulnerabilities/drill-content.tsx` (824 lines) is the single source of truth for both desktop `drill-panel.tsx` and mobile `drill-panel-mobile.tsx` (mobile renders `DrillContent` directly — one edit covers both, per existing convention comments throughout the file). Section order today: Header (severity/KEV/exploit chips) → CVSS → Affected hosts → Description → AI Explanation → AI Prioritization → Remediation → AI Remediation Guidance → Activity → Actions (`drill-content.tsx:611-735`).
- **Existing per-finding badge precedent** (header, `drill-content.tsx:583-592`): `★ CISA KEV` pink chip and `⚡ exploit available` amber chip, both conditionally rendered. A new "★ KEV floor applied" indicator for the risk breakdown should reuse this exact chip styling.
- **Existing per-asset breakdown-ROW precedent** (not per-finding): `frontend/src/components/assets/risk-card.tsx` — `RiskCard` composes `RiskRing` (the circular 0-100 gauge, `ui/RiskRing.tsx`) + 4 `BreakdownRow` components (label + tinted numeric value, `risk-card.tsx:22-40`). This is the **directly reusable pattern** for the new per-finding breakdown: a list of label/value rows, not the AI-citations inline-tooltip pattern (that's for prose text, not for a fixed list of named score components).
- **Existing per-text-segment citation precedent** (different shape, not reusable here): `frontend/src/components/ai/ai-explanation-citations.tsx` wraps substrings of AI-generated prose in tooltips labeled "Scanner-verbatim" vs "AI-interpreted." This precedent is about attributing *prose provenance*, not about rendering a *fixed breakdown table* — do not force-fit it onto the risk-score breakdown, which is structurally a list of `{label, raw_value, points, max_points}` rows, not flowing text.
- `useVulnerabilityDetail` (`frontend/src/lib/queries/use-vulnerability-detail.ts`) is the query hook backing `DrillContent`; its `VulnerabilityDetail` type will need `risk_exposure_score: number | null`, `risk_exposure_breakdown: RiskBreakdownComponent[] | null`, and `risk_model_version: string | null` added, mirroring the existing flat-field shape (no nesting needed beyond the breakdown array itself).
- `get_vulnerability` (`service.py:172-231`) is the backend function powering the detail endpoint; it already does a live per-request `VulnerabilityCorrelation.sources_count` lookup (`service.py:191-200`) for the (currently separate) `GET /{vuln_id}/correlation` endpoint pattern. For the new score fields, prefer reading the **persisted** `risk_exposure_score`/`risk_exposure_breakdown`/`risk_model_version` columns directly off the `Vulnerability` row (they were computed once at sync time) rather than recomputing live on every GET — cheaper, and consistent with "the score is computed and persisted" (RISK-02) rather than computed-on-read.

## Recommended Deterministic Scoring Formula

**Module:** `backend/app/vulnerabilities/risk_exposure_service.py` (new). Two layers, mirroring `risk_score.py`'s own split:

1. **Pure function** `score_finding(inputs: FindingScoreInputs) -> RiskBreakdown` — zero DB access, fully deterministic, directly fixture-testable (this is what makes RISK-03/RISK-04 "provable with a fixture" trivial: construct two `FindingScoreInputs` differing only in `cisa_kev` or `sources_count`, assert the score differs materially, no DB needed).
2. **DB-orchestration function** `compute_finding_risk_scores(db, tenant_id) -> dict` — bulk-fetches all OPEN/IN_PROGRESS `Vulnerability` rows for the tenant plus their `VulnerabilityCorrelation.sources_count` and joined `Asset` exposure fields, calls `score_finding` per row, and persists the three new columns. Mirrors `compute_risk_scores`'s existing full-tenant-recompute shape (`risk_score.py:84-147`).

### Weighted additive design (100-point budget) `[ASSUMED — weights are a design recommendation, not derived from an external standard; see Assumptions Log A1]`

| Component | Max points | Input | Normalization |
|-----------|-----------|-------|----------------|
| Severity / CVSS | 35 | `cvss_v3_score` (preferred) else `severity` | `cvss_v3_score is not None → (cvss_v3_score / 10) * 35`; else fallback table `{CRITICAL: 35, HIGH: 20, MEDIUM: 8, LOW: 2, INFO: 0}` (proportioned from the existing `SEVERITY_WEIGHTS` ratios in `risk_score.py:44-50`) |
| EPSS (exploit probability) | 20 | `epss_score` | `epss_score is not None → epss_score * 20`; else 0 (native 0-1 scale, `[VERIFIED: codebase Numeric(5,4) column]`, no normalization needed) |
| Native exploitability | 15 | `native_priority_score` / `native_priority_rating`, per-source | See per-source normalization table below; `None` (Defender/Wiz) → 0, never penalized, breakdown shows "not provided by {source}" |
| Exposure context | 20 (10 + 6 + 4 split) | `Asset.business_criticality` / `internet_facing` / `data_sensitivity` | See exposure sub-table below |
| Cross-scanner corroboration | 10 | `VulnerabilityCorrelation.sources_count` (default 1 if no row) | `min((sources_count - 1) / 3, 1.0) * 10` — count=1→0pts, count=2→3.3pts, count=3→6.7pts, count=4+→10pts (full) |
| **Subtotal** | **100** | | Sum of the above, pre-KEV-floor |
| KEV floor (applied last) | — | `cisa_kev` | `final_score = max(subtotal, 90) if cisa_kev else subtotal` |

**Native exploitability per-source normalization** (component of the 15-pt budget above):

```python
def _normalize_native_signal(source: str, score: Decimal | None, rating: str | None) -> float:
    """Returns 0.0-1.0. Never raises — soft-nulls to 0.0 on any parse
    failure or missing signal, mirroring the connectors' own defensive
    probe idiom (nessus.py:262-280, qualys.py:590-605)."""
    if source == "NESSUS" and score is not None:
        return min(max(float(score) / 10.0, 0.0), 1.0)          # VPR 0-10
    if source == "QUALYS" and score is not None:
        return min(max(float(score) / 100.0, 0.0), 1.0)         # QDS 0-100
    if source == "RAPID7" and score is not None:
        return min(max(float(score) / 1000.0, 0.0), 1.0)        # Risk Score 0-1000
    if source == "CROWDSTRIKE" and rating is not None:
        # Categorical (confirmed field) preferred over the unverified numeric
        # exprt_score (crowdstrike.py:378-391 — no confirmed scale exists).
        return {"UNKNOWN": 0.0, "LOW": 0.25, "MEDIUM": 0.5, "HIGH": 0.75, "CRITICAL": 1.0}.get(rating.upper(), 0.0)
    return 0.0  # DEFENDER, WIZ, or missing data — neutral, not penalized
```

**Exposure context sub-split** (component of the 20-pt budget above):

```python
_CRITICALITY_FRACTION = {"CRITICAL": 1.0, "HIGH": 0.67, "MEDIUM": 0.33, "LOW": 0.0}   # ×10 max
_SENSITIVITY_FRACTION = {"RESTRICTED": 1.0, "CONFIDENTIAL": 0.67, "INTERNAL": 0.33, "PUBLIC": 0.0}  # ×4 max
# internet_facing: bool → 1.0/0.0 × 6 max
```

### KEV Floor Mechanics (RISK-03)

`final_score = max(subtotal, KEV_FLOOR_SCORE) if vuln.cisa_kev else subtotal`, with `KEV_FLOOR_SCORE = 90` `[ASSUMED — see Assumptions Log A2; the phase language "near-automatic escalation/floor per BOD-26-04 guidance" mirrors the real CISA BOD 22-01 KEV-remediation-mandate spirit, but no external source dictates a numeric floor value — this is a project design choice]`.

**Fixture (directly satisfies "low-severity KEV scores materially higher than identical non-KEV")**:
```python
low_no_kev = FindingScoreInputs(severity="LOW", cvss_v3_score=Decimal("3.1"), epss_score=None,
                                  cisa_kev=False, source="DEFENDER", native_priority_score=None,
                                  native_priority_rating=None, sources_count=1,
                                  business_criticality="MEDIUM", data_sensitivity="INTERNAL", internet_facing=False)
low_with_kev = replace(low_no_kev, cisa_kev=True)

assert score_finding(low_no_kev).final_score < 15       # LOW severity, nothing else contributing
assert score_finding(low_with_kev).final_score == 90    # floor applied, materially higher
```

### Corroboration Mechanics (RISK-04)

**Fixture (directly satisfies "identical finding seen by 1 vs 3 scanners")**:
```python
base = FindingScoreInputs(severity="HIGH", cvss_v3_score=Decimal("7.5"), epss_score=Decimal("0.1"),
                            cisa_kev=False, source="QUALYS", native_priority_score=Decimal("60"),
                            native_priority_rating=None, sources_count=1,
                            business_criticality="MEDIUM", data_sensitivity="INTERNAL", internet_facing=False)
one_source = base
three_sources = replace(base, sources_count=3)

assert score_finding(three_sources).final_score > score_finding(one_source).final_score
assert score_finding(three_sources).final_score - score_finding(one_source).final_score == pytest.approx(6.7, abs=0.1)
```

## Per-Finding Persistence + Asset Rollup Design (RISK-02)

**New `Vulnerability` columns** (all nullable, additive migration, zero data migration in Phase 33):
```python
risk_exposure_score: Mapped[int | None] = mapped_column(Integer)
risk_exposure_breakdown: Mapped[dict | None] = mapped_column(JSONB)  # RiskBreakdown serialized
risk_model_version: Mapped[str | None] = mapped_column(String(20))
```

**New `Asset` columns** (shadow rollup — separate from the live `risk_score`):
```python
risk_exposure_score: Mapped[int | None] = mapped_column(Integer)  # shadow, NOT the live risk_score
risk_model_version: Mapped[str | None] = mapped_column(String(20))
```

**Rollup strategy** `[ASSUMED — Claude's Discretion; no CONTEXT.md locks this]`: `Asset.risk_exposure_score = MAX(risk_exposure_score across that asset's OPEN/IN_PROGRESS findings)`, i.e., "the asset is as urgent as its single worst open finding" — directly aligned with RISK-02's own framing ("finding list can sort by 'most urgent finding'"). This is simpler and more explainable than re-deriving a volume-sensitive curve (like the existing `_normalize_raw_score` power/log curve) for the shadow rollup; Phase 34 can revisit if a MAX-only rollup proves too spiky in practice (e.g., one dormant LOW-severity KEV finding pinning an otherwise-clean asset's score high forever) — flagged as an Open Question below.

**Migration:** New Alembic revision `042_add_risk_exposure_score` (27 chars, within the ≤32-char constraint), `down_revision = "041_add_inet_facing_signal"`. Purely additive (5 nullable columns, no backfill, no data migration — historical backfill is explicitly Phase 34/RISK-07 scope).

## Shadow-Compute + Versioning Contract (RISK-06)

- `RISK_MODEL_VERSION = "v1"` — a module-level constant in `risk_exposure_service.py`, stamped onto every row `compute_finding_risk_scores` touches. Bump this string whenever the weight table or formula changes; Phase 34's cutover and any future recompute can filter `WHERE risk_model_version = 'v1'` to distinguish "scored under the target version" from "stale or never scored" (`NULL`).
- **Trigger point:** call `compute_finding_risk_scores(db, tenant_id)` immediately after `compute_risk_scores(db, tenant_id)` at `connectors/sync.py:172-173` (same transaction, same post-sync block). Because this function recomputes the FULL open-finding set every call (mirroring `compute_risk_scores`'s own full-tenant-recompute behavior, not an incremental diff), the very first sync after this phase ships already covers every currently-open finding — satisfying "shadow-computed for at least one full sync cycle" without needing Phase 34's dedicated historical-backfill machinery in this phase.
- **Zero-consumer guarantee:** grep-provable — no existing query, sort, filter, alert, trend, or AI-batch-selector logic references `risk_exposure_score`, `risk_exposure_breakdown`, or the new `Asset.risk_exposure_score` column anywhere outside the new service module and the new DrillPanel display. The **only** intentional exception is the DrillPanel's read-only breakdown display (RISK-05) — a human looking at one finding at a time is not the same category of "consumer" as an automated system (SLA breach detection, list default-sort, trend charts, `min_risk_score` automation-rule conditions, the AI batch selector) making a decision from the score. This distinction is `[ASSUMED]` — flagged in the Assumptions Log for explicit confirmation, since RISK-05 and RISK-06 are in tension if read literally ("show it to analysts" vs. "zero consumers") and this research resolves that tension by treating "consumer" as "automated decision-making system," not "any code path that reads the column."

## Severity-Tier Centralization

Covered above under "Existing-Code Reconnaissance" — three named constants in `app/assets/risk_score.py`, imported by `dashboard.py`, `export.py`, `assets/router.py`. Pure refactor, zero behavior change, independently verifiable via existing tests on those three files (if any cover the risk-distribution endpoints — confirm during planning; none were found named for this specific behavior in `backend/tests/`).

## DrillPanel Breakdown Approach (RISK-05)

1. **Backend:** extend `VulnerabilityResponse` (`schemas.py:15-52`) with `risk_exposure_score: int | None`, `risk_exposure_breakdown: list[RiskBreakdownComponent] | None`, `risk_model_version: str | None`. `get_vulnerability` (`service.py:172-231`) reads these directly off the already-fetched `vuln` ORM object (no new query — the columns are already selected as part of `select(Vulnerability)`).
2. **`RiskBreakdownComponent` schema** (new, `schemas.py`):
   ```python
   class RiskBreakdownComponent(BaseModel):
       key: str            # "severity_cvss" | "epss" | "native_exploitability" | "exposure_business_criticality" | "exposure_internet_facing" | "exposure_data_sensitivity" | "corroboration"
       label: str           # human-facing, e.g. "EPSS (exploit probability)"
       raw_value: str        # e.g. "0.42" or "3 scanners (HIGH confidence)" or "not provided by DEFENDER"
       points: float
       max_points: float
   ```
3. **Frontend:** new section in `drill-content.tsx`, placed directly after the existing CVSS section (`drill-content.tsx:611-622`) and before "Affected hosts" — the analyst reads the raw CVSS number, then immediately sees "why this scored an 82" building on it. Render as a list of rows reusing `RiskCard`'s existing `BreakdownRow` shape (label left, tinted numeric value right, `risk-card.tsx:22-40`) rather than the AI-citations tooltip pattern (wrong shape for a fixed component list). Show the overall `risk_exposure_score` as a small badge or reuse `RiskRing` at a smaller size next to the section heading; render "★ KEV floor applied" using the exact same pink-chip styling as the existing "★ CISA KEV" chip (`drill-content.tsx:583-586`) when `risk_model_version` is present and the floor was applied (i.e., `cisa_kev && subtotal < 90`).
4. **Labeling as shadow/preview:** since RISK-06 explicitly gates automated consumption but RISK-05 explicitly wants analyst visibility, recommend a small "Preview — not yet used for sorting or alerts" caption near the new section (copy-voice-compliant, no "Coming soon!" boilerplate) so analysts don't mistake the shadow score for something that already drives triage elsewhere. This is a `[ASSUMED]` UX recommendation, not a locked requirement — flag for discuss-phase/planner confirmation.
5. **Test coverage precedent:** mirror `drill-panel.test.tsx`/`drill-content` test conventions already in the repo (inline mock shape, `FlexibleDetail` type already tolerates extra fields per its own comment at `drill-content.tsx:46-49`).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 0-100 score normalization/curve math | A new bespoke curve-fitting function | The existing additive weighted-points design (sums to exactly 100, no curve-fitting needed since it's per-finding not a volume aggregate) | `risk_score.py`'s power/log curve exists specifically to tame *volume* of vulns on one asset — a single finding has no volume dimension, so a simple weighted sum is the right tool, not a reused curve |
| Cross-scanner corroboration lookup | A new join/aggregation query duplicating `_find_correlated_groups` | `VulnerabilityCorrelation.sources_count`, already computed and upserted by Phase 30's `run_correlations` on every sync, immediately before this function's hook point | Correlation data is guaranteed fresh at the exact moment `compute_finding_risk_scores` runs (same post-sync block, right after `run_correlations`) |
| KEV authority | Re-deriving KEV status from `source_signals` or a connector's own guess | `Vulnerability.cisa_kev`, already the sole-authority column (D-04, `sync.py:334-349`) | Re-deriving KEV from raw connector signals would silently diverge from the codebase's own established single source of truth |
| Severity-tier boundaries | A 4th copy of `>=80/>=50/>=20` | The new centralized constants in `risk_score.py` | Literally what RISK-06 asks for |

**Key insight:** every input this phase needs already exists, correctly computed and persisted, from Phases 30-32. Phase 33's actual work is entirely in the *combination* function (weights + normalization + KEV floor) and the *persistence/versioning* scaffolding — not in sourcing new data.

## Common Pitfalls

### Pitfall 1: Confusing "per-finding" with "per logical issue"
**What goes wrong:** A single CVE-on-asset issue seen by 3 scanners produces 3 separate `Vulnerability` rows (`uq_vuln_dedup` includes `source`). All 3 will receive the identical corroboration bonus and near-identical scores. A naive "sort by most urgent finding" implementation (Phase 34 scope) could show the same logical issue 3 times near the top of a list.
**Why it happens:** The corroboration signal is deliberately keyed on `(cve_id, asset_id)`, one level above the per-row grain the score itself is computed at.
**How to avoid:** Document this explicitly in the formula module's docstring (as this research does); leave de-duplication of the finding LIST view as an explicit Phase 34 decision, not something Phase 33 should silently attempt.
**Warning signs:** A test asserting "top N findings by risk_exposure_score are all distinct issues" would fail without an explicit dedup step — don't write that assertion in Phase 33.

### Pitfall 2: Trusting `native_priority_score`'s numeric scale for CrowdStrike
**What goes wrong:** CrowdStrike's `exprt_score` has no confirmed field name OR scale (`crowdstrike.py:378-391`). Naively dividing by an assumed max (e.g., /100) could silently produce a wildly wrong normalized fraction.
**Why it happens:** Phase 31 flagged this as an unverified probe, not a confirmed API contract.
**How to avoid:** Use `native_priority_rating` (the confirmed categorical field) for CrowdStrike's contribution instead of the numeric score.
**Warning signs:** If a future live-connector verification confirms `exprt_score`'s real scale, this normalization table should be revisited — flagged in the Assumptions Log.

### Pitfall 3: Treating the KEV floor as a bonus instead of a floor
**What goes wrong:** Implementing `final = subtotal + KEV_BONUS` (additive) instead of `final = max(subtotal, KEV_FLOOR)` would let a finding that's ALREADY above the floor (e.g., a CRITICAL KEV finding scoring 95 on subtotal alone) get pushed above 100, requiring an extra clamp, and would not match the "floor" language in the requirement.
**Why it happens:** Additive bonuses are the more common pattern elsewhere in this codebase (`risk_score.py`'s exploit/KEV multipliers are multiplicative on the raw sum, not a floor).
**How to avoid:** Use `max()`, not `+`. This also makes the floor's fixture trivially provable (a LOW-severity KEV finding must land at EXACTLY the floor value, not some larger derived number).

### Pitfall 4: Recomputing the breakdown live on every GET instead of persisting it
**What goes wrong:** If `get_vulnerability` recomputes `score_finding` on every detail-page load (mirroring the existing live `sources_count` lookup pattern at `service.py:191-200`), the DrillPanel would show a score that could differ from what a bulk consumer (Phase 34) later reads from the persisted column, if inputs changed between sync and read — defeating "shadow-computed and persisted."
**Why it happens:** The live-lookup pattern is the closest existing precedent in this exact function, making it tempting to copy verbatim.
**How to avoid:** Read the persisted `risk_exposure_score`/`risk_exposure_breakdown`/`risk_model_version` columns directly off the `Vulnerability` row already being fetched — zero extra queries, and guarantees the DrillPanel always shows exactly what was shadow-computed at the last sync.

### Pitfall 5: Forgetting that EPSS/CVSS/native score can all be simultaneously `None`
**What goes wrong:** A finding with no CVE (`cve_id IS NULL`, allowed per the nullable column) has no EPSS, likely no CVSS either (vendor-specific misconfig-style findings sometimes lack CVSS), and may come from Defender/Wiz (no native score). If every optional input defensively contributes 0, the formula still produces a valid, low, honest score — but a naive implementation using division-by-input-count for "average available signal" would produce a misleadingly HIGH score from a tiny sample. The additive weighted-points design (fixed max-points per component, missing = 0, not renormalized) avoids this trap.
**Why it happens:** "Only average the signals we have" is an intuitive-but-wrong pattern when signals are sparse and non-uniformly available across the 6 connectors.
**How to avoid:** Never renormalize weights based on which inputs are present — a missing signal contributes exactly 0 points out of its budget, nothing more, nothing less. This is already the design above; call it out explicitly during implementation review.

## Code Examples

### Existing per-asset pure/impure split to mirror (`risk_score.py:67-147`)
```python
# Source: backend/app/assets/risk_score.py:67-81 (pure, DB-free)
def _normalize_raw_score(raw: float) -> int:
    if raw <= 0:
        return 0
    if raw <= KNEE_RAW:
        score = KNEE_SCORE * (raw / KNEE_RAW) ** 0.7
    else:
        score = KNEE_SCORE + (100.0 - KNEE_SCORE) * (math.log1p(raw - KNEE_RAW) / math.log1p(MAX_RAW - KNEE_RAW))
    return min(int(round(score)), 100)
```

### Existing correlation lookup precedent to reuse verbatim for bulk fetch (`correlation_service.py:170-193`)
```python
# Source: backend/app/vulnerabilities/correlation_service.py:170-193
async def get_correlation_for_vuln(db, tenant_id, cve_id, asset_id):
    result = await db.execute(
        select(VulnerabilityCorrelation).where(
            VulnerabilityCorrelation.tenant_id == tenant_id,
            VulnerabilityCorrelation.cve_id == cve_id,
            VulnerabilityCorrelation.asset_id == asset_id,
        )
    )
    # ... (compute_finding_risk_scores should bulk-fetch ALL correlations for
    # the tenant ONCE into a dict keyed by (cve_id, asset_id), not call this
    # per-row — mirrors compute_risk_scores's own single bulk subquery shape,
    # avoiding an N+1 query pattern across potentially thousands of findings.)
```

### Existing sync-time hook point to extend (`sync.py:171-173`)
```python
# Source: backend/app/connectors/sync.py:171-173
corr_stats = await run_correlations(db, connector_config.tenant_id)
risk_stats = await compute_risk_scores(db, connector_config.tenant_id)
# NEW (Phase 33): add immediately after, same transaction —
# finding_risk_stats = await compute_finding_risk_scores(db, connector_config.tenant_id)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Only a per-asset aggregate risk score exists (`risk_score.py`) | Per-finding score + asset rollup, shadow-computed | This phase (Phase 33) | Enables "sort by most urgent finding" (Phase 34 cutover) instead of only "sort by asset" |
| `native_priority_score` stored verbatim, no cross-scale meaning | Per-source normalization table maps every connector's native signal to a common 0-1 fraction | This phase | Makes vendor-native exploitability signals usable in a cross-vendor formula for the first time |
| Severity-tier boundaries hardcoded 3x (`dashboard.py`/`export.py`/`assets/router.py`) | Centralized constants in `risk_score.py` | This phase | Future boundary changes (if ever) require editing one file, not three |

**Deprecated/outdated:** None — this phase is purely additive; nothing existing is removed or deprecated.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The 100-point weight split (35/20/15/20/10 across severity, EPSS, native-exploitability, exposure, corroboration) is a reasonable starting allocation | "Recommended Deterministic Scoring Formula" | If tenants disagree with the relative emphasis (e.g., want EPSS weighted higher than severity), the formula produces defensible-but-contestable scores; low risk since it's a versioned, tunable constant table, not baked into schema — easy to adjust and re-shadow-compute before Phase 34 cutover |
| A2 | `KEV_FLOOR_SCORE = 90` is an appropriate near-automatic-escalation floor value | "KEV Floor Mechanics" | If 90 is too aggressive (floors too many findings to near-critical) or too weak (doesn't feel like a real "floor" against a 95+ subtotal), the fixture and cutover behavior both need revisiting; low risk to fix (single constant) |
| A3 | "Consumer" in RISK-06's "zero consumers reading it" means an automated decision-making system, not any code path that reads the column — the DrillPanel's read-only display (RISK-05) is exempt | "Shadow-Compute + Versioning Contract" | If the intended meaning is stricter (literally zero reads anywhere, including UI), RISK-05 and RISK-06 as written are mutually exclusive within Phase 33 and the DrillPanel work would need to be deferred to Phase 34's cutover instead — moderate risk, worth explicit confirmation before planning locks task order |
| A4 | `Asset.risk_exposure_score` rollup = `MAX` of open findings' scores (not a weighted/volume-sensitive curve) | "Per-Finding Persistence + Asset Rollup Design" | If a MAX-only rollup proves too spiky in practice (one old KEV finding pins an asset's shadow score permanently high even as everything else on it is remediated), Phase 34 would need a different rollup formula — low risk since it's shadow-only in Phase 33, easily revised before cutover |
| A5 | CrowdStrike's `native_priority_score` (`exprt_score`) numeric scale is untrustworthy enough to skip entirely in favor of `native_priority_rating` | "Native exploitability per-source normalization" | If a live Falcon instance confirms `exprt_score`'s real scale (currently unverified per 31-RESEARCH.md), the formula could use the finer-grained numeric signal instead of the 5-bucket categorical rating — low risk, purely an upgrade opportunity, not a correctness bug either way |
| A6 | "BOD-26-04" (phase goal language) is treated as this project's own internal shorthand for "near-automatic KEV escalation," modeled after the real-world CISA BOD 22-01 remediation mandate, not a literal external directive this research verified | "KEV Floor Mechanics" | If a real, specific external directive named "BOD-26-04" exists with prescriptive numeric requirements, the KEV floor value (and possibly the whole escalation mechanism) may need to match it exactly — worth a targeted web search before finalizing if the user has a specific compliance citation in mind |

**If this table is empty:** N/A — six assumptions requiring confirmation, none of which block starting the plan (all are tunable constants or a scope-boundary interpretation, not structural blockers).

## Open Questions

1. **Should `compute_finding_risk_scores` also be called from the ~9 other `compute_risk_scores` call sites** (status update, bulk update, snooze, ticket-triggered recompute — `vulnerabilities/router.py` lines 508/523, 544/557, 576/609, 745/770, 804/818; `ticketing/router.py:463`), or is the single `sync.py:172-173` hook sufficient for "at least one full sync cycle"?
   - What we know: `sync.py`'s call is a FULL tenant recompute (covers every open finding, not incremental), so it alone satisfies the literal "one full sync cycle" requirement.
   - What's unclear: whether an analyst updating a finding's status mid-cycle (before the next sync) should see an immediately-fresh shadow score, or whether staleness-until-next-sync is acceptable for a shadow-only feature.
   - Recommendation: Phase 33 only needs the `sync.py` hook (staleness is fine for a not-yet-consumed shadow value); defer the other call sites to Phase 34 if/when the score becomes consumer-facing and staleness starts to matter.

2. **Should the `Asset.risk_exposure_score` rollup use MAX or a volume-sensitive curve** (mirroring the existing `_normalize_raw_score` curve)?
   - What we know: MAX is simpler, more explainable, and directly matches the "most urgent finding" framing.
   - What's unclear: whether tenants expect an asset with 20 HIGH findings to score higher than an asset with 1 identical HIGH finding (a MAX rollup treats them identically).
   - Recommendation: Ship MAX in Phase 33 (shadow, low stakes); Phase 34 can A/B or reconsider before cutover since nothing consumes it yet.

3. **Does a real, specific "BOD-26-04" directive exist with prescriptive requirements** beyond "treat KEV as near-automatic"?
   - What we know: The real, verifiable CISA directive on KEV remediation is BOD 22-01 (binding for federal agencies, establishes required remediation timelines for cataloged KEV entries).
   - What's unclear: whether "BOD-26-04" is this project's own future-dated internal alias/shorthand or references something the user has specific external knowledge of.
   - Recommendation: Treat as internal shorthand per Assumption A6 unless the user corrects this during planning.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Backend framework | pytest 9.0.3 (`asyncio_mode = "auto"`, session-scoped event loop) — `backend/pyproject.toml` `[tool.pytest.ini_options]` |
| Backend config file | `backend/pyproject.toml` |
| Frontend framework | vitest ^4.1.6 — `frontend/package.json` |
| Frontend config file | `frontend/vitest.config.ts` (existing, unconfirmed exact path this session — same one every other `*.test.tsx` in the repo already uses) |
| Quick run command (backend) | `cd backend && ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") JWT_SECRET_KEY=test-secret .venv/bin/pytest tests/test_risk_exposure_service.py -x` |
| Quick run command (frontend) | `cd frontend && npx vitest run src/components/vulnerabilities/drill-content.test.tsx` |
| Full suite command (backend) | `cd backend && ENCRYPTION_KEY=... JWT_SECRET_KEY=... .venv/bin/pytest tests/ ` — per project memory, run **per-file** during development, full-dir only as a final gate |
| Full suite command (frontend) | `cd frontend && npm test` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RISK-01 | `score_finding` combines all 6 input categories deterministically | unit | `pytest tests/test_risk_exposure_service.py::test_score_finding_all_components -x` | ❌ Wave 0 |
| RISK-01 | Native-exploitability per-source normalization (Nessus/Qualys/Rapid7/CrowdStrike/Defender/Wiz) | unit | `pytest tests/test_risk_exposure_service.py::test_normalize_native_signal_per_source -x` | ❌ Wave 0 |
| RISK-02 | `compute_finding_risk_scores` persists `risk_exposure_score` on every open `Vulnerability` row | integration | `pytest tests/test_risk_exposure_service.py::test_compute_finding_risk_scores_persists -x` | ❌ Wave 0 |
| RISK-02 | `Asset.risk_exposure_score` rollup = MAX of open findings' scores | integration | `pytest tests/test_risk_exposure_service.py::test_asset_rollup_is_max -x` | ❌ Wave 0 |
| RISK-03 | KEV floor: identical LOW-severity finding scores materially higher with `cisa_kev=True` | unit (fixture) | `pytest tests/test_risk_exposure_service.py::test_kev_floor_fixture -x` | ❌ Wave 0 |
| RISK-04 | Corroboration: identical finding at `sources_count=1` vs `sources_count=3` scores materially higher | unit (fixture) | `pytest tests/test_risk_exposure_service.py::test_corroboration_fixture -x` | ❌ Wave 0 |
| RISK-05 | `GET /vulnerabilities/{id}` response includes `risk_exposure_score`/`risk_exposure_breakdown`/`risk_model_version` | integration | `pytest tests/test_vulnerability_router.py::test_get_vuln_includes_risk_breakdown -x` (or new file if none covers this endpoint yet) | ⚠️ confirm during planning |
| RISK-05 | DrillPanel renders the "Risk Exposure" breakdown section from a mocked detail response | unit (RTL) | `npx vitest run src/components/vulnerabilities/drill-content.test.tsx -t "risk exposure"` | ❌ Wave 0 (new test cases in existing file) |
| RISK-06 | `risk_model_version` is stamped on every scored row; zero existing consumer references the new columns (grep-provable, not a runtime test) | static check + unit | `grep -rn "risk_exposure_score\|risk_exposure_breakdown" backend/app --include="*.py" \| grep -v risk_exposure_service.py` (manual/CI grep gate, not pytest) | N/A — process check |
| RISK-06 | Severity-tier centralization: `dashboard.py`/`export.py`/`assets/router.py` risk-distribution endpoints produce identical output before/after the refactor | regression | `pytest tests/test_dashboard_tiles.py -x` (existing file — confirm it covers the risk-distribution buckets; extend if not) | ⚠️ confirm during planning |

### Sampling Rate
- **Per task commit:** run the specific new/modified test file(s) only (per-file, per backend_test_env constraint — never the whole `tests/` directory during iteration).
- **Per wave merge:** full backend suite (`pytest tests/`) + full frontend suite (`npm test`).
- **Phase gate:** both full suites green, plus the grep-provable zero-consumer check for RISK-06, before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `backend/tests/test_risk_exposure_service.py` — new file, covers RISK-01/03/04 (pure `score_finding` fixtures) + RISK-02 (DB-orchestration `compute_finding_risk_scores`). No existing test file covers `risk_score.py` either (confirmed via grep — zero hits), so this is a genuinely new test surface, not an extension.
- [ ] Confirm whether `backend/tests/test_dashboard_tiles.py` (or another existing file) already exercises the risk-distribution bucket endpoints in `dashboard.py`/`export.py`/`assets/router.py` — if not, add regression coverage alongside the centralization refactor (RISK-06) so the "zero behavior change" claim is test-backed, not just asserted.
- [ ] Extend `drill-content.test.tsx` (existing file) with new cases for the "Risk Exposure" section — no new test framework needed, same RTL/vitest conventions already in use.
- [ ] Confirm no existing integration test covers `GET /vulnerabilities/{id}`'s full response shape — if one exists, extend it for the 3 new fields rather than creating a duplicate.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Unchanged — existing session/OIDC auth untouched by this phase |
| V3 Session Management | No | Unchanged |
| V4 Access Control | Yes | All new queries filter on `tenant_id` exactly like every existing query in `risk_score.py`/`correlation_service.py`/`service.py` — no new endpoint is added in Phase 33 (fields are additive on the existing `GET /{vuln_id}` response, already `require_viewer`-gated per `router.py:371-381`) |
| V5 Input Validation | No new surface | No new user-controlled input in this phase — the score is server-computed from already-validated stored data; no new query params |
| V6 Cryptography | No | Not applicable — no secrets, no crypto operations introduced |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Cross-tenant data leakage in the new bulk-fetch queries (correlation/asset joins) | Information Disclosure | Every new query in `compute_finding_risk_scores` must filter `tenant_id == tenant_id` exactly like `_find_correlated_groups` (`correlation_service.py:118`) and `compute_risk_scores` (`risk_score.py:117-118`) already do — no new pattern needed, just consistent application of the existing one |
| JSONB breakdown column used as an unbounded/untrusted write target | Tampering | `risk_exposure_breakdown` is server-computed only (never accepts user input) — no sanitization concern, but bound the component list to a fixed, code-defined set of keys (never dynamically constructed from `source_signals` or other less-trusted JSONB) |

## Sources

### Primary (HIGH confidence)
- Direct codebase reads (file:line cited throughout): `backend/app/assets/risk_score.py`, `backend/app/vulnerabilities/models.py`, `backend/app/vulnerabilities/correlation_service.py`, `backend/app/vulnerabilities/service.py`, `backend/app/vulnerabilities/schemas.py`, `backend/app/connectors/sync.py`, `backend/app/connectors/{nessus,qualys,rapid7,crowdstrike,defender,wiz}.py`, `backend/app/assets/models.py`, `backend/app/assets/exposure.py`, `backend/app/export.py`, `backend/app/assets/router.py`, `backend/app/vulnerabilities/dashboard.py`, `backend/alembic/versions/` (naming/sequencing convention), `backend/tests/conftest.py` (fixture shapes), `backend/pyproject.toml` (pytest config)
- `frontend/src/components/vulnerabilities/drill-content.tsx`, `drill-panel.tsx`, `frontend/src/components/assets/risk-card.tsx`, `frontend/src/components/ui/RiskRing.tsx`, `frontend/src/components/ai/ai-explanation-citations.tsx`, `frontend/src/lib/queries/use-vulnerability-detail.ts`, `frontend/package.json`

### Secondary (MEDIUM confidence)
- `.planning/REQUIREMENTS.md` (RISK-01..09 exact text), `.planning/ROADMAP.md` (Phase 33/34 goal + success-criteria language, dependency ordering)
- `.planning/phases/32-asset-exposure-context/32-RESEARCH.md` (structural/style precedent for this document)
- Prior phase RESEARCH docs' own flagged assumptions (Nessus VPR field name, Rapid7 riskScore field name, CrowdStrike exprt_score field/scale) — inherited, not re-verified this session, since Phase 33's formula only needs to be defensive against those being wrong, not resolve them itself

### Tertiary (LOW confidence)
- Training-data knowledge of CISA BOD 22-01 (the real-world KEV remediation directive) used only to contextualize the phase's "BOD-26-04" language as likely internal project shorthand — not independently verified this session via web search (flagged as Open Question 3 / Assumption A6 for the user to confirm if a specific external citation is intended)

## Metadata

**Confidence breakdown:**
- Existing-code reconnaissance: HIGH — every claim is a direct file:line read this session
- Scoring formula design: MEDIUM — the mechanism (additive weighted points, KEV floor via max(), corroboration via capped fraction) is sound and testable; the specific weight numbers are an explicit, flagged judgment call (Assumption A1)
- Native-signal normalization: MEDIUM — built on top of Phase 31's own already-flagged unverified field names/scales; defensive design (soft-null on failure) contains the blast radius of any single wrong assumption
- Shadow-compute/versioning contract: HIGH — directly mirrors an existing, working precedent (`compute_risk_scores`'s full-tenant-recompute shape) with no novel mechanism invented
- Validation architecture: MEDIUM — test framework and commands are HIGH confidence (read directly); the exact set of files/tests needed is a recommendation for the planner to confirm against actual existing coverage, not an exhaustive audit of every test file in the repo

**Research date:** 2026-08-11
**Valid until:** 30 days (stable backend domain; no fast-moving external dependency)
