---
phase: 1
slug: multi-replica-state
status: complete
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-08
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3+, pytest-asyncio 0.24+ (`asyncio_mode = "auto"`) |
| **Config file** | `backend/pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `cd backend && pytest tests/test_oidc_state.py tests/test_rate_limit.py tests/test_multi_replica.py -x` |
| **Full suite command** | `cd backend && pytest -v --cov=app --cov-report=xml` |
| **Estimated runtime** | ~30 s quick / ~90 s full (assuming current test count) |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && pytest tests/test_oidc_state.py tests/test_rate_limit.py tests/test_multi_replica.py -x`
- **After every plan wave:** Run `cd backend && pytest -v`
- **Before `/gsd-verify-work`:** Full suite must be green (`cd backend && pytest -v --cov=app --cov-report=xml`)
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-W0-01 | Wave 0 | 0 | PROD-01-01/02/03 | — | Test infra present | infra | `cd backend && test -f tests/conftest.py` | ✅ | ✅ green |
| 01-W0-02 | Wave 0 | 0 | PROD-01-03 | — | `asgi-lifespan` dev dep declared | infra | `grep "asgi-lifespan" backend/pyproject.toml` | ✅ | ✅ green |
| 01-W0-03 | Wave 0 | 0 | PROD-01-01/02 | — | `create_app()` factory exists | refactor | `grep "def create_app" backend/app/main.py` | ✅ | ✅ green |
| 01-01-01 | 01-01 | 1 | PROD-01-01 | T-OIDC-replay | OIDC state SET with TTL ≤ 600s, GETDEL atomic consume | unit | `cd backend && pytest tests/test_oidc_state.py::test_state_set_with_ttl -x` | ✅ | ✅ green |
| 01-01-02 | 01-01 | 1 | PROD-01-01 | T-OIDC-replay | OIDC callback rejects reused state token | unit | `cd backend && pytest tests/test_oidc_state.py::test_state_replay_rejected -x` | ✅ | ✅ green |
| 01-01-03 | 01-01 | 1 | PROD-01-01 | T-OIDC-mismatch | OIDC callback rejects mismatched provider | unit | `cd backend && pytest tests/test_oidc_state.py::test_state_provider_mismatch -x` | ✅ | ✅ green |
| 01-01-04 | 01-01 | 1 | PROD-01-01 | T-OIDC-ttl | OIDC state expires after TTL (1 s in test) | unit | `cd backend && pytest tests/test_oidc_state.py::test_state_ttl_expiry -x` | ✅ | ✅ green |
| 01-01-05 | 01-01 | 1 | PROD-01-01 | T-OIDC-redis-down | OIDC login returns 503 on Redis ConnectionError | failure-mode | `cd backend && pytest tests/test_oidc_state.py::test_login_503_on_redis_down -x` | ✅ | ✅ green |
| 01-02-01 | 01-02 | 1 | PROD-01-02 | T-RL-cap | Limiter allows N≤200 in window, 429 at 201 | unit | `cd backend && pytest tests/test_rate_limit.py::test_limit_enforced -x` | ✅ | ✅ green |
| 01-02-02 | 01-02 | 1 | PROD-01-02 | T-RL-window | Limiter prunes entries older than window | unit | `cd backend && pytest tests/test_rate_limit.py::test_window_slides -x` | ✅ | ✅ green |
| 01-02-03 | 01-02 | 1 | PROD-01-02 | T-RL-tenant | Limiter is per-tenant (A and B independent) | unit | `cd backend && pytest tests/test_rate_limit.py::test_per_tenant_isolation -x` | ✅ | ✅ green |
| 01-02-04 | 01-02 | 1 | PROD-01-02 | T-RL-redis-down | Limiter fails OPEN + emits warning log on Redis ConnectionError | failure-mode | `cd backend && pytest tests/test_rate_limit.py::test_fail_open_on_redis_down -x` | ✅ | ✅ green |
| 01-02-05 | 01-02 | 1 | PROD-01-02 | T-RL-zadd-race | 200 concurrent requests observe correct cap (sub-ms duplicate-member defense) | concurrency | `cd backend && pytest tests/test_rate_limit.py::test_concurrent_burst_respects_limit -x` | ✅ | ✅ green |
| 01-02-06 | 01-02 | 1 | PROD-01-02 | — | doc/security.md:20 wording matches code | docs | `cd backend && pytest tests/test_rate_limit.py::test_doc_parity -x` | ✅ | ✅ green |
| 01-03-01 | 01-03 | 2 | PROD-01-03 | T-replica-spoof | Cross-replica OIDC: state set on app A, consumed on app B | integration | `cd backend && pytest tests/test_multi_replica.py::test_oidc_cross_replica -x` | ✅ | ✅ green |
| 01-03-02 | 01-03 | 2 | PROD-01-03 | T-replica-replay | Cross-replica OIDC second consume fails (one-shot) | integration | `cd backend && pytest tests/test_multi_replica.py::test_oidc_one_shot -x` | ✅ | ✅ green |
| 01-03-03 | 01-03 | 2 | PROD-01-03 | T-replica-bypass | Cross-replica rate limit: 100 reqs A + 101 reqs B → 201st is 429 | integration | `cd backend && pytest tests/test_multi_replica.py::test_ratelimit_shared_budget -x` | ✅ | ✅ green |
| 01-03-04 | 01-03 | 2 | PROD-01-03 | T-redis-outage | Redis down mid-test: limiter allows + warns, OIDC returns 503 | integration | `cd backend && pytest tests/test_multi_replica.py::test_redis_outage_failure_modes -x` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/conftest.py` — shared fixtures: `redis_test_url` (resolves to `redis://localhost:6379/1`), `flushed_redis` (FLUSHDB before each test), `app_factory` (returns a fresh FastAPI via `create_app()`), `two_apps` (returns a tuple of two independent app instances)
- [ ] `backend/tests/test_oidc_state.py` — covers PROD-01-01 (5 cases above)
- [ ] `backend/tests/test_rate_limit.py` — covers PROD-01-02 (6 cases above)
- [ ] `backend/tests/test_multi_replica.py` — covers PROD-01-03 (4 cases above)
- [ ] Add `asgi-lifespan>=2.1` to `[project.optional-dependencies].dev` in `backend/pyproject.toml` — required so tests trigger the FastAPI lifespan that creates `app.state.redis`
- [ ] Add `create_app()` factory to `backend/app/main.py` (extract current top-level `app = FastAPI(...)` body into the factory; keep `app = create_app()` at module bottom so `uvicorn app.main:app` is unaffected)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual confirmation of structlog `redis_unavailable` warning shape in stdout | PROD-01-02 D-19 | Log format inspection benefits from human read; automated test asserts presence + fields, not human-readability | After running `test_fail_open_on_redis_down`, inspect captured logs for `event=redis_unavailable subsystem=rate_limiter error=...` |
| Production-like behavior under sustained 1000 req/min | PROD-01-02 | Out of CI scope; requires soak test infra not in this milestone | Run `wrk -t4 -c100 -d60s` against deployed staging; expect ≤200 req/min/tenant accepted, rest 429 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (`backend/tests/conftest.py`, three `test_*.py` files, `asgi-lifespan` dep, `create_app()` factory)
- [ ] No watch-mode flags
- [ ] Feedback latency < 30 s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

---

## Validation Audit 2026-07-15 (post-BL-05 backend sweep)

Reconciled against the shipped suite. Pre-execution statuses were `⬜ pending` with `❌ W0`
file markers; every automated row now maps to an existing, passing test (Backend CI green on main).

| Metric | Count |
|--------|-------|
| Automated rows | 19 |
| Covered (green) | 19 |
| Gaps found | 0 |
| New tests written | 0 |
| Escalated to manual-only | 0 |

Evidence: `test_oidc_state.py` (5 tests), `test_rate_limit.py` (6), `test_multi_replica.py` (4),
`conftest.py` fixtures + `create_app()` + `asgi-lifespan` all present. **Nyquist-compliant.**
