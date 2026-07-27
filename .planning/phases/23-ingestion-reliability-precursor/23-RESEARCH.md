# Phase 23: Ingestion Reliability Precursor - Research

**Researched:** 2026-07-27
**Domain:** Backend connector/ticketing reliability (bug fixes + test coverage + provider dispatch) + Connectors-UI health surface. Augmenting existing code, not greenfield.
**Confidence:** HIGH (every claim below is `[VERIFIED: codebase]` via direct file reads / `grep` / a live Python REPL run against `backend/.venv`, not training-data recall)

## Summary

This phase closes six concrete, already-diagnosed gaps (REL-01..06) against a mature, ~30-migration-deep codebase. Every bug named in `23-CONTEXT.md` was independently reproduced or confirmed by reading the actual source in this session — there are no surprises on the "is the bug real" axis. The surprises are in **scope**: three defects exist that CONTEXT.md's decisions don't fully cover, and one design assumption (D-19's redaction reuse) needs a small correction. All are documented below with exact locations so the planner can decide whether to fold them into Phase 23 or explicitly defer them.

The single highest-value finding: **the ticket-create/dispatch problem is worse than "Asana-hardcoded."** It's not just that `AsanaClient` is hardcoded at the router/rule-engine layer — the backend *already accepts* `provider: "JIRA"` or `"GITHUB"` in the create-ticket request schema (regex-validated), and the frontend *already types* `CreateTicketRequest.provider` as the full `'ASANA'|'JIRA'|'GITHUB'` union — but today, submitting `provider: "JIRA"` silently creates the ticket **in Asana** anyway (the service functions always call `asana_client.create_task(...)` regardless of the `provider` string) while writing `Ticket.provider = "JIRA"` to the database. That's a live data-integrity bug, not just an unimplemented feature, and D-06/D-07's provider-dispatch protocol is the fix.

The second-highest-value finding: **the Connectors UI health-surface component (`SyncStatusPill`) never renders `SUCCESS`/`FAILED` correctly.** The frontend type and the component's internal lookup table both use lowercase words `'ok'|'syncing'|'failed'`, but the backend has never emitted those values — `sync.py` (and every sync module) writes `"SUCCESS"` / `"FAILED"` to `ConnectorConfig.last_sync_status`, passed through to the API response with zero transformation. `STATUS_CONFIG['SUCCESS']` is `undefined`, so destructuring it throws at render time. The only unit test that exists hardcodes the (wrong) value `'ok'` directly into its mock connector — it has never exercised the real backend value. REL-06 cannot "reuse `SyncStatusPill`" as CONTEXT.md's D-16 assumes without first fixing this status-value mapping; this is Wave-0-shaped work for whichever plan owns REL-06.

**Primary recommendation:** Treat REL-03 as pure **augmentation** (an entire parallel unit-test suite already exists at `backend/tests/test_connector_normalization.py`, covering pure normalization logic for all six scanners — the empty `backend/tests/test_connectors/` directory is for the *new*, HTTP-layer/pagination tests this phase adds, not a green field). Fix the two connector bugs and the status-mapping bug first (small, mechanical, unblocks everything downstream), then build the provider-dispatch protocol once and thread it through all three create paths + rule engine + router + daily_sync in one pass, using the `httpx.MockTransport` pattern already established in six other test files verbatim.

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Wiz `authenticate()` must return `bool` (`True` on success) to satisfy `BaseConnector.authenticate() -> bool`. Today it is typed `-> None` and has no `return` statement at all — a successful auth returns `None` (falsy), so the sync harness treats it as failure. Fix the return-type wiring end-to-end (method body + any call site checking the result).
- **D-02:** Rapid7 gets a real `async def authenticate(self, credentials, config) -> bool` and a **no-arg `__init__`** to match the harness's no-arg instantiation pattern. Today Rapid7 takes `config` in `__init__` and has no `authenticate()` at all, so the harness fails to even construct it. Move credential/base_url capture out of `__init__` into `authenticate()`.
- **D-03:** Acceptance bar for "full sync end-to-end" (REL-01/02) is a **CI-runnable `httpx.MockTransport` integration test** (authenticate → paginate → `fetch_vulnerabilities` → normalized records), no live credentials. This same test doubles as REL-03 coverage.
- **D-04:** Harness is **`httpx.MockTransport`** — matches six existing test files. Do NOT introduce `respx` / `pytest-httpx`. Tests live in `backend/tests/test_connectors/` (currently empty except `__init__.py`).
- **D-05:** Per connector assert: (1) auth success **and** failure, (2) multi-page pagination followed to completion, (3) `fetch_vulnerabilities` maps a fixture response field-for-field into `NormalizedVulnerability`.
- **D-06:** Build a **provider-dispatch protocol** — one ticketing-client interface (create/get/close/comment) that `AsanaClient`, `JiraClient`, `GitHubClient` all satisfy; service + rule engine pick the impl by `provider`. Replaces the current Asana-hardcoded call sites.
- **D-07:** Dispatch covers **all three create paths** — `create_tickets`, `create_host_ticket`, `create_remediation_ticket`.
- **D-08:** Consolidate to one canonical `JiraClient` under `app/ticketing/` (create+get+close+comment). Delete `app/connectors/jira_client.py`, repoint `daily_sync`'s import.
- **D-09:** Rule engine honors per-rule `provider` via dispatch; default stays `ASANA` for back-compat.
- **D-10:** Generalize router's `_get_asana_client` into `_get_ticketing_client(provider)`.
- **D-11:** Wire the already-built `GitHubClient` into create path + `daily_sync` + rule engine; expose `GITHUB` as a create provider in the UI.
- **D-12:** GitHub sync-back = inbound state map + auto-close parity (mirrors Asana's `sync_ticket_status`). `get_watchers()` stays a `[]` stub.
- **D-13:** GitHub connector-config: `connector_type=GITHUB`, fields token/owner/repo, Fernet-encrypted.
- **D-14:** Extend drill-panel create affordance into a provider picker (Asana/Jira/GitHub), filtered to configured+enabled.
- **D-15:** Picker's "configured providers" list from a backend endpoint (not client-side derivation), reused by Phase 27.
- **D-16:** Last-error, inline-on-failure — one-line severity-colored summary only when `last_sync_status` is failed, expand for full message + timestamp.
- **D-17:** Next scheduled sync — frontend-derived from `sync_interval_minutes` + `last_sync_at`, no backend change.
- **D-18:** Consecutive-failure count — new backend counter column + migration + increment/reset logic.
- **D-19:** Error-capture shape: sanitized/truncated (exception type + message, capped length), passed through the **Phase-7 recursive secret-redaction** so tokens never land in `last_error`/logs. Counter increments on failure, resets to 0 on success. Add `last_error` to backend model + frontend `ConnectorConfig` type.
- **D-20:** Migration for two new columns: `last_error` nullable default NULL; `consecutive_failure_count` INTEGER NOT NULL default 0.
- **D-21:** Rapid7 `verify=False` becomes per-connector `verify_tls` config field, default `True`.
- **D-22:** Retry/rate-limit behavior stays per-connector (no shared refactor). REL-03 tests pin existing behavior.
- **D-23:** Formalize a Python Enum (backend) + shared TS union type (frontend) for ticketing providers, preserving the uppercase-backend/lowercase-frontend wire convention (`CR-06`).

### Claude's Discretion

- Exact enum member values, endpoint route naming, and Alembic migration numbering.
- Exact truncation length + which exception fields compose the sanitized `last_error` string.
- Whether the ticketing-client interface is `typing.Protocol` vs an ABC.
- Field-mapping fixtures for each connector's REL-03 test.

### Deferred Ideas (OUT OF SCOPE)

- Shared connector retry/backoff helper — per-connector behavior stays; tests pin it (D-22).
- Forcing Rapid7 TLS fully ON (no opt-out) — rejected in favor of `verify_tls` opt-out (D-21).
- Natural-language query over the inventory (AINL-01) — deferred to v3.1.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REL-01 | Wiz connector completes a full sync end-to-end | Exact bug confirmed at `wiz.py:155-188` (see Open Question 2); `sync.py:96-99` harness contract documented; fix + MockTransport test pattern from `test_provider_stubs.py`/`test_okta_sync.py` |
| REL-02 | Rapid7 connector completes a full sync end-to-end | Exact bug + **exact runtime error message** confirmed live (see Open Question 3); `base.py` ABC contract documented |
| REL-03 | All six scanner connectors get HTTP-layer integration tests | Existing normalization-only suite (`test_connector_normalization.py`) inventoried; confirms augmentation not greenfield (Open Question 1); pagination-test pattern sourced from `test_okta_sync.py`/`test_mdm_hr_connectors.py`/`test_intune_sync.py` |
| REL-04 | Analyst can create a Jira ticket from a vuln | Router/service/rule-engine Asana-hardcode sites enumerated exactly (Open Question 6); two `JiraClient`s diffed method-by-method (Open Question 4) |
| REL-05 | GitHub ticketing finished end-to-end | `GitHubClient` confirmed complete-but-orphaned, method surface documented, gaps vs. Asana auto-close template identified (Open Question 5) |
| REL-06 | Per-connector sync health visible in Connectors UI | `ConnectorConfig`/frontend type inventoried; **critical pre-existing status-value bug found** (Open Question 11) that blocks D-16/D-17/D-18 unless fixed first |

## Architecture Patterns

### Connector sync harness contract (`backend/app/connectors/sync.py`)

```python
# Source: backend/app/connectors/sync.py (verbatim, lines ~93-100)
connector = connector_cls()  # no-arg construction — EVERY connector class must support this
credentials = get_decrypted_credentials(connector_config)

authed = await connector.authenticate(credentials, connector_config.config or {})
if not authed:                      # falsy check — None, False, 0, "" all count as failure
    log.status = "FAILED"
    log.error_message = "Authentication failed"
    log.finished_at = datetime.now(UTC)
    return log
```

`CONNECTOR_CLASSES` maps `"WIZ"` → `WizConnector`, `"RAPID7"` → `Rapid7Connector`, etc. `BaseConnector` (`app/connectors/base.py`) is an `abc.ABC` with two abstract methods: `authenticate(credentials, config) -> bool` and `fetch_vulnerabilities() -> list[NormalizedVulnerability]`. `fetch_misconfigurations()` has a default no-op implementation. **This is the exact contract D-01/D-02 must satisfy.**

### Provider-dispatch seam (D-06..D-10) — exact call sites to replace

`backend/app/ticketing/service.py` (all three create functions + sync/close):
- `create_tickets(..., asana_client: AsanaClient, ...)` — line 111, always calls `asana_client.create_task(...)` at line 175, **regardless of `request.provider`**. Writes `Ticket.provider = request.provider` (line 193) even when it's `"JIRA"`/`"GITHUB"` — a live data-integrity mismatch today if a caller ever sends provider != ASANA (the Pydantic schema already accepts it — see below).
- `create_host_ticket(..., asana_client: AsanaClient, ...)` — line 294, same pattern.
- `create_remediation_ticket(..., provider: str, asana_client: AsanaClient, ...)` — line 489, same pattern: takes an explicit `provider` string param *and* a hardcoded `asana_client`, calls `asana_client.create_task(...)` at line 600 regardless of `provider`'s value.
- `sync_ticket_status(db, tenant_id, asana_client: AsanaClient)` — line 933, filters `Ticket.provider == "ASANA"` only (line 945); the auto-close block (lines 1015-1031) is the exact template to mirror for GitHub (D-12).
- `close_ticket(db, tenant_id, url, asana_client: AsanaClient)` — line 1085, Asana-only.

`backend/app/ticketing/rule_engine.py`:
- `action.get("provider", "ASANA")` at **line 138** (confirmed, matches CONTEXT.md's cited line) inside `run_rule()`.
- `run_all_due_rules()` (line 275) has a **second, independent Asana-hardcode** not called out by name in CONTEXT.md: it queries `ConnectorConfig.connector_type == "ASANA"` only (line ~305) *before* even looking at any rule's `action.provider`, then constructs `AsanaClient(token)` at **line 327**. A `TicketRule` whose `action.provider == "JIRA"` today either (a) silently never runs if the tenant has no Asana connector configured, or (b) runs against the wrong provider's client if they do. **This must be fixed alongside D-09** — it's not enough to thread `provider` through `run_rule`; `run_all_due_rules` must look up connector configs per-provider (grouped by the union of providers actually referenced by that tenant's enabled rules, defaulting to ASANA).

`backend/app/ticketing/router.py` — every ticket-mutating endpoint hardcodes Asana:
- `_get_asana_client` (line 53) / `_get_asana_client_from_connector` (line 85) — the exact functions D-10 generalizes into `_get_ticketing_client(provider)`.
- `create_new_tickets` (line 179), `create_host_remediation_ticket` (line 213), `sync_all_ticket_statuses` (line 245), `bulk_ticket_action` (line 260, all four sub-actions: close/comment/sync-update/delete), `close_ticket_endpoint` (line 403), `run_rule_now` (line 1115) — **all** call `_get_asana_client_from_connector` unconditionally, ignoring `body.provider` even where the request schema carries one.

**Confirms the schema already advertises multi-provider support that the implementation doesn't honor:**
```python
# backend/app/ticketing/schemas.py:53-63 (verbatim)
class TicketCreateRequest(BaseModel):
    provider: str = Field(..., pattern="^(ASANA|JIRA|GITHUB)$")   # already accepts all 3
class HostTicketCreateRequest(BaseModel):
    provider: str = Field(..., pattern="^(ASANA|JIRA|GITHUB)$")   # already accepts all 3
```
```typescript
// frontend/src/lib/mutations/use-create-ticket.ts:8 (verbatim)
export type CreateTicketRequest = {
  ...
  provider: 'ASANA' | 'JIRA' | 'GITHUB';   // already typed for all 3
```
The frontend *type* is ready; the actual call site (`drill-content.tsx:140`) hardcodes `provider: 'ASANA'` and there is no picker UI yet — this is exactly D-14's scope, no more, no less.

### Two `JiraClient`s — exact method-surface diff (D-08)

| Method | `app/ticketing/jira_client.py` (API v3, canonical target) | `app/connectors/jira_client.py` (API v2, to delete) |
|---|---|---|
| `create_ticket`/`create_issue` | `create_ticket(project_key, summary, description, assignee_account_id=None) -> JiraIssue \| None` — wraps description in ADF, single 429-retry, returns dataclass | `create_issue(project_key, summary, description, issue_type="Task", priority="Medium", assignee_email=None, labels=None) -> dict` — plain-text description, raises on HTTP error, returns plain dict |
| `get_issue` | `get_issue(issue_id_or_key) -> dict \| None` | `get_issue(issue_key) -> dict` (raises on error, no None-return) |
| **comment** | **absent** | `update_issue(issue_key, comment=None, status=None) -> dict` — posts a comment |
| **status transition / close** | **absent** | `update_issue(issue_key, comment=None, status=None)` — looks up transitions, POSTs the matching one (this is what `daily_sync._sync_jira_tickets` calls today) |
| `test_connection` | present, returns `{success, message, account_id, display_name}` | present, returns `{success, display_name, email, account_id}` or `{success: False, error}` |
| `list_projects`/`search_issues`/`delete_issue` | absent | present |
| `close()` (HTTP client cleanup) | present | present |

**Correction to D-08 as stated:** "pick/merge into the `app/ticketing/` one, delete the other" is not a pure deletion — `app/ticketing/jira_client.py` **lacks comment and status-transition capability entirely**, which `daily_sync.py`'s `_sync_jira_tickets` (line 271) currently depends on via `app/connectors/jira_client.py`'s `update_issue()`. The consolidation must **port** `update_issue`'s comment+transition logic into the canonical client (as two methods matching the dispatch protocol's `comment`/`close` verbs) before deleting the old one, or `daily_sync`'s Jira sync silently loses comment/auto-close capability. This is a real merge, not a delete-the-loser operation. Also note the API-version divergence (v2 plain description vs. v3 ADF) — since the canonical client already targets v3/ADF and that's what a fresh `create_ticket` call needs, standardize on v3 throughout.

### `GitHubClient` — confirmed orphaned, confirmed gaps vs. the Asana auto-close template (D-11/D-12)

`backend/app/ticketing/github_client.py` is referenced **nowhere** outside its own file and `backend/tests/test_provider_stubs.py` (`grep -rn "GitHubClient" backend/app/` returns zero hits outside its own definition). Method surface:

```python
class GitHubClient:
    def __init__(self, token: str, owner: str, repo: str) -> None: ...
    async def test_connection(self) -> dict: ...
    async def create_ticket(self, title: str, body: str) -> GitHubIssue | None: ...   # single 429-retry
    async def get_issue(self, number: int) -> dict | None: ...
    async def get_watchers(self) -> list: ...   # [] stub, D-W-01
    async def close(self) -> None: ...
```

**Gap vs. the auto-close template it must mirror (D-12):** the Asana template in `service.py:sync_ticket_status` (lines 1015-1031) calls `asana_client.update_task(task_gid, completed=True)` then `asana_client.add_comment(task_gid, "...")`. `GitHubClient` has **no `update_ticket`/`close_issue` method and no `add_comment` method at all** — both must be added (e.g. `PATCH /repos/{owner}/{repo}/issues/{number}` with `{"state": "closed"}` for close, `POST /repos/{owner}/{repo}/issues/{number}/comments` for comment) before the dispatch protocol can treat GitHub uniformly with Asana/Jira.

**GitHub connector-config registration is currently absent, not just "config fields" (D-13):** `"GITHUB"` does not appear in `backend/app/connectors/schemas.py`'s `CONNECTOR_TYPES` dict, nor in `backend/app/connectors/router.py`'s `CONNECTOR_CATEGORIES` dict (which drives the `/connectors/types` endpoint the add-connector wizard reads), nor in `backend/app/connectors/tester.py`'s provider-test dispatch table, nor in `backend/app/connectors/sync.py`'s `SPECIAL_CONNECTORS` set. All four registrations are needed for a GitHub connector to be creatable via the existing Connectors UI wizard. **Good news:** the frontend visual layer is *already* fully ready — `ConnectorProvider` (frontend `types.ts`) already includes `'github'`, and `--gradient-provider-github` is already defined in `globals.css:135` (`linear-gradient(135deg, #C7BAFF, #A78BFA)` — violet, matching `visual-language.md`'s "GitHub (violet)" spec). Only backend registration is missing.

### `httpx.MockTransport` convention (D-04) — exact patterns observed across the six precedent files

Two equally-valid variants exist in the codebase; both are acceptable, pick one per test file for consistency within that file:

**Variant A — construct a fresh `AsyncClient` with the mock transport, assign it to the client attribute** (`test_directory_connectors.py`, `test_ticketing_clients.py`, `test_mdm_hr_connectors.py`):
```python
# Source: backend/tests/test_directory_connectors.py (verbatim)
def _mock_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://mock")

@pytest.mark.asyncio
async def test_azure_fetch_users_normalizes_and_filters_guests():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={...})
    conn = AzureEntraConnector()
    conn.client = _mock_client(handler)
    try:
        users = await conn.fetch_users()
    finally:
        await conn.client.aclose()
```

**Variant B — patch the `_transport` attribute of an already-constructed client** (`test_provider_stubs.py`):
```python
# Source: backend/tests/test_provider_stubs.py (verbatim)
def _mock_transport(status: int, body: dict) -> httpx.MockTransport:
    response = httpx.Response(status_code=status, content=json.dumps(body).encode(),
                               headers={"content-type": "application/json"})
    return httpx.MockTransport(lambda request: response)

def _patch_transport(client_instance, transport: httpx.MockTransport) -> None:
    client_instance._transport = transport

client = JiraClient(email="user@example.com", api_token="fake-token", base_url="https://acme.atlassian.net")
_patch_transport(client._client, transport)   # client._client is the underlying httpx.AsyncClient
```

**Multi-page pagination fake** (D-05's "cursor/page loop, not just page 1" requirement) — the exact pattern from `test_okta_sync.py` (also used by `test_mdm_hr_connectors.py` and `test_intune_sync.py`):
```python
# Source: backend/tests/test_okta_sync.py (verbatim)
pages = [
    httpx.Response(200, json=[{"id": "1"}, {"id": "2"}], headers={"link": '<https://okta/p2>; rel="next"'}),
    httpx.Response(200, json=[{"id": "3"}]),  # no Link header → last page
]
calls = {"n": 0}
def handler(request: httpx.Request) -> httpx.Response:
    resp = pages[calls["n"]]
    calls["n"] += 1
    return resp
client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
results = await _paginated_get(client, "https://okta/p1", _auth_headers("t"))
assert [r["id"] for r in results] == ["1", "2", "3"]
assert calls["n"] == 2  # proves it followed the cursor, didn't stop at page 1
```
Adapt the same `pages = [...]; calls = {"n": 0}` counter pattern for each scanner's own pagination shape: Wiz's `after`/`endCursor`/`hasNextPage` GraphQL cursor (`wiz.py:_paginate`, line 228), Rapid7's `page`/`totalPages` REST pagination (`rapid7.py:_paginate`, line 55), CrowdStrike's `after` cursor, Nessus's scan-export polling loop, Qualys's XML pagination, Defender's `nextLink`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP mocking for connector tests | A new fixture/mocking library | `httpx.MockTransport` (already the house convention, 6 precedent files) | D-04 explicitly forbids `respx`/`pytest-httpx`; consistency lets future connectors copy an existing test file verbatim |
| Ticketing provider dispatch | A registry pattern or factory class hierarchy from scratch | A `typing.Protocol` (or thin ABC) with `create`/`get`/`close`/`comment`, matching `AsanaClient`'s existing method shapes | `daily_sync.py` already dispatches by provider string for status-sync (if/elif on `connector.connector_type`) — mirror that shape for the create path rather than inventing a new abstraction |
| Secret redaction for `last_error` | A new regex-based secret scanner | `app/logging.py`'s existing `_redact_value`/`_is_sensitive`/`SENSITIVE_KEYS` — but see the Open Question 7 correction below on how it actually composes | Reinventing redaction risk-surfaces a second place credentials can leak if the two redactors diverge |
| Provider enum | Scattered string literals / a new StrEnum ad hoc per module | One Python `Enum` in `app/ticketing/` (or `app/connectors/`) imported everywhere `provider` is compared, mirrored by one TS union type | D-23; today `provider` is `str` in Pydantic schemas (regex-validated), a bare `str` param in every service function, and matched via `if provider == "ASANA":`/`.get("provider", "ASANA")` in five+ places — a real enum removes silent typo risk |

**Key insight:** every "don't hand-roll" item above is really "don't hand-roll a *second* version of a pattern this codebase already has one of." This phase's actual work is almost entirely *generalizing an existing single-provider pattern into a multi-provider one*, not building new patterns.

## Common Pitfalls

### Pitfall 1: Assuming `provider` in the request is honored anywhere downstream of the Pydantic validator
**What goes wrong:** A plan writes "add Jira support to `create_tickets`" assuming the function already respects `request.provider` and just needs a Jira branch. It doesn't — the function ignores `request.provider` for dispatch purposes and always calls the injected `asana_client`.
**Why it happens:** The Pydantic regex (`^(ASANA|JIRA|GITHUB)$`) and the frontend TS union both *look* like the feature exists — they were added in an earlier phase anticipating this one, but the create path itself was never wired.
**How to avoid:** Grep every `asana_client.create_task(` / `asana_client.get_task(` / `asana_client.update_task(` / `asana_client.add_comment(` call site in `service.py`, `rule_engine.py`, `router.py`, `daily_sync.py` and replace with the dispatched client — there are more sites than the ones CONTEXT.md's canonical_refs names (see Architecture Patterns above for the full router.py list, and `run_all_due_rules`'s second hardcode).
**Warning signs:** A test that POSTs `provider: "JIRA"` and asserts an actual Jira API call happened (not just that `Ticket.provider == "JIRA"` in the DB) — writing that test first will immediately surface every remaining hardcoded site.

### Pitfall 2: Assuming `SyncStatusPill` "just works" once `last_error`/`consecutive_failure_count` are added (REL-06)
**What goes wrong:** D-16/D-17/D-18 build error-summary/next-sync/failure-count UI on top of `SyncStatusPill`, but the pill itself is already broken for any connector that has ever completed a sync (success or failure) — see Open Question 11 below for the full trace. If this isn't fixed first, the phase ships a health surface that crashes on the exact "healthy, actively syncing connector" case it's meant to showcase.
**Why it happens:** The bug is invisible in the component's own unit tests (which hardcode the correct-but-fictional `'ok'` value) and would only surface with live/seeded data that has actually completed a sync — which the existing test suite for this component never exercises.
**How to avoid:** Fix the status-value mapping (backend `_to_response` in `service.py`, or a frontend-side mapping function) as part of whichever plan builds D-16, before adding new fields on top. Add a regression test using the *real* backend values (`"SUCCESS"`, `"FAILED"`, `None`) — not `'ok'`/`'failed'`/`null` — to `sync-status-pill.test.tsx` and `connector-card.test.tsx`.
**Warning signs:** `STATUS_CONFIG[key]` returning `undefined` in dev console; a Playwright/e2e run against a connector that has actually synced (not the `null`-status seed fixture) throwing a React render error.

### Pitfall 3: Treating `verify_tls` (D-21) as Rapid7-only
**What goes wrong:** A plan adds `verify_tls` only to Rapid7 (per the literal text of D-21), leaving Nessus with an identical hardcoded `verify=False` MITM exposure, and leaving the *Test Connection* code path exposed for both even after the sync path is fixed.
**Why it happens:** CONTEXT.md's D-21 names Rapid7 specifically (it's the connector REL-02 already touches), but `verify=False` independently appears in **four** places: `nessus.py:70`, `rapid7.py:44`, `tester.py:77` (`test_nessus`'s own connection test), `tester.py:348` (`test_rapid7`'s own connection test).
**How to avoid:** Either (a) explicitly extend D-21's `verify_tls` field to Nessus as well as Rapid7 and thread it through both connectors' sync-path *and* their `tester.py` test-connection functions (recommended — keeps the two on-prem-scanner stories consistent), or (b) explicitly scope D-21 to Rapid7-only and document Nessus's identical exposure as a deferred/backlog item so it isn't silently forgotten. Do not fix one call site per connector and leave the `tester.py` "Test Connection" wizard button using the old hardcoded `verify=False` — that produces a UI that reports "TLS verified! ✓" via Test Connection while the real sync still (or no longer) validates differently.
**Warning signs:** A connector's wizard "Test Connection" step succeeds against a cert an actual sync would reject (or vice versa) once `verify_tls` diverges between the two code paths.

### Pitfall 4: Assuming the Phase-7 redactor sanitizes arbitrary exception-message strings (D-19)
**What goes wrong:** A plan calls something like `redact_sensitive_keys(str(exc))` expecting it to strip embedded secrets from a plain string. It can't — see Open Question 7 for the exact mechanism.
**Why it happens:** The existing utility redacts by **dict key name** (`Authorization`, `password`, `token`, etc. — recursively through nested dicts/lists), not by scanning string *values* for secret-shaped substrings. An exception message is a bare string with no key context.
**How to avoid:** Wrap the exception capture in a small dict before redacting — e.g. `_redact_value({"exception_type": type(e).__name__, "message": str(e)})` — which only helps if the secret happens to be nested inside a dict-shaped substructure of the message (rare for `httpx.HTTPStatusError.__str__()`, which is just a formatted sentence). For the realistic case (a raw exception string that might echo back request/response text containing a token), the safer approach is either (a) truncate aggressively and accept residual risk is low because httpx exception `__str__()` doesn't include request headers by default, or (b) apply a lightweight pattern-based scrub (e.g. strip anything matching `Bearer [\w.-]+`, `Basic [\w+/=]+`, common API-key shapes) in addition to the dict-based redactor. Document whichever choice is made — this is exactly the kind of "how, precisely" detail CONTEXT.md left to Claude's discretion (truncation length + composed fields).
**Warning signs:** A crafted test where the mocked HTTP response body contains a fake credential and the resulting `last_error` string still contains it verbatim.

## Runtime State Inventory

Not applicable — this phase is bug-fix + feature-completion + new-column work, not a rename/refactor/migration of existing identifiers. (The two new columns in D-20 are additive with safe defaults, covered under Architecture Patterns / migration sequencing below, not a runtime-state migration.)

## Migration Sequencing (D-20)

**Correction to CONTEXT.md's canonical_refs:** "`backend/alembic/versions/` — latest migration to sequence D-20 after (026/027/028 are the most recent ticketing migrations)" is imprecise. `026_add_ticket_comments.py` → `027_add_ticket_blocked_sla.py` → `028_add_ticket_watchers.py` are indeed the most recent *ticketing* migrations, but they are **not the chain head**. `029_add_must_change_password.py` (Phase 6, unrelated to ticketing) was applied after all three and is the actual current head — confirmed by walking the full `revision`/`down_revision` chain (`001_initial_schema.py` → ... → `029_add_must_change_password.py`, single linear chain, no branches).

**The new migration for D-20 MUST set `down_revision = "029_add_must_change_password"`**, not `"028_add_ticket_watchers"`. Suggested name: `030_add_connector_health_columns.py`. Column additions:
```python
op.add_column("connector_configs", sa.Column("last_error", sa.Text(), nullable=True))
op.add_column("connector_configs", sa.Column(
    "consecutive_failure_count", sa.Integer(), nullable=False, server_default="0"
))
```
`server_default="0"` (not just a Python-side `default=0`) is required so existing rows backfill correctly in the same `ALTER TABLE ADD COLUMN` — matches D-20's "INTEGER NOT NULL default 0 for existing rows" requirement without a separate backfill UPDATE.

## Code Examples

### `NormalizedVulnerability` — exact D-05 mapping target

```python
# Source: backend/app/connectors/base.py (verbatim, the dataclass every REL-03 test's
# "field-for-field" assertion maps into)
@dataclass
class NormalizedVulnerability:
    cve_id: str | None
    vulnerability_name: str | None
    cvss_v3_score: float | None
    severity: str
    exploit_available: bool = False
    cisa_kev: bool = False
    source_vuln_id: str | None = None
    affected_product: str | None = None
    affected_version: str | None = None
    fixed_version: str | None = None
    remediation_info: str | None = None
    hostname: str | None = None
    ip_addresses: list[str] = field(default_factory=list)
    os_name: str | None = None
    os_version: str | None = None
    asset_type: str = "ENDPOINT"
    # + ~15 more optional enrichment fields (platform_name, serial_number, mac_address, etc.)
```

### Wiz bug — exact current signature (the fix target for D-01)

```python
# Source: backend/app/connectors/wiz.py:155-188 (verbatim)
async def authenticate(
    self,
    credentials: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> None:                                    # <-- WRONG: base contract says -> bool
    """Authenticate via OAuth2 client_credentials grant."""
    client_id: str = credentials["client_id"]
    ...
    resp = await self._client.post(token_endpoint, data={...})
    resp.raise_for_status()
    self._token = resp.json()["access_token"]
    self._client.headers["Authorization"] = f"Bearer {self._token}"
    logger.info("wiz.authenticated")
    # <-- no return statement at all; falls through returning None
```
Verified live: `inspect.signature(WizConnector.authenticate)` → `(self, credentials: 'dict[str, Any]', config: 'dict[str, Any] | None' = None) -> 'None'`. Fix: change the return annotation to `bool` and add `return True` at the end of the success path (there's no explicit failure path to also fix — `resp.raise_for_status()` already raises on HTTP failure, which the sync harness's `except Exception` catches separately from the `if not authed` branch).

### Rapid7 bug — exact current signature + **live-reproduced error** (the fix target for D-02)

```python
# Source: backend/app/connectors/rapid7.py:22-33 (verbatim)
class Rapid7Connector(BaseConnector):
    source_name = "RAPID7"
    def __init__(self, config: dict[str, Any]) -> None:   # <-- WRONG: harness calls Rapid7Connector() no-arg
        super().__init__(config)
        self.base_url = config["base_url"].rstrip("/")
        self.username = config["username"]
        self.password = config["password"]
        ...
    # <-- no authenticate() method defined anywhere in the file
```
Live-reproduced (`backend/.venv/bin/python -c "from app.connectors.rapid7 import Rapid7Connector; Rapid7Connector()"`):
```
TypeError: Can't instantiate abstract class Rapid7Connector without an implementation for abstract method 'authenticate'
```
This is the **actual** error the harness hits — `abc.ABC`'s instantiation guard fires before Python ever gets far enough to complain about the missing `config` argument. Fix: add `async def authenticate(self, credentials: dict, config: dict) -> bool:` that does what `__init__` does today (capture `base_url`/`username`/`password` from `credentials`/`config` instead of a constructor arg, return `True`), and change `__init__` to take no arguments beyond `self`.

## State of the Art

Not applicable in the "library/ecosystem moved on" sense — this is internal-codebase augmentation, not adoption of an external library that has newer versions. The one relevant "current vs. superseded" axis is the two `JiraClient`s (API v2 vs v3) — see Architecture Patterns above; standardize on v3/ADF (the canonical target already uses it).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The safest fix for `last_error` secret-redaction is wrapping the exception capture in a dict passed through `_redact_value`, plus an additional lightweight token-pattern scrub — rather than relying on the existing utility alone | Pitfall 4 | If skipped, a crafted upstream HTTP error response containing a credential-shaped string could land in `last_error`/logs unredacted; low likelihood (httpx exceptions don't embed request headers by default) but non-zero |
| A2 | Standardizing the consolidated `JiraClient` on API v3 + ADF descriptions (rather than v2 plain-text) is the right call, since the canonical target (`app/ticketing/jira_client.py`) already uses v3 | Architecture Patterns (two JiraClients) | Low — Jira Cloud fully supports v3; the only cost is porting `update_issue`'s comment/transition logic to the ADF-aware client, which must happen regardless per D-08 |

**All other claims in this document are `[VERIFIED: codebase]`** — confirmed via direct file reads, `grep`, or a live `backend/.venv/bin/python` REPL invocation in this session, not training-data recall.

## Open Questions (resolved during this research pass)

### 1. REL-03 greenfield-vs-augment — RESOLVED: augmenting, not greenfield
`backend/tests/test_connector_normalization.py` exists today (Phase 8) and already covers **pure normalization/severity-mapping logic** for all six scanners (CrowdStrike, Defender, Nessus, Qualys, Rapid7, Wiz) — e.g. `test_rapid7_severity_from_cvss`, `test_wiz_vuln_severity_fallbacks`, `test_nessus_normalize_vuln_maps_severity_and_cves`, `test_crowdstrike_normalize_vuln_extracts_cve_and_severity`. These tests call connector methods **directly with in-memory dicts** — no HTTP, no `httpx.MockTransport`, no auth, no pagination. `backend/tests/test_connectors/` is genuinely empty (only `__init__.py`) — it's the target directory for the *new* HTTP-layer tests this phase adds (auth success/failure, multi-page pagination, end-to-end `fetch_vulnerabilities` against a mocked transport), which is a **different, additive layer**, not a duplicate of the existing normalization suite. The Phase-8 memory note ("6 vuln-scanner connector tests shipped") refers to `test_connector_normalization.py`'s coverage — both claims are true simultaneously once you see they're testing different layers. **Sizing implication for the planner:** REL-03 plans should write genuinely new HTTP-layer test files in `backend/tests/test_connectors/` (e.g. `test_wiz_connector.py`, `test_rapid7_connector.py`, etc., one per scanner) — this is real, non-trivial new-test-authoring work across 6 connectors, not a quick augment of an existing file.

### 2. Wiz bug — RESOLVED: confirmed exactly as CONTEXT.md states, with exact source location
See Code Examples above. `authenticate()` is typed `-> None` at `wiz.py:155-159`, has no `return` statement, confirmed live via `inspect.signature`. `sync.py`'s harness does `if not authed:` (line 97) — `None` is falsy, so a fully successful Wiz auth (token fetched, headers set, no exception) is nonetheless reported as `"Authentication failed"`.

### 3. Rapid7 bug — RESOLVED: confirmed, with the *exact* error message (more precise than CONTEXT.md's generic "TypeError")
See Code Examples above. The harness's `connector_cls()` call raises `TypeError: Can't instantiate abstract class Rapid7Connector without an implementation for abstract method 'authenticate'` — reproduced live. `BaseConnector` (`base.py`) is confirmed as `abc.ABC` with `authenticate`/`fetch_vulnerabilities` as `@abc.abstractmethod`; it defines no `__init__`.

### 4. Two `JiraClient`s — RESOLVED, with a scope correction
See the full method-surface diff table under Architecture Patterns. **Correction:** D-08's "pick/merge into the `app/ticketing/` one, delete the other" undersells the work — the canonical target lacks comment/status-transition capability that `daily_sync.py` depends on today via the other client. This must be **ported**, not dropped.

### 5. Orphaned `GitHubClient` — RESOLVED, with two gaps flagged
Confirmed complete for create/get/watchers-stub/close, confirmed referenced nowhere outside its own file + `test_provider_stubs.py` (`grep -rn "GitHubClient" backend/app/` → zero hits outside definition). **Gap for D-12:** it has no comment or close/update-state method at all — both must be added to mirror the Asana auto-close template (`service.py:1015-1031`, documented verbatim under Architecture Patterns). **Gap for D-13:** `"GITHUB"` is registered in exactly zero of the four places a connector type needs to be registered on the backend (`CONNECTOR_TYPES`, `CONNECTOR_CATEGORIES`, `tester.py`'s dispatch table, `SPECIAL_CONNECTORS`) — though the frontend visual layer (`ConnectorProvider` type, `--gradient-provider-github` CSS var) is already fully ready.

### 6. Ticketing dispatch seam — RESOLVED, with one additional hardcode site found
Every call site CONTEXT.md names is confirmed at the line numbers given. **One additional site found:** `rule_engine.py::run_all_due_rules` (line 275) independently hardcodes an Asana-only connector lookup (`ConnectorConfig.connector_type == "ASANA"`, ~line 305) **before** `run_rule` even reads `action.provider` — a second, structurally different hardcode from the one at line 327 CONTEXT.md cites. Both must be fixed for D-09 to actually work for JIRA/GITHUB-provider rules on the scheduled path. **Codebase idiom for Protocol vs ABC:** the codebase has no existing `typing.Protocol` usage searched for in `app/`; `BaseConnector` uses `abc.ABC` + `@abc.abstractmethod`. Given `AsanaClient`/`JiraClient`/`GitHubClient` are already independent concrete classes (not subclasses of a common base) with matching-but-not-identical method names (`create_task`/`create_ticket`/`create_ticket`; `get_task`/`get_issue`/`get_issue`), a `typing.Protocol` is the lower-friction choice — it lets each client keep its existing method names as long as a thin adapter/wrapper normalizes them to the protocol's verbs, without forcing an inheritance rewrite of three already-shipped, already-tested classes. This is a nuance-with-a-recommendation (Claude's Discretion per CONTEXT.md), not a re-litigation of the decision.

### 7. Phase-7 secret-redaction reuse — RESOLVED, with an important correction
Located at `backend/app/logging.py`. Exports:
```python
SENSITIVE_KEYS: frozenset[str] = frozenset({"authorization", "cookie", "password", "token", "secret", "credentials", "api_key"})
def _is_sensitive(key: object) -> bool: ...          # underscore-prefixed (module-private by convention)
def _redact_value(value: object) -> object: ...       # underscore-prefixed; recursive over dict/list
def redact_sensitive_keys(logger, method, event_dict: EventDict) -> EventDict: ...  # the public structlog processor
```
**Correction:** `redact_sensitive_keys` is a structlog **processor** with a fixed 3-arg signature (`logger, method, event_dict`) operating on a `dict` — it redacts by **key name**, recursively through nested dicts/lists, not by scanning string *values* for secret-shaped substrings. A plain exception message (`str(exc)`) has no key structure, so passing it directly through this utility does nothing useful. See Pitfall 4 above for the recommended reuse pattern (wrap in a dict + optionally add a lightweight pattern scrub). The underscore-prefixed helpers (`_redact_value`, `_is_sensitive`) are importable (Python doesn't enforce privacy) but are module-private by convention — if D-19's implementation needs them directly, either import them with a `# noqa`-style comment acknowledging the convention break, or promote one to a public name in the same module.

### 8. Migration sequencing — RESOLVED, with a chain-head correction
See "Migration Sequencing (D-20)" section above. Actual head is `029_add_must_change_password`, not `028_add_ticket_watchers`.

### 9. `httpx.MockTransport` convention — RESOLVED
Two variants documented verbatim under Architecture Patterns, both valid; pagination-fake pattern from `test_okta_sync.py` documented verbatim (the `pages = [...]; calls = {"n": 0}` counter idiom).

### 10. Per-connector retry/rate-limit behavior — RESOLVED, more granular than CONTEXT.md's summary
| Connector | Behavior | Bounded? |
|---|---|---|
| Wiz | 5-attempt loop (`for attempt in range(1, 6)`) on 429, sleeps `Retry-After` header (default 5s), raises `RuntimeError` if exhausted | Yes, 5 attempts |
| Defender | `MAX_RETRIES = 3` loop on 429, sleeps `Retry-After` header | Yes, 3 attempts |
| Qualys | `_retries: int = 3` param, retries on `httpx.TimeoutException` (backoff `5*attempt`) AND on HTTP 409 (Qualys's rate-limit status code, not 429!) using `X-RateLimit-ToWait-Sec` header; also proactively throttles when `X-RateLimit-Remaining <= 2` | Yes, 3 attempts, dual-trigger (timeout + 409) |
| CrowdStrike | **Inconsistent within the connector itself**: main vulnerability-pagination loop (`fetch_vulnerabilities`) retries unboundedly on 429 (`sleep(5); continue`, no attempt cap); but the three enrichment-batch helpers (`_resolve_devices_batch`, `_resolve_remediations_batch`, `_resolve_vuln_metadata_batch`, `_resolve_eval_logic_batch`) only `sleep(3)` on 429 with **no actual retry of the failed batch** — the batch's data is silently dropped from the enrichment cache | No (main loop unbounded; enrichment batches don't retry at all) |
| GitHub (ticketing) | Single retry on 429 (no loop), sleeps `Retry-After` header, then retries once more unconditionally | Yes, exactly 1 retry |
| Rapid7 | **None** — no 429/rate-limit handling anywhere in `rapid7.py` | No handling |
| Nessus | **None** — no 429/rate-limit handling anywhere in `nessus.py` | No handling |
| Jira (ticketing) | Single retry on 429, sleeps `Retry-After` header | Yes, exactly 1 retry |

D-05's REL-03 tests should assert each of these behaviors **as currently implemented** (pin, don't change) — including CrowdStrike's internal inconsistency between its main loop and its enrichment batches, which is worth a one-line code comment in the test itself so a future reader doesn't mistake the pinned assertion for an oversight.

### 11. Frontend health-surface + provider-picker current state — RESOLVED, with a critical pre-existing bug found
- `frontend/src/types/connector.ts`'s `ConnectorConfig.last_sync_status: string | null` and `frontend/src/lib/queries/use-connectors-admin.ts`'s `ConnectorConfigResponse.last_sync_status: 'ok' | 'syncing' | 'failed' | null` — **confirmed no `last_error` field exists today**, exactly as CONTEXT.md states.
- **Critical bug (new finding, not in CONTEXT.md):** the backend has *never*, at any point in the codebase, written the string `"ok"`, `"syncing"`, or `"failed"` to `ConnectorConfig.last_sync_status`. Every sync module (`sync.py`, `directory_sync.py`, `jamf_sync.py`, `humaans_sync.py`) writes `"SUCCESS"` or `"FAILED"` (uppercase), and `backend/app/connectors/service.py::_to_response` passes the raw DB value straight through with **zero transformation** (`last_sync_status=c.last_sync_status`). `connector-card.tsx:71` passes this value directly into `<SyncStatusPill status={connector.last_sync_status} />`. `SyncStatusPill`'s internal lookup (`sync-status-pill.tsx:29`, `const { label, pillClass, dotClass } = STATUS_CONFIG[key]`) has no entry for `"SUCCESS"`/`"FAILED"` — only lowercase `ok`/`failed`/`syncing`/`__never` — so `STATUS_CONFIG["SUCCESS"]` is `undefined` and the destructure **throws at render time**. The component's own unit test (`sync-status-pill.test.tsx`) and `connector-card.test.tsx`'s `MOCK_CONNECTOR` both hardcode the fictional lowercase value directly (`last_sync_status: 'ok' as const`) — the test suite has never once exercised a real backend value, so this bug has shipped invisibly. **This must be fixed as prerequisite/Wave-0 work for whichever plan implements D-16/D-17/D-18** — the health surface's whole premise (showing sync status "at a glance") is currently broken for any connector that has actually completed a sync, success or failure alike. Recommended fix location: normalize in `_to_response` (backend, one line, `"SUCCESS"` → `"ok"`, `"FAILED"` → `"failed"`, `None` → `None`) rather than in the frontend, since the backend already owns the wire-convention precedent (`CR-06`, provider lowercasing) for this exact kind of enum-casing normalization.
- `frontend/src/components/connectors/connector-mark.tsx` and `types.ts` already fully support `github` as a `ConnectorProvider` (gradient + glyph) — confirmed no frontend visual work needed for D-13/D-11's UI-visibility requirement, only backend registration (see Open Question 5).
- `drill-content.tsx:140` hardcodes `provider: 'ASANA'` in its `createTicket.mutateAsync(...)` call — the create affordance exists (button → `ConfirmModal` → mutation → toast), but there is zero provider-selection UI. D-14's actual scope is: add a picker component (likely a small dropdown/radio-group in the existing confirm flow) that replaces this hardcoded literal, sourced from D-15's new "configured providers" endpoint.
- `use-connectors-admin.ts` already declares `ConnectorConfigResponse` matching the backend `ConnectorResponse` schema field-for-field except for the missing `last_error`/`consecutive_failure_count` (to be added by D-19/D-20) and the status-casing bug above.

### 12. Backend pytest env caveat — RESOLVED, exact command
```bash
cd backend
export ENCRYPTION_KEY=$(.venv/bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
export JWT_SECRET_KEY=$(.venv/bin/python -c "import secrets; print(secrets.token_urlsafe(48))")
export ENVIRONMENT=development
.venv/bin/pytest tests/test_connectors/test_wiz_connector.py -v   # per-file, NOT `pytest tests/`
```
Run **per file**, not the whole `tests/` directory — full-suite runs cause cross-test DB contamination against the shared local Postgres (order-dependent failures observed previously in `test_vuln_sort`/`test_vuln_facets`/`test_vuln_group_host`; same tests pass at file-level isolation). Two suites (`test_rate_limit.py`, `test_snooze.py::test_snooze_fails_closed_when_audit_write_fails`) are Docker-only and fail identically regardless of the phase under test — exclude them from local regression signal. REL-03's new tests are pure `httpx.MockTransport` unit tests with no DB fixture dependency (confirmed — none of the six precedent test files use a `db_session`/`async_session` fixture), so this caveat mostly matters for any test that touches `run_sync`/the DB-backed harness end-to-end, not for the mock-transport-only connector tests themselves.

**Separately, before pushing:** the backend CI gate is `ruff check` → `ruff format --check` → `mypy | mypy-baseline filter --allow-unsynced` → migrations → pytest, failing at the first red step. Running only pytest locally and skipping lint/type checks has caused CI-red-but-local-green surprises before (per project memory). Run:
```bash
.venv/bin/ruff check . && .venv/bin/ruff format --check . && \
  (set +o pipefail; .venv/bin/mypy app/ | .venv/bin/mypy-baseline filter --allow-unsynced; echo exit=$?)
```

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (backend, async via `pytest-asyncio` `@pytest.mark.asyncio`) + Vitest + React Testing Library (frontend component tests) + Playwright (frontend e2e, not required for this phase's backend-heavy scope but relevant to D-14/D-16 UI changes) |
| Config file | `backend/pytest.ini` (backend); `frontend/vitest.config.ts` (frontend unit) |
| Quick run command | `cd backend && .venv/bin/pytest tests/test_connectors/test_<connector>_connector.py -v` (per new test file) |
| Full suite command | Per-file iteration per the caveat in Open Question 12 — there is no single safe "run everything" command for this repo's backend suite; iterate `tests/*.py` individually, excluding `test_rate_limit.py` and the one Docker-only `test_snooze.py` case from local signal |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REL-01 | Wiz `authenticate()` returns `True` on success, sync harness proceeds to `fetch_vulnerabilities` | unit (MockTransport) | `pytest tests/test_connectors/test_wiz_connector.py -v` | ❌ Wave 0 |
| REL-02 | Rapid7 constructs no-arg, `authenticate()` returns `True`, sync proceeds | unit (MockTransport) | `pytest tests/test_connectors/test_rapid7_connector.py -v` | ❌ Wave 0 |
| REL-03 | Each of 6 connectors: auth success+failure, multi-page pagination to completion, field-for-field `NormalizedVulnerability` mapping | unit (MockTransport) | `pytest tests/test_connectors/test_{wiz,rapid7,crowdstrike,defender,nessus,qualys}_connector.py -v` | ❌ Wave 0 (all 6 files) |
| REL-04 | POST `/api/v1/tickets` with `provider: "JIRA"` actually calls the Jira client (not Asana); ticket row + external issue both reflect Jira | integration (MockTransport + DB fixture) | `pytest tests/test_ticketing_dispatch.py -v` | ❌ Wave 0 |
| REL-05 | POST `/api/v1/tickets` with `provider: "GITHUB"` creates a GitHub issue; `daily_sync` reads GitHub issue state and auto-closes on all-vulns-remediated | integration (MockTransport + DB fixture) | `pytest tests/test_ticketing_dispatch.py -v` (same file, GitHub cases) + `pytest tests/test_github_sync.py -v` | ❌ Wave 0 |
| REL-06 (backend) | `last_error`/`consecutive_failure_count` increment on failure, reset on success, redacted of secrets, truncated | unit + integration | `pytest tests/test_connector_health.py -v` | ❌ Wave 0 |
| REL-06 (frontend) | `SyncStatusPill` renders real backend values (`"SUCCESS"`/`"FAILED"`/`None`, post-normalization `"ok"`/`"failed"`/`null`) without throwing; `ConnectorCard` shows error summary + next-sync + failure count | component (Vitest + RTL) | `npm run test -- sync-status-pill connector-card` | ⚠️ files exist but assert the WRONG values today — must be corrected, not just extended |

### Sampling Rate

- **Per task commit:** run the specific new/modified test file (`pytest tests/test_connectors/test_<x>.py -v` or `npm run test -- <component>`).
- **Per wave merge:** run every file touched in that wave individually (per-file isolation caveat), plus `ruff check . && ruff format --check . && mypy | mypy-baseline filter`.
- **Phase gate:** all six new `test_connectors/test_*.py` files green + `test_ticketing_dispatch.py` + `test_github_sync.py` + `test_connector_health.py` green + frontend component suite green + a manual/e2e smoke of the provider picker (D-14) actually reaching a real-shaped mocked Jira/GitHub response, before `/gsd-verify-work`.

### Wave 0 Gaps

- [ ] `backend/tests/test_connectors/test_wiz_connector.py` — REL-01, REL-03 (Wiz slice)
- [ ] `backend/tests/test_connectors/test_rapid7_connector.py` — REL-02, REL-03 (Rapid7 slice)
- [ ] `backend/tests/test_connectors/test_crowdstrike_connector.py` — REL-03
- [ ] `backend/tests/test_connectors/test_defender_connector.py` — REL-03
- [ ] `backend/tests/test_connectors/test_nessus_connector.py` — REL-03
- [ ] `backend/tests/test_connectors/test_qualys_connector.py` — REL-03
- [ ] `backend/tests/test_ticketing_dispatch.py` — REL-04, REL-05 (provider-dispatch protocol, all three create paths × three providers)
- [ ] `backend/tests/test_github_sync.py` — REL-05 (daily_sync GitHub branch + auto-close)
- [ ] `backend/tests/test_connector_health.py` — REL-06 backend (last_error/counter increment/reset/redaction)
- [ ] Correct (not just add to) `frontend/src/components/connectors/sync-status-pill.test.tsx` and `connector-card.test.tsx` — both currently assert a value shape (`'ok'`/`'failed'`) the backend has never produced; REL-06 frontend tests must be rebuilt against real backend values

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes (indirectly) | This phase doesn't touch end-user auth, but connector *credential* handling (Fernet encryption via `get_decrypted_credentials`) is exercised throughout — no change to that mechanism, just correct usage per D-01/D-02/D-13 |
| V3 Session Management | no | Not touched by this phase |
| V4 Access Control | yes | New endpoint (D-15, "configured providers") and new columns (D-20) must be tenant-scoped like every existing query in this codebase (`ConnectorConfig.tenant_id == user.tenant_id` pattern used throughout `router.py`) |
| V5 Input Validation | yes | `provider` field already regex-validated (`^(ASANA|JIRA|GITHUB)$`) in Pydantic schemas; D-23's enum formalization should extend that validation to the enum's `__members__`, not weaken it |
| V6 Cryptography | yes | GitHub connector credentials (D-13: token/owner/repo) must go through the existing Fernet/`ConnectorConfig.credentials_secret_arn` pattern — never store the GitHub PAT in plaintext `config` JSONB (the existing pattern already separates `credentials_secret_arn` (encrypted) from `config` (plaintext, non-secret settings like `owner`/`repo`); `token` must live in the encrypted side, `owner`/`repo` can live in `config`) |
| V7 Error Handling / Logging | **yes — this phase's actual novel security surface** | D-19's `last_error` capture is a new place where a caught exception's string representation gets persisted to the DB and displayed in the UI — the exact "log secrets accidentally" pitfall the Phase-7 redactor was built to prevent for structured logs. See Pitfall 4 / Open Question 7 for the precise correction needed to reuse that machinery correctly for this new, string-shaped surface. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Credential/token leakage via error messages surfaced to the UI | Information Disclosure | D-19's sanitize-before-store; verified the existing redactor needs the dict-wrapping correction (Pitfall 4) to actually catch anything in a bare exception string |
| MITM on on-prem scanner connections (Rapid7, and — newly identified — Nessus) via disabled TLS verification | Tampering / Information Disclosure | D-21's `verify_tls` opt-out-not-default; extend to Nessus (Pitfall 3) and to both connectors' `tester.py` "Test Connection" paths, not just the sync path |
| Cross-tenant ticket/connector-config access via an unscoped provider-dispatch lookup | Elevation of Privilege | Every existing Asana-hardcoded lookup already filters by `ConnectorConfig.tenant_id == user.tenant_id` / `TicketRule.tenant_id` — the generalized `_get_ticketing_client(provider)` (D-10) and the new configured-providers endpoint (D-15) must preserve that filter exactly; do not introduce a global-lookup-by-provider-only path |
| Ticket-provider confusion (a Jira-labeled DB row created via an Asana API call) | Tampering (data integrity, not security-boundary, but adjacent) | This is the live bug documented in the Summary/Architecture Patterns sections — D-06/D-07's dispatch fix is the mitigation |

## Design System Constraints (auto-loaded per CLAUDE.md)

Per `.claude/skills/sketch-findings-getvul/SKILL.md`:
- **Providers:** "Jira (cool blue) · Asana (coral) · GitHub (violet). Gradient marks, not real logos." — already implemented in `connector-mark.tsx`/`globals.css` (confirmed, see Open Question 5/11).
- **Fonts locked:** Inter (UI/body) + JetBrains Mono (CVE IDs, hostnames, mono values) — `last_error`'s HTTP status code / request-id-shaped content, if any, should use the mono treatment already established for "terminal-pasteable" values.
- **Error state rule ("Amber, not red"):** `state-patterns.md` states partial/degraded failure should be amber, red reserved for critical severity. **Note for the planner:** `SyncStatusPill`'s existing `failed` state already uses `severity-critical` (red), not amber — this predates this phase and is a defensible distinction (a *fully* failed sync is arguably "down," not "degraded," matching the skill's own severity-vs-degraded distinction), but D-16's new inline error-summary component should decide consistently with the existing pill rather than introducing a second, conflicting color convention for the same "failed" state.
- **Mandatory state coverage:** any new UI surface (provider picker, error-summary expand/hover) needs loading/empty/error states per the skill's "no screen ships without all three" mandate — the provider picker specifically needs an empty state for "no ticketing providers configured yet" (which is exactly what D-15's endpoint should signal, not a client-side empty array from filtering).

## Sources

### Primary (HIGH confidence — all `[VERIFIED: codebase]`)
- `backend/app/connectors/base.py`, `wiz.py`, `rapid7.py`, `sync.py`, `scheduler.py`, `crowdstrike.py`, `defender.py`, `nessus.py`, `qualys.py`, `schemas.py`, `router.py`, `service.py`, `tester.py` — read in full or targeted `grep`/`sed` excerpts
- `backend/app/ticketing/service.py`, `rule_engine.py`, `router.py`, `daily_sync.py`, `asana_client.py`, `jira_client.py`, `github_client.py`, `models.py`, `schemas.py` — read in full or targeted excerpts
- `backend/app/connectors/jira_client.py` — read in full (the "other" JiraClient)
- `backend/app/logging.py` — read in full (Phase-7 redaction utility)
- `backend/alembic/versions/*.py` — revision/down_revision chain walked programmatically to confirm head
- `backend/tests/test_connector_normalization.py`, `test_provider_stubs.py`, `test_ticketing_clients.py`, `test_directory_connectors.py`, `test_okta_sync.py`, `test_mdm_hr_connectors.py` — read in full
- `frontend/src/types/connector.ts`, `frontend/src/lib/queries/use-connectors-admin.ts`, `frontend/src/components/connectors/connector-card.tsx`, `sync-status-pill.tsx`, `connector-mark.tsx`, `types.ts`, `sync-status-pill.test.tsx`, `connector-card.test.tsx`, `frontend/src/lib/mutations/use-create-ticket.ts`, `frontend/src/components/vulnerabilities/drill-content.tsx` — read in full or targeted excerpts
- Live REPL execution: `backend/.venv/bin/python -c "..."` — reproduced the exact Rapid7 `TypeError` and confirmed Wiz's `authenticate` signature via `inspect.signature`
- `.planning/phases/23-ingestion-reliability-precursor/23-CONTEXT.md`, `.planning/REQUIREMENTS.md`, `.planning/STATE.md`, `.planning/ROADMAP.md`, `.claude/skills/sketch-findings-getvul/SKILL.md`, `CLAUDE.md` — read in full

### Secondary (MEDIUM confidence)
- `~/.claude/projects/.../memory/getvul-backend-pytest-env.md` — project memory note, cross-checked against `conftest.py`/env-var expectations (not independently re-verified in this session beyond confirming the described `RuntimeError` gate exists per Phase 5's known startup check, referenced in STATE.md history)

### Tertiary (LOW confidence)
None — every substantive claim in this document was verified against the live codebase or a live interpreter run in this session.

## Metadata

**Confidence breakdown:**
- Standard stack / architecture: HIGH — this is 100% internal-codebase augmentation; every pattern cited is read directly from the files this phase will modify, not inferred from documentation or training data
- Pitfalls: HIGH — all four documented pitfalls were discovered by tracing actual call graphs and, in two cases (Rapid7's error, the SyncStatusPill bug), verified by direct execution/exact-value comparison, not speculation
- Validation architecture: HIGH for backend (six precedent MockTransport test files provide an unambiguous template); MEDIUM for frontend component-test correction scope (the exact shape of the post-fix `SyncStatusPill` test values depends on the planner's choice of where to normalize SUCCESS→ok, which is Claude's-discretion-shaped, not yet decided)

**Research date:** 2026-07-27
**Valid until:** Effectively indefinite for the codebase-state claims (they describe code at a specific commit, re-verify if `main` moves significantly before planning executes); ~30 days for any external-facing claims (none load-bearing in this document — no third-party API version claims were made without a direct source read)
