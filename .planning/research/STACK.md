# Stack Research

**Domain:** Adding Claude-based LLM assistance (summarization, remediation guidance, triage narrative, ticket auto-drafting) to an existing mature FastAPI + Next.js vulnerability-triage platform
**Researched:** 2026-07-25
**Confidence:** MEDIUM-HIGH (model IDs/pricing/caching verified against live `platform.claude.com` docs and PyPI; eval/guardrail library choices verified against PyPI + vendor docs, some claims WebSearch-only and flagged)

> Scope note: this research covers ONLY the net-new AI stack. It does not re-litigate FastAPI/Postgres/Redis/Next.js, which are locked per `CLAUDE.md` and `.planning/PROJECT.md`.

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|------------------|
| `anthropic` (Python SDK) | `>=0.120,<1.0` (latest verified: 0.120.0, released 2026-07-24) | Official Claude API client — sync + async, streaming, prompt caching, token counting, Message Batches | Only first-party, fully-typed client; ships `AsyncAnthropic` which drops straight into the existing `async def` FastAPI route handlers and the asyncio scheduler with no event-loop bridging. HIGH confidence (verified live on PyPI). |
| Claude Sonnet 5 — `claude-sonnet-5` | current (dateless pinned alias per Anthropic's 4.6+ generation versioning) | Default model: remediation guidance, triage narrative, ticket drafting | "Best combination of speed and intelligence" per Anthropic's own model table; 1M context, introductory pricing $2/$10 per MTok through 2026-08-31 (then $3/$15). Sits below Opus on cost, above Haiku on reasoning depth — the right default for most of this milestone's user-facing features. HIGH confidence (verified live on `platform.claude.com/docs/.../models/overview`). |
| Claude Haiku 4.5 — `claude-haiku-4-5` (pinned: `claude-haiku-4-5-20251001`) | current | Cheap, high-volume "Explain this vuln" summaries (one per finding, potentially thousands per tenant per sync cycle) | Fastest + lowest-cost current model ($1/$5 per MTok); 200k context is ample for a single CVE description + host context. This is the model that makes per-finding summarization economically viable at scanner-ingestion scale. HIGH confidence. |
| Claude Opus 4.8 — `claude-opus-4-8` | current, fully supported (dateless alias) | Deep triage reasoning — "what to fix first and why" batch prioritization across exploit/KEV/owner/SLA context; highest-stakes ticket drafts | Highest reasoning tier explicitly named in the milestone brief. **Currency flag (be honest, not stale):** as of this research date Anthropic has already shipped **Claude Opus 5** (`claude-opus-5`) as the new frontier-flagship successor — the live docs list Opus 4.8 under "Legacy models" (still fully supported, NOT deprecated; only Opus 4.1 carries a retirement date). Recommendation: build against `claude-opus-4-8` per the milestone's explicit mandate, but query the [Models API](https://platform.claude.com/docs/en/api/models/list) at deploy time (or re-check `/docs/about-claude/models/overview`) before locking the phase-implementation model ID, since Opus 5 may be the better default by the time this phase executes. MEDIUM confidence on "still correct at execution time" — HIGH confidence on "correct today." |
| DeepEval | `>=4.0.0` (released 2026-07-22) | LLM eval framework — regression-gate the summarizer/remediation/ticket-draft prompts | Python-native, built directly on `pytest` — drops into the exact CI gate GetVul already runs (`ruff`/`mypy`/`pytest`), no new YAML DSL, no new CI runtime. Ships 50+ metrics (answer relevancy, faithfulness/hallucination, G-Eval) plus a `BaseMetric`/`GEval` extension point for a **custom "no hallucinated remediation" metric** (assert the generated remediation only cites facts present in the scanner's own `solution` text) — directly maps to the milestone's named guardrail requirement. See Alternatives for why promptfoo is a *complement*, not the pick. MEDIUM confidence (version/release-date WebSearch-verified, not Context7-verified). |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `redis` (already a backend dependency, `>=5.2`) | existing | Response cache for LLM outputs | No new cache library needed. Two cache tiers, both keyed in the *existing* Redis instance: (1) a **global** cache keyed on `sha256(model_id + normalized_cve_id_or_finding_text)` for CVE/finding explanations — identical CVE text is shared across every tenant, so this tier is deliberately NOT tenant-scoped and gets the highest hit rate; (2) a **tenant-scoped** cache keyed on `sha256(tenant_id + model_id + prompt_hash + grounding_data_version)` for triage narratives and ticket drafts, since those embed tenant-specific asset/owner/SLA context. TTL: 24h for tier 1 (CVE text is近-immutable), shorter (e.g. 1h, or invalidate-on-write) for tier 2 since it's derived from live risk scores. |
| `llm-guard` | `0.3.16` (Python `<3.13,>=3.10` — **flag: caps below the repo's `>=3.12` target but under `<3.13`, compatible with the pinned 3.12 runtime; re-verify before bumping to 3.13**) | Local ONNX `PromptInjection` classifier scanner as one signal (not the sole gate) against attacker-controlled scanner text (CVE descriptions, hostnames, finding titles) before interpolation into a prompt | Runs fully in-process/on-VM (no external call, no data leaves the customer's single-VM deploy — important given GetVul's on-prem-per-customer topology). Use as a *scored signal* feeding an audit-logged flag, not a hard block — false positives on legitimate CVE prose are costly for a triage tool that must never silently drop a real finding. MEDIUM confidence (PyPI-verified version/deps; scanner behavior WebSearch-sourced). |
| `eventsource-parser` (npm, frontend) | `^3.1.0` | Parse the raw SSE byte stream FastAPI proxies from Claude's streaming API into discrete token events for the vuln drill panel / ticket-draft UI | ~3KB, source-agnostic (works against a plain `fetch` + `ReadableStream`, no assumption about who owns the LLM call). Deliberately **not** the Vercel AI SDK (`ai` + `@ai-sdk/anthropic`) — that SDK assumes the Node/Next.js layer calls Anthropic directly, which would create a second, unaudited path to the API key and bypass the tenant-scoping/RBAC/audit-logging that must stay centralized in the FastAPI backend per `CLAUDE.md`'s tenant-isolation constraint. MEDIUM confidence (WebSearch-verified version). |
| `presidio-analyzer` + `presidio-anonymizer` (optional, phase-gated — see "What NOT to Use") | latest (Microsoft, PyPI `presidio` meta-package) | PII detection/redaction on **free-text** fields before they reach a Claude prompt | Only if/when a future phase feeds genuinely unstructured free text (e.g. ticket comments, analyst notes) into a prompt. For this milestone's known, structured HR/MDM/asset fields, a deterministic allow-list (serialize only `owner.display_name` + `owner.team`, never the full enriched DB row) is simpler and more reliable than a probabilistic NER model — see rationale below. Do not add Presidio in the first AI-foundation phase; revisit only if a later phase's grounding data includes real free text. |
| Manual `httpx.MockTransport` injected via `anthropic.AsyncAnthropic(http_client=...)` | N/A (no new dependency) | Test-double Anthropic calls in pytest | The Anthropic SDK is itself httpx-based and accepts a custom `http_client`. This mirrors the exact mocking convention GetVul's connector tests already use (`tests/test_okta_sync.py`, `test_directory_connectors.py`, etc. — direct `httpx.MockTransport`, no `respx`), so no new test dependency is introduced for AI features. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| DeepEval's `deepeval test run` | CI regression gate for prompt/model quality | Wire as a new `pytest` marker/target inside the existing backend CI job (ruff → mypy → pytest), not a separate pipeline — keeps one CI mental model. |
| promptfoo (Node CLI, run as its own CI job) | Adversarial red-team gate: auto-generates jailbreak/prompt-injection/PII-leakage/excessive-agency attacks against the actual system prompts | Run as a **separate** CI job analogous to the existing `semgrep` SAST / OWASP ZAP DAST jobs — same pattern (a security scan gate, not a unit test), self-hosted, no data leaves CI. **Supply-chain note (MEDIUM confidence, WebSearch-only):** OpenAI acquired promptfoo in 2026; it remains open-source/self-hostable under its existing license, so the risk is low, but pin an exact version and re-verify the license/ownership at upgrade time given it's now owned by a direct model-provider competitor. |
| Anthropic `client.messages.count_tokens()` (beta at time of most training data; re-verify GA status against the SDK's current changelog before relying on it) | Pre-flight token estimate for per-tenant cost budgeting before a call is made | Use for a "this request will cost ~$X, proceed?" gate on expensive Opus-tier batch triage runs. LOW confidence on current beta/GA status specifically — verify via `anthropic` SDK's own docstrings/changelog at implementation time. |

## Installation

```bash
# Backend (pyproject.toml — add to [project.dependencies])
uv add anthropic>=0.120,<1.0

# Backend dev/test dependency (eval + guardrail scanner)
uv add --optional dev "deepeval>=4.0.0"
uv add --optional dev "llm-guard>=0.3.16,<0.4"

# Frontend (package.json)
npm install eventsource-parser@^3.1.0

# CI-only, not a runtime/dev Python or npm dependency — install in its own CI job
npx --yes promptfoo@0.121.x  # pin exact version; do not `latest` in CI
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|--------------------------|
| DeepEval (pytest-native) | promptfoo (YAML/CLI) as the *sole* eval tool | If the team strongly prefers declarative YAML over Python assertions, or wants the red-team attack-plugin library as the primary (not secondary) eval mechanism. GetVul's existing CI is Python-pytest-shaped, so DeepEval is the lower-friction primary; promptfoo is still recommended, but scoped to the security/red-team gate specifically (see Supporting Libraries), not as a replacement for DeepEval's quality-regression role. |
| DeepEval | A fully custom in-house eval harness | Only if DeepEval's metric set genuinely can't express a needed check — even then, extend DeepEval via its `BaseMetric`/`GEval` classes rather than building a parallel harness. A from-scratch harness would re-solve dataset management, scoring, and CI reporting that DeepEval already ships, for no clear benefit at this team's velocity. |
| llm-guard local ONNX scanner + structural prompt defenses (roll-your-own) | NeMo Guardrails | Only if the product grows a genuinely conversational, multi-turn agentic loop with tool-calling chains (RAG over a knowledge base, LangChain/LangGraph orchestration). NeMo Guardrails is built for that shape (Colang DSL, LangChain integration, jailbreak + fact-checking + hallucination detection) and is disproportionate — and dependency-heavy — for this milestone's mostly single-shot summarize/draft calls. |
| llm-guard (scanner-as-signal) + Pydantic tool-use schema validation (roll-your-own output enforcement) | Guardrails AI (`guardrails-ai`) | If the team wants a pre-built library of output validators (toxicity, competitor-mention, custom regex) beyond what a hand-rolled Pydantic schema + a small allow-list of post-generation checks covers. For this milestone, Claude's native tool-use JSON-schema enforcement + server-side Pydantic validation already gives deterministic, code-reviewable output control — Guardrails AI would be a second framework doing largely the same job. |
| Deterministic allow-list serialization of HR/MDM owner fields | Microsoft Presidio (general PII NER) | Once a phase ingests genuine free text (ticket comments, analyst-authored notes, connector free-text fields) where PII could appear in unpredictable positions that an allow-list can't cover. |
| Two-tier Redis cache (global CVE tier + tenant-scoped tier) | A dedicated LLM-caching library (e.g. GPTCache) | If cache-hit analytics/semantic-similarity matching (fuzzy cache hits on paraphrased prompts, not just exact hash matches) becomes valuable — not needed for this milestone's mostly-deterministic, template-built prompts. |
| Native Anthropic tool-use + Pydantic validation for structured ticket drafts | `instructor` library | If the team wants automatic retry-on-validation-failure and a more ergonomic decorator-based API across *multiple* LLM providers. Not needed here — GetVul calls exactly one provider (Anthropic), so `instructor`'s multi-provider abstraction buys little and is one more dependency between the app and the SDK's own well-documented tool-use API. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|--------------|
| `langchain` / `langgraph` | GetVul's AI features are single-shot or short-lived request/response calls (summarize, draft, prioritize) grounded in data the backend already has in Postgres — there is no multi-step agent loop, no tool-chaining across external systems, and no need for LangChain's abstraction layer. Adding it would introduce a large, fast-moving dependency surface (and its own prompt-template/output-parser abstractions) to do what 200 lines of a plain `app/ai/service.py` module already does clearly. | A plain `AsyncAnthropic` client wrapped in a small first-party `app/ai/` module, following the same `models.py` / `service.py` / `router.py` shape as every other domain module in this codebase (`app/connectors/`, `app/vulnerabilities/`, etc.). |
| A vector DB (pgvector, Pinecone, Weaviate, Chroma) / embeddings pipeline | Nothing in the milestone's four target features (explain-vuln, remediation guidance, triage narrative, ticket drafting) requires semantic retrieval over a corpus — the grounding data (CVE text, scanner solution text, asset/owner/SLA rows) is already structured, already in Postgres, and already fetched by exact ID via the existing ORM. RAG only pays off when you need fuzzy retrieval over an unstructured corpus (e.g., "find similar past incidents"), which is out of scope here. | Direct Postgres queries (existing SQLAlchemy async session) to assemble prompt context by ID; Anthropic's prompt caching for anything reused across calls (e.g., a stable system prompt or the KEV catalog excerpt) instead of a retrieval layer. |
| NeMo Guardrails as the guardrail framework | Built for conversational, LangChain-integrated, multi-turn bot pipelines; brings Colang, its own runtime, and (depending on rails configured) embedding-model dependencies — disproportionate for mostly single-shot generation calls, and would be the first thing in the backend pulling in an ML-framework-shaped dependency tree. | Structural prompt defenses (XML-tag untrusted scanner text + explicit "data, not instructions" system-prompt framing — Anthropic's own documented "spotlighting" pattern) + `llm-guard`'s narrow `PromptInjection` scanner as one additional signal + strict Pydantic/tool-use schema validation on every output before it reaches a ticket or the UI. |
| A brand-new "LLM gateway" service/container (e.g. LiteLLM proxy, Portkey) | GetVul calls exactly one provider (Anthropic) from exactly one backend (FastAPI) on a single-VM Docker Compose topology; a standalone gateway process adds an extra container, an extra network hop, and an extra thing to keep healthy on `install.sh`-managed VMs for a benefit (multi-provider routing/fallback) the product doesn't need. | The `AsyncAnthropic` client instantiated once at FastAPI lifespan startup (same pattern as the existing Redis/DB engine singletons) and injected via `Depends`. |
| Local/self-hosted open models (vLLM, Ollama) for any of the four target features | The milestone explicitly names Claude (Opus/Sonnet/Haiku) as "first AI capability in the product," single-VM customers have no GPU provisioning story today, and quality/latency of a self-hosted model for nuanced remediation reasoning is a materially different (and much larger) bet than integrating a hosted frontier API. | The Anthropic Messages API (streaming for interactive calls) + Message Batches API (50% off input/output tokens, MEDIUM confidence WebSearch-sourced, for the nightly/scheduler-driven bulk summarization of every finding from a sync — not latency-sensitive, so batch is the right default there). |
| Full Vercel AI SDK (`ai` + `@ai-sdk/anthropic`) on the frontend | Assumes the Next.js layer itself calls Anthropic (via a Next.js Route Handler), which would create a second code path to the Anthropic API key and bypass the FastAPI backend's tenant-scoping, RBAC, and audit-log enforcement that every other feature in this codebase goes through. | Keep 100% of Anthropic calls server-side in FastAPI; stream to the frontend as SSE proxied by FastAPI's `StreamingResponse`, parsed client-side by the ~3KB `eventsource-parser`. |
| Guardrails AI (`guardrails-ai`) as a second output-validation framework alongside hand-rolled Pydantic checks | Redundant: Claude's native tool-use already returns schema-conformant JSON, and GetVul's existing convention is Pydantic v2 schemas everywhere (FastAPI request/response models) — adding a second validation framework for the same job is inconsistent with the rest of the codebase's patterns. | Anthropic tool-use with a Pydantic-generated JSON schema + server-side `model_validate()` before any LLM output reaches a ticket draft or the UI; reject/re-prompt (bounded retries) on validation failure. |

## Stack Patterns by Variant

**If the call is user-triggered and latency-sensitive** (e.g. "Explain this vuln" opened from the drill panel, "Draft this ticket"):
- Use the streaming Messages API (`client.messages.stream(...)`) with `model="claude-sonnet-5"` (or Haiku for the cheapest single-finding summary), called directly from the FastAPI request handler.
- Re-emit as `StreamingResponse(media_type="text/event-stream")`; frontend consumes via `eventsource-parser`.
- Apply prompt caching (`cache_control: {"type": "ephemeral"}`) on the stable system prompt / grounding-data prefix (e.g. the tenant's risk-scoring rubric, the KEV excerpt) since it repeats across every analyst request that session.

**If the call is background/bulk** (e.g. pre-generating a summary for every finding surfaced by the nightly scanner sync, in the existing `app/connectors/scheduler.py` asyncio loop):
- Use the Message Batches API (`client.messages.batches.create`, up to 100,000 requests/batch, results within 24h, ~50% off both input and output tokens vs. synchronous calls — MEDIUM confidence, WebSearch-sourced) rather than looping synchronous calls in the scheduler.
- Combine with the global CVE-text cache tier so a batch never re-summarizes a CVE the platform has already explained for any tenant.

**If the output will be rendered as-is in the UI or sent to Jira/Asana** (ticket auto-drafting):
- Force structured output via Claude tool-use with a Pydantic-derived JSON schema (`title`, `description`, `remediation_steps`, `asset_context` as separate typed fields) — never let free-form generated markdown/HTML go straight into a ticket body unescaped.
- Validate server-side with `model_validate()` before the existing Jira/Asana connector call; on validation failure, retry once with a corrective system message, then fall back to a template-only draft (deterministic, no LLM) rather than blocking the analyst.

**If the input includes attacker-controllable text** (CVE descriptions, hostnames, scanner finding titles — true for every one of the four target features):
- Wrap it in an explicit `<untrusted_scanner_data>` XML block in the prompt with a system-prompt instruction that content in that block is data, never instructions (Anthropic's documented "spotlighting" pattern — free, no dependency).
- Score it with `llm-guard`'s local `PromptInjection` scanner before interpolation; log a flagged audit event (matching GetVul's existing `AUDIT-01` convention) on high scores rather than hard-blocking, to avoid silently dropping a legitimate finding.
- Never let the model's raw text execute a "tool" or trigger a ticket-creation side effect directly — only the validated, schema-conformant structured output can reach a connector call.

**If per-tenant model/feature configuration is needed** (the milestone's "per-tenant model config" requirement):
- Add a `tenant_ai_config` Postgres table (`tenant_id`, `feature` enum, `model_id`, `max_tokens`, `temperature`, `enabled`, `updated_at`), following the exact multi-tenant/`tenant_id`-scoping convention every other domain table already uses.
- Global defaults (model IDs, the single Anthropic API key) stay in `pydantic-settings`/`.env`, consistent with how connector defaults work today — do not build a per-tenant BYO-API-key system; GetVul's deployment model is one VM per customer, so a single platform-level Anthropic key is the right scope, with the Postgres table only controlling *which* model/feature is active per tenant, not *whose* key is billed.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|------------------|-------|
| `anthropic>=0.120,<1.0` | Python 3.9–3.14 (repo pins 3.12) | No conflict with the repo's `python-jose`, `cryptography`, `httpx>=0.27` — the SDK's own `httpx` pin is loose enough to coexist; verify via `uv lock` / `pip check` at integration time since exact transitive pins weren't verified via Context7. |
| `deepeval>=4.0.0` | `pytest>=8.3` (repo already pins this) | Confirmed compatible generation (both are current 2026 releases); DeepEval's own CLI (`deepeval test run`) wraps `pytest`, so no double test-runner conflict. |
| `llm-guard==0.3.16` | Python `<3.13,>=3.10` | **Compatible with the repo's Python 3.12 pin today; will need re-verification before any future bump to Python 3.13** (the repo's `[tool.mypy] python_version = "3.12"` / `requires-python = ">=3.12"` gives headroom, but don't silently jump `llm-guard` past its stated ceiling). |
| `eventsource-parser@^3.1.0` | Next.js 15 / React 19 (existing) | Zero framework coupling — it's a pure stream-parsing utility, not a React library; no version interaction with Next.js/React to track. |
| promptfoo (CI-only, Node) | No interaction with backend Python deps | Runs in its own CI job/container, never installed into `backend/pyproject.toml` or the app's runtime image — no version-compat surface with the rest of the stack. |

## Sources

- `platform.claude.com/docs/en/docs/about-claude/models/overview` (fetched live 2026-07-25) — model IDs, context windows, pricing, prompt-caching support, extended-thinking support for Opus 5 / Opus 4.8 / Sonnet 5 / Haiku 4.5. HIGH confidence.
- `platform.claude.com/docs/en/docs/build-with-claude/prompt-caching` (fetched live 2026-07-25) — cache_control syntax, 5-min vs 1h TTL, pricing multipliers (1.25x / 2x write, 0.1x read), minimum cacheable token counts per model, workspace-isolation and cache-invalidation rules. HIGH confidence.
- `anthropic.com/news/claude-sonnet-5` (fetched live 2026-07-25) — Sonnet 5 API model ID confirmation, release date 2026-06-30.
- PyPI `anthropic` project page (fetched live 2026-07-25) — latest version 0.120.0, released 2026-07-24, Python 3.9–3.14 support. HIGH confidence.
- PyPI `deepeval` / `llm-guard` project pages + WebSearch cross-checks — version numbers and dependency/Python-version constraints. MEDIUM confidence (not Context7-verified).
- WebSearch: "promptfoo vs deepeval 2026", "prompt injection guardrail library python 2026", "anthropic Message Batches API 50% discount pricing 2026" — architecture/rationale claims (Batch API discount, promptfoo's OpenAI acquisition, NeMo Guardrails' LangChain/Colang shape) are MEDIUM confidence, cross-referenced across 2+ independent sources but not Context7/official-doc-verified; flagged inline above where the confidence is lower.
- Repo inspection: `/Users/chemencedji/Desktop/getvul/backend/pyproject.toml` (existing dependency set, Python/pytest/mypy pins) and `/Users/chemencedji/Desktop/getvul/backend/tests/test_okta_sync.py` et al. (existing `httpx.MockTransport` test-mocking convention, no `respx` in use) — used to keep new recommendations idiomatically consistent with the codebase. HIGH confidence (direct read).

---
*Stack research for: AI-Assisted Triage (v3.0) — Claude integration layer, eval/guardrail tooling, caching, per-tenant config*
*Researched: 2026-07-25*
