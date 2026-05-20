# Phase 10: `/dashboard` - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-15
**Phase:** 10-dashboard
**Areas discussed:** Data fetching + state patterns; Chart implementation + bundle-split; Hero semantics; Activity feed mapping; Stat strip delta + SLA-at-risk; Top 5 to triage; Accessibility + motion; Primitive API shape; Sidebar count chips; Mobile breakpoints; Backend scope audit; Tab title dynamics; Error-state copy; Onboarding empty state; Header section above hero; Real-time updates; Performance budget; Initial render strategy; Test coverage floor; Telemetry; Keyboard shortcuts on dashboard; Snooze confirmation flow; Activity rail scroll; Time-zone display; Server-error retry policy; Cache lifecycle; Forced-colors + dark-only; Hero CTA arrangement + icons; Stat tile icons + delta arrow; Initial focus + print; Cross-tab sync; Error boundary; TanStack query-key convention; Range persistence

---

## Data fetching + state patterns

| Option | Description | Selected |
|---|---|---|
| TanStack Query v5 | v2.0 client data layer; ~13 kB; mutations + cache + dedup; sets convention for Phases 11–14 | ✓ |
| Keep useEffect + Promise.all | v1 pattern; no new deps; each screen owns its own state | |
| SWR | Lighter than TanStack; less feature-rich for mutations | |

| URL-synced `?range=30d` | Reload preserves range; anticipates Phase 11 URL-sync | ✓ |
| Component state only | useState in chart; reload resets | |

| Inline-minimal in Phase 10, replace in Phase 11 | Ship without dependency on unbuilt Phase 11 primitives | ✓ |
| Pull Phase 11 primitives forward | Balloons Phase 10 scope; design risk before list exists | |
| Single full-page loader (v1) | Cheap; bad UX on slow networks | |

| Render what we have, dim what failed + inline banner | `Promise.allSettled`-style independent queries | ✓ |
| All-or-nothing | Simpler; hides recoverable data | |

| 60s/30s staleTime | 60s for /stats /overview /trends; 30s for /notifications | ✓ |
| 0 staleTime (always refetch) | Most aggressive; overkill for ops tool | |
| 5min / 60s | Conservative; less "alive" feeling | |

| Refetch on window focus + on mount (TanStack defaults) | Standard for live ops dashboard | ✓ |
| Refetch on mount only | Less live | |

| QueryClient at `(authed)/layout.tsx` | Single shared client across authed routes; /login excluded | ✓ |
| QueryClient at root `app/layout.tsx` | Adds dead code to /login bundle | |

---

## Chart implementation + bundle-split

| recharts (already in deps) | Zero new deps; React-native API; ~115 kB → route-split | ✓ |
| Tremor | Built on recharts; layer on top with awkward token escapes | |
| Visx (Airbnb / d3) | Lower-level; more code; flexibility we don't need yet | |

| Thin `TrendChart` primitive | Wraps recharts behind typed API; future-swap-friendly; listed in /dev/primitives | ✓ |
| Inline recharts in page | recharts API leaks into page | |

| Dynamic import + ChartSkeleton fallback | `next/dynamic` ssr:false; route-split satisfied literally | ✓ |
| Static import + Next chunk splitting | Risk: recharts ends up in shared chunks | |

| Custom Tooltip + segmented Toggle (URL-synced) | Sunset chrome tooltip; range toggle wired to `?range=`; honors reduce-motion | ✓ |
| Default recharts tooltip + plain buttons | Off-brand | |

| Extend /trends backend with severity_trends | Single round-trip; shape matches chart 1:1 | ✓ |
| Use existing DailySnapshot table | Depends on what snapshot captures | |
| Compute client-side from /vulnerabilities | Bad scaling on big tenants | |

| `var(--color-severity-*)` per visual-language.md | Matches severity pills elsewhere; survives grayscale via glyph + stack-order | ✓ |
| Custom chart-tuned colors | Breaks design-system promise | |

| Auto y-max (nearest 10 above peak) + 4 gridlines | Standard for ops dashboard | ✓ |
| Fixed y-max 100 | Wastes space for low-volume; clips for high | |
| Log scale | Confusing for non-technical viewers | |

---

## Hero semantics

| Open + Critical, ignoring snoozes | Simplest defensible definition | ✓ |
| Open + Critical-or-High + KEV + active exploit | Tighter but unfindable from number alone | |
| Open + KEV-listed (any severity) | Strongest "act now" signal; misses non-KEV criticals | |

| Highest-CVSS open-critical with host + path | Matches copy-voice exemplar verbatim | ✓ |
| Count breakdown by source | Doesn't drive action | |
| Worst SLA-breached host | Mixes two concerns | |

| `/dashboard/vulnerabilities?status=open&severity=critical` | Lands in v2 vuln table with same filter | ✓ |
| Named saved-filter (`?filter=todays-triage`) | Couples Phase 10 to Phase 11 feature | |

| Open-critical = 0 | Symmetrical with headline definition | ✓ |
| Open-critical = 0 AND open-high = 0 | Higher bar; rarely hit | |
| Open-critical = 0 (excluding snoozed) | Same as headline definition above | |

| Snooze top sub-line CVE for 1h | Single-click, action-oriented | ✓ |
| Snooze ALL open-critical for 1h | High blast radius | |
| Open a snooze picker | Adds clicks; better as future enhancement | |
| Hide entirely from Phase 10 | Reduces hero impact | |

| Critical-red dot when count > 0; green when 0 | Reinforces headline state; reduce-motion = color only | ✓ |
| Always red, animates only when count > 0 | Dissonant in quiet-win | |
| Tied to highest severity present | Too subtle for a small dot | |

| `1 critical CVE needs your eyes` / `N critical CVEs need your eyes` | Grammar matches count | ✓ |
| Always plural with `(s)` | Easier i18n; less polished | |

| Line-clamp 2 lines + ellipsis, mono intact | Width-stable; hover tooltip for full | ✓ |
| Single line + horizontal scroll | Violates D-41 no-h-scroll | |
| Wrap freely | Bad for predictable layout | |

---

## Activity feed mapping

| critical→pink, sla→amber, sync→violet, risk→success | Matches sunset family + neutral system colors | ✓ |
| All same severity-tied color | Loses scan-ability | |
| Each category gets a gradient mark | Reads busy in narrow rail | |

| Lucide ShieldAlert/Clock/WifiOff/TrendingUp | Already a dep; semantically obvious | ✓ |
| Generic Bell icon | Wall of identical rows | |

| 0 events: quiet copy + 1–4 events render as-is | No padding placeholders | ✓ |
| Always pad to 5 with placeholders | Confusing | |
| Hide sidebar when 0 | Inconsistent layout | |

| Navigate to context per category | CVE drill / ticket / connectors / asset | ✓ |
| Rows non-clickable | Read-only feed | |

---

## Stat strip delta + SLA-at-risk

| Backend computes from DailySnapshot; returns `{value, delta, delta_direction}` | Single source of truth | ✓ |
| Frontend computes delta from /trends | Mixes concerns; couples to chart endpoint | |
| Hide delta until backend ready | Less than SC #2 specifies | |

| Within 25% of SLA deadline, not yet breached | Scales per severity | ✓ |
| Within fixed 48h of breach | Doesn't scale across severities | |
| Open + {Critical, High} + due ≤ 7d | Severity-gated; misses Med/Low cases | |

| Direction-aware: red ▲ for bad direction, green ▼ for good | Per-tile semantic | ✓ |
| Neutral gray deltas | Less expressive | |
| Always green up, red down | Wrong for ops (more criticals up = bad) | |

---

## Top 5 to triage

| KEV → CVSS desc → SLA-urgency tiebreak | Matches analyst triage intuition; stable | ✓ |
| Pure CVSS desc | Misses KEV signal | |
| Risk-score weighted (CVSS × asset × KEV) | Sophisticated; less interpretable | |

| Reuse `/api/v1/vulnerabilities?sort=triage&limit=5` | Same pattern Phase 11 needs | ✓ |
| New /api/v1/dashboard/top-triage | Diverges from Phase 11 list pattern | |
| Filter /stats response | Wrong fit (list not aggregate) | |

| `/dashboard/vulnerabilities?cve=…&open=drill` | Phase 11 honors URL convention | ✓ |
| Disable click in Phase 10 | Less satisfying | |
| Inline expand in card | Conflicts with Phase 11 drill panel | |

| Pad with next-highest severity (High → Medium → Low) | Always 5 rows; visually balanced | ✓ |
| Show only what exists + note | Card height shifts | |
| Show only critical even if <5 | Card height shifts | |

---

## Accessibility + motion

| sr-only h1 + h2 per section | Predictable section landmarks; stable | ✓ |
| h1 = hero headline | Couples h1 to data; quiet-win h1 changes | |

| <main> + <aside> + <section aria-labelledby> | Builds on Phase 9 shell | ✓ |
| Generic <div> | Misses easy a11y win | |

| sr-only text summary + accessible <table> | SR users navigate the data | ✓ |
| Just a high-level sr-only summary | Less navigable | |
| No accessible alternative | Fails WCAG 1.1.1 | |

| Pulsing dot + chart bar-rise + tile count-up | Each primitive owns its own reduce-motion check | ✓ |
| Only pulsing dot needs special handling | Misses bar-rise keyframes | |

---

## Primitive API shape

| `<Card variant padding>` with subcomponents | shadcn convention; one primitive, three variants | ✓ |
| Three separate primitives | More files; less composable | |
| No-prop Card; variants at call site | Drift-prone | |

| `<Stat label value delta deltaDirection deltaIsGood hint? icon?>` | Typed; reduce-motion count-up internal | ✓ |
| Headless Stat composition | Verbose; drift-prone | |

| `<StatStrip>{children}</StatStrip>` with auto-grid | Caller doesn't manage breakpoints | ✓ |
| `<StatStrip columns={4}>` | Inconsistent across screens | |

| `<ActivityFeed items emptyCopy?>` | Caller owns data | ✓ |
| Internal `useNotifications` hook | Couples primitive to source | |

---

## Sidebar count chips

| Vulnerabilities (open), Assets (total), Tickets (open) | Matches analyst mental model | ✓ |
| Vulnerabilities only | Tightest signal; less reference | |
| All seven nav items | Sidebar becomes busy | |

| Add counts to /stats; AppShell consumes | Shared cache; no new endpoint | ✓ |
| Separate /shell-counts endpoint | Extra request | |
| Each chip queries independently | No shared cache | |

| Dash `—` per D-35 until loaded; on error leave dash | Stable, no shift | ✓ |
| Skeleton bar | Animation in low-attention area | |
| Hide chip until loaded | Layout shift | |

---

## Mobile breakpoint behavior

| Stack activity below main content at <1280px | Predictable single threshold | ✓ |
| Hide activity entirely <1280px | Loses surface | |
| Collapsible drawer | New primitive needed | |

| 4 cols desktop → 2 cols tablet → 1 col mobile | Inherits StatStrip auto-grid | ✓ |
| Always 4 cols (h-scroll) | Breaks D-41 | |
| Always 2 cols | Wastes desktop | |

| Resize to viewport; reduce gridlines on mobile | Recharts ResponsiveContainer | ✓ |
| Collapse to 7-day on mobile | Forces range change | |
| Hide chart entirely | Loses key visual | |

| Same 5 rows; wrap to 2 lines | Severity glyph + CVE stay on row 1 | ✓ |
| Show only Top 3 on mobile | Hides actionable rows | |

---

## Backend scope audit

| List complete — lock five changes | Five derived from previous answers | ✓ |
| Hide changes behind single /dashboard endpoint | Duplication risk | |
| Split delta + top_vuln into /dashboard, leave /stats alone | Three endpoints | |

| One backend wave first; frontend after | Eliminates mock-data risk | ✓ |
| Frontend first against mocks; backend last | Mock drift risk | |
| Interleaved | More coordination overhead | |

---

## Tab title dynamics

| Dynamic `(N) Dashboard · GetVul` when N>0, else `Dashboard · GetVul` | Linear/GitHub-style; scannable when backgrounded | ✓ |
| Static `Dashboard · GetVul` | Loses count signal | |
| Pipe / em-dash separator | Inconsistent with middle-dot convention | |

---

## Error-state copy

| Inline error block in hero with HTTP code + request ID + Retry-now | Per copy-voice.md error pattern | ✓ |
| Show chrome but blank hero | Confusing loading vs failed | |
| Toast + blank hero | Toast is for ephemeral, not persistent | |

| Inline within failed card; rest renders normally | Spatial cue preserved | ✓ |
| Single page-level banner | Loses spatial cue | |
| Quiet failure | Hides backend instability | |

| Toasts only for user-initiated events | Ephemeral = action feedback only | ✓ |
| Toast for all errors including background | Spam risk | |
| Skip toasts entirely | No action feedback | |

---

## Onboarding empty state

| Dedicated `Connect a scanner` panel filling page | Single CTA; honest | ✓ |
| Render empty primitives with `—` | Reads broken | |
| Quiet-win style with welcome copy | Mismatched signal | |

| Backend flag `onboarding_state: 'no_scanners' \| 'no_data_yet' \| 'ready'` | Three distinct screens map cleanly | ✓ |
| Frontend derives from counts | Misses mid-state | |

| `Your first sync is in progress` with timestamp + Refresh | Honest about state | ✓ |
| Treat as no_scanners | User confused after connecting | |

---

## Header section + page actions

| Hero IS the header | Action-first; saves vertical space | ✓ |
| Small page-head with title + actions above hero | Conventional; pushes hero down | |

| No page actions in topbar — hero CTAs are it | Stays generic chrome | ✓ |
| Export / Refresh buttons in topbar | v1 pattern; not in v2 sketches | |

---

## Real-time updates

| Polling-only via TanStack | Honors PROJECT.md Out-of-Scope | ✓ |
| SSE for activity only | Backend infra; out of scope | |
| Periodic refetchInterval | More backend load | |

---

## Performance budget

| 180 kB First-Load | /login = 145 kB + TanStack + headroom for new primitives | ✓ |
| Match /login 145 kB | Strict; tough without rebundling | |
| Soft target with no ceiling | Phase 15 catches regressions | |

| Soft Vitals targets here; Phase 15 gates | Awareness without halting on regression | ✓ |
| Defer entirely to Phase 15 | Risk: chart animation tanks INP | |

| npm run build column captured in verification log | Phase 9 convention | ✓ |
| CI fail-on-regression check | PROD-02 territory | |

---

## Initial render strategy

| Full client component | Matches Phase 9; auth in localStorage | ✓ |
| RSC shell + client islands | Auth dance with localStorage | |
| Server actions + cookie sessions | Migration phase, not Phase 10 | |

| Skeleton hero + strip + chart, top-down arrival | Reduces perceived latency | ✓ |
| Single page-wide spinner (v1) | Slow networks feel awful | |
| Stale-while-revalidate from cache | First visit still needs skeleton | |

---

## Test coverage floor

| Per-primitive .test.tsx with axe + dashboard.test.tsx integration | Same shape as Phase 9 D-30 | ✓ |
| Primitive tests only | Misses integration | |
| Page-level only | Inverts Phase 9 convention | |

| pytest per endpoint extension | Matches v1.0 Phase 1 pattern | ✓ |
| One happy-path test for /stats overall | Misses per-field guarantees | |
| No backend tests | Coverage gap | |

| /dev/primitives gets new entries; no Storybook | REQUIREMENTS-v2 out-of-scope | ✓ |
| Add Storybook | Reverses out-of-scope decision | |

---

## Telemetry

| Skip telemetry in Phase 10 | No provider in deps; not in REQUIREMENTS | ✓ |
| Repurpose /audit-events for product events | Dilutes security signal | |
| Add PostHog | New dep + privacy review for self-hosted | |

---

## Keyboard shortcuts

| None in Phase 10; ⌘K stays visual-scaffold (D-37) | Future palette phase decides | ✓ |
| Add R / 1 / 2 / 3 shortcuts | Precedent not thought through | |
| Wire ⌘K | Scope creep | |

---

## Snooze 1h confirmation flow

| Immediate fire-and-forget + Undo toast | Modern pattern (Gmail/Linear) | ✓ |
| Confirm modal first | Heavy for reversible action | |
| Inline morphing button | New primitive needed | |

| 8s undo window | Standard (5-10s) | ✓ |
| 30s | Toast lingers, distracts | |
| 3s with no undo | Misclick unrecoverable | |

---

## Activity rail scroll behavior

| Sticky right rail, scrolls with page | Simple; no second scrollbar | ✓ |
| Sticky-positioned with own scrollbar | Second scrollbar feels off for 5 events | |
| Limit to exactly 5; never overflow | Already limit=5; removes question | |

| Section heading + 5 rows full-width when stacked | Heading orients; SR landmark | ✓ |
| Hide section heading | Loses landmark | |

---

## Time-zone display

| Browser-local everywhere | Single predictable rule | ✓ |
| UTC for everything | Confusing day boundaries | |
| Tenant-configured TZ | Scope creep | |

| Day 30 is today (rightmost = today, may be partial) | Natural reading | ✓ |
| Day 30 is yesterday (full days only) | Misses today's data | |

---

## Server-error retry policy

| Retry 1× on 5xx for /stats + dashboard-tiles; 0 elsewhere | Most-visible queries get one auto-retry | ✓ |
| Default 3 retries on 5xx | Hides backend issues | |
| 0 retries; user clicks Retry-now | Annoying for transient blips | |

| Silent token refresh on 401; redirect to /login on refresh-fail | Uses AUTH-03 refresh token | ✓ |
| Immediate redirect on any 401 | Loses session continuity | |

---

## Cache lifecycle on logout/login

| queryClient.clear() from useAuth().logout() | Per-tenant isolation | ✓ |
| Default GC time handles it | Race window | |
| Clear on tenant change only | Overengineering | |

| Invalidate /stats + tiles + /vulnerabilities on snooze success | Hero refetches naturally | ✓ |
| Optimistic update | Complex; future upgrade | |
| Full window reload | Wastes SPA model | |

---

## Forced-colors + dark-only

| Graceful: system colors win for surfaces/borders/text; severity glyphs stay | Pragmatic WCAG 1.4.8 | ✓ |
| Block with forced-color-adjust: none | Fails WCAG | |
| Defer to Phase 15 | Cheap to do now | |

| Dark-only visually; light architecture disabled in UserChip | Phase 9 WR-03 mitigation stands | ✓ |
| Try to light-mode-polish new primitives | Pulls D-06 partially forward; risk | |

---

## Hero CTA arrangement + icons

| Side-by-side, triage left (primary), snooze right; stack <640px | Primary→secondary reading order | ✓ |
| Stacked vertically always | Wastes desktop space | |
| Side-by-side, secondary first | Reverses convention | |

| Zap on Start triage; Clock on Snooze 1h | Matches copy-voice exemplar | ✓ |
| No icons | Less aligned with system | |
| Generic ArrowRight | Less semantic | |

---

## Stat tile icons + delta arrow

| Each tile gets muted lucide icon top-right | De-emphasized; number stays hero | ✓ |
| Numeric-only tiles | Loses scannability | |
| Sunset-gradient-tinted icons | Visually loud | |

| `▲`/`▼` unicode glyph + signed number + `from yesterday` | Per visual-language.md | ✓ |
| Lucide TrendingUp/TrendingDown | Heavier in dense tile | |

---

## Initial focus + Print

| No programmatic focus; browser default on <body> | Matches Phase 9; SR-friendly | ✓ |
| Auto-focus Start triage | Aggressive; accidental Enter risk | |
| Auto-focus h1 with tabIndex=-1 | Weak precedent | |

| Skip print stylesheet | EXP-01 covers PDF; no clear ask | ✓ |
| Add minimal @media print rules | Hard to test, no customer ask | |

---

## Cross-tab sync

| Rely on refetch-on-focus from Area 1 | No new infra; ≤30-60s lag acceptable | ✓ |
| BroadcastChannel for instant sync | ~30 lines code; future upgrade | |
| localStorage events | Older pattern | |

---

## Error boundary

| Per-section ErrorBoundary primitive | React 19 native; crash isolation | ✓ |
| Single page-level boundary | Whole page crashes together | |
| No boundaries; let crashes propagate | Worst UX | |

---

## TanStack query-key convention

| Domain-first: `['vulnerabilities', 'stats']`, `['notifications', 'recent', {limit}]` | Bulk-invalidate by domain | ✓ |
| Flat strings | Harder to bulk-invalidate | |
| Versioned with v1 prefix | Over-engineered | |

---

## Range toggle persistence

| URL is only source of truth | Reload-with-URL works; bookmarkable | ✓ |
| localStorage fallback when URL empty | Diverges bookmarked vs typed | |

---

## Claude's Discretion

- Exact spacing rhythm between hero / strip / chart / top-5 — consume `--space-*` tokens
- Specific gradient stops for hero CTA hover state — consume `--gradient-sunset`
- Skeleton shape details (height, radius, shimmer) — within `--motion-*` + `--radius-*`
- Stat tile internal layout (label-on-top vs label-on-side)
- Pulse-urgency keyframe specifics — defined in Phase 9 D-15

## Deferred Ideas

See `10-CONTEXT.md` `<deferred>` section for the full list (BroadcastChannel cross-tab sync; optimistic snooze; per-user preferences; CI bundle-size gating; Storybook; print stylesheet; telemetry; tenant-configured TZ; real-time push; light-theme polish; Top-5 inline expansion; keyboard shortcut layer; mobile-replacement nav).
