# Phase 39 — Deferred Items

Out-of-scope discoveries logged during execution per the executor's SCOPE BOUNDARY rule
(pre-existing issues in unrelated files are not auto-fixed).

## 39-01 Task 2 — pre-existing mypy-baseline drift (not caused by this plan)

**Found during:** Task 2 verification (`mypy app/ | mypy-baseline filter`).

**Observation:** Running the CI-equivalent `mypy app/ | mypy-baseline filter` reports 9 "new"
violations, all in `backend/app/ticketing/daily_sync.py` (lines 49/131/135/140/145/150) plus a
`note:` line-count mismatch in `backend/app/auth/dependencies.py:10`. None of these files are
touched by any 39-01 change.

**Root cause:** `pyproject.toml`'s own comment on the `mypy-baseline` pin warns "the
mypy-baseline is line/version-sensitive — drift silently breaks the type gate." Verified by
`git stash`-ing all of 39-01's changes and re-running the identical command against the
pre-existing tree: the same 9 violations appear with zero 39-01 code present, proving this is
baseline/tool drift already present on this branch, not something this plan introduced.

**This plan's own contribution:** one genuinely new violation was introduced and fixed inline
(`app/exceptions/service.py::active_exception_subquery` was missing a return type annotation;
added `-> Exists` from `sqlalchemy`). After that fix, the "new" count is unchanged at 9 —
matching the pre-existing-drift baseline exactly — confirming 39-01 adds zero net-new mypy
violations.

**Action:** Not fixed here (out of scope — `daily_sync.py` is untouched by this plan). Whoever
next touches `app/ticketing/daily_sync.py` or regenerates `mypy-baseline.txt` should reconcile
this drift, or it can be regenerated directly via `mypy app/ | mypy-baseline sync`.

## 39-06 Task 2 — pre-existing `components/ui/button.tsx` icon-variant padding bug (not caused by this plan)

**Found during:** Task 2, while deciding how to render the Revoke column's disabled placeholder
button.

**Observation:** `buttonVariants` (cva) has `defaultVariants: { variant: 'secondary', size: 'md' }`.
Passing `variant="icon"` alone (the documented way to get the sitewide 34x34 icon-button
treatment) does NOT zero out the `size` slot — it silently falls back to `size: 'md'`, whose
`px-4 py-2` classes concatenate with `icon`'s fixed `h-[34px] w-[34px]`. Under Tailwind's
`box-sizing: border-box` preflight, that leaves ~0px of content area for the icon child (34px
box − 32px horizontal padding − 2px border), squeezing/clipping any icon inside. The only
existing call site (`src/app/dev/primitives/showcase.tsx:108`, a dev-only, non-production
showcase route) uses `variant="icon"` with no `size` override and appears to have never been
visually inspected against this.

**This plan's own contribution:** avoided the bug entirely by hand-rolling the Revoke
placeholder's 34x34 markup directly (matching `sketch-findings-getvul/references/visual-
language.md`'s `.icon-btn` spec) instead of using `<Button variant="icon">` — see
`frontend/src/components/exceptions/exceptions-table.tsx`'s Revoke `<td>`. No production code
path in this plan calls the buggy variant.

**Action:** Not fixed here (`components/ui/button.tsx` is outside this plan's `files_modified`,
and the one existing caller is a dev-only route with no visual-regression coverage to safely
verify a fix against). Whoever next reaches for `<Button variant="icon">` in production code —
e.g. Plan 07 wiring the real Revoke mutation — should either add a `compoundVariants` entry
zeroing `size`'s padding when `variant: 'icon'`, or keep hand-rolling the 34x34 markup as this
plan does.

## 39-03 Task 2 — pre-existing scheduler-tick/foreground-write deadlock hazard, amplified (not caused) by this plan

**Found during:** Task 2 full-backend-suite regression run (`pytest -q`, 1117 tests, ~152s).

**Observation:** Two full-suite runs with this plan's Task 2 changes present both surfaced
`FAILED tests/test_ticketing_dispatch.py::test_close_ticket_endpoint_dispatches_by_ticket_provider`
with a 500 response; a Task-1-only baseline run (this plan's `run_sla_tier_pass`/
`detect_and_escalate` changes stashed out) did not reproduce it in one run. The test passes
every time in isolation (`pytest tests/test_ticketing_dispatch.py::test_...` alone, and the
whole file alone) — it only manifests as part of the full 1117-test suite, in this exact
collection order.

**Root cause (confirmed via a one-off diagnostic re-run with `ASGITransport(...,
raise_app_exceptions=True)` temporarily set in `conftest.py::_make_authed_client`, then
reverted — no net diff to `conftest.py`):** a genuine Postgres `DeadlockDetectedError` on
`UPDATE vulnerabilities SET status=... WHERE id=...`, between the test's own
`close_ticket_endpoint` transaction and the app's live background scheduler loop
(`app/connectors/scheduler.py::_scheduler_loop`, started via the `client` fixture's real
FastAPI lifespan), which calls `run_sla_tier_pass`/`detect_and_escalate` for every
`is_active` tenant once per tick. By the time this test runs deep into the full suite, dozens
of prior tests' tenants still exist in the DB (per-test cleanup truncates but the background
loop is a long-lived task that keeps re-querying `is_active` tenants across the whole run), so
the scheduler tick's per-tenant `SELECT ... then loop-update-then-flush` transaction has a much
larger row-set and window than in any single test, raising the odds of a lock-order collision
with a concurrent foreground request's own `Vulnerability` row update.

**This plan's own contribution:** `run_sla_tier_pass`/`detect_and_escalate` each gained one
additional batched query per tick (the `~active_exception_subquery` WHERE clause's subquery,
plus the new `lapsed_exception_seconds` lookup) — both pure `SELECT`s (no row locks acquired by
either), but they run before the per-row update loop, marginally lengthening how long each
tick's transaction stays open before its `UPDATE`s fire. This widens (does not create) the
pre-existing collision window: `run_sla_tier_pass`'s "loop over every OPEN/IN_PROGRESS
vulnerability across a tenant and flush all writes at the end of one transaction" shape already
existed, unchanged, since Phase 36 (`36-01`) — before any exception/SLA-subtraction code existed
to add queries to it. No new `UPDATE`/lock-acquisition path was added by this plan; the flagged
statement (`UPDATE vulnerabilities SET status=...`) belongs to the ticket-close endpoint, not to
anything Task 2 touches.

**Why not fixed here:** a real fix (e.g. locking rows in a consistent `ORDER BY id`,
retry-on-`DeadlockDetectedError`, or shortening `run_sla_tier_pass`'s single-flush-per-tenant
transaction into smaller per-row commits) is a scheduler-wide transaction/concurrency-strategy
change — Rule 4 architectural territory, spanning `app/connectors/scheduler.py` and potentially
every other bulk-update loop it drives (`compute_risk_scores`, `run_all_due_rules`, etc.), none
of which are in this plan's `files_modified`. It is also non-fatal in both directions today:
the scheduler's own `try/except Exception` around the SLA-tick block (`scheduler.py:327-340`)
already logs-and-continues on any error including this one, and Postgres's deadlock victim
selection only aborts one of the two colliding transactions (the other proceeds normally) — so
this is a rare, transient, already-gracefully-degraded failure mode, not a silent data-
corruption risk. It is also environment-specific to the compressed, ordering-sensitive
1117-test full-suite run (a live scheduler racing hundreds of ad hoc tenants in ~2.5 minutes) —
not a shape a real single-tenant-per-VM production deployment approximates.

**Action:** Not fixed here. Confirmed via `pytest tests/test_exceptions_sla.py -x` (10/10),
`test_sla_tier_service.py`+`test_escalation_engine.py`+`test_exceptions*.py`+6 vulnerabilities
test files (all green), and the plan's own grep verification gates that this plan's actual
D-15/D-16 logic is correct. Whoever next hardens `app/connectors/scheduler.py`'s transaction
model (or adds a deadlock-retry decorator around scheduler-tick DB work) should treat this as
a concrete repro case.
