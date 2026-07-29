"""Tests for the host + remediation SSE endpoints (D-15 Plan 08 Task 2):
app.api.v1.ai.explain_host / explain_remediation, and their grounding
assemblers app.ai.grounding.get_asset_posture / get_remediation_group.

`_run_explain_stream`'s OWN internal engine behavior (retry/audit/budget/
cache/etc) is already exhaustively covered by Plan 04's
test_ai_explain_stream.py and is reused UNCHANGED here (per this plan's own
must_haves) -- these tests exercise the ROUTE + grounding layer only,
mirroring test_ai_explain_stream.py's own Task-2 route-level test shape
(RBAC, headers, cache-check, tenant-scoping) via the identical patched-fake-
engine seam.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

from app.ai.grounding import get_asset_posture, get_remediation_group

# ── Seed helpers ─────────────────────────────────────────────────────────


async def _seed_asset(db_session, tenant_id: uuid.UUID, **overrides: Any) -> uuid.UUID:
    from app.assets.models import Asset

    defaults: dict[str, Any] = {
        "tenant_id": tenant_id,
        "hostname": f"host-{uuid.uuid4().hex[:8]}",
        "os_name": "Ubuntu",
        "os_version": "22.04",
        "device_category": "SERVER",
        "risk_score": 75,
        "tags": ["pci"],
        "last_checkin_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    asset = Asset(**defaults)
    db_session.add(asset)
    await db_session.commit()  # visible to the app's OWN, independently-connected session
    return asset.id


async def _seed_vulnerability_for_asset(
    db_session, tenant_id: uuid.UUID, asset_id: uuid.UUID, **overrides: Any
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
        "remediation_info": "Upgrade to fixed version.",
        "fixed_version": "1.0.2",
        "status": "OPEN",
        "first_detected_at": datetime.now(UTC),
        "last_seen_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    vuln = Vulnerability(**defaults)
    db_session.add(vuln)
    await db_session.commit()
    return vuln.id


def _valid_payload(summary: str = "Explained.") -> dict[str, Any]:
    return {
        "summary": summary,
        "business_risk": "Risk framing.",
        "citations": [{"text": summary, "source": "ai_interpreted", "source_field": None}],
        "grounded": True,
    }


async def _fake_explain_stream(*args: Any, **kwargs: Any):
    payload = {"type": "done", **_valid_payload()}
    yield f"data: {json.dumps(payload)}\n\n".encode()


async def _fake_ungrounded_stream(*args: Any, **kwargs: Any):
    yield b'data: {"type": "error", "kind": "grounded_false"}\n\n'


# ── Grounding assemblers: tenant-scoped, allowlisted shape ──────────────


async def test_get_asset_posture_returns_allowlisted_shape(db_session, tenant_a):
    asset_id = await _seed_asset(db_session, tenant_a)
    await _seed_vulnerability_for_asset(db_session, tenant_a, asset_id, severity="CRITICAL")

    record = await get_asset_posture(db_session, tenant_a, asset_id)

    assert record is not None
    assert record["vuln_counts"]["total"] == 1
    assert record["vuln_counts"]["critical"] == 1
    assert record["tags"] == ["pci"]
    assert record["hostname"] is not None


async def test_get_asset_posture_foreign_tenant_not_resolvable(db_session, tenant_a, tenant_b):
    asset_id = await _seed_asset(db_session, tenant_a)
    record = await get_asset_posture(db_session, tenant_b, asset_id)
    assert record is None


async def test_get_asset_posture_zero_findings_shape(db_session, tenant_a):
    """T-24-35: a sparse asset still resolves to a real (zero-count) record
    -- never None, never fabricated data -- the sparsity is signaled IN the
    grounding data, letting the downstream model/few-shot route to
    grounded=false rather than this layer inventing anything."""
    asset_id = await _seed_asset(db_session, tenant_a)
    record = await get_asset_posture(db_session, tenant_a, asset_id)
    assert record is not None
    assert record["vuln_counts"]["total"] == 0


# ── Grounding assembler: cross-asset CVE grouping (D-16 Option A) ──


async def test_get_remediation_group_aggregates_across_assets_by_cve(db_session, tenant_a):
    asset_1 = await _seed_asset(db_session, tenant_a, hostname=f"web-prod-{uuid.uuid4().hex[:6]}")
    asset_2 = await _seed_asset(db_session, tenant_a, hostname=f"web-prod-{uuid.uuid4().hex[:6]}")
    await _seed_vulnerability_for_asset(db_session, tenant_a, asset_1, cve_id="CVE-2023-4863", source="NESSUS")
    await _seed_vulnerability_for_asset(
        db_session,
        tenant_a,
        asset_2,
        cve_id="CVE-2023-4863",
        source="QUALYS",
        source_vuln_id=str(uuid.uuid4()),
    )

    record = await get_remediation_group(db_session, tenant_a, "CVE-2023-4863")

    assert record is not None
    assert record["cve"] == "CVE-2023-4863"
    assert len(record["affected_assets"]) == 2
    assert record["priority"] == "CRITICAL"  # KEV + exploit-available escalation


async def test_get_remediation_group_foreign_tenant_not_resolvable(db_session, tenant_a, tenant_b):
    asset_id = await _seed_asset(db_session, tenant_a)
    await _seed_vulnerability_for_asset(db_session, tenant_a, asset_id, cve_id="CVE-2099-0001")

    record = await get_remediation_group(db_session, tenant_b, "CVE-2099-0001")
    assert record is None


async def test_get_remediation_group_no_solution_text_fix_is_none(db_session, tenant_a):
    """T-24-35: no vendor solution text -> fix is None (not fabricated),
    routing the downstream model to grounded=false rather than inventing a
    remediation."""
    asset_id = await _seed_asset(db_session, tenant_a)
    await _seed_vulnerability_for_asset(
        db_session,
        tenant_a,
        asset_id,
        cve_id="CVE-2026-0001",
        remediation_info=None,
        fixed_version=None,
        severity="LOW",
        exploit_available=False,
        cisa_kev=False,
    )

    record = await get_remediation_group(db_session, tenant_a, "CVE-2026-0001")
    assert record is not None
    assert record["fix"] is None
    assert record["priority"] == "LOW"


# ── Route: explain-host ─────────────────────────────────────────────────


async def test_post_explain_host_as_analyst_returns_200_sse_with_headers(
    client_factory, db_session, tenant_a, analyst_user
):
    asset_id = await _seed_asset(db_session, tenant_a)

    client = client_factory(analyst_user)
    with patch("app.api.v1.ai.explain_host._run_explain_stream", _fake_explain_stream):
        resp = await client.post(f"/api/v1/ai/explain-host/{asset_id}")

    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert "no-cache" in resp.headers["cache-control"]
    assert resp.headers["x-accel-buffering"] == "no"
    assert '"type": "done"' in resp.text


async def test_post_explain_host_as_viewer_returns_403(client_factory, db_session, tenant_a, viewer_user):
    asset_id = await _seed_asset(db_session, tenant_a)
    client = client_factory(viewer_user)
    resp = await client.post(f"/api/v1/ai/explain-host/{asset_id}")
    assert resp.status_code == 403


async def test_get_explain_host_cache_check_as_viewer_miss_no_dispatch(
    client_factory, db_session, tenant_a, viewer_user
):
    asset_id = await _seed_asset(db_session, tenant_a)
    client = client_factory(viewer_user)

    with patch("app.ai.explain.AsyncAnthropic") as mock_anthropic_cls:
        resp = await client.get(f"/api/v1/ai/explain-host/{asset_id}")

    assert resp.status_code == 200
    assert resp.json() == {"cached": False}
    mock_anthropic_cls.assert_not_called()


async def test_get_explain_host_cache_check_returns_payload_on_hit(
    client_factory, db_session, flushed_redis, tenant_a, viewer_user
):
    from app.ai.cache import build_cache_key, record_hash, set_cached
    from app.ai.explain import DEFAULT_MODEL
    from app.ai.prompt_builder import build_explain_host_prompt, host_prompt_version

    asset_id = await _seed_asset(db_session, tenant_a)

    record = await get_asset_posture(db_session, tenant_a, asset_id)
    _system_prompt, user_blocks = build_explain_host_prompt(record)
    text = user_blocks[0]["text"]
    allowlisted_fields = json.loads(text[text.index(">") + 1 : text.rindex("</scanner_data>")])
    the_hash = record_hash(allowlisted_fields)
    cache_key = build_cache_key(tenant_a, "host", str(asset_id), the_hash, DEFAULT_MODEL, host_prompt_version())
    seeded_payload = _valid_payload()
    await set_cached(flushed_redis, cache_key, seeded_payload)

    client = client_factory(viewer_user)
    resp = await client.get(f"/api/v1/ai/explain-host/{asset_id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["cached"] is True
    assert body["summary"] == seeded_payload["summary"]


async def test_cross_tenant_asset_id_not_resolvable(
    client_factory, db_session, tenant_a, tenant_b, analyst_user, analyst_user_b
):
    """T-24-18-style: a foreign-tenant asset_id is not resolvable -- 404,
    never cross-tenant data. Contrasted against tenant_a's own analyst
    resolving the SAME asset_id successfully, so a vacuous 'route not
    found' 404 would fail both assertions, not just the cross-tenant one."""
    asset_id = await _seed_asset(db_session, tenant_a)

    client_a = client_factory(analyst_user)
    with patch("app.api.v1.ai.explain_host._run_explain_stream", _fake_explain_stream):
        same_tenant_post = await client_a.post(f"/api/v1/ai/explain-host/{asset_id}")
    assert same_tenant_post.status_code == 200, same_tenant_post.text
    same_tenant_get = await client_a.get(f"/api/v1/ai/explain-host/{asset_id}")
    assert same_tenant_get.status_code == 200, same_tenant_get.text

    client_b = client_factory(analyst_user_b)
    cross_tenant_post = await client_b.post(f"/api/v1/ai/explain-host/{asset_id}")
    assert cross_tenant_post.status_code == 404
    cross_tenant_get = await client_b.get(f"/api/v1/ai/explain-host/{asset_id}")
    assert cross_tenant_get.status_code == 404


async def test_asset_with_no_findings_grounded_false_path_no_fabrication(
    client_factory, db_session, tenant_a, analyst_user
):
    """T-24-35: a sparse (zero-vuln) asset still resolves (200, grounding
    succeeds with real zero counts) and the stream's own ungrounded path
    surfaces as the standard typed error -- never a fabricated 'done'."""
    asset_id = await _seed_asset(db_session, tenant_a)  # zero vulnerabilities

    client = client_factory(analyst_user)
    with patch("app.api.v1.ai.explain_host._run_explain_stream", _fake_ungrounded_stream):
        resp = await client.post(f"/api/v1/ai/explain-host/{asset_id}")

    assert resp.status_code == 200
    assert '"kind": "grounded_false"' in resp.text


# ── Route: explain-remediation ──────────────────────────────────────────


async def test_post_explain_remediation_as_analyst_returns_200_sse_with_headers(
    client_factory, db_session, tenant_a, analyst_user
):
    asset_id = await _seed_asset(db_session, tenant_a)
    await _seed_vulnerability_for_asset(db_session, tenant_a, asset_id, cve_id="CVE-2024-9999")

    client = client_factory(analyst_user)
    with patch("app.api.v1.ai.explain_remediation._run_explain_stream", _fake_explain_stream):
        resp = await client.post("/api/v1/ai/explain-remediation/CVE-2024-9999")

    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert "no-cache" in resp.headers["cache-control"]
    assert resp.headers["x-accel-buffering"] == "no"


async def test_post_explain_remediation_as_viewer_returns_403(client_factory, db_session, tenant_a, viewer_user):
    asset_id = await _seed_asset(db_session, tenant_a)
    await _seed_vulnerability_for_asset(db_session, tenant_a, asset_id, cve_id="CVE-2024-9999")
    client = client_factory(viewer_user)
    resp = await client.post("/api/v1/ai/explain-remediation/CVE-2024-9999")
    assert resp.status_code == 403


async def test_get_explain_remediation_cache_check_as_viewer_miss_no_dispatch(
    client_factory, db_session, tenant_a, viewer_user
):
    asset_id = await _seed_asset(db_session, tenant_a)
    await _seed_vulnerability_for_asset(db_session, tenant_a, asset_id, cve_id="CVE-2024-9999")
    client = client_factory(viewer_user)

    with patch("app.ai.explain.AsyncAnthropic") as mock_anthropic_cls:
        resp = await client.get("/api/v1/ai/explain-remediation/CVE-2024-9999")

    assert resp.status_code == 200
    assert resp.json() == {"cached": False}
    mock_anthropic_cls.assert_not_called()


async def test_cross_tenant_remediation_cve_not_resolvable(
    client_factory, db_session, tenant_a, tenant_b, analyst_user, analyst_user_b
):
    asset_id = await _seed_asset(db_session, tenant_a)
    await _seed_vulnerability_for_asset(db_session, tenant_a, asset_id, cve_id="CVE-2024-9999")

    client_a = client_factory(analyst_user)
    with patch("app.api.v1.ai.explain_remediation._run_explain_stream", _fake_explain_stream):
        same_tenant = await client_a.post("/api/v1/ai/explain-remediation/CVE-2024-9999")
    assert same_tenant.status_code == 200, same_tenant.text

    client_b = client_factory(analyst_user_b)
    cross_tenant = await client_b.post("/api/v1/ai/explain-remediation/CVE-2024-9999")
    assert cross_tenant.status_code == 404


# ── resource_type-namespacing: host/vuln/remediation cache keys never collide ──


def test_host_vuln_remediation_cache_keys_never_collide_for_same_underlying_id():
    """D-15/AI-05: even if a test forced the SAME literal id string across
    all three views, resource_type namespacing keeps the keys disjoint."""
    from app.ai.cache import build_cache_key

    same_tenant_id = uuid.uuid4()
    same_id = str(uuid.uuid4())
    host_key = build_cache_key(same_tenant_id, "host", same_id, "hash", "claude-sonnet-5", "v1")
    vuln_key = build_cache_key(same_tenant_id, "vuln", same_id, "hash", "claude-sonnet-5", "v1")
    remediation_key = build_cache_key(same_tenant_id, "remediation", same_id, "hash", "claude-sonnet-5", "v1")

    assert len({host_key, vuln_key, remediation_key}) == 3
