# Phase 26: Prioritization Narrative — Discussion Log

**Date:** 2026-07-30
**Mode:** discuss (default)

Human-reference record. Not consumed by downstream agents (they read 26-CONTEXT.md).

## Areas discussed (all 4 presented gray areas)

### 1. Batch generation strategy (AIP-02)
Options: (A) top-N open by deterministic score, nightly, hash-invalidated [recommended]; (B) entire open backlog nightly; (C) post-sync changed-only.
**Selected: A** → D-01/D-05/D-06/D-07.

### 2. Async-batch cache-miss UX
Options: (A) on-demand single-request fallback + 'being prepared' otherwise [recommended]; (B) wait-for-batch only; (C) on-demand primary, batch as warmer.
**Selected: A** → D-02.

### 3. Augment-never-replace surface + enforcement (Pitfall #7 / SC2)
Options: (A) drill-panel section only, no rank field in schema or UI [recommended]; (B) drill + non-sortable list badge; (C) fold into Explain section.
**Selected: A** → D-03/D-08.

### 4. Grounding factors + owner-PII (SC1)
Options: (A) cvss/epss/exploit/KEV/exploit-status + SLA + owner-as-DEPARTMENT [recommended]; (B) omit owner; (C) include owner name/email.
**Selected: A** → D-04.

## Carried forward (not re-asked)
Phase 24 D-06/08 (budget + admin alert), D-15 (owner-PII exclusion), D-17 (RBAC), D-18/20 (cache + prompt-version hash), D-24 (grounded-false), D-25 (busy), D-27 (audit), D-28 (English-only); Phase 25 grounding/schema/prompt-builder/new-drill-section pattern.

## Deferred
Ticket auto-drafting → Phase 27; cost dashboard + evals + circuit breaker → Phase 28; independently-sortable AI rank → never (violates SC2/Pitfall #7); non-English → out of scope.

## Claude's discretion
Top-N value + nightly schedule time; batch retrieval mechanism (poll vs webhook); exact factor-hash fields; drill placement (UI-SPEC); shared-vs-variant prompt for on-demand vs batch.
