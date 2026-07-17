---
phase: 18
slug: tickets-kanban-board
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-17
---

# Phase 18 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from 18-RESEARCH.md §Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Vitest 4.1.6 (unit) + Playwright 1.61.1 (e2e) + `@axe-core/playwright` 4.12.1 (a11y) |
| **Config file** | `frontend` package.json `test`; `frontend/e2e/playwright.config.ts` |
| **Quick run command** | `cd frontend && npx vitest run src/components/tickets/bucket-tickets.test.ts src/lib/queries/use-mark-blocked.test.ts` |
| **Full suite command** | `cd frontend && npm run test && npm run test:e2e && npm run perf:budget` |
| **Estimated runtime** | ~5s (quick) / ~2–4 min (full e2e + bundle gate) |

---

## Sampling Rate

- **After every task commit:** Run `cd frontend && npx vitest run src/components/tickets/bucket-tickets.test.ts src/lib/queries/use-mark-blocked.test.ts` (<5s)
- **After every plan wave:** Run `cd frontend && npm run test && npx playwright test e2e/tickets-kanban.spec.ts`
- **Before `/gsd-verify-work`:** `npm run test && npm run test:e2e && npm run perf:budget` all green (axe both themes + bundle ≤250 KB + keyboard drag)
- **Max feedback latency:** ~5 seconds (unit); e2e at wave boundaries

---

## Per-Task Verification Map

| Req ID | Behavior | Test Type | Automated Command | File Exists | Status |
|--------|----------|-----------|-------------------|-------------|--------|
| UX-D-01-01 | 4 columns render from `useTickets`; list/board toggle preserved | e2e | `npx playwright test e2e/tickets-kanban.spec.ts -g "renders four columns"` | ❌ W0 | ⬜ pending |
| UX-D-01-01 | `bucketTickets` Blocked-wins + unknown→Open + column order | unit | `npx vitest run src/components/tickets/bucket-tickets.test.ts` | ❌ W0 | ⬜ pending |
| UX-D-01-02 | pointer drag into Blocked persists w/ optimistic + rollback on error | e2e | `npx playwright test e2e/tickets-kanban.spec.ts -g "drag into Blocked persists"` | ❌ W0 | ⬜ pending |
| UX-D-01-02 | `useMarkBlocked` onMutate flips list cache; onError restores (Pitfall 1 fix) | unit | `npx vitest run src/lib/queries/use-mark-blocked.test.ts` | ❌ W0 (extend if exists) | ⬜ pending |
| UX-D-01-02 | reason whitespace→null coercion; Cancel = no mutation | unit | `npx vitest run src/components/tickets/kanban-reason-prompt.test.tsx` | ❌ W0 | ⬜ pending |
| UX-D-01-03 | keyboard grab/move/drop changes status (Space+arrows+Space) | e2e | `npx playwright test e2e/tickets-kanban.spec.ts -g "keyboard drag"` | ❌ W0 | ⬜ pending |
| UX-D-01-04 | empty column shows canonical EmptyState; status chip narrows columns | e2e | `npx playwright test e2e/tickets-kanban.spec.ts -g "empty column"` | ❌ W0 | ⬜ pending |
| UX-D-01-05 | <768px board view: fixed bottom-nav still visible AND focusable at 360px (non-regression on `?view=board`) | e2e | `npx playwright test e2e/tickets-kanban.spec.ts -g "board mobile bottom-nav"` | ❌ W0 | ⬜ pending |
| UX-D-01-06 | route ≤250 KB First Load JS | build gate | `cd frontend && npm run perf:budget` | ✅ `scripts/check-bundle-all.mjs` | ⬜ pending |
| UX-D-01-06 | axe WCAG 2.1 AA green on `/dashboard/tickets` BOTH themes (incl. mid-drag overlay) | e2e | `npx playwright test e2e/a11y-routes.spec.ts` | ✅ (extend to board view) | ⬜ pending |
| UX-D-01-06 | reduced-motion: DragOverlay drop animation suppressed (Pitfall 2) | e2e | `npx playwright test e2e/reduced-motion.spec.ts` | ✅ (extend w/ board drop) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Note on UX-D-01-05: the existing `a11y-routes.spec.ts` `-g "Bottom-nav"` sweep runs at 360px over `STATIC_ROUTES`, which only exercises the LIST view of `/dashboard/tickets`. The board-layout non-regression at <768px is now guarded by the dedicated `board mobile bottom-nav` case in `tickets-kanban.spec.ts` (authored RED in 18-01, turns GREEN when the board renders in Wave 2) — no longer manual-only.*

---

## Wave 0 Requirements

- [ ] `frontend/src/components/tickets/bucket-tickets.ts` + `bucket-tickets.test.ts` — pure bucketing (UX-D-01-01): Blocked-wins, `in_progress`/`in progress` alias, unknown/null→Open, `COLUMN_ORDER`.
- [ ] `frontend/src/lib/queries/use-mark-blocked.test.ts` — assert `onMutate` `setQueriesData` flips the `['tickets','list',*]` caches and `onError` restores (Pitfall 1 regression guard). Create if absent; extend if present.
- [ ] `frontend/src/components/tickets/kanban-reason-prompt.test.tsx` — Save with reason, Cancel = no mutation, whitespace→null (UX-D-01-02, mirror `blocked-toggle.tsx`).
- [ ] `frontend/e2e/tickets-kanban.spec.ts` — NEW: four columns render, pointer drag→Blocked persists (optimistic + rollback on injected error), keyboard drag, empty-column EmptyState, status-chip narrowing, board+overlay axe, board-view 360px bottom-nav non-regression.
- [ ] EXTEND `frontend/e2e/a11y-routes.spec.ts` — sweep `/dashboard/tickets?view=board` (+ mid-drag) in both themes.
- [ ] EXTEND `frontend/e2e/reduced-motion.spec.ts` — assert no drop tween under `reducedMotion: 'reduce'`.
- [ ] Framework install: `cd frontend && npm install @dnd-kit/core@6.3.1` (no `--legacy-peer-deps` needed; Vitest/Playwright already present).

*Note: the axe-both-themes e2e sweep must actually run against a prod build — per project memory, executors have historically claimed AA without running it.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Touch long-press-drag vs swipe-scroll disambiguation on a real phone | UX-D-01-05 | TouchSensor press-delay behavior is hard to assert reliably in headless Playwright | On a touch device / device-emulation: quick swipe scrolls the board horizontally; ~200ms press-and-hold on a card initiates drag |

*All other phase behaviors have automated verification. The board-view fixed-bottom-nav non-regression (UX-D-01-05 layout) is now automated via the `board mobile bottom-nav` e2e case — only the touch-gesture disambiguation above remains manual.*

---

## Validation Sign-Off

- [ ] All requirements have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s (unit)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
</content>
