# Phase 37 — Deferred Items

Out-of-scope discoveries logged during execution (not fixed; outside the current task's file scope).

## `backend/uv.lock` untracked, ungitignored

**Found during:** 37-01 Task 1 (running `uv run alembic`/`uv run pytest` for the first time in this
worktree/session).

**Issue:** Running `uv run ...` materializes `backend/uv.lock` in the working tree. It is neither
committed nor listed in any `.gitignore` (no `backend/.gitignore` exists; root `.gitignore` doesn't
cover it). This is pre-existing repo state, unrelated to any file this plan modifies.

**Action:** Left untouched — not staged, not deleted, not added to `.gitignore`. Whether to commit
it (pin dependency resolution) or gitignore it (treat as a local build artifact) is a project-wide
tooling decision out of this plan's scope (`files_modified` in the 37-01 frontmatter does not include
it).
