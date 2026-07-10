---
phase: 07
slug: health-and-observability
status: secured
threats_open: 0
threats_closed: 11
asvs_level: 2
created: 2026-07-10
---

# Security Audit — Phase 7: Health and Observability

**Audit Date:** 2026-07-10
**Auditor:** gsd-security-auditor
**ASVS Level:** L2
**Block On:** high (open threats = BLOCKER)

---

## Audit Result: SECURED

**Threats Closed:** 11 / 11
**Threats Open:** 0 / 11

---

## Threat Verification

| Threat ID | Category | Disposition | Status | Evidence |
|-----------|----------|-------------|--------|----------|
| T-07-00-01 | Tampering | mitigate | CLOSED | `backend/tests/test_health_observability.py:346` — `test_request_id_middleware` asserts three cases: no inbound (UUID4 minted), valid inbound echoed, invalid/oversized (200-char) replaced. Line 381 uses `"x" * 200` as the oversized case; line 387 asserts response differs from inbound. |
| T-07-00-02 | Information Disclosure | mitigate | CLOSED | `backend/tests/test_health_observability.py:400,438` — `test_redact_sensitive_keys` asserts `authorization`, `password`, `api_key` → `[REDACTED]` (line 420-426). `test_redact_sensitive_keys_case_insensitive_and_nested` covers title-cased and nested credentials (CR-01 regression tests, lines 458-465). |
| T-07-00-03 | Information Disclosure | accept-verify | CLOSED | `backend/tests/test_health_observability.py:86,141` — `test_ready_200_both_up` and `test_ready_503_postgres_down` both assert `"detail" not in body`. Accepted risk holds: `/ready` handler at `backend/app/main.py:307-351` uses `JSONResponse(content={...})` (never `raise HTTPException`), and Exception branches record only `type(exc).__name__` (lines 327, 338), not `str(exc)`. |
| T-07-01-01 | Tampering | mitigate | CLOSED | `backend/app/main.py:242` — `_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")`. Applied at line 251 in `RequestIdMiddleware.dispatch`: valid inbound honored, else `str(uuid.uuid4())` minted (line 254). Registered on all requests via `app.add_middleware(RequestIdMiddleware)` at line 288. |
| T-07-01-02 | Information Disclosure | accept | CLOSED | Accepted risk holds. `/ready` handler (main.py:307-351) uses `JSONResponse` exclusively — no `HTTPException` raise in the handler, confirmed by inspection. `except Exception as exc` path sets `error: type(exc).__name__` only (lines 327, 338). No connection strings, credentials, or stack traces in response body. |
| T-07-01-03 | Denial of Service | mitigate | CLOSED | `backend/app/main.py:321` — `asyncio.wait_for(session.execute(text("SELECT 1")), timeout=0.5)` (Postgres). Line 332 — `asyncio.wait_for(request.app.state.redis.ping(), timeout=0.5)` (Redis). Both probes bounded at 500ms per D-06. `test_ready_503_timeout_path` (test file line 177) verifies the timeout path produces `{"ok": false, "error": "timeout"}`. |
| T-07-01-04 | Denial of Service | mitigate | CLOSED | `backend/app/main.py:318-320` — `/ready` opens sessions via `async_session_factory` (the shared pool, same as all other requests). Pool exhaustion surfaces as 503 rather than being hidden. No dedicated probe-only connection exists. |
| T-07-02-01 | Information Disclosure | mitigate | CLOSED | `backend/app/logging.py:42-90` — `redact_sensitive_keys` implements CR-01-hardened redaction: `_is_sensitive(key)` uses `key.lower() in SENSITIVE_KEYS` (line 49, case-insensitive), and `_redact_value()` recurses into nested dicts and lists (lines 59-65). Processor placed LAST in `shared_processors` before renderer (line 171) and included in `foreign_pre_chain` (line 212) for stdlib/uvicorn records. Both case-insensitive and recursive regression tests present in test file (lines 438-466). |
| T-07-02-02 | Tampering | mitigate | CLOSED | `backend/app/logging.py:180-184` — `_json_serializer` wraps `orjson.dumps(obj, default=default).decode("utf-8")`, forwarding the `default` callable (WR-04 fix). `JSONRenderer(serializer=_json_serializer)` used in production path (line 184). JSON serialization escapes all values including embedded newlines/control characters. |
| T-07-02-03 | Repudiation | mitigate | CLOSED | `backend/app/logging.py:163` — `structlog.contextvars.merge_contextvars` is FIRST in `shared_processors`, injecting `request_id` into every structlog event. Line 212 — `foreign_pre_chain=shared_processors` applies the same chain (including `merge_contextvars`) to stdlib uvicorn records, ensuring `request_id` appears on every log line across all loggers. |
| T-07-02-04 | Information Disclosure | accept | CLOSED | Accepted risk holds. `backend/app/logging.py` contains no `import audit`, no `from app.audit`, no `SysLogHandler` reference in `configure_logging()`. Module docstring (lines 7-10) explicitly states the two channels remain independent. The audit syslog pipeline in `app/audit.py` is wired separately via the lifespan syslog-config bootstrap (main.py:117-135), not through `configure_logging()`. |

---

## Unregistered Flags

None. All SUMMARY.md `## Threat Flags` sections across 07-00, 07-01, and 07-02 report "None" — no new attack surface was declared by executors during implementation.

---

## Accepted Risks Log

| Risk ID | Threat | Accepted Claim | Verified |
|---------|--------|----------------|---------|
| T-07-01-02 | /ready body (public) | Body contains only `status`, `ok`, `latency_ms`, error-class string. No connection strings, credentials, or stack traces. | YES — `type(exc).__name__` only, `JSONResponse` used throughout, no `raise HTTPException` in handler. |
| T-07-02-04 | Audit pipeline cross-contamination | `configure_logging()` does not touch `app/audit.py` or its `SysLogHandler`. Two channels remain separate by design. | YES — zero audit references in `logging.py`; audit wired independently in `lifespan()`. |

---

## Notes

- **CR-01 (critical code review finding, resolved):** The original `redact_sensitive_keys` implementation scrubbed only exact-case top-level keys. The current implementation in `backend/app/logging.py` is the CR-01-hardened version: case-insensitive via `_is_sensitive()` + `key.lower()` (line 49), and recursive via `_redact_value()` descending into nested dicts and lists (lines 52-66). Two regression tests (`test_redact_sensitive_keys_case_insensitive_and_nested` and `test_probe_filter_exact_path_match`) verify the fixes. The threat register note for T-07-02-01 explicitly asks to "verify the CURRENT impl" — the current impl is confirmed hardened.

- **WR-01 (probe filter substring match, resolved):** `_ProbePathFilter` now uses a regex to extract the exact request path (`_REQUEST_LINE = re.compile(r'"[A-Z]+ (?P<path>[^ ?]+)(?:\?[^ ]*)? HTTP/')`) and compares against a frozenset, not a substring. `test_probe_filter_exact_path_match` (test file line 469) verifies `/health-history` and query strings containing `/ready` are NOT suppressed.

- **WR-04 (orjson default= forwarding, resolved):** `_json_serializer` forwards the `default` callable to `orjson.dumps` (logging.py:181), preventing `TypeError` on non-native types.

- **WR-02 (CORS wildcard, pre-existing, out of scope):** The `allow_origins=["https://*.getvul.app"]` pattern in `main.py:280` is a pre-existing defect from the initial scaffold, not introduced by Phase 7. Flagged for a dedicated fix outside this phase's scope. Not a Phase 7 threat register item.
