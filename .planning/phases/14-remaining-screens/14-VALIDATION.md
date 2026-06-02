---
phase: 14
slug: remaining-screens
status: draft
nyquist_compliant: false
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

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 14-XX-XX | TBD | TBD | UX-06-XX | — | RBAC gating hides categories below role | render/grep | TBD by planner | ❌ W0 | ⬜ pending |

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
