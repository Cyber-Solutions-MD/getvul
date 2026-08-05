# Roadmap: GetVul

## Overview

GetVul is a unified vulnerability management platform. Prior milestones (v1.0 Production Readiness, v2.0 UI/UX Redesign, v2.1 Polish, v2.2 Deferred UI Features, v3.0 AI-Assisted Triage) are fully shipped and archived — see [MILESTONES.md](MILESTONES.md) for the full log and `.planning/milestones/` for per-milestone detail.

**Current milestone: v4.0 — Enriched Risk Exposure & Source-Aware Triage.** Two verified defects sit directly in the path of this milestone's headline features and must be fixed first, not bolted on: `vulnerability_correlations` only has FK columns for 4 of the 6 live scanners (Qualys/Rapid7 correlation data is silently dropped today), and all six connectors already flatten every vendor-native risk signal down to two lossy booleans at ingestion, with the `epss_score` column populated by none of them. The milestone captures the richer signals each scanner actually provides (Phase 31), gives assets real exposure context (Phase 32), rebuilds the deterministic risk-exposure model around those inputs — deliberately split into *define* (Phase 33, shadow-computed) and *recompute + cut over* (Phase 34, the highest-risk phase) so a miscalibrated formula can never reach every tenant with no safety net — and makes scanner provenance a first-class, per-entity-designed, filterable/badged dimension across Vulnerabilities, Assets, CSPM, and Tickets (Phase 35). Continues phase numbering from Phase 29 (last shipped phase, v3.0).

## Milestones

- ✅ **v1.0 Production Readiness** — Phases 1–8 (SHIPPED 2026-07-14)
- ✅ **v2.0 UI/UX Redesign** — Phases 9–15 (SHIPPED 2026-06-30) — archived: [milestones/v2.0-ROADMAP.md](milestones/v2.0-ROADMAP.md)
- ✅ **v2.1 Polish & Tech Debt** — BL-01..05 (SHIPPED 2026-07-15; no new phases)
- ✅ **v2.2 Deferred UI Features** — Phases 16–22 (SHIPPED 2026-07-22) — archived: [milestones/v2.2-ROADMAP.md](milestones/v2.2-ROADMAP.md)
- ✅ **v3.0 AI-Assisted Triage ("Triage Copilot")** — Phases 23–29 (SHIPPED 2026-08-04) — archived: [milestones/v3.0-ROADMAP.md](milestones/v3.0-ROADMAP.md)
- 🚧 **v4.0 Enriched Risk Exposure & Source-Aware Triage** — Phases 30–35 (IN PROGRESS, started 2026-08-04)

## Phases

**Phase Numbering:**

- Integer phases (30, 31, 32...): Planned milestone work
- Decimal phases (30.1, 30.2): Urgent insertions (marked with INSERTED)

**v4.0 Enriched Risk Exposure & Source-Aware Triage (IN PROGRESS — Phases 30–35):**

- [x] **Phase 30: Correlation Schema Fix** — Replace the hardcoded 4-of-6-source correlation FK columns with a `sources ARRAY(String)` + GIN shape, migrate existing data with no loss, generalize `correlation_service.py` over the full `VulnSource` enum (completed 2026-08-05)
- [ ] **Phase 31: Connector Enrichment Rewrite** — All 6 connectors thread native signals (VPR, ExPRT.AI, EPSS, real KEV) from the raw payload through ingestion; new global EPSS/KEV reference tables refreshed by a daily scheduler job
- [ ] **Phase 32: Asset Exposure Context** — Auto-infer criticality/data-sensitivity/internet-facing at asset upsert; per-asset and asset-group admin override with audit trail and criticality-inflation calibration bound
- [ ] **Phase 33: Risk-Exposure Model Definition** — Deterministic, versioned, explainable per-finding risk-exposure score; shadow-computed for a full sync cycle before any consumer reads it
- [ ] **Phase 34: Historical Recompute & Consumer Cutover** — Idempotent/resumable/throttled per-tenant backfill; SLA/sort/trend/AI-batch-selector cutover; per-tenant threshold re-tuning acknowledgment; version-boundary guards on alerts/trends
- [ ] **Phase 35: Source-Aware Filtering & Provenance Badges** — Per-entity OR/AND scanner-source filtering (Vulnerabilities, Assets, CSPM, Tickets) and a `SourceBadgeGroup` provenance component, batched queries

## Phase Details

### Phase 30: Correlation Schema Fix

**Goal**: Cross-source correlation records the true, complete set of scanners that see each CVE-on-host — no silent data loss, no hardcoded source limit — so every downstream v4.0 feature that reads "which sources see this finding" has a correct foundation.
**Depends on**: Nothing (first phase of the v4.0 milestone)
**Requirements**: CORR-01, CORR-02, CORR-03
**Success Criteria** (what must be TRUE):

  1. `vulnerability_correlations` stores its source set as a `sources ARRAY(String)` column with a GIN index (mirroring the shipped `assets.tags` pattern), replacing the 4 hardcoded FK columns, and covers all 6 `VulnSource` values forward-compatibly with a 7th
  2. Existing correlation data — including Qualys/Rapid7 records that are silently dropped today — is migrated into the new shape with zero loss, verified per-tenant
  3. `correlation_service.py` loops over the full `VulnSource` enum instead of a hardcoded `SOURCE_COLUMN_MAP`, so `sources_count` and the resolved source-name list can never disagree
  4. A regression test seeds a finding seen only by Qualys + Rapid7 and confirms it now correlates correctly (this case was silently dropped pre-fix)

**Plans**: 2 plans (2/2 complete)

- [x] 30-01-PLAN.md — Generalized source-set: model + migration (034) + correlation_service rewrite; SC#4 tracer (CORR-01, CORR-03) *(complete 2026-08-04 — SC#4 GREEN: Qualys+Rapid7 now correlates)*
- [x] 30-02-PLAN.md — Re-correlation script (testable `_recorrelate_tenant` helper) + runtime per-tenant zero-loss recovery test + banding/invariant/tenant-scope + D-09 HTTP-shape tests (CORR-01, CORR-02, CORR-03) *(complete 2026-08-05 — 10/10 tests green, runtime zero-loss proof)*

### Phase 31: Connector Enrichment Rewrite

**Goal**: Every connector captures and persists the richer native signal each scanner actually provides, so v4.0's enrichment claims are real data, not permanently-null columns.
**Depends on**: Nothing (independent of Phase 30; both must land before Phase 33)
**Requirements**: ENRICH-01, ENRICH-02, ENRICH-03, ENRICH-04, ENRICH-05, ENRICH-06
**Success Criteria** (what must be TRUE):

  1. EPSS score + percentile is populated on newly-ingested findings for every one of the 6 connectors (today's `epss_score` column is populated by none)
  2. CISA KEV status is populated per finding from a real authoritative feed for every connector, including Defender (whose `cisa_kev=False` hardcode is fixed)
  3. Vendor-native exploitability/priority signals (Nessus VPR, CrowdStrike ExPRT.AI rating + score, and each other scanner's equivalent) land in promoted typed columns that can be sorted/filtered, not flattened to booleans at ingestion
  4. Long-tail scanner-native fields land in a queryable `source_signals` JSONB field per finding, with a fixture proving "missing" (field never returned) is distinguishable from "negative" (field returned false/zero)
  5. A dedicated daily job in the existing in-process scheduler refreshes global, tenant-independent `epss_scores`/`cisa_kev` reference tables, decoupled from any individual connector's sync cadence

**Plans**: 3/5 plans executed

- [x] 31-01-PLAN.md — TRACER: Defender end-to-end enrichment slice (schema spine: migrations 035+036, 4 columns, EpssScore/CisaKev models, dataclass fields, enrichment write-path, Defender parser) *(complete 2026-08-05 — SC#1-4 GREEN on Defender; migrations 035+036 applied, single alembic head; requirements stay Pending, shared-ID gated on 31-02/03/04/05)*
- [x] 31-02-PLAN.md — EPSS/KEV feed fetcher + daily scheduler refresh (atomic-swap-keeps-last-good, eager first-run, re-propagation UPDATE) [ENRICH-05]
- [x] 31-03-PLAN.md — CrowdStrike + Nessus native signals (ExPRT.AI, VPR) + source_signals
- [ ] 31-04-PLAN.md — Qualys + Rapid7 native signals (QDS, riskScore) + source_signals
- [ ] 31-05-PLAN.md — Wiz source_signals (null native, guarded GraphQL) + cross-6 ENRICH-06 sweep

### Phase 32: Asset Exposure Context

**Goal**: Every asset carries an accurate, admin-overridable exposure-context profile reflecting real business risk, ready to feed the risk-exposure model.
**Depends on**: Nothing (independent of Phases 30–31; must land before Phase 33)
**Requirements**: EXPO-01, EXPO-02, EXPO-03, EXPO-04, EXPO-05, EXPO-06
**Success Criteria** (what must be TRUE):

  1. Every asset carries business-criticality, data-sensitivity, and internet-facing fields, auto-inferred at upsert from existing MDM/HR/IdP enrichment plus scanner internet-facing flags, seeded from — never overwriting — existing `Asset.tags`
  2. An admin can set a per-field override on a single asset, and that override permanently wins over any future auto-inference re-run
  3. An admin can set an override at asset-group scope, with a defined and tested precedence against a per-asset override on the same field
  4. Every exposure-context override (auto or manual) is audit-logged with actor, asset/group, field, old value, and new value
  5. A calibration check caps or flags the proportion of assets auto-classified at the highest criticality tier, provable against a realistic seed-data fixture (guards against criticality inflation cascading into score/SLA distortion)

**Plans**: TBD
**UI hint**: yes

### Phase 33: Risk-Exposure Model Definition

**Goal**: A new deterministic, explainable, versioned per-finding risk-exposure score exists and is validated in shadow — proven correct before any consumer depends on it.
**Depends on**: Phase 30, Phase 31, Phase 32
**Requirements**: RISK-01, RISK-02, RISK-03, RISK-04, RISK-05, RISK-06
**Success Criteria** (what must be TRUE):

  1. `risk_exposure_service.py` computes a deterministic, non-ML score from severity/CVSS + EPSS + KEV + vendor-native exploitability signals + asset exposure context + cross-scanner corroboration count
  2. A real per-finding score is computed and persisted (today only a per-asset aggregate exists); the asset-level score becomes a rollup of its findings, and a finding list can sort by "most urgent finding"
  3. CISA KEV acts as a near-automatic escalation/floor on the score — provable with a fixture where a low-severity KEV finding scores materially higher than an otherwise-identical non-KEV finding
  4. Cross-scanner corroboration measurably raises the score — provable with a fixture comparing an identical finding seen by 1 vs 3 scanners
  5. An analyst can see the per-input score breakdown ("why is this an 82") for a finding in the DrillPanel
  6. The score carries a `risk_model_version` column and is shadow-computed for at least one full sync cycle with zero consumers reading it before cutover; the previously-triplicated severity-tier boundaries (`export.py`/`assets/router.py`/`dashboard.py`) are centralized to one constant

**Plans**: TBD
**UI hint**: yes

### Phase 34: Historical Recompute & Consumer Cutover

**Goal**: Every tenant's historical data is safely, provably recomputed onto the new score, every real consumer reads it, and cutover day produces no alert storm, no trend cliff, and no silently reinterpreted tenant thresholds.
**Depends on**: Phase 33
**Requirements**: RISK-07, RISK-08, RISK-09, RISK-10
**Success Criteria** (what must be TRUE):

  1. The one-time historical recompute is idempotent, resumable, throttled, and per-tenant isolated (bulk `UPDATE ... FROM`, reusing the `backfill_sla_due_dates` + scheduler-tick idiom, never a blocking Alembic data migration) — proven by a kill-mid-run-and-resume test AND a realistic single-VM load test, not just seed-row correctness
  2. SLA breach detection, list sorting (`sort="triage"`), trend charts, and the v3.0 AI batch selector (`get_top_findings_for_ai_batch`) all read the new score; SLA windows remain severity-keyed
  3. Every tenant receives a pre/post diff report for its `min_risk_score` automation-rule and saved-filter thresholds and must give an explicit re-tuning acknowledgment before its data is cut over — no silent reinterpretation
  4. The day-over-day risk-spike notification (`_check_risk_score_changes`) and the trend chart are version-boundary-guarded, provable with a fixture spanning the cutover boundary that produces neither an alert storm nor a trend cliff

**Plans**: TBD

### Phase 35: Source-Aware Filtering & Provenance Badges

**Goal**: Every finding/asset/CSPM/ticket row shows honest, non-overclaiming source provenance, and analysts get real per-entity OR/AND scanner-source filtering.
**Depends on**: Phase 30, Phase 34
**Requirements**: SRC-01, SRC-02, SRC-03, SRC-04, SRC-05, SRC-06, SRC-07, SRC-08
**Success Criteria** (what must be TRUE):

  1. Every finding row shows a `SourceBadgeGroup` that visually distinguishes single-source from multi-source-corroborated, and never implies "confirmed" from a single scanner
  2. Vulnerabilities and Assets support a scanner-source filter that defaults to OR (any selected scanner) with an AND toggle for true multi-scanner corroboration, implemented via the correlation-array `@>`/`&&` operators; the Assets filter partitions scanner sources from non-scanner enrichment sources (JAMF/HUMAANS/Intune)
  3. CSPM supports true multi-tool AND corroboration via a new resource + rule-id grouping concept — not a silent OR fallback
  4. Ticket source provenance resolves transitively through the linked vulnerability's correlation, with a defined and tested rule for multi-source-correlated cases
  5. Provenance and source-facet queries are batched (no per-row N+1) and stay performant at scale, provable with a query-count assertion

**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases 30 and 31 and 32 can execute in any order/parallel (no interdependency); Phase 33 requires all three; Phase 34 requires Phase 33; Phase 35 requires Phase 30 and Phase 34.

| Phase | Plans Complete | Status | Completed |
|-------|-----------------|--------|-----------|
| 30. Correlation Schema Fix | 2/2 | Complete    | 2026-08-05 |
| 31. Connector Enrichment Rewrite | 3/5 | In Progress | - |
| 32. Asset Exposure Context | 0/TBD | Not started | - |
| 33. Risk-Exposure Model Definition | 0/TBD | Not started | - |
| 34. Historical Recompute & Consumer Cutover | 0/TBD | Not started | - |
| 35. Source-Aware Filtering & Provenance Badges | 0/TBD | Not started | - |
