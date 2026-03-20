# Architecture

## System Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      Data Sources                           │
├────────────┬───────────────┬────────────────┬───────────────┤
│CrowdStrike │    Nessus     │   Defender     │     Wiz       │
└─────┬──────┴───────┬───────┴───────┬────────┴───────┬───────┘
      │              │               │                │
      └──────────────┴───────┬───────┴────────────────┘
                             │
                    ┌────────▼─────────┐
                    │   GetVul API     │
                    │   (FastAPI)      │
                    │   Python 3.12   │
                    └────────┬─────────┘
                             │
                ┌────────────┼────────────────┐
                │            │                │
       ┌────────▼──────┐ ┌──▼────────┐ ┌─────▼──────┐
       │  PostgreSQL   │ │   Redis   │ │  Jamf MDM  │
       │  (RDS)        │ │  (cache)  │ │ enrichment │
       └────────┬──────┘ └───────────┘ └────────────┘
                │
       ┌────────▼──────────┐
       │   Frontend        │
       │   (Next.js 14)    │
       │   TypeScript      │
       └────────┬──────────┘
                │
       ┌────────▼──────────┐
       │   Ticketing       │
       │   (Jira / GitHub) │
       └───────────────────┘
```

## Tech Stack

### Backend
| Component | Technology |
|-----------|-----------|
| Framework | FastAPI (Python 3.12) |
| Database | PostgreSQL 16 (asyncpg async driver) |
| ORM | SQLAlchemy 2.0 (async) |
| Cache/Queue | Redis 7 |
| Auth | JWT (python-jose), OAuth 2.0 OIDC (Google, Azure) |
| HTTP Client | httpx (async) |
| Encryption | cryptography (Fernet symmetric) |
| Scheduler | APScheduler (background sync jobs) |
| Validation | Pydantic 2.0 |
| Retry Logic | Tenacity |
| Logging | structlog |
| Migrations | Alembic |

### Frontend
| Component | Technology |
|-----------|-----------|
| Framework | Next.js 14.2 (React 18.3) |
| Language | TypeScript 5.5 |
| Styling | Tailwind CSS 3.4 + PostCSS |
| Icons | Lucide React |
| Charts | Recharts |
| HTTP | Native fetch API (with wrapper) |

### Infrastructure
| Component | Technology |
|-----------|-----------|
| Containers | Docker + Docker Compose |
| IaC | Terraform 1.7 (AWS) |
| CI/CD | GitHub Actions |
| Cloud | AWS (RDS, Secrets Manager) |

## Data Flow — Connector Sync Pipeline

```
1. APScheduler fires based on sync_interval_minutes
       ↓
2. Picks up enabled ConnectorConfig for each tenant
       ↓
3. trigger_background_sync() enqueues task
       ↓
4. Worker calls run_sync(connector_config)
       ↓
5. Connector instantiated (e.g., CrowdStrikeConnector)
       ↓
6. authenticate(credentials, config) → obtains access token
       ↓
7. fetch_vulnerabilities() → list[NormalizedVulnerability]
       ↓
8. For each vulnerability:
     a. _upsert_asset() → get-or-create Asset by hostname
     b. _upsert_vulnerability() → get-or-create Vulnerability
     c. Update asset.seen_by_sources array
       ↓
9. fetch_misconfigurations() → list[NormalizedMisconfiguration]
       ↓
10. For each misconfiguration: _upsert_misconfiguration()
       ↓
11. SyncLog recorded (status, counts, errors)
       ↓
12. ConnectorConfig.last_sync_at/status/record_count updated
```

## Device Classification Flow

```
1. Assets ingested from any source (device_category = null)
       ↓
2. Admin triggers POST /api/v1/assets/classify
       ↓
3. For each unclassified asset, classify by priority:
     a. CrowdStrike product_type_desc mapping
     b. Hostname patterns (regex)
     c. OS patterns (Windows/macOS/Linux/mobile)
     d. Platform hints
     e. Default to OTHER
       ↓
4. device_category updated on Asset record
```

## Correlation Process

After vulnerabilities are ingested, a correlation pass identifies the same CVE detected by multiple scanners on the same asset:

1. Query vulnerabilities grouped by `(tenant_id, cve_id, asset_id)`
2. Where `COUNT(DISTINCT source) > 1`
3. Create/update `VulnerabilityCorrelation` record
4. Set `sources_count` and `confidence` (HIGH if 3+ sources, MEDIUM if 2)

## Project Structure

```
getvul/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI entry point
│   │   ├── config.py               # Settings (env vars)
│   │   ├── encryption.py           # Fernet encrypt/decrypt
│   │   ├── pagination.py           # Shared pagination logic
│   │   ├── dependencies.py         # FastAPI dependency aliases
│   │   ├── seed.py                 # Demo data seeder
│   │   ├── dev_routes.py           # Dev-only endpoints
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
│   │   │   ├── schemas.py          # Connector type metadata + Pydantic models
│   │   │   └── router.py           # Connector API routes
│   │   ├── vulnerabilities/        # Vulnerability management
│   │   │   ├── models.py           # SQLAlchemy models
│   │   │   ├── service.py          # Query/filter/stats service
│   │   │   ├── remediation_service.py  # Grouped remediations
│   │   │   ├── schemas.py          # Pydantic request/response models
│   │   │   └── router.py           # Vulnerability API routes
│   │   ├── assets/                 # Asset management
│   │   │   ├── models.py           # Asset model
│   │   │   ├── classification.py   # Device type classification
│   │   │   ├── service.py          # Asset query service
│   │   │   ├── schemas.py          # Pydantic models
│   │   │   └── router.py           # Asset API routes
│   │   ├── cspm/                   # Cloud posture management
│   │   │   ├── models.py           # Misconfiguration model
│   │   │   ├── service.py          # CSPM query service
│   │   │   ├── schemas.py          # Pydantic models
│   │   │   └── router.py           # CSPM API routes
│   │   └── tickets/                # Ticketing integration
│   │       ├── models.py           # Ticket + TicketRule models
│   │       ├── service.py          # Ticket CRUD service
│   │       └── router.py           # Ticket API routes
│   ├── alembic/                    # Database migrations
│   │   └── versions/               # Migration scripts
│   ├── tests/                      # pytest tests
│   ├── pyproject.toml              # Python dependencies
│   ├── Dockerfile                  # Backend container
│   └── alembic.ini                 # Alembic config
├── frontend/
│   ├── src/
│   │   ├── app/                    # Next.js pages
│   │   │   ├── layout.tsx          # Root layout
│   │   │   ├── page.tsx            # Login page
│   │   │   └── dashboard/          # Dashboard pages
│   │   ├── components/             # React components
│   │   ├── lib/                    # API client, utilities
│   │   └── types/                  # TypeScript type definitions
│   ├── package.json                # Node dependencies
│   ├── Dockerfile                  # Frontend container
│   ├── tailwind.config.ts          # Tailwind configuration
│   └── tsconfig.json               # TypeScript config
├── infra/                          # Terraform IaC
│   └── main.tf                     # AWS provider setup
├── .github/workflows/ci.yml       # CI/CD pipeline
├── docker-compose.yml              # Local development
├── Makefile                        # Dev commands
└── .env.example                    # Environment template
```
