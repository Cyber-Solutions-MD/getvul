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
| 002 | dashboard-sunset | Which information hierarchy answers "what should I work on right now?" — and does the palette scale to a data-heavy screen? | **B · Action-first hero** | dashboard, layout, hierarchy, navigation-shell |
| 003 | vulnerabilities-sunset | Does sunset palette survive a dense data table? Which filter UX + density + drill-down combo fits GetVul's workflow? | **C · Chip bar + side panel** | vulnerabilities, table, filters, density, drill-down |
| 004 | states-sunset | How should empty / loading / error states feel in the sunset world? | All 3 approved; **C · Error (partial failure)** is the lead pattern | states, empty, loading, error, patterns |
| 005 | asset-detail-sunset | Which detail-page layout + risk-score viz fits the sunset world? | _pending_ | asset-detail, layout, risk-score, detail-page-pattern |

## Validated decisions (from sketch 004)

- **D-26 (loading):** Skeleton chip bar + skeleton table rows with gradient shimmer. **Per-connector progress strip** showing which sources have returned and which are still loading, with running count ("3 of 4 sources · 312 found so far"). Sidebar counts get skeleton too. Never a black screen — show partial data as it arrives.
- **D-27 (empty — filtered to zero):** Centered card with sunset-gradient icon + glow. Headline explaining *what* matched zero. Body explaining *why* (active filters listed inside the card as redundant-but-helpful context). Three CTAs at three tiers: clear-all (gradient primary), broaden-one-axis (secondary), broaden-everything (secondary). Bottom: violet "lightbulb" suggestion turning the dead-end into an opportunity ("save this as a watch").
- **D-28 (error — partial failure):** Realistic case for GetVul. Lead pattern across all error variants. Amber (not red) inline banner with: title + sub (HTTP code, last sync, retry count, request ID) + actions (View trace + Retry now). **Per-source status cards** in a row (one per connector) showing ok/fail status. Stale rows in the table get amber background tint + `stale` pill on source column. Footer note repeats the partial-data caveat with retry links. **Never replace the screen with a generic error when partial data is available.**

## Deferred (acknowledged, not blocking milestone planning)

- Total-failure error state (all sources down) — D-29 placeholder, sketch later
- First-time-empty / no-connectors-yet onboarding state — separate pattern
- Quiet/win empty state (when all critical items are resolved or snoozed) — friendly version
- Toast notifications for transient errors — pattern not yet sketched
- Dashboard's empty state (different from /vulnerabilities)

## Validated decisions (from sketch 003 → C)

- **D-20:** Sunset palette **survives** dense severity data. The deep-plum background lets red/orange/yellow severity pills breathe without becoming a fruit salad. Confirmed at full-screen and at 375px card view.
- **D-21:** **Horizontal filter bar > vertical filter drawer.** Filters live in an inline chip bar above the table (search field + severity chips + source chips + saved-filter pill in violet + clear-all link). Frees the full table width for data. Easier to share via URL.
- **D-22:** **Side-panel drill-down** is the canonical pattern for "scan → drill → act → close." Click a row to open a 420px right-side panel; table dims to ~60%. Panel includes: severity + KEV + exploit pills · description · CVSS score with vector · affected hosts list · remediation paragraph · action buttons (gradient CTA "Create Jira ticket" + secondary "Snooze 24h" + "Copy NVD link"). Close via × button or click another row to swap.
- **D-23:** Severity glyphs (■ ▲ ◆ ○ □) survive both table rows and mobile cards. Three-axis encoding (color + glyph + size) holds up under density.
- **D-24:** Tables collapse to card view at 375px width — severity pill + CVE on row 1, product on row 2, asset + SLA pill on row 3. No horizontal scroll, no truncation.
- **D-25:** The "Triage queue" gradient CTA in the top-right **anchors** rather than fights with severity color. It sits in a different zone (action column) than the data (rows), so the eye reads them separately.

## Summary of validated direction across all 3 sketches

| Surface | Pattern |
|---|---|
| Visual language | Wiz-inspired premium SaaS, **sunset palette** (pink → violet → amber on deep plum), restrained polish (gradient/glow only in CTAs + brand mark + active-nav strip + severity, not elsewhere) |
| Layout | **Sidebar nav (left, 220px) + topbar + main**. Sidebar has gradient brand mark + section labels + gradient-strip active indicator. Topbar has ⌘K search + bell + help + avatar chip. |
| Login | **Split-screen** — gradient mesh + tagline + product peek on left, clean form on right. SSO buttons primary, password fields secondary. Gradient CTA. |
| Dashboard | **Action-first hero** — eyebrow + pulsing dot + "3 critical CVEs need your eyes" + Start triage CTA. Stats demoted to a strip. Right sidebar activity feed. |
| Data table | **Chip bar filters + side panel drill-down**. Sunset palette survives severity color. Tables collapse to cards on mobile. |
| Severity | **Three-axis encoding** — color (red/orange/yellow/violet/blue) + Unicode glyph (■ ▲ ◆ ○ □) + size. Survives dense-data context. |
| CTAs | **Single gradient pill** (pink → violet → amber, `--glow-cta`), used across every screen as the primary action. Secondary actions are dark-surface bordered. |
| Motion | Subtle: hover lifts (1px), gradient drift (24s), pulsing urgency dot (2s). No page transitions designed yet. |
| Type | **Inter** body, **JetBrains Mono** for identifiers (CVE IDs, hostnames, scores, durations, counts). Locked. |

## What's not yet validated (deferred)

- Empty / loading / error states (REDESIGN_PLAN flagged as top pain point)
- Light theme — sunset translates to dark naturally; light variant untested
- Asset detail page, ticket flow, connector onboarding
- Settings page (was tabbed in v1, should be sidebar-of-categories per REDESIGN_PLAN)
- Mobile bottom-nav (sidebar collapses to hamburger; bottom-nav design deferred to v2-10 equivalent)
- Charts beyond the trend bar chart (sankey for connector health, ring for risk distribution)
- Page transitions / route-change motion

## Validated decisions (from sketch 002 → B)

- **D-14:** GetVul's user is a *doer*, not a reporter. Dashboard hero answers "what to do now" with a primary CTA, not a stat grid. Stats are secondary, demoted to a thin strip below the hero.
- **D-15:** Hero card pattern: gradient eyebrow + pulsing-dot urgency indicator + big numeric headline + supporting sentence + action buttons (snooze + CTA). The "fancy" lives in the eyebrow and pulse, not the card chrome.
- **D-16:** Activity feed belongs in a right sidebar at desktop widths, not full-width below. Keeps the main column scannable and the feed glanceable.
- **D-17:** Persistent UI shell: sidebar with gradient brand mark + gradient-strip active-nav indicator (with subtle glow). Topbar with search-as-input (⌘K affordance), icon buttons (bell, help), avatar chip. This shell carries to every authenticated screen.
- **D-18:** Severity glyphs (■ ▲ ◆ ○ □) work alongside color tokens — confirmed legible at table row sizes. Three-axis encoding (color + glyph + size) survived the dense-data context.
- **D-19:** Triage rows show severity glyph + CVE-ID + description + asset + score + SLA pill. Score color matches severity (≥9 red, ≥7 orange, ≥5 amber). SLA pill states: overdue / soon / ok.

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
