---
phase: 36-remediation-sla-engine-escalation
plan: 01
subsystem: vulnerabilities
tags: [sla, risk-tier, fastapi, sqlalchemy, react, scheduler, tracer]

# Dependency graph
requires:
  - phase: 33-risk-exposure-model-definition
    provides: "Vulnerability.risk_exposure_score + RISK_SCORE_TIER_CRITICAL/HIGH/MEDIUM constants (app/assets/risk_score.py)"
  - phase: 13-tickets-list-detail
    provides: "the SlaPill primitive (frontend/src/components/tickets/sla-pill.tsx) this plan extends"
provides:
  - "sla_tier_service.py: tier_for_score, severity_to_tier, get_tier_policy, compute_sla_state, resolve_state_for_vuln, run_sla_tier_pass"
  - "sla_state + sla_due_at on VulnerabilityResponse AND VulnerabilitySummary (schema contract for Plans 02-06)"
  - "SlaPill optional server-truth `state` prop (frontend contract for Plans 02-06 / drill panel, admin pane)"
  - "scheduler.py SLA tick now calls run_sla_tier_pass (replaces the severity-keyed backfill+breach-check)"
affects: [36-02, 36-03, 36-04, 36-05, 36-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Read-time state resolution: sla_state is computed fresh at request time (resolve_state_for_vuln + now=datetime.now(UTC)) inside service.py, decoupled from the 60s scheduler tick's write cadence — a finding gets a live, correct sla_state even before its first scheduler pass"
    - "Custom-or-default tenant JSONB policy merge (get_tier_policy mirrors sla_service.get_sla_days's per-key fallback shape) over Tenant.sla_config[\"tier_policy\"]"
    - "Derived-mirror write: sla_breached stays a boolean column written by the NEW engine so pre-existing consumers (ticket SlaPill, alerts.py, metrics) keep working unmodified"

key-files:
  created:
    - backend/app/vulnerabilities/sla_tier_service.py
    - backend/tests/test_sla_tier_service.py
  modified:
    - backend/app/vulnerabilities/schemas.py
    - backend/app/vulnerabilities/service.py
    - backend/app/connectors/scheduler.py
    - backend/tests/test_vuln_sort.py
    - frontend/src/components/tickets/sla-pill.tsx
    - frontend/src/components/tickets/sla-pill.test.tsx
    - frontend/src/components/vulnerabilities/vuln-table.tsx

key-decisions:
  - "get_tier_policy/resolve_state_for_vuln typed dict[str, Any] (not a TypedDict) to keep the mypy-baseline gate at 0 new errors with minimal footprint, matching the Any-import precedent already used elsewhere in this package"
  - "SlaPill's not_tracked state reuses the existing 'unknown' tier's visual TONE but renders distinct copy ('No SLA', not 'Unknown') per UI-SPEC — tone and copy diverge deliberately since D-12's below-floor signal and a null-dueAt signal are different situations to the analyst"
  - "run_sla_tier_pass fetches ALL OPEN/IN_PROGRESS vulns per tenant per tick (no incremental/changed-only filtering) and resyncs every ticket group unconditionally — matches the plan's explicit 'start-simple recompute-all' guidance (Open Question #5); optimize only if tick duration becomes a measured problem"

patterns-established:
  - "Pattern: extend an existing client-computed pill primitive with an optional server-truth prop that short-circuits the client computation entirely when present, leaving every pre-existing caller byte-identical when the prop is absent"

requirements-completed: [SLA-01, SLA-02]

coverage:
  - id: D1
    description: "Risk-tier SLA engine core: tier_for_score (D-12 floor), severity_to_tier (D-03 fallback), get_tier_policy (custom-or-default merge), compute_sla_state (D-02 tier+elapsed-% formula, scales per tier)"
    requirement: "SLA-01"
    verification:
      - kind: unit
        ref: "backend/tests/test_sla_tier_service.py (27 boundary/fallback/policy-merge tests)"
        status: pass
    human_judgment: false
  - id: D2
    description: "resolve_state_for_vuln + run_sla_tier_pass: per-finding resolution (scored/NULL-fallback/below-floor) and the scheduler-tick DB write path (sla_due_at + sla_breached derived mirror, D-08)"
    requirement: "SLA-01"
    verification:
      - kind: unit
        ref: "backend/tests/test_sla_tier_service.py (4 resolve_state_for_vuln tests)"
        status: pass
      - kind: integration
        ref: "backend/tests/test_sla_tier_service.py::test_run_sla_tier_pass_writes_due_date_and_breached_mirror"
        status: pass
      - kind: integration
        ref: "backend/tests/test_sla_tier_service.py::test_run_sla_tier_pass_ignores_remediated_vulns"
        status: pass
    human_judgment: false
  - id: D3
    description: "scheduler.py SLA tick block replaced (run_sla_tier_pass in, backfill_sla_due_dates+check_sla_breaches out), same own-session/try-except/commit isolation shape, no new scheduler registered"
    requirement: "SLA-01"
    verification:
      - kind: other
        ref: "grep -c run_sla_tier_pass backend/app/connectors/scheduler.py (>=1) && grep -c check_sla_breaches backend/app/connectors/scheduler.py (==0)"
        status: pass
    human_judgment: false
  - id: D4
    description: "GET /vulnerabilities (list) and GET /vulnerabilities/{id} (detail) responses each carry sla_state + sla_due_at, read-time resolved once per tenant policy lookup"
    requirement: "SLA-02"
    verification:
      - kind: integration
        ref: "backend/tests/test_vuln_sort.py::test_list_response_includes_sla_state_key"
        status: pass
      - kind: integration
        ref: "backend/tests/test_vuln_sort.py::test_detail_response_includes_sla_state_key"
        status: pass
    human_judgment: false
  - id: D5
    description: "SlaPill extended with an optional server-truth `state` prop (on_track/approaching/breached/not_tracked) that skips computeTier() and maps directly onto the existing 4-tone vocabulary; not_tracked renders 'No SLA'"
    requirement: "SLA-02"
    verification:
      - kind: unit
        ref: "frontend/src/components/tickets/sla-pill.test.tsx (6 new state-prop tests, including a contradictory-dueAt-is-ignored proof)"
        status: pass
    human_judgment: false
  - id: D6
    description: "vuln-table.tsx SLA column (desktop td + mobile card) renders <SlaPill state dueAt /> in place of the removed local slaBand() formatter"
    requirement: "SLA-02"
    verification:
      - kind: unit
        ref: "frontend/src/components/vulnerabilities/vuln-table.test.tsx (13 pre-existing tests, unmodified, all still pass)"
        status: pass
      - kind: other
        ref: "grep -c slaBand frontend/src/components/vulnerabilities/vuln-table.tsx (==0)"
        status: pass
    human_judgment: true
    rationale: "Only jsdom unit assertions (className/text content) were run this plan — no live-browser/Playwright screenshot proves the SlaPill's actual visual placement, right-alignment, and color contrast on the real finding row (desktop table + mobile card) in a running app. Logic correctness is proven; live visual appearance is not."
  - id: D7
    description: "Ticket SlaPill call sites (tickets-table.tsx, kanban-card.tsx, ticket-drill-content.tsx) remain untouched — the new state prop is optional/additive, zero behavior change for existing tickets callers"
    verification:
      - kind: other
        ref: "git diff --name-only ac67b90 HEAD | grep -E 'tickets-table.tsx|kanban-card.tsx|ticket-drill-content.tsx' (no match)"
        status: pass
      - kind: unit
        ref: "frontend/src/components/tickets/tickets-table.test.tsx + ticket-drill-content.test.tsx (19 pre-existing tests, unmodified, all still pass)"
        status: pass
    human_judgment: false

duration: ~30min
completed: 2026-08-13
status: complete
---

# Phase 36 Plan 01: Lead Tracer — Risk-Tier SLA Engine Summary

**A tenant-configurable risk-tier SLA engine (critical=7d/high=30d/moderate=90d default) computes live on_track/approaching/breached/not_tracked state off the v4.0 risk_exposure_score, writes durable due dates every scheduler tick, and surfaces the server-computed state on the vulnerability finding row via an extended SlaPill — proven end-to-end for the default-policy path.**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-08-13 (context load + Task 1)
- **Completed:** 2026-08-13T11:39:26Z
- **Tasks:** 3 (Task 1 RED, Task 2 GREEN, Task 3 tracer wiring) + 1 self-identified deviation (DB-integration test coverage)
- **Files modified:** 9 (2 created, 7 modified)

## Accomplishments

- Risk-tier SLA formula (`tier_for_score`/`compute_sla_state`/`resolve_state_for_vuln`) built as pure, exhaustively boundary-tested functions — every locked boundary (score==80/50/20/19, exact approaching-%, exact due-date, per-tier scaling 7d vs 90d, NULL-score severity fallback, below-floor not_tracked) has a dedicated test
- `run_sla_tier_pass` scheduler-tick entrypoint writes tier-based `sla_due_at` + the `sla_breached` derived mirror (D-08) and resyncs every affected ticket group's materialized SLA — wired into the existing 60s tick in place of the old severity-keyed backfill+breach-check, no new scheduler
- `sla_state`/`sla_due_at` now populate on both `GET /vulnerabilities` (list) and `GET /vulnerabilities/{id}` (detail), read-time resolved so state is live even between scheduler ticks — closes Pitfall 3 (FastAPI silently drops undeclared response-model attributes)
- `SlaPill` gained an optional server-truth `state` prop consumed by the finding row (`vuln-table.tsx`), while all three pre-existing ticket call sites (list, kanban, drill panel) are provably untouched and their behavior is byte-identical

## Task Commits

Each task was committed atomically:

1. **Task 1: Failing unit tests for the tier engine** - `aab6882` (test) — RED via genuine `ModuleNotFoundError`
2. **Task 2: Implement the tier engine + add SLA fields to both schemas** - `17b281c` (feat) — GREEN, 27/27, 0 new mypy-baseline errors
3. **Task 3: Wire the tracer end-to-end** - `59fb0b8` (feat) — scheduler + service.py + SlaPill + vuln-table.tsx + live integration tests
4. **Deviation follow-up: run_sla_tier_pass DB-integration coverage** - `84117b9` (test) — closes a self-identified verification gap

_Note: Task 1/2 followed the tdd="true" RED→GREEN cycle; Task 3 is `type="tracer"` (production-quality implementation + real `<verify>` + commit, no separate REFACTOR gate needed)._

## Files Created/Modified

- `backend/app/vulnerabilities/sla_tier_service.py` — the engine: `DEFAULT_TIER_POLICY`, `DEFAULT_APPROACHING_PCT`, `tier_for_score`, `severity_to_tier`, `get_tier_policy`, `compute_sla_state`, `resolve_state_for_vuln`, `run_sla_tier_pass`
- `backend/tests/test_sla_tier_service.py` — 29 tests: 27 pure-function boundary/fallback/policy tests + 2 DB-backed `run_sla_tier_pass` integration tests
- `backend/app/vulnerabilities/schemas.py` — `sla_state: str | None` + `sla_due_at: datetime | None` added to `VulnerabilityResponse` and `VulnerabilitySummary`
- `backend/app/vulnerabilities/service.py` — `list_vulnerabilities` and `get_vulnerability` resolve the tenant's tier policy once and attach read-time `sla_state`/`sla_due_at` to every row
- `backend/app/connectors/scheduler.py` — SLA tick block now calls `run_sla_tier_pass` per active tenant, same isolation shape
- `backend/tests/test_vuln_sort.py` — 2 new live integration tests proving `sla_state` on both list and detail responses
- `frontend/src/components/tickets/sla-pill.tsx` — optional `state?: SlaPillState` prop, server-truth path skips `computeTier()`
- `frontend/src/components/tickets/sla-pill.test.tsx` — 6 new tests for the 4-state prop path + a computeTier-is-never-consulted proof
- `frontend/src/components/vulnerabilities/vuln-table.tsx` — SLA column (desktop + mobile) now renders `<SlaPill state={row.sla_state} dueAt={row.sla_due_at} />`, local `slaBand()` removed

## Decisions Made

- `get_tier_policy`/`resolve_state_for_vuln` typed `dict[str, Any]` rather than a `TypedDict` — kept the mypy-baseline gate at 0 new errors with the smallest diff, matching the `Any`-import precedent already used elsewhere in `app.vulnerabilities`
- `SlaPill`'s `not_tracked` state reuses the existing `unknown` tier's visual tone (faint/gray) but renders distinct copy — `"No SLA"`, never `"Unknown"` — per UI-SPEC: a below-floor D-12 signal and a null-`dueAt` client signal are different situations to the analyst even though they share a tone
- `run_sla_tier_pass` recomputes ALL of a tenant's OPEN/IN_PROGRESS vulns and resyncs every ticket group unconditionally every tick (no incremental/changed-only filtering) — matches the plan's explicit "start simple, optimize only if measured" guidance (Open Question #5)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test CVE ID exceeded the `cve_id` column's `String(20)` limit**
- **Found during:** Task 3 (writing the live integration test for list-response `sla_state`)
- **Issue:** `"CVE-SLASTATE-FALLBACK"` is 21 characters; the DB insert failed with `StringDataRightTruncationError` against the real Postgres schema
- **Fix:** Shortened the three new test CVE IDs to a `CVE-SLA36-*` prefix (max 18 chars)
- **Files modified:** backend/tests/test_vuln_sort.py
- **Verification:** `pytest tests/test_vuln_sort.py -q` — 9/9 pass
- **Committed in:** 59fb0b8 (Task 3 commit)

**2. [Rule 1 - Bug] mypy: bare `dict` return/param types + branch-type mismatch in the new engine**
- **Found during:** Task 2 (post-implementation mypy sweep, before commit)
- **Issue:** `get_tier_policy`/`resolve_state_for_vuln` used bare `dict` (mypy `type-arg`); `resolve_state_for_vuln`'s `tier` variable was inferred `str` from its first branch, then mypy flagged the second branch's `str | None` assignment as incompatible
- **Fix:** Parameterized both as `dict[str, Any]`; added an explicit `tier: str | None` annotation before the if/else
- **Files modified:** backend/app/vulnerabilities/sla_tier_service.py
- **Verification:** `mypy app/ | mypy-baseline filter --allow-unsynced` → 0 new errors (confirmed both before and after the fix, isolating exactly these 3 as newly introduced)
- **Committed in:** 17b281c (Task 2 commit)

**3. [Rule 2 - Missing Critical] Added direct DB-integration coverage for `run_sla_tier_pass`**
- **Found during:** Post-Task-3 self-review, before writing this Summary
- **Issue:** `run_sla_tier_pass` is a named `must_haves.artifacts` function that every downstream Phase 36 plan depends on, but Task 3's own verification only proved it structurally (wired into `scheduler.py`) plus its pure formula dependencies (already exhaustively unit-tested). The live `GET /vulnerabilities` integration tests exercise an INDEPENDENT read-time resolution path in `service.py`, not this function's own DB write path — so `run_sla_tier_pass`'s actual persistence behavior had zero direct proof
- **Fix:** Added two async DB-backed tests: one seeding an OPEN vuln and asserting `sla_due_at`/`sla_breached` are written correctly after a call; one seeding a REMEDIATED vuln and asserting it is never retroactively touched. Extended the file's `_vuln()` helper with optional `tenant_id`/`status` params (backward-compatible — all existing call sites use keyword args)
- **Files modified:** backend/tests/test_sla_tier_service.py
- **Verification:** `pytest tests/test_sla_tier_service.py -q` — 29/29 pass; 0 new mypy-baseline errors
- **Committed in:** 84117b9 (follow-up commit)

---

**Total deviations:** 3 auto-fixed (2 Rule 1 bugs, 1 Rule 2 missing verification)
**Impact on plan:** All three fixes are corrections/hardening with zero scope creep — no new features, no architectural changes. The Rule 2 addition specifically de-risks the artifact contract downstream plans 02-06 depend on.

## Issues Encountered

None beyond the deviations documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The artifact contract this plan promised is fully delivered and tested: `tier_for_score`, `severity_to_tier`, `compute_sla_state`, `get_tier_policy`, `resolve_state_for_vuln`, `run_sla_tier_pass` all exist in `sla_tier_service.py` exactly as named; `sla_state`/`sla_due_at` are on both vuln schemas; `SlaPill`'s `state` prop is live.
- Plan 02 (escalation channels/events) can now read `run_sla_tier_pass`'s written `sla_due_at`/`sla_breached` and detect state transitions by comparing before/after `resolve_state_for_vuln` calls — the exactly-once escalation gate (D-07) has a correct, tested state source to key off of.
- Plan 05/06 (admin pane, drill panel) can call `get_tier_policy`/read `sla_state` directly — no further backend plumbing needed for the read side.
- Known gap for a later plan / the phase verifier: no live-browser/Playwright visual check of the SlaPill on the real finding row this plan (see coverage D6) — jsdom unit coverage only. Recommend a spot-check during `/gsd-verify-work 36` or the phase's UI gate.
- `backend/app/notifications/alerts.py`'s `_check_sla_breaches` (in-app breach notification) is UNTOUCHED per this plan's file scope — it continues reading `Vulnerability.sla_breached`, now written by the new engine instead of the old one, with no code change required. Full D-08 reconciliation (retiring/gating this function so a breach fires exactly one in-app signal via the new `sla_escalation` category) is explicitly Plan 03's job, not this plan's.

---
*Phase: 36-remediation-sla-engine-escalation*
*Completed: 2026-08-13*

## Self-Check: PASSED

All 9 key files verified present on disk (`[ -f ]`); all 4 commit hashes
(`aab6882`, `17b281c`, `59fb0b8`, `84117b9`) verified in `git log --oneline --all`.
