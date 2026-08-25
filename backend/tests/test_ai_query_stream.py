"""Tests for app.ai.query_assistant._run_query_stream -- the NLQ two-call
orchestrator (NLQ-01/NLQ-02/NLQ-03, Phase 44 Plan 01) -- and (Task 3) the
POST /api/v1/ai/query SSE endpoint + RBAC/tenant-scoping
(app.api.v1.ai.query).

Mirrors test_ai_explain_stream.py's testing strategy: control-flow tests
mock at the SDK boundary via `anthropic_client_factory` (fast, precise
control over get_final_message()/exceptions, no real wire format needed).

Backend env gotcha (MEMORY.md `getvul-backend-pytest-env`): run with a REAL
Fernet ENCRYPTION_KEY + JWT_SECRET_KEY set, per-file (not the whole tests/
dir).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

from app.ai.cache import acquire_inflight
from app.ai.query_assistant import _resolve_hostname, _run_query_stream
from app.audit import AuditLog
from app.encryption import encrypt_value
from app.pagination import PaginatedResponse, PaginationParams
from app.ticketing.models import ConnectorConfig

# ── Fake Anthropic client (SDK-boundary test seam, mirrors
# test_ai_explain_stream.py's own local test doubles) ──────────────────────


class _FakeStreamCM:
    def __init__(self, message: Any = None, error: BaseException | None = None) -> None:
        self._message = message
        self._error = error

    async def __aenter__(self) -> _FakeStreamCM:
        if self._error is not None:
            raise self._error
        return self

    async def __aexit__(self, *exc_info: object) -> bool:
        return False

    async def get_final_message(self) -> Any:
        return self._message


class _FakeMessages:
    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.call_count = 0

    def stream(self, **kwargs: Any) -> _FakeStreamCM:
        self.call_count += 1
        item = self._responses.pop(0)
        if isinstance(item, BaseException):
            return _FakeStreamCM(error=item)
        return _FakeStreamCM(message=item)


class _FakeAsyncAnthropic:
    def __init__(self, responses: list[Any]) -> None:
        self.messages = _FakeMessages(responses)


def _make_message(payload: dict[str, Any], input_tokens: int = 50, output_tokens: int = 40) -> Any:
    return _make_message_from_text(json.dumps(payload), input_tokens=input_tokens, output_tokens=output_tokens)


def _make_message_from_text(text: str, input_tokens: int = 50, output_tokens: int = 40) -> Any:
    block = SimpleNamespace(type="text", text=text)
    usage = SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens)
    return SimpleNamespace(content=[block], usage=usage)


def _translate_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "entity": "vulnerabilities",
        "vulnerability_filter": {
            "severity": ["CRITICAL"],
            "cisa_kev": True,
            "exploit_available": None,
            "age_days_min": 30,
            "status": None,
        },
        "asset_filter": None,
        "ticket_filter": None,
        "groundable": True,
    }
    payload.update(overrides)
    return payload


def _narrate_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "summary": "2 critical, CISA KEV-listed vulnerabilities older than 30 days are still open.",
        "business_risk": "Treat as urgent -- both are already past the 30-day mark.",
        "citations": [{"text": "2 critical KEV vulns", "source": "ai_interpreted", "source_field": None}],
        "grounded": True,
    }
    payload.update(overrides)
    return payload


def _decode_frame(frame: bytes) -> dict[str, Any]:
    text = frame.decode()
    assert text.startswith("data: ")
    assert text.endswith("\n\n")
    return json.loads(text[len("data: ") : -2])


# ── Seed helpers ────────────────────────────────────────────────────────────


async def _seed_anthropic_connector(
    db_session: Any,
    tenant_id: uuid.UUID,
    *,
    api_key: str = "sk-ant-test-key-abc123",
    model: str | None = None,
    monthly_budget_usd: float | None = None,
) -> ConnectorConfig:
    config: dict[str, Any] = {}
    if model is not None:
        config["model"] = model
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


async def _seed_ai_spend(db_session: Any, tenant_id: uuid.UUID, cost_estimate_usd: float) -> None:
    log = AuditLog(
        tenant_id=tenant_id,
        user_id=None,
        user_email="analyst@tenant-a.test",
        action="ai.query.translate",
        resource_type="translate",
        resource_id="vulnerabilities",
        details={"cost_estimate_usd": cost_estimate_usd, "status": "ok"},
        ip_address=None,
        created_at=datetime.now(UTC),
    )
    db_session.add(log)
    await db_session.flush()


async def _query_audit_rows(db_session: Any, tenant_id: uuid.UUID) -> list[AuditLog]:
    from sqlalchemy import select

    result = await db_session.execute(
        select(AuditLog)
        .where(AuditLog.action.like("ai.query.%"), AuditLog.tenant_id == tenant_id)
        .order_by(AuditLog.created_at)
    )
    return list(result.scalars().all())


async def _seed_vulnerability(db_session: Any, tenant_id: uuid.UUID, **overrides: Any) -> uuid.UUID:
    from app.vulnerabilities.models import Vulnerability

    defaults: dict[str, Any] = {
        "tenant_id": tenant_id,
        "cve_id": f"CVE-2024-{uuid.uuid4().hex[:6]}",
        "vulnerability_name": "Sample Vuln",
        "severity": "CRITICAL",
        "exploit_available": False,
        "cisa_kev": True,
        "source": "NESSUS",
        "source_vuln_id": str(uuid.uuid4()),
        "status": "OPEN",
        "first_detected_at": datetime.now(UTC) - timedelta(days=45),
        "last_seen_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    vuln = Vulnerability(**defaults)
    db_session.add(vuln)
    await db_session.commit()
    return vuln.id


def _run_stream(
    db_session: Any,
    tenant_id: uuid.UUID,
    redis_client: Any,
    *,
    question: str = "critical KEV vulns older than 30 days",
    anthropic_client_factory: Any = None,
    user_email: str = "analyst@test.local",
):
    return _run_query_stream(
        db_session,
        tenant_id=tenant_id,
        user_email=user_email,
        question=question,
        redis_client=redis_client,
        anthropic_client_factory=anthropic_client_factory,
    )


# ── Precondition envelope (NLQ-03, D-18) ────────────────────────────────────


async def test_no_key_precondition(db_session: Any, tenant_a: Any, flushed_redis: Any) -> None:
    # Deliberately no ANTHROPIC ConnectorConfig row seeded for this tenant.
    frames = [f async for f in _run_stream(db_session, tenant_a, flushed_redis)]
    decoded = [_decode_frame(f) for f in frames]

    assert decoded == [{"type": "no_key"}]
    rows = await _query_audit_rows(db_session, tenant_a)
    assert rows == []  # AI-01/D-23: never audited -- nothing was attempted


async def test_budget_exceeded_dispatches_zero_anthropic_calls(
    db_session: Any, tenant_a: Any, flushed_redis: Any
) -> None:
    await _seed_anthropic_connector(db_session, tenant_a, monthly_budget_usd=10.0)
    await _seed_ai_spend(db_session, tenant_a, 10.0)  # spend == cap -> fail-closed
    fake_client = _FakeAsyncAnthropic([])  # any .stream() call here would IndexError

    with patch("app.ai.query_assistant.notify_admins_budget_exceeded", new_callable=AsyncMock) as mock_notify:
        frames = [
            f
            async for f in _run_stream(
                db_session, tenant_a, flushed_redis, anthropic_client_factory=lambda k: fake_client
            )
        ]
    decoded = [_decode_frame(f) for f in frames]

    assert decoded == [{"type": "error", "kind": "budget_exceeded"}]
    mock_notify.assert_awaited_once()
    assert fake_client.messages.call_count == 0

    rows = await _query_audit_rows(db_session, tenant_a)
    assert rows[-1].details["status"] == "budget_exceeded"


async def test_abort_mid_stream_releases_inflight_guard(db_session: Any, tenant_a: Any, flushed_redis: Any) -> None:
    await _seed_anthropic_connector(db_session, tenant_a)
    fake_client = _FakeAsyncAnthropic([_make_message(_translate_payload()), _make_message(_narrate_payload())])

    gen = _run_stream(db_session, tenant_a, flushed_redis, anthropic_client_factory=lambda k: fake_client)
    first_frame = await gen.__anext__()
    assert first_frame

    assert await acquire_inflight(flushed_redis, tenant_a) is False
    await gen.aclose()
    assert await acquire_inflight(flushed_redis, tenant_a) is True


# ── D-15: results-first, narrative streams after ────────────────────────────


async def test_results_before_narrative(db_session: Any, tenant_a: Any, flushed_redis: Any) -> None:
    await _seed_anthropic_connector(db_session, tenant_a)
    await _seed_vulnerability(db_session, tenant_a)
    fake_client = _FakeAsyncAnthropic([_make_message(_translate_payload()), _make_message(_narrate_payload())])

    frames = [
        f
        async for f in _run_stream(db_session, tenant_a, flushed_redis, anthropic_client_factory=lambda k: fake_client)
    ]
    decoded = [_decode_frame(f) for f in frames]
    types = [d["type"] for d in decoded]

    assert "interpreted" in types
    assert "results" in types
    assert "summary_delta" in types
    assert types.index("interpreted") < types.index("results") < types.index("summary_delta")
    assert types[-1] == "done"


async def test_happy_path_full_flow_shape(db_session: Any, tenant_a: Any, flushed_redis: Any) -> None:
    await _seed_anthropic_connector(db_session, tenant_a)
    vuln_id = await _seed_vulnerability(db_session, tenant_a)
    fake_client = _FakeAsyncAnthropic([_make_message(_translate_payload()), _make_message(_narrate_payload())])

    frames = [
        f
        async for f in _run_stream(db_session, tenant_a, flushed_redis, anthropic_client_factory=lambda k: fake_client)
    ]
    decoded = [_decode_frame(f) for f in frames]

    interpreted = next(d for d in decoded if d["type"] == "interpreted")
    assert interpreted["entity"] == "vulnerabilities"
    assert interpreted["filter"]["cisa_kev"] is True
    assert interpreted["filter"]["age_days_min"] == 30

    results = next(d for d in decoded if d["type"] == "results")
    assert results["total"] == 1
    assert results["rows"][0]["id"] == str(vuln_id)

    done = decoded[-1]
    assert done["type"] == "done"
    assert done["summary"] == _narrate_payload()["summary"]
    assert done["grounded"] is True


# ── NLQ-02: tenant_id ALWAYS from the authenticated session ─────────────────


async def test_tenant_id_never_from_model(db_session: Any, tenant_a: Any, flushed_redis: Any) -> None:
    await _seed_anthropic_connector(db_session, tenant_a)
    fake_client = _FakeAsyncAnthropic([_make_message(_translate_payload()), _make_message(_narrate_payload())])

    fake_result: PaginatedResponse[Any] = PaginatedResponse.create(
        items=[], total=0, params=PaginationParams(page=1, page_size=10)
    )
    with patch(
        "app.ai.query_assistant.list_vulnerabilities", new=AsyncMock(return_value=fake_result)
    ) as mock_list_vulnerabilities:
        frames = [
            f
            async for f in _run_stream(
                db_session, tenant_a, flushed_redis, anthropic_client_factory=lambda k: fake_client
            )
        ]

    decoded = [_decode_frame(f) for f in frames]
    assert decoded[-1]["type"] == "done"

    mock_list_vulnerabilities.assert_awaited_once()
    call_args = mock_list_vulnerabilities.await_args
    assert call_args is not None
    assert call_args.args[1] == tenant_a


async def test_deterministic_triage_sort_applied_to_query(db_session: Any, tenant_a: Any, flushed_redis: Any) -> None:
    """D-07: the top-N passed to narrate uses list_vulnerabilities' existing
    risk-ranked ORDER BY (sort='triage') -- hardcoded by the orchestrator,
    never model-supplied (VulnFilterInput has no `sort` field at all)."""
    await _seed_anthropic_connector(db_session, tenant_a)
    fake_client = _FakeAsyncAnthropic([_make_message(_translate_payload()), _make_message(_narrate_payload())])

    fake_result: PaginatedResponse[Any] = PaginatedResponse.create(
        items=[], total=0, params=PaginationParams(page=1, page_size=10)
    )
    with patch("app.ai.query_assistant.list_vulnerabilities", new=AsyncMock(return_value=fake_result)) as mock_list:
        _ = [
            f
            async for f in _run_stream(
                db_session, tenant_a, flushed_redis, anthropic_client_factory=lambda k: fake_client
            )
        ]

    call_args = mock_list.await_args
    assert call_args is not None
    passed_filter = call_args.args[2]
    assert passed_filter.sort == "triage"
    assert passed_filter.cisa_kev is True
    assert passed_filter.age_days_min == 30
    passed_pagination = call_args.args[3]
    assert passed_pagination.page_size == 10


# ── D-14: honest refusal vs. Plan-02-deferred entities ──────────────────────


async def test_groundable_false_yields_refuse_only(db_session: Any, tenant_a: Any, flushed_redis: Any) -> None:
    await _seed_anthropic_connector(db_session, tenant_a)
    refusal = _translate_payload(vulnerability_filter=None, groundable=False)
    fake_client = _FakeAsyncAnthropic([_make_message(refusal)])

    frames = [
        f
        async for f in _run_stream(db_session, tenant_a, flushed_redis, anthropic_client_factory=lambda k: fake_client)
    ]
    decoded = [_decode_frame(f) for f in frames]

    assert decoded == [{"type": "refuse"}]
    assert fake_client.messages.call_count == 1  # narrate never dispatched


async def test_assets_entity_yields_guarded_refuse_placeholder(
    db_session: Any, tenant_a: Any, flushed_redis: Any
) -> None:
    """Plan 01 proves the spine on vulnerabilities only -- assets/tickets
    are a guarded no-op placeholder this plan (Plan 02 wires the real
    branches)."""
    await _seed_anthropic_connector(db_session, tenant_a)
    translate = _translate_payload(
        entity="assets",
        vulnerability_filter=None,
        asset_filter={"device_category": "SERVER"},
        groundable=True,
    )
    fake_client = _FakeAsyncAnthropic([_make_message(translate)])

    frames = [
        f
        async for f in _run_stream(db_session, tenant_a, flushed_redis, anthropic_client_factory=lambda k: fake_client)
    ]
    decoded = [_decode_frame(f) for f in frames]

    assert decoded == [{"type": "refuse"}]


# ── D-19: translation cache (question -> filter only) ────────────────────────


async def test_translation_cache_hit_skips_second_translate_call(
    db_session: Any, tenant_a: Any, flushed_redis: Any
) -> None:
    await _seed_anthropic_connector(db_session, tenant_a)
    fake_client = _FakeAsyncAnthropic(
        [
            _make_message(_translate_payload()),  # run 1: translate
            _make_message(_narrate_payload()),  # run 1: narrate
            _make_message(_narrate_payload()),  # run 2: narrate only -- translate is cached
        ]
    )
    question = "critical KEV vulns older than 30 days"

    frames_1 = [
        f
        async for f in _run_stream(
            db_session, tenant_a, flushed_redis, question=question, anthropic_client_factory=lambda k: fake_client
        )
    ]
    frames_2 = [
        f
        async for f in _run_stream(
            db_session, tenant_a, flushed_redis, question=question, anthropic_client_factory=lambda k: fake_client
        )
    ]

    assert _decode_frame(frames_1[-1])["type"] == "done"
    assert _decode_frame(frames_2[-1])["type"] == "done"
    # 2 translate calls would have been 4 total; caching the translation
    # means only 3 real model calls happen across both runs.
    assert fake_client.messages.call_count == 3

    rows = await _query_audit_rows(db_session, tenant_a)
    translate_rows = [r for r in rows if r.resource_type == "translate"]
    assert len(translate_rows) == 1  # only run 1's translate was ever audited


async def test_translation_cache_is_tenant_scoped(
    db_session: Any, tenant_a: Any, tenant_b: Any, flushed_redis: Any
) -> None:
    """A cached translation for tenant_a must never serve tenant_b -- the
    tenant_id is always the first interpolated segment of the cache key
    (mirrors cache.py's own AI-05 isolation contract)."""
    await _seed_anthropic_connector(db_session, tenant_a)
    await _seed_anthropic_connector(db_session, tenant_b)
    fake_client = _FakeAsyncAnthropic(
        [
            _make_message(_translate_payload()),
            _make_message(_narrate_payload()),
            _make_message(_translate_payload()),  # tenant_b must NOT hit tenant_a's cache
            _make_message(_narrate_payload()),
        ]
    )
    question = "critical KEV vulns older than 30 days"

    _ = [
        f
        async for f in _run_stream(
            db_session, tenant_a, flushed_redis, question=question, anthropic_client_factory=lambda k: fake_client
        )
    ]
    _ = [
        f
        async for f in _run_stream(
            db_session, tenant_b, flushed_redis, question=question, anthropic_client_factory=lambda k: fake_client
        )
    ]

    assert fake_client.messages.call_count == 4  # no cross-tenant cache reuse


# ── Retry loop: schema/business-rule validation failures ────────────────────


async def test_translate_two_malformed_responses_terminal_error_two_audit_rows(
    db_session: Any, tenant_a: Any, flushed_redis: Any
) -> None:
    bad_1 = _make_message_from_text("not valid json {{{")
    bad_2 = _make_message_from_text("still not valid json ]]]")
    await _seed_anthropic_connector(db_session, tenant_a)
    fake_client = _FakeAsyncAnthropic([bad_1, bad_2])

    frames = [
        f
        async for f in _run_stream(db_session, tenant_a, flushed_redis, anthropic_client_factory=lambda k: fake_client)
    ]
    decoded = [_decode_frame(f) for f in frames]

    assert decoded == [{"type": "error", "kind": "grounded_false"}]
    assert fake_client.messages.call_count == 2

    rows = await _query_audit_rows(db_session, tenant_a)
    assert len(rows) == 2
    assert all(r.details["status"] == "validation_failed" for r in rows)
    assert all(r.resource_type == "translate" for r in rows)


async def test_exclusivity_violation_retries_once_then_succeeds(
    db_session: Any, tenant_a: Any, flushed_redis: Any
) -> None:
    """recheck_nlq_filter_exclusivity's BusinessRuleError is treated exactly
    like a schema ValidationError -- one corrective retry, not an
    immediate terminal failure."""
    bad_exclusivity = _translate_payload(asset_filter={"device_category": "SERVER"})  # 2 filters populated
    good = _translate_payload()
    await _seed_anthropic_connector(db_session, tenant_a)
    fake_client = _FakeAsyncAnthropic(
        [_make_message(bad_exclusivity), _make_message(good), _make_message(_narrate_payload())]
    )

    frames = [
        f
        async for f in _run_stream(db_session, tenant_a, flushed_redis, anthropic_client_factory=lambda k: fake_client)
    ]
    decoded = [_decode_frame(f) for f in frames]

    assert decoded[-1]["type"] == "done"
    assert fake_client.messages.call_count == 3

    rows = await _query_audit_rows(db_session, tenant_a)
    assert [r.details["status"] for r in rows] == ["validation_failed", "ok", "ok"]


async def test_narrate_validation_failure_terminal_error(db_session: Any, tenant_a: Any, flushed_redis: Any) -> None:
    bad_narrate_1 = _make_message_from_text("not valid json {{{")
    bad_narrate_2 = _make_message_from_text("still not valid json ]]]")
    await _seed_anthropic_connector(db_session, tenant_a)
    fake_client = _FakeAsyncAnthropic([_make_message(_translate_payload()), bad_narrate_1, bad_narrate_2])

    frames = [
        f
        async for f in _run_stream(db_session, tenant_a, flushed_redis, anthropic_client_factory=lambda k: fake_client)
    ]
    decoded = [_decode_frame(f) for f in frames]

    # interpreted + results already streamed (D-15) before narrate failed.
    assert decoded[0]["type"] == "interpreted"
    assert decoded[1]["type"] == "results"
    assert decoded[-1] == {"type": "error", "kind": "grounded_false"}

    rows = await _query_audit_rows(db_session, tenant_a)
    narrate_rows = [r for r in rows if r.resource_type == "narrate"]
    assert len(narrate_rows) == 2
    assert all(r.details["status"] == "validation_failed" for r in narrate_rows)


# ── Audit trail (D-16/NLQ-02 provability): both calls land as ai.query.* ────


async def test_full_flow_audits_both_calls_with_query_prefix(
    db_session: Any, tenant_a: Any, flushed_redis: Any
) -> None:
    await _seed_anthropic_connector(db_session, tenant_a)
    fake_client = _FakeAsyncAnthropic([_make_message(_translate_payload()), _make_message(_narrate_payload())])

    _ = [
        f
        async for f in _run_stream(db_session, tenant_a, flushed_redis, anthropic_client_factory=lambda k: fake_client)
    ]

    rows = await _query_audit_rows(db_session, tenant_a)
    assert len(rows) == 2
    assert {r.resource_type for r in rows} == {"translate", "narrate"}
    assert all(r.action.startswith("ai.query.") for r in rows)
    assert [r.details["status"] for r in rows] == ["ok", "ok"]
    assert all(r.details["cost_estimate_usd"] is not None for r in rows)


# ── _resolve_hostname (deterministic, tenant-scoped, non-model) ─────────────


async def test_resolve_hostname_returns_matching_asset_id(db_session: Any, tenant_a: Any) -> None:
    from app.assets.models import Asset

    asset = Asset(tenant_id=tenant_a, hostname="web-prod-03")
    db_session.add(asset)
    await db_session.commit()

    resolved = await _resolve_hostname(db_session, tenant_a, "web-prod-03")
    assert resolved == asset.id


async def test_resolve_hostname_unresolved_returns_none(db_session: Any, tenant_a: Any) -> None:
    resolved = await _resolve_hostname(db_session, tenant_a, "does-not-exist-anywhere")
    assert resolved is None


async def test_resolve_hostname_is_tenant_scoped(db_session: Any, tenant_a: Any, tenant_b: Any) -> None:
    from app.assets.models import Asset

    asset = Asset(tenant_id=tenant_b, hostname="tenant-b-only-host")
    db_session.add(asset)
    await db_session.commit()

    resolved = await _resolve_hostname(db_session, tenant_a, "tenant-b-only-host")
    assert resolved is None


# ── Task 3: route-level tests (RBAC, headers, request validation) ───────────


async def _fake_query_stream(*args: Any, **kwargs: Any):
    payload = {"type": "done", **_narrate_payload()}
    yield f"data: {json.dumps(payload)}\n\n".encode()


async def test_post_query_as_analyst_returns_200_sse_with_headers(
    client_factory: Any, db_session: Any, tenant_a: Any, analyst_user: Any
) -> None:
    client = client_factory(analyst_user)

    with patch("app.api.v1.ai.query._run_query_stream", _fake_query_stream):
        resp = await client.post("/api/v1/ai/query", json={"question": "critical KEV vulns older than 30 days"})

    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert "no-cache" in resp.headers["cache-control"]
    assert resp.headers["x-accel-buffering"] == "no"
    assert '"type": "done"' in resp.text


async def test_post_query_as_viewer_returns_403(
    client_factory: Any, db_session: Any, tenant_a: Any, viewer_user: Any
) -> None:
    client = client_factory(viewer_user)
    resp = await client.post("/api/v1/ai/query", json={"question": "critical KEV vulns older than 30 days"})
    assert resp.status_code == 403


async def test_post_query_rejects_empty_question(
    client_factory: Any, db_session: Any, tenant_a: Any, analyst_user: Any
) -> None:
    client = client_factory(analyst_user)
    resp = await client.post("/api/v1/ai/query", json={"question": ""})
    assert resp.status_code == 422


async def test_post_query_rejects_overlong_question(
    client_factory: Any, db_session: Any, tenant_a: Any, analyst_user: Any
) -> None:
    client = client_factory(analyst_user)
    resp = await client.post("/api/v1/ai/query", json={"question": "x" * 501})
    assert resp.status_code == 422


async def test_post_query_end_to_end_through_route(
    client_factory: Any, db_session: Any, tenant_a: Any, analyst_user: Any
) -> None:
    """A real (keyless) POST through the actual route + orchestrator --
    proves the no_key inert precondition end-to-end via the real HTTP path,
    not just the generator function directly."""
    client = client_factory(analyst_user)
    resp = await client.post("/api/v1/ai/query", json={"question": "critical KEV vulns older than 30 days"})

    assert resp.status_code == 200, resp.text
    assert '"type": "no_key"' in resp.text
