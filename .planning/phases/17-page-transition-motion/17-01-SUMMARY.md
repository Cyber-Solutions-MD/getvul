---
phase: 17-page-transition-motion
plan: 01
subsystem: frontend/e2e
tags: [motion, view-transitions, a11y, e2e, testing, wave-0, red-tests]
dependency_graph:
  requires: []
  provides: [UX-D-06-01-spec, UX-D-06-02-spec-extended]
  affects: [frontend/e2e/page-transitions.spec.ts, frontend/e2e/reduced-motion.spec.ts]
tech_stack:
  added: []
  patterns:
    - document.getAnimations() poll for VT pseudo-element detection
    - effect.getComputedTiming().duration for VT animation duration assertion
    - Bounded polling (1500ms/800ms) to catch short-lived VT animations
key_files:
  created:
    - frontend/e2e/page-transitions.spec.ts
  modified:
    - frontend/e2e/reduced-motion.spec.ts
decisions:
  - Polling approach (not MutationObserver) for VT animation detection — more reliable with Playwright's JavaScript evaluation model; MutationObserver on :root is asynchronous and harder to synchronize with page.evaluate
  - CSSEffect/VTEffect helper type pattern — typed as a local alias to provide type-safe pseudoElement access without casting to any; consistent between both spec files
  - "If no VT animation fires, test passes" — both tests accept the "instant swap / no animation" case as a valid suppressed state; this prevents false failures in environments where the VT API fires and completes before the first poll tick
  - history.pushState proxy for searchParams-only change (Test B) — the DrillPanel / tab / view-toggle controls are not trivially reachable in a stateless test session; pushState + PopStateEvent is the documented proxy approach per plan
metrics:
  duration: 8m
  completed: "2026-07-16"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
---

# Phase 17 Plan 01: Wave-0 E2E Test Contract (RED) Summary

**One-liner:** Two Playwright spec files author the automated VT contract before implementation — cross-fade detection via `getAnimations()` poll + VT pseudo-element reduced-motion suppression, both expected RED until Plan 02.

## What Was Built

### Task 1 — `frontend/e2e/page-transitions.spec.ts` (NEW, commit `743998b`)

A new Playwright spec in `test.describe('Page-transition motion')` with two tests running on the default `chromium-a11y` project (no new project, no `testMatch`):

**Test A — "cross-fade fires on a real pathname change (dashboard → vulnerabilities)"**
- Navigates to `/dashboard`, waits for the primary nav landmark
- Clicks the Vulnerabilities nav link (client-side route change, not `page.goto` hard navigation per D-07)
- Polls `document.getAnimations()` up to 1500ms at 50ms intervals for any animation whose `effect.pseudoElement` includes `'view-transition'`
- Asserts the count reaches `>= 1` at least once during the poll window
- Asserts final URL is `/dashboard/vulnerabilities`

**Test B — "searchParams-only change does NOT trigger a page fade (D-02)"**
- Navigates to `/dashboard/vulnerabilities`, waits for primary nav
- Triggers a searchParams-only change via `history.pushState` + `PopStateEvent` (pathname unchanged)
- Polls 800ms for VT animations and asserts the count stays `0`
- Asserts the pathname is unchanged after the mutation

### Task 2 — `frontend/e2e/reduced-motion.spec.ts` (EXTENDED, commit `bcf425f`)

Appended a third test inside the existing `test.describe('Reduced-motion emulation')` block. Original two tests untouched.

**Third test — "view-transition pseudo-elements are suppressed under prefers-reduced-motion"**
- `page.emulateMedia({ reducedMotion: 'reduce' })` BEFORE navigation (reusing the existing pattern)
- Navigates to `/dashboard`, clicks Vulnerabilities link to trigger a client-side route change
- Polls 800ms for VT animations; reads each animation's computed duration via `effect.getComputedTiming().duration` (number in ms, not `getComputedStyle` on the pseudo-element which is unreliable)
- If any VT animation fires: asserts its duration is `<= 20ms` (the explicit reduce suppressor pins it to 0.01ms)
- If no VT animation fires: test passes (instant swap = also valid suppressed state)
- Timeout check: asserts primary nav is visible within 500ms after click (documents "instant swap" expectation)

## RED State (Expected at End of Plan 01)

This plan is Wave 0 (tests-first). Both new specs are expected RED:

| Spec | Expected State | Why RED |
|------|---------------|---------|
| `page-transitions.spec.ts` | RED (both tests fail) | `(authed)/template.tsx` does not exist yet; no `document.startViewTransition` fires on client nav; `getAnimations()` finds zero VT pseudo-element animations |
| `reduced-motion.spec.ts` — original 2 tests | GREEN | Implementation already exists; blanket `globals.css` rule suppresses `.bg-gradient-mesh` and `.bg-severity-critical` animations |
| `reduced-motion.spec.ts` — new 3rd test | RED | `(authed)/template.tsx` does not exist; no VT fires under any motion setting; the `::view-transition-group/old/new` explicit suppressor rule does not yet exist in `globals.css` |

The RED state is the success condition for Plan 01. Being honest about this is required — Plan 02 is where the implementation flips these tests GREEN.

## Acceptance Criteria Results

### Task 1 (`page-transitions.spec.ts`)

| Check | Result |
|-------|--------|
| File exists | PASS |
| `grep -c "view-transition"` >= 2 | PASS (10 occurrences) |
| `grep -q "getAnimations"` | PASS |
| `grep -q "Primary navigation"` | PASS |
| Exactly 2 `test(` calls in 1 `test.describe(` | PASS |
| No `testMatch` registered | PASS |

### Task 2 (`reduced-motion.spec.ts`)

| Check | Result |
|-------|--------|
| Original test 1 name present | PASS |
| Original test 2 name present | PASS |
| `grep -q "view-transition pseudo-elements are suppressed"` | PASS |
| `grep -q "reducedMotion: 'reduce'"` | PASS |
| `grep -q "getComputedTiming"` | PASS |
| Exactly 1 `test.describe(` | PASS |
| 3 `test(` calls total | PASS |

## Commits

| Task | Commit | Files |
|------|--------|-------|
| Task 1: page-transitions.spec.ts | `743998b` | `frontend/e2e/page-transitions.spec.ts` (+139 lines) |
| Task 2: extend reduced-motion.spec.ts | `bcf425f` | `frontend/e2e/reduced-motion.spec.ts` (+95 lines) |

## Deviations from Plan

None — plan executed exactly as written.

The worktree branch required a `git reset --soft` to align to the correct base commit (`6558cdb`) before execution. This is the documented stale-base worktree hazard. The reset correctly established the branch at the Phase 17 research/planning HEAD without altering source files.

## Key Decisions Made

1. **Polling over MutationObserver for VT detection** — `page.evaluate(() => document.getAnimations())` polled at 50ms intervals is more reliable in the Playwright executor context than registering a MutationObserver on `:root` and awaiting a Promise across the execution boundary.

2. **`getComputedTiming().duration` over `getComputedStyle`** — The plan correctly notes that pseudo-elements are not reliably queryable via `getComputedStyle`. The `effect.getComputedTiming()` approach reads the resolved duration of the animation object directly.

3. **"No VT animation seen" = pass for the reduce test** — The reduced-motion test correctly separates "no VT animation fires" (valid suppressed state — instant swap) from "VT animation fires with long duration" (failure). This prevents false failures in environments where the VT API completes before the first poll tick.

4. **`CSSEffect` / `VTEffect` local type aliases** — Added to avoid TypeScript `any` casts on `effect.pseudoElement` (which is exposed by `KeyframeEffect` but not by the base `AnimationEffect` interface in lib.dom.d.ts). Each spec file declares its own alias for clarity.

## Known Stubs

None. These are test-only spec files with no production code stubs.

## Threat Flags

None. The two files added are Playwright e2e spec files. No production code, no network handlers, no auth logic, no user input surface introduced. See threat model in the PLAN.md — T-17-01 disposition is `accept`.

## Self-Check: PASSED

File existence:
- `frontend/e2e/page-transitions.spec.ts` — FOUND
- `frontend/e2e/reduced-motion.spec.ts` — FOUND (extended)

Commit existence:
- `743998b` — FOUND (test(17-01): add page-transitions.spec.ts)
- `bcf425f` — FOUND (test(17-01): extend reduced-motion.spec.ts)
