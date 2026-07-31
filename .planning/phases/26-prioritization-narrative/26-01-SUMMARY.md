---
phase: 26-prioritization-narrative
plan: 01
subsystem: api
tags: [pydantic, sqlalchemy, ai-grounding, prioritization, tenant-isolation]

# Dependency graph
requires:
  - phase: 24-ai-foundation-explain-this-vuln
    provides: ExplainResponseBase (the 4-field, zero-numeric-field shared schema base) + the tenant-scoped grounding-query pattern
  - phase: 25-asset-aware-remediation-guidance
    provides: get_remediation_guidance_context() + ExplainRemediationGuidanceResponse — the closest structural analog mirrored line-for-line
provides:
  - get_prioritization_context(db, tenant_id, finding_id) — the 5th grounding-query quadruplet member (D-04 factors + cve_id + Asset.department, PII-excluded)
  - ExplainPrioritizationResponse(ExplainResponseBase) — the zero-new-fields, structurally-no-rank-possible schema class
affects: [26-02-prompt-builder, 26-03-route-registration, 26-04-frontend-no-rank-ui, 26-05-tracer-gate]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "5th grounding/schema quadruplet member (vuln/host/remediation/remediation-guidance/prioritization) added to the same two files, mirroring the immediately-prior Phase 25 pair almost line-for-line"
    - "Owner-PII exclusion extended one step further: department is the first field this module deliberately SELECTs (every prior grounding fn only ever excludes owner columns; this one names the one allowed exception)"
    - "No-rank enforcement via type structure, not runtime validation: the base class (ExplainResponseBase) has zero numeric fields, so a rank/priority/score field cannot be added to a subclass without a reviewable diff to the shared base"

key-files:
  created:
    - backend/tests/test_ai_grounding_prioritization.py
  modified:
    - backend/app/ai/grounding.py
    - backend/app/ai/schemas.py
    - backend/tests/test_ai_schemas.py

key-decisions:
  - "get_prioritization_context() returns exactly 10 keys (D-04's 8 factor columns + cve_id + department) — no more, no less; verified by set-equality assertion, not just presence checks"
  - "ExplainPrioritizationResponse docstring deliberately avoids the literal substrings 'priority'/'rank'/'score'/'ai_score' in its own class-block prose (unlike prose in this SUMMARY or the test file) to satisfy the plan's own grep-based T-26-02 acceptance check scoped to that block region"
  - "Owner-PII exclusion docstring convention followed exactly as get_asset_posture()/get_remediation_guidance_context() already establish: the excluded PII column names appear in the new function's OWN docstring (not just the module docstring) — this is expected, established precedent, not a violation of the 'no PII names inside the function' acceptance criterion (which targets the SELECT/query code, not explanatory prose)"

patterns-established:
  - "T-26-01 mitigation: owner-PII columns (assigned_user/managed_by/building/serial_number) are excluded at the SQL SELECT layer, never merely filtered downstream — proven by a positive negative-assertion test on the returned dict's keys, not just by inspecting the query"
  - "T-26-02 mitigation: the 'no AI rank' contract is enforced by class structure (subclassing a base with no numeric field) rather than a runtime check — a rank field would require editing ExplainResponseBase itself, which every other response variant also inherits"

requirements-completed: [AIP-01]

# Metrics
duration: 12min
completed: 2026-07-31
---

# Phase 26 Plan 01: Prioritization Grounding + No-Rank Schema Summary

**Tenant-scoped `get_prioritization_context()` grounding query (D-04's 8 factors + cve_id + Asset.department, owner-PII excluded at the SELECT) and the zero-field `ExplainPrioritizationResponse` schema that makes an AI-invented priority number structurally impossible to add without touching the shared base class.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-31T12:39:45Z
- **Completed:** 2026-07-31T12:51:38Z
- **Tasks:** 2/2 completed
- **Files modified:** 4 (2 created/modified source, 1 new test file, 1 extended test file)

## Accomplishments

- `get_prioritization_context()` added to `backend/app/ai/grounding.py`: a tenant-scoped, outer-joined, None-on-miss query returning exactly D-04's factor set (`cvss_v3_score`, `epss_score`, `exploit_available`, `cisa_kev`, `exploit_status_name`, `severity`, `sla_due_at`, `sla_breached`) plus `cve_id` plus `Asset.department` — the one allowed non-PII owner signal.
- `ExplainPrioritizationResponse` added to `backend/app/ai/schemas.py` as a zero-new-fields subclass of `ExplainResponseBase` — the literal D-03/Pitfall #7/SC2 "no AI rank" enforcement, proven by a test that asserts exactly 4 field names and the absence of any `priority`/`rank`/`score`/`ai_priority`/`ai_rank` identifier.
- Both costly-to-reverse grounding-contract seams (D-04 owner-PII exclusion, D-03 no-rank schema) are now locked and test-proven before any prompt/route/UI is built on top of them in Plans 02-04.

## Task Commits

Each task was committed atomically:

1. **Task 1: get_prioritization_context() grounding query (owner-PII excluded)** - `6531b62` (feat)
2. **Task 2: ExplainPrioritizationResponse — the no-rank schema** - `246e8af` (feat)

**Plan metadata:** (this commit) - `docs(26-01): complete plan`

## Files Created/Modified

- `backend/app/ai/grounding.py` - Added `get_prioritization_context()` (10-column SELECT: D-04's 8 factors + cve_id + Asset.department, outer-joined, tenant-scoped, None-on-miss) + a module-docstring paragraph documenting the function's PII-exclusion contract
- `backend/app/ai/schemas.py` - Added `ExplainPrioritizationResponse(ExplainResponseBase)` — zero new fields, docstring explains the structural no-rank guarantee
- `backend/tests/test_ai_grounding_prioritization.py` (new) - 5 tests: 10-key dict + department present, PII columns never selected, cross-tenant None, missing-finding None, asset-less outer-join tolerance
- `backend/tests/test_ai_schemas.py` - Added `test_prioritization_no_rank_field` (exactly 4 fields, no forbidden identifiers) + `test_recheck_business_rules_accepts_prioritization_response_unchanged`

## Decisions Made

- **10-key dict, set-equality checked:** the valid-finding test asserts `set(record.keys()) == _EXPECTED_KEYS` rather than just checking the expected keys are present — catches an accidental extra column just as reliably as a missing one.
- **PII-exclusion docstring inside the function itself:** followed the exact precedent set by `get_asset_posture()` and `get_remediation_guidance_context()` (both already name their excluded PII columns in their own function docstrings, not just the module docstring) — the plan's action text explicitly asked for this, and the acceptance criterion's "no PII names inside the function" grep check is about the SELECT/query code, not the explanatory prose that names what was deliberately left out.
- **No-rank docstring wording avoids "priority"/"rank"/"score"/"ai_score" substrings:** the plan's own acceptance criterion runs a literal grep for those substrings scoped to the `ExplainPrioritizationResponse` class block, so the docstring explains the same D-03/Pitfall-7/SC2 concept using synonyms ("competing verdict number", "numeric field") instead — verified directly by extracting the class block and running the exact acceptance-criteria grep command (returned 0).

## Deviations from Plan

None — plan executed exactly as written. Two out-of-scope, pre-existing items were discovered and logged (not fixed) per the scope-boundary rule:

### Logged, not fixed (out of scope — pre-existing, unrelated to this plan's diff)

**1. `ruff format --check` flags a pre-existing line in `test_ai_schemas.py`**
- **Found during:** post-edit lint pass
- **Issue:** `test_remediation_guidance_response_has_zero_new_fields`'s existing assertion (authored in Phase 25) exceeds the configured line length per the currently-installed `ruff` version
- **Why not fixed:** `git diff` on this file shows 0 deletions — this plan's edit is purely additive; the flagged line was never touched
- **Logged to:** `.planning/phases/26-prioritization-narrative/deferred-items.md`

**2. `mypy-baseline.txt` note-line-number-drift (recurrence of the Phase 24-02 finding)**
- **Found during:** full-tree `mypy app/ | mypy-baseline filter --allow-unsynced` (the exact CI gate)
- **Issue:** reports "3 new" violations, but diffing baseline vs. live output shows all 21 changed lines are `note:` (not `error:`) lines in 13 files never touched by this plan, where the baseline stores line number `0` and the live run reports the real line
- **Why not fixed:** confirmed zero errors of any kind in `app/ai/grounding.py`/`app/ai/schemas.py` directly (`mypy app/ | grep '^app/ai/grounding.py\|^app/ai/schemas.py'` returns empty); this is the identical environment-driven artifact STATE.md already documents as "confirmed unrelated" for Phase 24-02
- **Logged to:** `.planning/phases/26-prioritization-narrative/deferred-items.md`

---

**Total deviations:** 0 auto-fixed; 2 out-of-scope items logged (not fixed).
**Impact on plan:** None — both logged items are pre-existing and unrelated to this plan's diff; ruff check (lint) and the two targeted pytest files are fully green.

## Issues Encountered

- The `getvul-postgres-1`/`getvul-redis-1` Docker containers were stopped at session start (despite the execution context's note that they were already running) — started both and waited for the Postgres healthcheck before running Task 1's DB-backed tests. No code impact; purely an environment-startup step.

## User Setup Required

None - no external service configuration required.

## Requirements Tracking

`REQUIREMENTS.md`'s AIP-01 checkbox was deliberately **not** marked complete despite this plan's frontmatter declaring `requirements: [AIP-01]`. Five plans in this phase (26-01, 26-02, 26-03, 26-04, 26-05) all declare `requirements: [AIP-01]` in their own frontmatter — the requirement is only genuinely satisfied once an analyst can actually see a cited narrative, which requires the prompt-builder (Plan 02), route (Plan 03), and frontend section (Plan 04), verified end-to-end at the Plan 05 TRACER GATE checkpoint. Marking AIP-01 "Complete" after only this plan's grounding-query-and-schema groundwork would misrepresent an unfinished, not-yet-user-visible capability as done. `ROADMAP.md`'s phase-level and per-plan tracking (updated via `roadmap update-plan-progress`) already accurately reflects "1/8 plans, In Progress" — that is the correct source of truth for partial phase progress.

## Next Phase Readiness

- `get_prioritization_context()` and `ExplainPrioritizationResponse` are both test-proven and ready for Plan 02 (prompt-builder: `PRIORITIZATION_ALLOWLIST` + `AllowlistedPrioritization` + `build_explain_prioritization_prompt()` + `prioritization_prompt_version()`, per 26-PATTERNS.md) to import.
- Plan 03 (route) will import both this plan's grounding function and schema directly, mirroring `explain_host.py`'s two-route (POST + GET) shape.
- No blockers. The two costly-to-reverse seams (D-04 owner-PII allowlist, D-03 no-rank schema) are locked before any prompt/route/UI work begins, per this plan's stated purpose.

## Self-Check: PASSED

- FOUND: `backend/app/ai/grounding.py` (contains `def get_prioritization_context`)
- FOUND: `backend/app/ai/schemas.py` (contains `class ExplainPrioritizationResponse`)
- FOUND: `backend/tests/test_ai_grounding_prioritization.py`
- FOUND: `backend/tests/test_ai_schemas.py`
- FOUND: `.planning/phases/26-prioritization-narrative/deferred-items.md`
- FOUND commit `6531b62` (Task 1) in `git log --oneline --all`
- FOUND commit `246e8af` (Task 2) in `git log --oneline --all`

---
*Phase: 26-prioritization-narrative*
*Completed: 2026-07-31*
