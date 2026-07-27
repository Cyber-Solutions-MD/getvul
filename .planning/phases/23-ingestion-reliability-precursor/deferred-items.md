# Phase 23 — Deferred Items (out of scope, logged not fixed)

## From Plan 23-01

- **mypy-baseline drift in `app/connectors/google_workspace.py`** (unrelated file,
  not touched by this plan): `mypy app/ | mypy-baseline filter --allow-unsynced`
  reports "new: 3" — all 3 are `note:` lines under the pre-existing
  `Library stubs not installed for "jose"` `import-untyped` error at
  `google_workspace.py:23`. Reproduced identically with 23-01's diff fully
  reverted (stash test), confirming this is pre-existing baseline/mypy-version
  drift, not a regression introduced by 23-01. Verified 23-01's own touched
  files (wiz.py, rapid7.py, nessus.py, tester.py, schemas.py) introduce zero
  new mypy errors — mypy's `override`/`call-arg` baseline entries for
  wiz.py/rapid7.py were *removed* (genuine fixes), not added to.
