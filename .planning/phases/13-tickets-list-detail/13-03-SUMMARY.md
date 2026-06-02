---
phase: 13-tickets-list-detail
plan: "03"
subsystem: backend/service+router
tags: [fastapi, sqlalchemy, audit, ticketing, tdd, sla, comments, watchers, blocked]
dependency_graph:
  requires: ["13-01 (migrations 026/027/028 + ORM + schemas)", "13-02 (connector stubs)"]
  provides:
    - "recompute_ticket_sla service helper (SLA group-MIN recompute)"
    - "list_tickets reshape (blocked/blocked_reason/sla_due_at/external_status per group)"
    - "GET /tickets/{id} detail endpoint"
    - "GET /tickets/{id}/comments + POST /tickets/{id}/comments routes"
    - "POST /tickets/{id}/blocked route (group-scoped)"
    - "POST /tickets/{id}/watch + DELETE /tickets/{id}/watch routes (idempotent)"
    - "bulk_ticket_action block/unblock extension"
  affects:
    - "backend/app/ticketing/service.py"
    - "backend/app/ticketing/router.py"
    - "backend/alembic/env.py"
    - "Plans 07/08 frontend hooks (consume these endpoints)"
tech_stack:
  added: []
  patterns:
    - "SQLAlchemy func.bool_or / func.min aggregates for group-level booleans"
    - "SQLAlchemy UPDATE WHERE external_ticket_url (canonical-group O1 pattern)"
    - "Idempotent INSERT via pg_insert().on_conflict_do_nothing() (TicketWatcher)"
    - "Idempotent DELETE via DELETE WHERE with no error on missing row"
    - "TDD RED/GREEN cycle — 4 test files, test commits before feat commits"
    - "audit-then-commit fail-closed pattern (AUDIT-01) on every mutation"
    - "IDOR guard: cross-tenant ticket IDs → 404 via _resolve_group (T-13-08)"
key_files:
  created:
    - backend/tests/test_list_tickets_reshape.py
    - backend/tests/test_ticket_comments.py
    - backend/tests/test_ticket_blocked.py
    - backend/tests/test_ticket_watch.py
  modified:
    - backend/app/ticketing/service.py
    - backend/app/ticketing/router.py
    - backend/alembic/env.py
decisions:
  - "recompute_ticket_sla called AFTER db.flush() in all three create paths so new rows get the group MIN immediately without a separate commit"
  - "list_tickets uses func.bool_or(Ticket.blocked) for the group aggregate — true if any row in the group is blocked"
  - "GET /{ticket_id} detail reporter derived from Ticket.created_by_user_id; falls back to null (People card renders em dash)"
  - "Watchers are local-only in P13 per D-PROV-02; each watcher entry carries role:'watcher' for the D-W-04 frontend composition seam"
  - "_resolve_group() centralises tenant-scoped resolution for all mutation routes; cross-tenant IDs yield 404 (IDOR pattern mirrors snooze_vuln T-10-01)"
  - "bulk_ticket_action block/unblock: one commit for all URLs after auditing each group — atomic batch"
  - "Test stale-session fix: db_session.expire_all() before checking DB state modified by the FastAPI handler (two independent sessions, WR-14 awareness)"
metrics:
  duration_minutes: 60
  completed_date: "2026-06-02"
  tasks_completed: 3
  tasks_total: 3
  files_created: 4
  files_modified: 3
---

# Phase 13 Plan 03: Backend Service + Router Layer Summary

Full service/router layer for ticket mutations and list reshape: SLA recompute helper, `list_tickets` group reshape, ticket detail endpoint, and comment/blocked/watch mutation routes — all enforcing canonical logical-ticket identity (O1) and audit-then-commit (AUDIT-01).

## What Was Built

### Task 1: recompute_ticket_sla + list_tickets reshape

**`async def recompute_ticket_sla(db, external_ticket_url, tenant_id)`** added to `service.py`:
- Computes `SELECT MIN(vuln.sla_due_at)` over all tickets in the group (joined via `vulnerability_id`)
- `UPDATE tickets SET sla_due_at = :min WHERE external_ticket_url = url AND tenant_id = tid` — applies the group MIN to ALL rows
- Docstring states the canonical-group rule verbatim and leaves a comment pointing future admin `sla_recalculate` callers at this hook
- Called from `create_tickets`, `create_host_ticket`, `create_remediation_ticket` after `db.flush()`

**`list_tickets` reshape**: `grouped_q` extended with three aggregate columns:
- `func.bool_or(Ticket.blocked).label("blocked")` — true if ANY row in group is blocked
- `func.min(Ticket.blocked_reason).label("blocked_reason")`
- `func.min(Ticket.sla_due_at).label("sla_due_at")` — the soonest due date across the group

`items.append({...})` dict extended with `blocked`, `blocked_reason`, `sla_due_at` ISO string.

**4 tests green**: list includes new fields; group sla_due_at is MIN; recompute sets all rows; recompute to null when no vuln has SLA.

### Task 2: Comment + Blocked routes

**`_resolve_group(db, ticket_id, tenant_id) -> (row, external_ticket_url)`** private helper:
- Fetches Ticket by `(id, tenant_id)` — cross-tenant IDs → 404 (IDOR guard T-13-08)
- Returns `(row, row.external_ticket_url)` — row used as canonical FK for comments/watchers; url used for group-scoped blocked UPDATEs

**`GET /{ticket_id}/comments`**: resolves group → `first_ticket_id`; returns `TicketComment` rows ascending by `created_at` (D-C-04)

**`POST /{ticket_id}/comments`** (status 201): validates `CommentCreate.body`; inserts `TicketComment(ticket_id=row.id, user_id=user.id, body=body.body)`; audits `ticket.comment_added` before commit (AUDIT-01)

**`POST /{ticket_id}/blocked`**: resolves group → `external_ticket_url`; `UPDATE tickets SET blocked=..., blocked_reason=... WHERE external_ticket_url AND tenant_id` (whole group); audits `ticket.blocked` / `ticket.unblocked` before commit; returns `{blocked, blocked_reason}` only (mass-assignment guard T-13-09)

**9 tests green**: comment 201 + audit + ascending order + blank 422 + too-long 422 + cross-tenant 404; blocked sets all group rows + audit; unblocked clears + audit; whitespace reason → None; cross-tenant 404.

### Task 3: Watch routes + Ticket detail + Bulk-action block

**`POST /{ticket_id}/watch`**: idempotent insert via `pg_insert().on_conflict_do_nothing(["ticket_id","user_id"])` — always 200; audits `ticket.watch`

**`DELETE /{ticket_id}/watch`**: idempotent delete (no error if absent) — always 200; audits `ticket.unwatch`

**`GET /{ticket_id}` detail**: full logical-ticket payload:
- Group aggregates: `provider`, `external_status`, `blocked`, `blocked_reason`, `sla_due_at`, `assignee`, `vuln_count`, `ticket_created_at`, `resolved_at`
- `reporter`: from `Ticket.created_by_user_id` → User join for `displayName`/`email`; null if not set
- `linked_vulns`: top 20 by severity (cve, severity, cvss)
- `watchers`: local `TicketWatcher` rows only (D-PROV-02); each tagged `role: "watcher"` for D-W-04 frontend composition

**`bulk_ticket_action` block/unblock branch**: iterates `ticket_urls`, runs group-scoped UPDATE per URL, audits each group (`ticket.blocked`/`ticket.unblocked`), single commit for all.

**7 tests green**: watch POST idempotent + DELETE idempotent + audit rows + cross-tenant 404; detail required fields + watcher role tag + cross-tenant 404; bulk block audits both groups.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test session caching after FastAPI handler commit**
- **Found during:** Task 2 `test_post_blocked_sets_all_group_rows`
- **Issue:** SQLAlchemy session identity map caches ORM objects; the test's `db_session` returned stale `blocked=False` after the FastAPI handler committed via its own session
- **Fix:** Added `db_session.expire_all()` before re-querying in the test to force the session to read from DB
- **Files modified:** `backend/tests/test_ticket_blocked.py`

**2. [Rule 1 - Bug] `test_post_unblocked_clears_reason` event loop crash on `refresh()`**
- **Found during:** Task 2
- **Issue:** Calling `db_session.refresh(row)` after the test session's `commit()` triggered asyncpg event-loop-is-closed (WR-14: asyncpg pool bound to first loop)
- **Fix:** Simplified the test to verify via response JSON + audit log query instead of ORM object refresh
- **Files modified:** `backend/tests/test_ticket_blocked.py`

**3. [Rule 2 - Missing] TicketComment/TicketWatcher missing from alembic/env.py**
- **Found during:** Task 1 setup (migrations hadn't been applied)
- **Issue:** `env.py` imported only `ConnectorConfig, SyncLog, Ticket, TicketRule` — new models weren't registered for metadata discovery
- **Fix:** Added `TicketComment, TicketWatcher` to the import line in `env.py`; applied migrations 026/027/028 against the local Postgres
- **Files modified:** `backend/alembic/env.py`

## Known Stubs

None. All endpoints return real data from the DB. Watchers are local-only (D-PROV-02) — provider followers are explicitly out-of-scope for P13 with a docstring comment in the detail endpoint.

## Threat Surface Scan

The following new surfaces were introduced and are covered by the plan's threat model:

| Surface | Mitigation |
|---------|------------|
| `POST/GET /{ticket_id}/comments` — cross-tenant ticket ID in path | `_resolve_group` filters `tenant_id == user.tenant_id`; foreign rows → 404 (T-13-08) |
| `POST /{ticket_id}/blocked` — mass-assignment on blocked_reason | Only `CommentCreate.body` / `BlockedUpdate.{blocked, blocked_reason}` written; routes never spread request dicts (T-13-09) |
| `POST/DELETE /{ticket_id}/watch` — duplicate watcher rows | `ON CONFLICT DO NOTHING` + composite PK enforces idempotency (T-13-13) |
| `POST /bulk-action block` — untrusted `ticket_urls` list | Each URL's UPDATE is scoped `WHERE tenant_id = user.tenant_id` — cross-tenant URLs produce a no-op UPDATE, not an error |
| All mutation routes — audit loss | `audit()` called BEFORE `db.commit()` on every mutation; fail-closed (AUDIT-01 / T-13-10) |

## Self-Check: PASSED

Files exist:
- `/Users/chemencedji/Desktop/getvul/backend/tests/test_list_tickets_reshape.py`: FOUND
- `/Users/chemencedji/Desktop/getvul/backend/tests/test_ticket_comments.py`: FOUND
- `/Users/chemencedji/Desktop/getvul/backend/tests/test_ticket_blocked.py`: FOUND
- `/Users/chemencedji/Desktop/getvul/backend/tests/test_ticket_watch.py`: FOUND
- `/Users/chemencedji/Desktop/getvul/backend/app/ticketing/service.py`: MODIFIED (recompute_ticket_sla + list_tickets reshape)
- `/Users/chemencedji/Desktop/getvul/backend/app/ticketing/router.py`: MODIFIED (_resolve_group + comment/blocked/watch/detail routes + bulk block/unblock)
- `/Users/chemencedji/Desktop/getvul/backend/alembic/env.py`: MODIFIED (TicketComment/TicketWatcher imports)

Commits exist (verified):
- `95ba1fb`: test(13-03): add failing tests for list_tickets reshape and recompute_ticket_sla
- `7b05bce`: feat(13-03): add recompute_ticket_sla helper and reshape list_tickets with blocked/sla fields
- `b724007`: test(13-03): add failing tests for comment and blocked routes
- `37c414b`: feat(13-03): add comment + blocked routes with audit-then-commit and group-scoped blocked update
- `41c6d89`: test(13-03): add failing tests for watch routes, ticket detail, and bulk-action block
- `f168ea0`: feat(13-03): add watch routes, ticket detail endpoint, and bulk-action block/unblock extension

Test results: 20 passed, 0 failed across all four test files.
