---
status: pending
phase: 10-dashboard
source: [10-VALIDATION.md, 10-CONTEXT.md]
created: 2026-05-15
---

# Phase 10 — HUMAN UAT Checklist

**Phase:** 10 — `/dashboard`
**Scope:** Manual verifications that automated tests cannot cover.
**Tester:** Igor (igorchemencedji@parity.io) or designated reviewer.
**Pre-requisites:**

- Full vitest suite green: `cd frontend && npm run test -- --run` exits 0
- Full pytest suite green: `cd backend && pytest -x` exits 0
- `cd frontend && npm run build` exits 0
- `cd frontend && npm run build 2>&1 | node scripts/check-bundle.mjs --route /dashboard --max-kb 180` exits 0
- Backend seed data available so `/dashboard` renders something meaningful (use `install.sh` seed or `seed_data.py`)

> Voice contract: `.claude/skills/sketch-findings-getvul/references/copy-voice.md`. The visual contract: `.claude/skills/sketch-findings-getvul/sources/002-dashboard-sunset/index.html` — switch to **variant B** in the sketch shell selector.

---

## 1. Visual fidelity to sketch 002 variant B

**Why manual:** Pixel-eye-checking against the locked design contract. Automated tooling cannot catch palette drift, rhythm errors, or animation feel.

### 1.1 Hero block

Open `/dashboard` at 1280×800 (DevTools device toolbar). Open `.claude/skills/sketch-findings-getvul/sources/002-dashboard-sunset/index.html` in a second window and switch to **variant B** if a variant selector exists in the sketch shell.

- [ ] Pulsing-dot eyebrow is `--color-severity-critical` red when criticalOpen > 0. Verify with a seeded dataset (`seed_data.py` ships ~3+ open-critical CVEs).
- [ ] Pulsing-dot animation feels intentional — not jittery, not too fast. Roughly 1.2–1.6s cycle.
- [ ] Headline reads exactly "3 critical CVEs need your eyes" (or "1 critical CVE needs your eyes" for singular). No exclamation, no "Welcome".
- [ ] Sub-line follows the verbatim shape: "Top one is on <host> — <path>, CVSS <cvss>, exploited in the wild." Truncates to 2 lines with `…` on overflow; hovering shows the full string via title attribute.
- [ ] Hostnames + paths render in JetBrains Mono (`--font-mono`).
- [ ] CTA pair: "Start triage" (`cta` variant, sunset gradient, Zap icon left) + "Snooze 1h" (secondary variant, Clock icon left).
- [ ] CTAs side-by-side at ≥640px; stack at <640px.
- [ ] On hover, "Start triage" sunset gradient shifts subtly (per visual-language.md CTA chrome).

### 1.2 Stat strip

- [ ] 4 tiles in one row at ≥1280px; 2 cols at 768–1279px; 1 col at <640px.
- [ ] Tile labels uppercase + tracking-wide; values mono + tabular-nums.
- [ ] Delta row reads "▲ +N from yesterday" (red, "up is bad") OR "▼ -N from yesterday" (green, "down is good"). Direction-aware coloring per D-S-03.
- [ ] MTTR · 30d tile shows the value but NO delta row (Plan 01 ships `mttr_30d.delta = null` in Phase 10).
- [ ] When `delta=null` on `critical_open` (fresh tenant, <7 days of DailySnapshot history), the tile shows "Δ —" instead of a number. Reproduce by clearing DailySnapshot or seeding a fresh tenant.
- [ ] Each tile has a muted 16px lucide icon top-right: ShieldAlert (critical_open) / Clock (sla_at_risk) / Flame (kev) / TrendingDown (mttr_30d).

### 1.3 Trend chart

- [ ] Chart renders below the stat strip with stacked bars in 4 severity colors: ■ critical · ▲ high · ◆ medium · ○ low.
- [ ] Range toggle (7d / 30d / 90d) is a 3-segment control in the chart header. Active segment has `aria-pressed="true"` styling.
- [ ] Hovering a bar nudges it up ~2px AND scales ~1.04 (D-C-04).
- [ ] Tooltip shows severity glyphs + counts; rightmost bar's tooltip reads "Today (so far)" instead of a date.
- [ ] X-axis labels: short month + day; Y-axis labels right-aligned in mono.
- [ ] 4 gridlines at desktop, 2 at <640px.
- [ ] Y-axis scales to the nearest 10 above peak.

### 1.4 Top 5 to triage

- [ ] Exactly 5 rows (or fewer if there are <5 open vulns, padded per D-T-04).
- [ ] Each row: severity glyph + colored CVE id (mono) + asset (mono) + CVSS score (mono) + SLA pill on the right.
- [ ] SLA pill colors: red-soft = breached; amber-soft = at-risk (<72h); green-soft = healthy; surface-2 = unknown.
- [ ] Clicking a row navigates to `/dashboard/vulnerabilities?cve=<id>&open=drill`. Expected to land on the still-v1-styled vulnerabilities page until Phase 11 honors `?open=drill` — see §9 stubs.

### 1.5 Activity rail

- [ ] At ≥1280px: 340px column on the right, sticky — scrolls with page, no independent scrollbar.
- [ ] At <1280px: full-width section below the main column with a visible h2 "Recent activity".
- [ ] Each item: 28px tinted icon square + title + body + relative time ("12m ago" / "2h ago" / "3d ago").
- [ ] Icon tints: pink for `new_critical_vuln`; amber for `sla_breach`; violet for `sync_failure`; success-green for `risk_change`.
- [ ] Empty state copy reads exactly: "No recent activity. We'll show events here as they happen." No exclamation. No "Welcome".

---

## 2. Forced-colors mode (D-Ax-06)

**Why manual:** Browser DevTools toggle; no automated way to exercise real OS HC theme.

- [ ] DevTools → Rendering → Emulate CSS media feature `forced-colors: active`.
- [ ] Severity stack still conveys rank via tooltip glyphs (■ ▲ ◆ ○) AND the visually-hidden `<table>` below the chart.
- [ ] CTA buttons remain readable (system `ButtonFace` / `ButtonText`).
- [ ] Pulsing dot still visible (red or green; OS may override but the glyph remains).
- [ ] No section disappears or becomes invisible.
- [ ] Tab back through every interactive element — focus rings visible against the system theme.

---

## 3. Keyboard navigation

**Why manual:** Tab order + focus ring visibility require human judgment.

- [ ] Press Tab from the URL bar — focus lands on the skip-link (Phase 9 shell chrome).
- [ ] Activate skip-link → focus jumps to `<main>` (dashboard content).
- [ ] Tab order matches reading order: Hero CTAs (Start triage → Snooze 1h) → range toggle (7d/30d/90d) → Top-5 rows (each link focusable) → Activity rail rows.
- [ ] Focus rings remain visible at each step against the sunset palette.
- [ ] Enter activates each CTA; Space activates the range-toggle buttons.
- [ ] Escape on the Snooze toast (if focusable while live) dismisses the toast.
- [ ] Sidebar nav chips (Vulnerabilities / Assets / Tickets) are NOT separately tabbable — they're inside the Link, the Link is the single focusable target.

---

## 4. Reduce-motion (D-Ax-04)

**Why manual:** "Color stays, animation stops" must look intentional. `prefers-reduced-motion: reduce` is the trigger.

- [ ] macOS System Settings → Accessibility → Display → Reduce motion → enabled (or DevTools → Rendering → Emulate CSS media feature `prefers-reduced-motion: reduce`).
- [ ] Reload `/dashboard`.
- [ ] Pulsing dot becomes solid (no pulse) — color stays.
- [ ] Trend chart bars render at final height immediately — no rise animation.
- [ ] Stat tile counters show final number immediately — no count-up.
- [ ] Hover nudge on chart bars is absent (`translateY=0`) — color tint still appears.
- [ ] CTA hover gradient shift is reduced or eliminated.

---

## 5. Performance — CLS (Cumulative Layout Shift)

**Why manual:** Requires DevTools Performance trace.

- [ ] DevTools → Performance → Record.
- [ ] Hard-reload `/dashboard` (Cmd+Shift+R).
- [ ] Stop recording after first paint completes (~3s).
- [ ] CLS ≤ 0.1 (acceptable per Web Vitals baseline; D-Perf-02 sets it as soft target).
- [ ] Common offenders to spot-check:
  - Skeleton-to-real swap on the hero — final height must match skeleton height.
  - Sidebar chip swap from `—` to a number — D-N-03 keeps chip width stable; with 3-digit counts, no shift expected.
  - Stat strip skeleton → real number — tabular-nums + monospace prevents glyph-width shift.
- [ ] Record exact CLS value in `10-06-SUMMARY.md` testers-notes for reference.

---

## 6. First-Load JS budget

**Why manual:** Captures the verification number for the SUMMARY.

- [ ] Run `cd frontend && npm run build`.
- [ ] Read the "First Load JS" column on the `/dashboard` row.
- [ ] Confirm value ≤ 180 kB.
- [ ] Record exact value in `10-06-SUMMARY.md` (e.g., "First-Load JS on /dashboard: 173 kB").
- [ ] Run `cd frontend && npm run build 2>&1 | node scripts/check-bundle.mjs --route /dashboard --max-kb 180` — must exit 0.
- [ ] Confirm recharts is NOT in the "First Load JS shared by all" chunk list — it should appear in a route-specific chunk for `/dashboard` only (D-C-03 dynamic import).

---

## 7. Cross-browser smoke (D-Ax-07 + Phase 15 prep)

**Why manual:** axe-core in jsdom does not test real browser rendering.

- [ ] Open `/dashboard` in Chrome latest, Safari latest, Firefox latest at 1280px.
- [ ] Severity glyphs (■ ▲ ◆ ○) render legibly at 14px in each browser.
- [ ] Sunset gradient on the "Start triage" CTA renders identically across browsers (no banding, no fallback solid color).
- [ ] Mono identifiers (CVE ids, hostnames, paths) use JetBrains Mono in each browser.
- [ ] Sidebar count chips render the same numeric value in each browser (cache stays warm; first navigation does not re-fetch).

---

## 8. Copy-voice audit

**Why manual:** Forbidden tokens are easy for tooling to miss in dynamic strings.

- [ ] No occurrence of "Please", "Welcome", or "Click here" anywhere on the rendered page.
- [ ] No exclamation marks in user-facing copy. (Decorative copy in Phase 11+ chip-bar interactions may use them sparingly; Phase 10's dashboard has none.)
- [ ] All numbers render in numerals (e.g., "3 critical CVEs", not "Three critical CVEs").
- [ ] Sentence case on every heading and CTA (e.g., "Start triage", not "Start Triage"; "Today at a glance", not "Today At A Glance").
- [ ] Snooze toast copy matches the verbatim exemplar: `Snoozed CVE-… for 1h · Undo`.
- [ ] Activity-rail empty state matches verbatim: `No recent activity. We'll show events here as they happen.`

---

## 9. Known Phase 10 stubs (NOT bugs)

These behaviors are intentional. The CONTEXT `<domain>` Out-of-scope section lists them. Document any "this link doesn't work" feedback as future-Phase-11 scope.

- [ ] Top-5 row clicks navigate to `/dashboard/vulnerabilities?cve=…&open=drill` but do NOT open a drill panel — expected, Phase 11 owns the drill.
- [ ] Activity rail row clicks navigate to vuln / ticket / connector / asset routes; those routes still render in v1 styling — expected.
- [ ] `⌘K` command palette is still a visual scaffold (Phase 9 D-37 carryover) — expected, Phase 14+ wires it.
- [ ] Light theme is disabled in UserChip (`In progress` badge) — D-06 / UX-D-03 territory, not Phase 10.

---

## 10. Regression sanity (Phase 9 preservation)

**Why manual:** Confirms the Phase-10 sidebar wiring change did not break Phase 9 behavior.

- [ ] Navigate back to `/login` (sign out via UserChip) — `/login` still renders the split-screen sunset shell from Phase 9; no errors in console.
- [ ] Sign back in — land on `/dashboard` per D-50 default; sidebar Dashboard nav item active (D-35 exact match).
- [ ] Navigate to `/dashboard/vulnerabilities` — Vulnerabilities nav active per D-35; sidebar chip on the same item shows the live count from `useStats()`.
- [ ] Open DevTools Network panel; record. Navigate `/dashboard` → `/dashboard/vulnerabilities` → `/dashboard/assets` → `/dashboard/tickets` → `/dashboard`. Observe: exactly ONE `/api/v1/vulnerabilities/stats` request during a 60-second window (D-D-06 staleTime; D-D-12 may add one on focus regain).
- [ ] Theme toggle still works (Theme: Dark) — UserChip Dark radio stays enabled per Phase 9 WR-03 mitigation.

---

## Sign-off

- [ ] Sections 1–8 all pass.
- [ ] Section 9 stubs documented in tester notes (not flagged as bugs).
- [ ] Section 10 regression sanity passes — Phase 9 behavior intact.

**Approved by:** _________________ **Date:** _________________
