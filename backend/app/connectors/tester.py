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
                r = await client.get(
                    f"{base_url}/spotlight/combined/vulnerabilities/v1", headers=headers, params={"limit": 1}
                )
                scope_results["Vulnerabilities (Spotlight)"] = "✓" if r.status_code == 200 else f"✗ ({r.status_code})"

                # Test Hosts
                r = await client.get(f"{base_url}/devices/queries/devices/v1", headers=headers, params={"limit": 1})
                scope_results["Hosts"] = "✓" if r.status_code == 200 else f"✗ ({r.status_code})"

                # Test Configuration Assessment (CSPM)
                r = await client.get(
                    f"{base_url}/configuration-assessment/combined/assessments/v1", headers=headers, params={"limit": 1}
                )
                scope_results["Configuration Assessment (CSPM)"] = (
                    "✓" if r.status_code == 200 else f"✗ ({r.status_code})"
                )

                # Test CSPM Registration (fallback)
                r = await client.get(
                    f"{base_url}/cloud-connect-cspm-aws/entities/account/v1", headers=headers, params={"limit": 1}
                )
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
        async with httpx.AsyncClient(timeout=15, verify=config.get("verify_tls", True)) as client:
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
            return ConnectorTestResult(
                success=False, message=f"Auth failed: HTTP {resp.status_code}", details={"response": resp.text[:500]}
            )
    except Exception as e:
        return ConnectorTestResult(success=False, message=f"Connection error: {e}")


async def test_google_workspace(credentials: dict, config: dict) -> ConnectorTestResult:
    """Test Google Workspace Admin SDK access via service account or access token."""
    from app.connectors.google_workspace import GoogleWorkspaceConnector

    domain = config.get("domain", credentials.get("domain", ""))
    if not domain:
        return ConnectorTestResult(success=False, message="Domain is required")

    connector = GoogleWorkspaceConnector()
    try:
        authed = await connector.authenticate(credentials, config)
        if not authed:
            return ConnectorTestResult(
                success=False, message="Authentication failed — check JSON key, admin email, and domain-wide delegation"
            )
        users = await connector.fetch_users()
        await connector.close()
        return ConnectorTestResult(
            success=True,
            message=f"Connected to Google Workspace ({domain})",
            details={"total_users": len(users)},
        )
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
            resp = await client.post(
                f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "scope": "https://graph.microsoft.com/.default",
                },
            )
            if resp.status_code != 200:
                return ConnectorTestResult(success=False, message=f"Auth failed: HTTP {resp.status_code}")
            token = resp.json()["access_token"]

            users_resp = await client.get(
                "https://graph.microsoft.com/v1.0/users",
                headers={"Authorization": f"Bearer {token}"},
                params={"$top": 1, "$select": "id"},
            )
            groups_resp = await client.get(
                "https://graph.microsoft.com/v1.0/groups",
                headers={"Authorization": f"Bearer {token}"},
                params={"$top": 1, "$select": "id"},
            )
            return ConnectorTestResult(
                success=True,
                message="Connected to Azure Entra ID",
                details={
                    "users_access": "✓" if users_resp.status_code == 200 else f"✗ ({users_resp.status_code})",
                    "groups_access": "✓" if groups_resp.status_code == 200 else f"✗ ({groups_resp.status_code})",
                },
            )
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
            cf_resp = await client.get(
                "https://app.humaans.io/api/custom-fields", headers=headers, params={"$limit": 250}
            )
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


async def test_qualys(credentials: dict, config: dict) -> ConnectorTestResult:
    """Test Qualys VMDR API access."""
    url = config.get("base_url", credentials.get("url", "")).rstrip("/")
    username = credentials.get("username", "")
    password = credentials.get("password", "")
    if not all([url, username, password]):
        return ConnectorTestResult(success=False, message="URL, username and password are required")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{url}/api/2.0/fo/asset/host/?action=list&truncation_limit=1",
                auth=(username, password),
                headers={"X-Requested-With": "GetVul", "Accept": "application/json"},
            )
        if resp.status_code == 200:
            return ConnectorTestResult(success=True, message="Connected to Qualys VMDR")
        elif resp.status_code == 401:
            return ConnectorTestResult(success=False, message="Authentication failed — check username/password")
        return ConnectorTestResult(success=False, message=f"HTTP {resp.status_code}: {resp.text[:300]}")
    except Exception as e:
        return ConnectorTestResult(success=False, message=f"Connection error: {e}")


async def test_rapid7(credentials: dict, config: dict) -> ConnectorTestResult:
    """Test Rapid7 InsightVM API access."""
    url = config.get("base_url", credentials.get("url", "")).rstrip("/")
    username = credentials.get("username", "")
    password = credentials.get("password", "")
    if not all([url, username, password]):
        return ConnectorTestResult(success=False, message="Console URL, username and password are required")
    try:
        async with httpx.AsyncClient(timeout=15, verify=config.get("verify_tls", True)) as client:
            resp = await client.get(
                f"{url}/api/3/assets?page=0&size=1",
                auth=(username, password),
                headers={"Accept": "application/json"},
            )
        if resp.status_code == 200:
            total = resp.json().get("page", {}).get("totalResources", "?")
            return ConnectorTestResult(
                success=True, message=f"Connected to InsightVM — {total} assets", details={"total_assets": total}
            )
        elif resp.status_code == 401:
            return ConnectorTestResult(success=False, message="Authentication failed")
        return ConnectorTestResult(success=False, message=f"HTTP {resp.status_code}")
    except Exception as e:
        return ConnectorTestResult(success=False, message=f"Connection error: {e}")


async def test_jira(credentials: dict, config: dict) -> ConnectorTestResult:
    """Test Jira Cloud/Server API access."""
    import base64

    url = config.get("base_url", credentials.get("url", "")).rstrip("/")
    email = credentials.get("email", "")
    token = credentials.get("api_token", "")
    if not all([url, email, token]):
        return ConnectorTestResult(success=False, message="Jira URL, email, and API token are required")
    try:
        auth_str = base64.b64encode(f"{email}:{token}".encode()).decode()
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{url}/rest/api/2/myself",
                headers={"Authorization": f"Basic {auth_str}", "Accept": "application/json"},
            )
        if resp.status_code == 200:
            data = resp.json()
            # List projects
            proj_resp = await httpx.AsyncClient(timeout=15).get(
                f"{url}/rest/api/2/project",
                headers={"Authorization": f"Basic {auth_str}", "Accept": "application/json"},
            )
            proj_count = len(proj_resp.json()) if proj_resp.status_code == 200 else "?"
            return ConnectorTestResult(
                success=True,
                message=f"Authenticated as {data.get('displayName', data.get('name', email))}",
                details={"user": data.get("displayName"), "email": data.get("emailAddress"), "projects": proj_count},
            )
        return ConnectorTestResult(success=False, message=f"Authentication failed: HTTP {resp.status_code}")
    except Exception as e:
        return ConnectorTestResult(success=False, message=f"Connection error: {e}")


async def test_github(credentials: dict, config: dict) -> ConnectorTestResult:
    """Test a GitHub PAT + owner/repo via GitHubClient.test_connection().

    Mirrors the established dispatch.py/rule_engine.py contract: `token`
    lives in the encrypted credentials dict, `owner`/`repo` live in the
    plaintext config dict (T-23-13 — the PAT is never stored in plaintext).
    """
    from app.ticketing.github_client import GitHubClient

    token = credentials.get("token", "")
    owner = config.get("owner", "")
    repo = config.get("repo", "")
    if not all([token, owner, repo]):
        return ConnectorTestResult(success=False, message="Token, owner, and repo are required")
    client = GitHubClient(token=token, owner=owner, repo=repo)
    try:
        result = await client.test_connection()
        return ConnectorTestResult(success=result["success"], message=result["message"])
    except Exception as e:
        return ConnectorTestResult(success=False, message=f"Connection error: {e}")
    finally:
        await client.close()


async def test_okta(credentials: dict, config: dict) -> ConnectorTestResult:
    """Test Okta API access."""
    domain = config.get("domain", credentials.get("domain", "")).strip().rstrip("/")
    token = credentials.get("api_token", "")
    if not domain or not token:
        return ConnectorTestResult(success=False, message="Okta domain and API token are required")
    # Normalize domain
    if not domain.startswith("https://"):
        domain = f"https://{domain}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{domain}/api/v1/users?limit=1",
                headers={"Authorization": f"SSWS {token}", "Accept": "application/json"},
            )
        if resp.status_code == 200:
            # Get user count from a second call
            groups_resp = await httpx.AsyncClient(timeout=15).get(
                f"{domain}/api/v1/groups?limit=1",
                headers={"Authorization": f"SSWS {token}", "Accept": "application/json"},
            )
            return ConnectorTestResult(
                success=True,
                message="Connected to Okta",
                details={
                    "users_access": "✓",
                    "groups_access": "✓" if groups_resp.status_code == 200 else f"✗ ({groups_resp.status_code})",
                },
            )
        return ConnectorTestResult(success=False, message=f"Auth failed: HTTP {resp.status_code}")
    except Exception as e:
        return ConnectorTestResult(success=False, message=f"Connection error: {e}")


async def test_intune(credentials: dict, config: dict) -> ConnectorTestResult:
    """Test Microsoft Intune API access."""
    tenant_id = credentials.get("tenant_id", "")
    client_id = credentials.get("client_id", "")
    client_secret = credentials.get("client_secret", "")
    if not all([tenant_id, client_id, client_secret]):
        return ConnectorTestResult(success=False, message="Tenant ID, Client ID, and Client Secret are required")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "scope": "https://graph.microsoft.com/.default",
                },
            )
            if resp.status_code != 200:
                return ConnectorTestResult(success=False, message=f"Auth failed: HTTP {resp.status_code}")
            token = resp.json()["access_token"]

            devices_resp = await client.get(
                "https://graph.microsoft.com/v1.0/deviceManagement/managedDevices",
                headers={"Authorization": f"Bearer {token}"},
                params={"$top": 1, "$select": "id,deviceName"},
            )
            return ConnectorTestResult(
                success=True,
                message="Connected to Microsoft Intune",
                details={
                    "devices_access": "✓" if devices_resp.status_code == 200 else f"✗ ({devices_resp.status_code})",
                },
            )
    except Exception as e:
        return ConnectorTestResult(success=False, message=f"Connection error: {e}")


TESTERS = {
    "CROWDSTRIKE": test_crowdstrike,
    "NESSUS": test_nessus,
    "DEFENDER": test_defender,
    "WIZ": test_wiz,
    "QUALYS": test_qualys,
    "RAPID7": test_rapid7,
    "JAMF": test_jamf,
    "GOOGLE_WORKSPACE": test_google_workspace,
    "AZURE_ENTRA_ID": test_azure_entra_id,
    "OKTA": test_okta,
    "ASANA": test_asana,
    "JIRA": test_jira,
    "GITHUB": test_github,
    "HUMAANS": test_humaans,
    "INTUNE": test_intune,
}


async def test_connector(connector_type: str, credentials: dict, config: dict) -> ConnectorTestResult:
    tester = TESTERS.get(connector_type)
    if tester is None:
        return ConnectorTestResult(success=False, message=f"Unknown connector type: {connector_type}")
    return await tester(credentials, config)
