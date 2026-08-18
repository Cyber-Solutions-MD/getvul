---
phase: 38-remediation-campaigns
plan: 03
subsystem: api
tags: [fastapi, sqlalchemy, postgres, rbac, audit, campaigns, mttr]

# Dependency graph
requires:
  - phase: 38-remediation-campaigns
    provides: "Plan 01's persisted Campaign identity row (closed_at/closed_by_user_id/close_trigger columns already present) + get_or_create_campaign/get_campaign_progress/list_campaigns + RBAC/audit/tenant-scoping precedent this plan builds on additively; Plan 02's bulk-ticketing surface (untouched by this plan)"
provides:
  - "get_campaign_mttr() -- D-12 compute-on-read MTTR: AVG(RemediationEvent.duration_seconds) joined through Vulnerability.remediation_id, Decimal->float coerced (Pitfall 7), null (never 0/error) when no member has ever been remediated"
  - "mttr_seconds: float | null on CampaignDetail, wired into GET /{id}"
  - "apply_lifecycle_transition() -- lazy-on-read auto-complete (D-13) / auto-reactivate (D-14) detection invoked from GET /{id} after computing progress; closed_at-guarded single-write per transition (D-19); close_trigger=='manual' is never touched (D-17 sticky)"
  - "POST /api/v1/campaigns/{campaign_id}/close -- require_analyst manual early-close: closed_at + closed_by_user_id + close_trigger='manual' + one real-actor campaign.close audit row"
  - "System-actor campaign.close (auto_complete) / campaign.reactivate audit rows (user_id=None, user_email='system:campaign-complete'), constructed directly (reopen_vulnerability precedent), derived only from server-computed progress counts"
affects: [38-04-remediation-grouped-page, 38-05-campaign-views]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Lazy-on-read lifecycle transition detection (Pattern 6): a require_viewer GET can trigger a system-attributed persisted write, gated by a closed_at IS NULL / IS NOT NULL guard that makes the transition single-write per direction -- no scheduler tick, no hook in the Phase 36/37 remediation helpers"
    - "Durable-history MTTR aggregation: RemediationEvent rows are NOT filtered by the live membership status set (_CAMPAIGN_MEMBER_STATUSES) -- a member that was remediated and later recurred (Phase 37 reopen) still contributes its historical duration to MTTR, since the RemediationEvent row is never deleted on reopen"

key-files:
  created: []
  modified:
    - backend/app/campaigns/service.py
    - backend/app/campaigns/schemas.py
    - backend/app/campaigns/router.py
    - backend/tests/test_campaigns.py

key-decisions:
  - "get_campaign_mttr() joins RemediationEvent to Vulnerability on remediation_id WITHOUT filtering by _CAMPAIGN_MEMBER_STATUSES -- a RemediationEvent row is durable Phase-36 history that survives a later reopen-on-recurrence (Phase 37 D-04), so MTTR always reflects every remediation this group has ever completed, not just currently-REMEDIATED members. This is a deliberate scope difference from get_campaign_progress's live-membership filter, not an oversight."
  - "apply_lifecycle_transition() is invoked from GET /{campaign_id} AFTER get_campaign_progress and BEFORE get_campaign_mttr / _derive_status -- ordering matters: _derive_status reads the (possibly just-mutated) campaign.closed_at, so the transition must land on the same in-memory ORM object before status derivation runs. No separate D-17-aware branch was needed in _derive_status itself -- once the lazy transition clears closed_at on reactivation (or sets it on auto-complete), the pre-existing closed_at-is-not-None-wins check already produces the D-17-aware result."
  - "The system-actor AuditLog rows in apply_lifecycle_transition are constructed directly (db.add(AuditLog(...))), never via the audit() helper -- mirrors reopen_vulnerability's established system-actor precedent (vulnerabilities/service.py:464-476), since audit() requires a CurrentUser | None but always stamps a real ip_address/details shape tied to the request context, which a lazy background-detected transition doesn't have."
  - "CAMP-04 marked [x] complete in REQUIREMENTS.md -- all three declaring plans (38-01, 38-02, 38-03) now have SUMMARY.md files. CAMP-03 remains [ ] pending -- it is also declared by 38-05 (campaign list/detail views), which has not yet produced a SUMMARY.md. Verified directly against every phase-38 PLAN.md's requirements: frontmatter field (the SDK's requirements ready-ids verb is not installed in this environment, per 38-02's identical prior finding); only requirements mark-complete is available via gsd-tools.cjs."

patterns-established:
  - "A single service function (apply_lifecycle_transition) owns both directions of a bistable lazy-on-read transition (complete <-> reactivate), each branch independently idempotent via its own closed_at guard, rather than two separate detector functions"

requirements-completed: [CAMP-04]  # CAMP-03 NOT marked -- shared with 38-05, which has no SUMMARY.md yet (see key-decisions)

coverage:
  - id: D1
    description: "GET /api/v1/campaigns/{id} returns mttr_seconds = average of member RemediationEvent.duration_seconds (float-coerced), computed fresh on every read"
    requirement: "CAMP-03"
    verification:
      - kind: unit
        ref: "backend/tests/test_campaigns.py#test_campaign_mttr_average"
        status: pass
    human_judgment: false
  - id: D2
    description: "mttr_seconds is null (not 0, not an error) when no member has ever been remediated"
    requirement: "CAMP-03"
    verification:
      - kind: unit
        ref: "backend/tests/test_campaigns.py#test_campaign_mttr_null_when_none_remediated"
        status: pass
    human_judgment: false
  - id: D3
    description: "A member with a closed/resolved Ticket but status IN_PROGRESS (not rescan-verified REMEDIATED) is counted in in_progress, never done, and contributes no MTTR (D-09: done keys off status REMEDIATED only)"
    requirement: "CAMP-03"
    verification:
      - kind: unit
        ref: "backend/tests/test_campaigns.py#test_campaign_d09_ticket_closed_not_remediated_stays_in_progress"
        status: pass
    human_judgment: false
  - id: D4
    description: "A finding discovered on a newly-seen asset after campaign launch is counted in the live total denominator on the very next read, with no membership row ever written (D-03 live membership)"
    requirement: "CAMP-03"
    verification:
      - kind: unit
        ref: "backend/tests/test_campaigns.py#test_live_membership_grows"
        status: pass
    human_judgment: false
  - id: D5
    description: "POST /{id}/close (require_analyst) sets closed_at + closed_by_user_id + close_trigger='manual' and writes exactly one real-actor campaign.close audit row; a viewer gets 403"
    requirement: "CAMP-04"
    verification:
      - kind: unit
        ref: "backend/tests/test_campaigns.py#test_campaign_actions_audited"
        status: pass
    human_judgment: false
  - id: D6
    description: "The first read that observes done==total>0 on an open campaign sets closed_at + close_trigger='auto_complete' and writes exactly ONE system-actor campaign.close audit row; a second read of the already-complete campaign writes no additional row (D-13/D-19 audit-once idempotence)"
    requirement: "CAMP-04"
    verification:
      - kind: unit
        ref: "backend/tests/test_campaigns.py#test_auto_complete_audited_once"
        status: pass
    human_judgment: false
  - id: D7
    description: "An auto-completed campaign whose member recurs (reopens) flips COMPLETE->ACTIVE on the next read and writes exactly one campaign.reactivate system-actor audit row (D-14)"
    requirement: "CAMP-04"
    verification:
      - kind: unit
        ref: "backend/tests/test_campaigns.py#test_reopen_reactivates_campaign"
        status: pass
    human_judgment: false
  - id: D8
    description: "A manually-closed campaign (close_trigger='manual') stays closed on member recurrence -- no reactivation, no campaign.reactivate audit row (D-17 sticky close)"
    requirement: "CAMP-04"
    verification:
      - kind: unit
        ref: "backend/tests/test_campaigns.py#test_manual_close_is_sticky_no_reactivation"
        status: pass
    human_judgment: false
  - id: D9
    description: "Zero new scheduler tick, zero edits to Phase 36/37 files (mark_vulnerability_remediated/reopen_vulnerability/scheduler) -- lifecycle detection is lazy-on-read only"
    requirement: "CAMP-04"
    verification:
      - kind: other
        ref: "grep -rn campaign backend/app/vulnerabilities/service.py backend/app/connectors/scheduler.py (zero matches)"
        status: pass
    human_judgment: false

# Metrics
duration: ~25min
completed: 2026-08-18
status: complete
---

# Phase 38 Plan 03: Live Progress + MTTR + Lifecycle Audit Summary

**Campaign burndown made real: `get_campaign_mttr()` (D-12, average `RemediationEvent.duration_seconds`, Decimal->float coerced) wired into `GET /{id}`, plus a lazy-on-read `apply_lifecycle_transition()` that auto-completes (D-13), audits exactly once (D-19), auto-reactivates on recurrence (D-14), and treats a manual `POST /{id}/close` as sticky-terminal (D-17) -- with zero scheduler tick and zero edits to the Phase 36/37 remediation helpers.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-08-18T08:10:00Z (approx.)
- **Completed:** 2026-08-18T08:34:09Z
- **Tasks:** 2 (both `type="auto" tdd="true"`, both complete)
- **Files modified:** 4 (0 created, 4 modified)

## Accomplishments
- `get_campaign_mttr()` proven to average member `RemediationEvent.duration_seconds` and return a genuine `float` (not a string, not a Decimal-shaped JSON surprise -- Pitfall 7), returning `None` with HTTP 200 (never `0`, never a crash) when no member has ever been remediated
- D-09 semantics proven live: a finding with a closed/resolved `Ticket` but status `IN_PROGRESS` (never rescan-verified to `REMEDIATED`) stays counted in `in_progress`, never `done`, and contributes no MTTR
- D-03 live-membership growth proven: a finding discovered on a newly-seen asset after campaign launch is counted in `total` on the very next read, with zero membership rows ever written
- `POST /{campaign_id}/close` proven: analyst-only (viewer 403), sets `closed_at`/`closed_by_user_id`/`close_trigger="manual"`, writes exactly one real-actor `campaign.close` audit row
- Lazy auto-complete proven audited exactly once: the first read that observes `done==total>0` sets `closed_at`/`close_trigger="auto_complete"` and writes one system-actor (`user_id=None`, `user_email="system:campaign-complete"`) `campaign.close` row; a second read of the same complete campaign writes zero additional rows (D-19 idempotence, `closed_at IS NULL` guard)
- Auto-reactivate proven live: reopening a member after auto-complete flips the campaign `COMPLETE -> ACTIVE` on the next read and writes exactly one `campaign.reactivate` system-actor row (D-14)
- D-17 sticky-close proven: a manually-closed campaign (`close_trigger="manual"`) stays `COMPLETE` through a member recurrence cycle (remediate -> reopen) -- `apply_lifecycle_transition`'s reactivate branch never fires because it only matches `close_trigger=="auto_complete"`
- Zero-scheduler-tick / zero-Phase-36-37-file-edit constraint verified via `grep -rn campaign backend/app/vulnerabilities/service.py backend/app/connectors/scheduler.py` returning no matches

## Task Commits

Each task was committed atomically:

1. **Task 1: Campaign MTTR aggregation + wire into GET /{id} (D-12, D-09 semantics)** — `5bcd725` (feat)
2. **Task 2: Manual close endpoint + lazy-on-read auto-complete/reactivate (D-13/14/17/19)** — `220cd2e` (feat)

**Plan metadata:** _pending this commit_ (docs: complete plan)

_Note: both `tdd="true"` tasks followed genuine RED->GREEN within this session (tests written and run to confirm real failures -- `KeyError: 'mttr_seconds'` for Task 1, `404 Not Found` for Task 2's `/close` route -- before the implementation was added), but were committed as single combined test+implementation commits per task rather than separate `test(...)`->`feat(...)` sub-commits, matching the identical deviation Plans 01/02 documented for this repo._

## Files Created/Modified
- `backend/app/campaigns/service.py` — adds `get_campaign_mttr()` (AVG join, Decimal->float coercion, D-12) and `apply_lifecycle_transition()` (bistable lazy-on-read complete/reactivate detector, D-13/14/17/19); imports `RemediationEvent` and `AuditLog`
- `backend/app/campaigns/schemas.py` — `CampaignDetail` gains `mttr_seconds: float | None`
- `backend/app/campaigns/router.py` — `GET /{campaign_id}` calls `apply_lifecycle_transition` after computing progress and populates `mttr_seconds`; new `POST /{campaign_id}/close` (require_analyst, audit, commit)
- `backend/tests/test_campaigns.py` — 8 new tests: 4 MTTR/D-09/D-03 (`test_campaign_mttr_average`, `test_campaign_mttr_null_when_none_remediated`, `test_campaign_d09_ticket_closed_not_remediated_stays_in_progress`, `test_live_membership_grows`) + 4 lifecycle (`test_campaign_actions_audited`, `test_auto_complete_audited_once`, `test_reopen_reactivates_campaign`, `test_manual_close_is_sticky_no_reactivation`), plus a local `_audit_rows` test helper (24/24 file total, up from Plan 02's 16)

## Decisions Made
- `get_campaign_mttr()` deliberately does NOT filter by `_CAMPAIGN_MEMBER_STATUSES` (the live-membership status set `get_campaign_progress` uses) -- `RemediationEvent` rows are durable Phase-36 history that outlive a later reopen-on-recurrence (Phase 37 D-04), so MTTR reflects every remediation this group has EVER completed, not just currently-REMEDIATED members. This is a deliberate scope difference, not an inconsistency with the progress query.
- `apply_lifecycle_transition` runs inside `GET /{campaign_id}` strictly AFTER `get_campaign_progress` and BEFORE `_derive_status`/`get_campaign_mttr` -- ordering is load-bearing because `_derive_status` reads `campaign.closed_at` off the same in-memory ORM object the transition may have just mutated. No separate D-17-aware rewrite of `_derive_status` was needed: the pre-existing "`closed_at is not None` wins" check already produces the correct D-17-aware result once the lazy transition has run.
- System-actor `AuditLog` rows (`campaign.close` auto-complete, `campaign.reactivate`) are constructed directly via `db.add(AuditLog(...))`, never through the `audit()` helper -- mirrors `reopen_vulnerability`'s established system-actor precedent (`vulnerabilities/service.py:464-476`); `audit()` is reserved for real-user-attributed actions (the manual `/close` endpoint uses it correctly).
- CAMP-04 marked `[x]` complete in REQUIREMENTS.md -- all three declaring plans (38-01, 38-02, 38-03) now have SUMMARY.md files. CAMP-03 stays `[ ]` -- it is also declared by 38-05 (campaign list/detail views), not yet executed. Verified directly against every phase-38 `PLAN.md`'s `requirements:` frontmatter field, since the SDK's `requirements ready-ids` verb is not installed in this environment (only `requirements mark-complete` is available via `gsd-tools.cjs`) -- same workaround Plan 02 used.

## Deviations from Plan

None — plan executed exactly as written. `get_campaign_mttr()`'s shape, `apply_lifecycle_transition`'s D-13/14/17/19 branch logic, and the `POST /{id}/close` endpoint all match the plan's `<interfaces>` block verbatim (AVG+float coercion, closed_at-guarded single-write branches, system-actor construction mirroring `reopen_vulnerability`, D-17 stickiness via the `close_trigger=="auto_complete"` filter on the reactivate branch).

## Issues Encountered
- Docker Desktop was not running at session start (`Cannot connect to the Docker daemon`) -- started via `open -a Docker` + polling `docker info` until ready, then `docker start getvul-postgres-1 getvul-redis-1`. Not a plan defect -- an environment-setup step outside the plan's scope. Confirmed migration head `049_add_campaigns` matched with no fresh migration needed.
- Two prior attempts at this plan were interrupted by the machine sleeping mid-session (per the orchestrator's clean-base note); this execution started from a verified-clean `b8e78ad` base with no partial artifacts to reconcile.

## User Setup Required
None — no external service configuration required. No new environment variables, no new dependencies (zero new packages; reuses `RemediationEvent`/`AuditLog` models that already existed from Phase 36).

## Next Phase Readiness
- `mttr_seconds` on `CampaignDetail` and the `ACTIVE`/`COMPLETE` status derivation (now lifecycle-transition-aware) are ready for Plan 04 (remediation-grouped entry page) and Plan 05 (campaign list/detail views) to render with no backend changes required.
- `POST /{id}/close` is ready for a UI "Close Campaign" action; the response is a minimal `{"status": "closed"}` -- Plan 05's UI author should re-fetch `GET /{id}` afterward to render the updated `closed_at`/status rather than relying on the close response body for display state.
- No blockers. Phase 38 (`remediation-campaigns`) is now 3/5 plans complete -- CAMP-01/CAMP-02/CAMP-04 all fully shipped; CAMP-03 remains open pending Plan 05.

---
*Phase: 38-remediation-campaigns*
*Completed: 2026-08-18*

## Self-Check: PASSED

**Files verified to exist:**
- FOUND: backend/app/campaigns/service.py
- FOUND: backend/app/campaigns/schemas.py
- FOUND: backend/app/campaigns/router.py
- FOUND: backend/tests/test_campaigns.py

**Commits verified to exist (`git log --oneline --all`):**
- FOUND: 5bcd725 (Task 1)
- FOUND: 220cd2e (Task 2)

**Test suite re-verified green:** `ENCRYPTION_KEY=<fernet> JWT_SECRET_KEY=test-secret pytest backend/tests/test_campaigns.py -v` — 24/24 passed.

**Lazy-transition-only constraint re-verified:** `grep -rn campaign backend/app/vulnerabilities/service.py backend/app/connectors/scheduler.py` — zero matches.

**ruff/mypy re-verified:** `ruff check`/`ruff format --check` clean on all 4 touched files; `mypy app/ | mypy-baseline filter --allow-unsynced` shows zero campaigns-attributable new violations.
