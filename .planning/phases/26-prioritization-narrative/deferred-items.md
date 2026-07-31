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
