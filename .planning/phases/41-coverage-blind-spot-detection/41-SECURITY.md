---
phase: 41
slug: coverage-blind-spot-detection
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: 2026-08-21
---

# Phase 41 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| browser → GET /api/v1/coverage/blind-spots, /summary | authenticated analyst/viewer read of the tenant's reconciliation + connector aggregates | tenant-scoped asset UUIDs, coverage counts |
| browser → POST /api/v1/coverage/assets/{id}/route-to-owner | authenticated write that triggers an outbound owner/admin notification | untrusted `asset_id` path param; tenant scope |
| API → Postgres | every reconciliation/summary/asset-lookup query must be tenant-bounded in the WHERE clause | tenant-isolated rows |
| Intune Graph API → sync worker → Postgres | external tenant-scoped connector devices become Asset rows + SyncLog | tenant-bound device inventory |
| API → SMTP / Slack / Teams | route-to-owner emails the resolved owner (or admins) and pushes to the tenant alert channel | notification body (hostname, routed_to); tenant-admin-controlled webhook URL |
| browser UI → coverage write endpoint | client gates the action by role, but the server remains authoritative | React-escaped text nodes only |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-41-01 | Information Disclosure | GET /blind-spots list/count/exists query | high | mitigate | `Asset.tenant_id == tenant_id` in every WHERE clause — list (service.py:100-105), count subquery (107-108), authoritative-count (76), covered-count (159-163); never fetch-then-filter | closed |
| T-41-02 | Information Disclosure | `_get_asset_or_404` (by-id lookup) | high | mitigate | tenant_id IN the WHERE clause (router.py:45); cross-tenant id → 404 not 403/500 (IDOR, mirrors exceptions T-39-01) | closed |
| T-41-03 | Elevation of Privilege | GET endpoints | low | accept | reads require `require_viewer` (lowest authed role); no write in Plan 01 — see Accepted Risks R-41-01 | closed |
| T-41-04 | Tampering | route placement | medium | mitigate | page lives under `(authed)/dashboard/coverage` so the existing auth guard + shell apply (page.tsx module doc, Pitfall 2) | closed |
| T-41-05 | Tampering / Information Disclosure | `run_intune_sync` Asset lookup/create | high | mitigate | tenant_id in both Asset selects (intune_sync.py:156,166) and the Asset constructor (176) — closes the latent cross-tenant matching bug | closed |
| T-41-06 | Repudiation | SyncLog persistence | medium | mitigate | corrected `SyncLog(connector_id=…, tenant_id=…)` now actually records the sync attempt/outcome per tenant (intune_sync.py:122-124); `connector_config_id` TypeError removed (0 occurrences) | closed |
| T-41-07 | Information Disclosure | `get_coverage_summary` connector + asset counts | high | mitigate | tenant_id in every ConnectorConfig (service.py:181-185) and Asset (159-163, 76) WHERE clause; a tenant sees only its own connectors + coverage numbers | closed |
| T-41-08 | Elevation of Privilege | GET /summary | low | accept | `require_viewer` only (read); no write introduced — see Accepted Risks R-41-01 | closed |
| T-41-09 | Tampering (data integrity of displayed metric) | last_sync_status wire mapping | medium | mitigate | normalized via `_normalize_sync_status` (service.py:205) so the pill reflects true state rather than silently degrading (Pitfall 3) | closed |
| T-41-10 | Elevation of Privilege | POST /route-to-owner | high | mitigate | `Depends(require_analyst)` (router.py:83); viewer 403; asymmetric with the `require_viewer` GETs (D-08); asserted by `test_coverage` RBAC test | closed |
| T-41-11 | Information Disclosure | `_get_asset_or_404` on the POST | high | mitigate | tenant_id in the WHERE clause (router.py:45,93); cross-tenant asset_id → 404 (IDOR); `test_coverage` cross-tenant-404 test | closed |
| T-41-12 | Repudiation | route-to-owner audit | high | mitigate | fail-closed `audit(db, user, "coverage.route_to_owner", …)` with who/what/routed_to, audit-then-commit so any audit failure aborts the write (router.py:96-97, D-08) | closed |
| T-41-13 | Tampering (SSRF) | tenant alert-channel push (D-09) | high | mitigate | routes through `dispatch_channel`, which validates every outbound webhook URL via the existing `_validate_webhook_url` SSRF guard (escalation_channels.py:214,222 — https-only + private/loopback/link-local/metadata block); never a hand-rolled outbound POST | closed |
| T-41-14 | Denial of Service (notification abuse via repeated calls) | repeatable notify action | low | accept | repeatable by design (no state transition); every call audited so abuse is attributable; analyst-gated limits the actor set — see Accepted Risks R-41-02 | closed |
| T-41-15 | Elevation of Privilege | client-side Route-to-owner gating | medium | mitigate | `canRouteToOwner` disables/hides the action for viewers (page.tsx:195-196,238); the Plan 04 `require_analyst` gate is the authoritative defense-in-depth (client gate is UX only, never the security boundary) | closed |
| T-41-16 | Tampering (retry duplicating notifications) | `useRouteToOwner` | medium | mitigate | `retry: 0` (use-route-to-owner.ts:52) — a mutation with audit/notification side effects is never auto-retried | closed |
| T-41-17 | Information Disclosure | DrillPanel content | low | accept | renders only the tenant's own already-fetched blind-spot asset summary; no new data fetch beyond the tenant-scoped list — see Accepted Risks R-41-03 | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on (high) count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

**Note on `accept` dispositions:** T-41-15 (client-side route-to-owner gating) was dispositioned `mitigate` on the principle that *frontend gates are UX only — the server `require_analyst` (T-41-10, closed) is the authority*. Every `accept` disposition (T-41-03/08 read-only viewer reads, T-41-14 repeatable-by-design notify, T-41-17 already-fetched drill data) is a documented risk with no residual server-side exposure — the authoritative server-side control for each mutation path is itself `mitigate` and verified closed above.

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-41-01 | T-41-03, T-41-08 | GET /blind-spots and /summary are read-only, tenant-scoped, and gated at the lowest authed role (`require_viewer`); no privileged data or write is exposed. | Plan 41-01/41-03 threat model | 2026-08-21 |
| R-41-02 | T-41-14 | Route-to-owner is a repeatable notify-only action (no state transition, no idempotency guard by design, D-09); every call is audited (attributable) and analyst-gated (bounded actor set), so repeated-call abuse is detectable and constrained. | Plan 41-04 threat model | 2026-08-21 |
| R-41-03 | T-41-17 | The coverage asset DrillPanel renders only the tenant's own already-fetched blind-spot summary (no separate fetch), so it introduces no new data-crossing beyond the tenant-scoped list query already gated by T-41-01. | Plan 41-05 threat model | 2026-08-21 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-08-21 | 17 | 17 | 0 | /gsd-secure-phase (L1 grep-depth short-circuit; register authored at plan time across all 5 plans; every `mitigate` mitigation re-verified live in source — tenant-scoped WHERE clauses, `_get_asset_or_404` IDOR-404, `require_analyst`/`require_viewer` RBAC deps, audit-then-commit, `_validate_webhook_url` SSRF reuse in `dispatch_channel`, `retry: 0`, `canRouteToOwner` UX gate, Intune tenant-scoped upsert + SyncLog fix; cross-checked against 16/16 passing backend + 37/37 frontend tests reported in 41-VERIFICATION.md) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-08-21
