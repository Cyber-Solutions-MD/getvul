---
status: partial
phase: 14-remaining-screens
source: [14-VERIFICATION.md]
started: 2026-06-03T00:00:00Z
updated: 2026-06-03T00:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Connector gradient marks — visual review
expected: Open `/dashboard/connectors` with connectors configured; all 14 provider gradient marks are visually distinct and brand-approximate (crowdstrike=red, nessus=green, defender=blue, rapid7=orange, etc.). Automated checks confirm all 12 tokens exist and ConnectorMark uses literal lookup, but gradient color fidelity requires a real browser render.
result: [pending]

### 2. Sentinel passthrough — live backend round-trip
expected: Edit an existing connector with stored credentials, leave secrets untouched, save. PATCH body has no `credentials` key (visible in DevTools Network) and the connector continues to sync successfully. Unit test verifies the PATCH omits credentials, but backend secret retention requires a live backend.
result: [pending]

### 3. Settings mobile master-detail drill at <900px
expected: Open `/dashboard/settings` at a mobile viewport, tap a category; pane slides in with a back affordance, stacked layout, back button returns to the category list, no horizontal scroll. Responsive classes are coded but interactive behavior requires a real viewport.
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
