# GetVul — Project Overview

## What is GetVul?

GetVul is a **unified vulnerability aggregation platform** that collects vulnerability and cloud security data from multiple enterprise security tools, normalizes it into a single database, and enables teams to take action through ticketing integrations.

## Problem Statement

Enterprise security teams typically run multiple vulnerability scanners and cloud security tools (CrowdStrike, Nessus, Defender, Wiz, etc.). Each tool has its own dashboard, data format, and severity rating. This fragmentation makes it difficult to:

- Get a unified view of organizational risk
- Correlate findings across tools (same CVE detected by multiple scanners)
- Prioritize remediation effectively
- Track remediation progress across tools
- Report on overall security posture

## Solution

GetVul provides a **single pane of glass** by:

1. **Aggregating** vulnerability data from multiple sources via connector integrations
2. **Normalizing** findings into a common schema (CVE, severity, asset, status)
3. **Correlating** duplicate findings across scanners for higher confidence
4. **Enriching** with exploit intelligence (EPSS scores, CISA KEV, exploit availability)
5. **Organizing** remediations by grouping vulnerabilities that share the same fix
6. **Automating** ticket creation in Jira/GitHub for remediation workflows

## Key Features

### Unified Vulnerability Dashboard
- Single view for vulnerabilities from 4+ security tools
- Real-time background sync from security tools (configurable interval, default 15 min)
- Cross-source correlation (same CVE detected by multiple scanners)
- Severity aggregation with CVSS v3 scoring
- Exploit availability and CISA KEV enrichment

### Asset Intelligence
- Automatic device classification (workstation, server, network, mobile)
- Multi-source asset identification (CrowdStrike AID, Defender device ID, Nessus host ID, Wiz asset ID)
- Per-asset vulnerability impact summary
- MDM enrichment via Jamf for Apple devices
- Risk scoring (0–100)

### Intelligent Remediations
- Group vulnerabilities by remediation action
- Drill-down to affected hosts per remediation
- Show all available remediations for a given host
- Track remediation progress over time

### Cloud Security Posture Management (CSPM)
- Aggregate misconfigurations from cloud security tools
- Categorize by compliance framework (CIS, SOC 2, PCI-DSS, etc.)
- Map findings to specific cloud resources
- Remediation guidance per finding

### Multi-Tenant Support
- Full tenant isolation via `tenant_id` on all records
- Domain-based SSO mapping (email domain → tenant)
- Role-based access control with 4 roles (Owner, Admin, Analyst, Viewer)
- Per-tenant connector configuration

### Ticketing Automation
- Rules-based ticket creation from vulnerabilities
- Supports Jira Cloud and GitHub Issues
- Bidirectional status sync with external ticketing systems

## Supported Data Sources

| Source | Type | Data Collected |
|--------|------|---------------|
| CrowdStrike Falcon | EDR + Spotlight | Vulnerabilities, exploit status, device info, remediation guidance |
| Nessus Professional | Vulnerability scanner | Scan results, plugin vulnerabilities, affected systems |
| Microsoft Defender | Endpoint security | Machines, vulnerabilities, security recommendations |
| Wiz | Cloud security (CSPM) | Cloud vulnerabilities, misconfigurations, resource inventory |
| Jamf Pro | Apple MDM | Computer inventory, user assignments, device details |

## Supported Ticketing Systems

| System | Integration |
|--------|------------|
| Jira Cloud | REST API v3 — create/update issues with CVE details |
| GitHub Issues | GitHub API — create issues with labels and assignees |
