---
phase: 40-proactive-alerting-digests
plan: 05
subsystem: ui
tags: [nextjs, react, tanstack-query, tailwind, alerting, digests, settings]

# Dependency graph
requires:
  - phase: 40-proactive-alerting-digests
    provides: "Plan 01's Tenant.alerting_config + DEFAULT_ALERTING_CONFIG/merged_alerting_config contract; Plan 04's AlertingConfigUpdate PATCH branch + alerting_config GET exposure + POST /settings/alerting/test-digest (sent|empty|error)"
provides:
  - "The 'Alerting & Digests' settings pane (D-17) -- frontend/src/components/settings/alerting-digests-pane.tsx -- three section cards (New exposure alerts / Scheduled digests / Delivery channels), isOwner RBAC gate, mandatory loading/empty/error states, and a 'Send test digest' action wired to Plan 04's preview endpoint"
  - "Pane registration across microcopy.ts ('alerting' Category + CATEGORY_LABELS), settings-sidebar-shell.tsx (ALL_CATEGORIES + ADMIN_ONLY), and page.tsx (import + case 'alerting' + allow-list)"
  - "alerting_config added to the frontend TenantSettings/TenantSettingsPatch types (was missing, blocked compilation)"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Structural clone of sla-escalation-pane.tsx: same useAuth/useTenantSettings/useUpdateTenantSettings/useDirtyState/SaveBar/SkeletonTable/PartialFailureBanner/EmptyState composition, same isOwner disable-every-control RBAC gate, same data-pane test hook convention -- ToggleSwitch and the field-class tokens are duplicated locally (not exported from the SLA file) rather than imported, matching the plan's 'structural clone' instruction"
    - "Delivery-channel routing targets are derived from sla_config.channels (only channels already ENABLED under SLA & Escalation are offered), not re-configured in this pane -- D-19 (no channel secret ever touches this pane's form state or payload)"
    - "Test-digest error copy always leads with the fixed UI-SPEC string; any server-echoed detail is appended as separate, auto-escaped React text in parentheses, never replacing or dangerouslySetInnerHTML'ing the fixed copy (T-40-21)"

key-files:
  created:
    - frontend/src/components/settings/alerting-digests-pane.tsx
  modified:
    - frontend/src/components/settings/alerting-digests-pane.test.tsx
    - frontend/src/components/settings/microcopy.ts
    - frontend/src/components/settings/settings-sidebar-shell.tsx
    - frontend/src/components/settings/settings-sidebar-shell.test.tsx
    - frontend/src/app/(authed)/dashboard/settings/page.tsx
    - frontend/src/lib/queries/use-tenant-settings.ts

key-decisions:
  - "Delivery-channel routing checkboxes (Section 3) are grouped by alert TYPE (new_kev_epss/digest_owner/digest_team), each row only listing channels already enabled under SLA & Escalation -- row labels ('Real-time alerts'/'Owner digests'/'Team digests') are deliberately distinct strings from the Section 1/Section 2 headings ('New exposure alerts'/'Scheduled digests') to avoid an ambiguous duplicate-text render once both are on screen simultaneously (found via a failing multi-match test, fixed before it ever shipped)"
  - "alerting_config added to TenantSettings/TenantSettingsPatch in use-tenant-settings.ts (Rule 3 -- blocking): the type was never extended when Plan 04 added the field to the GET/PATCH payloads, so accessing settings.alerting_config would not compile without this fix"
  - "Test-digest 'error' branch always renders the fixed UI-SPEC copy ('Test digest couldn't be sent...') as the leading text; a server-supplied error string (if any) is appended in muted, parenthesized plain text -- satisfies both the Copywriting Contract's exact-string requirement and T-40-21's allowance for safely rendering server-echoed detail"
  - "Task 3 (checkpoint:human-verify, gate=\"blocking\") was approved ON-TRUST by the user via the orchestrator, consistent with this project's Phase 38/39 precedent for waiving live-browser walkthroughs. Live third-party delivery verification (steps 5-6 of the checkpoint: real Slack/Teams/SMTP send, KEV/EPSS real-time alert firing + no-re-fire) was NOT run in a live environment during this plan -- deferred to a future /gsd-verify-work 40 pass, per the user's explicit instruction. All other checkpoint steps (pane render/save/RBAC/empty-state) are covered by the unit-test suite added in Task 1."
  - "ALERT-01/ALERT-02/ALERT-03 marked [x] complete in REQUIREMENTS.md -- this plan is the designated closer for all three (Plans 01/03 explicitly left them unmarked pending this plan's frontend surface + on-trust sign-off)"

requirements-completed: [ALERT-01, ALERT-02, ALERT-03]

coverage:
  - id: D1
    description: "The 'Alerting & Digests' pane renders three section cards (New exposure alerts / Scheduled digests / Delivery channels), pre-filled from Tenant.alerting_config, saving via updateSettings.mutateAsync({ alerting_config })"
    requirement: "ALERT-03"
    verification:
      - kind: unit
        ref: "cd frontend && npx vitest run alerting-digests-pane -- 7/7 pass, including 'save calls mutateAsync (PATCH) with an alerting_config key reflecting the edit'"
        status: pass
      - kind: static
        ref: "grep -c 'data-pane=\"alerting-digests\"' alerting-digests-pane.tsx == 1; grep 'mutateAsync' shows the alerting_config payload"
        status: pass
    human_judgment: false
  - id: D2
    description: "The pane is registered: 'alerting' in microcopy Category union + CATEGORY_LABELS ('Alerting & Digests'), settings-sidebar-shell ALL_CATEGORIES + ADMIN_ONLY, page.tsx renderPane case 'alerting'"
    requirement: "ALERT-03"
    verification:
      - kind: unit
        ref: "cd frontend && npx vitest run settings-sidebar-shell -- 9/9 pass (updated category counts 8->9, added explicit 'Alerting & Digests' label assertion)"
        status: pass
      - kind: static
        ref: "npx tsc --noEmit clean across all Category consumers"
        status: pass
    human_judgment: false
  - id: D3
    description: "RBAC: a non-owner viewer sees the pane (admin-visible) with every control disabled (isOwner gate); owner can edit and save"
    requirement: "ALERT-03"
    verification:
      - kind: unit
        ref: "alerting-digests-pane.test.tsx: 'RBAC: a non-OWNER (ADMIN) sees every control disabled' + 'OWNER role leaves controls enabled', both pass"
        status: pass
    human_judgment: false
  - id: D4
    description: "Empty state: when no delivery channels are configured under SLA & Escalation, the pane shows 'No delivery channels configured' (reuses the sla-escalation anyChannelEnabled guard)"
    requirement: "ALERT-03"
    verification:
      - kind: unit
        ref: "alerting-digests-pane.test.tsx: 'renders the no-channels-configured EmptyState when sla_config has no enabled channel', passes"
        status: pass
    human_judgment: false
  - id: D5
    description: "Loading state uses SkeletonTable; error state uses PartialFailureBanner (mandatory states)"
    requirement: "ALERT-03"
    verification:
      - kind: static
        ref: "grep -c SkeletonTable / PartialFailureBanner / EmptyState in alerting-digests-pane.tsx all >=1 (3/3/6 respectively)"
        status: pass
    human_judgment: false
  - id: D6
    description: "Send test digest button shows disabled + 'Sending...' in flight; branches on sent/empty/error"
    requirement: "ALERT-03"
    verification:
      - kind: unit
        ref: "alerting-digests-pane.test.tsx: empty-branch and error-branch tests both pass, asserting the exact E1 inline message and the fixed UI-SPEC error copy respectively"
        status: pass
    human_judgment: false
  - id: D7
    description: "Send test digest with zero matching findings shows the inline 'Nothing to send right now...' message rather than silently no-op'ing (E1 backstop)"
    requirement: "ALERT-03"
    verification:
      - kind: unit
        ref: "alerting-digests-pane.test.tsx: '\"Send test digest\" empty-branch renders the fixed E1 inline message (not a false-positive error)' -- mocks POST /settings/alerting/test-digest -> {status:'empty'}, asserts the exact copy renders and the request path is correct"
        status: pass
    human_judgment: false
  - id: D8
    description: "Live human-verify of pane render/save/RBAC/empty-state, real Slack/Teams/SMTP digest delivery, KEV/EPSS real-time alert firing + no-re-fire, and the audit log row -- Task 3 checkpoint"
    requirement: "ALERT-01, ALERT-02, ALERT-03"
    verification:
      - kind: manual
        ref: "Task 3 checkpoint:human-verify (gate=\"blocking\") was approved ON-TRUST by the user via the orchestrator. Pane render/save/RBAC/empty-state are independently covered by the Task 1 unit-test suite (D1/D3/D4 above) and were NOT separately re-verified in a live browser by this executor. Live third-party delivery (real Slack/Teams webhook + SMTP send, step 5) and the real-time KEV/EPSS alert fire + no-re-fire check (step 6) were NOT run in a live environment during this plan -- explicitly deferred to a future /gsd-verify-work 40 pass per the user's instruction."
        status: pass
    human_judgment: true

# Metrics
duration: ~25min (Tasks 1-2 autonomous) + on-trust checkpoint approval (Task 3)
completed: 2026-08-19
status: complete
---

# Phase 40 Plan 05: Alerting & Digests Settings Pane Summary

**Ships the "Alerting & Digests" settings pane (D-17) as a structural clone of `sla-escalation-pane.tsx` -- three section cards (KEV/EPSS detection, digest cadence/scope, channel routing), owner-gated RBAC, mandatory loading/empty/error states, and a "Send test digest" preview action -- registered across the settings sidebar/microcopy/page, closing out ALERT-01/02/03. Task 3's live-verify checkpoint was approved on-trust; live third-party delivery is deferred to a future `/gsd-verify-work 40` pass.**

## Performance

- **Duration:** ~25 min autonomous work (Tasks 1-2) + checkpoint approved on-trust (Task 3, no additional executor work)
- **Started:** 2026-08-19T17:12Z (immediately after 40-04's metadata commit)
- **Completed:** 2026-08-19T17:24Z (Tasks 1-2); checkpoint approved on-trust thereafter
- **Tasks:** 2/2 `type="auto"` complete + 1 `type="checkpoint:human-verify"` approved on-trust
- **Files modified:** 6 (1 created, 5 modified)

## Accomplishments

- `AlertingDigestsPane` shipped as a structural clone of `sla-escalation-pane.tsx`: `useAuth`/`useTenantSettings`/`useUpdateTenantSettings`/`useDirtyState`/`SaveBar` composition, `isOwner` RBAC disabling every control for a non-owner viewer, `data-pane="alerting-digests"` test hook, design tokens only (0 raw hex literals)
- Section 1 "New exposure alerts" (KEV toggle + EPSS threshold, mono numeric input), Section 2 "Scheduled digests" (cadence select, send-hour, per-owner/per-team toggles), Section 3 "Delivery channels" (per-alert-type routing restricted to SLA-enabled channels only, D-19) -- exact UI-SPEC Copywriting Contract strings throughout
- Mandatory states wired: `SkeletonTable` (loading), `PartialFailureBanner` (error), `EmptyState` "No delivery channels configured" keyed off the same `anyChannelEnabled` guard pattern as `sla-escalation-pane.tsx`
- "Send test digest" secondary action calls `POST /api/v1/tenant/settings/alerting/test-digest` and branches on `sent`/`empty`/`error` -- the E1 backstop's exact inline copy for the empty case, and the fixed UI-SPEC error copy (with any server detail safely appended as plain text, T-40-21) for the error case
- Registered the pane across `microcopy.ts` (`'alerting'` Category + label), `settings-sidebar-shell.tsx` (`ALL_CATEGORIES` + `ADMIN_ONLY`), and `page.tsx` (import + `case 'alerting'` + allow-list)
- Graduated `alerting-digests-pane.test.tsx` from the Plan 01 RED scaffold (4 tests) to 7 full assertions; found and fixed a scaffold bug where `findByText(/./)` and loose multi-match regexes throw once the real pane renders more than one text node
- Fixed a real duplicate-text collision: the Section 3 routing-row labels initially reused the Section 1/2 heading text verbatim ("New exposure alerts"), which broke `getByText`/`findByText` queries once both were on screen -- renamed the row labels to distinct strings ("Real-time alerts"/"Owner digests"/"Team digests")
- Added `alerting_config` to the frontend `TenantSettings`/`TenantSettingsPatch` types (Rule 3 -- was missing since Plan 04 added the backend field, blocking compilation)
- Updated `settings-sidebar-shell.test.tsx`'s hardcoded category counts (8->9 total, 7->8 inactive) for the new admin-only category, added an explicit `'Alerting & Digests'` label assertion

## Task Commits

1. **Task 1: alerting-digests-pane.tsx (clone) + vitest green** -- `50daa4a` (feat)
2. **Task 2: Register the pane (microcopy + sidebar shell + page)** -- `d44d5d7` (feat)
3. **Task 3: checkpoint:human-verify** -- approved on-trust (see below); no additional commit from this executor

**Plan metadata:** pending (this SUMMARY's own commit)

### Task 3 -- checkpoint:human-verify, approved on-trust

The plan's Task 3 was a `checkpoint:human-verify` (`gate="blocking"`) asking a human to: (1) render/pre-fill/save the pane as an OWNER, (2) confirm every control is disabled as a non-owner ADMIN, (3) confirm the empty-channels EmptyState with no SLA channels configured, (4) send a real test digest against a configured Slack/Teams/SMTP tenant and confirm delivery or the empty-inline message, (5) trigger a real KEV/EPSS transition and confirm the real-time alert fires exactly once (no re-fire on a repeat tick), and (6) confirm an "updated alerting configuration" audit row.

The user, presented this checkpoint via the orchestrator, **explicitly selected "Approve on-trust"**, consistent with this project's established precedent (Phase 38/39) for waiving live-browser/live-delivery walkthroughs. Per the user's explicit instruction:

- Steps 1-3 (pane render/save/RBAC/empty-state) are independently covered by the Task 1 unit-test suite (7/7 green, including explicit RBAC-disabled/RBAC-enabled and empty-state tests) -- not separately re-verified in a live browser by this executor.
- Steps 5-6 (live third-party delivery via real Slack/Teams webhook + SMTP, and the real-time KEV/EPSS alert-fire + no-re-fire check) were **NOT run in a live environment** during this plan. This is explicitly deferred to a future `/gsd-verify-work 40` pass, per the user's instruction. Coverage item D8 above is marked `human_judgment: true` to flag this for the verifier.
- Step 7 (audit row) relies on the already-shipped, unit-tested Plan 04 audit path (`alerting.config_update`) and the existing `audit-log-pane.tsx` (reuse verbatim, no new frontend code) -- not independently re-verified live here either.

## Files Created/Modified

- `frontend/src/components/settings/alerting-digests-pane.tsx` (new) -- the pane, three section cards, RBAC, mandatory states, test-digest action
- `frontend/src/components/settings/alerting-digests-pane.test.tsx` (modified) -- graduated from 4-test RED scaffold to 7 full assertions
- `frontend/src/components/settings/microcopy.ts` (modified) -- `'alerting'` Category + `CATEGORY_LABELS['alerting']`
- `frontend/src/components/settings/settings-sidebar-shell.tsx` (modified) -- `ALL_CATEGORIES` + `ADMIN_ONLY`
- `frontend/src/components/settings/settings-sidebar-shell.test.tsx` (modified) -- updated hardcoded category counts, added label assertion
- `frontend/src/app/(authed)/dashboard/settings/page.tsx` (modified) -- import + `case 'alerting'` + allow-list entry
- `frontend/src/lib/queries/use-tenant-settings.ts` (modified) -- added `alerting_config` to `TenantSettings`/`TenantSettingsPatch`

## Decisions Made

See `key-decisions` in frontmatter for the full list (distinct routing-row labels to avoid duplicate-text collision, the `alerting_config` type-gap fix, the fixed-copy-leads error-rendering convention, the on-trust checkpoint approval and its scope, and the ALERT-01/02/03 requirements closure).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Scaffold's `findByText(/./)` and loose multi-match regexes threw once the real pane rendered**
- **Found during:** Task 1, first `vitest run` against the graduated test file
- **Issue:** The Plan 01 RED scaffold used `await screen.findByText(/./)` to "let data settle" and loose regexes (`/detection|kev|epss/i` etc.) to loosely match section headings without pinning unverified copy. Both patterns throw a `TestingLibraryElementError` once the pane renders more than one matching text node (which it now does, by design, once the real UI-SPEC copy exists).
- **Fix:** Replaced with `await screen.findByText('New exposure alerts')` (a specific heading) and `getByRole('heading', { name: ... })` for each of the three section headings.
- **Files modified:** `frontend/src/components/settings/alerting-digests-pane.test.tsx`
- **Verification:** All 7 tests pass.
- **Committed in:** `50daa4a` (Task 1 commit)

**2. [Rule 1 - Bug] Section 3 routing-row labels duplicated the Section 1 heading text**
- **Found during:** Task 1, while writing the "save calls mutateAsync" test -- `findByText('New exposure alerts')` found 2 matches (the Section 1 `<h2>` and a Section 3 routing-row `<div>` that reused the identical string as its own alert-type label)
- **Issue:** Ambiguous duplicate text breaks any test (and any screen-reader/visual scan) trying to locate "New exposure alerts" by content once both elements are on screen simultaneously.
- **Fix:** Renamed the Section 3 alert-type row labels to distinct strings not used elsewhere in the pane: `'Real-time alerts'` / `'Owner digests'` / `'Team digests'`.
- **Files modified:** `frontend/src/components/settings/alerting-digests-pane.tsx`
- **Verification:** All 7 tests pass with unambiguous single-match queries.
- **Committed in:** `50daa4a` (Task 1 commit)

**3. [Rule 3 - Blocking] `alerting_config` missing from the frontend `TenantSettings`/`TenantSettingsPatch` types**
- **Found during:** Task 1, while wiring `settings.alerting_config` and `updateSettings.mutateAsync({ alerting_config: ... })`
- **Issue:** Plan 04 added `alerting_config` to the backend GET/PATCH `/tenant/settings` payloads, but `frontend/src/lib/queries/use-tenant-settings.ts`'s `TenantSettings`/`TenantSettingsPatch` types were never extended -- accessing/sending the field would not type-check.
- **Fix:** Added `alerting_config: Record<string, unknown> | null` to both types, matching the existing loosely-typed `sla_config` precedent.
- **Files modified:** `frontend/src/lib/queries/use-tenant-settings.ts`
- **Verification:** `npx tsc --noEmit` clean.
- **Committed in:** `50daa4a` (Task 1 commit)

**4. [Rule 3 - Blocking] `settings-sidebar-shell.test.tsx` hardcoded category counts broke on the new category**
- **Found during:** Task 2, running the broader settings test suite after registering `'alerting'`
- **Issue:** Adding a 9th category to `ALL_CATEGORIES`/`ADMIN_ONLY` shifted the pre-existing test file's hardcoded `toBe(8)` (total admin categories) and `toBe(7)` (inactive-button count) assertions, which are direct consequences of this task's own registration change, not a pre-existing unrelated failure.
- **Fix:** Updated both counts (8->9, 7->8) and added an explicit `expect(labels).toContain('Alerting & Digests')` assertion.
- **Files modified:** `frontend/src/components/settings/settings-sidebar-shell.test.tsx`
- **Verification:** 9/9 tests pass; full `src/components/settings` + settings-page test suite (62 tests, 9 files) green.
- **Committed in:** `d44d5d7` (Task 2 commit)

---

**Total deviations:** 4 auto-fixed (2 Rule-1 bugs in the graduated test file, 2 Rule-3 blocking type/test-count gaps directly caused by this plan's own changes).
**Impact on plan:** No scope creep, no architectural changes. All four fixes were required to make the plan's own stated tests/gates pass; none altered the pane's behavior or copy contract.

## Issues Encountered

None beyond the deviations above. `ENCRYPTION_KEY`/`JWT_SECRET_KEY` were not needed for this frontend-only plan (no backend test run).

## User Setup Required

None -- no external service configuration required for the shipped frontend code. A tenant must have SLA & Escalation channels + SMTP already configured (existing Phase 36/40-04 setup) for "Send test digest" to actually deliver; an unconfigured tenant correctly gets the fixed error copy, not a silent success.

## Next Phase Readiness

- Phase 40 (`proactive-alerting-digests`) is now **5/5 plans complete**. ALERT-01/ALERT-02/ALERT-03 are ALL now `[x]` complete in `REQUIREMENTS.md` -- this plan is the designated closer.
- The full ALERT-01..03 surface is code-complete end-to-end: real-time KEV/EPSS detection + routing (Plan 02), scheduled owner/team digests (Plan 03), tenant-configurable + audited settings (Plan 04 backend + this plan's frontend).
- **Outstanding (deferred, not blocking):** live third-party delivery verification (real Slack/Teams webhook + SMTP send) and the real-time KEV/EPSS alert-fire + no-re-fire check were approved on-trust, not run live, in this plan. Recommend closing via `/gsd-verify-work 40` before considering the phase's live-delivery claims independently proven.
- No blockers for any other v5.0 phase -- Phase 40 has no downstream dependents per the v5.0 Phase Map.

---
*Phase: 40-proactive-alerting-digests*
*Completed: 2026-08-19*

## Self-Check: PASSED

**Files verified to exist:**
- FOUND: frontend/src/components/settings/alerting-digests-pane.tsx
- FOUND: frontend/src/components/settings/alerting-digests-pane.test.tsx
- FOUND: frontend/src/components/settings/microcopy.ts
- FOUND: frontend/src/components/settings/settings-sidebar-shell.tsx
- FOUND: frontend/src/components/settings/settings-sidebar-shell.test.tsx
- FOUND: frontend/src/app/(authed)/dashboard/settings/page.tsx
- FOUND: frontend/src/lib/queries/use-tenant-settings.ts
- FOUND: .planning/phases/40-proactive-alerting-digests/40-05-SUMMARY.md

**Commits verified to exist (`git log --oneline --all`):**
- FOUND: 50daa4a (Task 1)
- FOUND: d44d5d7 (Task 2)
- FOUND: 61ef669 (SUMMARY.md commit)

**Test suite re-verified green:** `npx vitest run alerting-digests-pane settings-sidebar-shell sla-escalation-pane` and the full `src/components/settings` + settings-page dirs — 62/62 (broader suite) + 7/7 + 9/9, all green. `npx tsc --noEmit` clean.

No missing items.
