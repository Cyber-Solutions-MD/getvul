# Phase 30 — Deferred Items

Out-of-scope discoveries logged during execution, not fixed (scope boundary: only auto-fix issues directly caused by the current task's changes).

## 30-01 Task 3

- **Pre-existing mypy `note` nondeterminism (not introduced by this plan).** Running `mypy app/ | mypy-baseline filter --allow-unsynced` (CI's exact gate) occasionally reports 2 extra transient `note` lines (`app/assets/service.py:81`/`:120`, "AssetSummary"/"AssetResponse" defined in...) beyond the stable 3-line `app/auth/dependencies.py:10` jose-stub-missing hint. Verified via `git stash` + `rm -rf .mypy_cache` + before/after diffing against a completely clean HEAD (zero Task 3 changes present): the exact same nondeterminism reproduces with or without this plan's `models.py`/`correlation_service.py` changes — confirmed identical to the flake already documented in Phase 29's SUMMARY. Not fixed; unrelated to any file this plan touches (`app/auth/dependencies.py`, `app/assets/service.py` are untouched by 30-01).
