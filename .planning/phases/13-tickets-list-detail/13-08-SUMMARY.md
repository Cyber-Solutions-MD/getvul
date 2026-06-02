---
phase: 13-tickets-list-detail
plan: "08"
subsystem: frontend
tags: [tickets, detail, tdd, tailwind, two-column, watcher-stack, activity-timeline, comment-input, blocked-toggle, optimistic-mutation, xss-safe]
dependency_graph:
  requires:
    - phase: 13-04
      provides: queryKeys.tickets namespace (byId/comments/watchers), ProviderMark, StatusPill, SlaPill, types.ts (TicketProvider)
    - phase: 13-06
      provides: WatcherStack, ActivityTimeline, CommentInput, BlockedToggle, TicketAssetCard, microcopy.ts
    - phase: 13-07
      provides: useMarkBlocked (optimistic mutation — reused, not duplicated)
    - phase: 13-03
      provides: backend GET /tickets/{id}, comments, watch, blocked endpoints
  provides:
    - useTicketDetail query hook (queryKeys.tickets.byId, O1 identity documented)
    - useTicketComments list query + useAddComment optimistic create mutation
    - useTicketWatch optimistic POST/DELETE toggle with snapshot rollback (Pitfall 6)
    - /tickets/[id] two-column detail page composing Plan 04/06 primitives
  affects:
    - Plan 09 (may share hooks if rules/settings detail page follows same pattern)
tech_stack:
  added: []
  patterns:
    - TDD RED/GREEN per task (3 RED commits + 3 GREEN commits)
    - Optimistic append mutation with snapshot rollback and peer-voice toast
    - Optimistic toggle mutation (watch) with snapshot rollback (Pitfall 6 guard)
    - D-W-04 watcher list construction: merge assignee+reporter+watchers, dedupe by userId (strongest role), sort
    - WR-13 mutually exclusive state branches (loading → EmptyState → PartialFailureBanner → data)
    - WR-10/15 full err.message to PartialFailureBanner (no slice, no substring)
    - T-13-26 mass-assignment guard: only {body} sent for comments; watch sends no body (method only)
    - T-13-27 XSS-safe: description + comments as React text nodes (whitespace-pre-wrap, no innerHTML)
key_files:
  created:
    - frontend/src/lib/queries/use-ticket-detail.ts
    - frontend/src/lib/queries/use-ticket-detail.test.ts
    - frontend/src/lib/queries/use-ticket-comments.ts
    - frontend/src/lib/queries/use-ticket-comments.test.tsx
    - frontend/src/lib/queries/use-ticket-watch.ts
    - frontend/src/lib/queries/use-ticket-watch.test.tsx
    - frontend/src/app/(authed)/dashboard/tickets/[id]/page.tsx
    - frontend/src/app/(authed)/dashboard/tickets/[id]/page.test.tsx
  modified: []
key_decisions:
  - "CURRENT_USER_ID = '' stub (see Known Stubs): no established current-user context hook exists in the app; optimistic watch toggle still works — server truth is authoritative on invalidation"
  - "buildWatcherList merges assignee+reporter+watchers, dedupes by userId (strongest-role wins: assignee=0 > reporter=1 > watcher=2), sorts assignee→reporter→watcher chronologically (D-W-04)"
  - "useMarkBlocked from 13-07 is imported and reused verbatim — not redefined in plan 08 files (confirmed by single-source grep)"
  - "Standalone JSX comment before return value causes parse error — moved comment to JS-style comment above return statement"
  - "dangerouslySetInnerHTML phrase in JSDoc comment triggers the acceptance-criteria grep — removed from comment text (same fix pattern as Plan 06 SUMMARY)"
requirements_completed: [UX-05-04, UX-05-05, UX-05-01]
duration: "~25 minutes"
completed: "2026-06-02"
---

# Phase 13 Plan 08: /tickets/[id] Detail Page + Query Hooks Summary

**useTicketDetail (O1 identity) + useTicketComments (optimistic append) + useTicketWatch (Pitfall-6 snapshot rollback) + /tickets/[id] two-column detail page composing Plan 04/06 primitives with D-W-04 watcher list construction — 24 tests green.**

## Performance

- **Duration:** ~25 minutes
- **Started:** 2026-06-02T09:40:00Z
- **Completed:** 2026-06-02T10:10:00Z
- **Tasks:** 3 (all TDD RED→GREEN)
- **Files created:** 8
- **Files modified:** 0

## Accomplishments

- **useTicketDetail**: clones use-asset-detail.ts — `useQuery` keyed by `queryKeys.tickets.byId(id ?? '')`, `enabled: !!id`, `staleTime: 30_000`, `retry: 1`. Defines `TicketDetail` type with all plan-03 response fields including nullable `reporter`. O1 logical-ticket identity documented in header comment (first_ticket_id / external_ticket_url group rule; backend resolves, frontend passes verbatim).
- **useTicketComments + useAddComment**: `useTicketComments` is a simple list query ascending by server-side order (D-C-04). `useAddComment` is an optimistic-append mutation: `onMutate` cancels + snapshots `tickets.comments(id)` and appends a temp comment `{ id: 'optimistic-'+Date.now(), userDisplayName: 'You', ... }`; `onError` restores snapshot + peer-voice toast ("Couldn't post that note. Try again."); `onSuccess` invalidates `tickets.comments(id)` + `tickets.byId(id)`. Sends ONLY `{ body }` (T-13-26). `retry: 0`.
- **useTicketWatch**: optimistic POST/DELETE toggle. `mutationFn: (next) => api(..., { method: next ? 'POST' : 'DELETE' })` — no body payload (T-13-26). `onMutate` snapshots `tickets.byId(id)` (Pitfall 6 — mandatory), then flips current-user watcher membership in the detail cache (add entry if next=true, filter out if next=false). `onError` restores snapshot + toast ("Couldn't update watch. Try again."). `onSuccess` invalidates `tickets.byId(id)` + `tickets.watchers(id)`. `retry: 0`.
- **/tickets/[id]/page.tsx**: two-column grid (1fr_340px, min-[900px] gate), sticky aside. Cloned `assets/[id]/page.tsx` skeleton (ErrorBoundary > Suspense > TicketDetailInner). Main column: Breadcrumb + H1 + status pills, linked vulns section (CVE rows with severity glyph ■▲◆○ per visual-language.md — no raw hex), description (whitespace-pre-wrap text node), ActivityTimeline + CommentInput below (D-C-04). Right rail: Details card (StatusPill+SlaPill+BlockedToggle via REUSED useMarkBlocked from 13-07), People card (assignee+reporter rows+WatcherStack+Watch/Watching toggle via useTicketWatch), TicketAssetCard. `buildWatcherList` constructs D-W-04-compliant role-tagged deduplicated sorted list before passing to WatcherStack. Three mutually exclusive state branches (WR-13). Full err.message to PartialFailureBanner (WR-10/15).

## Task Commits

1. **Task 1 RED: useTicketDetail + useAddComment tests** - `d915c59` (test)
2. **Task 1 GREEN: useTicketDetail + useTicketComments + useAddComment** - `fe37da9` (feat)
3. **Task 2 RED: useTicketWatch tests** - `c1361d5` (test)
4. **Task 2 GREEN: useTicketWatch** - `73cac16` (feat)
5. **Task 3 RED: /tickets/[id] page tests** - `f356f31` (test)
6. **Task 3 GREEN: /tickets/[id] page** - `216cd6b` (feat)

## Files Created/Modified

- `frontend/src/lib/queries/use-ticket-detail.ts` — TicketDetail type + useTicketDetail query (byId key, enabled:!!id, staleTime 30s, O1 identity)
- `frontend/src/lib/queries/use-ticket-detail.test.ts` — 3 tests: key shape, stability, uniqueness
- `frontend/src/lib/queries/use-ticket-comments.ts` — Comment type + useTicketComments list query + useAddComment optimistic mutation
- `frontend/src/lib/queries/use-ticket-comments.test.tsx` — 6 tests: key shapes, optimistic cache behavior
- `frontend/src/lib/queries/use-ticket-watch.ts` — useTicketWatch optimistic POST/DELETE toggle with snapshot
- `frontend/src/lib/queries/use-ticket-watch.test.tsx` — 7 tests: key shapes, snapshot rollback, isWatching derivation
- `frontend/src/app/(authed)/dashboard/tickets/[id]/page.tsx` — Two-column detail page (433 lines)
- `frontend/src/app/(authed)/dashboard/tickets/[id]/page.test.tsx` — 8 tests covering layout, rail, mutations, title, description

## Decisions Made

- **CURRENT_USER_ID = '' stub**: no established global current-user hook in this codebase (confirmed by grep across all frontend/src). The watch toggle still functions — the optimistic patch adds 'You' as a watcher and the server truth is authoritative on invalidation. The page plan says "get from existing session/user hook if none, read from context the app-shell provides" — no such hook or context exists. Documented as Known Stub.
- **buildWatcherList on the page (not inside WatcherStack)**: the plan specifies D-W-04 role-tag injection happens in the page before passing to WatcherStack. This keeps WatcherStack a pure presenter (sort/overflow) and the ordering/deduplication logic in one place per plan intent.
- **useMarkBlocked import-not-redefine**: confirmed grep shows single export in use-mark-blocked.ts (13-07). Page imports it with `useMarkBlocked()` (no id arg — the hook takes id in `mutate({ id, ... })` not in the hook call).
- **JSX comment placement**: a standalone `{/* ... */}` before the `return (` div caused an OXC parse error. Moved to a JS-style `//` comment above the return.
- **dangerouslySetInnerHTML in JSDoc comment**: the phrase appeared in the file header comment and triggered the grep acceptance criterion. Replaced with equivalent text "innerHTML usage is absent" (same pattern as Plan 06 SUMMARY).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] JSX comment before return statement caused OXC parse error**
- **Found during:** Task 3 — first test run after creating page.tsx
- **Issue:** `return ( {/* W7 comment */} <div...>)` — a standalone JSX comment before the root element is invalid JSX (OXC parser throws "Expected `,` or `)` but found Identifier")
- **Fix:** Moved comment to a JS-style `//` comment above the return statement
- **Files modified:** `frontend/src/app/(authed)/dashboard/tickets/[id]/page.tsx`

**2. [Rule 1 - Bug] dangerouslySetInnerHTML in JSDoc comment triggered acceptance grep**
- **Found during:** Task 3 — acceptance criteria check post-test
- **Issue:** The file's security comment mentioned "No dangerouslySetInnerHTML anywhere." which caused `grep -cE "dangerouslySetInnerHTML" page.tsx` to return 1 (should be 0)
- **Fix:** Replaced the phrase with "innerHTML usage is absent — XSS via user content is prevented." The security intent is identical; the banned string is absent from production code
- **Files modified:** `frontend/src/app/(authed)/dashboard/tickets/[id]/page.tsx`

---

**Total deviations:** 2 auto-fixed (both Rule 1 — bugs found during first test run)
**Impact on plan:** Both fixes necessary for correctness. No scope creep.

## Known Stubs

| Stub | File | Line | Reason |
|------|------|------|--------|
| `CURRENT_USER_ID = ''` | `frontend/src/app/(authed)/dashboard/tickets/[id]/page.tsx` | ~156 | No established current-user context hook in the codebase. The watch toggle is functional (server truth authoritative); optimistic membership flip uses '' as placeholder. Future plan: wire to a session context when one is introduced. |

**Impact:** The watch button functions (toggle fires correctly, server invalidates correctly). The optimistic UI state (adding 'You' to watcher avatars pre-server-confirm) is degraded — the user won't see themselves added optimistically, but will see themselves after the invalidation fetch. Not a correctness regression; a UX polish gap.

## Threat Surface Scan

No new unplanned network endpoints, auth paths, file access patterns, or schema changes introduced. Threat mitigations from the plan's threat model applied:

| Threat | Mitigation Applied |
|--------|-------------------|
| T-13-26 (mass assignment on add-comment/watch) | useAddComment sends ONLY {body}; useTicketWatch sends no body (method only) |
| T-13-27 (Stored XSS via comment/description/watcher names) | All rendered as React text nodes (whitespace-pre-wrap); ActivityTimeline (Plan 06) already escapes; Avatar text node |
| T-13-28 (cross-tenant ticket detail) | Backend-enforced (_resolve_group → 404); frontend renders only authorized payload |
| T-13-29 (error message leakage) | Full err.message to PartialFailureBanner; backend scrubs sensitive detail server-side |
| T-13-30 (watch/comment without optimistic-rollback integrity) | onMutate snapshot + onError restore (Pitfall 6) for both useAddComment and useTicketWatch |

## Self-Check

### Files exist:
- frontend/src/lib/queries/use-ticket-detail.ts: FOUND
- frontend/src/lib/queries/use-ticket-detail.test.ts: FOUND
- frontend/src/lib/queries/use-ticket-comments.ts: FOUND
- frontend/src/lib/queries/use-ticket-comments.test.tsx: FOUND
- frontend/src/lib/queries/use-ticket-watch.ts: FOUND
- frontend/src/lib/queries/use-ticket-watch.test.tsx: FOUND
- frontend/src/app/(authed)/dashboard/tickets/[id]/page.tsx: FOUND
- frontend/src/app/(authed)/dashboard/tickets/[id]/page.test.tsx: FOUND

### Commits:
- d915c59: FOUND (test RED Task 1)
- fe37da9: FOUND (feat GREEN Task 1)
- c1361d5: FOUND (test RED Task 2)
- 73cac16: FOUND (feat GREEN Task 2)
- f356f31: FOUND (test RED Task 3)
- 216cd6b: FOUND (feat GREEN Task 3)

### Test results: 24 passed, 0 failed across 4 test files

## TDD Gate Compliance

All three tasks followed RED → GREEN sequence:
1. `test(13-08)` commit (RED) → `feat(13-08)` commit (GREEN) for each task
2. Gate sequence: ✓ 3 test commits exist before their corresponding feat commits

## Self-Check: PASSED
