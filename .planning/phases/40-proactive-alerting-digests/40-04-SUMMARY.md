---
phase: 40-proactive-alerting-digests
plan: 04
subsystem: alerting
tags: [fastapi, pydantic, sqlalchemy, jsonb, audit, pytest, mypy-baseline]

# Dependency graph
requires:
  - phase: 40-proactive-alerting-digests
    plan: "01"
    provides: "Tenant.alerting_config (JSONB) + DEFAULT_ALERTING_CONFIG/merged_alerting_config canonical contract, 3 xfail + 1 passing RED scaffolds in test_alerting_settings.py"
  - phase: 40-proactive-alerting-digests
    plan: "03"
    provides: "notifications/digests.py::_assemble_sections/_render_digest_html/_digest_plain_text/_digest_subject/_sections_empty -- reused verbatim by the test-digest preview"
provides:
  - "AlertingConfigUpdate (Pydantic partial-update validation gate, epss_threshold 0..1 / send_hour 0..23 / cadence daily|weekly / kev_enabled/per_owner_digests/per_team_digests bool / routing dict) + _safe_alerting pass-through"
  - "if \"alerting_config\" in body: PATCH /settings branch -- validate -> assign -> flag_modified -> fail-closed audit(\"alerting.config_update\", secret-free) -- cloned from the proven sla_config branch"
  - "alerting_config exposed on GET /settings (via _safe_alerting) for the Plan 05 pane to pre-fill"
  - "POST /settings/alerting/test-digest -- require_admin, self-targeted-only preview, returns {status: sent|empty|error} distinguishing D-14 empty-suppression from a real send failure"
affects: [40-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "AlertingConfigUpdate mirrors SlaConfigUpdate's partial-update shape exactly: every field Optional with a bound-checked Field(None, ...) rather than a required field with a schema-level default -- lets a caller PATCH a single key (e.g. just epss_threshold) without resubmitting the whole config, and the handler persists the raw submitted dict as-is (not the model's own serialization), same 'validation-only gate' convention SlaConfigUpdate documents for itself"
    - "alerting_config and sla_config both get their own dedicated audit action + are excluded from the generic settings.update 'changed' audit dict -- a pattern now established twice, safe for a future third JSONB config block to follow without re-deriving the exclusion list"
    - "test-digest reuses digests.py's assembly/render functions via a local (in-function) import, mirroring this file's existing inline-import convention (syslog configure/disable) rather than a module-level import -- avoids growing router.py's always-loaded import surface for a rarely-hit preview action"

key-files:
  created: []
  modified:
    - backend/app/tenants/router.py
    - backend/tests/test_alerting_settings.py
    - backend/mypy-baseline.txt

key-decisions:
  - "AlertingConfigUpdate fields are ALL Optional (not the plan text's literal 'kev_enabled: bool'/'send_hour: int' required-looking signatures) -- required, because test_alerting_config_change_audited submits a single-key partial body ({\"epss_threshold\": 0.6}) and expects 200; a required-field schema would 422 on any partial submission. Mirrors SlaConfigUpdate's own Optional-everywhere shape exactly, which already solves this same partial-update problem for sla_config."
  - "alerting_config PATCH persists the raw submitted dict directly (tenant.alerting_config = new_alerting), not merged with the previously-stored config -- same full-replace convention the existing sla_config branch already uses (tenant.sla_config = new_sla). A partial submission therefore drops any previously-set keys not resubmitted; this is pre-existing router.py behavior for sla_config, not a new gap introduced here, and merged_alerting_config()'s default-overlay (Plan 01) is exactly the mechanism that makes this safe for READERS (detection/digests always read through the merge, never the raw column)."
  - "test-digest's audit is deliberately NOT added -- it's a read-only preview action (no state mutation), unlike alerting_config PATCH which is fail-closed-audited. Matches the plan's own must_haves, which only require an audit row for the config SAVE path, not the preview send."
  - "mypy-baseline.txt: mypy-baseline sync's 'stable-sync' heuristic under-counts when an already-baselined message signature becomes MORE frequent (a same-file/same-message error occurring one additional time) -- confirmed by diffing exact per-(file,message) counts between raw mypy output and the synced baseline; the 1-line delta was hand-appended, matching the documented precedent from commit 47236ef (Phase 36 Plan 05) rather than trusting sync's output blindly."
  - "Split the two tasks' router.py/test file edits into genuinely separate commits (not just 'committed in order') by temporarily removing Task 2's code, committing Task 1's slice standalone with its own mypy-baseline resync, then re-adding Task 2's code and resyncing again -- avoids a single commit silently bundling both tasks' behavior."

requirements-completed: []  # ALERT-03 remains open per the Plan 01/03 convention -- Plan 05 is the designated closer for ALERT-01/02/03.

coverage:
  - id: D1
    description: "AlertingConfigUpdate validates epss_threshold 0..1 / send_hour 0..23 / cadence daily|weekly, 422s on violation; a valid save persists to Tenant.alerting_config with flag_modified and is exposed on GET /settings"
    requirement: "ALERT-03"
    verification:
      - kind: unit
        ref: "cd backend && pytest tests/test_alerting_settings.py -k 'validates or persists or owner' -x -- 3/3 pass (xfail markers removed, genuinely green, not xpass)"
        status: pass
      - kind: static
        ref: "grep -c 'class AlertingConfigUpdate' app/tenants/router.py == 1; GET /settings response literally contains \"alerting_config\""
        status: pass
    human_judgment: false
  - id: D2
    description: "Every alerting_config save fires a fail-closed 'alerting.config_update' audit row with secret-free details, excluded from the generic settings.update audit dict; PATCH stays require_owner, GET stays require_admin (RBAC asymmetry inherited, unchanged)"
    requirement: "ALERT-03"
    verification:
      - kind: unit
        ref: "cd backend && pytest tests/test_alerting_settings.py -k 'audited or owner' -x -- test_alerting_config_change_audited asserts exactly 1 audit row + 'channels' not in details; test_patch_requires_owner asserts 403 for a non-owner"
        status: pass
    human_judgment: false
  - id: D3
    description: "POST /settings/alerting/test-digest is require_admin-gated, sends the acting tenant's current digest to the acting admin's own email ONLY (no broadcast), and returns a status distinguishing sent/empty/error"
    requirement: "ALERT-03"
    verification:
      - kind: unit
        ref: "cd backend && pytest tests/test_alerting_settings.py -k test_digest -x -- 4/4 pass: requires_admin (viewer 403), empty_when_no_findings, error_when_smtp_not_configured, sent_targets_only_acting_admin (mocks send_email, asserts to==[admin_user.email], call_count==1)"
        status: pass
    human_judgment: false

duration: ~25min
completed: 2026-08-19
status: complete
---

# Phase 40 Plan 04: ALERT-03 -- Config Save, Audit & Test-Digest Preview Summary

**`AlertingConfigUpdate` (bounds/enum-checked partial-update gate) turns PATCH `/settings` `alerting_config` into a validated, fail-closed-audited, owner-gated save exposed on GET; `POST /settings/alerting/test-digest` lets an admin preview their tenant's current digest to themselves only, returning a sent/empty/error status the Plan 05 pane's E1 backstop consumes.**

## Performance

- **Duration:** ~25 min (autonomous, no checkpoints)
- **Started:** 2026-08-19T13:55Z (immediately after 40-03's metadata commit)
- **Completed:** 2026-08-19T14:20Z
- **Tasks:** 2/2 (Task 1 auto/tdd, Task 2 auto)
- **Files modified:** 3 (0 created, 3 modified)

## Accomplishments

- Cloned the proven `sla_config` PATCH-branch pattern for `alerting_config`: `AlertingConfigUpdate` (a Pydantic partial-update gate mirroring `SlaConfigUpdate`'s all-Optional shape, bound-checked `epss_threshold`/`send_hour`/`cadence`) validates whatever keys are submitted, the handler assigns the raw dict + `flag_modified` + fires a dedicated fail-closed `alerting.config_update` audit row (secret-free, excluded from the generic `settings.update` "changed" audit) -- turning 3 of Plan 01's `xfail(strict=False)` RED scaffolds into genuinely green, non-xfail tests
- `_safe_alerting` documented as an intentional pass-through (D-19: `alerting_config` never holds a channel secret, unlike `sla_config`'s `_safe_sla` mask-on-read) and wired into GET `/settings` so the Plan 05 pane can pre-fill
- Built `POST /settings/alerting/test-digest`: `require_admin`-gated, reuses `digests.py`'s `_assemble_sections`/`_render_digest_html`/`_digest_plain_text`/`_digest_subject`/`_sections_empty` verbatim (Plan 03) to assemble and render the ACTING tenant's current digest, sends via `send_email` to the acting admin's own email ONLY (never a tenant-wide recipient list -- T-40-18), and returns `{"status": "sent" | "empty" | "error", ...}` so the pane can branch without a false-positive error on a legitimately-quiet tenant
- Discovered and hand-fixed a `mypy-baseline sync` under-count (the tool's stable-sync heuristic doesn't detect an already-baselined message becoming *more frequent*) by diffing exact per-(file, message) counts against raw mypy output and appending the 1-line delta -- matching the documented precedent from Phase 36 Plan 05 (commit `47236ef`) rather than trusting `sync`'s output blindly
- Split the two tasks into genuinely independent commits (not just sequential edits landing in one commit) by temporarily reverting Task 2's code before Task 1's commit, then re-applying it -- each commit's own `mypy app/ | mypy-baseline filter` reports 0 new/0 fixed in isolation

## Task Commits

1. **Task 1: AlertingConfigUpdate gate + alerting_config PATCH branch + GET exposure + audit** -- `00b9009` (feat)
2. **Task 2: POST /settings/alerting/test-digest (single-recipient preview, distinguishable empty vs error)** -- `0d5fd76` (feat)

**Plan metadata:** pending (this SUMMARY's own commit)

## Files Created/Modified

- `backend/app/tenants/router.py` (modified) -- adds `AlertingConfigUpdate`, `_safe_alerting`, the `if "alerting_config" in body:` PATCH branch + `alerting.config_update` audit, `alerting_config` in the GET `/settings` response, the `changed`-dict exclusion, and `POST /settings/alerting/test-digest`
- `backend/tests/test_alerting_settings.py` (modified) -- removes the 3 `xfail(strict=False)` markers (behavior now real), updates the module docstring, adds 4 new tests for `test-digest` (admin-gating, empty, error, sent-targets-only-acting-admin)
- `backend/mypy-baseline.txt` (modified) -- 2 resyncs (one per task commit), +1 hand-appended line for the `sync`-under-count case documented above

## Decisions Made

See `key-decisions` in frontmatter for the full list (AlertingConfigUpdate's all-Optional shape necessity, raw-dict-persist full-replace convention inherited from `sla_config`, no audit on the read-only test-digest preview, the `mypy-baseline sync` under-count fix, and the deliberate task-commit split).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `AlertingConfigUpdate` field shapes deviated from the plan's literal signatures to make partial-update actually work**
- **Found during:** Task 1, while turning `test_alerting_config_change_audited` green
- **Issue:** The plan's `<action>` text lists field signatures like `kev_enabled: bool` and `send_hour: int = Field(ge=0, le=23)` with no default -- taken literally, these are pydantic-required fields. `test_alerting_config_change_audited` PATCHes a single-key body (`{"epss_threshold": 0.6}`); a required-field schema would 422 on that submission, contradicting the test's own `assert resp.status_code == 200`.
- **Fix:** Made every `AlertingConfigUpdate` field `Optional` with a bound-checked `Field(None, ...)`, exactly mirroring `SlaConfigUpdate`'s existing all-Optional partial-update shape (which solves the identical problem for `sla_config`). The plan's bounds themselves (0..1 / 0..23 / `daily`|`weekly` enum) are preserved exactly.
- **Files modified:** `backend/app/tenants/router.py`
- **Verification:** All 3 previously-xfail tests pass genuinely (not xpass); `test_alerting_config_validates_bounds` still 422s on `epss_threshold: 1.5`.
- **Committed in:** `00b9009` (Task 1 commit)

**2. [Rule 3 - Blocking] `mypy-baseline sync` silently under-counted a repeated error signature**
- **Found during:** Task 2, pre-commit mypy-baseline gate check
- **Issue:** After adding `send_test_digest` (no return type annotation, matching this file's existing convention), `mypy app/ | mypy-baseline sync` followed immediately by `mypy app/ | mypy-baseline filter` still reported `new: 1` -- the sync command's "stable-sync" heuristic (per commit `47236ef`'s own documented finding) doesn't detect a same-file/same-message error becoming MORE frequent by exactly one occurrence, so it silently wrote one fewer duplicate line than the raw mypy output actually contains.
- **Fix:** Wrote a small script diffing exact per-`(file, message)` counts between raw `mypy app/` output and the synced `mypy-baseline.txt`, confirmed the single delta (`app/tenants/router.py` / "Function is missing a return type annotation" -- baseline had 14, raw had 15), and hand-appended the 1 missing line.
- **Files modified:** `backend/mypy-baseline.txt`
- **Verification:** `mypy app/ | mypy-baseline filter --allow-unsynced` reports `fixed: 0, new: 0` after the manual append.
- **Committed in:** `0d5fd76` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 Rule 1 -- bug in taking the plan's field signatures too literally against the plan's own test bodies; 1 Rule 3 -- blocking tooling gap in `mypy-baseline sync`, now a second documented instance of the same known limitation).
**Impact on plan:** No scope creep, no architectural changes. Both fixes were required to satisfy the plan's own stated tests/gates; the `AlertingConfigUpdate` shape change is fully consistent with the plan's stated bounds (0..1/0..23/enum) and its own `<must_haves>` -- only the Optional-vs-required mechanics changed, not the validation rules.

## Issues Encountered

- `ENCRYPTION_KEY`/`JWT_SECRET_KEY` generated fresh per test invocation (real Fernet key + random secret) since persisted `.env` files aren't readable via the sandboxed shell -- matches this project's established pytest-env convention and every prior Phase 40 plan's precedent.
- Ran a broader regression pass beyond the plan's own minimum verification commands as a precaution: `test_sla_policy.py`, `test_digests.py`, `test_alerts_kev_epss.py`, `test_tenant_isolation.py`, `test_admin_hardening.py` (67 passed / 5 pre-existing xpassed from Plan 02's own scaffold, unrelated to this plan's files) -- zero regressions from this plan's two file changes.

## User Setup Required

None -- no external service configuration required. (A tenant must have `smtp_config.enabled`/`host` set for `test-digest` to actually send -- this is existing Phase 36 tenant-admin configuration, not new setup introduced by this plan; an unconfigured tenant correctly gets `{"status": "error", ...}` rather than a silent 200.)

## Next Phase Readiness

- Plan 05 (ALERT-03 settings pane) has a stable backend contract to consume: `alerting_config` on GET `/settings` (pre-fill), the validated PATCH `alerting_config` branch (save), and `POST /settings/alerting/test-digest` returning `{"status": "sent"|"empty"|"error"}` -- exactly the three states the UI-SPEC's E1 backstop needs to branch on.
- Per the Plan 01/03 convention, ALERT-01/02/03 remain intentionally unchecked in `REQUIREMENTS.md` -- Plan 05 is the designated closer for all three.
- No blockers. `test_alerting_settings.py` is fully green (8/8, zero xfail remaining); `mypy app/ | mypy-baseline filter --allow-unsynced` reports 0 new/0 fixed; `ruff check`/`ruff format --check` clean on both touched files.

## Self-Check: PASSED

`backend/app/tenants/router.py`, `backend/tests/test_alerting_settings.py`, `backend/mypy-baseline.txt` all confirmed modified and present via `git status`/`git show`. Both commit hashes (`00b9009`, `0d5fd76`) confirmed present via `git log --oneline -5`. No missing items.

---
*Phase: 40-proactive-alerting-digests*
*Completed: 2026-08-19*
