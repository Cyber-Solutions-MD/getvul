---
status: testing
phase: 28-eval-cost-observability-gate
source: [28-VERIFICATION.md]
started: 2026-08-03T13:10:00Z
updated: 2026-08-03T13:10:00Z
---

## Current Test

number: 1
name: Visually verify the admin AI usage & settings pane (light + dark) against 28-UI-SPEC.md
expected: |
  /dashboard/settings?category=ai as a tenant admin renders the 4-card layout, spacing,
  and breaker-banner anchor position pixel/token-accurate to the design system — with a
  Playwright + axe accessibility sweep passing (no unverified visual/a11y claims).
awaiting: user response

## Tests

### 1. Admin AI usage & settings pane — live visual + a11y
expected: Open `/dashboard/settings?category=ai` as a tenant admin in a live browser (light + dark theme). The 4-card layout, spacing, and breaker-banner anchor position match 28-UI-SPEC.md; a Playwright + axe sweep passes. (Only jsdom unit tests ran this phase — 10/10 pass — no live browser render/screenshot/axe sweep was executed; see lesson getvul-axe-sweep-not-run-during-exec.)
result: [pending]

### 2. Opt-in key-gated live CI tier (`ai-live-eval-optin`) — real run
expected: Configure a `DEV_ANTHROPIC_API_KEY` repository secret, author the deliberately-unscaffolded `backend/tests/evals/test_llm_judge_evals.py` and `redteam/promptfooconfig.yaml`, and observe a real run of the `ai-live-eval-optin` job — runs the real DeepEval LLM-judge suite + real promptfoo redteam, `continue-on-error: true`, never blocks, never runs on fork PRs. (Only structural YAML correctness — gating, fork-guard, non-blocking flag — was provable in the sandbox.)
result: [pending]

### 3. Merge-blocking observed on a real GitHub PR
expected: Push this branch and open a real PR against the origin repo. A deliberately-broken golden fixture or injection-isolation regression causes `AI Golden-Set Evals (DeepEval)` / `AI Prompt-Injection Red-Team (static)` to fail and the PR to be blocked from merging. (branch-protection.json is verified byte-correct and the repo's own "docs job is non-required" precedent proves the mechanism, but a live block has not been observed — local `main` is ~400+ commits ahead of origin/main.)
result: [pending]

### 4. Live budget-exceeded degradation end-to-end
expected: In a live tenant session, exceed the configured AI budget and confirm every AI surface (explain vuln/host/remediation/remediation-guidance/prioritization, ticket drafting) degrades to deterministic-score-only in the running UI, and the admin pane's breaker banner ("AI paused — budget exceeded") appears within the same session. (Guard ordering explain.py:308 before :339 and frontend budget_exceeded handling were confirmed in isolation + the no-bypass coverage test, but the full live cross-stack flow was not exercised.)
result: [pending]

### 5. Policy decision — golden-fixture provenance
expected: Decide whether the hand-authored (non-model-captured) golden fixtures are acceptable to close AIE-01, or whether milestone close should be gated on a real `capture_ai_goldens.py` run first. Accept the documented fallback via a formal override, OR schedule a follow-up to run the fully-built capture script once `GETVUL_DEV_ANTHROPIC_KEY` exists. (Policy/scope decision, not code-correctness — the gate's structural discrimination is independently proven robust either way; the key has been absent since Phase 24-01.)
result: [pending]

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps
