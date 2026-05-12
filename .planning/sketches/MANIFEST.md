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
| 001 | login-sunset | Does the sunset palette + Wiz-style polish feel premium in pixels, and which "fancy level" is right? | **A · Split-screen** | login, palette, layout, polish-level |
| 002 | dashboard-sunset | Which information hierarchy answers "what should I work on right now?" — and does the palette scale to a data-heavy screen? | _pending_ | dashboard, layout, hierarchy, navigation-shell |

## Validated decisions (from sketch 001 → A)

- **D-08:** Sunset palette works. Pink → violet → amber on deep plum reads as premium and warm without crossing into crypto/dating-app territory.
- **D-09:** Restrained polish wins. "Fancy" should be contained to one zone of the screen (e.g., a visual side panel, a hero block), not surrounding the form/data. Glassmorphism + iridescent strokes were too loud.
- **D-10:** Split-screen layout language is canonical for hero/landing surfaces (login, signup, marketing). Form lives in a clean dark panel; visual + copy + UI peek lives on the gradient side.
- **D-11:** Animated gradient mesh as the "loud" visual element. Subtle drift, not aggressive motion. Confined to dedicated zones.
- **D-12:** Gradient CTA button (pink→violet→amber) is the universal primary-action treatment — used across all variants and survived to the winner.
- **D-13:** Real product preview (the floating glassy vuln-list peek in the visual zone) is more compelling than abstract gradients alone. The "what is this product" is shown, not just stated.

## Process commitments

- **Sketch first, build second.** No production code, no token system, no Tailwind config until at least three screens are visually approved (per D-05).
- **Variants on aesthetic dimension only.** When comparing variants, only one design axis differs at a time (in 001: polish level). Form content, palette, and SSO providers stay constant so the comparison is fair.
- **Cherry-pick allowed.** Final synthesis can mix elements across variants (e.g. "A's layout + C's orb"). Synthesis becomes a new variant tab, not a separate sketch.
