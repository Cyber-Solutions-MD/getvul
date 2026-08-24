---
phase: 43-executive-compliance-reporting
reviewed: 2026-08-24T11:51:12Z
depth: standard
files_reviewed: 33
files_reviewed_list:
  - backend/app/compliance/__init__.py
  - backend/app/compliance/catalog.py
  - backend/app/compliance/router.py
  - backend/app/compliance/schemas.py
  - backend/app/compliance/service.py
  - backend/app/export.py
  - backend/app/main.py
  - backend/app/reports.py
  - backend/app/vulnerabilities/router.py
  - backend/app/vulnerabilities/service.py
  - backend/app/vulnerabilities/sla_service.py
  - backend/pyproject.toml
  - backend/tests/test_compliance.py
  - backend/tests/test_export.py
  - backend/tests/test_mttr.py
  - backend/tests/test_reports.py
  - backend/tests/test_sla_route.py
  - backend/tests/test_sla_service.py
  - frontend/src/app/(authed)/dashboard/compliance/page.test.tsx
  - frontend/src/app/(authed)/dashboard/compliance/page.tsx
  - frontend/src/app/(authed)/dashboard/page.test.tsx
  - frontend/src/app/(authed)/dashboard/page.tsx
  - frontend/src/components/compliance/control-card.tsx
  - frontend/src/components/dashboard/export-board-report-dialog.test.tsx
  - frontend/src/components/dashboard/export-board-report-dialog.tsx
  - frontend/src/components/dashboard/framework-posture-strip.test.tsx
  - frontend/src/components/dashboard/framework-posture-strip.tsx
  - frontend/src/components/dashboard/leadership-hero.tsx
  - frontend/src/components/dashboard/lens-switcher.test.tsx
  - frontend/src/components/dashboard/lens-switcher.tsx
  - frontend/src/components/dashboard/mttr-by-tier-tile.tsx
  - frontend/src/components/dashboard/sla-compliance-tile.tsx
  - frontend/src/components/shell/nav-items.ts
  - frontend/src/hooks/use-lens.ts
  - frontend/src/lib/queries/keys.ts
  - frontend/src/lib/queries/use-compliance.ts
  - frontend/src/lib/queries/use-mttr-by-tier.ts
  - frontend/src/lib/queries/use-sla-metrics.ts
findings:
  critical: 1
  warning: 2
  info: 2
  total: 5
status: issues_found
---

# Phase 43: Code Review Report

**Reviewed:** 2026-08-24T11:51:12Z
**Depth:** standard
**Files Reviewed:** 33 (some named in the workflow's `files_to_read` list do not exist as separate source files, e.g. `backend/app/compliance/__init__.py` is an empty package marker)
**Status:** issues_found

## Summary

The new `compliance/` package (catalog + service + router + schemas) is careful and internally consistent: the zero-data-honesty invariant is upheld throughout (`not_measured` short-circuits before any threshold compare, `has_active_scanning` is correctly treated as a real boolean answer rather than a zero-denominator case), tenant scoping is threaded inline on every call (`user.tenant_id` passed directly, never fetch-then-filter, confirmed by a dedicated cross-tenant-isolation test), and the `exclude_exceptions=True` wiring for `sla_compliance_pct` is verified end-to-end from the compliance page down to `get_sla_metrics`. The frontend compliance page, control cards, framework-posture strip, and MTTR/SLA dashboard tiles also correctly gate on the metric's own null/zero-denominator signal rather than fabricating 0%/100% figures, and this is well covered by tests.

The one BLOCKER is in the pre-existing (not newly-added) part of `export.py`'s PDF renderer: the `sections` filter that gates which blocks appear in the board PDF is broken for every section except the three new RPT-01 chart sections — the six legacy sections (vulnerabilities, assets, risk, top hosts, top remediations, tickets) are drawn unconditionally regardless of what the caller requests, which is inconsistent with the CSV/text renderers (which honor `sections` correctly for all nine keys) and is directly reachable through the public `/api/v1/export/summary?format=pdf&section=...` endpoint. This is untested (the test suite only ever asserts inclusion, never a legacy section's absence).

A secondary WARNING concerns three of the new leadership-lens dashboard tiles silently collapsing a genuine backend error into the same "not yet measured" rendering used for an honestly-empty tenant, with no retry affordance, unlike the sibling risk-trend widget on the same lens.

## Critical Issues

### CR-01: Board-PDF `sections` filter is only honored for the 3 new RPT-01 chart sections — legacy sections always render regardless of the request

**File:** `backend/app/export.py:936-1148`

**Issue:** `generate_executive_summary_pdf`'s `sec = d.get("sections", [])` list is supposed to gate which blocks are drawn (exactly as `generate_executive_summary`/`generate_executive_summary_csv` do for all nine section keys, and exactly as the new `risk_trend`/`mttr_by_tier`/`sla_compliance` blocks correctly do in this same function via `if "risk_trend" in sec:` etc.). But for the six pre-existing sections the gating is either missing entirely or broken:

- **Vulnerabilities** (line 936-949): the section *header* is correctly gated —
  ```python
  if "vulns" not in sec:
      pass
  else:
      section("Vulnerability Overview")
  for label, val in [...]:      # NOT nested under the if/else — always runs
      row(label, val)
  ```
  so even when `"vulns"` is excluded from `sections`, every vulnerability metric row still prints (just without its header).
- **Assets by Type** (line 952), **Risk Distribution** (line 968), **Top N Riskiest Hosts** (line 1100), **Top N/0 Remediations** (line 1125-1129), and **Ticket Status** (line 1146) have **no `"X" in sec` check at all** — they are drawn unconditionally on every call, regardless of what `sections` the caller asked for.

This is reachable by any caller of the public export route: `GET /api/v1/export/summary?format=pdf&section=risk_trend` (main.py's `export_resource`, which passes `section` straight through to `report_filters["sections"]`) will still render Assets/Risk/Top-Hosts/Remediations/Tickets in the PDF even though the caller explicitly asked for only `risk_trend`. This is inconsistent behavior across formats (the same request with `format=csv`/`format=txt` correctly omits everything but the requested section, per `generate_executive_summary_csv`/`generate_executive_summary`'s `if "X" in sec:` checks) and has a real confidentiality implication: a board-report author who deliberately excludes a section (e.g. because it's not meant for a given recipient) does not get what they asked for in PDF form.

It is also untested: `test_export.py::test_generate_executive_summary_pdf_without_new_sections_is_backward_compatible` only exercises the case where `sections` includes ALL SIX legacy keys (never a legacy key's *exclusion*), and `test_sla_compliance_section_renders_not_yet_measured_on_zero_remediation`/`test_top_remediations_section_renders_honest_empty_state_when_none_recorded` pass a `sections` list containing only one key but never assert that the OTHER (ungated) sections are absent from the rendered PDF.

**Fix:** Wrap each of the five ungated blocks in the same `if "X" in sec:` pattern already used for `risk_trend`/`mttr_by_tier`/`sla_compliance`, and fix the "Vulnerabilities" block so the per-metric `for` loop is nested inside the `else` branch (or restructured as a single `if "vulns" in sec:` guarding both the header and the rows), mirroring `generate_executive_summary`'s existing correct pattern:
```python
if "vulns" in sec:
    section("Vulnerability Overview")
    for label, val in [...]:
        row(label, val)
    pdf.ln(5)

if "assets" in sec:
    section("Assets by Type")
    ...
    pdf.ln(5)

if "risk" in sec:
    section("Risk Distribution")
    ...
    pdf.ln(5)

if "top_hosts" in sec:
    section(f"Top {n} Riskiest Hosts")
    ...

if "top_remediations" in sec:
    ...  # existing nr==0 / else branches, now gated

if "tickets" in sec:
    section("Ticket Status")
    ...
```
Add a regression test that requests a narrow `sections` list (e.g. `["risk_trend"]` alone) and asserts the OTHER legacy sections' header text is absent from `_pdf_text_tokens(pdf_bytes)`, mirroring the existing absence-assertion pattern already used for the chart sections in `test_generate_executive_summary_pdf_without_new_sections_is_backward_compatible`.

## Warnings

### WR-01: Leadership-lens dashboard tiles collapse real backend errors into the same rendering as an honestly-empty tenant, with no retry

**File:** `frontend/src/app/(authed)/dashboard/page.tsx:119-161`

**Issue:** `LeadershipMttrTile`, `LeadershipSlaTile`, and `LeadershipPostureStrip` all use the pattern:
```tsx
if (q.isPending || q.error || !q.data) {
  return <MttrByTierTile rows={[]} />;   // / SlaComplianceTile with all-zero metrics / FrameworkPostureStrip with []
}
```
This means a genuine backend failure (500, network error, or an admin-gated 403 for `mttr/by-tier`) renders pixel-identical to a brand-new tenant with zero real posture data — the user sees "Not yet measured" everywhere with no indication that a request actually failed, and no retry control. Compare this to `RiskTrendWidget` on the exact same lens (lines 80-117), which correctly distinguishes `q.error` (renders `PartialFailureBanner` with an `onRetry` callback) from the genuinely-empty case (`scoredPointCount < 2`). The inconsistency means an operator with, say, a flaky network or a mis-scoped RBAC grant would have no signal from the dashboard that something needs attention — it would just look like an under-instrumented tenant.

**Fix:** At minimum, distinguish the error case for `LeadershipSlaTile`/`LeadershipPostureStrip` (both `require_viewer`-gated, so a 403 here would itself indicate a real bug) the same way `RiskTrendWidget` does, e.g.:
```tsx
function LeadershipSlaTile({ compact = false }: { compact?: boolean }) {
  const q = useSlaMetrics();
  if (q.error) {
    return <PartialFailureBanner errors={[...]} onRetry={() => q.refetch()} source="SLA compliance" />;
  }
  if (q.isPending || !q.data) {
    return <SlaComplianceTile compact={compact} metrics={ZERO_METRICS} />;
  }
  return <SlaComplianceTile compact={compact} metrics={q.data} />;
}
```
`LeadershipMttrTile`'s comment explicitly documents that a non-admin's 403 is intentionally treated this way (a reasonable RBAC-floor decision) — but that same code path also silently swallows a genuine 500, which is a distinct failure mode from "you don't have this role" and arguably deserves its own signal.

### WR-02: `compliance/__init__.py` is an empty file with no module docstring or exports

**File:** `backend/app/compliance/__init__.py`

**Issue:** The file is completely empty (zero bytes) — no package docstring, no re-exports. Every sibling module in this package (`catalog.py`, `service.py`, `router.py`, `schemas.py`) carries a substantial module docstring documenting its role in the D-08/D-09/D-13 architecture; the package `__init__.py` itself carries none, which is a minor inconsistency with this codebase's otherwise-thorough documentation convention for new packages (compare `app/coverage/__init__.py` or `app/analytics/__init__.py`'s equivalents, which the router.py docstring above explicitly says this package "mirrors").

**Fix:** Not blocking, but for consistency add a short package-level docstring describing the module's scope (RPT-03 compliance package: catalog + service + router).

## Info

### IN-01: Duplicate `n = len(d["top_hosts"])` computation in `generate_executive_summary_pdf`

**File:** `backend/app/export.py:933` and `:1098`

**Issue:** `n` is computed once at line 933 (used only by the dead `if "vulns" not in sec: pass else:` header text, which doesn't even reference `n`) and recomputed identically at line 1098 immediately before its actual use for the "Top N Riskiest Hosts" header. The first computation at line 933 is unused dead code.

**Fix:** Remove the line-933 computation; keep only the line-1098 one where it's actually consumed.

### IN-02: `evidencingLine`'s generic percentage branch will mis-render for future non-percentage metric keys without a compile-time guard

**File:** `frontend/src/components/compliance/control-card.tsx:58-67`

**Issue:** `evidencingLine` falls through to `` `${metricLabel}: ${control.value}%` `` for any `metric_key` not explicitly special-cased as `has_active_scanning`. This is correct for all five current metric keys (four of which are percentages, and `mttr_by_tier`'s value is also a 0-100 percentage so it happens to work), but there's no type-level or runtime guard that a *future* catalog metric_key with a non-percentage unit (e.g. a raw day count) would be caught before silently rendering `"...: 4.2%"` for a value that isn't a percentage. `METRIC_LABEL` is a `Record<string, string>` with no exhaustiveness check against the backend's `metric_key` union either.

**Fix:** Non-blocking for the current catalog (all current keys are legitimately percentages or the special-cased boolean), but worth a comment noting the assumption, or an explicit allow-list of percentage-shaped keys, before a future catalog addition silently inherits the wrong unit suffix.

---

_Reviewed: 2026-08-24T11:51:12Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
