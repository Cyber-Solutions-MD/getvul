---
phase: 27-ticket-auto-drafting
plan: 01
subsystem: api
tags: [pydantic, ticketing, mass-assignment, TDD, AID-01]

# Dependency graph
requires: []
provides:
  - "TicketCreateRequest.title: str | None (max_length=255 — Jira's hard summary ceiling, whitespace-coerces-to-None validator, extra='forbid' mass-assignment defense inherited) — the backend contract Plan 02's frontend Title Input will send"
  - "create_tickets() title WYSIWYG fallback: an analyst-supplied title replaces the auto-built '[sev] cve on host' ticket title verbatim; omitting it preserves the existing fallback unchanged"
  - "CreateTicketRequest.title?: string — frontend mutation type sibling to description, zero mutationFn change needed"
affects: [27-02, 27-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "title override mirrors Phase 25's description pattern class-for-class (Field + field_validator + ternary fallback), deviating only on max_length (255 — Jira's hard summary ceiling — vs description's 10000), per RESEARCH Pitfall 1 / Assumption A1"
    - "Fallback-assertion tests compute the expected value from the seeded fixture's own attributes (mirrors the pre-existing _build_task_description(vuln, hostname=None) precedent) rather than a hardcoded literal — caught a stale planning-doc assumption before it shipped"

key-files:
  created: []
  modified:
    - backend/app/ticketing/schemas.py
    - backend/app/ticketing/service.py
    - backend/tests/test_ticketing_dispatch.py
    - frontend/src/lib/mutations/use-create-ticket.ts

key-decisions:
  - "title max_length=255 (NOT description's 10000) — Jira's hard summary ceiling — converts RESEARCH Pitfall 1's silent create_tickets() `if url is None: ... continue` skip into a visible 422 at the mutation boundary"
  - "Fallback-title test assertion computed from vuln.severity/vuln.cve_id directly (mirroring create_tickets()'s own sev/cve fallback expressions) instead of the planning docs' hardcoded '[MEDIUM] {cve} on unknown host' literal — _seed_vuln() hardcodes severity='CRITICAL', so the literal from RESEARCH.md/PATTERNS.md would have failed against real fixture data"
  - "Task 1 shipped as a single feat commit with zero test-file changes (per the plan's own <files> scope); Task 2 added the full mirrored test suite in one test commit. Tests pass GREEN immediately since Task 1 already implements the correct behavior first — the same acknowledged pattern 25-06-SUMMARY.md documented for its own 'omitted' fallback test ('already passed, proving the fallback was never broken')"

patterns-established: []

requirements-completed: []  # AID-01 is only backend-contract-half delivered here. Plan 02 (frontend composer: title state + composed-once guard + Title Input) and Plan 03 (gap-fill "Draft with AI" affordance) complete the end-to-end feature. Mark AID-01 complete only after Plan 03 ships, per this phase's tracking_tool_caution.

# Metrics
duration: 11min
completed: 2026-08-01
---

# Phase 27 Plan 01: Ticket Title Override Backend Contract Summary

**`TicketCreateRequest.title` (max_length=255 — Jira's hard summary ceiling, not description's 10000) + `create_tickets()`'s WYSIWYG title fallback — mirrors Phase 25's `description` pattern class-for-class, proven at the `client.create()` call boundary.**

## Performance

- **Duration:** 11 min
- **Started:** 2026-08-01T11:47:00Z (approx, first file read)
- **Completed:** 2026-08-01T11:57:37Z
- **Tasks:** 2 completed
- **Files modified:** 4 (+ 1 deferred-items.md tracking note)

## Accomplishments

- `TicketCreateRequest` gained an optional, 255-length-bounded, whitespace-coercing `title` field — `extra="forbid"` mass-assignment defense already applies at the class level, so no new guard code was needed. Shape mirrors `description` exactly except the one deliberate deviation (255 vs 10000), per RESEARCH Pitfall 1 / Assumption A1.
- `create_tickets()`'s `task_name` assignment now honors `request.title` (stripped) when supplied, falling back unchanged to the existing `f"[{sev}] {cve} on {hostname or 'unknown host'}"` auto-build otherwise — proven at `FakeTicketingClient.create()`'s recorded call args (index `[0]`), not just the schema.
- `CreateTicketRequest.title?: string` added to the frontend mutation type; zero `mutationFn` changes needed — `JSON.stringify(body)` already serializes it, exactly as it did for `description` in Phase 25.
- D-05 scope boundary held: confirmed via `git diff --stat` that `dispatch.py`, `jira_client.py`, `asana_client.py`, `github_client.py`, `create_host_ticket()`, and `create_remediation_ticket()` all have **zero** diff — only `create_tickets()`'s own `task_name` line changed.
- Caught and fixed a stale literal in the planning docs before it could ship a misleading test: RESEARCH.md's Code Examples and PATTERNS.md's "Dispatch fallback tests to mirror" section both asserted the fallback title as `f"[MEDIUM] {vuln.cve_id} on unknown host"`, but the real `_seed_vuln()` fixture hardcodes `severity="CRITICAL"` — see Deviations below.
- Empirically proved the 255-cap test is a genuine regression guard (not vacuous): a throwaway Pydantic probe model with `max_length=10000` confirmed `"x"*256` would NOT raise under the old description-style cap, so the new test would have caught exactly the class of bug RESEARCH Pitfall 1 describes.

## Task Commits

Each task was committed atomically:

1. **Task 1: title override field + validator + create_tickets() fallback + frontend mutation type** — `65fc823` (feat)
2. **Task 2: mirror the description tests for title (schema + dispatch + 255-cap)** — `574e8e2` (test)

**Plan metadata:** (this commit, docs: complete plan)

## Files Created/Modified

- `backend/app/ticketing/schemas.py` — `TicketCreateRequest.title: str | None = Field(None, max_length=255)` + `@field_validator("title") def _title_no_ws_only` (identical body to `_no_ws_only`, distinct method name). Class docstring extended to document the new field alongside `description`'s existing note.
- `backend/app/ticketing/service.py` — `create_tickets()`'s `task_name` assignment converted to the same ternary-fallback shape as the existing `notes` assignment: `request.title.strip() if request.title and request.title.strip() else f"[{sev}] {cve} on {hostname or 'unknown host'}"`. The `client.create(task_name, notes, ...)` call site is unchanged.
- `backend/tests/test_ticketing_dispatch.py` — 4 schema tests (`test_ticket_create_request_title_whitespace_only_coerces_to_none`, `_omitted_is_valid`, `_valid_text_is_kept_verbatim_after_strip`, `_over_255_raises`) + 2 dispatch tests parametrized over ASANA/JIRA/GITHUB (`test_create_tickets_uses_request_title_when_supplied`, `test_create_tickets_falls_back_to_built_title_when_omitted`), asserting on `fake.created[0][0]` (title index).
- `frontend/src/lib/mutations/use-create-ticket.ts` — `CreateTicketRequest.title?: string` added as a sibling of `description?: string`; also tightened the now-stale `description` comment (removed the "no title/asset-context here" scope-fence line, since title now exists).
- `.planning/phases/27-ticket-auto-drafting/deferred-items.md` — new file, logs an unrelated pre-existing `mypy-baseline` note-diff (see Issues Encountered).

## Decisions Made

- **`title` max_length=255, not `description`'s 10000:** Jira's hard summary ceiling is the strictest of the three providers; capping at the Pydantic layer converts an over-length title from a silent `create_tickets()` skip (`if url is None: ... continue`) into a visible 422 at the mutation boundary. Matches RESEARCH Assumption A1 / Pitfall 1 exactly.
- **Task split honored as written:** Task 1 (schemas.py/service.py/use-create-ticket.ts) shipped as one `feat` commit with zero test-file changes, since its own `<files>` list excludes the test file. Task 2 then added the complete mirrored test suite as one `test` commit. This means the new tests pass GREEN immediately (Task 1's implementation already exists) rather than showing a literal RED failure first — the same outcome 25-06-SUMMARY.md already documented and accepted for its own dispatch-fallback test ("the 'omitted' branch already passed, proving the fallback was never broken").
- **Fallback-title test assertion computed from the vuln's own attributes, not a hardcoded literal** — see Deviations below.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed the planning docs' stale "[MEDIUM]" fallback-title literal**

- **Found during:** Task 2 (dispatch fallback test authoring)
- **Issue:** RESEARCH.md's "Code Examples" section and 27-PATTERNS.md's "Dispatch fallback tests to mirror" section both instruct asserting `fake.created[0][0] == f"[MEDIUM] {vuln.cve_id} on unknown host"` for the title-omitted fallback test, explicitly claiming this "match[es] `_seed_vuln`'s default severity/no-asset shape." Direct inspection of the actual `_seed_vuln()` fixture (test_ticketing_dispatch.py) shows it hardcodes `severity="CRITICAL"`, not an unset/None severity — so `create_tickets()`'s own `sev = vuln.severity or "MEDIUM"` resolves to `"CRITICAL"`, never `"MEDIUM"`. Writing the test with the planning docs' literal string would have produced a test that fails for the wrong reason (a bad assertion, not a real implementation regression) — or worse, silently passed only by coincidence if the fixture were ever set to `MEDIUM` later, masking the real fallback logic.
- **Fix:** Computed the expected title from the seeded vuln's own attributes — `f"[{vuln.severity or 'MEDIUM'}] {vuln.cve_id or 'Unknown vulnerability'} on unknown host"` — mirroring the exact robustness principle the pre-existing `description` fallback test already uses (`_build_task_description(vuln, hostname=None)`, a live function call over the fixture, never a hardcoded literal).
- **Files modified:** `backend/tests/test_ticketing_dispatch.py`
- **Verification:** Test passes against the real implementation (43/43 total, `-k title` isolates the 10 new instances all green). Empirically confirmed via a throwaway, non-committed Pydantic probe model that a hypothetical `max_length=10000` would NOT have raised on `"x"*256`, proving the (unrelated) 255-cap test's discriminating power is real, unaffected by this fix.
- **Committed in:** `574e8e2` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug — stale planning-doc literal)
**Impact on plan:** No scope creep; the fix keeps every new assertion factually accurate against the real fixture. All architectural boundaries (D-05: zero touch to dispatch.py/clients/create_host_ticket/create_remediation_ticket) held exactly as planned.

## Issues Encountered

- Backend tests require `ENCRYPTION_KEY` (a real Fernet key, not the literal string `"test"`) and `JWT_SECRET_KEY` env vars set per-invocation (documented project memory) — generated fresh each run via `python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"`.
- `ruff format` collapsed the new `title` `Field(...)` declaration onto a single line (unlike `description`'s, which stays wrapped across two lines because its longer `description=` string pushes it past the line-length limit) — reconfirmed all acceptance-criteria greps still matched after formatting.
- A pre-existing, environment-caused `mypy-baseline` diff (`fixed: 3, new: 3`, entirely inside the `note` category) surfaced when running the exact CI invocation (`mypy app/ | mypy-baseline filter --allow-unsynced`). Content-diffed (line-number-stripped) against `mypy-baseline.txt` and confirmed all 3 lines are informational hints in `app/auth/dependencies.py` (missing `types-python-jose` stub) and `app/connectors/jamf.py` (an `authenticate()` override note) — **zero** relation to `app/ticketing/schemas.py` or `app/ticketing/service.py`, the only two files this plan touches. This matches the same class of artifact STATE.md's Phase 24 history already documented and isolated. Logged to `deferred-items.md`, not fixed (out of scope, pre-existing, unrelated files).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The backend contract Plan 02's frontend Title `Input` will consume is complete, defended (mass-assignment + 255-char bound), and proven end-to-end at the `client.create()` call boundary — not just the schema or the DOM.
- Plan 02 can now safely add `title` state + the `resourceId`-keyed composed-once guard + a Title `Input` to `drill-content.tsx` (desktop) and `drill-panel-mobile.tsx` (mobile), threading `title` into `createTicket.mutateAsync`'s body, without risk of the backend silently discarding or mis-capping the analyst's edited title.
- **AID-01 remains NOT complete** (backend contract half only) — Plan 02 (frontend composer) and Plan 03 (gap-fill "Draft with AI" affordance + exported `AnalyzingIndicator`) complete the end-to-end feature. Per this phase's tracking guidance, do not flip the phase checkbox or mark AID-01 satisfied until Plan 03 ships.
- No blockers.

## TDD Gate Compliance

Both tasks are marked `tdd="true"`, but the plan's own file-scope split them into an implementation-only task (Task 1, `<files>` excludes the test file) followed by a dedicated test-authoring task (Task 2, `<files>` is the test file alone) — rather than each task carrying its own RED-then-GREEN pair. Executed faithfully to that explicit structure:
- Task 1: `feat` commit (`65fc823`) — schema field/validator, service.py fallback, frontend type. No test file changes (matches its own declared scope).
- Task 2: `test` commit (`574e8e2`) — the full mirrored test suite (4 schema + 2 dispatch × 3 providers = 10 instances). These pass GREEN on first run since Task 1's implementation already exists — an expected outcome given the task ordering, not a process failure. The plan's own acceptance criteria anticipates this exact outcome for the 255-cap test ("fails RED if the schema cap were 10000 ... passes GREEN against Task 1's max_length=255"), which was verified via a non-committed throwaway probe (see Accomplishments).
No REFACTOR commit was needed — both commits were minimal on first pass.

## Self-Check: PASSED

- `backend/app/ticketing/schemas.py` — FOUND, contains `title` field (`max_length=255`) + `_title_no_ws_only` validator.
- `backend/app/ticketing/service.py` — FOUND, contains `request.title.strip()` fallback in `create_tickets()`.
- `backend/tests/test_ticketing_dispatch.py` — FOUND, 10 new title test instances, all passing (43/43 total in file).
- `frontend/src/lib/mutations/use-create-ticket.ts` — FOUND, contains `title?: string`.
- `.planning/phases/27-ticket-auto-drafting/deferred-items.md` — FOUND.
- Commits `65fc823`, `574e8e2` — both FOUND in `git log --oneline`.

---
*Phase: 27-ticket-auto-drafting*
*Completed: 2026-08-01*
