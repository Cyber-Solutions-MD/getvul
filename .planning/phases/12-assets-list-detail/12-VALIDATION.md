---
phase: 12
slug: assets-list-detail
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-29
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Filled by gsd-planner before plans are finalized.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Backend framework** | pytest 7.x (backend/) |
| **Frontend framework** | vitest + @testing-library/react (frontend/) + Playwright (frontend/e2e) |
| **Config file** | backend/pyproject.toml (pytest config); frontend/vitest.config.ts; frontend/playwright.config.ts |
| **Quick run command (frontend)** | `pnpm --filter frontend test --run` |
| **Quick run command (backend)** | `cd backend && pytest -x -q` |
| **Full suite command** | `pnpm --filter frontend test --run && pnpm --filter frontend tsc --noEmit && cd backend && pytest && cd ../frontend && pnpm test:e2e` |
| **Estimated runtime** | ~90 seconds (unit + tsc); ~3 min including e2e |

---

## Sampling Rate

- **After every task commit:** Run scoped quick command (frontend changes → vitest; backend changes → pytest of touched module)
- **After every plan wave:** Run full unit suite (frontend vitest + backend pytest)
- **Before `/gsd-verify-work`:** Full suite + tsc + lint + playwright must be green
- **Max feedback latency:** 30 seconds for unit; 180 seconds for full

---

## Per-Task Verification Map

To be populated by gsd-planner. Each task in each PLAN.md must map to one row here with an `<automated>` verify command or a Wave 0 dependency.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| _to be populated by gsd-planner_ | | | | | | | | | ⬜ pending |

---

## Wave 0 Requirements

- [ ] Backend Alembic migration test fixture for adding `tags` + `sla_breach` aggregation — confirm existing `tests/conftest.py` supports `Asset.tags` column after migration
- [ ] Frontend test util to mock `useAssignableUsers` + `useReassignAsset` hooks — likely no new util needed (existing TanStack QueryClient wrapper from Phase 11 tests covers this)

*If existing infrastructure covers all requirements: gsd-planner should mark this as "Existing infrastructure covers all phase requirements" and proceed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Mobile rail collapse below 900px | UX-04-02 | Viewport-dependent visual; Playwright snapshot covers basic, but real-device fidelity needs manual check | Resize browser to 768/375; verify rail stacks below main; verify breadcrumb truncates gracefully |
| Risk-ring drop-shadow visual at variable scores | UX-04-03 | The `filter: drop-shadow(0 0 8px currentColor)` effect requires visual inspection | Open `/assets/[id]` for assets with scores 0/20/50/80/100; verify gradient stroke + glow read correctly against dark surface |
| Reassign optimistic UI smoothness | UX-04-04 | Mutation timing is sub-second; needs perceived-snappiness check | Reassign with throttled network (Slow 3G); verify combobox closes immediately and owner card shows new name before request resolves |
| Sketch 005 variant B fidelity | UX-04-02 | Pixel-level adherence to the locked sketch | Open both `/assets/[id]` and `.claude/skills/sketch-findings-getvul/sources/005-asset-detail-sunset/index.html` side-by-side at 1280px; verify layout match |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s for quick suite
- [ ] `nyquist_compliant: true` set in frontmatter (toggle once gsd-planner populates the per-task table)

**Approval:** pending
