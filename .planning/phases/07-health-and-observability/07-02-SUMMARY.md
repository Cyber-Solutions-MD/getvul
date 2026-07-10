---
phase: 07-health-and-observability
plan: "02"
subsystem: backend/observability
tags: [structlog, logging, redaction, runbook, json-logging, observability]
dependency_graph:
  requires:
    - backend/app/logging.py (importable stub from 07-00)
    - backend/app/main.py (configure_logging() call-site from 07-01)
    - backend/tests/test_health_observability.py (RED scaffold from 07-00)
  provides:
    - backend/app/logging.py: full configure_logging(), redact_sensitive_keys(), _ProbePathFilter
    - docs/15-monitoring-logging.md: Failure Modes & Operator Response runbook section
  affects:
    - backend/tests/test_health_observability.py (turns test_logging_json_in_production, test_logging_console_in_dev, test_redact_sensitive_keys GREEN)
tech_stack:
  added: []
  patterns:
    - structlog.stdlib.ProcessorFormatter + foreign_pre_chain unified stdlib+structlog stream (D-11)
    - ProcessorFormatter.wrap_for_formatter as final processor in structlog.configure()
    - ProcessorFormatter.remove_processors_meta as first processor in ProcessorFormatter.processors (Pitfall 2)
    - orjson.dumps wrapped via absorbing-kwargs function for bytes->str + ProcessorFormatter compat
    - structlog.reset_defaults() at configure_logging() start to defeat module-level logger cache (Pitfall 5)
    - logging.Filter subclass on uvicorn.access for probe-path suppression (D-19)
key_files:
  created: []
  modified:
    - backend/app/logging.py
    - docs/15-monitoring-logging.md
decisions:
  - orjson.dumps returns bytes; wrapped via _json_serializer(**_kw) function to decode to str and absorb structlog's `default=` kwarg (Rule 1 auto-fix)
  - structlog.reset_defaults() called as first statement in configure_logging() to guarantee clean slate regardless of module-level logger import order (Pitfall 5 / A3)
  - _ProbePathFilter added only to uvicorn.access logger (not root) so readiness_check_failed app-logger events remain visible (Pitfall 7)
  - foreign_pre_chain=shared_processors applies enrichment + redaction to stdlib/uvicorn records before renderer
  - remove_processors_meta placed first in ProcessorFormatter.processors to strip internal structlog keys before renderer (Pitfall 2)
metrics:
  duration_minutes: 25
  completed_date: "2026-07-10"
  tasks_completed: 2
  tasks_total: 2
  files_created: 0
  files_modified: 2
---

# Phase 07 Plan 02: Logging Implementation and Failure-Mode Runbook Summary

**One-liner:** Full structlog configure_logging() replacing 07-00 stub — unified JSON (prod) / ConsoleRenderer (dev) stream via ProcessorFormatter, sensitive-key redaction, probe-path suppression — plus DB-down / Redis-down / nginx-limitation operator runbook in docs/15-monitoring-logging.md.

## What Was Built

### Task 1: `backend/app/logging.py` — Full Implementation

Replaced the 07-00 no-op stub and NotImplementedError stub with the complete implementation:

**`configure_logging() -> None`:**
1. `structlog.reset_defaults()` — first statement; defeats the `cache_logger_on_first_use` binding from the module-level `logger = structlog.get_logger()` in main.py (Pitfall 5 / A3).
2. `min_level` gating: `logging.DEBUG` when `settings.debug`, else `logging.INFO` (D-16).
3. `shared_processors` chain (D-15): `merge_contextvars` (injects `request_id` from contextvars, D-13) → `add_log_level` → `add_logger_name` → `PositionalArgumentsFormatter()` → `TimeStamper(fmt="iso", utc=True)` → `StackInfoRenderer()` → `format_exc_info` → `UnicodeDecoder()` → `redact_sensitive_keys` (LAST — runs before renderer, D-17).
4. Renderer selection: `settings.environment == "production"` → `JSONRenderer(serializer=_json_serializer)` (orjson + bytes→str decode); else `ConsoleRenderer()` (D-11).
5. `structlog.configure()` with `shared_processors + [ProcessorFormatter.wrap_for_formatter]` as processors; `LoggerFactory()`; `make_filtering_bound_logger(min_level)`; `cache_logger_on_first_use=True`.
6. `ProcessorFormatter(processors=[remove_processors_meta, renderer], foreign_pre_chain=shared_processors)` — remove_processors_meta first (Pitfall 2); foreign_pre_chain applies shared processors to uvicorn.* stdlib records (D-11).
7. One `logging.StreamHandler(sys.stdout)` with the formatter; root logger handlers cleared first; root level set to `min_level`.
8. `logging.getLogger("uvicorn.access").addFilter(_ProbePathFilter())` — suppresses /health and /ready access-log lines; does NOT suppress app-level `readiness_check_failed` events (Pitfall 7).

**`redact_sensitive_keys(logger, method, event_dict)`:**
Iterates over `SENSITIVE_KEYS` (frozen, never over `event_dict.items()` while mutating — Pitfall 6); sets `event_dict[key] = "[REDACTED]"` for each key present; returns `event_dict`. Does not raise on empty dict.

**`_ProbePathFilter(logging.Filter)`:**
`_PROBE_PATHS = ("/health", "/ready")`; `filter()` returns `False` (drop) when the record message contains a probe path, else `True`.

**`SENSITIVE_KEYS: frozenset`:**
Unchanged from 07-00 stub — `{"authorization", "cookie", "password", "token", "secret", "credentials", "api_key"}` (D-17).

### Task 2: `docs/15-monitoring-logging.md` — Failure Modes & Operator Response Runbook

Appended a new `## Failure Modes & Operator Response` section immediately after the existing `## Health checks` section. Also updated the Health checks table to include the `/ready` endpoint row.

**Section contents (D-20):**
- Intro paragraph: `/ready` is the readiness gate (500ms bounds); docker-compose healthcheck is the de-facto active monitor; failure detection = 503 body + `readiness_check_failed` ERROR log naming which dep failed.
- Three-row symptom table: Postgres unreachable, Redis unreachable, dependency slow (> 500ms) — each row maps `/ready` body → log event → operator action.
- Redis failure row documents the fails-OPEN (rate limiter) vs fails-CLOSED (OIDC) nuance per D-04 hard-fail policy.
- `### nginx upstream — single-VM limitation` subsection: documents that open-source nginx ignores `max_fails`/`fail_timeout` for a single-server upstream group; upstream block is forward-compatible scaffolding; the real gate is the compose healthcheck; nginx Plus or an external HTTPS uptime monitor is required for active probing.
- `### CI/dev depends_on asymmetry` one-liner: CI gates frontend on `service_healthy`; dev depends_on left unconditioned for fast startup.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] orjson.dumps returns bytes; structlog.stdlib.ProcessorFormatter expects str**

- **Found during:** Task 1 verification (first test run)
- **Issue:** `structlog.processors.JSONRenderer` calls `serializer(event_dict, **self._dumps_kw)` where `_dumps_kw` includes a `default=` kwarg. `orjson.dumps` returns `bytes`, which `ProcessorFormatter.emit()` cannot write directly (it expects `str`). The plan specified `serializer=orjson.dumps` verbatim, which produced a bytes repr string in output and then failed JSON parsing.
- **Fix:** Defined a wrapper `_json_serializer(obj, **_kw)` that calls `orjson.dumps(obj).decode("utf-8")` and absorbs the `default=` kwarg. This preserves orjson's type-handling advantage (datetime, UUID natively) while satisfying both the str requirement and the `**kwargs` contract.
- **Files modified:** `backend/app/logging.py`
- **Commit:** `73931be`

**Deviations note:** The plan's Pattern 1 code used `serializer=orjson.dumps` directly. The runtime behavior of `ProcessorFormatter` requires a str-returning callable. The wrapper is a minimal, correct fix that preserves the design intent (orjson serialization, bytes decoded to str).

## Known Stubs

None. Both functions that were stubs in 07-00 are now fully implemented:
- `configure_logging()`: full implementation (replaces no-op)
- `redact_sensitive_keys()`: full implementation (replaces NotImplementedError)

## Threat Flags

No new threat surface beyond what the plan's `<threat_model>` covers:
- T-07-02-01 (Information Disclosure / key material): mitigated — `redact_sensitive_keys` scrubs D-17 key set, runs LAST before renderer, also in `foreign_pre_chain` for stdlib records. Verified by `test_redact_sensitive_keys`.
- T-07-02-02 (Tampering / log injection): mitigated — `_json_serializer` via orjson.dumps JSON-escapes all values.
- T-07-02-03 (Repudiation / correlation gap): mitigated — `merge_contextvars` injects `request_id` on every line including uvicorn records via `foreign_pre_chain`.
- T-07-02-04 (Information Disclosure / audit cross-contamination): accepted — `configure_logging()` does not touch `app/audit.py` or its SysLogHandler.

## Self-Check: PASSED

- `backend/app/logging.py` exists: FOUND
- `backend/app/logging.py` contains `structlog.reset_defaults()`: FOUND
- `backend/app/logging.py` contains `structlog.stdlib.ProcessorFormatter`: FOUND
- `backend/app/logging.py` contains `wrap_for_formatter`: FOUND
- `backend/app/logging.py` contains `remove_processors_meta`: FOUND
- `backend/app/logging.py` contains `foreign_pre_chain`: FOUND
- `backend/app/logging.py` contains `JSONRenderer`: FOUND
- `backend/app/logging.py` contains `ConsoleRenderer()`: FOUND
- `backend/app/logging.py` contains `make_filtering_bound_logger`: FOUND
- `backend/app/logging.py` contains `class _ProbePathFilter`: FOUND
- `backend/app/logging.py` contains `uvicorn.access`: FOUND
- `backend/app/logging.py` does NOT contain `NotImplementedError`: CONFIRMED
- `docs/15-monitoring-logging.md` contains `## Failure Modes & Operator Response`: FOUND
- `docs/15-monitoring-logging.md` contains `readiness_check_failed`: FOUND
- `docs/15-monitoring-logging.md` contains `/ready`: FOUND
- `docs/15-monitoring-logging.md` contains `single-server` (case-insensitive): FOUND
- `docs/15-monitoring-logging.md` contains `postgres` (case-insensitive): FOUND
- `docs/15-monitoring-logging.md` contains `redis` (case-insensitive): FOUND
- `docs/15-monitoring-logging.md` contains `fails-open`: FOUND
- Commit `73931be` (Task 1 — configure_logging() implementation): FOUND
- Commit `dedf74f` (Task 2 — Failure Modes runbook): FOUND
- Tests: `test_logging_json_in_production` PASSED, `test_logging_console_in_dev` PASSED, `test_redact_sensitive_keys` PASSED
