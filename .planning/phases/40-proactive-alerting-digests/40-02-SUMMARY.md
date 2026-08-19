---
phase: 40-proactive-alerting-digests
plan: 02
subsystem: alerting
tags: [sqlalchemy, fastapi, pytest, tracer, kev, epss]

# Dependency graph
requires:
  - phase: 40-proactive-alerting-digests
    plan: "01"
    provides: "AlertingGuard model + alerting_guard table, Tenant.alerting_config/alerting_last_digest_sent_at, alerting_config.py::DEFAULT_ALERTING_CONFIG/merged_alerting_config, 5 RED test scaffolds in test_alerts_kev_epss.py"
  - phase: 36-remediation-sla-engine-escalation
    provides: "Fernet-encrypted channel credential store (_build_channel_config + dispatch_channel) reused verbatim per D-19"
  - phase: 39-exception-risk-acceptance-workflow
    provides: "active_exception_subquery(tenant_id, now) — D-20 exclusion, reused verbatim, not re-derived"
provides:
  - "_check_new_kev_epss(db, tenant) -> int — ALERT-01 detection sibling wired into run_alert_checks (D-03)"
  - "AlertingGuard once-only subtraction proven live: cold-start silent seed (D-06), exactly-once fire, durable re-fire prevention across ticks"
  - "app.assets.directory.get_directory_user — owner-resolution helper extracted from assets/router.py, importable from the notifications layer without router coupling"
  - "_fire_kev_epss_alert — owner email / admin+channel fallback (D-10), tenant channel dispatch (D-07/D-19), in-app twin (category new_kev_epss), scheduler-side AuditLog (action alert.fire)"
affects: [40-03, 40-04, 40-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "KEV takes precedence over EPSS at the QUERY level (epss slice explicitly excludes cisa_kev=True rows) so a finding that is both KEV-listed and EPSS-qualifying is classified/fired under exactly one trigger_type per pass, never two — kept as a property of each slice's own SQL predicate, not runtime dedup bookkeeping"
    - "Durable guard-table subtraction (AlertingGuard, tenant/cve/asset/trigger_type-keyed) as the dedup primitive for transition-only alerting — distinct from the time-windowed _notification_exists() pattern used by the pre-existing sibling checks in the same module"
    - "Scheduler-side AuditLog constructed directly (never audit(db, None, ...)) — same precedent as sla_tier_service.py's _audit_escalation_fire and ai/audit.py's audit_log_ai_call"

key-files:
  created:
    - backend/app/assets/directory.py
  modified:
    - backend/app/notifications/alerts.py
    - backend/app/assets/router.py

key-decisions:
  - "KEV/EPSS mutual exclusivity resolved at the SQL predicate level (epss query adds `~Vulnerability.cisa_kev.is_(True)`), not via extra runtime dedup bookkeeping. This was required to satisfy test_new_kev_match_fires_once's `.scalar_one()` guard-row lookup (a finding qualifying under both conditions must produce exactly one guard row / one fire / one audit row, never two) while still writing a durable guard row for whichever single trigger_type actually fired -- consistent with the 'exactly once per (cve, asset, trigger_type)' truth without ever double-notifying an owner for one underlying finding."
  - "get_directory_user extracted to a new backend/app/assets/directory.py rather than moved into notifications/alerts.py or left in assets/router.py -- keeps the notifications layer free of any FastAPI/Pydantic router coupling (research A5) while assets/router.py's two existing call sites re-import it under the same private alias (_get_directory_user) for a zero-behavior-change diff."
  - "_fire_kev_epss_alert built in two commits (Task 1: minimal in-app-only stub; Task 2: full owner/channel/audit) rather than one -- mirrors the plan's own task split and keeps each commit's diff scoped to what its own acceptance criteria actually require."

requirements-completed: []  # ALERT-01 stays open -- shared across all 5 Phase 40 plans; only the LAST declaring plan (05) flips it per the Phase 38/40-01 precedent.

coverage:
  - id: D1
    description: "_check_new_kev_epss detects newly-KEV/EPSS-qualifying (cve, asset) pairs via AlertingGuard subtraction, seeds silently on cold start (D-06), excludes SUPPRESSED/FALSE_POSITIVE + actively-excepted findings (D-20)"
    requirement: "ALERT-01"
    verification:
      - kind: unit
        ref: "cd backend && pytest tests/test_alerts_kev_epss.py -k 'fires_once or refire or seeds or excluded' -x -- 4/4 pass (xpass under the file's xfail(strict=False) marker)"
        status: pass
      - kind: static
        ref: "grep -c 'async def _check_new_kev_epss' alerts.py == 1; grep -c '_check_new_kev_epss' alerts.py == 2 (def + call site); grep 'epss_score >=' present; active_exception_subquery imported+applied"
        status: pass
    human_judgment: false
  - id: D2
    description: "Owner resolution (resolved owner emailed directly, unresolved falls back to admins+channel D-10), tenant channel push via the shared Phase-36 dispatch seam (D-07/D-19, fail-isolated), in-app twin (category new_kev_epss), scheduler-side AuditLog (action alert.fire, real tenant_id, never audit(db, None, ...))"
    requirement: "ALERT-01"
    verification:
      - kind: unit
        ref: "cd backend && pytest tests/test_alerts_kev_epss.py -x -- 5/5 pass (xpass), including test_owner_fallback_to_admins_and_channel"
        status: pass
      - kind: static
        ref: "grep 'def get_directory_user' in directory.py + assets/router.py imports it; grep -c 'system:scheduler' alerts.py >= 1 and no 'audit(db, None' in the new code; dispatch_channel + create_notification both invoked in the fire path"
        status: pass
    human_judgment: false
  - id: D3
    description: "assets/router.py existing behavior unaffected by the get_directory_user extraction"
    requirement: "ALERT-01"
    verification:
      - kind: unit
        ref: "cd backend && pytest tests/test_asset_owner_reassign.py tests/test_asset_exposure.py tests/test_asset_groups.py tests/test_asset_source_filter.py tests/test_assets_tags_and_os_family.py -q -- 53 passed"
        status: pass
    human_judgment: false

duration: 45min
completed: 2026-08-19
status: complete
---

# Phase 40 Plan 02: ALERT-01 Lead Tracer — KEV/EPSS Detection, Guard Subtraction & Real Dispatch Summary

**`_check_new_kev_epss` proves ALERT-01 end-to-end through the real dispatch seam: guard-table subtraction with cold-start silent seeding, D-20-excluded qualifier queries, resolved-owner-or-admins+channel routing, an in-app twin, and a scheduler-side audit row — all 5 named RED tests now green.**

## Performance

- **Duration:** ~45 min (two tasks, no checkpoints — plan is `autonomous: true`)
- **Started:** 2026-08-19T16:22Z (immediately after 40-01's metadata commit)
- **Completed:** 2026-08-19T16:33Z
- **Tasks:** 2/2 (Task 1 tracer/tdd, Task 2 auto/tdd)
- **Files modified:** 3 (1 created, 2 modified)

## Accomplishments

- Implemented `_check_new_kev_epss(db, tenant) -> int` as a distinct sibling to `_check_new_critical_vulns` (D-03), wired into `run_alert_checks`'s per-tenant loop with a single new call-site line
- Proved the `AlertingGuard` once-only mechanism live: an empty guard slice seeds every currently-qualifying pair without firing (D-06 cold-start), a genuinely new pair fires exactly once and writes its own guard row, and an immediate re-run of the same qualifiers produces zero further fires
- Resolved a genuine design ambiguity the plan's action text didn't spell out: a finding that is simultaneously CISA KEV-listed AND above the tenant's EPSS threshold must fire exactly one alert, not two. Solved by making the two per-trigger-type SQL queries mutually exclusive at the predicate level (epss's query explicitly excludes `cisa_kev=True` rows) rather than adding cross-slice runtime bookkeeping — each slice stays a genuinely independent, self-contained query while the exclusivity is structural
- Extracted `get_directory_user` from `assets/router.py` into a new `backend/app/assets/directory.py` (research A5) with zero behavior change — both existing router call sites (`GET /assets/{id}`, `PATCH /assets/{id}/owner`) now import the shared symbol; verified via the existing 53-test asset regression suite, all passing
- Completed the fire step: resolved owner gets emailed directly; an unresolvable owner falls back to `_email_owners_and_admins` (D-10, fans out to every OWNER/ADMIN); every fire also attempts the tenant's `routing.new_kev_epss` channel(s) via `_build_channel_config` + `dispatch_channel` (D-07/D-19, fail-isolated — logs and continues on a channel failure, never raises); an in-app `Notification` twin (`category="new_kev_epss"`) and a direct-construction `AuditLog` row (`user_email="system:scheduler"`, `action="alert.fire"`, real `tenant_id`) land in the same pass

## Task Commits

1. **Task 1: `_check_new_kev_epss` — qualifier query, D-20 exclusion, guard subtraction, seed-silent** — `92adf52` (feat)
2. **Task 2: Owner resolution, channel push, in-app twin, scheduler audit** — `cdbdd41` (feat)

**Plan metadata:** pending (this SUMMARY's own commit)

## Files Created/Modified

- `backend/app/assets/directory.py` (created) — `get_directory_user(db, tenant_id, asset) -> dict[str, Any] | None`, extracted verbatim from `assets/router.py::_get_directory_user`
- `backend/app/notifications/alerts.py` (modified) — adds `_check_new_kev_epss` + `_fire_kev_epss_alert`; one new call-site line in `run_alert_checks`
- `backend/app/assets/router.py` (modified) — removes the inline `_get_directory_user` body, imports `get_directory_user` from `app.assets.directory` under the same private alias; both existing call sites (`GET /assets/{id}`, `PATCH /assets/{id}/owner`) unchanged

## Decisions Made

- **KEV/EPSS mutual exclusivity at the query level.** The plan's action text describes `kev` and `epss` as independent slices without addressing what happens when a single finding qualifies under both simultaneously. `test_new_kev_match_fires_once` implicitly requires exactly one guard row (it queries by `(tenant_id, cve_id, asset_id)` with `.scalar_one()`, which would raise `MultipleResultsFound` on two rows) and exactly one fire. Resolved by having the epss slice's own SQL predicate exclude `cisa_kev=True` rows — KEV (an authoritative, low-noise signal per `alerting_config.py`'s own comment) takes precedence, and the exclusivity is a property of each independent query rather than added cross-slice runtime state.
- **`get_directory_user` lives in a new `app/assets/directory.py`, not inlined into `alerts.py` or left in `router.py`.** Keeps the notifications/alerting layer free of any FastAPI/Pydantic coupling, matching the plan's own artifact spec.
- **Task 1's `_fire_kev_epss_alert` shipped as an intentionally minimal in-app-only stub, completed in Task 2.** Matches the plan's task split; Task 1's own verification (`-k "fires_once or refire or seeds or excluded"`) never exercises owner/channel/audit behavior, so the minimal version was correct and sufficient for that commit's scope.
- **`AuditLog` constructed directly (not via `app.audit.audit()`).** `audit()`'s `user=None` branch writes `tenant_id=uuid.UUID(int=0)` — a nil tenant that would misbucket a genuinely tenant-scoped scheduler-fired row. Mirrors the existing `sla_tier_service.py::_audit_escalation_fire` / `ai/audit.py::audit_log_ai_call` precedent for the identical problem.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] mypy type-narrowing error on `trigger_predicate`'s two branches**
- **Found during:** Task 1, mypy pass before commit
- **Issue:** Assigning `Vulnerability.cisa_kev.is_(True)` (inferred as the narrower `BinaryExpression[bool]`) in the `if` branch, then `and_(...)` (a `ColumnElement[bool]`) in the `else` branch, produced `Incompatible types in assignment`.
- **Fix:** Added an explicit `trigger_predicate: ColumnElement[bool]` annotation before the branch.
- **Files modified:** `backend/app/notifications/alerts.py`
- **Verification:** `mypy app/notifications/alerts.py` — only the pre-existing, out-of-scope `dict` (no type-args) error on line 28 (`run_alert_checks(db) -> dict`, untouched by this plan) remains.
- **Committed in:** `92adf52` (Task 1 commit)

**2. [Rule 1 - Bug] Missing type annotations on the new `directory.py`'s `asset` param and return type**
- **Found during:** Task 2, mypy pass before commit
- **Issue:** The extracted `get_directory_user` kept the original's untyped `asset` parameter and bare `dict | None` return, both of which mypy flagged as new errors (this is new code, not pre-existing rot, so in-scope to fix).
- **Fix:** Added `asset: Asset` (via a `TYPE_CHECKING`-guarded import to avoid a hard runtime dependency on `app.assets.models` from this thin module) and `-> dict[str, Any] | None`.
- **Files modified:** `backend/app/assets/directory.py`
- **Verification:** `mypy app/assets/directory.py` — zero errors.
- **Committed in:** `cdbdd41` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 — mypy type-correctness bugs in code this plan itself introduced, not pre-existing rot).
**Impact on plan:** No scope creep — no architectural changes, no new dependencies, both fixes are type-annotation-only.

## Issues Encountered

- Pre-existing backend mypy baseline has 61 errors across 11 unrelated files (mostly `dict` missing type-args, a long-standing codebase convention gap per Phase 38/39 precedent) — confirmed out of scope per this plan's own Scope Boundary; none of those pre-existing errors were touched or worsened.
- `ENCRYPTION_KEY`/`JWT_SECRET_KEY` generated fresh per test invocation (real Fernet key + real random secret, not placeholders) since the persisted `.env` files aren't readable via the sandboxed shell — matches the project's documented pytest-env convention (`getvul-backend-pytest-env` memory entry) and 40-01's own precedent.
- Ran all backend verification against the already-running local Docker Compose Postgres/Redis (host `localhost:5432`/`6379`) via `uv run pytest`, matching `conftest.py`'s hardcoded `localhost` assumptions.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Plan 03 (ALERT-02 digests) can now build `digests.py` against a proven, real `AlertingGuard`/`merged_alerting_config`/dispatch-seam pattern — this plan is the concrete worked example of "guard subtraction + shared dispatch + scheduler audit" the digest assembly/send-gating logic will reuse for its own send-marker gating.
- Plan 04 (ALERT-03 config save) and Plan 05 (ALERT-03 pane) are unaffected by this plan's files.
- No blockers. `test_alerts_kev_epss.py` is fully green (5/5); the existing 53-test asset regression suite and the broader scheduler/notification test files (`test_scheduler_ai_batch.py`, `test_scheduler_enrichment_refresh.py`, `test_alerting_settings.py`) all still pass unmodified.

## Self-Check: PASSED

`backend/app/assets/directory.py` confirmed present via `[ -f ... ]`. Both commit hashes (`92adf52`, `cdbdd41`) confirmed present via `git log --oneline --all`. No missing items.

---
*Phase: 40-proactive-alerting-digests*
*Completed: 2026-08-19*
