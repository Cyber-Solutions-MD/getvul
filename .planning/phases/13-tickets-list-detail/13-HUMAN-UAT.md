---
status: partial
phase: 13-tickets-list-detail
source: [13-VERIFICATION.md]
started: 2026-06-02T00:00:00Z
updated: 2026-06-02T00:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Assignee resolution with real connector data
expected: When the backend resolves assignee as a Person object (email match in users table, or a synthesized display-only object when no match), the People card on /tickets/[id] renders the correct displayName and Avatar. Confirm with an actual Jira/Asana-synced ticket (not test fixtures).
result: [pending]

### 2. SLA / severity / status chip filter semantic correctness
expected: On /tickets, selecting the "Critical" severity chip narrows the list to tickets with max_severity=CRITICAL; "In progress" status chip returns only in-progress tickets; "Overdue" SLA chip returns only tickets past sla_due_at. No silent no-ops. (WR-01 added server-side filtering but no dedicated automated test exercises it against real data.)
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
