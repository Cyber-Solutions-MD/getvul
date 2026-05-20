---
sketch: 002
name: dashboard-sunset
question: "Which information hierarchy answers 'what should I work on right now?' best — and does sunset palette + restrained polish scale to a data-heavy screen?"
winner: "B"
tags: [dashboard, layout, hierarchy, navigation-shell]
---

# Sketch 002: Dashboard — Sunset Palette

## Design Question

The v1 dashboard has 12+ stat tiles, 7 chart blocks, and an Executive Report tab. Per the redesign direction, less is more. Three variants test **what to put above the fold** when the analyst's actual question is "what should I work on right now?"

Also tests:
- Does the sunset palette scale from a hero login to a data-heavy screen, or does the warm gradient fight with severity colors (red/orange/yellow)?
- Does the persistent UI shell (sidebar + topbar) feel like Wiz/Linear or like a 2014 admin template?
- Does the gradient CTA still feel right as a recurring element, or does it overstay its welcome?

## How to View

```
open .planning/sketches/002-dashboard-sunset/index.html
```

Tab through the three variants. Same data in all three; only the **information hierarchy** differs.

## Variants

- **A — Stat-grid hero** — Traditional SaaS dashboard. Title + greeting line at top, 4 stat cards in a row, then chart + triage list side-by-side, activity feed full-width below. Familiar pattern, scannable. Most "Wiz-like."

- **B — Action-first hero** — A single hero card replaces the stat grid: "3 critical CVEs need your eyes" with a pulsing dot and a primary CTA "Start triage." Stats are demoted to a thin strip beneath. Activity moves to a right sidebar. Best for analysts who open the dashboard to *do* something, not to look at numbers.

- **C — Workspace 2-col** — Asymmetric split: left column is the workflow side (top-5 triage + activity feed), right column is the metrics side (4 mini-stats + chart). Greeting reads "Good morning, Ana" with the day's headline below. Most "Linear/Cursor" feel — treats the dashboard as a workspace, not a report.

All three share: same sidebar nav (with gradient brand mark + brand-strip active indicator), same topbar (search ⌘K + bell/help/avatar), same 4 stat values, same 30-day trend chart with severity stacks, same Top-5 triage list (with Unicode severity glyphs ■ ▲ ◆), same activity feed.

## What to Look For

- **First glance:** which one tells you "you should do X right now" the fastest?
- **Information hierarchy:** does the most urgent number visually dominate, or does it compete?
- **Severity color reads:** does red/orange/yellow on the warm-palette base feel clear, or does it muddy?
- **Gradient CTA frequency:** how does the pink→violet→amber button feel as a recurring element across the page? Distracting or anchoring?
- **Sidebar accent:** the active nav item has a gradient strip on its left edge with a glow. Subtle or showy?
- **Stat-card value gradient:** in A and C, the "Critical · open" stat has a gradient-text value (red→orange). Effective signal or gimmicky?
- **Mobile collapse (375):** sidebar hides, stats collapse to 2 cols. Which variant survives best?
- **Hover the trend chart bars** — they nudge up a touch on hover.

## Open variables

- Should there be a date / "last updated" stamp anywhere visible?
- Should the activity feed include avatars or just icons?
- The "today's queue" CTA is hypothetical — does that route exist or is it the triage list itself?
- Is the gradient brand mark too loud as a recurring element (login + sidebar + somewhere else)? Could simplify to a flat shield on the sidebar.
- Light theme: how does the sunset palette translate to a light surface? (Deferred — sketch only if/when light theme support is committed.)
