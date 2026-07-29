# Phase 24 — Deferred Items (out-of-scope discoveries, not fixed)

Items discovered during plan execution that are DIRECTLY caused by neither
the current plan's changes nor any prior Phase 24 plan's changes — logged
per the executor's scope-boundary rule, not fixed.

---

## 24-04: Full-suite-only flake in `test_connector_health.py` (pre-existing, unrelated)

**Found during:** Plan 24-04, post-Task-2 full-suite regression sweep
(`pytest tests/ -q`, 427 tests collected).

**Symptom:** `tests/test_connector_health.py::test_scheduler_path_error_message_and_log_are_sanitized`
fails only when the FULL `tests/` directory is collected together
(`1 failed, 426 passed`) — asserting `len(complete_events) == 1` where
`complete_events` is empty (`0 == 1`). The test asserts on a captured
structlog event list (`background_sync_complete`) that appears to get
lost/reordered under full-suite log-capture contention.

**Confirmed unrelated to Plan 24-04:** running the file in isolation
(`pytest tests/test_connector_health.py -q`) passes cleanly, 9/9. Plan
24-04 never touches `app/connectors/scheduler.py`, `app/connectors/health.py`,
or any sync-logging code path — the file/behavior under test is completely
outside this plan's `files_modified` list.

**Likely root cause (not investigated further — out of scope):** this
project's `pytest.ini_options` shares ONE session-scoped asyncio event loop
across the whole test session (`asyncio_default_fixture_loop_scope =
"session"`, documented in `pyproject.toml` as a workaround for a different
pre-existing pool-disposal issue, WR-14). A shared event loop across ~427
tests is a plausible vector for structlog capture-fixture cross-test
interference — the same general CLASS of "full-suite-only flake" already
documented in project memory for the frontend Playwright suite
(`getvul-e2e-fullsuite-flake-classes`), just on the backend pytest side.

**Action:** Not fixed (out of scope per SCOPE BOUNDARY — pre-existing,
unrelated file). Flag for a future backend test-harness hardening pass if
this resurfaces; matches the already-tracked `getvul-backend-test-harness-rot`
class of issue.

---

## 24-08: `mypy-baseline.txt` line-number drift on "note:" lines (pre-existing, environmental)

**Found during:** Plan 24-08, Task 2 `mypy app/ | mypy-baseline filter
--allow-unsynced` check.

**Symptom:** The gate reports `new: 3 / fixed: 3` (all under the `note`
error-code bucket) even with every Plan 08 file (`grounding.py`,
`explain_host.py`, `explain_remediation.py`, the `__init__.py` router
registration) removed/reverted — isolated via a `mv`-to-scratchpad +
`git show HEAD:...` restore (never `git stash`, per this session's git
hygiene constraint), confirming this is NOT caused by any Plan 08 change.

**Root cause (confirmed, not just suspected):** `mypy-baseline.txt` (checked
into the repo) stores every `note:` line with a hardcoded `:0:` line number
(e.g. `app/assets/router.py:0: note: PEP 484 prohibits implicit
Optional...`), while a live `mypy app/` run reports the note's REAL line
number (e.g. `app/assets/router.py:384: note: ...`). `mypy-baseline filter
--allow-unsynced` does not fuzzy-match note lines across this line-number
gap, so every note-category line is reported as simultaneously "fixed" (the
`:0:` baseline entry) and "new" (the real-line-number live entry) on every
run, regardless of what changed. Diffing the baseline's 21 `note:` lines
against a live run's 21 `note:` lines confirms an exact 1:1 correspondence
by message text, differing ONLY in the line number field.

**Confirmed unrelated to Plan 24-08:** none of the 7 files involved
(`app/assets/router.py`, `app/auth/providers.py`, `app/connectors/
crowdstrike.py`, `app/connectors/defender.py`, `app/connectors/
humaans_sync.py`, `app/connectors/jamf.py`, `app/connectors/jamf_sync.py`,
`app/connectors/sync.py`, `app/enrich_assets.py`, `app/vulnerabilities/
router.py`, `app/vulnerabilities/trends.py`) is in this plan's
`files_modified` list. `ruff check`/`ruff format --check`/direct `mypy`
invocation (not piped through `mypy-baseline`) all confirm ZERO errors
attributed to any of Plan 08's own new/modified files specifically.

**Action:** Not fixed (out of scope per SCOPE BOUNDARY — pre-existing,
checked-in artifact affecting unrelated files; regenerating
`mypy-baseline.txt` is a repo-wide CI-gate change outside this plan's
scope and was not attempted). This is precisely the risk
`pyproject.toml`'s own pinning comment already flags: "the mypy-baseline is
line/version-sensitive — drift silently breaks the type gate." Flag for a
future `mypy-baseline sync` pass if CI's own gate (which may run under
different conditions/timing than this local check) starts failing on it.
