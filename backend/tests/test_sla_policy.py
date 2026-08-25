"""Phase 36 Plan 05 — /api/v1/tenant/settings sla_config: RBAC, mask-on-read,
Fernet-at-rest encryption, keep-on-masked-write, and Pydantic validation
(SLA-01/SLA-03, D-14).

Drives the real HTTP client (client_factory) against the extended GET/PATCH
`/api/v1/tenant/settings` handlers — not sla_tier_service.py directly (that
module's own coverage lives in test_sla_tier_service.py from Plan 01). Reads
`tenant.sla_config` straight from the DB to assert the at-rest encryption
contract: the stored channel secret is neither the plaintext submitted nor
the mask placeholder, and app.encryption.decrypt_value recovers the original.

Session-visibility gotcha (mirrors test_risk_cutover_ack.py): `tenant_a`/
`owner_user`/`admin_user` fixtures only `flush()`, not `commit()`. The app's
own request-scoped DB session (a different session/transaction than this
file's `db_session` fixture) will not see an uncommitted row, so every test
that lets a request reach the route body (i.e. passes RBAC) commits first.
Pure-RBAC-403 tests skip this — the 403 fires in the dependency, before the
route body's Tenant SELECT ever runs.

Backend env gotcha (MEMORY.md `getvul-backend-pytest-env`): run with a REAL
Fernet ENCRYPTION_KEY (`Fernet.generate_key()`, NOT a placeholder string) +
JWT_SECRET_KEY set, per-file (not the whole tests/ dir).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from app.audit import AuditLog
from app.encryption import decrypt_value
from app.tenants.models import Tenant

SETTINGS_URL = "/api/v1/tenant/settings"
SLA_MASK = "••••••••"


def _full_sla_config(**overrides: Any) -> dict[str, Any]:
    """A complete sla_config PATCH body — mirrors the admin-pane full-replace
    contract established by the existing smtp_config precedent (router.py)."""
    body: dict[str, Any] = {
        "tier_policy": {"critical": 7, "high": 30, "moderate": 90},
        "approaching_pct": 0.8,
        "tier_floor": "high",
        "channels": {
            "slack": {"url": "https://hooks.slack.com/services/T00/B00/XXX", "enabled": True},
            "teams": {"url": "https://example.webhook.office.com/webhookb2/abc", "enabled": False},
            "pagerduty": {"routing_key": "R0ROUTINGKEY123", "enabled": False},
            "email": {"to": ["oncall@tenant-a.test"], "enabled": True},
        },
        "routing": {"approaching": ["slack"], "breached": ["slack", "pagerduty"]},
    }
    body.update(overrides)
    return body


async def _get_tenant(db_session: Any, tenant_id: uuid.UUID) -> Tenant:
    """Fetch + force-refresh the Tenant row (identity-map staleness guard —
    the app's PATCH commits in a *different* session; this session's cached
    copy, if any, won't auto-pick-up the new attribute values otherwise)."""
    tenant = (await db_session.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one()
    await db_session.refresh(tenant)
    return tenant


# ── PATCH persists the full policy (owner) ──────────────────────────────────


async def test_patch_as_owner_persists_full_policy(
    client_factory: Any, owner_user: Any, db_session: Any, tenant_a: uuid.UUID
) -> None:
    await db_session.commit()
    client = client_factory(owner_user)
    resp = await client.patch(SETTINGS_URL, json={"sla_config": _full_sla_config()})
    assert resp.status_code == 200, resp.text

    tenant = await _get_tenant(db_session, tenant_a)
    assert tenant.sla_config["tier_policy"] == {"critical": 7, "high": 30, "moderate": 90}
    assert tenant.sla_config["approaching_pct"] == 0.8
    assert tenant.sla_config["tier_floor"] == "high"
    assert tenant.sla_config["routing"] == {"approaching": ["slack"], "breached": ["slack", "pagerduty"]}
    assert tenant.sla_config["channels"]["email"]["to"] == ["oncall@tenant-a.test"]
    assert tenant.sla_config["channels"]["email"]["enabled"] is True


# ── GET masks channel secrets, never plaintext ──────────────────────────────


async def test_get_as_admin_masks_channel_secrets(
    client_factory: Any, owner_user: Any, admin_user: Any, db_session: Any, tenant_a: uuid.UUID
) -> None:
    await db_session.commit()
    owner_client = client_factory(owner_user)
    patch_resp = await owner_client.patch(SETTINGS_URL, json={"sla_config": _full_sla_config()})
    assert patch_resp.status_code == 200, patch_resp.text

    admin_client = client_factory(admin_user)
    resp = await admin_client.get(SETTINGS_URL)
    assert resp.status_code == 200, resp.text

    sla = resp.json()["sla_config"]
    assert sla["channels"]["slack"]["url"] == SLA_MASK
    assert sla["channels"]["teams"]["url"] == SLA_MASK
    assert sla["channels"]["pagerduty"]["routing_key"] == SLA_MASK
    # Not a secret — passes through unmasked.
    assert sla["channels"]["email"]["to"] == ["oncall@tenant-a.test"]
    assert sla["tier_policy"] == {"critical": 7, "high": 30, "moderate": 90}


# ── Round-trip: at-rest ciphertext, neither plaintext nor the mask ─────────


async def test_channel_secret_encrypted_at_rest(
    client_factory: Any, owner_user: Any, db_session: Any, tenant_a: uuid.UUID
) -> None:
    await db_session.commit()
    plaintext_url = "https://hooks.slack.com/services/T00/B00/SECRETVALUE"
    client = client_factory(owner_user)
    resp = await client.patch(
        SETTINGS_URL,
        json={"sla_config": _full_sla_config(channels={"slack": {"url": plaintext_url, "enabled": True}})},
    )
    assert resp.status_code == 200, resp.text

    tenant = await _get_tenant(db_session, tenant_a)
    stored = tenant.sla_config["channels"]["slack"]["url"]
    assert stored != plaintext_url
    assert stored != SLA_MASK
    assert decrypt_value(stored) == plaintext_url


# ── Masked-write keeps the existing stored ciphertext ───────────────────────


async def test_masked_write_keeps_existing_secret(
    client_factory: Any, owner_user: Any, db_session: Any, tenant_a: uuid.UUID
) -> None:
    await db_session.commit()
    plaintext_url = "https://hooks.slack.com/services/T00/B00/ORIGINAL"
    client = client_factory(owner_user)
    first = await client.patch(
        SETTINGS_URL,
        json={"sla_config": _full_sla_config(channels={"slack": {"url": plaintext_url, "enabled": True}})},
    )
    assert first.status_code == 200, first.text

    tenant = await _get_tenant(db_session, tenant_a)
    original_ciphertext = tenant.sla_config["channels"]["slack"]["url"]
    assert original_ciphertext != plaintext_url

    # Re-submit with the mask placeholder (simulates the admin pane leaving an
    # untouched secret field alone) while changing an unrelated field, to
    # prove a real PATCH ran rather than a silent no-op.
    second = await client.patch(
        SETTINGS_URL,
        json={
            "sla_config": _full_sla_config(
                tier_floor="critical",
                channels={"slack": {"url": SLA_MASK, "enabled": True}},
            )
        },
    )
    assert second.status_code == 200, second.text

    tenant2 = await _get_tenant(db_session, tenant_a)
    assert tenant2.sla_config["channels"]["slack"]["url"] == original_ciphertext
    assert decrypt_value(tenant2.sla_config["channels"]["slack"]["url"]) == plaintext_url
    assert tenant2.sla_config["tier_floor"] == "critical"


# ── RBAC: GET=admin, PATCH=owner (existing asymmetry preserved) ────────────


async def test_get_settings_analyst_forbidden(client_factory: Any, analyst_user: Any) -> None:
    client = client_factory(analyst_user)
    resp = await client.get(SETTINGS_URL)
    assert resp.status_code == 403


async def test_get_settings_viewer_forbidden(client_factory: Any, viewer_user: Any) -> None:
    client = client_factory(viewer_user)
    resp = await client.get(SETTINGS_URL)
    assert resp.status_code == 403


async def test_get_settings_admin_allowed(client_factory: Any, admin_user: Any, db_session: Any) -> None:
    await db_session.commit()
    client = client_factory(admin_user)
    resp = await client.get(SETTINGS_URL)
    assert resp.status_code == 200, resp.text


async def test_patch_settings_admin_forbidden(client_factory: Any, admin_user: Any) -> None:
    """ADMIN passes require_admin (GET) but NOT require_owner (PATCH) — the
    existing RBAC asymmetry (D-10) must be preserved even for the new
    sla_config fields."""
    client = client_factory(admin_user)
    resp = await client.patch(SETTINGS_URL, json={"sla_config": _full_sla_config()})
    assert resp.status_code == 403


async def test_patch_settings_analyst_forbidden(client_factory: Any, analyst_user: Any) -> None:
    client = client_factory(analyst_user)
    resp = await client.patch(SETTINGS_URL, json={"sla_config": _full_sla_config()})
    assert resp.status_code == 403


# ── Validation ───────────────────────────────────────────────────────────────


async def test_patch_rejects_non_positive_tier_day(client_factory: Any, owner_user: Any, db_session: Any) -> None:
    await db_session.commit()
    client = client_factory(owner_user)
    resp = await client.patch(
        SETTINGS_URL,
        json={"sla_config": _full_sla_config(tier_policy={"critical": 0, "high": 30, "moderate": 90})},
    )
    assert resp.status_code in (400, 422), resp.text


async def test_patch_rejects_approaching_pct_out_of_range(
    client_factory: Any, owner_user: Any, db_session: Any
) -> None:
    await db_session.commit()
    client = client_factory(owner_user)
    resp = await client.patch(
        SETTINGS_URL,
        json={"sla_config": _full_sla_config(approaching_pct=1.5)},
    )
    assert resp.status_code in (400, 422), resp.text


async def test_patch_rejects_unknown_tier_floor(client_factory: Any, owner_user: Any, db_session: Any) -> None:
    await db_session.commit()
    client = client_factory(owner_user)
    resp = await client.patch(
        SETTINGS_URL,
        json={"sla_config": _full_sla_config(tier_floor="apocalyptic")},
    )
    assert resp.status_code in (400, 422), resp.text


async def test_patch_rejects_non_https_webhook(client_factory: Any, owner_user: Any, db_session: Any) -> None:
    await db_session.commit()
    client = client_factory(owner_user)
    resp = await client.patch(
        SETTINGS_URL,
        json={"sla_config": _full_sla_config(channels={"slack": {"url": "http://hooks.slack.com/x", "enabled": True}})},
    )
    assert resp.status_code in (400, 422), resp.text


async def test_patch_accepts_masked_placeholder_despite_https_check(
    client_factory: Any, owner_user: Any, db_session: Any
) -> None:
    """The mask placeholder is not itself an https:// URL — the validator
    must special-case it so a legitimate masked-write PATCH doesn't 400."""
    await db_session.commit()
    client = client_factory(owner_user)
    # Seed a real secret first so the mask on the second call is meaningful.
    seed = await client.patch(
        SETTINGS_URL,
        json={
            "sla_config": _full_sla_config(channels={"slack": {"url": "https://hooks.slack.com/a", "enabled": True}})
        },
    )
    assert seed.status_code == 200, seed.text

    resp = await client.patch(
        SETTINGS_URL,
        json={"sla_config": _full_sla_config(channels={"slack": {"url": SLA_MASK, "enabled": True}})},
    )
    assert resp.status_code == 200, resp.text


# ── Audit (D-07 fail-closed convention) ─────────────────────────────────────


async def test_patch_writes_sla_policy_update_audit(
    client_factory: Any, owner_user: Any, db_session: Any, tenant_a: uuid.UUID
) -> None:
    await db_session.commit()
    client = client_factory(owner_user)
    resp = await client.patch(SETTINGS_URL, json={"sla_config": _full_sla_config()})
    assert resp.status_code == 200, resp.text

    rows = (
        (
            await db_session.execute(
                select(AuditLog).where(AuditLog.tenant_id == tenant_a, AuditLog.action == "sla.policy_update")
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1, f"expected exactly one sla.policy_update audit row, got {len(rows)}"
    assert rows[0].resource_type == "tenant"
    assert rows[0].details["tier_floor"] == "high"
    # The audit row must never carry a channel secret, encrypted or not.
    assert "channels" not in rows[0].details or rows[0].details.get("channels") is None


async def test_rejected_patch_writes_no_audit_row(
    client_factory: Any, owner_user: Any, db_session: Any, tenant_a: uuid.UUID
) -> None:
    """A validation failure must not leave a partial/rolled-back audit row
    (fail-closed means the mutation + its audit succeed together or not at
    all — a rejected PATCH persists nothing, audit included)."""
    await db_session.commit()
    client = client_factory(owner_user)
    resp = await client.patch(
        SETTINGS_URL,
        json={"sla_config": _full_sla_config(tier_floor="not-a-real-tier")},
    )
    assert resp.status_code in (400, 422), resp.text

    rows = (
        (
            await db_session.execute(
                select(AuditLog).where(AuditLog.tenant_id == tenant_a, AuditLog.action == "sla.policy_update")
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 0
