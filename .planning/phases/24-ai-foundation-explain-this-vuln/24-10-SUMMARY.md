---
phase: 24-ai-foundation-explain-this-vuln
plan: 10
subsystem: ai
tags: [fastapi, tanstack-query, tdd, rbac, gap-closure]

# Dependency graph
requires:
  - phase: 24-03
    provides: "get_tenant_anthropic_key(db, tenant_id) -> str | None -- the tenant-scoped, no-fallback BYOK key resolution this plan's new route reads from directly (never the admin-only connectors listing)"
  - phase: 24-05
    provides: "AiExplanationSection's 8-state body + the existing D-23 role-gated no-key card branches (Admin/Owner 'Configure AI' CTA, Analyst/Viewer 'ask an admin' nudge) -- this plan preserves that chrome/copy verbatim and swaps only the boolean signal feeding it"
provides:
  - "GET /api/v1/ai/status (require_viewer) -> {configured: bool}, tenant-scoped via get_tenant_anthropic_key, never echoes key material"
  - "useAiStatus() TanStack query hook + queryKeys.ai.status() -- the real, non-admin-safe replacement for the isError-based optimistic guess"
  - "AiExplanationSection's keyConfigured now derives from Boolean(statusQuery.data?.configured) for all four roles (Owner/Admin/Analyst/Viewer)"
  - "Closes 24-VERIFICATION.md's only code-proven gap (truth #2, D-23 no-key role-gating)"
affects: [25, 26, 27]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A lightweight require_viewer boolean-signal endpoint (never the admin-gated resource listing) is the correct pattern whenever a UI needs to role-gate on a resource's configured/enabled state without leaking the resource itself -- reusable precedent for any future 'is X configured' check spanning multiple RBAC tiers"

key-files:
  created:
    - backend/app/api/v1/ai/status.py
    - backend/tests/test_ai_status.py
    - frontend/src/lib/queries/use-ai-status.ts
  modified:
    - backend/app/api/v1/ai/__init__.py
    - frontend/src/lib/queries/keys.ts
    - frontend/src/components/ai/ai-explanation-section.tsx
    - frontend/src/components/ai/ai-explanation-section.test.tsx
    - frontend/src/components/vulnerabilities/drill-panel.test.tsx
    - frontend/src/components/vulnerabilities/drill-panel-mobile.test.tsx

key-decisions:
  - "GET /api/v1/ai/status is require_viewer-gated (the floor, matching the existing explain-vuln GET cache-check precedent) rather than role-specific -- a boolean 'is AI on' carries no sensitive data (T-24-42 accept disposition in the plan's own threat model)"
  - "status.py's docstring deliberately avoids the literal substrings ConnectorConfig/api_key/credentials_secret_arn/decrypt_value so its own no-credential-handling grep gate holds without weakening the actual code or its explanatory value"
  - "keyConfigured is now a direct Boolean(statusQuery.data?.configured) read -- the old isError-based optimistic pass-through and its explanatory comment are deleted outright, not merely bypassed"

patterns-established:
  - "Non-admin-safe boolean status endpoints derive from the SAME source of truth the paid/privileged path uses (get_tenant_anthropic_key), never a parallel/duplicated check -- keeps the signal and the enforcement mechanism from drifting apart"

requirements-completed: [AI-01]

# Metrics
duration: 25min
completed: 2026-07-29
---

# Phase 24 Plan 10: Gap Closure — Real ai-status Signal Summary

**Added a require_viewer `GET /api/v1/ai/status` boolean endpoint + `useAiStatus()` hook, replacing the `connectorsQuery.isError` optimistic guess so Analyst/Viewer get an accurate "is AI configured" signal instead of the admin-gated connectors query's 403 pass-through.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 2 completed
- **Files modified:** 9 (7 planned + 2 in-scope regression fixes)

## Accomplishments

- Closed the one code-proven gap from `24-VERIFICATION.md` (truth #2, D-23 no-key role-gating): Analyst/Viewer previously saw a live "Explain this vuln" button in a genuinely unconfigured tenant (because `GET /api/v1/connectors` is `require_admin`-gated and always 403s for them, and the old code read that error as "assume configured"), and on click got the permanently-wrong amber "AI busy — try again in a moment" card.
- New backend endpoint `GET /api/v1/ai/status` (`require_viewer`) returns `{"configured": bool}` derived from the exact same source of truth the engine uses (`get_tenant_anthropic_key(...) is not None`), tenant-scoped, proven to never leak credential material.
- Frontend `useAiStatus()` hook + swapped `keyConfigured` derivation in `AiExplanationSection` — the existing, already-correct D-23 role-gated no-key card (Admin/Owner CTA, Analyst/Viewer nudge) now receives a real signal for every role instead of an optimistic guess.
- Regression coverage rewritten to exercise real production behavior: the prior "no-key + Analyst" test mocked a `connectors: {isError:false, data:[]}` state that could never occur in production for that role; it and 5 new tests now mock the real `useAiStatus` signal across the full role x configured-state matrix.

## Task Commits

Each task followed the RED → GREEN TDD cycle, committed atomically:

1. **Task 1: Backend `GET /api/v1/ai/status`**
   - `0a8855a` (test — RED): 5 failing tests (404s, route didn't exist)
   - `472e17c` (feat — GREEN): route + registration; 5/5 pass
2. **Task 2: Frontend real-signal consumption**
   - `692d68e` (test — RED): re-pointed + expanded tests; 37/38 failing (real `useConnectorsList()` threw `No QueryClient set` since production code hadn't changed yet)
   - `28982a2` (feat — GREEN): `use-ai-status.ts` hook + `keys.ts` entry + `ai-explanation-section.tsx` swap + 2 sibling test-file mock fixes; 38/38 pass, full suite 816/816

**Plan metadata:** (this commit, following SUMMARY.md)

## Files Created/Modified

- `backend/app/api/v1/ai/status.py` — `require_viewer`-gated route returning `{"configured": bool}`; docstring intentionally avoids `ConnectorConfig`/`api_key`/`credentials_secret_arn`/`decrypt_value` literal substrings so the task's own no-leak grep gate holds
- `backend/app/api/v1/ai/__init__.py` — registers `status.router` on `ai_router` alongside the existing sub-routers
- `backend/tests/test_ai_status.py` — 5 named tests: viewer-unconfigured-false, analyst-configured-true, admin-200 (both states), no-key-material-leak, tenant-scoped
- `frontend/src/lib/queries/use-ai-status.ts` — `useAiStatus()` TanStack hook mirroring `use-explain-cache.ts`'s single-GET shape (`staleTime: 60_000`, `retry: 1`); exports `AiStatusResult`
- `frontend/src/lib/queries/keys.ts` — adds `queryKeys.ai.status()`
- `frontend/src/components/ai/ai-explanation-section.tsx` — removed `useConnectorsList` import/usage and the `isError ? true : ...` pass-through; `keyConfigured = Boolean(statusQuery.data?.configured)`; `prereqsPending` now reads `statusQuery.isPending`
- `frontend/src/components/ai/ai-explanation-section.test.tsx` — swapped the `use-connectors-admin` mock for `use-ai-status`; re-pointed 3 existing no-key tests; added a 6-test "role x configured-state matrix" describe block proving all 5 `<behavior>` bullets plus the "old endpoint never called" claim
- `frontend/src/components/vulnerabilities/drill-panel.test.tsx` / `drill-panel-mobile.test.tsx` — updated their pre-existing `use-connectors-admin` stub-mock (needed only to avoid a `QueryClientProvider` requirement for the nested `AiExplanationSection`) to mock `use-ai-status` instead

## Decisions Made

- `GET /api/v1/ai/status` sits at `require_viewer` (the floor), matching the existing `explain_vuln.py` GET cache-check precedent — a boolean "is AI on" is not sensitive, and D-23 explicitly requires Viewer and Analyst to get an accurate signal.
- The status route reuses `get_tenant_anthropic_key` directly rather than adding a second/parallel "is configured" check, so the signal can never drift from the engine's own enforcement.
- The old `isError ? true : ...` optimistic pass-through and its multi-line explanatory comment were deleted outright (not left commented out or gated behind a flag) — the plan's whole point was to remove the guess, not add a second path alongside it.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `drill-panel.test.tsx` and `drill-panel-mobile.test.tsx` broke after the Task 2 signal swap**
- **Found during:** Task 2, full-suite regression run after the GREEN commit's targeted test pass
- **Issue:** Both files pre-existingly mocked `@/lib/queries/use-connectors-admin` solely so the `AiExplanationSection` nested inside `DrillContent` wouldn't need a `QueryClientProvider` wrapper. Once `ai-explanation-section.tsx` stopped importing that module, the mock became inert and the component's new `useAiStatus()` call hit the real TanStack hook with no provider in scope, throwing `No QueryClient set, use QueryClientProvider to set one` in 17 tests across both files.
- **Fix:** Replaced the `use-connectors-admin` mock with an equivalent `use-ai-status` mock (`{ data: { configured: false }, isPending: false, isError: false }`) in both files, updating the adjacent explanatory comments to reference the new module. This also incidentally corrects a pre-existing inaccuracy in those comments (they claimed a "no key configured, Viewer-default" state, but the old mock's `isError: true` actually fed the old `isError ? true : ...` logic into `keyConfigured = true`/"configured" — the new mock now genuinely matches the documented intent).
- **Files modified:** `frontend/src/components/vulnerabilities/drill-panel.test.tsx`, `frontend/src/components/vulnerabilities/drill-panel-mobile.test.tsx`
- **Verification:** Full frontend suite 816/816 passed (130 files) after the fix, versus 799/816 immediately beforehand.
- **Committed in:** `28982a2` (Task 2 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 bug, directly caused by this plan's own signal swap)
**Impact on plan:** Necessary to avoid a regression the plan's own change introduced; no scope creep — both files are test-only, in the same component's dependency tree, and the fix is a one-line mock swap per file.

## Issues Encountered

None beyond the deviation above. The plan's `<interfaces>` block was accurate enough that no additional exploration was needed for either task.

## User Setup Required

None — no external service configuration required. No migration, no new environment variable.

## Next Phase Readiness

- `24-VERIFICATION.md`'s truth #2 (the only code-proven gap) is now closed: all four roles (Owner/Admin/Analyst/Viewer) see the correct D-23 state in both configured and unconfigured tenants, proven by 6 new tests plus 3 re-pointed existing ones exercising the real `/api/v1/ai/status` signal instead of an unreachable-for-Analyst/Viewer mock state.
- The 4 explicitly-waived live-verification items from `24-VERIFICATION.md` (AI-03 nginx anti-buffering, the full live tracer, the D-25 live busy card, reduced-motion/contrast in a real browser) are untouched and remain open per the user's own "skip live verify, proceed on trust" decision at the 24-06 checkpoint — this plan's scope was explicitly the one code gap only.
- Plans 24-01..24-09 are untouched (confirmed via `git diff --stat` against the pre-plan commit — only the 7 files this plan's frontmatter listed plus the 2 documented regression-fix test files changed).
- Phase 24 is ready for re-verification (`/gsd-verify-work 24` or equivalent) to confirm the gap-closure holds before the milestone considers Phase 24 fully done.

---
*Phase: 24-ai-foundation-explain-this-vuln*
*Completed: 2026-07-29*

## Self-Check: PASSED

All claimed files verified present; all claimed commit hashes verified present in `git log`:
- `backend/app/api/v1/ai/status.py` — FOUND
- `backend/tests/test_ai_status.py` — FOUND
- `frontend/src/lib/queries/use-ai-status.ts` — FOUND
- `0a8855a`, `472e17c`, `692d68e`, `28982a2` — all FOUND in `git log --oneline --all`
