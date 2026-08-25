# Phase 38: Remediation Campaigns - Research

**Researched:** 2026-08-17
**Domain:** Internal composition (Postgres/SQLAlchemy/Alembic + FastAPI + Next.js) — no new external technology
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Campaign grouping & scope (CAMP-01)**
- **D-01 — Campaign is 1:1 with an existing remediation group.** A campaign wraps one `Vulnerability.remediation_id` group (the shared patch/product/action GetVul already groups by via `get_remediations_grouped()`). Analyst launches a campaign directly from the remediation view — "one action." No new cross-CVE / multi-fix grouping engine.
- **D-02 — Whole group, always (no asset subset).** A campaign is *every* finding sharing that `remediation_id` — present and future. There is no launch-time subset selection; scoping to specific assets is out.
- **D-03 — Live / dynamic membership.** Any finding matching the campaign's `remediation_id` is a member — including findings a later scan discovers on a newly-seen asset. The denominator can grow; burndown reflects true current exposure. Reversibility: costly.
- **D-11 — One active campaign per (tenant, remediation_id).** Enforce uniqueness. Launching a campaign on a group that already has an active one **opens the existing campaign** rather than creating a duplicate. Reversibility: one-way (DB unique constraint, partial, on active status).

**Bulk ticketing (CAMP-02)**
- **D-04 — One ticket per owner.** Each owner gets a single ticket covering all their affected assets in the campaign. Reuses the existing N-rows-share-one-`external_ticket_url` linkage, grouped by assignee.
- **D-05 — Owner routing is reused verbatim, never re-derived.** Assignee comes from the existing inline derivation (`asset.assigned_user` / `asset.mdm_details` Humaans email) in `ticketing/service.py`. No campaign-level re-derivation; no manual owner override silently dropped.
- **D-06 — Adopt existing tickets; create only for the rest.** Findings already linked to a live ticket (from single-finding ticketing or an automation rule) are folded into campaign tracking as-is — no duplicate. Reuses the existing dedup-by-URL logic.
- **D-08 — Owner-less findings → unassigned ticket in the connector's default project.** A finding with no derivable owner still gets a ticket (unassigned, default project/board) — nothing silently dropped.
- **D-10 — New live-joined members are NOT auto-ticketed.** A finding that joins a live campaign after launch is counted in progress but stays un-ticketed until the analyst re-runs bulk-create (which adopts existing per D-06 and tickets only the newcomers). Never fires automatically on membership change.

**Live progress & MTTR (CAMP-03)**
- **D-07 — Compute-on-read.** Progress (open / in-progress / done %) and campaign MTTR are aggregated from member finding statuses + `RemediationEvent` rows at request time — no persisted progress columns, no scheduler refresh path. Mirrors how ticket stats re-aggregate today.
- **D-09 — "Done" = rescan-verified REMEDIATED only (carry-forward, Phase 37 D-03).** A campaign member counts as done/remediated only when the scanner re-scan verified it (status REMEDIATED via `mark_vulnerability_remediated`). A done/closed ticket drives the finding to IN_PROGRESS, never closes it. In-progress % keys off status IN_PROGRESS.
- **D-12 — Campaign MTTR = average of member finding MTTRs.** Average of the per-finding durations (`first_detected_at → remediated_at`) from `RemediationEvent` rows over remediated members. Consistent with Phase 36's tier MTTR; reads the same data, never re-derives it.

**Lifecycle & audit (CAMP-04)**
- **D-13 — Auto-complete + manual early close.** A campaign auto-marks complete when 100% of its (live) members are rescan-verified remediated; an analyst may also manually close early. Both transitions are audited.
- **D-14 — Auto-reactivate on recurrence (Phase 37 D-04 interaction).** If a completed campaign's member finding reopens via Phase 37 reopen-on-recurrence, it is OPEN again and still matches the `remediation_id`, so with compute-on-read (D-07) the campaign flips complete→active automatically and its % drops. Campaign status is derived, not a frozen terminal state.
- **D-15 — Every campaign action audited via the existing `audit()` helper.** create, bulk-assign (each run), and close route through `app/audit.py::audit` (tenant-scoped, fail-closed) — same discipline as Phase 36/37 status writes.

**RBAC**
- **D-16 — Analyst+ for all campaign writes.** create / bulk-assign / close require `require_analyst`, consistent with every existing ticketing write. Campaigns are a ticketing workflow, not admin config. Reads follow the existing viewer/analyst pattern.

### Claude's Discretion (planner/researcher decide)
- Campaign table schema, column names, status enum values, and the Alembic migration structure (including the partial unique constraint for D-11).
- Whether the campaign router is a new `app/campaigns/` module or lives under `app/ticketing/` — follow the closest existing module convention.
- Exact aggregation SQL for compute-on-read progress/MTTR (reuse the `get_mttr_by_tier` / ticket-stats re-aggregation shapes).
- How "adopt existing ticket" (D-06) detects a live link (by `external_ticket_url` / `vulnerability_id` join) — reuse the current dedup path.
- The campaign-view UI shape (list + burndown detail) — defer to `/gsd-ui-phase` / UI-SPEC and the `sketch-findings-getvul` design system.

### Deferred Ideas (OUT OF SCOPE)
- **Cross-CVE / multi-fix campaigns** (one campaign spanning several `remediation_id`s / CVEs) — rejected for this phase (D-01 keeps it 1:1).
- **Launch-time asset-subset scoping** (D-02 rejected it).
- **Auto-ticket-on-join** (D-10 rejected it).
- **Scheduler-refreshed progress snapshot** (D-07 chose compute-on-read) — revisit only if compute-on-read becomes a read-scale problem. **This directly rules out adding a new scheduler tick for ANY campaign-derived state, including completion detection — see Architecture Patterns, Pattern 6.**
- **Campaign-view visual design** — handled by `/gsd-ui-phase` (UI-SPEC, already produced and checker-approved), not deferred to a later milestone.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CAMP-01 | Group findings by shared fix (CVE / patch / product) across multiple assets and owners into a campaign in one action | `get_remediations_grouped()` is the existing grouping engine (reused verbatim, D-01). New `Campaign` model + partial-unique-index get-or-create pattern (Architecture Patterns 1–3, Code Examples 1–2). New entry-point list page required (no existing frontend consumer of `/remediations/grouped` today — confirmed by direct search). |
| CAMP-02 | Bulk-create/assign tickets for a campaign, respecting existing owner routing | `create_remediation_ticket()`'s N-rows-share-one-URL primitive re-carved by owner (Code Example 3); owner derivation copied verbatim from `ticketing/service.py:608-616/457-461`; dedup-by-`vulnerability_id` adoption logic (Code Example 3); Common Pitfall 1 (rule-engine interaction) must be resolved by the implementation. |
| CAMP-03 | Live per-campaign progress (open / in-progress / done, % remediated) and campaign MTTR | Compute-on-read aggregation mirroring `get_mttr_by_tier()` (Code Example 4); Common Pitfall 2 (status-filter denominator bug) is the single highest-risk implementation detail for this requirement. |
| CAMP-04 | All campaign actions are audited | `app/audit.py::audit()` + `require_analyst` wired into every write endpoint (Code Example 5); system-actor pattern (`system:campaign-complete`) for the derived auto-complete/reactivate transitions, mirroring `reopen_vulnerability`'s `system:rescan-reopen` precedent. |
</phase_requirements>

## Summary

Phase 38 is ~95% composition of already-shipped GetVul primitives — there is no new external library, no new infrastructure, and no new architectural tier. The four requirements decompose into: (1) a new, small `campaigns` table that persists a thin identity wrapper around an existing `remediation_id` grouping key, (2) a re-carve of the existing `create_remediation_ticket()` bulk-ticketing primitive — splitting its single "one ticket for the whole group" behavior into "one ticket per owner" — while reusing its owner-derivation and dedup-by-URL logic verbatim, (3) two SQL aggregation queries (progress buckets + MTTR average) that mirror the shape of `get_mttr_by_tier()` and the existing ticket-stats re-aggregation, computed fresh on every read with no persisted snapshot, and (4) wiring every write through the existing `audit()` + `require_analyst` pair, exactly as Phase 36/37 did for SLA and sync writes.

The main engineering risk is not "what to build" (CONTEXT.md's 16 locked decisions and canonical refs answer that almost completely) but three sharp edges this research surfaces that CONTEXT.md does not spell out: (a) the existing `get_remediations_grouped()`/`_base_open_vulns()` filter **excludes REMEDIATED status entirely** — naively reusing it for campaign membership would make "% remediated" permanently read 0%; (b) `create_remediation_ticket()`'s pre-existing dedup check (`Ticket.created_by_rule == remediation_id`) will not recognize campaign-created tickets unless the campaign's own `created_by_rule` value is chosen to match it, creating a latent double-ticket path if a `per_remediation` automation rule later fires on a remediation_id a campaign already ticketed; and (c) CONTEXT.md's D-07/D-13/D-14 combination (compute-on-read + audited auto-complete + derived-not-frozen status) requires *some* persisted one-bit marker (`closed_at`) purely to gate a "fire this audit exactly once" boundary — the exact mechanism for detecting that transition is genuinely undecided in CONTEXT.md, and this research recommends a lazy-on-read detection (zero changes to Phase 36/37 files) over a new scheduler tick (which the Deferred Ideas section explicitly rules out) or an inline hook into `mark_vulnerability_remediated` (which would grow that already-shared choke-point with an unrelated concern).

**Primary recommendation:** Build a new top-level `app/campaigns/` module (`models.py`/`schemas.py`/`service.py`/`router.py`, mirroring `app/cspm/` and `app/notifications/` exactly), with a `Campaign` table storing only identity + lifecycle columns (no denormalized label snapshot, no persisted progress) gated by a partial unique index on `(tenant_id, remediation_id) WHERE closed_at IS NULL`; re-carve `create_remediation_ticket()`'s owner-info-gathering shape into a per-owner loop; and compute all progress/MTTR/status values fresh on every read using the corrected status filter (Common Pitfall 2).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Campaign identity + lifecycle persistence (`closed_at`) | API/Backend | Database | New `campaigns` table; a thin identity+audit-gate row, not a data warehouse |
| Campaign membership resolution (which findings belong) | Database (via query) | API/Backend | D-02/D-03: always a live `WHERE remediation_id = :x` join against `vulnerabilities`, never a stored membership table |
| Bulk ticket creation + per-owner carve-up | API/Backend | — | Orchestrates `TicketingClient` dispatch (`app/ticketing/dispatch.py`); pure backend business logic, no DB-only or browser-only concern |
| Owner routing (assignee resolution) | API/Backend | — | Read-only reuse of `asset.assigned_user`/`asset.mdm_details["humaans_email"]`; never re-derived at the campaign layer (D-05) |
| Progress % + MTTR aggregation | Database (SQL aggregate) | API/Backend | Compute-on-read (D-07): the aggregation itself is a SQL `GROUP BY`/`AVG`, invoked fresh per API request — no caching tier |
| Audit trail | API/Backend | Database | `app/audit.py::audit()` writes to the existing `audit_logs` table; fail-closed transactional guarantee lives in the backend |
| Campaign list / detail UI | Browser (Next.js client component) | Frontend Server (SSR shell) | Standard TanStack-Query-driven client rendering, matching every other list/detail screen in this app |
| Remediation-grouped entry-point UI (new page) | Browser | Frontend Server (SSR shell) | Same tier as above — this is a **new page**, not an extension of an existing one (see Common Pitfall 11) |
| RBAC enforcement | API/Backend | — | FastAPI `Depends(require_analyst)` / `Depends(require_viewer)` — never trust a frontend-only gate |

## Project Constraints (from CLAUDE.md)

- Frontend must use Next.js 15 App Router + React 19 + TypeScript 5.5 + Tailwind 3.4, consuming `sketch-findings-getvul`'s CSS-variable design tokens (`foundation.md`) — never freehand hex colors.
- Backend must use FastAPI + Postgres + Redis; state lives in Postgres/Redis, never in-process dicts (v1.0 Phase 1 precedent).
- Inter + JetBrains Mono are locked fonts — no substitution. JetBrains Mono (via `--font-mono`) is required for the campaign remediation identifier, MTTR durations, counts, and percentages per the UI-SPEC.
- Every screen must ship empty/loading/error states — the UI-SPEC already resolves 21/40 states as `covered` and flags 10 as `backstop` (implementation-time verification against `state-patterns.md`, not a deferred gap).
- No Tailwind admin-template patterns; no generic SaaS copy ("Welcome!", "Please...") — `copy-voice.md` rules apply verbatim; the UI-SPEC's Copywriting Contract already supplies phase-specific copy for every action/error/empty state.
- `.claude/skills/sketch-findings-getvul/` must be read before any frontend implementation on this phase — the UI-SPEC (already produced, checker-APPROVED 6/6 dimensions) is the binding contract; this research does not re-litigate visual design.
- v5.0 hard constraints (from STATE.md, apply across every v5.0 phase): single-VM Docker Compose, in-process asyncio scheduler only (**no new scheduler tick** — reinforces the Deferred Ideas rejection of a scheduler-refreshed snapshot); every query tenant_id-scoped; audit events required for every new mutating action; lane discipline (no new scanner/patch-deployer/agent; v4.0 risk score and remediation grouping consumed, never re-derived).

## Standard Stack

This phase introduces **zero new dependencies**. All work composes already-installed libraries. Versions confirmed directly from the repo's own manifests (not training-data recall):

### Core (backend — already installed, verified via `backend/pyproject.toml`)
| Library | Version constraint | Purpose | Why no change needed |
|---------|---------|---------|--------------|
| fastapi | `>=0.115,<1.0` | HTTP framework | New `campaigns` router registers exactly like `tickets`/`vulnerabilities` routers |
| sqlalchemy | `[asyncio]>=2.0` | ORM / async DB access | New `Campaign` model uses the same `Mapped`/`mapped_column` style as every existing model |
| alembic | `>=1.14` | Migrations | New migration chains off the current head (`048_add_clean_scan_streak`) |
| pydantic | `>=2.9` | Request/response schemas | New `schemas.py` mirrors `ticketing/schemas.py`'s `extra="forbid"` convention |
| pytest / pytest-asyncio | `>=8.3` / `>=0.24` | Test framework | New `tests/test_campaigns.py` uses the existing `conftest.py` fixture surface |

### Core (frontend — already installed, verified via `frontend/package.json`)
| Library | Version | Purpose | Why no change needed |
|---------|---------|---------|--------------|
| Next.js / React / TypeScript | 15 / 19 / 5.5 | App shell | New routes under `(authed)/dashboard/` follow the existing App Router convention |
| @tanstack/react-query | (existing) | Data fetching/caching | New `use-campaigns.ts` mirrors `use-vuln-escalations.ts` exactly |
| lucide-react | `^0.383.0` | Icons | `FolderKanban`-style icon already used for a recent nav addition (Asset groups); pick a new icon for "Campaigns" (e.g. `Target`/`Flag`) — `--legacy-peer-deps` required per project memory when touching `node_modules` |
| vitest | `^4.1.6` | Unit/component tests | New component tests mirror `RiskRing.test.tsx`/`severity-ribbon` test conventions |
| @playwright/test | `^1.61.1` | E2E tests | New e2e spec follows the existing seeded-data caution (see Validation Architecture) |

**Installation:** None required — `npm install` / `pip install -e .` already cover everything this phase needs.

**Version verification:** Not applicable (no new package versions to verify against a registry) — every fact above was read directly from this repository's own lockfiles/manifests `[VERIFIED: backend/pyproject.toml, frontend/package.json]`, which is a stronger source than `npm view`/PyPI for "what does THIS codebase actually use."

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| A `campaigns` table + live join | A `campaign_members` join table (frozen snapshot at launch) | Rejected by D-02/D-03 explicitly — "Reversibility: costly." Not a live option for this phase. |
| Lazy-on-read completion detection | A new scheduler tick (mirroring `app/connectors/scheduler.py`) | Rejected — CONTEXT.md's Deferred Ideas explicitly lists "Scheduler-refreshed progress snapshot" as rejected; a completion-detection tick is the same category of mechanism. |
| Lazy-on-read completion detection | Inline hook inside `mark_vulnerability_remediated()` | Viable alternative (see Architecture Pattern 6) — works, but grows an already-shared Phase 36 choke-point with a Phase-38-specific concern, and every future phase (39, 40...) that wants a "when a finding closes" hook would compound this. Lazy-on-read keeps the concern local to `app/campaigns/`. |

## Architecture Patterns

### System Architecture Diagram

```
                    ┌─────────────────────────────────────────┐
                    │  Remediation-grouped list (NEW page)     │
                    │  GET /vulnerabilities/remediations/grouped│  <- existing endpoint, no frontend consumer yet
                    └───────────────┬───────────────────────────┘
                                    │ analyst clicks "Start campaign"
                                    ▼
                    ┌─────────────────────────────────────────┐
                    │ POST /api/v1/campaigns {remediation_id}  │  require_analyst
                    │  - SELECT existing WHERE closed_at IS NULL│
                    │  - if found: return it (no audit, toast) │
                    │  - else: INSERT, catch IntegrityError,   │
                    │    audit("campaign.create")              │
                    └───────────────┬───────────────────────────┘
                                    │ campaign.id
                                    ▼
     ┌──────────────────────────────────────────────────────────────────┐
     │ GET /api/v1/campaigns/{id}  (require_viewer, called on every load)│
     │                                                                    │
     │  live JOIN vulnerabilities WHERE remediation_id = campaign.rem_id │
     │       ├─ status IN (OPEN, IN_PROGRESS, REMEDIATED)  <- Pitfall 2  │
     │       ├─ COUNT(*) FILTER (status='REMEDIATED')  -> done           │
     │       ├─ COUNT(*) FILTER (status='IN_PROGRESS') -> in_progress    │
     │       └─ AVG(RemediationEvent.duration_seconds) JOIN by vuln_id   │
     │                                                                    │
     │  derive display_status:                                          │
     │       closed_at IS NOT NULL  OR  done == total (>0)  => "Complete"│
     │       else                                            => "Active"│
     │                                                                    │
     │  lazy transition detection (Pattern 6):                          │
     │       if just-computed complete AND closed_at IS NULL:           │
     │            UPDATE campaigns SET closed_at=now, close_trigger=auto│
     │            audit("campaign.close", system actor)                 │
     │       if just-computed NOT complete AND closed_at IS NOT NULL:   │
     │            UPDATE campaigns SET closed_at=NULL                   │
     │            audit("campaign.reactivate", system actor)            │
     └───────────────────────────────┬────────────────────────────────────┘
                                      │ analyst clicks "Create tickets"
                                      ▼
     ┌──────────────────────────────────────────────────────────────────┐
     │ POST /api/v1/campaigns/{id}/bulk-assign  (require_analyst)       │
     │  1. live members = same query as above, status IN (OPEN,IN_PROG)│
     │  2. exclude vuln_ids with an existing UNRESOLVED Ticket row      │
     │     (D-06 adopt) -> "adopted" count                              │
     │  3. group remaining vulns by owner_email                        │
     │     (asset.mdm_details["humaans_email"], D-05 verbatim)         │
     │  4. for each owner bucket (incl. None -> D-08 unassigned):      │
     │       client.create(...) via build_ticketing_client()           │
     │       N Ticket rows share one external_ticket_url               │
     │       vuln.status = "IN_PROGRESS"                               │
     │  5. audit("campaign.bulk_assign") EVERY run (D-10)               │
     └───────────────────────────────┬────────────────────────────────────┘
                                      │
                                      ▼
     ┌──────────────────────────────────────────────────────────────────┐
     │  Existing ticketing lifecycle takes over unchanged:               │
     │  Phase 37 sync-back (ticket done -> IN_PROGRESS, never closes)   │
     │  Phase 37 rescan auto-close (2 clean scans -> REMEDIATED)        │
     │  Phase 37 reopen-on-recurrence (REMEDIATED -> OPEN)              │
     │       -> feeds directly back into the SAME live join above,      │
     │          no campaign-specific code needed for D-14 to "just work"│
     └────────────────────────────────────────────────────────────────────┘

     Analyst "Close campaign" (manual early close):
     POST /api/v1/campaigns/{id}/close  (require_analyst)
       -> UPDATE campaigns SET closed_at=now, closed_by_user_id=user.id
       -> audit("campaign.close", trigger="manual")
```

### Recommended Project Structure
```
backend/app/campaigns/          # NEW top-level module — mirrors app/cspm/, app/notifications/
├── __init__.py
├── models.py                   # Campaign (SQLAlchemy model)
├── schemas.py                  # CampaignCreateRequest, CampaignResponse, BulkAssignRequest, etc.
├── service.py                  # get_or_create_campaign, compute progress/MTTR, bulk_create_campaign_tickets
└── router.py                   # POST /, GET /, GET /{id}, POST /{id}/bulk-assign, POST /{id}/close

backend/alembic/versions/
└── 049_add_campaigns.py        # chains off 048_add_clean_scan_streak (confirmed current head)

frontend/src/
├── app/(authed)/dashboard/
│   ├── vulnerabilities/remediations/page.tsx   # NEW entry-point list (see Open Question 3 re: exact path)
│   └── campaigns/
│       ├── page.tsx             # campaign list view
│       └── [id]/page.tsx        # campaign detail view (if full-page, not drill panel — planner's choice per UI-SPEC)
├── components/campaigns/        # NEW — mirrors components/tickets/, components/assets/
│   ├── campaign-burndown-card.tsx   # composes RiskRing.tsx (score = pct_remediated) + a new status-breakdown ribbon
│   ├── campaign-status-ribbon.tsx   # new sibling to severity-ribbon.tsx, status-colored not severity-colored
│   ├── campaigns-table.tsx
│   └── campaigns-chip-bar.tsx       # mirrors tickets-chip-bar.tsx / assets-chip-bar.tsx
└── lib/queries/
    └── use-campaigns.ts          # mirrors use-vuln-escalations.ts; add `campaigns` block to keys.ts
```

### Pattern 1: New top-level domain module, not nested under `ticketing/` or `vulnerabilities/`
**What:** `app/campaigns/` gets its own `models.py`/`schemas.py`/`service.py`/`router.py`, registered in `main.py` exactly like every other domain.
**When to use:** When the new concern (a) introduces its own persisted table, (b) is a permanent, user-facing entity (not an admin utility), and (c) synthesizes two existing domains roughly equally.
**Why not nest under `ticketing/` or `vulnerabilities/`:** Campaigns read from `vulnerabilities` (membership) AND write to `ticketing` (bulk-create) roughly equally — nesting under either creates an arbitrary ownership bias. The one counter-example in this codebase, `app/vulnerabilities/risk_cutover_router.py`, is a single-purpose ADMIN UTILITY bolted onto an existing migration workflow (threshold-ack + backfill-enqueue for the Phase 34 risk cutover) — not a new persistent entity with its own table and nav destination. Campaigns is the latter.
```python
# Source: direct read of backend/app/notifications/ and backend/app/cspm/ directory listings
# Both are: __init__.py, models.py, router.py, service.py(+schemas.py) — confirms this is
# the codebase's own convention for "new small top-level domain," not an invented pattern.
```
**Registration** (mirrors `backend/app/main.py:309-320` verbatim):
```python
# app/main.py
from app.campaigns.router import router as campaigns_router
...
app.include_router(campaigns_router, prefix="/api/v1/campaigns", tags=["Campaigns"])
```

### Pattern 2: Live-join membership, zero denormalized snapshot columns
**What:** The `Campaign` row stores ONLY identity (`tenant_id`, `remediation_id`) + lifecycle (`closed_at`, `created_by_user_id`, `closed_by_user_id`) + timestamps. It does **not** store `remediation_action`/`affected_product`/member counts/percentages anywhere.
**When to use:** Whenever display data (label, counts, %) is fully derivable from a live join that already exists elsewhere in the codebase for the identical grouping key.
**Why:** `get_remediations_grouped()` (the function D-01 explicitly says a campaign wraps) has **no separate identity table of its own** — it reads `remediation_action`/`affected_product` live off `Vulnerability` rows, grouped by `remediation_id`, every single call. A campaign snapshotting these fields at create-time would be the *first* denormalization of this concept in the codebase, contradicting D-07's "no persisted progress columns" spirit and D-03's "membership can grow" philosophy (a snapshotted label could drift from what current members actually show). The UI-SPEC's own E6 "empty" state ("Zero-member campaign → ring shows 0%... renders, never crashes on a 0/0 denominator") only makes sense if label/counts are computed fresh, since a truly zero-member campaign has nothing to snapshot.
```python
# Source: direct read of backend/app/vulnerabilities/remediation_service.py:53-97 —
# get_remediations_grouped() groups Vulnerability rows live; there is no
# "Remediation" identity table anywhere in this codebase. A Campaign row
# should follow the identical philosophy: identity + lifecycle only.
```

### Pattern 3: Race-safe get-or-create against the D-11 partial unique index
**What:** `POST /campaigns` does SELECT-first (fast path for the common "campaign already exists" case, D-11's "opens the existing campaign" UX), then INSERT wrapped in a nested transaction, catching `IntegrityError` as the race backstop.
**When to use:** Any create-or-open endpoint backed by a partial unique index.
**Example (mirrors an exact existing precedent):**
```python
# Source: backend/app/vulnerabilities/sla_tier_service.py:406-428 (SlaEscalationEvent
# race-safe insert against SlaEscalationEvent.uq_escalation_once) — this is a
# DIRECT, proven-in-this-codebase precedent for the identical problem shape
# ("insert unless a matching unique-constrained row already exists").
from sqlalchemy.exc import IntegrityError

async def get_or_create_campaign(db, tenant_id, remediation_id, user) -> tuple[Campaign, bool]:
    existing = (await db.execute(
        select(Campaign).where(
            Campaign.tenant_id == tenant_id,
            Campaign.remediation_id == remediation_id,
            Campaign.closed_at.is_(None),
        )
    )).scalar_one_or_none()
    if existing:
        return existing, False  # already_existed -> D-11 redirect toast, no audit

    campaign = Campaign(tenant_id=tenant_id, remediation_id=remediation_id, created_by_user_id=user.id)
    db.add(campaign)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError:
        # Another request won the race between our SELECT and INSERT.
        existing = (await db.execute(
            select(Campaign).where(
                Campaign.tenant_id == tenant_id,
                Campaign.remediation_id == remediation_id,
                Campaign.closed_at.is_(None),
            )
        )).scalar_one()
        return existing, False
    return campaign, True
```

### Pattern 4: Per-owner ticket carve-up (re-carving `create_remediation_ticket`)
**What:** `create_remediation_ticket()` (`ticketing/service.py:548-706`) today creates exactly **one** ticket for the whole remediation group — it gathers per-host owner info into its description text but never splits by owner. D-04 requires the opposite split: one ticket **per owner**, each covering that owner's subset of hosts/vulns.
**When to use:** This is the single largest net-new code surface in the phase. Confirm this before planning: the existing primitive is NOT a per-owner primitive today; it must be genuinely re-carved, not called N times with a filter (there is no `owner_email` filter parameter on `create_remediation_ticket`).
```python
# Adapted from backend/app/ticketing/service.py:548-706's structure — same
# owner-derivation precedence (lines 608-616), same N-rows-share-one-URL
# linkage (lines 664-692), same _provider_create_kwargs/recompute_ticket_sla
# reuse — but looped per owner bucket instead of once for the whole group.

async def bulk_create_campaign_tickets(db, tenant_id, user, campaign, provider, project_key, client, due_days=None):
    # 1. Live members. NOTE: status filter is OPEN/IN_PROGRESS here (matches
    #    every existing ticket-creation primitive) — members already
    #    REMEDIATED don't need a new ticket. This is intentionally NARROWER
    #    than the progress-aggregation filter in Pattern 5/Pitfall 2.
    rows = (await db.execute(
        select(Vulnerability, Asset.hostname, Asset.mdm_details)
        .outerjoin(Asset, Vulnerability.asset_id == Asset.id)
        .where(
            Vulnerability.tenant_id == tenant_id,
            Vulnerability.remediation_id == campaign.remediation_id,
            Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
        )
    )).all()

    # 2. D-06 adopt: exclude vulns with ANY existing unresolved Ticket row,
    #    regardless of what created it (single-finding create, host ticket,
    #    per-remediation ticket, or an automation rule).
    vuln_ids = [v.id for v, *_ in rows]
    already_ticketed = set((await db.execute(
        select(Ticket.vulnerability_id).where(
            Ticket.tenant_id == tenant_id,
            Ticket.vulnerability_id.in_(vuln_ids),
            Ticket.resolved_at.is_(None),
        )
    )).scalars().all())
    unticketed = [(v, hostname, mdm) for v, hostname, mdm in rows if v.id not in already_ticketed]
    adopted_count = len(vuln_ids) - len(unticketed)

    # 3. Carve by owner (D-05 verbatim derivation; D-08 None bucket = unassigned).
    owner_groups: dict[str | None, list] = {}
    for v, hostname, mdm in unticketed:
        owner_email = (mdm or {}).get("humaans_email") or None
        owner_groups.setdefault(owner_email, []).append((v, hostname))

    created, failed_owners = 0, []
    now = datetime.now(UTC)
    for owner_email, members in owner_groups.items():
        notes = _build_owner_ticket_description(members)  # new, campaign-scoped
        max_sev = max((m[0].severity for m in members), key=lambda s: _SEV_RANK.get(s, 0))
        due_on = _compute_due_on(due_days, max_sev)
        task_name = f"[{max_sev}] {campaign.remediation_id[:60]} — {owner_email or 'Unassigned'} ({len(members)} hosts)"
        url = await client.create(task_name, notes, **_provider_create_kwargs(provider, owner_email, due_on))
        if url is None:
            failed_owners.append(owner_email)
            continue
        ref = _extract_ref(url)
        for v, _hostname in members:
            db.add(Ticket(
                tenant_id=tenant_id, vulnerability_id=v.id, provider=provider,
                external_ticket_id=f"{ref}:{v.id}", external_ticket_url=url,
                external_status="open", project_key=project_key, assignee=owner_email,
                created_by_user_id=user.id,
                # Pitfall 1: bare remediation_id (NOT "campaign:{id}") so
                # create_remediation_ticket's own pre-existing dedup check
                # (line 597: Ticket.created_by_rule == remediation_id) can see
                # this ticket exists if a per_remediation automation rule
                # later fires on the same remediation_id.
                created_by_rule=campaign.remediation_id,
                detected_at=v.first_detected_at, ticket_created_at=now,
            ))
            v.status = "IN_PROGRESS"
        await db.flush()
        await recompute_ticket_sla(db, url, tenant_id)  # existing helper, reused verbatim
        created += len(members)

    return {"created_tickets": len(owner_groups) - len(failed_owners), "tickets_linked": created,
            "adopted": adopted_count, "owners": len(owner_groups), "failed_owners": failed_owners}
```

### Pattern 5: Compute-on-read progress + MTTR (D-07/D-12)
See Code Examples for the full query — summarized here: two independent aggregate queries, both scoped by `Vulnerability.remediation_id == campaign.remediation_id`, run on every `GET /campaigns` and `GET /campaigns/{id}` call. No caching layer, no persisted percentage column, matching `get_mttr_by_tier()`'s exact shape (`vulnerabilities/service.py:481-504`).

### Pattern 6: Lazy-on-read completion/reactivation detection (the D-13/D-14 audit-once mechanism)
**What:** `closed_at` is the *only* stored lifecycle marker. On every `GET /campaigns/{id}` (and optionally the list endpoint), after computing the live percentage:
- If `done == total > 0` and `closed_at IS NULL` → this is the FIRST time this campaign has been observed at 100%. Set `closed_at = now()`, `close_trigger = "auto_complete"`, write `audit(db, user=None, "campaign.close", ...)` with a system actor, commit.
- If `NOT (done == total > 0)` and `closed_at IS NOT NULL` and `close_trigger == "auto_complete"` → D-14 reactivation. Clear `closed_at`, write `audit(db, user=None, "campaign.reactivate", ...)`, commit.
**Why this shape, not a scheduler tick:** CONTEXT.md's Deferred Ideas section explicitly rejects "Scheduler-refreshed progress snapshot" for D-07 — a new tick that periodically re-evaluates campaign completion is the same category of mechanism and would recreate the exact thing D-07 chose against. `app/connectors/scheduler.py` (the only in-process scheduler) already carries three unrelated ticks (ticket sync, AI batch prewarm, enrichment refresh); adding a fourth for a phase that explicitly chose compute-on-read is internally inconsistent with its own locked decision.
**Why not an inline hook in `mark_vulnerability_remediated()`/`reopen_vulnerability()`:** Both are proven, tested, single-choke-point helpers from Phase 36/37 (`vulnerabilities/service.py:374-478`). They could be extended with a campaign-lookup-and-flip step — this works and ties the audit event's timestamp to the actual causing action rather than "whenever someone next loads the page" — but it means `vulnerabilities/service.py` (owned by Phase 36/37) grows a Phase 38-specific import/concern, and the same pressure will recur for Phase 39 (exceptions) and Phase 40 (alerts) if each new phase adds its own hook here. **This is a genuine, unresolved design tradeoff — flagged in Assumptions Log A1 and Open Questions 1.** Either approach is workable; this research recommends lazy-on-read as the phase-isolated default, but the planner should make (and document) the final call.
**RBAC note:** the write happens inside a `require_viewer`-gated GET. This is safe because the audit row attributes the transition to a system actor (`user_id=None`, `user_email="system:campaign-complete"`), never to the viewing user — exactly mirroring `reopen_vulnerability`'s `system:rescan-reopen` pattern (`vulnerabilities/service.py:464-476`), which already establishes "a read-adjacent, system-attributed write with its own audit row" as a normal pattern in this codebase (that helper is called from the sync path, not a raw GET, but the actor-attribution technique is identical).

### Anti-Patterns to Avoid
- **A `campaign_members` join table:** Explicitly rejected by D-02/D-03 ("Reversibility: costly"). Membership is always a live `WHERE remediation_id = :x` query.
- **A persisted `progress_pct`/`mttr_seconds` column on `Campaign`:** Contradicts D-07 verbatim ("no persisted progress columns").
- **A new scheduler tick for anything campaign-related:** Contradicts the Deferred Ideas rejection of "Scheduler-refreshed progress snapshot."
- **Re-deriving owner assignment from scratch:** D-05 requires reusing the exact `asset.mdm_details["humaans_email"]` lookup — do not invent a new owner-resolution algorithm even if it seems more "correct."
- **Reusing `_base_open_vulns()` verbatim for campaign progress:** See Common Pitfall 2 — it silently excludes REMEDIATED status, making "% remediated" always compute to 0.
- **A severity-colored progress ribbon:** The UI-SPEC is explicit that campaign progress uses the *status* color family (violet/amber/green), never severity red/orange/yellow — "mixing the families breaks the 'eye separates them' rule."

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Ticket creation across 3 providers | A new Asana/Jira/GitHub client call per provider | `app/ticketing/dispatch.py`'s `TicketingClient` protocol + `build_ticketing_client()` | Already normalizes create/get/comment/close across all 3 providers; campaigns are just a new *caller* of this, not a new provider integration |
| Owner resolution | A new "find the right person" algorithm | `asset.mdm_details.get("humaans_email")` / `asset.assigned_user` inline lookup (`ticketing/service.py:608-616`) | D-05 mandates byte-identical reuse; a "smarter" campaign-level resolver would silently diverge from single-ticket routing, breaking the "no re-derivation" guarantee |
| Duplicate-ticket prevention | A new dedup table/flag | `Ticket.vulnerability_id` + `resolved_at IS NULL` existence check | This is exactly what D-06 asks for ("reuse the existing dedup-by-URL logic") — the existing schema already supports it with zero new columns |
| Race-safe "one active row" enforcement | Application-level locking (`SELECT ... FOR UPDATE`, Redis lock) | Postgres partial unique index + `IntegrityError` catch (`sla_tier_service.py:406-428`) | Proven pattern already in this codebase for the identical problem shape; a new locking mechanism would be strictly more complex and untested here |
| MTTR calculation | A new duration-tracking table | `RemediationEvent` (`vulnerabilities/models.py:253-297`), already written by `mark_vulnerability_remediated()` on every REMEDIATED transition | D-12 requires reading this table, never re-deriving; it already has everything needed (`duration_seconds`, joined via `vulnerability_id`) |
| Confirmation dialogs | A new modal component | `frontend/src/components/ui/ConfirmModal.tsx` (`variant="danger"` for close-campaign) | Already handles mobile bottom-sheet vs. desktop modal, focus management, and the exact `title`/`message`/`confirmLabel` shape the UI-SPEC's copy needs |
| Partial-failure UI (some owner-tickets fail) | A new error-banner component | `frontend/src/components/states/partial-failure-banner.tsx` in **props mode** (`errors={ErrorRow[]}`, `onRetry`) | Its `ErrorRow = {code, requestId, message}` shape is a direct, already-tested fit for "N of M tickets created, K failed" — no query-cache subscription needed since this is a single mutation response, not a set of failed queries |
| Burndown ring visualization | A new SVG gauge component | `frontend/src/components/ui/RiskRing.tsx` (pass `score = pct_remediated`) | Already generic over any 0–100 score with the exact sunset-gradient-stroke chrome the UI-SPEC calls for ("reuses the asset-detail risk-ring's exact dimensions") — only the semantic meaning of the number changes |
| Member-findings table (campaign detail) | A new per-host query | `GET /api/v1/vulnerabilities/remediations/{remediation_id}/hosts` (`router.py:914-933`, `get_hosts_for_remediation()`) | Already `require_viewer`-gated and returns exactly the per-host/per-CVE breakdown a campaign detail page's main table needs; extend only if ticket/owner columns must be joined in |

**Key insight:** Every "hand-roll risk" in this phase is really a **re-carve risk**, not a build-from-scratch risk — the closest wrong move is calling an existing function with the wrong filter or the wrong grouping key (see Pitfalls 1 and 2), not inventing new infrastructure. The review focus for this phase should be "does this query/loop match the existing precedent's shape," not "is this library choice correct."

## Common Pitfalls

### Pitfall 1: Campaign tickets invisible to `create_remediation_ticket`'s own dedup check
**What goes wrong:** If campaign-created `Ticket` rows use a distinguishing `created_by_rule` value (e.g. `f"campaign:{campaign.id}"`), a *later* `per_remediation`-mode automation rule (`ticketing/rule_engine.py:208-262`) running against the same `remediation_id` will not see them — its own dedup check (`ticketing/service.py:591-602`, `Ticket.created_by_rule == remediation_id`) does an exact string match against the bare `remediation_id`. The rule will proceed to call `create_remediation_ticket()` again, creating a **second, overlapping ticket** for findings the campaign already ticketed to a specific owner.
**Why it happens:** `create_remediation_ticket()`'s existing-ticket check is group-level and string-exact, not per-vulnerability (unlike this phase's own D-06 adoption logic, which correctly checks per-`vulnerability_id`). This asymmetry pre-dates this phase — campaigns simply create a second live caller of the same `remediation_id` space that the existing check wasn't written to see.
**How to avoid:** Set campaign-created tickets' `created_by_rule = campaign.remediation_id` (the bare string, matching `create_remediation_ticket`'s own convention) rather than a campaign-prefixed string. This closes the gap in the direction that matters (rule-engine won't double-ticket a campaign's members) at zero cost to campaign functionality, since campaign→ticket traceability can always be recovered via `SELECT * FROM campaigns WHERE remediation_id = ...` (at most one active row at a time per D-11).
**Warning signs:** A finding shows two open tickets from two different providers/projects after both a campaign bulk-create and a scheduled automation rule have touched the same remediation_id.

### Pitfall 2: Reusing `_base_open_vulns()` silently zeroes out "% remediated" forever
**What goes wrong:** `remediation_service.py:14-32`'s `_base_open_vulns()` — the filter underlying `get_remediations_grouped()` — restricts to `status.in_(["OPEN", "IN_PROGRESS"])` (or adds `SUPPRESSED` under the `"all"` mode). It **never includes `REMEDIATED`**. If a developer copies this helper (or its calling convention) for campaign progress aggregation, `done` will always be `0` because REMEDIATED rows are filtered out of the query before the `COUNT() FILTER (status='REMEDIATED')` can ever see them.
**Why it happens:** `_base_open_vulns()` exists to answer "what does an analyst still need to act on" (used by the remediation-grouped *view*, which naturally shrinks as things get fixed) — a fundamentally different question from a campaign's "what fraction of the whole group is now fixed," which requires REMEDIATED rows to be *counted*, not excluded.
**How to avoid:** Campaign membership/progress queries must use their own filter: `Vulnerability.status.in_(["OPEN", "IN_PROGRESS", "REMEDIATED"])` (excluding only `SUPPRESSED`/`FALSE_POSITIVE`, which represent "not being tracked" — see Assumption A6 for why this exclusion itself is a judgment call, not a locked decision). Do not import or call `_base_open_vulns()` for this purpose.
**Warning signs:** A campaign never shows anything but 0% done even after `mark_vulnerability_remediated()` has clearly run (visible via a `RemediationEvent` row existing for a member).

### Pitfall 3: Postgres has no `UNIQUE CONSTRAINT ... WHERE` syntax
**What goes wrong:** Writing `UniqueConstraint("tenant_id", "remediation_id", ...)` in `__table_args__` (the pattern used by every OTHER unique constraint in this codebase, e.g. `Vulnerability.uq_vuln_dedup`) has no way to express "only when closed_at IS NULL" — `UniqueConstraint` has no `postgresql_where` parameter in SQLAlchemy, because Postgres itself has no partial `UNIQUE CONSTRAINT` syntax (only a partial `UNIQUE INDEX`).
**Why it happens:** The two SQLAlchemy constructs look similar but are backed by different Postgres DDL. `UniqueConstraint` compiles to `ALTER TABLE ... ADD CONSTRAINT ... UNIQUE (...)` (no `WHERE` clause possible); a partial unique index compiles to `CREATE UNIQUE INDEX ... ON ... (...) WHERE ...`.
**How to avoid:** Use `sqlalchemy.Index(..., unique=True, postgresql_where=text(...))` inside `__table_args__` (and the matching `op.create_index(..., unique=True, postgresql_where=...)` in Alembic) — exactly as `020_add_sla_tracking.py:27-32` already does for `ix_vuln_sla_due_at` (that one isn't unique, but the `postgresql_where` mechanics are identical; adding `unique=True` is the only difference needed for D-11).
**Warning signs:** A migration using `UniqueConstraint` with a `sqlite_where`/`postgresql_where` kwarg will raise a `TypeError` at import time (SQLAlchemy `UniqueConstraint.__init__` doesn't accept it) — this fails fast, not silently, but still costs a debugging cycle if not anticipated.

### Pitfall 4: `Ticket.vulnerability_id` is singular — never assume one Ticket row covers many findings
**What goes wrong:** A developer might look at "one ticket per owner covering all their affected assets" (D-04) and reach for a `Ticket.vulnerability_ids: ARRAY` column or a many-to-many join table.
**Why it happens:** The plain-English framing of D-04 ("one ticket covering all their affected assets") sounds like a single row should reference multiple vulnerabilities.
**How to avoid:** `ticketing/models.py:84` confirms `Ticket.vulnerability_id` is a **single** FK — CONTEXT.md's own canonical refs flag this explicitly ("no `vulnerability_ids` array on the model"). "One ticket" is a **human-facing concept** (one `external_ticket_url`, one Asana task / Jira issue / GitHub issue) implemented as **N database rows sharing that URL** — the exact pattern `create_remediation_ticket()` and `create_host_ticket()` already use (lines 664-692 and 486-519 respectively). Per-owner bulk-create must follow the identical multi-row-one-URL shape, just partitioned by owner instead of by "everyone."
**Warning signs:** A schema migration adding an array or join-table column to `tickets` is a signal this pitfall has been hit.

### Pitfall 5: Zero-member campaigns must not crash the percentage computation
**What goes wrong:** `pct = done / total * 100` raises `ZeroDivisionError` (Python) when `total == 0` — a campaign whose `remediation_id` currently has zero live OPEN/IN_PROGRESS/REMEDIATED members (an edge case the UI-SPEC explicitly anticipates: "E6 Burndown card | empty | Zero-member campaign → ring shows 0%... renders, never crashes on a 0/0 denominator").
**Why it happens:** D-03's live membership means the denominator is not guaranteed non-zero at read time, unlike most existing aggregate queries in this codebase which are computed over a set already known to be non-empty (e.g., `get_mttr_by_tier()` naturally skips tiers with zero rows via `GROUP BY`).
**How to avoid:** Guard explicitly: `pct = round(done / total * 100) if total else 0`.
**Warning signs:** A 500 error on `GET /campaigns/{id}` for any campaign whose remediation_id currently matches nothing (e.g., every member was suppressed after the campaign was created).

### Pitfall 6: Manual-close vs. auto-complete reactivation is genuinely ambiguous in CONTEXT.md
**What goes wrong:** Building reactivation (D-14) to apply ONLY to auto-completed campaigns (not manually-closed-early ones) — or the reverse — without realizing this is an interpretive choice, not a locked decision, risks building behavior a reviewer/user will later find surprising either way.
**Why it happens:** D-14's literal text ("if a completed campaign's member finding reopens... the campaign flips complete→active automatically") doesn't distinguish *how* the campaign became complete. The UI-SPEC's close-confirmation copy ("This can't be undone from the campaign view") could be read as "manual close is permanent" OR merely "there's no UI button to undo it" (leaving room for automatic system-driven reactivation, exactly as Phase 37's finding-level reopen-on-recurrence already overrides ANY closure path uniformly, regardless of how a finding reached REMEDIATED).
**How to avoid:** This research recommends **uniform treatment** (any closed campaign — manual or automatic — reactivates the same way) for internal consistency with Phase 37's own precedent, but flags this explicitly in Assumptions Log A2 for user/planner confirmation before treating it as locked.
**Warning signs:** A user reports "I closed a campaign early and it came back" (if uniform) or "I closed a campaign early, a finding came back a week later, and the campaign still shows 100% Complete forever" (if not uniform) — either could be perceived as a bug depending on unstated expectations.

### Pitfall 7: Decimal/float MTTR serialization
**What goes wrong:** Per project memory (`getvul-decimal-serialized-as-string`), some numeric backend fields (`cvss_v3_score`, `epss_score`) serialize as JSON **strings**, not numbers, tripping up naive `.toFixed()`/arithmetic on the frontend. `get_mttr_by_tier()` already guards this correctly (`float(r.avg_seconds) if r.avg_seconds is not None else None`, `vulnerabilities/service.py:500`) — a campaign MTTR query must apply the identical `float()` coercion, not assume SQLAlchemy's `func.avg()` over an `Integer` column returns a plain Python float by default (it returns a `Decimal` from asyncpg in some configurations).
**Why it happens:** Postgres `AVG()` over an integer column returns `numeric`, which asyncpg/SQLAlchemy surfaces as `Decimal`, which Pydantic can serialize as a string depending on model config.
**How to avoid:** Copy `get_mttr_by_tier()`'s exact `float(...)` coercion pattern for the campaign MTTR value before it enters a Pydantic response model.
**Warning signs:** Frontend `campaign.mttr_seconds.toFixed(1)` throws `TypeError: toFixed is not a function` in production but not in a dev fixture that happens to hit the `None` branch.

### Pitfall 8: The remediation-grouped entry-point page is new construction, not a wire-up
**What goes wrong:** Under-scoping the phase's frontend work because "the backend endpoint already exists" (`GET /remediations/grouped`, confirmed live since at least Phase 30-something). A direct search of the frontend source tree confirms **zero existing consumers** of this endpoint — no page, no hook, no component references it anywhere.
**Why it happens:** CONTEXT.md's "~80% of the plumbing already exists" framing is accurate for the *backend*, but the *frontend* entry point is 0% built — the UI-SPEC says this explicitly ("this list itself does not yet have a frontend page and must be built this phase") but it's easy to skim past given how much of the rest of the phase is backend re-carving.
**How to avoid:** Plan a full new page (chip-bar-filter + table shell, per `page-layouts.md` §3) as its own task/wave, not a one-line addition alongside the campaign views.
**Warning signs:** A plan that budgets one task for "add Start campaign button" without a preceding task for "build the remediation-grouped list page itself."

## Code Examples

### 1. Campaign model
```python
# Source: pattern verified against backend/app/vulnerabilities/models.py (RemediationEvent,
# SlaEscalationEvent) and backend/app/db/base.py's Base/TimestampMixin/UUIDPrimaryKeyMixin
# convention, applied to this phase's new table.
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Campaign(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Phase 38 (CAMP-01..04) -- a thin, persisted identity+lifecycle wrapper
    around an existing Vulnerability.remediation_id group. Deliberately
    stores NO label snapshot and NO progress/MTTR columns (D-07) -- those are
    always live-joined off `vulnerabilities`/`remediation_events` at read
    time, exactly like `get_remediations_grouped()` already does for the
    identical grouping key (see 38-RESEARCH.md Pattern 2).

    `closed_at` is the ONLY lifecycle marker, serving two purposes:
      1. The D-11 partial-unique-index predicate (one row per
         tenant+remediation_id WHERE closed_at IS NULL).
      2. The D-13/D-14 audit-once gate for the derived complete/active
         display status (see 38-RESEARCH.md Pattern 6) -- NOT itself the
         display status; a campaign's Active/Complete pill is always
         recomputed from live member percentages at read time.
    """

    __tablename__ = "campaigns"
    __table_args__ = (
        Index(
            "uq_campaign_active_remediation",
            "tenant_id",
            "remediation_id",
            unique=True,
            postgresql_where=text("closed_at IS NULL"),
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    remediation_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    # Optional but recommended: distinguishes "auto_complete" vs "manual" for
    # Pattern 6's reactivation-eligibility check + audit detail readability.
    close_trigger: Mapped[str | None] = mapped_column(String(20))
```

### 2. Alembic migration
```python
# Source: structural pattern verified against backend/alembic/versions/047_add_remediation_events.py
# (table-creation shape) and 020_add_sla_tracking.py:27-32 (postgresql_where precedent).
"""Add campaigns table (Phase 38 -- CAMP-01..04, D-11 partial unique index).

Revision id kept <= 32 chars: alembic_version.version_num is varchar(32).
"049_add_campaigns" is 17 chars -- safe.
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "049_add_campaigns"
down_revision = "048_add_clean_scan_streak"  # confirmed current head


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("remediation_id", sa.String(200), nullable=False),
        sa.Column(
            "created_by_user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "closed_by_user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("close_trigger", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_campaigns_tenant_id", "campaigns", ["tenant_id"])
    op.create_index("ix_campaigns_remediation_id", "campaigns", ["remediation_id"])
    # D-11: Postgres has no "UNIQUE CONSTRAINT ... WHERE" -- a partial UNIQUE
    # INDEX is the only way to express this (Pitfall 3).
    op.create_index(
        "uq_campaign_active_remediation",
        "campaigns",
        ["tenant_id", "remediation_id"],
        unique=True,
        postgresql_where=sa.text("closed_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_campaign_active_remediation", table_name="campaigns")
    op.drop_index("ix_campaigns_remediation_id", table_name="campaigns")
    op.drop_index("ix_campaigns_tenant_id", table_name="campaigns")
    op.drop_table("campaigns")
```

### 3. Compute-on-read progress + MTTR (D-07/D-09/D-12)
```python
# Source: shape mirrors backend/app/vulnerabilities/service.py:481-504's
# get_mttr_by_tier() exactly (Decimal->float coercion, func.avg/func.count),
# adapted to scope by remediation_id instead of tier, and CORRECTED for
# Pitfall 2 (do not reuse _base_open_vulns()).
from sqlalchemy import func, select

async def get_campaign_progress(db, tenant_id, remediation_id: str) -> dict:
    row = (await db.execute(
        select(
            func.count().label("total"),
            func.count().filter(Vulnerability.status == "REMEDIATED").label("done"),
            func.count().filter(Vulnerability.status == "IN_PROGRESS").label("in_progress"),
        ).where(
            Vulnerability.tenant_id == tenant_id,
            Vulnerability.remediation_id == remediation_id,
            # Pitfall 2: OPEN + IN_PROGRESS + REMEDIATED -- NOT _base_open_vulns().
            # SUPPRESSED/FALSE_POSITIVE excluded (Assumption A6).
            Vulnerability.status.in_(["OPEN", "IN_PROGRESS", "REMEDIATED"]),
        )
    )).one()
    total, done, in_progress = row.total, row.done, row.in_progress
    return {
        "total": total,
        "open": total - done - in_progress,
        "in_progress": in_progress,
        "done": done,
        # Pitfall 5: explicit zero-guard.
        "pct_remediated": round(done / total * 100) if total else 0,
    }


async def get_campaign_mttr(db, tenant_id, remediation_id: str) -> float | None:
    # RemediationEvent has NO remediation_id column (models.py:253-297) --
    # join through Vulnerability's CURRENT remediation_id, consistent with
    # D-03's live-membership philosophy applied to MTTR too.
    row = (await db.execute(
        select(func.avg(RemediationEvent.duration_seconds).label("avg_seconds"))
        .select_from(RemediationEvent)
        .join(Vulnerability, RemediationEvent.vulnerability_id == Vulnerability.id)
        .where(
            RemediationEvent.tenant_id == tenant_id,
            Vulnerability.remediation_id == remediation_id,
        )
    )).one()
    # Pitfall 7: Decimal->float coercion, exactly matching get_mttr_by_tier().
    return float(row.avg_seconds) if row.avg_seconds is not None else None
```

### 4. Router skeleton (RBAC + audit wiring, D-15/D-16)
```python
# Source: RBAC/audit pattern mirrors backend/app/vulnerabilities/router.py:811-862's
# suppress_remediation() endpoint exactly -- the closest existing precedent for
# "a bulk write over an entire remediation_id group, require_analyst-gated, audited."
from typing import Annotated
from fastapi import APIRouter, Depends
from app.auth.rbac import require_analyst, require_viewer
from app.auth.schemas import CurrentUser
from app.audit import audit
from app.db.session import DBSession

router = APIRouter()


@router.post("")
async def create_campaign(
    body: CampaignCreateRequest,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
):
    campaign, is_new = await get_or_create_campaign(db, user.tenant_id, body.remediation_id, user)
    if is_new:
        await audit(db, user, "campaign.create", "campaign", str(campaign.id),
                    {"remediation_id": body.remediation_id})
    await db.commit()
    return {"id": str(campaign.id), "remediation_id": campaign.remediation_id, "already_existed": not is_new}


@router.post("/{campaign_id}/bulk-assign")
async def bulk_assign(
    campaign_id: uuid.UUID,
    body: CampaignBulkAssignRequest,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
):
    campaign = await _get_campaign_or_404(db, user.tenant_id, campaign_id)
    client = await _resolve_ticketing_client(db, user.tenant_id, body.provider)  # existing dispatch.py pattern
    result = await bulk_create_campaign_tickets(db, user.tenant_id, user, campaign, body.provider,
                                                 body.project_key, client, body.due_days)
    # D-10: audited EVERY run, not just the first.
    await audit(db, user, "campaign.bulk_assign", "campaign", str(campaign.id), result)
    await db.commit()
    return result


@router.post("/{campaign_id}/close")
async def close_campaign(
    campaign_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
):
    campaign = await _get_campaign_or_404(db, user.tenant_id, campaign_id)
    campaign.closed_at = datetime.now(UTC)
    campaign.closed_by_user_id = user.id
    campaign.close_trigger = "manual"
    await audit(db, user, "campaign.close", "campaign", str(campaign.id), {"trigger": "manual"})
    await db.commit()
    return {"id": str(campaign.id), "closed": True}
```

### 5. Frontend query hook
```typescript
// Source: mirrors frontend/src/lib/queries/use-vuln-escalations.ts exactly
// (signal-aware queryFn, enabled-gate, staleTime convention).
'use client';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';

export type CampaignDetail = {
  id: string;
  remediation_id: string;
  status: 'ACTIVE' | 'COMPLETE'; // computed server-side, never stored client-side
  total: number;
  open: number;
  in_progress: number;
  done: number;
  pct_remediated: number;
  mttr_seconds: number | null;
};

export function useCampaignDetail(id: string | null) {
  return useQuery({
    queryKey: queryKeys.campaigns.detail(id ?? ''),
    queryFn: ({ signal }) =>
      api<CampaignDetail>(`/api/v1/campaigns/${encodeURIComponent(id!)}`, { signal }),
    enabled: id !== null && id !== '',
    staleTime: 0, // D-07 compute-on-read -- never treat a stale cache as authoritative
    retry: 1,
  });
}
```
Add to `frontend/src/lib/queries/keys.ts`:
```typescript
campaigns: {
  all: ['campaigns'] as const,
  list: (opts: { filters: object; page: number }) => ['campaigns', 'list', opts] as const,
  detail: (id: string) => ['campaigns', 'detail', id] as const,
},
```

## State of the Art

Not applicable in the usual sense — this phase adopts no new external technology and has no "old approach vs. new approach in the wider ecosystem" axis. The relevant "state of the art" is entirely internal:

| Old approach (pre-Phase-38) | Current approach (this phase) | When changed | Impact |
|--------------------------|------------------|--------------|--------|
| `create_remediation_ticket()` creates exactly one ticket for an entire remediation group, owner info only in description text | Per-owner carve-up creates N tickets, one per owner, each with real assignee routing | This phase (CAMP-02) | The existing primitive stays unchanged/still used by `rule_engine.py`'s `per_remediation` mode; campaigns add a sibling code path, not a replacement |
| No persisted concept of "a remediation group as a trackable unit" | `campaigns` table gives remediation groups a stable identity + audit trail across time | This phase (CAMP-01) | Enables "% remediated" and MTTR to be reported per initiative, not just per finding/tier |

**Deprecated/outdated:** Nothing in the existing codebase is deprecated by this phase — everything referenced above (`get_remediations_grouped`, `create_remediation_ticket`, `mark_vulnerability_remediated`, `audit()`) remains the live, unmodified source of truth this phase reads from.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Lazy-on-read detection (not a scheduler tick, not an inline hook in `mark_vulnerability_remediated`) is the right mechanism for the D-13 auto-complete audit-once gate | Architecture Pattern 6 | Low-medium — all three mechanisms are workable; choosing wrong only costs a refactor, not a correctness bug, since the *display* status is always computed independently of whichever mechanism fires the one-time audit row |
| A2 | Campaign reactivation (D-14) applies uniformly to manually-closed-early campaigns and naturally-auto-completed campaigns alike | Common Pitfall 6 | Medium — if the intended behavior is "manual close is permanent, only auto-complete reactivates," building the uniform version means a manually-closed campaign could silently reappear as Active after a recurrence, contradicting the UI-SPEC's "can't be undone" copy in spirit even if not in literal UI affordance |
| A3 | `Campaign` stores no denormalized `remediation_action`/`affected_product` label snapshot — always live-joined | Architecture Pattern 2, Code Example 1 | Low — reversible additively (a snapshot column could be added later without a breaking migration); the only cost of being wrong is a minor extra join at read time, not a correctness issue |
| A4 | Campaign-created tickets set `Ticket.created_by_rule` to the bare `remediation_id` (not a `"campaign:{id}"`-prefixed string) | Common Pitfall 1, Code Example (Pattern 4) | Medium — if wrong, the specific rule-engine double-ticket interaction in Pitfall 1 remains open; low blast radius (only affects tenants running BOTH campaigns and `per_remediation`-mode automation rules on the same remediation_id) but silent (no error, just a duplicate ticket) |
| A5 | The new remediation-grouped entry-point page lives at a URL under `/dashboard/vulnerabilities/remediations` (nested, matching the backend's own `/vulnerabilities/remediations/grouped` nesting) | Common Pitfall 8, Recommended Project Structure | Low — purely a routing/URL choice with no functional consequence; easy to rename later |
| A6 | Campaign membership/progress excludes `SUPPRESSED` and `FALSE_POSITIVE` findings from the denominator (matching the entry-point view's own default semantics), even though D-02's literal text ("every finding sharing that remediation_id") doesn't state this exclusion | Common Pitfall 2, Code Example 3 | Medium — if wrong (i.e., if suppressed/false-positive findings should count toward the denominator), campaign "% remediated" would read differently than the launch screen implied to the analyst; needs explicit product confirmation since it affects a customer-visible metric |
| A7 | Every campaign write's audit `action` string follows the `campaign.<verb>` convention (`campaign.create`, `campaign.bulk_assign`, `campaign.close`, `campaign.reactivate`) | Code Examples 4, Pattern 6 | Low — purely a naming convention; D-15 requires *that* every action is audited, not a specific string, and `app/audit.py`'s own action-name comment block (lines 53-76) shows this dotted-verb convention is already the codebase norm |

**Note:** A1, A2, and A6 are the three assumptions with real product-behavior consequences (not just implementation-detail choices) and should be explicitly confirmed with the user/planner before being treated as locked, per this agent's provenance discipline.

## Open Questions (RESOLVED)

1. **Should the D-13 auto-complete audit fire at the moment of the causing remediation event, or lazily whenever the campaign is next viewed?** _RESOLVED: see D-19 — auto-complete transition audited lazily-on-read (lazy-on-read / Pattern 6 confirmed)._
   - What we know: D-13 requires it to be audited; D-07 requires compute-on-read; the Deferred Ideas section rules out a new scheduler tick.
   - What's unclear: whether growing `mark_vulnerability_remediated()`/`reopen_vulnerability()` with a campaign-lookup step (tying the audit timestamp to the real event) is preferable to the phase-isolated lazy-on-read approach this research recommends (tying the audit timestamp to "whenever someone looked").
   - Recommendation: default to lazy-on-read (Pattern 6) unless the planner determines audit-timestamp precision for this specific transition is a compliance requirement, in which case the inline-hook alternative should be used instead.

2. **Does a manually-closed-early campaign reactivate on member recurrence the same way an auto-completed one does?** _RESOLVED: see D-17 — manual early-close is sticky (D-14 auto-reactivation does NOT apply to manually-closed campaigns)._
   - What we know: D-14's text doesn't distinguish the two paths; the UI-SPEC's confirmation copy says "can't be undone from the campaign view" (a UI-affordance statement, not necessarily a backend guarantee).
   - What's unclear: the intended product behavior for the specific case of "analyst closes a 60%-done campaign early, then a remediated member later recurs."
   - Recommendation: confirm with the user before implementation; default to uniform behavior (Assumption A2) if no answer is available, since it requires strictly less special-case code and mirrors Phase 37's own "closure path doesn't matter, recurrence always reopens" precedent.

3. **Exact route/URL for the new remediation-grouped entry-point page.** _RESOLVED: Plan 05 — /dashboard/vulnerabilities/remediations (own nav-adjacent route)._
   - What we know: it must exist as a dedicated page (UI-SPEC), reusing the chip-bar + table shell pattern; the backend endpoint is `GET /api/v1/vulnerabilities/remediations/grouped`.
   - What's unclear: whether it should be its own nav-adjacent route (`/dashboard/vulnerabilities/remediations`) or a view-toggle within the existing `/dashboard/vulnerabilities` page — the UI-SPEC does not add a "Remediations" item to `WORKFLOW_ITEMS`/`TRIAGE_ITEMS`, only a "Campaigns" item, implying the remediation-grouped view may be intended as a secondary/discoverable-from-elsewhere surface rather than a primary nav destination.
   - Recommendation: planner picks the exact route as a low-risk implementation detail (Assumption A5); either choice satisfies CAMP-01's "dedicated campaign view" requirement (which is about the *campaign* view, not the remediation-grouped entry point).

4. **Should `SUPPRESSED`/`FALSE_POSITIVE` findings count toward a campaign's denominator?** _RESOLVED: see D-18 — SUPPRESSED / FALSE_POSITIVE excluded from the campaign denominator._
   - What we know: D-02's literal text says "every finding sharing that remediation_id," unqualified; the existing remediation-grouped view (the thing a campaign wraps) excludes them by default.
   - What's unclear: whether a campaign's "% remediated" should be computed against the same base a user saw when they clicked "Start campaign," or against a stricter reading of D-02.
   - Recommendation: exclude them (Assumption A6), matching the launch-time view's own semantics; confirm with the user if this becomes contentious during review.

5. **Is hardening `rule_engine.py`'s per-vulnerability dedup gap in scope for this phase, or purely Assumption A4's shared-string workaround?** _RESOLVED: see D-20 — campaigns reuse the BARE `remediation_id` string as `created_by_rule` (A4 shared-string workaround is sufficient; no rule_engine.py change this phase)._
   - What we know: CONTEXT.md's "Explicitly NOT this phase" list does not mention the rule engine at all; this is a pre-existing gap this phase's own bulk-create surfaces more sharply (two independent "bulk ticket over a remediation_id" callers now exist).
   - What's unclear: whether the shared-`created_by_rule`-string workaround (Pitfall 1/A4) is considered sufficient, or whether the planner wants a small defensive change to `create_remediation_ticket()`'s own dedup check (making it per-vulnerability like the campaign's own D-06 logic) as a belt-and-suspenders fix.
   - Recommendation: treat A4's workaround as sufficient for this phase's scope (no changes to `rule_engine.py`/`ticketing/service.py` beyond what campaigns write into `created_by_rule`); flag the residual gap for a future ticketing-backlog item if the workaround is later judged insufficient.

## Environment Availability

This phase adds no new external dependency. It reuses Postgres (already required, already running per every prior phase) and the tenant's already-configured ticketing connectors (Asana/Jira/GitHub — conditional on tenant configuration, exactly like every existing bulk-ticketing feature; not a new environment requirement introduced by this phase).

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PostgreSQL | `campaigns` table, all aggregation queries | Already required by every phase | (existing) | — |
| A configured ticketing connector (Asana/Jira/GitHub) | Bulk-create tickets (CAMP-02) | Tenant-conditional (existing behavior) | — | If no connector is configured for the requested provider, `bulk-assign` should fail the same way `create_host_ticket`/`create_remediation_ticket` already do today (existing error-handling path, not a new one) |

No missing dependencies block this phase.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Backend framework | pytest 8.3+ / pytest-asyncio 0.24+ `[VERIFIED: backend/pyproject.toml]` |
| Backend config | `backend/pyproject.toml` `[tool.pytest.ini_options]` (line 74) |
| Frontend unit framework | Vitest 4.1.6 `[VERIFIED: frontend/package.json]` |
| Frontend e2e framework | Playwright 1.61.1 `[VERIFIED: frontend/package.json]` |
| Quick run command (backend) | `ENCRYPTION_KEY=<fernet-key> JWT_SECRET_KEY=test-secret pytest backend/tests/test_campaigns.py -x` |
| Quick run command (frontend) | `npm run test -- campaigns` (vitest, from `frontend/`) |
| Full suite command (backend) | Run **per-file**, not the whole `tests/` directory — per project memory (`getvul-backend-pytest-env`), running the whole directory produces false failures; CI likely runs per-file too (verify against `.github/workflows/ci.yml` at plan time) |
| Full suite command (frontend) | `npm run test` (vitest) + `npm run test:e2e` (Playwright, requires prod build per `getvul-local-e2e-perf-gate` memory) |

**Backend pytest env note (project memory, confirmed in `tests/test_finding_reopen.py:8-10`):** tests require a real Fernet `ENCRYPTION_KEY` + `JWT_SECRET_KEY` set, and must be run per-file, not as the whole `tests/` directory.

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CAMP-01 | `POST /campaigns` creates a new campaign for a fresh `remediation_id` | unit | `pytest backend/tests/test_campaigns.py::test_create_campaign_new -x` | ❌ Wave 0 |
| CAMP-01 | `POST /campaigns` on an existing active campaign returns it unchanged, no duplicate, no audit row | unit | `pytest backend/tests/test_campaigns.py::test_create_campaign_reopens_existing -x` | ❌ Wave 0 |
| CAMP-01 | D-11 partial unique index rejects a concurrent duplicate active row at the DB level (race-safety) | unit (direct `IntegrityError` simulation, mirroring `sla_tier_service.py`'s own test pattern) | `pytest backend/tests/test_campaigns.py::test_campaign_unique_active_index -x` | ❌ Wave 0 |
| CAMP-01 | A closed campaign's `remediation_id` CAN get a new active campaign (partial index only blocks `closed_at IS NULL` rows) | unit | `pytest backend/tests/test_campaigns.py::test_new_campaign_after_close -x` | ❌ Wave 0 |
| CAMP-02 | Bulk-assign creates exactly one ticket per distinct owner (D-04) | unit | `pytest backend/tests/test_campaigns.py::test_bulk_assign_one_ticket_per_owner -x` | ❌ Wave 0 |
| CAMP-02 | Owner-less findings get an unassigned ticket in the default project, never dropped (D-08) | unit | `pytest backend/tests/test_campaigns.py::test_bulk_assign_unassigned_bucket -x` | ❌ Wave 0 |
| CAMP-02 | A finding already linked to a live ticket is adopted, not duplicated (D-06) | unit | `pytest backend/tests/test_campaigns.py::test_bulk_assign_adopts_existing_ticket -x` | ❌ Wave 0 |
| CAMP-02 | Re-running bulk-assign only tickets newcomers, adopts the rest (idempotency, D-10) | integration | `pytest backend/tests/test_campaigns.py::test_bulk_assign_idempotent_rerun -x` | ❌ Wave 0 |
| CAMP-02 | Owner assignment matches `ticketing/service.py`'s own derivation byte-for-byte (D-05) | unit | `pytest backend/tests/test_campaigns.py::test_owner_derivation_matches_ticketing_service -x` | ❌ Wave 0 |
| CAMP-03 | Progress % / open / in_progress / done counts match hand-computed expectations across a mixed-status fixture (Pitfall 2 regression guard) | unit | `pytest backend/tests/test_campaigns.py::test_progress_counts_include_remediated -x` | ❌ Wave 0 |
| CAMP-03 | Zero-member campaign returns 0% without raising (Pitfall 5 regression guard) | unit | `pytest backend/tests/test_campaigns.py::test_progress_zero_member_no_crash -x` | ❌ Wave 0 |
| CAMP-03 | Campaign MTTR equals the average of member `RemediationEvent.duration_seconds` rows | unit | `pytest backend/tests/test_campaigns.py::test_campaign_mttr_average -x` | ❌ Wave 0 |
| CAMP-03 | A finding discovered on a newly-seen asset after launch is counted in the live denominator (D-03) | integration | `pytest backend/tests/test_campaigns.py::test_live_membership_grows -x` | ❌ Wave 0 |
| CAMP-03 | Phase 37 reopen-on-recurrence on a 100%-complete campaign's member flips the campaign back to Active and drops its % (D-14) | integration | `pytest backend/tests/test_campaigns.py::test_reopen_reactivates_campaign -x` | ❌ Wave 0 |
| CAMP-04 | `campaign.create`, `campaign.bulk_assign`, `campaign.close` each write an audit row with the correct tenant/actor | integration | `pytest backend/tests/test_campaigns.py::test_campaign_actions_audited -x` | ❌ Wave 0 |
| CAMP-04 | A viewer-role user gets 403 on create/bulk-assign/close; a viewer CAN read | integration | `pytest backend/tests/test_campaigns.py::test_campaign_rbac -x` | ❌ Wave 0 |
| CAMP-04 | Auto-complete-on-100% writes exactly one audit row (not once per subsequent page load) | integration | `pytest backend/tests/test_campaigns.py::test_auto_complete_audited_once -x` | ❌ Wave 0 |

Frontend (manual-only unless a seeded e2e fixture is built, per the kanban e2e precedent — see below): visual/state coverage is already resolved by the UI-SPEC's 21 `covered` + 10 `backstop` rows; `backstop` rows require live verification at execution time, not new test authorship.

### Sampling Rate
- **Per task commit:** `ENCRYPTION_KEY=<key> JWT_SECRET_KEY=test-secret pytest backend/tests/test_campaigns.py -x` (backend); `npm run test -- campaigns` (frontend)
- **Per wave merge:** full backend suite run per-file per project memory + `npm run test` + `npm run build` (bundle budget check)
- **Phase gate:** full suite green before `/gsd-verify-work`, plus a live e2e pass of create→bulk-assign→close if a seeded fixture is built (see below)

### Wave 0 Gaps
- [ ] `backend/tests/test_campaigns.py` — covers CAMP-01..04 (new file, all rows above)
- [ ] `backend/app/campaigns/` module itself — new, all 4 files (`models.py`/`schemas.py`/`service.py`/`router.py`)
- [ ] `backend/alembic/versions/049_add_campaigns.py` — new migration
- [ ] Frontend component test files (`campaign-burndown-card.test.tsx`, `campaigns-table.test.tsx`, etc.) — new, mirroring `RiskRing.test.tsx`/`severity-ribbon` conventions
- [ ] `frontend/src/lib/queries/use-campaigns.ts` (+ its test file) — new
- [ ] E2E seed data: per the `getvul-kanban-e2e-seed-gated-destructive` project memory, the existing dev-seed dataset may not contain a remediation group with enough OPEN findings across enough distinct owners to exercise the full create→bulk-assign→100%-complete lifecycle deterministically. **Flag for the planner:** an isolated seeded-DB e2e path (not the shared dev stack) will likely be needed for a genuine end-to-end campaign lifecycle test, exactly as that memory recommends for kanban's drag/keyboard paths. A pure UI-level "click Start campaign, see it in the list" smoke test can use the shared dev stack safely; the full 100%-remediated auto-complete assertion cannot without either a seeded DB or directly driving `mark_vulnerability_remediated()` at the API/service level instead of through a real scan cycle.

*(No pre-existing test infrastructure gap beyond "the module doesn't exist yet" — `conftest.py`'s fixture surface (`db_session`, `tenant_a`, `analyst_user`, `viewer_user`, `client`) already covers everything a `test_campaigns.py` file needs with zero new fixtures.)*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Reuses existing JWT session auth (`get_current_user`) unchanged |
| V3 Session Management | No | No new session concept |
| V4 Access Control | Yes | `require_analyst` on all 3 write endpoints, `require_viewer` on reads (D-16); every query additionally scoped by `Vulnerability.tenant_id`/`Campaign.tenant_id` — the same double-layer (RBAC + tenant scoping) every existing endpoint in this codebase uses |
| V5 Input Validation | Yes | New Pydantic schemas (`CampaignCreateRequest`, `CampaignBulkAssignRequest`) should use `extra="forbid"` mass-assignment defense, matching `ticketing/schemas.py:69`'s existing convention (`TicketCreateRequest`'s docstring cites this explicitly as "T-25-06, ASVS V5") |
| V6 Cryptography | No | No new crypto; ticketing credential decryption is entirely delegated to the existing `dispatch.py`/`get_decrypted_credentials()` path — campaigns never touch Fernet directly, exactly like every other ticketing caller |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Cross-tenant campaign access via guessed/enumerated `campaign_id` (IDOR) | Information Disclosure / Elevation of Privilege | Every campaign query must include `Campaign.tenant_id == user.tenant_id` in the `WHERE` clause, not just filter after fetch — mirrors the existing `_resolve_group`/`T-12-21`/`T-35-01` tenant-scoping comments already present in `ticketing/service.py` |
| Mass assignment via an unexpected body field on create/bulk-assign requests | Tampering | Pydantic `extra="forbid"` on all new request schemas (see V5 above) |
| Audit-row loss on a campaign write (mutation succeeds, audit silently fails) | Repudiation | Use `app/audit.py::audit()` exactly as-is — it is already fail-closed by design (an exception there propagates and rolls back the whole transaction, per its own docstring, lines 154-166) — do not wrap the `audit()` call in a try/except that could swallow this guarantee |
| A `require_viewer` GET triggering a write (the Pattern 6 lazy-completion-detection side effect) being exploited to forge audit rows | Tampering / Repudiation | The write must be system-attributed (`user_id=None`, `user_email="system:campaign-complete"`), never derived from the requesting viewer's identity, and must only ever be able to set `closed_at`/`close_trigger` based on a value it itself just computed from the DB (never from client input) |

## Sources

### Primary (HIGH confidence — direct codebase reads, this session)
- `backend/app/vulnerabilities/models.py` — `Vulnerability`, `RemediationEvent`, `SlaEscalationEvent`, `RiskExposureBackfillJob` (status/enum/constraint conventions)
- `backend/app/vulnerabilities/remediation_service.py` — `get_remediations_grouped()`, `get_hosts_for_remediation()`, `get_remediations_for_host()`, `_base_open_vulns()` (Pitfall 2 source)
- `backend/app/vulnerabilities/service.py:350-530` — `mark_vulnerability_remediated()`, `reopen_vulnerability()`, `get_mttr_by_tier()`
- `backend/app/vulnerabilities/router.py:780-940` — `remediations_grouped`, `suppress_remediation`, `hosts_for_remediation` endpoints
- `backend/app/ticketing/service.py` (full file, 1478 lines) — `create_tickets`, `create_host_ticket`, `create_remediation_ticket`, owner derivation sites, dedup logic, `list_tickets`
- `backend/app/ticketing/models.py`, `backend/app/ticketing/dispatch.py`, `backend/app/ticketing/rule_engine.py`, `backend/app/ticketing/providers.py`, `backend/app/ticketing/schemas.py`
- `backend/app/audit.py` (full file) — `audit()`, `AuditLog` model, action-naming convention
- `backend/app/auth/rbac.py` (full file) — `require_analyst`/`require_viewer`
- `backend/app/main.py` — router registration pattern, scheduler startup
- `backend/app/connectors/scheduler.py` — confirms the only in-process scheduler and its existing tick set
- `backend/app/vulnerabilities/sla_tier_service.py:395-440` — `IntegrityError`/`begin_nested()` race-safe pattern (Pattern 3 source)
- `backend/alembic/versions/020_add_sla_tracking.py`, `047_add_remediation_events.py`, `048_add_clean_scan_streak.py` — migration shape + partial-index precedent (Pitfall 3 source) + confirmed current head
- `backend/app/notifications/`, `backend/app/cspm/`, `backend/app/tenants/` directory listings — small top-level module convention (Pattern 1 source)
- `backend/tests/conftest.py`, `backend/tests/test_finding_reopen.py` — test fixture surface + env-var requirement confirmation
- `backend/pyproject.toml` — dependency versions
- `frontend/src/lib/api.ts`, `frontend/src/lib/queries/keys.ts`, `use-vuln-escalations.ts` — frontend data-fetching conventions
- `frontend/src/components/ui/RiskRing.tsx`, `frontend/src/components/assets/severity-ribbon.tsx`, `frontend/src/components/ui/ConfirmModal.tsx`, `frontend/src/components/states/partial-failure-banner.tsx` — reusable component inventory
- `frontend/src/components/shell/nav-items.ts` — nav registration pattern, `ChipKey` scope
- `.claude/skills/sketch-findings-getvul/references/page-layouts.md` — layout pattern confirmation (list-with-drill-down, two-column-sticky-rail)
- `frontend/package.json` — frontend dependency versions
- Direct search of `frontend/src/app/(authed)/dashboard/vulnerabilities/` and repo-wide grep for `remediations/grouped` consumers — confirms zero existing frontend page (Pitfall 8 source)

### Secondary (MEDIUM confidence)
- None — every claim in this research was verified against a direct codebase read in this session. No WebSearch or Context7 lookup was needed or performed, since this phase adopts no new external library or framework; the highest-trust source available (this repository's own working code) already answers every question CONTEXT.md's research focus list raised.

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — zero new dependencies, all versions read directly from lockfiles/manifests
- Architecture: HIGH — every recommended pattern has a direct, working precedent in this exact codebase (not an inferred "best practice"), with the sole exception of the D-13 audit-once mechanism (Pattern 6 / Assumption A1), which is MEDIUM since it's a reasoned synthesis, not a copy of an existing identical mechanism
- Pitfalls: HIGH for Pitfalls 1-5, 7-8 (each verified against a specific line-numbered code read); MEDIUM for Pitfall 6 (an interpretive gap in CONTEXT.md, not a code-level finding)

**Research date:** 2026-08-17
**Valid until:** 30 days (stable internal codebase; the only external-facing risk is if a future Phase 36/37/39/40 change touches `mark_vulnerability_remediated`, `create_remediation_ticket`, or the scheduler in a way that invalidates a cited line number — re-verify line numbers if this research is consumed more than a few weeks after this date)
