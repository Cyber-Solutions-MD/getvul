---
phase: 25-asset-aware-remediation-guidance
plan: 04
subsystem: ui
tags: [react, nextjs, typescript, ai, sse, cite-or-refuse, safety-gate, vitest]

# Dependency graph
requires:
  - phase: 25-asset-aware-remediation-guidance
    plan: 03
    provides: "the 'unsafe' SSE error kind + the GET groundable pre-signal, wired through _run_explain_stream()'s dangerous_pattern_check gate and the new POST/GET /explain-remediation-guidance/{finding_id} route"
provides:
  - "frontend/src/lib/ai/use-explain-stream.ts — 'unsafe' added to both the ExplainStreamState error-kind union and the standalone ErrorEvent type"
  - "frontend/src/lib/queries/use-explain-cache.ts — groundable?: boolean added to the cached:false branch of ExplainCacheResult"
  - "frontend/src/components/ai/ai-explanation-section.tsx — DegradedCard danger variant (border-danger/bg-danger-soft/text-danger, the ONE new color usage this phase introduces); the kind==='unsafe' safety-refusal branch; the cached===false && groundable===false pre-refusal branch checked before the Analyst-trigger branch; resourceType-scoped LOCKED copy (section header/CTA/viewer-empty-text/insufficient-evidence heading+body) for resourceType='remediation-guidance', with vuln/host/remediation retaining their original byte-identical copy"
  - "frontend/src/components/vulnerabilities/drill-content.tsx — new <section aria-labelledby='drill-remediation-guidance-h'> mounted between the raw Remediation section and Activity, rendering AiExplanationSection resourceType='remediation-guidance'"
affects: [26, 27, 28]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "resourceType-scoped copy branch inside a shared component: AiExplanationSection now derives heading/triggerLabel/viewerEmptyText/insufficientEvidenceCopy from `resourceType === 'remediation-guidance'`, the ONE deliberate exception to D-15's 'no per-view copy' rule for the three original views (vuln/host/remediation) — the four-view parity tests only ever governed those three, never this 4th, categorically distinct feature (D-06)"
    - "UI-SPEC state 8 (model's own grounded=false judgment) and state 3 (deterministic pre-generation gate) both render from the SAME insufficientEvidenceCopy constant, so all four render sites (done+!grounded, kind===grounded_false, cached+!grounded, the new groundable===false branch) stay in lockstep per resourceType"
    - "the groundable===false branch is structurally impossible to reach with a truthy/falsy check on the wrong routes: checked === false explicitly, positioned after the cached===true and !keyConfigured branches and before isAnalystOrAbove, so vuln/host/remediation-posture GET responses (which never return `groundable` at all) fall through to the trigger unaffected"

key-files:
  created: []
  modified:
    - frontend/src/lib/ai/use-explain-stream.ts
    - frontend/src/lib/queries/use-explain-cache.ts
    - frontend/src/components/ai/ai-explanation-section.tsx
    - frontend/src/components/ai/ai-explanation-section.test.tsx
    - frontend/src/components/vulnerabilities/drill-content.tsx
    - frontend/src/components/vulnerabilities/drill-panel.test.tsx

key-decisions:
  - "Added resourceType-scoped copy overrides (heading/triggerLabel/viewerEmptyText/insufficientEvidenceCopy) inside AiExplanationSection beyond what Task 1's <action> text literally specified — 25-UI-SPEC.md's Copywriting Contract locks distinct strings for the Primary CTA ('Get remediation guidance'), the section eyebrow header ('Remediation guidance'), the Viewer cache-miss text ('No remediation guidance generated yet.'), and the insufficient-evidence card (state 3 AND state 8, per UI-SPEC's explicit 'state 8 renders the same card as state 3') — shipping only the danger/groundable branches without this would have left the new section showing 'AI Explanation'/'Explain this vuln'/generic vuln-flavored refusal copy, directly violating the ui_requirement's mandate to use the Copywriting Contract's locked strings verbatim and CLAUDE.md's 'no generic SaaS copy' rule. Every other card (no-key D-23, busy/unknown D-25, budget-exceeded) stays byte-identical across all four resourceTypes, per D-07."
  - "Reused the AlertTriangle icon for the new danger variant (no new lucide-react import) since the color (border-danger/bg-danger-soft/text-danger) alone already makes the safety-refusal card unmistakably distinct from both the amber busy/budget cards and the neutral/violet insufficient-evidence card — proven by the Pitfall-3 test asserting the two new cards never share a `[class*=\"danger\"]` or `.bg-violet-soft` match."
  - "drill-panel.test.tsx's pre-existing '8 sections in order' test was extended to 9 sections (not left broken) since the new section shifts Activity/Actions down by one heading index — a document-order assertion was added alongside it, scoped independently of the heading-index array, to prove the new section's position without depending on exact heading counts elsewhere in the suite."

requirements-completed: [AIR-01]

# Metrics
duration: 13min
completed: 2026-07-30
---

# Phase 25 Plan 04: Frontend Tracer — unsafe SSE Kind + groundable Pre-Signal + Remediation Guidance Section Summary

**The frontend half of the AIR-01 tracer: a danger/red safety-refusal card and a neutral/violet insufficient-evidence card added to the shared `AiExplanationSection`, a `groundable` pre-click refusal signal, and a new "Remediation guidance" drill-panel section (its own locked copy, its own cite-or-refuse output) mounted between the raw Remediation text and Activity — closing the end-to-end per-vuln remediation-guidance slice front to back.**

## Performance

- **Duration:** ~13 min
- **Started:** 2026-07-30T13:21:40+03:00 (commit sequence start)
- **Completed:** 2026-07-30T13:31:43+03:00
- **Tasks:** 2 completed
- **Files modified:** 6 (4 modified source, 2 modified test)

## Accomplishments
- `use-explain-stream.ts`: `'unsafe'` added to both hand-synced closed unions (`ExplainStreamState`'s error branch, the standalone `ErrorEvent` type) — the SSE parsing loop needed zero change, it already forwards `evt.kind` verbatim.
- `use-explain-cache.ts`: `ExplainCacheResult`'s `cached: false` branch gains an optional `groundable?: boolean` field, riding the already-generic JSON response — every other existing GET route (vuln/host/remediation) never returns this key, so the field stays structurally optional.
- `ai-explanation-section.tsx`: `DegradedCard` gains a `danger` variant (`border-danger bg-danger-soft text-danger`, reusing the exact token combo from `ticket-provider-picker.tsx`'s error alert — the ONE new color usage this phase introduces, no new hex); a `state.kind === 'unsafe'` branch renders the danger card with the LOCKED "This guidance was withheld for safety" copy and no action button, positioned right after the existing `grounded_false` branch; a `cacheQuery.data?.cached === false && cacheQuery.data?.groundable === false` branch renders the neutral insufficient-evidence card with no button, checked `=== false` explicitly and positioned before the Analyst-trigger branch so it never fires for the three original resourceTypes' GET responses (which never carry the field at all). The component also now derives resourceType-scoped copy (section header, CTA label, Viewer-empty text, and the shared insufficient-evidence heading/body reused by both state 3 and state 8) for `resourceType === 'remediation-guidance'`, while `vuln`/`host`/`remediation` retain byte-identical copy to before.
- `ai-explanation-section.test.tsx`: 12 new tests across 4 new `describe` blocks proving the danger card's LOCKED copy and no-button contract, that the danger card is visually distinct from the neutral card (Pitfall 3 — never conflated), the groundable pre-refusal branch (`=== false` suppresses the trigger; `undefined`/`true` still show it), and that the section header/CTA/viewer-empty copy is `remediation-guidance`-only while the three original views are unaffected. 47/47 green (35 pre-existing + 12 new).
- `drill-content.tsx`: new `<section aria-labelledby="drill-remediation-guidance-h">` mounted immediately after the raw `drill-remed-h` section and before `drill-activity-h`, rendering `<AiExplanationSection resourceType="remediation-guidance" resourceId={v.id ?? idOrCve} headingId="drill-remediation-guidance-h" />`. Mobile is covered by the same insertion (`drill-panel-mobile.tsx` renders `DrillContent` directly). No `onCopyToDescription` prop is passed — that affordance is AIR-02, deferred to Plans 06/07.
- `drill-panel.test.tsx`: the pre-existing 8-section order assertion extended to 9 sections (adds "Remediation guidance" between Remediation and Activity); a new document-order test proves the new section sits strictly between the two via direct DOM index comparison. 19/19 green (2 test files: drill-panel + drill-panel-mobile).
- Full frontend suite: 826/826 green (130 test files), `tsc --noEmit` clean, `eslint` clean on every touched file.

## Task Commits

1. **Task 1: Additive type members + the two new states + groundable pre-refusal branch**
   - `48b1433` (feat) — `use-explain-stream.ts`, `use-explain-cache.ts`, `ai-explanation-section.tsx`, `ai-explanation-section.test.tsx` (47/47 passed)
2. **Task 2: Mount the Remediation guidance section in the drill panel**
   - `95f07a8` (feat) — `drill-content.tsx`, `drill-panel.test.tsx` (19/19 passed)

**Plan metadata:** (this commit) — SUMMARY.md + STATE.md + ROADMAP.md

## Files Created/Modified
- `frontend/src/lib/ai/use-explain-stream.ts` — added `'unsafe'` to both closed unions
- `frontend/src/lib/queries/use-explain-cache.ts` — added optional `groundable` field to the cache-miss shape
- `frontend/src/components/ai/ai-explanation-section.tsx` — danger variant, unsafe-kind branch, groundable===false branch, resourceType-scoped locked copy
- `frontend/src/components/ai/ai-explanation-section.test.tsx` — 12 new tests (danger card, Pitfall-3 distinctness, groundable pre-refusal, locked copy)
- `frontend/src/components/vulnerabilities/drill-content.tsx` — new Remediation guidance section mount
- `frontend/src/components/vulnerabilities/drill-panel.test.tsx` — extended section-order test (8→9) + new document-order test

## Decisions Made

See `key-decisions` in frontmatter. In short: Task 1's literal `<action>` text covered the danger variant + unsafe branch + groundable branch, but 25-UI-SPEC.md's Copywriting Contract explicitly locks distinct header/CTA/viewer-text/insufficient-evidence copy for this 4th resourceType (D-06: "its own trigger and its own cite-or-refuse output — distinct from Phase 24's 'Explain this vuln'"). Implementing the danger/groundable branches alone without also branching the copy would have shipped a "Remediation guidance" section that literally says "AI Explanation" / "Explain this vuln" / "No AI explanation generated yet." — directly contradicting the locked design contract the ui_requirement explicitly mandated using verbatim. This was treated as Rule 2 (auto-add missing critical functionality required by the design contract), implemented as a minimal `isRemediationGuidance` derivation inside the existing component rather than new props, keeping the diff additive and leaving all three original resourceTypes' tests unaffected (47/47 and 826/826 green).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] resourceType-scoped locked copy (header/CTA/viewer-text/insufficient-evidence) for the new section**
- **Found during:** Task 1
- **Issue:** Task 1's `<action>` text specified only the danger variant, the unsafe-kind branch, and the groundable pre-refusal branch — it did not specify how the section's header ("AI Explanation"), trigger button ("Explain this vuln"), Viewer-empty text ("No AI explanation generated yet."), or the existing `grounded_false`/cache/done "not grounded" card copy ("Not enough finding data to explain this reliably") would differ for the new `remediation-guidance` resourceType. 25-UI-SPEC.md's Copywriting Contract explicitly locks different strings for all four ("Remediation guidance" / "Get remediation guidance" / "No remediation guidance generated yet." / "Not enough vendor guidance to recommend a fix"), and D-06 explicitly frames this as "its own trigger and its own cite-or-refuse output — distinct from Phase 24's 'Explain this vuln'."
- **Fix:** Added a minimal `isRemediationGuidance = resourceType === 'remediation-guidance'` derivation inside `AiExplanationSection`, producing `heading`/`triggerLabel`/`viewerEmptyText`/`insufficientEvidenceCopy` constants consumed by the h4, the trigger button, the Viewer-empty `<p>`, and all four "insufficient evidence" render sites (state 3's new branch, state 8's `grounded_false` branch, the `done`+`!grounded` backstop, and the cache-hit+`!grounded` branch) — the last three of which pre-existed for `vuln`/`host`/`remediation` and previously hardcoded the old copy inline.
- **Files modified:** `frontend/src/components/ai/ai-explanation-section.tsx`, `frontend/src/components/ai/ai-explanation-section.test.tsx`
- **Verification:** New tests assert the locked strings render for `resourceType="remediation-guidance"` and that `vuln`/`host` mounts are unaffected (still "AI Explanation" / "Explain this vuln" / "No AI explanation generated yet."). Full suite 826/826 green.
- **Committed in:** `48b1433` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical functionality, driven by the design contract)
**Impact on plan:** Necessary for the new section to actually match 25-UI-SPEC.md's locked Copywriting Contract rather than silently inheriting Phase 24's vuln-flavored copy. No scope creep beyond the plan's own governing design document — AIR-02's "Copy into ticket description" affordance was NOT added (correctly deferred to Plans 06/07).

## Issues Encountered

None blocking. A pre-existing type-inference gap surfaced while writing the new `drill-panel.test.tsx` document-order test (`querySelectorAll('section')` returning `Element[]`, `.indexOf()` expecting `HTMLElement`) — resolved by typing the selectors with `querySelectorAll<HTMLElement>`/`querySelector<HTMLElement>` rather than casting, confirmed clean via `tsc --noEmit`.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- The end-to-end per-vuln remediation-guidance slice (AIR-01) is now code-complete front to back: backend grounding + cite-or-refuse two-layer defense + engine-level safety gate + RBAC + `groundable` pre-signal (Plans 01–03) all the way through the frontend's danger/neutral typed states, the `groundable` pre-click refusal, and the new drill-panel section reusing Phase 24's chrome unchanged.
- Remaining phase scope (not this plan, explicitly deferred): AIR-02's "Copy into ticket description" callback + the ticket-create dialog's description-textarea pre-fill (Plans 06/07), per D-08/D-09's scope fence.
- No blockers.

---
*Phase: 25-asset-aware-remediation-guidance*
*Completed: 2026-07-30*

## Self-Check: PASSED

All 6 claimed source/test files found on disk; both claimed commit hashes (`48b1433`, `95f07a8`) found in git log.
