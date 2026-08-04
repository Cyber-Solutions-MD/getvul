# Deferred Items — Phase 29

## mypy-baseline "note" flux (pre-existing, out of scope)

**Discovered during:** Task 2 verification (29-01).

**Symptom:** `mypy app/ | mypy-baseline filter --allow-unsynced` intermittently reports
2-3 "new" errors even with `backend/app/auth/password.py` fully reverted to the committed
HEAD state (i.e. reproducible on unmodified `main`). The specific new lines are always
`note:` hints ("Hint: python3 -m pip install types-python-jose" and its two follow-on
notes) attached to whichever `jose`-importing file mypy happens to check first in a given
run (`app/auth/jwt.py`, `app/auth/service.py`, `app/auth/dependencies.py`, or
`app/connectors/google_workspace.py`). `mypy-baseline.txt` only baselines this note trio
once (against `google_workspace.py`), so any run where mypy attaches it to a *different*
file surfaces as "new" — a baseline/tooling flake, not a real type regression.

**Verification it's pre-existing:** `git stash` (reverting Task 2's `password.py` changes
entirely) + `rm -rf .mypy_cache` still reproduces the same "new: 3" (or "new: 6" with a
warm cache) result. Confirmed independent of any Phase 29 code change.

**Task-2-specific confirmation:** Diffed the full `mypy app/ | grep password.py` error
list before vs. after Task 2's edits (policy floor / similarity primitives / policy_override
param) — byte-identical multiset of 12 lines (7 `dict` type-arg, 1 `list` type-arg, 2
`arg-type`, 2 `assignment`), all pre-existing and already in `mypy-baseline.txt`. Task 2
introduces zero new mypy errors.

**Disposition:** Out of scope per the executor's SCOPE BOUNDARY rule (pre-existing failure
unrelated to this phase's file changes). Not fixed. A future maintenance task should either
`pip install types-python-jose` (removing the stub-missing warning entirely) or regenerate
`mypy-baseline.txt` with `mypy-baseline sync` to stabilize this flake.
