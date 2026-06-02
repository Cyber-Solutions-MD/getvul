---
phase: 13-tickets-list-detail
plan: "09"
subsystem: frontend
tags: [tickets, rules, sunset-rewrite, tdd, query-hook, sidebar, chip-bar, state-patterns]
dependency_graph:
  requires:
    - queryKeys.tickets.rules() from Plan 04 (keys.ts)
    - ChipBar primitive (Plan 12-04)
    - SkeletonTable / EmptyState / PartialFailureBanner (Phase 11/12)
  provides:
    - useTicketRules hook (GET /api/v1/tickets/rules, queryKeys.tickets.rules())
    - /tickets/rules standalone sunset route (full v1 rewrite, D-S-01)
    - sidebar Rules link → /dashboard/tickets/rules
  affects:
    - frontend/src/components/shell/sidebar.tsx (new Rules nav item)
tech_stack:
  added: []
  patterns:
    - TDD RED/GREEN per task
    - ErrorBoundary > Suspense > Inner composition (assets/page.tsx pattern)
    - WR-13 mutually exclusive state branches (error > loading > empty > list)
    - WR-10 full err.message forwarded to PartialFailureBanner (no .slice)
    - T-12-05 hardcoded allowList on ChipAxis (T-13-31 reflected XSS mitigation)
    - T-13-32 React text node rendering (no dangerouslySetInnerHTML)
key_files:
  created:
    - frontend/src/lib/queries/use-ticket-rules.ts
    - frontend/src/lib/queries/use-ticket-rules.test.tsx
    - frontend/src/app/(authed)/dashboard/tickets/rules/page.tsx
    - frontend/src/app/(authed)/dashboard/tickets/rules/page.test.tsx
  modified:
    - frontend/src/components/shell/sidebar.tsx
decisions:
  - TicketRule type mirrors TicketRuleResponse backend field names verbatim (is_enabled not enabled; schedule_minutes not schedule)
  - Status chip axis uses allowList ['enabled','disabled'] clamped on read+write (T-12-05 / T-13-31)
  - Sidebar Rules item added as flat NavItem in WORKFLOW_ITEMS (no chip per D-N-01); uses Zap icon from lucide-react
  - Client-side filter applied to loaded rule list (no extra fetch per rule read-only scope)
  - Empty filtered state gets separate EmptyState ("No rules match these filters") to distinguish from no-rules-exist state
metrics:
  duration: "~8 minutes"
  completed: "2026-06-02"
  tasks_completed: 2
  tasks_total: 2
  tests_added: 7
  files_created: 4
  files_modified: 1
---

# Phase 13 Plan 09: /tickets/rules Sunset Route + useTicketRules Hook Summary

**One-liner:** standalone /tickets/rules sunset route (ChipBar + WR-13 state branches + verbatim TicketRule type) + sidebar Rules link, zero v1 carryover, zero inline hex, 7 TDD tests green.

## What Was Built

### useTicketRules hook (use-ticket-rules.ts)

Read-only list query for `GET /api/v1/tickets/rules`. Follows the `use-assets.ts` pattern exactly:
- `export type TicketRule` with verbatim backend field names from `TicketRuleResponse` (schemas.py): `id`, `name`, `is_enabled`, `conditions`, `action`, `saved_filter_id`, `schedule_minutes`, `last_run_at`, `last_run_status`, `last_run_tickets_created`, `created_at`.
- `export function useTicketRules()` → `useQuery({ queryKey: queryKeys.tickets.rules(), queryFn: ({ signal }) => api<TicketRule[]>('/api/v1/tickets/rules', { signal }), staleTime: 30_000, retry: 1 })`.
- Imports `queryKeys.tickets.rules()` from `keys.ts` (Plan 04 single source) — never re-declares.

### /tickets/rules page (rules/page.tsx)

Full sunset rewrite of the v1 `?tab=rules` surface (D-S-01). Architecture mirrors `assets/page.tsx`:
- `ErrorBoundary > Suspense > RulesPageInner` composition.
- `ChipBar` with Status axis (`allowList: ['enabled', 'disabled']`, T-12-05 / T-13-31 mitigation).
- `useDocumentTitle('Automation rules')` + peer-voice heading.
- **WR-13 mutually exclusive branches:** `q.error → PartialFailureBanner | q.isLoading → SkeletonTable | data.length===0 → EmptyState | else → RulesList`.
- **WR-10:** full `(q.error as Error).message` passed to `PartialFailureBanner.requestId` — no `.slice()` or `.substring()`.
- `RulesList` renders each rule as a table row: name (text node, T-13-32), enabled/disabled pill (sunset tokens — `bg-severity-low/10 text-severity-low` for enabled, `bg-surface-2 text-text-faint` for disabled), provider/mode summary, schedule.
- Empty state peer voice: "No automation rules yet — Create a rule to auto-route new findings to your ticketing provider."
- No v1 imports (`RulesPanel`, `CommentModal`), no inline hex.

### Sidebar update (sidebar.tsx)

Added `{ label: 'Rules', href: '/dashboard/tickets/rules', icon: Zap }` to `WORKFLOW_ITEMS` as a flat NavItem sibling (D-N-01 — no chip). Zero `?tab=rules` references remain in the sidebar.

## Tests

7 tests across 2 files, all green:
- `use-ticket-rules.test.tsx` — 2 tests: endpoint + queryKey verification; verbatim TicketRule field names.
- `page.test.tsx` — 5 tests: ChipBar + rules list render; loading → SkeletonTable (WR-13); empty → EmptyState peer voice (WR-13); error → PartialFailureBanner full message (WR-10/13); no v1 salvage assertion.
- Sidebar regression: `sidebar.test.tsx` — 7 existing tests still green.

## Deviations from Plan

None — plan executed exactly as written.

## Threat Surface Scan

No new network endpoints introduced. The GET `/api/v1/tickets/rules` endpoint is pre-existing backend (no new attack surface). Threat mitigations applied as specified in the plan's threat model:
- T-13-31: ChipAxis `allowList: ['enabled','disabled']` — `useUrlStateList` clamps reflected URL values on read+write.
- T-13-32: Rule names and conditions rendered as React text nodes (no `dangerouslySetInnerHTML`).
- T-13-33: Authz accepted — read-only surface inherits backend route's tenant scoping.
- T-13-34: Full `err.message` forwarded to `PartialFailureBanner`; backend scrubs server-side.

## Self-Check

### Files exist:
- frontend/src/lib/queries/use-ticket-rules.ts: FOUND (created)
- frontend/src/lib/queries/use-ticket-rules.test.tsx: FOUND (created)
- frontend/src/app/(authed)/dashboard/tickets/rules/page.tsx: FOUND (created)
- frontend/src/app/(authed)/dashboard/tickets/rules/page.test.tsx: FOUND (created)
- frontend/src/components/shell/sidebar.tsx: FOUND (modified)

### Commits:
- c70fe08: test(13-09): add failing tests for useTicketRules hook (RED)
- ac20370: feat(13-09): implement useTicketRules hook (GREEN)
- 4714af0: test(13-09): add failing tests for /tickets/rules page (RED)
- 9c4ddfc: feat(13-09): /tickets/rules sunset page + sidebar Rules link (GREEN)

## Self-Check: PASSED
