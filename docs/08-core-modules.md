# 08 — Core Modules

The backend is split into domain modules under `backend/app/`. Each module owns its models, services, schemas, and routes. The frontend mirrors this with feature folders under `frontend/src/app/dashboard/`.

## Backend modules

### `auth/`

**Purpose** — All authentication and authorization concerns.

**Public surface**
- `/auth/*` HTTP endpoints (11) — see [10-api-reference.md](10-api-reference.md)
- `get_current_user(token: str = Depends(oauth2_scheme))` — main user dependency
- `require_role(min_role: Role)` — RBAC factory used by every protected route
- `Role` enum: `OWNER (40) > ADMIN (30) > ANALYST (20) > VIEWER (10)`

**Files**
- [backend/app/auth/router.py](../backend/app/auth/router.py) — endpoints: login, callback, refresh, me, logout, register, password change, forgot/reset password, config
- [backend/app/auth/jwt.py](../backend/app/auth/jwt.py) — `issue_access_token`, `issue_refresh_token`, `decode_token` (HS256)
- [backend/app/auth/providers.py](../backend/app/auth/providers.py) — `GoogleOIDCProvider`, `AzureOIDCProvider` with discovery + token exchange
- [backend/app/auth/password.py](../backend/app/auth/password.py) — bcrypt + policy validator
- [backend/app/auth/rbac.py](../backend/app/auth/rbac.py) — Role enum + `require_role` Depends factory
- [backend/app/auth/dependencies.py](../backend/app/auth/dependencies.py) — `get_current_user`, `get_optional_user`

**Dependencies** — `pydantic`, `python-jose`, `bcrypt`, redis (for OIDC state), Postgres `users` + `tenants` tables.

**Invocation paths** — Mounted at `/auth` ([main.py:191](../backend/app/main.py#L191)). Frontend calls happen in [frontend/src/lib/auth.tsx](../frontend/src/lib/auth.tsx).

---

### `db/`

**Purpose** — SQLAlchemy async engine + session factory. Every other module imports `get_db` from here.

**Public surface**
- `get_db()` — async dependency yielding an `AsyncSession`
- `async_session_factory` — used by lifespan (no Depends context)
- `Base`, `UUIDPrimaryKeyMixin`, `TimestampMixin` — declarative bases

**Files**
- [backend/app/db/session.py](../backend/app/db/session.py)
- [backend/app/db/base.py](../backend/app/db/base.py)

---

### `tenants/` and `users/`

**Purpose** — Tenant & user management, plus directory views merging IdP-synced users with device owners.

**Public surface** — `/api/v1/tenant/*` (14 endpoints; settings, users CRUD, audit log, groups), `/api/v1/users/*` (3 endpoints; list, stats, directory).

**Files** — `tenants/{models,service,router}.py`, `users/{router}.py`.

**Notable** — Tenant model holds JSONB columns for `syslog_config`, `smtp_config`, `password_policy`, `sla_policy`, `branding`. Plus `sso_enforced`, `idp_provider` (LOCAL/GOOGLE/AZURE_ENTRA_ID), `timezone`. Users have JSONB `groups` and `password_history`.

---

### `assets/`

**Purpose** — Device inventory + risk scoring + classification.

**Public surface** — `/api/v1/assets/*` (8 endpoints).

**Files**
- `assets/models.py` — Asset entity (hostname, IPs, MACs, OS, scanner-specific IDs `crowdstrike_aid`/`defender_device_id`/`wiz_asset_id`/`nessus_host_id`/`jamf_id`, MDM details JSONB, containment_status)
- `assets/classification.py` — Device categorization (CrowdStrike product_type → hostname patterns → OS patterns → fallback OTHER)
- `assets/service.py` — Risk scoring (piecewise log curve, see [02-architecture.md](02-architecture.md)), filter/list/stats
- `assets/router.py`

**Notable** — Unique constraint `(tenant_id, hostname)`. Classification is on-demand via `POST /api/v1/assets/classify` (Admin+).

---

### `vulnerabilities/`

**Purpose** — The biggest module. Vuln CRUD, statistics, SLA tracking, remediation grouping, cross-source correlation, saved filters.

**Public surface** — `/api/v1/vulnerabilities/*` (25 endpoints).

**Files**
- `vulnerabilities/models.py` — `Vulnerability`, `VulnerabilityCorrelation`, `Severity` / `VulnStatus` / `VulnSource` / `Confidence` enums. Unique `(tenant_id, cve_id, asset_id, source)`.
- `vulnerabilities/service.py` — Filtering, paginated lists, stats, SLA calc, status transitions
- `vulnerabilities/remediation_service.py` — Per-host and per-remediation grouping
- `vulnerabilities/schemas.py` — Pydantic request/response

**Notable** — `VulnSource` enum currently lists 4 sources (`CROWDSTRIKE`, `NESSUS`, `DEFENDER`, `WIZ`) but connectors for Qualys and Rapid7 also exist. Phase 4 (PROD-04-03) will extend the enum + add a migration.

---

### `connectors/`

**Purpose** — All external integrations + the in-process scheduler that drives them.

**Public surface**
- `/api/v1/connectors/*` (8 endpoints) — config CRUD, test creds, sync trigger
- `start_scheduler()` / `stop_scheduler()` — lifespan hooks
- `BaseConnector` ABC — implemented by every scanner connector

**Files**
- `connectors/base.py` — Abstract base + normalized response types (`NormalizedVulnerability`, `NormalizedAsset`, `NormalizedMisconfiguration`)
- `connectors/scheduler.py` — In-process tick (~60s) that fans out connector syncs, ticket rules, scheduled reports, SLA breach checks
- `connectors/sync.py` — `run_sync(db, connector)` orchestration
- `connectors/service.py` — Connector CRUD with credential encryption
- `connectors/tester.py` — Pre-save credential validation
- Connector implementations: `crowdstrike.py`, `nessus.py`, `defender.py`, `wiz.py`, `qualys.py`, `rapid7.py`, `jamf.py`, `intune_sync.py`, `okta_sync.py`, `humaans.py`/`humaans_sync.py`, `google_workspace.py`, `azure_entra.py`, `directory_sync.py`
- Ticketing clients (lives here for historical reasons): `jira_client.py`, `jira_sync.py`

**Notable** — Credentials are encrypted at-rest with Fernet, stored in `connector_configs.credentials_secret_arn` (TEXT). Decrypted only in memory during a sync. Each connector has `last_sync_at`, `last_sync_status`, `last_sync_record_count`. See [11-integrations.md](11-integrations.md) for per-vendor details.

---

### `cspm/`

**Purpose** — Cloud Security Posture Management findings + compliance framework scoring.

**Public surface** — `/api/v1/cspm/*` (8 endpoints).

**Files** — `cspm/{models,service,schemas,router}.py`. `Misconfiguration` entity with `category` (IAM, NETWORK, ENCRYPTION, LOGGING, STORAGE, COMPUTE, DATABASE, OTHER), `frameworks` (JSONB list), `cloud_provider`, `cloud_account_id`, `resource_type`, `resource_region`.

**Notable** — Unique constraint `(tenant_id, rule_id, resource_id, source)`. Compliance scoring against CIS, SOC 2, PCI-DSS, HIPAA frameworks.

---

### `ticketing/`

**Purpose** — Asana + Jira integration, ticket lifecycle, automation rules.

**Public surface** — `/api/v1/tickets/*` (17 endpoints — list, create, bulk action, rules CRUD, Asana setup).

**Files** — `ticketing/{models,service,router}.py`. `Ticket`, `TicketRule`, `ConnectorConfig`, `SyncLog` entities.

**Notable** — Per-host (one task per asset, all its remediations) vs per-remediation (one task per fix, all affected hosts) tickets. SLA-based due dates. Daily sync auto-closes external tasks when GetVul vulns are resolved. The `jira_client.py` lives in `connectors/` for historical reasons.

---

### `notifications/`

**Purpose** — In-app bell + 4 scheduled alert checks + email delivery.

**Public surface** — `/api/v1/notifications/*` (5 endpoints — list, unread-count, mark read, mark-all-read, delete).

**Files** — `notifications/{models,service,router}.py`. The 4-check alert engine is split across these.

**Dedup keys & lookback windows** — see the table in [02-architecture.md](02-architecture.md).

---

### Inline routes in `main.py`

[backend/app/main.py:203-528](../backend/app/main.py#L203) hosts inline routes that didn't merit their own router:

- `/health` — public liveness check
- `/api/v1/export/{resource}` — CSV/PDF/TXT export
- `/api/v1/reports/*` — scheduled reports CRUD + send
- `/api/v1/smtp/*` — SMTP test connection / test email
- `/api/v1/certificates/*` — TLS cert upload / generate self-signed / delete

---

### Helper modules

| Module | Purpose |
|--------|---------|
| `audit.py` | `audit(db, user, action, resource_type, resource_id, details)` writes to `audit_logs`. `configure_syslog(host, port, protocol, facility)` enables CEF forwarding. |
| `encryption.py` | `encrypt_value(plaintext) -> str`, `decrypt_value(ciphertext) -> str`. Fernet key from `ENCRYPTION_KEY`. |
| `pagination.py` | Generic `PaginatedResponse[T]` and `PaginationParams` (page, page_size). |
| `email.py` | SMTP delivery using tenant's `smtp_config`. |
| `enrich_assets.py` | Merge MDM/HR/IdP data onto assets after sync. |
| `redis_client.py` | `get_redis(request: Request)` FastAPI Depends — yields `request.app.state.redis` (added in Phase 1). |
| `search.py` | Global search across vulns, assets, users, tickets, CSPM. |

## Frontend feature areas

| Route | Purpose | Notes |
|-------|---------|-------|
| `/login` | Email/password + SSO buttons + password reset flow | [frontend/src/app/login/](../frontend/src/app/login/) |
| `/dashboard` | Stat cards, severity/risk/source distribution, top hosts, connector health, SLA widget, trend charts, exec report tab | ~925 LOC in `dashboard/page.tsx`. Charts are pure SVG/CSS (recharts is in deps but unused). |
| `/dashboard/vulnerabilities` | Tabbed: Vulnerabilities + Remediations. Filters, bulk actions, per-host drilldown | ~658 LOC |
| `/dashboard/assets` | Filter, classify, recompute risk, ignore, asset detail with MDM + containment | |
| `/dashboard/users` | Unified directory (IdP + device owners), Active/Suspended/All filter, groups CSV export, expandable per-user device list | |
| `/dashboard/cspm` | 4 tabs: Findings, Compliance, Resources, Trends | |
| `/dashboard/connectors` | Card per connector, test/trigger sync/edit/delete | |
| `/dashboard/tickets` | Asana + Jira list, automation rules, bulk close/comment/sync/delete | |
| `/dashboard/settings` | Org, Authentication, SLA, TLS, SMTP, Branding, Users, Audit log, Reports | |

### Frontend cross-cutting modules

- [frontend/src/lib/api.ts](../frontend/src/lib/api.ts) — `api<T>(path, options)` fetch wrapper. Auto-refreshes token on 401, stores `getvul_token` + `getvul_refresh` in `localStorage`, redirects to `/login` on refresh failure.
- [frontend/src/lib/auth.tsx](../frontend/src/lib/auth.tsx) — `AuthProvider`, `useAuth()`. Methods: `login`, `register`, `loginSSO`, `logout`. User shape: `{ id, email, display_name, avatar_url, role, tenant_id, tenant_name }`.
- [frontend/src/lib/theme.tsx](../frontend/src/lib/theme.tsx) — `ThemeProvider`, `useTheme()`. Default dark, persisted in `localStorage`.
- [frontend/src/lib/utils.ts](../frontend/src/lib/utils.ts) — `cn()` helper (clsx + tailwind-merge).
- [frontend/src/components/layout/](../frontend/src/components/layout/) — Sidebar, Header, NotificationBell, GlobalSearch (Cmd+K).
- [frontend/src/components/ui/](../frontend/src/components/ui/) — Badge, ConfirmModal, ExportButton, Pagination, Toast.

### Cross-cutting state model

| Concern | Mechanism |
|---------|-----------|
| Auth state | React Context (`AuthProvider`) — token + user |
| Theme | React Context (`ThemeProvider`) — dark/light + `localStorage` |
| Toasts | React Context (`ToastProvider` in dashboard layout) |
| Server data | Manual `useEffect` + `useCallback` per page (no SWR / React Query) |
| URL state | Next.js `useSearchParams` for filter persistence on some pages |
