# Ticketing System

## Overview

GetVul integrates with **Asana** and **Jira** to create, track, and manage vulnerability remediation tickets. Tickets can be created manually, via bulk actions, or automatically through scheduled rules. A daily sync process checks open tickets, posts progress comments, and auto-closes resolved tickets.

## Supported Providers

| Provider | Auth | Features |
|----------|------|----------|
| Asana | Personal Access Token | Create, update, close, comment, delete tasks |
| Jira | Email + API Token | Create, update, close, comment on issues |

## Ticket Types

### Per-Host Tickets
One task per affected host, listing all its remediations:
- Task title: `[CRITICAL] Remediate server-01 -- 9 vulns (1 critical)`
- Description includes: host details, vuln summary, numbered remediation actions with CVE IDs, file paths, exploit/KEV flags
- Auto-assigned to the host's HR-linked user email
- Due date based on highest severity SLA

### Per-Remediation Tickets
One task per remediation action, listing all affected hosts:
- Task title: `[CRITICAL] Update OpenSSL to 3.1.5 -- 2 hosts`
- Description includes: remediation action, affected hosts with per-host CVE breakdown and file paths
- Assigned to a selected user (configurable)

## Automation Rules

Rules automatically create tickets on a schedule for hosts matching filter conditions.

### Rule Configuration
- **Saved Filter** (required): links to a saved vulnerability/remediation filter
- **Schedule:** 1h, 6h, 12h, 1 day, 7 days
- **Max Tickets Per Run:** 5, 10, 25, 50, 100
- **Ticket Grouping:** per-host or per-remediation
- **Assignee:** auto-assign to host user (per-host) or fixed user (per-remediation)

### Rule Conditions (from saved filter)
- Severity: CRITICAL, HIGH, MEDIUM, LOW
- Source: any configured scanner
- Exploit available, CISA KEV
- Device category, min risk score

### Scheduler
- Runs every 60 seconds via APScheduler background task
- Checks all enabled rules, triggers those past their interval
- Dedup: skips hosts/remediations that already have open tickets

## Daily Ticket Status Sync

The daily sync process runs automatically:

1. Checks all open tickets against the external provider (Asana/Jira)
2. If the external task is completed, marks vulns as REMEDIATED in GetVul
3. If partial remediation occurred, posts a progress comment with remaining actions
4. If all vulns for a ticket are resolved in GetVul, completes the external task
5. Updates `external_status` on ticket records

## Ticket Lifecycle

```
1. CREATE
   Manual (from asset detail, remediations, or tickets page)
   or Automated (via rules on schedule)
       |
2. TRACK
   Tickets page shows grouped view with severity, vuln count,
   assignee, status, SLA deadline
       |
3. SYNC
   Daily sync checks external provider for status changes
   "Sync Status" button for on-demand sync
       |
4. PROGRESS
   Partial remediation posts comment with remaining actions
       |
5. AUTO-CLOSE
   When all vulns are remediated/suppressed, external task
   is completed automatically
       |
6. CLOSE (manual)
   Completes external task and marks all vulns as REMEDIATED
       |
7. DELETE
   Removes from GetVul + deletes from external provider,
   reopens IN_PROGRESS vulns to OPEN
```

## SLA-Based Due Dates

Ticket due dates are automatically set based on the highest severity in the ticket:

| Severity | Default SLA | Description |
|----------|-------------|-------------|
| CRITICAL | 3 days | Configurable per tenant |
| HIGH | 14 days | Configurable per tenant |
| MEDIUM | 30 days | Configurable per tenant |
| LOW | 90 days | Configurable per tenant |

SLA deadlines are configurable in Settings under SLA Policy.

## Bulk Actions

Select tickets with checkboxes (+ select all):
- **Close:** Complete external tasks, mark vulns as REMEDIATED
- **Comment:** Post a message to all selected external tasks
- **Sync Update:** Check external provider for status changes
- **Delete:** Remove from both GetVul and external provider

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/tickets` | GET | List tickets (grouped by task) |
| `/api/v1/tickets` | POST | Create tickets for vulnerabilities |
| `/api/v1/tickets/host` | POST | Create per-host ticket |
| `/api/v1/tickets/stats` | GET | Ticket statistics |
| `/api/v1/tickets/assignees` | GET | List available assignees |
| `/api/v1/tickets/sync-status` | POST | Sync from external provider |
| `/api/v1/tickets/close` | POST | Close a ticket |
| `/api/v1/tickets/bulk-action` | POST | Bulk close/comment/sync/delete |
| `/api/v1/tickets/asana/config` | GET | Fast Asana config check |
| `/api/v1/tickets/asana/setup` | GET | Full Asana setup (workspaces/projects) |
| `/api/v1/tickets/asana/config` | PATCH | Update workspace/project selection |
| `/api/v1/tickets/rules` | GET | List automation rules |
| `/api/v1/tickets/rules` | POST | Create automation rule |
| `/api/v1/tickets/rules/{id}` | PATCH | Update rule |
| `/api/v1/tickets/rules/{id}` | DELETE | Delete rule |
| `/api/v1/tickets/rules/{id}/run` | POST | Run rule immediately |
