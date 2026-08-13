# Phase 34 Context — Historical Recompute & Consumer Cutover

**Source:** user decision + inline discuss during "complete v4.0" (2026-08-11). THE MILESTONE'S HIGHEST-RISK PHASE.

## Domain

Safely recompute every tenant's historical data onto the Phase-33 `risk_exposure_score`, wire the real
consumers to read it, and guarantee cutover day yields no alert storm, no trend cliff, and no silently
reinterpreted tenant thresholds. Requirements RISK-07..10.

## Locked decisions

- **[USER] Flag-gated cutover, default OFF.** Build + fixture-test ALL machinery, but the consumer flip
  (reading the new score instead of the old) is gated behind an explicit flag that defaults **OFF**. Do
  NOT flip consumers in this environment (no live/at-scale tenant data). A human flips it on a validated
  live stack. Flag schema precedent: `Tenant.exposure_hard_cap_enabled` (`app/tenants/models.py:52`,
  migration 038) — but this flag is a REAL behavioral branch, not an inert stub. Provide a real,
  RBAC-gated, audited admin flip endpoint/config (Q3 resolved: build it; just never flip it live here).
- **[RESOLVED A1] SLA stays severity-keyed; it is NOT a score-cutover target.** SLA breach detection
  (`sla_service.py:41-115`, `notifications/alerts.py:100-141`) is severity/due-date-keyed today and
  RISK-08 explicitly says "SLA windows remain severity-keyed" — so there is nothing to flip for SLA. The
  three REAL cutover consumers behind the flag are: list sort `sort="triage"`, the trend chart, and the
  v3.0 AI batch selector `get_top_findings_for_ai_batch`. Document that SLA is intentionally untouched.
- **[RESOLVED A2] Fix the dead spike-notification path + dual-write continuity (in scope for RISK-10).**
  `_check_risk_score_changes` (`notifications/alerts.py:189-255`) reads `snapshot.metrics["asset_risk_scores"]`,
  a key `capture_daily_snapshot` (`trends.py:218-329`) never writes → dead today. RISK-10 requires the
  spike notification be boundary-guarded and fixture-provable, which is meaningless while it's a no-op.
  Therefore: (a) dual-write the new-model risk metrics into `DailySnapshot.metrics` **unconditionally**
  (independent of the flag) starting this phase, so real trend continuity exists before any flip; (b) fix
  the spike-notification read so it functions; (c) version-boundary-guard both the spike notification and
  the trend chart so a `risk_model_version` change across a day boundary produces neither an alert storm
  nor a trend cliff (fixture spanning the boundary).
- **[RESOLVED A5] RISK-09 = diff report + per-tenant ack artifact this phase; NO live threshold retarget.**
  `min_risk_score` in `rule_engine.py:65-67` and `saved_filters.py:104-105` compares the OLD
  `Asset.risk_score` and is untouched by the flag. RISK-09 produces a pre/post diff report for each
  tenant's `min_risk_score` automation-rule + saved-filter thresholds and captures an explicit per-tenant
  **re-tuning acknowledgment** (audited) that GATES the (human, deferred) flip — it does not silently
  retarget thresholds in this phase.
- **Backfill design (RISK-07):** idempotent + resumable + throttled + per-tenant isolated. Synthesize two
  shipped precedents: durable job state à la `AiBatchJob` (`app/ai/models.py:52-90`, survives restart) +
  the idempotent WHERE-guard shape of `backfill_sla_due_dates` (`sla_service.py:41-61`, which is NOT
  chunked — add chunking + a resume cursor). Bulk `UPDATE ... FROM`, scheduler-tick driven, **never** a
  blocking Alembic data migration. Prove with a kill-mid-run-and-resume test AND a realistic single-VM
  fixture load test (not just seed-row correctness).

## Constraints (v4.0-wide)

Single-VM Docker Compose + in-process asyncio scheduler only; every query tenant_id-scoped; audit the
cutover flip + the RISK-09 ack (mutating actions); deterministic score authoritative. Alembic head
043_index_risk_exposure_score; revision ids ≤32 chars.

## Environment honesty

This env has no live/at-scale tenant data — the backfill's idempotency/resumability/throttling, the
boundary guards, and the cutover wiring are all built + FIXTURE-tested here; the real at-scale backfill
and the live consumer flip are **accepted debt** for a human on a real stack (consistent with the
on-trust waivers in Phases 31/32/33). "v4.0 complete" here = machinery shipped, fixture-proven, and the
flip gated OFF awaiting live validation.
