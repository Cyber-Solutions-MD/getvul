---
status: testing
phase: 24-ai-foundation-explain-this-vuln
source: [24-VERIFICATION.md]
started: 2026-07-29T00:00:00Z
updated: 2026-07-29T00:00:00Z
note: "All 4 items were EXPLICITLY WAIVED by the user at the 24-06 TRACER-gate checkpoint ('skip live verify, proceed on trust'). Every code-verifiable check passes (12/14 truths; truth #2 closed by gap plan 24-10). These 4 require a live Docker/nginx stack + a dev Anthropic key and can only be confirmed by human observation."
---

## Current Test

number: 1
name: AI-03 nginx anti-buffering through the real proxy
expected: |
  curl -N -H 'Authorization: Bearer <analyst-token>' -X POST http://localhost/api/v1/ai/explain-vuln/<finding_id>
  prints frames progressively (first byte well before the ~2s+ full completion), not all-at-once after full latency.
awaiting: user response

## Tests

### 1. AI-03 nginx anti-buffering through the real proxy
expected: SSE frames arrive progressively through nginx (not buffered-then-dumped). nginx.conf has `proxy_buffering off` in both server blocks (structurally verified); live behavior unobserved.
result: [pending]

### 2. Live end-to-end tracer (wizard → save → explain → cache → audit row)
expected: Admin configures a key via the wizard → save → Analyst clicks Explain → validated cited summary streams in → re-open renders from cache → an `ai.explain.vuln` row (model/tokens/cost/status, attributed to analyst+tenant) appears in the settings audit-log pane.
result: [pending]

### 3. D-25 persistent-429 'AI busy' amber card in the live UI
expected: Forcing a persistent Anthropic 429 on an uncached finding produces the amber "AI busy — try again in a moment" card with a working "Try again" button — not a generic error, blank panel, or partial text.
result: [pending]

### 4. Live RBAC states + reduced-motion/contrast in a real browser (dark + light)
expected: Role-gated states render as coded (Analyst/Viewer/keyless — now backed by GET /api/v1/ai/status per gap plan 24-10); violet-on-soft citation tint legible in both themes; prefers-reduced-motion disables the token-by-token reveal.
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps
