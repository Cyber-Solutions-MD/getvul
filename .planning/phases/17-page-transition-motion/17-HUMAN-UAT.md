---
status: resolved
phase: 17-page-transition-motion
source: [21-CONTEXT.md, 17-02-SUMMARY.md]
started: 2026-07-21T12:50:00Z
updated: 2026-07-21T13:15:08Z
---

## Current Test

[complete]

## Tests

### 1. Cross-fade feel (snappy ~220-320ms, pure opacity, no drift)
expected: Content region cross-fades on a sidebar route change — pure opacity, no transform, ~220-320ms per foundation.md §Motion.
result: passed — approved by user 2026-07-21 (Dashboard → Vulnerabilities → Assets cross-fades cleanly on Chromium against the live prod build on :3000)

### 2. Chrome stillness (sidebar/topbar do not move or fade)
expected: During a pathname change the persistent chrome stays fixed; only the content region transitions.
result: passed — approved by user 2026-07-21 (sidebar + topbar remain still across route changes; only the content region transitions)

### 3. DrillPanel-during-transition (open drill fades out with content, no ghost panel)
expected: An open DrillPanel fades out cleanly with the content on a pathname change; no stuck/ghost panel, no layout jump.
result: passed — approved by user 2026-07-21 (drill opened via a row / `?cve=CVE-2024-0001&open=drill`, then a sidebar nav — panel fades out with the content, no ghost panel, no layout jump)

### 4. Firefox cross-fade feel (equivalent clean cross-fade)
expected: On Firefox the transition looks equivalent to Chromium — a clean opacity cross-fade, no jank/broken nav. Note (Phase 21 finding): the installed Firefox now natively supports the View Transitions API, so it exercises the native VT path rather than the `[data-no-vt]` CSS-keyframe fallback; either path must feel equivalent.
result: passed — approved by user 2026-07-21 (Firefox cross-fade is equivalent to Chromium — clean opacity fade, no jank, navigation intact)

## Summary

total: 4
passed: 4
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

None. All four perceptual items signed off by the user on 2026-07-21. No defect surfaced — the transitions match the foundation.md §Motion contract (cross-fade only, no transforms) and the persistent-chrome stillness contract (app-shell.md). The only note is an environment observation, not a defect: the currently installed Firefox natively supports the View Transitions API, so the CSS-keyframe fallback path is not the branch exercised on that engine today (see 21-01-SUMMARY.md and 17-VERIFICATION.md UX-D-06-03 evidence); the fallback code remains correct and necessary for any engine that genuinely lacks VT support.
