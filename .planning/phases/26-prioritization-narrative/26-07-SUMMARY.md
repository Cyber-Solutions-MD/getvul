---
phase: 26-prioritization-narrative
plan: 07
subsystem: ai
tags: [fastapi, sqlalchemy, anthropic, message-batches-api, redis, byok, budget-guard]

# Dependency graph
requires:
  - phase: 26-06
    provides: "AiBatchJob durable registry (backend/app/ai/models.py) -- the row shape run_batch_prewarm() INSERTs into"
  - phase: 26-02
    provides: "build_explain_prioritization_prompt()/prioritization_prompt_version()/PRIORITIZATION_ALLOWLIST -- reused verbatim, shared between the on-demand route and this plan's batch submitter (CONTEXT default)"
  - phase: 26-01
    provides: "get_prioritization_context()/ExplainPrioritizationResponse -- the grounding record + zero-rank-field schema batch.py validates against"
  - phase: 24-04
    provides: "explain.py's _default_client_factory/_estimate_cost_usd/_build_output_config/_contains_leak_marker/MAX_TOKENS/pricing tables -- reused unchanged; the per-tenant-fresh-client seam this plan's T-24-19 mitigation mirrors exactly"
provides:
  - "get_top_findings_for_ai_batch() (vulnerabilities/service.py) -- the D-01 top-N query: Asset.risk_score DESC primary, KEV->CVSS->SLA per-finding tiebreak, tenant-scoped"
  - "get_month_to_date_spend() (extracted) + would_exceed_budget_for_batch() (ai/budget.py) -- the D-07 fail-closed batch pre-estimate, check_tenant_budget()'s contract unchanged"
  - "get_redis_client() (redis_client.py) -- the non-request Redis factory main.py's lifespan and the future scheduler batch job both call; single construction site"
  - "batch.py (new module): estimate_batch_cost_usd() (50% discount), run_batch_prewarm() (per-tenant FRESH BYOK client, freshness-skip, fail-closed budget, durable AiBatchJob INSERT, per-tenant failure containment), validate_and_cache_batch_result() (single-pass validator, no retry, 50% cost)"
affects: [26-08-scheduler-integration, 28-eval-cost-observability-gate]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Composite new module (batch.py) borrowing three existing shapes rather than one analog: explain.py's validation-gate chain (minus retry), scheduler.py's own-session background-task + active-tenant-loop shape, explain_remediation_guidance.py's audit-only refusal shape"
    - "TypedDict-constructed Anthropic request objects (Request/MessageCreateParamsNonStreaming) are plain nested dicts at runtime -- read via dict-style subscript access (req[\"params\"][field]), never attribute access, which raises AttributeError. This is the FIRST place this codebase reads a construction-side (not response-side) Anthropic TypedDict back after building it -- the asymmetry vs. the response-side Pydantic BaseModels (MessageBatch, MessageBatchIndividualResponse) is now a documented precedent for Plan 08's poller."
    - "Per-tenant try/except loop containment selects the loop-scope FK id as a plain scalar column (select(Tenant.id), not select(Tenant)) rather than the whole ORM object -- AsyncSession.rollback() expires every object in the session's identity map, so a later iteration's attribute access on an already-loaded ORM object raises sqlalchemy.exc.MissingGreenlet outside an await expression once ANY earlier iteration in the same session has rolled back."

key-files:
  created:
    - backend/app/ai/batch.py
    - backend/tests/test_top_findings_for_ai_batch.py
    - backend/tests/test_ai_batch.py
  modified:
    - backend/app/vulnerabilities/service.py
    - backend/app/ai/budget.py
    - backend/app/redis_client.py
    - backend/app/main.py
    - backend/tests/test_ai_budget.py

key-decisions:
  - "estimate_batch_cost_usd() reads the Request/MessageCreateParamsNonStreaming payload via DICT-style access (req[\"params\"][\"system\"]), not the plan's literal ATTRIBUTE-access instruction -- direct introspection of the installed anthropic==0.120.2 SDK proves both are TypedDict subclasses, which construct plain dict instances at runtime (type(Request(custom_id=\"x\", params=...)) is exactly dict); req.params raises AttributeError. Matches RESEARCH.md's own Pattern 6 code sample, which already used dict-style access -- the plan's interfaces-block claim (and its req[\"params\"]==0 grep acceptance criterion) does not hold against the real SDK."
  - "run_batch_prewarm()'s budget-skip audit call uses a local _ZERO_USAGE sentinel (SimpleNamespace(input_tokens=0, output_tokens=0)), not the plan's literal usage=None -- audit_log_ai_call() unconditionally reads usage.input_tokens/usage.output_tokens with no null-guard, so passing None crashes with AttributeError. Mirrors explain.py's own _ZERO_USAGE precedent for its structurally identical budget_exceeded/rate_limited audit calls."
  - "run_batch_prewarm() selects Tenant.id (a plain scalar column) instead of the whole Tenant ORM object, and wraps each tenant's processing in its own try/except -- added because AsyncSession.rollback() (needed to recover from one tenant's failure) expires every object in the session's identity map; a later iteration's tenant.id attribute access on an expired ORM object raises MissingGreenlet outside an await expression. Proven by a dedicated cross-tenant failure-containment test, not just reasoned about."
  - "validate_and_cache_batch_result() commits its own audit row immediately (await db.commit()) rather than leaving it to a not-yet-existing Plan 08 caller -- mirrors explain.py::_audit()'s wrapper convention (every attempt's audit row survives independently) and is what makes the row provable in a genuinely fresh session, matching this codebase's own established durability-proof test convention."
  - "Both test_ai_batch.py and test_top_findings_for_ai_batch.py write test file + implementation together in one commit per task (not split RED/GREEN commits) despite each task's tdd=\"true\" attribute -- the PLAN's own frontmatter type is execute (not tdd), matching 26-03's explicit precedent for the identical task-tdd-true/plan-type-execute combination; the Plan-Level TDD Gate Enforcement section is scoped to type: tdd plans only."

patterns-established:
  - "T-24-19 mitigation extended to the batch/scheduler surface: run_batch_prewarm() takes NO externally-injected shared client; a FRESH per-tenant AsyncAnthropic is built inside every loop iteration from that tenant's own resolved key. Proven by a two-tenant/two-distinct-key cross-tenant test whose submitted AiBatchJob.anthropic_batch_id encodes which api_key actually signed it."
  - "D-07 fail-closed budget applies symmetrically to batch and interactive paths: would_exceed_budget_for_batch() adds a pre-estimate to the SAME get_month_to_date_spend() sum check_tenant_budget() already uses -- one source of truth for 'how much has this tenant spent this month.'"
  - "The 50% batch discount is applied at BOTH cost sites (estimate_batch_cost_usd's pre-submission estimate AND validate_and_cache_batch_result's actual-cost audit write) -- a single missed site would silently 2x-corrupt the tenant's month-to-date spend figure in one direction or the other."

requirements-completed: []  # AIP-02 intentionally NOT marked complete -- this plan delivers the batch submitter + validator only; Plan 08 (scheduler wiring + poller) is still required before bulk generation is genuinely live end-to-end. Mirrors 26-06-SUMMARY.md's identical rationale.

# Metrics
duration: 30min
completed: 2026-07-31
---

# Phase 26 Plan 07: Batch Submitter Summary

**The nightly Message Batches submitter (`backend/app/ai/batch.py`): a per-tenant, freshly-constructed BYOK Anthropic client (never shared/injected) submits one Message Batch per tenant covering the D-01 top-N findings, gated by a fail-closed budget pre-estimate at the 50% batch discount, with a durable `AiBatchJob` registry row and a single-pass result validator -- all proven with a fake Anthropic client injected via the established `anthropic_client_factory` test seam.**

## Performance

- **Duration:** 30 min
- **Started:** 2026-07-31T14:26:00Z
- **Completed:** 2026-07-31T14:56:02Z
- **Tasks:** 3/3 completed
- **Files modified:** 9 (3 new, 6 modified)

## Accomplishments

- `backend/app/vulnerabilities/service.py`: new `get_top_findings_for_ai_batch(db, tenant_id, limit)` -- the D-01 top-N batch-scope query, ranked by `Asset.risk_score DESC` (Assumption A1, the literal ASSET-02 number) primary with a KEV->CVSS->SLA per-finding tiebreak, `nulls_last` for asset-less findings, OPEN+IN_PROGRESS status filter (matching `risk_score.py`'s own scoring input), tenant-scoped. 6 tests proving the ordering, tiebreak, nulls-last behavior, limit, status-exclusion, and tenant-scoping.
- `backend/app/ai/budget.py`: `get_month_to_date_spend()` extracted from `check_tenant_budget()` (unchanged public contract -- zero edits needed by `explain.py` or any existing route); `would_exceed_budget_for_batch()` -- the D-07 fail-closed pre-submission check, never skips when no cap is configured.
- `backend/app/redis_client.py` + `backend/app/main.py`: `get_redis_client()` non-request factory (same `BlockingConnectionPool` options as the prior inline construction) so the scheduler's future batch job can obtain a Redis client outside any FastAPI request; `main.py`'s lifespan now calls this single construction site. Verified the rewire is behaviorally identical (rate-limit + multi-replica suites unaffected).
- `backend/app/ai/batch.py` (new, 285 lines): `estimate_batch_cost_usd()` (sums real `count_tokens()` input + worst-case output at the model's rate, x0.5 discount), `run_batch_prewarm()` (loops active tenants; per tenant resolves its OWN key, skips silently if none configured (D-23); builds a FRESH per-tenant client; selects the D-01 top-N; skips any finding whose cache entry is already fresh; pre-estimates cost; fails closed on a would-breach budget with an admin alert + audit row + NO AiBatchJob; on the OK path submits one Message Batch and durably INSERTs an `AiBatchJob` row before advancing to the next tenant), `validate_and_cache_batch_result()` (single-pass schema -> business-rules -> grounded -> leak-marker -> cache gate, no retry loop, cost booked at 50%).
- `backend/tests/test_ai_batch.py` (new, 10 tests): the discount math; a keyless tenant is skipped with the client factory never even invoked; a TWO-TENANT/TWO-DISTINCT-KEY test proving each tenant's batch is submitted with its OWN key (the T-24-19 cross-tenant isolation regression guard -- the submitted `AiBatchJob.anthropic_batch_id` literally encodes which key signed it); a cache-fresh finding is excluded from the submitted batch; the budget-skip path (no `create()`, no `AiBatchJob` row, admin notified, `batch_skipped_budget_exceeded` audited); the OK path's durable `AiBatchJob` re-queried in a genuinely fresh session; one tenant's failure never blocks another tenant's submission in the same run; and the validator's `ok`/ungrounded/leak-marker branches.
- Full `test_ai_*.py` + `test_top_findings_for_ai_batch.py` wave-merge regression: 230/230 green. `ruff check` + `ruff format --check` clean on every touched/created file. `mypy` introduces zero new errors project-wide (verified via the exact CI gate command, `mypy app/ | mypy-baseline filter --allow-unsynced` -- the only delta is a 3rd recurrence of the already-documented `types-python-jose` note-line-drift artifact in an unrelated file).

## Task Commits

Each task was committed atomically:

1. **Task 1: get_top_findings_for_ai_batch() -- the D-01 top-N query** - `b60f057` (feat)
2. **Task 2: budget pre-estimate helpers + non-request Redis factory** - `52dae40` (feat)
3. **Task 3: batch.py -- cost estimate, run_batch_prewarm, single-pass validator** - `5fd8865` (feat)

**Plan metadata:** (this commit) - `docs(26-07): complete plan`

## Files Created/Modified

- `backend/app/vulnerabilities/service.py` - new `get_top_findings_for_ai_batch()` (D-01 top-N query, alongside `list_vulnerabilities()`'s own sort logic)
- `backend/tests/test_top_findings_for_ai_batch.py` (new) - 6 tests: risk_score-primary ordering + tiebreak, nulls_last, limit, status-exclusion, tenant-scoping
- `backend/app/ai/budget.py` - extracted `get_month_to_date_spend()`; added `would_exceed_budget_for_batch()`
- `backend/app/redis_client.py` - added `get_redis_client()` non-request factory
- `backend/app/main.py` - lifespan now calls `get_redis_client()` (single construction site; removed the now-unused `import redis.asyncio as redis`)
- `backend/tests/test_ai_budget.py` - 6 new tests for the SUM helper, unchanged `check_tenant_budget` delegation, and `would_exceed_budget_for_batch`'s three branches
- `backend/app/ai/batch.py` (new) - `estimate_batch_cost_usd()`, `run_batch_prewarm()`, `validate_and_cache_batch_result()`
- `backend/tests/test_ai_batch.py` (new) - 10 tests covering the discount, per-tenant-key isolation, keyless/cache-fresh/budget skips, durable registry insert, per-tenant failure containment, and the validator's three outcome branches
- `.planning/phases/26-prioritization-narrative/deferred-items.md` - logged 2 out-of-scope, pre-existing artifacts (a stray untracked `scratchpad/` dir predating this session; pre-existing baselined mypy debt in files this plan's diff never touches)

## Decisions Made

- **`estimate_batch_cost_usd()` uses dict-style access, not the plan's literal attribute-access instruction** -- see Deviations below; this is a correctness fix, not a style preference.
- **`run_batch_prewarm()`'s budget-skip audit uses a local `_ZERO_USAGE` sentinel, not `usage=None`** -- see Deviations below.
- **`run_batch_prewarm()` selects `Tenant.id` (scalar), not `Tenant` (ORM object), and wraps each tenant in its own try/except** -- see Deviations below; the scalar-selection fix and the try/except addition are two halves of the same correctness requirement (you cannot safely add per-iteration exception containment to a shared-session loop without also avoiding session-expiration-sensitive ORM attribute reads after a rollback).
- **`validate_and_cache_batch_result()` commits its own audit row** -- see Deviations below.
- **Test files combine test+implementation in one commit per task, not split RED/GREEN commits** -- the plan's frontmatter `type: execute` (not `type: tdd`) matches 26-03's own explicit precedent for the identical `tdd="true"`-task/`type: execute`-plan combination; the formal TDD gate-sequence enforcement is scoped to `type: tdd` plans only.
- **`_extract_scanner_data` (a `_`-prefixed helper) is imported from `app.ai.explain` into `batch.py`**, even though it is not literally named in the plan's "Reused UNCHANGED" list -- it is the exact, already-tested parser the interactive route's own `_allowlisted_hash_fields()`-style helpers use to re-derive the D-18 hash input from `user_blocks`; re-implementing an equivalent parser inline would duplicate logic the D-18 "structural, not remembered" discipline exists specifically to avoid.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `estimate_batch_cost_usd()`'s attribute-access instruction crashes on the installed SDK -- fixed to dict-style access**
- **Found during:** Task 3, while transcribing the plan's literal `req.params.system`/`req.params.messages` instruction into `estimate_batch_cost_usd()`
- **Issue:** Direct introspection of the installed `anthropic==0.120.2` SDK (`backend/.venv`) proves `Request` and `MessageCreateParamsNonStreaming` are `TypedDict` subclasses (`from ..._utils import ...`; `class Request(TypedDict, total=False)` in `batch_create_params.py`). Calling `Request(custom_id="x", params=...)` returns a PLAIN `dict` at runtime -- `type(Request(custom_id="x", params=MessageCreateParamsNonStreaming(...)))` is exactly `dict`. `req.params` therefore raises `AttributeError: 'dict' object has no attribute 'params'`. The plan's own `<critical>` block and Task 3's acceptance criteria (`grep -c 'req["params"]' == 0`) both assert the opposite. This is unlike the RESPONSE-side objects (`MessageBatch`, `MessageBatchIndividualResponse`) the poller (Plan 08) reads on retrieval, which genuinely ARE Pydantic `BaseModel`s with real attribute access -- the plan's claim appears to have generalized from the response side to the construction side, where it does not hold.
- **Fix:** `estimate_batch_cost_usd()` reads `params = req["params"]`, `params["system"]`, `params["messages"]` -- dict-style subscript access, matching RESEARCH.md's OWN Pattern 6 code sample (which already used `req["params"]["system"]`, not attribute access).
- **Files modified:** `backend/app/ai/batch.py`
- **Verification:** `test_estimate_batch_cost_discount` passes and asserts the exact discount math against a fake client's `count_tokens()` calls; direct interactive Python session confirmed `type(Request(...))`/`type(MessageCreateParamsNonStreaming(...))` are both `dict`. The plan's own literal-attribute-access acceptance grep (`grep -c 'req["params"]' == 0`) will legitimately show `2`, not `0` -- expected and documented, not a defect.
- **Committed in:** `5fd8865` (Task 3 commit)

**2. [Rule 1 - Bug] `usage=None` in the budget-skip audit call would crash `audit_log_ai_call()` -- fixed with a `_ZERO_USAGE` sentinel**
- **Found during:** Task 3, while transcribing the plan's literal `usage=None` instruction for the `batch_skipped_budget_exceeded` audit call
- **Issue:** `audit_log_ai_call()` (`app/ai/audit.py`) unconditionally reads `usage.input_tokens`/`usage.output_tokens` when building its `details` dict -- there is no null-guard. Passing `usage=None` (the plan's literal instruction) raises `AttributeError: 'NoneType' object has no attribute 'input_tokens'` the very first time a budget-skip path is exercised.
- **Fix:** Defined `_ZERO_USAGE = SimpleNamespace(input_tokens=0, output_tokens=0)` in `batch.py` (mirroring `explain.py`'s own identically-named, identically-shaped sentinel used for its structurally equivalent `budget_exceeded`/`rate_limited` audit calls) and pass that instead of `None`.
- **Files modified:** `backend/app/ai/batch.py`
- **Verification:** `test_run_batch_prewarm_budget_skip` passes, asserting the audit row's `details["status"] == "batch_skipped_budget_exceeded"` and `cost_estimate_usd == 0.0`.
- **Committed in:** `5fd8865` (Task 3 commit)

**3. [Rule 2 - Missing Critical, surfacing a Rule 1 bug] Per-tenant failure containment added; required selecting `Tenant.id` as a scalar, not the ORM object**
- **Found during:** Task 3, while adding per-tenant try/except containment to `run_batch_prewarm()`'s loop (a genuinely new resilience property the plan's own action text does not describe: one tenant's transient failure -- an Anthropic API error, a malformed grounding record -- must not silently abort every OTHER tenant's nightly batch in the same run)
- **Issue:** The first implementation selected `tenants = (await db.execute(select(Tenant)...)).scalars().all()` (the whole ORM object, matching `scheduler.py`'s own SLA-check-block precedent) and referenced `tenant.id` throughout the loop body. `AsyncSession.rollback()` (needed inside the new `except` block to recover from a failed tenant's partially-pending work) expires EVERY object in the session's identity map -- not just the failed tenant's. A dedicated regression test (`test_run_batch_prewarm_one_tenant_failure_does_not_block_others`) immediately caught this: after tenant_a's simulated failure triggered a rollback, the exception-logging line's own `str(tenant.id)` access raised `sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called; can't call await_only() here` -- a synchronous lazy-reload attempt on an expired ORM attribute, outside any `await` expression. The SAME failure would have recurred for tenant_b's OWN `tenant.id` reads on the next loop iteration, since rollback expires the whole identity map, not just the object touched by the failed transaction.
- **Fix:** Changed the query to `select(Tenant.id)` (a plain scalar column) instead of `select(Tenant)`, and renamed the loop variable from `tenant` to `tenant_id` throughout. A bare `uuid.UUID` value has no ORM expiration/lazy-load behavior, so it survives any number of intervening rollbacks unaffected.
- **Files modified:** `backend/app/ai/batch.py`
- **Verification:** `test_run_batch_prewarm_one_tenant_failure_does_not_block_others` (new test, not named in the plan) passes: tenant_a's client-factory failure is contained (no `AiBatchJob` row, no crash), and tenant_b's own submission completes successfully in the SAME `run_batch_prewarm()` call. Full `test_ai_batch.py` suite (10 tests) green; wave-merge regression (230 tests) green.
- **Committed in:** `5fd8865` (Task 3 commit)

**4. [Rule 2 - Missing Critical] `validate_and_cache_batch_result()` commits its own audit row**
- **Found during:** Task 3, while implementing `validate_and_cache_batch_result()` -- the plan's action text describes the audit call but does not explicitly say whether the function commits
- **Issue:** `audit_log_ai_call()` deliberately does NOT commit (mirrors `rotate_credentials()`'s pattern, per its own docstring) -- it only `db.add()`s the row. Leaving the commit to a not-yet-existing Plan 08 caller would mean this function's own audit row is not durable/provable in isolation, and would break the established test convention this codebase uses to prove AI-call audit durability (`test_ai_audit.py`'s `_fetch_rows()` re-queries via a genuinely FRESH `async_session_factory()` session specifically to prove the row survived past the test's own transaction).
- **Fix:** Added `await db.commit()` immediately after `audit_log_ai_call()`, mirroring `explain.py::_audit()`'s own wrapper convention ("this wrapper commits immediately after each call so every attempt's audit row survives independently").
- **Files modified:** `backend/app/ai/batch.py`
- **Verification:** All three `validate_and_cache_batch_result()` tests (`test_validate_and_cache_ok_books_half_cost`, `_ungrounded_not_cached`, `_leak_marker_flagged`) re-query the audit row via a fresh session and pass.
- **Committed in:** `5fd8865` (Task 3 commit)

---

**Total deviations:** 4 auto-fixed (2 Rule 1 bug fixes correcting factually-incorrect plan instructions against the real installed SDK/audit-writer contract; 2 Rule 2 additions for missing durability/resilience, one of which surfaced and required fixing a related Rule 1 bug as part of implementing it correctly).
**Impact on plan:** All four are necessary for correctness -- the plan's literal text for deviations 1 and 2 would have shipped code that crashes on its very first real invocation (attribute access on a TypedDict-constructed dict; `None.input_tokens`). Deviations 3 and 4 are additive resilience/durability properties consistent with this exact codebase's own established conventions (`_audit()`'s immediate-commit wrapper; per-call audit-row durability) and are each proven by a dedicated new test. No scope creep beyond the plan's own three functions -- no new files, no new public symbols beyond what the plan specified.

## Issues Encountered

- **`mypy-baseline.txt` note-line-number-drift artifact (3rd recurrence this phase, unrelated to this plan's diff).** `mypy app/ | mypy-baseline filter --allow-unsynced` reports "3 new / 3 fixed" both before and after this plan's changes (confirmed via a normalized file+message diff, ignoring line numbers). All 3 changed lines are `note:` lines (stub-install hints for the missing local `types-python-jose` package), this run attributed to `app/auth/dependencies.py:10` vs. `app/connectors/google_workspace.py:0` in the baseline -- a file neither this plan nor its diff touches. A second, purely cosmetic whitespace-indentation difference in `app/connectors/jamf.py`'s note text (also untouched by this plan) was isolated in the same diff pass. `mypy app/ai/batch.py`/`app/vulnerabilities/service.py`/`app/ai/budget.py`/`app/redis_client.py`/`app/main.py` in isolation all return zero errors attributable to any line this plan modified. Same class as 26-01's and 26-06's prior occurrences. Logged to `deferred-items.md` under "Plan 26-07"; not fixed (out of scope, environmental, pre-existing).
- **A pre-existing untracked `scratchpad/roadmap_patch.py` at the repo root** (timestamped before this session, unrelated to any task in this plan) was left as-is and logged to `deferred-items.md` rather than silently ignored or swept up into a commit.
- **Accidentally used `git stash` once during Task 2 verification** (to compare mypy's `main.py` error count before/after the redis-client rewire), in violation of this plan's explicit `git_hygiene` instruction. Immediately `git stash pop`'d; verified via `git stash list` that all 5 pre-existing stash entries survived untouched, in their original order. No further `git stash` used for the remainder of this plan -- the same before/after comparison for later checks was done via `mypy-baseline`'s own normalized diff instead.

## User Setup Required

None - no external service configuration required.

## Requirements Tracking

`REQUIREMENTS.md`'s AIP-02 checkbox remains **not** marked complete, mirroring 26-06-SUMMARY.md's identical rationale: this plan delivers only the batch submitter + single-pass validator (test-invoked directly, with a fake Anthropic client injected via the `anthropic_client_factory` seam) -- nothing is wired into the scheduler yet. AIP-02 (bulk generation via the scheduler + Message Batches API) is not fully satisfied until Plan 08 (scheduler integration + poller) lands.

`ROADMAP.md`'s per-plan tracking and `STATE.md`'s frontmatter/position/decisions/metrics were updated via DIRECT edit (not the `state`/`roadmap update-plan-progress` SDK commands, per this plan's own `tracking_tool_caution`) -- `git diff`-verified clean, no corruption, no Phase 999.x write.

## Next Phase Readiness

- `run_batch_prewarm()` has a fully test-proven submission path: per-tenant BYOK isolation (T-24-19), freshness-skip, fail-closed budget, and a durable `AiBatchJob` INSERT -- ready for Plan 08 to dispatch it from the scheduler via `asyncio.create_task`, exactly as D-05 requires.
- `validate_and_cache_batch_result()` is ready for Plan 08's poller to call per succeeded batch result (matched by `custom_id` against `AiBatchJob.custom_id_hash_map`) -- `errored`/`canceled`/`expired` results are Plan 08's own responsibility to audit directly (never reaching this validator, per RESEARCH Pattern 8).
- `get_redis_client()` is the confirmed, tested, single-construction-site Redis factory Plan 08's poller will also call for its own Redis client, alongside `run_batch_prewarm()`'s existing use.
- Two Rule 1 bugs found and fixed in this plan (dict-vs-attribute access on the TypedDict-constructed request objects; the `usage=None` audit crash) are directly relevant to Plan 08 too -- its poller will construct the SAME kind of per-item audit calls and must NOT reintroduce either pattern. Flagging explicitly for the next plan's own `read_first` pass.
- No blockers.

## Self-Check: PASSED

- FOUND: `backend/app/vulnerabilities/service.py` (contains `def get_top_findings_for_ai_batch`, `nulls_last(desc(Asset.risk_score))`, `status.in_(["OPEN", "IN_PROGRESS"])` inside the new function)
- FOUND: `backend/tests/test_top_findings_for_ai_batch.py` (6 tests, all passing)
- FOUND: `backend/app/ai/budget.py` (contains `def get_month_to_date_spend`, `def would_exceed_budget_for_batch`; `func.sum(AuditLog.details` appears exactly once)
- FOUND: `backend/app/redis_client.py` (contains `def get_redis_client`)
- FOUND: `backend/app/main.py` (`get_redis_client()` used in the lifespan; `redis.Redis(connection_pool` count is 0)
- FOUND: `backend/tests/test_ai_budget.py` (13 tests total, all passing -- 7 pre-existing + 6 new)
- FOUND: `backend/app/ai/batch.py` (contains `async def estimate_batch_cost_usd`, `async def run_batch_prewarm`, `async def validate_and_cache_batch_result`; `async def run_batch_prewarm(client` count is 0; `AsyncAnthropic()` bare count is 0)
- FOUND: `backend/tests/test_ai_batch.py` (10 tests, all passing)
- FOUND commit `b60f057` (Task 1) in `git log --oneline --all`
- FOUND commit `52dae40` (Task 2) in `git log --oneline --all`
- FOUND commit `5fd8865` (Task 3) in `git log --oneline --all`
- CONFIRMED: `test_ai_*.py` + `test_top_findings_for_ai_batch.py` wave-merge regression 230/230 green
- CONFIRMED: `mypy app/ | mypy-baseline filter --allow-unsynced` introduces zero new errors attributable to this plan's diff (only the pre-existing, 3rd-recurrence note-line-drift artifact)

---
*Phase: 26-prioritization-narrative*
*Completed: 2026-07-31*
