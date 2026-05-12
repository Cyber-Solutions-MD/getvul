# Sketch Manifest

## Design Direction

GetVul v2.0 redesign — **Wiz-inspired premium SaaS** in a **sunset / dusk palette** (pink → violet → amber accents on deep plum / near-black base). Less information density than Wiz proper. Warm-gradient where Wiz/Linear/Stripe are cool, to differentiate without leaving the polished-SaaS family.

Origin: [.planning/notes/redesign-direction-v2.md](../notes/redesign-direction-v2.md). Decisions D-01..D-07 locked there.

**Anti-direction (rejected):** Tactical Carbon / industrial / utilitarian / mono-identifier / sharp-corners — the rolled-back v2-01 direction. Sounded fine in writing, felt wrong in pixels.

## Reference Points

- **wiz.io** — overall layout language, polish level, dark-with-color premium SaaS feel
- **Linear, Vercel, Stripe** — for what *not* to be (cool blue/purple range; we go warm)
- **Arc browser, new-Linear** — adjacent for the glassmorphism + iridescent stroke idea

## Theme

`.planning/sketches/themes/sunset.css` — single source for color, type, spacing, motion. All sketches link to it.

## Sketches

| # | Name | Design Question | Winner | Tags |
|---|------|----------------|--------|------|
| 001 | login-sunset | Does the sunset palette + Wiz-style polish feel premium in pixels, and which "fancy level" is right? | _pending_ | login, palette, layout, polish-level |

## Process commitments

- **Sketch first, build second.** No production code, no token system, no Tailwind config until at least three screens are visually approved (per D-05).
- **Variants on aesthetic dimension only.** When comparing variants, only one design axis differs at a time (in 001: polish level). Form content, palette, and SSO providers stay constant so the comparison is fair.
- **Cherry-pick allowed.** Final synthesis can mix elements across variants (e.g. "A's layout + C's orb"). Synthesis becomes a new variant tab, not a separate sketch.
