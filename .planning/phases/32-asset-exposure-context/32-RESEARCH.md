# Phase 32: Asset Exposure Context - Research

**Researched:** 2026-08-10
**Domain:** Backend data model + inference service (FastAPI/SQLAlchemy/Alembic), no frontend surface required
**Confidence:** MEDIUM — codebase reconnaissance is HIGH confidence (read directly, file:line cited); the "scanner internet-facing flags" data source named in EXPO-02 does not actually exist in any connector today, which is a load-bearing gap flagged throughout this document.

## Summary

Phase 32 asks for three new exposure-context fields on `Asset` (business-criticality, data-sensitivity, internet-facing), auto-inferred at upsert, admin-overridable at per-asset AND asset-group scope with defined precedence, fully audit-logged, and calibration-bounded against criticality inflation.

No code for this exists yet. There are two *unrelated* pre-existing systems this phase must not confuse itself with:

1. **`app/assets/classification.py`** (used in production, called from `sync.py`, `jamf_sync.py`, `intune_sync.py`, `router.py`) classifies **`device_category`** (WORKSTATION/SERVER/NETWORK/MOBILE/OTHER) from hostname/OS/platform patterns. It has nothing to do with business-criticality, data-sensitivity, or internet-facing.
2. **`app/assets/classifier.py`** (`classify_device`/`classify_all_assets`) is a **near-duplicate, dead-code** implementation of the same device-category classification — grep confirms zero call sites outside itself. Do not extend either file for exposure-context; Phase 32 needs new columns and a new inference module, not a modification of device classification.

There is also no `AssetGroup` model, no asset-linked internet-facing flag from any of the 5 scanner connectors (Wiz, Qualys, Nessus, Rapid7, Defender), and two of the three "asset" query/response code paths in `app/assets/service.py` + `app/assets/schemas.py` are dead code (the live `/assets` and `/assets/{id}` endpoints in `router.py` build inline dicts directly from the ORM object and never import `service.py` or `AssetResponse`/`AssetSummary`). Extend `router.py`'s inline dict pattern, not the dead schema/service files.

The codebase already has two directly-reusable idioms for this phase: (a) the audit-then-commit-in-same-transaction pattern (`app/audit.py::audit()`, used by `owner`/`ignore`/`unignore` endpoints), and (b) the "admin-only full-tenant recompute" endpoint pattern (`POST /assets/classify`, `POST /assets/recompute-risk-scores`, both `require_role("admin")`), which is the direct precedent for a new `POST /assets/exposure-context/recompute` endpoint and for how auto-inference should be re-run across a tenant's assets.

**Primary recommendation:** Add 3 new criticality/sensitivity/internet-facing columns + 3 companion `*_source` enum columns directly on `Asset` (materialized/denormalized, following the `risk_score`/`device_category` precedent — not a separate EAV table). Model "asset-group" as a **tag-scoped override** (reusing the existing `Asset.tags` GIN-indexed array, zero new membership table) rather than inventing a new group-membership entity. Precedence: per-asset override > group(tag) override > auto-inference. Gate the calibration cap on auto-inferred values only (never override admin-set values). Flag the "scanner internet-facing flags" data-source gap to the user before planning locks it in — today the only real signals are `Asset.external_ip is not None` and a manually-applied `"internet-facing"` tag.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Exposure-context fields storage | Database / Storage (`assets` table) | — | Materialized columns on `Asset`, same tier as `risk_score`/`device_category` today |
| Auto-inference at upsert | API / Backend (`app/assets/exposure.py`, new) | Database (reads MDM/HR/tags already on `Asset`) | Pure function over an `Asset` ORM object, called from connector sync paths — mirrors `classify_asset_from_data` |
| Per-asset / group override write | API / Backend (`app/assets/router.py`, new endpoints) | Database (`asset_group_exposure_overrides` table, new) | Admin-only mutating endpoints, same tier as existing `/owner`, `/ignore` endpoints |
| Precedence resolution (auto vs asset vs group) | API / Backend (`app/assets/exposure.py::recompute_exposure_context`) | Database | Same tier + pattern as `compute_risk_scores` — a full-tenant recompute function |
| Audit trail | API / Backend (`app/audit.py::audit()`) | Database (`audit_logs` table, existing) | Reuse existing helper verbatim — no new audit infra |
| Calibration check | API / Backend (new function + admin endpoint) | Database (aggregate query over `assets`) | Same shape as `asset_stats`'s risk-distribution aggregate query |
| Consumer (Phase 33 risk model) | API / Backend | — | Out of scope for Phase 32 — Phase 32 only has to make the fields exist, correct, and stable; Phase 33 reads them |

## Standard Stack

### Core (all already installed — zero new pip dependencies needed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy | 2.0 (async) | ORM + `Mapped`/`mapped_column` models | Already the whole codebase's ORM |
| Alembic | (project-pinned) | Migration for new columns/table | Already the whole codebase's migration tool; sequential numeric-prefixed revision ids (see Pitfalls) |
| Pydantic | v2 | Request/response validation for new override endpoints | Already used everywhere in `app/*/schemas.py` and inline `BaseModel`s in routers |
| FastAPI | (project-pinned) | New router endpoints | Existing `app/assets/router.py` |
| pytest / pytest-asyncio | 8.3 / 0.24 | Tests | Existing convention — `asyncio_mode = "auto"` in `pyproject.toml` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `sqlalchemy.orm.attributes.flag_modified` | (bundled) | Mark JSONB mutation when writing details onto e.g. `mdm_details` if touched incidentally | Only if a JSONB field is mutated in-place; NOT needed for the new columns themselves since they are scalar |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Materialized columns + `*_source` discriminator on `Asset` | A separate `asset_exposure_context` 1:1 table | Rejected: adds a join to every asset list/detail read (already 2 queries per row in `list_assets`); the codebase's own precedent (`risk_score`, `device_category` living directly on `Asset`) argues for columns, not a side table |
| Tag-scoped "group" (reuse `Asset.tags`) | A first-class `AssetGroup` + `AssetGroupMember` (M2M) entity | Tag-scoped avoids a whole new membership-management subsystem and satisfies EXPO-02's "seeded from tags" language for free; a real M2M group entity is more explicit/auditable but needs a management UI/API this phase doesn't otherwise require — flagged as `[ASSUMED]`, see Assumptions Log A1 |
| `internet_facing` inferred from real scanner data | Treat `external_ip IS NOT NULL` + `"internet-facing"` tag as the only available signals | No connector in this codebase (Wiz/Qualys/Nessus/Rapid7/Defender/CrowdStrike) currently emits a public/internet-facing flag — verified by grep, see Pitfall 1 |

**Installation:** none — no new packages.

**Version verification:** N/A — no new third-party dependency introduced by this phase; only new first-party code + one Alembic migration.

## Locked Decisions (from STATE.md — no CONTEXT.md exists yet for Phase 32)

No `/gsd-discuss-phase 32` has run yet (`.planning/phases/32-asset-exposure-context/` contains no `32-CONTEXT.md`). The following are locked at the milestone level (`STATE.md`, do not re-open):

- Exposure override supports per-asset AND asset-group scope with a **defined and tested precedence** between them (EXPO-03/04).
- Single-VM Docker Compose + in-process asyncio scheduler only — **no new infra** (no Celery/Arq, no new services).
- Every query must be `tenant_id`-scoped.
- Audit events are **required** for new mutating actions (exposure overrides, per EXPO-05).
- Encrypted connector creds must keep decrypting (irrelevant to this phase's own code, but a regression guard for anything touching `app/connectors/service.py`).

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EXPO-01 | Each asset carries business-criticality, data-sensitivity, internet-facing exposure-context fields | New `Asset` columns — see Migration Plan |
| EXPO-02 | Auto-inferred at upsert from MDM/HR/IdP enrichment + scanner internet-facing flags, seeded from (never overwriting) `Asset.tags` | See "Recommended Approach per Success Criterion" §1 — flags the missing scanner-flag data source (Pitfall 1) |
| EXPO-03 | Admin can override any field per asset; override permanently wins over future auto-inference | `*_source` discriminator column per field — see §2 |
| EXPO-04 | Admin can override at asset-group scope, with defined precedence vs per-asset override | Tag-scoped group override table + precedence — see §3 |
| EXPO-05 | Every override (auto or manual) is audit-logged (actor, asset/group, field, old→new) | Reuse `app/audit.py::audit()` — see §4 |
| EXPO-06 | Calibration check caps/flags proportion of assets auto-classified at highest criticality tier | New calibration function + seed fixture — see §5 |

## Existing-Code Findings (critical reconnaissance)

### `app/assets/classification.py` vs `app/assets/classifier.py`
- **`classification.py`** (198 lines) — LIVE. Exports `classify_asset_from_data(hostname, os_name, platform_name, product_type_desc)` and `classify_asset(asset)`. Classifies **device category only** (`WORKSTATION|SERVER|NETWORK|MOBILE|OTHER`). Called from:
  - `app/connectors/sync.py:14,217,267` — the real ingestion upsert path (`_upsert_asset`, line 209-301)
  - `app/connectors/jamf_sync.py:14`
  - `app/enrich_assets.py:11` (standalone one-off script, not part of the scheduler)
  - `app/assets/router.py:14,560` — the `POST /assets/classify` admin recompute-all endpoint
- **`classifier.py`** (148 lines) — DEAD CODE. Exports `classify_device(...)` and `classify_all_assets(db, tenant_id)`, doing the *same* device-category classification with slightly different regex patterns. `grep -rn "classify_device"` returns only its own definition and its own internal call — **zero external call sites**. `[VERIFIED: grep across app/]`
- **Neither file classifies business-criticality, data-sensitivity, or internet-facing.** Phase 32 needs an entirely new module, e.g. `app/assets/exposure.py`, not a modification of either classification file.

### `app/assets/models.py` (76 lines) — current `Asset` schema
Relevant existing columns (file:line):
```
tenant_id            :26   — every query already tenant_id-scoped (constraint satisfied)
tags                 :71   — ARRAY(String), GIN-indexed (alembic 025_add_asset_tags), "operational labels
                              (e.g. 'pci', 'dmz', 'tier-1')" — EXPO-02's seed source
department           :62   — String(200), populated by JAMF (`jamf_sync.py:159,177-178`) and Humaans
                              (`humaans_sync.py:174-175`)
mdm_details          :67   — JSONB, holds `humaans_job_title`, `humaans_email`, `github_handle`, etc.
                              (`humaans_sync.py:182`)
external_ip          :56   — String(50), populated only by CrowdStrike (`crowdstrike.py:319,438`) —
                              the closest thing to an "internet-facing" signal that exists today
device_category      :47   — precedent for a materialized/denormalized classification column
risk_score           :39   — precedent for a materialized score recomputed by a full-tenant service fn
managed_by           :65   — "JAMF" | "INTUNE" — which MDM enriched this asset
```
No `business_criticality`, `data_sensitivity`, or `internet_facing` column exists. No override/source-discriminator column exists. `[VERIFIED: Read app/assets/models.py]`

### Enrichment sources feeding `Asset` (for auto-inference inputs)
| Source | File | What it sets on `Asset` | Usable as exposure-context signal? |
|--------|------|--------------------------|-------------------------------------|
| JAMF (MDM) | `app/connectors/jamf_sync.py:159,177-178` | `department`, `assigned_user`, `managed_by="JAMF"`, `mdm_details` (filevault/SIP/gatekeeper) | `department` → business-criticality signal (e.g. Finance/Legal/Security/Executive departments) |
| Intune (MDM) | `app/connectors/intune_sync.py:90-104` | `assigned_user`, `managed_by="INTUNE"`, `mdm_details` | Same department-style signal not directly present — Intune sync does not set `department` (verify before relying on it — flagged `[ASSUMED]` A2) |
| Humaans (HR) | `app/connectors/humaans_sync.py:168-186` | `assigned_user`, `department`, `mdm_details["humaans_job_title"]`, `humaans_email`, `github_handle` | `department` + `humaans_job_title` (e.g. contains "CFO"/"VP"/"Director") → strong business-criticality signal |
| Google Workspace / Azure Entra (IdP) | `app/connectors/directory_sync.py:19-130` | **`app.tenants.models.User`** (department, job_title, groups) — a *different* table (platform login users), NOT the `Asset` table directly | Indirect only — `router.py::_get_directory_user` (line 49-80) joins `User` to `Asset` via email matching at *read time*, not at upsert. Auto-inference at upsert cannot rely on this join unless it's replicated into the inference function — flag as Open Question |
| Scanner "internet-facing" flag | — | **Does not exist.** Grepped `internet\|public\|exposure\|is_dmz` across `wiz.py`, `qualys.py`, `nessus.py`, `rapid7.py`, `defender.py`, `crowdstrike.py` — zero hits except `defender.py`'s unrelated `publicExploit` (exploit-availability, not asset exposure) | **Gap — see Pitfall 1.** Closest real proxies: `external_ip IS NOT NULL` (CrowdStrike-only) and manually-applied `"internet-facing"` tag (already referenced as an example tag in `app/ai/prompt_builder.py:474,484,494` mock data) |
| CSPM (Wiz) network misconfigurations | `app/cspm/models.py` | `Misconfiguration.category == "NETWORK"` findings tied to `resource_id`/`cloud_account_id`, not directly to `Asset.id` | Weak/indirect — would need `Misconfiguration.resource_id` ↔ `Asset.cloud_resource_id` join; not currently done anywhere in the codebase. Out of scope for v1 of this phase — flag as Open Question, don't build in Phase 32 |

### Audit pattern (`app/audit.py`)
`audit(db, user, action, resource_type, resource_id, details, ip_address=None)` (line 129-200). Fail-closed: any exception writing the `AuditLog` row propagates and the caller's `db.commit()` is skipped, so the mutation and its audit row are atomic (see docstring lines 140-156). Existing convention: `await audit(...)` immediately followed by `await db.commit()` in the same handler, e.g. `ignore_asset` (router.py:381-409), `update_asset_owner`. **Action-name registry is a plain comment block at lines 53-61** — Phase 32 should append new action names there (e.g. `asset.exposure_override`, `asset_group.exposure_override`) as documentation, no code change required to the enum (there is no enum — `action` is a free-form `String(50)`).

### Asset-group concept — does it exist?
**No.** `grep -rln "class.*Group\|group_id\|GroupMembership"` across `app/` (excluding tests) returns only IdP-side group concepts (`azure_entra.py`, `okta_sync.py` — Azure AD / Okta groups synced into `User.groups`) and AI prompt builder references to Humaans "teams" — none of these are an asset-grouping construct. `app/ticketing/rule_engine.py::find_matching_assets` (line 51-130) dynamically matches assets against rule *conditions* (tags, severity, etc.) for ticket creation — a similar *shape* of problem (tag-based asset matching) but a transient per-rule-run match, not a persisted, named, overridable group entity. Precedence design for EXPO-04 has no existing precedent to reconcile against — it is new design surface (see "Override-Precedence Model" below).

### Alembic conventions
Latest head: `036_add_enrichment_ref_tables` (`down_revision` chain confirmed sequential). Conventions verified from `025_add_asset_tags.py` and `036_add_enrichment_ref_tables.py`:
- Revision id = filename prefix as a **string**, not the default alembic hash (e.g. `revision = "037_add_exposure_context"`)
- **Hard constraint, verified in a migration docstring**: `alembic_version.version_num` is `varchar(32)` — revision ids **must be ≤ 32 characters** or the migration fails with `StringDataRightTruncationError` (this already bit `031_rename_audit_tenant_idx.py` once). `"037_add_exposure_context"` is 25 chars — safe. `"038_add_asset_group_exposure_overrides"` is 39 chars — **too long**, must be shortened (e.g. `"038_add_group_exposure_ovr"`, 27 chars).
- New GIN/array columns follow `025_add_asset_tags.py`'s pattern (add column + separate `create_index(..., postgresql_using="gin")`) if a new array/JSONB column is added.
- No native Postgres `ENUM` types are used anywhere in this codebase for status/category-like columns (`DeviceCategory`, `MisconfigSeverity`, `MisconfigCategory` are all Python `str, enum.Enum` backed by a plain `String` column) — Phase 32's new criticality/sensitivity/source columns should follow this convention (`String(20)` + Python enum for validation), not a Postgres-native enum, to avoid `ALTER TYPE ... ADD VALUE` migration pain later.

### Dead code in the assets module (do not extend)
`app/assets/service.py` (`list_assets`, `get_asset`) and `app/assets/schemas.py` (`AssetResponse`, `AssetSummary`, `AssetFilter`) are **not imported by `router.py`**. `router.py`'s live `GET /assets` (line 94-224) and `GET /assets/{id}` (line 278-378) build **inline SQLAlchemy queries and raw dicts** directly, never calling `service.py` or constructing the Pydantic schemas. `[VERIFIED: grep "list_assets\|AssetResponse\|AssetSummary\|AssetFilter" app/assets/router.py → zero matches for schemas, one unrelated same-name local function for list_assets]`. **Any new exposure-context fields surfaced in API responses must be added to `router.py`'s inline dicts** (both the list-item dict at line ~194 and the detail dict at line ~318), not to the dead `schemas.py`/`service.py` files, unless a future phase revives them.

## Recommended Approach per Success Criterion

### 1. EXPO-01/02 — fields + auto-inference at upsert

Add 3 nullable-with-default columns to `Asset`:

```python
class BusinessCriticality(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class DataSensitivity(str, enum.Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED = "RESTRICTED"

class ExposureFieldSource(str, enum.Enum):
    AUTO = "AUTO"
    ASSET_OVERRIDE = "ASSET_OVERRIDE"
    GROUP_OVERRIDE = "GROUP_OVERRIDE"

# On Asset:
business_criticality: Mapped[str] = mapped_column(String(20), default="MEDIUM", server_default="MEDIUM")
business_criticality_source: Mapped[str] = mapped_column(String(20), default="AUTO", server_default="AUTO")
data_sensitivity: Mapped[str] = mapped_column(String(20), default="INTERNAL", server_default="INTERNAL")
data_sensitivity_source: Mapped[str] = mapped_column(String(20), default="AUTO", server_default="AUTO")
internet_facing: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
internet_facing_source: Mapped[str] = mapped_column(String(20), default="AUTO", server_default="AUTO")
```

Write `app/assets/exposure.py` (new, sibling to `classification.py`) exporting a pure function:

```python
def infer_exposure_context(
    *, tags: list[str] | None, department: str | None, job_title: str | None,
    external_ip: str | None,
) -> tuple[str, str, bool]:
    """Returns (business_criticality, data_sensitivity, internet_facing) — pure, no DB access."""
```

Call it from the same 3 places `classify_asset_from_data` is already called (`sync.py::_upsert_asset`, `jamf_sync.py`, `humaans_sync.py` — Humaans and JAMF are the ones that populate `department`/`job_title`, so inference must be (re-)run there too, not only at the scanner-upsert path, since the scanner sync usually runs *before* MDM/HR enrichment for a newly-seen host). **Only write the inferred value onto the `Asset` row if that field's `*_source == "AUTO"`** — this is the mechanism that makes EXPO-03's "permanently wins" guarantee hold across repeated re-inference. Seed the initial `internet_facing` guess from `"internet-facing" in (asset.tags or [])` per EXPO-02's explicit instruction to seed from (never overwrite) `tags` — this only sets the *initial* auto value; it does not mutate `tags` itself.

### 2. EXPO-03 — per-asset override, permanent precedence

New endpoint `PATCH /assets/{asset_id}/exposure-context` (admin-only, `require_role("admin")`), body `{field: "business_criticality"|"data_sensitivity"|"internet_facing", value: ...}`. Handler:
1. Loads asset (tenant-scoped), reads `old_value = getattr(asset, field)`.
2. Sets `setattr(asset, field, value)` and `setattr(asset, f"{field}_source", "ASSET_OVERRIDE")`.
3. `await audit(db, user, "asset.exposure_override", "asset", str(asset.id), {"field": field, "old": old_value, "new": value})`.
4. `await db.commit()`.

Because auto-inference (§1) only ever writes when `*_source == "AUTO"`, setting the source to `ASSET_OVERRIDE` here is sufficient to make the override permanent against all future re-inference runs — no separate "locked" boolean needed.

### 3. EXPO-04 — asset-group scope + precedence

**Recommendation: model "group" as a tag**, not a new membership entity (see Alternatives Considered). New table:

```python
class AssetGroupExposureOverride(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "asset_group_exposure_overrides"
    __table_args__ = (UniqueConstraint("tenant_id", "tag", "field", name="uq_group_override_tag_field"),)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    tag: Mapped[str] = mapped_column(String(100), nullable=False)   # e.g. "pci", "finance"
    field: Mapped[str] = mapped_column(String(30), nullable=False)  # business_criticality|data_sensitivity|internet_facing
    value: Mapped[str] = mapped_column(String(20), nullable=False)  # stored as string; cast per field on read
```

Group scope = "every asset whose `tags` array contains `tag`". This gets membership for free from the existing GIN-indexed `Asset.tags` (`ix_assets_tags`, `025_add_asset_tags.py`) — no new membership table to keep in sync as tags change.

**Precedence (recommended, needs user confirmation — see Assumptions Log A1):**
```
per-asset override (ASSET_OVERRIDE)  >  group override (any matching tag)  >  auto-inference (AUTO)
```
`recompute_exposure_context(db, tenant_id)` (the full-tenant recompute function, mirroring `compute_risk_scores`) applies this precedence per asset per field:
1. If `asset.<field>_source == "ASSET_OVERRIDE"` → skip (already permanent).
2. Else, look up all `AssetGroupExposureOverride` rows for `tenant_id, field` where `tag` is in `asset.tags` — if exactly one match, apply it and set source `GROUP_OVERRIDE`.
3. If **multiple** group overrides match the same asset+field (asset has 2+ tags each with their own group override) — recommend **most-recently-updated group override wins** (deterministic, uses `updated_at`), flagged `[ASSUMED]` (Assumptions Log A3; alternative is "most restrictive value wins", which the calibration check in §5 would then need to exempt since it's an explicit admin decision, not an auto-classification).
4. Else, run `infer_exposure_context(...)` and set source `AUTO`.

### 4. EXPO-05 — audit every override

Both the per-asset endpoint (§2) and the group-override endpoint (`PATCH /asset-groups/{tag}/exposure-context` or similar) call `app/audit.py::audit()` in the same transaction as the mutation, following the exact `ignore_asset`/`update_asset_owner` pattern (`router.py:381-409`, `:436+`). Required `details` payload per EXPO-05: `{"field": ..., "old": ..., "new": ...}` plus `resource_type="asset"` + `resource_id=str(asset.id)` for per-asset, or `resource_type="asset_group"` + `resource_id=tag` for group-scope. Auto-inference runs (non-admin, background) should **not** write an audit row per individual asset (would flood the audit log on every sync) — recommend audit only once per `recompute_exposure_context` batch run with a summary count, OR only audit admin-initiated overrides and treat AUTO writes as ordinary data (not "override" events) since EXPO-05 says "every exposure-context override" (auto *or* manual) — re-read: **the requirement text explicitly says "auto or manual"**, so this needs a decision — flagged Assumptions Log A4.

### 5. EXPO-06 — calibration check

New function `check_criticality_calibration(db, tenant_id) -> dict` (same shape as `asset_stats`'s risk-distribution aggregate, `router.py:256-263`):
```python
pct_critical = count(business_criticality == "CRITICAL" AND business_criticality_source == "AUTO") / count(all assets)
```
**Only counts `AUTO`-sourced rows** — an admin manually setting many assets to CRITICAL is a deliberate decision, not inflation, and should not trip the cap (Assumptions Log A5). Recommend a cap threshold of **15%** (needs product confirmation — no existing precedent in this codebase for a criticality distribution target; flagged Assumptions Log A6) with two behaviors depending on how strict this needs to be:
- **Soft (flag only):** log a structured warning + surface via a stats endpoint (`GET /assets/exposure-context/calibration`), similar to how `asset_stats` surfaces `risk_distribution` today. Matches "caps OR flags" wording in EXPO-06.
- **Hard (cap):** if inference would push `pct_critical` over the cap, downgrade the newest/lowest-confidence AUTO assignments to HIGH until back under threshold. More invasive; only do this if the "provable against a realistic seed-data fixture" success criterion is read as requiring an enforced cap rather than a visible flag.

Recommend the **soft/flag** approach first (lower risk, matches the "OR" in the requirement, easier to test deterministically), with the hard cap as a fast-follow if product wants stricter guarantees.

**Seed fixture:** extend `app/seed.py`'s existing 20-asset `HOSTNAMES` fixture (`seed.py:49-70`) with realistic `department`/`tags` distributions so the calibration test has non-trivial data to assert against — e.g. tag `"pci"` on payment-adjacent hostnames (`db-prod-*`, `api-prod-*`), department `"Finance"`/`"Executive"`/`"Security"` on a few, `"internet-facing"` tag on `vpn-gateway-01`/`mail-01`/`web-prod-*`. A dedicated test fixture (not necessarily touching `seed.py` itself, which is dev-seed data) in `tests/conftest.py` or a new `tests/test_exposure_calibration.py` helper that programmatically creates N assets (e.g. 100) with a realistic department/tag distribution is the safer, more deterministic choice for a compliance-provable test — recommend **not** modifying `seed.py` (used for live dev-environment seeding) and instead building the calibration fixture directly in the test file, following the exact inline-construction convention already used in `test_assets_tags_and_os_family.py:27-33`.

## Architecture Patterns

### System Architecture Diagram

```
 Scanner sync (Wiz/Qualys/Nessus/Rapid7/Defender/CrowdStrike)
        │  NormalizedVulnerability
        ▼
 sync.py::_upsert_asset()  ──creates/updates──▶  Asset row
        │                                          │  external_ip, tags (unchanged)
        │  calls classify_asset_from_data()        │
        │  calls infer_exposure_context() [NEW] ───┤  only writes if *_source == "AUTO"
        ▼                                          │
 device_category set                               │
                                                     │
 JAMF / Humaans / Intune sync (MDM/HR)  ────────────┤  department, job_title arrive
        │  re-calls infer_exposure_context() [NEW]  │  (may run AFTER scanner sync for a new host)
        ▼                                           │
 Asset.department, mdm_details updated              │
                                                     ▼
 Admin: PATCH /assets/{id}/exposure-context [NEW] ──▶ sets *_source = ASSET_OVERRIDE, audit()
 Admin: PATCH /asset-groups/{tag}/exposure-context [NEW] ─▶ asset_group_exposure_overrides row, audit()
        │
        ▼
 recompute_exposure_context(tenant_id) [NEW, mirrors compute_risk_scores]
   for each asset, for each field:
     ASSET_OVERRIDE → skip
     matching group override(s) → apply (tie-break: most-recent), source=GROUP_OVERRIDE
     else → infer_exposure_context(...), source=AUTO
        │
        ▼
 check_criticality_calibration(tenant_id) [NEW] ──▶ % AUTO+CRITICAL vs cap ──▶ flag/log
        │
        ▼
 Phase 33 risk-exposure model reads Asset.business_criticality/data_sensitivity/internet_facing
```

### Recommended Project Structure
```
backend/app/assets/
├── classification.py         # existing — device_category only, untouched
├── classifier.py              # existing — DEAD CODE, do not extend (flag for cleanup, out of scope)
├── exposure.py                 # NEW — infer_exposure_context(), recompute_exposure_context(),
│                                #        check_criticality_calibration()
├── models.py                   # extend — 6 new columns on Asset + new AssetGroupExposureOverride class
├── router.py                   # extend — new endpoints; extend existing inline dicts (list/detail)
└── ...

backend/alembic/versions/
├── 037_add_exposure_context.py           # new Asset columns
└── 038_add_group_exposure_ovr.py         # new asset_group_exposure_overrides table (≤32-char revision id!)

backend/tests/
└── test_exposure_context.py              # NEW — inference, override precedence, audit, calibration
```

### Pattern 1: Materialized + source-discriminator column (this codebase's own idiom)
**What:** Store the *effective* value directly on the row plus a companion `_source` column recording how it got there, recomputed by an explicit service function — not derived on every read via joins.
**When to use:** Whenever a value has multiple possible origins (auto vs override) and is read far more often than it's written (list/detail pages read `risk_score`/`device_category` on every page load; they are written only on sync or admin action).
**Example:**
```python
# Source: backend/app/assets/risk_score.py:134-139 (existing precedent — full-tenant recompute + persist)
for asset_id, raw_score in rows:
    normalized = _normalize_raw_score(float(raw_score))
    await db.execute(update(Asset).where(Asset.id == asset_id).values(risk_score=normalized))
```

### Pattern 2: Admin-only full-tenant recompute endpoint
**What:** `require_role("admin")` + a bulk recompute function + `db.commit()`.
**When to use:** Any time an inference algorithm changes and existing rows need to be brought current without waiting for the next sync.
**Example:**
```python
# Source: backend/app/assets/router.py:536-546 (existing — POST /assets/recompute-risk-scores)
@router.post("/recompute-risk-scores")
async def recompute_risk_scores(user=Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    stats = await compute_risk_scores(db, user.tenant_id)
    await db.commit()
    return {"message": "Risk scores recomputed", **stats}
```

### Pattern 3: Audit-then-commit, same transaction
**What:** Call `audit()` before `db.commit()` so an audit-write failure rolls back the mutation too.
**Example:**
```python
# Source: backend/app/assets/router.py:404-408 (existing — asset.ignore)
await audit(db, user, "asset.ignore", "asset", str(asset.id), {"hostname": asset.hostname, "reason": asset.ignored_reason})
await db.commit()
```

### Anti-Patterns to Avoid
- **Extending `app/assets/classifier.py`:** it is dead code; any change there ships with zero effect on production behavior. Extend `classification.py` only if truly extending device-category logic (not applicable here).
- **Extending `app/assets/service.py` / `schemas.py`:** dead code, not wired to `router.py`. New exposure-context fields must be added to `router.py`'s inline dicts (list item + detail dict) or they will silently not appear in API responses despite being on the ORM model.
- **A real M2M `AssetGroup`/`AssetGroupMember` table** unless the user explicitly wants persisted, admin-managed groups independent of tags — adds a membership-management surface (CRUD for group members) this phase's requirements don't ask for. Confirm with user before building (Assumptions Log A1).
- **Auditing every AUTO-sourced field write individually:** would flood `audit_logs` on every scanner sync (thousands of assets × 3 fields). Batch-summarize AUTO recompute audit entries, or exempt AUTO writes from EXPO-05's audit requirement — needs a product decision (Assumptions Log A4).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Audit trail for overrides | A new audit table/model | `app/audit.py::audit()` (existing `AuditLog`) | Already fail-closed, already syslog-forwarding, already tenant-scoped |
| Admin-only route guard | A new role-check decorator | `app/auth/dependencies.py::require_role("admin")` (existing) | Already used identically for `/assets/classify` and `/assets/recompute-risk-scores` |
| Tag containment query | Raw SQL `LIKE` over a stringified array | `Asset.tags.contains([tag])` / the existing GIN index `ix_assets_tags` | Already the pattern used in `router.py:127` (`Asset.seen_by_sources.contains([s])`) and by the tags migration itself |
| Enum-like string columns | Postgres native `ENUM` type | Python `str, enum.Enum` + plain `String` column | Matches `DeviceCategory`, `MisconfigSeverity`, `MisconfigCategory` — avoids `ALTER TYPE` migration pain when adding a tier later |

**Key insight:** every piece of this phase has a near-identical, already-shipped precedent somewhere in `app/assets/` or `app/audit.py` — the risk in this phase is not "what pattern to invent" but "don't accidentally build on top of the two pieces of dead code (`classifier.py`, `service.py`/`schemas.py`) that look live but aren't."

## Common Pitfalls

### Pitfall 1: "Scanner internet-facing flags" — the named data source does not exist
**What goes wrong:** A plan or task assumes some connector (Wiz, Qualys, Nessus, Rapid7, Defender) already emits a public/internet-facing boolean and just needs "reading," then discovers mid-implementation that no such field exists anywhere in the ingestion pipeline.
**Why it happens:** EXPO-02's wording ("scanner internet-facing flags") reads as if this is existing, available data.
**How to avoid:** Verified by grep across all 6 connector files (`internet\|public\|exposure\|is_dmz\|dmz`) — the only hits are `defender.py`'s `publicExploit` (an *exploit-availability* flag, unrelated to asset network exposure) and `crowdstrike.py`'s `external_ip` (a real IP-presence signal, but only from one connector). Recommend inference use `external_ip IS NOT NULL` OR `"internet-facing" in tags` as the v1 signal, and flag to the user/discuss-phase that a "real" per-scanner internet-facing flag is future work (possibly Wiz CSPM network misconfiguration correlation — see Open Questions).
**Warning signs:** A task description like "read the internet-facing flag from the Wiz/Qualys connector" without a specific field name — there isn't one to read.

### Pitfall 2: Ingestion order — MDM/HR enrichment can arrive after the first scanner upsert
**What goes wrong:** Inferring exposure-context only inside `sync.py::_upsert_asset` misses `department`/`job_title` for any asset whose *first-ever* sighting is from a scanner (Wiz/Qualys/etc.) before JAMF/Humaans/Intune has ever run — the asset gets `business_criticality=MEDIUM` (default) baked in with `source=AUTO` and correctly-informed re-inference never happens because nothing re-triggers it.
**Why it happens:** `classify_asset_from_data` (device category) already re-runs on every sync touching an asset (`sync.py:266-267`, `jamf_sync.py`), so this pattern already exists for device-category but must be **deliberately copied** for exposure-context — it will not happen "for free."
**How to avoid:** Call `infer_exposure_context()` (only for `AUTO`-sourced fields) from every enrichment path that could change an input signal: `sync.py::_upsert_asset`, `jamf_sync.py`, `humaans_sync.py`, `intune_sync.py` (once department/similar is added there, per Assumptions Log A2). Also expose the admin recompute-all endpoint (§5's `recompute_exposure_context`) as a manual trigger, same as `/assets/classify` and `/assets/recompute-risk-scores`.
**Warning signs:** A test seeding an asset via `Asset(...)` directly (bypassing `_upsert_asset`) and asserting on inferred criticality without also calling the inference function — the test would be testing the pure function, not the integration, which is fine but must not be mistaken for integration coverage.

### Pitfall 3: Alembic revision id length limit (32 chars, `alembic_version.version_num`)
**What goes wrong:** A migration named e.g. `038_add_asset_group_exposure_overrides` (39 chars) raises `StringDataRightTruncationError` at `alembic upgrade head` — this has already happened once in this codebase (`031_rename_audit_tenant_idx.py`'s docstring documents the exact incident).
**How to avoid:** Count characters before naming the revision string; keep both the filename prefix and the `revision = "..."` value ≤ 32 chars, e.g. `"038_add_group_exposure_ovr"` (27 chars).

### Pitfall 4: Dead-code traps (`classifier.py`, `service.py`, `schemas.py`)
**What goes wrong:** A plan/task edits `app/assets/service.py::get_asset` or `app/assets/schemas.py::AssetResponse` to add the 3 new fields, ships it, and the fields never appear in the actual `GET /assets/{id}` response because that endpoint (`router.py:278-378`) builds its own dict and never touches those files.
**Why it happens:** `service.py`/`schemas.py` look like the "correct," idiomatic place for this (well-typed Pydantic response model, clean function) — but they were superseded by inline dict construction in `router.py` at some point (likely Phase 12's fold-in, per the comment at `router.py:311-316`) and never deleted.
**How to avoid:** Grep `router.py` for actual usage before assuming a file in `app/assets/` is live. Add new fields to the list-item dict (~line 194-217) and the detail dict (~line 318-378) directly.
**Warning signs:** A test asserting on `AssetResponse(...)` construction in isolation, rather than hitting the actual `GET /assets/{id}` HTTP endpoint and asserting on the JSON body.

### Pitfall 5: Group-override precedence conflicts silently picking an unintended tag
**What goes wrong:** An asset has both `"pci"` (mapped to a group override forcing `data_sensitivity=RESTRICTED`) and `"dev"` tags (mapped to a group override forcing `data_sensitivity=PUBLIC`) — whichever tie-break rule is chosen (most-recent-update, alphabetical, etc.) silently picks one, and there's no per-asset visibility into *why* without inspecting the `asset_group_exposure_overrides` table directly.
**How to avoid:** Store which tag "won" somewhere inspectable — e.g. `internet_facing_source = "GROUP_OVERRIDE"` isn't enough; consider a richer source value like `f"GROUP_OVERRIDE:{winning_tag}"` or a separate `*_source_detail` column, so an admin (and EXPO-05's audit trail, if AUTO/GROUP writes are audited) can see which group override actually applied. Confirm with user during planning (Assumptions Log A3).

## Code Examples

### Existing upsert integration point (extend, don't replace)
```python
# Source: backend/app/connectors/sync.py:209-301 (_upsert_asset, existing)
device_category = classify_asset_from_data(
    hostname=hostname, os_name=v.os_name or "", platform_name=platform_name, product_type_desc=product_type_desc,
)
# NEW: mirror this call for exposure-context, gated on *_source == "AUTO" inside the function itself
# (so calling it repeatedly on every sync is always safe / idempotent for overridden fields)
```

### Existing audit-then-commit pattern to copy exactly
```python
# Source: backend/app/assets/router.py:436-470-ish (update_asset_owner, existing)
from app.audit import audit
old_value = asset.assigned_user
asset.assigned_user = body.assigned_user_email
await audit(db, user, "asset.owner_changed", "asset", str(asset.id), {"from": old_value, "to": body.assigned_user_email, "hostname": asset.hostname})
await db.commit()
```

### Existing full-tenant recompute pattern to copy exactly
```python
# Source: backend/app/assets/risk_score.py:84-147 (compute_risk_scores, existing)
async def compute_risk_scores(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    ...
    for asset_id, raw_score in rows:
        normalized = _normalize_raw_score(float(raw_score))
        await db.execute(update(Asset).where(Asset.id == asset_id).values(risk_score=normalized))
    return {"assets_updated": updated}
```

### Existing tag-containment query to copy exactly
```python
# Source: backend/app/assets/router.py:127 (existing, for a different filter — same idiom applies to group override matching)
query = query.where(Asset.seen_by_sources.contains([s]))
# For group-override matching: Asset.tags.contains([tag]) per matching AssetGroupExposureOverride.tag
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| N/A — greenfield within this codebase | N/A | — | This is new functionality, not a migration off an old approach |

**Deprecated/outdated:** N/A for this phase's own scope. Noted in passing: `app/assets/classifier.py` and `app/assets/service.py`/`schemas.py` are effectively deprecated-by-omission (dead code) — out of scope to delete in this phase, but worth flagging to the user as a cleanup candidate for a future backlog item.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | "Asset-group" should be modeled as a tag-scoped override (reusing `Asset.tags`) rather than a first-class `AssetGroup`/`AssetGroupMember` M2M entity | Recommended Approach §3, Alternatives Considered | If the user actually wants persisted, named, admin-managed groups independent of tags (e.g. groups that aren't 1:1 with a single tag, or groups an admin can rename without changing every member's tags), this design needs a real entity + membership table instead — bigger migration, bigger scope |
| A2 | Intune sync (`app/connectors/intune_sync.py`) does not currently set `Asset.department` (only JAMF and Humaans do) | Existing-Code Findings — Enrichment sources table | If Intune actually does set `department` via a code path not grepped, the inference function's input assumptions for Intune-managed devices are wrong — low risk, easy to verify by reading `intune_sync.py` fully during planning |
| A3 | Tie-break for conflicting group overrides on the same asset+field = "most-recently-updated group override wins" | Recommended Approach §3, Pitfall 5 | Wrong tie-break rule silently applies an unintended criticality/sensitivity value to real assets; alternative "most restrictive wins" has different security implications (safer default, but conflicts with calibration-cap intent per A5) |
| A4 | EXPO-05 ("every override, auto or manual, is audit-logged") should be satisfied by batch-summarizing AUTO-sourced writes (one audit row per full-tenant recompute run) rather than one row per asset per field | Recommended Approach §4 | If a strict per-row-per-field audit trail is actually required even for AUTO writes, the audit_logs table will grow by (assets × 3 fields) per sync — needs volume/retention consideration before locking the design |
| A5 | The calibration check (EXPO-06) should only count `AUTO`-sourced CRITICAL assignments, exempting admin `ASSET_OVERRIDE`/`GROUP_OVERRIDE` values from the cap | Recommended Approach §5 | If the requirement actually means "cap the total proportion of CRITICAL assets regardless of source," admin overrides could be silently downgraded or blocked, which would defeat EXPO-03's "override permanently wins" guarantee — these two requirements are in tension if calibration includes overrides |
| A6 | Recommended calibration cap threshold = 15% of assets at CRITICAL | Recommended Approach §5 | No existing precedent in this codebase for a target criticality distribution; wrong threshold either false-flags a legitimately high-criticality fleet (e.g. an all-financial-services tenant) or fails to catch real inflation |
| A7 | `internet_facing` v1 signal = `external_ip IS NOT NULL` OR `"internet-facing" in tags`, with no per-scanner real signal (Pitfall 1) | Recommended Approach §1, Pitfall 1 | If a real internet-facing signal is later found in one of the 6 connectors' raw API payloads (not currently mapped into `NormalizedVulnerability`/`Asset`), this v1 approach under-detects internet-facing assets until that mapping is added |

**If this table is empty:** N/A — table is populated; every item above needs explicit confirmation before the planner locks tasks around it.

## Open Questions (RESOLVED — see 32-CONTEXT.md, 2026-08-10)

> **Q1 RESOLVED:** real per-connector internet-facing detection is IN scope (CONTEXT [USER] decision) — Plan 04 adds real extraction where vendor payloads support it, with the `external_ip`/tag proxy as fallback and an honest coverage table.
> **Q2 RESOLVED:** IdP-directory signals are DEFERRED for v1 — inference uses MDM/HR only (see CONTEXT "IdP-directory signals are DEFERRED"). Documented future work, not a silent drop.
> **Q3 RESOLVED:** a real first-class `AssetGroup` entity is IN scope (CONTEXT [USER] decision) — Plan 03 builds it (not tag-scoped).

1. **Does a real internet-facing signal exist in any connector's raw payload that simply isn't mapped into `NormalizedVulnerability` yet?**
   - What we know: none of the 6 connectors' Python code maps such a field into the `Asset`/`NormalizedVulnerability` shape today (Pitfall 1).
   - What's unclear: whether Wiz's or Qualys's raw API response (not yet inspected at the wire-protocol level, only the already-mapped Python code) includes a public-IP/internet-exposure field that could be added to `NormalizedVulnerability` as a genuinely new mapped field — that would be a `connectors/` change, likely out of Phase 32's scope (which is asset-model + inference, not connector rewrites — Phase 31 already closed connector enrichment).
   - Recommendation: treat as out of scope for Phase 32 v1; use `external_ip`/tags proxy; revisit in a future connector-enrichment phase if the proxy proves insufficient.

2. **Should IdP-sourced signals (Azure Entra / Google Workspace / Okta groups, via `app.tenants.models.User`) feed auto-inference, given they currently only join to `Asset` at *read time* (`router.py::_get_directory_user`) and not at upsert?**
   - What we know: `User.department`/`User.job_title`/`User.groups` exist and are IdP-sourced; the join to `Asset` happens via email matching only inside the `GET /assets/{id}` handler, not during any sync/upsert path.
   - What's unclear: whether replicating that email-matching join inside `infer_exposure_context` (which would need DB access, making it no longer a pure function) is worth the complexity given JAMF/Humaans `department` already covers the same signal for MDM/HR-managed devices.
   - Recommendation: skip IdP-User join for v1 inference; rely on `Asset.department` (JAMF/Humaans) only. Revisit if `Asset.department` proves sparse in practice.

3. **Is a real `AssetGroup` entity (vs. tag-scoped groups) actually wanted, i.e. did the product decision "asset-group scope" in STATE.md mean something more structured than "matches this tag"?**
   - What we know: no existing group entity in the codebase to reconcile against; "asset-group" language in STATE.md/REQUIREMENTS.md doesn't specify implementation.
   - What's unclear: whether a future phase (e.g. Phase 35 Source-Aware Filtering) expects a first-class group resource with its own name/id independent of tags.
   - Recommendation: confirm with user at `/gsd-discuss-phase 32` before planning locks in the tag-scoped design (Assumptions Log A1).

## Environment Availability

No new external dependencies — this phase is pure application code (SQLAlchemy models, Alembic migration, FastAPI endpoints) against the already-running Postgres instance. Skipping the full environment probe table since nothing new is introduced; the existing backend dev environment (confirmed working per project memory: `ENCRYPTION_KEY`/`JWT_SECRET_KEY` env vars required for tests, `backend/.venv` dependencies) is sufficient.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3 + pytest-asyncio 0.24 (`asyncio_mode = "auto"`) |
| Config file | `backend/pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `cd backend && ENCRYPTION_KEY=<fernet-key> JWT_SECRET_KEY=<secret> .venv/bin/pytest tests/test_exposure_context.py -x` |
| Full suite command | `cd backend && ENCRYPTION_KEY=<fernet-key> JWT_SECRET_KEY=<secret> .venv/bin/pytest tests/ ` (per project memory: run per-file, not whole `tests/` dir, to avoid false failures from cross-file state) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EXPO-01 | New asset carries all 3 fields with sane defaults after upsert | unit/integration | `pytest tests/test_exposure_context.py::test_upsert_sets_default_exposure_fields -x` | ❌ Wave 0 |
| EXPO-02 | Auto-inference reads department/tags/external_ip, seeds from tags without mutating tags | unit | `pytest tests/test_exposure_context.py::test_infer_exposure_context_seeds_from_tags -x` | ❌ Wave 0 |
| EXPO-02 | Re-inference after MDM/HR enrichment does not clobber an already-overridden field | integration | `pytest tests/test_exposure_context.py::test_reinference_skips_overridden_field -x` | ❌ Wave 0 |
| EXPO-03 | Admin PATCH sets field + source=ASSET_OVERRIDE; permanently survives recompute | integration | `pytest tests/test_exposure_context.py::test_asset_override_wins_over_reinference -x` | ❌ Wave 0 |
| EXPO-03 | Non-admin gets 403 on override endpoint | integration (RBAC) | `pytest tests/test_exposure_context.py::test_override_requires_admin_role -x` | ❌ Wave 0 |
| EXPO-04 | Group (tag) override applies to all matching assets without per-asset override | integration | `pytest tests/test_exposure_context.py::test_group_override_applies_to_tagged_assets -x` | ❌ Wave 0 |
| EXPO-04 | Per-asset override wins over a group override on the same field | integration | `pytest tests/test_exposure_context.py::test_asset_override_beats_group_override -x` | ❌ Wave 0 |
| EXPO-04 | Conflicting group overrides (2 tags) resolve deterministically | integration | `pytest tests/test_exposure_context.py::test_conflicting_group_overrides_tiebreak -x` | ❌ Wave 0 |
| EXPO-05 | Per-asset override writes exactly one audit row with actor/asset/field/old/new | integration | `pytest tests/test_exposure_context.py::test_asset_override_writes_audit_row -x` | ❌ Wave 0 |
| EXPO-05 | Group override writes exactly one audit row with actor/group(tag)/field/old/new | integration | `pytest tests/test_exposure_context.py::test_group_override_writes_audit_row -x` | ❌ Wave 0 |
| EXPO-06 | Realistic 100-asset fixture with skewed department/tags stays under (or correctly flags over) the calibration cap | integration | `pytest tests/test_exposure_context.py::test_calibration_check_against_realistic_fixture -x` | ❌ Wave 0 |
| EXPO-06 | Admin-set CRITICAL overrides are exempt from the calibration cap | integration | `pytest tests/test_exposure_context.py::test_calibration_exempts_manual_overrides -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_exposure_context.py -x` (single file, per project memory's per-file convention)
- **Per wave merge:** full `tests/` suite run file-by-file (existing project convention — never `pytest tests/` as one invocation)
- **Phase gate:** Full suite green before `/gsd-verify-work 32`

### Wave 0 Gaps
- [ ] `tests/test_exposure_context.py` — new file, covers all of EXPO-01..06 (table above)
- [ ] Realistic 100-asset seed-data helper for the calibration test (inline in the test file, following `test_assets_tags_and_os_family.py`'s convention — NOT a modification to `app/seed.py`, which is live dev-environment seed data)
- [ ] Framework install: none — pytest/pytest-asyncio already present

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | no | Not touched by this phase (uses existing `get_current_user`) |
| V3 Session Management | no | Not touched |
| V4 Access Control | yes | `require_role("admin")` on both override endpoints (per-asset and group), mirroring `/assets/classify`/`/assets/recompute-risk-scores` — mutating exposure-context is a privileged action per EXPO-03/04's "an admin can" wording |
| V5 Input Validation | yes | New field values must be validated against the `BusinessCriticality`/`DataSensitivity` enums (reject unknown strings with 422) via a Pydantic body model with `field_validator`, mirroring `_AssetOwnerUpdate`'s pattern (`router.py:30-46`, `extra="forbid"`) |
| V6 Cryptography | no | No new secrets/crypto surface introduced |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| Cross-tenant override (attacker with a valid session in tenant A sets exposure-context on a tenant B asset by guessing its UUID) | Elevation of Privilege / Tampering | Every override query must filter `Asset.tenant_id == user.tenant_id` before mutating — mirrors the existing `update_asset_owner`/`ignore_asset` pattern; return 404 (not 403) on cross-tenant probe to avoid confirming existence, per the existing convention documented in `test_asset_owner_reassign.py:7` ("404 (NOT 403) on cross-tenant probe — existence hidden") |
| Privilege escalation via non-admin hitting the override endpoint directly | Elevation of Privilege | `require_role("admin")` dependency, tested explicitly (see Validation Architecture `test_override_requires_admin_role`) |
| Mass-assignment on the override body (extra fields reaching the ORM) | Tampering | Pydantic body model with `model_config = {"extra": "forbid"}`, mirroring `_AssetOwnerUpdate` |
| Audit-log tampering / silent-drop on override (mutation succeeds, audit row doesn't) | Repudiation | Reuse `app/audit.py::audit()`'s existing fail-closed semantics (exception propagates, `db.commit()` never runs) — do not write a bespoke audit call that swallows exceptions |
| Calibration-cap bypass via mass individual overrides instead of group override (admin scripts 1000 individual PATCH calls to set CRITICAL, evading a hypothetical "cap applies to AUTO only" rule) | Tampering (of the calibration signal itself) | Out of scope to defend against in Phase 32 — admin role is already a trust boundary; if this becomes a real concern, calibration reporting should still surface total-CRITICAL-including-overrides as a separate, non-blocking metric so drift is visible even if not capped |

## Sources

### Primary (HIGH confidence — direct codebase reads this session)
- `backend/app/assets/classification.py`, `backend/app/assets/classifier.py` — full read, confirms dead code
- `backend/app/assets/models.py` — full read, current `Asset` schema
- `backend/app/assets/service.py`, `backend/app/assets/schemas.py` — full read, confirms dead code
- `backend/app/assets/risk_score.py` — full read, recompute-pattern precedent
- `backend/app/assets/router.py` — read lines 1-90, 90-260, 260-400, 400-460, 530-565 — confirms live endpoint shapes, dead-code non-usage, `require_role`/`audit` patterns
- `backend/app/audit.py` — full read
- `backend/app/auth/dependencies.py` (lines 100-141) — `require_role` implementation
- `backend/app/connectors/sync.py` (`_upsert_asset`, lines 209-301) — the real ingestion upsert path
- `backend/app/connectors/jamf_sync.py`, `humaans_sync.py`, `humaans.py`, `intune_sync.py`, `directory_sync.py` — enrichment source mapping
- `backend/app/cspm/models.py` — full read, confirms no internet-facing/public flag
- `backend/app/tenants/models.py` (User model, lines 19-58) — confirms `User` ≠ `Asset`-linked directly
- `backend/app/enrich_assets.py` — full read, confirms standalone script, not scheduler-integrated
- `backend/alembic/versions/025_add_asset_tags.py`, `036_add_enrichment_ref_tables.py` — migration conventions, 32-char revision limit
- `backend/tests/test_assets_tags_and_os_family.py`, `test_asset_owner_reassign.py` — existing test conventions to mirror
- `backend/tests/conftest.py` (fixture list grep) — `db_session`, `tenant_a`, `admin_user`, `client` fixtures confirmed available
- `backend/app/seed.py` (lines 1-150) — existing dev-seed fixture shape
- `backend/pyproject.toml` — pytest/ruff/mypy config confirmed
- `grep -rn` across `backend/app/connectors/*.py` for `internet|public|exposure|is_dmz|dmz|criticality|sensitivity` — confirms no existing internet-facing/criticality signal in any connector
- `.planning/REQUIREMENTS.md` (lines 31-37, 102-107) — EXPO-01..06 exact wording
- `.planning/STATE.md` — v4.0 phase map, locked decisions, hard constraints

### Secondary (MEDIUM confidence)
- None — all findings this session were direct codebase reads (primary), not web-search-derived, since this phase is entirely internal to the existing GetVul codebase with zero new third-party dependencies.

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — zero new dependencies, 100% reuse of already-installed/pinned tooling
- Architecture: HIGH for patterns-to-reuse (directly cited file:line precedents); MEDIUM for the group-override design (genuinely new, no precedent to verify against — flagged in Assumptions Log)
- Pitfalls: HIGH — dead-code findings and the 32-char revision-id limit are directly verified; the "no internet-facing scanner flag exists" finding is HIGH confidence (exhaustive grep) but its *implication* (what to do instead) is a recommendation, not a verified fact

**Research date:** 2026-08-10
**Valid until:** 30 days (stable, internal-codebase-only research; no external library version drift risk)
