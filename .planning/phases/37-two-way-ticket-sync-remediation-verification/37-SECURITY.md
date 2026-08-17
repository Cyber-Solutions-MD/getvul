---
phase: 37
slug: two-way-ticket-sync-remediation-verification
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: 2026-08-17
---

# Phase 37 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| scanner connector → run_sync | Untrusted connector sync OUTCOME (SUCCESS vs FAILED) governs whether the absent-sweep may close findings | Sync status, finding identity |
| provider API → daily_sync / sync_ticket_status | Untrusted ticket-status payloads (Jira/Asana/GitHub) cross into finding-workflow writes | Ticket status strings, provider error text |
| analyst request → close_ticket | An authenticated analyst's explicit "Close Ticket" click must not force-close a scanner-detected finding | Ticket IDs, close intent |
| scheduler/router → AuditLog / Vulnerability writes | System-actor writes with no `CurrentUser`; rows must still carry the real `tenant_id` | tenant_id, audit details |
| provider error → last_error persistence | Raw upstream error strings may contain credentials | Bearer/Basic/api-key tokens |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-37-01 | Denial (accurate state) | run_sync absent-sweep | high | mitigate | Sweep/streak advance runs ONLY in the SUCCESS branch; FAILED/partial sync never advances a streak or false-closes findings — `connectors/sync.py:193` (auth-fail + `except` branches both return before the sweep) | closed |
| T-37-02 | Information Disclosure | system-actor AuditLog | medium | mitigate | `AuditLog(tenant_id=vuln.tenant_id, ...)` constructed directly; no `audit(user=None)` nil-UUID path — `sync.py:259-271` | closed |
| T-37-03 | Tampering | streak counter | high | mitigate | Sweep `select(Vulnerability)` scoped to the connector's own `tenant_id` + `source` — `sync.py:246-253` | closed |
| T-37-04 | Repudiation | auto-close decision | medium | mitigate | Each rescan-verified close writes an `AuditLog` (streak+source) and a durable `RemediationEvent` — `sync.py:258-272`, `vulnerabilities/service.py:412-420` | closed |
| T-37-05 | Tampering | reopen branch | high | mitigate | Reopen resolves via `uq_vuln_dedup(tenant, cve, asset, source)` — no cross-tenant resurrection — `sync.py:438-446`, `:472-475` | closed |
| T-37-06 | Information Disclosure | reopen AuditLog | medium | mitigate | `reopen_vulnerability` writes `AuditLog(tenant_id=vuln.tenant_id, ...)` — `vulnerabilities/service.py:464-476` | closed |
| T-37-07 | Repudiation | recurrence decision | low | accept | Reopen writes an audit row and never deletes/touches historical `RemediationEvent` rows — full close→reopen timeline reconstructable (`service.py:439-478`) | closed |
| T-37-08 | Tampering | map_ticket_status | high | mitigate | Whitelist mapper with `.get`-defaulted reads; empty/garbage payload → `"unknown"`, never `"remediated"` — `ticketing/service.py:1133-1179` | closed |
| T-37-09 | Elevation / integrity | ticket-done path | high | mitigate | `mark_vulnerability_remediated` removed from all ticket-done arms; done ticket sets `IN_PROGRESS` only (grep count = 0 in `app/ticketing/*.py`) — `daily_sync.py:356-371/463-479/584-599` | closed |
| T-37-10 | Information Disclosure | last_error persistence | high | mitigate | Only `_sanitize_error(e)` (Bearer/Basic/32+char token scrub) persisted — `sync.py:46-64`, used at `sync.py:217/220/223`, `daily_sync.py:71/182/191/193` | closed |
| T-37-11 | Information Disclosure | system-actor AuditLog | medium | mitigate | Direct `AuditLog(tenant_id=vuln.tenant_id, ...)`, never nil-UUID — `daily_sync.py:360-371/467-479/587-599` | closed |
| T-37-12 | Denial (accurate state) | poll failure | medium | mitigate | `_sync_with_retry` (3 attempts, 1/2/4s backoff) + per-connector isolation + FAILED surfacing; `clean_scan_streak` never referenced in `daily_sync.py` — `daily_sync.py:49-75`, `:122-194` | closed |
| T-37-13 | Spoofing | inbound ingress | low | accept | D-01: polling only, no public webhook ingress — `grep webhook router.py` → none; all 19 routes analyst-initiated or scheduler-polled | closed |
| T-37-14 | Elevation / integrity | sync_ticket_status ticket-done arm | high | mitigate | `sync_ticket_status` done arm sets `IN_PROGRESS` only; no `mark_vulnerability_remediated` in the function — `ticketing/service.py:1257-1281` | closed |
| T-37-15 | Elevation / integrity | close_ticket manual close | high | mitigate | Manual analyst close drives finding to `IN_PROGRESS` + awaiting-rescan audit, never `REMEDIATED`; returns `findings_awaiting_rescan` — `service.py:1443-1470`, `:1477` | closed |
| T-37-16 | Tampering | map_ticket_status payload | medium | mitigate | Same `.get`-defaulted whitelist mapper (`service.py:1133-1179`) reused by both `sync_ticket_status` and `close_ticket` call sites | closed |
| T-37-17 | Repudiation | system-actor status write | medium | mitigate | Every IN_PROGRESS transition writes `AuditLog(user_email="system:ticket-sync", tenant_id=vuln.tenant_id, action="vuln.ticket_status_sync")` — `service.py:1269-1281`, `:1452-1469` | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on (high) count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-37-01 | T-37-07 | Recurrence reopen writes an audit row and retains the historical `RemediationEvent`, so the full close→reopen timeline is reconstructable — no further control needed | Phase 37 threat model (plan-time) | 2026-08-17 |
| AR-37-02 | T-37-13 | D-01 locks the design to polling only (no public webhook ingress), so there is no inbound signature-verification attack surface to defend | Phase 37 threat model (plan-time) | 2026-08-17 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-08-17 | 17 | 17 | 0 | gsd-security-auditor (sonnet) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-08-17
