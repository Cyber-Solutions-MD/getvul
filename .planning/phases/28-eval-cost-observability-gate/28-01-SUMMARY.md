---
phase: 28-eval-cost-observability-gate
plan: 01
subsystem: testing
tags: [deepeval, pytest, eval-harness, ai, pydantic, keyless-ci]

# Dependency graph
requires:
  - phase: 24-ai-foundation-explain-this-vuln
    provides: ExplainResponseBase/ExplainVulnResponse/ExplainHostResponse/ExplainRemediationResponse schemas, recheck_business_rules(), VULN_ALLOWLIST/HOST_ALLOWLIST/REMEDIATION_ALLOWLIST + their build_explain_*_prompt() builders, _build_output_config()
  - phase: 25-asset-aware-remediation-guidance
    provides: ExplainRemediationGuidanceResponse schema, REMEDIATION_GUIDANCE_ALLOWLIST + build_explain_remediation_guidance_prompt(), has_actionable_remediation_text() D-01 gate semantics
  - phase: 26-prioritization-narrative
    provides: ExplainPrioritizationResponse (no-rank schema), PRIORITIZATION_ALLOWLIST + build_explain_prioritization_prompt()
provides:
  - "backend/tests/evals/ package: 5 keyless non-LLM DeepEval metrics + a parametrized golden-fixture eval test"
  - "10 committed, hand-authored synthetic golden fixtures (2 per capability x 5 capabilities)"
  - "backend/scripts/capture_ai_goldens.py: documented one-time dev-key capture mechanism (D-07)"
  - "deepeval==4.1.5 pinned backend dev dependency"
affects: [28-02-red-team-injection, 28-05-ci-wiring]

# Tech tracking
tech-stack:
  added: ["deepeval==4.1.5"]
  patterns:
    - "Non-LLM DeepEval BaseMetric: pure-Python measure()/a_measure()/is_successful()/__name__, zero evaluation_model/network/API key"
    - "Metrics call production validation gates directly (ExplainResponseBase.model_validate_json/recheck_business_rules) instead of re-implementing them"
    - "Golden-fixture JSON shape: {grounding_record, schema_name, model_response, model_used, captured_at, capture_method, note}"
    - "Hand-authored-fixture fallback when a dev key is absent: same grounding_record hardcoded in both the capture script and the committed fixture, so a future real capture run overwrites with identical inputs"

key-files:
  created:
    - backend/scripts/capture_ai_goldens.py
    - backend/tests/evals/__init__.py
    - backend/tests/evals/metrics.py
    - backend/tests/evals/test_golden_evals.py
    - backend/tests/evals/goldens/{vuln,host,remediation,remediation_guidance,prioritization}/{grounded,insufficient_evidence}.json
  modified:
    - backend/pyproject.toml
    - .gitignore

key-decisions:
  - "Fixtures hand-authored (not dev-key-captured): GETVUL_DEV_ANTHROPIC_KEY confirmed absent in this environment (matches STATE.md's Phase 24-01 blocker) -- each fixture passes the identical model_validate_json()+recheck_business_rules() gates the capture script itself enforces"
  - "SchemaValidMetric/GroundingTraceabilityMetric call production schemas.py functions directly, never re-implement validation logic (T-28-07)"
  - "CiteOrRefuseMetric operates on raw parsed JSON, independent of citations: Field(..., min_length=1), since Anthropic's structured-output translator can strip array-length constraints before they reach the model"
  - "NoOwnerPiiMetric's OWNER_PII_SENTINELS scoped to the literal excluded field names (directory_user/assigned_user/managed_by/serial_number/building) already precedented in test_ai_prompt_builder_host.py, mirroring safety.py's small-known-set reasoning"
  - "AIE-01 left [ ] Pending in REQUIREMENTS.md -- its own wording ('...runs in CI...') isn't satisfied until Plan 05 wires the ai-evals CI job; mirrors the AID-01 (Phase 27) precedent of holding a multi-plan requirement open until the final contributing plan lands"

patterns-established:
  - "Keyless DeepEval custom metric: subclass BaseMetric, store every __init__ parameter under an IDENTICAL attribute name (DeepEval's own copy_metrics() reconstructs via metric_class(**vars(metric)) matched against __init__'s signature)"
  - "Per-file narrow mypy suppression for third-party typing looseness (# mypy: disable-error-code=\"...\"), documented inline, never project-wide"

requirements-completed: []

# Metrics
duration: 45min
completed: 2026-08-03
---

# Phase 28 Plan 01: DeepEval Keyless Golden-Eval Harness Summary

**A keyless DeepEval structural eval harness — 5 non-LLM metrics calling production schema/business-rule gates directly, run against 10 hand-authored synthetic golden fixtures — proving schema/grounding/no-rank/no-PII/cite-or-refuse with zero model calls.**

## Performance

- **Duration:** ~45 min (approximate)
- **Started:** 2026-08-03T07:13:41Z
- **Completed:** 2026-08-03T07:58:41Z
- **Tasks:** 2 (Task 2 executed as TDD: RED then GREEN)
- **Files modified:** 17 (15 created, 2 modified)

## Accomplishments

- Pinned `deepeval==4.1.5` as a backend dev dependency (exact-pin-with-comment convention matching ruff/mypy) and verified it imports cleanly
- Built `backend/scripts/capture_ai_goldens.py`: the documented, one-time, dev-key-only golden-fixture capture mechanism (D-07), reusing the real `build_explain_*_prompt()` + `_build_output_config()` + `model_validate_json()`/`recheck_business_rules()` production code paths
- Hand-authored and committed 10 synthetic golden fixtures (2 per capability x 5 capabilities), since `GETVUL_DEV_ANTHROPIC_KEY` is confirmed absent in this environment — every fixture passes the exact same production gates the capture script itself enforces
- Implemented 5 non-LLM `BaseMetric` subclasses (`SchemaValidMetric`, `GroundingTraceabilityMetric`, `NoRankInvariantMetric`, `NoOwnerPiiMetric`, `CiteOrRefuseMetric`) — two call production validation gates directly, all five are pure Python with zero model calls
- Ran genuine RED→GREEN TDD: RED = real `ModuleNotFoundError` collection failure before `metrics.py` existed; GREEN = `deepeval test run tests/evals/test_golden_evals.py` passing 10/10 fixtures keyless, exit 0
- Found and fixed a real DeepEval framework gotcha via direct execution (not assumed from docs): `copy_metrics()` reconstructs each metric per test case via `metric_class(**vars(metric))` matched against `__init__`'s own parameter names
- Demonstrated the no-rank gate genuinely discriminates: a deliberately-corrupted fixture (extra `"priority": 5` key, temp copy only, never committed) makes `NoRankInvariantMetric` score 0.0/fail, while the real committed fixture still scores 1.0

## Task Commits

Each task was committed atomically (Task 2 as a strict TDD RED→GREEN pair):

1. **Task 1: deepeval dep + capture script + 10 committed golden fixtures** - `9cd1004` (feat)
2. **Task 2 RED: add failing golden eval test for structural metrics** - `f4a3e08` (test)
3. **Task 2 GREEN: implement 5 keyless structural eval metrics** - `77b79dd` (feat)

_TDD Gate Compliance: `test(...)` commit (`f4a3e08`) precedes the `feat(...)` commit (`77b79dd`) — RED then GREEN, no REFACTOR commit needed (implementation was already clean after the one attribute-name fix made during GREEN)._

## Files Created/Modified

- `backend/pyproject.toml` - added `deepeval==4.1.5` to `[project.optional-dependencies].dev`, pinned with a comment
- `backend/scripts/capture_ai_goldens.py` - one-time dev-key capture script; 10 `CaptureRow` entries (hand-authored synthetic `grounding_record`s), a minimal non-streaming `AsyncAnthropic.messages.create()` call, validated through the same two production gates the real engine uses
- `backend/tests/evals/__init__.py` - empty (0 bytes) package marker so `test_golden_evals.py`'s relative `from .metrics import ...` resolves
- `backend/tests/evals/metrics.py` - the 5 structural metrics
- `backend/tests/evals/test_golden_evals.py` - parametrized `assert_test()` suite over all 10 goldens x 5 metrics
- `backend/tests/evals/goldens/{vuln,host,remediation,remediation_guidance,prioritization}/{grounded,insufficient_evidence}.json` - 10 committed fixtures, each `{grounding_record, schema_name, model_response, model_used: null, captured_at, capture_method: "hand_authored", note}`
- `.gitignore` - added `.deepeval/` (DeepEval's local telemetry/cache directory)
- `.planning/phases/28-eval-cost-observability-gate/deferred-items.md` - logged 3 pre-existing, out-of-scope ruff-format-drift files found during the regression sweep

## Decisions Made

- Fixtures hand-authored (not dev-key-captured): `GETVUL_DEV_ANTHROPIC_KEY` confirmed absent (`echo`'d empty; matches STATE.md's documented Phase 24-01 blocker). Each hand-authored fixture reuses the identical `grounding_record` already hardcoded in `capture_ai_goldens.py`'s `CAPTURE_ROWS`, so a future real capture run with a dev key overwrites these exact paths with genuinely model-authored responses using the same inputs.
- `SchemaValidMetric`/`GroundingTraceabilityMetric` call `ExplainResponseBase.model_validate_json()`/`recheck_business_rules()` directly — never re-implemented — so the eval can't silently drift from what production enforces (T-28-07, grep-provable: `grep -v '^#' metrics.py | grep -c recheck_business_rules` = 4).
- `NoOwnerPiiMetric`'s `OWNER_PII_SENTINELS` scoped to the literal excluded field names (`directory_user`/`assigned_user`/`managed_by`/`serial_number`/`building`) already precedented in `test_ai_prompt_builder_host.py`'s own PII-exclusion test — mirrors `safety.py`'s "small known set, not a live-interceptor-evading adversary" reasoning rather than a full PII-detection model.
- `CiteOrRefuseMetric` operates on the raw parsed JSON (not the Pydantic-validated object), independent of `citations: Field(..., min_length=1)` — Anthropic's structured-output schema translator can strip array-length constraints before they reach the model (AI-SPEC Pitfall 4), so this metric proves the cite-or-refuse invariant on its own terms.
- `test_golden_evals.py` uses `from deepeval import assert_test` (the doc-sanctioned public API, matching 28-RESEARCH.md's Pattern 2 exactly) rather than the internal `deepeval.evaluate.evaluate` module path — the former trips `mypy --strict`'s `attr-defined` check, but CI's actual `mypy app/` gate never type-checks `tests/`, so this has zero effect on any real gate.
- AIE-01 intentionally left `[ ]` Pending in `REQUIREMENTS.md`: its own wording ("...runs in CI...") isn't satisfied until Plan 05 wires the `ai-evals` CI job (this plan's own `<output>` text says as much: "Feeds Plan 05's `ai-evals` CI job"). Mirrors the AID-01 (Phase 27) precedent of holding a multi-plan requirement open until the final contributing plan lands, rather than mechanically flipping the checkbox because this plan's frontmatter lists the requirement.

**mypy-baseline handling for deepeval:** `mypy app/` (`ci.yml`'s actual CI-blocking scope) never type-checks `backend/tests/`, so no `mypy-baseline.txt` entries were needed for any new file in this plan. A local, informational `mypy --strict` run against the 2 new eval files surfaced exactly 2 classes of DeepEval-typing-looseness friction in `metrics.py` — `no-untyped-call` (DeepEval's own `BaseMetric.__init_subclass__` hook is itself untyped) and `operator` (`BaseMetric` declares `threshold`/`score` as `Optional[float]`, so a subclass's own `>=` comparison trips under strict mode) — both narrowly suppressed via one file-scoped `# mypy: disable-error-code="no-untyped-call, operator"` directive, documented inline per 28-RESEARCH.md Pitfall 7. After adding this directive, `mypy --strict tests/evals/metrics.py` reports zero issues. `test_golden_evals.py` still trips one `attr-defined` error on `from deepeval import assert_test` (deepeval's dynamic re-export isn't statically resolvable) — left unsuppressed since it isn't CI-gated and matches the plan's own recommended import.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed a real DeepEval `copy_metrics()` attribute-name mismatch in `SchemaValidMetric`**
- **Found during:** Task 2 GREEN-phase verification (first `deepeval test run` attempt — all 10 fixtures failed)
- **Issue:** `SchemaValidMetric.__init__` stored the schema-name string as `self.response_model_name`, but DeepEval's internal `copy_metrics()` (`deepeval/metrics/utils.py`) reconstructs a fresh metric instance per test case via `metric_class(**vars(metric))`, filtered to whatever names appear in `__init__`'s OWN signature (`response_model`). Since the stored attribute name didn't match, reconstruction raised `TypeError: SchemaValidMetric.__init__() missing 1 required positional argument: 'response_model'` for every one of the 10 parametrized cases.
- **Fix:** Renamed the stored attribute to `self.response_model` (identical to the constructor parameter name), with an inline comment documenting the gotcha for future metric authors in this file.
- **Files modified:** `backend/tests/evals/metrics.py`
- **Verification:** `deepeval test run tests/evals/test_golden_evals.py` went from 10 failed to 10 passed (exit 0).
- **Committed in:** `77b79dd` (Task 2 GREEN commit)

**2. [Rule 3 - Blocking] Added `.deepeval/` to `.gitignore`**
- **Found during:** Task 1, post-smoke-test `git status` check
- **Issue:** Running `deepeval test run` (both an isolated smoke test and the real verification runs) from `backend/` creates a local `backend/.deepeval/` cache directory (result/telemetry cache), which surfaced as untracked.
- **Fix:** Added `.deepeval/` to the root `.gitignore`, mirroring the existing `.pytest_cache/` entry.
- **Files modified:** `.gitignore`
- **Verification:** `git status --short` no longer lists `backend/.deepeval/`.
- **Committed in:** `9cd1004` (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking/housekeeping)
**Impact on plan:** Both fixes were necessary for the harness to actually run green and for the repo to stay clean of generated artifacts. No scope creep.

## Issues Encountered

- Pre-existing `ruff format --check` drift in 3 files unrelated to this plan (`backend/tests/test_ai_explain_remediation_guidance.py`, `backend/tests/test_ai_schemas.py`, `backend/tests/test_connectors/test_rapid7_connector.py`), discovered during the full-backend regression sweep. Confirmed untouched by this plan (`git log`/`git status` show their last-touching commits predate Phase 28: 26-01/25-02/23-01). Logged to `.planning/phases/28-eval-cost-observability-gate/deferred-items.md`, not fixed (out of scope per the executor's scope-boundary rule).

## User Setup Required

None — no external service configuration required. `GETVUL_DEV_ANTHROPIC_KEY` is optional and only needed if/when a developer chooses to re-run `backend/scripts/capture_ai_goldens.py` to replace the hand-authored fixtures with genuinely model-captured ones.

## Next Phase Readiness

- The AIE-01 harness is complete and CI-blocking-ready: `deepeval test run tests/evals/test_golden_evals.py` is green, keyless (no `ANTHROPIC_API_KEY` anywhere in the run env), over all 10 fixtures, exit 0. Ready for Plan 05 to wire it into `.github/workflows/ci.yml` as the `ai-evals` job and into `.github/branch-protection.json`'s required-checks list (per 28-PATTERNS.md's Verification Correction #4 — a workflow job alone doesn't make it merge-blocking on this repo).
- No blockers for Plan 02 (AIE-02 red-team suite, wave 1, `depends_on: []`) — it shares no files with this plan.
- Full backend regression confirmed clean: `pytest --collect-only` (633 tests, 0 errors), `test_ai_schemas.py` (18 passed), the 4 prompt-builder test files (55 passed), `ruff check .` (0 issues) all green after this plan's changes.
- Future follow-up (not a blocker): if a developer obtains a `GETVUL_DEV_ANTHROPIC_KEY`, running `python scripts/capture_ai_goldens.py` will overwrite all 10 hand-authored fixtures with genuinely model-captured ones, using the identical `grounding_record`s already committed.

---
*Phase: 28-eval-cost-observability-gate*
*Completed: 2026-08-03*

## Self-Check: PASSED

All 17 claimed files verified present on disk (`backend/pyproject.toml`, `backend/scripts/capture_ai_goldens.py`, `backend/tests/evals/{__init__.py,metrics.py,test_golden_evals.py}`, all 10 `backend/tests/evals/goldens/**/*.json` fixtures, this SUMMARY.md, `deferred-items.md`, `.gitignore`). All 4 claimed commit hashes verified present in `git log` (`9cd1004`, `f4a3e08`, `77b79dd`, `1b64996`).
