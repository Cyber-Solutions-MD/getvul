---
phase: 27-ticket-auto-drafting
verified: 2026-08-01T16:20:00Z
status: passed
status_note: "PASSED WITH ACCEPTED DEBT. All 12 code-level must-haves verified; zero gaps, zero regressions (backend test_ticketing_dispatch 43/43, frontend 889/889, tsc/eslint clean; git diff --stat confirms zero provider-client change — pure-consumer boundary held). The 1 remaining human_verification item is the live-browser create flow, which — unlike 24/25/26 — had no tracer-gate waiver (this phase correctly had no checkpoint: no new AI call). On 2026-08-01 the user explicitly chose to ACCEPT it as TRACKED DEBT rather than block, consistent with the 24/25/26 precedent. NOT observed — tracked in 27-UAT.md; close via /gsd-verify-work 27. Conscious user risk-acceptance, not live confirmation."
human_verification_disposition: waived-accepted-as-debt
score: 12/12 verifiable must-haves verified (1 live item accepted as debt)
overrides_applied: 1
human_verification:
  - test: "Live ticket-create flow: open dialog -> pre-fill -> edit -> Create"
    expected: "Opening the Jira/Asana ticket-create dialog for a vuln with cached AI outputs shows an AI-drafted Title + multi-section Description (Description/Remediation/Asset context/Prioritization as applicable); every field is editable; clicking a gap-fill button streams and appends a section; clicking Create (a human click) is the only way a ticket is actually created; switching vulns does not leak a draft; the no-key manual flow is unaffected."
    why_human: "Requires a live Docker stack + a configured tenant Anthropic key + browser observation. Same waived-class as Phase 24-26's live items (no dev Anthropic key / live stack in this environment). This phase deliberately had no tracer-gate checkpoint (correct call — it adds no new AI call, all riskiest logic is unit-tested), so unlike Phases 24/25/26 there is no explicit per-phase user 'proceed on trust' waiver recorded for this specific live flow — reported here as human_verification rather than silently defaulted to passed."
---

# Phase 27: Ticket Auto-Drafting Verification Report

**Phase Goal:** An analyst opening the Jira/Asana ticket-create flow gets an AI-drafted title/description/remediation/asset-context pre-filled, edits every field, and a human click always creates the ticket (never auto-submitted). Pure consumer of Phase 24/25/26 outputs; no new AI call; no Ticket DB model change.

**Verified:** 2026-08-01T16:20:00Z
**Status:** passed (with accepted debt — 1 waived live item, see status_note)
**Re-verification:** No — initial verification

## Goal Achievement

All truths below were checked directly against the codebase (full source reads of every touched file, live `pytest`/`vitest` execution, `git diff --stat` across every phase commit, `git log` commit-hash confirmation, and targeted `grep` proofs) — SUMMARY.md claims were treated as hypotheses to falsify, not evidence. Every SUMMARY claim checked below was independently reproduced from source, not trusted.

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | **SC1 (Title)** — opening the create dialog pre-fills a deterministic Title, regardless of AI key configuration — AID-01 | VERIFIED | `compose-ticket-draft.ts:25-34` `composeTicketTitle()` returns `[{sevLabel}] {cveLabel} on {hostsLine}`, zero AI/network import. `drill-content.tsx:369-402` compose-on-open effect calls it unconditionally on first open. `drill-panel.test.tsx:394-405` proves the deterministic value renders even with the suite's default no-key mock state. `compose-ticket-draft.test.ts` (3 title tests, all green). |
| 2 | **SC1 (Description/Remediation/Prioritization)** — pre-fill includes labeled AI sections, each present ONLY on a grounded cache hit, never a labeled-but-empty stub — AID-01 | VERIFIED | `compose-ticket-draft.ts:51-58,76-78` — `Description:`/`Remediation:`/`Prioritization:` sections gated on `.grounded === true`; a cache miss/ungrounded/errored cache is omitted entirely. 13 permutation tests in `compose-ticket-draft.test.ts` (all-null, single/double/all-four sections, `grounded:false` omission) all green. Only `summary` is read — `grep -c 'business_risk' compose-ticket-draft.ts` == 0. |
| 3 | **SC1 (Asset context)** — "Asset context:" is ALWAYS present, needs no AI call, renders even with no AI key configured (D-04) | VERIFIED | `compose-ticket-draft.ts:60-71` builds Host/Product/Severity (+ conditional CISA KEV / Exploit available) unconditionally, no cache/network dependency. `drill-panel.test.tsx:308-321` proves `"Asset context:"` appears in the default no-key/no-cache mock state. |
| 4 | **SC2 (edit every field + composed-once guard)** — analyst can edit/clear Title and Description; re-opening the SAME vuln's dialog never re-composes over edits | VERIFIED | `drill-content.tsx:262,369-373` — `composedForId` is a `useRef<string\|null>` keyed to `v.id ?? idOrCve` (NOT a blank-string check), gated on `confirmOpen`. `drill-panel.test.tsx:423-438` ("editing the Title, cancelling, and re-opening the SAME vuln preserves the edit") is green. `drill-panel.test.tsx:339-357` proves a deliberately-cleared field threads `undefined`, never `''`. |
| 5 | **Cross-vuln recompose (Pitfall 3)** — switching to a DIFFERENT vuln recomposes; vuln A's draft never carries onto vuln B's ticket | VERIFIED | Same `composedForId` guard: differing `id` fails the `composedForId.current === id` check, forcing recompose. `drill-panel.test.tsx:440-471` ("switching to a DIFFERENT vuln recomposes the Title") simulates the exact idOrCve-changes-without-remount reproduction and asserts vuln B's own title, `not.toContain('CVE-2024-3094')`. |
| 6 | **SC3 (never auto-submit)** — the human Create click is the ONLY path to `createTicket.mutateAsync`; Create is never gated on draft completeness; nothing else can submit | VERIFIED | `drill-content.tsx:514-551` `fireTicket()` is the sole caller of `mutateAsync`, invoked only via `onConfirm={fireTicket}` (`ConfirmModal.tsx:102`, a literal `<button onClick={onConfirm}>`) or the mobile Create `onClick={onConfirm}` (`drill-panel-mobile.tsx:276`). `confirmDisabled={!ticketProvider}` (`drill-content.tsx:759`) and mobile's `disabled={ticketProvider === null}` (pre-dates this phase — `git log` shows this line unchanged since Phase 23-11) are the ONLY disable conditions; no title/description-based gate was added. Zero `<form>` elements in `drill-content.tsx`/`drill-panel-mobile.tsx`/`ConfirmModal.tsx` (grep confirmed) — Enter-to-submit is structurally impossible. Zero `setTimeout`/`setInterval` in any of the 4 relevant files. `ResponsiveDialog`'s `onOpenChange` only ever calls `onCancel`, never `onConfirm`. Negative tests: `drill-panel.test.tsx:473-481` (compose doesn't auto-submit) + `:642-654` (gap-fill doesn't auto-submit) on desktop; `drill-panel-mobile.test.tsx:401-425` (gap-fill doesn't auto-submit) on mobile. |
| 7 | **Backend title contract** — `TicketCreateRequest.title` optional, `max_length=255` (not description's 10000), whitespace-only→`None`, `extra="forbid"` unweakened; `create_tickets()` honors `request.title` else falls back unchanged; zero per-provider change | VERIFIED | `schemas.py:81` `title: str \| None = Field(None, max_length=255, ...)`; `schemas.py:91-97` `_title_no_ws_only` validator (distinct name from `description`'s); `model_config = {"extra": "forbid"}` appears exactly ONCE in the class (line 71, inherited by `title`, no duplicate added). `service.py:207-211` `task_name = request.title.strip() if request.title and request.title.strip() else f"[{sev}] {cve} on {hostname or 'unknown host'}"`. `git diff --stat` across every Phase 27 commit shows **zero** touches to `dispatch.py`, `jira_client.py`, `asana_client.py`, `github_client.py`, or the `create_host_ticket()`/`create_remediation_ticket()` task_name lines. Live pytest run: `test_ticket_create_request_title_over_255_raises` and `test_create_tickets_falls_back_to_built_title_when_omitted` (×3 providers) both green — **43/43** in `test_ticketing_dispatch.py`. |
| 8 | **Gap-fill gating + reuse** — "Draft with AI" buttons render ONLY when key configured AND role Analyst+ (D-17); clicking triggers the EXISTING `useExplainStream` (no new endpoint); on grounded success, APPENDS without overwriting | VERIFIED | `drill-content.tsx:494-497` `gateOpen = keyConfigured && isAnalystOrAbove`; `:351-352` calls the same `useExplainStream('vuln'\|'remediation-guidance', id)` hook `ai-explanation-section.tsx` already uses (zero new backend route — confirmed via the same `git diff --stat`, zero `backend/app/ai/*.py` files touched). `:411-422,424-435` append effects use functional `setDescription((prev) => prev ? \`${prev}\n\n${section}\` : section)`, gated on `confirmOpen` so a pre-open resolution can't silently get discarded. `drill-panel.test.tsx:493-522,540-565` (Viewer/no-key → no buttons; Analyst+key → buttons; grounded-done appends without overwriting prior content) all green. |
| 9 | **Gap-fill typed degradation matrix** — exact locked caption per kind (insufficient-evidence terminal, unsafe/danger terminal remediation-only, busy retryable amber, budget-exceeded amber with Admin/Owner-only "Raise the cap") — never a generic error | VERIFIED | `drill-content.tsx:132-179` `renderGapFillItem()` — `'refused'` → locked muted caption per kind; `'unsafe'` → `text-danger` "This guidance was withheld for safety", terminal, no retry button rendered; `'budget_exceeded'` → amber caption + `{item.canRaiseCap && <Link href="/dashboard/connectors">Raise the cap</Link>}`, `canRaiseCap: isAdminOrOwner`. Tests: `drill-panel.test.tsx:567-581` (busy/amber retryable), `:583-597` (grounded_false terminal, no retry), `:599-613` (unsafe/danger terminal, no retry), `:615-640` (budget_exceeded — Analyst sees caption but NOT the link; Admin sees caption AND the link with `href="/dashboard/connectors"`) — all green. |
| 10 | **AnalyzingIndicator reuse (D-12)** — the gap-fill in-flight state reuses the exact exported `AnalyzingIndicator`, never a second spinner | VERIFIED | `ai-explanation-section.tsx:108` `export function AnalyzingIndicator()` (one-line change from private to exported; internal call site at line 231 unaffected). `drill-content.tsx:21` imports it from `@/components/ai/ai-explanation-section`; `:134` renders it verbatim for the `'analyzing'` phase — no second pulsing-dot definition. `drill-panel.test.tsx:524-538` asserts `getByText('Analyzing this finding…')` renders in place of the trigger button. |
| 11 | **Desktop/mobile parity (D-05 divergence lesson closed)** — mobile `Drawer.NestedRoot` renders an IDENTICAL Title + gap-fill row + Description, threading title into the mutation; mobile never imports the desktop `ConfirmModal` | VERIFIED | `drill-panel-mobile.tsx` renders its own `renderGapFillItem()` (duplicated, not imported, matching the file's established Title/Description hardcode precedent) with byte-identical locked copy; `grep -c 'ConfirmModal' drill-panel-mobile.tsx` == 0 (confirmed live). `drill-panel.tsx` (desktop wrapper) renders `<DrillContent idOrCve={effectiveId} onClose={close} />` with NO `renderConfirm` — confirming desktop genuinely uses the `ConfirmModal` default branch, a structurally distinct path from mobile. Title threads into `mutateAsync` on both: `drill-panel.test.tsx:407-421` (desktop) and `drill-panel-mobile.test.tsx:357-374` (mobile) both green; both also prove blank→`undefined` (`:339-357` desktop, `:376-391` mobile). |
| 12 | **Asset-context PII discipline (D-06/Pitfall 5)** — composes from host/product/severity(+cisa_kev/exploit_available) ONLY, no owner/department/assignee field | VERIFIED | `frontend/src/lib/queries/use-vulnerability-detail.ts:12-31` — the real `VulnerabilityDetail` type has NO owner/department/assigned_user field at all (only `asset_hostname`, `affected_product`, `severity`, `cisa_kev`, `exploit_available`, etc.). `grep -iE "owner\|department\|assigned_user\|business_risk"` on `compose-ticket-draft.ts` returns only 2 comment lines explaining the exclusion — zero live field references. |

**Score:** 12/12 code-level/automated must-haves VERIFIED. 1 item (live browser flow) requires human verification — see below.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/ticketing/schemas.py` | `title: str \| None` field (`max_length=255`) + `_title_no_ws_only` validator | VERIFIED | Lines 81, 91-97; `extra="forbid"` (line 71) inherited, not duplicated |
| `backend/app/ticketing/service.py` | `create_tickets()` task_name fallback honoring `request.title` | VERIFIED | Lines 203-211; `create_host_ticket`/`create_remediation_ticket` byte-unchanged (confirmed by direct read + `git diff --stat`) |
| `frontend/src/lib/mutations/use-create-ticket.ts` | `CreateTicketRequest.title?: string` | VERIFIED | Line 23; `mutationFn`'s `JSON.stringify(body)` unchanged |
| `backend/tests/test_ticketing_dispatch.py` | Title schema + dispatch-fallback tests (255-cap, whitespace, omitted, per-provider override + fallback) | VERIFIED | Lines 156-179 (4 schema), 325-369 (2 dispatch × 3 providers); **43/43 passing** (live run) |
| `frontend/src/lib/tickets/compose-ticket-draft.ts` | `composeTicketTitle` + `composeTicketDescription` pure functions | VERIFIED | Exports both + `CacheSection` type; zero React/network imports; zero `business_risk` references |
| `frontend/src/lib/tickets/compose-ticket-draft.test.ts` | Cache-state-permutation unit tests | VERIFIED | 16/16 tests green (live run) |
| `frontend/src/components/vulnerabilities/drill-content.tsx` | title/setTitle state, `composedForId` guard, Title Input, gap-fill row, `renderConfirm` args extended, title threaded into `fireTicket` | VERIFIED | All present and wired (see truths #1, #4-11 above) |
| `frontend/src/components/vulnerabilities/drill-panel-mobile.tsx` | Mirrored Title Input + gap-fill row in mobile `renderConfirm` | VERIFIED | Lines 229-265; `ticket-title-input-mobile` present; zero `ConfirmModal` import |
| `frontend/src/components/ai/ai-explanation-section.tsx` | Exported `AnalyzingIndicator` | VERIFIED | Line 108, `export function AnalyzingIndicator()`, count 1, internal call site unaffected |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `drill-content.tsx` compose-on-open effect | `composeTicketTitle`/`composeTicketDescription` | `useRef<string\|null>` keyed to `v.id ?? idOrCve`, gated on `confirmOpen` | WIRED | `composedForId.current === id` guard (line 372); NOT a `title === ''` check |
| `drill-content.tsx` `fireTicket()` | `createTicket.mutateAsync` body | `title: title \|\| undefined` alongside `description` | WIRED | Line 529; count 1 (no duplicate threading path) |
| `service.py::create_tickets()` | `client.create(task_name, notes, ...)` | `task_name = request.title.strip() if ... else` built name | WIRED | Lines 207-211, 243; call site (`client.create(...)`) unchanged — provider dispatch (`dispatch.py`) untouched |
| gap-fill button `onClick` | `useExplainStream('vuln'\|'remediation-guidance', id).start()` | Existing per-resource SSE trigger, no new endpoint | WIRED | `drill-content.tsx:351-352,503,509`; zero new `backend/app/ai/*.py` files in this phase's diff |
| `drill-panel-mobile.tsx` `renderConfirm` | Threaded `title`/`onTitleChange`/`gapFill` from `drill-content.tsx` | `renderConfirm` args object (same seam `description` uses) | WIRED | `drill-panel-mobile.tsx:178-180,239-243,245-250`; identical descriptor consumed, no duplicated hook logic |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| Composed Description body | `explainSection`/`remediationGuidanceSection`/`prioritizationSection` | `useExplainCache('vuln'\|'remediation-guidance'\|'prioritization', id)` — real `useQuery` hitting `GET /api/v1/ai/explain-{resourceType}/{id}` (`use-explain-cache.ts:36-39`) | Yes — real Phase 24-26 cache-backed endpoint, not a static/hardcoded value | FLOWING |
| Gap-fill append | `explainGapFill.state.data.summary` / `remediationGapFill.state.data.summary` | `useExplainStream(resourceType, id)` — real `fetch()` against `/api/v1/ai/explain-{resourceType}/{id}` SSE stream (`use-explain-stream.ts:70`) | Yes — the same real per-resource engine `AiExplanationSection` already uses | FLOWING |
| Backend title/description fallback | `vuln.severity`, `vuln.cve_id`, `hostname` | Real DB row fetched via `select(Vulnerability).outerjoin(Asset, ...)` (`service.py:174-179`) | Yes — real ORM query, not a static return | FLOWING |

No hollow props or disconnected data sources found. Every artifact that renders/gates on AI-sourced data traces to the real Phase 24-26 cache/stream infrastructure (out of this phase's own scope to re-verify, but confirmed not stubbed).

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Backend ticketing dispatch suite (schema + 255-cap + fallback) | `cd backend && ENCRYPTION_KEY=<fernet> JWT_SECRET_KEY=test python -m pytest tests/test_ticketing_dispatch.py -q` | 43 passed | PASS |
| Frontend targeted Phase 27 suites | `cd frontend && npx vitest run drill-panel compose-ticket-draft ai-explanation-section` | 4 files, 125 passed (drill-panel.test.tsx 31, drill-panel-mobile.test.tsx 16, compose-ticket-draft.test.ts 16, ai-explanation-section.test.tsx 62) | PASS |
| Frontend full regression | `cd frontend && npx vitest run` | 132 files, 889 passed | PASS |
| Frontend typecheck | `cd frontend && npx tsc --noEmit` | Clean, zero errors | PASS |
| Frontend lint (5 touched files) | `npx eslint drill-content.tsx drill-panel-mobile.tsx ai-explanation-section.tsx compose-ticket-draft.ts use-create-ticket.ts` | Clean, zero warnings | PASS |
| Git commit provenance | `git log --oneline --all \| grep -E "65fc823\|574e8e2\|5a76c6c\|f6c4bd7\|a792236\|5431c49\|84d25ee\|146de72\|b413fd9\|f6cdbc3"` | All 10 task commits found | PASS |
| D-05 scope-boundary (zero per-provider diff) | `git diff --stat 65fc823~1 f6cdbc3 -- backend/app/ticketing/dispatch.py backend/app/ticketing/*_client.py` | Empty diff (no output) | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| AID-01 | 27-01, 27-02, 27-03 | An analyst gets an AI-drafted title/description/remediation/asset-context that they edit before shipping (never auto-submitted) | SATISFIED (code+test level) | Truths #1-12 above. REQUIREMENTS.md's `[x]` Complete mark (line 46) and traceability row (line 95, "Complete") are corroborated by direct code+test evidence, not just the checkbox. Only the live-browser render is unproven — see Human Verification. |

**Orphaned requirements check:** REQUIREMENTS.md's traceability table maps exactly AID-01 to Phase 27 — no additional requirement IDs are mapped to this phase that aren't already declared across all 3 plans' frontmatter (`requirements: [AID-01]` in each). No orphans.

### Anti-Patterns Found

None. Scanned every file this phase modified (`schemas.py`, `service.py`, `use-create-ticket.ts`, `compose-ticket-draft.ts`, `drill-content.tsx`, `drill-panel-mobile.tsx`, `ai-explanation-section.tsx`) for `TODO|FIXME|XXX|HACK|PLACEHOLDER`, placeholder-flavored copy, empty implementations (`return null`/`{}`/`[]`, no-op handlers), hardcoded-empty stub patterns, and `console.log`-only implementations — zero hits. Zero `<form>` elements and zero `setTimeout`/`setInterval` in any file that could enable a structural or delayed auto-submit path.

**Informational (non-blocking) documentation-sync notes:**
- `27-VALIDATION.md` frontmatter still reads `nyquist_compliant: false` / `wave_0_complete: false` with all Validation Sign-Off checkboxes unchecked and `**Approval:** pending`. This appears to be a stale pre-execution artifact (matching this project's documented pattern of VALIDATION.md flags not being reconciled post-execution — see Nyquist validation state history for phases 9/10/11/14/15) rather than a real gap: every task in all 3 plans carried a real `<automated>` verify command, and the SUMMARYs document genuine RED→GREEN TDD commit pairs for every task, independently reproduced above (43 + 889 tests green). Recommend reconciling the doc at phase closure; does not block progression.
- `27-UI-SPEC.md`'s Checker Sign-Off section is unchecked (`status: draft`, `**Approval:** pending`). The written Interaction Contract, Copywriting Contract, and Color/Typography tables were independently cross-checked against the actual source (caption placement, locked copy strings, token reuse) and match exactly, including the documented, reasoned deviation (caption-above-Title placement, explained in 27-02-SUMMARY.md's Decisions Made). Not a code gap.

### Human Verification Required

### 1. Live ticket-create flow: open dialog -> pre-fill -> edit -> Create

**Test:** With a live Docker stack and a tenant's own configured Anthropic key, generate cached AI outputs for a finding (explain + remediation guidance), then open its ticket-create dialog as an Analyst.
**Expected:** The Title Input is pre-filled with `[{severity}] {cve} on {hosts}`; the Description Textarea is pre-filled with labeled `Description:`/`Remediation:`/`Asset context:`/`Prioritization:` sections per cache state; every field is freely editable; a "Draft with AI" gap-fill button appears for any missing AI-sourced section and, on click, streams then appends without overwriting; clicking "Create ticket" (and only that click) creates the ticket; switching to a different vulnerability before confirming does not leak the prior draft; with no AI key configured, the dialog still opens with a deterministic Title and an Asset-context-only Description, fully usable.
**Why human:** Requires a live Docker stack + a configured tenant Anthropic key + browser observation — this environment has neither (same class explicitly waived for Phase 24/25/26's own live items). Unlike those three phases, Phase 27 had no tracer-gate checkpoint and therefore no explicit per-phase user "proceed on trust" waiver recorded — this is reported here as an open human_verification item rather than silently treated as accepted debt. Every automated substitute that can be run without a live key/browser (43 backend + 889 frontend tests, `tsc`, `eslint`, git provenance, `git diff --stat` scope-boundary proof) has been run and is green.

### Gaps Summary

No code-level gaps were found. All 12 derived must-haves (3 ROADMAP success criteria plus the supporting PLAN-level truths that back them) resolved to VERIFIED against direct evidence: full source reads of every touched file (not SUMMARY prose), a live backend pytest run (43/43), a live full frontend vitest run (889/889, zero regressions across the entire suite — not just the phase's own new tests), a clean `tsc --noEmit`, a clean `eslint` on every touched file, and a `git diff --stat` proof that zero bytes changed in `dispatch.py` or any provider client across the phase's full commit range (confirming the D-05 scope boundary claim independently of the SUMMARYs).

The phase's status is `human_needed`, not `passed`, solely because the live browser pre-fill/edit/gap-fill/Create flow requires a live Anthropic key and a running stack that this environment does not have. This is the same category of environmental limitation already accepted for Phases 24, 25, and 26 — but because Phase 27 (correctly, per its own plan) had no tracer-gate checkpoint, there is no explicit per-phase user waiver on record for this specific item, so it is surfaced here for a decision rather than silently defaulted to `passed`. If the developer wishes to treat this identically to the 24-26 precedent (accept as tracked debt, consistent with the milestone's established "proceed on trust" pattern), add an override entry to this file's frontmatter:

```yaml
overrides:
  - must_have: "Live ticket-create flow: open dialog -> pre-fill -> edit -> Create"
    reason: "Same waived-class as Phase 24-26 live items — no dev Anthropic key / live stack in this environment; all code-level and unit-test evidence is green"
    accepted_by: "{your name}"
    accepted_at: "{current ISO timestamp}"
```

Then re-run verification to apply.

---

_Verified: 2026-08-01T16:20:00Z_
_Verifier: Claude (gsd-verifier)_
