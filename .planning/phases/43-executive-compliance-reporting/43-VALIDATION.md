---
phase: 43
slug: executive-compliance-reporting
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-08-22
---

# Phase 43 — Validation Strategy

> Per-phase validation contract, reconstructed from the four plan SUMMARY `coverage:` blocks and cross-checked against 43-VERIFICATION.md (74 backend + 46 frontend tests passing, verified 2026-08-24).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend) + vitest (frontend) |
| **Config file** | `backend/pyproject.toml` · `frontend/vitest.config.ts` (`"test": "vitest"`) |
| **Quick run command** | `cd backend && ENCRYPTION_KEY=… JWT_SECRET_KEY=… .venv/bin/pytest tests/test_compliance.py -q` (single touched file) |
| **Full suite command** | backend: `.venv/bin/pytest tests/test_compliance.py tests/test_sla_service.py tests/test_export.py tests/test_reports.py tests/test_mttr.py tests/test_sla_route.py -q` · frontend: `pnpm vitest run compliance/page.test.tsx export-board-report-dialog.test.tsx lens-switcher.test.tsx framework-posture-strip.test.tsx dashboard/page.test.tsx` |
| **Estimated runtime** | backend ~30s · frontend ~15s |

> Backend env note (project memory `getvul-backend-pytest-env`): set `ENCRYPTION_KEY`/`JWT_SECRET_KEY` and run per-file (not the whole `tests/` dir) to avoid false failures; use `.venv/bin/python`/`.venv/bin/pytest` explicitly (bare `python` shim intermittently yields an empty key).

---

## Sampling Rate

- **After every task commit:** Run the single touched test file (quick command)
- **After every plan wave:** Run the full phase suite (both stacks)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 43-01-D1 | 01 | 1 | RPT-03 | — | `get_sla_metrics` exception-exclusion + severity scoping never suppresses lapsed exceptions | unit | `pytest tests/test_sla_service.py -q` | ✅ | ✅ green |
| 43-01-D2 | 01 | 1 | RPT-03 | — | Catalog evaluator short-circuits `None → not_measured` before any threshold compare (no fabricated pass/fail) | unit | `pytest tests/test_compliance.py -q` | ✅ | ✅ green |
| 43-01-D3 | 01 | 1 | RPT-03 | T-tenant-isolation | `/compliance/overview` require_viewer-gated, tenant-scoped, cross-tenant isolation proven, each metric computed once | unit + integration | `pytest tests/test_compliance.py -q` | ✅ | ✅ green |
| 43-01-D4 | 01 | 1 | RPT-03 | — | `/dashboard/compliance` renders loading / two-branch-empty / error / populated states | automated_ui | `vitest run compliance/page.test.tsx` | ✅ | ✅ green |
| 43-01-D5 | 01 | 1 | RPT-03 | — | Live-browser visual/contrast/WCAG-AA of compliance page | manual | — | n/a | ⬜ manual-only |
| 43-02-D1 | 02 | 2 | RPT-01 | — | 3 no-pyplot matplotlib chart helpers produce PIL-decodable PNGs; risk-trend degrades to neutral note under 2 points | unit | `pytest tests/test_export.py -q` | ✅ | ✅ green |
| 43-02-D2 | 02 | 2 | RPT-01 | — | `get_mttr_by_tier(start=,end=)` window filter; default call byte-identical | unit | `pytest tests/test_mttr.py -q` | ✅ | ✅ green |
| 43-02-D3 | 02 | 2 | RPT-01 | — | 3 PDF sections in UI-SPEC order, `exclude_exceptions=True`, zero-data → "Not yet measured" (never fabricated 0/100%), backward-compatible section shape | unit | `pytest tests/test_export.py -q` | ✅ | ✅ green |
| 43-02-D4 | 02 | 2 | RPT-01 | T-dos-custom-range | `export.summary` route period/from/to validation (both-or-neither, to≥from, span cap `MAX_ANALYTICS_WINDOW_DAYS`), audit payload records resolved period | integration | `pytest tests/test_export.py -q` | ✅ | ✅ green |
| 43-02-D5 | 02 | 2 | RPT-01 | — | `reports.py` default-sections lockstep (append-only), explicit sections preserved, `run_due_reports` end-to-end SMTP pickup | integration | `pytest tests/test_reports.py -q` | ✅ | ✅ green |
| 43-02-D6 | 02 | 2 | RPT-01 | — | Board-deck visual/print quality of the 3 chart images | manual | — | n/a | ⬜ manual-only |
| 43-03-D1 | 03 | 3 | RPT-01 | — | Export dialog period presets (default "Last quarter") + custom range (To≥From blocks submit) + E4 disabled generating-spinner | unit | `vitest run export-board-report-dialog.test.tsx` | ✅ | ✅ green |
| 43-03-D2 | 03 | 3 | RPT-01 | — | Scheduling disclosure inline (single dialog), seeds CHECKED from existing board `ScheduledReport` (content-based detect), POSTs 9-section payload | unit + integration | `vitest run export-board-report-dialog.test.tsx` | ✅ | ✅ green |
| 43-03-D3 | 03 | 3 | RPT-01 | — | E7 destructive stop-confirm (Cancel / Stop sending → `DELETE /reports/{id}`); Cancel re-checks toggle, issues no request | unit + integration | `vitest run export-board-report-dialog.test.tsx` | ✅ | ✅ green |
| 43-03-D4 | 03 | 3 | RPT-01 | — | Error banner + "retry with charts off" re-submits original 6 non-chart sections, zero backend change | unit + integration | `vitest run export-board-report-dialog.test.tsx` | ✅ | ✅ green |
| 43-03-D5 | 03 | 3 | RPT-01 | — | Board-ready visual quality of generated PDF (human-verify checkpoint) | manual | — | n/a | ✅ ran + approved (blocking checkpoint) |
| 43-03-D6 | 03 | 3 | RPT-01 | — | PDF footer loop no longer spawns spurious blank trailing page (auto_page_break disabled before loop) | unit | `pytest tests/test_export.py -q` | ✅ | ✅ green |
| 43-03-D7 | 03 | 3 | RPT-01 | — | Zero-remediation tenant renders honest "No remediation actions recorded yet" (not "Top 0 Remediations") | unit | `pytest tests/test_export.py -q` | ✅ | ✅ green |
| 43-04-D1 | 04 | 4 | RPT-02 | — | `useLens()` `?lens=` URL param (source of truth) + localStorage fallback, default `analyst` | unit | `vitest run dashboard/page.test.tsx` | ✅ | ✅ green |
| 43-04-D2 | 04 | 4 | RPT-02 | T-43-13 | `LensSwitcher` 4-segment role=group, aria-pressed, single row, never gated on `User.role` | unit | `vitest run lens-switcher.test.tsx` | ✅ | ✅ green |
| 43-04-D3 | 04 | 4 | RPT-02 | — | Analyst/IT-ops render pre-existing dashboard byte-for-byte; onboarding early-return stays outermost check | unit | `vitest run dashboard/page.test.tsx` | ✅ | ✅ green |
| 43-04-D4 | 04 | 4 | RPT-02 | — | Leadership lens items 1-5 (Export CTA / trend / MTTR tile / SLA tile / posture strip), zero triage widgets; compliance lens items 1-4 | unit | `vitest run dashboard/page.test.tsx` | ✅ | ✅ green |
| 43-04-D5 | 04 | 4 | RPT-02 | — | SLA tile exception-consistent: `/vulnerabilities/sla/metrics` additive `exclude_exceptions` (default false, byte-compat), hook always requests true | unit | `pytest tests/test_sla_route.py -q` | ✅ | ✅ green |
| 43-04-D6 | 04 | 4 | RPT-02 | — | Every zero-denominator tile renders "Not yet measured", posture pills never fabricate pass/fail for all-not-measured framework | unit | `vitest run framework-posture-strip.test.tsx` | ✅ | ✅ green |
| 43-04-D7 | 04 | 4 | RPT-02 | — | Live-browser visual + interaction of all 4 lenses (deep-link, reload-persistence, no-data honesty) — human-verify checkpoint | manual | — | n/a | ✅ ran + approved (blocking checkpoint) |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. No Wave-0 test stubs were needed — pytest and vitest were already in place; all 11 phase-43 test files (6 backend, 5 frontend) were authored and passing during execution.

> Note (surfaced during execution, already resolved): Plan 02 discovered `generate_executive_summary_pdf` had *never* been exercised by an automated test before this phase (two latent crashes — an em-dash encoding bug and a `/app/reports` archive-path assumption — were found and fixed the moment the first PDF test ran). The function now has direct test coverage.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions | State |
|----------|-------------|------------|-------------------|-------|
| Live-browser visual/contrast/WCAG-AA of `/dashboard/compliance` (D5) | RPT-03 | Visual contrast + actual browser rendering can't be asserted in jsdom | Prod build + Playwright/axe sweep against a seeded tenant; inspect control-card states in both themes | ⬜ not run — project-wide accepted gap (see memory `getvul-axe-sweep-not-run-during-exec`) |
| Board-deck visual/print quality of the 3 new PDF chart images (D6) | RPT-01 | Board-deck aesthetic judgment (legibility, color fidelity, pagination under large datasets) is inherently human | Generate a board PDF for a data-rich tenant, review chart legibility/branding/multi-page pagination | ⬜ not run as an independent pass — executor self-inspected 2 sample PDFs via QuickLook; multi-page-under-load not exercised |
| Board-ready visual quality of generated export PDF (43-03 D5) | RPT-01 | CISO-comfort / board-ready judgment is inherently human | Open a generated PDF; confirm section order, real charts vs honest zero-data fallbacks, branding, no dark-theme colors | ✅ ran + approved — blocking `checkpoint:human-verify`, user opened the real PDF and approved |
| Live-browser visual + interaction of all 4 dashboard lenses (43-04 D7) | RPT-02 | Switcher chrome, deep-link, reload-persistence, no-data honesty judged in a real browser | Open `/dashboard`, switch/deep-link each lens, reload to confirm persistence, verify no-data tiles on a real tenant | ✅ ran + approved — blocking `checkpoint:human-verify` against the running local dev stack |

*Every RPT requirement (RPT-01/02/03) has full automated coverage of its functional behavior; the manual-only rows above are supplementary visual/aesthetic confirmations, not the sole verification of any requirement. Two of the four already ran as blocking human-verify checkpoints during execution.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (none — existing infra sufficient)
- [x] No watch-mode flags (`vitest run`, not `vitest`)
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-08-24

---

## Validation Audit 2026-08-24

| Metric | Count |
|--------|-------|
| Gaps found | 0 (automated) |
| Resolved | 0 |
| Escalated | 0 |
| Manual-only recorded | 4 (2 already ran as approved blocking checkpoints) |

Reconstructed the per-task verification map from the four plan SUMMARY `coverage:` blocks (all `status: pass`) and cross-checked against 43-VERIFICATION.md (`status: passed`, 74 backend + 46 frontend tests green, verified same day). No automated MISSING/PARTIAL gaps; the nyquist auditor was not spawned. `status` flipped `draft → validated`, `nyquist_compliant` flipped `false → true`, `wave_0_complete` flipped `false → true` (the file was previously the unfilled plan-phase template stub).
