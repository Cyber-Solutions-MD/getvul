---
phase: 7
slug: health-and-observability
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-10
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3+ with pytest-asyncio 0.24+ (`asyncio_mode = "auto"`) |
| **Config file** | `backend/pyproject.toml` `[tool.pytest.ini_options]` (`testpaths = ["tests"]`) |
| **Quick run command** | `cd backend && pytest tests/test_health_observability.py -x` |
| **Full suite command** | `cd backend && pytest tests/ -x` |
| **Estimated runtime** | ~5s (quick) / phase full suite per existing baseline |

> Backend pytest requires `ENCRYPTION_KEY` / `JWT_SECRET_KEY` env vars and per-file runs — see project memory `getvul-backend-pytest-env`.

---

## Sampling Rate

- **After every task commit:** Run `cd backend && pytest tests/test_health_observability.py -x`
- **After every plan wave:** Run `cd backend && pytest tests/ -x`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~5 seconds (quick command)

---

## Per-Task Verification Map

> Task IDs finalized by the planner. This map derives from RESEARCH.md §"Phase Requirements → Test Map" (D-21 test matrix). Every row's test file is a Wave 0 dependency.

| Requirement | Behavior | Threat Ref | Test Type | Automated Command | File Exists |
|-------------|----------|------------|-----------|-------------------|-------------|
| PROD-07-01 | `GET /health` returns 200 + verbatim body regardless of DB/Redis state | — | unit | `pytest tests/test_health_observability.py::test_health_always_200 -x` | ❌ W0 |
| PROD-07-02 | `GET /ready` 200 + per-dep body when DB+Redis healthy | — | integration | `pytest tests/test_health_observability.py::test_ready_200_both_up -x` | ❌ W0 |
| PROD-07-02 | `GET /ready` 503 when Postgres down (mocked) | — | unit | `pytest tests/test_health_observability.py::test_ready_503_postgres_down -x` | ❌ W0 |
| PROD-07-02 | `GET /ready` 503 when Redis down (mocked) | — | unit | `pytest tests/test_health_observability.py::test_ready_503_redis_down -x` | ❌ W0 |
| PROD-07-02 | `/ready` timeout path → `ok:false, error:"timeout"`, overall 503 | T-ready-dos | unit | `pytest tests/test_health_observability.py::test_ready_503_timeout_path -x` | ❌ W0 |
| PROD-07-04 | JSON renderer selected when `ENVIRONMENT=production` | — | unit | `pytest tests/test_health_observability.py::test_logging_json_in_production -x` | ❌ W0 |
| PROD-07-04 | ConsoleRenderer selected in dev | — | unit | `pytest tests/test_health_observability.py::test_logging_console_in_dev -x` | ❌ W0 |
| PROD-07-04 (D-13/14) | `X-Request-ID` echoed; valid inbound honored; invalid → UUID4 | T-reqid-inject | unit | `pytest tests/test_health_observability.py::test_request_id_middleware -x` | ❌ W0 |
| PROD-07-04 (D-17) | Redaction processor scrubs sensitive keys → `[REDACTED]` | T-log-leak | unit | `pytest tests/test_health_observability.py::test_redact_sensitive_keys -x` | ❌ W0 |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_health_observability.py` — RED stubs for all PROD-07-01/02/04 + D-13/D-14/D-17 cases above
- [ ] `backend/app/logging.py` — new module must exist (even as a stub) before tests can import it

Mock strategy (from RESEARCH.md): reuse the `single_app` fixture from `conftest.py` (lifespan already run, `app.state.redis` set); `monkeypatch.setattr(app.state.redis, "ping", boom_ping)` for Redis-down; monkeypatch `app.db.session.async_session_factory` for Postgres-down; `await asyncio.sleep(10)` under `asyncio.wait_for(0.5)` for the timeout path; `structlog.testing.capture_logs` for log assertions. Established pattern lives in `test_rate_limit.py`.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| nginx `upstream backend` block parses and routes | PROD-07-03 | nginx config validity is infra, not pytest | `docker compose config` + `nginx -t` in the nginx container; curl `/health` + `/ready` through the proxy |
| docker-compose healthcheck flips to `/ready` and gates `service_healthy` | PROD-07-03 | Compose orchestration behavior | `docker compose up`, observe backend reaches `healthy`; verify `depends_on: condition: service_healthy` consumers wait |
| Failure Modes & Operator Response runbook is present and correct | PROD-07 SC#5 | Docs prose | grep the chosen docs file for the runbook section headings mapping symptom → `/ready` state → log event → action |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (`test_health_observability.py`, `logging.py`)
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
