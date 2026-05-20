---
title: GetVul Redesign Direction — v2 (post-rollback)
date: 2026-05-12
type: note
context: ideation
supersedes: v2-01 Tactical Carbon direction (rolled back 2026-05-12)
---

# GetVul Redesign Direction — v2

## Background

The first v2.0 milestone (10 phases of foundation-then-screens) was rolled back on 2026-05-12 — 32 commits discarded, HEAD reset to `6515a08`. Recovery branch: `v2-01-rollback-recovery`.

**Why it failed:**
1. **Aesthetic miss.** "Tactical Carbon" (industrial / utilitarian / console-flavored, mono identifiers, sharp corners, borders over shadows, two-tone amber-on-near-black) sounded fine in CONTEXT.md and felt wrong in the browser. The phrase didn't predict the visual.
2. **Pace miss.** v2-01 was scoped foundation-only per D-32 (tokens, theme, fonts, motion constants, a11y CI, manifesto) — explicitly no primitives, no screens. By design the user wouldn't see a "new" app until v2-03 (login redesign) landed, 2+ phases later. In practice this felt like *nothing was happening* + v1 screens lost their light-theme `!important` shims and looked degraded in the transitional state.

## Locked decisions (this conversation)

### Aesthetic reference
- **D-01:** Take design cues from **wiz.io** — polished modern SaaS, rounded corners, depth and elevation, gradient-rich accents, dark-with-color. Premium feel.
- **D-02:** **Less complex than Wiz** on information density. Wiz packs a lot of graph/connector visuals; GetVul should keep the polished surface but show less per screen, fewer simultaneous data viz components, simpler interaction model.

### Color palette — "Sunset / Dusk"
- **D-03:** Warm-gradient accents on cool dark base. Differentiates from Wiz/Linear/Stripe (all of which sit in the blue→purple→cyan range).
- **D-04:** Starting palette values (subject to mockup-driven tuning):
  - Background: `#0E0B1A` (deep plum)
  - Surface (raised card): `#1A1430`
  - Border (subtle): `#2A2150`
  - Text primary: `#F0E8FF` (warm white)
  - Accent 1: `#EC4899` (hot pink)
  - Accent 2: `#F59E0B` (amber)
  - Accent 3: `#A78BFA` (lavender)
  - Gradient: pink → violet → amber (for hero CTAs, severity ribbons, key CTAs)

### Process commitments
- **D-05:** **Sketch first, build second.** Throwaway HTML mockups of key screens before any production code, any token system, any primitives. Approve the visual in pixels before committing to anything maintainable.
- **D-06:** **Vertical-slice phases.** When a real milestone is built, each phase ships one *complete* screen end-to-end (tokens + primitives + page wiring + a11y + tests, all together for that screen). No foundation-only phase that ships invisible plumbing. First screen lands → user sees the new app immediately.
- **D-07:** First vertical slice candidate: `/login` — smallest surface, fewest dependencies, most-visited entrypoint. Establishes the visual language by shipping it, not by writing about it.

## What's preserved from v1.0 work

- `REDESIGN_PLAN.md` at repo root — the v1 audit catalogued every pain point (light theme `!important` hacks, oversized pages, missing primitives, no empty/loading/error states, tables-on-mobile, color-only conveyance, sub-44px touch targets, unused recharts). Still the canonical problem statement — the *what* of the redesign, not the *how*.
- v1.0 Production Readiness milestone — 1 of 8 phases complete (Multi-Replica State). Phases 2–8 unaffected by this redesign rethink and can ship in parallel.

## Open questions

- Are the v0.1 marketing/landing pages in scope, or product-only?
- Does "less complex than Wiz" mean we skip the graph/connector metaphor entirely, or include a simplified version?
- Should the redesigned app support a light theme at all, or commit to dark-only? (Sunset palette is strongly dark-leaning; a light variant would need its own design pass.)
- Mobile: does GetVul have real mobile users, or is it desktop-first and mobile is a politeness gesture? Affects breakpoint priority.

These resolve during mockup iteration — no need to answer now.
