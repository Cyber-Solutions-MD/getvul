---
phase: 44
slug: natural-language-query-assistant
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: 2026-08-25
---

# Phase 44 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| browser → POST /api/v1/ai/query | Untrusted free-text question crosses into the backend; `require_analyst`-gated | Untrusted NL question (≤500 chars) |
| backend → Anthropic API | Untrusted question + deterministic result rows sent to the model; model output is untrusted until schema-validated | NL question (tag-isolated) + own-tenant rows |
| model output → query execution | The emitted filter object is untrusted until `extra="forbid"` + `recheck_nlq_filter_exclusivity` pass; execution always uses the session tenant_id | Model-emitted Pydantic filter (no tenant_id field) |
| SSE frames → DOM | Model-narrated prose + interpreted-filter tokens + result rows rendered in the browser | Model output (rendered as text) |
| URL query params → list query | Reflected, user-controllable Open-in deep-link params flow into the list filter; server re-scopes by session tenant_id | Untrusted clamped params |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-44-01 | Tampering / EoP (prompt injection) | translate call (question text) | high | mitigate | `prompt_builder.py:1419` — `<user_question>{json.dumps(...)}</user_question>` tag-isolation, mirroring the red-teamed `<scanner_data>` contract; question never enters `system` (`prompt_builder.py:1529`). CI-blocking: `test_ai_injection_redteam.py` runs 17 adversarial payloads × the `query_translate` capability | closed |
| T-44-02 | Information Disclosure | query execution (cross-tenant) | high | mitigate | `schemas.py:238` — no `tenant_id` field on any `*FilterInput`; `query.py:56` passes `tenant_id=user.tenant_id` (session) to `_run_query_stream`; `query_assistant.py:306` executes with the authenticated tenant only | closed |
| T-44-03 | Tampering | emitted filter (hallucinated field/enum) | medium | mitigate | `schemas.py:194,212,224,241` `model_config = {"extra": "forbid"}` on every `*FilterInput`; `schemas.py:261 recheck_nlq_filter_exclusivity` enforces exactly-one-entity structurally | closed |
| T-44-04 | Tampering | free-form SQL | high | accept | Structurally impossible (D-01): the model emits only a Pydantic filter object executed via the existing parameterized ORM `list_*` funcs — no SQL/query string is ever emitted or interpolated | closed |
| T-44-05 | Denial of Service (financial) | repeated/oversized question | medium | mitigate | `query.py:43` `Field(..., min_length=1, max_length=500)`; `query_assistant.py:170` `max_tokens=MAX_TOKENS`; `query_assistant.py:313` `check_tenant_budget` fail-closed; `query_assistant.py:330` `acquire_inflight` anti-stampede; D-19 translation cache | closed |
| T-44-06 | Information Disclosure | narrate fabricating rows/counts | medium | mitigate | Narrate grounds on ONLY the executed rows + deterministic count; `schemas.py:253 NlqAnswerResponse` schema-validated; deterministic totals (`paginated.total`), never model-computed (D-13) | closed |
| T-44-07 | Tampering | model-emitted hostname/asset_id | medium | mitigate | `query_assistant.py:198 _resolve_hostname` deterministically maps a model-emitted hostname → UUID within the tenant (`query_assistant.py:444`); a model-supplied UUID is never trusted | closed |
| T-44-08 | Information Disclosure | stale `sla_breached` mirror | low | accept | ≤60s staleness window on an ad-hoc analyst query is acceptable — the same tradeoff Phase 40 alerting already accepts | closed |
| T-44-09 | Tampering (XSS) | narrative / interpreted / result-row render | high | mitigate | React escapes by default; no `dangerouslySetInnerHTML` anywhere under `dashboard/ask/`; reuses the `AiExplanationCitations`/`InterpretedFilter` text render path | closed |
| T-44-10 | Information Disclosure | Bearer token handling | medium | mitigate | Token sent only in the `Authorization` header to the same-origin API (mirrors `useExplainStream`), never logged or placed in a URL | closed |
| T-44-11 | Tampering (reflected XSS / param injection) | Open-in deep-link + list-page URL param reads | high | mitigate | `nlq-deep-link.ts` emits only clamped param names; `use-url-state-scalar.ts` clamps to default (allow-list `'true'\|'false'` / bounded numeric); tickets page UUID-shape regex clamp — proven against a literal `<script>` payload in `use-url-state-scalar.test.ts` | closed |
| T-44-12 | Elevation of Privilege (cross-tenant via crafted param) | list query execution | high | accept | Params only populate a filter object; both list routers still scope every query by the authenticated session `tenant_id` server-side (unchanged) — no client param can widen tenant scope | closed |
| T-44-13 | Repudiation | undetected eval/red-team regression | medium | mitigate | `test_ai_injection_redteam.py` + `tests/evals/test_nlq_golden_evals.py` are CI-blocking (branch-protection required checks) — an NLQ eval/red-team failure blocks merge | closed |
| T-44-14 | Elevation of Privilege | reaching the ask flow without a BYOK key | high | mitigate | `use-ai-status.ts` gate renders the inert Configure-AI state; backend fail-closes with `{"type":"no_key"}` at `query_assistant.py:310` before any budget/model call — no shared/fallback key path exists (NLQ-03) | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on (high) count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-44-01 | T-44-04 | Free-form SQL is structurally impossible (D-01): the model emits only a validated Pydantic filter object executed through the existing parameterized ORM `list_*` functions; no SQL string is ever produced. | gsd-security-auditor | 2026-08-25 |
| AR-44-02 | T-44-08 | A ≤60s staleness window on the `sla_breached` mirror for an ad-hoc analyst query is acceptable — identical to the tradeoff Phase 40 proactive alerting already accepts. | gsd-security-auditor | 2026-08-25 |
| AR-44-03 | T-44-12 | Deep-link/list params only populate a client-side filter object; the list services re-scope every query by the authenticated session `tenant_id` server-side, so no client-supplied param can widen tenant reach. | gsd-security-auditor | 2026-08-25 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-08-25 | 14 | 14 | 0 | gsd-secure-phase (ASVS L1, block_on: high) |

Register authored at plan time (all six `44-0N-PLAN.md` files carried a parseable `<threat_model>` block); all six `SUMMARY.md` files reported "no new threat flags". L1 grep-depth verification confirmed each mitigation's presence in the implementation (file:line anchors above). No high-severity threat left open.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-08-25
