---
phase: 20-light-theme-severity-high-aa
plan: 01
subsystem: ui
tags: [design-tokens, css-custom-properties, wcag-aa, light-theme, sketch-findings-getvul]

# Dependency graph
requires:
  - phase: 16-light-theme-visual-completion
    provides: the on-soft token pattern (violet/pink/amber-on-soft) established in Phase 16 WR-04, which this plan mirrors exactly for severity-high
provides:
  - "--color-severity-high-on-soft CSS custom property (light #9A3412, dark #FB923C — dark no-op) in frontend/src/app/globals.css"
  - "Reconciled design-system skill (foundation.md, visual-language.md, sunset.css) documenting the new token"
affects: [20-02-plan (consumer migration of ~18 components from bare text-severity-high to text-severity-high-on-soft on soft/tinted surfaces)]

# Tech tracking
tech-stack:
  added: []
  patterns: ["-on-soft token pair (light dark-same-hue shade / dark byte-identical no-op) for text rendered on an accent's soft/tinted fill — now covers all 4 on-soft tokens (violet, pink, amber, severity-high)"]

key-files:
  created: []
  modified:
    - frontend/src/app/globals.css
    - .claude/skills/sketch-findings-getvul/references/foundation.md
    - .claude/skills/sketch-findings-getvul/references/visual-language.md
    - .claude/skills/sketch-findings-getvul/sources/themes/sunset.css

key-decisions:
  - "Light value #9A3412 (orange-800): 6.56:1 on #F7F2EA surface-2, 6.84:1 on #FAF7F2 bg, 6.07:1 on the severity-high /10 tint — all clear WCAG 2.1 AA 4.5:1 (base #EA580C measured only 3.19:1 on the soft surface)"
  - "Dark value #FB923C is byte-identical to the existing --color-severity-high dark value, making the Plan 20-02 consumer migration a true dark no-op (mirrors the WR-02 amber-on-soft precedent)"
  - "Distinctness preserved via the locked three-axis encoding (color + glyph + label), not hue alone — #9A3412 sitting near #B45309 (Medium) in light mode is acceptable per the design system's existing severity choices"

patterns-established: []

requirements-completed: [UX-D-03-02, UX-D-03-03]

# Metrics
duration: 12min
completed: 2026-07-21
---

# Phase 20 Plan 01: severity-high-on-soft Token Summary

**Added the missing `--color-severity-high-on-soft` design token (light #9A3412 / dark #FB923C no-op) and reconciled it into the sketch-findings-getvul skill, closing the gap where the bare severity-high text measured only 3.19:1 on light soft/tinted surfaces.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-21T08:50:00Z (approx, per STATE.md last_updated)
- **Completed:** 2026-07-21T09:02:44Z
- **Tasks:** 2 completed
- **Files modified:** 4

## Accomplishments
- `--color-severity-high-on-soft` added to both theme blocks of `frontend/src/app/globals.css` (light #9A3412, dark #FB923C), purely additive — base `--color-severity-high` and the light selector are unchanged
- All three design-skill files (`sunset.css`, `foundation.md`, `visual-language.md`) reconciled to document the new token in the same style as the existing violet/pink/amber-on-soft rows, so the skill and live CSS now agree per CLAUDE.md's reconciliation requirement
- Established the single source of truth Plan 20-02 will build its consumer migration against (~18 components currently using bare `text-severity-high`)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add --color-severity-high-on-soft to globals.css (light + dark blocks)** - `96887d2` (feat)
2. **Task 2: Reconcile the token into the design-system skill (foundation.md + visual-language.md + sunset.css)** - `3da20e6` (docs)

**Plan metadata:** (pending — see final commit below)

## Files Created/Modified
- `frontend/src/app/globals.css` - Added `--color-severity-high-on-soft: #9A3412` to the light `:root[data-theme="light"]` on-soft block and `--color-severity-high-on-soft: #FB923C` to the dark `:root[data-theme="dark"]` on-soft block
- `.claude/skills/sketch-findings-getvul/references/foundation.md` - Extended the on-soft annotation comment + added a light-mode severity-high-on-soft note under "Severity colors"
- `.claude/skills/sketch-findings-getvul/references/visual-language.md` - Added a `severity-high` row to the light-mode "Text on -soft fills" table + a note in the light-mode severity section
- `.claude/skills/sketch-findings-getvul/sources/themes/sunset.css` - Added `--color-severity-high-on-soft: #9A3412` to the vendored light on-soft block with a dark no-op parity comment

## Decisions Made
- Light value #9A3412 (Tailwind orange-800) chosen for measured contrast: 6.56:1 on surface-2 #F7F2EA, 6.84:1 on bg #FAF7F2, 6.07:1 on the severity-high /10 tint — all clear AA 4.5:1
- Dark value #FB923C set byte-identical to the existing `--color-severity-high` dark value so the Plan 20-02 migration is a guaranteed dark no-op
- Distinctness from Medium (#B45309) in light mode is acceptable — the three-axis encoding (color + glyph ▲/◆ + text label) carries distinctness, not hue alone; explicitly documented in the plan's `<chosen-values>` section

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

**Worktree stale-base hazard (pre-task, resolved before any plan work began):** The worktree branch check found `git merge-base HEAD <target>` did not equal `<target>` — this worktree's branch had been forked from an older commit (`7c9063a`, right after Phase 16 was only *planned*) rather than the current main tip (`804c72b`, after Phases 16–19 were fully executed and Phase 20 begun). Following the branch-check instructions literally with `git reset --soft <target>` would have staged what amounted to a silent revert of Phases 16–19 (dozens of `D` entries for already-shipped SUMMARY/REVIEW/VERIFICATION/component files) — the exact stale-base hazard documented in project memory. Recognized this before committing anything, and instead ran `git reset --hard <target>` (explicitly permitted for this startup step per the destructive-git-prohibition carve-out) to fully align HEAD, index, and working tree to the correct base. Verified `.planning/phases/20-light-theme-severity-high-aa/` then contained the expected plan files and `git status --short` was clean before starting Task 1. No prior work was lost or reverted.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Plan 20-02 (consumer migration) can now build against `--color-severity-high-on-soft` as an established, contrast-verified, skill-reconciled token
- Dark rendering is guaranteed unchanged (dark on-soft value = existing severity-high dark value), so Plan 20-02's dark axe sweep should stay green
- No blockers

---
*Phase: 20-light-theme-severity-high-aa*
*Completed: 2026-07-21*

## Self-Check: PASSED

All created/modified files confirmed present on disk; both task commit hashes (`96887d2`, `3da20e6`) confirmed in git log.
