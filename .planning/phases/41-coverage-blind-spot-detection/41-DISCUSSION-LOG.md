# Phase 41: Coverage & Blind-Spot Detection - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-20
**Phase:** 41-coverage-blind-spot-detection
**Areas discussed:** Blind-spot definition, Coverage view shape, Coverage % + staleness, Owner-routing action, Compute cadence, No-inventory empty state, Unresolvable-owner fallback, seen_by_sources integrity

---

## Blind-spot definition — Authoritative inventory scope

| Option | Description | Selected |
|--------|-------------|----------|
| MDM+HR asset rows only | Baseline = assets with an ENRICHMENT source in seen_by_sources; IdP=users, CMDB=absent documented as deferred gap | ✓ |
| MDM+HR + IdP user-device join | Also derive expected devices from IdP users (new inference) | |
| Add a CMDB connector now | Build CMDB import as authoritative source | |

**User's choice:** MDM+HR asset rows only → D-01
**Notes:** Honest to what actually produces device inventory today; IdP directory-sync creates users not assets, no CMDB connector exists.

## Blind-spot definition — What defines a blind spot

| Option | Description | Selected |
|--------|-------------|----------|
| No scanner source at all | Authoritative asset with zero SCANNER_SOURCES in seen_by_sources | ✓ |
| No scanner OR stale/zero-finding | Broader coverage-risk bucket incl. stale + zero-findings | |
| Tiered severity | Unscanned > Stale > Clean-but-zero-findings tiers | |

**User's choice:** No scanner source at all → D-02
**Notes:** Asset-level staleness kept out of the blind-spot list; handled at connector level in COV-02.

---

## Coverage view shape — Placement

| Option | Description | Selected |
|--------|-------------|----------|
| New top-level nav page | Dedicated 'Coverage' sidebar entry | ✓ |
| Tab under Assets | Coverage tab on /assets | |

**User's choice:** New top-level nav page → D-03

## Coverage view shape — Layout

| Option | Description | Selected |
|--------|-------------|----------|
| Strip + unmanaged list | Per-connector coverage strip on top + unmanaged-asset list below (reuse Assets primitives) | ✓ |
| Two separate sections/pages | Split metrics and list into distinct sub-views | |

**User's choice:** Strip + unmanaged list → D-04

---

## Coverage % + staleness — Coverage % computation

| Option | Description | Selected |
|--------|-------------|----------|
| Per-scanner of authoritative | Per scanner: seen-by-that-scanner / total authoritative | ✓ |
| Overall scanned % | Single number: any-scanner / total authoritative | |
| Both | Headline overall + per-scanner breakdown | |

**User's choice:** Per-scanner of authoritative → D-05

## Coverage % + staleness — Stale threshold

| Option | Description | Selected |
|--------|-------------|----------|
| Fixed default, e.g. 7d | Single default from ConnectorConfig.last_sync_at | ✓ |
| Tenant-configurable | Expose N on settings pane | |
| Per-connector-interval-derived | Derive from sync_interval_minutes | |

**User's choice:** Fixed default 7d → D-06

---

## Owner-routing action — What route-to-owner does

| Option | Description | Selected |
|--------|-------------|----------|
| Assign owner + notify email | Resolve/confirm owner + notify-owner email; no fake finding/ticket | ✓ |
| Create a coverage ticket | Jira/Asana ticket assigned to owner (bends vulnerability_id FK) | |
| Assign owner only | Set owner field, no email/ticket | |

**User's choice:** Assign owner + notify email → D-07
**Notes:** Flagged as open research: assets have no dedicated owner column (owner resolved via get_directory_user); whether to persist an override is a planner call.

## Owner-routing action — Audit/RBAC

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — audit + RBAC | Fail-closed audit() + gate to analyst+ | ✓ |
| Audit only | Audit but available to all roles | |

**User's choice:** Yes — audit + RBAC → D-08

---

## Compute cadence

| Option | Description | Selected |
|--------|-------------|----------|
| Live on-read | Compute per request from seen_by_sources + ConnectorConfig | ✓ |
| Precomputed/materialized | Nightly job materializes coverage % + flags | |

**User's choice:** Live on-read → D-10

## No-inventory empty state

| Option | Description | Selected |
|--------|-------------|----------|
| Guided empty state | 'Connect an inventory source' EmptyState linking to /connectors | ✓ |
| Show scanner-only view | Render coverage using total assets as denominator | |

**User's choice:** Guided empty state → D-11

---

## Unresolvable-owner fallback

| Option | Description | Selected |
|--------|-------------|----------|
| Fallback to admins + channel | Notify admins + tenant alert channel (Phase 40 D-10 precedent) | ✓ |
| Allow manual owner entry | Prompt analyst for owner email | |
| Block with message | Disable action, show 'no owner resolved' | |

**User's choice:** Fallback to admins + channel → D-09

## seen_by_sources integrity

| Option | Description | Selected |
|--------|-------------|----------|
| Trust + treat empty as unscanned | Trust as source of truth; verify check in research, no backfill unless gap found | ✓ |
| Backfill migration first | Recompute seen_by_sources from vuln rows before trusting | |

**User's choice:** Trust + treat empty as unscanned → D-12

---

## Claude's Discretion
- Empty-state / blind-spot-list copy (per copy-voice.md).
- Optional overall headline number alongside the per-scanner strip.
- Notify-owner email template wording.

## Deferred Ideas
- CMDB connector (ServiceNow/CSV import) — its own phase.
- IdP user→device inference — future phase.
- Tenant-configurable / interval-derived stale threshold.
- Precomputed/materialized coverage rollup.
- Manual owner-entry UI for unresolvable owners.
