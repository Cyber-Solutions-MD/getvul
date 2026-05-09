# GetVul

**Unified Vulnerability Aggregation Platform**

GetVul collects vulnerability data from six enterprise scanners — CrowdStrike Falcon Spotlight, Tenable Nessus, Microsoft Defender for Endpoint, Wiz, Qualys VMDR, and Rapid7 InsightVM — normalizes it into a single merged database, enriches assets with identity/MDM/HR data (Google, Azure, Okta, Humaans, Jamf, Intune), and enables teams to act through Asana or Jira tickets.

## Architecture

```
┌─────────────┐ ┌─────────┐ ┌──────────┐ ┌─────┐ ┌────────┐ ┌────────┐
│ CrowdStrike │ │ Nessus  │ │ Defender │ │ Wiz │ │ Qualys │ │ Rapid7 │
└──────┬──────┘ └────┬────┘ └────┬─────┘ └──┬──┘ └────┬───┘ └────┬───┘
       │             │           │          │         │          │
       └─────────────┴───────────┴────┬─────┴─────────┴──────────┘
                                      │
                              ┌───────▼────────┐
                              │  GetVul API    │
                              │  (FastAPI)     │
                              └───────┬────────┘
                                      │
                        ┌─────────────┴─────────────┐
                ┌───────▼────────┐         ┌────────▼────────┐
                │  PostgreSQL 16 │         │     Redis 7     │
                │  (24 migrations)│        │ (state + limit) │
                └───────┬────────┘         └─────────────────┘
                        │
                ┌───────▼────────┐
                │  Dashboard     │──► Asana / Jira tickets
                │  (Next.js 15)  │
                └────────────────┘
```

Full architecture, request flow, and data-model diagrams: [docs/](docs/).

## Quick Start

```bash
git clone git@github.com:Cyber-Solutions-MD/getvul.git
cd getvul
cp .env.example .env
make dev
```

- Backend API: http://localhost:8000 (Swagger: http://localhost:8000/docs)
- Frontend: http://localhost:3000

## Commands

Run `make help` to see all available commands.

## License

Proprietary — All rights reserved.
