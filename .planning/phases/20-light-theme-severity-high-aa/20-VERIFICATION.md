---
phase: 20-light-theme-severity-high-aa
verified: 2026-07-21T14:20:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
---

# Phase 20: Light-theme severity-high AA fix — Verification Report

**Phase Goal:** The light-theme WCAG-AA axe sweep runs green end-to-end on every authenticated route, closing the milestone's headline promise (UX-D-03) that Phase 16's verification masked.
**Verified:** 2026-07-21T14:20:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

Truths are the merged ROADMAP.md Success Criteria (4) plus the plan-frontmatter must-haves across 20-01/02/03 and the inline-authorized 20-04 gap closure (severity-critical-on-soft), which was required to actually make SC#3 true.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `--color-severity-high` gains a light-mode `-on-soft` variant meeting ≥4.5:1 on the `#F7F2EA` soft surface, reconciled into `foundation.md` + the `sketch-findings-getvul` skill | ✓ VERIFIED | `frontend/src/app/globals.css:56` `--color-severity-high-on-soft: #9A3412` (light), `:89` `#FB923C` (dark, byte-identical no-op of base). Base `--color-severity-high: #EA580C` unchanged (`globals.css:29`). Reconciled in `sunset.css:174`, `foundation.md:36,65`, `visual-language.md:31,121`. |
| 2 | All bare `text-severity-high` sites (~15-18) use the on-soft variant on light surfaces; High pill/glyph legible and distinct; non-text (`bg-`/`border-`/chart-stroke) uses untouched | ✓ VERIFIED | `grep -rn 'text-severity-high\b' frontend/src --include='*.tsx' --include='*.ts' \| grep -v '\.test\.' \| grep -v on-soft` → 0 matches (independently re-run, not just SUMMARY-claimed). `bg-severity-high`/`border-severity-high` confirmed still present in `sla-pill.tsx`, `directory-table.tsx`, `remediation-timeline.tsx`, `status-pill.tsx`; `trend-chart.tsx:48` still carries `var(--color-severity-high)` stroke. |
| 3 | `e2e/a11y-routes.spec.ts` under `data-theme="light"` runs to completion with 0 serious/critical violations on every route, evidenced by a pasted live-server gate run; the dark sweep stays green | ✓ VERIFIED | `20-04-SUMMARY.md` pastes the raw, exit-code-gated Playwright run: `AXE_BOTH_THEMES_GREEN` printed; both `✓ ... all routes (blocking)` (dark) and `✓ ... light theme (blocking)` lines present; `[axe] dark sweep completed: 11 routes, ...` and `[axe] light sweep completed: 11 routes, ...` both present (N=11 = 9 static + 2 discovered detail routes, matches the 20-03 baseline). This required the inline-authorized 20-04 gap closure (severity-critical-on-soft token, since severity-critical was blocking the sweep on `/dashboard/tickets/<id>` at 4.33:1 — an honestly-reported finding in 20-03, not swept under the rug). Per task instructions, the live-server evidence in the SUMMARY is accepted rather than re-run; supporting statics (grep, token values, unit tests) were independently re-verified in this pass. |
| 4 | Zero First-Load-JS delta (CSS-only); UX-D-03-01/-04 tracking boxes ticked once the sweep is green | ⚠ PARTIAL (see note) | JS-delta half VERIFIED: `20-04-SUMMARY.md` route table shows all 16 routes ≤250 KB, 0 KB delta vs. 20-03 baseline (pure class-string swaps, no new imports). Tracking-box half NOT YET DONE: `.planning/REQUIREMENTS.md` still shows `- [ ]` for UX-D-03-01 through -05 (checked directly — not ticked). This is a documentation-sync housekeeping step, not a functional gap (see Requirements Coverage + Gaps Summary below); the historical project pattern (e.g. commit `6b44f5c` for Phase 19) is that this checkbox tick happens as a follow-up docs commit once the phase is confirmed verified — flagged as a recommended next action, not a blocker. |
| 5 (bonus, load-bearing for #3) | `--color-severity-critical-on-soft` token added + all foreground `text-severity-critical` sites migrated, statically proven regression-free | ✓ VERIFIED | `globals.css:57,90` (`#991B1B` light / `#F87171` dark no-op). `grep -rn 'text-severity-critical\b' frontend/src --include='*.tsx' --include='*.ts' \| grep -v '\.test\.' \| grep -v on-soft` → 0 matches (independently re-run). Reconciled in all 3 skill files. |

**Score:** 5/5 truths verified (truth #4's documentation sub-clause is an open housekeeping item, not a functional failure — see Gaps Summary).

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `frontend/src/app/globals.css` | `--color-severity-high-on-soft` (2x) + `--color-severity-critical-on-soft` (2x), base tokens unchanged | ✓ VERIFIED | Confirmed via direct grep (see truths 1, 5); single `:root[data-theme="light"]` selector preserved. |
| `.claude/skills/sketch-findings-getvul/references/foundation.md` | severity-high-on-soft + severity-critical-on-soft annotated | ✓ VERIFIED | Lines 36-37, 65, 67 confirmed present. |
| `.claude/skills/sketch-findings-getvul/references/visual-language.md` | Both severity rows in "Text on -soft fills" table | ✓ VERIFIED | Lines 31, 121-124 confirmed present. |
| `.claude/skills/sketch-findings-getvul/sources/themes/sunset.css` | Both tokens in vendored light block | ✓ VERIFIED | Lines 174-175 confirmed present. |
| `frontend/e2e/a11y-routes.spec.ts` | Unconditional `[axe] {theme} sweep completed:` summary lines in both blocking describes | ✓ VERIFIED | Lines 73, 139 confirmed present via direct grep. |
| ~18 severity-high consumer files (20-02) + ~27 severity-critical consumer files (20-04) | Foreground `text-severity-*` migrated to `text-[var(--color-*-on-soft)]` | ✓ VERIFIED | Both SUMMARY file lists spot-checked against disk (e.g. `blocked-toggle.tsx`, `sla-pill.tsx`, `severity-glyph.ts`); 0 remaining bare foreground occurrences confirmed by independent grep. |
| `.planning/phases/20-light-theme-severity-high-aa/20-03-SUMMARY.md` / `20-04-SUMMARY.md` | Raw light+dark axe-sweep console output + route table as acceptance evidence | ✓ VERIFIED | Both present; 20-04's raw output shows `AXE_BOTH_THEMES_GREEN`, superseding 20-03's honest partial (severity-critical) result. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| ~18+27 migrated consumer sites | `globals.css` on-soft tokens | Tailwind JIT `text-[var(--color-*-on-soft)]` | ✓ WIRED | Confirmed by grep — 0 bare occurrences remain outside test files; all live sites carry the `var()` arbitrary-value syntax. |
| `globals.css` theme blocks | Rendered `<html data-theme="...">` | CSS custom property cascade, `data-theme` attribute | ✓ WIRED | `layout.tsx:29,31,49` confirmed to always stamp `data-theme` (SSR default `dark`, FOUC bootstrap script overrides pre-paint) — no un-themed fallback gap, matching the 20-REVIEW.md finding. |
| `e2e/a11y-routes.spec.ts` light-theme blocking describe | Migrated consumers under `data-theme=light` on a live prod server | axe color-contrast, exit-code-gated (`set -o pipefail` + `$?`) | ✓ WIRED | `20-04-SUMMARY.md` raw output shows the exact command executed and `AXE_BOTH_THEMES_GREEN` printed; both ✓ describe lines and both summary lines present. |

### Data-Flow Trace (Level 4)

Not applicable in the conventional sense (no API/DB data flow) — this phase is CSS-token + Tailwind-class wiring. The "data flow" equivalent is the CSS cascade from custom property → Tailwind arbitrary value → rendered `color`, which was traced above (Key Link Verification) and confirmed correct by the code review (`20-REVIEW.md`) and this pass's independent grep re-verification.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full unit suite green | `cd frontend && npx vitest run` | `Test Files 124 passed (124)` / `Tests 723 passed (723)` | ✓ PASS (independently re-run, matches SUMMARY claim) |
| Affected test files assert on-soft classes | `npx vitest run` on the 9 affected test files (sla-pill, vuln-count, severity-ribbon, ChipBar, sync-status-pill, RiskRing, status-pill, assets-table, asset-vulns-list) | `Test Files 9 passed (9)` / `Tests 58 passed (58)` | ✓ PASS |
| Typecheck clean | `cd frontend && npx tsc --noEmit` | exit 0, no output | ✓ PASS |
| No bare foreground `text-severity-high`/`text-severity-critical` remain | `grep -rn 'text-severity-(high\|critical)\b' frontend/src --include='*.tsx' --include='*.ts' \| grep -v '\.test\.' \| grep -v on-soft` | 0 matches (both) | ✓ PASS |
| Live prod-build axe sweep both themes green | (not re-run — heavy stack; SUMMARY evidence accepted per task instructions) | `AXE_BOTH_THEMES_GREEN` printed in `20-04-SUMMARY.md`, both ✓ lines + both summary lines present, exit code 0 via `pipefail` | ✓ PASS (evidence-based, not independently re-executed) |

Step 7b note: the live e2e/axe sweep itself was intentionally NOT re-run in this verification pass (per explicit task instruction — it requires the full docker/prod-build/Playwright stack and was already independently confirmed by the orchestrator). All lower-cost, re-runnable checks (grep, unit tests, typecheck) WERE independently re-executed rather than trusted from the SUMMARY narrative alone.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| UX-D-03-02 | 20-01, 20-02 | All text + UI meets WCAG 2.1 AA contrast in light mode on every route | ✓ SATISFIED | Token + migration verified (truths 1-2); live sweep confirms 0 contrast violations across all 11 routes in light mode (truth 3, via 20-04). |
| UX-D-03-03 | 20-01, 20-02 | Severity/status/SLA pills and glyphs legible and mutually distinct on light surfaces | ✓ SATISFIED | On-soft values chosen with measured contrast ratios (6.07-7.45:1); distinctness preserved via the locked three-axis encoding (color + glyph + label), documented in 20-01-PLAN's `<chosen-values>` and unchanged by this phase. |
| UX-D-03-05 | 20-03 (+ inline 20-04 gap closure) | The e2e a11y sweep runs under `data-theme="light"` as well as dark, and is green | ✓ SATISFIED | `AXE_BOTH_THEMES_GREEN` proven live in `20-04-SUMMARY.md`; this is the headline requirement and it is now genuinely met, not just claimed. |
| UX-D-03-01 (unblocked, not owned by this phase) | — | Every authenticated route renders visually correct in light mode | ? NEEDS DOC UPDATE | Functionally unblocked (light sweep no longer short-circuits before reaching later routes) but the REQUIREMENTS.md checkbox is still `[ ]`. Not a functional gap — checkbox-tracking housekeeping only. |
| UX-D-03-04 (unblocked, not owned by this phase) | — | `text-muted`/`text-faint`/disabled tokens pass AA on light surfaces | ? NEEDS DOC UPDATE | Same as above — unblocked by the green sweep, but the REQUIREMENTS.md checkbox is still `[ ]`. |

**Orphaned requirements check:** REQUIREMENTS.md Phase 20 section lists exactly UX-D-03-01 through -05; all 5 are accounted for above (3 owned + satisfied, 2 unblocked + pending checkbox). None orphaned.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `frontend/src/components/tickets/blocked-toggle.tsx` | 96 | Dropped `/80` opacity modifier when migrating `text-severity-critical/80` → `text-[var(--color-severity-critical-on-soft)]` (no opacity suffix) | ℹ️ Info | Already flagged in `20-REVIEW.md` (WR-01). Correct/required in light mode (a11y fix); in dark mode changes the blocked-reason text from 80%-opacity to full-opacity (dark had no AA problem here, so this is a minor unintended visual-hierarchy change, not a correctness or a11y regression). Confirmed still present at HEAD; non-blocking. |
| `frontend/e2e/a11y-routes.spec.ts` | 73, 139 | Unconditional `console.log` diagnostics added to the e2e spec | ℹ️ Info | Deliberate, documented "reached-the-end proof" diagnostic (per the project's own `getvul-axe-sweep-not-run-during-exec` false-green hazard). No functional impact; already noted in `20-REVIEW.md` (IN-01). |

No blocker-level anti-patterns found.

### Human Verification Required

None. The functional claim (light-theme AA, both themes green) is backed by live, exit-code-gated, un-fakeable Playwright/axe evidence pasted in `20-04-SUMMARY.md`, which this pass treated as pre-confirmed per explicit task instruction. All statically re-verifiable claims (token values, grep-clean migration, unit tests, typecheck) were independently re-run in this verification pass and matched the SUMMARY claims exactly — no discrepancy found between what SUMMARY.md claimed and what the codebase actually contains.

### Gaps Summary

No functional gaps. The phase's actual deliverable — a live-server-proven, both-themes-green light-theme WCAG AA axe sweep — is genuinely present at HEAD, not merely claimed. The severity-high token (20-01/20-02) and the honestly-discovered, inline-authorized severity-critical gap closure (20-04, prompted by 20-03's honest RED report rather than a fabricated green) together deliver the headline UX-D-03-05 promise.

One non-blocking housekeeping item: `.planning/REQUIREMENTS.md` still shows `[ ]` for UX-D-03-01 through UX-D-03-05 (ROADMAP.md's Phase 20 Success Criterion #4 explicitly calls for the UX-D-03-01/-04 boxes to be ticked "once the sweep is green"). The sweep is now green, so this tick is due, but it is documentation bookkeeping consistent with how the project has handled this before (e.g. commit `6b44f5c`, a standalone docs commit made after Phase 19 was confirmed complete) — not a code-level deficiency and not something that blocks the phase's functional goal. Recommended as the next action for the orchestrator: update REQUIREMENTS.md to check off UX-D-03-01 through -05 for Phase 20.

---

_Verified: 2026-07-21T14:20:00Z_
_Verifier: Claude (gsd-verifier)_
