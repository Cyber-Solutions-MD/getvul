# Phase 33 Context — Risk-Exposure Model Definition

**Source:** inline discuss during "complete v4.0" (2026-08-11). Resolves the research open questions.

## Domain

A NEW deterministic, explainable, versioned PER-FINDING risk-exposure score, shadow-computed and proven
correct before any consumer depends on it (input to the Phase 34 recompute/cutover). Reconcile with the
EXISTING per-asset `backend/app/assets/risk_score.py` (147 lines, per-asset aggregate) — the new model is
**additive**: it adds a per-finding score; the asset score becomes a rollup of its findings.

## Locked decisions

- **Deterministic, non-ML, explainable.** Score 0–100 from: severity/CVSS + EPSS + CISA KEV (floor) +
  vendor-native exploitability + Phase 32 exposure context (criticality/data-sensitivity/internet-facing)
  + Phase 30 cross-scanner corroboration count. Every input's contribution is inspectable (RISK-05).
- **[RESOLVED A3 — RISK-05 vs RISK-06 tension] "Consumer" = an automated decision system** (SLA, sort,
  trend, AI-batch-selector). A **read-only analyst breakdown in the DrillPanel is NOT a consumer** and MAY
  ship in Phase 33, clearly labeled as a **shadow/preview** score. No automated behavior (SLA/sort/trend/
  AI selection) reads the new score in Phase 33 — those cut over in Phase 34. This satisfies RISK-05
  (analyst sees "why is this an 82") AND RISK-06 (no automated consumer reads it pre-cutover).
- **[RESOLVED Q1] Single invocation point:** compute the per-finding score at the existing post-sync hook
  (`sync.py:172-173`) only, this phase. Do NOT wire it into the other ~9 `compute_risk_scores` call sites yet.
- **[RESOLVED Q2] Asset rollup = MAX** of its findings' scores for now (simple, defensible); a
  volume-sensitive curve is explicitly deferred to Phase 34. Document it.
- **[RESOLVED Q3] KEV floor is internal design**, expressing CISA BOD 22-01's KEV "must-remediate" spirit —
  no external prescriptive numbers. KEV acts as a near-automatic escalation/floor so a low-severity KEV
  finding scores materially higher than an identical non-KEV finding (RISK-03, fixture-proven).
- **Native-signal normalization (highest-risk task):** `native_priority_score` arrives on incompatible
  vendor scales (Nessus VPR 0–10, Qualys QDS 0–100, Rapid7 0–1000, CrowdStrike unverified, None for
  Defender/Wiz). Normalize per-source to a common 0–1 before weighting; for CrowdStrike prefer the
  categorical `native_priority_rating` over its untrusted numeric. Soft-null: a missing native signal
  must never crash or zero the score — it just drops that input's weight.
- **Corroboration:** more scanners seeing a finding measurably raises the score (RISK-04, fixture: 1 vs 3
  scanners). Source count comes from Phase 30's `vulnerability_correlations.sources` ARRAY.
- **Versioning:** a `risk_model_version` column on the per-finding score; shadow-computed for ≥1 full sync
  cycle with zero automated consumers before Phase 34 cutover. The version constant + formula live in one
  place so Phase 34 can detect a version boundary.
- **Severity-tier centralization:** the `>=80/>=50/>=20` tier boundaries triplicated at
  `dashboard.py:125-128`, `export.py:368-371`, `assets/router.py:297-300` are centralized into ONE
  constant in `app/assets/risk_score.py`, zero behavior change (the 4th copy in frontend `RiskRing.tsx`
  is out of scope this phase — note it).

## Constraints (v4.0-wide)

Single-VM Docker Compose + in-process asyncio scheduler only; every query tenant_id-scoped; audit new
mutating admin actions (e.g. a recompute endpoint); deterministic score authoritative — AI augments, never
replaces (v3.0 principle). Alembic head 041_add_inet_facing_signal; revision ids ≤32 chars.

## UI

DrillPanel per-input score breakdown (RISK-05), shadow/preview-labeled. Follow sketch-findings-getvul
(sunset tokens, RiskRing precedent, state patterns, copy voice). Reuse the existing DrillPanel breakdown
/ citation-tier precedent from v3.0 where it fits.
