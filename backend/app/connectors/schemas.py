"""Connector schemas — Pydantic models for request/response."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

# ── Connector type metadata ──


class ConnectorPermission(BaseModel):
    scope: str
    access: str
    purpose: str


class ConnectorTypeInfo(BaseModel):
    id: str
    name: str
    description: str
    fields: list[dict[str, Any]]
    permissions: list[ConnectorPermission] = []
    setup_url: str = ""
    base_urls: dict[str, str] = {}
    notes: str = ""


CONNECTOR_TYPES: dict[str, ConnectorTypeInfo] = {
    "CROWDSTRIKE": ConnectorTypeInfo(
        id="CROWDSTRIKE",
        name="CrowdStrike Falcon",
        description="Vulnerability management via Spotlight + CSPM via Configuration Assessment",
        fields=[
            {"name": "client_id", "label": "Client ID", "type": "text", "required": True},
            {"name": "client_secret", "label": "Client Secret", "type": "password", "required": True},
            {"name": "base_url", "label": "Base URL", "type": "select", "required": True},
        ],
        permissions=[
            ConnectorPermission(
                scope="Spotlight Vulnerabilities", access="Read", purpose="Fetch vulnerability findings"
            ),
            ConnectorPermission(scope="Hosts", access="Read", purpose="Resolve device hostnames and OS info"),
            ConnectorPermission(
                scope="Configuration Assessment", access="Read", purpose="CSPM / cloud posture findings"
            ),
            ConnectorPermission(scope="CSPM Registration", access="Read", purpose="Fallback for cloud posture data"),
        ],
        setup_url="https://falcon.crowdstrike.com/documentation/46/crowdstrike-oauth2-based-apis",
        base_urls={
            "US-1": "https://api.crowdstrike.com",
            "US-2": "https://api.us-2.crowdstrike.com",
            "EU-1": "https://api.eu-1.crowdstrike.com",
            "US-GOV": "https://api.laggar.gcw.crowdstrike.com",
        },
        notes="Create an API client in Falcon Console → Support & Resources → API Clients and Keys",
    ),
    "NESSUS": ConnectorTypeInfo(
        id="NESSUS",
        name="Nessus Professional",
        description="On-prem vulnerability scanner",
        fields=[
            {"name": "url", "label": "Nessus URL", "type": "text", "required": True},
            {"name": "access_key", "label": "Access Key", "type": "password", "required": True},
            {"name": "secret_key", "label": "Secret Key", "type": "password", "required": True},
        ],
        permissions=[
            ConnectorPermission(scope="Scans", access="Read", purpose="List and export scan results"),
            ConnectorPermission(scope="Vulnerabilities", access="Read", purpose="Fetch vulnerability details"),
        ],
        setup_url="https://docs.tenable.com/nessus/Content/GenerateAnAPIKey.htm",
        notes="Generate API keys in Nessus → Settings → My Account → API Keys",
    ),
    "DEFENDER": ConnectorTypeInfo(
        id="DEFENDER",
        name="Microsoft Defender for Endpoint",
        description="Microsoft's endpoint security + vulnerability management",
        fields=[
            {"name": "tenant_id", "label": "Azure Tenant ID", "type": "text", "required": True},
            {"name": "client_id", "label": "App Client ID", "type": "text", "required": True},
            {"name": "client_secret", "label": "App Client Secret", "type": "password", "required": True},
        ],
        permissions=[
            ConnectorPermission(scope="Machine.Read.All", access="Application", purpose="Read device information"),
            ConnectorPermission(
                scope="Vulnerability.Read.All", access="Application", purpose="Read vulnerability data"
            ),
            ConnectorPermission(
                scope="SecurityRecommendation.Read.All", access="Application", purpose="Read security recommendations"
            ),
        ],
        setup_url="https://learn.microsoft.com/en-us/defender-endpoint/api/exposed-apis-create-app-webapp",
        notes="Register an app in Azure Entra ID → API permissions → Add Microsoft Threat Protection permissions",
    ),
    "WIZ": ConnectorTypeInfo(
        id="WIZ",
        name="Wiz",
        description="Cloud security — vulnerabilities + CSPM + CIEM",
        fields=[
            {"name": "client_id", "label": "Client ID", "type": "text", "required": True},
            {"name": "client_secret", "label": "Client Secret", "type": "password", "required": True},
            {"name": "api_url", "label": "API Endpoint URL", "type": "text", "required": True},
            {"name": "auth_url", "label": "Auth URL", "type": "text", "required": True},
        ],
        permissions=[
            ConnectorPermission(scope="read:vulnerabilities", access="Read", purpose="Fetch vulnerability findings"),
            ConnectorPermission(scope="read:cloud_configuration", access="Read", purpose="CSPM findings"),
            ConnectorPermission(scope="read:resources", access="Read", purpose="Cloud resource inventory"),
        ],
        setup_url="https://docs.wiz.io/wiz-docs/docs/set-up-wiz-service-accounts",
        base_urls={
            "US": "https://api.us1.app.wiz.io/graphql",
            "US2": "https://api.us2.app.wiz.io/graphql",
            "EU": "https://api.eu1.app.wiz.io/graphql",
        },
        notes="Create a Service Account in Wiz → Settings → Service Accounts with read-only permissions",
    ),
    "GOOGLE_WORKSPACE": ConnectorTypeInfo(
        id="GOOGLE_WORKSPACE",
        name="Google Workspace",
        description="SSO directory — sync users and groups from Google Workspace",
        fields=[
            {
                "name": "service_account_json",
                "label": "Service Account JSON Key (paste full file content)",
                "type": "password",
                "required": True,
            },
            {"name": "admin_email", "label": "Admin Email (for impersonation)", "type": "text", "required": True},
            {"name": "domain", "label": "Google Workspace Domain", "type": "text", "required": True},
        ],
        permissions=[
            ConnectorPermission(
                scope="admin.directory.user.readonly", access="Read", purpose="List all users in the domain"
            ),
            ConnectorPermission(scope="admin.directory.group.readonly", access="Read", purpose="List all groups"),
            ConnectorPermission(
                scope="admin.directory.group.member.readonly", access="Read", purpose="List group members"
            ),
        ],
        setup_url="https://admin.google.com/ac/owl/domainwidedelegation",
        notes="1) Create a Service Account in GCP Console → download JSON key. 2) Enable Admin SDK API. 3) In Google Admin → Security → API Controls → Domain-wide delegation, add the client_id with the 3 scopes. 4) Paste the full JSON key content here.",
    ),
    "AZURE_ENTRA_ID": ConnectorTypeInfo(
        id="AZURE_ENTRA_ID",
        name="Azure Entra ID",
        description="SSO directory — sync users and groups from Microsoft Entra ID",
        fields=[
            {"name": "tenant_id", "label": "Azure Tenant ID", "type": "text", "required": True},
            {"name": "client_id", "label": "App Client ID", "type": "text", "required": True},
            {"name": "client_secret", "label": "App Client Secret", "type": "password", "required": True},
        ],
        permissions=[
            ConnectorPermission(scope="User.Read.All", access="Application", purpose="Read all user profiles"),
            ConnectorPermission(scope="Group.Read.All", access="Application", purpose="Read all groups"),
            ConnectorPermission(scope="GroupMember.Read.All", access="Application", purpose="Read group memberships"),
        ],
        setup_url="https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps",
        notes="Register an app in Azure Entra ID → API permissions → Add Microsoft Graph Application permissions.",
    ),
    "ASANA": ConnectorTypeInfo(
        id="ASANA",
        name="Asana",
        description="Create vulnerability tickets in Asana and assign them to users for remediation",
        fields=[
            {"name": "access_token", "label": "Personal Access Token", "type": "password", "required": True},
        ],
        permissions=[
            ConnectorPermission(scope="tasks:write", access="Write", purpose="Create and update vulnerability tickets"),
            ConnectorPermission(scope="projects:read", access="Read", purpose="List projects for ticket assignment"),
            ConnectorPermission(scope="workspaces:read", access="Read", purpose="List workspaces"),
        ],
        setup_url="https://app.asana.com/0/my-apps",
        notes="Generate a Personal Access Token in Asana → My Settings → Apps → Developer Apps → Personal Access Tokens. After adding, edit the connector to select a workspace and project.",
    ),
    "HUMAANS": ConnectorTypeInfo(
        id="HUMAANS",
        name="Humaans",
        description="HR platform — enriches assets with user info, GitHub/Element handles, and device assignments",
        fields=[
            {"name": "api_token", "label": "API Access Token", "type": "password", "required": True},
        ],
        permissions=[
            ConnectorPermission(scope="public:read", access="Read", purpose="Read people names, emails, job titles"),
            ConnectorPermission(
                scope="private:read", access="Read", purpose="Read equipment, custom fields (GitHub/Element handles)"
            ),
        ],
        setup_url="https://app.humaans.io/settings/api-access-tokens",
        notes="Generate an API token in Humaans → Settings → API Access Tokens. Use an Owner or Admin token to access all people. Custom fields named 'GitHub' and 'Element' (or 'Matrix') will be auto-detected.",
    ),
    "JAMF": ConnectorTypeInfo(
        id="JAMF",
        name="Jamf Pro",
        description="Apple device management — enriches asset data with MDM info",
        fields=[
            {"name": "base_url", "label": "Jamf Pro URL", "type": "text", "required": True},
            {"name": "client_id", "label": "Client ID", "type": "text", "required": True},
            {"name": "client_secret", "label": "Client Secret", "type": "password", "required": True},
        ],
        permissions=[
            ConnectorPermission(scope="Read Computers", access="Read", purpose="Fetch computer inventory and details"),
            ConnectorPermission(scope="Read Users", access="Read", purpose="Resolve assigned user info"),
        ],
        setup_url="https://learn.jamf.com/en-US/bundle/jamf-pro-documentation/page/API_Roles_and_Clients.html",
        notes="Create API Role with Read Computers + Read Users, then create API Client assigned to that role",
    ),
    "JIRA": ConnectorTypeInfo(
        id="JIRA",
        name="Jira",
        description="Create and track vulnerability remediation issues in Jira Cloud or Server",
        fields=[
            {"name": "url", "label": "Jira URL", "type": "text", "required": True},
            {"name": "email", "label": "Email", "type": "text", "required": True},
            {"name": "api_token", "label": "API Token", "type": "password", "required": True},
        ],
        permissions=[
            ConnectorPermission(scope="Browse Projects", access="Read", purpose="List projects for ticket assignment"),
            ConnectorPermission(scope="Create Issues", access="Write", purpose="Create vulnerability tickets"),
            ConnectorPermission(scope="Edit Issues", access="Write", purpose="Update and transition ticket status"),
        ],
        setup_url="https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/",
        notes="Generate an API token at id.atlassian.com → Security → API Tokens. Use your Atlassian account email and the token as password.",
    ),
    "QUALYS": ConnectorTypeInfo(
        id="QUALYS",
        name="Qualys VMDR",
        description="Enterprise vulnerability management, detection and response",
        fields=[
            {"name": "url", "label": "Qualys API URL", "type": "text", "required": True},
            {"name": "username", "label": "Username", "type": "text", "required": True},
            {"name": "password", "label": "Password", "type": "password", "required": True},
        ],
        permissions=[
            ConnectorPermission(scope="Host Assets", access="Read", purpose="Fetch managed assets and host details"),
            ConnectorPermission(scope="Vulnerabilities", access="Read", purpose="Fetch vulnerability detections"),
            ConnectorPermission(
                scope="Knowledge Base", access="Read", purpose="Resolve QID to CVE and remediation info"
            ),
        ],
        setup_url="https://www.qualys.com/docs/qualys-api-vmpc-user-guide.pdf",
        base_urls={
            "US-1": "https://qualysapi.qualys.com",
            "US-2": "https://qualysapi.qg2.apps.qualys.com",
            "US-3": "https://qualysapi.qg3.apps.qualys.com",
            "EU-1": "https://qualysapi.qualys.eu",
            "EU-2": "https://qualysapi.qg2.apps.qualys.eu",
            "IN-1": "https://qualysapi.qg1.apps.qualys.in",
        },
        notes="Use a reader account or API-only user. API URL depends on your Qualys platform (US/EU/IN).",
    ),
    "OKTA": ConnectorTypeInfo(
        id="OKTA",
        name="Okta",
        description="Identity provider — SSO authentication and user/group directory sync via SCIM",
        fields=[
            {"name": "domain", "label": "Okta Domain", "type": "text", "required": True},
            {"name": "api_token", "label": "API Token", "type": "password", "required": True},
        ],
        permissions=[
            ConnectorPermission(scope="okta.users.read", access="Read", purpose="List all users in the directory"),
            ConnectorPermission(scope="okta.groups.read", access="Read", purpose="List groups and memberships"),
        ],
        setup_url="https://developer.okta.com/docs/guides/create-an-api-token/main/",
        notes="Create an API token in Okta Admin → Security → API → Tokens. Domain format: your-org.okta.com",
    ),
    "INTUNE": ConnectorTypeInfo(
        id="INTUNE",
        name="Microsoft Intune",
        description="Endpoint management — enrich assets with device compliance, OS details, and user assignments",
        fields=[
            {"name": "tenant_id", "label": "Azure Tenant ID", "type": "text", "required": True},
            {"name": "client_id", "label": "App Client ID", "type": "text", "required": True},
            {"name": "client_secret", "label": "App Client Secret", "type": "password", "required": True},
        ],
        permissions=[
            ConnectorPermission(
                scope="DeviceManagementManagedDevices.Read.All",
                access="Application",
                purpose="Read managed device inventory",
            ),
            ConnectorPermission(scope="User.Read.All", access="Application", purpose="Resolve device owners"),
        ],
        setup_url="https://learn.microsoft.com/en-us/mem/intune/developer/intune-graph-apis",
        notes="Register an app in Azure Entra ID with Microsoft Graph Application permissions for Intune device read.",
    ),
    "RAPID7": ConnectorTypeInfo(
        id="RAPID7",
        name="Rapid7 InsightVM",
        description="Vulnerability management with risk-based prioritization and live dashboards",
        fields=[
            {"name": "url", "label": "InsightVM Console URL", "type": "text", "required": True},
            {"name": "username", "label": "Username", "type": "text", "required": True},
            {"name": "password", "label": "Password", "type": "password", "required": True},
        ],
        permissions=[
            ConnectorPermission(scope="Assets", access="Read", purpose="Fetch asset inventory"),
            ConnectorPermission(
                scope="Vulnerabilities", access="Read", purpose="Fetch vulnerability findings per asset"
            ),
            ConnectorPermission(scope="Solutions", access="Read", purpose="Resolve remediation steps"),
        ],
        setup_url="https://help.rapid7.com/insightvm/en-us/api/index.html",
        notes="Use the InsightVM Security Console API (v3). URL is your console address, e.g. https://insightvm.company.com:3780",
    ),
}


# ── Request / Response schemas ──


class ConnectorCreate(BaseModel):
    connector_type: str
    credentials: dict[str, str]
    config: dict[str, Any] = {}
    sync_interval_minutes: int = 60


class ConnectorUpdate(BaseModel):
    credentials: dict[str, str] | None = None
    config: dict[str, Any] | None = None
    is_enabled: bool | None = None
    sync_interval_minutes: int | None = None


class ConnectorTestRequest(BaseModel):
    connector_type: str
    credentials: dict[str, str]
    config: dict[str, Any] = {}


class ConnectorTestResponse(BaseModel):
    success: bool
    message: str
    scopes: dict[str, bool] = {}


class ConnectorResponse(BaseModel):
    id: str
    connector_type: str
    connector_name: str = ""
    is_enabled: bool
    config: dict[str, Any] = {}
    has_credentials: bool = False
    last_sync_at: datetime | None = None
    last_sync_status: str | None = None
    last_sync_record_count: int | None = None
    last_error: str | None = None
    consecutive_failure_count: int = 0
    sync_interval_minutes: int = 60
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SyncStatusResponse(BaseModel):
    connector_id: str
    is_syncing: bool
    last_sync_at: datetime | None = None
    last_sync_status: str | None = None
    last_sync_record_count: int | None = None


# ── Aliases for backward compatibility ──
ConnectorConfigResponse = ConnectorResponse
ConnectorTypeResponse = ConnectorTypeInfo
ConnectorTestResult = ConnectorTestResponse
ConnectorCreateRequest = ConnectorCreate
ConnectorUpdateRequest = ConnectorUpdate
ConnectorTest = ConnectorTestRequest
