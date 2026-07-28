# API Coverage — Anthropic SDK

> Full coverage by default. Opt-outs are explicit, reasoned decisions.
> Phase 24 integrates the Anthropic Python SDK (`anthropic>=0.120.0`). This matrix enumerates
> the SDK capability surface this phase touches and decides each, starting from INTEGRATE.
> Validated at seal time by `api-coverage.verify-pre`.

| capability | decision | reason |
|---|---|---|
| `messages.stream` (async streaming context manager) | INTEGRATE | Core of AI-03 — `client.messages.stream(...)` consumed server-side via `await stream.get_final_message()` inside the buffer-then-validate-then-replay engine (`app/ai/explain.py`). |
| `messages.count_tokens` | INTEGRATE | D-04 test-before-save: the free (non-billed) validation call in `test_anthropic()` that authenticates a tenant key without spending on inference. |
| structured outputs (`output_config.format`, `type: json_schema`) | INTEGRATE | AI-02 schema gate — `ExplainVulnResponse.model_json_schema()` passed as the `json_schema` constraint on every explain call; guarantees structural JSON compliance before the Pydantic re-validation gate. |
| `output_config.effort` | INTEGRATE (fixed `"low"`) | D-01/AI-SPEC §4 — fixed at `"low"` for this bounded extraction task; a Wave-0 live smoke-test confirms/branches Haiku support (RESEARCH Pitfall 1) before the Haiku dropdown option ships. |
| `Message.usage` (input/output/cache tokens) | INTEGRATE | AI-06 audit + D-06 budget — per-call token counts drive the audit row's `cost_estimate_usd` and the `SUM`-over-audit-log budget guard. |
| model selection (`claude-sonnet-5` / `claude-opus-5` / `claude-haiku-4-5`) | INTEGRATE | D-01 tenant-wide model dropdown; default `claude-sonnet-5`. Model is a `config` JSONB field on the ANTHROPIC `ConnectorConfig` row and a cache-key component. |
| `AsyncAnthropic(api_key=..., http_client=...)` per-request client | INTEGRATE | BYOK boundary (AI-01) — fresh per-request client from the Fernet-decrypted key, never a module-level singleton (AI-SPEC Pitfall 3). `http_client` override is the test seam (`httpx.MockTransport`). |
| SDK built-in retry / backoff (`Retry-After` on `RateLimitError`) | INTEGRATE | D-25 — rely on the SDK's built-in `max_retries` backoff for 429s; surface a typed "AI busy" state only on persistent failure. |
| error handling (`APIStatusError`, `APIConnectionError`, `RateLimitError`, `AuthenticationError`) | INTEGRATE | Maps to typed UI states (budget/busy/unknown) and the tester's invalid-key result; every path audit-logged. |
| corrective one-shot retry on `ValidationError` / `grounded=false` | INTEGRATE | D-26 / AI-SPEC §4b — invisible-to-analyst single corrective turn, both attempts audit-logged with distinct `status`. |
| Anthropic server-side prompt caching (`cache_control`) | OPT-OUT | not needed yet — GetVul's own tenant-scoped Redis exact-match cache (AI-05) covers this phase; server-side prompt caching is a later cost-optimization lever (revisit under load / Phase 28). |
| `messages.parse` (non-streaming pre-parsed helper) | OPT-OUT | not needed yet — AI-03 mandates the streaming path; the SDK's `parse()` convenience only documents non-streaming, so we accumulate + `model_validate_json` explicitly instead. |
| Message Batches API | OPT-OUT | not needed yet — bulk offline generation is Phase 26 (AIP-02); Phase 24 is request-path only. |
| Files API | OPT-OUT | not needed yet — no file upload/attachment workload; grounding is SQL-join records, not documents. |
| extended thinking / reasoning blocks | OPT-OUT | not needed yet — a bounded extraction+summary task at `effort:"low"`; extended thinking adds latency/cost against the drill-panel latency budget (AI-SPEC §4). |
| tool use / function-calling (`tools` + `tool_choice`) | OPT-OUT | not needed yet — single grounded generation, no agent loop (AI-SPEC §2); bounded function-calling is deferred to later phases (e.g. AINL-01, v3.1). Untrusted data is delivered as a `tool_result`-shaped user block, not via the tools API. |
| `anthropic[aiohttp]` async backend | OPT-OUT | not needed yet — default httpx backend is sufficient for initial ship; add once under real concurrent analyst traffic (AI-SPEC / RESEARCH Standard Stack note). |
| embeddings / Voyage / vector search | OPT-OUT | milestone out-of-scope — no RAG/embeddings this milestone (REQUIREMENTS "Out of Scope"); exact-match tenant-scoped cache only. |
| Admin API / usage & cost reporting API | OPT-OUT | not needed yet — usage/cost is derived from GetVul's own `audit_logs` (AI-06); the admin usage/cost dashboard is Phase 28 (AIE-04). |
