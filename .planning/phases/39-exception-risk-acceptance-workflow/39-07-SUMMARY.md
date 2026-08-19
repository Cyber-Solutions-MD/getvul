---
phase: 39-exception-risk-acceptance-workflow
plan: 07
subsystem: ui
tags: [nextjs, react, typescript, tanstack-query, tailwind, exceptions, risk-acceptance, combobox, forms]

# Dependency graph
requires:
  - phase: 39-01
    provides: "the exceptions module scaffold (ExceptionRecord/ExceptionCreate/ExceptionResponse), grant/list/revoke endpoints (POST /api/v1/exceptions, POST /{id}/revoke, GET /), require_analyst on writes"
  - phase: 39-02
    provides: "full ASSET/ASSET_GROUP scope resolution (cve_id required for those scopes, vulnerability_id/asset_id derived server-side for FINDING per Pitfall 9), DEFAULT_EXPIRY_DAYS={FALSE_POSITIVE:180,ACCEPTED_RISK:90} + MAX_EXPIRY_DAYS=365 client-pre-fill constants"
  - phase: 39-06
    provides: "the /dashboard/exceptions list UI, useExceptions() hook, queryKeys.exceptions.{all,list}, exceptions-table.tsx with a disabled Revoke placeholder (Known Stub) awaiting this plan's mutation hook"
provides:
  - "ApproverCombobox: a controlled (value/onSelect), no-internal-mutation searchable tenant-user picker for embedding inside a single-submit multi-field form"
  - "useGrantException()/useRevokeException(id): grant/revoke mutation hooks (retry:0, invalidate queryKeys.exceptions.all)"
  - "ExceptionGrantDialog: the 4-field grant form (Scope -> Approver -> Justification -> Expires) covering all 3 scope types end-to-end, submit-gated on all four fields (D-06), classifyGrantError mapping backend errors onto the UI-SPEC's 3 dialog-owned error surfaces"
  - "Drill-panel Actions section 'Accept risk'/'Mark false positive' entry points opening the dialog with type pre-set and FINDING scope defaulted to the panel's own CVE x asset"
  - "exceptions-table.tsx's Revoke button wired to useRevokeException via a shared warning ConfirmModal (D-17) -- resolves 39-06's Known Stub"
affects: [39-08-closing-plan]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Controlled combobox variant (value/onSelect props, zero internal mutation) as the template for embedding a searchable-picker field inside any future single-submit multi-field form, alongside the pre-existing mutation-bound inline-editor combobox variant (reassign-combobox.tsx)"
    - "classifyGrantError: literal-string-match (D-03) + prefix-match (D-14) + generic-HTTP-coded-fallback error triage mapping a shared backend HTTPException message space onto field-level vs. dialog-level UI surfaces, without re-deriving or duplicating the backend's own well-crafted copy"

key-files:
  created:
    - frontend/src/components/exceptions/approver-combobox.tsx
    - frontend/src/components/exceptions/approver-combobox.test.tsx
    - frontend/src/lib/queries/use-exception-mutations.ts
    - frontend/src/lib/queries/use-exception-mutations.test.ts
    - frontend/src/components/exceptions/exception-grant-dialog.tsx
    - frontend/src/components/exceptions/exception-grant-dialog.test.tsx
  modified:
    - frontend/src/components/vulnerabilities/microcopy.ts
    - frontend/src/components/vulnerabilities/drill-content.tsx
    - frontend/src/components/exceptions/exceptions-table.tsx
    - frontend/src/components/exceptions/exceptions-table.test.tsx
    - frontend/src/components/vulnerabilities/drill-panel.test.tsx
    - frontend/src/components/vulnerabilities/drill-panel-mobile.test.tsx
    - .planning/phases/39-exception-risk-acceptance-workflow/deferred-items.md

key-decisions:
  - "ApproverCombobox widens DirectoryUser locally (ApproverUser = DirectoryUser & {id: string}) instead of editing the shared use-asset-detail.ts -- /users/directory's raw JSON already returns `id` (backend/app/users/router.py) but the shared frontend type never declared it (that consumer only ever needed email/display_name); editing the shared type file was outside this plan's files_modified"
  - "ExceptionGrantDialog has no separate CVE input field (matches the UI-SPEC's literal 4-field mockup) -- ASSET/ASSET_GROUP scope carries the FINDING's own cve_id forward unchanged, so broadening scope widens the blast radius for the SAME CVE the drill panel is already showing, never lets the analyst type an unrelated one"
  - "'This asset' scope option disables when finding.assetId is null; 'This asset'+'Asset group' both disable when finding.cveId is null -- a defensive completeness guard (Rule 2) the plan's action text didn't spell out, preventing a submit that would send an empty-string asset_id/cve_id to the backend"
  - "useGrantException mirrors useStartCampaign's onError toast (not just its onSuccess one), even though this means a generic toast can appear alongside the dialog's own specific field/banner error -- literal fidelity to the plan's explicit 'mirrors useStartCampaign' instruction; the transient toast and the persistent dialog banner serve different attention windows, not a redundant single surface"
  - "ExceptionGrantDialog renders via its own plain ResponsiveDialog, not through drill-panel-mobile.tsx's renderConfirm render-prop (whose type is fixed to the ticket-confirm's own fields) -- on mobile this nests a functional-but-non-cascading vaul Drawer inside the outer drill-panel drawer rather than a Drawer.NestedRoot; logged to deferred-items.md rather than extending renderConfirm's contract (outside this plan's files_modified)"
  - "The Revoke ConfirmModal names the scope kind ('this finding'/'this asset'/'this asset group') rather than a resolved hostname/group-name, mirroring exceptions-table.tsx's own pre-existing targetTitle() 'no fake human-readable target' precedent (ExceptionResponse has no such join, 39-01/39-02's documented scope boundary)"
  - "EXC-01 left [ ] unmarked in REQUIREMENTS.md despite being in this plan's own requirements frontmatter -- confirmed (a 4th time) that 39-08 is this phase's sole designated last-declaring plan for EXC-01..04: its own PLAN.md frontmatter literally lists `requirements: [EXC-01, EXC-02, EXC-03, EXC-04]`, matching the precedent 39-01/39-02/39-06 each independently documented"
  - "Added 3 new co-located test files (approver-combobox.test.tsx, use-exception-mutations.test.tsx, exception-grant-dialog.test.tsx) beyond the plan's files_modified, and updated 3 pre-existing test files (exceptions-table.test.tsx, drill-panel.test.tsx, drill-panel-mobile.test.tsx) that broke as a direct, unavoidable consequence of the new real query/mutation hooks this plan's wiring introduced into components those suites already render -- mirrors 39-06's own established co-located-test-file convention"

patterns-established:
  - "A controlled (value/onSelect), zero-internal-mutation combobox is now the second established combobox shape in this codebase (alongside the mutation-bound inline-editor shape) -- future forms needing a searchable-picker FIELD (not a standalone inline editor) should copy ApproverCombobox's data-flow, not ReassignCombobox's"

requirements-completed: []  # EXC-01 spans 39-01/39-02/39-06/39-07; 39-08 is the phase's designated last declaring plan (see key-decisions)

# Metrics
duration: 36min
completed: 2026-08-19
---

# Phase 39 Plan 07: Exception Grant/Revoke Frontend Summary

**Grant surface for EXC-01: drill-panel "Accept risk"/"Mark false positive" entry points, a 4-field ExceptionGrantDialog covering all three scope types end-to-end, a controlled approver-combobox with zero internal mutation, and the exceptions-list Revoke button wired to useRevokeException — closing the D-17 UI loop Plan 06 stubbed.**

## Performance

- **Duration:** 36 min
- **Started:** 2026-08-19T09:07:00Z (approx, immediately following 39-03/39-06)
- **Completed:** 2026-08-19T09:43:37Z
- **Tasks:** 3/3
- **Files modified:** 13 (6 created, 7 modified)

## Accomplishments

- `ApproverCombobox`: a controlled (value/onSelect), no-internal-mutation tenant-user picker copying reassign-combobox's 250ms debounce/highlightIdx/keyboard-nav/WAI-ARIA markup but replacing the data-flow entirely (Pitfall 6) — grep-verified zero `useReassignAsset` occurrences; loading (disabled + "Loading approvers…") and error ("Approvers failed to load. Retry.") states both covered
- `useGrantException()`/`useRevokeException(id)`: grant/revoke mutation hooks mirroring `useStartCampaign`/`useCloseCampaign` exactly (retry:0, `queryKeys.exceptions.all` invalidation)
- `ExceptionGrantDialog`: the 4-field grant form (Scope segmented control → Approver → Justification → Expires) with all three scope types wired — FINDING sends `vulnerability_id` only (server derives `cve_id`/`asset_id`, Pitfall 9/T-39-26); ASSET/ASSET_GROUP carry the finding's own `cve_id` forward (D-11 forward-looking, no separate CVE field exists). Submit gated on all four fields (D-06); Expires is the visual focal point with its always-visible mandatory helper; `classifyGrantError` maps the backend's own HTTPException messages onto the UI-SPEC's three dialog-owned error surfaces (D-03 precondition verbatim banner / D-14 expiry-cap field-level / generic HTTP-coded fallback)
- Drill panel Actions section gains "Accept risk"/"Mark false positive" secondary buttons (border/bg-surface-2 chrome, not the gradient CTA) opening a single dialog instance with `type` pre-set and FINDING scope defaulted to the panel's own CVE × asset
- `exceptions-table.tsx`'s Revoke button (39-06's disabled placeholder) is now fully live: opens a shared warning `ConfirmModal` with the exact D-17 copy, confirms via `useRevokeException(row.id)` (invalidates the list on success), disabled only for already-historical (revoked/expired) rows
- 65 new/updated frontend tests across 6 files proving fixed field order, submit-gating (including scope-switch re-gating and "This asset" disabled when the finding has no `asset_id`), the 1000-char justification backstop (counter appears near the cap + a full-length value is never silently truncated), all 3 scope-branch payload shapes, all 3 dialog error surfaces, and the Revoke confirm-then-mutate flow; full project regression sweep 153 test files / 1074 tests green, `tsc`/`eslint` clean

## Task Commits

Each task was committed atomically:

1. **Task 1: approver-combobox + grant/revoke mutation hooks + drill microcopy** - `8757fdd` (feat)
2. **Task 2: ExceptionGrantDialog (4-field form, all state branches)** - `d7ff511` (feat)
3. **Task 3: wire drill-panel Actions entry points + exceptions-list Revoke** - `a5b98e3` (feat)

**Plan metadata:** _pending — this commit follows_

## Files Created/Modified

- `frontend/src/components/exceptions/approver-combobox.tsx` — controlled tenant-user picker (value/onSelect, no internal mutation)
- `frontend/src/components/exceptions/approver-combobox.test.tsx` — 10 tests (no-mutation guarantee, loading/error states, external-value-reset sync, ARIA wiring)
- `frontend/src/lib/queries/use-exception-mutations.ts` — `useGrantException()` + `useRevokeException(id)`
- `frontend/src/lib/queries/use-exception-mutations.test.ts` — 5 tests (POST bodies, invalidation, toast copy, per-call onSuccess)
- `frontend/src/components/exceptions/exception-grant-dialog.tsx` — the 4-field grant form
- `frontend/src/components/exceptions/exception-grant-dialog.test.tsx` — 15 tests (field order, gating, 3 scope-branch payloads, backstop, 3 error surfaces, reset-on-reopen)
- `frontend/src/components/vulnerabilities/microcopy.ts` — `drill.acceptRisk`/`drill.markFalsePositive` labels
- `frontend/src/components/vulnerabilities/drill-content.tsx` — Actions section entry points + `ExceptionGrantDialog` mount
- `frontend/src/components/exceptions/exceptions-table.tsx` — live Revoke wiring (replaces the disabled placeholder), `isHistorical()`/`SCOPE_TARGET_PHRASE` helpers
- `frontend/src/components/exceptions/exceptions-table.test.tsx` — updated Test 5 + 4 new tests for the confirm-then-mutate flow
- `frontend/src/components/vulnerabilities/drill-panel.test.tsx` — new hook mocks (use-exception-mutations/use-asset-groups/use-assignable-users) + 1 new behavioral test
- `frontend/src/components/vulnerabilities/drill-panel-mobile.test.tsx` — same 3 new hook mocks (defensive parity, no dialog-opening test added there)
- `.planning/phases/39-exception-risk-acceptance-workflow/deferred-items.md` — logs the mobile Drawer-nesting trade-off (not fixed, out of scope)

## Decisions Made

See frontmatter `key-decisions` for the full list with rationale. Summary: the approver-combobox widens a shared type locally rather than editing an out-of-scope file; the grant dialog deliberately has no CVE field (ASSET/ASSET_GROUP reuse the finding's own CVE); two defensive scope-target guards were added beyond the literal plan text; `useGrantException`'s onError toast is literal fidelity to the "mirrors useStartCampaign" instruction even though it's a secondary signal alongside the dialog's own error UI; the mobile Drawer-nesting trade-off is documented, not fixed; EXC-01 stays unmarked pending 39-08 per this phase's now four-times-independently-confirmed convention.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Pre-existing drill-panel test suites crashed once the Actions section always renders `<ExceptionGrantDialog>`**
- **Found during:** Task 3
- **Issue:** `drill-panel.test.tsx`/`drill-panel-mobile.test.tsx` already mock every OTHER real query/mutation hook `DrillContent` uses (to avoid needing a `QueryClientProvider`) — the new dialog transitively calls 3 more real hooks (`useGrantException`, `useAssetGroupsList`, and `useAssignableUsers` via `ApproverCombobox`) that weren't mocked, crashing all 57 tests across both files with "No QueryClient set."
- **Fix:** Added mocks for all 3 new hooks in both files, mirroring the exact established comment/pattern already used for every other hook mock in those suites; added one new behavioral test proving both trigger buttons open the dialog with the right type/scope defaults.
- **Files modified:** `drill-panel.test.tsx`, `drill-panel-mobile.test.tsx`
- **Verification:** both suites green (59 + 58 tests respectively) after the fix
- **Committed in:** `a5b98e3` (Task 3 commit)

**2. [Rule 1 - Bug] `exceptions-table.test.tsx`'s "Revoke button renders disabled" test was now factually wrong**
- **Found during:** Task 3
- **Issue:** the pre-existing test asserted Revoke is ALWAYS disabled — 39-06's own documented placeholder behavior. Wiring the real mutation makes an ACTIVE row's Revoke button enabled by design; leaving the old assertion in place would be a permanently-incorrect test masking real behavior.
- **Fix:** Split into "enabled for an active row" + "disabled for historical rows" tests, and added a `useRevokeException` mock (mirrors `reassign-combobox.test.tsx`'s `useReassignAsset` mock) plus 3 new tests for the confirm-then-mutate flow, `stopPropagation`, and Cancel.
- **Files modified:** `exceptions-table.test.tsx`
- **Verification:** 12/12 tests green
- **Committed in:** `a5b98e3`

**3. [Rule 1 - Bug] My own `approver-combobox.tsx` docstring and test tripped the file's own Pitfall-6 grep gate**
- **Found during:** Task 1
- **Issue:** descriptive header-comment prose named "reassign-combobox.tsx" and literally wrote `useReassignAsset` to explain what was deliberately NOT reproduced — a naive substring test (mirroring the plan's own literal verification gate) flagged the file, reproducing the exact false-positive class 39-06-SUMMARY.md already documented for its own "useRouter" mention.
- **Fix:** Reworded the docstring to describe the same constraint without the literal identifier, and fixed my own test to check for an actual `import` statement rather than a bare substring. The plan's real verification gate (`grep -c "useReassignAsset"`) now correctly returns 0.
- **Files modified:** `approver-combobox.tsx`, `approver-combobox.test.tsx`
- **Verification:** grep gate 0; full 10-test suite green
- **Committed in:** `8757fdd`

**4. [Rule 2 - Missing Critical] "This asset"/"Asset group" scope options needed a target-availability guard**
- **Found during:** Task 2
- **Issue:** the plan's action text didn't specify what happens when a vulnerability has no linked asset (`asset_id` null) or no CVE (`cve_id` null) — without a guard, selecting "This asset" with no `asset_id`, or either target-scope with no `cve_id`, would submit a payload with an empty-string `asset_id`/`cve_id`, silently creating a malformed exception record instead of failing loudly.
- **Fix:** Disabled the "This asset" segmented-control option when `finding.assetId` is falsy, and disabled both "This asset"/"Asset group" when `finding.cveId` is falsy.
- **Files modified:** `exception-grant-dialog.tsx`
- **Verification:** dedicated test ("This asset" scope option is disabled when the finding has no asset_id")
- **Committed in:** `d7ff511`

---

**Total deviations:** 4 auto-fixed (2 Rule 1 bugs, 1 Rule 2 missing-critical, 1 Rule 3 blocking).
**Impact on plan:** All four were necessary for correctness — two test-suite corrections forced by the new real hooks/wired behavior, one self-inflicted grep-gate false positive, one payload-integrity guard. No scope creep: none touch backend files, SLA subtraction, or the consumer sweep.

## Issues Encountered

- A new drill-panel.test.tsx assertion (`screen.getByText('Grant exception')`) initially matched TWO elements — the dialog's `<h2>` title and its "Grant exception" submit button share the identical literal string. Fixed by using `getByRole('heading', { name: 'Grant exception' })` to disambiguate.
- The mobile Drawer-nesting trade-off (ExceptionGrantDialog opens a plain, non-`NestedRoot` vaul drawer inside `DrillPanelMobile`'s outer drawer) is a documented, deliberate scope decision, not a bug — see Decisions above and `deferred-items.md`. It is fully functional (open/close/Esc/swipe all work), just without the ticket-confirm's cascading-scale gesture polish.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- EXC-01's grant surface is now complete end-to-end for all three scope types: backend resolution (39-01/39-02), the manage-only list view (39-06), and the grant/revoke UI (this plan).
- 39-08 (closing plan) can mark EXC-01/EXC-02/EXC-03/EXC-04 complete in REQUIREMENTS.md — this plan was the last outstanding frontend piece across the phase.
- Wave 4 (39-05, the second consumer-sweep plan) is now unblocked — STATE.md's own wave note said Wave 4 needed full Wave 3 completion (39-01/39-02/39-03/39-06/**39-07**), not just 39-03.
- No blockers. `npx tsc --noEmit` clean project-wide; `eslint` clean on every touched file; full regression sweep 153 test files / 1074 tests green (pre-existing jsdom/axe-core canvas warnings are unrelated environment noise, not failures).

## Known Stubs

None — this plan fully resolves 39-06's own documented "Known Stubs" entry (the disabled Revoke placeholder in `exceptions-table.tsx`).

## Self-Check: PASSED

- `frontend/src/components/exceptions/approver-combobox.tsx` — FOUND
- `frontend/src/components/exceptions/approver-combobox.test.tsx` — FOUND
- `frontend/src/lib/queries/use-exception-mutations.ts` — FOUND
- `frontend/src/lib/queries/use-exception-mutations.test.ts` — FOUND
- `frontend/src/components/exceptions/exception-grant-dialog.tsx` — FOUND
- `frontend/src/components/exceptions/exception-grant-dialog.test.tsx` — FOUND
- `frontend/src/components/vulnerabilities/microcopy.ts` — FOUND
- `frontend/src/components/vulnerabilities/drill-content.tsx` — FOUND
- `frontend/src/components/exceptions/exceptions-table.tsx` — FOUND
- `frontend/src/components/exceptions/exceptions-table.test.tsx` — FOUND
- `frontend/src/components/vulnerabilities/drill-panel.test.tsx` — FOUND
- `frontend/src/components/vulnerabilities/drill-panel-mobile.test.tsx` — FOUND
- `.planning/phases/39-exception-risk-acceptance-workflow/deferred-items.md` — FOUND
- Commit `8757fdd` — FOUND in git log
- Commit `d7ff511` — FOUND in git log
- Commit `a5b98e3` — FOUND in git log

---
*Phase: 39-exception-risk-acceptance-workflow*
*Completed: 2026-08-19*
