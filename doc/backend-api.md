# Backend API Reference

The GetVul backend is a FastAPI application (Python 3.12) serving a REST API at `http://localhost:8000`.

Interactive API docs (Swagger): `http://localhost:8000/docs`

## Route Overview

| Prefix | Module | Description |
|--------|--------|-------------|
| `/auth` | auth | SSO login, token refresh, user info |
| `/api/v1/vulnerabilities` | vulnerabilities | Vulnerability CRUD, stats, remediations |
| `/api/v1/assets` | assets | Asset inventory, classification, stats |
| `/api/v1/connectors` | connectors | Connector config, sync, testing |
| `/api/v1/cspm` | cspm | Cloud posture findings |
| `/api/v1/tickets` | tickets | Ticketing integration |
| `/api/v1/tenant` | tenant | Tenant and user management |
| `/dev` | dev_routes | Seed data (development only) |
| `/health` | main | Health check |

---

## Authentication (`/auth`)

### `GET /auth/login/{provider}`
Initiates SSO login flow for the given OIDC provider.

- **Path params:** `provider` — `google` or `azure`
- **Returns:** `{ authorization_url, state }`
- **Auth:** None

### `GET /auth/callback/{provider}`
OAuth 2.0 callback endpoint. Exchanges authorization code for tokens.

- **Query params:** `code`, `state`
- **Returns:** `{ access_token, refresh_token, token_type, user }`
- **Auth:** None

### `POST /auth/refresh`
Refreshes an expired access token.

- **Body:** `{ refresh_token }`
- **Returns:** `{ access_token, token_type }`
- **Auth:** Valid refresh token

### `GET /auth/me`
Returns the currently authenticated user's profile.

- **Returns:** `{ id, email, display_name, role, tenant_id, avatar_url }`
- **Auth:** Bearer token

### `POST /auth/logout`
Client-side logout (optional server-side token blocklist via Redis).

- **Auth:** Bearer token

---

## Vulnerabilities (`/api/v1/vulnerabilities`)

### `GET /`
List vulnerabilities with filtering and pagination.

- **Query params:**
  - `page` (default 1), `page_size` (default 50, max 200)
  - `severity` — CRITICAL, HIGH, MEDIUM, LOW, INFO
  - `source` — CROWDSTRIKE, NESSUS, DEFENDER, WIZ
  - `status` — OPEN, IN_PROGRESS, REMEDIATED, SUPPRESSED, FALSE_POSITIVE
  - `cve_id` — exact CVE match
  - `exploit_available` — boolean
  - `cisa_kev` — boolean
  - `asset_id` — filter by asset UUID
  - `search` — partial match on CVE ID or product
  - `age_days_min`, `age_days_max` — filter by age
- **Returns:** `PaginatedResponse<VulnerabilitySummary>`
- **Auth:** Viewer+

### `GET /stats`
Dashboard statistics.

- **Returns:**
  ```json
  {
    "total": 1500,
    "open": 1200,
    "by_severity": { "CRITICAL": 50, "HIGH": 200, ... },
    "by_source": { "CROWDSTRIKE": 500, ... },
    "exploitable": 80,
    "cisa_kev": 30,
    "correlated": 120,
    "mttr_days": 12.5
  }
  ```
- **Auth:** Viewer+

### `GET /{id}`
Single vulnerability detail.

- **Returns:** Full vulnerability object with all fields
- **Auth:** Viewer+

### `PATCH /{id}/status`
Update vulnerability status.

- **Body:** `{ status: "REMEDIATED" }`
- **Side effect:** Sets `remediated_at` if status is REMEDIATED
- **Auth:** Analyst+

### `PUT /`
Bulk status update (max 500 vulnerabilities).

- **Body:** `{ vulnerability_ids: [...], status: "SUPPRESSED" }`
- **Auth:** Analyst+

### `GET /remediations/grouped`
Group vulnerabilities by remediation action.

- **Query params:** Same filters as list endpoint
- **Returns:** List of grouped remediations:
  ```json
  [
    {
      "remediation_id": "rem-123",
      "remediation_action": "Update OpenSSL to 3.1.5",
      "affected_product": "OpenSSL",
      "affected_host_count": 15,
      "vulnerability_count": 45,
      "max_severity": "CRITICAL"
    }
  ]
  ```
- **Auth:** Viewer+

### `GET /remediations/{remediation_id}/hosts`
Drill-down: hosts affected by a specific remediation.

- **Returns:** List of assets with vuln counts for this remediation
- **Auth:** Viewer+

### `GET /hosts/{asset_id}/remediations`
Drill-down: remediations available for a specific host.

- **Returns:** List of remediations with exploit/KEV info
- **Auth:** Viewer+

---

## Assets (`/api/v1/assets`)

### `GET /`
List assets with filtering and pagination.

- **Query params:**
  - `page`, `page_size`
  - `search` — hostname partial match
  - `device_category` — WORKSTATION, SERVER, NETWORK, MOBILE, OTHER
  - `min_risk_score` — minimum risk score (0–100)
- **Returns:** `PaginatedResponse<AssetSummary>`
- **Auth:** Viewer+

### `GET /stats`
Asset statistics.

- **Returns:**
  ```json
  {
    "total": 500,
    "avg_risk_score": 45.2,
    "by_category": { "WORKSTATION": 200, "SERVER": 150, ... },
    "by_os": { "Windows": 250, "macOS": 150, ... },
    "by_risk_range": { "critical": 50, "high": 100, ... },
    "scanner_coverage": { "CROWDSTRIKE": 400, "NESSUS": 300, ... }
  }
  ```
- **Auth:** Viewer+

### `GET /{id}`
Single asset detail with vulnerability breakdown.

- **Returns:** Asset object + vulnerability stats:
  ```json
  {
    "...asset fields...",
    "vuln_stats": {
      "open": 25,
      "critical": 5,
      "high": 10,
      "exploitable": 3,
      "cisa_kev": 1
    }
  }
  ```
- **Auth:** Viewer+

### `POST /classify`
Trigger bulk device classification for all unclassified assets.

- **Auth:** Admin+

---

## Connectors (`/api/v1/connectors`)

### `GET /types`
Returns metadata for all supported connector types (name, description, required fields, permissions, setup URLs).

- **Auth:** Admin+

### `GET /`
List all connectors for the tenant.

- **Returns:** List of connector configs (credentials masked)
- **Auth:** Admin+

### `POST /`
Create a new connector.

- **Body:** `{ connector_type, credentials: {...}, config: {...} }`
- **Side effect:** Credentials encrypted with Fernet before storage
- **Auth:** Admin+

### `PATCH /{id}`
Update connector config or credentials.

- **Auth:** Admin+

### `DELETE /{id}`
Delete a connector.

- **Auth:** Admin+

### `POST /test`
Test connector credentials without saving.

- **Body:** `{ connector_type, credentials: {...}, config: {...} }`
- **Returns:** `{ success, message, scope_checks: [...] }`
- **Auth:** Admin+

### `POST /{id}/sync`
Trigger immediate background sync for a connector.

- **Auth:** Admin+

### `GET /{id}/sync-status`
Get current sync status and last run info.

- **Returns:** `{ is_running, last_sync_at, last_sync_status, last_sync_record_count }`
- **Auth:** Admin+

---

## CSPM (`/api/v1/cspm`)

### `GET /`
List cloud misconfigurations with filters.

- **Query params:** `severity`, `category`, `source`, `framework`, `resource_type`, `status`, `search`
- **Auth:** Viewer+

### `GET /stats`
CSPM summary statistics.

- **Auth:** Viewer+

### `GET /{id}`
Single misconfiguration detail.

- **Auth:** Viewer+

### `PATCH /{id}/status`
Update misconfiguration status.

- **Auth:** Analyst+

---

## Services Layer

### VulnerabilityService (`vulnerabilities/service.py`)
- `_apply_filters()` — builds SQLAlchemy WHERE clauses from filter params
- `list_vulnerabilities()` — paginated query, severity-sorted, joins with Assets for hostname
- `get_vulnerability()` — single detail with all fields
- `update_vulnerability_status()` — status update + `remediated_at` tracking
- `bulk_update_status()` — batch update up to 500 records
- `get_dashboard_stats()` — aggregated metrics including MTTR calculation

### RemediationService (`vulnerabilities/remediation_service.py`)
- `get_grouped_remediations()` — groups vulns by `remediation_id`, aggregates host/vuln counts
- `get_hosts_for_remediation()` — lists assets affected by a remediation
- `get_remediations_for_host()` — lists remediations for an asset with exploit/KEV info

### AssetService (`assets/service.py`)
- `list_assets()` — paginated query with search, category, and risk score filters
- `get_asset()` — detail with per-severity vulnerability counts
- `classify_all_assets()` — bulk classification for unclassified assets

### ConnectorService (`connectors/service.py`)
- `create_connector()` — encrypt credentials, store config
- `list_connectors()` — list for tenant
- `get_decrypted_credentials()` — decrypt for sync use
- `update_connector()` / `delete_connector()`

### SyncOrchestrator (`connectors/sync.py`)
- `run_sync()` — main entry: authenticate → fetch → upsert → log
- `_upsert_asset()` — get-or-create by hostname
- `_upsert_vulnerability()` — get-or-create by unique constraint
- `_upsert_misconfiguration()` — get-or-create by unique constraint

## Shared Utilities

### Pagination (`pagination.py`)
- `PaginationParams` — page (default 1), page_size (default 50, max 200)
- `PaginatedResponse[T]` — generic paginated response with items, total, page info

### Encryption (`encryption.py`)
- `encrypt_value(plaintext)` → Fernet-encrypted string
- `decrypt_value(ciphertext)` → original plaintext
- Key from `ENCRYPTION_KEY` environment variable

### Config (`config.py`)
- Pydantic BaseSettings loading from `.env`
- All application configuration in one place
