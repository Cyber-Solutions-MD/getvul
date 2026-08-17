# Phase 38 — Deferred Items

Out-of-scope discoveries logged during execution, per the executor's scope-boundary rule
(only auto-fix issues directly caused by the current task's changes).

## Plan 38-01

### Pre-existing mypy-baseline flake in unrelated files (not fixed)

**Found during:** Task 3 verification (`mypy app/ | mypy-baseline filter --allow-unsynced`).

**Issue:** The baseline-filtered mypy run reports a small, consistent delta of "new" violations
entirely inside two files this plan never touches:
- `app/ticketing/daily_sync.py:49,131,135,140,145,150` (missing type annotation / untyped-call /
  incompatible-assignment errors)
- `app/auth/dependencies.py:10` (a `jose`-stubs-missing `note`)

**Confirmed pre-existing, not introduced by this plan:** Reproduced identically via
`git stash` (reverting all Task 3 files, leaving only Task 2's already-committed
`campaigns/models.py` + migration in place) + `rm -rf .mypy_cache` + re-run. The exact same
delta signature (`+1 no-untyped-def, +2 assignment, +3 note, +3 no-untyped-call, -2 type-arg`)
appeared with zero campaigns-authored code present at all. This matches the previously-logged
project memory finding (`getvul-backend-test-harness-rot` / Phase 29 summary) of a
non-deterministic `mypy-baseline.txt` drift unrelated to any single plan's edits.

**Action:** Not fixed — out of scope (SCOPE BOUNDARY: pre-existing issues in unrelated files).
Genuinely new mypy issues introduced by this plan's own new files (`app/campaigns/service.py`
missing `dict[str, int]` type args, `app/campaigns/router.py` missing 3 endpoint return-type
annotations + a `dict` type-arg) were found and fixed before committing Task 3.

**Suggested follow-up:** Whoever next touches `app/ticketing/daily_sync.py` should confirm
whether `mypy-baseline.txt` needs a regeneration (`mypy-baseline sync`) to resync the checked-in
baseline against current `mypy`/stub versions.
