---
status: partial
phase: 28-eval-cost-observability-gate
source: [28-VERIFICATION.md]
started: 2026-08-03T13:10:00Z
updated: 2026-08-03T16:30:00Z
---

## Current Test

[testing paused — 3 items blocked on external infrastructure]

## Tests

### 1. Admin AI usage & settings pane — live visual + a11y
expected: Open `/dashboard/settings?category=ai` as a tenant admin in a live browser (light + dark theme). The 4-card layout, spacing, and breaker-banner anchor position match 28-UI-SPEC.md; a Playwright + axe sweep passes.
result: pass
note: |
  Verified live (not jsdom). Brought up the docker-compose stack (postgres/redis/backend/frontend),
  created admin@getvul.local (OWNER), seeded an ANTHROPIC connector so the pane renders the CONFIGURED
  4-card layout, and drove a new Playwright axe sweep at ?category=ai in BOTH themes
  (frontend/e2e/ai-usage-pane-a11y.spec.ts).
  Initial run FAILED: 1 serious WCAG 2.1 AA violation in both themes — `aria-progressbar-name` on the
  budget-meter progress bar (Radix `role=progressbar` with no accessible name), SC 1.1.1. This is exactly
  the unproven-a11y gap this test existed to catch (only jsdom unit tests had run during execution).
  FIXED inline: added an `aria-label` to the `<Progress>` budget meter in ai-usage-pane.tsx. Re-ran the
  sweep — 4-card layout renders and axe WCAG 2.1 AA passes clean in dark + light. Pane unit tests still 10/10.
  See resolved gap G-28-1 below.

### 2. Opt-in key-gated live CI tier (`ai-live-eval-optin`) — real run
expected: Configure a `DEV_ANTHROPIC_API_KEY` repository secret, author the deliberately-unscaffolded `backend/tests/evals/test_llm_judge_evals.py` and `redteam/promptfooconfig.yaml`, and observe a real run of the `ai-live-eval-optin` job — runs the real DeepEval LLM-judge suite + real promptfoo redteam, `continue-on-error: true`, never blocks, never runs on fork PRs.
result: blocked
blocked_by: third-party
reason: "Requires a real DEV_ANTHROPIC_API_KEY repository secret + a live GitHub Actions run to observe. Cannot provision GitHub secrets or trigger real CI from this environment; the referenced test_llm_judge_evals.py / promptfooconfig.yaml are intentionally unscaffolded. Only structural YAML correctness (key-gating, fork-guard, continue-on-error) is provable locally and was already confirmed in 28-VERIFICATION.md."

### 3. Merge-blocking observed on a real GitHub PR
expected: Push this branch and open a real PR against the origin repo. A deliberately-broken golden fixture or injection-isolation regression causes `AI Golden-Set Evals (DeepEval)` / `AI Prompt-Injection Red-Team (static)` to fail and the PR to be blocked from merging.
result: blocked
blocked_by: other
reason: "Requires a real PR against an up-to-date origin. Local main is ~400+ commits ahead of origin/main (origin at PR#12); a PR would be unmergeable and I should not push it. branch-protection.json is verified byte-correct and the repo's own non-required-docs-job precedent proves the mechanism, but a live merge-block cannot be observed here."

### 4. Live budget-exceeded degradation end-to-end
expected: In a live tenant session, exceed the configured AI budget and confirm every AI surface (explain vuln/host/remediation/remediation-guidance/prioritization, ticket drafting) degrades to deterministic-score-only in the running UI, and the admin pane's breaker banner ("AI paused — budget exceeded") appears within the same session.
result: blocked
blocked_by: third-party
reason: "Requires a live Anthropic BYOK key + a real tenant session actually spending inference to trip the fail-closed breaker end-to-end across the stack. No real key is available (BYOK, absent since Phase 24-01). Guard ordering (explain.py) + frontend budget_exceeded handling + the no-bypass coverage test were confirmed in isolation, but the full live cross-stack flow needs a spending key. NOTE: the pane's breaker-banner render path itself is exercised — the seeded-configured 4-card layout in Test 1 renders from the same component (breaker_tripped=false branch)."

### 5. Policy decision — golden-fixture provenance
expected: Decide whether the hand-authored (non-model-captured) golden fixtures are acceptable to close AIE-01, or whether milestone close should be gated on a real `capture_ai_goldens.py` run first.
result: pass
note: |
  DECISION (user, 2026-08-03): ACCEPT the documented hand-authored-fixture fallback as the AIE-01 close
  criterion — a formal override. Rationale: the golden-eval gate's structural discrimination (grounded vs
  insufficient_evidence, schema + business-rule validation) is independently proven robust regardless of
  fixture provenance, and the capture script is built + documented so a future real capture run overwrites
  the same grounding_record inputs with identical shape. No milestone-close gate on a real capture run.

## Summary

total: 5
passed: 2
issues: 0
pending: 0
skipped: 0
blocked: 3

## Gaps

- gap_id: G-28-1
  truth: "The admin AI usage pane's budget meter has an accessible name (WCAG 2.1 AA, SC 1.1.1)."
  status: resolved
  reason: "Live axe sweep found a serious `aria-progressbar-name` violation (Radix role=progressbar with no accessible name) in both themes."
  severity: major
  test: 1
  root_cause: "The budget-meter <Progress> in ai-usage-pane.tsx rendered a Radix progressbar with no aria-label/aria-labelledby/title; only jsdom unit tests ran during execution, so no live axe sweep caught it (see lesson getvul-axe-sweep-not-run-during-exec)."
  artifacts:
    - path: "frontend/src/components/settings/ai-usage-pane.tsx"
      issue: "<Progress> budget meter missing an accessible name"
  missing:
    - "Added aria-label to the <Progress> budget meter describing spent-of-cap and percent used."
  resolved_by: "inline fix during verify-work + new e2e/ai-usage-pane-a11y.spec.ts (dark+light) re-verified clean"
  resolved_at: 2026-08-03
