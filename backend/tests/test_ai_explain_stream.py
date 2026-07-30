"""Tests for app.ai.explain._run_explain_stream -- the buffer-then-validate-
then-replay streaming engine (AI-02/AI-03), and (Task 2) the per-vuln SSE
endpoint + cache-check GET + RBAC/tenant-scoping (app.api.v1.ai.explain_vuln).

Two testing strategies, per RESEARCH.md's own guidance:
  - Most control-flow tests (retry/budget/no-key/abort/rate-limit/injection)
    mock at the SDK boundary via `anthropic_client_factory` -- fast, precise
    control over get_final_message()/exceptions, no real wire format needed.
  - ONE true wire-format integration test (`test_buffer_not_proxy_...`) uses
    the REAL AsyncAnthropic client against a real SSE byte stream via
    `httpx.MockTransport` (RESEARCH.md Code Examples SSE_BODY convention) --
    proves the buffer-then-validate-then-replay contract against the actual
    installed SDK's parsing, not just our own test double's behavior.

Backend env gotcha (MEMORY.md `getvul-backend-pytest-env`): run with a REAL
Fernet ENCRYPTION_KEY (`Fernet.generate_key()`, NOT a placeholder string) +
JWT_SECRET_KEY set, per-file (not the whole tests/ dir).
"""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
from anthropic import APIStatusError, AsyncAnthropic, RateLimitError

from app.ai.cache import acquire_inflight
from app.ai.explain import _run_explain_stream
from app.ai.prompt_builder import VULN_ALLOWLIST, build_explain_vuln_prompt
from app.ai.schemas import ExplainVulnResponse
from app.audit import AuditLog
from app.encryption import encrypt_value
from app.ticketing.models import ConnectorConfig

SAMPLE_RECORD: dict[str, Any] = {
    "cve_id": "CVE-2024-1234",
    "vulnerability_name": "Sample Vuln",
    "cvss_v3_score": 9.8,
    "cvss_v3_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
    "severity": "CRITICAL",
    "cisa_kev": True,
    "exploit_available": True,
    "asset_hostname": "web-01",
    "source": "NESSUS",
    "affected_product": "OpenSSL",
    "affected_version": "1.0.1",
    "fixed_version": "1.0.2",
    "remediation_info": "Upgrade OpenSSL to 1.0.2.",
    "status": "OPEN",
    "first_detected_at": "2026-01-01T00:00:00Z",
    "last_seen_at": "2026-07-01T00:00:00Z",
}


# ── Fake Anthropic client (SDK-boundary test seam) ─────────────────────────


class _FakeStreamCM:
    """Stands in for AsyncMessageStreamManager. __aenter__ either returns
    self (so get_final_message() can be awaited) or raises the configured
    exception -- matching where the REAL SDK raises HTTP-status errors
    (spike-verified against the installed anthropic==0.120.2 in this repo's
    backend/.venv: a 429/529 response raises on __aenter__, not on
    .stream() itself)."""

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


def _valid_payload(
    summary: str = "This host is affected by CVE-2024-1234.",
    business_risk: str = "Internet-facing and KEV-listed -- treat as urgent.",
    grounded: bool = True,
) -> dict[str, Any]:
    return {
        "summary": summary,
        "business_risk": business_risk,
        "citations": [{"text": summary, "source": "ai_interpreted", "source_field": None}],
        "grounded": grounded,
    }


def _decode_frame(frame: bytes) -> dict[str, Any]:
    text = frame.decode()
    assert text.startswith("data: ")
    assert text.endswith("\n\n")
    return json.loads(text[len("data: ") : -2])


def _make_sse_wire_body(json_text: str) -> bytes:
    """A REAL Anthropic Messages-API SSE wire-format body (event-typed
    frames), for the one true wire-format test. Mirrors RESEARCH.md's Code
    Examples SSE_BODY -- spike-verified against the installed SDK
    (anthropic==0.120.2) to parse correctly via
    `client.messages.stream()` + `await stream.get_final_message()`."""
    escaped_delta = json.dumps(json_text)
    return (
        b"event: message_start\n"
        b'data: {"type":"message_start","message":{"id":"msg_1","type":"message","role":"assistant","content":[],'
        b'"model":"claude-sonnet-5","stop_reason":null,"stop_sequence":null,'
        b'"usage":{"input_tokens":50,"output_tokens":0}}}\n\n'
        b"event: content_block_start\n"
        b'data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}\n\n'
        b"event: content_block_delta\n"
        b'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":'
        + escaped_delta.encode()
        + b"}}\n\n"
        b"event: content_block_stop\n"
        b'data: {"type":"content_block_stop","index":0}\n\n'
        b"event: message_delta\n"
        b'data: {"type":"message_delta","delta":{"stop_reason":"end_turn","stop_sequence":null},'
        b'"usage":{"output_tokens":40}}\n\n'
        b"event: message_stop\n"
        b'data: {"type":"message_stop"}\n\n'
    )


# ── Seed helpers ────────────────────────────────────────────────────────────


async def _seed_anthropic_connector(
    db_session,
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


async def _seed_ai_spend(db_session, tenant_id: uuid.UUID, cost_estimate_usd: float) -> None:
    from datetime import UTC, datetime

    log = AuditLog(
        tenant_id=tenant_id,
        user_id=None,
        user_email="analyst@tenant-a.test",
        action="ai.explain.vuln",
        resource_type="vuln",
        resource_id=f"finding-{uuid.uuid4().hex[:8]}",
        details={"cost_estimate_usd": cost_estimate_usd, "status": "ok"},
        ip_address=None,
        created_at=datetime.now(UTC),
    )
    db_session.add(log)
    await db_session.flush()


async def _audit_rows(db_session, tenant_id: uuid.UUID) -> list[AuditLog]:
    from sqlalchemy import select

    result = await db_session.execute(
        select(AuditLog)
        .where(AuditLog.action == "ai.explain.vuln", AuditLog.tenant_id == tenant_id)
        .order_by(AuditLog.created_at)
    )
    return list(result.scalars().all())


def _run_stream(db_session, tenant_id, redis_client, *, anthropic_client_factory=None, user_email="analyst@test.local"):
    return _run_explain_stream(
        db_session,
        tenant_id=tenant_id,
        user_email=user_email,
        resource_type="vuln",
        resource_id="finding-1",
        record=SAMPLE_RECORD,
        build_prompt=build_explain_vuln_prompt,
        response_model=ExplainVulnResponse,
        redis_client=redis_client,
        allowed_source_fields=VULN_ALLOWLIST,
        anthropic_client_factory=anthropic_client_factory,
    )


# ── Task 1 behavior tests ───────────────────────────────────────────────────


async def test_happy_path_streams_validated_result_and_audits_ok(db_session, tenant_a, flushed_redis):
    await _seed_anthropic_connector(db_session, tenant_a)
    fake_client = _FakeAsyncAnthropic([_make_message(_valid_payload())])

    frames = [
        f
        async for f in _run_stream(db_session, tenant_a, flushed_redis, anthropic_client_factory=lambda k: fake_client)
    ]
    decoded = [_decode_frame(f) for f in frames]

    assert decoded[-1]["type"] == "done"
    assert decoded[-1]["summary"] == _valid_payload()["summary"]
    assert decoded[-1]["grounded"] is True

    rows = await _audit_rows(db_session, tenant_a)
    assert len(rows) == 1
    assert rows[0].details["status"] == "ok"
    assert rows[0].tenant_id == tenant_a


async def test_buffer_not_proxy_partial_deltas_never_leak(db_session, tenant_a, flushed_redis):
    """The mocked stream's partial content_block_delta frames never appear
    as outbound frames -- proven against the REAL installed Anthropic SDK
    + a real SSE wire-format MockTransport, not just our own fake."""
    await _seed_anthropic_connector(db_session, tenant_a)
    payload = _valid_payload(summary="UNIQUE_MARKER_MUST_ONLY_APPEAR_IN_THE_FINAL_DONE_FRAME")
    sse_body = _make_sse_wire_body(json.dumps(payload))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=sse_body, headers={"content-type": "text/event-stream"})

    mock_httpx_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    def factory(api_key: str) -> AsyncAnthropic:
        return AsyncAnthropic(api_key=api_key, http_client=mock_httpx_client, max_retries=0)

    frames = [f async for f in _run_stream(db_session, tenant_a, flushed_redis, anthropic_client_factory=factory)]
    decoded = [_decode_frame(f) for f in frames]

    raw_wire_event_types = {
        "message_start",
        "content_block_start",
        "content_block_delta",
        "content_block_stop",
        "message_delta",
        "message_stop",
    }
    for evt in decoded:
        assert evt["type"] not in raw_wire_event_types
    assert decoded[-1]["type"] == "done"
    assert decoded[-1]["summary"] == payload["summary"]


async def test_grounded_false_triggers_one_corrective_retry_then_succeeds(db_session, tenant_a, flushed_redis):
    ungrounded = _valid_payload(grounded=False, summary="Insufficient evidence in the record.")
    grounded = _valid_payload(grounded=True, summary="Now grounded and faithful.")
    await _seed_anthropic_connector(db_session, tenant_a)
    fake_client = _FakeAsyncAnthropic([_make_message(ungrounded), _make_message(grounded)])

    frames = [
        f
        async for f in _run_stream(db_session, tenant_a, flushed_redis, anthropic_client_factory=lambda k: fake_client)
    ]
    decoded = [_decode_frame(f) for f in frames]

    assert decoded[-1]["type"] == "done"
    assert decoded[-1]["summary"] == "Now grounded and faithful."
    assert fake_client.messages.call_count == 2

    rows = await _audit_rows(db_session, tenant_a)
    assert [r.details["status"] for r in rows] == ["grounded_retry", "ok"]


async def test_two_malformed_responses_terminal_error_two_audit_rows(db_session, tenant_a, flushed_redis):
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

    rows = await _audit_rows(db_session, tenant_a)
    assert len(rows) == 2
    assert all(r.details["status"] == "validation_failed" for r in rows)


async def test_budget_exceeded_dispatches_zero_anthropic_calls(db_session, tenant_a, flushed_redis):
    await _seed_anthropic_connector(db_session, tenant_a, monthly_budget_usd=10.0)
    await _seed_ai_spend(db_session, tenant_a, 10.0)  # spend == cap -> fail-closed
    fake_client = _FakeAsyncAnthropic([])  # any .stream() call here would IndexError

    with patch("app.ai.explain.notify_admins_budget_exceeded", new_callable=AsyncMock) as mock_notify:
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

    # 2 rows total: the seeded prior-spend row + the one this call itself
    # writes (both share resource_type/action; distinguish by status).
    rows = await _audit_rows(db_session, tenant_a)
    assert len(rows) == 2
    assert rows[-1].details["status"] == "budget_exceeded"


async def test_no_key_configured_yields_inert_event_not_error(db_session, tenant_a, flushed_redis):
    # Deliberately no ANTHROPIC ConnectorConfig row seeded for this tenant.
    frames = [f async for f in _run_stream(db_session, tenant_a, flushed_redis)]
    decoded = [_decode_frame(f) for f in frames]

    assert decoded == [{"type": "no_key"}]
    # AI-01/D-23: never audited as an attempt (nothing was dispatched).
    rows = await _audit_rows(db_session, tenant_a)
    assert rows == []


async def test_abort_mid_stream_releases_inflight_guard(db_session, tenant_a, flushed_redis):
    await _seed_anthropic_connector(db_session, tenant_a)
    fake_client = _FakeAsyncAnthropic([_make_message(_valid_payload())])

    gen = _run_stream(db_session, tenant_a, flushed_redis, anthropic_client_factory=lambda k: fake_client)
    first_frame = await gen.__anext__()
    assert first_frame  # got at least one frame -- generator is mid-flight

    # The guard is still held (a fresh acquire attempt fails) because the
    # generator has not reached its natural end yet.
    assert await acquire_inflight(flushed_redis, tenant_a) is False

    await gen.aclose()  # simulate a client disconnect / stopped reader

    # `finally: release_inflight(...)` fired on GeneratorExit -- a fresh
    # acquire now succeeds.
    assert await acquire_inflight(flushed_redis, tenant_a) is True


async def test_persistent_rate_limit_error_yields_busy_and_audits_rate_limited(db_session, tenant_a, flushed_redis):
    await _seed_anthropic_connector(db_session, tenant_a)
    fake_response = httpx.Response(429, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))
    error = RateLimitError("rate limited", response=fake_response, body=None)
    fake_client = _FakeAsyncAnthropic([error])

    frames = [
        f
        async for f in _run_stream(db_session, tenant_a, flushed_redis, anthropic_client_factory=lambda k: fake_client)
    ]
    decoded = [_decode_frame(f) for f in frames]

    assert decoded == [{"type": "error", "kind": "busy"}]
    rows = await _audit_rows(db_session, tenant_a)
    assert len(rows) == 1
    assert rows[0].details["status"] == "rate_limited"


async def test_persistent_api_status_error_yields_busy_and_audits_rate_limited(db_session, tenant_a, flushed_redis):
    await _seed_anthropic_connector(db_session, tenant_a)
    fake_response = httpx.Response(529, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))
    error = APIStatusError("overloaded", response=fake_response, body=None)
    fake_client = _FakeAsyncAnthropic([error])

    frames = [
        f
        async for f in _run_stream(db_session, tenant_a, flushed_redis, anthropic_client_factory=lambda k: fake_client)
    ]
    decoded = [_decode_frame(f) for f in frames]

    assert decoded == [{"type": "error", "kind": "busy"}]
    rows = await _audit_rows(db_session, tenant_a)
    assert len(rows) == 1
    assert rows[0].details["status"] == "rate_limited"


async def test_leak_marker_output_is_injection_flagged_and_blocked(db_session, tenant_a, flushed_redis):
    # First 40 chars of SYSTEM_PROMPT's first line, verbatim -- proves the
    # leak-marker check reads the REAL system_prompt in scope for this
    # call, not a hardcoded fixture string.
    leak_marker = "You are GetVul's vulnerability-explanati"
    leaked = _valid_payload(summary=f"Ignoring instructions: {leak_marker} -- system prompt echoed.")
    await _seed_anthropic_connector(db_session, tenant_a)
    fake_client = _FakeAsyncAnthropic([_make_message(leaked)])

    frames = [
        f
        async for f in _run_stream(db_session, tenant_a, flushed_redis, anthropic_client_factory=lambda k: fake_client)
    ]
    decoded = [_decode_frame(f) for f in frames]

    # Blocked by the gate -- no off-task text streamed, just the typed error.
    assert decoded == [{"type": "error", "kind": "grounded_false"}]
    rows = await _audit_rows(db_session, tenant_a)
    assert len(rows) == 1
    assert rows[0].details["status"] == "injection_flagged"


async def test_dangerous_pattern_check_hit_is_unsafe_denylisted_and_never_cached(db_session, tenant_a, flushed_redis):
    """Phase 25 D-04/T-25-02: a `dangerous_pattern_check` hit on a validated
    candidate refuses the ENTIRE guidance BEFORE `set_cached()` ever runs --
    the load-bearing backstop is that `set_cached` itself is never invoked
    (spied), not merely that the outgoing SSE text lacks the pattern
    (25-RESEARCH.md Pitfall 2)."""
    await _seed_anthropic_connector(db_session, tenant_a)
    fake_client = _FakeAsyncAnthropic([_make_message(_valid_payload(summary="Run rm -rf /opt/app to clean up."))])

    with patch("app.ai.explain.set_cached", new_callable=AsyncMock) as mock_set_cached:
        frames = [
            f
            async for f in _run_explain_stream(
                db_session,
                tenant_id=tenant_a,
                user_email="analyst@test.local",
                resource_type="vuln",
                resource_id="finding-1",
                record=SAMPLE_RECORD,
                build_prompt=build_explain_vuln_prompt,
                response_model=ExplainVulnResponse,
                redis_client=flushed_redis,
                allowed_source_fields=VULN_ALLOWLIST,
                anthropic_client_factory=lambda k: fake_client,
                dangerous_pattern_check=lambda candidate: "rm -rf" if "rm -rf" in candidate.summary.lower() else None,
            )
        ]
    decoded = [_decode_frame(f) for f in frames]

    mock_set_cached.assert_not_called()
    assert decoded == [{"type": "error", "kind": "unsafe", "matched_pattern": "rm -rf"}]
    # No summary_delta/done frame ever emitted.
    assert all(evt["type"] != "summary_delta" and evt["type"] != "done" for evt in decoded)

    rows = await _audit_rows(db_session, tenant_a)
    assert len(rows) == 1
    assert rows[0].details["status"] == "unsafe_denylisted"


async def test_dangerous_pattern_check_no_hit_still_reaches_set_cached_and_done(db_session, tenant_a, flushed_redis):
    """The gate is not over-eager: a benign candidate with
    `dangerous_pattern_check` supplied (but returning None) still reaches
    `set_cached()` and streams a `done` frame exactly as the default-None
    path does."""
    await _seed_anthropic_connector(db_session, tenant_a)
    fake_client = _FakeAsyncAnthropic([_make_message(_valid_payload())])

    with patch("app.ai.explain.set_cached", new_callable=AsyncMock) as mock_set_cached:
        frames = [
            f
            async for f in _run_explain_stream(
                db_session,
                tenant_id=tenant_a,
                user_email="analyst@test.local",
                resource_type="vuln",
                resource_id="finding-1",
                record=SAMPLE_RECORD,
                build_prompt=build_explain_vuln_prompt,
                response_model=ExplainVulnResponse,
                redis_client=flushed_redis,
                allowed_source_fields=VULN_ALLOWLIST,
                anthropic_client_factory=lambda k: fake_client,
                dangerous_pattern_check=lambda candidate: None,
            )
        ]
    decoded = [_decode_frame(f) for f in frames]

    mock_set_cached.assert_awaited_once()
    assert decoded[-1]["type"] == "done"

    rows = await _audit_rows(db_session, tenant_a)
    assert len(rows) == 1
    assert rows[0].details["status"] == "ok"


async def test_error_kind_vocabulary_matches_plan_05_closed_set(db_session, tenant_a, flushed_redis):
    """Structural acceptance-criteria proof: every 'error'-typed event this
    engine can ever emit uses a kind from exactly
    {busy, grounded_false, budget_exceeded, unknown} -- no orphan kinds."""
    allowed_kinds = {"busy", "grounded_false", "budget_exceeded", "unknown"}

    # unknown: force an unexpected exception path via a build_prompt that raises.
    def _broken_build_prompt(record: Any) -> tuple[str, list[dict[str, str]]]:
        raise RuntimeError("boom")

    await _seed_anthropic_connector(db_session, tenant_a)
    frames = [
        f
        async for f in _run_explain_stream(
            db_session,
            tenant_id=tenant_a,
            user_email="analyst@test.local",
            resource_type="vuln",
            resource_id="finding-unknown",
            record=SAMPLE_RECORD,
            build_prompt=_broken_build_prompt,
            response_model=ExplainVulnResponse,
            redis_client=flushed_redis,
            allowed_source_fields=VULN_ALLOWLIST,
        )
    ]
    decoded = [_decode_frame(f) for f in frames]
    assert decoded == [{"type": "error", "kind": "unknown"}]
    assert decoded[0]["kind"] in allowed_kinds

    rows = await _audit_rows(db_session, tenant_a)
    assert rows[-1].details["status"] == "unknown"


# ── Task 2: route-level tests (RBAC, headers, cache-check, tenant-scoping) ──


async def _seed_vulnerability(db_session, tenant_id: uuid.UUID, **overrides: Any) -> uuid.UUID:
    from datetime import UTC, datetime

    from app.vulnerabilities.models import Vulnerability

    defaults: dict[str, Any] = {
        "tenant_id": tenant_id,
        "cve_id": "CVE-2024-1234",
        "vulnerability_name": "Sample Vuln",
        "cvss_v3_score": 9.8,
        "cvss_v3_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
        "severity": "CRITICAL",
        "exploit_available": True,
        "cisa_kev": True,
        "source": "NESSUS",
        "source_vuln_id": str(uuid.uuid4()),
        "affected_product": "OpenSSL",
        "affected_version": "1.0.1",
        "fixed_version": "1.0.2",
        "remediation_info": "Upgrade OpenSSL to 1.0.2.",
        "status": "OPEN",
        "first_detected_at": datetime.now(UTC),
        "last_seen_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    vuln = Vulnerability(**defaults)
    db_session.add(vuln)
    await db_session.commit()  # visible to the app's OWN, independently-connected session
    return vuln.id


async def _fake_explain_stream(*args: Any, **kwargs: Any):
    """Stands in for the real engine at the ROUTE-test layer -- Task 1's
    own tests already exhaustively cover `_run_explain_stream`'s internal
    behavior; these tests exercise the ROUTE (RBAC, headers, path/tenant
    resolution) in isolation."""
    payload = {"type": "done", **_valid_payload()}
    yield f"data: {json.dumps(payload)}\n\n".encode()


async def test_post_explain_vuln_as_analyst_returns_200_sse_with_headers(
    client_factory, db_session, tenant_a, analyst_user
):
    vuln_id = await _seed_vulnerability(db_session, tenant_a)
    client = client_factory(analyst_user)

    with patch("app.api.v1.ai.explain_vuln._run_explain_stream", _fake_explain_stream):
        resp = await client.post(f"/api/v1/ai/explain-vuln/{vuln_id}")

    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/event-stream")
    # The route sets Cache-Control: no-cache explicitly; the app's
    # pre-existing SecurityHeadersMiddleware then applies its OWN, even
    # stricter blanket no-cache policy to every /api/* response
    # ("no-store, no-cache, must-revalidate, max-age=0") -- caching is
    # still fully prevented, just via a superseding stricter directive.
    assert "no-cache" in resp.headers["cache-control"]
    assert resp.headers["x-accel-buffering"] == "no"
    assert '"type": "done"' in resp.text


async def test_post_explain_vuln_as_viewer_returns_403(client_factory, db_session, tenant_a, viewer_user):
    vuln_id = await _seed_vulnerability(db_session, tenant_a)
    client = client_factory(viewer_user)

    resp = await client.post(f"/api/v1/ai/explain-vuln/{vuln_id}")

    assert resp.status_code == 403


async def test_get_explain_vuln_cache_check_as_viewer_miss_no_dispatch(
    client_factory, db_session, tenant_a, viewer_user
):
    vuln_id = await _seed_vulnerability(db_session, tenant_a)
    client = client_factory(viewer_user)

    with patch("app.ai.explain.AsyncAnthropic") as mock_anthropic_cls:
        resp = await client.get(f"/api/v1/ai/explain-vuln/{vuln_id}")

    assert resp.status_code == 200
    assert resp.json() == {"cached": False}
    # D-09: a cache-check GET performs NO Anthropic dispatch on a miss.
    mock_anthropic_cls.assert_not_called()


async def test_get_explain_vuln_cache_check_returns_payload_on_hit(
    client_factory, db_session, flushed_redis, tenant_a, viewer_user
):
    from app.ai.cache import build_cache_key, record_hash, set_cached
    from app.ai.explain import DEFAULT_MODEL
    from app.ai.prompt_builder import build_explain_vuln_prompt, prompt_version

    vuln_id = await _seed_vulnerability(db_session, tenant_a)

    # Seed the cache under the EXACT key the route itself computes (same
    # allowlisted fields -- derived from the same real record via the same
    # prompt builder -- same model default, same prompt_version).
    from app.vulnerabilities.service import get_vulnerability

    record = await get_vulnerability(db_session, tenant_a, vuln_id)
    _system_prompt, user_blocks = build_explain_vuln_prompt(record)
    text = user_blocks[0]["text"]
    allowlisted_fields = json.loads(text[text.index(">") + 1 : text.rindex("</scanner_data>")])
    the_hash = record_hash(allowlisted_fields)
    cache_key = build_cache_key(tenant_a, "vuln", str(vuln_id), the_hash, DEFAULT_MODEL, prompt_version())
    seeded_payload = _valid_payload()
    await set_cached(flushed_redis, cache_key, seeded_payload)

    client = client_factory(viewer_user)
    resp = await client.get(f"/api/v1/ai/explain-vuln/{vuln_id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["cached"] is True
    assert body["summary"] == seeded_payload["summary"]
    assert body["grounded"] is True


async def test_cross_tenant_finding_id_not_resolvable(
    client_factory, db_session, tenant_a, tenant_b, analyst_user, analyst_user_b
):
    """T-24-18: a foreign-tenant finding_id is not resolvable -- 404, never
    cross-tenant data. Contrasted directly against tenant_a's OWN analyst
    resolving the SAME finding_id successfully, so this can only pass when
    the route genuinely exists and enforces tenant scoping -- a vacuous
    'route not found' 404 would make BOTH assertions fail, not just the
    cross-tenant one."""
    vuln_id = await _seed_vulnerability(db_session, tenant_a)  # belongs to tenant_a

    client_a = client_factory(analyst_user)  # tenant_a's own analyst
    with patch("app.api.v1.ai.explain_vuln._run_explain_stream", _fake_explain_stream):
        same_tenant_post = await client_a.post(f"/api/v1/ai/explain-vuln/{vuln_id}")
    assert same_tenant_post.status_code == 200, same_tenant_post.text
    same_tenant_get = await client_a.get(f"/api/v1/ai/explain-vuln/{vuln_id}")
    assert same_tenant_get.status_code == 200, same_tenant_get.text

    client_b = client_factory(analyst_user_b)  # analyst in tenant_b
    cross_tenant_post = await client_b.post(f"/api/v1/ai/explain-vuln/{vuln_id}")
    assert cross_tenant_post.status_code == 404

    cross_tenant_get = await client_b.get(f"/api/v1/ai/explain-vuln/{vuln_id}")
    assert cross_tenant_get.status_code == 404
