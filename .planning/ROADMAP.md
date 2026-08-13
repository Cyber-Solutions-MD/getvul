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
- [x] **Phase 31: Connector Enrichment Rewrite** — All 6 connectors thread native signals (VPR, ExPRT.AI, EPSS, real KEV) from the raw payload through ingestion; new global EPSS/KEV reference tables refreshed by a daily scheduler job (completed 2026-08-10)
- [x] **Phase 32: Asset Exposure Context** — Auto-infer criticality/data-sensitivity/internet-facing at asset upsert; per-asset and asset-group admin override with audit trail and criticality-inflation calibration bound (completed 2026-08-11)
- [x] **Phase 33: Risk-Exposure Model Definition** — Deterministic, versioned, explainable per-finding risk-exposure score; shadow-computed for a full sync cycle before any consumer reads it (completed 2026-08-11)
- [x] **Phase 34: Historical Recompute & Consumer Cutover** — Idempotent/resumable/throttled per-tenant backfill; SLA/sort/trend/AI-batch-selector cutover; per-tenant threshold re-tuning acknowledgment; version-boundary guards on alerts/trends (completed 2026-08-12)
- [x] **Phase 35: Source-Aware Filtering & Provenance Badges** — Per-entity OR/AND scanner-source filtering (Vulnerabilities, Assets, CSPM, Tickets) and a `SourceBadgeGroup` provenance component, batched queries (completed 2026-08-12 — pending /gsd-verify-phase 35)

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

**Plans**: 5/5 plans executed

- [x] 31-01-PLAN.md — TRACER: Defender end-to-end enrichment slice (schema spine: migrations 035+036, 4 columns, EpssScore/CisaKev models, dataclass fields, enrichment write-path, Defender parser) *(complete 2026-08-05 — SC#1-4 GREEN on Defender; migrations 035+036 applied, single alembic head; requirements stay Pending, shared-ID gated on 31-02/03/04/05)*
- [x] 31-02-PLAN.md — EPSS/KEV feed fetcher + daily scheduler refresh (atomic-swap-keeps-last-good, eager first-run, re-propagation UPDATE) [ENRICH-05]
- [x] 31-03-PLAN.md — CrowdStrike + Nessus native signals (ExPRT.AI, VPR) + source_signals
- [x] 31-04-PLAN.md — Qualys + Rapid7 native signals (QDS, riskScore) + source_signals
- [x] 31-05-PLAN.md — Wiz source_signals (null native, guarded GraphQL) + cross-6 ENRICH-06 sweep *(complete 2026-08-05 — VULNERABILITY_QUERY_ENRICHED + WizGraphQLSchemaError guard (A4: schema error falls back to the unchanged base query); source_signals allowlist of 6 raw keys, native_priority_* explicit None (Pitfall 6); cross-6 parametrized sweep proves all 6 connectors always explicitly set native_priority_score/native_priority_rating/source_signals. Last of the 4 declaring plans for ENRICH-03/04/06 — all 6 connectors now compliant. Phase 31 is 5/5 plans executed, pending /gsd-verify-work 31)*

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

**Plans**: 5/5 plans complete

Plans:

- [x] 32-01-PLAN.md — TRACER: business_criticality end-to-end (migration + enums/columns + inference + per-asset override + audit + response dicts) *(complete 2026-08-10 — migration 037 + exposure.py + PATCH/POST override+recompute endpoints + 6 keys in both inline dicts; 10/10 tests green, EXPO-01/02/03/05)*
- [x] 32-02-PLAN.md — all 3 fields real inference + EXPO-06 calibration check + per-tenant cap config *(complete 2026-08-10 — real data_sensitivity/internet_facing inference completing the triad; check_criticality_calibration (AUTO-only CRITICAL proportion, overrides exempt) + migration 038 per-tenant cap/hard-cap-enabled + admin GET /assets/exposure-context/calibration; 16/16 tests green, EXPO-06 complete)*
- [x] 32-03-PLAN.md — real AssetGroup entity (model + membership + admin CRUD) + group-scope override + per-asset>group>auto precedence *(complete 2026-08-10 — migrations 039/040 + AssetGroup/AssetGroupMember/AssetGroupExposureOverride models + groups_service/groups_router at /api/v1/asset-groups + apply_precedence_to_asset (GROUP_OVERRIDE tier, most-recently-updated tiebreak) + add_member/remove_member immediate re-apply + full audit trail; 24/24 tests green, EXPO-04/EXPO-05 complete)*
- [x] 32-04-PLAN.md — real per-connector internet-facing detection (detected-signal>proxy) + honest coverage doc *(complete 2026-08-11 — migration 041 Asset.internet_facing_detected + NormalizedVulnerability.internet_facing + sync.py passthrough + infer_exposure_context detected-signal-beats-proxy precedence; all 6 connectors (CrowdStrike/Wiz/Qualys/Nessus/Rapid7/Defender) directly inspected and honestly documented FALLBACK — none currently exposes a distinct internet-facing signal; 31/31 new+regression tests green, EXPO-02 complete)*
- [x] 32-05-PLAN.md — frontend: exposure card + inline override + AssetGroup management page (sketch-findings, mandatory states, admin gating) *(complete 2026-08-11 — exposure-context-card.tsx (3 fields + source badges incl. "group: {name}") + admin flip-edit override wired into assets/[id]'s rail; /dashboard/asset-groups management page (list/create/edit/delete + membership + per-group override) + nav entry; backend deviation added member_count + GET members/exposure-context read endpoints + group-name read-side lookup (Rule 2/3, no schema change). 18 new frontend tests + 6 new backend tests green, full frontend suite 922/922 + full backend exposure/groups suite green, tsc/eslint clean. Task 3 human-verify checkpoint recorded as accepted verification debt — no live browser in this environment.)*

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

**Plans**: 4/4 plans complete

- [x] 33-01-PLAN.md — Tracer: per-finding score column + migration → deterministic score_finding (severity/CVSS+EPSS+KEV floor) → persist at sync hook → read into response *(complete 2026-08-11 — migration 042 (5 nullable columns); risk_exposure_service.py's score_finding (pure, severity/CVSS+EPSS+KEV-floor real, native/exposure/corroboration zeroed Plan-33-02 placeholders) + compute_finding_risk_scores (DB-orchestration); single sync.py post-sync hook wire; GET /vulnerabilities/{id} persisted-column read. 5 new backend tests green, zero-consumer grep gate confirmed.)*
- [x] 33-02-PLAN.md — Full formula: native per-source 0-1 normalization + exposure context + corroboration; KEV-floor + 1-vs-3-scanner fixtures *(complete 2026-08-11 — _normalize_native_signal (per-source 0-1, soft-null, never raises); exposure 3-row split (business_criticality/internet_facing/data_sensitivity) driven by real Asset fields; corroboration capped linear fraction fed by a single tenant-scoped VulnerabilityCorrelation bulk-join (no N+1); kev_floor breakdown row emitted when the floor changes the outcome. RISK-03 re-proven under the full formula, RISK-04 proven (corroboration component delta exactly 6.67). 10/10 tests green (5 Plan 01 regression + 5 new).)*
- [x] 33-03-PLAN.md — Asset MAX rollup + sortable index; severity-tier centralization (one constant) + characterization regression *(complete 2026-08-11 — compute_finding_risk_scores rolls Asset.risk_exposure_score up to the MAX of open findings (NULL reset when none) via one bulk subquery + outerjoin, risk_model_version stamped; migration 043 adds a btree index on Vulnerability.risk_exposure_score (zero-consumer gate intact); RISK_SCORE_TIER_CRITICAL/HIGH/MEDIUM centralized in risk_score.py, imported by dashboard.py/export.py/assets/router.py, zero behavior change proven by test_risk_tier_distribution.py (byte-identical bucket counts before/after). RISK-02/RISK-06 complete. 13/13 new+regression tests green.)*
- [x] 33-04-PLAN.md — DrillPanel per-input breakdown ("why is this an 82"), shadow/preview-labeled (RISK-05) *(complete 2026-08-11 — new "Risk exposure" DrillPanel section (desktop+mobile, one drill-content.tsx edit) renders the shadow risk_exposure_score via a reused RiskRing + a data-driven row per risk_exposure_breakdown component + a "★ KEV floor applied" chip keyed off a kev_floor component + a "Shadow score — not yet used for sorting or alerts" preview caption; null-safe absent state when unscored. 51/51 RTL tests green (both DrillPanel wrapper suites), full frontend suite 137 files/926 tests green, tsc/eslint clean. RISK-05 complete — Phase 33 is now 4/4 plans complete, RISK-01..06 all marked Complete in REQUIREMENTS.md, pending /gsd-verify-work 33 for phase-level closeout. Task 3 human-verify checkpoint recorded as accepted manual-UAT (no live browser in this environment), matching Phase 31's waived-on-trust precedent.)*

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

**Plans**: 5/5 plans complete (Wave 1: 01 tracer done; Wave 2: 02/03/04 done — parallel, no file overlap; 05: gap-closure)

- [x] 34-01-PLAN.md — RISK-07 lead tracer: durable RiskExposureBackfillJob + migration 044 (+cutover flag +ack columns) → chunked idempotent resumable bulk UPDATE...FROM → scheduler dispatcher → kill-mid-chunk/restart/isolation/load fixtures *(complete 2026-08-11 — migration 044 lands the full Phase-34 schema spine (job table + 3 Tenant columns) additively, no data migration; risk_backfill_service.py implements claim-row/keyset-cursor/WHERE-guard chunked backfill reusing score_finding verbatim; scheduler dispatcher wired via asyncio.create_task, no in-memory gate. 9/9 RISK-07 fixture tests green incl. kill-mid-chunk-no-double-count + simulated-restart resume + per-tenant isolation + multi-chunk load. 2 Rule-1 bugs found+fixed during GREEN (heartbeat-clear-on-success; identity-map staleness after raw bulk UPDATE). alembic round-trip clean, single head 044; 0 new mypy-baseline violations. Pre-existing (non-Phase-34) test-isolation hang between test_risk_exposure_service.py + test_scheduler_enrichment_refresh.py logged to deferred-items.md, confirmed not a regression.)*
- [x] 34-02-PLAN.md — RISK-08 flag-gated cutover: sort="triage" + get_top_findings_for_ai_batch read the new score when ON (byte-identical OFF); SLA stays severity-keyed (untouched) *(complete 2026-08-12 — once-per-call scalar Tenant fetch (mirrors sla_service.py:43) branches both consumers' primary order_by key on cutover_risk_exposure_scoring; OFF path byte-identical (proven by inverted-fixture tests + all 23 pre-existing regression tests staying green unmodified); ON path leads by risk_exposure_score desc for both. Asset outerjoin kept on both get_top_findings_for_ai_batch paths; stale "no risk_score field" docstring corrected. sla_service.py/rule_engine.py/saved_filters.py/trends.py untouched — confirmed via grep + git diff. 5/5 new RISK-08 tests green, 0 new mypy-baseline violations, ruff clean.)*
- [x] 34-03-PLAN.md — RISK-09 diff+ack: pre/post min_risk_score threshold diff + audited per-tenant ack + admin flag-flip endpoint gated on backfill-complete + fresh-ack (no live retarget) *(complete 2026-08-12 — risk_cutover_service.py: compute_threshold_diff (backfill-completion gated, Pitfall 3), record_threshold_ack (audited stamp+hash), enable_cutover (both-gates-enforced, gate-specific 409 detail strings: backfill_incomplete/threshold_ack_missing/threshold_ack_stale); 3 admin endpoints under /api/v1/risk-cutover wired in main.py; audit.py gained risk_cutover.threshold_ack/risk_cutover.flag_enable. 8/8 new RISK-09 fixture tests green (diff computation, backfill-gate, ack stamp+hash, stale-ack invalidation, both-gates flip, RBAC 403). rule_engine.py/saved_filters.py untouched (git diff empty — no live retarget, Pitfall 4). 0 new mypy-baseline violations, ruff clean. Flip never invoked against live data in this environment (accepted debt, 34-CONTEXT.md locked).)*
- [x] 34-04-PLAN.md — RISK-10 boundary guards: unconditional DailySnapshot dual-write + dead _check_risk_score_changes fix + same-version-only diffing; boundary fixture proves no storm / no cliff *(complete 2026-08-12 — capture_daily_snapshot unconditionally dual-writes avg_risk_exposure_score/asset_risk_scores/asset_risk_exposure_scores/risk_model_version_snapshot into every DailySnapshot (grep for the flag name in trends.py returns nothing); get_risk_score_trend exposes avg_risk_exposure as an additional key, avg_risk unchanged. _check_risk_score_changes now genuinely fires (was dead code — asset_risk_scores was never populated before this phase) and diffs same-version-only (new-vs-new ON, old-vs-old OFF), never cross-version. 5/5 new RISK-10 fixture tests green including two Pitfall-2 non-zero controls (proving the check fires before trusting a boundary-zero result) and the core boundary fixture (flag flips OFF→ON mid-history, 0 storm alerts, continuous new trend series vs. a 65-point old-series cliff). test_severity_trends.py + test_dashboard_tiles.py regress clean, ruff clean. Phase 34 is now 4/4 plans complete.)*
- [x] 34-05-PLAN.md — Gap closure (34-VERIFICATION.md, score 3.5/4): GAP 1 flag-gates the trend chart's primary series on `cutover_risk_exposure_scoring` (the third named RISK-08 consumer, previously unconditional); GAP 2 adds an admin-only `POST /api/v1/risk-cutover/backfill/enqueue` production trigger for RISK-07's previously test-only-invoked backfill machinery *(complete 2026-08-12 — get_risk_score_trend now branches its PRIMARY avg_risk series on the flag exactly like service.py's sort="triage"/get_top_findings_for_ai_batch pattern: OFF byte-identical (avg_risk_score only, no extra key), ON swaps to avg_risk_exposure_score; capture_daily_snapshot's dual-write (RISK-10) stays unconditional, only the read branches. Updated test_risk_boundary_guard.py::test_trend_no_cliff (asserted the old unconditional dual-key shape) to prove continuity under the flag a tenant actually reads with. New admin backfill-enqueue endpoint wraps the already-idempotent enqueue_backfill_job with audit()-then-commit (only on a genuinely new enqueue); RBAC 403 for non-admin, idempotent for active/completed jobs, 0 duplicate rows. 7 new tests green (3 trend-cutover + 4 backfill-endpoint), 21/21 in the combined RISK-08/09/10/trend/dashboard regression window, 23/23 flag-OFF vulnerabilities/SLA/AI-batch regression, 0 new mypy-baseline violations, ruff clean, single alembic head unchanged (044). RISK-08 flipped to Complete in REQUIREMENTS.md.)*

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

**Plans**: 5/5 plans complete (Wave 1: 01, 02 tracer done; Wave 2: 03, 04 done; Wave 3: 05 done) — Phase 35 COMPLETE

- [x] 35-01-PLAN.md — TRACER (backend): Vulnerabilities correlation-ARRAY OR/AND source filter (`&&`/`@>`) + page-scoped batched provenance (sources/sources_count) + the NEW before_cursor_execute query-count harness *(complete 2026-08-12 — `_apply_filters` branches on `VulnerabilityCorrelation.sources` overlap (`&&`, OR default + single-source direct-match fallback) / contains (`@>`, AND toggle, structurally excludes single-source findings); `list_vulnerabilities` gains a page-scoped `tuple_(cve_id,asset_id).in_(page_keys)` batched provenance fetch (tenant-scoped per T-35-01) populating `VulnerabilitySummary.sources`/`sources_count`, no per-row query; `source_mode: Literal["or","and"]` bound as an explicit router Query param (this router builds filters from explicit params, not Depends). New `backend/tests/query_count.py` `before_cursor_execute` harness proves `list_vulnerabilities` issues a fixed 4 statements regardless of page size — reusable by Plans 03/04. `tuple_(...).in_(subquery)` compiles cleanly against asyncpg, no EXISTS fallback needed. 6/6 new tests green + 4/4 regression (test_vuln_source_filter.py) green. One Rule-1 fix: a genuine flake in the new query-count test caused by the engine-wide `before_cursor_execute` listener also catching an unrelated background EPSS-refresh task from sibling tests sharing the session-scoped event loop — fixed by filtering counted statements to the SUT's own tables.)*
- [x] 35-02-PLAN.md — TRACER (frontend): shared SourceBadgeGroup component (non-overclaiming) wired into vuln-table + vuln chip-bar OR/AND toggle + reconciled 6-value VulnSource list *(complete 2026-08-12 — new `source-badge-group.tsx`: literal `SOURCE_GRADIENTS`/`SOURCE_GLYPH` lookup maps (mirrors `ProviderMark`/`ConnectorMark` T-13-14/T-14-01, reusing the 6 `--gradient-provider-{crowdstrike,nessus,defender,wiz,qualys,rapid7}` tokens that already shipped with Phase 14's `ConnectorMark` — no token gap found); single source renders ONE gradient mark with zero corroboration chrome (no "confirmed"/"verified" copy, no `--color-success` tint), 2+ sources render the mark group + a `"N sources"` label using the SLA-ok green tint (CONTEXT [RESOLVED A3]); unknown codes (Assets-surface enrichment values) fall through to a neutral fallback mark, never a crash. Wired into `vuln-table.tsx`'s desktop Status cluster + mobile Row-3 cluster (`row.sources ?? [row.source]` / `row.sources_count`, both new optional `VulnTableRow` fields, backward-compatible). `chip-bar.tsx`'s `SOURCES` reconciled to the real 6-value `VulnSource` enum; a sibling OR/AND `?source_mode` toggle (`useUrlState('source_mode', ['or','and'], 'or')`) added below the generic ChipBar, disabled below 2 selected sources, copy "Any selected"/"All selected" (no AND/OR jargon per copy-voice.md). 6 new component tests + 5 new chip-bar tests green; one pre-existing chip-bar test fixture referencing the removed fake TENABLE value fixed (Rule 1). Full frontend regression 937/937 green, tsc/eslint clean.)*
- [x] 35-03-PLAN.md — Assets: fix the shipped multi-select-ANDs bug to OR-default + AND toggle + scanner/enrichment partition (SRC-06) + batched sources + seen_by_sources GIN index (migration 045) + rule_engine.py same fix *(complete 2026-08-12 — replaced the chained `.where(seen_by_sources.contains([s]))` AND-bug in `assets/router.py::list_assets` (SRC-03 shipped bug) with `or_(*contains)` OR-default, `source_mode=and` behind an explicit toggle (SRC-04); new `app/assets/constants.py` `SCANNER_SOURCES`/`ENRICHMENT_SOURCES` partition clamps `?scanner=` (enrichment can't leak in, SRC-06) and backs a new `?enrichment_source=` OR-only facet; each list row gains `sources`/`sources_count` derived in-Python from the already-selected column (zero extra queries, SRC-08, proven page-size-invariant via Plan 01's `count_queries()` harness filtered to the `assets` table); identical AND-bug fixed in `ticketing/rule_engine.py::find_matching_assets` using the same shared constant; migration 045 adds the `seen_by_sources` GIN index the column never had (mirrors 034). 6/6 new tests green (the OR-default union test is the literal bug-regression proof — fails against pre-fix code), 9/9 rule-engine tests green (no regression), 52/52 other asset-suite tests green, alembic round-trips clean at head 045, ruff/mypy clean (0 new type-debt). One Rule-1/2 deviation: added an explicit `false()` fallback when a `?scanner=`/`?enrichment_source=` value is fully clamped out, rather than silently falling through to "no filter" (which would leak enrichment-only assets into a scanner view) — not shown in the plan's own interfaces sketch but required by its own specified test behavior.)*
- [x] 35-04-PLAN.md — CSPM read-time GROUP BY(tenant_id,rule_id,resource_id) AND corroboration (no silent OR) + Tickets transitive union provenance (array_agg, not func.min); both batched with query-count assertions *(complete 2026-08-12 — `cspm/service.py::_apply_filters` AND branch (2+ selected sources) builds a `GROUP BY(rule_id,resource_id) HAVING count(DISTINCT source)>=len(selected)` subquery restricting the outer query, replacing NOTHING for OR (unchanged `source.in_()`, still correct); `list_misconfigurations` gains a page-scoped `tuple_((rule_id,resource_id)).in_(page_keys)` batched grouped query populating `MisconfigSummary.sources`/`sources_count`, tenant-scoped (T-35-01), proven page-size-invariant; `source_mode` bound as an explicit `cspm/router.py` Query param (this router builds filters from explicit params like Plan 01's Vulnerabilities router) — without it `?source_mode=and` is unreachable via HTTP, proven directly against a same-request service-vs-HTTP comparison. Tickets: `ticketing/service.py::list_tickets` extends the existing WR-05 `details_q` (already GROUP BY external_ticket_url) with `array_agg(DISTINCT Vulnerability.source)` as an `own_sources` floor (a real UNION, unlike the file's own documented `func.min` representative-pick aggregates alongside it), adds a new batched `(url,cve_id,asset_id)` keys query + ONE batched `VulnerabilityCorrelation` fetch (tenant-scoped), and a `_resolve_sources()` helper unions `own_sources` with every matched correlation's `sources` per grouped row (CONTEXT [RESOLVED A4] — multi-source if ANY linked vuln is corroborated, proven against a mixed 2-vuln grouped-task fixture); `list_tickets(source=...)` is a real OR-default filter (SRC-02, not display-only) using the same subquery-filter shape the function's pre-existing `severity_vals` filter already uses, bound through `ticketing/router.py::list_all_tickets`'s new `source` Query param — SRC-02 now delivered for all four entities. 10/10 new tests green (5 CSPM + 5 Tickets) + 91/91 combined regression (CSPM/ticketing/rule_engine/Vulnerabilities/Assets source-filter suites) green, ruff clean, mypy unchanged (149 baseline). One Rule-1 mid-task restructure: first ticket-provenance implementation did the entire union in pure Python with no SQL `array_agg` call, failing the plan's own no-representative-pick verification gate — restructured to extend `details_q` with a real `array_agg` for the group floor before committing, same final behavior, same query count.)*
- [x] 35-05-PLAN.md — Frontend expansion: SourceBadgeGroup on Assets/CSPM/Tickets rows + assets scanner/enrichment split axes + CSPM/Tickets source chips (OR/AND where backend-supported) *(complete 2026-08-12 — final plan of Phase 35 and of v4.0. `assets-chip-bar.tsx`: replaced the stale single `source` axis with a `scanner` axis (real 6-value set, `?scanner=`, OR/AND `?source_mode` toggle mirroring Plan 02's chip-bar toggle verbatim) and an independent `enrichment_source` OR-only facet (JAMF/HUMAANS/INTUNE, no toggle); `assets-table.tsx` wires `SourceBadgeGroup` into desktop + mobile row clusters. `cspm/page.tsx` gains the same OR/AND `source_mode` toggle reaching Plan 04's true multi-tool corroboration; `finding-card.tsx` wires `SourceBadgeGroup` (group sources over the finding's `(rule_id,resource_id)` group), falling back to `[finding.source]` for pre-Plan-04 shapes. `tickets-chip-bar.tsx` gains a REAL server-filtering `source` axis (6 real values, `?source=`, OR-default, no AND toggle — SRC-04 is scoped to Vulns/Assets/CSPM); `tickets-table.tsx` wires `SourceBadgeGroup` (transitive union provenance) alongside — and visually distinct from — the existing ticket `ProviderMark`. Deviation (Rule 3, blocking, all 3 tasks): threaded the new filters end-to-end through `use-assets.ts`/`use-cspm-findings.ts`/`use-tickets.ts` and the assets/tickets `page.tsx` files (not in the plan's own `files_modified` list) — without this the new chip-bar controls would write URL params nobody reads into the query, an inert filter. Confirmed the Tickets `?source=` param must be REPEATED (not comma-joined like the ticket-page's other 3 axes), matching the backend's `list[str] Query(None)` binding. Full frontend regression 961/961 green, `tsc --noEmit` clean, `eslint` clean (0 new errors). All 4 entities (Vulnerabilities, Assets, CSPM, Tickets) now share the identical non-overclaiming SourceBadgeGroup + SRC-02/03/04 OR/AND filter contract.)*

**UI hint**: yes

## Progress

**Execution Order:**
Phases 30 and 31 and 32 can execute in any order/parallel (no interdependency); Phase 33 requires all three; Phase 34 requires Phase 33; Phase 35 requires Phase 30 and Phase 34.

| Phase | Plans Complete | Status | Completed |
|-------|-----------------|--------|-----------|
| 30. Correlation Schema Fix | 2/2 | Complete    | 2026-08-05 |
| 31. Connector Enrichment Rewrite | 5/5 | Complete    | 2026-08-10 |
| 32. Asset Exposure Context | 5/5 | Complete    | 2026-08-11 |
| 33. Risk-Exposure Model Definition | 4/4 | Complete    | 2026-08-11 |
| 34. Historical Recompute & Consumer Cutover | 5/4 | Complete    | 2026-08-12 |
| 35. Source-Aware Filtering & Provenance Badges | 4/5 | In progress | - |
