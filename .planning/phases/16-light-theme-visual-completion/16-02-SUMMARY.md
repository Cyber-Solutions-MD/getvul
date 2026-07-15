---
phase: 16-light-theme-visual-completion
plan: 02
subsystem: design-system/skill+frontend/shell
tags: [light-theme, design-system, wcag, tokens, user-chip, a11y]
dependency_graph:
  requires:
    - 16-01 (axe-confirmed light-mode token values)
  provides:
    - light-mode-skill-reconciliation
    - theme-toggle-enabled
  affects:
    - .claude/skills/sketch-findings-getvul/sources/themes/sunset.css
    - .claude/skills/sketch-findings-getvul/references/foundation.md
    - .claude/skills/sketch-findings-getvul/references/visual-language.md
    - frontend/src/components/shell/user-chip.tsx
tech_stack:
  added: []
  patterns:
    - BL-04 reconciliation pattern applied to light mode (skill source-of-truth mirrors app layer)
    - Additive documentation — dark docs preserved, light annotations added inline
key_files:
  created: []
  modified:
    - .claude/skills/sketch-findings-getvul/sources/themes/sunset.css
    - .claude/skills/sketch-findings-getvul/references/foundation.md
    - .claude/skills/sketch-findings-getvul/references/visual-language.md
    - frontend/src/components/shell/user-chip.tsx
decisions:
  - Skill light hex values copy verbatim from 16-01-SUMMARY.md — no re-derivation to prevent drift
  - foundation.md annotation is inline (dark: <hex> — light: <hex>) rather than a separate table to keep the existing dark docs intact
  - Light radio matches Dark radio shape exactly (DropdownMenuRadioItem value="light") per the plan's target shape
metrics:
  duration: ~15 minutes
  completed_date: "2026-07-15"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 4
---

# Phase 16 Plan 02: Design-System Skill Reconciliation & Theme Toggle Summary

**One-liner:** BL-04 mirror for light mode — axe-confirmed light token values reconciled into the design-system skill (sunset.css + foundation.md + visual-language.md) and Theme: Light radio enabled (disabled attr + In-progress badge removed).

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Reconcile axe-confirmed light-mode token values into design-system skill | 332813f | sunset.css, foundation.md, visual-language.md |
| 2 | Enable the Theme: Light toggle in the user chip | e565334 | frontend/src/components/shell/user-chip.tsx |

## What Was Done

### Task 1 — Skill Reconciliation (BL-04 mirror for light mode)

All values copied verbatim from 16-01-SUMMARY.md "Final Axe-Confirmed Light-Mode Token Values" tables:

**sunset.css** — appended a `:root[data-theme="light"]` block at the end of the file (after the reset rules) with all overridden tokens:
- Severity x5: critical `#DC2626`, high `#EA580C`, medium `#B45309`, low `#7C3AED`, info `#2563EB`
- Semantic state x3: danger `#DC2626`, success `#15803D`, warning `#B45309`
- Shadows x2: shadow-card `0 2px 8px rgba(0,0,0,0.08)`, shadow-elevated `0 8px 24px rgba(0,0,0,0.12)`
- Glows x5: glow-pink, glow-violet, glow-amber, glow-cta, glow-card-inner (all reduced opacity/radius)
- On-soft x3: violet-on-soft `#5B21B6`, pink-on-soft `#9D174D`, amber-on-soft `#92400E`
- Text: text-faint `#6B6480`

**foundation.md** — additive inline annotation of each overridden token with its light value:
- text-faint line: `— light: #6B6480 (~4.8:1 on #FAF7F2 cream)` appended
- on-soft comment block: added light-mode on-soft hex list
- semantic-state tokens: `/* light: <hex> */` per token
- Severity colors section: `/* light: <hex> (name, ~ratio:1 on #FAF7F2) */` per token + explanatory "Light-mode note" paragraph
- Shadows & Glow section: inline light value per token + "Light-mode note" paragraph

**visual-language.md** — two additions:
1. Under severity table: new "Light-mode severity colors" subsection with a 4-column table (Level / Dark hex / Light hex / Light ratio) + three-axis encoding explanation
2. After the dark on-soft AA table: "**Light-mode variants**" paragraph + 4-column table (Fill / Text token (light) / Hex (light) / Contrast on fill) for all 3 on-soft tokens, with a note on the var() cascade pattern

### Task 2 — Toggle Enabled

`user-chip.tsx`: replaced the disabled Light radio + In-progress badge block with the clean form matching the Dark radio:

```tsx
<DropdownMenuRadioItem value="light">{'Theme: Light'}</DropdownMenuRadioItem>
```

Removed: `disabled` attr, `aria-description` (not-ready message), inner `<span>` wrapper, `{'In progress'}` badge, stale WR-03 comment. Updated the radio group comment to reflect Phase 16 shipped state.

## Verification

- `grep -n 'data-theme="light"' .claude/skills/sketch-findings-getvul/sources/themes/sunset.css` — PASS (line 145)
- `grep -qi "Light-mode variants" .claude/skills/sketch-findings-getvul/references/visual-language.md` — PASS
- `grep -niE "light-mode|light:" .claude/skills/sketch-findings-getvul/references/foundation.md` — PASS (14 matches)
- `grep -A3 'value="light"' frontend/src/components/shell/user-chip.tsx` — PASS (no `disabled`)
- `grep -n "In progress" frontend/src/components/shell/user-chip.tsx` — PASS (none)
- `grep -n "aria-description" frontend/src/components/shell/user-chip.tsx` — PASS (none)
- `grep -n "not ready\|WR-03" frontend/src/components/shell/user-chip.tsx` — PASS (none)
- `git diff --name-only 332813f~1..332813f` — PASS (only 3 skill files, no `frontend/` in Task 1)
- Hex values in sunset.css light block byte-match 16-01-SUMMARY.md — PASS (copied verbatim)

## Decisions Made

1. **Verbatim copy from SUMMARY.md**: All light hex values were copied from 16-01-SUMMARY.md without re-derivation. This prevents any drift between the app layer and the skill.

2. **Inline annotation pattern** for foundation.md: Added `/* light: <hex> */` comments inline on each token rather than a separate table. Keeps the existing dark-mode documentation intact while making both values visible side-by-side.

3. **Additive-only approach** for all three skill files: No existing dark-mode content was removed or restructured — light-mode information was added in dedicated sections or inline comments.

## Deviations from Plan

None — plan executed exactly as written. All three skill files updated as specified; user chip light radio enabled matching the Dark radio shape.

## Known Stubs

None — all changes are documentation reconciliation and a real functional toggle enable.

## Threat Flags

None — CSS/documentation files and a one-line component attribute change. No new network surface, auth paths, data flow changes, or schema changes.

## Self-Check

### Modified Files Present

- `.claude/skills/sketch-findings-getvul/sources/themes/sunset.css` — FOUND
- `.claude/skills/sketch-findings-getvul/references/foundation.md` — FOUND
- `.claude/skills/sketch-findings-getvul/references/visual-language.md` — FOUND
- `frontend/src/components/shell/user-chip.tsx` — FOUND

### Commits

- `332813f` — feat(16-02): reconcile axe-confirmed light-mode token values into design-system skill
- `e565334` — feat(16-02): enable Theme: Light toggle in user chip

## Self-Check: PASSED

All commits verified in git log. Skill files contain light-mode overrides. Toggle enabled and acceptance criteria verified by grep.
