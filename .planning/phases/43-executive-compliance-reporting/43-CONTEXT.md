# Phase 43: Executive & Compliance Reporting - Context

**Gathered:** 2026-08-22
**Status:** Ready for planning

<domain>
## Phase Boundary

A CISO or compliance owner can **prove the program is working** — and see **where findings sit against a named framework** — without an analyst hand-building a slide deck. Three deliverables (RPT-01..03):

1. **RPT-01 — exec/board PDF:** an exportable, branded PDF for a **selected period** showing risk trend + MTTR-by-tier + SLA compliance.
2. **RPT-02 — role-scoped dashboards:** the dashboard renders per job-function persona (analyst / IT-ops / compliance / leadership), tenant-scoped, each surfacing only what that persona needs.
3. **RPT-03 — compliance view:** a view mapping the tenant's vuln-management posture to framework controls (SOC 2 / ISO 27001 / PCI DSS / NIST CSF).

This is the **capstone reporting layer** over data already built: Phase 42's reusable analytics service (risk trend + burndown) and Phase 36's MTTR-by-tier + SLA-compliance metrics. It is **read-side reporting + presentation** — it **consumes** those services, never re-derives the risk model, SLA engine, or snapshot capture.

**Explicitly NOT this phase (how-to-implement boundary — no new capabilities):**
- **Per-finding framework-control tagging** — D-08 chose program-level control *evidence*, not tagging individual CVEs.
- **Tenant-configurable compliance catalog / control overrides** — D-09 ships a built-in curated catalog only.
- **Unifying vuln + CSPM compliance** into one framework view — D-10 is vuln-only this phase; the existing CSPM `get_compliance_dashboard` stays separate.
- **Control → drill-into-specific-findings evidence** — D-13 ships threshold-derived pass/partial/fail status only; the drill-to-findings evidence view is deferred.
- **A saved "default dashboard view" user attribute** — D-05 persists the lens client-side only; no backend user-preference column.
- **Redoing the filtering / ChipBar UI/UX** — raised mid-discussion; a new capability and its own phase, captured in Deferred Ideas.

</domain>

<decisions>
## Implementation Decisions

### RPT-01 — Exec/board PDF
- **D-01:** **Extend the existing branded exec-summary PDF** (`export.py::generate_executive_summary_pdf`, fpdf2) with new v5.0 sections (risk trend, MTTR-by-tier, SLA compliance) rather than building a second board-report generator. Reuse its branding (logo/colors), section-toggle mechanism, and the shared exception-exclusion predicate in `_collect_summary_data`. One PDF codepath to maintain. — **Reversibility:** reversible — additive sections on an existing generator.
- **D-02:** **Trend / burndown / MTTR charts are rendered server-side to raster images (PNG) and embedded** in the PDF (the frontend recharts components can't render into fpdf). Produces a real board-deck look. **Flag for research:** this needs a new charting dependency (matplotlib is NOT currently a backend dep — only `fpdf2>=2.8` is; likely also Pillow for image embedding). — **Reversibility:** costly — adds a backend charting dependency to the image; falling back to tables/numbers later means re-authoring the PDF section.
- **D-03:** **Period selector = presets (quarter / 30d / 90d / 1y) PLUS a custom start/end date-range picker**, mirroring Phase 42 D-03's Analytics range-control idiom exactly. Default period is planner discretion (a board cadence like "last quarter" is natural).
- **D-04:** **Reuse the existing `ScheduledReport` delivery** (`reports.py`) — the board report becomes a selectable format/section-set that can auto-email on a cadence (daily/weekly/monthly already supported), in addition to on-demand export. Do not build a second scheduling/delivery path.
- **D-01a (data source, cross-cutting):** RPT-01 sources trend + burndown from Phase 42's **reusable analytics service** (`backend/app/analytics/service.py` — `get_scoped_trend_series`, `get_burndown_rate`, `get_analytics_overview`), MTTR-by-tier from `backend/app/vulnerabilities/service.py::get_mttr_by_tier`, and SLA compliance from `backend/app/vulnerabilities/sla_service.py::get_sla_metrics` (`compliance_pct`). Call these **directly, no HTTP round-trip** (Phase 42 D-16 shaped them for exactly this). Never re-derive.

### RPT-02 — Role-scoped dashboards
- **D-05:** **Switchable view-lens model** — the four personas (analyst / IT-ops / compliance / leadership) are selectable dashboard *lenses*, NOT tied to the RBAC role tier (owner/admin/analyst/viewer). Any authenticated user can switch lens; "role" here means **job function**, not permission. Lens selection persists **client-side** (URL param / localStorage), no new backend user-preference column this phase. — **Reversibility:** reversible — a frontend selector + client-persisted state.
- **D-06:** **Reconfigure the existing `/dashboard` hero per selected lens** (one "home" page whose widget set swaps by persona) rather than net-new per-persona routes. Avoids duplicating the shell/layout and fragmenting "home".
- **D-07:** **Leadership / compliance lenses = trend-&-posture widgets** (risk trend, MTTR-by-tier, SLA-compliance %, framework posture summary, board-PDF export entry point). **Analyst / IT-ops lenses = the existing action-first triage widgets** (open criticals, my tickets, recent activity — the current `hero` / `stat-strip-wired` / `activity-rail` / `top5-card`). Exact per-lens widget composition is planner discretion, derived from existing dashboard components + Phase 42/36 data.

### RPT-03 — Compliance view
- **D-08:** **Program-level control-evidence model** — map the vuln-management **program** to a curated set of framework controls (e.g. PCI DSS 6.3.3 / 11.3, SOC 2 CC7.1, ISO 27001 A.8.8, NIST CSF ID.RA / PR.PS); each control's status is **evidenced by posture metrics**, NOT by tagging individual CVEs. Answers "are we satisfying framework X's vuln-management controls." — **Reversibility:** reversible — a read-side mapping + rollup, no finding-level schema change.
- **D-09:** **Built-in, version-controlled curated catalog** (framework → relevant controls → evidencing metric) shipped in code. No tenant configuration or control overrides this phase. Consistent, auditable, upgradeable in code. **Flag for research:** find authoritative control text/IDs per framework so the catalog is credible to auditors.
- **D-10:** **Vuln-only this phase.** Do NOT entangle RPT-03 with the existing CSPM framework grouping (`cspm/service.py::get_compliance_dashboard`, free-text `frameworks` JSONB on misconfigs). The two compliance surfaces stay separate; a unified vuln+CSPM rollup is deferred.
- **D-11:** **New top-level "Compliance" nav page** (`/dashboard/compliance` + a `nav-items.ts` entry), mirroring the Coverage (Phase 41) and Analytics (Phase 42) new-page precedent. Also reachable from the compliance dashboard lens (D-07).
- **D-12:** **All four frameworks ship day one** — SOC 2, ISO 27001, PCI DSS, NIST CSF (the full RPT-03 set).
- **D-13:** **Control status = thresholds on posture metrics.** Each catalog control maps to a metric (SLA-compliance %, coverage %, open-critical count) with pass / partial / fail thresholds defined in the built-in catalog (e.g. "PCI 6.3.3 = pass if critical SLA-compliance ≥ 95%"). Deterministic and explainable. Drill-into-the-specific-findings-behind-a-control is **deferred** (not this phase). Exact metric-per-control + thresholds are planner discretion within the catalog.

### Claude's Discretion
- Default reporting period for the PDF (D-03) and exact new PDF section layout/order (D-01).
- Charting library choice + how images are generated and embedded (D-02) — subject to the dependency flag.
- Exact per-lens widget composition for each persona (D-07); how the lens switcher renders (segmented control, dropdown) and where it sits on `/dashboard`.
- Exact catalog contents: which controls per framework are vuln-management-relevant, which metric evidences each, and the pass/partial/fail thresholds (D-09/D-13).
- `/dashboard/compliance` route naming/layout and whether framework posture also renders as a compact section inside the compliance lens vs. only the standalone page (D-11).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` §"Phase 43: Executive & Compliance Reporting" (lines ~281–293) — goal, 3 success criteria, dependencies (Phase 36 + Phase 42).
- `.planning/REQUIREMENTS.md` — RPT-01, RPT-02, RPT-03 (lines ~76–78; dependency map ~121–123: all three depend on Phase 36 MTTR/SLA + Phase 42 trends).

### RPT-01 — existing PDF + scheduling stack to extend (do NOT rebuild)
- `backend/app/export.py` — `generate_executive_summary_pdf` (§L623, fpdf2, branded), `_collect_summary_data` (§L308, shared data collection + exception-exclusion `open_filter`), `generate_executive_summary` / `_csv`. The generator D-01 extends.
- `backend/app/reports.py` — `ScheduledReport` model (§L16) + `run_due_reports` / `_send_report` / `_is_due` (§L124+, daily/weekly/monthly cadence + SMTP delivery). The delivery path D-04 reuses.
- `backend/pyproject.toml` §L23 — current dep is `fpdf2>=2.8`; **matplotlib/Pillow are NOT present** (the D-02 dependency flag).

### RPT-01 — report data sources (call directly, no HTTP; Phase 42 D-16 / Phase 36)
- `backend/app/analytics/service.py` — Phase 42 reusable analytics service: `get_scoped_trend_series` (§L104), `get_burndown_rate` (§L302), `get_aging_distribution` (§L211), `get_analytics_overview` (§L397), `detect_version_boundaries` (§L160). Risk-trend + burndown source.
- `backend/app/vulnerabilities/service.py::get_mttr_by_tier` (§L507) — MTTR-by-tier (Phase 36 SLA-04).
- `backend/app/vulnerabilities/sla_service.py::get_sla_metrics` (§L119; `compliance_pct` §L191/223) — SLA-compliance % (RPT-01 section + RPT-03 evidencing metric).
- `backend/app/vulnerabilities/trends.py::get_mttr_trend` (§L148) — weekly MTTR line (supporting context if useful).
- `.planning/phases/42-risk-trend-analytics-burndown/42-CONTEXT.md` §D-16 — the "shape compute as a reusable service for Phase 43" hand-off contract.

### RPT-03 — compliance-view precedent & the metric that evidences controls
- `backend/app/cspm/service.py::get_compliance_dashboard` (§L255) — existing per-framework rollup pattern (CSPM misconfigs). D-10 keeps this SEPARATE; reference as the shape-to-mirror, not to merge.
- `backend/app/coverage/service.py::get_coverage_summary` (§L169) — Phase 41 coverage % (a candidate RPT-03 evidencing metric under D-13).
- Phase 36 SLA config + `backend/app/vulnerabilities/sla_tier_service.py` — risk-tier SLA windows behind SLA-compliance % (RPT-03 threshold metric).

### RPT-02 — dashboard surface to reconfigure
- `frontend/src/app/(authed)/dashboard/page.tsx` + `frontend/src/components/dashboard/` — `hero.tsx`, `stat-strip-wired.tsx`, `activity-rail.tsx`, `trend-section.tsx`, `top5-card.tsx`. The widgets the lens model (D-06/D-07) recomposes.
- `frontend/src/components/shell/nav-items.ts` — single source of truth for nav; where the new "Compliance" entry (D-11) is added. Note: no per-role nav gating exists today (RBAC-01 is owner/admin/analyst/viewer — deliberately NOT the RPT-02 personas, per D-05).

### Precedent (mirror these new-page patterns)
- `frontend/src/app/(authed)/dashboard/coverage/page.tsx` (Phase 41) and `.../analytics/page.tsx` (Phase 42) — the new-top-level-nav-page pattern D-11 mirrors.
- `.planning/phases/41-coverage-blind-spot-detection/41-CONTEXT.md` and `.../42-risk-trend-analytics-burndown/42-CONTEXT.md` — new-page + live-read-on-compute + honest-empty-state precedents.

### Design system (RPT-02 dashboard + RPT-03 page are UI — ROADMAP "UI hint: yes")
- `.claude/skills/sketch-findings-getvul/` — sunset design system. `references/page-layouts.md` (new-page + dashboard hero), `references/state-patterns.md` (mandatory empty/loading/error), `references/visual-language.md` (severity/SLA/status colors for posture + framework status), `references/copy-voice.md` (board-appropriate copy, no generic SaaS voice).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`export.py` exec-summary PDF stack** (`generate_executive_summary_pdf`, `_collect_summary_data`): branded, section-toggled, exception-aware — RPT-01 extends it (D-01) rather than starting fresh.
- **`reports.py` `ScheduledReport` + `run_due_reports`**: cadence + SMTP delivery reused verbatim for scheduled board reports (D-04).
- **`analytics/service.py`** (Phase 42, D-16): scoped trend, burndown, aging, overview — the RPT-01 trend/burndown data, callable without an HTTP round-trip.
- **`get_mttr_by_tier`** + **`sla_service.get_sla_metrics` (`compliance_pct`)**: the MTTR-by-tier and SLA-compliance numbers for RPT-01 and the RPT-03 control-evidence thresholds.
- **`cspm/service.get_compliance_dashboard`**: the per-framework rollup *shape* to mirror for RPT-03 (kept separate per D-10).
- **Dashboard widgets** (`hero`, `stat-strip-wired`, `activity-rail`, `trend-section`, `top5-card`) + **`nav-items.ts`** + Coverage/Analytics page precedent: compose the RPT-02 lenses and the RPT-03 Compliance page.

### Established Patterns
- **New top-level nav page for a distinct workflow** (Coverage/Analytics, Phases 41/42) — D-11.
- **Reusable service functions callable by both HTTP route and other services** (`analytics/service.py`, `trends.py`) — D-01a report generator calls them directly.
- **Branded, section-toggled PDF + scheduled SMTP delivery** (EXP-01/EXP-02, `export.py`/`reports.py`) — D-01/D-04.
- **Client-persisted view state via URL param** (Phase 42 D-03 `useUrlState`) — the RPT-02 lens persistence (D-05).

### Integration Points
- New PDF sections + a server-side chart-image step inside `export.py` (D-01/D-02); a new board-report format/section-set option in the `ScheduledReport` config (D-04).
- Lens switcher + persona-driven widget composition on `/dashboard` (D-05/D-06/D-07) — frontend-led, no new backend user attribute.
- New "Compliance" nav entry + `/dashboard/compliance` route (D-11) backed by a new read endpoint that computes per-framework control status from the built-in catalog against posture metrics (D-08/D-09/D-13).
- New built-in framework-control catalog module (data + threshold logic) — the RPT-03 core new asset.

</code_context>

<specifics>
## Specific Ideas

- The value is a CISO/compliance owner **proving** the program works and showing framework posture **without an analyst building a deck** — so RPT-01 must look board-ready (D-02 real chart images) and RPT-03 must be auditor-credible (D-09 authoritative control mappings).
- "Role" in RPT-02 means **job function, not permission tier** (D-05) — a deliberate decoupling from RBAC-01. A leadership lens is about *what you want to see*, not *what you're allowed to do*.
- RPT-03 is intentionally **program-level evidence, not per-CVE tagging** (D-08) — because a missing patch maps to the same handful of vuln-management controls; the honest question is "does our posture satisfy the control," answered by thresholds on real metrics (D-13).
- This phase adds **almost no new data** — it's presentation over Phase 36 + Phase 42 outputs. The one genuinely new data asset is the built-in framework-control catalog (D-09).

</specifics>

<deferred>
## Deferred Ideas

- **Redo the filtering / ChipBar UI/UX** (raised mid-discussion — "looks very bad from UI/UX"). The current filtering is the Phase 11 `ChipBar` + `useUrlState` pattern reused across Vulnerabilities / Assets / CSPM / Tickets. A redesign is a **new capability = its own phase**, not part of v5.0's current roadmap (Phases 43–45 are Reporting → NLQ Assistant → Public API). **Action:** promote via `/gsd-phase` (insert a UI phase) or `/gsd-capture` to the backlog. Not folded into Phase 43.
- **Per-finding framework-control tagging** — D-08 chose program-level evidence; per-CVE control tagging would need a CVE→control mapping source and is low-value for most findings.
- **Tenant-configurable compliance catalog / control overrides + thresholds** — D-09 ships a built-in curated catalog; a settings UI to toggle controls/thresholds is a later enhancement.
- **Unified vuln + CSPM compliance view** — D-10 is vuln-only; blending CSPM's free-text framework strings into one per-framework rollup is deferred.
- **Control → drill-into-specific-findings evidence view** — D-13 ships threshold-derived status only; showing the exact open findings behind each control's status is a richer later add.
- **Saved "default dashboard view" as a backend user preference** — D-05 persists lens client-side only; a server-side per-user default is a small later enhancement.

None of the above blocks Phase 43.

</deferred>

---

*Phase: 43-executive-compliance-reporting*
*Context gathered: 2026-08-22*
