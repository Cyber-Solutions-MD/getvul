# Sketch Wrap-Up Summary

**Date:** 2026-05-12
**Sketches processed:** 6
**Design areas:** 7
**Skill output:** `./.claude/skills/sketch-findings-getvul/`

## Included Sketches

| # | Name | Winner | Design Area |
|---|------|--------|-------------|
| 001 | login-sunset | A · Split-screen | Page layouts (hero) |
| 002 | dashboard-sunset | B · Action-first hero | Page layouts (hero), App shell |
| 003 | vulnerabilities-sunset | C · Chip bar + side panel | Page layouts (list), Interaction patterns |
| 004 | states-sunset | All 3 patterns; C (error) is lead | State patterns |
| 005 | asset-detail-sunset | B · Two-col + metadata rail | Page layouts (detail), Visual language (risk ring) |
| 006 | tickets-sunset | A (list) + B (detail) + C deferred | Page layouts (list/detail), Visual language (providers) |

## Excluded Sketches

None — all 6 included.

## Design Direction (Consolidated)

GetVul v2.0 is a **Wiz-inspired premium SaaS** redesign in a **sunset / dusk palette** — pink → violet → amber accents on deep plum / near-black backgrounds. The aesthetic is "warmer than Wiz/Linear/Stripe" (which all sit in the blue-purple-cyan range) while still feeling premium. Polish is **restrained**: gradients and glows are reserved for the CTA, brand mark, active nav strip, and severity indicators — everything else is clean dark surfaces with subtle borders.

Information density is **lower than Wiz** by intent. Each screen answers a single primary question:
- `/dashboard` — "what should I do now?"
- `/vulnerabilities` — "what vulns match my filters, and what's behind this row?"
- `/assets/[id]` — "who owns this and what's wrong with it?"
- `/tickets` — "what's the state of remediation work?"

Persistent shell across all authenticated screens: 220px sidebar (gradient brand mark + section labels + gradient-strip active indicator) + topbar (⌘K search + bell + help + avatar chip). Login is the only authenticated-adjacent surface with its own layout (split-screen hero).

## Key Decisions

**Layout:**
- Login uses split-screen with gradient mesh visual + clean form panel
- Dashboard hero is action-first: pulsing eyebrow + numeric headline + CTA, NOT a stat grid
- List routes use chip-bar filters + side-panel drill-down (no persistent left drawer)
- Detail pages use two-column with sticky right metadata rail (220px main + 340px rail)
- Mobile collapses sidebar to hamburger and tables to card view

**Palette & Type:**
- `--gradient-sunset: linear-gradient(135deg, #EC4899 0%, #A78BFA 50%, #F59E0B 100%)`
- Body: Inter. Identifiers (CVE, hostnames, scores): JetBrains Mono.
- Severity colors locked: critical red, high orange, medium yellow, low lavender, info blue
- Status colors deliberately different from severity: open violet, in-progress amber, completed green

**Visual language:**
- Severity uses three-axis encoding: color + Unicode glyph (■ ▲ ◆ ○ □) + size
- SLA tiered: overdue red / soon amber / ok green, monospace, right-aligned
- Provider identity (Jira/Asana/GitHub) uses gradient marks + tinted chips, not real logos
- Risk score visualization: circular gradient ring with center number + breakdown rows
- Single gradient CTA repeats as the primary action across all screens

**State patterns (mandatory):**
- Loading: skeleton screens + per-source progress strip ("3 of 4 sources · 312 found")
- Empty: explained empty + 3-tier CTAs (clear / broaden one axis / broaden everything) + lightbulb suggestion
- Error (partial failure): amber inline banner with HTTP code + request ID + per-source status cards + stale-row tinting

**Voice:**
- Peer tone (Linear / Vercel / GitHub family)
- Sentence case, no exclamation marks, no "please"
- Specific errors with HTTP code + request ID by default
- Mono for any value resembling a path or terminal output

## Open / Deferred

- Total-failure error state (all sources down) — different from partial-failure
- First-time-empty / no-connectors-yet onboarding state
- Light theme (sunset translates to dark natively; light variant untested)
- Mobile bottom-nav (sidebar → hamburger pattern OK; bottom-nav deferred to a dedicated sketch)
- Charts beyond severity bar chart (sankey for connector health, ring for risk distribution)
- Drag-and-drop kanban (deferred as future "Board view" toggle on `/tickets`)
- Connector onboarding wizard (multi-step form pattern not yet validated)
- Settings page (sidebar-of-categories pattern not yet validated)
- Page transitions / route-change motion
- Toast notifications

## Routing

Production agents auto-load `sketch-findings-getvul` (via CLAUDE.md routing line) when building UI on this project. Reference files in `references/` are the contract; sketches in `sources/` are inspectable for visual fidelity. Tokens come from `sources/themes/sunset.css`.

The seed `wiz-sunset-redesign-milestone.md` is now triggered — ready to plan the milestone via `/gsd-new-milestone v2.0 UI/UX Redesign`.
