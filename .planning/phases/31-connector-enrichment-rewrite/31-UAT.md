---
status: partial
phase: 31-connector-enrichment-rewrite
source: [31-VERIFICATION.md]
started: 2026-08-05T12:25:12Z
updated: 2026-08-05T13:05:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Confirm unverified vendor field-name assumptions against live scanner accounts
expected: Each connector's native_priority_score/native_priority_rating (and Wiz's 5 source_signals sub-scores) populate with real, non-null values on a live sync against a real vendor tenant, not just soft-null on the synthetic test fixtures. Fields to confirm: CrowdStrike numeric ExPRT companion (`exprt_score`), Nessus VPR field (`vpr_score`/`vpr`), Qualys QDS element name + `show_qds_factors` param, Rapid7 `riskScore` field/location on the AssetVulnerability association, Wiz's 5 GraphQL fields (`epssSeverity`/`epssPercentile`/`epssProbability`/`exploitabilityScore`/`impactScore`).
result: blocked
blocked_by: third-party
reason: "No live CrowdStrike/Nessus/Qualys/Rapid7/Wiz credentials or configured connectors exist in this environment (connector_configs is empty; no vendor keys in .env; no vendor-sourced vulnerability rows). A live vendor sync cannot be performed here. Automated proxy verification is green: the connector parsing logic passes all synthetic-fixture tests (168 tests during phase verification), and every field guess soft-nulls safely if wrong — but confirming the guesses match real vendor payloads is only possible against a live vendor tenant."

## Summary

total: 1
passed: 0
issues: 0
pending: 0
skipped: 0
blocked: 1

## Gaps

[none — the single open item is a third-party prerequisite gate (live vendor accounts), not a code defect]
