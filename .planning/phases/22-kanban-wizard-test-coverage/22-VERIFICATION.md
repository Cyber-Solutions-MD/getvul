---
phase: 22-kanban-wizard-test-coverage
verified: 2026-07-22T13:10:00Z
status: gaps_found
score: 6/7 must-haves verified
overrides_applied: 0
gaps:
  - truth: "The wizard Confirm step's submit-error state reports 0 serious/critical axe violations in both dark and light themes"
    status: partial
    reason: >
      Live-reproduced (5 full-suite reruns of `connector-wizard-a11y.spec.ts` against the
      same prod build + command the plan mandates): the DARK-theme "confirm step submit-error"
      test failed 2 of 5 times with a real axe `color-contrast` violation (serious impact,
      3.58:1 vs required 4.5:1) on `<p class="text-sm text-text-muted">API error: 500</p>`
      inside a global error Toast (`frontend/src/components/ui/Toast.tsx`, rendered by
      `ToastProvider.tsx`). This toast is a genuine, deterministic side effect of the mocked
      500 response (`use-connectors-admin.ts:146` calls `toast({variant:'error', ...})` on
      the create-connector mutation's `onError`) — it fires every time this test runs, in
      addition to the wizard's own inline `role="alert"`. The violation itself is a TIMING
      ARTIFACT, not a steady-state defect: the Toast fades in over a 200ms CSS opacity
      transition (`Toast.tsx` `visible` state + `transition-all duration-200`), and axe's
      color-contrast check sometimes samples the DOM mid-transition, when the semi-opaque
      overlay blends toward the page background and produces an artificially low apparent
      ratio. The toast's actual settled-state colors (`--color-text-muted:#B8AECE` on
      `--color-surface-2:#241B40`, sunset.css dark tokens) compute to ~7.65:1 — comfortably
      AA-compliant. Isolated `-g "confirm step submit-error"` reruns (5/5) never reproduced
      the failure; it only manifested when run as part of the FULL 14-test suite (the exact
      command Task 3 of 22-02-PLAN.md mandates as the acceptance gate), at roughly a 40%
      rate in this reproduction. The 22-02-SUMMARY.md's pasted "14 passed (11.4s)" transcript
      is a genuine, real transcript (line numbers match the spec file exactly) but reflects
      one lucky run of a flaky gate, not a deterministically green one. The plan's own Task 3
      contract ("If the failure is a test-driving bug (wrong selector/timing), fix the test")
      was not triggered because the executor's single live run did not happen to hit the race.
    artifacts:
      - path: "frontend/e2e/connector-wizard-a11y.spec.ts"
        issue: >
          The "confirm step submit-error" tests (lines 454-471 dark, 485-500 light) call
          sweepBlocking() immediately after `dialog.getByRole('alert')` becomes visible, with
          no wait for the ambient global Toast's 200ms fade-in transition to settle, and no
          scoping of the axe run to exclude the toast container
          (`div.fixed.top-4.right-4.z-\[60\]` in ToastProvider.tsx) from the sweep.
    missing:
      - "Wait for the Toast's opacity transition to finish before calling sweepBlocking() in both submit-error tests (dark + light) — e.g. `await page.waitForTimeout(250)` after the toast becomes visible, or poll the toast's computed opacity/transition state, before running analyze()."
      - "Alternatively, scope the Confirm-step submit-error axe sweep to the dialog only (exclude the global toast container) if the intent is to sweep the wizard's own DOM, not ambient site chrome — but this is a design choice; waiting for transition-settle is the minimal fix consistent with the rest of the suite's full-page sweep pattern."
      - "Re-run the FULL suite (not just -g isolated) at least 5x after the fix to confirm the flake is eliminated, and paste that evidence in a corrective SUMMARY addendum."
---

# Phase 22: Kanban + Wizard Test-Coverage Hardening Verification Report

**Phase Goal:** The two audit warnings on already-satisfied requirements are closed — the kanban's keyboard/announcement fixes and the wizard's later steps gain real test coverage.
**Verified:** 2026-07-22T13:10:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | CR-01: Enter-key drag changes ticket status; `[data-drill-panel]` stays at count 0 throughout | ✓ VERIFIED | `tickets-kanban.spec.ts:204` test exists with 3x `[data-drill-panel]` `toHaveCount(0)` assertions (mid-drag, post-drop, final); re-ran live against prod build — genuine PASS (not skip), matches 22-01-SUMMARY.md transcript exactly (same spec line 204, same 6-passed/2-skipped full-suite shape) |
| 2 | WR-02 gated no-op: read-only→read-only drop announces "returned to its column", never a false "Moved ticket" success, with an anti-vacuous-pass proof-of-movement gate | ✓ VERIFIED | `tickets-kanban.spec.ts:253-288` — interim `/is over the In progress column/i` assertion precedes the drop and the `/returned to its column/i` + `not(/^Moved ticket/i)` assertions. Re-run live: skipped (no Open tickets in current seed state — same disclosed, genuine seed-exhaustion pattern 22-01-SUMMARY.md documents; isolated `-g "announce"` run also skipped for the same reason, confirming this is real seed-data state, not a masked failure) |
| 3 | WR-02 committed move: read-only→Blocked announces "Moved ticket ... to the Blocked column" | ✓ VERIFIED | `tickets-kanban.spec.ts:201` (existing "keyboard drag" test, strengthened) — assertion present and passed live in my re-run (test #4, ✓ 862ms) |
| 4 | Test step (loader/success/error) reports 0 serious/critical axe violations, both themes | ✓ VERIFIED | `connector-wizard-a11y.spec.ts:299-441` — 6 tests present, all 6 passed live in every one of my 5 full-suite reruns (0 flakes observed on this block) |
| 5 | Confirm step permission/sync review reports 0 serious/critical axe violations, both themes | ✓ VERIFIED | `connector-wizard-a11y.spec.ts:446-453,477-484` — passed live in all 5 of my full-suite reruns |
| 6 | Confirm step submit-error reports 0 serious/critical axe violations, both themes | ✗ FAILED (partial) | Light theme passed 5/5 live reruns. **Dark theme failed 2 of 5 live full-suite reruns** with a real (if transient) axe `color-contrast` violation on an ambient global error Toast — see Gaps. |
| 7 | Test/Confirm steps driven deterministically via `page.route()` mocking; no real outbound call, no DB row created | ✓ VERIFIED | `connectors/test` mocked at lines 251-257, 306-313, 332-338, 353-359 etc.; `**/api/v1/connectors` mocked to 500 at lines 462-464, 491-493; `GET /connectors/types` deliberately never mocked (0 occurrences of `route.fulfill` against it — confirmed by grep) |

**Score:** 6/7 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `frontend/e2e/tickets-kanban.spec.ts` | CR-01 + WR-02 tests, `DndLiveRegion` + `data-drill-panel` anchors | ✓ VERIFIED | Both new tests present at exact line numbers cited in 22-01-SUMMARY.md's pasted transcript (204, 253) — corroborates the transcript is genuine, not fabricated |
| `frontend/src/app/(authed)/dashboard/tickets/tickets-kanban-board.tsx` | coordinateGetter fix (destination-column y-centering) | ✓ VERIFIED | Lines 108-111: `y: rect.top + rect.height / 2` (destination rect), matches SUMMARY's described fix exactly |
| `frontend/src/components/tickets/kanban-column.tsx` | `min-w-0` added to outer div | ✓ VERIFIED | Line 81: `'min-w-0 snap-start shrink-0 basis-[85vw] md:basis-0 md:flex-1 flex flex-col rounded-lg'` |
| `frontend/e2e/connector-wizard-a11y.spec.ts` | "Test step" + "Confirm step" describe blocks, `connectors/test` mock, `status:500` mock | ✓ VERIFIED | Both blocks present (10 new tests); mocks present at expected call sites; `connectors/types` never mocked (only referenced in explanatory comments, confirmed via grep+manual read) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `tickets-kanban.spec.ts` | `[data-drill-panel]` | `toHaveCount(0)` x3 | ✓ WIRED | Confirmed at lines 225, 234, 250 |
| `tickets-kanban.spec.ts` | `[id^="DndLiveRegion"]` | `toContainText(...)` (gated + committed branches) | ✓ WIRED | Confirmed at lines 173/201 (committed) and 265/278/283/284 (gated) |
| `connector-wizard-a11y.spec.ts` | `**/api/v1/connectors/test` | `page.route()` fulfilling 200 success/error bodies | ✓ WIRED | Confirmed at 10+ call sites across Test-step + Confirm-step helpers |
| `connector-wizard-a11y.spec.ts` | `**/api/v1/connectors` | `page.route()` fulfilling 500 | ✓ WIRED | Confirmed at lines 462-464, 491-493 |
| `connector-wizard-a11y.spec.ts` | `makeAxeBuilder().analyze()` | blocking-filter (`critical`/`serious`) + `toHaveLength(0)` | ⚠️ PARTIAL | Wired and passing for 13 of 14 sub-cases deterministically; the dark-theme Confirm-step submit-error sub-case is wired but intermittently reports a real (transient) violation — see Gaps |

### Data-Flow Trace (Level 4)

Not applicable in the conventional sense — this phase's "data flow" is the axe sweep's DOM-state coverage, traced above under Observable Truths / Key Links rather than a separate component-to-API data trace (no new production data source was introduced).

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full `tickets-kanban.spec.ts` live against prod build | `npx playwright test e2e/tickets-kanban.spec.ts --project=chromium-a11y` | 6 passed / 2 skipped (identical shape to 22-01-SUMMARY.md's transcript, same 2 tests skipped for the same disclosed seed-exhaustion reason) | ✓ PASS |
| CR-01 test in isolation | `-g "Enter"` | 2 passed (genuine, non-skipped) | ✓ PASS |
| WR-02 gated test in isolation | `-g "announce"` | 1 passed (setup) + 1 skipped (no Open tickets in current seed state — matches disclosed pattern) | ✓ PASS (disclosed skip) |
| Full `connector-wizard-a11y.spec.ts` live against prod build, **run 5 times** | `npx playwright test e2e/connector-wizard-a11y.spec.ts --project=chromium-a11y` (x5) | 14 passed (x3), 13 passed / 1 failed (x2) — same test failed both times: "confirm step submit-error ... (dark)" | ✗ FAIL (flaky, ~40% in this sample) |
| Isolated re-run of the flaky test alone | `-g "confirm step submit-error"` (x5) | 3 passed each time (setup + dark + light) — never reproduced in isolation | ✓ PASS in isolation (confirms the flake is a full-suite-timing artifact, not a deterministic defect) |
| `npm run perf:budget` | `npm run perf:budget` | `/dashboard/tickets` 167.0 kB, `/dashboard/connectors` 156.0 kB — both match SUMMARY exactly | ✓ PASS |

**Root cause of the one flaky sub-case:** `frontend/src/components/ui/Toast.tsx` renders a global `role="alert"` toast (via `ToastProvider.tsx`, triggered by `use-connectors-admin.ts:146`'s `onError` handler) any time the mocked `POST /connectors` 500 fires — a real, deterministic side effect of the Confirm-step submit-error scenario the test exercises, additional to the wizard's own inline alert. The toast fades in over a 200ms CSS opacity transition; axe's `color-contrast` check occasionally samples the DOM mid-transition (more likely under the CPU load of a full 14-test sequential run than in a 3-test isolated run), at which point the semi-transparent overlay's blended-toward-background colors compute to 3.58:1 (serious violation) instead of the toast's true settled-state ~7.65:1 (`--color-text-muted:#B8AECE` on `--color-surface-2:#241B40`, both well-established dark-theme tokens used correctly elsewhere). This is a test-timing gap, not a genuine WCAG contrast defect in the design tokens.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|--------------|------------|--------------|--------|----------|
| UX-D-01-02 (coverage) | 22-01-PLAN.md | Kanban CR-01 Enter-drag + WR-02 gated/committed live-region coverage | ✓ SATISFIED | All 3 associated truths verified live; REQUIREMENTS.md line 36 marks this satisfied and correctly attributes the coverage work to Phase 22 |
| UX-D-02-06 (coverage) | 22-02-PLAN.md | Wizard Test-step + Confirm-step axe coverage, both themes | ⚠️ PARTIAL | Test-step (6/6) and Confirm-step review (2/2) sub-cases are solidly green; Confirm-step submit-error (dark) is flaky (~40% fail rate reproduced live) — REQUIREMENTS.md line 49 marks this satisfied, but the live evidence does not yet support "passes axe in both themes" deterministically for this one state |

No orphaned requirements found — REQUIREMENTS.md's Phase-22 references (lines 36, 49) match exactly the two requirement IDs declared in the two plans' frontmatter.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | — | — | No TODO/FIXME/placeholder/stub patterns found in any of the 4 modified files. The one "placeholder" grep hit in `tickets-kanban.spec.ts:4` is a pre-existing Phase-18 historical comment, unrelated to this phase's changes. |

### Human Verification Required

None. All behaviors are automatable and were spot-checked live in this verification pass.

### Gaps Summary

Both plans' authored tests are real, substantive, and correctly wired — not stubs, not vacuous passes. The CR-01/WR-02 kanban coverage (22-01) is solid: re-running it live reproduced the exact pass/skip shape documented in the SUMMARY, and the two production fixes (`coordinateGetter` re-centering, `min-w-0`) are genuinely present in the source and correctly described.

The wizard coverage (22-02) is 13/14 solid, but one sub-case — the dark-theme "Confirm step submit-error" axe sweep — is flaky under the exact full-suite command the plan's own Task 3 mandates as the acceptance gate (~40% failure rate across 5 live reruns in this verification, never reproduced in isolation). The failure is a real axe-reported `color-contrast` violation, but traced to a CSS-transition timing race with an ambient global error Toast the test doesn't wait out — not a genuine steady-state design-token defect (the toast's settled contrast is ~7.65:1). This means the phase's own success criterion #2 ("0 serious/critical … in both themes") is not yet deterministically true, and the 22-02-SUMMARY.md's "14/14 passing" claim, while a genuine transcript of one real run, does not reflect the gate's actual reliability.

Recommended closure: add a short settle-wait (or transition-state poll) before the `sweepBlocking()` call in both Confirm-step submit-error tests, then re-run the full suite 5x to confirm 0 flakes, and paste that evidence in a corrective SUMMARY addendum.

---

*Verified: 2026-07-22T13:10:00Z*
*Verifier: Claude (gsd-verifier)*
