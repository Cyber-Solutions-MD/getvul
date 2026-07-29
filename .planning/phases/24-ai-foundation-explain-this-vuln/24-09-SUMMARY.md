---
phase: 24-ai-foundation-explain-this-vuln
plan: 09
subsystem: ui
tags: [react, nextjs, tanstack-query, tdd, ai, ticketing]

# Dependency graph
requires:
  - phase: 24-05
    provides: "AiExplanationSection (8-state body) + AiExplanationCitations (two-tier citation renderer) + useExplainStream/useExplainCache, already fully generalized over resourceType/resourceId -- this plan relocates and mounts them, it does not rebuild the state machine"
  - phase: 24-08
    provides: "POST/GET /explain-host/{asset_id} (UUID-keyed) and /explain-remediation/{cve_id} (CVE-STRING-keyed, D-16 cross-asset-CVE grounding) -- this plan's two new mount sites call these routes indirectly via the unmodified Plan-05 hooks"
provides:
  - "components/ai/ai-explanation-section.tsx + ai-explanation-citations.tsx -- the shared, view-agnostic home for the AI Explanation section (D-15 complete: one component drives vuln/host/remediation, no per-view duplicate)"
  - "AiExplanationSection headingId prop (optional, defaults to 'drill-ai-h') -- lets >1 mount coexist on one page without a duplicate-DOM-id collision"
  - "host mount: assets/[id]/page.tsx renders resourceType='host' in the main column between the vuln list and the remediation timeline"
  - "remediation mount: remediation-timeline.tsx renders resourceType='remediation' once per ticket row, keyed on that row's own representative cve_id"
  - "backend list_tickets() now returns a representative cve_id per ticket group (MIN aggregate, mirrors the existing remediation_action/affected_product convention) -- closes the gap Plan 08's own SUMMARY flagged as needed for this plan's remediation resourceId"
affects: [25, 26, 27]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A shared, mount-more-than-once-per-page component must not hardcode an internal DOM id -- AiExplanationSection's h4 id became a headingId prop (default 'drill-ai-h' preserves the vuln view byte-for-byte) the moment a second real mount (host) landed on the same page as a to-be-added third (remediation, N-per-page); discovered and fixed within this plan, not deferred"
    - "A grouped/aggregated list endpoint (list_tickets(), one row per external ticket, potentially >1 underlying Vulnerability) exposes a representative value for a per-CVE-keyed downstream feature via the SAME func.min(...) MIN-aggregate convention already used in that exact query for remediation_action/affected_product -- not a new query shape, not a new table"
    - "A page/list component that mounts a shared, hook-heavy component (5 internal hooks incl. 2 real useQuery calls) is tested by stubbing the shared component itself (matching the file's own existing DrillPanel-stub precedent), asserting only the mount's own resourceType/resourceId/headingId wiring -- the component's internal 8-state matrix and role-gating are proven exhaustively, once, in the component's own test file across all three resourceTypes, not re-proven at every mount site"
    - "Cross-component/cross-hook wiring for a NEW resourceType is verified via prop-forwarding assertions (mockUseExplainStream/mockUseExplainCache called with the exact resourceType/resourceId) composing with an ALREADY-proven hook-internal fetch-URL test (Plan 05's use-explain-stream.test.ts), rather than re-mocking fetch/SSE end-to-end a second time for the same URL-construction logic"

key-files:
  created:
    - frontend/src/components/ai/ai-explanation-section.tsx
    - frontend/src/components/ai/ai-explanation-citations.tsx
    - frontend/src/components/ai/ai-explanation-section.test.tsx
    - frontend/src/components/ai/ai-explanation-citations.test.tsx
  modified:
    - frontend/src/components/vulnerabilities/drill-content.tsx
    - frontend/src/app/(authed)/dashboard/assets/[id]/page.tsx
    - frontend/src/app/(authed)/dashboard/assets/[id]/page.test.tsx
    - frontend/src/components/assets/remediation-timeline.tsx
    - frontend/src/components/assets/remediation-timeline.test.tsx
    - frontend/src/lib/queries/use-asset-remediations.ts
    - backend/app/ticketing/service.py
    - backend/tests/test_tickets_asset_id_filter.py

key-decisions:
  - "AiExplanationSection's internal h4 id is now a headingId prop (default 'drill-ai-h') instead of a hardcoded literal -- the vuln view (drill-content.tsx) needed zero changes since its default matches exactly; host and every remediation-row mount pass their own unique id"
  - "The remediation surface mounts ONE AiExplanationSection PER ticket row (not once for the whole timeline) -- list_tickets() groups by external_ticket_url, and a single ticket group can span >1 Vulnerability/CVE, so there is no single canonical 'the CVE' for the whole list; each row gets its own representative cve_id and its own section, gated off entirely when that row's cve_id is null"
  - "list_tickets()'s response gained a representative cve_id field via func.min(Vulnerability.cve_id), an additive/backward-compatible field on an already-existing, already-authenticated, already-tenant-scoped endpoint -- not a new query, table, or trust boundary (Rule 2 auto-add, not an architectural change)"
  - "The host AI Explanation section is placed between 'Vulnerabilities on this host' and 'Remediation timeline' in the main column, mirroring the vuln drill's own Description -> AI Explanation -> Remediation placement rationale (D-11 analog: synthesize raw findings before remediation guidance)"
  - "Both new mount-site tests stub AiExplanationSection itself (matching the existing DrillPanel-stub precedent in page.test.tsx) rather than re-mocking its 5 internal hooks -- the component's own 8-state matrix and three-view parity are proven exhaustively once in ai-explanation-section.test.tsx, not duplicated at every mount site"

requirements-completed: [AI-04]

# Metrics
duration: 29min
completed: 2026-07-29
---

# Phase 24 Plan 09: Generalized AI Explanation Section — Host + Remediation Mounts Summary

**Moved the already-generalized AI Explanation section to a shared `components/ai/` home and mounted it on the asset-detail (host) page and per-row on the remediation timeline, closing D-15's "all three views" — including a backend fix to give the remediation view a real CVE-string identity it didn't have.**

## Performance

- **Duration:** ~29 min
- **Started:** 2026-07-29T12:29:00Z (immediately after 24-08 completion)
- **Completed:** 2026-07-29T12:58:00Z
- **Tasks:** 2/2 completed
- **Files modified:** 13 (4 created, 9 modified — 2 of the 9 are backend)

## Accomplishments

- **"Explain this" now ships on all three drill views (vuln/host/remediation), driven by one literally-unmodified-in-logic shared component.** `AiExplanationSection`/`AiExplanationCitations` moved from `components/vulnerabilities/` to `components/ai/` with zero behavior change — they were already fully generalized over `resourceType`/`resourceId` per Plan 05. A new `it.each(['vuln','host','remediation'])` parity suite proves identical chrome, copy, and role-gating across all three, and a prop-forwarding suite proves the component never hardcodes a resource-kind literal, composing with Plan 05's already-proven hook-level fetch-URL construction rather than re-testing it.
- **Found and fixed a real duplicate-DOM-id bug before it ever reached the DOM, not after.** `AiExplanationSection` hardcoded `id="drill-ai-h"` on its internal heading. The moment this plan mounts a host instance on `/assets/[id]` alongside a to-be-added remediation instance on the SAME page, two (or more, for N ticket rows) elements would share one id — invalid HTML, broken `aria-labelledby` resolution. Fixed with an optional `headingId` prop defaulting to `'drill-ai-h'`, so the vuln view (`drill-content.tsx`) needed zero changes while every new mount passes its own unique id.
- **Found and closed a genuine backend gap the prior plan's own SUMMARY had explicitly flagged, not worked around with a fake id.** The remediation surface's backend route (`/explain-remediation/{cve_id}`, Plan 08) is CVE-string-keyed, but `RemediationTimeline`'s `RemediationTicket` type — sourced from `list_tickets()`, which groups rows by `external_ticket_url` and can span more than one `Vulnerability`/CVE per group — carried no CVE identifier at all. Added a representative `cve_id` via `func.min(Vulnerability.cve_id)`, mirroring that exact query's own existing `remediation_action`/`affected_product` MIN-aggregate convention (not a new query shape, not a new table) — proven by a new backend test and zero regressions across 92 backend ticketing/AI tests.
- **The remediation view mounts per ticket row, not once for the whole list, matching the real data shape.** Since a single ticket group can legitimately span multiple CVEs, there is no single canonical "the remediation" for the page — each row gets its own `AiExplanationSection resourceType="remediation" resourceId={row.cve_id}`, gated off entirely (no broken affordance) when a row's representative `cve_id` is null.
- **Test design avoids duplicating already-exhaustive coverage.** Both new mount-site tests (`page.test.tsx`, `remediation-timeline.test.tsx`) stub `AiExplanationSection` itself — the same pattern the asset-detail page already uses for `DrillPanel` — asserting only that each mount wires the right `resourceType`/`resourceId`/`headingId`. The component's own 8-state matrix and cross-resourceType role-gating are proven once, exhaustively, in `ai-explanation-section.test.tsx`.

## Task Commits

Each task followed the full RED → GREEN cycle (plan-level `type: tdd`):

1. **Task 1: Generalize the AI Explanation section to a shared, view-agnostic component**
   - `f5c0ff1` (test) — RED: two new test files at `components/ai/` fail with `Failed to resolve import` (the shared implementation files don't exist yet at that path)
   - `0e12339` (feat) — GREEN: `git mv` both component files to `components/ai/`, updated the cross-directory `ai-feedback-control` import and `drill-content.tsx`'s import path; 60/60 targeted tests green, 804/804 full suite green, tsc + eslint clean
2. **Task 2: Mount the section on the host (asset-detail) and remediation surfaces**
   - `c452397` (test) — RED: new/extended tests for the missing backend `cve_id` field, the not-yet-supported `headingId` prop, and the two not-yet-mounted surfaces all fail against the current implementation
   - `a93daf0` (feat) — GREEN: backend `cve_id` MIN-aggregate, `headingId` prop, host mount in `assets/[id]/page.tsx`, per-row remediation mount in `remediation-timeline.tsx`; 810/810 full frontend suite green, 92/92 backend ticketing/AI regression tests green, tsc + eslint + ruff + ruff format clean, `next build` clean (`/dashboard/assets/[id]` 187 kB, well under the 250 KB budget)

**Plan metadata:** (this commit, docs: complete plan)

_TDD gate sequence confirmed in git log: `test(24-09)` precedes `feat(24-09)` for both Task 1 and Task 2, in order._

## Files Created/Modified

- `frontend/src/components/ai/ai-explanation-section.tsx` (moved + `headingId` prop added) — the view-agnostic 8-state AI Explanation section, now the single shared home for all three resourceTypes
- `frontend/src/components/ai/ai-explanation-citations.tsx` (moved, unchanged) — the two-tier citation renderer, reused verbatim
- `frontend/src/components/ai/ai-explanation-section.test.tsx` (new, 34 tests) — relocated 8-state matrix + three-view parity + resourceType/resourceId prop-forwarding + query-key-collision + headingId tests
- `frontend/src/components/ai/ai-explanation-citations.test.tsx` (new, 4 tests) — relocated pure-render citation tests, split out of the former combined file
- `frontend/src/components/vulnerabilities/drill-content.tsx` — import path updated to the new shared location
- `frontend/src/app/(authed)/dashboard/assets/[id]/page.tsx` — mounts `AiExplanationSection resourceType="host"` between the vuln list and remediation timeline
- `frontend/src/app/(authed)/dashboard/assets/[id]/page.test.tsx` — stubs the shared component, asserts the host mount's resourceType/resourceId/headingId
- `frontend/src/components/assets/remediation-timeline.tsx` — mounts one `AiExplanationSection resourceType="remediation"` per ticket row, gated on a non-null `cve_id`
- `frontend/src/components/assets/remediation-timeline.test.tsx` — asserts per-row mount + the null-cve_id omission guard
- `frontend/src/lib/queries/use-asset-remediations.ts` — `RemediationTicket.cve_id: string | null` added
- `backend/app/ticketing/service.py` (+12 lines) — `list_tickets()`'s `details_q` gains `func.min(Vulnerability.cve_id).label("cve_id")`; the response dict threads it through
- `backend/tests/test_tickets_asset_id_filter.py` (+1 test) — asserts the representative `cve_id` appears in the ticket-list response

## Decisions Made

- `AiExplanationSection` gained an optional `headingId` prop (default `'drill-ai-h'`) instead of a hardcoded internal DOM id — see Key Decisions in frontmatter.
- The remediation surface mounts per ticket row (not once for the whole timeline) since a ticket group can span >1 CVE — see Key Decisions in frontmatter.
- `list_tickets()`'s new `cve_id` field is a representative MIN aggregate, additive and backward-compatible on an already-existing endpoint — see Key Decisions in frontmatter.
- The host section sits between "Vulnerabilities on this host" and "Remediation timeline" (D-11 placement analog), as a bare `<section>` with no bordered-card restyle — reuses the exact chrome verified for the vuln view rather than inventing per-surface styling.
- Both new mount-site tests stub the shared component rather than its 5 internal hooks, avoiding duplicate coverage of the already-exhaustive component-level test suite.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed a duplicate-DOM-id collision the plan's own dual mounting would introduce**
- **Found during:** Task 2, while designing the host + remediation mount sites
- **Issue:** `AiExplanationSection` hardcoded `<h4 id="drill-ai-h">`. This plan mounts the SAME component on the host page AND (per ticket row, potentially N times) on the remediation timeline, both of which render on the same `/assets/[id]` page as the vuln view's own drill panel — every additional mount beyond the first would share the identical DOM id, invalid HTML and a broken `aria-labelledby` reference for every instance after the first.
- **Fix:** Added an optional `headingId` prop (default `'drill-ai-h'`, preserving the vuln view unchanged) and used it on the `<h4>`. The host mount passes `"ai-explanation-h-host"`; each remediation row passes `` `ai-explanation-h-remediation-${t.id}` ``.
- **Files modified:** `frontend/src/components/ai/ai-explanation-section.tsx`, `frontend/src/app/(authed)/dashboard/assets/[id]/page.tsx`, `frontend/src/components/assets/remediation-timeline.tsx`, `frontend/src/components/ai/ai-explanation-section.test.tsx`
- **Verification:** New tests assert the default id renders for a bare mount and a custom id renders (and the default id is absent) when `headingId` is supplied; full suite green.
- **Committed in:** `c452397` (test) / `a93daf0` (feat), Task 2

**2. [Rule 2 - Missing Critical] Added a representative `cve_id` field to the ticket-list response, required to wire the remediation view's resourceId at all**
- **Found during:** Task 2, while designing the remediation mount
- **Issue:** `/explain-remediation/{cve_id}` (Plan 08) is CVE-string-keyed, but `RemediationTicket` (the frontend contract for `GET /api/v1/tickets?asset_id=`, which `RemediationTimeline` renders) carried no CVE identifier anywhere — the backend's `list_tickets()` groups rows by `external_ticket_url` (a group can legitimately span >1 `Vulnerability`/CVE), so there was no existing single "the CVE" to reuse. Without this field, Task 2's own explicit deliverable (wiring a real remediation resourceId) could not be completed at all. Plan 08's own SUMMARY had already flagged this exact need: "24-09's frontend integration must derive/pass a CVE ID string."
- **Fix:** Added `func.min(Vulnerability.cve_id).label("cve_id")` to `list_tickets()`'s existing `details_q` aggregate (the SAME MIN-aggregate pattern already used in that query for `remediation_action`/`affected_product`) and threaded it into the response dict and the frontend `RemediationTicket` type. Purely additive — no new query shape, no new table, no breaking change to the existing response contract.
- **Files modified:** `backend/app/ticketing/service.py`, `backend/tests/test_tickets_asset_id_filter.py`, `frontend/src/lib/queries/use-asset-remediations.ts`
- **Verification:** New backend test seeds one asset/vuln/ticket and asserts the response's `cve_id` matches the seeded CVE; 9/9 `test_tickets_asset_id_filter.py` + `test_list_tickets_reshape.py` green, 92/92 broader backend ticketing/AI regression green, ruff + ruff format clean, direct `mypy` on the touched file shows zero errors attributable to `cve_id` (see Issues Encountered for the unrelated pre-existing baseline-drift noise).
- **Committed in:** `c452397` (test) / `a93daf0` (feat), Task 2

---

**Total deviations:** 2 auto-fixed (1 bug fix preventing a duplicate-DOM-id collision this plan's own mounting work would otherwise introduce, 1 missing-critical-functionality fix closing a backend gap without which the remediation view's core deliverable could not be wired at all).
**Impact on plan:** Both fixes are correctness requirements directly caused by this plan's own mounting work, scoped narrowly (an optional prop with a backward-compatible default; one additive MIN-aggregate field mirroring an existing pattern in the same query). No architectural change, no new table, no new service layer, no scope creep beyond what Task 2's own stated deliverable required.

## Issues Encountered

- **Re-observed the same pre-existing `mypy-baseline.txt` note-line-number-drift artifact Plan 08 already root-caused (not a new issue, not fixed).** `mypy app/ | mypy-baseline filter --allow-unsynced` reported `new: 3 / fixed: 3` (all `note`-category) after this plan's backend change. Confirmed unrelated: the 3 notes are in `app/auth/dependencies.py` (missing-stub hints for `python-jose`), a file this plan never touches, and a direct grep of the raw `mypy app/` output for `cve_id` returns zero matches — this plan's own 2-line addition introduces no mypy error at all. Already logged in `deferred-items.md` under "24-08: mypy-baseline.txt line-number drift"; no new entry needed since the root cause (environmental, affects any diff) is identical.

## User Setup Required

None — no external service configuration required. This plan is pure frontend composition over Plan 05's already-shipped section and Plan 08's already-shipped backend routes, plus one small, additive backend query field.

## Next Phase Readiness

- **D-15 is now fully complete end-to-end:** the same, unmodified `AiExplanationSection`/`AiExplanationCitations` pair drives all three drill views (vuln, host, remediation) — proven by a dedicated three-view parity test suite, not just asserted.
- Postgres + Redis containers were already running from prior Phase 24 plans and were reused directly; no new containers, no new environment variables.
- **Live browser/e2e verification of the host and remediation views was not performed this plan**, consistent with the 24-06 checkpoint's explicit user waiver ("skip live verify, proceed on trust") — this plan's new mounts are new INSTANCES of the same proven component/pattern already covered by that waiver, not a new integration seam. The plan's own `<verification>` section defers a live spot-check to "the phase verification," not to this plan.
- Phase 24 is now feature-complete across all 9 plans (Plans 01–09) — the tracer-first "Explain this vuln/host/remediation" flow is code-complete and unit-tested end-to-end for all three resource kinds, ready for the phase-level verification/audit pass.
- The `cve_id` field added to `GET /api/v1/tickets` is additive and backward-compatible; any future consumer of that endpoint (e.g. the tickets kanban board, `/tickets` list) automatically gains access to it with zero migration.

## Self-Check: PASSED

- Files verified present: `frontend/src/components/ai/ai-explanation-section.tsx`, `frontend/src/components/ai/ai-explanation-citations.tsx`, `frontend/src/components/ai/ai-explanation-section.test.tsx`, `frontend/src/components/ai/ai-explanation-citations.test.tsx`, `backend/app/ticketing/service.py`, `backend/tests/test_tickets_asset_id_filter.py` (6/6 found)
- Files verified absent (moved away): `frontend/src/components/vulnerabilities/ai-explanation-section.tsx`, `frontend/src/components/vulnerabilities/ai-explanation-citations.tsx`, `frontend/src/components/vulnerabilities/ai-explanation-citations.test.tsx` (0/3 found at old path, confirming the move)
- Commits verified present in `git log`: `f5c0ff1`, `0e12339`, `c452397`, `a93daf0` (4/4 found), in the correct `test` → `feat` → `test` → `feat` order
- TDD gate sequence confirmed: `test(24-09)` precedes `feat(24-09)` for both Task 1 and Task 2
- Plan's own `<verification>` re-run and green: `npm test -- ai-explanation-section` → 34/34; asset-detail + vuln drill regression → 9/9 + 60/60
- Acceptance-criteria greps re-confirmed: import path in `drill-content.tsx` (1), `resourceType="host"` in `page.tsx` (1), `resourceType="remediation"` in `remediation-timeline.tsx` (1), no vuln-only prop in `Props` type
- Full regression sweep green: 810/810 frontend unit tests (130/130 files), 92/92 targeted backend tests, `tsc --noEmit` clean, `eslint` clean on every new/modified file, `ruff check`/`ruff format --check` clean, `next build` clean (`/dashboard/assets/[id]` 187 kB ≤ 250 KB budget)
- Prohibitions swept clean: zero per-resourceType branches inside `AiExplanationSection`; zero new spinner/red/`--color-danger`/second-gradient-CTA/freehand-hex introduced by this plan's own files (the only hex matches in touched files are the pre-existing, already-documented provider-gradient exception in `remediation-timeline.tsx`)

---
*Phase: 24-ai-foundation-explain-this-vuln*
*Completed: 2026-07-29*
