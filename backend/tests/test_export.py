"""Phase 43 Plan 02 (RPT-01) -- board-PDF chart rendering + new PDF
sections. Wave 0 gap: no prior `test_export.py` existed
(43-RESEARCH.md Validation Architecture).

Task 1 (chart-render helpers): headless matplotlib `Figure`+
`FigureCanvasAgg` only, never `pyplot` (Pitfall 5); PNG bytes decode via
PIL with `DISPLAY` unset; the risk-trend helper degrades to a neutral
"not enough history" note under 2 data points (E9), never a fabricated
line.
"""

from __future__ import annotations

import contextlib
import io
import re
import uuid
import zlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

from PIL import Image

from app.export import (
    _collect_summary_data,
    _render_mttr_by_tier_chart,
    _render_risk_trend_chart,
    _render_sla_compliance_chart,
    _sla_compliance_color,
    generate_executive_summary_pdf,
)
from app.vulnerabilities.models import Vulnerability
from app.vulnerabilities.service import mark_vulnerability_remediated
from app.vulnerabilities.sla_service import get_sla_metrics
from app.vulnerabilities.trends import DailySnapshot


def _assert_valid_png(buf: io.BytesIO) -> None:
    buf.seek(0)
    img = Image.open(buf)
    assert img.format == "PNG"
    img.verify()


# ── Chart-render helpers: headless, decodable, no-pyplot ───────────────────


def test_render_mttr_by_tier_chart_produces_decodable_png(monkeypatch):
    monkeypatch.delenv("DISPLAY", raising=False)
    buf = _render_mttr_by_tier_chart(
        ["Critical", "High", "Moderate"], [4.2, 12.8, 41.0], ["#DC2626", "#EA580C", "#B45309"]
    )
    assert isinstance(buf, io.BytesIO)
    _assert_valid_png(buf)


def test_render_sla_compliance_chart_produces_decodable_png(monkeypatch):
    monkeypatch.delenv("DISPLAY", raising=False)
    buf = _render_sla_compliance_chart(92.5, "#15803D")
    assert isinstance(buf, io.BytesIO)
    _assert_valid_png(buf)


def test_render_risk_trend_chart_produces_decodable_png_with_enough_history(monkeypatch):
    monkeypatch.delenv("DISPLAY", raising=False)
    trend = [
        {"date": "2026-06-01", "avg_risk_exposure_score": 40.0, "risk_model_version": "v1"},
        {"date": "2026-06-02", "avg_risk_exposure_score": 42.0, "risk_model_version": "v1"},
        {"date": "2026-06-03", "avg_risk_exposure_score": 38.0, "risk_model_version": "v1"},
    ]
    buf = _render_risk_trend_chart(trend, [], (79, 70, 229))
    assert isinstance(buf, io.BytesIO)
    _assert_valid_png(buf)


def test_render_risk_trend_chart_with_version_boundary_still_decodes(monkeypatch):
    monkeypatch.delenv("DISPLAY", raising=False)
    trend = [
        {"date": "2026-06-01", "avg_risk_exposure_score": 40.0, "risk_model_version": "v1"},
        {"date": "2026-06-02", "avg_risk_exposure_score": 45.0, "risk_model_version": "v2"},
        {"date": "2026-06-03", "avg_risk_exposure_score": 44.0, "risk_model_version": "v2"},
    ]
    boundaries = [{"date": "2026-06-02", "old_version": "v1", "new_version": "v2"}]
    buf = _render_risk_trend_chart(trend, boundaries, (79, 70, 229))
    assert isinstance(buf, io.BytesIO)
    _assert_valid_png(buf)


def test_render_risk_trend_chart_under_two_points_renders_not_enough_history_note(monkeypatch):
    """E9: fewer than 2 real data points must never render a fabricated or
    misleading line -- degrades to a neutral note instead."""
    monkeypatch.delenv("DISPLAY", raising=False)

    # Zero points.
    buf_zero = _render_risk_trend_chart([], [], (79, 70, 229))
    _assert_valid_png(buf_zero)

    # Exactly one real point (the second row's score is None -- a gap, not
    # a second plottable point).
    trend_one = [
        {"date": "2026-06-01", "avg_risk_exposure_score": 40.0, "risk_model_version": "v1"},
        {"date": "2026-06-02", "avg_risk_exposure_score": None, "risk_model_version": "v1"},
    ]
    buf_one = _render_risk_trend_chart(trend_one, [], (79, 70, 229))
    _assert_valid_png(buf_one)


def test_no_module_imports_matplotlib_pyplot():
    """Pitfall 5: pyplot's global mutable figure registry is a documented
    thread-safety hazard under concurrent web-request access -- grep the
    whole backend/app tree, not just export.py."""
    app_dir = Path(__file__).resolve().parent.parent / "app"
    pyplot_import_re = re.compile(r"^\s*(import matplotlib\.pyplot|from matplotlib import pyplot)\b", re.MULTILINE)
    offenders = []
    for path in app_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if pyplot_import_re.search(text):
            offenders.append(str(path))
    assert offenders == [], f"matplotlib.pyplot imported in: {offenders}"


# ── Task 2: 3 new PDF sections + get_mttr_by_tier period extension ─────────

_ALL_SECTIONS = [
    "vulns",
    "assets",
    "risk",
    "top_hosts",
    "top_remediations",
    "tickets",
    "risk_trend",
    "mttr_by_tier",
    "sla_compliance",
]


def _pdf_text_tokens(pdf_bytes: bytes) -> list[bytes]:
    """Test-only helper: fpdf2 content streams are FlateDecode-compressed
    by default, so a plain substring search over the raw PDF bytes can't
    see drawn text at all. Decompresses every `stream...endstream` block
    (stdlib `zlib` only -- no new dependency) and extracts every
    parenthesized `Tj` string-literal operand IN DRAW ORDER, which lets
    tests assert both section ORDER and literal rendered text (e.g. "Not
    yet measured") -- something a raw-bytes `in` check cannot do."""
    streams = re.findall(rb"stream\r?\n(.*?)\r?\nendstream", pdf_bytes, re.DOTALL)
    blob = b""
    for s in streams:
        with contextlib.suppress(zlib.error):
            # Not every stream is FlateDecode (e.g. a raw PNG XObject) --
            # irrelevant to text extraction, skip silently.
            blob += zlib.decompress(s)
    return re.findall(rb"\((.*?)\)\s*Tj", blob)


def _vuln_for_export(
    tenant_id: uuid.UUID,
    *,
    severity: str = "CRITICAL",
    risk_exposure_score: int | None = None,
    first_detected_at: datetime | None = None,
) -> Vulnerability:
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        cve_id=f"CVE-{uuid.uuid4().hex[:8]}",
        severity=severity,
        source="CROWDSTRIKE",
        status="OPEN",
        risk_exposure_score=risk_exposure_score,
        first_detected_at=first_detected_at or (now - timedelta(days=3)),
        last_seen_at=now,
    )


async def test_generate_executive_summary_pdf_with_new_sections_embeds_charts(db_session, tenant_a):
    today = datetime.now(UTC).date()
    for i, score in enumerate([40.0, 42.0, 38.0]):
        db_session.add(
            DailySnapshot(
                tenant_id=tenant_a,
                snapshot_date=today - timedelta(days=2 - i),
                metrics={"avg_risk_exposure_score": score, "risk_model_version_snapshot": "v1"},
                created_at=datetime.now(UTC),
            )
        )
    vuln = _vuln_for_export(tenant_a, risk_exposure_score=85)
    db_session.add(vuln)
    await db_session.flush()
    await mark_vulnerability_remediated(db_session, vuln)
    await db_session.commit()

    filters = {"sections": _ALL_SECTIONS, "period_start": today - timedelta(days=7), "period_end": today}
    pdf_bytes = bytes(await generate_executive_summary_pdf(db_session, tenant_a, filters))

    assert pdf_bytes.startswith(b"%PDF")
    # `/Subtype /Image` (not the looser `/Image`) is the precise marker for
    # an actual embedded XObject -- fpdf2's boilerplate page `/ProcSet`
    # array always lists `/ImageB /ImageC /ImageI` regardless of whether
    # any image is embedded, so a naive `/Image` substring check is a
    # false positive on every generated PDF.
    assert b"/Subtype /Image" in pdf_bytes


async def test_generate_executive_summary_pdf_without_new_sections_is_backward_compatible(db_session, tenant_a):
    """Task 2 acceptance: `sections` omitting the 3 new keys must not draw
    them at all -- byte-compatible with the pre-existing 6-section shape
    (no chart images, no new section headers)."""
    old_sections = ["vulns", "assets", "risk", "top_hosts", "top_remediations", "tickets"]
    pdf_bytes = bytes(await generate_executive_summary_pdf(db_session, tenant_a, {"sections": old_sections}))

    assert pdf_bytes.startswith(b"%PDF")
    assert b"/Subtype /Image" not in pdf_bytes  # no chart sections drawn, no logo configured on tenant_a
    joined = b" ".join(_pdf_text_tokens(pdf_bytes))
    for absent in (b"Risk Trend", b"MTTR by Risk Tier", b"SLA Compliance"):
        assert absent not in joined


async def test_new_sections_render_in_ui_spec_order(db_session, tenant_a):
    """Acceptance: risk trend -> MTTR by tier -> SLA compliance, after the
    existing Risk Distribution summary-stats block, before Top N Riskiest
    Hosts (43-UI-SPEC.md PDF Rendering Contract)."""
    pdf_bytes = bytes(await generate_executive_summary_pdf(db_session, tenant_a, {"sections": _ALL_SECTIONS}))
    tokens = [t.decode("latin-1") for t in _pdf_text_tokens(pdf_bytes)]

    def first_index(needle: str) -> int:
        return next(i for i, t in enumerate(tokens) if needle in t)

    idx_risk_dist = first_index("Risk Distribution")
    idx_trend = first_index("Risk Trend")
    idx_mttr = first_index("MTTR by Risk Tier")
    idx_sla = first_index("SLA Compliance")
    idx_top_hosts = first_index("Riskiest Hosts")

    assert idx_risk_dist < idx_trend < idx_mttr < idx_sla < idx_top_hosts


async def test_sla_compliance_section_renders_not_yet_measured_on_zero_remediation(db_session, tenant_a):
    """Pitfall 1: a zero-remediation tenant must never show a fabricated
    100% SLA-compliance figure -- proves both the underlying data
    (`remediated_total == 0`) and the actual rendered PDF text."""
    d = await _collect_summary_data(db_session, tenant_a, {"sections": ["sla_compliance"]})
    assert d["sla_compliance"]["remediated_total"] == 0

    pdf_bytes = bytes(await generate_executive_summary_pdf(db_session, tenant_a, {"sections": ["sla_compliance"]}))
    tokens = _pdf_text_tokens(pdf_bytes)
    assert any(b"Not yet measured" in t for t in tokens)
    assert not any(b"100.0%" in t or b"100%" in t for t in tokens)


async def test_collect_summary_data_sla_uses_exclude_exceptions(db_session, tenant_a):
    """Wiring proof (43-RESEARCH.md Pitfall 2): `_collect_summary_data`'s
    `sla_compliance` must be computed with `exclude_exceptions=True` -- an
    actively-excepted breached finding must not inflate the breach count,
    matching the rest of the same document's exception-exclusion
    convention."""
    from app.exceptions.models import ExceptionRecord

    now = datetime.now(UTC)
    excepted = Vulnerability(
        tenant_id=tenant_a,
        cve_id=f"CVE-{uuid.uuid4().hex[:8]}",
        severity="CRITICAL",
        source="CROWDSTRIKE",
        status="OPEN",
        first_detected_at=now - timedelta(days=10),
        last_seen_at=now,
        sla_due_at=now - timedelta(days=1),
        sla_breached=True,
    )
    plain_breached = Vulnerability(
        tenant_id=tenant_a,
        cve_id=f"CVE-{uuid.uuid4().hex[:8]}",
        severity="CRITICAL",
        source="CROWDSTRIKE",
        status="OPEN",
        first_detected_at=now - timedelta(days=10),
        last_seen_at=now,
        sla_due_at=now - timedelta(days=1),
        sla_breached=True,
    )
    db_session.add_all([excepted, plain_breached])
    await db_session.flush()
    grant = ExceptionRecord(
        tenant_id=tenant_a,
        type="ACCEPTED_RISK",
        scope_type="FINDING",
        cve_id=excepted.cve_id,
        vulnerability_id=excepted.id,
        asset_id=None,
        asset_group_id=None,
        justification="Compensating control in place.",
        approver_user_id=None,
        granted_by_user_id=None,
        expires_at=now + timedelta(days=30),
        revoked_at=None,
    )
    db_session.add(grant)
    await db_session.commit()

    d = await _collect_summary_data(db_session, tenant_a, {"sections": ["sla_compliance"]})
    assert d["sla_compliance"]["breached"] == 1  # only plain_breached; excepted is excluded

    direct = await get_sla_metrics(db_session, tenant_a, exclude_exceptions=True)
    assert d["sla_compliance"] == direct


async def test_collect_summary_data_skips_new_section_queries_when_not_requested(db_session, tenant_a):
    """Efficiency + backward-compat: omitting the 3 new keys from
    `sections` skips their computation entirely -- CSV/txt exports and any
    caller with a narrower `sections` list pay zero extra query cost."""
    d = await _collect_summary_data(db_session, tenant_a, {"sections": ["vulns"]})
    assert d["risk_trend"] == {}
    assert d["mttr_by_tier"] == {}
    assert d["sla_compliance"] == {}


def test_sla_compliance_color_thresholds():
    assert _sla_compliance_color(100.0) == "#15803D"
    assert _sla_compliance_color(95.0) == "#15803D"
    assert _sla_compliance_color(94.9) == "#B45309"
    assert _sla_compliance_color(80.0) == "#B45309"
    assert _sla_compliance_color(79.9) == "#DC2626"
    assert _sla_compliance_color(0.0) == "#DC2626"
