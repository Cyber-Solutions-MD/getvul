# Phase 32: Asset Exposure Context - Pattern Map

**Mapped:** 2026-08-10
**Files analyzed:** 15 new/modified files (backend + frontend)
**Analogs found:** 13 / 15 (2 flagged "no analog — new territory")

**CONTEXT.md supersedes RESEARCH.md on two points** — both change which analogs apply:
1. Asset-group = a **real `AssetGroup` entity** (model + membership + CRUD API + UI), NOT the tag-scoped table RESEARCH.md recommended. Analogs below point at `ConnectorConfig`/`connectors/*` (full tenant-scoped CRUD, live schemas.py) rather than a tag-containment query.
2. Internet-facing = **real per-connector detection** wherever the vendor payload supports it, not just the `external_ip`/tag proxy. No existing connector currently extracts such a signal (verified again this session — see "No Analog Found"), so this is genuinely new engineering, not a copy-paste job.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `backend/alembic/versions/037_add_exposure_context.py` | migration | batch (schema) | `backend/alembic/versions/025_add_asset_tags.py` | exact |
| `backend/alembic/versions/038_add_asset_groups.py` | migration | batch (schema) | `backend/alembic/versions/036_add_enrichment_ref_tables.py` (new-table shape) + `001_initial_schema.py` (tenant FK table shape) | role-match |
| `backend/alembic/versions/039_add_group_exposure_ovr.py` | migration | batch (schema) | `backend/alembic/versions/028_add_ticket_watchers.py` (join/membership table) | role-match |
| `backend/app/assets/models.py` (extend) | model | CRUD | `backend/app/assets/models.py:13-18,39,47` (`DeviceCategory` enum + `risk_score`/`device_category` columns, same file) | exact |
| `backend/app/assets/models.py` — new `AssetGroup`, `AssetGroupMember` classes | model | CRUD | `backend/app/ticketing/models.py:39-57` (`ConnectorConfig`, tenant-scoped entity) + `:139-156` (`TicketWatcher`, composite-PK membership) | exact (composite pattern) |
| `backend/app/assets/exposure.py` (new) | service/utility | transform + batch | `backend/app/assets/classification.py` (pure inference fn) + `backend/app/assets/risk_score.py:84-147` (full-tenant recompute + persist) | exact |
| `backend/app/assets/groups_service.py` (new, or `app/assets/groups.py`) | service | CRUD | `backend/app/connectors/service.py` (full `list_/create_/update_/delete_connector` CRUD shape) | exact |
| `backend/app/assets/router.py` (extend — inline dicts + new endpoints) | controller/route | request-response | `backend/app/assets/router.py:194-222` (list dict), `:318-378` (detail dict), `:536-565` (admin recompute) | exact (same file) |
| `backend/app/assets/router.py` or new `groups_router.py` — AssetGroup CRUD endpoints | controller/route | CRUD | `backend/app/connectors/router.py:110-150` (list/create/patch/delete, `require_admin`) | exact |
| `backend/app/assets/schemas.py` (new schemas for override/group bodies — NOT the dead `AssetResponse`) | model (Pydantic) | request-response | `backend/app/assets/router.py:30-46` (`_AssetOwnerUpdate` inline body model) + `backend/app/connectors/schemas.py:391-414` (`ConnectorCreate`/`ConnectorUpdate`) | exact |
| `backend/app/connectors/{wiz,qualys,nessus,rapid7,defender,crowdstrike}.py` (extend where vendor payload supports it) | transform (connector mapping) | event-driven (sync) | `backend/app/connectors/crowdstrike.py:319,438` (`external_ip` extraction → `NormalizedVulnerability` → `Asset`) | partial — process analog only, no per-vendor field analog exists |
| `backend/app/connectors/sync.py`, `jamf_sync.py`, `humaans_sync.py` (call `infer_exposure_context`) | service (upsert hook) | event-driven | `backend/app/connectors/sync.py:209-301` (`_upsert_asset`, calls `classify_asset_from_data` at :217) | exact |
| `backend/tests/test_asset_exposure.py` (new) | test | integration | `backend/tests/test_asset_owner_reassign.py` (inline-seed, audit-row assertion, 404-not-403 cross-tenant) | exact |
| `backend/tests/test_asset_groups.py` (new) | test | integration | `backend/tests/test_ai_status.py:42-92` (`client_factory(role_user)` RBAC + tenant-isolation pattern) | role-match |
| `frontend/src/lib/queries/use-asset-groups.ts` (new) | hook | CRUD | `frontend/src/lib/queries/use-connectors-admin.ts` (full list/create/update/delete + toast mutation hooks) | exact |
| `frontend/src/lib/queries/use-asset-detail.ts` (extend `AssetDetail` type) | hook/type | request-response | `frontend/src/lib/queries/use-asset-detail.ts:22-52` (same file, `AssetDetail` type) | exact |
| `frontend/src/components/assets/exposure-context-card.tsx` (new) | component | request-response | `frontend/src/components/assets/owner-card.tsx` (flip-edit card pattern) + `identity-metadata-rail.tsx` (stacked-row display) | exact |
| `frontend/src/app/(authed)/dashboard/asset-groups/page.tsx` (new management surface) | component/page | CRUD | `frontend/src/app/(authed)/dashboard/connectors/page.tsx` (list + admin-gated CRUD + `SkeletonTable`/`PartialFailureBanner` states) | exact |
| `frontend/src/components/assets/asset-group-form.tsx` (new) | component | CRUD | `frontend/src/components/connectors/connector-form.tsx` | role-match |

## Pattern Assignments

### `backend/alembic/versions/037_add_exposure_context.py`

**Analog:** `backend/alembic/versions/025_add_asset_tags.py` (full read, lines 1-31)

**Copy exactly:**
```python
# Source: backend/alembic/versions/025_add_asset_tags.py:12-13
revision = "025_add_asset_tags"
down_revision = "024_add_containment_status"
```
Follow this literal-string revision-id pattern (not the default alembic hash). Set `down_revision = "036_add_enrichment_ref_tables"`.

**Hard constraint** (from `036_add_enrichment_ref_tables.py:16-20` and `028_add_ticket_watchers.py` docstrings): `alembic_version.version_num` is `varchar(32)`. `"037_add_exposure_context"` = 25 chars — safe. Count every candidate name before committing to it; this bit the codebase once already (`031_rename_audit_tenant_idx.py`).

**Column-add pattern to copy** (`025_add_asset_tags.py:16-25`):
```python
def upgrade() -> None:
    op.add_column("assets", sa.Column("tags", ARRAY(sa.String()), nullable=True))
    op.create_index("ix_assets_tags", "assets", ["tags"], postgresql_using="gin")

def downgrade() -> None:
    op.drop_index("ix_assets_tags", table_name="assets")
    op.drop_column("assets", "tags")
```
Add 6 plain columns this way (no GIN index needed — these are scalar String/Boolean, not arrays): `business_criticality`, `business_criticality_source`, `data_sensitivity`, `data_sensitivity_source`, `internet_facing`, `internet_facing_source`. Use `server_default` (not just `default`) for each, mirroring `models.py:42` (`is_ignored: ... server_default="false"`) so existing rows backfill without a data migration.

**What differs:** no GIN index required (scalar columns, not arrays); use plain `sa.Column(sa.String(20), server_default="MEDIUM")` etc.

---

### `backend/alembic/versions/038_add_asset_groups.py` + `039_add_group_exposure_ovr.py`

**Analog:** `backend/alembic/versions/036_add_enrichment_ref_tables.py` (full read) for `op.create_table` shape; `backend/app/ticketing/models.py:39-57` (`ConnectorConfig`) for the tenant-scoped-entity column shape (this migration doesn't exist standalone — `001_initial_schema.py` is the only migration that creates a tenant-FK'd standalone table from scratch, per grep; base the DDL off the live model class instead, generated via `alembic revision --autogenerate` against the new `AssetGroup`/`AssetGroupMember`/`AssetGroupExposureOverride` models).

**Copy the `create_table` idiom exactly** (`036_add_enrichment_ref_tables.py:32-51`):
```python
op.create_table(
    "epss_scores",
    sa.Column("cve_id", sa.String(20), primary_key=True),
    ...
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
)
```
For the membership join table, copy `028_add_ticket_watchers.py:20-42` verbatim shape (composite PK, both FKs `ondelete="CASCADE"`):
```python
op.create_table(
    "ticket_watchers",
    sa.Column("ticket_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
    sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.PrimaryKeyConstraint("ticket_id", "user_id"),
)
```
Apply the same shape to `asset_group_members` (`group_id` FK → `asset_groups.id` CASCADE, `asset_id` FK → `assets.id` CASCADE, composite PK).

**What differs:** `asset_groups` itself needs a UUID surrogate PK + `tenant_id` FK + `name`/`description` (unlike `epss_scores`'s natural-key, tenant-less shape) — model it after `ConnectorConfig` (`ticketing/models.py:39-57`: `UUIDPrimaryKeyMixin, TimestampMixin`, `tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)`), not after the tenant-less reference tables.

**Revision-id length check again:** `"038_add_asset_groups"` = 21 chars, safe. `"039_add_group_exposure_ovr"` = 27 chars, safe (mirrors the exact shortening `036_add_enrichment_ref_tables.py`'s docstring documents doing for the same reason).

---

### `backend/app/assets/models.py` (extend)

**Analog:** same file, `DeviceCategory` enum (lines 13-18) + `risk_score`/`device_category` columns (lines 39, 47).

**Copy exactly:**
```python
# Source: backend/app/assets/models.py:13-18
class DeviceCategory(str, enum.Enum):
    WORKSTATION = "WORKSTATION"
    SERVER = "SERVER"
    ...
```
Add parallel `BusinessCriticality`, `DataSensitivity`, `ExposureFieldSource` enums the same way (`str, enum.Enum`, plain `String` column — **no native Postgres `ENUM`**, confirmed convention: `grep` shows `DeviceCategory`/`MisconfigSeverity`/`MisconfigCategory` are all this shape, zero native enums anywhere in the codebase).

**New `AssetGroup`/`AssetGroupMember` classes — copy structural shape from:**
```python
# Source: backend/app/ticketing/models.py:39-57 (ConnectorConfig — tenant-scoped entity)
class ConnectorConfig(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "connector_configs"
    __table_args__ = (UniqueConstraint("tenant_id", "connector_type", name="uq_connector_tenant_type"),)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    ...
```
```python
# Source: backend/app/ticketing/models.py:139-156 (TicketWatcher — composite-PK membership)
class TicketWatcher(Base):
    __tablename__ = "ticket_watchers"
    __table_args__ = (PrimaryKeyConstraint("ticket_id", "user_id"),)
    ticket_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
```
`AssetGroupMember` = same shape with `group_id`/`asset_id`. `AssetGroupExposureOverride` = `UUIDPrimaryKeyMixin` entity with `group_id` FK, `field` (String(30)), `value` (String(20)) — same shape as RESEARCH.md's tag-scoped table design (§3), just keyed on `group_id` instead of `tag`.

**What differs:** RESEARCH.md's `AssetGroupExposureOverride.tag` column becomes `.group_id` (FK to the new `asset_groups.id`), per CONTEXT.md's real-entity decision.

---

### `backend/app/assets/exposure.py` (new)

**Analog:** `backend/app/assets/classification.py` (full file, pure-function inference) for `infer_exposure_context`; `backend/app/assets/risk_score.py:84-147` (`compute_risk_scores`) for `recompute_exposure_context`.

**Core inference pattern to copy** (`classification.py:131-184`, `classify_asset_from_data`):
```python
def classify_asset_from_data(hostname="", os_name="", platform_name="", product_type_desc="") -> str:
    if product_type_desc:
        mapped = CS_TYPE_MAP.get(product_type_desc.lower().strip())
        if mapped: return mapped
    if _match(hostname, NETWORK_HOSTNAME): return "NETWORK"
    ...
    return "OTHER"
```
Same shape for `infer_exposure_context(*, tags, department, job_title, external_ip) -> tuple[str, str, bool]` — pure function, ordered-priority pattern matching, no DB access, default fallback at the end.

**Full-tenant recompute + persist pattern to copy** (`risk_score.py:134-139`):
```python
# Source: backend/app/assets/risk_score.py:134-139
for asset_id, raw_score in rows:
    normalized = _normalize_raw_score(float(raw_score))
    await db.execute(update(Asset).where(Asset.id == asset_id).values(risk_score=normalized))
```
`recompute_exposure_context(db, tenant_id)` follows the identical shape: iterate assets, apply precedence (per-asset override skip → group override → auto), `db.execute(update(Asset).where(...).values(...))`, return a stats dict (`risk_score.py:147`: `return {"assets_updated": updated}`).

**Structured logging on completion** (`risk_score.py:141-145`):
```python
logger.info("risk_scores_computed", tenant_id=str(tenant_id), assets_updated=updated)
```
Mirror with `logger.info("exposure_context_recomputed", tenant_id=..., assets_updated=..., ...)`.

**What differs:** `classify_asset_from_data` always overwrites; `infer_exposure_context`'s caller (not the function itself) must gate the write on `*_source == "AUTO"` per EXPO-03's "permanently wins" guarantee — this gating logic has no existing precedent (new design surface), do not copy `classification.py`'s always-overwrite behavior wholesale.

---

### `backend/app/assets/groups_service.py` (new)

**Analog:** `backend/app/connectors/service.py` (full file, 161 lines) — the only live example of a complete tenant-scoped CRUD service module in this codebase (`schemas.py` here IS wired to `router.py`, unlike the dead `assets/service.py`).

**Copy exactly** (list/create/update/delete shape, `service.py:67-149`):
```python
async def list_connectors(db, tenant_id): ...
async def create_connector(db, tenant_id, body): ...
async def update_connector(db, tenant_id, connector_id, body):
    result = await db.execute(select(ConnectorConfig).where(ConnectorConfig.id == connector_id, ConnectorConfig.tenant_id == tenant_id))
    connector = result.scalar_one_or_none()
    if connector is None:
        return None
    ...
async def delete_connector(db, tenant_id, connector_id):
    ...
    await db.delete(connector)
    return True
```
Every query filters `tenant_id` first (satisfies the v4.0-wide "every query tenant_id-scoped" constraint) and returns `None`/`False` on not-found rather than raising — the router layer converts that to 404.

**What differs:** no encryption step needed (connectors encrypt credentials via `app.encryption`; `AssetGroup` has no secret material) — skip `encrypt_value`/`decrypt_value` entirely, this is the one piece of `service.py` NOT to copy.

---

### `backend/app/assets/router.py` (extend)

**Analog:** same file — `require_role("admin")` recompute-all pattern (lines 536-565), audit-then-commit (381-409, 438-495), inline dict responses (194-222, 318-378).

**Admin-only recompute endpoint — copy exactly:**
```python
# Source: backend/app/assets/router.py:536-546
@router.post("/recompute-risk-scores")
async def recompute_risk_scores(user=Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    stats = await compute_risk_scores(db, user.tenant_id)
    await db.commit()
    return {"message": "Risk scores recomputed", **stats}
```
New endpoint `POST /assets/exposure-context/recompute` follows this identically, importing `from app.assets.exposure import recompute_exposure_context`.

**Note the two different admin-gate dependencies in this codebase** — `assets/router.py` uses `app.auth.dependencies.require_role("admin")` (line 16, 538, 551); `connectors/router.py` uses `app.auth.rbac.require_admin` (a pre-built `RequireRole(UserRole.ADMIN.value)` instance, `rbac.py:52`). Both enforce the identical ADMIN-or-higher check (`rbac.py:12-19` role hierarchy: OWNER=40 > ADMIN=30 > ANALYST=20 > VIEWER=10). **Match whichever dependency the surrounding file already imports** — new endpoints added to `assets/router.py` should use `require_role("admin")` (existing import at line 16); a standalone new `groups_router.py` should use `require_admin` from `rbac.py` (matching `connectors/router.py`'s newer convention) since it's a new file with no legacy import to match.

**Per-asset override endpoint — audit-then-commit to copy exactly:**
```python
# Source: backend/app/assets/router.py:406-409 (asset.ignore)
await audit(db, user, "asset.ignore", "asset", str(asset.id), {"hostname": asset.hostname, "reason": asset.ignored_reason})
await db.commit()
```
```python
# Source: backend/app/assets/router.py:461-486 (update_asset_owner — full handler shape incl. 404-not-403)
asset = (await db.execute(select(Asset).where(Asset.id == asset_id, Asset.tenant_id == user.tenant_id))).scalar_one_or_none()
if not asset:
    raise HTTPException(404, "Asset not found")  # T-12-20: 404 not 403, cross-tenant existence hidden
old_email = asset.assigned_user
asset.assigned_user = new_email
await audit(db, user, "asset.owner_changed", "asset", str(asset.id), {"from": old_email, "to": new_email, "hostname": asset.hostname})
await db.commit()
await db.refresh(asset)
```
New `PATCH /assets/{asset_id}/exposure-context` handler follows this exact shape: load tenant-scoped, 404-not-403 on miss, capture `old_value = getattr(asset, field)`, `setattr(asset, field, value)` + `setattr(asset, f"{field}_source", "ASSET_OVERRIDE")`, `audit(db, user, "asset.exposure_override", "asset", str(asset.id), {"field": field, "old": old_value, "new": value})`, commit.

**Body model — copy exactly:**
```python
# Source: backend/app/assets/router.py:30-46 (_AssetOwnerUpdate)
class _AssetOwnerUpdate(BaseModel):
    model_config = {"extra": "forbid"}
    assigned_user_email: str = Field(..., min_length=3, max_length=320)
    @field_validator("assigned_user_email")
    @classmethod
    def _must_be_email(cls, v): ...
```
New `_ExposureOverrideUpdate(BaseModel)` follows the same shape: `model_config = {"extra": "forbid"}` (mass-assignment defense) + `field_validator` that checks `field` against an allow-list (`{"business_criticality", "data_sensitivity", "internet_facing"}`) and `value` against the matching enum, mirroring the email-validator idiom.

**Inline dict responses — add new fields here, NOT to `schemas.py`:**
```python
# Source: backend/app/assets/router.py:194-222 (list item dict) and :318-378 (detail dict)
"device_category": a.device_category or "OTHER",
"risk_score": a.risk_score or 0,
```
Add `"business_criticality": a.business_criticality`, `"business_criticality_source": a.business_criticality_source`, (same for `data_sensitivity`, `internet_facing`) to BOTH dict-builders — list item (~line 194) and detail (~line 318-378). **This is the single highest-risk step in the whole phase to get wrong** — see Anti-Patterns below.

---

### AssetGroup CRUD router (new endpoints, either in `router.py` or a new `groups_router.py`)

**Analog:** `backend/app/connectors/router.py:110-150` (list/create/update/delete, full CRUD wired to a live `service.py`).

**Copy exactly:**
```python
# Source: backend/app/connectors/router.py:110-137
@router.get("", response_model=list[ConnectorConfigResponse])
async def list_all_connectors(db: DBSession, user: Annotated[CurrentUser, Depends(require_admin)]):
    return await list_connectors(db, user.tenant_id)

@router.post("", response_model=ConnectorConfigResponse, status_code=201)
async def create_new_connector(body: ConnectorCreate, db: DBSession, user: Annotated[CurrentUser, Depends(require_admin)]):
    return await create_connector(db, user.tenant_id, body)

@router.patch("/{connector_id}", response_model=ConnectorConfigResponse)
async def update_existing_connector(connector_id, body, db, user=Depends(require_admin)):
    result = await update_connector(db, user.tenant_id, connector_id, body)
    if result is None:
        raise HTTPException(status_code=404, detail="Connector not found")
    return result

@router.delete("/{connector_id}")
async def delete_existing_connector(connector_id, db, user=Depends(require_admin)):
    deleted = await delete_connector(db, user.tenant_id, connector_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Connector not found")
    return {"message": "Connector deleted"}
```
Mirror 1:1 for `GET/POST /asset-groups`, `PATCH/DELETE /asset-groups/{group_id}`, plus member-add/remove endpoints (`POST/DELETE /asset-groups/{group_id}/members/{asset_id}`) using the `TicketWatcher`-style idempotent composite-PK pattern. Note: `list_connectors`/`create_connector` are NOT admin-gated in every codebase surface — verify against CONTEXT.md whether non-admin roles should be able to VIEW groups (list) while only admins mutate; `require_admin` on GET here is a connectors-specific choice, don't copy it blindly onto the list endpoint if viewer/analyst visibility is desired.

**Group-scope override endpoint — same audit pattern as per-asset**, `resource_type="asset_group"`, `resource_id=str(group.id)`.

---

### `backend/app/connectors/sync.py`, `jamf_sync.py`, `humaans_sync.py` (call `infer_exposure_context`)

**Analog:** `backend/app/connectors/sync.py:209-301` (`_upsert_asset`), specifically the `classify_asset_from_data` call site.

**Copy exactly** (`sync.py:217-222` + `:266-267`):
```python
device_category = classify_asset_from_data(hostname=hostname, os_name=v.os_name or "", platform_name=platform_name, product_type_desc=product_type_desc)
...
if product_type_desc or not asset.device_category or asset.device_category == "OTHER":
    asset.device_category = device_category
```
Add the equivalent `infer_exposure_context(...)` call at both the create branch (`sync.py:233-258`, unconditional — brand-new asset has no override yet) and the update branch (`sync.py:261-300`, gated per-field on `*_source == "AUTO"`). **Must also add the same call inside `jamf_sync.py:159,177-178` and `humaans_sync.py:173-175,182`** (both set `department`/`job_title`-equivalent fields AFTER the initial scanner upsert) — this is Pitfall 2 from RESEARCH.md: `classify_asset_from_data` already re-runs at every enrichment touchpoint; exposure-context inference must be *deliberately* copied to the same touchpoints, it does not happen automatically. **`intune_sync.py` does NOT set `department`** (verified again this session: `intune_sync.py:90` sets only `assigned_user`) — do not assume an inference call there needs the department signal; internet_facing/external_ip is still relevant if Intune surfaces it.

---

### Real per-connector internet-facing detection (`wiz.py`, `qualys.py`, `nessus.py`, `rapid7.py`, `defender.py`, `crowdstrike.py`)

**Analog (process, not field):** `crowdstrike.py:319,438` — the only existing example of a connector-specific network-exposure-adjacent field flowing end-to-end:
```python
# Source: backend/app/connectors/crowdstrike.py:319,438
external_ip = device.get("external_ip", "")
...
external_ip=external_ip or None,
```
```python
# Source: backend/app/connectors/base.py:36 (NormalizedVulnerability dataclass field)
external_ip: str | None = None
```
```python
# Source: backend/app/connectors/sync.py:248,279
external_ip=getattr(v, "external_ip", None),   # create branch
if getattr(v, "external_ip", None): asset.external_ip = v.external_ip   # update branch
```
**Copy this three-hop wiring shape** (raw payload field → new `NormalizedVulnerability` field → `sync.py` create/update branches → `Asset` column) for whichever per-connector field the phase adds (e.g. Wiz `vulnerableAsset { publicExposure }` if the Wiz GraphQL schema supports it — **unverified this session**, the `VULNERABILITY_QUERY` read at `wiz.py:39-75` has no such field today; adding one is genuinely new engineering, follow the `WizGraphQLSchemaError` fallback pattern at `wiz.py:19-30` if the field name turns out to be wrong).

**What differs / no analog:** there is no existing "add a new mapped field to a connector's raw-payload parser" precedent beyond `external_ip` itself (which was presumably added in an earlier phase not covered by this research pass). Treat each connector's actual capability as unverified until the raw API/GraphQL schema is inspected directly — do not assume Qualys/Nessus/Rapid7/Defender expose a usable field just because the requirement asks for one. Document per-connector coverage honestly in the module docstring, per CONTEXT.md's explicit instruction.

---

### `backend/tests/test_asset_exposure.py` (new)

**Analog:** `backend/tests/test_asset_owner_reassign.py` (full file, 181 lines) — inline-seed helper, audit-row assertion, 404-not-403 cross-tenant probe.

**Copy exactly** (seed helper shape, lines 33-45):
```python
def _seed_asset(tenant_id, hostname, *, assigned_user=None, os_name="Ubuntu 22.04 LTS") -> Asset:
    return Asset(tenant_id=tenant_id, hostname=hostname, assigned_user=assigned_user, os_name=os_name)
```
**Audit-row assertion pattern** (lines 68-86):
```python
audit_rows = (await db_session.execute(select(AuditLog).where(AuditLog.action == "asset.owner_changed", AuditLog.resource_id == str(asset_id)))).scalars().all()
assert len(audit_rows) == 1
assert row.details["from"] == ... and row.details["to"] == ...
```
**Cross-tenant 404-not-403 pattern** (lines 100-130) — reuse verbatim for the override endpoint tests.

---

### `backend/tests/test_asset_groups.py` (new)

**Analog:** `backend/tests/test_ai_status.py:42-92` — `client_factory(role_user)` pattern for RBAC + tenant-isolation across multiple roles in one file.

**Copy exactly:**
```python
# Source: backend/tests/test_ai_status.py:42-45 (adapt path/assertions)
async def test_status_viewer_unconfigured_returns_false(client_factory, db_session, tenant_a, viewer_user):
    client = client_factory(viewer_user)
    ...
```
Use `client_factory(admin_user)` for the happy-path CRUD tests and `client_factory(analyst_user)`/`client_factory(viewer_user)` for the 403 RBAC-denial tests (`conftest.py:286` `admin_user` fixture, `:274` `analyst_user`, `:280` `viewer_user` all confirmed present). For cross-tenant isolation, use `analyst_user_b`/`tenant_b` exactly as `test_asset_owner_reassign.py:100-130` does.

---

### `frontend/src/lib/queries/use-asset-groups.ts` (new)

**Analog:** `frontend/src/lib/queries/use-connectors-admin.ts` (full file, 276 lines).

**Copy exactly** (list query + mutation-with-toast shape):
```typescript
// Source: frontend/src/lib/queries/use-connectors-admin.ts:130-138
export function useConnectorsList() {
  return useQuery({
    queryKey: queryKeys.connectors.list(),
    queryFn: ({ signal }) => api<ConnectorConfigResponse[]>('/api/v1/connectors', { signal }),
    staleTime: 60_000,
    retry: 1,
  });
}
```
```typescript
// Source: frontend/src/lib/queries/use-connectors-admin.ts:160-179
export function useCreateConnector() {
  const qc = useQueryClient();
  const { toast } = useToast();
  return useMutation({
    mutationFn: (body) => api('/api/v1/connectors', { method: 'POST', body: JSON.stringify(body), headers: {'Content-Type': 'application/json'} }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.connectors.all }); toast({ variant: 'success', message: 'Connector added.' }); },
    onError: (err) => { toast({ variant: 'error', message: err.message || 'Failed to add connector.' }); },
  });
}
```
Mirror for `useAssetGroupsList`, `useCreateAssetGroup`, `useUpdateAssetGroup`, `useDeleteAssetGroup`, `useAddGroupMember`/`useRemoveGroupMember`, `useSetExposureOverride` (per-asset), `useSetGroupExposureOverride`. Add a `queryKeys.assetGroups` entry to `keys.ts` mirroring `queryKeys.connectors`.

---

### `frontend/src/lib/queries/use-asset-detail.ts` (extend)

**Analog:** same file — `AssetDetail` type (lines 22-52).

**Add fields to the existing type, don't create a new one:**
```typescript
// Source: frontend/src/lib/queries/use-asset-detail.ts:22-52
export type AssetDetail = {
  ...
  tags: string[] | null;
  department: string | null;
};
```
Add `business_criticality: string | null`, `business_criticality_source: 'AUTO' | 'ASSET_OVERRIDE' | 'GROUP_OVERRIDE' | null` (+ same pair ×2 for `data_sensitivity`, `internet_facing`) at the end of the type, matching the snake_case-no-transform convention already documented in `use-connectors-admin.ts:15` ("Snake_case fields: no transform layer").

---

### `frontend/src/components/assets/exposure-context-card.tsx` (new)

**Analog:** `frontend/src/components/assets/owner-card.tsx` (full file, 113 lines) for the flip-edit interaction; `identity-metadata-rail.tsx` (full file) for stacked-row display.

**Flip-edit pattern to copy exactly** (`owner-card.tsx:46-68`):
```tsx
const [isEditing, setIsEditing] = useState(false);
if (isEditing) {
  return (
    <section className="rounded-lg border border-border-subtle bg-surface-2 p-4" aria-label="Owner — edit mode">
      <ReassignCombobox assetId={asset.id} initialEmail={asset.assigned_user} onDone={() => setIsEditing(false)} />
    </section>
  );
}
```
Apply per-field (3 flip-edit rows: criticality, sensitivity, internet-facing), each showing current value + a small source badge (AUTO / manually overridden / group: {name}) when not `AUTO` — no existing "source badge" component exists; compose from the sunset `<span className="rounded-full ...">` pill idiom already used for `IdpPill` (`owner-card.tsx:33-44`).

**Stacked-row pattern to copy exactly** (`identity-metadata-rail.tsx:14-30`):
```tsx
function MetadataRow({ label, value, mono }) {
  if (value === null || value === undefined || value === '') return null;
  return (
    <div className="flex items-baseline justify-between gap-3 border-t border-border-subtle py-2 text-xs">
      <span className="uppercase tracking-wide text-text-faint">{label}</span>
      <span className={mono ? 'font-mono text-text' : 'text-text'}>{value}</span>
    </div>
  );
}
```
**Admin gating in UI** — copy exactly from `connectors/page.tsx:98-99`:
```tsx
const { user } = useAuth();
const isAdmin = user?.role === 'OWNER' || user?.role === 'ADMIN';
```
Hide/disable the override "Edit" affordance unless `isAdmin` (backend independently enforces via `require_admin`/`require_role("admin")` — UI gating is defense-in-depth per CONTEXT.md's UI section, not the actual security boundary).

---

### `frontend/src/app/(authed)/dashboard/asset-groups/page.tsx` (new)

**Analog:** `frontend/src/app/(authed)/dashboard/connectors/page.tsx` (full file read through line 130) — category-sectioned list + admin-gated CRUD + mandatory state patterns.

**State-pattern imports to copy exactly** (`connectors/page.tsx:33-34`, per `sketch-findings-getvul` D-X-01, mandatory):
```tsx
import { SkeletonTable, PartialFailureBanner } from '@/components/states';
```
```tsx
// isPending → <SkeletonTable columns={SKELETON_COLUMNS} />
// error     → <PartialFailureBanner ... />
// zero-state → browsable catalog card / explained empty (per foundation.md state-patterns.md)
```
**Admin gate + list/create/update/delete wiring** — copy the whole `ConnectorsPageInner` composition shape (`connectors/page.tsx:97-127`): `useAuth()` → `isAdmin` derivation, `useXxxList()`/`useCreateXxx()`/`useUpdateXxx()`/`useDeleteXxx()` hooks, local `FormState`/`DeleteState` for the add/edit modal and delete-confirm modal (`ConfirmModal`, `ResponsiveDialog` — both existing shared components, reuse don't reinvent).

**Read `references/page-layouts.md` and `references/state-patterns.md`** from the `sketch-findings-getvul` skill before building this page — it's a genuinely new list/management surface and must follow the locked hero/list layout + state-pattern conventions, not a Tailwind admin-template grid (explicit anti-pattern in project CLAUDE.md).

---

## Shared Patterns

### Audit-then-commit (EXPO-05)
**Source:** `backend/app/audit.py::audit()` (lines 129-200), used at `backend/app/assets/router.py:406-409, 478-486`.
**Apply to:** per-asset override endpoint, group override endpoint, group CRUD endpoints (create/update/delete of `AssetGroup` itself is also a mutating admin action worth an audit row, mirroring `connector.create`/`connector.update`/`connector.delete` already listed in the action registry at `audit.py:58`).
```python
await audit(db, user, "asset.exposure_override", "asset", str(asset.id), {"field": field, "old": old_value, "new": value})
await db.commit()
```
Fail-closed semantics are automatic (`audit.py:140-156` docstring) — do not wrap the `audit()` call in a try/except that swallows exceptions.
**Action-name registry** (`audit.py:53-61`, plain comment block, no enum) — append: `asset.exposure_override`, `asset_group.create/update/delete`, `asset_group.exposure_override`, `asset.exposure_recompute` (batch summary row per RESEARCH.md §4 recommendation for AUTO writes).

### Admin-only gate (backend)
**Source:** `backend/app/auth/dependencies.py::require_role("admin")` (used in `assets/router.py:538,551`) OR `backend/app/auth/rbac.py::require_admin` (used in `connectors/router.py`, all handlers). Both check the same `ROLE_HIERARCHY` (`rbac.py:12-19`: OWNER=40 > ADMIN=30 > ANALYST=20 > VIEWER=10).
**Apply to:** exposure-context recompute endpoint, all AssetGroup CRUD endpoints, both override endpoints (per-asset and group-scope).

### Admin-only gate (frontend, defense-in-depth only)
**Source:** `frontend/src/app/(authed)/dashboard/connectors/page.tsx:98-99`, `frontend/src/components/settings/settings-sidebar-shell.tsx:69-75`.
```tsx
const isAdmin = user?.role === 'OWNER' || user?.role === 'ADMIN';
```
**Apply to:** exposure override edit affordance, asset-groups management page/nav entry.

### Tenant scoping
**Source:** every query in `backend/app/assets/router.py` (e.g. line 109, 286, 396) and `backend/app/connectors/service.py` (lines 72, 108-113, 139-144): `.where(Model.tenant_id == user.tenant_id)` (or `tenant_id` param) is the first filter clause on every SELECT/UPDATE/DELETE.
**Apply to:** every new query touching `assets`, `asset_groups`, `asset_group_members`, `asset_group_exposure_overrides`.

### 404-not-403 on cross-tenant probe
**Source:** `backend/app/assets/router.py:465-466` (comment: "T-12-20 mitigation — 404 (not 403) keeps cross-tenant existence private"), tested in `backend/tests/test_asset_owner_reassign.py:100-130`.
**Apply to:** per-asset override endpoint (asset_id guess), group override/CRUD endpoints (group_id guess).

### No native Postgres ENUM
**Source:** `backend/app/assets/models.py:13-18` (`DeviceCategory`), confirmed pattern via `MisconfigSeverity`/`MisconfigCategory` (cspm/models.py).
**Apply to:** `BusinessCriticality`, `DataSensitivity`, `ExposureFieldSource` — Python `str, enum.Enum` + `String(20)` column, never `sa.Enum(...)`.

---

## No Analog Found

| File / Change | Role | Data Flow | Reason |
|---|---|---|---|
| Real per-connector internet-facing extraction (Wiz/Qualys/Nessus/Rapid7/Defender payload parsing beyond `external_ip`) | transform (connector mapping) | event-driven | No connector's current Python mapping code exposes a public-IP/security-group/network-exposure field today (re-verified this session: `grep -ni "public_ip\|security_group\|internet\|network_interface\|subnet\|vpc\|dmz"` across all 6 connector files returns zero hits besides `crowdstrike.py`'s `external_ip`). The `external_ip` wiring (`crowdstrike.py` → `base.py` → `sync.py`) is the closest **process** analog, but there is no field-level precedent per vendor — the raw Wiz GraphQL/Qualys/Nessus/Rapid7/Defender API schemas have not been inspected at the wire level in this codebase to confirm a mappable field exists. Executors must treat this as exploratory: inspect each vendor's actual API response before assuming a field is there, and honestly document per-connector coverage (CONTEXT.md's explicit instruction) rather than guessing a field name that may not exist. |
| Multi-tag / multi-group conflict tie-break unit test assertions | test | integration | No existing precedent for "N overlapping matches, most-recent wins" logic anywhere in this codebase to model the test shape on — RESEARCH.md flags this as genuinely new design surface (Assumptions Log A3). Base the test structure on `test_asset_owner_reassign.py`'s inline-seed style but the assertions themselves are novel. |

## Anti-Patterns to Avoid

- **Extending `app/assets/classifier.py`** — confirmed dead code again this session (zero external call sites via grep). Any change here ships with zero production effect.
- **Extending `app/assets/service.py` / `app/assets/schemas.py`** — confirmed dead code again this session (`router.py` never imports `list_assets`/`get_asset`/`AssetResponse`/`AssetSummary`/`AssetFilter` from these files — the router builds inline dicts). New exposure-context fields added only here will silently not appear in `GET /assets`/`GET /assets/{id}` responses. **Add fields to `router.py`'s inline dicts directly** (list ~line 194-222, detail ~line 318-378).
- **A tag-scoped "group"** — this was RESEARCH.md's default recommendation but CONTEXT.md's `[USER]` decision explicitly overrides it: build a real `AssetGroup` + membership entity, not a tag-containment query (`Asset.tags.contains([tag])`). Do not silently revert to the cheaper tag-based design.
- **Assuming a scanner "internet-facing flag" exists to simply read** — it doesn't, in any of the 6 connectors, as of this session's re-verification. CONTEXT.md still requires attempting real per-connector detection "wherever the vendor payload supports it" — this means inspecting each vendor's actual raw API/GraphQL response, not grepping for a field that was already mapped into `NormalizedVulnerability`.
- **Auditing every AUTO-sourced write individually** — would flood `audit_logs` on every scanner sync (thousands of assets × 3 fields). CONTEXT.md resolves this: auto-inference audits only when a value **actually changes**, actor = `system:exposure-inference`, never on re-affirmation.
- **Calibration cap including admin/group overrides** — CONTEXT.md explicitly exempts overrides from the EXPO-06 cap (auto-inflation only) to avoid contradicting EXPO-03's "override permanently wins" guarantee. Don't build a calibration check that would downgrade or block an admin's explicit CRITICAL override.
- **Using `require_admin` (rbac.py) and `require_role("admin")` (dependencies.py) inconsistently within the same new file** — pick one per file based on what that file already imports (see Pattern Assignments note under `router.py`); don't mix both dependencies across sibling endpoints in the same router for no reason.

## Metadata

**Analog search scope:** `backend/app/assets/`, `backend/app/connectors/`, `backend/app/ticketing/`, `backend/app/audit.py`, `backend/app/auth/`, `backend/alembic/versions/` (last 15 revisions), `backend/tests/` (asset + connector + ai-status test files), `frontend/src/lib/queries/`, `frontend/src/components/{assets,connectors,settings}/`, `frontend/src/app/(authed)/dashboard/{assets,connectors,settings}/`.
**Files scanned (read in full or targeted sections):** `assets/models.py`, `assets/classification.py`, `assets/classifier.py` (grep only, confirmed dead), `assets/risk_score.py`, `assets/router.py` (full), `audit.py` (full), `auth/rbac.py`, `connectors/router.py`, `connectors/service.py` (full), `connectors/schemas.py` (partial), `connectors/sync.py` (upsert section), `connectors/jamf_sync.py`/`humaans_sync.py`/`intune_sync.py` (grep), `connectors/wiz.py` (partial, GraphQL query), `ticketing/models.py` (full), `alembic/versions/025_add_asset_tags.py`, `036_add_enrichment_ref_tables.py`, `028_add_ticket_watchers.py` (all full), `tests/test_asset_owner_reassign.py` (full), `tests/test_ai_status.py` (grep), `tests/conftest.py` (fixture section), `frontend/src/lib/queries/use-connectors-admin.ts` (full), `use-asset-detail.ts` (full), `frontend/src/components/assets/owner-card.tsx` (full), `identity-metadata-rail.tsx` (full), `frontend/src/app/(authed)/dashboard/connectors/page.tsx` (partial), `frontend/.../settings/settings-sidebar-shell.tsx` (grep), `.claude/skills/sketch-findings-getvul/SKILL.md` (partial).
**Pattern extraction date:** 2026-08-10
