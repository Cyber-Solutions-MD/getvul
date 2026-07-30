---
phase: 25-asset-aware-remediation-guidance
plan: 02
subsystem: ai
tags: [python, pydantic, prompt-engineering, cite-or-refuse, allowlist, prompt-injection]

# Dependency graph
requires:
  - phase: 25-asset-aware-remediation-guidance
    plan: 01
    provides: "get_remediation_guidance_context()'s 12-key dict shape (cve_id/remediation_action/remediation_info/affected_product/affected_version/fixed_version/severity/exploit_available/cisa_kev/asset_hostname/os_name/os_version) — the exact field names this plan's allowlist declares"
  - phase: 24-ai-foundation-explain-this-vuln
    plan: 08
    provides: "The allowlist-quadruplet shape (ALLOWLIST frozenset + Allowlisted* Pydantic model + _to_allowlisted_*() field-by-field constructor + SYSTEM_PROMPT_*/FEW_SHOT_* + build_explain_*_prompt() + *_prompt_version()) this plan's 4th instance mirrors exactly
provides:
  - "backend/app/ai/schemas.py — ExplainRemediationGuidanceResponse(ExplainResponseBase), zero new fields"
  - "backend/app/ai/prompt_builder.py — REMEDIATION_GUIDANCE_ALLOWLIST + AllowlistedRemediationGuidance + _to_allowlisted_remediation_guidance() + SYSTEM_PROMPT_REMEDIATION_GUIDANCE + FEW_SHOT_REMEDIATION_GUIDANCE + build_explain_remediation_guidance_prompt() + remediation_guidance_prompt_version()"
affects: [25-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "4th allowlist-quadruplet instance, chosen to mirror the HOST quadruplet (flat 12 scalar fields, no nested list) rather than REMEDIATION's affected_assets[] shape"
    - "System prompt is the one place D-01/D-03's product intent becomes prompt text: cite-vendor-text-verbatim-before-interpretation + refuse-rather-than-invent-when-too-generic, backing (not replacing) the future D-01 deterministic code gate wired in Plan 03"
    - "SYSTEM_PROMPT_REMEDIATION_GUIDANCE also explicitly instructs the model to never recommend a destructive/security-disabling action even if vendor text implies one — a prompt-level second line of defense ahead of Plan 01's post-generation dangerous-pattern gate"

key-files:
  created:
    - backend/tests/test_ai_prompt_builder_remediation_guidance.py
  modified:
    - backend/app/ai/schemas.py
    - backend/app/ai/prompt_builder.py
    - backend/tests/test_ai_schemas.py

key-decisions:
  - "Second few-shot exemplar's grounded=false case uses vendor text that PASSES Plan 01's has_actionable_remediation_text() length/placeholder gate ('Contact vendor support for guidance.', 36 chars, not a denylisted placeholder) but is still too generic to safely derive concrete steps from — demonstrating D-02's second, model-judgment layer of the two-layer cite-or-refuse gate, distinct from Plan 01's deterministic pre-generation layer"
  - "System prompt adds an explicit 'never recommend a destructive/security-disabling action, describe it plainly instead' instruction not literally required by this plan's must_haves — a Rule 2 addition, since D-04's post-generation denylist gate (Plan 01, wired in Plan 03) is belt-and-suspenders, and this phase's own threat model (Pitfall #2) is specifically about dangerous AI-authored remediation text"

requirements-completed: [AIR-01]

# Metrics
duration: 25min
completed: 2026-07-30
---

# Phase 25 Plan 02: Remediation-Guidance Schema + Prompt-Builder Quadruplet Summary

**4th allowlist-quadruplet instance (`ExplainRemediationGuidanceResponse` + `REMEDIATION_GUIDANCE_ALLOWLIST` + `AllowlistedRemediationGuidance` + prompt builder) mirroring 24-08's host pattern exactly, with a system prompt that puts D-01's cite-verbatim-first + refuse-rather-than-invent contract into prompt text for the first time this phase.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-07-30T12:35:54+03:00
- **Completed:** 2026-07-30T13:00:09+03:00
- **Tasks:** 2 completed
- **Files modified:** 4 (2 modified source, 1 modified test, 1 new test file)

## Accomplishments
- `backend/app/ai/schemas.py`: `ExplainRemediationGuidanceResponse(ExplainResponseBase)` — a zero-new-fields subclass, identical shape to `ExplainHostResponse`/`ExplainRemediationResponse`; cited remediation steps live as prose inside `summary`.
- `backend/tests/test_ai_schemas.py`: added the D4 substring-provenance property test (`test_scanner_verbatim_citation_is_substring_of_source_field`, 25-AI-SPEC.md Section 5 / 25-RESEARCH.md Pattern 6) plus a zero-new-fields shape assertion.
- `backend/app/ai/prompt_builder.py`: the 4th allowlist-quadruplet instance — `REMEDIATION_GUIDANCE_ALLOWLIST` (12 fields, verified against Plan 01's `get_remediation_guidance_context()` return-dict keys), `AllowlistedRemediationGuidance` (`extra="forbid"`), `_to_allowlisted_remediation_guidance()` (field-by-field, `_get_field`/`_truncate` reused unchanged), `SYSTEM_PROMPT_REMEDIATION_GUIDANCE` + `FEW_SHOT_REMEDIATION_GUIDANCE` (grounded=true + grounded=false exemplars), `build_explain_remediation_guidance_prompt()`, `remediation_guidance_prompt_version()`.
- `backend/tests/test_ai_prompt_builder_remediation_guidance.py` (new): allowlist shape (12 fields, no owner-PII names), owner-PII exclusion proven against both a dict AND an attribute-bearing dataclass row, injection isolation (adversarial `remediation_info` text isolated inside `<scanner_data>`, never in `system`), and prompt-version stability/distinctness from `host_prompt_version()`.
- 22 new/extended tests all green; zero regression across the full existing `test_ai_schemas.py` (16), `test_ai_prompt_builder.py` (16), `test_ai_prompt_builder_host.py` (24), `test_ai_explain_host_remediation.py` (17), `test_ai_safety.py` (16), and `test_ai_grounding_remediation_guidance.py` (18) test files.

## Task Commits

Each task followed the TDD RED→GREEN cycle, committed atomically:

1. **Task 1: Response schema variant + scanner_verbatim substring-provenance test**
   - `d2a0ead` (test) — failing `test_ai_schemas.py` additions (RED, `ImportError: cannot import name 'ExplainRemediationGuidanceResponse'`)
   - `a0f0a40` (feat) — `ExplainRemediationGuidanceResponse` added to `schemas.py` (GREEN, 16/16 passed)
2. **Task 2: Allowlist + prompt-builder quadruplet (cite-verbatim-first system prompt)**
   - `8f35070` (test) — new `test_ai_prompt_builder_remediation_guidance.py` (RED, `ImportError: cannot import name 'REMEDIATION_GUIDANCE_ALLOWLIST'`)
   - `b22d146` (feat) — the full quadruplet added to `prompt_builder.py`, plus a ruff SIM300 (Yoda-condition) fix in the new test file (GREEN, 38/38 passed across the three touched test files)

**Plan metadata:** (this commit) — SUMMARY.md + STATE.md + ROADMAP.md

## Files Created/Modified
- `backend/app/ai/schemas.py` — added `ExplainRemediationGuidanceResponse(ExplainResponseBase): pass`-shaped subclass with docstring; `recheck_business_rules()` untouched
- `backend/tests/test_ai_schemas.py` — added `test_remediation_guidance_response_has_zero_new_fields` and `test_scanner_verbatim_citation_is_substring_of_source_field`; extended imports (`Citation`, `ExplainRemediationGuidanceResponse`, `ExplainResponseBase`)
- `backend/app/ai/prompt_builder.py` — added `REMEDIATION_GUIDANCE_ALLOWLIST`, `AllowlistedRemediationGuidance`, `_to_allowlisted_remediation_guidance()`, `FEW_SHOT_REMEDIATION_GUIDANCE`, `SYSTEM_PROMPT_REMEDIATION_GUIDANCE`, `build_explain_remediation_guidance_prompt()`, `remediation_guidance_prompt_version()`; extended the `app.ai.schemas` import
- `backend/tests/test_ai_prompt_builder_remediation_guidance.py` — new: allowlist shape, owner-PII exclusion (dict + attribute-object), injection isolation, prompt-version distinctness

## Decisions Made
- The second `FEW_SHOT_REMEDIATION_GUIDANCE` exemplar deliberately uses vendor text that clears Plan 01's `has_actionable_remediation_text()` deterministic gate (36 chars, not a denylisted placeholder) but is still too vague ("Contact vendor support for guidance.", no version/package named) to safely derive concrete steps from — this demonstrates D-02's SECOND layer of the two-layer cite-or-refuse gate (model judgment), distinct from Plan 01's first, deterministic layer. Both layers now have concrete artifacts: the deterministic predicate (Plan 01) and this few-shot exemplar (Plan 02).
- Added one instruction to `SYSTEM_PROMPT_REMEDIATION_GUIDANCE` not literally spelled out in this plan's `<action>` text: "never recommend a destructive or security-disabling action... describe it plainly instead." This is a Rule 2 addition (missing critical functionality) — the phase's threat model explicitly owns Pitfall #2 (dangerous AI-authored remediation text), D-04's post-generation denylist gate is the primary code-level mitigation (Plan 01, wired in Plan 03), and this prompt-level instruction is a cheap, directly-relevant second line of defense consistent with D-05's "maintained... reused by later phases" framing — it costs nothing to add now and narrows the surface the denylist gate has to catch.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking lint issue] Yoda-condition in the new allowlist-shape test**
- **Found during:** Task 2 GREEN verification (`ruff check`)
- **Issue:** `assert REMEDIATION_GUIDANCE_ALLOWLIST == frozenset({...})` triggered SIM300 (Yoda condition detected)
- **Fix:** Swapped operand order to `assert frozenset({...}) == REMEDIATION_GUIDANCE_ALLOWLIST`, matching the existing `test_vuln_allowlist_has_16_fields_excludes_asset_id`'s operand order in `test_ai_prompt_builder.py`
- **Files modified:** `backend/tests/test_ai_prompt_builder_remediation_guidance.py`
- **Commit:** `b22d146`

Otherwise: plan executed exactly as written. Both tasks followed the plan's `<action>` sections verbatim; `REMEDIATION_GUIDANCE_ALLOWLIST`'s 12 field names were cross-checked directly against `get_remediation_guidance_context()`'s (Plan 01) return-dict keys and matched exactly with no adjustment needed.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness
- The remediation-guidance schema + prompt-builder quadruplet is complete and fully test-proven: `ExplainRemediationGuidanceResponse`, `REMEDIATION_GUIDANCE_ALLOWLIST`, `AllowlistedRemediationGuidance`, `build_explain_remediation_guidance_prompt()`, `remediation_guidance_prompt_version()` are all ready for Plan 03 to import directly.
- Plan 03 wires: (1) Plan 01's `has_actionable_remediation_text()` D-01 pre-generation gate into a new `explain_remediation_guidance.py` route (mirroring `explain_host.py`'s UUID-keyed single-record shape per 25-PATTERNS.md), (2) Plan 01's `contains_dangerous_pattern()` as the new `dangerous_pattern_check` optional parameter on `_run_explain_stream()`, and (3) this plan's `build_explain_remediation_guidance_prompt`/`ExplainRemediationGuidanceResponse`/`REMEDIATION_GUIDANCE_ALLOWLIST`/`remediation_guidance_prompt_version` as the route's `build_prompt`/`response_model`/`allowed_source_fields`/`get_prompt_version` arguments.
- No blockers.

---
*Phase: 25-asset-aware-remediation-guidance*
*Completed: 2026-07-30*

## Self-Check: PASSED

All 5 claimed files found on disk; all 4 claimed commit hashes found in git log.
