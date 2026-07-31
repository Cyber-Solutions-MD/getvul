# Requirements: GetVul v3.0 — AI-Assisted Triage ("Triage Copilot")

**Defined:** 2026-07-27
**Core Value:** A vuln-triage analyst can open one dashboard, see the same CVE-on-host correlated across multiple scanners, identify the asset's owner from IdP/MDM/HR, and ship a Jira/Asana ticket — without ever opening a scanner console. **v3.0 adds AI that helps the analyst *decide and act*, grounded in the tenant's own data, using the tenant's own AI key.**

## Foundational Principle — BYOK (bring-your-own-key)

All AI functionality is **client-provided-key only**. Each tenant supplies their **own** Anthropic API key and owns the AI integration; their vulnerability data is only ever sent to *their* AI account. There is **no GetVul-owned, shared, or fallback key** and **no GetVul-proxied inference offering**. AI features are **inert for a tenant until they configure their own key** (graceful "configure AI" state, not an error). This is a hard privacy guarantee that constrains AI-01, AI-05, and AIE-03/04 below.

## v1 Requirements (this milestone)

Each maps to exactly one phase (phases 23–28, continuing from v2.2).

### Ingestion Reliability (REL) — precursor

AI grounding is worthless on broken ingestion. Close the real gaps first.

- [x] **REL-01**: Wiz connector completes a full sync end-to-end (fix the `authenticate()` return-type wiring so a successful auth is not treated as failure)
- [x] **REL-02**: Rapid7 connector completes a full sync end-to-end (implement `authenticate()` / fix the no-arg instantiation `TypeError`)
- [x] **REL-03**: Every scanner connector (CrowdStrike, Nessus, Defender, Wiz, Qualys, Rapid7) has HTTP-layer integration tests covering auth + pagination + `fetch_vulnerabilities` mapping (mock transport)
- [x] **REL-04**: An analyst can create a **Jira** ticket from a vulnerability (wire Jira into the ticket-create + rule-engine paths, not just status sync)
- [x] **REL-05**: GitHub ticketing is finished end-to-end (create + sync) **or** explicitly retired — no dead stub referenced nowhere
- [x] **REL-06**: An analyst can see per-connector sync health (last sync time, last error, status) in the Connectors UI

### AI Foundation & Guardrails (AI)

- [x] **AI-01**: A tenant admin can configure their **own** Anthropic API key + model preferences (encrypted at rest via the Fernet/`ConnectorConfig` pattern); AI features are the ONLY consumers of that key and stay disabled until it is set — no shared/fallback key exists
- [x] **AI-02**: Untrusted scanner text (CVE descriptions, hostnames, finding titles) is delimited/encoded and passed to the model as **data** (`tool_result`), never as instructions; all model output is schema-validated (Pydantic) and never executed (prompt-injection + PII guardrails)
- [x] **AI-03**: AI responses stream token-by-token into the vuln drill panel (`fetch()` + `ReadableStream`; scoped nginx `location /api/v1/ai/` with `proxy_buffering off`)
- [x] **AI-04**: An analyst can get an "Explain this vuln" plain-English summary + business-risk framing in the drill panel, grounded in the correlated data with **two-tier citation** (verbatim scanner text vs. AI-interpreted)
- [x] **AI-05**: AI outputs are cached in Redis **tenant-scoped only**, content-hash keyed (no cross-tenant serving — an output billed on one tenant's key never reaches another)
- [x] **AI-06**: Every AI call is audit-logged (model, tokens, cost estimate, prompt provenance), including scheduler-originated calls (written directly with `user_email="system:scheduler"`, avoiding the `audit()` nil-tenant path)

### AI Remediation Guidance (AIR)

- [x] **AIR-01**: An analyst can get asset-aware remediation guidance that cites the scanner's own solution text and **refuses (cites insufficient evidence) rather than inventing** an ungrounded fix
- [x] **AIR-02**: Remediation guidance can populate a draft ticket description for the analyst to review

### AI Prioritization (AIP)

- [ ] **AIP-01**: An analyst can see a "what to fix first and why" narrative that **augments and explains — never replaces** — the deterministic risk score, using exploit/KEV/owner/SLA factors
- [x] **AIP-02**: Prioritization/triage suggestions are generated in bulk via the scheduler using the Message Batches API (cost-efficient), respecting the tenant's key

### AI Ticket Drafting (AID)

- [ ] **AID-01**: When creating a Jira/Asana ticket, an analyst gets an AI-drafted title/description/remediation/asset-context that they edit before shipping (never auto-submitted)

### AI Evals, Cost & Observability Gate (AIE)

- [ ] **AIE-01**: A DeepEval pytest-native eval harness runs in CI against golden sets seeded from real outputs, asserting on schema/grounding/citation (not brittle prose snapshots)
- [ ] **AIE-02**: A promptfoo red-team job (prompt-injection resistance over adversarial scanner text) runs as a separate CI check, alongside semgrep/ZAP
- [ ] **AIE-03**: A **fail-closed** per-tenant token-cost budget / circuit breaker halts AI calls when the tenant's configured budget is exceeded
- [ ] **AIE-04**: A tenant admin can see their AI usage + cost and manage AI settings (key, model, budget) in the UI

## Future Requirements (deferred)

### AI Natural-Language Query (AINL)

- **AINL-01**: Natural-language query over the vuln inventory — implemented strictly as **bounded function-calling over the existing already-tenant-scoped filter/search endpoints**, never generated SQL. Deferred to v3.1 so tenant-scoping gets a dedicated design-review gate (highest anti-feature risk in the milestone).

## Out of Scope

| Feature | Reason |
|---------|--------|
| GetVul-owned/shared/fallback AI key or GetVul-proxied inference | BYOK privacy guarantee — tenant data goes only to the tenant's own AI account |
| Cross-tenant / global AI-output cache | Output billed on one tenant's key must never serve another; caches are tenant-scoped |
| Fully-autonomous / agentic auto-remediation (execution) | GetVul has no execution layer; a human always approves and ships the fix |
| LLM-to-SQL / model-generated queries | Would bypass `tenant_id` scoping (which lives in the query layer) — hard security risk |
| Replacing the deterministic risk score (ASSET-02) with an ML/LLM score | The score stays authoritative; AI explains/augments it, never replaces it |
| Vector DB / embeddings / RAG | Correlation service already assembles grounding via SQL joins; no retrieval need this milestone |
| Non-Claude / self-hosted models | Milestone standardizes on Claude via the tenant's Anthropic key |

## Traceability

Coverage: 21/21 v1 requirements mapped, phases continue from 22. No orphans, no duplicates.

| Requirement | Phase | Status |
|-------------|-------|--------|
| REL-01 | 23 (Ingestion Reliability Precursor) | Complete |
| REL-02 | 23 (Ingestion Reliability Precursor) | Complete |
| REL-03 | 23 (Ingestion Reliability Precursor) | Complete |
| REL-04 | 23 (Ingestion Reliability Precursor) | Complete |
| REL-05 | 23 (Ingestion Reliability Precursor) | Complete |
| REL-06 | 23 (Ingestion Reliability Precursor) | Complete |
| AI-01 | 24 (AI Foundation + Explain-this-vuln) | Complete |
| AI-02 | 24 (AI Foundation + Explain-this-vuln) | Complete |
| AI-03 | 24 (AI Foundation + Explain-this-vuln) | Complete |
| AI-04 | 24 (AI Foundation + Explain-this-vuln) | Complete |
| AI-05 | 24 (AI Foundation + Explain-this-vuln) | Complete |
| AI-06 | 24 (AI Foundation + Explain-this-vuln) | Complete |
| AIR-01 | 25 (Asset-Aware Remediation Guidance) | Complete |
| AIR-02 | 25 (Asset-Aware Remediation Guidance) | Complete |
| AIP-01 | 26 (Prioritization Narrative) | Pending |
| AIP-02 | 26 (Prioritization Narrative) | Complete |
| AID-01 | 27 (Ticket Auto-Drafting) | Pending |
| AIE-01 | 28 (Eval + Cost + Observability Gate) | Pending |
| AIE-02 | 28 (Eval + Cost + Observability Gate) | Pending |
| AIE-03 | 28 (Eval + Cost + Observability Gate) | Pending |
| AIE-04 | 28 (Eval + Cost + Observability Gate) | Pending |
