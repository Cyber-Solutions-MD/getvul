# Phase 42 — External API Coverage Declaration

No external API integration: Phase 42 reads existing internal Postgres score-history and finding data to compute trend/burndown analytics; no external service is called.

## Rationale

Phase 42 is a pure read-side analytics feature. Every data source is an existing internal Postgres table:

- `daily_snapshots` (per-day tenant metrics + per-asset score dicts + `risk_model_version_snapshot`), written by the existing `capture_daily_snapshot` job (not touched by this phase).
- `vulnerabilities` (live `first_detected_at` / `remediated_at` / `status` / `severity` / `sla_due_at` / `sla_breached` columns) for aging + burndown.
- `asset_groups` / `asset_group_members` for group scoping.

No SDK, no HTTP client to a third party, no webhook, no `SERVICE_*` env var, and zero new packages (recharts, TanStack Query, FastAPI, SQLAlchemy, Pydantic are all already installed). The v5.0 hard-constraint "no new infra" holds — this phase adds only a read-only router + service module.

## Schema Gate

Backend is SQLAlchemy + Alembic — the schema-push gate does not apply. This phase READS existing tables only; no new table, no new column, no Alembic migration is required or created.
