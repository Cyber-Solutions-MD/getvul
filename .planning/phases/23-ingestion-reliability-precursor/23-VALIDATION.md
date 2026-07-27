---
phase: 23
slug: ingestion-reliability-precursor
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-27
---

# Phase 23 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-asyncio (backend); Vitest 4.x + React Testing Library (frontend) |
| **Config file** | `backend/pytest.ini` (backend); `frontend/vitest.config.ts` (frontend) |
| **Quick run command (backend)** | `cd backend && export ENCRYPTION_KEY=$(.venv/bin/python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())") JWT_SECRET_KEY=$(.venv/bin/python -c "import secrets;print(secrets.token_urlsafe(48))") ENVIRONMENT=development && .venv/bin/pytest tests/<file>.py -v` |
| **Quick run command (frontend)** | `cd frontend && npm run test -- <pattern>` |
| **Full suite command** | Per-file iteration (NO single "run everything" — see caveat below). Backend: iterate `tests/*.py` individually excluding `test_rate_limit.py` + the Docker-only `test_snooze.py::test_snooze_fails_closed_when_audit_write_fails`. Plus `ruff check . && ruff format --check . && (mypy app/ \| mypy-baseline filter --allow-unsynced)` |
| **Estimated runtime** | ~5–30s per backend test file; ~5–15s per frontend component pattern |

**Mandatory backend invocation caveat (project memory `getvul-backend-pytest-env`):** always export `ENCRYPTION_KEY` + `JWT_SECRET_KEY` and run **per-file**, never `pytest tests/`. Full-suite runs cause cross-test DB contamination (order-dependent false failures). REL-03's `test_connectors/` files are pure `httpx.MockTransport` unit tests with no DB fixture, so the caveat matters most for the DB-touching integration files (`test_ticketing_dispatch.py`, `test_github_sync.py`, `test_connector_health.py`).

---

## Sampling Rate

- **After every task commit:** Run the specific new/modified test file (`pytest tests/<file>.py -v` or `npm run test -- <component>`).
- **After every plan wave:** Run every file touched in that wave individually (per-file isolation), plus `ruff check . && ruff format --check . && mypy | mypy-baseline filter`.
- **Before `/gsd-verify-work`:** All six `test_connectors/test_*_connector.py` + `test_ticketing_dispatch.py` + `test_github_sync.py` + `test_connector_health.py` + `test_ticketing_clients.py` green (per-file); frontend `sync-status-pill` + `connector-card` + `ticket-provider-picker` green; `tsc --noEmit` clean; migration applies (`alembic upgrade head`).
- **Max feedback latency:** ~30 seconds (single file).

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 23-01-01 | 01 | 2 | REL-01, REL-03 | T-23-02 | Wiz auth returns True; no secret in log | unit (MockTransport) | `pytest tests/test_connectors/test_wiz_connector.py -v` | ❌ W0 (created here) | ⬜ pending |
| 23-01-02 | 01 | 2 | REL-02, REL-03 | T-23-03 | Rapid7 constructs no-arg + auth True | unit (MockTransport) | `pytest tests/test_connectors/test_rapid7_connector.py -v` | ❌ W0 (created here) | ⬜ pending |
| 23-01-03 | 01 | 2 | REL-02 (hardening) | T-23-01 | TLS verify defaults ON at all 4 sites | unit + grep | `grep -rn "verify=False" app/connectors/{rapid7,nessus,tester}.py` == 0 + `pytest tests/test_connectors/test_rapid7_connector.py -v` | ❌ W0 (created here) | ⬜ pending |
| 23-02-01 | 02 | 3 | REL-03 | T-23-04 | Pins current 429 behavior, no silent change | unit (MockTransport) | `pytest tests/test_connectors/test_crowdstrike_connector.py -v` | ❌ W0 (created here) | ⬜ pending |
| 23-02-02 | 02 | 3 | REL-03 | T-23-04 | Pins MAX_RETRIES=3 | unit (MockTransport) | `pytest tests/test_connectors/test_defender_connector.py -v` | ❌ W0 (created here) | ⬜ pending |
| 23-02-03 | 02 | 3 | REL-03 | T-23-05 | Nessus verify_tls default True; Qualys 409 pinned | unit (MockTransport) | `pytest tests/test_connectors/test_nessus_connector.py tests/test_connectors/test_qualys_connector.py -v` | ❌ W0 (created here) | ⬜ pending |
| 23-03-01 | 03 | 1 | REL-04, REL-05 | T-23-06 | Enum-gated provider; no token in logs | import smoke + tsc | `python -c "from app.ticketing.dispatch import build_ticketing_client"` + `tsc --noEmit` | N/A | ⬜ pending |
| 23-03-02 | 03 | 1 | REL-04 | T-23-07 | No broken import after JiraClient delete | unit (MockTransport) | `grep -rn "app.connectors.jira_client" backend/` == 0 + `pytest tests/test_ticketing_clients.py -v` | ⚠️ extend | ⬜ pending |
| 23-03-03 | 03 | 1 | REL-05 | T-23-08 | GitHub close/comment added | unit (MockTransport) | `pytest tests/test_ticketing_clients.py -v` | ⚠️ extend | ⬜ pending |
| 23-04-01 | 04 | 2 | REL-04, REL-05 | T-23-11 | provider drives destination (data integrity) | integration (DB + MockTransport) | `pytest tests/test_ticketing_dispatch.py -v` | ❌ W0 (created here) | ⬜ pending |
| 23-04-02 | 04 | 2 | REL-04 | T-23-12 | rule provider enum-coerced; default ASANA | integration | `pytest tests/test_ticketing_dispatch.py -v` | ❌ W0 | ⬜ pending |
| 23-04-03 | 04 | 2 | REL-04 | T-23-09, T-23-10 | configured-providers endpoint tenant-scoped | integration | `pytest tests/test_ticketing_dispatch.py -v` | ❌ W0 | ⬜ pending |
| 23-05-01 | 05 | 3 | REL-05 | T-23-13 | GitHub token stored encrypted, not plaintext config | unit + import smoke | `python -c "...assert 'GITHUB' in SPECIAL_CONNECTORS and 'GITHUB' in CONNECTOR_TYPES"` + `pytest tests/test_github_sync.py -v` | ❌ W0 (created here) | ⬜ pending |
| 23-05-02 | 05 | 3 | REL-05 | T-23-14, T-23-15 | tenant-scoped GitHub sync; issue state enum-checked | integration (MockTransport) | `pytest tests/test_github_sync.py -v` | ❌ W0 | ⬜ pending |
| 23-06-01 | 06 | 1 | REL-06 | T-23-17 | Additive migration, safe backfill (server_default 0) | migration + import smoke | `alembic upgrade head` + `python -c "assert hasattr(ConnectorConfig,'last_error')"` | N/A | ⬜ pending |
| 23-06-02 | 06 | 1 | REL-06 | T-23-16 | status normalized at wire boundary | unit | `python -c "from app.connectors.service import _normalize_sync_status as n; assert n('SUCCESS')=='ok'"` | N/A | ⬜ pending |
| 23-06-03 | 06 | 1 | REL-06 | T-23-16 | Pill non-crashing on real + unexpected values | component (Vitest) | `npm run test -- sync-status-pill connector-card` | ⚠️ correct existing (masks bug) | ⬜ pending |
| 23-07-01 | 07 | 4 | REL-06 | T-23-19, T-23-20 | counter increment/reset; secret redacted from last_error | unit + integration | `pytest tests/test_connector_health.py -v` | ❌ W0 (created here) | ⬜ pending |
| 23-07-02 | 07 | 4 | REL-06 | T-23-21 | scheduler parity, single implementation | integration | `pytest tests/test_connector_health.py -v` | ❌ W0 | ⬜ pending |
| 23-08-01 | 08 | 3 | REL-04 | T-23-22 | providers list tenant-scoped (server-enforced) | component (Vitest) | `npm run test -- ticket-provider-picker` | ❌ W0 (created here) | ⬜ pending |
| 23-08-02 | 08 | 3 | REL-04 | T-23-24 | empty state deep-links; all 3 states present | component (Vitest) | `npm run test -- ticket-provider-picker` | ❌ W0 | ⬜ pending |
| 23-08-03 | 08 | 3 | REL-04 | T-23-23 | chosen provider re-validated server-side | tsc + grep | `tsc --noEmit` + `grep -n "TicketProviderPicker" drill-content.tsx` | N/A | ⬜ pending |
| 23-09-01 | 09 | 2 | REL-06 | T-23-25, T-23-26 | last_error rendered as plain text; AA contrast token | component (Vitest) | `npm run test -- connector-card` | ⚠️ extend (Plan 06 corrected) | ⬜ pending |
| 23-09-02 | 09 | 2 | REL-06 | — | derived next-sync, frozen-clock tested | component (Vitest) | `npm run test -- connector-card` | ⚠️ extend | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Nyquist continuity check:** every task above has an `<automated>` command; no run of 3 consecutive tasks lacks automated verification. ✅

---

## Wave 0 Requirements

Test files are authored RED-first inside each owning plan's first `tdd="true"` task (the six precedent MockTransport files define their helpers locally — there is no shared `conftest`, matching house convention, so no separate Wave-0 fixture plan is needed).

New backend test files (created by the owning plan/task):
- [ ] `backend/tests/test_connectors/test_wiz_connector.py` — REL-01, REL-03 (Plan 01 T1)
- [ ] `backend/tests/test_connectors/test_rapid7_connector.py` — REL-02, REL-03, verify_tls (Plan 01 T2/T3)
- [ ] `backend/tests/test_connectors/test_crowdstrike_connector.py` — REL-03 (Plan 02 T1)
- [ ] `backend/tests/test_connectors/test_defender_connector.py` — REL-03 (Plan 02 T2)
- [ ] `backend/tests/test_connectors/test_nessus_connector.py` — REL-03 + verify_tls (Plan 02 T3)
- [ ] `backend/tests/test_connectors/test_qualys_connector.py` — REL-03 (Plan 02 T3)
- [ ] `backend/tests/test_ticketing_dispatch.py` — REL-04, REL-05 (Plan 04, all three create paths × three providers + rule engine + endpoint)
- [ ] `backend/tests/test_github_sync.py` — REL-05 (Plan 05, registration + daily_sync GitHub branch + auto-close)
- [ ] `backend/tests/test_connector_health.py` — REL-06 (Plan 07, counter increment/reset + redaction + truncation + scheduler parity)

Extend existing backend test file:
- [ ] `backend/tests/test_ticketing_clients.py` — Jira comment/transition + GitHub add_comment/close_issue (Plan 03 T2/T3)

Correct existing frontend test files (they currently assert the fictional `'ok'`/`'failed'` values the backend never emits — the bug-masking cases MUST be rebuilt against real values, not merely extended):
- [ ] `frontend/src/components/connectors/sync-status-pill.test.tsx` — real backend values + raw-value guard (Plan 06 T3)
- [ ] `frontend/src/components/connectors/connector-card.test.tsx` — real values + new fields (Plan 06 T3), then error/next-sync/failure-count cases (Plan 09)

New frontend test file:
- [ ] `frontend/src/components/vulnerabilities/ticket-provider-picker.test.tsx` — all four states (Plan 08 T2)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| End-to-end create → real Jira/GitHub ticket via the drill-panel picker | REL-04, REL-05 | Needs a real tenant with configured Jira/GitHub credentials (BYOK — no creds in CI) | With a Jira connector configured, open a vuln drill panel → Create ticket → pick Jira → confirm; verify a Jira issue is created and `Ticket.provider=='JIRA'`. Backend dispatch is fully covered by `test_ticketing_dispatch.py` under MockTransport; only the live-credential smoke is manual. |
| Connectors page renders without crash for a connector that has actually synced | REL-06 | The masking bug only surfaces with real (non-null) `last_sync_status` seeded data | Seed/observe a connector with a completed sync; load the Connectors page; confirm SyncStatusPill renders (no React render error). Automated regression exists in `sync-status-pill.test.tsx` (raw-value guard). |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (nine new + one extended backend file; two corrected + one new frontend file)
- [x] No watch-mode flags (Vitest invoked via `npm run test -- <pattern>`, single-run; pytest per-file)
- [x] Feedback latency < 30s (single file)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-27
