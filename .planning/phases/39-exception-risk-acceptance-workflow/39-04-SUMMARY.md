---
phase: 39-exception-risk-acceptance-workflow
plan: 04
subsystem: api
tags: [fastapi, sqlalchemy, exceptions, risk-acceptance, compute-on-read, consumer-sweep, ticketing, governance]

# Dependency graph
requires:
  - phase: 39-01
    provides: "active_exception_subquery(tenant_id, now) -- the shared compute-on-read exclusion seam (FINDING/ASSET/ASSET_GROUP branches, CVE-pinned D-10, OR-semantics D-12)"
provides:
  - "compute_risk_scores' raw-score subquery excludes actively-excepted findings (Consumer 6, EXC-02)"
  - "_base_open_vulns' 'active' branch (ONLY) excludes actively-excepted findings, covering get_remediations_grouped / get_hosts_for_remediation / get_remediations_for_host in one edit; 'ignored'/'all' branches deliberately untouched (Consumer 7, T-39-18)"
  - "vulnerabilities/router.py::remediations_for_host's hand-rolled ad hoc query gets its own exclusion predicate (Consumer 11 / Pitfall 5 -- proves the shared-helper fix alone is insufficient)"
  - "campaigns/service.py::get_campaign_progress + bulk_create_campaign_tickets exclude actively-excepted members from both the denominator and the live-ticketing query (Consumers 8/9)"
  - "ticketing/rule_engine.py::find_matching_assets' counts_q AND run_rule's per_remediation rem_q both exclude actively-excepted findings -- closes the governance gap where a scheduler tick could still auto-open a ticket for an accept-risk-governed finding (Consumer 10, Tier 2 #8, T-39-15)"
  - "backend/tests/test_exceptions_consumers.py -- 7 tests, every one seeding a CVE-pinned control alongside the excepted target to prove selective (not blanket) exclusion"
affects: [39-05-consumer-sweep, 39-08-closing-plan]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "1-3 line ~active_exception_subquery(tenant_id, datetime.now(UTC)) WHERE-clause addition threaded verbatim into every Tier-1 core-consumer + the two governance-critical rule-engine queries -- the exact seam 39-01 established, now proven against 5 more call sites with zero new abstractions"

key-files:
  created:
    - backend/tests/test_exceptions_consumers.py
  modified:
    - backend/app/assets/risk_score.py
    - backend/app/vulnerabilities/remediation_service.py
    - backend/app/vulnerabilities/router.py
    - backend/app/campaigns/service.py
    - backend/app/ticketing/rule_engine.py

key-decisions:
  - "Task 1's literal <verify> -k filter ('risk or remediation or campaign or host') under-covers 2 of its own 6 named tests -- test_ignored_all_branches_still_show and test_excepted_member_not_ticketed contain none of those 4 substrings. Ran the full un-filtered file (Task 2's own <verify> command) to confirm all 6 pass; this is a verify-command authoring artifact (like 39-01's Task-2 app.routes precedent), not a functional gap -- every named test exists and passes."
  - "run_rule's per_remediation rem_q sibling fix (the second half of Consumer 10, named in the plan's interfaces block as 'run_rule (208-234)') has no dedicated unit test -- Task 2's action text names exactly ONE new test (test_excluded_from_rule_engine, against find_matching_assets). No pre-existing test in this codebase exercises ticket_mode='per_remediation' at all, so rem_q's identical-shape WHERE-clause addition is verified via the file-level grep gate (5/5) + direct code inspection, not an executed assertion. Flagged here for transparency, not silently assumed correct."
  - "EXC-02 left [ ] unmarked in REQUIREMENTS.md -- re-confirmed via grep across all 8 phase plan files that 39-08 is the only plan claiming all four EXC-01..04 and is the phase's designated last declaring plan (39-01/39-02 precedent); 39-03/39-05 still have EXC-02-relevant work outstanding (SLA subtraction, Tier-2 dashboard/export consumers)."
  - "Executed out of STATE.md's linear 'Plan 3 of 8' pointer -- 39-04 is wave 2 with depends_on:[39-01] only (not 39-03, which is wave 3 and still unexecuted). This is intentional: the phase's dependency graph allows 39-04 to run independent of 39-03, and STATE.md is hand-edited below to reflect the true non-linear completion set (01, 02, 04 done; 03 next, still unblocked) rather than a misleading incremented counter."

patterns-established:
  - "Consumer-sweep plans in this phase author their own local _seed_asset/_seed_vuln/_grant_body/FakeTicketingClient helpers per test file (mirroring test_campaigns.py/test_exceptions_scope.py) rather than importing shared fixtures across test files -- every consumer test in test_exceptions_consumers.py seeds a co-located, un-excepted CONTROL finding/asset/member alongside the excepted target so a passing assertion proves CVE-pinned exclusion (D-10), never a blanket per-asset/per-remediation/per-rule wipe"

requirements-completed: []  # EXC-02 still shared with 39-03/39-05/39-08 (39-08 is the phase's last declaring plan) -- see key-decisions

coverage:
  - id: D1
    description: "An actively-excepted finding is excluded from compute_risk_scores' raw-score subquery; a co-located un-excepted finding on the same asset proves CVE-pinned (not blanket) exclusion"
    requirement: "EXC-02"
    verification:
      - kind: integration
        ref: "backend/tests/test_exceptions_consumers.py#test_excluded_from_risk_scores"
        status: pass
    human_judgment: false
  - id: D2
    description: "An actively-excepted finding's remediation group is excluded from get_remediations_grouped's default 'active' view; a sibling un-excepted remediation_id still appears; the 'all' branch deliberately still shows the excepted (but still-OPEN) finding, proving no over-exclusion"
    requirement: "EXC-02"
    verification:
      - kind: integration
        ref: "backend/tests/test_exceptions_consumers.py#test_excluded_from_remediations_grouped"
        status: pass
      - kind: integration
        ref: "backend/tests/test_exceptions_consumers.py#test_ignored_all_branches_still_show"
        status: pass
    human_judgment: false
  - id: D3
    description: "The hand-rolled remediations_for_host endpoint (router.py, bypasses _base_open_vulns entirely) gets its own exclusion predicate -- an excepted finding never resurfaces there"
    requirement: "EXC-02"
    verification:
      - kind: integration
        ref: "backend/tests/test_exceptions_consumers.py#test_excluded_from_remediations_for_host_bypass"
        status: pass
    human_judgment: false
  - id: D4
    description: "An actively-excepted campaign member is excluded from get_campaign_progress's member count and from bulk_create_campaign_tickets' live-members query -- never ticketed"
    requirement: "EXC-02"
    verification:
      - kind: integration
        ref: "backend/tests/test_exceptions_consumers.py#test_excluded_from_campaign_progress"
        status: pass
      - kind: integration
        ref: "backend/tests/test_exceptions_consumers.py#test_excepted_member_not_ticketed"
        status: pass
    human_judgment: false
  - id: D5
    description: "An accept-risk exception on an asset's only qualifying finding removes it from find_matching_assets' match set (governance-critical, Tier 2 #8) -- a sibling un-excepted asset still matches"
    requirement: "EXC-02"
    verification:
      - kind: integration
        ref: "backend/tests/test_exceptions_consumers.py#test_excluded_from_rule_engine"
        status: pass
    human_judgment: false

# Metrics
duration: 18min
completed: 2026-08-19
status: complete
---

# Phase 39 Plan 04: Consumer Sweep -- Risk Score, Remediation View, Campaigns, Rule Engine Summary

**Threaded the shared `active_exception_subquery` seam into 5 Tier-1 "active work" consumers + the governance-critical automated ticket rule engine, each with a 1-3 line WHERE-clause addition, proven by 7 CVE-pinned exclusion tests.**

## Performance

- **Duration:** 18 min
- **Started:** 2026-08-19T07:27:35Z
- **Completed:** 2026-08-19T07:45:29Z
- **Tasks:** 2/2
- **Files modified:** 6 (1 created, 5 modified)

## Accomplishments

- `compute_risk_scores`' raw-score subquery (`assets/risk_score.py`) excludes actively-excepted findings -- an excepted CRITICAL finding no longer inflates an asset's dashboard risk score, while a co-located un-excepted LOW finding still contributes (Consumer 6)
- `_base_open_vulns`' "active" branch (ONLY) gained the exclusion, covering `get_remediations_grouped` / `get_hosts_for_remediation` / `get_remediations_for_host` in one edit; the "ignored"/"all" branches are deliberately untouched and tested as such (Consumer 7, T-39-18 no-over-exclusion)
- `vulnerabilities/router.py::remediations_for_host` -- the one hand-rolled ad hoc query that bypasses every shared helper -- gets its own predicate, proving the shared-helper fix alone would have left a real bypass (Consumer 11 / Pitfall 5)
- `campaigns/service.py::get_campaign_progress` + `bulk_create_campaign_tickets` exclude actively-excepted members from both the live denominator and the ticket-creation query -- an excepted campaign member is never counted or ticketed (Consumers 8/9)
- `ticketing/rule_engine.py::find_matching_assets` (counts_q) AND `run_rule`'s per_remediation matcher (rem_q) both exclude actively-excepted findings -- closes the governance gap where an accept-risk decision would otherwise still let a scheduler tick auto-open a ticket, which would have been *worse* than the pre-Phase-39 status quo (Consumer 10, Tier 2 #8, T-39-15)
- `backend/tests/test_exceptions_consumers.py` -- new 7-test file; every test seeds an un-excepted control alongside the excepted target, proving D-10 CVE-pinned exclusion rather than a blanket per-asset/per-remediation/per-rule wipe
- Zero new mypy-baseline violations (verified via `git stash` against a clean tree -- the "new: 9" count reproduces identically with none of this plan's changes present, confirming it's the same pre-existing `daily_sync.py` drift 39-01/39-02 already logged); `ruff check`/`ruff format --check` clean; full regression sweep (test_campaigns.py, test_tenant_isolation.py, test_vuln_group_host.py, test_exceptions.py, test_exceptions_scope.py, test_vulnerabilities.py, test_rule_engine.py) all green with zero prior-test breakage

## Task Commits

Each task was committed atomically:

1. **Task 1: risk-score + remediation view (shared helper + hand-rolled bypass) + campaigns exclusion** - `c197f00` (feat)
2. **Task 2: governance-critical -- automated ticket rule engine exclusion + rule-engine test** - `ad5cc25` (feat)

**Plan metadata:** _pending -- this commit follows_

## Files Created/Modified

- `backend/app/assets/risk_score.py` - `compute_risk_scores`' `raw_score_sub` WHERE gains `~active_exception_subquery(tenant_id, datetime.now(UTC))`
- `backend/app/vulnerabilities/remediation_service.py` - `_base_open_vulns`' final ("active") `and_(...)` branch gains the same predicate; "ignored"/"all" branches unchanged
- `backend/app/vulnerabilities/router.py` - `remediations_for_host`'s hand-rolled WHERE gains its own predicate
- `backend/app/campaigns/service.py` - `get_campaign_progress` + `bulk_create_campaign_tickets`'s live-members query both gain the predicate
- `backend/app/ticketing/rule_engine.py` - `find_matching_assets`' `counts_q` WHERE + `run_rule`'s per_remediation `rem_q` WHERE both gain the predicate
- `backend/tests/test_exceptions_consumers.py` - new: 7 tests (6 in Task 1, 1 appended in Task 2), local `_seed_asset`/`_seed_vuln`/`_grant_body`/`FakeTicketingClient` helpers mirroring `test_campaigns.py`/`test_exceptions_scope.py`

## Decisions Made

- Verified the mypy-baseline "new: 9" count is pre-existing `daily_sync.py` drift (not caused by this plan) by stashing all 5 changed/new files and re-running `mypy app/ | mypy-baseline filter` against the clean tree -- identical "new: 9" reproduces with zero of this plan's code present.
- Kept `find_matching_assets`'s exclusion test focused on a severity-filtered `conditions` dict (`{"severity": ["CRITICAL"]}`) so the fix is exercised through the function's real per-asset `counts_q` loop (the early-return path when no vuln-count conditions are set would never reach the patched query).
- See key-decisions in frontmatter for: the Task 1 `-k` filter naming mismatch, the untested `rem_q` sibling fix, EXC-02's unmarked status, and the out-of-linear-order execution relative to STATE.md's prior "Plan 3 of 8" pointer.

## Deviations from Plan

None (Rule 1-4) -- no bugs found, no missing-critical functionality, no blocking issues, no architectural changes. The plan's exact 5 consumer files + 1 governance-critical file were modified with 1-3 line WHERE-clause additions as specified, and all 7 named tests were authored verbatim by name.

Two authoring-fidelity notes (not deviations under Rules 1-4, since they don't touch application code) are documented under Decisions Made / key-decisions above: the Task 1 `<verify>` `-k` filter doesn't literally match 2 of its own 6 named tests, and `run_rule`'s `rem_q` sibling fix has no dedicated test (grep-gate + inspection only).

## Issues Encountered

None. All 7 new tests passed on first write; zero regressions across the 7-file regression sweep; zero new mypy violations; ruff clean on first run.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The `active_exception_subquery` seam is now proven against 6 real call sites total (39-01's `_apply_filters` + this plan's 5), including the one genuinely governance-critical scheduler path (the automated ticket rule engine) and the one genuinely bypass-prone hand-rolled query (`remediations_for_host`).
- 39-03 (SLA subtraction) remains unexecuted and unblocked (`depends_on: [39-01, 39-02]`, both done) -- ready to run next in dependency order, independent of this plan.
- 39-05 (the remaining Tier-2 consumers: `assets/router.py` badges, `users/router.py` owner-risk, `dashboard.py`/`export.py`, `risk_exposure_service.py` rollup) depends on `[39-01, 39-03]`, not on this plan -- it can proceed once 39-03 lands, reusing this plan's exact one-line-per-consumer pattern.
- No blockers. Full `test_exceptions_consumers.py` suite (7/7), `test_rule_engine.py` (9/9), and the broader regression sweep all green; `ruff check`/`ruff format --check` clean; mypy-baseline shows zero new violations attributable to this plan.

## Self-Check: PASSED

- `backend/app/assets/risk_score.py` — FOUND
- `backend/app/vulnerabilities/remediation_service.py` — FOUND
- `backend/app/vulnerabilities/router.py` — FOUND
- `backend/app/campaigns/service.py` — FOUND
- `backend/app/ticketing/rule_engine.py` — FOUND
- `backend/tests/test_exceptions_consumers.py` — FOUND
- Commit `c197f00` — FOUND in git log
- Commit `ad5cc25` — FOUND in git log

---
*Phase: 39-exception-risk-acceptance-workflow*
*Completed: 2026-08-19*
