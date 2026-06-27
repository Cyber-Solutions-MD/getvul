---
phase: 15
plan: 06
artifact: human-uat
status: pending
---

# Phase 15 — Human UAT Checklist

> Manual-only verifications that cannot be automated (15-VALIDATION.md §Manual-Only Verifications).
> Each item requires real hardware/OS interaction. Complete all three before signing off phase 15.

---

## Item 1: Severity Glyphs Legible at 14px in Real Safari.app

**Requirement:** UX-07-07 / D-02
**Why manual:** WebKit-in-Playwright is a proxy only. Real Safari.app DPR rendering on macOS
may differ. The five severity glyphs (■ ▲ ◆ ○ □) must be distinguishable at 14px on real DPR.

**Steps:**

1. Open Safari.app (not the Simulator — use real macOS Safari).
2. Navigate to `http://localhost:3000/dashboard/vulnerabilities` (stack must be running).
3. Check default font-size renders glyphs clearly at 14px: Critical (■), High (▲), Medium (◆), Low (○), Info (□).
4. Navigate to a vulnerability detail page (e.g., `/dashboard/vulnerabilities` then open a drill panel).
5. Confirm each glyph is visually distinct and legible — not blurred, clipped, or confused with another glyph.
6. If available, check on a non-Retina display (or toggle DPR in Safari DevTools) to confirm legibility at 1x DPR.

**Pass criteria:** All five glyphs (■ ▲ ◆ ○ □) are visually distinct and legible at 14px in Safari.app.

| | |
|---|---|
| **Result** | Pass / Fail |
| **Notes** | (fill in — include DPR tested, any glyph confusion) |
| **Tester** | (name) |
| **Date** | (date) |

---

## Item 2: Focus-Not-Obscured by Fixed Bottom-Nav at <768px

**Requirement:** UX-07-03 / WCAG 2.4.11 (SC 2.4.12 not yet in axe 4.12 — manual only)
**Why manual:** axe-core 4.12 has no `focus-not-obscured` rule (WCAG 2.4.11/2.4.12).
The bottom-nav is `position: fixed` at the bottom — a focused element scrolled near the
bottom of the viewport could be hidden behind it.

**Steps:**

1. Open Chrome or Safari with DevTools responsive mode set to 360×812 (phone width < 768px).
2. Navigate to `http://localhost:3000/dashboard/vulnerabilities`.
3. Confirm the bottom-nav (4-slot fixed bar) is visible at the bottom of the screen.
4. Press Tab repeatedly to cycle through all interactive elements on the page.
5. For each focused element: confirm the focus ring is FULLY VISIBLE — not clipped or hidden behind the bottom-nav bar.
6. Scroll the page down to the bottom of the list while Tab-navigating. Verify the last focusable item in the list is still visible above the nav.
7. Repeat on `/dashboard/assets`, `/dashboard/tickets` (these are long lists with many focusable rows).

**Pass criteria:** No focused element is obscured by the fixed bottom-nav at any scroll position at <768px viewport width.

| | |
|---|---|
| **Result** | Pass / Fail |
| **Notes** | (fill in — include any route/element where focus was obscured, or "all clear") |
| **Tester** | (name) |
| **Date** | (date) |

---

## Item 3: No White Flash on Cold Dark-OS `/login` Load

**Requirement:** UX-07-05 / D-10
**Why manual:** Flash-of-unstyled-content (FOUC) is pre-hydration timing. jsdom cannot test
real browser paint timing. The `theme.tsx` + `layout.tsx` head bootstrap script is already
implemented — this is verify-only.

**Steps:**

1. In Chrome DevTools, go to Rendering tab (three-dot menu → More tools → Rendering).
2. Under "Emulate CSS media feature `prefers-color-scheme`" select **dark**.
3. Open Application tab → Storage → clear all `localStorage` for `localhost:3000`.
4. Close DevTools (leave dark emulation active via the Rendering panel if possible), or use an incognito window with OS dark mode enabled.
5. Navigate to `http://localhost:3000/login` with a **hard reload** (Shift+Cmd+R / Shift+Ctrl+R).
6. Watch the page load carefully — specifically the first 100–500ms of paint.
7. Confirm there is NO white flash (white background briefly visible before dark paint).

**Expected behavior:** The page loads directly into the dark theme. The FOUC-prevention blocking script in `layout.tsx` applies the `dark` class before React hydrates.

**Alternative test (more reliable):**
- In macOS System Preferences, set Appearance to **Dark**.
- Clear localStorage on `localhost:3000`.
- Hard-reload `/login` in Safari.app (no DevTools emulation involved).
- Observe: no white flash.

**Pass criteria:** No white flash visible on cold dark-OS `/login` load. Page paints dark on first frame.

| | |
|---|---|
| **Result** | Pass / Fail |
| **Notes** | (fill in — include browser used, OS dark mode method: system / DevTools emulation) |
| **Tester** | (name) |
| **Date** | (date) |

---

## Sign-Off

- [ ] Item 1 — Safari.app severity glyphs: **Pass**
- [ ] Item 2 — Focus-not-obscured by bottom-nav: **Pass**
- [ ] Item 3 — No white flash dark-OS cold load: **Pass**

**All items resolved by:** (name)
**Date:** (date)

> After completing all three items, update `15-PERF-REPORT.md` sign-off section
> and type "approved" to the GSD agent to continue to phase completion.
