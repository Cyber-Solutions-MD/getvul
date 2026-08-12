---
phase: 35
slug: source-aware-filtering-provenance-badges
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-12
---

# Phase 35 — Validation Strategy

> Final v4.0 phase. Planner populates the per-task map. Every SRC-01..08 → ≥1 automated test.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (backend) + vitest (frontend) |
| **Config file** | backend/pyproject.toml · frontend/vitest.config.ts |
| **Quick run (backend)** | `cd backend && ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") JWT_SECRET_KEY=test-secret .venv/bin/python -m pytest tests/test_source_filtering.py -x` |
| **Quick run (frontend)** | `cd frontend && npx vitest run src/components/**/source-badge-group.test.tsx` |
| **Full suite** | per-file across touched source-filter/provenance/CSPM/ticket test files |
| **Estimated runtime** | ~5–20s per file |

Note: real Fernet ENCRYPTION_KEY + JWT_SECRET_KEY; run per-file (MEMORY getvul-backend-pytest-env). Frontend WCAG AA unproven without the Playwright axe sweep (MEMORY getvul-axe-sweep-not-run-during-exec) — reason about token contrast manually.

---

## Sampling Rate

- **After every task commit:** run the touched test file
- **After every wave:** run all Phase 35 test files (per-file); frontend `npm test` at wave gate
- **Before `/gsd-verify-work`:** full Phase 35 suite green + the SRC-08 query-count assertion green
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

> Planner fills — every SRC-01..08 → ≥1 automated test. MANDATORY: OR-default vs AND-toggle correctness (vuln+asset), the assets multi-select OR-not-AND bug regression, CSPM multi-tool AND grouping (no silent OR), transitive ticket provenance rule, and the SRC-08 query-count assertion (no N+1).

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| (planner fills) | | | SRC-01..08 | | | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_source_filtering.py` — vuln+asset OR-default/AND-toggle via `&&`/`@>`; the assets multi-select-is-OR-not-AND regression (the found bug); scanner-vs-enrichment partition
- [ ] `backend/tests/test_cspm_corroboration.py` — CSPM multi-tool AND via GROUP BY(tenant_id,rule_id,resource_id), no silent OR
- [ ] `backend/tests/test_source_provenance_batched.py` — transitive ticket provenance rule + the query-count-assertion harness (before_cursor_execute counter) proving no N+1
- [ ] frontend `source-badge-group.test.tsx` — single-source (no overclaim) vs multi-source-corroborated rendering; source list sourced from VulnSource enum (no fake TENABLE/AWS_INSPECTOR/MOCK)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SourceBadgeGroup visual across the 4 surfaces + OR/AND chip toggle | SRC-01..04 | Visual on live stack | Confirm single vs multi-source rendering never implies "confirmed"; OR/AND toggle behaves; empty/loading/error states present |

---

## Validation Sign-Off

- [ ] Every SRC-01..08 maps to ≥1 automated test
- [ ] OR-default/AND-toggle proven for vuln + asset (incl. the assets OR-not-AND bug regression)
- [ ] CSPM multi-tool AND grouping proven (no silent OR)
- [ ] transitive ticket provenance rule tested
- [ ] SRC-08 query-count assertion proves no N+1
- [ ] No watch-mode flags
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
