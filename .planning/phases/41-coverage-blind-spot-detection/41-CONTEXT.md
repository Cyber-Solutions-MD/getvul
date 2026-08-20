# Phase 41: Coverage & Blind-Spot Detection - Context

**Gathered:** 2026-08-20
**Status:** Ready for planning

<domain>
## Phase Boundary

GetVul tells a tenant **what it doesn't know** — devices the authoritative inventory knows about but **no scanner has ever touched** — instead of only reporting on what scanners already found. Three deliverables (COV-01..03):

1. **COV-01 — reconciliation view:** reconcile the authoritative device inventory against scanner-seen assets and list assets **never touched by any scanner**.
2. **COV-02 — per-connector coverage:** per-scanner coverage % against the authoritative baseline, plus **stale-source gaps** (a connector that hasn't reported in N days).
3. **COV-03 — route to owner:** a newly-discovered unmanaged asset can be routed to an owner directly from the coverage view.

This is a **how-to-implement** boundary — no new capabilities beyond COV-01..03. This phase is **mostly a read-side reconciliation over data GetVul already has** (`assets.seen_by_sources` + `ConnectorConfig` sync-health + directory owner resolution), not new ingestion plumbing.

**Explicitly NOT this phase:**
- A new **CMDB connector** (ServiceNow/CSV import). COV-01 names "CMDB" but no CMDB connector exists — deferred (see Deferred Ideas). Do NOT build one here.
- An **IdP user→device inference** (deriving "expected devices" from IdP users). IdP `directory_sync` creates **users**, not asset rows — out of scope.
- Precomputed/materialized coverage rollups, tenant-configurable stale thresholds, per-connector-interval-derived staleness — all deferred (see decisions D-06, D-05).
- Re-deriving enrichment/scanner data or the v4.0 risk model (consume, never re-derive).
- Trend analytics (Phase 42), executive reporting (Phase 43).

</domain>

<decisions>
## Implementation Decisions

### COV-01 — Authoritative baseline & blind-spot definition
- **D-01:** **Authoritative inventory = MDM+HR asset rows only.** The baseline is every asset whose `seen_by_sources` contains an ENRICHMENT source (`JAMF` / `HUMAANS` / `INTUNE`, per `app/assets/constants.py::ENRICHMENT_SOURCES`). Honest to what actually produces device inventory today. IdP (users, not devices) and CMDB (absent) are documented as a deferred gap, not silently implied. No new connector work.
- **D-02:** **A blind spot = zero scanner sources.** An asset is a coverage blind spot when it is in the authoritative baseline (D-01) but its `seen_by_sources` contains **no** `SCANNER_SOURCES` value (the 6-value `VulnSource` enum) — i.e. never touched by any vuln scanner. This is Success-Criterion-1's "zero findings / never scanned"; for a never-scanned asset the zero-findings and null-`last_seen_at` conditions are subsumed by the no-scanner-source signal. Asset-level staleness (scanner-seen but gone quiet) is deliberately kept out of the blind-spot list and handled at the connector level in COV-02 (D-05), keeping asset-level vs source-level signals cleanly separated.

### COV-01 — View placement & layout
- **D-03:** **New top-level "Coverage" nav page** (sidebar entry alongside Vulnerabilities / Assets / Campaigns), not a tab under Assets. Blind-spot detection is a distinct analyst workflow; matches ROADMAP "coverage view" + "UI hint: yes".
- **D-04:** **Layout = per-connector coverage strip on top + unmanaged/never-scanned asset list below.** Top strip renders COV-02 (coverage % + stale badges) reusing `StatStrip` / `SyncStatusPill` / `ConnectorMark`. Below, the blind-spot asset list reuses the Assets **chip-bar + list + `DrillPanel`** primitives, with the route-to-owner action (D-07) per row. The two are read together (see the gap %, then the assets behind it).

### COV-02 — Coverage % & staleness
- **D-05:** **Per-scanner coverage % of the authoritative baseline.** For each scanner connector: `coverage% = (authoritative assets whose seen_by_sources includes that scanner) / (total authoritative MDM+HR assets)`. Answers "what fraction of my known devices does each scanner actually cover." Chosen over a single overall-scanned % (loses the per-connector breakdown COV-02 requires) and over both (unneeded now).
- **D-06:** **Stale-source threshold = fixed default 7 days.** A connector whose `ConnectorConfig.last_sync_at` is older than 7 days is flagged stale. Reads existing sync-health columns directly (`ConnectorConfig.last_sync_at`, `last_sync_status`, `consecutive_failure_count`). Tenant-configurable and per-connector-interval-derived staleness were both rejected as over-engineering for this phase (can be added later without rework). — **Reversibility:** reversible — a single constant in the coverage service.

### COV-03 — Owner-routing action
- **D-07:** **Route-to-owner = assign/confirm owner + notify-owner email.** A never-scanned asset has no findings, so there is nothing to ticket in the normal vuln flow. The action resolves the owner (reusing the `get_directory_user` precedence that ALERT-01/digests already use in `app/notifications/`), and sends a notify-owner email ("this device is in inventory but no scanner covers it — please onboard it"). **No synthetic finding and no fake vuln-linked ticket** (would bend `Ticket.vulnerability_id`'s NOT-NULL FK). Chosen over create-a-coverage-ticket and assign-owner-only.
  - **Open for research (do NOT re-ask user):** the `assets` table has **no dedicated `owner` column** — owner is *resolved* via `get_directory_user` precedence; `assigned_user` (String) exists as raw MDM data. Whether "assign owner" persists an explicit owner override (new column/field) or simply confirms + notifies the resolved owner is a planner/researcher call. Prefer the lightest path that satisfies "route to an owner"; flag if an override column is genuinely needed.
- **D-08:** **Route-to-owner is audited (fail-closed `audit()`) + RBAC-gated to write roles (analyst+).** Consistent with every other v5.0 mutation (exceptions, campaigns, alerting-config). Viewer cannot invoke it.
- **D-09:** **Unresolvable-owner fallback = notify admins + the tenant alert channel.** When no directory owner resolves for an unmanaged asset, fall back to tenant OWNER/ADMIN users + the tenant alert channel so the riskiest shadow-IT asset is never silently dropped. Mirrors Phase 40 **D-10** owner-resolution fallback. Rejected: blocking the action, or a manual owner-entry UI (adds entry/validation surface not warranted this phase).

### Compute & data integrity
- **D-10:** **Compute live on-read.** The reconciliation (blind-spot list + per-scanner coverage % + staleness) is computed per request from `seen_by_sources` + `ConnectorConfig` each time the Coverage view loads. `seen_by_sources` is GIN-filterable and asset counts are tenant-bounded, so this is fine at expected scale. No new job, table, backfill, or staleness of the numbers. A precomputed/materialized rollup (like the v4.0 risk-exposure shadow) was rejected as over-engineered for this phase. — **Reversibility:** reversible — pure read-side service; can be materialized later if scale demands.
- **D-11:** **No-inventory guided empty state.** When a tenant has **no MDM/HR (authoritative) connector configured**, the Coverage view shows a canonical `EmptyState` — "Connect an inventory source (Jamf / Intune / Humaans) to detect coverage gaps" with a link to `/connectors` — rather than a misleading 0%/100%. Mandatory state-pattern per project rules; do NOT fall back to a total-assets denominator (would imply full coverage when the real inventory is simply unknown).
- **D-12:** **Trust `seen_by_sources`; treat empty scanner-sources as unscanned.** `seen_by_sources` is the source of truth (scanner syncs reliably append it in `app/connectors/sync.py`; MDM/HR syncs append their source). An authoritative asset with no scanner source in `seen_by_sources` = a blind spot (exactly the signal wanted). Add a **one-time verify check during research** (spot-check historical rows), but **no backfill migration** unless research finds a real gap. Backfill-recompute-from-vuln-rows was rejected as likely-unnecessary migration risk.

### Claude's Discretion
- Exact empty-state / blind-spot-list copy (follow `copy-voice.md`).
- Whether the coverage strip shows an overall headline number alongside the per-scanner breakdown (D-05 mandates per-scanner; a summary tile is discretionary if it aids scanability).
- Notify-owner email template wording (reuse `app/notifications`/`email.py` HTML pattern).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` §"Phase 41: Coverage & Blind-Spot Detection" — goal, success criteria, dependencies.
- `.planning/REQUIREMENTS.md` — COV-01, COV-02, COV-03 (lines ~64–66, dependency map ~115–117).

### Source-class partition (the reconciliation depends on this)
- `backend/app/assets/constants.py` — `SCANNER_SOURCES` (the 6 `VulnSource`) vs `ENRICHMENT_SOURCES` (`JAMF`/`HUMAANS`/`INTUNE`); the exact partition D-01/D-02 reconcile across. Never conflate the two classes.
- `backend/app/assets/models.py` — `Asset.seen_by_sources` (JSONB list), `last_seen_at`, `assigned_user`, exposure/owner-adjacent fields.

### Connector sync-health (COV-02)
- `backend/app/ticketing/models.py` §`ConnectorConfig` — `last_sync_at`, `last_sync_status`, `consecutive_failure_count`, `sync_interval_minutes` (read directly for coverage % + staleness).
- `backend/app/connectors/sync.py` — where scanner syncs create assets + append `seen_by_sources` (D-12 integrity basis).
- `backend/app/connectors/{jamf_sync,humaans_sync,intune_sync}.py` — where MDM/HR (authoritative) syncs create/append asset rows.

### Owner resolution & notification (COV-03)
- `backend/app/notifications/alerts.py` + `backend/app/notifications/digests.py` — `get_directory_user` owner-resolution precedence + `_email_owners_and_admins` fan-out; the D-07/D-09 pattern to reuse.
- `.planning/phases/40-proactive-alerting-digests/40-CONTEXT.md` §D-10 — owner-resolution fallback precedent (admins + tenant alert channel) that D-09 mirrors.

### UI primitives & patterns
- `.claude/skills/sketch-findings-getvul/` — sunset design system; `references/state-patterns.md` (mandatory empty state for D-11), `references/interaction-patterns.md` (chip-bar / drill-panel for D-04), `references/visual-language.md` (providers/SyncStatusPill).
- Existing Assets screen (`/assets`) — chip-bar + list + `DrillPanel` primitives reused verbatim in D-04.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Asset.seen_by_sources` + `app/assets/constants.py` partition: the entire COV-01/COV-02 reconciliation is a filter over this — no new data model needed for the core signal.
- `ConnectorConfig.last_sync_at` / `last_sync_status` / `consecutive_failure_count`: COV-02 reads these directly; no new sync-health plumbing.
- `get_directory_user` owner-resolution + `_email_owners_and_admins` (in `app/notifications/`): COV-03 assign+notify (D-07) and unresolvable-owner fallback (D-09) reuse these wholesale.
- Frontend Assets primitives (chip-bar, list, `DrillPanel`, `StatStrip`, `SyncStatusPill`, `ConnectorMark`, `EmptyState`): compose the entire Coverage page (D-04, D-11).

### Established Patterns
- Fail-closed `audit()` + RBAC route gating on every v5.0 mutation (D-08).
- Single unified `assets` table with provenance in `seen_by_sources` (not separate scanner/inventory tables) — reconciliation is intra-table set logic.
- Read-side live compute over tenant-bounded data (D-10), consistent with existing list/facet endpoints.

### Integration Points
- New "Coverage" sidebar nav entry + top-level page/route (D-03).
- New read endpoint(s): blind-spot asset list (filter authoritative ∧ no-scanner) + per-connector coverage summary (D-04/D-05/D-06), computed on-read.
- New write endpoint: route-to-owner (assign/confirm + notify), audited + RBAC-gated (D-07/D-08/D-09).

</code_context>

<specifics>
## Specific Ideas

- The reconciliation is deliberately narrow and honest: "authoritative" means *the device inventory GetVul actually has today* (MDM+HR), and a "blind spot" means *literally never scanned*. The view must not overclaim coverage when the inventory baseline is unknown (D-11).
- COV-03's value is closing the loop on shadow IT: the owner of an unmanaged device gets told to onboard it — no gap silently dropped (D-09).

</specifics>

<deferred>
## Deferred Ideas

- **CMDB connector (ServiceNow / CSV import)** — COV-01 names "CMDB" as an authoritative source, but none exists. A real CMDB import is its own connector phase. Route to roadmap backlog.
- **IdP user→device inference** — deriving "expected devices" from IdP users (users with no managed device). Needs a new inference model; IdP has no device rows today. Future phase.
- **Tenant-configurable stale threshold** and **per-connector-interval-derived staleness** — D-06 ships a fixed 7-day default; make configurable later if requested.
- **Precomputed/materialized coverage rollup** — D-10 computes on-read; materialize only if a very large tenant demonstrates a real performance need.
- **Manual owner-entry UI for unresolvable owners** — D-09 falls back to admins + channel; a typed-owner path could be a later enhancement.

</deferred>

---

*Phase: 41-coverage-blind-spot-detection*
*Context gathered: 2026-08-20*
