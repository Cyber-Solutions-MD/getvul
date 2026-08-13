# Phase 32 Context — Asset Exposure Context

**Source:** inline discuss during "complete v4.0" (2026-08-10). Locks the 7 research assumptions.

## Domain

Every asset carries an accurate, admin-overridable exposure-context profile (business-criticality,
data-sensitivity, internet-facing) auto-inferred at upsert, ready to feed the Phase 33 risk-exposure
model. Reconcile with existing code: `classification.py`/`classifier.py` classify only
`device_category` (and `classifier.py` is dead code) — exposure context is a NEW module
(`app/assets/exposure.py`), not an extension. `app/assets/service.py`/`schemas.py` are dead — live
responses are built inline in `assets/router.py`, so new fields must be added there or they won't surface.

## Locked decisions

- **[USER] Internet-facing = real detection (not a proxy).** Add real internet-facing extraction to
  the connectors/data sources that expose it, rather than only `external_ip`/tag proxying. Where a
  vendor genuinely provides no signal, fall back to `external_ip IS NOT NULL` OR an `internet-facing`
  tag, but the phase must add real per-connector detection wherever the vendor payload supports it
  (e.g. public-exposure / shodan-style / cloud public-IP / security-group signals). Admin override
  always wins. Document per-connector coverage honestly.
- **[USER] Asset-group scope = a real `AssetGroup` entity.** Build a first-class AssetGroup
  (group model + membership + admin CRUD APIs + management UI + migration), tenant-scoped. Group-scope
  overrides target a group, not a tag.
- **[DEFAULT] Override precedence:** per-asset override > group override > auto-inference. A per-asset
  override on a field permanently wins over any future auto re-run (EXPO-02/03). Conflicting overrides
  from multiple groups on the same field → **most-recently-updated group override wins** (deterministic,
  tested). This precedence must be unit-tested (EXPO-04 criterion #3).
- **[DEFAULT] Auto-inference seeds from — never overwrites — existing `Asset.tags`** and existing
  **MDM (Jamf/Intune) + HR (Humaans, department/job_title)** enrichment plus scanner flags. An existing
  manual override or a set tag value is never clobbered by a re-run.
- **[RESOLVED post-plan-check 2026-08-10] IdP-directory signals are DEFERRED for Phase 32 v1.** EXPO-02's
  "MDM/HR/IdP" wording is narrowed to **MDM/HR** for v1: a live join to IdP directory data
  (Entra/Okta/Google `User.department`/groups) is NOT wired into inference — it breaks the pure-inference
  function and needs a DB join for low marginal value (per RESEARCH Open Question 2). Documented future
  work, not a silent drop. HR-sourced department/job_title (already on the asset) still feed inference.
- **[DEFAULT] Audit (EXPO-05):** every exposure-context field change is audit-logged with actor,
  asset/group, field, old value, new value, reusing the existing `app/audit.py` audit()-then-commit
  pattern. Manual overrides → actor = the admin user. Auto-inference → actor = `system:exposure-inference`,
  logged **only when a value actually changes** (never re-affirmations) to avoid flooding the audit log
  on bulk re-runs.
- **[DEFAULT] Calibration check (EXPO-06):** measures the proportion of assets **auto-classified** at
  the highest criticality tier (admin/group overrides are exempt — the criterion is about auto
  inflation, and exempting them resolves the tension with EXPO-03's "override permanently wins").
  Default behavior = **flag + calibration report** (emit a warning + a report row when the auto
  highest-tier proportion exceeds the cap); a hard-cap mode is configurable but **off by default**
  (silently down-ranking a genuinely critical asset is worse than flagging). Default threshold **15%**,
  tenant-configurable. Provable against a realistic seed-data fixture.
- **[DEFAULT] Migration:** new columns on `assets` (criticality, data_sensitivity, internet_facing +
  per-field source discriminator auto/manual, mirroring how `risk_score`/`device_category` work) +
  `asset_groups` + membership + an exposure-override record. Alembic revision id ≤ 32 chars
  (`alembic_version.version_num` is varchar(32)); latest head = `036_add_enrichment_ref_tables`.
- **[DEFAULT] Admin-only recompute endpoint** for full-tenant re-inference, mirroring the existing
  `POST /assets/classify` / `POST /assets/recompute-risk-scores` precedent.

## Constraints (v4.0-wide)

Single-VM Docker Compose + in-process asyncio scheduler only (no new infra); every query tenant_id-scoped;
audit events for all new mutating actions; encrypted connector creds must keep decrypting.

## UI

Phase has a UI surface (asset exposure fields + override controls + AssetGroup management). Follow the
`sketch-findings-getvul` design system (sunset tokens, state patterns, copy voice). Admin-only controls
gated in UI (backend enforces independently).

## Execution notes (from plan-check, 2026-08-10)

- **System audit actor:** `app/audit.py::audit()` derives the actor from a `CurrentUser` and cannot emit a
  literal `system:*` actor. For auto-inference audit rows use a **direct `AuditLog(...)` construction**
  (precedent: `app/encryption.py:256-276` `user_email="system:cli"`; `app/ai/audit.py` `system:scheduler`)
  with `user_email="system:exposure-inference"`, still audit-then-commit, logged only when a value changes.
- **Group membership re-applies precedence:** `add_member`/`remove_member` (Plan 03) MUST re-apply the
  per-asset > group > auto precedence to the affected asset immediately (mirror the group-override-PATCH
  handler), so a newly-added member picks up the group override without waiting for a full recompute. Add a
  test for the add-member-after-override ordering.
- **Migration filenames:** trust each PLAN.md's migration ids (chain from `036`, ≤32 chars); 32-PATTERNS.md's
  example filenames are illustrative and may be off-by-one — PLAN.md is authoritative.

## Scope note (honest)

The two [USER] choices (real internet-facing detection + a real AssetGroup entity) deliberately expand
Phase 32 beyond the minimal path. This is accepted. Internet-facing detection coverage will vary by
vendor — document which connectors get a real signal vs. the external_ip/tag fallback.
