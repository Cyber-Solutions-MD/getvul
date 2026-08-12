---
phase: 34-historical-recompute-consumer-cutover
verified: 2026-08-12T08:20:55Z
status: gaps_found
score: 3.5/4 must-haves verified
overrides_applied: 0
gaps:
  - truth: "Trend chart reads the new (risk_exposure_score-derived) series ONLY when the cutover flag is ON (RISK-08 / ROADMAP SC#2, third of the three named real cutover consumers alongside sort=\"triage\" and get_top_findings_for_ai_batch)"
    status: failed
    reason: >
      get_risk_score_trend (backend/app/vulnerabilities/trends.py:166-188) contains NO branch on
      Tenant.cutover_risk_exposure_scoring at all -- it unconditionally returns BOTH avg_risk (old) and
      avg_risk_exposure (new) as additional keys on every row, regardless of the flag. This differs in kind
      from the other two named consumers (list sort="triage" and get_top_findings_for_ai_batch), which both
      genuinely branch their primary ordering key on the flag (verified: service.py:95-115, 585-600) and are
      fixture-proven byte-identical OFF / correctly re-ranked ON (test_risk_cutover.py, 5/5 green). The trend
      chart was re-scoped mid-phase (34-CONTEXT.md RESOLVED A2) from "flag-gated read" to "unconditional
      dual-write + boundary guard," which is a legitimate and well-reasoned structural fix for the alert-storm
      /trend-cliff problem (RISK-10, fully verified) -- but it does not implement "reads the new score ONLY
      when the flag is ON" for the trend chart the way it does for the other two consumers. This is not an
      invented gap: REQUIREMENTS.md itself still has RISK-08 unchecked (`- [ ] **RISK-08**`, line 47) and the
      34-02-PLAN.md commit message states verbatim: "RISK-08 remains Pending in REQUIREMENTS.md -- the
      requirement also covers the trend chart's cutover continuity, which is Plan 04's scope... not yet
      landed." Plan 04 landed the dual-write and boundary guard (RISK-10) but never added a flag branch to
      get_risk_score_trend or any router calling it, so the self-acknowledged gap was never closed. ROADMAP.md
      nonetheless marks Phase 34 as `[x]` complete and RISK-08's roadmap traceability row is not reconciled
      with REQUIREMENTS.md's own Pending checkbox for the same requirement.
    artifacts:
      - path: "backend/app/vulnerabilities/trends.py"
        issue: "get_risk_score_trend (lines 166-188) has no cutover_risk_exposure_scoring read/branch; capture_daily_snapshot's dual-write (lines 290-330) is correctly unconditional (that part is RISK-10's job, verified), but nothing in this file implements RISK-08's per-tenant flag-gated trend read"
    missing:
      - "Either: (a) add a genuine flag branch somewhere in the trend-chart read path (get_risk_score_trend or its router/caller) so the series a tenant actually sees changes when cutover_risk_exposure_scoring flips, closing RISK-08 as originally scoped; or (b) formally accept 34-CONTEXT.md's RESOLVED A2 re-scoping via a VERIFICATION.md override (reason: dual-write + additive key achieves the anti-cliff intent without literal per-consumer gating) and flip REQUIREMENTS.md's RISK-08 checkbox + ROADMAP.md traceability row to Complete so the project's own tracking is internally consistent."
human_verification:
  - test: "Confirm whether 34-CONTEXT.md's RESOLVED A2 re-scoping of the trend-chart cutover (unconditional dual-write + additive key, no flag branch) is an ACCEPTED design pivot or an outstanding gap that needs a follow-up plan before Phase 34 / RISK-08 is considered done."
    expected: "A decision recorded (override in this VERIFICATION.md, or a new closure plan) so REQUIREMENTS.md's RISK-08 checkbox and ROADMAP.md's Phase 34 completion marker stop disagreeing with each other."
    why_human: "This is a scope/intent judgment call the phase's own context doc flags as a deliberate re-interpretation mid-phase, not a mechanical pass/fail; the project's own REQUIREMENTS.md tracking has already flagged it unresolved and no override has been recorded yet."
  - test: "Decide whether a tenant-triggerable admin path (endpoint or script) to call enqueue_backfill_job is required before a human on a live stack can actually start the RISK-07 backfill, or whether direct DB/script access is acceptable as-is."
    expected: "Either an admin endpoint/CLI script is added (mirroring the risk-cutover router's admin-gated shape) or this is explicitly accepted as an operational runbook step outside application code."
    why_human: "enqueue_backfill_job (backend/app/vulnerabilities/risk_backfill_service.py:73) is never called from any production code path, router, or script in this codebase -- only from tests. The chunk dispatcher (scheduler-wired, create_task) is fully functional once a job row exists, but nothing in the shipped code creates that row for a real tenant. This may be intentional (consistent with the milestone's accepted-debt precedent that the live backfill run itself is deferred to a human on a real stack) but is not explicitly called out as such in 34-CONTEXT.md the way the flag-flip's non-invocation is."
---

# Phase 34: Historical Recompute & Consumer Cutover — Verification Report

**Phase Goal:** Every tenant's historical data is safely, provably recomputed onto the Phase-33
risk-exposure score, every real consumer reads it (behind a flag), and cutover day produces no alert storm,
no trend cliff, and no silently reinterpreted tenant thresholds.
**Verified:** 2026-08-12T08:20:55Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | RISK-07: historical recompute is idempotent, resumable, throttled, per-tenant isolated — durable job + chunked bulk `UPDATE...FROM` + scheduler `create_task` dispatch, never a blocking Alembic migration | VERIFIED | `test_risk_recompute.py` 9/9 green (chunk correctness, idempotent re-run, kill-mid-chunk resume w/ no double-count, simulated-restart resume, per-tenant isolation, 105-row/6-pass load fixture, dispatcher non-blocking + failure-swallowing). Migration 044 confirmed additive-only (`grep op.execute` → none). `alembic heads` → single head `044_add_risk_backfill_job`. Scheduler wire confirmed `asyncio.create_task` (scheduler.py:130-170), no in-memory gate — the durable claim-row is the gate. |
| 2 | RISK-08: `sort="triage"`, trend chart, and `get_top_findings_for_ai_batch` read the new score ONLY when the flag is ON; flag defaults OFF; OFF byte-identical; SLA untouched; RBAC admin flip endpoint exists, never flipped in-env | **PARTIAL / FAILED** (trend chart sub-clause) | `sort="triage"` and `get_top_findings_for_ai_batch`: VERIFIED — both genuinely branch on `cutover_risk_exposure_scoring` (service.py:95-115, 585-600), 5/5 `test_risk_cutover.py` green, 23 pre-existing regression tests unmodified/green. SLA: VERIFIED — `grep risk_score sla_service.py` → none; `test_sla_breach_stays_severity_keyed` passes. Admin flip endpoint: VERIFIED — `POST /api/v1/risk-cutover/enable`, RBAC `require_role("admin")`, never invoked outside tests (grep confirms `cutover_risk_exposure_scoring = True` occurs nowhere except inside `enable_cutover`). **Trend chart: FAILED** — `get_risk_score_trend` has no flag branch at all; see Gaps. |
| 3 | RISK-09: pre/post `min_risk_score` diff + audited per-tenant re-tuning ack that GATES the flip (both gates: backfill-complete + fresh-ack); `rule_engine.py`/`saved_filters.py` untouched | VERIFIED | `test_risk_cutover_ack.py` 8/8 green (diff computation w/ hand-computed counts + stable hash, backfill-incomplete refusal w/ and w/o a job row, ack stamp+hash, stale-ack-after-threshold-change → 409, both-gates flip 409/409/200 across states, admin RBAC 403 for analyst/viewer). `git diff --stat` empty for `rule_engine.py`/`saved_filters.py`. Audit actions `risk_cutover.threshold_ack`/`risk_cutover.flag_enable` present in `audit.py` and called before `db.commit()` in both mutating service functions. |
| 4 | RISK-10: `DailySnapshot` dual-write is unconditional; dead `_check_risk_score_changes` fixed + version-boundary-guarded (same-version-only diffing); boundary fixture proves no storm/no cliff with a genuine-spike control | VERIFIED | `test_risk_boundary_guard.py` 5/5 green (dict-population shape, OFF genuine-spike control ≥1 alert, ON genuine-spike control ≥1 alert, boundary fixture 0 alerts despite a naive cross-version diff that would have produced a 46-point false spike, trend-continuity fixture). `grep cutover_risk_exposure_scoring trends.py` → none (dual-write genuinely unconditional). `_check_risk_score_changes` (alerts.py:185-255) reads the flag once and picks matched `(metrics_key, score_column)` pairs, never crossing versions. `test_severity_trends.py` + `test_dashboard_tiles.py` regress clean (8/8). |

**Score:** 3.5/4 truths verified (RISK-07, RISK-09, RISK-10 fully verified; RISK-08 verified for 2 of its 3 named consumers + SLA + admin endpoint, failed for the trend-chart consumer)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/alembic/versions/044_add_risk_backfill_job.py` | New job table + 3 Tenant columns, purely additive | VERIFIED | Read in full: `op.create_table("risk_exposure_backfill_jobs", ...)` + 3 `op.add_column` on tenants; symmetric `downgrade()`; zero `op.execute`; revision id 25 chars ≤32; `down_revision = "043_index_risk_exposure_score"`; `alembic heads` confirms single head. |
| `backend/app/vulnerabilities/models.py::RiskExposureBackfillJob` | Durable per-tenant job row | VERIFIED | Matches interfaces block verbatim (status String(20), cursor_vuln_id, rows_migrated, chunk_size, heartbeat, UniqueConstraint(tenant_id)). |
| `backend/app/tenants/models.py` (3 new columns) | `cutover_risk_exposure_scoring` (default False, REAL branch) + 2 ack columns | VERIFIED | `default=False, server_default="false"`; comment block documents the "real branch not inert stub" distinction. |
| `backend/app/vulnerabilities/risk_backfill_service.py` | enqueue/process_chunk/dispatch, single scoring source reused | VERIFIED (wiring caveat) | Full read: claim-row → keyset select → `score_finding` reuse (verbatim import, no re-implementation: `grep "def score_finding\|WEIGHT_"` → none) → bulk `UPDATE...FROM` w/ per-value CAST → cursor/heartbeat advance, one transaction, `db.expire_all()` post-commit. **`enqueue_backfill_job` is never called from any production code path** (only from tests) — see Human Verification #2. |
| `backend/app/connectors/scheduler.py::_dispatch_risk_exposure_backfill` | `create_task` wire, no in-memory gate | VERIFIED | Lines 130-170; wraps `dispatch_backfill_chunks` in `asyncio.create_task`; called via plain `await` at scheduler.py:382 (matches Plan 01's documented dispatcher-internally-create_tasks shape). |
| `backend/app/vulnerabilities/service.py` (sort="triage" + AI batch) | Flag-gated branch, OFF byte-identical | VERIFIED | Both branches confirmed by direct read (lines 95-115, 560-600); Tenant fetch once per call, tenant-scoped. |
| `backend/app/vulnerabilities/risk_cutover_service.py` + `risk_cutover_router.py` | diff/ack/enable + 3 admin endpoints | VERIFIED | Full read; both-gates enforcement, gate-specific 409 details, audit-before-commit on both mutations; router wired in `main.py:322`. |
| `backend/app/vulnerabilities/trends.py` (dual-write + trend read) | Unconditional dual-write; continuity-aware trend read | PARTIAL | Dual-write: VERIFIED unconditional (grep confirms no flag reference). Trend read (`get_risk_score_trend`): exposes both series unconditionally but has **no flag branch** — see gap above. |
| `backend/app/notifications/alerts.py::_check_risk_score_changes` | Dead-code fix + version-boundary branch | VERIFIED | Full read; flag read once, matched metrics_key/score_column pair, never cross-version. |
| `backend/tests/test_risk_recompute.py` | RISK-07 fixture suite | VERIFIED | 9/9 passed (isolated run). |
| `backend/tests/test_risk_cutover.py` | RISK-08 fixture suite | VERIFIED | 5/5 passed (isolated run). |
| `backend/tests/test_risk_cutover_ack.py` | RISK-09 fixture suite | VERIFIED | 8/8 passed (isolated run). |
| `backend/tests/test_risk_boundary_guard.py` | RISK-10 fixture suite | VERIFIED | 5/5 passed (isolated run). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `scheduler._scheduler_loop` | `risk_backfill_service.dispatch_backfill_chunks` | `asyncio.create_task` | WIRED | Confirmed in scheduler.py:130-170,382. |
| `risk_backfill_service.process_backfill_chunk` | `risk_exposure_service.score_finding` | direct call, reused inputs | WIRED | Confirmed at risk_backfill_service.py:214-229; no second scorer (grep clean). |
| `service.py::list_vulnerabilities` / `get_top_findings_for_ai_batch` | `tenants.cutover_risk_exposure_scoring` | scalar Tenant fetch, branch order_by | WIRED | Confirmed at service.py:95-115, 585-600. |
| `risk_cutover_service.enable_cutover` | `risk_exposure_backfill_jobs.status` + `tenants.risk_cutover_threshold_ack_*` | both-gates check before flip | WIRED | Confirmed at risk_cutover_service.py:168-211. |
| `trends.capture_daily_snapshot` | `DailySnapshot.metrics[asset_risk_scores / asset_risk_exposure_scores]` | unconditional bulk fetch | WIRED | Confirmed at trends.py:290-330. |
| `alerts._check_risk_score_changes` | `tenants.cutover_risk_exposure_scoring` + matching-version snapshot dict | flag read once, matched pair | WIRED | Confirmed at alerts.py:185-255. |
| `trends.get_risk_score_trend` | `tenants.cutover_risk_exposure_scoring` | flag-gated series selection | **NOT_WIRED** | No such branch exists — the function is flag-blind by design (34-CONTEXT RESOLVED A2 pivot); see gap. |
| `risk_backfill_service.enqueue_backfill_job` | any router/script/admin trigger | — | **NOT_WIRED (orphaned in production)** | Only called from tests; no production call site. Flagged as human-verification item, not a blocker (consistent with accepted-debt precedent for the live run itself). |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|--------------|------------|-------------|--------|----------|
| RISK-07 | 34-01 | Idempotent/resumable/throttled/per-tenant-isolated backfill | SATISFIED | 9/9 tests, migration/scheduler grep gates all pass. |
| RISK-08 | 34-02 (+34-04 partial) | sort/trend/AI-batch cutover, SLA untouched, severity-tier centralized | **BLOCKED (partial)** | sort="triage" + AI-batch: satisfied. Severity-tier centralization: satisfied (Phase 33, cited via grep in export.py/assets/router.py/dashboard.py). Trend-chart cutover: NOT satisfied — no flag branch. REQUIREMENTS.md itself still shows `[ ]` Pending for RISK-08, corroborating this finding independent of this verifier's own read. |
| RISK-09 | 34-03 | Diff + ack gates the flip | SATISFIED | 8/8 tests, both-gates enforcement confirmed by direct code read. |
| RISK-10 | 34-04 | Unconditional dual-write, dead-code fix, version-boundary guard | SATISFIED | 5/5 tests, dead-code bug genuinely reproduced pre-fix and fixed, non-zero control proves the check fires before trusting the boundary-zero result. |

**Orphaned requirements:** None — all 4 (RISK-07..10) are claimed by exactly one plan each (RISK-08 additionally touched by 34-04's boundary-guard work, consistent with the phase's own cross-plan design).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/app/vulnerabilities/trends.py` | 166-188 | Missing flag branch where one was implied by 34-CONTEXT.md's original "three real cutover consumers" framing | ⚠️ Warning | Trend chart is not literally "cut over" behind the flag — dual-exposure only. Not a stub/placeholder (real data, real computation), but not the same cutover mechanism as the other two consumers. |
| `backend/app/vulnerabilities/risk_backfill_service.py` | 73 (`enqueue_backfill_job`) | Dead production code path (function exists, fully correct, never called outside tests) | ℹ️ Info | Not a stub — the function is real and fixture-proven. But no operational trigger exists in this codebase for a human to actually start a tenant's backfill. |

No blocker-level anti-patterns (no placeholder returns, no empty handlers, no TODO/FIXME in the touched files).

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| RISK-07 suite | `pytest tests/test_risk_recompute.py` (isolated) | 9 passed | ✓ PASS |
| RISK-08 suite | `pytest tests/test_risk_cutover.py` (isolated) | 5 passed | ✓ PASS |
| RISK-09 suite | `pytest tests/test_risk_cutover_ack.py` (isolated) | 8 passed | ✓ PASS |
| RISK-10 suite | `pytest tests/test_risk_boundary_guard.py` (isolated) | 5 passed | ✓ PASS |
| Flag-OFF regression (vulnerabilities/SLA/AI-batch) | `pytest tests/test_vulnerabilities.py tests/test_sla_service.py tests/test_top_findings_for_ai_batch.py` | 23 passed | ✓ PASS |
| Trend/dashboard regression | `pytest tests/test_severity_trends.py tests/test_dashboard_tiles.py` | 8 passed | ✓ PASS |
| Pre-existing hang isolation check | `pytest tests/test_risk_exposure_service.py` (isolated) | 12 passed | ✓ PASS (confirms documented hang is a cross-file scheduler-lifespan hazard, not a Phase 34 regression) |
| Single alembic head | `alembic heads` | `044_add_risk_backfill_job (head)` | ✓ PASS |
| No op.execute in migration 044 | `grep op.execute 044_add_risk_backfill_job.py` | no output | ✓ PASS |
| No risk_score read in sla_service.py | `grep "risk_score\|risk_exposure_score" sla_service.py` | no output | ✓ PASS |
| Trend dual-write unconditional | `grep cutover_risk_exposure_scoring trends.py` | no output | ✓ PASS |
| Flag set True only inside enable_cutover | `grep "cutover_risk_exposure_scoring = True" app/` | only risk_cutover_service.py:199 (inside `enable_cutover`) | ✓ PASS |
| Severity-tier centralization (Phase 33 citation) | `grep RISK_SCORE_TIER_ app/assets/risk_score.py app/export.py app/assets/router.py app/vulnerabilities/dashboard.py` | single-source constants imported in all 3 consumer files | ✓ PASS |

### Human Verification Required

See frontmatter `human_verification` — two items:
1. Whether the trend-chart cutover re-scoping (34-CONTEXT RESOLVED A2) is an accepted pivot (needs an override + REQUIREMENTS.md/ROADMAP.md reconciliation) or an outstanding gap requiring a follow-up plan.
2. Whether a production trigger path for `enqueue_backfill_job` (admin endpoint or script) is required before this phase's backfill machinery can actually be used on a live stack, or whether direct DB/script access is an acceptable operational answer.

### Gaps Summary

Three of the phase's four requirements (RISK-07, RISK-09, RISK-10) are fully and rigorously verified: all four fixture suites pass in isolation (27 tests total), the migration is clean and additive with a single alembic head, the scheduler dispatch is genuinely non-blocking and durable, the diff+ack gate structurally prevents a silent threshold reinterpretation, and the boundary-guard fixture proves both a real non-zero spike control and a zero-alert/continuous-trend boundary case — the milestone's stated highest-risk mechanics hold up under direct code and test scrutiny, not just SUMMARY claims.

RISK-08 is mostly solid — the two consumers that were fully implemented (`sort="triage"`, `get_top_findings_for_ai_batch`) are correctly flag-gated, fixture-proven byte-identical when OFF, and existing regression suites (23 tests) stayed green and unmodified. SLA is confirmed untouched and severity-tier centralization is confirmed already-landed from Phase 33. However, the third named consumer — the trend chart — was re-scoped mid-phase (documented in 34-CONTEXT.md) from "flag-gated cutover" to "unconditional dual-write + boundary guard," and that re-scoping was never carried through to a literal flag branch anywhere in the trend-read path. This is not a fabricated finding: the project's own REQUIREMENTS.md still has RISK-08 unchecked, and the 34-02 commit message explicitly names this exact gap as open, pending Plan 04. Plan 04 closed RISK-10's boundary-guard mechanics but did not add the missing trend-chart flag branch, so the self-acknowledged gap remains open even though ROADMAP.md now marks the whole phase `[x]` complete — an internal inconsistency in the project's own tracking that this verification surfaces rather than silently accepting.

This finding is presented as an Escalation Gate item: the underlying engineering (dual-write, continuity, no-cliff) is genuinely sound and arguably achieves the more important safety property RISK-10 was chasing, but it does not literally satisfy RISK-08's "trend chart reads the new score ONLY when the flag is ON" clause. A human should decide whether to (a) accept this via an explicit override and reconcile REQUIREMENTS.md/ROADMAP.md, or (b) request a small follow-up plan to add the missing flag branch to the trend-chart read path.

---

_Verified: 2026-08-12T08:20:55Z_
_Verifier: Claude (gsd-verifier)_
