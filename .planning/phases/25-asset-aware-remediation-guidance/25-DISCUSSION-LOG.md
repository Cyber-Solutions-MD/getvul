# Phase 25: Asset-Aware Remediation Guidance — Discussion Log

**Date:** 2026-07-30
**Mode:** discuss (default)

Human-reference record of the discussion. Not consumed by downstream agents (they read 25-CONTEXT.md).

## Areas selected for discussion
All four presented gray areas: refuse predicate, dangerous-command safety net, UI surface, AIR-02 ticket hand-off.

## Decisions

### 1. Refuse predicate (cite-or-refuse)
- Options: (A) non-generic remediation_action/info present [recommended], (B) any scanner text present + model self-refuses, (C) require remediation_action specifically.
- **Selected: A** — deterministic pre-generation gate on non-generic `remediation_action`/`remediation_info`, belt-and-suspenders with the schema `grounded` flag. → D-01/D-02/D-03.

### 2. Dangerous-command safety net (Pitfall #2)
- Options: (A) refuse whole guidance + typed safety state [recommended], (B) strip offending lines, (C) render all + flag.
- **Selected: A** — a denylist hit refuses the entire guidance, typed safety-refusal state, audited; code gate not prompt wording. → D-04/D-05.

### 3. Where guidance surfaces in the UI
- Options: (A) separate "Remediation guidance" section/action [recommended], (B) extend existing AI Explanation section, (C) supersede Phase-24 posture output.
- **Selected: A** — separate section reusing Phase 24's AI chrome + citation component; coexists with the per-remediation posture output. → D-06/D-07.

### 4. AIR-02 draft-ticket hand-off
- Options: (A) pre-fill existing ticket-create description field [recommended], (B) lightweight copy action, (C) dedicated draft-ticket preview panel now.
- **Selected: A** — pre-fill the existing drill-panel ticket-create description; analyst reviews/edits before creating. Phase 25 = description only; full auto-drafting is Phase 27. → D-08/D-09.

## Carried forward (not re-asked)
Phase 24 D-01/03 (BYOK+model config), D-12 (streaming replay), D-17 (RBAC), D-18/19/20 (cache + prompt-version), D-06 (budget), D-21 (feedback), D-23/24/25 (no-key/grounded-false/429 states), D-27 (audit), D-28 (English-only), D-13/14 (citation tiers), D-15 (asset-fact allowlist / PII exclusion).

## Deferred
Full ticket auto-drafting → Phase 27; prioritization narrative → Phase 26; usage/cost dashboard + evals → Phase 28; non-English → out of scope.

## Claude's discretion
Denylist patterns, refuse-predicate thresholds, OS/package asset-fact field list (within existing allowlist), exact drill-panel placement (UI-SPEC).
