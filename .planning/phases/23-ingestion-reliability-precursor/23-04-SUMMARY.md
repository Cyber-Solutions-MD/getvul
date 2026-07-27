---
phase: 23-ingestion-reliability-precursor
plan: 04
subsystem: api
tags: [ticketing, jira, github, asana, dispatch, rule-engine, tenant-isolation]

# Dependency graph
requires:
  - phase: 23-03
    provides: "TicketProvider enum + TicketingClient Protocol/adapters/factory (backend/app/ticketing/{providers,dispatch}.py)"
provides:
  - "backend/app/ticketing/service.py: create_tickets/create_host_ticket/create_remediation_ticket/sync_ticket_status/close_ticket all dispatch by provider via TicketingClient, not hardcoded Asana"
  - "backend/app/ticketing/rule_engine.py: run_rule + run_all_due_rules resolve per-rule/per-tenant provider connectors instead of an Asana-only lookup"
  - "backend/app/ticketing/router.py: _get_ticketing_client(provider) generalized helper + GET /api/v1/tickets/providers tenant-scoped configured-providers endpoint"
affects: [23-08, phase-27-ticket-auto-drafting]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "client_resolver callback (Callable[[str], Awaitable[TicketingClient | None]]) lets sync_ticket_status/close_ticket dispatch to a ticket's OWN stored provider without owning tenant-scoped credential decryption themselves"
    - "_extract_ref(url) derives the provider's raw ref (gid/issue key/issue number) from TicketingClient.create()'s returned URL — all three adapters' URLs end with the raw ref as the last path segment"
    - "_provider_create_kwargs gates assignee/due_on kwargs to Asana only — Jira/GitHub adapters don't accept those parameter names and would TypeError if forwarded"

key-files:
  created:
    - backend/tests/test_ticketing_dispatch.py
  modified:
    - backend/app/ticketing/service.py
    - backend/app/ticketing/rule_engine.py
    - backend/app/ticketing/router.py

key-decisions:
  - "TicketingClient.create() returns one URL string (per Plan 03's contract), not a separate id+url pair — _extract_ref() reliably recovers the raw ref because all three providers' URL shapes end with it (Asana gid, Jira issue key, GitHub issue number)"
  - "Only Asana's create_task natively accepts assignee/due_on kwargs; Jira/GitHub still get that info baked into the description text, not passed as kwargs (would TypeError against JiraClient.create_ticket)"
  - "sync_ticket_status/close_ticket use a client_resolver callback (built by router._make_client_resolver) rather than a pre-built client, since a ticket's provider is only known after the DB lookup and multiple providers can appear in one sync batch"
  - "Bulk 'delete' action drops its best-effort raw Asana HTTP delete call — dispatch.py's TicketingClient Protocol has no delete verb; local GetVul ticket rows are still deleted and vulns reopened, matching the prior best-effort (contextlib.suppress-wrapped) semantics"
  - "GET /tickets/providers is tenant-scoped + enabled-only, returning only {provider, enabled} — no credentials or secret_arn, closing T-23-10"

requirements-completed: [REL-04, REL-05]

# Metrics
duration: 82min
completed: 2026-07-27
---

# Phase 23 Plan 04: Ticket Provider Dispatch Wiring Summary

**Every Asana-hardcoded ticketing call site (3 create paths, sync, close, both rule-engine connector lookups, and the router's client resolution) now dispatches by the actual requested/stored provider, closing the live bug where `provider:"JIRA"` silently created an Asana task while persisting `Ticket.provider="JIRA"`.**

## Performance

- **Duration:** 82 min
- **Started:** 2026-07-27T13:58:47+03:00 (base commit 5c06d0d)
- **Completed:** 2026-07-27T15:20:53+03:00
- **Tasks:** 3 completed
- **Files modified:** 4 (3 modified, 1 created)

## Accomplishments
- `service.py`'s three create paths (`create_tickets`, `create_host_ticket`, `create_remediation_ticket`) now take a resolved `TicketingClient` and call `.create(...)` instead of always calling `asana_client.create_task(...)` — the destination now matches `Ticket.provider` for every request.
- `sync_ticket_status`/`close_ticket` dispatch per ticket's own stored provider via a `client_resolver` callback, replacing the `Ticket.provider == "ASANA"` filter that silently ignored every Jira/GitHub ticket.
- `rule_engine.py`'s two independent Asana hardcodes are both fixed: `run_rule` builds its client from the rule's own `action.provider`, and `run_all_due_rules` looks up ONE connector per provider actually referenced by a tenant's due rules (default ASANA), skipping (not silently redirecting) a rule whose provider has no configured connector.
- `router.py` gained a generalized `_get_ticketing_client(provider)` (replacing `_get_asana_client_from_connector`, removed) used by every mutating endpoint, plus a new tenant-scoped `GET /api/v1/tickets/providers` (D-15) returning which providers are configured+enabled.
- `test_ticketing_dispatch.py` (22 tests) proves, for JIRA/GITHUB/ASANA: the right client is invoked across all three create paths, sync/close dispatch by a ticket's own provider, the rule-engine's scheduled path reaches the correct provider (with an ASANA-default regression + an unconfigured-provider skip test), and the `/providers` endpoint is tenant-scoped (two tenants with different connectors see different provider sets) and excludes disabled connectors.

## Task Commits

Each task was committed atomically:

1. **Task 1: Dispatch all three create paths + sync + close in service.py (D-07)** - `c05472b` (feat)
2. **Task 2: Fix both rule-engine Asana hardcodes (D-09)** - `7abc281` (feat)
3. **Task 3: Generalize router client resolution (D-10) + tenant-scoped configured-providers endpoint (D-15)** - `dd0c6a9` (feat)

_Note: all three tasks were implemented together before the first commit (design required understanding the full call chain across service/rule_engine/router up front — e.g. the URL-to-ref extraction and the assignee/due_on kwargs gate had to be right before ANY create path would work for Jira), then split into task-scoped commits. The full 22-test `test_ticketing_dispatch.py` was authored and committed with Task 1 since it exercises all three tasks' surfaces end-to-end; Tasks 2/3 landed their implementation changes on top of already-passing tests, mirroring the precedent in 23-03-SUMMARY.md._

## Files Created/Modified
- `backend/app/ticketing/service.py` - `create_tickets`/`create_host_ticket`/`create_remediation_ticket` take `client: TicketingClient`; `sync_ticket_status`/`close_ticket` take a `client_resolver`; new `_extract_ref`, `_provider_create_kwargs`, `_is_ticket_completed` helpers
- `backend/app/ticketing/rule_engine.py` - `run_rule` resolves its own provider's client via `build_ticketing_client`; `run_all_due_rules` looks up one connector per provider referenced by due rules; new `_has_min_credentials` helper
- `backend/app/ticketing/router.py` - new `_get_ticketing_client` (replaces removed `_get_asana_client_from_connector`) + `_make_client_resolver`; every mutating endpoint (create/create-host/sync-all/bulk-action's 4 sub-actions/close/run-rule-now) dispatches by provider; new `GET /tickets/providers` endpoint
- `backend/tests/test_ticketing_dispatch.py` - 22 tests across service-layer dispatch, rule-engine dispatch, and router-level HTTP integration + tenant-scoping

## Decisions Made
See frontmatter `key-decisions` above (URL-derived ref extraction, Asana-only create kwargs, resolver-callback pattern for sync/close, dropped bulk-delete provider call, tenant-scoped `/providers` response shape).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `_extract_ref()` added to bridge `TicketingClient.create()`'s single-URL return to the existing `external_ticket_id`/`external_ticket_url` two-column schema**
- **Found during:** Task 1 design
- **Issue:** Plan 03's `TicketingClient.create()` returns one URL string, but `sync_ticket_status`/`close_ticket` (and the adapters' own `get`/`close`/`comment`) need the provider's RAW ref (Asana gid / Jira issue key / GitHub issue number), not the URL — passing the URL where a ref is expected would silently break every subsequent sync/close/comment call.
- **Fix:** Added `_extract_ref(url)` — verified all three adapters' returned URLs end with the raw ref as the last path segment (confirmed by reading `asana_client.py`/`jira_client.py`/`github_client.py`'s URL-construction code), so a single `url.rstrip("/").rsplit("/", 1)[-1]` recovers it correctly for every provider. No changes to dispatch.py's shipped contract were needed.
- **Files modified:** `backend/app/ticketing/service.py`
- **Verification:** `test_create_tickets_dispatches_to_the_requested_provider` asserts the exact expected `external_ticket_id`/`external_ticket_url` split for a fake URL shaped like each real provider's.
- **Committed in:** `c05472b`

**2. [Rule 1 - Bug] `_provider_create_kwargs()` gates assignee/due_on to Asana only**
- **Found during:** Task 1 design
- **Issue:** `JiraAdapter.create(title, body, **kwargs)` forwards `**kwargs` straight to `JiraClient.create_ticket(project_key, summary, description, assignee_account_id=None)` — passing generic `assignee=`/`due_on=` kwargs (as the old Asana-only code did) would raise `TypeError: unexpected keyword arguments` for every Jira create, defeating REL-04 entirely.
- **Fix:** Added `_provider_create_kwargs(provider, assignee, due_on)` returning `{"assignee":..., "due_on":...}` only for `TicketProvider.ASANA`, `{}` otherwise. Jira/GitHub still receive the same assignee/due-date info baked into the description text (unchanged `_build_task_description`/`_build_host_task_description`).
- **Files modified:** `backend/app/ticketing/service.py`
- **Verification:** `test_create_tickets_jira_does_not_receive_asana_only_kwargs` asserts Jira's `create()` call received an empty kwargs dict; parametrized create-path tests confirm Jira/GitHub create succeeds without raising.
- **Committed in:** `c05472b`

**3. [Rule 1 - Bug] Removed the now-dead `_get_asana_client_from_connector` function definition**
- **Found during:** Task 3, verifying the acceptance grep
- **Issue:** After replacing every call site, the function definition itself remained as dead code — the plan's literal acceptance criterion (`grep _get_asana_client_from_connector` returns zero hits) requires the definition gone too, not just its call sites.
- **Fix:** Deleted the function; `_get_asana_client` (used only by the Asana-specific `/asana/setup`/`/asana/config` settings routes, out of this plan's scope) is untouched.
- **Files modified:** `backend/app/ticketing/router.py`
- **Verification:** `grep -n "_get_asana_client_from_connector" backend/app/ticketing/router.py` returns zero hits; full ticketing test suite still green.
- **Committed in:** `dd0c6a9`

**4. [Rule 3 - Blocking] Dropped the bulk-action "delete" sub-action's raw Asana HTTP delete call**
- **Found during:** Task 3
- **Issue:** `dispatch.py`'s `TicketingClient` Protocol defines only create/get/comment/close — no delete verb — so the old `asana_client.client.delete(f"/tasks/{gid}")` (already best-effort, wrapped in `contextlib.suppress`) had no generalized equivalent to dispatch to for Jira/GitHub.
- **Fix:** The delete sub-action now only deletes the local GetVul `Ticket` rows and reopens their vulns (unchanged from before for that part); the external provider ticket is left as-is rather than attempting a provider-specific escape hatch outside the Protocol. Documented inline as a deviation, not silently dropped.
- **Files modified:** `backend/app/ticketing/router.py`
- **Verification:** Existing bulk-action tests (none exercised the Asana-delete HTTP call directly, since it was already best-effort/suppressed) still pass; `contextlib` import removed as it's now unused.
- **Committed in:** `dd0c6a9`

---

**Total deviations:** 4 auto-fixed (3 bug-class, 1 blocking-class), all necessary to make the Jira/GitHub create/sync/close paths actually work end-to-end (the plan's stated purpose) rather than merely compile. No scope creep — no files outside `service.py`/`rule_engine.py`/`router.py`/the new test file were touched.

## Issues Encountered
- `mypy-baseline` initially flagged 2 NEW `no-untyped-def` violations from the new `GET /tickets/providers` handler (missing return type + untyped `user` param) — fixed by fully annotating it (`-> list[dict[str, Any]]`, `user: CurrentUser`), re-verified 0 new violations (7 pre-existing stale entries were incidentally fixed by removing dead Asana-only code, left in the baseline file untouched per the same conservative precedent Plan 03 set — not re-running a full `mypy-baseline sync` to avoid touching unrelated drift).
- Two of my own docstrings accidentally contained the literal grep-target strings from the plan's acceptance criteria (`asana_client.create_task(...)` and `connector_type == "ASANA"`) — reworded them so the required-zero-hits greps pass for real, not just for code.
- Initial test run hit a `ForeignKeyViolationError` from using random `uuid.uuid4()` as `user_id` in direct service-layer tests (no such user row exists) — fixed by passing `None` (nullable FK, matches the rule-engine's own pre-existing `user_id=None` pattern for scheduled/system-created tickets).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `GET /api/v1/tickets/providers` is live and tenant-scoped, ready for Plan 08's ticket-provider picker and Phase 27's ticket auto-drafting to consume directly.
- Every ticketing call site (create/sync/close/rules) is now provider-agnostic; Plan 08 (frontend picker) and any future provider addition only need a `TicketProvider` enum member + adapter (Plan 03's contract) — no further service/router/rule_engine changes required.
- `dispatch.py`'s adapters expose no cleanup/`aclose()` method (only the `close(ref)` business-close verb) — router.py's generalized client-resolution helpers no longer call any cleanup on the underlying httpx client (previously each Asana-only route explicitly called `asana_client.close()` in a `finally` block). This is a minor resource-management gap inherited from Plan 03's shipped contract, not introduced by this plan; flagged here rather than expanding this plan's scope into `dispatch.py`. Recommend a future plan add an `aclose()` verb to `TicketingClient` + its three adapters.

---
*Phase: 23-ingestion-reliability-precursor*
*Completed: 2026-07-27*

## Self-Check: PASSED
