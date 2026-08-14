# Phase 37: Two-Way Ticket Sync & Remediation Verification - Research

**Researched:** 2026-08-14
**Domain:** Backend — polling-based inbound ticket status sync + scanner-rescan-verified finding auto-close/reopen (GetVul, FastAPI + Postgres, in-process asyncio scheduler)
**Confidence:** HIGH (all findings verified against the live codebase)

## Summary

Phase 37 is an **extension of existing machinery**, not greenfield. Every seam it needs
already exists: the scheduler tick (`connectors/scheduler.py`), the ticket-status poll pass
(`ticketing/daily_sync.py`, which already reads status from all three providers), the three
provider clients (each already exposes a status-read call), the single MTTR-capturing
REMEDIATED helper (`vulnerabilities/service.py::mark_vulnerability_remediated`), the
scanner upsert that stamps `last_seen_at` (`connectors/sync.py::_upsert_vulnerability`), and
the connector resilience columns (`ConnectorConfig.last_sync_status` / `last_sync_at` /
`consecutive_failure_count` / `last_error`). [VERIFIED: codebase grep]

There are **two load-bearing gaps** the planner must design around, and one **existing
behavior that violates a locked decision**:

1. **No absent-detection exists.** `_upsert_vulnerability` refreshes `last_seen_at` for
   findings that ARE present in a scan, but nothing sweeps for findings whose `last_seen_at`
   was *not* refreshed. SYNC-02's "absent from 2 consecutive clean scans" bookkeeping must be
   built from scratch and hooked strictly inside the SUCCESS branch of `run_sync`. [VERIFIED]
2. **The existing inbound sync closes findings on ticket-done — which D-03 forbids.**
   `daily_sync.py` today calls `mark_vulnerability_remediated` the moment a Jira/Asana/GitHub
   ticket goes done/completed/closed. D-03 says a done ticket must **never** close a finding
   the scanner still detects. Phase 37 must *remove* the REMEDIATED write from the ticket-done
   path and route it to the rescan-verified path instead. This is the central design change,
   not a footnote. [VERIFIED: daily_sync.py lines 243-249, 331-337, 425-431]
3. **Reopen (D-04) is a natural fit for the dedup identity key.** The
   `uq_vuln_dedup(tenant_id, cve_id, asset_id, source)` constraint means a re-detected finding
   already lands on the SAME row in `_upsert_vulnerability`'s `existing` branch — the reopen
   hook is "if that existing row is REMEDIATED, resurrect it." No dedup logic to invent. [VERIFIED]

**Primary recommendation:** Keep the single-helper discipline (route the REMEDIATED write
through `mark_vulnerability_remediated`, extended with an optional `verified_by="rescan"`
keyword — do NOT add a sibling status-writer). Build a per-finding clean-scan streak counter
as a new integer column, incremented only inside `run_sync`'s SUCCESS branch. Audit every
system-driven status write via **direct `AuditLog` construction with `user_email="system:*"`**
(the `audit()` helper cannot express a system actor — see Pitfall 4).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Inbound ticket status → finding workflow state (SYNC-01) | API / Backend (`ticketing/daily_sync.py`) | Provider clients (read status) | Status mapping + workflow write is business logic; no client tier involved |
| Rescan-verified auto-close (SYNC-02) | API / Backend (`connectors/sync.py` SUCCESS branch) | Database (streak column) | "Absent" is derived from scanner sync outcome; belongs where `last_seen_at` is written |
| Reopen on recurrence (SYNC-03) | API / Backend (`connectors/sync.py::_upsert_vulnerability`) | Provider clients (reopen/comment ticket) | Re-detection happens during upsert; identity key already routes to the same row |
| Sync resilience / last-sync surfacing (SYNC-04) | API / Backend (`ticketing/daily_sync.py` + `ConnectorConfig`) | Frontend (connector list already renders `last_sync_status`) | Mirrors scanner-connector resilience columns; UI already exists |
| Audit of every status write | API / Backend (`app/audit.py` model, direct `AuditLog`) | — | Tenant-scoped, system-actor; no HTTP request context |

## Standard Stack

This phase adds **no new libraries**. It reuses the established backend stack. [VERIFIED: backend/pyproject.toml]

### Core (already present — reuse)
| Component | Where | Purpose | Why Standard |
|-----------|-------|---------|--------------|
| `httpx.AsyncClient` | all 3 provider clients | Async provider API calls | Already wraps Jira/Asana/GitHub; 429+Retry-After retry already implemented |
| SQLAlchemy async ORM | `sync.py`, `daily_sync.py`, models | DB reads/writes | Codebase convention (`AsyncSession`) |
| `structlog` | everywhere | Structured logging | Codebase convention |
| `mark_vulnerability_remediated` | `vulnerabilities/service.py:370` | Single REMEDIATED transition + `RemediationEvent`/MTTR | Phase 36 D-09/Pitfall-6 discipline — every REMEDIATED write MUST route here |
| `ConnectorConfig` resilience columns | `ticketing/models.py:50-55` | `last_sync_at`/`last_sync_status`/`consecutive_failure_count`/`last_error` | SYNC-04 precedent, already surfaced in UI |
| `AuditLog` (direct construction) | `app/audit.py` model | System-actor tenant-scoped audit | `exposure.py` / `encryption.py` / `ai/batch.py` precedent |

### Supporting (test)
| Component | Version | Purpose | When to Use |
|-----------|---------|---------|-------------|
| pytest + pytest-asyncio | 8.3 / 0.24, `asyncio_mode="auto"` | Async unit tests | All new logic |
| `httpx.MockTransport` | (httpx) | Mock provider APIs | Provider-client status-read tests (pattern in `test_ticketing_clients.py:23`) |
| `db_session` fixture | `tests/conftest.py:157` | Real-Postgres behavioral tests | Streak/reopen/auto-close DB behavior |

**Installation:** none — no new packages.

**Version verification:** No new dependencies to verify; all components are in-tree. [VERIFIED: no `npm/pip install` needed]

## Architecture Patterns

### System Architecture Diagram

```
                         in-process asyncio scheduler loop
                         (connectors/scheduler.py::_scheduler_loop)
                                        │
        ┌───────────────────────────────┼────────────────────────────────┐
        │                               │                                 │
   [every tick]                   [every 24h gate]                  [per-connector due]
        │                               │                                 │
        ▼                               ▼                                 ▼
  SLA tier pass            run_daily_ticket_sync(db)            run_sync(db, connector)
  (Phase 36)               (ticketing/daily_sync.py)            (connectors/sync.py)
                                        │                                 │
                    ┌───────────────────┼───────────────┐                │ (scanner connector)
                    ▼                   ▼               ▼                 ▼
              Jira get_issue     Asana get_task   GitHub get_issue   fetch_vulnerabilities()
                    │                   │               │                 │
                    └─────────┬─────────┴───────────────┘                 ▼
                              ▼                              _upsert_vulnerability (present → last_seen_at=now)
              map external status → internal              ┌──────────────┴───────────────┐
              (SYNC-01, D-03: ticket drives               │ (NEW) SUCCESS-branch          │
               WORKFLOW state only, NEVER closes)         │ absent-sweep (SYNC-02):       │
                              │                            │  last_seen_at < sync_start    │
                    ┌─────────┴─────────┐                  │  → streak++; else streak=0    │
                    ▼                   ▼                  │  streak==2 → REMEDIATED        │
           finding.status →       post comment /           └──────────────┬───────────────┘
           IN_PROGRESS            "awaiting rescan"                        │
                                                          (NEW) existing REMEDIATED row re-detected
                                                            → reopen SAME row (SYNC-03, D-04)
                                                            → relink/reopen ticket
                                                                          │
                    ┌─────────────────────────────────────────────────────┘
                    ▼
       mark_vulnerability_remediated(db, vuln, verified_by="rescan")
       → status=REMEDIATED + RemediationEvent (MTTR) + AuditLog(system:*)
```

### Component Responsibilities
| File | Responsibility this phase | Change type |
|------|---------------------------|-------------|
| `ticketing/daily_sync.py` | SYNC-01 status mapping; **remove** ticket-done→REMEDIATED close; set per-connector `last_sync_*` (SYNC-04) | Modify (significant) |
| `connectors/sync.py` (`run_sync` SUCCESS branch + `_upsert_vulnerability`) | SYNC-02 absent-sweep + streak; SYNC-03 reopen-on-recurrence | Modify |
| `vulnerabilities/service.py::mark_vulnerability_remediated` | Add optional `verified_by` kwarg; add a reopen helper | Modify (additive) |
| `vulnerabilities/models.py::Vulnerability` | New `clean_scan_streak` integer column | Migration |
| `ticketing/{jira,asana,github}_client.py` | Add GitHub `reopen_issue` (PATCH state=open); Jira/Asana reopen already expressible | Modify (minor) |
| Alembic migration | `clean_scan_streak` column | New |

### Pattern 1: SYNC-01 — external status → internal workflow state (D-03-safe)
**What:** Map the provider's status to an internal *workflow* transition that never closes a finding.
**When to use:** Every inbound poll in `daily_sync.py`.
**Recommended mapping** [ASSUMED — needs confirmation, Claude's-discretion item]:

| Provider signal | Source field | Internal effect (D-03) |
|-----------------|-------------|------------------------|
| Jira `statusCategory.key == "indeterminate"` (In Progress) | `fields.status.statusCategory.key` | finding → `IN_PROGRESS` |
| Jira `statusCategory.key == "done"` / name in {done,closed,resolved} | same | **workflow only** — post "ticket done, awaiting rescan verification" comment/state; do NOT set REMEDIATED |
| Jira `statusCategory.key == "new"` | same | leave `OPEN` (or IN_PROGRESS→OPEN if reverted) |
| Asana `completed == true` | `/tasks/{gid}` `completed` | **workflow only** — awaiting-rescan; do NOT set REMEDIATED |
| Asana `completed == false` | same | `OPEN`/`IN_PROGRESS` per prior state |
| GitHub `state == "closed"` | `/issues/{n}` `state` | **workflow only** — awaiting-rescan; do NOT set REMEDIATED |
| GitHub `state == "open"` | same | `OPEN`/`IN_PROGRESS` |

**Example (current code that MUST change):**
```python
# Source: backend/app/ticketing/daily_sync.py:321-337 (Jira branch — CURRENT, VIOLATES D-03)
if status_category == "done" or jira_status.lower() in ("done", "closed", "resolved", "completed"):
    ticket.external_status = jira_status.lower()
    ticket.resolved_at = datetime.now(UTC)
    resolved += 1
    vuln = (...).scalar_one_or_none()
    if vuln and vuln.status not in ("REMEDIATED", "SUPPRESSED"):
        from app.vulnerabilities.service import mark_vulnerability_remediated
        await mark_vulnerability_remediated(db, vuln)   # ← D-03 violation: closes on ticket-done
```
Under D-03 this becomes: record `ticket.external_status`, drive finding to a workflow state
(`IN_PROGRESS` / awaiting-rescan), post the comment — but the REMEDIATED write is deleted here
and moved to the SYNC-02 rescan-verified path. The identical pattern repeats in the Asana
(`:236-249`) and GitHub (`:418-431`) branches.

### Pattern 2: SYNC-02 — absent-sweep streak inside the SUCCESS branch
**What:** After a *successful* scanner sync for a `(tenant, source)`, findings whose
`last_seen_at` predates the sync start are absent this cycle.
**When to use:** Only inside `run_sync`'s SUCCESS branch (`connectors/sync.py` ~line 196), never
on FAILED. A partial/failed sync must not decrement anything (D-02).
**Example (recommended new logic):**
```python
# Source: derived from backend/app/connectors/sync.py:91-201 (run_sync)
# `now` is captured at run_sync entry (line 92) BEFORE the upsert loop.
# Present vulns get last_seen_at = a fresh now() inside _upsert_vulnerability (line 363/376).
# So "absent this cycle" == last_seen_at < run_sync.now for OPEN/IN_PROGRESS findings of this source.
sync_start = now  # line 92
# ... only after log.status == "SUCCESS" (line 182) ...
absent = await db.execute(
    select(Vulnerability).where(
        Vulnerability.tenant_id == connector_config.tenant_id,
        Vulnerability.source == connector_config.connector_type,
        Vulnerability.status.in_(("OPEN", "IN_PROGRESS")),
        Vulnerability.last_seen_at < sync_start,
    )
)
for vuln in absent.scalars():
    vuln.clean_scan_streak = (vuln.clean_scan_streak or 0) + 1
    if vuln.clean_scan_streak >= 2:               # D-02 fixed threshold
        await mark_vulnerability_remediated(db, vuln, verified_by="rescan")
        # + direct AuditLog(system:rescan-verify)
# findings refreshed this cycle reset their streak (they were re-detected):
await db.execute(
    update(Vulnerability)
    .where(Vulnerability.tenant_id == connector_config.tenant_id,
           Vulnerability.source == connector_config.connector_type,
           Vulnerability.last_seen_at >= sync_start,
           Vulnerability.clean_scan_streak > 0)
    .values(clean_scan_streak=0)
)
```
**Streak storage recommendation:** new column `clean_scan_streak: Mapped[int] = mapped_column(
Integer, default=0, server_default="0")` on `Vulnerability` — mirrors
`ConnectorConfig.consecutive_failure_count` exactly (`models.py:55`). Per-finding, per-source
alignment is automatic because `source` is part of the dedup key. [VERIFIED: uq_vuln_dedup]

### Pattern 3: SYNC-03 — reopen the same row (D-04)
**What:** A re-detected finding lands on its original row via the dedup key; if that row is a
rescan-verified REMEDIATED, resurrect it.
**Example:**
```python
# Source: backend/app/connectors/sync.py:375-393 (_upsert_vulnerability existing branch)
if existing:
    existing.last_seen_at = now
    # ... existing field refresh ...
    if existing.status == "REMEDIATED":          # NEW (D-04): recurrence after auto-close
        existing.status = "OPEN"
        existing.remediated_at = None
        existing.clean_scan_streak = 0
        # + AuditLog(system:rescan-reopen); relink/reopen the linked ticket(s)
    return False
```
MTTR lineage is preserved automatically — the historical `RemediationEvent` row(s) are never
deleted, and reopen creates no duplicate finding (same row) and no duplicate ticket (existing
`Ticket.vulnerability_id` still points here). [VERIFIED: RemediationEvent has no unique
constraint on vuln — `models.py:272`, so a later re-close writes a second event correctly.]

### Pattern 4: SYNC-04 — mirror the connector resilience columns for ticketing
**What:** On each provider poll in `daily_sync.py`, set the ticketing `ConnectorConfig`'s
`last_sync_at` / `last_sync_status` / `consecutive_failure_count` / `last_error` exactly as
`run_sync` does for scanners (`sync.py:196-209`).
**Why:** Today ticketing connectors short-circuit to a stub SUCCESS (`sync.py:125-131`,
`"no data sync needed"`) and `run_daily_ticket_sync` swallows per-connector exceptions
(`daily_sync.py:93-99`) without touching these columns — so the UI shows a meaningless status.
The connector list already renders `last_sync_status`, so this is UI-free.
**Retry/backoff:** clients already do a single 429 + `Retry-After` retry
(`jira_client.py:128-132`, `asana_client.py:135-139`, `github_client.py:96-103`). For
transient 5xx/network failure, add a small bounded retry (e.g. 3 attempts, exponential
backoff) around the poll; because reads are idempotent and the streak only advances on SUCCESS,
a skipped cycle is safe (no data loss — retried next tick).

### Anti-Patterns to Avoid
- **Closing a finding because its ticket is done** (current code) — violates D-03. Only 2 clean
  rescans close.
- **Adding a sibling `mark_vulnerability_rescan_verified` status-writer** — forks the
  single-helper MTTR discipline (Phase 36 D-09/Pitfall 6). Extend the one helper instead.
- **Counting absent findings on a FAILED/partial sync** — false-closes everything. Sweep only
  in the SUCCESS branch.
- **Using `audit()` for scheduler-driven writes** — it requires a `CurrentUser` and stamps
  `tenant_id=UUID(int=0)` when `user=None` (`audit.py:174`), losing tenant scope. Use direct
  `AuditLog(user_email="system:*")`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| REMEDIATED transition + MTTR | A new status write / new event insert | `mark_vulnerability_remediated` (`service.py:370`) | Single-helper discipline; misses drop MTTR (Pitfall 6) |
| Finding dedup / "is this the same finding" | Custom cve+asset matching | `uq_vuln_dedup` + the `_upsert_vulnerability` existing-branch | Identity key already resolves recurrence to the same row |
| Provider HTTP + 429 handling | New API client | `jira/asana/github_client.py` | Clients already exist, tested via `MockTransport` |
| Per-connector sync outcome surfacing | New table/UI | `ConnectorConfig.last_sync_*` columns | Already modeled + rendered in connector list |
| System-actor audit row | Faked `CurrentUser` | Direct `AuditLog(user_email="system:*")` | Established precedent; `audit()` cannot express it |

**Key insight:** Almost every piece exists; the phase is wiring + one behavior correction +
one new streak column. The risk is *duplicating* an existing seam (a second status-writer, a
second dedup path), not missing a library.

## Runtime State Inventory

> Rename/refactor category. Phase 37 is behavior-additive, not a rename, but two data-shape
> items matter:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `Vulnerability` rows need a new `clean_scan_streak` column; existing rows default 0 | Alembic migration (add column, `server_default="0"`) — safe backfill |
| Stored data | Findings already auto-closed by the *current* ticket-done path are `REMEDIATED` but were NOT rescan-verified | None required for SYNC scope; flag as open question (see Open Questions Q3) |
| Live service config | Jira/Asana/GitHub ticket status lives in the provider, read each poll — not stored in git | None — polled each cycle (D-01) |
| OS-registered state | None — in-process scheduler only, no OS timers | None — verified (`scheduler.py` is an asyncio loop) |
| Secrets/env vars | Provider creds via `get_decrypted_credentials(connector)` — unchanged | None — reused as-is |
| Build artifacts | None | None — verified (pure Python, no compiled artifacts) |

## Common Pitfalls

### Pitfall 1: Ticket-done still closes the finding
**What goes wrong:** Leaving the existing `mark_vulnerability_remediated` calls in
`daily_sync.py` means a human closing a ticket closes the finding — the exact anti-pattern D-03
forbids.
**Why it happens:** The current code (shipped pre-Phase-37) does this deliberately; it's easy to
"extend" it without noticing it must be *removed*.
**How to avoid:** Delete the REMEDIATED write from all three ticket-done branches; move it to the
SYNC-02 rescan path only.
**Warning signs:** A finding reaches REMEDIATED with `clean_scan_streak < 2`.

### Pitfall 2: FAILED sync silently false-closes everything
**What goes wrong:** If the absent-sweep runs regardless of sync outcome, an auth failure /
network blip makes every finding look absent and the streak advances toward auto-close.
**Why it happens:** `run_sync` sets `last_sync_status="FAILED"` and skips the upsert loop
(`sync.py:143-152, 202-209`) — no `last_seen_at` gets refreshed on failure.
**How to avoid:** Gate the sweep on `log.status == "SUCCESS"`; never touch streaks on
FAILED/PARTIAL (D-02).
**Warning signs:** `consecutive_failure_count > 0` on a connector whose findings' streaks are
climbing.

### Pitfall 3: MTTR clock semantics on rescan-verified close
**What goes wrong:** `mark_vulnerability_remediated` computes `duration_seconds =
now - first_detected_at` (`service.py:391`). For a rescan-verified close, `now` is the 2nd
clean-scan moment, not the fix moment — MTTR includes up to ~2 scan intervals of latency.
**Why it happens:** The helper stamps `remediated_at = now` unconditionally.
**How to avoid:** Accept it as the intended semantics (D-03: "verified by rescan is the truth"),
OR extend the helper's `verified_by` path to accept an explicit `remediated_at`. Do NOT branch
into a separate helper. Flag for planner (Open Questions Q1).
**Warning signs:** MTTR-by-tier drifts upward after Phase 37 ships vs. the manual-close baseline.

### Pitfall 4: Losing tenant scope in system-driven audit
**What goes wrong:** Calling `audit(db, None, ...)` stamps `tenant_id=UUID(int=0)`
(`audit.py:174`), producing cross-tenant-orphaned audit rows.
**Why it happens:** The scheduler has no `CurrentUser`.
**How to avoid:** Construct `AuditLog` directly with `tenant_id=<from the vuln/connector row>`,
`user_id=None`, `user_email="system:rescan-verify"` (or `system:ticket-sync`) — exactly the
`exposure.py:230` / `encryption.py` / `ai/batch.py` precedent.
**Warning signs:** Audit rows with a zero UUID tenant.

### Pitfall 5: Reopen leaves a stale duplicate ticket or forgets to relink
**What goes wrong:** Creating a new ticket on recurrence instead of reopening the existing one.
**How to avoid:** Find `Ticket` rows where `vulnerability_id == vuln.id`; reopen via the client
(Asana `update_task(completed=False)`, Jira `transition(open-status)`, GitHub needs a new
`reopen_issue` PATCH `state="open"`) + comment. No new `Ticket` row (D-04).
**Warning signs:** Two tickets for one finding; a finding OPEN again with no linked ticket.

## Code Examples

### System-actor tenant-scoped audit (the correct precedent)
```python
# Source: backend/app/assets/exposure.py:230-260 (audit_auto_inference_changes)
db.add(
    AuditLog(
        tenant_id=tenant_id,          # from the vuln/connector row, NOT UUID(int=0)
        user_id=None,
        user_email="system:exposure-inference",   # Phase 37 → "system:rescan-verify" etc.
        action="asset.exposure_recompute",
        resource_type="asset",
        resource_id=str(asset_id),
        details={"changes": changes},
        created_at=datetime.now(UTC),
    )
)
# No db.commit() here — caller commits at its own transaction boundary.
```

### Provider status-read calls (all three already exist)
```python
# Jira  — backend/app/ticketing/jira_client.py:156  → dict; read fields.status.statusCategory.key
await client.get_issue(issue_key)
# Asana — backend/app/ticketing/asana_client.py:164 → dict; read data["completed"]
await client.get_task(task_gid)
# GitHub— backend/app/ticketing/github_client.py:127 → dict; read data["state"]
await client.get_issue(number)
```

### Test pattern (provider clients via MockTransport)
```python
# Source: backend/tests/test_ticketing_clients.py:23-36
def _mock_client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://mock")

def handler(request):
    return httpx.Response(200, json={"fields": {"status": {"statusCategory": {"key": "done"}}}})
c = JiraClient(email="e", api_token="t", base_url="https://mock")
c._client = _mock_client(handler)
```

## State of the Art

| Old Approach | Current Approach (this phase) | When Changed | Impact |
|--------------|-------------------------------|--------------|--------|
| Ticket-done → close finding | Ticket-done → workflow state only; rescan closes | Phase 37 (D-03) | Removes premature closure |
| No absent-detection | 2-consecutive-clean-scan streak | Phase 37 (SYNC-02) | New column + SUCCESS-branch sweep |
| Ticketing connectors report stub "no sync needed" | Real per-poll `last_sync_*` outcome | Phase 37 (SYNC-04) | Meaningful connector status in UI |

**Deprecated/outdated:** the three `mark_vulnerability_remediated` calls in `daily_sync.py`
(ticket-done branches) — retire them from that path (they move to the rescan path).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | External→internal status mapping table (Jira indeterminate→IN_PROGRESS, done→awaiting-rescan, etc.) | Pattern 1 | Wrong workflow states; but D-03 (no close) holds regardless — low blast radius |
| A2 | "awaiting rescan" is represented via `IN_PROGRESS` + a comment, NOT a new status enum value | Pattern 1 | If a distinct status is wanted, needs enum + migration; `VulnStatus` has no such value today |
| A3 | `clean_scan_streak` as a new `Vulnerability` column (vs. a side table) is the right shape | Pattern 2 | A side table would be more work; column matches `consecutive_failure_count` precedent |
| A4 | Rescan-verified close should reuse `mark_vulnerability_remediated` (extended), not a sibling | Summary / Pattern 2 | A sibling would fork MTTR discipline — high cost if chosen wrongly |
| A5 | Bounded retry (3 attempts, exp backoff) is sufficient for SYNC-04 transient failures | Pattern 4 | Under/over-tuned backoff; low risk given 24h cadence + idempotent reads |

## Open Questions

1. **MTTR clock on rescan-verified close.** Should `remediated_at`/`duration_seconds` reflect the
   2nd-clean-scan moment (default helper behavior) or the fix/first-clean-scan moment?
   - Known: helper stamps `now`; D-03 says rescan is truth.
   - Unclear: whether SLA-04 reporting wants "time-to-fix" vs "time-to-verified".
   - Recommendation: default to 2nd-clean-scan `now` (matches D-03); expose `verified_by`
     on the `RemediationEvent`/audit so reporting can distinguish later.
2. **"Awaiting rescan" representation.** Is a done ticket reflected as `IN_PROGRESS` + comment, or
   does the phase want a new visible state? (A2). Recommendation: reuse `IN_PROGRESS` + comment;
   avoid an enum/migration churn unless the UI needs a distinct pill.
3. **Backfill of already-(prematurely-)closed findings.** Findings the *current* ticket-done path
   already set to REMEDIATED were never rescan-verified. Leave as-is (out of SYNC scope) or
   re-open on next detection? Recommendation: do nothing proactively; SYNC-03 will naturally
   reopen any that recur. Flag to planner as a data note, not a task.
4. **Reopen ticket policy per provider.** GitHub needs a new `reopen_issue` (PATCH `state="open"`)
   — confirm we reopen the closed issue vs. only commenting. D-04 allows "reopen OR re-comment."

## Environment Availability

Step 2.6: SKIPPED for new external tooling — no new runtimes/services. The three provider APIs
(Jira Cloud, Asana, GitHub Issues) are already integrated via existing clients and exercised in
tests with `httpx.MockTransport`; live connectivity depends on per-tenant configured credentials
at runtime (`get_decrypted_credentials`), not on the build environment. [VERIFIED: clients +
`test_ticketing_clients.py` exist]

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Postgres | streak column, behavioral tests | ✓ (dev stack) | — | tests skip cleanly if unreachable (`conftest.py:143`) |
| Provider APIs (Jira/Asana/GitHub) | SYNC-01/03/04 | ✓ (via existing clients) | — | mocked in unit tests |

## Validation Architecture

> `workflow.nyquist_validation` is absent in `.planning/config.json` → treated as ENABLED.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3 + pytest-asyncio 0.24 (`asyncio_mode="auto"`) |
| Config file | `backend/pyproject.toml` (`[tool.pytest.ini_options]`, `testpaths=["tests"]`) |
| Quick run command | `cd backend && ENCRYPTION_KEY=... JWT_SECRET_KEY=... uv run pytest tests/test_<file>.py -x` |
| Full suite command | run **per-file** (MEMORY: whole-`tests/` dir gives false failures); iterate the phase's files |

> Env note (from user MEMORY `getvul-backend-pytest-env`): set `ENCRYPTION_KEY` + `JWT_SECRET_KEY`
> and run per-file, not the whole directory, to avoid false failures.

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SYNC-01 | Jira/Asana/GitHub status → workflow state (never REMEDIATED) | unit | `pytest tests/test_ticket_status_sync.py -x` | ❌ Wave 0 |
| SYNC-02 | 2 consecutive clean SUCCESS syncs → REMEDIATED; FAILED never counts | unit+db | `pytest tests/test_rescan_autoclose.py -x` | ❌ Wave 0 |
| SYNC-03 | recurrence reopens SAME row, no duplicate finding/ticket, MTTR preserved | db | `pytest tests/test_finding_reopen.py -x` | ❌ Wave 0 |
| SYNC-04 | failed poll retries, `last_sync_*` set, streak untouched on failure | unit | `pytest tests/test_ticket_sync_resilience.py -x` | ❌ Wave 0 |
| (regression) | provider status-read parsing | unit | `pytest tests/test_ticketing_clients.py -x` | ✅ exists |

### Sampling Rate
- **Per task commit:** the single new test file for that task (`-x`).
- **Per wave merge:** all Phase 37 test files, per-file.
- **Phase gate:** all Phase 37 files green + a targeted rerun of `test_mttr.py` /
  `test_sla_tier_service.py` (guard the shared `mark_vulnerability_remediated` path).

### Wave 0 Gaps
- [ ] `tests/test_ticket_status_sync.py` — SYNC-01 mapping + D-03 (no close on ticket-done)
- [ ] `tests/test_rescan_autoclose.py` — SYNC-02 streak, SUCCESS-only gating, FAILED-guard
- [ ] `tests/test_finding_reopen.py` — SYNC-03 same-row reopen + MTTR/history preserved
- [ ] `tests/test_ticket_sync_resilience.py` — SYNC-04 retry/backoff + `last_sync_*`
- [ ] Alembic migration test parity (see `tests/test_ticket_migrations.py` pattern)

## Security Domain

> `security_enforcement` absent in config → treated as ENABLED.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no (new surface) | Provider auth via existing encrypted creds (`get_decrypted_credentials`) |
| V3 Session Management | no | Scheduler-driven, no session |
| V4 Access Control | yes | All queries tenant-scoped (`tenant_id` on every read/write); system-actor audit carries real `tenant_id` |
| V5 Input Validation | yes | Validate/whitelist provider status strings before mapping; treat provider payloads as untrusted (`.get(...)` with defaults, already the client style) |
| V6 Cryptography | no (reuse) | Creds already encrypted at rest; never logged (clients note "never logged") |
| V7 Error Handling / Logging | yes | `_sanitize_error` (`sync.py:45`) redaction precedent for `last_error`; every status write audited |

### Known Threat Patterns for polling ticket sync
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malicious/garbage provider status payload | Tampering | Whitelist-map known statuses; unknown → no-op + log, never auto-close |
| Cross-tenant audit/status leak | Info Disclosure | Every query filters `tenant_id`; system-actor audit uses the row's real tenant (Pitfall 4) |
| False auto-close via induced sync failure | Denial (of accurate state) | Streak advances only on SUCCESS; FAILED never counts (D-02, Pitfall 2) |
| No inbound webhook ingress | — | D-01: polling only → no public ingress, no signature-verification attack surface |
| Secret leakage in error surfacing | Info Disclosure | Reuse `_sanitize_error` before persisting to `last_error` |

## Sources

### Primary (HIGH confidence)
- `backend/app/ticketing/daily_sync.py` — existing inbound poll for all 3 providers; the D-03-violating REMEDIATED calls (lines 243-249, 331-337, 425-431)
- `backend/app/ticketing/{jira_client,asana_client,github_client}.py` — status-read calls `get_issue`/`get_task`; 429 retry; missing GitHub `reopen_issue`
- `backend/app/ticketing/models.py` — `Ticket.vulnerability_id` (singular FK), `external_status`, `ConnectorConfig.last_sync_*`/`consecutive_failure_count`, `SyncLog`
- `backend/app/connectors/sync.py` — `run_sync` (SUCCESS/FAILED status writes, lines 91-215), `_upsert_vulnerability` (`last_seen_at` refresh, no absent-detection)
- `backend/app/connectors/scheduler.py` — tick cadence, 24h ticket-sync gate (lines 342-353), SLA pass precedent
- `backend/app/vulnerabilities/service.py` — `mark_vulnerability_remediated` (single helper, MTTR), `get_mttr_by_tier`, `update_vulnerability_status`
- `backend/app/vulnerabilities/models.py` — `VulnStatus` enum, `uq_vuln_dedup(tenant_id,cve_id,asset_id,source)`, `RemediationEvent` (no unique constraint)
- `backend/app/assets/exposure.py:230` + `backend/app/audit.py:143` — system-actor audit precedent vs. `audit()` `CurrentUser` requirement
- `backend/app/connectors/directory_sync.py` / `humaans_sync.py` — SUCCESS/FAILED `last_sync_*` resilience precedent
- `backend/tests/test_ticketing_clients.py`, `tests/conftest.py`, `backend/pyproject.toml` — test framework + fixtures

### Secondary (MEDIUM)
- User MEMORY: `getvul-backend-pytest-env` (per-file run + env vars), `getvul-execute-phase-tracking-hazards` (`**Plans**:` format, sequential runs)

### Tertiary (LOW)
- None — this phase required no external/web sources; all findings are codebase-verified.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all components in-tree, verified by grep
- Architecture / integration points: HIGH — exact files and line numbers confirmed
- Pitfalls: HIGH — the D-03 violation and absent-detection gap are observed in current code
- Status-mapping table: MEDIUM (ASSUMED A1/A2) — Claude's-discretion item, needs confirmation

**Research date:** 2026-08-14
**Valid until:** 2026-09-13 (stable — internal codebase; revisit if `daily_sync.py`, `sync.py`, or `service.py::mark_vulnerability_remediated` change before planning)
