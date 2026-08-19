"""Phase 40 Plan 01 (ALERT-03) -- Wave 0 RED scaffold for the
`alerting_config` PATCH /settings save path + its audit action.

Drives the REAL existing `/api/v1/tenant/settings` PATCH handler (mirrors
test_sla_policy.py's harness) -- the route already exists and already
requires Owner (`Depends(require_owner)`, tenants/router.py, D-10 RBAC
asymmetry) for ANY body, so `test_patch_requires_owner` is a genuine,
currently-PASSING test, not a RED one (Task 3's instruction marks
unimplemented assertions xfail "ONLY where the symbol does not yet exist" --
require_owner already exists and is already wired to this exact route).

The other three tests assert behavior that ships in Phase 40 Plan 04
(`AlertingConfigUpdate` validation, the `if "alerting_config" in body:`
persistence branch, and the `alerting.config_update` audit action) -- each
marked `xfail(strict=False)` until then. Today, an unrecognized
"alerting_config" key in the PATCH body is silently accepted (200) and
NOT persisted (falls through to the generic `changed` audit dict, never
`tenant.alerting_config`), which is exactly what makes these three fail
meaningfully right now.

Test names match the Phase Requirements -> Test Map (40-RESEARCH.md:448-470).
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import select

from app.audit import AuditLog
from app.tenants.models import Tenant

SETTINGS_URL = "/api/v1/tenant/settings"


async def _get_tenant(db_session: Any, tenant_id: uuid.UUID) -> Tenant:
    """Fetch + force-refresh the Tenant row (identity-map staleness guard --
    mirrors test_sla_policy.py's `_get_tenant` helper)."""
    tenant = (await db_session.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one()
    await db_session.refresh(tenant)
    return tenant


@pytest.mark.xfail(strict=False, reason="AlertingConfigUpdate validation gate ships in Phase 40 Plan 04")
async def test_alerting_config_validates_bounds(client_factory: Any, owner_user: Any, db_session: Any) -> None:
    """An out-of-bounds `epss_threshold` (must be 0.0-1.0 per
    DEFAULT_ALERTING_CONFIG's shape) must 422, mirroring SlaConfigUpdate's
    `approaching_pct` bound check (tenants/router.py)."""
    await db_session.commit()
    client = client_factory(owner_user)
    resp = await client.patch(SETTINGS_URL, json={"alerting_config": {"epss_threshold": 1.5}})
    assert resp.status_code in (400, 422), resp.text


@pytest.mark.xfail(strict=False, reason="alerting_config PATCH persistence branch ships in Phase 40 Plan 04")
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


@pytest.mark.xfail(strict=False, reason="alerting.config_update audit action ships in Phase 40 Plan 04")
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
