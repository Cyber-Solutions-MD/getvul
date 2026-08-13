"""Tests for escalation channel payload builders + SSRF guard + failure
handling (Phase 36 Plan 02, SLA-03 delivery plumbing).

This plan is delivery plumbing ONLY -- the transition-detection + once-only
firing logic that calls `dispatch_channel()` lands in Plan 03, so these
tests exercise the payload builders, the SSRF guard (_validate_webhook_url,
Pitfall 10), and the "a channel failure returns a dict, never raises"
contract (Pattern 1) directly, against a sample finding context.

Per 36-RESEARCH.md Environment Availability (lines 625-632) and
36-PATTERNS.md's "Test convention" note, there is no live Slack/Teams/
PagerDuty/SMTP credential in this environment -- every network-adjacent
test here monkeypatches `httpx.AsyncClient.post` directly (never a real
endpoint, never respx/pytest-httpx), mirroring
test_scheduler_enrichment_refresh.py's "monkeypatch the local function"
convention.

Backend env gotcha (MEMORY.md `getvul-backend-pytest-env`): run with a REAL
Fernet ENCRYPTION_KEY (`Fernet.generate_key()`) + JWT_SECRET_KEY set,
per-file, e.g.:
    cd backend && ENCRYPTION_KEY=$(.venv/bin/python -c \
        "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") \
        JWT_SECRET_KEY=test-secret .venv/bin/python -m pytest tests/test_escalation_channels.py -q
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.notifications import escalation_channels as ec


def _sample_context(**overrides: Any) -> dict[str, Any]:
    context: dict[str, Any] = {
        "vuln_id": "11111111-1111-1111-1111-111111111111",
        "cve_id": "CVE-2026-12345",
        "hostname": "host03",
        "tier": "critical",
        "tier_days": 7,
        "to_state": "breached",
    }
    context.update(overrides)
    return context


class _FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


# ---------------------------------------------------------------------------
# Payload shape -- Slack (RESEARCH.md:486-498)
# ---------------------------------------------------------------------------


def test_slack_payload_has_text_fallback_and_blocks() -> None:
    payload = ec._build_slack_payload(_sample_context())
    assert isinstance(payload.get("text"), str) and payload["text"]
    assert isinstance(payload.get("blocks"), list)
    assert len(payload["blocks"]) >= 1


def test_slack_payload_text_mentions_cve_and_host() -> None:
    payload = ec._build_slack_payload(_sample_context(cve_id="CVE-2026-99999", hostname="web-01"))
    assert "CVE-2026-99999" in payload["text"]
    assert "web-01" in payload["text"]


# ---------------------------------------------------------------------------
# Payload shape -- Teams (D-15 / Pitfall 7: Workflows webhook, NOT the
# retired classic connector)
# ---------------------------------------------------------------------------


def test_teams_payload_is_simple_text_form() -> None:
    payload = ec._build_teams_payload(_sample_context())
    assert payload.get("text")
    assert "@type" not in payload  # classic MessageCard connector signature


def test_teams_payload_never_uses_messagecard_classic_connector_shape() -> None:
    payload = ec._build_teams_payload(_sample_context(to_state="approaching", tier="moderate"))
    assert payload.get("@type") != "MessageCard"
    assert "themeColor" not in payload  # another classic-connector-only field


# ---------------------------------------------------------------------------
# Payload shape -- PagerDuty Events API v2 (RESEARCH.md:521-541)
# ---------------------------------------------------------------------------


def test_pagerduty_payload_shape() -> None:
    context = _sample_context(vuln_id="abc-123", to_state="breached")
    payload = ec._build_pagerduty_payload(context, "R0UT1NGKEY")
    assert payload["routing_key"] == "R0UT1NGKEY"
    assert payload["event_action"] == "trigger"
    assert payload["dedup_key"] == "getvul:abc-123:breached"
    assert payload["payload"]["severity"] in {"critical", "error", "warning", "info"}


def test_pagerduty_payload_dedup_key_scales_with_to_state() -> None:
    context = _sample_context(vuln_id="abc-123", to_state="approaching")
    payload = ec._build_pagerduty_payload(context, "R0UT1NGKEY")
    assert payload["dedup_key"] == "getvul:abc-123:approaching"


def test_pagerduty_payload_never_sends_resolve() -> None:
    """D-13: PagerDuty fires on approaching/breached transitions only --
    never event_action=resolve this phase (manual resolution required)."""
    for to_state in ("approaching", "breached"):
        payload = ec._build_pagerduty_payload(_sample_context(to_state=to_state), "R0UT1NGKEY")
        assert payload["event_action"] == "trigger"
        assert payload["event_action"] != "resolve"


# ---------------------------------------------------------------------------
# SSRF guard -- _validate_webhook_url (Pitfall 10)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://hooks.slack.com/services/T000/B000/XXXX",  # non-https
        "https://169.254.169.254/latest/meta-data/",  # AWS/Azure/GCP metadata IP
        "https://127.0.0.1/webhook",  # loopback
        "https://10.0.0.5/webhook",  # RFC1918 private
        "https://192.168.1.5/webhook",  # RFC1918 private
        "https://172.16.0.5/webhook",  # RFC1918 private
        "https://metadata.google.internal/computeMetadata/v1/",  # GCP metadata hostname
        "https://localhost/webhook",
        "",
        None,
    ],
)
def test_validate_webhook_url_rejects_unsafe_targets(url: str | None) -> None:
    assert ec._validate_webhook_url(url) is False


@pytest.mark.parametrize(
    "url",
    [
        "https://hooks.slack.com/services/T000/B000/XXXX",
        "https://contoso.webhook.office.com/webhookb2/abc",
        "https://events.pagerduty.com/v2/enqueue",
    ],
)
def test_validate_webhook_url_accepts_normal_https_hosts(url: str) -> None:
    assert ec._validate_webhook_url(url) is True


# ---------------------------------------------------------------------------
# Failure handling -- every sender returns a dict, never raises (Pattern 1)
# ---------------------------------------------------------------------------


async def test_send_slack_rejects_unsafe_url_without_any_network_call(monkeypatch: pytest.MonkeyPatch) -> None:
    called = False

    async def fake_post(self: httpx.AsyncClient, url: str, json: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        nonlocal called
        called = True
        raise AssertionError("must not POST to an unsafe URL")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    result = await ec.send_slack({"url": "http://evil.example.com/x", "enabled": True}, _sample_context())

    assert result["ok"] is False
    assert result["error"]
    assert called is False


async def test_send_slack_post_raises_returns_error_dict_not_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_post(self: httpx.AsyncClient, url: str, json: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    result = await ec.send_slack({"url": "https://hooks.slack.com/services/x", "enabled": True}, _sample_context())

    assert result["ok"] is False
    assert result["error"]


async def test_send_teams_post_404_returns_error_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_post(self: httpx.AsyncClient, url: str, json: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        return _FakeResponse(404)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    result = await ec.send_teams(
        {"url": "https://contoso.webhook.office.com/webhookb2/abc", "enabled": True}, _sample_context()
    )

    assert result["ok"] is False
    assert "404" in result["error"]


async def test_send_pagerduty_success_returns_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_post(self: httpx.AsyncClient, url: str, json: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        assert url == "https://events.pagerduty.com/v2/enqueue"
        return _FakeResponse(202)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    result = await ec.send_pagerduty({"routing_key": "R0UT1NG", "enabled": True}, _sample_context())

    assert result == {"ok": True}


async def test_send_pagerduty_missing_routing_key_returns_error_without_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    async def fake_post(self: httpx.AsyncClient, url: str, json: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        nonlocal called
        called = True
        return _FakeResponse(202)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    result = await ec.send_pagerduty({"routing_key": "", "enabled": True}, _sample_context())

    assert result["ok"] is False
    assert called is False


async def test_post_json_retries_on_429_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    async def fake_post(self: httpx.AsyncClient, url: str, json: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        calls["n"] += 1
        if calls["n"] < 2:
            return _FakeResponse(429)
        return _FakeResponse(200)

    async def fake_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    monkeypatch.setattr(ec.asyncio, "sleep", fake_sleep)

    result = await ec._post_json("https://hooks.slack.com/services/x", {"text": "hi"}, channel="slack")

    assert result == {"ok": True}
    assert calls["n"] == 2


# ---------------------------------------------------------------------------
# Email channel -- reuse app.email.send_email verbatim (D-04)
# ---------------------------------------------------------------------------


def test_send_email_channel_delegates_to_send_email(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_send_email(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(ec, "send_email", fake_send_email)

    result = ec.send_email_channel(
        {"to": ["analyst@example.com"], "smtp_config": {"host": "smtp.example.com"}},
        _sample_context(),
    )

    assert result == {"ok": True}
    assert captured["to"] == ["analyst@example.com"]
    assert captured["smtp_config"] == {"host": "smtp.example.com"}


def test_send_email_channel_no_recipients_returns_error_without_calling_send_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    def fake_send_email(**kwargs: Any) -> dict[str, Any]:
        nonlocal called
        called = True
        return {"ok": True}

    monkeypatch.setattr(ec, "send_email", fake_send_email)

    result = ec.send_email_channel({"to": [], "smtp_config": {}}, _sample_context())

    assert result["ok"] is False
    assert called is False


def test_send_email_channel_exception_returns_error_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    def bad_send_email(**kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("smtp exploded")

    monkeypatch.setattr(ec, "send_email", bad_send_email)

    result = ec.send_email_channel({"to": ["a@b.com"], "smtp_config": {"host": "smtp.example.com"}}, _sample_context())

    assert result["ok"] is False
    assert "smtp exploded" in result["error"]


# ---------------------------------------------------------------------------
# dispatch_channel router
# ---------------------------------------------------------------------------


async def test_dispatch_channel_routes_slack(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_post(self: httpx.AsyncClient, url: str, json: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        return _FakeResponse(200)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    result = await ec.dispatch_channel(
        "slack", {"url": "https://hooks.slack.com/services/x", "enabled": True}, _sample_context()
    )

    assert result == {"ok": True}


async def test_dispatch_channel_routes_email(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ec, "send_email", lambda **kwargs: {"ok": True})

    result = await ec.dispatch_channel(
        "email", {"to": ["a@b.com"], "smtp_config": {"host": "smtp.example.com"}}, _sample_context()
    )

    assert result == {"ok": True}


async def test_dispatch_channel_unknown_channel_returns_error_dict_not_exception() -> None:
    result = await ec.dispatch_channel("carrier_pigeon", {}, _sample_context())

    assert result["ok"] is False
    assert result["error"]


async def test_dispatch_channel_never_raises_on_sender_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    async def bad_sender(config: dict[str, Any] | None, context: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("unexpected")

    monkeypatch.setattr(ec, "send_slack", bad_sender)

    result = await ec.dispatch_channel("slack", {"url": "https://hooks.slack.com/x"}, _sample_context())

    assert result["ok"] is False
