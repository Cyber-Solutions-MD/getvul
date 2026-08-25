---
phase: 40
slug: proactive-alerting-digests
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-19
---

# Phase 40 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend) + vitest (frontend) |
| **Config file** | backend/pyproject.toml (pytest) / frontend vitest config |
| **Quick run command** | `ENCRYPTION_KEY=... JWT_SECRET_KEY=... pytest backend/tests/test_alerts_kev_epss.py` (per-file — see backend pytest env memory) |
| **Full suite command** | `ENCRYPTION_KEY=... JWT_SECRET_KEY=... pytest backend/tests/` |
| **Estimated runtime** | ~60 seconds |

---

## Sampling Rate

- **After every task commit:** Run the affected per-file test (`pytest backend/tests/test_<file>.py`)
- **After every plan wave:** Run the full backend suite + affected vitest tests
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

> Seeded by plan-phase; the planner/executor fill exact task IDs and commands during planning/execution.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 40-01-01 | 01 | 1 | ALERT-01/02/03 | T-40-01 | Guard-table one-way-door schema approval | checkpoint:decision | (human gate — no automated cmd) | — | ⬜ pending |
| 40-01-02 | 01 | 1 | ALERT-01/02/03 | T-40-01,02 | Reversible non-destructive migration; secret-free config schema | migration | `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` | ❌ W0 | ⬜ pending |
| 40-01-03 | 01 | 1 | ALERT-01/02/03 | — | RED test scaffolds collect (incl. test_newly_critical_section_content) | unit (scaffold) | `pytest backend/tests/test_alerts_kev_epss.py tests/test_digests.py tests/test_alerting_settings.py --collect-only -q` | ❌ W0 | ⬜ pending |
| 40-02-01 | 02 | 2 | ALERT-01 | T-40-04,05 | KEV/EPSS qualifier + D-20 exclusion + guard subtraction + seed-silent | unit | `pytest backend/tests/test_alerts_kev_epss.py -k "fires_once or refire or seeds or excluded" -x` | ❌ W0 | ⬜ pending |
| 40-02-02 | 02 | 2 | ALERT-01 | T-40-06,07 | Owner resolution, channel push, in-app twin, scheduler audit | unit | `pytest backend/tests/test_alerts_kev_epss.py -x` | ❌ W0 | ⬜ pending |
| 40-03-01 | 03 | 3 | ALERT-02 | T-40-09 | send_email html multipart/alternative, non-raising contract | unit | `pytest backend/tests/test_digests.py -k html -x` | ❌ W0 | ⬜ pending |
| 40-03-02 | 03 | 3 | ALERT-02 | T-40-09,10,11,12 | Send-hour gate, 4-section assembly (incl. newly-critical), D-20 exclusion, HTML escaping, owner/team routing, empty-suppress | unit | `pytest backend/tests/test_digests.py -x` | ❌ W0 | ⬜ pending |
| 40-03-03 | 03 | 3 | ALERT-02 | T-40-11 | Fail-isolated scheduler digest-dispatch block | unit + syntax | `pytest backend/tests/test_digests.py -x && python -c "import ast; ast.parse(open('app/connectors/scheduler.py').read())"` | ❌ W0 | ⬜ pending |
| 40-04-01 | 04 | 4 | ALERT-03 | T-40-02 | AlertingConfigUpdate bounds gate, PATCH branch, GET exposure, audit | unit | `pytest backend/tests/test_alerting_settings.py -k "validates or persists or audited or owner" -x` | ❌ W0 | ⬜ pending |
| 40-04-02 | 04 | 4 | ALERT-03 | T-40-13 | POST /settings/alerting/test-digest preview (empty vs error distinguishable) | unit | `pytest backend/tests/test_alerting_settings.py -x` | ❌ W0 | ⬜ pending |
| 40-05-01 | 05 | 5 | ALERT-03 | — | alerting-digests-pane renders sections + RBAC gate + no-channels EmptyState | component (vitest) | `npx vitest run alerting-digests-pane` | ❌ W0 | ⬜ pending |
| 40-05-02 | 05 | 5 | ALERT-03 | — | Pane registered in microcopy + sidebar shell (admin-only) + page routing | component + typecheck | `npx tsc --noEmit && npx vitest run settings-sidebar-shell` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_alerts_kev_epss.py` — stubs for ALERT-01 (new-KEV / high-EPSS asset-match firing)
- [ ] `backend/tests/test_digests.py` — stubs for ALERT-02 (scheduled digest delivery, send-hour gate, SLA due/breaching content)
- [ ] `backend/tests/test_alerting_settings.py` — stubs for ALERT-03 (tenant-configurable rules/channels + audit)
- [ ] Frontend vitest test for the alerting settings pane / digest surfaces
- [ ] Shared fixtures for tenant + asset + enrichment seeding (extend existing conftest)

*Note: no `test_alerts.py` exists today — Wave 0 must create the alerting test files.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real Slack/Teams/email message actually renders/delivers to a live channel | ALERT-01, ALERT-02 | External delivery to third-party services can't be asserted in unit tests (dispatch is SSRF-guarded + mocked in tests) | Configure a real channel in a test tenant, trigger an alert/digest, confirm receipt and formatting |

*Automated tests assert dispatch fan-out, payload shape, and gating; live delivery is manual.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
