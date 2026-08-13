# Phase 36: Remediation SLA Engine & Escalation - Context

**Gathered:** 2026-08-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace today's flat **severity-keyed** SLA with a real **risk-tier-keyed SLA engine**. Every open finding carries a live SLA state (`on-track` / `approaching` / `breached`) computed off its v4.0 risk-exposure tier against a tenant-configurable policy; approaching/breach **transitions** auto-escalate to external channels (Slack / Teams / email / PagerDuty) exactly once per transition, fully audited; and MTTR is captured per risk tier for later reporting (Phase 42 trends, Phase 43 reporting).

Delivers success criteria SLA-01..04. This is a *how-to-implement* boundary — no new capabilities beyond the four criteria.

**Explicitly NOT this phase:** the v4.0 risk-exposure score itself (shipped — never re-derive it), the risk-cutover flip, two-way ticket sync (Phase 37), digests/alerting UI polish (Phase 40), trend/burndown analytics (Phase 42), executive reporting (Phase 43).

</domain>

<decisions>
## Implementation Decisions

### SLA State Model
- **D-01:** SLA policy is **risk-tier-keyed**, computed off the v4.0 `Vulnerability.risk_exposure_score` bands (`RISK_SCORE_TIER_CRITICAL=80 / HIGH=50 / MEDIUM=20` from [risk_score.py](../../../backend/app/assets/risk_score.py#L59-L61)). Default policy: critical 7d / high 30d / moderate 90d. **This keys off the raw shadow-computed `risk_exposure_score`, independent of the `cutover_risk_exposure_scoring` flag** (which stays default-OFF and only governs which score is *primary* for sort/display).
- **D-02:** `approaching` is defined as a **configurable percentage of the SLA window elapsed** (e.g. 80%), which **scales per-tier automatically** (80% of 7d vs 80% of 90d). Chosen over a fixed lead-time window so long moderate windows get a proportionate warning.
- **D-03:** Findings with a **NULL `risk_exposure_score`** fall back to the existing **severity-keyed** SLA until they are scored. The severity path is retained specifically as this fallback (see D-08). — **Reversibility:** costly — removing the fallback later means guaranteeing every finding is scored before SLA runs, which touches the backfill ordering.

### Escalation Channels
- **D-04:** Build **all four channels via webhooks + existing SMTP**: Slack incoming webhook, Microsoft Teams incoming webhook, PagerDuty Events API, and reuse `email.py` (SMTP). **No OAuth apps** — webhook/API-key config only. Channel-specific payload formatting per channel.
- **D-05:** **Per-transition-type routing.** The tenant maps each transition type independently: `approaching → [zero-or-more channels]`, `breached → [zero-or-more channels]` (e.g. approaching → Slack; breach → Slack + PagerDuty).
- **D-06:** **Configurable tier floor** for escalation. Admin sets a minimum tier that escalates (e.g. "high + critical escalate; moderate tracks state silently but does not page"). Prevents alert fatigue on 90d moderate windows. All tiers still *track* state and show a badge; the floor only gates *escalation firing*.

### Transition Tracking & "Exactly Once"
- **D-07:** A new **escalation-event table** records each `(finding_id, from_state, to_state, channel, fired_at, tenant_id)`. Firing is gated on "no row exists for this (finding, transition, channel) yet" → clean once-only semantics and a **user-visible, auditable escalation history**. Every fire also goes through the fail-closed `audit()` path ([audit.py:143](../../../backend/app/audit.py#L143)). — **Reversibility:** one-way — introduces a new table via Alembic migration; dropping it later loses escalation history.

### Old-SLA Coexistence
- **D-08:** **Tier engine owns state; keep `sla_breached` as a derived mirror.** The new engine is the source of truth for state + due dates. `Vulnerability.sla_breached` (boolean) is kept but written as a *derived mirror* so already-shipped consumers (tickets `SlaPill`, metrics, dashboard) don't break. The existing in-app breach notification in [alerts.py](../../../backend/app/notifications/alerts.py) `_check_sla_breaches` becomes the **in-app twin of the breach escalation** — one breach yields one escalation event across channels + in-app, **not two separate breach signals**. Reconcile so the scheduler's old `check_sla_breaches` and the new engine do not double-fire.

### MTTR Capture
- **D-09:** On remediation, write a **remediation-event row** capturing the **tier-at-remediation** (final risk tier) + duration (`first_detected_at → remediated_at`). MTTR is a **queryable aggregate over those rows**, grouped by tier. Chosen tier-at-remediation (over tier-at-detection) so MTTR reflects the finding's final assessed risk. Durable history that Phase 42/43 consume directly. — **Reversibility:** one-way — new table via migration.

### Admin UI (UI hint: yes)
- **D-10:** New **"SLA & Escalation" pane** in the existing `/settings` sidebar-of-categories (RBAC-gated to admin/owner). Exposes the **full policy**: per-tier SLA days + the approaching % threshold, channel config (webhook URLs / API keys + per-transition routing + tier floor). Follows the established `SettingsSidebarShell` + `SaveBar` + `useDirtyState` pattern from Phase 14.
- **D-11:** Live SLA state renders on the **finding row and drill panel**. Reuse/extend the existing `SlaPill` primitive (Phase 13, tickets) for the on-track/approaching/breached visual language rather than inventing a new component.

### Post-Research Decisions (resolved 2026-08-13 from RESEARCH.md open questions)
- **D-12:** **No SLA below the MEDIUM tier floor** (`risk_exposure_score < 20`). Such findings are always `on-track`, carry no due date, and never escalate. The policy stays at three tiers (critical/high/moderate) — do **not** add a 4th "low" tier. (Resolves RESEARCH Open Question #1.) The D-03 severity fallback mapping follows suit: CRITICAL→critical, HIGH→high, MEDIUM/LOW/INFO→moderate (small explicit tested lookup; resolves Open Question #2).
- **D-13:** **PagerDuty fires on approaching/breach transitions only** (matches D-07 exactly-once scope). Do **not** send an `event_action=resolve` on remediation/un-breach this phase. **Document the limitation explicitly** in the admin pane + code (PagerDuty incidents require manual resolution). (Resolves RESEARCH Open Question #3.)
- **D-14:** **New channel secrets are Fernet-encrypted at rest** via the existing `app/encryption.py` `encrypt_value`/`decrypt_value` (as `ConnectorConfig.credentials` already does), plus **mask-on-read** so webhook URLs / routing keys never round-trip to the browser in plaintext. This does **not** retroactively re-encrypt the pre-existing `smtp_config.password` (out of scope). (Resolves RESEARCH Open Question #6.)
- **D-15 (fact, not a choice):** The classic Office 365 "Incoming Webhook" connector (MessageCard) is being retired — new connectors can no longer be created (Microsoft Learn, 2026-08-03). The Teams channel targets the **Workflows app** (`webhook.office.com` URL) which still accepts a simple JSON POST; the wire pattern ("paste webhook URL, POST JSON") matches the Slack channel. Admin-pane setup copy must describe the Workflows flow, not the retired connector.

### Claude's Discretion
- Exact schema/column names, migration structure, and whether the escalation-event + remediation-event tables share infrastructure.
- Whether to centralize the 6 `REMEDIATED` write sites behind one `mark_vulnerability_remediated()` helper (research recommends centralize) vs. edit in place (RESEARCH Open Question #4).
- Whether to recompute all ticket SLA groups every tick vs. only affected groups (research recommends start-simple/recompute-all; RESEARCH Open Question #5).
- Where in the scheduler loop the transition-detection + escalation-firing runs (currently SLA check runs every 60s tick — [scheduler.py:314](../../../backend/app/connectors/scheduler.py#L314)).
- Webhook payload shapes and per-channel formatting (following each vendor's incoming-webhook / Events API contract).
- The default approaching-% value (80% is illustrative).
- Retry/failure semantics for a channel POST that fails (audit + surface, don't block the transition record).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Roadmap
- `.planning/REQUIREMENTS.md` §SLA-01..04 — the four locked requirements this phase satisfies
- `.planning/ROADMAP.md` → "Phase 36" — goal + 4 success criteria (source of truth for scope)

### v4.0 Risk Model (shipped — consume, never re-derive)
- `backend/app/assets/risk_score.py` §L56-L61 — `RISK_SCORE_TIER_CRITICAL=80 / HIGH=50 / MEDIUM=20` tier boundaries the SLA policy keys off
- `backend/app/vulnerabilities/risk_exposure_service.py` — how `risk_exposure_score` is computed (the value the tier engine reads)
- `backend/app/vulnerabilities/models.py` §L87-L101 — `risk_exposure_score`, `risk_model_version`, `status`, `first_detected_at`, `remediated_at`, `sla_due_at`, `sla_breached` columns
- `backend/app/vulnerabilities/risk_cutover_service.py` — why the cutover flag is default-OFF and why SLA can read the raw score anyway

### Existing SLA machinery to replace/reconcile
- `backend/app/vulnerabilities/sla_service.py` — the severity-keyed engine being replaced; keep its severity path as the NULL-score fallback (D-03)
- `backend/app/connectors/scheduler.py` §L314-L328 — where old SLA backfill + breach-check run each tick; new engine slots in here
- `backend/app/notifications/alerts.py` `_check_sla_breaches` — existing in-app breach notification; becomes the in-app twin of breach escalation (D-08)
- `backend/app/tenants/models.py` §L41 — `Tenant.sla_config` JSONB (extend for tier policy + channel/routing config)

### Infrastructure to reuse
- `backend/app/audit.py` §L143 — fail-closed `audit()` for every escalation (D-07)
- `backend/app/email.py` — existing SMTP path (the email channel)
- `backend/app/notifications/service.py` — `create_notification` for the in-app twin

### Frontend
- `.claude/skills/sketch-findings-getvul/` — design system (severity/SLA/status visual language, state patterns) — MUST follow
- Phase 13 `SlaPill` primitive + Phase 14 `SettingsSidebarShell`/`SaveBar`/`useDirtyState` — reuse for D-10/D-11 (locate in `frontend/` during research)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`SlaPill` primitive** (Phase 13, tickets): existing on-track/at-risk/breached pill — extend to the 3-state on-track/approaching/breached vocabulary for finding rows + drill panel (D-11).
- **`SettingsSidebarShell` + `SaveBar` + `useDirtyState`** (Phase 14): the settings-pane pattern for the new "SLA & Escalation" pane (D-10).
- **`audit()`** ([audit.py:143](../../../backend/app/audit.py#L143)): fail-closed audit; each escalation fire audits through it (D-07).
- **`create_notification`** ([notifications/service.py](../../../backend/app/notifications/service.py)): in-app twin of breach escalation.
- **`email.py`**: existing SMTP → the email escalation channel (no new integration needed).
- **`get_sla_days` / severity policy** ([sla_service.py](../../../backend/app/vulnerabilities/sla_service.py)): retained as the NULL-score fallback (D-03).

### Established Patterns
- **Scheduler tick model**: SLA check already runs every 60s loop over active tenants ([scheduler.py:314](../../../backend/app/connectors/scheduler.py#L314)). Transition detection + escalation firing extend this loop, not a new scheduler.
- **Tenant JSONB config**: `sla_config`, `smtp_config`, `syslog_config` all live as per-tenant JSONB on `Tenant` — the tier policy + channel/routing config follow this precedent.
- **Shadow-then-cutover discipline** (v4.0): `risk_exposure_score` is computed for all findings regardless of the cutover flag — the SLA engine reads it directly.
- **Alembic migrations**: 24+ existing migrations; two new tables (escalation-event, remediation-event) follow the established migration flow.

### Integration Points
- **Scheduler loop** ([scheduler.py:314](../../../backend/app/connectors/scheduler.py#L314)) — new transition/escalation logic hooks here; must reconcile with the old `check_sla_breaches` to avoid double-firing (D-08).
- **`Vulnerability.sla_breached`** — written as a derived mirror so tickets/metrics/dashboard consumers keep working (D-08).
- **`Tenant.sla_config`** — extended to hold tier policy + approaching % + channel config + per-transition routing + tier floor.
- **Remediation status change** (`status → REMEDIATED`, `remediated_at` set) — the trigger point for writing an MTTR remediation-event row (D-09).

</code_context>

<specifics>
## Specific Ideas

- Default policy values from the roadmap: critical 7d / high 30d / moderate 90d.
- Approaching threshold as a % (80% illustrative) that scales per-tier.
- Escalation routing example the user endorsed: approaching → Slack; breach → Slack + PagerDuty.
- Tier-floor example: "high + critical escalate; moderate tracks state silently."
- One breach = one escalation event fanned across configured channels + one in-app notification — never two independent breach signals.

</specifics>

<deferred>
## Deferred Ideas

- **Richer channel routing UI / digests** — deferred to **Phase 40** (Proactive Alerting & Digests), which depends on this phase's SLA breach/approaching states.
- **OAuth-based channel apps** (full Slack/Teams apps vs incoming webhooks) — out of scope; webhook config is sufficient now.
- **Two-way remediation verification** (confirming a ticket actually closed the finding) — **Phase 37**.
- **MTTR trend/burndown visualization** — **Phase 42**; this phase only *captures* the MTTR-by-tier data.
- **Executive/compliance SLA reporting** — **Phase 43**.

None of these were scope creep into Phase 36 — discussion stayed within the four success criteria.

</deferred>

---

*Phase: 36-remediation-sla-engine-escalation*
*Context gathered: 2026-08-13*
