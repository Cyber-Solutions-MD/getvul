# Phase 21: Page-transition verification - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-21
**Phase:** 21-page-transition-verification
**Areas discussed:** UAT closure, Test fidelity, Firefox fallback, Close-race coverage

---

## UAT closure (SC#2 — perceptual human-UAT)

| Option | Description | Selected |
|--------|-------------|----------|
| I'll test it now, guided | App stood up + perceptual checklist; user signs off item-by-item; recorded in 17-HUMAN-UAT.md | ✓ |
| Accept on evidence | Persist + mark closed based on e2e-green/reduced-motion state, no fresh manual pass | |
| Persist as pending | Create structured file, leave items pending for /gsd-verify-work (does NOT satisfy SC#2) | |

**User's choice:** I'll test it now, guided
**Notes:** Becomes a `human-action` checkpoint during execution (real interactive pause, not auto-approved). Checklist items: cross-fade feel, chrome stillness, DrillPanel-during-transition, Firefox fallback feel. On sign-off, clear STATE.md OUTSTANDING flag.

---

## Test fidelity (SC#1 — replace synthetic PopStateEvent proxy)

| Option | Description | Selected |
|--------|-------------|----------|
| Real router, both cases | Real Next navigation: ?drill=/?tab= no-fade case + pathname-change-with-drill-open fade case. No seeded-data dependency | ✓ |
| Real UI click, both cases | Click a live vuln row to open the real DrillPanel then navigate; highest fidelity but fixture-dependent / flakier | |
| No-fade case only | Only replace the proxy for the searchParams no-fade assertion | |

**User's choice:** Real router, both cases
**Notes:** Asserts D-02 (searchParams never fade) AND D-11 (drill fades out with content, no layout shift). Prefer real router.replace over seeded interactive data — the reason Phase 17 used the proxy. A reachable real UI control is an acceptable upgrade if cheap.

---

## Firefox fallback (perceptual "Firefox feel")

| Option | Description | Selected |
|--------|-------------|----------|
| Automated assertion | e2e assertion (Firefox project) that the CSS-keyframe fallback runs on template mount | ✓ |
| Manual UAT item | Keep Firefox as a manual perceptual check in 17-HUMAN-UAT.md | |
| You decide | Let Claude pick during planning | |

**User's choice:** Automated assertion
**Notes:** Firefox lacks View Transitions → exercises D-06 fallback path. Reuse the existing Firefox project + firefoxUserPrefs in playwright.config.ts. Confirm the D-12 reduced-motion blanket still suppresses it.

---

## Close-race coverage (UX-D-06-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Add explicit close-path test | Open drill, Esc/clickaway close, assert no authed-page-content fade + no layout shift | ✓ |
| Architectural guarantee is enough | Rely on the generic "searchParams never fade" assertion; fold Esc/clickaway into perceptual UAT | |

**User's choice:** Add explicit close-path test
**Notes:** Directly exercises the race guard rather than inferring it.

## Claude's Discretion

- How the real router.replace is invoked from Playwright (page.evaluate vs. reachable control).
- Which spec file the Firefox fallback assertion lives in.
- Layout-shift measurement technique (CLS observer vs. bounding-box before/after).

## Deferred Ideas

- Navigation pending indicator (top loading bar during navigation to force-dynamic routes) — carried from Phase 17; a new capability, not UX-D-06 verification.
