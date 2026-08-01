# Phase 28: Eval + Cost + Observability Gate — Discussion Log

**Date:** 2026-08-01
**Mode:** discuss (default)

Human-reference record. Not consumed by downstream agents (they read 28-CONTEXT.md).

## Central tension surfaced
BYOK = no GetVul Anthropic key, including in CI. DeepEval/promptfoo traditionally call an LLM. How the CI gates run keyless drove Q1.

## Areas discussed (all 4 presented gray areas)

### 1. Keyless-CI eval + red-team execution (AIE-01/02)
Options: (A) two-tier — deterministic gates in CI, live evals key-gated & non-blocking [recommended]; (B) full LLM-judge in CI via a GetVul eval-only key; (C) local-only, CI just checks harness exists.
**Selected: A** → D-01/D-06. Blocking CI gates are deterministic/no-model-call (schema/grounding/citation/no-rank/no-PII/cite-or-refuse + injection-as-data static inspection); LLM-judge live evals are opt-in key-gated non-blocking.

### 2. Golden-set sourcing (AIE-01)
Options: (A) curated captured real outputs as committed fixtures [recommended]; (B) synthetic/hand-authored; (C) generate on-demand from a dev key.
**Selected: A** → D-02/D-07. Real Phase 24-27 outputs, redacted to a synthetic tenant, committed as JSON; capture is a one-time documented dev-key op.

### 3. Cost circuit-breaker delta (AIE-03)
Options: (A) global degrade + no-bypass coverage test + release-gate [recommended]; (B) reuse guard as-is + coverage test only; (C) full token-bucket rework.
**Selected: A** → D-04/D-09. Persistent per-tenant breaker degrades every AI surface to deterministic-only; coverage test proves no call bypasses the guard; unified degraded state, built on the existing check_tenant_budget guard.

### 4. Admin usage/cost + settings UI (AIE-04)
Options: (A) new AI settings pane: usage/cost + consolidated key/model/budget [recommended]; (B) usage view only, settings stay on connectors card; (C) minimal widget in audit-log pane.
**Selected: A** → D-05/D-08. Dedicated admin AI pane: month-to-date cost vs budget + per-capability usage + breaker status (from existing audit rows) + consolidated key/model/budget.

## Carried forward (not re-asked)
D-06/07/08 (budget guard + admin alert), D-27 (audit rows), D-25 (degraded-state vocabulary), AI-02 (injection-as-data), the no-rank/no-PII/cite-or-refuse schema contracts, the settings-pane + RBAC pattern.

## Deferred
LLM-judge as CI-blocking gate → OUT (opt-in key-gated tier); GetVul-owned eval/CI key → OUT (privacy guarantee); token-bucket breaker → OUT; AINL-01 → v3.1; new telemetry backend → OUT.

## Claude's discretion
Golden-fixture count/capabilities; promptfoo-proper vs a lighter keyless static-assert harness for the blocking red-team tier; breaker state derived-vs-persisted; usage-view metrics/layout (UI-SPEC).
