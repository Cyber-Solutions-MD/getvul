---
phase: 34-historical-recompute-consumer-cutover
plan: 02
subsystem: api
tags: [sqlalchemy, fastapi, feature-flag, risk-scoring, cutover]

# Dependency graph
requires:
  - phase: 34-historical-recompute-consumer-cutover
    provides: "Tenant.cutover_risk_exposure_scoring (migration 044, default OFF) + RiskExposureBackfillJob + risk_backfill_service.py (Plan 01)"
provides:
  - "Flag-gated branch in list_vulnerabilities(sort=\"triage\") — OFF byte-identical (KEV desc -> CVSS desc -> SLA-due asc), ON leads with risk_exposure_score desc"
  - "Flag-gated branch in get_top_findings_for_ai_batch — OFF byte-identical (Asset.risk_score desc primary), ON swaps primary key to per-finding risk_exposure_score desc"
  - "Corrected stale docstring (Phase 33 added risk_exposure_score; the AI-batch selector no longer claims Vulnerability has no risk_score field)"
  - "test_risk_cutover.py: 5-test RISK-08 fixture suite (OFF-identical x2, ON-cutover x2, SLA-untouched structural guard)"
affects: [34-03-diff-ack-flag-flip, 34-04-boundary-guards]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Once-per-call scalar Tenant fetch to branch a query's order_by on a per-tenant boolean flag (mirrors sla_service.py:43's get_sla_days precedent) — reusable by Plan 03/04 for any other flag-gated consumer read"
    - "Inverted-fixture RED proof: seed the NEW ordering key in the OPPOSITE direction of the OLD ordering keys so an OFF-vs-ON behavioral difference is unambiguous in a single assertion"

key-files:
  created:
    - backend/tests/test_risk_cutover.py
  modified:
    - backend/app/vulnerabilities/service.py

key-decisions:
  - "Tenant fetch placed once per list_vulnerabilities call (before the whole sort if/elif chain), not conditioned on sort==\"triage\" — matches the plan's interfaces block literally and mirrors the existing sla_service.py Tenant-fetch-per-call precedent; the extra indexed-PK lookup is negligible cost (same precedent cited in exposure.py:424-426)."
  - "Kept the Asset outerjoin on BOTH paths of get_top_findings_for_ai_batch (the plan's default choice) rather than dropping it on the ON path — simplest, keeps the OFF path's query shape completely untouched, and the join cost is unchanged since it was already present."
  - "SLA (sla_service.py), rule_engine.py, saved_filters.py, and trends.py were touched by NEITHER task — verified via grep (zero risk_exposure_score/risk_score references in sla_service.py) and git diff --stat (no changes to rule_engine.py/saved_filters.py)."

patterns-established:
  - "Flag-gated primary-order-key swap: branch only the PRIMARY sort key on the tenant flag, keep all tiebreakers byte-identical on both paths — minimizes the diff surface and makes the OFF-path-untouched claim trivially reviewable."

requirements-completed: [RISK-08]

coverage:
  - id: D1
    description: "list_vulnerabilities(sort=\"triage\") is byte-identical to pre-Phase-34 ordering when the cutover flag is OFF (default)"
    requirement: "RISK-08"
    verification:
      - kind: unit
        ref: "backend/tests/test_risk_cutover.py#test_triage_sort_flag_off_is_identical"
        status: pass
      - kind: unit
        ref: "backend/tests/test_vulnerabilities.py (existing suite, unmodified, stays green)"
        status: pass
    human_judgment: false
  - id: D2
    description: "list_vulnerabilities(sort=\"triage\") leads by risk_exposure_score desc when the cutover flag is ON"
    requirement: "RISK-08"
    verification:
      - kind: unit
        ref: "backend/tests/test_risk_cutover.py#test_triage_sort_cutover_flag"
        status: pass
    human_judgment: false
  - id: D3
    description: "get_top_findings_for_ai_batch is byte-identical to pre-Phase-34 ordering (Asset.risk_score primary) when the cutover flag is OFF"
    requirement: "RISK-08"
    verification:
      - kind: unit
        ref: "backend/tests/test_risk_cutover.py#test_ai_batch_selector_flag_off_is_identical"
        status: pass
      - kind: unit
        ref: "backend/tests/test_top_findings_for_ai_batch.py (existing suite, unmodified, stays green)"
        status: pass
    human_judgment: false
  - id: D4
    description: "get_top_findings_for_ai_batch ranks by per-finding risk_exposure_score desc when the cutover flag is ON, with an asset-less finding sorting last via nulls_last"
    requirement: "RISK-08"
    verification:
      - kind: unit
        ref: "backend/tests/test_risk_cutover.py#test_ai_batch_selector_cutover_flag"
        status: pass
    human_judgment: false
  - id: D5
    description: "SLA breach detection (sla_service.py) stays severity-keyed — no risk_exposure_score/risk_score reference added (RESOLVED A1 boundary)"
    requirement: "RISK-08"
    verification:
      - kind: unit
        ref: "backend/tests/test_risk_cutover.py#test_sla_breach_stays_severity_keyed"
        status: pass
    human_judgment: false

# Metrics
duration: 15min
completed: 2026-08-12
status: complete
---

# Phase 34 Plan 02: Flag-Gated Consumer Cutover (list sort="triage" + AI batch selector) Summary

**Both genuine RISK-08 cutover consumers (`list_vulnerabilities(sort="triage")` and `get_top_findings_for_ai_batch`) now branch their primary ordering key on `Tenant.cutover_risk_exposure_scoring` via a once-per-call scalar Tenant fetch — proven byte-identical OFF (default) and correctly re-ranked by the new per-finding `risk_exposure_score` ON, with SLA and the two `min_risk_score` threshold sites left deliberately untouched.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-08-12T10:18:08+03:00 (context read)
- **Completed:** 2026-08-12T10:28:15+03:00 (GREEN commit)
- **Tasks:** 2 completed (RED, GREEN)
- **Files modified:** 2 (1 created, 1 modified)

## Accomplishments

- `list_vulnerabilities(sort="triage")`: added the scalar Tenant fetch + flag branch. OFF path is the exact pre-existing `order_by(desc(cisa_kev), nulls_last(desc(cvss_v3_score)), nulls_last(asc(sla_due_at)))` — untouched code path, only reached when `cutover_enabled` is `False`. ON path leads with `nulls_last(desc(Vulnerability.risk_exposure_score))` as the new primary key, keeping the same 3 tiebreakers.
- `get_top_findings_for_ai_batch`: added the same Tenant-fetch idiom; the primary order key is now a runtime-selected expression — `nulls_last(desc(Asset.risk_score))` OFF, `nulls_last(desc(Vulnerability.risk_exposure_score))` ON — with the `Asset` outerjoin and all 3 tiebreakers (KEV/CVSS/SLA) kept identical on both paths. The stale docstring claim ("`Vulnerability` has no `risk_score` field at all") is corrected to describe both the OFF and ON primary keys.
- `test_risk_cutover.py` (5 tests, all green): 2 OFF-byte-identical tests (inverted-`risk_exposure_score` fixtures prove the OFF path ignores the new score entirely), 2 ON-cutover tests (prove the new score becomes the leading key, including an asset-less finding sorting last via `nulls_last` on the ON path), and a structural SLA-untouched guard (reads `sla_service.py`'s source text, asserts no `risk_exposure_score`/`risk_score` substring).
- Existing regression suites confirmed green and unmodified: `test_vulnerabilities.py` (6), `test_sla_service.py` (11), `test_top_findings_for_ai_batch.py` (6) — 23 pre-existing tests plus the 5 new ones, 28 total, all passing with the flag OFF (the only state this environment runs).

## Task Commits

Each task was committed atomically:

1. **Task 1: RED — flag-OFF-identical + flag-ON-new-score tests + SLA-untouched assertion** - `a1e1b5d` (test)
2. **Task 2: GREEN — flag-gated branch in sort="triage" and get_top_findings_for_ai_batch** - `544650f` (feat)

_No REFACTOR commit needed — GREEN required no post-implementation cleanup._

## Files Created/Modified

- `backend/tests/test_risk_cutover.py` - RISK-08 fixture suite: `_seed_asset`/`_seed_vuln`/`_set_cutover_flag` helpers + the 5 tests described above
- `backend/app/vulnerabilities/service.py` - `Tenant` import; scalar Tenant fetch + flag branch inside `list_vulnerabilities`'s `sort="triage"` case; scalar Tenant fetch + primary-key branch + corrected docstring inside `get_top_findings_for_ai_batch`

## Decisions Made

1. **Tenant fetch placement in `list_vulnerabilities`:** added once per call, right before the `sort` if/elif chain begins (not conditioned on `sort == "triage"`) — matches the plan's interfaces block literally, and the extra indexed-PK lookup cost is the same negligible cost the codebase already accepts for `sla_service.py:43` and `exposure.py:424-426`.
2. **Asset outerjoin kept on both paths in `get_top_findings_for_ai_batch`:** the plan flagged dropping it on the ON path as an "optional simplification, not a hard requirement" — declined it to keep the OFF path's query shape completely untouched and minimize the diff.
3. **Exact OFF/ON `order_by` for both consumers** (as landed):
   - `list_vulnerabilities(sort="triage")` OFF: `order_by(desc(cisa_kev), nulls_last(desc(cvss_v3_score)), nulls_last(asc(sla_due_at)))` — byte-identical to pre-Phase-34.
   - `list_vulnerabilities(sort="triage")` ON: `order_by(nulls_last(desc(risk_exposure_score)), desc(cisa_kev), nulls_last(desc(cvss_v3_score)), nulls_last(asc(sla_due_at)))`.
   - `get_top_findings_for_ai_batch` OFF: `order_by(nulls_last(desc(Asset.risk_score)), desc(cisa_kev), nulls_last(desc(cvss_v3_score)), nulls_last(asc(sla_due_at)))` — byte-identical to pre-Phase-34.
   - `get_top_findings_for_ai_batch` ON: `order_by(nulls_last(desc(Vulnerability.risk_exposure_score)), desc(cisa_kev), nulls_last(desc(cvss_v3_score)), nulls_last(asc(sla_due_at)))`.

## Deviations from Plan

None - plan executed exactly as written. The one auto-run of `ruff format` (whitespace-only reflow of the two files, no logic change) is not a deviation — it was run as part of the standard lint gate before committing GREEN, same as any other task.

## Issues Encountered

None.

## Verification Evidence

- `cd backend && ENCRYPTION_KEY=... JWT_SECRET_KEY=... .venv/bin/python -m pytest tests/test_risk_cutover.py -v` → 5 passed.
- Flag-OFF regression gate: `pytest tests/test_vulnerabilities.py tests/test_sla_service.py tests/test_top_findings_for_ai_batch.py -v` → 23 passed, unmodified, no live behavior change.
- SLA-untouched gate: `grep -n "risk_exposure_score\|risk_score" backend/app/vulnerabilities/sla_service.py` → no output (zero matches).
- min_risk_score-untouched gate: `git diff --stat -- app/ticketing/rule_engine.py app/vulnerabilities/saved_filters.py` → no output (no changes).
- Severity-tier centralization citation: `grep -n "RISK_SCORE_TIER_" backend/app/assets/risk_score.py` → `RISK_SCORE_TIER_CRITICAL = 80`, `RISK_SCORE_TIER_HIGH = 50`, `RISK_SCORE_TIER_MEDIUM = 20` (Phase 33, confirmed present, no new work needed this plan).
- `mypy app/vulnerabilities/service.py | mypy-baseline filter --allow-unsynced` → 0 new violations.
- `ruff check` + `ruff format --check` on both changed files → clean.

## User Setup Required

None - no external service configuration required. The flag itself (`cutover_risk_exposure_scoring`) remains OFF in every tenant row (Plan 01's migration default); this plan only builds the read-side branch, per 34-CONTEXT's locked decision the flip is never performed in this environment.

## Next Phase Readiness

- Plan 03 (diff + ack + the flag-flip endpoint) and Plan 04 (boundary guards / dual-write) can now assume both `sort="triage"` and `get_top_findings_for_ai_batch` correctly honor `cutover_risk_exposure_scoring` — no further wiring needed in `service.py` for these two consumers.
- The trend chart (Plan 04's concern) and SLA (deliberately out of scope, RESOLVED A1) remain untouched — neither reads `risk_exposure_score`/`Asset.risk_score` differently than before this plan.
- `min_risk_score` in `rule_engine.py`/`saved_filters.py` remains reading `Asset.risk_score` unconditionally — Plan 03's RISK-09 diff+ack artifact is the next step for that surface, no live retarget performed here.
- No blockers for Plan 03/04.

---
*Phase: 34-historical-recompute-consumer-cutover*
*Completed: 2026-08-12*

## Self-Check: PASSED

All created/modified files verified present on disk; both task commit hashes (`a1e1b5d`, `544650f`) verified present in `git log`.
