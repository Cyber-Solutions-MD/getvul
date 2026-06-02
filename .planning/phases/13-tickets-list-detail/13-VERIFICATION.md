---
phase: 13-tickets-list-detail
verified: 2026-06-02T00:00:00Z
status: human_needed
score: 6/6 must-haves verified
overrides_applied: 0
gaps: []
post_verification_fixes:
  - finding: "SC3 — StatusPill Completed rendered severity-low (#A78BFA lavender) instead of success green"
    resolution: "Fixed in commit 21a0b5c — Completed now uses border-success/40 bg-success/10 text-success (--color-success / #4ADE80) per SC3 and visual-language.md; component + test updated, 21/21 affected tests green. References win over Plan 13-04's mislabel, so this was fixed rather than accepted as an override."
human_verification:
  - test: "Assignee resolution with real connector data"
    expected: "When the backend resolves assignee as a Person object (email match in users table or fallback synthesized object), the People card in /tickets/[id] renders the correct displayName and Avatar. Confirm with actual Jira/Asana ticket data (not test fixtures)."
    why_human: "The assignee-resolution heuristic (match users.email == assignee string, else synthesize a display-only Person) is flagged by REVIEW-FIX.md as requiring human verification against real connector data shapes."
  - test: "SLA/severity/status chip filter semantic correctness"
    expected: "Selecting 'Critical' severity chip narrows the list to tickets with max_severity=CRITICAL. Selecting 'In progress' status chip returns only in-progress tickets. Selecting 'Overdue' SLA chip returns only tickets past their sla_due_at. No silent no-ops."
    why_human: "REVIEW-FIX.md flags WR-01 (four-status-chip → backend-semantics mapping and severity/SLA filter semantics) as requiring human end-to-end confirmation. No dedicated tests exercise the filter behavior against real data."
---

# Phase 13: `/tickets` List + Detail Verification Report

**Phase Goal:** An analyst can review remediation work as a list with provider-aware identity chips and open a two-column detail that ties the ticket to its linked vulnerabilities, asset, and people.
**Verified:** 2026-06-02T00:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Verification Context

This phase had a post-execution code-review gate (13-REVIEW.md) that found 6 critical + 9 warning issues — primarily a systematic snake_case/camelCase frontend-backend contract mismatch. All 15 findings were fixed in 13-REVIEW-FIX.md before this verification. Verification confirms the fixes are present in the actual codebase and that the original phase goals are achieved.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `/tickets` list renders chip-bar + table with 8 spec columns; rows open side-panel drill | VERIFIED | `TicketsChipBar` (4 axes: Status/Provider/Severity/SLA) + `TicketsTable` (8 column headers: Severity/Provider/ID/Title/Vulns/Assignee/Status/SLA) in `tickets/page.tsx`; `DrillPanel idKey="ticket"` + `DrillPanelMobile idKey="ticket"` wired with `TicketDrillContent` |
| 2 | Provider identity renders as gradient-mark chips, not logos; zero trademark assets in `frontend/public/` | VERIFIED | `ProviderMark` uses `PROVIDER_GRADIENTS` lookup (`var(--gradient-provider-*)`) — no `<img>` tags, no SVGs. CSS tokens in `globals.css` lines 59-61. `frontend/public/` is empty (ls confirms). Test files contain `atlassian.net` URLs as data only (not assets). |
| 3 | Status pills use a separate color family from severity with leading colored dot | VERIFIED | Open=violet, In progress=amber, Blocked=severity-critical(red), Completed=success green are all correct. Leading `<Dot />` component present. **Completed color fixed post-verification in commit 21a0b5c** (was `severity-low` lavender → now `success` green per SC3 / `visual-language.md`). |
| 4 | `/tickets/[id]` two-column layout with linked vulns + description + timeline + right rail | VERIFIED | `grid-cols-[1fr_340px]` at 900px breakpoint — identical to `assets/[id]/page.tsx`. Main column: linked vulns (`t.linked_vulns.map()`, up to 20 rows from backend), description (text node, XSS-safe), `ActivityTimeline` + `CommentInput`. Right rail: Details card (StatusPill + SlaPill + BlockedToggle), People card (assignee + reporter + `WatcherStack` with +N overflow + Watch toggle), `TicketAssetCard` (cross-links to `/assets/{assetId}`). Backend emits `linked_vulns`, `description`, `assignee` (Person object), `reporter`, `watchers`, `asset` object — all fields verified in `router.py:865-895`. |
| 5 | List/Board segmented toggle in page-head-actions zone; Board shows placeholder copy | VERIFIED | Toggle rendered inside `<header>` as `role="group" aria-label="View mode"` with `aria-pressed`. Board branch shows `BOARD_PLACEHOLDER` constant. `?view=board` URL param persisted via `useUrlState`. |
| 6 | State patterns reused from Phase 11 with no new variants; vuln-count uses condensed T·C·H format | VERIFIED | Both `tickets/page.tsx` and `tickets/[id]/page.tsx` import `SkeletonTable`, `EmptyState`, `PartialFailureBanner` from `@/components/states` (Phase 11). No new state components defined. `VulnCount` renders `{total}·{critical}·{high}` with middot separator and color tokens (no inline hex). |

**Score:** 6/6 truths verified (SC3 Completed-color deviation fixed post-verification in commit 21a0b5c)

### Deferred Items

None.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|---------|--------|---------|
| `backend/alembic/versions/026_add_ticket_comments.py` | ticket_comments table | VERIFIED | File exists; contains `op.create_table('ticket_comments'` and `down_revision = "025_add_asset_tags"` |
| `backend/alembic/versions/027_add_ticket_blocked_sla.py` | blocked/sla columns + backfill | VERIFIED | Contains `ix_tickets_tenant_sla` index and `FROM vulnerabilities` backfill |
| `backend/alembic/versions/028_add_ticket_watchers.py` | ticket_watchers table | VERIFIED | Contains `op.create_table('ticket_watchers'` |
| `backend/app/ticketing/models.py` | Ticket.blocked/blocked_reason/sla_due_at + TicketComment + TicketWatcher ORM | VERIFIED | `class TicketComment`, `class TicketWatcher`, `blocked_reason`, `sla_due_at` all grep-confirmed |
| `backend/app/ticketing/schemas.py` | CommentCreate + BlockedUpdate | VERIFIED | `class BlockedUpdate`, `max_length=10000`, `max_length=500` grep-confirmed |
| `frontend/src/components/tickets/types.ts` | TicketProvider + TicketStatus types | VERIFIED | Exists, exports `TicketProvider = 'jira' | 'asana' | 'github'` and `TicketStatus = 'open' | 'in_progress' | 'completed' | 'blocked'` |
| `frontend/src/components/tickets/provider-mark.tsx` | ProviderMark gradient-square component | VERIFIED | Exists; uses `PROVIDER_GRADIENTS` literal lookup with `var(--gradient-provider-*)` CSS vars; no `<img>`, no hex |
| `frontend/src/components/tickets/status-pill.tsx` | StatusPill with 4 states + leading dot | VERIFIED | Exists; `<Dot/>` component; STATUS_MAP and BLOCKED_CONFIG defined; leading dot rendered |
| `frontend/src/components/tickets/sla-pill.tsx` | SlaPill client-side tier computation | VERIFIED | Client-side tier from `sla_due_at` string; 3 tiers (overdue/soon/ok/unknown) |
| `frontend/src/components/tickets/vuln-count.tsx` | VulnCount T·C·H format | VERIFIED | Renders `{total}·{critical}·{high}` with middot; zero total → em dash; >99 → 99+ |
| `frontend/src/components/tickets/tickets-chip-bar.tsx` | TicketsChipBar 4 axes | VERIFIED | 4 ChipAxis: status/provider/severity/sla with hardcoded allow-lists |
| `frontend/src/components/tickets/tickets-table.tsx` | TicketsTable 8-column | VERIFIED | 8 `<th>` headers (Severity/Provider/ID/Title/Vulns/Assignee/Status/SLA); reads snake_case fields from TicketSummary |
| `frontend/src/components/tickets/watcher-stack.tsx` | WatcherStack with +N overflow | VERIFIED | Exists; `dedupeAndSort` by role priority; shows first 3 avatars; +N overflow button with accessible popover |
| `frontend/src/components/tickets/activity-timeline.tsx` | ActivityTimeline with day grouping | VERIFIED | `groupByDay` with local-day key (WR-08 fix); `Number.isFinite` guard (WR-09 fix); Invalid timestamps → "Unknown date" |
| `frontend/src/components/tickets/comment-input.tsx` | CommentInput | VERIFIED | Exists (confirmed via directory listing + wiring in detail page) |
| `frontend/src/components/tickets/blocked-toggle.tsx` | BlockedToggle | VERIFIED | Exists; wired in both list page drill and detail page right rail |
| `frontend/src/components/tickets/ticket-asset-card.tsx` | TicketAssetCard with asset link | VERIFIED | Exists; renders hostname/osName/riskScore; `Link href="/assets/{assetId}"`; multi-host fallback |
| `frontend/src/app/(authed)/dashboard/tickets/page.tsx` | Tickets list page | VERIFIED | Exists; full list page with chip-bar, table, drill, bulk-bar, board toggle |
| `frontend/src/app/(authed)/dashboard/tickets/[id]/page.tsx` | Ticket detail page | VERIFIED | Exists; two-column layout; all right-rail sections present |
| `frontend/src/lib/queries/use-tickets.ts` | useTickets + TicketSummary (snake_case) | VERIFIED | `TicketSummary` type uses snake_case (`external_ticket_id`, `vuln_count`, `max_severity`, etc.); `buildSearchParams` exported |
| `frontend/src/lib/queries/use-ticket-detail.ts` | useTicketDetail + TicketDetail type | VERIFIED | `TicketDetail` uses snake_case top-level; nested `assignee`/`reporter`/`asset` keep camelCase keys matching backend |
| `frontend/src/lib/queries/use-ticket-comments.ts` | useTicketComments with snake_case | VERIFIED | `Comment` type uses `user_display_name`, `created_at`, `edited_at`; optimistic add matches wire shape |
| `frontend/src/lib/queries/use-mark-blocked.ts` | useMarkBlocked optimistic mutation | VERIFIED | Both optimistic branches write `blocked_reason` (snake) — WR-07 fix confirmed |
| `frontend/src/app/globals.css` | Provider gradient CSS tokens | VERIFIED | Lines 59-61: `--gradient-provider-jira/asana/github` defined; jira=cool-blue, asana=coral, github=violet |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `tickets/page.tsx` | `GET /api/v1/tickets` | `useTickets` → `api()` | WIRED | `buildSearchParams` serializes filters; response consumed |
| `tickets/page.tsx` | `POST /api/v1/tickets/bulk-action` | `handleBulkAction` → `api()` | WIRED | CR-01 fix: sends `ticket_urls` (not `external_ticket_urls`); confirmed line 182 |
| `tickets-table.tsx` | `TicketSummary.provider` | `isTicketProvider()` guard | WIRED | CR-06 fix: validates lowercase provider before `<ProviderMark>`; no unchecked `as` cast |
| `tickets/[id]/page.tsx` | `GET /api/v1/tickets/{id}` | `useTicketDetail` | WIRED | Response type `TicketDetail` (snake_case top-level) matches backend dict keys confirmed in `router.py:865-895` |
| `tickets/[id]/page.tsx` | `GET /api/v1/tickets/{id}/comments` | `useTicketComments` | WIRED | CR-05 fix: backend LEFT JOINs users and emits `user_display_name`; frontend reads `user_display_name` and `created_at` |
| `tickets/[id]/page.tsx` | `useAuth()` | `user.id` → `currentUserId` | WIRED | WR-06 fix: `const { user } = useAuth()` line 165; `isWatching` compares real userId |
| `status-pill.tsx` | `TicketSummary.external_status` | `externalStatus` prop | WIRED | Table passes `r.external_status`; pill normalizes to lowercase and maps |
| `vuln-count.tsx` | `TicketSummary.vuln_count/critical_count/high_count` | props | WIRED | Table passes `r.vuln_count`, `r.critical_count`, `r.high_count` — all snake_case matching backend |
| `ticket-asset-card.tsx` | `TicketDetail.asset` | nested camelCase object | WIRED | Detail page passes `t.asset?.assetId`, `t.asset?.hostname`, etc.; backend emits `assetId`/`hostname` camelCase in nested `asset` object |
| `ProviderMark` | `globals.css` CSS vars | `var(--gradient-provider-*)` | WIRED | `PROVIDER_GRADIENTS` lookup keys exactly match CSS variable names |
| `useMarkBlocked` | detail + list cache | `onMutate` optimistic update | WIRED | WR-07 fix: both branches write `blocked_reason` (snake) |
| `backend list_tickets` | frontend `TicketSummary` | snake_case wire contract | WIRED | `service.py:874-896` emits `external_ticket_id`, `external_ticket_url`, `external_status`, `max_severity`, `vuln_count`, `critical_count`, `high_count`, `blocked_reason`, `sla_due_at` — all match `TicketSummary` type |
| `backend detail endpoint` | frontend `TicketDetail` | snake_case top-level | WIRED | `router.py:865-895` emits `external_ticket_id`, `external_ticket_url`, `external_status`, `blocked`, `blocked_reason`, `sla_due_at`, `description`, `max_severity`, `critical_count`, `high_count`, `linked_vulns`, `watchers`, `asset`, `assignee` (as Person object), `reporter` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| `tickets-table.tsx` | `rows: TicketSummary[]` | `useTickets` → `GET /api/v1/tickets` → `list_tickets` in `service.py` | Yes — SQL GROUP BY query over `tickets` table with vuln join | FLOWING |
| `tickets/[id]/page.tsx` | `t: TicketDetail` | `useTicketDetail` → `GET /api/v1/tickets/{id}` → `get_ticket_detail` in `router.py` | Yes — SQL aggregation over `tickets` + `vulnerabilities` + `assets` + `users` | FLOWING |
| `ProviderMark` | `gradient: string` | `PROVIDER_GRADIENTS[provider]` → CSS var → `globals.css` | Yes — CSS variable resolves to real gradient | FLOWING |
| `WatcherStack` | `watchers: Watcher[]` | `buildWatcherList({ assignee, reporter, watchers })` → `useTicketDetail` | Yes — backend joins `ticket_watchers` + `users` | FLOWING |
| `ActivityTimeline` | `entries: TimelineEntry[]` | `mapCommentsToEntries(commentList)` → `useTicketComments` → backend | Yes — backend LEFT JOINs `ticket_comments` + `users` | FLOWING |
| `TicketAssetCard` | `assetId`, `hostname`, `osName`, `riskScore` | `t.asset` → backend `asset_obj` from `Asset` join | Yes — backend emits real asset data for single-host groups; null for multi-host | FLOWING |
| `SlaPill` | `dueAt: string \| null` | `r.sla_due_at` / `t.sla_due_at` from wire | Yes — computed from `tickets.sla_due_at` column (backfilled from vuln) | FLOWING |

### Behavioral Spot-Checks

Step 7b: SKIPPED — requires running server with live database. No runnable entry points available without Docker Compose up.

### Requirements Coverage

The requirement IDs UX-05-01 through UX-05-06 are defined in ROADMAP.md for this phase. REQUIREMENTS.md tracks only the v1.0 production-readiness milestone (PROD-01 through PROD-08); UX-05 requirements belong to the v2.0 UI/UX Redesign milestone and are intentionally absent from REQUIREMENTS.md. No orphaned requirements — all 6 UX-05 IDs are claimed across the 9 plans.

| Requirement | Plans | Description | Status |
|-------------|-------|-------------|--------|
| UX-05-01 | 03, 04, 05, 07, 08, 09 | `/tickets` list table + chip-bar | SATISFIED — TicketsTable, TicketsChipBar, DrillPanel wired |
| UX-05-02 | 02, 04, 07 | Provider gradient marks, not logos | SATISFIED — ProviderMark with CSS gradient vars, empty public/ |
| UX-05-03 | 01, 03, 04 | Status pills with color family + dot | PARTIAL — color family correct for Open/InProgress/Blocked; Completed uses severity-low (lavender) instead of green |
| UX-05-04 | 03, 06, 08 | `/tickets/[id]` two-column detail with right rail | SATISFIED — two-column layout, Details/People/Asset rail |
| UX-05-05 | 01, 03, 06, 08 | People card: assignee + reporter + watcher stack | SATISFIED — WatcherStack with +N overflow; buildWatcherList; useTicketWatch |
| UX-05-06 | 04, 07, 09 | List/Board toggle + Board placeholder | SATISFIED — segmented toggle in header, Board placeholder copy |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|---------|--------|
| `status-pill.tsx` | 40-43 | Uses `severity-low` (#A78BFA lavender) for "Completed" state | Warning | Visual deviation from SC3 ("Completed green") and `visual-language.md` (green = `--color-success`). The plan 13-04 explicitly specified this and labeled it "green" erroneously. Functional behavior is correct; color is wrong per design spec. |
| `use-tickets.ts` | — | No test exercises filter behavior against real backend | Info | WR-01 fix added server-side filter logic; no dedicated tests for severity/SLA/search filter semantics. Covered by human verification item 3. |

### Human Verification Required

#### 1. StatusPill "Completed" renders green vs. violet

**Test:** Navigate to `/dashboard/tickets`. Apply the "Completed" status chip filter (or have at least one completed ticket). Observe the Completed pill color in the table.
**Expected:** Completed pill should be green (matching `--color-success` / `#4ADE80`), visually distinct from violet (Open) and consistent with `visual-language.md` spec.
**Why human:** The code is deterministic — `status-pill.tsx` uses `severity-low` (#A78BFA lavender/violet). ROADMAP SC3 and `visual-language.md` require green. Plan 13-04 explicitly chose `severity-low` and mislabeled it "green". A human must decide: accept the deviation (add override to this VERIFICATION.md) or fix `status-pill.tsx` to use `text-success / bg-success/10 / border-success/40`.

**To accept the deviation, add to VERIFICATION.md frontmatter:**
```yaml
overrides:
  - must_have: "Status pills use the separate color family from severity (Open violet · In progress amber · Completed green · Blocked red) with leading colored dot"
    reason: "Plan 13-04 deliberately chose severity-low (lavender) for Completed to stay within the sunset palette's existing token set; green (#4ADE80 success) is a semantic success color, not a ticket-status color. Design team to confirm."
    accepted_by: ""
    accepted_at: ""
```

#### 2. Assignee resolution with real connector data

**Test:** Open a ticket from a real Jira or Asana sync that has an assignee set. Navigate to `/tickets/[id]`. Inspect the People card.
**Expected:** Assignee name renders correctly (not "unknown@example.com" or the raw email string). Avatar has the right initials/gravatar.
**Why human:** The backend heuristic (match `users.email == assignee_string`, else synthesize a display-only Person with `userId: f"assignee:{raw_assignee}"`) was flagged in REVIEW-FIX.md as needing real-data verification. Tests use controlled fixtures.

#### 3. Chip-bar filter semantic correctness

**Test:** With actual ticket data: (a) select "Critical" severity chip — verify only Critical-max-severity tickets appear. (b) select "In progress" status chip — verify only in-progress tickets appear. (c) select "Overdue" SLA chip — verify only past-SLA tickets appear.
**Expected:** Each chip narrows the result set correctly; no silent no-ops or mismapped status values.
**Why human:** REVIEW-FIX.md (WR-01 fix) notes the four-status-chip → backend mapping and SLA/severity filter semantics are product decisions with no dedicated tests; "existing list tests pass but the filter behavior should be confirmed end-to-end."

### Gaps Summary

No hard gaps found. The phase goal is substantially achieved with one observable deviation (SC3 Completed color: lavender instead of green) that requires a human product/design decision before the phase can be declared fully passed.

The post-review critical fixes (CR-01 through CR-06) are all present in the codebase:
- CR-01: `ticket_urls` key in bulk-action POST body — FIXED
- CR-02: `assignee` resolved to Person object (not bare string) — FIXED
- CR-03: detail endpoint emits `description`, `asset`, `external_ticket_id`, severity counts — FIXED
- CR-04: `TicketSummary` type and all accessors use snake_case — FIXED
- CR-05: comments endpoint emits `user_display_name`; timeline reads `created_at` — FIXED
- CR-06: backend emits lowercase `provider`; frontend validates with `isTicketProvider()` — FIXED

---

_Verified: 2026-06-02T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
