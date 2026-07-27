---
phase: 23-ingestion-reliability-precursor
plan: 01
subsystem: connectors
tags: [httpx, mypy-baseline, mocktransport, tls]

# Dependency graph
requires: []
provides:
  - "Wiz connector completes a full sync (authenticate now returns True on success)"
  - "Rapid7 connector constructs no-arg and authenticates (was a hard TypeError before)"
  - "verify_tls config field (default True) closing the silent-MITM gap on rapid7.py, nessus.py, tester.py"
  - "MockTransport integration tests for Wiz + Rapid7 (auth success/fail, multi-page pagination, field-for-field NormalizedVulnerability mapping)"
affects: [23-02, 23-04, 23-05, 23-06, 23-07, 23-08, 23-09]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "httpx.AsyncClient.__init__ monkeypatch idiom for connectors that build their own client inside authenticate() rather than __init__ (Wiz, Rapid7) — injects httpx.MockTransport transparently so real network code paths run unmodified under test"

key-files:
  created:
    - backend/tests/test_connectors/test_wiz_connector.py
    - backend/tests/test_connectors/test_rapid7_connector.py
    - .planning/phases/23-ingestion-reliability-precursor/deferred-items.md
  modified:
    - backend/app/connectors/wiz.py
    - backend/app/connectors/rapid7.py
    - backend/app/connectors/nessus.py
    - backend/app/connectors/tester.py
    - backend/app/connectors/schemas.py

key-decisions:
  - "Rapid7 base_url reads from credentials.get('url', ''), not config['base_url'] as the plan text suggested — matches the Nessus/Qualys sibling pattern and the actual credentials/config split enforced by connector-form.tsx (all wizard fields, including url, submit as `credentials`; `config` carries only non-form settings like verify_tls)"
  - "Rapid7 auth failure returns False (not raise) — mirrors Nessus/Qualys convention rather than Wiz's raise-on-401 (each connector's existing failure-handling idiom is preserved, per D-22 no shared-behavior refactor)"

requirements-completed: [REL-01, REL-02, REL-03]

# Metrics
duration: ~25min
completed: 2026-07-27
---

# Phase 23 Plan 01: Wiz + Rapid7 Connector Fixes Summary

**Wiz authenticate() now returns True (was silently None, so sync.py always reported "Authentication failed"); Rapid7Connector() now constructs no-arg and authenticates (was a hard TypeError, so Rapid7 sync could never even start); both proven end-to-end under httpx.MockTransport, and the silent-MITM verify=False literal is gone from all four sites in favor of a config-driven verify_tls default-True.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-07-27T10:49:00Z (approx.)
- **Completed:** 2026-07-27T11:14:12Z
- **Tasks:** 3 completed
- **Files modified:** 5 (+ 2 new test files, 1 deferred-items log)

## Accomplishments
- Wiz `authenticate()` is typed `-> bool` and returns `True` on success — the sync harness's `if not authed:` truthiness check in `sync.py:95-96` no longer misreports every successful Wiz auth as a failure.
- Rapid7 got a real no-arg `__init__` + `async def authenticate(self, credentials, config) -> bool`, moving base_url/username/password capture out of `__init__` (which previously required a `config` positional arg the no-arg sync harness could never supply, causing `TypeError: Can't instantiate abstract class Rapid7Connector`).
- Both connectors now have CI-runnable `httpx.MockTransport` integration tests (10 tests total) covering: auth success + failure, multi-page pagination followed to completion (Wiz GraphQL cursor, Rapid7 REST page/totalPages), and field-for-field `NormalizedVulnerability` mapping.
- Every hardcoded `verify=False` (silent TLS-validation-off) is gone from `rapid7.py`, `nessus.py`, and both `tester.py` connection-test functions — TLS validation now defaults ON everywhere, with an explicit per-connector `verify_tls: false` opt-out for on-prem scanners on self-signed/internal-CA certs. Advertised as a `verify_tls` boolean field (default True) on the NESSUS and RAPID7 wizard entries in `schemas.py` so the wizard's Test Connection and the real sync always agree.

## Task Commits

Each task was committed atomically (TDD RED → GREEN pairs):

1. **Task 1: Fix Wiz authenticate() return-type wiring + MockTransport test** - `a08843c` (test, RED) + `bcb6b2a` (feat, GREEN)
2. **Task 2: Rapid7 no-arg __init__ + authenticate() + MockTransport test** - `06562ad` (test, RED) + `54e41b8` (feat, GREEN)
3. **Task 3: verify_tls config field threaded through all four verify=False sites** - `c976f3f` (fix)

**Plan metadata:** (pending — this commit)

_Note: Tasks 1 and 2 are TDD (test → feat); RED failures were verified live by stashing the fix and re-running pytest before restoring it, confirming each test file genuinely fails without its corresponding fix._

## Files Created/Modified
- `backend/app/connectors/wiz.py` - `authenticate()` return type `-> None` → `-> bool`; added `return True` to the success path
- `backend/app/connectors/rapid7.py` - no-arg `__init__`; new `async def authenticate(credentials, config) -> bool` (auth probe via `GET /api/3/assets`, `verify=self.verify_tls`); `_get_client()` now reads instance attrs set by `authenticate()`
- `backend/app/connectors/nessus.py` - sync client `verify=False` → `verify=config.get("verify_tls", True)`
- `backend/app/connectors/tester.py` - `test_nessus` and `test_rapid7` `verify=False` → `verify=config.get("verify_tls", True)`
- `backend/app/connectors/schemas.py` - added `verify_tls` boolean field (default True, with help text) to `NESSUS` and `RAPID7` `CONNECTOR_TYPES` entries
- `backend/tests/test_connectors/test_wiz_connector.py` - 4 tests: auth success/failure, 2-page GraphQL cursor pagination, field-for-field mapping
- `backend/tests/test_connectors/test_rapid7_connector.py` - 6 tests: no-arg construction regression, auth success/failure, REST page/totalPages pagination, field-for-field mapping, verify_tls default/opt-out
- `.planning/phases/23-ingestion-reliability-precursor/deferred-items.md` - logs a pre-existing, unrelated mypy-baseline drift in `google_workspace.py` (not touched by this plan)

## Decisions Made
- Rapid7's `base_url` reads from `credentials.get("url", "")` rather than `config["base_url"]` as the plan text literally suggested — see Deviations below.
- Rapid7 auth failure (e.g. 401 on the probe) returns `False` rather than raising, matching the Nessus/Qualys sibling convention (Wiz's raise-on-401 is a distinct, pre-existing per-connector behavior pinned by D-22 — no shared retry/error-handling refactor this phase).
- Rapid7's `verify_tls` resolution (`config.get("verify_tls", True)`) was implemented in Task 2 alongside `authenticate()`, since the frontmatter's Task 2 artifact spec explicitly required "config-driven verify_tls" as part of the same change; Task 3 completed the remaining three sites (nessus.py, tester.py x2) and the schemas.py wizard field.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Rapid7 `base_url` sourced from `credentials`, not `config`, contradicting the plan's literal action text**
- **Found during:** Task 2 (Rapid7 authenticate() implementation)
- **Issue:** The plan's `<action>` text specified `self.base_url = config["base_url"].rstrip("/")`. But every existing sibling connector (`nessus.py`, `qualys.py`) reads its base URL from `credentials.get("url", ...)`, the `RAPID7`/`NESSUS` `CONNECTOR_TYPES` entries in `schemas.py` list `url` as a single field (not `base_url`), and the frontend `connector-form.tsx` submits ALL wizard fields (including `url`) together as `credentials` — `config` is reserved for non-form settings like `verify_tls`. Implementing the plan literally would `KeyError` in production the first time a real tenant configured a Rapid7 connector via the wizard, since `config["base_url"]` would never be populated.
- **Fix:** `self.base_url = credentials.get("url", "").rstrip("/")`, mirroring the Nessus/Qualys precedent exactly (the plan's own `<read_first>` pointed at Qualys as "a sibling connector... to mirror exactly").
- **Files modified:** `backend/app/connectors/rapid7.py`
- **Verification:** `test_authenticate_success_returns_true` and `test_fetch_vulnerabilities_paginates_to_completion` in `test_rapid7_connector.py` pass credentials-only (`{"url": ..., "username": ..., "password": ...}`) with an empty `config={}`, proving the real wiring works without requiring a `config.base_url` the wizard never sends.
- **Committed in:** `54e41b8` (Task 2 commit, documented inline in the commit message)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug prevention, avoided a production KeyError)
**Impact on plan:** Necessary correction to match the codebase's actual credentials/config contract; no scope creep — same task, same files, same artifact spec, just a corrected key name.

## Issues Encountered
- No local Python venv exists in this worktree (`backend/.venv` absent) — resolved by invoking the main repo's `backend/.venv` interpreter/pytest/mypy/ruff binaries directly against this worktree's source tree (absolute paths), consistent with the documented worktree-isolation posture; no venv was created or modified in this worktree.
- Initial branch-base check found this worktree's HEAD (`adc0571`) was a stale, much older commit that predated Phase 23 entirely (missing all phase-23 planning docs and even the 23-03 ticketing-consolidation work). Fixed per the mandatory pre-work protocol via `git reset --hard 5c06d0d` (safe — `git status` was clean before the reset, no uncommitted scaffolding to lose) before any plan work began.
- `mypy app/ | mypy-baseline filter --allow-unsynced` reports "new: 3", but these are `note:` lines under a pre-existing `google_workspace.py:23` `import-untyped` (missing `jose` stubs) error — a file untouched by this plan. Reproduced identically with this plan's entire diff reverted via `git stash`, confirming pre-existing baseline drift, not a regression. Logged to `deferred-items.md` per the scope-boundary rule (pre-existing issues in unrelated files are out of scope for auto-fix). This plan's own touched files (`wiz.py`, `rapid7.py`, `nessus.py`, `tester.py`, `schemas.py`) introduce **zero** new mypy errors — the `override` (Wiz) and `call-arg` (Rapid7 `Too many arguments for __init__ of object`) baseline entries were genuinely *fixed* (removed), not added to.

## User Setup Required

None - no external service configuration required. `verify_tls` defaults to `True` for all existing and new Nessus/Rapid7 connectors with zero config changes required; operators with self-signed on-prem certs can opt out via the new wizard field or by setting `config.verify_tls = false` directly.

## Next Phase Readiness
- Wiz and Rapid7 now complete a full simulated sync end-to-end under MockTransport — the grounding-data reliability floor for both connectors is proven, unblocking any later phase (24-28) that reads from `vulnerabilities`/`assets` tables populated by these two sources.
- REL-03 test-file scaffolding (`backend/tests/test_connectors/`) and the `httpx.AsyncClient.__init__` monkeypatch idiom for self-constructing-client connectors are now established precedent for the remaining four connectors' REL-03 coverage (CrowdStrike, Defender, Nessus, Qualys — tracked in later 23-0X plans per the phase's wave plan).
- No blockers for 23-02 through 23-09; this plan touched only `backend/app/connectors/{wiz,rapid7,nessus,tester,schemas}.py` and two new test files, with no shared-state or cross-plan file conflicts beyond the already-documented `schemas.py` serialization convention.

---
*Phase: 23-ingestion-reliability-precursor*
*Completed: 2026-07-27*

## Self-Check: PASSED

All 9 claimed files verified present on disk; all 5 claimed commit hashes (`a08843c`, `bcb6b2a`, `06562ad`, `54e41b8`, `c976f3f`) verified present in `git log --oneline --all`.
