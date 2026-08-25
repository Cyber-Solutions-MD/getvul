---
phase: 39-exception-risk-acceptance-workflow
plan: 08
subsystem: verification
tags: [human-verify, checkpoint, uat, exceptions, risk-acceptance]

# Dependency graph
requires:
  - phase: 39-exception-risk-acceptance-workflow
    provides: the full integrated exception workflow (39-01..39-07) — backend module, consumer sweep, SLA subtraction, dashboards/exports, frontend grant + list
provides:
  - "Human sign-off closing EXC-01..04 end-to-end against the running dev stack"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns: []
---

## What this plan did

Verification-only closing checkpoint (`checkpoint:human-verify`, blocking gate). No code
changed (`files_modified: []`). A human ran the integrated exception workflow against the
running dev stack and confirmed the visible/functional behaviour that automated tests cannot
fully assert (visual state, dashboard exclusion, the grant→resurface UX).

## Human verification result

**Status: APPROVED** by the user on 2026-08-19.

The user confirmed the full loop against the running dev stack per the plan's 8-step protocol:

1. Grant from a finding's drill panel ("Accept risk") — dialog opens with correct type/scope,
   mono CVE/asset header, ~90d pre-filled expiry + helper copy, Grant disabled until Approver +
   Justification supplied.
2. On grant, the finding disappears from the vuln list and the asset badge counts + `/dashboard`
   tiles drop by one (dashboard exclusion).
3. `/dashboard/exceptions` shows the row with Accept-risk pill, mono CVE/target, approver
   avatar+name, "Nd ago" granted, green/amber Expires sla-pill, sorted soonest-expiring first.
4. Row inline accordion expands (justification + who/when); Revoke → ConfirmModal → confirm.
5. On revoke the finding immediately reappears and dashboard counts restore, without an instant
   SLA breach (D-16 subtraction holds).
6. A forward-looking ASSET_GROUP-scoped grant for a CVE with zero current matches is accepted
   (D-11) and audited.
7. Exceptions list state branches (loading skeleton, never-granted empty, filtered-to-zero
   empty, error banner) render with UI-SPEC copy.
8. A past/over-cap (2099) expiry is rejected with the field-level D-14 copy.

No defects were reported. EXC-01..04 are confirmed closed end-to-end.

## Requirements

This is the phase's designated last-declaring plan for EXC-01, EXC-02, EXC-03, EXC-04. With
the human sign-off recorded, these requirements are satisfied and are marked in REQUIREMENTS.md
at phase completion.

## Self-Check: PASSED

- [x] Human verification obtained (user approved)
- [x] All 8 acceptance steps confirmed
- [x] No defects requiring a --gaps replan
- [x] SUMMARY.md created
