---
phase: 13
slug: tickets-list-detail
status: ready
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-01
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (backend) + vitest/jest (frontend — confirm in Wave 0) |
| **Config file** | `backend/pyproject.toml` / frontend test config (planner to confirm) |
| **Quick run command** | `cd backend && pytest tests/ticketing -q` |
| **Full suite command** | `cd backend && pytest -q` + `cd frontend && npm test` |
| **Estimated runtime** | ~60–120 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick run command for the affected subsystem
- **After every plan wave:** Run full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 13-01-T1 | 13-01 | 1 | UX-05-03,04,05 | T-13-01,02,03 | migrations 026/027/028 round-trip; FKs to tickets/users/vulns | integration (alembic) | `cd backend && alembic upgrade head && alembic downgrade -3 && alembic upgrade head` | ❌ W0 | ⬜ pending |
| 13-01-T2 | 13-01 | 1 | UX-05-04,05 | T-13-01,02,03 | TicketComment/TicketWatcher ORM + CommentCreate/BlockedUpdate validators (min/max length) | unit (import) | `cd backend && python -c "from app.ticketing import models, schemas; assert hasattr(models,'TicketComment') and hasattr(models,'TicketWatcher') and hasattr(schemas,'BlockedUpdate') and hasattr(schemas,'CommentCreate')"` | ❌ W0 | ⬜ pending |
| 13-01-T3 | 13-01 | 1 | UX-05-03,04,05 | T-13-01,02,03 | backfill round-trip; sla_due_at = MIN(linked vuln) | integration | `cd backend && pytest tests/test_ticket_migrations.py -x -q` | ❌ W0 | ⬜ pending |
| 13-02-T1 | 13-02 | 1 | UX-05-02 | T-13-04,05 | JiraClient interface parity; bearer auth; no token logging | unit (import) | `cd backend && python -c "from app.ticketing.jira_client import JiraClient, JiraIssue"` | ❌ W0 | ⬜ pending |
| 13-02-T2 | 13-02 | 1 | UX-05-02 | T-13-06,07 | GitHubClient Issues API parity; no token logging | unit (import) | `cd backend && python -c "from app.ticketing.github_client import GitHubClient, GitHubIssue"` | ❌ W0 | ⬜ pending |
| 13-02-T3 | 13-02 | 1 | UX-05-02 | T-13-04..07 | mocked-httpx stubs; create + read-state behavior | unit | `cd backend && pytest tests/test_provider_stubs.py -x -q` | ❌ W0 | ⬜ pending |
| 13-03-T1 | 13-03 | 2 | UX-05-01,03,04,05 | T-13-08..13 | list_tickets surfaces blocked/sla(group MIN)/external_status; recompute on all create paths | unit | `cd backend && pytest tests/test_list_tickets_reshape.py -x -q` | ❌ W0 | ⬜ pending |
| 13-03-T2 | 13-03 | 2 | UX-05-04,05 | T-13-08,09,10,11,12 | comment/blocked routes: uuid path, tenant-scope 404, audit-then-commit, group-scoped blocked, validator bounds | integration | `cd backend && pytest tests/test_ticket_comments.py tests/test_ticket_blocked.py -x -q` | ❌ W0 | ⬜ pending |
| 13-03-T3 | 13-03 | 2 | UX-05-04,05 | T-13-08,10,12,13 | idempotent watch; detail endpoint (assignee+reporter+role-tagged watchers); bulk block/unblock | integration | `cd backend && pytest tests/test_ticket_watch.py -x -q` | ❌ W0 | ⬜ pending |
| 13-04-T1 | 13-04 | 1 | UX-05-01,02 | T-13-14,15 | queryKeys.tickets defined once; ProviderMark CSS-var gradient, no inline hex, no logo asset | unit (RTL) | `cd frontend && npx vitest run src/lib/queries/keys.test.ts src/components/tickets/provider-mark.test.tsx` | ❌ W0 | ⬜ pending |
| 13-04-T2 | 13-04 | 1 | UX-05-03 | T-13-14,15 | StatusPill 4 states + leading dot; Blocked renders alongside provider status | unit (RTL) | `cd frontend && npx vitest run src/components/tickets/status-pill.test.tsx` | ❌ W0 | ⬜ pending |
| 13-04-T3 | 13-04 | 1 | UX-05-03,06 | T-13-14,15 | SlaPill client-side tier; VulnCount T·C·H edge cases (0→'—', >99→'99+') | unit (RTL) | `cd frontend && npx vitest run src/components/tickets/sla-pill.test.tsx src/components/tickets/vuln-count.test.tsx` | ❌ W0 | ⬜ pending |
| 13-05-T1 | 13-05 | 2 | UX-05-01 | T-13-16,17,18 | DrillPanel slot generalization back-compat; existing vuln-drill tests stay green (REGRESSION) | unit (RTL) | `cd frontend && npx vitest run src/components/vulnerabilities/drill-panel.test.tsx src/components/vulnerabilities/drill-panel-mobile.test.tsx` | ❌ W0 | ⬜ pending |
| 13-05-T2 | 13-05 | 2 | UX-05-01 | T-13-16,17,18 | TicketDrillContent body (top-3 vulns, status+SLA, footer actions) | unit (RTL) | `cd frontend && npx vitest run src/components/tickets/ticket-drill-content.test.tsx` | ❌ W0 | ⬜ pending |
| 13-06-T1 | 13-06 | 2 | UX-05-04,05 | T-13-19,20,21 | WatcherStack +N overflow popover; TicketAssetCard cross-link; peer-voice microcopy | unit (RTL) | `cd frontend && npx vitest run src/components/tickets/watcher-stack.test.tsx src/components/tickets/ticket-asset-card.test.tsx` | ❌ W0 | ⬜ pending |
| 13-06-T2 | 13-06 | 2 | UX-05-04 | T-13-19,20,21 | ActivityTimeline day-grouped chronological; CommentInput 1..10000 validation | unit (RTL) | `cd frontend && npx vitest run src/components/tickets/activity-timeline.test.tsx src/components/tickets/comment-input.test.tsx` | ❌ W0 | ⬜ pending |
| 13-06-T3 | 13-06 | 2 | UX-05-04 | T-13-19,20,21 | BlockedToggle inline reason editor (reassign-combobox shape) | unit (RTL) | `cd frontend && npx vitest run src/components/tickets/blocked-toggle.test.tsx` | ❌ W0 | ⬜ pending |
| 13-07-T1 | 13-07 | 3 | UX-05-01,02,03,06 | T-13-23 | useTickets allow-list clamp; useMarkBlocked optimistic + rollback + predicate invalidation, sends only {blocked,blocked_reason} | unit (RTL) | `cd frontend && npx vitest run src/lib/queries/use-tickets.test.ts` | ❌ W0 | ⬜ pending |
| 13-07-T2 | 13-07 | 3 | UX-05-01,06 | T-13-22 | 8-column table renders all headers + each Plan-04 primitive cell; chip-bar allowList (T-12-05) | unit (RTL) | `cd frontend && npx vitest run src/components/tickets/tickets-table.test.tsx` | ❌ W0 | ⬜ pending |
| 13-07-T3 | 13-07 | 3 | UX-05-01,02,03 | T-13-22,24,25 | mutually-exclusive states; full err.message (WR-10); Board placeholder; connector deep-link empty state | unit (RTL) | `cd frontend && npx vitest run "src/app/(authed)/dashboard/tickets/page.test.tsx"` | ❌ W0 | ⬜ pending |
| 13-08-T1 | 13-08 | 3 | UX-05-04 | T-13-26 | useTicketDetail/useAddComment send only {body}; optimistic append + rollback | unit (RTL) | `cd frontend && npx vitest run src/lib/queries/use-ticket-detail.test.ts src/lib/queries/use-ticket-comments.test.tsx` | ❌ W0 | ⬜ pending |
| 13-08-T2 | 13-08 | 3 | UX-05-05 | T-13-30 | useTicketWatch optimistic toggle, snapshot + rollback toast (Pitfall 6) | unit (RTL) | `cd frontend && npx vitest run src/lib/queries/use-ticket-watch.test.tsx` | ❌ W0 | ⬜ pending |
| 13-08-T3 | 13-08 | 3 | UX-05-04, UX-05-05 | T-13-27,28,29 | two-column detail; escaped description/comments (no innerHTML); mutually-exclusive states; full err.message | unit (RTL) | `cd frontend && npx vitest run "src/app/(authed)/dashboard/tickets/[id]/page.test.tsx"` | ❌ W0 | ⬜ pending |
| 13-09-T1 | 13-09 | 2 | UX-05-01 | T-13-32 | useTicketRules read-only list; TicketRule fields verbatim | unit (RTL) | `cd frontend && npx vitest run src/lib/queries/use-ticket-rules.test.ts` | ❌ W0 | ⬜ pending |
| 13-09-T2 | 13-09 | 2 | UX-05-01 | T-13-31,33,34 | rules sunset rewrite; ChipBar allowList; mutually-exclusive states; sidebar → /tickets/rules, no ?tab=rules | unit (RTL) | `cd frontend && npx vitest run "src/app/(authed)/dashboard/tickets/rules/page.test.tsx"` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky. "File Exists ❌ W0" = the test file is created by its own (tdd) task during execution — the test seam is co-located with the code, not a pre-existing fixture.*

---

## Wave 0 Requirements

Each tdd task creates its own co-located test file as the first step of execution (the test seam ships with the code, not as a separate Wave-0 batch). The infrastructure these depend on already exists and is confirmed by RESEARCH.md (no new framework install):

- [x] Backend pytest infrastructure exists (`backend/tests/` — confirmed by RESEARCH; new test files: test_ticket_migrations / test_provider_stubs / test_list_tickets_reshape / test_ticket_comments / test_ticket_blocked / test_ticket_watch)
- [x] Frontend vitest + RTL infrastructure exists (confirmed by RESEARCH; Phase 11/12 component + hook tests are the template)
- [x] Alembic migration round-trip seam (upgrade/downgrade for 026/027/028) covered by 13-01-T1/T3
- [ ] Regression gate: existing vuln drill-panel tests must stay green after the 13-05 slot generalization (`src/components/vulnerabilities/drill-panel*.test.tsx`) — verified during 13-05 execution

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Provider gradient marks render correct tint | UX-05-02 | Visual | Open `/tickets`, confirm Jira blue / Asana coral / GitHub violet marks |
| Two-column detail layout + sticky 340px rail | UX-05-04 | Visual/responsive | Open `/tickets/[id]`, verify rail stickiness + 900px stack breakpoint |
| Status/SLA pill colors match locked contract | UX-05-03 | Visual | Verify pill color families distinct from severity |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (all 25 tasks across 9 plans mapped above)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (every task carries an `<automated>` command)
- [x] Wave 0 covers all MISSING references (existing pytest + vitest infra; co-located tdd test files; regression gate noted)
- [x] No watch-mode flags (all commands use `vitest run` / `pytest -x -q` — no `--watch`)
- [x] Feedback latency < 120s (per-task commands are single-file scoped)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-01 (map completed across all 9 plans during plan-phase revision)
