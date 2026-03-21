# Connectors & Integrations

## Overview

GetVul supports 9 connector types across 4 categories:

| Category | Connectors |
|----------|-----------|
| **Vulnerability Scanners** | CrowdStrike Falcon, Nessus (planned), Defender (planned), Wiz (planned) |
| **Device Management** | Jamf Pro |
| **HR / Identity** | Humaans, Google Workspace, Azure Entra ID |
| **Ticketing** | Asana |

## CrowdStrike Falcon (Implemented)

**Data**: Spotlight vulnerabilities, device info, file paths, exploit status, CSPM
**Auth**: OAuth 2.0 (client_id + client_secret)
**Sync**: Per-severity queries (CRITICAL → LOW), batch device/remediation/evaluation logic resolution
**Fields synced**: CVE, severity, product, version, remediation, file paths, exploit status, CISA KEV, host details (serial, model, login user, host status)

## Jamf Pro (Implemented)

**Data**: Apple device MDM — FileVault, SIP, Gatekeeper, model, serial, user
**Auth**: OAuth 2.0 (client_id + client_secret)
**Matching**: Serial number → CrowdStrike asset, login username → CrowdStrike last_login_user, hostname fallback
**Note**: Base URL auto-strips trailing `/api` to prevent double-path issues

## Humaans (Implemented)

**Data**: HR — name, email, GitHub, LinkedIn, Element handles, teams, location, timezone
**Auth**: Bearer token (API Access Token)
**Matching**: Email local part → CrowdStrike last_login_user, preferred/first name → hostname pattern
**Custom fields**: Auto-detects "GitHub" (top-level + custom), "Element"/"Matrix" custom fields

## Asana (Implemented)

**Data**: Ticketing — create/update/close/delete tasks, add comments
**Auth**: Personal Access Token
**Config**: Workspace + Project selection via Settings UI
**Features**: Per-host tickets, per-remediation tickets, auto-assignment, SLA due dates, status sync

## Google Workspace (Implemented)

**Data**: Directory — users (name, email, department, job title) + groups with memberships
**Auth**: Admin OAuth token or Service Account with domain-wide delegation
**Scopes**: admin.directory.user.readonly, admin.directory.group.readonly, admin.directory.group.member.readonly

## Azure Entra ID (Implemented)

**Data**: Directory — users + groups via Microsoft Graph API
**Auth**: Client credentials (app registration)
**Permissions**: User.Read.All, Group.Read.All, GroupMember.Read.All (Application)

## Connector Management

### API Endpoints
| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/connectors/types` | Available connector types |
| `GET /api/v1/connectors` | List configured connectors |
| `POST /api/v1/connectors` | Create connector |
| `PATCH /api/v1/connectors/{id}` | Update credentials/config |
| `DELETE /api/v1/connectors/{id}` | Delete connector |
| `POST /api/v1/connectors/test` | Test credentials |
| `POST /api/v1/connectors/{id}/sync` | Trigger sync |
| `GET /api/v1/connectors/{id}/sync-status` | Check sync status |

### Credential Storage
- Encrypted with Fernet symmetric encryption before database storage
- Decrypted only in memory during active sync
- Never exposed in API responses

### Background Scheduler
- Checks all enabled connectors every 60 seconds
- Triggers sync based on `sync_interval_minutes` per connector
- Prevents concurrent syncs per connector
- Logs results to `sync_logs` table
