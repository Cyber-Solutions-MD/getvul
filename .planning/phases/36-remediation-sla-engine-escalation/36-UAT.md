---
status: complete
phase: 36-remediation-sla-engine-escalation
source: [36-01-SUMMARY.md, 36-02-SUMMARY.md, 36-03-SUMMARY.md, 36-04-SUMMARY.md, 36-05-SUMMARY.md, 36-06-SUMMARY.md]
started: 2026-08-18T12:25:18Z
updated: 2026-08-18T12:27:30Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Fresh boot with migrations 046 + 047 applied; scheduler SLA tick (run_sla_tier_pass + detect_and_escalate) runs without error; a primary query returns live data.
result: pass

### 2. SLA state visible on Vulnerabilities list + detail (D6, 36-01)
expected: The Vulnerabilities table SLA column renders a server-truth SlaPill (on_track / approaching / breached / "No SLA") in place of the old local slaBand formatter — right-aligned, readable contrast, on both the desktop table row and the mobile card. The detail view carries sla_state + sla_due_at.
result: pass

### 3. SLA & Escalation admin pane renders, gated, with mandated copy (36-06)
expected: As admin/owner, /settings shows a "SLA & Escalation" entry (hidden for non-admins). It renders three sunset-theme cards (SLA policy, Escalation channels, Escalation floor) — no zinc-gray/raw hex, Inter + JetBrains Mono only, and the SaveBar "Save changes" is the only gradient element. Loading/empty/error states render. The D-13 PagerDuty manual-resolution copy and D-15 Teams Workflows setup copy are both present.
result: pass

### 4. Configure & persist an escalation channel (36-05 + 36-06)
expected: Enter a webhook URL / PagerDuty routing key, set the tier floor ("Escalate at" Critical only / High and critical / All tracked) and per-transition Approaching/Breach routing, then Save. Settings persist; secrets read back masked (••••••••); a masked-write save keeps the existing secret rather than clearing it.
result: pass

### 5. Live escalation delivery to a real channel (36-02 + 36-06 step 3)
expected: With a real Slack / Teams Workflow / PagerDuty webhook mapped to the approaching transition in a scratch tenant, forcing an approaching/breach transition delivers a correctly-formatted message to that channel (fires exactly once per channel/transition).
result: pass

### 6. Drill-panel SLA pill + escalation-history list (36-06 step 4)
expected: Open a finding's drill panel. The SlaPill matches the list row. An escalation-history list shows fired events (from GET /vulnerabilities/{id}/escalations); a failed delivery renders as an amber-tinted, audit-only row with NO retry button, and the transition record stays visible.
result: pass

### 7. Concurrent-double-tick hardening — inspection-level proof accepted (D8, 36-03)
expected: The uq_escalation_once IntegrityError savepoint-catch (W4 concurrent-double-tick hardening) is defense-in-depth for a future multi-replica scheduler. Today's single-process/sequential scheduler produces no genuine concurrent tick, so it is proven by code inspection + a direct structural mirror of seed.py's begin_nested/except/continue idiom, NOT by a live race test. Confirm you accept inspection-level proof for this branch (or flag if you want a race harness built).
result: pass

<!-- Auto-passed via coverage: deterministically covered by passing tests; not presented (see 36-COVERAGE.md / SUMMARY coverage blocks) -->

### 8. [36-01 D1] Risk-tier SLA engine core (tier_for_score, severity_to_tier, get_tier_policy, compute_sla_state)
expected: SLA-01 — tier/elapsed-% state formula with D-12 floor, D-03 severity fallback, custom-or-default policy merge.
result: pass
source: automated
coverage_id: 36-01-D1

### 9. [36-01 D2] resolve_state_for_vuln + run_sla_tier_pass scheduler write path
expected: SLA-01 — per-finding resolution + sla_due_at / sla_breached mirror write (D-08); ignores remediated vulns.
result: pass
source: automated
coverage_id: 36-01-D2

### 10. [36-01 D3] scheduler SLA tick swapped to run_sla_tier_pass
expected: SLA-01 — run_sla_tier_pass in, check_sla_breaches out; same isolation shape, no new scheduler.
result: pass
source: automated
coverage_id: 36-01-D3

### 11. [36-01 D4] List + detail responses carry sla_state + sla_due_at
expected: SLA-02 — GET /vulnerabilities and /{id} both include sla_state + sla_due_at, read-time resolved.
result: pass
source: automated
coverage_id: 36-01-D4

### 12. [36-01 D5] SlaPill server-truth `state` prop
expected: SLA-02 — optional state prop skips computeTier(), maps to 4-tone vocabulary; contradictory dueAt ignored.
result: pass
source: automated
coverage_id: 36-01-D5

### 13. [36-01 D7] Ticket SlaPill call sites untouched (additive prop)
expected: tickets-table / kanban-card / ticket-drill-content unchanged; 19 pre-existing tests still pass.
result: pass
source: automated
coverage_id: 36-01-D7

### 14. [36-03 D1] Exactly-once escalation firing across double invocation
expected: SLA-03 — re-running the tick twice = no duplicate event row / dispatch / notification.
result: pass
source: automated
coverage_id: 36-03-D1

### 15. [36-03 D2] Tier-floor gating produces zero escalations but tracked state
expected: SLA-03 — below-floor finding: 0 escalation rows, still a valid tracked breached state.
result: pass
source: automated
coverage_id: 36-03-D2

### 16. [36-03 D3] Per-transition-type routing is exclusive
expected: SLA-03 — approaching channels never fire for breach and vice versa.
result: pass
source: automated
coverage_id: 36-03-D3

### 17. [36-03 D4] Every fire writes exactly one fail-closed audit row
expected: SLA-03 — success and failure both audit once with channel/from/to/tier/delivery_status.
result: pass
source: automated
coverage_id: 36-03-D4

### 18. [36-03 D5] D-08 reconciliation: legacy _check_sla_breaches retired
expected: SLA-03 — one breach = one sla_escalation notification, no legacy double-fire.
result: pass
source: automated
coverage_id: 36-03-D5

### 19. [36-03 D6] GET /vulnerabilities/{id}/escalations tenant-scoped (IDOR-safe)
expected: SLA-03 — history ordered by fired_at; cross-tenant request 404s.
result: pass
source: automated
coverage_id: 36-03-D6

### 20. [36-03 D7] detect_and_escalate wired into scheduler tick
expected: SLA-03 — runs right after run_sla_tier_pass, same isolation shape, no new scheduler.
result: pass
source: automated
coverage_id: 36-03-D7

### 21. [36-04 D1] remediation_events row written on every REMEDIATED transition
expected: SLA-04 — frozen tier_at_remediation + duration_seconds + timestamps (D-09).
result: pass
source: automated
coverage_id: 36-04-D1

### 22. [36-04 D2] All 7 REMEDIATED write sites route through mark_vulnerability_remediated()
expected: SLA-04 — no bare status=REMEDIATED assignment remains (Pitfall 6).
result: pass
source: automated
coverage_id: 36-04-D2

### 23. [36-04 D3] NULL-score severity fallback + below-floor not_tracked
expected: SLA-04 — deterministic tier freeze; below-floor records 'not_tracked' rather than dropping the row.
result: pass
source: automated
coverage_id: 36-04-D3

### 24. [36-04 D4] get_mttr_by_tier grouped + tenant-scoped
expected: SLA-04 — avg duration + count by tier_at_remediation, no cross-tenant leakage.
result: pass
source: automated
coverage_id: 36-04-D4

### 25. [36-04 D5] GET /vulnerabilities/mttr/by-tier admin-gated + tenant-scoped
expected: SLA-04 — 403 below ADMIN; tenant-scoped aggregate.
result: pass
source: automated
coverage_id: 36-04-D5

### 26. [36-04 D6] Migration 047 chains off 046 and is reversible
expected: SLA-04 — upgrade/downgrade/upgrade round-trip verified against real dev Postgres.
result: pass
source: automated
coverage_id: 36-04-D6

### 27. [36-04 D7] Pre-existing flat MTTR queries untouched (additive)
expected: SLA-04 — dashboard.py / trends.py not in the diff (Pitfall 11).
result: pass
source: automated
coverage_id: 36-04-D7

### 28. [36-05 D1] GET/PATCH tenant settings sla_config full policy persistence
expected: SLA-01 — tier days/approaching%/floor/routing; mask-on-read; Fernet-at-rest; keep-on-masked-write; GET=admin/PATCH=owner; fail-closed audit (16 HTTP tests).
result: pass
source: automated
coverage_id: 36-05-D1

### 29. [36-05 D2] Escalation channel config storable server-side with validation
expected: SLA-03 — Slack/Teams/PagerDuty/email config; https-only + floor + tier-day + approaching_pct validation; secret encrypted at rest.
result: pass
source: automated
coverage_id: 36-05-D2

## Summary

total: 29
passed: 29
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none yet]
