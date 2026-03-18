"""Test connector credentials by attempting authentication with each provider."""

from __future__ import annotations

import httpx

from app.connectors.schemas import ConnectorTestResult


async def test_crowdstrike(credentials: dict, config: dict) -> ConnectorTestResult:
    """Test CrowdStrike OAuth2 token endpoint and check available scopes."""
    base_url = config.get("base_url", credentials.get("base_url", "https://api.crowdstrike.com"))
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Get token
            resp = await client.post(
                f"{base_url}/oauth2/token",
                data={
                    "client_id": credentials["client_id"],
                    "client_secret": credentials["client_secret"],
                },
            )
        if resp.status_code == 201:
            token_data = resp.json()
            token = token_data.get("access_token", "")

            # Check which scopes are available by testing key endpoints
            scope_results = {}
            async with httpx.AsyncClient(timeout=10) as client:
                headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

                # Test Spotlight (Vulnerabilities)
                r = await client.get(f"{base_url}/spotlight/combined/vulnerabilities/v1",
                                      headers=headers, params={"limit": 1})
                scope_results["Vulnerabilities (Spotlight)"] = "✓" if r.status_code == 200 else f"✗ ({r.status_code})"

                # Test Hosts
                r = await client.get(f"{base_url}/devices/queries/devices/v1",
                                      headers=headers, params={"limit": 1})
                scope_results["Hosts"] = "✓" if r.status_code == 200 else f"✗ ({r.status_code})"

                # Test Configuration Assessment (CSPM)
                r = await client.get(f"{base_url}/configuration-assessment/combined/assessments/v1",
                                      headers=headers, params={"limit": 1})
                scope_results["Configuration Assessment (CSPM)"] = "✓" if r.status_code == 200 else f"✗ ({r.status_code})"

                # Test CSPM Registration (fallback)
                r = await client.get(f"{base_url}/cloud-connect-cspm-aws/entities/account/v1",
                                      headers=headers, params={"limit": 1})
                scope_results["CSPM Registration"] = "✓" if r.status_code == 200 else f"✗ ({r.status_code})"

            return ConnectorTestResult(
                success=True,
                message="Successfully authenticated with CrowdStrike",
                details={
                    "expires_in": token_data.get("expires_in"),
                    "scopes_available": scope_results,
                },
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
    base_url = config.get("base_url", credentials.get("base_url", "https://localhost:8834"))
    try:
        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            resp = await client.get(
                f"{base_url}/server/status",
                headers={"X-ApiKeys": f"accessKey={credentials['access_key']};secretKey={credentials['secret_key']}"},
            )
        if resp.status_code == 200:
            return ConnectorTestResult(success=True, message="Successfully connected to Nessus", details=resp.json())
        else:
            return ConnectorTestResult(success=False, message=f"Authentication failed: HTTP {resp.status_code}")
    except Exception as e:
        return ConnectorTestResult(success=False, message=f"Connection error: {e}")


async def test_defender(credentials: dict, config: dict) -> ConnectorTestResult:
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
            return ConnectorTestResult(success=True, message="Successfully authenticated with Microsoft Defender")
        else:
            return ConnectorTestResult(
                success=False,
                message=f"Authentication failed: HTTP {resp.status_code}",
                details={"error": resp.json().get("error_description", resp.text[:500])},
            )
    except Exception as e:
        return ConnectorTestResult(success=False, message=f"Connection error: {e}")


async def test_wiz(credentials: dict, config: dict) -> ConnectorTestResult:
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
            return ConnectorTestResult(success=True, message="Successfully authenticated with Wiz")
        else:
            return ConnectorTestResult(success=False, message=f"Authentication failed: HTTP {resp.status_code}")
    except Exception as e:
        return ConnectorTestResult(success=False, message=f"Connection error: {e}")


TESTERS = {
    "CROWDSTRIKE": test_crowdstrike,
    "NESSUS": test_nessus,
    "DEFENDER": test_defender,
    "WIZ": test_wiz,
}


async def test_connector(connector_type: str, credentials: dict, config: dict) -> ConnectorTestResult:
    tester = TESTERS.get(connector_type)
    if tester is None:
        return ConnectorTestResult(success=False, message=f"Unknown connector type: {connector_type}")
    return await tester(credentials, config)
