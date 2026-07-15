# Phase 16: Light-theme Visual Completion — Research

**Researched:** 2026-07-15
**Domain:** CSS custom properties (light-mode overrides) + WCAG 2.1 AA contrast + Playwright/axe parametrization
**Confidence:** HIGH — all findings verified directly against the codebase; no assumptions about external packages

---

## Summary

Phase 16 completes the light-theme work that was explicitly deferred from v2.0 (UX-D-03). The
architecture is already correct: `globals.css` has a `:root[data-theme="light"]` block and
`theme.tsx` sets `data-theme` on `<html>`. What is missing is (1) a full set of light-mode token
overrides for elements that the current 13-token light block does not address, (2) a per-route
visual sweep to catch dark-only artifacts (glows, hard-coded dark RGBA shadows, -soft fills
that lose legibility on a warm-cream background), and (3) an axe sweep that runs in **both**
themes so WCAG 2.1 AA is confirmed under light as well as dark.

The phase is **pure CSS + one test-harness change**. Zero new React components, zero JS
changes that affect the bundle, zero backend work. The constraint that `sunset.css` is vendored
and NOT edited directly (BL-04 pattern) means all fixes live in `globals.css` as
`:root[data-theme="light"]` overrides; any new light-palette values that become design-system
canonical must also be written back into
`.claude/skills/sketch-findings-getvul/references/foundation.md` and
`sources/themes/sunset.css` (mirroring what BL-04 did for dark contrast).

**Primary recommendation:** Audit each token category against the 13 already-overridden tokens,
add missing overrides (shadows, glows, semantic-state soft fills, severity tokens, -soft fills,
-on-soft shades) under a `/* Phase 16 — Light-mode visual completion */` comment block in
`globals.css`, then parametrize the existing `a11y-routes.spec.ts` to run the axe loop twice —
once in dark (current), once in light — and let axe's `color-contrast` rule (confirmed in
`wcag2aa` tag) report all remaining failures automatically.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UX-D-03-01 | Every authed route renders visually correct in light mode — no dark-only borders, shadows, hover, or disabled artifacts | Token gap analysis (§Token Gap Analysis) + route inventory (§Authed Routes Inventory) |
| UX-D-03-02 | All text + UI meets WCAG 2.1 AA (4.5:1 text, 3:1 UI/graphics) in light mode on every route | axe `color-contrast` rule confirmed in `wcag2aa` tag; parametrize sweep in §Validation Architecture |
| UX-D-03-03 | Severity/status/SLA pills + glyphs legible + distinct on light surfaces | Severity token analysis (§Severity, Status, SLA Tokens on Light) |
| UX-D-03-04 | `text-muted`/`text-faint`/disabled tokens pass AA; source-palette changes reconciled into design system (BL-04 pattern) | Existing token values vs. light background contrast analysis (§Contrast Arithmetic) + BL-04 reconciliation pattern (§BL-04 Reconciliation Pattern) |
| UX-D-03-05 | `e2e/a11y-routes.spec.ts` runs under `data-theme="light"` as well as dark and is green | Test parametrization strategy (§Validation Architecture — Test Parametrization) |
</phase_requirements>

---

## Project Constraints (from CLAUDE.md)

- **No freehand hex** — all color values must use CSS variables from `foundation.md` or be declared as new named tokens in `globals.css` and reconciled into the skill.
- **Inter + JetBrains Mono locked** — fonts not in scope for this phase.
- **Design system is authoritative** — conflicts between component behavior and sketch findings resolve in favor of the skill references.
- **Light-mode fixes that change the palette must be reconciled into the skill** — `foundation.md` + `visual-language.md` + `sources/themes/sunset.css` must reflect any new light-theme token values (BL-04 pattern).
- **Bundle: zero First-Load JS delta** — this phase is CSS + test only. No component changes that add JS weight.
- **Validation gate** — axe WCAG 2.1 AA in BOTH themes (dark already green; light must be green after this phase).

---

## Standard Stack

No new packages. All tooling is already present.

### Installed and confirmed

| Tool | Version (installed) | Role | Source |
|------|---------------------|------|--------|
| `@playwright/test` | `^1.61.1` | e2e runner | `[VERIFIED: frontend/package.json]` |
| `@axe-core/playwright` | `^4.12.1` | axe WCAG sweep fixture | `[VERIFIED: frontend/package.json]` |
| `axe-core` | included transitively | WCAG rule engine | `[VERIFIED: node_modules/axe-core/axe.js]` |
| `vitest` | `^4.1.6` | unit test runner | `[VERIFIED: frontend/package.json]` |

**No `npm install` needed for this phase.**

**axe `color-contrast` rule confirmation** `[VERIFIED: node -e "require('axe-core').getRules(['wcag2aa'])"]`:

```
ruleId: "color-contrast"
tags:   ["cat.color", "wcag2aa", "wcag143", ...]
enabled: true
```

The rule is in the `wcag2aa` tag set already used by the existing `makeAxeBuilder()` fixture.
Running the sweep with `data-theme="light"` set on `<html>` before `.analyze()` is called will
cause axe to measure contrast against the light-mode CSS property values. No fixture change
is needed — only the caller must set the theme attribute before navigating.

---

## Token Gap Analysis

### What globals.css already overrides for light mode

`[VERIFIED: frontend/src/app/globals.css lines 8-22]`

The current `:root[data-theme="light"]` block overrides 13 tokens:

```
--color-bg, --color-bg-darker, --color-surface, --color-surface-2,
--color-surface-glass, --color-border, --color-border-subtle, --color-border-strong,
--color-text, --color-text-muted, --color-text-faint, --color-text-inverse
color-scheme: light
```

### What is NOT overridden (falls through to sunset.css dark values)

All remaining tokens from `sunset.css` are dark-tuned and will be wrong on a warm-cream
light background. The categories below are ordered by visual-impact risk.

`[VERIFIED: .claude/skills/sketch-findings-getvul/sources/themes/sunset.css]`
`[VERIFIED: frontend/tailwind.config.ts — token→Tailwind class mapping]`

#### Category 1: Shadows and glows (HIGH visual impact)

Dark `--shadow-card` and `--shadow-elevated` use `rgba(0,0,0,0.4/0.5)` — black-on-black
works on dark surfaces but produces a subtle-to-invisible shadow on light cream. The glow
tokens (`--glow-pink`, `--glow-violet`, `--glow-amber`, `--glow-cta`, `--glow-card-inner`)
are pure-accent-color blobs: on a dark field they read as luminous halo; on a light field they
turn into garish ink blobs that break the premium feel.

**Usages found in production code** `[VERIFIED: grep across src/]`:
- `shadow-card` on `connector-card.tsx` (hover), `card.tsx` (elevated variant), `trend-chart.tsx`, `Toast.tsx`
- `shadow-elevated` on `drill-panel.tsx` (fixed side panel)
- `shadow-glow-cta` on `button.tsx` (CTA), `connectors/page.tsx`, `tickets/page.tsx`, `cspm/page.tsx`, `vulnerabilities/page.tsx`, `comment-input.tsx`, `ticket-drill-content.tsx`, `drill-content.tsx`, `drill-panel-mobile.tsx`
- `shadow-[var(--glow-cta)]` literal in `connectors/page.tsx` + `connector-form.tsx`

**Light-mode fix needed:** Override all shadow and glow tokens to lighter values:
- `--shadow-card` → `0 2px 8px rgba(0, 0, 0, 0.08)` (subtle neutral)
- `--shadow-elevated` → `0 8px 24px rgba(0, 0, 0, 0.12)`
- `--glow-pink` → `0 0 16px rgba(236, 72, 153, 0.2)` (softer)
- `--glow-violet` → `0 0 16px rgba(167, 139, 250, 0.2)`
- `--glow-amber` → `0 0 16px rgba(245, 158, 11, 0.15)`
- `--glow-cta` → `0 4px 16px rgba(236, 72, 153, 0.25), 0 0 0 1px rgba(0, 0, 0, 0.04) inset`
- `--glow-card-inner` → `0 0 0 1px rgba(0, 0, 0, 0.04) inset`

These are `[ASSUMED]` values pending contrast/visual review — the planner should treat them as
starting-point proposals; the human UAT step confirms visual quality.

#### Category 2: Accent soft fills and -on-soft text (HIGH a11y impact)

`sunset.css` defines:
- `--color-pink-soft: rgba(236, 72, 153, 0.18)` → on dark (`#0E0B1A`), effective fill ≈ #261228. On light cream (`#FAF7F2`), effective fill ≈ #F9D9EC (very pale pink). Text-on-soft becomes the contrast-critical question.
- `--color-violet-soft: rgba(167, 139, 250, 0.18)` → on light, effective fill ≈ #EDE9FE.
- `--color-amber-soft: rgba(245, 158, 11, 0.18)` → on light, effective fill ≈ #FDF3D8.

**BL-04 established on-soft text tokens for dark** (to meet 4.5:1): `--color-violet-on-soft: #C4B5FD`, `--color-pink-on-soft: #F472B6`, `--color-amber-on-soft: #F59E0B`. These same hex values may or may not clear 4.5:1 against the light-mode soft-fill backgrounds — they need contrast arithmetic against the light surfaces (see §Contrast Arithmetic). If they fail, lighter on-soft shades are needed for light mode only.

**Usages** `[VERIFIED: grep across src/]`:
- `status-pill.tsx`: `bg-violet-soft text-[#C4B5FD]` (Open pill)
- `profile-pane.tsx`: `bg-pink-soft text-[#F472B6]` (OWNER), `bg-violet-soft text-[#C4B5FD]` (ADMIN)
- `connector-form.tsx`: `bg-severity-low/10`, `bg-severity-critical/10`
- `drill-content.tsx`: `bg-pink-soft` + `text-severity-critical` (CISA KEV badge)
- `vuln-table.tsx`: `bg-pink-soft` + `text-severity-critical` (KEV inline badge)

**Key principle:** The `-soft` alpha fills are used as backgrounds; the hardcoded `[#C4B5FD]` and `[#F472B6]` literals in Tailwind JIT classes are the dark-tuned on-soft text values. For light mode, the on-soft overrides need to be re-evaluated (see §Contrast Arithmetic).

#### Category 3: Semantic state fills (HIGH a11y impact)

`--color-danger-soft: rgba(248,113,113,0.15)` and `--color-success-soft: rgba(74,222,128,0.15)` are dark-surface alpha fills. On light cream they will be extremely pale and may make text-danger or text-success fail contrast. No explicit override exists in the current light block.

#### Category 4: Severity color tokens (MEDIUM impact — may be fine as-is)

`--color-severity-critical: #F87171` (red), `--color-severity-high: #FB923C` (orange), `--color-severity-medium: #FBBF24` (yellow), `--color-severity-low: #A78BFA` (lavender), `--color-severity-info: #60A5FA` (blue).

These are accent hues used as text colors on soft fills and as standalone glyph colors. On a light cream background they may lose contrast (particularly `#FBBF24` yellow and `#60A5FA` blue). Exact outcome is determined by the axe sweep — but the planner should budget for potential token overrides, especially for `severity-medium` (yellow text on any light background) and `severity-low` (lavender).

**Distinct-on-light-surface** (UX-D-03-03): Since the design uses glyph + color + text (three-axis encoding), even if a color loses some contrast, the glyph differentiation remains. The axe `color-contrast` rule will flag any that fail WCAG 4.5:1 for text.

#### Category 5: Animation keyframe RGBA values (LOW visual impact)

`globals.css` keyframes contain hardcoded dark-optimized RGBA:
- `pulse-urgency`: `rgba(248, 113, 113, 0.6)` (red glow) — only used on dashboard hero urgency dot (not found in authed route scan; login only uses `gradient-drift`).
- `skeleton-shimmer`, `cta-shine-sweep`, `gradient-drift`: these are transform-only or gradient-based, not color-contrast issues.

No override needed in the light block for the keyframes themselves — if an element is visible in light mode, the animation opacity is a minor visual-quality matter, not a WCAG issue.

#### Category 6: `bg-black/50` overlay in `ticket-bulk-bar.tsx` (LOW impact)

`className="fixed inset-0 ... bg-black/50 backdrop-blur-sm"` (bulk-action modal backdrop). This is
an overlay darken pattern — functional on both themes (dark overlay works on any background). Not
a contrast violation. No fix needed unless the visual review flags it.

---

## Authed Routes Inventory

`[VERIFIED: frontend/e2e/routes.ts + find frontend/src/app/(authed)/]`

The axe sweep covers 9 static routes + 2 discovered dynamic routes (via API, not hardcoded IDs):

| Route | Static/Dynamic | Notes |
|-------|---------------|-------|
| `/dashboard` | static | Hero cards, trend chart, activity feed |
| `/dashboard/vulnerabilities` | static | Chip-bar, drill panel, severity pills, KEV badges |
| `/dashboard/assets` | static | Asset list, severity breakdown |
| `/dashboard/tickets` | static | Status pills, SLA pills, drill panel |
| `/dashboard/tickets/rules` | static | Rules list |
| `/dashboard/cspm` | static | CSPM findings, severity |
| `/dashboard/connectors` | static | ConnectorCard, sync-status-pill |
| `/dashboard/users` | static | Role badges (OWNER/ADMIN/ANALYST/VIEWER) |
| `/dashboard/settings` | static | Profile (role badge), workspace, SAML, notifications, audit log |
| `/dashboard/assets/[id]` | dynamic (discovered) | RiskRing, remediation-timeline, owner card |
| `/dashboard/tickets/[id]` | dynamic (discovered) | Full ticket detail, watcher stack, activity timeline |

The `discoverDetailRoutes()` function in `routes.ts` uses the backend API to resolve one real ID
for assets and tickets. The test must be running against a live dev server with seeded data.

---

## Contrast Arithmetic

`[ASSUMED]` — verified by reasoning from known values; not instrument-measured in this session.
The axe sweep is the authoritative instrument; these calculations are pre-flight estimates to
guide token selection.

### Light background values (from globals.css light block)

| Token | Value |
|-------|-------|
| `--color-bg` | `#FAF7F2` (luminance ≈ 0.96) |
| `--color-surface` | `#FFFFFF` (luminance = 1.0) |
| `--color-surface-2` | `#F7F2EA` (luminance ≈ 0.94) |

### Text tokens on light backgrounds

| Token | Light value | On `bg` (L≈0.96) | On `surface` (L=1.0) | AA pass (4.5:1)? |
|-------|-------------|-------------------|----------------------|-----------------|
| `--color-text` | `#1A1430` | ~16:1 | ~17:1 | PASS |
| `--color-text-muted` | `#5C5474` | ~7:1 | ~7.5:1 | PASS |
| `--color-text-faint` | `#8A8298` | ~3.8:1 | ~4.0:1 | **LIKELY FAIL** on bg/surface |
| `--color-text-inverse` | `#F0E8FF` | ~1.1:1 | ~1.1:1 | **FAIL** (for text) |

`text-faint` is the likely first failure — similar to the BL-04 dark-mode case. The current light
value `#8A8298` needs a darker companion for light mode. `#666080` is a candidate (same hue,
same saturation, darker value) `[ASSUMED]` — axe will confirm.

`text-inverse` (`#F0E8FF`) is near-white — on the dark gradient CTA button it's white-on-gradient
(fine); on any light surface used as foreground text it will be invisible. The current code
already uses `text-white` for CTA buttons directly, so `text-inverse` may have limited exposure
as a standalone text class. Verify during sweep.

### Severity colors on light surfaces (`bg` = `#FAF7F2`)

| Severity token | Hex | Approx contrast on `#FAF7F2` | AA (4.5:1)? |
|----------------|-----|-------------------------------|-------------|
| critical | `#F87171` | ~2.6:1 | **FAIL** |
| high | `#FB923C` | ~2.3:1 | **FAIL** |
| medium | `#FBBF24` | ~1.9:1 | **FAIL** |
| low | `#A78BFA` | ~3.2:1 | **FAIL** |
| info | `#60A5FA` | ~3.0:1 | **FAIL** |

These are `[ASSUMED]` contrast estimates. All severity colors are designed for dark surfaces.
On light cream, all five will likely fail WCAG 4.5:1 as small text. Light-mode overrides are
needed for the severity tokens — darker/richer variants of the same hues:

| Token | Proposed light value (same hue, darker) |
|-------|----------------------------------------|
| `--color-severity-critical` | `#DC2626` (red-600) — approx 5.5:1 on `#FAF7F2` |
| `--color-severity-high` | `#EA580C` (orange-600) — approx 4.7:1 |
| `--color-severity-medium` | `#D97706` (amber-600) — approx 4.5:1 |
| `--color-severity-low` | `#7C3AED` (violet-600) — approx 6.0:1 |
| `--color-severity-info` | `#2563EB` (blue-600) — approx 5.1:1 |

These are `[ASSUMED]` candidate values. The axe sweep will confirm or reject each one.
Importantly, the three-axis severity encoding (color + glyph + text label) means the WCAG
`color-contrast` rule tests the TEXT contrast; the distinct glyphs themselves are not
color-dependent, so glyph legibility on light (UX-D-03-03) is a visual-QA item, not an
axe-reportable item.

### Violet-on-soft on light surfaces

On dark, `#C4B5FD` on `rgba(167,139,250,0.18)` over `#0E0B1A` passes 4.5:1.
On light, `rgba(167,139,250,0.18)` over `#FAF7F2` ≈ `#EDE9FE`. `#C4B5FD` on `#EDE9FE` ≈ 1.5:1 — **FAIL**.
The -on-soft shades need to be overridden for light mode to much darker values.

Proposed light-mode on-soft overrides `[ASSUMED]`:
- `--color-violet-on-soft`: `#5B21B6` (violet-800) — approx 7.5:1 on `#EDE9FE`
- `--color-pink-on-soft`: `#9D174D` (pink-800) — approx 6.0:1 on `#F9D9EC`
- `--color-amber-on-soft`: `#92400E` (amber-800) — approx 5.5:1 on `#FDF3D8`

These will also affect `status-pill.tsx` (Open pill) and `profile-pane.tsx` (OWNER/ADMIN badges)
which hardcode the dark-mode `-on-soft` hex literals. Those two components will need minor
updates: replace `text-[#C4B5FD]` / `text-[#F472B6]` with CSS variable references
(`text-[var(--color-violet-on-soft)]` / `text-[var(--color-pink-on-soft)]`) so the light-mode
override in `globals.css` takes effect. **This is the only component-level change needed** —
all other fixes are pure CSS token overrides.

---

## BL-04 Reconciliation Pattern

`[VERIFIED: .planning/BACKLOG.md BL-04 entry + globals.css dark override block]`

The established flow for palette fixes in this project:

1. **Fix in `globals.css`** — add or modify token values under the appropriate `data-theme` block.
   The vendored `sunset.css` is NEVER edited directly.
2. **Add a design-system comment** — explain which axe finding or requirement drove the change,
   referencing the requirement ID (e.g., `/* Phase 16 a11y — UX-D-03-02 */`).
3. **Reconcile into the skill** — if the new value becomes design-system canonical (i.e., it
   defines the correct light-mode behavior of the token), write it back to:
   - `.claude/skills/sketch-findings-getvul/sources/themes/sunset.css` (add a light-mode
     overrides section or update the existing comment)
   - `.claude/skills/sketch-findings-getvul/references/foundation.md` (update the token table
     to show the light-mode value alongside the dark value)
   - `.claude/skills/sketch-findings-getvul/references/visual-language.md` (if severity/status/
     SLA pill rendering rules change for light surfaces, add a "Light-mode variants" subsection
     analogous to the BL-04 "Text on -soft fills" rule)
4. **Update component literals** (if any) — `status-pill.tsx` and `profile-pane.tsx` hardcode
   dark `-on-soft` hex values in JIT class syntax (`text-[#C4B5FD]`). Replace with
   `text-[var(--color-violet-on-soft)]` / `text-[var(--color-pink-on-soft)]` so the CSS
   variable cascade handles both themes.

**Anti-pattern (do not do):** Adding `[data-theme="light"] .status-pill-open { color: #5B21B6 }` as a
component-scoped rule — this circumvents the token system and creates untracked exceptions.
The correct approach is to always go through the CSS variable.

---

## Architecture Patterns

### CSS variable cascade (how theme switching works)

`[VERIFIED: frontend/src/app/globals.css + frontend/src/app/layout.tsx + frontend/src/lib/theme.tsx]`

```
layout.tsx → <script> in <head>:
  reads localStorage('getvul_theme') || prefers-color-scheme → sets data-theme on <html>

globals.css:
  @import 'sunset.css'         ← dark tokens as :root defaults
  :root[data-theme="light"] { ...overrides... }   ← narrower specificity wins for light

ThemeProvider:
  setTheme(next) → document.documentElement.setAttribute('data-theme', next)
                 → localStorage.setItem('getvul_theme', next)
```

**No Flash of Unstyled Content (FOUC)** because the `<script>` in `<head>` runs synchronously
before paint. The SSR default is `data-theme="dark"` (layout.tsx:49), which means the first
SSR paint is always dark; the client bootstrap corrects it before the browser paints.

### Theme toggle in e2e tests (the mechanism for UX-D-03-05)

`[VERIFIED: frontend/e2e/smoke.spec.ts lines 100-131]`

The existing smoke spec shows the working pattern: `page.addInitScript()` removes `getvul_theme`
from localStorage before each navigation, then `page.emulateMedia({ colorScheme: 'light' })` sets
the OS preference, which the bootstrap script reads and converts to `data-theme="light"`.

For the Phase 16 axe sweep, a cleaner approach is direct attribute injection — no need to depend
on `emulateMedia` + bootstrap indirection:

```typescript
// Before navigating to each route in the light-mode loop:
await page.addInitScript(() => {
  document.documentElement.setAttribute('data-theme', 'light');
});
// OR, after navigation (if addInitScript is not convenient in the loop):
await page.evaluate(() => {
  document.documentElement.setAttribute('data-theme', 'light');
});
await page.waitForTimeout(50); // let CSS cascade repaint
```

The `evaluate` approach runs after the page loads and lets React hydrate first. The `addInitScript`
approach sets the attribute before the bootstrap script runs — the bootstrap will then overwrite
it based on `localStorage`/`prefers-color-scheme`. For reliable light-mode forcing, the safest
pattern mirrors what smoke.spec.ts does: `addInitScript` to remove `getvul_theme` from localStorage
first, then either `emulateMedia({ colorScheme: 'light' })` OR `page.evaluate` after navigation.

**Recommended pattern for a11y-routes.spec.ts parametrization:**

```typescript
// Add a second describe block (or parametrize the existing one) for light theme.
// The simplest approach that doesn't restructure the existing dark sweep:

test.describe('WCAG 2.1 AA axe sweep — light theme (blocking)', () => {
  test.beforeEach(async ({ page }) => {
    // Force light mode via localStorage before the bootstrap script sees it.
    await page.addInitScript(() => {
      try { localStorage.setItem('getvul_theme', 'light'); } catch {}
    });
  });

  test('sweeps all routes for critical/serious violations in light mode', async ({
    page, makeAxeBuilder, makeAxeBuilderReportOnly
  }) => {
    // ... same loop as the dark sweep ...
    // After waitForNav, also assert data-theme is actually "light":
    const actualTheme = await page.locator('html').getAttribute('data-theme');
    // If bootstrap script overrides addInitScript, fall back to evaluate:
    if (actualTheme !== 'light') {
      await page.evaluate(() => {
        document.documentElement.setAttribute('data-theme', 'light');
      });
      await page.waitForTimeout(50);
    }
    // Then run makeAxeBuilder().analyze() ...
  });
});
```

**Why `localStorage.setItem` in addInitScript is reliable:** The FOUC-prevention script in
`layout.tsx` reads `localStorage.getItem('getvul_theme')` as its first check — it wins over
`prefers-color-scheme`. So pre-seeding `'light'` in localStorage guarantees the bootstrap sets
`data-theme="light"` before paint.

---

## Severity, Status, SLA Tokens on Light

### Severity pills

`[VERIFIED: frontend/src/components/vulnerabilities/vuln-table.tsx + chip-bar.tsx + drill-content.tsx]`

Severity pills use Tailwind classes like `text-severity-critical`, `bg-pink-soft`, `border-severity-critical/40`.
All these resolve via the CSS variable system and will automatically use light-mode overrides
once the variables are redefined in the `:root[data-theme="light"]` block. No component changes
needed for pills — the token override is sufficient.

The hardcoded RGBA values in `visual-language.md`'s CSS examples (`.sev-pill.critical {
background: rgba(248,113,113,0.12); }`) are sketch-prototype artifacts; production code uses
Tailwind `bg-pink-soft/10` patterns that resolve through the variable.

### Status pills

`[VERIFIED: frontend/src/components/tickets/status-pill.tsx]`

The Open pill hardcodes `text-[#C4B5FD]` (dark-mode violet-on-soft). This is the **one
component change needed**: replace with `text-[var(--color-violet-on-soft)]`.

Other status (In progress/Completed/Blocked) use `text-amber`, `text-success`, `text-severity-critical` —
all variable-resolved; they inherit the light-mode override from globals.css.

### SLA pills

`[VERIFIED: frontend/src/components/tickets/sla-pill.tsx — not read in full but class pattern confirmed]`

SLA pills use `text-severity-critical`, `text-severity-high`, `text-success` — all variable-
resolved. Same override flow as severity.

### Role badges (OWNER/ADMIN)

`[VERIFIED: frontend/src/components/settings/profile-pane.tsx lines 49-63]`

Hardcodes `text-[#F472B6]` (OWNER) and `text-[#C4B5FD]` (ADMIN). Same fix as status-pill:
replace literals with `text-[var(--color-pink-on-soft)]` / `text-[var(--color-violet-on-soft)]`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Contrast measurement | Manual contrast calculator | axe `color-contrast` rule (already wired) | Axe measures the ACTUAL computed CSS value in the browser, accounting for alpha compositing — more accurate than offline calculation |
| Light-mode CSS-in-JS switch | `const color = theme === 'light' ? '#X' : '#Y'` in components | CSS custom property override in globals.css | The variable cascade handles it without any JS; adding JS breaks the 0 KB delta constraint |
| Per-component dark: prefix | Tailwind `dark:text-gray-900` etc. | CSS variable override in globals.css | The project uses `data-theme` attribute, not prefers-color-scheme; Tailwind's `dark:` variant responds to `prefers-color-scheme` by default and would not be gated by `data-theme` |
| One-off hex color for light severity | Freehand hex in a component | Named token override in globals.css + reconcile into foundation.md | CLAUDE.md: no freehand hex |

---

## Common Pitfalls

### Pitfall 1: Tailwind `dark:` prefix does not respond to `data-theme`

**What goes wrong:** A developer adds `dark:bg-white dark:text-gray-900` expecting it to flip
in light mode. It does not — Tailwind's `dark:` variant responds to `prefers-color-scheme: dark`
by default (or `darkMode: 'class'` with `.dark` class, which this project does not use).
`[VERIFIED: grep for "dark:" in src/ — zero instances found]`

**How to avoid:** All theme-responsive values must go through the CSS variable system. The
existing convention is already correct — this pitfall is for future contributors.

**Warning sign:** Any Tailwind `dark:` prefix in a `.tsx` file.

### Pitfall 2: `addInitScript` fires before OR after the FOUC bootstrap

**What goes wrong:** `addInitScript` runs in the page context before scripts, but the ordering
relative to the inline `<script>` in `<head>` can vary. If the bootstrap script wins, it may
read `localStorage` (which addInitScript already set) — this is fine. If another test's
`afterEach` or test isolation clears localStorage between tests, the bootstrap falls back to
`prefers-color-scheme` (dark by project default), overriding the light intent.

**How to avoid:** After `page.goto()` + `waitForNav()`, assert
`await page.locator('html').getAttribute('data-theme') === 'light'` and force-set via
`page.evaluate` if it's wrong. This is the defensive pattern.

### Pitfall 3: Alpha-composited colors fool offline contrast calculators

**What goes wrong:** `rgba(167,139,250,0.18)` on `#FAF7F2` looks like it should produce a
specific computed color, but axe measures the ACTUAL browser-rendered pixel (which accounts for
subpixel rendering, anti-aliasing, and alpha compositing correctly). Offline contrast estimates
can be off by 0.5–1.0 contrast ratio.

**How to avoid:** Let axe be the single source of truth. Use the offline estimates in this
research only to identify *likely* failures so the fix can be structured before running the test;
confirm with the actual axe output.

### Pitfall 4: Hardcoded JIT hex literals don't cascade

**What goes wrong:** `text-[#C4B5FD]` in a JSX class string is a Tailwind JIT literal — it
is compiled to `color: #C4B5FD` directly, bypassing the CSS variable cascade. Overriding
`--color-violet-on-soft` in globals.css does NOT affect this literal.

**How to avoid:** Replace `text-[#C4B5FD]` with `text-[var(--color-violet-on-soft)]` so the
token cascade works. Applies to: `status-pill.tsx`, `profile-pane.tsx`. These are the ONLY
two files with this pattern `[VERIFIED: grep text-\[# in src/]`.

### Pitfall 5: The disabled "Theme: Light" switch in user-chip.tsx

`[VERIFIED: frontend/src/components/shell/user-chip.tsx lines 59-78]`

The `DropdownMenuRadioItem value="light"` is `disabled` with `aria-description` explaining
the light theme is not ready. This WR-03 comment must be updated (remove `disabled` attr,
remove the aria-description) once Phase 16 ships — this is a deliverable, not just a
nice-to-have.

### Pitfall 6: Badge.tsx is orphaned but uses off-system colors

`[VERIFIED: grep for SeverityBadge/StatusBadge/SourceBadge imports — zero callers found]`

`frontend/src/components/ui/Badge.tsx` uses raw Tailwind palette (`bg-red-500/20 text-red-400
bg-gray-700 text-gray-300` etc.). It is not imported anywhere and is effectively dead code.
Do NOT resurrect it for this phase. If it were to be used, it would need a full rewrite to
use design-system tokens. For now: no action.

---

## Code Examples

### Pattern 1: Light-mode token override in globals.css (BL-04 shape)

`[VERIFIED: globals.css dark override block — same shape, different selector]`

```css
/* Phase 16 — Light-mode visual completion (UX-D-03-01..04).
   All overrides below apply ONLY under data-theme="light".
   Source-palette changes are reconciled into the design-system skill
   (foundation.md + visual-language.md + sunset.css) per BL-04 pattern. */
:root[data-theme="light"] {
  /* ... existing 13 tokens ... */

  /* Shadows — lightened from dark-surface black-alpha values */
  --shadow-card:     0 2px 8px rgba(0, 0, 0, 0.08);
  --shadow-elevated: 0 8px 24px rgba(0, 0, 0, 0.12);

  /* Glows — softer on light surfaces */
  --glow-pink:      0 0 16px rgba(236, 72, 153, 0.20);
  --glow-violet:    0 0 16px rgba(167, 139, 250, 0.20);
  --glow-amber:     0 0 16px rgba(245, 158, 11, 0.15);
  --glow-cta:       0 4px 16px rgba(236, 72, 153, 0.25), 0 0 0 1px rgba(0,0,0,0.04) inset;
  --glow-card-inner: 0 0 0 1px rgba(0, 0, 0, 0.04) inset;

  /* Severity — darker same-hue variants for AA on cream */
  --color-severity-critical: #DC2626;
  --color-severity-high:     #EA580C;
  --color-severity-medium:   #D97706;
  --color-severity-low:      #7C3AED;
  --color-severity-info:     #2563EB;

  /* Semantic states */
  --color-danger:  #DC2626;
  --color-success: #15803D;
  --color-warning: #D97706;

  /* On-soft text for light surfaces (overrides dark-tuned BL-04 values) */
  --color-violet-on-soft: #5B21B6;
  --color-pink-on-soft:   #9D174D;
  --color-amber-on-soft:  #92400E;
}
```

Note: all hex values above are `[ASSUMED]` candidates. The axe sweep confirms or adjusts them.

### Pattern 2: Replace hardcoded JIT literal with variable reference

`[VERIFIED: status-pill.tsx line 33 + profile-pane.tsx lines 57-58]`

```tsx
// BEFORE (dark-only):
classes: 'border-violet/40 bg-violet-soft text-[#C4B5FD]',

// AFTER (theme-responsive via CSS variable):
classes: 'border-violet/40 bg-violet-soft text-[var(--color-violet-on-soft)]',
```

```tsx
// BEFORE (dark-only):
OWNER: 'bg-pink-soft text-[#F472B6]',
ADMIN: 'bg-violet-soft text-[#C4B5FD]',

// AFTER:
OWNER: 'bg-pink-soft text-[var(--color-pink-on-soft)]',
ADMIN: 'bg-violet-soft text-[var(--color-violet-on-soft)]',
```

### Pattern 3: Parametrize axe sweep by theme in a11y-routes.spec.ts

`[VERIFIED: e2e/smoke.spec.ts addInitScript pattern + theme.tsx localStorage key 'getvul_theme']`

```typescript
// New describe block to add alongside the existing dark-mode sweep:
test.describe('WCAG 2.1 AA axe sweep — light theme (blocking)', () => {
  // Force light mode by pre-seeding localStorage before the FOUC bootstrap reads it.
  // The bootstrap script in layout.tsx checks localStorage('getvul_theme') first.
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      try {
        window.localStorage.setItem('getvul_theme', 'light');
      } catch { /* storage unavailable; fall back to evaluate after goto */ }
    });
  });

  test('sweeps all routes for critical/serious violations in light mode', async ({
    page, makeAxeBuilder, makeAxeBuilderReportOnly,
  }) => {
    const detailRoutes = await discoverDetailRoutes(page);
    const routes: string[] = [...STATIC_ROUTES, ...detailRoutes];

    for (const route of routes) {
      await page.goto(route);
      await waitForNav(page, 1280);

      // Defensive: confirm data-theme is actually "light" (bootstrap may override)
      const actualTheme = await page.locator('html').getAttribute('data-theme');
      if (actualTheme !== 'light') {
        await page.evaluate(() => {
          document.documentElement.setAttribute('data-theme', 'light');
        });
        await page.waitForTimeout(50); // allow CSS cascade repaint
      }

      const results = await makeAxeBuilder().analyze();
      const blocking = results.violations.filter(
        (v) => v.impact === 'critical' || v.impact === 'serious',
      );
      expect(blocking, `Zero critical/serious axe violations (light) on ${route}`)
        .toHaveLength(0);
    }
  });
});
```

### Pattern 4: User-chip disabled-light fix (enable the theme toggle)

`[VERIFIED: frontend/src/components/shell/user-chip.tsx lines 59-78]`

```tsx
// Remove `disabled` and the aria-description "In progress" badge.
// Before:
<DropdownMenuRadioItem
  value="light"
  disabled
  aria-description="Light theme is not ready yet — only surface tokens swap; severity, accent, and danger colors stay dark-tuned."
>
  ...
  <span className="text-[10px] uppercase ... text-text-faint">{'In progress'}</span>
</DropdownMenuRadioItem>

// After (Phase 16 ships light theme as complete):
<DropdownMenuRadioItem value="light">
  {'Theme: Light'}
</DropdownMenuRadioItem>
```

---

## State of the Art

| Area | Old Approach (pre-Phase 16) | Phase 16 Approach |
|------|-----------------------------|-------------------|
| Light theme | Architecture-only: 13 surface/text/border tokens overridden | Full visual completion: + severity, semantic-state, glow, shadow, -on-soft tokens |
| axe sweep | Dark theme only (colorScheme: 'dark' in playwright.config.ts) | Both themes: existing dark sweep + new light-mode describe block |
| User theme toggle | Light option `disabled` with "In progress" label | Light option enabled; both themes fully verified |
| Design-system skill | Dark values only for severity/status/SLA/on-soft | Light-mode variant subsection added to foundation.md + visual-language.md |

---

## Environment Availability

| Dependency | Required By | Available | Notes |
|------------|------------|-----------|-------|
| Next.js dev server (port 3000) | Playwright e2e sweep | Must be running | Start: `cd frontend && npm run dev` |
| Backend (port 8000) | `discoverDetailRoutes()` — queries `/api/v1/assets?page=1` etc. | Must be running | Start: `docker compose up backend db` |
| Seeded data | `discoverDetailRoutes()` returns non-empty lists | Depends on dev DB | Empty list → detail routes skipped (test warns but continues) |
| Playwright browsers | e2e tests | Installed | `npx playwright install` if missing |

**Note:** Backend + seeded data are required only for the axe sweep. The CSS token work and
component literal fixes require only `npm run dev` (frontend only) for visual review.

**Backend-pytest-DB hazard is irrelevant** — this phase is purely frontend (CSS + one test harness
change). No backend tests, no Python environment, no database migrations.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `text-faint: #8A8298` on `bg: #FAF7F2` fails WCAG 4.5:1 | Contrast Arithmetic | Low — axe confirms; fix straightforward (darken the value) |
| A2 | All 5 severity color tokens fail WCAG 4.5:1 on cream | Contrast Arithmetic | Low — axe confirms; if some pass, fewer tokens need overriding |
| A3 | `violet-on-soft: #C4B5FD` on light `violet-soft` fill fails 4.5:1 | Contrast Arithmetic | Low — this calculation is directionally correct (1.5:1 is far below AA) |
| A4 | Proposed light-mode severity hex candidates (`#DC2626` etc.) clear 4.5:1 | Token Gap Analysis | Medium — actual contrast ratios need axe confirmation; adjust if any fail |
| A5 | Shadow/glow candidate values are visually appropriate for premium feel | Token Gap Analysis | Medium — visual UAT may require iteration; axe does not flag visual-quality |
| A6 | `Badge.tsx` has zero callers (safe to ignore) | Pitfalls | Low — grep confirmed no imports; dead code only |
| A7 | `page.addInitScript` + `localStorage.setItem('getvul_theme','light')` reliably forces light mode before bootstrap runs | Test Parametrization | Medium — smoke.spec.ts uses the reverse (removeItem); same mechanism, opposite polarity. Defensive `evaluate` fallback in Pattern 3 mitigates this risk. |

---

## Open Questions (RESOLVED)

RESOLVED during planning — none blocks execution: (Q1) run axe in light mode and investigate any violation beyond expected token failures; (Q2) `/login` gradient-mesh legibility is a human-UAT item, out of authed-route axe scope; (Q3) the `severity-medium` starting hex is axe-tunable — the sweep is the authoritative instrument.

1. **Are there any routes that load `prefers-color-scheme` media queries directly?**
   - What we know: No `@media (prefers-color-scheme)` found in globals.css or component CSS.
   - What's unclear: Third-party components (if any) might embed their own color-scheme logic.
   - Recommendation: Run axe in light mode; if new violations appear beyond the expected
     token failures, investigate the source element.

2. **Does the gradient-mesh on `/login` look acceptable in light mode?**
   - What we know: `bg-gradient-mesh` uses dark-tuned radial gradients with pink/violet/amber
     at 30-40% alpha. On a light background, these become vivid blobs rather than subtle haze.
   - What's unclear: `/login` is not an authed route and is not in `STATIC_ROUTES` — it is NOT
     swept by the authed a11y test. The smoke spec covers it but without light-mode forcing.
   - Recommendation: Add `/login` light-mode visual check to the human UAT list; do not add it
     to the axe sweep scope (it's unauthenticated and separate from UX-D-03's scope).

3. **Do `--color-danger-soft` and `--color-success-soft` need light-mode overrides?**
   - What we know: Used in a few places (e.g., `ConfirmModal` danger button uses
     `bg-severity-critical` directly; `connector-form.tsx` uses `bg-severity-critical/10`).
   - What's unclear: `bg-severity-critical/10` with the overridden `--color-severity-critical:
     #DC2626` will give `rgba(220,38,38,0.10)` on cream — very pale red. Text `text-severity-
     critical` (#DC2626) on this fill is effectively text-on-white, likely AA pass.
   - Recommendation: Do not add explicit soft-fill overrides; let the severity token override
     cascade through the `/10` alpha modifier. Axe will flag if the result still fails.

---

## Validation Architecture

**Nyquist validation** is enabled (no `nyquist_validation: false` in `.planning/config.json`).

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Playwright `^1.61.1` + `@axe-core/playwright ^4.12.1` |
| Config file | `frontend/e2e/playwright.config.ts` |
| Quick run command | `cd frontend && npx playwright test e2e/a11y-routes.spec.ts --project=chromium-a11y` |
| Full suite command | `cd frontend && npx playwright test` |
| Unit tests | `cd frontend && npx vitest run` |

**Server prerequisite:** Both commands require a running dev server + backend:
```bash
# Terminal 1: frontend
cd frontend && npm run dev
# Terminal 2: backend (docker)
docker compose up backend db
```

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UX-D-03-01 | No dark-only borders/shadows/hover/disabled on light routes | manual visual + axe structural | `npx playwright test e2e/a11y-routes.spec.ts --project=chromium-a11y` (light-mode describe) | ❌ Wave 0: add light-mode describe block to `a11y-routes.spec.ts` |
| UX-D-03-02 | WCAG 2.1 AA contrast in light mode (4.5:1 text, 3:1 UI) | automated axe (color-contrast rule in wcag2aa) | `npx playwright test e2e/a11y-routes.spec.ts --project=chromium-a11y` (light-mode describe) | ❌ Wave 0: same file change |
| UX-D-03-03 | Severity/status/SLA pills legible + distinct on light surfaces | automated axe (contrast) + manual visual (glyph distinctness) | axe sweep in light mode | ❌ Wave 0: axe sweep; glyph distinctness = human UAT |
| UX-D-03-04 | text-muted/text-faint/disabled pass AA; reconciled into design system | automated axe + grep gate | `grep -n "color-text-faint" frontend/src/app/globals.css` confirms override present; axe confirms contrast | ❌ Wave 0: CSS token addition |
| UX-D-03-05 | `e2e/a11y-routes.spec.ts` runs in light mode AND dark mode, both green | automated e2e | `cd frontend && npx playwright test e2e/a11y-routes.spec.ts --project=chromium-a11y` | ❌ Wave 0: add light-mode describe block |

### Sampling Rate

- **Per task commit:** `cd frontend && npx playwright test e2e/a11y-routes.spec.ts --project=chromium-a11y` (runs both dark + light sweeps)
- **Per wave merge:** Full suite: `cd frontend && npx playwright test && npx vitest run`
- **Phase gate:** Full suite green (`npx playwright test` — all projects including smoke + reduced-motion) before `/gsd-verify-work`

### Wave 0 Gaps (must exist before implementation waves start)

- [ ] `frontend/e2e/a11y-routes.spec.ts` — add `test.describe('WCAG 2.1 AA axe sweep — light theme (blocking)')` block (Pattern 3 above). The file EXISTS but needs the new describe block.
- [ ] `frontend/src/app/globals.css` — `:root[data-theme="light"]` block must have the new tokens before the axe sweep is green. Add in the same Wave as the test parametrization so both land together.
- [ ] Component literal fixes (`status-pill.tsx` + `profile-pane.tsx`) — must land before the axe sweep is expected to pass (otherwise the -on-soft contrast violations will remain even with the CSS variable override).
- [ ] `user-chip.tsx` — remove `disabled` from the Light radio item after the token/component fixes are confirmed green.
- [ ] Design-system skill reconciliation — `foundation.md` + `visual-language.md` + `sunset.css` updated to carry light-mode token values (BL-04 mirror for light mode).

*(No new test files needed — the gap is an additional describe block in an existing file.)*

---

## Security Domain

Security enforcement is not applicable to this phase — it is CSS-only token changes + a test-harness
update. There is no new data handling, no new endpoints, no authentication surface, and no
cryptographic operations. The ASVS audit is appropriately skipped.

---

## Sources

### Primary (HIGH confidence)

- `[VERIFIED: frontend/src/app/globals.css]` — full light-mode token block (lines 8-22), dark override, keyframes
- `[VERIFIED: frontend/e2e/a11y-routes.spec.ts]` — existing axe sweep structure
- `[VERIFIED: frontend/e2e/fixtures/axe.ts]` — makeAxeBuilder fixture tags (wcag2a, wcag2aa, wcag21aa)
- `[VERIFIED: frontend/e2e/playwright.config.ts]` — projects, colorScheme default, storageState
- `[VERIFIED: frontend/e2e/smoke.spec.ts]` — addInitScript + emulateMedia theme-bootstrap pattern
- `[VERIFIED: frontend/e2e/routes.ts]` — STATIC_ROUTES (9 routes), discoverDetailRoutes
- `[VERIFIED: frontend/src/lib/theme.tsx]` — setTheme flow: data-theme attr + localStorage key 'getvul_theme'
- `[VERIFIED: frontend/src/app/layout.tsx lines 1-60]` — FOUC bootstrap script, localStorage priority
- `[VERIFIED: .claude/skills/sketch-findings-getvul/sources/themes/sunset.css]` — all 50+ dark token values
- `[VERIFIED: .claude/skills/sketch-findings-getvul/references/foundation.md]` — token documentation
- `[VERIFIED: .claude/skills/sketch-findings-getvul/references/visual-language.md]` — on-soft AA rule (BL-04)
- `[VERIFIED: frontend/tailwind.config.ts]` — token-to-Tailwind class mapping
- `[VERIFIED: frontend/package.json]` — @playwright/test ^1.61.1, @axe-core/playwright ^4.12.1, vitest ^4.1.6
- `[VERIFIED: node -e "require('axe-core').getRules(['wcag2aa'])"]` — color-contrast rule confirmed in wcag2aa
- `[VERIFIED: frontend/src/components/tickets/status-pill.tsx]` — text-[#C4B5FD] literal (dark-only)
- `[VERIFIED: frontend/src/components/settings/profile-pane.tsx lines 49-63]` — text-[#F472B6] / text-[#C4B5FD] literals
- `[VERIFIED: frontend/src/components/shell/user-chip.tsx lines 59-78]` — disabled light radio item (WR-03)
- `[VERIFIED: .planning/BACKLOG.md BL-04 entry]` — reconciliation pattern documented
- `[VERIFIED: .planning/REQUIREMENTS.md Phase 16 section]` — UX-D-03-01..05 full text

### Secondary (MEDIUM confidence)

- `[VERIFIED: grep for text-[# across src/]` — exactly two files with dark-only JIT hex literals
- `[VERIFIED: grep for dark: across src/]` — zero instances (no Tailwind dark: prefix used)
- `[VERIFIED: grep for SeverityBadge/StatusBadge/SourceBadge imports]` — Badge.tsx has zero callers (orphaned)

### Tertiary (LOW confidence — assumptions requiring axe confirmation)

- Contrast arithmetic estimates for severity tokens, text-faint, and on-soft text on light surfaces

---

## Metadata

**Confidence breakdown:**
- Token gap analysis: HIGH — verified against actual CSS files
- Test parametrization pattern: HIGH — derived from smoke.spec.ts production pattern
- Contrast arithmetic estimates: LOW — approximations pending axe measurement
- Component literal locations: HIGH — grep-verified

**Research date:** 2026-07-15
**Valid until:** This research covers a snapshot of the codebase at commit 657393c (latest main);
stable until any component that uses severity/status/on-soft styling is modified.
