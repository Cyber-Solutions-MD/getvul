# Phase 39 — Deferred Items

Out-of-scope discoveries logged during execution per the executor's SCOPE BOUNDARY rule
(pre-existing issues in unrelated files are not auto-fixed).

## 39-01 Task 2 — pre-existing mypy-baseline drift (not caused by this plan)

**Found during:** Task 2 verification (`mypy app/ | mypy-baseline filter`).

**Observation:** Running the CI-equivalent `mypy app/ | mypy-baseline filter` reports 9 "new"
violations, all in `backend/app/ticketing/daily_sync.py` (lines 49/131/135/140/145/150) plus a
`note:` line-count mismatch in `backend/app/auth/dependencies.py:10`. None of these files are
touched by any 39-01 change.

**Root cause:** `pyproject.toml`'s own comment on the `mypy-baseline` pin warns "the
mypy-baseline is line/version-sensitive — drift silently breaks the type gate." Verified by
`git stash`-ing all of 39-01's changes and re-running the identical command against the
pre-existing tree: the same 9 violations appear with zero 39-01 code present, proving this is
baseline/tool drift already present on this branch, not something this plan introduced.

**This plan's own contribution:** one genuinely new violation was introduced and fixed inline
(`app/exceptions/service.py::active_exception_subquery` was missing a return type annotation;
added `-> Exists` from `sqlalchemy`). After that fix, the "new" count is unchanged at 9 —
matching the pre-existing-drift baseline exactly — confirming 39-01 adds zero net-new mypy
violations.

**Action:** Not fixed here (out of scope — `daily_sync.py` is untouched by this plan). Whoever
next touches `app/ticketing/daily_sync.py` or regenerates `mypy-baseline.txt` should reconcile
this drift, or it can be regenerated directly via `mypy app/ | mypy-baseline sync`.
