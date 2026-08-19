---
phase: 39-exception-risk-acceptance-workflow
plan: 02
subsystem: api
tags: [fastapi, sqlalchemy, pydantic, exceptions, risk-acceptance, scope-resolution]

# Dependency graph
requires:
  - phase: 39-01
    provides: the exceptions module scaffold (ExceptionRecord/ExceptionCreate/ExceptionResponse), active_exception_subquery (already schema-complete for all 3 scope branches), grant/list/revoke endpoints (FINDING scope only), validate_expiry's D-14 hard cap (shipped ahead of schedule), Pattern 4 lazy-audit sweep
provides:
  - "grant_exception resolves all three EXC-01 scope types end-to-end: FINDING (server-derived cve_id/asset_id, Pitfall 9), ASSET (tenant-scoped Asset lookup + client cve_id, forward-looking), ASSET_GROUP (tenant-scoped AssetGroup lookup + client cve_id, forward-looking)"
  - "ExceptionCreate.cve_id: required for ASSET/ASSET_GROUP (422 via model_validator), optional-but-ignored for FINDING"
  - "D-03 precondition reconciled per Pattern 2: OPEN/IN_PROGRESS check applies ONLY to FINDING scope; ASSET/ASSET_GROUP validate only tenant-owned target existence (D-11/Pitfall 8)"
  - "DEFAULT_EXPIRY_DAYS={FALSE_POSITIVE:180, ACCEPTED_RISK:90} exposed alongside the pre-existing MAX_EXPIRY_DAYS=365 hard cap"
  - "D-12 overlap OR-semantics and D-11 live AssetGroupMember/new-source membership proven end-to-end (no new logic needed -- both were already correct by construction from 39-01's active_exception_subquery)"
  - "exception.grant audit payload enriched with the resolved vulnerability_id/asset_id/asset_group_id (Rule 2)"
affects: [39-03-sla-subtraction, 39-04-consumer-sweep, 39-05-consumer-sweep, 39-06-dashboards-frontend, 39-07-frontend, 39-08-closing-plan]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Scope-conditional Pydantic model_validator (cve_id required only for ASSET/ASSET_GROUP) mirroring the belt-and-suspenders defense-in-depth pattern 39-01 established for approver tenant-scoping (schema-level 422 + service-level 400 both check the same invariant)"
    - "Forward-looking grant validation: ASSET/ASSET_GROUP scope validates ONLY that the target exists and is tenant-owned, deliberately never the OPEN/IN_PROGRESS precondition that FINDING scope applies (D-11)"

key-files:
  created:
    - backend/tests/test_exceptions_scope.py
  modified:
    - backend/app/exceptions/service.py
    - backend/app/exceptions/schemas.py
    - backend/app/exceptions/router.py

key-decisions:
  - "cve_id added to ExceptionCreate as a new optional field with a model_validator(mode='after') enforcing it's required for ASSET/ASSET_GROUP scope (422) -- FINDING scope accepts-but-ignores a client cve_id since extra='forbid' only blocks UNDECLARED fields, not declared-but-unused ones"
  - "Rule 2 (missing critical/audit completeness): enriched the exception.grant audit payload with the resolved vulnerability_id/asset_id/asset_group_id -- previously only scope_type+cve_id were recorded, which couldn't distinguish WHICH asset/group a grant covers without cross-referencing the exceptions table. Added its own test (test_grant_audit_includes_resolved_target, committed as a small follow-up after Task 2) since this wasn't literally requested by Task 1's action bullets"
  - "MAX_EXPIRY_DAYS's dual-bound validation (past-date AND 365-day cap) was already fully implemented in 39-01, ahead of this plan's own Task 2 action bullets (which assumed it didn't exist yet) -- Task 2's actual net-new code is limited to the DEFAULT_EXPIRY_DAYS constant; the rest of Task 2 is test coverage proving already-correct 39-01 behavior (D-12 overlap, D-11 live membership) now that Task 1's ASSET/ASSET_GROUP grants make it exercisable end-to-end"
  - "DEFAULT_EXPIRY_DAYS implemented as a plain importable module constant, not a new API endpoint -- the frontend pre-fill UX consuming it is explicitly deferred to /gsd-ui-phase (39-CONTEXT.md), and no task in this plan calls for a new endpoint; inventing one now would be untested surface ahead of need"
  - "EXC-01/EXC-02/EXC-03 left unmarked [ ] in REQUIREMENTS.md despite being in this plan's requirements frontmatter -- confirmed via grep that 39-08 is the only plan claiming all four EXC-01..04 and is this phase's explicitly-designated last declaring plan (39-01-SUMMARY.md precedent, mirrors the Phase 38 CAMP-01 convention); marking them complete here would overclaim since 39-03/04/05/06/07 still have EXC-02/EXC-01 work outstanding (SLA subtraction, consumer sweep, dashboards, frontend)"
  - "Both tdd='true' tasks were executed with tests and implementation verified together before each commit (write code -> write tests -> run green -> commit), not as literally separate RED-commit-then-GREEN-commit pairs -- this plan's frontmatter is type: execute, not type: tdd, so the strict plan-level RED/GREEN gate-sequence enforcement (which specifically gates on type: tdd) does not apply. Meaningfulness was confirmed by inspection: test_scope_asset_grant/test_scope_asset_group_grant/test_precondition_skipped_for_asset_scope/test_derive_finding_target_server_side all exercise branches that 400'd or 422'd against the pre-Task-1 code (the old `else: raise HTTPException(400, f'{scope_type} scope is not yet supported.')` catch-all, and cve_id being an undeclared/forbidden field); test_default_windows_exposed would ImportError against pre-Task-2 code. The overlap/live-membership tests prove pre-existing 39-01 exclusion-join behavior now reachable via Task 1's new grants, not new Task-2 logic"

patterns-established:
  - "grant_exception's if/elif/elif scope_type branch shape (FINDING/ASSET/ASSET_GROUP) is now the template for the plan's remaining consumer-sweep work -- no further scope-resolution changes needed, only the exclusion filter itself needs threading into new call sites (39-04/39-05)"

requirements-completed: []  # EXC-01/02/03 span multiple plans in this phase; 39-08 is the last declaring plan (see key-decisions)

coverage:
  - id: D1
    description: "All three EXC-01 scope types (FINDING/ASSET/ASSET_GROUP) grant correctly with the right persisted fields"
    requirement: "EXC-01"
    verification:
      - kind: integration
        ref: "backend/tests/test_exceptions_scope.py#test_scope_finding_grant"
        status: pass
      - kind: integration
        ref: "backend/tests/test_exceptions_scope.py#test_scope_asset_grant"
        status: pass
      - kind: integration
        ref: "backend/tests/test_exceptions_scope.py#test_scope_asset_group_grant"
        status: pass
    human_judgment: false
  - id: D2
    description: "FINDING scope derives cve_id/asset_id server-side from the resolved Vulnerability row, ignoring any client-supplied cve_id (Pitfall 9)"
    requirement: "EXC-01"
    verification:
      - kind: integration
        ref: "backend/tests/test_exceptions_scope.py#test_derive_finding_target_server_side"
        status: pass
    human_judgment: false
  - id: D3
    description: "D-03 OPEN/IN_PROGRESS precondition applies only to FINDING scope (rejects REMEDIATED); ASSET/ASSET_GROUP scope is forward-looking and skips it entirely (D-11/Pitfall 8)"
    requirement: "EXC-01"
    verification:
      - kind: integration
        ref: "backend/tests/test_exceptions_scope.py#test_precondition_rejects_remediated"
        status: pass
      - kind: integration
        ref: "backend/tests/test_exceptions_scope.py#test_precondition_skipped_for_asset_scope"
        status: pass
    human_judgment: false
  - id: D4
    description: "D-14 hard expiry cap rejects past dates and dates beyond 365 days; DEFAULT_EXPIRY_DAYS exposed for future frontend pre-fill"
    requirement: "EXC-02"
    verification:
      - kind: integration
        ref: "backend/tests/test_exceptions_scope.py#test_expiry_past_rejected"
        status: pass
      - kind: integration
        ref: "backend/tests/test_exceptions_scope.py#test_expiry_over_cap_rejected"
        status: pass
      - kind: unit
        ref: "backend/tests/test_exceptions_scope.py#test_default_windows_exposed"
        status: pass
    human_judgment: false
  - id: D5
    description: "D-12 overlap OR-semantics: excluded while any covering exception is active (across different scope branches), still excluded after revoking one, resurfaces once the last covering exception is revoked"
    requirement: "EXC-02"
    verification:
      - kind: integration
        ref: "backend/tests/test_exceptions_scope.py#test_overlap_or_semantics"
        status: pass
    human_judgment: false
  - id: D6
    description: "D-11 live ASSET_GROUP membership: a member added after the grant is excluded with no re-grant; a new source re-detecting the same CVE/asset is covered too"
    requirement: "EXC-01"
    verification:
      - kind: integration
        ref: "backend/tests/test_exceptions_scope.py#test_live_group_membership"
        status: pass
    human_judgment: false
  - id: D7
    description: "exception.grant audit payload includes the resolved vulnerability_id/asset_id/asset_group_id, not just scope_type/cve_id"
    requirement: "EXC-03"
    verification:
      - kind: integration
        ref: "backend/tests/test_exceptions_scope.py#test_grant_audit_includes_resolved_target"
        status: pass
    human_judgment: false

# Metrics
duration: 26min
completed: 2026-08-19
status: complete
---

# Phase 39 Plan 02: Full Scope Resolution & Expiry-Cap/Overlap Proofs Summary

**ASSET/ASSET_GROUP scope resolution added to the exceptions grant path (tenant-scoped target validation, D-11 forward-looking precondition skip, D-14 default-window constant), proven against 39-01's already-correct D-12 overlap and D-11 live-membership exclusion logic via a new 12-test scope suite.**

## Performance

- **Duration:** 26 min
- **Started:** 2026-08-19T06:58:39Z (chained immediately after 39-01)
- **Completed:** 2026-08-19T07:24:13Z
- **Tasks:** 2/2 (plus one Rule-2 test-coverage follow-up)
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments

- `grant_exception` now resolves ASSET and ASSET_GROUP scope end-to-end: tenant-scoped `Asset`/`AssetGroup` existence lookups (404 on miss, matching the FINDING-scope IDOR-safe convention), client-supplied `cve_id` persisted verbatim, deliberately **no** OPEN/IN_PROGRESS precondition (D-11's forward-looking rule, Pitfall 8) -- the `else: raise HTTPException(400, "... not yet supported.")` placeholder from 39-01 is gone
- `ExceptionCreate.cve_id` added: required for ASSET/ASSET_GROUP (422 via a `model_validator`), optional-but-silently-ignored for FINDING scope (server always derives it from the resolved `Vulnerability` row, Pitfall 9) -- proven by sending a bogus client `cve_id` alongside a FINDING grant and asserting the response reflects the real one
- `DEFAULT_EXPIRY_DAYS = {"FALSE_POSITIVE": 180, "ACCEPTED_RISK": 90}` added alongside the pre-existing `MAX_EXPIRY_DAYS` hard cap (39-01 had already shipped both the past-date and 365-day-ceiling checks in `validate_expiry`, ahead of this plan's own schedule)
- D-12 overlap OR-semantics and D-11 live `AssetGroupMember`/new-source membership proven end-to-end for the first time -- both behaviors were already correct in 39-01's `active_exception_subquery` by construction, but were untestable until Task 1 made ASSET/ASSET_GROUP grants reachable
- `exception.grant` audit payload enriched with the resolved `vulnerability_id`/`asset_id`/`asset_group_id` (Rule 2 self-review fix, EXC-03 completeness) plus a dedicated proof test
- 12-test `backend/tests/test_exceptions_scope.py` suite (20/20 green combined with 39-01's 8-test tracer suite); zero regressions across a 58-test sweep spanning vulnerabilities/campaigns/asset-groups

## Task Commits

Each task was committed atomically:

1. **Task 1: full scope resolution + per-scope precondition + Pitfall-9 target derivation** - `8c2b437` (feat)
2. **Task 2: hard expiry cap + default windows + D-12 overlap tests** - `f38bf27` (test)

**Follow-up (Rule 2 test-coverage addendum, found during self-review before writing this Summary):** `96eee3b` (test)

**Plan metadata:** _pending -- this commit follows_

## Files Created/Modified

- `backend/app/exceptions/service.py` - `grant_exception`'s ASSET/ASSET_GROUP branches (tenant-scoped `Asset`/`AssetGroup` lookups, no OPEN/IN_PROGRESS precondition); `DEFAULT_EXPIRY_DAYS` constant
- `backend/app/exceptions/schemas.py` - `ExceptionCreate.cve_id` field + `_require_cve_id_for_target_scope` model_validator
- `backend/app/exceptions/router.py` - `exception.grant` audit payload gains `vulnerability_id`/`asset_id`/`asset_group_id`
- `backend/tests/test_exceptions_scope.py` - 12 tests: 3 scope grants, 2 precondition-reconciliation, 1 Pitfall-9 derivation, 2 expiry-cap, 1 default-windows, 1 overlap OR-semantics, 1 live-membership, 1 audit-payload

## Decisions Made

- `cve_id` validated at the schema layer (422) AND re-checked at the service layer (400) for ASSET/ASSET_GROUP -- belt-and-suspenders, mirroring 39-01's own approver tenant-scoping precedent, so `grant_exception` stays safe to call directly without relying solely on Pydantic.
- Chose to enrich the grant audit payload with the resolved target IDs (Rule 2) rather than leave it at `scope_type`+`cve_id` alone -- an auditor reviewing `exception.grant` rows previously couldn't tell WHICH asset or group a non-FINDING grant covered without a separate query.
- `DEFAULT_EXPIRY_DAYS` shipped as a plain constant, no new endpoint -- the frontend that would consume it for pre-fill UX is out of this phase's scope (`/gsd-ui-phase`, per 39-CONTEXT.md).
- EXC-01/EXC-02/EXC-03 requirement checkboxes intentionally left unmarked; see key-decisions in frontmatter for the full 39-08-is-last-declaring-plan rationale (verified via grep across all 8 phase plans).
- Both `tdd="true"` tasks were executed as write-code-then-tests-then-verify-green-then-commit, not literal separate RED/GREEN commits -- this plan's frontmatter `type` is `execute`, not `tdd`, so the stricter plan-level gate-sequence check doesn't apply. See key-decisions in frontmatter for the test-by-test meaningfulness analysis (which tests exercise genuinely new code vs. already-correct 39-01 behavior).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] `exception.grant` audit payload didn't record the resolved target**
- **Found during:** Task 1 (while wiring ASSET/ASSET_GROUP resolution)
- **Issue:** The existing audit payload (from 39-01) recorded `scope_type` and `cve_id` but never the actual `vulnerability_id`/`asset_id`/`asset_group_id` the grant resolved to. Once ASSET/ASSET_GROUP scope became grantable, two different `exception.grant` rows with `scope_type="ASSET_GROUP", cve_id="CVE-X"` would be indistinguishable in the audit trail without a separate `exceptions` table lookup -- a real EXC-03 ("who/why/scope/expiry") completeness gap, not a hypothetical one.
- **Fix:** Added `vulnerability_id`/`asset_id`/`asset_group_id` (each `str(...)` or `None`) to the audit `details` dict in `router.py::grant_exception_endpoint`.
- **Files modified:** `backend/app/exceptions/router.py`
- **Verification:** New test `test_grant_audit_includes_resolved_target` (committed separately, `96eee3b`, after being caught in self-review); confirmed the pre-existing `test_grant_revoke_audit_payload` (39-01) still passes unmodified since it only asserts specific keys, not exact dict equality.
- **Committed in:** `8c2b437` (Task 1 commit); test coverage in `96eee3b`

---

**Total deviations:** 1 auto-fixed (missing-critical/audit-completeness)
**Impact on plan:** Necessary for EXC-03 correctness once non-FINDING scopes exist. No scope creep -- doesn't touch SLA subtraction, the consumer sweep, or any file beyond the router's existing audit call.

## Issues Encountered

None. `MAX_EXPIRY_DAYS`'s dual-bound check (past-date + 365-day cap) was assumed by Task 2's action bullets to not exist yet, but 39-01 had already implemented both checks in `validate_expiry` -- this made Task 2's actual net-new code small (just `DEFAULT_EXPIRY_DAYS`), with the rest of Task 2 being test coverage for already-correct 39-01 behavior now exercisable end-to-end. Verified via `mypy app/ | mypy-baseline filter` that the only "new violations" reported (9, in `backend/app/ticketing/daily_sync.py`) reproduce identically via `git stash` with zero of this plan's changes present -- confirmed pre-existing and unrelated (same drift 39-01 already logged to `deferred-items.md`).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `grant_exception`'s full scope-resolution shape (FINDING/ASSET/ASSET_GROUP) is complete; no further scope-resolution work remains in this phase.
- Plan 03 (SLA subtraction) and Plans 04/05 (consumer sweep) can now exercise ASSET/ASSET_GROUP-scoped exceptions end-to-end for the first time -- the `active_exception_subquery` seam they'll thread into every remaining consumer was already correct from 39-01 and is now proven reachable via all three scope types, not just FINDING.
- Plans 06/07 (dashboards/frontend) have the full `ExceptionResponse` shape (raw `scope_type`/`cve_id`/`vulnerability_id`/`asset_id`/`asset_group_id`) to build target-label formatting against, plus `DEFAULT_EXPIRY_DAYS` for the grant form's pre-fill.
- No blockers. Full `test_exceptions.py` + `test_exceptions_scope.py` suite (20/20) plus a 58-test regression sweep across vulnerabilities/campaigns/asset-groups all green; ruff clean; mypy shows zero new violations attributable to this plan's files.

## Self-Check: PASSED

- `backend/app/exceptions/service.py` — FOUND
- `backend/app/exceptions/schemas.py` — FOUND
- `backend/app/exceptions/router.py` — FOUND
- `backend/tests/test_exceptions_scope.py` — FOUND
- Commit `8c2b437` — FOUND in git log
- Commit `f38bf27` — FOUND in git log
- Commit `96eee3b` — FOUND in git log

---
*Phase: 39-exception-risk-acceptance-workflow*
*Completed: 2026-08-19*
