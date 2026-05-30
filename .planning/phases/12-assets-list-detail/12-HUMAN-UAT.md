---
status: partial
phase: 12-assets-list-detail
source: [12-VERIFICATION.md]
started: 2026-05-30T14:45:00Z
updated: 2026-05-30T14:45:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Responsive two-column layout + sticky rail + chip URL sync on /assets
expected: Chip clicks update URL params, page survives reload, sticky rail stays in viewport as main column scrolls. Two-column at >=900px viewport, single-column below.
result: [pending]

### 2. DrillPanel on /assets/[id] for in-context CVE drill
expected: Clicking a vuln row mounts DrillPanel with cveId from URL; Esc/X close it and remove ?cve+open=drill from the URL.
result: [pending]

### 3. OwnerCard Reassign optimistic flow
expected: Combobox closes immediately on Enter, owner name flips to new email, success toast "Owner reassigned to X" appears, no jank on resync.
result: [pending]

### 4. Reassign malformed-input UX (BL-01 / WR-02 followup)
expected: Either combobox rejects the free-text commit, or backend 422 surfaces as an inline alert. Current state may have known gap pending /gsd-code-review-fix 12.
result: [pending]

### 5. Cross-tenant reassign returns 404 (T-12-20)
expected: POST /api/v1/assets/{other-tenant-id}/owner returns 404 (not 403). Requires staging DB to verify cross-tenant in real Postgres.
result: [pending]

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps
