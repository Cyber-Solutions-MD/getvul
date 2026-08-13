---
phase: 34
slug: historical-recompute-consumer-cutover
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-08-11
---

# Phase 34 — Validation Strategy

> Highest-risk phase. Fixture-level validation only (no live/at-scale data here). Every RISK-07..10 → ≥1 automated fixture test. The at-scale backfill + the live consumer flip are accepted debt for a human on a validated stack (34-CONTEXT).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (backend) |
| **Config file** | backend/pyproject.toml (`asyncio_mode = "auto"`) |
| **Quick run** | `cd backend && ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") JWT_SECRET_KEY=test-secret .venv/bin/python -m pytest tests/test_risk_recompute.py -x` |
| **Full suite** | per-file across the 4 Phase-34 test files (below) |
| **Estimated runtime** | ~5–30s per file (load fixture bounded to <30s) |

Note: real Fernet ENCRYPTION_KEY + JWT_SECRET_KEY required; run per-file (MEMORY getvul-backend-pytest-env).

---

## Sampling Rate

- **After every task commit:** run the touched test file
- **After every wave:** run all Phase 34 test files (per-file)
- **Before `/gsd-verify-work`:** all 4 Phase-34 files green + `alembic upgrade head` clean (single head 044) + the flag-OFF gate greps below + a verifier manual re-read of `capture_daily_snapshot` + `_check_risk_score_changes` (confirm the dead-code fix is real, not just fixture-passed — Pitfall 2)
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| 34-01 T1 | 01 | 1 | RISK-07 | RED (fixtures) | `pytest tests/test_risk_recompute.py -x` (expects RED) | ⬜ pending |
| 34-01 T2 | 01 | 1 | RISK-07 | migration/model | `alembic upgrade head && alembic heads \| grep 044_add_risk_backfill_job` | ⬜ pending |
| 34-01 T3 | 01 | 1 | RISK-07 | integration/fixture | `pytest tests/test_risk_recompute.py -x` (chunk, idempotent, kill-mid-chunk, restart-resume, isolation, load, non-blocking) | ⬜ pending |
| 34-02 T1 | 02 | 2 | RISK-08 | RED | `pytest tests/test_risk_cutover.py -x` (expects RED) | ⬜ pending |
| 34-02 T2 | 02 | 2 | RISK-08 | unit | `pytest tests/test_risk_cutover.py -x` (OFF byte-identical + ON new-score for sort/AI-batch; SLA-untouched) | ⬜ pending |
| 34-03 T1 | 03 | 2 | RISK-09 | RED | `pytest tests/test_risk_cutover_ack.py -x` (expects RED) | ⬜ pending |
| 34-03 T2 | 03 | 2 | RISK-09 | integration | `pytest tests/test_risk_cutover_ack.py -x -k "diff or ack or gates or stale"` | ⬜ pending |
| 34-03 T3 | 03 | 2 | RISK-09 | integration | `pytest tests/test_risk_cutover_ack.py -x` (RBAC 403 + audit rows + 409 gates) | ⬜ pending |
| 34-04 T1 | 04 | 2 | RISK-10 | RED | `pytest tests/test_risk_boundary_guard.py -x` (expects RED) | ⬜ pending |
| 34-04 T2 | 04 | 2 | RISK-10 | unit/fixture | `pytest tests/test_risk_boundary_guard.py -x -k "populates or cliff"` | ⬜ pending |
| 34-04 T3 | 04 | 2 | RISK-10 | integration/fixture | `pytest tests/test_risk_boundary_guard.py -x` (genuine-spike non-zero control + boundary no-storm) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Requirement → Fixture Coverage (mandatory fixtures)

| Requirement | Mandatory fixture | Test | File |
|-------------|-------------------|------|------|
| RISK-07 | kill-mid-run-and-resume (mid-CHUNK, no double-count) | `test_kill_mid_chunk_resumes_correctly` | test_risk_recompute.py |
| RISK-07 | simulated process restart resume-from-cursor | `test_resume_survives_simulated_restart` | test_risk_recompute.py |
| RISK-07 | realistic single-VM load (≥5 chunks) | `test_large_tenant_backfill_throughput` | test_risk_recompute.py |
| RISK-07 | idempotent re-run + per-tenant isolation + throttle | `test_backfill_is_idempotent`, `test_tenant_failure_isolated`, `test_chunk_size_bounds_each_pass` | test_risk_recompute.py |
| RISK-08 | flag-OFF byte-identical vs flag-ON new-score (both consumers) | `test_triage_sort_flag_off_is_identical` / `_cutover_flag`, `test_ai_batch_selector_flag_off_is_identical` / `_cutover_flag` | test_risk_cutover.py |
| RISK-08 | SLA stays severity-keyed (untouched) | `test_sla_breach_stays_severity_keyed` | test_risk_cutover.py |
| RISK-09 | pre/post diff + backfill-incomplete gate | `test_threshold_diff_computation`, `test_diff_refused_when_backfill_incomplete` | test_risk_cutover_ack.py |
| RISK-09 | ack gates the flip (both gates + stale-ack) | `test_flag_flip_requires_both_gates`, `test_stale_ack_after_threshold_change` | test_risk_cutover_ack.py |
| RISK-10 | boundary no-storm/no-cliff + genuine-spike non-zero control (Pitfall 2) | `test_cutover_boundary_no_storm_no_cliff`, `test_genuine_spike_still_alerts`, `test_trend_no_cliff` | test_risk_boundary_guard.py |

---

## Wave 0 Requirements (RED test files authored before implementation)

- [ ] `backend/tests/test_risk_recompute.py` (Plan 01 T1) — RISK-07: chunk correctness, idempotency, chunk-size bound, kill-mid-chunk resume (no double-count), simulated-restart resume, per-tenant isolation, multi-chunk load, dispatcher non-blocking
- [ ] `backend/tests/test_risk_cutover.py` (Plan 02 T1) — RISK-08: flag-OFF byte-identical + flag-ON new-score for sort="triage" and get_top_findings_for_ai_batch; SLA-untouched guard
- [ ] `backend/tests/test_risk_cutover_ack.py` (Plan 03 T1) — RISK-09: diff computation, backfill-incomplete gate, ack stamp+hash, stale-ack, both-gates flip, RBAC 403, audit rows
- [ ] `backend/tests/test_risk_boundary_guard.py` (Plan 04 T1) — RISK-10: snapshot dual-write, genuine-spike non-zero controls (OFF + ON), boundary no-storm, trend no-cliff

---

## Flag-OFF Safety Gates (run before `/gsd-verify-work`)

- [ ] `grep -n "op.execute" backend/alembic/versions/044_add_risk_backfill_job.py` → nothing (NO blocking data migration; recompute runs via the scheduler dispatcher)
- [ ] `grep -rn "def score_finding\|WEIGHT_\|SEVERITY_FALLBACK" backend/app/vulnerabilities/risk_backfill_service.py` → nothing (single scoring implementation reused)
- [ ] `grep -n "risk_exposure_score\|risk_score" backend/app/vulnerabilities/sla_service.py` → nothing (SLA stays severity-keyed)
- [ ] `git diff` shows NO change to `rule_engine.py` or `saved_filters.py` (RISK-09 diff+ack artifact only, Pitfall 4)
- [ ] `grep -n "cutover_risk_exposure_scoring" backend/app/vulnerabilities/trends.py` → nothing (dual-write is unconditional, not flag-gated)
- [ ] `cutover_risk_exposure_scoring` is NEVER set to `True` anywhere except inside `enable_cutover` (the both-gates-enforced endpoint), and is never invoked against live data in this env

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real at-scale per-tenant backfill | RISK-07 | No live/at-scale data in env | Run the backfill on a real stack; confirm idempotent/resumable/throttled at production row counts |
| Live consumer cutover flip | RISK-08 | Flag stays OFF here (user decision) | On a validated live stack: complete backfill → generate diff → ack → POST /risk-cutover/enable; confirm sort/trend/AI-batch read the new score, SLA unchanged |

---

## Validation Sign-Off

- [ ] Every RISK-07..10 maps to ≥1 automated (fixture) test
- [ ] kill-mid-run-and-resume + simulated-restart + load fixtures present (RISK-07)
- [ ] flag-OFF gate proven (no consumer reads new score with flag off; OFF path byte-identical)
- [ ] RISK-09 flip is structurally gated on backfill-complete + fresh-ack (409 otherwise); rule_engine/saved_filters untouched
- [ ] boundary fixture proves no storm / no cliff, WITH a non-zero genuine-spike control (RISK-10, Pitfall 2)
- [ ] No watch-mode flags
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
