---
status: testing
phase: 31-connector-enrichment-rewrite
source: [31-VERIFICATION.md]
started: 2026-08-05T12:25:12Z
updated: 2026-08-05T12:25:12Z
---

## Current Test

number: 1
name: Confirm unverified vendor field-name assumptions against live scanner accounts
expected: |
  Each connector's native_priority_score / native_priority_rating (and Wiz's 5
  source_signals sub-scores) populate with real, non-null values on a live sync
  against a real vendor tenant — not just soft-null on the synthetic test fixtures.
awaiting: user response

## Tests

### 1. Confirm unverified vendor field-name assumptions against live scanner accounts
expected: Each connector's native_priority_score/native_priority_rating (and Wiz's 5 source_signals sub-scores) populate with real, non-null values on a live sync against a real vendor tenant, not just soft-null on the synthetic test fixtures. Fields to confirm: CrowdStrike numeric ExPRT companion (`exprt_score`), Nessus VPR field (`vpr_score`/`vpr`), Qualys QDS element name + `show_qds_factors` param, Rapid7 `riskScore` field/location on the AssetVulnerability association, Wiz's 5 GraphQL fields (`epssSeverity`/`epssPercentile`/`epssProbability`/`exploitabilityScore`/`impactScore`).
result: [pending]

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
