---
sketch: 004
name: states-sunset
question: "How should empty / loading / error states feel in the sunset world — and what's the right level of detail for each?"
winner: "all three needed"
tags: [states, empty, loading, error, patterns]
---

# Sketch 004: States — Empty / Loading / Error

## Design Question

The v1 audit ([REDESIGN_PLAN.md](../../../REDESIGN_PLAN.md) §3) flagged "no empty/loading/error states" as a top pain point. Generic spinners and raw API errors everywhere. Production code can't ship until these patterns are locked.

Unlike sketches 001–003, **the three variants here are not competing approaches** — they're three complementary states the production app needs. The question per state is: does this treatment work? Tweak feedback is welcome; "pick one" doesn't apply.

## How to View

```
open .planning/sketches/004-states-sunset/index.html
```

Three variants. Each shows `/vulnerabilities` in one state, with realistic content (real CVEs, real connector names, plausible error scenarios).

## Variants

### A — Loading

What's shown:
- Skeleton chip bar (gradient-tinted shimmer-pill placeholders for chips)
- Skeleton table rows (gradient shimmer on text widths, severity-pill placeholders)
- **Per-connector progress strip:** "Fetching from 3 of 4 sources… 312 found so far · this usually takes 2–3 seconds" + a row of connector chips with state (✓ Qualys 287 · ✓ AWS 18 · Tenable 7 [pulsing dot] · Rapid7 waiting)
- Sidebar count gets a thin skeleton ("Vulnerabilities …") so the user knows the count is loading too

The pattern: **progressive feedback, not a black screen.** The user sees what's loading, from where, and roughly how much has arrived. They can act on partial data (Qualys's 287 vulns are already shown if the table populates progressively).

### B — Empty (filtered to zero)

What's shown:
- Active filter chips remain visible above the empty card (so the user can see what they applied)
- Centered card with a sunset-gradient shield icon + glow + sparkles
- Headline: "Nothing matches all 5 filters"
- Body: explains *why* the empty state happened — the user applied a tight conjunction
- "Currently filtered by" summary inside the card listing every active chip
- Three CTAs: gradient "Clear all filters" + secondary "Include Medium severity" + secondary "Search all sources"
- A violet "lightbulb" hint at the bottom: "This is a sharp query. Save it as 'Hyperion KEV watch' — you'll be notified when anything matches." Turns the empty state into an *opportunity*, not a dead end.

The pattern: **explain the empty, offer a concrete escape, suggest a follow-up.** Never "no results" alone.

### C — Error (partial failure)

The realistic case for GetVul: not all 4 connectors fail at once — usually one of them goes down, the rest are fine. The UI has to communicate "you have partial data" clearly without crying wolf.

What's shown:
- Amber warning icon button in the topbar (small persistent indicator)
- Subtitle below the page title: `⚠ Partial data · 3 of 4 sources returned · 312 hidden`
- **Inline error banner** (amber-tinted): "Tenable connector is unreachable" + sub: last sync, HTTP code, retries, request ID + actions (View trace · Retry now)
- **Per-source status cards** (4-card row): Qualys/Rapid7/AWS show `ok` status; Tenable card is highlighted in red with status `503` and a "Retry → or view connector settings" link
- The table below shows **the data we DO have** — successful connectors' rows are normal; rows from stale Tenable cache are tinted amber with a `stale` pill on the source column
- Bottom of table: "Some results may be incomplete because Tenable hasn't responded since 2h 14m ago. Retry Tenable · view connector logs"

The pattern: **show what you have, mark what's stale, name what failed, offer a fix.** Never replace the screen with a generic error page when partial data is available.

## What to Look For

**Variant A (Loading):**
- Shimmer animation — too fast (anxious) / right / too slow (sleepy)?
- Per-connector progress chips — useful information or noise?
- Skeleton pill widths match real content widths (realistic preview)
- Sidebar count skeleton — communicates that nav counts are loading too

**Variant B (Empty):**
- Sunset-gradient icon with glow — fancy or appropriate?
- Filter summary inside the card — too redundant (chips are already above) or genuinely helpful?
- Three CTAs at three different levels (clear-all gradient / include-medium secondary / search-all secondary). Right number?
- The violet "save as filter" suggestion — clever or pushy?

**Variant C (Error):**
- Amber color (not red) for partial-failure — does that read right? Red would feel scarier; amber says "degraded, not down."
- 4 source cards in a row — informative or too much chrome?
- The stale-row treatment (amber row tint + `stale` pill on source) — does it draw enough attention without screaming?
- Topbar's persistent amber alert icon — should that be there all the time when any source is down, or only when the user is on a page affected by it?
- Request ID + HTTP code shown by default — helpful for support tickets, or jargon?

**All three:**
- Mobile (toggle 375) — sidebar hides; empty card centers; error banner stacks. Test each.
- Does the sunset palette make these states feel premium, or do the warm colors fight the urgency signals?

## Decisions to capture (from feedback)

If approved as-is, these become **D-26 through D-2X**:
- **D-26 (loading):** Skeleton rows + per-source progress strip. No black screens. Show partial data as it arrives.
- **D-27 (empty):** Centered card with gradient icon + explanation + 3-tier actions + opportunity hint (save as filter). Never just "0 results."
- **D-28 (error, partial):** Amber inline banner + per-source status cards + stale-tinted rows + always show what data we have.
- **D-29 (error, total):** Not sketched here — what if ALL sources fail? Deferred to a follow-up if needed.

## Deferred from this sketch

- **Total error state** (all 4 sources fail) — different pattern: probably a full empty-card with retry. Worth a separate variant if the partial-failure pattern is approved.
- **First-time-ever empty state** (no connectors configured yet) — different from filtered-to-zero. Onboarding-flavored: "Connect a scanner to see your first vulnerabilities" + CTA to /connectors.
- **Snooze/dismissed empty** — when all critical items are snoozed. Friendly: "Quiet here. Nothing critical right now."
- **Toast notifications** for transient errors (connector retried successfully, etc.) — pattern not yet sketched.
- **Dashboard's empty state** — different shape. Hero card "0 critical CVEs need triage" should feel like a *win*, not a failure.
