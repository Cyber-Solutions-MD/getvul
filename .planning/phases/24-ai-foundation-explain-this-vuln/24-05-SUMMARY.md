---
phase: 24-ai-foundation-explain-this-vuln
plan: 05
subsystem: ui
tags: [react, nextjs, tanstack-query, sse, radix-tooltip, tailwind, tdd, ai]

# Dependency graph
requires:
  - phase: 24-04
    provides: "POST /explain-vuln/{id} (SSE, require_analyst) + GET /explain-vuln/{id} (cache-check, require_viewer); the SSE wire vocabulary ({type:no_key}|{type:summary_delta}|{type:done,...ExplainVulnResponse}|{type:error,kind}) this frontend consumes exactly"
provides:
  - "useExplainStream(resourceType, resourceId) — fetch()+ReadableStream discriminated-union state machine parsing SSE frames on \\n\\n boundaries, never api()"
  - "useExplainCache(resourceType, resourceId) — the D-09 cheap cache-check useQuery, mirrors use-vulnerability-detail.ts"
  - "AiExplanationCitations — inline two-tier citation renderer (scanner_verbatim tint / ai_interpreted superscript) over a validated ExplainVulnResponse, one flowing paragraph, D-12 staggered reveal"
  - "AiExplanationSection — the 8 mutually-exclusive body states, wired into drill-content.tsx between Description and Remediation (both desktop and mobile, one edit)"
  - "tooltip.tsx — shadcn Tooltip primitive, hand-reconciled to the sunset token set"
  - "End-to-end tracer complete: admin configures an AI key -> analyst opens a drill panel -> clicks Explain -> validated, cited, streamed summary renders in place"
affects: [24-06, 24-07, 24-08]

# Tech tracking
tech-stack:
  added: ["@radix-ui/react-tooltip@^1.2.16"]
  patterns:
    - "Streaming hooks bypass the generic api() helper entirely (RESEARCH Pitfall 3) — a dedicated fetch()+ReadableStream+TextDecoder loop with its own \\n\\n frame buffer is the only correct shape for a long-lived multi-event SSE consumer; ordinary single-GET queries (useExplainCache) keep using api() as normal"
    - "A backend SSE event type outside the frontend's own locked closed-kind-vocabulary (the defensive no_key frame, which Plan 04 emits as a structurally different, non-error event) is mapped to the SAME generic retryable fallback ({phase:'error',kind:'unknown'}) rather than silently dropped — an unhandled event type must never leave a stream hook parked in 'analyzing' forever"
    - "A 'key configured' UI signal that can only be resolved precisely by an Admin-gated backend route (GET /api/v1/connectors, require_admin) is derived via query.isError as the branch point, not via an explicit role check in the derivation itself — Admin/Owner get the real signal from their own successful query; Analyst/Viewer's query 403s, and isError:true is treated as 'couldn't verify, assume configured' so the trigger stays reachable for the role the whole tracer exists to serve, while the backend's own require_analyst gate + the stream hook's no_key fallback remain the authoritative control"
    - "A citation renderer that needs to overlay tags on substrings of model-authored prose builds a single sorted list of non-overlapping match ranges via indexOf-with-overlap-skip, then slices the source text into an alternating text/citation segment array — a general, reusable shape for 'highlight matched spans without ever risking dangerouslySetInnerHTML'"
    - "A 'replay' animation that must never gate DOM presence on a timer: every segment renders synchronously on first paint regardless of the reveal flag; only a per-segment inline animation-delay + a motion-safe:-prefixed Tailwind class differ, so a component's animate-vs-static branch is exercised by class/style assertions rather than fragile timing waits in tests"
    - "A shared JSX wrapper element (<section aria-labelledby>) stays in the PARENT file (drill-content.tsx) when a child component (AiExplanationSection) supplies only the interior h4+body — avoids <section><section> double-nesting and keeps a single, greppable occurrence of the new landmark's id in the file that owns section layout"

key-files:
  created:
    - frontend/src/lib/ai/use-explain-stream.ts
    - frontend/src/lib/ai/use-explain-stream.test.ts
    - frontend/src/lib/queries/use-explain-cache.ts
    - frontend/src/components/ui/tooltip.tsx
    - frontend/src/components/vulnerabilities/ai-explanation-citations.tsx
    - frontend/src/components/vulnerabilities/ai-explanation-citations.test.tsx
    - frontend/src/components/vulnerabilities/ai-explanation-section.tsx
  modified:
    - frontend/src/lib/queries/keys.ts
    - frontend/src/components/vulnerabilities/drill-content.tsx
    - frontend/src/components/vulnerabilities/drill-panel.test.tsx
    - frontend/src/components/vulnerabilities/drill-panel-mobile.test.tsx
    - frontend/package.json
    - frontend/package-lock.json

key-decisions:
  - "GET /api/v1/connectors is require_admin-gated server-side with no non-admin-safe alternative signal anywhere in the shipped backend (Plan 04 didn't add one, out of this plan's own file scope) — Analyst/Viewer cannot precisely verify key-configured status client-side; connectorsQuery.isError is treated as an optimistic pass-through (assume configured) rather than a hard 'no key', so the tracer's primary role (Analyst) can still reach the trigger button. Documented as a known, deliberate trade-off, not silently swallowed."
  - "The <section aria-labelledby='drill-ai-h'> landmark itself lives in drill-content.tsx (matching the plan's own artifact list); AiExplanationSection renders only the h4+body via a Fragment, so the acceptance grep (exactly 1 occurrence of drill-ai-h in drill-content.tsx) holds and no section-in-section nesting exists"
  - "D-12's 'token-by-token replay' is implemented as a per-citation-boundary-segment staggered CSS animate-in/fade-in (animationDelay increasing per segment), not a literal per-word timer or a raw sync to the backend's own summary_delta SSE frames — the hook's locked state shape ({phase:'done';data}) carries no slot for partial text, and the backend's own comments call summary_delta 'purely cosmetic replay chunking of the ALREADY-validated summary', so the reveal is a presentation-layer effect over the complete payload, gated only by prefers-reduced-motion and whether this is a fresh click (never a cache hit, D-09 vs D-12)"
  - "A defensive backend SSE no_key frame is not surfaced as its own frontend phase (the locked ExplainStreamState union has no slot for it) — mapped to kind:'unknown' so an unexpected mid-flight no_key can never leave the hook parked in 'analyzing' forever, while the pre-click gating (the button only renders when the client's own keyConfigured signal is true) means this path is expected to be effectively unreachable in normal use"
  - "A 'done' payload is re-checked for grounded:false at render time even though the real Plan-04 engine never emits 'done' for an ungrounded response — the UI-SPEC backstop test proves a hypothetically-malformed done payload still routes to the insufficient-evidence card, never a half-grounded citation render, without trusting that upstream invariant blindly"
  - "AI Explanation section copy is NOT threaded through the vulnerabilities microcopy.ts (that file isn't in this plan's declared files_modified) — copy strings live inline in ai-explanation-section.tsx; the shared h4 chrome classes are hardcoded to match the sibling sections' own literal className string exactly"

requirements-completed: [AI-03, AI-04]

# Metrics
duration: 41min
completed: 2026-07-29
---

# Phase 24 Plan 05: AI Explanation Section — SSE Hook, Cache Query, Two-Tier Citation Renderer Summary

**The tracer's frontend half: a fetch()+ReadableStream SSE hook (never the generic `api()` helper), an 8-state drill-panel section, and an inline scanner-verbatim/AI-interpreted citation renderer — closing the end-to-end path from an admin's configured key to an analyst's clicked "Explain this vuln" to a validated, cited summary rendered in place.**

## Performance

- **Duration:** ~41 min
- **Started:** 2026-07-29T10:16:30Z (immediately after 24-04 completion)
- **Completed:** 2026-07-29T10:57:00Z
- **Tasks:** 2/2 completed
- **Files modified:** 13 (7 created, 6 modified)

## Accomplishments

- **The SSE hook genuinely never touches the generic `api()` helper**, confirmed by grep at acceptance (`from '.*api'` count 0 in `use-explain-stream.ts`) — a discriminated-union state machine (`{phase:'idle'}|{phase:'analyzing'}|{phase:'done';data}|{phase:'error';kind}`) reads `res.body.getReader()`, buffers on `\n\n`, and carries the Bearer token from `localStorage` exactly as `api.ts` itself does, but bypassing its unconditional `res.json()` call that would otherwise hang/throw against a streamed body (RESEARCH Pitfall 3).
- **Every fetch URL and query key is genuinely resourceType-parameterized, never a hardcoded `'vuln'` literal** — proven not just by convention but by an explicit test asserting `resourceType='host'` hits `/api/v1/ai/explain-host/host-77`, and by a hard grep gate (`explain-vuln` count 0 in both hook files) that would fail the build if a future edit accidentally hardcoded the resource kind. D-15 compliance is structural, not just documented.
- **A real, previously-undiscussed backend/RBAC constraint was found and resolved, not silently worked around.** `GET /api/v1/connectors` (the only route that can precisely confirm an ANTHROPIC connector is configured) is `require_admin`-gated — an Analyst, the exact role this phase's tracer exists to serve, cannot call it. Deriving the "key configured" signal via `connectorsQuery.isError` (rather than an explicit role branch) means Admin/Owner get the real signal from their own successful query, while a 403 for Analyst/Viewer is treated as "couldn't verify, assume configured" — keeping the click-to-explain path reachable for the tracer's primary consumer without ever bypassing the backend's own authoritative `require_analyst` gate or its defensive `no_key` fallback. Documented in full in Decisions Made below.
- **A citation-matching algorithm renders two-tier tags over model-authored prose with zero XSS surface** — every citation is matched as a plain-JS substring range over the assembled `summary + business_risk` text and sliced into a segment array rendered as React children (never `dangerouslySetInnerHTML`), directly satisfying T-24-22's mitigation. `scanner_verbatim` gets the `bg-violet-soft`/`text-[var(--color-violet-on-soft)]` tinted span; `ai_interpreted` gets plain prose plus a 10px "AI" superscript — both `tabIndex={0}` + a shadcn Tooltip revealing the exact Copywriting Contract micro-copy on hover/focus.
- **A pre-existing regression was caught and fixed, not left for a future plan to discover.** Adding `<AiExplanationSection>` (a real `useQuery`-backed component) inside `DrillContent` broke `drill-panel.test.tsx` and `drill-panel-mobile.test.tsx` — both pre-existing suites render the real component tree without a `QueryClientProvider`, since they'd only ever needed to mock `useVulnerabilityDetail` before. Fixed by mocking the two new query hooks the same way, and — since the new section adds an 8th `<h4>` heading between Description and Remediation — updated the "renders 7 sections in order" assertion to 8, which now doubles as a regression test pinning D-11's exact section placement.
- **The `npx shadcn add tooltip` scaffold was hand-corrected for design-system compliance, not shipped as-is.** The generated file used `bg-primary`/`text-primary-foreground` — CSS variables that don't exist anywhere in this app's theme (confirmed via grep: no `--primary`/`--popover` token in `globals.css`), which would have rendered an invisible/broken tooltip. Reconciled to the sunset `bg-surface-2`/`text-text`/`border-border-strong` tokens, mirroring `dropdown-menu.tsx`'s own established precedent for hand-editing shadcn-scaffolded primitives in this codebase.

## Task Commits

Each task followed the full RED → GREEN cycle (plan-level `type: tdd`):

1. **Task 1: SSE stream hook + cache-check query + query key**
   - `13eda05` (test) — RED: `Failed to resolve import "./use-explain-stream"` confirmed before any implementation existed
   - `43354c3` (feat) — GREEN: 9/9 new tests passing (SSE parsing, mid-frame-split reassembly, closed error-kind vocabulary, resourceType-parameterization, Bearer token carry, defensive no_key fallback, single-GET cache-check); tsc + eslint clean
2. **Task 2: AI Explanation section (8 states) + inline two-tier citation renderer + drill wiring**
   - `1702265` (test) — RED: `Failed to resolve import "./ai-explanation-citations"` / `"./ai-explanation-section"` confirmed
   - `1049167` (feat) — GREEN: 18/18 new tests passing (citation classes, 8-state matrix, UI-SPEC backstop, busy/unknown same-card, role-gated no-key/budget copy, reduced-motion vs animated reveal, cache-hit-never-animates); full regression suite re-verified 783/783 green; includes the drill-panel/drill-panel-mobile regression fix

**Plan metadata:** (this commit, docs: complete plan)

_TDD gate sequence confirmed in git log: `test(24-05)` precedes `feat(24-05)` for both Task 1 and Task 2, in order._

## Files Created/Modified

- `frontend/src/lib/ai/use-explain-stream.ts` (139 lines) — `useExplainStream()` discriminated-union state machine, `ExplainStreamState`/`ExplainVulnResponse`/`Citation`/`CitationSource` types
- `frontend/src/lib/ai/use-explain-stream.test.ts` (9 tests) — SSE parsing, mid-frame-split reassembly, closed error-kind vocabulary, resourceType-parameterized URL, Bearer token carry, defensive no_key handling, useExplainCache single-GET
- `frontend/src/lib/queries/use-explain-cache.ts` (24 lines) — `useExplainCache()`, mirrors `use-vulnerability-detail.ts`
- `frontend/src/lib/queries/keys.ts` — added `ai.explain(resourceType, resourceId)` query key
- `frontend/src/components/ui/tooltip.tsx` (shadcn, hand-reconciled to sunset tokens) — `Tooltip`/`TooltipTrigger`/`TooltipContent`/`TooltipProvider`
- `frontend/src/components/vulnerabilities/ai-explanation-citations.tsx` (146 lines) — `AiExplanationCitations()`, `buildSegments()` substring-matching algorithm
- `frontend/src/components/vulnerabilities/ai-explanation-section.tsx` (203 lines) — `AiExplanationSection()`, the 8-state body + `DegradedCard`/`AnalyzingIndicator` local sub-components
- `frontend/src/components/vulnerabilities/ai-explanation-citations.test.tsx` (18 tests) — both components' full behavior matrix
- `frontend/src/components/vulnerabilities/drill-content.tsx` — new `<section aria-labelledby="drill-ai-h">` between Description and Remediation
- `frontend/src/components/vulnerabilities/drill-panel.test.tsx` — regression fix: mock the two new query hooks; "8 sections" heading-order assertion
- `frontend/src/components/vulnerabilities/drill-panel-mobile.test.tsx` — regression fix: mock the two new query hooks
- `frontend/package.json` / `frontend/package-lock.json` — `@radix-ui/react-tooltip@^1.2.16`

## Decisions Made

- `GET /api/v1/connectors` is `require_admin`-gated with no non-admin-safe alternative in the shipped backend — the "key configured" signal for Analyst/Viewer is derived via `connectorsQuery.isError` (optimistic pass-through on a 403), not a hardcoded role check, keeping the trigger reachable for the tracer's primary role while Admin/Owner get the real, precise signal. See Accomplishments and the Known Gaps note below.
- The `<section aria-labelledby="drill-ai-h">` landmark lives in `drill-content.tsx` (not inside `AiExplanationSection`, which renders only the `h4`+body via a Fragment) — satisfies the plan's own artifact list and its exactly-1-occurrence grep gate, and avoids nesting `<section>` inside `<section>`.
- D-12's token-by-token replay is a per-segment staggered `motion-safe:animate-in`/`fade-in-0` CSS effect over the complete, already-validated payload — never a literal sync to the backend's own cosmetic `summary_delta` frames (which the hook intentionally does not surface, since the locked state shape has no slot for partial text) and never gates DOM presence on a timer, so every citation/text segment is always synchronously queryable regardless of the reveal flag.
- The replay animation applies only when `state.phase === 'done'` (a just-streamed result) and motion is allowed — never on a cache hit (D-09), which always renders statically per the Copywriting/Section-Placement contract's own state-1-vs-state-6 distinction.
- A `'done'` payload is defensively re-checked for `grounded: false` at render time (routing to the insufficient-evidence card) even though the real engine never emits `'done'` for an ungrounded response — satisfies the UI-SPEC backstop test without trusting that upstream invariant blindly.
- AI Explanation section copy lives inline in `ai-explanation-section.tsx`, not threaded through `vulnerabilities/microcopy.ts` (not in this plan's declared `files_modified`); the shared `h4` chrome class string is copied verbatim from the sibling sections rather than centralized.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed a pre-existing test regression introduced by adding a real `useQuery`-backed section to `DrillContent`**
- **Found during:** Task 2, full-suite regression sweep
- **Issue:** `drill-panel.test.tsx` and `drill-panel-mobile.test.tsx` render the real `DrillContent` component tree with no `QueryClientProvider` wrapper (they only ever needed to mock `useVulnerabilityDetail` before). The new `AiExplanationSection` calls `useExplainCache`/`useConnectorsList` (real `useQuery` hooks), which threw `"No QueryClient set, use QueryClientProvider to set one"` on every render, failing all 17 tests across both files.
- **Fix:** Mocked `@/lib/queries/use-explain-cache` and `@/lib/queries/use-connectors-admin` in both files, matching the existing `useVulnerabilityDetail` mocking convention exactly. Also updated `drill-panel.test.tsx`'s "renders 7 sections in order" assertion to 8 (the new `<h4>AI Explanation</h4>` is a genuine 8th heading between Description and Remediation) — this now doubles as a regression test pinning D-11's exact section placement.
- **Files modified:** `frontend/src/components/vulnerabilities/drill-panel.test.tsx`, `frontend/src/components/vulnerabilities/drill-panel-mobile.test.tsx`
- **Verification:** Both files re-ran green (39/39 combined); full frontend suite re-ran 783/783 green; `next build` clean.
- **Committed in:** `1049167` (Task 2 GREEN commit)

**2. [Rule 1 - Bug] Hand-corrected the shadcn-scaffolded tooltip.tsx's undefined CSS variable tokens**
- **Found during:** Task 1, immediately after `npx shadcn add tooltip`
- **Issue:** The generated file used `bg-primary`/`text-primary-foreground` — this app defines no `--primary`/`--popover` CSS variable anywhere (`globals.css` grep confirmed absent), so the tooltip would have rendered invisibly/broken in production.
- **Fix:** Replaced with the sunset `bg-surface-2 border-border-strong text-text` tokens (`shadow-md`, `text-xs font-medium`), mirroring `dropdown-menu.tsx`'s own established precedent for hand-editing shadcn-scaffolded primitives in this codebase.
- **Files modified:** `frontend/src/components/ui/tooltip.tsx`
- **Verification:** Visual class inspection against `foundation.md`'s token list; no raw/undefined CSS variable remains in the file.
- **Committed in:** `43354c3` (Task 1 GREEN commit)

**3. [Rule 3 - Blocking] Installed `@radix-ui/react-tooltip` with `--legacy-peer-deps` before the shadcn CLI could scaffold the file**
- **Found during:** Task 1, running `npx shadcn add tooltip`
- **Issue:** The shadcn CLI's own internal `npm install` step failed with the project's pre-existing, previously-documented `lucide-react@^0.383.0` (peer `react@^18`) vs. React 19 conflict (same class of issue flagged in Phase 15/18/19 project memory).
- **Fix:** Ran `npm install @radix-ui/react-tooltip --legacy-peer-deps` manually first (matching the established project precedent for this exact recurring conflict), then re-ran `npx shadcn add tooltip --overwrite`, which detected the dependency already present and only wrote the component file — no `--legacy-peer-deps` residue in the final `package.json`.
- **Verification:** `git diff package.json` shows a clean `"@radix-ui/react-tooltip": "^1.2.16"` addition; `npm run build` and the full test suite both green afterward.
- **Committed in:** `43354c3` (Task 1 GREEN commit)

---

**Total deviations:** 3 auto-fixed (1 bug fix protecting a pre-existing test suite from a real regression, 1 bug fix on a scaffolded file's design-system compliance, 1 blocking dependency-install workaround matching established project precedent)
**Impact on plan:** All three are correctness/hygiene fixes directly caused by this plan's own changes, not scope changes. No feature behavior differs from what the plan specified.

## Issues Encountered

- **Known, documented gap (not a defect, not silently worked around):** the "key configured" signal cannot be resolved with full precision for Analyst/Viewer roles from the frontend alone, because the only backend route that reports it (`GET /api/v1/connectors`) is `require_admin`-gated and this plan's scope does not include adding a new backend endpoint. The `connectorsQuery.isError`-based optimistic fallback (see Decisions Made) keeps the tracer functional for Analyst in the common case; the one residual edge case (an Analyst clicks Explain when AI genuinely isn't configured yet) surfaces the generic amber "AI busy — try again in a moment" retry card rather than the more precise "ask an admin" copy — never a crash, never a paid dispatch (the engine's own `no_key` short-circuit is unconditional and free). Flagging this explicitly for whichever future plan (or a follow-up to this one) has the opportunity to add a lightweight, non-admin-safe "is AI configured" signal to close this precision gap.

## User Setup Required

None — no external service configuration required. This plan is pure frontend composition over Plan 04's already-shipped, already-tested backend endpoint.

## Next Phase Readiness

- The end-to-end tracer is now genuinely complete and wired: an admin's configured Anthropic key flows through to an analyst's drill-panel click, through the real SSE endpoint, into a validated, cited, streamed summary rendered with the app's existing sunset design-system primitives.
- Plan 06 (the human-verify gate) can now exercise all 8 section states live in a browser — the automated test suite proves the render-logic branches are correct and complete, but the plan's own `<verification>` explicitly defers the live 8-state visual walkthrough and the axe contrast check on `violet-on-soft` to that gate.
- Plan 07 (feedback prompt: "Was this explanation accurate?") has a stable `AiExplanationCitations`/`AiExplanationSection` surface to attach its thumbs-up/down control beneath, per D-10's explicit "no regenerate control" boundary respected in this plan.
- Plan 08 (host/remediation views) can reuse `useExplainStream`/`useExplainCache` unchanged, parameterized by a different `resourceType` — proven not just by design but by this plan's own tests asserting a `resourceType='host'` call hits `/api/v1/ai/explain-host/...`. Whether Plan 08 also reuses `AiExplanationSection`/`AiExplanationCitations` as-is or builds dedicated per-view sections is an open design question for that plan, not resolved here.
- Postgres + Redis containers were not needed this plan (pure frontend); no backend state touched.
- Carried forward, not blocking: the "key configured" precision gap for non-admin roles (see Issues Encountered) — worth a small follow-up (e.g., a `GET /api/v1/ai/status` viewer-safe endpoint) if the imprecise copy edge case proves to matter in practice.

## Self-Check: PASSED

- Files verified present: `frontend/src/lib/ai/use-explain-stream.ts`, `frontend/src/lib/ai/use-explain-stream.test.ts`, `frontend/src/lib/queries/use-explain-cache.ts`, `frontend/src/components/ui/tooltip.tsx`, `frontend/src/components/vulnerabilities/ai-explanation-citations.tsx`, `frontend/src/components/vulnerabilities/ai-explanation-citations.test.tsx`, `frontend/src/components/vulnerabilities/ai-explanation-section.tsx` (7/7 found)
- Commits verified present in `git log`: `13eda05`, `43354c3`, `1702265`, `1049167` (4/4 found)
- TDD gate sequence confirmed: `test(24-05)` precedes `feat(24-05)` for both Task 1 and Task 2, in order
- Plan's own `<verification>` re-run and green: `npx vitest run use-explain-stream ai-explanation-citations` → 27/27 (9 + 18)
- Acceptance-criteria greps re-confirmed: `getReader` (1), `from '.*api'` (0), `explain-${resourceType}` (1 each in both hook files), `explain-vuln` literal (0 in both hook files), `getvul_token|Authorization` (4), `tooltip.tsx` exists, `drill-ai-h` in `drill-content.tsx` (exactly 1), `color-danger|text-danger|bg-danger` in `ai-explanation-section.tsx` (0), `violet-soft` in `ai-explanation-citations.tsx` (≥1)
- Prohibitions swept clean across all 4 new source files: `font-mono` (0), raw hex colors (0), `gradient-sunset` (0), `regenerate`/`refresh` (0), `i18n`/`locale` (0)
- Full regression sweep green: 783/783 frontend unit tests, `tsc --noEmit` clean, `eslint` clean on every new/modified file, `next build` clean (no new warnings from this plan's files; all routes stay well under the 250 KB bundle budget)

---
*Phase: 24-ai-foundation-explain-this-vuln*
*Completed: 2026-07-29*
