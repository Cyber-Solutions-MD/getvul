---
phase: 36
slug: remediation-sla-engine-escalation
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: 2026-08-18
---

# Phase 36 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Register origin: authored at plan time (all 6 PLANs carry a `<threat_model>` block).
> Verification depth: ASVS L1 (grep-depth mitigation-presence), sufficient for `threats_open: 0` at L1 per the short-circuit rule; every `mitigate` control located in the implementation and backed by a passing test (see 36-COVERAGE.md / SUMMARY coverage blocks).

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| scheduler tick → DB | server-computed sla_due_at / sla_breached / remediation_events writes; no external input | tenant-scoped finding state (non-sensitive) |
| API → browser | sla_state / sla_due_at / MTTR aggregate are server-computed; client never re-derives the formula | tenant-scoped, non-sensitive |
| GetVul server → third-party channel | outbound POST to admin-controlled webhook URLs (untrusted target) | finding/CVE/host payload |
| tenant admin/owner → settings API | SLA policy + channel secrets are user-controlled input | webhook URLs, PagerDuty routing keys, email recipients |
| DB at rest | channel secrets stored in `Tenant.sla_config` JSONB | Fernet-encrypted secrets |
| browser secret input UX | secret fields must never display stored plaintext | masked (`••••••••`) |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-36-01 | Tampering | client-side SLA state | medium | mitigate | State computed server-side, returned as string; `SlaPill` renders it directly, never recomputes tier client-side (36-01 D5 test: contradictory dueAt ignored) | closed |
| T-36-02 | Information Disclosure | cross-tenant sla_due_at write | high | mitigate | `run_sla_tier_pass` + list/detail queries filter by `tenant_id` | closed |
| T-36-03 | Denial of Service | recompute-all ticket resync each 60s tick | low | accept | Start-simple recompute-all matches existing admin-endpoint precedent; optimize only if tick duration is a measured problem (Open Question #5) | closed |
| T-36-esc-ssrf | Tampering / Information Disclosure | outbound webhook POST | high | mitigate | `_validate_webhook_url`: https-only allowlist, blocks private/loopback/link-local/metadata IPs+hosts; `httpx.AsyncClient(follow_redirects=False)` (escalation_channels.py:69,196) | closed |
| T-36-esc-leak | Information Disclosure | finding/CVE/host payload sent to attacker-pointed URL | high | mitigate | SSRF guard above prevents redirection of the payload to internal targets | closed |
| T-36-esc-flood | Denial of Service | duplicate channel POSTs | medium | mitigate | `UniqueConstraint(tenant_id,vulnerability_id,to_state,channel)` = `uq_escalation_once` (models.py:236) | closed |
| T-36-esc-tenant | Information Disclosure | cross-tenant escalation rows | high | mitigate | `tenant_id` FK + index on `sla_escalation_events`; every query tenant-scoped | closed |
| T-36-fire-once | Denial of Service (alert flood) | detect_and_escalate | high | mitigate | `_escalation_already_fired` check-before-insert + `db.begin_nested()`/`IntegrityError` savepoint backstop; idempotent under double-tick (sla_tier_service.py:269,407,421) | closed |
| T-36-fire-dup | Denial of Service | legacy `_check_sla_breaches` double-fire | high | mitigate | Legacy path reconciled to no-op; one breach = one signal (D-08; 36-03 D5 test) | closed |
| T-36-fire-audit | Repudiation | escalation fire without audit | medium | mitigate | Fail-closed `_audit_escalation_fire` → `audit("sla.escalation_fire")` on every fire, success or failure (sla_tier_service.py:309,336) | closed |
| T-36-fire-spoof | Spoofing | forged escalation history | medium | mitigate | Rows written only by the server tick; read endpoint tenant-scoped (IDOR-safe, 36-03 D6 test) | closed |
| T-36-fire-isolation | Denial of Service | one bad tenant/channel stalls the tick | medium | mitigate | Pattern-1 own-try/except isolation; failed POST recorded, never raised (36-02) | closed |
| T-36-mttr-tenant | Information Disclosure | remediation_events cross-tenant | high | mitigate | `tenant_id` FK + index; `get_mttr_by_tier` and endpoint filter by `tenant_id` | closed |
| T-36-mttr-rbac | Elevation of Privilege | MTTR endpoint access | high | mitigate | `require_admin` on `GET /vulnerabilities/mttr/by-tier` (router.py:269) | closed |
| T-36-mttr-drop | Tampering (data integrity) | a missed REMEDIATED site drops MTTR | medium | mitigate | Single `mark_vulnerability_remediated()` helper + test exercising all 7 sites (Pitfall 6; 36-04 D2) | closed |
| T-36-sec-atrest | Information Disclosure | channel secrets in sla_config | high | mitigate | Fernet `encrypt_value` at rest (D-14) on channel secret fields (tenants/router.py:356) | closed |
| T-36-sec-readback | Information Disclosure | GET /settings round-trip | high | mitigate | `_safe_sla` mask-on-read + keep-stored-on-masked-write; browser never sees plaintext (tenants/router.py:127,353) | closed |
| T-36-sec-rbac | Elevation of Privilege | policy edit by non-owner | high | mitigate | `require_admin` (GET) / `require_owner` (PATCH) preserved (D-10; tenants/router.py) | closed |
| T-36-sec-ssrf-pre | Tampering | storing an internal webhook URL | medium | mitigate | `_validate_https_url` save-time https-only validation (defense-in-depth with send-time SSRF guard; tenants/router.py:38) | closed |
| T-36-sec-audit | Repudiation | policy change without audit | medium | mitigate | Fail-closed `audit("sla.policy_update")` before commit (tenants/router.py:370) | closed |
| T-36-ui-secret | Information Disclosure | secret fields round-tripping plaintext | high | mitigate | Seed EMPTY + `••••••••` placeholder + touched-flag; only touched secrets sent (mirrors backend mask, D-14; 36-06) | closed |
| T-36-ui-rbac | Elevation of Privilege | non-admin sees the pane | high | mitigate | `sla` added to `ADMIN_ONLY`; isAdmin gate in settings-sidebar-shell (D-10; 36-06) | closed |
| T-36-ui-xss | Tampering | rendering server error_message/URL text | low | accept | React escapes text by default; values rendered as text, not HTML; truncate+title only | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on (high) count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-36-01 | T-36-03 | Recompute-all ticket resync each 60s tick is start-simple and matches the existing admin-endpoint precedent; low severity, single-tenant scale. Optimize only if tick duration is a measured problem (Open Question #5). | plan-time disposition (36-01 PLAN) | 2026-08-18 |
| AR-36-02 | T-36-ui-xss | Server `error_message` / URL strings are rendered as React text nodes (auto-escaped), never as HTML; truncate+title only. No injection surface. Low severity. | plan-time disposition (36-06 PLAN) | 2026-08-18 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-08-18 | 23 | 23 | 0 | gsd-secure-phase (L1 short-circuit; orchestrator) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-08-18
