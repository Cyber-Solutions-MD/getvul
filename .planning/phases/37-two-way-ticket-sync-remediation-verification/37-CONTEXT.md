# Phase 37: Two-Way Ticket Sync & Remediation Verification - Context

**Gathered:** 2026-08-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Ticket state stops being one-way (GetVul → Jira/Asana/GitHub only). This phase makes
linked ticket status flow **back** onto the GetVul finding, and makes a fix get **verified
by the scanner re-scanning clean** — not by a human remembering to close the loop.
Delivers SYNC-01..04.

**In scope:**
- Inbound status sync: external ticket status (Jira / Asana / GitHub) → linked finding's workflow state (SYNC-01).
- Rescan-verified auto-close: a finding absent from 2 consecutive post-fix scanner syncs auto-closes, fully audited (SYNC-02).
- Reopen-on-recurrence: a later scan re-detecting an auto-closed finding reopens the *same* finding + relinks its ticket, never duplicates (SYNC-03).
- Sync resilience: failed syncs retry, no data loss, last-successful-sync surfaced per connector (SYNC-04).

**Explicitly NOT this phase:** inbound webhooks / real-time push (deferred — see Deferred Ideas); bulk remediation campaigns (Phase 38); exception/risk-acceptance workflow (Phase 39); proactive alerting/digests (Phase 40); any new scanner or patch-deployer (lane discipline). The v4.0 risk score is consumed, never re-derived.
</domain>

<decisions>
## Implementation Decisions

### D-01 — Sync mechanism: polling, extend the existing scheduler
Extend the in-process asyncio scheduler's ticket-sync pass (today `ticketing/daily_sync.py`)
to poll Jira/Asana/GitHub for status and write back onto findings. **No inbound webhook
endpoint** — honors the single-VM Docker Compose / in-process-scheduler infra constraint
(no public ingress, no signature-verification surface). "Without manual action" (SYNC-01)
is satisfied by the scheduler cadence; near-real-time = poll interval.
— **Reversibility:** reversible — a webhook seam can be added later without unwinding polling.

### D-02 — Rescan-verified auto-close threshold: 2 consecutive clean syncs (fixed default)
A finding absent from **2 consecutive** post-fix scanner syncs auto-closes as
rescan-verified. Two (not one) guards against a single partial/failed scan false-closing.
Fixed default this phase (NOT tenant-configurable — kept simple; can be promoted to a
tenant setting in a later phase if asked). "Absent" is derived from the scanner sync not
refreshing the finding's `last_seen_at` across two sync cycles for a source that DID run
successfully (a failed/partial connector sync must NOT count as a clean scan — ties into D-04).

### D-03 — Conflict precedence: rescan is truth for closure; ticket drives workflow state
Scanner evidence governs OPEN ↔ REMEDIATED — **a finding only truly closes when
rescan-verified (D-02)**. An external ticket status change drives *workflow* state
(e.g. → IN_PROGRESS) and posts context/comments, but a closed ticket **never force-closes a
finding the scanner still detects**. This keeps "verified by rescan, not by a human closing
a ticket" as the core guarantee and avoids premature closure.
— **Reversibility:** costly — changing the precedence later touches every status-write path.

### D-04 — Reopen on recurrence: resurrect the same finding + relink
When a later scan re-detects an auto-closed finding, **reopen the original finding row**
(preserving its history and MTTR lineage) and reopen or re-comment the linked external
ticket. No duplicate finding, no duplicate ticket. Requires the auto-close to be a
*soft* close (status transition + audit, row retained and re-findable by its identity
key: tenant + source_vuln_id / cve+asset).

### D-03 addendum — the whole ticketing surface obeys D-03, including manual close (gap closure 2026-08-17)
Verification found the D-03 fix in Plan 37-03 was scoped to `daily_sync.py` only; the
router-invoked twins in `ticketing/service.py` (`sync_ticket_status`, `close_ticket`) still
force-close findings via `mark_vulnerability_remediated` on ticket-done. **Decision (user,
gap closure): D-03 applies to BOTH.** Neither an inbound status sync NOR an analyst's explicit
"Close Ticket" click may close a finding — the scanner re-scanning clean is the ONLY closure
path. A done/closed ticket (however triggered) drives the linked finding to IN_PROGRESS +
awaiting-rescan comment + `system:ticket-sync` audit, never REMEDIATED. The two `test_mttr.py`
tests that lock in the old REMEDIATED-on-ticket-done behavior (`sync_ticket_status` and
`close_ticket` variants) are rewritten to assert the IN_PROGRESS-only outcome.
— **Reversibility:** costly — same precedence surface as D-03.

### Claude's Discretion (planner/researcher decide)
- External→internal status mapping table (which Jira/Asana/GitHub states map to IN_PROGRESS
  vs "ticket done, awaiting rescan"), following D-03 (ticket done ≠ finding closed).
- Retry/backoff mechanics and the "clean scan" bookkeeping structure for SYNC-04.
- Whether auto-close routes through the existing `mark_vulnerability_remediated` helper or a
  sibling `mark_vulnerability_rescan_verified` (new REMEDIATED-adjacent transition) — must
  stay consistent with Phase 36's single-helper discipline (D-09/Pitfall 6) and MTTR capture.
- Where the per-connector "last successful sync" surfaces in the UI (connector list already
  shows sync status — SYNC-04 likely extends that, not a new screen).
</decisions>

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Roadmap
- `.planning/REQUIREMENTS.md` — SYNC-01..04 (Phase 37 block).
- `.planning/ROADMAP.md` — Phase 37 goal + success criteria.

### Existing ticketing machinery to EXTEND (not replace)
- `backend/app/ticketing/daily_sync.py` — the scheduler sync pass. Already does a *partial*
  inbound read (e.g. `_sync_asana_tickets` sets `ticket.external_status = "completed"`).
  Phase 37 generalizes this to all three providers + writes back onto the finding.
- `backend/app/ticketing/{jira_client,asana_client,github_client}.py` — provider clients
  (reuse their status-read calls; add status fetch where missing).
- `backend/app/ticketing/models.py` — `Ticket.external_status` (String 50) already exists;
  `Ticket` ↔ finding link via `vulnerability_ids` grouping. `SyncLog` table for audit.
- `backend/app/ticketing/service.py`, `router.py` — ticket CRUD + linkage.

### Vulnerability side (consume, keep consistent)
- `backend/app/vulnerabilities/service.py::mark_vulnerability_remediated` (Phase 36) — the
  SINGLE REMEDIATED-transition helper + MTTR capture. Auto-close and reopen MUST route
  through this discipline, not write `status` directly.
- `Vulnerability.last_seen_at` / scanner sync in `backend/app/connectors/scheduler.py` — the
  signal for "absent from N scans". `status` enum: OPEN / IN_PROGRESS / REMEDIATED / SUPPRESSED / FALSE_POSITIVE.

### Infra / resilience precedent (SYNC-04)
- `ConnectorConfig.last_sync_at` / `last_sync_status` / `last_sync_record_count` +
  `directory_sync.py` / `humaans_sync.py` SUCCESS/FAILED pattern — the established
  "surface last successful sync per connector" precedent to mirror for ticketing.
- In-process asyncio scheduler only; audit every status write (tenant-scoped audit event).

## Existing Code Insights

### Reusable Assets
- Scheduler sync pass + three provider clients + `Ticket.external_status` column already exist
  → SYNC-01 is an *extension*, not greenfield.
- `mark_vulnerability_remediated` + `RemediationEvent` (Phase 36) → auto-close reuses the
  MTTR-capturing transition path.
- Connector `last_sync_status` SUCCESS/FAILED pattern → SYNC-04 surfacing.

### Integration Points
- Scheduler tick (add/extend the ticketing sync job).
- Finding status writes must remain funneled through the single-helper discipline (Phase 36).
- Audit log (existing tenant-scoped `audit()` used by Phase 36 escalation + settings).

## Deferred Ideas
- **Inbound webhooks / real-time status push** — deferred from D-01; a later phase can add a
  webhook ingress + signature verification if real-time becomes a requirement.
- **Tenant-configurable auto-close threshold N** — fixed at 2 this phase (D-02); promote to a
  setting later if requested.

---

_Decisions captured via /gsd-discuss-phase 37 (2026-08-14). Ready for /gsd-plan-phase 37._
