# Deferred Items — Phase 26 (prioritization-narrative)

Out-of-scope discoveries logged during execution, per the executor's scope
boundary rule (only auto-fix issues directly caused by the current task's
changes; pre-existing issues in unrelated code are logged, not fixed).

## Plan 26-01

- **`backend/tests/test_ai_schemas.py` line ~184 — pre-existing `ruff format` drift.**
  `ruff format --check` flags `test_remediation_guidance_response_has_zero_new_fields`'s
  existing assertion (`assert set(ExplainRemediationGuidanceResponse.model_fields.keys()) == set(ExplainResponseBase.model_fields.keys())`)
  as exceeding the configured line length and wanting to wrap. This line was
  authored in Phase 25 Plan 02/04 and is untouched by 26-01's diff (26-01 only
  adds new lines; `git diff` shows 0 deletions on this file). Left as-is —
  fixing it would mix an unrelated formatting change into this plan's commit.
  `ruff check` (lint) passes clean; only `ruff format --check` (style) flags it.

- **`mypy-baseline.txt` note-line-number-drift artifact (recurrence of the Phase 24-02 finding).**
  `mypy app/ | mypy-baseline filter --allow-unsynced` (the exact CI gate,
  `.github/workflows/ci.yml` line 85) reports "3 new" violations. Isolated via
  diff: all 21 changed lines are `note:` (not `error:`) lines whose baseline
  entry has line number `0` while the live run reports the real line number
  (e.g. `app/auth/dependencies.py:0:` vs `:10:`), in 13 files never touched by
  this plan (`app/assets/router.py`, `app/auth/dependencies.py`,
  `app/auth/providers.py`, `app/connectors/{crowdstrike,defender,
  google_workspace,humaans_sync,jamf,jamf_sync,sync}.py`,
  `app/enrich_assets.py`, `app/vulnerabilities/{router,trends}.py`). Zero
  errors of any kind in `app/ai/grounding.py` / `app/ai/schemas.py` (the two
  files this plan modified) confirmed via `mypy app/ | grep '^app/ai/grounding.py\|^app/ai/schemas.py'`
  (empty output). Same phenomenon STATE.md already documents for Phase
  24-02 ("a pre-existing mypy-baseline.txt note-line-number-drift artifact
  ... confirmed unrelated"); not caused by, or fixable within, this plan.

## Plan 26-06

- **`mypy-baseline.txt` note-line-number-drift artifact (recurrence, 3rd occurrence this phase).**
  `mypy app/ | mypy-baseline filter --allow-unsynced` reports "3 new / 3
  fixed" after adding `AiBatchJob` to `backend/app/ai/models.py`. Isolated:
  all 3 changed lines are `note:` lines (stub-install hints for
  `types-python-jose`) attributed to `app/auth/dependencies.py:10` on this
  run vs. `app/connectors/google_workspace.py:0` in the baseline -- a file
  neither this plan nor its diff touches. Reproduced deterministically with
  a fully-cleared `.mypy_cache/` (ruling out stale-cache causation) and
  confirmed present even with zero code changes between two consecutive
  runs. `mypy app/ | grep '^app/ai/models.py'` returns empty (zero errors
  of any kind in the file this plan actually modified) -- direct proof the
  new `AiBatchJob` model/column additions introduce no real mypy debt.
  Same class as 26-01's and Phase 24-02's prior occurrences (missing local
  `types-python-jose` stub package; mypy's single "install this stub"
  hint attaches to whichever `jose`-importing file it happens to visit
  first in a given run, which drifts across environment states). Not
  caused by, or fixable within, this plan.

## Plan 26-07

- **Pre-existing untracked `scratchpad/roadmap_patch.py` at the repo root
  (timestamped 2026-07-29, predates this session).** `git status --short`
  shows `scratchpad/` as untracked at the start of this plan's execution —
  not created by this plan (no task in 26-07 writes to a `scratchpad/`
  directory), not referenced by anything this plan touches. Left as-is;
  not staged, not deleted, not added to `.gitignore` — out of scope, likely
  a leftover working file from an earlier plan's execution in this same
  phase. Flagged rather than silently ignored per the executor's untracked-
  files protocol.
- **`mypy app/vulnerabilities/service.py` in isolation surfaces 9
  pre-existing errors, none in `get_top_findings_for_ai_batch()`.** All 9
  (`Select` missing type-arg line 33; two `InstrumentedAttribute`
  assignment mismatches lines 109/114; `dict` missing type-arg lines
  239/256; `Result[Any]` has no `rowcount` + `no-any-return` pairs lines
  246/268) are already present verbatim in `mypy-baseline.txt` (grep
  `^app/vulnerabilities/service.py` — 9 matching entries, all pre-existing
  `list_vulnerabilities`/`update_vulnerability_status`/`bulk_update_status`
  code this plan's diff never touches). The new function (added at line
  524+) introduces zero new mypy errors. Not caused by, or fixable within,
  this plan.

## Plan 26-08

- **`mypy-baseline.txt` note-line-number-drift artifact (recurrence, 4th
  occurrence this phase).** `mypy app/ | mypy-baseline filter --allow-unsynced`
  reports "3 new / 3 fixed" after adding `poll_pending_batches()` to
  `backend/app/ai/batch.py` and the two scheduler dispatch blocks to
  `backend/app/connectors/scheduler.py`. Isolated: all 3 changed lines are
  the SAME `note:` lines (stub-install hints for `types-python-jose`)
  attributed to `app/auth/dependencies.py:10` -- a file neither this plan
  nor its diff touches. `mypy app/ | grep '^app/ai/batch.py\|^app/connectors/scheduler.py'`
  returns empty (zero errors of any kind in either file this plan actually
  modified) -- direct proof this plan's own diff introduces no real mypy
  debt. Same class as 26-01/26-06/26-07's prior occurrences. Not caused by,
  or fixable within, this plan.
- **Pre-existing untracked `scratchpad/` directory at the repo root, still
  present.** Confirmed via `git status --short` at the start of this
  plan's execution -- not created by this plan (no task in 26-08 writes to
  a `scratchpad/` directory). Already flagged by 26-07's own entry above;
  re-confirmed still present and still out of scope.
