---
phase: 25-asset-aware-remediation-guidance
verified: 2026-07-30T12:23:29Z
status: passed
status_note: "PASSED WITH ACCEPTED DEBT. All 12 programmatically-verifiable must-haves pass; zero gaps, zero regressions (backend 178/178 + 33/33, frontend 839 green); all 6 load-bearing safety facts confirmed in code. The 2 remaining human_verification items (live cited-steps render + WCAG AA live axe) are the live browser checks the user EXPLICITLY WAIVED at the 25-05 tracer gate (proceed-on-trust, mirroring 24-06) and, on 2026-07-30, accepts as TRACKED DEBT rather than blocking. NOT observed — tracked in 25-UAT.md; close via /gsd-verify-work 25 against a live stack + dev Anthropic key. This status reflects a conscious user risk-acceptance decision, not live confirmation."
human_verification_disposition: waived-accepted-as-debt
score: 12/12 verifiable must-haves verified (2 live items accepted as debt)
overrides_applied: 1
human_verification:
  - test: "Live cited-steps render + insufficient-evidence card (SC1/SC2 visual check)"
    expected: "With a configured tenant Anthropic key: a finding with real vendor remediation text shows 'Analyzing this finding…' then cited steps with scanner_verbatim text tinted and rendered before any ai_interpreted text; a finding with blank/generic remediation text shows the neutral 'Not enough vendor guidance to recommend a fix' card with no button, before any click."
    why_human: "Requires a live Docker stack + a configured Anthropic API key, which is unprovisioned in this environment. Explicitly WAIVED by the user at the 25-05 tracer gate (proceed-on-trust, mirroring Phase 24's 24-06 decision) — reported here as unproven, not failed."
  - test: "WCAG AA contrast/focus-order check on the new danger card, groundable branch, and ticket-description Textarea"
    expected: "New danger/red card, neutral insufficient-evidence card, and Textarea meet WCAG AA contrast and keyboard/focus-order requirements."
    why_human: "Per project convention (no live axe/Playwright sweep run this phase), WCAG AA claims are unproven and must be verified live, not inferred from token usage alone."
---

# Phase 25: Asset-Aware Remediation Guidance Verification Report

**Phase Goal:** An analyst gets remediation guidance grounded strictly in the scanner's own solution text plus asset facts — never a fabricated fix (cite-or-refuse) — and can carry it into a draft ticket description they review/edit before creating.
**Verified:** 2026-07-30T12:23:29Z
**Status:** passed (with accepted debt — 2 waived live-verification items, see `status_note`)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SC1 — analyst can request remediation guidance and see OS/package-aware steps citing the scanner's own solution text VERBATIM before any AI interpretation, in the drill panel | ✓ VERIFIED (code+tests); live render UNCERTAIN | `SYSTEM_PROMPT_REMEDIATION_GUIDANCE` (backend/app/ai/prompt_builder.py:956-982) mandates "Cite the vendor's own solution text VERBATIM FIRST, tagged 'scanner_verbatim', before adding any of your own interpretation" and folds in os_name/os_version/affected_product/affected_version/fixed_version. `AiExplanationCitations` (frontend) renders `scanner_verbatim` citations with distinct violet tinting + tooltip, `ai_interpreted` with an "AI" superscript, in document order. New "Remediation guidance" section mounted in `drill-content.tsx` (`resourceType="remediation-guidance"`). All backend/frontend unit suites green (see Behavioral Spot-Checks). Live browser render is a human-verification item (waived at 25-05). |
| 2 | SC2 — when no vendor remediation guidance exists, the assistant says so explicitly (insufficient evidence) rather than inventing a fix | ✓ VERIFIED (code+tests); live render UNCERTAIN | Two-layer refuse: (a) deterministic `has_actionable_remediation_text()` (grounding.py:240-261) — `.strip()`+15-char minimum+casefolded-placeholder-set, never `is not None`; route-level pre-generation gate returns a single `grounded_false` SSE frame with `status="ungroundable"`, zero model calls (`explain_remediation_guidance.py` `_refuse_ungroundable`). (b) model's own `grounded=false` judgment renders the identical card. Frontend `groundable===false` branch suppresses the trigger button before any click (`ai-explanation-section.tsx` line ~278). 12 route tests + 12 frontend groundable/copy tests green. |
| 3 | SC3 — analyst can populate a draft ticket description from the guidance and review/edit before creating | ✓ VERIFIED | `onCopyToDescription={setDescription}` wires `AiExplanationSection`'s "Copy into ticket description" button to `drill-content.tsx` state; textarea (desktop `ConfirmModal` child + mobile `Drawer.NestedRoot` `renderConfirm` path) is freely editable; `fireTicket()` threads `description: description \|\| undefined` into `createTicket.mutateAsync`. Backend `TicketCreateRequest.description` (bounded, `extra="forbid"`) and `create_tickets()`'s WYSIWYG override (`request.description.strip() if ... else _build_task_description(...)`) prove the analyst's exact reviewed text reaches `client.create()`'s `notes` arg — not a UI-only pre-fill. 13 new frontend tests + 11 backend dispatch tests, all asserting on the mutation/client-call boundary, green. |
| 4 | Fact 1 — dangerous-pattern gate runs at ENGINE level, AFTER leak-marker check, BEFORE `set_cached()`; dangerous content never cache-retrievable | ✓ VERIFIED | `backend/app/ai/explain.py` lines 430-467: `_contains_leak_marker` check (430-446) precedes the `dangerous_pattern_check` gate (448-467), which precedes `set_cached()` (473). On a hit: audits `unsafe_denylisted`, yields `{"type":"error","kind":"unsafe"}`, `return`s — never reaches `set_cached`. Backstop test `test_dangerous_pattern_check_hit_is_unsafe_denylisted_and_never_cached` mocks `set_cached` and asserts `assert_not_called()` (not just SSE content). Ran green: `tests/test_ai_explain_stream.py` 18/18 passed. Route-level backstop (real engine, fake Anthropic client) also green in `test_ai_explain_remediation_guidance.py`. |
| 5 | Fact 2 — refuse predicate uses `.strip()`+min-length+placeholder screen, not `is not None` | ✓ VERIFIED | `grounding.py:240-261` — `has_actionable_remediation_text` loops both fields, `raw.strip()`, `len(text) < MIN_REMEDIATION_CHARS` (15), `text.casefold() in _GENERIC_REMEDIATION_PLACEHOLDERS` (6-entry frozenset incl. empty-after-strip-implied cases). No `is not None` anywhere in the function. 18 grounding tests green. |
| 6 | Fact 3 — grounding query excludes owner-PII fields | ✓ VERIFIED | `get_remediation_guidance_context()` SELECTs exactly 12 columns (cve_id, remediation_action, remediation_info, affected_product, affected_version, fixed_version, severity, exploit_available, cisa_kev, Asset.hostname/os_name/os_version). `grep -nE "assigned_user\|directory_user\|managed_by\|building\|serial_number\|department"` on grounding.py shows zero matches inside this function. |
| 7 | Fact 4 — AIR-02 is a real backend contract (not UI-only pre-fill) | ✓ VERIFIED | `TicketCreateRequest.description: str \| None = Field(None, max_length=10000)` + `model_config = {"extra": "forbid"}` + whitespace-coercion validator (schemas.py:53-79). `create_tickets()` (service.py:222-230) honors `request.description.strip()` when present, else falls back to `_build_task_description()`. Both WYSIWYG-override and fallback dispatch tests (`test_create_tickets_uses_request_description_when_supplied`, `test_create_tickets_falls_back_to_built_description_when_omitted`) assert on `fake.created[0][1]` (the actual client.create() notes arg) — green. |
| 8 | Fact 5 — description textarea wired through BOTH desktop and mobile paths to the create-ticket mutation body | ✓ VERIFIED | Desktop: `drill-content.tsx` `fireTicket()` sends `description: description \|\| undefined`. Mobile: `drill-panel-mobile.tsx`'s `renderConfirm` destructures the identical `description`/`onDescriptionChange` from `DrillContent`'s shared state (never imports `ConfirmModal`, builds its own `Drawer.NestedRoot` markup — genuinely divergent path). Both paths tested independently: `drill-panel.test.tsx` (4 new tests) + `drill-panel-mobile.test.tsx` (3 new tests), all asserting on `mockMutateAsync` call args, not just DOM state. |
| 9 | Fact 6 — no regressions in relevant test suites | ✓ VERIFIED | Backend: `test_ai_*.py` 178/178 green; `test_ticketing_dispatch.py` 33/33 green. Frontend: full suite 130 files / 839 tests green; `ai-explanation-section`/`drill-panel`/`drill-panel-mobile` subsets (83 tests) green in isolation. Ruff clean on all touched backend files. |
| 10 | UI-SPEC "partial" backstop — a denylist hit never yields a partially-redacted step list | ✓ VERIFIED (structural) | No literal "mixed safe+dangerous lines" fixture test exists, but the guarantee is structural and doubly proven: (a) backend `_run_explain_stream` never emits `summary_delta`/`done` before the `unsafe` frame on a hit (asserted in the backstop test) — the model's full candidate is discarded whole, never partially forwarded; (b) frontend's `kind==='unsafe'` branch renders 100%-static locked copy (`ai-explanation-section.tsx` lines 234-247) with zero data binding to any candidate field — it cannot render a partial step list even if the backend ever sent one. |
| 11 | Requirements AIR-01 / AIR-02 traceability | ✓ VERIFIED | REQUIREMENTS.md lines 36-37, 91-92: both marked `[x]` Complete, mapped to Phase 25. Plan frontmatter: AIR-01 declared in 25-01/02/03/04/05; AIR-02 declared in 25-06/07. No orphaned requirement IDs found for Phase 25. |
| 12 | Router registration | ✓ VERIFIED | `backend/app/api/v1/ai/__init__.py` imports `explain_remediation_guidance` and calls `ai_router.include_router(explain_remediation_guidance.router)`; RBAC confirmed in-file (`require_analyst` on POST, `require_viewer` on GET); `app/ticketing/router.py` unchanged by this phase (last touched in Phase 23, confirmed via git log). |

**Score:** 12/12 programmatically-verifiable truths verified. 2 items require human/live verification (see below) — these were explicitly WAIVED at the 25-05 tracer gate (proceed-on-trust) and are reported as unproven, not failed.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/ai/safety.py` | `DANGEROUS_PATTERNS` + `contains_dangerous_pattern` | ✓ VERIFIED | 8-category denylist, stdlib `re` only; 16 tests green |
| `backend/app/ai/grounding.py` (additions) | `has_actionable_remediation_text` + `get_remediation_guidance_context` | ✓ VERIFIED | Both present, tenant-scoped, PII-excluding; 18 tests green |
| `backend/app/ai/schemas.py` (addition) | `ExplainRemediationGuidanceResponse` | ✓ VERIFIED | Zero-new-fields subclass; substring-provenance test green |
| `backend/app/ai/prompt_builder.py` (additions) | `REMEDIATION_GUIDANCE_ALLOWLIST` + quadruplet | ✓ VERIFIED | Cite-verbatim-first + refuse-rather-than-invent prompt text confirmed verbatim |
| `backend/app/ai/explain.py` (modified) | `dangerous_pattern_check` param before `set_cached()` | ✓ VERIFIED | Confirmed at exact line position; backward-compatible default-None no-op proven |
| `backend/app/api/v1/ai/explain_remediation_guidance.py` | POST/GET route, D-01 gate, `groundable` field | ✓ VERIFIED | RBAC, 404, ungroundable-refusal, unsafe-backstop all tested green |
| `backend/app/api/v1/ai/__init__.py` (modified) | Router registration | ✓ VERIFIED | Import + include_router present |
| `backend/app/ticketing/schemas.py` (modified) | `TicketCreateRequest.description` | ✓ VERIFIED | Bounded, `extra="forbid"`, whitespace-coerces |
| `backend/app/ticketing/service.py` (modified) | WYSIWYG `notes=` override | ✓ VERIFIED | Confirmed at service.py:222-230 |
| `frontend/src/lib/ai/use-explain-stream.ts` (modified) | `'unsafe'` union member | ✓ VERIFIED | Both `ExplainStreamState` and `ErrorEvent` updated |
| `frontend/src/lib/queries/use-explain-cache.ts` (modified) | `groundable?: boolean` | ✓ VERIFIED | On the `cached: false` branch |
| `frontend/src/components/ai/ai-explanation-section.tsx` (modified) | danger variant, unsafe branch, groundable branch, copy-to-description | ✓ VERIFIED | All present and tested |
| `frontend/src/components/vulnerabilities/drill-content.tsx` (modified) | remediation-guidance section mount + description state + Textarea | ✓ VERIFIED | Confirmed wiring end-to-end |
| `frontend/src/components/vulnerabilities/drill-panel-mobile.tsx` (modified) | mirrored mobile Textarea | ✓ VERIFIED | Divergent `Drawer.NestedRoot` path confirmed |
| `frontend/src/components/ui/textarea.tsx` | shadcn Textarea primitive | ✓ VERIFIED | Restyled to sunset tokens (no new hex) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `explain_remediation_guidance.py` POST | `_run_explain_stream(..., dangerous_pattern_check=contains_dangerous_pattern)` | kwarg pass-through | ✓ WIRED | Confirmed at line 148 |
| `explain_remediation_guidance.py` POST | `has_actionable_remediation_text()` pre-dispatch gate | route-level `if not ...` check | ✓ WIRED | Confirmed at line 125, before any `_run_explain_stream` call |
| `_run_explain_stream` dangerous_pattern_check hit | `unsafe_denylisted` audit + skip `set_cached` | terminal `return` | ✓ WIRED | Confirmed at explain.py:448-467; backstop test asserts `set_cached` never called |
| `AiExplanationSection.onCopyToDescription` | `drill-content.tsx` `setDescription` | prop callback | ✓ WIRED | Confirmed at drill-content.tsx `onCopyToDescription={setDescription}` |
| `drill-content.tsx` description state | `createTicket.mutateAsync` body | `fireTicket()` | ✓ WIRED | `description: description \|\| undefined` confirmed in mutation call |
| `drill-panel-mobile.tsx` renderConfirm description | same `createTicket.mutateAsync` body | shared `DrillContent` state via renderConfirm args | ✓ WIRED | Confirmed — mobile textarea `onChange` calls `onDescriptionChange`, same underlying state as desktop |
| `TicketCreateRequest.description` | `create_tickets()` `notes=` | WYSIWYG override with fallback | ✓ WIRED | Confirmed at service.py:222-230; both override and fallback dispatch tests green |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Engine dangerous-pattern backstop (never cached) | `pytest tests/test_ai_explain_stream.py -q` | 18 passed | ✓ PASS |
| Route-level RBAC/404/ungroundable/unsafe backstop | `pytest tests/test_ai_explain_remediation_guidance.py -q` | 12 passed | ✓ PASS |
| Denylist positive/negative/obfuscation coverage | `pytest tests/test_ai_safety.py -q` | 16 passed | ✓ PASS |
| Refuse predicate + PII-exclusion + tenant isolation | `pytest tests/test_ai_grounding_remediation_guidance.py -q` | 18 passed | ✓ PASS |
| Schema + prompt-builder allowlist/injection/provenance | `pytest tests/test_ai_schemas.py tests/test_ai_prompt_builder_remediation_guidance.py -q` | passed (part of 101-test batch) | ✓ PASS |
| Ticket description schema + WYSIWYG dispatch | `pytest tests/test_ticketing_dispatch.py -q` | 33 passed | ✓ PASS |
| Full backend AI regression | `pytest tests/test_ai_*.py -q` | 178 passed | ✓ PASS |
| Full frontend regression | `npx vitest run` | 839 passed (130 files) | ✓ PASS |
| Ruff lint on touched backend files | `ruff check <files>` | All checks passed | ✓ PASS |
| Commit existence for 9 claimed hashes | `git log --oneline \| grep <hashes>` | all 9 found | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| AIR-01 | 25-01, 25-02, 25-03, 25-04, 25-05 | Asset-aware remediation guidance, cite-or-refuse | ✓ SATISFIED | Denylist, refuse predicate, grounding query, schema/prompt quadruplet, engine gate, route, frontend section all verified in code + tests |
| AIR-02 | 25-06, 25-07 | Populate draft ticket description, review/edit before creating | ✓ SATISFIED | Backend contract + WYSIWYG override + desktop/mobile frontend wiring all verified at the mutation/client-call boundary |

No orphaned requirements found for Phase 25 (REQUIREMENTS.md maps only AIR-01/AIR-02 to this phase, both accounted for in plan frontmatter).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `.planning/phases/25-asset-aware-remediation-guidance/25-VALIDATION.md` | frontmatter | `status: draft`, `nyquist_compliant: false`, sign-off checkboxes unchecked | ℹ️ Info | Documentation debt, not a functional gap — per project memory ("Nyquist validation state"), stale pre-exec VALIDATION.md flags have historically not reflected real test-coverage gaps in this codebase; all actual test suites referenced in this file ran green during this verification. Should be reconciled (flipped to `validated`/`true`) in a future docs pass, consistent with how Phase 25-01-05's predecessors were handled in v2.1 (BL-05). |

No blocker or warning-level anti-patterns (no TODO/FIXME/stub/placeholder markers, no empty handlers, no hardcoded-empty data flowing to render) found in any of the phase's new or modified files.

### Human Verification Required

### 1. Live cited-steps render + insufficient-evidence card

**Test:** Configure a tenant Anthropic key; open a finding whose raw "Remediation" section shows real vendor solution text; click "Get remediation guidance" in the new drill-panel section. Separately, open a finding with blank/generic remediation text.
**Expected:** First finding streams "Analyzing this finding…" then cited steps with `scanner_verbatim` vendor text visually tinted and appearing before any `ai_interpreted` text. Second finding shows the neutral "Not enough vendor guidance to recommend a fix" card with no trigger button, before any click.
**Why human:** Requires a live Docker stack + configured Anthropic API key + browser observation. This environment has neither provisioned. The user explicitly WAIVED this check at the 25-05 tracer gate (proceed-on-trust, mirroring Phase 24's 24-06 decision) — recorded in `25-05-SUMMARY.md`. All underlying logic (prompt cite-verbatim-first instruction, citation-rendering component, groundable pre-signal, insufficient-evidence branch) is unit-tested and green; only the live visual render is unproven.

### 2. WCAG AA accessibility of new UI surfaces

**Test:** Run an axe/Playwright accessibility sweep against the new danger card, neutral insufficient-evidence card (remediation-guidance-flavored copy), and the ticket-description Textarea (both desktop and mobile).
**Expected:** No WCAG AA violations (contrast, focus order, ARIA labeling).
**Why human:** Per established project convention (see memory: "Axe sweep not run during execution"), no live axe sweep was run this phase; token-contrast reasoning alone is not proof. Treat as unproven, not failed.

### Gaps Summary

No blocking gaps. All 12 programmatically-verifiable must-haves (roadmap SC1-SC3, the 6 load-bearing safety/contract facts specified for this verification, plus requirements traceability and regression health) are VERIFIED directly against the codebase — not merely claimed in SUMMARY.md. The engine-level dangerous-pattern gate is correctly positioned before `set_cached()` with a green backstop test asserting `set_cached` is never called on a hit. The refuse predicate correctly avoids `is not None` in favor of `.strip()`+length+placeholder screening. The grounding query is structurally incapable of leaking owner-PII columns. AIR-02 is a real, tested backend contract (bounded, `extra="forbid"`, WYSIWYG override with fallback) wired through both desktop and mobile frontend paths to the actual ticket-creation mutation body — not a UI-only pre-fill that silently discards edits. All targeted backend and frontend test suites (368 backend-relevant + 839 frontend tests spot-checked) are green with no regressions.

The two items requiring human verification (live browser render of cited steps/insufficient-evidence card, and a live WCAG AA sweep) were both explicitly and knowingly deferred by the user during phase execution (25-05 tracer gate) and per project convention respectively — they are reported here as open human-verification items per the escalation-gate pattern, not as gaps or failures. This is why overall status is `human_needed` rather than `passed`, even though every truth resolvable from the codebase resolved to VERIFIED.

---

*Verified: 2026-07-30T12:23:29Z*
*Verifier: Claude (gsd-verifier)*
