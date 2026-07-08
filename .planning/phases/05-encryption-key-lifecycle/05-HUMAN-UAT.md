---
status: partial
phase: 05-encryption-key-lifecycle
source: [05-VERIFICATION.md]
started: 2026-07-06T00:00:00Z
updated: 2026-07-08T00:00:00Z
---

## Current Test

[1 item outstanding — full container-exit path for production startup rejection]

## Tests

### 1. Live `verify` command against a running stack
expected: `docker compose exec -T backend python3 -m app.encryption verify` runs against a stack with seeded connector rows and prints `N OK / M failing` with no traceback; exits 0 when all rows decrypt with the current key.
result: pass
note: "Covered by interactive UAT (05-UAT.md Test 3): live verify in a container against the dev DB printed '0 OK / 0 failing' exit 0, and against an isolated getvul_test DB with one seeded encrypted connector printed '1 OK / 0 failing' exit 0. No traceback."

### 2. Production startup rejection on placeholder key
expected: with `ENVIRONMENT=production` and `ENCRYPTION_KEY` set to the placeholder (or unset), the backend container fails to start — uvicorn propagates the `RuntimeError` from `_check_secrets_at_startup()` to a non-zero container exit — and never serves traffic.
result: pending
note: "Underlying check human-verified in interactive UAT (05-UAT.md Tests 7 + 8): production + placeholder/empty/invalid ENCRYPTION_KEY and production + placeholder JWT_SECRET_KEY each raised RuntimeError and logged critical 'startup_secret_check_failed' (no key material), while dev warned-and-continued (Test 9). Those were driven by invoking `_check_secrets_at_startup()` directly. Still outstanding: confirm uvicorn propagates that RuntimeError through FastAPI's lifespan hook to a non-zero *container* exit before serving the first request (full `docker compose up backend` in production mode). Thin integration-wrapper check only; the security-critical decision logic is already proven."

## Summary

total: 2
passed: 1
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
