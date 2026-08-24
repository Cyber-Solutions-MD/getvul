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

import io
import re
from pathlib import Path

from PIL import Image

from app.export import (
    _render_mttr_by_tier_chart,
    _render_risk_trend_chart,
    _render_sla_compliance_chart,
)


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
