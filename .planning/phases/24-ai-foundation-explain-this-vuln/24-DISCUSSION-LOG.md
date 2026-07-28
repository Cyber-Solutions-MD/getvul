# Phase 24: AI Foundation + "Explain This Vuln" - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-28
**Phase:** 24-ai-foundation-explain-this-vuln
**Areas discussed:** AI config scope, Explain trigger UX, Citation visual language, Feedback + scope edges, Perceived streaming UX, Budget-exceeded notification, Feedback storage/visibility, Model default & scope, Explain affordance scope, Prompt-version convention, Cache TTL, Model dropdown guidance, Aggregate explanation shape, Rate-limit / 429 UX, RBAC gating, Retry visibility, Cache-hash composition, AI audit visibility, Feedback granularity, Explanation language

> Note: the technical HOW was pre-locked by `24-AI-SPEC.md`; discussion focused only on the product/UX/scope surface it left open.

---

## AI config scope

| Question | Options | Selected |
|----------|---------|----------|
| What admin configures | Key only (model fixed) / **Key + model dropdown** / Key + model + effort | Key + model dropdown ✓ |
| Budget cap now? | Defer to Phase 28 / **Simple monthly cap now** | Simple monthly cap now ✓ |
| Where config lives | New 'AI' settings pane / **Connectors screen card** | Connectors screen card ✓ |
| Key validation | **Test before save** / Save, validate lazily | Test before save ✓ |

**Notes:** User went broader than the minimal defaults on three of four. Flagged: model dropdown drops in cleanly (cache key + audit already key on model); monthly cap is a fenced pull-forward of AIE-03 (heavy circuit-breaker + dashboard stays Phase 28); connectors card = new `ConnectorConfig` `connector_type`, wizard step-3 = test-before-save.

---

## Explain trigger UX

| Question | Options | Selected |
|----------|---------|----------|
| Generation on open | On-demand button / Auto-generate on open / **Auto on open, only if cached** | Auto on open, only if cached ✓ |
| Regenerate affordance | **No manual regenerate** / Add regenerate button | No manual regenerate ✓ |
| Placement | **Dedicated panel section** / Inline near header | Dedicated panel section ✓ |

---

## Citation visual language

| Question | Options | Selected |
|----------|---------|----------|
| Two-tier distinction | **Inline per-claim tagging** / Two segmented regions / Footnote-style refs | Inline per-claim tagging ✓ |
| Surface source_field | **On hover / expand** / Always visible label / Tier badge only | On hover / expand ✓ |

**Notes:** Exact pixel styling deferred to UI-SPEC; reuse sunset chip/badge primitives.

---

## Feedback + scope edges

| Question | Options | Selected |
|----------|---------|----------|
| Feedback capture | Lightweight thumbs now / **Thumbs + optional note** / Defer all feedback | Thumbs + optional note ✓ |
| Ticket-quoting | **Strictly Phase 27** / Manual copy now | Strictly Phase 27 ✓ |
| No-key state | **Honest nudge + admin link** / Hide section entirely | Honest nudge + admin link ✓ |
| grounded=false | **Distinct honest 'can't explain' card** / Same as 'AI unavailable' | Distinct honest card ✓ |

---

## Perceived streaming UX

| Question | Options | Selected |
|----------|---------|----------|
| Click → explanation experience | **'Analyzing…' then replay** / Skeleton then instant / Spinner then replay | 'Analyzing…' then replay ✓ |

**Notes:** Buffer-then-validate-then-replay means a wait then a validated token replay; the replay is where AI-03 is satisfied.

---

## Budget-exceeded notification

| Question | Options | Selected |
|----------|---------|----------|
| Admin notification path | **Panel state + NOTIF-01 alert** / Panel state only / NOTIF-01 alert only | Panel state + NOTIF-01 alert ✓ |

---

## Feedback storage/visibility

| Question | Options | Selected |
|----------|---------|----------|
| Storage + visibility | **New table, capture-only** / Extend audit row / New table + admin count | New table, capture-only ✓ |

---

## Model default & scope

| Question | Options | Selected |
|----------|---------|----------|
| Default + scope | **sonnet-5, tenant-wide** / sonnet-5, per-user override | sonnet-5, tenant-wide ✓ |

---

## Explain affordance scope

| Question | Options | Selected |
|----------|---------|----------|
| Which drill views (initial) | Per-vuln CVE-on-host only / Per-vuln + per-host / **All three views** | All three views ✓ |
| Scope confirmation (after flag) | Per-vuln only this phase / All three, expand this phase / **All three, per-vuln first internally** | All three, per-vuln first internally ✓ |

**Notes:** Claude flagged that "all three" widens scope vs. the AI-SPEC's single-record minimum-blast-radius design (per-host is an aggregate needing different grounding). User confirmed all-three but accepted a **sequencing constraint**: per-vuln path built + validated end-to-end first, then host/remediation within the phase.

---

## Aggregate explanation shape

| Question | Options | Selected |
|----------|---------|----------|
| What host/remediation say | **Posture summary** / Thin per-CVE list / Defer shape to planner | Posture summary ✓ |

**Notes:** Each aggregate view gets its own grounding shape + schema variant.

---

## Rate-limit / 429 UX

| Question | Options | Selected |
|----------|---------|----------|
| 429 / concurrency handling | **SDK backoff + busy state + guard** / Busy state only | SDK backoff + busy state + guard ✓ |

---

## RBAC gating

| Question | Options | Selected |
|----------|---------|----------|
| Who can invoke Explain | **Analyst and above** / Anyone with panel access / Admin/Owner only | Analyst and above ✓ |

---

## Retry visibility

| Question | Options | Selected |
|----------|---------|----------|
| Corrective retry visible? | **Invisible** / Subtle indicator | Invisible ✓ |

---

## Cache-hash composition

| Question | Options | Selected |
|----------|---------|----------|
| What the record hash covers | **Grounding fields only** / Whole record | Grounding fields only (Claude default) ✓ |

**Notes:** Decided as a Claude-discretion default (AskUserQuestion was interrupted by a tool error; user said continue). Rationale: makes D-10 "no manual regenerate" correct — unrelated edits don't force re-spend.

---

## AI audit visibility

| Question | Options | Selected |
|----------|---------|----------|
| Surface AI audit this phase? | **Reuse existing AUDIT-01 audit-log-pane** / Rows only, expose in Phase 28 | Reuse existing audit-log-pane (Claude default) ✓ |

**Notes:** Claude-discretion default. Dedicated usage/cost dashboard stays Phase 28.

---

## Feedback granularity

| Question | Options | Selected |
|----------|---------|----------|
| Feedback shape | **Per-user, editable** / One verdict per finding-explanation | Per-user, editable (Claude default) ✓ |

**Notes:** Claude-discretion default.

---

## Explanation language

| Question | Options | Selected |
|----------|---------|----------|
| Language | **English-only this phase** / Follow tenant/user locale | English-only (Claude default) ✓ |

**Notes:** Claude-discretion default; keeps eval golden-set single-language.

---

## Claude's Discretion

- The final four areas (cache-hash composition, AI audit visibility, feedback granularity, explanation language) were locked with Claude-recommended defaults after the AskUserQuestion tool was interrupted and the user said "continue." All four are low-ambiguity with a clear best answer.
- Aggregate schema-variant field lists, panel layout/ordering, citation pixel-styling, exact cache TTL window, and concurrency-cap value left to researcher/planner/UI-SPEC.

## Deferred Ideas

- Full per-tenant cost circuit breaker + admin usage/cost dashboard — Phase 28 (AIE-03/04)
- AI explanation → ticket draft pre-fill — Phase 27
- Golden-set promotion + calibrated LLM-judge dashboards — Phase 28
- Effort-dial exposure / model-choice expansion — Phase 28+
- Explanation localization — out of scope
- Semantic/embedding caching, RAG — milestone out-of-scope
