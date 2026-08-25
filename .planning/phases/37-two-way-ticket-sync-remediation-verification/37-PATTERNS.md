# Phase 37: Two-Way Ticket Sync & Remediation Verification - Pattern Map

**Mapped:** 2026-08-14
**Files analyzed:** ~8 capabilities (SYNC-01..04), mostly EXTENSIONS of existing files
**Analogs found:** 8 / 8 (every capability has a strong in-repo analog — this is not greenfield)

> Read alongside `37-CONTEXT.md` (locked decisions D-01..D-04) and `REQUIREMENTS.md` (SYNC-01..04).
> **The core discipline for this phase:** every finding status write routes through the single
> `mark_vulnerability_remediated` helper (Phase 36 / D-09 / Pitfall 6). Auto-close, reopen, and
> ticket-driven transitions all inherit that rule. Never write `Vulnerability.status` directly.

---

## File Classification

| Capability to build | Role / Data flow | Closest existing analog | Match quality |
|---------------------|------------------|-------------------------|---------------|
| SYNC-01 scheduler write-back pass (generalize inbound to all 3 providers → write onto finding) | service / event-driven poll | `backend/app/ticketing/daily_sync.py::run_daily_ticket_sync` + `_sync_{asana,jira,github}_tickets` | exact (extend in place) |
| SYNC-01 unified provider status fetch | utility / request-response | `backend/app/ticketing/dispatch.py::TicketingClient` protocol + `sync_ticket_status`'s `ClientResolver` | exact |
| SYNC-01 external→internal status mapping table | utility / transform | `backend/app/ticketing/service.py::_is_ticket_completed` (line 1092) | role+flow match (extend, don't replace) |
| SYNC-02 finding auto-close (rescan-verified) | service / state-transition | `backend/app/vulnerabilities/service.py::mark_vulnerability_remediated` (line 370) | exact (route through it, per D-09) |
| SYNC-02 "absent from N scans" bookkeeping | model + service / event-driven | `Vulnerability.last_seen_at` refresh in `backend/app/connectors/sync.py::_upsert_vulnerability` (line 376) + `SyncLog.status=="SUCCESS"` signal | partial (signal exists; counter is new) |
| SYNC-03 reopen-on-recurrence (resurrect + relink) | service / state-transition | `_upsert_vulnerability` existing-row branch (line 375-393, dedupe unique key) | partial (identity-key match; reopen logic is new) |
| SYNC-04 per-connector last-successful-sync surfacing | model + service + schema | `ConnectorConfig.last_sync_at/last_sync_status/consecutive_failure_count` set by `directory_sync.py` / `sync.py`; surfaced via `connectors/router.py::get_sync_status` + `ConnectorResponse` | exact |
| Scheduler-originated audit of every status write | utility / event | `backend/app/vulnerabilities/sla_tier_service.py::_audit_escalation_fire` (line 309) | exact (NOT `app/audit.py::audit`) |
| New DB table/columns (clean-scan counter / sync-state) | migration + model | `RemediationEvent` model + `alembic/versions/047_add_remediation_events.py` | exact |
| Backend tests (httpx-mocked provider sync) | test | `backend/tests/test_github_sync.py` + `test_ticketing_clients.py` MockTransport convention | exact |

---

## Pattern Assignments

### SYNC-01 — Scheduler inbound write-back pass (`ticketing/daily_sync.py`)

**Analog / extend in place:** `backend/app/ticketing/daily_sync.py`

The three `_sync_<provider>_tickets` functions ALREADY do a partial inbound read + auto-close.
Phase 37 generalizes the "ticket done → drive finding workflow state" half. The template to mirror
is the Asana branch's first pass (lines 225-251):

```python
# daily_sync.py:236-251 — the existing inbound-status → finding branch to generalize
if task.get("completed"):
    ticket.external_status = "completed"
    ticket.resolved_at = datetime.now(UTC)
    resolved += 1
    vuln = (await db.execute(select(Vulnerability).where(...))).scalar_one_or_none()
    if vuln and vuln.status not in ("REMEDIATED", "SUPPRESSED"):
        # D-09/Pitfall 6: routed through the single helper (never `vuln.status = ...`)
        from app.vulnerabilities.service import mark_vulnerability_remediated
        await mark_vulnerability_remediated(db, vuln)
    else:
        ticket.external_status = "open"
```

Jira branch (286-374) and GitHub branch (377-468) are byte-parallel to this. Per **D-03**, Phase 37
must SPLIT this: a "ticket done" external status must NOT force-close the finding (rescan is truth).
It should drive *workflow* state (→ IN_PROGRESS) and comment context, while closure stays gated on
SYNC-02. Concretely: keep the `mark_vulnerability_remediated` call **only** on the rescan path
(SYNC-02); on the ticket-done path, transition to IN_PROGRESS + audit, do not close.

**Scheduler wiring — DO NOT add a new scheduler.** Extend the existing 24h-gated tick block:

```python
# connectors/scheduler.py:342-355 — the existing ticket-sync tick block (extend, don't add a job)
global _last_ticket_sync
if _last_ticket_sync is None or (now - _last_ticket_sync).total_seconds() >= 86400:
    async with async_session_factory() as db:
        from app.ticketing.daily_sync import run_daily_ticket_sync
        result = await run_daily_ticket_sync(db)
    _last_ticket_sync = now
```
Mirror the SLA block above it (lines 327-340) for the per-tenant loop + single `await db.commit()`
per tick. Each provider/tenant error is caught and isolated (daily_sync.py:93-99) so one bad
connector never aborts the pass — reuse that try/except-per-connector shape for SYNC-04 resilience.

---

### SYNC-01 — Unified provider fetch + status mapping

**Analog (preferred, newer):** `backend/app/ticketing/dispatch.py` — the `TicketingClient` Protocol
(create/get/comment/close, line 24) + `AsanaAdapter`/`JiraAdapter`/`GitHubAdapter` +
`build_ticketing_client(provider, credentials, config)` (line 121). This is the clean unified surface
that post-dates the three hand-rolled `_sync_*` branches. Prefer building the write-back on
`client.get(ref)` (raw payload) + the mapping function below, over duplicating provider `if` ladders.

**Provider status-fetch calls already exist:**
- `jira_client.py::get_issue` (line 156) → returns raw dict; read `fields.status.statusCategory.key` + `fields.status.name`.
- `asana_client.py::get_task` (line 164) → read `completed` bool.
- `github_client.py::get_issue` (line 127) → read `state` (`open`/`closed`).
All three already single-retry on HTTP 429 (`create_ticket`/`add_comment`) and return `None` (never raise) on failure — reuse for retry/resilience (SYNC-04).

**External→internal mapping table (Claude's Discretion item):** extend the ONE place that already
reads all three raw shapes:

```python
# ticketing/service.py:1092 — the single provider-shape reader. Extend to return a
# workflow-state enum ("in_progress" / "done_awaiting_rescan"), not just a done bool.
def _is_ticket_completed(provider: str, payload: dict[str, Any]) -> bool:
    if provider == TicketProvider.ASANA:  return bool(payload.get("completed"))
    if provider == TicketProvider.JIRA:   ...  # statusCategory=="done" or name in (done/closed/resolved/completed)
    if provider == TicketProvider.GITHUB: return payload.get("state") == "closed"
```
Per D-03 the new mapping must express "ticket done ≠ finding closed" — add IN_PROGRESS detection
(e.g. Jira `statusCategory=="indeterminate"`) rather than only the terminal branch.

**Manual/router inbound sync analog:** `ticketing/service.py::sync_ticket_status` (line 1112) is the
router-invoked twin of the scheduler pass, already provider-generalized via a `ClientResolver`
(groups tickets by provider, resolves one client per provider, skips unconfigured providers with a
log — line 1145-1151). Mirror its grouping + per-provider client resolution in the scheduler pass.

---

### SYNC-02 — Rescan-verified auto-close (`vulnerabilities/service.py`)

**Analog / route through:** `mark_vulnerability_remediated` (line 370) — the SINGLE
REMEDIATED-transition helper. It sets `status="REMEDIATED"` + `remediated_at=now` AND inserts the
durable `RemediationEvent` (MTTR-by-tier). Every existing REMEDIATED site already funnels here
(service.py x2: `update_vulnerability_status` line 446, `bulk_update_status` line 480;
`ticketing/service.py` x2: `sync_ticket_status` 1180, `close_ticket` 1335; `daily_sync.py` x3).

```python
# vulnerabilities/service.py:370-402 — the helper auto-close MUST use (no direct status write)
async def mark_vulnerability_remediated(db, vuln) -> RemediationEvent:
    now = datetime.now(UTC)
    vuln.status = "REMEDIATED"
    vuln.remediated_at = now
    tier = _freeze_tier_at_remediation(vuln)          # freezes FINAL tier (line 356), not tier-at-detection
    duration_seconds = int((now - vuln.first_detected_at).total_seconds())
    event = RemediationEvent(tenant_id=vuln.tenant_id, vulnerability_id=vuln.id, tier_at_remediation=tier, ...)
    db.add(event)                                      # no flush/commit — caller owns the txn boundary
    return event
```

**Claude's Discretion (resolved recommendation):** auto-close should route through
`mark_vulnerability_remediated` directly (it already produces the MTTR row). If the audit trail needs
to distinguish "rescan-verified" from "ticket/manual" closure, add a `source`/`reason` param to the
helper (default preserves current callers) OR emit a distinct audit action alongside — but do NOT
fork a parallel `mark_vulnerability_rescan_verified` that skips the RemediationEvent insert (that
reintroduces the exact Pitfall 6 the single-helper discipline exists to prevent).

---

### SYNC-02 — "Absent from N scans" bookkeeping

**Signal already exists:** `connectors/sync.py::_upsert_vulnerability` refreshes `last_seen_at=now`
on every re-detection (line 376, existing-row branch). A finding whose `last_seen_at` does NOT
advance across a scan cycle is "absent." Per **D-02** only a scan from a source that *ran
successfully* counts — the success signal is `SyncLog.status == "SUCCESS"` /
`ConnectorConfig.last_sync_status == "SUCCESS"` (set in `sync.py:196-199`; a FAILED/PARTIAL sync at
`sync.py:205-209` must NOT count).

**New counter column (recommended shape):** add a per-finding `clean_scan_count` (Integer,
`server_default="0"`) mirroring `ConnectorConfig.consecutive_failure_count`
(`ticketing/models.py:55`), incremented when a successful scan of its source did NOT refresh
`last_seen_at`, reset to 0 on re-detection, and triggering auto-close at 2 (fixed default, D-02).
Model + migration style below.

---

### SYNC-03 — Reopen-on-recurrence (resurrect + relink)

**Analog / identity key:** `connectors/sync.py::_upsert_vulnerability` (line 360). It already
locates an existing finding by the dedup identity key `(tenant_id, cve_id, asset_id, source)`
(matching `Vulnerability.uq_vuln_dedup`, `vulnerabilities/models.py:49`) and updates the SAME row
(line 375) rather than inserting a duplicate. This is exactly the "re-findable by identity key"
guarantee **D-04** requires — the auto-close MUST be a *soft* close (status transition only; the row
is retained and still matches this lookup).

**What's new (extend the existing-row branch, line 375-393):** today it refreshes `last_seen_at`
but leaves `status` untouched. Add: if the matched row is a rescan-verified auto-close (REMEDIATED
via SYNC-02) and the scan re-detects it, reopen it (→ OPEN/IN_PROGRESS), reset the clean-scan
counter, and relink/re-comment its existing `Ticket` (`Ticket.vulnerability_id` FK,
`ticketing/models.py:84`) rather than creating a new ticket. Preserve `first_detected_at` so MTTR
lineage (`RemediationEvent`) is intact. Audit the reopen (scheduler-audit pattern below).

---

### SYNC-04 — Per-connector last-successful-sync surfacing

**Analog / mirror exactly:** the connector `last_sync_*` precedent, already end-to-end:

- **Write (SUCCESS):** `connectors/sync.py:196-200` and `directory_sync.py:133-135`
  set `last_sync_at`, `last_sync_status="SUCCESS"`, `last_sync_record_count`, reset
  `consecutive_failure_count=0`, clear `last_error`.
- **Write (FAILED):** `sync.py:205-209` / `directory_sync.py:139-141` set
  `last_sync_status="FAILED"`, increment `consecutive_failure_count`, store a **sanitized**
  `last_error` via `_sanitize_error` (sync.py:44 — redacts Bearer/Basic/api-key shapes; reuse this
  for any ticket-sync error persisted).
- **Model columns:** `ConnectorConfig.last_sync_at / last_sync_status / last_sync_record_count /
  consecutive_failure_count / last_error` (`ticketing/models.py:50-55`) already exist — ticketing
  connectors (ASANA/JIRA/GITHUB) currently short-circuit to SUCCESS with no data
  (`sync.py:125-131`), so Phase 37 should start populating these from the new write-back pass.
- **Durable per-run log:** `SyncLog` (`ticketing/models.py:60`) — one row per run
  (RUNNING→SUCCESS/FAILED), mirror `directory_sync.py:23-30` construction.
- **Surface (API):** `connectors/router.py::get_sync_status` (line 192) already returns
  `last_sync_at/last_sync_status/last_sync_record_count`; `ConnectorResponse`
  (`connectors/schemas.py:417-428`) already carries all five fields incl. `last_error` +
  `consecutive_failure_count`. **SYNC-04 extends this existing surface — no new screen** (CONTEXT
  D-04 discretion note). Retry mechanics: reuse the scheduler's due-interval retry
  (`scheduler.py:273-278` `sync_interval_minutes` elapsed check) — the next tick naturally retries a
  FAILED connector; no new backoff table needed for a fixed cadence.

---

### Audit — scheduler-originated status writes

**Analog / use this, NOT `app/audit.py::audit`:** `sla_tier_service.py::_audit_escalation_fire`
(line 309). The scheduler has no `CurrentUser`, and `app.audit.audit(user=None, ...)` writes
`tenant_id=uuid.UUID(int=0)` (nil tenant, `audit.py:174`) — which mis-buckets a genuinely
tenant-scoped row. The established scheduler precedent constructs `AuditLog` directly with the REAL
tenant_id and a `"system:scheduler"` sentinel user_email:

```python
# sla_tier_service.py:332-350 — the scheduler-audit pattern for every SYNC status write
log = AuditLog(
    tenant_id=tenant.id, user_id=None, user_email="system:scheduler",
    action="sla.escalation_fire", resource_type="vulnerability", resource_id=str(vuln.id),
    details={...}, ip_address=None, created_at=datetime.now(UTC),
)
db.add(log)
```
Use for: auto-close (`vuln.rescan_verified_close`), reopen (`vuln.reopen_recurrence`), inbound
workflow transition (`vuln.ticket_status_sync`). Add-then-commit within the tick's own
`await db.commit()` (audit-before-commit / fail-closed, AUDIT-01). For router-invoked paths (if any
manual re-sync endpoint), use `app/audit.py::audit(db, user, ...)` with the real user, mirroring
`ticketing/router.py:1269` (`ticket.sync_status`).

---

### New DB table / columns

**Model analog:** `RemediationEvent` / `SlaEscalationEvent` (`vulnerabilities/models.py:246, 206`).
Conventions to mirror: `Base, UUIDPrimaryKeyMixin, TimestampMixin`; `tenant_id` FK
`ondelete="CASCADE"` + `index=True`; plain `String(20)` status columns (no Python enum on the
column — codebase convention); `UniqueConstraint` for any once-only/idempotency gate (as
`uq_escalation_once`, models.py:229). For the per-finding clean-scan counter, prefer an
`Integer server_default="0"` column on `Vulnerability` mirroring `consecutive_failure_count`
(`ticketing/models.py:55`) over a new table.

**Migration analog:** `alembic/versions/047_add_remediation_events.py`. Mirror exactly:
`revision`/`down_revision` chained off the latest head (currently `047_...`); revision id ≤ 32 chars
(`alembic_version.version_num` is varchar(32)); `op.create_table` with
`postgresql.UUID(as_uuid=True)`, explicit FKs, `server_default=sa.text("now()")` timestamps;
explicit `op.create_index` for tenant_id + any FK; a symmetric `downgrade()` even if one-way in
practice. **Next revision id:** `048_...`.

---

### Backend tests

**Analog / convention:** `backend/tests/test_github_sync.py` (+ `test_ticketing_clients.py`,
`test_ticketing_dispatch.py`). Established patterns to reuse:

- **httpx mocking:** build a REAL provider client, swap its transport:
  `client._client._transport = httpx.MockTransport(handler)` (test_github_sync.py:73-78). The
  `handler` inspects `request.url.path`/`method` and returns canned `httpx.Response`s. Do NOT hit a
  live API.
- **Seed helpers:** `_seed_<provider>_connector` (encrypts creds with `encrypt_value`, splits
  token↔config), `_seed_vuln(status=...)`, `_seed_ticket(...)` — copy these signatures.
- **conftest fixtures:** `db_session`, `tenant_a`/`tenant_b` (real-Postgres behavioural surface;
  skip cleanly if Postgres unreachable, conftest.py:143-157). Note MEMORY: set
  `ENCRYPTION_KEY`/`JWT_SECRET_KEY` env vars and run per-file, not the whole `tests/` dir.
- **Scheduler-fn unit test convention:** `from app.ticketing import daily_sync as m; await m.run_daily_ticket_sync(db)` — extracted top-level async fns are directly awaitable (the `while True` loop is not). Mirror `test_connector_health.py::test_scheduler_path_failure_parity`.
- **Coverage to add:** ticket-done→IN_PROGRESS (not closed, D-03); 2-clean-scans→auto-close (D-02);
  1-clean-scan does NOT close; failed scan does NOT count as clean (D-02/D-04); recurrence reopens
  same row + relinks ticket, no duplicate (D-03); FAILED sync sets `last_sync_status`/`last_error`
  sanitized + increments `consecutive_failure_count` (SYNC-04).

---

## Shared Patterns

### Single-helper REMEDIATED discipline (D-09 / Pitfall 6)
**Source:** `vulnerabilities/service.py::mark_vulnerability_remediated` (line 370).
**Apply to:** every finding-close path in this phase. NEVER assign `Vulnerability.status = "REMEDIATED"`
directly — it silently drops the `RemediationEvent`/MTTR row.

### Provider abstraction
**Source:** `ticketing/dispatch.py` `TicketingClient` protocol + `build_ticketing_client` (line 121).
**Apply to:** all provider status fetches — prefer over per-provider `if` ladders.

### Scheduler-originated audit
**Source:** `sla_tier_service.py::_audit_escalation_fire` (line 309) — direct `AuditLog`, real
`tenant_id`, `user_email="system:scheduler"`. **Apply to:** every scheduler status write.

### Error isolation + sanitized persistence (SYNC-04 resilience)
**Source:** per-connector `try/except` in `daily_sync.py:44-99`; `_sanitize_error` in `sync.py:44`.
**Apply to:** the write-back pass so one provider/tenant failure never aborts the others, and no
secret is persisted in `last_error`.

### Decimal-as-string wire convention
**Source:** `vulnerabilities/schemas.py::ScoreDecimal` (line 17) — `PlainSerializer(float, when_used="json")`.
**Apply to:** ANY new numeric response field. Note the nuance: this repo's `ScoreDecimal` emits
Decimals as JSON **numbers** (float) on the wire because frontend does `.toFixed`; a raw Decimal
otherwise serializes as a JSON **string** and crashed the drill panel. If Phase 37 adds numeric
response fields (e.g. clean-scan count, sync latency), use plain `int`/`float` or the `ScoreDecimal`
annotation — do not leak an un-annotated `Decimal`.

---

## No Analog Found

None. Every SYNC-01..04 capability maps to an existing file to extend. The only genuinely new
artifacts are (a) the per-finding clean-scan counter column, (b) its migration, (c) the D-03 split
of ticket-status-drives-workflow vs rescan-drives-closure — all built by mirroring the analogs above.

## Metadata

**Analog search scope:** `backend/app/ticketing/`, `backend/app/vulnerabilities/`,
`backend/app/connectors/`, `backend/app/audit.py`, `backend/alembic/versions/`, `backend/tests/`.
**Files scanned:** ~18 read in full or targeted.
**Pattern extraction date:** 2026-08-14.
