---
phase: 23-ingestion-reliability-precursor
plan: 03
subsystem: api
tags: [ticketing, jira, github, asana, protocol, enum, httpx, mypy-baseline]

# Dependency graph
requires: []
provides:
  - "backend/app/ticketing/providers.py: TicketProvider str-Enum (ASANA/JIRA/GITHUB), the single source of truth for the provider identifier"
  - "backend/app/ticketing/dispatch.py: TicketingClient Protocol (create/get/comment/close) + AsanaAdapter/JiraAdapter/GitHubAdapter + build_ticketing_client factory"
  - "backend/app/ticketing/jira_client.py: canonical JiraClient now has comment()/transition()/close_issue() alongside create_ticket()/get_issue(), consolidating the two prior divergent Jira clients into one"
  - "backend/app/ticketing/github_client.py: GitHubClient now has add_comment()/close_issue() alongside create_ticket()/get_issue()/get_watchers()"
  - "frontend/src/lib/ticketing/providers.ts: TicketProvider TS union + PROVIDER_LABELS, consumed by use-create-ticket.ts"
affects: [23-04, 23-05, 23-08, phase-27-ticket-auto-drafting]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "typing.Protocol + thin per-provider adapter classes for verb normalization (first Protocol use in this codebase; BaseConnector elsewhere uses ABC)"
    - "Concrete client method names are never renamed — only wrapped by adapters — so existing call sites (daily_sync, future service-layer code) keep working unmodified"

key-files:
  created:
    - backend/app/ticketing/providers.py
    - backend/app/ticketing/dispatch.py
    - frontend/src/lib/ticketing/providers.ts
  modified:
    - backend/app/ticketing/models.py
    - backend/app/ticketing/jira_client.py
    - backend/app/ticketing/github_client.py
    - backend/app/ticketing/daily_sync.py
    - backend/tests/test_ticketing_clients.py
    - backend/mypy-baseline.txt
    - frontend/src/lib/mutations/use-create-ticket.ts

key-decisions:
  - "Jira's business-close method is named close_issue(issue_key), not close(issue_key) as the plan's literal text suggested — the canonical JiraClient already had a no-arg close() for HTTP-client cleanup; reusing that name would have silently overridden it and broken every existing caller of client.close() for cleanup. Mirrors the pattern the plan itself specifies for GitHub (close() = cleanup, close_issue() = business close)."
  - "Consolidated a second, unused, duplicate TicketProvider enum found in app/ticketing/models.py onto the new providers.py source (models.py now imports + re-exports it) so there is genuinely one enum, not two with identical members defined independently."
  - "dispatch.py's TicketingClient.get() return type tightened from bare dict to dict[str, Any] to satisfy the CI mypy-baseline gate (4 new violations caught before commit, fixed inline — not deferred)."
  - "test_ticketing_clients.py's Jira section was fully rewritten rather than patched: the old tests exercised the deleted v2 API client's create_issue/list_projects/base_url surface, which has no equivalent on the canonical v3 client. Asana tests were left untouched."

requirements-completed: [REL-04, REL-05]

duration: 46min
completed: 2026-07-27
---

# Phase 23 Plan 03: Ticketing Provider Contracts Summary

**One `TicketProvider` enum, one `TicketingClient` Protocol with three working adapters, a consolidated Jira client (create/get/comment/close), and a completed GitHub client — replacing scattered `if provider == "ASANA"` string checks and two divergent JiraClients with a single dispatch surface.**

## Performance

- **Duration:** 46 min
- **Started:** 2026-07-27T13:10:23+03:00
- **Completed:** 2026-07-27T13:56:42+03:00
- **Tasks:** 3 completed
- **Files modified:** 10 (3 created, 7 modified, 1 deleted)

## Accomplishments
- `TicketProvider` str-Enum (backend) + matching TS union (frontend) are now the single source of truth for ASANA/JIRA/GITHUB — a second, unused duplicate enum in `models.py` was found and consolidated onto it.
- `TicketingClient` Protocol + `AsanaAdapter`/`JiraAdapter`/`GitHubAdapter` + `build_ticketing_client()` factory normalize all three providers' divergent method names (`create_task` vs `create_ticket` vs `create_ticket`; `get_task` vs `get_issue` vs `get_issue`) onto one create/get/comment/close verb surface, with credential decryption explicitly kept out of the module.
- The two divergent JiraClients are now one: the canonical v3/ADF client gained `comment()` and `transition()` ported from the deleted v2 connectors client's `update_issue(comment=, status=)`, plus a `close_issue()` wrapper. The legacy `app/connectors/jira_client.py` is deleted and `daily_sync.py` is repointed — a repo-wide grep for the old import returns zero hits.
- `GitHubClient` gained `add_comment()` and `close_issue()`, mirroring the Asana auto-close template (`update_task(completed=True)` + `add_comment`). All three clients now satisfy `TicketingClient` through their adapters.

## Task Commits

Each task was committed atomically:

1. **Task 1: TicketProvider enum + TicketingClient Protocol + adapters + factory + TS union (D-23, D-06)** - `eccbae0` (feat)
2. **Task 2: Consolidate JiraClient (D-08)** - RED `1643f41` (test) → GREEN `cbce926` (feat)
3. **Task 3: Complete GitHubClient (D-12)** - GREEN `42e5316` (feat) — RED for this task was included in the same `1643f41` test commit (both Task 2 and Task 3's failing tests were authored together in one rewritten test file, since both tasks touch the same file)

_Note: Task 2 and 3 shared a single test file (`test_ticketing_clients.py`), so the RED phase for both was written and committed once (`1643f41`), then each task's GREEN implementation landed in its own commit._

## Files Created/Modified
- `backend/app/ticketing/providers.py` - `TicketProvider(str, Enum)`: ASANA/JIRA/GITHUB, single source of truth
- `backend/app/ticketing/dispatch.py` - `TicketingClient` Protocol + 3 adapters + `build_ticketing_client()` factory
- `backend/app/ticketing/models.py` - duplicate `TicketProvider` enum removed; now imports from `providers.py`
- `backend/app/ticketing/jira_client.py` - added `comment()`, `transition()`, `close_issue()` to the canonical v3/ADF client
- `backend/app/ticketing/github_client.py` - added `add_comment()`, `close_issue()`
- `backend/app/ticketing/daily_sync.py` - JIRA branch repointed to `app.ticketing.jira_client`; `_sync_jira_tickets` calls `comment()`/`transition()` instead of the old combined `update_issue()`
- `backend/app/connectors/jira_client.py` - deleted (v2 API duplicate, fully ported and superseded)
- `backend/tests/test_ticketing_clients.py` - rewritten: canonical-client Jira coverage (test_connection/get_issue-404/comment/transition/close_issue/import-smoke) + new GitHub add_comment/close_issue tests; Asana tests unchanged
- `backend/mypy-baseline.txt` - 8 stale entries for the deleted connectors client removed
- `frontend/src/lib/ticketing/providers.ts` - `TicketProvider` TS union + `PROVIDER_LABELS`
- `frontend/src/lib/mutations/use-create-ticket.ts` - `CreateTicketRequest.provider` now typed via the shared `TicketProvider`

## Decisions Made
- Named Jira's business-close method `close_issue`, not `close`, to avoid colliding with the pre-existing HTTP-cleanup `close()` — see key-decisions in frontmatter for full rationale.
- Consolidated the duplicate `TicketProvider` enum found (unused) in `models.py` onto the new `providers.py` source rather than leaving two independently-defined enums with identical members.
- Tightened `dispatch.py`'s `get()` Protocol/adapter return type to `dict[str, Any]` to keep the CI mypy-baseline gate green.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Renamed Jira's business-close method to `close_issue` instead of `close`**
- **Found during:** Task 2 (Consolidate JiraClient)
- **Issue:** The plan's literal text asked for `async def close(self, issue_key: str) -> None`, but the canonical `JiraClient` already defines `async def close(self) -> None` for httpx cleanup (used by every existing caller, e.g. `daily_sync.py`'s `await client.close()`). Defining a second `close` with a different signature would silently override the first in Python, breaking cleanup everywhere.
- **Fix:** Named the new method `close_issue(issue_key)`, matching the exact pattern the plan itself specifies for `GitHubClient` (`close()` = HTTP cleanup, `close_issue()` = business close). Updated `JiraAdapter.close` in `dispatch.py` to call `close_issue`.
- **Files modified:** `backend/app/ticketing/jira_client.py`, `backend/app/ticketing/dispatch.py`
- **Verification:** `test_jira_close_issue_transitions_to_done` passes; `client.close()` (cleanup) and `client.close_issue()` (business) coexist without collision.
- **Committed in:** `cbce926`

**2. [Rule 1 - Bug] Consolidated a duplicate, unused `TicketProvider` enum in `models.py`**
- **Found during:** Task 1 (TicketProvider enum)
- **Issue:** `backend/app/ticketing/models.py` already defined its own `class TicketProvider(str, enum.Enum)` with the same three members (unused anywhere else in the codebase) — leaving both would contradict the plan's explicit "one source of truth" must-have.
- **Fix:** Replaced the local definition in `models.py` with an import from the new `providers.py`, preserving `models.TicketProvider` as a working re-export for any future importer.
- **Files modified:** `backend/app/ticketing/models.py`
- **Verification:** `python -c "from app.ticketing.models import TicketProvider"` still resolves; no importers broke (grep confirmed nothing imported the old definition directly besides its own file).
- **Committed in:** `eccbae0`

**3. [Rule 1 - Bug] Fixed a bare-`dict` mypy-baseline-gate violation introduced by `dispatch.py`**
- **Found during:** Task 3 (final full-suite mypy check before commit)
- **Issue:** `mypy app/ | mypy-baseline filter` reported 4 NEW violations (not pre-existing/baselined) from `dispatch.py`'s `get(self, ref: str) -> dict | None` signatures (bare `dict` missing type args) across the Protocol + 3 adapters.
- **Fix:** Changed all four `-> dict | None` signatures to `-> dict[str, Any] | None`.
- **Files modified:** `backend/app/ticketing/dispatch.py`
- **Verification:** `mypy app/ | mypy-baseline filter` reports 0 new violations (only the intentional baseline-shrink from the deleted connectors file).
- **Committed in:** `42e5316`

**4. [Rule 3 - Blocking] Removed 8 stale `mypy-baseline.txt` entries for the deleted file**
- **Found during:** Task 2 (delete `app/connectors/jira_client.py`)
- **Issue:** `mypy-baseline.txt` carried 8 baseline entries scoped to `app/connectors/jira_client.py`, which no longer exists after the D-08 consolidation — leaving them would be silently-stale bookkeeping (not a hard failure, but drift the gate is meant to prevent).
- **Fix:** Manually removed only the 8 lines referencing that file (deliberately did NOT run a full `mypy-baseline sync`, which would have also touched unrelated pre-existing baseline drift outside this plan's scope — verified the targeted manual edit alone reports 0 new violations).
- **Files modified:** `backend/mypy-baseline.txt`
- **Verification:** `mypy app/ | mypy-baseline filter` clean.
- **Committed in:** `cbce926`

---

**Total deviations:** 4 auto-fixed (3 bug-class naming/typing fixes, 1 blocking-class stale-baseline cleanup)
**Impact on plan:** All four were necessary for correctness (no silent method-shadowing bug) and to keep the CI mypy gate green. No scope creep — no files outside the plan's declared `files_modified` list were touched except the two byproduct files (`models.py`'s duplicate enum, `mypy-baseline.txt`'s stale entries), both directly caused by this plan's own changes.

## Issues Encountered
- Existing `test_ticketing_clients.py` imported `app.connectors.jira_client` (the file this plan deletes) and tested its v2-specific surface (`create_issue`, `list_projects`, `.base_url` attribute) — none of which exists on the canonical v3 client. Resolved by rewriting the Jira section of that test file against the canonical client's actual surface while leaving the Asana tests untouched.
- No `.venv`/`node_modules` exist inside this parallel worktree; verification commands were run using the main checkout's `backend/.venv` Python (invoked with the worktree as `cwd`) and a local `node_modules` symlink into the main checkout's `frontend/node_modules` (gitignored, not committed).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Plans 04/05/08 (per the phase plan's dependency notes) can now import `TicketProvider`, `TicketingClient`, and `build_ticketing_client` from `app.ticketing.{providers,dispatch}` to wire the create-ticket service/router/rule-engine paths without re-deriving provider dispatch.
- `JiraClient.comment()`/`transition()`/`close_issue()` and `GitHubClient.add_comment()`/`close_issue()` are available for any future ticket-status-sync or auto-close work (e.g. extending `daily_sync.py`'s GitHub coverage, currently absent from daily sync — out of this plan's scope, tracked implicitly by REL-04/05 follow-on plans).
- No blockers identified for downstream plans in this phase wave.

---
*Phase: 23-ingestion-reliability-precursor*
*Completed: 2026-07-27*

## Self-Check: PASSED

All created/modified files confirmed present on disk (11/11), `backend/app/connectors/jira_client.py` confirmed deleted, and all 4 task commit hashes (`eccbae0`, `1643f41`, `cbce926`, `42e5316`) confirmed present in `git log --all`.
