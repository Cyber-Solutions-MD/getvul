# Phase 24: AI Foundation + "Explain This Vuln" - Pattern Map

**Mapped:** 2026-07-28
**Files analyzed:** 37 (new + modified, backend + frontend + migrations + tests)
**Analogs found:** 34 exact/role-match/partial-match / 37 total (3 with no direct precedent, flagged below)

> Read `24-AI-SPEC.md` and `24-RESEARCH.md` first — both already lock the technical HOW (framework, streaming shape, schema, cache/audit design) and name most of these analogs. This document verifies every one of those claims against the live codebase (all line numbers below were confirmed by direct `Read` in this session, not inherited) and adds the concrete excerpts the planner copies from.

---

## File Classification

### Backend — new `app/ai/` package

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `backend/app/ai/tenant_keys.py` | service/utility | request-response (decrypt) | `backend/app/connectors/service.py::get_decrypted_credentials` + `backend/app/encryption.py::decrypt_value` | role-match |
| `backend/app/ai/schemas.py` | model (Pydantic) | request-response (validation gate) | `backend/app/connectors/schemas.py` (`ConnectorTypeInfo`/`ConnectorCreate` style) | role-match |
| `backend/app/ai/prompt_builder.py` | utility/transform | transform (allowlist assembly) | `backend/app/connectors/service.py::_to_response` (field-allowlist object construction) | partial-match (net-new domain, reused discipline) |
| `backend/app/ai/explain.py` (`_run_explain_stream`) | service | streaming | `backend/app/encryption.py::rotate_credentials` (validate-before-commit gate) + `backend/app/main.py::export_resource` (`StreamingResponse`) | partial-match (SSE itself is net-new — see Pitfall 2 in RESEARCH.md) |
| `backend/app/ai/audit.py` (`audit_log_ai_call`) | utility | event-driven (audit write) | `backend/app/encryption.py::rotate_credentials` direct `AuditLog(...)` construction | **exact** |
| `backend/app/ai/cache.py` | utility | CRUD (Redis get/set) | `backend/app/redis_client.py::get_redis` + `backend/app/auth/router.py` OIDC state key convention | role-match |
| `backend/app/ai/budget.py` (`check_tenant_budget`) | service | batch/aggregate query | `backend/app/notifications/alerts.py::_check_sla_breaches` (query → threshold → action shape) | partial-match |

### Backend — new API routes (`app/api/v1/ai/`)

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `backend/app/api/v1/ai/explain_vuln.py` | controller/route | streaming (POST SSE) + request-response (GET cache-check) | `backend/app/connectors/router.py` (RBAC route shape) + `backend/app/main.py::export_resource` (`StreamingResponse`) | role-match |
| `backend/app/api/v1/ai/explain_host.py` | controller/route | streaming | same as above | role-match |
| `backend/app/api/v1/ai/explain_remediation.py` | controller/route | streaming | same as above | role-match |
| `backend/app/api/v1/ai/feedback.py` | controller/route | CRUD (idempotent upsert) | `backend/app/ticketing/router.py::watch_ticket`/`unwatch_ticket` (one row per ticket+user) | **exact mechanism** (needs `on_conflict_do_update`, not `do_nothing` — see below) |

### Backend — modified existing files

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `backend/app/connectors/schemas.py` (`CONNECTOR_TYPES["ANTHROPIC"]`) | config | CRUD | `CONNECTOR_TYPES["OKTA"]` entry (lines 261-275) | **exact** |
| `backend/app/connectors/tester.py` (`test_anthropic` + `TESTERS` entry) | utility | request-response (validation call) | `test_okta()` (lines 424-455) | **exact** |
| `backend/app/connectors/router.py` (`CONNECTOR_CATEGORIES` dict) | config | — | existing dict, lines 33-49 | **exact** |
| `backend/app/main.py` (register `ai` router(s)) | config | — | existing `app.include_router(...)` calls, lines 315-325 | **exact** |
| `backend/alembic/versions/0NN_add_ai_feedback.py` | migration | — | `026_add_ticket_comments.py` (new table + FK + index) | **exact** |
| `backend/alembic/versions/0NN_add_audit_logs_tenant_created_index.py` | migration | — | same file's `op.create_index(...)` call | **exact** |
| `nginx/nginx.conf` (new `location /api/v1/ai/` block, both server blocks) | config | streaming passthrough | existing `location /api/` block (HTTP lines 72-79, HTTPS lines 142-149) | role-match (needs `proxy_buffering off` — net-new concern) |

### Backend — tests

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `backend/tests/test_ai_connector.py` | test | CRUD | `backend/tests/conftest.py` fixtures (`tenant_a`, `admin_user`, `client_factory`) + `backend/app/connectors/service.py` CRUD under test | role-match |
| `backend/tests/test_connectors/test_ai_tester.py` | test | request-response (mocked HTTP) | `backend/tests/test_okta_sync.py` (`httpx.MockTransport`) | **exact** |
| `backend/tests/test_ai_prompt_builder.py` | test | transform (property-style) | none precise in-repo | no analog (see below) |
| `backend/tests/test_ai_schemas.py` | test | validation | none precise in-repo | no analog |
| `backend/tests/test_ai_explain_stream.py` | test | streaming (mocked SSE) | RESEARCH.md's own sketch (`httpx.MockTransport` fed through `AsyncAnthropic(http_client=...)`) | role-match (sketch, not an existing file) |
| `backend/tests/test_ai_cache_isolation.py` | test | cross-tenant integration | `tenant_a`/`tenant_b`/`flushed_redis` fixtures (`conftest.py` lines 216-247, 69) | role-match |
| `backend/tests/test_ai_audit.py` | test | audit-row assertion | `backend/tests/test_encryption_rotation.py::test_audit_event` (lines 258-295) | **exact** |
| `backend/tests/test_ai_budget.py` | test | aggregate/threshold assertion | `backend/app/notifications/alerts.py::_check_sla_breaches` (conceptual sibling; no existing test file targets an identical shape) | partial-match |

### Frontend — new files

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `frontend/src/lib/ai/use-explain-stream.ts` | hook | streaming | `frontend/src/components/connectors/wizard/use-wizard-state.ts` (local `useReducer` state machine — NOT `useQuery`/`useMutation`) | role-match |
| `frontend/src/lib/queries/use-explain-cache.ts` | hook | request-response (cache GET) | `frontend/src/lib/queries/use-vulnerability-detail.ts` | **exact** |
| AI Explanation `<section>` in `frontend/src/components/vulnerabilities/drill-content.tsx` | component | request-response/streaming UI | sibling `<section>` blocks in the same file (Description/Remediation, lines 253-271) | **exact** |
| Citation rendering (inline span + tooltip, likely a new `ai-explanation-citations.tsx`) | component | transform (render validated JSON → styled prose) | `frontend/src/components/ui/Badge.tsx::SourceBadge` (10px tag precedent, lines 52-63) | partial-match (Tooltip primitive itself is net-new) |
| Feedback control (thumbs + note, likely a new `ai-feedback-control.tsx`) | component | CRUD (mutation) | `frontend/src/lib/queries/use-connectors-admin.ts` mutation-hook shape (`useCreateConnector`/`useTestConnector`) | partial-match — optimistic-revert-on-failure detail not directly confirmed (see below) |
| `frontend/src/components/ui/tooltip.tsx` (`npx shadcn add tooltip`) | component | — | none — official-registry scaffold | no analog (by design, per UI-SPEC Registry Safety) |
| `frontend/src/app/(authed)/dashboard/connectors/page.tsx` (extend `CONNECTOR_CATEGORIES`) | config | — | existing dict in same file (lines 51-67) | **exact** |
| `frontend/src/components/connectors/microcopy.ts` (extend `ConnectorCategory` union + `CATEGORY_LABELS`/`CATEGORY_ORDER`/`CATEGORY_EMPTY`) | config | — | existing entries (lines 13-68) | **exact** |

### Frontend — tests

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `frontend/src/lib/ai/use-explain-stream.test.ts` | test | streaming (hook state machine) | `frontend/src/components/connectors/wizard/use-wizard-state.test.ts` | role-match |
| `frontend/src/components/connectors/wizard/add-connector-wizard.test.tsx` (extend with `ANTHROPIC` case) | test | CRUD | existing file itself | **exact** |
| citation / feedback-control component tests | test | render/interaction | `frontend/src/components/vulnerabilities/chip-bar.test.tsx` conventions (RTL) | partial-match |

---

## Pattern Assignments

### `backend/app/ai/tenant_keys.py` (utility, request-response)

**Analog:** `backend/app/connectors/service.py::get_decrypted_credentials` (lines 152-160) + `backend/app/encryption.py` encrypt/decrypt primitives.

**Decrypt pattern** (`backend/app/connectors/service.py:152-160`):
```python
def get_decrypted_credentials(connector: ConnectorConfig) -> dict[str, str]:
    """Decrypt stored credentials for use in sync. Internal use only."""
    if not connector.credentials_secret_arn:
        return {}
    try:
        encrypted_map = json.loads(connector.credentials_secret_arn)
        return {k: decrypt_value(v) for k, v in encrypted_map.items()}
    except Exception:
        return {}
```
`get_tenant_anthropic_key(tenant_id)` should be this exact shape but scoped by `tenant_id` + `connector_type == "ANTHROPIC"`: `select(ConnectorConfig).where(ConnectorConfig.tenant_id == tenant_id, ConnectorConfig.connector_type == "ANTHROPIC")`, then decrypt the `api_key` field the same way. **Never** cache the decrypted key in a module-level variable (BYOK boundary — AI-SPEC Pitfall 3) — decrypt fresh per call, exactly as `get_decrypted_credentials` does (no caching here either).

**Encrypt/decrypt primitives** (`backend/app/encryption.py:24-30`, confirmed present):
```python
def encrypt_value(plaintext: str) -> str: ...
def decrypt_value(ciphertext: str) -> str: ...
```
Reused verbatim — no new crypto code.

---

### `backend/app/ai/schemas.py` (Pydantic model, request-response)

**Analog:** `backend/app/connectors/schemas.py` — the project's Pydantic-model conventions (plain `BaseModel`, no `orm_mode`/aliasing tricks except `class Config: from_attributes = True` on response models that wrap ORM rows — not needed here since `ExplainVulnResponse` wraps the *model's own JSON output*, not a DB row).

AI-SPEC §4b already fully specifies the target shape (`CitationSource` enum, `Citation`, `ExplainVulnResponse`) — this is locked, not something to re-derive from the codebase. The only codebase-grounded addition: name the per-view variants consistently with existing naming (`ConnectorConfigResponse`/`ConnectorTestResponse` — suffix `Response`), e.g. `ExplainVulnResponse`, `ExplainHostResponse`, `ExplainRemediationResponse`, sharing a common base per D-16 ("each aggregate view gets its own grounding shape + schema variant").

**Existing project convention for shared/varying schemas** (`backend/app/connectors/schemas.py:19-28`):
```python
class ConnectorTypeInfo(BaseModel):
    id: str
    name: str
    description: str
    fields: list[dict[str, Any]]
    permissions: list[ConnectorPermission] = []
    setup_url: str = ""
    base_urls: dict[str, str] = {}
    notes: str = ""
```
Same discipline for `ExplainResponseBase` → subclassed per view.

---

### `backend/app/ai/prompt_builder.py` (utility/transform, transform)

**Analog:** `backend/app/connectors/service.py::_to_response` (lines 47-64) — the codebase's one clean precedent for "map a full ORM row onto a narrow, explicitly-named allowlist object, deliberately dropping sensitive/internal fields":
```python
def _to_response(c: ConnectorConfig) -> ConnectorConfigResponse:
    """Convert DB model to response schema."""
    return ConnectorConfigResponse(
        id=str(c.id),
        connector_type=c.connector_type,
        connector_name=_get_connector_name(c.connector_type),
        is_enabled=c.is_enabled,
        config=c.config or {},
        has_credentials=bool(c.credentials_secret_arn),   # boolean flag, never the arn itself
        ...
    )
```
Note `credentials_secret_arn` (the encrypted blob) never appears in the response — only `has_credentials: bool`. This is the exact discipline `prompt_builder.py` needs applied to `AssetDetail` for the per-host view: never pass the raw dict/row through, not even partially — construct a new, explicitly-named object field-by-field.

**Confirmed PII fields to exclude** (`frontend/src/lib/queries/use-asset-detail.ts:10-52`, the wire contract the backend's `AssetDetail`-shaped endpoint actually returns):
```typescript
export type DirectoryUser = {
  email: string; display_name: string | null; department: string | null;
  job_title: string | null; avatar_url: string | null; groups: string[];
  idp_source: string | null; is_active: boolean; role: string | null;
};

export type AssetDetail = {
  id: string; hostname: string | null; os_name: string | null; os_version: string | null;
  device_category: string | null; risk_score: number | null;
  seen_by_sources: string[] | Record<string, unknown>;
  assigned_user: string | null;               // ← PII-adjacent, EXCLUDE
  tags: string[] | null; sla_breach: number;
  vuln_counts: { total: number; critical: number; high: number; medium: number;
                 low: number; exploitable: number; kev: number; sla_breach: number };
  directory_user: DirectoryUser | null;        // ← PII, EXCLUDE entirely
  ip_addresses: string[] | null; mac_addresses: string[] | null;
  serial_number: string | null;                // ← EXCLUDE (low grounding value)
  model: string | null;
  managed_by: string | null;                   // ← likely a person/team, EXCLUDE unless confirmed non-PII
  last_checkin_at: string | null;
  building: string | null;                     // ← physical location, EXCLUDE
  department: string | null;
};
```
Safe-to-allowlist subset for the per-host prompt: `hostname, os_name, os_version, device_category, risk_score, vuln_counts, tags, sla_breach, last_checkin_at`.

**Per-vuln allowlist** (`frontend/src/lib/queries/use-vulnerability-detail.ts:12-31`, no PII present, safe in full):
```typescript
export type VulnerabilityDetail = {
  id: string; cve_id: string | null; vulnerability_name: string | null;
  cvss_v3_score: number | null; cvss_v3_vector: string | null;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';
  cisa_kev: boolean; exploit_available: boolean;
  asset_id: string | null;              // keep OUT of prompt text — internal id, not grounding content
  asset_hostname: string | null; source: string;
  affected_product: string | null; affected_version: string | null; fixed_version: string | null;
  remediation_info: string | null; status: string;
  first_detected_at: string; last_seen_at: string;
};
```

The untrusted-content-as-data wrapping itself (`<scanner_data>` tagged JSON block, system/user separation) is already fully locked by AI-SPEC §4b — do not re-derive, just apply this field-selection discipline when constructing the object passed into it.

---

### `backend/app/ai/explain.py` (service, streaming — the core "buffer-then-validate-then-replay")

**Two analogs, for two different halves of this file's job:**

**1. Validate-everything-before-any-write-commits discipline** — `backend/app/encryption.py::rotate_credentials` (lines 126-294). This is the strongest existing precedent in the codebase for "do all the risky work in memory, validate completely, and only then commit/emit — abort-all on any failure":
```python
# PRE-FLIGHT: decrypt every field with old key, collect failures
...
if preflight_failures:
    await db.rollback()
    raise RotationPreflightError(preflight_failures, phase="preflight")
...
# POST-VERIFY (D-04): decrypt every re-encrypted field with new_key before commit.
...
if post_failures:
    await db.rollback()
    raise RotationPreflightError(post_failures, phase="post_verify")
...
# COMMIT once (D-01/D-03: single transaction)
await db.commit()
```
`explain.py`'s shape is the same skeleton: consume the whole Anthropic stream into memory (`await stream.get_final_message()`) → validate (`ExplainVulnResponse.model_validate_json`) → **only then** emit anything to the SSE generator, mirroring "abort-all, nothing partial escapes, one clean commit point."

**2. The `StreamingResponse` mechanics themselves** — `backend/app/main.py::export_resource` (lines 460-493) is the **only** existing `StreamingResponse` usage in this backend:
```python
return StreamingResponse(
    iter([bytes(pdf_bytes)]),
    media_type="application/pdf",
    headers={"Content-Disposition": f"attachment; filename=getvul_executive_summary_{now}.pdf"},
)
```
**Critical divergence, not a copy-paste target:** every existing call wraps `iter([single_blob])` — a **one-shot, already-fully-buffered** body, not a generator that yields multiple chunks over real wall-clock time. RESEARCH.md's Pitfall 2 flags this exactly: true incremental SSE (`StreamingResponse(some_async_generator())`, `media_type="text/event-stream"`, headers `{"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}`) is **genuinely new** to this backend. Treat the multi-yield generator mechanics as unproven — spike-test it before building the full buffer-then-validate-then-replay logic on top (per RESEARCH.md's own recommendation).

---

### `backend/app/ai/audit.py` (`audit_log_ai_call`) — **exact analog**

**Analog:** `backend/app/encryption.py::rotate_credentials` direct `AuditLog` construction (lines 256-276):
```python
if audit and rotated_count > 0:
    log = AuditLog(
        tenant_id=connectors[0].tenant_id,
        user_id=None,
        user_email="system:cli",
        action="encryption.key_rotated",
        resource_type="encryption_key",
        resource_id=None,
        details={"row_count": rotated_count, "tenant_count": tenant_count, "dry_run": False},
        ip_address=None,
        created_at=datetime.now(UTC),
    )
    db.add(log)
```
`audit_log_ai_call()` must copy this shape exactly — direct `AuditLog(...)` construction with an **explicit, required** `tenant_id` parameter (never derived from a nullable user) and `user_email` as a plain string (analyst's email OR `"system:scheduler"` for future Phase-26 calls). **Do not** call the shared `audit()` helper — its nil-tenant fallback is the trap (see Shared Patterns below).

**`AuditLog` model** (`backend/app/audit.py:36-50`) — the exact columns available:
```python
class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()")
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    user_email: Mapped[str | None] = mapped_column(String(320))
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(200))
    details: Mapped[dict | None] = mapped_column(JSONB)
    ip_address: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```
`details` is unstructured JSONB — `{"model": ..., "input_tokens": ..., "output_tokens": ..., "cost_estimate_usd": ..., "status": ...}` fits with no migration. `action` should follow the existing dot-namespaced convention documented at the top of `audit.py` (`connector.create`, `ticket.create`, etc.) → `ai.explain.{resource_type}` per RESEARCH.md.

**Test analog** — `backend/tests/test_encryption_rotation.py::test_audit_event` (lines 258-295) is the exact test shape to model `test_ai_audit.py` on:
```python
async def test_audit_event(db_session, tenant_a):
    ...
    await rotate_credentials(key_a, key_b, audit=True)
    async with async_session_factory() as fresh:
        audit_rows = (await fresh.execute(select(AuditLog).where(AuditLog.action == "encryption.key_rotated"))).scalars().all()
        assert len(audit_rows) >= 1
        row = audit_rows[0]
        assert row.user_email == "system:cli"
        assert row.details is not None
```
For `test_ai_audit.py`, assert `row.user_email == "system:scheduler"` for a directly-invoked scheduler-shaped call and `row.user_email == user.email` for an interactive one — same query-by-`action`-then-assert-row-shape structure.

---

### `backend/app/ai/cache.py` (utility, CRUD via Redis)

**Analog:** `backend/app/redis_client.py` (full file, 14 lines) — the dependency to reuse, not reimplement:
```python
def get_redis(request: Request) -> redis.Redis:
    return request.app.state.redis
```
**Key-convention analog** — the OIDC CSRF-state nonce (`backend/app/auth/router.py:47,70`), the only existing Redis read/write in the codebase and thus the project's one precedent for key shape:
```python
ok = await redis_client.set(f"oidc:state:{state}", provider, ex=600, nx=True)
...
stored_provider = await redis_client.getdel(f"oidc:state:{state}")
```
Colon-delimited, category-prefixed. `cache.py`'s key should extend this convention: `ai:explain:{tenant_id}:{resource_type}:{resource_id}:{record_hash}:{model}:{prompt_version}` (RESEARCH.md Pattern 4) with a TTL via the same `ex=` kwarg shown above (D-19, ~30 days). Access **only** through `get_redis(request)` — never construct a second Redis client in `cache.py`.

---

### `backend/app/ai/budget.py` (`check_tenant_budget`) — service, aggregate query

**Analog:** `backend/app/notifications/alerts.py::_check_sla_breaches` (lines 100-143) — the closest existing "query aggregated tenant state → compare against a threshold → conditionally act" shape:
```python
async def _check_sla_breaches(db: AsyncSession, tenant: Tenant) -> int:
    now = datetime.now(UTC)
    sla_window = now + timedelta(hours=24)
    vulns = (await db.execute(
        select(Vulnerability, Asset).outerjoin(Asset, Vulnerability.asset_id == Asset.id).where(
            Vulnerability.tenant_id == tenant.id,
            Vulnerability.sla_due_at.isnot(None),
            Vulnerability.sla_due_at <= sla_window,
            ...
        )
    )).all()
    for vuln, asset in vulns:
        ...
        await create_notification(db, tenant_id=tenant.id, title=..., severity="high", category="sla_breach", ...)
```
RESEARCH.md already supplies the concrete `check_tenant_budget` implementation (query `SUM` over `AuditLog.details["cost_estimate_usd"]`, filtered by `tenant_id` + `action.like("ai.%")` + `created_at >= month_start`, compared against `config.monthly_budget_usd`) — treat that as locked; the `_check_sla_breaches` analog above is for the surrounding "query → decide → act (notify)" control flow shape, not the SQL itself. On breach, call `create_notification(..., send_email_flag=True)` exactly as `_check_sla_breaches` does (see Shared Patterns).

---

### `backend/app/api/v1/ai/explain_vuln.py` / `explain_host.py` / `explain_remediation.py` (controllers)

**Analog:** `backend/app/connectors/router.py` — the RBAC-gated route shape used by every existing router in this codebase:
```python
from app.auth.rbac import require_admin
from app.auth.schemas import CurrentUser
from app.dependencies import DBSession

@router.post("", response_model=ConnectorConfigResponse, status_code=201)
async def create_new_connector(
    body: ConnectorCreate,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_admin)],
):
    return await create_connector(db, user.tenant_id, body)
```
**AI-SPEC's illustrative `tenant=Depends(current_tenant)` does not exist in this codebase** (confirmed: no `current_tenant` symbol anywhere under `app/auth/`). The real, universally-used pattern is exactly the block above, substituting `require_analyst`/`require_viewer` (RESEARCH.md Pattern 2, D-17):
```python
from app.auth.rbac import require_analyst, require_viewer

@router.post("/explain-vuln/{finding_id}")
async def explain_vuln(finding_id: str, db: DBSession, user: Annotated[CurrentUser, Depends(require_analyst)]):
    # user.tenant_id, user.email, user.id, user.role all directly available.
    ...

@router.get("/explain-vuln/{finding_id}")
async def get_cached_explanation(finding_id: str, db: DBSession, user: Annotated[CurrentUser, Depends(require_viewer)]):
    ...
```
`require_analyst`/`require_viewer` (`backend/app/auth/rbac.py:49-53`) already implement the exact Owner(40) > Admin(30) > Analyst(20) > Viewer(10) hierarchy D-17 needs — zero new RBAC code:
```python
require_viewer = RequireRole(UserRole.VIEWER.value)
require_analyst = RequireRole(UserRole.ANALYST.value)
require_admin = RequireRole(UserRole.ADMIN.value)
require_owner = RequireRole(UserRole.OWNER.value)
```
`CurrentUser` (`backend/app/auth/schemas.py:10-17`): `{id, tenant_id, email, role, must_change_password}`. **Note:** a second, unused `require_role()` factory + a *different* numeric hierarchy (4/3/2/1) also exists in `backend/app/auth/dependencies.py:119-141` — do not use it; `app/auth/rbac.py`'s `RequireRole`/`ROLE_HIERARCHY` (40/30/20/10) is the one actually wired into every router including `connectors/router.py`.

**`StreamingResponse` header convention** (`backend/app/main.py:489-493`, adapted for SSE per AI-SPEC §3):
```python
return StreamingResponse(
    explain_vuln_stream(user.tenant_id, record),
    media_type="text/event-stream",
    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
)
```

---

### `backend/app/api/v1/ai/feedback.py` (controller, CRUD upsert)

**Analog — exact mechanism, one required change:** `backend/app/ticketing/router.py::watch_ticket`/`unwatch_ticket` (lines 681-734), the codebase's only existing "idempotent one-row-per-(parent, user)" endpoint pair:
```python
@router.post("/{ticket_id}/watch")
async def watch_ticket(ticket_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(require_analyst)):
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    row, _url = await _resolve_group(db, ticket_id, user.tenant_id)
    stmt = (
        pg_insert(TicketWatcher)
        .values(ticket_id=row.id, user_id=user.id)
        .on_conflict_do_nothing(index_elements=["ticket_id", "user_id"])
    )
    await db.execute(stmt)
    await audit(db, user, "ticket.watch", "ticket", str(ticket_id), {})
    await db.commit()
    return {"watching": True}
```
**Required divergence:** D-22 needs feedback **editable** ("an analyst can change their own verdict"), so the feedback endpoint must use `.on_conflict_do_update(index_elements=["finding_id", "user_id"], set_={"verdict": ..., "note": ..., "updated_at": ...})` instead of `.on_conflict_do_nothing(...)` — same `pg_insert` mechanism, different conflict clause. `TicketWatcher`'s composite-PK model shape (`backend/app/ticketing/models.py:139-156`) is the schema analog for the new `ai_feedback` table's own composite-uniqueness need (`UniqueConstraint` or composite PK on `(finding_id, user_id)`, per D-22).

**Gating note (Assumption A4, RESEARCH.md):** the watch/unwatch analog gates at `require_analyst`. D-17 only explicitly gates the *paid Explain trigger*, not feedback capture (free, non-billed) — confirm at plan time whether feedback should gate at `require_viewer` (any authenticated role) or mirror `require_analyst` for consistency with this analog.

---

### `backend/app/connectors/schemas.py` — add `CONNECTOR_TYPES["ANTHROPIC"]` — exact analog

**Analog:** `CONNECTOR_TYPES["OKTA"]` (lines 261-275) — simplest existing entry (2 credential fields, no `base_urls` select):
```python
"OKTA": ConnectorTypeInfo(
    id="OKTA",
    name="Okta",
    description="Identity provider — SSO authentication and user/group directory sync via SCIM",
    fields=[
        {"name": "domain", "label": "Okta Domain", "type": "text", "required": True},
        {"name": "api_token", "label": "API Token", "type": "password", "required": True},
    ],
    permissions=[
        ConnectorPermission(scope="okta.users.read", access="Read", purpose="List all users in the directory"),
    ],
    setup_url="https://developer.okta.com/docs/guides/create-an-api-token/main/",
    notes="Create an API token in Okta Admin → Security → API → Tokens...",
),
```
The `"ANTHROPIC"` entry needs `fields=[{"name": "api_key", "label": "Anthropic API Key", "type": "password", "required": True}, {"name": "model", "label": "Model", "type": "select", "required": True}]` — the `"select"` field type already has a live precedent in `CROWDSTRIKE`'s `base_url` field (lines 38, 51-56), whose `base_urls` dict is converted into the frontend's `defaults` map by `get_connector_types()` (`backend/app/connectors/router.py:60-69`):
```python
for f in v.fields if isinstance(v.fields, list) else []:
    if isinstance(f, dict):
        name = f.get("name", "")
        if f.get("type") == "select" and isinstance(v.base_urls, dict) and v.base_urls:
            defaults[name] = list(v.base_urls.values())[0]
```
D-05's per-option guidance copy ("Sonnet 5 — recommended balance", etc.) is presentation-layer (UI-SPEC Copywriting Contract) — it doesn't need a new backend field shape, just a `model` select field whose options the frontend renders with the guidance strings inline (not sourced from `base_urls`, which is a URL map — the model dropdown's option labels are a frontend-only concern per UI-SPEC).

**`ConnectorCreate`/`ConnectorUpdate` request shapes already generic** (lines 346-357) — no change needed, `config: dict[str, Any] = {}` already accepts `{"model": "claude-sonnet-5", "monthly_budget_usd": 50}` with zero schema change.

---

### `backend/app/connectors/tester.py` — add `test_anthropic()` — exact analog

**Analog:** `test_okta()` (lines 424-455) — simplest existing tester (single bearer-style token, one cheap read-only call, no OAuth dance):
```python
async def test_okta(credentials: dict, config: dict) -> ConnectorTestResult:
    domain = config.get("domain", credentials.get("domain", "")).strip().rstrip("/")
    token = credentials.get("api_token", "")
    if not domain or not token:
        return ConnectorTestResult(success=False, message="Okta domain and API token are required")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{domain}/api/v1/users?limit=1", headers={"Authorization": f"SSWS {token}", ...})
        if resp.status_code == 200:
            return ConnectorTestResult(success=True, message="Connected to Okta", details={...})
        return ConnectorTestResult(success=False, message=f"Auth failed: HTTP {resp.status_code}")
    except Exception as e:
        return ConnectorTestResult(success=False, message=f"Connection error: {e}")
```
RESEARCH.md Pattern 3 already supplies the concrete `test_anthropic()` (using `AsyncAnthropic(...).messages.count_tokens(...)` instead of a raw `httpx` call, since the free-validation mechanism here is the Anthropic SDK, not a bearer-header GET) — same `if not X: return ConnectorTestResult(success=False, ...)` / `try/except Exception` shape as every other tester. Register in `TESTERS` dict (lines 496-512) the same way every other entry is:
```python
TESTERS = {
    "CROWDSTRIKE": test_crowdstrike,
    ...
    "INTUNE": test_intune,
    "ANTHROPIC": test_anthropic,   # new
}
```
`test_connector()` dispatcher (lines 515-519) needs **no change** — it's already generic over `TESTERS.get(connector_type)`.

---

### `backend/alembic/versions/0NN_add_ai_feedback.py` — exact analog

**Analog:** `backend/alembic/versions/026_add_ticket_comments.py` (full file) — the most recent "add one new child table with an FK + composite index" migration:
```python
revision = "026_add_ticket_comments"
down_revision = "025_add_asset_tags"

def upgrade() -> None:
    op.create_table(
        "ticket_comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ticket_comments_ticket_created", "ticket_comments", ["ticket_id", "created_at"])

def downgrade() -> None:
    op.drop_index("ix_ticket_comments_ticket_created", table_name="ticket_comments")
    op.drop_table("ticket_comments")
```
`ai_feedback` needs the same skeleton: `id` (UUID PK), `tenant_id` (FK → tenants, CASCADE, per Shared Patterns' tenant-scoping requirement — `ticket_comments` omits `tenant_id` because it's reachable via `ticket_id`, but AI-05/cross-tenant isolation discipline argues for an explicit `tenant_id` column here rather than relying on a join), `finding_id`/`resource_type`/`resource_id` (per D-15's 3-view widening), `user_id` (FK → users, CASCADE), `verdict` (thumbs up/down), `note` (nullable Text, capped 500 chars per UI-SPEC), `created_at`/`updated_at`. Per D-22 add a `UniqueConstraint`/composite index on `(resource_type, resource_id, user_id)` for the one-row-per-user upsert target (mirroring `TicketWatcher`'s `PrimaryKeyConstraint("ticket_id", "user_id")` in `backend/app/ticketing/models.py:146-147`).

**Current migration HEAD** (verified): `revision = "030_add_connector_health_columns"`, so the new migration's `down_revision` should chain from `"030_add_connector_health_columns"` (or whatever is HEAD at execution time if other phases land migrations first — confirm before writing).

**Composite index for budget queries** — same file's `op.create_index(...)` call is also the template for the separate `CREATE INDEX ix_audit_logs_tenant_created ON audit_logs (tenant_id, created_at)` migration RESEARCH.md's `check_tenant_budget()` needs for query performance.

---

### `nginx/nginx.conf` — new `location /api/v1/ai/` block

**Analog:** the existing `location /api/` block, present verbatim in both the HTTP server (lines 72-79) and HTTPS server (lines 142-149):
```nginx
location /api/ {
    limit_req zone=api burst=50 nodelay;
    proxy_pass http://backend/api/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;   # literal "https" in the HTTPS block
}
```
The new AI location must add to this base: `proxy_http_version 1.1;`, `proxy_buffering off;`, `proxy_cache off;`, `chunked_transfer_encoding on;`, `proxy_read_timeout 90s;` (default 60s risks killing a slow buffer-then-validate call mid-stream) — per RESEARCH.md Pattern 7. nginx's longest-prefix matching means a more specific `/api/v1/ai/` block correctly takes precedence over the existing `/api/` block regardless of declaration order, but place it adjacent to the existing block in **both** server blocks for readability. `docker-compose.yml` mounts this file read-only — an nginx container **restart** (not rebuild) picks up the change.

---

### `frontend/src/lib/ai/use-explain-stream.ts` (hook, streaming) — the one genuinely novel frontend file

**Analog:** `frontend/src/components/connectors/wizard/use-wizard-state.ts` (full file) — the codebase's only existing hook shaped as a **local state machine** (`useReducer`, not `useQuery`/`useMutation`), which is exactly the shape a long-lived multi-event SSE stream needs:
```typescript
export type WizardStep = 'credentials' | 'test' | 'confirm';
export interface WizardState {
  step: WizardStep;
  values: Record<string, string>;
  testResult: { success: boolean; message: string } | null;
  ...
}
type Action =
  | { type: 'UPDATE_FIELD'; name: string; value: string }
  | { type: 'SET_TEST_RESULT'; result: { success: boolean; message: string } }
  | { type: 'ADVANCE' } | { type: 'BACK' };

export function useWizardState(fields: string[]) {
  const [state, dispatch] = useReducer((s: WizardState, a: Action) => reducer(s, a, fields), undefined, initialState);
  ...
  return { state, canAdvance, updateField, setTestResult, advance, back, buildCredentials };
}
```
`useExplainStream` should follow the same "one hook, one concern, typed discriminated-union state" convention:
```typescript
type ExplainStreamState =
  | { phase: 'idle' }
  | { phase: 'analyzing' }
  | { phase: 'done'; data: ExplainVulnResponse }
  | { phase: 'error'; kind: 'busy' | 'grounded_false' | 'budget_exceeded' | 'unknown' };
```
(RESEARCH.md Pattern 6 already sketches the full implementation — `fetch()` + `res.body.getReader()` + manual SSE frame parsing on `\n\n` boundaries — treat that sketch as the locked shape; the pattern-mapping contribution here is that `use-wizard-state.ts` is the concrete **existing codebase convention** this new hook's shape should match, not `useQuery`/`useMutation`.)

**What NOT to reuse** — `frontend/src/lib/api.ts::api()` (full file). Confirmed at line 133: `return res.json();` — unconditional. Every other hook in this codebase (`use-vulnerability-detail.ts`, `use-connectors-admin.ts`, etc.) calls `api<T>(path, opts)` and gets back a fully-parsed JSON object; reflexively reusing it for the streaming endpoint will hang until the stream closes, then throw a JSON-parse error on the first SSE frame (RESEARCH.md Pitfall 3). `use-explain-stream.ts` must call `fetch()` directly, reading the `Authorization: Bearer` header the same way `api.ts` does (`localStorage.getItem('getvul_token')`, lines 33-38) but bypassing `api()`'s `.json()` call entirely.

---

### `frontend/src/lib/queries/use-explain-cache.ts` (hook, request-response) — exact analog

**Analog:** `frontend/src/lib/queries/use-vulnerability-detail.ts` (full file) — the simplest existing single-GET `useQuery` hook in the codebase:
```typescript
export function useVulnerabilityDetail(idOrCve: string | null) {
  return useQuery({
    queryKey: queryKeys.vulnerabilities.detail(idOrCve ?? ''),
    queryFn: ({ signal }) =>
      api<VulnerabilityDetail>(`/api/v1/vulnerabilities/${encodeURIComponent(idOrCve!)}`, { signal }),
    enabled: idOrCve !== null && idOrCve !== '',
    staleTime: 60_000,
    retry: 1,
  });
}
```
`useExplainCache(resourceType, resourceId)` is a direct structural copy — same `enabled`/`staleTime`/`retry` conventions, same `api<T>()` usage (this one genuinely is a fast, non-streaming GET, so `api()` is correct here, unlike the streaming hook above). Add a new `queryKeys.ai.explain(resourceType, resourceId)` entry to `frontend/src/lib/queries/keys.ts` following the existing domain-first nesting convention (e.g. `assets: { byId: (id) => ['assets', 'detail', id] as const, ... }`, `keys.ts:37-49`).

---

### AI Explanation `<section>` in `frontend/src/components/vulnerabilities/drill-content.tsx` — exact analog (self-referential)

**Analog:** the file's own sibling `<section>` blocks (Description, lines 253-261; Remediation, lines 263-271) — the new section must be visually and structurally identical in chrome, per UI-SPEC ("no new heading style"):
```tsx
<section aria-labelledby="drill-desc-h">
  <h4
    id="drill-desc-h"
    className="mb-2 text-xs uppercase tracking-wide text-text-muted"
  >
    {microcopy.drill.sections.description}
  </h4>
  <p className="text-sm text-text">{description}</p>
</section>
```
Per UI-SPEC's Section Placement (D-11), insert a new `<section aria-labelledby="drill-ai-h">` between the Description section (ends line 261) and the Remediation section (starts line 263), using the identical `text-xs uppercase tracking-wide text-text-muted` `<h4>` treatment. The section lives inside the existing `overflow-y-auto` container (`panelInteractivesRef`, line 226-229) — no independent scroll region needed.

**Confirmed: this is the only file to touch for both desktop and mobile.** `frontend/src/components/vulnerabilities/drill-panel-mobile.tsx` renders `<DrillContent .../>` directly inside its `vaul` `Drawer` (confirmed via import + usage at line 99) — it does not duplicate section markup. Adding the AI Explanation section to `drill-content.tsx` alone satisfies D-15's "all three drill views" for the vuln view on both desktop and mobile with one edit.

**Existing loading/error state precedent in the same file** (lines 114-127), for degraded-state consistency:
```tsx
if (q.isPending) {
  return (<div ref={ref} aria-busy="true" className="p-6 text-text-muted">Loading…</div>);
}
if (q.isError || !q.data) {
  return (<div ref={ref} role="alert" className="p-6 text-danger">Couldn't load this vulnerability.</div>);
}
```
The new section's own internal states (no-key / analyzing / grounded=false / busy / budget-exceeded, per UI-SPEC "Section body states") are section-local, not panel-level like this — but the `role="alert"`/`aria-busy` accessibility conventions shown here should carry into the section's own state markup.

---

### Citation rendering (new component, e.g. `ai-explanation-citations.tsx`)

**Analog for the 10px inline tag precedent:** `frontend/src/components/ui/Badge.tsx::SourceBadge` (lines 52-63) — the codebase's existing "small, tinted, 10px, uppercase-ish inline tag" pattern UI-SPEC explicitly cites as the precedent for the `ai_interpreted` superscript tag:
```tsx
export function SourceBadge({ source }: { source: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-1.5 py-0.5 text-[10px] font-medium",
        sourceStyles[source] || "bg-gray-700 text-gray-300 border-gray-600"
      )}
    >
      {source === "CROWDSTRIKE" ? "CS" : source === "DEFENDER" ? "MDE" : source}
    </span>
  );
}
```
UI-SPEC's own citation contract already locks the exact classes to use (`rounded-[3px] bg-violet-soft px-1 -mx-0.5 text-[var(--color-violet-on-soft)]` for `scanner_verbatim`; `<sup class="ml-0.5 text-[10px] font-medium uppercase tracking-wide text-text-faint">AI</sup>` for `ai_interpreted`) — `SourceBadge` is cited here only as the pre-existing "10px tag" precedent that justifies reusing that scale rather than inventing a new one (UI-SPEC Typography section explicitly says this 10px size is "reused (not newly declared)... matching the existing SourceBadge/kev-badge 10px precedent").

**Net-new primitive:** the shadcn `Tooltip` component does not exist in this codebase yet (`frontend/src/components/ui/` listing confirmed — no `tooltip.tsx`). UI-SPEC's Registry Safety table already specifies `npx shadcn add tooltip` (official registry, no safety gate needed) — this is a scaffold command, not a hand-written pattern to copy from an existing file.

---

### Feedback control (new component, e.g. `ai-feedback-control.tsx`)

**Partial analog only** — `frontend/src/lib/queries/use-connectors-admin.ts`'s mutation-hook shape (`useCreateConnector`, lines 132-151) gives the base `useMutation` + toast convention:
```typescript
export function useCreateConnector() {
  const qc = useQueryClient();
  const { toast } = useToast();
  return useMutation({
    mutationFn: (body: CreateConnectorBody) => api<ConnectorConfigResponse>('/api/v1/connectors', { method: 'POST', body: JSON.stringify(body), headers: {...} }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.connectors.all }); toast(...); },
    onError: (err: Error) => { toast({ variant: 'error', message: err.message || '...' }); },
  });
}
```
**Gap — not directly confirmed this pass:** UI-SPEC's own coverage table says feedback submission failure should "silently revert" the thumb state optimistically, with **no** blocking error toast (low-stakes signal). The `useCreateConnector` analog above always toasts on error — that's the wrong error-handling shape for feedback. `frontend/src/lib/queries/use-mark-blocked.ts` or `use-snooze` mutations were not read this pass but are named in project conventions as sites with optimistic-update-with-revert-on-failure; confirm the exact revert mechanism (`onMutate`/`onError` optimistic cache patch, TanStack Query's standard pattern) against one of those two files at plan time rather than inventing a new revert mechanism from scratch.

---

### `frontend/src/app/(authed)/dashboard/connectors/page.tsx` + `frontend/src/components/connectors/microcopy.ts`

**Analog:** both files' own existing `CONNECTOR_CATEGORIES`/`ConnectorCategory` definitions. `microcopy.ts:13-32`:
```typescript
export type ConnectorCategory = 'vulnerability_scanner' | 'ticketing' | 'identity_provider' | 'enrichment';

export const CATEGORY_LABELS: Record<ConnectorCategory, string> = {
  vulnerability_scanner: 'Vulnerability scanners',
  identity_provider: 'Identity',
  enrichment: 'MDM & enrichment',
  ticketing: 'Ticketing',
};

export const CATEGORY_ORDER: ConnectorCategory[] = ['vulnerability_scanner', 'identity_provider', 'enrichment', 'ticketing'];
```
`page.tsx:51-67` mirrors the backend's `CONNECTOR_CATEGORIES` dict (`backend/app/connectors/router.py:33-49`) 1:1, mapping each connector-type string to a category key. Adding the AI connector requires **three files kept in lockstep**: (1) backend `CONNECTOR_CATEGORIES["ANTHROPIC"] = "<category>"`, (2) frontend `page.tsx`'s duplicate dict, (3) `microcopy.ts`'s `ConnectorCategory` union + `CATEGORY_LABELS`/`CATEGORY_ORDER`/`CATEGORY_EMPTY`. **The category name/key itself (e.g. a new `"ai_assistant"` category vs. folding into an existing one) is a plan-time decision, not resolved by this pattern map** — CONTEXT.md/UI-SPEC do not specify it; flag for the planner.

`CATEGORY_EMPTY` (`microcopy.ts:43-68`) also needs a new entry per the copy-voice rules already established (heading + body + cta + suggestion, sentence case, no "Are you sure?").

---

## Shared Patterns

### RBAC gating
**Source:** `backend/app/auth/rbac.py` (full file) — `require_viewer`/`require_analyst`/`require_admin`/`require_owner`.
**Apply to:** every new `app/api/v1/ai/*` route. Explain-trigger POST routes → `require_analyst` (D-17); cache-check GET routes → `require_viewer` (Viewers may read cached, never trigger); AI connector CRUD (reusing `connectors/router.py` verbatim) already gates at `require_admin` — no change needed there.
```python
require_viewer = RequireRole(UserRole.VIEWER.value)
require_analyst = RequireRole(UserRole.ANALYST.value)
```

### Audit logging — what to avoid
**Source:** `backend/app/audit.py::audit()` (lines 129-200), specifically the nil-tenant fallback at line 160:
```python
log = AuditLog(
    tenant_id=user.tenant_id if user else uuid.UUID(int=0),   # ← the trap
    ...
)
```
**Apply to:** every AI call site. **Never** call this shared `audit()` helper for AI audit rows — it silently stamps the nil UUID as tenant when `user=None`, exactly the failure mode AI-06 warns against for scheduler-originated calls. Use the dedicated `audit_log_ai_call()` (see Pattern Assignments above) which takes `tenant_id` as a required, explicit parameter instead.

### Redis access
**Source:** `backend/app/redis_client.py::get_redis` (full file).
**Apply to:** `app/ai/cache.py` and any future AI in-flight concurrency guard (D-25's per-tenant lock). Always inject via `Depends(get_redis)` / call `get_redis(request)` — never construct a second `redis.Redis(...)` client.

### Admin notification on breach
**Source:** `backend/app/notifications/service.py::create_notification` (lines 19-61) + its concrete call site in `backend/app/notifications/alerts.py::_check_sla_breaches` (lines 130-140):
```python
await create_notification(
    db,
    tenant_id=tenant.id,
    title=f"SLA Breach Warning: {resource_id}",
    message=f"{resource_id} on {hostname} — SLA due in {hours_remaining}h",
    severity="high",
    category="sla_breach",
    resource_type="vulnerability",
    resource_id=resource_id,
    details={...},
)
```
**Apply to:** D-08's budget-breach admin alert. Same call shape, `category="ai_budget_exceeded"` (or similar), `send_email_flag=True` to also fire the existing SMTP path (`create_notification`'s `_send_notification_email`, lines 162-189, already checks the tenant's `smtp_config` before sending — no new email code needed).

### DBSession / CurrentUser dependency shape
**Source:** `backend/app/dependencies.py` (full file, 13 lines):
```python
DBSession = Annotated[AsyncSession, Depends(get_db)]
AuthenticatedUser = Annotated[CurrentUser, Depends(get_current_user)]
```
**Apply to:** every new router file — `db: DBSession` as a parameter type, never a raw `Depends(get_db)` inline (matches `connectors/router.py`'s own usage).

### HTTP mocking for external-API tests
**Source:** `backend/tests/test_okta_sync.py` (full file) — `httpx.MockTransport` pattern used project-wide for connector tests:
```python
def handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=[...], headers={...})
client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
```
**Apply to:** `test_connectors/test_ai_tester.py` (mock the Anthropic REST calls `count_tokens` makes) and `test_ai_explain_stream.py` (mock the full Messages-API SSE wire format via `AsyncAnthropic(api_key="test-key", http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))` — the SDK is httpx-based and accepts an `http_client` override; RESEARCH.md's Code Examples section already has the full SSE-body fixture for this). No new test dependency (`respx`, `pytest-httpx`) needed.

### Test fixtures already available, no new plumbing needed
**Source:** `backend/tests/conftest.py` (lines 216-365) — `tenant_a`/`tenant_b` (isolated tenant fixtures), `analyst_user`/`viewer_user`/`admin_user` (role-scoped users in `tenant_a`), `analyst_user_b` (cross-tenant identity), `flushed_redis` (real Redis, flushed between tests), `client`/`client_factory` (pre-authed `AsyncClient` fixtures). Every AI-01..AI-06 test can reuse these directly — confirmed no new fixture plumbing is required for RBAC, cross-tenant, or Redis-integration tests.

---

## No Analog Found

Files/patterns with no close match in the codebase (planner should lean on AI-SPEC/RESEARCH.md's own locked design instead):

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `backend/tests/test_ai_prompt_builder.py` | test | transform (property-style) | No existing property-style test asserts "every field in an output object traces back to an allowlist" — this is a net-new test shape. AI-SPEC §5/D1-D11 already define exactly what to assert; write from that spec, not from an in-repo template. |
| `backend/tests/test_ai_schemas.py` | test | validation | No existing test suite targets pure Pydantic schema-validation-gate behavior (malformed/missing-citation/bad-enum JSON) in isolation — closest sibling tests validate request bodies, not model *output*. Straightforward `pytest.raises(ValidationError)` style, no special convention to inherit. |
| `backend/app/ai/explain.py`'s true multi-yield SSE generator | service | streaming | Confirmed: every existing `StreamingResponse` call in `backend/app/main.py` wraps a pre-built, one-shot `iter([bytes])` body. No generator-based, wall-clock-incremental `StreamingResponse` exists anywhere in this backend today. Treat as the phase's core engineering novelty (RESEARCH.md Pitfall 2) — spike-test the nginx → Docker → browser path before building the full feature on top. |
| `frontend/src/components/ui/tooltip.tsx` | component | — | Does not exist yet; UI-SPEC directs `npx shadcn add tooltip` (official registry, no adaptation needed). |
| Feedback-control optimistic-revert-on-failure mechanics | component | CRUD | Not confirmed against a read file this pass (candidates: `use-mark-blocked.ts`, `use-snooze` mutations) — read one of those at plan time rather than inventing the revert mechanism. |
| Per-remediation grounding query (cross-asset CVE grouping) | service | aggregate/transform | Confirmed via `frontend/src/lib/queries/use-asset-remediations.ts`: the existing `RemediationTicket` shape is per-ticket (already carries `vuln_count`/`critical_count`/`high_count`/`max_severity` aggregated *within* one ticket group), not a cross-asset-by-CVE aggregate. This is RESEARCH.md's own flagged Open Question #2 / Assumption A1 — explicitly out of scope for this pattern map to resolve; D-15 says do not let it block the per-vuln path. |

---

## Metadata

**Analog search scope:** `backend/app/{connectors,auth,ticketing,notifications}/`, `backend/app.{audit,encryption,redis_client,dependencies,main}.py`, `backend/alembic/versions/`, `backend/tests/` (+ `conftest.py`), `nginx/nginx.conf`, `frontend/src/lib/{api.ts,queries/,ai/}`, `frontend/src/components/{connectors,vulnerabilities,settings,ui}/`, `.claude/skills/sketch-findings-getvul/references/{foundation,state-patterns}.md`.
**Files scanned (Read + targeted Grep/offset reads):** 34.
**Pattern extraction date:** 2026-07-28.
