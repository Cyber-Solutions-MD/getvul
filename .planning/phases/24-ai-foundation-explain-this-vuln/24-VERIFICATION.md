---
phase: 24-ai-foundation-explain-this-vuln
verified: 2026-07-29T17:45:00Z
status: human_needed
score: 12/14 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 11/14
  gaps_closed:
    - "No-key state is role-gated: Analyst/Viewer get the 'ask an admin' nudge, no CTA, when no Anthropic key is configured (D-23, truth #2)"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "AI-03 nginx anti-buffering through the real proxy"
    expected: "curl -N -H 'Authorization: Bearer <analyst-token>' -X POST http://localhost/api/v1/ai/explain-vuln/<finding_id> prints frames progressively (first byte well before the ~2s+ full completion), not all-at-once after full latency"
    why_human: "Requires the live Docker Compose + nginx stack and a real/dev Anthropic key; explicitly WAIVED by the user at the 24-06 checkpoint ('skip live verify, proceed on trust'). The nginx config itself is re-confirmed structurally unchanged and correct this pass (location /api/v1/ai/ with proxy_buffering off in both HTTP and HTTPS server blocks, zero diff since original verification), and the SSE mechanics are proven by automated MockTransport-based tests, but the actual behavior through the real proxy has never been observed running."
  - test: "Live end-to-end tracer: admin configures key via wizard -> save -> analyst clicks Explain -> cached -> audit-log-pane row appears"
    expected: "The full flow completes visibly in a browser against the real Docker stack; an ai.explain.vuln row with model/tokens/cost/status appears in the settings audit-log pane"
    why_human: "Explicitly WAIVED by the user at the 24-06 checkpoint. Automated tests prove each stage (wizard submit, engine, cache, audit row construction) in isolation; the generic get_audit_logs() query has no exclusion for ai.* actions (structurally confirmed); the live UI rendering was never observed. Unaffected by 24-10's scope."
  - test: "D-25 persistent-429 'AI busy' amber card in the live UI"
    expected: "Forcing a real/simulated persistent rate-limit produces the amber 'AI busy — try again in a moment' card with a working 'Try again' button in a live browser"
    why_human: "Explicitly WAIVED. Automated tests prove the backend emits {type:error,kind:busy} and audits status=rate_limited, and the frontend component code renders the correct amber card for kind=busy (re-confirmed passing this pass) -- but the live-triggered visual/interactive confirmation was not performed."
  - test: "Live RBAC states (Analyst/Viewer/keyless) and reduced-motion/contrast checks in a real browser (dark + light)"
    expected: "Role-gated states render as coded; violet-on-soft citation tint is legible in both themes; prefers-reduced-motion disables the reveal animation"
    why_human: "Explicitly WAIVED. Per project convention, WCAG AA claims are treated as unproven without a live axe sweep (none run this phase) — token contrast was reasoned about via the design-system reference, not asserted. Reduced-motion branching is unit-tested (mocked matchMedia), not observed in a live browser. NOTE: the underlying role-gating logic this item also covers (Analyst/Viewer/keyless states) is now MORE thoroughly proven at the code/automated-test level than in the initial verification, since 24-10 added a real, non-optimistic signal and a 6-test matrix — only the LIVE browser observation remains open."
---

# Phase 24: AI Foundation + "Explain This Vuln" Verification Report

**Phase Goal:** A tenant admin can turn AI on with their own key, and an analyst gets a grounded, safely-guardrailed, streamed plain-English explanation of any vulnerability — proving the full integration risk (streaming, encrypted per-tenant config, guardrails) end-to-end at minimum blast radius before it's multiplied across four more capabilities.
**Verified:** 2026-07-29T17:45:00Z
**Status:** human_needed
**Re-verification:** Yes — after gap-closure plan 24-10 (previous run: gaps_found, 11/14)

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | AI-01: Tenant admin configures own Anthropic key + model prefs, encrypted via Fernet/ConnectorConfig; no shared/fallback key exists anywhere | ✓ VERIFIED (regression-confirmed) | `backend/app/ai/tenant_keys.py` is byte-unchanged (absent from the 24-10 diff — `git diff --stat 0a8855a~1..HEAD` shows only 9 files, none in `app/ai/`); full backend AI suite still 130/130 green (includes this file's tests) |
| 2 | No-key UI state is role-gated: Analyst/Viewer get the "ask an admin" nudge, no CTA; Admin/Owner get "Configure AI" CTA (D-23, Plan 05 must-have) | ✓ **VERIFIED — GAP CLOSED** | See "Gap Closure Verification" below. `keyConfigured = Boolean(statusQuery.data?.configured)` now derives from a real `require_viewer`-gated `GET /api/v1/ai/status` (backend confirmed at `backend/app/api/v1/ai/status.py`, tenant-scoped via `get_tenant_anthropic_key`). 5/5 backend tests + 38/38 frontend tests pass, including a new 6-test role×configured-state matrix exercising real production behavior for all 4 roles |
| 3 | AI-02: Untrusted scanner text (incl. adversarial) delivered to the model only as data, never instructions; every response schema-validated before reaching the UI | ✓ VERIFIED (regression-confirmed) | `backend/app/ai/prompt_builder.py` and `backend/app/ai/schemas.py` are byte-unchanged (absent from 24-10 diff); `test_ai_prompt_builder.py` + `test_ai_schemas.py` still pass as part of the 130/130 full AI-suite green run |
| 4 | AI-03: streaming mechanism — `fetch()`+`ReadableStream`, backend buffer-then-validate-then-replay, nginx `location /api/v1/ai/` with `proxy_buffering off` | ✓ VERIFIED (mechanism; regression-confirmed) | `frontend/src/lib/ai/use-explain-stream.ts` and `backend/app/ai/explain.py` byte-unchanged (absent from diff); re-checked `nginx/nginx.conf` directly this pass — `proxy_buffering off` still present in both the HTTP (line ~93) and HTTPS (line ~178) `location /api/v1/ai/` blocks, 0 lines changed since original verification (`git diff --stat` on `nginx/` = empty). Live proxy behavior remains unproven (see human_verification #1) |
| 5 | AI-04: "Explain this vuln" plain-English summary + business-risk framing with two-tier citation | ✓ VERIFIED (regression-confirmed) | `ai-explanation-citations.tsx` byte-unchanged (absent from diff); citation tests still pass as part of the 816/816 full frontend suite |
| 6 | AI-04 widening: same affordance + citations on host/remediation views via one shared, unmodified component (D-15) | ✓ VERIFIED (regression-confirmed) | `ai-explanation-section.tsx`'s `resourceType`/`resourceId`/`headingId` props and the "three-view parity" describe block (4 `it.each(['vuln','host','remediation'])` groups, 12 tests) still pass unchanged post-24-10; the ONLY change to this file was the `keyConfigured` derivation + `prereqsPending` source, confirmed by direct diff read (lines 96-116 area) — no per-view branching was touched |
| 7 | AI-05: AI output cache tenant-scoped, content-hash keyed; cross-tenant read is forced miss | ✓ VERIFIED (regression-confirmed) | `backend/app/ai/cache.py` byte-unchanged (absent from diff); `test_ai_cache_isolation.py` still passes in the 130/130 full AI-suite run |
| 8 | AI-06: every AI call audit-logged with explicit required `tenant_id`, symmetric interactive/scheduler shape | ✓ VERIFIED (regression-confirmed) | `backend/app/ai/audit.py` byte-unchanged (absent from diff); `test_scheduler_audit` and related tests still pass |
| 9 | D-16: per-remediation grounding shape (Option A — cross-asset CVE grouping) implemented as decided at 24-06 checkpoint | ✓ VERIFIED (regression-confirmed) | `backend/app/ai/grounding.py` byte-unchanged (absent from diff); `test_get_remediation_group_aggregates_across_assets_by_cve` still passes |
| 10 | Buffer-then-validate-then-replay: no raw provider token proxied; one corrective retry; typed error taxonomy, each audited distinctly | ✓ VERIFIED (regression-confirmed) | `backend/app/ai/explain.py` byte-unchanged (absent from diff); all named regression tests (`test_buffer_not_proxy_partial_deltas_never_leak`, rate-limit/grounded-false/malformed-retry tests) still pass |
| 11 | Host-view PII allowlist excludes owner PII; defense-in-depth (query + prompt-builder layers) | ✓ VERIFIED (regression-confirmed) | `grounding.py`/`prompt_builder.py` byte-unchanged (absent from diff); `test_host_pii_exclusion_directory_assigned_managed_building_serial` still passes |
| 12 | ai_feedback capture: idempotent per-user UPSERT, tenant-isolated, silent optimistic revert, capture-only | ✓ VERIFIED (regression-confirmed) | `ai-feedback-control.tsx`, `use-ai-feedback.ts`, `backend/app/ai/models.py` byte-unchanged (absent from diff); the `ai-feedback-control-stub` mock and its presence/absence assertions still pass in all 38 `ai-explanation-section.test.tsx` tests; migration `032_add_ai_feedback` still the sole `alembic heads` result |
| 13 | AI-03 manual truth: nginx does NOT buffer the incremental SSE stream through the real proxy | ? UNCERTAIN (human_verification — WAIVED) | Explicitly waived by the user at the 24-06 checkpoint. Unaffected by 24-10. See Human Verification Required |
| 14 | Live end-to-end tracer, D-25 live busy card, live RBAC states, reduced-motion/contrast in a real browser | ? UNCERTAIN (human_verification — WAIVED) | Explicitly waived by the user at the 24-06 checkpoint. Unaffected by 24-10 (if anything, the RBAC-states portion is now backed by stronger automated evidence — see truth #2). See Human Verification Required |

**Score:** 12/14 truths verified (0 FAILED, 2 UNCERTAIN/human-pending — both explicitly waived, not gaps)

### Gap Closure Verification (Truth #2 — Full 3-Level + Regression Check)

**Backend — `GET /api/v1/ai/status`**

| Check | Expected | Result |
|---|---|---|
| File exists | `backend/app/api/v1/ai/status.py` | EXISTS, 37 lines |
| `require_viewer`-gated | `Depends(require_viewer)` present | `grep -c "require_viewer"` = 3 (import + docstring + Depends) |
| Derives from `get_tenant_anthropic_key` | Same source of truth as engine | `grep -c "get_tenant_anthropic_key"` = 2 (import + call); `configured = await get_tenant_anthropic_key(db, user.tenant_id) is not None` read directly |
| No credential-material handling | Never touches `ConnectorConfig`/`api_key`/`credentials_secret_arn`/`decrypt_value` literally | `grep -c "credentials_secret_arn\|api_key\|decrypt_value\|ConnectorConfig"` = 0 |
| Registered in router | `ai_router.include_router(status.router)` | `grep -c "status.router" __init__.py` = 1; confirmed present, mounted alongside explain_vuln/host/remediation/feedback |
| Response shape | `dict[str, bool]`, exactly `{"configured": bool}` | Read directly: `return {"configured": configured}` |
| ruff | clean | `ruff check app/api/v1/ai/status.py app/api/v1/ai/__init__.py` → "All checks passed!" |
| mypy | 0 new errors | `mypy app/api/v1/ai/status.py \| grep "status.py"` → no output (0 errors attributed to this file; all 76 reported errors are in unrelated pre-existing transitive files, same pattern as original verification) |

**Backend tests — `backend/tests/test_ai_status.py`**

| Test | Result |
|---|---|
| `test_status_viewer_unconfigured_returns_false` | PASSED |
| `test_status_analyst_configured_returns_true` | PASSED |
| `test_status_admin_returns_200` (both unconfigured AND configured cells, explicit) | PASSED |
| `test_status_response_never_leaks_key_material` (keys == {"configured"}, seeded key string absent from resp.text) | PASSED |
| `test_status_is_tenant_scoped` (tenant_b sees false while tenant_a has a key) | PASSED |

Ran live: `cd backend && ENCRYPTION_KEY=<generated> JWT_SECRET_KEY=test-secret python -m pytest tests/test_ai_status.py -v` → **5 passed**, 0 failed.

**Frontend — `ai-explanation-section.tsx` signal swap**

| Check | Expected | Result |
|---|---|---|
| `useAiStatus` imported/used | ≥1 occurrence | `grep -c "useAiStatus"` = 2 |
| Old hook fully removed | `useConnectorsList`/`connectorsQuery` gone | `grep -c "useConnectorsList\|connectorsQuery"` = 0 |
| Optimistic pass-through removed | `isError ? true` gone | `grep -c "isError ? true"` = 0 |
| New derivation present | `Boolean(statusQuery.data?.configured)` | `grep -c "statusQuery.data?.configured"` = 1; read directly at line 108 |
| `prereqsPending` updated | uses `statusQuery.isPending` | Confirmed at line 110: `cacheQuery.isPending \|\| statusQuery.isPending` |
| Repo-wide sweep | no other file has the buggy `isError ? true` pattern, no stray `useConnectorsList` reference for AI purposes | `grep -rn "isError ? true" frontend/src/` = 0 matches anywhere; `useConnectorsList` usages elsewhere are all legitimate (the actual `/dashboard/connectors` admin page + its own hook/tests) |
| No new anti-patterns | no TODO/FIXME/hex/font-mono | 0 matches across all 4 modified 24-10 frontend/backend source files |

**Frontend hook — `use-ai-status.ts`**

| Check | Expected | Result |
|---|---|---|
| File exists | `frontend/src/lib/queries/use-ai-status.ts` | EXISTS, 22 lines |
| Calls the right endpoint | `/api/v1/ai/status` | `grep -c` = 1; read directly: `api<AiStatusResult>('/api/v1/ai/status', { signal })` |
| Mirrors sibling pattern | Same shape as `use-explain-cache.ts` | Confirmed: `staleTime: 60_000`, `retry: 1`, ordinary `api()` GET (not SSE) |
| Query key added | `queryKeys.ai.status()` | Confirmed in `keys.ts`: `status: () => ['ai', 'status'] as const` |
| No dedicated unit test file | Consistent with sibling `use-explain-cache.ts` (also untested directly, covered via component tests) | Confirmed by `find` — neither hook has its own `.test.ts`; both are exercised only through the component test suite. Not a gap — matches established codebase convention |

**Frontend tests — `ai-explanation-section.test.tsx` correction + expansion**

Ran live: `cd frontend && npx vitest run ai-explanation-section use-ai-status` → **38 passed (38)**, 1 test file.

New "real ai-status signal: role × configured-state matrix" describe block (6 tests, all pass):
1. unconfigured + Analyst → "ask an admin" nudge present, no trigger button — PASS
2. unconfigured + Viewer → same nudge, no CTA, never generic "No AI explanation generated yet." — PASS
3. unconfigured + Admin → "Configure AI" CTA → `/dashboard/connectors` — PASS
4. configured + Analyst → live "Explain this vuln" button, no false nudge — PASS
5. configured + Admin → live "Explain this vuln" button (asserted explicitly) — PASS
6. sanity: `mockUseAiStatus` was called — PASS

Locked copy strings (D-23) verified verbatim in the test file:
- `"AI isn't set up yet"` ✓
- `"Configure AI"` / href `/dashboard/connectors` ✓
- `"AI explanations aren't available yet — ask an admin to configure GetVul's AI connector."` ✓ (used identically for both Analyst and Viewer unconfigured tests)

The previously-flagged confirmation-biased test (`connectors: {isError:false, data:[]}` mock, unreachable in production for Analyst) is gone — no `use-connectors-admin` mock exists anywhere in this file (confirmed by full-file read); every "no-key" test now mocks `status: {data:{configured:false},...}` via `mockUseAiStatus`, which is what the real production code actually consumes.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/api/v1/ai/status.py` | `router`, `get_ai_status()`, `require_viewer`-gated, `{configured: bool}` | ✓ VERIFIED | 37 lines; exists, substantive, wired (registered + called by 5 passing tests) |
| `backend/tests/test_ai_status.py` | 5 named RBAC/leak/tenant-isolation tests | ✓ VERIFIED | 95 lines; all 5 tests pass |
| `frontend/src/lib/queries/use-ai-status.ts` | `useAiStatus()` TanStack hook | ✓ VERIFIED | 22 lines; exists, substantive, wired (imported + called in ai-explanation-section.tsx, exercised via 38 passing tests) |
| `frontend/src/components/ai/ai-explanation-section.tsx` | `keyConfigured` derived from `statusQuery.data?.configured` | ✓ VERIFIED | Old optimistic pass-through fully removed; all role branches preserved verbatim; grep gates all pass |
| `frontend/src/components/ai/ai-explanation-section.test.tsx` | Corrected + expanded 4-role × 2-state matrix | ✓ VERIFIED | 447 lines; 38/38 tests pass, incl. 6 new matrix tests |
| All 14 previously-verified artifacts (Plans 01-09) | — | ✓ VERIFIED (regression) | Confirmed byte-unchanged via `git diff --stat 0a8855a~1..HEAD` (only 9 files touched, all from 24-10's own scope) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `frontend AiExplanationSection` | `frontend use-ai-status.ts useAiStatus()` | `const statusQuery = useAiStatus();` | ✓ WIRED | Confirmed at line 104 of the component |
| `frontend use-ai-status.ts` | backend `GET /api/v1/ai/status` | `api<AiStatusResult>('/api/v1/ai/status', {signal})` | ✓ WIRED | Confirmed at line 18 of the hook |
| `backend status.py` | `app.ai.tenant_keys.get_tenant_anthropic_key` | `await get_tenant_anthropic_key(db, user.tenant_id) is not None` | ✓ WIRED | Confirmed at line 36 of the route; same source of truth as the paid-call engine — no drift risk |
| `backend ai/__init__.py` | `status.router` | `ai_router.include_router(status.router)` | ✓ WIRED | Confirmed present, 1 occurrence |
| ~~`frontend AiExplanationSection`~~ | ~~`use-connectors-admin.ts useConnectorsList()`~~ | ~~`keyConfigured` derivation~~ | **REMOVED (correctly)** | This was the prior gap's root-cause link (⚠️ WIRED BUT IMPRECISE in the original verification) — confirmed fully removed, 0 occurrences repo-wide in this component |
| `frontend .../connectors/page.tsx` | backend `CONNECTOR_TYPES['ANTHROPIC']` | `useConnectorTypes()` → wizard | ✓ WIRED (unaffected) | Unchanged since original verification |
| `explain_vuln.py`/`explain_host.py`/`explain_remediation.py` | `_run_explain_stream()` | direct call | ✓ WIRED (unaffected) | Files absent from 24-10 diff |
| `assets/[id]/page.tsx`, `remediation-timeline.tsx` | `AiExplanationSection` | component mount | ✓ WIRED (unaffected) | Files absent from 24-10 diff |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `ai-explanation-section.tsx` | `keyConfigured` | `useAiStatus()` → real `GET /api/v1/ai/status` → `get_tenant_anthropic_key(db, user.tenant_id)` → real tenant-scoped Postgres/ConnectorConfig lookup | **Yes — now real for ALL roles** (previously: real for Admin only, synthetic `true` fallback for Analyst/Viewer) | ✓ **FLOWING (fixed from ⚠️ STATIC)** |
| `ai-explanation-section.tsx` | `state.data` (validated explanation) | `useExplainStream` → backend SSE → `_run_explain_stream()` (unchanged) | Yes | ✓ FLOWING (unaffected) |
| `remediation-timeline.tsx` | `t.cve_id` | `list_tickets()` real aggregate query (unchanged) | Yes | ✓ FLOWING (unaffected) |

This closes the ONE Level-4 data-flow gap the original verification found: the `keyConfigured` signal is no longer a synthetic optimistic guess for non-admin roles — it is now a real, tenant-scoped boolean from a dedicated, correctly-RBAC-gated endpoint.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| New backend status tests pass | `pytest tests/test_ai_status.py -v` | 5 passed | ✓ PASS |
| Full backend AI suite (regression) | `pytest tests/test_ai_*.py -q` | 130 passed (125 prior + 5 new, exact match) | ✓ PASS |
| Backend AI suite incl. connector tester (regression, matches prior verification's exact command) | `pytest tests/test_ai_*.py tests/test_connectors/test_ai_tester.py -q` | 130 passed | ✓ PASS |
| Full backend suite (regression) | `pytest tests/ -q` | 480 passed, 1 failed — same pre-existing, unrelated `test_connector_health.py::test_scheduler_path_error_message_and_log_are_sanitized` flake documented since Plan 24-04 (`deferred-items.md`); re-ran in isolation this pass: 9/9 passed, confirming full-suite-only flake, not a regression | ✓ PASS |
| `alembic upgrade head` / `alembic heads` | single clean head | `032_add_ai_feedback (head)` | ✓ PASS |
| Frontend AI matrix tests pass | `npx vitest run ai-explanation-section use-ai-status` | 38 passed (38), 1 file | ✓ PASS |
| Full frontend suite (regression) | `npx vitest run` | 816 passed (816), 130 files (up from 810/130 pre-24-10 — exactly +6 new tests, no losses) | ✓ PASS |
| `tsc --noEmit` | clean | No output | ✓ PASS |
| `ruff check` on new files | clean | "All checks passed!" | ✓ PASS |
| `mypy` zero new errors on `status.py` | 0 matches when filtered to the file itself | 0 matches (76 pre-existing errors all in unrelated transitive files) | ✓ PASS |
| Scope-boundary check | `git diff --stat 0a8855a~1..HEAD` | Exactly 9 files changed (7 planned + 2 documented regression fixes); zero Plan 24-01..24-09 production files touched | ✓ PASS |
| Commit integrity | `git log --oneline --all \| grep <hashes>` | All 4 claimed commits (0a8855a, 472e17c, 692d68e, 28982a2) exist with content matching SUMMARY claims exactly (verified via `git show --stat` on each) | ✓ PASS |
| nginx `location /api/v1/ai/` progressive delivery through real proxy | `curl -N` through live Docker/nginx | NOT RUN | ? SKIP — explicitly waived by user; see human_verification |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|----------------|--------------|--------|----------|
| AI-01 | 24-01, 24-03, 24-05, 24-06, **24-10** | Tenant admin configures own Anthropic key, encrypted, no shared/fallback key; features disabled until configured, gracefully, **for every role** | ✓ **FULLY SATISFIED (gap closed)** | The narrower UI-precision deviation flagged in the original verification (Gap #2) is now closed — the "graceful configure-AI state" is correctly role-gated for Analyst/Viewer as well as Admin/Owner, proven by 5 backend + 38 frontend tests |
| AI-02 | 24-02, 24-04, 24-08 | Untrusted scanner text as data only; schema-validated output | ✓ SATISFIED (unaffected) | Unchanged since original verification |
| AI-03 | 24-01, 24-04, 24-05 | Token-by-token streaming via fetch+ReadableStream; nginx no-buffering | ✓ SATISFIED (mechanism) / ? NEEDS HUMAN (live proxy, explicitly waived) | Unchanged since original verification |
| AI-04 | 24-05, 24-07, 24-08, 24-09 | "Explain this vuln/host/remediation" + two-tier citation | ✓ SATISFIED (unaffected) | Unchanged since original verification |
| AI-05 | 24-03, 24-04, 24-08 | Tenant-scoped, content-hash-keyed cache; no cross-tenant serving | ✓ SATISFIED (unaffected) | Unchanged since original verification |
| AI-06 | 24-02, 24-03, 24-04 | Every AI call audit-logged incl. scheduler-originated, explicit tenant_id | ✓ SATISFIED (unaffected) | Unchanged since original verification |

No orphaned requirements. Plan 24-10 declared `requirements: [AI-01]` in frontmatter, correctly scoping its contribution as closing the one open AI-01 precision gap rather than introducing a new requirement ID.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `frontend/src/components/ai/ai-explanation-section.test.tsx` | 7 | Docblock comment still lists `useConnectorsList` as one of the hooks driving the "8-state behavior matrix", describing the pre-24-10 architecture | ℹ️ INFO | Cosmetic only — the actual mocks/code in this file are fully corrected and verified (confirmed via full-file read + 0 functional `useConnectorsList` references); a stale historical comment, not a functional gap |
| `frontend/src/components/ai/ai-explanation-section.test.tsx` | 374-378 | The "forwards nothing to the old admin-gated connectors endpoint" test only positively asserts `mockUseAiStatus` was called, rather than directly asserting the old hook was NOT called | ℹ️ INFO | Low risk: the claim is still enforced indirectly — this test file has zero mock registered for the old hook, so if the component still called it for real, the render would throw (`No QueryClient set`) and the test would fail, not pass silently. Independently confirmed via repo-wide grep (0 references) |
| `frontend/src/components/ai/ai-explanation-section.tsx` | 104-110 | `statusQuery.isError` (the new status endpoint itself failing) has no dedicated test case | ℹ️ INFO | By code inspection this fails closed, not open: `Boolean(undefined?.configured)` evaluates to `false`, so an errored status check shows the safe "not configured" nudge/CTA for every role — never a false-positive live trigger. Same class of finding as the pre-existing `use-explain-stream.ts` untested outer-catch path noted in the original verification |
| Test matrix (new) | — | No test explicitly exercises `role: 'OWNER'` in the new 6-test matrix (only `'ADMIN'` is used for the admin-analogous cases) | ℹ️ INFO | Consistent with the pre-existing convention across this entire test file (e.g., the earlier `budget_exceeded` Admin-only test also never separately tests OWNER) — the code's shared `isAdminOrOwner = role==='OWNER'\|\|role==='ADMIN'` boolean makes the two roles structurally identical; not a new gap introduced by 24-10 |
| `backend/app/api/v1/ai/spike.py` + `__init__.py` | whole file | Throwaway Wave-0 spike route still registered/live | ℹ️ INFO | Unaffected by 24-10 (absent from diff); same disposition as original verification — still `require_analyst`-gated, dead but harmless |
| `.planning/phases/24-.../24-VALIDATION.md` | frontmatter | `status: draft`, `nyquist_compliant: false` | ℹ️ INFO | Unaffected by 24-10; matches known project pattern of stale pre-exec artifacts (per user memory) |
| `.planning/ROADMAP.md` line 291 | — | **RESOLVED since original verification** — previously flagged as stale ("Plans: 7/9 plans executed"); now reads "**Plans**: 10 executed (9 original + 1 gap-closure, 24-10)", accurately reflecting the current state | — | No longer an anti-pattern; fixed as a side effect of the 24-10 documentation commit (`d5dadba`) |

No 🛑 Blocker-severity and no ⚠️ Warning-severity anti-patterns found in any file touched by 24-10, or in any file this pass re-confirmed as unchanged.

### Human Verification Required

### 1. AI-03 nginx anti-buffering through the real proxy

**Test:** `docker compose up -d`, then `curl -N -H "Authorization: Bearer <analyst-token>" -X POST http://localhost/api/v1/ai/explain-vuln/<finding_id>`
**Expected:** Frames print progressively as they arrive (first byte well before the full ~2s+ completion), never all four/five frames dumped at once after full latency
**Why human:** Requires the live Docker/nginx stack + a real Anthropic key; explicitly waived by the user at the 24-06 checkpoint. Re-confirmed this pass: `nginx/nginx.conf` has zero diff since original verification, `proxy_buffering off` still present in both server blocks.

### 2. Live end-to-end tracer (wizard → save → explain → cache → audit-row)

**Test:** As Admin, configure a real Anthropic key via `/dashboard/connectors`; as Analyst, open a vuln drill panel and click "Explain this vuln"; re-open the same finding to confirm a cache hit; open the audit-log pane and confirm an `ai.explain.vuln` row appears
**Expected:** Each stage completes visibly and consistently with the automated-test-proven backend behavior
**Why human:** Explicitly waived at the 24-06 checkpoint. Unaffected by 24-10's scope (which only touched the no-key signal, not the configured-tenant explain flow).

### 3. D-25 persistent-429 "AI busy" card

**Test:** Force a persistent Anthropic rate-limit (or point the client at a 429-returning mock) and click Explain on an uncached finding
**Expected:** The amber "AI busy — try again in a moment" card with a working "Try again" button appears — never a generic error, blank panel, or partial text
**Why human:** Explicitly waived at the 24-06 checkpoint. Re-confirmed this pass: the `kind==='busy'`/`kind==='unknown'` render branch is untouched by 24-10 and its unit test still passes.

### 4. Reduced-motion + citation contrast in a real browser (dark + light)

**Test:** Toggle OS-level `prefers-reduced-motion`; inspect `violet-on-soft` citation tint contrast in both themes
**Expected:** Reduced-motion renders the result instantly (no reveal animation); citation tint is legible (AA contrast) in both themes
**Why human:** Explicitly waived. Per project convention, WCAG AA claims are treated as unproven without a live axe sweep. Reduced-motion branching is unit-tested via mocked `matchMedia`, not observed live. The role-gating portion of what this item originally also covered is now backed by materially stronger automated evidence (truth #2's 6-test matrix) than at the time of original verification — only the visual/live-browser observation remains open.

### Gaps Summary

**The one code-proven gap from the original verification is closed.** Gap-closure plan 24-10 added a `require_viewer`-gated `GET /api/v1/ai/status` endpoint (backend) and a `useAiStatus()` hook (frontend), replacing the `connectorsQuery.isError ? true : ...` optimistic pass-through that caused Analyst/Viewer roles to see a live "Explain this vuln" trigger in a genuinely unconfigured tenant. This was verified independently at all four levels: the artifact exists (37-line route, 22-line hook), is substantive (correct RBAC gate, correct tenant-scoped source of truth, zero credential-material handling), is wired (registered in `ai_router`, imported and called by the component, consumed by `keyConfigured`), and its data flows for real (a genuine per-tenant Postgres-backed boolean, not a synthetic fallback) — for all four roles, in both tenant states, proven by 5 new backend tests and 6 new frontend matrix tests, none of which existed before this plan.

Regression risk was explicitly checked and found clean: `git diff --stat` against the pre-24-10 commit shows exactly the 9 files the plan's own scope claimed (7 planned + 2 documented sibling-test fixes for `drill-panel.test.tsx`/`drill-panel-mobile.test.tsx`, whose pre-existing `use-connectors-admin` stub mocks became inert once the production import changed and needed an equivalent `use-ai-status` stub — a necessary, narrowly-scoped, test-only fix, not scope creep). No file backing any of truths 1, 3-12 was touched; the full backend suite (480/481, the 1 failure being the same pre-existing unrelated flake documented since Plan 24-04, re-confirmed 9/9 in isolation) and full frontend suite (816/816, exactly +6 tests over the pre-24-10 810/810 baseline, zero losses) both stay fully green. nginx config, alembic migration head, and the admin connectors RBAC gate (still `require_admin`, confirming the original root-cause diagnosis remains valid) were all independently re-checked and found unchanged.

A disconfirmation pass (Confirmation Bias Counter) surfaced four genuinely minor, INFO-level observations — a stale docblock comment, one indirectly-enforced test assertion, one untested-but-provably-fail-closed error path, and no dedicated `role:'OWNER'` test cell (consistent with this file's pre-existing convention) — none of which rise to a functional gap or regression.

**The only items still open are the four explicitly-waived live/manual verification checks** from the original verification (AI-03 nginx anti-buffering through the real proxy, the full live tracer, the D-25 live busy card, and reduced-motion/contrast in a real browser). The user explicitly chose "skip live verify, proceed on trust" at the 24-06 checkpoint for these; they are reported here as `human_verification` per that explicit instruction, not as failures or gaps, and 24-10 did not touch any of the code paths they would exercise. Status is `human_needed` (not `passed`) strictly because these four items remain open observations pending a human — every automated, code-level, and regression check that CAN be verified in the codebase now passes cleanly, including the one true gap this re-verification pass was scoped to close.

---

_Verified: 2026-07-29T17:45:00Z_
_Verifier: Claude (gsd-verifier) — re-verification after gap-closure plan 24-10_
