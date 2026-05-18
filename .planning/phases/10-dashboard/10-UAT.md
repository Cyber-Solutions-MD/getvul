---
status: complete
phase: 10-dashboard
source: [10-01-SUMMARY.md, 10-02-SUMMARY.md, 10-03-SUMMARY.md, 10-04-SUMMARY.md, 10-05-SUMMARY.md, 10-06-SUMMARY.md]
started: 2026-05-18T11:00:00Z
updated: 2026-05-18T15:45:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Dashboard loads in action mode
expected: |
  Navigate to /dashboard (signed in, with seeded data containing ≥1 open critical CVE).
  Hero renders at top with: a small pulsing red dot + "Action required" eyebrow,
  a large headline like "3 critical CVEs need your eyes" (singular: "1 critical CVE needs your eyes"),
  a sub-line "Top one is on <host> — <path>, CVSS <n>, exploited in the wild.",
  and two CTAs side-by-side: "Start triage" (sunset gradient) and "Snooze 1h" (secondary).
result: pass
notes: |
  User screenshot confirmed: "46 critical CVEs need your eyes" headline, sub-line
  "Top one is on SRV-WIN-FS01 — PAN-OS, CVSS 10.0, exploited in the wild.", both CTAs
  rendered correctly. Adjacent Activity Rail crashed but that's logged under Test 5.

### 2. Stat strip renders 4 tiles with direction-aware deltas
expected: |
  Below the hero, 4 stat tiles render in a row at ≥1280px (2-col at tablet, 1-col on mobile):
  Critical · open, SLA · at risk, CISA KEV, MTTR · 30d. Each shows a value, a small icon
  in the corner (ShieldAlert/Clock/Flame/TrendingDown), and a delta row reading
  "▲ +N from yesterday" in red ("up is bad") or "▼ -N from yesterday" in green ("down is good").
  The MTTR · 30d tile shows the value but NO delta row (server ships delta=null for that tile).
  If a tile has delta=null (fresh tenant), it shows "Δ —" instead.
result: pass

### 3. Trend chart renders + range toggle works
expected: |
  Below the stat strip, a "30-day vulnerability trend" section renders a stacked bar chart
  with critical/high/medium/low severity colors. A range toggle (7d / 30d / 90d) sits at the top right;
  clicking 90d updates the URL to ?range=90d AND swaps the chart data. The page DOES NOT reload.
  Reload the page with ?range=90d in the URL — chart loads at 90d directly.
result: pass

### 4. Top 5 to triage card
expected: |
  A "Top 5 to triage" card renders 5 rows. Each row has:
  a severity glyph prefix (■ critical / ▲ high / ◆ medium / ○ low) in the corresponding color,
  a mono CVE id (e.g. CVE-2024-1234), a truncated host, the CVSS score, and an SLA pill
  ("4h left" amber if <72h, "Breached 12h ago" red if past, "8d left" green if healthy).
  Clicking a row navigates to /dashboard/vulnerabilities?cve=…&open=drill (stub OK — Phase 11 honors ?open=drill).
result: pass

### 5. Activity rail in right sidebar
expected: |
  At ≥1280px width: a 340px sidebar on the right of the main column shows recent activity events
  (last 5 from /api/v1/notifications). Each event has a sunset-tinted category icon
  (pink ShieldAlert for new critical / amber Clock for SLA breach / violet WifiOff for sync fail /
  green TrendingDown for risk change), title, and "Xm ago"/"Xh ago" relative time.
  Resize the window below 1280px — rail collapses below the main column as a full-width section
  with a visible "Recent activity" h2 heading.
result: pass
notes: |
  First observation during Test 1 was an ErrorBoundary fallback:
  "Activity unavailable. HTTP crash · Request ID Value need to be finite number for Intl. · Retry now"
  Root cause: schema mismatch (backend created_at/message vs frontend occurred_at/body) + missing
  NaN guard in relativeTime(). Fixed inline by adding `select` adapter to useRecentNotifications
  and a Number.isFinite guard in ActivityFeed.relativeTime(). User re-verified — rail renders.

### 6. Quiet-win path (criticalOpen = 0)
expected: |
  Snooze, suppress, or remediate every open critical CVE so dashboard_tiles.critical_open.value = 0.
  Reload /dashboard. The hero swaps: green dot + "Status" eyebrow + headline "Nothing critical right now".
  NO Snooze CTA is rendered (no top vuln to snooze). The rest of the dashboard (stat strip, trend, top5, rail) still renders.
result: pass

### 7. Snooze flow with Undo toast
expected: |
  In action mode (criticalOpen > 0), click "Snooze 1h". Top-right toast appears reading
  "Snoozed CVE-YYYY-NNNN for 1h" with an "Undo" button. The button stays visible for ~8 seconds.
  Without clicking Undo: the top vuln updates (hero may swap to a different vuln, or quiet-win
  if it was the last critical). With clicking Undo: the snooze is reversed; the vuln reappears
  in the hero / top-5 on next data refresh.
result: pass

### 8. Onboarding state (no_scanners) swaps whole dashboard
expected: |
  Test in a tenant with NO scanners connected (or temporarily disable all scanners).
  /dashboard replaces the whole hero+stats+trend+top5+rail composition with a single
  centered panel: "No scanners connected yet" heading + body copy + a "Connect a scanner"
  gradient CTA linking to /dashboard/connectors.
result: pass

### 9. Sidebar nav-chip counts populate from /stats
expected: |
  In the left sidebar (≥1000px viewport), three nav items carry chip counts:
  Vulnerabilities (open count), Assets (total count), Tickets (open count).
  On initial load: chips briefly show "—" (em-dash) while /stats is fetching, then swap to numbers.
  Open the Network tab and reload /dashboard: /api/v1/vulnerabilities/stats is called EXACTLY ONCE
  (shared cache between Sidebar and Dashboard page — verified by the test suite, but worth a sanity check).
result: pass

### 10. Tab title updates with critical count
expected: |
  Browser tab title reads "(3) Dashboard · GetVul" when critical_open.value > 0
  (count matches the hero headline). When the count is 0 or onboarding state matches,
  it reads "Dashboard · GetVul" (no count prefix). Navigating away from /dashboard restores
  the previous page's title.
result: pass

## Summary

total: 10
passed: 10
issues: 0
pending: 0
skipped: 0

## Gaps

- truth: "Activity rail renders the last 5 events from /api/v1/notifications with title + category icon + relative-time"
  status: resolved
  reason: "Fixed inline during UAT: useRecentNotifications now adapts backend payload (created_at→occurred_at, message→body, category enum normalized); relativeTime() guards Number.isFinite and returns em-dash on bad input. Dashboard test mocks remain ideal-shape — note for future: should also exercise the adapter."
  severity: blocker
  test: 5
  resolved_in_commits: [b77f497]

- truth: "Sidebar Connectors link routes to an existing page"
  status: resolved
  reason: "Phase 9's D-36 baked /dashboard/integrations into the sidebar Connectors href, but the v1 route directory is /dashboard/connectors — clicking the sidebar item produced a 404. Caught during Phase 10 UAT (user navigating to manage scanners for Test 8 onboarding setup). Plan 10-06 preserved the wrong href verbatim. Fixed inline: sidebar.tsx now points to /dashboard/connectors; sidebar.test.tsx assertion updated."
  severity: major
  test: 9
  resolved_in_commits: [cb6441c]
