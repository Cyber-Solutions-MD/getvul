---
phase: 38
slug: remediation-campaigns
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: 2026-08-18
---

# Phase 38 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| client → API (POST/GET /campaigns, /{id}/bulk-assign, /{id}/close) | untrusted `remediation_id`, `campaign_id` path params, and mutation bodies (`provider`/`project_key`/`due_days`) cross here | tenant-scoped campaign metadata; analyst-gated on writes |
| viewer-GET → system-write | a `require_viewer` GET can trigger a system-attributed lifecycle write (lazy auto-complete / reactivate transition) | server-computed done/total counts only — never client input |
| API → DB | every campaign query must be tenant-scoped in the WHERE clause | tenant-isolated rows |
| API → external ticketing provider | bulk-assign orchestrates the existing dispatch path; no new credential handling | assignee derived from the tenant's own `asset.mdm_details` |
| browser → UI (tables, toasts, dialog body) | remediation label / owner / provider strings rendered in React | text nodes only, React-escaped |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-38-01 | Information Disclosure / Elevation | GET/POST `/campaigns/{id}` — IDOR via guessed `campaign_id` | high | mitigate | `_get_campaign_or_404` (router.py:100-108) filters `Campaign.tenant_id == tenant_id` in the WHERE clause, not post-fetch; cross-tenant id 404s, never leaks existence | closed |
| T-38-02 | Tampering | POST `/campaigns` body | medium | mitigate | `CampaignCreateRequest` `model_config = ConfigDict(extra="forbid")` (schemas.py:20) — mass-assignment defense (ASVS V5) | closed |
| T-38-03 | Repudiation | `campaign.create` / `campaign.bulk_assign` / `campaign.close` / `campaign.reactivate` audit writes | high | mitigate | `audit()` called unwrapped (fail-closed), committed with the mutation; asserted on every run by `test_bulk_assign_endpoint_audited_every_run`, `test_campaign_actions_audited` | closed |
| T-38-04 | Elevation of Privilege | RBAC on campaign mutations | high | mitigate | `Depends(require_analyst)` on POST create/bulk-assign/close; `require_viewer` on GETs (router.py:116/133/157/185/211); `test_campaign_rbac` + `test_bulk_assign_viewer_forbidden` assert viewer 403 | closed |
| T-38-05 | Tampering / Repudiation | lazy transition write inside a `require_viewer` GET | high | mitigate | write is system-attributed (`user_id=None`, `user_email="system:campaign-complete"`, service.py:184/201), derived ONLY from server-computed done/total; can only set the `closed_at`/`close_trigger` it just computed | closed |
| T-38-06 | Tampering (race) | D-11 concurrent campaign launch on the same `remediation_id` | medium | mitigate | partial unique index `uq_campaign_active_remediation (tenant_id, remediation_id) WHERE closed_at IS NULL` (migration 049, verified in live DB) + `begin_nested()` + IntegrityError re-SELECT; `test_campaign_unique_active_index` proves DB-level rejection | closed |
| T-38-07 | Information Disclosure | ticket assignee routing during bulk-assign | low | accept | assignee derived only from the tenant's own `asset.mdm_details['humaans_email']` via the existing byte-identical ticketing derivation; no new cross-tenant exposure (reuses shipped routing) | closed |
| T-38-08 | Repudiation (duplicate) | auto-complete transition audited more than once | medium | mitigate | `closed_at IS NULL` guard makes the transition single-write; `test_auto_complete_audited_once` proves idempotency | closed |
| T-38-09 | Information Disclosure (XSS) | remediation label / owner / provider strings in tables, toasts, dialog body | medium | mitigate | React text-node escaping; no `dangerouslySetInnerHTML` anywhere in the campaigns/remediations surface (grep-confirmed: only comments disclaiming it); ChipBar allow-list clamp on filter values (T-12-05 precedent) | closed |
| T-38-10 | Tampering | mutation payloads (`provider`/`project_key`) from the client | medium | mitigate | server-side `CampaignBulkAssignRequest` `extra="forbid"` (schemas.py:65) is the authority; client sends only declared fields | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on (high) count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

**Note on `accept` dispositions:** T-38-04's frontend-nav variant and T-38-05/T-38-10's client-side gates were dispositioned `accept` in the plans on the principle that *frontend gates are UX only — the server RBAC + `extra="forbid"` on every mutation is the authority*. The server-side authority for each is itself `mitigate` and verified closed above, so no client-trust risk remains open.

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-38-01 | T-38-07 | Ticket assignee is derived solely from the acting tenant's own asset MDM details via the pre-existing ticketing derivation; bulk-assign introduces no new data-crossing path. | Plan 38-02 threat model | 2026-08-18 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-08-18 | 10 | 10 | 0 | /gsd-secure-phase (L1 grep-depth short-circuit; register authored at plan time; mitigations cross-checked against 24/24 passing backend tests) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-08-18
