---
phase: 24-ai-foundation-explain-this-vuln
plan: 06
subsystem: ai
tags: [checkpoint, human-verify, decision, sse, remediation, grounding, tracer-gate]

# Dependency graph
requires:
  - phase: 24-05
    provides: "The complete per-vuln tracer (ANTHROPIC connector + wizard, schema/prompt/audit contracts, BYOK key + tenant cache + budget guard, buffer-validate-replay SSE engine + endpoint, drill-panel AI Explanation section with two-tier citations) — proven in isolation by automated tests"
provides:
  - "TRACER-gate sign-off (live end-to-end verification EXPLICITLY WAIVED by the user — see Waiver below)"
  - "Recorded one-way-door decision D-16: per-remediation grounding shape = Option A (Cross-asset CVE grouping) — the contract Plan 08 implements and Phases 25-28 build on"
affects: [24-08, 25, 26, 27, 28]

# Tech tracking
tech-stack:
  added: []
  patterns: []

key-files:
  created:
    - ".planning/phases/24-ai-foundation-explain-this-vuln/24-06-SUMMARY.md"
  modified: []

key-decisions:
  - "D-16 per-remediation grounding shape = Option A (Cross-asset CVE grouping). Rationale: faithful to D-16's literal 'across the affected assets' framing and aligned with GetVul's core cross-scanner/cross-asset correlation value proposition; establishes a clean tenant-scoped aggregate contract for Phase 25 (remediation guidance). Accepted cost: Plan 08 must build a NEW tenant-scoped query grouping a tenant's affected assets by CVE/fix (no such cross-asset-by-CVE query exists today — the existing RemediationTicket/Ticket concept is per-asset with a single vulnerability_id FK) plus a new grounding-faithfulness surface."
  - "Live end-to-end tracer verification (Task 1, 11-step Docker/nginx flow) was EXPLICITLY WAIVED by the user (chose 'Skip live verify, proceed on trust'). Automated unit/route tests for all five prior plans pass in isolation; the manual-only checks that remain UNPROVEN are called out under Waiver / Unproven below."

patterns-established: []

requirements-completed: []  # This is a verify+decide gate; it implements no requirements itself. AI-01..AI-06 traceability is closed by the plans that build them (01-05, 07-09) and the phase verifier. Live verification of AI-03 was waived (see Waiver), so this plan makes NO requirement-verified claim.

coverage:
  - id: D1
    description: "TRACER live end-to-end sign-off — per-vuln Explain flow verified through the real Docker/nginx stack (streaming incremental, cited, cached, audited, RBAC-gated, inert-when-keyless, reduced-motion + contrast)"
    verification:
      - kind: manual_procedural
        ref: "24-06-PLAN.md Task 1 (11-step live checklist)"
        status: unknown
    human_judgment: true
    rationale: "Requires a live Docker/nginx stack + a dev Anthropic key + browser and curl -N inspection; cannot be automated. User explicitly waived live verification ('proceed on trust'), so status is unknown, not pass."
  - id: D2
    description: "Recorded D-16 per-remediation grounding decision consumed by Plan 08 (Option A — Cross-asset CVE grouping)"
    verification:
      - kind: manual_procedural
        ref: "AskUserQuestion decision — recorded in key-decisions above"
        status: pass
    human_judgment: true
    rationale: "A one-way-door design decision; correctness is a human judgment call, now made and recorded."
---

## Accomplishments

- **TRACER gate reached and cleared to proceed.** Plans 01–05 built the entire per-vuln "Explain this vuln" slice and each passed its own automated test suite in isolation. This gate is the human checkpoint between the proven per-vuln tracer and the expansion plans (07 feedback, 08–09 host/remediation widening).
- **Recorded the D-16 one-way-door decision → Option A (Cross-asset CVE grouping).** This is the grounding-record contract the per-remediation "Explain this fix" view uses, which Plan 08 implements and Phases 25–28 build on. RESEARCH had flagged this genuinely unresolved (Open Question #2 / Assumption A1); it is now settled.

## Decision detail — D-16 per-remediation grounding shape

**Chosen: Option A — Cross-asset CVE grouping.**

- **What it means:** the per-remediation grounding record aggregates a tenant's affected assets *by CVE/fix* — `{ cve, fix, affected_assets[], priority }` across all of a tenant's assets sharing the CVE — faithful to D-16's literal "what applying this one fix accomplishes ACROSS the affected assets + its priority."
- **Why:** aligns with GetVul's core value (the same CVE-on-host correlated across scanners/assets) and gives Phase 25 a clean fleet-wide aggregate contract.
- **Accepted cost (Plan 08 owns this):** there is no existing cross-asset-by-CVE query — the current `RemediationTicket`/`Ticket` concept is per-asset (single `vulnerability_id` FK). Plan 08 must build a NEW tenant-scoped aggregate query + its own grounding-faithfulness surface. (Per-host grounding remains a separate "posture summary" aggregate per D-16 and is NOT part of this decision.)

## Waiver / Unproven (live verification skipped on user instruction)

The user chose **"Skip live verify, proceed on trust."** The following manual-only checks from Task 1 were **NOT run** and remain **unproven** going into expansion:

- **AI-03 nginx anti-buffering** (`curl -N` progressive-frame assertion) — the one check the automated suite cannot cover through the real proxy. nginx config was written in Plan 01 but its no-buffering behavior is not live-verified.
- Live end-to-end wizard→save→explain→cache→audit-row flow through Docker.
- D-25 persistent-429 amber "AI busy" card in the live UI.
- RBAC live states (Analyst/Viewer/keyless) and the audit-log-pane `ai.explain.vuln` row.
- Reduced-motion instant-render and violet-on-soft citation contrast in a real browser (dark + light).

Recommendation: run `/gsd-verify-work 24` against a live stack with a dev Anthropic key before shipping the milestone, to close AI-03 and the D-25/RBAC/a11y manual items.

## Self-Check: PASSED

- Checkpoint gate resolved via user decisions (D-16 = Option A; live verify = waived-on-trust).
- No code artifacts expected or produced (files_modified: []).
- Both blocking checkpoint tasks have a recorded disposition.
