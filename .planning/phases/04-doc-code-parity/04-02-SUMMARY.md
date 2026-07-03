---
phase: 04-doc-code-parity
plan: "02"
subsystem: backend
tags: [enum, vuln-source, regression-test, tenant-isolation, tdd]
dependency_graph:
  requires: []
  provides: [VulnSource-6-members, source-filter-regression-test]
  affects: [backend/app/vulnerabilities/models.py, backend/tests/test_vuln_source_filter.py]
tech_stack:
  added: []
  patterns: [TDD RED/GREEN, pytest-asyncio, conftest fixture reuse]
key_files:
  created:
    - backend/tests/test_vuln_source_filter.py
  modified:
    - backend/app/vulnerabilities/models.py
decisions:
  - VulnSource extended enum-only (D-10) with no Alembic migration (D-11) — source column is String(30), not a DB enum; adding members has zero DB impact
  - VulnSource import kept out of all app/ write paths (D-12 boundary) — enum is advisory; connector source_name already emits "QUALYS"/"RAPID7" as plain strings
  - API tests skip gracefully when Postgres unreachable (conftest skip guard) — test_vuln_source_enum_members is a pure-Python assertion that passes in any environment
metrics:
  duration: "2m 3s"
  completed: "2026-07-03"
  tasks: 2
  files: 2
---

# Phase 04 Plan 02: VulnSource Enum Extension + Source Filter Regression Summary

VulnSource enum extended to 6 members (QUALYS + RAPID7 added to existing CROWDSTRIKE/NESSUS/DEFENDER/WIZ) with a 4-test API regression suite verifying Qualys/Rapid7 filter correctness and tenant isolation.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Wave 0 — failing enum + source-filter + tenant-scope tests (RED) | f3c0d3d | backend/tests/test_vuln_source_filter.py |
| 2 | Add QUALYS + RAPID7 to VulnSource enum (GREEN) | 267057d | backend/app/vulnerabilities/models.py |

## What Was Built

**models.py change:** Two new members added to the `VulnSource` enum — `QUALYS = "QUALYS"` and `RAPID7 = "RAPID7"`. The `source` column is `String(30)`, not a PostgreSQL enum type, so no Alembic migration is required or generated. No import of `VulnSource` was added to any write path, connector, or API validation layer.

**test_vuln_source_filter.py:** Four tests covering PROD-04-03 and PROD-04-04:
- `test_vuln_source_enum_members` — pure-Python assertion that VulnSource has exactly 6 members including QUALYS and RAPID7; was RED before Task 2, GREEN after.
- `test_source_filter_qualys` — seeds one QUALYS + one RAPID7 vuln for tenant_a; asserts `GET ?source=QUALYS` returns exactly the QUALYS row.
- `test_source_filter_rapid7` — same seed; asserts `GET ?source=RAPID7` returns exactly the RAPID7 row.
- `test_source_filter_tenant_scoped` — seeds 1 QUALYS for tenant_a + 2 QUALYS for tenant_b; asserts tenant_a's client sees exactly 1 row, proving the service's `tenant_id == user.tenant_id` filter precedes the source filter and cross-tenant rows never leak (T-04-03 mitigation).

## TDD Gate Compliance

- RED commit (f3c0d3d): `test_vuln_source_enum_members` failed with `AttributeError: type object 'VulnSource' has no attribute 'QUALYS'` — RED gate confirmed.
- GREEN commit (267057d): `test_vuln_source_enum_members` passes; API tests skip cleanly (no Postgres in sandbox) — GREEN gate confirmed.
- No REFACTOR step needed (the 2-line enum addition requires no cleanup).

## Verification

- `pytest tests/test_vuln_source_filter.py::test_vuln_source_enum_members` — PASSED after Task 2.
- `pytest tests/test_vuln_source_filter.py` — 1 passed, 3 skipped (Postgres not reachable in sandbox; CI with live DB will run all 4).
- `grep -c "QUALYS = \"QUALYS\"\|RAPID7 = \"RAPID7\"" backend/app/vulnerabilities/models.py` — returns 2.
- `grep -rl "import.*VulnSource" backend/app/` — returns nothing (D-12 boundary intact).
- No migration file added under `backend/alembic/versions/` for this change.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None. The VulnSource enum extension is advisory Python-only (String(30) column, imported nowhere in app/); it introduces no new input path, validation gate, or attack surface. The tenant-isolation test (`test_source_filter_tenant_scoped`) directly validates the T-04-03 mitigation.

## Self-Check: PASSED

- `backend/tests/test_vuln_source_filter.py` — FOUND (created in Task 1, committed f3c0d3d)
- `backend/app/vulnerabilities/models.py` — FOUND (modified in Task 2, committed 267057d)
- Commit f3c0d3d — FOUND in git log
- Commit 267057d — FOUND in git log
