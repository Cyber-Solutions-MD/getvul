---
phase: 6
slug: default-admin-hardening
status: complete
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-08
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Backend: pytest with pytest-asyncio (asyncio_mode=auto). Frontend: Vitest 2.x + jsdom + @testing-library/react |
| **Config file** | Backend: `backend/pyproject.toml` `[tool.pytest.ini_options]`. Frontend: `frontend/vitest.config.mts` |
| **Quick run command** | `cd backend && ENCRYPTION_KEY=$ENCRYPTION_KEY JWT_SECRET_KEY=$JWT_SECRET_KEY python -m pytest tests/test_admin_hardening.py -x` |
| **Full suite command** | `cd backend && python -m pytest tests/test_admin_hardening.py tests/test_auth.py -x` (per-file — NOT whole `tests/` dir) + `cd frontend && npm run test` |
| **Estimated runtime** | ~30 seconds |

**Backend env gotcha (MEMORY.md `getvul-backend-pytest-env`):** `ENCRYPTION_KEY` and `JWT_SECRET_KEY` must be set; run tests per-file, not the whole `tests/` directory, or you get false failures.

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/test_admin_hardening.py -x` (or the frontend Vitest file for FE tasks)
- **After every plan wave:** Run `pytest tests/test_admin_hardening.py tests/test_auth.py -x` (regression: existing JWT/auth tests must still pass) + `npm run test`
- **Before `/gsd-verify-work`:** Full backend suite green + frontend `npm run test` green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| migration + column | 01 | 1 | PROD-06-01 | — | `users.must_change_password` boolean NOT NULL server_default false; migration up/down clean | integration | `pytest tests/test_admin_hardening.py::test_migration_column -x` | ✅ | ✅ green |
| seed flag | 01 | 1 | PROD-06-01 | — | seeded OWNER admin row has `must_change_password=True` | integration | `pytest tests/test_admin_hardening.py::test_seed_flag -x` | ✅ | ✅ green |
| JWT claim round-trip | 02 | 2 | PROD-06-02 | T-06-token-replay | access token from login carries `must_change_password`; decode restores it | unit | `pytest tests/test_admin_hardening.py::test_jwt_claim_round_trip -x` | ✅ | ✅ green |
| CurrentUser claim | 02 | 2 | PROD-06-02 | — | `get_current_user` returns `must_change_password=True` for flagged token | unit | `pytest tests/test_admin_hardening.py::test_current_user_claim -x` | ✅ | ✅ green |
| enforcement blocks | 02 | 2 | PROD-06-02 | T-06-allowlist-bypass | flagged user, non-allowlist path → 403 `{"reason":"password_change_required"}` | integration | `pytest tests/test_admin_hardening.py::test_enforcement_blocks -x` | ✅ | ✅ green |
| allowlist /me | 02 | 2 | PROD-06-02 | T-06-allowlist-bypass | flagged user → `/auth/me` returns 200 | integration | `pytest tests/test_admin_hardening.py::test_enforcement_allowlist_me -x` | ✅ | ✅ green |
| allowlist change-pw | 02 | 2 | PROD-06-02 | — | flagged user → `/auth/change-password` not blocked | integration | `pytest tests/test_admin_hardening.py::test_enforcement_allowlist_change -x` | ✅ | ✅ green |
| unflagged unblocked | 02 | 2 | PROD-06-02 | — | unflagged user: no 403 interference on any path | integration | `pytest tests/test_admin_hardening.py::test_unflagged_user_unblocked -x` | ✅ | ✅ green |
| rotation clears flag | 02 | 2 | PROD-06-04 | — | successful rotation sets `users.must_change_password=False` | integration | `pytest tests/test_admin_hardening.py::test_rotation_clears_flag -x` | ✅ | ✅ green |
| rotation audit event | 02 | 2 | PROD-06-04 | — | rotation emits `auth.first_login_rotation` audit row | integration | `pytest tests/test_admin_hardening.py::test_rotation_audit_event -x` | ✅ | ✅ green |
| rotation fresh tokens | 02 | 2 | PROD-06-04 | T-06-token-replay | tokens returned after rotation do NOT carry the flag | integration | `pytest tests/test_admin_hardening.py::test_rotation_fresh_tokens -x` | ✅ | ✅ green |
| refresh reads flag | 02 | 2 | PROD-06-04 | T-06-token-replay | `/auth/refresh` after rotation carries current DB flag state (false) | integration | `pytest tests/test_admin_hardening.py::test_refresh_reads_current_flag -x` | ✅ | ✅ green |
| FE redirect gate | 03 | 3 | PROD-06-03 | — | `useAuth` sees `must_change_password=true` → `router.replace('/change-password')`; form submit + error/success states | unit | `cd frontend && npm run test -- change-password` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_admin_hardening.py` — all 12 backend test cases above; uses `db_session`, `tenant_a`, `client_factory` fixtures from `conftest.py` (already present — verified)
- [ ] `frontend/src/app/change-password/change-password.test.tsx` — Vitest unit: redirect gate fires when `must_change_password=true`; form submits correctly; error states render; success redirects to `/dashboard`

*Existing infrastructure (pytest, Vitest, conftest fixtures) is present — Wave 0 only adds the two new test files above, no framework install.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Full operator flow: `install.sh` seed → login as `admin@getvul.local` / `Admin123!` → forced onto `/change-password` → cannot escape to `/dashboard` → rotate → land on dashboard | PROD-06-01..04 | End-to-end across install script + real browser session; not cost-effective to automate at the install.sh layer | Fresh deploy, log in with defaults, confirm redirect + inescapability + successful rotation + audit row in `audit_logs` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

---

## Validation Audit 2026-07-15 (post-BL-05 backend sweep)

Reconciled against the shipped suite. Pre-execution statuses were `⬜ pending` / `❌ W0`; every
automated row now maps to an existing, passing test (Backend CI green on main).

| Metric | Count |
|--------|-------|
| Automated rows | 13 |
| Covered (green) | 13 |
| Gaps found | 0 |
| New tests written | 0 |
| Escalated to manual-only | 0 |

Evidence: `test_admin_hardening.py` (12 tests — migration/seed flag, JWT claim round-trip,
enforcement + allowlist, rotation clears flag + audit + fresh tokens + refresh) +
`change-password.test.tsx` (5 FE redirect-gate cases). **Nyquist-compliant.**
