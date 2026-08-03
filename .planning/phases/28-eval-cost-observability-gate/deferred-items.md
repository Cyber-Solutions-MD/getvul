# Phase 28 — Deferred Items

Out-of-scope discoveries logged during plan execution (not fixed, per the
executor's scope-boundary rule: only auto-fix issues directly caused by the
current task's changes).

## 28-01: Pre-existing ruff-format drift (3 files, unrelated to this plan)

**Found during:** Task 2 post-implementation regression sweep (`ruff format --check .` across the whole `backend/` tree).

**Files:**
- `backend/tests/test_ai_explain_remediation_guidance.py`
- `backend/tests/test_ai_schemas.py`
- `backend/tests/test_connectors/test_rapid7_connector.py`

**Issue:** `ruff format --check .` reports these 3 files "would reformat" (formatting drift from the pinned `ruff==0.15.21` formatter's current output). `ruff check .` (linting) reports zero issues — this is purely a formatter-output drift, not a lint violation.

**Why deferred:** None of these files were touched by 28-01 (confirmed via `git log -- <file>` and `git status --short`: last commits are 26-01/25-02/23-01 respectively, all pre-dating this phase). Reformatting them is outside 28-01's task scope (schema/prompt-builder tests, not the eval harness).

**Suggested fix:** `cd backend && ruff format tests/test_ai_explain_remediation_guidance.py tests/test_ai_schemas.py tests/test_connectors/test_rapid7_connector.py` as a small standalone housekeeping commit, whenever convenient (does not block any Phase 28 plan).
