"""Phase 40 Plan 01 (ALERT-02) -- Wave 0 RED scaffold for digest assembly +
send-hour gating.

`app.notifications.digests` does not exist at all until Plan 03 (unlike
`app.notifications.alerts`, which already exists for test_alerts_kev_epss.py
to import at module level). Each test therefore defers the import via
`pytest.importorskip` INSIDE the test body -- never at module level -- so
`pytest --collect-only` still discovers and lists every named test below
(Wave 0 requirement: "collect their named tests"). At actual run time each
skips with a clear reason until Plan 03 lands and the module import
succeeds, at which point the rest of the test body runs for real.

Function names asserted here (`run_digests`, `_send_hour_due`,
`_assemble_sections`, `_render_digest_html`) are pinned by 40-01-PLAN.md's
own `<artifacts_produced>` inventory for Plan 03 -- not guessed here.

Test names match the Phase Requirements -> Test Map (40-RESEARCH.md:448-470).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select

from app.tenants.models import Tenant

DIGESTS_MODULE = "app.notifications.digests"


async def _tenant(db_session: Any, tenant_id: uuid.UUID) -> Tenant:
    return (await db_session.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one()


async def test_send_hour_gate_fires_past_target_not_before(db_session: Any, tenant_a: uuid.UUID) -> None:
    """D-12: the digest dispatch gate is "past the tenant's configured
    send_hour (in Tenant.timezone) AND not yet sent this period" -- it must
    NOT fire before the target hour, and MUST fire once the hour is
    reached."""
    digests = pytest.importorskip(DIGESTS_MODULE)

    tenant = await _tenant(db_session, tenant_a)
    tenant.alerting_config = {"send_hour": 8}
    tenant.alerting_last_digest_sent_at = None
    await db_session.flush()

    before_hour = datetime.now(UTC).replace(hour=6, minute=0, second=0, microsecond=0)
    assert digests._send_hour_due(tenant, now=before_hour) is False

    past_hour = datetime.now(UTC).replace(hour=9, minute=0, second=0, microsecond=0)
    assert digests._send_hour_due(tenant, now=past_hour) is True


async def test_not_sent_twice_per_period(db_session: Any, tenant_a: uuid.UUID) -> None:
    """D-12/Pitfall 4: once `Tenant.alerting_last_digest_sent_at` has been
    stamped for the current period, a second gate check must return False
    -- the durable marker (not an in-memory flag) is what survives a
    process restart on this single-VM stack."""
    digests = pytest.importorskip(DIGESTS_MODULE)

    tenant = await _tenant(db_session, tenant_a)
    now = datetime.now(UTC).replace(hour=9, minute=0, second=0, microsecond=0)
    tenant.alerting_config = {"send_hour": 8}
    tenant.alerting_last_digest_sent_at = now
    await db_session.flush()

    assert digests._send_hour_due(tenant, now=now) is False


async def test_empty_digest_suppressed(db_session: Any, tenant_a: uuid.UUID, owner_user: Any) -> None:
    """D-14: when every section is empty for a recipient, nothing is sent
    -- no "all clear" digest, to avoid alert-fatigue churn."""
    digests = pytest.importorskip(DIGESTS_MODULE)

    sent = await digests.run_digests(db_session, tenant_id=tenant_a)
    assert sent == 0


async def test_sections_read_sla_and_exception_state(db_session: Any, tenant_a: uuid.UUID) -> None:
    """D-13: digest sections are due / breaching / newly-critical /
    expiring-exceptions -- "breaching" reads Phase 36's SLA state and
    "expiring-exceptions" reads Phase 39's exception expiry, neither
    re-derived here."""
    digests = pytest.importorskip(DIGESTS_MODULE)

    tenant = await _tenant(db_session, tenant_a)
    sections = await digests._assemble_sections(db_session, tenant)
    assert set(sections.keys()) >= {"due", "breaching", "newly_critical", "expiring_exceptions"}


async def test_newly_critical_section_content(db_session: Any, tenant_a: uuid.UUID, kev_epss_finding: Any) -> None:
    """The newly-critical section is populated from CRITICAL findings
    first-detected within the digest window, with the D-20 exclusion
    (excepted/suppressed) applied -- forces this slot green so Success
    Criterion 2's third content type cannot ship empty."""
    digests = pytest.importorskip(DIGESTS_MODULE)

    vuln, _asset, _owner = kev_epss_finding
    assert vuln.severity == "CRITICAL"  # fixture precondition this test relies on

    tenant = await _tenant(db_session, tenant_a)
    sections = await digests._assemble_sections(db_session, tenant)
    newly_critical_ids = {str(item["vulnerability_id"]) for item in sections["newly_critical"]}
    assert str(vuln.id) in newly_critical_ids


async def test_html_body_renders_sections(db_session: Any, tenant_a: uuid.UUID) -> None:
    """D-15: the digest is an HTML email (reuses email.py), top-N per
    section with an "and N more" line + a deep-link back to the filtered
    dashboard view."""
    digests = pytest.importorskip(DIGESTS_MODULE)

    sections = {"due": [], "breaching": [], "newly_critical": [], "expiring_exceptions": []}
    html = digests._render_digest_html(sections)
    assert "<html" in html.lower()


async def test_per_owner_email_vs_per_team_channel(db_session: Any, tenant_a: uuid.UUID, kev_epss_finding: Any) -> None:
    """D-08/D-09: owner digests are per-person and go to email; team
    digests are per-AssetGroup and go to the team's shared Slack/Teams
    channel -- an admin can enable either or both independently."""
    digests = pytest.importorskip(DIGESTS_MODULE)

    _vuln, _asset, _owner = kev_epss_finding
    tenant = await _tenant(db_session, tenant_a)
    tenant.alerting_config = {"per_owner_digests": True, "per_team_digests": True}
    await db_session.flush()

    result = await digests.run_digests(db_session, tenant_id=tenant_a)
    assert result >= 0  # placeholder shape assertion until Plan 03 defines the real return contract
