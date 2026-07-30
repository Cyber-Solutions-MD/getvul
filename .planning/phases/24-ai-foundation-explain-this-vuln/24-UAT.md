---
status: partial
phase: 24-ai-foundation-explain-this-vuln
source: [24-VERIFICATION.md]
started: 2026-07-29T00:00:00Z
updated: 2026-07-30T00:00:00Z
note: "All 4 items were EXPLICITLY WAIVED by the user at the 24-06 TRACER-gate checkpoint ('skip live verify, proceed on trust'). Every code-verifiable check passes (12/14 truths; truth #2 closed by gap plan 24-10). These 4 require a live Docker/nginx stack + a dev Anthropic key and can only be confirmed by human observation."
---

## Current Test

[testing paused — all 4 items blocked on prerequisites (dev Anthropic key, clean single-project Docker stack, browser automation). Re-run /gsd-verify-work 24 once those are available.]

## Tests

### 1. AI-03 nginx anti-buffering through the real proxy
expected: SSE frames arrive progressively through nginx (not buffered-then-dumped). nginx.conf has `proxy_buffering off` in both server blocks (structurally verified); live behavior unobserved.
result: blocked
blocked_by: other
reason: "Attempted live on 2026-07-29: brought up getvul backend (healthy) but nginx crash-loops on `host not found in upstream \"frontend\"` — this machine has a tangled two-project Docker state (getvul containers split across networks; getvul-frontend fights the unrelated security-intelligence project for :3000). Getting nginx healthy needs either editing nginx.conf (the file under test) or `docker compose down` on the user's other running project — both too intrusive to do unprompted. AI-03's assertion requires nginx IN the path, so a backend-direct curl (no published host port anyway) would not satisfy it. Partial evidence stands: `proxy_buffering off` present in both server blocks + the spike endpoint sets `X-Accel-Buffering: no` and yields 4 frames 0.5s apart by design. Needs a clean single-project stack to observe live."

### 2. Live end-to-end tracer (wizard → save → explain → cache → audit row)
expected: Admin configures a key via the wizard → save → Analyst clicks Explain → validated cited summary streams in → re-open renders from cache → an `ai.explain.vuln` row (model/tokens/cost/status, attributed to analyst+tenant) appears in the settings audit-log pane.
result: blocked
blocked_by: third-party
reason: "No dev Anthropic key is provisioned in this environment (GETVUL_DEV_ANTHROPIC_KEY unset — confirmed by env scan, consistent with the 24-01 finding). Without a real key the Explain path returns a `no_key` short-circuit instead of a streamed cited summary, so the wizard→explain→cache→audit flow cannot produce real content to observe. Needs a dev/tenant Anthropic key."

### 3. D-25 persistent-429 'AI busy' amber card in the live UI
expected: Forcing a persistent Anthropic 429 on an uncached finding produces the amber "AI busy — try again in a moment" card with a working "Try again" button — not a generic error, blank panel, or partial text.
result: blocked
blocked_by: third-party
reason: "Requires either a real Anthropic key at/over its rate limit or a mock transport returning 429 wired into a live stack — neither is available here (no key; no 429-mock harness in the running stack). Backend emitting {type:error,kind:busy} on persistent 429 and the frontend rendering the amber card for kind=busy are both proven by automated tests; only the live-triggered visual confirmation is outstanding."

### 4. Live RBAC states + reduced-motion/contrast in a real browser (dark + light)
expected: Role-gated states render as coded (Analyst/Viewer/keyless — now backed by GET /api/v1/ai/status per gap plan 24-10); violet-on-soft citation tint legible in both themes; prefers-reduced-motion disables the token-by-token reveal.
result: blocked
blocked_by: other
reason: "No browser/Playwright MCP is available in this session, so live visual + a11y (axe contrast, prefers-reduced-motion) observation cannot be performed. The underlying logic is more strongly proven at code level than at initial verification: gap plan 24-10 added the real GET /api/v1/ai/status signal + a 4-role×config matrix, and reduced-motion branching is unit-tested (mocked matchMedia). Only the live-browser visual/a11y observation remains open."

## Summary

total: 4
passed: 0
issues: 0
pending: 0
skipped: 0
blocked: 4

## Gaps

[none — the 4 items are blocked prerequisites (no dev Anthropic key, no clean single-project Docker stack, no browser automation), not code defects. Blocked items do not spawn gap plans.]
