---
status: testing
phase: 41-coverage-blind-spot-detection
source: [41-VERIFICATION.md]
started: 2026-08-21T08:42:01Z
updated: 2026-08-21T08:42:01Z
---

## Current Test

number: 1
name: Route-to-owner pre-confirm dialog copy accuracy (SC3 UX judgment)
expected: |
  As an analyst, open /dashboard/coverage for a tenant whose blind-spot asset has a
  resolvable owner (assigned_user matching a real tenant User row, or a Humaans /
  last-login match resolvable via get_directory_user). Click "Route to owner" on that
  row (or from the drill panel) and read the confirm dialog BEFORE confirming.

  Functionally correct behavior (already verified in code + tests): on confirm, the
  server resolves the true owner, emails them directly, writes a coverage.route_to_owner
  audit row, and the success toast reports the true routed_to recipient.

  The judgment call: the pre-confirm dialog ALWAYS shows the D-09 "no owner found" copy
  (every real call site hardcodes ownerResolved={false}, because BlindSpotAssetResponse
  carries no owner-preview signal — a schema change ruled out of this phase's reversibility
  scope). So the dialog may tell you "no owner found" for an asset the backend will in fact
  route to a specific named owner. Decide: ship as-is (accept via override), or require a
  follow-up plan to add an owner-preview field so the dialog can select the correct branch.
awaiting: user response

## Tests

### 1. Route-to-owner pre-confirm dialog copy accuracy (SC3 UX judgment)
expected: Pre-confirm dialog copy matches the actual routing outcome, OR the always-"no owner found" default is accepted as a conservative, disclosed limitation.
result: [pending]

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
