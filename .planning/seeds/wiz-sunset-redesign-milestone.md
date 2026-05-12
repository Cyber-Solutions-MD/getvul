---
title: v2.0 UI/UX Redesign — Wiz-inspired sunset milestone
planted_date: 2026-05-12
trigger_condition: mockups approved for >=3 screens (login + dashboard + one data-heavy screen)
type: seed
status: dormant
links:
  - .planning/notes/redesign-direction-v2.md
  - REDESIGN_PLAN.md
recovery_ref: v2-01-rollback-recovery (branch, at commit c09194c)
---

# Seed: v2.0 UI/UX Redesign Milestone (Wiz-inspired, sunset palette)

## Trigger

Surface this seed when **HTML mockups for at least 3 screens have been visually approved** by the maintainer. Don't start planning the milestone before that — the v1 attempt failed because it committed to a shape (10 phases, foundation-first) before validating the aesthetic.

## Proposed shape (when triggered)

**Anti-pattern to avoid:** the 10-phase foundation-first decomposition from the rolled-back v2.0 attempt.

**Proposed instead:** **vertical-slice phases.** Each phase ships one complete screen end-to-end — tokens for the colors that screen uses, primitives for the components that screen needs, the page itself wired up to real data, a11y verified, tests written. All in one phase. When the phase lands, the user can open the app and see that screen redesigned. No invisible "foundation phase" that ships only CSS variables and gets rejected for "looking worse."

**Suggested phase order (1 phase = 1 screen unless noted):**
1. `/login` — smallest surface, fewest deps, establishes the visual language by shipping it. Token set extracted from this screen's needs only.
2. `/dashboard` — sets the data-density bar. Cards, stat numerals, one trend chart, one activity feed. Re-uses login tokens; adds chart-specific tokens.
3. `/dashboard/vulnerabilities` — first data-heavy table screen. Establishes table + filter primitives.
4. Sweep remaining screens in priority order (assets, cspm, tickets, connectors, users, settings). Each can lean on primitives from phases 1–3; some may merge.
5. Mobile + a11y + perf pass — closing quality gate.

Estimate: 5–7 phases instead of 10. Significantly faster time-to-first-visible-result (1 phase vs ~3 in the old plan).

## Inputs ready at trigger time

- `.planning/notes/redesign-direction-v2.md` — locked aesthetic + palette decisions D-01..D-07
- Approved HTML mockups (location TBD — likely `dev/mockups/` or similar throwaway path)
- `REDESIGN_PLAN.md` — v1 pain-point audit, still authoritative on the *what*
- v1.0 Production Readiness milestone state — independent, may still be in flight

## Inputs to gather at trigger time

- Whether mobile and light-theme are in scope (see open questions in the note)
- Whether v1.0 Phase 2–8 are finished or running in parallel
- Bundle / performance budget — should be set explicitly once mockups reveal the actual asset weight

## Why this is a seed, not a phase yet

The aesthetic call ("Wiz-inspired + sunset") has not been visually validated. Sketching mockups is a `/gsd-sketch` operation, not a `/gsd-new-milestone` operation. If the mockups expose that the sunset palette doesn't actually feel premium in pixels, this seed gets revised — better to revise a seed than to roll back another milestone.

## How to wake this seed

After mockup approval, run:
```
/gsd-new-milestone v2.0 UI/UX Redesign
```
and reference `.planning/notes/redesign-direction-v2.md` + the approved mockups as input.
