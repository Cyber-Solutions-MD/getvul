---
phase: 23-ingestion-reliability-precursor
plan: 05
subsystem: ticketing
tags: [github, connectors, daily-sync, ticketing, fastapi, httpx]

# Dependency graph
requires:
  - phase: 23-03
    provides: "JiraClient/GitHubClient consolidation + GitHub add_comment/close_issue methods, TicketingClient dispatch protocol (dispatch.py)"
  - phase: 23-04
    provides: "Provider dispatch generalization (build_ticketing_client, TicketProvider enum, service.py sync_ticket_status genericized across ASANA/JIRA/GITHUB)"
provides:
  - "GITHUB registered as a creatable connector type in all four backend registration points (schemas.py, connectors/router.py, tester.py, sync.py)"
  - "daily_sync.py GitHub branch: inbound state map (get_issue -> completed/REMEDIATED) + outbound auto-close (close_issue + add_comment) parity with Asana/Jira"
affects: [24-ai-foundation, connectors, tickets]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "GitHub connector credential split: token -> encrypted credentials, owner/repo -> plaintext config (matches dispatch.py/rule_engine.py's established contract from Plan 03/04)"
    - "test_github(credentials, config) reads token from credentials and owner/repo from config, mirroring dispatch.py's build_ticketing_client exactly"
    - "_sync_github_tickets mirrors _sync_jira_tickets structure 1:1: cache get_issue payloads by issue number, first pass maps state->completed, second pass groups open tickets and applies auto-close via the shared _build_status_comment helper"

key-files:
  created:
    - backend/tests/test_github_sync.py
  modified:
    - backend/app/connectors/schemas.py
    - backend/app/connectors/router.py
    - backend/app/connectors/tester.py
    - backend/app/connectors/sync.py
    - backend/app/ticketing/daily_sync.py

key-decisions:
  - "GitHub's CONNECTOR_TYPES fields (token/owner/repo) all render through the existing add-connector wizard's single credentials-only submission path; owner/repo's plaintext-config destination is realized by the pre-existing dispatch.py/rule_engine.py contract from Plan 03/04, not a new frontend split — no frontend changes were needed or made per plan scope"
  - "sync.py's ASANA/JIRA no-data-sync short-circuit message generalized to a _TICKETING_DISPLAY_NAMES lookup so GITHUB gets its own correctly-cased 'GitHub is a ticketing connector...' message instead of a naive .title() transform"
  - "daily_sync's GitHub branch instantiates GitHubClient directly (token from decrypted credentials, owner/repo from connector.config) rather than going through dispatch.py's adapter — matches the existing ASANA/JIRA branches' own direct-client-construction style in this file"

requirements-completed: [REL-05]

# Metrics
duration: 35min
completed: 2026-07-27
---

# Phase 23 Plan 05: GitHub Ticketing End-to-End Summary

**GITHUB registered as a creatable ticketing connector across all four backend registration points, plus a daily_sync GitHub branch (inbound get_issue state map + outbound close_issue/add_comment auto-close) mirroring the existing Asana/Jira pattern.**

## Performance

- **Duration:** 35 min
- **Started:** 2026-07-27T16:14:00Z
- **Completed:** 2026-07-27T16:49:00Z
- **Tasks:** 2 completed
- **Files modified:** 5 (1 created)

## Accomplishments
- GITHUB is now a fully creatable connector type: `CONNECTOR_TYPES["GITHUB"]` (token as password/credential field, owner/repo as text/config fields), `CONNECTOR_CATEGORIES["GITHUB"] = "ticketing"`, a `test_github` dispatch entry in `TESTERS`, and `"GITHUB"` in `sync.py`'s `SPECIAL_CONNECTORS` + no-data-sync short-circuit
- `daily_sync.py` gained a full GitHub sync branch: `_sync_github_tickets` reads each open GitHub ticket's remote issue state via `get_issue`, maps `state=="closed"` to GetVul `ticket.external_status="closed"` + linked vuln `REMEDIATED`, and — when all linked vulns for an issue are resolved — auto-closes via `close_issue` + posts a summary via `add_comment`, exactly mirroring the Asana/Jira auto-close parity pattern
- `GitHubClient` (previously referenced nowhere outside its own file per 23-RESEARCH Open Question 5) is now consumed from `tester.py`, `daily_sync.py`, `dispatch.py`, and `service.py` — no longer an orphaned stub
- 8 new tests in `backend/tests/test_github_sync.py`: 5 registration assertions (Task 1) + 3 MockTransport-backed daily_sync behavior tests (Task 2, inbound-close / outbound-auto-close / no-get_watchers-call)

## Task Commits

Each task was committed atomically:

1. **Task 1: Register GITHUB connector type across all four backend points (D-13, D-11)** - `3047b99` (feat)
2. **Task 2: GitHub daily_sync branch — inbound state map + outbound auto-close (D-12)** - `4c3c474` (feat)

_Note: both tasks were TDD-flagged in the plan; tests were authored alongside each task's implementation and verified green before commit (RED/GREEN folded into a single commit per task, consistent with this file's existing single-commit-per-branch history)._

## Files Created/Modified
- `backend/app/connectors/schemas.py` - Added `GITHUB` `ConnectorTypeInfo` (token/owner/repo fields, token marked password/credential)
- `backend/app/connectors/router.py` - Added `"GITHUB": "ticketing"` to `CONNECTOR_CATEGORIES`
- `backend/app/connectors/tester.py` - Added `test_github()` (constructs `GitHubClient(token, owner, repo)`, calls `test_connection()`) + `TESTERS["GITHUB"]` entry
- `backend/app/connectors/sync.py` - Added `"GITHUB"` to `SPECIAL_CONNECTORS`; generalized the ASANA/JIRA no-data-sync short-circuit to include GITHUB with a per-provider display-name message
- `backend/app/ticketing/daily_sync.py` - Added a `GITHUB` branch in `run_daily_ticket_sync` (constructs `GitHubClient` from decrypted credentials + connector config) and a new `_sync_github_tickets()` helper mirroring `_sync_jira_tickets()`
- `backend/tests/test_github_sync.py` (new) - Registration assertions (Task 1) + MockTransport-backed daily_sync behavior tests (Task 2)

## Decisions Made
- Followed the established token(credentials)/owner+repo(config) split already proven in `dispatch.py`/`rule_engine.py`/`test_ticketing_dispatch.py`'s `_seed_connector` fixture from Plan 03/04, rather than inventing a new split — kept `test_github` and the daily_sync branch consistent with that existing contract
- Generalized `sync.py`'s no-data-sync short-circuit message via a small `_TICKETING_DISPLAY_NAMES` dict (rather than `.title()`, which would incorrectly render "GITHUB".title() as "Github" not "GitHub")
- `daily_sync.py`'s GitHub branch constructs `GitHubClient` directly (not via `dispatch.py`'s `GitHubAdapter`) to match the file's own existing ASANA/JIRA direct-construction style — consistent internal convention over cross-module reuse for this particular file

## Deviations from Plan

None — plan executed exactly as written. Both tasks' `<action>` and `<verify>` blocks were followed as specified; the `<read_first>` guidance (dispatch.py's `build_ticketing_client`, service.py's `_is_ticket_completed`/auto-close block, existing ASANA/JIRA branches in daily_sync.py) matched what was found in the codebase with no surprises requiring an out-of-plan fix.

## Issues Encountered
- **Worktree stale-base hazard (environment, not code):** this worktree's branch was initially based on a pre-Phase-23 commit (`adc0571`) instead of the expected `a74593d`. Working tree was clean with no unique commits, so it was reset to `a74593d` per the documented recovery procedure before any work began. No project code was affected.
- **Backend venv not present in this worktree:** `backend/.venv` (gitignored) only existed in the main checkout, not this worktree. Ran the worktree's tests using the main checkout's venv interpreter (`/Users/.../getvul/backend/.venv/bin/python`) with `cwd` set to the worktree's `backend/` directory — this correctly resolves the worktree's own `app`/`tests` packages via `sys.path`/rootdir, while reusing already-installed dependencies. No test or source files were affected.

## User Setup Required

None - no external service configuration required. (An operator wanting a live GitHub connector still needs to generate a PAT with `repo` scope per the connector's `notes` field and configure `owner`/`repo` — this is existing operator-facing UX, unchanged by this plan.)

## Next Phase Readiness
- REL-05 (GitHub ticketing create + sync) is now fully wired end-to-end: creatable via the four registration points, create-path dispatch already generalized in Plan 04, and status-sync/auto-close added here.
- Phase 23's remaining plans (per the wave/dependency graph) can proceed; no blockers introduced by this plan.
- Known pre-existing gap (out of scope for this plan, not introduced by it): the add-connector wizard's frontend submission path sends all connector fields (including GitHub's `owner`/`repo`) into the `credentials` dict rather than splitting `owner`/`repo` into `config` at creation time — meaning a GitHub connector created purely through today's wizard would need its `config.owner`/`config.repo` set via a follow-up edit/config-update path (the same pattern Asana's `workspace_gid`/`project_gid` already requires, per its own `notes` field). This is a frontend/wizard-contract gap, not a backend registration gap, and was out of this plan's file scope (schemas.py/router.py/tester.py/sync.py/daily_sync.py only).

## Self-Check: PASSED

All files created/modified verified present; both task commits (`3047b99`, `4c3c474`) verified present in git log.

---
*Phase: 23-ingestion-reliability-precursor*
*Completed: 2026-07-27*
