---
phase: 40-proactive-alerting-digests
plan: 01
subsystem: alerting
tags: [alembic, sqlalchemy, jsonb, postgres, pytest, vitest, fastapi]

# Dependency graph
requires:
  - phase: 36-remediation-sla-engine-escalation
    provides: "Fernet-encrypted channel credential store (Tenant.sla_config.channels: Slack/Teams/PagerDuty/SMTP) reused per D-19 -- alerting_config references channel names only, never stores secrets"
  - phase: 39-exception-risk-acceptance-workflow
    provides: "SUPPRESSED/FALSE_POSITIVE + active-exception exclusion predicate (D-20) -- referenced in Wave 0 scaffolds, will be consumed verbatim by Plan 02/03, not re-derived"
provides:
  - "AlertingGuard model + alerting_guard table -- once-only KEV/EPSS transition guard keyed (tenant_id, cve_id, asset_id, trigger_type), D-05/D-06, Task 1 checkpoint option-a"
  - "Tenant.alerting_config (JSONB) + Tenant.alerting_last_digest_sent_at (durable digest-send marker closing Pitfall 4 -- survives process restarts on the single-VM stack)"
  - "alerting_config.py::DEFAULT_ALERTING_CONFIG + merged_alerting_config(tenant) -- the one canonical config-schema contract Plans 02-05 must import, not re-derive"
  - "migration 051_add_alerting_guard_and_config -- reversible, non-destructive, upgrade/downgrade/upgrade round-trip verified against a live Postgres"
  - "Wave 0 RED test scaffolds: 3 backend files (16 named tests) + shared kev_epss_finding fixture + 1 frontend file (4 named tests) -- concrete, individually-collectible green targets for Plans 02-05"
affects: [40-02, 40-03, 40-04, 40-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Tenant JSONB config precedent extended: alerting_config sits alongside sla_config/smtp_config/syslog_config, with its own merged_alerting_config() default-overlay helper (mirrors sla_tier_service.py's get_tier_policy style)"
    - "Once-only guard table keyed on domain identity (tenant_id, cve_id, asset_id, trigger_type) -- a NEW dedicated table, not a reuse of the structurally-similar-but-wrong-keyed SlaEscalationEvent"
    - "Wave 0 RED-scaffold deferred-import techniques, chosen per what actually exists today: (1) module exists, symbol missing -- import the module at top level, look up the attribute inside the test body, decorate with `pytestmark = pytest.mark.xfail(strict=False)`; (2) module doesn't exist at all -- `pytest.importorskip(...)` INSIDE each test body (never at module level, which would skip the whole file and hide the named tests); (3) frontend/vitest -- a literal `await import('./x')` is resolved EAGERLY by Vite's import-analysis plugin at transform time (unlike Python), even a `@vite-ignore` comment on a literal was insufficient (verified empirically) -- only a genuinely non-literal, runtime-computed specifier defers resolution to test-run time"

key-files:
  created:
    - backend/app/notifications/alerting_config.py
    - backend/alembic/versions/051_add_alerting_guard_and_config.py
    - backend/tests/test_alerts_kev_epss.py
    - backend/tests/test_digests.py
    - backend/tests/test_alerting_settings.py
    - frontend/src/components/settings/alerting-digests-pane.test.tsx
  modified:
    - backend/app/notifications/models.py
    - backend/app/tenants/models.py
    - backend/tests/conftest.py

key-decisions:
  - "Task 1 checkpoint resolved: option-a (dedicated alerting_guard table + fired_at + Tenant.alerting_last_digest_sent_at durable column) -- user-selected, locked as a one-way-door schema decision"
  - "Migration revision id shortened to 051_add_alerting_guard_config (29 chars) -- the natural filename-stem-derived id (051_add_alerting_guard_and_config, 33 chars) exceeds alembic_version's varchar(32); the FILE keeps the full descriptive name from files_modified, only the internal revision string is shortened, mirroring the char-budget discipline 050_add_exceptions.py's own docstring already established"
  - "ALERT-01/02/03 left UNCHECKED in REQUIREMENTS.md -- Plan 01 is a foundation plan shared with Plans 02-05 (all four declare the same three REQ-IDs per 40-01-PLAN.md's own artifacts_produced inventory); per the Phase 38 precedent (CAMP-01 left unmarked until its last declaring plan), only the LAST plan to touch a shared requirement should flip it complete. Marking it now would misrepresent that detection/digests/config-save/pane are done when only schema+scaffolding exists."
  - "test_patch_requires_owner (test_alerting_settings.py) written as a real, non-xfail test -- Depends(require_owner) already gates the entire existing PATCH /settings route regardless of body content, so it already passes today; verified by running it for real (1 passed, 3 xfailed in the same file)"

requirements-completed: []  # Deliberately empty -- see key-decisions; ALERT-01/02/03 remain open until Plan 05.

coverage:
  - id: D1
    description: "alerting_guard table (D-05 identity key, D-06 cold-start seeding shape) + Tenant.alerting_config/alerting_last_digest_sent_at columns via a reversible migration"
    requirement: "ALERT-01"
    verification:
      - kind: integration
        ref: "cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head (round-trip, exit 0) + information_schema/pg_constraint/pg_indexes inspection confirming exact columns/constraints/indexes and that pre-existing tenants.sla_config was untouched"
        status: pass
    human_judgment: false
  - id: D2
    description: "alerting_config.py::DEFAULT_ALERTING_CONFIG + merged_alerting_config(tenant) -- canonical config-schema contract for Plans 02-05"
    requirement: "ALERT-03"
    verification:
      - kind: unit
        ref: "uv run python -c '...' ad-hoc script: asserts merged_alerting_config(tenant with alerting_config=None) == DEFAULT_ALERTING_CONFIG (fresh dict, not aliased) and a partial override (epss_threshold + one routing key) correctly shallow-merges top-level keys while nested-merging the untouched routing keys"
        status: pass
    human_judgment: false
  - id: D3
    description: "Backend Wave 0 RED scaffolds (test_alerts_kev_epss.py, test_digests.py, test_alerting_settings.py) + shared kev_epss_finding fixture -- collect cleanly, give Plans 02/03/04 16 concrete named-test targets"
    requirement: "ALERT-01"
    verification:
      - kind: unit
        ref: "cd backend && pytest tests/test_alerts_kev_epss.py tests/test_digests.py tests/test_alerting_settings.py --collect-only -q (16 tests collected, exit 0); also executed for real against a live Postgres: 5 XFAIL (alerts.py), 7 SKIPPED (digests module absent), 3 XFAIL + 1 PASSED (settings) -- every outcome matches the intended Wave 0 design exactly"
        status: pass
    human_judgment: false
  - id: D4
    description: "Frontend Wave 0 RED scaffold (alerting-digests-pane.test.tsx) for the not-yet-built AlertingDigestsPane -- 4 named tests collect and fail individually rather than erroring the whole suite"
    requirement: "ALERT-03"
    verification:
      - kind: unit
        ref: "cd frontend && npx vitest run alerting-digests-pane (Test Files: 1 failed, Tests: 4 failed -- each with a distinct module-not-found error, not a transform-time suite error) + npx eslint (clean) + npx tsc --noEmit (clean)"
        status: pass
    human_judgment: false

duration: 30min
completed: 2026-08-19
status: complete
---

# Phase 40 Plan 01: Schema, Config Contract & Wave 0 RED Scaffolds Summary

**Reversible migration 051 (alerting_guard table + Tenant.alerting_config/alerting_last_digest_sent_at), the DEFAULT_ALERTING_CONFIG canonical contract, and 20 collectible Wave 0 RED test targets (16 backend + 4 frontend) for Plans 02-05.**

## Performance

- **Duration:** ~30 min (includes the Task 1 checkpoint round-trip to the user; active build/verify work for Tasks 2-3 was ~11 min per commit timestamps)
- **Started:** 2026-08-19T12:46:19Z (phase execution start, per STATE.md)
- **Completed:** 2026-08-19T13:15:57Z
- **Tasks:** 3/3 (Task 1 checkpoint:decision + Task 2 auto + Task 3 auto)
- **Files modified:** 9 (6 created, 3 modified)

## Accomplishments

- Locked the one-way-door `alerting_guard` schema via the Task 1 checkpoint (option-a: dedicated table with `fired_at` observability + a durable `Tenant.alerting_last_digest_sent_at` marker), then implemented and verified it end-to-end against a live Postgres (upgrade/downgrade/upgrade round-trip, non-destructive to `tenants.sla_config`)
- Established `alerting_config.py::DEFAULT_ALERTING_CONFIG` + `merged_alerting_config(tenant)` as the single canonical JSONB key-set contract every later plan (detection, digests, config-save, pane) must import rather than re-derive
- Authored Wave 0 RED scaffolds for all three ALERT requirements: 5 tests for KEV/EPSS detection (ALERT-01), 7 for digest assembly/send-gating (ALERT-02), 4 for the settings PATCH + audit (ALERT-03), plus a 4-test frontend pane scaffold (ALERT-03) -- all 20 tests collect individually and fail/skip for the *right* reason (missing symbol/module/component), verified by actually running them, not just asserting it
- Added a shared `kev_epss_finding` fixture to `conftest.py` (vulnerability + asset + owner_user, KEV+EPSS-qualifying, resolvable owner email) so Plans 02/03 don't have to hand-roll this scaffolding

## Task Commits

1. **Task 1: One-way-door gate -- guard-table schema + migration 051** - checkpoint, no commit (decision only; user selected option-a)
2. **Task 2: Guard model + Tenant columns + config-schema contract + migration 051** - `961b1f4` (feat)
3. **Task 3: Wave 0 RED test scaffolds + shared fixtures** - `a390f59` (test)

**Plan metadata:** pending (this SUMMARY's own commit)

## Files Created/Modified

- `backend/app/notifications/alerting_config.py` - `DEFAULT_ALERTING_CONFIG` + `merged_alerting_config(tenant)`; the canonical alerting JSONB key-set contract
- `backend/alembic/versions/051_add_alerting_guard_and_config.py` - creates `alerting_guard` (+ unique constraint + 2 indexes) and adds the 2 `tenants` columns; reversible
- `backend/tests/test_alerts_kev_epss.py` - 5 RED tests against `alerts._check_new_kev_epss` (Plan 02 target)
- `backend/tests/test_digests.py` - 7 RED tests against the not-yet-existing `app.notifications.digests` module (Plan 03 target)
- `backend/tests/test_alerting_settings.py` - 4 tests against PATCH `/settings` alerting_config (Plan 04 target); 1 already passes today
- `frontend/src/components/settings/alerting-digests-pane.test.tsx` - 4 RED tests for the not-yet-built pane (Plan 05 target)
- `backend/app/notifications/models.py` - adds `class AlertingGuard`
- `backend/app/tenants/models.py` - adds `alerting_config` (JSONB) + `alerting_last_digest_sent_at` columns to `Tenant`
- `backend/tests/conftest.py` - adds the shared `kev_epss_finding` fixture

## Decisions Made

- Task 1 checkpoint resolved as **option-a**: dedicated `alerting_guard` table, `fired_at` timestamptz (nullable, distinguishes seeded-not-fired from fired), `trigger_type` bounded string, `Index("ix_alerting_guard_slice", tenant_id, trigger_type)`, plus `Tenant.alerting_last_digest_sent_at` as the durable send marker (closes Pitfall 4) -- user-selected over the bare-existence-rows alternative.
- Migration revision id shortened to `051_add_alerting_guard_config` (29 chars) since the filename-stem-derived id is 33 chars, over `alembic_version.version_num`'s `varchar(32)` -- the file itself keeps its full descriptive name.
- **ALERT-01/02/03 intentionally left unchecked in REQUIREMENTS.md.** All five Phase 40 plans declare the same three REQ-IDs in frontmatter (this is a foundation plan, not a closing one). Per the Phase 38 precedent (a shared requirement is marked complete only by its *last* declaring plan), marking these complete now -- when detection/digests/config-save/pane don't exist yet -- would misrepresent phase progress. Plan 05 should mark them.
- `test_patch_requires_owner` written as a real (non-`xfail`) test: the existing `Depends(require_owner)` gate on PATCH `/settings` already covers any body content, so it genuinely passes today -- confirmed by executing the file (1 passed, 3 xfailed).
- Two different Wave 0 deferred-import techniques used deliberately: `app.notifications.alerts` already exists (module-level import + runtime attribute lookup, `xfail(strict=False)`) vs. `app.notifications.digests` not existing at all (`pytest.importorskip` inside each test body, never at module level, so the 7 named tests still individually collect instead of the whole file being skipped invisibly).
- Frontend scaffold required a genuinely non-literal dynamic-import specifier (`['.', 'alerting-digests-pane'].join('/')`), not a `@vite-ignore`-commented literal -- the latter still failed at Vite transform time in this project's vitest config (verified empirically, both attempts shown in the file's own comments for the next reader).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Migration revision id exceeded alembic_version's varchar(32)**
- **Found during:** Task 2 (writing migration 051)
- **Issue:** The natural revision id matching the plan's filename stem, `051_add_alerting_guard_and_config`, is 33 characters -- one over the `varchar(32)` limit on `alembic_version.version_num`, which 050's own docstring flags as a real constraint in this codebase
- **Fix:** Shortened the `revision =` string to `051_add_alerting_guard_config` (29 chars); the migration file itself keeps the full descriptive filename from the plan's `files_modified` list; documented the discrepancy in the migration's own docstring
- **Files modified:** backend/alembic/versions/051_add_alerting_guard_and_config.py
- **Verification:** `alembic heads` / `current` / `upgrade head` / `downgrade -1` / `upgrade head` round-trip all exit 0 against a live Postgres
- **Committed in:** 961b1f4 (Task 2 commit)

**2. [Rule 3 - Blocking] ruff format flagged test_digests.py docstring wrapping**
- **Found during:** Task 3 (pre-commit lint pass)
- **Issue:** `ruff format --check` reported test_digests.py would be reformatted (multi-line docstring quote-wrapping style)
- **Fix:** Ran `ruff format tests/test_digests.py`; re-ran `--collect-only` and `ruff check`/`ruff format --check` afterward to confirm no behavior change
- **Files modified:** backend/tests/test_digests.py
- **Verification:** `ruff format --check` clean on all 8 touched backend files; `pytest --collect-only` still reports 16 tests collected, exit 0
- **Committed in:** a390f59 (Task 3 commit)

**3. [Rule 3 - Blocking] Vite eagerly resolves a literal dynamic `import()` at transform time**
- **Found during:** Task 3 (verifying the frontend RED scaffold actually collects)
- **Issue:** A literal `await import('./alerting-digests-pane')` inside an async test body -- mirroring sla-escalation-pane.test.tsx's own pattern -- failed the WHOLE test file's collection with a hard "Failed to resolve import" transform error, since the target component doesn't exist yet (Plan 05). A `@vite-ignore` comment on the literal was tried first and did NOT fix it (verified empirically)
- **Fix:** Replaced the literal specifier with a runtime-computed one (`['.', 'alerting-digests-pane'].join('/')` inside an `importPane()` helper), which Vite's import-analysis plugin cannot statically resolve -- defers to actual test-run time, so all 4 named tests collect and fail individually instead of the file erroring as a whole
- **Files modified:** frontend/src/components/settings/alerting-digests-pane.test.tsx
- **Verification:** `npx vitest run alerting-digests-pane` now reports "Test Files 1 failed (1) / Tests 4 failed (4)" with 4 distinct module-not-found errors, vs. the prior "no tests" whole-suite transform error; `npx eslint` and `npx tsc --noEmit` both clean
- **Committed in:** a390f59 (Task 3 commit)

---

**Total deviations:** 3 auto-fixed (all Rule 3 -- blocking issues preventing the stated verification/acceptance criteria from passing)
**Impact on plan:** All three were required to satisfy this plan's own acceptance criteria (reversible migration, clean lint, and a frontend file that genuinely "collects" its named tests). No scope creep -- no architectural changes, no new dependencies.

## Issues Encountered

- `gsd-sdk` is not installed in this environment; used the locally-installed `.claude/get-shit-done/bin/gsd-tools.cjs` CLI instead (confirmed equivalent behavior for `init execute-phase`) for the init/context-loading step. No `state`/`roadmap`/`requirements` CLI calls were made for this plan's completion beyond what's documented below, since `requirements mark-complete` is deliberately deferred (see Decisions Made).
- Root `.env` and `backend/.env` were not readable via the Bash tool (permission denied on file-path pattern) -- worked around by generating ephemeral, valid-format `ENCRYPTION_KEY` (`Fernet.generate_key()`) and `JWT_SECRET_KEY` values per command instead of reading any persisted secret, per the project's own documented pytest-env convention (real Fernet key required, not a placeholder).
- Ran backend verification from the host via `uv run` against the already-running local Docker Compose Postgres/Redis (exposed on `localhost:5432`/`localhost:6379`), matching `conftest.py`'s hardcoded `localhost` assumptions -- not via `docker exec` into the backend container, whose own env points at the docker-network hostnames (`postgres`/`redis`), which would have broken the `flushed_redis`/`client` fixture chain had any test needed it (not needed for this plan's actual verification, but confirmed before choosing the host route).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 02 (ALERT-01 detection: `alerts.py::_check_new_kev_epss`, `assets/directory.py::get_directory_user` extraction) can now import `AlertingGuard`, `DEFAULT_ALERTING_CONFIG`/`merged_alerting_config`, and flip `test_alerts_kev_epss.py`'s 5 tests from XFAIL to real passes.
- Plan 03 (ALERT-02 digests) has its exact function names (`run_digests`, `_send_hour_due`, `_assemble_sections`, `_render_digest_html`) pre-pinned by this plan's `<artifacts_produced>` inventory and by `test_digests.py`'s 7 SKIPPED tests.
- Plan 04 (ALERT-03 config save) has a concrete target in `test_alerting_settings.py`'s 3 XFAIL tests (validation, persistence, audit) plus the existing `test_patch_requires_owner` pass to not regress.
- Plan 05 (ALERT-03 pane) has a concrete target in `alerting-digests-pane.test.tsx`'s 4 failing tests, and should be the plan that finally checks off ALERT-01/02/03 in REQUIREMENTS.md.
- No blockers. `alembic upgrade head` is clean on `main`'s current migration chain; the full existing `test_sla_policy.py` suite (16 tests) still passes unmodified, confirming no regression from the new `Tenant` columns.

---
*Phase: 40-proactive-alerting-digests*
*Completed: 2026-08-19*
