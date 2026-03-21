# Ticketing System

## Overview

GetVul integrates with Asana to create, track, and manage vulnerability remediation tickets. Tickets can be created manually, via bulk actions, or automatically through scheduled rules.

## Ticket Types

### Per-Host Tickets
One Asana task per affected host, listing all its remediations:
- Task title: `[CRITICAL] Remediate par03642 — 9 vulns (1 critical)`
- Description includes: host details, vuln summary, numbered remediation actions with CVE IDs, file paths, exploit/KEV flags
- Auto-assigned to the host's Humaans-linked user email
- Due date based on highest severity SLA

### Per-Remediation Tickets
One Asana task per remediation action, listing all affected hosts:
- Task title: `[CRITICAL] Apple Mac OS 13: Update to 26.0.1 — 2 hosts`
- Description includes: remediation action, affected hosts with per-host CVE breakdown and file paths
- Assigned to a selected user (configurable)

## Automation Rules

Rules automatically create tickets on a schedule for hosts matching filter conditions.

### Rule Configuration
- **Saved Filter** (required): links to a vulnerability/remediation filter
- **Schedule**: 1h, 6h, 12h, 1 day, 7 days
- **Max Tickets Per Run**: 5, 10, 25, 50, 100
- **Ticket Grouping**: per-host or per-remediation
- **Assignee**: auto-assign to host user (per-host) or fixed user (per-remediation)

### Rule Conditions (from saved filter)
- Severity: CRITICAL, HIGH, MEDIUM, LOW
- Source: CROWDSTRIKE, etc.
- Exploit available, CISA KEV
- Device category, min risk score

### Scheduler
- Runs every 60 seconds via APScheduler background task
- Checks all enabled rules, triggers those past their interval
- Dedup: won't create tickets for hosts/remediations that already have open tickets

## Ticket Lifecycle

1. **Create**: Manual (from asset detail or tickets page) or automated (rules)
2. **Track**: Tickets page shows grouped view with severity, vulns, assignee, status
3. **Sync**: "Sync Status from Asana" checks if tasks were completed
4. **Auto-close**: When all vulns are remediated/suppressed, task is completed automatically
5. **Progress comments**: Partial remediation posts a comment with remaining actions
6. **Close**: Manual close completes the Asana task and marks vulns as REMEDIATED
7. **Delete**: Removes from GetVul + deletes from Asana, reopens IN_PROGRESS vulns

## Bulk Actions
- Select tickets with checkboxes (+ select all)
- Close: complete Asana tasks, remediate vulns
- Comment: post a message to all selected Asana tasks
- Sync Update: check Asana for status changes
- Delete: remove from both GetVul and Asana

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/tickets` | GET | List tickets (grouped by task) |
| `/api/v1/tickets` | POST | Create tickets for vulnerabilities |
| `/api/v1/tickets/host` | POST | Create per-host ticket |
| `/api/v1/tickets/stats` | GET | Ticket statistics |
| `/api/v1/tickets/sync-status` | POST | Sync from Asana |
| `/api/v1/tickets/close` | POST | Close a ticket |
| `/api/v1/tickets/bulk-action` | POST | Bulk close/comment/delete |
| `/api/v1/tickets/rules` | GET/POST | List/create automation rules |
| `/api/v1/tickets/rules/{id}` | PATCH/DELETE | Update/delete rule |
| `/api/v1/tickets/rules/{id}/run` | POST | Run rule immediately |
| `/api/v1/tickets/assignees` | GET | List available assignees |
| `/api/v1/tickets/asana/config` | GET | Fast Asana config check |
| `/api/v1/tickets/asana/setup` | GET | Full Asana setup (workspaces/projects) |
| `/api/v1/tickets/asana/config` | PATCH | Update workspace/project selection |
