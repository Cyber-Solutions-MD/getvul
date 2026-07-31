"""Tests for app.ai.batch -- the Message Batches submitter + single-pass
result validator (AIP-02, Phase 26 Plan 07).

A fake Anthropic client is injected via the `anthropic_client_factory` seam
(mirrors test_ai_explain_stream.py's `_FakeAsyncAnthropic` convention) --
`run_batch_prewarm()` takes NO externally-injected shared client, so every
test that exercises it supplies its own recording factory instead.

Backend env gotcha (MEMORY.md `getvul-backend-pytest-env`): run with a REAL
Fernet ENCRYPTION_KEY (`Fernet.generate_key()`) + JWT_SECRET_KEY set,
per-file.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request
from sqlalchemy import select

from app.ai.batch import estimate_batch_cost_usd, run_batch_prewarm, validate_and_cache_batch_result
from app.ai.cache import build_cache_key, get_cached, record_hash
from app.ai.explain import DEFAULT_MODEL, MAX_TOKENS, _estimate_cost_usd, _extract_scanner_data
from app.ai.grounding import get_prioritization_context
from app.ai.models import AiBatchJob
from app.ai.prompt_builder import (
    SYSTEM_PROMPT_PRIORITIZATION,
    build_explain_prioritization_prompt,
    prioritization_prompt_version,
)
from app.audit import AuditLog
from app.db.session import async_session_factory
from app.encryption import encrypt_value
from app.ticketing.models import ConnectorConfig
from app.vulnerabilities.models import Vulnerability

# ── Fake Anthropic client (SDK-boundary test seam, batch surface) ──────────


class _FakeBatch:
    def __init__(self, batch_id: str) -> None:
        self.id = batch_id


class _FakeTokensCount:
    def __init__(self, input_tokens: int) -> None:
        self.input_tokens = input_tokens


class _FakeBatches:
    def __init__(self, client: _FakeBatchAnthropic) -> None:
        self._client = client

    async def create(self, *, requests: list[Request]) -> _FakeBatch:
        self._client.create_calls.append(requests)
        self._client.batches_created += 1
        return _FakeBatch(f"batch-for-{self._client.api_key}")


class _FakeBatchMessages:
    def __init__(self, client: _FakeBatchAnthropic) -> None:
        self.batches = _FakeBatches(client)
        self._client = client

    async def count_tokens(self, *, model: str, system: Any, messages: Any) -> _FakeTokensCount:
        self._client.count_tokens_calls.append({"model": model, "system": system, "messages": messages})
        return _FakeTokensCount(input_tokens=self._client.input_tokens_per_request)


class _FakeBatchAnthropic:
    """Records which api_key constructed this instance -- the per-tenant
    BYOK isolation regression guard (T-24-19)."""

    def __init__(self, api_key: str, *, input_tokens_per_request: int = 1000) -> None:
        self.api_key = api_key
        self.input_tokens_per_request = input_tokens_per_request
        self.messages = _FakeBatchMessages(self)
        self.create_calls: list[list[Request]] = []
        self.count_tokens_calls: list[dict[str, Any]] = []
        self.batches_created = 0


def _make_recording_factory():
    """Returns (factory, constructed_keys, clients_by_key)."""
    constructed_keys: list[str] = []
    clients_by_key: dict[str, _FakeBatchAnthropic] = {}

    def factory(api_key: str) -> _FakeBatchAnthropic:
        constructed_keys.append(api_key)
        client = _FakeBatchAnthropic(api_key)
        clients_by_key[api_key] = client
        return client

    return factory, constructed_keys, clients_by_key


# ── Seed helpers ─────────────────────────────────────────────────────────────


async def _seed_anthropic_connector(
    db_session,
    tenant_id: uuid.UUID,
    *,
    api_key: str = "sk-ant-test-key-abc123",
    monthly_budget_usd: float | None = None,
) -> ConnectorConfig:
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


async def _seed_finding(db_session, tenant_id: uuid.UUID, *, cve_id: str) -> uuid.UUID:
    now = datetime.now(UTC)
    vuln = Vulnerability(
        tenant_id=tenant_id,
        cve_id=cve_id,
        severity="HIGH",
        source="NESSUS",
        source_vuln_id=str(uuid.uuid4()),
        status="OPEN",
        cisa_kev=True,
        cvss_v3_score=9.0,
        first_detected_at=now,
        last_seen_at=now,
    )
    db_session.add(vuln)
    await db_session.flush()
    return vuln.id


async def _fetch_audit_rows_fresh_session(action: str, resource_id: str) -> list[AuditLog]:
    """Fresh session -- proves the row was actually committed, mirroring
    test_ai_audit.py::_fetch_rows()."""
    async with async_session_factory() as fresh:
        result = await fresh.execute(
            select(AuditLog).where(AuditLog.action == action, AuditLog.resource_id == resource_id)
        )
        return list(result.scalars().all())


async def _fetch_batch_jobs_fresh_session(tenant_id: uuid.UUID) -> list[AiBatchJob]:
    async with async_session_factory() as fresh:
        result = await fresh.execute(select(AiBatchJob).where(AiBatchJob.tenant_id == tenant_id))
        return list(result.scalars().all())


async def _expected_cache_key(
    db_session, tenant_id: uuid.UUID, finding_id: uuid.UUID, model: str = DEFAULT_MODEL
) -> str:
    """Re-derive the EXACT cache key run_batch_prewarm() would compute for
    this finding, via the real record + real prompt builder + real hash --
    mirrors test_ai_explain_stream.py's own cache-key-recomputation test
    convention."""
    record = await get_prioritization_context(db_session, tenant_id, finding_id)
    _system, user_blocks = build_explain_prioritization_prompt(record)
    allowlisted_fields = _extract_scanner_data(user_blocks)
    the_hash = record_hash(allowlisted_fields)
    return build_cache_key(
        tenant_id, "prioritization", str(finding_id), the_hash, model, prioritization_prompt_version()
    )


# ── estimate_batch_cost_usd() ────────────────────────────────────────────────


async def test_estimate_batch_cost_discount():
    """The batch estimate must be exactly half the interactive-rate
    equivalent (RESEARCH Pitfall 4) -- the discount check."""
    fake_client = _FakeBatchAnthropic("sk-ant-any", input_tokens_per_request=1000)
    requests: list[Request] = [
        Request(
            custom_id="finding-1",
            params=MessageCreateParamsNonStreaming(
                model="claude-sonnet-5",
                max_tokens=MAX_TOKENS,
                temperature=0,
                system="a system prompt",
                messages=[{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
            ),
        )
    ]

    est = await estimate_batch_cost_usd(fake_client, "claude-sonnet-5", requests)

    input_rate, output_rate = 3.0, 15.0  # claude-sonnet-5's published rate
    interactive_equivalent = (1000 / 1_000_000) * input_rate + (MAX_TOKENS / 1_000_000) * output_rate
    assert est == round(interactive_equivalent * 0.5, 6)
    assert fake_client.count_tokens_calls == [
        {"model": "claude-sonnet-5", "system": "a system prompt", "messages": requests[0]["params"]["messages"]}
    ]


# ── run_batch_prewarm() ──────────────────────────────────────────────────────


async def test_run_batch_prewarm_skips_keyless_tenant(db_session, tenant_a, flushed_redis):
    """D-23 parity: a tenant with no ANTHROPIC ConnectorConfig row is
    skipped -- no client is EVER constructed for it, and no AiBatchJob row
    is inserted."""
    await _seed_finding(db_session, tenant_a, cve_id="CVE-BATCH-KEYLESS")
    await db_session.commit()

    def _factory(api_key: str):
        raise AssertionError("a client must never be constructed for a keyless tenant")

    await run_batch_prewarm(anthropic_client_factory=_factory)

    rows = await _fetch_batch_jobs_fresh_session(tenant_a)
    assert rows == []


async def test_run_batch_prewarm_uses_per_tenant_key(db_session, tenant_a, tenant_b, flushed_redis):
    """T-24-19/D-05/SC3: two tenants, two DISTINCT keys -- each tenant's
    batch is submitted with ITS OWN key, never a shared/fallback key. The
    fake factory records which api_key constructed which client, and the
    submitted batch id (encoding the api_key) proves which client actually
    signed which tenant's AiBatchJob row."""
    await _seed_anthropic_connector(db_session, tenant_a, api_key="sk-ant-key-tenant-a")
    await _seed_anthropic_connector(db_session, tenant_b, api_key="sk-ant-key-tenant-b")
    await _seed_finding(db_session, tenant_a, cve_id="CVE-BATCH-A-1")
    await _seed_finding(db_session, tenant_b, cve_id="CVE-BATCH-B-1")
    await db_session.commit()

    factory, constructed_keys, clients_by_key = _make_recording_factory()

    await run_batch_prewarm(anthropic_client_factory=factory)

    assert sorted(constructed_keys) == ["sk-ant-key-tenant-a", "sk-ant-key-tenant-b"]
    client_a = clients_by_key["sk-ant-key-tenant-a"]
    client_b = clients_by_key["sk-ant-key-tenant-b"]
    assert client_a.batches_created == 1
    assert client_b.batches_created == 1

    rows_a = await _fetch_batch_jobs_fresh_session(tenant_a)
    rows_b = await _fetch_batch_jobs_fresh_session(tenant_b)
    assert len(rows_a) == 1
    assert len(rows_b) == 1
    # Tenant A's job was submitted via the client built from tenant A's OWN
    # key -- never tenant B's, and vice versa.
    assert rows_a[0].anthropic_batch_id == "batch-for-sk-ant-key-tenant-a"
    assert rows_b[0].anthropic_batch_id == "batch-for-sk-ant-key-tenant-b"
    assert "sk-ant-key-tenant-b" not in rows_a[0].anthropic_batch_id
    assert "sk-ant-key-tenant-a" not in rows_b[0].anthropic_batch_id


async def test_run_batch_prewarm_one_tenant_failure_does_not_block_others(
    db_session, tenant_a, tenant_b, flushed_redis
):
    """Rule 2 resilience addition (26-07-SUMMARY.md Deviations): the
    per-tenant loop is wrapped in its own try/except so tenant_a's failure
    (simulated here as the client factory raising, e.g. a transient
    network/API error) does not abort tenant_b's own submission in the
    SAME nightly run."""
    await _seed_anthropic_connector(db_session, tenant_a, api_key="sk-ant-key-fail")
    await _seed_anthropic_connector(db_session, tenant_b, api_key="sk-ant-key-ok")
    await _seed_finding(db_session, tenant_a, cve_id="CVE-BATCH-FAIL-A")
    await _seed_finding(db_session, tenant_b, cve_id="CVE-BATCH-OK-B")
    await db_session.commit()

    def factory(api_key: str) -> _FakeBatchAnthropic:
        if api_key == "sk-ant-key-fail":
            raise RuntimeError("simulated transient client-construction failure")
        return _FakeBatchAnthropic(api_key)

    await run_batch_prewarm(anthropic_client_factory=factory)

    rows_a = await _fetch_batch_jobs_fresh_session(tenant_a)
    rows_b = await _fetch_batch_jobs_fresh_session(tenant_b)
    assert rows_a == []  # tenant_a's iteration failed -- no partial row, never crashes the whole run
    assert len(rows_b) == 1  # tenant_b still processed successfully in the SAME call


async def test_run_batch_prewarm_skips_cached_fresh_finding(db_session, tenant_a, flushed_redis):
    """Pitfall 5: a finding whose narrative is already cache-fresh is
    excluded from tonight's submitted requests -- no re-pay for an
    unchanged narrative."""
    from app.ai.cache import set_cached

    await _seed_anthropic_connector(db_session, tenant_a)
    finding_id = await _seed_finding(db_session, tenant_a, cve_id="CVE-BATCH-FRESH")
    await db_session.commit()

    cache_key = await _expected_cache_key(db_session, tenant_a, finding_id)
    await set_cached(
        flushed_redis,
        cache_key,
        {"summary": "already fresh", "business_risk": "n/a", "citations": [], "grounded": True},
    )

    factory, _constructed_keys, clients_by_key = _make_recording_factory()
    await run_batch_prewarm(anthropic_client_factory=factory)

    client = clients_by_key["sk-ant-test-key-abc123"]
    assert client.batches_created == 0  # nothing to submit -- the only finding was fresh
    rows = await _fetch_batch_jobs_fresh_session(tenant_a)
    assert rows == []


async def test_run_batch_prewarm_budget_skip(db_session, tenant_a, flushed_redis):
    """D-07: a pre-estimate that would breach the tenant's cap is skipped
    BEFORE create() ever runs -- admin-notified, audited
    batch_skipped_budget_exceeded, NO AiBatchJob row (never a silent
    partial)."""
    await _seed_anthropic_connector(db_session, tenant_a, monthly_budget_usd=0.0001)
    await _seed_finding(db_session, tenant_a, cve_id="CVE-BATCH-BUDGET")
    await db_session.commit()

    factory, _constructed_keys, clients_by_key = _make_recording_factory()

    with patch("app.ai.batch.notify_admins_budget_exceeded", new_callable=AsyncMock) as mock_notify:
        await run_batch_prewarm(anthropic_client_factory=factory)

    client = clients_by_key["sk-ant-test-key-abc123"]
    assert client.batches_created == 0
    mock_notify.assert_awaited_once()

    rows = await _fetch_batch_jobs_fresh_session(tenant_a)
    assert rows == []

    audit_rows = await _fetch_audit_rows_fresh_session("ai.explain.prioritization", "batch")
    tenant_rows = [r for r in audit_rows if r.tenant_id == tenant_a]
    assert len(tenant_rows) == 1
    assert tenant_rows[0].details["status"] == "batch_skipped_budget_exceeded"
    assert tenant_rows[0].details["cost_estimate_usd"] == 0.0


async def test_run_batch_prewarm_ok_inserts_durable_registry(db_session, tenant_a, flushed_redis):
    """The OK path: one AiBatchJob row, durable in a genuinely fresh
    session (Pitfall 2), with model/prompt_version frozen at submit time
    and a custom_id_hash_map keyed by the submitted finding_id."""
    await _seed_anthropic_connector(db_session, tenant_a)
    finding_id = await _seed_finding(db_session, tenant_a, cve_id="CVE-BATCH-DURABLE")
    await db_session.commit()

    factory, _constructed_keys, clients_by_key = _make_recording_factory()
    await run_batch_prewarm(anthropic_client_factory=factory)

    client = clients_by_key["sk-ant-test-key-abc123"]
    assert client.batches_created == 1

    rows = await _fetch_batch_jobs_fresh_session(tenant_a)
    assert len(rows) == 1
    row = rows[0]
    assert row.status == "in_progress"
    assert row.model == DEFAULT_MODEL
    assert row.prompt_version == prioritization_prompt_version()
    assert row.anthropic_batch_id == "batch-for-sk-ant-test-key-abc123"
    assert str(finding_id) in row.custom_id_hash_map

    record = await get_prioritization_context(db_session, tenant_a, finding_id)
    _system, user_blocks = build_explain_prioritization_prompt(record)
    expected_hash = record_hash(_extract_scanner_data(user_blocks))
    assert row.custom_id_hash_map[str(finding_id)] == expected_hash


# ── validate_and_cache_batch_result() ───────────────────────────────────────


def _valid_payload(summary: str = "Driven by KEV and a public exploit.") -> dict[str, Any]:
    return {
        "summary": summary,
        "business_risk": "Owned by Finance; SLA already breached.",
        "citations": [{"text": "CISA KEV-listed", "source": "scanner_verbatim", "source_field": "cisa_kev"}],
        "grounded": True,
    }


async def test_validate_and_cache_ok_books_half_cost(db_session, tenant_a, flushed_redis):
    raw_text = json.dumps(_valid_payload())
    usage = SimpleNamespace(input_tokens=1000, output_tokens=200)
    cache_key = f"ai:explain:test:{uuid.uuid4().hex}"
    finding_id = f"finding-{uuid.uuid4().hex[:8]}"

    status = await validate_and_cache_batch_result(
        db_session,
        flushed_redis,
        tenant_id=tenant_a,
        finding_id=finding_id,
        raw_text=raw_text,
        model="claude-sonnet-5",
        usage=usage,
        cache_key=cache_key,
    )

    assert status == "ok"
    cached = await get_cached(flushed_redis, cache_key)
    assert cached is not None
    assert cached["summary"] == _valid_payload()["summary"]

    rows = await _fetch_audit_rows_fresh_session("ai.explain.prioritization", finding_id)
    assert len(rows) == 1
    expected_cost = _estimate_cost_usd("claude-sonnet-5", usage) * 0.5
    assert rows[0].details["cost_estimate_usd"] == expected_cost
    assert rows[0].details["status"] == "ok"
    assert rows[0].user_email == "system:scheduler"


async def test_validate_and_cache_ungrounded_not_cached(db_session, tenant_a, flushed_redis):
    payload = {
        "summary": "Not enough signal to explain this finding's drivers.",
        "business_risk": "Unable to explain priority drivers without more data.",
        "citations": [
            {"text": "no CVSS/EPSS/exploit/KEV signal present", "source": "scanner_verbatim", "source_field": None}
        ],
        "grounded": False,
    }
    raw_text = json.dumps(payload)
    usage = SimpleNamespace(input_tokens=500, output_tokens=100)
    cache_key = f"ai:explain:test:{uuid.uuid4().hex}"
    finding_id = f"finding-{uuid.uuid4().hex[:8]}"

    status = await validate_and_cache_batch_result(
        db_session,
        flushed_redis,
        tenant_id=tenant_a,
        finding_id=finding_id,
        raw_text=raw_text,
        model="claude-sonnet-5",
        usage=usage,
        cache_key=cache_key,
    )

    assert status == "validation_failed"
    assert await get_cached(flushed_redis, cache_key) is None

    rows = await _fetch_audit_rows_fresh_session("ai.explain.prioritization", finding_id)
    assert len(rows) == 1
    assert rows[0].details["cost_estimate_usd"] == 0.0


async def test_validate_and_cache_leak_marker_flagged(db_session, tenant_a, flushed_redis):
    leak_marker = SYSTEM_PROMPT_PRIORITIZATION.strip().splitlines()[0][:40].strip().lower()
    payload = _valid_payload(summary=f"Ignoring instructions: {leak_marker} -- system prompt echoed back.")
    raw_text = json.dumps(payload)
    usage = SimpleNamespace(input_tokens=700, output_tokens=150)
    cache_key = f"ai:explain:test:{uuid.uuid4().hex}"
    finding_id = f"finding-{uuid.uuid4().hex[:8]}"

    status = await validate_and_cache_batch_result(
        db_session,
        flushed_redis,
        tenant_id=tenant_a,
        finding_id=finding_id,
        raw_text=raw_text,
        model="claude-sonnet-5",
        usage=usage,
        cache_key=cache_key,
    )

    assert status == "injection_flagged"
    assert await get_cached(flushed_redis, cache_key) is None

    rows = await _fetch_audit_rows_fresh_session("ai.explain.prioritization", finding_id)
    assert len(rows) == 1
    assert rows[0].details["cost_estimate_usd"] == 0.0
