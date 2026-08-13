# Phase 36: Remediation SLA Engine & Escalation - Research

**Researched:** 2026-08-13
**Domain:** Backend scheduler-driven state machine (risk-tier SLA computation) + multi-channel outbound webhook/SMTP escalation + tenant admin settings UI
**Confidence:** MEDIUM-HIGH — every backend/frontend codebase claim below is `[VERIFIED]` via direct file read; external channel contracts are `[CITED]` via live fetch/search, including one HIGH-impact, time-sensitive correction to what training data would otherwise assume (Microsoft Teams webhook mechanism).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**SLA State Model**
- **D-01:** SLA policy is **risk-tier-keyed**, computed off the v4.0 `Vulnerability.risk_exposure_score` bands (`RISK_SCORE_TIER_CRITICAL=80 / HIGH=50 / MEDIUM=20` from [risk_score.py](../../../backend/app/assets/risk_score.py#L59-L61)). Default policy: critical 7d / high 30d / moderate 90d. **This keys off the raw shadow-computed `risk_exposure_score`, independent of the `cutover_risk_exposure_scoring` flag** (which stays default-OFF and only governs which score is *primary* for sort/display).
- **D-02:** `approaching` is defined as a **configurable percentage of the SLA window elapsed** (e.g. 80%), which **scales per-tier automatically** (80% of 7d vs 80% of 90d). Chosen over a fixed lead-time window so long moderate windows get a proportionate warning.
- **D-03:** Findings with a **NULL `risk_exposure_score`** fall back to the existing **severity-keyed** SLA until they are scored. The severity path is retained specifically as this fallback (see D-08). — **Reversibility:** costly — removing the fallback later means guaranteeing every finding is scored before SLA runs, which touches the backfill ordering.

**Escalation Channels**
- **D-04:** Build **all four channels via webhooks + existing SMTP**: Slack incoming webhook, Microsoft Teams incoming webhook, PagerDuty Events API, and reuse `email.py` (SMTP). **No OAuth apps** — webhook/API-key config only. Channel-specific payload formatting per channel.
- **D-05:** **Per-transition-type routing.** The tenant maps each transition type independently: `approaching → [zero-or-more channels]`, `breached → [zero-or-more channels]` (e.g. approaching → Slack; breach → Slack + PagerDuty).
- **D-06:** **Configurable tier floor** for escalation. Admin sets a minimum tier that escalates (e.g. "high + critical escalate; moderate tracks state silently but does not page"). Prevents alert fatigue on 90d moderate windows. All tiers still *track* state and show a badge; the floor only gates *escalation firing*.

**Transition Tracking & "Exactly Once"**
- **D-07:** A new **escalation-event table** records each `(finding_id, from_state, to_state, channel, fired_at, tenant_id)`. Firing is gated on "no row exists for this (finding, transition, channel) yet" → clean once-only semantics and a **user-visible, auditable escalation history**. Every fire also goes through the fail-closed `audit()` path ([audit.py:143](../../../backend/app/audit.py#L143)). — **Reversibility:** one-way — introduces a new table via Alembic migration; dropping it later loses escalation history.

**Old-SLA Coexistence**
- **D-08:** **Tier engine owns state; keep `sla_breached` as a derived mirror.** The new engine is the source of truth for state + due dates. `Vulnerability.sla_breached` (boolean) is kept but written as a *derived mirror* so already-shipped consumers (tickets `SlaPill`, metrics, dashboard) don't break. The existing in-app breach notification in [alerts.py](../../../backend/app/notifications/alerts.py) `_check_sla_breaches` becomes the **in-app twin of the breach escalation** — one breach yields one escalation event across channels + in-app, **not two separate breach signals**. Reconcile so the scheduler's old `check_sla_breaches` and the new engine do not double-fire.

**MTTR Capture**
- **D-09:** On remediation, write a **remediation-event row** capturing the **tier-at-remediation** (final risk tier) + duration (`first_detected_at → remediated_at`). MTTR is a **queryable aggregate over those rows**, grouped by tier. Chosen tier-at-remediation (over tier-at-detection) so MTTR reflects the finding's final assessed risk. Durable history that Phase 42/43 consume directly. — **Reversibility:** one-way — new table via migration.

**Admin UI (UI hint: yes)**
- **D-10:** New **"SLA & Escalation" pane** in the existing `/settings` sidebar-of-categories (RBAC-gated to admin/owner). Exposes the **full policy**: per-tier SLA days + the approaching % threshold, channel config (webhook URLs / API keys + per-transition routing + tier floor). Follows the established `SettingsSidebarShell` + `SaveBar` + `useDirtyState` pattern from Phase 14.
- **D-11:** Live SLA state renders on the **finding row and drill panel**. Reuse/extend the existing `SlaPill` primitive (Phase 13, tickets) for the on-track/approaching/breached visual language rather than inventing a new component.

### Claude's Discretion
- Exact schema/column names, migration structure, and whether the escalation-event + remediation-event tables share infrastructure.
- Where in the scheduler loop the transition-detection + escalation-firing runs (currently SLA check runs every 60s tick — [scheduler.py:314](../../../backend/app/connectors/scheduler.py#L314)).
- Webhook payload shapes and per-channel formatting (following each vendor's incoming-webhook / Events API contract).
- The default approaching-% value (80% is illustrative).
- Retry/failure semantics for a channel POST that fails (audit + surface, don't block the transition record).

### Deferred Ideas (OUT OF SCOPE)
- **Richer channel routing UI / digests** — deferred to **Phase 40** (Proactive Alerting & Digests), which depends on this phase's SLA breach/approaching states.
- **OAuth-based channel apps** (full Slack/Teams apps vs incoming webhooks) — out of scope; webhook config is sufficient now.
- **Two-way remediation verification** (confirming a ticket actually closed the finding) — **Phase 37**.
- **MTTR trend/burndown visualization** — **Phase 42**; this phase only *captures* the MTTR-by-tier data.
- **Executive/compliance SLA reporting** — **Phase 43**.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SLA-01 | Risk-tier SLA policy (default critical 7d / high 30d / moderate 90d), tenant-configurable, computed off the v4.0 risk-exposure tier | `RISK_SCORE_TIER_*` constants (risk_score.py:59-61), `Tenant.sla_config` extension pattern (tenants/router.py:150-229, tenants/models.py:41), NotificationsPane as the settings-pane template, tier-boundary gap Open Question #1 |
| SLA-02 | Each open finding shows a live SLA state (on-track / approaching / breached) derived from that policy | Tier+elapsed-% state formula (Code Examples), `VulnerabilitySummary`/`VulnerabilityResponse` schema gap (Pitfall 3), SlaPill extension path (D-11), scheduler-tick compute pass |
| SLA-03 | Approaching/breach transitions auto-escalate to a configured channel (Slack / Microsoft Teams / email / PagerDuty), fired exactly once per transition, audited | Escalation channel contracts (Slack/Teams/PagerDuty/SMTP), escalation-event table + once-only gating pattern, D-08 double-fire reconciliation (Pitfall 1), `audit()`/`create_notification()` reuse |
| SLA-04 | MTTR is captured per risk tier and exposed for reporting (feeds RPT/TREND) | remediation-event table schema, tier-at-remediation freeze behavior (Pitfall 13 discussion), the 6 scattered `REMEDIATED` write sites (Pitfall 6), MTTR-by-tier aggregate query shape |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Fonts/colors:** No font substitution (Inter + JetBrains Mono locked); no freehand hex — use CSS variables from `sketch-findings-getvul/references/foundation.md`. Applies to the new "SLA & Escalation" pane and any SlaPill extension.
- **State patterns mandatory:** The new settings pane and any new finding-row/drill-panel SLA UI must ship loading/empty/error states per `sketch-findings-getvul/references/state-patterns.md` — this was called out as "the v1 audit's top pain point."
- **No Tailwind admin-template patterns.** Follow `page-layouts.md` / `app-shell.md` conventions already used by `NotificationsPane`/`SettingsSidebarShell`.
- **Copy voice:** No generic SaaS copy. Use `copy-voice.md` — e.g. `SaveBar`'s existing "Save changes" / "Discard" / "Saving…" strings, not "Submit"/"OK".
- **Stack:** Backend FastAPI + Postgres + Redis; deployment is single-VM Docker Compose + in-process asyncio scheduler (no Celery/Arq/new infra) — reconfirmed as a v5.0-wide hard constraint in STATE.md. This phase must not introduce a second scheduler or an external queue for escalation delivery.
- **Auditability (v5.0-wide):** "every new mutating action... emits a tenant-scoped audit event" — applies directly to SLA policy changes and every escalation fire (D-07 already locks this in).
- **v4.0 risk score is authoritative** — this phase consumes `risk_exposure_score`, never re-derives it (STATE.md foundational principle, matches D-01).

## Summary

This phase replaces `app/vulnerabilities/sla_service.py`'s flat severity-keyed engine with a risk-tier-keyed one, while explicitly keeping the old engine's `get_sla_days`/severity mapping alive as the D-03 NULL-score fallback. The new engine slots into the *existing* 60-second scheduler tick ([scheduler.py:314-328](../../../backend/app/connectors/scheduler.py#L314-L328)) that already runs `backfill_sla_due_dates` + `check_sla_breaches` every loop — this phase's transition-detection and escalation-firing logic replaces or wraps that block, not a new scheduler registration. The tier boundaries to reuse already exist and are centralized at [risk_score.py:59-61](../../../backend/app/assets/risk_score.py#L59-L61) (`RISK_SCORE_TIER_CRITICAL=80/HIGH=50/MEDIUM=20`) — imported today only for `Asset.risk_score` bucketing in `export.py`/`dashboard.py`/`assets/router.py`; this phase is the first to apply them to `Vulnerability.risk_exposure_score`.

Two integration debts surfaced during research that materially affect task scope. First, **`VulnerabilitySummary` (list schema) and `VulnerabilityResponse` (detail schema) currently carry no SLA fields at all** — `sla_due_at` is used only for *sorting* in `list_vulnerabilities` ([service.py:143-165](../../../backend/app/vulnerabilities/service.py)), never returned in the response body, despite the frontend's `VulnerabilitySummary` type and `vuln-table.tsx`'s local `slaBand()` function assuming it exists. The finding-row SLA column is very likely rendering `—` in production today. D-11 cannot be satisfied without first adding SLA fields to both schemas. Second, **six separate call sites** across three files (`vulnerabilities/service.py`, `ticketing/service.py`, `ticketing/daily_sync.py`) independently set `vuln.status = "REMEDIATED"` / `vuln.remediated_at = now`, with no shared helper — D-09's remediation-event write needs either a new centralizing helper or six coordinated edits, and missing one silently drops MTTR data for that path.

On escalation channels, three of the four contracts are stable and low-risk (Slack incoming webhooks, PagerDuty Events API v2, and the already-fully-built `app/email.py::send_email`). The fourth, **Microsoft Teams, is a genuine trap for stale training knowledge**: the classic Office 365 Connector "Incoming Webhook" (the MessageCard-based mechanism most documentation and most LLM training data describes) is being retired — new connectors can no longer even be created, per a live-fetched Microsoft Learn page dated 2026-08-03. The current mechanism is the Teams **Workflows** app (Power Automate-backed), configured via a "Send webhook alerts to a channel" template, producing a `webhook.office.com` URL that still accepts a simple JSON POST. This changes the admin-facing setup instructions this phase must document, though the wire-level "paste a webhook URL, POST JSON" UX pattern GetVul already uses for Slack transfers over unchanged.

**Primary recommendation:** Extend the existing scheduler-tick SLA block in place (don't add a new scheduler), read tier boundaries from `app.assets.risk_score` rather than redefining them, add the missing SLA fields to both vulnerability Pydantic schemas as a first sub-task, introduce one centralizing "mark remediated" helper before touching six call sites, and build all four channels as bare `httpx.AsyncClient` JSON POSTs (no vendor SDKs) gated by a DB-backed once-only check mirroring `alerts.py`'s existing `_notification_exists` dedup pattern.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| SLA tier policy storage (days / approaching-% / tier floor / channel routing) | Database/Storage (`Tenant.sla_config` JSONB) | API/Backend (Pydantic validation, RBAC) | Extends the existing per-tenant JSONB config precedent (`smtp_config`/`syslog_config`) — no new storage mechanism |
| SLA state computation (on-track / approaching / breached) | API/Backend (scheduler tick) | Database/Storage (reads `risk_exposure_score`, writes `sla_due_at`/`sla_breached` mirror) | Must be server-computed — needs tenant policy + tier boundaries, unlike the ticket `SlaPill`'s pure client-side `dueAt` math |
| Transition detection + exactly-once gating | API/Backend (scheduler tick decision logic) | Database/Storage (new escalation-event table as the durable gate) | Decision runs server-side each tick; the gate itself is a DB row so it survives process restarts |
| Escalation delivery (Slack / Teams / PagerDuty / Email) | API/Backend (outbound HTTP/SMTP from the scheduler tick) | — | No client involvement — server-to-third-party fan-out only |
| Escalation audit trail | Database/Storage (`audit_logs` + new escalation-event table) | API/Backend (`audit()` call site) | Compliance requirement, fail-closed by existing project-wide convention |
| MTTR capture | API/Backend (write hook at the `REMEDIATED` transition) | Database/Storage (new remediation-event table) | Durable per-tier history; six existing write sites need a single hook point |
| MTTR query/aggregate | API/Backend (new aggregate query/endpoint) | Database/Storage (`GROUP BY` tier) | This phase only needs the capability queryable — Phase 42/43 build the reporting UI |
| "SLA & Escalation" admin pane | Frontend/Client (React settings pane) | API/Backend (extend `GET`/`PATCH /tenants/settings`) | Mirrors the Phase 14 `NotificationsPane` pattern exactly |
| Live SLA state display (finding row + drill panel) | Frontend/Client (`SlaPill` extension) | API/Backend (new `sla_state` field on both vulnerability schemas) | Must render server-computed state, never re-derive the tier formula client-side |

## Standard Stack

**Key finding: this phase requires zero new pip/npm dependencies.** `[VERIFIED]` — every capability it needs is already vendored.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | 0.28.1 installed (`>=0.27` pinned, `backend/pyproject.toml`) | Async outbound POST to Slack/Teams/PagerDuty webhooks | Already the sole HTTP client used everywhere else in `app/connectors/` (`tester.py`, `jamf.py`, `enrich_assets.py`) — `[VERIFIED]` via `pip show httpx` |
| smtplib (stdlib) | Python 3.12 stdlib | Email escalation channel | Already fully wrapped by `app/email.py::send_email` — TLS/STARTTLS/attachments all handled; zero new code needed for the email channel itself |
| SQLAlchemy 2.0 async + Alembic | already pinned | New `escalation_events` / `remediation_events` tables | Existing convention — 45 prior migrations, most recently `045_add_seen_by_sources_gin.py` |
| FastAPI + Pydantic v2 | already pinned | Extend `/tenants/settings`, `/vulnerabilities` schemas | No new endpoint infra; extends `tenants/router.py` and `vulnerabilities/router.py` in place |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tenacity | 9.x — **currently only a transitive dependency** (pulled in by `deepeval`, not imported anywhere in `app/`) `[VERIFIED]` via `grep -rn "import tenacity" backend/app/` (zero hits) | Retry/backoff for a failed channel POST | Optional promotion to a direct dependency — see Don't Hand-Roll and Open Question #6 |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Raw `httpx` POST to vendor webhooks (recommended) | `slack-sdk`, `pdpyras` (PagerDuty), MS Graph SDK | D-04 explicitly scopes to webhook/API-key config, no OAuth apps — all three vendor contracts are simple enough that a raw JSON POST is fully sufficient; three SDKs for three one-shot webhook calls is unjustified dependency weight |
| Ad-hoc retry in the new escalation-dispatch code | `tenacity` (promote to direct dep) | The existing codebase's own retry pattern (`okta_sync.py::_request_with_retry`, `[VERIFIED]`) is a hand-rolled per-connector helper, not centralized — `tenacity` would be the *first* centralized retry utility in this codebase, a genuine improvement but a new direct dependency to declare |

**Installation:**
```bash
# No installation needed for httpx/smtplib/SQLAlchemy/FastAPI (already present).
# Only if promoting tenacity to a direct dependency (Open Question #6):
# add "tenacity>=9.0" to the [project.dependencies] list in backend/pyproject.toml
# (it is currently present only inside the resolved lockfile via deepeval).
```

**Version verification:** `[VERIFIED]`
```bash
cd backend && pip show httpx     # → 0.28.1, satisfies >=0.27
grep -n "httpx\|tenacity" pyproject.toml   # httpx>=0.27 (direct); tenacity absent from [project.dependencies]
```

## Architecture Patterns

### System Architecture Diagram

```
                         ┌───────────────────────────────────────────┐
                         │   Scheduler tick (asyncio, every 60s)      │
                         │   app/connectors/scheduler.py:314-328      │
                         └───────────────────┬─────────────────────────┘
                                             │  for each active Tenant
                                             ▼
                  ┌──────────────────────────────────────────────────┐
                  │  SLA Tier Engine pass (NEW, this phase)          │
                  │  1. Read tenant.sla_config (tier days,           │
                  │     approaching %, tier floor, channel routing)  │
                  │  2. For each OPEN/IN_PROGRESS Vulnerability:     │
                  │     score = risk_exposure_score (raw, always)    │
                  │       score present → tier via RISK_SCORE_TIER_* │
                  │       score NULL    → severity fallback (D-03)   │
                  │     compute sla_due_at, state (on_track /        │
                  │     approaching / breached) via % elapsed        │
                  │  3. Write sla_due_at + sla_breached (mirror)     │
                  │  4. Call recompute_ticket_sla-equivalent for     │
                  │     every affected external_ticket_url           │
                  └───────────────────┬──────────────────────────────┘
                                      │ transition detected?
                                      ▼
                  ┌──────────────────────────────────────────────────┐
                  │  Transition + Escalation Gate (NEW)              │
                  │  - to_state in {approaching, breached}?          │
                  │  - tier >= tenant's configured tier floor?       │
                  │  - row exists in escalation_events for           │
                  │    (finding, to_state, channel)? → skip (once-   │
                  │    only, D-07)                                   │
                  └───────────────────┬──────────────────────────────┘
                                      │ fan out to configured channels
              ┌───────────┬───────────┼───────────┬─────────────────┐
              ▼           ▼           ▼           ▼                 ▼
         ┌────────┐  ┌─────────┐ ┌──────────┐ ┌────────┐    ┌───────────────┐
         │ Slack  │  │  Teams   │ │PagerDuty │ │ Email  │    │ In-app twin   │
         │webhook │  │ Workflows│ │Events v2 │ │(SMTP,  │    │(create_       │
         │(httpx) │  │ webhook  │ │(httpx)   │ │email.py)│   │ notification) │
         └───┬────┘  └────┬─────┘ └────┬─────┘ └───┬────┘    └──────┬────────┘
             │             │            │            │               │
             └─────────────┴────────────┴────────────┴───────────────┘
                                      │  every fire, success or failure
                                      ▼
                  ┌──────────────────────────────────────────────────┐
                  │  escalation_events row (fired_at, channel,       │
                  │  from_state, to_state) + audit() (fail-closed,   │
                  │  audit.py:143)                                   │
                  └────────────────────────────────────────────────────┘

   ── Separately, at any REMEDIATED transition (6 existing write sites) ──
   vulnerabilities/service.py, ticketing/service.py, ticketing/daily_sync.py
                                      │
                                      ▼
                  ┌──────────────────────────────────────────────────┐
                  │  remediation_events row (NEW): tier-at-          │
                  │  remediation (frozen risk_exposure_score /       │
                  │  severity fallback) + duration                   │
                  │  (first_detected_at → remediated_at)             │
                  └──────────────────────────────────────────────────┘
                                      │
                                      ▼
                    MTTR-by-tier aggregate query (GROUP BY tier)
                    → feeds Phase 42/43 later; queryable now (SLA-04)
```

### Recommended Project Structure
```
backend/app/vulnerabilities/
├── sla_service.py          # KEEP AS-IS — severity-keyed engine, now the D-03 fallback path
├── sla_tier_service.py     # NEW — tier boundaries + state formula + escalation dispatch (suggested name)
├── models.py                # Vulnerability model unchanged; sla_due_at/sla_breached already exist
├── schemas.py               # EXTEND — VulnerabilitySummary + VulnerabilityResponse gain sla_state (+ sla_due_at on Response)
└── router.py                 # EXTEND — settings-adjacent SLA endpoints if any new read surface is needed

backend/app/notifications/
├── alerts.py                 # RECONCILE _check_sla_breaches — becomes a no-op or is fully superseded (D-08)
└── escalation_channels.py    # NEW (suggested) — Slack/Teams/PagerDuty payload builders + httpx senders

backend/alembic/versions/
├── 046_add_sla_escalation_events.py     # NEW
└── 047_add_remediation_events.py        # NEW (or combined into one migration — Claude's Discretion)

frontend/src/components/settings/
├── sla-escalation-pane.tsx   # NEW — mirrors notifications-pane.tsx structure
└── microcopy.ts               # EXTEND — Category union gains 'sla', CATEGORY_LABELS gains an entry

frontend/src/components/tickets/  (or promote sla-pill.tsx to a shared location — Claude's Discretion)
└── sla-pill.tsx               # EXTEND — accept an optional server-computed `state` prop
```

### Pattern 1: Scheduler-tick block isolation
**What:** Every existing task inside `_scheduler_loop()` (`scheduler.py`) opens its own `async with async_session_factory() as db:` block and wraps itself in its own `try/except Exception as e: logger.error(...)` — a failure in one task (e.g. ticket rules) never blocks or crashes another (e.g. SLA check).
**When to use:** The new transition-detection + escalation-firing logic must follow this exact isolation shape so a bug in Tenant A's channel POST, or PagerDuty being down, cannot stall SLA processing for Tenant B or block unrelated scheduler tasks in the same tick.
**Example:**
```python
# Source: backend/app/connectors/scheduler.py:314-328 (existing pattern to extend)
try:
    async with async_session_factory() as db:
        tenants = (await db.execute(_sel(TenantModel).where(TenantModel.is_active.is_(True)))).scalars().all()
        for t in tenants:
            await backfill_sla_due_dates(db, t.id)
            await check_sla_breaches(db, t.id)
        await db.commit()
except Exception as e:
    logger.error("sla_check_error", error=str(e))
```

### Pattern 2: Check-before-insert dedup (the model for "exactly once")
**What:** `alerts.py::_notification_exists` already implements the exact query shape D-07 needs: check for an existing row matching a dedup key before creating a new one.
**When to use:** Directly transferable to the escalation-event once-only gate — same shape, different table/columns.
**Example:**
```python
# Source: backend/app/notifications/alerts.py:276-296 (existing precedent)
async def _notification_exists(db, tenant_id, category, resource_type, resource_id, *, hours):
    cutoff = datetime.now(UTC) - timedelta(hours=hours)
    result = await db.execute(
        select(func.count(Notification.id)).where(
            Notification.tenant_id == tenant_id,
            Notification.category == category,
            Notification.resource_type == resource_type,
            Notification.resource_id == resource_id,
            Notification.created_at >= cutoff,
        )
    )
    return result.scalar_one() > 0

# NEW equivalent for escalation events — no time window needed (D-07 is
# "ever fired for this exact transition+channel", not a lookback window):
async def _escalation_already_fired(db, tenant_id, vuln_id, to_state, channel) -> bool:
    result = await db.execute(
        select(func.count(SlaEscalationEvent.id)).where(
            SlaEscalationEvent.tenant_id == tenant_id,
            SlaEscalationEvent.vulnerability_id == vuln_id,
            SlaEscalationEvent.to_state == to_state,
            SlaEscalationEvent.channel == channel,
        )
    )
    return result.scalar_one() > 0
```
Recommend backing this with a `UniqueConstraint(tenant_id, vulnerability_id, to_state, channel)` as a defense-in-depth backstop (mirrors `RiskExposureBackfillJob.uq_risk_backfill_job_tenant` using a unique constraint as both identity key and correctness guard) — even though this project's single-VM/single-process scheduler (no multi-replica scheduler, confirmed via STATE.md's v5.0 hard constraints) means there is no real concurrent-writer race today.

### Pattern 3: Ticket-materialized SLA must be explicitly re-synced
**What:** `Ticket.sla_due_at` is a **stored, copied** column (not a live join) — `[VERIFIED]` at [ticketing/models.py:103](../../../backend/app/ticketing/models.py#L103). It only stays correct because `recompute_ticket_sla()` ([ticketing/service.py:72-115](../../../backend/app/ticketing/service.py#L72-L115)) is explicitly called after any bulk change to `Vulnerability.sla_due_at` — today, only from the admin `POST /vulnerabilities/sla/recalculate` endpoint ([vulnerabilities/router.py:226-263](../../../backend/app/vulnerabilities/router.py#L226-L263)).
**When to use:** The new scheduler-tick tier engine, which will change `sla_due_at` far more often (every tick, not just on-demand), MUST call the same `recompute_ticket_sla` for every affected `external_ticket_url` — otherwise ticket-side `SlaPill` displays silently go stale, repeating the exact WR-02 defect this endpoint was built to fix, but for a new code path.
**Example:**
```python
# Source: backend/app/vulnerabilities/router.py:237-257 (existing admin-endpoint precedent)
await db.flush()  # new vuln.sla_due_at values must be visible to the MIN aggregate
ticket_urls = (await db.execute(
    _select(distinct(Ticket.external_ticket_url)).where(Ticket.tenant_id == user.tenant_id)
)).scalars().all()
for ticket_url in ticket_urls:
    await recompute_ticket_sla(db, ticket_url, user.tenant_id)
```

### Pattern 4: Tenant JSONB config, mask-on-read + touched-flag-on-write for secrets
**What:** `smtp_config.password` is never returned in plaintext (`_safe_smtp()` masks it, [tenants/router.py:140-147](../../../backend/app/tenants/router.py#L140-L147)); the frontend seeds the password field empty and only sends it back if the user actually edited it (`passwordTouched`, [notifications-pane.tsx:44-58](../../../frontend/src/components/settings/notifications-pane.tsx#L44-L58)).
**When to use:** The new PagerDuty routing key and Slack/Teams webhook URLs are bearer-secret-equivalent (anyone holding the URL/key can post to the channel or page someone) — mask and touched-track them exactly like the SMTP password, not like a plain config string.

### Anti-Patterns to Avoid
- **Re-deriving tier boundaries in the new module:** `RISK_SCORE_TIER_CRITICAL/HIGH/MEDIUM` already exist at `app.assets.risk_score` specifically to prevent triplication (its own code comment cites three prior duplicate sites this constant centralization fixed). Import them; do not hardcode `80`/`50`/`20` again.
- **Letting the old `alerts.py::_check_sla_breaches` keep running unmodified:** it fires an in-app `"sla_breach"` notification on a flat 24h lookahead, independent of tier — if left running alongside the new engine, a breach produces two unrelated in-app notifications, violating D-08's explicit "one breach = one escalation event... never two separate breach signals."
- **Computing SLA state client-side for findings:** unlike ticket `SlaPill` (pure `dueAt` math, no server "state"), the new tier engine's `approaching` calculation depends on tenant policy (tier days + approaching %) that the client should not need to fetch and re-implement. Compute server-side, ship the resulting `sla_state` string.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SMTP delivery | A new email client/library | `app/email.py::send_email(smtp_config, to, subject, body, ...)` (existing, fully built) | Already handles TLS/STARTTLS/attachments — zero reason to duplicate for the email escalation channel |
| Outbound webhook retry/backoff | A bespoke `for attempt in range(3): sleep(...)` loop | `tenacity` (promote from transitive to direct dep) or, if avoiding a new direct dependency, mirror `okta_sync.py::_request_with_retry`'s existing shape | Retry-with-backoff-and-jitter is a "deceptively complex" problem (which exceptions are retryable, max attempts, backoff curve) that a hand-rolled loop reliably gets subtly wrong |
| Risk tier boundaries | New magic numbers `80`/`50`/`20` in the SLA module | `from app.assets.risk_score import RISK_SCORE_TIER_CRITICAL, RISK_SCORE_TIER_HIGH, RISK_SCORE_TIER_MEDIUM` | Already centralized there for exactly this reason — `export.py`, `dashboard.py`, `assets/router.py` all import from this one location today |
| Frontend admin-role gating | New role-check logic in the new pane | `useAuth()` + the `isAdmin = role === 'OWNER' \|\| role === 'ADMIN'` pattern already in `SettingsSidebarShell` | Established, matches backend RBAC precedent |
| Settings dirty-state tracking | A new form-state hook | `useDirtyState` (`frontend/src/components/settings/use-dirty-state.ts`) | Purpose-built for exactly this multi-section-pane-with-one-SaveBar pattern |
| Audit logging | A new audit table/schema | `audit()` (`app/audit.py:143`) | Fail-closed (raises → aborts the whole request/transaction), syslog-forwarding — the sole compliance mechanism in this codebase |
| In-app notification delivery | A new notification model | `create_notification()` (`app/notifications/service.py:19`) | Already supports broadcast (`user_id=None`) + optional email fan-out |
| Secret-masking UX | A new "reveal/hide" secret input component | Mirror `NotificationsPane`'s SMTP-password `touched`-flag + `••••••••` mask (Pattern 4 above) | Proven, shipped pattern directly transferable to the new channel secrets |
| Vendor integration SDKs | `slack-sdk`, `pdpyras`, MS Graph SDK | Raw `httpx.AsyncClient` POST of vendor JSON | D-04 explicitly scopes to webhook/API-key only (no OAuth apps) — all three contracts are simple enough for a bare POST |

**Key insight:** Nearly every piece of infrastructure this phase needs (audit, in-app notifications, tenant JSONB config, secret masking, HTTP client, tier constants) was already built for a different phase and is directly reusable. The genuinely new code is: the tier+elapsed-% state formula, the escalation-event/remediation-event tables, the channel payload builders, and the settings pane markup.

## Common Pitfalls

### Pitfall 1: Double-fire from un-reconciled legacy breach paths (D-08)
**What goes wrong:** The scheduler already runs `check_sla_breaches` (sla_service.py, sets `sla_breached=True` on any past-due OPEN/IN_PROGRESS vuln) every 60s tick, AND separately `alerts.py::_check_sla_breaches` runs every 5 minutes and creates an in-app `"sla_breach"` notification for anything due within 24h. If the new engine is simply added alongside these without modification, a single breach produces: the old in-app notification, PLUS the new engine's breach escalation (channels + its own in-app twin) — exactly the "two separate breach signals" D-08 forbids.
**Why it happens:** `check_sla_breaches` and `_check_sla_breaches` are both flat/severity-agnostic and were never designed with a tier engine in mind; nothing currently gates them off.
**How to avoid:** Either retire `alerts.py::_check_sla_breaches` entirely (replaced by the new engine's own in-app twin) or gate it to be a genuine no-op once the new engine covers a tenant. Decide explicitly which of `check_sla_breaches`'s writes to `sla_breached` the new engine supersedes vs. still relies on as the "derived mirror" (D-08).
**Warning signs:** Two notifications with different `category` values (`sla_breach` vs. whatever the new engine uses) referencing the same `resource_id` within seconds of each other in tests.

### Pitfall 2: Ticket-materialized `sla_due_at` goes stale (repeats the WR-02 defect for a new cause)
**What goes wrong:** `Ticket.sla_due_at` is a stored copy, not a live join (`[VERIFIED]`, ticketing/models.py:103). It is only kept in sync because `recompute_ticket_sla()` is explicitly called after `Vulnerability.sla_due_at` changes — today only from the admin `/sla/recalculate` endpoint. The new tier engine will change `sla_due_at` on every 60s tick; if it doesn't also call `recompute_ticket_sla`-equivalent, ticket-side `SlaPill` displays go stale continuously, not just occasionally.
**Why it happens:** The recompute call is a manually-wired side effect at one call site, not an automatic trigger/hook on the column.
**How to avoid:** The new engine's tick pass must call `recompute_ticket_sla` for every affected `external_ticket_url` (or, since this runs every 60s and could be expensive tenant-wide, consider tracking only ticket groups whose linked-vuln `sla_due_at` actually changed this tick — see Open Question #5).
**Warning signs:** A ticket's SLA pill and its linked finding's SLA pill disagree in a live-stack manual check.

### Pitfall 3: `VulnerabilitySummary`/`VulnerabilityResponse` don't carry SLA fields today
**What goes wrong:** `[VERIFIED]` — `VulnerabilitySummary` (list schema, [schemas.py:74-98](../../../backend/app/vulnerabilities/schemas.py#L74-L98)) has no `sla_due_at` field; `sla_due_at` is used only for the `sort=sla_due_at` query parameter ([service.py:143-165](../../../backend/app/vulnerabilities/service.py)), never returned. `VulnerabilityResponse` (detail schema, [schemas.py:27-71](../../../backend/app/vulnerabilities/schemas.py#L27-L71)) also has no `sla_due_at`/`sla_breached` field. FastAPI's `response_model` validation drops any attribute not declared on the Pydantic model, regardless of what the underlying ORM row has. Meanwhile `vuln-table.tsx`'s local `slaBand(row.sla_due_at)` function and the frontend `VulnerabilitySummary` TypeScript type both assume the field is present.
**Why it happens:** The SLA column was probably added to the frontend ahead of a backend field that was never wired through, or the field was removed from the schema at some point without updating the consumers.
**How to avoid:** Treat "add `sla_due_at` + the new `sla_state` to both Pydantic schemas" as a first, foundational sub-task — D-11 (finding row + drill panel SLA state) is blocked on this, not just enhanced by it.
**Warning signs:** A quick manual check of `GET /api/v1/vulnerabilities` response JSON today will show no `sla_due_at` key.

### Pitfall 4: Tier-boundary gap below the MEDIUM floor (score < 20)
**What goes wrong:** `RISK_SCORE_TIER_MEDIUM = 20` is the *lower* bound of the "medium/moderate" band. The roadmap's default policy only names three tiers with day-budgets: critical (7d) / high (30d) / moderate (90d). Nothing in CONTEXT.md or the roadmap specifies what SLA (if any) applies to a finding scoring below 20 — `risk_score.py`'s own docstring calls this "0-19 = low risk" but defines no `RISK_SCORE_TIER_LOW` constant and no day-budget for it.
**Why it happens:** The 3-tier framing (critical/high/moderate) in the roadmap/CONTEXT doesn't map 1:1 onto the 4-band structure the tier constants actually define.
**How to avoid:** Surface this explicitly during planning (see Open Question #1) rather than silently picking a default. Candidate resolutions: no SLA tracking below 20 (state is always `on_track`, no due date), or a 4th configurable "low" tier extending the same day-budget pattern.
**Warning signs:** Ambiguity will show up as a test that can't decide what `sla_due_at`/`sla_state` should be for a `risk_exposure_score=5` finding.

### Pitfall 5: NULL-score severity fallback needs an explicit severity→tier mapping
**What goes wrong:** D-03's fallback uses the OLD 5-value severity scale (CRITICAL/HIGH/MEDIUM/LOW/INFO), but the new engine's tier floor (D-06) and per-transition channel routing (D-05) are keyed by the new 3-4-value tier vocabulary. Without an explicit mapping, a fallback finding's severity can't be checked against the tier floor consistently with a scored finding's tier.
**Why it happens:** Two different vocabularies (severity vs. tier) governing the same gate (tier floor) with no declared translation between them.
**How to avoid:** Define (and test) an explicit severity→tier map for fallback findings — the natural one is CRITICAL→critical, HIGH→high, MEDIUM/LOW/INFO→moderate (or apply the same Pitfall 4 resolution to LOW/INFO).
**Warning signs:** A fallback CRITICAL-severity finding silently never escalates because the tier-floor check compares a severity string against a tier string and always fails the comparison.

### Pitfall 6: Six scattered `REMEDIATED` write sites, no centralized hook
**What goes wrong:** `[VERIFIED]` via `grep -rn "REMEDIATED" backend/app/`, these six sites independently set `vuln.status = "REMEDIATED"` + `vuln.remediated_at = now`, each with a slightly different existing guard condition:
- `vulnerabilities/service.py:332` (`update_vulnerability_status`, guard: `new_status == "REMEDIATED"`)
- `vulnerabilities/service.py:349` (`bulk_update_status`, guard: `body.status == "REMEDIATED"`)
- `ticketing/service.py:1177-1179` (guard: `vuln.status != "REMEDIATED"`)
- `ticketing/service.py:1326-1327` (guard: `vuln.status not in ("REMEDIATED", "SUPPRESSED")`)
- `ticketing/daily_sync.py:243-245`, `:327-328`, `:417-418` (three near-identical blocks across different ticket-provider sync functions, guard: `not in ("REMEDIATED", "SUPPRESSED")`)

D-09's remediation-event write must fire at every one of these or MTTR data silently drops for whichever path is missed.
**Why it happens:** Status transitions accreted across multiple ticketing-sync features (Asana/generic daily sync, ticket-completion webhooks) without ever being centralized.
**How to avoid:** Introduce one shared helper (e.g. `mark_vulnerability_remediated(db, vuln)` that sets status+timestamp AND writes the remediation-event row) and route all six call sites through it, rather than duplicating the remediation-event-write logic six times.
**Warning signs:** MTTR-by-tier numbers that look complete for directly-closed vulns but are missing entries for ticket-auto-closed ones (or vice versa) — a sign one call site was missed.

### Pitfall 7: Microsoft Teams' classic incoming-webhook mechanism is being retired
**What goes wrong:** Training data (and most existing documentation/tutorials) describes Teams incoming webhooks as an Office 365 "Connector" producing an `outlook.office.com/webhook/...` URL that accepts a legacy `MessageCard` JSON payload. `[CITED]` — a live fetch of the official Microsoft Learn page (dated 2026-08-03, i.e. 10 days before this research) confirms: "Microsoft 365 Connectors... are nearing deprecation, and the creation of new Microsoft 365 Connectors will soon be blocked." New connectors can no longer be created; existing ones are being phased out.
**Why it happens:** This is a genuinely recent platform change (WebSearch corroborates a retirement timeline running through Dec 2025 → migration deadline extended to March 31 2026 — already past as of this phase's 2026-08-13 date), exactly the kind of thing stale training knowledge gets wrong.
**How to avoid:** Target the current mechanism instead: the Teams **Workflows** app (Power Automate-backed). A tenant admin creates a webhook via **channel → More options → Workflows → "Send webhook alerts to a channel"** template, which produces a `webhook.office.com`-hosted URL. This URL still accepts a simple `POST {"text": "..."}` JSON body (confirmed in the official example), and per the same page, "Workflows support both Adaptive Cards and Message Card format" for richer payloads — so classic MessageCard-shaped JSON still renders through a Workflow, just not through a *new* classic Connector. Rate limit: 4 requests/second per webhook (429 on excess); message size limit 28 KB.
**Warning signs:** None locally — this only surfaces when a real tenant admin tries to set up the integration and can't find "Connectors" in their Teams UI, or an existing customer's classic webhook silently stops working on Microsoft's retirement date.

### Pitfall 8: PagerDuty `dedup_key` — "exactly once" for escalation ≠ auto-resolved incidents
**What goes wrong:** `[CITED]` (WebSearch, developer.pagerduty.com) — sending a `trigger` event with a stable `dedup_key` and letting the local escalation-event table gate re-sends satisfies GetVul's own "exactly once per transition" requirement. But PagerDuty's own semantics say: "once the alert is resolved, any further events with the same dedup_key... create a new alert" — meaning if GetVul never sends an `event_action="resolve"` when a finding is fixed or un-breaches, the PagerDuty incident stays open forever, even after the underlying issue is gone.
**Why it happens:** D-07/D-08 only specify *firing* semantics (approaching/breach transitions), not an unwind/resolve path.
**How to avoid:** Decide explicitly (Open Question #3) whether to send a `resolve` event with the same `dedup_key` when a finding transitions back to on-track or gets remediated. If out of scope for this phase, document that PagerDuty incidents from this integration require manual resolution.
**Warning signs:** A PagerDuty account accumulating permanently-open incidents for long-since-fixed findings.

### Pitfall 9: Secrets in `Tenant.sla_config`/`smtp_config` are plaintext at rest today (existing precedent)
**What goes wrong:** `[VERIFIED]` — `app/tenants/router.py`'s settings PATCH assigns `tenant.smtp_config = new_smtp` directly with no call into `app/encryption.py::encrypt_value` (which exists and is used elsewhere, presumably for `ConnectorConfig.credentials`). The SMTP password is stored in plaintext JSONB today. By direct precedent, new PagerDuty routing keys and Slack/Teams webhook URLs added to `sla_config` will land in plaintext JSONB too unless the planner deliberately elevates security beyond the existing pattern.
**Why it happens:** Pre-existing architectural choice, not something this phase introduces — but this phase adds three more secret-shaped values to the same unencrypted column.
**How to avoid:** At minimum, apply the existing mask-on-read pattern (Pattern 4) so the values never round-trip back to the browser in plaintext. Whether to go further (Fernet-encrypt at rest, matching `ConnectorConfig.credentials`) is a real product/security decision — see Open Question #6; don't silently decide it either way.
**Warning signs:** None locally — this is a data-at-rest exposure, not a functional bug; a DB dump or backup would contain the secrets in cleartext.

### Pitfall 10: SSRF surface from tenant-admin-controlled outbound webhook URLs
**What goes wrong:** Slack/Teams webhook URLs and (less so) the PagerDuty routing key are values a tenant admin can set arbitrarily via the new settings pane. The scheduler will `httpx.AsyncClient.post()` to whatever URL is stored, from the GetVul server itself. A malicious or compromised tenant admin could point the "Slack webhook URL" field at an internal service (e.g., a cloud metadata endpoint, or another container on the same Docker network) and use GetVul's own backend as an SSRF pivot, potentially exfiltrating the JSON payload (which contains finding/CVE/host details) or probing internal infrastructure.
**Why it happens:** No existing validation constrains what a webhook URL can point to — this is a new capability, not present in the codebase's pre-existing SMTP-host or syslog-host config validation either (worth checking whether those have the same gap, though that's out of this phase's scope).
**How to avoid:** Validate the URL scheme is `https://` before every POST; consider disallowing literal private/loopback/link-local IP addresses and well-known metadata hostnames (`169.254.169.254`, `metadata.google.internal`, etc.) if resolvable at validation time; set `httpx.AsyncClient(follow_redirects=False)` (or validate the redirect target too) to prevent a redirect-based bypass of any hostname check.
**Warning signs:** None locally — this is a security-review-time finding, not something a functional test surfaces.

### Pitfall 11: Duplicate flat-MTTR implementations already exist — don't conflate with the new tier-grouped MTTR
**What goes wrong:** `[VERIFIED]` — a flat, tenant-wide MTTR (`AVG(remediated_at - first_detected_at)`, no tier grouping) is already computed independently in **two** near-identical places: `vulnerabilities/service.py:571-579` and `vulnerabilities/dashboard.py:212-228` (both feed the dashboard's `mttr_30d` tile), plus a weekly-bucketed version in `trends.py:129-159` (`get_mttr_trend`). None of these are tier-grouped.
**Why it happens:** Pre-existing, unrelated to this phase.
**How to avoid:** D-09's tier-grouped MTTR is a **new, additional** capability built on the new `remediation_events` table — it does not replace or need to touch these three existing flat/weekly queries. Don't scope a "consolidate MTTR queries" refactor into this phase; that's out of bounds relative to the four locked success criteria.
**Warning signs:** A task that tries to modify `dashboard.py`'s `mttr_30d` tile — that's the wrong file for this phase's MTTR requirement.

## Code Examples

### Tier + state computation (the core new formula, SLA-01/SLA-02)
```python
# Recommended shape — no direct source (this is new code), but tier boundaries
# are imported from the existing, centralized constants:
# Source: backend/app/assets/risk_score.py:59-61
from app.assets.risk_score import (
    RISK_SCORE_TIER_CRITICAL,  # 80
    RISK_SCORE_TIER_HIGH,      # 50
    RISK_SCORE_TIER_MEDIUM,    # 20
)

def tier_for_score(score: int | None) -> str | None:
    """None means Open Question #1 (score < 20) or D-03 fallback territory."""
    if score is None:
        return None
    if score >= RISK_SCORE_TIER_CRITICAL:
        return "critical"
    if score >= RISK_SCORE_TIER_HIGH:
        return "high"
    if score >= RISK_SCORE_TIER_MEDIUM:
        return "moderate"
    return None  # Open Question #1 — no named tier below MEDIUM today

def compute_sla_state(
    *, first_detected_at: datetime, tier_days: int, approaching_pct: float, now: datetime,
) -> tuple[datetime, str]:
    """D-02: approaching window scales per-tier automatically."""
    sla_due_at = first_detected_at + timedelta(days=tier_days)
    approaching_at = sla_due_at - timedelta(days=tier_days * (1 - approaching_pct))
    if now >= sla_due_at:
        return sla_due_at, "breached"
    if now >= approaching_at:
        return sla_due_at, "approaching"
    return sla_due_at, "on_track"
```

### Existing `audit()` convention (D-07 requires every escalation fire to go through this)
```python
# Source: backend/app/audit.py:143-171 (signature + fail-closed contract)
await audit(
    db, user_or_none, "sla.escalation_fire", "vulnerability", str(vuln_id),
    {"channel": "slack", "from_state": "on_track", "to_state": "breached"},
)
# NOTE: the scheduler tick has no CurrentUser — pass None (audit.py:174 handles
# user=None by writing tenant_id=uuid.UUID(int=0) unless a system-actor
# convention is established; check how other scheduler-originated audits
# solve this — STATE.md mentions a "system:scheduler" actor precedent
# elsewhere in this codebase (Phase 26) worth following for consistency).
```

### Existing `create_notification()` signature (the in-app twin, D-08)
```python
# Source: backend/app/notifications/service.py:19-33
await create_notification(
    db, tenant_id=tenant.id, title="SLA Breach: CVE-2026-XXXXX",
    message="CVE-2026-XXXXX on host03 — breached the critical tier SLA (7d)",
    severity="critical", category="sla_escalation",  # NEW category, distinct from legacy "sla_breach"
    resource_type="vulnerability", resource_id=cve_id_or_uuid,
    details={"tier": "critical", "to_state": "breached", "channels_notified": ["slack", "pagerduty"]},
)
```

### Escalation-event once-only gate + migration shape
```python
# Source pattern: backend/alembic/versions/044_add_risk_backfill_job.py (structure to mirror)
revision = "046_add_sla_escalation_events"
down_revision = "045_add_seen_by_sources_gin"

def upgrade() -> None:
    op.create_table(
        "sla_escalation_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vulnerability_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("vulnerabilities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_state", sa.String(20), nullable=False),
        sa.Column("to_state", sa.String(20), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("fired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivery_status", sa.String(20), nullable=False, server_default="sent"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "vulnerability_id", "to_state", "channel", name="uq_escalation_once"),
    )
    op.create_index("ix_sla_escalation_events_tenant_id", "sla_escalation_events", ["tenant_id"])
    op.create_index("ix_sla_escalation_events_vulnerability_id", "sla_escalation_events", ["vulnerability_id"])
```

### Channel payload shapes (D-04)

**Slack incoming webhook** — `[CITED]` docs.slack.dev, fetched live:
```python
# POST <slack-webhook-url>, Content-Type: application/json
{
    "text": "SLA breach: CVE-2026-XXXXX on host03 (critical tier, 7d)",  # required fallback
    "blocks": [
        {"type": "section", "text": {"type": "mrkdwn",
            "text": "*SLA breach* — `CVE-2026-XXXXX` on `host03`\ntier: *critical* (7d) — remediation overdue"}}
    ],
}
# Success: HTTP 200, body "ok" (plain text, not JSON).
# Failure: 400/403/404 with bodies like invalid_payload / invalid_token / no_text /
# channel_is_archived / no_service — a revoked/deleted webhook returns an error, not a silent no-op.
```

**Microsoft Teams (Workflows webhook — NOT the classic connector, see Pitfall 7)** — `[CITED]` learn.microsoft.com, fetched live (page dated 2026-08-03):
```python
# POST <teams-workflow-webhook-url>, Content-Type: application/json
# Simplest form (matches the official "Send webhook alerts to a channel" example):
{"text": "SLA breach: CVE-2026-XXXXX on host03 (critical tier, 7d)"}

# Richer form — Adaptive Card envelope (also supported through Workflows):
{
    "type": "message",
    "attachments": [{
        "contentType": "application/vnd.microsoft.card.adaptive",
        "content": {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard", "version": "1.2",
            "body": [{"type": "TextBlock", "text": "SLA breach — CVE-2026-XXXXX on host03"}],
        },
    }],
}
# Rate limit: 4 req/sec per webhook (429 beyond that). Message size limit: 28 KB.
```

**PagerDuty Events API v2** — `[CITED]` WebSearch cross-referenced (request fields), `[ASSUMED]` response body shape (see Assumptions Log A1):
```python
# POST https://events.pagerduty.com/v2/enqueue, Content-Type: application/json
{
    "routing_key": "<tenant's Events API v2 integration key>",
    "event_action": "trigger",  # or "acknowledge" / "resolve"
    "dedup_key": f"getvul:{vulnerability_id}:{to_state}",  # stable per finding+transition
    "payload": {
        "summary": "SLA breach: CVE-2026-XXXXX on host03 (critical tier, 7d)",
        "source": "getvul",
        "severity": "critical",  # enum: critical | error | warning | info — CITED
        "timestamp": "2026-08-13T12:00:00Z",
        "custom_details": {"cve_id": "CVE-2026-XXXXX", "tier": "critical", "asset": "host03"},
    },
    "client": "GetVul",
    "client_url": "https://<tenant-domain>/dashboard/vulnerabilities?cve=CVE-2026-XXXXX",
}
# dedup_key semantics (CITED): subsequent events with the same dedup_key apply to the
# SAME open alert; once resolved, a new trigger with the same key opens a NEW alert.
# See Pitfall 8 for the resolve-semantics gap this creates.
```

### MTTR-by-tier aggregate (SLA-04)
```python
# Pattern mirrors the EXISTING weekly-bucketed MTTR shape at trends.py:129-159,
# grouped by tier instead of by week, reading the NEW durable table instead of
# live-computing from Vulnerability rows (which would lose tier-at-remediation
# once compute_finding_risk_scores stops touching a REMEDIATED row).
mttr_by_tier_q = (
    select(
        RemediationEvent.tier_at_remediation,
        func.avg(RemediationEvent.duration_seconds).label("avg_seconds"),
        func.count().label("count"),
    )
    .where(RemediationEvent.tenant_id == tenant_id)
    .group_by(RemediationEvent.tier_at_remediation)
)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Severity-keyed SLA (5 bands, `sla_service.py`) | Risk-tier-keyed SLA (off `risk_exposure_score`) | This phase (36) | Severity path is retained *only* as the D-03 NULL-score fallback — `sla_service.py` is not deleted |
| MS Teams classic "Incoming Webhook" connector (MessageCard, `outlook.office.com/webhook/...`) | Teams "Workflows" app (Power Automate-backed), `webhook.office.com` URL via a channel template | New connectors already blocked per the live-fetched doc (dated 2026-08-03); migration deadline (March 31 2026) already passed relative to this phase's 2026-08-13 date | Admin setup instructions and any URL-shape validation in the new settings pane must target Workflows, not the deprecated classic connector |
| Flat tenant-wide MTTR (`service.py:571`, `dashboard.py:212` — live `AVG` over `Vulnerability` rows) | Durable per-tier MTTR from `remediation_events` rows (D-09) | This phase (36) | New, additive capability — coexists with the flat dashboard tile, does not replace it (Pitfall 11) |
| Ticket `SlaPill` — pure client-computed from `dueAt`, fixed 7-day "soon" band | Unchanged for tickets; but the Vulnerabilities finding-row/drill-panel use of `SlaPill` must consume a server-computed 3-state field | This phase (36), finding-row/drill-panel scope only (D-11) | Ticket screens are explicitly out of scope — do not touch `tickets-table.tsx`/`kanban-card.tsx`/`ticket-drill-content.tsx`'s existing `SlaPill` call sites |

**Deprecated/outdated:**
- Microsoft 365 (Office 365) Connectors in Teams: retired/blocked for new setups. Anyone following a tutorial that says "Teams → Connectors → Incoming Webhook" is following stale instructions as of this phase's date.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | PagerDuty Events API v2 success response is `202 Accepted` with a JSON body containing `status`/`message`/`dedup_key` | Code Examples — PagerDuty payload | LOW — only affects how the planner's task describes parsing the acknowledgment; the request-side fields (routing_key/event_action/dedup_key/severity enum) were WebSearch-verified independently and are not affected |
| A2 | PagerDuty's optional `images`/`links` array fields exist and follow the shape shown | Code Examples — PagerDuty payload | LOW — these are optional enrichment fields; omitting them entirely still produces a valid trigger event |
| A3 | `tenacity`, if promoted from transitive to direct dependency, integrates cleanly with this codebase's async httpx call sites | Standard Stack / Don't Hand-Roll | LOW-MEDIUM — should be smoke-tested once adopted; the library itself is exceptionally stable, but this codebase has zero existing direct usage to validate against |

**Note:** The Microsoft Teams webhook-retirement finding (Pitfall 7 / State of the Art) is **not** in this table — it was independently confirmed by a live fetch of an official, dated Microsoft Learn page during this session, so it is `[CITED]`, not `[ASSUMED]`.

## Open Questions

1. **What SLA (if any) applies to a finding scoring below the MEDIUM tier boundary (`risk_exposure_score < 20`)?**
   - What we know: The default policy names three tiers (critical 7d / high 30d / moderate 90d); `RISK_SCORE_TIER_MEDIUM=20` is the floor of "moderate."
   - What's unclear: Nothing in CONTEXT.md or the roadmap specifies behavior below 20 — no `RISK_SCORE_TIER_LOW` constant exists.
   - Recommendation: Resolve explicitly before writing tier-state tasks. Simplest options: (a) no SLA tracking below 20 (always `on_track`, no due date), or (b) add a 4th configurable "low" tier following the same day-budget shape. Flag to discuss-phase if not already implicitly decided.

2. **What severity→tier mapping applies to D-03 fallback findings for tier-floor and channel-routing purposes?**
   - What we know: The fallback uses the old 5-value severity scale; the tier floor/routing config uses the new tier vocabulary.
   - What's unclear: No explicit translation is defined.
   - Recommendation: CRITICAL→critical, HIGH→high, MEDIUM/LOW/INFO→moderate (or apply whatever Question 1 resolves to for LOW/INFO) — should be a small, explicit, tested lookup table.

3. **Should the PagerDuty channel send an `event_action=resolve` when a finding un-breaches or is remediated?**
   - What we know: D-07/D-08 only specify firing on approaching/breach transitions; PagerDuty's dedup_key semantics leave an incident open forever without an explicit resolve.
   - What's unclear: Whether auto-resolving PagerDuty incidents is in scope for this phase or deferred.
   - Recommendation: If out of scope, document the limitation explicitly (manual resolution required) rather than leaving it as a silent gap.

4. **Centralize the 6 `REMEDIATED` write sites behind one helper, or write the remediation-event row independently at each?**
   - What we know: No shared helper exists today (Pitfall 6); each site has a slightly different existing guard condition.
   - What's unclear: Whether a refactor-then-extend approach (introduce `mark_vulnerability_remediated()`, migrate 6 call sites) or a leave-in-place-and-duplicate approach is preferred, given the guard-condition inconsistencies already present.
   - Recommendation: Centralize — the guard-condition drift across the 6 sites is itself a latent bug risk, and D-09 is exactly the forcing function to fix it once.

5. **Recompute ticket SLA for every ticket group every 60s tick, or only affected groups?**
   - What we know: The existing admin endpoint recomputes ALL ticket groups for the tenant (`/sla/recalculate`), acceptable for an on-demand action.
   - What's unclear: Whether doing this every 60s tick for every tenant is acceptable cost, or whether the new engine should track which vulns' `sla_due_at` actually changed this tick and only recompute those groups.
   - Recommendation: Start with the simple "recompute all groups" approach (matches existing precedent, correctness-first); revisit for efficiency only if the scheduler tick duration becomes a measured problem.

6. **Should the new channel secrets (PagerDuty routing key, Slack/Teams webhook URLs) be Fernet-encrypted at rest, or follow the existing plaintext-JSONB precedent (`smtp_config.password`)?**
   - What we know: `app/encryption.py::encrypt_value`/`decrypt_value` exist and are used for `ConnectorConfig.credentials`, but NOT for `Tenant.smtp_config`/`sla_config` (Pitfall 9).
   - What's unclear: Whether this phase should elevate security beyond existing precedent or intentionally match it.
   - Recommendation: Flag to discuss-phase / the user explicitly rather than silently deciding — this is a security posture question bigger than this one phase (it also implicates the pre-existing SMTP password), but this phase is what introduces 2-3 more secret-shaped values to the same storage.

## Environment Availability

This phase's external dependencies are **remote, tenant-provided services** with per-tenant credentials — not locally installable tools, so the standard CLI-probe table doesn't directly apply. Framing accordingly:

| Dependency | Required By | Available (this dev env) | Notes | Fallback |
|------------|------------|---------------------------|-------|----------|
| httpx (async HTTP client) | Slack/Teams/PagerDuty POST | ✓ | 0.28.1 installed, `[VERIFIED]` | — |
| SMTP server | Email channel | ✗ (no local SMTP dev server / mailhog / maildev found in `docker-compose*.yml`, `[VERIFIED]`) | Existing `email.py`/`_send_notification_email` already ships without one — tests presumably mock `send_email` | Mock `send_email` at the module level in tests, as existing notification tests must already do |
| Slack workspace + incoming webhook URL | Slack channel | ✗ — no tenant credentials available in this environment | Per-tenant, remote, credential-gated | Tests must monkeypatch the outbound POST function, not hit a real Slack workspace |
| Microsoft Teams + Workflow webhook URL | Teams channel | ✗ — same as above | Per-tenant, remote, credential-gated; also requires the tenant to have already migrated off the classic connector (Pitfall 7) | Same — monkeypatch |
| PagerDuty account + Events API v2 integration key | PagerDuty channel | ✗ — same as above | Per-tenant, remote, credential-gated | Same — monkeypatch |
| HTTP mocking library (`respx` / `pytest-httpx`) | Testing the channel senders without real network | ✗ — not currently a dependency, `[VERIFIED]` via `grep backend/pyproject.toml` | Not required — this codebase's existing convention (`test_scheduler_enrichment_refresh.py`, `test_scheduler_ai_batch.py`) is to `monkeypatch.setattr` the local module function that performs the call, not mock the HTTP transport layer | Follow the existing monkeypatch-the-function convention; only add `respx` if the planner specifically wants transport-level assertions |

**Missing dependencies with no fallback:** None — every external service dependency has a viable test-time fallback (monkeypatch), and no new local tooling is required.

**Missing dependencies with fallback:** All four channels' live credentials (Slack/Teams/PagerDuty/SMTP-server) — tests exercise the payload-building and dispatch logic via monkeypatched senders; a live end-to-end proof against real tenant credentials is not possible in this environment (consistent with this project's existing precedent for SMTP/connector integrations, per project memory).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Backend framework | pytest 8.x, `asyncio_mode = "auto"` (`backend/pyproject.toml:74-82`) |
| Backend config file | `backend/pyproject.toml` `[tool.pytest.ini_options]` |
| Backend quick run | `cd backend && ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())") JWT_SECRET_KEY=test-secret pytest tests/test_sla_service.py -v` (per-file — project memory: whole-`tests/`-dir runs produce false failures) |
| Backend full suite | `cd backend && pytest -v --cov=app --cov-report=term-missing` (Makefile `test-local` target) |
| Frontend framework | Vitest (`frontend/vitest.config.mts`), Testing Library |
| Frontend quick run | `cd frontend && npx vitest run src/components/tickets/sla-pill.test.tsx` |
| Frontend full suite | `cd frontend && npm test` |
| E2E framework | Playwright, config at `frontend/e2e/playwright.config.ts`, run via `npm run test:e2e` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SLA-01 | Tier policy is tenant-configurable; RBAC (admin can view, owner can save) | integration | `pytest tests/test_tenant_sla_settings.py -x` | ❌ Wave 0 (new file; mirrors `tenants/router.py`'s existing `/settings` test coverage — check for an existing `test_tenants.py` to extend instead) |
| SLA-01 | Default policy values (critical 7d/high 30d/moderate 90d) applied when tenant has no custom config | unit | `pytest tests/test_sla_tier_service.py::test_default_policy -x` | ❌ Wave 0 |
| SLA-02 | Tier-state computation: on_track/approaching/breached boundaries, per-tier approaching-% scaling | unit | `pytest tests/test_sla_tier_service.py::test_compute_sla_state -x` | ❌ Wave 0 |
| SLA-02 | NULL-score fallback still resolves to a severity-keyed state (D-03) | unit | `pytest tests/test_sla_tier_service.py::test_null_score_fallback -x` | ❌ Wave 0 |
| SLA-02 | `GET /vulnerabilities` and `GET /vulnerabilities/{id}` responses carry `sla_state`/`sla_due_at` | integration | `pytest tests/test_vulnerabilities.py::test_list_includes_sla_state -x` | ❌ Wave 0 (extend existing vuln router test file — check for `test_vulnerabilities.py` or equivalent) |
| SLA-03 | Exactly-once escalation firing across a transition; re-running the tick logic twice produces no duplicate rows | integration | `pytest tests/test_sla_escalation.py::test_exactly_once -x` | ❌ Wave 0 — direct-await the dispatcher function, mirroring `test_scheduler_enrichment_refresh.py`'s convention |
| SLA-03 | Channel payload shape assertions (Slack/Teams/PagerDuty/Email), via monkeypatched senders | unit | `pytest tests/test_sla_escalation.py::test_channel_payloads -x` | ❌ Wave 0 |
| SLA-03 | Every escalation fire produces exactly one `audit()` row | integration | `pytest tests/test_sla_escalation.py::test_audit_coverage -x` | ❌ Wave 0 |
| SLA-03 | Old `alerts.py::_check_sla_breaches` no longer double-fires alongside the new engine (D-08 reconciliation) | integration | `pytest tests/test_notifications_alerts.py::test_no_double_fire -x` | ❌ Wave 0 (check whether a `test_notifications_alerts.py`/`test_alerts.py` already exists to extend — none found in this session's search) |
| SLA-04 | Remediation-event row written with correct tier-at-remediation + duration at each of the 6 write sites | integration | `pytest tests/test_remediation_events.py -x` | ❌ Wave 0 |
| SLA-04 | MTTR-by-tier aggregate query returns correct grouped averages | unit | `pytest tests/test_remediation_events.py::test_mttr_by_tier_aggregate -x` | ❌ Wave 0 |
| SLA-01/D-11 | `SlaPill` renders on-track/approaching/breached from a server-provided `state` prop | unit | `npx vitest run src/components/tickets/sla-pill.test.tsx` | ✅ (extend existing file) |
| SLA-01/D-10 | New "SLA & Escalation" settings pane: dirty-state, save, RBAC-aware render | unit | `npx vitest run src/components/settings/sla-escalation-pane.test.tsx` | ❌ Wave 0 — mirror `saml-pane.test.tsx`/`ai-usage-pane.test.tsx` conventions (note: `notifications-pane.tsx`, the closest structural analog, has **no** test file today — don't mirror an untested pane) |

### Sampling Rate
- **Per task commit:** run the specific new/changed test file directly (per-file, per project memory — avoid whole-`tests/`-dir false failures).
- **Per wave merge:** `cd backend && pytest -v --cov=app --cov-report=term-missing` + `cd frontend && npm test`.
- **Phase gate:** Full backend + frontend suites green, plus a manual/live check of at least one real channel (or an explicit documented waiver, matching this project's existing precedent for untestable live integrations) before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `backend/tests/test_sla_tier_service.py` — covers SLA-01/SLA-02 (tier boundaries, state formula, fallback)
- [ ] `backend/tests/test_sla_escalation.py` — covers SLA-03 (exactly-once, channel payloads, audit coverage)
- [ ] `backend/tests/test_remediation_events.py` — covers SLA-04 (write-hook coverage, MTTR aggregate)
- [ ] Extend `backend/tests/test_tenants.py` (or create `test_tenant_sla_settings.py`) — covers SLA-01's RBAC/CRUD
- [ ] Extend the vulnerabilities router test file — covers the `sla_state` field appearing in list/detail responses
- [ ] `frontend/src/components/settings/sla-escalation-pane.test.tsx` — new pane
- [ ] Extend `frontend/src/components/tickets/sla-pill.test.tsx` — new `state` prop path
- [ ] Framework install: none — all frameworks already present

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | No (new behavior) | Existing session/OIDC auth unchanged |
| V3 Session Management | No | Unchanged |
| V4 Access Control | Yes | `require_admin`/`require_owner` RBAC on the extended `/tenants/settings` (matches existing precedent — GET admin, PATCH owner, `[VERIFIED]` tenants/router.py:105-154); every new query tenant_id-scoped (project-wide constraint, STATE.md) |
| V5 Input Validation | Yes | Pydantic validation on the new `sla_config` shape (tier days must be positive ints, approaching_pct bounded 0-100, tier floor a valid tier name); webhook URL scheme/host validation (Pitfall 10, SSRF) |
| V6 Cryptography | Partial — Open Question #6 | New channel secrets currently would follow the existing plaintext-JSONB precedent (`smtp_config.password`) unless explicitly elevated to use `app/encryption.py::encrypt_value` (already used for `ConnectorConfig.credentials`) |
| V10 Malicious Input / SSRF | Yes (new surface) | Validate webhook URL scheme + disallow private/loopback/metadata targets; `follow_redirects=False` on outbound httpx calls (Pitfall 10) |
| V7 Error Handling / Logging | Yes | `audit()`'s fail-closed contract already covers this — every escalation fire and every SLA policy change must go through it (D-07 already locks this in) |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| SSRF via tenant-admin-controlled webhook URL | Tampering / Information Disclosure | Scheme allowlist (`https://` only), block private/loopback/link-local/metadata targets, disable redirect-following on the outbound `httpx` client |
| Secret leakage via settings GET round-trip | Information Disclosure | Mask-on-read + touched-flag-on-write (Pattern 4) — already proven for SMTP password, extend to PagerDuty routing key + Slack/Teams webhook URLs |
| Audit-trail gap on escalation fire (mutation succeeds, audit row doesn't land) | Repudiation | Reuse `audit()`'s existing fail-closed contract verbatim — do not write a separate, weaker audit path for escalations |
| Double-fire / notification spam (D-08 unreconciled legacy path) | Denial of Service (alert fatigue), not a security vuln per se but a real operational risk | Explicit reconciliation of `alerts.py::_check_sla_breaches` vs. the new engine (Pitfall 1) |
| Cross-tenant data leak in the new escalation-event/remediation-event tables | Information Disclosure | `tenant_id` FK + index on every new table, every query filtered by it — matches the project-wide V4 convention already used throughout (`RiskExposureBackfillJob`, `VulnerabilityCorrelation`, etc.) |

## Sources

### Primary (HIGH confidence)
- Direct file reads (all `[VERIFIED]`): `backend/app/vulnerabilities/sla_service.py`, `backend/app/assets/risk_score.py`, `backend/app/vulnerabilities/models.py`, `backend/app/vulnerabilities/risk_exposure_service.py`, `backend/app/vulnerabilities/risk_cutover_service.py`, `backend/app/connectors/scheduler.py`, `backend/app/notifications/alerts.py`, `backend/app/audit.py`, `backend/app/notifications/service.py`, `backend/app/tenants/models.py`, `backend/app/tenants/router.py`, `backend/app/auth/rbac.py`, `backend/app/email.py`, `backend/app/ticketing/models.py`, `backend/app/ticketing/service.py`, `backend/app/ticketing/daily_sync.py`, `backend/app/vulnerabilities/service.py`, `backend/app/vulnerabilities/router.py`, `backend/app/vulnerabilities/schemas.py`, `backend/app/cspm/models.py`, `backend/alembic/versions/044_add_risk_backfill_job.py`, `backend/tests/test_sla_service.py`, `backend/tests/test_scheduler_enrichment_refresh.py`, `backend/tests/conftest.py`, `frontend/src/components/tickets/sla-pill.tsx` + `.test.tsx`, `frontend/src/components/settings/notifications-pane.tsx`, `settings-sidebar-shell.tsx`, `save-bar.tsx`, `use-dirty-state.ts`, `microcopy.ts`, `frontend/src/lib/queries/use-tenant-settings.ts`, `use-vulnerabilities.ts`, `use-vulnerability-detail.ts`, `frontend/src/components/vulnerabilities/vuln-table.tsx`, `drill-content.tsx`.
- [Create an Incoming Webhook - Teams | Microsoft Learn](https://learn.microsoft.com/en-us/microsoftteams/platform/webhooks-and-connectors/how-to/add-incoming-webhook) — live-fetched, page dated 2026-08-03. Confirms classic connector retirement + current Workflows-based mechanism, payload shapes, rate limits.
- [Sending messages using incoming webhooks | Slack Developer Docs](https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks/) — live-fetched. Confirms `text`/`blocks` payload shape, response codes, error bodies.

### Secondary (MEDIUM confidence)
- [Send an Alert Event | PagerDuty Developer Documentation](https://developer.pagerduty.com/docs/events-api-v2/trigger-events/index.html) — WebSearch-verified (direct WebFetch of the page failed twice this session; content cross-referenced via search snippets from this and adjacent developer.pagerduty.com pages).
- [Integrate Your Monitoring System With PagerDuty Using Events API V2](https://blog.incidenthub.cloud/Integrate-Your-Monitoring-System-With-PagerDutys-Events-API-V2) — corroborating source for field shapes.
- [Retirement of Office 365 connectors within Microsoft Teams - Microsoft 365 Developer Blog](https://devblogs.microsoft.com/microsoft365dev/retirement-of-office-365-connectors-within-microsoft-teams/) — corroborates the Teams retirement timeline found via WebSearch.
- [Status of Legacy MessageCard support in Workflows (October 28 update) - Microsoft Q&A](https://learn.microsoft.com/en-us/answers/questions/5685899/status-of-legacy-messagecard-support-in-workflows) — corroborates MessageCard-via-Workflows compatibility.

### Tertiary (LOW confidence)
- PagerDuty response-body shape (Assumptions Log A1/A2) — training-knowledge only for this specific detail, not independently re-verified this session after two failed WebFetch attempts.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every backend/frontend library claim directly verified via `pip show`/`grep`/file read; zero new dependencies needed.
- Architecture: HIGH — every integration point (scheduler tick, ticket-SLA mirror, schema gaps, RBAC asymmetry) verified via direct code read with file:line citations.
- Escalation channel contracts: MEDIUM-HIGH — Slack and Teams confirmed via live official-doc fetch (HIGH); PagerDuty confirmed via cross-referenced WebSearch of official/adjacent pages (MEDIUM, two direct WebFetch attempts failed); SMTP confirmed via direct code read (HIGH).
- Pitfalls: HIGH — nearly all sourced from direct code reads of real, currently-shipping behavior, not speculation.

**Research date:** 2026-08-13
**Valid until:** 30 days for the codebase-internal findings (stable, slow-moving backend); **7 days for the Microsoft Teams webhook-retirement finding specifically** — this is an active platform migration with a recently-passed deadline; if planning is delayed, re-verify the current Teams webhook mechanism before implementation.
