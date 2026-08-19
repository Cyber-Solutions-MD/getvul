# Phase 40: Proactive Alerting & Digests - Research

**Researched:** 2026-08-19
**Domain:** Backend event detection + in-process scheduling + multi-channel notification delivery + tenant-config settings pane (FastAPI/Postgres/Next.js)
**Confidence:** HIGH — this phase is almost entirely wiring already-shipped primitives; every referenced module was read in-session and its exact contract confirmed.

## Summary

Phase 40 makes GetVul **push** exposure to people. It is a low-invention, high-reuse phase: every delivery primitive it needs already exists and was verified in-session. The real-time alert scaffold (`run_alert_checks` + `_check_*` siblings, `_notification_exists`, `_email_owners_and_admins`), the multi-channel fan-out with SSRF guard + retry + fail-isolation (`escalation_channels.dispatch_channel`), the in-process asyncio scheduler tick (`_scheduler_loop`), the tenant JSONB-config + masked-secret + fail-closed-audit settings pattern (`tenants/router.py::update_tenant_settings` for `sla_config`), the Phase 36 SLA state resolver (`resolve_state_for_vuln`), the Phase 39 exclusion predicate (`active_exception_subquery`) and expiry surface (`ExceptionRecord.expires_at`), and the hand-rolled settings pane pattern (`sla-escalation-pane.tsx` + `SettingsSidebarShell`) are all present and directly extensible. [VERIFIED: read in-session]

Three genuinely-new pieces must be built: (1) a **per-tenant "already-alerted" guard table** (D-05) via a new Alembic migration `051_*`, because `repropagate_enrichment` overwrites `cisa_kev`/`epss_score` in place with **no transition capture** [VERIFIED: enrichment_feeds.py:234-263] — there is no newly-KEV event to consume, so detection must own its state; (2) a **wall-clock send-hour gate** (D-12) — no existing scheduler implements a "past target hour in tenant tz AND not sent this period" check (both `_is_due` in reports.py and the `_last_ticket_sync` idiom are pure elapsed-hours gates) [VERIFIED: reports.py:155-166, scheduler.py:342-353]; and (3) an **HTML digest email body** — `email.py::send_email` currently only attaches `MIMEText(body, "plain")` [VERIFIED: email.py:52].

**Primary recommendation:** Add `_check_new_kev_epss` as a sibling in `run_alert_checks` backed by a new guard table (seed-silently on first pass per D-06); add a digest-dispatch block to `_scheduler_loop` gated by a new wall-clock send-hour helper; store all config in a new `Tenant.alerting_config` JSONB column saved through the exact `sla_config` masked/validated/audited route pattern; reuse `dispatch_channel` for channel pushes and `email.py` for owner/HTML digests; build the settings pane as a structural clone of `sla-escalation-pane.tsx`. Introduce zero new infra.

## User Constraints (from CONTEXT.md)

### Locked Decisions

**ALERT-01 — Trigger & Thresholds**
- **D-01:** High-EPSS = a tenant-overridable numeric `epss_score` threshold, default 0.5 (not percentile-rank, not KEV-only).
- **D-02:** Transition-only firing. Fire once when a CVE newly enters KEV OR newly crosses the EPSS threshold — not on every current match each tick. No daily re-alerting.
- **D-03:** Add a distinct `_check_new_kev_epss` sibling check in `run_alert_checks` — do NOT fold KEV/EPSS into `_check_new_critical_vulns`.
- **D-04:** Alert granularity = per (CVE, asset) transition, guarded once-only per `(tenant, cve, asset, trigger_type)`.

**ALERT-01 — Detection & Cold Start**
- **D-05:** Detection via a per-tenant "already-alerted" guard table keyed `(tenant_id, cve_id, asset_id, trigger_type)`. Each tick compute current qualifiers, subtract rows already in the guard, fire on the remainder, insert. One-way reversibility (new Alembic table).
- **D-06:** Seed a baseline on first run — record all currently-qualifying pairs WITHOUT firing. Also applies when a tenant newly enables KEV/EPSS or lowers the threshold (default = seed silently).

**Routing**
- **D-07:** ALERT-01 routes to the tenant alert channel (Slack/Teams webhook) + email to the matched asset's resolved owner(s) + admins.
- **D-08:** Digest recipient scope = both per-owner AND per-team (AssetGroup). Admin can enable either or both.
- **D-09:** Digest channel split: owner digests → email; team digests → the team's shared Slack/Teams channel (email optional).
- **D-10:** Owner-resolution fallback: no resolved owner → admins + tenant alert channel; multiple owners → notify all; asset in no AssetGroup → covered by per-owner digest only.

**ALERT-02 — Schedule & Content**
- **D-11:** Cadence = tenant-configurable daily or weekly, default daily. No per-recipient cadence store.
- **D-12:** Send timing = configurable target hour in the tenant's timezone. Each tick checks "past the target hour AND not yet sent this period."
- **D-13:** Digest sections = due + breaching + newly-critical + expiring-exceptions.
- **D-14:** Empty digests are suppressed — send nothing when all sections empty for a recipient. No "all clear" digest.
- **D-15:** Digest format = HTML (reuse `email.py`), top-N per section (e.g. top 10 by risk) + "and N more" line + deep-links back to the filtered dashboard view.

**ALERT-03 — Config, Rules Model, Audit**
- **D-16:** Fixed structured settings, NOT a rule-builder. KEV on/off, EPSS threshold, cadence + send-hour + timezone, per-type channel routing, per-owner/per-team enablement.
- **D-17:** New "Alerting & Digests" settings pane in `/settings` (RBAC-gated admin/owner), using `SettingsSidebarShell` + `SaveBar` + `useDirtyState`. Kept separate from the "SLA & Escalation" pane.
- **D-18:** Config stored in a new `alerting_config` JSONB key on `Tenant`, every save routed through the fail-closed `audit()` path.
- **D-19:** Reuse Phase 36's channel credentials with independent enablement/routing (alerting does NOT inherit SLA-escalation rules).

**Exclusions & Overlap**
- **D-20:** Excepted/suppressed findings excluded everywhere. `status IN (SUPPRESSED, FALSE_POSITIVE)` OR active exception (Phase 39) excluded from ALERT-01 and every digest section. Reuse the Phase 39 exclusion predicate — do not re-derive.
- **D-21:** Real-time push and digest may overlap by design. No dedup between the two.

### Claude's Discretion
- Exact table/column names + migration structure for the D-05 guard table; whether it shares infra with `SlaEscalationEvent`.
- Whether the guard table stores `fired_at` for observability vs. bare existence rows.
- Exact `alerting_config` JSONB schema + default values.
- Where in `_scheduler_loop()` the digest dispatch and `_check_new_kev_epss` calls slot in.
- Per-channel payload formatting for the digest (reuse `dispatch_channel` builders vs. digest-specific formatting).
- Per-section top-N cap value + exact deep-link URL construction.
- Retry/failure semantics for a failing channel POST (reuse `_post_json_with_retry` + audit; don't block the run).
- Whether "team" AssetGroup digests iterate all groups every tick vs. only groups with content.

### Deferred Ideas (OUT OF SCOPE)
- Per-recipient (per-user) notification preferences (needs a user-preference store).
- Per-owner Slack/Teams DM routing (no owner→handle data source; IdP/MDM/HR give email only).
- Generic rule-builder engine (`when <condition> then notify <channel>`).
- PagerDuty for ALERT-01 (optional channel-routing option, not mandated).

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ALERT-01 | A newly KEV-listed or high-EPSS CVE matching a tenant asset fires a targeted alert to the right channel | New `_check_new_kev_epss` sibling in `run_alert_checks` (alerts.py:30-33) + new guard table (D-05) because `repropagate_enrichment` has no transition capture (enrichment_feeds.py:234). Routing via `dispatch_channel` (D-07) + `_email_owners_and_admins`/`_get_directory_user` owner resolution (assets/router.py:81). |
| ALERT-02 | Scheduled per-owner / per-team digests of due/breaching/newly-critical/expiring-exception findings on the in-process scheduler | New digest-dispatch block in `_scheduler_loop` (scheduler.py:369) with a NEW wall-clock send-hour gate (D-12, no existing analog). Content reads `resolve_state_for_vuln` (sla_tier_service.py:144), `ExceptionRecord.expires_at`, and `~active_exception_subquery`. HTML body extends `email.py::send_email` (currently plain-text only). |
| ALERT-03 | Alert rules + delivery channels tenant-configurable on a settings page; every change audited | New `Tenant.alerting_config` JSONB (models.py:41 precedent) saved through the `sla_config` route pattern (tenants/router.py:332-380) with a dedicated `alerting.config_update` audit action via the fail-closed `audit()` (audit.py:148). New "Alerting & Digests" pane cloning `sla-escalation-pane.tsx`. |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Newly-KEV/EPSS transition detection | API / Backend (scheduler tick) | Database (guard table) | Transition state is not in the feed; backend must own it in a durable table |
| Alert channel push (Slack/Teams/email) | API / Backend (`dispatch_channel`) | External (webhooks/SMTP) | Existing delivery plumbing; channel secrets live server-side (Fernet) |
| Owner-email resolution | API / Backend (`_get_directory_user`) | Database (Asset/User) | Owner email comes from IdP/MDM/HR enrichment on the Asset row |
| Digest scheduling (send-hour gate) | API / Backend (`_scheduler_loop`) | — | In-process asyncio only (SC2: no new infra) |
| Digest content assembly (SLA/exception/critical state) | API / Backend | Database | Reads Phase 36 SLA resolver + Phase 39 exclusion/expiry |
| HTML digest rendering | API / Backend (`email.py`) | — | Server-generated static HTML; no client tier involved |
| Config storage + audit | API / Backend + Database (`Tenant.alerting_config`) | — | JSONB column + fail-closed audit, tenant-scoped |
| Settings pane (form) | Frontend Server (Next.js pane) | API (`PATCH /settings`) | Hand-rolled Tailwind pane, RBAC-gated; API enforces owner-only PATCH |
| In-app ALERT-01 twin + audit-log rows | Frontend (existing bell/toast + audit pane) | API | Reused verbatim; only new triggers/rows, no new UI |

## Standard Stack

This phase adds **zero new dependencies**. Everything is already in the codebase. Verification below confirms the in-repo modules, not registry versions (no `npm install`/`pip install` needed).

### Core (existing, reuse verbatim)
| Module | Purpose | Why Standard |
|--------|---------|--------------|
| `app/notifications/alerts.py::run_alert_checks` | Every-5-min alert scaffold; ALERT-01 adds a sibling here (D-03) | The established alert-check pattern; `_notification_exists` + `_email_owners_and_admins` reusable [VERIFIED: alerts.py] |
| `app/notifications/escalation_channels.py::dispatch_channel` | Slack/Teams/PagerDuty/email fan-out w/ SSRF guard, 429-retry, fail-isolation | The delivery layer for ALERT-01 push + team-digest posts (D-07/D-09/D-19) [VERIFIED: escalation_channels.py] |
| `app/email.py::send_email` | SMTP delivery | Email channel for alerts + owner/HTML digests (D-09/D-15) [VERIFIED: email.py] |
| `app/connectors/scheduler.py::_scheduler_loop` | In-process asyncio tick loop | SC2 forbids new infra; digest + `_check_new_kev_epss` slot in here [VERIFIED: scheduler.py:249-406] |
| `app/vulnerabilities/sla_tier_service.py::resolve_state_for_vuln` | Per-finding SLA state (on_track/approaching/breached) | Digest "due"/"breaching" content reads this (D-13) [VERIFIED] |
| `app/exceptions/service.py::active_exception_subquery` | Compute-on-read exclusion predicate | D-20 exclusion — `~active_exception_subquery(tenant_id, now)` [VERIFIED] |
| `app/audit.py::audit` | Fail-closed audit-then-commit | ALERT-03 config audit (D-18) [VERIFIED: audit.py:148] |
| `app/notifications/service.py::create_notification` | In-app notification twin | ALERT-01 in-app twin (E3, reused verbatim) [VERIFIED] |

### Supporting (existing patterns to mirror)
| Module | Purpose | When to Use |
|--------|---------|-------------|
| `tenants/router.py::update_tenant_settings` (`sla_config` branch, lines 332-380) | Masked-secret + validated + dedicated-audit JSONB save | The exact template for the `alerting_config` PATCH branch |
| `tenants/router.py` inline Pydantic models (`SlaConfigUpdate`, `SlaChannelsConfig`, `_safe_sla`) | Endpoint-local validation + mask-on-read | Mirror as `AlertingConfigUpdate` / `_safe_alerting` |
| `assets/router.py::_get_directory_user` (lines 81-107) | Resolve an asset's owner User by email (mdm humaans_email / assigned_user / last_login_user) | Owner-email resolution for D-07/D-10 |
| `reports.py::run_due_reports` + `_is_due` (lines 124-166) | Enabled-rows + due-gate + send-then-stamp loop | Structural analog for the digest dispatch loop (but D-12 needs a NEW wall-clock gate, not `_is_due`'s elapsed-hours) |
| `sla_tier_service.py::_build_channel_config` (lines 328-344) | Decrypt Fernet secret + assemble `dispatch_channel` config; merges `sla_config.channels.email.to` + `Tenant.smtp_config` | Reuse to build alerting channel configs from the SHARED Phase 36 credentials (D-19) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| New guard table (D-05) | Snapshot prior KEV/EPSS values inside the feed job | Rejected in D-05: `repropagate_enrichment` is tenant-agnostic and can't honor per-tenant thresholds; couples alerting to the feed pipeline |
| Wall-clock send-hour gate (D-12) | Pure `_last_*` 24h elapsed gate | Rejected in D-12: drifts with process restarts, not tied to a business hour |
| Digest-specific HTML builder | Reuse `dispatch_channel`'s `_build_summary_text` | Discretion item; `dispatch_channel` builders are single-finding SLA-shaped, not multi-section digest-shaped — likely need digest-specific formatting for D-15 |

**Installation:** None. `import` from existing modules.

## Architecture Patterns

### System Architecture Diagram

```
                        ┌─────────────────────────────────────────────┐
                        │   _scheduler_loop()  (in-process asyncio,    │
                        │    60s tick, single process — scheduler.py)  │
                        └───────────────┬─────────────────────────────┘
                                        │  (per tick, isolated try/except blocks)
        ┌───────────────────────────────┼───────────────────────────────────┐
        │                               │                                    │
        ▼ (every 5 min, existing)       ▼ (NEW: wall-clock send-hour gate)   ▼ (existing SLA pass, upstream)
 run_alert_checks(db)            digest dispatch (per tenant)          run_sla_tier_pass + detect_and_escalate
   ├ _check_new_critical_vulns     ├ for cadence-due tenants past      (writes sla_due_at / sla_breached;
   ├ _check_sync_failures          │   send-hour & not-sent-this-period  ALERT-02 reads these, does not fire)
   ├ _check_risk_score_changes     ├ per-owner: resolve owners → email
   └ _check_new_kev_epss  (NEW)    └ per-team:  AssetGroup → shared Slack/Teams
        │                                    │
        ▼                                    ▼
  current qualifiers =            assemble sections (top-N by risk):
   (cisa_kev OR epss>=thr)          due | breaching | newly-critical | expiring-exceptions
   matched to tenant assets,          each EXCLUDING ~active_exception_subquery + SUPPRESSED/FALSE_POSITIVE (D-20)
   EXCLUDING excepted (D-20)          │
        │                             ▼   suppress if all sections empty (D-14)
   SUBTRACT rows in guard table       │
   (tenant,cve,asset,trigger)         ▼
        │                       render HTML (email.py, NEW html body) / dispatch_channel (team)
   fire on remainder ──► dispatch_channel (Slack/Teams) + _email_owners_and_admins
        │                        + create_notification (in-app twin)
        ▼
   INSERT fired pairs into guard table (once-only, D-04)
   [first pass: seed baseline WITHOUT firing — D-06]

  ┌──────────────────────────────────────────────────────────────────┐
  │  Config plane (independent of the tick):                          │
  │  Next.js "Alerting & Digests" pane  ──PATCH /tenant/settings──►    │
  │  update_tenant_settings → validate (AlertingConfigUpdate) →       │
  │  mask/merge secrets → Tenant.alerting_config (JSONB) →            │
  │  audit("alerting.config_update", fail-closed) → commit            │
  │  The scheduler reads Tenant.alerting_config each tick.            │
  └──────────────────────────────────────────────────────────────────┘
```

### Recommended Structure (files this phase touches)
```
backend/app/
├── notifications/
│   ├── alerts.py              # ADD _check_new_kev_epss sibling (D-03)
│   ├── digests.py             # NEW — digest assembly + send-hour gate + HTML (D-11..15)
│   └── escalation_channels.py # REUSE dispatch_channel (unchanged)
├── connectors/scheduler.py    # ADD digest dispatch block in _scheduler_loop (D-12)
├── email.py                   # ADD html_body support to send_email (D-15)
├── tenants/
│   ├── models.py              # ADD Tenant.alerting_config JSONB column (D-18)
│   └── router.py              # ADD alerting_config PATCH branch + AlertingConfigUpdate + _safe_alerting (D-18)
├── vulnerabilities/models.py  # NEW guard model (or app/notifications/) for D-05
└── alembic/versions/051_*.py  # NEW guard table + alerting_config column migration

frontend/src/
├── components/settings/
│   ├── alerting-digests-pane.tsx   # NEW — clone of sla-escalation-pane.tsx (D-17)
│   ├── settings-sidebar-shell.tsx  # ADD 'alerting' to ALL_CATEGORIES + ADMIN_ONLY
│   └── microcopy.ts                # ADD 'alerting' Category + CATEGORY_LABELS entry
└── app/(authed)/dashboard/settings/page.tsx  # ADD case 'alerting' to renderPane()
```

### Pattern 1: Guard-table transition detection with silent cold-start (D-05/D-06)
**What:** Each tick, compute current qualifiers and subtract the guard set; the difference is "new"; insert the difference. First-ever pass inserts everything WITHOUT firing.
**When to use:** Any "fire once on transition" where the source data is overwritten in place with no history (exactly the KEV/EPSS case).
```python
# The subtraction pattern — grounded in enrichment_feeds.py:234 (no transition capture)
# For trigger_type in ("kev", "epss"):
#   qualifiers = SELECT (cve_id, asset_id) FROM vulnerabilities v JOIN assets ...
#     WHERE tenant_id = t AND status NOT IN ('SUPPRESSED','FALSE_POSITIVE')
#       AND ~active_exception_subquery(t, now)                       # D-20
#       AND (v.cisa_kev IS TRUE)  -- or  (v.epss_score >= tenant_threshold)
#   already = SELECT (cve_id, asset_id) FROM alerting_guard
#             WHERE tenant_id=t AND trigger_type=trigger
#   new_pairs = qualifiers - already
#   if guard_is_empty_for(tenant, trigger):   # D-06 first-run / newly-enabled
#       insert new_pairs; DO NOT fire
#   else:
#       fire(new_pairs); insert new_pairs
```
Note `epss_score` is `Numeric(5,4)` on the vuln row [VERIFIED: models.py:57] — compare against the tenant threshold as a Decimal/float carefully (see Pitfall 3).

### Pattern 2: Fail-isolated channel dispatch inside a scheduler tick
**What:** Every channel POST is wrapped so one failure never aborts the rest of the tick. `dispatch_channel` already guarantees this — it always returns `{"ok": bool, "error": str|None}` and never raises.
```python
# Source: escalation_channels.py:272-298 (verified in-session)
outcome = await dispatch_channel(channel, config, context)  # never raises
if not outcome["ok"]:
    logger.error("alert_channel_failed", channel=channel, error=outcome["error"])
    # record + continue — do NOT let it stall the rest of the run (Pattern 1)
```
Build the channel `config` with `_build_channel_config(sla_config, channel, tenant)` (sla_tier_service.py:328) so alerting reuses Phase 36's Fernet-decrypted shared credentials (D-19).

### Pattern 3: Scheduler-originated audit (no CurrentUser)
**What:** The shared `audit()` helper writes `tenant_id=uuid.UUID(int=0)` when `user is None` — wrong for a tenant-scoped scheduler row. Construct `AuditLog` directly with a real `tenant_id` and `user_email="system:scheduler"`.
```python
# Source: sla_tier_service.py:347-388 & audit.py:179 (verified)
# ALERT-01/02 scheduler-side audit (if you audit sends) must NOT call audit(db, None, ...).
db.add(AuditLog(tenant_id=tenant.id, user_id=None, user_email="system:scheduler",
                action="alert.fire", resource_type="vulnerability", resource_id=..., ...))
```
The CONFIG save (ALERT-03), by contrast, DOES have a real `CurrentUser` and MUST use `await audit(db, user, "alerting.config_update", "tenant", ...)` then `await db.commit()` (tenants/router.py:367 pattern).

### Pattern 4: Whole-object-replace config save with masked secrets (D-18/D-19)
**What:** `PATCH /settings` persists `sla_config` (and will persist `alerting_config`) as a WHOLE-OBJECT REPLACE. Masked-secret round-tripping requires the keep-stored-on-masked-write trick. **But** D-19 says alerting reuses Phase 36's credentials — so `alerting_config` likely stores routing/enablement/thresholds ONLY (no raw secrets), sidestepping the mask dance. Confirm during planning whether alerting_config holds any secret at all; if not, `_safe_alerting` masking is unnecessary.
```python
# Source: tenants/router.py:332-380 (verified)
if "alerting_config" in body:
    AlertingConfigUpdate.model_validate(new_cfg)          # 422 on bad shape
    tenant.alerting_config = new_cfg
    flag_modified(tenant, "alerting_config")              # JSONB in-place mutation guard
    await audit(db, user, "alerting.config_update", "tenant", str(tenant.id), {...secret-free...})
```

### Anti-Patterns to Avoid
- **Folding KEV/EPSS into `_check_new_critical_vulns`** — explicitly forbidden (D-03). Different trigger, dedup key, semantics.
- **Re-deriving the exclusion predicate** — D-20 mandates reusing `active_exception_subquery`. It's a correlated `EXISTS` with three OR-branches (finding/asset/group scope) that is easy to get wrong.
- **Re-deriving KEV/EPSS values** — consume `Vulnerability.cisa_kev`/`epss_score` as written by `repropagate_enrichment`; never re-fetch feeds (SC / D-05 grounding).
- **Calling `audit(db, None, ...)` from the scheduler** — mis-buckets to nil tenant (audit.py:179). Construct `AuditLog` directly.
- **`flag_modified` omission** on JSONB in-place edits — SQLAlchemy won't detect the mutation and the save silently no-ops (tenants/router.py uses `flag_modified` for every JSONB column).
- **Firing on the first alerting pass** — D-06 requires silent baseline seeding or launch-day produces a backlog alert storm.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSRF-safe webhook POST + 429 retry | Custom httpx wrapper | `escalation_channels._post_json_with_retry` / `dispatch_channel` | Already validates https-only, blocks private/loopback/metadata IPs, `follow_redirects=False`, retries 429 (escalation_channels.py:69-203) |
| Slack/Teams/PagerDuty payload shape | Hand-written JSON | `_build_slack_payload` / `_build_teams_payload` (Teams Workflows form, NOT retired MessageCard) | Teams "classic connector" MessageCard envelope is retired; the Workflows `{"text":...}` form is required (escalation_channels.py:129-135) |
| Owner-email resolution | New directory join | `_get_directory_user` (assets/router.py:81) | Encodes the mdm humaans_email → assigned_user → last_login_user precedence already |
| SLA due/breaching state | New date math | `resolve_state_for_vuln` (sla_tier_service.py:144) | Tier policy + Phase 39 excepted-seconds subtraction already handled |
| Excepted/suppressed exclusion | New WHERE clause | `~active_exception_subquery(tenant_id, now)` + `status NOT IN (...)` | Compute-on-read exclusion is subtle across ~12 consumers; reuse verbatim (D-20) |
| Fail-closed config audit | Direct AuditLog for config | `await audit(db, user, ...)` then commit | audit.py is deliberately fail-closed; commit short-circuits if the audit row can't write |
| Overlapping-interval math (if you touch expiry) | Naive sum | `_merge_intervals` (exceptions/service.py:94) | Overlaps double-count; already merge-adjacent-sorted |
| SMTP send | New mailer | `email.py::send_email` | Handles TLS/STARTTLS/auth, never raises, returns `{"ok":...}` |

**Key insight:** This phase's risk is NOT novelty — it's mis-wiring a well-established set of primitives (wrong audit actor, missing `flag_modified`, re-deriving exclusion, forgetting the D-06 baseline). Every "build" temptation here already has a canonical in-repo implementation.

## Runtime State Inventory

> This phase ADDS state; it is not a rename/refactor. Included because D-05 introduces a durable guard table whose lifecycle matters.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | NEW `alerting_guard` table (D-05) keyed `(tenant_id, cve_id, asset_id, trigger_type)`; NEW `Tenant.alerting_config` JSONB column | Alembic migration `051_*`; guard is populated at runtime (seed-silent on first pass per D-06) |
| Live service config | Slack/Teams/PagerDuty webhook secrets — REUSED from Phase 36's `Tenant.sla_config.channels` (Fernet-encrypted, masked on read). Alerting adds its own enablement/routing but shares credentials (D-19) | None new — reference existing encrypted config via `_build_channel_config` |
| OS-registered state | None — the scheduler is an in-process asyncio task started at app boot (`start_scheduler`), no OS cron/systemd | None ("None — verified: scheduler.py:409 `start_scheduler` is an in-process `asyncio.create_task`") |
| Secrets/env vars | `ENCRYPTION_KEY` (Fernet) + `JWT_SECRET_KEY` already required for tests (per project memory); no NEW secret names | None — reuse `encryption.decrypt_value` |
| Build artifacts | None | None |

**Guard-table lifecycle caution:** Per D-05 reversibility note, dropping the guard table loses alerted-history and reopens the double-fire window. The seed-silent logic (D-06) MUST run whenever the guard is empty for a `(tenant, trigger_type)` slice — that is both first-ever run AND immediately after a tenant enables a trigger or lowers the EPSS threshold.

## Common Pitfalls

### Pitfall 1: No newly-KEV event exists to subscribe to
**What goes wrong:** Planner assumes the enrichment feed emits a "newly added to KEV" signal ALERT-01 can hook.
**Why it happens:** `repropagate_enrichment` says it "flips both ways" — that means the recompute is bidirectional (True→False and False→True), NOT that it emits a transition event. It's a bare `UPDATE ... SET cisa_kev = (cve_id IN (SELECT ...))` with no prior-value capture [VERIFIED: enrichment_feeds.py:234-263].
**How to avoid:** ALERT-01 MUST maintain its own alerted-state (the D-05 guard). This is the whole reason the guard table exists.
**Warning signs:** Any plan task that says "listen for KEV changes in the feed job."

### Pitfall 2: Wall-clock send-hour has no existing analog
**What goes wrong:** Copying `reports.py::_is_due` or the `_last_ticket_sync` 24h-gate for D-12 — both are pure `elapsed_hours >= N` checks that drift with restarts and ignore the tenant's business hour [VERIFIED: reports.py:155-166, scheduler.py:342-353].
**Why it happens:** They look superficially like "runs once per day."
**How to avoid:** Build a NEW gate: convert `now` into the tenant's timezone (`Tenant.timezone`, default "UTC" — models.py:37), check `local_now.hour >= configured_send_hour` AND the last-sent timestamp is not within the current period. Store last-sent per tenant (in-memory `_last_digest_sent` dict mirrors `_last_ticket_sync`, but must be period-aware, or persist on the tenant/guard so restarts don't double-send).
**Warning signs:** A digest that fires at process-start time instead of the configured morning hour.

### Pitfall 3: EPSS threshold comparison type mismatch
**What goes wrong:** `Vulnerability.epss_score` is `Numeric(5,4)` → SQLAlchemy returns a `Decimal`; the tenant threshold from JSONB is a Python `float`. Also note a codebase-wide gotcha: numeric columns are serialized to JSON as **strings** in some API paths (per project memory, `getvul-decimal-serialized-as-string`).
**Why it happens:** Decimal vs float vs str comparisons silently mis-fire or raise.
**How to avoid:** Do the `>=` comparison in SQL (`Vulnerability.epss_score >= literal(threshold)`) where Postgres coerces, or coerce both sides to a consistent type in Python. Default threshold 0.5 (D-01).
**Warning signs:** ALERT-01 fires on everything or nothing at the boundary.

### Pitfall 4: In-memory send-gate resets on restart → duplicate digests
**What goes wrong:** A module-global `_last_digest_sent` (like `_last_ticket_sync`) resets to `None` on every process restart/`--reload`, re-sending the day's digest.
**Why it happens:** Single-VM dev stack restarts frequently; the enrichment-refresh code hit exactly this class of bug and added a lock (scheduler.py:173-247 docstring documents a live-repro'd race).
**How to avoid:** Prefer a durable last-sent marker (a column on `Tenant` or a small `alerting_digest_send` row) over pure in-memory state, OR accept the risk explicitly and gate on send-hour + a "sent today" check that reads a persisted timestamp. Planner's discretion (D-12 says "reversible, local to the dispatch block") — but note the restart hazard.
**Warning signs:** Users report duplicate morning digests after a deploy.

### Pitfall 5: Missing `flag_modified` on JSONB write
**What goes wrong:** Assigning nested keys into `tenant.alerting_config` without `flag_modified(tenant, "alerting_config")` → SQLAlchemy doesn't mark the attribute dirty → the save is a silent no-op.
**Why it happens:** JSONB mutation tracking is opt-in.
**How to avoid:** Every existing JSONB save in tenants/router.py calls `flag_modified` (lines 311, 316, 361, 386, 396). Mirror it.
**Warning signs:** PATCH returns 200 but the config doesn't change.

### Pitfall 6: Digest content must apply the SAME exclusion as everything else
**What goes wrong:** A digest "due"/"breaching" section that queries vulns directly re-includes excepted/suppressed findings that Phase 39 removed everywhere else (D-20).
**Why it happens:** The exclusion is a compute-on-read join, not a status flag — easy to forget in a fresh query.
**How to avoid:** Every digest section query AND the ALERT-01 qualifier query must include `~active_exception_subquery(tenant.id, now)` and `status NOT IN ('SUPPRESSED','FALSE_POSITIVE')`.
**Warning signs:** A finding a user accepted-risk on last week shows up in their digest.

## Code Examples

### Adding the sibling check (D-03) — call site
```python
# Source: alerts.py:28-34 (verified). Add ONE line; keep existing paths untouched.
for tenant in tenants:
    alerts = 0
    alerts += await _check_new_critical_vulns(db, tenant)
    alerts += await _check_sync_failures(db, tenant)
    alerts += await _check_risk_score_changes(db, tenant)
    alerts += await _check_new_kev_epss(db, tenant)   # NEW (D-03)
    total_alerts += alerts
```

### Reusing shared channel credentials for an alert push (D-19)
```python
# Source: sla_tier_service.py:328-344 + escalation_channels.py:272 (verified)
sla_config = tenant.sla_config or {}
config = _build_channel_config(sla_config, channel, tenant)   # Fernet-decrypts secret server-side
outcome = await dispatch_channel(channel, config, {
    "cve_id": vuln.cve_id, "hostname": hostname, "to_state": "kev_listed", ...
})   # never raises; returns {"ok": bool, "error": str|None}
```

### Owner resolution + email (D-07/D-10)
```python
# Source: assets/router.py:81 (_get_directory_user) + alerts.py:270 (_email_owners_and_admins) (verified)
owner_user = await _get_directory_user(db, tenant.id, asset)   # None if unresolved
if owner_user is None:
    await _email_owners_and_admins(db, tenant, title, message, "new_kev_epss")  # D-10 fallback
else:
    await _send_notification_email(db, tenant.id, owner_user.email, title, message, "new_kev_epss")
```

### Config save branch (ALERT-03) — mirrors sla_config
```python
# Source: tenants/router.py:332-380 (verified)
if "alerting_config" in body:
    from sqlalchemy.orm.attributes import flag_modified
    new_cfg = body["alerting_config"] or {}
    try:
        AlertingConfigUpdate.model_validate(new_cfg)      # inline Pydantic gate (like SlaConfigUpdate)
    except ValidationError as exc:
        raise HTTPException(422, str(exc)) from exc
    tenant.alerting_config = new_cfg
    flag_modified(tenant, "alerting_config")
    await audit(db, user, "alerting.config_update", "tenant", str(tenant.id),
                {"kev_enabled": new_cfg.get("kev_enabled"),
                 "epss_threshold": new_cfg.get("epss_threshold"),
                 "cadence": new_cfg.get("cadence"), ...})   # secret-free details
# ... await db.commit() at end of handler
```

### HTML email — extend send_email (D-15)
```python
# email.py:52 currently: msg.attach(MIMEText(body, "plain"))
# Add an optional html_body param and attach BOTH parts (multipart/alternative)
# so plain-text clients still render. Use inline-CSS + light background per UI-SPEC.
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Flat severity-agnostic `_check_sla_breaches` in alerts.py | Retired to a no-op; risk-tier SLA engine owns breach in-app twin | Phase 36 | ALERT-02 "breaching" reads `resolve_state_for_vuln`, NOT the dead `_check_sla_breaches` (alerts.py:100-114) |
| Teams classic Incoming Webhook (MessageCard) | Teams Workflows webhook (`{"text":...}`) | Phase 36 | Never emit MessageCard envelope; `_build_teams_payload` is correct (escalation_channels.py:129) |
| Exception = status flip | Compute-on-read `active_exception_subquery` | Phase 39 | Exclusion is a join, not a column — must be applied per-query (D-20) |
| `email.py` plain-text only | (this phase) HTML multipart | Phase 40 | `send_email` gains an html body path |

**Deprecated/outdated:**
- `_check_sla_breaches` (alerts.py) — intentional no-op; do not revive or read from it.
- `sla_service.py` severity-keyed SLA — superseded by `sla_tier_service.py` for state; don't read due dates from it.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `alerting_config` will store routing/enablement/thresholds only (no raw channel secrets, since D-19 reuses Phase 36 creds), so `_safe_alerting` masking may be unnecessary | Pattern 4 | If planner decides alerting stores its own secrets, the mask/keep-stored-on-masked-write dance from sla_config is required |
| A2 | The wall-clock send-hour last-sent marker should be persisted (not in-memory) to survive restarts | Pitfall 2/4 | If left in-memory, duplicate digests after deploys; D-12 leaves this to planner discretion |
| A3 | Digest per-channel formatting needs a digest-specific builder (the existing `dispatch_channel` builders are single-finding SLA-shaped) | Standard Stack / Discretion | If forced through `_build_summary_text`, team-digest posts would be one-finding-shaped, not a multi-section summary |
| A4 | Team digests should iterate only AssetGroups with content to avoid empty-post churn (aligns with D-14 suppression) | Discretion | Iterating all groups every tick wastes queries but isn't incorrect |
| A5 | `_get_directory_user` (in assets/router.py) is importable/refactorable for reuse in the notifications layer | Code Examples | If it has router-coupled deps, a small extraction to a service module is needed |

**Note:** A1–A5 all map to explicit "Claude's Discretion" items in CONTEXT.md — they are planner decisions, not blockers.

## Open Questions

1. **Guard table home + shape**
   - What we know: keyed `(tenant_id, cve_id, asset_id, trigger_type)`; discretion whether to store `fired_at` and whether to share infra with `SlaEscalationEvent`.
   - What's unclear: `SlaEscalationEvent` is keyed on `vulnerability_id` (a UUID), whereas ALERT-01 keys on `(cve_id, asset_id)` — different identity, so sharing the table is a poor fit. A dedicated `alerting_guard` table is cleaner.
   - Recommendation: New table `alerting_guard` with a `UniqueConstraint(tenant_id, cve_id, asset_id, trigger_type)` + `fired_at` (cheap observability), mirroring the `uq_escalation_once` once-only pattern.

2. **Send-hour "sent this period" persistence**
   - What we know: D-12 wants "past target hour AND not sent this period"; the existing 24h gates are in-memory and restart-fragile.
   - What's unclear: whether to persist last-sent on `Tenant`, on a new per-tenant row, or accept in-memory.
   - Recommendation: persist a `last_digest_sent_at` (per tenant, or per (tenant, recipient-scope)) to avoid restart double-sends (Pitfall 4).

3. **Digest recipient iteration model**
   - What we know: per-owner (email) + per-team (AssetGroup shared channel), D-08/D-09.
   - What's unclear: how to enumerate "owners" — distinct resolved emails across the tenant's assets vs. distinct `User` rows.
   - Recommendation: group assets by resolved owner email (via `_get_directory_user` semantics), one digest per distinct owner; separate loop over AssetGroups for team digests.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Postgres | guard table + alerting_config + all queries | ✓ (project stack) | — | — |
| In-process asyncio scheduler | digest + alert dispatch | ✓ | — (already running) | — |
| SMTP (tenant `smtp_config`) | owner/HTML digest + ALERT-01 email | ✓ (config-gated at runtime) | — | Digest silently skips email if SMTP not enabled (matches reports.py:219 guard) |
| Slack/Teams webhooks (tenant `sla_config`) | ALERT-01 push + team digest | ✓ (config-gated) | — | Empty-channels EmptyState in the pane; no push if unconfigured |
| Fernet `ENCRYPTION_KEY` | decrypt shared channel secrets | ✓ (env) | — | Tests need it set (project memory) |

**Missing dependencies with no fallback:** None — all runtime deps are already present; external channels are tenant-config-gated by design.

## Validation Architecture

> nyquist_validation is enabled (config.json has no `workflow.nyquist_validation` key → treat as enabled).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3 + pytest-asyncio 0.24 (`asyncio_mode = "auto"`) [VERIFIED: pyproject.toml:74-82] |
| Config file | `backend/pyproject.toml` `[tool.pytest.ini_options]`, `testpaths = ["tests"]` |
| Quick run command | `cd backend && ENCRYPTION_KEY=... JWT_SECRET_KEY=... pytest tests/test_alerts_kev_epss.py -x` (per-file — project memory: whole-`tests/` runs give false failures) |
| Full suite command | `cd backend && ENCRYPTION_KEY=... JWT_SECRET_KEY=... pytest tests/ ` (env vars mandatory) |

Frontend: vitest + co-located `*.test.tsx` (e.g. `sla-escalation-pane.test.tsx` exists) for the new pane.

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ALERT-01 | New KEV/EPSS match fires once; guard prevents re-fire; D-06 seeds silently | unit | `pytest tests/test_alerts_kev_epss.py -x` | ❌ Wave 0 |
| ALERT-01 | Excepted/suppressed excluded (D-20) | unit | `pytest tests/test_alerts_kev_epss.py -k excluded -x` | ❌ Wave 0 |
| ALERT-01 | Owner-resolution fallback to admins+channel (D-10) | unit | `pytest tests/test_alerts_kev_epss.py -k owner -x` | ❌ Wave 0 |
| ALERT-02 | Send-hour gate fires past target hour, not before; not twice/period (D-12) | unit | `pytest tests/test_digests.py -k send_hour -x` | ❌ Wave 0 |
| ALERT-02 | Empty digest suppressed (D-14); sections read SLA/exception state (D-13) | unit | `pytest tests/test_digests.py -x` | ❌ Wave 0 |
| ALERT-02 | HTML body renders sections; per-owner vs per-team routing (D-08/D-09/D-15) | unit | `pytest tests/test_digests.py -k html -x` | ❌ Wave 0 |
| ALERT-03 | Config validates, persists to JSONB, audited via fail-closed path (D-18) | unit | `pytest tests/test_tenant_settings.py -k alerting -x` | ❌ Wave 0 (extend existing settings tests) |
| ALERT-03 | Pane renders/saves; RBAC owner-gate; empty-channels state (D-17) | unit (vitest) | `cd frontend && npx vitest run alerting-digests-pane` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** the relevant per-file `pytest tests/test_<file>.py -x` (env vars set).
- **Per wave merge:** `pytest tests/` full backend suite + `npx vitest run` frontend.
- **Phase gate:** full suite green before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_alerts_kev_epss.py` — ALERT-01 fire/guard/seed/exclusion/owner-fallback (no `test_alerts.py` exists today — verified)
- [ ] `tests/test_digests.py` — ALERT-02 send-hour gate, suppression, section content, HTML, per-owner/per-team routing
- [ ] Extend `tests/test_tenant_settings.py` (or add) — ALERT-03 alerting_config validation + audit action
- [ ] `frontend/.../alerting-digests-pane.test.tsx` — pane render/save/RBAC/empty-state (clone sla-escalation-pane.test.tsx)
- [ ] Shared fixtures: a KEV/EPSS-qualifying vuln+asset+owner-User factory; likely reuse existing conftest tenant/vuln fixtures

## Security Domain

> security_enforcement absent in config.json → treat as enabled.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no (reuses session auth) | existing OIDC/session |
| V4 Access Control | yes | GET `/settings` `require_admin`, PATCH `require_owner` (asymmetric, tenants/router.py:284) + pane RBAC gate; every query `tenant_id`-scoped |
| V5 Input Validation | yes | `AlertingConfigUpdate` Pydantic gate (mirror `SlaConfigUpdate`); EPSS threshold bounded 0..1; send-hour 0..23; cadence Literal["daily","weekly"] |
| V6 Cryptography | yes | Channel secrets stay Fernet-encrypted (reuse Phase 36 creds via `_build_channel_config`); mask on read; never round-trip plaintext/ciphertext to browser |
| V7 Errors & Logging (audit) | yes | Fail-closed `audit("alerting.config_update")` (audit.py); scheduler-side sends use direct `AuditLog` with real tenant_id |
| V10 Malicious / SSRF | yes | Every outbound webhook goes through `_validate_webhook_url` (https-only, blocks private/loopback/metadata) + `follow_redirects=False` — inherited free via `dispatch_channel` |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SSRF via tenant-supplied webhook URL | Tampering / Info-disclosure | `_validate_webhook_url` + no-redirect httpx (escalation_channels.py:69) — already enforced by reuse |
| Cross-tenant leakage in alerts/digests | Info-disclosure | Every qualifier/section query `tenant_id`-scoped; owner resolution restricted to same-tenant Users (`_get_directory_user` filters `User.tenant_id`) |
| Config change without audit trail | Repudiation | Fail-closed `audit()` — commit short-circuits if the audit row can't write (audit.py:28-33) |
| Secret exposure in audit/log/browser | Info-disclosure | sla_config's dedicated audit deliberately excludes raw channel config; mirror for alerting (tenants/router.py:363-380); mask on read |
| Alert storm on launch / threshold change | DoS / fatigue | D-06 silent baseline seeding; D-14 empty-digest suppression |
| Untrusted scanner text in alert/digest body (CVE names, hostnames) | XSS in HTML email | HTML-escape all finding-derived strings when building the digest HTML body (email clients render HTML) |

## Sources

### Primary (HIGH confidence — read in-session)
- `backend/app/notifications/alerts.py` — run_alert_checks, `_check_*`, `_notification_exists`, `_email_owners_and_admins`
- `backend/app/notifications/escalation_channels.py` — dispatch_channel, SSRF guard, retry, payload builders
- `backend/app/notifications/service.py` — create_notification signature
- `backend/app/connectors/scheduler.py` — `_scheduler_loop`, dispatch idioms, 24h-gate idiom
- `backend/app/connectors/enrichment_feeds.py` — repropagate_enrichment (no transition capture, grounds D-05)
- `backend/app/vulnerabilities/sla_tier_service.py` — resolve_state_for_vuln, `_build_channel_config`, scheduler-audit pattern
- `backend/app/exceptions/service.py` — active_exception_subquery, `_merge_intervals`, expiry
- `backend/app/exceptions/models.py` — ExceptionRecord.expires_at/revoked_at
- `backend/app/tenants/models.py` — Tenant JSONB precedent + timezone column
- `backend/app/tenants/router.py` — update_tenant_settings sla_config branch (masked/validated/audited save)
- `backend/app/audit.py` — fail-closed audit(), nil-tenant None-user branch
- `backend/app/email.py` — send_email (plain-text only today)
- `backend/app/assets/models.py` + `assets/router.py::_get_directory_user` — owner resolution
- `backend/app/assets/risk_score.py` — RISK_SCORE_TIER_* bands (top-N ordering)
- `backend/app/vulnerabilities/models.py` — cisa_kev/epss_score/sla_* columns, SlaEscalationEvent
- `backend/app/reports.py` — run_due_reports/_is_due (elapsed-hours gate analog)
- `frontend/src/components/settings/sla-escalation-pane.tsx`, `settings-sidebar-shell.tsx`, `microcopy.ts`, `settings/page.tsx`
- `40-CONTEXT.md`, `40-UI-SPEC.md`, `.planning/STATE.md`

### Secondary (MEDIUM)
- Project memory: `getvul-decimal-serialized-as-string`, `getvul-backend-pytest-env`, `getvul-nyquist-validation-state`

### Tertiary (LOW)
- None — no external/web sources were needed; the phase is fully internal.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every module read in-session, contracts confirmed.
- Architecture: HIGH — scheduler/alerts/config patterns are explicit and already exercised by Phases 36/39.
- Pitfalls: HIGH — the no-transition-event, wall-clock-gate, flag_modified, and exclusion pitfalls are all grounded in verified source.
- Discretion items (A1–A5): MEDIUM — these are deliberately open planner decisions, not unknowns.

**Research date:** 2026-08-19
**Valid until:** 2026-09-18 (stable internal codebase; 30 days). Re-verify only if Phase 36/39 modules change before planning.
