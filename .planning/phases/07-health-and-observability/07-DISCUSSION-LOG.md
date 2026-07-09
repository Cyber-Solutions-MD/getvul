# Phase 7: Health and Observability - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-09
**Phase:** 07-health-and-observability
**Areas discussed:** Nginx health wiring, Readiness failure policy, Readiness body shape, structlog scope, request_id correlation, Alerting scope, Probe access-log noise, Per-check timeout, nginx probe exposure, Test contract, Log redaction, Audit-log separation, /health body back-compat, Log field naming, Scheduler-in-/ready, Prod log level, DB check connection, Inbound request_id trust

---

## Nginx health wiring (PROD-07-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Compose healthcheck → /ready | Flip compose healthcheck + passive upstream block | |
| Passive nginx upstream only | upstream max_fails + /ready location, compose stays on /health | |
| Full: compose + passive + doc | All three + docs on nginx-Plus/external-monitor caveat | ✓ |

**User's choice:** Full: compose + passive + doc
**Notes:** Honest single-VM implementation of SC#3; open-source nginx has no active health probing.

---

## Readiness failure policy (Redis)

| Option | Description | Selected |
|--------|-------------|----------|
| Hard-fail: Redis down → 503 | Spec-literal; both deps must be healthy for 200 | ✓ |
| Redis soft/degraded | Redis down → 200 + degraded:true (would reword SC#2) | |

**User's choice:** Hard-fail: Redis down → 503
**Notes:** Chose spec-literal over the fail-open-reality soft option. Keeps the contract honest; operator runbook (D-20) covers the single-VM de-registration consequence.

---

## Readiness body shape

| Option | Description | Selected |
|--------|-------------|----------|
| Per-dependency detail | status + per-check ok/latency_ms/error, same shape 200/503 | ✓ |
| Minimal status only | {"status":"ready"} / {"status":"not_ready"} | |

**User's choice:** Per-dependency detail

---

## structlog scope (PROD-07-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Unified: fold in stdlib + uvicorn | One JSON stream via ProcessorFormatter | ✓ |
| App logs only | structlog renderer only; uvicorn stays plaintext (mixed stream) | |

**User's choice:** Unified: fold in stdlib + uvicorn

---

## request_id correlation

| Option | Description | Selected |
|--------|-------------|----------|
| Add request_id middleware | Generate/propagate, bind via contextvars, echo header | ✓ |
| No correlation this phase | Standard fields only | |

**User's choice:** Add request_id middleware

---

## Alerting scope (SC#5)

| Option | Description | Selected |
|--------|-------------|----------|
| Loud log + doc runbook | logger.error per failed check + Failure Modes docs section; no new infra | ✓ |
| Build minimal alerting | SMTP-based failure email + background poller | |

**User's choice:** Loud log + doc runbook

---

## Probe access-log noise

| Option | Description | Selected |
|--------|-------------|----------|
| Suppress probe access logs | Filter /health + /ready from uvicorn.access | ✓ |
| Keep all access logs | Log every probe hit | |

**User's choice:** Suppress probe access logs
**Notes:** Failed /ready still emits its explicit check log line.

---

## Per-check timeout mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| asyncio.wait_for per check | Uniform 500ms bound regardless of socket settings | ✓ |
| Dedicated short-timeout clients | Redis socket_timeout=0.5 + PG statement_timeout | |

**User's choice:** asyncio.wait_for per check

---

## nginx probe exposure

| Option | Description | Selected |
|--------|-------------|----------|
| Expose /ready like /health | Public location, mirrors existing /health | ✓ |
| Keep /ready internal-only | Only compose healthcheck reaches it | |

**User's choice:** Expose /ready like /health
**Notes:** Per-dep body carries no sensitive data.

---

## Test contract

| Option | Description | Selected |
|--------|-------------|----------|
| Full matrix | 200/503 matrix + body + timeout path + renderer selection | ✓ |
| Core only | 200/503 matrix only | |

**User's choice:** Full matrix

---

## Log redaction (security)

| Option | Description | Selected |
|--------|-------------|----------|
| Add redaction processor | Scrub authorization/cookie/password/token/secret/credentials/api_key | ✓ |
| No redaction processor | Rely on developer discipline | |

**User's choice:** Add redaction processor
**Notes:** Extends Phase 5's "never log key material" to operational logs.

---

## Audit-log vs app-log separation

| Option | Description | Selected |
|--------|-------------|----------|
| Keep fully separate | CEF/syslog audit pipeline untouched; structlog is ops-only | ✓ |
| Unify under structlog | Route audit through structlog (risks CEF-format break) | |

**User's choice:** Keep fully separate

---

## /health body back-compat

| Option | Description | Selected |
|--------|-------------|----------|
| Keep verbatim | {"status":"ok","service":"getvul-api"} unchanged | ✓ |
| Mirror /ready shape | Restructure for consistency | |

**User's choice:** Keep verbatim

---

## Log field/timestamp naming

| Option | Description | Selected |
|--------|-------------|----------|
| structlog defaults | timestamp (ISO-8601 UTC), level, logger, event | ✓ |
| ECS/ELK-tuned keys | @timestamp, log.level, message | |

**User's choice:** structlog defaults
**Notes:** No aggregator chosen — avoid premature coupling.

---

## Scheduler-liveness in /ready

| Option | Description | Selected |
|--------|-------------|----------|
| Keep /ready DB+Redis only | Scheduler health deferred | ✓ |
| Add scheduler to /ready | Dead scheduler de-registers node | |

**User's choice:** Keep /ready DB+Redis only

---

## Prod log-level threshold

| Option | Description | Selected |
|--------|-------------|----------|
| INFO in prod | Keeps request traces + operational breadcrumbs | ✓ |
| WARNING in prod | Quietest/cheapest; loses routine traces | |

**User's choice:** INFO in prod (DEBUG in dev)

---

## DB check: shared vs dedicated connection

| Option | Description | Selected |
|--------|-------------|----------|
| Shared app pool | Reflects real serving capacity; pool-exhaustion → not-ready | ✓ |
| Dedicated probe connection | Isolates probe from app load (masks pool saturation) | |

**User's choice:** Shared app pool

---

## Inbound request_id trust

| Option | Description | Selected |
|--------|-------------|----------|
| Honor inbound, bounded | Reuse valid X-Request-ID (len≤128, safe charset), else UUID4 | ✓ |
| Always server-generated | Ignore inbound; always UUID4 | |

**User's choice:** Honor inbound, bounded

---

## Claude's Discretion

- Exact `configure_logging()` call-site; processor ordering (redaction before render); helper/function names; precise nginx location phrasing; docs file placement; request_id middleware as new class vs folded.

## Deferred Ideas

- Scheduler health surface; real alerting infrastructure; log-aggregator/ECS field mapping; multi-replica load balancing. All deliberately bounded out — none were scope creep.
