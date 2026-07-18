# Phase 18 Plan 04 — Gate Evidence

Real, pasted terminal output from the full automated quality gate, run against a
production build (`next build` + `next start` on `:3000`) with a live backend
(Docker Compose: postgres + redis + backend, all healthy) and 5 real seeded
tickets under the `admin@getvul.local` tenant. No output below is summarized or
fabricated — it is copied verbatim from the actual command runs on 2026-07-17.

## Environment setup (for reproducibility)

- `docker compose up -d postgres redis backend` — all 3 healthy.
- Frontend served via `next build && next start -- --port 3000` (prod build, not
  the dev container) — required per project memory (`getvul-local-e2e-perf-gate`)
  because Lighthouse/Playwright against a dev server is unrepresentative and the
  axe sweep needs a live server.
- Backend CORS allowlists `http://localhost:3000` — confirmed via a manual
  `curl -H "Origin: http://localhost:3000"` login request returning
  `access-control-allow-origin: http://localhost:3000`.
- Auth: `admin@getvul.local` / `Admin123!` (pre-existing OWNER user;
  `must_change_password=false`) — matches `e2e/auth/setup.ts`'s default.
- **Data seeding (new for this plan):** the tenant had **zero** tickets/vulnerabilities
  before this run (`SELECT count(*) FROM tickets` → 0), so every board e2e/axe/reduced-motion
  test would have silently `test.skip()`'d ("no seeded tickets") without ever asserting real
  behavior — exactly the "claimed but not run" failure mode this plan exists to close. A
  one-off script (`backend/scratch_seed_kanban.py`, run via `docker exec getvul-backend-1
  python scratch_seed_kanban.py`, not committed — scratch/dev-only) seeded 1 asset + 5
  vulnerabilities + 5 tickets (KAN-1..5) under the existing tenant:
  - KAN-1, KAN-2: unresolved, `external_status=null` (Open bucket), but `resolved_at` SET —
    excluded from the backend's `status=open` filter (`resolved_at IS NULL`) regardless of
    later `blocked` mutations, so the "empty column" test's per-column assertions hold even
    after KAN-1/KAN-2 get dragged into Blocked by earlier tests in the same file.
  - KAN-3: unresolved, `external_status=null`, `resolved_at=null` — the one ticket that
    stays genuinely Open through the whole spec run.
  - KAN-4: `external_status=in_progress`, `resolved_at` SET (same exclusion reasoning).
  - KAN-5: `external_status=completed`, `resolved_at` SET.
  Rationale documented so a future run can reproduce the same deterministic pass —
  the `tickets-kanban.spec.ts` tests mutate real backend state in file order (test 2 and
  3 each block one ticket for real) and the "empty column" test's filter assertions only
  hold if none of the *already-blocked-by-earlier-tests* tickets can leak back into the
  `status=open` filter's result set.

---

## 1. Bundle budget — `npm run perf:budget` (UX-D-01-06)

```
> getvul-frontend@0.1.0 build
> next build

   ▲ Next.js 15.5.20
   - Environments: .env.local

   Creating an optimized production build ...
 ✓ Compiled successfully in 1564ms
   Linting and checking validity of types ...

./src/app/(authed)/dashboard/users/page.tsx
154:9  Warning: The 'items' logical expression could make the dependencies of useCallback Hook (at line 175) change on every render. Move it inside the useCallback callback. Alternatively, wrap the initialization of 'items' in its own useMemo() Hook.  react-hooks/exhaustive-deps

./src/app/change-password/page.tsx
136:23  Warning: The autoFocus prop should not be used, as it can reduce usability and accessibility for users.  jsx-a11y/no-autofocus

./src/app/login/page.tsx
313:19  Warning: The autoFocus prop should not be used, as it can reduce usability and accessibility for users.  jsx-a11y/no-autofocus
420:19  Warning: The autoFocus prop should not be used, as it can reduce usability and accessibility for users.  jsx-a11y/no-autofocus
534:19  Warning: The autoFocus prop should not be used, as it can reduce usability and accessibility for users.  jsx-a11y/no-autofocus

./src/lib/auth.tsx
109:6  Warning: React Hook useEffect has a missing dependency: 'refreshToken'. Either include it or remove the dependency array.  react-hooks/exhaustive-deps

info  - Need to disable some ESLint rules? Learn more here: https://nextjs.org/docs/app/api-reference/config/eslint#disabling-rules
   Collecting page data ...
   Generating static pages (0/7) ...
   Generating static pages (1/7)
   Generating static pages (3/7)
   Generating static pages (5/7)
 ✓ Generating static pages (7/7)
   Finalizing page optimization ...
   Collecting build traces ...

Route (app)                                 Size  First Load JS
┌ ○ /                                      124 B         102 kB
├ ○ /_not-found                            998 B         103 kB
├ ○ /change-password                     1.37 kB         143 kB
├ ƒ /dashboard                           9.73 kB         138 kB
├ ƒ /dashboard/assets                     5.1 kB         130 kB
├ ƒ /dashboard/assets/[id]                9.7 kB         161 kB
├ ƒ /dashboard/connectors                11.3 kB         153 kB
├ ƒ /dashboard/cspm                      9.42 kB         157 kB
├ ƒ /dashboard/settings                  14.5 kB         156 kB
├ ƒ /dashboard/tickets                   6.88 kB         167 kB
├ ƒ /dashboard/tickets/[id]              9.71 kB         138 kB
├ ƒ /dashboard/tickets/rules             3.72 kB         126 kB
├ ƒ /dashboard/users                     6.63 kB         129 kB
├ ƒ /dashboard/vulnerabilities           7.06 kB         158 kB
├ ○ /dev/primitives                        124 B         102 kB
└ ○ /login                               4.01 kB         146 kB
+ First Load JS shared by all             102 kB
  ├ chunks/255-41622e0825f37f6a.js         46 kB
  ├ chunks/4bd1b696-409494caf8c83275.js  54.2 kB
  └ other shared chunks (total)          2.08 kB


ƒ Middleware                               34 kB

○  (Static)   prerendered as static content
ƒ  (Dynamic)  server-rendered on demand
```

```
> getvul-frontend@0.1.0 perf:budget
> node scripts/check-bundle-all.mjs

PASS  /  102.0 kB
PASS  /_not-found  103.0 kB
PASS  /change-password  143.0 kB
PASS  /dashboard  138.0 kB
PASS  /dashboard/assets  130.0 kB
PASS  /dashboard/assets/[id]  161.0 kB
PASS  /dashboard/connectors  153.0 kB
PASS  /dashboard/cspm  157.0 kB
PASS  /dashboard/settings  156.0 kB
PASS  /dashboard/tickets  167.0 kB
PASS  /dashboard/tickets/[id]  138.0 kB
PASS  /dashboard/tickets/rules  126.0 kB
PASS  /dashboard/users  129.0 kB
PASS  /dashboard/vulnerabilities  158.0 kB
PASS  /dev/primitives  102.0 kB
PASS  /login  146.0 kB

Routes checked: 16
Largest route:  /dashboard/tickets  167.0 kB
Budget:         250 kB gzipped per route (First Load JS)

check-bundle-all: OK — all 16 routes within 250 kB budget.
```

**Result: PASS.** `/dashboard/tickets` First Load JS = **167.0 kB**, well under the
250 KB budget (UX-D-01-06) — @dnd-kit stayed off the route's First-Load bundle via
the `next/dynamic({ssr:false})` lazy import (18-03), confirmed unchanged by this
plan's `tickets-kanban-board.tsx` edit (the keyboard-drag fix added a small pure
function + a `useRef`/`useMemo`, no new dependency).

---

## 2. Board e2e — `npx playwright test e2e/tickets-kanban.spec.ts` (UX-D-01-01..05)

**First real run (before this plan's fixes)** — 4 of 6 tests **skipped**, not because
tickets were absent (5 were seeded) but because of a genuine race in the RED spec
(authored in 18-01, before the board's `next/dynamic({ssr:false})` lazy-load
behavior existed to test against):

```
Running 6 tests using 1 worker

  ✓  1 [setup] › e2e/auth/setup.ts:18:6 › authenticate (548ms)
  -  2 [chromium-a11y] › e2e/tickets-kanban.spec.ts:25:7 › Tickets kanban board › renders four columns
  -  3 [chromium-a11y] › e2e/tickets-kanban.spec.ts:52:7 › Tickets kanban board › drag into Blocked persists
  -  4 [chromium-a11y] › e2e/tickets-kanban.spec.ts:137:7 › Tickets kanban board › keyboard drag
  -  5 [chromium-a11y] › e2e/tickets-kanban.spec.ts:173:7 › Tickets kanban board › empty column
  ✓  6 [chromium-a11y] › e2e/tickets-kanban.spec.ts:195:7 › Tickets kanban board › board mobile bottom-nav (250ms)

  4 skipped
  2 passed (3.0s)
```

Root-caused live (see "Deviations" below) and fixed. **Final run, after fixes, fresh
seed, clean build:**

```
Running 6 tests using 1 worker

  ✓  1 [setup] › e2e/auth/setup.ts:18:6 › authenticate (676ms)
  ✓  2 [chromium-a11y] › e2e/tickets-kanban.spec.ts:25:7 › Tickets kanban board › renders four columns (869ms)
  ✓  3 [chromium-a11y] › e2e/tickets-kanban.spec.ts:58:7 › Tickets kanban board › drag into Blocked persists (1.8s)
  ✓  4 [chromium-a11y] › e2e/tickets-kanban.spec.ts:158:7 › Tickets kanban board › keyboard drag (892ms)
  ✓  5 [chromium-a11y] › e2e/tickets-kanban.spec.ts:196:7 › Tickets kanban board › empty column (782ms)
  ✓  6 [chromium-a11y] › e2e/tickets-kanban.spec.ts:220:7 › Tickets kanban board › board mobile bottom-nav (271ms)

  6 passed (6.3s)
```

**Result: PASS, 6/6 real (non-skipped) tests green** — `renders four columns`,
`drag into Blocked persists` (including the 500-interceptor rollback half),
`keyboard drag` (now genuinely reaches the Blocked column via the new
column-snapping `coordinateGetter` — see Deviations), `empty column`, and
`board mobile bottom-nav`. Re-ran the "drag into Blocked persists" test 3
additional times against fresh reseeded data to confirm the layout-settle fix
holds (not a one-off pass) — all 3 green.

---

## 3. Axe sweep, both themes — `npx playwright test e2e/a11y-routes.spec.ts -g "tickets board view"` (UX-D-01-06)

```
Running 3 tests using 1 worker

  ✓  1 [setup] › e2e/auth/setup.ts:18:6 › authenticate (500ms)
  ✓  2 [chromium-a11y] › e2e/a11y-routes.spec.ts:144:7 › WCAG 2.1 AA axe sweep — tickets board view (blocking) › sweeps /dashboard/tickets?view=board for critical/serious violations (dark) (1.2s)
  ✓  3 [chromium-a11y] › e2e/a11y-routes.spec.ts:178:7 › WCAG 2.1 AA axe sweep — tickets board view (blocking) › sweeps /dashboard/tickets?view=board for critical/serious violations (light) (1.2s)

  3 passed (3.8s)
```

**Result: PASS.** Zero critical/serious axe violations on `/dashboard/tickets?view=board`
in **both** dark and light themes, swept against the real 5-card board (not an
empty-state skip) — directly closes the project-memory gap ("axe sweep not run
during execution") this phase exists to prevent.

---

## 4. Reduced motion — `npx playwright test e2e/reduced-motion.spec.ts -g "board drag drop animation"` (Pitfall 2 / T-18-10)

```
Running 2 tests using 1 worker

  ✓  1 [setup] › e2e/auth/setup.ts:18:6 › authenticate (501ms)
  ✓  2 [chromium-a11y] › e2e/reduced-motion.spec.ts:97:7 › Reduced-motion emulation › board drag drop animation is suppressed under prefers-reduced-motion (1.4s)

  2 passed (2.7s)
```

**Result: PASS.** Under `prefers-reduced-motion: reduce`, the `DragOverlay`'s WAAPI
drop-tween duration stayed ≤20ms across a ~500ms poll window after a real pointer
drag — `dropAnimation={reduced ? null : undefined}` (18-03) holds.

---

## 5. Full unit suite — `npx vitest run`

```
The plugin "vite-tsconfig-paths" is detected. Vite now supports tsconfig paths resolution natively via the resolve.tsconfigPaths option. You can remove the plugin and set resolve.tsconfigPaths: true in your Vite config instead.

 RUN  v4.1.6 /Users/chemencedji/Desktop/getvul/frontend

Error: Not implemented: HTMLCanvasElement.prototype.getContext (without installing the canvas npm package)
    at module.exports (/Users/chemencedji/Desktop/getvul/frontend/node_modules/jsdom/lib/jsdom/browser/not-implemented.js:9:17)
    at HTMLCanvasElementImpl.getContext (/Users/chemencedji/Desktop/getvul/frontend/node_modules/jsdom/lib/jsdom/living/nodes/HTMLCanvasElement-impl.js:42:5)
    at HTMLCanvasElement.getContext (/Users/chemencedji/Desktop/getvul/frontend/node_modules/jsdom/lib/jsdom/living/generated/HTMLCanvasElement.js:131:58)
    at /Users/chemencedji/Desktop/getvul/frontend/node_modules/axe-core/axe.js:16723:49
    at Object.get (/Users/chemencedji/Desktop/getvul/frontend/node_modules/axe-core/axe.js:11239:23)
    at _isIconLigature (/Users/chemencedji/Desktop/getvul/frontend/node_modules/axe-core/axe.js:16722:41)
    at /Users/chemencedji/Desktop/getvul/frontend/node_modules/axe-core/axe.js:28288:54
    at Array.some (<anonymous>)
    at hasRealTextChildren (/Users/chemencedji/Desktop/getvul/frontend/node_modules/axe-core/axe.js:28287:35)
    at Rule.colorContrastMatches [as matches] (/Users/chemencedji/Desktop/getvul/frontend/node_modules/axe-core/axe.js:28249:12) undefined
[... repeated ~20x, one per jsdom-axe component-level a11y test — known pre-existing
jsdom limitation (no <canvas> 2D context in the test DOM), non-fatal, does not fail
any test; unrelated to this plan's changes]

 Test Files  118 passed (118)
      Tests  701 passed (701)
   Start at  17:19:43
   Duration  12.74s (transform 3.11s, setup 26.14s, import 17.17s, tests 14.45s, environment 54.64s)
```

**Result: PASS.** 701/701 tests, 118/118 files. The `HTMLCanvasElement.getContext`
errors are pre-existing jsdom console noise from component-level `vitest-axe`
checks elsewhere in the suite (no `canvas` npm package installed in the test
environment) — logged but non-fatal; confirmed present before this plan's changes
too (not a regression).

---

## 6. Static checks

```
$ npx tsc --noEmit -p tsconfig.json
(no output — 0 errors)

$ npx eslint "src/app/(authed)/dashboard/tickets/tickets-kanban-board.tsx" \
    e2e/tickets-kanban.spec.ts e2e/a11y-routes.spec.ts e2e/reduced-motion.spec.ts
(no output — 0 errors, 0 warnings)
```

---

## Deviations from plan (Rule 1 — auto-fixed bugs found while proving the gate)

Running the gate for real (per this plan's whole purpose) surfaced three genuine,
reproducible bugs that were invisible to static review because none of them could
be seen without a live prod build + server + seeded data + a real browser. All
three are documented here; none were fabricated around.

### 1. Board content race in 3 e2e specs (false-skip, not a data problem)

**Found during:** first "Board e2e" run above (4/6 tests skipped despite 5 real
seeded tickets).

**Root cause (reproduced live via a standalone debug script):** the board is a
`next/dynamic({ssr:false})` lazy import (18-03). `waitForNav()` resolves as soon
as the persistent nav shell mounts — *before* the board's JS chunk downloads and
its `useTickets` query resolves. Measured: `[data-ticket-id]` count = 0 at t=0ms
immediately after `waitForNav()`, and = 5 by t=200ms. Every board test in
`tickets-kanban.spec.ts` (×4), `a11y-routes.spec.ts` (×2), and
`reduced-motion.spec.ts` (×1) read `[data-ticket-id]`'s count *immediately* after
`waitForNav()` to decide whether to `test.skip()` on "no seeded tickets" — so this
race silently converted "cards ARE there" into a false skip on every run.

**Fix:** added `await page.waitForLoadState('networkidle');` immediately after each
`waitForNav()` call in the 3 files, before the first card-count check.

**Files:** `frontend/e2e/tickets-kanban.spec.ts`, `frontend/e2e/a11y-routes.spec.ts`,
`frontend/e2e/reduced-motion.spec.ts`.

### 2. Reason-prompt Save-click race (pointer drag)

**Found during:** re-running "drag into Blocked persists" after fix #1 (both the
initial drag and its rollback sub-flow).

**Root cause (reproduced live):** `KanbanReasonPrompt` defers its autofocus via
`setTimeout(..., 0)` (Pitfall 6, 18-02). Clicking Save in the exact same tick the
popover becomes visible returns from `locator.click()` with no error, but the
click never reaches the `onClick` handler (confirmed via network capture: no
`POST .../blocked` request fires). Adding `force: true` or a short settle wait
before clicking both fix it deterministically; the settle wait is closer to real
user behavior (no one clicks a modal in the same 16ms it appears) and doesn't mask
a real actionability failure, so that's what was applied. A second, distinct race
was found in the *rollback* sub-flow: grabbing the next card's `boundingBox()`
immediately after the first successful mutation races the column reflow
(the moved card leaving Open causes the remaining cards to shift) — the very next
mousedown can land between cards instead of on one, silently failing to start a
drag at all.

**Fix:** added `await page.waitForTimeout(200);` before each Save-button click
(after it's already `waitFor({state:'visible'})`), and
`await page.waitForTimeout(300);` after the first successful-block assertion,
before starting the rollback drag. Re-ran the full test 3 additional times against
fresh reseeded data — all 3 green (not a one-off pass).

**Files:** `frontend/e2e/tickets-kanban.spec.ts`.

### 3. Keyboard drag never reaches Blocked (the exact gap 18-03 flagged for this plan)

**Found during:** "keyboard drag" test, both before and immediately after fix #1
(reproduced live with a standalone debug script: 6 `ArrowRight` presses moved the
card's bounding box by **0px**).

**Root cause:** `@dnd-kit/core`'s `defaultKeyboardCoordinateGetter` moves the drag
position by a flat **25px per arrow-key press** (confirmed by reading the
installed package source). The Blocked column sits ~700px+ from the first card in
this board's layout — 6 presses (150px) cannot cross even one column boundary, let
alone reach Blocked. This is exactly the "Open item for 18-04" flagged in
`18-03-SUMMARY.md` (RESEARCH Open Question 1 fallback): 18-03 shipped the default
coordinateGetter because verifying keyboard reachability required this plan's full
e2e harness.

A first fix attempt (a stateless getter deriving the current column from
`context.over`) worked when arrow presses were spaced out (150ms apart) but failed
identically to the original bug under back-to-back presses (no inter-press
delay — exactly how the e2e spec and a real fast typist both fire ArrowRight):
`context.over` only updates once collision detection re-runs against the
*previous* press's coordinates, so rapid presses re-derive the same "next" index
every time and the drag stalls one column short of Blocked.

**Fix (applied, per this plan's explicit pre-authorization to close this exact
gap):** replaced the default `coordinateGetter` with a column-snapping one
(`makeKanbanColumnCoordinateGetter` in `tickets-kanban-board.tsx`) that tracks the
current column index via a `useRef` counter (reset to the card's real starting
column in `handleDragStart`), not via `context.over`. `ArrowRight`/`ArrowLeft` jump
directly to the center of the next/previous column's droppable rect (clamped to
the column range, via `context.droppableContainers`); `ArrowUp`/`ArrowDown` remain
no-ops (ticket ordering within a lane isn't reorderable). Verified live: 6
`ArrowRight` presses (back-to-back, no delay) now reliably reach the Blocked
column and open the reason prompt; `npx tsc --noEmit` and the full `vitest`
suite (701/701) both stayed green with no regressions.

**Files:** `frontend/src/app/(authed)/dashboard/tickets/tickets-kanban-board.tsx`.

---

## Summary

| Check | Command | Result |
|---|---|---|
| Bundle budget | `npm run perf:budget` | PASS — `/dashboard/tickets` 167.0 kB ≤ 250 kB |
| Board e2e (6 tests) | `npx playwright test e2e/tickets-kanban.spec.ts` | PASS — 6/6 green (after 3 documented fixes) |
| Axe sweep, dark | `npx playwright test e2e/a11y-routes.spec.ts -g "tickets board view"` (dark) | PASS — 0 critical/serious |
| Axe sweep, light | same, light theme | PASS — 0 critical/serious |
| Reduced motion | `npx playwright test e2e/reduced-motion.spec.ts -g "board drag drop animation"` | PASS — drop-tween ≤20ms |
| Unit suite | `npx vitest run` | PASS — 701/701 |
| Types | `npx tsc --noEmit` | PASS — 0 errors |
| Lint | `npx eslint` (touched files) | PASS — 0 errors/warnings |

**The automated gate is GREEN, with real evidence, against a production build.**

---

## Task 2 — Human-verify checkpoint (device emulation)

**Environment provided:** prod build served at `http://localhost:3000`, backend +
Postgres + Redis healthy in Docker Compose, 5 real tickets seeded and reset to a
clean state (KAN-1/2/3 Open, KAN-4 In progress, KAN-5 Completed, none Blocked)
immediately before the checkpoint so the human had material to drag.

**Verification items and result:** the human ran the device-emulation checks
against the environment above and reported **"pass all"** — every item in the
checkpoint's `<how-to-verify>` list was confirmed working correctly:

- Touch **long-press-drag** starts a drag (vs a **quick swipe**, which scrolls the
  board horizontally instead of picking up a card) — swipe-vs-drag disambiguation
  (D-DRAG-05 / UX-D-01-05) confirmed correct on device emulation.
- Dropping a card into Blocked opens the reason prompt; **Save** persists the move
  (card lands in Blocked).
- The fixed bottom-nav (mobile navigation) stays **visible and tappable** at the
  bottom throughout, unobstructed by the board.
- **DrillPanel** Esc/clickaway behaves cleanly both **during** and **after** a
  drag — no stuck state, no layout shift, no double-open.

**Resolution: APPROVED.** Both manual-only success criteria this plan exists to
close — UX-D-01-05 (touch drag/swipe disambiguation) and the DrillPanel-during-drag
interaction (Pitfall 3 / D-CARD-02) — are human-verified against the real device
emulation environment, in addition to the fully automated evidence in Sections 1-6
above.

---

## Post-review-fix gate re-run (2026-07-18)

Six code-review fixes landed on `main` **after** the evidence above was captured:
`eee55de` (CR-01), `6c25f73` (WR-02), `23921d0` (WR-04), `34592aa` (WR-03),
`7faa111` (WR-01), `b8ff253` (WR-05) — see `18-REVIEW-FIX.md`. Per that report,
the fixer explicitly did **not** run the Playwright e2e/axe/perf gate ("needs a
prod build + running server"), only `tsc`, `eslint`, and the scoped
`vitest run src/components/tickets/` (69/69). This section re-runs the FULL
automated gate from Sections 1–5 above, fresh, against a clean `npm run build`
on top of all 6 fixes, to close that gap. Same reproducibility method as the
original run (docker compose `postgres`+`redis`+`backend`, prod `next build` +
`next start` on `:3000`, real output pasted verbatim, nothing fabricated).

### Environment for this re-run

- `docker compose up -d postgres redis backend` — all 3 healthy (confirmed via
  `docker compose ps`).
- The tenant's seeded kanban data from the original gate run had persisted in the
  `getvul_pgdata` docker volume across the intervening sessions (volume was never
  removed) — verified via `SELECT external_ticket_id, external_status, blocked,
  resolved_at IS NOT NULL FROM tickets` before running anything: KAN-1/2 (resolved,
  Open-filter-excluded), KAN-3 (genuinely Open), KAN-4 (in_progress, resolved),
  KAN-5 (completed, resolved), **none Blocked** — the exact same deterministic
  starting state documented in the original evidence's "Data seeding" note. No
  reseed was necessary; the same 5 real tickets (KAN-1..5) were used.
- `admin@getvul.local` confirmed present (`must_change_password=false`) and login
  verified end-to-end via a direct `curl -X POST http://localhost:8000/auth/login`
  with `Origin: http://localhost:3000` → `200 OK` with
  `access-control-allow-origin: http://localhost:3000` echoed back.
- Fresh `npm run build` (not reusing any prior `.next`), then `npm run start --
  --port 3000`. Confirmed no stale `next-server`/`next start` processes were
  running beforehand (`pgrep -fl "next-server|next start"` → none).

### 1. Bundle budget — `npm run perf:budget`

```
> getvul-frontend@0.1.0 build
> next build

   ▲ Next.js 15.5.20
   - Environments: .env.local

   Creating an optimized production build ...
 ✓ Compiled successfully in 2.4s
   Linting and checking validity of types ...

./src/app/(authed)/dashboard/users/page.tsx
154:9  Warning: The 'items' logical expression could make the dependencies of useCallback Hook (at line 175) change on every render. Move it inside the useCallback callback. Alternatively, wrap the initialization of 'items' in its own useMemo() Hook.  react-hooks/exhaustive-deps

./src/app/change-password/page.tsx
136:23  Warning: The autoFocus prop should not be used, as it can reduce usability and accessibility for users.  jsx-a11y/no-autofocus

./src/app/login/page.tsx
313:19  Warning: The autoFocus prop should not be used, as it can reduce usability and accessibility for users.  jsx-a11y/no-autofocus
420:19  Warning: The autoFocus prop should not be used, as it can reduce usability and accessibility for users.  jsx-a11y/no-autofocus
534:19  Warning: The autoFocus prop should not be used, as it can reduce usability and accessibility for users.  jsx-a11y/no-autofocus

./src/lib/auth.tsx
109:6  Warning: React Hook useEffect has a missing dependency: 'refreshToken'. Either include it or remove the dependency array.  react-hooks/exhaustive-deps

info  - Need to disable some ESLint rules? Learn more here: https://nextjs.org/docs/app/api-reference/config/eslint#disabling-rules
   Collecting page data ...
   Generating static pages (0/7) ...
   Generating static pages (1/7)
   Generating static pages (3/7)
   Generating static pages (5/7)
 ✓ Generating static pages (7/7)
   Finalizing page optimization ...
   Collecting build traces ...

Route (app)                                 Size  First Load JS
┌ ○ /                                      124 B         102 kB
├ ○ /_not-found                            998 B         103 kB
├ ○ /change-password                     1.37 kB         143 kB
├ ƒ /dashboard                           9.73 kB         138 kB
├ ƒ /dashboard/assets                     5.1 kB         130 kB
├ ƒ /dashboard/assets/[id]                9.7 kB         161 kB
├ ƒ /dashboard/connectors                11.3 kB         153 kB
├ ƒ /dashboard/cspm                      9.42 kB         157 kB
├ ƒ /dashboard/settings                  14.5 kB         156 kB
├ ƒ /dashboard/tickets                   6.96 kB         167 kB
├ ƒ /dashboard/tickets/[id]              9.71 kB         138 kB
├ ƒ /dashboard/tickets/rules             3.72 kB         126 kB
├ ƒ /dashboard/users                     6.63 kB         129 kB
├ ƒ /dashboard/vulnerabilities           7.06 kB         158 kB
├ ○ /dev/primitives                        124 B         102 kB
└ ○ /login                               4.01 kB         146 kB
+ First Load JS shared by all             102 kB
  ├ chunks/255-41622e0825f37f6a.js         46 kB
  ├ chunks/4bd1b696-409494caf8c83275.js  54.2 kB
  └ other shared chunks (total)          2.08 kB


ƒ Middleware                               34 kB

○  (Static)   prerendered as static content
ƒ  (Dynamic)  server-rendered on demand
```

```
> getvul-frontend@0.1.0 perf:budget
> node scripts/check-bundle-all.mjs

PASS  /  102.0 kB
PASS  /_not-found  103.0 kB
PASS  /change-password  143.0 kB
PASS  /dashboard  138.0 kB
PASS  /dashboard/assets  130.0 kB
PASS  /dashboard/assets/[id]  161.0 kB
PASS  /dashboard/connectors  153.0 kB
PASS  /dashboard/cspm  157.0 kB
PASS  /dashboard/settings  156.0 kB
PASS  /dashboard/tickets  167.0 kB
PASS  /dashboard/tickets/[id]  138.0 kB
PASS  /dashboard/tickets/rules  126.0 kB
PASS  /dashboard/users  129.0 kB
PASS  /dashboard/vulnerabilities  158.0 kB
PASS  /dev/primitives  102.0 kB
PASS  /login  146.0 kB

Routes checked: 16
Largest route:  /dashboard/tickets  167.0 kB
Budget:         250 kB gzipped per route (First Load JS)

check-bundle-all: OK — all 16 routes within 250 kB budget.
```

**Verdict: PASS.** `/dashboard/tickets` First Load JS = **167.0 kB** (6.96 kB route
size vs. 6.88 kB in the original run — the WR-01 pagination render and WR-04
`onRetry` prop are a few bytes of new JSX/props on an already-lazy-loaded board,
not a new dependency), unchanged First Load JS total, still well under the 250 KB
budget. No new dependency was added by any of the 6 fixes.

---

### 2. Board e2e — `npx playwright test e2e/tickets-kanban.spec.ts`

```
Running 6 tests using 1 worker

  ✓  1 [setup] › e2e/auth/setup.ts:18:6 › authenticate (669ms)
  ✓  2 [chromium-a11y] › e2e/tickets-kanban.spec.ts:25:7 › Tickets kanban board › renders four columns (873ms)
  ✓  3 [chromium-a11y] › e2e/tickets-kanban.spec.ts:58:7 › Tickets kanban board › drag into Blocked persists (1.8s)
  ✓  4 [chromium-a11y] › e2e/tickets-kanban.spec.ts:158:7 › Tickets kanban board › keyboard drag (863ms)
  ✓  5 [chromium-a11y] › e2e/tickets-kanban.spec.ts:196:7 › Tickets kanban board › empty column (770ms)
  ✓  6 [chromium-a11y] › e2e/tickets-kanban.spec.ts:220:7 › Tickets kanban board › board mobile bottom-nav (266ms)

  6 passed (6.3s)
```

**Verdict: PASS.** 6/6 real (non-skipped) tests green, including the drag-into-Blocked
persist/rollback flow (exercises `KanbanReasonPrompt`, now `role="group"` per WR-05)
and the keyboard drag reaching the Blocked column (CR-01's `defaultPrevented` guard
in `kanban-card.tsx` sits on the Space-key path this spec drives — unaffected, still
green; the spec still does not press Enter, so CR-01's specific Enter-vs-drag
interaction remains the one item this automated suite cannot assert — see "Residual
gap" below, unchanged from the fix report's own caveat).

---

### 3. Axe sweep, both themes — `npx playwright test e2e/a11y-routes.spec.ts -g "tickets board view"`

```
Running 3 tests using 1 worker

  ✓  1 [setup] › e2e/auth/setup.ts:18:6 › authenticate (503ms)
  ✓  2 [chromium-a11y] › e2e/a11y-routes.spec.ts:144:7 › WCAG 2.1 AA axe sweep — tickets board view (blocking) › sweeps /dashboard/tickets?view=board for critical/serious violations (dark) (1.2s)
  ✓  3 [chromium-a11y] › e2e/a11y-routes.spec.ts:178:7 › WCAG 2.1 AA axe sweep — tickets board view (blocking) › sweeps /dashboard/tickets?view=board for critical/serious violations (light) (1.2s)

  3 passed (3.8s)
```

**Verdict: PASS.** Zero critical/serious axe violations in both dark and light on
`/dashboard/tickets?view=board`, with all 6 fixes in place — this is the direct
regression check for **WR-01** (new `Pagination` control rendered in the board
branch) and **WR-05** (`role="dialog"` → `role="group"` on `KanbanReasonPrompt`,
which changes its accessible semantics): neither introduced a critical/serious
violation. The 5-ticket seed fits on a single page so the pagination control did
not actually render during this sweep (`q.data.pages > 1` gate) — its presence on
a route with >1 page is not exercised by this seed; the sweep confirms the board's
baseline a11y tree stayed clean with the fixes merged, not that the paginated
state itself is axe-clean (documented as a residual gap below, consistent with
WR-01's own fix note about being a partial mitigation).

---

### 4. Reduced motion — `npx playwright test e2e/reduced-motion.spec.ts -g "board drag drop animation"`

```
Running 2 tests using 1 worker

  ✓  1 [setup] › e2e/auth/setup.ts:18:6 › authenticate (511ms)
  ✓  2 [chromium-a11y] › e2e/reduced-motion.spec.ts:97:7 › Reduced-motion emulation › board drag drop animation is suppressed under prefers-reduced-motion (1.4s)

  2 passed (2.8s)
```

**Verdict: PASS.** Drop-tween suppression under `prefers-reduced-motion: reduce`
unaffected by the 6 fixes (none touch `tickets-kanban-board.tsx`'s
`dropAnimation` prop; WR-02's `announcements.onDragEnd` rewrite is a separate
code path).

---

### 5. Unit suite (scoped) — `npx vitest run src/components/tickets/`

```
The plugin "vite-tsconfig-paths" is detected. Vite now supports tsconfig paths resolution natively via the resolve.tsconfigPaths option. You can remove the plugin and set resolve.tsconfigPaths: true in your Vite config instead.

 RUN  v4.1.6 /Users/chemencedji/Desktop/getvul/frontend


 Test Files  13 passed (13)
      Tests  69 passed (69)
   Start at  13:30:56
   Duration  1.62s (transform 736ms, setup 2.91s, import 968ms, tests 736ms, environment 5.89s)
```

**Verdict: PASS.** 69/69 — matches the count `18-REVIEW-FIX.md` reported
immediately after the fixes (this re-run confirms it still holds on a fresh
install/build, not just at fix-time).

---

### Bonus static checks (not one of the 5 required dimensions, run for parity with the original evidence's Section 6)

```
$ npx tsc --noEmit -p tsconfig.json
(no output — 0 errors)

$ npx eslint "src/app/(authed)/dashboard/tickets/tickets-kanban-board.tsx" \
    "src/app/(authed)/dashboard/tickets/page.tsx" \
    src/components/tickets/kanban-card.tsx \
    src/components/tickets/kanban-reason-prompt.tsx \
    e2e/tickets-kanban.spec.ts e2e/a11y-routes.spec.ts e2e/reduced-motion.spec.ts
(no output — 0 errors, 0 warnings)
```

**Verdict: PASS.** Zero type errors, zero lint errors/warnings across all files
touched by the 6 review fixes plus the e2e specs.

### Residual gap (not a gate failure — carried over from `18-REVIEW-FIX.md`)

Per the fix report's own human-verification notes, two of the six fixes have a
behavioral surface the automated suite still cannot assert, and this re-run does
not change that:

- **CR-01** (Enter-vs-drag on a kanban card): `tickets-kanban.spec.ts`'s keyboard
  drag test uses **Space**, not **Enter**, so it never exercises the
  `if (e.defaultPrevented) return;` branch the fix added. This gate re-run
  confirms nothing *regressed*, but does not newly cover CR-01's actual behavior.
- **WR-02** (gated screen-reader announcement wording): the axe sweep asserts
  *no violations*, not *announcement text*; the "returned to its column" wording
  for gated no-op drops is still unasserted by any automated check in this repo.

Neither blocks this gate (both were already flagged as requiring human
verification in the fix report, not as automated-gate requirements) — carried
forward here so the gap isn't lost between the fix report and this re-run.

### Post-review-fix gate summary

| Check | Command | Result |
|---|---|---|
| Bundle budget | `npm run perf:budget` | PASS — `/dashboard/tickets` 167.0 kB ≤ 250 kB (unchanged) |
| Board e2e (6 tests) | `npx playwright test e2e/tickets-kanban.spec.ts` | PASS — 6/6 green |
| Axe sweep, dark | `npx playwright test e2e/a11y-routes.spec.ts -g "tickets board view"` (dark) | PASS — 0 critical/serious |
| Axe sweep, light | same, light theme | PASS — 0 critical/serious |
| Reduced motion | `npx playwright test e2e/reduced-motion.spec.ts -g "board drag drop animation"` | PASS — drop-tween suppressed |
| Unit (scoped) | `npx vitest run src/components/tickets/` | PASS — 69/69 |
| Types (bonus) | `npx tsc --noEmit` | PASS — 0 errors |
| Lint (bonus) | `npx eslint` (touched files) | PASS — 0 errors/warnings |

**The automated gate is GREEN on a fresh production build with all 6 code-review
fixes (`eee55de`, `6c25f73`, `23921d0`, `34592aa`, `7faa111`, `b8ff253`) merged.**
No product source was modified during this re-run — every gate passed as-is.

### Environment teardown (this re-run)

- `pkill -f "next start"` + `pkill -f "next-server"` — confirmed via `pgrep -fl`
  that no next processes remained afterward.
- `docker compose down` — stopped and removed `postgres`, `redis`, `backend`
  (the 3 services this re-run started) plus `nginx`/`frontend` containers that
  were present-but-stopped from a prior session; the `getvul_pgdata` volume was
  **not** removed (no `-v` flag), so the KAN-1..5 seed data used by this re-run
  is preserved for any future gate run.

