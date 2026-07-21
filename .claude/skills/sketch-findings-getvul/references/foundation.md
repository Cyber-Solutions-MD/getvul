# Foundation — Tokens, Typography, Motion

The **sunset / dusk palette** + restrained polish — Wiz-inspired premium SaaS aesthetic but warmer than the blue/purple/cyan default that Wiz/Linear/Stripe share.

## Color Tokens

All values consumed via CSS variables. See `sources/themes/sunset.css` for the full file.

```css
/* Surfaces */
--color-bg:            #0E0B1A;  /* deep plum — page base */
--color-bg-darker:     #08060F;  /* near-black for special variants */
--color-surface:       #1A1430;  /* raised card */
--color-surface-2:     #241B40;  /* elevated above card */
--color-surface-glass: rgba(36, 27, 64, 0.45);  /* glass card (deferred) */

/* Borders */
--color-border:        #2A2150;
--color-border-subtle: #1F1840;
--color-border-strong: #3A2D70;

/* Text */
--color-text:          #F0E8FF;  /* warm white */
--color-text-muted:    #B8AECE;
--color-text-faint:    #8B84A8;  /* AA-lifted; was #6B6488 (failed 4.5:1 on dark) — light: #6B6480 (~4.8:1 on #FAF7F2 cream) */
--color-text-inverse:  #0E0B1A;

/* Sunset accents */
--color-pink:          #EC4899;  /* hot pink */
--color-violet:        #A78BFA;  /* lavender */
--color-amber:         #F59E0B;  /* amber */
/* + matching -soft variants at 18% alpha */
/* + matching -on-soft text shades (AA-safe text on a -soft fill):
   pink-on-soft #F472B6, violet-on-soft #C4B5FD, amber-on-soft #F59E0B. (dark theme)
   Light-mode on-soft: pink-on-soft #9D174D, violet-on-soft #5B21B6, amber-on-soft #92400E.
   severity-high-on-soft #9A3412 (light) / #FB923C (dark).
   severity-critical-on-soft #991B1B (light) / #F87171 (dark).
   See visual-language.md "Text on -soft fills". */

/* The signature gradient */
--gradient-sunset:     linear-gradient(135deg, #EC4899 0%, #A78BFA 50%, #F59E0B 100%);
--gradient-mesh:       radial-gradient(at 20% 20%, rgba(236, 72, 153, 0.4) 0%, transparent 50%),
                       radial-gradient(at 80% 30%, rgba(167, 139, 250, 0.35) 0%, transparent 55%),
                       radial-gradient(at 50% 80%, rgba(245, 158, 11, 0.3) 0%, transparent 55%);

/* Semantic states */
--color-danger:    #F87171;  /* light: #DC2626 (red-600, matches severity-critical) */
--color-success:   #4ADE80;  /* light: #15803D (green-700, ~5.8:1 on cream) */
--color-warning:   #FBBF24;  /* light: #B45309 (amber-700, matches severity-medium) */
--color-info:      #60A5FA;  /* light: #2563EB (blue-600, ~5.1:1 on cream — consumed by SourcePill text-info) */
```

### Severity colors (locked — used in every list/badge/glyph)

```css
--color-severity-critical: #F87171;  /* red    — light: #DC2626 (red-600,    ~5.5:1 on #FAF7F2) */
--color-severity-high:     #FB923C;  /* orange — light: #EA580C (orange-600, ~4.7:1 on #FAF7F2) */
--color-severity-medium:   #FBBF24;  /* yellow — light: #B45309 (amber-700, not amber-600 — yellow family needs deeper for 4.5:1) */
--color-severity-low:      #A78BFA;  /* lavender— light: #7C3AED (violet-600, ~6.0:1 on #FAF7F2) */
--color-severity-info:     #60A5FA;  /* blue   — light: #2563EB (blue-600,   ~5.1:1 on #FAF7F2) */
```

**Light-mode note:** All 5 severity tokens are overridden under `data-theme="light"` to darker same-hue variants that clear WCAG 2.1 AA (4.5:1) on the warm-cream `#FAF7F2` background. The three-axis encoding (color + glyph + text) keeps severity levels distinct even where hue shifts for contrast. Values axe-confirmed in 16-01-SUMMARY.md.

**severity-high-on-soft (Phase 20, UX-D-03-02/03):** severity-high has an `-on-soft` text variant for light soft/tinted fills — the bare light-mode `#EA580C` measures only 3.19:1 on the `#F7F2EA` soft surface (fails 4.5:1). `--color-severity-high-on-soft` (`#9A3412`, orange-800) clears 6.56:1 on `#F7F2EA`. See visual-language.md "Text on -soft fills".

**severity-critical-on-soft (Phase 20, UX-D-03-05):** severity-critical also has an `-on-soft` text variant for light soft/tinted fills — the bare light-mode `#DC2626` measures only 4.33:1 on the severity-critical `/10` tint (`#F7F2EA`-based), failing 4.5:1. `--color-severity-critical-on-soft` (`#991B1B`, red-800) clears ~7.45:1 on that tint. Dark value is a no-op (`#F87171`, = `--color-severity-critical` dark). See visual-language.md "Text on -soft fills".

## Typography

Two faces, used **strictly by purpose** — never mix:

```css
--font-sans:    'Inter', -apple-system, system-ui, sans-serif;
--font-mono:    'JetBrains Mono', 'Fira Code', monospace;
```

| Use | Font |
|---|---|
| Prose, labels, headings, body text | Inter |
| CVE IDs, hostnames, scores, durations, request IDs, counts, dates in mono context | JetBrains Mono |
| **Anything you'd ever copy-paste into a terminal** | JetBrains Mono |

**Type scale (1.25 modular):**
```css
--text-xs:    0.75rem;   /* labels, captions */
--text-sm:    0.875rem;  /* body, form labels */
--text-base:  1rem;      /* body large */
--text-lg:    1.125rem;  /* h6, subhead */
--text-xl:    1.25rem;   /* h5 */
--text-2xl:   1.5rem;    /* h3 (card titles, modal headers) */
--text-3xl:   2rem;      /* h2 (page titles) */
--text-4xl:   2.5rem;    /* h1 (rare — stat hero numbers) */
--text-5xl:   3.5rem;    /* hero display (login tagline only) */

--tracking-tight:   -0.02em;
--tracking-tighter: -0.04em;
--leading-tight:    1.1;
--leading-snug:     1.3;
--leading-base:     1.5;
```

Tabular numerals via `font-variant-numeric: tabular-nums` on `.num` and `.cell-score`.

## Spacing

4px base, multiples through 96. Use the `--space-N` variables for consistent rhythm — never hand-pick px values for padding/gap.

```css
--space-1: 4px;   --space-2: 8px;   --space-3: 12px;
--space-4: 16px;  --space-5: 20px;  --space-6: 24px;
--space-8: 32px;  --space-10: 40px; --space-12: 48px;
--space-16: 64px; --space-20: 80px; --space-24: 96px;
```

## Shapes (Radii)

Rounded but not exaggerated. Cards 14px, buttons/inputs 10px.

```css
--radius-sm:    6px;
--radius-md:    10px;  /* buttons, inputs, small cards */
--radius-lg:    14px;  /* cards (default) */
--radius-xl:    20px;  /* hero cards */
--radius-2xl:   28px;  /* large prominent cards (login glass card) */
--radius-full:  9999px;
```

## Shadows & Glow

Borders > shadows for normal chrome. Glow reserved for sunset-gradient elements (CTA, brand mark, active nav strip).

```css
--shadow-card:        0 8px 24px rgba(0, 0, 0, 0.4);    /* light: 0 2px 8px rgba(0, 0, 0, 0.08) */
--shadow-elevated:    0 20px 60px rgba(0, 0, 0, 0.5);   /* light: 0 8px 24px rgba(0, 0, 0, 0.12) */
--glow-pink:          0 0 32px rgba(236, 72, 153, 0.45); /* light: 0 0 16px rgba(236, 72, 153, 0.20) */
--glow-violet:        0 0 32px rgba(167, 139, 250, 0.45); /* light: 0 0 16px rgba(167, 139, 250, 0.20) */
--glow-amber:         0 0 32px rgba(245, 158, 11, 0.4);  /* light: 0 0 16px rgba(245, 158, 11, 0.15) */
--glow-cta:           0 8px 32px rgba(236, 72, 153, 0.35),
                      0 0 0 1px rgba(255, 255, 255, 0.05) inset;
                      /* light: 0 4px 16px rgba(236, 72, 153, 0.25), 0 0 0 1px rgba(0, 0, 0, 0.04) inset */
--glow-card-inner:    0 0 0 1px rgba(255, 255, 255, 0.04) inset; /* light: 0 0 0 1px rgba(0, 0, 0, 0.04) inset */
```

**Light-mode note:** Under `data-theme="light"`, all shadow and glow tokens are reduced in depth/opacity to suit the warm-cream `#FAF7F2` surface. The shadow-card / shadow-elevated use lighter rgba values; all glows halve their blur radius and reduce opacity. Values axe-confirmed in 16-01-SUMMARY.md.

## Motion

Four cubic-beziers (Material-3-derived), four durations. Subtle by default — micro-animations only.

```css
--ease-standard:   cubic-bezier(0.2, 0, 0, 1);   /* most things */
--ease-decelerate: cubic-bezier(0, 0, 0, 1);      /* enter */
--ease-accelerate: cubic-bezier(0.3, 0, 1, 1);    /* exit */
--ease-emphasis:   cubic-bezier(0.05, 0.7, 0.1, 1); /* hero moments */

--motion-fast:  120ms;  /* hover, focus */
--motion-base:  220ms;  /* dialog/drawer enter, default */
--motion-slow:  320ms;  /* hero moments */
--motion-xslow: 520ms;  /* page transitions if added */
```

**What animates:**
- Hover lifts (1px translate-Y, fast)
- CTA shine sweep on hover (slow)
- Drawer/panel slide (base, decelerate)
- Severity pill scale on hover (fast)
- Pulsing urgency dot (2s loop, base)
- Gradient mesh drift in hero backgrounds (24s loop, very slow ease-in-out)
- Skeleton shimmer (1.6s loop, linear)

**What does NOT animate:**
- Page transitions (cross-fade only on prefers-reduced-motion)
- List item enter (no stagger by default)
- Text scale

## Reduced motion

`prefers-reduced-motion: reduce` substitutes: cross-fade only (no transforms). Pulses, drift, shine, hover lifts — all skipped. Skeleton shimmer becomes a static gradient.

## Anti-list (what NOT to do)

- No drop shadows on cards (use borders instead)
- No bright pure-white backgrounds
- No purple gradients on white
- No rounded-full chips with gradient fills outside the CTA
- No Inter / Roboto / Geist / Space Grotesk substitution (Inter only for the redesign)
- No `font-variant: small-caps`
- No pulsing UI besides the urgency-dot pattern
- No glassmorphism on data-heavy surfaces (deferred to login hero only; tested in 001 variant B as not-the-winner)
- No multi-tone hover gradients on table rows

## Origin

Synthesized from sketches 001–006 (all). Source files in `sources/`.
