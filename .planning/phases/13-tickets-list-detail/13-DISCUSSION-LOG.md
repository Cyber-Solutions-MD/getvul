# Phase 13: `/tickets` List + Detail — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in 13-CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-01
**Phase:** 13-tickets-list-detail
**Areas discussed:** Out-of-scope cleanup · Comment input behavior · Status pill interaction · Side-panel drill shape · Provider scope (extra) · SLA derivation (extra) · Watcher source (extra)

---

## Initial Selection: Gray Areas

| Option | Description | Selected |
|--------|-------------|----------|
| Out-of-scope cleanup | v1 /tickets page mixes list + Rules tab + Asana config + bulk-actions. Decide what stays in P13 vs deferred to P14. | ✓ |
| Comment input behavior | Local audit notes vs provider write-back vs hybrid. | ✓ |
| Status pill interaction | Display-only vs interactive transitions. | ✓ |
| Side-panel drill shape | Slim / Standard / Rich content depth. | ✓ |

**User's choice:** All 4 areas selected.

---

## Out-of-scope cleanup

### v1 Rules tab fate

| Option | Description | Selected |
|--------|-------------|----------|
| Move to /tickets/rules (own route, P13) | Extract Rules into its own route now. Slight scope nudge but avoids dead chrome in the rewrite. | ✓ |
| Leave v1 Rules untouched, restyle in P14 (Recommended) | P14 covers it as part of v1-styling sweep. Cleanest scope discipline. | |
| Cut Rules entirely from P13 nav | Hide Rules from topnav in P13; analyst can't access it. Most aggressive. | |

**User's choice:** Move to /tickets/rules (own route, P13).

### Asana config + setup + sync-status surface

| Option | Description | Selected |
|--------|-------------|----------|
| Move to /dashboard/connectors (Recommended) | Asana workspace/project picker + OAuth setup is connector chrome. Belongs under /dashboard/connectors (P14). | ✓ |
| Keep on /tickets as collapsed banner | Asana config stays as a collapsed banner / empty-state link when not set up. Lower friction but mixes concerns. | |
| Leave v1 Asana surface untouched in P13 | Treat as cosmetic debt; P14 will sort. | |

**User's choice:** Move to /dashboard/connectors (P14 territory).

### Bulk actions on list

| Option | Description | Selected |
|--------|-------------|----------|
| Keep — with Phase 11 BulkActionBar pattern (Recommended) | Multi-select with bottom-anchored bulk-actions bar. Common operation. | ✓ |
| Defer to P14 — single-row actions only in P13 | Reduces P13 scope; trades analyst velocity. | |
| Keep but limit to 'Close' only | Multi-select Close in P13, comments + others deferred. Middle ground. | |

**User's choice:** Keep — with Phase 11 BulkActionBar pattern.

### Rules route depth (follow-up)

| Option | Description | Selected |
|--------|-------------|----------|
| Route extraction only (v1 chrome stays) | Move existing Rules JSX into the new route as-is. Smallest scope expansion. | |
| Full sunset rewrite (Recommended) | Rewrite Rules against sunset design system in P13. Adds ~1 plan to P13 but cleans v1 carryover. | ✓ |
| Light pass: tokens + states, keep layout | Recolor + add states, keep layout. Middle ground. | |

**User's choice:** Full sunset rewrite.

**Notes:** Phase 13 scope explicitly expands by one plan-worth for the Rules rewrite. Compensates for not deferring to P14.

---

## Comment input behavior

### Activity timeline comment input behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Local audit notes (Recommended) | Comment writes to GetVul only. Never posts to Jira/Asana. Simple: no OAuth scopes, no threading. | ✓ |
| Provider write-back via existing connectors | Comment POSTs to provider. Requires OAuth scope, threading, rate-limit handling. | |
| Hybrid: local default + 'Also post to provider' checkbox | Most flexible but most complex. | |

**User's choice:** Local audit notes.

### Storage shape

| Option | Description | Selected |
|--------|-------------|----------|
| New ticket_comments table (Recommended) | Dedicated table for comment content. First-class entities. | ✓ |
| Extend AuditLog with action='ticket.comment' | Reuse audit_log; comments in details JSONB. Conflates audit with user content. | |
| Both — ticket_comments for content, audit row for trail | Cleanest separation but doubles writes per comment. | |

**User's choice:** New ticket_comments table.

---

## Status pill interaction

### Interactive vs display-only

| Option | Description | Selected |
|--------|-------------|----------|
| Display-only — status mirrors provider sync (Recommended) | Pill reflects external_status from sync. Simplest, zero provider write surface. | |
| Interactive — user transitions status, write back to provider | Click pill → transition → POST. Significant backend surface. | |
| Mixed — GetVul-only 'Blocked' is interactive, others display-only | Open/In progress/Completed from sync; Blocked is GetVul-internal toggle. Lowest-friction analyst value-add. | ✓ |

**User's choice:** Mixed — GetVul-only 'Blocked' is interactive.

### Blocked toggle location

| Option | Description | Selected |
|--------|-------------|----------|
| Detail page only (Recommended) | Toggle in right rail Details card. Smallest surface. | |
| Detail page + bulk action on list | Same detail toggle plus BulkActionBar 'Mark blocked / Unblock'. Useful when a vendor patch slips. | ✓ |
| Inline pill click on list rows | Click status pill to cycle Blocked↔Open. Conflicts with display-only affordance. | |

**User's choice:** Detail page + bulk action on list.

### Blocked schema

| Option | Description | Selected |
|--------|-------------|----------|
| ticket.blocked: bool + ticket.blocked_reason: text (Recommended) | Two new columns + audit on toggle. blocked_reason validated like BL-01. | ✓ |
| ticket.blocked: bool only | No reason capture. Loses workflow context. | |
| Separate ticket_block_history table | Block events as first-class rows. Heavier schema. | |

**User's choice:** ticket.blocked + ticket.blocked_reason columns.

---

## Side-panel drill shape

### Drill content depth

| Option | Description | Selected |
|--------|-------------|----------|
| Standard (sketch A's shape) (Recommended) | Header + linked vulns mini-list (3) + description (truncated) + status + SLA + footer actions. | ✓ |
| Slim (minimal context) | Header + vulns mini-list + 'Open full detail' only. Worse triage velocity. | |
| Rich (overlap with detail page) | Standard + collapsed activity timeline + comment input. Blurs panel/detail boundary. | |

**User's choice:** Standard.

### Quick-actions placement

| Option | Description | Selected |
|--------|-------------|----------|
| Footer action bar (Recommended) | Sticky footer with 3 buttons. Matches Phase 11 DrillPanel convention. | ✓ |
| Header overflow menu (...) | Kebab menu in panel header. Hides actions behind extra click. | |
| Inline as primary + 2nd-row secondary | Primary at top of body, secondary inline below. Mixes content with chrome. | |

**User's choice:** Footer action bar.

---

## Extra Areas (user requested more)

### Provider scope for Phase 13

| Option | Description | Selected |
|--------|-------------|----------|
| Asana-only data, all 3 marks rendered when provider field is set (Recommended) | Backend keeps Asana-only writes. Frontend ready for Jira/GitHub. Honest about data, future-proof on visual. | |
| Hide Jira / GitHub entirely until connectors exist | Phase 13 only renders Asana coral mark. Deviates from UX-05-02 literal text. | |
| Build Jira + GitHub connector stubs in Phase 13 | Stub clients for Jira + GitHub (OAuth + create + read state). Significant scope expansion. | ✓ |

**User's choice:** Build Jira + GitHub connector stubs in Phase 13.

**Notes:** Significant backend scope expansion. Adds 2 new client modules (jira_client.py, github_client.py) implementing the asana_client.py interface — auth + ticket-create + read-back state. Full bidirectional sync deferred.

### SLA derivation

| Option | Description | Selected |
|--------|-------------|----------|
| Worst linked vuln's sla_due_at (Recommended) | Aggregate at request time. No new column. | |
| Ticket-create timestamp + fixed window per severity | Independent of vuln SLA. Risk of mismatched dates. | |
| Backend stores ticket.sla_due_at explicitly | New column + backfill + recompute hooks. Single source of truth. | ✓ |

**User's choice:** Backend stores ticket.sla_due_at explicitly.

**Notes:** Computation rule: `MIN(linked_vuln.sla_due_at)`. New alembic migration + service-layer hook to recompute on linked-vuln changes.

### Watcher source

| Option | Description | Selected |
|--------|-------------|----------|
| Asana 'followers' field + local GetVul subscriptions (Recommended) | Union of provider followers + new ticket_watchers join table. Works across providers. | ✓ |
| Provider-synced only, no local subscriptions | Just provider state. Simpler but no GetVul 'Watch' button. | |
| Defer watcher functionality entirely | Right rail shows assignee + reporter only in P13. Loses UX-05-05 sketch element. | |

**User's choice:** Asana 'followers' field + local GetVul subscriptions.

---

## Claude's Discretion

Areas the user delegated:
- Mobile breakpoint for two-column → stacked (use 900px per Phase 12)
- Activity timeline date grouping (group by day with "Today" / "Yesterday" / "MMM D")
- DrillPanel close behavior + URL state (standard `?ticket=...&open=drill`)
- Bulk-action confirmation modals
- Connector OAuth flow UX for Jira / GitHub stubs (admin-CLI/manual config in P13; UI in P14)

## Deferred Ideas

- Full kanban / Board view body — UX-D-01
- Comment write-back to provider — future phase
- Status interactive transitions to provider — future phase
- Asana config + setup + sync-status UI — Phase 14 connectors
- Edit / delete / markdown comments — v1 plain text only
- Mine vs All filter persistence across screens — sketch 006 open variable
- Connector OAuth UI for Jira + GitHub — Phase 14
- Bulk-comment — Phase 14 if analysts ask
- Watcher drag-to-reorder / prioritization — out of scope
- Search ticket comments (Cmd+K) — v2 if analysts ask
