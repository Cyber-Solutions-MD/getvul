---
phase: 24-ai-foundation-explain-this-vuln
plan: 04
subsystem: ai
tags: [anthropic, sse, streaming, fastapi, pydantic, redis, tdd, prompt-injection, byok]

# Dependency graph
requires:
  - phase: 24-02
    provides: ExplainVulnResponse/Citation schema gate, build_explain_vuln_prompt untrusted-content-as-data contract, prompt_version() auto-hash, audit_log_ai_call()
  - phase: 24-03
    provides: get_tenant_anthropic_key() BYOK resolution, tenant-scoped Redis cache (build_cache_key/record_hash/get_cached/set_cached), acquire_inflight/release_inflight, check_tenant_budget()/notify_admins_budget_exceeded()
provides:
  - _run_explain_stream() — the shared buffer-then-validate-then-replay streaming engine (parameterized by build_prompt/response_model), reused unchanged by Plan 08's host/remediation views
  - get_model_and_budget() — tenant model+budget-cap resolution from ConnectorConfig.config, shared between the engine's own dispatch and the GET cache-check's key computation
  - POST /api/v1/ai/explain-vuln/{finding_id} (SSE, require_analyst) + GET /api/v1/ai/explain-vuln/{finding_id} (cache-check, require_viewer) — the first real, working "click Explain -> validated cited summary streams back" path
  - Proven-live spike findings: anthropic==0.120.2's `client.messages.stream()` + `output_config` + `get_final_message()` all work exactly as AI-SPEC/RESEARCH documented, verified against the real installed SDK via httpx.MockTransport, not just asserted
affects: [24-05, 24-06, 24-07, 24-08, 24-09, 25, 26, 27]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Buffer-then-validate-then-replay as ONE outer try/finally around the entire post-acquire flow (prompt build through final replay yield), not per-phase acquire/release — GeneratorExit from a client abort at ANY point (mid-retry, mid-replay) still fires the finally and releases the per-tenant inflight guard exactly once"
    - "D-18 cache-key hashing reads the allowlisted fields BACK OUT of the already-built <scanner_data> prompt block (rightmost-close-tag extraction, mirroring Plan 02's own delimiter-breakout-safe convention) instead of a second, independently-maintained allowlist — structural D-18 compliance for this view AND every future Plan-08 view for free"
    - "Two-axis retry semantics: the corrective-turn retry loop (explain.py's own 2-attempt loop, D-26) is orthogonal to the SDK's own Retry-After-aware max_retries backoff (set once, on client construction) — a RateLimitError/APIStatusError short-circuits the ENTIRE function immediately (one audit row, status=rate_limited), it never consumes one of the two corrective-turn attempts"
    - "audit status vocabulary: grounded_retry fires ONLY when THIS attempt's failure cause was a self-reported grounded=false with a retry still available; validation_failed fires for a hard ValidationError/BusinessRuleError OR for the terminal (no-retries-left) attempt regardless of cause — reconciled precisely against both the grounded=false-then-succeeds test and the two-malformed-responses test"
    - "The engine's SSE vocabulary is deliberately two-tier: {type:'error', kind: busy|grounded_false|budget_exceeded|unknown} is a CLOSED set matching Plan 05's frontend ExplainStreamState exactly; 'no key configured' is a structurally DIFFERENT, non-error {type:'no_key'} event so it can never be confused with (or accidentally widen) the error kind vocabulary"
    - "get_model_and_budget() promoted from a private (_-prefixed) helper to a shared, no-underscore export the moment a SECOND module (the GET route) needed the identical resolution — avoids a stale-model cache-key mismatch between the POST dispatch path and the GET cache-check path"

key-files:
  created:
    - backend/app/ai/explain.py
    - backend/app/api/v1/ai/explain_vuln.py
    - backend/tests/test_ai_explain_stream.py
  modified:
    - backend/app/api/v1/ai/__init__.py

key-decisions:
  - "The leak-marker/injection-flagged check (W3) reads the REAL system_prompt in scope for the current call (first 40 chars of its first line) rather than a hardcoded marker string — generic across every current/future view, not just the vuln prompt's own wording"
  - "Injection-flagged and terminal-validation-failed BOTH surface as the SAME {type:error, kind:grounded_false} SSE event (matching UI-SPEC's own 'validation failure after the retry -> same insufficient-evidence card' state 6) — only the AUDIT status distinguishes them (injection_flagged vs validation_failed), since the frontend has no dedicated injection-flagged UI state and shouldn't need one"
  - "budget_exceeded and rate_limited/no-model-dispatch paths get cost_estimate_usd=0.0 (not None) in their audit row -- explicit zero, not ambiguous-null, since genuinely zero tokens were spent"
  - "Cost-estimate pricing table uses Anthropic's STANDARD (non-promotional) per-MTok rates ($3/$15 Sonnet 5, $5/$25 Opus 5) rather than the $2/$10 introductory Sonnet-5 rate active today (expires 2026-08-31) -- avoids silently under-counting spend against D-06's cap once the promotion lapses; Haiku 4.5's rate is a documented conservative placeholder pending live re-verification (Phase 28's cost dashboard is the authoritative source, not this fail-closed guard)"
  - "The GET cache-check route resolves the tenant's CURRENT model via the same get_model_and_budget() the POST path uses (not a hardcoded default) before computing its cache key -- otherwise a GET issued after an admin changes the connector's model would silently look under the wrong key and always report a false cache miss"

requirements-completed: [AI-02, AI-03, AI-05, AI-06]

# Metrics
duration: 58min
completed: 2026-07-29
---

# Phase 24 Plan 04: The Explain Engine — Buffer-Validate-Retry-Audit-Cache-Replay + Per-Vuln SSE Endpoint Summary

**The buffer-then-validate-then-replay SSE streaming engine and the real per-vuln explain endpoint, proven against the actual installed Anthropic SDK (not just a hand-rolled fake) — closes the tracer's backend half: click Explain, get a validated, cited, cached explanation, with every failure mode (retry, budget, rate-limit, injection, abort) audited and typed.**

## Performance

- **Duration:** ~58 min (includes reading all Phase 24 context/AI-SPEC/RESEARCH/PATTERNS docs, three rounds of live SDK spiking against the real installed `anthropic==0.120.2`, and recovering from an unrelated stash-pop incident — see Issues Encountered)
- **Started:** 2026-07-29T09:34:53Z (approx, immediately after 24-03 completion)
- **Completed:** 2026-07-29T10:09:40Z
- **Tasks:** 2/2 completed
- **Files modified:** 4 (3 created, 1 modified)

## Accomplishments

- **The buffer-then-validate-then-replay contract is proven against the REAL Anthropic SDK, not just our own test double.** Before writing a single line of `explain.py`, three scratchpad spikes ran against the actually-installed `anthropic==0.120.2` package (freshly `pip install -e .`'d into `backend/.venv` — see Issues Encountered) via `httpx.MockTransport`: (1) a full SSE wire-format response parses correctly through `client.messages.stream()` + `await stream.get_final_message()`; (2) `output_config={"format": {"type": "json_schema", ...}, "effort": "low"}` is accepted on the real request without rejection; (3) a mocked 429 raises `RateLimitError` and a mocked 529 raises `OverloadedError` (an `APIStatusError` subclass) specifically on `async with ... as stream:` entry, not on the `.stream()` call itself — directly informing where the engine's own `try/except (RateLimitError, APIStatusError)` needed to wrap. `test_buffer_not_proxy_partial_deltas_never_leak` keeps this real-SDK proof permanently in the test suite (RESEARCH.md's own "reserve MockTransport for one true wire-format test" guidance), asserting none of the six raw Anthropic wire-format event types (`message_start`, `content_block_delta`, etc.) ever appear as an outbound SSE frame — only the buffered, validated `summary_delta`/`done` events do.
- **The retry/audit status vocabulary is reconciled precisely, not just asserted.** Reading the plan's own test descriptions closely resolved an apparent ambiguity: `status="grounded_retry"` fires only when THIS attempt's failure was a self-reported `grounded=false` with a retry still available; `status="validation_failed"` fires for a hard schema/business-rule failure OR for the terminal (no-retries-left) attempt regardless of cause. This reconciliation is directly proven by two tests with different expected status sequences: `grounded=false` then success → `[grounded_retry, ok]`; two hard-malformed responses → `[validation_failed, validation_failed]` (both rows share the SAME status, matching the plan's literal "two audit rows (validation_failed)" wording).
- **The engine's SSE error vocabulary is a genuinely closed, verified set.** `test_error_kind_vocabulary_matches_plan_05_closed_set` forces an unexpected exception path (a broken `build_prompt` callable) and asserts the resulting event is `{type:"error", kind:"unknown"}` — proving the catch-all path emits from the SAME closed `{busy, grounded_false, budget_exceeded, unknown}` set Plan 05's frontend `ExplainStreamState` union expects, with zero orphan kinds. The "no key configured" precondition is deliberately a DIFFERENT, non-error `{"type": "no_key"}` event shape (never audited, since nothing was attempted) — matching D-23's "never an error" framing literally in the wire event's own `type` field, not just its copy.
- **A cache-key mismatch between the POST and GET paths was caught and fixed during Task 2, not left as a latent bug.** The GET cache-check needs to hash/key against the EXACT SAME `(record_hash, model, prompt_version)` tuple the POST path would use — including the tenant's CURRENTLY-configured model. `get_model_and_budget()` was promoted from a private engine-internal helper to a shared, no-underscore export specifically so the GET route reuses the identical resolution logic rather than risking a stale hardcoded default that would silently always report a false cache miss after an admin changes the connector's model.
- **A vacuous-pass test was caught and fixed via the RED-retroactive-verification discipline itself.** Temporarily removing `explain_vuln.py` to verify RED (this phase's established convention from Plan 02) revealed that `test_cross_tenant_finding_id_not_resolvable` PASSED even with the route completely absent — a missing-route 404 is indistinguishable from a correctly-tenant-scoped 404. The test was rewritten to first assert tenant_a's OWN analyst gets 200 for the SAME `finding_id` (via the patched fake engine), then assert tenant_b's analyst gets 404 for it — a genuinely vacuous "route not found" state now fails BOTH assertions, not just the cross-tenant one. Re-verified RED-then-GREEN after the fix.

## Task Commits

Each task followed the full RED → GREEN cycle (plan-level `type: tdd`):

1. **Task 1: The explain engine — buffer, validate, retry-once, audit, cache, replay**
   - `5e0c79d` (test) — RED: `ModuleNotFoundError: No module named 'app.ai.explain'` confirmed before any implementation existed
   - `6b837d5` (feat) — GREEN: 11/11 new tests passing, ruff + mypy clean, 53/53 prior Phase 24 AI tests still green
2. **Task 2: Per-vuln SSE endpoint + cache-check GET + router registration**
   - `c77a684` (test) — RED: route absent → 404s / `AttributeError` confirmed (including catching and fixing one vacuous-pass test along the way, see Accomplishments)
   - `8fd92db` (feat) — GREEN: 16/16 tests in `test_ai_explain_stream.py`, 69/69 across the full Phase 24 AI wave-merge regression, `test_encryption_rotation.py` (19) + `test_connectors/` (41) re-verified green

**Plan metadata:** (this commit, docs: complete plan)

_TDD gate sequence confirmed in git log: `test(24-04)` precedes `feat(24-04)` for both Task 1 and Task 2, in order._

## Files Created/Modified

- `backend/app/ai/explain.py` (484 lines) - `_run_explain_stream()` (the shared engine), `get_model_and_budget()`, `_default_client_factory()` (per-request `AsyncAnthropic`, never a singleton), `_build_output_config()` (omits `effort` for `claude-haiku-4-5` per the Plan-01 finding), `_extract_scanner_data()` (D-18 structural hash-field extraction), `_contains_leak_marker()` (W3), `_estimate_cost_usd()`, `_append_corrective_turn()`, `_audit()` (write + immediate commit per attempt)
- `backend/app/api/v1/ai/explain_vuln.py` (104 lines) - `POST /explain-vuln/{finding_id}` (SSE, `require_analyst`), `GET /explain-vuln/{finding_id}` (cache-check, `require_viewer`), `_allowlisted_hash_fields()` (route-local mirror of the engine's own hash-extraction, for the GET path)
- `backend/app/api/v1/ai/__init__.py` - registers `explain_vuln.router` into `ai_router` via `include_router`
- `backend/tests/test_ai_explain_stream.py` (621 lines, 16 tests) - Task 1: happy path, buffer-not-proxy (real wire-format MockTransport), grounded=false retry, two-malformed-responses terminal, budget fail-closed, no-key inert, abort-releases-guard, rate-limit busy (RateLimitError + APIStatusError), injection-flagged, closed-kind-vocabulary proof. Task 2: analyst POST 200+headers, viewer POST 403, viewer GET cache-check miss+no-dispatch, GET cache-check hit, cross-tenant 404 (contrasted against same-tenant 200)
- `.planning/phases/24-ai-foundation-explain-this-vuln/deferred-items.md` (new) - logs one pre-existing, unrelated full-suite-only pytest flake discovered during the wave-merge regression sweep (see Issues Encountered)

## Decisions Made

- The leak-marker/injection check reads the REAL `system_prompt` in scope for the current call (its first line's first 40 chars) rather than a hardcoded string — generic across every current/future Plan-08 view.
- Injection-flagged and terminal-validation-failed both surface as the identical `{type:error, kind:grounded_false}` SSE event (matching UI-SPEC's "same insufficient-evidence card" state) — only the AUDIT status (`injection_flagged` vs `validation_failed`) distinguishes them; the frontend needs no dedicated injection UI state.
- `budget_exceeded`/`rate_limited` audit rows get `cost_estimate_usd=0.0` explicitly (not `None`) — genuinely zero tokens were spent, not an ambiguous unknown.
- Cost-estimate pricing uses Anthropic's STANDARD, non-promotional per-MTok rates ($3/$15 Sonnet 5, $5/$25 Opus 5) rather than the currently-active $2/$10 introductory Sonnet-5 rate (expires 2026-08-31) — avoids silently under-counting spend against D-06's cap once the promotion lapses; documented as a best-effort estimate for the fail-closed guard, not Phase 28's authoritative cost dashboard.
- `get_model_and_budget()` promoted from private to a shared, no-underscore export the moment the GET route needed the identical resolution the POST path already used internally.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed the missing `anthropic` package into `backend/.venv`**
- **Found during:** Task start (carried forward from 24-02/24-03's flagged blocker)
- **Issue:** `anthropic>=0.120.0` was declared in `backend/pyproject.toml` since Plan 01 but never installed in this local `.venv` — this is the first plan whose code actually imports the SDK.
- **Fix:** Ran `pip install -e ".[dev]"` from `backend/`, matching the Docker build's own install path (`RESEARCH.md`: "the Docker build already runs `pip install -e ".[dev]"`"). Installed `anthropic==0.120.2` (current stable) + its transitive deps (`distro`, `docstring-parser`, `jiter`).
- **Verification:** `python -c "import anthropic; print(anthropic.__version__)"` → `0.120.2`; three scratchpad spikes (SSE parsing, `output_config` request shape, 429/529 exception raising) all ran successfully against the real installed SDK before any engine code was written.
- **Committed in:** N/A (environment-only change, not a tracked file; `pyproject.toml` was untouched since the dependency was already declared).

**2. [Rule 1 - Bug] Fixed a vacuous-pass cross-tenant test caught during RED-retroactive verification**
- **Found during:** Task 2, RED verification (route file temporarily removed)
- **Issue:** `test_cross_tenant_finding_id_not_resolvable` asserted only that a foreign-tenant `finding_id` returns 404 — but a MISSING route also returns 404, so the test passed even with `explain_vuln.py` completely absent, proving nothing about tenant-scoping specifically.
- **Fix:** Rewrote the test to first assert the SAME `finding_id` resolves 200 for its own tenant's analyst (via the patched fake engine), then assert a DIFFERENT tenant's analyst gets 404 for it — a missing route now fails both assertions, not just the cross-tenant one.
- **Files modified:** `backend/tests/test_ai_explain_stream.py`
- **Verification:** Re-ran RED (route absent) → the rewritten test now fails with a genuine `AttributeError` (patch target doesn't exist); restored the route → GREEN, 16/16.
- **Committed in:** `c77a684` (Task 2 RED commit — the rewrite happened before either Task 2 commit landed)

**3. [Rule 3 - Blocking] Recovered from an unrelated stash-pop conflict without data loss**
- **Found during:** Task 1, mid-verification (attempting a before/after mypy comparison)
- **Issue:** A `git stash` / `git stash pop` pair I ran to compare mypy output with/without my new untracked file incorrectly popped an unrelated, pre-existing stash entry (`gsd-reviewfix/12-86112: WIP: BL-01 WR-06 BL-02 WR-04 combined`, unrelated to Phase 24) because `git stash` does not stash untracked files by default — there was nothing of mine actually on the stash stack, so the pop reached further down and produced merge conflicts in three unrelated files (`app/assets/router.py`, `app/ticketing/router.py`, `app/ticketing/service.py`).
- **Fix:** Restored all three conflicted files to their exact HEAD blob via `git checkout HEAD -- <file>` (three targeted, named-file restores — never a blanket reset/clean). The pre-existing stash entry was NEVER popped successfully (git leaves a conflicting pop's stash entry in place) and remains fully intact and untouched in the stash list for whoever owns that unrelated work. Switched all subsequent before/after comparisons to a safe `mv`-based temporary-file-move approach instead of `git stash`.
- **Files modified:** None persisted — the incident was fully reverted; `git diff HEAD` on the three files confirmed byte-identical to HEAD afterward.
- **Verification:** `git status` clean except my own new files; `git stash list` shows all 5 pre-existing entries intact and unchanged.
- **Committed in:** N/A (no commit — the incident left no trace in the final tree).

---

**Total deviations:** 3 auto-fixed (1 blocking dependency install, 1 bug — vacuous test fix, 1 blocking — git incident recovery)
**Impact on plan:** All three are execution-hygiene corrections, not scope changes. The `anthropic` install resolves a blocker flagged by two prior plans exactly as they recommended. The vacuous-test fix strengthens test quality without changing behavior. The stash incident left zero residual changes to the tree (fully reverted, confirmed byte-identical to HEAD) and cost time but no correctness risk — logged here in the interest of complete honesty about the session, not because it affected the shipped code.

## Issues Encountered

- **Pre-existing full-suite-only pytest flake, NOT fixed (out of scope):** `tests/test_connector_health.py::test_scheduler_path_error_message_and_log_are_sanitized` fails ONLY when the entire `tests/` directory (427 tests) is collected together, passing cleanly in isolation (9/9). Confirmed unrelated to this plan (never touches connector scheduler/health/logging code). Logged to `24-ai-foundation-explain-this-vuln/deferred-items.md` per the scope-boundary rule rather than investigated or fixed — matches the same "full-suite-only flake" class already tracked in project memory for the frontend Playwright suite, just newly observed on the backend pytest side.
- **The git-stash incident** (see Deviations #3) cost real time mid-session but left no residual state — documented above for transparency, not because it affected any shipped file.

## User Setup Required

None - no external service configuration required. `GETVUL_DEV_ANTHROPIC_KEY` remains unprovisioned in this environment (flagged since Plan 01); this plan's own tests never require a live Anthropic key (all Anthropic interaction is either a real-SDK-against-MockTransport spike/test, or an injected fake client via the `anthropic_client_factory` test seam).

## Next Phase Readiness

- The tracer's backend half is now genuinely complete and proven end-to-end against a mocked (and, for the one true wire-format test, real-SDK-parsed) Anthropic response: an analyst's POST streams a validated, cited, cached explanation; a viewer's GET reads the cache with zero spend; every failure mode (retry, budget, rate-limit, injection, abort) is typed and audited.
- `_run_explain_stream()` is ready for Plan 08 to reuse UNCHANGED for the host/remediation views — only `build_prompt`, `response_model`, and (optionally) `allowed_source_fields`/`get_prompt_version` need to vary per view; the engine's control flow, retry semantics, audit vocabulary, and cache/inflight wiring are already view-agnostic by construction (D-15/D-16).
- Plan 05 (frontend `use-explain-stream.ts` hook + AI Explanation section) can now build against a REAL backend endpoint rather than a sketch — the SSE event shapes (`no_key`, `error{kind}`, `summary_delta`, `done`) are exactly what Plan 05's own `ExplainStreamState` union already expects, verified by `test_error_kind_vocabulary_matches_plan_05_closed_set`.
- `get_model_and_budget()` is now a shared, importable symbol in `app.ai.explain` — Plan 08's host/remediation routes can reuse it directly for their own GET cache-check routes without re-deriving the resolution logic.
- Postgres + Redis containers (`getvul-postgres-1`, `getvul-redis-1`) were already running at session start and were reused directly; left running for continuity.
- **Outstanding, carried forward (not blocking):** the Haiku `effort` live smoke-test (RESEARCH Pitfall 1 / Plan 01's own flagged gap) still has not run against a real Anthropic key in this environment — `_build_output_config()` already implements the documented mitigation (omit `effort` for `claude-haiku-4-5`) defensively, but this remains unverified against a live API call. `GETVUL_DEV_ANTHROPIC_KEY` provisioning is still the action item for whichever future plan first has access to a real key.

## Self-Check: PASSED

- Files verified present: `backend/app/ai/explain.py`, `backend/app/api/v1/ai/explain_vuln.py`, `backend/app/api/v1/ai/__init__.py`, `backend/tests/test_ai_explain_stream.py` (4/4 found)
- Commits verified present in `git log`: `5e0c79d`, `6b837d5`, `c77a684`, `8fd92db` (4/4 found)
- TDD gate sequence confirmed: `test(24-04)` precedes `feat(24-04)` for both Task 1 and Task 2, in order
- Plan's own `<verification>` re-run and green: `pytest tests/test_ai_explain_stream.py -q` → 16/16; wave-merge (`test_ai_schemas/prompt_builder/audit/cache_isolation/budget.py`) → 53/53, combined 69/69
- Acceptance-criteria greps re-confirmed: `explain.py` shows `get_final_message` (2 occurrences), `StreamingResponse(client` (0 occurrences — no raw passthrough); `explain_vuln.py` shows `text/event-stream` (1 occurrence); `__init__.py` shows `include_router` (2 occurrences)
- Regression sweep green: `test_encryption_rotation.py` (19/19) + `test_connectors/` (41/41) re-verified
- ruff + mypy clean on all 3 new/modified non-test source files (the only mypy findings anywhere in `app/` are the same pre-existing, already-baselined errors in unrelated files noted by every prior Phase 24 plan)
- Full `tests/` suite run once for a broader safety check: 426/427 passed; the one failure (`test_connector_health.py`) confirmed pre-existing/unrelated and a full-suite-only flake (passes 9/9 in isolation) — logged to `deferred-items.md`, not fixed

---
*Phase: 24-ai-foundation-explain-this-vuln*
*Completed: 2026-07-29*
