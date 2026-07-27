---
phase: 23-ingestion-reliability-precursor
reviewed: 2026-07-27T00:00:00Z
depth: standard
files_reviewed: 26
files_reviewed_list:
  - backend/app/connectors/nessus.py
  - backend/app/connectors/rapid7.py
  - backend/app/connectors/router.py
  - backend/app/connectors/schemas.py
  - backend/app/connectors/service.py
  - backend/app/connectors/sync.py
  - backend/app/connectors/tester.py
  - backend/app/connectors/wiz.py
  - backend/app/ticketing/daily_sync.py
  - backend/app/ticketing/dispatch.py
  - backend/app/ticketing/github_client.py
  - backend/app/ticketing/jira_client.py
  - backend/app/ticketing/models.py
  - backend/app/ticketing/providers.py
  - backend/app/ticketing/router.py
  - backend/app/ticketing/rule_engine.py
  - backend/app/ticketing/service.py
  - frontend/src/components/connectors/connector-card.tsx
  - frontend/src/components/connectors/sync-status-pill.tsx
  - frontend/src/components/ui/ConfirmModal.tsx
  - frontend/src/components/vulnerabilities/drill-content.tsx
  - frontend/src/components/vulnerabilities/ticket-provider-picker.tsx
  - frontend/src/lib/mutations/use-create-ticket.ts
  - frontend/src/lib/queries/use-connectors-admin.ts
  - frontend/src/lib/queries/use-ticketing-providers.ts
  - frontend/src/lib/ticketing/providers.ts
  - frontend/src/types/connector.ts
findings:
  critical: 3
  warning: 2
  info: 2
  total: 7
status: issues_found
---

# Phase 23: Code Review Report

**Reviewed:** 2026-07-27T00:00:00Z
**Depth:** standard
**Files Reviewed:** 26
**Status:** issues_found

## Summary

The core multi-provider ticketing dispatch fix (D-07/D-10) is implemented
correctly on the primary desktop path: `dispatch.py`'s adapters route to the
concrete client that matches `TicketProvider`, `service.py`'s create/sync/close
functions all take an already-resolved `TicketingClient` instead of hardcoding
Asana, and `router.py`'s `_get_ticketing_client` resolves a tenant-scoped,
provider-scoped connector before building that client. `Ticket.provider`
persistence matches the client that was actually dispatched to on every path
I traced (`create_tickets`, `create_host_ticket`, `create_remediation_ticket`,
`sync_ticket_status`, `close_ticket`, `run_rule`). The `connectors/jira_client.py`
deletion (D-08) left no dangling imports — `app/ticketing/jira_client.py` is the
sole surviving Jira client and every importer references it correctly.

However, I found three BLOCKER-level defects, two of which reintroduce or leak
around the exact class of bug this phase set out to fix:

1. **The mobile "create ticket" confirm flow bypasses provider selection
   entirely** and silently defaults to Asana regardless of the tenant's
   actual configured/selected provider — the same bug class (D-07) resurfacing
   on a code path this phase didn't audit.
2. **A duplicate `POST /sync-status` route** in `ticketing/router.py` shadows
   the legacy `daily_sync`-driven handler, making its ticket-sync audit trail
   entry permanently unreachable via the API.
3. **Unredacted secrets can still reach structured logs** via `SyncLog.error_message`,
   which is never passed through `_sanitize_error` (only `ConnectorConfig.last_error`
   is), and is then logged verbatim by the scheduler on every background sync.

TLS verification threading (nessus.py/rapid7.py/tester.py) is sound — every
`httpx.AsyncClient` construction I found defaults `verify=True` and only
flips to caller-supplied `config.get("verify_tls", True)`; there is no reachable
`verify=False` default.

## Critical Issues

### CR-01: Mobile ticket-creation confirm flow never lets the analyst pick a provider — always defaults to Asana

**File:** `frontend/src/components/vulnerabilities/drill-content.tsx:55-60, 142-168, 314-333`
**Issue:**
`DrillContent`'s `renderConfirm` slot (used by the mobile nested-drawer
confirmation in `drill-panel-mobile.tsx`) has this signature:

```ts
renderConfirm?: (args: {
  open: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  cveLabel: string;
}) => React.ReactNode;
```

It carries no `ticketProvider` value, no `onChange`, and no disabled/gating
signal. When `renderConfirm` is supplied, `DrillContent` renders **only** that
slot (line 314-320) — the `<TicketProviderPicker>` and its `confirmDisabled`
gate (used on the desktop `ConfirmModal` branch, lines 322-332) are skipped
entirely. `ticketProvider` state (line 75) therefore stays `null` for the
whole life of the mobile flow, and `fireTicket` (line 151) always falls back to:

```ts
provider: ticketProvider ?? 'ASANA',
```

`drill-panel-mobile.tsx` (confirmed caller) wires its own bare confirm dialog
through this exact slot with no provider picker of its own — so on mobile,
every ticket-creation is fired with `provider: 'ASANA'`, regardless of which
provider the tenant has configured or would have chosen. A tenant with only
Jira/GitHub configured gets a hard 400 ("No Asana connector configured") on
every mobile ticket creation; a tenant with multiple providers configured has
no way to choose on mobile and silently gets Asana every time. This is the
same "provider silently defaults to Asana" defect class (D-07) that this
phase's backend work fixed, now reintroduced on the frontend for the mobile
surface.

**Fix:** Extend the `renderConfirm` callback args to pass through
`ticketProvider`/`setTicketProvider` (or the whole picker element) so
`drill-panel-mobile.tsx` can render `<TicketProviderPicker>` inside its nested
dialog and gate its confirm button the same way `ConfirmModal`'s
`confirmDisabled={!ticketProvider}` does on desktop, e.g.:

```ts
renderConfirm?: (args: {
  open: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  cveLabel: string;
  ticketProvider: TicketProvider | null;
  onProviderChange: (p: TicketProvider) => void;
}) => React.ReactNode;
```

and require the mobile confirm dialog to render `<TicketProviderPicker>` and
disable its confirm button while `ticketProvider` is null.

---

### CR-02: Duplicate `POST /sync-status` route — the legacy handler is permanently unreachable

**File:** `backend/app/ticketing/router.py:348-359` and `backend/app/ticketing/router.py:1251-1264`
**Issue:** Two handlers are registered on the exact same path + method on the
same `router` object:

```python
@router.post("/sync-status")          # line 348 — NEW in this phase (D-10)
async def sync_all_ticket_statuses(...):
    resolver = await _make_client_resolver(db, user.tenant_id)
    result = await sync_ticket_status(db, user.tenant_id, resolver)
    await db.commit()
    return result
```

```python
@router.post("/sync-status")          # line 1251 — pre-existing
async def trigger_ticket_sync(...):
    from app.ticketing.daily_sync import run_daily_ticket_sync
    result = await run_daily_ticket_sync(db)
    await audit(db, user, "ticket.sync_status", "ticket", None, result)
    await db.commit()
    return result
```

FastAPI/Starlette matches routes in declaration order, so every real
`POST /api/v1/tickets/sync-status` request is dispatched to
`sync_all_ticket_statuses` (line 348); `trigger_ticket_sync` (line 1251) is
dead code that can never execute via the API. Confirmed via `git diff
8f1b87f -- app/ticketing/router.py`: this phase added the first handler above
the pre-existing second one without removing/merging it. Consequences:
- `trigger_ticket_sync`'s `audit(db, user, "ticket.sync_status", ...)` call
  never fires — the audit trail for a manual sync trigger silently never
  records this action.
- `daily_sync.run_daily_ticket_sync`'s per-provider sync/comment logic is now
  reachable only from the scheduler (`app/connectors/scheduler.py`), never
  from the manual "Sync ticket statuses" UI action — two divergent
  implementations of the same feature exist in the codebase with no test or
  route exercising the second one.

No test in `tests/test_ticketing_dispatch.py` or elsewhere hits this route, so
nothing currently catches the shadowing.

**Fix:** Remove one of the two handlers. Given `sync_all_ticket_statuses`
correctly dispatches by each ticket's own provider (D-10) and
`trigger_ticket_sync` still routes through the older `daily_sync.py` path,
delete `trigger_ticket_sync` (lines 1251-1264) and, if the
`audit(db, user, "ticket.sync_status", ...)` call and/or `daily_sync`-specific
stats are still wanted, fold them into `sync_all_ticket_statuses` instead.

---

### CR-03: `SyncLog.error_message` bypasses the secret-redaction machinery and is logged verbatim

**File:** `backend/app/connectors/sync.py:192-199`, consumed at `backend/app/connectors/scheduler.py:38-46`
**Issue:** In `run_sync`'s exception handler:

```python
except Exception as e:
    sanitized = _sanitize_error(e)
    logger.error("sync_error", error=sanitized)
    log.status = "FAILED"
    log.error_message = str(e)[:2000]                       # <-- RAW, unsanitized
    connector_config.last_sync_status = "FAILED"
    connector_config.consecutive_failure_count = (connector_config.consecutive_failure_count or 0) + 1
    connector_config.last_error = sanitized                  # <-- sanitized
```

`connector_config.last_error` (the field this phase's D-18/D-19 work targets)
correctly goes through `_sanitize_error`. But `log.error_message` — persisted
on the `SyncLog` row and passed straight through to structured logging by the
scheduler:

```python
# app/connectors/scheduler.py:38-46
logger.info(
    "background_sync_complete",
    connector_id=connector_id,
    connector_type=connector.connector_type,
    status=log.status,
    records_fetched=log.records_fetched,
    records_created=log.records_created,
    error=log.error_message,     # <-- raw exception string, secrets intact
)
```

— never passes through `_sanitize_error`. Any `Bearer <token>` / `Basic
<creds>` / API-key-shaped substring echoed back in an upstream HTTP error body
(the exact threat `_sanitize_error`'s docstring and `_SECRET_PATTERN` exist
to catch) survives into both the `sync_logs` table and the application's
structured log stream on every background sync failure. The existing test
`tests/test_connector_health.py::test_scheduler_path_failure_parity` even
constructs an exception containing `"Authorization: Bearer sk-scheduler-secret"`
and drives it through `scheduler_module._run_single_sync`, but only asserts
on `connector.last_error` — it does not (and currently cannot) assert that the
secret didn't reach `log.error_message` or the log line, because it does.

**Fix:** Sanitize `log.error_message` the same way `last_error` is sanitized:

```python
except Exception as e:
    sanitized = _sanitize_error(e)
    logger.error("sync_error", error=sanitized)
    log.status = "FAILED"
    log.error_message = sanitized
    ...
    connector_config.last_error = sanitized
```

(`_sanitize_error`'s 500-char cap is a reasonable value for `log.error_message`
too — `SyncLog.error_message` is `Text`, unbounded, so this is a compatible
change.) Also add a regression test that drives a secret-bearing exception
through `run_sync`/`scheduler._run_single_sync` and asserts the secret is
absent from `log.error_message`, not just `connector_config.last_error`.

## Warnings

### WR-01: `TicketRuleAction.provider` has no enum/pattern validation — an unhandled `ValueError` can 500 the manual rule-run endpoint

**File:** `backend/app/ticketing/schemas.py:100-107`, `backend/app/ticketing/rule_engine.py:155-156`, `backend/app/ticketing/router.py:1205-1248`
**Issue:** `TicketCreateRequest.provider` and `HostTicketCreateRequest.provider`
are both constrained with `Field(..., pattern="^(ASANA|JIRA|GITHUB)$")`, but
`TicketRuleAction.provider` (the schema backing `TicketRule.action.provider`,
settable via `POST /rules` / `PATCH /rules/{id}`) is just `provider: str =
"ASANA"` with no pattern/enum constraint. `rule_engine.run_rule()` then does:

```python
provider = action.get("provider", "ASANA")
provider_enum = TicketProvider(provider)   # raises ValueError for any other string
```

`router.run_rule_now` (the manual "run rule now" endpoint) calls `run_rule(...)`
with no surrounding `try/except` — a rule saved with a garbage
`action.provider` (e.g. `"asana"` lowercase, or any typo) will raise an
unhandled `ValueError` that FastAPI turns into a raw 500, not a clean 400.
(The scheduler's `run_all_due_rules` does wrap this same call in
`try/except Exception`, so the automated path degrades gracefully — only the
manual-trigger endpoint is exposed.)

**Fix:** Add the same pattern constraint used elsewhere:
```python
provider: str = Field("ASANA", pattern="^(ASANA|JIRA|GITHUB)$")
```
and/or wrap the `run_rule(...)` call in `router.run_rule_now` in a
`try/except ValueError` that raises `HTTPException(400, ...)`.

### WR-02: `WizConnector.authenticate` silently ignores its `config` parameter — no TLS-toggle parity with Nessus/Rapid7

**File:** `backend/app/connectors/wiz.py:155-189`
**Issue:** `NessusConnector.authenticate` and `Rapid7Connector.authenticate`
both read `config.get("verify_tls", True)` and thread it into their
`httpx.AsyncClient(..., verify=...)` construction (correctly defaulting to
`True`). `WizConnector.authenticate` accepts the same `config:
dict[str, Any] | None = None` parameter but never reads it — the
`httpx.AsyncClient(timeout=httpx.Timeout(60.0))` at line 169 has no `verify=`
argument at all (so it inherits httpx's secure default, which is fine), but
this means Wiz has no way to ever support a `verify_tls` override the way the
other two on-prem-capable scanners do, and the parameter is dead code. Not
exploitable today (Wiz is SaaS-only and the default is secure), but it's an
inconsistency worth resolving explicitly rather than by omission, especially
since `CONNECTOR_TYPES["WIZ"]` in `schemas.py` has no `verify_tls` field while
`NESSUS`/`RAPID7` do — so the schema and the connector are at least
consistent with each other, just silently inconsistent with the other two
connector types' pattern.

**Fix:** Either document explicitly (a one-line comment) that Wiz
intentionally never supports `verify_tls` because it's SaaS-only, or drop the
unused `config` parameter's implication of use and lint-suppress/rename it to
signal intent.

## Info

### IN-01: `bulk_ticket_action`'s "comment" branch silently no-ops for a URL with zero matching ticket rows

**File:** `backend/app/ticketing/router.py:394-420`
**Issue:** For each `url` in the request, tickets are looked up
tenant-scoped; if the query returns zero rows (e.g., a stale/already-deleted
ticket URL), the inner `for t in tickets:` loop never executes, and neither
`results["processed"]` nor `results["errors"]` is incremented for that URL —
the caller has no signal that a particular ticket URL in their bulk selection
was silently skipped.

**Fix:** Track requested vs. processed URL count and surface the delta (e.g.
`results["errors"] += 1` when a URL yields no ticket rows), or explicitly
document current best-effort semantics.

### IN-02: `_upsert_asset`/`_upsert_vulnerability` in `sync.py` build significant per-record classification/enrichment inline (~90+ lines combined)

**File:** `backend/app/connectors/sync.py:208-300`
**Issue:** `_upsert_asset` is ~90 lines with a long chain of `getattr(v,
"...", None)` conditionals repeated for both the create and update branches.
This isn't new to this phase, but it's a maintainability hazard for future
per-source enrichment fields (each new field currently means editing this one
function in two near-identical places). No correctness defect found, but flag
for a follow-up refactor (e.g., a single "enrichment fields" dict driven by a
declarative field map) rather than continuing to hand-add `if getattr(...)`
branches per connector-specific field.

**Fix:** Consider extracting a small `_ENRICHMENT_FIELDS: list[str]` and a
loop, or otherwise deduplicating the create vs. update branches, next time a
new source enrichment field is added.

---

_Reviewed: 2026-07-27T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
