# Architecture

## System Diagram

```
┌────────────────────────────────────────────────────────────────────────┐
│                         Data Sources                                   │
├──────────┬────────┬──────────┬──────┬─────────┬────────────┬──────────┤
│CrowdStrike│ Nessus │ Defender │ Wiz  │ Qualys  │  Rapid7    │          │
└─────┬─────┴───┬────┴────┬─────┴──┬───┴────┬────┴─────┬──────┘          │
      │         │         │        │        │          │                 │
      └─────────┴─────────┴───┬────┴────────┴──────────┘                 │
                              │                                          │
├──────────┬──────────┬───────┤────────┬──────────┬─────────────────────┤
│ Humaans  │ Jamf Pro │ Intune│  Okta  │  Google  │  Azure Entra ID    │
│  (HR)    │  (MDM)   │ (MDM) │ (IdP)  │  (IdP)   │     (IdP)          │
└─────┬────┴────┬─────┴──┬────┴───┬────┴────┬─────┴────────┬───────────┘
      └─────────┴────────┴────────┴─────────┴──────────────┘
                              │
                     ┌────────▼──────────┐
                     │     Nginx         │
                     │  TLS 1.2/1.3      │
                     │  Rate Limiting    │
                     └────────┬──────────┘
                              │
                 ┌────────────┼───────────────┐
                 │            │               │
        ┌────────▼──────┐ ┌──▼────────┐ ┌────▼───────┐
        │  Backend API  │ │  Frontend  │ │  Redis     │
        │  (FastAPI)    │ │  (Next.js  │ │  (cache)   │
        │  Python 3.12  │ │   15)      │ └────────────┘
        └────────┬──────┘ └───────────┘
                 │
        ┌────────▼──────┐
        │  PostgreSQL   │
        │  16           │
        └────────┬──────┘
                 │
        ┌────────▼──────────┐     ┌──────────────┐
        │  Ticketing        │     │  SMTP        │
        │  (Asana / Jira)   │     │  (Reports)   │
        └───────────────────┘     └──────────────┘
```

## Tech Stack

### Backend
| Component | Technology |
|-----------|-----------|
| Framework | FastAPI (Python 3.12) |
| Database | PostgreSQL 16 (asyncpg async driver) |
| ORM | SQLAlchemy 2.0 (async) |
| Migrations | Alembic (22 migrations) |
| Cache/Queue | Redis 7 |
| Auth | JWT (python-jose), OAuth 2.0 OIDC (Google, Azure) |
| HTTP Client | httpx (async) |
| Encryption | cryptography (Fernet symmetric) |
| Scheduler | APScheduler (background sync jobs) |
| Validation | Pydantic 2.0 |
| Retry Logic | Tenacity |
| Logging | structlog |
| PDF Reports | fpdf2 |

### Frontend
| Component | Technology |
|-----------|-----------|
| Framework | Next.js 15 (React 19) |
| Language | TypeScript |
| Styling | Tailwind CSS + PostCSS |
| Icons | Lucide React |
| Charts | Recharts |
| HTTP | Native fetch API (with wrapper) |

### Infrastructure
| Component | Technology |
|-----------|-----------|
| Containers | Docker + Docker Compose (5 services) |
| IaC | Terraform 1.7 (AWS + GCP) |
| CI/CD | GitHub Actions (5 jobs) |
| Reverse Proxy | Nginx (TLS, rate limiting, security headers) |

## Data Flow -- Connector Sync Pipeline

```
1. APScheduler fires based on sync_interval_minutes
       |
2. Picks up enabled ConnectorConfig for each tenant
       |
3. trigger_background_sync() enqueues task
       |
4. Worker calls run_sync(connector_config)
       |
5. Connector instantiated (e.g., CrowdStrikeConnector)
       |
6. authenticate(credentials, config) -> obtains access token
       |
7. fetch_vulnerabilities() -> list[NormalizedVulnerability]
       |
8. For each vulnerability:
     a. _upsert_asset() -> get-or-create Asset by hostname
     b. _upsert_vulnerability() -> get-or-create Vulnerability
     c. Update asset.seen_by_sources array
       |
9. fetch_misconfigurations() -> list[NormalizedMisconfiguration]
       |
10. For each misconfiguration: _upsert_misconfiguration()
       |
11. SyncLog recorded (status, counts, errors)
       |
12. ConnectorConfig.last_sync_at/status/record_count updated
       |
13. Enrichment pass: Jamf/Humaans/Intune data merged into assets
       |
14. Classification pass: unclassified assets assigned device_category
       |
15. Risk score recalculation for affected assets
       |
16. Correlation pass: detect same CVE across multiple scanners
```

## Device Classification Flow

```
1. Assets ingested from any source (device_category = null)
       |
2. Admin triggers POST /api/v1/assets/classify
       |
3. For each unclassified asset, classify by priority:
     a. CrowdStrike product_type_desc mapping
     b. Hostname patterns (regex)
     c. OS patterns (Windows/macOS/Linux/mobile)
     d. Platform hints
     e. Default to OTHER
       |
4. device_category updated on Asset record
```

## Risk Scoring Algorithm

```
1. Raw score = SUM(severity_weight * exploit_multiplier * kev_multiplier)
     - Severity weights: CRITICAL=40, HIGH=10, MEDIUM=3, LOW=1
     - Exploit multiplier: 2x if exploit_available
     - KEV multiplier: 1.5x if in CISA KEV catalog

2. Piecewise log curve normalization (0-100 scale):
     - Knee point: raw=120 maps to score=45
     - Below knee: linear scaling
     - Above knee: logarithmic compression
```

## Correlation Process

After vulnerabilities are ingested, a correlation pass identifies the same CVE detected by multiple scanners on the same asset:

1. Query vulnerabilities grouped by `(tenant_id, cve_id, asset_id)`
2. Where `COUNT(DISTINCT source) > 1`
3. Create/update `VulnerabilityCorrelation` record
4. Set `sources_count` and `confidence` (HIGH if 3+ sources, MEDIUM if 2)

## Notification and Alert Engine Flow

```
1. APScheduler triggers alert checks on schedule
       |
2. run_alert_checks() iterates all active tenants
       |
3. For each tenant, runs 4 automated checks:
     a. _check_new_critical_vulns() — CRITICAL vulns detected in last 2 hours
     b. _check_sla_breaches() — vulns with SLA due within 24 hours
     c. _check_sync_failures() — enabled connectors with failed sync status
     d. _check_risk_score_changes() — assets with 20+ point risk spike vs yesterday
       |
4. Deduplication: checks if matching notification already exists
   within lookback window (2h / 24h / 4h per check type)
       |
5. Creates Notification record (broadcast or user-targeted)
       |
6. Sends email to OWNER and ADMIN users (for critical alerts)
       |
7. Frontend polls /api/v1/notifications/unread-count for bell badge
```

## GCP Deployment Architecture

```
┌─────────────────────────────────────────────────┐
│              Google Cloud Platform                │
│                                                   │
│  ┌──────────────┐     ┌───────────────────────┐  │
│  │  Static IP    │────>│  GCE VM (COS image)   │  │
│  │  (External)   │     │                       │  │
│  └──────────────┘     │  ┌─────────────────┐   │  │
│                       │  │ Docker Compose   │   │  │
│  ┌──────────────┐     │  │  - nginx         │   │  │
│  │  Firewall     │     │  │  - backend       │   │  │
│  │  (80, 443,    │     │  │  - frontend      │   │  │
│  │   SSH)        │     │  │  - postgres      │   │  │
│  └──────────────┘     │  │  - redis         │   │  │
│                       │  └─────────────────┘   │  │
│  ┌──────────────┐     │                       │  │
│  │  Service      │     │  Auto-update cron    │  │
│  │  Account      │     │  (daily at 3 AM UTC) │  │
│  └──────────────┘     └───────────────────────┘  │
└─────────────────────────────────────────────────┘

Terraform provisions: static IP, firewall rules, service account, GCE VM
Startup script: installs Docker, clones repo, starts app, sets up cron
Auto-update: checks GitHub releases daily, pulls latest, restarts services
```

## Daily Snapshot Pipeline

```
1. Scheduler triggers daily at configured time
       |
2. Computes current metrics per tenant:
     - Total/open vulnerabilities by severity
     - Risk score distribution
     - SLA compliance stats
     - MTTR calculation
       |
3. Stores snapshot in daily_snapshots table
       |
4. Dashboard trend charts query snapshot history
```

## Project Structure

```
getvul/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI entry, health, export, reports, certs
│   │   ├── config.py               # Settings (env vars)
│   │   ├── encryption.py           # Fernet encrypt/decrypt
│   │   ├── pagination.py           # Shared pagination logic
│   │   ├── dependencies.py         # FastAPI dependency aliases
│   │   ├── seed.py                 # Demo data seeder
│   │   ├── dev_routes.py           # Dev-only endpoints
│   │   ├── export.py               # CSV export service
│   │   ├── reports.py              # Scheduled reports model + CRUD
│   │   ├── email.py                # SMTP email delivery
│   │   ├── certificates.py         # TLS cert management
│   │   ├── audit.py                # Audit logging + syslog/SIEM
│   │   ├── enrich_assets.py        # Asset enrichment from HR/MDM
│   │   ├── auth/                   # Authentication module
│   │   │   ├── jwt.py              # JWT create/decode
│   │   │   ├── providers.py        # OIDC providers (Google, Azure)
│   │   │   ├── router.py           # Auth routes
│   │   │   ├── rbac.py             # Role-based access control
│   │   │   └── dependencies.py     # Auth dependencies
│   │   ├── db/                     # Database layer
│   │   │   ├── session.py          # Async engine, session factory
│   │   │   └── base.py             # Base classes, mixins
│   │   ├── connectors/             # External integrations
│   │   │   ├── base.py             # Abstract connector + normalized types
│   │   │   ├── crowdstrike.py      # CrowdStrike Falcon connector
│   │   │   ├── jamf.py             # Jamf Pro MDM connector
│   │   │   ├── sync.py             # Sync orchestration
│   │   │   ├── scheduler.py        # APScheduler background jobs
│   │   │   ├── tester.py           # Connector credential testing
│   │   │   ├── service.py          # Connector CRUD service
│   │   │   ├── schemas.py          # All 14 connector type definitions
│   │   │   └── router.py           # Connector API routes
│   │   ├── vulnerabilities/        # Vulnerability management
│   │   │   ├── models.py           # Vulnerability + Correlation models
│   │   │   ├── service.py          # Query/filter/stats/SLA service
│   │   │   ├── remediation_service.py  # Grouped remediations
│   │   │   ├── schemas.py          # Pydantic request/response models
│   │   │   └── router.py           # Vulnerability API routes
│   │   ├── assets/                 # Asset management
│   │   │   ├── models.py           # Asset model
│   │   │   ├── classification.py   # Device type classification
│   │   │   ├── service.py          # Asset query + risk scoring
│   │   │   ├── schemas.py          # Pydantic models
│   │   │   └── router.py           # Asset API routes
│   │   ├── cspm/                   # Cloud posture management
│   │   │   ├── models.py           # Misconfiguration model
│   │   │   ├── service.py          # CSPM query service
│   │   │   ├── schemas.py          # Pydantic models
│   │   │   └── router.py           # CSPM API routes
│   │   ├── ticketing/              # Ticketing integration
│   │   │   ├── models.py           # Ticket, TicketRule, ConnectorConfig, SyncLog
│   │   │   ├── service.py          # Ticket CRUD + automation
│   │   │   └── router.py           # Ticket API routes
│   │   ├── tenants/                # Tenant and user management
│   │   │   ├── models.py           # Tenant + User models
│   │   │   ├── service.py          # Tenant/user CRUD
│   │   │   └── router.py           # Tenant API routes
│   │   ├── users/                  # User directory views
│   │   │   └── router.py           # User list + stats routes
│   │   └── notifications/          # Notification and alert system
│   │       ├── models.py           # Notification model
│   │       ├── service.py          # Notification CRUD + email delivery
│   │       ├── router.py           # Notification API routes
│   │       └── alerts.py           # Alert engine (4 automated checks)
│   ├── alembic/                    # Database migrations
│   │   └── versions/               # 22 migration scripts
│   ├── tests/                      # pytest test suite
│   ├── pyproject.toml              # Python dependencies
│   ├── Dockerfile                  # Backend container
│   └── alembic.ini                 # Alembic config
├── frontend/
│   ├── src/
│   │   ├── app/                    # Next.js pages
│   │   │   ├── layout.tsx          # Root layout
│   │   │   ├── page.tsx            # Landing/redirect
│   │   │   ├── login/              # Login page
│   │   │   ├── dashboard/          # Main dashboard + sub-pages
│   │   │   ├── vulnerabilities/    # Vulnerability views
│   │   │   ├── assets/             # Asset views
│   │   │   ├── tickets/            # Ticket views
│   │   │   ├── integrations/       # Connector views
│   │   │   └── settings/           # Settings views
│   │   ├── components/             # React components
│   │   ├── lib/                    # API client, utilities
│   │   └── types/                  # TypeScript type definitions
│   ├── package.json                # Node dependencies
│   ├── Dockerfile                  # Frontend container
│   ├── tailwind.config.ts          # Tailwind configuration
│   └── tsconfig.json               # TypeScript config
├── infra/                          # Terraform IaC
│   ├── main.tf                     # AWS provider setup
│   ├── variables.tf                # AWS variables
│   ├── outputs.tf                  # AWS outputs
│   └── gcp/                        # GCP deployment
│       ├── main.tf                 # GCE VM, firewall, static IP, service account
│       ├── variables.tf            # GCP variables
│       ├── outputs.tf              # GCP outputs
│       └── startup.sh              # VM startup script (Docker, clone, auto-update)
├── .github/workflows/ci.yml       # CI/CD pipeline (5 jobs)
├── docker-compose.yml              # Development stack (5 services)
├── docker-compose.ci.yml           # CI DAST testing stack
├── Makefile                        # Dev commands
└── .env.example                    # Environment template
```
