---
phase: 13-tickets-list-detail
plan: "02"
subsystem: backend/ticketing
tags: [connector-stubs, jira, github, httpx, tdd]
dependency_graph:
  requires: []
  provides:
    - backend/app/ticketing/jira_client.py
    - backend/app/ticketing/github_client.py
    - backend/tests/test_provider_stubs.py
  affects:
    - backend/app/ticketing/service.py (Plan 03 will consume JiraClient/GitHubClient)
tech_stack:
  added: []
  patterns:
    - httpx.AsyncClient with BasicAuth (Jira) and Bearer token (GitHub)
    - httpx.MockTransport injected via monkeypatch for unit tests
    - structlog structured logging — status/url only, token never logged
    - asyncio.sleep(Retry-After) on HTTP 429, retry-once pattern
key_files:
  created:
    - backend/app/ticketing/jira_client.py
    - backend/app/ticketing/github_client.py
    - backend/tests/test_provider_stubs.py
  modified: []
decisions:
  - "Used httpx.MockTransport injected by patching _client._transport — no respx or pytest-httpx dep required"
  - "JiraIssue.status set to empty string on create (create endpoint does not return status); caller uses get_issue for read-back"
  - "get_watchers() stub returns [] with docstring citing D-W-01 — GitHub notifications API is not per-issue, local ticket_watchers table is the watcher source"
metrics:
  duration: "7m"
  completed: "2026-06-01"
  tasks_completed: 3
  tasks_total: 3
  files_created: 3
  files_modified: 0
---

# Phase 13 Plan 02: Jira + GitHub Connector Stubs Summary

**One-liner:** Jira Cloud REST v3 stub with Basic auth + ADF descriptions and GitHub Issues stub with Bearer token, both unit-tested against mocked httpx transports with zero network calls.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | jira_client.py — Jira Cloud REST v3 stub | cbfb55b | backend/app/ticketing/jira_client.py |
| 2 | github_client.py — GitHub Issues stub | c5b8144 | backend/app/ticketing/github_client.py |
| 3 | Mocked-httpx unit tests for both stubs | 7b7e72e | backend/tests/test_provider_stubs.py |

## What Was Built

### JiraClient (`jira_client.py`)

1:1 interface clone of `asana_client.py`:
- `JiraIssue` dataclass — `id`, `key`, `url`, `summary`, `status`, `assignee`
- `__init__(email, api_token, base_url)` — `httpx.BasicAuth(email, api_token)`, api_token never logged
- `test_connection()` — `GET /rest/api/3/myself`, returns `{success, message, account_id}`
- `create_ticket(project_key, summary, description, assignee_account_id=None)` — `POST /rest/api/3/issue` with ADF-wrapped description, 201 → `JiraIssue`, failure → `None`
- `get_issue(issue_id_or_key)` — `GET /rest/api/3/issue/{id}`, returns raw dict or `None`
- 429 handling — `Retry-After` sleep + retry-once
- `close()` — `await self._client.aclose()`
- Out-of-scope methods NOT implemented: `add_comment`, `list_projects`, `update_issue`

### GitHubClient (`github_client.py`)

1:1 interface clone of `asana_client.py`, symmetric with `JiraClient`:
- `GitHubIssue` dataclass — `id`, `number`, `url`, `title`, `state`, `assignee`
- `__init__(token, owner, repo)` — Bearer token header, token never logged
- `test_connection()` — `GET /repos/{owner}/{repo}`, returns `{success, message}`
- `create_ticket(title, body)` — `POST /repos/{owner}/{repo}/issues`, 201 → `GitHubIssue`, failure → `None`
- `get_issue(number)` — `GET /repos/{owner}/{repo}/issues/{number}`, returns raw dict or `None`
- `get_watchers()` — always returns `[]` (D-W-01 documented stub; GitHub notifications are not per-issue)
- 429 handling — mirrors asana/jira pattern
- `close()` — `await self._client.aclose()`

### Tests (`test_provider_stubs.py`)

6 async tests using `httpx.MockTransport` injected at `client._client._transport`:
- **Test 1** (Jira create): 201 mock → `JiraIssue.url` ends with `/browse/GV-12`
- **Test 2** (Jira get): 200 mock → raw dict `fields.status.name == "Done"`
- **Test 3** (Jira failure): 400 mock → `create_ticket` returns `None`, no exception raised
- **Test 4** (GitHub create): 201 mock → `GitHubIssue.number == 7`, `url == html_url`
- **Test 5** (GitHub get): 200 mock → raw dict `state == "closed"`
- **Test 6** (GitHub watchers): `get_watchers()` returns `[]`

All 6 pass. No network calls.

## Threat Model Coverage

| Threat ID | Disposition | Status |
|-----------|-------------|--------|
| T-13-04 (token in logs) | mitigate | structlog calls log `status`/`url` only; `grep api_token\|token=` in log lines → 0 |
| T-13-05 (tokens at rest) | transfer | Clients receive already-decrypted secrets from `get_decrypted_credentials()` — Plan 03 injects |
| T-13-06 (SSRF via user-supplied base_url) | accept | Admin-CLI config only in P13; documented for P14 connector UI |
| T-13-07 (DoS via 429) | mitigate | Retry-After + retry-once, no unbounded loop |

## Deviations from Plan

None — plan executed exactly as written.

The plan noted that Task 3 is TDD (`tdd="true"`). Because Tasks 1 and 2 (the units under test) were implemented first per the task ordering in the plan, the test file was written against the completed implementation and immediately reached GREEN. All 6 tests pass.

## Known Stubs

The following stubs are intentional and documented per the plan (D-PROV-02):
- `GitHubClient.get_watchers()` — returns `[]`; GitHub has no per-issue watcher primitive (D-W-01). Plan 03 watcher union uses local `ticket_watchers` table for GitHub-backed tickets.
- `JiraIssue.status` — set to `""` on `create_ticket` return (Jira's create endpoint does not return the status field; callers use `get_issue()` for read-back state).

## Self-Check: PASSED

Files created:
- `backend/app/ticketing/jira_client.py` — FOUND
- `backend/app/ticketing/github_client.py` — FOUND
- `backend/tests/test_provider_stubs.py` — FOUND

Commits:
- `cbfb55b` feat(13-02): add JiraClient stub — FOUND
- `c5b8144` feat(13-02): add GitHubClient stub — FOUND
- `7b7e72e` test(13-02): mocked-httpx unit tests — FOUND
