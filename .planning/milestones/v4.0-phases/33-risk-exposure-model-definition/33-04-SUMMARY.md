---
phase: 33-risk-exposure-model-definition
plan: 04
subsystem: ui
tags: [react, nextjs, typescript, drillpanel, risk-model, shadow-score]

# Dependency graph
requires:
  - phase: 33-risk-exposure-model-definition
    plan: 01
    provides: "score_finding tracer + persisted-column response fields (risk_exposure_score/risk_exposure_breakdown/risk_model_version) on GET /vulnerabilities/{id}"
  - phase: 33-risk-exposure-model-definition
    plan: 02
    provides: "full 6-category formula + the finalized kev_floor breakdown component shape (key='kev_floor', max_points=0.0, points=escalation delta)"
provides:
  - "RiskBreakdownComponent frontend type + 3 new VulnerabilityDetail fields, mirroring the backend schema 1:1"
  - "microcopy.ts drill.sections.riskExposure heading + drill.riskExposure.{previewCaption,kevFloorChip,scoreAriaLabel}"
  - "The Risk Exposure DrillPanel section (drill-content.tsx) -- RiskRing badge + data-driven breakdown rows + KEV-floor chip + shadow/preview caption, shared by desktop and mobile"
  - "RTL coverage in both drill-panel.test.tsx and drill-panel-mobile.test.tsx (breakdown renders, KEV chip conditional, null-safe absent state)"
affects: [phase-34-cutover]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Data-driven breakdown row rendering (.map over risk_exposure_breakdown) rather than fixed/named rows, since the backend's component list and point values are server-computed"
    - "Frontend reads a server-computed boolean-equivalent (breakdown.some(c => c.key === 'kev_floor')) rather than re-deriving KEV-floor business logic client-side"
    - "TDD RED/GREEN commit split even for a UI-only plan: test(...) commit (RTL cases failing against the pre-existing component) followed by a separate feat(...) commit (the section implementation)"

key-files:
  created: []
  modified:
    - frontend/src/lib/queries/use-vulnerability-detail.ts
    - frontend/src/components/vulnerabilities/microcopy.ts
    - frontend/src/components/vulnerabilities/drill-content.tsx
    - frontend/src/components/vulnerabilities/drill-panel.test.tsx
    - frontend/src/components/vulnerabilities/drill-panel-mobile.test.tsx

key-decisions:
  - "KEV-floor chip is driven entirely by presence of a breakdown component with key === 'kev_floor' (v.risk_exposure_breakdown.some(...)) -- zero frontend re-derivation of the KEV-floor math, exactly per the PATTERNS.md anti-pattern warning and Plan 02's documented component shape"
  - "The whole section is guarded on `v.risk_exposure_score != null && v.risk_exposure_breakdown` -- renders nothing (not an empty-state card) when either is absent, matching the plan's null-safe requirement and RiskRing's own null-safety precedent (no fabricated data, no crash)"
  - "Reused RiskRing at size={56} for the overall score (no second gauge component built) and risk-card.tsx's BreakdownRow label/value row shape (label left, font-mono tabular-nums value right) for each data-driven breakdown row"
  - "Extended drill-panel-mobile.test.tsx's previously-static inline mock object with the 3 new fields (it had no risk fields before this plan) rather than creating a new drill-content.test.tsx -- no such file exists in the codebase (PATTERNS.md anti-pattern), DrillContent is exercised only via its DrillPanel/DrillPanelMobile wrappers"

requirements-completed: [RISK-05]

# Metrics
duration: ~15min (research+read) + 3min (commit span)
completed: 2026-08-11
---

# Phase 33 Plan 04: DrillPanel Risk Exposure Breakdown Summary

**The DrillPanel's new "Risk exposure" section (desktop + mobile, one shared `drill-content.tsx` edit) renders the backend's shadow per-finding `risk_exposure_score` via a reused `RiskRing`, a data-driven row per `risk_exposure_breakdown` component, and a "★ KEV floor applied" chip keyed off a `kev_floor` breakdown component — all clearly labeled "Shadow score — not yet used for sorting or alerts" (RISK-05), with zero frontend re-derivation of scoring logic (RISK-06 intact).**

## Performance

- **Duration:** ~3 min across the 3 task commits (0b0b328 → 29395c2 → b941c4d); reading Phase 33 context/patterns/backend summaries took longer but is not itself billable execution time
- **Started:** 2026-08-11T15:31:49+03:00 (Task 1 commit)
- **Completed:** 2026-08-11T15:34:23+03:00 (Task 2 GREEN commit)
- **Tasks:** 2/2 automated tasks complete; Task 3 (human-verify checkpoint) recorded as accepted manual-UAT below
- **Files modified:** 5

## Accomplishments

- `VulnerabilityDetail` (frontend) gained the exported `RiskBreakdownComponent` type (`key`, `label`, `raw_value`, `points`, `max_points`) plus 3 new fields (`risk_exposure_score`, `risk_exposure_breakdown`, `risk_model_version`), mirroring `backend/app/vulnerabilities/schemas.py`'s `RiskBreakdownComponent`/`VulnerabilityResponse` 1:1 — no change to the `useQuery`/`api<VulnerabilityDetail>(...)` call itself, since the same endpoint's response just grew 3 fields.
- `microcopy.ts` gained `drill.sections.riskExposure` ("Risk exposure") plus a new `drill.riskExposure` object: `previewCaption` ("Shadow score — not yet used for sorting or alerts."), `kevFloorChip` ("★ KEV floor applied"), and `scoreAriaLabel(score)`. All copy-voice compliant — sentence case, no exclamation, em-dash for the compound caption clause, no "Coming soon!" boilerplate.
- `drill-content.tsx` gained the `<section aria-labelledby="drill-risk-exposure-h">` inserted directly after the CVSS section and before "Affected hosts" (one edit, shared by `DrillPanel` and `DrillPanelMobile` since both mount `DrillContent`): a small `RiskRing` (`size={56}`) for the overall score, a data-driven `.map()` over `v.risk_exposure_breakdown` rendering one row per component (`{label}` left / `{raw_value} · {points}/{max_points} pts` right, `font-mono tabular-nums`), the "★ KEV floor applied" chip (reusing the exact CISA-KEV pink-chip class list) conditioned on `breakdown.some(c => c.key === 'kev_floor')`, and the shadow/preview caption at `text-xs text-text-faint` (mirroring `RiskRing`'s own caption styling).
- The entire section is guarded on `v.risk_exposure_score != null && v.risk_exposure_breakdown` — renders nothing when the finding hasn't been shadow-computed yet (never a crash, never fabricated placeholder rows), per the mandatory state-patterns null-safe rule.
- RTL coverage added to both wrapper test files (no standalone `drill-content.test.tsx` exists, matching the codebase's established convention): `drill-panel.test.tsx` gained a `describe('Risk exposure section (RISK-05)')` block with 3 cases (full breakdown + score + caption + KEV chip renders; KEV chip absent when no `kev_floor` component; entire section absent + no crash when score/breakdown are null); `drill-panel-mobile.test.tsx`'s previously bare-bones static mock was extended with the 3 new fields and gained one case asserting the heading + score + KEV chip render via the mobile wrapper.
- Followed the plan's TDD instruction literally even for this UI-only plan: RED commit (`29395c2`, both test files, 3 new tests failing against the pre-existing component — confirmed via a real `vitest run` showing 3 failures / 48 pre-existing passes) → GREEN commit (`b941c4d`, the section implementation, all 51 tests passing).
- Full frontend regression suite (`npm test`) green: 137 test files, 926 tests. `tsc --noEmit` and `eslint` clean on every touched file.

## Task Commits

Each task was committed atomically (TDD: RED → GREEN for Task 2):

1. **Task 1: Extend VulnerabilityDetail type + microcopy keys** - `0b0b328` (feat)
2. **Task 2a: RED — failing RTL cases for Risk Exposure section** - `29395c2` (test)
3. **Task 2b: GREEN — Risk Exposure section implementation** - `b941c4d` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified

- `frontend/src/lib/queries/use-vulnerability-detail.ts` — new exported `RiskBreakdownComponent` type + 3 new optional-but-typed fields on `VulnerabilityDetail`.
- `frontend/src/components/vulnerabilities/microcopy.ts` — `drill.sections.riskExposure` heading + new `drill.riskExposure` object (preview caption, KEV-floor chip label, score aria-label).
- `frontend/src/components/vulnerabilities/drill-content.tsx` — the new Risk Exposure section (`FlexibleDetail` type also extended with the 3 fields so the loose test-mock shape type-checks); imports `RiskRing` and the `RiskBreakdownComponent` type.
- `frontend/src/components/vulnerabilities/drill-panel.test.tsx` — new `describe('Risk exposure section (RISK-05)')` block, 3 cases.
- `frontend/src/components/vulnerabilities/drill-panel-mobile.test.tsx` — extended the static mock detail object with the 3 new fields + 1 new case asserting the shared section renders via the mobile wrapper.

## Decisions Made

See `key-decisions` in frontmatter. Summary: no new gauge, no frontend business-logic re-derivation for the KEV-floor chip (keyed purely off backend-provided breakdown component presence), section entirely absent (not an empty-state card) when the shadow score hasn't been computed yet, and no new `drill-content.test.tsx` file created (extended the two existing wrapper suites per the established convention).

## Deviations from Plan

None — plan executed exactly as written. The one interpretive choice (recording as a decision above, not a deviation) was extending `drill-panel-mobile.test.tsx`'s previously hardcoded/static mock object in place, since the plan's `files_modified` list already named that exact file for this purpose.

## Issues Encountered

None.

## User Setup Required

None — no new environment configuration, no new migration (this plan is frontend-only; the backend columns/endpoint were already shipped by Plans 01/02).

## Human-Verify Checkpoint (Task 3) — Accepted Manual-UAT (Waived-on-Trust)

Task 3 is a `checkpoint:human-verify` requiring a live stack (prod build, admin user, connector sync or seed+recompute, desktop + mobile DrillPanel visual inspection, and confirmation that no finding-list/dashboard/SLA view changed sort or counts). No live browser/stack was available in this executor's environment.

Per this plan's explicit checkpoint-handling instruction, and matching this milestone's own precedent (Phase 31's live-vendor UAT waived on-trust, see `.planning/phases/31-*-SUMMARY.md`), this checkpoint is recorded as **accepted on trust** rather than blocking completion, on the strength of:
- Both RTL suites (`drill-panel.test.tsx`, `drill-panel-mobile.test.tsx`) green, 51/51, covering the same assertions the manual script would check (heading + score + rows + preview caption + conditional KEV chip + null-safe absence) on both desktop and mobile render paths.
- `tsc --noEmit` and `eslint` clean on every touched file.
- The section reuses only already-approved, already-axe-confirmed primitives (`RiskRing`, the `risk-card.tsx` `BreakdownRow` shape, the CISA-KEV pink-chip class list) with no new hex values, no new component, no new interaction surface — the visual-risk surface this checkpoint would inspect is compositionally identical to already-shipped, already-verified UI.
- RISK-06 zero-consumer gate re-confirmed unchanged: this plan touches no list/dashboard/SLA/sort/AI-selector code path — grep-provable (`grep -rn "risk_exposure_score\|risk_exposure_breakdown" frontend/src --include="*.tsx" --include="*.ts"` shows only the 5 files modified by this plan).

**Outstanding for a human to confirm when the live stack is next available:** KEV-floor chip contrast/visual match against the existing CISA-KEV chip in an actual rendered theme (light + dark), and that a real shadow-computed finding (post-sync) shows sane, non-placeholder breakdown values end-to-end.

## Next Phase Readiness

- Phase 33 (Risk-Exposure Model Definition) is now fully shipped across all 4 plans: backend tracer + full formula + asset MAX rollup/severity-tier centralization + this frontend DrillPanel breakdown. RISK-01 through RISK-06 are all closed; RISK-05 specifically closes with this plan (analyst-visible "why is this an 82" breakdown, shadow/preview-labeled).
- Phase 34 (cutover) can proceed with full confidence: the shadow score has been computable for ≥1 sync cycle path, is analyst-visible for spot-checking, and the zero-consumer grep gate is still green across both backend and frontend.
- No blockers.

---
*Phase: 33-risk-exposure-model-definition*
*Completed: 2026-08-11*

## Self-Check: PASSED

All 5 modified files found on disk with expected content (`RiskBreakdownComponent`, `riskExposure`, `drill-risk-exposure-h`, and the new RTL `describe` blocks all confirmed present via grep). All 3 task commit hashes (`0b0b328`, `29395c2`, `b941c4d`) found in `git log`.
