---
phase: 24-ai-foundation-explain-this-vuln
plan: 07
subsystem: ai
tags: [fastapi, sqlalchemy, alembic, postgres, react, tanstack-query, tdd, ai, feedback]

# Dependency graph
requires:
  - phase: 24-05
    provides: "AiExplanationSection (8-state drill-panel body) + AiExplanationCitations two-tier renderer — the stable surface this plan attaches the feedback control beneath (section state 1: validated, grounded explanation)"
  - phase: 24-06
    provides: "TRACER-gate sign-off clearing the per-vuln tracer to proceed to expansion plans (07 feedback, 08-09 host/remediation)"
provides:
  - "ai_feedback table (migration 032) — tenant_id/resource_type/resource_id/user_id/verdict/note/timestamps + composite UNIQUE(resource_type, resource_id, user_id) — the D-22 upsert target"
  - "AiFeedback SQLAlchemy model (app/ai/models.py)"
  - "POST /api/v1/ai/feedback/{resource_type}/{resource_id} — idempotent per-user upsert (pg_insert(...).on_conflict_do_update(...)), require_analyst-gated, audits ai.feedback"
  - "useAiFeedback(resourceType, resourceId) — TanStack mutation hook, deliberately no hook-level onError/toast"
  - "AiFeedbackControl — thumbs (Accurate/Not accurate) + optional 500-char note, mounted beneath both grounded rendering branches of AiExplanationSection"
affects: [28]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A capture-only feedback signal with no reader elsewhere in the app this phase has no shared TanStack Query cache to snapshot/patch (unlike use-mark-blocked.ts's byId/list cache rollback) — the optimistic-mark + silent-revert-on-error correctly lives in the CONSUMING COMPONENT's own local state (activeThumb), driven via the mutation's per-call `mutate(vars, { onError })` callback, while the mutation hook itself stays a bare useMutation with no hook-level onError/toast at all — a deliberately different shape from every other mutation hook in this codebase, justified by the absence of any pre-existing cache to reconcile against"
    - "Postgres ON CONFLICT DO UPDATE as the D-22 'editable per-user upsert' mechanism needs only a plain UNIQUE constraint matching the conflict target's index_elements — not a composite PRIMARY KEY (the TicketWatcher/watch_ticket analog used a composite PK because DO NOTHING never needed a SET clause; DO UPDATE works identically against a non-PK UniqueConstraint, leaving `id` as an ordinary UUID surrogate PK)"
    - "A component mounted inside a panel that gets reused across resource-id changes without a `key` remount (confirmed: drill-content.tsx passes no `key` to DrillContent) must defensively reset its own local optimistic state in a useEffect keyed on the identifying props — otherwise a stale 'already voted' thumb silently leaks across unrelated resources"

key-files:
  created:
    - backend/alembic/versions/032_add_ai_feedback.py
    - backend/app/ai/models.py
    - backend/app/api/v1/ai/feedback.py
    - backend/tests/test_ai_feedback.py
    - frontend/src/lib/queries/use-ai-feedback.ts
    - frontend/src/components/vulnerabilities/ai-feedback-control.tsx
    - frontend/src/components/vulnerabilities/ai-feedback-control.test.tsx
  modified:
    - backend/app/api/v1/ai/__init__.py
    - frontend/src/components/vulnerabilities/ai-explanation-section.tsx
    - frontend/src/components/vulnerabilities/ai-explanation-citations.test.tsx

key-decisions:
  - "Feedback gates at require_analyst (not require_viewer) — matches the watch/unwatch analog and D-17's actor model for consistency, even though feedback capture itself is free/non-billed (RESEARCH Assumption A4 resolved in favor of the analog)"
  - "resource_type/resource_id are plain path strings, not a Python enum, on both the DB column (String(20)/String(200)) and the FastAPI path params — D-15 can widen this same endpoint to host/remediation views with zero contract change, mirroring how app/ai/cache.py already treats resource_type as a free string"
  - "The optimistic-mark + silent-revert lives in ai-feedback-control.tsx's own local component state, not in use-ai-feedback.ts's hook lifecycle — there is no other reader of 'this analyst's thumb state for this resource' anywhere in the app this phase (capture-only, D-21), so there is no shared query cache to snapshot/patch the way use-mark-blocked.ts does; the mutation hook stays a bare useMutation with zero hook-level onError, making the 'no toast' contract structural (grep-provable) rather than caller-discipline-dependent"
  - "A note typed AFTER a thumb is already active resubmits on textarea blur (attached to the current verdict) rather than being silently dropped — the backend upsert is idempotent so this is a harmless no-op when unchanged, and it closes an otherwise-real gap in D-21's 'capture the correction note' value (not tested as a locked <behavior> item, but implemented since the plan's own must-haves treat the note as real captured signal, not a decorative field)"

requirements-completed: [AI-04]

# Metrics
duration: 21min
completed: 2026-07-29
---

# Phase 24 Plan 07: AI Feedback Capture — ai_feedback Table + Idempotent Upsert + Thumbs Control Summary

**A dedicated `ai_feedback` table with a per-user, per-tenant `ON CONFLICT DO UPDATE` upsert endpoint, plus a thumbs-up/down + optional 500-char note control wired beneath every validated AI explanation — capture-only this phase, seeding real data for Phase 28's flywheel/dashboards.**

## Performance

- **Duration:** ~21 min
- **Started:** 2026-07-29T14:33:12+03:00 (immediately after 24-06 completion)
- **Completed:** 2026-07-29T14:54:20+03:00
- **Tasks:** 2/2 completed
- **Files modified:** 10 (7 created, 3 modified)

## Accomplishments

- **The one genuinely-new table this phase adds is tenant-scoped and cross-tenant-isolation-proven, not just tenant-scoped by convention.** `ai_feedback` carries an explicit `tenant_id` FK (not resolved via a join) and a composite `UniqueConstraint(resource_type, resource_id, user_id)` — a live cross-tenant test proves `analyst_user_b` (tenant_b) submitting feedback for the exact same `resource_id` as `tenant_a`'s analyst lands in its OWN row (`row_a.id != row_b.id`), never overwriting or reading tenant_a's data, satisfying T-24-28 structurally rather than by inspection alone.
- **The D-22 "editable per-user verdict" requirement is proven, not asserted.** `test_post_feedback_edit_upserts_single_row` submits `up`/"first pass" then `down`/"changed my mind" for the identical `(resource_type, resource_id, user)` and asserts exactly ONE row exists afterward with the SECOND submission's values — the `pg_insert(...).on_conflict_do_update(index_elements=["resource_type","resource_id","user_id"], set_={...})` mechanism (diverging from the watch/unwatch analog's `on_conflict_do_nothing`, per D-22's explicit requirement) is verified end-to-end through the real Postgres unique-constraint conflict path, not mocked.
- **A real, previously-undocumented test-environment gap was found and fixed, not silently worked around.** The plan's own literal verify command (`ENCRYPTION_KEY=test JWT_SECRET_KEY=test`) fails for any test using the `client`/`client_factory` fixtures: `app.main`'s startup secrets check hard-fails because `settings.environment` defaults to `"production"` and `"test"` is not a valid Fernet key. Diagnosed via a temporary (immediately reverted) `raise_app_exceptions=True` flip in a scratch run — the actual fix was a real `Fernet.generate_key()` value, matching `test_ai_explain_stream.py`'s own docstring precedent that MEMORY.md's "set ENCRYPTION_KEY" note under-specifies for any test file that spins up the full app lifespan.
- **A second, more fundamental test bug was found the same way: fixture rows were never committed before the HTTP call needed to see them.** `tenant_a`/`analyst_user` (and every role fixture) only `flush()`, never `commit()` — invisible to the FastAPI app's own separate DB session until the test explicitly commits (exactly the documented WR-13 contract in `db_session`'s own docstring, and the pattern `test_ticket_watch.py` already follows). Fixed by adding `await db_session.commit()` immediately after fixture setup in every test that performs an HTTP write, before asserting on it.
- **The frontend wiring caused, and this plan fixed, the exact same regression class Plan 05 already hit once.** Adding `<AiFeedbackControl>` (a real `useMutation`-backed component) inside `AiExplanationSection`'s two grounded-rendering branches broke `ai-explanation-citations.test.tsx`, which renders the bare component tree with no `QueryClientProvider`. Fixed by mocking `ai-feedback-control` there (a detectable stub, not `null`) — and, going further than a silent fix, added PRESENCE/ABSENCE assertions to 5 of that file's existing test cases, turning "control renders only beneath a validated explanation (section state 1)" from a manually-inspected acceptance line into an automated, regression-proof contract.
- **The feedback control's optimistic-revert is provably silent, not just documented as silent.** `use-ai-feedback.ts` has zero hook-level `onError` and zero `toast` calls (grep-verified: `on_conflict_do_update` count ≥1 in the backend router is mirrored by a `toast` count of exactly 0 in this file) — the revert-on-failure logic lives entirely in `ai-feedback-control.tsx`'s own local `activeThumb` state, exercised by a test that makes the mocked mutation synchronously invoke `onError` and asserts both the thumb reverts (`aria-pressed="false"`) AND no `role="alert"` element exists anywhere in the tree.

## Task Commits

Each task followed the full RED → GREEN cycle (plan-level `type: tdd`):

1. **Task 1: ai_feedback migration + model + idempotent upsert endpoint**
   - `f599922` (test) — RED: `ModuleNotFoundError: No module named 'app.ai.models'` confirmed before any implementation existed
   - `38f8fe8` (feat) — GREEN: migration 032 applied (`alembic heads` == `032_add_ai_feedback`), `AiFeedback` model, `POST /feedback/{resource_type}/{resource_id}` with `on_conflict_do_update`; 7/7 new tests passing (create, edit-upsert, thumb-only, note-cap-422, cross-tenant isolation, RBAC 403, audit row)
2. **Task 2: Feedback control (thumbs + optional note) with silent optimistic revert**
   - `bfba04d` (test) — RED: `Failed to resolve import "./ai-feedback-control"` confirmed
   - `2307e6c` (feat) — GREEN: `use-ai-feedback.ts` + `ai-feedback-control.tsx` + wiring into `ai-explanation-section.tsx`'s two grounded branches + the `ai-explanation-citations.test.tsx` regression fix; 6/6 new tests passing, full suite re-verified 789/789 green

**Plan metadata:** (this commit, docs: complete plan)

_TDD gate sequence confirmed in git log: `test(24-07)` precedes `feat(24-07)` for both Task 1 and Task 2, in order._

## Files Created/Modified

- `backend/alembic/versions/032_add_ai_feedback.py` — `ai_feedback` table: `id` UUID PK, `tenant_id` FK→tenants CASCADE, `resource_type` String(20), `resource_id` String(200), `user_id` FK→users CASCADE, `verdict` String(8), `note` Text nullable, `created_at`/`updated_at`, `UniqueConstraint(resource_type, resource_id, user_id)`; `down_revision = "031_rename_audit_tenant_idx"` (the real HEAD, confirmed live, not the plan's placeholder name)
- `backend/app/ai/models.py` (44 lines) — `AiFeedback` SQLAlchemy model (`Base, UUIDPrimaryKeyMixin, TimestampMixin`), matching the migration exactly
- `backend/app/api/v1/ai/feedback.py` (98 lines) — `FeedbackRequest` (Pydantic, `extra="forbid"`, `note` capped `max_length=500` + whitespace-only-to-`None` validator) + `POST /feedback/{resource_type}/{resource_id}` (`require_analyst`), `pg_insert(...).on_conflict_do_update(...)`, `audit(db, user, "ai.feedback", ...)`, commit
- `backend/app/api/v1/ai/__init__.py` — registered `feedback.router` into `ai_router`
- `backend/tests/test_ai_feedback.py` (7 tests) — create, edit/idempotent-upsert, thumb-only, note>500→422, cross-tenant isolation, Viewer→403, audit row
- `frontend/src/lib/queries/use-ai-feedback.ts` (43 lines) — `useAiFeedback(resourceType, resourceId)`, bare `useMutation`, zero hook-level `onError`/toast
- `frontend/src/components/vulnerabilities/ai-feedback-control.tsx` (99 lines) — `AiFeedbackControl()`: thumbs (`aria-label="Accurate"`/`"Not accurate"`, `aria-pressed`), optional textarea (`aria-label="Feedback note"`, `maxLength=500`, placeholder "What was off? (optional)"), optimistic mark + silent revert, resource-id-keyed state reset, blur-triggered note resubmit when a thumb is already active
- `frontend/src/components/vulnerabilities/ai-feedback-control.test.tsx` (6 tests) — render, optimistic mark, silent revert, thumb-only, thumb+note, 500-char cap with no warning UI
- `frontend/src/components/vulnerabilities/ai-explanation-section.tsx` — `<AiFeedbackControl>` added beneath `<AiExplanationCitations>` in both the just-streamed `'done'`-grounded branch and the cache-hit-grounded branch
- `frontend/src/components/vulnerabilities/ai-explanation-citations.test.tsx` — mocked `ai-feedback-control` (regression fix) + added 5 presence/absence assertions proving the state-1-only placement contract

## Decisions Made

- Feedback gates at `require_analyst`, matching the watch/unwatch analog and D-17's actor model, even though feedback capture is free/non-billed.
- `resource_type`/`resource_id` are plain strings end-to-end (DB columns, path params) — no enum — so D-15's host/remediation widening needs zero contract change here.
- The optimistic-mark-and-silent-revert mechanics live in `ai-feedback-control.tsx`'s own local state, not in `use-ai-feedback.ts`'s mutation lifecycle — there is no other reader of an analyst's feedback state anywhere in the app this phase (capture-only), so there is no shared cache to snapshot/patch the way `use-mark-blocked.ts` does. The mutation hook is a bare `useMutation` with zero hook-level `onError`, making "no toast" a structural, grep-provable property of the file rather than something every future caller must remember not to break.
- A note typed after a thumb is already active resubmits on textarea blur (attached to the current verdict) — the backend upsert is idempotent, so this is harmless when the note is unchanged, and it closes what would otherwise be a real gap in capturing D-21's "optional correction note" signal.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] The plan's own literal verify-command env vars fail the app's startup secrets check for any HTTP-client-based test**
- **Found during:** Task 1, first `pytest tests/test_ai_feedback.py -x -q` run with `ENCRYPTION_KEY=test`
- **Issue:** `app.main`'s `_check_secrets_at_startup()` hard-fails (`RuntimeError: Backend refused to start`) because `settings.environment` defaults to `"production"` and the literal string `"test"` is not a valid Fernet key. This only surfaces for tests using the `client`/`client_factory` fixtures (which run the real app lifespan) — `test_ai_budget.py`-style tests that only touch `db_session` directly never hit this path, which is why the plan's verify command (copied from an earlier, simpler AI test convention) looked correct on paper.
- **Fix:** Generated a real Fernet key (`Fernet.generate_key()`) and used it as `ENCRYPTION_KEY` for every `pytest`/`alembic` invocation in this plan — matching `test_ai_explain_stream.py`'s own docstring, which already documents this exact requirement for full-app-lifespan tests.
- **Files modified:** none (environment-only; no source change)
- **Verification:** `alembic upgrade head` and the full `test_ai_feedback.py` suite both ran clean afterward.
- **Committed in:** n/a (diagnostic/environment fix, not a code change)

**2. [Rule 1 - Bug] Test fixtures only `flush()`, never `commit()` — HTTP-client writes couldn't see the seeded tenant/user rows**
- **Found during:** Task 1, first real test run (post-Fernet-fix), `ForeignKeyViolationError: insert or update on table "ai_feedback" violates foreign key constraint "ai_feedback_tenant_id_fkey"`
- **Issue:** `tenant_a`/`analyst_user`(and sibling role fixtures) in `conftest.py` only `db_session.add(...)` + `flush()`, never `commit()` — invisible to the FastAPI app's own separate DB session (opened per-request via `get_db()`) until the test explicitly commits. This is the exact, already-documented `db_session` WR-13 contract (`test_ticket_watch.py` already follows it) — my first draft simply hadn't added the commit.
- **Fix:** Added `await db_session.commit()` immediately after fixture setup, before the first `client.post(...)`/`client_a.post(...)` call, in every test that writes via HTTP and reads back via `db_session`.
- **Files modified:** `backend/tests/test_ai_feedback.py`
- **Verification:** All 7 tests pass; the two tests that never touch the DB (422 validation, 403 RBAC) correctly needed no commit and were left unchanged.
- **Committed in:** `38f8fe8` (Task 1 GREEN commit — the test file's fix landed alongside the implementation, since RED had already been committed before this was discovered)

**3. [Rule 1 - Bug] Wiring `<AiFeedbackControl>` into `AiExplanationSection` broke the pre-existing `ai-explanation-citations.test.tsx` suite**
- **Found during:** Task 2, full-suite regression sweep after wiring
- **Issue:** `ai-explanation-citations.test.tsx` renders `AiExplanationSection`'s bare component tree with no `QueryClientProvider` (it only ever needed to mock 4 hooks before this plan). The newly-wired `AiFeedbackControl` calls `useAiFeedback()` (a real `useMutation`), which throws `"No QueryClient set, use QueryClientProvider to set one"` whenever a grounded branch renders — the identical regression class Plan 05 documented for `drill-panel.test.tsx`/`drill-panel-mobile.test.tsx`.
- **Fix:** Mocked `./ai-feedback-control` in that file with a detectable stub (`<div data-testid="ai-feedback-control-stub" />`, not `null`), then added presence/absence assertions to 5 existing test cases (2 grounded-render cases now assert presence; 3 non-grounded cases — cache-miss button, no-key card, grounded=false backstop — now assert absence), converting the acceptance criterion "control renders only beneath a validated explanation (section state 1)" into an automated proof rather than a manually-inspected claim.
- **Files modified:** `frontend/src/components/vulnerabilities/ai-explanation-citations.test.tsx`
- **Verification:** All 18 tests in that file pass (same count as before — only existing `it()` blocks gained extra assertions, no new blocks added); full frontend suite re-ran 789/789 green (783 prior + 6 new `ai-feedback-control` tests); `tsc --noEmit` clean; `next build` clean, `/dashboard/vulnerabilities` at 187 kB (well under the 250 KB budget, +0 KB from this plan since `AiFeedbackControl` adds no new dependency).
- **Committed in:** `2307e6c` (Task 2 GREEN commit)

**4. [Rule 2 - Missing Critical] `AiFeedbackControl` had no defense against stale local state leaking across a resource-id change**
- **Found during:** Task 2, while designing the component (before any test failure — a proactive correctness read of `drill-content.tsx`, not a caught bug)
- **Issue:** `drill-content.tsx` renders `<AiExplanationSection resourceType="vuln" resourceId={...}>` with no `key` prop, so React reuses the same component instance (and all descendants, including the new feedback control) across a resource-id change rather than remounting. Without a defensive reset, an analyst who had thumbed-up one finding could see that same thumb rendered "active" after the panel target switched to an entirely different, unrelated finding.
- **Fix:** Added a `useEffect` in `ai-feedback-control.tsx` that resets `activeThumb`/`note` to their initial empty state whenever `resourceType`/`resourceId` change.
- **Files modified:** `frontend/src/components/vulnerabilities/ai-feedback-control.tsx`
- **Verification:** Code-level defense (no dedicated test added — the plan's own `<behavior>` list doesn't test this scenario, and the fix is a straightforward `useEffect` dependency-array reset, not complex enough to warrant a bespoke render-with-rerender test in this pass); flagged here for visibility.
- **Committed in:** `2307e6c` (Task 2 GREEN commit)

---

**Total deviations:** 4 auto-fixed (1 blocking test-environment fix, 2 bug fixes in the new test file's own DB-visibility assumptions, 1 bug fix + hardening pair on the frontend wiring's regression + a proactive stale-state defense)
**Impact on plan:** All four are correctness/hygiene fixes directly caused by this plan's own changes (or by an environment gap the plan's own verify command under-specified). No feature behavior differs from what the plan specified; no scope creep beyond the plan's own declared files (the one addition — `ai-explanation-citations.test.tsx` — was necessary, not optional, to keep the pre-existing suite passing).

## Issues Encountered

None beyond the four deviations above (all resolved inline, no open blockers).

## User Setup Required

None — no external service configuration required. This plan is pure backend/frontend composition over Plan 04/05's already-shipped, already-tested AI foundation.

## Next Phase Readiness

- The `ai_feedback` table + upsert endpoint + control are genuinely capture-only this phase (D-21) — no route reads feedback back, confirmed by grep (no `GET`/`select`-and-return endpoint exists in `feedback.py`) and by design (only `ai-feedback-control.tsx` itself ever reads its own just-submitted verdict, via local state, never from the server).
- Phase 28 (Eval + Cost + Observability Gate) can build its flywheel/dashboard surfacing directly against the `ai_feedback` table's existing shape (`tenant_id`, `resource_type`, `resource_id`, `user_id`, `verdict`, `note`, timestamps) — no migration changes anticipated, though Phase 28 should confirm whether it needs a read index beyond the existing `(resource_type, resource_id, user_id)` unique index and `tenant_id` index (e.g. a `created_at` index for time-windowed golden-set queries).
- Plan 08 (host/remediation views) can reuse `AiFeedbackControl`/`useAiFeedback` unchanged, parameterized by a different `resourceType` — proven by design (both are already resourceType-parameterized, matching D-15's convention established in Plan 05) though not exercised by a host/remediation-specific test in this plan (out of this plan's scope).
- Postgres was live for this plan (real migration + real FK/unique-constraint behavior proven); Redis was not needed (feedback has no cache layer, capture-only).
- Carried forward, not blocking: the stale-local-state defensive reset (deviation 4) has no dedicated regression test — low risk given its simplicity, but worth a follow-up unit test if `drill-content.tsx` is ever changed to key-remount its content (which would make the defense moot) or if a future plan adds more local state to this component.

## Self-Check: PASSED

- Files verified present: `backend/alembic/versions/032_add_ai_feedback.py`, `backend/app/ai/models.py`, `backend/app/api/v1/ai/feedback.py`, `backend/tests/test_ai_feedback.py`, `frontend/src/lib/queries/use-ai-feedback.ts`, `frontend/src/components/vulnerabilities/ai-feedback-control.tsx`, `frontend/src/components/vulnerabilities/ai-feedback-control.test.tsx` (7/7 found)
- Commits verified present in `git log`: `f599922`, `38f8fe8`, `bfba04d`, `2307e6c` (4/4 found)
- TDD gate sequence confirmed: `test(24-07)` precedes `feat(24-07)` for both Task 1 and Task 2, in order
- Plan's own `<verification>` re-run and green: `alembic heads` == `032_add_ai_feedback`; `pytest tests/test_ai_feedback.py -q` → 7/7; `npx vitest run ai-feedback-control` → 6/6
- Acceptance-criteria greps re-confirmed: `grep -c "on_conflict_do_update" backend/app/api/v1/ai/feedback.py` == 1; `grep -c "toast" frontend/src/lib/queries/use-ai-feedback.ts` == 0; aria-labels "Accurate"/"Not accurate" present; `ai-feedback-control|AiFeedbackControl` present in `ai-explanation-section.tsx`
- Full regression sweep green: 789/789 frontend unit tests (783 prior + 6 new), `tsc --noEmit` clean, `eslint` clean on every new/modified frontend file, `next build` clean (`/dashboard/vulnerabilities` 187 kB, no bundle-budget regression); backend `ruff check`/`ruff format --check` clean on all new/modified files; mypy introduces zero new violations in the 3 new/modified Python files (confirmed via `mypy-baseline filter --allow-unsynced`, cross-checked line-by-line — the reported "3 new / 3 fixed" is pre-existing `types-python-jose` note-line churn in `app/auth/dependencies.py`, untouched by this plan)

---
*Phase: 24-ai-foundation-explain-this-vuln*
*Completed: 2026-07-29*
