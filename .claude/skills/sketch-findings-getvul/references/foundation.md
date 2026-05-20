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
--color-text-faint:    #6B6488;
--color-text-inverse:  #0E0B1A;

/* Sunset accents */
--color-pink:          #EC4899;  /* hot pink */
--color-violet:        #A78BFA;  /* lavender */
--color-amber:         #F59E0B;  /* amber */
/* + matching -soft variants at 18% alpha */

/* The signature gradient */
--gradient-sunset:     linear-gradient(135deg, #EC4899 0%, #A78BFA 50%, #F59E0B 100%);
--gradient-mesh:       radial-gradient(at 20% 20%, rgba(236, 72, 153, 0.4) 0%, transparent 50%),
                       radial-gradient(at 80% 30%, rgba(167, 139, 250, 0.35) 0%, transparent 55%),
                       radial-gradient(at 50% 80%, rgba(245, 158, 11, 0.3) 0%, transparent 55%);

/* Semantic states */
--color-danger:    #F87171;
--color-success:   #4ADE80;
--color-warning:   #FBBF24;
--color-info:      #60A5FA;
```

### Severity colors (locked — used in every list/badge/glyph)

```css
--color-severity-critical: #F87171;  /* red */
--color-severity-high:     #FB923C;  /* orange */
--color-severity-medium:   #FBBF24;  /* yellow */
--color-severity-low:      #A78BFA;  /* lavender */
--color-severity-info:     #60A5FA;  /* blue */
```

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
--shadow-card:        0 8px 24px rgba(0, 0, 0, 0.4);
--shadow-elevated:    0 20px 60px rgba(0, 0, 0, 0.5);
--glow-pink:          0 0 32px rgba(236, 72, 153, 0.45);
--glow-violet:        0 0 32px rgba(167, 139, 250, 0.45);
--glow-cta:           0 8px 32px rgba(236, 72, 153, 0.35),
                      0 0 0 1px rgba(255, 255, 255, 0.05) inset;
```

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
