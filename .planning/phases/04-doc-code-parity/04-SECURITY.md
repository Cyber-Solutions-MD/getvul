---
phase: 4
slug: 04-doc-code-parity
status: verified
threats_open: 0
asvs_level: 1
created: 2026-07-03
audited: 2026-07-03
auditor: gsd-security-auditor (claude-sonnet-4-6)
---

# Phase 4 — Security (Doc/Code Parity)

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| client → FastAPI backend | Untrusted browser/HTTP client receives every backend response; response headers are the last line of browser-side hardening | HTTP responses (all content types) |
| direct-to-backend (bypassing Nginx) | Internal/dev callers hit FastAPI directly; Nginx-only headers would not protect these paths | HTTP responses on API/auth paths |
| authenticated analyst → vulnerabilities API | Each analyst is scoped to one tenant; the `source` filter must never widen visibility across tenants | Vulnerability rows (tenant-scoped data) |
| operator → application config | Removing dead config/deps reduces attack surface; fewer packages, no advertised-but-unwired secret backend | Application configuration surface |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-04-01 | Tampering / XSS | SecurityHeadersMiddleware / all responses | mitigate | `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'; base-uri 'none'` emitted on every non-docs-route response. Docs routes (`/docs`, `/redoc`, `/openapi.json`) are exempt only when `settings.debug=True` (they are unmounted in production). Gate: `if not (settings.debug and request.url.path in DOCS_PATHS)`. | closed |
| T-04-02 | Elevation of Privilege | SecurityHeadersMiddleware / all responses | mitigate | `Cross-Origin-Opener-Policy: same-origin` emitted unconditionally on every response (outside the CSP conditional). Severs `window.opener` channel from cross-origin openers. | closed |
| T-04-03a | Information Disclosure | docs/16-security.md accuracy | accept | Doc-drift is not an attack surface; the drift-row flip is a correctness fix, not a runtime control. No runtime risk. Documented in Accepted Risks Log. | closed |
| T-04-03b | Spoofing / Information Disclosure | GET /api/v1/vulnerabilities source filter → VulnerabilityService._apply_filters | mitigate | `_apply_filters` (service.py:35) applies `Vulnerability.tenant_id == tenant_id` as the first WHERE clause, before the `source.in_(filters.source)` predicate (line 40). Cross-tenant rows are structurally excluded before any source filter is evaluated. Regression test `test_source_filter_tenant_scoped` asserts tenant_a sees exactly 1 of 3 seeded QUALYS rows. | closed |
| T-04-04 | Information Disclosure | Dead AWS Secrets Manager config | mitigate | Exhaustive removal: `aws_region` and `secrets_manager_prefix` absent from `Settings.model_fields`; `boto3` absent from `pyproject.toml` dependencies array; boto3 + botocore/s3transfer/jmespath uninstalled from venv. Removal-guard tests assert both conditions at runtime. | closed |
| (enum) | — | VulnSource enum extension | accept | Enum is advisory Python-only (String(30) column, not a DB enum, imported nowhere in app/ write paths). Adding QUALYS/RAPID7 members introduces no new input path, no validation gate, no attack surface. Documented in Accepted Risks Log. | closed |
| (boto3) | — | boto3 transitive supply-chain | accept→resolved | Dropping boto3 also removed botocore/s3transfer/jmespath (~30MB AWS SDK). Supply-chain reduction resolved by T-04-04 mitigation; no standalone control needed. Documented in Accepted Risks Log. | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Verification Evidence

### T-04-01 — CSP on non-docs routes (CLOSED)

**File:** `backend/app/main.py`

- **Line 89:** `DOCS_PATHS = frozenset({"/docs", "/redoc", "/openapi.json"})`
- **Line 102:** `if not (settings.debug and request.url.path in DOCS_PATHS):`
- **Lines 103–105:** `response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"`
- **Logic:** Exempt only when BOTH `settings.debug=True` AND path in DOCS_PATHS. Production (`debug=False`) → condition is always False → strict CSP applies to 100% of responses including any request to `/docs`. JSON API surface is fully covered in all environments.
- **Test coverage:** `test_strict_csp_on_api_path` (dispatch-level, no infra needed), `test_docs_routes_exempt_from_strict_csp_when_debug` (WR-01 fix verified), `test_docs_paths_get_strict_csp_when_not_debug`, `test_csp_and_coop_headers_emitted` (integration, Redis-gated).
- **WR-01 note:** Code-review finding WR-01 (strict CSP breaking Swagger UI in debug mode) was fixed in commit bc2df7b before phase completion. The `DOCS_PATHS` exemption gate is the fix. Four dispatch-level unit tests in `test_security_headers.py` verify all branches without Redis.

### T-04-02 — COOP unconditional (CLOSED)

**File:** `backend/app/main.py`

- **Line 106:** `response.headers["Cross-Origin-Opener-Policy"] = "same-origin"` — outside the CSP conditional block; executes on every response regardless of path or debug mode.
- **Test coverage:** `test_docs_routes_exempt_from_strict_csp_when_debug` asserts COOP is present even on docs routes in debug mode.

### T-04-03b — Tenant predicate precedes source filter (CLOSED)

**File:** `backend/app/vulnerabilities/service.py`

- **Line 35:** `query = query.where(Vulnerability.tenant_id == tenant_id)` — first WHERE clause applied unconditionally.
- **Lines 39–40:** `if filters.source: query = query.where(Vulnerability.source.in_(filters.source))` — source filter applied only after tenant scope is established.
- **Test:** `backend/tests/test_vuln_source_filter.py:68–81` — `test_source_filter_tenant_scoped` seeds 1 QUALYS row for tenant_a + 2 QUALYS rows for tenant_b, asserts tenant_a's client returns exactly 1 item. DB-gated (requires Postgres); runs in CI.

### T-04-04 — AWS config + boto3 exhaustive removal (CLOSED)

**File:** `backend/app/config.py`

- Settings class (lines 6–38): fields present — `app_name`, `debug`, `environment`, `database_url`, `redis_url`, `jwt_secret_key`, `jwt_algorithm`, `jwt_access_token_expire_minutes`, `jwt_refresh_token_expire_days`, `encryption_key`, `google_client_id`, `google_client_secret`, `google_redirect_uri`, `azure_client_id`, `azure_client_secret`, `azure_redirect_uri`, `sync_interval_minutes`. `aws_region` and `secrets_manager_prefix` are absent.

**File:** `backend/pyproject.toml`

- Dependencies array (lines 6–25): fastapi, uvicorn, pydantic, pydantic-settings, sqlalchemy, asyncpg, alembic, redis, python-jose, httpx, orjson, tenacity, croniter, structlog, cryptography, bcrypt, fpdf2, python-multipart. `boto3` is absent.

**Tests:** `backend/tests/test_aws_removal.py` — `test_boto3_not_installed` asserts `import boto3` raises `ModuleNotFoundError`; `test_settings_has_no_aws_fields` asserts `aws_region` and `secrets_manager_prefix` absent from `Settings.model_fields`. Both confirmed PASSED locally (per 04-VERIFICATION.md).

**Additional scrub confirmed by 04-03-SUMMARY.md:** `docs/05-configuration.md` AWS section removed; `docs/03-tech-stack.md` boto3 row removed; `.env.example` AWS lines removed; infra/ confirmed zero hits.

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-04-01 | T-04-03a | Doc-drift in docs/16-security.md is not a runtime attack surface. The drift rows (CSP/COOP "not emitted") were a correctness gap in documentation, not a gap in the deployed security controls. The fix (removing drift rows, adding accurate rows) is a correctness change. No runtime risk exists or existed. | Phase executor + phase reviewer | 2026-07-03 |
| AR-04-02 | (enum) VulnSource extension | `VulnSource` enum extension (adding QUALYS, RAPID7) is purely advisory. The `source` column is `String(30)` — not a PostgreSQL native enum — so adding Python members has zero DB impact and requires no migration. The enum is not imported in any write-validation or connector path; connectors already emit "QUALYS"/"RAPID7" as plain strings. No new input path, validation gate, or attack surface introduced. | Phase executor + phase reviewer | 2026-07-03 |
| AR-04-03 | (boto3) transitive supply-chain | Dropping `boto3>=1.35` from `pyproject.toml` and uninstalling it from the venv also removed `botocore`, `s3transfer`, and `jmespath` (~30MB AWS SDK surface). This is a supply-chain reduction achieved as a consequence of the T-04-04 mitigation (exhaustive removal of dead AWS config). No standalone ongoing control is required; the removal-guard test (`test_boto3_not_installed`) prevents re-introduction. | Phase executor + phase reviewer | 2026-07-03 |

---

## Unregistered Threat Flags

None. The only threat flag surfaced during implementation (VulnSource enum advisory-only extension from 04-02-SUMMARY.md) maps to the existing `(enum)` entry in the threat register.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-03 | 7 (4 mitigate + 3 accept/resolved) | 7 | 0 | gsd-security-auditor (claude-sonnet-4-6) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-03
