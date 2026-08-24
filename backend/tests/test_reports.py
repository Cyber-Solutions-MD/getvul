"""Phase 43 Plan 02 (RPT-01 D-04) -- scheduled board reports. Wave 0 gap:
no prior `test_reports.py` existed (43-RESEARCH.md Validation
Architecture) -- `backend/app/reports.py` had zero automated coverage.

Covers the `ScheduledReport` CRUD default `sections` list (kept in
lockstep with `export.py::_collect_summary_data`'s own default,
appended-only per 43-UI-SPEC.md -- "existing scheduled reports don't
silently change shape") and `run_due_reports`/`_is_due`/`_send_report`
picking up a report carrying the 3 new section keys, generating the
extended PDF via the pre-existing SMTP delivery path (no second delivery
codepath, D-04).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.reports import ScheduledReport, _is_due, _send_report, create_report, run_due_reports
from app.tenants.models import Tenant

_OLD_SHAPE = ["vulns", "assets", "risk", "top_hosts", "top_remediations", "tickets"]
_NEW_SECTION_KEYS = ["risk_trend", "mttr_by_tier", "sla_compliance"]


def _bypass_report_file_archive(monkeypatch) -> None:
    """`_send_report` hardcodes `/app/reports` as the report-file archive
    path -- the real, writable WORKDIR inside the deployed Docker image,
    but absent both in this local sandbox and in CI's bare
    `ubuntu-latest` backend job (no `container:`, confirmed via
    `.github/workflows/ci.yml`). No-ops the filesystem write for tests
    (pure test-isolation, no production code change) -- everything else
    this suite actually asserts on (filters wiring, SMTP send, audit
    status) is unaffected."""
    monkeypatch.setattr(Path, "mkdir", lambda self, *a, **kw: None)
    monkeypatch.setattr(Path, "write_bytes", lambda self, data: None)
    monkeypatch.setattr(Path, "write_text", lambda self, data: None)


# ── create_report's own default (call site 1) ──────────────────────────────


async def test_create_report_default_sections_appends_new_keys_at_the_end(db_session, tenant_a):
    """43-PATTERNS.md: appended-only, never inserted mid-list -- the
    original 6-key shape is preserved verbatim as a prefix."""
    report = await create_report(db_session, tenant_a, {"name": "Board Report", "recipients": ["ciso@example.test"]})

    assert report["sections"][: len(_OLD_SHAPE)] == _OLD_SHAPE
    assert report["sections"][len(_OLD_SHAPE) :] == _NEW_SECTION_KEYS


async def test_create_report_explicit_sections_are_not_overridden(db_session, tenant_a):
    """An explicit `sections` list passed by the caller is stored as-is --
    the default is only a fallback for an omitted key."""
    explicit = ["vulns", "risk_trend"]
    report = await create_report(db_session, tenant_a, {"name": "Custom", "recipients": [], "sections": explicit})
    assert report["sections"] == explicit


# ── _send_report's fallback (call site 2) ───────────────────────────────────


async def test_send_report_fallback_sections_appends_new_keys_when_report_sections_empty(
    monkeypatch, db_session, tenant_a
):
    """A pre-existing `ScheduledReport` row with `sections=None` (predating
    this phase) must still pick up the new default when sent, matching
    `create_report`'s own default (kept in lockstep)."""
    captured: dict[str, Any] = {}

    async def fake_generate_pdf(db, tenant_id, filters):
        captured["filters"] = filters
        return b"%PDF-fake"

    monkeypatch.setattr("app.export.generate_executive_summary_pdf", fake_generate_pdf)
    _bypass_report_file_archive(monkeypatch)

    report = ScheduledReport(
        tenant_id=tenant_a,
        name="Legacy Report",
        schedule="weekly",
        format="pdf",
        recipients=[],
        sections=None,
        filters={},
        is_enabled=True,
        created_at=datetime.now(UTC),
    )
    db_session.add(report)
    await db_session.commit()

    await _send_report(db_session, report)

    sections = captured["filters"]["sections"]
    assert sections[: len(_OLD_SHAPE)] == _OLD_SHAPE
    assert sections[len(_OLD_SHAPE) :] == _NEW_SECTION_KEYS


async def test_send_report_preserves_explicit_old_shape_sections_unchanged(monkeypatch, db_session, tenant_a):
    """Existing scheduled reports keep their exact shape (must_haves
    truth): a report that already has an explicit 6-key `sections` list
    (predating this phase) is sent with exactly that list -- the new
    default only ever applies when `sections` is falsy, never overriding
    an explicit pre-existing choice."""
    captured: dict[str, Any] = {}

    async def fake_generate_pdf(db, tenant_id, filters):
        captured["filters"] = filters
        return b"%PDF-fake"

    monkeypatch.setattr("app.export.generate_executive_summary_pdf", fake_generate_pdf)
    _bypass_report_file_archive(monkeypatch)

    report = ScheduledReport(
        tenant_id=tenant_a,
        name="Old Report",
        schedule="weekly",
        format="pdf",
        recipients=[],
        sections=list(_OLD_SHAPE),
        filters={},
        is_enabled=True,
        created_at=datetime.now(UTC),
    )
    db_session.add(report)
    await db_session.commit()

    await _send_report(db_session, report)

    assert captured["filters"]["sections"] == _OLD_SHAPE


# ── run_due_reports / _is_due -- the extended PDF over the existing SMTP path ──


async def test_run_due_reports_picks_up_new_section_keys_and_sends_via_existing_smtp_path(
    monkeypatch, db_session, tenant_a
):
    """Task 3 behavior: a ScheduledReport carrying the 3 new section keys
    is picked up by `run_due_reports`/`_is_due` and generates the extended
    PDF via `_send_report`, reusing the existing SMTP delivery path (no
    second delivery codepath)."""
    captured: dict[str, Any] = {}

    async def fake_generate_pdf(db, tenant_id, filters):
        captured["filters"] = filters
        return b"%PDF-fake"

    def fake_send_email(**kwargs: Any) -> dict[str, Any]:
        captured["email_kwargs"] = kwargs
        return {"ok": True}

    monkeypatch.setattr("app.export.generate_executive_summary_pdf", fake_generate_pdf)
    _bypass_report_file_archive(monkeypatch)
    monkeypatch.setattr("app.email.send_email", fake_send_email)

    tenant = (await db_session.execute(select(Tenant).where(Tenant.id == tenant_a))).scalar_one()
    tenant.smtp_config = {"enabled": True, "host": "smtp.example.test"}
    await db_session.flush()

    report = ScheduledReport(
        tenant_id=tenant_a,
        name="Board Report",
        schedule="daily",
        format="pdf",
        recipients=["ciso@example.test"],
        sections=[*_OLD_SHAPE, *_NEW_SECTION_KEYS],
        filters={},
        is_enabled=True,
        last_sent_at=None,
        created_at=datetime.now(UTC),
    )
    db_session.add(report)
    await db_session.commit()

    assert _is_due(report, datetime.now(UTC)) is True  # never sent -> due immediately

    result = await run_due_reports(db_session)

    assert result["sent"] == 1
    assert captured["filters"]["sections"] == [*_OLD_SHAPE, *_NEW_SECTION_KEYS]
    assert captured["email_kwargs"]["to"] == ["ciso@example.test"]

    await db_session.refresh(report)
    assert report.last_send_status == "SUCCESS"


async def test_run_due_reports_not_due_yet_is_skipped(db_session, tenant_a):
    """A report sent recently (within its cadence window) is not re-sent
    -- `_is_due` gates the scheduler tick, not just a smoke check."""
    now = datetime.now(UTC)
    report = ScheduledReport(
        tenant_id=tenant_a,
        name="Just Sent",
        schedule="daily",
        format="pdf",
        recipients=[],
        sections=[*_OLD_SHAPE, *_NEW_SECTION_KEYS],
        filters={},
        is_enabled=True,
        last_sent_at=now,
        created_at=now,
    )
    db_session.add(report)
    await db_session.commit()

    assert _is_due(report, now) is False

    result = await run_due_reports(db_session)
    assert result["sent"] == 0
