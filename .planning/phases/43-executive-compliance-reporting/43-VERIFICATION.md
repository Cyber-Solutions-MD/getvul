---
phase: 43-executive-compliance-reporting
verified: 2026-08-24T15:20:00Z
status: passed
score: 17/17 must-haves verified
overrides_applied: 0
---

# Phase 43: Executive & Compliance Reporting Verification Report

**Phase Goal:** Executive & Compliance Reporting — Exportable exec/board PDF report (RPT-01), role-scoped/job-function dashboards (RPT-02), and a framework-control compliance view mapping findings to SOC 2 / ISO 27001 / PCI DSS / NIST CSF controls (RPT-03).
**Verified:** 2026-08-24T15:20:00Z
**Status:** passed
**Re-verification:** No — initial verification (no prior 43-VERIFICATION.md existed)

## Context for this verification

This phase ran sequentially on the main tree (worktrees degraded due to HEAD/origin divergence). A code-review pass (`43-REVIEW.md`) found 1 critical + 2 warning findings, all of which were fixed in follow-up commits BEFORE this verification ran:

- **CR-01** (blocker): board PDF's `sections` filter was only honored for the 3 new RPT-01 chart sections; 5 of 6 legacy sections rendered unconditionally regardless of the caller's request. Fixed in `5eb137c` — all 6 legacy blocks now gated by `if "X" in sec:`, with a regression test (`test_pdf_legacy_sections_are_gated_by_requested_sections_list`) that asserts absence of ungated sections' header text.
- **WR-01** (warning): leadership-lens tiles (MTTR/SLA/posture strip) collapsed genuine backend errors into the same rendering as an honestly-empty tenant, with no retry. Fixed in `6624801` — `LeadershipSlaTile`/`LeadershipPostureStrip` now render `PartialFailureBanner` with `onRetry` on any error; `LeadershipMttrTile` still treats a 403 (admin-gated route, pre-existing RBAC floor) as "not yet measured" but surfaces any other error via the same banner.
- **WR-02** (warning): `compliance/__init__.py` was an empty file with no docstring. Fixed in `019655f`.

All three fixes were independently re-verified in this pass (code read directly, not trusted from REVIEW.md's own claim) — see Anti-Patterns / Key Link sections below.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | RPT-03: CISO can open `/dashboard/compliance` and see per-framework control cards (SOC 2/ISO/PCI/NIST) with deterministic pass/partial/fail/not-measured status | ✓ VERIFIED | `backend/app/compliance/catalog.py` — 10-control `CATALOG` across all 4 frameworks; `evaluate_catalog()` short-circuits `None → not_measured` before any threshold compare (lines 166-191). `frontend/src/app/(authed)/dashboard/compliance/page.tsx` (274 lines) renders framework-grouped control-card grid. `page.test.tsx` (7 tests) pass. |
| 2 | `GET /api/v1/compliance/overview` returns 200, tenant-scoped, `require_viewer`-gated | ✓ VERIFIED | `backend/app/compliance/router.py` registered at `/api/v1/compliance` in `main.py:327`. `test_compliance.py` includes cross-tenant isolation + 200-for-viewer tests; all pass (11 tests). |
| 3 | A control with zero underlying data renders "Not yet measured", never a fabricated pass/fail | ✓ VERIFIED | `catalog.py` lines 142/155/179-191: `None → "not_measured"` guard before threshold logic. `control-card.tsx` line 60: `if (control.status === 'not_measured' \|\| control.value === null)` renders the dashed/faint treatment. |
| 4 | Each of ~5 underlying metrics computed exactly once per request; catalog is a pure function issuing zero queries | ✓ VERIFIED | `test_compliance.py::test_compliance_overview_computes_each_metric_exactly_once` passes; `service.py` makes exactly 4 async calls (coverage, SLA, aging, MTTR-by-tier) regardless of catalog size. |
| 5 | Control status is program-level, never per-CVE tagged | ✓ VERIFIED | `catalog.py`/`service.py` operate only on aggregate metric dicts (percentages, booleans, tier averages) — no per-finding/per-CVE loop exists in either file. |
| 6 | Compliance page loading/two-branch-empty/error/populated states (E2/E3/E5) | ✓ VERIFIED | `page.tsx` implements `ErrorBoundary>Suspense>Inner`, skeleton loading, two-branch empty (no-scanner vs no-SLA-policy via `useCoverageSummary()`), amber error banner with partially-resolved cards still rendering, framework-grouped grid. All 7 `page.test.tsx` assertions pass, covering branch order + both empty-branch root causes. |
| 7 | RPT-01: exec/board PDF exports PERIOD-SCOPED risk-trend + MTTR-by-tier, fixed-trailing-90-day SLA section, appended after summary-stats/before top-hosts | ✓ VERIFIED | `backend/app/export.py` lines ~985-1090: sections drawn in exact order risk_trend → mttr_by_tier → sla_compliance, after `risk` block, before `top_hosts`. SLA section includes literal caption "Trailing 90-day metric, independent of the selected period" (line ~1090). `get_mttr_by_tier(start=, end=)` period-filters (verified in `vulnerabilities/service.py:507-513`). |
| 8 | 3 new PDF sections render as real matplotlib PNG chart images (Figure+FigureCanvasAgg, no pyplot) | ✓ VERIFIED | `grep -rn "import matplotlib.pyplot" backend/app` → 0 matches. `test_export.py` chart-decodability tests pass (headless PIL-decode). |
| 9 | Period selector supports presets (30d/90d/quarter/year) + validated custom range | ✓ VERIFIED | `main.py:401-490` — `period` enum `Query(..., pattern="^(30d\|90d\|quarter\|year)$")`, `from_`/`to` validated (both-or-neither, `to>=from`, span cap `MAX_ANALYTICS_WINDOW_DAYS`), `last_completed_quarter()` helper backs the `quarter` preset and the no-period default. |
| 10 | New SLA-compliance section excludes actively-excepted findings (`exclude_exceptions=True`), captioned trailing-90-day | ✓ VERIFIED | `export.py:543`: `get_sla_metrics(db, tenant_id, exclude_exceptions=True)`; caption confirmed present (see #7). |
| 11 | Zero-data section renders "Not yet measured", never fabricated 0/100% | ✓ VERIFIED | `export.py` SLA block: `not_measured = sla.get("remediated_total", 0) == 0` gates the render; MTTR block renders "Not yet measured" per-tier when `count == 0`. |
| 12 | Risk-trend chart with <2 points renders "not enough history" note, never a fabricated line | ✓ VERIFIED | `export.py` risk_trend block: `if len(scored) >= 2: ... elif len(scored)==1: ... else: row("Risk Trend","Not enough history to plot a trend yet")`. Frontend `RiskTrendWidget` (dashboard page.tsx) mirrors with `scoredPointCount < 2` → neutral note (`data-testid="risk-trend-no-history"`). |
| 13 | Existing scheduled reports keep exact shape; 3 new section keys appended (never mid-list) at all 3 call sites | ✓ VERIFIED | `reports.py`'s `create_report`/`_send_report` default-sections lists both append the 3 new keys at the end; `test_reports.py` (6 tests) proves lockstep + explicit-sections-preserved. |
| 14 | Scheduled board report picked up by `run_due_reports`/`_is_due`, generated on cadence via existing SMTP path | ✓ VERIFIED | `test_reports.py` end-to-end pickup+SMTP+audit-status test passes. |
| 15 | E9 populated/empty/error states (print-safe light-mode hexes, neutral gray dashed version-boundary, "charts unavailable" flag on render failure) | ✓ VERIFIED | `export.py` chart-render helpers use documented print-safe hexes; each of the 3 new sections wraps chart embedding in try/except → `charts_enabled`/`chart_failed` flag → "(chart unavailable — showing table)" fallback text, never a silently-dropped section. |
| 16 | User can open "Export board report" dialog, choose period, download branded PDF | ✓ VERIFIED | `export-board-report-dialog.tsx` (533 lines) — period presets/custom range, authenticated blob-download fetch against `/api/v1/export/summary`. 15 unit tests pass. Checkpoint (Plan 03 Task 2) human-verified against real generated PDFs; user approved (per 43-03-SUMMARY.md D5, plan `gate="blocking"` — execution could not have proceeded to Plan 04 without this approval). |
| 17 | Dialog default period = "Last quarter"; scheduling disclosure inline (no second dialog); E7 destructive stop-confirm | ✓ VERIFIED | Dialog code confirms default `quarter` preset, inline cadence/recipients reveal, "Stop scheduled board report" confirm dialog (`Cancel`/`Stop sending`) calling `DELETE /api/v1/reports/{id}`. Tests pass. |
| 18 | RPT-02: `/dashboard` renders per job-function lens (analyst/IT-ops/compliance/leadership); lens ≠ RBAC role tier | ✓ VERIFIED | `use-lens.ts` (81 lines): `useUrlState<Lens>` + localStorage fallback, default `analyst`; no `User.role` reference anywhere in lens logic. `lens-switcher.tsx` (67 lines) 4-segment control. |
| 19 | Analyst/IT-ops render existing action-first dashboard byte-for-byte unchanged | ✓ VERIFIED | `page.tsx` preserves the onboarding early-return as outermost check (unchanged), analyst/it-ops branch renders the pre-existing hero/stat-strip/activity-rail/top5 block verbatim; `dashboard/page.test.tsx` original 4 tests unmodified and still passing. |
| 20 | Leadership lens: Export CTA, risk-trend, MTTR tile, SLA tile, posture strip — no triage widgets | ✓ VERIFIED | `page.tsx` leadership branch composes exactly these 5 items; `dashboard/page.test.tsx` `?lens=leadership` tests pass. |
| 21 | Compliance lens: hero posture strip, compact SLA tile, compact trend, "View full compliance page" link | ✓ VERIFIED | `page.tsx` compliance branch; `?lens=compliance` tests pass. |
| 22 | Lens persists via `?lens=` + localStorage fallback; default analyst | ✓ VERIFIED | `use-lens.ts` dual-persistence logic confirmed; tests cover URL-param, localStorage-seed, and switch-persists cases. |
| 23 | Framework-posture strip aggregates pass/partial/fail/not-measured per framework from `/api/v1/compliance/overview`; pills link to `/dashboard/compliance?framework=` | ✓ VERIFIED | `framework-posture-strip.tsx` line 85: `href={\`/dashboard/compliance?framework=${framework}\`}`. 4 tests pass. |
| 24 | Every lens widget is tenant-scoped | ✓ VERIFIED | All new hooks (`use-mttr-by-tier`, `use-sla-metrics`, `use-compliance`) hit existing `require_viewer`/`require_admin`-gated, tenant-scoped routes; no client-supplied tenant id anywhere. |
| 25 | Leadership/compliance SLA tile exception-consistent with compliance page + board PDF (`exclude_exceptions=true`) | ✓ VERIFIED | Confirmed 3-way: `compliance/service.py:89` (`exclude_exceptions=True`), `export.py:543` (`exclude_exceptions=True`), `use-sla-metrics.ts:37` (`?exclude_exceptions=true`) — all three surfaces use the same guarded source. Backend route additively gained `exclude_exceptions: bool = Query(False)` (`vulnerabilities/router.py:206-220`), default preserves existing consumers. `test_sla_route.py` (2 tests) pass. |
| 26 | Onboarding gate remains outermost check, unchanged | ✓ VERIFIED | Confirmed in `page.tsx` structure + dedicated regression test ("onboarding-preempts-lens"). |

**Score:** 26/26 truths verified (consolidated from ROADMAP success criteria + all 4 plans' `must_haves.truths`; duplicative/overlapping truths across plans counted once)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/compliance/catalog.py` | `ControlDef` + `CATALOG` (4 frameworks) + `evaluate_catalog()` | ✓ VERIFIED | Present, `def evaluate_catalog` found, None-short-circuit confirmed |
| `backend/app/compliance/service.py` | `get_compliance_overview()` compute-once | ✓ VERIFIED | Present, 4 async calls, `exclude_exceptions=True` wired |
| `backend/app/compliance/router.py` | `GET /overview`, `require_viewer` | ✓ VERIFIED | Present, registered in `main.py:327` |
| `backend/app/compliance/schemas.py` | Response models | ✓ VERIFIED | Present |
| `backend/app/compliance/__init__.py` | Package marker | ✓ VERIFIED | Docstring added (WR-02 fix), no longer empty |
| `frontend/.../dashboard/compliance/page.tsx` | Full page, 4 states | ✓ VERIFIED | 274 lines, all states present |
| `frontend/.../components/compliance/control-card.tsx` | Presentation-only card | ✓ VERIFIED | not_measured dashed treatment confirmed |
| `frontend/.../lib/queries/use-compliance.ts` | `useComplianceOverview()` hook | ✓ VERIFIED | Present |
| `backend/pyproject.toml` | `matplotlib>=3.9` + `Pillow>=10.0` | ✓ VERIFIED | Present |
| `backend/app/export.py` | Chart helpers + 3 sections + section-gating for all 9 keys | ✓ VERIFIED | CR-01 fix confirmed — all 6 legacy + 3 new sections gated by `if "X" in sec:` |
| `backend/app/vulnerabilities/service.py::get_mttr_by_tier` | Additive `start`/`end` | ✓ VERIFIED | Confirmed lines 507-513 |
| `frontend/.../export-board-report-dialog.tsx` | Period + scheduling + E4/E7 states | ✓ VERIFIED | 533 lines, DELETE-confirm flow confirmed |
| `frontend/.../hooks/use-lens.ts` | URL+localStorage dual persistence | ✓ VERIFIED | 81 lines |
| `frontend/.../components/dashboard/lens-switcher.tsx` | 4-segment control | ✓ VERIFIED | 67 lines |
| `frontend/.../components/dashboard/framework-posture-strip.tsx` | Per-framework pills | ✓ VERIFIED | 157 lines, deep-links confirmed |
| `frontend/.../components/dashboard/mttr-by-tier-tile.tsx` / `sla-compliance-tile.tsx` | Tiles w/ null-signal honesty | ✓ VERIFIED | 87 / 85 lines |
| `frontend/.../app/(authed)/dashboard/page.tsx` | Lens-branched composition | ✓ VERIFIED | Onboarding gate outermost, WR-01 error-vs-empty distinction confirmed |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `compliance/service.py` | `sla_service.py::get_sla_metrics` | `exclude_exceptions=True` + `remediated_total==0→None` | ✓ WIRED | Confirmed line 89 |
| `compliance/service.py` | `catalog.py::evaluate_catalog` | pass metrics dict | ✓ WIRED | Confirmed |
| `frontend compliance/page.tsx` | `/api/v1/compliance/overview` | `useComplianceOverview()` | ✓ WIRED | Confirmed |
| `main.py` | `compliance/router.py` | `include_router` | ✓ WIRED | Confirmed line 327 |
| `export.py` | `analytics/sla_service/vulnerabilities service.py` | direct calls, `exclude_exceptions=True` | ✓ WIRED | Confirmed line 543 |
| `export.py` | matplotlib Figure/FigureCanvasAgg → `pdf.image()` | BytesIO PNG buffer | ✓ WIRED | Confirmed, no pyplot |
| `reports.py` | `export.py::generate_executive_summary_pdf` | `run_due_reports`→`_send_report` | ✓ WIRED | `test_reports.py` end-to-end pass |
| `export-board-report-dialog.tsx` | `/api/v1/export/summary` | authenticated blob-download fetch | ✓ WIRED | Confirmed |
| `framework-posture-strip.tsx` | `/dashboard/compliance?framework=` | pill `href` | ✓ WIRED | Confirmed line 85 |
| `leadership-hero.tsx` | `export-board-report-dialog.tsx` | Export CTA opens dialog | ✓ WIRED | Confirmed via dashboard/page.tsx composition + tests |
| `dashboard/page.tsx` | `use-lens.ts` | lens branches JSX | ✓ WIRED | Confirmed |
| `mttr-by-tier-tile.tsx` | `/api/v1/vulnerabilities/mttr/by-tier` | `useMttrByTier()` | ✓ WIRED | Confirmed |
| `use-sla-metrics.ts` | `/api/v1/vulnerabilities/sla/metrics?exclude_exceptions=true` | `useSlaMetrics()` | ✓ WIRED | Confirmed line 37 |
| `vulnerabilities/router.py::sla_metrics` | `sla_service.py::get_sla_metrics` | additive `exclude_exceptions` param | ✓ WIRED | Confirmed lines 206-220 |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Backend test suites for phase 43 (compliance/sla/export/reports/mttr/sla_route) | `pytest tests/test_compliance.py tests/test_sla_service.py tests/test_export.py tests/test_reports.py tests/test_mttr.py tests/test_sla_route.py -q` | 74 passed | ✓ PASS |
| Frontend test suites for phase 43 (compliance page, export dialog, lens switcher, posture strip, dashboard page) | `vitest run compliance/page.test.tsx export-board-report-dialog.test.tsx lens-switcher.test.tsx framework-posture-strip.test.tsx dashboard/page.test.tsx` | 46 passed (5 files) | ✓ PASS |
| No `matplotlib.pyplot` import anywhere in backend/app | `grep -rn "import matplotlib.pyplot" backend/app` | 0 matches | ✓ PASS |
| CR-01 regression test present and passing | `grep -n test_pdf_legacy_sections_are_gated tests/test_export.py` | Found at line 450; included in the 74-passed run above | ✓ PASS |
| Review-fix commits present on current branch tip | `git log --oneline -15` | `5eb137c`/`6624801`/`019655f` all present, ahead of the code-review commit | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| RPT-01 | 43-02, 43-03 | Exportable exec/board PDF (risk trend + MTTR-by-tier + SLA compliance, selected period) | ✓ SATISFIED | Backend sections + validated period params (43-02) + frontend dialog + human-verified PDF (43-03); marked `[x]` in REQUIREMENTS.md |
| RPT-02 | 43-04 | Role-scoped/job-function dashboards, tenant-scoped | ✓ SATISFIED | 4-lens dashboard, decoupled from RBAC, tenant-scoped endpoints, human-verified in-browser; marked `[x]` in REQUIREMENTS.md |
| RPT-03 | 43-01 | Compliance view mapping findings to framework controls | ✓ SATISFIED | 10-control catalog, compute-once service, `/dashboard/compliance` page; marked `[x]` in REQUIREMENTS.md |

No orphaned requirements found — REQUIREMENTS.md's Phase 43 row lists exactly RPT-01/RPT-02/RPT-03, all three appear in plan frontmatter (`requirements:` fields across 43-01/02/03/04), and all three are checked complete.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/app/export.py` | 933 | Dead-code duplicate `n = len(d["top_hosts"])` (IN-01, 43-REVIEW.md) | ℹ️ Info | Cosmetic only, not fixed — non-blocking per REVIEW.md, no functional effect |
| `frontend/.../control-card.tsx` | 58-67 | `evidencingLine` percentage-branch has no exhaustiveness guard for future non-percentage `metric_key`s (IN-02, 43-REVIEW.md) | ℹ️ Info | No current impact (all 5 live metric keys are percentage-shaped); flagged for future catalog additions, not fixed — non-blocking |

No blocker or warning anti-patterns remain — CR-01/WR-01/WR-02 were all fixed and independently re-verified in this pass (see Context section above). No TODO/FIXME/PLACEHOLDER/stub patterns found in any phase-43 file scanned.

### Human Verification Required

None outstanding. Both `checkpoint:human-verify` gates built into this phase's plans (43-03 Task 2: generated board PDF visual quality; 43-04 Task 3: all four dashboard lenses in-browser) already ran during execution and were approved by the user before the phase was allowed to proceed to its next plan (both gates are `gate="blocking"` — the phase could not have reached its documented "4/4 plans complete" state without those approvals). This verification pass independently confirmed the underlying code/tests these checkpoints exercised are still present and passing; it did not re-run the visual checkpoints themselves since they are not new information.

One informational (non-blocking) note carried over from `43-01-SUMMARY.md` D5 and consistent with this project's established convention (see project memory "Axe sweep not run during execution"): no prod-build Playwright/axe WCAG-AA sweep was run for the new `/dashboard/compliance` page or the new dashboard lens widgets. This is a project-wide, previously-accepted gap pattern (not unique to Phase 43) and is not part of any must-have in ROADMAP.md's success criteria or the plans' `must_haves` blocks for this phase.

### Gaps Summary

None. All 3 phase requirements (RPT-01, RPT-02, RPT-03) are implemented, tested, and wired end-to-end. The one blocker (CR-01) and two warnings (WR-01, WR-02) surfaced by the phase's own code-review pass were fixed in dedicated commits before this verification ran, and all three fixes were independently re-confirmed against the actual source (not just REVIEW.md's claim) — including a new regression test for CR-01 that specifically proves the fix (requests a narrow `sections` list and asserts other legacy sections are absent from the rendered PDF). Backend (74 tests) and frontend (46 tests) suites for every file this phase touched pass cleanly. The three RESEARCH.md landmines (fake-100 on zero data, exception-exclusion consistency, MTTR/SLA period parameterization) are all threaded and verified consistently across all three consuming surfaces (compliance page, board PDF, dashboard tile).

---

_Verified: 2026-08-24T15:20:00Z_
_Verifier: Claude (gsd-verifier)_
