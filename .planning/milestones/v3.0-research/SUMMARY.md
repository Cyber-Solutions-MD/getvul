# Project Research Summary

**Project:** GetVul — v3.0 AI-Assisted Triage ("Triage Copilot")
**Domain:** LLM-assistance layer (summarization, remediation guidance, triage narrative, ticket auto-drafting, optional NL query) bolted onto an existing mature multi-tenant FastAPI + Next.js vulnerability-triage platform
**Researched:** 2026-07-25
**Confidence:** MEDIUM-HIGH overall — stack/architecture are HIGH confidence where grounded in live docs and direct codebase reads; features/pitfalls are MEDIUM-HIGH, corroborated across multiple independent vendor/industry sources but not Context7-verified in all cases

## Executive Summary

GetVul v3.0 is not a "build an AI chatbot" project — it's a **grounding-and-guardrails engineering problem** wrapped around a narrow set of well-precedented LLM use cases (explain, remediate, prioritize, draft) that industry leaders (Microsoft Security Copilot, CrowdStrike Charlotte AI/ExPRT.AI, Wiz AI Agents) have already validated the shape of. The single cross-cutting architectural decision that recurs in all four research files is the **deterministic-score-plus-LLM-narrative split**: GetVul's existing ASSET-02 piecewise-log risk score stays the one authoritative number; the LLM only narrates, explains, and augments it — mirroring CrowdStrike's ExPRT.AI (quantitative score) / Charlotte AI (explanatory layer) architecture precisely. A second AI-generated score, an auto-reordered list, or any autonomous execution (auto-patch, auto-submit-ticket, auto-assign) are hard anti-features across every research file, not just a design preference — they would each require bypassing a constraint (one score, human-gated tickets, no execution layer) that already exists in this codebase today.

The recommended approach is architecturally conservative and reuses everything GetVul already has: a new sibling `app/ai/` package (matching `connectors/`, `ticketing/`, etc.), deterministic SQL-join grounding (no vector DB/RAG — nothing here needs semantic retrieval over unstructured text), the existing Fernet/`ConnectorConfig` encryption pattern extended to a new `AiConfig` table, the existing `audit()` helper (plus its one documented `user=None` workaround, reused verbatim), and the existing Redis instance for a two-tier cache. The stack is `anthropic` SDK 0.120.0 with Claude Haiku 4.5 (cheap/high-volume explain), Sonnet 5 (default for remediation/triage/drafting), and Opus 4.8 (deep batch prioritization) — with an explicit flag that Opus 5 has already shipped and should be re-checked against the Models API at phase-execution time, not assumed stale-safe. DeepEval (pytest-native, in the existing CI gate) plus promptfoo (a separate red-team CI job, analogous to the existing semgrep/ZAP gates) form the eval/guardrail tooling layer.

The dominant risk, named as the headline threat in both FEATURES.md and PITFALLS.md, is **prompt injection via attacker-controllable scanner text**: CVE descriptions, hostnames, and vendor "solution" fields already look like trusted first-party Postgres rows by the time they reach a prompt-builder, but they originate from six independently-attacker-influenceable scanner vendors. The concrete, load-bearing defense pattern — corroborated by Anthropic's own official guidance — is (1) deliver untrusted scanner text as JSON-encoded/XML-delimited data in a `tool_result`, never concatenated into the instruction/user turn, (2) enforce all outputs through Pydantic/JSON-schema validation so the model can never emit anything but structured, code-reviewable output, and (3) give the model **zero write/tool access** — every AI feature produces prose/JSON that flows into existing human-submitted create/edit paths, so even a successful injection can't itself flip a severity, suppress a finding, or fire a ticket. A second, closely related grounding pattern — the **two-tier citation model** (verbatim scanner "solution" text vs. AI-interpreted translation, visually and structurally distinguished) — is both the primary anti-hallucination mechanism and the primary trust-building UX mechanism; it recurs as load-bearing in FEATURES.md (Areas 1, 2, 4), ARCHITECTURE.md (`validate_no_hallucination()`), and PITFALLS.md (Pitfall 2's "cite or refuse" contract). Natural-language query over the vuln inventory is explicitly the highest anti-feature risk in the whole milestone: get it wrong (freeform text-to-SQL) and it compounds prompt injection with SQL injection and bypasses tenant_id scoping that today lives entirely in the query layer — all four research files independently converge on deprioritizing it to P3/future, bounded strictly to function-calling over already-tenant-scoped filter endpoints, never generated SQL.

## Key Findings

### Recommended Stack

The net-new stack is deliberately minimal and reuses GetVul's existing infra wherever possible — no new microservice, no vector DB, no LangChain/LangGraph, no self-hosted model, no standalone LLM gateway. See STACK.md for full rationale and version-compatibility notes.

**Core technologies:**
- `anthropic` Python SDK `>=0.120,<1.0` — official, fully-typed, `AsyncAnthropic` drops into existing `async def` FastAPI handlers and the asyncio scheduler with zero event-loop bridging
- Claude Sonnet 5 (`claude-sonnet-5`) — default model for remediation guidance, triage narrative, ticket drafting; best speed/intelligence tradeoff at $2/$10 per MTok (introductory, through 2026-08-31)
- Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) — cheap, high-volume "Explain this vuln" summaries; the model that makes per-finding summarization economical at scanner-ingestion scale
- Claude Opus 4.8 (`claude-opus-4-8`) — deep batch triage reasoning; **currency flag: Opus 5 has already shipped and Opus 4.8 is listed under "Legacy" (still fully supported, not deprecated) — re-check the Models API at deploy/phase-execution time before locking the model ID**
- DeepEval `>=4.0.0` — pytest-native LLM eval framework, drops into GetVul's existing `ruff`→`mypy`→`pytest` CI gate with no new YAML DSL or CI runtime; extend via `BaseMetric`/`GEval` for a custom "no hallucinated remediation" metric
- promptfoo (CI-only, Node, pinned exact version) — separate adversarial red-team CI job (auto-generated jailbreak/injection/PII-leakage/excessive-agency attacks), analogous to the existing semgrep/ZAP security-scan gates, not a replacement for DeepEval
- `llm-guard==0.3.16` — local ONNX `PromptInjection` classifier as one scored signal (not a hard block) against attacker-controlled scanner text; runs fully in-process, no data leaves the customer's single-VM deploy
- Two-tier Redis cache on the *existing* Redis instance: a global CVE/finding-explanation tier (deliberately not tenant-scoped, since identical CVE text is shared across all tenants) and a tenant-scoped tier for triage narratives/ticket drafts (embed tenant-specific asset/owner/SLA context, so must never cross tenant boundaries)
- Message Batches API for scheduler-driven bulk pre-warming (~50% off tokens vs. synchronous calls, MEDIUM confidence)
- `eventsource-parser` (npm, frontend) over a plain `fetch()`+`ReadableStream` — deliberately not the Vercel AI SDK, which would create a second, unaudited path to the Anthropic API key bypassing FastAPI's centralized tenant-scoping/RBAC/audit-logging

**What NOT to add:** LangChain/LangGraph (no multi-step agent loop exists in scope), any vector DB/embeddings pipeline (grounding is deterministic SQL joins, no unstructured corpus), NeMo Guardrails (disproportionate for single-shot generation), a standalone LLM gateway service (single provider, single backend, single VM), self-hosted open models (no GPU story on single-VM customer deploys), Guardrails AI (redundant with native tool-use + Pydantic).

### Expected Features

Five feature areas, four of which are named phases in the milestone; the fifth (NL query) is explicitly optional/deferred. See FEATURES.md for full detail, competitor analysis, and per-area grounding/citation/streaming guidance.

**Must have (table stakes) — P1:**
- Per-finding plain-English summary + business-risk framing (Area 1), grounded only in scanner text + existing enrichment fields, streamed, with an AI-content badge
- Verbatim-first remediation guidance (Area 2): quote the scanner's own solution text, then OS/package-aware translation, with an honest "no vendor remediation available" fallback — never fabricate from general LLM knowledge
- Narrative explanation of the *existing* deterministic score (Area 3) — "why is this an 87," fed structured score-contributing factors, never raw free reasoning
- Draft-only ticket auto-fill (Area 4) — a human click always creates the ticket; reuses Areas 1–2's output rather than re-deriving

**Should have (differentiators) — P2:**
- Cross-scanner agreement/conflict synthesis in summaries (GetVul's actual multi-scanner correlation moat — no single-scanner competitor can do this)
- Batch/aggregate remediation across correlated findings on one host ("one patch fixes 12 of 15")
- Interactive "ask why" follow-up on the triage narrative (mirrors Charlotte AI's explicit capability)
- Embedded permalink from ticket body back to the GetVul drill panel

**Defer (v2+/P3):**
- Area 5 (NL query over the vuln inventory) — highest anti-feature risk in the milestone; must be bounded function-calling over already-tenant-scoped filter endpoints if built at all, never freeform text-to-SQL, and is not named as its own phase in the milestone's target-feature list
- Cross-host batch remediation grouping, delta summaries on re-open, saved-query-from-NL-query

**Hard anti-features (all areas):** autonomous auto-remediation/auto-patching; a second AI-generated risk score; auto-submitting AI-drafted tickets without review; freeform LLM-to-SQL; treating scanner/finding text as trusted instruction context; no visual distinction between AI-generated and human/scanner-authored content.

### Architecture Approach

A new `app/ai/` top-level package, sibling to every existing domain package (`connectors/`, `vulnerabilities/`, `ticketing/`), orchestrates a fixed pipeline for every capability: `grounding.py` (tenant-scoped SQL joins, no RAG) → `cache.py` (Redis, tenant-scoped except the global CVE tier) → `client.py` (`AsyncAnthropic`, per-tenant model resolution) → `guardrails.py` (injection defense + hallucination validation) → `costs.py` (budget pre-check, fail-closed) → `app/audit.py` (reused unmodified). Streaming to the frontend uses `fetch()`+`ReadableStream` (never `EventSource`, since the app's Bearer-JWT auth can't ride `EventSource`'s header-less model) through a new, narrowly scoped nginx `location /api/v1/ai/` block with `proxy_buffering off` — deliberately not touching the existing `/api/` block's buffering/timeout behavior for every other verified endpoint. Batch/bulk work (nightly triage pre-warm) is dispatched via `asyncio.create_task` from the existing scheduler loop, exactly like `trigger_background_sync()`, never awaited inline — a slow Opus call must never stall the same tick's connector sync or SLA-breach check.

**Major components:**
1. `app/ai/grounding.py` — deterministic, tenant-scoped SQL assembly of `GroundingContext` from Vulnerability/Asset/Correlation/Misconfiguration/SLA fields; the single source every capability calls first
2. `app/ai/client.py` + new `AiConfig` Postgres table — per-tenant model/feature config, reusing the exact Fernet `encrypt_value`/`decrypt_value` helpers `ConnectorConfig` already uses (no second crypto scheme)
3. `app/ai/guardrails.py` — two-sided defense: input-side untrusted-text delimiting + `llm-guard` scoring, output-side `validate_no_hallucination()` cross-checking claims against grounding facts
4. `app/ai/costs.py` + Redis `ai:usage:{tenant}:{yyyy-mm}` counter + `AiUsage` Postgres ledger — pre-check-then-record, **fail-closed** (the deliberate opposite fail-mode of the existing rate limiter's fail-open)
5. `app/ai/cache.py` — two-tier Redis cache (global CVE tier / tenant-scoped narrative-and-draft tier), both content-hash-keyed, `prompt_version` bump busts the hash on prompt edits

### Critical Pitfalls

Full detail, warning signs, and phase-mapping in PITFALLS.md; the nine pitfalls map cleanly onto specific phases in the suggested build order below.

1. **Prompt injection via attacker-controlled scanner text (headline threat)** — treat every scanner-sourced field as untrusted at the type level forever, not just at the first call site; deliver as JSON/XML-delimited `tool_result` data with an explicit "data, never instructions" system-prompt policy; zero model write/tool access; screen with a local classifier as a scored signal, not a hard block.
2. **Hallucinated/unsafe remediation guidance** — ground only in scanner solution text + DB asset facts; enforce "cite or refuse" via the output schema, not prompt wording; post-generation dangerous-pattern regex (`rm -rf`, `DROP TABLE`, "disable firewall/EDR"); never auto-execute.
3. **PII/secret leakage into prompts or logs** — explicit per-feature field allowlist (never `asset.__dict__`/`model_dump()` wholesale); prompt-builders must never receive decrypted connector credential objects; reuse (don't reinvent) the Phase 7 recursive redaction middleware for any new prompt-trace logging.
4. **Cross-tenant data bleed via shared cache/prompts or batching** — cache keys must be composite and include `tenant_id` unless the content is provably tenant-agnostic (a separate, explicitly-reviewed namespace); never batch multiple tenants' findings into one LLM call; extend the existing tenant-isolation regression-test pattern to the new cache/prompt layer.
5. **Cost blowup at 100k+ findings** — on-demand generation only (never eager/pre-computed for a whole list); response caching by `(tenant_id, cve_id, content_hash)`; cheap-model-first routing (Haiku/Sonnet/Opus tiering); a hard per-tenant budget with a **fail-closed** circuit breaker that degrades to "deterministic score only," not unbounded spend.

Four more pitfalls matter structurally: **non-determinism breaking CI** (assert schema/properties, never exact prose — this codebase has twice already shipped false "gate is green" claims per MEMORY.md, and prose-snapshot testing is the exact mechanism that would repeat it); **over-trusting AI prioritization over the deterministic score** (automation-bias research shows analysts skew toward trusting fluent AI narrative even when skeptical in the abstract — enforce "no independently-sortable AI rank" as a literal schema/UI constraint, not just a design intention); **shipping without evals** (every feature phase ships its own scoped mini-eval as a completion condition — VALIDATION.md may not claim "AI output is accurate" without pasted eval-run numbers, exactly the discipline this codebase already applies to axe sweeps); and **drill-panel latency/UX regression** (the AI summary must be its own Suspense-bounded async region with its own skeleton/error state, never blocking the panel's already-fast deterministic content).

## Implications for Roadmap

All four research files converge on the same six-phase build order (STACK.md's "stack patterns by variant," ARCHITECTURE.md's "Suggested Build Order," FEATURES.md's "MVP Definition," and PITFALLS.md's "Pitfall-to-Phase Mapping" all independently land here), because the dependency chain is genuinely forced: grounding requires reliable ingestion, every feature requires the guardrail scaffold, and the eval/cost gate is only meaningful once real usage data exists to seed it.

### Phase 1: Ingestion-Reliability Precursor
**Rationale:** Every research file calls this out as a hard prerequisite, not good practice — "AI is only as good as its grounding." Wiz/Rapid7 connector wiring is documented as currently broken; building summarization/remediation/prioritization on top of silently-wrong or missing scanner data means the AI confidently narrates garbage and nobody can tell why it seems unreliable.
**Delivers:** Fixed Wiz/Rapid7 connector wiring, scanner HTTP-layer integration tests, wired Jira ticket-create + finished GitHub ticketing, per-connector sync-health surface.
**Addresses:** No user-visible AI feature; unblocks Areas 1–4 and Area 4's specific dependency on Jira-create/GitHub-ticketing being complete.
**Avoids:** Nothing yet, but establishes the grounding-data reliability every later pitfall assumes.

### Phase 2: AI Foundation + "Explain This Vuln"
**Rationale:** This is where the integration risk concentrates — streaming through nginx, tenant-scoped caching, encrypted per-tenant config, and the guardrail scaffold all need to be proven end-to-end against the single simplest capability before being multiplied across four capabilities. Every later phase reuses this scaffold unmodified.
**Delivers:** `app/ai/` package skeleton (models, `AiConfig` + encryption reuse, `grounding.py`, `cache.py`, `client.py`, `guardrails.py`, `costs.py`, prompt-versioning, audit wiring), the scoped nginx streaming block, the frontend streaming hook, and the first capability (`explain_vulnerability`).
**Uses:** `anthropic` SDK, Claude Haiku 4.5, `llm-guard`, two-tier Redis cache, Fernet/`ConnectorConfig`-pattern encryption, DeepEval scaffold.
**Implements:** Grounding Context Assembly, Redis Content-Hash Cache, Per-Tenant Encrypted Model Config, SSE Streaming, Guardrail Wrapper, Cost Ledger (fail-closed), Audit Logging patterns (all from ARCHITECTURE.md).
**Avoids:** Pitfall 1 (prompt injection — untrusted-content-handling pattern and "model never writes state" contract must exist before any AI call ships), Pitfall 3 (PII leakage — allowlist prompt-builder pattern), Pitfall 4 (cross-tenant bleed — tenant-keyed cache/prompt contract), Pitfall 6 (non-determinism — schema/property test convention + API-mocking harness established here for reuse), Pitfall 9 (drill-panel latency — Suspense-bounded async region pattern established here since it's the first phase touching the shared DrillPanel primitive).

### Phase 3: Asset-Aware Remediation Guidance
**Rationale:** Low incremental integration risk once Phase 2's scaffold is solid — reuses everything, adds `Misconfiguration`/asset fields to grounding and a second prompt template. Shares Area 1's grounding/citation pipeline directly (FEATURES.md).
**Delivers:** OS/package-aware remediation translation, verbatim scanner-solution-text citation, "no vendor remediation available" honest fallback, dangerous-pattern post-generation guardrail.
**Addresses:** Area 2 table-stakes features; feeds Area 4's ticket draft directly.
**Avoids:** Pitfall 2 (hallucinated remediation — "cite or refuse" enforced by output schema, dangerous-pattern regex, golden-dataset eval scoring grounding/citation correctness before ship).

### Phase 4: Natural-Language Triage Assistant (Prioritization Narrative, Batch)
**Rationale:** First feature that touches `connectors/scheduler.py` (batch pre-warm tick) — sequenced after the request-path phases (2–3) are proven, since scheduler-originated audit/budget paths are subtly different (`user=None`/`system:scheduler` handling) and easier to get right with a known-good single-request reference already in place.
**Delivers:** Narrative explanation of the existing ASSET-02 deterministic score fed structured contributing factors (never raw free reasoning), SLA-aware narrative, scheduler batch pre-warm via `asyncio.create_task` (never inline), direct `AuditLog` construction with `user_email="system:scheduler"` following the `encryption.py` "system:cli" precedent.
**Addresses:** Area 3 table-stakes and differentiator features.
**Avoids:** Pitfall 7 (over-trusting AI over the deterministic score — enforce "augment, never replace" as a literal output-schema/prompt constraint, not just a design description; no UI affordance to sort by AI priority).

### Phase 5: AI Ticket Auto-Drafting
**Rationale:** Purely additive to the existing ticket-create UI; depends on Phases 2–3's grounding/guardrail infrastructure but introduces no new backend risk surface (no `Ticket` model changes) — the safest phase to sequence last among the four core capabilities.
**Delivers:** `POST /api/v1/ai/tickets/draft` returning a suggested `{title, description, remediation}` payload that pre-fills the *existing*, unchanged `POST /tickets` create flow; provider-schema-aware field mapping; embedded permalink back to the drill panel.
**Addresses:** Area 4 table-stakes and differentiator features.
**Avoids:** the ticket-specific instance of the "draft, never auto-submit" anti-feature (a human click always creates the ticket, preserving RBAC/audit accountability).

### Phase 6: Eval + Guardrail + Cost/Observability Gate (Milestone-Closing)
**Rationale:** By this point every capability exists and has generated real `AiUsage`/`AuditLog` data, so eval fixtures can be seeded from real observed outputs rather than purely synthetic cases — the same reasoning DeepEval/promptfoo research recommends running the red-team suite once real system prompts exist.
**Delivers:** `app/ai_evals/` fixture harness (git-reviewed JSONL, not runtime data) + `AiEvalRun`/`AiEvalResult` Postgres tables; hardened guardrails against accumulated real examples; enforced per-tenant hard budget + circuit breaker (fail-closed) + admin-visible usage pane; nightly (non-PR-blocking) golden-dataset + LLM-as-judge eval run with human-reviewed regression threshold; adversarial/injection regression suite re-verified across all five capabilities; cross-tenant cache/batch isolation regression test.
**Addresses:** The milestone's own named "eval + guardrail + cost/observability" closing requirement.
**Avoids:** Pitfall 5 (cost blowup — hard budget/circuit breaker + 100k-finding load test as a release gate), Pitfall 6 (non-determinism — nightly golden-dataset run + prompt-change-triggers-eval-rerun policy), Pitfall 8 (shipping without evals — enforces "evals are the arbiter," matching this codebase's existing "the sweep, not the file list, is the arbiter" discipline).

### Phase Ordering Rationale

- **Grounding-data reliability must come before any AI feature** (Phase 1) — this is a hard dependency called out identically in FEATURES.md's dependency graph, ARCHITECTURE.md's build order, and PITFALLS.md's framing, not a convenience ordering.
- **The riskiest architectural bet (streaming through nginx + tenant-scoped caching + encrypted per-tenant config + guardrails) is proven once, in Phase 2, at minimum blast radius** (one capability) rather than discovered while juggling four capabilities simultaneously — this is ARCHITECTURE.md's explicit rationale for sequencing "Explain this vuln" first among the four capabilities.
- **Request-path phases (2–3) precede the first batch/scheduler-touching phase (4)** because the scheduler's `user=None`/system-audit path is a materially different code path (direct `AuditLog` construction bypassing `audit()`) that's safer to get right with a known-good single-request reference already validated.
- **Ticket drafting (5) is deliberately last among the four core capabilities** because it's a pure consumer of Phases 2–3's output (no independent LLM call, no new backend risk surface) — sequencing it last means it's assembling already-proven output, not re-deriving anything.
- **The eval/guardrail/cost gate closes the milestone, not opens it,** so its golden datasets can be seeded from real Phase 2–5 outputs — but note PITFALLS.md's counter-pressure: *each* feature phase must still ship its own scoped mini-eval as a phase-completion condition (Pitfall 8), so "the closing gate will cover it" is explicitly not a valid excuse to defer per-phase eval work.
- Area 5 (NL query) is not in this six-phase core sequence at all — deferred to a future milestone per FEATURES.md's MVP Definition, given its P3 priority and highest-severity anti-feature risk (tenant-scoping bypass) if rushed.

### Research Flags

Phases likely needing deeper research (`/gsd-research-phase`) during planning:
- **Phase 2 (AI Foundation + Explain-this-vuln):** Highest integration-risk concentration — SSE streaming through the existing nginx/FastAPI reverse-proxy setup is architecture-researched but not implementation-proven (STACK.md and ARCHITECTURE.md both flag streaming specifics as MEDIUM confidence, WebSearch-verified rather than Context7-resolved); the `count_tokens()` beta/GA status is explicitly LOW confidence and needs re-verification against the SDK's current changelog before the cost-estimate gate depends on it.
- **Phase 2 (encryption extension):** `rotate_credentials()` currently hardcodes `ConnectorConfig` import — generalizing it to also sweep `AiConfig` is a real refactor with a "no Fernet key rotation without a documented migration" constraint attached; worth a dedicated research/design pass rather than treating it as a drive-by change.
- **Phase 4 (batch/scheduler triage):** The scheduler's `user=None`/tenant-sentinel gap in `audit()` is a genuine existing bug pattern (not just an AI-specific concern) — worth confirming the `system:scheduler` direct-`AuditLog`-construction precedent is the right long-term fix vs. a scheduler-wide `audit()` signature change.
- **Phase 6 (eval gate):** Reconciling `AiEvalRun`/`AiEvalResult` Postgres storage with whatever the `gsd-ai-integration-phase` tooling expects (if that skill/tool imposes its own eval-storage or CI-integration conventions) should be explicitly checked before this phase's schema is finalized, to avoid building two parallel eval-ledger shapes.

Phases with standard, well-documented patterns (can likely skip dedicated research-phase):
- **Phase 1 (ingestion-reliability precursor):** Standard connector-fix + integration-test work, no new architectural pattern — reuses GetVul's existing connector conventions.
- **Phase 3 (remediation guidance):** Reuses Phase 2's scaffold entirely; the OS/package-translation logic is prompt-engineering over an already-shipped `os_family` field, not new integration surface.
- **Phase 5 (ticket auto-drafting):** Purely additive to an existing, unchanged create flow; no new backend risk surface.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH for model IDs/pricing/SDK version (verified live against `platform.claude.com` and PyPI 2026-07-25); MEDIUM for eval/guardrail library specifics (PyPI-verified versions, but behavioral/architectural claims are WebSearch cross-checked, not Context7-verified) |
| Features | MEDIUM-HIGH — grounded in current production security-copilot precedent (Microsoft Security Copilot, CrowdStrike Charlotte AI/ExPRT.AI, Wiz AI Agents) and OWASP GenAI Top 10; vendor marketing claims noted as such (MEDIUM), but the architectural conclusions (score/narrative split, anti-features) are corroborated across multiple independent sources and match GetVul's own explicit existing constraints (HIGH) |
| Architecture | HIGH for integration points — read directly from `backend/app/**`, `frontend/src/**`, `nginx/nginx.conf`; MEDIUM for Anthropic SDK streaming specifics (WebSearch-verified against current docs, not Context7-resolved) |
| Pitfalls | HIGH for prompt-injection/guardrail guidance (Anthropic official docs + OWASP LLM Top 10 2025, both current authoritative sources); MEDIUM for cost/eval/cache specifics (multiple 2026 practitioner sources agree, no single canonical spec); MEDIUM for automation-bias/analyst-trust figures (single research-survey source, directionally consistent with broader SOC-automation literature) |

**Overall confidence:** MEDIUM-HIGH — the architectural conclusions (score/narrative split, two-tier citation, injection defense pattern, on-demand+cached generation, fail-closed cost gate) are corroborated across all four research files independently and matched against GetVul's own existing codebase constraints, which is the strongest evidence available short of building it. The lower-confidence items are narrowly scoped (specific beta-API statuses, exact Batch-API discount percentage, Opus-5-vs-4.8 currency) and don't change the phase structure or architectural recommendations.

### Gaps to Address

- **Opus 4.8 vs. Opus 5 currency:** STACK.md flags that Opus 5 has already shipped as the new frontier flagship at research time; re-check the Models API (`platform.claude.com/docs/en/api/models/list`) at Phase 2/4 execution time before locking the model ID for deep-reasoning batch triage — don't silently build against a now-stale "Opus 4.8" default.
- **Per-model cost/latency routing budgets:** The milestone names Haiku/Sonnet/Opus tiering by capability, but no research file pins concrete per-tenant token/dollar budget defaults or latency SLOs (p95 time-to-first-token target) — this needs an explicit decision at requirements/roadmap time, not left implicit in "reasonable defaults."
- **Streaming feasibility spike against the current nginx/FastAPI setup:** All streaming guidance (SSE via `fetch()`+`ReadableStream`, scoped nginx `proxy_buffering off` block, heartbeat comments) is architecturally sound but not yet proven against GetVul's actual `nginx.conf` and Docker Compose topology — recommend a small spike/proof-of-concept as part of or immediately preceding Phase 2, before the rest of that phase's scaffold is built around an unverified streaming assumption.
- **`rotate_credentials()` generalization scope:** ARCHITECTURE.md flags this as a needed refactor (currently hardcodes `ConnectorConfig`) but doesn't resolve whether it should be its own small planning phase/sub-phase or folded into Phase 2 — decide explicitly at roadmap time given the "no Fernet key rotation without a documented migration" constraint.
- **`audit()`'s `user=None` tenant-sentinel gap:** This is a pre-existing, real gap in the current codebase (not AI-specific), being worked around via the `system:cli`/`system:scheduler` direct-`AuditLog`-construction precedent rather than fixed at the source — worth a decision on whether v3.0 should also fix `audit()`'s signature itself or continue extending the workaround pattern.
- **Reconciling eval storage with `gsd-ai-integration-phase` tooling:** If GetVul's GSD workflow has its own conventions for AI-integration-phase eval tooling/storage, Phase 6's `AiEvalRun`/`AiEvalResult` Postgres schema should be checked against those conventions before finalizing, to avoid two parallel eval-ledger mechanisms.
- **Message Batches API discount and `count_tokens()` GA status:** Both are MEDIUM/LOW confidence, WebSearch-sourced claims (not Context7/official-doc-verified at the time of research) — re-verify against the `anthropic` SDK's own changelog/docstrings before Phase 2/4 implementation depends on either behavior.

## Sources

### Primary (HIGH confidence)
- `platform.claude.com/docs/en/docs/about-claude/models/overview` and `.../build-with-claude/prompt-caching` (fetched live 2026-07-25) — model IDs, context windows, pricing, caching mechanics
- PyPI `anthropic` project page (fetched live 2026-07-25) — SDK version 0.120.0, Python 3.9–3.14 support
- [Mitigate jailbreaks and prompt injections — Claude Platform Docs](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/mitigate-jailbreaks) — tool_result/JSON-encoding/least-privilege defense patterns
- [OWASP Top 10 for LLM Applications 2025](https://owasp.org/www-project-top-10-for-large-language-model-applications/assets/PDF/OWASP-Top-10-for-LLMs-v2025.pdf) — prompt injection ranked #1, defense-in-depth framing
- Direct codebase reads: `backend/app/connectors/scheduler.py`, `backend/app/encryption.py`, `backend/app/audit.py`, `backend/app/main.py`, `backend/app/ticketing/models.py`, `backend/app/config.py`, `nginx/nginx.conf`, `frontend/src/components/vulnerabilities/drill-content.tsx`, `.planning/PROJECT.md`

### Secondary (MEDIUM confidence)
- [What is Microsoft Security Copilot? | Microsoft Learn](https://learn.microsoft.com/en-us/copilot/security/microsoft-security-copilot), CrowdStrike ExPRT.AI/Charlotte AI product pages and blog posts, [Wiz AI Security Graph](https://www.wiz.io/academy/ai-security/ai-security-graph) / [Green Agent](https://www.wiz.io/blog/introducing-wiz-green-agent) — competitor architecture precedent for the score/narrative split and human-approval-gated execution
- [Malicious Jira Tickets Exploit AI Workflows](https://www.techbeams.com/tech/malicious-jira-tickets-exploit-ai-workflows/) / [SC Media](https://www.scworld.com/news/jira-tickets-become-attack-vectors-in-poc-living-off-ai-attack) — real PoC validating untrusted-ticket-text treatment
- [TrojanSQL (ACL Anthology)](https://aclanthology.org/2023.emnlp-main.264/) — peer-reviewed support for the NL-query anti-feature reasoning
- [A Unified Framework for Human-AI Collaboration in SOCs (arXiv)](https://arxiv.org/pdf/2505.23397) — automation-bias/analyst-trust figures
- PyPI `deepeval`/`llm-guard` project pages, WebSearch cross-checks on promptfoo/Message-Batches-API pricing

### Tertiary (LOW confidence)
- Anthropic `count_tokens()` beta/GA status — explicitly flagged LOW confidence in STACK.md, needs SDK-changelog re-verification
- [AI Copilot UX Design](https://www.theskinsfactory.com/uiux-design-blog/ai-copilot-ux-design), [AI citation and source UI design patterns for 2026](https://www.aydesign.ai/blog/ai-citation-source-ui-patterns-2026) — general UX-pattern corroboration only, not primary technical sources

---
*Research completed: 2026-07-25*
*Ready for roadmap: yes*
