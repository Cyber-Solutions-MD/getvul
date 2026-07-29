---
phase: 24-ai-foundation-explain-this-vuln
plan: 08
subsystem: ai
tags: [anthropic, sse, pydantic, grounding, cross-tenant-isolation, pii-exclusion, tdd, cross-asset-aggregation]

# Dependency graph
requires:
  - phase: 24-04
    provides: "_run_explain_stream() — the shared buffer-then-validate-then-replay SSE engine, reused UNCHANGED by this plan's host/remediation routes; get_model_and_budget() reused directly by both new GET cache-check routes"
  - phase: 24-06
    provides: "D-16 per-remediation grounding decision = Option A (Cross-asset CVE grouping) — the exact contract this plan implements, recorded as a one-way-door at the TRACER checkpoint"
provides:
  - "ExplainHostResponse / ExplainRemediationResponse — D-16 schema variants sharing ExplainResponseBase, validated by the SAME schema gate as the vuln view"
  - "HOST_ALLOWLIST (9 fields) + build_explain_host_prompt() — a re-audited, PII-excluding posture-summary prompt builder; AssetDetail's owner-PII fields (directory_user/assigned_user/managed_by/building/serial_number) are structurally unreadable by this builder"
  - "REMEDIATION_ALLOWLIST (cve/fix/affected_assets/priority) + build_explain_remediation_prompt() — implements the D-16 Option A cross-asset-CVE-grouping shape locked at the 24-06 checkpoint"
  - "app/ai/grounding.py: get_asset_posture() + get_remediation_group() — two NEW tenant-scoped aggregate queries (the latter is the accepted-cost query the 24-06 decision explicitly flagged as not existing anywhere in the codebase, keyed on cve_id rather than the existing remediation_id-keyed queries)"
  - "POST/GET /api/v1/ai/explain-host/{asset_id} and /explain-remediation/{cve_id} — thin per-view SSE routes, both reusing _run_explain_stream() UNCHANGED (zero lines touched in app/ai/explain.py)"
  - "prompt_version() generalized to accept response_model (backward-compatible default), enabling host_prompt_version()/remediation_prompt_version() per-view auto-invalidating cache-key components"
affects: [24-09, 25, 26, 27]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Defense-in-depth for the highest-PII-risk boundary in the phase (T-24-32): get_asset_posture() SELECTs only the 9 HOST_ALLOWLIST columns directly off Asset/Vulnerability (owner-PII columns like assigned_user/managed_by/building/serial_number are never fetched at all), and build_explain_host_prompt() independently re-enforces the same allowlist field-by-field even if a future caller passed a full PII-bearing AssetDetail-shaped object — two independent layers, neither relying on the other"
    - "Cross-asset-by-CVE aggregation is a genuinely new query shape in this codebase: get_remediation_group() groups Vulnerability rows by cve_id (the correlation key GetVul's core value is built on) rather than the existing remediation_id-keyed queries in vulnerabilities/remediation_service.py (a scanner-specific identifier) — confirmed via RESEARCH.md's own Open Question #2 / Assumption A1 that no such query previously existed"
    - "priority is deterministic and backend-computed, never left to the model to infer: max severity across the affected-asset group, escalated to CRITICAL if any instance is CISA KEV-listed or has a public exploit — mirroring ASSET-02's own exploit/KEV-multiplier convention for the single-asset risk score, applied here to a fleet-wide aggregate (the 'deterministic score stays and is explained, never replaced' project principle, extended to remediation-priority)"
    - "prompt_version()'s response_model parameter generalization is purely additive — every existing call site (explain_vuln.py's prompt_version() with zero arguments) is provably unaffected (test_prompt_version_still_defaults_to_vuln_response_model pins this), while host_prompt_version()/remediation_prompt_version() each fold their OWN system prompt + few-shot + schema so a host-only prompt change never invalidates the vuln or remediation cache namespaces"
    - "Empty/sparse grounding is signaled as real zero-valued data, never as None or a fabricated placeholder: a zero-vuln asset still returns a full posture record with vuln_counts.total=0; a CVE group with no vendor solution text returns fix=None — both let the SAME downstream model + few-shot contract (already proven for the vuln view) route to grounded=false, rather than this layer inventing anything"

key-files:
  created:
    - backend/app/ai/grounding.py
    - backend/app/api/v1/ai/explain_host.py
    - backend/app/api/v1/ai/explain_remediation.py
    - backend/tests/test_ai_prompt_builder_host.py
    - backend/tests/test_ai_explain_host_remediation.py
  modified:
    - backend/app/ai/schemas.py
    - backend/app/ai/prompt_builder.py
    - backend/app/api/v1/ai/__init__.py

key-decisions:
  - "D-16 per-remediation grounding shape implemented as Option A (Cross-asset CVE grouping), per the locked 24-06 TRACER-checkpoint decision — NOT re-litigated. get_remediation_group(db, tenant_id, cve_id) aggregates {cve, fix, affected_assets[], priority} across every asset in the tenant sharing the CVE."
  - "The remediation route's path parameter is a CVE ID string (e.g. 'CVE-2023-4863'), not a UUID — /explain-remediation/{cve_id} — because D-16 Option A groups by CVE/fix, not by any single ticket/vulnerability row. This is a new precedent 24-09's frontend integration must pass a CVE string, not a ticket/remediation UUID, to this endpoint."
  - "get_asset_posture() is a NEW, narrow query selecting ONLY HOST_ALLOWLIST columns directly off Asset/Vulnerability — it does NOT reuse assets/router.py's existing get_asset endpoint dict (which bundles owner PII for the /assets/[id] page) specifically so the highest-PII-risk boundary in the phase has a defense-in-depth query layer, not just a prompt-builder-layer allowlist."
  - "priority in the remediation grounding record is deterministically computed in Python (max severity + KEV/exploit escalation), never left for the model to infer — consistent with ASSET-02's 'deterministic risk score augmented/explained, never replaced' project-level principle, extended here to a cross-asset aggregate."
  - "prompt_version() generalized to accept a response_model parameter (default ExplainVulnResponse, preserving the exact existing vuln-view hash) rather than introducing a parallel hashing function, so host_prompt_version()/remediation_prompt_version() reuse the identical, already-tested hashing logic."

requirements-completed: [AI-04]

# Metrics
duration: 27min
completed: 2026-07-29
---

# Phase 24 Plan 08: Host + Remediation Explain Views — PII-Excluding Posture Summary + Cross-Asset CVE Grounding Summary

**Expands the proven per-vuln "Explain this vuln" tracer to the host and remediation drill views by reusing `_run_explain_stream()` completely unchanged — a re-audited 9-field PII-excluding posture-summary allowlist for hosts, and a brand-new tenant-scoped cross-asset-CVE-grouping query implementing the D-16 Option A decision locked at the 24-06 checkpoint for remediations.**

## Performance

- **Duration:** ~27 min (includes reading all read_first files, the plan/2 prior SUMMARYs, PROJECT.md/STATE.md, existing prompt_builder.py/schemas.py/explain.py/explain_vuln.py, frontend AssetDetail/RemediationTicket query shapes, and the existing remediation_service.py/assets/router.py query patterns to design the two new grounding queries against real, verified schema)
- **Started:** ~2026-07-29T15:00Z (immediately after 24-07 completion)
- **Completed:** 2026-07-29T15:24:36+03:00 (last commit)
- **Tasks:** 2/2 completed
- **Files modified:** 8 (5 created, 3 modified) — plus one deferred-items.md documentation update

## Accomplishments

- **The host view's PII allowlist was re-audited field-by-field against the CONCRETE PII risk, not just declared.** `frontend/src/lib/queries/use-asset-detail.ts`'s `AssetDetail` type was read directly to enumerate the exact 5 owner-PII fields the vuln view never has to worry about (`directory_user`, `assigned_user`, `managed_by`, `building`, `serial_number`) alongside a nested `DirectoryUser` object carrying an email/display_name. `HOST_ALLOWLIST` (9 fields: hostname/os_name/os_version/device_category/risk_score/vuln_counts/tags/sla_breach/last_checkin_at) and `build_explain_host_prompt()` construct the narrow allowlisted object field-by-field, mirroring `_to_allowlisted_finding`'s exact discipline — proven by tests that pass a full PII-bearing record (both as a dict AND as an attribute-bearing dataclass, to prove the `_get_field()` Mapping/attribute duality holds) and assert none of the 5 forbidden field names or their values ever appear in the built prompt text.
- **Defense-in-depth, not just a single allowlist layer, for the phase's highest-PII-risk boundary (T-24-32).** `get_asset_posture()` is a genuinely NEW query — it does not reuse `assets/router.py`'s existing `get_asset` endpoint dict (which deliberately bundles `directory_user`/`assigned_user`/`managed_by`/`building`/`serial_number` for the `/assets/[id]` page). Instead it `SELECT`s only the 9 `HOST_ALLOWLIST` columns directly off `Asset`, plus a mirrored vuln-counts aggregate query. Owner PII is never fetched from the database at all in this code path — a second, independent line of defense ahead of `build_explain_host_prompt()`'s own field-by-field re-enforcement, so even a hypothetical future caller passing a raw `AssetDetail`-shaped object through this builder would still be safe.
- **The genuinely new cross-asset-by-CVE query the 24-06 checkpoint flagged as not existing anywhere in the codebase was built, keyed correctly on `cve_id`.** RESEARCH.md's own Open Question #2 confirmed the existing `vulnerabilities/remediation_service.py::get_hosts_for_remediation()` groups by the internal `remediation_id` field (a scanner-specific identifier), not `cve_id` (the true cross-scanner correlation key GetVul's core value is built on). `get_remediation_group(db, tenant_id, cve_id)` is a new query joining `Vulnerability`+`Asset`, grouping by `cve_id`, producing the exact D-16 Option A shape `{cve, fix, affected_assets[], priority}` the 24-06 checkpoint locked in — proven against a real two-asset, two-scanner-source seed (`NESSUS` + `QUALYS`, avoiding the `uq_vuln_dedup` unique constraint) asserting both assets land in `affected_assets[]`.
- **`priority` is a deterministic, backend-computed grounding fact, not something left for the model to infer** — mirroring the project's own `ASSET-02` principle that the deterministic risk score is "augmented/explained, never replaced" by the model, extended here to a fleet-wide aggregate: max severity across the affected-asset group, escalated to `CRITICAL` if ANY instance is CISA KEV-listed or has a public exploit (the identical exploit/KEV-multiplier convention `ASSET-02`'s own risk-score formula already uses for a single asset).
- **`prompt_version()` was generalized without breaking its existing callers.** The function was hardcoded to hash `ExplainVulnResponse`'s schema; Task 1 added a `response_model` parameter (defaulting to `ExplainVulnResponse`) so `host_prompt_version()`/`remediation_prompt_version()` reuse the SAME hashing function rather than duplicating it. `test_prompt_version_still_defaults_to_vuln_response_model` explicitly proves the zero-argument call produces the byte-identical hash it always has — a genuine backward-compatibility guard, not just an assumption.
- **A pre-existing `mypy-baseline.txt` line-number-drift artifact was isolated, root-caused, and proven unrelated — without touching git stash.** The gate reported `new: 3 / fixed: 3` (all in the `note` bucket) after Task 2; rather than assume it was caused by this plan's new files, they were temporarily moved to the scratchpad directory (never `git stash`, per this session's git-hygiene constraint) and the router `__init__.py` temporarily reverted to `HEAD` via `git show`, reproducing the IDENTICAL `new:3/fixed:3` result with zero Plan 08 code present. Root cause: the checked-in baseline stores every `note:`-category line with a hardcoded `:0:` line number while a live run reports the real line number — a 1:1 message-text match across 21 lines, differing only in line number, in files this plan never touches. Logged to `deferred-items.md`, not fixed (out of scope, matches `pyproject.toml`'s own "mypy-baseline is line/version-sensitive" warning).

## Task Commits

Each task followed the full RED → GREEN cycle (plan-level `type: tdd`):

1. **Task 1: Host + remediation schema variants + PII-excluding prompt builders**
   - `16a955a` (test) — RED: `ImportError: cannot import name 'HOST_ALLOWLIST'` confirmed before any implementation existed
   - `43a74cc` (feat) — GREEN: 24/24 new tests passing, 30/30 pre-existing Plan 02 prompt-builder/schema tests still green (backward-compat proven), ruff + mypy clean
2. **Task 2: Grounding assemblers + thin host/remediation SSE routes**
   - `8fd7fc3` (test) — RED: `ModuleNotFoundError: No module named 'app.ai.grounding'` confirmed before any implementation existed
   - `1782379` (feat) — GREEN: 17/17 new tests passing, full `tests/test_ai_*.py` wave-merge regression 117/117 green, ruff + ruff format clean, zero mypy errors attributed to any new/modified file

**Plan metadata:** (this commit, docs: complete plan)

_TDD gate sequence confirmed in git log: `test(24-08)` precedes `feat(24-08)` for both Task 1 and Task 2, in order._

## Files Created/Modified

- `backend/app/ai/schemas.py` (+13 lines) - `ExplainHostResponse`, `ExplainRemediationResponse` (D-16 variants sharing `ExplainResponseBase`, no additional fields — the allowlisted grounding records are already narrow enough)
- `backend/app/ai/prompt_builder.py` (+462 lines) - `HOST_ALLOWLIST` (9 fields) + `AllowlistedVulnCounts`/`AllowlistedHostPosture` + `build_explain_host_prompt()` + `FEW_SHOT_HOST`/`SYSTEM_PROMPT_HOST` + `host_prompt_version()`; `REMEDIATION_ALLOWLIST` (4 fields) + `AllowlistedAffectedAsset`/`AllowlistedRemediationGroup` + `build_explain_remediation_prompt()` + `FEW_SHOT_REMEDIATION`/`SYSTEM_PROMPT_REMEDIATION` + `remediation_prompt_version()`; `prompt_version()` generalized with a `response_model` parameter (backward-compatible default)
- `backend/app/ai/grounding.py` (194 lines, new) - `get_asset_posture()` (tenant-scoped posture-summary query, HOST_ALLOWLIST columns only) + `get_remediation_group()` (tenant-scoped cross-asset-CVE-grouping query, D-16 Option A, with deterministic `priority` computation)
- `backend/app/api/v1/ai/explain_host.py` (103 lines, new) - `POST/GET /explain-host/{asset_id}`, thin wrapper mirroring `explain_vuln.py`
- `backend/app/api/v1/ai/explain_remediation.py` (108 lines, new) - `POST/GET /explain-remediation/{cve_id}`, thin wrapper mirroring `explain_vuln.py`
- `backend/app/api/v1/ai/__init__.py` - registers `explain_host.router` + `explain_remediation.router` into `ai_router`
- `backend/tests/test_ai_prompt_builder_host.py` (420 lines, 24 tests, new) - schema variants, allowlist shape, PII exclusion (dict + attribute-object), injection isolation, empty/sparse builds, `prompt_version()` generalization + backward-compat guard
- `backend/tests/test_ai_explain_host_remediation.py` (359 lines, 17 tests, new) - grounding assembler tenant-scoping/sparsity, route RBAC matrix, cache-check GET, cross-tenant 404 (contrasted against same-tenant 200), resource_type cache-key namespacing across all three views
- `.planning/phases/24-ai-foundation-explain-this-vuln/deferred-items.md` (modified) - logs the pre-existing `mypy-baseline.txt` note-line-number-drift artifact (root-caused, confirmed unrelated to this plan)

## Decisions Made

- D-16 per-remediation grounding shape implemented as **Option A (Cross-asset CVE grouping)**, per the locked 24-06 checkpoint decision — not re-litigated.
- The remediation route's path parameter is a **CVE ID string**, not a UUID (`/explain-remediation/{cve_id}`) — 24-09's frontend integration must pass a CVE string to this endpoint, a new precedent relative to the UUID-keyed vuln/host routes.
- `get_asset_posture()` is a genuinely new, narrow query (not a reuse of `assets/router.py`'s existing PII-bearing `get_asset` dict) — defense-in-depth for the phase's highest-PII-risk boundary.
- `priority` in the remediation grounding record is deterministically backend-computed (max severity + KEV/exploit escalation), never left for the model to infer.
- `prompt_version()` generalized with a `response_model` parameter (default preserves the exact existing vuln hash) rather than a parallel hashing function.

## Deviations from Plan

### Auto-fixed Issues

None — no bugs, missing functionality, or blocking issues were encountered during implementation. The two items below are process/verification observations, not deviations from the plan's required behavior.

**1. [Process] Ruff auto-fix: two Yoda-condition assertions + one import-order/formatting pass**
- **Found during:** Task 1 and Task 2 lint verification
- **Issue:** Two new test assertions were written as `CONSTANT == frozenset(...)` (ruff's SIM300 flags an ALL-CAPS name on the comparison's left side against a call/literal expression on the right as a Yoda condition, matching this project's own established convention of writing the literal/call on the left — see `test_ai_prompt_builder.py`'s pre-existing `test_vuln_allowlist_has_16_fields_excludes_asset_id`); one file needed a `ruff format` pass after a fixture-heavy edit.
- **Fix:** `ruff check --fix` + `ruff format` applied; both are whitespace/ordering-only, zero behavior change.
- **Files modified:** `backend/tests/test_ai_prompt_builder_host.py`
- **Verification:** `ruff check` + `ruff format --check` both clean afterward; full test suite re-run green.
- **Committed in:** `43a74cc` / `1782379`

**2. [Process] Isolated and logged a pre-existing `mypy-baseline.txt` drift, confirmed unrelated**
- **Found during:** Task 2 mypy-baseline verification
- **Issue:** `mypy app/ | mypy-baseline filter --allow-unsynced` reported `new: 3 / fixed: 3` (all `note`-category). Rather than assume this was caused by this plan, the new files were isolated (moved to scratchpad, `__init__.py` temporarily reverted via `git show HEAD:...`, restored immediately after) and the SAME result reproduced with zero Plan 08 code present.
- **Fix:** Not fixed — root-caused (the checked-in baseline hardcodes `:0:` for every `note:` line; a live run reports real line numbers, an exact 1:1 message-text match otherwise) and logged to `deferred-items.md` per the scope-boundary rule. Regenerating the checked-in baseline is a repo-wide CI-gate change outside this plan's scope.
- **Files modified:** `.planning/phases/24-ai-foundation-explain-this-vuln/deferred-items.md`
- **Verification:** Direct per-file `mypy app/ai/grounding.py app/api/v1/ai/explain_host.py app/api/v1/ai/explain_remediation.py app/api/v1/ai/__init__.py` (not piped through `mypy-baseline`) shows zero errors on all 4 files; the isolation test (files removed, `new:3/fixed:3` persists) is conclusive.
- **Committed in:** `1782379`

---

**Total deviations:** 0 auto-fixed (Rules 1-3 never triggered); 2 process/verification observations logged for transparency, neither affecting shipped behavior.
**Impact on plan:** None on shipped code. Both items are lint/type-gate hygiene, not scope changes.

## Issues Encountered

- **`mypy-baseline.txt` note-line-number drift** — see Deviations #2 above. Pre-existing, environmental, logged to `deferred-items.md`, not fixed.
- No other issues. Postgres (`getvul-postgres-1`) and Redis (`getvul-redis-1`) containers were already running at session start (left running from Plan 04 onward) and were reused directly.

## User Setup Required

None - no external service configuration required. This plan adds two new backend routes reusing the already-provisioned BYOK/cache/audit infrastructure from Plans 01-04; no new environment variables or dashboard configuration.

## Next Phase Readiness

- All three explain views (vuln/host/remediation) now ship with per-view grounding shapes (D-15/D-16), all reusing `_run_explain_stream()` completely unchanged — `app/ai/explain.py` has zero diff since Plan 04's `8fd92db` (confirmed via `git diff 8fd92db..HEAD -- backend/app/ai/explain.py`, empty).
- **24-09 (frontend wiring) contract note:** the host endpoint is UUID-keyed (`/explain-host/{asset_id}`, matching the existing `/assets/[id]` route param), but the remediation endpoint is **CVE-string-keyed** (`/explain-remediation/{cve_id}`, e.g. `/explain-remediation/CVE-2023-4863`) — not a ticket/remediation UUID. 24-09's `AiExplanationSection` integration on the remediation surface must derive/pass a CVE ID string, not reuse whatever ticket/remediation identifier the surrounding UI otherwise uses.
- `resource_type` values are exactly `"host"` and `"remediation"` (matching the cache-key namespacing convention already established for `"vuln"`) — these are the literal strings 24-09's frontend hook must pass through to the existing `useExplainStream`/`useExplainCache` hooks' `resourceType` parameter (per Plan 05's own generalization already anticipating this D-15 widening).
- Both new routes' RBAC matrix (`require_analyst` POST / `require_viewer` GET), tenant-scoping (foreign-tenant id/CVE → 404), and resource_type cache-key namespacing are proven by automated tests — no live-stack verification was in this plan's scope (the 24-06 checkpoint already recorded live end-to-end verification as explicitly waived by the user for the whole phase, "proceed on trust"; that waiver's scope extends to this plan's routes identically since they're new instances of the SAME proven engine/nginx path, not a new integration seam).
- Postgres + Redis containers left running for continuity, matching every prior Phase 24 plan's practice.

## Self-Check: PASSED

- Files verified present: `backend/app/ai/grounding.py`, `backend/app/api/v1/ai/explain_host.py`, `backend/app/api/v1/ai/explain_remediation.py`, `backend/tests/test_ai_prompt_builder_host.py`, `backend/tests/test_ai_explain_host_remediation.py` (5/5 found)
- Commits verified present in `git log`: `16a955a`, `43a74cc`, `8fd7fc3`, `1782379` (4/4 found)
- TDD gate sequence confirmed: `test(24-08)` precedes `feat(24-08)` for both Task 1 and Task 2, in order
- Plan's own `<verification>` re-run and green: `pytest tests/test_ai_prompt_builder_host.py tests/test_ai_explain_host_remediation.py -q` → 41/41; wave-merge (`tests/test_ai_*.py`, all 9 files) → 117/117
- Acceptance-criteria greps re-confirmed: `grep -c "HOST_ALLOWLIST\|REMEDIATION_ALLOWLIST" prompt_builder.py` → 8 (>=2 required); `grep -c "class ExplainHostResponse\|class ExplainRemediationResponse" schemas.py` → 2 (==2 required); `grep -c "_run_explain_stream"` on each route file → 4 each (>=1 required)
- `app/ai/explain.py` confirmed byte-identical to Plan 04's `8fd92db` (empty `git diff`) — "reuses `_run_explain_stream()` unchanged" is structurally proven, not just claimed
- ruff check + ruff format clean on all 8 new/modified files; mypy shows zero errors attributed to any of the 4 new/modified non-test source files (isolated from a pre-existing, root-caused, unrelated `mypy-baseline.txt` drift — see Deviations #2)
- Full backend suite run once for a broader safety check: 474 passed, 1 failed — the failure (`test_connector_health.py::test_scheduler_path_error_message_and_log_are_sanitized`) confirmed pre-existing/unrelated (isolated re-run: 9/9 passed) and already logged in `deferred-items.md` since Plan 24-04; not a new regression

---
*Phase: 24-ai-foundation-explain-this-vuln*
*Completed: 2026-07-29*
