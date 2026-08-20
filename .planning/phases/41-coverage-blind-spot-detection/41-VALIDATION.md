---
phase: 41
slug: coverage-blind-spot-detection
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: validated
nyquist_compliant: true
wave_0_complete: false
created: 2026-08-20
---

# Phase 41 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Transcribed from 41-RESEARCH.md "## Validation Architecture" (verified against every plan's `<verify><automated>` command).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (`asyncio_mode = "auto"`) backend · Vitest frontend · Playwright e2e |
| **Config file** | `backend/pyproject.toml [tool.pytest.ini_options]` · `frontend/vitest.config.mts` · `frontend/e2e/playwright.config.ts` |
| **Quick run command** | backend: `cd backend && ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())") JWT_SECRET_KEY=test-secret python -m pytest tests/test_coverage.py -x -q` · frontend: `cd frontend && npm test -- coverage` |
| **Full suite command** | `make test` (repo root) + `cd frontend && npm test && npm run lint` |
| **Estimated runtime** | ~30 s quick (per-file) · ~3–5 min full suite |

**Env note (MEMORY.md `getvul-backend-pytest-env`):** always set `ENCRYPTION_KEY`/`JWT_SECRET_KEY` and run backend tests **per-file** (`tests/test_coverage.py`), never the whole `tests/` dir — whole-dir runs produce false failures.

---

## Sampling Rate

- **After every task commit:** Run the relevant quick-run command (backend per-file `-x`; frontend `npm test -- coverage`)
- **After every plan wave:** Run `pytest tests/test_coverage.py -x` (full file) + `cd frontend && npm test -- coverage`
- **Before `/gsd-verify-work`:** Full suite green — `make test` + `cd frontend && npm test && npm run lint` + `npm run test:e2e` (extend `frontend/e2e/a11y-routes.spec.ts` per-route pattern, or add `coverage.spec.ts`, so `/dashboard/coverage` gets ≥1 smoke + axe pass)
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 41-01-01 | 01 | 1 | COV-01 | IDOR (tenant-scoped list) | Blind-spot query returns authoritative-but-never-scanned assets, tenant-scoped; excludes scanner-touched + ignored | integration | `pytest tests/test_coverage.py::test_blind_spot_list -x` | ❌ W0 | ⬜ pending |
| 41-01-02 | 01 | 1 | COV-01 | — | `/dashboard/coverage` renders blind-spot table + D-11 no-inventory empty state + "quiet win" all-covered empty state | component | `npm test -- coverage/page` | ❌ W0 | ⬜ pending |
| 41-02-01 | 02 | 1 | COV-01 | cross-tenant write | Intune `SyncLog` uses `connector_id` + required `tenant_id` (no stale `connector_config_id`) | source | `python -c "src=open('app/connectors/intune_sync.py').read(); assert 'connector_config_id' not in src; assert 'connector_id=connector_config.id' in src; assert 'tenant_id=connector_config.tenant_id' in src"` | N/A (source) | ⬜ pending |
| 41-02-02 | 02 | 1 | COV-01 | cross-tenant write | Intune sync upserts assets tenant-scoped; sync succeeds end-to-end | integration | `pytest tests/test_intune_sync.py -x` | ❌ W0 | ⬜ pending |
| 41-03-01 | 03 | 2 | COV-02 | — | Coverage % = `covered/total`; division-by-zero → `null` (never crash / misleading 0%); stale flag fires at >7 days, not exactly 7 (D-06 boundary) | unit | `pytest tests/test_coverage.py::test_coverage_percentage -x && pytest tests/test_coverage.py::test_stale_threshold_boundary -x` | ❌ W0 | ⬜ pending |
| 41-03-02 | 03 | 2 | COV-02 | — | `last_sync_status` wire-normalized before the coverage card (Pitfall 3 regression guard) | component | `npm test -- coverage` | ❌ W0 | ⬜ pending |
| 41-04-01 | 04 | 3 | COV-03 | RBAC (D-08 asymmetric) · IDOR | Owner resolves → email + `coverage.route_to_owner` audit row; owner unresolved → `_email_owners_and_admins` fallback + audit still written (D-09); viewer 403 on write but 200 on GET; cross-tenant `asset_id` → 404 (not 403/500) | integration | `pytest tests/test_coverage.py::test_route_to_owner_resolved -x && pytest tests/test_coverage.py::test_route_to_owner_fallback -x && pytest tests/test_coverage.py::test_route_to_owner_rbac -x && pytest tests/test_coverage.py::test_route_to_owner_cross_tenant_404 -x` | ❌ W0 | ⬜ pending |
| 41-05-01 | 05 | 4 | COV-03 | — | Route-to-owner confirm dialog + mutation wired from the coverage drill panel | component | `npm test -- route-to-owner` | ❌ W0 | ⬜ pending |
| 41-05-02 | 05 | 4 | COV-03 | — | Drill panel opens from a coverage row (tickets-page `idKey` precedent) and reflects post-route state | component | `npm test -- coverage/page` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*File Exists ❌ W0: test file created inline by the plan's TDD/Wave-0 task before assertion — no dangling MISSING reference.*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_coverage.py` — new file; no existing test covers this module (entirely new backend domain)
- [ ] `backend/tests/test_intune_sync.py` — new file; covers the 41-02 Intune sync defect fix
- [ ] `frontend/src/app/(authed)/dashboard/coverage/page.test.tsx` — new; mirrors `assets/page.test.tsx` loading/empty/error/populated branch coverage
- [ ] `frontend/src/components/coverage/*.test.tsx` — new component tests for `CoverageConnectorCard` and `RouteToOwnerDialog`
- [ ] Framework install: **none** — pytest and Vitest are already fully configured

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live third-party email/channel delivery of a route-to-owner notification | COV-03 / D-09 | Real SMTP/alert-channel delivery cannot be asserted in CI (external side-effect); tests assert the send-call + audit row, not receipt | In `/gsd-verify-work 41`: route an unmanaged asset with no resolvable owner; confirm the admin/owner fallback email is received and a `coverage.route_to_owner` audit row exists |
| `/dashboard/coverage` route smoke + axe (WCAG AA) | COV-01 | Axe sweep needs a prod build + running server (MEMORY.md `getvul-axe-sweep-not-run-during-exec`); not run inline during execution | Extend `frontend/e2e/a11y-routes.spec.ts` (or add `coverage.spec.ts`) and run `npm run test:e2e` against a prod build before ship |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (test files created inline by TDD/Wave-0 tasks)
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-08-20
