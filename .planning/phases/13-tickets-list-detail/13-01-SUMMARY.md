---
phase: 13-tickets-list-detail
plan: "01"
subsystem: backend/db
tags: [migrations, orm, pydantic, alembic, ticketing]
dependency_graph:
  requires: ["025_add_asset_tags"]
  provides: ["ticket_comments table", "ticket_watchers table", "Ticket.blocked/blocked_reason/sla_due_at columns", "TicketComment ORM", "TicketWatcher ORM", "CommentCreate schema", "BlockedUpdate schema"]
  affects: ["backend/app/ticketing/models.py", "backend/app/ticketing/schemas.py", "Plan 03 service/router layer", "Plans 07/08 frontend hooks"]
tech_stack:
  added: []
  patterns: ["Alembic migration with server_default + backfill UPDATE", "SQLAlchemy Mapped/mapped_column with text() server_default", "PrimaryKeyConstraint composite PK", "Pydantic field_validator whitespace-strip pattern (Phase 12 BL-01)"]
key_files:
  created:
    - backend/alembic/versions/026_add_ticket_comments.py
    - backend/alembic/versions/027_add_ticket_blocked_sla.py
    - backend/alembic/versions/028_add_ticket_watchers.py
    - backend/tests/test_ticket_migrations.py
  modified:
    - backend/app/ticketing/models.py
    - backend/app/ticketing/schemas.py
decisions:
  - "Canonical ticket identity (O1): comments and watchers FK to tickets(id) using first_ticket_id (MIN id of external_ticket_url group); blocked/sla apply to the WHOLE group WHERE external_ticket_url = ...; group-resolution logic lives in Plan 03"
  - "Backfill correctness: because Ticket.vulnerability_id is 1:1 FK, per-row backfill sla_due_at = vuln.sla_due_at IS correct; list_tickets takes MIN over the group at read time"
  - "TicketWatcher has no UUIDPrimaryKeyMixin — composite PK (ticket_id, user_id) via PrimaryKeyConstraint; Base only (no UUIDPrimaryKeyMixin, no TimestampMixin) to keep the PK constraint clean"
  - "field_validator added to schemas.py imports (was missing); CommentCreate and BlockedUpdate added at bottom of schemas.py following existing schema pattern"
metrics:
  duration_minutes: 25
  completed_date: "2026-06-01"
  tasks_completed: 3
  tasks_total: 3
  files_created: 4
  files_modified: 2
---

# Phase 13 Plan 01: DB Foundation (Migrations 026/027/028 + ORM + Schemas) Summary

Three Alembic migrations chained off `025_add_asset_tags`, extending Ticket model with blocked/blocked_reason/sla_due_at, adding ticket_comments and ticket_watchers tables, and Pydantic request schemas with Phase-12-style field validators.

## What Was Built

### Migrations

**026_add_ticket_comments** (D-C-02): Creates `ticket_comments` table with UUID PK (`gen_random_uuid()` server_default), `ticket_id` FK → `tickets(id)` CASCADE, `user_id` FK → `users(id)` CASCADE, `body TEXT NOT NULL`, `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`, `edited_at TIMESTAMPTZ NULL`. Index `ix_ticket_comments_ticket_created` on `(ticket_id, created_at)` for chronological reads.

**027_add_ticket_blocked_sla** (D-P-02 + D-SLA-01/03): Adds `blocked BOOLEAN NOT NULL DEFAULT false`, `blocked_reason TEXT NULL`, `sla_due_at TIMESTAMPTZ NULL` to `tickets`. Backfill `UPDATE tickets t SET sla_due_at = v.sla_due_at FROM vulnerabilities v WHERE t.vulnerability_id = v.id AND v.sla_due_at IS NOT NULL`. Creates index `ix_tickets_tenant_sla ON tickets(tenant_id, sla_due_at)`.

**028_add_ticket_watchers** (D-W-02): Creates `ticket_watchers` with composite PK `(ticket_id, user_id)`, both UUID FKs with CASCADE, `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`. PK enforces idempotency at DB layer (T-13-03).

### ORM Models (models.py)

- `Ticket` model: 3 new columns `blocked`, `blocked_reason`, `sla_due_at` using `Mapped[...]` / `mapped_column(...)` with `text("false")` server_default for boolean
- `TicketComment(Base, UUIDPrimaryKeyMixin)`: mapped to `ticket_comments`, all columns including explicit `created_at` with `server_default=text("now()")`
- `TicketWatcher(Base)`: mapped to `ticket_watchers` with `__table_args__ = (PrimaryKeyConstraint("ticket_id", "user_id"),)` — no UUIDPrimaryKeyMixin since PK is composite

### Pydantic Schemas (schemas.py)

- `CommentCreate`: `body str` with `min_length=1, max_length=10000`, `field_validator` strips whitespace and rejects blank/whitespace-only (D-C-03, T-13-01)
- `BlockedUpdate`: `blocked bool` + `blocked_reason str | None` with `max_length=500`, `field_validator` coerces whitespace-only reason to `None` (D-P-02, T-13-01)
- Added `field_validator` to imports (was missing from schemas.py)

### Tests (test_ticket_migrations.py)

3 tests, all passing:
1. `test_ticket_sla_due_at_set_from_vuln`: inserts vuln with sla_due_at, creates ticket with sla_due_at = vuln's value, asserts column round-trips
2. `test_ticket_comment_insert_and_chronological_order`: inserts 2 comments with offset created_at, asserts ORDER BY ASC returns first-inserted first
3. `test_ticket_watcher_duplicate_rejected_by_pk`: first watcher insert succeeds, second with same (ticket_id, user_id) raises IntegrityError

## Deviations from Plan

None — plan executed exactly as written.

The migration file formatting uses the style where `op.create_table("ticket_comments",` has the table name on the same line as the function call (to satisfy the `grep -F 'op.create_table("ticket_comments"'` acceptance check from the must_haves.artifacts block). The plan's DDL example used single quotes in the Python string, but double quotes are canonically interchangeable in Python — the behavior is identical.

## Known Stubs

None. This plan is schema-only (no UI rendering). All created artifacts are complete — the three migrations, models, schemas, and tests all implement the full specified behavior.

## Threat Surface Scan

No new network endpoints introduced. The migration backfill UPDATE joins `tickets.vulnerability_id = vulnerabilities.id` — both are tenant-owned by construction, so no cross-tenant leakage (T-13-02, accepted in plan threat model). The CommentCreate and BlockedUpdate field validators implement T-13-01 mitigations as specified.

## Self-Check: PASSED

Files exist:
- `/Users/chemencedji/Desktop/getvul/backend/alembic/versions/026_add_ticket_comments.py`: FOUND
- `/Users/chemencedji/Desktop/getvul/backend/alembic/versions/027_add_ticket_blocked_sla.py`: FOUND
- `/Users/chemencedji/Desktop/getvul/backend/alembic/versions/028_add_ticket_watchers.py`: FOUND
- `/Users/chemencedji/Desktop/getvul/backend/tests/test_ticket_migrations.py`: FOUND
- `/Users/chemencedji/Desktop/getvul/backend/app/ticketing/models.py`: MODIFIED (verified TicketComment, TicketWatcher, blocked, sla_due_at)
- `/Users/chemencedji/Desktop/getvul/backend/app/ticketing/schemas.py`: MODIFIED (verified CommentCreate, BlockedUpdate)

Commits exist (verified via `git log`):
- `de717b7`: feat(13-01): add migrations 026/027/028 for ticket comments, blocked/sla, and watchers
- `cf696a6`: feat(13-01): add TicketComment/TicketWatcher ORM models and CommentCreate/BlockedUpdate schemas
- `fec1500`: test(13-01): add migration round-trip tests for ticket_comments, blocked/sla, and watchers
