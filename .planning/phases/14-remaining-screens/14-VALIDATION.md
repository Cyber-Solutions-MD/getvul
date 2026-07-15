---
phase: 14
slug: remaining-screens
status: complete
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-02
---

# Phase 14 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Playwright (frontend e2e — see `frontend/test-results/`) + tsc/build for type+render gates |
| **Config file** | `frontend/playwright.config.ts` (confirm during Wave 0); `frontend/tsconfig.json` |
| **Quick run command** | `cd frontend && npx tsc --noEmit` |
| **Full suite command** | `cd frontend && npm run build && npx playwright test` |
| **Estimated runtime** | ~90 seconds (type-check ~15s, build ~45s, e2e subset ~30s) |

---

## Sampling Rate

- **After every task commit:** Run `cd frontend && npx tsc --noEmit`
- **After every plan wave:** Run `cd frontend && npm run build`
- **Before `/gsd-verify-work`:** Full suite + success-criteria grep gates must be green
- **Max feedback latency:** 90 seconds

---

## Per-Task Verification Map

> Populated by the planner from RESEARCH.md "## Validation Architecture". Each of the 6 phase
> success criteria maps to at least one observable, automatable check below.

> Reconciled 2026-07-15 (BL-05): the pre-execution `TBD by planner` stub was replaced with
> the six shipped success-criteria checks, each cross-referenced to its passing test.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 14-03 (SC-1) | 14-03 | 3 | UX-06-01 | — | CSPM chip-bar + finding-drill + compliance strip render | unit | `cd frontend && npx vitest run src/app/\(authed\)/dashboard/cspm/page.test.tsx src/components/cspm` | ✅ | ✅ green |
| 14-02 (SC-2) | 14-02 | 2 | UX-06-02 | T-14 credentials | Connector cards (gradient mark + sync pill) + add/edit form sentinel passthrough | unit | `cd frontend && npx vitest run src/components/connectors` | ✅ | ✅ green |
| 14-04 (SC-3) | 14-04 | 3 | UX-06-03 | — | Directory source pills + export bulk bar + directory/groups toggle | unit | `cd frontend && npx vitest run src/components/users/directory-table.test.tsx src/components/users/users-export-bar.test.tsx` | ✅ | ✅ green |
| 14-01 (SC-4) | 14-01 | 1 | UX-06-04 | T-14 RBAC | Settings sidebar-of-categories, RBAC-gated (VIEWER hides Workspace/SAML/Audit) | unit | `cd frontend && npx vitest run src/components/settings/settings-sidebar-shell.test.tsx src/components/settings/save-bar.test.tsx` | ✅ | ✅ green |
| 14-05 (SC-5) | 14-05 | 4 | UX-06-04 | — | Zero horizontal-tab patterns remain in settings/ | grep | `! grep -rqE 'border-b-2\|role="tab"' frontend/src/app/\(authed\)/dashboard/settings/` | ✅ | ✅ green |
| 14-all (SC-6) | 14-02..05 | 2-4 | D-X-01 | — | All 4 screens render SkeletonTable + EmptyState + PartialFailureBanner | unit | `cd frontend && npx vitest run src/app/\(authed\)/dashboard/cspm/page.test.tsx src/app/\(authed\)/dashboard/connectors/page.test.tsx src/app/\(authed\)/dashboard/users/page.test.tsx src/app/\(authed\)/dashboard/settings/page.test.tsx` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Success-Criteria Gate Commands (derived from RESEARCH Validation Architecture)

| # | Success Criterion | Automatable Check |
|---|-------------------|-------------------|
| 1 | CSPM renders chip-bar + side-panel + frameworks list + cloud-segmented control + finding cards | Render assertion: `/dashboard/cspm` mounts `ChipBar`, `DrillPanel` (idKey=finding), cloud segmented control, framework strip, finding cards |
| 2 | Connectors renders provider-gradient cards + last-sync + status pill + actions; add-connector multi-step form | Render assertion + `grep` for `ProviderMark` usage across 14 providers; functional add/edit/test/sync/delete wired |
| 3 | Users renders enrichment-source pills + bulk bar + role/title chips | Render assertion on `/dashboard/users`; `ExportButton` present in bulk bar |
| 4 | Settings renders sidebar-of-categories (6 categories), v1 tabbed layout replaced | Render assertion: 6 category sidebar items present |
| 5 | No horizontal-tab pattern in settings | `grep -rE "border-b-2 border-indigo|role=\"tab\"|\btabs?\b" frontend/src/app/(authed)/dashboard/settings/` returns no horizontal-tab usages |
| 6 | Every screen state-pattern compliant (loading/empty/partial-failure/toast) | `grep` each route for `SkeletonTable`/`EmptyState`/`PartialFailureBanner` + toast usage |

---

## Wave 0 Requirements

- [ ] Confirm `frontend/playwright.config.ts` exists; if absent, type-check + build are the automated gate, e2e is manual
- [ ] 11 new `--gradient-provider-*` tokens land in `globals.css` (foundation for connector/cspm cards)
- [ ] Sunset-restyle `ConfirmModal` + `ExportButton` (v1 raw palette → sunset tokens) before screen use
- [ ] New primitives created: connector card, finding card, settings sidebar shell, per-category save bar, sync status pill

*Wave 0 is the foundation per D-SEQ-01; the four screen plans depend on it.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Sunset palette visual fidelity (gradient hex review) | UX-06-01..04 | Brand-approximate hex for 11 new providers needs human visual review (RESEARCH LOW-confidence item) | Render connectors page, visually confirm each provider mark gradient reads correctly |
| Settings mobile master-detail drill (<900px) | UX-06-04 | Responsive interaction; formal audit deferred to Phase 15 | Resize to <900px, tap category, confirm slide-to-pane + back affordance |
| Masked-secret sentinel passthrough on connector edit | UX-06-02 | End-to-end credential round-trip needs live backend | Edit a connector, leave secret untouched, save, confirm stored secret preserved |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

---

## Validation Audit 2026-07-15 (BL-05)

The Per-Task Map shipped with a single `TBD by planner` placeholder. Reconciled it to the six
phase success criteria, each cross-referenced to its passing test/grep gate.

| Metric | Count |
|--------|-------|
| Automated rows | 6 (SC-1..6) |
| Covered (green) | 6 |
| Gaps found | 0 |
| New tests written | 0 |
| Escalated to manual-only | 0 (3 manual items already in Manual-Only) |

Evidence: `npx vitest run` 683/683 green (cspm/connectors/users/settings components + pages) ·
settings tab-pattern grep returns 0 matches. **Nyquist-compliant.**
