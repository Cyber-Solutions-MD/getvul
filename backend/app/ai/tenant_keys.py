"""BYOK Anthropic key resolution (AI-01) — the tenant-scoped, no-fallback boundary.

Mirrors `connectors/service.py::get_decrypted_credentials` (lines 152-160):
the same `json.loads(credentials_secret_arn)` then `decrypt_value(v)` per
field, scoped by `tenant_id` + `connector_type == "ANTHROPIC"`. There is no
shared/fallback Anthropic key anywhere in this codebase (the BYOK
constraint) — a tenant with no ANTHROPIC `ConnectorConfig` row gets `None`
back (the inert "configure AI" precondition), never an exception and never
another tenant's key or an env-var fallback.

The decrypted key is NEVER cached in a module-level variable — every call
re-selects the row and re-decrypts fresh, so a key rotation, connector
delete, or `encryption.py::rotate_credentials()` re-encryption takes effect
on the very next call with zero extra invalidation logic.
"""

from __future__ import annotations

import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.encryption import decrypt_value
from app.ticketing.models import ConnectorConfig

ANTHROPIC_CONNECTOR_TYPE = "ANTHROPIC"


async def get_tenant_anthropic_key(db: AsyncSession, tenant_id: uuid.UUID) -> str | None:
    """Return the tenant's decrypted Anthropic API key, or None if unconfigured.

    Selects the tenant's ANTHROPIC `ConnectorConfig` row (at most one per
    tenant — `uq_connector_tenant_type` on (tenant_id, connector_type)),
    decrypts the `api_key` field fresh from `credentials_secret_arn`, and
    returns the plaintext. Returns None — never raises, never falls back to
    any shared/env key, never leaks another tenant's key — when the tenant
    has no row, the row has no stored credentials, the credentials blob
    fails to parse, or the `api_key` field is absent (AI-01's inert
    "configure AI" precondition).
    """
    result = await db.execute(
        select(ConnectorConfig).where(
            ConnectorConfig.tenant_id == tenant_id,
            ConnectorConfig.connector_type == ANTHROPIC_CONNECTOR_TYPE,
        )
    )
    connector = result.scalar_one_or_none()
    if connector is None or not connector.credentials_secret_arn:
        return None
    try:
        encrypted_map = json.loads(connector.credentials_secret_arn)
        ciphertext = encrypted_map.get("api_key") if isinstance(encrypted_map, dict) else None
        if not ciphertext:
            return None
        return decrypt_value(ciphertext)
    except Exception:
        # Mirrors get_decrypted_credentials' defensive shape: any parse/
        # decrypt failure is treated as "no usable key" (inert), never a
        # 500 that would surface mid-triage — never re-raised or logged
        # with key material.
        return None
