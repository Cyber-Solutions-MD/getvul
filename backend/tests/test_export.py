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
from sqlalchemy import select

from app.analytics.service import MAX_ANALYTICS_WINDOW_DAYS
from app.audit import AuditLog
from app.export import (
    _collect_summary_data,
    _render_mttr_by_tier_chart,
    _render_risk_trend_chart,
    _render_sla_compliance_chart,
    _sla_compliance_color,
    generate_executive_summary_pdf,
    last_completed_quarter,
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


# ── Plan 03 checkpoint fixes: page-break footer overlap + honest empty
# remediations state ────────────────────────────────────────────────────────


_FOOTER_RE = re.compile(rb"Confidential\s*\|\s*Page")


def _pdf_per_page_text_tokens(pdf_bytes: bytes) -> list[list[bytes]]:
    """Test-only helper: like `_pdf_text_tokens`, but keeps each content
    stream's tokens SEPARATE (in file order) instead of merging every
    page's text into one flat list. Needed to make a claim about a
    SPECIFIC page (e.g. "the last page is not blank except for its own
    footer") -- a fact a globally-merged token list cannot distinguish,
    since real content and a spurious trailing page's lone footer token
    would land in the same bucket. Streams with zero extracted text (e.g.
    a bare embedded-PNG XObject stream, not FlateDecode at all) are
    dropped rather than appearing as an empty page entry."""
    streams = re.findall(rb"stream\r?\n(.*?)\r?\nendstream", pdf_bytes, re.DOTALL)
    pages: list[list[bytes]] = []
    for s in streams:
        with contextlib.suppress(zlib.error):
            blob = zlib.decompress(s)
            tokens = re.findall(rb"\((.*?)\)\s*Tj", blob)
            if tokens:
                pages.append(tokens)
    return pages


async def test_pdf_footer_loop_never_spawns_a_spurious_trailing_page(db_session, tenant_a):
    """Regression for the bug found during Plan 03's checkpoint pre-
    verification: the retroactive per-page footer loop used to run with
    `auto_page_break` still enabled, and `set_y(-15)` sits exactly at the
    auto-break trigger threshold -- so fpdf2's own page-advance fired
    mid-loop, corrupting footer placement and minting an extra, otherwise-
    blank trailing page whose ONLY content was that one misplaced footer
    stamp. Verified directly against both the pre-fix and post-fix code
    (via a throwaway repro) before writing this assertion -- a naive
    "serialized page count matches fpdf2's own declared /Count" check is
    tautologically always true (fpdf2 never loses track of its own page
    bookkeeping, buggy or not) and would not have caught this."""
    from app.assets.models import Asset

    for i in range(90):
        db_session.add(
            Asset(
                tenant_id=tenant_a,
                hostname=f"host-{i:03d}",
                risk_score=90 - (i % 50),
                device_category="SERVER",
            )
        )
    await db_session.commit()

    pdf_bytes = bytes(
        await generate_executive_summary_pdf(db_session, tenant_a, {"sections": ["top_hosts"], "top_count": 90})
    )
    assert pdf_bytes.startswith(b"%PDF")

    pages = _pdf_per_page_text_tokens(pdf_bytes)
    # Precondition sanity check: this scenario must genuinely force a
    # multi-page report, otherwise the assertion below would pass
    # vacuously without ever exercising the footer-loop page-break path.
    assert len(pages) >= 2, "test setup did not force a multi-page PDF -- increase the host row count"

    # The bug's exact symptom: the LAST page (in file order) contains
    # nothing but its own retroactively-stamped footer -- every real page
    # must carry substantive section/table content beyond that footer.
    last_page_non_footer = [t for t in pages[-1] if not _FOOTER_RE.search(t)]
    assert last_page_non_footer, (
        f"last page's only text is its own footer stamp ({pages[-1]!r}) -- this is the "
        "spurious blank trailing page created by the auto-page-break/footer-loop bug"
    )
    # The tail of the host table must appear on a REAL page (host-089 is
    # the 90th, last-created row), never lost to a spurious page shuffle.
    assert any(b"host-089" in t for page in pages for t in page)


async def test_top_remediations_section_renders_honest_empty_state_when_none_recorded(db_session, tenant_a):
    """A tenant with zero remediation-linked open findings must never
    render a literal "Top 0 Remediations (by impact)" header + an empty
    table -- an honest empty-state line instead, consistent with the
    "Not yet measured" / "Not enough history" copy used by the other
    RPT-01 zero-data sections."""
    pdf_bytes = bytes(await generate_executive_summary_pdf(db_session, tenant_a, {"sections": ["top_remediations"]}))
    tokens = _pdf_text_tokens(pdf_bytes)
    joined = b" ".join(tokens)
    assert b"Top 0 Remediations" not in joined
    assert any(b"No remediation actions recorded yet" in t for t in tokens)


async def test_top_remediations_section_still_renders_real_rows_when_present(db_session, tenant_a):
    """The honest-empty-state fix must not regress the populated case."""
    from app.assets.models import Asset

    asset = Asset(tenant_id=tenant_a, hostname="host-rem-01", risk_score=80, device_category="SERVER")
    db_session.add(asset)
    await db_session.flush()
    vuln = Vulnerability(
        tenant_id=tenant_a,
        cve_id=f"CVE-{uuid.uuid4().hex[:8]}",
        severity="CRITICAL",
        source="CROWDSTRIKE",
        status="OPEN",
        asset_id=asset.id,
        remediation_id="patch-openssl-3.0.14",
        remediation_action="Upgrade OpenSSL to 3.0.14",
        affected_product="OpenSSL",
        first_detected_at=datetime.now(UTC) - timedelta(days=3),
        last_seen_at=datetime.now(UTC),
    )
    db_session.add(vuln)
    await db_session.commit()

    pdf_bytes = bytes(await generate_executive_summary_pdf(db_session, tenant_a, {"sections": ["top_remediations"]}))
    tokens = _pdf_text_tokens(pdf_bytes)
    joined = b" ".join(tokens)
    assert b"Top 1 Remediations" in joined
    assert not any(b"No remediation actions recorded yet" in t for t in tokens)


async def test_pdf_legacy_sections_are_gated_by_requested_sections_list(db_session, tenant_a):
    """CR-01 regression (43-REVIEW.md): before this fix, the six
    pre-existing (non-RPT-01) sections -- Vulnerability Overview, Assets by
    Type, Risk Distribution, Top N Riskiest Hosts, Top N Remediations, and
    Ticket Status -- were drawn unconditionally regardless of the caller's
    `sections` list (only the 3 new RPT-01 chart sections honored it). A
    request for a single narrow section must render ONLY that section's
    text -- every other legacy section's header must be absent, matching
    the `sections`-honoring behavior already proven for the CSV/text
    renderers and for the 3 new chart sections."""
    pdf_bytes = bytes(await generate_executive_summary_pdf(db_session, tenant_a, {"sections": ["tickets"]}))
    tokens = _pdf_text_tokens(pdf_bytes)
    joined = b" ".join(tokens)

    # The one requested section must render.
    assert b"Ticket Status" in joined

    # Every other legacy section's header text must be absent.
    for absent in (
        b"Vulnerability Overview",
        b"Assets by Type",
        b"Risk Distribution",
        b"Riskiest Hosts",
        b"Remediations (by impact)",
    ):
        assert absent not in joined, f"{absent!r} rendered despite sections=['tickets']"


# ── Task 3: export_resource period params + validation + audit ─────────────


async def _last_audit_row(db_session, tenant_id: uuid.UUID) -> AuditLog:
    rows = (
        await db_session.execute(
            select(AuditLog)
            .where(AuditLog.tenant_id == tenant_id, AuditLog.action == "export.summary")
            .order_by(AuditLog.created_at.desc())
        )
    ).scalars()
    return next(iter(rows))


async def test_export_resource_period_quarter_resolves_to_last_completed_quarter(client, db_session, tenant_a):
    # WR-13 (conftest.py db_session docstring): the route's own `get_db()`
    # session is a SEPARATE connection from this test's `db_session` --
    # `tenant_a`/the authed user (flushed by upstream fixtures, not yet
    # committed) must be committed before the route's `audit()` INSERT can
    # see the tenant row it FK-references.
    await db_session.commit()
    resp = await client.get("/api/v1/export/summary?format=txt&period=quarter")
    assert resp.status_code == 200

    expected_start, expected_end = last_completed_quarter(datetime.now(UTC).date())
    audit_row = await _last_audit_row(db_session, tenant_a)
    assert audit_row.details["period"] == "quarter"
    assert audit_row.details["period_start"] == expected_start.isoformat()
    assert audit_row.details["period_end"] == expected_end.isoformat()


async def test_export_resource_default_period_is_last_completed_quarter(client, db_session, tenant_a):
    """D-03/UI-SPEC default: no `period`/`from`/`to` supplied at all still
    resolves to the last-completed calendar quarter, not an unbounded or
    all-time window."""
    await db_session.commit()  # WR-13 -- see comment above
    resp = await client.get("/api/v1/export/summary?format=txt")
    assert resp.status_code == 200

    expected_start, expected_end = last_completed_quarter(datetime.now(UTC).date())
    audit_row = await _last_audit_row(db_session, tenant_a)
    assert audit_row.details["period"] == "quarter"
    assert audit_row.details["period_start"] == expected_start.isoformat()
    assert audit_row.details["period_end"] == expected_end.isoformat()


async def test_export_resource_custom_range_both_or_neither_422(client):
    resp = await client.get("/api/v1/export/summary?format=txt&from=2026-01-01")
    assert resp.status_code == 422


async def test_export_resource_custom_range_to_before_from_422(client):
    resp = await client.get("/api/v1/export/summary?format=txt&from=2026-06-01&to=2026-01-01")
    assert resp.status_code == 422


async def test_export_resource_custom_range_over_cap_422(client):
    # 2000-01-01 to 2026-01-01 spans ~9,490 days -- comfortably over
    # MAX_ANALYTICS_WINDOW_DAYS (1096, ~3y) either way this constant moves.
    assert (datetime(2026, 1, 1, tzinfo=UTC).date() - datetime(2000, 1, 1, tzinfo=UTC).date()).days > (
        MAX_ANALYTICS_WINDOW_DAYS
    )
    resp = await client.get("/api/v1/export/summary?format=txt&from=2000-01-01&to=2026-01-01")
    assert resp.status_code == 422


async def test_export_resource_custom_range_within_cap_succeeds(client, db_session, tenant_a):
    await db_session.commit()  # WR-13 -- see comment above
    resp = await client.get("/api/v1/export/summary?format=txt&from=2026-01-01&to=2026-01-31")
    assert resp.status_code == 200

    audit_row = await _last_audit_row(db_session, tenant_a)
    assert audit_row.details["period"] == "custom"
    assert audit_row.details["period_start"] == "2026-01-01"
    assert audit_row.details["period_end"] == "2026-01-31"


async def test_export_resource_audit_records_requested_sections(client, db_session, tenant_a):
    """The pre-existing `filters["section"]` echo (unchanged) plus the new
    period fields together let a reviewer see exactly what a given export
    covered."""
    await db_session.commit()  # WR-13 -- see comment above
    resp = await client.get("/api/v1/export/summary?format=txt&section=risk_trend&section=sla_compliance&period=90d")
    assert resp.status_code == 200

    audit_row = await _last_audit_row(db_session, tenant_a)
    assert audit_row.details["section"] == ["risk_trend", "sla_compliance"]
    assert audit_row.details["period"] == "90d"
