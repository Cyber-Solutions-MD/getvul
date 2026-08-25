# Phase 39: Exception & Risk-Acceptance Workflow - Research

**Researched:** 2026-08-18
**Domain:** Internal backend feature extension (FastAPI + SQLAlchemy async + Alembic) — governed exception records + compute-on-read exclusion join across ~10 existing read paths. Zero new third-party dependencies.
**Confidence:** HIGH (schema/migration/RBAC/audit patterns — directly verified against this codebase) / MEDIUM (exact scope-column semantics, SLA-subtraction implementation — reasoned recommendations, flagged where CONTEXT left them to discretion)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Exclusion model & source of truth (EXC-01 / EXC-02)**
- **D-01** — New `exceptions` table is the source of truth; exclusion is a compute-on-read join. Granting an exception does **not** permanently flip finding status. Exclusion is derived at read time by joining findings against *active (non-expired)* exceptions. Reversibility: costly.
- **D-02** — Additive to the legacy suppress paths. `/cve/{id}/ignore`, `/remediations/{id}/suppress`, asset `is_ignored` stay as-is. Exclusion becomes the union: a finding is excluded if `status IN (SUPPRESSED, FALSE_POSITIVE)` **OR** an active exception matches it. No migration of shipped endpoints/tests this phase.
- **D-03** — Grant only on actionable (OPEN / IN_PROGRESS) findings. Granting against a `REMEDIATED` item is rejected / no-op.
- **D-04** — EXC-04 auto-resurface is free via compute-on-read. An exception is "active" only while `now < expiry`. Once expired, the join stops matching and the finding reappears everywhere automatically — no scheduler tick, no re-flip, no manual re-trigger.

**Record shape & types (EXC-01)**
- **D-05** — One `exceptions` table with a `type` enum `{FALSE_POSITIVE, ACCEPTED_RISK}`. Same form, scope, approver, expiry, audit, and exclusion machinery for both. Reversibility: costly.
- **D-06** — Justification, approver, scope, and expiry are all mandatory — for both types. No optional-approver, no optional-expiry.

**Approval & RBAC (EXC-01 / EXC-03)**
- **D-07** — Recorded-attribution, single-action grant (no pending→approved state machine). The granting analyst fills a required **approver** field and the exception is created + audited in one action.
- **D-08** — Approver is a required tenant-user reference (FK), not free text. (Assumes the approver is a GetVul user; out-of-band external approvers are out of scope this phase.)
- **D-09** — `require_analyst` for grant / list-write / revoke. Reads follow the existing viewer/analyst pattern.

**Scope semantics (EXC-01)**
- **D-10** — Scope pins a CVE × target: finding / asset / asset-group. Not a blanket whole-target exception (would hide unrelated new criticals on an "excepted" asset). Matches how `/cve/ignore` already scopes by CVE.
- **D-11** — Live membership. An exception is a scope *predicate*; it covers all matching findings — present AND future — until expiry. Reversibility: costly.
- **D-12** — Overlap = OR semantics; latest expiry governs resurface. A finding matched by multiple active exceptions is excluded if ANY is active, and resurfaces only when the **last-expiring** covering exception lapses. No most-specific-wins precedence.

**Expiry (EXC-02)**
- **D-13** — Mandatory expiry on BOTH types. Defaults may differ per type (exact windows → planning).
- **D-14** — Absolute expiry date, validated future + hard max cap (e.g. ≤ 1 year — exact cap → planning).

**Exclusion surface (EXC-02)**
- **D-15** — Exclusion is comprehensive: active queues + SLA timers + risk-scored dashboards. `list_vulnerabilities`, `resolve_state_for_vuln`, AND `compute_risk_scores`/asset `risk_exposure_score`. Reversibility: costly.
- **D-16** — The excepted duration does NOT count against the SLA clock. On resurface, the SLA due date is shifted by how long the finding was under an active exception. Reversibility: costly.

**Revocation & audit (EXC-01 / EXC-03)**
- **D-17** — Early revocation allowed, audited, immediate resurface.
- **D-18** — Every mutation routes through `audit()` (tenant-scoped, fail-closed). Grant payload: type/scope/approver/justification/expiry. Revoke: who/when.

**Visibility**
- **D-19** — Passive "expiring soon" indicator only. Sortable/filterable by expiry. Active push deferred to Phase 40.

### Claude's Discretion
- `exceptions` table schema, column names, the `type`/scope enums, indexes, and the Alembic migration structure.
- The exact scope-match SQL for finding/asset/asset-group and how the active-exception join is factored — a single shared helper/subquery vs. per-consumer joins (shared seam preferred).
- The exact SLA-subtraction implementation for D-16 within `sla_tier_service`.
- Whether the expiry-driven resurface writes a lazy-on-read audit row (optional — no actor).
- The exact expiry max-cap value (D-14) and any per-type default windows (D-13).
- The exception form + list UI — deferred to `/gsd-ui-phase` / UI-SPEC (already produced, see below).
- The precise enumeration of every read path that must learn the exclusion join (D-15) — sweep results below.

### Deferred Ideas (OUT OF SCOPE)
- **Legacy suppress consolidation** — rewiring `/cve/ignore`, `/remediations/suppress`, asset `is_ignored` onto the exception path. Rejected as scope creep (D-02); revisit as its own phase.
- **Two-step pending→approved approval** — rejected for D-07's single-action attribution.
- **Active push for expiring exceptions** (Slack/email/digest) — belongs to Phase 40.
- **Frozen-snapshot scoping** — a later phase could add snapshot scopes if live membership (D-11) proves too broad.
- **Free-text / external approver** — D-08 requires a tenant-user reference.
- **Most-specific-wins overlap precedence** — D-12 chose OR semantics.
- **Exception-form/list visual design** — handled by `/gsd-ui-phase` (UI-SPEC, already produced).

None of these were scope creep — discussion stayed within the four success criteria.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EXC-01 | Mark false-positive / accept-risk with required justification, approver, and scope (finding / asset / asset-group) | `exceptions` table schema (Standard Stack §Schema), scope-match SQL (Architecture Patterns §Pattern 2), router/RBAC/audit wiring (Code Examples §5) |
| EXC-02 | Mandatory expiry; excluded from active queues, SLA timers, and dashboards until expiry | Exclusion sweep (Architecture Patterns §Consumer Sweep, all 3 tiers), shared `active_exception_subquery` seam (Pattern 1), D-16 SLA-subtraction seam (Pattern 3), expiry validation (Pitfall 9, Code Examples §4) |
| EXC-03 | Every exception emits an audit event (who/why/scope/expiry) | `audit()` wiring (Code Examples §5), action-name convention (Architecture Patterns §Audit) |
| EXC-04 | Expired exceptions auto-resurface into the active queue | Compute-on-read design (Pattern 1) — D-04 satisfied by construction; no scheduler needed for the primary consumers (staleness caveat only on materialized asset-score fields, see Pitfall 7) |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Frontend: Next.js 15 App Router + React 19 + TypeScript 5.5 + Tailwind 3.4. Fonts locked (Inter + JetBrains Mono) — no substitution. Colors via CSS variables from `foundation.md` only — no freehand hex. No screen ships without empty/loading/error states. No Tailwind admin-template patterns. No generic SaaS copy.
- Backend: FastAPI + Postgres + Redis. State lives in Postgres/Redis, never in-process dicts (v1.0 Phase 1 precedent).
- Auth: OIDC + email/password; session state in Redis; RBAC via `require_viewer`/`require_analyst`/`require_admin`.
- The `sketch-findings-getvul` skill governs all UI decisions for this phase — already applied and checker-approved in `39-UI-SPEC.md`; this research treats that file as the frontend contract and does not re-derive it.
- v5.0 foundational principles (REQUIREMENTS.md): the v4.0 risk-exposure score is authoritative and **never re-derived**; lane discipline (no new scanner/patch-deployer/agent); single-VM Docker Compose + in-process asyncio scheduler only (no new infra); every query tenant-scoped; every new mutating action audited.

## Summary

Phase 39 is a pure backend-extension phase: one new table (`exceptions`), three new endpoints (grant/list/revoke), and a compute-on-read exclusion join threaded into a **surprisingly large number of existing read paths** (this research enumerates 20+ call sites across 12 files, not the 5 CONTEXT named as "known"). No new third-party library is needed anywhere — every building block (async SQLAlchemy `NOT EXISTS` correlated subqueries, Alembic migrations, `audit()`, `require_analyst`, live `AssetGroupMember` joins) already exists and has a direct precedent from Phases 32/36/37/38.

The highest-value finding from the consumer sweep: `list_vulnerabilities`, `list_vulnerabilities_by_host`, and `get_facets` all funnel through one shared function, `_apply_filters()` in `vulnerabilities/service.py` — adding the exclusion predicate there covers three consumers in one edit. A second, equally important finding: **two consumers not named in CONTEXT are governance-critical and must not be skipped** — `ticketing/rule_engine.py`'s automated ticket-creation rule engine and `sla_tier_service.py::detect_and_escalate`'s Slack/email/PagerDuty escalation firing. Leaving either unpatched means an analyst's "accept this risk" decision would still silently auto-open a ticket or fire a breach alert — a direct contradiction of the phase's own goal, arguably worse than today's status quo.

The SLA-subtraction requirement (D-16) is tractable because of a structural fact this research verified: `resolve_state_for_vuln` is only ever called on findings that already passed the exclusion filter upstream — so at the point it runs, the finding is *never currently under an active exception*. The subtraction problem reduces to summing **lapsed** (expired or revoked) exception windows only, which is a small, boundable computation, not an open-ended live overlap problem.

**Primary recommendation:** build one shared helper (`active_exception_subquery(tenant_id, now)` in a new `app/exceptions/service.py`) returning a correlated `EXISTS` clause matched against `Vulnerability.id` / `(cve_id, asset_id)` / `(cve_id, asset_group via AssetGroupMember)`; apply `~subquery` to `_apply_filters`, `_base_open_vulns`, `compute_risk_scores`, `compute_finding_risk_scores`'s asset rollup, `run_sla_tier_pass`, `detect_and_escalate`, `campaigns/service.py`'s progress/ticketing queries, and `ticketing/rule_engine.py`'s asset/remediation matchers; extend `compute_sla_state`/`resolve_state_for_vuln` with an `excepted_seconds` parameter fed by a batched, interval-merged lookup of the finding's own lapsed-exception history.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Grant / revoke exception (mutation) | API/Backend | Browser/Client (dialog form) | FastAPI router owns validation, RBAC, audit; browser only collects input |
| Compute-on-read exclusion join | API/Backend | Database/Storage | SQL `NOT EXISTS`/`EXISTS` subquery evaluated per-request; indexes make it cheap, but the join logic lives in the service layer, not the DB (no views/triggers per this codebase's convention) |
| SLA due-date subtraction (D-16) | API/Backend | — | Pure computation inside `sla_tier_service.py`; no client involvement |
| Scope resolution (asset-group live membership) | API/Backend | Database/Storage | `AssetGroupMember` join, same tier as every other live-membership feature (Phase 32/38 precedent) |
| Audit trail | API/Backend | Database/Storage | `audit()` writes `audit_logs`; no client-side audit logic exists anywhere in this codebase |
| Expiring-soon badge + list sort | Browser/Client | API/Backend | Backend returns `expires_at`; client renders the `sla-pill` tier and default-sorts — no new backend "is-expiring-soon" flag needed (client derives it from the date, mirroring how `sla_state` classification patterns already work) |
| RBAC gate | API/Backend | — | `require_analyst`/`require_viewer` dependency injection, zero client enforcement (client only hides buttons for UX, never the security boundary) |

## Standard Stack

### Core

No new dependencies. This phase is a pure extension of the existing stack:

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy (async) | already pinned | ORM + `NOT EXISTS`/`EXISTS` correlated subqueries | Every exclusion consumer already uses this async session pattern |
| Alembic | already pinned | Schema migration (`050_add_exceptions.py`) | 49 existing migrations follow one convention exactly (verified: `backend/alembic/versions/049_add_campaigns.py`) |
| FastAPI + Pydantic | already pinned | Router + request/response schemas | Every other feature router (`campaigns`, `vulnerabilities`, `assets`) follows this shape |
| structlog | already pinned | Structured logging on the (optional) lazy-audit-on-expiry sweep | Matches `sla_tier_service.py`'s `logger.info(...)` convention |

**Installation:** None required — zero new packages. `[VERIFIED: codebase read]`

### Supporting

Not applicable — no supporting libraries are introduced.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Compute-on-read `NOT EXISTS` join (D-01 locked) | A Postgres materialized view or trigger-maintained denormalized `is_excepted` column on `vulnerabilities` | Would violate D-01/D-04 (loses "free" auto-resurface, needs a re-flip mechanism); this codebase has zero precedent for triggers or materialized views anywhere — would be a first-of-kind infra pattern, explicitly against "no new infra" |
| Python-side interval merge for D-16 subtraction | A specialized interval-algebra library (e.g. `portion`) | Per-finding lapsed-exception count is typically 0-1 (D-12 overlap is an edge case, not the common path); a ~10-line merge-adjacent-sorted-intervals loop is simpler than a new dependency for this volume |

### Schema (Claude's Discretion — recommended)

New module `backend/app/exceptions/` (mirrors `backend/app/campaigns/` shape: `models.py`, `service.py`, `schemas.py`, `router.py`).

**Table `exceptions`:**

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | UUID PK | No | `UUIDPrimaryKeyMixin` |
| `tenant_id` | UUID FK `tenants.id` CASCADE | No | indexed — every query's IDOR boundary |
| `type` | String(20) | No | `FALSE_POSITIVE` \| `ACCEPTED_RISK` (Python `str, enum.Enum`, matches `VulnStatus`/`BusinessCriticality` convention — **not** a native Postgres enum, zero precedent for that anywhere in this codebase) |
| `scope_type` | String(20) | No | `FINDING` \| `ASSET` \| `ASSET_GROUP` |
| `cve_id` | String(20) | No | indexed; always populated regardless of scope_type (D-10: scope always pins a CVE) |
| `vulnerability_id` | UUID FK `vulnerabilities.id` SET NULL | Yes | populated only when `scope_type=FINDING` — the exact detected row |
| `asset_id` | UUID FK `assets.id` SET NULL | Yes | populated for `FINDING` and `ASSET` scope (mirrors `Vulnerability.asset_id`'s own `ondelete="SET NULL"` choice — models.py:62) |
| `asset_group_id` | UUID FK `asset_groups.id` SET NULL | Yes | populated only when `scope_type=ASSET_GROUP` |
| `justification` | Text | No | app-layer cap 1000 chars (matches UI-SPEC textarea cap) |
| `approver_user_id` | UUID FK `users.id` SET NULL | DB-nullable, app-required | D-08 — see Pitfall 3 for why DB-nullable ≠ optional |
| `granted_by_user_id` | UUID FK `users.id` SET NULL | DB-nullable, app-required | the authenticated analyst who submitted the grant (`CurrentUser.id`, server-derived, never client-supplied) — distinct from `approver_user_id` (D-07 permits same-or-different person) |
| `expires_at` | DateTime(timezone=True) | No | D-14 — validated future + capped, see Code Examples §4 |
| `revoked_at` | DateTime(timezone=True) | Yes | D-17 |
| `revoked_by_user_id` | UUID FK `users.id` SET NULL | Yes | |
| `resurfaced_audited_at` | DateTime(timezone=True) | Yes | **optional** (CONTEXT: discretionary) — see Pattern 4 |
| `created_at`/`updated_at` | TimestampMixin | No | `created_at` doubles as "granted at" |

**Indexes:**
- `ix_exceptions_tenant_id` (tenant_id)
- `ix_exceptions_vulnerability_id` (vulnerability_id) — FINDING-scope equality lookup
- `ix_exceptions_asset_scope` (tenant_id, asset_id) — ASSET-scope lookup
- `ix_exceptions_group_scope` (tenant_id, asset_group_id) — ASSET_GROUP-scope lookup
- `ix_exceptions_cve` (tenant_id, cve_id) — narrows ASSET/ASSET_GROUP branches fast
- `ix_exceptions_expires_at` (expires_at) — default list sort (D-19) + the `expires_at > now()` predicate
- `ix_exceptions_not_revoked` partial index on `(tenant_id)` `WHERE revoked_at IS NULL` — **valid** because the predicate is a pure NULL check (see Pitfall 2 for the pattern that is *not* valid)

No `UniqueConstraint`/partial-unique-index is needed (unlike `Campaign`'s `uq_campaign_active_remediation`) — D-12 explicitly permits multiple overlapping active exceptions on the same finding.

**Migration:** `backend/alembic/versions/050_add_exceptions.py`, `down_revision = "049_add_campaigns"` (the current head, confirmed via `ls backend/alembic/versions | tail`). Revision id `"050_add_exceptions"` is 19 chars, safe under the `varchar(32)` `alembic_version.version_num` cap (the existing migrations' own documented constraint). `[VERIFIED: alembic/versions/049_add_campaigns.py header comment]`

## Architecture Patterns

### System Architecture Diagram

```
                     ┌─────────────────────────┐
   Browser           │ Vuln Drill Panel        │
   (analyst)         │  "Accept risk" /        │
                     │  "Mark false positive"  │
                     └────────────┬────────────┘
                                  │ opens
                                  ▼
                     ┌─────────────────────────┐
                     │ Exception Grant Dialog  │
                     │ scope→approver→         │
                     │ justification→expiry    │
                     └────────────┬────────────┘
                                  │ POST /api/v1/exceptions
                                  ▼
        ┌─────────────────────────────────────────────────┐
        │  API/Backend: exceptions/router.py                │
        │  require_analyst → validate D-03/D-06/D-14         │
        │  → INSERT exceptions row → audit("exception.grant")│
        └───────────────────────┬─────────────────────────┘
                                 │ persists
                                 ▼
                     ┌─────────────────────────┐
                     │   exceptions table       │
                     │ (tenant_id, type,         │
                     │  scope_type, cve_id,      │
                     │  vulnerability_id/        │
                     │  asset_id/asset_group_id, │
                     │  approver, expires_at,    │
                     │  revoked_at)              │
                     └────────────┬─────────────┘
                                  │ read by (NOT EXISTS / EXISTS correlated subquery)
                                  │ active_exception_subquery(tenant_id, now)
              ┌───────────────────┼────────────────────────────────────────┐
              ▼                   ▼                    ▼                  ▼
   list_vulnerabilities   sla_tier_service      risk_score.py /    remediation_service /
   (_apply_filters)       (resolve_state_for_    risk_exposure_    campaigns/service /
   get_facets             vuln, run_sla_tier_    service.py       rule_engine.py /
   list_vulnerabilities_  pass, detect_and_      (asset badges,   dashboard.py /
   by_host                escalate)              risk-scored      export.py / assets+
                                                  dashboards)      users routers
              │                   │                    │                  │
              └───────────────────┴────────────────────┴──────────────────┘
                                  │ excluded findings never surface here
                                  ▼
                     ┌─────────────────────────┐
                     │  /dashboard/exceptions   │  ← GET /api/v1/exceptions (list,
                     │  list + revoke button    │    require_viewer; lazy-audit sweep
                     │  passive "Nd left" pill  │    for newly-lapsed rows, Pattern 4)
                     └─────────────────────────┘
```

A reader can trace the primary use case (grant → excluded everywhere → auto-resurface) by following the arrows: the analyst's one POST lands in one table, and every downstream consumer *reads* that table fresh on every request — no consumer ever needs to be told "an exception expired," it simply stops matching.

### Recommended Project Structure

```
backend/app/exceptions/
├── __init__.py
├── models.py       # ExceptionRecord (NOT "Exception" — shadows the Python builtin, see Pitfall 10)
├── schemas.py       # ExceptionCreate / ExceptionResponse (Pydantic)
├── service.py       # active_exception_subquery(), grant/list/revoke logic, lapsed-duration lookup for D-16
└── router.py        # POST /, GET / (list), POST /{id}/revoke
backend/alembic/versions/
└── 050_add_exceptions.py
backend/tests/
└── test_exceptions.py   # new — no existing file; see Validation Architecture
frontend/src/app/dashboard/exceptions/
└── page.tsx
frontend/src/components/exceptions/
├── exception-grant-dialog.tsx
├── approver-combobox.tsx   # NEW sibling to reassign-combobox.tsx, not a verbatim reuse — see Pitfall 6
└── exceptions-table.tsx
frontend/src/lib/queries/
└── use-exceptions.ts
```

### Pattern 1: Shared "effective exclusion" seam (research emphasis #2)

**What:** One function returning a correlated SQLAlchemy `exists()` clause, callable from every consumer's own query-building code, rather than duplicating the join logic per file.

**When to use:** Any query that currently filters `Vulnerability.status.in_(["OPEN", "IN_PROGRESS"])` and represents an "active work" surface (list, count, badge, scoring, escalation, auto-ticketing).

**Recommended implementation** (`app/exceptions/service.py`):

```python
# Source: this codebase's own AssetGroupMember join precedent
# (app/assets/groups_service.py:37-38) + the corr_by_key batched-lookup
# precedent (vulnerabilities/service.py:217-240)
from sqlalchemy import and_, exists, or_, select
from app.assets.models import AssetGroupMember
from app.exceptions.models import ExceptionRecord
from app.vulnerabilities.models import Vulnerability


def active_exception_subquery(tenant_id: uuid.UUID, now: datetime):
    """Correlated EXISTS: does an active (non-expired, non-revoked)
    exception cover the OUTER Vulnerability row this is joined against?
    Caller applies `~active_exception_subquery(...)` to EXCLUDE, or the
    bare form to select actively-excepted rows (e.g. the exceptions list's
    own "is this still active" flag).
    """
    return exists(
        select(ExceptionRecord.id).where(
            ExceptionRecord.tenant_id == tenant_id,
            ExceptionRecord.revoked_at.is_(None),
            ExceptionRecord.expires_at > now,
            or_(
                ExceptionRecord.vulnerability_id == Vulnerability.id,
                and_(
                    ExceptionRecord.scope_type == "ASSET",
                    ExceptionRecord.cve_id == Vulnerability.cve_id,
                    ExceptionRecord.asset_id == Vulnerability.asset_id,
                ),
                and_(
                    ExceptionRecord.scope_type == "ASSET_GROUP",
                    ExceptionRecord.cve_id == Vulnerability.cve_id,
                    exists(
                        select(AssetGroupMember.asset_id).where(
                            AssetGroupMember.group_id == ExceptionRecord.asset_group_id,
                            AssetGroupMember.asset_id == Vulnerability.asset_id,
                        )
                    ),
                ),
            ),
        )
    )
```

This directly answers the research emphasis: `_apply_filters()` in `vulnerabilities/service.py` (lines 43-106) is the single choke point covering `list_vulnerabilities`, `list_vulnerabilities_by_host`, and `get_facets` in one edit — add `query = query.where(~active_exception_subquery(tenant_id, datetime.now(UTC)))` right after the existing `tenant_id ==` clause. `remediation_service._base_open_vulns`'s "active" branch (not its "ignored"/"all" branches — those intentionally show suppressed items) gets the same one-line addition and covers `get_remediations_grouped`, `get_hosts_for_remediation`, and `get_remediations_for_host` together.

### Pattern 2: Scope-match semantics (D-10/D-11) — three granularities, all CVE-pinned

`[ASSUMED — recommendation, not spelled out at column-level in CONTEXT]`: CONTEXT's UI mockup shows the CVE+asset context ("CVE-2024-3094 on prod-db-01") staying fixed across all three segmented-control options, confirming every scope type pins the *same* CVE (per D-10's explicit text). The meaningful difference between "This finding" and "This asset" is **which rows currently/future match**, not which CVE:

| scope_type | Matches | "Present and future" meaning (D-11) |
|---|---|---|
| `FINDING` | Exact `vulnerability_id` (the one detected row the drill panel is anchored on) | Narrow — covers re-scans by the *same* source (upsert dedup guarantees it's the same row), but NOT a new source later detecting the same CVE+asset pair |
| `ASSET` | `(cve_id, asset_id)` — any current or future *source* reporting this CVE on this asset | Broader — a second scanner starting to also flag this CVE on this host is automatically covered |
| `ASSET_GROUP` | `(cve_id, asset_group_id)` resolved live through `AssetGroupMember` | Broadest — covers every current/future group member, any source, per D-11's literal "asset-group Lab-hosts" example |

This is the interpretation this research recommends the planner adopt; it is internally consistent with D-11's "present and future" framing (which only has real content for `ASSET`/`ASSET_GROUP` — a `FINDING`-scoped exception is inherently static since dedup means the same source always maps to the same row). See Assumptions Log A1 and Open Questions Q1.

**Grant precondition reconciliation (D-03 × D-11):** D-03 ("grant only on actionable OPEN/IN_PROGRESS findings") cleanly applies to `FINDING` scope (a concrete existing row — reject with the UI-SPEC's declared copy "This finding is already remediated — nothing to except." if its status isn't OPEN/IN_PROGRESS). It must **NOT** be applied the same way to `ASSET`/`ASSET_GROUP` scope, which D-11 explicitly frames as forward-looking predicates that may have zero currently-matching OPEN rows (e.g., accepting risk for a CVE on a group before any member has been scanned yet) — a uniform precondition check would wrongly reject a legitimate forward-looking grant. `ASSET`/`ASSET_GROUP` grants should only validate that the target `asset_id`/`asset_group_id` itself exists and belongs to the tenant.

### Pattern 3: D-16 SLA-subtraction seam

**Verified structural fact:** `resolve_state_for_vuln` (`sla_tier_service.py:131-159`) is called from `list_vulnerabilities`, `get_vulnerability`, `run_sla_tier_pass`, and `detect_and_escalate` — and in every one of those call sites, by the time this function runs, the finding has **already passed** the exclusion filter (Pattern 1). This means the finding is, by construction, never *currently* under an active exception at the moment SLA state is resolved — the subtraction problem is only about **lapsed** (naturally expired, per D-04, or early-revoked, per D-17) exception windows, never a live one.

**Recommended signature change:**

```python
def compute_sla_state(
    *, first_detected_at: datetime, tier_days: int, approaching_pct: float,
    now: datetime, excepted_seconds: int = 0,
) -> tuple[datetime, str]:
    effective_start = first_detected_at + timedelta(seconds=excepted_seconds)
    sla_due_at = effective_start + timedelta(days=tier_days)
    approaching_at = sla_due_at - timedelta(days=tier_days * (1 - approaching_pct))
    if now >= sla_due_at:
        return sla_due_at, "breached"
    if now >= approaching_at:
        return sla_due_at, "approaching"
    return sla_due_at, "on_track"
```

`excepted_seconds` for a given finding = sum of `(COALESCE(revoked_at, expires_at) - created_at)` across every **lapsed** exception matching its scope (`revoked_at IS NOT NULL OR expires_at <= now`), **with overlapping windows merged, not naively summed** — D-12 explicitly permits simultaneous overlapping exceptions (e.g. a finding-level one stacked with an asset-group one), and a naive sum would double-count the overlap, over-crediting the SLA clock. Given the typical case is 0-1 lapsed exceptions per finding, a small Python interval-merge over a handful of `(start, end)` tuples is sufficient — no new library needed (see Don't Hand-Roll).

**Batching:** mirror the `corr_by_key` pattern already in `list_vulnerabilities` (service.py:217-240) — one extra page-scoped query fetching every lapsed exception matching the page's `(cve_id, asset_id)` set (+ any covering asset-groups), grouped into a dict, merged-and-summed per row in Python. For `run_sla_tier_pass`/`detect_and_escalate` (whole-tenant scans, not paginated), batch the same lookup tenant-wide once per tick instead of per-row.

### Pattern 4: Lazy-on-read audit for expiry (optional, CONTEXT discretionary)

Recommend adopting it, mirroring the campaigns precedent (`apply_lifecycle_transition`, `campaigns/service.py:151-211`, called only from the single-item `GET /{campaign_id}` read, never scattered across every consumer). For exceptions, the natural single checkpoint is the exceptions list endpoint (`GET /api/v1/exceptions`) — on each fetch, for every row where `expires_at <= now AND revoked_at IS NULL AND resurfaced_audited_at IS NULL`, write a system-attributed audit row (`action="exception.expire"`, `user_email="system:exception-expiry"`, mirroring `reopen_vulnerability`'s system-actor precedent, `vulnerabilities/service.py:464-476`) and set `resurfaced_audited_at = now`. This requires the optional `resurfaced_audited_at` column (Schema table above).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Role gating on grant/revoke | A new permission check | `require_analyst` (`auth/rbac.py:50-52`) | Every existing suppress/ignore endpoint already uses this exact dependency |
| Audit trail | A bespoke log call or a new table | `audit()` (`audit.py:143`) | Fail-closed transaction semantics already solved; a hand-rolled logger would silently succeed on audit-write failure, violating EXC-03/AUDIT-01 |
| Tenant-user search picker (Approver field) | A new search endpoint | `/users/directory` (already backs `useAssignableUsers`, `users/router.py:251`) | Same data (active tenant users), zero reason to duplicate |
| Interval-overlap math for D-16 | A dedicated interval-algebra package | ~10-line Python merge-adjacent-sorted-intervals loop | Typical N is 0-1 per finding (D-12 overlap is the edge case, not the common path) |
| Confirm-before-destructive-action UI | A new modal | `ConfirmModal` (variant `"warning"`, already installed per UI-SPEC) | Exact precedent for the Revoke action |
| Migration tooling | Manual SQL scripts | Alembic (49 existing migrations, one unbroken convention) | Consistency with `alembic current`/`alembic upgrade head` workflow |
| Live group-membership resolution | A frozen snapshot table | `AssetGroupMember` (already exists, `assets/models.py:155-164`) | D-11 explicitly requires live membership; this table is the exact existing mechanism Phase 32 built for the identical problem |

**Key insight:** every primitive this phase needs — RBAC, audit, live membership, compute-on-read exclusion, migration — already exists in this codebase with a working precedent from Phases 32, 36, 37, or 38. The risk in this phase is not "what do we build" but "which of the ~20 read paths did we forget to wire the shared helper into."

## Consumer Sweep (research emphasis #1 — full enumeration)

CONTEXT named 5 consumers as "known." A full-codebase grep for `Vulnerability.status.in_(["OPEN", "IN_PROGRESS"])` (and equivalent tuple/list forms) surfaced **~20 distinct call sites across 12 files**. Categorized by confidence and priority:

### Tier 1 — named in CONTEXT, definitely in scope

| # | File : Line | Function | Fix |
|---|---|---|---|
| 1 | `vulnerabilities/service.py:43-106` | `_apply_filters` | Add `~active_exception_subquery` — covers `list_vulnerabilities`, `list_vulnerabilities_by_host`, `get_facets` (3-for-1, see Pattern 1) |
| 2 | `vulnerabilities/service.py:276-347` | `get_vulnerability` | Does not need to 404/exclude (the exceptions list's own "View finding" cross-link needs the detail page reachable) — its role is inheriting the corrected `resolve_state_for_vuln` (D-16) so the detail view's SLA state is never stale |
| 3 | `sla_tier_service.py:111-159` | `resolve_state_for_vuln`/`compute_sla_state` | D-16 subtraction (Pattern 3) |
| 4 | `sla_tier_service.py:162-224` | `run_sla_tier_pass` | Add exclusion to its `status.in_(["OPEN","IN_PROGRESS"])` WHERE (line 184) so the *persisted* `sla_due_at`/`sla_breached` mirror also stops updating for actively-excepted rows |
| 5 | `assets/risk_score.py:91-154` | `compute_risk_scores` | Add exclusion to the raw-score subquery's WHERE (line 124-127) |
| 6 | `remediation_service.py:14-32` | `_base_open_vulns` | Add exclusion to the "active" branch only — covers `get_remediations_grouped`, `get_hosts_for_remediation`, `get_remediations_for_host` |
| 7 | `campaigns/service.py:88-118` | `get_campaign_progress` | Add exclusion to the member-count WHERE (line 105-108) |

### Tier 2 — discovered via sweep, HIGH confidence should-fix (governance-critical or literal "dashboards" text)

| # | File : Line | Function | Why it matters |
|---|---|---|---|
| 8 | `ticketing/rule_engine.py:85-142, 208-234` | `find_matching_assets`, `run_rule` | **Governance-critical, not in CONTEXT's list.** The automated ticket-creation rule engine runs on a scheduler tick and would auto-open a ticket for an asset whose only qualifying finding is under an active accept-risk exception — directly undermining the phase's purpose |
| 9 | `sla_tier_service.py:353-534` | `detect_and_escalate` | **Governance-critical, not in CONTEXT's list.** Fires Slack/Teams/email/PagerDuty + an in-app notification for approaching/breached findings; without the exclusion, an accepted-risk finding could still trigger a breach alert |
| 10 | `campaigns/service.py:249-384` | `bulk_create_campaign_tickets` | Filters `OPEN/IN_PROGRESS` (line 282) to decide which members need a new ticket; must not ticket an excepted member |
| 11 | `assets/router.py:261-274, 388-403` | asset list + asset detail vuln-count/critical/high/exploitable/kev/**sla_breach** badges | Literal "dashboards" (EXC-02). Note: `sla_breach` here reads the *persisted* `Vulnerability.sla_due_at` column directly (bypasses `resolve_state_for_vuln` entirely) — fixing #4 above is a prerequisite for this one to be correct |
| 12 | `users/router.py:130-149, 358-381` | owner-risk aggregate list | Per-owner vuln-count/critical/high/exploitable badges — a "dashboard" surface by EXC-02's own wording |
| 13 | `vulnerabilities/dashboard.py:43, 189-208, 311` + `service.py:750` (`get_dashboard_stats`) | `compute_dashboard_tiles_v10`, `compute_top_vuln_v10`, `compute_nav_counts_v10`, `open_q` | The `/dashboard` page's own tiles/top-vuln spotlight/nav badge counts |
| 14 | `export.py:266, 318` | CSV/exec-summary export | Literally named as an example in the research emphasis ("exports") |
| 15 | `vulnerabilities/risk_exposure_service.py:347-399` | `compute_finding_risk_scores`'s asset-level MAX rollup subquery (lines 392-399) | D-15 explicitly names `Asset.risk_exposure_score` (the Phase 33/34 field), not just the older `Asset.risk_score`. The per-finding score-write loop itself (lines 347-385) does not need the filter — only the rollup does |
| 16 | `vulnerabilities/router.py:936-988` | `remediations_for_host` | **Bypasses the shared `_base_open_vulns` helper entirely** — a direct ad hoc query. Concrete proof that "add it to the shared helper" is necessary but not sufficient; this path needs its own fix |

### Tier 3 — discovered, reviewed, recommend explicitly OUT of scope (to prevent over-application)

| # | File | Reasoning |
|---|---|---|
| 17 | `connectors/sync.py:234-256` (clean-scan-streak reconciliation, SYNC-02) | Internal ingestion bookkeeping between scanner results and DB rows — unrelated to display/governance. Exceptions must NOT change scan-detection reconciliation; the finding stays OPEN "under the hood" per D-01 |
| 18 | `ticketing/service.py`, `ticketing/daily_sync.py` (SYNC-01..04 status write-back) | Mutates vuln STATUS from ticket-provider state — a different lane (Phase 37) from exception governance. Learning the exclusion join here risks breaking the sync pipeline for no benefit |
| 19 | `search.py::_search_vulnerabilities` | **Reviewed, recommend no change.** Already returns results across *every* status (no OPEN/IN_PROGRESS filter exists today — verified by reading the function) — finding a SUPPRESSED or REMEDIATED vuln via search is already expected behavior; adding exclusion here would be an inconsistent asymmetry, not a fix |
| 20 | `ai/grounding.py:123, 176` | v3.0 AI feature context-grounding (separate lane/milestone). Flagged as an open question (Q3), not mandated |
| 21 | `vulnerabilities/trends.py:267-302` | Historical trend/burndown lines. A trend chart arguably should show "this was open at time T" as a point-in-time historical fact even after a later exception — retroactively filtering history is a genuinely different design question than filtering a live list. Flagged as an open question (Q4), not mandated for this phase |
| 22 | `cspm/service.py`, `cspm/schemas.py` (Misconfiguration model) | A structurally separate model/table (CSPM cloud posture, not `Vulnerability`). CONTEXT's Scope Resolution section only references `Vulnerability` fields — CSPM parity would be scope creep |

**Given the size of Tier 2, the planner should explicitly decide the cut line** — at minimum, items #8/#9 (rule engine + escalation firing) should not be deferred, since skipping them creates a behavior *worse* than pre-Phase-39 status quo. Items #11-16 are straightforward once Pattern 1's shared helper exists (each is a 1-3 line addition to an existing WHERE clause) and can reasonably be split into their own plan/task within this phase rather than a separate phase, given D-15's literal "dashboards" wording.

## Common Pitfalls

### Pitfall 1: Two parallel SLA representations
**What goes wrong:** Fixing `resolve_state_for_vuln` alone (the read-time path used by `list_vulnerabilities`/`get_vulnerability`) leaves the *persisted* `Vulnerability.sla_due_at`/`sla_breached` mirror columns (written only by `run_sla_tier_pass`'s scheduler tick, per its own D-08 docstring) stale for any consumer reading those columns directly.
**Why it happens:** `sla_tier_service.py` was built (Phase 36) with a live read-time value AND a persisted mirror for consumers that can't afford a live join (ticket SLA pills, `assets/router.py`'s `sla_breach` badge count).
**How to avoid:** Patch `run_sla_tier_pass`'s own WHERE clause (Tier 1 #4) in addition to `resolve_state_for_vuln` — both paths need the exclusion, and D-16's subtraction logic needs to run inside `run_sla_tier_pass` too (not just the two direct read-time callers) or the persisted mirror will show an unsubtracted, too-early due date after resurface until the next scheduler tick.
**Warning signs:** An asset's `sla_breach` badge count and its detail page's live `sla_state` disagree for a recently-resurfaced finding.

### Pitfall 2: `now()` is not IMMUTABLE — cannot appear in a partial index predicate
**What goes wrong:** `CREATE INDEX ... WHERE expires_at > now()` fails at migration time with "functions in index predicate must be marked IMMUTABLE."
**Why it happens:** Postgres requires partial-index predicates to be provably stable across the life of the index; `now()` is STABLE, not IMMUTABLE.
**How to avoid:** Only index `revoked_at IS NULL` in a partial index (a pure NULL check, valid); keep `expires_at > :now` as a normal runtime WHERE clause backed by a plain (non-partial) index on `expires_at`.
**Warning signs:** Alembic migration fails on `upgrade()` with a Postgres error mentioning IMMUTABLE.

### Pitfall 3: `approver_user_id` "required" (D-08) vs. FK `ondelete="SET NULL"` looks contradictory
**What goes wrong:** A schema author might make `approver_user_id` `NOT NULL` at the DB level to "enforce" D-08, then discover `ondelete="SET NULL"` cannot satisfy a NOT NULL constraint if the referenced user is ever deleted.
**Why it happens:** D-08's "required" is a request-validation/business rule, not necessarily a DB-level constraint.
**How to avoid:** Follow the exact precedent already in this codebase (`Campaign.created_by_user_id`, `campaigns/models.py:63-65`): DB-nullable + `ondelete="SET NULL"`, with the Pydantic request schema (`ExceptionCreate`) enforcing non-null at the API boundary. Same reasoning for `granted_by_user_id`.
**Warning signs:** A migration that sets `nullable=False` alongside `ondelete="SET NULL"` on a user FK will work fine until the first user deletion, then throw an IntegrityError deep in an unrelated user-management code path.

### Pitfall 4: Naive summation double-counts overlapping exception windows (D-16 × D-12 interaction)
**What goes wrong:** If the lapsed-exception lookup for D-16 simply `SUM()`s every matching row's duration, a finding covered by two overlapping exceptions (e.g. a finding-level one AND an asset-group one, both lapsed) gets its SLA clock pushed back by MORE time than it was actually hidden for.
**Why it happens:** D-12 explicitly permits overlapping active exceptions (OR semantics) — this is a real, if uncommon, case.
**How to avoid:** Merge overlapping `[created_at, COALESCE(revoked_at, expires_at)]` intervals in Python before summing (Pattern 3). The common case (0-1 matching lapsed exceptions) makes this trivial; only the rare overlap case needs the merge logic to matter.
**Warning signs:** A finding's post-resurface SLA due date is further out than `first_detected_at + tier_days + (single exception's actual duration)`.

### Pitfall 5: The shared exclusion helper is necessary but not sufficient
**What goes wrong:** Adding `active_exception_subquery` to `_base_open_vulns` and `_apply_filters` feels like "covering everything," but `remediations_for_host` (`vulnerabilities/router.py:936-988`) is a hand-rolled query that never calls either shared helper.
**Why it happens:** Not every "active findings" query in this codebase routes through the shared helpers that exist — some routes were written directly against `Vulnerability` before/alongside the helper's other callers.
**How to avoid:** Treat the Tier 1/Tier 2 table above as the actual checklist, not "patch the two shared functions and assume done."
**Warning signs:** A finding excluded everywhere else still shows up under `/hosts/{asset_id}/remediations`.

### Pitfall 6: `reassign-combobox.tsx` cannot be reused verbatim for the Approver field
**What goes wrong:** The UI-SPEC lists `reassign-combobox.tsx` under "reuse verbatim," but the component (`frontend/src/components/assets/reassign-combobox.tsx`) hardcodes `useReassignAsset(assetId)` and calls `mutation.mutate(email)` directly on selection — there is no asset to reassign in the exception-grant dialog, and the approver field must not fire its own mutation (it is one field inside a larger multi-field form that submits once, on "Grant exception").
**Why it happens:** `ReassignCombobox` was built (Phase 12) as a self-contained widget bound to one specific mutation, not a generic controlled picker.
**How to avoid:** Build a new sibling component (`approver-combobox.tsx`) that copies the debounce/keyboard-nav/`useAssignableUsers`/avatar-rendering *pattern* verbatim but accepts `value`/`onSelect(user)` props instead of an internal mutation — the UX is identical, the data flow is different.
**Warning signs:** Attempting to import `ReassignCombobox` directly into the grant dialog and finding there is no `assetId` prop that makes sense to pass, and no way to prevent it from firing a reassignment mutation on selection.

### Pitfall 7: Materialized asset-level risk-score fields have a bounded staleness window on natural expiry — but this is pre-existing precedent, not a new gap
**What goes wrong:** Assuming that granting/revoking an exception must trigger a live recompute of `Asset.risk_exposure_score` (the Phase 33/34 field) to stay "always correct" would mean re-deriving/re-triggering a batch computation on every mutation — and worse, a pure time-based *expiry* (no action, per D-04) has nothing to trigger a recompute at all.
**Why it happens / why it's OK:** `[VERIFIED: grep of all call sites]` — `compute_finding_risk_scores` (the function that writes `Asset.risk_exposure_score`) is, as of today, called **only** from `connectors/sync.py:182` — not from any of the six existing ignore/unignore/suppress/unsuppress endpoints in `vulnerabilities/router.py`, all of which call *only* `compute_risk_scores` (the older `Asset.risk_score` field). This means the newer risk-exposure field already lags behind every existing suppress/ignore action until the next connector sync — Phase 39 introduces no new inconsistency by following the exact same precedent.
**How to avoid:** Grant/revoke endpoints should call `compute_risk_scores(db, tenant_id)` only (matching `/cve/ignore` etc. exactly) — do **not** attempt to also synchronously call `compute_finding_risk_scores` (that would make Phase 39 inconsistent with its own siblings, not more correct). Document the staleness window rather than trying to close it; closing it is out of scope and would touch the v5.0 foundational principle "the risk score is authoritative — v5.0 acts on it, never re-derives it."
**Warning signs:** None expected if this precedent is followed — flag if a future reviewer asks "why doesn't granting an exception refresh the asset's risk-exposure score," the answer is "neither does ignoring a CVE today."

### Pitfall 8: D-03's grant precondition, naively applied, would break valid forward-looking `ASSET`/`ASSET_GROUP` grants
See Pattern 2's "Grant precondition reconciliation" — worth restating as a pitfall since it is an easy mistake: applying the SAME "must be OPEN/IN_PROGRESS right now" check uniformly across all three scope types would make it impossible to accept risk for a CVE on an asset-group *before* any member has actually been detected with it, directly contradicting D-11's "present AND future" framing.

### Pitfall 9: Client-supplied `cve_id`/`asset_id` must not be trusted independently of the resolved target
**What goes wrong:** If the grant endpoint accepts `cve_id` and `asset_id` as independent client-supplied fields (rather than deriving them server-side from the resolved `vulnerability_id`/`asset_id`/`asset_group_id`), a malformed or malicious payload could create an exception row whose `cve_id` doesn't actually match the vulnerability it claims to scope, silently breaking the exclusion join for the wrong CVE (or excluding an unintended one).
**How to avoid:** For `FINDING` scope, look up the real `Vulnerability` row server-side by `vulnerability_id` + `tenant_id` and derive `cve_id`/`asset_id` from it — never accept them as independent request fields for that scope type.
**Warning signs:** A grant endpoint that accepts `cve_id` as a free top-level field without cross-checking it against the resolved target row.

### Pitfall 10: `Exception` is a Python builtin
**What goes wrong:** Naming the SQLAlchemy model class `Exception` shadows `builtins.Exception`, breaking any `except Exception:` in the same or an importing module and causing extremely confusing errors.
**How to avoid:** Name the class `ExceptionRecord` (table name `exceptions` is fine — only the Python class name collides).

## Code Examples

### 1. Migration skeleton

```python
# Source: this codebase's own 049_add_campaigns.py (verified, direct precedent)
revision = "050_add_exceptions"
down_revision = "049_add_campaigns"


def upgrade() -> None:
    op.create_table(
        "exceptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("scope_type", sa.String(20), nullable=False),
        sa.Column("cve_id", sa.String(20), nullable=False),
        sa.Column("vulnerability_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vulnerabilities.id", ondelete="SET NULL"), nullable=True),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("asset_group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("asset_groups.id", ondelete="SET NULL"), nullable=True),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("approver_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("granted_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resurfaced_audited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_exceptions_tenant_id", "exceptions", ["tenant_id"])
    op.create_index("ix_exceptions_vulnerability_id", "exceptions", ["vulnerability_id"])
    op.create_index("ix_exceptions_asset_scope", "exceptions", ["tenant_id", "asset_id"])
    op.create_index("ix_exceptions_group_scope", "exceptions", ["tenant_id", "asset_group_id"])
    op.create_index("ix_exceptions_cve", "exceptions", ["tenant_id", "cve_id"])
    op.create_index("ix_exceptions_expires_at", "exceptions", ["expires_at"])
    op.create_index(
        "ix_exceptions_not_revoked", "exceptions", ["tenant_id"],
        postgresql_where=sa.text("revoked_at IS NULL"),  # valid — pure NULL check, no volatile fn (Pitfall 2)
    )


def downgrade() -> None:
    op.drop_table("exceptions")  # indexes drop automatically with the table
```

### 2. Expiry validation (D-14)

```python
# Recommended location: app/exceptions/service.py, called from the router
# before INSERT.
MAX_EXPIRY_DAYS = 365  # [ASSUMED — CONTEXT's own example value, "e.g. <= 1 year"]
DEFAULT_EXPIRY_DAYS = {"FALSE_POSITIVE": 180, "ACCEPTED_RISK": 90}  # [ASSUMED — business policy, see Assumptions Log A2]

def validate_expiry(expires_at: datetime, now: datetime) -> None:
    if expires_at <= now:
        raise HTTPException(400, "Pick a date between tomorrow and the maximum allowed date.")
    if expires_at > now + timedelta(days=MAX_EXPIRY_DAYS):
        raise HTTPException(400, f"Pick a date between tomorrow and {(now + timedelta(days=MAX_EXPIRY_DAYS)).date()}.")
```

`DEFAULT_EXPIRY_DAYS` only matters for the frontend's pre-fill UX (UI-SPEC: "Expires pre-filled to the type's default window") — the server's cap/future validation above is authoritative regardless of what value the client pre-filled or the analyst edited it to, so client and server never need to share this constant byte-for-byte.

### 3. Grant endpoint skeleton (RBAC + audit wiring, EXC-01/EXC-03/D-07/D-09/D-18)

```python
# Source: pattern mirrors backend/app/vulnerabilities/router.py's
# ignore_cve (audit-then-commit) and campaigns/router.py's RBAC wiring.
@router.post("/")
async def grant_exception(
    body: ExceptionCreate,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
):
    # 1. Resolve + validate target by scope_type (Pitfall 9 — derive, don't trust client cve_id/asset_id for FINDING scope)
    # 2. D-03: FINDING scope only — reject if not OPEN/IN_PROGRESS (Pattern 2)
    # 3. D-14: validate_expiry(body.expires_at, datetime.now(UTC))
    # 4. Resolve approver_user_id against tenant-scoped users table (D-08)
    record = ExceptionRecord(
        tenant_id=user.tenant_id, type=body.type, scope_type=body.scope_type,
        cve_id=resolved_cve_id, vulnerability_id=..., asset_id=..., asset_group_id=...,
        justification=body.justification, approver_user_id=body.approver_user_id,
        granted_by_user_id=user.id, expires_at=body.expires_at,
    )
    db.add(record)
    await db.flush()

    await compute_risk_scores(db, user.tenant_id)  # matches ignore_cve precedent exactly (Pitfall 7)

    await audit(
        db, user, "exception.grant", "exception", str(record.id),
        {"type": body.type, "scope_type": body.scope_type, "cve_id": resolved_cve_id,
         "approver_user_id": str(body.approver_user_id), "justification": body.justification,
         "expires_at": body.expires_at.isoformat()},
    )
    await db.commit()
    return record
```

Extend the `## Actions` comment block in `audit.py` (lines 53-76) with `exception.grant, exception.revoke` (and `exception.expire` if Pattern 4 is adopted) — every other feature phase has added its own action names to that same list.

## State of the Art

| Old Approach | Current Approach (this phase) | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Ad-hoc `SUPPRESSED`/`FALSE_POSITIVE` status flip via `/cve/ignore`, bare `reason` string, no approver, no expiry | Governed `exceptions` table: justification + named approver + explicit CVE×scope + mandatory capped expiry, all required | Phase 39 | The legacy paths are NOT retired (D-02) — this is a second, parallel, more rigorous mechanism that the exclusion join treats as a union with the legacy status flip |
| Single flat SLA representation | Two representations already coexist as of Phase 36 (read-time `resolve_state_for_vuln` vs. persisted `sla_due_at`/`sla_breached` mirror) | Phase 36 (pre-existing, not introduced by 39) | Phase 39 must patch both, not just the one CONTEXT names explicitly (Pitfall 1) |

**Deprecated/outdated:** Nothing in this phase deprecates existing functionality — D-02 is explicit that the legacy suppress paths are untouched.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `FINDING` scope matches the exact `vulnerability_id`; `ASSET` scope matches `(cve_id, asset_id)` across all sources; `ASSET_GROUP` matches `(cve_id, asset_group_id)` via live membership | Architecture Patterns §Pattern 2 | If the product intent for "This finding" vs. "This asset" is actually identical (both meaning cve+asset), the schema still works but the `vulnerability_id` column becomes redundant/unused for `FINDING` rows — low-risk either way since both interpretations use the same table shape, only the router's scope-resolution branch differs |
| A2 | Hard expiry cap = 365 days; default windows FALSE_POSITIVE=180d, ACCEPTED_RISK=90d | Standard Stack §Schema, Code Examples §2 | Pure business-policy numbers with no code-verifiable source — if wrong, only affects UX pre-fill defaults and the validation ceiling, both single-constant changes, not an architectural risk |
| A3 | Grant/revoke should call `compute_risk_scores` only, not `compute_finding_risk_scores` | Pitfall 7 | HIGH confidence — `[VERIFIED: grep of all call sites of both functions]`, not really an assumption; listed here for visibility since it reverses an initially-plausible-sounding "should recompute everything" intuition |
| A4 | Tier 2 consumers (#11-16) should be addressed within Phase 39 rather than deferred | Consumer Sweep | If deferred, EXC-02's literal "dashboards" text is only partially satisfied at phase close — a reasonable, disclosed scope-cut, not a silent gap, as long as the planner makes the choice explicitly rather than by omission |

**A3 is effectively verified, not assumed — included for transparency about the reasoning chain, not because the underlying fact is in doubt.**

## Open Questions

1. **Is the FINDING vs. ASSET scope distinction (vulnerability_id vs. cve_id+asset_id) the product's actual intent?**
   - What we know: CONTEXT confirms 3 distinct scope options exist and are always CVE-pinned (D-10); the UI-SPEC shows a 3-way segmented control with a fixed CVE+asset context header.
   - What's unclear: CONTEXT never states the literal column-level difference between "This finding" and "This asset" — both could theoretically resolve to the identical `(cve_id, asset_id)` predicate with `scope_type` as a display-only label.
   - Recommendation: Adopt A1's interpretation (it gives each option genuinely different coverage, and gives D-11's "present and future" language real content for `ASSET` scope) — but flag for a quick confirm during planning/discuss if there's any doubt, since it's a one-line change to the router's scope-resolution branch either way, not a schema change.

2. **Does the planner want the optional lazy-on-read expiry-audit row (Pattern 4)?**
   - What we know: CONTEXT marks it explicitly optional ("no actor, so it's optional").
   - What's unclear: whether EXC-03's audit completeness expectation (every exception's full lifecycle traceable) implicitly wants this even though CONTEXT didn't lock it.
   - Recommendation: adopt it — the cost is one nullable column + a guarded write in the list endpoint, and it closes an otherwise-silent gap in the audit trail ("this exception just... stopped showing up, with no record of when").

3. **Should `ai/grounding.py`'s context-building queries learn the exclusion join?**
   - What we know: it feeds "explain this vuln"/prioritization-narrative AI prompts with the tenant's OPEN/IN_PROGRESS findings (v3.0 feature, separate lane).
   - What's unclear: whether an AI narrative referencing/prioritizing an already-excepted finding is a real user-facing problem or a non-issue (the AI output is advisory text, not a queue item).
   - Recommendation: leave out of Phase 39's must-fix list; note for whoever next touches AI grounding.

4. **Should `trends.py`'s historical burndown lines retroactively exclude excepted findings?**
   - What we know: trend/burndown charts (Phase 42 territory, TREND-01/02) currently count OPEN/IN_PROGRESS at query time for each historical bucket.
   - What's unclear: whether a trend chart should show "this was open at time T" (a historical fact, arguably correct to leave alone) or apply today's exclusion retroactively (arguably wrong — the exception didn't exist at time T).
   - Recommendation: leave untouched in Phase 39; this is more naturally Phase 42's concern once TREND-03's "risk-model-version-boundary aware" annotation work exists to reason about exactly this class of retroactive-filtering question.

## Environment Availability

No new external dependency. This phase's only infrastructure touch is an Alembic migration against the same Postgres instance every other phase already migrates.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PostgreSQL | `exceptions` table + all exclusion joins | Yes (49 prior migrations run against it) | — | — |
| Alembic | Migration `050_add_exceptions.py` | Yes | already pinned in `pyproject.toml` | — |
| FastAPI / Pydantic / SQLAlchemy async | Router + service layer | Yes | already pinned | — |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest, `asyncio_mode = "auto"`, session-scoped event loop (`pyproject.toml:74-82`) |
| Config file | `backend/pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())") JWT_SECRET_KEY=test-secret pytest backend/tests/test_exceptions.py -x` |
| Full suite command | `ENCRYPTION_KEY=... JWT_SECRET_KEY=... pytest backend/tests/` (per-file is required, not whole-dir — see project memory `getvul-backend-pytest-env`: whole-dir runs produce false failures) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EXC-01 | Grant creates a row with justification/approver/scope/expiry; rejected without any one of them | unit/integration | `pytest backend/tests/test_exceptions.py::test_grant_requires_all_fields -x` | ❌ Wave 0 |
| EXC-01 | D-03: grant rejected on a REMEDIATED finding for FINDING scope; allowed for ASSET/ASSET_GROUP scope with zero current matches | integration | `pytest backend/tests/test_exceptions.py::test_grant_precondition_by_scope -x` | ❌ Wave 0 |
| EXC-02 | Active exception excludes the finding from `list_vulnerabilities`, `compute_risk_scores`, `get_campaign_progress` | integration | `pytest backend/tests/test_exceptions.py::test_active_exception_excludes_from_consumers -x` | ❌ Wave 0 |
| EXC-02 | D-16: resurfaced finding's SLA due date reflects the excepted duration, not an instant breach | unit | `pytest backend/tests/test_exceptions.py::test_sla_subtraction_on_resurface -x` | ❌ Wave 0 |
| EXC-02 | D-12: overlapping exceptions — OR-exclusion, latest-expiry governs resurface | integration | `pytest backend/tests/test_exceptions.py::test_overlap_or_semantics -x` | ❌ Wave 0 |
| EXC-03 | Grant and revoke each write exactly one `audit_logs` row with the right payload shape | integration | `pytest backend/tests/test_exceptions.py::test_grant_revoke_audit_payload -x` | ❌ Wave 0 |
| EXC-04 | Naturally-expired exception (no action taken) auto-resurfaces the finding on the next read, with no scheduler tick run | integration | `pytest backend/tests/test_exceptions.py::test_expiry_auto_resurface_no_retrigger -x` | ❌ Wave 0 |
| D-17 | Early revoke immediately resurfaces + audits who/when | integration | `pytest backend/tests/test_exceptions.py::test_early_revoke_resurfaces -x` | ❌ Wave 0 |
| D-10/D-11 | Asset-group scope covers a newly-added member and a newly-detected source without re-granting | integration | `pytest backend/tests/test_exceptions.py::test_live_group_membership -x` | ❌ Wave 0 |
| Tier 2 governance | Excepted finding is excluded from `find_matching_assets`/`run_rule` (auto-ticket) and `detect_and_escalate` | integration | `pytest backend/tests/test_exceptions.py::test_excluded_from_rule_engine_and_escalation -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** quick run command above, scoped to `test_exceptions.py`.
- **Per wave merge:** full suite command (all `backend/tests/*.py` files, per-file invocation per the project's known env gotcha).
- **Phase gate:** Full suite green before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `backend/tests/test_exceptions.py` — new file, no existing coverage for any of the above (verified: `ls backend/tests | grep -i except` returned nothing).
- [ ] No new shared fixtures needed beyond the existing inline-seed + `client_factory` pattern already used by `test_campaigns.py`/`test_asset_groups.py` (reuse verbatim, per that file's own header comment).
- [ ] Framework install: none — pytest + asyncio plugin already configured.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Unchanged — reuses existing session auth |
| V3 Session Management | No | Unchanged |
| V4 Access Control | Yes | `require_analyst` for grant/revoke, `require_viewer` for list (D-09); every query filters `tenant_id` (IDOR boundary, matches every existing router's `T-XX-04`-style pattern) |
| V5 Input Validation | Yes | Pydantic `ExceptionCreate` schema: `type`/`scope_type` as `Literal[...]` (not free string), `justification` length-capped, `expires_at` future+capped (D-14, Code Examples §2), approver/asset/asset-group FKs resolved server-side against tenant-scoped tables (not trusted blindly) |
| V6 Cryptography | No | No secret material on this table (unlike `ConnectorConfig` credentials) |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Cross-tenant exception grant/revoke (IDOR) | Tampering / Information Disclosure | Every query (`grant`, `list`, `revoke`, and the exclusion subquery itself) filters `tenant_id == user.tenant_id`; a cross-tenant `vulnerability_id`/`asset_id`/`asset_group_id`/`approver_user_id` in the request body must resolve against a tenant-scoped lookup and 404 (not 403) on a miss — matches `get_vuln_correlation`'s documented "cross-tenant vuln_id is indistinguishable from a missing one" convention |
| Authorization bypass (viewer granting/revoking) | Elevation of Privilege | `require_analyst` dependency, not a manual role string check |
| Governance bypass via malformed scope payload | Tampering | Pitfall 9 — derive `cve_id`/`asset_id` server-side from the resolved target for `FINDING` scope rather than trusting independent client-supplied fields |
| Backdating/over-capping expiry to quietly defeat "never permanently silenced" | Tampering / Repudiation | D-14 server-side validation (future-only + hard cap) is authoritative regardless of client `min`/`max` date-input attributes, which are UX hints only |
| Audit-row loss on grant/revoke (compliance gap) | Repudiation | `audit()`'s existing fail-closed contract (any exception in `audit()` propagates and the caller's `db.commit()` is skipped) — no change needed, just correct usage (audit-then-commit, same order as `ignore_cve`) |

## Sources

### Primary (HIGH confidence — direct codebase reads, this session)
- `backend/app/vulnerabilities/models.py` — `VulnStatus` enum, `Vulnerability` columns (`sla_due_at`, `sla_breached`, `risk_exposure_score`)
- `backend/app/vulnerabilities/router.py` (lines 500-999) — `/cve/ignore`/`unignore`, `/remediations/suppress`/`unsuppress`, `remediations_for_host` (bypass discovery)
- `backend/app/vulnerabilities/service.py` — `_apply_filters`, `list_vulnerabilities`, `get_vulnerability`, `get_dashboard_stats`, `get_top_findings_for_ai_batch`
- `backend/app/vulnerabilities/sla_tier_service.py` (full file) — `resolve_state_for_vuln`, `compute_sla_state`, `run_sla_tier_pass`, `detect_and_escalate`
- `backend/app/vulnerabilities/remediation_service.py` (full file) — `_base_open_vulns` and its 3 callers
- `backend/app/vulnerabilities/risk_exposure_service.py` (lines 300-399) — `compute_finding_risk_scores`, asset MAX rollup
- `backend/app/assets/risk_score.py` (full file) — `compute_risk_scores`
- `backend/app/assets/models.py` — `Asset.is_ignored`, `AssetGroup`, `AssetGroupMember`, `AssetGroupExposureOverride`
- `backend/app/assets/router.py` (lines 255-310, 385-425) — asset list/detail vuln-count badges
- `backend/app/assets/groups_service.py` — live `AssetGroupMember` join precedent
- `backend/app/campaigns/service.py`, `backend/app/campaigns/models.py`, `backend/alembic/versions/049_add_campaigns.py` — migration/model/partial-index convention, `get_campaign_progress`, `bulk_create_campaign_tickets`
- `backend/app/audit.py` (full file) — `audit()` fail-closed contract, action-naming convention
- `backend/app/auth/rbac.py` (full file) — `require_analyst`/`require_viewer`/`require_admin`
- `backend/app/main.py` (lines 255-335) — router registration pattern
- `backend/app/search.py` (full file) — confirmed no status filter on vuln search today
- `backend/app/users/router.py` (lines 115-175, 355-395) — owner-risk aggregate, `/directory` endpoint
- `backend/app/export.py` (lines 250-330) — CSV/summary export status filters
- `backend/app/ticketing/rule_engine.py` (lines 85-234) — automated rule engine (governance-critical discovery)
- `backend/app/tenants/models.py` (full file) — `Tenant`, `User`, `UserRole`
- `backend/pyproject.toml` (pytest/ruff/mypy config sections)
- `backend/tests/test_campaigns.py` (header + imports) — test-authoring convention
- `frontend/src/components/assets/reassign-combobox.tsx` (full file) — confirmed non-verbatim-reusable
- `.claude/skills/sketch-findings-getvul/SKILL.md` (lines 1-60) — design-system index (fully applied already in `39-UI-SPEC.md`)
- Grep sweep: `Vulnerability.status.in_(["OPEN","IN_PROGRESS"])` and equivalents across `backend/app/**/*.py` (~20 call sites, 12 files) — full Consumer Sweep enumeration
- Grep: all call sites of `compute_risk_scores`/`compute_finding_risk_scores` — Pitfall 7 / Assumption A3

### Secondary (MEDIUM confidence)
- None — this phase required no external web research; it is a 100% internal-pattern-extension phase with zero new third-party dependency, so no Context7/WebSearch lookups were performed or needed.

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — zero new dependencies, 100% verified against existing pinned versions and 4 prior phases' migration/router/service conventions.
- Architecture (exclusion seam, scope SQL, SLA-subtraction seam): HIGH for the mechanism (verified against actual function signatures and call graphs), MEDIUM for the exact FINDING-vs-ASSET column semantics (flagged as A1/Q1 — a reasoned recommendation, not something CONTEXT spelled out at the column level).
- Pitfalls: HIGH — every pitfall in this document is grounded in a specific, cited line range this session read directly (not generic domain knowledge), including two (Pitfall 1, Pitfall 7) that overturn an initially-plausible-but-wrong assumption via direct verification.
- Consumer sweep completeness: HIGH confidence the enumeration is comprehensive for `Vulnerability`-status-based queries (exhaustive grep across `backend/app`); MEDIUM confidence on the Tier 2/Tier 3 priority calls, which are judgment calls flagged as such (A4, Q3, Q4) rather than presented as settled fact.

**Research date:** 2026-08-18
**Valid until:** 2026-09-17 (30 days — this is an internal-codebase-only research pass with no external library version drift risk; the only staleness risk is if a concurrent phase touches the same files, which the planner should check via `git log` at plan time)
