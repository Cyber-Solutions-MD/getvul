# Phase 41: Coverage & Blind-Spot Detection - Research

**Researched:** 2026-08-20
**Domain:** Internal reconciliation over existing asset/connector data (FastAPI + Postgres backend, Next.js/React frontend) — no new external technology
**Confidence:** HIGH

## Summary

Phase 41 is a **read-mostly reconciliation feature** built almost entirely from data and primitives GetVul already has. The backend already partitions `Asset.seen_by_sources` into `SCANNER_SOURCES` (the 6-value `VulnSource` enum) vs `ENRICHMENT_SOURCES` (`JAMF`/`HUMAANS`/`INTUNE`) in `backend/app/assets/constants.py`, GIN-indexes that column (`alembic/versions/045_add_seen_by_sources_gin.py`), and already exposes `ConnectorConfig.last_sync_at`/`last_sync_status`/`consecutive_failure_count` sync-health columns. This means COV-01's "authoritative vs scanner-seen" reconciliation is **not** a cross-table join with fuzzy hostname matching — GetVul already collapsed scanner + MDM + HR provenance onto **one** `assets` row per host (matching happens upstream, at sync time, via serial-number / login-user / hostname strategies in `jamf_sync.py` / `humaans_sync.py` / `connectors/sync.py`). Phase 41 only needs `.contains()` filters over the existing JSONB array — the same idiom the Assets list's `?scanner=`/`?enrichment_source=` facets already use — generalized into two aggregate reads (a blind-spot list and a per-connector coverage count). Phase 39's exception/exclusion machinery (`active_exception_subquery`) does not apply here: exceptions are finding-scoped risk acceptances, and a blind-spot asset by definition has no findings to except.

The owner-routing side (COV-03) is even more of a pure-composition task. `get_directory_user` (in `backend/app/assets/directory.py` — **not** `app/notifications/`, a minor correction to CONTEXT.md's canonical-refs shorthand) already resolves an owner by email precedence, `_email_owners_and_admins` (`backend/app/notifications/alerts.py`) already implements the exact "no owner found → notify admins" fallback D-09 asks for, and `_fire_kev_epss_alert` in that same file is a complete worked example of "resolve → notify-or-fallback → optional channel push → audit" that Phase 41's new endpoint can mirror almost line for line. An owner-persistence endpoint (`POST /assets/{id}/owner`, Phase 12 UX-04-04) **already exists** — this directly answers CONTEXT.md's open D-07 question about whether a new owner-override column is needed: it isn't (owner lives in the plain-string `Asset.assigned_user` field, by an explicit Phase-12 "no `owner_user_id` migration" decision), and given the UI-SPEC's confirm dialog has no manual-owner-entry field, Phase 41 most likely doesn't even need to call that endpoint at all (see Open Questions).

Research surfaced one load-bearing pre-existing defect that CONTEXT.md's D-12 explicitly asked research to check for: **`run_intune_sync` cannot currently succeed against a real database.** It constructs `SyncLog(connector_config_id=connector_config.id, ...)` — `connector_config_id` is not a field on the real `SyncLog` model (only `connector_id` exists), and the required `tenant_id` is also omitted — so SQLAlchemy raises `TypeError` on the very first statement, before any device is processed. Since D-01 names INTUNE as one of exactly three authoritative sources, any tenant relying solely on Intune (no Jamf, no Humaans-matchable asset) will see an empty baseline / the D-11 "no inventory" empty state even though they configured a connector correctly, and that connector will show "Never synced" forever no matter how many times it retries. This is flagged prominently below (Pitfall 1); the planner must decide whether fixing it is in-scope for Phase 41 or tracked separately.

**Primary recommendation:** Build Phase 41 as a new, small `backend/app/coverage/` module (`router.py` + `service.py` + `schemas.py`, **no new models/tables** — D-10 mandates pure compute-on-read) mounted at `/api/v1/coverage`, computing via `.contains()` filters over the existing GIN-indexed `seen_by_sources` column and `ConnectorConfig` sync-health columns; compose the frontend page entirely from existing primitives (`StatStrip`, `SyncStatusPill`, `ConnectorMark`, `EmptyState`, `DrillPanel` with `idKey="asset"` mirroring the **tickets** list page's precedent — not the assets list page, which doesn't use `DrillPanel` — `ChipBar`, `PartialFailureBanner`, `useToast`) at the real route `/dashboard/coverage` (not the UI-SPEC's shorthand `/coverage`); and implement "route to owner" as a pure resolve-and-notify action (`get_directory_user` + `_email_owners_and_admins`/`dispatch_channel`) with **no new database column**, following `_fire_kev_epss_alert`'s exact shape but using the standard `audit()` helper (this runs in an authenticated HTTP request, not the scheduler).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**COV-01 — Authoritative baseline & blind-spot definition**
- **D-01:** Authoritative inventory = MDM+HR asset rows only. The baseline is every asset whose `seen_by_sources` contains an ENRICHMENT source (`JAMF` / `HUMAANS` / `INTUNE`, per `app/assets/constants.py::ENRICHMENT_SOURCES`). Honest to what actually produces device inventory today. IdP (users, not devices) and CMDB (absent) are documented as a deferred gap, not silently implied. No new connector work.
- **D-02:** A blind spot = zero scanner sources. An asset is a coverage blind spot when it is in the authoritative baseline (D-01) but its `seen_by_sources` contains **no** `SCANNER_SOURCES` value (the 6-value `VulnSource` enum) — i.e. never touched by any vuln scanner. This is Success-Criterion-1's "zero findings / never scanned"; for a never-scanned asset the zero-findings and null-`last_seen_at` conditions are subsumed by the no-scanner-source signal. Asset-level staleness (scanner-seen but gone quiet) is deliberately kept out of the blind-spot list and handled at the connector level in COV-02 (D-05), keeping asset-level vs source-level signals cleanly separated.

**COV-01 — View placement & layout**
- **D-03:** New top-level "Coverage" nav page (sidebar entry alongside Vulnerabilities / Assets / Campaigns), not a tab under Assets. Blind-spot detection is a distinct analyst workflow; matches ROADMAP "coverage view" + "UI hint: yes".
- **D-04:** Layout = per-connector coverage strip on top + unmanaged/never-scanned asset list below. Top strip renders COV-02 (coverage % + stale badges) reusing `StatStrip` / `SyncStatusPill` / `ConnectorMark`. Below, the blind-spot asset list reuses the Assets chip-bar + list + `DrillPanel` primitives, with the route-to-owner action (D-07) per row. The two are read together (see the gap %, then the assets behind it).

**COV-02 — Coverage % & staleness**
- **D-05:** Per-scanner coverage % of the authoritative baseline. For each scanner connector: `coverage% = (authoritative assets whose seen_by_sources includes that scanner) / (total authoritative MDM+HR assets)`. Answers "what fraction of my known devices does each scanner actually cover." Chosen over a single overall-scanned % (loses the per-connector breakdown COV-02 requires) and over both (unneeded now).
- **D-06:** Stale-source threshold = fixed default 7 days. A connector whose `ConnectorConfig.last_sync_at` is older than 7 days is flagged stale. Reads existing sync-health columns directly (`ConnectorConfig.last_sync_at`, `last_sync_status`, `consecutive_failure_count`). Tenant-configurable and per-connector-interval-derived staleness were both rejected as over-engineering for this phase (can be added later without rework). — **Reversibility:** reversible — a single constant in the coverage service.

**COV-03 — Owner-routing action**
- **D-07:** Route-to-owner = assign/confirm owner + notify-owner email. A never-scanned asset has no findings, so there is nothing to ticket in the normal vuln flow. The action resolves the owner (reusing the `get_directory_user` precedence that ALERT-01/digests already use in `app/notifications/`), and sends a notify-owner email ("this device is in inventory but no scanner covers it — please onboard it"). No synthetic finding and no fake vuln-linked ticket (would bend `Ticket.vulnerability_id`'s NOT-NULL FK). Chosen over create-a-coverage-ticket and assign-owner-only.
  - **Open for research (do NOT re-ask user):** the `assets` table has no dedicated `owner` column — owner is *resolved* via `get_directory_user` precedence; `assigned_user` (String) exists as raw MDM data. Whether "assign owner" persists an explicit owner override (new column/field) or simply confirms + notifies the resolved owner is a planner/researcher call. Prefer the lightest path that satisfies "route to an owner"; flag if an override column is genuinely needed.
- **D-08:** Route-to-owner is audited (fail-closed `audit()`) + RBAC-gated to write roles (analyst+). Consistent with every other v5.0 mutation (exceptions, campaigns, alerting-config). Viewer cannot invoke it.
- **D-09:** Unresolvable-owner fallback = notify admins + the tenant alert channel. When no directory owner resolves for an unmanaged asset, fall back to tenant OWNER/ADMIN users + the tenant alert channel so the riskiest shadow-IT asset is never silently dropped. Mirrors Phase 40 D-10 owner-resolution fallback. Rejected: blocking the action, or a manual owner-entry UI (adds entry/validation surface not warranted this phase).

**Compute & data integrity**
- **D-10:** Compute live on-read. The reconciliation (blind-spot list + per-scanner coverage % + staleness) is computed per request from `seen_by_sources` + `ConnectorConfig` each time the Coverage view loads. `seen_by_sources` is GIN-filterable and asset counts are tenant-bounded, so this is fine at expected scale. No new job, table, backfill, or staleness of the numbers. A precomputed/materialized rollup (like the v4.0 risk-exposure shadow) was rejected as over-engineered for this phase. — **Reversibility:** reversible — pure read-side service; can be materialized later if scale demands.
- **D-11:** No-inventory guided empty state. When a tenant has no MDM/HR (authoritative) connector configured, the Coverage view shows a canonical `EmptyState` — "Connect an inventory source (Jamf / Intune / Humaans) to detect coverage gaps" with a link to `/connectors` — rather than a misleading 0%/100%. Mandatory state-pattern per project rules; do NOT fall back to a total-assets denominator (would imply full coverage when the real inventory is simply unknown).
- **D-12:** Trust `seen_by_sources`; treat empty scanner-sources as unscanned. `seen_by_sources` is the source of truth (scanner syncs reliably append it in `app/connectors/sync.py`; MDM/HR syncs append their source). An authoritative asset with no scanner source in `seen_by_sources` = a blind spot (exactly the signal wanted). Add a one-time verify check during research (spot-check historical rows), but no backfill migration unless research finds a real gap. Backfill-recompute-from-vuln-rows was rejected as likely-unnecessary migration risk. **Research finding: see Pitfall 1 below — the "MDM/HR syncs append their source" premise is FALSE for Intune specifically (code defect, not a data gap; no backfill applies since no Intune rows have ever been successfully written).**

### Claude's Discretion
- Exact empty-state / blind-spot-list copy (follow `copy-voice.md`).
- Whether the coverage strip shows an overall headline number alongside the per-scanner breakdown (D-05 mandates per-scanner; a summary tile is discretionary if it aids scanability).
- Notify-owner email template wording (reuse `app/notifications`/`email.py` HTML pattern).

### Deferred Ideas (OUT OF SCOPE)
- **CMDB connector (ServiceNow / CSV import)** — COV-01 names "CMDB" as an authoritative source, but none exists. A real CMDB import is its own connector phase. Route to roadmap backlog.
- **IdP user→device inference** — deriving "expected devices" from IdP users (users with no managed device). Needs a new inference model; IdP has no device rows today. Future phase.
- **Tenant-configurable stale threshold** and **per-connector-interval-derived staleness** — D-06 ships a fixed 7-day default; make configurable later if requested.
- **Precomputed/materialized coverage rollup** — D-10 computes on-read; materialize only if a very large tenant demonstrates a real performance need.
- **Manual owner-entry UI for unresolvable owners** — D-09 falls back to admins + channel; a typed-owner path could be a later enhancement.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| COV-01 | Reconcile authoritative inventory (IdP/MDM/HR/CMDB) against scanner-seen assets; list assets with zero findings / never scanned | Pattern 1 (compute-on-read `.contains()` reconciliation, no join needed); `SCANNER_SOURCES`/`ENRICHMENT_SOURCES` partition already exists and is GIN-indexed; Pitfall 5 (Humaans never originates asset rows) and Pitfall 1 (Intune sync is currently broken) directly determine what "authoritative" looks like in practice for a given tenant |
| COV-02 | Per-connector coverage % and stale-source gaps | Code Example B (coverage-% query loop over `ConnectorConfig` + `Asset`); D-06's fixed 7-day threshold is a one-line comparison against `last_sync_at`; Pitfall 3 (must reuse `_normalize_sync_status` or `SyncStatusPill` silently mis-renders) |
| COV-03 | A newly-discovered unmanaged asset can be routed to an owner | Pattern 2 (resolve-then-notify-with-fallback, mirrors `_fire_kev_epss_alert` almost verbatim); existing `get_directory_user` / `_email_owners_and_admins` / `dispatch_channel`; existing `POST /assets/{id}/owner` endpoint answers the "does this need a new column" question (no); RBAC/audit conventions in Anti-Patterns and Pitfall 4 |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

`./CLAUDE.md` applies to this phase. Directives relevant to Phase 41, and how the already-approved 41-UI-SPEC.md satisfies each:

| Directive | Source | Status for Phase 41 |
|---|---|---|
| Frontend stack: Next.js 15 App Router + React 19 + TS 5.5 + Tailwind 3.4, consuming `sketch-findings-getvul` CSS-variable tokens (not shadcn's zinc theme) | CLAUDE.md "Codebase conventions" | UI-SPEC confirms: "This phase adds zero new shadcn components" — hand-rolled Tailwind + design tokens only, verified against `frontend/components.json`'s preset note |
| Backend stack: FastAPI + Postgres + Redis | CLAUDE.md "Codebase conventions" | No new infra — reuses existing Postgres (GIN-indexed column) and the existing Redis-backed session/auth stack; no Redis-specific work this phase |
| `sketch-findings-getvul` skill auto-loads for all frontend work | CLAUDE.md "Skills" | Already consumed — 41-UI-SPEC.md is the distilled, phase-specific output of that skill (checker-approved, 6/6 dimensions PASS); no need to re-derive from the raw skill references |
| Don't substitute fonts (Inter + JetBrains Mono locked) | CLAUDE.md "What NOT to do" | UI-SPEC Typography table specifies Inter (UI/body) + JetBrains Mono (hostnames, %, day counts) — compliant |
| Don't pick hex colors freehand | CLAUDE.md "What NOT to do" | UI-SPEC Color table uses only `var(--color-*)` tokens, including reuse of the existing SLA 3-tier and stale-pill families — compliant, no new palette |
| Don't ship a screen without empty/loading/error states | CLAUDE.md "What NOT to do" | UI-SPEC's "UI Considerations" table resolves 24/2/4 (empty/loading/error/populated/partial/overflow/zero-one-many/long-text) across all 5 page regions — see the 2 unresolved backstops in Open Questions below |
| Don't compose generic SaaS copy | CLAUDE.md "What NOT to do" | UI-SPEC Copywriting Contract is fully specified per `copy-voice.md` conventions (e.g. "stale · 12d", never "Oops! Something went wrong") |

No CLAUDE.md directive conflicts with any locked CONTEXT.md decision — no contradictions to flag to the planner.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Blind-spot reconciliation (COV-01) | API / Backend | Database | Pure SQL `.contains()` filter over an existing GIN-indexed JSONB column — the database does the set logic, the API only assembles/paginates the response |
| Per-connector coverage % + staleness (COV-02) | API / Backend | Database | Aggregation (`COUNT ... WHERE`) over `Asset` + `ConnectorConfig`; no client-side math, no new table |
| Coverage strip / blind-spot list rendering | Browser / Client | — | Pure presentation over API JSON; composes existing `StatStrip` / `SyncStatusPill` / table primitives, zero new state logic |
| Owner resolution (COV-03) | API / Backend | Database | `get_directory_user` queries the tenant-private `users` table — must stay server-side, never exposed as a client-callable directory search |
| Notify-owner / admin-fallback delivery (COV-03) | API / Backend | External (SMTP / Slack / Teams) | Backend calls existing `_send_notification_email` / `dispatch_channel`; the browser never talks to SMTP or a webhook directly |
| Route-to-owner confirm UI | Browser / Client | API / Backend | Dialog is presentation only; the actual resolve + notify + audit all happen server-side on submit |
| Audit trail | API / Backend | Database | `audit()` writes an `AuditLog` row in the same transaction as the mutation; the frontend only re-reads it via the existing `audit-log-pane.tsx` — no new UI |
| Sidebar nav entry | Frontend Server (persistent shell) | Browser | Static `nav-items.ts` entry rendered as part of the already-mounted app shell — no independent data fetch |

## Standard Stack

**No new third-party packages.** This phase is verified to be 100% composition of code already in the repository — consistent with CONTEXT.md's own framing ("mostly a read-side reconciliation over data GetVul already has"). No `npm install` / `pip install` is needed.

### Core (existing internal modules this phase composes)

| Module | Location | Purpose | Why reuse (not new) |
|---|---|---|---|
| Source partition constants | `backend/app/assets/constants.py` (`SCANNER_SOURCES`, `ENRICHMENT_SOURCES`) | Defines exactly which `seen_by_sources` values are "scanner" vs "authoritative enrichment" | This *is* the D-01/D-02 partition — import it rather than re-deriving the 9 strings, or Phase 41 and the existing Assets facet filter can drift apart [VERIFIED: codebase] |
| `Asset.seen_by_sources` GIN index | `backend/alembic/versions/045_add_seen_by_sources_gin.py` | Makes `.contains([x])` filters index-scannable | Confirms D-10's "GIN-filterable... fine at expected scale" claim is already live in the production schema, not aspirational [VERIFIED: codebase] |
| `ConnectorConfig` sync-health columns | `backend/app/ticketing/models.py:39-57` | `last_sync_at` / `last_sync_status` / `consecutive_failure_count` / `sync_interval_minutes` | COV-02 reads these directly; no new sync-health plumbing [VERIFIED: codebase] |
| `get_directory_user` | `backend/app/assets/directory.py` | Owner-by-email-precedence resolution | The exact function CONTEXT.md's D-07 says to reuse; extracted in Phase 40 specifically so non-router code could call it [VERIFIED: codebase] |
| `_email_owners_and_admins`, `_fire_kev_epss_alert` (as a pattern) | `backend/app/notifications/alerts.py` | Resolve→notify-or-fallback, with optional tenant-channel push | Worked, already-shipping precedent for exactly COV-03's D-07/D-09 shape [VERIFIED: codebase] |
| `dispatch_channel` / `_build_channel_config` | `backend/app/notifications/escalation_channels.py`, `backend/app/vulnerabilities/sla_tier_service.py` | Slack/Teams/PagerDuty/email delivery with SSRF guarding built in | Reuse for D-09's "tenant alert channel" leg — never hand-roll a new outbound webhook POST [VERIFIED: codebase] |
| `require_viewer` / `require_analyst` | `backend/app/auth/rbac.py` | RBAC FastAPI dependency | The current v5.0 convention (see Pitfall 4 — a second, legacy RBAC system also exists) [VERIFIED: codebase] |
| `audit()` | `backend/app/audit.py` | Fail-closed audit-row helper | D-08's mandate; "audit-then-commit" ordering [VERIFIED: codebase] |
| `StatStrip`, `SyncStatusPill`, `ConnectorMark`, `EmptyState`, `DrillPanel`, `PartialFailureBanner`, `SkeletonTable` | `frontend/src/components/{ui,connectors,states,vulnerabilities}/` | All visual primitives named in the UI-SPEC | Zero new components beyond 2 new compositions (a coverage card, a route-to-owner dialog) [VERIFIED: codebase] |
| `useToast` | `frontend/src/components/ui/ToastProvider.tsx` | Success/error toast | Already fully implemented and used by 10+ existing mutation hooks — the UI-SPEC's "deferred toast spec" phrase refers to a reference doc, not an unbuilt feature [VERIFIED: codebase] |
| `Radar` icon | `lucide-react` (already a dependency, `^0.383.0`) | New sidebar glyph named in the UI-SPEC | Confirmed present in the installed package (`typeof require('lucide-react').Radar === 'object'`) — no version bump needed [VERIFIED: local node_modules] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Compute-on-read `.contains()` filters | A precomputed/materialized coverage rollup table | Rejected by D-10 as over-engineering for current scale; revisit only if a very large tenant shows real latency |
| Notify-only route-to-owner | A synthetic finding + ticket | Rejected by D-07 — would violate `Ticket.vulnerability_id`'s NOT-NULL FK and misrepresent an unscanned asset as having a real finding |

**Installation:** none.

**Version verification:** not applicable (no new packages). `lucide-react@^0.383.0` (already installed) confirmed to export `Radar`.

## Architecture Patterns

### System Architecture Diagram

```
Analyst opens /dashboard/coverage
        │
        ▼
Frontend: GET /api/v1/coverage/summary        GET /api/v1/coverage/blind-spots?page=1
        │                                              │
        ▼                                              ▼
app/coverage/router.py (require_viewer)         app/coverage/router.py (require_viewer)
        │                                              │
        ▼                                              ▼
app/coverage/service.py                         app/coverage/service.py
  • list ConnectorConfig WHERE tenant_id           • SELECT Asset WHERE tenant_id
    AND connector_type IN SCANNER_SOURCES              AND seen_by_sources ∩ ENRICHMENT_SOURCES (any)
  • COUNT Asset WHERE authoritative filter           AND NOT (seen_by_sources ∩ SCANNER_SOURCES)
  • COUNT Asset WHERE authoritative ∧               (paginated, tenant-bounded)
    contains(scanner_type)  — per connector
  • stale = now - last_sync_at > 7d (D-06)
        │                                              │
        ▼                                              ▼
   Postgres — assets.seen_by_sources (GIN)        Postgres — same index + table
   + connector_configs (sync-health cols)
        │                                              │
        └──────────────────┬───────────────────────────┘
                            ▼
          JSON → StatStrip cards (per-connector %, stale badge)
                + blind-spot table (below, D-04 top-to-bottom order)
                            │
                            ▼
          Analyst clicks "Route to owner" on a blind-spot row
                            │
                            ▼
     POST /api/v1/coverage/assets/{id}/route-to-owner (require_analyst)
                            │
                            ▼
          app/coverage/service.py::route_to_owner(db, tenant_id, user, asset)
                  │                                  │
        owner resolves                     owner does NOT resolve (D-09)
        (get_directory_user)                         │
                  │                                  ▼
                  ▼                     _email_owners_and_admins (OWNER/ADMIN users)
    _send_notification_email                + dispatch_channel (tenant alert channel —
    (direct to owner)                          see Open Questions on the routing key)
                  │                                  │
                  └───────────────┬──────────────────┘
                                  ▼
                  audit(db, user, "coverage.route_to_owner", "asset", ...)
                                  ▼
                            await db.commit()
                                  ▼
                200 response → success toast + row/list re-fetch (React Query invalidate)
```

A reader can trace COV-01 (left branch), COV-02 (per-connector cards, same left branch), and COV-03 (the lower half, triggered from a row in the right branch's rendered list) end to end via the arrows above.

### Recommended Project Structure

```
backend/app/coverage/                 # NEW — mirrors app/exceptions/, app/campaigns/ shape
├── __init__.py
├── router.py                         # GET /summary, GET /blind-spots, POST /assets/{id}/route-to-owner
├── service.py                        # reconciliation queries + route_to_owner() resolve/notify logic
└── schemas.py                        # CoverageSummaryResponse, BlindSpotAssetResponse, RouteToOwnerResponse
# No models.py — D-10 mandates pure compute-on-read, no new table.

frontend/src/app/(authed)/dashboard/coverage/
├── page.tsx                          # composes ChipBar + StatStrip + table + DrillPanel + EmptyState
└── page.test.tsx                     # mirrors assets/page.test.tsx's branch-coverage convention

frontend/src/components/coverage/     # NEW — mirrors components/campaigns/, components/exceptions/
├── coverage-connector-card.tsx       # per-connector %, SyncStatusPill, stale badge
├── coverage-asset-drill-content.tsx  # DrillPanel renderContent for idKey="asset"
├── route-to-owner-dialog.tsx         # mirrors exception-grant-dialog.tsx's ResponsiveDialog shape (simpler: 2 branches, no form fields)
└── microcopy.ts                      # mirrors components/assets/microcopy.ts

frontend/src/lib/queries/
├── use-coverage-summary.ts           # useQuery, queryKeys.coverage.summary()
├── use-blind-spot-assets.ts          # useQuery, queryKeys.coverage.blindSpots(opts)
└── use-route-to-owner.ts             # useMutation, mirrors use-reassign-asset.ts's toast+invalidate shape
```

### Pattern 1: Compute-on-read reconciliation via JSONB `.contains()` — not a join

**What:** the "reconciliation" is a same-table filter, not a join between a separate scanner-inventory table and an authoritative-inventory table — both provenance classes already live in one `Asset.seen_by_sources` JSONB array.
**When to use:** any time GetVul needs to ask "did source X ever see this asset." This is the established, GIN-indexed idiom, already used by `assets/router.py`'s `?scanner=`/`?enrichment_source=` facets and `ticketing/rule_engine.py::find_matching_assets`.
**Example (generalized from the existing facet-filter shape):**
```python
# Source: backend/app/assets/router.py:126-152 (existing pattern), generalized for D-01/D-02
from sqlalchemy import not_, or_, select
from app.assets.constants import ENRICHMENT_SOURCES, SCANNER_SOURCES
from app.assets.models import Asset

authoritative = or_(*[Asset.seen_by_sources.contains([e]) for e in ENRICHMENT_SOURCES])   # D-01
never_scanned = not_(or_(*[Asset.seen_by_sources.contains([s]) for s in SCANNER_SOURCES]))  # D-02

blind_spots = select(Asset).where(
    Asset.tenant_id == tenant_id,
    Asset.is_ignored.is_(False),   # mirrors list_assets' default — see Open Questions
    authoritative,
    never_scanned,
)
```

### Pattern 2: Resolve-then-notify-with-fallback (COV-03)

**What:** `_fire_kev_epss_alert`'s exact shape — resolve an owner, email them if found, else fan out to admins, optionally also push to a configured channel, always write an audit row.
**When to use:** any "tell a human about this asset" action where the database has no guaranteed owner.
**Example (adapted for an authenticated HTTP request, not the scheduler's `user=None` context):**
```python
# Source: backend/app/notifications/alerts.py:394-402 (_fire_kev_epss_alert, D-10/D-09 pattern),
# adapted: use audit() here (a real CurrentUser exists), NOT the raw AuditLog(...) construction
# _fire_kev_epss_alert uses — that shape exists only for the scheduler's user=None case.
from app.assets.directory import get_directory_user
from app.audit import audit
from app.notifications.alerts import _email_owners_and_admins
from app.notifications.service import _send_notification_email

directory_user = await get_directory_user(db, tenant_id, asset)
if directory_user and directory_user.get("email"):
    await _send_notification_email(
        db, tenant_id, directory_user["email"], title, message, "coverage_route_to_owner"
    )
    routed_to = directory_user["display_name"] or directory_user["email"]
else:
    await _email_owners_and_admins(db, tenant, title, message, "coverage_route_to_owner")  # D-09
    routed_to = "your admins"

await audit(
    db, user, "coverage.route_to_owner", "asset", str(asset.id),
    {"hostname": asset.hostname, "routed_to": routed_to},
)
await db.commit()
```

### Pattern 3: Generalized `DrillPanel` with `idKey` (asset context)

**What:** `DrillPanel` already supports an `idKey`/`renderContent` slot contract (added additively for tickets — vuln callers still work unmodified via `cveId` back-compat). The **tickets** list page is the real precedent to copy — **not** the `/assets` list page, which navigates to a full detail route instead of opening a panel (`assets/page.tsx`'s own comment: "drill happens on the detail page, not in a panel on the list").
**Example:**
```tsx
// Source: frontend/src/app/(authed)/dashboard/tickets/page.tsx:349-394 (idKey="ticket" precedent)
<DrillPanel
  idKey="asset"
  id={assetIdFromUrl}
  ariaLabel="Device detail"
  renderContent={({ id, onClose }) => (
    <CoverageAssetDrillContent assetId={id} onClose={onClose} />
  )}
/>
```

### Anti-Patterns to Avoid

- **Don't build a second scanner-inventory-vs-authoritative-inventory join.** The data model already unified provenance into one column; a join would re-introduce the fuzzy hostname-matching problem the sync layer already solved at write time.
- **Don't construct `AuditLog(...)` directly.** That raw-insert shape (seen in `_fire_kev_epss_alert`) exists *only* because the scheduler has no `CurrentUser` (`user=None`, `user_email="system:scheduler"`). COV-03 runs inside an authenticated request — use `audit()`.
- **Don't import `require_role` from `app.auth.dependencies`.** That's the legacy, lowercase-keyed RBAC helper still used by some Phase-12/32 endpoints in `assets/router.py`. Every v5.0 phase (36–40) uses `app.auth.rbac.require_viewer`/`require_analyst` — see Pitfall 4.
- **Don't pass a raw uppercase `last_sync_status` to the frontend.** `SyncStatusPill` expects the wire-normalized `'ok'|'failed'|'syncing'|null` — run it through the same mapping `connectors/service.py::_normalize_sync_status` already applies. See Pitfall 3.
- **Don't copy the `/assets` list page's row-click handler for the blind-spot list.** It navigates full-page; copy the tickets list page's `DrillPanel` usage instead. See Pitfall 8.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| "Which asset rows are authoritative / never-scanned" | A new cross-table join + fuzzy hostname/serial matcher | `.contains()` filter over `Asset.seen_by_sources` using `SCANNER_SOURCES`/`ENRICHMENT_SOURCES` from `app/assets/constants.py` | The matching already happened once, correctly, at sync time (serial → login-user → hostname strategy in `jamf_sync.py`/`humaans_sync.py`); redoing it here risks a different, inconsistent notion of "the same device" |
| "Who owns this device" | A new heuristic (email guessing, hostname parsing) | `get_directory_user(db, tenant_id, asset)` (`app/assets/directory.py`) | Already handles the 3-field precedence (`humaans_email` → `assigned_user` → `last_login_user`) and is proven via the existing digest/alert call sites |
| "Nobody to notify — now what" | A new "notify tenant admins" query | `_email_owners_and_admins(db, tenant, title, message, category)` (`app/notifications/alerts.py`) | Already queries `User.role.in_(["OWNER","ADMIN"])` tenant-scoped and fans out to all matches |
| "Push to the tenant's Slack/Teams" | A new `httpx` POST to a tenant-supplied webhook URL | `dispatch_channel()` + `_build_channel_config()` (`app/notifications/escalation_channels.py`, `app/vulnerabilities/sla_tier_service.py`) | Already SSRF-guards the URL (`_validate_webhook_url`), decrypts Fernet-at-rest secrets, and fails isolated per channel |
| "Is this connector stale" | New per-connector interval math | `now - ConnectorConfig.last_sync_at > timedelta(days=7)` (D-06's fixed constant) | `ConnectorConfig` already carries `last_sync_at`; no new column |
| Coverage-strip / blind-spot-list loading, empty, error states | New skeleton/empty/error components | `SkeletonTable`, `EmptyState` (compound), `PartialFailureBanner` (`frontend/src/components/states/`) | Already accessible (`role="status" aria-live="polite"`), already sunset-tokenized |
| "Nd ago" / "stale · Nd" day-count copy | A `date-fns`/`dayjs` dependency | The existing inline day-math helper pattern (`exceptions-table.tsx:92-97`) | This codebase's established convention for this exact copy-voice shape is a 4-line function, not a library — matches `copy-voice.md`'s "3d left" quantity format |

**Key insight:** every "hard part" of this phase (identity resolution across scanners/MDM/HR, notification fan-out with fallback, webhook delivery security) was already built and is load-bearing for a *different* phase (35, 40, 36 respectively). Phase 41's actual net-new code is small: two read endpoints that filter an existing column, one write endpoint that calls two existing functions, and a page that arranges nine existing components in a new layout.

## Common Pitfalls

### Pitfall 1: `run_intune_sync` cannot currently write to `seen_by_sources` (verified defect)
**What goes wrong:** a tenant configures an Intune connector expecting it to populate the authoritative baseline (D-01 names INTUNE as one of exactly 3 sources). It never does — `run_intune_sync` crashes on its very first statement, every time.
**Why it happens:** `backend/app/connectors/intune_sync.py:122-129` constructs `SyncLog(connector_config_id=connector_config.id, status="running", started_at=..., records_fetched=0, records_created=0, records_updated=0)`. The real `SyncLog` model (`backend/app/ticketing/models.py:60-76`) has **no `connector_config_id` field** (only `connector_id`) and requires `tenant_id` (also omitted) — SQLAlchemy's declarative `__init__` raises `TypeError` immediately, before `db.add()`/`db.flush()` ever run. The exception propagates through `run_sync` (`connectors/sync.py:122-125`) to the scheduler's `_run_single_sync` (`scheduler.py:29-52`), which catches it with a bare `except Exception` that only logs — it never sets `connector.last_sync_status`, so the connector shows "Never synced" forever regardless of retry count. Separately (masked by the crash today, but live if someone "fixes" only the `SyncLog` kwarg in isolation): the two `select(Asset).where(...)` lookups (lines 153, 158) and the `Asset(hostname=device_name)` construction (line 165) carry **no `tenant_id` filter or value at all** — a naive partial fix would introduce a cross-tenant asset-matching bug.
**How to avoid:** if fixing this is scoped into Phase 41 (recommended — see Open Questions), fix both issues together: (1) `SyncLog(connector_id=connector_config.id, tenant_id=connector_config.tenant_id, status="RUNNING", ...)` — uppercase status too, matching every sibling sync file (`_normalize_sync_status`'s map only recognizes `"SUCCESS"/"FAILED"/"SYNCING"`); (2) add `Asset.tenant_id == connector_config.tenant_id` to both lookups and `tenant_id=connector_config.tenant_id` to the `Asset(...)` constructor.
**Warning signs:** a tenant whose only MDM connector is Intune sees the D-11 "no inventory source" empty state despite having configured one correctly; no `SyncLog` row is ever created for that connector, not even a `FAILED` one.
**Confidence:** HIGH — verified by direct comparison of `intune_sync.py`'s `SyncLog(...)` call against the actual model fields (`ticketing/models.py`) and against every sibling sync file's construction pattern (`jamf_sync.py`, `humaans_sync.py`, `connectors/sync.py` all use `connector_id=`, `tenant_id=`, uppercase status).

### Pitfall 2: The UI-SPEC's `/coverage` is shorthand — the real route must be `/dashboard/coverage`
**What goes wrong:** creating a Next.js route at the literal path `frontend/src/app/coverage/page.tsx` would place the page outside the authenticated `(authed)/dashboard/` route group — no sidebar/topbar shell, no auth guard.
**Why it happens:** 41-UI-SPEC.md's Design System section says "this phase ships one new route (`/coverage`)" — informal shorthand, consistent with how the UI-SPEC refers to every screen by its bare slug.
**How to avoid:** every sibling nav destination lives at `/dashboard/{slug}` (`/dashboard/assets`, `/dashboard/campaigns`, `/dashboard/exceptions` — confirmed in `nav-items.ts` and the physical `frontend/src/app/(authed)/dashboard/` directory listing). Coverage must follow the same convention: `frontend/src/app/(authed)/dashboard/coverage/page.tsx`, nav `href: '/dashboard/coverage'`.
**Confidence:** HIGH — verified against `nav-items.ts` and the actual directory structure.

### Pitfall 3: Passing raw backend sync-status values silently breaks `SyncStatusPill`
**What goes wrong:** the coverage-summary response serializes `ConnectorConfig.last_sync_status` (raw `"SUCCESS"`/`"FAILED"`/`None`) directly. `SyncStatusPill` only recognizes the wire contract `'ok'|'failed'|'syncing'|null` and treats anything else as `__never` ("Never synced") — every real connector would silently render as "Never synced" regardless of true state.
**Why it happens:** the wire-normalization step already exists but lives in `app/connectors/service.py::_normalize_sync_status`/`_SYNC_STATUS_MAP` — a function the new `app/coverage/service.py` won't inherit automatically just by importing `ConnectorConfig`.
**How to avoid:** import and reuse `_normalize_sync_status` (or duplicate the tiny 3-entry map) when building each per-connector coverage-card payload.
**Confidence:** HIGH — verified both ends of the contract: the pill's own defensive-fallback comment ("an unexpected/un-normalized value... degrades gracefully to the `__never` config") and the backend's normalization comment referencing this exact mismatch class ("CR-06 precedent").

### Pitfall 4: Two parallel RBAC systems — importing the wrong one
**What goes wrong:** copying an RBAC import from `assets/router.py` (the file this phase touches most, for `get_directory_user`) pulls in `from app.auth.dependencies import require_role`, the legacy lowercase-keyed helper — functionally similar but a different implementation than the v5.0 standard.
**Why it happens:** this codebase has two independently-implemented role-hierarchy dependencies: `app.auth.dependencies.require_role(str)` (older; lowercase `{"owner":4,"admin":3,"analyst":2,"viewer":1}`; used by some Phase-12/32 endpoints in `assets/router.py`, e.g. `require_role("admin")` on the exposure-context endpoint) and `app.auth.rbac.RequireRole`/`require_viewer`/`require_analyst`/`require_admin`/`require_owner` (newer; `UserRole`-enum-keyed; used by every v5.0 phase — exceptions, campaigns, alerting).
**How to avoid:** import `require_viewer`/`require_analyst` from `app.auth.rbac`, matching `backend/app/exceptions/router.py`'s pattern exactly — D-08 explicitly says "consistent with every other v5.0 mutation."
**Confidence:** HIGH — verified both implementations exist side by side, with different active callers.

### Pitfall 5: HUMAANS can never independently populate the baseline
**What goes wrong:** assuming "tenant has Humaans configured" implies "tenant has a populated authoritative baseline."
**Why it happens:** `humaans_sync.py::_find_matching_assets` only enriches assets that **already exist** (matched by equipment serial → `last_login_user` → hostname-pattern) — it never constructs a new `Asset` row (`_enrich_asset` only mutates an existing instance). Only `jamf_sync.py` and `intune_sync.py` (bug notwithstanding — Pitfall 1) create rows from scratch.
**How to avoid:** no code change needed — this is by design, and D-01's baseline definition (`seen_by_sources` contains *any* of JAMF/HUMAANS/INTUNE) already handles it correctly, since a Humaans-tagged asset can only exist if some other sync created the row first. Just don't assume in test fixtures or documentation that "Humaans-only" is a populated-baseline scenario — combined with Pitfall 1, it is currently indistinguishable from "no inventory" unless Jamf also ran.
**Confidence:** HIGH — verified via direct read of `humaans_sync.py`.

### Pitfall 6: "Tenable" / "AWS Inspector" aren't real `connector_type` values in this codebase
**What goes wrong:** searching for a `TENABLE` or `AWS_INSPECTOR` connector type (referenced in the UI-SPEC's example copy — "e.g. Qualys, Tenable" — and in CLAUDE.md's product description — "Tenable, Qualys, Rapid7, AWS Inspector") turns up nothing, because neither exists as a `connector_type`.
**Why it happens:** the actual 6 scanner `connector_type`/`VulnSource` values are `CROWDSTRIKE, NESSUS, DEFENDER, WIZ, QUALYS, RAPID7` — Nessus is Tenable's product, registered under the label "Nessus Professional" in `backend/app/connectors/schemas.py::CONNECTOR_TYPES`. CLAUDE.md's phrasing is product-vision language, not a literal connector enumeration.
**How to avoid:** when building the coverage-strip's connector enumeration, iterate `ConnectorConfig` rows filtered to `connector_type in SCANNER_SOURCES` (the 6 real values) — don't special-case vendor names pulled from marketing/example copy.
**Confidence:** HIGH — verified against `connectors/schemas.py::CONNECTOR_TYPES` and `frontend/src/components/connectors/types.ts::ConnectorProvider` (neither lists Tenable or AWS Inspector).

### Pitfall 7: D-09's "tenant alert channel" has no ready-made routing key
**What goes wrong:** assuming `dispatch_channel`/`_build_channel_config` can be wired up for COV-03's admin-fallback with zero config changes.
**Why it happens:** Phase 40's `Tenant.alerting_config.routing` dict (`backend/app/notifications/alerting_config.py::DEFAULT_ALERTING_CONFIG`) has exactly 3 keys — `new_kev_epss`, `digest_owner`, `digest_team` — none for a coverage/unmanaged-asset event. The channel-dispatch *machinery* is fully reusable; the *routing configuration* that says which channel(s) to use for this new event type does not yet exist.
**How to avoid:** see Open Questions — either add a cheap new default routing key (no migration needed; `alerting_config` is an unconstrained JSONB column) or scope D-09's channel leg down to email-only for this phase.
**Confidence:** HIGH (that the gap exists) — verified against `alerting_config.py`'s literal 3-key dict. MEDIUM on the resolution (a design choice, not a fact).

### Pitfall 8: The `/assets` list page is **not** the `DrillPanel` precedent to copy
**What goes wrong:** assuming the existing Assets list page demonstrates the "list + `DrillPanel`" pattern CONTEXT.md/UI-SPEC describe, and copying its row-click handler.
**Why it happens:** `frontend/src/app/(authed)/dashboard/assets/page.tsx`'s `onRowOpen` does `router.push('/dashboard/assets/${id}')` — a full navigation to a detail *page*, not a `DrillPanel`. Per the page's own comment, this is deliberate (Phase 12, D-D-03): "drill happens on the detail page, not in a panel on the list."
**How to avoid:** the real "list row opens a `DrillPanel` via a generalized `idKey`" precedent is the **tickets** list page (`frontend/src/app/(authed)/dashboard/tickets/page.tsx:349-394`, `idKey="ticket"`) — copy that shape with `idKey="asset"` (Pattern 3 above).
**Confidence:** HIGH — verified by reading both pages directly.

## Code Examples

### Per-connector coverage % + staleness (COV-02)
```python
# Source: pattern derived from backend/app/assets/router.py's existing .contains() facet filters
# + backend/app/ticketing/models.py's ConnectorConfig sync-health columns
from datetime import UTC, datetime, timedelta
from sqlalchemy import func, or_, select
from app.assets.constants import ENRICHMENT_SOURCES, SCANNER_SOURCES
from app.assets.models import Asset
from app.connectors.service import _normalize_sync_status  # Pitfall 3 — do not skip
from app.ticketing.models import ConnectorConfig

STALE_THRESHOLD = timedelta(days=7)  # D-06 fixed default

authoritative_filter = or_(*[Asset.seen_by_sources.contains([e]) for e in ENRICHMENT_SOURCES])

total = (await db.execute(
    select(func.count()).select_from(Asset).where(Asset.tenant_id == tenant_id, authoritative_filter)
)).scalar() or 0

scanner_connectors = (await db.execute(
    select(ConnectorConfig).where(
        ConnectorConfig.tenant_id == tenant_id,
        ConnectorConfig.connector_type.in_(SCANNER_SOURCES),
    )
)).scalars().all()

cards = []
now = datetime.now(UTC)
for conn in scanner_connectors:
    covered = (await db.execute(
        select(func.count()).select_from(Asset).where(
            Asset.tenant_id == tenant_id,
            authoritative_filter,
            Asset.seen_by_sources.contains([conn.connector_type]),
        )
    )).scalar() or 0
    cards.append({
        "connector_type": conn.connector_type,
        "coverage_pct": round(100 * covered / total) if total else None,   # D-11: null, never a misleading 0/100
        "is_stale": bool(conn.last_sync_at and (now - conn.last_sync_at) > STALE_THRESHOLD),
        "last_sync_status": _normalize_sync_status(conn.last_sync_status),  # 'ok'|'failed'|'syncing'|None
    })
```

### Frontend mutation hook for "route to owner" (mirrors an existing, shipped pattern)
```typescript
// Source: frontend/src/lib/queries/use-reassign-asset.ts (existing shape to mirror — mutation + toast + invalidate)
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useToast } from '@/components/ui/ToastProvider';
import { queryKeys } from './keys';

type RouteToOwnerResponse = { hostname: string; routed_to: string };

export function useRouteToOwner(assetId: string) {
  const qc = useQueryClient();
  const { toast } = useToast();

  return useMutation<RouteToOwnerResponse, Error, void>({
    mutationFn: () =>
      api<RouteToOwnerResponse>(`/api/v1/coverage/assets/${assetId}/route-to-owner`, { method: 'POST' }),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: queryKeys.coverage.all });
      toast({ variant: 'success', message: `${data.hostname} routed to ${data.routed_to}` });
    },
    onError: () =>
      toast({
        variant: 'error',
        message: "Couldn't send the notification. Try again, or check the device's owner directly in your directory connector.",
      }),
    retry: 0,
  });
}
```

### `queryKeys` addition (mirrors the existing per-domain nesting convention)
```typescript
// Source: frontend/src/lib/queries/keys.ts — add alongside the existing exceptions/campaigns entries
coverage: {
  all: ['coverage'] as const,
  summary: () => ['coverage', 'summary'] as const,
  blindSpots: (opts: { page: number }) => ['coverage', 'blind-spots', opts] as const,
},
```

### Day-count badge copy (no new date library)
```typescript
// Source: frontend/src/components/exceptions/exceptions-table.tsx:92-97 (existing convention)
function daysAgo(iso: string): number {
  return Math.floor((Date.now() - new Date(iso).getTime()) / (1000 * 60 * 60 * 24));
}
// stale badge copy (D-06 / UI-SPEC): `stale · ${daysAgo(lastSyncAt)}d`
```

**Minor documentation note:** `backend/app/audit.py` keeps a comment block listing existing audit action names (`vuln.status_update`, `ticket.create`, `connector.sync`, …) for developer reference only (not an enforced enum). Whoever implements COV-03 should append `coverage.route_to_owner` to that list for consistency.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| No index on `seen_by_sources` (sequential scan per filter) | GIN index (`ix_assets_seen_by_sources`) | Phase 35 Plan 03 (SRC-08) | Makes Phase 41's `.contains()`-heavy reconciliation queries index-scannable instead of a seq scan per request — directly de-risks D-10's compute-on-read decision |
| `app.auth.dependencies.require_role` (legacy, lowercase-keyed) | `app.auth.rbac`'s `RequireRole`/`require_*` singletons | Phase 36 onward | New v5.0 code (including Phase 41) should exclusively use the newer one; the older helper is legacy-only, not deprecated-and-removed, so it still appears in some pre-v5.0 files (see Pitfall 4) |

**Deprecated/outdated:** none with an external timeline — this phase touches no library with its own deprecation schedule.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Recommending a new `routing.coverage_unmanaged_asset` default key (or equivalent) as the way to satisfy D-09's "tenant alert channel" leg | Pitfall 7 / Open Questions | If the planner instead wants a full settings-UI toggle for this, the recommended cheap default-key approach under-delivers on visibility/control; if the planner wants email-only, the recommended approach is unnecessary extra surface |
| A2 | Recommending `Asset.is_ignored.is_(False)` be applied to both the blind-spot list and the coverage-% denominator, mirroring the `/assets` list's default | Pattern 1 / Open Questions | If ignored assets should count toward "authoritative baseline," coverage % would read differently than what an analyst expects after ignoring a device |
| A3 | Recommending disabled connectors (`ConnectorConfig.is_enabled == False`) be excluded from the coverage strip | Open Questions | If a disabled-but-historically-relevant connector should still show its last-known %, excluding it silently drops that context |
| A4 | Recommending the new "Coverage" nav entry go in `WORKFLOW_ITEMS` (alongside Campaigns/Exceptions) rather than `TRIAGE_ITEMS` | Open Questions | Cosmetic only — wrong group placement doesn't break functionality, just visual grouping order |
| A5 | Recommending the Intune sync defect (Pitfall 1) be fixed as an in-scope prep task for Phase 41 rather than tracked separately | Pitfall 1 | If descoped, any Intune-only tenant's Coverage view will misleadingly show "no inventory" indefinitely until a separate fix ships; if fixed here, it adds backend surface area (and a new small test) beyond the phase's original 3 requirements |

**If this table is empty:** not applicable — see entries above. Every other claim in this research (the data model, the existing functions, the two RBAC systems, the Intune defect itself) was directly verified by reading the source and is not tagged `[ASSUMED]`.

## Open Questions (RESOLVED)

> **Resolution map (back-annotated at plan-checker, 2026-08-20):** every open question below was resolved during planning and is traceable to a specific plan.
> - **Q1 (D-09 channel wiring)** → RESOLVED in **41-04**: adds `"coverage_unmanaged_asset": []` to `DEFAULT_ALERTING_CONFIG["routing"]` (one-line JSONB default) AND keeps the `_email_owners_and_admins` fallback — both legs of D-09 honored, no scope reduction; no settings-UI control this phase.
> - **Q2 (pagination contract)** → RESOLVED in **41-01**: reuses the `AssetsResponse` `page`/`page_size` envelope verbatim.
> - **Q3 (scanner-absent empty-state copy)** → RESOLVED in **41-03**: extends the `EmptyState` family with the "No scanner connected" copy per `copy-voice.md`.
> - **Q4 (ignored assets / disabled connectors)** → RESOLVED in **41-01 / 41-03**: both excluded (`is_ignored.is_(False)`; `ConnectorConfig.is_enabled == True`), mirroring the `/assets` default.
> - **Q5 (nav group placement)** → RESOLVED in **41-01**: `WORKFLOW_ITEMS`, alongside Campaigns/Exceptions.
> - **Q6 (Intune defect scope)** → RESOLVED: raised explicitly and pulled into scope as **41-02** (Wave 1, independent files), documented in that plan's `planner_scoping_note` — not silently fixed or ignored.

1. **How should D-09's "tenant alert channel" fallback actually be wired, given no routing key exists for this event type yet?** — **RESOLVED → 41-04**
   - What we know: `dispatch_channel`/`_build_channel_config` are fully reusable, SSRF-guarded, and already used by `_fire_kev_epss_alert` for an analogous resolve-or-fallback flow. `Tenant.alerting_config` is an unconstrained JSONB column, so adding a new default routing key is a one-line, zero-migration change.
   - What's unclear: whether CONTEXT.md's "tenant alert channel" phrase requires a new tenant-configurable routing key (with an eventual settings-UI toggle, likely out of scope this phase) or can be satisfied by a fixed/default channel selection.
   - Recommendation: add `"coverage_unmanaged_asset": []` (or a sensible default like `["slack"]`) to `DEFAULT_ALERTING_CONFIG["routing"]` in `alerting_config.py`, reuse `_build_channel_config`/`dispatch_channel` exactly as `_fire_kev_epss_alert` does, and explicitly skip adding a settings-UI control this phase (tenants can still configure the underlying Slack/Teams/email credentials via the existing Phase 36 UI). If the planner wants a lighter footprint, email-to-admins-only (already satisfies "notify admins") is a defensible fallback, with the channel leg deferred.

2. **Blind-spot list pagination contract** (UI-SPEC backstop, E2 "overflow").
   - What we know: D-10 mandates on-read compute over tenant-bounded data but doesn't specify a page-size contract for the new endpoint. The existing `/assets` list already has a proven `page`/`page_size` query-param contract returning `{items, total, page, page_size, pages}` (`AssetsResponse`).
   - What's unclear: whether the planner wants that exact contract reused verbatim or a coverage-specific default (e.g., no pagination at all, given "expected scale" per D-10).
   - Recommendation: reuse the `AssetsResponse` shape verbatim (`page`/`page_size` query params, same response envelope) — this is a proven, already-tested pattern and avoids inventing a second pagination contract for a conceptually identical list.

3. **Scanner-absent-but-inventory-present empty-state copy** (UI-SPEC backstop, E4).
   - What we know: D-11 specifies copy only for "no authoritative inventory." The inverse (≥1 MDM/HR connector configured, zero scanner connectors) is a real, reachable state per COV-02 but has no locked copy.
   - What's unclear: exact heading/body wording (UI-SPEC explicitly defers this to the executor "to confirm copy in review").
   - Recommendation: extend the same `EmptyState` family — Heading: "No scanner connected" — Body: "You have inventory sources connected, but no vulnerability scanner. Connect one to measure coverage." — Action: "Connect a scanner" (links to `/connectors`), following `copy-voice.md`'s existing pattern for the analogous no-authoritative-inventory case.

4. **Should ignored assets and disabled connectors be excluded from coverage computation?**
   - What we know: `/assets`'s existing list defaults to excluding `is_ignored=True` assets; CONTEXT.md doesn't address either exclusion for Phase 41.
   - What's unclear: whether an analyst expects an ignored asset to still "count" toward the authoritative baseline, or a disabled scanner connector to still show its last-known %.
   - Recommendation: exclude both, mirroring the closest existing default (`is_ignored.is_(False)` on the query; filter `ConnectorConfig.is_enabled == True` when enumerating scanner cards) — least surprising, smallest deviation from existing conventions.

5. **Which `nav-items.ts` group should "Coverage" join — `TRIAGE_ITEMS` or `WORKFLOW_ITEMS`?**
   - What we know: D-03 says "alongside Vulnerabilities / Assets / Campaigns" — a phrase spanning both existing groups (Vulnerabilities/Assets are `TRIAGE_ITEMS`; Campaigns is `WORKFLOW_ITEMS`).
   - What's unclear: no locked placement.
   - Recommendation: `WORKFLOW_ITEMS`, alongside Campaigns and Exceptions — the two most recently added, most similar (analyst-workflow, non-chip-carrying) destinations.

6. **Is fixing the Intune sync defect (Pitfall 1) in scope for Phase 41?**
   - What we know: the bug is real, verified, and directly undermines D-01 for any Intune-reliant tenant; it is a small, contained fix (a handful of lines in one file) with an existing unit-test file (`test_intune_sync.py`) to extend.
   - What's unclear: whether the user wants this bundled into Phase 41 (whose stated scope is COV-01..03 only) or tracked as a separate defect ticket.
   - Recommendation: raise this explicitly during planning/discussion rather than silently fixing or silently ignoring it — either choice is defensible, but it changes the phase's task list either way.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Backend framework | pytest (`asyncio_mode = "auto"`), config in `backend/pyproject.toml [tool.pytest.ini_options]` |
| Backend quick run | `ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())") JWT_SECRET_KEY=test-secret pytest backend/tests/test_coverage.py -x` — per-file, not the whole `tests/` dir (MEMORY.md `getvul-backend-pytest-env`: whole-dir runs produce false failures) |
| Backend full suite | `make test` (repo-root `Makefile`) or `make test-local` |
| Frontend framework | Vitest (`frontend/vitest.config.mts`), co-located `*.test.tsx` |
| Frontend quick run | `cd frontend && npm test -- coverage` (name-filtered) |
| Frontend full suite | `cd frontend && npm test` + `npm run lint` |
| E2E framework | Playwright (`frontend/e2e/playwright.config.ts`), specs in `frontend/e2e/*.spec.ts` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| COV-01 | Blind-spot query returns authoritative-but-never-scanned assets; excludes scanner-touched and ignored assets | integration | `pytest backend/tests/test_coverage.py::test_blind_spot_list -x` | ❌ Wave 0 |
| COV-01 | `/dashboard/coverage` renders blind-spot table + D-11 no-inventory empty state + "quiet win" all-covered empty state | component | `npm test -- coverage-page` | ❌ Wave 0 |
| COV-02 | Per-connector coverage % math (`covered/total`; division-by-zero → `null`, never a crash or a misleading 0%) | unit | `pytest backend/tests/test_coverage.py::test_coverage_percentage -x` | ❌ Wave 0 |
| COV-02 | Stale-source flag fires at >7 days, not at exactly 7 (D-06 boundary) | unit | `pytest backend/tests/test_coverage.py::test_stale_threshold_boundary -x` | ❌ Wave 0 |
| COV-02 | `last_sync_status` is wire-normalized before reaching the coverage card (Pitfall 3 regression guard) | component | `npm test -- coverage-connector-card` | ❌ Wave 0 |
| COV-03 | Owner resolves → email sent to owner, `coverage.route_to_owner` audit row written | integration | `pytest backend/tests/test_coverage.py::test_route_to_owner_resolved -x` | ❌ Wave 0 |
| COV-03 | Owner unresolved → `_email_owners_and_admins` fallback fires, audit row still written (D-09) | integration | `pytest backend/tests/test_coverage.py::test_route_to_owner_fallback -x` | ❌ Wave 0 |
| COV-03 | Viewer role gets 403 on route-to-owner; can still `GET` the list (D-08 asymmetric RBAC) | integration | `pytest backend/tests/test_coverage.py::test_route_to_owner_rbac -x` | ❌ Wave 0 |
| COV-03 | Cross-tenant `asset_id` on route-to-owner returns 404, never 403/500 (IDOR) | integration | `pytest backend/tests/test_coverage.py::test_route_to_owner_cross_tenant_404 -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** the relevant quick-run command above (backend per-file `-x`, frontend `npm test -- coverage`)
- **Per wave merge:** `pytest backend/tests/test_coverage.py -x` (full file) + `npm test -- coverage`
- **Phase gate:** full suite green before `/gsd-verify-work` — `make test` + `npm test` + `npm run test:e2e` (extend `frontend/e2e/a11y-routes.spec.ts`'s per-route pattern, or add a small `coverage.spec.ts`, so the new route gets at least one smoke + axe pass)

### Wave 0 Gaps
- [ ] `backend/tests/test_coverage.py` — new file; no existing test file covers this module (entirely new backend domain)
- [ ] `frontend/src/app/(authed)/dashboard/coverage/page.test.tsx` — new, mirrors `assets/page.test.tsx`'s loading/empty/error/populated branch coverage
- [ ] `frontend/src/components/coverage/*.test.tsx` — new component tests for `CoverageConnectorCard` and `RouteToOwnerDialog`
- [ ] Framework install: none — pytest and Vitest are already fully configured; no new test framework needed

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no (unchanged) | inherits existing session-cookie auth |
| V3 Session Management | no (unchanged) | inherits existing Redis-backed session state |
| V4 Access Control | yes | `require_viewer` (GET summary/blind-spots) / `require_analyst` (POST route-to-owner) from `app.auth.rbac`; tenant_id in every WHERE clause, never fetch-then-filter |
| V5 Input Validation | yes (minimal surface) | FastAPI/Pydantic path-param UUID typing for `asset_id`; no free-text request body this phase (D-09 rejected manual owner entry) — the smallest input surface of any v5.0 mutation to date |
| V6 Cryptography | no (new work) | reuses existing Fernet-encrypted channel credentials via `_build_channel_config`; no new secret storage |
| V7 Error Handling & Logging | yes | `audit()`'s existing fail-closed pattern; errors surfaced via the existing `PartialFailureBanner` (no new error-message surface to sanitize) |
| V13 API and Web Service | yes | new endpoints mounted under the existing `/api/v1/` prefix convention (`/api/v1/coverage`), same auth middleware stack as every other router |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| IDOR on the blind-spot list / route-to-owner endpoint (guessing another tenant's asset UUID) | Information Disclosure / Tampering | tenant_id in the WHERE clause on every lookup; 404 (not 403) on a cross-tenant id — mirrors `exceptions/router.py::_get_exception_or_404`'s documented T-39-01 mitigation |
| Privilege escalation (a viewer triggers a notification) | Elevation of Privilege | `require_analyst` gate on the POST route; GET/list stays `require_viewer` — asymmetric, matches D-08 and the existing exceptions precedent |
| SSRF via a tenant-configured Slack/Teams webhook (D-09's channel-push leg) | Tampering | already mitigated upstream by `_validate_webhook_url` in `escalation_channels.py` — reused unmodified, never re-implemented |
| Audit-trail loss or tampering on a mutating action | Repudiation | `audit()`'s fail-closed, propagate-and-skip-commit pattern (D-08) |
| Mass assignment, if a manual owner-entry field is ever added later | Tampering | not needed this phase (D-09 rejected manual entry); if added later, follow `_AssetOwnerUpdate`'s `extra="forbid"` + field-validator precedent (`assets/router.py`) rather than a new looser schema |

## Sources

### Primary (HIGH confidence — direct codebase reads)
- `backend/app/assets/constants.py`, `models.py`, `directory.py`, `router.py` — source partition, Asset schema, owner resolution, existing facet-filter pattern, existing owner-assignment endpoint
- `backend/app/connectors/sync.py`, `jamf_sync.py`, `humaans_sync.py`, `intune_sync.py`, `schemas.py`, `scheduler.py`, `service.py` — sync-write behavior for every source class, the Intune defect, connector type registry, RBAC-adjacent sync-status normalization
- `backend/app/ticketing/models.py` — `ConnectorConfig`, `SyncLog` field definitions (the ground truth the Intune defect was checked against)
- `backend/app/vulnerabilities/models.py` — `VulnSource` enum
- `backend/app/notifications/alerts.py`, `service.py`, `escalation_channels.py`, `alerting_config.py` — owner/admin notification fan-out, channel dispatch + SSRF guard, alerting-config routing-key gap
- `backend/app/vulnerabilities/sla_tier_service.py` — `_build_channel_config`
- `backend/app/exceptions/router.py` — RBAC + audit + tenant-scoped-404 precedent for a new mutation-bearing module
- `backend/app/auth/rbac.py`, `dependencies.py` — the two parallel RBAC systems
- `backend/app/audit.py` — fail-closed `audit()` helper
- `backend/app/tenants/models.py` — `Tenant.sla_config`/`alerting_config`/`smtp_config` JSONB columns
- `backend/alembic/versions/045_add_seen_by_sources_gin.py` — the GIN index
- `backend/tests/conftest.py`, `test_exceptions.py`, `test_campaigns.py`, `test_intune_sync.py`, `test_asset_owner_reassign.py` — test harness conventions, env-var gotcha, existing coverage of the owner-assignment endpoint and Intune's pure helpers
- `backend/pyproject.toml`, root `Makefile` — test framework config and run commands
- `frontend/src/components/ui/stat-strip.tsx`, `ToastProvider.tsx` — layout primitive, toast system (already implemented)
- `frontend/src/components/connectors/sync-status-pill.tsx`, `connector-mark.tsx`, `types.ts` — status normalization contract, provider enumeration (no Tenable/AWS Inspector)
- `frontend/src/components/states/empty-state.tsx` — compound empty-state primitive
- `frontend/src/components/vulnerabilities/drill-panel.tsx` — generalized `idKey`/`renderContent` contract
- `frontend/src/components/exceptions/exception-grant-dialog.tsx`, `exceptions-table.tsx` — confirm-dialog + day-diff-copy precedent
- `frontend/src/app/(authed)/dashboard/assets/page.tsx`, `tickets/page.tsx` — the two competing list-page patterns (navigate vs. `DrillPanel`)
- `frontend/src/components/shell/nav-items.ts` — route-naming convention (Pitfall 2)
- `frontend/src/lib/queries/use-assets.ts`, `use-reassign-asset.ts`, `keys.ts`, `use-connectors-admin.ts` — query-hook and cache-key conventions, existing owner-mutation hook
- `frontend/package.json`, installed `lucide-react` package — dependency + icon verification
- `.planning/phases/40-proactive-alerting-digests/40-CONTEXT.md` — D-10 owner-resolution fallback precedent that Phase 41's D-09 mirrors
- `.planning/config.json` — confirms `nyquist_validation` and `security_enforcement` are both absent (treated as enabled)

No Context7/WebSearch/WebFetch lookups were needed for this phase — it introduces zero new third-party dependencies and no new external technology; every claim above was verified directly against the running codebase, consistent with CONTEXT.md's own framing of this phase as "mostly a read-side reconciliation over data GetVul already has."

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — zero new dependencies; every module recommended for reuse was opened and read directly
- Architecture: HIGH — the reconciliation pattern, RBAC, audit, and notification fan-out were all verified against currently-shipping code paths (some, like `_fire_kev_epss_alert`, are a near-exact behavioral template for COV-03)
- Pitfalls: HIGH for 7 of 8 catalogued pitfalls (each verified by reading both sides of the relevant contract); MEDIUM for Pitfall 7's *resolution* (the routing-key gap itself is a verified fact, but the right fix is a design judgment, not a fact)

**Research date:** 2026-08-20
**Valid until:** 2026-09-19 (30 days — stable internal codebase, no fast-moving external dependency to re-check)
