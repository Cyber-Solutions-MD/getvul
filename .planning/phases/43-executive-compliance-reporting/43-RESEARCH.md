# Phase 43: Executive & Compliance Reporting - Research

**Researched:** 2026-08-22
**Domain:** Server-side PDF chart rendering (Python/fpdf2/matplotlib) + compliance-framework control mapping (SOC 2 / ISO 27001 / PCI DSS / NIST CSF) + read-side dashboard composition over existing Phase 36/42 services
**Confidence:** HIGH (both flagged items independently verified — chart pipeline hands-on in a throwaway venv, framework controls cross-sourced against 2+ independent references each; codebase integration points read directly, not inferred)

## Summary

Phase 43 is almost entirely a **read-side composition problem**, not a new-capability problem. RPT-01/02/03 consume Phase 36 (MTTR-by-tier, SLA compliance) and Phase 42 (risk trend, burndown) outputs; the only genuinely new backend asset is the RPT-03 framework-control catalog (D-09), and the only genuinely new backend *dependency* is a charting library for the PDF (D-02). Both flagged items resolved with HIGH confidence:

**D-02 (chart rendering):** matplotlib's object-oriented API (`Figure` + `FigureCanvasAgg`, never `matplotlib.pyplot`) rendering to an in-memory PNG buffer, embedded via fpdf2's `pdf.image()`, is the correct and verified pattern — confirmed end-to-end in a throwaway venv (headless, `DISPLAY` unset, ~35-260ms/chart, zero crashes). The important **correction to the CONTEXT.md premise**: Pillow is *already* installed and required — it is fpdf2's own unconditional dependency (`Requires: defusedxml, fonttools, Pillow` — verified via `pip show fpdf2` and the PyPI registry), not a new addition. **Only `matplotlib` is a genuinely new dependency.** The backend's `python:3.12-slim` Docker base needs zero new `apt-get` packages (manylinux wheels bundle FreeType/libpng statically; matplotlib bundles its own DejaVu Sans font — verified live).

**D-09 (framework controls):** Verified canonical control IDs and paraphrased intent for all four frameworks, cross-sourced against 2-3 independent references each. **NIST CSF 2.0 text is U.S. public domain (17 U.S.C. §105) and may be quoted verbatim; SOC 2 (AICPA), ISO 27001, and PCI DSS text are all copyrighted — the catalog must reference control IDs + paraphrased intent for those three, never verbatim standard text.** A precise version correction: PCI DSS v4.0 was retired 2024-12-31; **v4.0.1 is the only active version as of 2026** (same requirement numbers, clarifications only) — the catalog and UI copy should say "PCI DSS v4.0.1."

Beyond the two flagged items, direct code reads surfaced two **non-obvious, high-value pitfalls** the planner must design around: (1) `sla_service.get_sla_metrics().compliance_pct` returns a hardcoded `100.0` — not `None` — when there is zero remediation history, which will silently defeat D-13's mandatory "Not yet measured" (never-fake-a-pass) requirement unless the catalog explicitly checks the metric's denominator; (2) that same function does **not** exclude actively-excepted findings (unlike the newer `analytics/service.py` and `export.py::_collect_summary_data`, which both do), so a board PDF's new SLA-compliance section would be internally inconsistent with the rest of the same document and would over-count breaches EXC-02 says should be excluded.

**Primary recommendation:** Add `matplotlib>=3.9` and explicit `Pillow>=10.0` to `backend/pyproject.toml`; render each chart with `Figure`+`FigureCanvasAgg` (never `pyplot`) straight to an `io.BytesIO` PNG buffer and hand that buffer directly to `pdf.image()`; build the RPT-03 catalog as a small set of ~5 reusable metric computations (each computed once) mapped to ~11 controls across 4 frameworks, with an explicit zero-denominator guard on every threshold check.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**RPT-01 — Exec/board PDF**
- **D-01:** Extend the existing branded exec-summary PDF (`export.py::generate_executive_summary_pdf`, fpdf2) with new v5.0 sections (risk trend, MTTR-by-tier, SLA compliance) rather than building a second board-report generator. Reuse its branding (logo/colors), section-toggle mechanism, and the shared exception-exclusion predicate in `_collect_summary_data`. One PDF codepath to maintain. — Reversibility: reversible — additive sections on an existing generator.
- **D-02:** Trend / burndown / MTTR charts are rendered server-side to raster images (PNG) and embedded in the PDF (the frontend recharts components can't render into fpdf). Produces a real board-deck look. **Flagged for research** (resolved above/below). — Reversibility: costly — adds a backend charting dependency to the image; falling back to tables/numbers later means re-authoring the PDF section.
- **D-03:** Period selector = presets (quarter / 30d / 90d / 1y) PLUS a custom start/end date-range picker, mirroring Phase 42 D-03's Analytics range-control idiom exactly. Default period is planner discretion (a board cadence like "last quarter" is natural).
- **D-04:** Reuse the existing `ScheduledReport` delivery (`reports.py`) — the board report becomes a selectable format/section-set that can auto-email on a cadence (daily/weekly/monthly already supported), in addition to on-demand export. Do not build a second scheduling/delivery path.
- **D-01a (data source, cross-cutting):** RPT-01 sources trend + burndown from Phase 42's reusable analytics service (`backend/app/analytics/service.py` — `get_scoped_trend_series`, `get_burndown_rate`, `get_analytics_overview`), MTTR-by-tier from `backend/app/vulnerabilities/service.py::get_mttr_by_tier`, and SLA compliance from `backend/app/vulnerabilities/sla_service.py::get_sla_metrics` (`compliance_pct`). Call these directly, no HTTP round-trip (Phase 42 D-16 shaped them for exactly this). Never re-derive.

**RPT-02 — Role-scoped dashboards**
- **D-05:** Switchable view-lens model — the four personas (analyst / IT-ops / compliance / leadership) are selectable dashboard lenses, NOT tied to the RBAC role tier (owner/admin/analyst/viewer). Any authenticated user can switch lens; "role" here means job function, not permission. Lens selection persists client-side (URL param / localStorage), no new backend user-preference column this phase. — Reversibility: reversible — a frontend selector + client-persisted state.
- **D-06:** Reconfigure the existing `/dashboard` hero per selected lens (one "home" page whose widget set swaps by persona) rather than net-new per-persona routes. Avoids duplicating the shell/layout and fragmenting "home".
- **D-07:** Leadership / compliance lenses = trend-&-posture widgets (risk trend, MTTR-by-tier, SLA-compliance %, framework posture summary, board-PDF export entry point). Analyst / IT-ops lenses = the existing action-first triage widgets (open criticals, my tickets, recent activity — the current `hero` / `stat-strip-wired` / `activity-rail` / `top5-card`). Exact per-lens widget composition is planner discretion, derived from existing dashboard components + Phase 42/36 data.

**RPT-03 — Compliance view**
- **D-08:** Program-level control-evidence model — map the vuln-management program to a curated set of framework controls (e.g. PCI DSS 6.3.3 / 11.3, SOC 2 CC7.1, ISO 27001 A.8.8, NIST CSF ID.RA / PR.PS); each control's status is evidenced by posture metrics, NOT by tagging individual CVEs. Answers "are we satisfying framework X's vuln-management controls." — Reversibility: reversible — a read-side mapping + rollup, no finding-level schema change.
- **D-09:** Built-in, version-controlled curated catalog (framework → relevant controls → evidencing metric) shipped in code. No tenant configuration or control overrides this phase. Consistent, auditable, upgradeable in code. **Flagged for research** (resolved below).
- **D-10:** Vuln-only this phase. Do NOT entangle RPT-03 with the existing CSPM framework grouping (`cspm/service.py::get_compliance_dashboard`, free-text `frameworks` JSONB on misconfigs). The two compliance surfaces stay separate; a unified vuln+CSPM rollup is deferred.
- **D-11:** New top-level "Compliance" nav page (`/dashboard/compliance` + a `nav-items.ts` entry), mirroring the Coverage (Phase 41) and Analytics (Phase 42) new-page precedent. Also reachable from the compliance dashboard lens (D-07).
- **D-12:** All four frameworks ship day one — SOC 2, ISO 27001, PCI DSS, NIST CSF (the full RPT-03 set).
- **D-13:** Control status = thresholds on posture metrics. Each catalog control maps to a metric (SLA-compliance %, coverage %, open-critical count) with pass / partial / fail thresholds defined in the built-in catalog (e.g. "PCI 6.3.3 = pass if critical SLA-compliance ≥ 95%"). Deterministic and explainable. Drill-into-the-specific-findings-behind-a-control is deferred (not this phase). Exact metric-per-control + thresholds are planner discretion within the catalog.

### Claude's Discretion
- Default reporting period for the PDF (D-03) and exact new PDF section layout/order (D-01). **Note:** 43-UI-SPEC.md has since locked the default preset to `Last quarter` and the section order (risk trend → MTTR by tier → SLA compliance, inserted after the existing summary-stats block, before top-hosts/top-remediations/tickets) — treat as decided, not open.
- Charting library choice + how images are generated and embedded (D-02) — subject to the dependency flag. **Resolved below: matplotlib + Agg.**
- Exact per-lens widget composition for each persona (D-07); how the lens switcher renders (segmented control, dropdown) and where it sits on `/dashboard`. **Note:** 43-UI-SPEC.md has since locked this to a 4-segment ChipBar-style control, top-right of the dashboard header — treat as decided.
- Exact catalog contents: which controls per framework are vuln-management-relevant, which metric evidences each, and the pass/partial/fail thresholds (D-09/D-13). **A concrete starting proposal is given below** — still adjustable by the planner within the catalog.
- `/dashboard/compliance` route naming/layout and whether framework posture also renders as a compact section inside the compliance lens vs. only the standalone page (D-11). **Note:** 43-UI-SPEC.md has since locked this — both surfaces exist (full page + a compact strip inside the Leadership/Compliance lenses) — treat as decided.

### Deferred Ideas (OUT OF SCOPE)
- Redo the filtering / ChipBar UI/UX (raised mid-discussion) — a new capability, its own future phase. Not folded into Phase 43.
- Per-finding framework-control tagging — D-08 chose program-level evidence; per-CVE control tagging would need a CVE→control mapping source and is low-value for most findings.
- Tenant-configurable compliance catalog / control overrides + thresholds — D-09 ships a built-in curated catalog; a settings UI to toggle controls/thresholds is a later enhancement.
- Unified vuln + CSPM compliance view — D-10 is vuln-only; blending CSPM's free-text framework strings into one per-framework rollup is deferred.
- Control → drill-into-specific-findings evidence view — D-13 ships threshold-derived status only; showing the exact open findings behind each control's status is a richer later add.
- Saved "default dashboard view" as a backend user preference — D-05 persists lens client-side only; a server-side per-user default is a small later enhancement.

None of the above blocks Phase 43.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RPT-01 | Exportable exec/board report (PDF) with risk trend + MTTR-by-tier + SLA compliance for a selected period | D-02 chart pipeline (verified matplotlib+fpdf2 pattern below); Standard Stack (dependency additions); Common Pitfalls #1 (SLA compliance_pct fake-100 bug), #2 (exception-exclusion gap), #3 (MTTR/SLA have no period parameter today — extension pattern given), #4 (burndown window is "now"-relative, not bounded-historical); Code Examples (chart render, tier-scoped SLA extension, calendar-quarter helper); `export.py`/`reports.py`/`main.py` integration points fully mapped in Architecture Patterns |
| RPT-02 | Role-scoped dashboards (analyst / IT-ops / compliance / leadership), tenant-scoped | Architectural Responsibility Map (frontend-primary); Architecture Patterns (lens composition, existing widget reuse, `useUrlState` precedent); Open Question on onboarding-gate interaction; existing dashboard/nav-items.ts integration points mapped |
| RPT-03 | Compliance view mapping findings to framework controls (SOC 2 / ISO 27001 / PCI DSS / NIST CSF) | D-09 authoritative control catalog (full table below, cited); Don't Hand-Roll (catalog-as-data, not per-tenant config engine); Architecture Patterns (compute-metrics-once-then-evaluate-catalog pattern); Common Pitfalls #1/#2 (zero-denominator + exception-exclusion, directly threaten D-13's "Not yet measured" requirement); `coverage/service.py`/`cspm/service.py` shape precedents mapped |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

| Directive | Source | Relevance to Phase 43 |
|-----------|--------|------------------------|
| Frontend stack: Next.js 15 App Router + React 19 + TS 5.5 + Tailwind 3.4 | CLAUDE.md "Codebase conventions" | RPT-02/RPT-03 frontend work must stay on this stack — no new framework/library for the dashboard lens switcher or `/dashboard/compliance` page. |
| Backend stack: FastAPI + Postgres + Redis; state in Redis, not in-process dicts | CLAUDE.md "Codebase conventions" | RPT-03's catalog is **code, not a DB table** (D-09) — this is consistent with the constraint (no new stateful store needed); the catalog module ships as a plain Python data structure. |
| Deployment: Docker Compose, nginx in front of frontend/backend | CLAUDE.md "Codebase conventions"; STATE.md "single-VM Docker Compose... no new infra" | D-02's new `matplotlib` dependency must work in the existing `python:3.12-slim` image with no new infra service — **verified compatible, no Dockerfile/apt changes needed** (see Environment Availability). |
| `sketch-findings-getvul` skill governs all UI work | CLAUDE.md "Skills" | RPT-02 (dashboard lenses) and RPT-03 (`/dashboard/compliance`) are UI phases — 43-UI-SPEC.md has already fully synthesized this skill's 7 reference files into a locked design contract. Research defers to that document for all visual/copy/interaction decisions; this file does not re-derive them. |
| Don't ship a screen without empty/loading/error states | CLAUDE.md "What NOT to do" | Directly load-bearing for RPT-03's "Not yet measured" state (see Common Pitfalls #1) and RPT-02's per-lens no-data tiles — already fully specified in 43-UI-SPEC.md's "UI Considerations," but the *backend* must supply the right null-vs-zero signal for those states to render correctly (this is where the pitfalls below bite). |
| Don't substitute fonts (Inter + JetBrains Mono locked) | CLAUDE.md "What NOT to do" | Applies to the web UI (RPT-02/03) only. The PDF (RPT-01) is explicitly a *separate* rendering surface using Helvetica (fpdf2's built-in font, matching the existing `export.py` convention) — 43-UI-SPEC.md already codifies this "two palettes, two font stories" split. Matplotlib chart text uses its own bundled DejaVu Sans (verified) — this is fine since chart images are visually distinct print elements, not UI text; no cross-contamination of the locked web font pair. |
| Don't pick hex colors freehand | CLAUDE.md "What NOT to do" | Web UI: use `foundation.md` CSS variables (already codified in 43-UI-SPEC.md). PDF chart colors: use the tenant's own `branding` JSONB colors (existing precedent) plus the print-safe light-mode severity hexes 43-UI-SPEC.md already specifies (`#DC2626`/`#EA580C`/`#B45309` etc.) — never the dark-theme hex values. |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| RPT-01 period selection UI (presets + custom range) | Browser / Client | — | Pure form state in the export dialog; mirrors Phase 42's `scope-window-controls.tsx` (plain component state, not `useUrlState` — a dialog, not a page). |
| RPT-01 chart rendering (trend line, MTTR bars, SLA gauge) | API / Backend | — | Must happen server-side (D-02) — fpdf2 cannot render React/recharts; matplotlib runs inside the same FastAPI process that already builds the PDF. |
| RPT-01 PDF assembly + branding | API / Backend | — | Extends `export.py`'s existing fpdf2 codepath (D-01) — no browser involvement beyond triggering the download. |
| RPT-01 scheduled delivery (cadence, SMTP) | API / Backend | — | Extends `reports.py`'s existing in-process asyncio scheduler tick (`run_due_reports`) — no new infra service (STATE.md hard constraint). |
| RPT-02 lens selection + persistence | Browser / Client | — | D-05 explicitly locks this to URL param + localStorage, no backend column. |
| RPT-02 widget data (trend/MTTR/SLA/stats) | API / Backend | Browser (rendering only) | All values come from existing/extended read endpoints (`/analytics/overview`, a new or reused MTTR/SLA read path); the browser only composes and renders what the lens dictates. |
| RPT-03 control catalog (IDs, text, metric mapping, thresholds) | API / Backend | — | D-09: "built-in, version-controlled... shipped in code" — lives in a backend Python module, not a database table, not the frontend. |
| RPT-03 control status evaluation (pass/partial/fail/not-measured) | API / Backend | — | Deterministic threshold math over already-computed metrics (D-13) — belongs server-side so the catalog + the numbers it judges stay co-located and auditable in one place. |
| RPT-03 control-card grid rendering | Browser / Client | — | Presentation only; the browser never re-derives a status, it renders what the backend returns. |
| Database / Storage | — (not primary for RPT-03) | Read-only source for existing tables | No new tables/migrations required anywhere in this phase — `ScheduledReport.sections`/`.filters` are already-flexible JSONB, and the compliance catalog is code, not schema. This is a notable deviation from the "new feature = new table" default and should not be second-guessed into one. |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `matplotlib` | `>=3.9` (latest verified on PyPI: **3.11.1**, requires Python `>=3.11` — compatible with backend's `>=3.12`) `[VERIFIED: PyPI registry + hands-on scratch-venv render test]` | Server-side chart rendering (trend line, MTTR grouped bars, SLA bar/gauge) to raster PNG for PDF embedding | The de facto standard for headless server-side chart generation in Python; fpdf2's **own official documentation** uses matplotlib as its worked example for chart embedding (`py-pdf.github.io/fpdf2/Maths.html`), so this is not an outside choice, it's the path the PDF library itself documents. |
| `fpdf2` | already present, `>=2.8` pinned, currently resolves to **2.8.8** `[VERIFIED: pip show fpdf2 in backend/.venv]` | PDF assembly + image embedding | Already the project's PDF engine (D-01 extends it, doesn't replace it). No version bump required — `pdf.image()` already accepts `bytes` / `io.BytesIO` / `PIL.Image` / file path / `numpy.ndarray` inputs in the installed version. |
| `Pillow` | **already installed transitively** (currently **12.3.0**), recommend declaring explicitly as `Pillow>=10.0` for supply-chain hygiene | Image decoding inside `fpdf2.image()` when embedding the PNG | **Correction to CONTEXT.md's premise:** Pillow is not a new dependency. `pip show fpdf2` shows `Requires: defusedxml, fonttools, Pillow`, and the PyPI registry confirms `fpdf2`'s `requires_dist` includes `Pillow!=9.2.*,>=8.3.2` unconditionally (not behind an extra/marker). It is already resolved and installed in `backend/.venv` today. The only reason to add it to `pyproject.toml` explicitly is that the new chart-embedding code will (indirectly, via fpdf2) depend on Pillow's behavior — relying on an *undeclared transitive* dependency for a code path you're actively adding is fragile if fpdf2 ever relaxes that constraint. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `numpy` | arrives transitively via `matplotlib` (do not declare directly) | matplotlib's internal numeric array handling | Never imported directly by application code in the recommended pattern below — `fig.savefig(buf, format="png")` handles PNG encoding via matplotlib's own bundled `_png` C extension, not via numpy/PIL in the calling code. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| matplotlib (Agg) | `plotly` + `kaleido` | Rejected: `kaleido` historically bundles/downloads a headless Chromium-derived renderer for static image export — much heavier Docker image, a documented history of packaging churn between kaleido v0/v1 install steps, and total overkill for 3 simple chart types on a single-VM Compose stack. No official fpdf2 integration precedent. |
| matplotlib (Agg) | Hand-rolled `PIL.ImageDraw` bars/lines | Rejected: reinventing axis scaling, tick labels, legends, and DPI-correct text layout is exactly the "Don't Hand-Roll" trap — matplotlib already solves this correctly and is the library fpdf2's own docs point to. |
| matplotlib (Agg) | `bokeh` + Selenium/geckodriver static export | Rejected: requires a real browser engine + webdriver in the container for static PNG export — the heaviest option, and this project has no existing browser-automation runtime in the backend image. |
| Declaring `Pillow` transitively-only (status quo) | Declaring `Pillow` as a direct dependency | Recommended: the new chart-embedding code is a first-class feature depending on fpdf2's Pillow-based image path; declaring it directly documents that dependency and survives a future fpdf2 version that might make Pillow optional/extra. |

**Installation:**
```bash
# In backend/pyproject.toml, add to [project] dependencies:
#   "matplotlib>=3.9",
#   "Pillow>=10.0",
uv pip install -e ".[dev]"   # or: pip install -e ".[dev]" inside backend/.venv
```

**Version verification (done this session):**
```
$ pip show fpdf2         → Version: 2.8.8, Requires: defusedxml, fonttools, Pillow
$ curl pypi.org/pypi/matplotlib/json → latest 3.11.1, requires_python >=3.11
$ curl pypi.org/pypi/pillow/json     → latest 12.3.0, requires_python >=3.10
$ curl pypi.org/pypi/fpdf2/json      → requires_dist includes 'Pillow!=9.2.*,>=8.3.2' (unconditional)
```
`[VERIFIED: PyPI registry + local pip show, 2026-08-22]`

## Architecture Patterns

### System Architecture Diagram

```
RPT-01 — On-demand export
────────────────────────────────────────────────────────────────────────
[Browser: Export dialog]
  period preset (30d/90d/quarter/1y) or custom [from,to]
  + "also send by email {cadence}" checkbox (D-04)
        │  GET /api/v1/export/summary?format=pdf&sections=...&period params
        ▼
[FastAPI: export_resource() in main.py — extended]
        │
        ├─▶ _collect_summary_data()  (existing, untouched: vulns/assets/top-hosts/tickets)
        │
        ├─▶ get_scoped_trend_series(start,end) + detect_version_boundaries()   [analytics/service.py, Phase 42]
        ├─▶ get_burndown_rate(days=...)                                        [analytics/service.py, Phase 42]
        ├─▶ get_mttr_by_tier(tenant_id)              ⚠ no period param today   [vulnerabilities/service.py, Phase 36]
        ├─▶ get_sla_metrics(tenant_id)                ⚠ no period param,        [sla_service.py, Phase 36]
        │                                               ⚠ fake-100 on empty,
        │                                               ⚠ no exception-exclusion
        │                                               (see Common Pitfalls #1-3)
        │
        ▼
[NEW: chart-render step]  Figure + FigureCanvasAgg (no pyplot) → io.BytesIO PNG   ×3 (trend, MTTR, SLA)
        ▼
[export.py: generate_executive_summary_pdf()  — extended]
   existing tables/sections  +  3 new pdf.image(buf, w=180) sections
        ▼
[StreamingResponse: application/pdf]  ──or──  [ScheduledReport → run_due_reports() → SMTP attach]  (D-04, existing asyncio scheduler tick)


RPT-02 — Dashboard lenses
────────────────────────────────────────────────────────────────────────
[Browser: /dashboard]
  useUrlState('lens', [...], 'analyst')  ──▶  4-segment switcher
        │
        ├─ analyst / it-ops (unchanged) ──▶ Hero + StatStripWired + ActivityRail + Top5Card
        │                                    (existing useStats() hook, byte-identical)
        │
        └─ leadership / compliance ──▶ NEW top strip (Export CTA) + TrendSection (reused)
                                        + NEW MttrByTierTile + NEW SlaComplianceTile
                                        + NEW FrameworkPostureStrip
                                             │
                                             ▼
                                   useAnalytics() [existing] + NEW hook(s) hitting
                                   GET /vulnerabilities/mttr/by-tier [existing route]
                                   + a small SLA read (existing or new route)
                                   + GET /api/v1/compliance/overview  (RPT-03's endpoint, reused)


RPT-03 — Compliance page
────────────────────────────────────────────────────────────────────────
[Browser: /dashboard/compliance]
        │  GET /api/v1/compliance/overview   (require_viewer, tenant-scoped)
        ▼
[NEW: compliance/router.py]
        ▼
[NEW: compliance/service.py]
   Step 1 — compute each underlying metric ONCE:
     coverage_pct           ← coverage/service.py::get_coverage_summary()      [Phase 41, reused as-is]
     sla_compliance_pct     ← sla_service.get_sla_metrics()                    [Phase 36, zero-denom guarded]
     critical_sla_health_pct← analytics/service.py::get_aging_distribution()   [Phase 42, tier-bucketed, reused]
     mttr_by_tier           ← vulnerabilities/service.py::get_mttr_by_tier()   [Phase 36, reused as-is]
   Step 2 — evaluate the built-in catalog (compliance/catalog.py, pure data + pure function):
     for each of ~11 (framework, control) rows → look up its metric_key →
     apply thresholds → PASS / PARTIAL / FAIL / NOT_MEASURED
        ▼
[Pydantic response: per-framework list of control-status rows]
        ▼
[Browser: control-card grid, grouped by framework]  (43-UI-SPEC.md layout)
```

### Recommended Project Structure

```
backend/app/
├── export.py                 # EXTEND: new chart-render helper + 3 new PDF sections (D-01/D-02)
├── reports.py                 # EXTEND: _send_report's `filters["sections"]` default list grows additively (D-04)
├── main.py                    # EXTEND: export_resource() query params grow (period preset/from/to); scheduled-report body accepts the same
├── analytics/
│   └── service.py             # UNCHANGED — called directly, no HTTP round-trip (D-01a)
├── vulnerabilities/
│   ├── service.py             # UNCHANGED (reused) — get_mttr_by_tier
│   └── sla_service.py         # LIKELY EXTEND — add optional (start,end)/severity params to get_sla_metrics
│                               #   (see Common Pitfalls/Code Examples — additive, not a re-derivation)
└── compliance/                # NEW package, mirrors coverage/ and analytics/ shape
    ├── __init__.py
    ├── catalog.py              # NEW — the D-09 built-in curated catalog: pure data (frameworks → controls → metric_key → thresholds)
    ├── service.py              # NEW — compute the ~5 underlying metrics once, evaluate catalog against them (D-13)
    ├── schemas.py              # NEW — Pydantic response models (mirrors coverage/schemas.py conventions)
    └── router.py                # NEW — GET /overview (require_viewer), mirrors coverage/router.py / analytics/router.py exactly

frontend/src/
├── app/(authed)/dashboard/
│   ├── page.tsx                # EXTEND: lens switcher + conditional widget composition (D-05/D-06)
│   └── compliance/
│       └── page.tsx            # NEW — mirrors coverage/page.tsx and analytics/page.tsx composition (ErrorBoundary > Suspense > Inner)
├── components/
│   ├── dashboard/
│   │   ├── lens-switcher.tsx    # NEW
│   │   ├── leadership-hero.tsx  # NEW — the Export-CTA top strip that replaces Hero for the leadership lens
│   │   ├── mttr-by-tier-tile.tsx    # NEW
│   │   ├── sla-compliance-tile.tsx  # NEW
│   │   └── framework-posture-strip.tsx  # NEW — shared between the compliance lens (compact) and /dashboard/compliance (full)
│   └── compliance/
│       └── control-card.tsx     # NEW
└── lib/queries/
    └── use-compliance.ts        # NEW — GET /api/v1/compliance/overview, mirrors use-analytics.ts / use-coverage-summary.ts shape
```

### Pattern 1: Object-oriented matplotlib, never `pyplot`, in a web request context
**What:** Construct `matplotlib.figure.Figure` directly and drive it with `matplotlib.backends.backend_agg.FigureCanvasAgg`; never `import matplotlib.pyplot`.
**When to use:** Any chart rendered inside a FastAPI request/response cycle (or the scheduler's `_send_report`).
**Why:** `pyplot` keeps a global mutable figure registry that is explicitly documented as unsafe to touch from multiple threads/requests; the object-oriented `Figure`+`FigureCanvasAgg` path sidesteps all shared global state (`[VERIFIED: hands-on scratch-venv test, cross-referenced via WebSearch against matplotlib's own thread-safety guidance and community reports]`).
**Example (verified working end-to-end this session — headless, `DISPLAY` unset):**
```python
# Source: verified in a throwaway venv this session; pattern confirmed against
# the official fpdf2 docs (py-pdf.github.io/fpdf2/Maths.html), simplified —
# fig.savefig(..., format="png") avoids the doc's extra Image.fromarray() step.
import io
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg

def render_mttr_by_tier_chart(tiers: list[str], days: list[float], colors: list[str]) -> io.BytesIO:
    fig = Figure(figsize=(7.2, 4.0), dpi=200)   # 7.2in ≈ 183mm content width; dpi=200 → crisp print
    ax = fig.add_subplot(111)
    ax.bar(tiers, days, color=colors)
    ax.set_ylabel("MTTR (days)")
    ax.set_title("MTTR by Risk Tier")
    fig.tight_layout()

    canvas = FigureCanvasAgg(fig)   # never FigureCanvas() from pyplot
    canvas.draw()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200)
    buf.seek(0)
    return buf

# ... inside generate_executive_summary_pdf():
buf = render_mttr_by_tier_chart(["Critical", "High", "Moderate"], [4.2, 12.8, 41.0],
                                  ["#DC2626", "#EA580C", "#B45309"])  # print-safe light-mode hexes, 43-UI-SPEC.md
pdf.image(buf, w=180)   # fpdf2 accepts a BytesIO directly — no temp file, no manual PIL conversion needed
```
Measured (this session, warm cache): ~35-55ms/chart after the one-time font-cache build (~230ms, happens once per fresh container on first use — not per request; the container's writable `$HOME` from the existing `useradd --create-home` Dockerfile line already satisfies matplotlib's font-cache write requirement).

### Pattern 2: Compute each RPT-03 metric once, then evaluate the catalog as pure data
**What:** `compliance/service.py` runs ~5 DB-backed metric computations (coverage %, tenant-wide SLA compliance %, critical/high-tier SLA health %, MTTR-by-tier, open-critical count) exactly once per request; `compliance/catalog.py` is a **pure function over those already-computed values** — it issues zero additional queries no matter how many controls are in the catalog (~11 across 4 frameworks today).
**When to use:** RPT-03's `/api/v1/compliance/overview` endpoint.
**Why:** Several catalog controls across different frameworks naturally evidence off the *same* underlying metric (see the D-09 catalog table below — coverage % alone evidences one control in each of SOC 2, ISO, PCI, and NIST). Evaluating the catalog as N independent DB-querying functions would mean the same query runs 3-4 times per request for no reason.
**Example:**
```python
# backend/app/compliance/catalog.py — NEW, pure data + pure function, no DB access.
from dataclasses import dataclass

@dataclass(frozen=True)
class ControlDef:
    framework: str       # "soc2" | "iso27001" | "pci_dss" | "nist_csf"
    control_id: str      # e.g. "CC7.1", "A.8.8", "6.3.3", "ID.RA-01"
    title: str            # short paraphrased title (see D-09 table — verbatim only for NIST)
    metric_key: str       # one of the ~5 keys service.py computes
    thresholds: dict[str, float]  # {"pass": 90, "partial": 50} — see per-control notes below

CATALOG: list[ControlDef] = [
    ControlDef("soc2", "CC7.1", "Vulnerability detection & monitoring", "coverage_pct", {"pass": 90, "partial": 50}),
    ControlDef("pci_dss", "11.3.1.1", "Critical/high vulnerabilities resolved per risk-based timeframe",
               "critical_sla_health_pct", {"pass": 95, "partial": 80}),
    # ... full table below
]

def evaluate_catalog(metrics: dict[str, float | None]) -> list[dict]:
    """Pure function: no I/O. `metrics[key] is None` means the denominator was
    zero — MUST short-circuit to NOT_MEASURED before any threshold compare
    (Common Pitfall #1)."""
    results = []
    for c in CATALOG:
        value = metrics.get(c.metric_key)
        if value is None:
            status = "not_measured"
        elif value >= c.thresholds["pass"]:
            status = "pass"
        elif value >= c.thresholds["partial"]:
            status = "partial"
        else:
            status = "fail"
        results.append({"framework": c.framework, "control_id": c.control_id, "title": c.title,
                         "metric_key": c.metric_key, "value": value, "status": status})
    return results
```

### Pattern 3: Reuse `coverage/service.py`'s zero-denominator discipline as the model to copy
**What:** `get_coverage_summary()` already solves exactly the "don't fake a number when there's no data" problem RPT-03 needs (`coverage_pct: int | None`, `None` when `total == 0`; separate `has_authoritative_inventory`/`has_scanner_connector` booleans distinguish *which* empty-state branch applies).
**When to use:** As the direct model for `compliance/service.py`'s own zero-denominator guards, and directly reusable for the "no scanner connected" vs. "no inventory source" empty-state branching 43-UI-SPEC.md already specifies for `/dashboard/compliance`.
**Why:** Don't re-derive this distinction — `get_coverage_summary()` is already the source of truth for "has this tenant even started scanning."

### Anti-Patterns to Avoid
- **Assuming the RPT-01 period selector scopes every PDF section:** It doesn't, and shouldn't without an explicit decision. Today, `_collect_summary_data`'s existing sections (vulns/assets/top-hosts/tickets) are live point-in-time snapshots with no date dimension at all. Only the 3 *new* sections need period awareness, and even among those, `get_scoped_trend_series` is the only one that natively accepts a bounded `[start, end]` — MTTR-by-tier and SLA-compliance are all-time/trailing-90-day aggregates today (see Common Pitfalls #3). Treat "does this section respect the period selector, and how" as a per-section decision, not a blanket assumption.
- **Reading `get_sla_metrics().compliance_pct` at face value for a threshold check:** See Common Pitfalls #1/#2 below — it silently returns `100.0` on zero data and doesn't exclude active exceptions. Both must be handled before this value reaches a pass/fail gate.
- **Quoting ISO 27001 or PCI DSS control text verbatim in the shipped catalog:** Both are copyrighted standards bodies; reference control IDs and a paraphrase of intent (see D-09 table's "Reproduction" column). NIST CSF 2.0 text is public domain and safe to quote verbatim.
- **Building the compliance catalog as N independent metric-fetching functions:** Defeats Pattern 2 above and needlessly multiplies DB round-trips as the catalog grows.
- **Treating the lens switcher and RBAC role as related:** D-05 is explicit and the codebase confirms it — `User.role` (owner/admin/analyst/viewer, `backend/app/tenants/models.py`) is a plain string column with zero relationship to the four RPT-02 personas. Do not gate lens availability on `role`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Chart rasterization for the PDF | A hand-rolled `PIL.ImageDraw` bar/line renderer | `matplotlib` (`Figure`+`FigureCanvasAgg`) | Axis scaling, tick labels, legends, DPI-correct text are already solved; fpdf2's own docs point here. |
| PNG embedding into the PDF | Manual PNG byte-stream parsing | `pdf.image(buf, w=...)` (fpdf2's existing, already-installed capability) | fpdf2 already accepts `bytes`/`BytesIO`/`PIL.Image`/path/`ndarray` — verified this session; no custom embedding code needed. |
| Compliance-framework control text | Hand-transcribing full standard documents into the codebase | The curated, cited D-09 catalog below (IDs + paraphrase for copyrighted frameworks, verbatim only for NIST) | ISO/PCI/AICPA text is licensed; a from-scratch transcription risks both inaccuracy and a licensing problem. Citing IDs + a defensible paraphrase is the standard approach compliance-tooling vendors use. |
| Per-tenant compliance-catalog configuration engine | A rules/config UI for toggling controls or thresholds | The static, in-code `catalog.py` (D-09) | Explicitly out of scope this phase (Deferred Ideas) — building it now is scope creep the user already declined. |
| Calendar-quarter date math | Nothing existing to reuse — **flagged as new logic, see Open Questions** | Plain date arithmetic (`date_trunc('quarter', ...)`-equivalent in Python) if "Last quarter" means a real calendar quarter | No existing precedent in this codebase (`grep -rn "quarter"` returns zero hits in both `backend/app` and `frontend/src`) — this is genuinely new, not a re-derivation of something that exists. |

**Key insight:** The overwhelming majority of Phase 43's surface area is *composition* of already-correct Phase 36/42 code. The two places genuine new logic is warranted — chart rasterization and the control catalog — both have a clear, narrow, well-precedented library/pattern to reach for; resist the temptation to hand-build either.

## Common Pitfalls

### Pitfall 1: `get_sla_metrics().compliance_pct` fakes a 100% score on zero data
**What goes wrong:** A brand-new tenant (or any tenant with zero REMEDIATED findings in the trailing 90 days) will show `compliance_pct: 100.0` — not `null`/`None` — from `sla_service.py::get_sla_metrics()`. If RPT-03's catalog evaluator naively applies `value >= 95 → pass`, a tenant with **no remediation history at all** will render a confident "PASS — 100% compliant" control card, which is precisely the false-positive/misleading-data failure mode 43-UI-SPEC.md's "Not yet measured" state exists to prevent (it explicitly calls out the *opposite* case — never render fail on absent data — but the same principle cuts both ways: never render a fabricated pass either).
**Why it happens:** `backend/app/vulnerabilities/sla_service.py` line ~191: `compliance_pct = round(...) if remediated_total > 0 else 100.0` — a hardcoded fallback, not a null.
**How to avoid:** The catalog evaluator (or a thin wrapper around `get_sla_metrics()`) must check `remediated_total == 0` **before** trusting `compliance_pct`, and treat that case as `not_measured` regardless of the number returned. `remediated_total` is already in the function's return dict — no backend change needed to detect this, only correct consumption.
**Warning signs:** A freshly-seeded/demo tenant showing 100% SLA compliance and all-pass framework controls before any remediation has ever happened.

### Pitfall 2: `get_sla_metrics()` does not exclude actively-excepted findings — inconsistent with the rest of the same PDF
**What goes wrong:** `export.py::_collect_summary_data`'s `open_filter` already includes `~active_exception_subquery(tenant_id, now)` (verified — Phase 39/EXC-02's exclusion predicate), and Phase 42's `analytics/service.py::_open_backlog_conditions` does too. But `sla_service.py::get_sla_metrics()`'s five queries (`open_with_sla`, `breached`, `at_risk`, `remediated_total`, `remediated_within_sla`, `breach_by_sev_q`) reference **no exception exclusion at all** — confirmed by direct read, zero references to `app.exceptions.service` anywhere in that file. A finding under an active accepted-risk exception (EXC-02: "excluded from active queues, SLA timers, and dashboards until expiry") will still count against `breached`/`compliance_pct` here.
**Why it happens:** `sla_service.py` predates Phase 39 (Exception & Risk-Acceptance Workflow); the exclusion predicate was retrofitted into the newer `analytics/service.py` (Phase 42) but never back-ported to this older module.
**How to avoid:** Either (a) add an additive, optional exception-exclusion parameter to `get_sla_metrics()` mirroring `_open_backlog_conditions`'s shape (this is parameterizing an existing function, not re-deriving the SLA algorithm — consistent with D-01a's "call directly, never re-derive"), or (b) explicitly and visibly accept the discrepancy if the team decides a historical/trailing metric shouldn't retroactively exclude exceptions — but this should be a stated decision, not a silent gap, given the same PDF's other sections already apply the opposite rule.
**Warning signs:** A tenant with several accepted-risk exceptions on breached findings sees a *worse* SLA-compliance number in the new PDF section than the vuln-overview section (which already excludes those findings) would suggest, and a worse number than the Vulnerabilities list UI shows for the same findings.

### Pitfall 3: MTTR-by-tier and SLA-compliance have no period parameter today — the D-03 selector doesn't reach them for free
**What goes wrong:** `get_mttr_by_tier(db, tenant_id)` (Phase 36) aggregates `RemediationEvent` with **no date filter at all** — it's an all-time average per tier. `get_sla_metrics(db, tenant_id)` has a **hardcoded** trailing-90-day window baked into its `compliance_pct` calculation (`ninety_days_ago = now - timedelta(days=90)`), not a caller-supplied range. Only `analytics/service.py`'s trend/burndown functions actually accept a period. If the planner assumes "the period selector governs the whole PDF," MTTR-by-tier and SLA-compliance numbers will silently stay identical regardless of which preset/custom range the user picks.
**Why it happens:** Both functions were built for Phase 36's dashboard-tile use case (a single current snapshot), not for Phase 43's report-over-a-selected-window use case; they were never designed to be period-scoped.
**How to avoid:** This is genuinely extensible — `RemediationEvent` already has a `remediated_at: DateTime` column (confirmed in the model), so adding an optional `(start, end)` filter to `get_mttr_by_tier` is a one-line additive `.where(RemediationEvent.remediated_at.between(start, end))`. For SLA compliance, the codebase already has a **tier-capable, live alternative**: `analytics/service.py::get_aging_distribution()` returns `within_sla`/`recently_breached`/`long_overdue` counts *bucketed by severity* for the **current open backlog** — a percentage derived from those buckets (e.g. `critical.within_sla / sum(critical.*)`) is a legitimate, already-available, tier-scoped "SLA health" metric that answers a related-but-different question (is the *current* backlog healthy) than `compliance_pct` (were *recently closed* items closed on time). Decide explicitly which question RPT-01's "SLA compliance" section and RPT-03's per-tier controls are answering — don't let the ambiguity resolve itself by accident (see Open Questions).
**Warning signs:** Switching the PDF's period preset from "30 days" to "1 year" changes the trend chart but leaves the MTTR-by-tier table and SLA-compliance number completely unchanged.

### Pitfall 4: Burndown's "days" window is trailing-from-now, not a bounded historical [start, end]
**What goes wrong:** `get_analytics_overview` computes `span_days = max((range_end - range_start).days, 1)` and passes that into `get_burndown_rate(days=span_days, ...)`, but `get_burndown_rate` → `get_vuln_trends` internally computes `start = now - timedelta(days=days)` — i.e. it always ends at **the actual current moment**, never at a caller-supplied historical `end` date. This is invisible for RPT-01's presets (30d/90d/quarter/1y all naturally end "now"), but if a custom historical range is picked (e.g., a `[Jan 1, Mar 31]` window in the past for a retrospective board review), the trend chart would correctly show that historical window while the burndown tile would silently report a *different*, current-moment-relative velocity — two sections of the same report describing different time windows without saying so.
**Why it happens:** `get_vuln_trends`/`get_burndown_rate` were built for "how are we trending right now," not for arbitrary historical reporting windows — this is a pre-existing Phase 42 characteristic, not a Phase 43 bug, but Phase 43 is the first consumer that might pick a genuinely historical (not-ending-at-now) custom range.
**How to avoid:** Either (a) restrict RPT-01's custom range to always end "today" (simplest — matches every existing preset's behavior and sidesteps the mismatch entirely), or (b) if a fully historical range must be supported, flag burndown as "not available for historical periods" in that case rather than silently showing a mismatched number.
**Warning signs:** A custom-range PDF for a period ending months in the past shows a burndown velocity that doesn't visually match the trend chart's own slope over that same window.

### Pitfall 5: matplotlib + `pyplot` in a shared-process web server is a documented thread-safety hazard
**What goes wrong:** If a future contributor "simplifies" the chart code to `import matplotlib.pyplot as plt; plt.figure(); plt.bar(...)`, this reintroduces global mutable state (the pyplot figure registry) that is unsafe under concurrent access and can leak figure objects across requests.
**Why it happens:** `pyplot` is the more commonly-tutorialized matplotlib API (most blog posts/StackOverflow answers use it), so it's an easy trap to fall into during a later edit even if the initial implementation is correct.
**How to avoid:** Use only `Figure()` + `FigureCanvasAgg()` (Pattern 1 above) — never import `matplotlib.pyplot` anywhere in the backend. Consider a lint/review note or a code comment at the top of the chart-render helper making this explicit, mirroring how `analytics/service.py` already documents its own "HTTP-agnostic, D-16" convention inline.
**Warning signs:** Intermittent, hard-to-reproduce chart corruption or crashes under concurrent PDF-generation requests; `[Bug]: ... crashes ... outside the main thread` is a real, cited upstream matplotlib issue class for exactly this misuse.

### Pitfall 6: PDF generation (now with charts) is synchronous CPU-bound work inside an `async def` route
**What goes wrong:** `generate_executive_summary_pdf` is declared `async def` but does all of its fpdf2 drawing synchronously inline (no `await asyncio.to_thread(...)`) — this is the **existing** pattern, and it blocks the single event-loop thread of whichever Uvicorn worker handles the request for the full duration of PDF assembly. Adding matplotlib chart rendering (even at the verified ~35-260ms/chart) makes this measurably slower and extends how long that worker is unresponsive to any other request (health checks, other tenants' API calls) during generation.
**Why it happens:** This is consistent with the codebase's existing style (the current, chart-free PDF generation has the same characteristic) — it isn't a regression Phase 43 introduces, but Phase 43 makes the existing tradeoff more expensive.
**How to avoid:** Not necessarily a blocker — for a low-frequency, user-initiated "export board report" action on a single-VM Compose deployment, a sub-second block is likely acceptable and consistent with existing behavior. If the team wants to be defensive, wrap the chart-render-and-build step in `await asyncio.to_thread(...)` (Python 3.9+, available on this project's `>=3.12` floor) — this is exactly the scenario where Pattern 1's "no pyplot, no global state" discipline becomes load-bearing, since `asyncio.to_thread` genuinely runs the work on a separate thread.
**Warning signs:** Other API requests (or the scheduler's next tick) visibly stalling while a board PDF with several charts is being generated.

### Pitfall 7: Reproducing ISO/PCI/AICPA control text verbatim is a licensing risk, not just a style choice
**What goes wrong:** ISO/IEC copyrights its standards outright (sells the documents); PCI SSC and AICPA both similarly restrict reproduction of their standard text (AICPA explicitly directs reproduction requests to `copyright@aicpa.org`). Shipping verbatim paragraph-length control text from any of these three inside an open-source-adjacent product's codebase is a real (if commonly under-enforced) licensing exposure.
**Why it happens:** It's the path of least resistance when copy-pasting from a compliance blog that itself quotes the standard closely.
**How to avoid:** For SOC 2 / ISO 27001 / PCI DSS: cite the control ID and a short, independently-worded paraphrase of intent (the D-09 table below models this). For NIST CSF 2.0 only: verbatim reproduction is safe (U.S. public domain, 17 U.S.C. §105 — verified this session).
**Warning signs:** A catalog entry that reads like a direct quote (matches a standard's sentence structure closely) for any of the three copyrighted frameworks.

## Code Examples

### D-09: The authoritative framework-control catalog (verified this session)

**Confidence and reproduction note:** every ID below is cross-sourced against 2+ independent references. Reproduction column states whether the *exact wording* can ship in the codebase (`verbatim OK`) or must be paraphrased (`paraphrase only`).

| Framework | Control ID | Paraphrased intent (safe to ship) | Reproduction | Recommended `metric_key` | Suggested thresholds | Sources |
|-----------|-----------|-------------------------------------|---------------|---------------------------|------------------------|---------|
| SOC 2 (AICPA TSC 2017, rev. 2022 POF) | **CC7.1** | Detection/monitoring procedures identify new vulnerabilities and vulnerability-introducing config changes. | paraphrase only — AICPA copyrighted | `coverage_pct` | pass ≥90, partial ≥50 | `[CITED: docs.alertlogic.com SOC2-CC-7.1; cross-referenced against multiple compliance-vendor summaries]` |
| SOC 2 *(optional secondary — weaker fit, see Open Questions)* | **CC7.2** | Monitoring of system components/operations for anomalies, analyzed to identify security events. | paraphrase only | `coverage_pct` (same metric, broader control) | pass ≥90, partial ≥50 | `[CITED: cyberday.ai CC7.2 summary; xorabyte.com CC7 overview]` |
| ISO/IEC 27001:2022 Annex A | **A.8.8** | "Management of technical vulnerabilities" — obtain vulnerability info, evaluate exposure, take appropriate measures. | paraphrase only — ISO copyrighted | `critical_sla_health_pct` | pass ≥90, partial ≥70 | `[CITED: isms.online Annex A 8.8; hightable.io A.8.8 explainer]` |
| ISO/IEC 27001:2022 Annex A | **A.8.9** | "Configuration management" — establish, document, monitor, review configurations. | paraphrase only | `coverage_pct` | pass ≥90, partial ≥50 | `[CITED: dataguard.com Annex A controls list; scrut.io ISO 27001 controls]` |
| PCI DSS **v4.0.1** (v4.0 retired 2024-12-31 — verified current version) | **6.3.1** | Vulnerabilities are identified via an ongoing process and risk-ranked (at minimum, high-risk/critical flagged). | paraphrase only — PCI SSC copyrighted | `has_active_scanning` (boolean existence check, not a %) | pass = ≥1 non-stale connector | `[CITED: pcisecuritystandards.org FAQ on risk rankings; trustedsec.com PCI vuln-mgmt series]` |
| PCI DSS v4.0.1 | **6.3.3** | Critical/high security patches installed within 1 month of release; others within an appropriate documented timeframe. | paraphrase only | `critical_sla_health_pct` | pass ≥95, partial ≥80 | `[CITED: riskassociates.com PCI v4.0.1 vuln-fix rules; tuxcare.com PCI patching requirements]` |
| PCI DSS v4.0.1 | **11.3.1** | Internal vulnerability scans performed at least quarterly (and after significant change). | paraphrase only | `coverage_pct` (+ per-connector staleness from Coverage) | pass = ≥1 non-stale connector | `[CITED: tenable docs.tenable.com PCI Control Objective 3; edgescan.com PCI v4.0.1 guide]` |
| PCI DSS v4.0.1 | **11.3.1.1** | High-risk/critical vulnerabilities resolved per a risk-based timeframe (post-v4.0.1: a documented Targeted Risk Analysis). **Recommended primary evidencing control for "SLA compliance," more precise than 6.3.3 for this purpose** (see Open Questions). | paraphrase only | `critical_sla_health_pct` | pass ≥95, partial ≥80 | `[CITED: riskassociates.com; cybeats.com 2025 SBOM/6.3.2/11.3.1.1 deadline guide]` |
| NIST CSF **2.0** (Feb 2024) | **ID.RA-01** | "Vulnerabilities in assets are identified, validated, and recorded." | **verbatim OK — U.S. public domain** | `coverage_pct` | pass ≥90, partial ≥50 | `[VERIFIED: csf.tools ID.RA reference page; nist.gov CSF 2.0 Core PDF]` |
| NIST CSF 2.0 | **ID.RA-06** | "Risk responses are chosen, prioritized, planned, tracked, and communicated." | verbatim OK | `sla_compliance_pct` (tenant-wide, zero-denom guarded) | pass ≥90, partial ≥50 | `[VERIFIED: csf.tools ID.RA reference page]` |
| NIST CSF 2.0 | **PR.PS-02** | "Software is maintained, replaced, and removed commensurate with risk." | verbatim OK | `mttr_by_tier` (pass if each tier's avg MTTR ≤ that tier's own configured SLA-day target) | see note below | `[VERIFIED: csf.tools PR.PS reference page]` |
| NIST CSF 2.0 *(optional 4th)* | **ID.RA-08** | "Processes for receiving, analyzing, and responding to vulnerability disclosures are established." | verbatim OK | existence check (Phase 40 alerting configured) — weak numeric fit, better as boolean | pass = alerting_config enabled | `[VERIFIED: csf.tools ID.RA reference page]` |

**PR.PS-02 threshold note:** rather than an arbitrary percentage, this control is naturally evidenced by comparing each tier's *own* `get_mttr_by_tier` average against that *same tenant's own configured* `sla_tier_service.get_tier_policy(tenant)["tier_days"]` value — e.g. pass if `critical.avg_seconds / 86400 <= tier_days["critical"]`. This is a tenant-calibrated threshold rather than a hardcoded percentage, and reuses two functions that already exist with zero new queries.

**Total catalog size:** 10 controls (or 11 with the optional SOC2 CC7.2 / NIST ID.RA-08 additions) across 4 frameworks — within D-12's "all four ship day one" and each framework's "2-5 controls" guidance from D-09.

**Underlying metrics reused (only ~5 distinct computations power the whole catalog):**
| `metric_key` | Backend source | Already period-aware? | Already exception-excluded? | Already zero-denominator-safe? |
|---|---|---|---|---|
| `coverage_pct` | `coverage/service.py::get_coverage_summary` | N/A (live snapshot) | N/A (asset-level, not finding-status) | Yes — `None` on zero denominator `[VERIFIED]` |
| `sla_compliance_pct` | `sla_service.py::get_sla_metrics().compliance_pct` | No (hardcoded trailing 90d) | **No — Pitfall 2** | **No — fakes 100.0, Pitfall 1** |
| `critical_sla_health_pct` (derived) | `analytics/service.py::get_aging_distribution()` buckets | Live snapshot (current backlog) | Yes (`_open_backlog_conditions`) `[VERIFIED]` | Needs a guard: 0-of-0 in a tier should be `None`, not a divide-by-zero or a fake 100 |
| `mttr_by_tier` | `vulnerabilities/service.py::get_mttr_by_tier` | No (all-time) | N/A (post-remediation events) | Yes — `avg_seconds: None` per empty tier `[VERIFIED]` |
| `has_active_scanning` | `coverage/service.py::get_coverage_summary().has_scanner_connector` | N/A | N/A | N/A (already boolean) |

### Extending `get_sla_metrics` with an optional tier/date filter (additive, not a re-derivation)

```python
# backend/app/vulnerabilities/sla_service.py — illustrative additive extension.
# Mirrors the existing function's own query shape; adds two optional params
# with backward-compatible defaults so every existing call site (dashboard
# tiles, etc.) is byte-for-byte unaffected.
async def get_sla_metrics(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    severity: str | None = None,          # NEW, optional — None = tenant-wide (unchanged behavior)
    exclude_exceptions: bool = False,      # NEW, optional — default False preserves existing behavior;
                                            # Pitfall 2 recommends the NEW caller (RPT-01/03) pass True
) -> dict:
    ...
    conditions = [Vulnerability.tenant_id == tenant_id, Vulnerability.status.in_(["OPEN", "IN_PROGRESS"])]
    if severity:
        conditions.append(Vulnerability.severity == severity)
    if exclude_exceptions:
        from app.exceptions.service import active_exception_subquery
        conditions.append(~active_exception_subquery(tenant_id, now))
    ...
```

### Calendar-quarter helper (new logic — no existing precedent, see Don't Hand-Roll)

```python
# NEW — no existing "quarter" logic anywhere in this codebase (verified via
# grep). Only needed if "Last quarter" (D-03) means a real calendar quarter
# rather than a rolling ~90-day window — see Open Questions before building this.
from datetime import date

def last_completed_quarter(today: date) -> tuple[date, date]:
    q = (today.month - 1) // 3 + 1                  # current quarter, 1-4
    first_of_this_q = date(today.year, 3 * (q - 1) + 1, 1)
    end = first_of_this_q - timedelta(days=1)        # last day of previous quarter
    start_month = 3 * ((end.month - 1) // 3) + 1
    start = date(end.year, start_month, 1)
    return start, end
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| PCI DSS v4.0 | PCI DSS **v4.0.1** | 2024-06 published; v4.0 retired 2024-12-31; v4.0.1 the only active version for all 2026 assessments | Same requirement numbers (6.3.1/6.3.3/11.3.1/11.3.1.1), only clarifications — but the catalog and any auditor-facing copy should cite "v4.0.1," not "v4.0," to read as current and credible. |
| PCI DSS "vulnerability management" as one broad control | PCI DSS v4.0.1 formally distinguishes **resolving** (patch/config/removal) from **addressing** (documented risk-based alternative action via a Targeted Risk Analysis) for 11.3.1.1 | v4.0/v4.0.1 restructure | The catalog's 11.3.1.1 paraphrase should reflect "resolved per a risk-based timeframe," not a flat fixed day-count, matching how GetVul's own tier-based SLA windows already work. |
| NIST CSF 1.1's `RS.MI-3` ("newly identified vulnerabilities are mitigated or documented as accepted risks") | Reorganized into CSF 2.0's `ID.RA-06` ("risk responses are chosen, prioritized, planned, tracked, and communicated") and related `ID.RA-07` | CSF 2.0, Feb 2024 | If any team member's prior knowledge cites "RS.MI-3" for vuln remediation tracking, that subcategory ID no longer maps the same way in 2.0 — use `ID.RA-06` instead (verified against the current CSF 2.0 core reference, not the 1.1 mapping). |
| ISO/IEC 27001:2013 Annex A (114 controls, old numbering, e.g. old A.12.6.1) | ISO/IEC 27001:**2022** Annex A (93 controls, 4 themes, A.8.8 is the current vulnerability-management control ID) | 2022 restructure | If any legacy documentation cites an old 2013-numbering control ID, it will not match this catalog — this phase should cite 2022 IDs only, consistent with D-08/D-09's own "A.8.8" framing. |

**Deprecated/outdated:** PCI DSS v3.2.1 (retired March 2024) and PCI DSS v4.0 (retired Dec 2024) — neither should appear as the cited version anywhere in this phase's UI copy or catalog.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|----------------|
| A1 | matplotlib's bundled DejaVu Sans font and Agg backend need zero additional `apt-get` packages on `python:3.12-slim` — **partially verified**: bundled fonts confirmed live in a scratch venv (real verification); the "no apt packages needed on Debian slim specifically" claim rests on WebSearch-cross-referenced community knowledge, not an official matplotlib doc page (matplotlib.org returned HTTP 403 to WebFetch this session). | Standard Stack / Environment Availability | Low — if wrong, the fix is a one-line `apt-get install` addition to the existing Dockerfile; would surface immediately and loudly on the first Docker build, not silently. |
| A2 | The exact numeric thresholds proposed in the D-09 catalog table (pass ≥90/95, partial ≥50/70/80) are reasonable starting points, not sourced from any framework's own official numeric thresholds (the standards themselves are qualitative — "installed within an appropriate timeframe" — not phrased as "X% compliance"). | Code Examples (catalog table) | Medium — an auditor or the tenant's own compliance owner may want different thresholds; D-13 already states "exact thresholds are planner discretion within the catalog," so this is expected to be adjusted, not treated as final. |
| A3 | SOC 2 CC7.2's fit as a genuine "vulnerability management" control is weaker than CC7.1's (it's phrased around anomaly detection broadly, not vulnerabilities specifically) — presented as an optional secondary, not a confident recommendation. | Code Examples (catalog table); Open Questions | Low — worst case, the planner ships SOC 2 with just 1 control (CC7.1), which is still within D-12/D-09's "2-5" *range* language read as an upper bound, and is more honest than stretching CC7.2's fit. |
| A4 | PCI SSC (like AICPA and ISO) restricts verbatim reproduction of PCI DSS text — treated as true by extension of standard industry practice for paid/licensed standards bodies, but not independently confirmed via an explicit PCI SSC copyright-policy citation this session (WebSearch did not surface one directly). | Common Pitfalls #7; D-09 catalog Reproduction column | Low — the recommended behavior (paraphrase, don't quote) is the conservative/safe choice regardless; being wrong here only means the caution was unnecessary, not that anything is broken. |

## Open Questions (RESOLVED)

> All four questions below were resolved by locked plan decisions (43-01..43-04 PLAN.md); retained for provenance.

1. **Does "Last quarter" (D-03) mean a rolling ~90-day window or an actual calendar quarter?**
   - What we know: 43-UI-SPEC.md lists `Last 30 days` / `Last 90 days` / `Last quarter` / `Last year` as four *distinct* presets in the same picker, and D-03's own text frames it as "a board cadence like 'last quarter'" — both suggest a real calendar-quarter concept (otherwise "Last quarter" and "Last 90 days" would be redundant, near-identical options sitting side by side).
   - What's unclear: There is zero existing precedent for calendar-quarter date math anywhere in this codebase (verified via grep — zero hits for "quarter" in both `backend/app` and `frontend/src`), so this is new logic either way; the question is only whether to build it.
   - **RESOLVED** (43-02 Task 3 `last_completed_quarter` helper): Implement "Last quarter" as the most-recently-**completed** calendar quarter (a simple, well-defined date-arithmetic function — sketch given in Code Examples). This matches how a board actually uses the phrase ("Q2's numbers") and avoids a confusing duplicate-feeling preset next to "Last 90 days."

2. **Which underlying "SLA compliance" question does RPT-01's PDF section (and RPT-03's threshold controls) actually answer — historical closure rate, or current backlog health?**
   - What we know: two different, both-legitimate metrics already exist in the codebase (Pitfall 3): `get_sla_metrics().compliance_pct` (trailing-90-day, tenant-wide, "were recently-closed items closed on time") vs. a tier-scoped derivation from `get_aging_distribution()`'s buckets ("is the currently-open backlog within SLA, broken down by tier").
   - What's unclear: D-01a explicitly names `get_sla_metrics`/`compliance_pct` as the RPT-01 source, which answers the historical-closure-rate question — but D-13's own illustrative example ("critical SLA-compliance ≥ 95%") implies a *tier-scoped* number, which `compliance_pct` alone cannot provide without extension.
   - **RESOLVED** (43-01/43-02: RPT-01 PDF uses guarded tenant-wide `compliance_pct`; RPT-03 tier controls use `critical_sla_health_pct` from `get_aging_distribution`): Use `get_sla_metrics().compliance_pct` (tenant-wide, guarded per Pitfall 1/2) for RPT-01's PDF tile, matching D-01a literally. For RPT-03's tier-scoped controls (PCI 6.3.3/11.3.1.1, ISO A.8.8), use the `get_aging_distribution()`-derived `critical_sla_health_pct` instead, since it's tier-capable today with zero backend changes — and label the two surfaces' numbers distinctly in copy ("SLA compliance" vs. "Critical backlog health") so they aren't mistaken for the same measurement if they diverge.

3. **Does the RPT-02 lens switcher render during the existing onboarding empty state?**
   - What we know: `dashboard/page.tsx` currently has a top-level early-return — `if (!stats.isPending && (onboarding === 'no_scanners' || onboarding === 'no_data_yet')) return <OnboardingPanel .../>` — that fires **before** any of Hero/StatStrip/etc. render. 43-UI-SPEC.md fully specifies each lens's own populated/loading/error/no-data states but does not address this pre-existing, page-level onboarding gate's interaction with the new lens switcher.
   - What's unclear: Should a brand-new tenant with zero scanner data see the lens switcher at all (and if they switch to "Leadership," see a leadership-flavored onboarding message), or should the existing onboarding gate simply preempt all lenses uniformly, exactly as it does today?
   - **RESOLVED** (43-04 Task 1: onboarding early-return preserved as the OUTERMOST check, byte-for-byte): Keep the existing onboarding gate as the outermost check, unchanged (byte-for-byte) — the lens switcher only appears once onboarding clears. This is the minimal-risk reading of D-06 ("reconfigure the existing hero... rather than net-new routes") and avoids designing four more onboarding-state variants this phase doesn't otherwise need.

4. **Should SOC 2 ship 1 control (CC7.1 only) or 2 (CC7.1 + CC7.2)?**
   - What we know: CC7.1 is an unambiguous, precise fit ("detection... of new vulnerabilities"). CC7.2 is broader (anomaly detection generally) and its fit to "vulnerability management" specifically is looser than the other three frameworks' second/third controls.
   - What's unclear: D-09/D-12 ask for "2-5 controls" per framework as guidance, but SOC 2's Trust Services Criteria are genuinely more principles-based/less granular than ISO/PCI/NIST, so forcing a 2nd control may reduce catalog credibility rather than improve it.
   - **RESOLVED** (43-01 CATALOG: SOC 2 ships CC7.1; CC7.2 optional per catalog rows): Ship CC7.1 alone if catalog credibility is the priority; add CC7.2 only if the team is comfortable with its broader framing. Flagged explicitly rather than silently picking one.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `matplotlib` (Python package) | D-02 chart rendering | ✗ (not yet in `backend/pyproject.toml` or `.venv`) | — (verified installable: latest 3.11.1, requires Python ≥3.11) | Add to `pyproject.toml`; no fallback needed, this is a normal dependency addition, not an external-service risk |
| `Pillow` (Python package) | fpdf2's image embedding (already used today for the logo) | ✓ (already installed transitively via fpdf2) | 12.3.0 `[VERIFIED: pip show in backend/.venv]` | — |
| `python:3.12-slim` Docker base + existing `apt-get gcc libpq-dev` | Running matplotlib headlessly in the deployed container | ✓ | current Dockerfile, unchanged | No apt-get changes needed — manylinux wheels bundle FreeType/libpng; `[VERIFIED via WebSearch cross-reference, A1 in Assumptions Log]` |
| Writable `$HOME`/matplotlib font cache inside the container | First-use font-cache build (~230ms one-time cost, verified) | ✓ | Dockerfile already does `useradd --create-home` before `USER appuser` | — |
| SMTP configuration (`Tenant.smtp_config`) | D-04 scheduled board-report email delivery | Tenant-dependent, pre-existing feature (not new to this phase) | — | Already has a fallback: `_send_report` only emails `if smtp_cfg and smtp_cfg.get("enabled")`; otherwise the report is still generated and written to `/app/reports` for on-demand download, audited either way |

No missing dependency in this phase blocks execution — `matplotlib` is a standard `pip install` addition with a verified-compatible target environment.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Backend framework | pytest 8.3 + pytest-asyncio 0.24 (`asyncio_mode = "auto"`, session-scoped loop — `backend/pyproject.toml` `[tool.pytest.ini_options]`) |
| Backend config file | `backend/pyproject.toml` (no separate `pytest.ini`) |
| Backend quick run command | `ENCRYPTION_KEY=... JWT_SECRET_KEY=... backend/.venv/bin/pytest tests/test_<file>.py -x` (per-file, not whole-`tests/`-dir — project memory: `getvul-backend-pytest-env`) |
| Frontend framework | Vitest (`frontend/vitest.config.mts`, `npm run test`) + Playwright e2e (`npm run test:e2e`, `e2e/playwright.config.ts`) |
| Frontend quick run command | `npm run test -- <file>.test.tsx` |

### Wave 0 Gap — no existing test coverage for the two files RPT-01 extends
**Verified via direct file listing of `backend/tests/`:** there is **no `test_export.py` and no `test_reports.py`** anywhere in the suite — `export.py` (`generate_executive_summary_pdf`, `_collect_summary_data`, `generate_executive_summary_csv`) and `reports.py` (`ScheduledReport`, `run_due_reports`, `_send_report`, `_is_due`) have **zero existing automated coverage**. This is a real Wave 0 gap, not a hypothetical one — RPT-01 will be the first phase to add tests for these modules at all, not just extending existing ones.

Existing, reusable test coverage for the *data sources* RPT-01/03 consume:
- `backend/tests/test_mttr.py` — covers `get_mttr_by_tier` and the `RemediationEvent`-writing helper; good seed-data pattern to copy for a period-filtered variant.
- `backend/tests/test_sla_service.py` — covers `get_sla_metrics`; the natural place to add zero-denominator and exception-exclusion regression tests (Pitfalls 1/2).
- `backend/tests/test_analytics.py` — covers `get_scoped_trend_series`/`get_burndown_rate`/`get_aging_distribution`; the natural place to add a "critical-tier SLA health" derivation test if that path is built.
- `backend/tests/test_coverage.py` — covers `get_coverage_summary`; reusable as-is for the RPT-03 `coverage_pct` metric, no new coverage test needed for that piece.

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|--------------|
| RPT-01 | PDF generation with 3 new sections produces valid, non-empty PDF bytes with charts embedded | unit | `pytest tests/test_export.py -x` | ❌ Wave 0 — new file |
| RPT-01 | `_collect_summary_data`'s existing `sections` toggle mechanism still works with new keys added (`risk_trend`/`mttr_by_tier`/`sla_compliance`) appended to the default list, byte-compatible with existing scheduled reports | unit | `pytest tests/test_export.py -x` | ❌ Wave 0 |
| RPT-01 | Chart-render helper produces a decodable PNG from `Figure`+`FigureCanvasAgg`, headless (no `DISPLAY`) | unit | `pytest tests/test_export.py -x -k chart` | ❌ Wave 0 |
| RPT-01 | `get_sla_metrics()` (or its extension) returns `None`/a distinguishable "not measured" signal on zero remediation history, not `100.0` treated as real | unit (regression for Pitfall 1) | `pytest tests/test_sla_service.py -x -k zero` | ❌ Wave 0 (new test case in existing file) |
| RPT-01 | Scheduled board report (`ScheduledReport` with new section keys) is picked up by `run_due_reports`/`_is_due` and generates the extended PDF on cadence | integration | `pytest tests/test_reports.py -x` | ❌ Wave 0 — new file |
| RPT-02 | Lens switcher persists via URL param and falls back to `localStorage`; default `analyst` renders the byte-identical existing dashboard | unit/component | `npm run test -- dashboard/page.test.tsx` | ❌ Wave 0 (extend or create) |
| RPT-02 | Leadership/compliance lens widgets (MTTR tile, SLA tile, framework-posture strip) render populated/loading/error/no-data branches per 43-UI-SPEC.md | unit/component | `npm run test -- mttr-by-tier-tile.test.tsx` (and siblings) | ❌ Wave 0 — new files |
| RPT-03 | `evaluate_catalog()` pure function: for each of the ~5 metric keys, `None` input → `not_measured`; boundary values at each threshold produce the correct pass/partial/fail | unit | `pytest tests/test_compliance.py -x` | ❌ Wave 0 — new file |
| RPT-03 | `GET /api/v1/compliance/overview` is tenant-scoped (mirrors `test_tenant_isolation.py`'s cross-tenant-403/404 pattern) and requires `require_viewer` | integration | `pytest tests/test_compliance.py -x -k tenant` | ❌ Wave 0 |
| RPT-03 | `/dashboard/compliance` renders the two-branch empty state (no scanner / no SLA policy) correctly gated on `has_scanner_connector`/zero-denominator signals | component | `npm run test -- compliance/page.test.tsx` | ❌ Wave 0 — new file |

### Sampling Rate
- **Per task commit:** `pytest tests/test_<touched_file>.py -x` (backend) / `npm run test -- <touched>.test.tsx` (frontend) — per-file, matching project memory's documented env-var gotcha.
- **Per wave merge:** full backend suite (`pytest` from `backend/`, with `ENCRYPTION_KEY`/`JWT_SECRET_KEY` set) + full frontend `npm run test`.
- **Phase gate:** full suite green + (if UI changed) the existing Playwright quality gate (`npm run test:e2e`) before `/gsd-verify-work`, per project memory `getvul-local-e2e-perf-gate`.

### Wave 0 Gaps
- [ ] `backend/tests/test_export.py` — new file; covers RPT-01's extended PDF generation, chart embedding, section-toggle compatibility
- [ ] `backend/tests/test_reports.py` — new file; covers RPT-01's scheduled-delivery path with the new section keys
- [ ] `backend/tests/test_compliance.py` — new file; covers RPT-03's catalog evaluator + the new `/api/v1/compliance/overview` endpoint (tenant isolation, RBAC, zero-denominator handling)
- [ ] New test cases inside `backend/tests/test_sla_service.py` — zero-denominator (Pitfall 1) and exception-exclusion (Pitfall 2) regression coverage
- [ ] Frontend: `dashboard/page.test.tsx` extension (or a new lens-specific test file) — lens switcher persistence + per-lens widget composition
- [ ] Frontend: `app/(authed)/dashboard/compliance/page.test.tsx` — new file, mirrors `coverage/page.test.tsx`'s state-branch test structure
- [ ] Framework install: none — pytest/Vitest/Playwright are already fully configured; only new *test files*, not new *test infrastructure*, are needed

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|----------------|---------|---------------------|
| V1 Architecture | Partial | No new trust boundary — RPT-03's catalog is static in-code data (no new attack surface for injection); RPT-01's chart images are generated from the tenant's own already-trusted DB data, never from user-supplied strings rendered as chart labels beyond what already flows through the existing PDF (hostnames/product names — already the case today, unchanged risk profile). |
| V4 Access Control | Yes | New `GET /api/v1/compliance/overview` must use `require_viewer` + inline `tenant_id ==` filtering on every query, mirroring `analytics/router.py`/`coverage/router.py` exactly — never a fetch-then-403 pattern (established codebase convention, verified in both existing routers). |
| V5 Input Validation | Yes | RPT-01's new period-selector query params (preset enum + custom `from`/`to`) must be validated exactly like `analytics/router.py`'s existing `from_`/`to` handling: both-or-neither, `to >= from`, and a server-side span cap mirroring `MAX_ANALYTICS_WINDOW_DAYS` — do not accept an unbounded custom range for the PDF path (a multi-year range would force `get_scoped_trend_series` to scan a proportionally large `DailySnapshot` range). |
| V7 Error Handling / Logging | Yes | Existing `audit(db, user, "export.summary", ...)` call in `main.py` should extend to log which new sections were requested (auditability principle already established project-wide: "every new mutating action... emits a tenant-scoped audit event" — an export is arguably read-only, but the existing code already treats it as audit-worthy; keep that convention for the new sections). |
| V8 Data Protection | Yes (data-accuracy framing, not confidentiality) | The two SLA-metric pitfalls above (fake-100 on empty, missing exception-exclusion) are not confidentiality/injection bugs, but they are **data-integrity** issues on a document whose entire purpose is to be trusted by a CISO/auditor — treat them with the same seriousness as a correctness bug in this ASVS-adjacent sense. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|------------------------|
| IDOR on the new compliance endpoint (tenant A reads tenant B's posture) | Information Disclosure | Inline `tenant_id ==` filter on every query inside `compliance/service.py`, `require_viewer` dependency on the router — copy `coverage/router.py`'s exact shape, already proven correct across two prior phases. |
| DoS via an unbounded custom date range on the PDF export or `/compliance` endpoint | Denial of Service | Reuse `MAX_ANALYTICS_WINDOW_DAYS`-style server-side span cap; the existing `/api/v1/analytics/overview` route already has this exact validated pattern to copy verbatim. |
| A misleading "PASS" on a board/auditor-facing document (data-integrity, not a classic STRIDE category, but material to this phase's entire value proposition) | Repudiation-adjacent / Tampering-by-omission | The zero-denominator guard (Pitfall 1) and exception-exclusion consistency (Pitfall 2) are the mitigations — treat a fabricated compliance number as seriously as a spoofing bug, since the phase's whole purpose is "prove the program is working" to an external-trust audience. |

## Sources

### Primary (HIGH confidence)
- `pip show fpdf2` + PyPI registry JSON for `matplotlib`/`Pillow`/`fpdf2` — run directly this session, 2026-08-22.
- Hands-on verification: a throwaway venv (`python3.12 -m venv`), `pip install matplotlib fpdf2`, headless (`DISPLAY` unset) chart render + fpdf2 embed, timed, cleaned up after — this session.
- Direct reads of `backend/app/export.py`, `reports.py`, `main.py` (export/scheduled-report routes), `analytics/service.py`, `analytics/schemas.py`, `analytics/router.py`, `vulnerabilities/sla_service.py`, `vulnerabilities/service.py` (`get_mttr_by_tier`), `vulnerabilities/models.py` (`RemediationEvent`), `cspm/service.py` (`get_compliance_dashboard`), `coverage/service.py`/`schemas.py`, `tenants/models.py` (`Tenant`, `User`) — all this session.
- Direct reads of `frontend/src/app/(authed)/dashboard/page.tsx`, `.../analytics/page.tsx`, `.../coverage/page.tsx`, `components/dashboard/hero.tsx`, `trend-section.tsx`, `components/shell/nav-items.ts`, `hooks/use-url-state.ts`, `lib/queries/use-analytics.ts` — this session.
- `csf.tools` NIST CSF 2.0 reference pages for `ID.RA` and `PR.PS` categories (full subcategory listing) — WebFetch, this session.
- NIST's own public-domain notice (`nist.gov/copyrights-disclaimers`, `spdx.org/licenses/NIST-PD.html`) confirming 17 U.S.C. §105 status.

### Secondary (MEDIUM confidence)
- fpdf2's official documentation page (`py-pdf.github.io/fpdf2/Maths.html`) for the canonical matplotlib-embedding code pattern — WebFetch, cross-verified against the hands-on test above (which succeeded with a simplified variant of the same pattern).
- WebSearch-aggregated, cross-referenced control text for SOC 2 CC7.1/CC7.2 (multiple compliance-vendor sources converging on identical wording), PCI DSS v4.0.1 6.3.1/6.3.3/11.3.1/11.3.1.1 (multiple sources, including a direct PCI SSC FAQ page reference), ISO 27001:2022 A.8.8/A.8.9/A.5.7 (multiple ISMS/compliance-vendor sources).
- WebSearch confirmation of PCI DSS v4.0 retirement (2024-12-31) and v4.0.1 as the sole active version for 2026 assessments (multiple independent sources: SecurityMetrics, Scrut, PCI SSC's own blog).
- WebSearch cross-reference on matplotlib manylinux wheels bundling FreeType/libpng statically (no apt-get needed on Debian-based slim images) — general community consensus, not an official doc citation (matplotlib.org blocked WebFetch with HTTP 403 this session).

### Tertiary (LOW confidence)
- None — every finding in this document was either directly verified against the codebase/a live test, or cross-referenced against 2+ independent secondary sources. Items resting on a single unverified source are called out explicitly in the Assumptions Log above.

## Metadata

**Confidence breakdown:**
- Standard stack (D-02 chart pipeline): HIGH — hands-on verified end-to-end this session, plus official fpdf2 docs corroboration.
- Framework control catalog (D-09): HIGH for IDs/categorization (cross-sourced, NIST verified against `csf.tools`'s structured reference); MEDIUM for the specific numeric pass/partial/fail thresholds (explicitly flagged as a starting proposal, not sourced from the standards themselves, which are qualitative).
- Codebase integration points (export.py/reports.py/analytics/sla_service/coverage): HIGH — all read directly this session, not inferred from documentation or memory.
- Pitfalls (zero-denominator fake-100, missing exception-exclusion, no-period-param): HIGH — each is a direct, quoted read of the actual source line, not a guess.
- RPT-02 frontend composition: HIGH for integration points (files/hooks/patterns read directly); the visual/interaction decisions themselves are already locked in 43-UI-SPEC.md and correctly out of this document's scope.

**Research date:** 2026-08-22
**Valid until:** ~30 days for the codebase-integration findings (stable, low-churn area of an actively-developed repo); ~90-180 days for the framework-control IDs/text (NIST CSF 2.0, ISO 27001:2022, PCI DSS v4.0.1 are all current major versions unlikely to renumber controls soon; watch for PCI DSS v5.0 or an ISO 27001 revision as the most likely future invalidation triggers).
