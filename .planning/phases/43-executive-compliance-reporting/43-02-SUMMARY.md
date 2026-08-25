---
phase: 43-executive-compliance-reporting
plan: 02
subsystem: reporting
tags: [fastapi, sqlalchemy, matplotlib, fpdf2, pytest]

# Dependency graph
requires:
  - phase: 43-01
    provides: get_sla_metrics(severity=, exclude_exceptions=) additive extension
  - phase: 36-remediation-sla-engine-escalation
    provides: get_mttr_by_tier, RemediationEvent, get_sla_metrics
  - phase: 42-risk-trend-analytics-burndown
    provides: get_scoped_trend_series, detect_version_boundaries, MAX_ANALYTICS_WINDOW_DAYS, analytics/router.py's custom-range validation block
provides:
  - "3 no-pyplot matplotlib chart-render helpers in export.py (_render_risk_trend_chart / _render_mttr_by_tier_chart / _render_sla_compliance_chart) -- reusable pattern for any future PDF chart"
  - "generate_executive_summary_pdf extended with 3 period-aware, exception-consistent, zero-data-honest sections (risk trend -> MTTR by tier -> SLA compliance) in UI-SPEC order, with a charts_enabled tables-only fallback"
  - "get_mttr_by_tier(db, tenant_id, start=, end=) additive period filter"
  - "export_resource period (30d/90d/quarter/year) + from/to (validated custom range) query params + last_completed_quarter() helper + extended export.summary audit payload"
  - "reports.py default sections lockstep (create_report + _send_report), so existing + newly-scheduled board reports include the 3 new sections via the unchanged SMTP delivery path"
affects: [43-03-rpt01-export-dialog]

# Tech tracking
tech-stack:
  added: [matplotlib>=3.9, Pillow>=10.0 (explicit; was already transitive via fpdf2)]
  patterns:
    - "Figure + FigureCanvasAgg only, matplotlib imported lazily inside each chart helper -- never module-level, never pyplot (thread-safety)"
    - "charts_enabled filter-level toggle + per-section try/except -> tables-only fallback, never a silently-dropped section on a chart-render failure"
    - "Gated computation: _collect_summary_data only computes/queries the 3 new sections' data when at least one of their keys is actually requested (backward-compatible + zero extra cost for CSV/txt/narrower callers)"
    - "Zero-denominator discipline extended to a per-tier granularity (MTTR) as well as whole-metric (SLA) -- a tier with data renders as a real bar, a tier without renders 'Not yet measured' text, never a fabricated 0"

key-files:
  created:
    - backend/tests/test_export.py
    - backend/tests/test_reports.py
    - .planning/phases/43-executive-compliance-reporting/deferred-items.md
  modified:
    - backend/pyproject.toml
    - backend/app/export.py
    - backend/app/vulnerabilities/service.py
    - backend/app/main.py
    - backend/app/reports.py
    - backend/tests/test_mttr.py
    - backend/mypy-baseline.txt

key-decisions:
  - "RPT-01 is NOT marked complete in REQUIREMENTS.md/ROADMAP.md despite being this plan's `requirements:` tag -- ROADMAP.md's own Wave 2/Wave 3 lines tag BOTH 43-02 (backend, this plan) AND 43-03 (frontend export dialog) as [RPT-01], a deliberate multi-plan split. A user cannot yet select a period or trigger a board PDF without hand-crafting query params -- the requirement's real completion waits on 43-03's UI. requirements-completed is left empty; ROADMAP.md's plan checkbox and progress count (2/4) ARE updated (that tracks plan completion, not requirement completion)"
  - "last_completed_quarter() lives in export.py, not main.py (plan left this an explicit executor choice) -- _collect_summary_data needs it as ITS OWN internal default (scheduled reports have no period-selection route at all and must still get a sane, non-unbounded default), and main.py's route reuses the same function for its period=quarter preset and its own no-period default, so there is exactly one definition of 'last quarter'"
  - "No burndown PDF section was built, despite the plan's edge_coverage_assumptions mentioning a 'Pitfall-4 burndown window' decision. 43-UI-SPEC.md's own 'RPT-01 PDF Rendering Contract' names exactly 3 new sections (risk trend / MTTR by tier / SLA compliance); this plan's must_haves/artifacts/acceptance_criteria never mention a 4th (burndown) section. Treated the edge_coverage_assumptions burndown language as RESEARCH.md boilerplate inherited into the plan file, not an actionable Plan 02 deliverable -- flagged explicitly here rather than silently either building an unrequested section or silently ignoring the note"
  - "MTTR-by-tier's zero-denominator handling is per-TIER, not per-section: a tier with real remediation data in the window renders a real bar in the chart; a tier with zero data renders a 'Not yet measured' text row instead of a 0-height bar (which would look like a real, misleadingly-fast MTTR). Only when ALL 3 tiers are empty does the section skip the chart entirely and render text-only, matching 43-UI-SPEC.md E9's literal 'zero-denominator MTTR/SLA sections render their tables/labels' wording (not a placeholder chart image, unlike the trend chart's own <2-point in-image note)"
  - "The E9 'chart-render failure surfaces a flag the route can act on' requirement is satisfied via a request-level `filters['charts_enabled']` toggle (defaults True) plus per-section try/except -> tables-only degradation with an inline '(chart unavailable -- showing table)' note -- not a new return-type/exception contract on generate_executive_summary_pdf. This gives Plan 03's future 'retry with charts off' dialog a real backend lever to call into without inventing an unspecified API shape now"
  - "SLA-compliance color thresholds (pass >=95 / approaching >=80 / breached <80) and MTTR tier display order/colors (critical/high/moderate, print-safe hexes) are centralized as small pure helpers (_sla_compliance_color, _MTTR_TIER_DISPLAY) in export.py rather than inlined at each call site -- directly unit-testable in isolation from PDF generation"

patterns-established:
  - "export.py's chart-render helpers are the reusable template for any future PDF chart: Figure(figsize, dpi=200) + FigureCanvasAgg, lazy matplotlib import, fig.savefig(buf, format='png') -> io.BytesIO -> pdf.image(buf, w=180)"
  - "A stdlib-only (zlib + regex) PDF content-stream text extractor in test_export.py (_pdf_text_tokens) -- fpdf2 FlateDecode-compresses content streams by default, so a raw substring search over PDF bytes can't see drawn text at all; this extractor decompresses every stream block and pulls every Tj-operator string literal IN DRAW ORDER, enabling both section-order and literal-text assertions without a new PDF-parsing dependency"

requirements-completed: []

coverage:
  - id: D1
    description: "matplotlib>=3.9 + explicit Pillow>=10.0 dependency + 3 no-pyplot chart-render helpers (Figure+FigureCanvasAgg only), each producing a headless-PIL-decodable PNG; risk-trend helper degrades to a neutral 'not enough history' note under 2 real data points"
    requirement: "RPT-01"
    verification:
      - kind: unit
        ref: "backend/tests/test_export.py (6 tests: 3 chart-decodability + version-boundary-marker + <2-point-degradation + whole-tree no-pyplot grep)"
        status: pass
    human_judgment: false
  - id: D2
    description: "get_mttr_by_tier additively extended with keyword-only start/end -- filters RemediationEvent.remediated_at to the window; default call byte-identical to every pre-existing call site"
    requirement: "RPT-01"
    verification:
      - kind: unit
        ref: "backend/tests/test_mttr.py::test_get_mttr_by_tier_start_end_filters_to_remediated_at_window"
        status: pass
    human_judgment: false
  - id: D3
    description: "generate_executive_summary_pdf gains 3 sections in UI-SPEC order (risk trend -> MTTR by tier -> SLA compliance) after the summary-stats block, before top-hosts; SLA computed with exclude_exceptions=True and captioned as a fixed trailing-90-day metric; zero-remediation SLA and zero-data MTTR tiers render 'Not yet measured', never 0/100%; sections omitting the 3 new keys are byte-compatible with the pre-existing 6-section shape"
    requirement: "RPT-01"
    verification:
      - kind: unit
        ref: "backend/tests/test_export.py (embeds-charts, UI-SPEC section-order via stdlib zlib text extraction, not-yet-measured render, exclude_exceptions wiring cross-checked against get_sla_metrics directly, backward-compatibility, gated-computation-skips-queries)"
        status: pass
    human_judgment: false
  - id: D4
    description: "export_resource gains period (30d/90d/quarter/year) + from/to query params; custom-range validation ported verbatim from analytics/router.py (both-or-neither, to>=from, span cap at MAX_ANALYTICS_WINDOW_DAYS); period=quarter and the no-period default both resolve via last_completed_quarter(); the export.summary audit payload now records the resolved period + requested sections"
    requirement: "RPT-01"
    verification:
      - kind: integration
        ref: "backend/tests/test_export.py (7 route tests: quarter resolution, no-period default, 3 distinct 422 branches, within-cap success, audit-payload content -- all via a real HTTP client against the live app + a real DB-backed AuditLog row read-back)"
        status: pass
    human_judgment: false
  - id: D5
    description: "reports.py's 2 remaining default-sections literals (create_report, _send_report's fallback) append the 3 new keys at the end, kept in lockstep with export.py's own default; an explicit pre-existing sections list is never overridden (existing scheduled reports keep their exact shape); run_due_reports/_is_due picks up a report carrying the new keys and sends the extended PDF via the existing SMTP path"
    requirement: "RPT-01"
    verification:
      - kind: integration
        ref: "backend/tests/test_reports.py (6 tests: create_report default shape, explicit-sections-preserved, _send_report fallback-vs-preserved-shape, run_due_reports end-to-end pickup+SMTP+audit-status, not-yet-due skip)"
        status: pass
    human_judgment: false
  - id: D6
    description: "Visual/print board-deck quality of the 3 new chart images (color fidelity, legibility, layout/pagination) as an actual human stakeholder would judge them"
    verification: []
    human_judgment: true
    rationale: "Automated tests prove PNG decodability, section order, and literal rendered text, but cannot judge visual board-deck quality. The executor DID generate 2 realistic sample PDFs this session (one with a populated risk-trend line in the tenant's brand color; one isolating MTTR-by-tier + SLA-compliance with a real red breached-threshold bar + caption) and visually inspected both via macOS QuickLook thumbnails -- a stronger self-check than a bare claim, and every rendered value cross-checked correct against the seeded data. This is still not an independent human/verifier sign-off, and multi-page pagination under a large realistic dataset (many hosts/vulns spanning several pages) was not exercised -- appropriate for a dedicated visual-verification pass."

duration: 92min
completed: 2026-08-24
status: complete
---

# Phase 43 Plan 02: RPT-01 Backend (Board PDF + Scheduled Reports) Summary

**Extended the existing branded exec-summary PDF with 3 real matplotlib-rendered chart sections (risk trend, MTTR-by-tier, SLA compliance) for a caller-selected period, made the board report schedulable via the existing SMTP delivery path, and along the way fixed a previously-undiscovered latent crash (every prior call to `generate_executive_summary_pdf` would raise on the em-dash in its own title).**

## Performance

- **Duration:** 92 min
- **Started:** 2026-08-24T08:15:00Z
- **Completed:** 2026-08-24T09:47:00Z
- **Tasks:** 3
- **Files modified:** 10 (7 modified, 3 created)

## Accomplishments
- `matplotlib>=3.9` + explicit `Pillow>=10.0` added; 3 chart-render helpers (`_render_risk_trend_chart` / `_render_mttr_by_tier_chart` / `_render_sla_compliance_chart`) built strictly on `Figure`+`FigureCanvasAgg` (never `pyplot`), verified headless-PNG-decodable and free of any `matplotlib.pyplot` import anywhere in `backend/app`
- `get_mttr_by_tier` additively extended with an optional `(start, end)` window (Pitfall 3's "no period param" landmine), byte-identical for every existing caller
- `generate_executive_summary_pdf` gained 3 new sections in the exact UI-SPEC order (risk trend -> MTTR by tier -> SLA compliance), each exception-consistent (`exclude_exceptions=True`) and zero-data-honest (`Not yet measured`, never a fabricated 0/100%), with a `charts_enabled` toggle + try/except tables-only fallback so a chart-render failure never silently drops a section
- `export_resource` gained `period`/`from`/`to` query params with the exact custom-range DoS guard ported from `analytics/router.py`, a new `last_completed_quarter()` helper backing both the `quarter` preset and the D-03 no-period default, and an extended `export.summary` audit payload
- `reports.py`'s remaining 2 default-`sections` literals brought into lockstep with `export.py`'s own default (appended-only, existing scheduled reports keep their exact shape); `run_due_reports` proven end-to-end to pick up a report with the new keys and deliver the extended PDF via the pre-existing SMTP path
- Self-verified via 2 realistic generated sample PDFs (screenshotted via macOS QuickLook) -- confirmed the risk-trend line renders in the tenant's own brand color with a correctly-rotated date axis, the SLA-compliance bar renders red at a computed 20.0% (cross-checked correct against the seeded remediation timestamps) with the exact "Trailing 90-day metric, independent of the selected period" caption, and MTTR-by-tier correctly rendered all 3 tiers as "Not yet measured" when the (intentionally) out-of-window seed data proved the period-scoping genuinely excludes data outside the selected window

## Task Commits

Each task was committed atomically:

1. **Task 1: Add matplotlib/Pillow deps + chart-render helpers** - `7bae432` (feat)
2. **Task 2: Three new PDF sections + get_mttr_by_tier period extension** - `9313aa9` (feat)
3. **Task 3: Export route period params + validation + scheduled-report section keys** - `b2a8b81` (feat)

_All three tasks carry `tdd="true"` in the plan. See "TDD Gate Compliance" below for a disclosure on how that was executed._

## Files Created/Modified
- `backend/pyproject.toml` - `matplotlib>=3.9` + `Pillow>=10.0` added to `[project] dependencies`
- `backend/app/export.py` - 3 chart-render helpers; `last_completed_quarter()` + `_MTTR_TIER_DISPLAY` + `_sla_compliance_color` module-level helpers; `_collect_summary_data` gains `risk_trend`/`mttr_by_tier`/`sla_compliance` return keys (gated on whether requested); `generate_executive_summary_pdf` draws the 3 new sections + fixes the pre-existing em-dash crash (`core_fonts_encoding = "cp1252"`) + type-annotates its `row()`/`section()` closures
- `backend/app/vulnerabilities/service.py` - `get_mttr_by_tier` gains optional keyword-only `start`/`end`
- `backend/app/main.py` - `export_resource` gains `period`/`from_`/`to` query params, the ported custom-range validation, period resolution, and the extended audit payload
- `backend/app/reports.py` - `create_report`'s and `_send_report`'s default `sections` literals both append the 3 new keys
- `backend/mypy-baseline.txt` - synced after type-annotating `row()`/`section()` resolved 11 pre-existing baselined errors (mechanical, `mypy-baseline sync`)
- `backend/tests/test_export.py` (new) - 20 tests across chart-render helpers, the 3 new PDF sections, and the `export_resource` route's period/validation/audit behavior
- `backend/tests/test_reports.py` (new) - 6 tests covering `create_report`/`_send_report` default-sections lockstep and `run_due_reports`/`_is_due` end-to-end delivery
- `backend/tests/test_mttr.py` - 1 new test for `get_mttr_by_tier`'s `start`/`end` window filter
- `.planning/phases/43-executive-compliance-reporting/deferred-items.md` (new) - logs an out-of-scope, pre-existing discovery (see Issues Encountered)

## Decisions Made

See `key-decisions` in frontmatter for the full list. The two most consequential:

1. **RPT-01 is left unmarked in REQUIREMENTS.md/ROADMAP.md's requirement tracking.** ROADMAP.md itself tags both this plan (43-02, backend) and the still-unexecuted 43-03 (frontend export dialog) as `[RPT-01]` -- a deliberate multi-plan split. Marking the requirement complete now, before a user has any UI path to select a period or trigger an export, would be a materially false status. The plan-level checkbox and progress count (2/4) ARE updated since those track plan completion, which genuinely happened.
2. **No burndown PDF section was built.** The plan's `edge_coverage_assumptions` block carries RESEARCH.md language about a "Pitfall-4 burndown window" decision, but the plan's own must_haves/artifacts/acceptance_criteria consistently name exactly 3 new sections (risk trend / MTTR by tier / SLA compliance), matching 43-UI-SPEC.md's literal PDF Rendering Contract. Treated as inherited research boilerplate rather than a Plan 02 deliverable, flagged explicitly rather than silently building an unrequested 4th section or silently dropping the note.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] fpdf2's default core-font encoding cannot render the PDF's own hardcoded em-dash**
- **Found during:** Task 2, first attempt to actually call `generate_executive_summary_pdf` in a test (Wave 0 gap -- no test had ever exercised this function before)
- **Issue:** fpdf2's `core_fonts_encoding` defaults to `"latin-1"`, which does not cover the em-dash (U+2014) the PDF's title (`f"{company_name} — Executive Summary"`) and footer have always hardcoded. Every real call to `generate_executive_summary_pdf` -- for any tenant, regardless of this plan's changes -- would raise `FPDFUnicodeEncodingException`. This predates Plan 02 entirely; it was simply never caught because no automated test had ever called this function.
- **Fix:** Set `pdf.core_fonts_encoding = "cp1252"` right after `FPDF()` construction -- cp1252 is a superset-compatible encoding for this font (identical for ASCII, adds the em-dash at byte 0x97), so the fix changes zero visible rendered text.
- **Files modified:** backend/app/export.py
- **Verification:** Verified in a throwaway script before applying; all PDF-generating tests (Task 2/3) pass afterward.
- **Committed in:** 9313aa9 (Task 2 commit -- caught and fixed before commit)

**2. [Rule 3 - Blocking] New calls to the pre-existing untyped `row()`/`section()` PDF closures tripped the mypy CI gate**
- **Found during:** Task 2, running the project's `mypy | mypy-baseline filter --allow-unsynced` gate before committing
- **Issue:** `generate_executive_summary_pdf`'s local `row()`/`section()` closures had no type annotations; my new call sites (drawing the 3 new sections) produced `no-untyped-call` errors the baseline's count-based fuzzy matching flagged as new (15 new violations)
- **Fix:** Added `title: str -> None` / `label: str, value: str -> None` annotations to both closures -- this also retroactively resolved 11 pre-existing baselined errors for the OLD call sites using the same closures, synced via `mypy-baseline sync` (mechanical, zero semantic change)
- **Files modified:** backend/app/export.py, backend/mypy-baseline.txt
- **Verification:** `mypy app/ | mypy-baseline filter --allow-unsynced` exits 0 with 0 new violations after the fix (was 15 new before)
- **Committed in:** 9313aa9 (Task 2 commit)

**3. [Test-only, Rule 3 - Blocking] `_send_report`'s hardcoded `/app/reports` archive path doesn't exist outside the Docker image**
- **Found during:** Task 3, first `test_reports.py` run
- **Issue:** `_send_report` hardcodes `Path("/app/reports")` (the container's real WORKDIR) for its report-file archive step. This path doesn't exist locally, and CI's backend job runs on a bare `ubuntu-latest` runner (no `container:`, confirmed via `.github/workflows/ci.yml`) -- so this line has always been a latent CI-breaker the moment any test ever called `_send_report`/`run_due_reports` for real (another Wave 0 "never tested" gap, not a Plan 02 regression).
- **Fix:** Test-only -- `monkeypatch.setattr(Path, "mkdir"/"write_bytes"/"write_text", no-op)` inside `test_reports.py`'s 3 tests that call `_send_report`/`run_due_reports`. Zero production code change; every other observable behavior (filters wiring, SMTP send, audit status) is asserted on normally.
- **Files modified:** backend/tests/test_reports.py
- **Verification:** All 6 `test_reports.py` tests pass.
- **Committed in:** b2a8b81 (Task 3 commit)

**4. [Test-only] Route tests needed an explicit cross-session commit (WR-13) before the app's own audit() INSERT**
- **Found during:** Task 3, first `export_resource` route tests
- **Issue:** The test's `db_session` and the running app's own `get_db()`-sourced session are genuinely separate DB connections (documented convention, `conftest.py`'s `db_session` docstring, WR-13). Fixture-seeded `tenant_a`/the authed user are only `flush()`ed, not committed, by upstream fixtures -- invisible to the app's session. This doesn't matter for read-only routes (an empty/missing row just yields zero results), but `export_resource`'s `audit()` call is an FK-constrained INSERT referencing `tenant_id`, which fails outright if the tenant row isn't visible cross-session.
- **Fix:** Added `await db_session.commit()` at the top of each route test that expects a 200 (the 3 pure-validation 422 tests never reach the `audit()` INSERT, so they needed no change).
- **Files modified:** backend/tests/test_export.py
- **Verification:** All 7 route tests pass with the commit added.
- **Committed in:** b2a8b81 (Task 3 commit)

**5. [Rule 1 - Bug in my own test, caught before commit] Naive `/Image` substring check false-positived on fpdf2 boilerplate**
- **Found during:** Task 2, writing the "backward compatible / no charts drawn" test
- **Issue:** fpdf2 always emits a page `/ProcSet [/PDF /Text /ImageB /ImageC /ImageI]` resource array regardless of whether any image is actually embedded -- a plain `b"/Image" in pdf_bytes` check is a false positive on every generated PDF, not evidence of an embedded chart.
- **Fix:** Switched to the precise `/Subtype /Image` XObject marker (verified in a throwaway script to appear only when `pdf.image()` actually embeds something).
- **Files modified:** backend/tests/test_export.py
- **Verification:** The "no new sections -> no images" test now correctly fails if a chart is accidentally drawn, and passes when none is.
- **Committed in:** 9313aa9 (Task 2 commit -- caught and fixed before commit, not a follow-up patch)

---

**Total deviations:** 5 auto-fixed (2 production bugs/blockers, 3 test-only fixes)
**Impact on plan:** Both production fixes (em-dash crash, mypy typing) were required for this plan's own tests to run and for the CI gate to stay green -- necessary, not scope creep. All 3 test-only fixes are pure test-isolation corrections with zero production-code change.

## TDD Gate Compliance

All 3 tasks carry `tdd="true"`. Per-task execution did not produce a standalone `test(...)` RED commit before each `feat(...)` GREEN commit -- for every task, the `<behavior>` test cases were written immediately alongside the implementation, iterated to green, and committed together as a single `feat(43-02): ...` commit once fully verified. `git log` for this plan shows no `test(...)`-prefixed commits.

This is a **process deviation from the literal RED-then-GREEN commit sequence**, not a coverage gap: every `<behavior>` bullet specified in all 3 tasks has a corresponding passing test (enumerated in the `coverage:` frontmatter block above -- 6/7/13 tests respectively across the 3 tasks, 26 new tests total plus 1 in test_mttr.py), and no implementation code shipped without a verifying test in the same commit. The plan's frontmatter `type` is `execute` (not `tdd`), so the stricter plan-level RED/GREEN/REFACTOR gate sequence enforcement does not apply -- only the per-task `tdd="true"` attribute's commit-shape expectation was not followed literally, matching Plan 01's own precedent in this phase.

## Issues Encountered

- **Pre-existing, out-of-scope discovery:** `generate_executive_summary_pdf`'s `sections` toggle is a no-op for all 6 original sections (only the "Vulnerability Overview" section's *header* is gated; its rows and all 5 other sections' headers+rows draw unconditionally regardless of `sections`). Logged to `.planning/phases/43-executive-compliance-reporting/deferred-items.md` per the Scope Boundary rule -- not fixed here (pre-existing, unrelated to this plan's own 3 new sections, which ARE correctly gated end-to-end).
- **Full backend suite (1216-1217 tests) run twice; 1-2 failures each time, never the same set of 2 consistently:** `test_connector_health.py::test_scheduler_path_error_message_and_log_are_sanitized` and `test_ticketing_dispatch.py::test_close_ticket_endpoint_dispatches_by_ticket_provider`. Both pass cleanly in isolation; re-running the full suite a second time reproduced only 1 of the 2 failures. Neither test touches any file this plan modifies. Consistent with this codebase's documented "full-suite-only flake class" pattern (project memory) -- not investigated further as genuinely out of scope.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Backend is fully ready for Plan 03 (RPT-01 frontend export dialog): `GET /api/v1/export/summary` accepts `period=30d|90d|quarter|year` or a validated custom `from`/`to`, and the PDF/CSV/TXT outputs already include the 3 new sections by default.
- Plan 03 should thread a `charts=off` (or similar) query param into `filters["charts_enabled"]` to give the "retry with charts off (tables only)" E4/E6 UX a real backend lever -- the mechanism already exists, only the route-level parameter name/wiring is Plan 03's to choose.
- **RPT-01 should be marked complete in REQUIREMENTS.md/ROADMAP.md only once Plan 03 also ships** (see Decisions Made) -- do not mark it from this plan alone.
- No blockers for Plan 03 or Plan 04.

---
*Phase: 43-executive-compliance-reporting*
*Completed: 2026-08-24*

## Self-Check: PASSED

- All 11 claimed created/modified files verified present on disk.
- All 3 claimed commit hashes (`7bae432`, `9313aa9`, `b2a8b81`) verified present in `git log`.
