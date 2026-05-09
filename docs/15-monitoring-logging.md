# 15 — Monitoring & Logging

GetVul today ships **structured backend logs** and an **audit log** that can forward to a SIEM in CEF format. There is no metrics pipeline (Prometheus / OpenTelemetry / Datadog) and no synthetic monitoring. Phase 7 (PROD-07: Health and Observability) will close some of these gaps.

## Logs

### Backend (structured, via `structlog`)

The backend uses [`structlog`](https://www.structlog.org/) (≥ 24.0) — see [backend/pyproject.toml](../backend/pyproject.toml). Every module instantiates a logger:

```python
import structlog
logger = structlog.get_logger()
```

Logs go to **stdout** of the backend container by default. Notable event names you'll see in `docker compose logs -f backend`:

| Event name | Where | Meaning |
|------------|-------|---------|
| `sync_scheduler_started` | [scheduler.py](../backend/app/connectors/scheduler.py) | In-process scheduler tick loop is up |
| `background_sync_start` / `background_sync_complete` | scheduler | Connector sync start/end with `connector_id`, `connector_type`, `records_*`, `status` |
| `scheduler_triggering_sync` | scheduler | A connector is due |
| `ticket_rules_completed` | scheduler | Automation pass finished |
| `sla_breached_notification` | notifications | An SLA-breach alert was created |
| `redis_unavailable` | [main.py:141-146](../backend/app/main.py#L141-L146) | Rate limiter caught `RedisError` (subsystem=`rate_limiter`) — fail-OPEN path |
| `rate_limit_exceeded` | rate limiter | A tenant hit the 200/60s ceiling |
| `scheduled_report_failed` | reports | fpdf2 / SMTP error during report send |

SQLAlchemy emits its own INFO logs when `DEBUG=true` (raw SQL on every query) — these can be voluminous. In production keep `DEBUG=false`.

### Frontend

Next.js logs go to the frontend container's stdout. Production builds suppress most output. There is no client-side error reporter (Sentry / Bugsnag) wired up.

### Nginx

Standard Nginx access + error logs at `/var/log/nginx/access.log` and `/var/log/nginx/error.log` inside the container ([nginx/nginx.conf:25-26](../nginx/nginx.conf#L25-L26)). They are not rotated by anything in the repo — for production, mount them to a log driver or volume.

### Postgres / Redis

Container-default logging only. Postgres logs go through asyncpg back into structlog when `DEBUG=true` (see above).

## Audit log

A separate, structured, **persistent** log of every mutating user action.

| Concern | Where |
|---------|-------|
| Storage | Postgres `audit_logs` table ([09-data-model.md](09-data-model.md#audit_logs)) |
| Helper | `await audit(db, user, action, resource_type, resource_id, details)` in [backend/app/audit.py](../backend/app/audit.py) |
| Categories logged | `auth.*`, `vuln.*`, `asset.*`, `ticket.*`, `rule.*`, `user.*`, `settings.*`, `cert.*`, `export.*`, `report.*` (see [16-security.md](16-security.md) for the full matrix) |
| UI | `Settings → Audit Log` (Admin+) — filterable table |
| API | `GET /api/v1/tenant/audit-log` (Admin+) |

### CEF / syslog forwarding

`tenants.syslog_config` (JSONB) holds per-tenant syslog config:

```json
{
  "enabled": true,
  "host": "siem.example.com",
  "port": 514,
  "protocol": "udp",
  "facility": "local0"
}
```

If `enabled: true`, the backend calls `configure_syslog(host, port, protocol, facility)` at startup ([main.py:62-68](../backend/app/main.py#L62-L68)), wiring a Python `logging.handlers.SysLogHandler`. Subsequent audit events are forwarded in **CEF (Common Event Format)**:

```
CEF:0|GetVul|VulnMgmt|1.0|auth.login|auth.login|5|suser=admin@company.com act=auth.login cs1=user cs1Label=ResourceType msg={"method":"password"} rt=2026-03-20T13:55:47Z
```

Compatible with Splunk, IBM QRadar, Microsoft Sentinel, Elastic SIEM, and any CEF-capable receiver. UDP and TCP both supported. Facilities: `local0`–`local7`, `auth`, `authpriv`.

> Note: only the **first tenant**'s `syslog_config` is consumed at startup ([main.py:61](../backend/app/main.py#L61)). For multi-tenant deployments this is a known limitation — it works for single-tenant installs (the GetVul deployment model today).

## Health checks

| Endpoint | What it does | Used by |
|----------|--------------|---------|
| `GET /health` | Returns `{"status":"ok","service":"getvul-api"}` immediately. Does **not** check DB or Redis. | Docker Compose, CD verification, load-balancer probes |

Phase 7 (PROD-07-01) will add a separate liveness vs readiness check and surface DB / Redis connectivity. Today, a backend that has lost its DB connection still returns 200 from `/health` until uvicorn itself crashes.

## Metrics

**None today.** No Prometheus exporter, no OpenTelemetry, no Datadog/New Relic agent. The dashboard charts you see in `/dashboard` are computed on-demand from Postgres data, not from a metrics store.

If you need observability into request rates, latencies, queue depth, etc., you'll need to:

1. Add `prometheus-fastapi-instrumentator` (or similar) for HTTP-level metrics.
2. Wrap connector syncs with explicit timers, emit structlog events, and scrape them with a log-based metrics collector.

This is intentionally not in v1.0.

## Dashboards

There are no Grafana / Kibana / Splunk dashboards shipped. The application's built-in dashboard at `/dashboard` is the only operator view today, and it's product-data-focused (vulns, assets, SLA), not infra-focused.

## Alerts

Two distinct alerting systems exist; don't confuse them.

### In-product notifications (security-event alerts)

The 4-check engine emits to `notifications` and SMTP — see [02-architecture.md](02-architecture.md#notification-engine):

| Check | Lookback | Notify whom |
|-------|----------|-------------|
| New critical vulnerability | 2h | OWNER + ADMIN by email + bell badge |
| SLA breach within 24h | 24h | OWNER + ADMIN by email + bell badge |
| Connector sync failure | 4h | bell badge (no email by default) |
| Risk score spike (≥20pt day-over-day) | 24h | bell badge |

### Infra/ops alerts

**None configured.** No PagerDuty integration, no Opsgenie, no Slack webhook, no email-on-CI-failure. CD deployment success/failure is visible only in the GitHub Actions UI.

Phase 7 may add a Slack webhook for sync failures and CD deploys — not yet scoped.

## Sampling and retention

| Stream | Retention |
|--------|-----------|
| Backend stdout logs | Whatever Docker / your log driver retains. No rotation in repo. |
| Audit log (`audit_logs`) | Indefinite — Postgres rows. Manual archival required. |
| Daily snapshots (`daily_snapshots`) | Indefinite — Postgres rows. |
| Sync logs (`sync_logs`) | Indefinite. Trim manually if it gets large. |
| Notifications (`notifications`) | Indefinite (users delete via the UI). |
| Postgres data | Whatever your backup policy says. Repo does not configure one (see [13-deployment.md](13-deployment.md#backups)). |
| Redis | None — in-memory only, lost on container restart by design. |
| GitHub Actions artefacts (ZAP reports, codecov XML) | GitHub default (90 days for artefacts). |

## Recommended additions (post-v1.0)

- A real `/healthz` that pings DB + Redis (PROD-07-01).
- A `/readyz` separate from `/healthz` (PROD-07-02).
- JSON log formatter so log shippers (Vector, Fluent Bit) can parse uniformly.
- Prometheus metrics for HTTP request count/latency/errors and scheduler tick health.
- A Grafana dashboard or Kibana saved view derived from those metrics.
- Slack/email alerting on CD failure or sync-failure spikes.
- Postgres backups (`pg_dump` to off-host bucket, nightly).
