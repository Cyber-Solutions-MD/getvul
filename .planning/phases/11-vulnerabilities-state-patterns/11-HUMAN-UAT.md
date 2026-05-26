---
status: partial
phase: 11-vulnerabilities-state-patterns
source: [11-08-PLAN.md, 11-VALIDATION.md]
started: 2026-05-26T14:30:00Z
updated: 2026-05-26T14:30:00Z
---

# Phase 11 — Human UAT Checklist

**Reviewer:** ____________________  **Date:** ____________________
**Build:** `git rev-parse --short HEAD` → ____________________

Mirrors Phase 10's `10-HUMAN-UAT.md`. Covers the 8 manual-only verifications from `11-VALIDATION.md` §Manual-Only Verifications. All items must be ✓ before phase signoff.

## Setup
1. `cd backend && uvicorn app.main:app --reload` against a seeded dev DB with ≥100 vulnerabilities + 4 connectors (Qualys + Tenable + AWS Inspector + a fourth)
2. `cd frontend && npm run dev`
3. Open Chrome at `http://localhost:3000/dashboard/vulnerabilities` (logged in as analyst)

## Current Test

[awaiting human testing]

## Tests

### 1. Sunset visual continuity vs Phase 10 (D-S-06)
expected: No regression in the dashboard's visual hierarchy; only loading shimmer + error chrome changed after retrofit.
checks:
- [ ] Open `/dashboard` (Phase 10) — observe Top-5 card loading + error appearance (now using SkeletonTable + PartialFailureBanner)
- [ ] Visually compare against Phase 10 baseline screenshot — visual continuity check
- [ ] Confirm onboarding-panel (`no_scanners` / `no_data_yet`) still renders identically post-retrofit
result: [pending]

### 2. 420px drill panel layout vs sketch-003 variant C (UX-03-03)
expected: Panel layout matches sketch within rendering tolerance.
checks:
- [ ] Open `/dashboard/vulnerabilities?cve=CVE-2024-3094&open=drill` (or any seeded CVE)
- [ ] Side-by-side compare against `.claude/skills/sketch-findings-getvul/sources/003-vulnerabilities-sunset/index.html` (variant C — chosen)
- [ ] Verify: 420px width, right-side aside, panel sections in order (CVSS → Hosts → Description → Remediation → Activity → Actions), close × button top-right, severity pill + KEV badge + exploit badge in header
result: [pending]

### 3. vaul mobile bottom-sheet on real device (UX-03-06)
expected: Smooth drag gesture, no jank, focus correctly returns after close.
checks:
- [ ] Open the page on a real mobile device (iPhone Safari + Android Chrome) OR via Chrome DevTools device emulation set to iPhone 14 Pro (390px width)
- [ ] Tap a row → drill panel slides up from bottom as a vaul `Drawer.Root`
- [ ] Swipe down → drawer closes
- [ ] Tap × in drawer → drawer closes
- [ ] Esc on connected keyboard → drawer closes
- [ ] In drawer, tap "Create ticket" → confirmation appears
result: [pending]

### 4. Empty-state copy voice + tone (UX-S-02 + copy-voice.md)
expected: Tone matches `copy-voice.md` exemplar — peer, not butler.
checks:
- [ ] Apply 5 filters that produce zero results (e.g., search "hyperion" + Critical + High + CISA KEV + Tenable source)
- [ ] Read the EmptyState aloud
- [ ] Verify: title is sentence case (NO exclamation, NO "Welcome", NO "Please")
- [ ] Body explains WHY (the conjunction that produced zero)
- [ ] Violet lightbulb suggestion is informative, not pity
- [ ] 3 CTAs at 3 tiers: Clear all (primary gradient) / Broaden one axis / Search all sources
result: [pending]

### 5. Screen-reader announcements (D-S-07 + UX-07-03 partial)
expected: All ARIA roles/labels exercised; no double-announcement; no focus traps.
checks:
- [ ] On macOS: enable VoiceOver (⌘F5); on Windows: enable NVDA
- [ ] Navigate to `/dashboard/vulnerabilities`
- [ ] Verify announcement: "Loading vulnerabilities" (SkeletonTable `aria-busy="true"`) while loading
- [ ] After load, tab into the table — first row announced with severity + CVE + asset
- [ ] ArrowDown → next row announced
- [ ] Enter → "dialog Vulnerability detail" announced; focus on Close button
- [ ] If a connector fails: PartialFailureBanner announced as alert
- [ ] PerSourceStatusStrip updates announced politely (no focus steal)
result: [pending]

### 6. Forced-colors-mode preservation (Phase 9 a11y carryover)
expected: No invisible UI in forced-colors mode.
checks:
- [ ] Enable Windows High Contrast OR Edge "Force Colors" devtools toggle
- [ ] Verify: severity glyphs (■ ▲ ◆ ○) survive grayscale (glyph + color encoded)
- [ ] Verify: SkeletonTable rows still perceivable (borders survive forced-colors)
- [ ] Verify: PartialFailureBanner amber chrome maps to system colors cleanly
- [ ] Verify: focus rings remain visible on chip-bar + table rows + drill panel
result: [pending]

### 7. Reduce-motion shimmer suppression (Phase 9 a11y carryover)
expected: All animations halted; visual shape preserved.
checks:
- [ ] OS-level: macOS System Settings → Accessibility → Display → Reduce motion ON; OR Chrome DevTools → Rendering → "Emulate CSS prefers-reduced-motion: reduce"
- [ ] Reload `/dashboard/vulnerabilities` during the loading state
- [ ] Verify: SkeletonTable shimmer animation STOPS (gradient stays static — `motion-safe:animate-shimmer` is gated)
- [ ] Verify: pulsing dot on dashboard hero stops
- [ ] Verify: gradient-mesh drift on /login stops
result: [pending]

### 8. Real-world filter + pagination performance @ 2k vulns (D-T-03 sanity)
expected: No visible jank; render times remain <100ms per interaction; no need for virtualization (validates D-T-03 deferral).
checks:
- [ ] Seed dev DB with 2,000 vulnerabilities
- [ ] Profile the vulnerabilities page with React DevTools profiler
- [ ] Apply Critical filter → measure render time
- [ ] Toggle through 5 pages of pagination
- [ ] Open drill panel on the 47th row of page 3
result: [pending]

## Summary

total: 8
passed: 0
issues: 0
pending: 8
skipped: 0
blocked: 0

## Gaps

## Sign-off

- [ ] All 8 items above PASS
- [ ] No regressions observed in Phase 9 / Phase 10 surfaces
- [ ] Sketch fidelity confirmed visually

**Reviewer signature:** ____________________

**Notes / Issues:**
