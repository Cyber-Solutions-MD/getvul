# Phase 15 Plan 05 — Progress Note (Tasks 1 + 2 Complete, Awaiting Task 3)

**Status:** Partial — Tasks 1 and 2 committed. Task 3 (live-backend Playwright run) is a
blocking human-verify checkpoint that cannot run without docker-compose up.

---

## What was written

Four spec files + one shared helper were created and individually committed:

| Commit   | File                               | Covers                                   |
|----------|------------------------------------|------------------------------------------|
| 83c728c  | frontend/e2e/routes.ts             | Shared STATIC_ROUTES, waitForNav, discoverDetailRoute helpers |
| 83c728c  | frontend/e2e/viewport-scroll.spec.ts | UX-07-01: 9 static + 2 discovered detail routes × 4 viewports (360/390/768/1280), no horizontal scroll |
| 83c728c  | frontend/e2e/reduced-motion.spec.ts  | UX-07-04: emulateMedia({reducedMotion:'reduce'}), asserts .bg-gradient-mesh and .bg-severity-critical animationDuration <= 0.02s |
| c824192  | frontend/e2e/a11y-routes.spec.ts   | UX-07-03: per-route axe WCAG 2.1 AA blocking + WCAG 2.2 AA report-only; UX-07-02: 360px bottom-nav visible + More-sheet opens |
| c824192  | frontend/e2e/smoke.spec.ts         | UX-07-07: cross-browser smoke (chromium/webkit/firefox), landmark assertions, axe; severity glyphs ■ ▲ ◆ ○ □; UX-07-05: data-theme reflects emulated dark/light |

## --list verification (confirmed passing without backend)

```
cd frontend && npx playwright test --list --config=e2e/playwright.config.ts
```

Outputs 26 tests across 5 files / 5 projects:
- `[chromium-a11y]`: a11y-routes (3 tests), reduced-motion (2), viewport-scroll (4)
- `[chromium-smoke]`, `[webkit-smoke]`, `[firefox-smoke]`: smoke (4 each)
- `[setup]`: auth/setup authenticate

Both Task 1 and Task 2 automated --list verifications pass (exit 0).

---

## Task 3 — Human checkpoint (blocking)

Task 3 requires a live docker-compose backend. The sandbox has no docker daemon.

**The D-09 audit-fix loop is still pending** — it runs during the live suite.

### Exact commands to run (from repo root):

**Step 1 — Start the backend stack:**
```bash
docker-compose up -d postgres redis backend frontend
```
The default admin must exist (created by `backend/create_admin.py`):
- Email: `admin@getvul.local`
- Password: `Admin123!`

**Step 2 — Ensure frontend is on port 3000:**

Either the compose `frontend` service exposes :3000, OR run manually:
```bash
cd frontend && npm run build && npm run start
```

**Step 3 — Run the full Playwright suite:**
```bash
cd frontend && npx playwright test --config=e2e/playwright.config.ts
```

**Expected result:**
- `setup` project authenticates → writes `e2e/.auth/state.json`
- `chromium-a11y`: viewport-scroll (4 tests), a11y-routes (3 tests), reduced-motion (2 tests) — all green
- `chromium-smoke` + `webkit-smoke` + `firefox-smoke`: smoke (4 tests each) — all green
- Zero critical/serious axe violations; zero horizontal-scroll failures
- WCAG 2.2 AA violations logged as warnings only (not failures)

**If any spec fails (D-09 audit-fix loop):**
Fix the underlying UI defect — do NOT modify the test assertions. Re-run until green.
Only a defect requiring a backend change may be deferred; log it to `deferred-items.md`
with a risk statement.

**When green:** Reply "approved" to the resume-signal in the plan to close the checkpoint.
The final SUMMARY.md (15-05-SUMMARY.md) will be written after the checkpoint passes.

---

## What is NOT done yet

- 15-05-SUMMARY.md (not written — plan incomplete until Task 3 human checkpoint passes)
- STATE.md / ROADMAP.md not updated to mark plan complete
- D-09 audit-fix loop outcome unknown (pending live run)
