---
status: partial
phase: 05-encryption-key-lifecycle
source: [05-VERIFICATION.md]
started: 2026-07-06T00:00:00Z
updated: 2026-07-06T00:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Live `verify` command against a running stack
expected: `docker compose exec -T backend python3 -m app.encryption verify` runs against a stack with seeded connector rows and prints `N OK / M failing` with no traceback; exits 0 when all rows decrypt with the current key.
result: [pending]

### 2. Production startup rejection on placeholder key
expected: with `ENVIRONMENT=production` and `ENCRYPTION_KEY` set to the placeholder (or unset), the backend container fails to start — uvicorn propagates the `RuntimeError` from `_check_secrets_at_startup()` to a non-zero container exit — and never serves traffic.
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
