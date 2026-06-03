---
phase: 14
slug: remaining-screens
status: verified
threats_open: 0
asvs_level: 1
created: 2026-06-03
---

# Phase 14 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| backend `connector_type`/`cloud_provider` → ConnectorMark CSS-var lookup | provider string flows into a gradient class lookup | low-trust string → CSS class name |
| user-selected resource/filters → ExportButton URL | export request params | tenant-scoped CSV request |
| client `?provider=` / `?category=` URL → add-flow / pane selection | reflected URL value selects a provider or settings pane | low-trust reflected string |
| client → POST/PATCH/DELETE `/connectors`, `/tenant/settings`, `/tenant/users`, `/cspm/bulk-status` | mutations cross to backend (Admin/Owner/Analyst-gated) | privileged write |
| stored credentials / SMTP password → edit forms | masked secrets must never reach the client | secret material (masked) |
| client `role` → reachable settings categories & directory fields | `useAuth().role` gates UX (backend is authority) | RBAC posture |
| ChipBar URL filter values → `/cspm`, `/directory` queries | reflected severity/status/source/department values | low-trust query params |
| audit log / directory / export → panes | tenant rows must not expose cross-tenant data | tenant-scoped PII |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-14-01 | Tampering | ConnectorMark CSS-var lookup | mitigate | Literal `Record<ConnectorProvider,string>` lookup; no `var(--gradient-provider-${x})` interpolation; unknown → undefined (`connector-mark.tsx:21-37,66`; grep=0) | closed |
| T-14-02 | Information disclosure | ExportButton auth token | accept | Pre-existing localStorage token (restyle-only); export tenant-scoped server-side; WR-06 adds prod `/login` redirect (`ExportButton.tsx:25-28`) | closed |
| T-14-03 | Tampering | ConfirmModal variant prop | accept | `variant` typed union; `btnColor` from literal ternary, no user string → className (`ConfirmModal.tsx:5-13,57-63`) | closed |
| T-14-04 | Elevation of privilege | SettingsSidebarShell RBAC gating | mitigate (UX) + backend-enforced | UX gating hides admin categories; backend `require_admin`/`require_owner` is authority (documented `settings-sidebar-shell.tsx:14-16,53-74`) | closed |
| T-14-05 | Tampering | useDirtyState baseline | accept | Pure client state; server validates PATCH via Pydantic (`use-dirty-state.ts`) | closed |
| T-14-06 | Information disclosure | ConnectorForm secret fields | mitigate | Backend returns `has_credentials` boolean only; sentinel pre-fill; untouched fields omit `credentials` from PATCH (`connector-form.tsx:36,77-84,112`) | closed |
| T-14-07 | Tampering (sentinel spoofing) | PATCH credentials body | mitigate | `buildCredentials()` omits key when untouched and guards `v !== SENTINEL` — sentinel literal can never reach backend (`connector-form.tsx:124-135`) | closed |
| T-14-08 | Elevation of privilege | Connector delete gating | mitigate (UX) + backend-enforced | Delete button `{isAdmin && …}`; backend DELETE requires Admin independently (`connector-card.tsx:7,132`) | closed |
| T-14-09 | Tampering | `?provider=` reflected value | mitigate | Uppercased + matched to known `/types`; unknown opens no form (`connectors/page.tsx:119-123`) | closed |
| T-14-10 | Tampering | ChipBar URL filter values (cspm) | mitigate | Every axis declares REQUIRED `allowList`; `useUrlStateList` clamps read+write (`cspm/page.tsx:42-110`, `use-url-state-list.ts:27-40`) | closed |
| T-14-11 | Elevation of privilege | bulk-status mutation | accept (backend-enforced) | `POST /cspm/bulk-status` requires Analyst+ server-side; 403 → error toast (`cspm-bulk-bar.tsx`) | closed |
| T-14-12 | Tampering | cloud_provider gradient lookup | mitigate | Same ConnectorMark literal lookup; unknown cloud_provider falls through (`connector-mark.tsx:21-37`) | closed |
| T-14-13 | Tampering | ChipBar URL filter values (users) | mitigate | `STATUS_ALLOW`/`SOURCE_ALLOW` allowLists clamped via `useUrlStateList` (`users/page.tsx:40-43,113-119`) | closed |
| T-14-14 | Information disclosure | directory/groups export | accept (backend tenant-scoped) | Backend scopes export to caller tenant; token unchanged (`users-export-bar.tsx:39-44`) | closed |
| T-14-15 | Information disclosure | RBAC role on directory | mitigate | RBAC role field NEVER rendered (Pitfall 7) (`directory-table.tsx:15,61-165`; grep=0) | closed |
| T-14-16 | Elevation of privilege | RBAC category gating + Owner mutations | mitigate (UX) + backend-enforced | UX gating + documented backend `require_admin`/`require_owner` authority; 403 → PartialFailureBanner (`settings/page.tsx:28-29`, `settings-sidebar-shell.tsx:14-16`) | closed |
| T-14-17 | Information disclosure | SMTP password in Notifications | mitigate | Field seeded empty + `passwordTouched` tracking; PATCH includes password only when explicitly edited — mask never round-trips as secret (CR-01 hardening, commit 973a9a5) (`notifications-pane.tsx:47-56,96-99,173-175`) | closed |
| T-14-18 | Tampering | SAML enforce-SSO toggle | mitigate | Enforce-SSO `disabled` until non-LOCAL `idp_provider`; auto-resets on LOCAL; mirrors backend D-SET-07 guard (`saml-pane.tsx:96-105,221`) | closed |
| T-14-19 | Information disclosure | Audit log table | accept (backend tenant-scoped) | `GET /tenant/audit-log WHERE tenant_id = caller_tenant`; pane renders only API rows (`audit-log-pane.tsx:192-231`) | closed |
| T-14-20 | Tampering | `?category=` reflected value | mitigate | `CATEGORY_ALLOW_LIST` of 6 known categories; `useUrlState` clamps unknown → `profile` (`settings/page.tsx:50-67`, `use-url-state.ts:25-28`) | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-14-01 | T-14-02 | ExportButton reuses the pre-existing localStorage token (restyle-only per RESEARCH anti-pattern); export is tenant-scoped server-side; prod no-token case redirects to `/login` | igorchemencedji@parity.io | 2026-06-03 |
| AR-14-02 | T-14-03 | ConfirmModal `variant` is a typed union; no user-controlled string reaches a className | igorchemencedji@parity.io | 2026-06-03 |
| AR-14-03 | T-14-05 | useDirtyState is pure client state; backend validates every PATCH via Pydantic | igorchemencedji@parity.io | 2026-06-03 |
| AR-14-04 | T-14-11 | `/cspm/bulk-status` is Analyst+ enforced server-side; client gating is UX only | igorchemencedji@parity.io | 2026-06-03 |
| AR-14-05 | T-14-14 | Directory/groups export is tenant-scoped by the backend; no cross-tenant rows | igorchemencedji@parity.io | 2026-06-03 |
| AR-14-06 | T-14-19 | Audit-log query is `WHERE tenant_id = caller_tenant` server-side; pane renders only API rows | igorchemencedji@parity.io | 2026-06-03 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-03 | 20 | 20 | 0 | gsd-security-auditor (ASVS L1, block_on: high) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-03
