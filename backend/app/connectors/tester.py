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




async def test_jamf(credentials: dict, config: dict) -> ConnectorTestResult:
    """Test JAMF Pro API access."""
    base_url = config.get("base_url", credentials.get("base_url", "")).rstrip("/")
    if not base_url:
        return ConnectorTestResult(success=False, message="Base URL is required")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{base_url}/api/oauth/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": credentials["client_id"],
                    "client_secret": credentials["client_secret"],
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        if resp.status_code == 200:
            token = resp.json().get("access_token", "")
            # Test inventory access
            async with httpx.AsyncClient(timeout=15) as client:
                inv_resp = await client.get(
                    f"{base_url}/api/v1/computers-inventory",
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                    params={"page-size": 1},
                )
            inv_status = "✓" if inv_resp.status_code == 200 else f"✗ ({inv_resp.status_code})"
            total = inv_resp.json().get("totalCount", "?") if inv_resp.status_code == 200 else "?"
            return ConnectorTestResult(
                success=True,
                message="Successfully authenticated with Jamf Pro",
                details={"inventory_access": inv_status, "total_computers": total},
            )
        else:
            return ConnectorTestResult(success=False, message=f"Auth failed: HTTP {resp.status_code}", details={"response": resp.text[:500]})
    except Exception as e:
        return ConnectorTestResult(success=False, message=f"Connection error: {e}")

async def test_google_workspace(credentials: dict, config: dict) -> ConnectorTestResult:
    """Test Google Workspace Admin SDK access."""
    token = credentials.get("access_token", "")
    domain = config.get("domain", credentials.get("domain", ""))
    if not token or not domain:
        return ConnectorTestResult(success=False, message="Access token and domain are required")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            h = {"Authorization": f"Bearer {token}"}
            resp = await client.get("https://admin.googleapis.com/admin/directory/v1/users",
                                     headers=h, params={"domain": domain, "maxResults": 1})
            if resp.status_code == 200:
                total = resp.json().get("totalResults", "?")
                return ConnectorTestResult(success=True, message=f"Connected to Google Workspace ({domain})",
                                           details={"total_users": total})
            return ConnectorTestResult(success=False, message=f"Auth failed: HTTP {resp.status_code}")
    except Exception as e:
        return ConnectorTestResult(success=False, message=f"Connection error: {e}")


async def test_azure_entra_id(credentials: dict, config: dict) -> ConnectorTestResult:
    """Test Azure Entra ID Graph API access."""
    tenant_id = credentials.get("tenant_id", "")
    client_id = credentials.get("client_id", "")
    client_secret = credentials.get("client_secret", "")
    if not all([tenant_id, client_id, client_secret]):
        return ConnectorTestResult(success=False, message="Tenant ID, Client ID, and Client Secret are required")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
                                      data={"grant_type": "client_credentials", "client_id": client_id,
                                            "client_secret": client_secret, "scope": "https://graph.microsoft.com/.default"})
            if resp.status_code != 200:
                return ConnectorTestResult(success=False, message=f"Auth failed: HTTP {resp.status_code}")
            token = resp.json()["access_token"]

            users_resp = await client.get("https://graph.microsoft.com/v1.0/users",
                                           headers={"Authorization": f"Bearer {token}"}, params={"$top": 1, "$select": "id"})
            groups_resp = await client.get("https://graph.microsoft.com/v1.0/groups",
                                            headers={"Authorization": f"Bearer {token}"}, params={"$top": 1, "$select": "id"})
            return ConnectorTestResult(success=True, message="Connected to Azure Entra ID",
                                       details={"users_access": "✓" if users_resp.status_code == 200 else f"✗ ({users_resp.status_code})",
                                                 "groups_access": "✓" if groups_resp.status_code == 200 else f"✗ ({groups_resp.status_code})"})
    except Exception as e:
        return ConnectorTestResult(success=False, message=f"Connection error: {e}")


async def test_asana(credentials: dict, config: dict) -> ConnectorTestResult:
    """Test Asana Personal Access Token."""
    token = credentials.get("access_token", "")
    if not token:
        return ConnectorTestResult(success=False, message="Access token is required")
    try:
        from app.ticketing.asana_client import AsanaClient
        client = AsanaClient(token)
        result = await client.test_connection()
        await client.close()
        if result["success"]:
            return ConnectorTestResult(
                success=True,
                message=f"Authenticated as {result['user']} ({result['email']})",
                details={
                    "user": result["user"],
                    "email": result["email"],
                    "workspaces": result["workspaces"],
                },
            )
        return ConnectorTestResult(success=False, message=result["message"])
    except Exception as e:
        return ConnectorTestResult(success=False, message=f"Connection error: {e}")


async def test_humaans(credentials: dict, config: dict) -> ConnectorTestResult:
    """Test Humaans.io API access token."""
    token = credentials.get("api_token", "")
    if not token:
        return ConnectorTestResult(success=False, message="API token is required")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

            # Test people access
            resp = await client.get("https://app.humaans.io/api/people", headers=headers, params={"$limit": 1})
            if resp.status_code != 200:
                return ConnectorTestResult(success=False, message=f"Auth failed: HTTP {resp.status_code}")

            people_total = resp.json().get("total", 0)

            # Test equipment access
            eq_resp = await client.get("https://app.humaans.io/api/equipment", headers=headers, params={"$limit": 1})
            eq_status = "✓" if eq_resp.status_code == 200 else f"✗ ({eq_resp.status_code})"
            eq_total = eq_resp.json().get("total", "?") if eq_resp.status_code == 200 else "?"

            # Test custom fields access
            cf_resp = await client.get("https://app.humaans.io/api/custom-fields", headers=headers, params={"$limit": 250})
            cf_status = "✓" if cf_resp.status_code == 200 else f"✗ ({cf_resp.status_code})"
            field_names = []
            if cf_resp.status_code == 200:
                field_names = [f.get("name", "") for f in cf_resp.json().get("data", [])]

            return ConnectorTestResult(
                success=True,
                message="Successfully authenticated with Humaans",
                details={
                    "people_count": people_total,
                    "equipment_access": eq_status,
                    "equipment_count": eq_total,
                    "custom_fields_access": cf_status,
                    "custom_field_names": field_names,
                },
            )
    except Exception as e:
        return ConnectorTestResult(success=False, message=f"Connection error: {e}")


TESTERS = {
    "CROWDSTRIKE": test_crowdstrike,
    "NESSUS": test_nessus,
    "DEFENDER": test_defender,
    "WIZ": test_wiz,
    "JAMF": test_jamf,
    "GOOGLE_WORKSPACE": test_google_workspace,
    "AZURE_ENTRA_ID": test_azure_entra_id,
    "ASANA": test_asana,
    "HUMAANS": test_humaans,
}


async def test_connector(connector_type: str, credentials: dict, config: dict) -> ConnectorTestResult:
    tester = TESTERS.get(connector_type)
    if tester is None:
        return ConnectorTestResult(success=False, message=f"Unknown connector type: {connector_type}")
    return await tester(credentials, config)
