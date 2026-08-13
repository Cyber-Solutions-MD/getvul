---
status: complete
phase: 31-connector-enrichment-rewrite
source: [31-VERIFICATION.md]
started: 2026-08-05T12:25:12Z
updated: 2026-08-10T00:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Confirm unverified vendor field-name assumptions against live scanner accounts
expected: Each connector's native_priority_score/native_priority_rating (and Wiz's 5 source_signals sub-scores) populate with real, non-null values on a live sync against a real vendor tenant. Fields: CrowdStrike ExPRT companion (`exprt_score`), Nessus VPR (`vpr_score`/`vpr`), Qualys QDS element + `show_qds_factors`, Rapid7 `riskScore`, Wiz's 5 GraphQL fields.
result: skipped
reason: "Waived on-trust at v4.0 closeout (2026-08-10) — no live CrowdStrike/Nessus/Qualys/Rapid7/Wiz credentials or configured connectors exist in this environment, so a live sync cannot be performed. Accepted as debt, matching the v3.0 Phases 24–27 on-trust-waiver precedent. Code is 5/5 auto-verified (168 tests during phase verification) and every field guess soft-nulls safely if wrong (never crashes ingestion). Close by re-running a live sync once real scanner credentials exist."

## Summary

total: 1
passed: 0
issues: 0
pending: 0
skipped: 1
blocked: 0

## Gaps

[none — the single item is accepted live-vendor-verification debt, not a code defect]
