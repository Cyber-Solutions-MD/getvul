---
phase: 31-connector-enrichment-rewrite
plan: 02
subsystem: backend/connectors
tags: [scheduler, httpx, gzip, epss, cisa-kev, sqlalchemy, asyncio, postgres]

# Dependency graph
requires:
  - phase: 31-connector-enrichment-rewrite (Plan 01)
    provides: "epss_scores/cisa_kev global ref tables, EpssScore/CisaKev ORM models, _lookup_enrichment write-path choke point in sync.py"
provides:
  - "enrichment_feeds.py: _fetch_and_parse_epss/_fetch_and_parse_kev (gzip/redirect/JSON parse, malformed-row tolerance, size caps)"
  - "refresh_enrichment_reference_data: D-09 atomic-swap-keeps-last-good (fetch+parse fully first, DB write only on full success, caller commits)"
  - "repropagate_enrichment: D-01/D-02 raw UPDATE...FROM re-propagation, cve_id-keyed, backfills historical findings for free"
  - "scheduler.py: _dispatch_enrichment_refresh (24h-gated, inline-await, lock-guarded) + eager first-run in start_scheduler() + per-tick wiring in _scheduler_loop()"
  - "_enrichment_refresh_lock: asyncio.Lock closing a real concurrency race between the eager call and the loop's own first-tick call"
affects: ["31-03", "31-04", "31-05 (unaffected — this plan only touches the feed-refresh/scheduler layer, not per-connector parsers)", "Phase 33/34 (risk model consumers now have real, continuously-refreshed epss_score/epss_percentile/cisa_kev data to read, not just Plan 01's test fixtures)"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Fetch+parse-fully-before-any-DB-write atomic swap: both feeds are fetched and parsed entirely in memory (pure, DB-free, directly mockable functions) before a single DELETE/INSERT statement runs — a parse failure never touches the database"
    - "asyncio.Lock-guarded 24h-gated dispatcher: a module-level datetime sentinel PLUS a module-level asyncio.Lock, because this dispatcher (unlike its siblings) has TWO independent call sites (start_scheduler()'s eager call + _scheduler_loop()'s per-tick call) that can race on the same in-memory gate"
    - "Raw text() UPDATE...FROM for cross-table bulk re-propagation, where the codebase's usual ORM update().values() idiom (single-table only) doesn't reach"

key-files:
  created:
    - backend/app/connectors/enrichment_feeds.py
    - backend/tests/test_enrichment_feeds.py
    - backend/tests/test_scheduler_enrichment_refresh.py
    - .planning/phases/31-connector-enrichment-rewrite/deferred-items.md
  modified:
    - backend/app/connectors/scheduler.py
    - backend/mypy-baseline.txt
    - backend/tests/test_vulnerability_enrichment.py

key-decisions:
  - "repropagate_enrichment returns {'repropagated': N, 'kev_recomputed': M} (two counts, not the plan's literal single 'repropagated' key) — the EPSS UPDATE only touches rows with a cve_id match (a meaningful 'how many findings got fresher EPSS data' count), while the KEV UPDATE is an unconditional bidirectional recompute touching every row unconditionally (matching D-04's 'authoritative both ways' requirement) — collapsing both into one number would have obscured that the two statements have structurally different match semantics"
  - "_enrichment_refresh_lock (asyncio.Lock) added beyond the plan's literal text — a genuine concurrency bug (not speculative; reproduced live), see Deviations"
  - "Seed cve_id values in both the new test_enrichment_feeds.py and Plan 01's pre-existing test_vulnerability_enrichment.py use a pre-1999 year (CVE-1990-...) instead of a plausible real-CVE-range year — collision-proofing against the real feed data that this plan's own scheduler wiring can now populate during any client-fixture test's app lifespan"

patterns-established:
  - "_fetch_and_parse_epss/_fetch_and_parse_kev: pure async fetch+parse functions with zero DB access, each independently mockable via httpx.MockTransport and independently unit-testable — the template for any future external-feed integration in this codebase"
  - "Lock-then-gate-check dispatcher shape for any scheduler dispatcher reachable from more than one call site (this is the first one in the codebase with that property)"

requirements-completed: [ENRICH-01, ENRICH-02, ENRICH-05]

# Metrics
duration: 65min
completed: 2026-08-05
---

# Phase 31 Plan 02: Enrichment Feed Refresh + Scheduler Wiring Summary

**Daily 24h-gated scheduler job that fetches the real EPSS CSV + CISA KEV JSON feeds, atomic-swaps them into the global reference tables (keeping last-good data on any failure), and re-propagates the refreshed values onto every existing finding by cve_id — verified live against the real feeds (355,094 EPSS rows, 1,660 KEV rows), and hardened against a genuine concurrency race discovered during that live verification.**

## Performance

- **Duration:** ~65 min
- **Started:** 2026-08-05T10:18Z (approx, immediately following Plan 01's completion per STATE.md)
- **Completed:** 2026-08-05T10:58Z
- **Tasks:** 3 (RED / GREEN part 1: feed fetch+swap / GREEN part 2: scheduler wiring)
- **Files modified:** 8 (4 created, 4 modified — including one Plan 01 test file fixed for a cross-plan regression this plan's own change surfaced)

## Accomplishments

- `enrichment_feeds.py` fetches both external feeds for real: EPSS's CSV (`https://epss.empiricalsecurity.com/epss_scores-current.csv.gz`, 302-redirect-then-gzip, `follow_redirects=True`, comment-line skip, ~1% malformed-row tolerance, 50MB compressed/decompressed sanity cap) and CISA KEV's JSON catalog (`{catalogVersion, count, vulnerabilities[]}` envelope). `refresh_enrichment_reference_data` implements D-09's atomic-swap-keeps-last-good contract precisely: both feeds are fetched+parsed FULLY in memory first (pure, DB-free functions); any exception aborts before a single DB statement runs; on full success, `epss_scores`/`cisa_kev` are delete-then-chunked-bulk-inserted inside the caller's transaction (this function never commits itself).
- `repropagate_enrichment` runs the D-01/D-02 raw-SQL `UPDATE vulnerabilities v SET epss_score = e.epss_score, epss_percentile = e.percentile FROM epss_scores e WHERE v.cve_id = e.cve_id` plus `UPDATE vulnerabilities SET cisa_kev = (cve_id IN (SELECT cve_id FROM cisa_kev))` — keyed on `cve_id`, not "ingested this run," so historical findings backfill for free and the CISA KEV column recomputes authoritatively in BOTH directions (flips back to `False` when a CVE drops out of the catalog, not just OR'd in).
- `scheduler.py` gained `_dispatch_enrichment_refresh` (24h-gated, inline-`await`ed — not `create_task`'d like the AI batch dispatchers — so D-09's atomic swap runs to completion as one unit before the gate advances, and only advances on `status == "ok"`), wired into both `_scheduler_loop()`'s per-tick body and an eager first-run call in `start_scheduler()` (D-10).
- **Verified live, not just unit-tested:** while iterating, the docker dev stack's `--reload` backend picked up the new code and ran the real refresh multiple times, populating the dev Postgres with the exact real-world counts RESEARCH.md cited (`epss_rows=355094`, `kev_rows=1660`, `status=ok`) — this satisfies the plan's Manual-Only verification requirement (confirmed real egress to `epss.empiricalsecurity.com`/`www.cisa.gov`, real row counts) without a separate deliberate script.
- That same live exposure surfaced and let us fix a genuine concurrency bug before it could reach production — see Deviations.

## Task Commits

Each task was committed atomically:

1. **Task 1: RED — scheduler dispatch + feed-parse tests** - `feade83` (test)
2. **Task 2: GREEN — enrichment_feeds.py fetch+parse, atomic swap, re-propagation** - `65bf6ba` (feat)
3. **Task 3: GREEN — scheduler wiring + concurrency-race fix** - `46446fd` (feat)

**Plan metadata:** (this commit, docs: complete plan)

_TDD gate compliance: RED (`feade83`) → GREEN (`65bf6ba`, `46446fd`). Both gates present in git log — compliant._

## Files Created/Modified

- `backend/app/connectors/enrichment_feeds.py` (new) - `_fetch_and_parse_epss`/`_fetch_and_parse_kev` (pure, DB-free, mockable fetch+parse), `refresh_enrichment_reference_data` (D-09 atomic swap), `repropagate_enrichment` (D-01/D-02 raw-SQL re-propagation)
- `backend/app/connectors/scheduler.py` - `_last_enrichment_refresh` sentinel + `_enrichment_refresh_lock` + `_dispatch_enrichment_refresh` + per-tick wiring in `_scheduler_loop()` + eager first-run in `start_scheduler()`
- `backend/tests/test_enrichment_feeds.py` (new) - EPSS gzip/redirect/malformed-row-tolerance/size-cap unit tests (MockTransport), KEV JSON envelope parse, atomic-swap-keeps-last-good + full-success-swap integration tests, re-propagation integration tests (both EPSS backfill and bidirectional KEV recompute)
- `backend/tests/test_scheduler_enrichment_refresh.py` (new) - 24h-gate, gate-does-not-advance-on-failure, eager-first-run (fires cold / stays silent warm), dispatch-exception-containment, no-per-tenant-client-arg, and the concurrency-race regression test
- `backend/tests/test_vulnerability_enrichment.py` (Plan 01's file, fixed) - `ENRICHED_CVE`/`UNENRICHED_CVE` constants changed from a real-CVE-range year to a pre-1999 (collision-proof) year — see Deviations
- `backend/mypy-baseline.txt` - +2 `"Result[Any]" has no attribute "rowcount"` entries for `enrichment_feeds.py`'s raw `text()` UPDATE statements — the same pre-existing, already-baselined SQLAlchemy stub limitation present throughout `sla_service.py`/`correlation_service.py`/etc.
- `.planning/phases/31-connector-enrichment-rewrite/deferred-items.md` (new) - logs the broader "no test-mode gate anywhere in `app/`" architectural observation as out-of-scope, mirroring the Phase 28-02 precedent

## Decisions Made

- `repropagate_enrichment` returns `{"repropagated": N, "kev_recomputed": M}` — two separate counts rather than the plan's literal single `"repropagated"` key, because the EPSS `UPDATE...FROM` only matches rows with a `cve_id` hit (a meaningful "how many findings got fresher EPSS data" count) while the KEV `UPDATE` is an unconditional bidirectional recompute touching every row in the table regardless of match (per D-04's "authoritative both ways" requirement) — these are structurally different counts and collapsing them into one number would have obscured that difference in logs.
- `_enrichment_refresh_lock` (`asyncio.Lock`) added beyond the plan's literal text, to close a genuine, reproduced-live concurrency race between `start_scheduler()`'s eager call and `_scheduler_loop()`'s own first-tick inline call (both reach the same in-memory gate check nearly simultaneously on process startup). See Deviations for the full account.
- Seed `cve_id` constants in this plan's own `test_enrichment_feeds.py` AND Plan 01's pre-existing `test_vulnerability_enrichment.py` were both changed to a pre-1999 year (`CVE-1990-...`) — the real CVE numbering scheme's floor is 1999, making this range permanently collision-proof against real feed data, which this plan's own scheduler wiring can now populate during any test that spins up the real FastAPI app lifespan (see Deviations + `deferred-items.md`).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Race condition between `start_scheduler()`'s eager call and `_scheduler_loop()`'s first-tick call**
- **Found during:** Task 3, wave-level regression sweep — the docker dev stack's `--reload` backend container picked up the in-progress `scheduler.py` edit and, in its own logs, showed a real `sqlalchemy.exc.IntegrityError: ... duplicate key value violates unique constraint "epss_scores_pkey"` immediately after a successful `enrichment_refresh_completed` log line.
- **Issue:** `start_scheduler()`'s `asyncio.create_task(_dispatch_enrichment_refresh())` (D-10 eager first-run) and `_scheduler_loop()`'s own per-tick inline `await _dispatch_enrichment_refresh()` (which fires on the loop's very first iteration too, since nothing delays it) both reach the dispatcher nearly simultaneously on process startup. The in-memory `_last_enrichment_refresh is None` gate check alone is a classic check-then-act race: both call sites can observe `None` before either has finished setting the gate, so both independently fetch their own copy of the feed and both attempt their own delete-then-insert swap. Whichever finishes and commits first makes its rows visible; the second, still mid-insert with its own independently-fetched (near-identical) row set, then collides on the primary key.
- **Fix:** Added a module-level `_enrichment_refresh_lock = asyncio.Lock()`. `_dispatch_enrichment_refresh` now checks `if _enrichment_refresh_lock.locked(): return` before doing anything else, then wraps its entire gate-check-and-execute body in `async with _enrichment_refresh_lock:`. A concurrent call while a refresh is already in-flight is now a clean, immediate no-op instead of a second overlapping swap.
- **Files modified:** `backend/app/connectors/scheduler.py`, `backend/tests/test_scheduler_enrichment_refresh.py` (new `test_dispatch_enrichment_refresh_concurrent_calls_do_not_race` regression test, using `asyncio.Event`-based deterministic synchronization — not a fragile `sleep()` — to prove a second concurrent call is a no-op while the first is mid-flight)
- **Verification:** New regression test passes; re-ran the same live docker-reload scenario 3 more times after the fix (visible in `docker logs getvul-backend-1`) — 3 consecutive clean `enrichment_refresh_completed` runs with zero errors, versus the pre-fix run that raised `IntegrityError` on the second concurrent attempt.
- **Committed in:** `46446fd` (Task 3 commit)

**2. [Rule 1 - Bug] Cross-file test collision from real feed data populated during the live-reload investigation**
- **Found during:** Task 3, wave-level regression sweep — `tests/test_enrichment_feeds.py` (this plan) and `tests/test_vulnerability_enrichment.py` (Plan 01, untouched by this plan until now) both started failing with `UniqueViolationError`/wrong-assertion failures once the docker dev stack's live reload (triggered by items 1's investigation) populated the shared dev Postgres's `epss_scores` with ~355k real rows.
- **Issue:** Both test files seeded synthetic `EpssScore` rows using plausible real-CVE-range identifiers (`CVE-2024-0001`/`CVE-2024-9999` in Plan 01's file, `CVE-1999-0001`/`CVE-1999-0002` in this plan's own file — 1999 and 2024 are both real, heavily-populated years in the actual EPSS dataset). Once real data existed in the table, these seeds either collided on insert (duplicate primary key) or made a "this CVE is NOT in the ref table" assertion silently false (since the real feed does cover CVE-2024-9999).
- **Fix:** Changed both files' seed `cve_id` values to a pre-1999 year (`CVE-1990-...`) — the real CVE numbering scheme's floor is 1999 (the CVE program itself launched in 1999; even retroactively-catalogued legacy vulnerabilities use the `CVE-1999-...` series, never earlier), so this range is permanently guaranteed collision-proof regardless of whether the ref tables are empty (Plan 01's original test assumption) or fully populated (now possible, since this plan's scheduler wiring can populate them for real during any `client`-fixture test's app lifespan).
- **Files modified:** `backend/tests/test_enrichment_feeds.py`, `backend/tests/test_vulnerability_enrichment.py` (Plan 01's file — a cross-plan fix, directly caused by this plan's own change making the previously-dormant real-fetch pathway reachable for the first time)
- **Verification:** Both files pass individually and as part of the full 12-file wave-level regression sweep (90/90 tests green), regardless of whether `epss_scores`/`cisa_kev` are currently empty or populated with real data.
- **Committed in:** `46446fd` (Task 3 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 — a genuine concurrency bug and a cross-file test-collision regression, both directly caused by and discovered through this plan's own change; neither was speculative, both reproduced live against the real docker dev stack)
**Impact on plan:** No scope creep — both fixes are narrowly scoped to files this plan's own change broke or introduced. The broader "no test-mode gate anywhere in `app/`" architectural observation this investigation surfaced is explicitly NOT fixed here (see `deferred-items.md`, mirroring the established Phase 28-02 precedent for the identical class of issue) since it's a cross-cutting test-infrastructure concern affecting every scheduler dispatcher, not something this narrowly-scoped plan should silently redesign.

## Issues Encountered

The docker-compose dev stack's `getvul-backend-1` container runs `uvicorn --reload` and shares the same Postgres this executor's `.venv`-based pytest runs use. Every in-progress edit to `scheduler.py`/`enrichment_feeds.py`/the new test files triggered a live reload, which (since `settings.environment` defaults to `"production"` and nothing gates scheduler startup during development) re-ran the real scheduler — including, now, the real EPSS/KEV fetch — on every single reload. This was the mechanism that surfaced both deviations above; it is also the mechanism that provided the plan's own Manual-Only live-feed verification for free (see Accomplishments). The shared dev Postgres's `epss_scores`/`cisa_kev` tables were `TRUNCATE`d back to empty (a plain SQL statement, not a git operation) after verification, to leave a clean baseline; nothing prevents the container from repopulating them again on its own on a subsequent reload or its next natural 24h tick — this is expected, benign, and no longer capable of breaking any test given the collision-proof CVE IDs now in place.

## User Setup Required

None — no external service configuration required. Both feed URLs (`epss.empiricalsecurity.com`, `www.cisa.gov`) are public and unauthenticated; live egress to both was directly confirmed working from this dev environment during execution.

## Next Phase Readiness

- ENRICH-01, ENRICH-02, and ENRICH-05 are now fully satisfied — Plan 02 was each requirement's last declaring plan (Plan 01 provided the schema + universal write-path choke point; this plan provides the actual daily-refreshed real data). Flipped to `[x]` Complete in `REQUIREMENTS.md`.
- `epss_scores`/`cisa_kev` are now genuinely self-populating and self-healing in this dev environment (and will be in any deployment where `settings.environment` is `"production"`/`"development"`) — Plans 03/04/05's remaining connector work (ENRICH-03/04/06) can now be verified end-to-end against real reference data, not just Plan 01's synthetic test fixtures.
- No blockers. Full wave-level regression sweep (12 files, 90 tests, spanning `test_connector_normalization.py`, all 6 `test_connectors/*.py` files, both new files, `test_connector_health.py`, `test_scheduler_ai_batch.py`, and Plan 01's `test_vulnerability_enrichment.py`) green. `ruff check`/`ruff format --check` clean on every touched file. `mypy app/ | mypy-baseline filter --allow-unsynced` shows zero new violations beyond the already-baselined `"Result[Any]" has no attribute "rowcount"` pattern (2 new entries added, matching the identical pre-existing pattern in `sla_service.py`/`correlation_service.py`) and the confirmed pre-existing, nondeterministic `jose`-stub-missing `note:` flake (unrelated, documented in this project's own STATE.md history across Phases 24/29/31-01).
- Flagged, not silent: `deferred-items.md` documents the broader "no test-mode gate" architectural gap (shared by every scheduler dispatcher, not new to this plan) for a future, deliberately-scoped fix.

---
*Phase: 31-connector-enrichment-rewrite*
*Completed: 2026-08-05*

## Self-Check: PASSED

All 4 created files confirmed present on disk (`backend/app/connectors/enrichment_feeds.py`, `backend/tests/test_enrichment_feeds.py`, `backend/tests/test_scheduler_enrichment_refresh.py`, `.planning/phases/31-connector-enrichment-rewrite/deferred-items.md`); `_enrichment_refresh_lock` confirmed present in `backend/app/connectors/scheduler.py`; all 3 task commit hashes (`feade83`, `65bf6ba`, `46446fd`) confirmed in `git log`.
