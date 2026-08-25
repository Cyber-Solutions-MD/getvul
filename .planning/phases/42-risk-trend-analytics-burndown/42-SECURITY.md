---
phase: 42
slug: risk-trend-analytics-burndown
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: 2026-08-22
---

# Phase 42 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| browser → `/api/v1/analytics/overview` | Untrusted session + query params (`days`, `scope`, `group_id`, `from`, `to`) cross into the read endpoint | Session token; unvalidated window/scope params |
| service query → Postgres | Tenant-scoped reads over `daily_snapshots`, `vulnerabilities`, `asset_group_members` | Tenant-owned risk-exposure snapshots, open-backlog findings, group membership |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-42-01 | Information Disclosure | `get_scoped_trend_series` / `get_analytics_overview` | high | mitigate | `DailySnapshot.tenant_id == tenant_id` inline in `.where(...)` (never post-fetch); verified by `test_overview_is_tenant_scoped` (tenant_b never leaks) | closed |
| T-42-02 | Elevation of Privilege | `GET /overview` | high | mitigate | `Depends(require_viewer)` on the route (router.py:46, D-14); no unauthenticated path | closed |
| T-42-03 | Denial of Service | `days` query param | medium | mitigate | `days: int = Query(30, ge=7, le=365)` caps the window server-side (router.py:47) | closed |
| T-42-04 | Tampering | window param reflected into the page | low | accept | `useUrlState` clamps the window to a fixed allow-list before use; never interpolated into a query string unescaped. Low risk, no PII | closed |
| T-42-05 | Information Disclosure | `get_aging_distribution` / `get_burndown_rate` | high | mitigate | `Vulnerability.tenant_id == tenant_id` inline in `_open_backlog_conditions` (shared by both queries); tenant-scoped in tests | closed |
| T-42-06 | Tampering / integrity of open-backlog definition | exclusion predicate | medium | mitigate | `~active_exception_subquery(tenant_id, now)` applied verbatim to every open-backlog query (D-10); enforced by `test_aging_honors_exclusion_predicate` | closed |
| T-42-07 | Denial of Service | live aging scan | low | accept | Query is tenant-scoped and bounded by the `days` cap; per-tenant `vulnerabilities` volume is modest; no new unbounded surface | closed |
| T-42-08 | Information Disclosure / Elevation of Privilege (IDOR) | `group_id` scope param | high | mitigate | `_resolve_group_scope` → `list_members(db, tenant_id, group_id)` returns None for a cross-tenant group (tenant filter in WHERE) → router raises 404, never fetch-then-403; `test_cross_tenant_group_id_404` | closed |
| T-42-09 | Denial of Service | unbounded custom date range | medium | mitigate | `MAX_ANALYTICS_WINDOW_DAYS` (1096) span cap + `to >= from` validated server-side (422 otherwise); `test_custom_range_span_capped` | closed |
| T-42-10 | Tampering | reflected `from`/`to` params | low | mitigate | `from`/`to` typed as `date` Query params — parsed & validated server-side (422 on malformed), never interpolated unescaped; window preset stays allow-list-clamped via `useUrlState` | closed |
| T-42-11 | Information Disclosure | group series intersection query | high | mitigate | Per-asset dict read from the tenant's own (already tenant-scoped) snapshots; `member_ids` sourced from `list_members` (tenant-scoped) — no cross-tenant asset score can enter the average | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on (high) count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-42-01 | T-42-04 | Reflected window param is clamped to a fixed allow-list by `useUrlState` before use and never interpolated unescaped. Low risk, no PII exposure. | Igor Chemencedji | 2026-08-22 |
| AR-42-02 | T-42-07 | Live aging scan is tenant-scoped and bounded by the `days` cap; per-tenant `vulnerabilities` volume is modest and adds no new unbounded surface (custom range carries its own span cap, T-42-09). | Igor Chemencedji | 2026-08-22 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-08-22 | 11 | 11 | 0 | gsd-secure-phase (L1 grep-depth, register authored at plan time) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-08-22
