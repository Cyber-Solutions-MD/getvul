---
phase: 13-tickets-list-detail
reviewed: 2026-06-02T00:00:00Z
depth: standard
files_reviewed: 44
files_reviewed_list:
  - backend/alembic/env.py
  - backend/alembic/versions/026_add_ticket_comments.py
  - backend/alembic/versions/027_add_ticket_blocked_sla.py
  - backend/alembic/versions/028_add_ticket_watchers.py
  - backend/app/ticketing/github_client.py
  - backend/app/ticketing/jira_client.py
  - backend/app/ticketing/models.py
  - backend/app/ticketing/router.py
  - backend/app/ticketing/schemas.py
  - backend/app/ticketing/service.py
  - backend/tests/test_list_tickets_reshape.py
  - backend/tests/test_provider_stubs.py
  - backend/tests/test_ticket_blocked.py
  - backend/tests/test_ticket_comments.py
  - backend/tests/test_ticket_migrations.py
  - backend/tests/test_ticket_watch.py
  - frontend/src/app/(authed)/dashboard/tickets/[id]/page.tsx
  - frontend/src/app/(authed)/dashboard/tickets/page.tsx
  - frontend/src/app/(authed)/dashboard/tickets/rules/page.tsx
  - frontend/src/app/globals.css
  - frontend/src/components/shell/sidebar.tsx
  - frontend/src/components/tickets/activity-timeline.tsx
  - frontend/src/components/tickets/blocked-toggle.tsx
  - frontend/src/components/tickets/comment-input.tsx
  - frontend/src/components/tickets/microcopy.ts
  - frontend/src/components/tickets/provider-mark.tsx
  - frontend/src/components/tickets/sla-pill.tsx
  - frontend/src/components/tickets/status-pill.tsx
  - frontend/src/components/tickets/ticket-asset-card.tsx
  - frontend/src/components/tickets/ticket-bulk-bar.tsx
  - frontend/src/components/tickets/ticket-drill-content.tsx
  - frontend/src/components/tickets/tickets-chip-bar.tsx
  - frontend/src/components/tickets/tickets-table.tsx
  - frontend/src/components/tickets/types.ts
  - frontend/src/components/tickets/vuln-count.tsx
  - frontend/src/components/tickets/watcher-stack.tsx
  - frontend/src/components/vulnerabilities/drill-panel-mobile.tsx
  - frontend/src/components/vulnerabilities/drill-panel.tsx
  - frontend/src/lib/queries/keys.ts
  - frontend/src/lib/queries/use-mark-blocked.ts
  - frontend/src/lib/queries/use-ticket-comments.ts
  - frontend/src/lib/queries/use-ticket-detail.ts
  - frontend/src/lib/queries/use-ticket-rules.ts
  - frontend/src/lib/queries/use-ticket-watch.ts
  - frontend/src/lib/queries/use-tickets.ts
findings:
  critical: 6
  warning: 9
  info: 5
  total: 20
status: issues_found
---

# Phase 13: Code Review Report

**Reviewed:** 2026-06-02T00:00:00Z
**Depth:** standard
**Files Reviewed:** 44 (3 not loaded individually: sidebar.tsx, drill-panel-mobile.tsx, globals.css — verified via targeted grep)
**Status:** issues_found

## Summary

Phase 13 ships the tickets list/detail surface: three backend migrations, comment/watch/blocked routes, two connector stubs (Jira/GitHub), a reshaped `list_tickets`, a detail endpoint, and a large frontend surface (list page, detail page, drill content, rules page, ~12 components, ~7 query hooks).

The backend work is largely solid — the migrations are clean, the IDOR guard (`_resolve_group`) is consistent, audit-before-commit is correct, and tenant scoping holds. The tests, however, only ever exercise the backend directly; **no test crosses the frontend↔backend wire contract**, and that is exactly where this phase breaks.

The dominant problem is a systematic **API contract mismatch between the snake_case JSON the backend emits and the camelCase shapes the frontend types/consumes**. The `api()` helper performs no key transformation (`return res.json()` verbatim — confirmed in `frontend/src/lib/api.ts`). As a result:

- The tickets table renders blank/`undefined` cells (`externalId`, `vulnCount`, `maxSeverity`, etc. are all `undefined`).
- The provider mark never renders (`provider` arrives as `"ASANA"`, frontend guards on `"asana"`).
- The detail page **crashes** dereferencing `t.assignee.displayName` when the backend returns `assignee` as a plain string (or `null`), plus reads fields the backend never returns (`description`, `asset`, `externalTicketUrl`).
- The bulk-action bar silently no-ops because the page POSTs `external_ticket_urls` while the router reads `ticket_urls`.

These are shipping-blockers: the primary screens of the phase do not function against the implemented backend. Several SLA-tier and `created_by_rule` filtering gaps compound the picture. Details below.

## Critical Issues

### CR-01: Bulk-action body field name mismatch — every bulk action silently no-ops

**File:** `frontend/src/app/(authed)/dashboard/tickets/page.tsx:170-178` and `backend/app/ticketing/router.py:250`
**Issue:** The list page sends the selected URLs under the key `external_ticket_urls`:
```js
body: JSON.stringify({ action, external_ticket_urls: urls, blocked_reason: blockedReason ?? null })
```
But the backend reads `urls = body.get("ticket_urls", [])`. The key never matches, so `urls` is always `[]` and the handler raises `HTTPException(400, "No tickets selected")` for *every* bulk action from the list UI. The page swallows the error in a bare `catch {}` (line 181), so the user sees a selection that clears with no effect. Note the backend tests (`test_bulk_action_block_sets_group_blocked`) use the correct `ticket_urls` key, which is why CI is green while the real UI is broken.
**Fix:** Align the field name. Send `ticket_urls` from the page (matches the router and the passing tests):
```js
body: JSON.stringify({ action, ticket_urls: urls, blocked_reason: blockedReason ?? null }),
```

### CR-02: Ticket detail page crashes — `assignee` typed as `Person`, backend returns a string

**File:** `frontend/src/app/(authed)/dashboard/tickets/[id]/page.tsx:353-354` and `backend/app/ticketing/router.py:783`
**Issue:** The detail endpoint returns `"assignee": group.assignee` where `Ticket.assignee` is a `String(255)` (an email/user id), or `None`. The frontend `TicketDetail` types `assignee: Person | null` and the page renders `t.assignee.displayName` and `t.assignee.email`. When `assignee` is a non-empty string, `t.assignee.displayName` is `undefined` (renders nothing) and `<Avatar name={undefined} .../>` is fed garbage; more importantly `buildWatcherList({ assignee: t.assignee, ... })` (line 220-224) spreads a string into `{ ...params.assignee, role: 'assignee' }`, producing a malformed watcher with no `userId`. The People card and WatcherStack are driven by corrupt data. This is a hard contract break: the rendered detail page is wrong whenever a ticket has an assignee.
**Fix:** Decide the contract and make both sides agree. Either (a) have the backend resolve `assignee` to a `{userId, displayName, email}` object (join `users`/asset Humaans email like the reporter block does), or (b) change the frontend type to `assignee: string | null` and render it as plain text. Given the People card and `buildWatcherList` expect an object, (a) is the intended shape — return `null` or a `Person`, never a bare string.

### CR-03: Detail endpoint omits fields the detail page requires (`description`, `asset`, `externalTicketUrl`)

**File:** `backend/app/ticketing/router.py:775-795` and `frontend/src/lib/queries/use-ticket-detail.ts:30-59` / `[id]/page.tsx:296-301,403-408`
**Issue:** The frontend `TicketDetail` type and page consume:
- `t.externalTicketUrl` — backend returns `external_ticket_url` (snake_case; camelCase access yields `undefined`).
- `t.description` — backend never returns a `description` key at all (the `{description && ...}` section silently never renders, and the drill content always passes `description: null`).
- `t.asset` (`{ assetId, hostname, osName, riskScore }`) — backend never returns an `asset` object. `TicketAssetCard` always receives `assetId=null` and renders the "Multiple hosts" fallback even for single-host tickets.
- `t.maxSeverity`, `t.criticalCount`, `t.highCount`, `t.vulnCount` — backend returns `vuln_count` (snake) and omits the severity counts; all read as `undefined`.

So the Asset rail card is always degraded, the description block is dead, and any code path reading these is broken.
**Fix:** Make the detail endpoint return the full documented contract in the casing the frontend reads (or introduce a response model + a shared camelCase serializer). At minimum add `asset`, `description`, `max_severity`, `critical_count`, `high_count`, and ensure key casing matches the consumer. The `detail_q` (router.py:752) already computes hostname — extend it to also select `Asset.id/os_name/risk_score` and emit the `asset` object.

### CR-04: List response casing mismatch — tickets table renders empty rows

**File:** `frontend/src/lib/queries/use-tickets.ts:24-39` and `backend/app/ticketing/service.py:763-786`
**Issue:** `list_tickets` emits snake_case item keys: `external_ticket_url`, `external_status`, `max_severity`, `vuln_count`, `critical_count`, `high_count`, and has **no** `external_id` key. The frontend `TicketSummary` type and `TicketsTable` read `externalId`, `externalStatus`, `externalTicketUrl`, `maxSeverity`, `vulnCount`, `criticalCount`, `highCount`. Because `api()` does no transform, every one of these is `undefined` at runtime:
- `r.externalId` → `undefined` → the mono "ID" column and the checkbox `aria-label` show nothing.
- `r.maxSeverity?.toLowerCase()` → `undefined` → always the fallback `○` glyph / faint color.
- `r.vulnCount`/`criticalCount`/`highCount` → `undefined` → `VulnCount total={undefined}` (`undefined === 0` is false, so it skips the em-dash branch and renders `undefined·undefined`).
- `r.externalTicketUrl` → `undefined` → bulk action URL list is `[undefined,...]` (compounds CR-01).
- Row key `r.id` works (backend does emit `id`), and `blocked`/`blocked_reason`/`sla_due_at`... note `blockedReason` is also camelCase on the frontend while backend sends `blocked_reason`.

The list table is non-functional against the real payload.
**Fix:** Establish a single casing convention at the wire boundary. Either add a response transform in `api()` / `useTickets` (`snake→camel`), or change the frontend types and accessors to snake_case to match the backend. Whichever is chosen, apply it consistently across `use-tickets`, `use-ticket-detail`, and `use-ticket-comments` (see CR-05).

### CR-05: Comment list casing mismatch — author and timestamps render as "Unknown"/Invalid Date

**File:** `frontend/src/lib/queries/use-ticket-comments.ts:23-30` and `backend/app/ticketing/router.py:471-481`
**Issue:** `GET /tickets/{id}/comments` returns `{id, ticket_id, user_id, body, created_at, edited_at}` (snake_case) and crucially has **no** `userDisplayName` field (the backend never joins `users` for the comment list — see router.py:464-481). The frontend `Comment` type expects `userId`, `userDisplayName`, `createdAt`, `editedAt`. At runtime `c.createdAt` is `undefined` and `mapCommentsToEntries` ([id]/page.tsx:88-103) builds `TimelineEntry.createdAt = undefined`; `ActivityTimeline.relativeTime`/`groupByDay` then call `new Date(undefined)` → `Invalid Date` → `NaN` math and a broken/blank day header. `c.userDisplayName` is `undefined` so every comment shows author "Unknown".
**Fix:** (1) Join `users.display_name` in the comments query and emit it; (2) reconcile casing (emit `userDisplayName`/`createdAt` or transform on the client). The optimistic-add path in `useAddComment` already produces camelCase (`createdAt`, `userDisplayName: 'You'`), so the server payload must match that shape for the timeline to work consistently.

### CR-06: Provider value casing — ProviderMark never renders, drill cast is unsafe

**File:** `frontend/src/components/tickets/tickets-table.tsx:45-47,175-177` and `backend/app/ticketing/service.py:768`
**Issue:** The backend stores/returns `provider` as uppercase (`"ASANA"`, `"JIRA"`, `"GITHUB"` — see `models.py` and all seed/test data). `isTicketProvider` only accepts lowercase `'jira'|'asana'|'github'`, so `{isTicketProvider(r.provider) && <ProviderMark .../>}` is always false — the Provider column is permanently blank. Worse, the list page casts unconditionally: `provider: selectedTicket.provider as 'jira' | 'asana' | 'github'` ([id]/page.tsx... page.tsx:318), feeding `"ASANA"` into `PROVIDER_GRADIENTS["ASANA"]` (→ `undefined` background) and `PROVIDER_LABEL["ASANA"]` (→ `undefined` "Open in undefined"). The detail page passes `t.provider` (`"ASANA"`) straight into `<ProviderMark provider={t.provider} />` with the same result.
**Fix:** Normalize provider casing at the boundary — lowercase it in the query hook mapping (`provider: raw.provider?.toLowerCase()`), or have the backend emit lowercase. Do not rely on `as` casts to launder unvalidated values.

## Warnings

### WR-01: SLA chip filters and severity/search filters are accepted but never applied

**File:** `frontend/src/lib/queries/use-tickets.ts:49-94` and `backend/app/ticketing/service.py:655-687`
**Issue:** `buildSearchParams` serializes `status`, `provider`, `severity`, `sla`, and `search` into the query string, and `list_all_tickets` (router.py:100-122) only declares `provider`, `status`, `page`, `page_size`, `asset_id`. The backend `list_tickets` ignores `severity`, `sla`, and `search` entirely, and only understands `status in {"open","resolved"}` — not the chip values `open/in_progress/completed/blocked`. So selecting "Critical", "Overdue", or typing a search term changes the URL but returns an unfiltered list, and selecting status chips like "in_progress"/"completed"/"blocked" maps to neither branch (falls through to no status filter). Users get silently wrong result sets.
**Fix:** Either implement the missing filters server-side (severity via the `detail` aggregate or a join; SLA tier via `sla_due_at` ranges; search across id/title/assignee; map the 4 status chips) or remove the non-functional chips. At minimum the status chip values must agree with the backend's accepted vocabulary.

### WR-02: `recompute_ticket_sla` is never called by the admin SLA-recalculate path it documents

**File:** `backend/app/ticketing/service.py:37-40`
**Issue:** The docstring states callers of the admin `sla_recalculate` endpoint "should call `recompute_ticket_sla` for each affected `external_ticket_url`." Nothing in the reviewed scope wires that hook. After an admin bulk-changes `vulnerability.sla_due_at`, the `tickets.sla_due_at` group MIN goes stale and the SLA pill shows an outdated tier indefinitely (it is materialized on the ticket row, not computed live from the vuln). This is a correctness/data-staleness defect, not just docs.
**Fix:** Call `recompute_ticket_sla` for each affected `external_ticket_url` inside the SLA-recalculate flow, or document explicitly that ticket SLA is recomputed on next ticket create/sync only.

### WR-03: SLA "soon" tier (frontend) vs SEVERITY_SLA_DAYS (backend) are unrelated thresholds

**File:** `frontend/src/components/tickets/sla-pill.tsx:18,68-75`
**Issue:** `SlaPill` hardcodes a 7-day "soon" window, while the backend SLA model assigns due dates of 3/14/30/90/180 days by severity (`service.py:67-73`). A CRITICAL ticket (3-day SLA) is "soon" only inside the last 7 days, which is its entire lifetime — fine — but a LOW ticket (90 days) shows green "OK" until 7 days out with no severity weighting. The single hardcoded threshold means the pill does not reflect per-severity urgency the rest of the system encodes. Acceptable if intentional, but it diverges from the backend SLA semantics and the chip `sla` axis (overdue/soon/ok) that the backend doesn't compute (see WR-01).
**Fix:** Confirm the product intent. If tiers should track severity, derive the "soon" window from severity or from a backend-provided tier rather than a flat 7 days.

### WR-04: `created_by_rule` set only on the first row of remediation tickets breaks group ticket-type detection

**File:** `backend/app/ticketing/service.py:610-642`
**Issue:** In `create_remediation_ticket` every row in the group gets `created_by_rule=remediation_id` (good). But `create_host_ticket` (service.py:442-456) sets no `created_by_rule`, and `list_tickets`/detail derive `is_per_remediation = bool(min(created_by_rule))`. Because `func.min(Ticket.created_by_rule)` over a remediation group returns the rule id (non-null) this works for remediation tickets; however if a group ever mixes rows with and without `created_by_rule` (e.g. a vuln re-ticketed via two paths sharing a URL), `min()` returns the non-null string and the title logic silently flips type. Low likelihood but the type detection is fragile — it infers a per-group attribute from a per-row column via MIN.
**Fix:** Treat ticket type as a group-level invariant: assert all rows in a group share `created_by_rule`, or store ticket "mode" explicitly once per logical ticket rather than inferring via aggregate.

### WR-05: `list_tickets` runs a per-row detail query inside a loop (N+1)

**File:** `backend/app/ticketing/service.py:719-746`
**Issue:** For each grouped row, a separate `detail_q` is executed (`for row in grouped_rows: ... await db.execute(detail_q)`). With `page_size` up to 100 that's up to 100 extra round-trips per list call. (Flagged as a correctness/robustness concern under DB load rather than pure perf: it also means the detail aggregate is recomputed without the `asset_id`/status filters applied, so counts can disagree with the filtered group — e.g. `host_count`/severity counts include rows the outer filter would exclude.)
**Fix:** Fold the detail aggregates into the grouped query (single GROUP BY with the joins), or batch-fetch details for all returned URLs in one query keyed by `external_ticket_url`.

### WR-06: `CURRENT_USER_ID = ''` makes the Watch toggle and watcher dedupe incorrect

**File:** `frontend/src/app/(authed)/dashboard/tickets/[id]/page.tsx:160,167,227`
**Issue:** The detail page hardcodes `CURRENT_USER_ID = ''`. `isWatching = t.watchers.some(w => w.userId === '')` is always false, so the button always shows "Watch" even after the user is watching (server truth shows them as a watcher with a real id). The optimistic `useTicketWatch(id, '')` appends/removes a watcher with `userId: ''`, which can collide with `buildWatcherList`/`dedupeAndSort` (any other entry lacking a userId dedupes against it). The button state and watcher list are unreliable.
**Fix:** Source the real current-user id (the app has an auth/session context used elsewhere — `getToken()` implies a session). Until then, derive `isWatching` from a server-provided `watching` boolean rather than comparing against `''`.

### WR-07: `useMarkBlocked` optimistic detail patch writes `blocked_reason` but the detail cache uses `blockedReason`

**File:** `frontend/src/lib/queries/use-mark-blocked.ts:62-69` vs `:79-84`
**Issue:** The detail-cache optimistic update sets `{...prev, blocked, blocked_reason}` (snake) while the list-cache update sets `{...ticket, blocked, blockedReason: blocked_reason}` (camel). The `TicketDetail` type uses `blockedReason` (camel), so the detail optimistic write adds a stray `blocked_reason` key and never updates the `blockedReason` the UI reads — the BlockedToggle reason text won't reflect optimistically (and the underlying server payload is snake anyway per CR-03/CR-04). Inconsistent key casing within the same hook.
**Fix:** Pick one casing and use it in both branches, matching whatever the wire/transform convention from CR-04 lands on.

### WR-08: ActivityTimeline groups by local calendar day but labels with a separate Date — DST/locale edge cases

**File:** `frontend/src/components/tickets/activity-timeline.tsx:34-64`
**Issue:** `groupByDay` keys on local `getFullYear/Month/Date`, while the comment "(YYYY-MM-DD in UTC)" claims UTC — the code is actually local time, so the doc is wrong and grouping is timezone-dependent. Separately, `dayLabel` recomputes "Today/Yesterday" from `new Date(isoDate)` per entry; entries near midnight can land in a group whose label disagrees with neighbors. Minor, but produces confusing headers around midnight and is mislabeled.
**Fix:** Compute the day key and the label from the same normalized value, and make the comment match the implementation (local, not UTC).

### WR-09: `relativeTime` produces negative/"just now" output for future or `Invalid Date` timestamps

**File:** `frontend/src/components/tickets/activity-timeline.tsx:67-76`
**Issue:** With the broken `createdAt` from CR-05 (`undefined`), `new Date(undefined).getTime()` is `NaN`, so `minutes = Math.floor(NaN/60000) = NaN`, every comparison is false, and the function falls through to `${NaN}d ago`. Even with valid data, a clock-skewed future timestamp yields negative minutes → "just now" is the only guard. No defensive handling of non-finite input.
**Fix:** Guard `Number.isFinite(ms)` and clamp negatives; render a stable fallback (e.g. the absolute date) when the timestamp is unparseable.

## Info

### IN-01: Dead/unused variable in `_build_host_task_description`

**File:** `backend/app/ticketing/service.py:266`
**Issue:** `rem.get("vuln_count", 1)` is called and its result discarded — a no-op statement (likely meant to be assigned or removed).
**Fix:** Remove the line or use the value.

### IN-02: Duplicate `/sync-status` route registration

**File:** `backend/app/ticketing/router.py:228` and `:1048`
**Issue:** `@router.post("/sync-status")` is declared twice — once as `sync_all_ticket_statuses` (require_analyst, calls `sync_ticket_status`) and once as `trigger_ticket_sync` (get_current_user, calls `run_daily_ticket_sync`). FastAPI keeps the first registration; the second is unreachable dead code, and the differing auth dependency (`require_analyst` vs `get_current_user`) signals confusion about which behavior is intended.
**Fix:** Remove one; if both behaviors are needed, give them distinct paths.

### IN-03: `microcopy.openFull` defined but unused

**File:** `frontend/src/components/tickets/microcopy.ts:24`
**Issue:** `openFull: 'Open full detail'` is never referenced (the drill content hardcodes the same string at `ticket-drill-content.tsx:230`). Minor duplication / dead export.
**Fix:** Use the constant in the drill content, or drop it.

### IN-04: `TicketResponse`/`TicketStats.by_severity` schema oddities

**File:** `backend/app/ticketing/schemas.py:13-34,820`
**Issue:** `TicketResponse` is defined but not used by any reviewed route (the routes return raw dicts). `get_ticket_stats` returns `by_severity = {"vulns_covered": N}` — a severity dict keyed by a non-severity string, which the `TicketStats` type (`dict[str,int]`) permits but is semantically misleading for any consumer expecting severity buckets.
**Fix:** Remove the unused schema; rename or restructure the stats field to reflect its contents.

### IN-05: `aria-modal="false"` on a role="dialog" drill panel

**File:** `frontend/src/components/vulnerabilities/drill-panel.tsx:96`
**Issue:** The aside uses `role="dialog"` with `aria-modal="false"`. That is technically valid for a non-modal panel, but combined with the outside-click-closes behavior it behaves modally for mouse users while not trapping focus for AT users — an a11y inconsistency.
**Fix:** Confirm intent; if it should trap focus, set `aria-modal="true"` and add a focus trap, otherwise document the non-modal choice.

---

_Reviewed: 2026-06-02T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
