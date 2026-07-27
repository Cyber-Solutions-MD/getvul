# Feature Research: AI-Assisted Vulnerability Triage ("Triage Copilot")

**Domain:** AI-assisted vulnerability-triage copilot features (LLM-on-top-of-existing-VM-platform)
**Researched:** 2026-07-25
**Confidence:** MEDIUM-HIGH — grounded in current production security-copilot products (Microsoft Security Copilot, CrowdStrike Charlotte AI / ExPRT.AI / Exposure Prioritization Agent, Wiz AI Agents) plus OWASP GenAI LLM Top 10 and RAG-citation UX research. Vendor marketing claims are noted as such (MEDIUM confidence on specific behavior); architectural/anti-pattern conclusions are HIGH confidence because they're corroborated across multiple independent sources and match GetVul's own explicit constraints (deterministic score stays authoritative, no autonomous remediation, tenant isolation).

**Scope note:** This file covers only the five NEW AI feature areas named in the milestone. Existing GetVul capabilities (correlation, drill-down, deterministic scoring, SLA, ticketing, CSPM, search) are treated as dependencies/grounding sources, not re-researched.

---

## Feature Landscape

### Area 1 — CVE/Finding Summarization + Business-Risk Framing

**What it is:** In the existing vuln drill-down panel (VULN-04), replace/augment the raw CVE description + scanner jargon with a plain-English summary and a "why this matters to you" business-risk framing pulled from the asset's own enrichment data (owner, criticality, internet-facing, MDM/HR context).

| Feature | Classification | Why | Complexity | Notes |
|---|---|---|---|---|
| 2–4 sentence plain-English summary per finding (not generic CVE-DB blurb, but this asset-instance) | Table stakes | This is the headline capability every vendor ships first (Microsoft Copilot "converts complex alerts into structured, actionable guidance"); an analyst who has to re-read raw CVE text got no value | LOW–MEDIUM | Must be per (CVE, host, scanner) tuple, not cached per-CVE-globally, since business-risk framing is asset-specific |
| Business-risk framing using existing asset/HR/MDM fields | Table stakes | Differentiates "CVSS 9.8" from "CVSS 9.8 on the CFO's laptop, internet-facing" — GetVul already has the enrichment data (ASSET-03), this is just narrating it | LOW | Zero new data dependency — pure prompt-engineering over existing fields |
| AI-content visual badge/disclaimer in the panel | Table stakes | Universal pattern across Copilot-class tools; also matches CLAUDE.md's "don't compose generic SaaS copy" bar — needs a designed, non-generic AI-attribution treatment, not a bolted-on "✨ AI" pill | LOW | Extend sketch-findings-getvul visual-language for a new "AI-generated" affordance |
| Streaming token-by-token render in the drill panel | Table stakes | Every current-gen copilot (Microsoft, CrowdStrike, ChatGPT-family) streams; a blocking spinner for 3–8s of LLM latency now reads as broken, not "loading" | MEDIUM | Needs SSE/websocket-free chunked HTTP or polling — GetVul is explicitly NOT adding websockets (Out of Scope: "Real-time websocket dashboards" — use chunked fetch/SSE-over-HTTP instead, which is compatible with that constraint since it's request-scoped, not a persistent dashboard socket) |
| Cross-scanner agreement/conflict synthesis ("3 scanners agree this is exploitable; 1 rates it Medium") | Differentiator | This is GetVul's actual moat (multi-scanner correlation, VULN-02) — no single-scanner competitor (Wiz, Qualys-native AI) can narrate cross-tool disagreement | MEDIUM | Depends on VULN-02 correlation data already existing |
| Delta summary on re-open ("what changed since last scan") | Differentiator | Reduces re-reading cost for recurring findings | MEDIUM | Needs a "last viewed" or scan-diff signal; nice-to-have, not blocking |
| Replacing the raw CVE description / scanner solution text entirely | Anti-feature | Analysts who distrust black boxes want the ground truth still visible, one click away — summarizing *over* source text, never *instead of* it | — | Keep raw scanner text expandable/visible alongside the AI summary, not removed |
| Eager summarization of every finding at ingest time | Anti-feature | Cost explosion (thousands of findings × every scan cycle) for content most will never be read; also stale the moment new scan data lands | — | Generate lazily on drill-panel open, cache by (finding content hash), invalidate on scanner-data change |

**Grounding/citation expectations:** Every summary claim must be traceable to (a) the scanner's own description/solution field, or (b) a specific GetVul DB field (asset.owner, asset.criticality, asset.internet_facing, CVE.kev_flag). No external knowledge beyond what's already in GetVul's tenant-scoped data — the CVE description itself should be pulled verbatim from scanner data, not regenerated from the model's (stale, training-cutoff) memory of the CVE. Cite via inline chips ("from Tenable" / "from asset record") rather than a footnote wall.

**Uncertainty/confidence surfacing:** If correlated scanners disagree (severity, description, exploitability), state the conflict explicitly rather than silently picking one source. If enrichment data needed for business-risk framing is missing (no owner, no MDM record), say so ("owner unknown — risk framing incomplete") rather than inventing plausible-sounding context.

**Streaming vs. blocking:** Streaming is the expected default. Skeleton/shimmer state until first token (reuses the existing SkeletonTable/EmptyState state-pattern family conceptually, extended for streamed text), then token-by-token reveal. A non-streaming fallback with a clear loading state is an acceptable engineering fallback for MVP but should not be the target UX.

---

### Area 2 — Asset-Aware Remediation Guidance

**What it is:** OS/package/config-aware remediation steps that start from the scanner's own "solution" text and translate it into actionable, host-specific instructions; feeds the ticket draft in Area 4.

| Feature | Classification | Why | Complexity | Notes |
|---|---|---|---|---|
| Verbatim/quoted restatement of the scanner's own solution field | Table stakes | This is the highest-hallucination-risk surface in the whole milestone (a wrong patch version can break production) — CrowdStrike's own Exposure Prioritization Agent frames its value as "plain-language remediation guidance" *grounded in* validated exploitability, not invented from scratch | LOW | Reuse existing per-source `solution`/`remediation` fields already ingested by connectors |
| OS-family/package-aware command translation (apt/yum/winget/registry) | Table stakes | GetVul already classifies OS family on the asset (Phase 12, `os_family`); translating generic scanner solution text into the right package-manager syntax for *this* host is the core value-add over reading the scanner console directly | MEDIUM | Depends on `os_family` field already shipped |
| Honest "no vendor remediation available" fallback | Table stakes | Silently fabricating confident-sounding steps when the scanner provided none is the single most dangerous failure mode here | LOW | Must degrade gracefully with a distinct visual state, not blend in with grounded guidance |
| Auto-populates ticket description draft | Table stakes | Directly required by the milestone; also the natural payoff of doing this work once instead of per-surface | LOW–MEDIUM | Feeds Area 4 |
| Batch/aggregate remediation across correlated findings on one host ("one patch fixes 12 of these 15") | Differentiator | Plays directly to VULN-04's existing per-remediation drill-down grouping — a capability competitors without cross-scanner correlation structurally can't offer | MEDIUM–HIGH | Needs grouping logic over the existing remediation-drill-down data model |
| Suppress/ignore-history awareness ("similar CVE previously suppressed on this asset — still applies?") | Differentiator | Reuses existing CVE ignore/suppress audit trail (VULN-03) | MEDIUM | |
| Generating remediation from general LLM knowledge when scanner solution text is empty | Anti-feature | Confidently-worded but ungrounded patch/config advice is the top way to lose analyst trust in one incident | — | Fall back to a clearly-labeled "general guidance, unverified — confirm before applying" tier, never silently equal-weighted with grounded guidance |
| **Autonomous execution of remediation (auto-patch, auto-config-change, agent-executed fixes)** | **Anti-feature (hard)** | Explicitly out of scope per milestone framing; GetVul orchestrates ticketing, it doesn't execute changes on assets — it has no execution/agent layer today and building one is a different, much riskier product. Even AI vendors selling *agentic* remediation (Wiz's Green Agent) require explicit human approval before anything executes in production | — | Keep the boundary hard: GetVul's output is text into a ticket, never a command against a live host |

**Grounding/citation expectations:** Two-tier citation — (1) "scanner-provided" text quoted directly with a source chip, (2) "AI-interpreted" text (the OS-specific command derived from that source) visually distinguished so the analyst knows which part is verified vendor guidance vs. model translation.

**Uncertainty/confidence surfacing:** If OS/package detection is ambiguous (mixed fleet, unclear package manager), either ask or present multiple OS-specific variants rather than guessing one silently.

**Streaming vs. blocking:** Streaming acceptable during generation, but the final remediation text needs a stable, non-streaming "settled" state before it's copyable into a ticket draft — an in-flight streaming string shouldn't be what gets pasted into Area 4's form.

---

### Area 3 — AI Prioritization / "What to Fix First and Why" (augments the deterministic score)

**What it is:** A narrative layer that explains and augments GetVul's existing deterministic risk score (ASSET-02: piecewise log curve + severity weights + exploit/KEV multipliers) — never a second, competing AI-generated score.

This is the area where the milestone's explicit constraint ("deterministic risk scoring stays and is *explained/augmented*, never replaced") most directly shapes what's table-stakes vs. anti-feature. Industry precedent for this exact split exists: CrowdStrike's ExPRT.AI computes/adjusts the quantitative score using real-time threat intel, while Charlotte AI is a *separate* explanatory layer that "exposes the Exposure Prioritization Agent logic and allows analysts to ask why a vulnerability is prioritized" — the score and the narrative are architecturally distinct outputs, which is exactly the boundary GetVul needs.

| Feature | Classification | Why | Complexity | Notes |
|---|---|---|---|---|
| Narrative explanation of the EXISTING deterministic score ("why is this an 87") | Table stakes | This is the trust-building core of the whole milestone — turns the black-box-distrust problem into "the math was always deterministic, the LLM just translates it" | LOW–MEDIUM | Feed the score's *contributing factors* (severity weight, exploit multiplier, KEV flag, SLA state) as structured input to the LLM, not raw free text — this makes it a translation task, not open reasoning, which is a materially lower hallucination-risk architecture |
| Batch "what to fix first" narrative on the vuln list, layering exploit/KEV/owner/SLA context on top of the existing score's rank order | Table stakes | Directly named in the milestone; matches CrowdStrike's pattern of combining a quantitative score with an LLM explanation layer | MEDIUM | Must not silently re-sort the list on hidden AI judgment — see anti-features below |
| Interactive "ask why" follow-up per item | Differentiator | Mirrors Charlotte AI's explicit "ask why it's prioritized" capability; turns a static narrative into a trust-building conversation | MEDIUM | Grounded Q&A over the same structured factors as the narrative, not open-ended chat |
| Fix-together grouping surfaced in the triage narrative (across hosts, not just one) | Differentiator | Extends Area 2's batch remediation idea to the prioritization view | MEDIUM–HIGH | |
| SLA-aware narrative explicitly citing existing SLA-01 breach/at-risk state | Differentiator | Reuses shipped SLA infrastructure directly | LOW | |
| **A second, AI-generated 0–100 risk score competing with/replacing ASSET-02** | **Anti-feature (hard)** | Named explicitly in the milestone as something to avoid; also the single fastest way to reintroduce the black-box-distrust problem the whole milestone exists to solve | — | One score, one source of truth; AI narrative is prose, never a number |
| Auto-reordering the vuln list purely on hidden AI judgment, with no way to see/toggle back to deterministic sort | Anti-feature | Removes analyst control and auditability — GetVul's core value prop is the analyst deciding, not the AI deciding invisibly | — | AI suggestions should be an overlay/badge/filter on top of the deterministic sort, never a silent resort the analyst can't undo |
| Autonomous batch "auto-fix the top N" action without per-item review | Anti-feature | Conflicts with the ticket-drafting boundary in Area 4 (draft, never auto-submit) | — | Batch view can *suggest* a batch of tickets to draft, but each still needs individual confirm |

**Grounding/citation expectations:** Every "why" sentence should map to a real, already-computed DB field (KEV flag, exploit-available flag, SLA due date, asset criticality/owner, cross-scanner correlation count) — not free-floating LLM reasoning from scratch. Architecturally: pass the score's structured contributing factors into the prompt, don't ask the model to re-derive prioritization logic independently.

**Uncertainty/confidence surfacing:** Because this is explanatory text over already-computed, deterministic inputs, hallucination risk is comparatively low — but any language claiming attackers are "likely" to target something goes beyond GetVul's own data (KEV is a dated, authoritative government list; general exploit-likelihood commentary is closer to opinion). Flag speculative threat-framing language distinctly from KEV/exploit-flag citations, which are simple factual lookups.

**Streaming vs. blocking:** Per-item "why" in a drill panel: stream, same as Area 1. Batch/list-level narrative covering many findings at once is more expensive and less latency-sensitive (analyst is scanning a list, not waiting on one answer) — consider precomputed/cached with an explicit "regenerate" affordance rather than live per-row streaming.

---

### Area 4 — AI Ticket Auto-Drafting

**What it is:** Pre-fills the existing Jira/Asana create-ticket flow (TKT-01) with an AI-drafted title, description, remediation steps, and asset context — the analyst reviews, edits, and submits.

| Feature | Classification | Why | Complexity | Notes |
|---|---|---|---|---|
| Draft-only, never auto-submit — a human click always creates the ticket | Table stakes | Directly stated in the milestone ("analyst edits and ships"); also required to preserve GetVul's existing audit trail (AUDIT-01) and RBAC model — ticket authorship/accountability matters | LOW | The existing TKT-01 create flow is unchanged; only its fields start pre-filled |
| Reuses Areas 1–2's already-computed summary/remediation rather than re-deriving from scratch | Table stakes | Avoids redundant LLM calls (cost, per the milestone's own cost/observability gate) and keeps the ticket consistent with what the analyst already saw in the drill panel | LOW–MEDIUM | Architectural requirement, not a UX one |
| Provider-schema-aware field mapping (Jira issue-type fields vs. Asana task fields) | Table stakes | Reuses the existing TKT-01 connector abstraction; nothing new to invent | LOW | Note: milestone's ingestion-reliability precursor is fixing/finishing Jira ticket-create and GitHub ticketing — Area 4 depends on those being wired first |
| Cross-scanner correlation context embedded in the ticket body ("flagged by Tenable + Qualys, confirmed exploitable per KEV") | Differentiator | Plays to GetVul's actual multi-scanner differentiator; a single-scanner competitor's AI drafting can't cite corroborating tools | MEDIUM | |
| Auto-suggest bundling correlated findings on one host into a single ticket | Differentiator | Extends Area 2's batch remediation grouping into the ticketing surface | MEDIUM–HIGH | |
| Embedded permalink back to the GetVul drill-panel/finding in the ticket body | Differentiator | Whoever picks up the Jira/Asana ticket later often won't have GetVul open — a traceable link back to the grounding source is a real trust/audit win, mirroring the "citations are the trust surface" pattern seen across enterprise copilot products | LOW | |
| **Auto-submitting the ticket without review** | **Anti-feature (hard)** | Explicitly excluded by the milestone; breaks the audit/accountability chain (who authored this ticket — a human or a model?) | — | |
| AI autonomously selecting/assigning the ticket owner | Anti-feature | Should *suggest* an owner using existing IdP/MDM/HR asset-owner identification (ASSET-03), but writing the assignment field without analyst confirmation removes a decision point that matters for accountability | — | Suggest, don't silently assign |
| Autonomous post-creation ticket lifecycle actions (auto-comment, auto-close, auto-update based on new scan data) | Anti-feature | Milestone scope is drafting at creation time only; an AI that keeps acting on a ticket after creation is a different, unscoped feature with its own risk surface | — | Out of scope for this milestone; could be a future milestone with its own guardrail design |

**Grounding/citation expectations:** The ticket body should carry forward the same citation trail established in Areas 1–2 (scanner solution text, CVE fields, correlation sources) — the ticket is often the *only* artifact a downstream engineer without GetVul access will see, so it needs to be self-auditable, not just the drill panel.

**Uncertainty/confidence surfacing:** If the underlying summary/remediation carried a low-confidence or "no vendor guidance available" flag, that must propagate visibly into the draft (e.g., a footer note: "AI-drafted from partial data — verify remediation steps") rather than being silently dropped once it becomes plain ticket text.

**Streaming vs. blocking:** MEDIUM confidence this should default to blocking-with-skeleton rather than streaming. Ticket text needs to land as a finished, stable, directly-editable string in a form field — streaming into an editable textarea has known cursor-jump/edit-race UX friction if the analyst starts typing before the stream settles. A brief "Drafting ticket..." loading state (reusing existing state-pattern primitives) followed by a fully-populated form is simpler and safer than partial-field streaming.

---

### Area 5 — Natural-Language Query Over the Vuln Inventory (optional)

**What it is:** A conversational query surface over GetVul's own vuln/asset data. Marked "optional" in the research question and not named as its own phase in the milestone's target-feature list (Area 3's "natural-language triage assistant" is the prioritization narrative, not general NL search) — treat this as a lower-priority, clearly-scoped addition, not a chat-everything feature.

| Feature | Classification | Why | Complexity | Notes |
|---|---|---|---|---|
| NL query translated into parameters of the EXISTING filter/facet API (chip-bar, SEARCH-01), never freeform SQL | Table stakes (if built) | This is the one safety-critical architectural choice for this area — see anti-feature below | MEDIUM | Reuses UX-03's chip-bar filter contract and SEARCH-01's Cmd+K infra |
| Results rendered via the existing list/table UI (SkeletonTable etc.), not a chat transcript dump of raw rows | Table stakes (if built) | Keeps this "the search bar got smarter," consistent with copy-voice.md's no-bolt-on-chatbot stance | LOW–MEDIUM | |
| Tenant/RBAC scoping identical to the human-driven search path — no bypass channel | Table stakes (if built) | The query layer's tenant_id scoping is a hard constraint (TENANT-01); an LLM-constructed query must go through the same scoped endpoints, never a new unscoped path | LOW (if architected correctly), HIGH RISK (if not) | |
| Shows the interpreted filter as reviewable chips before/alongside running ("Severity: Critical, OS: Windows, SLA: Breached") | Table stakes (if built) | Lets the analyst confirm intent matched interpretation — directly reuses the existing ChipBar primitive from UX-03, a natural implementation hook | LOW–MEDIUM | This is also the confidence/uncertainty mechanism for this feature |
| Conversational follow-up refinement ("...only on Windows hosts" narrows prior result set) | Differentiator | Nice-to-have; not required for the core value | MEDIUM | |
| Saved-query creation from an NL query, feeding TKT-02's existing saved-filter automation | Differentiator | Ties a new feature into an existing one instead of creating a parallel system | MEDIUM | |
| **Freeform text-to-SQL directly against Postgres** | **Anti-feature (hard)** | Compounds prompt-injection risk with SQL-injection risk (documented text-to-SQL attack research shows parsers can be misled into harmful queries) and — more specifically to GetVul — bypasses the tenant_id scoping that today lives entirely in the query/ORM layer, not as a string an LLM assembles. A bounded function-calling schema over pre-scoped endpoints is the only acceptable design | — | This is the single highest-severity anti-feature in the whole research file: getting it wrong risks cross-tenant data leakage |
| A general-purpose chatbot answering anything beyond GetVul's own data | Anti-feature | Scope creep with no security-analyst value and its own unbounded risk surface | — | Keep the query domain hard-scoped to vuln/asset/ticket/CSPM data already in GetVul |
| A separate first-class chat-transcript UI replacing the dashboard IA | Anti-feature | Conflicts with the existing app-shell/page-layout design system and copy-voice's stance against generic SaaS chat-bolt-ons | — | Should feel like an enhanced search bar, not a new app surface |

**Grounding/citation expectations:** Every result set must be the literal output of a real, tenant-scoped query — never the LLM paraphrasing or inventing counts/rows. The LLM's only job is intent → filter-parameter translation; the deterministic query engine (already built, already tenant-scoped) returns ground truth. "Citation" here effectively means "these are your real N vulnerabilities matching X/Y/Z," which is inherently grounded because it never leaves the existing data path.

**Uncertainty/confidence surfacing:** If an NL query doesn't map cleanly to available filters, ask a clarifying question or show the best-guess interpreted chips before running rather than guessing silently and returning a confidently-wrong result set.

**Streaming vs. blocking:** Streaming acknowledgment of query interpretation ("Searching for Critical severity, Windows, SLA breached...") is a nice touch; the actual result-set render should be blocking/table-based via the existing SkeletonTable pattern — not streamed row-by-row.

---

## Cross-Cutting Anti-Features (Milestone-Level)

These apply across all five areas and are called out separately because they're the ones most likely to be requested/assumed by stakeholders unfamiliar with the trust dynamics of security tooling:

| Feature | Why Requested | Why Problematic | Alternative |
|---|---|---|---|
| Fully autonomous auto-remediation / auto-patching | "The AI already knows the fix, why not just apply it?" | Executing changes against production assets from unattended LLM output is the single highest-blast-radius failure mode possible in this milestone; even vendors selling *agentic* remediation (Wiz Green Agent) gate execution behind explicit human approval | Draft-only remediation text feeding a ticket; GetVul has no execution/agent layer and should not grow one in this milestone |
| An AI-generated risk score alongside/instead of the deterministic one | "Wouldn't a smarter model prioritize better?" | Reintroduces exactly the black-box-distrust problem this milestone exists to solve; two competing scores also breaks the RiskRing/UI's single source of truth | Keep ASSET-02's formula authoritative; AI narrates and explains it, never computes a competing number |
| Auto-submitting AI-drafted tickets without human review | "Save the analyst a click" | Breaks audit trail / accountability (AUDIT-01, RBAC) — who authored this ticket matters when something goes wrong | Draft-and-review is the floor; auto-submit is out of scope entirely |
| Freeform LLM-to-SQL or unrestricted tool-calling against the DB | "More flexible than fixed filters" | Compounds prompt-injection with SQL-injection risk and bypasses tenant_id scoping that today only exists in the query layer | Bounded function-calling over existing, already-scoped endpoints only |
| Treating scanner/finding text as trusted instruction context | Convenience of "just paste the CVE description into the prompt" | CVE descriptions, hostnames, and finding titles are attacker-controllable (a vendor's raw feed, or in principle a crafted hostname) — OWASP ranks prompt injection as the #1 LLM risk (LLM01), with reported attack success rates of 50-84% against undefended systems, and no complete fix exists even from frontier labs | Treat all scanner/finding text strictly as untrusted data, never as instructions; system-prompt/user-data separation, output validation, and no tool-calling permissions derived from within that text |
| No visual distinction between AI-generated and human/scanner-authored content | "It reads more naturally blended in" | Blending erodes exactly the "distrust black boxes" trust bar the milestone targets — an analyst needs to instantly know what's verified-source vs. model-generated | A consistent, designed AI-attribution treatment (badge + citation chips) across all five areas |
| A standalone chat app / chatbot persona replacing the dashboard | "Chat is the trendy AI UX" | Conflicts with the existing information architecture, state-pattern primitives, and copy-voice stance against generic SaaS bolt-ons; also makes grounding/citation harder to keep tight per-answer | Surface AI in-context: drill panel, list view, ticket-create flow — not a new chat surface |

---

## Feature Dependencies

```
Ingestion-reliability precursor (Wiz/Rapid7 wiring fix, connector HTTP tests, sync-health surface)
    └──requires──> nothing new (fixes existing connectors) — but is a PRECONDITION for everything below
                       "AI is only as good as its grounding" — garbage scanner data in, garbage AI output out

AI foundation (Claude integration + prompt/eval scaffolding + guardrails)
    └──requires──> Ingestion-reliability precursor
    └──gates──> Areas 1, 2, 3, 4, 5 (nothing below ships without this layer)

Area 1 — Summarization + business-risk framing
    └──requires──> AI foundation
    └──requires──> ASSET-03 (HR/MDM enrichment) for business-risk framing
    └──requires──> VULN-02 (cross-source correlation) for cross-scanner synthesis differentiator

Area 2 — Asset-aware remediation guidance
    └──requires──> Area 1 (shares the same grounding/citation pipeline)
    └──requires──> os_family field (shipped, Phase 12 / ASSET-01 delta)
    └──requires──> VULN-04 (per-remediation drill-down) for batch-grouping differentiator

Area 3 — Prioritization narrative ("what to fix first and why")
    └──requires──> ASSET-02 (deterministic risk score) — narrates it, never replaces it
    └──requires──> SLA-01 (breach/at-risk state) for SLA-aware narrative
    └──requires──> VULN-02 (correlation count) for cross-scanner "why" context
    └──enhances──> the existing vuln list, does not replace its sort/rank UI

Area 4 — AI ticket auto-drafting
    └──requires──> Area 1 (summary) + Area 2 (remediation) — reuses their output, doesn't re-derive
    └──requires──> TKT-01 (Jira/Asana create flow) — pre-fills it, doesn't replace it
    └──requires──> ingestion-reliability precursor's "wire Jira ticket-create + finish GitHub ticketing" sub-item

Area 5 — NL query over inventory (optional)
    └──requires──> SEARCH-01 (existing Cmd+K search) + UX-03 chip-bar filter API
    └──must-not-bypass──> TENANT-01 (tenant_id scoping) — bounded function-calling only, never freeform SQL

Eval + guardrail + cost/observability gate
    └──gates──> production readiness of Areas 1–5 (not a user-visible feature; the milestone-closing quality bar)

[Fully autonomous auto-remediation] ──conflicts──> [existing "GetVul orchestrates, doesn't execute" constraint]
[AI-generated competing risk score]  ──conflicts──> [ASSET-02 deterministic score as single source of truth]
[Freeform LLM-to-SQL]                ──conflicts──> [TENANT-01 tenant isolation]
```

### Dependency Notes

- **Everything requires the ingestion-reliability precursor first:** the milestone plan itself states this ("AI is only as good as its grounding") — Wiz and Rapid7 findings are silently broken today, so summarization/remediation/prioritization built on top of them would confidently narrate wrong or missing data. This is a hard phase-ordering constraint, not a nice-to-have.
- **Areas 1 and 2 share a grounding/citation pipeline:** both cite scanner-provided text (description/solution fields) and both need the two-tier "scanner-provided vs. AI-interpreted" citation treatment. Building Area 1 first establishes the pattern Area 2 reuses.
- **Area 4 is a consumer, not a producer:** it should not re-run summarization/remediation LLM calls independently — it assembles already-computed Area 1/2 output into the existing ticket form. This matters for the cost-budgeting guardrail (fewer redundant LLM calls).
- **Area 3 is architecturally different from 1/2/4:** its LLM task is narrating already-computed, structured, deterministic inputs (score factors, SLA state, KEV flag) rather than grounding against free-text scanner descriptions. This is a materially lower hallucination-risk task and should be built as prompt-over-structured-data, not prompt-over-raw-text.
- **Area 5 conflicts with any temptation toward general-purpose LLM DB access:** the safest design constrains the model to choosing among the existing filter/facet parameters (a closed function-calling schema), never generating SQL or ORM code. This is the one area where getting the architecture wrong has cross-tenant data-leakage consequences, not just a wrong answer.
- **Autonomous action anti-features (auto-remediate, auto-score, auto-submit, freeform SQL) all conflict with existing platform constraints**, not just abstract AI-safety principles — GetVul already has no execution layer, already has one authoritative score field, already gates ticket creation behind RBAC/audit, and already enforces tenant_id at the query layer. Each anti-feature would require *removing or bypassing* something that already exists, which is a strong signal they're out of bounds for this milestone.

---

## MVP Definition

The milestone's own "Target features" list already specifies a vertical-slice order (continuing phase numbering from 22); this MVP section aligns with and elaborates on that order rather than proposing a different one.

### Launch With (v1 — first vertical slices)

- [ ] **Ingestion-reliability precursor** (Wiz/Rapid7 fixes, connector integration tests, sync-health surface) — not a user-facing AI feature, but everything else silently produces wrong output without it
- [ ] **AI foundation layer** (model integration, prompt/eval scaffolding, prompt-injection/PII/cost guardrails) — must ship *with*, not after, the first user-visible feature; guardrails-as-afterthought is the exact anti-pattern to avoid given scanner/vuln text is attacker-controllable
- [ ] **Area 1 — "Explain this vuln"** (plain-English summary + business-risk framing in the drill panel) — the simplest, most contained, most trust-building slice: it takes no actions, only explains, which is the right feature to earn analyst trust with before asking them to trust remediation/ticket content

### Add After Validation (v1.x)

- [ ] **Area 2 — Asset-aware remediation guidance** — trigger: Area 1's grounding/citation pattern is validated and trusted; reuses that pipeline directly
- [ ] **Area 3 — Prioritization narrative** — trigger: confidence that the narrative layer stays visually/architecturally subordinate to the deterministic score (no score-replacement drift)
- [ ] **Area 4 — AI ticket auto-drafting** — trigger: Areas 1–2 output is stable enough to assemble into a ticket without re-deriving; also gated on the ingestion-reliability precursor's Jira-create/GitHub-ticketing wiring being complete

### Future Consideration (v2+)

- [ ] **Area 5 — NL query over the vuln inventory** — defer: not named as its own phase in the milestone's target-feature list, lower analyst pull than the other four (existing chip-bar/search already covers most filtering needs), and carries the highest-severity anti-feature risk (tenant-scoping bypass) if rushed
- [ ] **Interactive "ask why" follow-up chat** (Area 3 differentiator) — defer until the static narrative version is proven; conversational follow-up adds state-management and grounding-consistency complexity
- [ ] **Cross-host batch remediation grouping** (Areas 2/4 differentiator) — defer until single-finding remediation guidance is solid; grouping logic is materially more complex than per-finding guidance

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---|---|---|---|
| Area 1 — Summarization + business-risk framing | HIGH | MEDIUM | P1 |
| AI foundation + guardrails (prompt-injection/PII/cost) | HIGH (enabling) | MEDIUM–HIGH | P1 |
| Ingestion-reliability precursor | HIGH (enabling) | MEDIUM | P1 |
| Area 2 — Asset-aware remediation guidance | HIGH | MEDIUM–HIGH | P1 |
| Area 3 — Prioritization narrative (why, not a new score) | HIGH | MEDIUM | P1 |
| Area 4 — AI ticket auto-drafting | HIGH | MEDIUM | P1 |
| Eval + guardrail + cost/observability gate | HIGH (enabling, closes milestone) | MEDIUM | P1 |
| Cross-scanner synthesis in summaries (Area 1 differentiator) | MEDIUM | LOW–MEDIUM | P2 |
| Batch remediation grouping (Area 2 differentiator) | MEDIUM–HIGH | HIGH | P2 |
| Interactive "ask why" (Area 3 differentiator) | MEDIUM | MEDIUM–HIGH | P2 |
| Embedded permalink + correlation context in ticket drafts (Area 4 differentiator) | MEDIUM | LOW | P2 |
| Area 5 — NL query over inventory | MEDIUM | MEDIUM–HIGH (safety-critical if done wrong) | P3 |
| Delta summaries on re-open (Area 1 differentiator) | LOW–MEDIUM | MEDIUM | P3 |
| Saved-query from NL query (Area 5 differentiator) | LOW | MEDIUM | P3 |

**Priority key:**
- P1: Must have for the v3.0 milestone as scoped
- P2: Should have, natural follow-on once P1 areas are trusted in production
- P3: Nice to have, defer past this milestone

---

## Competitor / Adjacent-Product Feature Analysis

| Feature | Microsoft Security Copilot | CrowdStrike Charlotte AI / ExPRT.AI | Wiz AI Agents | Our Approach (GetVul) |
|---|---|---|---|---|
| Plain-English summarization | Converts alerts into "structured, actionable summaries," suppressing noise across signals | N/A (endpoint/exposure focus, not general summarization) | Security Graph context feeds agent reasoning | Area 1 — per-finding, asset-instance-specific, cites scanner text directly, cross-scanner-aware (our correlation moat) |
| Prioritization explanation vs. scoring | "Guided responses" recommend triage/containment/investigation/remediation actions as categorized suggestions | ExPRT.AI computes/adjusts the *quantitative* score using real-time threat intel; Charlotte AI is a *separate* layer that lets analysts "ask why" — score and narrative are architecturally distinct | Agents draw on the Security Graph "combining deep context with explainable reasoning" | Area 3 mirrors the Charlotte AI split precisely: ASSET-02's deterministic score stays authoritative, LLM only narrates/explains it — never a second score |
| Remediation guidance | Guided-response "Remediation" category recommends response actions per entity | Exposure Prioritization Agent gives "plain-language remediation guidance," validates exploitability before recommending | Green Agent synthesizes root cause + "safest, most effective resolution" from Security Graph + code-to-cloud + identity + historical remediation patterns — but explicitly **never executes in production without approval** | Area 2 — grounded in the scanner's own solution text first, OS/package translation second; no execution layer, ever (matches Wiz's own approval-gate boundary) |
| Ticket/case drafting | Not a headline Copilot feature in public docs reviewed | Charlotte Agentic SOAR "orchestrates... triage and remediation workflow" including ITSM/patching tool integration (more automation-forward than GetVul intends) | N/A in reviewed sources | Area 4 — draft-only into existing Jira/Asana flow, human always clicks "create"; deliberately less automated than CrowdStrike's SOAR framing, by design (matches GetVul's "orchestrate, don't execute" model) |
| Confidence/verification on AI findings | Not detailed in reviewed sources | Not detailed in reviewed sources | Explicitly stated: "every AI-generated finding needs a confidence score... dual-verification is required before any AI finding surfaces to an analyst or triggers downstream action" | Matches this bar: every AI output in Areas 1–4 carries an explicit grounding/citation trail and a distinct "AI-interpreted vs. source-verified" visual tier; Area 5 constrained to bounded, verifiable query translation |
| NL query surface | Natural-language prompting is the core Copilot interaction model (chat-first product) | Not the primary interaction model (agent/dashboard-first) | Not the primary interaction model (graph/dashboard-first) | Area 5 deliberately narrower than Microsoft's chat-first model — bounded function-calling over existing filter API, embedded in the existing dashboard IA, not a standalone chat product |

---

## Sources

- [What is Microsoft Security Copilot? | Microsoft Learn](https://learn.microsoft.com/en-us/copilot/security/microsoft-security-copilot) — MEDIUM confidence (official docs)
- [Triage and investigate incidents with guided responses with Microsoft Copilot in Microsoft Defender | Microsoft Learn](https://learn.microsoft.com/en-us/defender-xdr/security-copilot-m365d-guided-response) — MEDIUM confidence (official docs)
- [CrowdStrike Introduces Charlotte AI, Generative AI Security Analyst](https://www.crowdstrike.com/en-us/blog/crowdstrike-introduces-charlotte-ai-to-deliver-generative-ai-powered-cybersecurity/) — MEDIUM confidence (vendor blog, cross-checked against product page)
- [ExPRT.AI | CrowdStrike Falcon Exposure Management](https://www.crowdstrike.com/en-us/platform/exposure-management/risk-prioritization/) — MEDIUM confidence (vendor product page)
- [AI Innovations Powering Falcon Exposure Management | CrowdStrike](https://www.crowdstrike.com/en-us/blog/built-for-scale-powered-by-ai-innovation-driving-falcon-exposure-management/) — MEDIUM confidence (vendor blog)
- [AI Security Graphs Explained: Contextual Risk for AI Systems | Wiz](https://www.wiz.io/academy/ai-security/ai-security-graph) — MEDIUM confidence (vendor content, but explicit re: dual-verification/confidence scoring — a specific, checkable claim)
- [Introducing the Green Agent: AI-Powered Remediation | Wiz Blog](https://www.wiz.io/blog/introducing-wiz-green-agent) — MEDIUM confidence (vendor blog; "never executes in production without explicit approval" is a specific, load-bearing claim for our anti-feature reasoning)
- [LLM01:2025 Prompt Injection | OWASP Gen AI Security Project](https://genai.owasp.org/llmrisk/llm01-prompt-injection/) — HIGH confidence (industry-standard reference, cross-checked against multiple secondary sources)
- [Prompt injection: types, real-world CVEs, and enterprise defenses | Vectra AI](https://www.vectra.ai/topics/prompt-injection) — MEDIUM confidence (vendor content, but consistent with OWASP framing and cites real CVEs — CVE-2025-53773 GitHub Copilot chain, Microsoft/Cursor CVSS scores)
- [Malicious Jira Tickets Exploit AI Workflows](https://www.techbeams.com/tech/malicious-jira-tickets-exploit-ai-workflows/) / [Jira tickets become attack vectors in PoC 'living off AI' attack | SC Media](https://www.scworld.com/news/jira-tickets-become-attack-vectors-in-poc-living-off-ai-attack) — MEDIUM confidence, directly relevant precedent: a real PoC where a crafted support-ticket body prompt-injected an AI ticketing assistant into leaking internal data — validates treating ticket/finding text as untrusted in Area 4
- [TrojanSQL: SQL Injection against Natural Language Interface to Database | ACL Anthology](https://aclanthology.org/2023.emnlp-main.264/) — MEDIUM confidence (peer-reviewed research) — supports the Area 5 anti-feature reasoning against freeform text-to-SQL
- [AI Copilot UX Design: How to Build Copilots Users Actually Trust](https://www.theskinsfactory.com/uiux-design-blog/ai-copilot-ux-design) — LOW-MEDIUM confidence (design-agency blog, general UX pattern corroboration, not a primary/technical source)
- [AI citation and source UI design patterns for 2026 | AYDesign](https://www.aydesign.ai/blog/ai-citation-source-ui-patterns-2026) — LOW-MEDIUM confidence (single secondary source on citation UX conventions; used only for corroborating widely-observed patterns — inline chips, source popovers, confidence-tied citation strength — not for any specific factual claim)
- GetVul's own `.planning/PROJECT.md` (existing shipped requirements VULN-01..04, ASSET-01..03, TKT-01/02, SLA-01, SEARCH-01, TENANT-01, RBAC-01, AUDIT-01) — HIGH confidence (primary source, internal)

---
*Feature research for: AI-Assisted Vulnerability Triage (v3.0 "Triage Copilot")*
*Researched: 2026-07-25*
