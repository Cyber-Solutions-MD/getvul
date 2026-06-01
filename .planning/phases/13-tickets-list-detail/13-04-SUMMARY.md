---
phase: 13-tickets-list-detail
plan: "04"
subsystem: frontend
tags: [primitives, query-keys, design-system, tailwind, tdd]
dependency_graph:
  requires: []
  provides:
    - queryKeys.tickets namespace (list/byId/comments/watchers/rules) in keys.ts
    - --gradient-provider-jira/asana/github CSS tokens in globals.css
    - ProviderMark component (gradient square, zero hex, zero logos)
    - StatusPill component (4 states + leading dot, Blocked alongside)
    - SlaPill component (client-side tier compute)
    - VulnCount component (T·C·H with edge cases)
    - TicketProvider / TicketStatus types in types.ts
  affects:
    - Plans 07/08/09 (import queryKeys.tickets read-only)
    - Plan 05 (uses SlaPill + StatusPill + ProviderMark in drill content)
tech_stack:
  added: []
  patterns:
    - TDD RED/GREEN/REFACTOR per task
    - CSS-variable gradient token (hex lives once in globals.css, consumed via var())
    - Literal lookup object for XSS-safe provider → gradient mapping
    - Client-side SLA tier computation (thresholds in one place, Pitfall 5)
    - as const tuples in queryKeys namespace (D-D-03 convention)
key_files:
  created:
    - frontend/src/components/tickets/types.ts
    - frontend/src/components/tickets/provider-mark.tsx
    - frontend/src/components/tickets/provider-mark.test.tsx
    - frontend/src/components/tickets/status-pill.tsx
    - frontend/src/components/tickets/status-pill.test.tsx
    - frontend/src/components/tickets/sla-pill.tsx
    - frontend/src/components/tickets/sla-pill.test.tsx
    - frontend/src/components/tickets/vuln-count.tsx
    - frontend/src/components/tickets/vuln-count.test.tsx
    - frontend/src/lib/queries/keys.test.ts
  modified:
    - frontend/src/lib/queries/keys.ts
    - frontend/src/app/globals.css
decisions:
  - queryKeys.tickets namespace defined once in keys.ts as single source; Plans 07/08/09 import read-only
  - Provider gradient hex lives in globals.css :root block; components use var(--gradient-provider-*) only
  - ProviderMark uses literal lookup object for provider→gradient to prevent var-injection (T-13-14)
  - StatusPill Blocked renders alongside provider pill (not replacement) per D-P-04
  - SlaPill thresholds (7d Soon boundary) defined once in sla-pill.tsx (Pitfall 5)
  - VulnCount em dash for total=0; 99+ cap for total>99; zeros explicit
metrics:
  duration: "~10 minutes"
  completed: "2026-06-01"
  tasks_completed: 3
  tasks_total: 3
  tests_added: 32
  files_created: 10
  files_modified: 2
---

# Phase 13 Plan 04: Ticket Presentational Primitives + Query Keys Summary

**One-liner:** queryKeys.tickets namespace (list/byId/comments/watchers/rules as const tuples) + three CSS gradient tokens + ProviderMark/StatusPill/SlaPill/VulnCount with zero inline hex and 32 co-located tests green.

## What Was Built

### queryKeys.tickets namespace (keys.ts)
Added a `tickets:` block as a sibling to `assets:` inside the existing `queryKeys` object, using identical `as const` tuple style. This is the **single source** — Plans 07, 08, and 09 import these read-only, never re-declare them. Namespace includes: `all` (prefix invalidator), `list(opts)`, `byId(id)`, `comments(id)`, `watchers(id)`, `rules()`.

### Provider gradient tokens (globals.css)
Added three CSS variables to a new `:root` block in `globals.css`:
- `--gradient-provider-jira: linear-gradient(135deg, #5C9CFF, #2684FF)`
- `--gradient-provider-asana: linear-gradient(135deg, #FF8AA0, #F1506E)`
- `--gradient-provider-github: linear-gradient(135deg, #C7BAFF, #A78BFA)`

Hex lives ONCE here (A4 resolution from RESEARCH). Components consume via `var()` only.

### ProviderMark (provider-mark.tsx)
14px `size-3.5 rounded-[3px]` gradient square with a text glyph initial (J/A/G). Uses a literal `Record<TicketProvider, string>` lookup to map provider → CSS var reference — prevents CSS var injection via user-controlled provider values (T-13-14 mitigation). No `<img>`, no `.svg`, no inline hex.

### StatusPill (status-pill.tsx)
Maps `externalStatus` case-insensitively through a locked class-map (D-P-04):
- Open → `border-violet/40 bg-violet-soft text-violet`
- In progress → `border-amber/40 bg-amber/10 text-amber`
- Completed → `border-severity-low/40 bg-severity-low/10 text-severity-low`
- Blocked → `border-severity-critical/40 bg-severity-critical/10 text-severity-critical`

Leading dot: `<span class="size-1.5 rounded-full bg-current" />`. When `blocked=true`, renders the provider pill **and** a Blocked pill side-by-side — not a replacement.

### SlaPill (sla-pill.tsx)
Client-side tier computation per D-SLA-04. Thresholds defined ONCE here (Pitfall 5). `SOON_THRESHOLD_MS = 7 * 24 * 60 * 60 * 1000`. Tiers: Overdue/Soon/OK/Unknown → mapped to severity-critical/severity-high/severity-low/text-faint classes. `font-mono` per visual-language.md. Label shows relative time string ("−2h", "3d left", "Unknown").

### VulnCount (vuln-count.tsx)
T·C·H format per D-L-02: total `text-text`, critical `text-severity-critical`, high `text-severity-high`. Zeros explicit. total=0 → `—` em dash (no breakdown). total>99 → `99+`. Middot `·` separator.

### types.ts
```ts
export type TicketProvider = 'jira' | 'asana' | 'github';
export type TicketStatus = 'open' | 'in_progress' | 'completed' | 'blocked';
```

## Tests

32 tests across 5 files, all green:
- `keys.test.ts` — 8 tests: all/list/byId/comments/watchers/rules tuples + prefix invalidation + assets regression
- `provider-mark.test.tsx` — 6 tests: jira/asana/github gradient vars, distinct per provider, no img, aria-label
- `status-pill.test.tsx` — 7 tests: open violet, completed severity-low, in_progress amber, COMPLETED case-insensitive, blocked both pills, blocked severity-critical, label copy
- `sla-pill.test.tsx` — 5 tests: Overdue/Soon/OK/Unknown tiers + font-mono
- `vuln-count.test.tsx` — 6 tests: T·C·H colors, zeros explicit, total=0 em dash, total=150 → 99+, total=99 uncapped, total=100 capped

## Deviations from Plan

None — plan executed exactly as written.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. All components are pure presentational (no external data fetching). T-13-14 mitigated via literal lookup objects + React text node rendering.

## Self-Check

### Files exist:
- frontend/src/lib/queries/keys.ts: FOUND (modified)
- frontend/src/lib/queries/keys.test.ts: FOUND (created)
- frontend/src/app/globals.css: FOUND (modified)
- frontend/src/components/tickets/types.ts: FOUND (created)
- frontend/src/components/tickets/provider-mark.tsx: FOUND (created)
- frontend/src/components/tickets/provider-mark.test.tsx: FOUND (created)
- frontend/src/components/tickets/status-pill.tsx: FOUND (created)
- frontend/src/components/tickets/status-pill.test.tsx: FOUND (created)
- frontend/src/components/tickets/sla-pill.tsx: FOUND (created)
- frontend/src/components/tickets/sla-pill.test.tsx: FOUND (created)
- frontend/src/components/tickets/vuln-count.tsx: FOUND (created)
- frontend/src/components/tickets/vuln-count.test.tsx: FOUND (created)

### Commits:
- 52c2d6d: feat(13-04): queryKeys.tickets namespace + provider gradient tokens + ProviderMark + types.ts
- 596d58d: feat(13-04): StatusPill (4 states + leading dot, Blocked alongside)
- b21fea2: feat(13-04): SlaPill (client-side tier) + VulnCount (T·C·H)

## Self-Check: PASSED
