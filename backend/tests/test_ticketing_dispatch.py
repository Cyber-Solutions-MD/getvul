"""Phase 23 Plan 04 — provider-dispatch coverage (D-07/D-09/D-10/D-15).

Proves the live data-integrity bug is fixed: `provider:"JIRA"` now actually
reaches the Jira client (not Asana), across all three create paths, the
scheduled rule-engine path, sync/close, and the new tenant-scoped
configured-providers endpoint.

Uses a `FakeTicketingClient` (records calls, returns a provider-shaped fake
URL) rather than a live provider or an httpx.MockTransport — the thing under
test here is DISPATCH (does the right provider's client get called with the
right ref), not any single provider's HTTP wire format (already covered by
test_ticketing_clients.py).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.assets.models import Asset
from app.encryption import encrypt_value
from app.ticketing.models import ConnectorConfig, Ticket, TicketRule
from app.ticketing.providers import TicketProvider
from app.ticketing.schemas import HostTicketCreateRequest, TicketCreateRequest
from app.ticketing.service import close_ticket, create_host_ticket, create_remediation_ticket, create_tickets
from app.vulnerabilities.models import Vulnerability

_FAKE_URL_BASE = {
    "ASANA": "https://app.asana.com/0/999",
    "JIRA": "https://acme.atlassian.net/browse",
    "GITHUB": "https://github.com/o/r/issues",
}


class FakeTicketingClient:
    """Records every dispatch verb call; returns a provider-shaped fake URL
    from create() so _extract_ref's "last path segment" parsing is exercised
    exactly as it would be against a real adapter."""

    def __init__(self, provider: str, get_payload: dict | None = None) -> None:
        self.provider = provider
        self.created: list[tuple[str, str, dict]] = []
        self.gotten: list[str] = []
        self.commented: list[tuple[str, str]] = []
        self.closed: list[str] = []
        self._get_payload = get_payload if get_payload is not None else {"completed": True}
        self._seq = 0

    async def create(self, title, body, **kwargs):
        self._seq += 1
        self.created.append((title, body, kwargs))
        return f"{_FAKE_URL_BASE[self.provider]}/ref-{self._seq}"

    async def get(self, ref):
        self.gotten.append(ref)
        return self._get_payload

    async def comment(self, ref, body):
        self.commented.append((ref, body))

    async def close(self, ref):
        self.closed.append(ref)


def _seed_vuln(tenant_id, *, asset_id=None, remediation_id=None) -> Vulnerability:
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        asset_id=asset_id,
        cve_id=f"CVE-DISP-{uuid.uuid4().hex[:6]}",
        severity="CRITICAL",
        status="OPEN",
        source="MOCK",
        source_vuln_id=str(uuid.uuid4()),
        first_detected_at=now,
        last_seen_at=now,
        remediation_id=remediation_id,
        remediation_action="Upgrade to fixed version",
        affected_product="widget",
    )


def _seed_asset(tenant_id) -> Asset:
    return Asset(tenant_id=tenant_id, hostname=f"host-{uuid.uuid4().hex[:6]}", os_name="Ubuntu 22.04")


def _seed_connector(tenant_id, provider: str, *, enabled: bool = True) -> ConnectorConfig:
    """Seed a ConnectorConfig with plausible encrypted creds for `provider`
    (mirrors app/connectors/service.py's own encrypt_value usage)."""
    creds = {
        "ASANA": {"access_token": "fake-asana-token"},
        "JIRA": {"email": "e@x.com", "api_token": "tok", "url": "https://acme.atlassian.net"},
        "GITHUB": {"token": "fake-gh-token"},
    }[provider]
    config = {
        "ASANA": {"workspace_gid": "w1", "project_gid": "p1"},
        "JIRA": {"project_key": "PROJ"},
        "GITHUB": {"owner": "o", "repo": "r"},
    }[provider]
    return ConnectorConfig(
        tenant_id=tenant_id,
        connector_type=provider,
        is_enabled=enabled,
        credentials_secret_arn=__import__("json").dumps({k: encrypt_value(v) for k, v in creds.items()}),
        config=config,
    )


# ── Task 1: TicketCreateRequest.description field (AIR-02, T-25-06) ─────────


def test_ticket_create_request_description_whitespace_only_coerces_to_none():
    """A whitespace-only description never raises — the field is optional
    (D-08) — it simply normalizes to None."""
    request = TicketCreateRequest(
        vulnerability_ids=[uuid.uuid4()], provider="ASANA", description="   \n\t  "
    )
    assert request.description is None


def test_ticket_create_request_description_over_max_length_raises():
    with pytest.raises(ValidationError):
        TicketCreateRequest(
            vulnerability_ids=[uuid.uuid4()], provider="ASANA", description="x" * 10001
        )


def test_ticket_create_request_description_omitted_is_valid():
    request = TicketCreateRequest(vulnerability_ids=[uuid.uuid4()], provider="ASANA")
    assert request.description is None


def test_ticket_create_request_description_valid_text_is_kept_verbatim_after_strip():
    request = TicketCreateRequest(
        vulnerability_ids=[uuid.uuid4()], provider="ASANA", description="  Do the fix  "
    )
    assert request.description == "Do the fix"


def test_ticket_create_request_description_unknown_field_rejected():
    """extra='forbid' mass-assignment defense (T-25-06, ASVS V5)."""
    with pytest.raises(ValidationError):
        TicketCreateRequest(
            vulnerability_ids=[uuid.uuid4()], provider="ASANA", not_a_real_field="x"
        )


# ── Task 1: service.py create-path dispatch (D-07) ───────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["ASANA", "JIRA", "GITHUB"])
async def test_create_tickets_dispatches_to_the_requested_provider(db_session, tenant_a, provider):
    """T-23-11: for provider:X, the X client (not Asana) creates the ticket,
    and the persisted Ticket.provider matches the client actually invoked."""
    vuln = _seed_vuln(tenant_a)
    db_session.add(vuln)
    await db_session.commit()

    fake = FakeTicketingClient(provider)
    request = TicketCreateRequest(vulnerability_ids=[vuln.id], provider=provider, project_key="PROJ")

    summaries = await create_tickets(db=db_session, tenant_id=tenant_a, user_id=None, request=request, client=fake)
    await db_session.commit()

    assert len(summaries) == 1
    assert len(fake.created) == 1, f"{provider} client's create() was not called"

    row = (await db_session.execute(select(Ticket).where(Ticket.vulnerability_id == vuln.id))).scalar_one()
    assert row.provider == provider
    assert row.external_ticket_url == f"{_FAKE_URL_BASE[provider]}/ref-1"
    assert row.external_ticket_id == "ref-1"


@pytest.mark.asyncio
async def test_create_tickets_jira_does_not_receive_asana_only_kwargs(db_session, tenant_a):
    """Regression: JiraAdapter.create forwards **kwargs straight to
    JiraClient.create_ticket, which does NOT accept assignee/due_on — passing
    them would raise TypeError. Only Asana gets those kwargs."""
    vuln = _seed_vuln(tenant_a)
    db_session.add(vuln)
    await db_session.commit()

    fake = FakeTicketingClient("JIRA")
    request = TicketCreateRequest(
        vulnerability_ids=[vuln.id], provider="JIRA", project_key="PROJ", assignee="a@x.com", due_days=5
    )
    await create_tickets(db=db_session, tenant_id=tenant_a, user_id=None, request=request, client=fake)

    assert fake.created[0][2] == {}, "Jira create() must not receive assignee/due_on kwargs"


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["ASANA", "JIRA", "GITHUB"])
async def test_create_host_ticket_dispatches_to_the_requested_provider(db_session, tenant_a, provider):
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()
    vuln = _seed_vuln(tenant_a, asset_id=asset.id)
    db_session.add(vuln)
    await db_session.commit()

    fake = FakeTicketingClient(provider)
    request = HostTicketCreateRequest(asset_id=asset.id, provider=provider, project_key="PROJ")

    result = await create_host_ticket(db=db_session, tenant_id=tenant_a, user_id=None, request=request, client=fake)
    await db_session.commit()

    assert "error" not in result, result
    assert len(fake.created) == 1
    row = (await db_session.execute(select(Ticket).where(Ticket.vulnerability_id == vuln.id))).scalar_one()
    assert row.provider == provider


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["ASANA", "JIRA", "GITHUB"])
async def test_create_remediation_ticket_dispatches_to_the_requested_provider(db_session, tenant_a, provider):
    remediation_id = f"rem-{uuid.uuid4().hex[:6]}"
    vuln = _seed_vuln(tenant_a, remediation_id=remediation_id)
    db_session.add(vuln)
    await db_session.commit()

    fake = FakeTicketingClient(provider)
    result = await create_remediation_ticket(
        db=db_session,
        tenant_id=tenant_a,
        user_id=None,
        remediation_id=remediation_id,
        provider=provider,
        project_key="PROJ",
        client=fake,
    )
    await db_session.commit()

    assert "error" not in result, result
    assert len(fake.created) == 1
    row = (await db_session.execute(select(Ticket).where(Ticket.vulnerability_id == vuln.id))).scalar_one()
    assert row.provider == provider


# ── Task 1: sync_ticket_status / close_ticket dispatch by ticket's own provider ──


@pytest.mark.asyncio
async def test_sync_ticket_status_dispatches_each_ticket_to_its_own_provider(db_session, tenant_a):
    """Previously hardcoded Ticket.provider == 'ASANA' — a JIRA ticket now
    gets synced via the Jira client, not skipped/ignored."""
    vuln_asana = _seed_vuln(tenant_a)
    vuln_jira = _seed_vuln(tenant_a)
    db_session.add_all([vuln_asana, vuln_jira])
    await db_session.flush()

    now = datetime.now(UTC)
    t_asana = Ticket(
        tenant_id=tenant_a,
        vulnerability_id=vuln_asana.id,
        provider="ASANA",
        external_ticket_id="a1",
        external_ticket_url="https://app.asana.com/0/999/a1",
        external_status="open",
        ticket_created_at=now,
    )
    t_jira = Ticket(
        tenant_id=tenant_a,
        vulnerability_id=vuln_jira.id,
        provider="JIRA",
        external_ticket_id="GV-1",
        external_ticket_url="https://acme.atlassian.net/browse/GV-1",
        external_status="open",
        ticket_created_at=now,
    )
    db_session.add_all([t_asana, t_jira])
    await db_session.commit()

    fakes: dict[str, FakeTicketingClient] = {
        "ASANA": FakeTicketingClient("ASANA", get_payload={"completed": True}),
        "JIRA": FakeTicketingClient(
            "JIRA",
            get_payload={"fields": {"status": {"statusCategory": {"key": "done"}, "name": "Done"}}},
        ),
    }

    async def resolver(provider: str):
        return fakes.get(provider)

    from app.ticketing.service import sync_ticket_status

    result = await sync_ticket_status(db_session, tenant_a, resolver)
    await db_session.commit()

    assert result["synced"] == 2
    assert fakes["ASANA"].gotten == ["a1"]
    assert fakes["JIRA"].gotten == ["GV-1"]

    await db_session.refresh(t_asana)
    await db_session.refresh(t_jira)
    assert t_asana.external_status == "completed"
    assert t_jira.external_status == "completed"


@pytest.mark.asyncio
async def test_sync_ticket_status_skips_provider_with_no_configured_connector(db_session, tenant_a):
    """A ticket whose provider has no enabled connector is skipped (logged),
    not a hard failure for the whole sync."""
    vuln = _seed_vuln(tenant_a)
    db_session.add(vuln)
    await db_session.flush()

    ticket = Ticket(
        tenant_id=tenant_a,
        vulnerability_id=vuln.id,
        provider="GITHUB",
        external_ticket_id="7",
        external_ticket_url="https://github.com/o/r/issues/7",
        external_status="open",
        ticket_created_at=datetime.now(UTC),
    )
    db_session.add(ticket)
    await db_session.commit()

    async def resolver(provider: str):
        return None

    from app.ticketing.service import sync_ticket_status

    result = await sync_ticket_status(db_session, tenant_a, resolver)
    assert result["synced"] == 0


@pytest.mark.asyncio
async def test_close_ticket_dispatches_by_the_tickets_own_provider(db_session, tenant_a):
    vuln = _seed_vuln(tenant_a)
    db_session.add(vuln)
    await db_session.flush()

    ticket = Ticket(
        tenant_id=tenant_a,
        vulnerability_id=vuln.id,
        provider="JIRA",
        external_ticket_id="GV-42",
        external_ticket_url="https://acme.atlassian.net/browse/GV-42",
        external_status="open",
        ticket_created_at=datetime.now(UTC),
    )
    db_session.add(ticket)
    await db_session.commit()

    fake = FakeTicketingClient("JIRA")

    async def resolver(provider: str):
        assert provider == "JIRA"
        return fake

    result = await close_ticket(db_session, tenant_a, ticket.external_ticket_url, resolver)
    await db_session.commit()

    assert result["closed"] is True
    assert fake.closed == ["GV-42"]


# ── Task 2: rule-engine dispatch (D-09) ──────────────────────────────────────


@pytest.mark.asyncio
async def test_run_all_due_rules_dispatches_jira_rule_to_jira_client(db_session, tenant_a, monkeypatch):
    """A JIRA-provider rule for a tenant with a Jira connector configured
    reaches the Jira client on the scheduled path — not Asana, not a no-op."""
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()
    vuln = _seed_vuln(tenant_a, asset_id=asset.id)
    db_session.add(vuln)

    connector = _seed_connector(tenant_a, "JIRA")
    db_session.add(connector)

    rule = TicketRule(
        tenant_id=tenant_a,
        name="jira-rule",
        is_enabled=True,
        conditions={},
        action={"provider": "JIRA", "project_key": "PROJ", "auto_assign": False, "max_tickets": 10},
        schedule_minutes=1440,
    )
    db_session.add(rule)
    await db_session.commit()

    fake = FakeTicketingClient("JIRA")
    calls: list[tuple] = []

    def fake_build(provider, creds, config):
        calls.append((provider, creds, config))
        return fake

    monkeypatch.setattr("app.ticketing.rule_engine.build_ticketing_client", fake_build)

    from app.ticketing.rule_engine import run_all_due_rules

    result = await run_all_due_rules(db_session)

    assert result["rules_run"] == 1
    assert len(calls) == 1
    assert calls[0][0] == TicketProvider.JIRA
    assert len(fake.created) == 1, "the Jira client's create() was never invoked"

    row = (await db_session.execute(select(Ticket).where(Ticket.vulnerability_id == vuln.id))).scalar_one()
    assert row.provider == "JIRA"


@pytest.mark.asyncio
async def test_run_all_due_rules_defaults_to_asana_when_rule_has_no_provider(db_session, tenant_a, monkeypatch):
    """Back-compat regression: a rule with no action.provider still resolves
    to ASANA, unchanged."""
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()
    vuln = _seed_vuln(tenant_a, asset_id=asset.id)
    db_session.add(vuln)

    connector = _seed_connector(tenant_a, "ASANA")
    db_session.add(connector)

    rule = TicketRule(
        tenant_id=tenant_a,
        name="default-rule",
        is_enabled=True,
        conditions={},
        action={"auto_assign": False, "max_tickets": 10},  # no "provider" key
        schedule_minutes=1440,
    )
    db_session.add(rule)
    await db_session.commit()

    fake = FakeTicketingClient("ASANA")
    calls: list[tuple] = []

    def fake_build(provider, creds, config):
        calls.append(provider)
        return fake

    monkeypatch.setattr("app.ticketing.rule_engine.build_ticketing_client", fake_build)

    from app.ticketing.rule_engine import run_all_due_rules

    result = await run_all_due_rules(db_session)

    assert result["rules_run"] == 1
    assert calls == [TicketProvider.ASANA]


@pytest.mark.asyncio
async def test_run_all_due_rules_skips_rule_whose_provider_has_no_connector(db_session, tenant_a, monkeypatch):
    """A rule referencing a provider with no configured connector is skipped
    (logged), not silently redirected to a different provider."""
    rule = TicketRule(
        tenant_id=tenant_a,
        name="unconfigured-provider-rule",
        is_enabled=True,
        conditions={},
        action={"provider": "GITHUB"},
        schedule_minutes=1440,
    )
    db_session.add(rule)
    await db_session.commit()

    called = False

    def fake_build(provider, creds, config):
        nonlocal called
        called = True
        return FakeTicketingClient("GITHUB")

    monkeypatch.setattr("app.ticketing.rule_engine.build_ticketing_client", fake_build)

    from app.ticketing.rule_engine import run_all_due_rules

    result = await run_all_due_rules(db_session)

    assert result["rules_run"] == 0
    assert called is False


# ── Task 3: router dispatch + configured-providers endpoint (D-10/D-15) ─────


@pytest.mark.asyncio
async def test_post_tickets_provider_jira_reaches_jira_client_and_persists_jira(
    db_session, tenant_a, client, monkeypatch
):
    """The live data-integrity bug, reproduced at the HTTP layer: POST
    /api/v1/tickets with provider:'JIRA' must create via the Jira client and
    persist Ticket.provider == 'JIRA' — not silently create in Asana."""
    vuln = _seed_vuln(tenant_a)
    db_session.add(vuln)
    connector = _seed_connector(tenant_a, "JIRA")
    db_session.add(connector)
    await db_session.commit()

    fake = FakeTicketingClient("JIRA")
    monkeypatch.setattr("app.ticketing.router.build_ticketing_client", lambda p, c, cfg: fake)

    resp = await client.post(
        "/api/v1/tickets",
        json={"vulnerability_ids": [str(vuln.id)], "provider": "JIRA", "project_key": "PROJ"},
    )
    assert resp.status_code == 200, resp.text
    assert len(fake.created) == 1, "JIRA request never reached the Jira client"

    row = (await db_session.execute(select(Ticket).where(Ticket.vulnerability_id == vuln.id))).scalar_one()
    assert row.provider == "JIRA"


@pytest.mark.asyncio
async def test_post_tickets_provider_github_reaches_github_client(db_session, tenant_a, client, monkeypatch):
    vuln = _seed_vuln(tenant_a)
    db_session.add(vuln)
    connector = _seed_connector(tenant_a, "GITHUB")
    db_session.add(connector)
    await db_session.commit()

    fake = FakeTicketingClient("GITHUB")
    monkeypatch.setattr("app.ticketing.router.build_ticketing_client", lambda p, c, cfg: fake)

    resp = await client.post(
        "/api/v1/tickets",
        json={"vulnerability_ids": [str(vuln.id)], "provider": "GITHUB"},
    )
    assert resp.status_code == 200, resp.text
    assert len(fake.created) == 1
    row = (await db_session.execute(select(Ticket).where(Ticket.vulnerability_id == vuln.id))).scalar_one()
    assert row.provider == "GITHUB"


@pytest.mark.asyncio
async def test_post_tickets_provider_asana_still_works(db_session, tenant_a, client, monkeypatch):
    """Regression: ASANA behavior stays intact through the generalized dispatch."""
    vuln = _seed_vuln(tenant_a)
    db_session.add(vuln)
    connector = _seed_connector(tenant_a, "ASANA")
    db_session.add(connector)
    await db_session.commit()

    fake = FakeTicketingClient("ASANA")
    monkeypatch.setattr("app.ticketing.router.build_ticketing_client", lambda p, c, cfg: fake)

    resp = await client.post(
        "/api/v1/tickets",
        json={"vulnerability_ids": [str(vuln.id)], "provider": "ASANA", "project_key": "1199999999"},
    )
    assert resp.status_code == 200, resp.text
    assert len(fake.created) == 1
    row = (await db_session.execute(select(Ticket).where(Ticket.vulnerability_id == vuln.id))).scalar_one()
    assert row.provider == "ASANA"


@pytest.mark.asyncio
async def test_get_ticketing_providers_scoped_by_tenant(
    db_session, tenant_a, tenant_b, client, client_factory, analyst_user_b
):
    """D-15 + T-23-10: the configured-providers endpoint returns only the
    CALLER's tenant's configured+enabled providers — a second tenant with a
    different provider configured sees a different set (tenant isolation
    proven, not just documented)."""
    db_session.add(_seed_connector(tenant_a, "ASANA"))
    db_session.add(_seed_connector(tenant_b, "JIRA"))
    await db_session.commit()

    resp_a = await client.get("/api/v1/tickets/providers")
    assert resp_a.status_code == 200, resp_a.text
    providers_a = {item["provider"] for item in resp_a.json()}
    assert providers_a == {"ASANA"}

    client_b = client_factory(analyst_user_b)
    resp_b = await client_b.get("/api/v1/tickets/providers")
    assert resp_b.status_code == 200, resp_b.text
    providers_b = {item["provider"] for item in resp_b.json()}
    assert providers_b == {"JIRA"}


@pytest.mark.asyncio
async def test_get_ticketing_providers_excludes_disabled_connector(db_session, tenant_a, client):
    db_session.add(_seed_connector(tenant_a, "ASANA", enabled=False))
    await db_session.commit()

    resp = await client.get("/api/v1/tickets/providers")
    assert resp.status_code == 200, resp.text
    assert resp.json() == []


@pytest.mark.asyncio
async def test_close_ticket_endpoint_dispatches_by_ticket_provider(db_session, tenant_a, client, monkeypatch):
    vuln = _seed_vuln(tenant_a)
    db_session.add(vuln)
    connector = _seed_connector(tenant_a, "JIRA")
    db_session.add(connector)
    await db_session.flush()

    ticket = Ticket(
        tenant_id=tenant_a,
        vulnerability_id=vuln.id,
        provider="JIRA",
        external_ticket_id="GV-9",
        external_ticket_url="https://acme.atlassian.net/browse/GV-9",
        external_status="open",
        ticket_created_at=datetime.now(UTC),
    )
    db_session.add(ticket)
    await db_session.commit()

    fake = FakeTicketingClient("JIRA")
    monkeypatch.setattr("app.ticketing.router.build_ticketing_client", lambda p, c, cfg: fake)

    resp = await client.post("/api/v1/tickets/close", json={"external_ticket_url": ticket.external_ticket_url})
    assert resp.status_code == 200, resp.text
    assert fake.closed == ["GV-9"]
