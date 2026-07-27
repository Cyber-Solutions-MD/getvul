# Phase 23: Ingestion Reliability Precursor - Context

**Gathered:** 2026-07-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Make ingestion trustworthy — the grounding-data reliability floor every later AI phase (24–28) depends on. Specifically:

- Fix the Wiz and Rapid7 connectors so each completes a full sync end-to-end (REL-01, REL-02).
- Give all six scanner connectors (CrowdStrike, Nessus, Defender, Wiz, Qualys, Rapid7) HTTP-layer integration tests covering auth + pagination + `fetch_vulnerabilities` mapping (REL-03).
- Let an analyst **create** (not just status-sync) a Jira ticket from a vulnerability (REL-04).
- **Finish** GitHub ticketing end-to-end — create + sync (REL-05). *(Decided: finish, not retire.)*
- Surface per-connector sync health (status, last-sync, last-error, more) in the Connectors UI (REL-06).

Out of scope for this phase: any AI functionality (Phases 24–28), a connector retry/backoff refactor, and natural-language query (deferred to v3.1). No new capabilities — this clarifies HOW to close the six REL gaps.

</domain>

<decisions>
## Implementation Decisions

### Connector bug fixes (REL-01, REL-02) — mechanical, via the base contract
- **D-01:** Wiz `authenticate()` must return `bool` (`True` on success) to satisfy `BaseConnector.authenticate() -> bool` ("Returns True on success"). Today it is typed `-> None`, so a successful auth returns falsy and the sync harness treats it as failure. Fix the return-type wiring end-to-end (method body + any call site checking the result).
- **D-02:** Rapid7 gets a real `async def authenticate(self, credentials, config) -> bool` and a **no-arg `__init__`** to match the harness's no-arg instantiation pattern (every other connector is constructed no-arg, then `authenticate()` is called). Today Rapid7 takes `config` in `__init__` and has no `authenticate()`, so the harness `TypeError`s. Move credential/base_url capture out of `__init__` into `authenticate()`.
- **D-03:** Acceptance bar for "full sync end-to-end" (REL-01/02) is a **CI-runnable `httpx.MockTransport` integration test** (authenticate → paginate → `fetch_vulnerabilities` → normalized records), no live credentials. This same test doubles as the connector's REL-03 coverage. No live-credential smoke is required (BYOK / no creds in CI).

### Connector HTTP-layer tests (REL-03)
- **D-04:** Harness is **`httpx.MockTransport`** — matches the six existing connector/client test files (`test_directory_connectors.py`, `test_ticketing_clients.py`, `test_mdm_hr_connectors.py`, `test_okta_sync.py`, `test_intune_sync.py`, `test_provider_stubs.py`). Do NOT introduce `respx` / `pytest-httpx`. Tests live in `backend/tests/test_connectors/` (currently empty except `__init__.py`).
- **D-05:** Per connector assert: (1) auth success **and** failure handling, (2) **multi-page pagination followed to completion** (cursor/page loop, not just page 1), (3) `fetch_vulnerabilities` maps a fixture response **field-for-field** into `NormalizedVulnerability`.

### Ticket-create generalization (REL-04) — provider dispatch
- **D-06:** Build a **provider-dispatch protocol** — one ticketing-client interface (create / get / close / comment) that `AsanaClient`, `JiraClient`, and `GitHubClient` all satisfy; the service + rule engine pick the impl by `provider`. Replaces the current Asana-hardcoded call sites. This is also the seam Phase 27's multi-provider AI ticket-drafting plugs into.
- **D-07:** Dispatch covers **all three create paths** — `create_tickets` (per-vuln), `create_host_ticket`, and `create_remediation_ticket` — so Jira + GitHub work for per-vuln, host, and remediation tickets alike. No Asana-only paths left behind.
- **D-08:** **Consolidate to one canonical `JiraClient`** under `app/ticketing/` with create + get + close + comment. Today there are two: `app/connectors/jira_client.py` (`create_issue`, imported by `daily_sync`) and `app/ticketing/jira_client.py` (`create_ticket`). Pick/merge into the `app/ticketing/` one, delete the other, repoint `daily_sync`'s import.
- **D-09:** Rule engine (`ticketing/rule_engine.py`) honors the **per-rule `provider`** via the dispatch protocol (the action dict already reads `action.get("provider", "ASANA")`); default stays `ASANA` for back-compat. Removes the hardcoded `AsanaClient` construction there.
- **D-10:** Generalize the router's `_get_asana_client` into a **`_get_ticketing_client(provider)`** helper that resolves the right connector config + Fernet-decrypts credentials per provider, mirroring the existing Asana pattern.

### GitHub ticketing — FINISH (REL-05)
- **D-11:** Wire the (already fully-built) `GitHubClient` into the generalized create path + `daily_sync` status-sync + rule engine, and expose `GITHUB` as a create provider in the UI. Today `GitHubClient` is complete but referenced nowhere outside its own file/tests — an orphaned stub.
- **D-12:** GitHub sync-back = **inbound state map + auto-close parity**: `daily_sync` reads issue state via `get_issue` (`closed` → GetVul ticket `completed` / linked vuln `REMEDIATED`); and when all linked vulns resolve, GetVul PATCHes the issue to `state=closed`, mirroring the existing Asana auto-close. `get_watchers()` stays a `[]` stub (GitHub has no per-issue watcher primitive — local `ticket_watchers` remain the source of truth).
- **D-13:** GitHub connector-config model: `connector_type` `GITHUB`, config fields token / owner / repo (credentials Fernet-encrypted like every other connector).

### Ticket-create UX (REL-04)
- **D-14:** Extend the existing drill-panel create affordance (`use-create-ticket.ts` / `drill-content.tsx`) into a **provider picker** — the analyst chooses the provider (Asana / Jira / GitHub) at create time, filtered to configured+enabled providers.
- **D-15:** The picker's "configured providers" list comes from a **backend endpoint** (which ticketing providers are configured + enabled for the tenant), not client-side derivation — authoritative on credential/enabled state, and reused by Phase 27.

### Connector health surface (REL-06)
- **D-16:** **last-error, inline-on-failure**: show a one-line, severity-colored error summary on the connector card **only when** `last_sync_status` is failed/error, with expand/hover for the full message + timestamp. Healthy connectors stay clean. Reuses the existing error-state visual language + `SyncStatusPill` (already renders status; card already shows last-sync-time + record count).
- **D-17:** **next scheduled sync** line — frontend-derived from `sync_interval_minutes` + `last_sync_at` ("next sync in ~Xm"). No backend change.
- **D-18:** **consecutive-failure count** — new backend counter column on the connector config + migration + sync-harness increment (on failure) / reset (on any success) logic; surface "failed N times in a row" to distinguish a blip from a persistent outage.
- **D-19:** Sync error-capture shape (feeds D-16/D-18): store a **sanitized, truncated** error string (exception type + message, capped length), passed through the **Phase-7 recursive secret-redaction** so tokens/credentials never land in `last_error` or logs. The failure counter increments on any failed sync and resets to 0 on any success. Add `last_error` to the backend connector-config model + frontend `ConnectorConfig` type (frontend type has no such field today).
- **D-20:** Migration/backfill for the two new columns: `last_error` nullable (default NULL); `consecutive_failure_count` INTEGER NOT NULL default 0 for existing rows.

### Hardening
- **D-21:** Rapid7 `verify=False` (TLS validation OFF) becomes a **per-connector `verify_tls` config field, default `True`**. On-prem InsightVM on self-signed/internal-CA certs can explicitly opt out; everyone else gets validated TLS. Closes the silent MITM exposure without breaking on-prem deploys.
- **D-22:** Retry/rate-limit behavior stays **per-connector** (Wiz 5-attempt 429 loop, GitHub single 429 retry, Rapid7 none) — REL-03 tests just pin each connector's existing behavior. No shared retry-helper refactor this phase (would be scope creep for a precursor).

### Provider modeling
- **D-23:** Formalize a **Python Enum (backend) + shared TS union type (frontend)** for ticketing providers, replacing scattered uppercase/lowercase string literals, now that there are three real create providers. Backend stores/compares via the enum; the existing "uppercase backend / lowercase frontend" wire convention is preserved at the serialization boundary (see `CR-06` note in `service.py`).

### Claude's Discretion
- Exact enum member values, endpoint route naming, and Alembic migration numbering (next in `backend/alembic/versions/`).
- Exact truncation length + which exception fields compose the sanitized `last_error` string.
- Whether the ticketing-client interface is a `typing.Protocol` vs an ABC — planner's call, following existing codebase idiom.
- Field-mapping fixtures for each connector's REL-03 test (derive from each connector's real query/response shape).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` §"Ingestion Reliability (REL)" — REL-01..06 acceptance criteria, BYOK foundational principle.
- `.planning/ROADMAP.md` §"Phase 23: Ingestion Reliability Precursor" — goal, 5 success criteria, dependency (nothing; first milestone phase).

### Research (v3.0 grounding rationale — why REL matters before AI)
- `.planning/research/PITFALLS.md` — esp. the "treat every scanner-sourced text field as untrusted, forever, at the type level" framing (Pitfall 1) and the "Six scanner connectors … treating post-ingestion Postgres rows as trusted" integration gotcha. Phase 23 doesn't build AI, but its connectors are the untrusted-data sources those later guardrails wrap.
- `.planning/research/SUMMARY.md`, `.planning/research/ARCHITECTURE.md` — connector + ticketing architecture context for the milestone.

### Backend — connectors (bug fixes + tests)
- `backend/app/connectors/base.py` — `BaseConnector.authenticate() -> bool` contract (D-01/D-02 anchor) + `NormalizedVulnerability` dataclass (D-05 mapping target).
- `backend/app/connectors/wiz.py` — REL-01: `authenticate()` typed `-> None` (line ~155); GraphQL cursor pagination in `_paginate` (line ~228).
- `backend/app/connectors/rapid7.py` — REL-02: no `authenticate()`, `__init__(config)` (line ~25), `verify=False` (line ~45, D-21), page-loop pagination (`_paginate`, line ~55).
- `backend/app/connectors/{crowdstrike,defender,nessus,qualys}.py` — the other four connectors needing REL-03 tests.
- `backend/app/connectors/sync.py`, `backend/app/connectors/scheduler.py` — the sync harness that instantiates connectors + calls `authenticate()`; where D-18/D-19 failure-capture/counter logic lands.
- `backend/tests/test_provider_stubs.py`, `backend/tests/test_directory_connectors.py`, `backend/tests/test_ticketing_clients.py` — the `httpx.MockTransport` convention to mirror (D-04).

### Backend — ticketing (provider dispatch + GitHub finish)
- `backend/app/ticketing/service.py` — Asana-hardcoded `create_tickets` / `create_host_ticket` / `create_remediation_ticket` (D-06/D-07) + `sync_ticket_status` (Asana-only) + auto-close pattern to mirror for GitHub (D-12).
- `backend/app/ticketing/rule_engine.py` — hardcoded `AsanaClient` (line ~327); `action.get("provider", "ASANA")` already present (line ~138) → D-09.
- `backend/app/ticketing/router.py` — `_get_asana_client` (line ~56) → generalize to `_get_ticketing_client(provider)` (D-10); ticket-create endpoint (line ~206).
- `backend/app/ticketing/daily_sync.py` — provider-dispatch precedent for **sync** (ASANA branch ~50, JIRA branch ~56); imports `app/connectors/jira_client.py` (D-08 repoint).
- `backend/app/ticketing/github_client.py` — the complete-but-orphaned client to wire (D-11/D-12).
- `backend/app/ticketing/jira_client.py` (`create_ticket`) **and** `backend/app/connectors/jira_client.py` (`create_issue`) — the two clients to consolidate (D-08).
- `backend/app/ticketing/asana_client.py` — the reference client shape the dispatch protocol generalizes.
- `backend/alembic/versions/` — latest migration to sequence D-20 after (026/027/028 are the most recent ticketing migrations).

### Frontend — health UI + create UX
- `frontend/src/components/connectors/connector-card.tsx` — already renders `SyncStatusPill` + last-sync-time + record count; add last-error (D-16) + next-sync (D-17) + failure-count (D-18).
- `frontend/src/components/connectors/sync-status-pill.tsx`, `connector-mark.tsx` — existing health/provider primitives to reuse.
- `frontend/src/types/connector.ts` — `ConnectorConfig` type; add `last_error` (+ counter) field (D-19).
- `frontend/src/lib/queries/use-connectors-admin.ts` — connector-config query (`ConnectorConfigResponse`).
- `frontend/src/lib/mutations/use-create-ticket.ts`, `frontend/src/components/vulnerabilities/drill-content.tsx` — existing per-vuln create affordance to extend into a provider picker (D-14/D-15).

### Design system (UI work — auto-loads per CLAUDE.md)
- `.claude/skills/sketch-findings-getvul/references/state-patterns.md` — error/empty/loading patterns (D-16 error surface).
- `.claude/skills/sketch-findings-getvul/references/visual-language.md` — status / provider visual language.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `httpx.MockTransport` test harness — six existing test files already use it; REL-03 + REL-01/02 acceptance tests extend the same pattern (no new mocking dependency).
- `SyncStatusPill`, `ConnectorMark`, `EmptyState`, drill-panel `use-create-ticket.ts` — all exist; REL-06 + REL-04 UX reuse rather than rebuild.
- `daily_sync.py` already dispatches by provider for **status sync** (ASANA/JIRA) — the create-side dispatch (D-06) can mirror its shape.
- Phase-7 recursive secret-redaction — reuse for D-19 (do not build a parallel redactor).
- Asana auto-close logic in `sync_ticket_status` — the template for GitHub auto-close (D-12).

### Established Patterns
- All connectors: no-arg `__init__` + `authenticate(credentials, config) -> bool` + `fetch_vulnerabilities()` (Rapid7 is the lone deviation D-02 fixes).
- Connector credentials Fernet-encrypted in connector config; decrypt-on-use (D-10/D-13 follow this).
- Provider stored uppercase backend, lowercased at the frontend serialization boundary (`CR-06`) — preserved by D-23.
- Tenant scoping on every query (`tenant_id`) — new endpoint (D-15) and columns (D-20) must honor it.

### Integration Points
- Sync harness (`connectors/sync.py` + `scheduler.py`) — where failure capture + consecutive-failure counter hook in.
- Ticketing router create endpoint + rule engine — where provider dispatch replaces Asana-hardcoding.
- Drill panel (vulnerabilities) — where the create provider-picker lives; also where Phase 24 "Explain" and Phase 27 AI-draft will land.
- New backend endpoint for configured ticketing providers — reused by Phase 27.

</code_context>

<specifics>
## Specific Ideas

- GitHub is a **wanted** ticketing destination (user chose finish over retire) — treat it as a first-class provider equal to Asana/Jira, not a stub.
- Provider abstraction is deliberately built "properly" now (all three create paths, formal enum) specifically so Phase 27's multi-provider AI drafting inherits it without rework — avoid leaving partial/Asana-only paths.
- "Health at a glance" is the REL-06 intent — failing connectors must be spottable without opening each one (drives the on-card error surface + failure counter).

</specifics>

<deferred>
## Deferred Ideas

- Shared connector retry/backoff helper (standardize 429/5xx across all six connectors) — out of scope; per-connector behavior stays, tests pin it (D-22). Candidate for a later hardening pass.
- Forcing Rapid7 TLS fully ON (no opt-out) — rejected in favor of the `verify_tls` opt-out (D-21); revisit if on-prem self-signed support is ever dropped.
- Natural-language query over the inventory (AINL-01) — explicitly deferred to v3.1 per REQUIREMENTS.md.
- Reconcile the Phase-8 memory note ("6 vuln-scanner connector tests shipped") against the empty `backend/tests/test_connectors/` — a note for the planner to verify where/whether those tests exist before assuming REL-03 is greenfield vs. augmenting.

</deferred>

---

*Phase: 23-ingestion-reliability-precursor*
*Context gathered: 2026-07-27*
