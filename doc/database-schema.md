# Database Schema

GetVul uses PostgreSQL 16 with SQLAlchemy 2.0 (async). Migrations are managed by Alembic.

## Entity Relationship Diagram

```
┌──────────────┐     ┌──────────────┐     ┌────────────────────────┐
│   tenants    │────<│    users      │     │   connector_configs    │
│              │     │              │     │                        │
│ id (PK)      │     │ id (PK)      │     │ id (PK)                │
│ name         │     │ tenant_id(FK)│────>│ tenant_id (FK)         │
│ slug (UQ)    │     │ email        │     │ connector_type         │
│ domain       │     │ role         │     │ credentials_secret_arn │
│ idp_provider │     │ ...          │     │ sync_interval_minutes  │
│ ...          │     └──────────────┘     │ ...                    │
└──────┬───────┘                          └───────────┬────────────┘
       │                                              │
       │  ┌──────────────┐                  ┌─────────▼──────────┐
       ├─<│   assets      │                  │    sync_logs       │
       │  │              │                  │                    │
       │  │ id (PK)      │                  │ id (PK)            │
       │  │ tenant_id(FK)│                  │ connector_id (FK)  │
       │  │ hostname (UQ)│                  │ status             │
       │  │ ip_addresses │                  │ records_fetched    │
       │  │ os_name      │                  │ ...                │
       │  │ device_category│                 └────────────────────┘
       │  │ risk_score   │
       │  │ ...          │
       │  └──────┬───────┘
       │         │
       │  ┌──────▼──────────────────────┐   ┌──────────────────────────────┐
       ├─<│   vulnerabilities           │──>│  vulnerability_correlations  │
       │  │                             │   │                              │
       │  │ id (PK)                     │   │ id (PK)                      │
       │  │ tenant_id (FK)              │   │ tenant_id (FK)               │
       │  │ asset_id (FK → assets)      │   │ cve_id                       │
       │  │ cve_id                      │   │ asset_id (FK)                │
       │  │ severity                    │   │ crowdstrike_vuln_id          │
       │  │ source                      │   │ nessus_vuln_id               │
       │  │ status                      │   │ defender_vuln_id             │
       │  │ remediation_id              │   │ wiz_vuln_id                  │
       │  │ ...                         │   │ sources_count                │
       │  └──────┬──────────────────────┘   │ confidence                   │
       │         │                          └──────────────────────────────┘
       │  ┌──────▼───────────┐
       ├─<│   tickets        │
       │  │                  │
       │  │ id (PK)          │
       │  │ tenant_id (FK)   │
       │  │ vulnerability_id │
       │  │ provider         │
       │  │ external_ticket_id│
       │  │ ...              │
       │  └──────────────────┘
       │
       │  ┌──────────────────────┐
       ├─<│  misconfigurations   │
       │  │                      │
       │  │ id (PK)              │
       │  │ tenant_id (FK)       │
       │  │ rule_id              │
       │  │ resource_id          │
       │  │ severity             │
       │  │ category             │
       │  │ ...                  │
       │  └──────────────────────┘
       │
       │  ┌──────────────────┐
       └─<│  ticket_rules    │
          │                  │
          │ id (PK)          │
          │ tenant_id (FK)   │
          │ name             │
          │ conditions (JSON)│
          │ action (JSON)    │
          └──────────────────┘
```

## Tables

### tenants

Multi-tenant organization support.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, auto-gen | Unique tenant identifier |
| name | VARCHAR | NOT NULL | Organization name |
| slug | VARCHAR | UNIQUE, NOT NULL | URL-safe identifier |
| domain | VARCHAR | | Email domain for SSO mapping |
| idp_provider | VARCHAR | | Identity provider (google, azure) |
| idp_tenant_id | VARCHAR | | Provider-specific tenant ID |
| session_timeout_minutes | INTEGER | DEFAULT 30 | Session timeout |
| is_active | BOOLEAN | DEFAULT true | Tenant active status |
| created_at | TIMESTAMP | server default | |
| updated_at | TIMESTAMP | auto-update | |

### users

Application users, each belonging to one tenant.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK → tenants | |
| email | VARCHAR | NOT NULL | |
| display_name | VARCHAR | | |
| avatar_url | VARCHAR | | |
| role | ENUM | NOT NULL | OWNER, ADMIN, ANALYST, VIEWER |
| is_active | BOOLEAN | DEFAULT true | |
| idp_subject | VARCHAR | | SSO provider subject ID |
| last_login_at | TIMESTAMP | | |
| created_at | TIMESTAMP | | |
| updated_at | TIMESTAMP | | |

**Unique constraint:** `(tenant_id, email)`

### assets

Devices and cloud resources discovered by scanners.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK → tenants | |
| hostname | VARCHAR | NOT NULL | Primary identifier |
| ip_addresses | JSONB | | List of IPs `["10.0.0.1"]` |
| mac_addresses | JSONB | | List of MACs |
| os_name | VARCHAR | | Operating system name |
| os_version | VARCHAR | | OS version |
| asset_type | VARCHAR | | General type |
| cloud_provider | VARCHAR | | AWS, Azure, GCP |
| cloud_resource_id | VARCHAR | | Cloud resource ARN/ID |
| seen_by_sources | JSONB | | `["CROWDSTRIKE", "NESSUS"]` |
| crowdstrike_aid | VARCHAR | | CrowdStrike Agent ID |
| defender_device_id | VARCHAR | | Defender device ID |
| wiz_asset_id | VARCHAR | | Wiz asset identifier |
| nessus_host_id | VARCHAR | | Nessus host identifier |
| device_category | ENUM | | WORKSTATION, SERVER, NETWORK, MOBILE, OTHER |
| risk_score | INTEGER | | 0–100 risk score |
| **Jamf MDM Fields** | | | |
| jamf_id | VARCHAR | | Jamf computer ID |
| serial_number | VARCHAR | | Device serial number |
| model | VARCHAR | | Hardware model |
| department | VARCHAR | | Assigned department |
| building | VARCHAR | | Building location |
| assigned_user | VARCHAR | | User assigned in Jamf |
| managed_by | VARCHAR | | Management system |
| last_checkin_at | TIMESTAMP | | Last MDM check-in |
| mdm_details | JSONB | | Extra MDM metadata |
| created_at | TIMESTAMP | | |
| updated_at | TIMESTAMP | | |

**Unique constraint:** `(tenant_id, hostname)`

### vulnerabilities

Normalized vulnerability findings from any scanner source.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK → tenants | |
| cve_id | VARCHAR | | CVE identifier (e.g., CVE-2024-3094) |
| vulnerability_name | VARCHAR | | Human-readable name |
| cvss_v3_score | NUMERIC(3,1) | | CVSS v3 base score (0.0–10.0) |
| cvss_v3_vector | VARCHAR | | CVSS vector string |
| severity | ENUM | NOT NULL | CRITICAL, HIGH, MEDIUM, LOW, INFO |
| epss_score | FLOAT | | Exploit Prediction Scoring (0.0–1.0) |
| exploit_available | BOOLEAN | DEFAULT false | Known exploit exists |
| cisa_kev | BOOLEAN | DEFAULT false | In CISA KEV catalog |
| asset_id | UUID | FK → assets (SET NULL) | Affected asset |
| source | ENUM | NOT NULL | CROWDSTRIKE, NESSUS, DEFENDER, WIZ |
| source_vuln_id | VARCHAR | | Vendor-specific vulnerability ID |
| source_scan_id | VARCHAR | | Vendor scan/batch ID |
| remediation_id | VARCHAR | | Vendor remediation identifier |
| remediation_action | TEXT | | Remediation description |
| remediation_info | TEXT | | Additional remediation details |
| exploit_status_id | INTEGER | | Exploit status code (CrowdStrike) |
| exploit_status_name | VARCHAR | | Exploit status label |
| affected_product | VARCHAR | | Affected software name |
| affected_version | VARCHAR | | Affected version |
| fixed_version | VARCHAR | | Version with the fix |
| status | ENUM | DEFAULT 'OPEN' | OPEN, IN_PROGRESS, REMEDIATED, SUPPRESSED, FALSE_POSITIVE |
| first_detected_at | TIMESTAMP | | When first seen |
| last_seen_at | TIMESTAMP | | Most recent detection |
| remediated_at | TIMESTAMP | | When marked remediated |
| created_at | TIMESTAMP | | |
| updated_at | TIMESTAMP | | |

**Unique constraint:** `(tenant_id, cve_id, asset_id, source)` — prevents duplicate entries from the same source for the same CVE on the same asset.

### vulnerability_correlations

Links the same CVE across multiple scanner sources for the same asset.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK → tenants | |
| cve_id | VARCHAR | NOT NULL | Common CVE identifier |
| asset_id | UUID | FK → assets | Target asset |
| crowdstrike_vuln_id | UUID | FK → vulnerabilities | |
| nessus_vuln_id | UUID | FK → vulnerabilities | |
| defender_vuln_id | UUID | FK → vulnerabilities | |
| wiz_vuln_id | UUID | FK → vulnerabilities | |
| sources_count | INTEGER | | Number of sources detecting this CVE |
| confidence | ENUM | | HIGH (3+ sources), MEDIUM (2), LOW (1) |
| created_at | TIMESTAMP | | |
| updated_at | TIMESTAMP | | |

**Unique constraint:** `(tenant_id, cve_id, asset_id)`

### misconfigurations

Cloud Security Posture Management (CSPM) findings.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK → tenants | |
| rule_id | VARCHAR | NOT NULL | Policy rule identifier |
| rule_name | VARCHAR | | Rule display name |
| rule_description | TEXT | | What the rule checks |
| category | ENUM | | IAM, NETWORK, ENCRYPTION, LOGGING, STORAGE, COMPUTE, DATABASE, OTHER |
| severity | ENUM | NOT NULL | CRITICAL, HIGH, MEDIUM, LOW, INFO |
| frameworks | JSONB | | `["CIS AWS 1.5", "SOC 2"]` |
| resource_id | VARCHAR | NOT NULL | Cloud resource ARN/ID |
| resource_name | VARCHAR | | Friendly resource name |
| resource_type | VARCHAR | | Resource type (e.g., S3 Bucket) |
| resource_region | VARCHAR | | Cloud region |
| cloud_provider | VARCHAR | | AWS, Azure, GCP |
| cloud_account_id | VARCHAR | | Account/subscription ID |
| cloud_account_name | VARCHAR | | Account display name |
| source | ENUM | NOT NULL | WIZ, DEFENDER, etc. |
| source_finding_id | VARCHAR | | Vendor finding ID |
| remediation_info | TEXT | | Remediation guidance |
| remediation_url | VARCHAR | | Link to remediation docs |
| status | ENUM | DEFAULT 'OPEN' | OPEN, IN_PROGRESS, REMEDIATED, SUPPRESSED, FALSE_POSITIVE |
| details | JSONB | | Source-specific extra data |
| first_detected_at | TIMESTAMP | | |
| last_seen_at | TIMESTAMP | | |
| remediated_at | TIMESTAMP | | |
| created_at | TIMESTAMP | | |
| updated_at | TIMESTAMP | | |

**Unique constraint:** `(tenant_id, rule_id, resource_id, source)`

### connector_configs

Configuration for each external data source connector.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK → tenants | |
| connector_type | ENUM | NOT NULL | CROWDSTRIKE, NESSUS, DEFENDER, WIZ, JAMF |
| is_enabled | BOOLEAN | DEFAULT true | Whether sync is active |
| credentials_secret_arn | TEXT | | Fernet-encrypted credentials JSON |
| config | JSONB | | Base URL, custom settings |
| sync_interval_minutes | INTEGER | DEFAULT 15 | Sync frequency |
| last_sync_at | TIMESTAMP | | Last sync timestamp |
| last_sync_status | VARCHAR | | SUCCESS, FAILED, PARTIAL |
| last_sync_record_count | INTEGER | | Records from last sync |
| created_at | TIMESTAMP | | |
| updated_at | TIMESTAMP | | |

**Unique constraint:** `(tenant_id, connector_type)` — one connector per type per tenant.

### sync_logs

Audit trail for all connector synchronization runs.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| connector_id | UUID | FK → connector_configs | |
| tenant_id | UUID | FK → tenants | |
| status | ENUM | NOT NULL | RUNNING, SUCCESS, FAILED, PARTIAL |
| started_at | TIMESTAMP | NOT NULL | |
| finished_at | TIMESTAMP | | |
| records_fetched | INTEGER | | Total fetched from source |
| records_created | INTEGER | | New records inserted |
| records_updated | INTEGER | | Existing records updated |
| error_message | TEXT | | Error details if failed |
| details | JSONB | | Extra metadata |

### tickets

Links vulnerabilities to external ticketing systems.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK → tenants | |
| vulnerability_id | UUID | FK → vulnerabilities | |
| provider | ENUM | NOT NULL | JIRA, GITHUB |
| external_ticket_id | VARCHAR | NOT NULL | Ticket ID in external system |
| external_ticket_url | VARCHAR | | Link to ticket |
| external_status | VARCHAR | | Status in external system |
| project_key | VARCHAR | | Jira project key |
| assignee | VARCHAR | | Assigned person |
| created_by_user_id | UUID | | User who created |
| created_by_rule | UUID | | Auto-creation rule |
| detected_at | TIMESTAMP | | When vuln was detected |
| ticket_created_at | TIMESTAMP | | When ticket was created |
| resolved_at | TIMESTAMP | | When ticket was resolved |
| created_at | TIMESTAMP | | |
| updated_at | TIMESTAMP | | |

**Unique constraint:** `(tenant_id, external_ticket_id, provider)`

### ticket_rules

Automated rules for ticket creation.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK → tenants | |
| name | VARCHAR | NOT NULL | Rule name |
| is_enabled | BOOLEAN | DEFAULT true | |
| conditions | JSONB | NOT NULL | Filter criteria (severity, source, etc.) |
| action | JSONB | NOT NULL | Ticket template, fields, project, assignee |
| created_at | TIMESTAMP | | |
| updated_at | TIMESTAMP | | |

## Migration History

| Version | Description |
|---------|-------------|
| 001 | Initial schema — all core tables |
| 002 | Add misconfigurations table (CSPM) |
| 003 | Widen credentials column for encrypted JSON |
| 004 | Add remediation_id, remediation_action, exploit status fields |
| 005 | Add device_category enum and Jamf MDM fields to assets |
