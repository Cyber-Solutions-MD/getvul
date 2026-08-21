---
status: complete
phase: 42-risk-trend-analytics-burndown
source: [42-01-SUMMARY.md, 42-02-SUMMARY.md, 42-03-SUMMARY.md]
started: 2026-08-21T14:23:16Z
updated: 2026-08-21T14:23:16Z
---

## Current Test

[testing complete]

## Tests

### 1. Live risk-exposure trend tracer (TREND-01/03)
expected: Analytics nav entry → /dashboard/analytics; violet trend line renders on live data; 7d/30d/90d/1y presets re-fetch; loading skeleton, error+retry, and insufficient-history empty state behave correctly.
result: pass
coverage_id: D4
evidence: Playwright against live seeded stack — nav heading "Risk-exposure trend" present; 4 recharts line elements render; 90d preset re-fetch keeps the line. Also live-approved during the execute-phase session.

### 2. Live backlog aging + burndown (TREND-02)
expected: Populated aging chart (all 3 SLA buckets, severity-stacked bars with accurate tooltips); "% of open backlog is overdue" headline tile; burndown tile shows shrinking (green) with a days-to-clear figure; suppressed / false-positive / actively-excepted findings are absent from the counts.
result: pass
coverage_id: D5
evidence: Playwright — 12 severity-stacked aging bar rects across 3 buckets; overdue tile renders "87% of open backlog is overdue" (legitimate — the scheduled SLA-tier pass recomputed due dates from first_detected_at, so the 150-day-old seeded backlog is genuinely overdue; not a defect); burndown tile "8.6 findings/week net · 37d to clear". Exclusion of suppressed/FP/excepted verified by unit tests. Also live-approved during execution.

### 3. Group scoping + version boundary + custom range (TREND-01/03)
expected: The scope dropdown re-scopes the trend line, aging chart, and burndown tile distinctly from tenant-wide (with the group caption); a v1→v2 boundary renders as a segmented, neutrally-marked, non-interpolated line; a bogus group_id 404s; the 8-group seed exercises the dropdown's search filter; Custom range rejects To-before-From and fires no query.
result: pass
coverage_id: D8
evidence: Playwright + API — scope dropdown lists 8 named groups; "Search groups" filter narrows to "Database Cluster" on typing; selecting "Production Web Tier" re-scopes the trend line and renders the caption verbatim ("Shows Production Web Tier's current members, applied retroactively across this window."); one recharts reference-line renders for the v1→v2 boundary (2026-08-07) with a version label; bogus group_id returns HTTP 404; Custom range with To<From shows "End date must be after start date." Also live-approved during execution.

### 4. Empty-membership group renders the D-04 empty state (backstop)
expected: Selecting a group whose CURRENT membership is entirely empty renders the D-04 "insufficient history / trends appear after a few days" empty affordance (NOT an all-None misleading/gapless line); aging + burndown render their zero-scope state for the same group.
result: pass
reported: "Initially FAILED: a zero-member group ('Decommissioned (empty)') rendered an all-null trend line, not the guided empty state. FIXED inline (commit b9dc1ae) — the empty-state gate now keys on the count of scored (non-null) points. Re-verified live via Playwright: the D-04 'Trends appear after a few days of history' empty state renders with zero trend-line elements."
severity: minor
coverage_id: D9
resolved_by: "commit b9dc1ae (inline fix during this UAT session)"

## Summary

total: 4
passed: 4
issues: 0
pending: 0
skipped: 0

## Gaps

- gap_id: G-42-4
  truth: "A group whose CURRENT membership is entirely empty renders the D-04 'insufficient history' empty affordance, not an all-None misleading/gapless line."
  status: resolved
  resolved_by: "commit b9dc1ae"
  resolved_at: 2026-08-21
  reason: "User-requested automated UAT confirmed the empty-membership group rendered an all-null RiskTrendChart line instead of the guided EmptyState (API returned 31 trend rows all with avg_risk_exposure_score=null). Fixed inline: the empty-state gate now counts scored (non-null) points instead of raw rows. Re-verified live (D-04 empty state renders, zero line elements) + regression test added (page.test.tsx, 19/19 green)."
  severity: minor
  test: 4
  artifacts:
    - "frontend/src/app/(authed)/dashboard/analytics/page.tsx — empty-state gate now keys on scoredPointCount (non-null) instead of trend.length"
    - "frontend/src/app/(authed)/dashboard/analytics/page.test.tsx — added all-null-series → EmptyState regression test"
  missing: []

## Notes

- Tests 1–3 (D4/D5/D8) were also human-approved live during the execute-phase session; this pass re-verified them programmatically against the seeded stack (Playwright + API).
- Root cause for G-42-4 was fully determined by code inspection + live API confirmation; no separate debug agent needed.
- G-42-4 is backstop-tier (the plan author tagged the underlying must_haves truth `verification: backstop`). Phase 42 VERIFICATION.md already passed with this documented as an override — the phase is not blocked by it.
