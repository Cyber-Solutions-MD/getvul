---
phase: 35
slug: source-aware-filtering-provenance-badges
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-12
---

# Phase 35 — Validation Strategy

> Final v4.0 phase. Every SRC-01..08 → ≥1 automated test. Populated by the planner across 5 plans.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (backend) + vitest (frontend) |
| **Config file** | backend/pyproject.toml · frontend/vitest.config.ts |
| **Quick run (backend)** | `cd backend && ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") JWT_SECRET_KEY=test-secret .venv/bin/python -m pytest tests/test_source_filtering.py -x` |
| **Quick run (frontend)** | `cd frontend && npx vitest run src/components/vulnerabilities/source-badge-group.test.tsx` |
| **Full suite** | per-file across every Phase 35 backend test file + `npx vitest run` for each touched frontend test |
| **Estimated runtime** | ~5–20s per file |

Note: real Fernet ENCRYPTION_KEY + JWT_SECRET_KEY; run per-file (MEMORY getvul-backend-pytest-env). Frontend WCAG AA unproven without the Playwright axe sweep (MEMORY getvul-axe-sweep-not-run-during-exec) — reason about token contrast manually.

---

## Sampling Rate

- **After every task commit:** run the touched test file
- **After every wave:** run all Phase 35 test files (per-file); frontend `npx vitest run` per touched test
- **Before `/gsd-verify-work`:** full Phase 35 suite green + all SRC-08 query-count assertions green
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

> Every SRC-01..08 → ≥1 automated test. MANDATORY coverage present: OR-default vs AND-toggle correctness (vuln+asset), the assets multi-select OR-not-AND bug regression, CSPM multi-tool AND grouping (no silent OR), transitive ticket provenance rule, and the SRC-08 query-count assertion (no N+1) via the new before_cursor_execute harness.

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| 01-T1/T2 | 35-01 | 1 | SRC-01 (data), SRC-03 | integration | `pytest tests/test_source_filtering.py::test_or_default_returns_union -x` | ⬜ pending |
| 01-T1/T2 | 35-01 | 1 | SRC-04 | integration | `pytest tests/test_source_filtering.py::test_and_toggle_requires_corroboration -x` | ⬜ pending |
| 01-T1/T2 | 35-01 | 1 | SRC-04 (Pitfall 1) | integration | `pytest tests/test_source_filtering.py::test_and_with_single_source_is_or -x` | ⬜ pending |
| 01-T1/T2 | 35-01 | 1 | SRC-01 (sources field) | integration | `pytest tests/test_source_filtering.py::test_summary_carries_sources -x` | ⬜ pending |
| 01-T1/T2 | 35-01 | 1 | SRC-02 (validation) | integration | `pytest tests/test_source_filtering.py::test_bad_source_mode_422 -x` | ⬜ pending |
| 01-T1/T2 | 35-01 | 1 | SRC-08 (vuln, harness) | query-count | `pytest tests/test_source_filtering.py::test_list_query_count_is_page_size_invariant -x` | ⬜ pending |
| 02-T1 | 35-02 | 2 | SRC-01 (no overclaim) | unit (fe) | `npx vitest run src/components/vulnerabilities/source-badge-group.test.tsx` | ⬜ pending |
| 02-T2 | 35-02 | 2 | SRC-02/03/04 (vuln UI) | unit (fe) | `npx vitest run src/components/vulnerabilities/` | ⬜ pending |
| 03-T1/T2 | 35-03 | 2 | SRC-03 (assets bug regression) | integration | `pytest tests/test_asset_source_filter.py::test_or_default_multi_scanner_returns_union -x` | ⬜ pending |
| 03-T1/T2 | 35-03 | 2 | SRC-04 (assets AND) | integration | `pytest tests/test_asset_source_filter.py::test_and_toggle_requires_all -x` | ⬜ pending |
| 03-T1/T2 | 35-03 | 2 | SRC-06 (partition) | integration | `pytest tests/test_asset_source_filter.py::test_enrichment_does_not_leak_into_scanner_filter -x` | ⬜ pending |
| 03-T1/T2 | 35-03 | 2 | SRC-08 (assets) | query-count | `pytest tests/test_asset_source_filter.py::test_list_assets_query_count_invariant -x` | ⬜ pending |
| 04-T1/T2 | 35-04 | 2 | SRC-05 (CSPM AND grouping) | integration | `pytest tests/test_cspm_corroboration.py::test_cspm_and_requires_same_group -x` | ⬜ pending |
| 04-T1/T2 | 35-04 | 2 | SRC-03/05 (CSPM OR) | integration | `pytest tests/test_cspm_corroboration.py::test_cspm_or_default_unchanged -x` | ⬜ pending |
| 04-T1/T2 | 35-04 | 2 | SRC-08 (CSPM) | query-count | `pytest tests/test_cspm_corroboration.py::test_cspm_query_count_invariant -x` | ⬜ pending |
| 04-T1/T3 | 35-04 | 2 | SRC-07 (transitive) | integration | `pytest tests/test_source_provenance_batched.py::test_ticket_transitive_provenance -x` | ⬜ pending |
| 04-T1/T3 | 35-04 | 2 | SRC-07 (union rule A4) | integration | `pytest tests/test_source_provenance_batched.py::test_ticket_grouped_union -x` | ⬜ pending |
| 04-T1/T3 | 35-04 | 2 | SRC-08 (tickets) | query-count | `pytest tests/test_source_provenance_batched.py::test_list_tickets_query_count_invariant -x` | ⬜ pending |
| 05-T1 | 35-05 | 3 | SRC-01/02/06 (assets UI) | unit (fe) | `npx vitest run src/components/assets/` | ⬜ pending |
| 05-T2 | 35-05 | 3 | SRC-01/02/04 (cspm UI) | unit (fe) | `npx vitest run src/components/cspm/ "src/app/(authed)/dashboard/cspm/"` | ⬜ pending |
| 05-T3 | 35-05 | 3 | SRC-01/02 (tickets UI) | unit (fe) | `npx vitest run src/components/tickets/` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**SRC → test coverage check:** SRC-01 (01,02,05) · SRC-02 (01,02,03,04,05) · SRC-03 (01,03,04) · SRC-04 (01,03) · SRC-05 (04) · SRC-06 (03,05) · SRC-07 (04) · SRC-08 (01,03,04). Every requirement ≥1 automated test.

---

## Wave 0 Requirements

Wave 0 = the RED (failing-test) tasks that MUST exist before implementation. Each backend plan's Task 1 is a
RED task; the shared query-count harness is a Wave-0 artifact created in Plan 01.

- [ ] `backend/tests/query_count.py` — NEW before_cursor_execute statement-counter harness (Plan 01 Task 1); no precedent exists (SRC-08's structural proof mechanism), reused by Plans 03/04
- [ ] `backend/tests/test_source_filtering.py` — vuln OR-default (`&&`) / AND-toggle (`@>`) + sources/sources_count response + vuln query-count (Plan 01 Task 1) — SRC-01/03/04/08
- [ ] `backend/tests/test_asset_source_filter.py` — assets OR-default (the multi-select-is-OR-not-AND bug regression) + AND toggle + scanner-vs-enrichment partition + assets query-count (Plan 03 Task 1) — SRC-02/03/04/06/08
- [ ] `backend/tests/test_cspm_corroboration.py` — CSPM multi-tool AND via GROUP BY(tenant_id,rule_id,resource_id), no silent OR + CSPM query-count (Plan 04 Task 1) — SRC-02/05/08
- [ ] `backend/tests/test_source_provenance_batched.py` — transitive ticket provenance + multi-vuln union rule (A4) + list_tickets query-count (Plan 04 Task 1) — SRC-07/08
- [ ] `frontend/src/components/vulnerabilities/source-badge-group.test.tsx` — single-source (no "confirmed" overclaim) vs multi-source-corroborated rendering; CSS-var-not-hex; no <img>; 6-value VulnSource source list (Plan 02 Task 1) — SRC-01

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SourceBadgeGroup visual across the 4 surfaces + OR/AND chip toggle | SRC-01..04 | Visual on live stack | Confirm single vs multi-source rendering never implies "confirmed"; OR/AND toggle disables below 2 selections; empty/loading/error states present on every surface |
| WCAG AA contrast of the corroboration tint + provider marks | SRC-01 | axe sweep needs prod build+server (MEMORY) | Reason about token contrast manually; run the Playwright axe sweep at phase gate if the harness is available |

---

## Validation Sign-Off

- [ ] Every SRC-01..08 maps to ≥1 automated test (see coverage check above)
- [ ] OR-default/AND-toggle proven for vuln + asset (incl. the assets OR-not-AND bug regression)
- [ ] CSPM multi-tool AND grouping proven (no silent OR)
- [ ] transitive ticket provenance + multi-vuln union rule tested
- [ ] SRC-08 query-count assertion proves no N+1 on all four list endpoints
- [ ] SourceBadgeGroup single-source never renders "confirmed" (structural test)
- [ ] No watch-mode flags
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
