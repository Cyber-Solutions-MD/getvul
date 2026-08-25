# Phase 43: Executive & Compliance Reporting - Pattern Map

**Mapped:** 2026-08-22
**Files analyzed:** 22 (12 backend, 10 frontend)
**Analogs found:** 22 / 22

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `backend/app/export.py` (extend `_collect_summary_data`, `generate_executive_summary_pdf`, new `_render_*_chart` helpers) | service (PDF assembly) | batch / transform | itself (existing functions, same file) | exact |
| `backend/app/reports.py` (extend `_send_report`'s default `sections` list; no schema change — `sections`/`filters` are JSONB) | service (scheduled delivery) | batch / event-driven (cron-tick) | itself (`_send_report`, `run_due_reports`) | exact |
| `backend/app/main.py::export_resource` (extend query params: period preset/from/to; new `risk_trend`/`mttr_by_tier`/`sla_compliance` section keys) | route | request-response | itself + `analytics/router.py`'s `from_`/`to`/span-cap validation block | role-match |
| `backend/app/vulnerabilities/sla_service.py::get_sla_metrics` (extend — optional `severity`, `exclude_exceptions` params, additive) | service | CRUD (aggregate read) | `analytics/service.py::_open_backlog_conditions` (the exception-exclusion predicate to port in) | role-match |
| `backend/app/compliance/__init__.py` | package init | — | `coverage/__init__.py` / `analytics/__init__.py` (empty/minimal) | exact |
| `backend/app/compliance/catalog.py` (NEW — pure data + `evaluate_catalog()`) | model/utility (static data + pure function) | transform | no direct analog — closest shape is `assets/risk_score.py`'s tier-threshold constants (pure, no I/O) | role-match |
| `backend/app/compliance/service.py` (NEW — compute ~5 metrics once, call catalog) | service | CRUD (read aggregation, compute-once) | `coverage/service.py::get_coverage_summary` (zero-denominator discipline) + `analytics/service.py::get_analytics_overview` (orchestrator-calls-sub-functions-once shape) | exact |
| `backend/app/compliance/schemas.py` (NEW — Pydantic response models) | model (DTO) | transform | `coverage/schemas.py` (response-model conventions, `ConfigDict(from_attributes=True)`) | exact |
| `backend/app/compliance/router.py` (NEW — `GET /overview`) | route/controller | request-response | `coverage/router.py` (thin-handler + `require_viewer` + tenant-scoped shape) | exact |
| `backend/app/main.py` (register `compliance_router` at `app.include_router(...)`) | config (route registration) | — | the existing `coverage_router`/`analytics_router` registration lines | exact |
| `backend/pyproject.toml` (add `matplotlib>=3.9`, `Pillow>=10.0`) | config | — | existing `fpdf2>=2.8` dependency line | exact |
| `backend/tests/test_export.py` (NEW) | test | — | no existing file (Wave 0 gap) — mirror `backend/tests/test_analytics.py`'s fixture/seed-data style | no analog (new) |
| `backend/tests/test_reports.py` (NEW) | test | — | no existing file (Wave 0 gap) — mirror `backend/tests/test_mttr.py`'s `RemediationEvent`-seeding helper | no analog (new) |
| `backend/tests/test_compliance.py` (NEW) | test | — | `backend/tests/test_coverage.py` (tenant-isolation + zero-denominator test shape) | role-match |
| `frontend/src/app/(authed)/dashboard/page.tsx` (extend — lens switcher + conditional widget composition) | page (client component, composition root) | request-response (client-fetched) | itself (existing file) | exact |
| `frontend/src/app/(authed)/dashboard/compliance/page.tsx` (NEW) | page | request-response | `frontend/src/app/(authed)/dashboard/coverage/page.tsx` (ErrorBoundary > Suspense > Inner, mandatory empty/loading/error branches) + `.../analytics/page.tsx` (single-combined-query shape) | exact |
| `frontend/src/components/dashboard/lens-switcher.tsx` (NEW) | component (toggle control) | — | `frontend/src/components/ui/trend-chart.tsx`'s `RangeToggle` idiom + `ScopeWindowControls`' window-preset segmented buttons (`role="group"` + `aria-pressed`) | role-match |
| `frontend/src/components/dashboard/leadership-hero.tsx` (NEW) | component | request-response | `frontend/src/components/dashboard/hero.tsx` (same slot, same page, swapped content) | role-match |
| `frontend/src/components/dashboard/mttr-by-tier-tile.tsx` (NEW) | component | request-response | `frontend/src/components/analytics/burndown-tile.tsx` (stat-tile-with-states shape) | role-match |
| `frontend/src/components/dashboard/sla-compliance-tile.tsx` (NEW) | component | request-response | `frontend/src/components/analytics/burndown-tile.tsx` (same stat-tile shape, different metric) | role-match |
| `frontend/src/components/dashboard/framework-posture-strip.tsx` (NEW, shared between lens + full page) | component | request-response | `frontend/src/components/coverage/coverage-connector-card.tsx` (per-item pill/card strip pattern) | role-match |
| `frontend/src/components/compliance/control-card.tsx` (NEW) | component | request-response | `frontend/src/components/coverage/coverage-connector-card.tsx` (card w/ status pill + metric line) | role-match |
| `frontend/src/lib/queries/use-compliance.ts` (NEW) | hook (data fetch) | request-response | `frontend/src/lib/queries/use-coverage-summary.ts` (no-arg query, `staleTime: 0`, snake_case passthrough) | exact |
| `frontend/src/components/shell/nav-items.ts` (extend — add `Compliance` entry to `WORKFLOW_ITEMS`) | config (nav registry) | — | itself (existing `Coverage`/`Analytics` entries, same array) | exact |
| `frontend/src/components/dashboard/export-board-report-dialog.tsx` (NEW — period preset + custom range + scheduling-toggle disclosure) | component (dialog/form) | request-response (file download) | `frontend/src/components/exceptions/exception-grant-dialog.tsx` (ResponsiveDialog wrapper + FIELD_CLASS form idiom) + `frontend/src/components/analytics/scope-window-controls.tsx` (preset+custom-range control) + `frontend/src/components/ui/ExportButton.tsx` (auth'd blob-download fetch pattern) | role-match |

## Pattern Assignments

### `backend/app/export.py` (extend — RPT-01)

**Analog:** itself — `_collect_summary_data` (L308-474) and `generate_executive_summary_pdf` (L623-788)

**Imports pattern** (L1-18):
```python
from __future__ import annotations

import csv
import io
import uuid
from datetime import UTC, datetime

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.assets.risk_score import RISK_SCORE_TIER_CRITICAL, RISK_SCORE_TIER_HIGH, RISK_SCORE_TIER_MEDIUM
from app.exceptions.service import active_exception_subquery
from app.tenants.models import Tenant, User
from app.ticketing.models import Ticket
from app.vulnerabilities.models import Vulnerability
```
New imports needed for D-01a/D-02: `from app.analytics.service import get_scoped_trend_series, get_burndown_rate, detect_version_boundaries`, `from app.vulnerabilities.service import get_mttr_by_tier`, `from app.vulnerabilities.sla_service import get_sla_metrics`, plus (inside the chart helper, matching Pitfall 5's "never top-level `import matplotlib.pyplot`" rule) a lazy `from matplotlib.figure import Figure` / `from matplotlib.backends.backend_agg import FigureCanvasAgg`.

**Section-toggle + exception-exclusion pattern** (L308-330, the shared predicate every new section must reuse):
```python
async def _collect_summary_data(db: AsyncSession, tenant_id: uuid.UUID, filters: dict | None = None) -> dict:
    f = filters or {}
    ...
    sections = f.get("sections") or ["vulns", "assets", "risk", "top_hosts", "top_remediations", "tickets"]

    # EXC-02/D-15 (Phase 39 Tier 2 #14): an actively-excepted finding is
    # excluded from every count/query below that spreads `*open_filter`
    open_filter = [
        Vulnerability.tenant_id == tenant_id,
        Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
        ~active_exception_subquery(tenant_id, now),
    ]
```
D-01 extends this by appending `"risk_trend"`, `"mttr_by_tier"`, `"sla_compliance"` to the default `sections` list (per 43-UI-SPEC.md's byte-compatible-with-existing-scheduled-reports requirement) and returning three new top-level keys in `_collect_summary_data`'s return dict, computed via the D-01a direct service calls — **never** re-deriving vuln/risk numbers already in this function.

**PDF section-drawing pattern** (L677-775, the `section()`/`row()` closures + section-toggle guard to copy for each new section):
```python
def section(title):
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_fill_color(accent_r, accent_g, accent_b)
    pdf.set_text_color(primary_r, primary_g, primary_b)
    pdf.cell(0, 8, f"  {title}", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)

def row(label, value):
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(90, 6, f"  {label}")
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, str(value), new_x="LMARGIN", new_y="NEXT")

sec = d.get("sections", [])
if "vulns" not in sec:
    pass
else:
    section("Vulnerability Overview")
```
New sections go **after** the existing summary-stats block, **before** top-hosts/top-remediations/tickets (43-UI-SPEC.md order: risk trend → MTTR by tier → SLA compliance). Each is gated by `if "risk_trend" in sec: ...` mirroring the `"vulns" not in sec` guard above.

**Branding values already available for print-safe chart colors** (L636-641):
```python
primary_r = brand.get("primary_color_r", 79)
primary_g = brand.get("primary_color_g", 70)
primary_b = brand.get("primary_color_b", 229)  # indigo-500 default
accent_r = brand.get("accent_color_r", 240)
accent_g = brand.get("accent_color_g", 240)
accent_b = brand.get("accent_color_b", 250)
```
The risk-trend chart line uses `(primary_r, primary_g, primary_b)` per 43-UI-SPEC.md's PDF Rendering Contract (tenant's own brand, not sunset palette); MTTR/SLA chart colors use the **hardcoded light-mode hexes** from the UI-SPEC (`#DC2626`/`#EA580C`/`#B45309` for tier bars; `#15803D`/`#B45309`/`#DC2626` for SLA gauge) — these are NOT tenant-branded, they're fixed print-safe severity colors.

**Chart-render helper to add** (new function in this file, per RESEARCH.md Pattern 1 — copy verbatim, do not `import matplotlib.pyplot`):
```python
import io
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg

def _render_mttr_by_tier_chart(tiers: list[str], days: list[float], colors: list[str]) -> io.BytesIO:
    fig = Figure(figsize=(7.2, 4.0), dpi=200)
    ax = fig.add_subplot(111)
    ax.bar(tiers, days, color=colors)
    ax.set_ylabel("MTTR (days)")
    ax.set_title("MTTR by Risk Tier")
    fig.tight_layout()
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200)
    buf.seek(0)
    return buf

# usage inside generate_executive_summary_pdf():
buf = _render_mttr_by_tier_chart([...], [...], [...])
pdf.image(buf, w=180)
```

**PDF image embedding** (fpdf2 already installed, accepts `BytesIO` directly — no new code needed beyond calling `pdf.image(buf, w=180)`, verified this session per RESEARCH.md).

**Error handling / logo-embed convention** (L653-661, the existing "best-effort image embed, swallow failure" precedent to mirror for chart embedding if a render fails):
```python
if logo_path:
    from pathlib import Path
    if Path(logo_path).exists():
        try:
            pdf.image(logo_path, x=10, y=y_start, h=15)
            y_start += 2
        except Exception:
            pass  # skip if image fails
```
43-UI-SPEC.md's E4/E9 "retry with charts off (tables only)" error contract means a chart-render failure should be caught similarly, but — unlike the logo — should not be silently dropped from the user's perspective; surface a "charts unavailable" flag the route/dialog can act on rather than silently omitting a whole PDF section (see Shared Patterns below).

---

### `backend/app/reports.py` (extend — RPT-01 D-04)

**Analog:** itself (`_send_report`, L169-254; `ScheduledReport` model, L16-33)

**No schema/migration change needed** — `sections: Mapped[dict] = mapped_column(JSONB)` (L28) and `filters: Mapped[dict] = mapped_column(JSONB)` (L29) already accept arbitrary keys. D-04's board-report format/section-set is just a new value convention inside these existing JSONB columns.

**Default-sections list to extend additively** (L61, `create_report`, and L182, `_send_report` — both must grow in lockstep with `export.py`'s new default):
```python
# reports.py::create_report, L61
sections=data.get("sections", ["vulns", "assets", "risk", "top_hosts", "top_remediations", "tickets"]),

# reports.py::_send_report, L182 (the filters dict handed to generate_executive_summary_pdf)
"sections": report.sections or ["vulns", "assets", "risk", "top_hosts", "top_remediations", "tickets"],
```
Per 43-UI-SPEC.md: "appended to the default list so existing scheduled reports don't silently change shape" — do NOT insert the new keys into the middle of this list; append `"risk_trend"`, `"mttr_by_tier"`, `"sla_compliance"` at the end everywhere this literal list appears (3 call sites: `export.py::_collect_summary_data` default, `reports.py::create_report` default, `reports.py::_send_report` fallback).

**Delivery pattern (verbatim reuse, no changes needed)** (L187-235):
```python
if report.format == "pdf":
    content = await generate_executive_summary_pdf(db, report.tenant_id, filters)
...
if smtp_cfg and smtp_cfg.get("enabled") and smtp_cfg.get("host"):
    from app.email import send_email
    email_result = send_email(
        smtp_config=smtp_cfg, to=report.recipients, subject=f"GetVul Report: {report.name}",
        ...
    )
```
This already handles cadence (`_is_due`, L155-166) + SMTP delivery + audit logging (L238-254) — D-04 requires zero changes here beyond the `sections` default-list extension above.

---

### `backend/app/main.py::export_resource` (extend — RPT-01 period params)

**Analog:** itself (L385-449) for the export route shape; `backend/app/analytics/router.py` (L43-101) for the period-validation block to port in.

**Existing route signature to extend** (L385-399):
```python
async def export_resource(
    resource: str,
    db=Depends(get_db),
    user=Depends(get_current_user),
    severity: list[str] | None = Query(None),
    ...
    format: str = Query("csv"),
    section: list[str] | None = Query(None),
    top_count: int = Query(5),
    min_risk: int = Query(0),
):
```
Add `period: str | None = Query(None)` (preset enum: `30d`/`90d`/`quarter`/`year`) and `from_: date | None = Query(None, alias="from")` / `to: date | None = Query(None, alias="to")`, following the exact validation block below.

**Custom-range validation + DoS-cap pattern to copy verbatim** (`analytics/router.py` L74-86):
```python
start_param: date | None = None
end_param: date | None = None
if from_ is not None or to is not None:
    if from_ is None or to is None:
        raise HTTPException(status_code=422, detail="Both 'from' and 'to' are required for a custom range")
    if to < from_:
        raise HTTPException(status_code=422, detail="'to' must not be before 'from'")
    if (to - from_).days > MAX_ANALYTICS_WINDOW_DAYS:
        raise HTTPException(status_code=422, detail=f"Custom range cannot exceed {MAX_ANALYTICS_WINDOW_DAYS} days")
    start_param, end_param = from_, to
```
Reuse `analytics/service.MAX_ANALYTICS_WINDOW_DAYS` (or define an export-local equivalent) as the span cap per RESEARCH.md's V5/DoS mitigation — do not accept an unbounded custom range for the PDF path.

**Audit-call pattern to extend** (L446-449):
```python
elif resource == "summary":
    fmt = filters.get("format", "txt") if isinstance(filters.get("format"), str) else "txt"
    await audit(db, user, "export.summary", "report", f"summary.{fmt}", filters)
    await db.commit()
```
Extend the `filters` dict passed to `audit()` to include which new sections were requested (RESEARCH.md V7 — "every new mutating action... emits a tenant-scoped audit event," and an export is already treated as audit-worthy here).

---

### `backend/app/vulnerabilities/sla_service.py::get_sla_metrics` (extend, additive — Pitfall 1/2 fixes)

**Analog:** itself (L118-228); the exception-exclusion predicate to port in from `backend/app/analytics/service.py::_open_backlog_conditions` (L188-208)

**Current signature and the two bugs to guard against** (L118, L191):
```python
async def get_sla_metrics(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    ...
    compliance_pct = round((remediated_within_sla / remediated_total * 100), 1) if remediated_total > 0 else 100.0
    ...
    return {
        ...,
        "compliance_pct": compliance_pct,
        "remediated_within_sla": remediated_within_sla,
        "remediated_total": remediated_total,   # <- already in the return dict; callers MUST check this before trusting compliance_pct
        ...
    }
```
**Pitfall 1 (fake-100):** `remediated_total == 0` → treat as "not measured," never a real 100%. RPT-01/RPT-03 callers must check `remediated_total` before using `compliance_pct` as a threshold input (this can be done at the call site without changing the function, OR via the additive extension below).

**Pitfall 2 fix — the exception-exclusion predicate to add** (mirrors `analytics/service.py` L201-208 exactly):
```python
from app.exceptions.service import active_exception_subquery

async def get_sla_metrics(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    severity: str | None = None,           # NEW, optional
    exclude_exceptions: bool = False,       # NEW, optional, default False = byte-identical existing behavior
) -> dict:
    now = datetime.now(UTC)
    conditions = [Vulnerability.tenant_id == tenant_id, Vulnerability.status.in_(["OPEN", "IN_PROGRESS"])]
    if severity:
        conditions.append(Vulnerability.severity == severity)
    if exclude_exceptions:
        conditions.append(~active_exception_subquery(tenant_id, now))
    ...
```
New callers (RPT-01's PDF section, RPT-03's catalog metric) should pass `exclude_exceptions=True`; every existing call site keeps its default `False` (byte-compatible, per D-01a "never re-derive").

---

### `backend/app/compliance/catalog.py` (NEW — RPT-03 D-09)

**Analog:** no direct precedent for pure catalog data; closest shape is a plain dataclass + pure evaluator, exactly as scoped in 43-RESEARCH.md's own Pattern 2 (already verified against the codebase's conventions — `ConfigDict`/dataclass-free-of-I/O style matches `assets/risk_score.py`'s tier constants).

**Full pattern to implement (from RESEARCH.md Code Examples, verified against this session's codebase reads):**
```python
"""Built-in framework-control catalog (D-09) — pure data + pure function,
zero I/O. NIST CSF 2.0 text is U.S. public domain (verbatim OK); SOC 2/
ISO 27001/PCI DSS text is paraphrase-only (their standards bodies are
copyrighted) — see 43-RESEARCH.md Pitfall 7 / Code Examples table."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class ControlDef:
    framework: str       # "soc2" | "iso27001" | "pci_dss" | "nist_csf"
    control_id: str       # e.g. "CC7.1", "A.8.8", "6.3.3", "ID.RA-01"
    title: str            # short paraphrased title
    metric_key: str        # one of the ~5 keys service.py computes
    thresholds: dict[str, float]  # {"pass": 90, "partial": 50}

CATALOG: list[ControlDef] = [
    ControlDef("soc2", "CC7.1", "Vulnerability detection & monitoring", "coverage_pct", {"pass": 90, "partial": 50}),
    ControlDef("iso27001", "A.8.8", "Management of technical vulnerabilities", "critical_sla_health_pct", {"pass": 90, "partial": 70}),
    ControlDef("iso27001", "A.8.9", "Configuration management", "coverage_pct", {"pass": 90, "partial": 50}),
    ControlDef("pci_dss", "6.3.1", "Vulnerabilities identified & risk-ranked", "has_active_scanning", {}),  # boolean control
    ControlDef("pci_dss", "6.3.3", "Critical/high patches within documented timeframe", "critical_sla_health_pct", {"pass": 95, "partial": 80}),
    ControlDef("pci_dss", "11.3.1", "Internal vuln scans at least quarterly", "coverage_pct", {"pass": 90, "partial": 50}),
    ControlDef("pci_dss", "11.3.1.1", "Critical/high vulns resolved per risk-based timeframe", "critical_sla_health_pct", {"pass": 95, "partial": 80}),
    ControlDef("nist_csf", "ID.RA-01", "Vulnerabilities in assets are identified, validated, and recorded.", "coverage_pct", {"pass": 90, "partial": 50}),
    ControlDef("nist_csf", "ID.RA-06", "Risk responses are chosen, prioritized, planned, tracked, and communicated.", "sla_compliance_pct", {"pass": 90, "partial": 50}),
    ControlDef("nist_csf", "PR.PS-02", "Software is maintained, replaced, and removed commensurate with risk.", "mttr_by_tier", {}),  # tenant-calibrated, see service.py
]

def evaluate_catalog(metrics: dict[str, float | None]) -> list[dict]:
    """Pure function, no I/O. metrics[key] is None => the denominator was
    zero (Pitfall 1) => MUST short-circuit to NOT_MEASURED before any
    threshold compare — never render a fabricated pass OR fail."""
    results = []
    for c in CATALOG:
        value = metrics.get(c.metric_key)
        if value is None:
            status = "not_measured"
        elif value >= c.thresholds.get("pass", 999):
            status = "pass"
        elif value >= c.thresholds.get("partial", -1):
            status = "partial"
        else:
            status = "fail"
        results.append({
            "framework": c.framework, "control_id": c.control_id, "title": c.title,
            "metric_key": c.metric_key, "value": value, "status": status,
        })
    return results
```
NOTE for the boolean-style controls (`has_active_scanning`, `mttr_by_tier`) — the generic `>=` threshold shape above doesn't fit them cleanly; the planner should special-case these two in `evaluate_catalog` (boolean pass/fail; tenant-calibrated `sla_tier_service.get_tier_policy` comparison per RESEARCH.md's PR.PS-02 note) rather than force them through the numeric-threshold path.

---

### `backend/app/compliance/service.py` (NEW — RPT-03)

**Analog:** `backend/app/coverage/service.py::get_coverage_summary` (L169-215, zero-denominator discipline to copy) + `backend/app/analytics/service.py::get_analytics_overview` (L397+, compute-multiple-sub-metrics-once orchestrator shape)

**Zero-denominator discipline to copy verbatim** (`coverage/service.py` L192-193):
```python
# D-11: null (never 0 or 100) when the denominator is zero.
coverage_pct = round(100 * covered / total) if total else None
```
Apply the identical discipline to every metric `compliance/service.py` computes — `critical_sla_health_pct` must be `None` when the tier has zero open findings (0-of-0), and `sla_compliance_pct` must be `None` when `get_sla_metrics()["remediated_total"] == 0` (Pitfall 1), not the raw `compliance_pct` field.

**Metric-reuse orchestration to model** (imports/calls; direct, no HTTP, per D-01a's own precedent):
```python
from app.coverage.service import get_coverage_summary
from app.vulnerabilities.sla_service import get_sla_metrics
from app.vulnerabilities.service import get_mttr_by_tier
from app.analytics.service import get_aging_distribution
from app.compliance.catalog import evaluate_catalog

async def get_compliance_overview(db, tenant_id: uuid.UUID) -> dict:
    coverage = await get_coverage_summary(db, tenant_id)
    sla = await get_sla_metrics(db, tenant_id, exclude_exceptions=True)  # Pitfall 2 fix, see sla_service.py extension above
    aging = await get_aging_distribution(db, tenant_id, now=datetime.now(UTC))
    mttr = await get_mttr_by_tier(db, tenant_id)

    metrics = {
        "coverage_pct": coverage.total_authoritative_assets and _pct(coverage),  # None-safe per coverage's own convention
        "sla_compliance_pct": sla["compliance_pct"] if sla["remediated_total"] > 0 else None,  # Pitfall 1 guard
        "critical_sla_health_pct": _critical_health_from_aging(aging),  # derived, zero-denom guarded
        "has_active_scanning": coverage.has_scanner_connector,
        "mttr_by_tier": mttr,
    }
    return {"controls": evaluate_catalog(metrics)}
```
(Illustrative — exact helper names are planner discretion; the load-bearing constraint is: **compute each of the ~5 metrics exactly once**, never let `evaluate_catalog`'s per-control loop issue its own query.)

---

### `backend/app/compliance/schemas.py` (NEW)

**Analog:** `backend/app/coverage/schemas.py` (full file, L1-110) — `ConfigDict(from_attributes=True)` Pydantic v2 convention.

**Pattern to copy** (`coverage/schemas.py` L56-69, the response-envelope shape):
```python
class CoverageSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    cards: list[CoverageConnectorCardResponse]
    total_authoritative_assets: int
    has_authoritative_inventory: bool
    has_scanner_connector: bool
```
Mirror this exactly for `ComplianceOverviewResponse` (a `controls: list[ControlStatusResponse]` list, each row carrying `framework`, `control_id`, `title`, `metric_key`, `value: float | None`, `status: Literal["pass","partial","fail","not_measured"]`).

---

### `backend/app/compliance/router.py` (NEW)

**Analog:** `backend/app/coverage/router.py` (full file, L1-99) — thin-handler + RBAC + tenant-scoping shape to copy verbatim.

**Pattern to copy** (`coverage/router.py` L67-76):
```python
@router.get("/summary", response_model=CoverageSummaryResponse)
async def get_coverage_summary_endpoint(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
) -> CoverageSummaryResponse:
    """... Tenant-scoped throughout (T-41-07)."""
    return await _get_coverage_summary(db, user.tenant_id)
```
For `GET /overview`:
```python
from app.auth.rbac import require_viewer
from app.auth.schemas import CurrentUser
from app.dependencies import DBSession
from app.compliance.schemas import ComplianceOverviewResponse
from app.compliance.service import get_compliance_overview as _get_compliance_overview

router = APIRouter()

@router.get("/overview", response_model=ComplianceOverviewResponse)
async def get_compliance_overview_endpoint(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
) -> ComplianceOverviewResponse:
    return await _get_compliance_overview(db, user.tenant_id)
```
`require_viewer` (not `require_analyst`) — read-only endpoint, matching Coverage's `/summary` GET precedent exactly (RESEARCH.md V4 Access Control).

---

### `backend/app/main.py` (register the new router)

**Analog:** the existing registration lines (L35, L324-325):
```python
from app.coverage.router import router as coverage_router
...
app.include_router(coverage_router, prefix="/api/v1/coverage", tags=["Coverage"])
app.include_router(analytics_router, prefix="/api/v1/analytics", tags=["Analytics"])
```
Add: `from app.compliance.router import router as compliance_router` and `app.include_router(compliance_router, prefix="/api/v1/compliance", tags=["Compliance"])`.

---

### `frontend/src/app/(authed)/dashboard/page.tsx` (extend — RPT-02)

**Analog:** itself (full file, 92 lines)

**Existing composition to preserve for analyst/IT-ops (D-07 "byte-for-byte")** (L46-92):
```tsx
export default function DashboardPage() {
  const stats = useStats();
  ...
  const onboarding = stats.data?.onboarding_state;
  if (!stats.isPending && (onboarding === 'no_scanners' || onboarding === 'no_data_yet')) {
    return ( <><h1 className="sr-only">Dashboard</h1><OnboardingPanel .../></> );
  }
  return (
    <>
      <h1 className="sr-only">Dashboard</h1>
      <div className="grid gap-6 xl:grid-cols-[1fr_340px]">
        <div className="flex min-w-0 flex-col gap-6">
          <ErrorBoundary fallback={SectionErrorFallback('Hero')}><Hero /></ErrorBoundary>
          <ErrorBoundary fallback={SectionErrorFallback('Stats')}><StatStripWired /></ErrorBoundary>
          <ErrorBoundary fallback={SectionErrorFallback('Trend')}>
            <Suspense fallback={<TrendChartSkeleton />}><TrendSection /></Suspense>
          </ErrorBoundary>
          <ErrorBoundary fallback={SectionErrorFallback('Top 5')}><Top5Card /></ErrorBoundary>
        </div>
        <ErrorBoundary fallback={SectionErrorFallback('Activity')}><ActivityRail /></ErrorBoundary>
      </div>
    </>
  );
}
```
**Integration approach (Open Question 3's recommendation, locked):** keep the onboarding gate as the OUTERMOST check, unchanged — the lens switcher only renders once onboarding clears. Add the `useUrlState('lens', [...], 'analyst')` read at the top (mirrors `TrendSection`'s own `useUrlState('range', ...)` call one component down — same hook, different key, no collision), then branch the returned JSX on `lens`: `analyst`/`it-ops` render the exact block above unchanged; `leadership`/`compliance` render the new widget sets per 43-UI-SPEC.md's Phase-Specific Contract. Each new widget still gets its own `<ErrorBoundary>` wrapper, matching this file's existing per-section isolation convention.

**localStorage-fallback note:** `useUrlState` (below) has NO localStorage fallback built in — D-05 requires one for bare `/dashboard` visits. This must be a small local addition inside `page.tsx` (read `localStorage.getItem('dashboard-lens')` once, seed the initial `useUrlState` call, or wrap with a thin local hook) — there is no existing codebase precedent for URL+localStorage dual persistence; this is genuinely new plumbing, not a re-derivation.

---

### `frontend/src/hooks/use-url-state.ts` (reused as-is for the lens param)

**Analog:** itself (full file, 43 lines) — the D-05/Phase-42-D-03 lens-persistence idiom.

```tsx
export function useUrlState<T extends string>(
  key: string, allowed: readonly T[], defaultValue: T
): [T, (next: T) => void] {
  ...
  const value: T = raw !== null && (allowed as readonly string[]).includes(raw) ? (raw as T) : defaultValue;
  const setValue = useCallback((next: T) => {
    const sp = new URLSearchParams(params?.toString() ?? '');
    if (next === defaultValue) sp.delete(key); else sp.set(key, next);
    ...
    router.replace(target, { scroll: false });
  }, [router, pathname, params, key, defaultValue]);
  return [value, setValue];
}
```
Call as `useUrlState<Lens>('lens', ['analyst','it-ops','compliance','leadership'] as const, 'analyst')` inside `dashboard/page.tsx` (mirrors `AnalyticsPageInner`'s `useUrlState<AnalyticsWindow>('window', ALLOWED_WINDOWS, '30d')` call exactly). Requires `<Suspense>` around any consumer per the existing `TrendSection` wrapping comment in `page.tsx` (`useSearchParams` CSR-bailout requirement, Next 15).

---

### `frontend/src/app/(authed)/dashboard/compliance/page.tsx` (NEW — RPT-03)

**Analog:** `frontend/src/app/(authed)/dashboard/analytics/page.tsx` (full file, 229 lines) for the single-combined-query shell shape; `frontend/src/app/(authed)/dashboard/coverage/page.tsx` (L1-90+) for the multi-branch empty-state precedent.

**Shell composition to copy** (`analytics/page.tsx` L219-229):
```tsx
const PAGE_FALLBACK = <AnalyticsPageSkeleton />;

export default function AnalyticsPage() {
  return (
    <ErrorBoundary fallback={pageErrorFallback} boundaryName="AnalyticsPage">
      <Suspense fallback={PAGE_FALLBACK}>
        <AnalyticsPageInner />
      </Suspense>
    </ErrorBoundary>
  );
}
```

**Mutually-exclusive state-branch order to copy** (`analytics/page.tsx` L163-214, adapted — RPT-03 has no custom-range concern, so the branch chain is simpler: error > loading > empty(no-scanner / no-SLA-policy, two-branch per UI-SPEC) > populated):
```tsx
{q.error ? (
  <PartialFailureBanner errors={[{ code: 'http_error', requestId: ... }]} onRetry={() => q.refetch()} />
) : q.isPending ? (
  <CompliancePageSkeleton />
) : isZeroDenominator ? (
  <EmptyState>
    <EmptyState.Title>{microcopy.empty.title}</EmptyState.Title>
    <EmptyState.Body>{microcopy.empty.noScanner /* or */ microcopy.empty.noSlaPolicy}</EmptyState.Body>
  </EmptyState>
) : (
  <div className="space-y-8">
    {/* framework chip bar + control-card grid, grouped by framework */}
  </div>
)}
```
**Empty-state branch selection source:** reuse `has_scanner_connector`/`has_authoritative_inventory` semantics from `CoverageSummaryResponse` (already the source of truth per RESEARCH.md Pattern 3) to pick which of the two UI-SPEC empty-state copy branches applies — do not re-derive "has this tenant started scanning" logic here.

**Framework chip bar precedent** — mirror `components/ui/ChipBar.tsx`'s existing active-chip convention (used by Vulnerabilities/Assets/CSPM/Tickets filtering, referenced directly in 43-UI-SPEC.md's Design System section) for the `All / SOC 2 / ISO 27001 / PCI DSS / NIST CSF` chip bar.

---

### `frontend/src/lib/queries/use-compliance.ts` (NEW)

**Analog:** `frontend/src/lib/queries/use-coverage-summary.ts` (full file, 49 lines) — the exact no-arg, `staleTime: 0`, snake_case-passthrough shape to copy.

```tsx
'use client';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';

export type ControlStatus = {
  framework: string;
  control_id: string;
  title: string;
  metric_key: string;
  value: number | null;
  status: 'pass' | 'partial' | 'fail' | 'not_measured';
};

export type ComplianceOverviewResponse = {
  controls: ControlStatus[];
};

export function useComplianceOverview() {
  return useQuery({
    queryKey: queryKeys.compliance.overview(),
    queryFn: ({ signal }) => api<ComplianceOverviewResponse>('/api/v1/compliance/overview', { signal }),
    staleTime: 0,
    retry: 1,
  });
}
```
Add a `compliance: { overview: () => [...] }` entry to `frontend/src/lib/queries/keys.ts` mirroring the existing `coverage.summary()`/`analytics.overview(...)` key-factory entries (not read directly this session, but the convention is unambiguous from both hooks above using `queryKeys.<domain>.<verb>()`).

---

### `frontend/src/components/dashboard/lens-switcher.tsx` (NEW)

**Analog:** `frontend/src/components/analytics/scope-window-controls.tsx`'s window-preset segmented-button block (L48-54 options array + the `role="group"`/`aria-pressed` toggle it extends from `components/ui/trend-chart.tsx`'s `RangeToggle`).

Render as a 4-segment control per 43-UI-SPEC.md: inactive segment = `--color-surface-2` fill + `--color-text-muted` label; active segment = `--color-pink-soft` fill + `--color-pink` label/border (existing `.chip`/`ChipBar` active-state convention — reuse those exact classes/tokens, do not invent new ones).

---

### `frontend/src/components/dashboard/leadership-hero.tsx`, `mttr-by-tier-tile.tsx`, `sla-compliance-tile.tsx`, `framework-posture-strip.tsx` (NEW — RPT-02 D-07)

**Analog:** `frontend/src/components/dashboard/hero.tsx` (slot precedent — same page position, different content for the leadership lens) and `frontend/src/components/analytics/burndown-tile.tsx` (stat-tile-with-populated/no-data-states shape to copy for MTTR/SLA tiles).

**"Not yet measured" no-data pattern (mandatory per E8) — model after the aging/burndown null-gating discipline already established in `use-analytics.ts`:**
```tsx
// use-analytics.ts L120-127 pattern — gate on the metric's OWN null signal,
// never on a falsy/zero value (0 can be a legitimate healthy reading).
const scoredPointCount = trend.filter((p) => p.avg_risk_exposure_score !== null).length;
const isBelowMinHistory = scoredPointCount < MIN_HISTORY_POINTS;
```
Apply the identical never-gate-on-falsy discipline to the MTTR-by-tier and SLA-compliance tiles: render the neutral `Not yet measured` treatment when the backend signals `null` (zero denominator), never when the value happens to be `0`.

---

### `frontend/src/components/compliance/control-card.tsx` (NEW)

**Analog:** `frontend/src/components/coverage/coverage-connector-card.tsx` (card w/ status badge + metric line + mono formatting — read the component's shape via its co-located test file `coverage-connector-card.test.tsx` for the exact prop/render contract if deeper detail is needed during planning).

Card layout locked by 43-UI-SPEC.md (control ID in mono + framework glyph + status pill + evidencing-metric line in mono) — this component is presentation-only, consuming `ControlStatus` from `use-compliance.ts` and never re-deriving status client-side (RESEARCH.md Architectural Responsibility Map: "the browser never re-derives a status, it renders what the backend returns").

---

### `frontend/src/components/dashboard/export-board-report-dialog.tsx` (NEW — RPT-01 D-03/D-04 web UI)

**Analog:** `frontend/src/components/exceptions/exception-grant-dialog.tsx` (ResponsiveDialog wrapper + `FIELD_CLASS`/`FIELD_LABEL_CLASS` form-field convention) + `frontend/src/components/analytics/scope-window-controls.tsx` (preset-toggle + custom-date-range-reveal pattern, L48-60) + `frontend/src/components/ui/ExportButton.tsx` (authenticated blob-download fetch + 401-refresh-retry pattern).

**Dialog wrapper pattern to copy** (`exception-grant-dialog.tsx` L37-64):
```tsx
import { ResponsiveDialog } from '@/components/ui/responsive-dialog';
const FIELD_CLASS = 'w-full rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-text placeholder-text-faint focus:border-violet focus:outline-none disabled:cursor-not-allowed disabled:opacity-60';
const FIELD_LABEL_CLASS = 'mb-1 block text-xs font-semibold uppercase tracking-wide text-text-muted';
```

**Preset + custom-range field pattern to copy** (`scope-window-controls.tsx` L48-60):
```tsx
const WINDOW_OPTIONS: { id: AnalyticsWindow; label: string; a11y: string }[] = [
  { id: '7d', label: ..., a11y: ... },
  ...
  { id: 'custom', label: microcopy.window.custom, a11y: microcopy.window.customA11y },
];
const FIELD_CLASS = '...'; // native <input type="date"> styling, no date-picker dependency
```
RPT-01's dialog uses the SAME idiom but with the D-03 preset set (`30d`/`90d`/`quarter`/`1y`/`custom`) and default `Last quarter` per 43-UI-SPEC.md (not Analytics' default `30d`).

**Authenticated blob-download fetch pattern to copy** (`ExportButton.tsx` L16-83 — the 401-refresh-retry + blob-download flow; the new dialog's "Export board report" submit action reuses this exact fetch/blob/download flow, extended with the D-03 period query params and a loading state per E4 "Generating…" spinner requirement):
```tsx
let resp = await fetch(`${API}/api/v1/export/summary?${params}`, { headers: { Authorization: `Bearer ${token}` } });
if (resp.status === 401) { /* refresh-and-retry, see full ExportButton.tsx block */ }
if (!resp.ok) return;
const blob = await resp.blob();
const url = URL.createObjectURL(blob);
const a = document.createElement('a'); a.href = url; a.download = filename; a.click();
URL.revokeObjectURL(url);
```

**D-04 scheduling-toggle disclosure** — no existing frontend precedent for the `ScheduledReport` CRUD UI was found in this session's search (no `ScheduledReport`-consuming `.tsx` file exists yet); the checkbox-reveals-inline-fields disclosure pattern itself has a precedent in `settings/notifications-pane.tsx` (found via grep, not read this session — flagged for the planner to open directly if the exact disclosure-toggle shape is needed).

---

### `frontend/src/components/shell/nav-items.ts` (extend — D-11)

**Analog:** itself (full file, 104 lines) — the exact array entry shape to copy.

**Pattern to copy** (L53-59, the two most recent additions, same array, same comment convention):
```ts
// Phase 41 (41-01, COV-01) — blind-spot detection list view. No chip per
// D-N-01 (not one of the three chip-carrying destinations).
{ label: 'Coverage', href: '/dashboard/coverage', icon: Radar },
// Phase 42 (42-01, TREND-01..03) — risk-trend analytics & burndown deep
// view. No chip per D-N-01 (not one of the three chip-carrying
// destinations).
{ label: 'Analytics', href: '/dashboard/analytics', icon: LineChart },
```
Add, in the same `WORKFLOW_ITEMS` array, after `Analytics`:
```ts
// Phase 43 (43-0X, RPT-03) — framework-control compliance posture view.
// No chip per D-N-01 (not one of the three chip-carrying destinations).
{ label: 'Compliance', href: '/dashboard/compliance', icon: ShieldCheck },
```
Import `ShieldCheck` (or `FileCheck`) from `lucide-react` alongside the existing icon imports at L5. No changes needed to `ALL_ITEMS`/`MORE_ITEMS`/`isActive` — they derive automatically from `WORKFLOW_ITEMS`.

---

## Shared Patterns

### Zero-denominator "not yet measured" discipline (cross-cutting: RPT-01, RPT-02, RPT-03)
**Source:** `backend/app/coverage/service.py::get_coverage_summary` (`coverage_pct = round(...) if total else None`, L192-193) + `frontend/src/lib/queries/use-analytics.ts`'s scored-point-count gating (L120-127).
**Apply to:** `compliance/catalog.py::evaluate_catalog` (None → `not_measured`, never a fabricated pass or fail), `compliance/service.py`'s metric computations, `export.py`'s new PDF sections (MTTR/SLA tables render "Not yet measured" text, never `0`), and every new frontend tile (MTTR tile, SLA tile, framework-posture strip) — gate on the metric's own `null` signal, never on a falsy/zero value.
```python
# The one-line idiom to replicate everywhere a new denominator-based % is computed:
pct = round(100 * numerator / denominator) if denominator else None
```

### Exception-exclusion predicate (cross-cutting: RPT-01, RPT-03)
**Source:** `backend/app/exceptions/service.py::active_exception_subquery`, already wired into `export.py::_collect_summary_data` (L329) and `analytics/service.py::_open_backlog_conditions` (L204) — NOT yet wired into `sla_service.py::get_sla_metrics`.
**Apply to:** the `sla_service.py` extension above (new `exclude_exceptions` param) — any new RPT-01/RPT-03 caller of `get_sla_metrics` MUST pass `exclude_exceptions=True` so the new PDF section / compliance control stays internally consistent with the rest of the same document/page (Pitfall 2).

### Tenant-scoped `require_viewer` read endpoint (cross-cutting: RPT-03)
**Source:** `backend/app/coverage/router.py::get_coverage_summary_endpoint` (L67-76) and `backend/app/analytics/router.py::get_analytics_overview_endpoint` (L43-101) — both use `Annotated[CurrentUser, Depends(require_viewer)]` and pass `user.tenant_id` inline into the service call, never a fetch-then-403.
**Apply to:** `compliance/router.py`'s new `GET /overview` — copy this shape exactly (RESEARCH.md V4 Access Control requirement).

### `ErrorBoundary` + `Suspense` page/section composition (cross-cutting: RPT-02, RPT-03)
**Source:** `frontend/src/app/(authed)/dashboard/page.tsx` (per-section `<ErrorBoundary>` wrapping, L69-88) and `frontend/src/app/(authed)/dashboard/analytics/page.tsx` (page-level `ErrorBoundary > Suspense > Inner`, L219-229).
**Apply to:** every new dashboard widget (wrap individually, matching the existing per-section isolation convention) and the new `/dashboard/compliance` page (wrap the whole page, matching Coverage/Analytics precedent).

### `useUrlState` client-persisted enum state (cross-cutting: RPT-01 period preset UI, RPT-02 lens)
**Source:** `frontend/src/hooks/use-url-state.ts` (full file) — already used by `TrendSection` (`range`) and `AnalyticsPageInner` (`window`).
**Apply to:** the RPT-02 lens switcher (`lens` key) directly; the RPT-01 export dialog's period preset is explicitly NOT `useUrlState`-based per 43-RESEARCH.md's Architectural Responsibility Map ("plain form state in the export dialog... a dialog, not a page") — use local `useState` there instead, mirroring `AnalyticsPageInner`'s own `customFrom`/`customTo` plain-`useState` treatment for its custom-range fields (L92-93).

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `backend/app/compliance/catalog.py` | model/utility | transform | No existing pure-data-catalog-with-thresholds module exists in this codebase; closest conceptual sibling (`assets/risk_score.py`'s tier constants) is far simpler (no per-item metric-mapping). Built directly from 43-RESEARCH.md's verified Code Examples section instead of a codebase analog. |
| Calendar-quarter date-math helper (used inside `main.py`/`export.py` for the `Last quarter` preset) | utility | transform | Zero existing "quarter" logic anywhere in the codebase (verified via grep in RESEARCH.md) — genuinely new logic; RESEARCH.md's `last_completed_quarter()` sketch is the reference implementation. |
| `frontend/src/components/dashboard/export-board-report-dialog.tsx`'s scheduling-toggle disclosure (D-04's "Also send this report {cadence} by email" checkbox) | component | request-response | No existing `.tsx` file consumes `ScheduledReport` yet (grep found zero matches) — `settings/notifications-pane.tsx` has a general checkbox-disclosure precedent but was not read this session; flagged for the planner to inspect directly if needed. |

## Metadata

**Analog search scope:** `backend/app/{export,reports,main,analytics,vulnerabilities,cspm,coverage}.py` and their packages; `frontend/src/app/(authed)/dashboard/**`, `frontend/src/components/{dashboard,analytics,coverage,exceptions,ui}/**`, `frontend/src/hooks/`, `frontend/src/lib/queries/`.
**Files scanned:** ~30 backend + ~20 frontend files (direct reads or targeted greps this session).
**Pattern extraction date:** 2026-08-22
