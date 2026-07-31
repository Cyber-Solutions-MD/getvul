"""Tests for the `explain-prioritization` SSE endpoint (Phase 26 Plan 03):
app.api.v1.ai.explain_prioritization.

`_run_explain_stream`'s OWN internal engine behavior (retry/audit/budget/
cache/etc) is already exhaustively covered by test_ai_explain_stream.py and
reused UNCHANGED here -- these tests exercise the ROUTE (RBAC, headers,
cache-check, tenant-scoping) via the identical patched-fake-engine seam
`test_ai_explain_host_remediation.py`/`test_ai_explain_remediation_guidance.py`
already established.

Unlike `test_ai_explain_remediation_guidance.py`, there is NO D-01
pre-generation-gate test and NO denylisted-candidate backstop test here --
this route passes no `dangerous_pattern_check` and has no deterministic
refuse predicate (26-PATTERNS.md "No Analog Found"; prioritization
narratives explain drivers, they recommend nothing to execute).

Backend env gotcha (MEMORY.md `getvul-backend-pytest-env`): run with a REAL
Fernet ENCRYPTION_KEY (`Fernet.generate_key()`, NOT a placeholder string) +
JWT_SECRET_KEY set, per-file (not the whole tests/ dir).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

from app.ai.grounding import get_prioritization_context

# ── Seed helpers ─────────────────────────────────────────────────────────


async def _seed_finding(
    db_session,
    tenant_id: uuid.UUID,
    **overrides: Any,
) -> uuid.UUID:
    from app.vulnerabilities.models import Vulnerability

    defaults: dict[str, Any] = {
        "tenant_id": tenant_id,
        "cve_id": "CVE-2024-1234",
        "vulnerability_name": "Sample Vuln",
        "severity": "CRITICAL",
        "cvss_v3_score": 9.1,
        "epss_score": 0.87,
        "exploit_available": True,
        "cisa_kev": True,
        "exploit_status_name": "Weaponized",
        "source": "NESSUS",
        "source_vuln_id": str(uuid.uuid4()),
        "status": "OPEN",
        "sla_due_at": datetime.now(UTC),
        "sla_breached": True,
        "first_detected_at": datetime.now(UTC),
        "last_seen_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    vuln = Vulnerability(**defaults)
    db_session.add(vuln)
    await db_session.commit()  # visible to the app's OWN, independently-connected session
    return vuln.id


async def _seed_batch_job(
    db_session,
    tenant_id: uuid.UUID,
    finding_id: uuid.UUID,
    **overrides: Any,
) -> uuid.UUID:
    """Seed an `AiBatchJob` (Plan 06) whose `custom_id_hash_map` contains
    `finding_id` -- the exact row `_is_finding_queued()` queries for."""
    from app.ai.models import AiBatchJob

    defaults: dict[str, Any] = {
        "tenant_id": tenant_id,
        "anthropic_batch_id": f"msgbatch_{uuid.uuid4().hex[:16]}",
        "status": "in_progress",
        "model": "claude-sonnet-5",
        "prompt_version": "abc123",
        "custom_id_hash_map": {str(finding_id): "hash1"},
        "submitted_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    job = AiBatchJob(**defaults)
    db_session.add(job)
    await db_session.commit()  # visible to the app's OWN, independently-connected session
    return job.id


def _valid_payload(summary: str = "Explained.") -> dict[str, Any]:
    return {
        "summary": summary,
        "business_risk": "Risk framing.",
        "citations": [{"text": summary, "source": "scanner_verbatim", "source_field": "cisa_kev"}],
        "grounded": True,
    }


async def _fake_explain_stream(*args: Any, **kwargs: Any):
    payload = {"type": "done", **_valid_payload()}
    yield f"data: {json.dumps(payload)}\n\n".encode()


# ── POST: RBAC + happy path ─────────────────────────────────────────────


async def test_post_as_analyst_returns_200_sse_with_headers(client_factory, db_session, tenant_a, analyst_user):
    finding_id = await _seed_finding(db_session, tenant_a)
    client = client_factory(analyst_user)

    with patch("app.api.v1.ai.explain_prioritization._run_explain_stream", _fake_explain_stream):
        resp = await client.post(f"/api/v1/ai/explain-prioritization/{finding_id}")

    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert "no-cache" in resp.headers["cache-control"]
    assert resp.headers["x-accel-buffering"] == "no"
    assert '"type": "done"' in resp.text


async def test_post_as_viewer_returns_403(client_factory, db_session, tenant_a, viewer_user):
    finding_id = await _seed_finding(db_session, tenant_a)
    client = client_factory(viewer_user)

    resp = await client.post(f"/api/v1/ai/explain-prioritization/{finding_id}")

    assert resp.status_code == 403


async def test_post_missing_finding_id_returns_404(client_factory, db_session, tenant_a, analyst_user):
    client = client_factory(analyst_user)
    resp = await client.post(f"/api/v1/ai/explain-prioritization/{uuid.uuid4()}")
    assert resp.status_code == 404


# ── GET: cache-check, no dispatch ────────────────────────────────────────


async def test_get_cache_check_miss_returns_cached_false_no_dispatch(client_factory, db_session, tenant_a, viewer_user):
    finding_id = await _seed_finding(db_session, tenant_a)
    client = client_factory(viewer_user)

    with patch("app.ai.explain.AsyncAnthropic") as mock_anthropic_cls:
        resp = await client.get(f"/api/v1/ai/explain-prioritization/{finding_id}")

    assert resp.status_code == 200
    assert resp.json() == {"cached": False, "queued": False}
    mock_anthropic_cls.assert_not_called()


async def test_get_cache_check_returns_payload_on_hit(client_factory, db_session, flushed_redis, tenant_a, viewer_user):
    from app.ai.cache import build_cache_key, record_hash, set_cached
    from app.ai.explain import DEFAULT_MODEL
    from app.ai.prompt_builder import build_explain_prioritization_prompt, prioritization_prompt_version

    finding_id = await _seed_finding(db_session, tenant_a)

    record = await get_prioritization_context(db_session, tenant_a, finding_id)
    _system_prompt, user_blocks = build_explain_prioritization_prompt(record)
    text = user_blocks[0]["text"]
    allowlisted_fields = json.loads(text[text.index(">") + 1 : text.rindex("</scanner_data>")])
    the_hash = record_hash(allowlisted_fields)
    cache_key = build_cache_key(
        tenant_a, "prioritization", str(finding_id), the_hash, DEFAULT_MODEL, prioritization_prompt_version()
    )
    seeded_payload = _valid_payload()
    await set_cached(flushed_redis, cache_key, seeded_payload)

    client = client_factory(viewer_user)
    resp = await client.get(f"/api/v1/ai/explain-prioritization/{finding_id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["cached"] is True
    assert body["summary"] == seeded_payload["summary"]


async def test_get_missing_finding_id_returns_404(client_factory, db_session, tenant_a, viewer_user):
    client = client_factory(viewer_user)
    resp = await client.get(f"/api/v1/ai/explain-prioritization/{uuid.uuid4()}")
    assert resp.status_code == 404


# ── GET: queued signal (D-02, Plan 06's AiBatchJob) ──────────────────────


async def test_get_miss_queued_true_when_in_progress_batch_contains_finding(
    client_factory, db_session, tenant_a, viewer_user
):
    """A GET miss with an in_progress AiBatchJob whose custom_id_hash_map
    contains this finding_id, for THIS tenant, returns queued: true."""
    finding_id = await _seed_finding(db_session, tenant_a)
    await _seed_batch_job(db_session, tenant_a, finding_id)

    client = client_factory(viewer_user)
    resp = await client.get(f"/api/v1/ai/explain-prioritization/{finding_id}")

    assert resp.status_code == 200
    assert resp.json() == {"cached": False, "queued": True}


async def test_get_miss_queued_false_when_no_batch(client_factory, db_session, tenant_a, viewer_user):
    """No AiBatchJob row at all -- queued: false (the ordinary miss)."""
    finding_id = await _seed_finding(db_session, tenant_a)
    client = client_factory(viewer_user)

    resp = await client.get(f"/api/v1/ai/explain-prioritization/{finding_id}")

    assert resp.status_code == 200
    assert resp.json() == {"cached": False, "queued": False}


async def test_get_miss_queued_false_when_batch_completed(client_factory, db_session, tenant_a, viewer_user):
    """A `completed` AiBatchJob row (not in_progress) never surfaces as
    queued: true -- only an in_progress batch counts."""
    finding_id = await _seed_finding(db_session, tenant_a)
    await _seed_batch_job(db_session, tenant_a, finding_id, status="completed")

    client = client_factory(viewer_user)
    resp = await client.get(f"/api/v1/ai/explain-prioritization/{finding_id}")

    assert resp.status_code == 200
    assert resp.json() == {"cached": False, "queued": False}


async def test_get_miss_queued_cross_tenant_isolation(client_factory, db_session, tenant_a, tenant_b, viewer_user):
    """tenant_b's in_progress batch containing the SAME finding_id (as a
    custom_id_hash_map key) must NEVER make tenant_a's GET show queued:
    true (T-26-03)."""
    finding_id = await _seed_finding(db_session, tenant_a)
    await _seed_batch_job(db_session, tenant_b, finding_id)  # different tenant, same finding_id key

    client = client_factory(viewer_user)
    resp = await client.get(f"/api/v1/ai/explain-prioritization/{finding_id}")

    assert resp.status_code == 200
    assert resp.json() == {"cached": False, "queued": False}


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
    with patch("app.api.v1.ai.explain_prioritization._run_explain_stream", _fake_explain_stream):
        same_tenant_post = await client_a.post(f"/api/v1/ai/explain-prioritization/{finding_id}")
    assert same_tenant_post.status_code == 200, same_tenant_post.text
    same_tenant_get = await client_a.get(f"/api/v1/ai/explain-prioritization/{finding_id}")
    assert same_tenant_get.status_code == 200, same_tenant_get.text

    client_b = client_factory(analyst_user_b)
    cross_tenant_post = await client_b.post(f"/api/v1/ai/explain-prioritization/{finding_id}")
    assert cross_tenant_post.status_code == 404

    cross_tenant_get = await client_b.get(f"/api/v1/ai/explain-prioritization/{finding_id}")
    assert cross_tenant_get.status_code == 404
