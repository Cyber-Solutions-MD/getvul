---
phase: 42-risk-trend-analytics-burndown
plan: 02
subsystem: analytics
tags: [fastapi, pydantic-v2, sqlalchemy, recharts, tanstack-query, nextjs]

# Dependency graph
requires:
  - phase: 42-risk-trend-analytics-burndown
    provides: "42-01's backend/app/analytics/ module skeleton, AnalyticsOverviewResponse, and /dashboard/analytics page's single-query loading/error/empty/populated branch structure — extended additively, no reshape"
  - phase: 36-remediation-sla-engine-escalation
    provides: "sla_tier_service.py tier policy (tier_for_score / severity_to_tier / get_tier_policy) + the stored Vulnerability.sla_due_at / sla_breached columns bucketing reads directly"
  - phase: 39-exception-risk-acceptance-workflow
    provides: "active_exception_subquery(tenant_id, now) — the exclusion predicate applied verbatim to every open-backlog query"
provides:
  - "get_aging_distribution + get_burndown_rate service functions; get_analytics_overview extended with aging/aging_pct_overdue/burndown keys (additive, no reshape)"
  - "get_vuln_trends gains an additive asset_ids: list[uuid.UUID] | None = None param (byte-identical for existing callers) — the seam Plan 03 wires through for group scoping"
  - "BacklogAgingChart (severity-stacked, SLA-tier-bucketed bar chart + overdue headline tile) + BurndownTile (net-velocity + capped days-to-clear) rendered under the trend line on /dashboard/analytics"
affects: [42-03-PLAN, 43-executive-compliance-reporting]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Capped-projection pattern: a rate-based day-count projection (days_to_clear) is populated ONLY for the improving/shrinking branch, hard-capped at a named MAX constant (MAX_PROJECTION_DAYS = 500) with an explicit capped: bool flag rather than an unbounded or silently-truncated number — growing/no_change branches carry null, never a fake number"
    - "Additive-scope-param threading: extend an existing service function's signature with a new keyword-only param defaulting to None (get_vuln_trends gains asset_ids), verified via grep that every existing call site is untouched — the exact seam Plan 03 will wire through for real group scoping"
    - "Bucket-boundary determinism via stored state, not recomputation: sla_breached / sla_due_at are read as-is (never recomputed per-row); the breached/non-breached line mirrors compute_sla_state's own now >= sla_due_at inclusive-on-breached semantics, and the recently_breached/long_overdue split is a second, independent inequality (now - sla_due_at <= tier_days) — one finding can only ever satisfy exactly one of the three bucket predicates"

key-files:
  created:
    - frontend/src/components/analytics/backlog-aging-chart.tsx
    - frontend/src/components/analytics/burndown-tile.tsx
  modified:
    - backend/app/analytics/service.py
    - backend/app/analytics/schemas.py
    - backend/app/vulnerabilities/trends.py
    - backend/tests/test_analytics.py
    - frontend/src/components/analytics/microcopy.ts
    - frontend/src/lib/queries/use-analytics.ts
    - "frontend/src/app/(authed)/dashboard/analytics/page.tsx"
    - "frontend/src/app/(authed)/dashboard/analytics/page.test.tsx"

key-decisions:
  - "Aging bucket edge is deterministic by construction, not by a tie-break rule: sla_breached mirrors compute_sla_state's now >= sla_due_at (inclusive on the breached side) for the within_sla/breached split; recently_breached vs long_overdue then splits on now - sla_due_at <= tier_days (recently_breached) vs > tier_days (long_overdue) — two independent inequalities, so a finding lands in exactly one bucket with no double-count and no drop at either boundary"
  - "MAX_PROJECTION_DAYS locked at 500 (backend/app/analytics/service.py:71); days_to_clear is populated ONLY when status == 'shrinking' (null for growing/no_change) and is capped=True at the 500 ceiling per UI-SPEC E4, rendering '500+ d to clear' rather than an absurd multi-thousand-day figure"
  - "pct_overdue returns 0 (int), never None, when total open == 0 — UI-SPEC E3's explicit-zero requirement ('0% of open backlog is overdue') takes precedence over the general None-safety idiom used elsewhere"
  - "get_vuln_trends's new asset_ids param is wired now (default None = tenant-wide) but not yet exercised by any caller with a real value — Plan 03 is the consumer; grep-confirmed every existing call site is byte-identical"
  - "BurndownTile omits RiskRing entirely (a rate, not a percentage) and never divides client-side — status/netPerWeek/daysToClear/capped all arrive as precomputed props from get_burndown_rate; the component only branches copy on status"
  - "Task 3's human-verify checkpoint was approved against ORCHESTRATOR-SEEDED SYNTHETIC data, not production data: the orchestrator inserted synthetic findings across all 3 SLA-tier buckets and a shrinking burndown trend (net 8.6/wk, 37 d to clear, aging_pct_overdue=44) out-of-band (a login-cache fix + tenant seed happened outside this plan's file changes) so the populated branch of both new sections had something to render; the human then verified the live /api/v1/analytics/overview response and the rendered page against that seeded state, not a production tenant's real backlog"
  - "TREND-02 marked [x] complete in REQUIREMENTS.md — 42-02 is the sole declaring plan (confirmed via `gsd-tools.cjs requirements ready-ids 42-02-PLAN.md TREND-02` -> {\"ready\":[\"TREND-02\"],\"blocked\":[],\"total\":1}), unlike TREND-01/TREND-03 which stay open pending 42-03 (shared with 42-01, already documented in 42-01-SUMMARY.md)"
  - "Re-confirmed (independently of the 42-01 finding) that `gsd-tools.cjs query roadmap.update-plan-progress 42 42-02 complete` corrupts ROADMAP.md formatting: it dropped the '(tracer-led)' suffix, inserted stray blank lines around the Phase 42 plan-list block, and mangled the progress-table row's cell spacing ('In Progress|  |' instead of 'In Progress | - |') — while also reporting a stale summary_count=1 (correct given 42-02-SUMMARY.md did not exist on disk at call time, but not useful for finalization). Reverted via `git checkout -- .planning/ROADMAP.md` and hand-edited both STATE.md and ROADMAP.md directly instead, per this project's established decision-log precedent (Phases 39-41, reaffirmed at 42-01)"

patterns-established:
  - "Rate-tile chrome (campaign-burndown-card.tsx's rounded-lg/border-border-subtle/bg-surface-2/p-4 card + directional text-success/text-danger/text-muted copy row) reused verbatim for a second, unrelated metric (backlog burndown) — confirms this is now the codebase's general 'directional rate tile' pattern, not something specific to campaigns"
  - "Stacked-severity bar chart over named text-label buckets (not a continuous axis) built by importing SEVERITY_FILLS from trend-chart.tsx rather than redefining a color map — the second consumer of that export after risk-trend-chart.tsx, confirming it is now a shared severity-color source of truth"

requirements-completed: [TREND-02]

coverage:
  - id: D1
    description: "get_aging_distribution buckets current open findings into within_sla / recently_breached / long_overdue (stacked by severity), honoring active_exception_subquery verbatim and sla_tier_service tier windows (never the legacy sla_service.py 5-severity constants), deterministic at the exact tier-boundary edge, and rendering all-zero buckets (not an error) when nothing is open"
    requirement: "TREND-02"
    verification:
      - kind: unit
        ref: "backend/tests/test_analytics.py#test_aging_honors_exclusion_predicate"
        status: pass
      - kind: unit
        ref: "backend/tests/test_analytics.py#test_aging_buckets_use_tier_policy"
        status: pass
      - kind: unit
        ref: "backend/tests/test_analytics.py#test_aging_bucket_edge_deterministic"
        status: pass
      - kind: unit
        ref: "backend/tests/test_analytics.py#test_aging_zero_open_renders_three_zero_buckets"
        status: pass
    human_judgment: false
  - id: D2
    description: "get_burndown_rate returns net velocity (avg resolved-new per week) plus a projected days-to-zero across shrinking (positive projection) / growing (no clear date) / no-change (distinct branch) states, with the projection capped at MAX_PROJECTION_DAYS rather than an absurd multi-thousand-day number"
    requirement: "TREND-02"
    verification:
      - kind: unit
        ref: "backend/tests/test_analytics.py#test_burndown_projection_branches"
        status: pass
    human_judgment: false
  - id: D3
    description: "Every new numeric aggregate (aging bucket counts, pct_overdue, net_per_week, days_to_clear) is a JSON number, never a Decimal-string, entering the Pydantic response"
    requirement: "TREND-02"
    verification:
      - kind: unit
        ref: "backend/tests/test_analytics.py#test_burndown_and_aging_numeric_types"
        status: pass
    human_judgment: false
  - id: D4
    description: "BacklogAgingChart (3 severity-stacked SLA-tier buckets + sr-only data table + '% of open backlog is overdue' headline tile, explicit at zero) and BurndownTile (directional net-per-week + capped/growing/no-change projection copy, no RiskRing, no client-side division) render under the trend line on /dashboard/analytics, sharing the page's single compute pass; no freehand hex, no new dependency, SEVERITY_FILLS reused verbatim, tsc clean"
    requirement: "TREND-02"
    verification:
      - kind: automated_ui
        ref: "frontend/src/app/(authed)/dashboard/analytics/page.test.tsx (12/12 total: 7 from Plan 01 + 5 new — 3-bucket populated render, zero-overdue explicit tile, no-change/growing/capped burndown branches)"
        status: pass
      - kind: other
        ref: "grep -n SEVERITY_FILLS backlog-aging-chart.tsx (imported, not redefined); grep -rniE '#[0-9a-f]{3,6}' (no freehand hex); grep -n RiskRing burndown-tile.tsx (0 matches); npx tsc --noEmit (clean)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Live end-to-end verification in the real dev stack: the populated aging chart (all 3 buckets), the overdue headline tile, and the burndown tile (shrinking, green, with a days-to-clear figure) render correctly against a seeded tenant, and suppressed/false-positive/actively-excepted findings are confirmed absent from the counts"
    requirement: "TREND-02"
    verification:
      - kind: manual_procedural
        ref: "Task 3 checkpoint:human-verify (gate=\"blocking\") — 5-step how-to-verify script against orchestrator-seeded synthetic data (all 3 buckets populated, aging_pct_overdue=44, net 8.6/wk shrinking, 37 d to clear); resume-signal 'approved'"
        status: pass
    human_judgment: true
    rationale: "Visual rendering fidelity (stacked-bar severity coloring, tooltip accuracy, directional tile color), live network loading/error behavior, and correct exclusion of suppressed/FP/excepted findings against real seeded rows cannot be fully proven by a mocked-hook unit-test harness alone. The human already reviewed the live page and responded 'approved' in this session; recorded here for audit trail. Verification data was synthetic (orchestrator-seeded for this checkpoint), not production data — a genuinely empty or all-within-SLA production tenant was not separately observed live, though both are covered by D1's zero-open and within_sla unit tests."

duration: ~35min
completed: 2026-08-21
status: complete
---

# Phase 42 Plan 02: Backlog Aging + Burndown Rate Summary

**Backlog aging (3 SLA-tier buckets × severity) and burndown rate (net velocity + capped days-to-clear) shipped on `/dashboard/analytics` — new `get_aging_distribution`/`get_burndown_rate` service functions honoring the Phase 39 exclusion predicate and Phase 36 tier windows verbatim, rendered via a new `BacklogAgingChart` + `BurndownTile` under the existing trend line — human-verify checkpoint approved against orchestrator-seeded synthetic data.**

## Performance

- **Duration:** ~35 min (includes the Task 3 human-verify checkpoint pause between the Task 2 commit and the "approved" response, plus this finalization session)
- **Started:** 2026-08-21T12:23:17Z (`cc35712`, Task 1 commit)
- **Completed:** 2026-08-21T12:57:59Z
- **Tasks:** 3/3 (2 auto tasks + 1 blocking human-verify checkpoint)
- **Files modified:** 10 (4 backend, 6 frontend — 2 newly created, 8 extended)

## Accomplishments
- `get_aging_distribution`: live query over open (`OPEN`/`IN_PROGRESS`) findings, `~active_exception_subquery(tenant_id, now)` applied verbatim, tier boundaries resolved via `sla_tier_service` (never the legacy `sla_service.py` 5-severity constants); buckets into `within_sla` / `recently_breached` / `long_overdue` stacked by severity, plus `pct_overdue` (explicit `0`, never `None`, at zero open)
- `get_burndown_rate`: composes `get_vuln_trends`'s new-vs-resolved feed into a net-per-week velocity and a `MAX_PROJECTION_DAYS`-capped (500) days-to-clear projection, populated only on the `shrinking` branch; `growing`/`no_change` carry `null` with distinct copy branches
- `get_vuln_trends` gains an additive `asset_ids: list[uuid.UUID] | None = None` parameter (default preserves every existing call site byte-for-byte) — the seam Plan 03 will exercise for group scoping
- `get_analytics_overview` extended additively with `aging` / `aging_pct_overdue` / `burndown` keys; no reshape of the existing `trend`/`boundaries` response
- 11/11 backend tests green (6 new: exclusion predicate, tier-policy override, deterministic edge boundary, zero-open empty state, all 4 burndown branches incl. the overflow cap, numeric JSON-safety)
- `BacklogAgingChart`: recharts stacked `BarChart` over the 3 named buckets, `SEVERITY_FILLS` imported verbatim from `trend-chart.tsx` (not redefined), sr-only data table, Display-size "N% of open backlog is overdue" headline tile
- `BurndownTile`: Display-size net-per-week headline + directional copy row (`text-success`/`text-danger`/muted) + capped/growing/shrinking projected-clear line; receives all values as precomputed props, no client-side division, no `RiskRing`
- Both wired into `/dashboard/analytics`'s populated branch under the trend line (`xl`-gapped), sharing the page's single-query loading/error/empty branches (D-13) — no independent fetch
- 12/12 frontend tests green (5 new: 3-bucket populated render, zero-overdue explicit tile, no-change/growing/capped burndown branches)
- Task 3 checkpoint (`gate="blocking"`) reviewed against orchestrator-seeded synthetic data (all 3 aging buckets populated, `aging_pct_overdue=44`, net 8.6/wk shrinking, 37 d to clear) and **approved** by the user — unblocks Plan 03

## Task Commits

Each task was committed atomically:

1. **Task 1: Aging distribution + burndown rate service functions + schemas + tests** — `cc35712` (feat; tests and implementation landed together — see TDD Gate Compliance below)
2. **Task 2: BacklogAgingChart + BurndownTile + page wiring + microcopy** — `bb025dd` (feat)
3. **Task 3: checkpoint:human-verify (blocking)** — no code commit (pure verification gate); human responded "approved"

**Plan metadata:** committed alongside this SUMMARY (see Self-Check below for hash)

## TDD Gate Compliance

Task 1 declares `tdd="true"` with an explicit `<behavior>` block instructing tests to be authored FIRST. `git log` between the Plan 01 boundary (`9193643`) and this plan's Task 1 commit shows **no separate `test(...)` RED commit** — `cc35712` is a single `feat(...)` commit containing both the 6 new tests and the service/schema implementation together. This is a process gap relative to the plan's RED/GREEN gate sequence (Task 1 was executed and committed by the prior executor session before this continuation began, so it cannot be retroactively split without rewriting shared history, which is prohibited). Outcome is not in doubt — all 11 backend tests (6 new + 5 from Plan 01) are green per the completed-state handoff and this session's file/commit inspection — but the RED-first discipline itself was not observed as a distinct commit. Flagged here for audit trail; no further action taken (rewriting `cc35712`'s history is out of scope and against the destructive-git-operations policy).

## Files Created/Modified
- `backend/app/analytics/service.py` - `get_aging_distribution`, `get_burndown_rate`, `MAX_PROJECTION_DAYS = 500`; `get_analytics_overview` extended
- `backend/app/analytics/schemas.py` - `AgingBucketResponse`, `BurndownResponse`; `AnalyticsOverviewResponse` extended with `aging`/`aging_pct_overdue`/`burndown`
- `backend/app/vulnerabilities/trends.py` - `get_vuln_trends` gains additive `asset_ids` param
- `backend/tests/test_analytics.py` - 6 new tests (11 total)
- `frontend/src/components/analytics/backlog-aging-chart.tsx` - new: stacked severity bar chart + overdue headline tile
- `frontend/src/components/analytics/burndown-tile.tsx` - new: net-velocity + projected-clear tile
- `frontend/src/components/analytics/microcopy.ts` - `aging` + `burndown` sections added
- `frontend/src/lib/queries/use-analytics.ts` - response type extended with aging/burndown fields
- `frontend/src/app/(authed)/dashboard/analytics/page.tsx` - wires both new sections under the trend line
- `frontend/src/app/(authed)/dashboard/analytics/page.test.tsx` - 5 new tests (12 total)

## Decisions Made
See `key-decisions` in frontmatter for the full list. Highlights: deterministic two-inequality bucket-boundary construction (no tie-break needed); `MAX_PROJECTION_DAYS = 500` with an explicit `capped` flag and `days_to_clear: null` outside the shrinking branch; `pct_overdue` explicit `0` (not `None`) at zero; `asset_ids` threaded into `get_vuln_trends` now but unexercised until Plan 03; the human-verify checkpoint was approved against orchestrator-seeded synthetic data, not production data; TREND-02 marked complete (sole declaring plan) while TREND-01/03 stay open per the 42-01 precedent; `roadmap update-plan-progress`'s corruption behavior was independently re-confirmed and worked around by hand-editing.

## Deviations from Plan

None affecting code correctness or scope — plan executed as written for Tasks 1 and 2. One process-level deviation is documented above under "TDD Gate Compliance" (Task 1's RED/GREEN commits were collapsed into one `feat` commit rather than a separate `test` commit followed by a `feat` commit); this was already committed by the prior executor session before this continuation began and is noted for audit trail, not corrected retroactively.

## Issues Encountered

- Re-ran `gsd-tools.cjs query roadmap.update-plan-progress 42 42-02 complete` as instructed to test the CLI path first; it corrupted `ROADMAP.md` formatting (dropped the `(tracer-led)` suffix, inserted stray blank lines, mangled the progress-table row spacing) and reported a stale count since `42-02-SUMMARY.md` didn't exist on disk yet at call time. Reverted with `git checkout -- .planning/ROADMAP.md` (no other changes were staged at that point) and hand-edited both `STATE.md` and `ROADMAP.md` directly instead, per this project's established precedent.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Both new sections (aging + burndown) are live on `/dashboard/analytics`, sharing the same single-compute-pass query as the Plan 01 trend line — no independent fetch, no reshape of the response envelope.
- `get_vuln_trends`'s additive `asset_ids` param and the response shape are both already positioned for Plan 03 (group scope + custom date range + synthetic-boundary frontend verification) to extend without touching this plan's files structurally.
- No blockers. TREND-02 is now `[x]` complete in REQUIREMENTS.md; TREND-01/TREND-03 remain intentionally open pending 42-03.

---
*Phase: 42-risk-trend-analytics-burndown*
*Completed: 2026-08-21*

## Self-Check: PASSED

All 10 plan files (4 backend, 6 frontend) and both task commits (`cc35712`, `bb025dd`) verified present via `[ -f ... ]` and `git log --oneline --all | grep`. No missing items.
