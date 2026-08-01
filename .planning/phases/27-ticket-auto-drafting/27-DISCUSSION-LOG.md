# Phase 27: Ticket Auto-Drafting — Discussion Log

**Date:** 2026-08-01
**Mode:** discuss (default)

Human-reference record. Not consumed by downstream agents (they read 27-CONTEXT.md).

## Areas discussed (all 4 presented gray areas)

### 1. Draft source
Options: (A) compose from cached AI outputs + deterministic title [recommended]; (B) compose + tiny title-only AI call; (C) one new dedicated ticket-draft AI call.
**Selected: A** — client-side compose from cached explain/remediation/asset/prioritization; title derived deterministically; no new AI call / no new backend risk surface. → D-01/D-06.

### 2. Trigger + freshness
Options: (A) auto-populate on open from cache + "Draft with AI" gap-fill [recommended]; (B) explicit "Draft with AI" button; (C) auto-populate AND generate missing on open.
**Selected: A** — free auto-fill from cache; on-demand gap-fill (Analyst+); respects D-09 budget discipline. → D-02.

### 3. Field mapping + editability
Options: (A) editable title field + one composed editable description body [recommended]; (B) four separate editable fields.
**Selected: A** — `title` request override (mirrors Phase 25 `description`) + composed description textarea; maps to Jira/Asana summary+description; whole body editable (SC2). → D-03/D-05.

### 4. Graceful degradation + never-auto-submit
Options: (A) pre-fill what exists, never block, human-click-to-create [recommended]; (B) require complete draft before enabling Create.
**Selected: A** — never blocked by missing AI; no-key → existing manual flow; nothing auto-submits (SC3); AI is a convenience layer. → D-04.

## Carried forward (not re-asked)
D-17 RBAC, D-23 no-key, D-09 auto-render-if-cached-else-button, D-15 owner-PII exclusion, D-28 English-only; Phase 25 `TicketCreateRequest.description` + `create_tickets()` WYSIWYG + desktop/mobile dialog threading.

## Deferred
Dedicated ticket-draft AI call / AI title → OUT; auto-generate missing outputs on open → OUT (use gap-fill); evals/cost/observability → Phase 28; Ticket DB model change / draft-persistence table → OUT; non-English → out of scope.

## Claude's discretion
Deterministic title format; composed-body section labels/order; whether prioritization is in the body by default; "Draft with AI" affordance placement (UI-SPEC); whether a `title` field is needed vs reusing the summary path (plan-time confirm).
