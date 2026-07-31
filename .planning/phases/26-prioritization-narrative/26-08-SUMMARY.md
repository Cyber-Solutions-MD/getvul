---
phase: 26-prioritization-narrative
plan: 08
subsystem: ai
tags: [fastapi, sqlalchemy, anthropic, message-batches-api, asyncio, scheduler, redis, byok]

# Dependency graph
requires:
  - phase: 26-07
    provides: "run_batch_prewarm() + batch.py's own-session/per-tenant-client shape + get_redis_client() -- the nightly submitter this plan's poller/scheduler wiring completes"
  - phase: 26-06
    provides: "AiBatchJob durable registry (backend/app/ai/models.py) -- the table poll_pending_batches() resumes from"
provides:
  - "poll_pending_batches() (backend/app/ai/batch.py) -- resume-from-Postgres retrieval + per-tenant BYOK client per job + result routing (succeeded/errored/canceled/expired) + row completion"
  - "_dispatch_ai_batch_prewarm()/_dispatch_ai_batch_poll() (backend/app/connectors/scheduler.py) -- the two asyncio.create_task-dispatched blocks (nightly 24h-gated submit + every-tick poll) that make the batch feature genuinely live, plus the _last_ai_batch_prewarm module global"
affects: [28-eval-cost-observability-gate]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Scheduler per-tick blocks extracted as their own top-level async functions (_dispatch_ai_batch_prewarm/_dispatch_ai_batch_poll) rather than inlined directly in _scheduler_loop()'s body -- the first time this file's per-tick blocks are refactored into directly-unit-testable units, needed because _scheduler_loop()'s own infinite while-loop cannot be awaited to completion in a test; _scheduler_loop() itself now just awaits both in sequence each tick."
    - "Per-job re-select-by-scalar-id inside the per-job try (not looping over the initially-loaded ORM objects) -- the SAME AsyncSession.rollback()-expires-the-whole-identity-map defense 26-07 established for run_batch_prewarm()'s tenant loop, now applied to poll_pending_batches()'s job loop."
    - "Duck-typed poll-side test fakes (_FakeRetrieveResponse/_FakeSucceededResult/_FakeNonSucceededResult/_FakeResultLine/_FakeResultsStream in test_ai_batch.py) rather than real anthropic SDK Pydantic instances or isinstance-based match/case narrowing -- poll_pending_batches() matches on line.result.type (a plain string) and reads .message/.error via ordinary attribute access, so a duck-typed fake is indistinguishable from the real SDK response shape to the code under test."

key-files:
  created:
    - backend/tests/test_scheduler_ai_batch.py
  modified:
    - backend/app/ai/batch.py
    - backend/app/connectors/scheduler.py
    - backend/tests/test_ai_batch.py

key-decisions:
  - "poll_pending_batches() re-selects each AiBatchJob by scalar id inside the per-job try (not the initially-loaded ORM object) -- mirrors 26-07's Tenant.id-not-Tenant fix; a rollback() in one job's except block would otherwise expire a LATER job's already-loaded ORM attributes and raise sqlalchemy.exc.MissingGreenlet on next access."
  - "The errored/canceled/expired audit branches use literal per-case status strings (batch_errored/batch_canceled/batch_expired via match/case), not the plan's literal status=f\"batch_{line.result.type}\" f-string -- the plan's own grep-based acceptance criteria checks for the three literal substrings in the source file, which an f-string's interpolation would never produce."
  - "_audit_non_succeeded_batch_result() uses the module's existing _ZERO_USAGE sentinel, not the plan's literal usage=None -- the exact Rule 1 bug 26-07-SUMMARY.md already fixed for run_batch_prewarm()'s budget-skip audit call (audit_log_ai_call() unconditionally reads usage.input_tokens/output_tokens with no null-guard), explicitly flagged by that summary as relevant to this plan's poller."
  - "The two scheduler dispatch blocks were extracted into their own top-level _dispatch_ai_batch_prewarm()/_dispatch_ai_batch_poll() functions rather than inlined directly in _scheduler_loop()'s body -- required to satisfy the plan's own read_first-cited test convention (direct await on a named function, mirroring test_connector_health.py), since _scheduler_loop()'s infinite while-loop cannot be awaited to completion in a test."

patterns-established:
  - "T-24-19's per-tenant-fresh-client contract now spans BOTH sides of the batch lifecycle: run_batch_prewarm() (26-07) on submit, poll_pending_batches() (this plan) on retrieval -- neither ever holds a shared/injected client, each resolving its OWNING tenant's key fresh per iteration."
  - "D-05's asyncio.create_task hard constraint is now uniformly enforced across every scheduler-dispatched AI batch operation (submit AND poll), not just the literally-named submission path -- closing the exact gap RESEARCH's Pitfall 3 warned about."

requirements-completed: [AIP-02]

# Metrics
duration: 22min
completed: 2026-07-31
---

# Phase 26 Plan 08: Scheduler Integration -- Batch Goes Live Summary

**The batch feature goes live end-to-end: `poll_pending_batches()` resumes every in-progress `AiBatchJob` from Postgres with a fresh per-tenant BYOK client per job, and the connector scheduler now dispatches both the nightly 24h-gated submit and the every-tick poll via `asyncio.create_task` -- the scheduler itself builds zero Anthropic clients.**

## Performance

- **Duration:** 22 min
- **Started:** 2026-07-31T15:02:36Z
- **Completed:** 2026-07-31T15:24:11Z
- **Tasks:** 2/2 completed
- **Files modified:** 4 (1 new, 3 modified)

## Accomplishments

- `backend/app/ai/batch.py`: new `poll_pending_batches(*, anthropic_client_factory=None)` -- selects EVERY `AiBatchJob` with `status == "in_progress"` directly from Postgres on each call (resume-from-Postgres, T-26-08); per job resolves that job's OWNING tenant's key fresh and builds a FRESH per-tenant client before `retrieve()`/`results()` (T-24-19) -- a key rotated away skips the job, left `in_progress`, never retrieved with another tenant's key. Gates `results()` strictly behind `processing_status == "ended"` (Pitfall 6). `succeeded` results route through Plan 07's `validate_and_cache_batch_result()` (same cache key the GET route computes -- D-06); `errored`/`canceled`/`expired` get their own distinct `batch_errored`/`batch_canceled`/`batch_expired` audit at cost 0.0, never cached. Closes the row (`status="completed"`, `ended_at`) after the results loop. Per-job try/except containment (one job's failure never aborts the tick's other in-flight jobs), with a scalar-id re-select per iteration to stay immune to a prior job's `rollback()`.
- `backend/app/connectors/scheduler.py`: two new top-level dispatcher functions -- `_dispatch_ai_batch_prewarm()` (24h-gated, mirrors the file's OWN `_last_ticket_sync` timing idiom, `asyncio.create_task`-dispatched, never inline) and `_dispatch_ai_batch_poll()` (every tick, no gate, ALSO `asyncio.create_task`-dispatched -- RESEARCH Pitfall 3's explicit warning that the poll side needs the SAME non-blocking treatment as submission). New `_last_ai_batch_prewarm: datetime | None` module global alongside the existing three. Both wired into `_scheduler_loop()`'s per-tick body after the existing alert-checks block. Neither dispatcher builds an `AsyncAnthropic` client or passes one to the batch functions -- each batch function resolves its own per-tenant key(s) internally; a dispatch-time exception in either block is caught, logged, and never crashes the loop.
- `backend/tests/test_ai_batch.py` (extended, +6 tests): per-tenant-key poll isolation (two tenants, two distinct keys, each job retrieved via its OWN client), key-rotated-away skip (client never constructed), still-processing no-op (`results()` never called -- Pitfall 6), succeeded caches under the SAME cache key the GET route computes + audits `ok` + completes the row, the three errored/canceled/expired branches (distinct audit, cost 0.0, never cached), and resume-from-a-directly-seeded row (simulating a pre-restart submit, proving no in-memory registry links submit and poll -- only the `AiBatchJob` row). New duck-typed poll-side fakes (`_FakeRetrieveResponse`, `_FakeSucceededResult`, `_FakeNonSucceededResult`, `_FakeResultLine`, `_FakeResultsStream`) and a `_make_poll_recording_factory()` extending the established `anthropic_client_factory` seam convention.
- `backend/tests/test_scheduler_ai_batch.py` (new, 7 tests) -- the FIRST direct tests of `scheduler.py`'s own dispatch functions: non-blocking dispatch (control returns before a slow fake's `asyncio.sleep` completes -- the Pitfall 3 regression guard, for BOTH blocks), the 24h gate + its re-dispatch-after-24h counterpart, the poll block's no-gate-every-call behavior, dispatch-exception containment for both blocks, no-client-passed, and a static source-inspection guard that the module never imports `AsyncAnthropic` or inline-awaits either batch function.
- Full `test_ai_*.py test_scheduler_ai_batch.py` wave-merge regression: 237/237 green. `test_connector_health.py` (the other file touching `scheduler.py`) unaffected, 9/9 green. `ruff check` + `ruff format --check` clean on every touched/created file. `mypy app/ai/batch.py`/`app/connectors/scheduler.py` in isolation: zero errors attributable to either file (verified via `mypy app/ | grep '^app/ai/batch.py\|^app/connectors/scheduler.py'` returning empty).

## Task Commits

Each task was committed atomically:

1. **Task 1: poll_pending_batches() -- resume-from-Postgres retrieval + per-tenant BYOK client + result routing** - `6192e94` (feat)
2. **Task 2: scheduler dispatch -- nightly submit + every-tick poll, both asyncio.create_task, no client arg** - `5b725a6` (feat)

**Plan metadata:** (this commit) - `docs(26-08): complete plan`

## Files Created/Modified

- `backend/app/ai/batch.py` - new `poll_pending_batches()` + `_audit_non_succeeded_batch_result()` helper; module docstring updated (three Critical properties; the batch feature is now genuinely wired into the scheduler)
- `backend/app/connectors/scheduler.py` - new `_last_ai_batch_prewarm` global + `_dispatch_ai_batch_prewarm()`/`_dispatch_ai_batch_poll()` functions, wired into `_scheduler_loop()`'s per-tick body
- `backend/tests/test_ai_batch.py` - 6 new poll tests + poll-side duck-typed fakes + `_seed_batch_job()`/`_make_poll_recording_factory()` helpers
- `backend/tests/test_scheduler_ai_batch.py` (new) - 7 tests covering non-blocking dispatch, 24h gating (both directions), no-gate poll, exception containment, and no-client dispatch
- `.planning/phases/26-prioritization-narrative/deferred-items.md` - logged the mypy-baseline note-line-drift artifact's 4th recurrence this phase (unrelated to this plan's diff) and re-confirmed the pre-existing untracked `scratchpad/` dir flagged by 26-07 is still present

## Decisions Made

- **`poll_pending_batches()` re-selects each job by scalar id, not the initially-loaded ORM object** -- see Deviations below; this is a correctness fix (prevents a real, reproducible `MissingGreenlet` crash), not a style preference.
- **Literal per-case audit status strings via `match`/`case`, not an f-string** -- see Deviations below; required for the plan's own grep-based acceptance criteria to actually pass.
- **`_ZERO_USAGE` sentinel, not `usage=None`, in the non-succeeded audit helper** -- see Deviations below; the identical Rule 1 fix 26-07 already made, now applied here too.
- **Scheduler dispatch logic extracted into two named top-level functions** rather than inlined verbatim into `_scheduler_loop()`'s body -- see Deviations below; needed to satisfy the plan's own required direct-await test convention.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `poll_pending_batches()`'s per-job loop re-selects by scalar id, not the initially-loaded `AiBatchJob` ORM object**
- **Found during:** Task 1, while designing the per-job try/except containment the plan's own action text requires ("Wrap the per-job body so one failing job does not abort the others")
- **Issue:** The plan's literal action text queries `jobs = (await db.execute(select(AiBatchJob)...)).scalars().all()` and loops over these ORM objects directly. `26-07-SUMMARY.md` already documented and fixed the EXACT same bug class for `run_batch_prewarm()`'s tenant loop: `AsyncSession.rollback()` (needed in a per-item `except` block to recover from one item's failure) expires EVERY object in the session's identity map -- not just the failed item's. Had I looped over already-loaded `AiBatchJob` objects directly, a rollback triggered by job N's failure would leave job N+1's `job.tenant_id`/`job.model`/etc. attribute access attempting a synchronous lazy-reload, raising `sqlalchemy.exc.MissingGreenlet` on the very next access -- for ANY tenant with 2+ in-progress jobs where an earlier one fails.
- **Fix:** Changed the outer query to `select(AiBatchJob.id)` (a plain scalar column), then inside each per-job `try`, re-queries the fresh full row via `select(AiBatchJob).where(AiBatchJob.id == job_id)`. A bare `uuid.UUID` has no ORM expiration/lazy-load behavior, so it survives any number of intervening rollbacks; re-querying fresh per iteration means even the row itself is immune to a prior iteration's rollback.
- **Files modified:** `backend/app/ai/batch.py`
- **Verification:** No dedicated multi-job-failure regression test was added this plan (the plan didn't name one, and 26-07's own equivalent test — `test_run_batch_prewarm_one_tenant_failure_does_not_block_others` — is the precedent this fix mirrors); the fix's correctness was verified via direct reasoning against 26-07's own documented, tested finding for the structurally identical pattern, plus all 6 new poll tests (which DO exercise the per-job try/except's happy paths) passing.
- **Committed in:** `6192e94` (Task 1 commit)

**2. [Rule 1 - Bug] Literal `batch_errored`/`batch_canceled`/`batch_expired` status strings via `match`/`case`, not the plan's literal `status=f"batch_{line.result.type}"` f-string**
- **Found during:** Task 1, while transcribing the plan's literal action text for the errored/canceled/expired audit call
- **Issue:** The plan's own action text instructs `status=f"batch_{line.result.type}"` (an f-string), but the SAME plan's acceptance criteria requires `grep -n "batch_errored\|batch_canceled\|batch_expired" backend/app/ai/batch.py` to show all three present. An f-string's interpolation (`f"batch_{line.result.type}"`) never produces the literal substrings `batch_errored`/`batch_canceled`/`batch_expired` in the SOURCE FILE -- only at runtime, once `line.result.type` is a real string value. The plan's own literal instruction and its own acceptance criterion are mutually contradictory.
- **Fix:** Branch explicitly per result type (`match line.result.type: case "errored": ... status="batch_errored" ...`) via a small `_audit_non_succeeded_batch_result()` helper to avoid tripling the `audit_log_ai_call()` boilerplate, so all three status strings appear literally in the source.
- **Files modified:** `backend/app/ai/batch.py`
- **Verification:** `grep -n "batch_errored\|batch_canceled\|batch_expired" backend/app/ai/batch.py` shows all three; `test_poll_result_types_errored_canceled_expired` asserts each finding gets its own correct, distinct status at runtime too.
- **Committed in:** `6192e94` (Task 1 commit)

**3. [Rule 1 - Bug] `_audit_non_succeeded_batch_result()` uses the module's `_ZERO_USAGE` sentinel, not the plan's literal `usage=None`**
- **Found during:** Task 1, while transcribing the plan's literal action text for the same errored/canceled/expired audit call
- **Issue:** The plan's action text instructs `usage=None`. `audit_log_ai_call()` (`app/ai/audit.py`) unconditionally reads `usage.input_tokens`/`usage.output_tokens` with no null-guard -- passing `None` raises `AttributeError` the first time this path is exercised. This is the EXACT SAME bug `26-07-SUMMARY.md` already found and fixed for `run_batch_prewarm()`'s budget-skip audit call, and that summary explicitly flagged it as relevant to this plan: "its poller will construct the SAME kind of per-item audit calls and must NOT reintroduce either pattern."
- **Fix:** `_audit_non_succeeded_batch_result()` passes the module's existing `_ZERO_USAGE = SimpleNamespace(input_tokens=0, output_tokens=0)` sentinel instead of `None`.
- **Files modified:** `backend/app/ai/batch.py`
- **Verification:** `test_poll_result_types_errored_canceled_expired` passes, asserting each of the three audit rows' `details["cost_estimate_usd"] == 0.0` with no crash.
- **Committed in:** `6192e94` (Task 1 commit)

**4. [Rule 3 - Blocking] Scheduler dispatch logic extracted into `_dispatch_ai_batch_prewarm()`/`_dispatch_ai_batch_poll()` instead of inlined directly in `_scheduler_loop()`'s body**
- **Found during:** Task 2, while reconciling the plan's action text ("Inside `_scheduler_loop()`... add block A... Add block B...") against its own `read_first` instruction to mirror `test_connector_health.py::test_scheduler_path_failure_parity`'s `from app.connectors import scheduler as scheduler_module; await scheduler_module.<fn>(...)` direct-await calling convention for the new scheduler test
- **Issue:** `_scheduler_loop()` is an infinite `while True:` loop with a 60-second `asyncio.sleep()` at the bottom -- it cannot be awaited to completion in a test, so literally inlining the two new blocks directly in its body would make the plan's own required test-writing convention (a directly-awaitable named function) impossible to satisfy for the dispatch logic itself.
- **Fix:** Extracted each block into its own top-level `async def _dispatch_ai_batch_prewarm()`/`_dispatch_ai_batch_poll()` function (each still self-contained with its own try/except, exactly as specified); `_scheduler_loop()`'s per-tick body now just does `await _dispatch_ai_batch_prewarm(); await _dispatch_ai_batch_poll()`. Awaiting these wrapper functions inline is safe and does NOT reintroduce D-05's forbidden inline-await pattern -- each wrapper itself does only a datetime comparison plus an `asyncio.create_task(...)` call (no I/O), so awaiting the WRAPPER returns near-instantly; only the wrapped batch function runs detached in the background.
- **Files modified:** `backend/app/connectors/scheduler.py`
- **Verification:** All plan-specified grep acceptance criteria still pass (they check for substrings anywhere in the file, not structural position); `test_batch_blocks_are_non_blocking` and the other 6 new scheduler tests all call `scheduler_module._dispatch_ai_batch_prewarm()`/`_dispatch_ai_batch_poll()` directly and pass.
- **Committed in:** `5b725a6` (Task 2 commit)

**5. [Rule 2 - Missing Critical] Defensive `the_hash is None` skip + `case _:` fallback in `poll_pending_batches()`'s results loop**
- **Found during:** Task 1, while implementing the cache-key rebuild from `custom_id_hash_map`
- **Issue:** The plan's action text assumes every `custom_id` in a batch's results is present in `job.custom_id_hash_map` (true by construction under normal operation, since `run_batch_prewarm()` populates it 1:1 with the submitted requests) -- but nothing defends against a malformed/incomplete map reaching this code path, and passing `None` into `build_cache_key()`'s `str`-typed parameter would silently embed the literal text `"None"` into a real cache key rather than failing loudly. Similarly, the Anthropic Batches API's four documented result types (`succeeded`/`errored`/`canceled`/`expired`) are exhaustive today, but a future SDK/API addition of a 5th type would otherwise fall through the `match` silently.
- **Fix:** Added a `the_hash is None` guard (log a warning, skip that one line, continue processing the rest of the batch's results) and a `case _:` catch-all that logs an `ai_batch_poll_unknown_result_type` warning rather than silently doing nothing.
- **Files modified:** `backend/app/ai/batch.py`
- **Verification:** Neither branch is exercised by the current test suite (both are defensive backstops for conditions that don't arise under normal operation); `ruff`/`mypy` clean, and the addition doesn't change any existing test's behavior.
- **Committed in:** `6192e94` (Task 1 commit)

---

**Total deviations:** 5 auto-fixed (3 Rule 1 bug fixes correcting factually-incorrect-or-self-contradicting plan instructions -- two of which are the EXACT bug classes 26-07-SUMMARY.md explicitly predicted this plan would need to avoid reintroducing; 1 Rule 3 structural extraction required to satisfy the plan's own testability requirement; 1 Rule 2 defensive addition).
**Impact on plan:** All five are necessary for correctness or for the plan's own acceptance criteria to be satisfiable at all. Deviations 1-3 would each have shipped code that crashes or fails its own grep gate on first real exercise. Deviation 4 is a minimal, behavior-preserving structural reorganization (the SAME two try/except blocks, just callable by name) forced by a genuine conflict between two of the plan's own instructions. Deviation 5 is additive defensive-only code with zero behavior change on the happy path. No scope creep beyond the plan's own two functions -- no new files beyond the plan's own `test_scheduler_ai_batch.py`, no new public symbols beyond what the plan specified (the two `_dispatch_*` helpers and `_audit_non_succeeded_batch_result()` are private, minimal, and directly implied by the plan's own action text).

## Issues Encountered

- **Accidentally used `git stash` once during Task 1 verification** (to compare `mypy`'s output before/after the `batch.py` change), in violation of this plan's explicit `git_hygiene` instruction -- the exact same mistake `26-07-SUMMARY.md` documented making. Immediately `git stash pop`'d; verified via `git stash list` that all 5 pre-existing stash entries survived untouched, in their original order, and that `batch.py`'s working-tree change was correctly restored. No further `git stash` used for the remainder of this plan -- the mypy-baseline delta was instead confirmed unrelated via `mypy-baseline filter`'s own detailed output (isolating the exact 3 changed `note:` lines) without any further stash/restore cycle.
- **`mypy-baseline.txt` note-line-number-drift artifact (4th recurrence this phase, unrelated to this plan's diff).** Logged to `deferred-items.md` under "Plan 26-08" -- same `types-python-jose` stub-hint artifact 26-01/26-06/26-07 already documented; `mypy app/ | grep '^app/ai/batch.py\|^app/connectors/scheduler.py'` returns empty, directly proving this plan's own diff introduces no real mypy debt.
- **Pre-existing untracked `scratchpad/roadmap_patch.py`** (already flagged by 26-07) confirmed still present, unrelated to this plan, re-noted in `deferred-items.md` rather than silently re-discovered.

## User Setup Required

None - no external service configuration required. (A live end-to-end Anthropic Batches API smoke test — a real submit + poll + retrieve cycle — remains the same accepted, previously-documented gap as every other AI phase's live-key requirement; every test here injects a fake client via the established `anthropic_client_factory` seam.)

## Requirements Tracking

`REQUIREMENTS.md`'s **AIP-02** checkbox is now marked `[x]` complete, and its traceability-table row flipped to "Complete" -- per this plan's own explicit instruction, AIP-02 is genuinely satisfied end-to-end only now that both backend halves (the submitter, 26-07) and the scheduler wiring (this plan) have landed: the scheduler dispatches one Message Batch per tenant nightly and polls to completion every tick, both via `asyncio.create_task`, each resolving its own tenant's own key.

**AIP-01's checkbox is deliberately left untouched** (still "Pending") -- this plan's own `requirements:` frontmatter field names only `AIP-02`; AIP-01 (the narrative itself augmenting, never replacing, the deterministic score) was built across Plans 01-05 and is not this plan's concern to close out. Flagging for phase verification's own review: AIP-01 appears functionally complete already (grounding query, no-rank schema, prompt builder, on-demand route, frontend section, and the 26-05 TRACER GATE all shipped), but its `REQUIREMENTS.md` checkbox has not been flipped by any prior Phase 26 plan either -- this may be an intentional "phase verification closes it" convention (matching how the phase-level roadmap checkbox is also deliberately left unflipped here) rather than an oversight, but it is worth an explicit look during `/gsd-verify-work 26`.

`ROADMAP.md`'s Phase 26 plan-progress row was updated via DIRECT edit to `8/8` (status left as "In Progress", NOT flipped to "Complete" -- that is phase verification's call, per this plan's own explicit instruction); the `26-08-PLAN.md` checkbox in the Plans list was flipped to `[x]`; the top-level `- [ ] **Phase 26: Prioritization Narrative**` milestone checkbox was deliberately left unchecked. `git diff` confirms both edits are exactly the two intended one-line changes, with zero corruption and no stray `Phase 999.x` write (the known `state`/`roadmap update-plan-progress` SDK bug this plan's own instructions warned about was avoided entirely by using direct `Edit` calls instead).

## Next Phase Readiness

- **Phase 26 (Prioritization Narrative) is now 8/8 plans complete.** The batch feature is genuinely live end-to-end: the scheduler submits one Message Batch per tenant nightly (24h-gated, `asyncio.create_task`-dispatched) covering the D-01 top-N findings, and polls to completion every tick (also `asyncio.create_task`-dispatched); the poller resumes any in-flight batch from Postgres across a restart, retrieves each with its owning tenant's OWN freshly-constructed BYOK key, and writes each narrative into the SAME tenant cache the drill panel's on-demand path reads -- a batch-warmed narrative is a plain cache hit for the analyst (D-06). SC3 (bulk generation via the scheduler using the Message Batches API, dispatched via `asyncio.create_task`, using only the tenant's own key) is satisfied.
- Ready for `/gsd-verify-work 26` -- the phase-level verification pass should confirm the full tracer-to-batch arc holds together (on-demand fallback still works per 26-03/26-05; the `queued` signal from 26-06 correctly reflects an in-flight batch; a batch-warmed cache hit renders identically to an on-demand one in the frontend), and should make its own call on whether AIP-01's `REQUIREMENTS.md` checkbox and the phase-level roadmap checkbox should now flip (both deliberately left untouched by this plan, per its own explicit scope).
- No blockers. No live Anthropic key was available or required this plan (matching every prior Phase 26/24/25 plan's accepted gap) -- every new code path is proven against a fake client injected via the established `anthropic_client_factory` seam, including the two Rule 1 bug classes this plan's own predecessor (26-07) explicitly flagged as likely to recur here, which did in fact recur and were fixed the same way.

## Self-Check: PASSED

- FOUND: `backend/app/ai/batch.py` (contains `async def poll_pending_batches`, `async def _audit_non_succeeded_batch_result`, `"batch_errored"`, `"batch_canceled"`, `"batch_expired"`, `status == "in_progress"`, zero bare `AsyncAnthropic()` constructions)
- FOUND: `backend/app/connectors/scheduler.py` (contains `_last_ai_batch_prewarm`, `async def _dispatch_ai_batch_prewarm`, `async def _dispatch_ai_batch_poll`, exactly 2 `asyncio.create_task(run_batch_prewarm())`/`asyncio.create_task(poll_pending_batches())` calls, zero `AsyncAnthropic` references, zero inline `await run_batch_prewarm`/`await poll_pending_batches`)
- FOUND: `backend/tests/test_ai_batch.py` (16 tests total, all passing -- 10 pre-existing + 6 new poll tests)
- FOUND: `backend/tests/test_scheduler_ai_batch.py` (7 tests, all passing)
- FOUND commit `6192e94` (Task 1) in `git log --oneline --all`
- FOUND commit `5b725a6` (Task 2) in `git log --oneline --all`
- CONFIRMED: `test_ai_batch.py tests/test_scheduler_ai_batch.py` -q -> 23/23 green
- CONFIRMED: `test_ai_*.py test_scheduler_ai_batch.py` wave-merge regression -> 237/237 green
- CONFIRMED: `test_connector_health.py` (the other file exercising `scheduler.py`) -> 9/9 green, no regression
- CONFIRMED: `mypy app/ | grep '^app/ai/batch.py\|^app/connectors/scheduler.py'` -> empty (zero errors attributable to either file this plan modified)
- CONFIRMED: `ruff check` + `ruff format --check` clean on all 4 touched/created files
- CONFIRMED: `git stash list` shows exactly the same 5 pre-existing entries, in original order, after the accidental stash/pop in Issues Encountered

---
*Phase: 26-prioritization-narrative*
*Completed: 2026-07-31*
