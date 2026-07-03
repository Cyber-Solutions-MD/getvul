---
status: resolved
phase: 04-doc-code-parity
source: [04-VERIFICATION.md, 04-REVIEW.md]
started: "2026-07-03T00:00:00Z"
updated: "2026-07-03T00:00:00Z"
---

## Current Test

[resolved in code — no human action outstanding]

## Tests

### 1. Swagger UI renders when DEBUG=true (WR-01)
expected: With `settings.debug=True`, opening `/docs` (Swagger UI) and `/redoc` in a browser renders the interactive API docs. The unconditional CSP `default-src 'none'` had NO `script-src`/`style-src`, so it blocked Swagger/ReDoc assets.

result: resolved — fixed in commit bc2df7b. `SecurityHeadersMiddleware.dispatch` now skips the strict CSP for the debug-only routes `/docs`, `/redoc`, `/openapi.json` (`DOCS_PATHS`), so the docs pages load their CDN assets in dev. Production (`DEBUG=false`) leaves those routes unmounted, so the strict policy still covers the entire live surface. Dispatch-level unit tests assert the exemption (debug) and non-exemption (prod) branches without Redis; `docs/16-security.md` corrected. Optional human smoke-check: with `DEBUG=true`, confirm `/docs` renders in a browser — no longer blocked by CSP.

## Summary

total: 1
passed: 1
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps
