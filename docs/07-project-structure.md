# 07 — Project Structure

Annotated tree of the repository. Top-level folders first, then per-area drilldown.

## Top level

```
getvul/
├── backend/                Python 3.12 FastAPI app + Alembic migrations + tests
├── frontend/               Next.js 15 / React 19 / TypeScript app
├── infra/                  Terraform IaC (gcp/, aws/, azure/)
├── nginx/                  Reverse-proxy config + entrypoint + cert dir
├── scripts/                Bootstrap and maintenance shell scripts
├── doc/                    DEPRECATED — content moved into docs/ (this folder)
├── docs/                   ← you are here
├── .github/workflows/      CI + CD GitHub Actions
├── .planning/              GSD planning artefacts (PROJECT, ROADMAP, REQUIREMENTS, phases)
├── .claude/                Claude Code agent config + GSD installation (local tooling)
├── docker-compose.yml      Dev/prod stack (5 services)
├── docker-compose.ci.yml   Slim stack for CI DAST jobs (no nginx, no hot-reload)
├── Makefile                Developer commands (~25 targets)
├── install.sh              7-step VM bootstrap (Docker, certs, .env, migrate, admin, seed)
├── README.md               High-level project README (see PROD-04-02 for scanner-count drift)
├── .env / .env.example     Environment configuration
├── .gitignore              Python + Node + Terraform + secrets patterns
└── .gitleaks.toml          Secret scanner allowlist (dev keys whitelisted)
```

## `backend/`

```
backend/
├── app/
│   ├── main.py                FastAPI factory (create_app), lifespan, middleware,
│   │                          inline /health, /api/v1/export, /api/v1/reports,
│   │                          /api/v1/smtp, /api/v1/certificates routes
│   ├── config.py              pydantic_settings.Settings — every env var
│   ├── dependencies.py        Shared FastAPI Depends aliases
│   ├── redis_client.py        get_redis() FastAPI dep (added in Phase 1)
│   ├── encryption.py          Fernet encrypt_value / decrypt_value
│   ├── audit.py               audit() helper, configure_syslog, CEF formatter
│   ├── pagination.py          PaginationParams + PaginatedResponse[T]
│   ├── email.py               SMTP delivery
│   ├── certificates.py        TLS cert upload / self-sign
│   ├── export.py              CSV exporters per resource
│   ├── reports.py             Scheduled reports model + CRUD
│   ├── enrich_assets.py       Merge MDM/HR/IdP into assets after sync
│   ├── search.py              Global cross-category search router
│   ├── seed.py                Demo data seeder
│   ├── dev_routes.py          /dev/* endpoints (only mounted when DEBUG=true)
│   │
│   ├── auth/                  Auth domain
│   │   ├── router.py          /auth/* routes (login, callback, refresh, password reset)
│   │   ├── jwt.py             JWT issue/decode (HS256)
│   │   ├── providers.py       Google + Azure OIDC discovery, token exchange
│   │   ├── password.py        bcrypt hash + verify, policy validation, history
│   │   ├── rbac.py            Role enum + require_role(min) dependency
│   │   └── dependencies.py    get_current_user, get_optional_user
│   │
│   ├── db/                    DB layer
│   │   ├── base.py            Base class, UUIDPrimaryKeyMixin, TimestampMixin
│   │   └── session.py         Async engine, async_session_factory, get_db()
│   │
│   ├── tenants/               Tenant + User models, tenant settings router
│   ├── users/                 Directory / list views (read-mostly)
│   ├── assets/                Asset model, classification, risk scoring, router
│   ├── vulnerabilities/       Vuln + Correlation models, service, router (25 endpoints)
│   ├── cspm/                  Misconfiguration model, compliance scoring, router
│   ├── ticketing/             Ticket + TicketRule + ConnectorConfig + SyncLog models,
│   │                          Asana + Jira clients, automation rule engine
│   ├── notifications/         Notification model + 4-check alert engine
│   │
│   └── connectors/            All scanner / IdP / MDM / HR connectors
│       ├── base.py            BaseConnector ABC
│       ├── crowdstrike.py     CrowdStrikeConnector
│       ├── nessus.py          NessusConnector
│       ├── defender.py        DefenderConnector
│       ├── wiz.py             WizConnector
│       ├── qualys.py          QualysConnector
│       ├── rapid7.py          Rapid7Connector
│       ├── jamf.py            JamfConnector + jamf_sync.py (separate sync logic)
│       ├── intune_sync.py     Intune device-compliance sync
│       ├── google_workspace.py    Directory + groups
│       ├── azure_entra.py     Directory + groups + tenant config
│       ├── okta_sync.py       Okta directory sync
│       ├── humaans.py + humaans_sync.py   HRIS enrichment
│       ├── jira_client.py + jira_sync.py  Jira REST client + daily ticket sync
│       ├── directory_sync.py  Common directory-merge helpers
│       ├── scheduler.py       In-process async scheduler (~60s tick)
│       ├── sync.py            run_sync orchestration
│       ├── service.py         Connector CRUD service
│       ├── tester.py          Test-credentials before saving
│       ├── schemas.py         All 14 connector type definitions
│       └── router.py          /api/v1/connectors/* routes
│
├── alembic/                   Migration toolkit
│   ├── env.py
│   └── versions/              24 migrations (001 … 024) — see docs/09-data-model.md
│
├── tests/                     pytest suite (950 LOC across 7 files)
│   ├── conftest.py            redis_test_url, flushed_redis, app_factory,
│   │                          single_app, two_apps fixtures (added in Phase 1)
│   ├── test_auth.py
│   ├── test_oidc_state.py     5 Phase-1 tests (Redis SET NX EX 600 + GETDEL)
│   ├── test_rate_limit.py     6 Phase-1 tests (Redis sorted-set sliding window)
│   ├── test_multi_replica.py  4 Phase-1 cross-replica tests
│   ├── test_tenant_isolation.py
│   └── test_vulnerabilities.py
│
├── pyproject.toml             Dependencies + ruff + mypy + pytest config
├── alembic.ini
├── Dockerfile                 python:3.12-slim, uvicorn entrypoint
├── create_admin.py            Idempotent admin bootstrapper
├── seed_data.py               Demo data loader (called by install.sh)
└── .python-version            Local pyenv hint (untracked)
```

## `frontend/`

```
frontend/
├── src/
│   ├── app/                   Next.js App Router pages
│   │   ├── layout.tsx         Wraps in ThemeProvider + AuthProvider
│   │   ├── page.tsx           Redirects → /login
│   │   ├── login/
│   │   ├── dashboard/
│   │   │   ├── layout.tsx     Sidebar + Header + ToastProvider
│   │   │   ├── page.tsx       Main dashboard (~925 LOC)
│   │   │   ├── assets/
│   │   │   ├── vulnerabilities/
│   │   │   ├── tickets/
│   │   │   ├── connectors/
│   │   │   ├── cspm/
│   │   │   ├── users/
│   │   │   └── settings/
│   │   └── globals.css        Theme variables (dark default)
│   ├── components/
│   │   ├── layout/            Sidebar, Header, NotificationBell, GlobalSearch
│   │   ├── ui/                Badge, ConfirmModal, ExportButton, Pagination, Toast
│   │   └── vulnerabilities/   Feature-specific: VulnFilters, VulnTable, BulkActions
│   ├── lib/
│   │   ├── api.ts             fetch wrapper with auto-refresh on 401
│   │   ├── auth.tsx           AuthProvider + useAuth() context
│   │   ├── theme.tsx          ThemeProvider + useTheme() context
│   │   └── utils.ts           cn() helper
│   └── types/                 Per-domain TypeScript types
├── public/                    Static assets
├── Dockerfile                 node:20-alpine, npm install --legacy-peer-deps
├── next.config.js             output: standalone, CSP, transpiledPackages
├── tailwind.config.ts         HSL theme system, content globs
├── tsconfig.json              strict, paths "@/*": "./src/*"
├── package.json               7 deps, 9 devDeps, scripts: dev/build/start/lint
└── package-lock.json
```

> ⚠ `frontend/frontend/` exists as a stray nested directory (only an empty `package-lock.json`) — accidental nesting, scheduled for cleanup. `frontend/tsconfig.tsbuildinfo` is also a build artifact that should be in `.gitignore`.

## `infra/`

```
infra/
├── main.tf                Top-level pointer (comment: "Primary deployment: GCP")
├── variables.tf           Shared variables
├── outputs.tf             Shared outputs
├── gcp/                   PRIMARY — GCE single-VM deploy
│   ├── main.tf            Static IP, firewall, service account, GCE instance (e2-medium)
│   ├── variables.tf       region, zone, machine_type, ssh_user, ssh_public_key, ...
│   ├── outputs.tf         vm_ip, ssh_command, app_url
│   └── startup.sh         VM first-boot: install Docker, clone repo, write .env, compose up
├── aws/                   SECONDARY — EC2 single-VM (Ubuntu 22.04, IMDSv2 required)
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
└── azure/                 SECONDARY — Linux VM (Premium SSD, NSG)
    ├── main.tf
    ├── variables.tf
    └── outputs.tf
```

GCP is the actively deployed target. AWS and Azure templates validate in CI but aren't currently used.

## `nginx/`

```
nginx/
├── nginx.conf             HTTP→HTTPS redirect, TLS 1.2/1.3, security headers,
│                          api zone (30 r/s), auth zone (5 r/s), proxy_pass
│                          to frontend:3000 and backend:8000
├── entrypoint.sh          Auto-generates self-signed cert if missing, then nginx -g
└── certs/                 Mounted volume — server.crt + server.key (gitignored)
```

## `scripts/`

```
scripts/
└── deploy.sh              Manual SSH push: ./scripts/deploy.sh <VM_IP> [SSH_USER]
```

## `.github/`

```
.github/
└── workflows/
    ├── ci.yml             5 jobs: backend, frontend, terraform, semgrep SAST, ZAP DAST
    │                      ⚠ trigger is workflow_dispatch only — push/PR commented out
    └── cd.yml             Triggered by GitHub release published; SSHes to VM, pulls main,
                            rebuilds, health-checks, prunes images
```

No `.github/ISSUE_TEMPLATE/`, `.github/PULL_REQUEST_TEMPLATE.md`, or `.github/CODEOWNERS` yet.

## `.planning/`

GSD workflow output (not a runtime artefact). See [06-development-workflow.md](06-development-workflow.md) for how to read it.

```
.planning/
├── PROJECT.md             Validated + active requirements, decisions
├── REQUIREMENTS.md        Requirement IDs (PROD-01…PROD-08)
├── ROADMAP.md             Phase breakdown for v1.0
├── STATE.md               Current focus
├── config.json            GSD config
└── phases/
    └── 01-multi-replica-state/
        ├── 01-CONTEXT.md          User-decision log (D-05…D-17)
        ├── 01-RESEARCH.md         Technical research (pitfalls, patterns)
        ├── 01-VALIDATION.md       Manual / programmatic verification map
        ├── 01-DISCUSSION-LOG.md
        ├── 01-{00..03}-PLAN.md    Per-plan PLAN.md
        ├── 01-{00..03}-SUMMARY.md Per-plan post-execution SUMMARY.md
        ├── 01-VERIFICATION.md     Goal-backward verification report
        └── 01-REVIEW.md           Code-review findings (4 warning + 6 info)
```

## What's deliberately not in the repo

- No CHANGELOG.md, no LICENSE file (README claims "Proprietary — All rights reserved")
- No CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md at root
- No `pgdata/` or seeds checked in (Postgres data lives in a Docker volume)
- No `node_modules/`, `.next/`, `.venv/`, `*.tfstate` (all gitignored)
