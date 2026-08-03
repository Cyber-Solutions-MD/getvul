"""D-04 "no AI call path bypasses the guard" -- the AIE-03 no-bypass budget
coverage gate.

Test A patches the module-local bound name `app.ai.explain.AsyncAnthropic`
(the name `_default_client_factory` (explain.py:121) constructs, matching 6
existing repo precedents, e.g. `test_ai_explain_prioritization.py:146`)
across all 5 explain routes, proving `check_tenant_budget()`'s fail-closed
short-circuit (explain.py:308) runs BEFORE any client construction
(explain.py:339) when the tenant is over its monthly cap. An UNDER-budget
control proves the SAME patched name IS constructed when the guard passes --
without this control, an over-budget `call_count == 0` assertion could be
tautologically true even with the guard deleted, IF the wrong target were
patched: a top-level, SDK-package-level patch would bind nothing at call
time, since both app.ai.explain and app.ai.batch do `from anthropic import
AsyncAnthropic`, binding the name into their OWN module namespace at import
time.

Test B proves the batch path's construct-then-count-then-gate asymmetry
(batch.py:200-278): the client IS legitimately constructed and a free
`count_tokens()` pre-estimate call IS legitimately made regardless of budget
status (both are needed to COMPUTE the estimate the gate decides on) -- but
the BILLED `client.messages.batches.create()` dispatch is NEVER reached over
budget. A fake client is injected via the documented `anthropic_client_
factory=` DI seam on `run_batch_prewarm()` (mirrors test_ai_batch.py's
`_FakeBatchAnthropic` convention) -- a recording factory, never a global
monkeypatch, so no real Anthropic network call is ever possible (KEYLESS).

Backend env gotcha (MEMORY.md `getvul-backend-pytest-env`): run with a REAL
Fernet ENCRYPTION_KEY (`Fernet.generate_key()`, NOT a placeholder string) +
JWT_SECRET_KEY set, per-file (not the whole tests/ dir).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.ai.batch import run_batch_prewarm
from app.assets.models import Asset
from app.encryption import encrypt_value
from app.ticketing.models import ConnectorConfig
from app.vulnerabilities.models import Vulnerability
from tests.test_ai_budget import _seed_ai_spend  # reuse, don't re-derive (PATTERNS AIE-03 analog)

# ── Seed helpers ─────────────────────────────────────────────────────────


async def _seed_anthropic_connector(
    db_session: Any,
    tenant_id: uuid.UUID,
    *,
    api_key: str = "sk-ant-coverage-test-key",
    monthly_budget_usd: float | None = None,
) -> ConnectorConfig:
    """Mirrors test_ai_batch.py::_seed_anthropic_connector's exact shape."""
    config: dict[str, Any] = {}
    if monthly_budget_usd is not None:
        config["monthly_budget_usd"] = monthly_budget_usd
    connector = ConnectorConfig(
        tenant_id=tenant_id,
        connector_type="ANTHROPIC",
        credentials_secret_arn=json.dumps({"api_key": encrypt_value(api_key)}),
        config=config,
    )
    db_session.add(connector)
    await db_session.flush()
    return connector


async def _seed_vulnerability(db_session: Any, tenant_id: uuid.UUID, **overrides: Any) -> uuid.UUID:
    now = datetime.now(UTC)
    defaults: dict[str, Any] = {
        "tenant_id": tenant_id,
        "cve_id": f"CVE-2024-{uuid.uuid4().hex[:4]}",
        "severity": "HIGH",
        "source": "NESSUS",
        "source_vuln_id": str(uuid.uuid4()),
        "status": "OPEN",
        "cisa_kev": True,
        "cvss_v3_score": 9.0,
        "first_detected_at": now,
        "last_seen_at": now,
    }
    defaults.update(overrides)
    vuln = Vulnerability(**defaults)
    db_session.add(vuln)
    await db_session.flush()
    return vuln.id


async def _seed_asset(db_session: Any, tenant_id: uuid.UUID, **overrides: Any) -> uuid.UUID:
    defaults: dict[str, Any] = {
        "tenant_id": tenant_id,
        "hostname": f"host-{uuid.uuid4().hex[:8]}",
    }
    defaults.update(overrides)
    asset = Asset(**defaults)
    db_session.add(asset)
    await db_session.flush()
    return asset.id


async def _seed_route_resource(db_session: Any, tenant_id: uuid.UUID, resource_type: str) -> str:
    """Seed whatever grounding record each route's own resolver needs so the
    request reaches _run_explain_stream()'s budget check (explain.py:308) --
    returns the path-parameter value to substitute into the route template
    (a UUID string, or a literal CVE-ID string for the remediation route)."""
    if resource_type == "vuln":
        return str(await _seed_vulnerability(db_session, tenant_id))
    if resource_type == "host":
        return str(await _seed_asset(db_session, tenant_id))
    if resource_type == "remediation":
        cve_id = f"CVE-2024-{uuid.uuid4().hex[:4]}"
        asset_id = await _seed_asset(db_session, tenant_id)
        await _seed_vulnerability(
            db_session,
            tenant_id,
            cve_id=cve_id,
            asset_id=asset_id,
            remediation_info="Upgrade to the fixed version.",
        )
        return cve_id
    if resource_type == "remediation-guidance":
        # D-01's has_actionable_remediation_text() pre-gate must pass
        # (>=15 chars, not a generic placeholder) so the request reaches
        # _run_explain_stream() rather than the zero-dispatch refuse path.
        return str(
            await _seed_vulnerability(
                db_session,
                tenant_id,
                remediation_action="Upgrade the affected package to the patched release.",
            )
        )
    if resource_type == "prioritization":
        return str(await _seed_vulnerability(db_session, tenant_id))
    raise AssertionError(f"unknown resource_type {resource_type!r}")


# ── Test A: the 5 explain routes -- module-local app.ai.explain.AsyncAnthropic ──

ALL_EXPLAIN_ROUTES: list[tuple[str, str]] = [
    ("vuln", "/api/v1/ai/explain-vuln/{id}"),
    ("host", "/api/v1/ai/explain-host/{id}"),
    ("remediation", "/api/v1/ai/explain-remediation/{id}"),
    ("remediation-guidance", "/api/v1/ai/explain-remediation-guidance/{id}"),
    ("prioritization", "/api/v1/ai/explain-prioritization/{id}"),
]


@pytest.mark.parametrize("resource_type,route_template", ALL_EXPLAIN_ROUTES)
async def test_over_budget_never_constructs_anthropic_client(
    resource_type: str,
    route_template: str,
    client: Any,
    db_session: Any,
    tenant_a: uuid.UUID,
) -> None:
    """D-04/AIE-03: patches the module-local bound name
    `app.ai.explain.AsyncAnthropic`. A top-level, SDK-package-level patch
    would bind nothing at call time (both app.ai.explain and app.ai.batch do
    `from anthropic import AsyncAnthropic`, binding the name in their OWN
    module namespace at import time), making a call_count == 0 assertion
    tautologically true even with the budget guard deleted.

    Deviation (Rule 1/3 -- test-reliability bug found and fixed while
    verifying this task): the REAL `create_app()` behind the `client`
    fixture starts `app.connectors.scheduler`'s background loop, whose
    `_dispatch_ai_batch_prewarm()` fires unconditionally on its very FIRST
    tick per process (a module-level `_last_ai_batch_prewarm is None`
    24h-gate). If that tick lands after this test's own ANTHROPIC connector
    is committed and while `app.ai.explain.AsyncAnthropic` is patched, the
    scheduler's OWN real `run_batch_prewarm()` independently constructs a
    client through the SAME patched name, spuriously incrementing
    `mock_cls.call_count` and flaking this exact `== 0` assertion (observed
    empirically: 1/10 parametrized cases failed non-deterministically on
    first run, always via a stray `ai_batch_prewarm_tenant_error` log line
    from a background task, never from the route under test). Test B (no
    `client`/app instance) and the under-budget control (an extra
    construction only strengthens `>= 1`) are structurally immune, so the
    no-op patch below is scoped to only this test."""
    with patch("app.connectors.scheduler._dispatch_ai_batch_prewarm", new_callable=AsyncMock):
        resource_id = await _seed_route_resource(db_session, tenant_a, resource_type)
        await _seed_anthropic_connector(db_session, tenant_a, monthly_budget_usd=1.0)
        await _seed_ai_spend(db_session, tenant_a, 999.0)  # month-to-date spend >> the $1 cap
        await db_session.commit()

        with patch("app.ai.explain.AsyncAnthropic") as mock_cls:
            resp = await client.post(route_template.format(id=resource_id))

    assert resp.status_code == 200, resp.text
    assert '"kind": "budget_exceeded"' in resp.text
    assert mock_cls.call_count == 0


@pytest.mark.parametrize("resource_type,route_template", ALL_EXPLAIN_ROUTES)
async def test_under_budget_control_constructs_anthropic_client(
    resource_type: str,
    route_template: str,
    client: Any,
    db_session: Any,
    tenant_a: uuid.UUID,
) -> None:
    """REGRESSION GATE: proves the over-budget assertion above is NOT
    tautological. With the SAME tenant genuinely UNDER budget, the SAME
    patched module-local name IS constructed at explain.py:339 -- so if a
    future change accidentally removed the budget-guard call from
    _run_explain_stream entirely, the over-budget test's
    `mock_cls.call_count == 0` assertion would flip to >= 1 and FAIL,
    proving this suite can genuinely catch that regression. Also wrapped in
    the same scheduler-dispatch no-op as the over-budget test above (a
    stray background construction here would only strengthen `>= 1`, but
    the wrap keeps both tests' background-noise behavior identical and
    avoids unrelated log noise)."""
    with patch("app.connectors.scheduler._dispatch_ai_batch_prewarm", new_callable=AsyncMock):
        resource_id = await _seed_route_resource(db_session, tenant_a, resource_type)
        await _seed_anthropic_connector(db_session, tenant_a, monthly_budget_usd=1_000_000.0)
        await db_session.commit()

        with patch("app.ai.explain.AsyncAnthropic") as mock_cls:
            resp = await client.post(route_template.format(id=resource_id))

    assert resp.status_code == 200, resp.text
    assert mock_cls.call_count >= 1


# ── Test B: the batch path -- anthropic_client_factory= DI seam, KEYLESS ──


class _RecordingBatchAnthropic:
    """A minimal recording fake -- mirrors test_ai_batch.py's
    `_FakeBatchAnthropic`/`_FakeBatches`/`_FakeTokensCount` DI-seam
    convention, injected via `run_batch_prewarm(anthropic_client_factory=)`
    so NO real Anthropic client is ever constructed and NO real network call
    is ever possible (keyless). Only implements the two methods
    `estimate_batch_cost_usd()`/`run_batch_prewarm()` actually call on the
    injected client: the free `count_tokens()` pre-estimate and the BILLED
    `batches.create()` dispatch."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.count_tokens_calls = 0
        self.batches_created = 0
        self.messages = _RecordingBatchMessages(self)


class _RecordingBatchMessages:
    def __init__(self, client: _RecordingBatchAnthropic) -> None:
        self._client = client
        self.batches = _RecordingBatches(client)

    async def count_tokens(self, *, model: str, system: Any, messages: Any) -> Any:
        self._client.count_tokens_calls += 1
        return SimpleNamespace(input_tokens=1000)


class _RecordingBatches:
    def __init__(self, client: _RecordingBatchAnthropic) -> None:
        self._client = client

    async def create(self, *, requests: Any) -> Any:
        self._client.batches_created += 1
        return SimpleNamespace(id=f"batch-for-{self._client.api_key}")


async def test_batch_over_budget_never_reaches_billed_dispatch(
    db_session: Any,
    tenant_a: uuid.UUID,
    flushed_redis: Any,
) -> None:
    """D-04/AIE-03 batch-path invariant (26-PATTERNS.md CRITICAL CORRECTION):
    unlike the 5 explain routes, the batch client IS legitimately
    constructed and the free count_tokens() pre-estimate IS legitimately
    called BEFORE the budget gate (batch.py:210/:259) -- both are needed to
    COMPUTE the estimate the gate decides on. The invariant this test
    proves is narrower and more precise: the BILLED
    client.messages.batches.create() dispatch (batch.py:278) is NEVER
    reached when the estimated spend would breach the tenant's cap."""
    await _seed_anthropic_connector(db_session, tenant_a, monthly_budget_usd=0.0001)
    await _seed_vulnerability(db_session, tenant_a)
    await db_session.commit()

    constructed: list[_RecordingBatchAnthropic] = []

    def factory(api_key: str) -> _RecordingBatchAnthropic:
        fake = _RecordingBatchAnthropic(api_key)
        constructed.append(fake)
        return fake

    await run_batch_prewarm(anthropic_client_factory=factory)

    assert len(constructed) == 1  # legitimately constructed -- needed to compute the estimate
    fake = constructed[0]
    assert fake.count_tokens_calls >= 1  # the free pre-estimate legitimately runs pre-gate
    assert fake.batches_created == 0  # ...but the BILLED dispatch is NEVER reached over budget
