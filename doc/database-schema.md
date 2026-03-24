# Database Schema

GetVul uses PostgreSQL 16 with SQLAlchemy 2.0 (async). Migrations are managed by Alembic (22 migrations).

## Entity Relationship Diagram

```
┌──────────────┐     ┌──────────────┐     ┌────────────────────────┐
│   tenants    │----<│    users      │     │   connector_configs    │
│              │     │              │     │                        │
│ id (PK)      │     │ id (PK)      │     │ id (PK)                │
│ name         │     │ tenant_id(FK)│---->│ tenant_id (FK)         │
│ slug (UQ)    │     │ email        │     │ connector_type         │
│ domain       │     │ role         │     │ credentials (encrypted)│
│ idp_provider │     │ ...          │     │ sync_interval_minutes  │
│ sso_enforced │     └──────────────┘     │ ...                    │
│ timezone     │                          └───────────┬────────────┘
│ sla_policy   │                                      │
│ smtp_config  │                            ┌─────────▼──────────┐
│ syslog_config│                            │    sync_logs       │
│ ...          │                            │                    │
└──────┬───────┘                            │ id (PK)            │
       │                                    │ connector_id (FK)  │
       │  ┌──────────────┐                  │ status             │
       ├─<│   assets      │                  │ records_fetched    │
       │  │              │                  └────────────────────┘
       │  │ id (PK)      │
       │  │ hostname (UQ)│    ┌────────────────────────────────────┐
       │  │ device_category│   │   vulnerability_correlations       │
       │  │ risk_score   │   │                                    │
       │  │ ignored      │   │ id (PK)                            │
       │  │ ...          │   │ tenant_id, cve_id, asset_id        │
       │  └──────┬───────┘   │ crowdstrike/nessus/defender/wiz_id │
       │         │           │ sources_count, confidence           │
       │  ┌──────▼───────────┤───────────────────────────────────┘
       ├─<│  vulnerabilities │
       │  │                  │
       │  │ id (PK)          │     ┌──────────────────────┐
       │  │ cve_id, severity │     │   saved_filters      │
       │  │ source, status   │     │                      │
       │  │ remediation_id   │     │ id (PK)              │
       │  │ exploit_available│     │ tenant_id (FK)       │
       │  │ cisa_kev         │     │ name, conditions     │
       │  │ ...              │     └──────────────────────┘
       │  └──────┬───────────┘
       │         │             ┌──────────────────────┐
       │  ┌──────▼──────┐     │  ticket_rules         │
       ├─<│   tickets    │     │                      │
       │  │              │     │ id (PK)              │
       │  │ provider     │     │ saved_filter_id (FK) │
       │  │ external_id  │     │ conditions, action   │
       │  │ ...          │     │ schedule, max_tickets│
       │  └──────────────┘     └──────────────────────┘
       │
       │  ┌──────────────────┐  ┌──────────────────────┐
       ├─<│ misconfigurations│  │   audit_logs         │
       │  │                  │  │                      │
       │  │ rule_id          │  │ id (PK)              │
       │  │ resource_id      │  │ tenant_id (FK)       │
       │  │ severity, status │  │ user_id, action      │
       │  └──────────────────┘  │ resource_type, detail│
       │                        └──────────────────────┘
       │
       │  ┌──────────────────────┐  ┌──────────────────────┐
       ├─<│  scheduled_reports   │  │   daily_snapshots    │
       │  │                      │  │                      │
       │  │ schedule, format     │  │ tenant_id, date      │
       │  │ recipients, sections │  │ metrics (JSONB)      │
       │  └──────────────────────┘  └──────────────────────┘
       │
       │  ┌──────────────────────┐
       ├─<│   notifications      │
       │  │                      │
       │  │ title, message       │
       │  │ severity, category   │
       │  │ is_read, email_sent  │
       │  │ details (JSONB)      │
       │  └──────────────────────┘
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
| idp_provider | VARCHAR | | Identity provider (google, azure, okta) |
| idp_tenant_id | VARCHAR | | Provider-specific tenant ID |
| sso_enforced | BOOLEAN | DEFAULT false | Require SSO login |
| session_timeout_minutes | INTEGER | DEFAULT 30 | Session timeout |
| timezone | VARCHAR | DEFAULT 'UTC' | Tenant timezone |
| sla_policy | JSONB | | Per-severity SLA deadlines |
| smtp_host | VARCHAR | | SMTP server hostname |
| smtp_port | INTEGER | | SMTP port |
| smtp_username | VARCHAR | | SMTP auth username |
| smtp_password_encrypted | TEXT | | SMTP auth password (Fernet) |
| smtp_from_email | VARCHAR | | Sender email address |
| smtp_use_tls | BOOLEAN | | TLS for SMTP |
| syslog_enabled | BOOLEAN | DEFAULT false | SIEM forwarding toggle |
| syslog_host | VARCHAR | | Syslog server address |
| syslog_port | INTEGER | | Syslog server port |
| syslog_protocol | VARCHAR | | UDP or TCP |
| syslog_facility | VARCHAR | | Syslog facility |
| password_policy | JSONB | | Password complexity rules |
| is_active | BOOLEAN | DEFAULT true | Tenant active status |
| created_at | TIMESTAMP | server default | |
| updated_at | TIMESTAMP | auto-update | |

### users

Application users, each belonging to one tenant.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK -> tenants | |
| email | VARCHAR | NOT NULL | |
| display_name | VARCHAR | | |
| avatar_url | VARCHAR | | |
| role | ENUM | NOT NULL | OWNER, ADMIN, ANALYST, VIEWER |
| hashed_password | VARCHAR | | bcrypt hash |
| allow_password_login | BOOLEAN | DEFAULT false | Override SSO enforcement |
| password_history | JSONB | | Previous password hashes |
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
| tenant_id | UUID | FK -> tenants | |
| hostname | VARCHAR | NOT NULL | Primary identifier |
| ip_addresses | JSONB | | `["10.0.0.1"]` |
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
| risk_score | INTEGER | | 0-100 computed risk score |
| ignored | BOOLEAN | DEFAULT false | Excluded from remediations |
| serial_number | VARCHAR | | Device serial number |
| model | VARCHAR | | Hardware model |
| department | VARCHAR | | Assigned department |
| building | VARCHAR | | Building location |
| assigned_user | VARCHAR | | Assigned user |
| managed_by | VARCHAR | | MDM system |
| last_checkin_at | TIMESTAMP | | Last MDM check-in |
| mdm_details | JSONB | | Extra MDM metadata |
| jamf_id | VARCHAR | | Jamf computer ID |
| created_at | TIMESTAMP | | |
| updated_at | TIMESTAMP | | |

**Unique constraint:** `(tenant_id, hostname)`

### vulnerabilities

Normalized vulnerability findings from any scanner source.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK -> tenants | |
| cve_id | VARCHAR | | CVE identifier (e.g., CVE-2024-3094) |
| vulnerability_name | VARCHAR | | Human-readable name |
| cvss_v3_score | NUMERIC(3,1) | | CVSS v3 base score (0.0-10.0) |
| cvss_v3_vector | VARCHAR | | CVSS vector string |
| severity | ENUM | NOT NULL | CRITICAL, HIGH, MEDIUM, LOW, INFO |
| epss_score | FLOAT | | Exploit Prediction Scoring (0.0-1.0) |
| exploit_available | BOOLEAN | DEFAULT false | Known exploit exists |
| cisa_kev | BOOLEAN | DEFAULT false | In CISA KEV catalog |
| asset_id | UUID | FK -> assets (SET NULL) | Affected asset |
| source | ENUM | NOT NULL | CROWDSTRIKE, NESSUS, DEFENDER, WIZ, QUALYS, RAPID7 |
| source_vuln_id | VARCHAR | | Vendor-specific vulnerability ID |
| source_scan_id | VARCHAR | | Vendor scan/batch ID |
| remediation_id | VARCHAR | | Vendor remediation identifier |
| remediation_action | TEXT | | Remediation description |
| remediation_info | TEXT | | Additional remediation details |
| exploit_status_id | INTEGER | | Exploit status code |
| exploit_status_name | VARCHAR | | Exploit status label |
| affected_product | VARCHAR | | Affected software name |
| affected_version | VARCHAR | | Affected version |
| fixed_version | VARCHAR | | Version with the fix |
| file_paths | JSONB | | File paths where vulnerable software is installed |
| status | ENUM | DEFAULT 'OPEN' | OPEN, IN_PROGRESS, REMEDIATED, SUPPRESSED, FALSE_POSITIVE |
| sla_deadline | TIMESTAMP | | Computed SLA deadline |
| sla_breached | BOOLEAN | DEFAULT false | Whether SLA was breached |
| first_detected_at | TIMESTAMP | | When first seen |
| last_seen_at | TIMESTAMP | | Most recent detection |
| remediated_at | TIMESTAMP | | When marked remediated |
| created_at | TIMESTAMP | | |
| updated_at | TIMESTAMP | | |

**Unique constraint:** `(tenant_id, cve_id, asset_id, source)`

### vulnerability_correlations

Links the same CVE across multiple scanner sources for the same asset.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK -> tenants | |
| cve_id | VARCHAR | NOT NULL | Common CVE identifier |
| asset_id | UUID | FK -> assets | Target asset |
| crowdstrike_vuln_id | UUID | FK -> vulnerabilities | |
| nessus_vuln_id | UUID | FK -> vulnerabilities | |
| defender_vuln_id | UUID | FK -> vulnerabilities | |
| wiz_vuln_id | UUID | FK -> vulnerabilities | |
| sources_count | INTEGER | | Number of confirming sources |
| confidence | ENUM | | HIGH (3+), MEDIUM (2) |
| created_at | TIMESTAMP | | |
| updated_at | TIMESTAMP | | |

**Unique constraint:** `(tenant_id, cve_id, asset_id)`

### misconfigurations

Cloud Security Posture Management (CSPM) findings.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK -> tenants | |
| rule_id | VARCHAR | NOT NULL | Policy rule identifier |
| rule_name | VARCHAR | | Rule display name |
| rule_description | TEXT | | What the rule checks |
| category | ENUM | | IAM, NETWORK, ENCRYPTION, LOGGING, STORAGE, COMPUTE, DATABASE, OTHER |
| severity | ENUM | NOT NULL | CRITICAL, HIGH, MEDIUM, LOW, INFO |
| frameworks | JSONB | | `["CIS AWS 1.5", "SOC 2"]` |
| resource_id | VARCHAR | NOT NULL | Cloud resource ARN/ID |
| resource_name | VARCHAR | | Friendly resource name |
| resource_type | VARCHAR | | Resource type |
| resource_region | VARCHAR | | Cloud region |
| cloud_provider | VARCHAR | | AWS, Azure, GCP |
| cloud_account_id | VARCHAR | | Account/subscription ID |
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
| tenant_id | UUID | FK -> tenants | |
| connector_type | ENUM | NOT NULL | See 14 connector types |
| is_enabled | BOOLEAN | DEFAULT true | Whether sync is active |
| credentials_secret_arn | TEXT | | Fernet-encrypted credentials JSON |
| config | JSONB | | Base URL, custom settings |
| sync_interval_minutes | INTEGER | DEFAULT 15 | Sync frequency |
| last_sync_at | TIMESTAMP | | Last sync timestamp |
| last_sync_status | VARCHAR | | SUCCESS, FAILED, PARTIAL |
| last_sync_record_count | INTEGER | | Records from last sync |
| created_at | TIMESTAMP | | |
| updated_at | TIMESTAMP | | |

**Unique constraint:** `(tenant_id, connector_type)`

### sync_logs

Audit trail for all connector synchronization runs.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| connector_id | UUID | FK -> connector_configs | |
| tenant_id | UUID | FK -> tenants | |
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
| tenant_id | UUID | FK -> tenants | |
| vulnerability_id | UUID | FK -> vulnerabilities | |
| provider | ENUM | NOT NULL | ASANA, JIRA |
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
| tenant_id | UUID | FK -> tenants | |
| name | VARCHAR | NOT NULL | Rule name |
| is_enabled | BOOLEAN | DEFAULT true | |
| saved_filter_id | UUID | FK -> saved_filters | Linked filter |
| conditions | JSONB | NOT NULL | Filter criteria |
| action | JSONB | NOT NULL | Ticket template, assignee |
| schedule | VARCHAR | | Interval (1h, 6h, 12h, 1d, 7d) |
| max_tickets_per_run | INTEGER | | Limit per execution |
| last_run_at | TIMESTAMP | | |
| created_at | TIMESTAMP | | |
| updated_at | TIMESTAMP | | |

### saved_filters

Reusable vulnerability/asset filter presets.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK -> tenants | |
| name | VARCHAR | NOT NULL | Filter name |
| conditions | JSONB | NOT NULL | Filter criteria (severity, source, etc.) |
| created_by | UUID | FK -> users | |
| created_at | TIMESTAMP | | |
| updated_at | TIMESTAMP | | |

### audit_logs

Full audit trail of all user actions.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK -> tenants | |
| user_id | UUID | | Acting user |
| action | VARCHAR | NOT NULL | Action type (e.g., auth.login) |
| resource_type | VARCHAR | | Target resource type |
| resource_id | VARCHAR | | Target resource ID |
| detail | JSONB | | Action-specific metadata |
| ip_address | VARCHAR | | Client IP |
| created_at | TIMESTAMP | | |

### scheduled_reports

Recurring report delivery configuration.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK -> tenants | |
| name | VARCHAR(200) | NOT NULL | Report name |
| is_enabled | BOOLEAN | DEFAULT true | |
| schedule | VARCHAR(20) | NOT NULL | daily, weekly, monthly |
| format | VARCHAR(10) | DEFAULT 'pdf' | pdf, csv, txt |
| recipients | JSONB | NOT NULL | Email addresses |
| sections | JSONB | | Report sections to include |
| filters | JSONB | | Data filters |
| last_sent_at | TIMESTAMP | | |
| last_send_status | VARCHAR(20) | | |
| created_at | TIMESTAMP | | |
| updated_at | TIMESTAMP | | |

### daily_snapshots

Historical metric snapshots for trend analytics.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK -> tenants | |
| snapshot_date | DATE | NOT NULL | Date of snapshot |
| metrics | JSONB | NOT NULL | All computed metrics |
| created_at | TIMESTAMP | | |

**Unique constraint:** `(tenant_id, snapshot_date)`

### notifications

In-app and email alerts for security events.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| tenant_id | UUID | FK -> tenants | |
| user_id | UUID | FK -> users, nullable | Target user (null = broadcast to all) |
| title | VARCHAR(200) | NOT NULL | Notification title |
| message | TEXT | NOT NULL | Notification body |
| severity | VARCHAR(20) | NOT NULL, DEFAULT 'info' | critical, high, medium, low, info |
| category | VARCHAR(50) | NOT NULL | new_critical_vuln, sla_breach, sync_failure, risk_change |
| resource_type | VARCHAR(50) | | vulnerability, asset, ticket, connector |
| resource_id | VARCHAR(200) | | ID of related resource |
| is_read | BOOLEAN | DEFAULT false | Whether user has read it |
| read_at | TIMESTAMP | | When marked as read |
| email_sent | BOOLEAN | DEFAULT false | Whether email was delivered |
| email_sent_at | TIMESTAMP | | When email was sent |
| details | JSONB | DEFAULT '{}' | Extra metadata |
| created_at | TIMESTAMP | | |
| updated_at | TIMESTAMP | | |

**Indexes:**
- `(tenant_id, user_id, is_read)` -- unread notifications query
- `(tenant_id, category)` -- filter by category
- `(tenant_id, created_at)` -- chronological listing

## Migration History

| Version | Description |
|---------|-------------|
| 001 | Initial schema -- all core tables |
| 002 | Add misconfigurations table (CSPM) |
| 003 | Widen credentials column for encrypted JSON |
| 004 | Add remediation_id, remediation_action, exploit status fields |
| 005 | Add device_category enum and Jamf MDM fields to assets |
| 006 | Add CrowdStrike device fields (serial, model, login user) |
| 007 | Add ticket rule schedule and max tickets |
| 008 | Add saved_filters table |
| 009 | Link ticket rules to saved filters |
| 010 | Add vulnerability file paths (JSONB) |
| 011 | Add password authentication (hashed_password, allow_password_login) |
| 012 | Add user groups table |
| 013 | Add audit_logs table |
| 014 | Add syslog config fields to tenants |
| 015 | Add tenant timezone |
| 016 | Add password policy (JSONB on tenants) |
| 017 | Add scheduled_reports table |
| 018 | Add SMTP config fields to tenants |
| 019 | Add asset ignored flag |
| 020 | Add SLA tracking fields (sla_deadline, sla_breached, sla_policy) |
| 021 | Add daily_snapshots table |
| 022 | Add notifications table (in-app + email alerts) |
