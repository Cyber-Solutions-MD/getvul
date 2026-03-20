# Connectors & Integrations

GetVul integrates with enterprise security tools via **connectors** — pluggable modules that authenticate with vendor APIs, fetch data, and normalize it into GetVul's unified schema.

## Connector Architecture

All connectors implement the `BaseConnector` abstract class:

```python
class BaseConnector:
    async def authenticate(self, credentials: dict, config: dict) -> None
    async def fetch_vulnerabilities(self) -> list[NormalizedVulnerability]
    async def fetch_misconfigurations(self) -> list[NormalizedMisconfiguration]  # optional
```

### Normalized Data Types

**NormalizedVulnerability** — vendor-agnostic vulnerability record:
- `cve_id`, `vulnerability_name`, `cvss_v3_score`, `cvss_v3_vector`
- `severity`, `epss_score`, `exploit_available`, `cisa_kev`
- `hostname`, `ip_address`, `os_name`, `os_version`
- `source`, `source_vuln_id`, `source_scan_id`
- `remediation_id`, `remediation_action`, `remediation_info`
- `exploit_status_id`, `exploit_status_name`
- `affected_product`, `affected_version`, `fixed_version`
- `first_detected_at`, `last_seen_at`

**NormalizedMisconfiguration** — vendor-agnostic CSPM finding:
- `rule_id`, `rule_name`, `rule_description`, `category`, `severity`
- `frameworks` (compliance frameworks)
- `resource_id`, `resource_name`, `resource_type`, `resource_region`
- `cloud_provider`, `cloud_account_id`, `cloud_account_name`
- `source`, `source_finding_id`
- `remediation_info`, `remediation_url`

---

## CrowdStrike Falcon (Implemented)

### Overview
- **Data:** Spotlight vulnerabilities, exploit status, device info, remediation guidance
- **Auth:** OAuth 2.0 (client_id + client_secret)
- **API Version:** v2
- **Base URLs:** US-1 (`api.crowdstrike.com`), US-2 (`api.us-2.crowdstrike.com`), EU-1 (`api.eu-1.crowdstrike.com`), US-GOV (`api.laggar.gcw.crowdstrike.com`)

### Required Credentials
| Field | Description |
|-------|-------------|
| `client_id` | CrowdStrike API client ID |
| `client_secret` | CrowdStrike API client secret |

### Required API Scopes
- `Spotlight Vulnerabilities: Read`
- `Hosts: Read`
- `Remediation: Read` (optional, for remediation details)

### Sync Process
1. Authenticate via OAuth 2.0 token endpoint
2. Fetch vulnerabilities per severity level (CRITICAL → LOW) using Spotlight API
3. Resolve device AIDs to hostnames via Hosts API (batch, cached)
4. Fetch remediation details for each `remediation_id`
5. Map exploit status codes (0–50 scale):
   - 0: Unknown → `exploit_available: false`
   - 10: Available → `exploit_available: true`
   - 20: Active Use → `exploit_available: true`, `cisa_kev: true`
   - 30+: KEV confirmed → `cisa_kev: true`
6. Normalize and return findings

### Key Implementation Details
- Batch device resolution (100 per batch) with in-memory cache
- Remediation details cached to minimize API calls
- Severity-based queries to ensure critical vulnerabilities are fetched first
- Handles API pagination (offset-based)
- ~500 lines of implementation in `crowdstrike.py`

---

## Nessus Professional (Planned)

### Overview
- **Data:** Scan results, plugin vulnerabilities, affected systems
- **Auth:** Access Key + Secret Key
- **API:** REST API (on-premises)

### Required Credentials
| Field | Description |
|-------|-------------|
| `access_key` | Nessus API access key |
| `secret_key` | Nessus API secret key |

### Required Permissions
- Scan Read access
- Plugin details access

---

## Microsoft Defender for Endpoint (Planned)

### Overview
- **Data:** Machines, vulnerabilities, security recommendations
- **Auth:** Azure Entra ID OAuth 2.0 (app registration)
- **API:** Microsoft Graph Security API

### Required Credentials
| Field | Description |
|-------|-------------|
| `tenant_id` | Azure Entra ID tenant ID |
| `client_id` | App registration client ID |
| `client_secret` | App registration client secret |

### Required Permissions
- `Machine.Read.All`
- `Vulnerability.Read.All`
- `SecurityRecommendation.Read.All`

---

## Wiz (Planned)

### Overview
- **Data:** Cloud vulnerabilities, misconfigurations, resource inventory
- **Auth:** OAuth 2.0 (service account)
- **API:** GraphQL

### Required Credentials
| Field | Description |
|-------|-------------|
| `client_id` | Wiz service account client ID |
| `client_secret` | Wiz service account client secret |

### Required Permissions
- `read:vulnerabilities`
- `read:cloud_configuration`
- `read:resources`

### Base URLs
- US1: `api.us1.app.wiz.io`
- US2: `api.us2.app.wiz.io`
- EU1: `api.eu1.app.wiz.io`

---

## Jamf Pro (Implemented)

### Overview
- **Purpose:** MDM enrichment for Apple devices (not vulnerability data)
- **Data:** Computer inventory, user assignments, device details, enrollment status
- **Auth:** OAuth 2.0 (API client + secret)

### Required Credentials
| Field | Description |
|-------|-------------|
| `client_id` | Jamf API client ID |
| `client_secret` | Jamf API client secret |

### Required Permissions
- `Read Computers`
- `Read Users`

### Enrichment Fields
Jamf sync enriches existing Asset records with:
- `serial_number`, `model`, `department`, `building`
- `assigned_user`, `managed_by`, `last_checkin_at`
- `mdm_details` (JSONB with extra metadata)

---

## Ticketing Integrations

### Jira Cloud
- **API:** REST API v3
- **Auth:** API token or OAuth 2.0
- **Capabilities:** Create issues, update status, link to vulnerabilities
- **Fields mapped:** Issue type, priority (from severity), assignee, project, CVE details

### GitHub Issues
- **API:** GitHub REST/GraphQL API
- **Auth:** Personal access token or GitHub App
- **Capabilities:** Create issues, add labels, assign users
- **Labels mapped:** Severity, source, priority

### Ticket Automation Rules
Rules engine for automatic ticket creation:

```json
{
  "conditions": {
    "severity": ["CRITICAL", "HIGH"],
    "exploit_available": true,
    "age_days_min": 7
  },
  "action": {
    "provider": "JIRA",
    "project_key": "SEC",
    "issue_type": "Bug",
    "priority": "High",
    "assignee": "security-team"
  }
}
```

---

## Credential Security

- All connector credentials are **encrypted at rest** using Fernet symmetric encryption
- Encryption key stored in `ENCRYPTION_KEY` environment variable
- Credentials decrypted **only in memory** during active sync operations
- Credentials are **never logged** or exposed in API responses
- The `credentials_secret_arn` column stores the Fernet-encrypted JSON blob

## Connector Management API

See [Backend API — Connectors section](backend-api.md#connectors-apiv1connectors) for full API reference.

### Lifecycle
1. **Create:** Admin provides credentials and config → encrypted and stored
2. **Test:** Validate credentials against vendor API without saving
3. **Enable/Disable:** Toggle `is_enabled` to start/stop background syncs
4. **Sync:** Trigger immediate sync or wait for scheduled interval
5. **Monitor:** Check sync status, last run time, record counts
6. **Delete:** Remove connector and stop all syncs

### Background Scheduler
- **Engine:** APScheduler running inside FastAPI lifespan
- **Default interval:** 15 minutes (configurable per connector)
- **Behavior:** Loops through enabled connectors, triggers sync if interval has elapsed
- **Concurrency:** One sync per connector at a time (prevents overlap)
- **Failure handling:** Errors logged to SyncLog, connector remains enabled for next attempt
