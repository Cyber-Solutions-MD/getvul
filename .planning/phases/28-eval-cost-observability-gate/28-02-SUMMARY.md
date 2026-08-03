---
phase: 28-eval-cost-observability-gate
plan: 02
subsystem: testing
tags: [pytest, prompt-injection, red-team, budget-guard, anthropic, keyless-ci, fail-closed]

# Dependency graph
requires:
  - phase: 28-01
    provides: keyless DeepEval golden-eval harness precedent (deepeval dep, tests/evals/ package shape) — no direct code dependency, same phase's sibling CI-blocking gate
provides:
  - Consolidated keyless prompt-injection red-team suite (backend/tests/test_ai_injection_redteam.py) — 17-payload adversarial corpus x 5 AI capabilities = 85 parametrized cases
  - No-bypass AI budget coverage gate (backend/tests/test_ai_budget_coverage.py) — proves the fail-closed budget guard is unreachable-past on all 5 explain routes + the batch path
  - Removal of the 5 superseded single-payload injection tests from 4 pre-existing prompt-builder test files
affects: [28-05 (CI wiring — ai-redteam-injection job), 28-03, 28-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "JSON round-trip assertion (parse the <scanner_data> body, compare the poisoned field's parsed value to the raw payload) instead of raw substring search against the JSON-encoded text — correctly handles quote/backslash/newline/non-ASCII payload content that json.dumps' default ensure_ascii=True/escaping would otherwise falsify a naive substring check against"
    - "Regression-gate control test (under-budget companion asserting the SAME patched mock IS constructed) alongside a no-bypass coverage test, so the coverage assertion is provably falsifiable, not tautological"
    - "Scoped no-op patch of a background scheduler dispatch function (app.connectors.scheduler._dispatch_ai_batch_prewarm) inside a specific test, rather than touching production code, to neutralize a process-global-state race against a per-test app lifespan"

key-files:
  created:
    - backend/tests/test_ai_injection_redteam.py
    - backend/tests/test_ai_budget_coverage.py
  modified:
    - backend/tests/test_ai_prompt_builder.py
    - backend/tests/test_ai_prompt_builder_host.py
    - backend/tests/test_ai_prompt_builder_remediation_guidance.py
    - backend/tests/test_ai_prompt_builder_prioritization.py
    - .planning/phases/28-eval-cost-observability-gate/deferred-items.md

key-decisions:
  - "Adversarial corpus finalized at 17 payloads (4 ignore-instructions + 4 system-prompt-extraction + 3 tag/delimiter-breakout + 4 role-play/jailbreak + 2 unicode-obfuscation) x 5 capabilities = 85 cases, comfortably above the >=75 floor"
  - "Positive-containment assertion uses json.loads(inner)[field] == payload (round-trip equality), not a raw substring search on the encoded text — a raw substring check would give false negatives for any payload containing a quote, backslash, or non-ASCII character, since json.dumps' default ensure_ascii=True escapes exactly those; verified this divergence from RESEARCH Pattern 3's own illustrative code empirically before finalizing"
  - "AIE-02/AIE-03 left [ ] Pending in REQUIREMENTS.md, mirroring the AIE-01/Plan-01 precedent — both gates' own requirement wording ('runs as a separate CI check' / D-04's 'enforced as a CI gate') isn't satisfied until Plan 05 wires the ai-redteam-injection CI job; the gates exist and pass standalone today"
  - "Test A's regression control (under-budget, asserting the same patched mock_cls.call_count >= 1) is included per the plan's REGRESSION GATE acceptance criterion, proving the over-budget call_count == 0 assertion is genuinely falsifiable"

requirements-completed: []  # AIE-02/AIE-03 intentionally NOT marked complete — see key-decisions; both gates exist and pass but their own requirement wording needs Plan 05's CI wiring first (AIE-01 precedent)

# Metrics
duration: 32min
completed: 2026-08-03
---

# Phase 28 Plan 02: Keyless Red-Team + No-Bypass Budget Coverage Summary

**Two keyless CI-blocking backend gates: a consolidated 17-payload x 5-capability prompt-injection red-team suite (85 parametrized cases) and a no-bypass budget coverage test proving the fail-closed guard is unreachable-past on all 5 explain routes plus the batch path — both proven zero-model-call, with a found-and-fixed background-scheduler race that would have made the coverage gate flaky.**

## Performance

- **Duration:** ~32 min
- **Started:** 2026-08-03T08:01:00Z (approx, immediately following 28-01)
- **Completed:** 2026-08-03T08:33:39Z
- **Tasks:** 2 completed
- **Files modified:** 7 (2 created, 4 modified test files, 1 deferred-items.md)

## Accomplishments

- **AIE-02 (consolidated keyless red-team, `backend/tests/test_ai_injection_redteam.py`):** A 17-entry adversarial payload corpus (ignore-previous-instructions variants, system-prompt-extraction attempts, tag/delimiter-breakout attempts including a literal `</scanner_data>` substring, role-play/jailbreak framings, and unicode-obfuscation payloads — zero-width-space and Cyrillic/Greek homoglyphs) crossed with all 5 `build_explain_*_prompt` capabilities (vuln/host/remediation/remediation_guidance/prioritization) = 85 parametrized cases, all green with zero model calls, zero network access. Every case proves the payload is absent from the system prompt, present (via exact JSON round-trip, not a fragile raw substring match) inside the `<scanner_data>` block, and that an embedded literal `</scanner_data>` never breaks the real tag boundary.
- **Consolidation cleanup:** The 5 now-superseded single-payload `test_injection_isolation`-style functions were removed from the 4 files that previously scattered them (`test_ai_prompt_builder.py`; `test_ai_prompt_builder_host.py`, which held both the host and remediation variants; `test_ai_prompt_builder_remediation_guidance.py`; `test_ai_prompt_builder_prioritization.py`). Every other test and helper factory in those 4 files is untouched — the sibling suites still pass in full (135 tests green across the 5 files together).
- **AIE-03 (no-bypass budget coverage, `backend/tests/test_ai_budget_coverage.py`):** Test A patches the module-local `app.ai.explain.AsyncAnthropic` (the name `_default_client_factory` actually constructs) across all 5 explain routes (vuln/host/remediation/remediation-guidance/prioritization — remediation keyed by a CVE-ID string, the other 4 by UUID) and proves zero client construction when the tenant is over its monthly cap, paired with an under-budget regression control proving the same patched name IS constructed when the guard passes (so the over-budget assertion is genuinely falsifiable, not tautological — deleting the budget-guard call would flip it to `>= 1` and fail). Test B injects a recording fake via `run_batch_prewarm`'s documented `anthropic_client_factory=` DI seam and proves the batch path's construct-then-count-then-gate asymmetry: the client and the free `count_tokens()` pre-estimate both legitimately run before the gate (needed to compute the estimate the gate decides on), but the BILLED `client.messages.batches.create()` dispatch is never reached over budget — zero real Anthropic network calls anywhere in either test.
- **Found and fixed a genuine test-reliability bug** while verifying Test A against live Postgres+Redis: the background AI batch-prewarm scheduler (`app.connectors.scheduler`) gates its dispatch on a module-level, process-global "first tick" flag, which races the `client` fixture's real per-test `create_app()` + lifespan and can spuriously construct a client through the same patched name the coverage test observes. Neutralized locally (patched `app.connectors.scheduler._dispatch_ai_batch_prewarm` to a no-op for the affected tests' duration) rather than touching production code; logged as a deferred item with a residual benign artifact noted. Verified stable over 3 consecutive full clean reruns post-fix.

## Task Commits

Each task was committed atomically:

1. **Task 1: Consolidated keyless prompt-injection red-team suite (AIE-02)** - `53086f4` (test)
2. **Task 2: No-bypass budget coverage test (AIE-03)** - `77e3a50` (test)

**Plan metadata:** (this commit) `docs(28-02): complete keyless red-team + budget coverage plan`

## Files Created/Modified

- `backend/tests/test_ai_injection_redteam.py` - New consolidated keyless red-team suite: 17-payload corpus x 5 capabilities = 85 parametrized cases
- `backend/tests/test_ai_budget_coverage.py` - New no-bypass budget coverage suite: Test A (5 explain routes, with regression control) + Test B (batch path via DI seam)
- `backend/tests/test_ai_prompt_builder.py` - Removed the superseded `test_injection_isolation` function; all other tests/factories intact
- `backend/tests/test_ai_prompt_builder_host.py` - Removed the superseded `test_host_injection_isolation_stays_inside_scanner_data` and `test_remediation_injection_isolation` functions; all other tests/factories intact
- `backend/tests/test_ai_prompt_builder_remediation_guidance.py` - Removed the superseded `test_injection_isolation` function; all other tests/factories intact
- `backend/tests/test_ai_prompt_builder_prioritization.py` - Removed the superseded `test_injection_isolation` function; all other tests/factories intact
- `.planning/phases/28-eval-cost-observability-gate/deferred-items.md` - Logged the scheduler-race finding (28-02) and its local fix + residual benign artifact

## Decisions Made

- **17-payload corpus, 5 categories:** 4 ignore-instructions + 4 system-prompt-extraction + 3 tag/delimiter-breakout (one containing a literal `</scanner_data>`) + 4 role-play/jailbreak + 2 unicode-obfuscation (zero-width space, Cyrillic/Greek homoglyphs) = 17 x 5 capabilities = 85 cases, comfortably above the plan's `>= 75` floor.
- **JSON round-trip assertion over raw substring search:** the positive-containment check parses the extracted `<scanner_data>` JSON body and asserts `parsed[field] == payload` (exact equality) rather than a raw `payload in user_text` substring search. Verified empirically that the raw-substring approach (matching RESEARCH Pattern 3's own illustrative code) silently gives false negatives for any payload containing a double-quote, backslash, or non-ASCII character, since `json.dumps`'s default `ensure_ascii=True` escapes exactly those into `\"`/`\\`/`\uXXXX` sequences in the encoded output — this let the corpus include genuine unicode obfuscation and realistic quote-bearing payloads (e.g. a fake JSON-injection attempt) without a brittle assertion.
- **AIE-02/AIE-03 left `[ ]` Pending in REQUIREMENTS.md:** both requirements' own wording ("runs as a separate CI check, alongside semgrep/ZAP" for AIE-02; D-04's "enforced as a CI gate" for AIE-03) isn't satisfied until Plan 05 wires the `ai-redteam-injection` CI job — mirroring the AIE-01/Plan-01 precedent already established this phase. Both gates exist and pass standalone as of this plan.
- **Regression-gate control test included for Test A:** per the plan's explicit acceptance criterion, an under-budget companion test proves the same patched `mock_cls` IS constructed when the guard passes, so the over-budget `call_count == 0` assertion is provably falsifiable (deleting the budget check would flip it, not silently stay green).
- **Batch-path assertion targets the billed dispatch, not client construction:** Test B does NOT assert zero client constructions for the batch path (that would be false — the client legitimately IS built and `count_tokens()` legitimately IS called before the gate, per the construct-then-count-then-gate nuance) — it asserts zero `batches_created` (the actual billed `.batches.create()` call), which is the correct invariant.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1/3 - Bug/Blocking] Background AI batch-prewarm scheduler races the `client` fixture's per-test app lifespan, flaking Test A**

- **Found during:** Task 2, first live run of `test_ai_budget_coverage.py` against Postgres+Redis (`test_over_budget_never_constructs_anthropic_client[remediation-...]` failed with `mock_cls.call_count == 1` instead of `0`).
- **Issue:** `app/connectors/scheduler.py::_dispatch_ai_batch_prewarm()` gates its dispatch of `run_batch_prewarm()` on a module-level global (`_last_ai_batch_prewarm`), not per-app-instance state. Its first tick per Python process fires unconditionally. Since pytest shares one event loop for the whole session and the `client` fixture starts a REAL `create_app()` + lifespan (a fresh background scheduler task) per test, that one process-wide first tick can land — non-deterministically — during any test whose own `app.ai.explain.AsyncAnthropic` patch and seeded ANTHROPIC connector happen to be active at that moment, causing the scheduler's own real `run_batch_prewarm()` to independently construct a client through the same patched name.
- **Fix:** Both Test A functions (over-budget and its under-budget regression control) additionally patch `app.connectors.scheduler._dispatch_ai_batch_prewarm` to a no-op (`AsyncMock`) for their full duration. No production code was touched — this is a test-only mitigation of a test-harness timing hazard, not a fix to `scheduler.py` itself (which behaves reasonably outside a shared-loop, per-test-app-instance harness).
- **Files modified:** `backend/tests/test_ai_budget_coverage.py`
- **Verification:** Re-ran the full `test_ai_budget_coverage.py` suite 4 times post-fix (11/11 passed every time); also ran the full `tests/test_ai_*.py` + `tests/evals/` sweep (331/331 passed) and a whole-suite `--collect-only` (724 tests collected, matching 633 baseline + 80 net-new red-team + 11 new coverage).
- **Committed in:** `77e3a50` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1/3 — test-reliability bug in the new coverage test's own interaction with pre-existing background-scheduler architecture)
**Impact on plan:** Necessary for the coverage gate to be genuinely deterministic-green (a flaky CI-blocking gate is worse than no gate). No scope creep — fixed entirely inside the new test file; zero production code touched. A residual, non-fatal, intermittent `SAWarning` from the same root cause is logged in `deferred-items.md` as out-of-scope (never fails a test, not reproduced under `-W error`).

## Issues Encountered

- **mypy on new test files:** running `mypy` directly against the two new test files surfaces pre-existing project-wide errors (unrelated files pulled in transitively) plus one real, expected arg-type mismatch (the recording fakes aren't subclasses of the real `AsyncAnthropic`/SDK types) — but confirmed this project's actual CI mypy gate is scoped to `mypy app/` only (`.github/workflows/ci.yml`), never `tests/`, and the identical mismatch is already present, unaddressed, in the pre-existing `test_ai_batch.py`. No action needed; not a new gap.
- Both new files are `ruff format --check`-clean and `ruff check`-clean (the actual CI-enforced gates for `tests/`).

## User Setup Required

None - no external service configuration required. Both gates run keylessly (Task 1) or against the already-provisioned local Postgres+Redis (Task 2) with zero new environment variables.

## Next Phase Readiness

- AIE-02 and AIE-03's gates exist, pass green, and are ready to be wired into the `ai-redteam-injection` CI job — Plan 05's job.
- Plan 03/04 (AIE-04's usage/cost UI) can proceed independently — no dependency on this plan's test files.
- Backend regression is fully clean: `pytest --collect-only` reports 724/724 tests collected (up from 633 pre-plan), full `tests/test_ai_*.py` + `tests/evals/` sweep 331/331 green, `ruff check .`/`ruff format --check .` clean on every touched file.

---
*Phase: 28-eval-cost-observability-gate*
*Completed: 2026-08-03*

## Self-Check: PASSED

All 8 claimed files verified present on disk (2 new test files, 4 modified prompt-builder test files, deferred-items.md, this summary). All 3 claimed commit hashes (`53086f4`, `77e3a50`, `908fc74`) verified present in `git log --oneline --all`.
