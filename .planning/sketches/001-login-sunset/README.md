---
sketch: 001
name: login-sunset
question: "Does the sunset palette (pink → violet → amber on deep plum) plus Wiz-style polish actually feel premium in pixels — and which 'fancy level' is right for GetVul?"
winner: null
tags: [login, palette, layout, polish-level]
---

# Sketch 001: Login — Sunset Palette

## Design Question

Three things at once:

1. **Does the sunset palette work?** Pink + violet + amber on deep plum sounded good in the explore. Does it actually feel premium, or does it look like a crypto site / dating app / kids' product?
2. **Which polish level feels right for GetVul?** Three escalating treatments — tame to showy. The right one balances "this looks expensive" with "this is a security tool, take it seriously."
3. **Does the Wiz-inspired layout language translate?** Split-screen with marketing copy vs. centered card. Wiz uses both depending on the entry point.

## How to View

```
open .planning/sketches/001-login-sunset/index.html
```

Tab through the three variants at the top. Use the toolbar (bottom-right, hover to expand) to test mobile viewport.

## Variants

- **A — Split-screen** — Big animated gradient mesh on the left with marketing copy ("See your security posture without opening another tool.") + a peek-preview of a vuln list. Clean form panel on the right. Most "Wiz-like." Restrained polish — fancy where it earns it (gradient text accent, brand mark glow), clean where it doesn't.

- **B — Centered glass card** — Single 440px card on a full-bleed gradient mesh (drifting). Glassmorphic blur + saturation. Thin iridescent stroke around the card. SaaS-premium feel without being loud.

- **C — Floating orb** — Solid card (less glass, more substance) on a near-black base, with a huge animated gradient orb behind it that rotates slowly. Conic-gradient stroke around the card that rotates independently. CTA has a "shine" sweep on hover. Highest polish, biggest "is this a security tool?" risk.

All three share: same sunset palette, same form fields (real labels from v1 `/login`), same SSO providers (Google + Microsoft per v1), same severity glyph + gradient CTA button. The difference is **how loud the visual treatment is around the form**.

## What to Look For

When comparing variants, watch for:

- **Does it feel like a real product or a Dribbble shot?** Premium SaaS is restrained-fancy. If it screams "designer flexed here," it's wrong.
- **Does the gradient CTA dominate or compete?** The pink→violet→amber button is the same in all three. In A it's the only "fancy" thing on screen; in C it competes with the orb.
- **Mobile collapse.** Toggle the 375 viewport in the toolbar. Does A collapse gracefully (visual goes top, form goes bottom)? Does C still feel fancy when the orb is squeezed?
- **Error state.** Click "Toggle error" on each variant. Red error bars on warm-palette backgrounds can look weird — check the contrast.
- **Register mode.** Click "Show register" — does adding a Full Name field break the rhythm of the form?
- **Animation.** The mesh and orb are subtly animated. Does it feel alive or distracting?

## Open variables (for next sketch round if needed)

- Should the form be left or right in variant A? (Right is convention; left has eye-tracking benefits for left-to-right readers.)
- Are SSO buttons primary or secondary visually? Currently they're styled as secondary. Per the explore, SSO should probably be the primary hierarchy.
- Severity glyph color in the var-A preview — currently it's a colored dot. Could be the glyph (■ ▲ ◆ ○ □) instead.
- Tagline copy: "See your security posture without opening another tool." Placeholder — real copy comes later.
