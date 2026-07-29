---
phase: 24-ai-foundation-explain-this-vuln
plan: 03
subsystem: ai
tags: [redis, cache, fernet, byok, budget, audit-log, alembic, tdd, tenant-isolation]

# Dependency graph
requires:
  - phase: 24-02
    provides: ExplainVulnResponse schema, prompt_builder (VULN_ALLOWLIST, prompt_version), audit_log_ai_call — the three contracts this plan's storage layer sits alongside
provides:
  - get_tenant_anthropic_key(db, tenant_id) — BYOK key resolution, decrypted fresh per call, None (inert) when unconfigured, never a shared/fallback key
  - Tenant-scoped Redis explanation cache (build_cache_key/record_hash/get_cached/set_cached) with proven cross-tenant isolation, D-18 allowlist-scoped hashing, ~30-day TTL
  - Per-tenant Redis in-flight concurrency guard (acquire_inflight/release_inflight)
  - check_tenant_budget() — fail-closed monthly AI spend guard derived from audit_logs, no separate counter table
  - notify_admins_budget_exceeded() — per-admin NOTIF-01 in-app+email alert on budget breach
  - ix_audit_logs_tenant_created composite index (renamed from a pre-existing identical index, not duplicated)
affects: [24-04, 24-05, 24-06, 24-07, 24-08, 24-09, 25, 26, 27, 28]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Decrypt-fresh-per-call, never cache in a module global — mirrors get_decrypted_credentials' shape (connectors/service.py) but scoped by tenant_id + connector_type=='ANTHROPIC'; a key rotation or connector delete takes effect on the very next call"
    - "tenant_id as the mandatory first cache-key segment (ai:explain:{tenant_id}:{resource_type}:{resource_id}:{record_hash}:{model}:{prompt_version}) — the entire cross-tenant isolation mechanism, proven against a real flushed Redis rather than asserted"
    - "record_hash() is a pure sha256-over-sorted-JSON function (mirrors prompt_builder.py::prompt_version's hashing style) that only ever sees what the caller explicitly passes — the allowlist discipline lives in the CALLER's responsibility to extract only grounding fields, not in record_hash itself"
    - "SETNX-with-TTL for the per-tenant in-flight guard (ai:inflight:{tenant_id}) — mirrors the one existing Redis convention in this codebase, auth/router.py's oidc:state:{state} key"
    - "Budget accounting derived entirely from audit_logs (SUM over details->>'cost_estimate_usd' where action LIKE 'ai.%') — no second source of truth; a call that never wrote an audit row also never ran, so there's nothing to bypass by forging a cost figure"
    - "Per-admin (not single-broadcast) create_notification calls for budget-breach alerts — user_id/user_email set to each OWNER/ADMIN individually so send_email_flag=True actually reaches every admin's inbox, not just one"
    - "Rename-not-duplicate for a pre-existing index — when a migration's target index already exists under a different name with identical columns, ALTER INDEX RENAME is the correct fix, not a second CREATE INDEX"

key-files:
  created:
    - backend/app/ai/tenant_keys.py
    - backend/app/ai/cache.py
    - backend/app/ai/budget.py
    - backend/alembic/versions/031_rename_audit_tenant_idx.py
    - backend/tests/test_ai_cache_isolation.py
    - backend/tests/test_ai_budget.py
  modified: []

key-decisions:
  - "Migration renamed to 031_rename_audit_tenant_idx (27 chars) instead of the plan's literal 031_add_audit_logs_tenant_created_index (39 chars) — this repo's alembic_version.version_num column is varchar(32) (every existing revision id sits at or under exactly 32 chars); confirmed empirically via a real StringDataRightTruncationError on the first apply attempt"
  - "Migration 031 RENAMES the pre-existing idx_audit_tenant_created index (created by 013_add_audit_log.py, identical columns (tenant_id, created_at)) to ix_audit_logs_tenant_created rather than creating a second, duplicate index — RESEARCH.md's 'the only new index this phase needs' claim was incorrect, found via direct inspection during read_first"
  - "notify_admins_budget_exceeded() calls create_notification once PER active OWNER/ADMIN user (not a single broadcast row) so send_email_flag=True + user_email genuinely reaches every admin, not just the first"
  - "get_tenant_anthropic_key wraps json.loads + decrypt_value in one broad try/except returning None on any failure — mirrors get_decrypted_credentials' exact defensive shape rather than distinguishing parse-vs-decrypt failures"
  - "record_hash() takes a plain dict and hashes exactly what it's given (sha256 over json.dumps(..., sort_keys=True)) — the D-18 allowlist-only guarantee is a caller contract (documented, tested for determinism/order-independence/sensitivity), not re-implemented as a second allowlist inside cache.py"

requirements-completed: [AI-01, AI-05, AI-06]

# Metrics
duration: 19min
completed: 2026-07-29
---

# Phase 24 Plan 03: Tenant-Scoped Data Layer — BYOK Keys, Cross-Tenant-Isolated Cache, Fail-Closed Budget Summary

**BYOK Anthropic key resolution decrypted fresh per call, a Redis explanation cache with cross-tenant isolation proven against real (not mocked) Redis, and a fail-closed monthly budget guard derived entirely from the existing audit log — built test-first, with one real bug found and fixed (a duplicate-index migration) rather than blindly executed.**

## Performance

- **Duration:** ~19 min
- **Started:** 2026-07-29T09:12:00Z (approx, immediately after 24-02 completion)
- **Completed:** 2026-07-29T09:31:13Z
- **Tasks:** 2/2 completed
- **Files modified:** 6 (6 created, 0 modified)

## Accomplishments

- **BYOK key resolution is genuinely inert, not just documented as such.** `get_tenant_anthropic_key()` returns `None` — never raises, never falls back — for a tenant with no `ANTHROPIC` `ConnectorConfig` row, for a tenant whose key belongs to a *different* tenant (`test_key_never_falls_back_across_tenants` proves tenant_b gets `None` even though tenant_a has a real configured key), and correctly round-trips a real Fernet-encrypted key back to plaintext, decrypted fresh on every call with zero module-level caching.
- **Cross-tenant cache isolation is proven, not asserted.** `test_cross_tenant_cache_read_is_a_forced_miss` sets an explanation under tenant_a's fully-built cache key and reads under tenant_b's key for the identical `(resource_type, resource_id, record_hash, model, prompt_version)` tuple — against a real, flushed Redis (the `flushed_redis` fixture), not a mock — and gets a hard `None` back. This is the zero-tolerance proof for Critical Failure Mode #2 / T-24-11.
- **A real bug was found and fixed during read_first, not blindly executed.** RESEARCH.md's Code Example proposed creating a brand-new composite index `ix_audit_logs_tenant_created` on `audit_logs(tenant_id, created_at)` — but direct inspection of `013_add_audit_log.py` (part of this task's own read_first) revealed that migration already created exactly this index, under the name `idx_audit_tenant_created`, when the table itself was created. Blindly following the plan would have shipped a wasteful duplicate index (disk space + write overhead on every audit-log insert, zero query-planner benefit). Migration 031 renames the existing index instead of duplicating it — an `ALTER INDEX ... RENAME` metadata-only operation, no rebuild, no downtime.
- **A second real bug surfaced empirically on the first migration apply attempt**, not caught by any static check: the plan's literal revision id (`031_add_audit_logs_tenant_created_index`, 39 characters) exceeds this repo's `alembic_version.version_num` column width (`varchar(32)` — alembic's own default; every existing revision id in the repo sits at or under exactly 32 characters, e.g. `030_add_connector_health_columns` is exactly 32). The first `alembic upgrade head` attempt failed with a genuine `StringDataRightTruncationError`; Postgres's transactional DDL rolled back both the index rename and the version-table bookkeeping update together, leaving the database in a fully consistent pre-migration state with no manual cleanup required. The migration was renamed to `031_rename_audit_tenant_idx` (27 chars) and re-applied cleanly.
- **The fail-closed budget guard has no second source of truth.** `check_tenant_budget()` sums `audit_logs.details->>'cost_estimate_usd'` for `action LIKE 'ai.%'` rows in the current month and returns `False` the instant spend meets or exceeds the configured cap — proven at the exact boundary (`spend == cap` → `False`) and proven that a non-`ai.`-namespaced audit row (e.g. `ticket.create`) with an enormous cost figure never counts toward the cap.
- **Budget-breach admin alerts reach every admin, not just one.** `notify_admins_budget_exceeded()` queries every active `OWNER`/`ADMIN` user in the tenant and calls `create_notification(..., send_email_flag=True, user_id=admin.id, user_email=admin.email)` once per admin — proven that a tenant with only an `ANALYST` user gets zero notification calls, and that the notification payload never carries key material (`"sk-ant"` absent from both `title` and `message`, T-24-15).

## Task Commits

Each task followed the full RED → GREEN cycle (plan-level `type: tdd`):

1. **Task 1: BYOK key resolution + tenant-scoped cache with cross-tenant isolation**
   - `3fae1a5` (test) — RED: `ModuleNotFoundError: No module named 'app.ai.cache'` confirmed before any implementation existed
   - `3867552` (feat) — GREEN: 11/11 tests passing, ruff + mypy clean
2. **Task 2: Fail-closed budget guard + audit_logs index migration + admin breach notification**
   - `4989d16` (test) — RED: `ModuleNotFoundError: No module named 'app.ai.budget'` confirmed before any implementation existed
   - `fbf97ef` (feat) — GREEN: 7/7 tests passing, migration applied (`alembic heads` == 031), ruff + mypy clean

**Plan metadata:** (this commit, docs: complete plan)

_TDD gate sequence confirmed in git log: `test(24-03)` precedes `feat(24-03)` for both tasks, in order._

## Files Created/Modified

- `backend/app/ai/tenant_keys.py` - `get_tenant_anthropic_key(db, tenant_id) -> str | None` — BYOK key resolution, decrypted fresh, inert `None` on no-key
- `backend/app/ai/cache.py` - `build_cache_key()`, `record_hash()`, `get_cached()`, `set_cached()`, `acquire_inflight()`, `release_inflight()` — tenant-scoped cache + in-flight guard
- `backend/app/ai/budget.py` - `check_tenant_budget()`, `notify_admins_budget_exceeded()` — fail-closed spend guard + per-admin NOTIF-01 alert
- `backend/alembic/versions/031_rename_audit_tenant_idx.py` - renames the pre-existing `audit_logs(tenant_id, created_at)` index to `ix_audit_logs_tenant_created` (see Deviations)
- `backend/tests/test_ai_cache_isolation.py` - 11 tests: no-key inert, key roundtrip, no cross-tenant key fallback, cross-tenant cache MISS (real Redis), cache-key segment ordering, record_hash determinism/sensitivity/order-independence, TTL, in-flight guard (including tenant-scoping)
- `backend/tests/test_ai_budget.py` - 7 tests: under/at/over-budget (fail-closed), no-cap-configured (unlimited), non-`ai.%` spend excluded, admin notified on breach, non-admin tenant gets zero notifications

## Decisions Made

- Migration renamed to `031_rename_audit_tenant_idx` (27 chars) — the plan's literal filename (39 chars) exceeds `alembic_version.version_num`'s `varchar(32)`, confirmed empirically.
- Migration 031 RENAMES the pre-existing `idx_audit_tenant_created` index rather than creating a duplicate `ix_audit_logs_tenant_created` — direct inspection of `013_add_audit_log.py` found the index already existed on identical columns.
- `notify_admins_budget_exceeded()` calls `create_notification` once per admin (not a single broadcast row) so `send_email_flag=True` reaches every admin's inbox.
- `get_tenant_anthropic_key` wraps JSON parsing + decryption in one broad `try/except`, mirroring `get_decrypted_credentials`'s exact defensive shape.
- `record_hash()` hashes exactly what it's given; the D-18 allowlist-only guarantee is a documented, tested caller contract rather than a second allowlist re-implemented inside `cache.py`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Migration renamed a pre-existing index instead of creating a duplicate**
- **Found during:** Task 2, read_first (`013_add_audit_log.py`)
- **Issue:** RESEARCH.md's Code Example and the plan's own artifact table specified creating a NEW composite index `ix_audit_logs_tenant_created` on `audit_logs(tenant_id, created_at)`. Direct inspection of the audit_logs table's own creation migration (`013_add_audit_log.py`, read as part of this task's mandatory read_first) showed `op.create_index("idx_audit_tenant_created", "audit_logs", ["tenant_id", "created_at"])` already exists on the exact same columns in the exact same order. Creating a second index would be pure duplication — extra disk space and write overhead on every future audit-log insert, with zero query-planner benefit (Postgres would simply pick one of the two identical indexes).
- **Fix:** Migration 031's `upgrade()` runs `ALTER INDEX idx_audit_tenant_created RENAME TO ix_audit_logs_tenant_created` (a fast, metadata-only operation — no table/index rebuild, no downtime) instead of `CREATE INDEX`. `downgrade()` renames it back.
- **Files modified:** `backend/alembic/versions/031_rename_audit_tenant_idx.py`
- **Verification:** `docker exec getvul-postgres-1 psql -U getvul -d getvul -c "SELECT indexname FROM pg_indexes WHERE tablename='audit_logs';"` confirmed `ix_audit_logs_tenant_created` exists post-migration and no duplicate/second index was created.
- **Committed in:** `fbf97ef` (Task 2 GREEN commit)

**2. [Rule 3 - Blocking] Migration revision id shortened to fit alembic_version's varchar(32) column**
- **Found during:** Task 2, first `alembic upgrade head` attempt
- **Issue:** The plan's specified migration filename/revision id, `031_add_audit_logs_tenant_created_index`, is 39 characters. This repo's `alembic_version.version_num` column is `varchar(32)` (alembic's own default — confirmed by checking every existing revision id in the repo, all of which sit at or under exactly 32 characters, e.g. `030_add_connector_health_columns` is exactly 32). The first `alembic upgrade head` attempt failed with a genuine `asyncpg.exceptions.StringDataRightTruncationError: value too long for type character varying(32)` on the `UPDATE alembic_version SET version_num=...` bookkeeping statement — the index rename itself had already run, but Postgres's transactional DDL rolled back BOTH the rename and the bookkeeping update together, leaving the database at revision 030 with no manual cleanup needed (confirmed via `alembic current` and a direct `pg_indexes` query showing the original index name still in place).
- **Fix:** Renamed the migration file and its `revision`/`down_revision` values to `031_rename_audit_tenant_idx` (27 characters, comfortably under the 32-char limit).
- **Files modified:** `backend/alembic/versions/031_rename_audit_tenant_idx.py` (the plan specified `031_add_audit_logs_tenant_created_index.py` — this file does not exist under that name)
- **Verification:** `alembic upgrade head` applied cleanly on retry; `alembic heads` reports `031_rename_audit_tenant_idx (head)`.
- **Committed in:** `fbf97ef` (Task 2 GREEN commit)

---

**Total deviations:** 2 auto-fixed (1 bug — duplicate-index avoidance, 1 blocking — DB column-width constraint)
**Impact on plan:** Both deviations are execution-detail corrections to the SAME migration file, discovered by direct inspection (Rule 1) and by the migration genuinely failing to apply (Rule 3) rather than by inventing new scope. The resulting index (`ix_audit_logs_tenant_created` on `audit_logs(tenant_id, created_at)`) is exactly what the plan's artifact table describes — it now exists via a rename instead of a wasteful duplicate `CREATE INDEX`, and the migration filename differs from the plan's literal specification (any future plan referencing `031_add_audit_logs_tenant_created_index.py` by exact filename should instead reference `031_rename_audit_tenant_idx.py`; the revision id in `alembic heads` is `031_rename_audit_tenant_idx`, not the plan's originally-specified string). No architectural change, no new table, no scope creep.

## Issues Encountered

None beyond the two deviations documented above (which were resolved inline, not left open).

## User Setup Required

None - no external service configuration required. All changes are internal backend code, tests, and a database migration; no new environment variables.

## Next Phase Readiness

- `get_tenant_anthropic_key()`, the cache functions, and `check_tenant_budget()`/`notify_admins_budget_exceeded()` are ready for Plan 04's `explain_vuln.py` streaming engine to import and wire against unchanged — this plan deliberately isolated the storage/enforcement concerns from the streaming logic so cross-tenant isolation and fail-closed budget stay testable against real Redis + Postgres fixtures independently, per the plan's own objective.
- The in-flight guard (`acquire_inflight`/`release_inflight`) is ready for Plan 04 to wrap around the real Anthropic call in a `try/finally` — this plan only proves the guard's own acquire/release semantics, not its integration into a real call path.
- **Naming note for downstream plans/tooling:** the audit_logs composite index migration is named `031_rename_audit_tenant_idx.py` (revision id `031_rename_audit_tenant_idx`), NOT the plan-specified `031_add_audit_logs_tenant_created_index.py` — see Deviations above. The resulting index name (`ix_audit_logs_tenant_created`) matches what was originally documented; only the migration file/revision-id string differs.
- Postgres + Redis containers (`getvul-postgres-1`, `getvul-redis-1`) were left running after this session for continuity — Plan 04's executor can reuse them directly.
- The local `backend/.venv` still does not have the `anthropic` package installed (flagged in `24-02-SUMMARY.md`) — this plan's files never import it, so it remained out of scope here too, but Plan 04 (which builds the real streaming engine against the `anthropic` SDK) will need `pip install -e .` (or equivalent) in `backend/.venv` before its own tests can run locally.

## Self-Check: PASSED

- Files verified present: `backend/app/ai/tenant_keys.py`, `backend/app/ai/cache.py`, `backend/app/ai/budget.py`, `backend/alembic/versions/031_rename_audit_tenant_idx.py`, `backend/tests/test_ai_cache_isolation.py`, `backend/tests/test_ai_budget.py` (6/6 found)
- Commits verified present in `git log`: `3fae1a5`, `3867552`, `4989d16`, `fbf97ef` (4/4 found)
- TDD gate sequence confirmed: `test(24-03)` precedes `feat(24-03)` for both Task 1 and Task 2, in order
- Plan-level `<verification>` re-run and green: `alembic upgrade head` clean, `alembic heads` == `031_rename_audit_tenant_idx (head)`; `pytest tests/test_ai_cache_isolation.py tests/test_ai_budget.py -q` → 18 passed; cross-tenant isolation test green against real (flushed) Redis
- Acceptance-criteria greps re-confirmed: `cache.py` shows `ai:explain:` (2 occurrences) with `tenant_id` as the first interpolated segment; `cache.py` shows 0 occurrences of `app.state.redis`/`redis.Redis(` (no bare client construction); `budget.py` shows `action.like`/`ai.%` (1 occurrence)
- Regression sweep green: `test_ai_audit.py` + `test_ai_schemas.py` + `test_ai_prompt_builder.py` + `test_encryption_rotation.py` — 54/54 passed
- ruff + mypy clean on all 4 new non-test source files (the only mypy findings are 15 pre-existing, already-baselined errors in unrelated files: `app/audit.py`, `app/tenants/models.py`, `app/ticketing/models.py`)

---
*Phase: 24-ai-foundation-explain-this-vuln*
*Completed: 2026-07-29*
