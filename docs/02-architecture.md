# 02 — Architecture

GetVul is a single-VM, container-based application. Five Docker services sit behind one Nginx reverse proxy. All scanner integrations are pull-based and run in an in-process scheduler inside the FastAPI backend.

## High-level system

```mermaid
flowchart TB
    subgraph "External integrations"
        SCN["6 scanners<br/>CrowdStrike · Nessus · Defender<br/>Wiz · Qualys · Rapid7"]
        IDP["3 IdPs<br/>Google · Azure · Okta"]
        MDM["3 MDM/HR<br/>Jamf · Intune · Humaans"]
        TKT["Ticketing<br/>Jira · Asana"]
        SMTP["SMTP server"]
        SIEM["Syslog/SIEM (CEF)"]
    end

    subgraph "User"
        BROW[Browser]
    end

    subgraph "Single VM (Docker Compose)"
        NGX["nginx<br/>:80, :443<br/>TLS, security headers, rate limit"]
        FE["frontend<br/>Next.js 15 / React 19<br/>:3000"]
        BE["backend<br/>FastAPI + SQLAlchemy 2.0 async<br/>:8000<br/>+ in-process scheduler"]
        PG[("postgres :5432<br/>JSONB, 24 migrations")]
        RED[("redis :6379<br/>OIDC state · rate limiter")]
    end

    BROW -->|HTTPS| NGX
    NGX -->|/| FE
    NGX -->|/api/, /auth/| BE
    FE -->|fetch /api/| BE
    BE --> PG
    BE --> RED
    BE -->|pull| SCN
    BE -->|pull| IDP
    BE -->|pull| MDM
    BE -->|push| TKT
    BE -->|send| SMTP
    BE -->|forward| SIEM
```

Source: [diagrams/architecture-system.mmd](diagrams/architecture-system.mmd).

## Request flow (browser → API)

```mermaid
sequenceDiagram
    participant U as Browser
    participant N as nginx
    participant F as frontend (Next.js)
    participant B as backend (FastAPI)
    participant R as Redis
    participant P as Postgres

    U->>N: GET https://app/dashboard
    N->>F: proxy_pass /
    F-->>U: HTML + JS bundle
    U->>F: useAuth() loads token from localStorage
    U->>N: GET /api/v1/vulnerabilities/stats<br/>Authorization: Bearer <jwt>
    N->>B: proxy_pass /api/ (rate-limited 30 r/s)
    B->>B: SecurityHeaders middleware
    B->>B: TenantRateLimit middleware
    B->>R: ZREMRANGEBYSCORE / ZADD / ZCARD / EXPIRE
    R-->>B: count
    B->>B: get_current_user → JWT decode
    B->>P: SELECT ... WHERE tenant_id = $1
    P-->>B: rows
    B-->>U: JSON
```

Middleware order is wired in [backend/app/main.py:179-188](../backend/app/main.py#L179-L188): `CORSMiddleware` → `SecurityHeadersMiddleware` → `TenantRateLimitMiddleware`.

## Connector sync pipeline

The in-process scheduler ([backend/app/connectors/scheduler.py](../backend/app/connectors/scheduler.py)) wakes every ~60s and runs four parallel workstreams.

```mermaid
flowchart TD
    A[Scheduler tick<br/>~60s] --> B{For each tenant}
    B --> C[Connector syncs<br/>due if last_sync_at + sync_interval_minutes &lt;= now]
    B --> D[Ticket rules<br/>run_all_due_rules]
    B --> E[Scheduled reports<br/>run_due_reports]
    B --> F[SLA breach checks<br/>check_sla_breaches]

    C --> G[run_sync per connector]
    G --> H[authenticate]
    H --> I[fetch_vulnerabilities + fetch_misconfigurations]
    I --> J[upsert Asset, Vulnerability, Misconfiguration]
    J --> K[Asset enrichment Jamf/Humaans/Intune]
    K --> L[Device classification]
    L --> M[Risk score recompute]
    M --> N[Cross-source correlation]
    N --> O[SyncLog row]

    D --> D1[Evaluate filter -> create per-host or per-remediation tickets]
    E --> E1[Generate PDF/CSV/TXT -> SMTP send]
    F --> F1[Mark sla_breached, emit notifications + email]
```

Source: [diagrams/sync-pipeline.mmd](diagrams/sync-pipeline.mmd).

## Authentication flow (OIDC, post-Phase 1)

```mermaid
sequenceDiagram
    participant U as User
    participant F as Frontend
    participant B as Backend (any replica)
    participant R as Redis (db 0)
    participant P as Provider (Google/Azure)

    U->>F: Click "Sign in with Google"
    F->>B: GET /auth/login/google?tenant_id=...
    B->>B: generate state token (256-bit)
    B->>R: SET oidc:state:{state} provider EX 600 NX
    R-->>B: OK
    B-->>F: { authorization_url }
    F-->>U: redirect to provider
    U->>P: authenticate
    P-->>U: redirect to /auth/callback/google?code=...&state=...
    U->>B: GET /auth/callback/google?code=...&state=...<br/>(may land on a DIFFERENT replica)
    B->>R: GETDEL oidc:state:{state}
    R-->>B: provider | nil
    alt state missing or wrong provider
        B-->>F: 400 invalid_state
    else state valid
        B->>P: exchange code for tokens
        P-->>B: id_token, access_token
        B->>B: upsert user, issue JWT access + refresh
        B-->>F: { access_token, refresh_token }
    end
```

The `SET ... NX EX 600` + `GETDEL` pair is what makes the flow safe across replicas: the state can be created by one replica and consumed by another, and replay is blocked because `GETDEL` is atomic. If Redis is unreachable the backend fails closed (HTTP 503) — bypassing state validation would be a CSRF defect (decision D-06 in [.planning/phases/01-multi-replica-state/01-CONTEXT.md](../.planning/phases/01-multi-replica-state/01-CONTEXT.md)).

## Rate-limiter mechanics

`TenantRateLimitMiddleware` ([backend/app/main.py:107-159](../backend/app/main.py#L107-L159)) implements a sliding-window rate limit per tenant using a Redis sorted set:

1. Extract `tenant_id` from JWT (without DB validation; "anonymous" if missing).
2. Build key `ratelimit:{tenant_id}`.
3. In one `MULTI/EXEC` pipeline: `ZREMRANGEBYSCORE` (drop entries older than the window), `ZADD` (insert `{now_ms}:{uuid8}` with score `now_ms`), `ZCARD` (count), `EXPIRE` (set TTL = window).
4. If `ZCARD > 200` → return 429 with `Retry-After`.
5. On `RedisError` → log `redis_unavailable` and **fail open** (limiter is a safety valve, not a security boundary — decision D-05).

The unique uuid suffix on the ZADD member defeats sub-millisecond ZADD coalescing — verified by the 6-test suite in [backend/tests/test_rate_limit.py](../backend/tests/test_rate_limit.py).

## Risk scoring

Per-asset risk score computation ([backend/app/assets/service.py](../backend/app/assets/service.py)):

```
raw = Σ severity_weight × exploit_multiplier × kev_multiplier
        severity_weights:    CRITICAL=40 HIGH=10 MEDIUM=3 LOW=1
        exploit_multiplier:  2.0 if exploit_available else 1.0
        kev_multiplier:      1.5 if cisa_kev else 1.0

score = piecewise_log(raw):
        knee at raw=120, score=45
        below knee → linear
        above knee → log compression to 100
```

Triggered by `POST /api/v1/assets/recompute-risk-scores` (Admin+) and automatically after each connector sync.

## Cross-source correlation

After every vulnerability sync, the correlation pass groups vulns by `(tenant_id, cve_id, asset_id)` and emits a `vulnerability_correlations` row when `COUNT(DISTINCT source) > 1`. Confidence: `HIGH` if ≥3 sources, `MEDIUM` if 2.

## Notification engine

Four scheduled checks per active tenant:

| Check | Lookback | Dedup key |
|-------|----------|-----------|
| New critical vuln | 2h | `(tenant_id, category, cve_id)` |
| SLA breach warning | 24h | `(tenant_id, category, cve_id)` |
| Connector sync failure | 4h | `(tenant_id, category, connector_id)` |
| Risk score spike | 24h | `(tenant_id, category, asset_id)` |

Notifications are stored in `notifications` table (broadcast or per-user) and emailed to OWNER + ADMIN for critical events. Frontend polls `/api/v1/notifications/unread-count` for the bell badge.

## Single-VM deployment topology

```mermaid
flowchart LR
    subgraph "Cloud (GCP / AWS / Azure)"
        STIP[Static IP]
        FW[Firewall: 80, 443, 22 from allowlist]
        VM["VM: e2-medium / t3.medium / Standard_B2s<br/>30GB SSD, COS or Ubuntu 22.04"]
        SA[Service account / IAM role]
    end
    subgraph "VM"
        DC["Docker Compose<br/>nginx · backend · frontend · postgres · redis"]
    end
    STIP --> FW --> VM
    VM --> DC
```

Terraform templates exist for all three clouds ([infra/gcp/](../infra/gcp/), [infra/aws/](../infra/aws/), [infra/azure/](../infra/azure/)). GCP is primary; the others validate in CI but are not actively deployed. See [13-deployment.md](13-deployment.md).

## Project structure

For the per-folder walkthrough see [07-project-structure.md](07-project-structure.md). For per-module responsibilities see [08-core-modules.md](08-core-modules.md).
