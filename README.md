# GetVul

**Unified Vulnerability Aggregation Platform**

GetVul collects vulnerability data from CrowdStrike Spotlight, Nessus Professional, Microsoft Defender for Endpoint, and Wiz — normalizes it into a single merged database — and enables teams to take action by creating tickets in Jira or GitHub.

## Architecture

```
┌─────────────┐  ┌─────────┐  ┌──────────┐  ┌─────┐
│ CrowdStrike │  │ Nessus  │  │ Defender │  │ Wiz │
└──────┬──────┘  └────┬────┘  └────┬─────┘  └──┬──┘
       │              │            │            │
       └──────────────┴─────┬──────┴────────────┘
                            │
                    ┌───────▼────────┐
                    │  GetVul API    │
                    │  (FastAPI)     │
                    └───────┬────────┘
                            │
                  ┌─────────▼──────────┐
                  │  PostgreSQL (RDS)  │
                  │  Merged Vuln DB    │
                  └─────────┬──────────┘
                            │
                    ┌───────▼────────┐
                    │  Dashboard     │──► Jira / GitHub
                    │  (Next.js)     │    Tickets
                    └────────────────┘
```

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
