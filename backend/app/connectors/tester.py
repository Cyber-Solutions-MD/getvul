"""Test connector credentials by attempting authentication with each provider."""

from __future__ import annotations

import httpx

from app.connectors.schemas import ConnectorTestResult


async def test_crowdstrike(credentials: dict, config: dict) -> ConnectorTestResult:
    """Test CrowdStrike OAuth2 token endpoint."""
    base_url = config.get("base_url", credentials.get("base_url", "https://api.crowdstrike.com"))
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{base_url}/oauth2/token",
                data={
                    "client_id": credentials["client_id"],
                    "client_secret": credentials["client_secret"],
                },
            )
        if resp.status_code == 201:
            token_data = resp.json()
            return ConnectorTestResult(
                success=True,
                message="Successfully authenticated with CrowdStrike",
                details={"expires_in": token_data.get("expires_in")},
            )
        else:
            return ConnectorTestResult(
                success=False,
                message=f"Authentication failed: HTTP {resp.status_code}",
                details={"response": resp.text[:500]},
            )
    except Exception as e:
        return ConnectorTestResult(success=False, message=f"Connection error: {e}")


async def test_nessus(credentials: dict, config: dict) -> ConnectorTestResult:
    """Test Nessus API key by calling /server/status."""
    base_url = config.get("base_url", credentials.get("base_url", "https://localhost:8834"))
    try:
        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            resp = await client.get(
                f"{base_url}/server/status",
                headers={
                    "X-ApiKeys": f"accessKey={credentials['access_key']};secretKey={credentials['secret_key']}",
                },
            )
        if resp.status_code == 200:
            return ConnectorTestResult(
                success=True,
                message="Successfully connected to Nessus",
                details=resp.json(),
            )
        else:
            return ConnectorTestResult(
                success=False,
                message=f"Authentication failed: HTTP {resp.status_code}",
            )
    except Exception as e:
        return ConnectorTestResult(success=False, message=f"Connection error: {e}")


async def test_defender(credentials: dict, config: dict) -> ConnectorTestResult:
    """Test Microsoft Defender by getting an OAuth2 token."""
    tenant_id = credentials.get("tenant_id", "")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": credentials["client_id"],
                    "client_secret": credentials["client_secret"],
                    "scope": "https://api.securitycenter.microsoft.com/.default",
                },
            )
        if resp.status_code == 200:
            return ConnectorTestResult(
                success=True,
                message="Successfully authenticated with Microsoft Defender",
            )
        else:
            return ConnectorTestResult(
                success=False,
                message=f"Authentication failed: HTTP {resp.status_code}",
                details={"error": resp.json().get("error_description", resp.text[:500])},
            )
    except Exception as e:
        return ConnectorTestResult(success=False, message=f"Connection error: {e}")


async def test_wiz(credentials: dict, config: dict) -> ConnectorTestResult:
    """Test Wiz by getting an OAuth2 token."""
    auth_url = config.get("auth_url", credentials.get("auth_url", "https://auth.app.wiz.io/oauth/token"))
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                auth_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": credentials["client_id"],
                    "client_secret": credentials["client_secret"],
                    "audience": "wiz-api",
                },
            )
        if resp.status_code == 200:
            return ConnectorTestResult(
                success=True,
                message="Successfully authenticated with Wiz",
            )
        else:
            return ConnectorTestResult(
                success=False,
                message=f"Authentication failed: HTTP {resp.status_code}",
            )
    except Exception as e:
        return ConnectorTestResult(success=False, message=f"Connection error: {e}")


TESTERS = {
    "CROWDSTRIKE": test_crowdstrike,
    "NESSUS": test_nessus,
    "DEFENDER": test_defender,
    "WIZ": test_wiz,
}


async def test_connector(connector_type: str, credentials: dict, config: dict) -> ConnectorTestResult:
    """Run the appropriate tester for a connector type."""
    tester = TESTERS.get(connector_type)
    if tester is None:
        return ConnectorTestResult(success=False, message=f"Unknown connector type: {connector_type}")
    return await tester(credentials, config)
