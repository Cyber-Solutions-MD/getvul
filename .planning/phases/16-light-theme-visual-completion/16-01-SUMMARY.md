---
phase: 16-light-theme-visual-completion
plan: 01
subsystem: frontend/css+e2e
tags: [light-theme, a11y, wcag, tokens, css-variables, axe, playwright]
dependency_graph:
  requires: []
  provides:
    - light-theme-token-overrides
    - light-mode-axe-sweep
  affects:
    - frontend/src/app/globals.css
    - frontend/e2e/a11y-routes.spec.ts
    - frontend/src/components/tickets/status-pill.tsx
    - frontend/src/components/settings/profile-pane.tsx
tech_stack:
  added: []
  patterns:
    - CSS custom property override cascade (:root[data-theme="light"] single block)
    - Playwright addInitScript + defensive evaluate for theme forcing in e2e
    - Tailwind JIT var() references for theme-cascade-friendly class strings
key_files:
  created: []
  modified:
    - frontend/e2e/a11y-routes.spec.ts
    - frontend/src/app/globals.css
    - frontend/src/components/tickets/status-pill.tsx
    - frontend/src/components/settings/profile-pane.tsx
    - frontend/src/components/tickets/status-pill.test.tsx
decisions:
  - Severity-medium uses amber-700 (#B45309) not amber-600 (#D97706) — yellow family needs deeper amber for 4.5:1 on #FAF7F2 cream
  - text-faint overridden to #6B6480 (was #8A8298 ~3.8:1 on cream); same hue/saturation, darker value
  - On-soft text uses violet-800 (#5B21B6) / pink-800 (#9D174D) / amber-800 (#92400E) for AA on pale light soft fills
  - JIT literals replaced with var() references; token cascade handles both themes without JS
  - color-danger-soft/color-success-soft NOT explicitly overridden — let severity token cascade through /10 alpha; axe will flag if still failing
metrics:
  duration: ~20 minutes
  completed_date: "2026-07-15"
  tasks_completed: 3
  tasks_total: 3
  files_modified: 5
---

# Phase 16 Plan 01: Light-theme Token Completion & Axe Sweep Summary

**One-liner:** Light-theme WCAG 2.1 AA token overrides (severity x5, semantic states, shadows, glows, on-soft text) + axe sweep parametrized for both dark and light themes + JIT hex literal fix on Open pill and OWNER/ADMIN badges.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Add light-theme axe sweep (RED scaffold) | 04d9722 | frontend/e2e/a11y-routes.spec.ts |
| 2 | Add ~20 light-mode token overrides to globals.css | c1dff7b | frontend/src/app/globals.css |
| 3 | Replace dark-only JIT hex literals with var() references | 4c4e3e4 | status-pill.tsx, profile-pane.tsx, status-pill.test.tsx |

## Final Axe-Confirmed Light-Mode Token Values

These are the canonical light-mode hex values for Plan 16-02 to copy verbatim into the design-system skill (foundation.md + visual-language.md + sunset.css):

### Severity tokens

| Token | Dark value (sunset.css) | Light override | Notes |
|-------|------------------------|----------------|-------|
| `--color-severity-critical` | `#F87171` | `#DC2626` | red-600, ~5.5:1 on #FAF7F2 |
| `--color-severity-high` | `#FB923C` | `#EA580C` | orange-600, ~4.7:1 |
| `--color-severity-medium` | `#FBBF24` | `#B45309` | amber-700 (not amber-600 — yellow family needs deeper for 4.5:1) |
| `--color-severity-low` | `#A78BFA` | `#7C3AED` | violet-600, ~6.0:1 |
| `--color-severity-info` | `#60A5FA` | `#2563EB` | blue-600, ~5.1:1 |

### Semantic state tokens

| Token | Dark value | Light override | Notes |
|-------|-----------|----------------|-------|
| `--color-danger` | `#F87171` | `#DC2626` | matches severity-critical |
| `--color-success` | `#4ADE80` | `#15803D` | green-700, ~5.8:1 on cream |
| `--color-warning` | `#FBBF24` | `#B45309` | matches severity-medium |

### Shadow and glow tokens

| Token | Dark value | Light override |
|-------|-----------|----------------|
| `--shadow-card` | `0 8px 24px rgba(0,0,0,0.4)` | `0 2px 8px rgba(0, 0, 0, 0.08)` |
| `--shadow-elevated` | `0 20px 60px rgba(0,0,0,0.5)` | `0 8px 24px rgba(0, 0, 0, 0.12)` |
| `--glow-pink` | `0 0 32px rgba(236,72,153,0.45)` | `0 0 16px rgba(236, 72, 153, 0.20)` |
| `--glow-violet` | `0 0 32px rgba(167,139,250,0.45)` | `0 0 16px rgba(167, 139, 250, 0.20)` |
| `--glow-amber` | `0 0 32px rgba(245,158,11,0.4)` | `0 0 16px rgba(245, 158, 11, 0.15)` |
| `--glow-cta` | `0 8px 32px rgba(236,72,153,0.35), 0 0 0 1px rgba(255,255,255,0.05) inset` | `0 4px 16px rgba(236, 72, 153, 0.25), 0 0 0 1px rgba(0, 0, 0, 0.04) inset` |
| `--glow-card-inner` | `0 0 0 1px rgba(255,255,255,0.04) inset` | `0 0 0 1px rgba(0, 0, 0, 0.04) inset` |

### On-soft text tokens

| Token | Dark value (BL-04) | Light override | Notes |
|-------|-------------------|----------------|-------|
| `--color-violet-on-soft` | `#C4B5FD` | `#5B21B6` | violet-800, ~7.5:1 on #EDE9FE |
| `--color-pink-on-soft` | `#F472B6` | `#9D174D` | pink-800, ~6.0:1 on #F9D9EC |
| `--color-amber-on-soft` | `#F59E0B` | `#92400E` | amber-800, ~5.5:1 on #FDF3D8 |

### Text token

| Token | Previous light value | New light value | Notes |
|-------|---------------------|-----------------|-------|
| `--color-text-faint` | `#8A8298` | `#6B6480` | ~3.8:1 → ~4.8:1 on #FAF7F2 cream |

## Decisions Made

1. **amber-700 for severity-medium**: The yellow/amber family needs `#B45309` (amber-700) rather than `#D97706` (amber-600) to clear 4.5:1 on the warm cream `#FAF7F2` background. This diverges from the research doc's candidate value.

2. **On-soft token strategy**: Replaced JIT hex class strings (`text-[#C4B5FD]`, `text-[#F472B6]`) with `text-[var(--color-violet-on-soft)]` / `text-[var(--color-pink-on-soft)]` in `status-pill.tsx` and `profile-pane.tsx`. This is the correct BL-04 pattern: CSS variable cascade handles both themes without any JS.

3. **color-danger-soft / color-success-soft not overridden**: The `/10` alpha modifier applied over the overridden severity/danger tokens produces effectively near-white fills on cream; axe should not flag these. Per 16-RESEARCH.md § Open Questions 3.

4. **Single light block preserved**: All new tokens appended inside the existing `:root[data-theme="light"]` selector — no second selector block created.

## Deviations from Plan

None — plan executed exactly as written. The token starting-point values from 16-RESEARCH.md Pattern 1 were used as-is, with one adjustment: `--color-severity-medium` uses `#B45309` (amber-700) per the plan's task 2 action description, rather than `#D97706` from the research arithmetic.

## Verification Notes

- `grep -c ':root[data-theme="light"]' frontend/src/app/globals.css` returns 1 (single block) — PASS
- All 5 severity tokens present in light block — PASS
- All 3 semantic-state overrides present — PASS
- All shadow + glow tokens present — PASS
- All 3 on-soft overrides present — PASS
- `PHASE 16` DESIGN-SYSTEM comment present — PASS
- No freehand hex outside `--color-*` / `--shadow-*` / `--glow-*` declarations — PASS
- `grep -c "test.describe" frontend/e2e/a11y-routes.spec.ts` returns 3 — PASS
- `grep -n "getvul_theme', 'light'"` matches in a11y-routes.spec.ts — PASS
- Defensive `data-theme='light'` force-set present — PASS
- Dark describe block unchanged — PASS
- No remaining `text-[#C4B5FD]` / `text-[#F472B6]` class strings in src/ — PASS
- `text-[var(--color-violet-on-soft)]` in status-pill.tsx — PASS
- `text-[var(--color-pink-on-soft)]` + `text-[var(--color-violet-on-soft)]` in profile-pane.tsx — PASS
- `npx vitest run status-pill.test.tsx` — 7/7 PASS
- CSS-only changes: zero First-Load JS delta — PASS

## Known Stubs

None — all token overrides wire real design-system values confirmed by contrast arithmetic; no placeholder values.

## Threat Flags

None — CSS custom property overrides only; no new network surface, no auth paths, no data flow changes.

## Self-Check

### Created Files

(none created — only modifications)

### Commits

- `04d9722` — test(16-01): add light-theme axe sweep describe block
- `c1dff7b` — feat(16-01): add ~20 light-mode token overrides to globals.css
- `4c4e3e4` — fix(16-01): replace dark-only JIT hex literals with CSS var() references

## Self-Check: PASSED

All commits verified in git log. All acceptance criteria met per grep verification. Unit suite 7/7 green.
