---
phase: 39-exception-risk-acceptance-workflow
plan: 06
subsystem: ui
tags: [nextjs, react, typescript, tanstack-query, tailwind, exceptions, risk-acceptance, state-patterns]

# Dependency graph
requires:
  - phase: 39-01
    provides: "the exceptions module (ExceptionRecord/ExceptionResponse), GET /api/v1/exceptions (require_viewer, tenant-scoped, all scope types), the Pattern 4 lazy-audit sweep run on every list read"
  - phase: 39-02
    provides: "full ASSET/ASSET_GROUP scope resolution -- ExceptionResponse's raw scope_type/cve_id/vulnerability_id/asset_id/asset_group_id fields this plan's table renders"
  - phase: 38-04
    provides: "the campaigns list page/table/chip-bar/query-hook pattern this plan directly clones (ErrorBoundary>Suspense>Inner, WR-13 branch order, ChipAxis descriptor model, staleTime:0 compute-on-read hook shape)"
provides:
  - "/dashboard/exceptions manage-only list page: two client-computed empty states (never-granted vs filtered-to-zero), skeleton loading, PartialFailureBanner error, client-side chip-bar filtering + free-text CVE search + client-side pagination (25/page)"
  - "ExceptionsTable: Type/CVE-target/Scope/Approver/Granted/Expires/Revoke columns, default-ascending Expires sort (D-19) with header-click toggle, stable equal-expiry tiebreak, LOCAL inline-accordion row expand (justification + audit metadata), never navigates"
  - "ExceptionsChipBar: Type (False positive/Accept risk) + Scope (Finding/Asset/Asset group) axes, hardcoded allow-list clamps"
  - "useExceptions() query hook (staleTime:0, retry:1) + queryKeys.exceptions.{all,list} block"
  - "WORKFLOW_ITEMS sidebar entry: Exceptions (ShieldOff icon, after Campaigns, no chip)"
affects: [39-07-frontend, 39-08-closing-plan]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Client-side filter+search+pagination over a full unfiltered GET response, mirroring campaigns' no-server-pagination precedent (Phase 38) but adding a local (non-URL) page cursor + Pagination footer since this list's own UI-SPEC anticipates higher cardinality than campaigns"
    - "Pre-check-then-delegate SLA rendering: a lapsed/revoked guard branch runs BEFORE handing off to the shared SlaPill component, so the shared component's own tier math is reused verbatim and can only ever produce its two non-overdue tiers here -- no second, hand-rolled tier formula"
    - "Row-level inline-accordion expand (local component state, Fragment-per-row keying) as a deliberate, UI-SPEC-approved alternative to the drill-panel pattern for small (4-field) records"

key-files:
  created:
    - frontend/src/lib/queries/use-exceptions.ts
    - frontend/src/components/exceptions/exceptions-chip-bar.tsx
    - frontend/src/components/exceptions/exceptions-table.tsx
    - frontend/src/components/exceptions/exceptions-table.test.tsx
    - "frontend/src/app/(authed)/dashboard/exceptions/page.tsx"
    - "frontend/src/app/(authed)/dashboard/exceptions/page.test.tsx"
  modified:
    - frontend/src/lib/queries/keys.ts
    - frontend/src/components/shell/nav-items.ts
    - .planning/phases/39-exception-risk-acceptance-workflow/deferred-items.md

key-decisions:
  - "Row click toggles a LOCAL inline-accordion expand, not a drill panel or navigation -- a deliberate, phase-specific override of the general sketch-findings interaction-patterns.md anti-pattern ('don't put drill-down inside row expansion'), justified in the checker-approved 39-UI-SPEC.md by the record's small 4-field shape (avoids a redundant modal-inside-modal)"
  - "The 'CVE / target' column shows cve_id only, with the scope-specific raw asset_id/asset_group_id surfaced via a title tooltip -- ExceptionResponse has no resolved hostname/group-name join (39-01/39-02's own documented scope boundary); inventing a fake human-readable target label was rejected as untested, out-of-contract UI"
  - "Expires column reuses the real SlaPill component verbatim for active rows via a pre-check branch (revoked_at set, or expires_at already lapsed, renders first) -- SlaPill's own computeTier() can only ever return 'soon'/'ok' here, never 'overdue', satisfying the UI-SPEC rule that an active exception is never overdue without re-deriving the tier formula"
  - "Revoke renders a hand-rolled disabled 34x34 placeholder, not <Button variant=\"icon\">, after discovering that variant's default size:'md' padding compounds with its fixed h-[34px] w-[34px] box (near-zero content area under border-box sizing) -- logged to deferred-items.md as a pre-existing components/ui/button.tsx bug, not fixed (out of this plan's files_modified)"
  - "Client-side local (non-URL) page-cursor pagination added, deviating from campaigns' page (Phase 38, which ships none) -- 39-UI-SPEC.md's own mockup shows a Pagination footer for this list, anticipating higher-cardinality growth"
  - "Two distinct empty states computed client-side: never-granted (backend returned zero rows for the tenant, regardless of filters) vs. filtered-to-zero (rows exist but the active chip/search filter excludes all of them) -- campaigns' single combined empty branch didn't need this distinction, but 39-UI-SPEC.md's Copywriting Contract requires two different copies here"
  - "joinConjunction() generalizes the UI-SPEC's literal 2-chip 'both X and Y' filtered-empty template to 1 or 3+ simultaneously active filter dimensions (type/scope/search) -- the verbatim template is preserved exactly for the demonstrated 2-chip case"
  - "PartialFailureBanner is reused with no source prop, rendering its default 'Some data is incomplete' title rather than the UI-SPEC's literal 'Exceptions failed to load' -- the shared component has no title-override prop; this plan's own must_haves wording only requires 'PartialFailureBanner verbatim (HTTP code + request ID + Retry now)', which is satisfied exactly, matching campaigns/page.tsx's identical precedent"
  - "EXC-02/EXC-03 left [ ] unmarked in REQUIREMENTS.md -- 39-08 remains the sole plan claiming all four EXC-01..04 and the phase's designated last declaring plan (39-01/39-02 precedent); this plan ships only the read/manage-only viewing surface, not grant/revoke UI"
  - "Added exceptions-table.test.tsx and page.test.tsx (not in the plan's files_modified) mirroring campaigns-table.test.tsx / campaigns/page.test.tsx's co-located test convention -- proves the sort/expand/WR-13/empty-copy must_haves rather than leaving them unverified"

patterns-established:
  - "Manage-only list surfaces (view + row action, no create CTA) mirror the campaigns list's ErrorBoundary>Suspense>Inner + WR-13 branch-order shape, but may add a THIRD empty-state branch (never-granted vs filtered-to-zero) when the phase's own UI-SPEC calls for distinct copy for each"

requirements-completed: []  # EXC-02/EXC-03 span multiple plans in this phase; 39-08 is the last declaring plan (see key-decisions)

# Metrics
duration: 28min
completed: 2026-08-19
---

# Phase 39 Plan 06: Exceptions List Frontend Summary

**Manage-only `/dashboard/exceptions` list surface (page + sortable/expandable table + two-axis chip-bar + query hook + sidebar entry), reusing the campaigns list (Phase 38) as the direct structural analog and the checker-approved 39-UI-SPEC.md as the locked visual contract.**

## Performance

- **Duration:** 28 min
- **Started:** 2026-08-19T07:51:00Z
- **Completed:** 2026-08-19T08:19:00Z
- **Tasks:** 3/3
- **Files modified:** 9 (6 created, 3 modified)

## Accomplishments

- `useExceptions()` hook (`staleTime: 0`, `retry: 1`) + `queryKeys.exceptions.{all,list}` block, mirroring `useCampaigns()`'s compute-on-read reasoning — an exception's active/expiring-soon state has zero persisted snapshot on the backend
- `WORKFLOW_ITEMS` gains an "Exceptions" sidebar entry (`ShieldOff`, after Campaigns, no live-count chip per D-N-01)
- `ExceptionsTable`: the full UI-SPEC column set (Type pill · CVE/target mono · Scope · Approver avatar+name · Granted relative · Expires sla-pill · Revoke), default-ascending Expires sort with a stable equal-timestamp tiebreak and a header-click direction toggle, and a local inline-accordion row expand that never imports a navigation hook
- `ExceptionsChipBar`: Type + Scope axes with hardcoded allow-list clamps (T-39-22)
- `/dashboard/exceptions` page: WR-13 mutually-exclusive state branches (error > loading > never-granted-empty > filtered-to-zero-empty > data), client-side filtering + free-text search + client-side pagination (sitewide 25/page) over the full `GET /api/v1/exceptions` response
- 12 new frontend tests (8 table + 4 page) proving sort/toggle/expand/disabled-Revoke/historical-chip behavior and the WR-13 branch order + both empty-state copies

## Task Commits

Each task was committed atomically:

1. **Task 1: query hook + keys + nav entry** - `1234c54` (feat)
2. **Task 2: exceptions table (sortable, inline-expand) + two-axis chip-bar** - `6d4e95f` (feat)
3. **Task 3: exceptions list page with all state branches** - `6df7b70` (feat)

**Plan metadata:** _pending — this commit follows_

## Files Created/Modified

- `frontend/src/lib/queries/use-exceptions.ts` - `useExceptions()` hook + `ExceptionResponse`/`ExceptionType`/`ExceptionScopeType` types mirroring the backend schema
- `frontend/src/components/exceptions/exceptions-chip-bar.tsx` - Type + Scope two-axis `<ChipBar>` composition
- `frontend/src/components/exceptions/exceptions-table.tsx` - sortable/expandable table, no navigation
- `frontend/src/components/exceptions/exceptions-table.test.tsx` - 8 tests (headers, sort default+toggle, expand toggle x2, disabled Revoke, historical muted chips, no-router source guard)
- `frontend/src/app/(authed)/dashboard/exceptions/page.tsx` - list page, all state branches
- `frontend/src/app/(authed)/dashboard/exceptions/page.test.tsx` - 4 tests (row rendering, WR-13 mutual exclusivity, both empty-state copies + Clear-all-filters)
- `frontend/src/lib/queries/keys.ts` - `exceptions.{all,list}` block added
- `frontend/src/components/shell/nav-items.ts` - `ShieldOff` import + `WORKFLOW_ITEMS` entry
- `.planning/phases/39-exception-risk-acceptance-workflow/deferred-items.md` - logs a pre-existing `components/ui/button.tsx` icon-variant padding bug, discovered but not fixed (out of scope)

## Decisions Made

See frontmatter `key-decisions` for the full list with rationale. Summary: the inline-accordion row expand deliberately overrides the general sketch-findings drill-down anti-pattern per the phase's own checker-approved UI-SPEC; the CVE/target column and PartialFailureBanner title both fall back to the closest-available real data/component rather than inventing unbacked UI; client-side pagination is a genuine (UI-SPEC-driven) deviation from the campaigns analog; EXC-02/EXC-03 stay unmarked pending 39-08.

## Deviations from Plan

### Auto-fixed Issues

None — no bugs, missing-critical gaps, or blocking issues were found in code this plan touched that required a Rule 1/2/3 fix. The `components/ui/button.tsx` `variant="icon"` padding issue (see Decisions) was discovered but is a **pre-existing** bug in a file outside this plan's `files_modified`, so it was worked around (hand-rolled markup) rather than fixed in place, per the SCOPE BOUNDARY rule, and logged to `deferred-items.md`.

---

**Total deviations:** 0 auto-fixed. One pre-existing out-of-scope bug discovered and logged (not fixed).
**Impact on plan:** None — the discovered bug was avoided entirely by not using the affected code path.

## Issues Encountered

- The self-authored `exceptions-table.tsx` module docstring initially used the literal word "useRouter" to explain that the table never imports it — this tripped the plan's own literal `<verification>` grep gate (`grep -c useRouter == 0`), which does a naive whole-file substring search. Reworded the comment to describe the same constraint without the literal identifier; the gate now passes (0) while the semantic guarantee (and the companion test's source-file regex assertion) is unchanged.
- Two initial test assertions in `exceptions-table.test.tsx` used raw `element.dispatchEvent(...)` instead of Testing Library's `fireEvent`, so the resulting React state update (sort-direction toggle, accordion expand) hadn't flushed by the time the assertion ran (no implicit `act()` wrap around a bare `dispatchEvent`). Switched to `fireEvent.click`/`fireEvent.keyDown`; all 8 tests pass. A separate test also assumed a `data-col` attribute existed on table body `<td>` cells (it only exists on `<th>` headers, matching the campaigns-table.tsx precedent) — fixed by deriving row order from `tr[tabindex="0"]` DOM order instead.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 07 (`depends_on: [39-01, 39-02, 39-06]`) is now unblocked: the exception-grant-dialog + approver-combobox + `use-exception-mutations.ts` frontend can proceed, and its revoke mutation has an exact landing spot — swap the disabled placeholder `<button>` in `ExceptionsTable`'s Revoke `<td>` for a real `ConfirmModal`-gated mutation call.
- Plan 08 (closing plan) can mark EXC-02/EXC-03 complete once Plan 07 ships the grant/revoke UI half.
- No blockers. `npx tsc --noEmit` clean project-wide; `eslint` clean on every touched file; both plan-mandated grep gates pass (0 `useRouter` occurrences in the table, ≥1 `/dashboard/exceptions` occurrence in nav-items.ts); full regression sweep (exceptions + campaigns + shell suites) 50/50 green.

## Known Stubs

- `frontend/src/components/exceptions/exceptions-table.tsx` — the per-row Revoke button (inside the `<td data-col="revoke">` cell) is a disabled, non-functional placeholder (`title="Revoke — coming soon"`). This is explicitly plan-sanctioned (Task 2's action text: "render a disabled placeholder if the mutation hook is not yet present") since Plan 07, which owns the revoke mutation + `ConfirmModal` wiring, has not yet executed. Resolved automatically once Plan 07 ships — no further 39-06 changes needed.

## Self-Check: PASSED

- `frontend/src/lib/queries/use-exceptions.ts` — FOUND
- `frontend/src/components/exceptions/exceptions-chip-bar.tsx` — FOUND
- `frontend/src/components/exceptions/exceptions-table.tsx` — FOUND
- `frontend/src/components/exceptions/exceptions-table.test.tsx` — FOUND
- `frontend/src/app/(authed)/dashboard/exceptions/page.tsx` — FOUND
- `frontend/src/app/(authed)/dashboard/exceptions/page.test.tsx` — FOUND
- Commit `1234c54` — FOUND in git log
- Commit `6d4e95f` — FOUND in git log
- Commit `6df7b70` — FOUND in git log

---
*Phase: 39-exception-risk-acceptance-workflow*
*Completed: 2026-08-19*
