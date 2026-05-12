---
name: sketch-findings-getvul
description: Validated design decisions, CSS patterns, and visual direction from the v2.0 UI/UX redesign sketch experiments. Auto-loaded during UI implementation on getvul. Covers sunset palette, Wiz-inspired layouts, severity / SLA / status visual language, and state patterns.
---

<context>
## Project: getvul

GetVul v2.0 UI/UX redesign — **Wiz-inspired premium SaaS** in a **sunset / dusk palette** (pink → violet → amber on deep plum). Less information density than Wiz proper, restrained polish, gradient CTAs, severity glyphs at scale, persistent shell (sidebar + topbar with ⌘K).

Sketches wrapped: 2026-05-12.

Reference points: wiz.io (overall language); Linear / Vercel / Stripe (what NOT to be — cool palettes); Arc, new-Linear (adjacent ideas).

**Anti-direction (rejected):** "Tactical Carbon" / industrial / utilitarian / mono-identifier / sharp corners — the rolled-back v2-01 attempt.
</context>

<design_direction>
## Overall Direction

- **Palette:** sunset / dusk — `#0E0B1A` deep plum bg, `#1A1430` raised surfaces, accents `#EC4899` pink + `#A78BFA` violet + `#F59E0B` amber. Signature gradient `linear-gradient(135deg, pink 0%, violet 50%, amber 100%)`.
- **Typography:** Inter (body/UI/headings) + JetBrains Mono (CVE IDs, hostnames, scores, durations, all "terminal-pasteable" values). 1.25 modular scale, 14px base, tabular-nums on numeric cells.
- **Spacing:** 4px base, `--space-N` tokens through 96px. Cards 20px padding by default.
- **Shapes:** Rounded but not exaggerated — buttons/inputs 10px, cards 14px, hero cards 20px, large prominent cards 28px, full-pill 9999px.
- **Shadows:** Borders preferred over shadows for normal chrome. Glow reserved for sunset-gradient elements (CTA, brand mark, active nav strip).
- **Motion:** Subtle. Hover lifts (1px, 120ms), gradient drift (24s loop on hero mesh), pulsing urgency dot (2s loop), skeleton shimmer (1.6s linear). No page transitions designed yet. Respects `prefers-reduced-motion`.

## Layout patterns

| Surface | Pattern |
|---|---|
| Login / unauthenticated | **Split-screen** — gradient mesh left, clean form right. SSO primary, password secondary. |
| Dashboard / "what to do now" | **Action-first hero** — pulsing eyebrow + numeric headline + CTA. Stats demoted to a thin strip. Activity feed in right sidebar. |
| List routes (/vulnerabilities, /tickets) | **Chip-bar filters + side-panel drill-down**. No persistent left drawer. Click row → 420px right panel. |
| Detail pages (/assets/[id], /tickets/[id]) | **Two-column with sticky right metadata rail.** Main column: workflow content. Rail: risk score, owner, identity, asset link. |

## Visual language

- **Severity** — three-axis: color + Unicode glyph (■ ▲ ◆ ○ □) + size. Always paired in pills.
- **SLA** — three-tier: overdue (red) / soon (amber) / ok (green). Mono. Right-aligned.
- **Status** — separate color family from severity: Open (violet) · In progress (amber) · Completed (green) · Blocked (red). Pill with leading dot.
- **Providers** — Jira (cool blue) · Asana (coral) · GitHub (violet). Gradient marks, not real logos.
- **CISA KEV badge** — red mono uppercase pill, inline with severity.
- **Avatars** — sunset-gradient default, violet/amber variants for variety. 40px (primary) / 26px (chip) / 20px (assignee).
- **Single gradient CTA** — repeats as the primary action on every screen.

## State patterns (mandatory in production)

- **Loading** — skeleton screens + per-source progress strip ("3 of 4 sources · 312 found so far") + connector chips with state. Never black screens.
- **Empty** — sunset-gradient icon + explained empty + 3 CTAs (clear / broaden / search wider) + lightbulb hint suggesting save-as-filter.
- **Error (partial failure)** — amber inline banner (HTTP code + request ID + last-sync + retry) + per-source status cards + stale rows tinted amber + footer caveat. Never replace screen with generic error when partial data exists.

## Voice

A peer, not a butler. Direct, technical, friendly. Linear / Vercel / GitHub-flavored. Sentence case. Mono for paths/values/IDs. No exclamation marks. No "Please". No "Unable to".
</design_direction>

<findings_index>
## Design Areas (read these references during UI implementation)

| Area | Reference | Key decision |
|---|---|---|
| Tokens & motion | `references/foundation.md` | Sunset palette + Inter+JetBrains Mono + 4px spacing + 4 cubic-bezier curves |
| App chrome | `references/app-shell.md` | Sidebar (220px) with gradient brand mark + active-strip indicator. Topbar with ⌘K search. |
| Page layouts | `references/page-layouts.md` | Hero split-screen, action-first dashboard hero, list+side-panel, detail two-column+rail |
| Loading/empty/error | `references/state-patterns.md` | Per-source progress, explained empty + lightbulb, amber partial-failure with stale-row tinting |
| Visual language | `references/visual-language.md` | Severity glyphs+pills, SLA tiers, status workflow, provider identity, gradient CTAs |
| Interaction patterns | `references/interaction-patterns.md` | Side-panel drill-down, chip-bar filters, bulk-action bar, activity timeline, drag (deferred) |
| Copy & voice | `references/copy-voice.md` | Peer tone, sentence case, mono for paths, no "please", error-state specificity |

## Theme

`sources/themes/sunset.css` — the canonical CSS variable theme. Every variable is documented in `foundation.md`. Production should consume this verbatim (renamed to whatever the tailwind/CSS-modules convention is).

## Source Files

`sources/NNN-sketch-name/` — original HTML mockups + README per sketch. Open in a browser to see the validated interactions inline. **Production implementations should reproduce these visually, not deviate stylistically.**

| Sketch | Surface | Winner |
|---|---|---|
| 001-login-sunset | `/login` | A · Split-screen |
| 002-dashboard-sunset | `/dashboard` | B · Action-first hero |
| 003-vulnerabilities-sunset | `/vulnerabilities` | C · Chip bar + side panel |
| 004-states-sunset | Empty / Loading / Error | All 3 patterns; C (error) is the lead |
| 005-asset-detail-sunset | `/assets/[id]` | B · Two-col + metadata rail with ring |
| 006-tickets-sunset | `/tickets` | A (list) + B (detail page inherits asset-detail pattern); C kanban deferred as future Board view |
</findings_index>

<usage_during_build>
## When building UI in this project

1. **Read `foundation.md` first** — every screen consumes these tokens. Don't hand-pick hex values. Don't substitute fonts.
2. **Read the relevant layout pattern** from `page-layouts.md`. Don't invent new layouts.
3. **Read `visual-language.md` for any element with color** — severity, status, SLA, provider chips all have defined treatments. Use them; don't recolor.
4. **Read `state-patterns.md` before shipping any screen.** Empty/loading/error states are mandatory — the v1 audit flagged their absence as the top pain point.
5. **Read `copy-voice.md` when writing any UI text.** Don't compose generic SaaS copy.
6. **When uncertain about a small detail**, open the relevant sketch HTML in `sources/` and see the validated pattern.

## What this skill does NOT contain

- Production component code (the sketches are throwaway HTML/inline CSS; production is React + Tailwind + shadcn-style primitives)
- Tailwind config or shadcn token wiring (that's a build-time mapping from `foundation.md`)
- Tests, a11y audits, performance budgets — those are production concerns, not design concerns
- Backend / API decisions
- Mobile bottom-nav, drag-and-drop kanban, light theme — deferred (see `state-patterns.md` "deferred" notes)
</usage_during_build>

<metadata>
## Processed Sketches

- 001-login-sunset
- 002-dashboard-sunset
- 003-vulnerabilities-sunset
- 004-states-sunset
- 005-asset-detail-sunset
- 006-tickets-sunset

## Total decisions captured: 43 (D-01..D-43, see `.planning/sketches/MANIFEST.md`)
</metadata>
