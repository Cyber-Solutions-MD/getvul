# Phase 27 — Deferred Items (out-of-scope discoveries)

Items found during execution that are pre-existing, unrelated to the current task's
changes, and therefore NOT auto-fixed per the executor's scope-boundary rule.

## Plan 27-01

### Pre-existing mypy-baseline "note" noise (unrelated files)

**Found during:** Task 1 (`title` field/validator/fallback), while running
`mypy app/ | mypy-baseline filter --allow-unsynced` per CI's exact invocation
(`.github/workflows/ci.yml`).

**Observed:** `mypy-baseline filter` reports `fixed: 3, new: 3` relative to the committed
`backend/mypy-baseline.txt`, entirely inside the `note` error category.

**Root cause (confirmed via content-diff, ignoring line numbers):** ALL 3 "new"/"fixed"
lines are informational `note:` hints attached to pre-existing errors in two files this
plan never touches:
- `app/auth/dependencies.py` — missing-stub hints for `types-python-jose`.
- `app/connectors/jamf.py` — a Liskov override note comparing `authenticate()` signatures.

A byte-for-byte content diff (`comm -23` on line-number-stripped mypy output vs.
`mypy-baseline.txt`) confirms **zero** new/fixed lines reference `app/ticketing/schemas.py`
or `app/ticketing/service.py` (the only two files this plan modifies). This is the same
class of artifact STATE.md's Phase 24 history already documented and isolated
("a pre-existing mypy-baseline.txt note-line-number-drift artifact ... confirmed
unrelated").

**Disposition:** Out of scope (SCOPE BOUNDARY — pre-existing, unrelated files). Not fixed.
Logged here per the executor's deviation-tracking protocol. `ruff check`/`ruff format` and
the full `test_ticketing_dispatch.py` suite are unaffected and green.
