---
phase: 34-historical-recompute-consumer-cutover
plan: 04
subsystem: api
tags: [risk-scoring, notifications, trends, feature-flag, boundary-guard, fastapi, sqlalchemy]

# Dependency graph
requires:
  - phase: 34-historical-recompute-consumer-cutover
    provides: "Plan 01's Tenant.cutover_risk_exposure_scoring flag column + Plan 33's Asset.risk_exposure_score / RISK_MODEL_VERSION"
provides:
  - "Unconditional dual-write of new-model risk metrics into every DailySnapshot (avg_risk_exposure_score, asset_risk_scores, asset_risk_exposure_scores, risk_model_version_snapshot)"
  - "Dead-code fix: _check_risk_score_changes now actually fires (previously always returned 0 for every tenant, every day)"
  - "Version-boundary-guarded spike notification (same-version-only diffing, new-vs-new ON / old-vs-old OFF, never cross-version)"
  - "Continuity-aware trend read (avg_risk_exposure additional key on get_risk_score_trend rows, existing avg_risk wire contract unchanged)"
affects: ["future flag-flip phase", "trend-chart frontend (if it ever adopts avg_risk_exposure)"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Unconditional dual-write ahead of a flag flip, so real history exists before cutover (structural trend-cliff / alert-storm prevention)"
    - "Same-version-only diffing keyed off a per-tenant boolean flag, read once per check"

key-files:
  created:
    - backend/tests/test_risk_boundary_guard.py
  modified:
    - backend/app/vulnerabilities/trends.py
    - backend/app/notifications/alerts.py

key-decisions:
  - "Dual-write is unconditional on the cutover flag per 34-CONTEXT RESOLVED A2 — verified via grep gate (see below)"
  - "get_risk_score_trend adds avg_risk_exposure as an ADDITIONAL key (not a rename) so the existing avg_risk wire contract stays byte-identical"
  - "_check_risk_score_changes fixes the pre-existing dead-code bug (asset_risk_scores was never populated) as part of enabling the boundary guard, since guarding a check that never fires proves nothing (Pitfall 2)"

patterns-established:
  - "Version-boundary guard: read the flag once, select the matching-version metrics key + column, never mix old/new across the diff"

requirements-completed: [RISK-10]

coverage:
  - id: D1
    description: "capture_daily_snapshot dual-writes avg_risk_exposure_score, asset_risk_scores (dead-code fix), asset_risk_exposure_scores, and risk_model_version_snapshot into every DailySnapshot, unconditionally"
    requirement: "RISK-10"
    verification:
      - kind: unit
        ref: "backend/tests/test_risk_boundary_guard.py#test_snapshot_populates_asset_risk_dicts"
        status: pass
    human_judgment: false
  - id: D2
    description: "_check_risk_score_changes actually fires for a genuine same-version spike (non-zero control), on both the OLD (flag OFF) and NEW (flag ON) branches"
    requirement: "RISK-10"
    verification:
      - kind: unit
        ref: "backend/tests/test_risk_boundary_guard.py#test_genuine_spike_still_alerts"
        status: pass
      - kind: unit
        ref: "backend/tests/test_risk_boundary_guard.py#test_genuine_spike_new_version_alerts"
        status: pass
    human_judgment: false
  - id: D3
    description: "A fixture spanning the cutover boundary (flag flips OFF->ON between two snapshot days) produces ZERO storm alerts, because the diff is same-version-only"
    requirement: "RISK-10"
    verification:
      - kind: unit
        ref: "backend/tests/test_risk_boundary_guard.py#test_cutover_boundary_no_storm_no_cliff"
        status: pass
    human_judgment: false
  - id: D4
    description: "get_risk_score_trend's new (avg_risk_exposure) series stays continuous across a boundary day where the old (avg_risk) series jumps sharply"
    requirement: "RISK-10"
    verification:
      - kind: unit
        ref: "backend/tests/test_risk_boundary_guard.py#test_trend_no_cliff"
        status: pass
    human_judgment: false

duration: 35min
completed: 2026-08-12
status: complete
---

# Phase 34 Plan 04: RISK-10 Version-Boundary Guards Summary

**Unconditional dual-write of new-model risk metrics into every DailySnapshot, fixing the pre-existing dead `asset_risk_scores` read and version-boundary-guarding `_check_risk_score_changes` so a `risk_model_version` change across a day boundary produces neither an alert storm nor a trend cliff.**

## Performance

- **Duration:** 35 min
- **Started:** 2026-08-12T07:30:00Z (approx.)
- **Completed:** 2026-08-12T08:06:21Z
- **Tasks:** 3 (RED / GREEN pt1 / GREEN pt2)
- **Files modified:** 2 (+1 test file created)

## Accomplishments

- `capture_daily_snapshot` (`backend/app/vulnerabilities/trends.py`) now writes four new keys into every `DailySnapshot.metrics`, **unconditionally** (no read of `Tenant.cutover_risk_exposure_scoring` anywhere in the function):
  - `avg_risk_exposure_score` — scalar `func.avg(Asset.risk_exposure_score)`, mirroring the existing `avg_risk_score` pattern verbatim.
  - `asset_risk_scores` — `{str(asset.id): risk_score}` — **the dead-code fix**: this exact key is what `_check_risk_score_changes` has always read but `capture_daily_snapshot` had never written, meaning the spike-notification check has returned `0` for every tenant, every day, since it was written.
  - `asset_risk_exposure_scores` — `{str(asset.id): risk_exposure_score}`, the new parallel series.
  - `risk_model_version_snapshot` — stamped `RISK_MODEL_VERSION` (`"v1"`, imported from `risk_exposure_service.py`) for future model-version boundary guards.
  - All four keys are built from **one** extra bulk `select(Asset.id, Asset.risk_score, Asset.risk_exposure_score)` query, tenant-scoped + `is_ignored` filtered, mirroring the existing `total_assets` query shape.
- `get_risk_score_trend` gains an **additional** key, `avg_risk_exposure` (sourced from `metrics.get("avg_risk_exposure_score", 0)`), on every row dict. The existing `avg_risk` key's name and source (`metrics.get("avg_risk_score", 0)`) are byte-identical — no wire-contract break for the OFF/pre-flip path.
- `_check_risk_score_changes` (`backend/app/notifications/alerts.py`) reads `tenant.cutover_risk_exposure_scoring` **once** and picks a matched `(metrics_key, score_column)` pair:
  - **OFF (default):** `asset_risk_scores` dict vs. live `Asset.risk_score` — this is the OLD-model comparison, now genuinely wired for the first time.
  - **ON:** `asset_risk_exposure_scores` dict vs. live `Asset.risk_exposure_score` — the NEW-model comparison.
  - **Never cross-version** — the function cannot compare a new-model live score against an old-model yesterday value or vice versa. The `>= 20` delta threshold, `_notification_exists(hours=24)` dedup, and `create_notification(...)` call are byte-identical on both branches.
- New fixture suite `backend/tests/test_risk_boundary_guard.py` (5 tests, all passing): dict-population shape, a non-zero control on the OFF branch, a non-zero control on the ON branch (Pitfall-2 controls — proving the check genuinely fires before asserting a boundary zero proves anything), the core boundary fixture (flag flips OFF→ON between two snapshot days, same-version diff yields 0 alerts even though a naive cross-version diff would have produced a 46-point false spike), and a trend-continuity fixture (old series jumps 65 points across the boundary day, new series drifts only 2).

## Task Commits

Each task was committed atomically:

1. **Task 1: RED — snapshot dual-write, genuine-spike control, boundary no-storm, trend no-cliff** - `639ffc0` (test)
2. **Task 2: GREEN part 1 — capture_daily_snapshot dual-write + get_risk_score_trend continuity read** - `6982a8d` (feat)
3. **Task 3: GREEN part 2 — _check_risk_score_changes dead-code fix + version-boundary branch** - `88c3f81` (feat)

_Note: this was a `type: tdd` plan; the RED commit (`639ffc0`) precedes both GREEN commits (`6982a8d`, `88c3f81`) in git log, confirming gate sequence order. No REFACTOR commit was needed — the GREEN implementation matched the intended shape with no cleanup pass required._

## Files Created/Modified

- `backend/tests/test_risk_boundary_guard.py` - New RISK-10 fixture suite (5 tests): dict-population shape, OFF/ON non-zero spike controls, boundary no-storm, trend no-cliff.
- `backend/app/vulnerabilities/trends.py` - `capture_daily_snapshot` dual-writes 4 new unconditional metrics keys; `get_risk_score_trend` exposes `avg_risk_exposure` as an additional row key.
- `backend/app/notifications/alerts.py` - `_check_risk_score_changes` reads the cutover flag once, diffs same-version-only (new-vs-new ON, old-vs-old OFF).

## Decisions Made

- **Dual-write is unconditional — verified mechanically.** `grep -n "cutover_risk_exposure_scoring" backend/app/vulnerabilities/trends.py` returns **nothing** (confirmed empty, exit code 1). One early comment draft referenced the flag's literal name to explain *why* it wasn't being read; reworded to describe the same intent without the literal string, so the mechanical gate (which the plan's `<verification>` section requires to return NOTHING) passes honestly rather than by accident.
- **`avg_risk_exposure` is an additive key, not a rename.** Per the plan's interface note ("do NOT change the existing avg_risk field name — the OFF/pre-flip wire contract stays identical"), the new series lives under a new key name so any future frontend consumer opts in explicitly.
- **The Pitfall-2 non-zero controls are load-bearing, not decorative.** `test_genuine_spike_still_alerts` and `test_genuine_spike_new_version_alerts` were written and verified to actually assert `>= 1` before the boundary test's `== 0` assertion is trusted — a green boundary-zero test without these would prove nothing (the dead-code bug would trivially pass it too).

## Deviations from Plan

None — plan executed exactly as written. One clarification, not a deviation: the plan's `<verification>` unconditional-dual-write grep gate is a literal string match against `trends.py`; the first draft of an explanatory code comment happened to contain that literal string (in a "this is NOT gated on X" sense) and was reworded before commit so the mechanical gate passes for the right reason (no flag-name reference at all in the file) rather than needing a human to eyeball the false-positive.

## Issues Encountered

None. The RED fixture failed for a real reason on first run (`asset_risk_scores` missing from the constructed metrics dict), confirming the dead-code bug was genuinely reproduced before any fix landed.

## Verification Evidence

```
$ cd backend && ENCRYPTION_KEY=... JWT_SECRET_KEY=test-secret .venv/bin/python -m pytest tests/test_risk_boundary_guard.py -x
5 passed in 0.92s

$ ENCRYPTION_KEY=... JWT_SECRET_KEY=test-secret .venv/bin/python -m pytest tests/test_severity_trends.py tests/test_dashboard_tiles.py
8 passed in ~2s   # both existing snapshot-consumer suites regress clean

$ grep -n "cutover_risk_exposure_scoring" backend/app/vulnerabilities/trends.py
(no output — unconditional-dual-write gate satisfied)

$ .venv/bin/ruff check app/vulnerabilities/trends.py app/notifications/alerts.py tests/test_risk_boundary_guard.py
All checks passed!

$ .venv/bin/ruff format --check app/vulnerabilities/trends.py app/notifications/alerts.py tests/test_risk_boundary_guard.py
3 files already formatted
```

## Next Phase Readiness

Phase 34 (Historical Recompute & Consumer Cutover) is now fully implemented across all 4 plans (backfill service + scheduler wire, flag-gated consumer cutover, RISK-09 diff+ack, RISK-10 boundary guards). Per 34-CONTEXT.md's locked "Environment honesty" section, the actual live flag-flip (`Tenant.cutover_risk_exposure_scoring = True` on a real tenant) remains accepted debt for a human on a validated live stack — this environment has no live/at-scale tenant data, consistent with Phases 31/32/33's on-trust waivers. By the time that flip ever happens, every `DailySnapshot` captured from this deploy forward already carries real `avg_risk_exposure_score` / `asset_risk_exposure_scores` history, so the trend chart's new series and the spike-notification check both have genuine multi-day continuity the first time they're ever read on the ON path — there is no "day 1 of the new metric" moment at cutover time.

No blockers for phase closure. The one remaining phase-level action is the final `/gsd-verify-phase` / phase VALIDATION.md pass across all 4 plans.

---
*Phase: 34-historical-recompute-consumer-cutover*
*Completed: 2026-08-12*

## Self-Check: PASSED

All created/modified files confirmed present on disk; all 3 task commits (`639ffc0`, `6982a8d`, `88c3f81`) confirmed present in `git log`.
