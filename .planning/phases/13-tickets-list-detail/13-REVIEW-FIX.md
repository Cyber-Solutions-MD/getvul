---
phase: 13-tickets-list-detail
fixed_at: 2026-06-02T00:00:00Z
review_path: .planning/phases/13-tickets-list-detail/13-REVIEW.md
iteration: 1
findings_in_scope: 15
fixed: 15
skipped: 0
status: all_fixed
---

# Phase 13: Code Review Fix Report

**Fixed at:** 2026-06-02
**Source review:** .planning/phases/13-tickets-list-detail/13-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 15 (6 Critical + 9 Warning; Info out of scope)
- Fixed: 15
- Skipped: 0

The root cause behind CR-01..CR-06 was a casing/contract mismatch between the
snake_case JSON the FastAPI backend emits (and `lib/api.ts` returns verbatim,
no transform) and the camelCase the new Phase 13 frontend assumed. Per the
verified codebase-wide convention (snake_case end-to-end, confirmed against
Phase 12 assets components), the fix aligned the NEW Phase 13 frontend to
snake_case rather than introducing a camelCase transform layer. Nested objects
(`assignee`/`reporter`/`watchers`/`asset`) keep camelCase keys because the
backend emits THOSE nested keys camelCase. Where the backend simply omitted a
field the frontend needed, the backend was extended to emit it.

Validation: 29 backend ticket tests (pytest, live Postgres) + 150 frontend
ticket tests (vitest) all green.

## Fixed Issues

### CR-01: Bulk-action body field name mismatch

**Files modified:** `frontend/src/app/(authed)/dashboard/tickets/page.tsx`
**Commit:** cc8e1bf
**Applied fix:** Send `ticket_urls` (not `external_ticket_urls`) in the
bulk-action POST body so `router.py` `body.get("ticket_urls")` matches. Every
bulk action previously 400'd with "No tickets selected".

### CR-04 / CR-06: List response casing + provider casing

**Files modified:** `backend/app/ticketing/service.py`,
`frontend/src/lib/queries/use-tickets.ts`,
`frontend/src/components/tickets/tickets-table.tsx`,
`frontend/src/app/(authed)/dashboard/tickets/page.tsx`,
`frontend/src/components/tickets/tickets-table.test.tsx`,
`frontend/src/app/(authed)/dashboard/tickets/page.test.tsx`
**Commit:** 5234c0e
**Applied fix:** `TicketSummary` type + `TicketsTable` accessors + list page now
read snake_case keys (`external_ticket_id`, `external_status`, `max_severity`,
`vuln_count`, `critical_count`, `high_count`, `sla_due_at`, `blocked_reason`,
`external_ticket_url`) matching `list_tickets`. Backend now also emits
`external_ticket_id` per item and lowercases `provider`. The drill mapping
validates provider via `isTicketProvider` instead of an unchecked `as` cast.

### CR-02 / CR-03 / CR-05: Detail + comments contract

**Files modified:** `backend/app/ticketing/router.py`,
`frontend/src/lib/queries/use-ticket-detail.ts`,
`frontend/src/lib/queries/use-ticket-comments.ts`,
`frontend/src/lib/queries/use-mark-blocked.ts`,
`frontend/src/app/(authed)/dashboard/tickets/[id]/page.tsx`,
`frontend/src/app/(authed)/dashboard/tickets/[id]/page.test.tsx`,
`frontend/src/lib/queries/use-ticket-comments.test.tsx`
**Commits:** 6413e7c, 400aa56 (CR-03 SQL correction: `func.min(Asset.id)` →
cast to text, since Postgres has no `min(uuid)`; CR-06 detail test asserts
`provider == "asana"`)
**Applied fix (requires human verification — semantic/logic):**
- CR-02: detail endpoint resolves `assignee` (string) to a `Person` object
  (joins `users` by email; falls back to a display-only object). No more
  string spread into `buildWatcherList`.
- CR-03: detail endpoint now emits `external_ticket_id`, `description`,
  `max_severity`, `critical_count`, `high_count`, and a single-host `asset`
  object (`{assetId,hostname,osName,riskScore}`); multi-host groups send
  `asset=null`. Frontend `TicketDetail` + page read snake_case top-level keys.
- CR-05: comments endpoint LEFT JOINs `users` to emit `user_display_name`;
  `Comment` type + timeline mapping + optimistic add use snake_case. Author and
  timestamps now render instead of "Unknown" / "Invalid Date".

> Flagged for human verification: the assignee-resolution heuristic (match
> `users.email == assignee`, else synthesize a display-only Person) and the
> single-host `asset` derivation are semantic decisions that pass tests but
> should be confirmed against real connector data shapes.

### WR-06: Hardcoded `CURRENT_USER_ID = ''`

**Files modified:** `frontend/src/app/(authed)/dashboard/tickets/[id]/page.tsx`,
`frontend/src/app/(authed)/dashboard/tickets/[id]/page.test.tsx`
**Commit:** 6413e7c
**Applied fix:** The app DOES expose a session hook (`useAuth()` in
`lib/auth.tsx` with `user.id`). Sourced the real current-user id from it;
`isWatching` now compares the real id, not `''`. (The REVIEW.md note that the
app had no user hook was outdated.)

### WR-07: `useMarkBlocked` optimistic casing inconsistency

**Files modified:** `frontend/src/lib/queries/use-mark-blocked.ts`
**Commit:** 6413e7c
**Applied fix:** Both optimistic branches now write `blocked_reason` (snake) to
match `TicketSummary`/`TicketDetail` after the CR-04 alignment.

### WR-08 / WR-09: ActivityTimeline date grouping + relativeTime

**Files modified:** `frontend/src/components/tickets/activity-timeline.tsx`
**Commit:** d697fc6
**Applied fix:** WR-08 — day key and label both derive from the same normalized
LOCAL `Date` (the "UTC" comment was wrong); invalid timestamps bucket under an
"Unknown date" group. WR-09 — `relativeTime` guards `Number.isFinite` and clamps
negative deltas to "just now".

### WR-01: List filters accepted but never applied

**Files modified:** `backend/app/ticketing/service.py`,
`backend/app/ticketing/router.py`, `backend/tests/test_ticket_watch.py`
**Commit:** 400aa56
**Applied fix (requires human verification — semantic/logic):** `list_tickets`
now applies the chip axes the frontend already sent: `provider`
(comma-separated, case-insensitive), `status` (maps the four chips
open/in_progress/completed/blocked, multi-value OR; legacy open/resolved still
work), `severity` (comma-separated, row-level EXISTS via the vuln join so the
grouped count stays consistent), `sla` (overdue/soon/ok via HAVING on group
MIN(sla_due_at), 7-day "soon" window matching the pill), and `search` (ILIKE on
`external_ticket_id`/`assignee`). Router declares and forwards the new params.

> Flagged for human verification: the four-status-chip → backend-semantics
> mapping and severity/SLA filter semantics are product decisions with no
> dedicated tests yet; existing list tests pass but the filter behavior should
> be confirmed end-to-end.

### WR-02: `recompute_ticket_sla` not wired to admin SLA-recalculate

**Files modified:** `backend/app/vulnerabilities/router.py`,
`backend/app/ticketing/service.py`
**Commit:** 3ec1381
**Applied fix (requires human verification — logic, no dedicated test):** The
admin `sla_recalculate` endpoint now flushes the recomputed
`vulnerability.sla_due_at` values, then calls `recompute_ticket_sla` for every
affected ticket group in the tenant before committing, so the materialized
ticket SLA no longer goes stale. Docstring updated. No dedicated test exercises
this path — confirm manually.

### WR-04: `created_by_rule` group ticket-type invariant

**Files modified:** `backend/app/ticketing/service.py`,
`backend/app/ticketing/router.py`
**Commit:** 3ec1381
**Applied fix (requires human verification — logic):** Ticket "mode" (host vs
per-remediation) is now derived from `bool_and(created_by_rule IS NOT NULL)` —
per-remediation iff EVERY row in the group carries the rule id — instead of
`bool(min(created_by_rule))`, which silently flipped type for a mixed group.
Applied in both `list_tickets` and the detail endpoint.

### WR-03: SLA "soon" vs per-severity SLA days

**Files modified:** `frontend/src/components/tickets/sla-pill.tsx`
**Commit:** e288ec7
**Applied fix:** Documented (in code) that the flat 7-day "soon" window is
intentional — severity is surfaced separately, the backend SLA chip filter
(WR-01) uses the same window so chip and pill agree, and the migration path to
backend-computed per-severity tiers is noted. Behavior unchanged.

### WR-05: N+1 per-row detail query in `list_tickets`

**Files modified:** `backend/app/ticketing/service.py`
**Commit:** b978499
**Applied fix (requires human verification — logic):** Replaced the per-grouped-
row `detail_q` (up to 100 round-trips per list call) with a single `GROUP BY`
query over exactly the page's `external_ticket_url`s (IN-list), keyed into a
dict. Scoping to the page URLs also makes the detail aggregate consistent with
the filtered/paginated group set (the old per-row query recomputed without that
scope). Multi-row-group reshape tests pass.

## Skipped Issues

None — all 15 in-scope findings were fixed.

(Info findings IN-01..IN-05 were out of scope for this critical_warning run.)

---

_Fixed: 2026-06-02_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
