---
phase: 37
slug: two-way-ticket-sync-remediation-verification
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-14
---

# Phase 37 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from RESEARCH.md ## Validation Architecture + the PLAN task IDs.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3 + pytest-asyncio 0.24 (`asyncio_mode="auto"`) |
| **Config file** | backend/pyproject.toml (`[tool.pytest.ini_options]`, `testpaths=["tests"]`) |
| **Quick run command** | `cd backend && ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())") JWT_SECRET_KEY=test-secret uv run pytest tests/test_<file>.py -x` (per-file — see memory: getvul-backend-pytest-env) |
| **Full suite command** | run per-file across the phase's files (whole `tests/` dir gives false failures) |
| **Estimated runtime** | ~30–90 seconds per file |

---

## Sampling Rate

- **After every task commit:** run the single new test file for that task (`-x`).
- **After every plan wave:** run all Phase 37 test files, per-file.
- **Phase gate:** all Phase 37 files green + a targeted rerun of the shared-path guards (`test_mttr.py`, `test_sla_tier_service.py`) so the `verified_by` extension didn't break existing REMEDIATED/MTTR callers.
- **Max feedback latency:** 90 seconds.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 37-01-T1 | 01 | 1 | SYNC-02 | T-37-01/04 | `clean_scan_streak` column (migration 048 chained off 047, Integer NOT NULL server_default "0"); `mark_vulnerability_remediated` extended with keyword-only `verified_by` (no sibling writer; MTTR/RemediationEvent unforked) | unit+db | `pytest tests/test_rescan_autoclose.py -x -k "migration or streak_default or verified_by or helper_regression"` | ❌ W0 | ⬜ pending |
| 37-01-T2 | 01 | 1 | SYNC-02 | T-37-01/02/03/04 | Absent-sweep runs ONLY in `run_sync` SUCCESS branch (FAILED/partial never advances a streak — D-02); auto-close at streak==2 via the single helper; system-actor `AuditLog(tenant_id=vuln.tenant_id, user_email="system:rescan-verify")`; tenant+source scoped | unit+db | `pytest tests/test_rescan_autoclose.py -x` | ❌ W0 | ⬜ pending |
| 37-02-T1 | 02 | 2 | SYNC-03 | T-37-05/06/07 | `reopen_vulnerability` soft-close resurrection: clears `remediated_at`, resets streak, preserves `first_detected_at` + historical RemediationEvent (MTTR lineage); direct system AuditLog | unit+db | `pytest tests/test_finding_reopen.py -x -k "reopen_helper or preserves or noop"` | ❌ W0 | ⬜ pending |
| 37-02-T2 | 02 | 2 | SYNC-03 | T-37-05 | Recurrence routes to the SAME row via `uq_vuln_dedup(tenant, cve, asset, source)` in `_upsert_vulnerability`; finding COUNT stays 1, no duplicate ticket | db | `pytest tests/test_finding_reopen.py -x` | ❌ W0 | ⬜ pending |
| 37-03-T1 | 03 | 2 | SYNC-01 | T-37-08/09 | D-03 split: DELETE the 3 premature `mark_vulnerability_remediated` calls (daily_sync.py:249/337/431); whitelist status map → done ticket sets IN_PROGRESS + comment, NEVER REMEDIATED; unknown payload = no-op+log | unit | `pytest tests/test_ticket_status_sync.py -x -k "map_status or reopen_issue or unknown"` | ❌ W0 | ⬜ pending |
| 37-03-T2 | 03 | 2 | SYNC-03 | T-37-09 | External-ticket reopen on recurrence per provider (GitHub `reopen_issue` PATCH state=open, Jira `transition`, Asana `update_task(completed=False)`) + re-comment (D-04) | unit | `pytest tests/test_ticket_status_sync.py -x` | ❌ W0 | ⬜ pending |
| 37-03-T3 | 03 | 2 | SYNC-04 | T-37-10/11/12/13 | Bounded retry + per-connector isolation; `last_sync_*` set per poll; `_sanitize_error` redaction into `last_error`; failed poll loses no data and never advances a scanner streak | unit | `pytest tests/test_ticket_sync_resilience.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_rescan_autoclose.py` — SYNC-02 streak, SUCCESS-only gating, FAILED-guard, migration 048, `verified_by` helper regression
- [ ] `backend/tests/test_finding_reopen.py` — SYNC-03 same-row reopen via dedup key + MTTR/history preserved + no-duplicate
- [ ] `backend/tests/test_ticket_status_sync.py` — SYNC-01 status map + D-03 (done ticket → IN_PROGRESS, never REMEDIATED) + per-provider reopen
- [ ] `backend/tests/test_ticket_sync_resilience.py` — SYNC-04 retry/backoff + `last_sync_*` + `_sanitize_error`
- [ ] Migration parity test — mirror `tests/test_ticket_migrations.py` for 048
- [ ] Shared fixtures: scanner sync harness (SUCCESS/FAILED), OPEN-finding+closed-ticket seed, mock provider HTTP (httpx mock, per `test_ticketing_clients.py`)

*Frameworks already present (pytest, pytest-asyncio) — no install needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real provider status round-trip (Jira/Asana/GitHub) | SYNC-01/03 | Live provider status change → poll → finding update cannot be asserted in CI without live creds (CI covers it against mocked httpx) | In a scratch tenant, move a real linked ticket to Done, run the sync pass, confirm the finding goes IN_PROGRESS (not REMEDIATED) and the comment posts |

*All in-app behaviors have automated verification (mocked-provider); the row above is a live-creds confirmation only.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (7/7 carry a concrete pytest command)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (test files created RED-first during execution)
- [x] No watch-mode flags (all targeted `-x` per-file)
- [x] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter (flip at validate-phase once Wave 0 files exist green)

**Approval:** pending (execution-time — plan-time validation strategy is sound per gsd-plan-checker 8a–8d PASS)
