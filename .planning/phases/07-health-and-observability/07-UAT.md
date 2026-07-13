---
status: complete
phase: 07-health-and-observability
source: [07-00-SUMMARY.md, 07-01-SUMMARY.md, 07-02-SUMMARY.md]
started: 2026-07-11T00:00:00Z
updated: 2026-07-13T07:30:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running server/containers. Clear ephemeral state. Start the app from scratch. Backend boots without errors, configure_logging() runs before the first startup log line, dependency checks pass, and /health returns 200 `{"status":"ok","service":"getvul-api"}`.
result: pass
notes: full `docker compose down` → `up --build`; all 5 services up; backend healthcheck (/ready) went healthy; Alembic migrations ran clean; /health → 200 with x-request-id header.

### 2. Liveness probe — GET /health always 200
expected: GET /health returns 200 with body exactly `{"status":"ok","service":"getvul-api"}`, even when a dependency is down.
result: pass
notes: 200 verbatim body; stayed 200 while Redis was paused (verified in Test 4).

### 3. Readiness probe — GET /ready 200 when deps up
expected: 200 with `{"status": ..., "checks": {...}}` reporting postgres + redis OK; bounded latency.
result: pass
notes: `{"status":"ready","checks":{"postgres":{"ok":true,"latency_ms":3},"redis":{"ok":true,"latency_ms":0}}}` → 200.

### 4. Readiness probe — GET /ready 503 when a dependency is down
expected: 503 with the failed dependency not-ok; body exposes only ok/latency/error-class (no secrets/connection strings/stack traces); a readiness_check_failed ERROR log names the failed dep.
result: pass
notes: Redis paused → 503 `{"status":"not_ready","checks":{"postgres":{"ok":true},"redis":{"ok":false,"error":"timeout"}}}`; no secrets leaked; `readiness_check_failed postgres_ok=True redis_ok=False request_id=...` logged; recovered to 200 on unpause.

### 5. Request correlation — X-Request-ID header
expected: response carries X-Request-ID (UUID); valid inbound value echoed; invalid/oversized replaced with fresh UUID; log lines carry the same request_id.
result: pass
notes: minted UUID on plain request; `X-Request-ID: my-trace-123` echoed; `bad id with spaces!!` replaced with a fresh UUID; readiness_check_failed log carried request_id.

### 6. Structured logging renderer (JSON in prod, console in dev)
expected: JSON one-line logs in production, console in dev; /health + /ready access-log noise suppressed; readiness_check_failed still visible.
result: pass
notes: dev ConsoleRenderer confirmed in live startup logs; 0 uvicorn access lines for /health|/ready after probe traffic (_ProbePathFilter); readiness_check_failed app event still emitted. Prod JSON renderer covered by passing unit tests test_logging_json_in_production / test_logging_console_in_dev.

### 7. Sensitive-key redaction in logs
expected: keys authorization/cookie/password/token/secret/credentials/api_key rendered as [REDACTED].
result: pass
notes: redact_sensitive_keys() redacted all 7 SENSITIVE_KEYS to "[REDACTED]"; non-sensitive keys preserved.

### 8. nginx routes /ready and uses named upstream
expected: /ready via nginx proxies to backend and returns the same result; named `upstream backend` block; no `http://backend:8000/` literals.
result: pass
notes: `https://localhost/ready` → 200 with correct body through nginx.

### 9. Compose healthcheck gates on /ready
expected: backend reports healthy only after /ready succeeds (healthcheck hits /ready, not /health).
result: pass
notes: healthcheck cmd urlopen('http://localhost:8000/ready'); backend container state = healthy.

## Summary

total: 9
passed: 9
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none — all tests passed]

<!--
Note: this UAT surfaced a chain of unrelated FRONTEND/login bugs (Phases
6/9/10/11/12/13/14) while navigating the running app. Those were diagnosed and
fixed on branch fix/uat-frontend-error-chain (7 atomic commits). They are NOT
Phase 7 gaps — Phase 7's own deliverables all pass. A "data loss" scare during
the session was traced to the backend test suite TRUNCATEing the shared dev DB
when pytest was run inside the live container — a dev-env gotcha, not a product
bug.
-->
