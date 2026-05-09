# GetVul Documentation

This is the canonical documentation for **GetVul** — a unified vulnerability-management platform that aggregates findings from six enterprise scanners, correlates them across sources, enriches them with identity/MDM/HR data, and turns them into actionable remediation tickets.

It is intended for engineers joining the project. Read **[01-overview.md](01-overview.md)** first, then **[04-installation.md](04-installation.md)** to get the stack running locally, then dive into whichever area you own.

## Index

| # | Document | What's inside |
|---|----------|---------------|
| 01 | [Overview](01-overview.md) | What GetVul does, target users, feature inventory, current milestone |
| 02 | [Architecture](02-architecture.md) | System architecture, request and sync data flows, Mermaid diagrams |
| 03 | [Tech Stack](03-tech-stack.md) | Every language, framework, library, and version pinned in lockfiles |
| 04 | [Installation](04-installation.md) | Prerequisites, local setup, seeding data, verification |
| 05 | [Configuration](05-configuration.md) | Every environment variable — purpose, default, where it's read |
| 06 | [Development Workflow](06-development-workflow.md) | Branches, commits, PRs, code review, lint/format/typecheck |
| 07 | [Project Structure](07-project-structure.md) | Annotated tree of the repo |
| 08 | [Core Modules](08-core-modules.md) | Backend modules and frontend feature areas, with public surface |
| 09 | [Data Model](09-data-model.md) | Postgres schema, ER diagram, every table, all 24 migrations |
| 10 | [API Reference](10-api-reference.md) | All ~99 backend endpoints grouped by router |
| 11 | [Integrations](11-integrations.md) | Every third-party connector (6 scanners + 2 ticketing + 3 IdP + 3 MDM/HR) |
| 12 | [Pipelines / CI/CD](12-pipelines-cicd.md) | GitHub Actions workflows, gates, soft-fail flags, DAST policy |
| 13 | [Deployment](13-deployment.md) | Single-VM Docker Compose stack on GCP/AWS/Azure, install.sh, rollback |
| 14 | [Testing](14-testing.md) | Test types, fixtures, how to run, coverage, gaps |
| 15 | [Monitoring & Logging](15-monitoring-logging.md) | structlog, syslog/CEF, audit logs, dashboards |
| 16 | [Security](16-security.md) | AuthN/AuthZ, secrets, headers, CI/CD security, tenant isolation |
| 17 | [Troubleshooting](17-troubleshooting.md) | Common failure modes and how to fix them |
| 18 | [Glossary](18-glossary.md) | Domain terms, acronyms, internal jargon |

## Diagrams

Mermaid diagrams are embedded in the relevant docs. The source `.mmd` files and rendered `.png` versions live in [diagrams/](diagrams/) for reuse outside this folder (slides, README badges, RFCs).

## Status legend used throughout

| Mark | Meaning |
|------|---------|
| ✓ | Implemented and verified |
| ⚠ | Implemented but with caveats — see surrounding text |
| ✗ | Documented as planned but not yet shipped |
| 🚧 | In flight (tracked in [.planning/ROADMAP.md](../.planning/ROADMAP.md)) |

## Quick stats

| Metric | Value |
|--------|-------|
| Backend routes (FastAPI) | ~99 endpoints across 9 routers |
| Postgres migrations (Alembic) | 24 |
| Connectors | 14 (6 scanners + 2 ticketing + 3 IdP + 3 MDM/HR) |
| Frontend routes (Next.js) | 10 (1 public, 9 protected) |
| Docker Compose services | 5 (nginx, postgres, redis, backend, frontend) |
| RBAC roles | 4 (Owner > Admin > Analyst > Viewer) |
| Backend tests | 7 files, 950 LOC, multi-replica suite included |
| Frontend tests | 0 (planned in Phase 8) |

## Document conventions

- Code, file paths, identifiers, and env vars are in `backticks`.
- File citations include line numbers when describing behavior — e.g. `backend/app/main.py:107` is the start of `TenantRateLimitMiddleware`.
- Cross-doc links use relative Markdown so navigation works on GitHub and locally.
- "Not applicable" with a one-line reason is preferred over fabricated content.
