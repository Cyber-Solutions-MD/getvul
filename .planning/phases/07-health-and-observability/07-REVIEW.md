---
phase: 07-health-and-observability
reviewed: 2026-07-10T00:00:00Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - backend/app/logging.py
  - backend/app/main.py
  - backend/tests/test_health_observability.py
  - docker-compose.ci.yml
  - docker-compose.yml
  - docs/15-monitoring-logging.md
  - nginx/nginx.conf
findings:
  critical: 1
  warning: 5
  info: 5
  total: 11
status: resolved
resolution:
  fixed: [CR-01, WR-01, WR-04, WR-05]
  out_of_scope: [WR-02]   # pre-existing CORS bug from initial scaffold — not a Phase 7 change
  accepted: [WR-03]       # configure_logging() in lifespan is the plan's design decision (07-01)
---

# Phase 7: Code Review Report

**Reviewed:** 2026-07-10
**Depth:** standard
**Files Reviewed:** 7
**Status:** resolved

## Resolution (2026-07-10)

Fixed in follow-up commits during phase execution:
- **CR-01** — `redact_sensitive_keys` now matches case-insensitively and recurses into nested dicts/lists; two regression tests added. D-17 control is now effective.
- **WR-01** — `_ProbePathFilter` parses the exact request path instead of substring matching.
- **WR-04** — `_json_serializer` forwards the `default` callable to orjson.
- **WR-05** — healthcheck `urlopen` bounded with `timeout=4`; `start_period` widened to 60s.

Not addressed here (with rationale):
- **WR-02** (CORS wildcard `allow_origins`) — pre-existing defect from the initial project scaffold (`c39c79c`), not introduced by Phase 7. A real bug; flagged for a dedicated fix outside this phase's scope.
- **WR-03** (`configure_logging()` runs in lifespan, after uvicorn setup) — this is the design chosen in plan 07-01 (D: call it as the first lifespan statement). Moving it to import time is a design change beyond this phase's mandate.
- Info-level findings — noted; deferred as non-blocking cleanup.

## Summary

Phase 7 splits liveness (`/health`) from readiness (`/ready`), adds a request-id
middleware, wires a unified structlog configuration with a redaction processor,
adds an nginx upstream block, and points the compose healthchecks at `/ready`.
The wiring is mostly sound and the readiness probe's timeout/error handling is
solid. However the redaction processor — the security-critical piece of this
phase (D-17) — has a material gap: it only scrubs exact-case, top-level keys, so
the very values it is meant to catch (an `Authorization` header on a foreign
uvicorn record, or a nested credential) sail through un-redacted. There are also
several correctness and operability concerns around the probe-path log filter,
the readiness-check log statement, and a pre-existing broken CORS wildcard that
this file now owns.

## Critical Issues

### CR-01: Redaction processor misses cased and nested sensitive keys — real credential-leak path

**File:** `backend/app/logging.py:41-58`
**Issue:** `redact_sensitive_keys` iterates the lowercase `SENSITIVE_KEYS`
frozenset and only replaces top-level keys via `if key in event_dict`. Two gaps
make this fail exactly where D-17 needs it to hold:

1. **Case sensitivity.** The `foreign_pre_chain` runs this processor over
   *stdlib* records from `uvicorn.access` / `uvicorn.error` and any third-party
   library. Header-derived keys arrive title-cased (`Authorization`, `Cookie`,
   `Set-Cookie`) or upper-cased. `"authorization" in {"Authorization": "Bearer …"}`
   is `False`, so the bearer token is rendered verbatim into the log stream.
2. **Nested values.** Structlog events routinely carry nested payloads
   (`event_dict["headers"] = {...}`, `event_dict["body"] = {"password": "…"}`).
   The processor never descends, so a `password`/`token`/`secret` one level deep
   is emitted in cleartext.

Because this processor is the only redaction layer in the phase, either gap is a
credential disclosure into stdout/log shippers. This is a security control that
does not actually control.

**Fix:** Normalize keys case-insensitively and recurse into nested mappings:
```python
def redact_sensitive_keys(logger, method, event_dict):
    def _scrub(obj):
        if isinstance(obj, dict):
            for k in list(obj.keys()):
                if k.lower() in SENSITIVE_KEYS:
                    obj[k] = "[REDACTED]"
                else:
                    _scrub(obj[k])
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                _scrub(item)
    _scrub(event_dict)
    return event_dict
```
If recursion is deliberately out of scope, at minimum lower-case the comparison
(`if key.lower() in SENSITIVE_KEYS`) and document the top-level-only limitation.

## Warnings

### WR-01: `_ProbePathFilter` uses substring match — silently drops unrelated access logs

**File:** `backend/app/logging.py:70-74`
**Issue:** The filter returns `False` (drops the record) if `"/health"` or
`"/ready"` appears *anywhere* in the formatted access-log message via
`any(path in msg for path in self._PROBE_PATHS)`. `record.getMessage()` for a
uvicorn access line contains the full request line and can also contain query
strings, referers, or paths that merely *contain* the substring — e.g.
`GET /api/v1/assets?q=/ready`, `GET /health-history`, or
`GET /api/v1/reports/ready-report`. All of those are legitimate requests whose
access logs would be silently suppressed, blinding operators to real traffic.
The intent (D-19) is to suppress only the probe endpoints.

**Fix:** Match the actual request path, not a substring of the whole message.
Attach the filter with an exact-path check, e.g. inspect `record.args`
(uvicorn's access logger passes the path as a positional arg) or match a
word-boundaried pattern:
```python
_PROBE_RE = re.compile(r'"(?:GET|HEAD) (/health|/ready)(?:\?[^ ]*)? HTTP')
def filter(self, record):
    return not self._PROBE_RE.search(record.getMessage())
```

### WR-02: Production CORS `allow_origins` wildcard never matches — all cross-origin prod requests blocked

**File:** `backend/app/main.py:280`
**Issue:** `allow_origins=[... "https://*.getvul.app"]` relies on a wildcard
subdomain pattern. Starlette's `CORSMiddleware` treats `allow_origins` entries as
*exact* string matches (only the bare literal `"*"` is special-cased); it does
**not** interpret `*` as a glob. Verified against the installed
`starlette==1.3.1`. The real `Origin: https://app.getvul.app` will never equal
`"https://*.getvul.app"`, so in production (`debug=False`) no browser origin is
allowed and every credentialed cross-origin request fails preflight. This file
is in the Phase 7 review scope even though the line predates the phase.

**Fix:** Use the regex option, which Starlette *does* support:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"] if settings.debug else [],
    allow_origin_regex=None if settings.debug else r"https://.*\.getvul\.app",
    allow_credentials=True,
    ...
)
```

### WR-03: `configure_logging()` runs inside `lifespan`, after middleware/imports have already logged

**File:** `backend/app/main.py:41,97`
**Issue:** The module-level `logger = structlog.get_logger()` (line 41) and every
router import happen at import time, but `configure_logging()` is only invoked
inside `lifespan` (line 97) — i.e. at first startup, not at import. The module
docstring in `logging.py:12-15` and the inline comment (`must be the FIRST call
in lifespan`) claim `structlog.reset_defaults()` "defeats the module-level logger
cache," which is true for structlog's own bound loggers, but it does **not**
retroactively format any log lines emitted by imported modules or by uvicorn
*before* the app's lifespan runs (uvicorn configures its own logging first). Any
startup log emitted before `lifespan` executes bypasses the redaction chain and
renderer selection. In a multi-worker/multi-replica deploy this is the window
where unformatted (and unredacted) lines appear.

**Fix:** Call `configure_logging()` at module import (top of `main.py`, before
`logger = structlog.get_logger()`), or from uvicorn's `--log-config` /
`logging.config` hook, rather than deferring to lifespan. If it must stay in
lifespan, document that pre-lifespan log lines are intentionally unformatted and
confirm none can carry secrets.

### WR-04: `_json_serializer` swallows the `default` callable — non-native types will raise instead of serializing

**File:** `backend/app/logging.py:143-144`
**Issue:** The comment (lines 138-142) claims the wrapper "forwards `default` via
the orjson `option` mechanism if required" and warns "never drop kwargs
silently," but the implementation `def _json_serializer(obj, **_kw): return
orjson.dumps(obj).decode("utf-8")` does exactly that — it absorbs `**_kw`
(including `default`) and drops it. structlog's `JSONRenderer` passes
`default=repr` (or similar) so that objects orjson cannot natively encode still
serialize. Without forwarding it, any event value orjson does not handle
natively (e.g. `set`, `Decimal`, a custom object, `bytes`) raises `TypeError`
*inside the log call*, which can crash the request/log path rather than
degrading gracefully. The code contradicts its own stated contract.

**Fix:** Forward the callable to orjson's `default` parameter:
```python
def _json_serializer(obj, default=None, **_kw):
    return orjson.dumps(obj, default=default or repr).decode("utf-8")
```

### WR-05: Dev/CI backend healthcheck probes `/ready`, which needs an authenticated-free path but returns 503 during migrations — `start_period` may be too short

**File:** `docker-compose.yml:68-73`, `docker-compose.ci.yml:44-49`
**Issue:** The healthcheck now targets `/ready`, and the backend `command` runs
`alembic upgrade head` before uvicorn starts. `urllib.request.urlopen(...)`
raises `HTTPError` on the 503 that `/ready` returns while Postgres/Redis are
still warming — which is the intended "not ready" behavior — but urlopen also
raises on a 503, so the healthcheck correctly fails-and-retries. The concern is
the `start_period: 30s` combined with `alembic upgrade head` on a cold DB plus
image build: a large migration set can exceed 30s, during which failing probes
before `start_period` elapses are ignored, but probes *after* it that still hit
migration latency count toward the 20-retry budget at 5s interval (~100s). On
slow CI runners this is tight and can flap. Also, `urlopen` with no explicit
timeout can hang a probe indefinitely if the socket stalls, holding the
healthcheck's own `timeout: 5s` as the only bound (acceptable, but implicit).

**Fix:** Add an explicit urlopen timeout and give migrations headroom:
```yaml
test: ["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/ready', timeout=3)"]
start_period: 60s
```

## Info

### IN-01: Duplicate / redundant uuid imports

**File:** `backend/app/main.py:6-7`
**Issue:** `import uuid` and `import uuid as _uuid` both alias the same module.
`uuid.uuid4()` is used in the middleware while `_uuid.UUID(...)` is used in the
report routes — two names for one module is needless.
**Fix:** Drop line 7 and use `uuid.UUID(...)` everywhere.

### IN-02: Unused imports

**File:** `backend/app/main.py:9,24`
**Issue:** `timezone` and `datetime` are both imported (line 9) but `UTC` is used
in one place and `timezone` in another — fine — however `async_session_factory`
is imported at module top (line 24) yet the readiness probe re-imports it locally
(line 318) and the lifespan re-imports it locally (line 121), making the
top-level import dead. Also `JSONResponse` is imported at top (line 16) and
re-imported locally inside the rate-limit middleware (line 229).
**Fix:** Remove the module-level `from app.db.session import async_session_factory`
(line 24) if only the local call-time imports are intended, and drop the local
`from starlette.responses import JSONResponse` at line 229.

### IN-03: Broad `except Exception: pass` hides syslog-config startup failures

**File:** `backend/app/main.py:134-135`
**Issue:** The syslog-config bootstrap wraps everything in
`except Exception: pass`, silently swallowing DB errors, missing keys, or
`configure_syslog` failures. An operator who mis-configures `syslog_config` gets
no signal that audit forwarding never came up.
**Fix:** Log the exception at warning level before continuing:
`logger.warning("syslog_config_bootstrap_failed", error=str(exc))`.

### IN-04: Docs cite stale `main.py` line numbers

**File:** `docs/15-monitoring-logging.md:25,69,77`
**Issue:** References like `main.py:141-146`, `main.py:62-68`, and `main.py:61`
no longer correspond to the current code (the rate-limiter `redis_unavailable`
log is at 219-224; the syslog bootstrap is at 118-135). Stale line anchors
mislead operators following the runbook.
**Fix:** Update the anchors, or link to symbol names rather than line ranges.

### IN-05: `readiness_check_failed` log omits the failing dependency's error detail

**File:** `backend/app/main.py:343-347`
**Issue:** The ERROR log records only `postgres_ok` / `redis_ok` booleans. The
per-dependency `error` string (`"timeout"`, `"ConnectionRefusedError"`) that the
runbook table in `docs/15-monitoring-logging.md:92-96` promises to surface in the
log is not included, so log-only consumers (who never see the 503 body) lose the
"which failure mode" signal the docs claim exists.
**Fix:** Include the error strings:
```python
logger.error("readiness_check_failed",
             postgres=checks["postgres"], redis=checks["redis"])
```

---

_Reviewed: 2026-07-10_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
