---
phase: 16-light-theme-visual-completion
verified: 2026-07-15T18:30:00Z
status: gaps_found
score: 2/4 must-haves verified
overrides_applied: 0
gaps:
  - truth: "e2e/a11y-routes.spec.ts runs under data-theme=\"light\" and reports 0 serious/critical axe violations on every route"
    status: failed
    reason: "The light-theme axe describe block was added (structural requirement met) but there is no evidence it was ever executed against a running server. The most recent playwright-report/index.html and test-results/.last-run.json are both dated 2026-06-30 — 15 days before the Phase 16 commits (first commit: 04d9722, 2026-07-15). CI does not run Playwright at all (zero playwright references in .github/workflows/ci.yml). The SUMMARY self-check lists only grep assertions and a vitest unit run — no playwright invocation is recorded. SC#2 is structurally present but operationally unproven."
    artifacts:
      - path: "frontend/e2e/a11y-routes.spec.ts"
        issue: "Spec exists and is correctly structured; the light describe block (lines 74-135) is wired. However: no run evidence post Phase 16 commits."
      - path: "frontend/playwright-report/index.html"
        issue: "Dated 2026-06-30 — predates Phase 16 entirely. Cannot serve as evidence that the light sweep passed."
    missing:
      - "Run npx playwright test e2e/a11y-routes.spec.ts --project=chromium-a11y against a live Next.js production build with data-theme=light and record the results. Both dark and light describe blocks must report 0 critical/serious violations."

  - truth: "Severity/status/SLA pills and glyphs are legible and distinct on light surfaces; muted/faint/disabled tokens pass AA (source-palette changes reconciled into the design system)"
    status: failed
    reason: "Two independent contrast failures remain after Phase 16, confirming code-review findings WR-01 and WR-02 against the actual codebase. (1) WR-01 CONFIRMED: --color-info is not overridden in the light block. Its dark value #60A5FA (blue-400, ~2.5:1 on #FAF7F2 cream) is consumed as small text (text-xs font-mono) in SourcePill on /dashboard/users — a STATIC_ROUTE swept by the light axe describe. (2) WR-02 CONFIRMED: --color-amber-on-soft (#92400E) is defined in globals.css and the skill but is consumed by nothing. status-pill.tsx in_progress/in progress entries (lines 40,44) and profile-pane.tsx ANALYST badge (line 62) still use text-amber = var(--color-amber) = #F59E0B, which is the dark accent value (~1.9:1 on cream surfaces). Both sites remain sub-AA. status-pill.test.tsx line 35 still asserts text-amber, confirming the test was updated for violet but not amber."
    artifacts:
      - path: "frontend/src/app/globals.css"
        issue: "--color-info not overridden in :root[data-theme=\"light\"] block; --color-amber-on-soft defined but dead (nothing consumes it)"
      - path: "frontend/src/components/users/source-pill.tsx"
        issue: "Uses text-info (line 21-24) which resolves to #60A5FA in light mode — text-xs on pale bg-info/10 fill over cream, fails 4.5:1 (est. ~2.5:1)"
      - path: "frontend/src/components/tickets/status-pill.tsx"
        issue: "in_progress and 'in progress' entries (lines 40,44) use text-amber = #F59E0B — not migrated to text-[var(--color-amber-on-soft)], sub-AA on bg-amber/10 over cream"
      - path: "frontend/src/components/settings/profile-pane.tsx"
        issue: "ANALYST badge (line 62) uses text-amber = #F59E0B on bg-amber-soft — not migrated to var(--color-amber-on-soft)"
    missing:
      - "Add --color-info: #2563EB to the :root[data-theme=\"light\"] block in globals.css (mirrors severity-info per the plan's own reasoning)"
      - "Migrate status-pill.tsx in_progress/'in progress' classes from text-amber to text-[var(--color-amber-on-soft)]"
      - "Migrate profile-pane.tsx ANALYST badge from text-amber to text-[var(--color-amber-on-soft)]"
      - "Update status-pill.test.tsx line 35 in_progress assertion from text-amber to text-[var(--color-amber-on-soft)]"
      - "Add --color-info to the skill's sunset.css light block and annotate foundation.md (mirrors severity-info reconciliation)"

human_verification:
  - test: "Per-route light-mode visual sweep (manual)"
    expected: "No dark-only visual artifacts (dark shadows, dark borders, dark hover states, dark disabled states) visible on any of the ~15 authed routes when data-theme=light is active"
    why_human: "Programmatic axe catches contrast but not pure visual correctness of border/shadow/hover rendering. Requires a browser with the light theme active."
  - test: "Light-theme axe sweep execution"
    expected: "npx playwright test e2e/a11y-routes.spec.ts --project=chromium-a11y runs against a production build, both dark and light describe blocks pass with 0 critical/serious violations (after WR-01 and WR-02 fixes above)"
    why_human: "Requires a running Next.js production server plus a backend — cannot be verified in a static code check. The spec is structurally correct; the result is unknown."
---

# Phase 16: Light-theme Visual Completion — Verification Report

**Phase Goal:** Every authenticated route is visually correct and WCAG 2.1 AA in light mode — not just architecturally themed.
**Verified:** 2026-07-15T18:30:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Per-route light-mode sweep shows no dark-only visual artifacts on any of the ~15 routes | ? UNCERTAIN | No programmatic check is conclusive; requires human visual verification. Code-level artifacts (shadows, borders, glow tokens) are overridden in the CSS. No playwright run exists post-Phase-16. |
| 2 | `e2e/a11y-routes.spec.ts` runs under `data-theme="light"` and reports 0 serious/critical axe violations on every route | ✗ FAILED | Spec structure: present and correct (3 describe blocks, light seed via addInitScript, defensive re-assert). Execution: zero evidence. playwright-report dated 2026-06-30 (15 days before Phase 16 commits). CI pipeline has no playwright job. SUMMARY self-check records only grep + vitest — no playwright run output. |
| 3 | Severity/status/SLA pills and glyphs are legible and distinct on light surfaces; muted/faint/disabled tokens pass AA | ✗ FAILED | Two confirmed gaps. WR-01: --color-info not overridden in light block; SourcePill uses text-info (text-xs) on /dashboard/users — #60A5FA on cream fails 4.5:1. WR-02: --color-amber-on-soft defined but dead; in_progress pill (status-pill.tsx:40,44) and ANALYST badge (profile-pane.tsx:62) still use text-amber = #F59E0B, sub-AA on pale amber fill over cream. |
| 4 | Zero First-Load-JS delta (CSS-only); the existing dark-mode gate stays green | ✓ VERIFIED | Changes are limited to CSS custom properties, one Tailwind class string migration per component, and a Playwright spec addition. Bundle script (check-bundle-all.mjs) exists. Dark describe block is byte-for-byte intact. No new JS added. |

**Score:** 2/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `frontend/e2e/a11y-routes.spec.ts` | Light-theme axe sweep describe block with addInitScript + defensive re-assert | ✓ WIRED | Present at lines 74-135. 3 describe blocks confirmed. beforeEach seeds getvul_theme=light. Defensive evaluate re-assert present. |
| `frontend/src/app/globals.css` | Single :root[data-theme="light"] block with ~20 overrides | ✓ VERIFIED | Single block confirmed (grep returns 1). All 5 severity, 3 semantic state, 2 shadow, 5 glow, 3 on-soft, text-faint present. --color-info NOT present (gap). |
| `frontend/src/components/tickets/status-pill.tsx` | Open pill via var(--color-violet-on-soft) | ✓ VERIFIED | Line 36: classes: 'border-violet/40 bg-violet-soft text-[var(--color-violet-on-soft)]'. Migrated correctly. In_progress lines 40,44 still use text-amber (gap). |
| `frontend/src/components/settings/profile-pane.tsx` | OWNER/ADMIN badge via var(--color-pink-on-soft)/var(--color-violet-on-soft) | ✓ PARTIAL | Lines 60-61: OWNER=text-[var(--color-pink-on-soft)], ADMIN=text-[var(--color-violet-on-soft)]. Line 62: ANALYST=text-amber (not migrated — gap). |
| `.claude/skills/sketch-findings-getvul/sources/themes/sunset.css` | Light-mode overrides section with all overridden tokens | ✓ VERIFIED | Light block present at line 145. Contains all expected tokens. --color-info not included in light block (consistent with the globals.css gap). |
| `.claude/skills/sketch-findings-getvul/references/foundation.md` | Token tables annotated with light values | ✓ VERIFIED | Light annotations confirmed at lines 25, 34-36, 45-48, 54-59, 128-139. |
| `.claude/skills/sketch-findings-getvul/references/visual-language.md` | Light-mode variants subsection under on-soft fills + severity | ✓ VERIFIED | Lines 17-29 (severity light table). Lines 112-120 (on-soft light variants). Amber-on-soft documented here but not consumed by any component. |
| `frontend/src/components/shell/user-chip.tsx` | Theme: Light radio enabled, no disabled attr, no In-progress badge | ✓ VERIFIED | Line 67: plain `<DropdownMenuRadioItem value="light">{'Theme: Light'}</DropdownMenuRadioItem>`. No disabled attr. No In-progress badge. No WR-03 comment. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| status-pill.tsx | globals.css --color-violet-on-soft | text-[var(--color-violet-on-soft)] | ✓ WIRED | Confirmed: line 36 uses the var() reference; light override in globals.css:52 resolves to #5B21B6 |
| profile-pane.tsx OWNER | globals.css --color-pink-on-soft | text-[var(--color-pink-on-soft)] | ✓ WIRED | Confirmed: line 60 |
| profile-pane.tsx ADMIN | globals.css --color-violet-on-soft | text-[var(--color-violet-on-soft)] | ✓ WIRED | Confirmed: line 61 |
| profile-pane.tsx ANALYST | globals.css --color-amber-on-soft | text-[var(--color-amber-on-soft)] | ✗ NOT_WIRED | Line 62 uses text-amber; globals.css:54 --color-amber-on-soft is never reached |
| status-pill.tsx in_progress | globals.css --color-amber-on-soft | text-[var(--color-amber-on-soft)] | ✗ NOT_WIRED | Lines 40,44 use text-amber; --color-amber-on-soft defined but dead |
| source-pill.tsx (google/azure/humaans) | globals.css --color-info | text-info | ✗ BROKEN | text-info resolves to var(--color-info) = #60A5FA in light mode; --color-info has no light override |
| a11y-routes.spec.ts light describe | globals.css light-mode token block | axe under data-theme=light | ? UNCONFIRMED | Structurally wired; no execution evidence post Phase 16 |

### Data-Flow Trace (Level 4)

Not applicable — this phase is CSS tokens, spec additions, and component class strings. No dynamic data rendering was changed.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Light axe sweep spec exists and has 3 describe blocks | `grep -c "test.describe" frontend/e2e/a11y-routes.spec.ts` | 3 | ✓ PASS |
| Light theme seed via addInitScript present | `grep -q "getvul_theme', 'light'" frontend/e2e/a11y-routes.spec.ts` | matched | ✓ PASS |
| Single light CSS block (no duplicate selector) | `grep -c ':root\[data-theme="light"\]' frontend/src/app/globals.css` | 1 | ✓ PASS |
| No dark JIT hex literals in production src/ | `grep -rn 'text-\[#[0-9A-Fa-f]{6}\]' src/` | comment-only reference in status-pill.tsx:33 | ✓ PASS |
| Theme: Light radio enabled | `grep -n "disabled" src/components/shell/user-chip.tsx` | no match | ✓ PASS |
| Light axe sweep executed and green | playwright test run evidence | No run after 2026-06-30; Phase 16 commits are 2026-07-15 | ✗ FAIL |
| --color-amber-on-soft consumed in light mode | `grep -rn "amber-on-soft" src/` (components only) | only in globals.css declaration | ✗ FAIL |
| --color-info overridden for light | `grep -n "color-info" src/app/globals.css` | no match | ✗ FAIL |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|---------|
| UX-D-03-01 | 16-01-PLAN.md | Every authenticated route renders visually correct in light mode — no dark-only borders, shadows, hover, or disabled artifacts | ? NEEDS HUMAN | CSS token overrides for shadows/glows/borders are present and correct. Visual correctness of rendered output requires human inspection; no axe sweep run confirmed. |
| UX-D-03-02 | 16-01-PLAN.md | All text + UI meets WCAG 2.1 AA contrast (4.5:1 text, 3:1 UI) in light mode on every route | ✗ BLOCKED | Axe sweep not proven run. Two confirmed text contrast failures: text-info on /dashboard/users (SourcePill), text-amber on in_progress pill and ANALYST badge. |
| UX-D-03-03 | 16-01-PLAN.md | Severity / status / SLA pills and severity glyphs are legible and mutually distinct on light surfaces | ✗ BLOCKED | Severity pills (critical/high/medium/low/info) all overridden and correctly wired. Status pills: Open pill correct; In-progress pill uses text-amber (sub-AA on cream). |
| UX-D-03-04 | 16-01-PLAN.md, 16-02-PLAN.md | text-muted / text-faint / disabled-state tokens pass AA; source-palette changes reconciled into design system | ✓ PARTIAL | text-faint correctly overridden to #6B6480. Skill reconciliation complete for all documented tokens. amber-on-soft token defined in both app and skill but not wired to any component. |
| UX-D-03-05 | 16-01-PLAN.md | e2e a11y sweep runs under data-theme="light" as well as dark, and is green | ✗ BLOCKED | Spec structure satisfies "runs under data-theme=light." Greenness is unproven: no playwright execution evidence post Phase 16 commits. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `frontend/src/components/tickets/status-pill.tsx` | 40, 44 | `text-amber` (base accent, not on-soft) on amber-soft fill | Blocker | in_progress pill: #F59E0B on rgba(245,158,11,0.10) over cream ≈ 1.9:1 — fails WCAG AA by ~2.6x; blocks SC#2 and SC#3 |
| `frontend/src/components/settings/profile-pane.tsx` | 62 | `text-amber` on bg-amber-soft | Blocker | ANALYST badge: same contrast failure as in_progress pill; --color-amber-on-soft defined but dead |
| `frontend/src/app/globals.css` | light block | `--color-info` absent from light override set | Blocker | SourcePill on /dashboard/users uses text-info (text-xs); #60A5FA fails ~2.5:1 on cream — any info-variant toast title would also fail |
| `frontend/src/app/globals.css` | 54 | `--color-amber-on-soft: #92400E` defined but zero consumers | Warning | Dead token; its purpose is documented in visual-language.md and the skill, but nothing renders it |

### Human Verification Required

#### 1. Light-theme axe sweep execution

**Test:** Start a Next.js production build (`npm run build && npm start` in `frontend/`), ensure backend is running with seed data, then run `npx playwright test e2e/a11y-routes.spec.ts --project=chromium-a11y` from `frontend/`. Both the dark describe block ("WCAG 2.1 AA axe sweep — all routes") and the light describe block ("WCAG 2.1 AA axe sweep — light theme") must complete with 0 critical/serious violations on every route.

**Expected:** All tests green. If violations are reported, the console.error output names the failing rule and route.

**Why human:** Requires a running production build + backend server. Cannot be verified statically. The spec structure is correct; only the execution result is unknown.

**Note:** Run this AFTER fixing WR-01 (--color-info) and WR-02 (amber migrations). Running before those fixes will produce known failures in SourcePill and the in_progress/ANALYST elements.

#### 2. Visual correctness sweep (no dark-only artifacts)

**Test:** With `data-theme="light"` active in a real browser, navigate through all ~15 authed routes and verify no dark-colored borders, dark shadows, dark hover states, or dark disabled-state elements are visible.

**Expected:** All routes render with the warm-cream (#FAF7F2) background, lighter card surfaces, reduced box-shadow depth, and softened glows. No element looks "dark on dark."

**Why human:** Axe catches contrast violations but not pure visual correctness of shadow rendering, border weight, or hover-state color on light surfaces. CSS overrides are in place for all shadow/glow/border tokens; visual confirmation that no other component hardcodes dark values requires a browser.

### Gaps Summary

Phase 16 made genuine and substantive progress: the ~20 CSS token overrides are present and correctly structured, the two violet/pink literal migrations are correct, the design-system skill reconciliation is thorough, and the Theme: Light toggle is enabled. The phase's foundational architecture (single CSS override block, CSS variable cascade, Playwright addInitScript pattern) is sound.

Two categories of gap remain that directly block the phase goal claim ("WCAG 2.1 AA in light mode"):

**Gap 1 — Axe sweep unexecuted (SC#2):** The light-theme describe block was scaffolded but never run against a live server. The existing playwright-report predates Phase 16 by 15 days. Without an execution result, "0 critical/serious violations on every route" is a claim, not a verified state. This is a process gap; it may resolve cleanly once the token gaps below are fixed.

**Gap 2 — Amber and info token failures (SC#2, SC#3):**
- `--color-info` is not overridden in the light block. SourcePill on `/dashboard/users` renders `text-info` (text-xs) at an estimated 2.5:1 on cream — a critical failure for SC#2.
- `--color-amber-on-soft` is defined in globals.css and the design system skill but is consumed by nothing. The two amber call sites (`status-pill.tsx` in_progress entries; `profile-pane.tsx` ANALYST badge) still use `text-amber` = `#F59E0B` directly, which fails AA on the pale amber fill over cream. The design system even explicitly documents that "Always use `text-[var(--color-*-on-soft)]`" — these two sites violate the rule the phase itself codified.

The fixes are mechanical and low-risk: add one CSS line to globals.css, migrate two component class strings (mirroring the already-done violet/pink migration), update one test assertion, and mirror the info override into the skill. After those fixes, the axe sweep must be executed to confirm SC#2.

---

_Verified: 2026-07-15T18:30:00Z_
_Verifier: Claude (gsd-verifier)_
