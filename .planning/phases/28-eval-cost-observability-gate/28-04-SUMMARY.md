---
phase: 28-eval-cost-observability-gate
plan: 04
subsystem: ui
tags: [react, tanstack-query, radix-ui, shadcn, tailwind, settings-pane, admin-ui, ai]

# Dependency graph
requires:
  - phase: 28-03
    provides: "GET /api/v1/ai/usage — the locked, require_admin-gated response contract this pane consumes verbatim (configured/model/monthly_budget_usd/spent_this_month_usd/breaker_tripped/capability_breakdown/degraded_calls_count)"
provides:
  - "The AIE-04 admin pane: frontend/src/components/settings/ai-usage-pane.tsx, a new admin-only 'AI usage & settings' settings category"
  - "useAiUsage() hook + queryKeys.ai.usage() — the single-query data layer for the pane"
  - "A restyled shadcn progress primitive (frontend/src/components/ui/progress.tsx) — the budget meter, sunset-tokenized"
  - "3 registration edits wiring the admin-only 'ai' category into the existing settings shell (microcopy.ts, settings-sidebar-shell.tsx, settings/page.tsx)"
affects: []

# Tech tracking
tech-stack:
  added: ["@radix-ui/react-progress"]
  patterns:
    - "shadcn 'add official primitive + restyle with sunset tokens' precedent extended to progress, matching the tooltip.tsx/textarea.tsx precedent exactly"
    - "Hardcoded fixed-length row-mapping array (not derived from the API response array's length) as a structural backstop guaranteeing a table can never grow an unplanned row"
    - "Model family-name substring matching (sonnet/opus/haiku), never the exact raw model id, so a display-label lookup never has to embed the raw id literal in the file"
    - "Recreate module-private chrome (DegradedCard, SyncStatusPill) as local, file-scoped equivalents rather than importing — the established pattern for reusing a sibling component's visual recipe without exporting its internals"

key-files:
  created:
    - frontend/src/lib/queries/use-ai-usage.ts
    - frontend/src/components/ui/progress.tsx
    - frontend/src/components/settings/ai-usage-pane.tsx
    - frontend/src/components/settings/ai-usage-pane.test.tsx
  modified:
    - frontend/src/lib/queries/keys.ts
    - frontend/src/components/settings/microcopy.ts
    - frontend/src/components/settings/settings-sidebar-shell.tsx
    - frontend/src/components/settings/settings-sidebar-shell.test.tsx
    - frontend/src/app/(authed)/dashboard/settings/page.tsx
    - frontend/package.json
    - frontend/package-lock.json

key-decisions:
  - "Status and Budget rendered as two h2-labeled sub-sections inside ONE bordered card (not two separate outer-bordered cards) — reconciles 28-UI-SPEC.md's Spacing section naming Status/Budget as 2 of 'the pane's 4 distinct cards' with the plan Task's own literal 'Status + Budget row' single-section action text"
  - "Key & model's 'Connector: Enabled/Disabled' field is derived from the locked endpoint's own `configured` boolean, not a separate is_enabled query — the locked response carries no is_enabled field, and neither get_tenant_anthropic_key() nor get_model_and_budget() consult ConnectorConfig.is_enabled either, so configured is the practically-accurate proxy without inventing a new field or backend query"
  - "Model label matched by case-insensitive family-name substring (sonnet/opus/haiku), never the exact raw model id — satisfies the 'no raw claude- literal' acceptance grep on the pane file itself while staying correct across any future dated-suffix model id"
  - "The 6-row usage-by-capability table is a hardcoded, fixed-length local array, never derived from the API response array's length — guarantees exactly 6 rows always render and makes a fabricated/future 7th 'ticket-draft' row structurally impossible to display"

patterns-established:
  - "Admin-only settings category registration: 3-file edit (microcopy Category+labels, sidebar-shell ALL_CATEGORIES+ADMIN_ONLY, page.tsx allow-list+renderPane case) with zero new gating code — backend require_admin remains the sole authoritative gate"

requirements-completed: [AIE-04]

coverage:
  - id: D1
    description: "New admin-only 'ai' settings category is registered and reachable (sidebar + page routing), gated by the existing ADMIN_ONLY/RBAC mechanism with zero new gating code"
    requirement: "AIE-04"
    verification:
      - kind: unit
        ref: "settings-sidebar-shell.test.tsx#Test 2: ADMIN role renders all 7 categories"
        status: pass
      - kind: unit
        ref: "settings-sidebar-shell.test.tsx#Test 1: VIEWER role renders only Profile and API tokens"
        status: pass
    human_judgment: false
  - id: D2
    description: "AiUsagePane renders all 4 UI-SPEC cards (Status, Budget, Usage-by-capability, Key & model) for a configured, non-tripped tenant, including a restyled progress meter"
    requirement: "AIE-04"
    verification:
      - kind: unit
        ref: "ai-usage-pane.test.tsx#renders exactly 6 fixed capability rows with the locked labels (ticket-draft backstop: no 7th row)"
        status: pass
      - kind: unit
        ref: "ai-usage-pane.test.tsx#renders a progress meter when a cap is set"
        status: pass
    human_judgment: false
  - id: D3
    description: "Breaker-tripped amber banner renders only when breaker_tripped, positioned as the pane's first/anchor element, with the locked copy + 'Raise the cap' -> /dashboard/connectors link"
    requirement: "AIE-04"
    verification:
      - kind: unit
        ref: "ai-usage-pane.test.tsx#renders the breaker-tripped banner as the anchor, above the rest of the pane, when breaker_tripped"
        status: pass
      - kind: unit
        ref: "ai-usage-pane.test.tsx#does not render the breaker-tripped banner when breaker_tripped is false"
        status: pass
    human_judgment: false
  - id: D4
    description: "Usage-by-capability table always renders exactly the 6 locked rows; a fabricated/future 7th row (e.g. a ticket-draft resource_type) can never surface — the ticket-draft attribution backstop"
    requirement: "AIE-04"
    verification:
      - kind: unit
        ref: "ai-usage-pane.test.tsx#renders exactly 6 fixed capability rows with the locked labels (ticket-draft backstop: no 7th row)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Every non-populated UI-SPEC state is covered: loading pulse, error banner, no-key whole-pane replacement, zero-usage (4 cards still render, not an empty screen), no-cap (no meter bar + caption)"
    requirement: "AIE-04"
    verification:
      - kind: unit
        ref: "ai-usage-pane.test.tsx#shows the \"AI isn't set up yet\" card when no key is configured"
        status: pass
      - kind: unit
        ref: "ai-usage-pane.test.tsx#renders PartialFailureBanner on a query error"
        status: pass
      - kind: unit
        ref: "ai-usage-pane.test.tsx#renders all-zero rows (not an empty screen) when usage is zero for the month"
        status: pass
      - kind: unit
        ref: "ai-usage-pane.test.tsx#renders no meter bar + the no-cap caption when monthly_budget_usd is null"
        status: pass
    human_judgment: false
  - id: D6
    description: "Model displayed as its short enum label (Sonnet 5/Opus 5/Haiku), never the raw model id; every Stat instance passes delta={0} with no stray 'Δ —' placeholder"
    requirement: "AIE-04"
    verification:
      - kind: unit
        ref: "ai-usage-pane.test.tsx#shows the model as its enum label, never the raw model id"
        status: pass
      - kind: unit
        ref: "ai-usage-pane.test.tsx#every Stat renders with delta={0} — no stray \"Δ —\" placeholder"
        status: pass
      - kind: other
        ref: "grep -cE '#[0-9A-Fa-f]{6}' ai-usage-pane.tsx == 0; grep -c 'claude-' ai-usage-pane.tsx == 0"
        status: pass
    human_judgment: false
  - id: D7
    description: "Visual fidelity to 28-UI-SPEC.md's exact chrome (spacing scale, sunset color tokens, card layout, typography) as rendered in a real browser on both themes"
    requirement: "AIE-04"
    verification: []
    human_judgment: true
    rationale: "Only jsdom unit tests were run this plan (no live browser render, screenshot, or axe accessibility sweep) — pixel/token-level visual fidelity, light/dark theme rendering, and the exact 'primary visual anchor' hierarchy as a human actually perceives it need a live browser or Playwright+axe pass to confirm, consistent with this project's own 'axe sweep not run during execution' lesson (no screen in this codebase should have unverified visual claims)."

# Metrics
duration: 36min
completed: 2026-08-03
status: complete
---

# Phase 28 Plan 04: AIE-04 Admin Usage/Cost/Settings Pane Summary

**A new admin-only "AI usage & settings" settings category rendering month-to-date cost vs budget (restyled shadcn `progress` meter), a hardcoded 6-row per-capability breakdown, the breaker status (amber banner + pill), and a read-only key/model summary linking out to Connectors — consuming Plan 03's locked `GET /api/v1/ai/usage` contract verbatim.**

## Performance

- **Duration:** 36 min
- **Started:** 2026-08-03T08:57:00Z (approx, immediately following 28-03)
- **Completed:** 2026-08-03T09:32:39Z
- **Tasks:** 2 completed
- **Files modified:** 11 (4 created, 7 modified)

## Accomplishments

- **`use-ai-usage.ts` + `queryKeys.ai.usage()`:** a single admin-gated `useQuery()` mirroring `use-ai-status.ts`'s exact shape, consuming Plan 03's response fields verbatim (`configured`/`model`/`monthly_budget_usd`/`spent_this_month_usd`/`breaker_tripped`/`capability_breakdown`/`degraded_calls_count`) — no invented fields.
- **`progress.tsx`:** the shadcn `add` CLI's own install step hit the documented lucide/React19 peer conflict; installed `@radix-ui/react-progress` directly with `--legacy-peer-deps` (the established package.json-override precedent), then hand-wrote the component from the CLI's `--view`-previewed template, restyled to sunset tokens (`bg-surface-2` track, caller-driven `indicatorClassName` for the SLA 3-tier fill — no hardcoded indicator color, since the same primitive needs green/amber/red per instance).
- **Registration (3 files):** `microcopy.ts` (`'ai'` Category + `'AI usage & settings'` label), `settings-sidebar-shell.tsx` (`ALL_CATEGORIES` + `ADMIN_ONLY`), `settings/page.tsx` (allow-list + `renderPane` case + import) — zero new gating code, mirrors the existing `workspace`/`saml`/`notifications`/`audit` admin-only precedent exactly.
- **`ai-usage-pane.tsx` (the pane):** breaker-tripped amber banner (recreated `DegradedCard`-style chrome, the primary visual anchor when tripped, positioned first); a combined Status+Budget card (recreated 3-state `SyncStatusPill` recipe + two `Stat` tiles each with `delta={0}` + the restyled `progress` meter with SLA 3-tier fill, or the no-cap caption with no bar); a Usage-by-capability card with a **hardcoded 6-row table** (never derived from the API array's length, so a stray/future "ticket-draft" row can structurally never appear — the UI-SPEC's ticket-draft backstop); a Key & model card with a family-name-substring model label (never the raw id) and a "Manage in Connectors" link-out (D-05 — no key/model/budget edit UI rebuilt here).
- **Every UI-SPEC state covered:** loading (lightweight pulse, not a heavy `SkeletonTable`), error (`PartialFailureBanner` verbatim), no-key (whole-pane "AI isn't set up yet" replacement), zero-usage (the 4 cards still render with zero-value shapes + a "No AI usage yet" notice), no-cap (no meter bar), breaker-tripped (amber anchor banner).
- **`ai-usage-pane.test.tsx`:** 10 new tests — 6-row + ticket-draft backstop, breaker banner present/absent + anchor position, no-cap no-meter, zero-usage all-zero rows, no-key card, query error, model label, no stray delta placeholder.
- **Deviation caught in full-suite regression:** Task 1's registration edit (adding the 7th admin-only `'ai'` category) invalidated 3 hardcoded category-count assertions in the pre-existing `settings-sidebar-shell.test.tsx` (6→7 total, 5→6 inactive). Fixed as a direct, in-scope consequence — see Deviations below.

## Task Commits

Each task was committed atomically:

1. **Task 1: query key + useAiUsage hook + progress primitive + 3 registration edits** - `6ac6fec` (feat)
2. **Task 2: ai-usage-pane.tsx (4 cards) + pane test** - `cc4f62e` (feat)

**Deviation fix (found during post-task full-suite regression):** `f1a0a47` (fix)

**Plan metadata:** (this commit) `docs(28-04): complete AIE-04 admin usage/cost/settings pane plan`

## Files Created/Modified

- `frontend/src/lib/queries/use-ai-usage.ts` - `useAiUsage()` hook + `AiUsageResult`/`AiUsageCapabilityRow` types (locked response shape)
- `frontend/src/components/ui/progress.tsx` - restyled shadcn `Progress` (sunset tokens, caller-driven indicator color) — the budget meter
- `frontend/src/components/settings/ai-usage-pane.tsx` - the AIE-04 admin pane (4 cards + every UI-SPEC state)
- `frontend/src/components/settings/ai-usage-pane.test.tsx` - 10-case test suite
- `frontend/src/lib/queries/keys.ts` - added `usage: () => ['ai','usage']` to the existing `ai` key block
- `frontend/src/components/settings/microcopy.ts` - added `'ai'` Category + `CATEGORY_LABELS.ai`
- `frontend/src/components/settings/settings-sidebar-shell.tsx` - added `'ai'` to `ALL_CATEGORIES` + `ADMIN_ONLY`
- `frontend/src/components/settings/settings-sidebar-shell.test.tsx` - updated 3 category-count assertions (6→7, 5→6) for the new admin-only category
- `frontend/src/app/(authed)/dashboard/settings/page.tsx` - added `'ai'` to the allow-list + `AiUsagePane` import + `renderPane` case
- `frontend/package.json` / `frontend/package-lock.json` - added `@radix-ui/react-progress`

## Decisions Made

- Status and Budget rendered as two h2-labeled sub-sections inside one bordered card, reconciling 28-UI-SPEC.md's "4 distinct cards" Spacing-section wording with the plan Task's own literal "Status + Budget row" single-section action text — both card titles still render verbatim.
- "Connector: Enabled/Disabled" derived from the locked endpoint's own `configured` boolean (no separate `is_enabled` query invented) — the locked `GET /api/v1/ai/usage` response carries no `is_enabled` field, and neither `get_tenant_anthropic_key()` nor `get_model_and_budget()` consult `ConnectorConfig.is_enabled` either, so `configured` is the practically-accurate, contract-faithful proxy.
- Model label matched by case-insensitive family-name substring (`sonnet`/`opus`/`haiku`), never the exact raw model id — satisfies the "no raw `claude-` literal" acceptance grep on the pane file itself (a literal id-keyed lookup table would have failed it) while staying correct across any future dated-suffix model id.
- The 6-row usage-by-capability table is a hardcoded, fixed-length local array — never derived from the API response array's length — so a fabricated/future 7th row can structurally never render, regardless of what the backend ever returns.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `settings-sidebar-shell.test.tsx` category-count assertions invalidated by the new admin category**
- **Found during:** Post-Task-2 full frontend regression run (`npx vitest run`), before writing this Summary
- **Issue:** Task 1's registration edit appends `'ai'` to `ALL_CATEGORIES`/`ADMIN_ONLY` (7 total categories now, 6 previously). Three pre-existing tests hardcoded the old count: "ADMIN role renders all 6 categories" (expected `buttons.length === 6`), the OWNER-role equivalent, and the active/inactive-button-count test (expected 5 inactive, now 6).
- **Fix:** Updated the 3 assertions (6→7 total buttons, 5→6 inactive buttons) and added `'AI usage & settings'` to the expected label list in the two renamed test cases. No production code touched.
- **Files modified:** `frontend/src/components/settings/settings-sidebar-shell.test.tsx`
- **Verification:** Full suite re-run green: 133 test files / 899 tests passed (0 failed).
- **Committed in:** `f1a0a47`

---

**Total deviations:** 1 auto-fixed (1 Rule 1 — bug, a stale test assumption directly invalidated by this plan's own registration change).
**Impact on plan:** None beyond the fix itself — a necessary, minimal, test-only correction with zero production-code impact. No scope creep.

## Issues Encountered

- The `npx shadcn add progress` CLI's own dependency-install step failed with the documented lucide-react/React19 `ERESOLVE` peer conflict (the same class of conflict this repo has hit before — Phase 15-01/18-00 both used `--legacy-peer-deps`). Resolved by installing `@radix-ui/react-progress` directly with `--legacy-peer-deps`, then hand-authoring `progress.tsx` from the exact template the CLI's `--view` flag previewed (so the restyle is byte-faithful to what `shadcn add` would have generated, before the sunset-token hand-edit).
- A UI-SPEC/Task-text tension surfaced during implementation: 28-UI-SPEC.md's Spacing section names "Status" and "Budget" among "the pane's 4 distinct cards," while the plan Task's own `<action>` text groups them as one "Status + Budget row." Resolved (see Decisions above) as one bordered card with two h2-labeled sub-sections — satisfies both documents' literal wording without contradicting either.
- The `GET /api/v1/ai/usage` locked response contract has no `is_enabled` field for the Key & model card's "Connector: Enabled/Disabled" row (28-UI-SPEC.md assumed one). Resolved by deriving it from `configured` rather than inventing a new field/query (see Decisions above) — per the critical constraint to consume the exact locked response shape without inventing fields.

## User Setup Required

None - no external service configuration required. `@radix-ui/react-progress` is a public npm package already resolved via the existing registry access; no secrets or env vars introduced.

## Next Phase Readiness

- AIE-04 is now fully `[x]` Complete in `REQUIREMENTS.md` — both declaring plans (28-03 backend, 28-04 frontend) are done, clearing the shared-ID gate.
- Phase 28 is now 4/5 plans complete. Plan 05 (AIE-01/02/03 CI wiring: `ci.yml` +3 jobs + `branch-protection.json` required-check registration) is the phase's final plan — no dependency on this plan's frontend work.
- Full frontend regression clean: `npx vitest run` reports 133/133 test files, 899/899 tests passing; `npx tsc --noEmit` clean; `npm run lint` (whole project) shows only pre-existing warnings in unrelated files (users/page.tsx, change-password/page.tsx, login/page.tsx, auth.tsx) untouched by this plan.
- Not yet verified: a live browser / Playwright+axe visual and accessibility sweep of the new pane (see coverage D7) — flagged as a human-judgment item, not silently claimed.

---
*Phase: 28-eval-cost-observability-gate*
*Completed: 2026-08-03*

## Self-Check: PASSED

All 4 claimed created files verified present on disk: `frontend/src/lib/queries/use-ai-usage.ts`, `frontend/src/components/ui/progress.tsx`, `frontend/src/components/settings/ai-usage-pane.tsx`, `frontend/src/components/settings/ai-usage-pane.test.tsx`. All 3 claimed commit hashes (`6ac6fec`, `cc4f62e`, `f1a0a47`) verified present in `git log --oneline --all`. Plan-level `<verification>` re-confirmed: new admin-only category renders the 4-card pane (settings-sidebar-shell test), every UI-SPEC state covered with 6 fixed rows and no fabricated ticket-draft row (ai-usage-pane test suite, 10/10 passing), inherited chrome only (`grep -cE '#[0-9A-Fa-f]{6}'` == 0, `grep -c 'claude-'` == 0, exactly one new primitive), breaker banner is the anchor when tripped and no-cap renders no meter (both directly asserted). Full regression: 899/899 frontend tests green, tsc clean.
