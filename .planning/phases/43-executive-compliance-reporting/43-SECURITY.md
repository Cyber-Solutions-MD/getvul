---
phase: 43
slug: executive-compliance-reporting
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: 2026-08-24
---

# Phase 43 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| browser → GET /api/v1/compliance/overview | Authenticated viewer requests own-tenant posture; must never read another tenant's findings/metrics | Tenant compliance metrics (sensitive) |
| browser → GET /api/v1/export/summary | Authenticated user requests own-tenant PDF; period/date-range params are untrusted input | Tenant PDF report + untrusted range params |
| scheduler → _send_report → SMTP | Scheduled report must deliver only the owning tenant's data to that tenant's recipients | Tenant report data over email |
| browser lens widgets → tenant-scoped read endpoints | Each widget reads only the caller's own-tenant data; lens selection is presentation-only and never changes authorization | Tenant MTTR/SLA/compliance reads |
| compliance/service.py → underlying services | Reuses tenant-scoped read functions; must pass the caller's tenant_id, never a client-supplied one | Cross-service tenant_id propagation |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-43-01 | Information Disclosure | GET /api/v1/compliance/overview | high | mitigate | `compliance/router.py:28,34` — `require_viewer` + inline `user.tenant_id` to every service call; cross-tenant read blocked (`test_compliance.py::test_compliance_overview_cross_tenant_isolation`) | closed |
| T-43-02 | Tampering-by-omission | evaluate_catalog / service metric guards | high | mitigate | `compliance/catalog.py:166-197` None short-circuit before threshold compare; `compliance/service.py:89,97` `get_sla_metrics(exclude_exceptions=True)` + `remediated_total>0` guard | closed |
| T-43-03 | Spoofing | require_viewer auth | low | accept | Existing auth stack (JWT/session) reused verbatim; no new auth surface (`compliance/router.py:16,28`) | closed |
| T-43-04 | Elevation of Privilege | lens/role confusion | low | accept | Read-only viewer-gated `GET /overview`; catalog is a frozen-dataclass, zero-I/O in-code list | closed |
| T-43-05 | Denial of Service | export_resource custom date range | high | mitigate | `main.py:465-474` — both-or-neither + `to<from` rejection + `(to-from).days > MAX_ANALYTICS_WINDOW_DAYS` span cap; 3 × 422 branches tested (`test_export.py:524-541`) | closed |
| T-43-06 | Information Disclosure | export_resource / _send_report | medium | mitigate | `main.py:517` passes `user.tenant_id`; `reports.py:227,268` `_send_report` uses `report.tenant_id`/`report.recipients` only | closed |
| T-43-07 | Tampering-by-omission | new SLA/MTTR PDF sections | high | mitigate | `export.py:543` `exclude_exceptions=True`; `export.py:1067,1073,1093` "Not yet measured" gated on `remediated_total==0` | closed |
| T-43-08 | Repudiation | export audit trail | medium | mitigate | `main.py:492-499` — `audit(db, user, "export.summary", ...)` extended with resolved period/sections | closed |
| T-43-09 | Injection (V5) | chart labels | low | accept | Chart text from tenant's own trusted DB data; matplotlib `Figure`+`FigureCanvasAgg` renders text as raster, no eval/template surface | closed |
| T-43-10 | Denial of Service | client custom range | low | mitigate | Client `isCustomRangeValid`/`rangeOrderError` (`export-board-report-dialog.tsx:110-112,235-236`); server span cap (T-43-05) authoritative | closed |
| T-43-11 | Information Disclosure | blob download auth | medium | mitigate | `export-board-report-dialog.tsx:118-181` Bearer-token fetch + 401-refresh-retry; token never in URL | closed |
| T-43-12 | Spoofing | scheduled-report recipients | low | accept | Dialog POSTs to pre-existing `/api/v1/reports` CRUD; no new recipient-config endpoint introduced | closed |
| T-43-13 | Elevation of Privilege | lens vs RBAC confusion | high | mitigate | `use-lens.ts`/`lens-switcher.tsx` reference no `User.role`/RBAC; lens-branched widgets call existing `require_viewer`/tenant-scoped routes (`vulnerabilities/router.py:203-220`) | closed |
| T-43-14 | Information Disclosure | mttr/sla/compliance reads | medium | mitigate | `vulnerabilities/router.py:220,294` — `mttr/by-tier` + `sla/metrics` call services with `user.tenant_id`; no client-supplied tenant id | closed |
| T-43-15 | Tampering-by-omission | metric tiles / SLA source consistency | high | mitigate | `sla-compliance-tile.tsx:31` + `mttr-by-tier-tile.tsx:58` null-signal → "Not yet measured"; `use-sla-metrics.ts:37` `exclude_exceptions=true`; end-to-end regression (`test_sla_route.py`) | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on (high) count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-43-01 | T-43-03 | Compliance endpoint reuses the existing `require_viewer` auth stack unchanged; adds no new authentication surface. | gsd-security-auditor | 2026-08-24 |
| AR-43-02 | T-43-04 | Endpoint is read-only viewer-gated with no role tier elevated; catalog is static in-code data (no injection surface). | gsd-security-auditor | 2026-08-24 |
| AR-43-03 | T-43-09 | Chart labels come from the tenant's own already-trusted DB data; matplotlib renders text as raster (no code-execution surface). | gsd-security-auditor | 2026-08-24 |
| AR-43-04 | T-43-12 | Scheduled-report recipients are configured by an authed user for their own tenant via the pre-existing ScheduledReport path; no new trust surface. | gsd-security-auditor | 2026-08-24 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-08-24 | 15 | 15 | 0 | gsd-security-auditor (sonnet) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-08-24
