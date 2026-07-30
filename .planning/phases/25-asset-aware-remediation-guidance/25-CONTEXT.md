# Phase 25: Asset-Aware Remediation Guidance - Context

**Gathered:** 2026-07-30
**Status:** Ready for planning

<domain>
## Phase Boundary

An analyst gets **actionable remediation guidance** for a finding — OS/package-aware steps grounded **strictly** in the scanner's own solution text plus asset facts — that **cites the vendor text verbatim before any AI interpretation**, and **refuses (cites insufficient evidence) rather than fabricating** a fix when no vendor guidance exists. The analyst can carry that guidance into a **draft ticket description** they review/edit before creating anything.

Requirements: **AIR-01** (asset-aware, cite-or-refuse remediation), **AIR-02** (guidance populates a draft ticket description for review). Both fixed by ROADMAP.md — this phase clarifies HOW, not WHAT.

This phase **reuses Phase 24's entire scaffold unchanged**: the `_run_explain_stream()` buffer→validate→replay engine, BYOK key resolution, tenant-scoped cache, fail-closed budget guard, audit writer, prompt-injection-as-data contract, and the frontend AI section + two-tier citation component. Phase 25 adds a new **grounding record + response-schema variant + prompt builder** for actionable remediation, a **safety denylist gate**, and a **draft-ticket pre-fill** hand-off — nothing more.
</domain>

<decisions>
## Implementation Decisions

### Cite-or-refuse (AIR-01 anti-fabrication core)
- **D-01:** Grounding source of truth for remediation is the finding's own scanner text: `Vulnerability.remediation_action` (primary) and `remediation_info` (fallback). The **refuse predicate** is a **deterministic pre-generation gate**: generate cited steps only when `remediation_action` OR `remediation_info` is present AND **non-generic** (not empty, not the `"No remediation info available"` placeholder the ticketing layer emits, above a small minimum content length). Otherwise **refuse** with a typed "insufficient evidence" state — no model call is spent. This is belt-and-suspenders with the output-schema `grounded` flag (mirrors Phase 24 D-24). — **Reversibility:** costly — the gate + `grounded=false` schema shape is a contract Phases 26–27 read.
- **D-02:** The refuse predicate is enforced in **two independent layers**: (1) the deterministic input gate above, and (2) the response-schema `grounded: false` path the model can still take if it judges the cited text too weak to produce safe steps. A refusal from either layer renders the same honest "not enough vendor guidance to recommend a fix" card, visually distinct from a system error (reuses Phase 24's grounded-false treatment, D-24).
- **D-03:** Cited vendor text is rendered **verbatim and visually first** (the `scanner_verbatim` tier), with any AI-authored interpretation clearly marked as the `ai_interpreted` tier — reusing Phase 24's inline two-tier citation component (D-13/D-14) unchanged. "Cite before interpret" is the ordering contract for AIR-01 success criterion 1.

### Dangerous-command safety net (Pitfall #2)
- **D-04:** A **post-generation dangerous-pattern gate** scans the produced steps against a maintained denylist (e.g. `rm -rf`, `DROP TABLE`, disable firewall/EDR, `dd`, `mkfs`, `chmod 777`, `curl … | sh`, and similar destructive/security-disabling patterns — exact list finalized at plan time). **On any hit the ENTIRE guidance is refused** and a **typed safety-refusal state** is shown; a partially-dangerous step set is never rendered. The hit is **audited** (distinct status). This is enforced as a code gate (schema-contract + regex), NOT prompt wording — the roadmap's Pitfall-#2 mitigation. — **Reversibility:** costly — the denylist + refusal status is a safety contract other phases inherit.
- **D-05:** The denylist is a **maintained constant/module** (single source of truth, unit-tested with positive + negative cases incl. obfuscation-resistant matching where cheap), so Phases 26–27 that also surface AI-authored text can reuse it. Exact patterns + case/whitespace normalization are a plan-time detail.

### UI surface
- **D-06:** Remediation guidance is a **SEPARATE "Remediation guidance" section/action** in the drill panel — its own trigger and its own cite-or-refuse output — **distinct** from Phase 24's "Explain this vuln" and the Phase-24 per-remediation **posture** summary (`explain_remediation`/`get_remediation_group`, D-16). Both coexist: "what is this / what's the posture" (Phase 24) vs. "how do I fix it" (Phase 25). It **reuses the exact AI section chrome + two-tier citation component** built in Phase 24 (no re-styling). — **Reversibility:** costly — a new drill-panel section + endpoint is a surface other phases build on.
- **D-07:** All Phase 24 UI-state contracts are inherited unchanged for this new section: "Analyzing…" then replay (D-12), no-key state (D-23), 429/busy (D-25), Analyst+ triggers / Viewer cached-only (D-17), thumbs feedback capture (D-21), audit into the existing pane (D-27). No new state vocabulary is invented.

### AIR-02 draft-ticket hand-off
- **D-08:** Guidance populates the **description field of the EXISTING drill-panel ticket-create flow** (the affordance from Phase 23 / D-14). The analyst **reviews and edits** the pre-filled description **in that same create dialog** before anything is created — satisfying AIR-02's "review/edit before creating" clause. Nothing is auto-created. — **Reversibility:** reversible — a pre-fill of an existing field.
- **D-09:** **Phase 25 pre-fills the description only.** Full auto-drafting (AI-authored title + remediation + asset-context, Jira/Asana field mapping, the richer draft surface) is **explicitly Phase 27 (AID-01)** and must NOT be built here. This keeps AIR-02 a thin, non-overlapping slice. — **Reversibility:** reversible (scope fence, not code).

### Grounding & engine reuse (defaults, not re-litigated)
- **D-10:** Reuse `_run_explain_stream()` and the Phase 24 grounding/cache/budget/audit/RBAC layers **unchanged**; Phase 25 adds only a new **remediation grounding-record assembler** + **`ExplainRemediation…`-style response schema variant** + **prompt builder**, following the exact per-view-variant pattern Phase 24 established for host/remediation (24-08). The asset-fact ("OS/package-aware") inputs come from the **same allowlisted asset fields** Phase 24's `HOST_ALLOWLIST`/`get_asset_posture()` already vet — **owner-PII fields stay excluded** (Phase 24 D-15 defense-in-depth). Exact field list for OS/package context is a researcher/planner detail, constrained to the existing allowlist discipline. — **Reversibility:** costly — a new schema variant is a contract Phase 27 consumes.

### Claude's Discretion
- Exact denylist patterns + normalization strategy (D-04/D-05).
- Exact minimum-content-length / generic-placeholder detection for the refuse predicate (D-01).
- The precise OS/package asset-fact field list feeding grounding, within the existing allowlist (D-10).
- Cache TTL window and prompt-version hashing are inherited from Phase 24 conventions (D-18/D-19/D-20) — no new decision.
- Exact drill-panel placement/ordering of the new Remediation section — a UI-SPEC decision (`/gsd-ui-phase 25`).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` §"Phase 25: Asset-Aware Remediation Guidance" — goal, 3 success criteria, Pitfall #2 ownership (cite-or-refuse + dangerous-pattern regex).
- `.planning/REQUIREMENTS.md` — AIR-01, AIR-02 (lines ~34–37, traceability ~91–92).

### Phase 24 decisions & artifacts this phase reuses (MUST read — the inherited scaffold)
- `.planning/phases/24-ai-foundation-explain-this-vuln/24-CONTEXT.md` — D-01..D-28 (BYOK, streaming, cache, budget, audit, RBAC, citation tiers, grounded-false, no-key/429 states, feedback, English-only) — nearly all carried forward unchanged.
- `.planning/phases/24-ai-foundation-explain-this-vuln/24-08-SUMMARY.md` — the per-view schema-variant + prompt-builder + grounding pattern (`ExplainHostResponse`/`ExplainRemediationResponse`, `HOST_ALLOWLIST`, `get_asset_posture()`/`get_remediation_group()`) this phase mirrors.
- `.planning/phases/24-ai-foundation-explain-this-vuln/24-04-SUMMARY.md` + `backend/app/ai/explain.py` — `_run_explain_stream()` engine reused unchanged.
- `.planning/phases/24-ai-foundation-explain-this-vuln/*-AI-SPEC.md` (if present) — grounding/eval/guardrail design contract.

### Code the phase touches / grounds in
- `backend/app/ai/grounding.py` — add the remediation-steps grounding-record assembler alongside `get_asset_posture()`/`get_remediation_group()`.
- `backend/app/ai/schemas.py`, `backend/app/ai/prompt_builder.py` — new remediation response-schema variant + allowlist + prompt builder.
- `backend/app/api/v1/ai/` — new remediation-guidance route (mirror `explain_remediation.py` registration).
- `Vulnerability.remediation_action` / `remediation_info` — the scanner solution grounding fields (see `backend/app/ticketing/service.py:135`, `daily_sync.py:147/183`).
- `backend/app/ticketing/router.py` / `service.py` + the drill-panel ticket-create flow (Phase 23 / D-14) — AIR-02 description pre-fill target.
- `.claude/skills/sketch-findings-getvul/` — MANDATORY before any UI: state-patterns (refuse/insufficient-evidence/safety states), copy-voice (honest refusal copy, no fabricated confidence), foundation (tokens/fonts), visual-language (citation tiers). Reuse Phase 24's AI section + citation component.

### Phase boundary (do NOT build)
- Phase 27 (AID-01) — full AI ticket auto-drafting (title/remediation/asset-context, provider field mapping). Phase 25 stops at description pre-fill.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/ai/explain.py::_run_explain_stream()` — the buffer→validate→(1 retry)→audit→cache→replay engine; reuse verbatim, only new grounding/schema/prompt vary.
- `backend/app/ai/grounding.py` — established tenant-scoped, PII-excluding grounding assemblers to mirror.
- Frontend AI Explanation section + `ai-explanation-citations` two-tier renderer (`frontend/src/components/ai/…`) + `useExplainStream`/`useAiStatus` hooks — reuse for the new Remediation section.
- Existing drill-panel ticket-create flow (Phase 23 / D-14) — AIR-02 pre-fill target.

### Established Patterns
- Per-view schema variant + allowlist + prompt builder + thin SSE route (Phase 24, 24-08) — the exact shape Phase 25's remediation variant follows.
- Deterministic grounding gate + `grounded=false` honest-refusal card (D-24) — the anti-fabrication pattern extended here to cite-or-refuse.
- Allowlist defense-in-depth for asset facts (`HOST_ALLOWLIST`, D-15) — owner PII never enters the prompt.

### Integration Points
- New remediation route mounts in `ai_router` (`backend/app/api/v1/ai/__init__.py`) like the Phase 24 explain routes.
- Description pre-fill wires the guidance output into the existing ticket-create dialog's description field.
</code_context>

<specifics>
## Specific Ideas

- "Cite before interpret": vendor `remediation_action`/`remediation_info` text must render verbatim (scanner_verbatim tier) ahead of any AI interpretation.
- Fail-closed everywhere: no vendor text → refuse; dangerous pattern detected → refuse the whole thing; both audited.
- Remediation guidance and Phase 24's posture explanation are two distinct, coexisting affordances — never merged.
</specifics>

<deferred>
## Deferred Ideas

- **Full AI ticket auto-drafting** (AI-authored title/remediation/asset-context, Jira/Asana field mapping, richer draft surface) → **Phase 27 (AID-01)**. Phase 25 pre-fills the description field only.
- **Prioritization narrative** ("what to fix first and why") → Phase 26 (AIP).
- **AI usage/cost dashboard, eval harness, red-team CI** → Phase 28.
- Non-English remediation guidance → out of milestone scope (Phase 24 D-28 English-only carried forward).

None of the above are built in Phase 25.
</deferred>

---

*Phase: 25-asset-aware-remediation-guidance*
*Context gathered: 2026-07-30*
