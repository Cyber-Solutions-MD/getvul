---
status: complete
phase: 13-tickets-list-detail
source: [13-VERIFICATION.md]
started: 2026-06-02T00:00:00Z
updated: 2026-06-02T12:30:00Z
---

## Current Test

[testing complete — both items skipped by user; backend behavior API-pre-verified on the UAT fixture]

## Tests

### 1. Assignee resolution with real connector data
expected: When the backend resolves assignee as a Person object (email match in users table, or a synthesized display-only object when no match), the People card on /tickets/[id] renders the correct displayName and Avatar. Confirm with an actual Jira/Asana-synced ticket (not test fixtures).
result: skipped
note: Backend resolution pre-verified via API on UAT fixture (UAT-101 → real "Demo Admin"; UAT-102 → synthesized display-only). User skipped the browser walkthrough.

### 2. SLA / severity / status chip filter semantic correctness
expected: On /tickets, selecting the "Critical" severity chip narrows the list to tickets with max_severity=CRITICAL; "In progress" status chip returns only in-progress tickets; "Overdue" SLA chip returns only tickets past sla_due_at. No silent no-ops. (WR-01 added server-side filtering but no dedicated automated test exercises it against real data.)
result: skipped
note: API pre-verified on UAT fixture — severity=CRITICAL→3, status=completed→2, sla=overdue→3 all correct. KNOWN GAP: status=open and status=in_progress return the identical 6 (backend maps both to resolved_at IS NULL); the In-progress chip does not narrow to in-progress-only. User skipped the browser walkthrough.

## Summary

total: 2
passed: 0
issues: 0
pending: 0
skipped: 2
blocked: 0

## Gaps
