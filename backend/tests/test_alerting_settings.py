"""Phase 40 Plan 04 (ALERT-03) -- `alerting_config` PATCH /settings save
path (validation/persistence/audit) + the `POST /settings/alerting/
test-digest` single-recipient preview endpoint.

Originally scaffolded in Plan 01 as 3 `xfail(strict=False)` RED tests (the
validation gate / persistence branch / audit action did not exist yet) plus
1 genuinely-passing `test_patch_requires_owner` (the route-wide
`Depends(require_owner)` gate already covered any body). Plan 04 implements
`AlertingConfigUpdate`, the `if "alerting_config" in body:` branch, and the
`alerting.config_update` audit action -- the three xfail markers are removed
here since the behavior is now real, not just expected-to-eventually-pass.

Test names match the Phase Requirements -> Test Map (40-RESEARCH.md:448-470).
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import patch

from sqlalchemy import select

from app.audit import AuditLog
from app.tenants.models import Tenant

SETTINGS_URL = "/api/v1/tenant/settings"
TEST_DIGEST_URL = "/api/v1/tenant/settings/alerting/test-digest"


async def _get_tenant(db_session: Any, tenant_id: uuid.UUID) -> Tenant:
    """Fetch + force-refresh the Tenant row (identity-map staleness guard --
    mirrors test_sla_policy.py's `_get_tenant` helper)."""
    tenant = (await db_session.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one()
    await db_session.refresh(tenant)
    return tenant


async def test_alerting_config_validates_bounds(client_factory: Any, owner_user: Any, db_session: Any) -> None:
    """An out-of-bounds `epss_threshold` (must be 0.0-1.0 per
    DEFAULT_ALERTING_CONFIG's shape) must 422, mirroring SlaConfigUpdate's
    `approaching_pct` bound check (tenants/router.py)."""
    await db_session.commit()
    client = client_factory(owner_user)
    resp = await client.patch(SETTINGS_URL, json={"alerting_config": {"epss_threshold": 1.5}})
    assert resp.status_code in (400, 422), resp.text


async def test_alerting_config_persists_to_jsonb(
    client_factory: Any, owner_user: Any, db_session: Any, tenant_a: uuid.UUID
) -> None:
    await db_session.commit()
    client = client_factory(owner_user)
    body = {"kev_enabled": True, "epss_threshold": 0.6, "cadence": "daily", "send_hour": 9}
    resp = await client.patch(SETTINGS_URL, json={"alerting_config": body})
    assert resp.status_code == 200, resp.text

    tenant = await _get_tenant(db_session, tenant_a)
    assert tenant.alerting_config is not None
    assert tenant.alerting_config["epss_threshold"] == 0.6
    assert tenant.alerting_config["send_hour"] == 9


async def test_alerting_config_change_audited(
    client_factory: Any, owner_user: Any, db_session: Any, tenant_a: uuid.UUID
) -> None:
    await db_session.commit()
    client = client_factory(owner_user)
    resp = await client.patch(SETTINGS_URL, json={"alerting_config": {"epss_threshold": 0.6}})
    assert resp.status_code == 200, resp.text

    rows = (
        (
            await db_session.execute(
                select(AuditLog).where(AuditLog.tenant_id == tenant_a, AuditLog.action == "alerting.config_update")
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1, f"expected exactly one alerting.config_update audit row, got {len(rows)}"
    # Mirrors sla.policy_update's secret-free convention (D-19: alerting_config
    # never holds channel secrets in the first place, but the audit row must
    # not accidentally widen to include one via a future field addition).
    assert "channels" not in rows[0].details


async def test_patch_requires_owner(client_factory: Any, analyst_user: Any) -> None:
    """The existing `/settings` PATCH handler already requires Owner for
    ANY body -- this must hold for `alerting_config` too, and already does
    today (not a RED test; require_owner is a pre-existing, route-wide gate)."""
    client = client_factory(analyst_user)
    resp = await client.patch(SETTINGS_URL, json={"alerting_config": {"epss_threshold": 0.6}})
    assert resp.status_code == 403


# ── POST /settings/alerting/test-digest (Task 2) ────────────────────────────


async def test_test_digest_requires_admin(client_factory: Any, viewer_user: Any) -> None:
    """T-40-18: the test-digest send primitive is admin-gated, not merely
    analyst/viewer-readable -- a Viewer must be rejected."""
    client = client_factory(viewer_user)
    resp = await client.post(TEST_DIGEST_URL)
    assert resp.status_code == 403


async def test_test_digest_empty_when_no_findings(client_factory: Any, admin_user: Any, db_session: Any) -> None:
    """D-14: a tenant with nothing to report gets a distinguishable "empty"
    status, never a false "error"."""
    await db_session.commit()
    client = client_factory(admin_user)
    resp = await client.post(TEST_DIGEST_URL)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "empty"


async def test_test_digest_error_when_smtp_not_configured(
    client_factory: Any, admin_user: Any, db_session: Any, tenant_a: uuid.UUID, kev_epss_finding: Any
) -> None:
    """A tenant with digest content but no SMTP configured gets a
    distinguishable "error" status, not a silent 200 "sent"."""
    tenant = await _get_tenant(db_session, tenant_a)
    tenant.smtp_config = None
    await db_session.commit()

    client = client_factory(admin_user)
    resp = await client.post(TEST_DIGEST_URL)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "error"
    assert body.get("error")


async def test_test_digest_sent_targets_only_acting_admin(
    client_factory: Any, admin_user: Any, db_session: Any, tenant_a: uuid.UUID, kev_epss_finding: Any
) -> None:
    """The preview send must target ONLY the acting admin's own email --
    never a tenant-wide recipient list (T-40-18: no broadcast from a
    preview action)."""
    tenant = await _get_tenant(db_session, tenant_a)
    tenant.smtp_config = {"enabled": True, "host": "smtp.test.local", "from_email": "alerts@test.local"}
    await db_session.commit()

    client = client_factory(admin_user)
    with patch("app.email.send_email", return_value={"ok": True}) as mock_send:
        resp = await client.post(TEST_DIGEST_URL)

    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "sent"
    assert mock_send.call_count == 1
    assert mock_send.call_args.kwargs["to"] == [admin_user.email]
