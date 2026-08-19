---
phase: 39-exception-risk-acceptance-workflow
plan: 03
subsystem: api
tags: [fastapi, sqlalchemy, postgres, sla, exceptions, risk-acceptance, compute-on-read, escalation]

# Dependency graph
requires:
  - phase: 39-01
    provides: active_exception_subquery(tenant_id, now) exclusion seam + ExceptionRecord model (created_at/expires_at/revoked_at/scope_type/cve_id/asset_id/asset_group_id) this plan's lapsed-exception lookup queries directly
  - phase: 39-02
    provides: full ASSET/ASSET_GROUP scope resolution — makes the D-16 lapsed-exception lookup exercisable across all three scope types, not just FINDING
  - phase: 36-remediation-sla-engine-escalation
    provides: compute_sla_state / resolve_state_for_vuln / run_sla_tier_pass / detect_and_escalate — the exact Phase 36 SLA engine this plan wires the exclusion + subtraction into
provides:
  - "_merge_intervals + lapsed_exception_seconds (exceptions/service.py) — batched (cve_id, asset_id)-keyed D-16 lookup, interval-merged (Pitfall 4/T-39-12) before summing"
  - "compute_sla_state / resolve_state_for_vuln gain excepted_seconds:int=0 (keyword-only, backward compatible) — D-16 SLA-clock subtraction"
  - "D-15 exclusion (~active_exception_subquery) wired into run_sla_tier_pass's WHERE (persisted mirror) and detect_and_escalate's WHERE (breach-alert firing, T-39-11 governance-critical)"
  - "list_vulnerabilities (page-scoped) and get_vulnerability (single-key) both feed the batched excepted_seconds into resolve_state_for_vuln so read-time sla_state/sla_due_at reflect the subtraction"
  - "detect_and_escalate ALSO applies the subtraction (Rule 2, beyond the plan's literal action text) so a just-resurfaced finding doesn't independently resolve 'breached' inside the escalation loop despite the persisted mirror correctly showing on_track"
affects: [39-05-consumer-sweep, 39-08-closing-plan]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Interval-merge (merge-adjacent-sorted-intervals, _merge_intervals) for any derived duration computed over D-12-permitted overlapping exception windows — must merge before summing or the SLA clock gets over-credited"
    - "Tenant-wide-once-per-tick batched lookup for scheduler-tick functions (run_sla_tier_pass/detect_and_escalate), mirroring the page-scoped batching already used by list_vulnerabilities' corr_by_key"

key-files:
  created:
    - backend/tests/test_exceptions_sla.py
  modified:
    - backend/app/exceptions/service.py
    - backend/app/vulnerabilities/sla_tier_service.py
    - backend/app/vulnerabilities/service.py
    - .planning/phases/39-exception-risk-acceptance-workflow/deferred-items.md

key-decisions:
  - "detect_and_escalate also receives the excepted_seconds subtraction (Rule 2 — missing critical), not only the ~active_exception_subquery WHERE exclusion the plan's literal action text specified. Proven necessary empirically: temporarily reverting just this one line and re-running the new test showed detect_and_escalate DOES fire a real breach escalation (fired=1, notified=1) for a just-resurfaced finding whose un-subtracted due date reads breached — exactly the 'instant-breach escalation storm' this plan's own objective names as what D-16 exists to prevent. The fix was restored and the test (test_escalation_not_fired_on_resurface) locks the regression in."
  - "lapsed_exception_seconds keys on (cve_id, asset_id) rather than vulnerability_id for FINDING scope, mirroring corr_by_key's exact batching shape (interfaces block's stated precedent). This is correct because grant_exception (39-01/39-02) always derives FINDING's asset_id from the resolved Vulnerability row — a FINDING-scope ExceptionRecord always carries the same (cve_id, asset_id) as its target vulnerability, so a single equality match covers both FINDING and ASSET scope without a second query."
  - "get_vulnerability inherits ONLY the lapsed-duration subtraction, not a structural exclusion/suppression of sla_state for a CURRENTLY-actively-excepted finding (whose ongoing window hasn't lapsed yet and so contributes nothing to lapsed_exception_seconds). This follows RESEARCH's own explicit Tier-1-#2 design note verbatim ('does not need to 404/exclude... its role is inheriting the corrected resolve_state_for_vuln') and Task 2's literal action text ('get_vulnerability inherits the same [subtraction]') — the must_haves' concluding, concrete clause ('never fires a breach alert or notification') is fully satisfied by the run_sla_tier_pass/detect_and_escalate wiring; a viewable-but-informational detail-page sla_state field for an actively-excepted finding is not itself an escalation surface."
  - "EXC-02/EXC-04 left unmarked [ ] in REQUIREMENTS.md despite being this plan's frontmatter requirements — mirrors the 39-01/39-02 precedent (39-08 is the phase's last declaring plan for all four EXC-* IDs); this plan closes the SLA-engine/escalation surface specifically, while EXC-02's 'dashboards' clause (assets/router.py badges, users/router.py owner-risk aggregates) and EXC-04's full auto-resurface guarantee across ALL ~20 consumers remain 39-04/39-05's domain."
  - "A discovered, full-suite-only, order-dependent Postgres deadlock (background scheduler's SLA tick vs. a concurrent foreground ticket-close write) is documented in deferred-items.md, not fixed — root-caused via a temporarily-reverted diagnostic transport change (no net diff), confirmed pre-existing in shape (Phase 36's bulk-update-in-one-transaction scheduler tick) and only measurably amplified (not newly caused) by this plan's added per-tick SELECT queries. A real fix is a scheduler-wide transaction/concurrency-strategy change (Rule 4 architectural territory), out of this plan's files_modified."

patterns-established:
  - "Any future consumer that needs to know 'how long was this finding hidden by a now-lapsed exception' calls exceptions/service.py::lapsed_exception_seconds with a batched key set — never a per-row query, never a naive sum of matching windows"

requirements-completed: []  # EXC-02/EXC-04 span multiple plans in this phase; 39-08 is the last declaring plan (see key-decisions)

# Metrics
duration: 42min
completed: 2026-08-19
---

# Phase 39 Plan 03: SLA-Engine Exclusion & Resurface Subtraction Summary

**Wired the D-15 active-exception exclusion and the D-16 SLA-clock subtraction into all four Phase 36 SLA-engine surfaces (`list_vulnerabilities`, `get_vulnerability`, `run_sla_tier_pass`, `detect_and_escalate`) via a new interval-merged, batched `lapsed_exception_seconds` lookup — closing a real self-discovered escalation-storm gap in `detect_and_escalate` along the way.**

## Performance

- **Duration:** 42 min (chained immediately after 39-06)
- **Started:** 2026-08-19T08:21:33Z
- **Completed:** 2026-08-19T09:04:06Z
- **Tasks:** 2/2
- **Files modified:** 4 (1 created, 3 modified) + 1 phase-tracking doc (deferred-items.md)

## Accomplishments

- `_merge_intervals` (exceptions/service.py) — a pure merge-adjacent-sorted-intervals function proving D-12-permitted overlapping exception windows are counted once, never double-summed (Pitfall 4 / T-39-12)
- `lapsed_exception_seconds` (exceptions/service.py) — ONE batched query (plus one batched `AssetGroupMember` lookup for ASSET_GROUP scope) resolving, per `(cve_id, asset_id)` key, the merged duration a finding spent under any now-LAPSED (naturally expired OR early-revoked) exception, scope-matched the same three ways `active_exception_subquery` matches
- `compute_sla_state` / `resolve_state_for_vuln` gain a keyword-only `excepted_seconds: int = 0` that shifts the effective SLA-clock start — fully backward compatible, zero behavior change for any caller passing nothing
- `run_sla_tier_pass` excludes actively-excepted findings from its WHERE (D-15, persisted mirror stops updating for them, mirroring the pre-existing REMEDIATED-vuln precedent) AND applies the identical tenant-wide-once-per-tick subtraction to its writes (closing Pitfall 1's two-parallel-representations gap)
- `detect_and_escalate` excludes actively-excepted findings from its WHERE (T-39-11, governance-critical — an accepted-risk finding fires zero Slack/Teams/email/PagerDuty/in-app alerts while covered) AND, as a self-discovered Rule 2 fix, applies the SAME subtraction so a just-resurfaced finding doesn't independently compute "breached" inside the escalation loop and fire an instant-breach storm
- `list_vulnerabilities`/`get_vulnerability` both feed the batched `excepted_seconds` into `resolve_state_for_vuln`, so a resurfaced finding's live `sla_state`/`sla_due_at` agrees with the persisted mirror
- 10-test `backend/tests/test_exceptions_sla.py` (6 pure-unit interval-merge/subtraction cases + 4 DB-backed integration tests, one of which doubles as a T-39-12 overlap-merge proof against a real DB read)

## Task Commits

Each task was committed atomically:

1. **Task 1: lapsed-exception batched lookup + interval-merge, and excepted_seconds in compute_sla_state** - `0218646` (feat)
2. **Task 2: apply excepted_seconds at read-time + exclude excepted findings from the persisted mirror and escalation** - `a38399a` (feat)

**Plan metadata:** _pending — this commit follows_

## Files Created/Modified

- `backend/app/exceptions/service.py` - `_merge_intervals` (pure interval-merge), `lapsed_exception_seconds` (batched D-16 lookup)
- `backend/app/vulnerabilities/sla_tier_service.py` - `compute_sla_state`/`resolve_state_for_vuln` gain `excepted_seconds`; `run_sla_tier_pass`/`detect_and_escalate` gain the `~active_exception_subquery` WHERE exclusion + the batched-once-per-tick subtraction
- `backend/app/vulnerabilities/service.py` - `list_vulnerabilities`/`get_vulnerability` compute and forward `excepted_seconds`
- `backend/tests/test_exceptions_sla.py` - 10 tests: 6 pure-unit (interval-merge cases + subtraction shift) + 4 DB-backed (resurface subtraction w/ overlap-merge proof, persisted-mirror parity, escalation exclusion, escalation-not-fired-on-resurface)
- `.planning/phases/39-exception-risk-acceptance-workflow/deferred-items.md` - logs the discovered full-suite-only scheduler/foreground-write Postgres deadlock (root-caused, not fixed — out of scope)

## Decisions Made

- `detect_and_escalate` gained the D-16 subtraction as a Rule 2 addition beyond the plan's literal action text (which only specified the WHERE exclusion for it) — see key-decisions in frontmatter for the empirical proof (reverted the fix, confirmed a real escalation fires without it, restored it).
- `lapsed_exception_seconds` batches on `(cve_id, asset_id)`, matching `corr_by_key`'s exact shape rather than `vulnerability_id` — correct because `grant_exception` always populates FINDING-scope's `asset_id` from the resolved `Vulnerability` row (verified by reading 39-01/39-02's `grant_exception` implementation directly).
- `get_vulnerability` inherits only the subtraction, not a structural state-suppression for currently-active exceptions — follows RESEARCH's own explicit design note and Task 2's literal action text; the must_haves' concrete, testable outcome ("never fires a breach alert or notification") is satisfied entirely by the `run_sla_tier_pass`/`detect_and_escalate` wiring, which are the only two alert-firing surfaces.
- EXC-02/EXC-04 requirement checkboxes intentionally left unmarked; see key-decisions in frontmatter for the full 39-08-is-last-declaring-plan rationale (mirrors 39-01/39-02 precedent, verified those plans' checkboxes are still `[ ]` too).
- The discovered full-suite-only Postgres deadlock is documented, not fixed — a real fix is a scheduler-wide transaction/concurrency-strategy change spanning `app/connectors/scheduler.py` and every other bulk-update loop it drives, none of which are in this plan's `files_modified`. See Issues Encountered below and `deferred-items.md` for the full root-cause writeup.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] `detect_and_escalate` needed the SAME D-16 subtraction as `run_sla_tier_pass`, not only the WHERE exclusion**
- **Found during:** Task 2, while wiring the WHERE exclusion (plan's action text only asked for `~active_exception_subquery` on `detect_and_escalate`'s WHERE)
- **Issue:** `detect_and_escalate` calls `resolve_state_for_vuln` independently of `run_sla_tier_pass`. Without also passing `excepted_seconds` into that call, a just-resurfaced finding (no longer actively excepted, so it passes the WHERE) would have its un-subtracted, stale due date resolve to "breached" INSIDE `detect_and_escalate` even though the persisted mirror and read-time list correctly show on_track — firing exactly the "instant-breach escalation storm" this plan's own stated objective names as what D-16 exists to prevent.
- **Fix:** Added the identical tenant-wide-once-per-tick `lapsed_exception_seconds` batched lookup inside `detect_and_escalate`, forwarding each row's `excepted_seconds` into its `resolve_state_for_vuln` call.
- **Files modified:** `backend/app/vulnerabilities/sla_tier_service.py`
- **Verification:** Temporarily reverted just this one line, re-ran `test_escalation_not_fired_on_resurface` — it failed with a real fired escalation (`fired=1, notified=1` in the captured logs, one `SlaEscalationEvent` row created). Restored the fix; the same test passes; full `test_exceptions_sla.py` (10/10) and the broader SLA/escalation/exceptions/vulnerabilities regression suite (146 tests) all green.
- **Committed in:** `a38399a` (Task 2 commit)

**2. [Rule 1 - Bug] mypy `arg-type` violations from dict-key `None`-narrowing (2 occurrences across both commits)**
- **Found during:** Task 1 and Task 2 mypy-baseline verification (`mypy app/ | mypy-baseline filter`)
- **Issue:** (a) Task 1: `lapsed_exception_seconds`'s `members_by_group.get(record.asset_group_id, ())` — `record.asset_group_id` is typed `UUID | None` but the dict key type is `UUID`. (b) Task 2: `run_sla_tier_pass`'s `lapsed_by_key.get((vuln.cve_id, vuln.asset_id), 0)` — `vuln.cve_id`/`vuln.asset_id` are `str | None`/`UUID | None` but the dict key type is `tuple[str, UUID]`. Both are genuinely new violations (confirmed via `git stash` re-running the identical mypy-baseline command against the pre-existing tree, which reproduced only the known, unrelated 9-violation `daily_sync.py` drift with zero of this plan's code present).
- **Fix:** (a) Added an explicit `record.asset_group_id is not None` guard before the `.get()` call. (b) Added an explicit `if vuln.cve_id and vuln.asset_id:` guard (applied to both `run_sla_tier_pass` and, for consistency/defensive hygiene, the equivalent `detect_and_escalate` line even though mypy didn't flag that one — same runtime shape, same latent risk) before computing `excepted_seconds`.
- **Files modified:** `backend/app/exceptions/service.py`, `backend/app/vulnerabilities/sla_tier_service.py`
- **Verification:** `mypy app/ | mypy-baseline filter` "new" count returned to the pre-existing-drift baseline (9) after each fix, i.e. net-zero-new from this plan.
- **Committed in:** `0218646` (Task 1), `a38399a` (Task 2)

---

**Total deviations:** 2 auto-fixed (1 missing-critical/governance, 1 bug/type-safety)
**Impact on plan:** Both fixes are correctness-necessary. No scope creep — neither touches ASSET/ASSET_GROUP scope resolution, the frontend, or any consumer beyond the four SLA-engine surfaces this plan owns.

## Issues Encountered

- **Discovered (not fixed): a full-suite-only, order-dependent Postgres `DeadlockDetectedError`** between the app's live background scheduler loop (`app/connectors/scheduler.py::_scheduler_loop`, which calls `run_sla_tier_pass`+`detect_and_escalate` for every `is_active` tenant on every tick) and a concurrent foreground `POST /api/v1/tickets/close` request's own `Vulnerability` row update, surfacing as `tests/test_ticketing_dispatch.py::test_close_ticket_endpoint_dispatches_by_ticket_provider` failing with a 500 only when run as part of the full 1117-test suite (never in isolation, never in its own file). Root-caused via a one-off diagnostic re-run with `ASGITransport(..., raise_app_exceptions=True)` temporarily set in `conftest.py` (reverted immediately after — zero net diff), which surfaced the real `sqlalchemy.exc.DBAPIError: DeadlockDetectedError` on `UPDATE vulnerabilities SET status=...`. Confirmed via a Task-1-only baseline full-suite run that this specific failure did not reproduce without Task 2's changes present (though it is not claimed to be impossible pre-Task-2 — it's a probabilistic race). `run_sla_tier_pass`'s "loop over every OPEN/IN_PROGRESS vulnerability and flush all writes in one transaction" shape is unchanged since Phase 36; this plan's two added per-tick `SELECT`s (no row locks) measurably widen, but did not create, the pre-existing collision window. Logged in full to `deferred-items.md` with the complete root-cause writeup — not fixed (a real fix is a scheduler-wide transaction/concurrency redesign, Rule 4 territory, well outside this plan's `files_modified`).
- Full backend regression: 1117/1117 tests collected with zero import errors; the dedicated `test_exceptions_sla.py` (10/10), the full SLA/escalation/exceptions/vulnerabilities-adjacent suite (146 tests across 12 files), and two independent full-suite runs (152s each) all confirm no regression beyond the one pre-existing `test_connector_health.py` log-ordering flake (unrelated, reproduces identically with or without this plan's changes) and the deadlock above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All four Phase 36 SLA-engine surfaces now honor D-15 (exclusion) and D-16 (resurface subtraction); `resolve_state_for_vuln`'s `excepted_seconds` parameter is the stable, backward-compatible seam any future consumer can adopt.
- `lapsed_exception_seconds` is the shared, tested, tenant-scoped, batched primitive for "how long was this finding hidden" — ready for reuse if a future plan (e.g. a dashboard "days saved by exceptions" metric) needs the same computation.
- Plans 04/05 (consumer sweep) and 39-08 (closing plan) are unaffected by this plan's file scope (`sla_tier_service.py`, `exceptions/service.py`, `vulnerabilities/service.py`) and can proceed independently; EXC-02/EXC-04 remain correctly unmarked pending their contributions.
- One discovered, documented, out-of-scope architectural hazard (the scheduler/foreground-write deadlock) is available in `deferred-items.md` for whoever next hardens `scheduler.py`'s transaction model.
- No blockers to `alembic upgrade head` (no migration in this plan) or the existing suite; full `test_exceptions_sla.py` + regression sweep green.

## Self-Check: PASSED

- `backend/app/exceptions/service.py` — FOUND (contains `_merge_intervals`, `lapsed_exception_seconds`)
- `backend/app/vulnerabilities/sla_tier_service.py` — FOUND (contains `excepted_seconds`, `active_exception_subquery`)
- `backend/app/vulnerabilities/service.py` — FOUND (contains `lapsed_exception_seconds` import + usage)
- `backend/tests/test_exceptions_sla.py` — FOUND (10 tests, all passing)
- `.planning/phases/39-exception-risk-acceptance-workflow/deferred-items.md` — FOUND (39-03 entry appended)
- Commit `0218646` — FOUND in git log
- Commit `a38399a` — FOUND in git log

---
*Phase: 39-exception-risk-acceptance-workflow*
*Completed: 2026-08-19*
