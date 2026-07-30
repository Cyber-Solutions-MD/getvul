---
phase: 25-asset-aware-remediation-guidance
plan: 06
subsystem: api
tags: [pydantic, ticketing, mass-assignment, TDD, AIR-02]

requires:
  - phase: 25-05
    provides: "TRACER-gate sign-off (proceed-on-trust) — AIR-02 expansion unblocked"
provides:
  - "TicketCreateRequest.description: str | None (max_length=10000, whitespace-coerces-to-None validator, extra='forbid' mass-assignment defense) — the backend contract Plan 07's frontend textarea will send"
  - "create_tickets() WYSIWYG description override: an analyst-supplied description replaces the auto-built ticket body verbatim; omitting it preserves the existing fallback unchanged"
affects: [25-07]

tech-stack:
  added: []
  patterns:
    - "extra='forbid' mass-assignment defense added retroactively to an in-production schema (TicketCreateRequest), mirroring CommentCreate/BlockedUpdate's existing convention in the same file"
    - "Optional free-text field whitespace-coercion validator mirrors BlockedUpdate.blocked_reason's shape (coerce blank-after-strip to None, never raise) rather than CommentCreate's required-field raise-on-blank shape"

key-files:
  created: []
  modified:
    - backend/app/ticketing/schemas.py
    - backend/app/ticketing/service.py
    - backend/tests/test_ticketing_dispatch.py

key-decisions:
  - "extra='forbid' added to TicketCreateRequest (previously had no model_config) — a deliberate blast-radius judgment call per RESEARCH.md's Security Domain / Pattern 5, confirmed safe: grepped the codebase for every TicketCreateRequest(...) construction site (only tests + router body-passthrough) before applying, and the full 33-test test_ticketing_dispatch.py suite still passes."
  - "WYSIWYG replace (not append): a supplied description becomes the ENTIRE ticket body, never concatenated with the auto-built block — per RESEARCH Assumptions Log A3, adopted as-is."
  - "router.py needs no change — create_new_tickets() already passes the whole request body through to create_tickets(); description rides along automatically once the schema field exists. Confirmed via git diff --stat showing zero changes to router.py."

patterns-established: []

requirements-completed: []  # AIR-02 is only half-delivered here (backend contract). Plan 07 (also requirements:[AIR-02]) delivers the frontend pre-fill wiring that actually satisfies "populate a draft ticket description for the analyst to review". Mark AIR-02 complete when 25-07 ships, not here.

# Metrics
duration: 9min
completed: 2026-07-30
---

# Phase 25 Plan 06: Ticket Description WYSIWYG Backend Contract Summary

**Closed AIR-02's backend dead-end: `TicketCreateRequest.description` (bounded, mass-assignment-defended) plus `create_tickets()`'s one-line WYSIWYG override, proven at the `client.create()` call boundary — not just the schema.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-07-30T13:47:00+03:00 (approx, first RED test file edit)
- **Completed:** 2026-07-30T13:56:22+03:00
- **Tasks:** 2 completed
- **Files modified:** 3

## Accomplishments

- `TicketCreateRequest` gained an optional, length-bounded, whitespace-coercing `description` field with `extra="forbid"` mass-assignment defense (T-25-06, ASVS V5) — the exact contract shape RESEARCH.md's Pattern 5 specified.
- `create_tickets()`'s `notes=` assignment now honors `request.description` when non-empty, falling back to the unchanged `_build_task_description()` otherwise — proven by asserting on `FakeTicketingClient.create()`'s recorded `notes` argument (the external ticket body), not the DOM (Pitfall 4).
- Confirmed `router.py` needs zero changes — the description rides the existing `request=body` passthrough.
- Both tasks followed a strict RED→GREEN TDD cycle: tests were written and confirmed failing against the old code before any implementation change.

## Task Commits

Each task was committed atomically (test → feat per TDD):

1. **Task 1: TicketCreateRequest.description field + mass-assignment defense**
   - `b88ca16` (test) — 5 failing schema-validation tests (RED)
   - `dd550f1` (feat) — the field, validator, and `extra="forbid"` (GREEN)
2. **Task 2: create_tickets() WYSIWYG description override**
   - `e1eaa38` (test) — 2 parametrized (x3 provider) dispatch tests (RED — the "supplied" branch failed as expected; the "omitted" branch already passed, proving the fallback was never broken)
   - `c0d1d19` (feat) — the one-line `notes=` override + ruff-format pass on the test file (GREEN)

**Plan metadata:** (this commit, docs: complete plan)

## Files Created/Modified

- `backend/app/ticketing/schemas.py` — `TicketCreateRequest.description: str | None = Field(None, max_length=10000)`, `@field_validator("description")` coercing blank-after-strip to `None`, `model_config = {"extra": "forbid"}`.
- `backend/app/ticketing/service.py` — `create_tickets()`'s `notes` assignment: `request.description.strip() if request.description and request.description.strip() else _build_task_description(vuln, hostname)`.
- `backend/tests/test_ticketing_dispatch.py` — 5 new schema-validation tests (`test_ticket_create_request_description_*`) + 2 new parametrized dispatch tests (`test_create_tickets_uses_request_description_when_supplied` / `test_create_tickets_falls_back_to_built_description_when_omitted`), asserting on `fake.created[0][1]`.

## Decisions Made

- **`extra="forbid"` retrofit on an in-production schema:** RESEARCH.md flagged this as a deliberate judgment call (bigger blast radius than adding it to a brand-new schema). Verified safe by grepping every `TicketCreateRequest(...)` construction site in the codebase (only `router.py`'s body-passthrough and this test file) before applying, and confirming the full 33-test dispatch suite (covering ASANA/JIRA/GITHUB dispatch, rule-engine, sync, close, and HTTP-layer tests) still passes unchanged.
- **WYSIWYG replace, not append (RESEARCH Assumptions A3):** adopted as recommended — a supplied description is the entire ticket body, never concatenated with the auto-built CVE/host/product/remediation block. This is the analyst's reviewed, edited text; nothing is silently appended behind it.
- **No `router.py` change:** confirmed via `git diff --stat backend/app/ticketing/router.py` showing zero diff after both tasks — `create_new_tickets()` already forwards the whole request body.

## Deviations from Plan

None — plan executed exactly as written, including the exact recommended code (schema field shape, validator mirror, and the one-line service.py override) taken directly from RESEARCH.md Pattern 5 / PATTERNS.md.

## Issues Encountered

- Backend tests require `ENCRYPTION_KEY` (a real Fernet key, not the literal string `"test"`) and `JWT_SECRET_KEY` env vars set per-invocation (documented project memory, confirmed again here) — used `python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"` each run.
- `ruff format` flagged one line-wrapping change in the freshly-edited test file after Task 2's edits; applied `ruff format` and reconfirmed the full 33-test suite green before committing.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- The backend contract Plan 07's frontend textarea will consume is complete, defended (mass-assignment + length bound), and proven end-to-end at the `client.create()` boundary — not just the schema or the DOM.
- Plan 07 can now safely add `description?: string` to the frontend `CreateTicketRequest` mutation type and thread a controlled textarea through `DrillContent`'s `renderConfirm` (desktop) and `drill-panel-mobile.tsx` (mobile) without risk of the backend silently discarding the analyst's edited text.
- No blockers.

## Self-Check: PASSED

- `backend/app/ticketing/schemas.py` — FOUND, contains `description` field + `extra="forbid"`.
- `backend/app/ticketing/service.py` — FOUND, contains `request.description` at the `notes=` assignment.
- `backend/tests/test_ticketing_dispatch.py` — FOUND, 7 new tests, all passing (33/33 total in file).
- Commits `b88ca16`, `dd550f1`, `e1eaa38`, `c0d1d19` — all FOUND in `git log --oneline`.
- `backend/app/ticketing/router.py` — confirmed zero diff (no change required, as predicted).

## TDD Gate Compliance

Both tasks followed the mandatory RED→GREEN sequence, verified in git log order:
- Task 1: `test(25-06)` (b88ca16, RED — 5 failures confirmed) → `feat(25-06)` (dd550f1, GREEN — all pass).
- Task 2: `test(25-06)` (e1eaa38, RED — 3/6 failures confirmed, 3 already-passing fallback cases) → `feat(25-06)` (c0d1d19, GREEN — all 33 pass).
No REFACTOR commits were needed — both implementations were minimal on first GREEN pass.

---
*Phase: 25-asset-aware-remediation-guidance*
*Completed: 2026-07-30*
