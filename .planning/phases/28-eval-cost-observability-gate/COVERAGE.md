# API Coverage — Anthropic SDK (Phase 28)

> Full coverage by default. Opt-outs are explicit, reasoned decisions.
> Phase 28 (eval / cost-observability / CI gate) introduces **no new external-API surface**.
> The Anthropic Python SDK capability surface is decided in
> [phase 24's COVERAGE.md](../24-ai-foundation-explain-this-vuln/COVERAGE.md), which already
> reasoned this phase's usage/cost work through by name ("the admin usage/cost dashboard is
> Phase 28 (AIE-04)"). This matrix enumerates the only points where phase 28 *touches* that
> surface and confirms each reuses an already-INTEGRATE'd phase-24 capability — no new capability
> is added. Validated at seal time by `api-coverage.verify-pre`.

| capability | decision | reason |
|---|---|---|
| runtime external Anthropic calls in phase-28 shipped code | OPT-OUT | Only shipped route `GET /api/v1/ai/usage` aggregates GetVul's own audit_logs (D-08, no new telemetry) — zero external calls. All runtime Anthropic use stays the phase-24 path. |
| golden-fixture capture (`capture_ai_goldens.py`) | INTEGRATE | One-time dev-only tool (D-07) reusing phase 24's already-INTEGRATE'd `messages.stream` explain path to capture fixtures. Never in runtime or blocking CI; no new SDK capability. |
| opt-in live eval + red-team CI job (`ai-live-eval-optin`) | INTEGRATE | Key-gated, continue-on-error, fork-guarded, non-blocking CI. Exercises the same phase-24 `messages.stream` surface when a key is present; no new capability, no blocking dependency. |
| keyless DeepEval golden-set harness (`tests/evals/`) | OPT-OUT | Non-LLM BaseMetrics call production validation gates directly; zero evaluation_model, zero network, zero API key. No Anthropic surface touched. |
| keyless prompt-injection red-team suite (`test_ai_injection_redteam.py`) | OPT-OUT | Static assertions against prompt builders only — inspects the `<scanner_data>` body shape, never dispatches a request. No external call. |
| no-bypass AI budget coverage gate (`test_ai_budget_coverage.py`) | OPT-OUT | Asserts the mocked SDK client is never constructed when over budget — the SDK path is mocked, never invoked externally. |
| Admin API / Anthropic usage & cost reporting API | OPT-OUT | Declined in phase 24 and unchanged here — the AIE-04 admin pane is derived entirely from GetVul's own audit_logs, not any Anthropic usage/reporting endpoint. |
