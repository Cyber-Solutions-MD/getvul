# Requirements: GetVul — v4.0 Enriched Risk Exposure & Source-Aware Triage

**Defined:** 2026-08-04
**Core Value:** A vuln-triage analyst can open one dashboard, see the same CVE-on-host correlated across multiple scanners, identify the asset's owner from IdP/MDM/HR, and ship a Jira/Asana ticket — without ever opening a scanner console.

**Milestone goal:** Capture the richer signals each scanner actually provides, rebuild the risk-exposure model around them (plus asset-exposure context), and make scanner provenance a first-class, filterable, badged dimension across the whole app.

> **Grounding:** This milestone is an *extension/rebuild* of live infrastructure, not greenfield — see `.planning/research/SUMMARY.md`. Two verified defects (the 4-of-6-scanner correlation gap, and lossy boolean-ized ingestion with `epss_score` populated by no connector) are prerequisite fixes, not new features. The clean-slate risk model is the highest-risk work and is deliberately split into *define* and *recompute/cut-over*.

## v1 Requirements

Requirements for the v4.0 release. Each maps to exactly one roadmap phase (see Traceability).

### Correlation Completeness (CORR) — prerequisite

- [ ] **CORR-01**: Cross-source correlation records the complete set of scanners that see each CVE-on-host (all 6 sources, forward-compatible with a 7th), replacing the hardcoded 4-source FK columns with a `sources ARRAY(String)` + GIN-index shape (mirrors the shipped `assets.tags` pattern)
- [ ] **CORR-02**: Existing correlation data (including Qualys/Rapid7, silently dropped today) is migrated into the generalized source-set model with no loss, tenant-scoped
- [ ] **CORR-03**: `correlation_service.py` loops over the full `VulnSource` enum instead of a hardcoded 4-entry `SOURCE_COLUMN_MAP`, so `sources_count` and the resolved source names can never disagree

### Connector Enrichment (ENRICH)

- [ ] **ENRICH-01**: EPSS score + percentile is captured per finding and populated for every connector (the `epss_score` column exists today but no connector populates it)
- [ ] **ENRICH-02**: Real CISA KEV status is captured per finding from an authoritative feed (fixing the Defender `cisa_kev=False` hardcode)
- [ ] **ENRICH-03**: Vendor-native exploitability/priority signals (Nessus VPR, CrowdStrike ExPRT.AI rating + score, and each scanner's equivalent) are preserved per finding in promoted typed columns for sort/filter, not flattened to booleans at ingestion
- [ ] **ENRICH-04**: Long-tail scanner-native signals are retained per finding in a queryable `source_signals` JSONB field (mirrors the `Asset.mdm_details` precedent), with explicit "missing vs. negative" modeling
- [ ] **ENRICH-05**: EPSS and CISA KEV reference data live in global, tenant-independent reference tables refreshed by a dedicated daily job in the existing in-process scheduler, decoupled from any individual connector's sync cadence (a deliberate, signed-off exception to the "every table has `tenant_id`" convention, correct because this is CVE-level fact, not tenant-owned data)
- [ ] **ENRICH-06**: All 6 connectors (CrowdStrike, Nessus, Defender, Wiz, Qualys, Rapid7) thread native signals from the raw vendor payload through ingestion, so new fields are never permanently null/inconsistent

### Asset Exposure Context (EXPO)

- [ ] **EXPO-01**: Each asset carries business-criticality, data-sensitivity, and internet-facing exposure-context fields
- [ ] **EXPO-02**: Exposure context is auto-inferred at asset upsert from existing MDM/HR/IdP enrichment + scanner internet-facing flags, seeded from (never overwriting) existing `Asset.tags`
- [ ] **EXPO-03**: An admin can override any exposure-context field per asset, and a set override permanently wins over auto-inference (explicit per-field override discriminator)
- [ ] **EXPO-04**: An admin can override exposure context at asset-group scope, with a defined precedence between group and per-asset overrides
- [ ] **EXPO-05**: Every exposure-context override is audit-logged (actor, asset/group, field, old→new)
- [ ] **EXPO-06**: Auto-inference is calibration-bounded — the proportion of assets auto-classified at the highest criticality is capped/flagged to prevent criticality inflation cascading into score/SLA distortion

### Risk-Exposure Model (RISK)

- [ ] **RISK-01**: A deterministic, explainable (non-ML) risk-exposure model computes a score from severity/CVSS + EPSS + KEV + vendor-native exploitability signals + asset exposure context + cross-scanner corroboration count
- [ ] **RISK-02**: A real per-finding risk-exposure score is computed and persisted (today only a per-asset aggregate exists), so finding lists can sort by "most urgent finding"; the asset score becomes a rollup of it
- [ ] **RISK-03**: CISA KEV acts as a near-automatic escalation/floor on the score (per BOD-26-04 guidance), not merely a buried multiplier
- [ ] **RISK-04**: Cross-scanner corroboration count raises confidence/urgency in the score (the aggregator differentiator)
- [ ] **RISK-05**: The score is explainable — an analyst can see the per-input breakdown ("why is this an 82") for a finding/asset in the DrillPanel
- [ ] **RISK-06**: The score is versioned via a `risk_model_version` column and shadow-computed for at least one full sync cycle before any consumer reads it
- [ ] **RISK-07**: The one-time historical recompute is idempotent, resumable, throttled, and per-tenant isolated (bulk `UPDATE … FROM`, reusing the shipped `backfill_sla_due_dates` + scheduler-tick idiom, never a blocking Alembic data migration) and provably survives a kill-mid-run-and-resume + a realistic single-VM load test
- [ ] **RISK-08**: SLA breach detection, list sorting (`sort="triage"`), trend charts, and the v3.0 AI batch selector (`get_top_findings_for_ai_batch`) cut over to the new score; SLA windows remain severity-keyed; hardcoded severity-tier boundaries currently triplicated across `export.py`/`assets/router.py`/`dashboard.py` are centralized to one constant
- [ ] **RISK-09**: Before cutover, each tenant receives a pre/post diff report for its `min_risk_score` automation-rule and saved-filter thresholds, requiring explicit re-tuning acknowledgment (no silent reinterpretation)
- [ ] **RISK-10**: The day-over-day risk-spike notification (`_check_risk_score_changes`) and the trend chart are version-boundary-guarded so cutover day produces neither an alert storm nor a trend cliff

### Source-Aware Filtering & Provenance (SRC)

- [ ] **SRC-01**: Every finding row shows a source-provenance badge indicating which scanner(s) reported it, visually distinguishing single-source from multi-source-corroborated (badges must never imply "confirmed" from a single scanner)
- [ ] **SRC-02**: A scanner-source filter is available on Vulnerabilities, Assets, CSPM, and Tickets
- [ ] **SRC-03**: Selecting multiple sources defaults to OR (findings seen by any selected scanner)
- [ ] **SRC-04**: An AND toggle filters to findings corroborated by all selected scanners (Vulnerabilities/Assets via the correlation-array `@>` operator)
- [ ] **SRC-05**: CSPM supports true multi-tool AND corroboration via a new resource + rule-id grouping concept (not a silent OR fallback)
- [ ] **SRC-06**: The Assets source filter partitions scanner sources from non-scanner enrichment sources (JAMF/HUMAANS/Intune) so enrichment providers don't leak into a scanner-source filter
- [ ] **SRC-07**: Ticket source provenance resolves transitively through the linked vulnerability's correlation, with a defined rule for multi-source-correlated cases
- [ ] **SRC-08**: Provenance and source-facet queries are batched (no per-row N+1) and performant at scale

## v2 Requirements

Deferred to a future release. Tracked but not in this roadmap.

### AI / NL

- **AINL-01**: Natural-language triage assistant — bounded function-calling over the existing already-tenant-scoped filter/search endpoints, never generated SQL (deferred from v3.0)

### Exposure & Scoring extensions

- **EXPO-07**: Compound "why exposed" summary chips beyond the DrillPanel breakdown (presentation polish — sequence after the fields/model stabilize)
- **RISK-11**: Consume a vendor/third-party ML exploit-prediction output as an additional signal (only if a defensible source appears)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| In-house ML exploit-prediction model | No defensible training data at single-tenant scale; breaks the v3.0 "deterministic, explainable, AI augments-never-replaces the score" invariant. Consume vendor ML output instead (see RISK-11 future). |
| Wiz-style toxic-combination / attack-path reachability signals | Out of GetVul's aggregator scope per PROJECT.md; GetVul normalizes scanner output, it does not compute attack paths. |
| Moving SLA windows to risk-exposure-score bands | Product decision made to keep SLA severity-keyed this milestone (lowest cutover risk); revisit only if severity-keying proves insufficient. |
| Raw CVE feeds (NVD/OSV) as findings | GetVul aggregates scanner output, not raw vuln intel (existing platform boundary). EPSS/KEV are used only as enrichment reference data, never as standalone findings. |
| Multi-region HA / SaaS multi-org / self-scanning | Unchanged existing platform boundaries. |

## Traceability

Which phases cover which requirements. Populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CORR-01 | Phase 30 (Correlation Schema Fix) | Pending |
| CORR-02 | Phase 30 (Correlation Schema Fix) | Pending |
| CORR-03 | Phase 30 (Correlation Schema Fix) | Pending |
| ENRICH-01 | Phase 31 (Connector Enrichment Rewrite) | Pending |
| ENRICH-02 | Phase 31 (Connector Enrichment Rewrite) | Pending |
| ENRICH-03 | Phase 31 (Connector Enrichment Rewrite) | Pending |
| ENRICH-04 | Phase 31 (Connector Enrichment Rewrite) | Pending |
| ENRICH-05 | Phase 31 (Connector Enrichment Rewrite) | Pending |
| ENRICH-06 | Phase 31 (Connector Enrichment Rewrite) | Pending |
| EXPO-01 | Phase 32 (Asset Exposure Context) | Pending |
| EXPO-02 | Phase 32 (Asset Exposure Context) | Pending |
| EXPO-03 | Phase 32 (Asset Exposure Context) | Pending |
| EXPO-04 | Phase 32 (Asset Exposure Context) | Pending |
| EXPO-05 | Phase 32 (Asset Exposure Context) | Pending |
| EXPO-06 | Phase 32 (Asset Exposure Context) | Pending |
| RISK-01 | Phase 33 (Risk-Exposure Model Definition) | Pending |
| RISK-02 | Phase 33 (Risk-Exposure Model Definition) | Pending |
| RISK-03 | Phase 33 (Risk-Exposure Model Definition) | Pending |
| RISK-04 | Phase 33 (Risk-Exposure Model Definition) | Pending |
| RISK-05 | Phase 33 (Risk-Exposure Model Definition) | Pending |
| RISK-06 | Phase 33 (Risk-Exposure Model Definition) | Pending |
| RISK-07 | Phase 34 (Historical Recompute & Consumer Cutover) | Pending |
| RISK-08 | Phase 34 (Historical Recompute & Consumer Cutover) | Pending |
| RISK-09 | Phase 34 (Historical Recompute & Consumer Cutover) | Pending |
| RISK-10 | Phase 34 (Historical Recompute & Consumer Cutover) | Pending |
| SRC-01 | Phase 35 (Source-Aware Filtering & Provenance Badges) | Pending |
| SRC-02 | Phase 35 (Source-Aware Filtering & Provenance Badges) | Pending |
| SRC-03 | Phase 35 (Source-Aware Filtering & Provenance Badges) | Pending |
| SRC-04 | Phase 35 (Source-Aware Filtering & Provenance Badges) | Pending |
| SRC-05 | Phase 35 (Source-Aware Filtering & Provenance Badges) | Pending |
| SRC-06 | Phase 35 (Source-Aware Filtering & Provenance Badges) | Pending |
| SRC-07 | Phase 35 (Source-Aware Filtering & Provenance Badges) | Pending |
| SRC-08 | Phase 35 (Source-Aware Filtering & Provenance Badges) | Pending |

**Coverage:**
- v1 requirements: 33 total (CORR 3, ENRICH 6, EXPO 6, RISK 10, SRC 8)
- Mapped to phases: 33/33 ✓
- Unmapped: 0 ✓ (Phase 30 CORR, Phase 31 ENRICH, Phase 32 EXPO, Phase 33 RISK-01..06, Phase 34 RISK-07..10, Phase 35 SRC)

---
*Requirements defined: 2026-08-04*
*Last updated: 2026-08-04 after v4.0 roadmap creation — 33/33 requirements mapped to Phases 30-35, no orphans*
