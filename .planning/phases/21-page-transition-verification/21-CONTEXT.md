# Phase 21: Page-transition verification - Context

**Gathered:** 2026-07-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Formally verify Phase 17 (View Transitions API cross-fade, UX-D-06) — already shipped and
e2e-green — by closing the three verification-coverage gaps flagged as blocker #2 in
`v2.2-MILESTONE-AUDIT.md`:

1. A **real** DrillPanel-during-navigation e2e test that replaces the synthetic
   `history.pushState` + `PopStateEvent` proxy (IN-01 from `17-REVIEW.md`), which never
   exercised Next.js's real App Router segment-diffing path.
2. A persisted **`17-HUMAN-UAT.md`** recording the perceptual checkpoint (cross-fade feel,
   chrome stillness, DrillPanel-during-transition, Firefox fallback feel) **as closed**, and
   STATE.md's `human-UAT checkpoint OUTSTANDING` flag cleared.
3. A goal-backward **`17-VERIFICATION.md`** confirming UX-D-06-01..05 were delivered.

This phase is **verification + test hardening + doc closure**. It adds/strengthens e2e
assertions and records human sign-off — it does NOT add new motion behavior or change the
shipped transition. Covers requirements **UX-D-06-01, UX-D-06-03, UX-D-06-04**.

</domain>

<decisions>
## Implementation Decisions

### Real DrillPanel-during-navigation test (SC#1 — replaces IN-01 proxy)
- **D-01:** Drive **real Next.js router navigation**, not the synthetic `history.pushState` +
  `PopStateEvent` proxy. The new test must exercise the actual App Router segment-diffing path
  so the assertion is trustworthy.
- **D-02:** Cover **BOTH cases** with real navigation:
  - **No-fade case (D-02 from Phase 17):** a `searchParams`-only change (e.g. `?drill=…` /
    `?tab=…` via a real `router.replace`) must produce **0** `authed-page-content` view-transition
    animations — the template is keyed on the segment, so searchParams never remount it.
  - **Fade case (D-11 from Phase 17):** a **pathname change while a DrillPanel is open** must
    fade the content region (drill included) — the panel goes out with the outgoing snapshot,
    no special close choreography, no layout shift.
- **D-03:** Prefer driving the real `router.replace`/`router.push` over depending on seeded
  interactive data (clicking a live vuln row). Rationale: Phase 17 fell back to the proxy
  precisely because interactive controls weren't trivially reachable in a stateless e2e
  session — a real `router` drive gets genuine segment behavior without a fixture dependency.
  (If the planner finds a reachable real control cheaply, driving the actual UI click is an
  acceptable upgrade — the point is "real routing, not PopStateEvent.")

### Firefox CSS-fallback coverage (SC — perceptual "Firefox feel")
- **D-04:** Add an **automated e2e assertion** (Firefox project) that the **CSS-keyframe
  fallback** cross-fade runs on `(authed)/template.tsx` mount for a real pathname change —
  Firefox lacks the View Transitions API, so it exercises the D-06 fallback path. This gives
  durable cross-browser regression coverage rather than relying solely on a one-time manual
  Firefox spot-check. Planner to confirm the existing `e2e/playwright.config.ts` Firefox
  project (already carries `firefoxUserPrefs`) supports the assertion, and that the D-12
  reduced-motion blanket still suppresses it.

### DrillPanel Esc/clickaway close-race (SC#1 / UX-D-06-04)
- **D-05:** Add a **dedicated close-path test**: open a DrillPanel, trigger an Esc/clickaway
  close (which mutates searchParams), and assert **no** `authed-page-content` fade fires AND
  **no layout shift** — directly exercising the UX-D-06-04 race guard rather than inferring it
  from the generic "searchParams never fade" assertion.

### Perceptual human-UAT closure (SC#2)
- **D-06:** The user will **perform the perceptual sign-off during execution, guided**. The
  executor (or orchestrator) stands up the app (or the user runs it), presents a concise
  perceptual checklist, and the user signs off item-by-item; results are recorded in
  `17-HUMAN-UAT.md`. **This is a `human-action` checkpoint** — plan for a real interactive pause,
  not an auto-approved gate.
- **D-07:** The UAT checklist items to record (from Phase 17 `17-02` Task 4): (a) cross-fade
  *feel* — snappy 220–320ms pure-opacity, no drift; (b) chrome *stillness* — sidebar/topbar do
  not move or fade during a route change; (c) DrillPanel-during-transition — an open drill fades
  out cleanly with the content on a pathname change, no stuck/ghost panel; (d) Firefox
  fallback *feel* — the cross-fade looks equivalent under the CSS-keyframe path.
- **D-08:** On successful sign-off, mark `17-HUMAN-UAT.md` status closed/resolved AND clear the
  `human-UAT checkpoint OUTSTANDING` line in STATE.md (SC#2 requires both).

### 17-VERIFICATION.md (SC#3)
- **D-09:** Produce a goal-backward `17-VERIFICATION.md` confirming UX-D-06-01..05 against the
  shipped code + the newly-hardened tests. This is the standard gsd-verifier artifact, back-dated
  in intent to Phase 17's goal but authored now (Phase 17 shipped without one).

### Claude's Discretion
- Exact structure/wording of the new e2e assertions and how the real `router.replace` is invoked
  from Playwright (e.g. `page.evaluate` against the Next router vs. a reachable in-app control).
- Whether the Firefox fallback assertion lives in `page-transitions.spec.ts` or a sibling spec.
- Layout-shift measurement technique for D-05 (CLS observer vs. bounding-box before/after).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 21 scope & audit source
- `.planning/ROADMAP.md` §"Phase 21: Page-transition verification" — goal + 3 success criteria.
- `.planning/milestones/v2.2-ROADMAP.md` §"Phase 21" — same, milestone-level.
- `.planning/v2.2-MILESTONE-AUDIT.md` — blocker #2 (no 17-VERIFICATION.md, unpersisted perceptual
  UAT, IN-01 proxy) that this phase closes.

### Phase 17 artifacts (what is being verified)
- `.planning/phases/17-page-transition-motion/17-CONTEXT.md` — the locked D-01..D-11 decisions
  (pathname-only trigger, searchParams-never-fade, content-only scope, Firefox fallback, DrillPanel
  behavior) that the tests must confirm.
- `.planning/phases/17-page-transition-motion/17-REVIEW.md` §IN-01 + `17-REVIEW-FIX.md` §IN-01 —
  the exact synthetic-proxy limitation being replaced.
- `.planning/phases/17-page-transition-motion/17-01-SUMMARY.md` / `17-02-SUMMARY.md` — what was
  built and the Task-4 perceptual checkpoint that was left OUTSTANDING.

### Design contract (authoritative for perceptual "feel" items)
- `.claude/skills/sketch-findings-getvul/references/foundation.md` §Motion — the four durations,
  "cross-fade only, no transforms," and the reduced-motion substitution rule.
- `.claude/skills/sketch-findings-getvul/references/app-shell.md` — the persistent chrome that must
  stay still (D-05 from Phase 17 / chrome-stillness UAT item).

### Code + tests under verification
- `frontend/src/app/(authed)/template.tsx` — the transition driver.
- `frontend/src/app/globals.css` — `::view-transition-*` rules, fallback keyframe, D-12
  reduced-motion blanket.
- `frontend/e2e/page-transitions.spec.ts` — the spec to harden (TEST B / IN-01 proxy at ~line 101).
- `frontend/e2e/reduced-motion.spec.ts` — must stay green (UX-D-06-02).
- `frontend/e2e/playwright.config.ts` — Firefox project + `firefoxUserPrefs` for the D-04 assertion.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `frontend/e2e/page-transitions.spec.ts` — existing suite already polls `document.getAnimations()`
  for `authed-page-content` pseudo-element VT animations (the WR-03-tightened named-group check).
  The new real-router tests reuse this polling harness; only the *trigger* changes (real
  `router.replace` / pathname nav instead of `PopStateEvent`).
- `frontend/e2e/playwright.config.ts` — already defines a Firefox project with
  `firefoxUserPrefs: { 'ui.systemUsesDarkTheme': 1 }`; the D-04 fallback assertion runs there.
- Project memory `getvul-local-e2e-perf-gate` — the live prod-build + :3000 + admin-login recipe
  the guided UAT (D-06) and any live e2e run depend on.

### Established Patterns
- **DrillPanel + tabs + list/board toggle all drive `searchParams`** (`?drill=`, `?tab=`, `?view=`)
  — this is exactly the no-fade path the real-router test must exercise (D-02).
- **Reduced motion handled globally** by the D-12 `globals.css` blanket — the Firefox fallback
  assertion must confirm the blanket still suppresses the keyframe under `prefers-reduced-motion`.

### Integration Points
- No production-code change expected — this phase adds/strengthens e2e specs and authors
  `17-HUMAN-UAT.md` + `17-VERIFICATION.md`. If a test surfaces a real VT×DrillPanel race or layout
  shift, that becomes an in-scope fix (the test, not the file list, is the arbiter).

</code_context>

<specifics>
## Specific Ideas

- The whole phase is a direct answer to the recurring project anti-pattern (memory
  `getvul-axe-sweep-not-run-during-exec`): verification claims made without the check actually
  running. Every SC here is "make the unproven thing proven" — real routing instead of a proxy,
  a persisted human sign-off instead of an OUTSTANDING note, an actual VERIFICATION.md instead of
  its absence. Bias toward evidence that would survive an audit.
- The user explicitly wants the highest-rigor path on all four decisions (real router both cases,
  automated Firefox assertion, dedicated close-race test, guided perceptual sign-off) — do not
  down-scope these to "architectural guarantee is enough" during planning.

</specifics>

<deferred>
## Deferred Ideas

- **Navigation pending indicator** (top loading bar during navigation to `force-dynamic` routes) —
  carried over from Phase 17's deferred list; a new capability, not part of UX-D-06 verification.
  Note for a future backlog item if analysts report the fade alone is insufficient feedback.

</deferred>

---

*Phase: 21-page-transition-verification*
*Context gathered: 2026-07-21*
