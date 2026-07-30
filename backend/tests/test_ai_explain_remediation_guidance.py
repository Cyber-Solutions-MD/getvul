"""Tests for the `explain-remediation-guidance` SSE endpoint (Phase 25
Plan 03 Task 2): app.api.v1.ai.explain_remediation_guidance.

`_run_explain_stream`'s OWN internal engine behavior (retry/audit/budget/
cache/dangerous_pattern_check/etc) is already exhaustively covered by
test_ai_explain_stream.py and reused UNCHANGED here -- most of these tests
exercise the ROUTE (RBAC, headers, D-01 pre-generation gate, cache-check,
groundable-on-miss, tenant-scoping) via the identical patched-fake-engine
seam `test_ai_explain_host_remediation.py` already established. ONE test
(the denylisted-candidate backstop) deliberately does NOT patch
`_run_explain_stream` -- it injects a fake Anthropic client at the SDK
boundary so the REAL engine's `dangerous_pattern_check` wiring is proven at
the route level, not just at Plan 03 Task 1's engine-level test.

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

from app.ai.grounding import get_remediation_guidance_context

# ── Seed helpers ─────────────────────────────────────────────────────────


async def _seed_asset(db_session, tenant_id: uuid.UUID, **overrides: Any) -> uuid.UUID:
    from app.assets.models import Asset

    defaults: dict[str, Any] = {
        "tenant_id": tenant_id,
        "hostname": f"host-{uuid.uuid4().hex[:8]}",
        "os_name": "Ubuntu",
        "os_version": "22.04",
    }
    defaults.update(overrides)
    asset = Asset(**defaults)
    db_session.add(asset)
    await db_session.commit()  # visible to the app's OWN, independently-connected session
    return asset.id


async def _seed_finding(
    db_session,
    tenant_id: uuid.UUID,
    asset_id: uuid.UUID | None = None,
    **overrides: Any,
) -> uuid.UUID:
    from app.vulnerabilities.models import Vulnerability

    defaults: dict[str, Any] = {
        "tenant_id": tenant_id,
        "asset_id": asset_id,
        "cve_id": "CVE-2024-1234",
        "vulnerability_name": "Sample Vuln",
        "severity": "CRITICAL",
        "exploit_available": True,
        "cisa_kev": True,
        "source": "NESSUS",
        "source_vuln_id": str(uuid.uuid4()),
        "affected_product": "OpenSSL",
        "affected_version": "1.0.1",
        "fixed_version": "1.0.2",
        "remediation_action": "Upgrade OpenSSL to 1.0.2 or later.",
        "remediation_info": "Upgrade OpenSSL to 1.0.2 or later.",
        "status": "OPEN",
        "first_detected_at": datetime.now(UTC),
        "last_seen_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    vuln = Vulnerability(**defaults)
    db_session.add(vuln)
    await db_session.commit()  # visible to the app's OWN, independently-connected session
    return vuln.id


async def _seed_anthropic_connector(db_session, tenant_id: uuid.UUID, api_key: str = "sk-ant-test-key-abc123") -> None:
    from app.encryption import encrypt_value
    from app.ticketing.models import ConnectorConfig

    connector = ConnectorConfig(
        tenant_id=tenant_id,
        connector_type="ANTHROPIC",
        credentials_secret_arn=json.dumps({"api_key": encrypt_value(api_key)}),
        config={},
    )
    db_session.add(connector)
    await db_session.commit()  # visible to the app's OWN, independently-connected session


def _valid_payload(summary: str = "Explained.") -> dict[str, Any]:
    return {
        "summary": summary,
        "business_risk": "Risk framing.",
        "citations": [{"text": summary, "source": "scanner_verbatim", "source_field": "remediation_action"}],
        "grounded": True,
    }


async def _fake_explain_stream(*args: Any, **kwargs: Any):
    payload = {"type": "done", **_valid_payload()}
    yield f"data: {json.dumps(payload)}\n\n".encode()


async def _audit_rows_for_action(db_session, tenant_id: uuid.UUID, action: str) -> list[Any]:
    from sqlalchemy import select

    from app.audit import AuditLog

    result = await db_session.execute(
        select(AuditLog)
        .where(AuditLog.action == action, AuditLog.tenant_id == tenant_id)
        .order_by(AuditLog.created_at)
    )
    return list(result.scalars().all())


# ── POST: RBAC + happy path ─────────────────────────────────────────────


async def test_post_as_analyst_groundable_finding_returns_200_sse_with_headers(
    client_factory, db_session, tenant_a, analyst_user
):
    finding_id = await _seed_finding(db_session, tenant_a)
    client = client_factory(analyst_user)

    with patch("app.api.v1.ai.explain_remediation_guidance._run_explain_stream", _fake_explain_stream):
        resp = await client.post(f"/api/v1/ai/explain-remediation-guidance/{finding_id}")

    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert "no-cache" in resp.headers["cache-control"]
    assert resp.headers["x-accel-buffering"] == "no"
    assert '"type": "done"' in resp.text


async def test_post_as_viewer_returns_403(client_factory, db_session, tenant_a, viewer_user):
    finding_id = await _seed_finding(db_session, tenant_a)
    client = client_factory(viewer_user)

    resp = await client.post(f"/api/v1/ai/explain-remediation-guidance/{finding_id}")

    assert resp.status_code == 403


async def test_post_missing_finding_id_returns_404(client_factory, db_session, tenant_a, analyst_user):
    client = client_factory(analyst_user)
    resp = await client.post(f"/api/v1/ai/explain-remediation-guidance/{uuid.uuid4()}")
    assert resp.status_code == 404


# ── POST: D-01 pre-generation route gate (ungroundable finding) ────────


async def test_post_ungroundable_finding_yields_single_grounded_false_frame_no_model_call(
    client_factory, db_session, tenant_a, analyst_user
):
    """D-01: a finding with no actionable remediation text is refused BEFORE
    any model call -- a single grounded_false frame, audited
    status="ungroundable", zero Anthropic dispatch."""
    finding_id = await _seed_finding(
        db_session, tenant_a, remediation_action=None, remediation_info="Unknown"
    )
    client = client_factory(analyst_user)

    with patch("app.ai.explain.AsyncAnthropic") as mock_anthropic_cls:
        resp = await client.post(f"/api/v1/ai/explain-remediation-guidance/{finding_id}")

    assert resp.status_code == 200, resp.text
    assert '"kind": "grounded_false"' in resp.text
    mock_anthropic_cls.assert_not_called()

    rows = await _audit_rows_for_action(db_session, tenant_a, "ai.explain.remediation-guidance")
    assert len(rows) == 1
    assert rows[0].details["status"] == "ungroundable"


async def test_post_empty_string_remediation_is_ungroundable(client_factory, db_session, tenant_a, analyst_user):
    """Pitfall 1: an empty-string remediation_action/remediation_info (e.g.
    Rapid7's own fetch-failure path) must be treated as absent, not
    'present', even though it is not None."""
    finding_id = await _seed_finding(db_session, tenant_a, remediation_action="", remediation_info="")
    client = client_factory(analyst_user)

    resp = await client.post(f"/api/v1/ai/explain-remediation-guidance/{finding_id}")

    assert resp.status_code == 200, resp.text
    assert '"kind": "grounded_false"' in resp.text


# ── POST: denylisted candidate -- route-level backstop (real engine, fake SDK) ──


async def test_post_denylisted_candidate_yields_unsafe_and_never_cached(
    client_factory, db_session, tenant_a, analyst_user, flushed_redis
):
    """T-25-02 route-level proof: the REAL `_run_explain_stream()` engine
    (not a patched-out fake) is reached, and its `dangerous_pattern_check`
    wiring refuses a denylisted candidate BEFORE `set_cached()` ever runs --
    the load-bearing backstop is that `set_cached` is never invoked."""
    finding_id = await _seed_finding(db_session, tenant_a)
    await _seed_anthropic_connector(db_session, tenant_a)

    danger_block = SimpleNamespace(
        type="text", text=json.dumps(_valid_payload(summary="Run rm -rf /opt/old-app to clean up."))
    )
    usage = SimpleNamespace(input_tokens=50, output_tokens=40)
    fake_message = SimpleNamespace(content=[danger_block], usage=usage)

    class _FakeStreamCM:
        async def __aenter__(self) -> _FakeStreamCM:
            return self

        async def __aexit__(self, *exc_info: object) -> bool:
            return False

        async def get_final_message(self) -> Any:
            return fake_message

    class _FakeMessages:
        def stream(self, **kwargs: Any) -> _FakeStreamCM:
            return _FakeStreamCM()

    class _FakeAsyncAnthropic:
        def __init__(self, api_key: str) -> None:
            self.messages = _FakeMessages()

    client = client_factory(analyst_user)

    with (
        patch("app.ai.explain._default_client_factory", _FakeAsyncAnthropic),
        patch("app.ai.explain.set_cached", new_callable=AsyncMock) as mock_set_cached,
    ):
        resp = await client.post(f"/api/v1/ai/explain-remediation-guidance/{finding_id}")

    assert resp.status_code == 200, resp.text
    assert '"kind": "unsafe"' in resp.text
    mock_set_cached.assert_not_called()

    rows = await _audit_rows_for_action(db_session, tenant_a, "ai.explain.remediation-guidance")
    assert len(rows) == 1
    assert rows[0].details["status"] == "unsafe_denylisted"


# ── GET: cache-check, groundable-on-miss, no dispatch ───────────────────


async def test_get_cache_check_miss_groundable_true_no_dispatch(client_factory, db_session, tenant_a, viewer_user):
    finding_id = await _seed_finding(db_session, tenant_a)
    client = client_factory(viewer_user)

    with patch("app.ai.explain.AsyncAnthropic") as mock_anthropic_cls:
        resp = await client.get(f"/api/v1/ai/explain-remediation-guidance/{finding_id}")

    assert resp.status_code == 200
    assert resp.json() == {"cached": False, "groundable": True}
    mock_anthropic_cls.assert_not_called()


async def test_get_cache_check_miss_groundable_false_when_no_actionable_text(
    client_factory, db_session, tenant_a, viewer_user
):
    """25-RESEARCH.md Pattern 4 / UI-SPEC state 3: the frontend must be able
    to render the insufficient-evidence card BEFORE any click."""
    finding_id = await _seed_finding(db_session, tenant_a, remediation_action=None, remediation_info="N/A")
    client = client_factory(viewer_user)

    resp = await client.get(f"/api/v1/ai/explain-remediation-guidance/{finding_id}")

    assert resp.status_code == 200
    assert resp.json() == {"cached": False, "groundable": False}


async def test_get_cache_check_returns_payload_on_hit(client_factory, db_session, flushed_redis, tenant_a, viewer_user):
    from app.ai.cache import build_cache_key, record_hash, set_cached
    from app.ai.explain import DEFAULT_MODEL
    from app.ai.prompt_builder import build_explain_remediation_guidance_prompt, remediation_guidance_prompt_version

    finding_id = await _seed_finding(db_session, tenant_a)

    record = await get_remediation_guidance_context(db_session, tenant_a, finding_id)
    _system_prompt, user_blocks = build_explain_remediation_guidance_prompt(record)
    text = user_blocks[0]["text"]
    allowlisted_fields = json.loads(text[text.index(">") + 1 : text.rindex("</scanner_data>")])
    the_hash = record_hash(allowlisted_fields)
    cache_key = build_cache_key(
        tenant_a, "remediation-guidance", str(finding_id), the_hash, DEFAULT_MODEL, remediation_guidance_prompt_version()
    )
    seeded_payload = _valid_payload()
    await set_cached(flushed_redis, cache_key, seeded_payload)

    client = client_factory(viewer_user)
    resp = await client.get(f"/api/v1/ai/explain-remediation-guidance/{finding_id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["cached"] is True
    assert body["summary"] == seeded_payload["summary"]
    assert "groundable" not in body


async def test_get_missing_finding_id_returns_404(client_factory, db_session, tenant_a, viewer_user):
    client = client_factory(viewer_user)
    resp = await client.get(f"/api/v1/ai/explain-remediation-guidance/{uuid.uuid4()}")
    assert resp.status_code == 404


# ── Cross-tenant 404 (POST + GET) ────────────────────────────────────────


async def test_cross_tenant_finding_id_not_resolvable(
    client_factory, db_session, tenant_a, tenant_b, analyst_user, analyst_user_b
):
    """A foreign-tenant finding_id is not resolvable -- 404, never
    cross-tenant data. Contrasted against tenant_a's OWN analyst resolving
    the SAME finding_id successfully, so this can only pass when the route
    genuinely exists and enforces tenant scoping."""
    finding_id = await _seed_finding(db_session, tenant_a)  # belongs to tenant_a

    client_a = client_factory(analyst_user)
    with patch("app.api.v1.ai.explain_remediation_guidance._run_explain_stream", _fake_explain_stream):
        same_tenant_post = await client_a.post(f"/api/v1/ai/explain-remediation-guidance/{finding_id}")
    assert same_tenant_post.status_code == 200, same_tenant_post.text
    same_tenant_get = await client_a.get(f"/api/v1/ai/explain-remediation-guidance/{finding_id}")
    assert same_tenant_get.status_code == 200, same_tenant_get.text

    client_b = client_factory(analyst_user_b)
    cross_tenant_post = await client_b.post(f"/api/v1/ai/explain-remediation-guidance/{finding_id}")
    assert cross_tenant_post.status_code == 404

    cross_tenant_get = await client_b.get(f"/api/v1/ai/explain-remediation-guidance/{finding_id}")
    assert cross_tenant_get.status_code == 404


# ── Asset-aware grounding: OS/package fields ride along, owner-PII excluded ──


async def test_grounding_record_includes_asset_os_fields_excludes_owner_pii(db_session, tenant_a):
    asset_id = await _seed_asset(db_session, tenant_a, os_name="Windows Server", os_version="2022")
    finding_id = await _seed_finding(db_session, tenant_a, asset_id=asset_id)

    record = await get_remediation_guidance_context(db_session, tenant_a, finding_id)

    assert record is not None
    assert record["os_name"] == "Windows Server"
    assert record["os_version"] == "2022"
    assert "assigned_user" not in record
    assert "directory_user" not in record
