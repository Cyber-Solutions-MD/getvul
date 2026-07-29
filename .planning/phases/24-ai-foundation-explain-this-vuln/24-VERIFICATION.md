---
phase: 24-ai-foundation-explain-this-vuln
verified: 2026-07-29T13:17:16Z
status: gaps_found
score: 11/14 must-haves verified
overrides_applied: 0
gaps:
  - truth: "No-key state is role-gated: Analyst/Viewer get the 'ask an admin' nudge, no CTA, when no AAnthropic key is configured (D-23, Plan 05 must-have)"
    status: failed
    reason: "GET /api/v1/connectors (used by useConnectorsList() to derive the keyConfigured signal) is require_admin-gated on the backend. frontend/src/lib/api.ts's api() helper throws ApiError on any non-ok response, so for Analyst/Viewer this call always 403s -> TanStack Query's isError becomes true after the configured retry. ai-explanation-section.tsx's derivation `connectorsQuery.isError ? true : ...` treats that 403 as an optimistic 'assume configured' pass-through. Net effect for a genuinely unconfigured tenant: an Analyst sees the live 'Explain this vuln' button (not the intended role-gated 'ask an admin' text) and, on click, the backend's real no_key short-circuit returns a {type:'no_key'} SSE event that the frontend maps to kind:'unknown', rendering the SAME amber 'AI busy — try again in a moment' card used for real rate-limiting -- a permanently-wrong, retry-inviting message for what is actually a permanent 'not configured' state. A Viewer lands on a less harmful but still imprecise generic 'No AI explanation generated yet.' rather than the specified 'ask an admin' copy. No security/BYOK boundary is crossed (no dispatch occurs; the backend's own no_key gate is authoritative) -- this is a UI-precision gap, not a safety gap."
    artifacts:
      - path: "frontend/src/components/ai/ai-explanation-section.tsx"
        issue: "keyConfigured derivation (lines ~112-114) treats connectorsQuery.isError as 'assume configured' -- the only way to reach an accurate signal (GET /api/v1/connectors) is admin-gated, so Analyst/Viewer can never get a real signal from it"
      - path: "frontend/src/components/ai/ai-explanation-section.test.tsx"
        issue: "The 'no-key + role=Analyst renders the ask-an-admin nudge' test mocks `connectors: { isError: false, data: [] }` -- a scenario that cannot occur in production for Analyst, since GET /api/v1/connectors is require_admin-gated and would always 403 (isError: true) for that role. The test passes but does not exercise real production behavior for the role it claims to cover (Confirmation Bias Counter finding)."
    missing:
      - "A lightweight, non-admin-safe 'is AI configured' signal (e.g. a require_viewer-gated GET /api/v1/ai/status or similar) that Analyst/Viewer can call to get a real, non-error-coded key-configured boolean, replacing the isError-based optimistic guess"
      - "OR: an explicit product decision to accept the current optimistic-pass-through behavior as intentional trade-off (already self-documented by the Plan 05 executor with this exact remediation suggestion in 24-05-SUMMARY.md 'Issues Encountered'), recorded as a verification override"
deferred: []
human_verification:
  - test: "AI-03 nginx anti-buffering through the real proxy"
    expected: "curl -N -H 'Authorization: Bearer <analyst-token>' -X POST http://localhost/api/v1/ai/explain-vuln/<finding_id> prints frames progressively (first byte well before the ~2s+ full completion), not all-at-once after full latency"
    why_human: "Requires the live Docker Compose + nginx stack and a real/dev Anthropic key; explicitly WAIVED by the user at the 24-06 checkpoint ('skip live verify, proceed on trust'). The nginx config itself is structurally verified (location /api/v1/ai/ with proxy_buffering off in both HTTP and HTTPS server blocks) and the SSE mechanics are proven by automated MockTransport-based tests, but the actual behavior through the real proxy has never been observed running."
  - test: "Live end-to-end tracer: admin configures key via wizard -> save -> analyst clicks Explain -> cached -> audit-log-pane row appears"
    expected: "The full flow completes visibly in a browser against the real Docker stack; an ai.explain.vuln row with model/tokens/cost/status appears in the settings audit-log pane"
    why_human: "Explicitly WAIVED by the user at the 24-06 checkpoint. Automated tests prove each stage (wizard submit, engine, cache, audit row construction) in isolation; the generic get_audit_logs() query has no exclusion for ai.* actions (structurally confirmed), but the live UI rendering was never observed."
  - test: "D-25 persistent-429 'AI busy' amber card in the live UI"
    expected: "Forcing a real/simulated persistent rate-limit produces the amber 'AI busy — try again in a moment' card with a working 'Try again' button in a live browser"
    why_human: "Explicitly WAIVED. Automated tests prove the backend emits {type:error,kind:busy} and audits status=rate_limited, and the frontend component code renders the correct amber card for kind=busy -- but the live-triggered visual/interactive confirmation was not performed."
  - test: "Live RBAC states (Analyst/Viewer/keyless) and reduced-motion/contrast checks in a real browser (dark + light)"
    expected: "Role-gated states render as coded; violet-on-soft citation tint is legible in both themes; prefers-reduced-motion disables the reveal animation"
    why_human: "Explicitly WAIVED. Per project convention, WCAG AA claims are treated as unproven without a live axe sweep (no axe e2e run this phase) -- token contrast was reasoned about via the design-system reference, not asserted. Reduced-motion branching is unit-tested (mocked matchMedia), not observed in a live browser."
---

# Phase 24: AI Foundation + "Explain This Vuln" Verification Report

**Phase Goal:** A tenant admin can turn AI on with their own key, and an analyst gets a grounded, safely-guardrailed, streamed plain-English explanation of any vulnerability — proving the full integration risk (streaming, encrypted per-tenant config, guardrails) end-to-end at minimum blast radius before it's multiplied across four more capabilities.
**Verified:** 2026-07-29T13:17:16Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | AI-01: Tenant admin configures own Anthropic key + model prefs, encrypted via Fernet/ConnectorConfig; no shared/fallback key exists anywhere | ✓ VERIFIED | `backend/app/ai/tenant_keys.py::get_tenant_anthropic_key()` decrypts fresh per-call, returns `None` (never raises/falls back) when unconfigured; `grep -rn "ANTHROPIC_API_KEY\|GETVUL_ANTHROPIC" backend/app/` returns zero hits (no shared-key code path exists anywhere); `CONNECTOR_TYPES["ANTHROPIC"]` registered with `uq_connector_tenant_type` UNIQUE(tenant_id, connector_type) enforcing one row/tenant |
| 2 | No-key UI state is role-gated: Admin/Owner get "Configure AI" CTA; Analyst/Viewer get "ask an admin" nudge, no CTA (D-23, Plan 05 must-have) | ✗ FAILED | See Gaps below — `GET /api/v1/connectors` is `require_admin`-gated (confirmed: all 8 routes in `connectors/router.py` use `require_admin`, none `require_analyst`/`require_viewer`); `api()` throws on non-2xx (confirmed in `frontend/src/lib/api.ts:127-131`), so Analyst/Viewer's `connectorsQuery` always errors; `ai-explanation-section.tsx`'s `keyConfigured = connectorsQuery.isError ? true : ...` treats this as "assume configured," bypassing the intended role-gated copy |
| 3 | AI-02: Untrusted scanner text (incl. adversarial) delivered to the model only as data, never instructions; every response schema-validated before reaching the UI | ✓ VERIFIED | `test_injection_isolation` and `test_delimiter_breakout_is_inert` (backend/tests/test_ai_prompt_builder.py) pass — adversarial/delimiter-breakout strings proven present ONLY in the user `<scanner_data>` block, absent from `system`, verbatim; `ExplainVulnResponse.model_validate_json()` + `recheck_business_rules()` two-stage gate proven to reject malformed/incomplete/over-budget output (`test_ai_schemas.py`, 14 tests, all pass) |
| 4 | AI-03: streaming mechanism — `fetch()`+`ReadableStream` (never `api()`/`EventSource`); backend buffer-then-validate-then-replay; nginx `location /api/v1/ai/` with `proxy_buffering off` | ✓ VERIFIED (mechanism) | `frontend/src/lib/ai/use-explain-stream.ts` uses `res.body.getReader()` + `\n\n`-boundary buffering, zero `api()` import (grep-confirmed); `backend/app/ai/explain.py::_run_explain_stream()` consumes the Anthropic stream ENTIRELY via `await stream.get_final_message()` (zero `StreamingResponse(client...)` passthrough, grep-confirmed); `nginx/nginx.conf` has `location /api/v1/ai/` with `proxy_buffering off` in BOTH HTTP (line 85) and HTTPS (line 170) server blocks. See truth #13/human_verification for the LIVE proxy behavior (unproven, waived) |
| 5 | AI-04: "Explain this vuln" plain-English summary + business-risk framing with two-tier citation (scanner_verbatim tint vs. ai_interpreted superscript) | ✓ VERIFIED | `ai-explanation-citations.tsx` renders `scanner_verbatim` in a `bg-violet-soft`/`text-[var(--color-violet-on-soft)]` tinted span (`tabIndex=0`, `cursor-help`, Tooltip "Scanner-verbatim · from {source_field}") and `ai_interpreted` as prose + 10px uppercase "AI" superscript (Tooltip "AI-interpreted"); one flowing paragraph (no split blocks); 4/4 citation unit tests pass |
| 6 | AI-04 widening: the same "Explain this" affordance + citations ship on host and remediation drill views via one shared, unmodified component (D-15) | ✓ VERIFIED | `frontend/src/components/ai/ai-explanation-section.tsx` takes `resourceType`/`resourceId`/`headingId`; mounted with `resourceType="host"` on `assets/[id]/page.tsx` and `resourceType="remediation"` per-row on `remediation-timeline.tsx`; three-view parity test suite (`it.each(['vuln','host','remediation'])`) passes 34/34 in `ai-explanation-section.test.tsx` |
| 7 | AI-05: AI output cache is tenant-scoped, content-hash keyed; a cross-tenant read is a forced miss | ✓ VERIFIED | `backend/app/ai/cache.py::build_cache_key()` interpolates `tenant_id` as the FIRST segment; `test_cross_tenant_cache_read_is_a_forced_miss` (in `test_ai_cache_isolation.py`) proves a tenant_b read of tenant_a's identical (resource,hash,model,version) tuple is a hard `None` against a REAL flushed Redis (not mocked) — re-ran, passes |
| 8 | AI-06: every AI call attempt is audit-logged (model/tokens/cost/status) with an explicit, required `tenant_id` (never the nil-tenant fallback), symmetric interactive/scheduler shape | ✓ VERIFIED | `backend/app/ai/audit.py::audit_log_ai_call()` has `tenant_id` as a required keyword-only param (no default); never calls the shared `audit()` helper (grep-confirmed); `test_scheduler_audit` proves `row.tenant_id == tenant_a.id` (not `uuid.UUID(int=0)`) for `user_email="system:scheduler"`; `_run_explain_stream()` calls `_audit()` on every code path (ok/validation_failed/grounded_retry/budget_exceeded/rate_limited/injection_flagged) — no silent unlogged attempt |
| 9 | D-16: per-remediation grounding shape decided at the 24-06 checkpoint (Option A — cross-asset CVE grouping) is what Plan 08 actually implemented | ✓ VERIFIED | `backend/app/ai/grounding.py::get_remediation_group()` joins Asset+Vulnerability grouped by `cve_id`, returns `{cve, fix, affected_assets[], priority}`; `test_get_remediation_group_aggregates_across_assets_by_cve` seeds 2 assets sharing one CVE and asserts `len(affected_assets) == 2` — genuine cross-asset aggregation, not a per-ticket reuse |
| 10 | Buffer-then-validate-then-replay: no raw provider token ever proxied; exactly one corrective retry on validation failure/grounded=false; typed error taxonomy for rate-limit/budget/grounded_false/unknown, each audited distinctly | ✓ VERIFIED | `explain.py` — `grep -c "StreamingResponse(client" == 0`; `test_buffer_not_proxy_partial_deltas_never_leak` (real-SDK MockTransport wire-format test) proves raw `content_block_delta` frames never appear outbound; `test_persistent_rate_limit_error_yields_busy_and_audits_rate_limited`, `test_grounded_false_triggers_one_corrective_retry_then_succeeds`, `test_two_malformed_responses_terminal_error_two_audit_rows` all pass with distinct audited statuses |
| 11 | Host-view PII allowlist excludes owner PII (directory_user/assigned_user/managed_by/building/serial_number); defense-in-depth (query layer + prompt-builder layer) | ✓ VERIFIED | `get_asset_posture()` SELECTs only 7 named `Asset` columns (no PII columns fetched at all); `build_explain_host_prompt()`'s `AllowlistedHostPosture` has `extra="forbid"` with only 9 named fields; `test_host_pii_exclusion_directory_assigned_managed_building_serial` asserts none of the 5 forbidden field names/values appear in the built prompt — passes |
| 12 | ai_feedback capture: idempotent per-user UPSERT, tenant-isolated, silent optimistic revert (no toast), capture-only | ✓ VERIFIED | `ON CONFLICT (resource_type,resource_id,user_id) DO UPDATE` proven by `test_post_feedback_edit_upserts_single_row` (one row after 2 submissions); cross-tenant isolation test passes against real Postgres; `grep -c "toast" use-ai-feedback.ts == 0`; silent-revert test proves no `role="alert"` element renders on mutation failure |
| 13 | AI-03 manual truth: nginx does NOT buffer the incremental SSE stream through the real proxy (`curl -N` progressive-frame assertion) | ? UNCERTAIN (human_verification) | **Explicitly WAIVED by the user at the 24-06 checkpoint** ("skip live verify, proceed on trust"). Config is structurally correct (verified above); live behavior never observed. See Human Verification Required |
| 14 | Live end-to-end tracer (wizard→save→explain→cache→audit-row), D-25 live busy card, live RBAC states, reduced-motion/contrast in a real browser | ? UNCERTAIN (human_verification) | **Explicitly WAIVED by the user at the 24-06 checkpoint.** Every stage is proven in isolation by automated tests (see truths 1-12); the composed live flow was never run. See Human Verification Required |

**Score:** 11/14 truths verified (1 FAILED, 2 UNCERTAIN/human-pending)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/ai/schemas.py` | `CitationSource`, `Citation`, `ExplainResponseBase`, `ExplainVulnResponse`, `ExplainHostResponse`, `ExplainRemediationResponse`, `recheck_business_rules()` | ✓ VERIFIED | 141 lines, all symbols present, wired into `explain.py`/`prompt_builder.py`/all 3 route files |
| `backend/app/ai/prompt_builder.py` | `SYSTEM_PROMPT`, `VULN_ALLOWLIST`, `build_explain_vuln_prompt()`, `prompt_version()`, `HOST_ALLOWLIST`, `REMEDIATION_ALLOWLIST`, host/remediation builders | ✓ VERIFIED | 778 lines, all symbols present and tested (73 tests across `test_ai_prompt_builder.py` + `test_ai_prompt_builder_host.py`) |
| `backend/app/ai/audit.py` | `audit_log_ai_call()` | ✓ VERIFIED | 74 lines, direct `AuditLog` construction, required keyword-only `tenant_id` |
| `backend/app/ai/tenant_keys.py` | `get_tenant_anthropic_key()` | ✓ VERIFIED | 63 lines, decrypt-fresh, inert `None`, no fallback |
| `backend/app/ai/cache.py` | cache key builder, get/set+TTL, `record_hash`, inflight guard | ✓ VERIFIED | 118 lines, tenant-namespaced, real-Redis-tested |
| `backend/app/ai/budget.py` | `check_tenant_budget()`, `notify_admins_budget_exceeded()` | ✓ VERIFIED | 108 lines, fail-closed, per-admin notification |
| `backend/app/ai/explain.py` | `_run_explain_stream()` shared engine | ✓ VERIFIED | 484 lines, reused unchanged by host/remediation (byte-identical since Plan 04, confirmed via `git diff 8fd92db..HEAD`) |
| `backend/app/ai/grounding.py` | `get_asset_posture()`, `get_remediation_group()` | ✓ VERIFIED | 194 lines, both tenant-scoped, PII-excluding |
| `backend/app/ai/models.py` | `AiFeedback` | ✓ VERIFIED | 48 lines, matches migration exactly |
| `backend/app/api/v1/ai/explain_vuln.py`, `explain_host.py`, `explain_remediation.py`, `feedback.py` | RBAC-gated POST(SSE)+GET(cache-check) routes | ✓ VERIFIED | All 4 exist, all registered in `ai_router`, all RBAC-matrix-tested |
| `backend/alembic/versions/031_rename_audit_tenant_idx.py`, `032_add_ai_feedback.py` | migrations | ✓ VERIFIED | `alembic heads` == `032_add_ai_feedback`; both apply cleanly from a fresh `alembic upgrade head` run during this verification |
| `frontend/src/lib/ai/use-explain-stream.ts` | SSE hook | ✓ VERIFIED | 138 lines, `getReader`-based, no `api()` import, resourceType-parameterized |
| `frontend/src/components/ai/ai-explanation-section.tsx`, `ai-explanation-citations.tsx` | shared, view-agnostic section + citations | ✓ VERIFIED | Moved from `components/vulnerabilities/` (old paths confirmed absent); 230 + 151 lines |
| `frontend/src/components/vulnerabilities/ai-feedback-control.tsx` | thumbs+note control | ✓ VERIFIED | 106 lines, wired beneath both grounded-render branches |
| `frontend/src/components/ui/tooltip.tsx` | shadcn tooltip, sunset-token-corrected | ✓ VERIFIED | 36 lines, no undefined CSS vars |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `frontend/.../connectors/page.tsx` | backend `CONNECTOR_TYPES['ANTHROPIC']` | `useConnectorTypes()` → wizard | ✓ WIRED | `ai_assistant` category present in both backend `router.py` and frontend `page.tsx`/`microcopy.ts`; wizard test suite (add-connector-wizard) passes 6/6 ANTHROPIC-specific assertions |
| `backend/app/connectors/tester.py TESTERS` | `test_anthropic` | dispatch table | ✓ WIRED | `TESTERS["ANTHROPIC"] = test_anthropic`; `test_connector()` dispatcher unchanged (generic) |
| `explain_vuln.py`/`explain_host.py`/`explain_remediation.py` | `_run_explain_stream()` | direct call, parameterized | ✓ WIRED | All 3 routes call the identical shared function; `explain.py` proven byte-identical since Plan 04 |
| `frontend/.../drill-content.tsx` | `components/ai/ai-explanation-section.tsx` | import + `<section aria-labelledby="drill-ai-h">` | ✓ WIRED | Import path updated post-move; exactly 1 `drill-ai-h` occurrence |
| `assets/[id]/page.tsx` | `AiExplanationSection resourceType="host"` | component mount | ✓ WIRED | `resourceType="host"` present, asset id passed as resourceId |
| `remediation-timeline.tsx` | `AiExplanationSection resourceType="remediation"` | per-row component mount, gated on non-null `cve_id` | ✓ WIRED | `list_tickets()` MIN-aggregate `cve_id` field added and tested |
| `backend/app/ai/budget.py` | `notifications.service.create_notification` | per-admin call on breach, `send_email_flag=True` | ✓ WIRED | Verified via `test_admin_notified_on_breach` |
| `frontend AiExplanationSection` | `frontend/lib/queries/use-connectors-admin.ts useConnectorsList()` | `keyConfigured` derivation | ⚠️ WIRED BUT IMPRECISE | See Gaps — the link exists and functions, but the signal it derives is not accurate for non-Admin roles (admin-gated endpoint) |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `ai-explanation-section.tsx` | `state.data` (validated explanation) | `useExplainStream` → real backend SSE → `_run_explain_stream()` → real Anthropic SDK call (mocked only in tests) | Yes — real DB-backed grounding record (`get_vulnerability`/`get_asset_posture`/`get_remediation_group`, all real tenant-scoped SQL queries, not static returns) | ✓ FLOWING |
| `ai-explanation-section.tsx` | `keyConfigured` | `useConnectorsList()` → `GET /api/v1/connectors` (real DB query) | Partially — real data for Admin/Owner; a synthetic `true` fallback for Analyst/Viewer on any query error (not a static stub, but not the resource's real state either) | ⚠️ STATIC (for non-admin roles only) |
| `remediation-timeline.tsx` | `t.cve_id` | `list_tickets()` → `func.min(Vulnerability.cve_id)` (real aggregate query) | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Backend AI test suite passes | `pytest tests/test_ai_*.py tests/test_connectors/test_ai_tester.py -q` | 125 passed, 0 failed | ✓ PASS |
| Full backend suite (regression) | `pytest tests/ -q` | 475 passed, 1 failed (pre-existing, unrelated `test_connector_health.py` flake — 9/9 in isolation, documented in `deferred-items.md` since Plan 24-04) | ✓ PASS |
| `alembic upgrade head` applies cleanly | `alembic upgrade head && alembic heads` | `032_add_ai_feedback (head)` | ✓ PASS |
| Frontend AI test suite passes | `npx vitest run use-explain-stream ai-explanation-section ai-explanation-citations ai-feedback-control add-connector-wizard` | 58/58 passed | ✓ PASS |
| Full frontend suite (regression) | `npx vitest run` | 810/810 passed (130 files) | ✓ PASS |
| Mount-site tests (host/remediation) | `npx vitest run` (asset detail + remediation timeline files) | 9/9 + 12/12 passed | ✓ PASS |
| `tsc --noEmit` clean | `npx tsc --noEmit` | No output (clean) | ✓ PASS |
| `ruff check` clean on new files | `ruff check app/ai/ app/api/v1/ai/` | All checks passed | ✓ PASS |
| `mypy` zero new errors on new files | `mypy app/ai/ app/api/v1/ai/` \| filter to `app/ai/` and `app/api/v1/ai/` paths | 0 matches (all 76 reported errors are in unrelated pre-existing files) | ✓ PASS |
| nginx `location /api/v1/ai/` progressive delivery through real proxy | `curl -N` through live Docker/nginx | NOT RUN | ? SKIP — explicitly waived by user; see human_verification |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|----------------|--------------|--------|----------|
| AI-01 | 24-01, 24-03, 24-05, 24-06 | Tenant admin configures own Anthropic key, encrypted, no shared/fallback key; features disabled until configured | ✓ SATISFIED (core capability) — see Gap #2 for a narrower UI-precision deviation on the "graceful state" framing for non-admin roles | `get_tenant_anthropic_key`, `CONNECTOR_TYPES["ANTHROPIC"]`, zero shared-key code paths, all backend-verified. Frontend precision gap tracked separately, does not compromise the BYOK guarantee itself |
| AI-02 | 24-02, 24-04, 24-08 | Untrusted scanner text as data only; schema-validated output | ✓ SATISFIED | Injection isolation + delimiter breakout + schema gate all real-tested and passing |
| AI-03 | 24-01, 24-04, 24-05 | Token-by-token streaming via fetch+ReadableStream; nginx no-buffering | ✓ SATISFIED (mechanism) / ? NEEDS HUMAN (live proxy behavior, explicitly waived) | Mechanism code-verified + automated-tested; live behavior unproven per explicit waiver |
| AI-04 | 24-05, 24-07, 24-08, 24-09 | "Explain this vuln/host/remediation" + two-tier citation | ✓ SATISFIED | All three views ship via one shared, tested component; citation rendering verified |
| AI-05 | 24-03, 24-04, 24-08 | Tenant-scoped, content-hash-keyed cache; no cross-tenant serving | ✓ SATISFIED | Proven against real Redis, not mocked |
| AI-06 | 24-02, 24-03, 24-04 | Every AI call audit-logged incl. scheduler-originated, explicit tenant_id | ✓ SATISFIED | `audit_log_ai_call` symmetric interactive/scheduler shape unit-tested; every `_run_explain_stream()` code path audits |

No orphaned requirements: REQUIREMENTS.md maps exactly AI-01..AI-06 to Phase 24, and every one of the 9 plans' `requirements:` frontmatter fields collectively covers all 6 IDs (cross-checked: 24-01→[AI-01,AI-03], 24-02→[AI-02,AI-06], 24-03→[AI-01,AI-05,AI-06], 24-04→[AI-02,AI-03,AI-05,AI-06], 24-05→[AI-03,AI-04], 24-06→[AI-01..AI-06] (checkpoint, verify-only), 24-07→[AI-04], 24-08→[AI-04], 24-09→[AI-04]). No ID is claimed without a corresponding REQUIREMENTS.md entry, and no REQUIREMENTS.md entry for Phase 24 goes unclaimed.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/app/api/v1/ai/spike.py` + `__init__.py` | whole file | Throwaway Wave-0 spike route left registered/live (plan said "remove or leave inert before phase seal") | ℹ️ INFO | Mitigated: still gated behind `require_analyst` (never anonymous), so the threat model's own disposition holds; it's dead/unused code left mounted, not a security or functional gap |
| `backend/app/ai/explain.py` | 82-88 | Haiku `effort:"low"` support is a documented conservative assumption (`_NO_EFFORT_MODELS`), never live-verified against a real Anthropic key across all 3 plans that touched this (01, 04) | ℹ️ INFO | No dev Anthropic key was ever available in any execution environment this phase; the code implements the safe fallback per the plan's own contingency instruction. Does not block any must-have — self-documented as an open item across 2 SUMMARYs |
| `frontend/src/lib/ai/use-explain-stream.ts` | 64-73 | The outer `try{ fetch() }catch{...}` (genuine network failure before any response) has no dedicated test — only the `!res.ok` branch is tested | ℹ️ INFO | Low risk: the catch path falls into the same generic `kind:'unknown'` retryable state already proven correct for other paths; an uncovered-but-sensible error path (Confirmation Bias Counter finding) |
| `.planning/phases/24-.../24-VALIDATION.md` | frontmatter | `status: draft`, `nyquist_compliant: false`, Wave-0 checklist never filled in | ℹ️ INFO | Matches the known project pattern (per user memory: several prior phases' VALIDATION.md were stale pre-exec artifacts, not real gaps) — actual test-sampling clearly happened per each plan's own extensive, evidenced Self-Check sections and the live pytest/vitest reruns performed during this verification |
| `.planning/ROADMAP.md` | line 291 | "Plans: 7/9 plans executed" text is stale (all 9 plan checkboxes below it are `[x]`, and all 9 SUMMARY.md files exist and are complete) | ℹ️ INFO | Documentation bookkeeping inconsistency only, not a functional gap |

No 🛑 Blocker-severity anti-patterns found in any of the 24 new/modified AI-specific source files (backend `app/ai/`, `app/api/v1/ai/`; frontend `lib/ai/`, `components/ai/`, `ai-feedback-control.tsx`, `use-ai-feedback.ts`, `use-explain-cache.ts`): zero TODO/FIXME/HACK/PLACEHOLDER markers, zero "coming soon" copy, zero red/`--color-danger` classes, zero freehand hex, zero `font-mono` substitution, zero no-op handlers, zero empty stub returns outside legitimate empty-input guard clauses.

### Human Verification Required

### 1. AI-03 nginx anti-buffering through the real proxy

**Test:** `docker compose up -d`, then `curl -N -H "Authorization: Bearer <analyst-token>" -X POST http://localhost/api/v1/ai/explain-vuln/<finding_id>`
**Expected:** Frames print progressively as they arrive (first byte well before the full ~2s+ completion), never all four/five frames dumped at once after full latency (the classic nginx-buffering symptom)
**Why human:** Requires the live Docker/nginx stack + a real Anthropic key; explicitly waived by the user at the 24-06 checkpoint. This is the ONE check RESEARCH.md itself flagged as impossible to automate through the real proxy.

### 2. Live end-to-end tracer (wizard → save → explain → cache → audit-row)

**Test:** As Admin, configure a real Anthropic key via `/dashboard/connectors`; as Analyst, open a vuln drill panel and click "Explain this vuln"; re-open the same finding to confirm a cache hit; open the audit-log pane and confirm an `ai.explain.vuln` row appears
**Expected:** Each stage completes visibly and consistently with the automated-test-proven backend behavior
**Why human:** Explicitly waived at the 24-06 checkpoint ("skip live verify, proceed on trust"). Every individual stage is proven by automated tests in this verification; the composed live flow was never observed running.

### 3. D-25 persistent-429 "AI busy" card

**Test:** Force a persistent Anthropic rate-limit (or point the client at a 429-returning mock) and click Explain on an uncached finding
**Expected:** The amber "AI busy — try again in a moment" card with a working "Try again" button appears — never a generic error, blank panel, or partial text
**Why human:** Explicitly waived at the 24-06 checkpoint. Backend emission + frontend rendering are both unit-proven in isolation; the live-triggered end-to-end visual was not exercised.

### 4. Reduced-motion + citation contrast in a real browser (dark + light)

**Test:** Toggle OS-level `prefers-reduced-motion`; inspect `violet-on-soft` citation tint contrast in both themes
**Expected:** Reduced-motion renders the result instantly (no reveal animation); citation tint is legible (AA contrast) in both themes
**Why human:** Explicitly waived. Per project convention, WCAG AA claims are treated as unproven without a live axe sweep (none run this phase) — reason about token contrast manually rather than asserting a pass. Reduced-motion branching is unit-tested via mocked `matchMedia`, not observed live.

### Gaps Summary

Of the two categories of open items:

**1. One concrete, code-proven gap (not waived, not uncertain):** the "key configured" signal `ai-explanation-section.tsx` derives for Analyst/Viewer roles is structurally inaccurate — `GET /api/v1/connectors` is `require_admin`-gated, so those roles' query always errors, and the component optimistically treats that as "assume configured." In a genuinely unconfigured tenant, an Analyst sees a live "Explain this vuln" button instead of the specified role-gated "ask an admin" text, and clicking it surfaces the SAME amber "AI busy — try again in a moment" card used for real transient rate-limiting — a permanently-wrong, retry-inviting message for what is actually a permanent "not configured" state. This was self-identified and transparently documented by the Plan 05 executor (24-05-SUMMARY.md "Issues Encountered") with a specific suggested remediation (a lightweight, non-admin-safe "AI configured" signal endpoint) — it was not hidden, but it also was not fixed, and the associated frontend test for this exact scenario mocks a state (`isError: false`) that cannot occur in real production for the Analyst role, so the gap has no regression coverage pointing at it. No security or BYOK boundary is crossed by this gap (no unauthorized dispatch, no cross-tenant leak, no crash) — it is a UI-precision/messaging gap, not a safety gap. **This looks like it could be an intentional, accepted trade-off** given how thoroughly it was self-documented; see the override suggestion below.

**This looks intentional.** To accept this deviation, add to VERIFICATION.md frontmatter:

```yaml
overrides:
  - must_have: "No-key state is role-gated: Analyst/Viewer get the 'ask an admin' nudge, no CTA"
    reason: "GET /api/v1/connectors is require_admin-gated (pre-existing from Phase 19); no non-admin-safe alternative signal exists yet. Optimistic pass-through keeps the Analyst tracer functional in the common (key-configured) case; the residual imprecise-copy edge case (unconfigured tenant) is accepted until a follow-up adds a lightweight viewer-safe status endpoint."
    accepted_by: "{your name}"
    accepted_at: "{current ISO timestamp}"
```

Alternatively, a small closure plan can add a `require_viewer`-gated `GET /api/v1/ai/status` (or similar) endpoint that all roles can call for an accurate signal, replacing the `isError`-based guess.

**2. Four explicitly-waived live/manual verification items** (AI-03 nginx anti-buffering, the full live tracer, the D-25 live busy card, and reduced-motion/contrast in a real browser) — the user explicitly chose "skip live verify, proceed on trust" at the 24-06 checkpoint. These are reported here as open `human_verification` items per that explicit instruction, not as failures: every underlying mechanism they would confirm is independently proven correct by automated tests and direct code/config inspection in this verification pass. They remain the only parts of this phase's goal not yet observed running for real.

**Everything else — the schema-validation gate, the untrusted-content-as-data prompt contract, the tenant-scoped cache with proven cross-tenant isolation against real Redis, the fail-closed budget guard, the buffer-then-validate-then-replay streaming engine with its full retry/rate-limit/injection-flag/audit taxonomy, the two-tier citation renderer, the D-16 cross-asset-CVE grounding decision faithfully implemented, the three-view widening to host/remediation via one shared component, and the capture-only feedback mechanism — is genuinely built, substantively implemented, correctly wired, and passes 125/125 backend AI tests + 810/810 frontend tests (including a full-suite regression sweep with only one pre-existing, unrelated, already-documented flake).** This is a well-executed phase with one narrow, self-disclosed, non-security precision gap and a set of explicitly-waived manual checks — not a phase where the goal was broadly missed.

---

_Verified: 2026-07-29T13:17:16Z_
_Verifier: Claude (gsd-verifier)_
