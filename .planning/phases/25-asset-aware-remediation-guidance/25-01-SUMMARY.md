---
phase: 25-asset-aware-remediation-guidance
plan: 01
subsystem: ai
tags: [python, sqlalchemy, regex, cite-or-refuse, safety-gate, pydantic]

# Dependency graph
requires:
  - phase: 24-ai-foundation-explain-this-vuln
    provides: "ExplainResponseBase schema (summary/business_risk/citations/grounded), _contains_leak_marker haystack idiom, get_asset_posture()/get_remediation_group() grounding-query precedent, HOST_ALLOWLIST/VULN_ALLOWLIST owner-PII-exclusion discipline"
provides:
  - "backend/app/ai/safety.py — DANGEROUS_PATTERNS (8-category maintained denylist) + contains_dangerous_pattern() (D-04/D-05 post-generation safety gate primitive)"
  - "backend/app/ai/grounding.py additions — has_actionable_remediation_text() (D-01 deterministic refuse predicate) + get_remediation_guidance_context() (tenant-scoped, 12-column, owner-PII-excluding per-finding grounding query)"
affects: [25-02, 25-03, 26, 27]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Denylist gate mirrors _contains_leak_marker's exact haystack-composition idiom (summary + business_risk + every citation.text), then lowercase+whitespace-normalizes before scanning — obfuscation-resistant where cheap, not a full command-canonicalization pipeline"
    - "Refuse predicate never uses `is not None` — always .strip() + length-check + .casefold()-against-placeholder-set, since empty-string and generic-placeholder rows are indistinguishable from 'present' under a naive None check"
    - "New per-finding grounding query mirrors get_asset_posture()'s narrow-SELECT + tenant-scoped-404 shape; owner-PII columns are structurally never named in the SELECT (defense-in-depth ahead of any prompt-layer allowlist)"

key-files:
  created:
    - backend/app/ai/safety.py
    - backend/tests/test_ai_safety.py
    - backend/tests/test_ai_grounding_remediation_guidance.py
  modified:
    - backend/app/ai/grounding.py

key-decisions:
  - "Shipped only the 8 DANGEROUS_PATTERNS categories named in D-04 (rm -rf, drop/truncate table, mkfs, dd-to-device, chmod 777/a+rwx, pipe-to-shell, disable-security-control); the candidate 9th 'credential-rotation instructions' category is explicitly deferred (RESEARCH Open Question 1) — trivial one-line follow-up if real usage shows a need"
  - "MIN_REMEDIATION_CHARS=15 combined with a 6-entry casefolded placeholder frozenset (no remediation info [available], no remediation available, unknown, n/a, none) — 'Unknown'/'N/A'/'-' are already excluded by the length check alone; the placeholder set exists specifically for the longer multi-word placeholders ('No remediation info available' etc.) that exceed 15 chars"
  - "CrowdStrike's synthesized 'Update {product} to the latest version' is NOT added to the placeholder denylist — it names a real, asset-specific product, satisfying the length+placeholder gate (RESEARCH Assumptions A1, deliberately not re-litigated here)"

requirements-completed: [AIR-01]

# Metrics
duration: 21min
completed: 2026-07-30
---

# Phase 25 Plan 01: Anti-Fabrication Primitives (Denylist + Refuse Predicate + Grounding Query) Summary

**Standalone `contains_dangerous_pattern()` 8-category regex denylist and `has_actionable_remediation_text()`/`get_remediation_guidance_context()` cite-or-refuse primitives, proven by 34 positive/negative/obfuscation/tenant-isolation tests — zero engine or route wiring yet.**

## Performance

- **Duration:** 21 min
- **Started:** 2026-07-30T12:04:51+03:00
- **Completed:** 2026-07-30T12:25:36+03:00
- **Tasks:** 2 completed
- **Files modified:** 4 (1 new module, 1 modified module, 2 new test files)

## Accomplishments
- `backend/app/ai/safety.py`: a maintained, stdlib-`re`-only dangerous-command denylist (`DANGEROUS_PATTERNS`) and `contains_dangerous_pattern(candidate) -> str | None`, reusing `_contains_leak_marker`'s exact haystack idiom and returning a matched-pattern label for audit rows.
- `backend/app/ai/grounding.py`: `has_actionable_remediation_text()` — the D-01 deterministic pre-generation refuse predicate that treats empty-string, generic placeholders, and sub-15-char text as absent (never `is not None`).
- `backend/app/ai/grounding.py`: `get_remediation_guidance_context()` — a new, narrow, tenant-scoped, 12-column `Vulnerability` outerjoin `Asset` query keyed on `finding_id`, structurally incapable of surfacing owner-PII columns.
- 34 new tests (16 safety + 18 grounding) all green; zero regression in the 17 pre-existing `test_ai_explain_host_remediation.py` tests that exercise the same `grounding.py` module.

## Task Commits

Each task followed the TDD RED→GREEN cycle, committed atomically:

1. **Task 1: Dangerous-command denylist module (D-04/D-05)**
   - `1ab21e0` (test) — failing `test_ai_safety.py` (RED, `ModuleNotFoundError`)
   - `cd4445d` (feat) — `backend/app/ai/safety.py` implementation (GREEN, 16/16 passed)
2. **Task 2: Refuse predicate + tenant-scoped, PII-excluding grounding query (D-01/D-10)**
   - `2fb6982` (test) — failing `test_ai_grounding_remediation_guidance.py` (RED, `ImportError`)
   - `1c308f4` (feat) — `has_actionable_remediation_text()` + `get_remediation_guidance_context()` additions to `grounding.py` (GREEN, 18/18 passed)

**Plan metadata:** (this commit) — SUMMARY.md + STATE.md + ROADMAP.md

## Files Created/Modified
- `backend/app/ai/safety.py` — new module: `DANGEROUS_PATTERNS` (8 categories) + `contains_dangerous_pattern(candidate: ExplainResponseBase) -> str | None`
- `backend/tests/test_ai_safety.py` — new: positive (1 per category + explicit per-label coverage), obfuscation (mixed-case/whitespace, split-field), negative (3 named over-block-proof cases) tests
- `backend/app/ai/grounding.py` — added `_GENERIC_REMEDIATION_PLACEHOLDERS`, `MIN_REMEDIATION_CHARS`, `has_actionable_remediation_text()`, `get_remediation_guidance_context()`; extended module docstring to distinguish the new query from `get_vulnerability()` and `get_remediation_group()`
- `backend/tests/test_ai_grounding_remediation_guidance.py` — new: refuse-predicate cases (None/empty/placeholder/short/CrowdStrike-synthesized), tenant-isolation (foreign-tenant + missing finding_id → None), 12-key allowlisted shape, owner-PII-key absence, null-asset outerjoin case

## Decisions Made
- 8-category denylist scope locked to D-04's literal example list; the 9th "credential-rotation" category is deferred, not built (documented deferral, not a silent omission).
- `MIN_REMEDIATION_CHARS = 15` chosen exactly per RESEARCH Pattern 1 — excludes "Unknown"/"N/A"/"-" via length alone; the placeholder frozenset exists for the longer multi-word placeholders.
- CrowdStrike's synthesized "Update {product} to the latest version" text counts as actionable (RESEARCH Assumptions A1) — not re-litigated, per plan's explicit test coverage requirement.

## Deviations from Plan

None - plan executed exactly as written. Both tasks followed the plan's `<action>` sections verbatim (RESEARCH Pattern 1/Pattern 2/Pattern 3 code was the direct basis for the implementations), and the scope-decision to defer the 9th denylist category was explicitly called for by the plan itself (not an unplanned deviation).

## Issues Encountered
- Accidentally ran `git stash -- app/ai/grounding.py` while diagnosing a pre-existing, unrelated mypy baseline noise (checking whether `vulnerabilities/models.py`/`assets/models.py` errors were caused by this plan's edit). Immediately caught and reverted via `git stash pop` before any other action — confirmed via `git stash list` that only the just-created stash was popped, leaving the repo's 5 pre-existing stash entries (from prior worktree/reviewfix sessions) untouched. `app/ai/grounding.py`'s changes were fully restored and re-verified (grep + pytest) before proceeding. No data loss; documented per the git-hygiene constraint in this session's instructions.
- Confirmed the mypy errors surfaced when type-checking `app/ai/grounding.py` (`Missing type arguments for generic type "dict"`, `Name "Asset"/"Vulnerability" is not defined`) originate entirely from `app/vulnerabilities/models.py` and `app/assets/models.py` — pre-existing, unrelated to this plan's files, and out of this task's scope boundary (not fixed, not touched).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Both anti-fabrication primitives (`contains_dangerous_pattern`, `has_actionable_remediation_text` + `get_remediation_guidance_context`) exist standalone and are fully test-proven, ready for Plan 03 to wire `dangerous_pattern_check` into `_run_explain_stream()` and the D-01 gate into the new `explain_remediation_guidance.py` route (per RESEARCH Pattern 3/4).
- Plan 02 (schema variant + prompt-builder quadruplet) can now import `get_remediation_guidance_context()`'s 12-key dict shape directly — field names (`cve_id`, `remediation_action`, `remediation_info`, `affected_product`, `affected_version`, `fixed_version`, `severity`, `exploit_available`, `cisa_kev`, `asset_hostname`, `os_name`, `os_version`) are locked and test-verified.
- No blockers.

---
*Phase: 25-asset-aware-remediation-guidance*
*Completed: 2026-07-30*
