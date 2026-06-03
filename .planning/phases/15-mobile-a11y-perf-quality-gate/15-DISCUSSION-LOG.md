# Phase 15: Mobile + a11y + Perf Quality Gate - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-03
**Phase:** 15-mobile-a11y-perf-quality-gate
**Areas discussed:** a11y/cross-browser toolchain, Mobile navigation model, Lighthouse + perf-budget gate, Audit-fix scope policy

---

## Area selection

| Option | Selected |
|--------|----------|
| a11y/cross-browser toolchain | ✓ |
| Mobile navigation model | ✓ |
| Lighthouse + perf-budget gate | ✓ |
| Audit-fix scope policy | ✓ |

All four gray areas selected for discussion.

---

## a11y / cross-browser toolchain

| Option | Description | Selected |
|--------|-------------|----------|
| Adopt Playwright (full) | @playwright/test + @axe-core/playwright; per-route × 4-viewport sweep across Chromium/WebKit/Firefox | ✓ |
| Playwright a11y only + manual cross-browser | Chromium-only Playwright; Safari/Firefox manual | |
| Stay vitest-axe + manual everything | No new toolchain; jsdom + manual checklists | |

**User's choice:** Adopt Playwright (full).

### Follow-up: Safari strictness

| Option | Selected |
|--------|----------|
| WebKit proxy is enough | |
| WebKit + manual Safari spot-check | ✓ |

**User's choice:** WebKit automated gate + manual Safari.app spot-check on smoke routes for glyph rendering at 14px.

### Follow-up: axe ruleset

| Option | Selected |
|--------|----------|
| 2.1 AA blocks, 2.2 AA reports | ✓ |
| 2.2 AA blocks everything | |

**User's choice:** WCAG 2.1 AA blocking (zero critical/serious); WCAG 2.2 AA as report/warnings.

---

## Mobile navigation model

| Option | Description | Selected |
|--------|-------------|----------|
| Bottom-nav phone + drawer tablet | <768 bottom-nav; 768–999 hamburger drawer; ≥1000 sidebar | ✓ |
| Bottom-nav everywhere <1000px | Single pattern; no drawer | |
| Hamburger drawer everywhere <1000px | Single pattern; no bottom-nav | |

**User's choice:** Bottom-nav on phone + drawer on tablet.

### Follow-up: breakpoint + bottom-nav behavior

| Option | Selected |
|--------|----------|
| 768px split, More = sheet | ✓ |
| 640px split | |

**User's choice:** 768px split; "More" opens a vaul bottom sheet (Assets/CSPM/Connectors/Users/Settings); gradient-strip active indicator.

### Follow-up: bottom-sheet conversion scope

| Option | Selected |
|--------|----------|
| All app modals | ✓ |
| Drill panels + confirms only | |
| Verify existing only | |

**User's choice:** All app modals convert to vaul bottom sheets on mobile.

---

## Lighthouse + perf-budget gate

| Option | Description | Selected |
|--------|-------------|----------|
| Scripted local run + committed report | Lighthouse CI mobile on /login + /dashboard; check-bundle extended to all routes ≤250KB; committed 15-PERF-REPORT.md | ✓ |
| Wire into Playwright/CI as blocking | Hard CI gate; overlaps deferred Phase 2 | |
| Fully manual | DevTools by hand into HUMAN-UAT | |

**User's choice:** Scripted local run + committed report artifact.

---

## Audit-fix scope policy

| Option | Description | Selected |
|--------|-------------|----------|
| Fix all SC-blocking + a11y critical/serious; defer cosmetic | Bounded closer; cosmetic/2.2-only nits to backlog | |
| Fix everything found | No deferral; phase ends when defect list empty | ✓ |
| Time-boxed triage | Fixed fix-budget, defer remainder | |

**User's choice:** Fix everything found. Only exception (noted by Claude): defects requiring backend changes are out of scope for this frontend-only milestone and get logged to a v1.x backlog with a risk note.

---

## Claude's Discretion

- Playwright config structure, test-file organization, route enumeration.
- Lighthouse CI package/runner choice.
- check-bundle.mjs all-route extension approach.
- Drawer animation + bottom-nav icon choices (lucide-react).
- Retaining vitest-axe component tests alongside Playwright route tests.

## Deferred Ideas

- UX-D-03 — full light-theme visual polish pass (toggle verified; per-screen QA deferred).
- UX-D-06 — page-transition motion.
- Backend-requiring defects → v1.x backlog with risk note.
