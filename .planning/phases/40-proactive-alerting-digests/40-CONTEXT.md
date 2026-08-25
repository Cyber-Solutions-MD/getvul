# Phase 40: Proactive Alerting & Digests - Context

**Gathered:** 2026-08-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Make GetVul **push** critical exposure to people instead of waiting for them to open the dashboard. Three delivery surfaces:

1. **ALERT-01 — targeted real-time alert:** when a CVE **newly** becomes KEV-listed or **newly** crosses a high-EPSS threshold and matches one of the tenant's own assets, fire a targeted alert to the tenant alert channel + the matched asset's owner(s)/admins.
2. **ALERT-02 — scheduled digests:** per-owner and per-team (AssetGroup) digests of **due / breaching / newly-critical / expiring-exceptions** findings, delivered on the existing in-process scheduler (no new infra).
3. **ALERT-03 — tenant-configurable + audited:** alert rules (KEV toggle, EPSS threshold, digest cadence/send-time, channel routing) live on a new settings pane, stored per-tenant, every change audited.

This is a **how-to-implement** boundary — no new capabilities beyond ALERT-01..03. This phase is **mostly wiring existing primitives together**, not building new plumbing.

**Explicitly NOT this phase:**
- The v4.0 EPSS/KEV enrichment feeds themselves (shipped — consume, never re-derive).
- The Phase 36 SLA state machine / escalation firing (shipped — digests **read** SLA state, they do not replace real-time SLA escalation).
- A generic rule-builder engine (rejected in favor of fixed structured settings — see D-14).
- Per-user (per-recipient) notification preference store (cadence is tenant-level, not per-person).
- Coverage/blind-spot detection (Phase 41), trend analytics (Phase 42), executive reporting (Phase 43).

</domain>

<decisions>
## Implementation Decisions

### ALERT-01 — Trigger & Thresholds
- **D-01:** **High-EPSS = a tenant-overridable numeric `epss_score` threshold, default 0.5.** Admins tune it per tenant on the settings pane. Chosen over percentile-rank (harder to explain; depends on `epss_percentile` being reliably populated) and over KEV-only (would leave half of ALERT-01 unmet).
- **D-02:** **Transition-only firing.** Fire once when a CVE **newly** enters KEV **or newly** crosses the EPSS threshold — not on every current match each tick. No daily re-alerting on the same finding.
- **D-03:** **Add a distinct `_check_new_kev_epss` sibling check** in `run_alert_checks` — do NOT fold KEV/EPSS into the existing `_check_new_critical_vulns` (severity=CRITICAL / 2h-window). The trigger source, dedup key, and semantics differ ("newly qualifies for KEV/EPSS" ≠ "newly detected as CRITICAL"). Keeps the existing severity path untouched.
- **D-04:** **Alert granularity = per (CVE, asset) transition**, guarded once-only per `(tenant, cve, asset, trigger_type)`. One alert per affected asset so each owner learns of their own exposure; matches "matches one of the tenant's own assets."

### ALERT-01 — Detection Mechanism & Cold Start
- **D-05:** **Detection via a per-tenant "already-alerted" guard table** keyed `(tenant_id, cve_id, asset_id, trigger_type)`. Each tick: compute current qualifiers (`cisa_kev = true` OR `epss_score >= tenant_threshold`) matched to tenant assets, **subtract rows already in the guard**, fire on the remainder, then insert. One structure simultaneously delivers: the tenant-specific EPSS threshold, the once-only guard (D-04), and cold-start seeding (D-06). Chosen over snapshotting prior values inside the feed job because `repropagate_enrichment` is **tenant-agnostic** and cannot honor per-tenant EPSS thresholds, and coupling alerting to the feed pipeline is undesirable. — **Reversibility:** one-way — introduces a new table via Alembic migration; dropping it loses the alerted-history + reopens the double-fire window.
- **D-06:** **Seed a baseline on first run.** On the first alerting pass, record **all currently-qualifying** `(cve, asset)` pairs into the guard table **without firing**, so ALERT-01 only fires for genuine future transitions. Prevents a launch-day alert storm across the entire existing backlog. (Also applies whenever a tenant newly enables KEV/EPSS alerts or changes the EPSS threshold downward — treat newly-in-scope findings as baseline-seeded, not "new," unless the planner decides threshold-lowering should intentionally surface them; default = seed silently.)

**Reality correction (grounding for D-05):** `backend/app/connectors/enrichment_feeds.py::repropagate_enrichment` overwrites `vulnerabilities.cisa_kev` and `epss_score` **in place with NO prior-value capture** — the "flips both ways" comment means the recompute is bidirectional, NOT that it emits a "newly-added" event. There is **no ready-made newly-KEV transition to consume**; detection must maintain its own state (the D-05 guard table).

### Routing — Who Receives What, On Which Channel
- **D-07:** **ALERT-01 routes to the tenant alert channel (Slack/Teams webhook) + email to the matched asset's resolved owner(s) + admins.** Slack/Teams webhooks are channel-level (not per-person), so the shared alert channel gets the push while per-person email reaches the actual owner. Reflects the contact data we actually have (owner email from IdP/MDM/HR enrichment; webhooks are shared).
- **D-08:** **Digest recipient scope = both per-owner AND per-team.** Owner digests cover assets that person owns (owner email resolved from enrichment); team digests cover an AssetGroup's assets. Admin can enable either or both. Matches ALERT-02's "per-owner / per-team" wording directly.
- **D-09:** **Digest channel split: owner digests → email; team digests → the team's shared Slack/Teams channel (email optional).** Per-person email is the reliable per-owner channel; per-team posts to a shared channel. Avoids needing a per-owner Slack/Teams DM mapping that has no data source.
- **D-10:** **Owner-resolution fallback:** asset with **no resolved owner** → route to **admins + the tenant alert channel** (no exposure silently dropped); **multiple owners** → notify all of them; asset in **no AssetGroup** → covered by the per-owner digest only, simply absent from team digests. Rejected: skipping unowned assets (drops the riskiest shadow IT).

### ALERT-02 — Schedule & Content
- **D-11:** **Cadence = tenant-configurable daily or weekly, default daily.** No per-recipient cadence store this phase.
- **D-12:** **Send timing = configurable target hour in the tenant's timezone.** Each scheduler tick checks "past the target hour AND not yet sent this period." Chosen over the pure `_last_ticket_sync` 24h-gate (which drifts with process restarts and isn't tied to a business hour) so digests land at a predictable morning time. — **Reversibility:** reversible — timing logic is local to the digest dispatch block.
- **D-13:** **Digest sections = due + breaching + newly-critical + expiring-exceptions.** The three named in ALERT-02 plus an **expiring-exceptions** section — Phase 39 explicitly deferred that push (Slack/email/digest) to Phase 40, so folding it into the digest closes that loop. "breaching" reads Phase 36's SLA state; "expiring-exceptions" reads Phase 39's exception expiry.
- **D-14:** **Empty digests are suppressed** — send nothing when all sections are empty for a recipient. Avoids alert fatigue / "why did I get an empty email" churn. No "all clear" digest.
- **D-15:** **Digest format = HTML (reuse `email.py`), top-N per section (e.g. top 10 by risk) with an "and N more" line + deep-links back to the filtered dashboard view.** Keeps emails scannable and bounded; avoids provider size limits on large tenants. Rejected: plaintext-all and HTML-uncapped.

### ALERT-03 — Config Surface, Rules Model, Audit
- **D-16:** **Fixed structured settings, NOT a rule-builder.** Bounded, well-typed form: KEV-alert on/off, EPSS threshold, digest cadence + send-hour + timezone, per-type channel routing, per-owner/per-team enablement. Meets "tenant-configurable" and mirrors Phase 36's SLA config shape without over-engineering. A generic `when <condition> then notify <channel>` engine is explicitly out of scope.
- **D-17:** **New "Alerting & Digests" settings pane** in the `/settings` sidebar-of-categories (RBAC-gated admin/owner), using the established `SettingsSidebarShell` + `SaveBar` + `useDirtyState` pattern (Phase 14). Kept separate from Phase 36's already-dense "SLA & Escalation" pane.
- **D-18:** **Config stored in a new `alerting_config` JSONB key on `Tenant`** (following the `sla_config` / `smtp_config` / `syslog_config` precedent), every save routed through the fail-closed `audit()` path. Satisfies ALERT-03's "audited." — **Reversibility:** reversible — JSONB column addition, no data destruction.
- **D-19:** **Reuse Phase 36's channel credentials with independent enablement/routing.** One place configures Slack/Teams/SMTP webhooks (Phase 36's masked, Fernet-encrypted config); alerting/digests reference those credentials but have their own on/off + routing so they do NOT inherit SLA-escalation rules.

### Exclusions & Cross-Signal Overlap
- **D-20:** **Excepted/suppressed findings are excluded everywhere.** A finding with `status IN (SUPPRESSED, FALSE_POSITIVE)` OR an active exception (EXC-02, Phase 39) is excluded from ALERT-01 and from every digest section. Reuse the Phase 39 exclusion predicate — do not re-derive it.
- **D-21:** **Real-time push and digest may overlap by design.** A finding can appear in BOTH a real-time ALERT-01 push AND the next digest's newly-critical section — push = immediate signal, digest = daily state summary, intentionally distinct purposes. No dedup between the two (rejected: dropping already-pushed findings would make the digest an incomplete point-in-time summary). Likewise the digest's "breaching" section intentionally re-summarizes findings that Phase 36 already escalated in real time.

### Claude's Discretion
- Exact table/column names and migration structure for the D-05 guard table; whether it shares infrastructure with Phase 36's escalation-event table.
- Whether the guard table stores a `fired_at` for observability vs. bare existence rows.
- Exact `alerting_config` JSONB schema shape and default values (EPSS 0.5, cadence daily, send-hour illustrative).
- Where in `_scheduler_loop()` the digest dispatch and `_check_new_kev_epss` calls slot in (relative to the existing SLA pass + `run_alert_checks`).
- Per-channel payload formatting for the digest (reuse `escalation_channels.py` `dispatch_channel` builders vs. digest-specific formatting).
- The per-section top-N cap value and exact deep-link URL construction.
- Retry/failure semantics for a channel POST that fails (reuse Phase 36's `_post_json_with_retry` + audit; don't block the rest of the run).
- Whether "team" AssetGroup digests iterate all groups every tick vs. only groups with content.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Roadmap
- `.planning/REQUIREMENTS.md` §ALERT-01..03 — the three locked requirements this phase satisfies
- `.planning/ROADMAP.md` → "Phase 40: Proactive Alerting & Digests" — goal + 3 success criteria (source of truth for scope)

### Reuse — Real-time alert path (extend, don't rebuild)
- `backend/app/notifications/alerts.py` — `run_alert_checks` + `_check_new_critical_vulns` / `_check_sla_breaches` (now a no-op) / `_check_sync_failures` / `_check_risk_score_changes`; `_notification_exists` (dedup helper) + `_email_owners_and_admins`. ALERT-01 adds a sibling `_check_new_kev_epss` here (D-03).
- `backend/app/notifications/service.py` — `create_notification` for the in-app twin.
- `backend/app/email.py` — existing SMTP path; the email channel for alerts + owner digests (D-09/D-15).

### Reuse — Phase 36 channel + settings infrastructure (the biggest reuse)
- `backend/app/notifications/escalation_channels.py` — `dispatch_channel(channel, config, context)` fan-out for Slack / Teams / PagerDuty / email; `_post_json_with_retry`, per-channel payload builders. Reuse for ALERT-01 channel push + team digest posting (D-07/D-09/D-19).
- `.planning/phases/36-remediation-sla-engine-escalation/36-CONTEXT.md` — D-04/D-05/D-14/D-15 channel model, masked+Fernet-encrypted channel secrets, per-transition routing, Teams Workflows-app webhook reality. The alerting channel config reuses these credentials (D-19).
- `backend/app/encryption.py` — `encrypt_value`/`decrypt_value` (Fernet) + mask-on-read pattern for any new secret fields.

### Reuse — Scheduler (no new infra — SC2 requires "no new infra")
- `backend/app/connectors/scheduler.py` §L249-L352 — `_scheduler_loop()`; the SLA tier-engine pass (§L314), `run_alert_checks` call site, and the 24h-gate idiom (`_last_ticket_sync`, §L342-L352). Digest dispatch + `_check_new_kev_epss` slot into this loop (D-12).

### Consume — enrichment feed & risk model (never re-derive)
- `backend/app/connectors/enrichment_feeds.py` §L208-L266 — `refresh_enrichment_reference_data` + `repropagate_enrichment`; **overwrites `cisa_kev`/`epss_score` in place with NO transition capture** (grounds D-05). ALERT-01 must maintain its own alerted-state.
- `backend/app/vulnerabilities/models.py` — `cisa_kev`, `epss_score`, `epss_percentile`, `severity`, `status`, `first_detected_at`, `risk_exposure_score`, `sla_due_at`, `sla_breached` columns.
- `backend/app/assets/risk_score.py` §L56-L61 — `RISK_SCORE_TIER_*` bands (top-N-by-risk digest ordering, D-15).

### Consume — Phase 36 SLA state & Phase 39 exceptions (digest content)
- `.planning/phases/36-remediation-sla-engine-escalation/36-CONTEXT.md` + `backend/app/vulnerabilities/sla_tier_service.py` — SLA state (`on-track`/`approaching`/`breached`) for the digest's due/breaching sections.
- `.planning/phases/39-exception-risk-acceptance-workflow/39-CONTEXT.md` §D-18 — expiring-exception push explicitly deferred to Phase 40 (D-13); §exclusion predicate `status IN (SUPPRESSED, FALSE_POSITIVE) OR active exception` (D-20).

### Config & audit
- `backend/app/tenants/models.py` — `Tenant` JSONB config precedent (`sla_config`, `smtp_config`, `syslog_config`); new `alerting_config` follows suit (D-18).
- `backend/app/audit.py` §L143 — fail-closed `audit()` for every config change (D-18/ALERT-03).
- `backend/app/tenants/router.py` — existing settings save routes (e.g. `SlaEmailChannel`) as the pattern for the alerting-config save route.

### Frontend
- `.claude/skills/sketch-findings-getvul/` — design system (severity/SLA/status visual language, state patterns, copy voice) — MUST follow.
- Phase 14 `SettingsSidebarShell` / `SaveBar` / `useDirtyState` + Phase 36 "SLA & Escalation" pane — the closest analog for the new "Alerting & Digests" pane (D-17). Locate exact paths in `frontend/` during research.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`escalation_channels.dispatch_channel`** — multi-channel Slack/Teams/PagerDuty/email fan-out with retry; the delivery layer for ALERT-01 pushes and team-digest posts (D-07/D-09).
- **`run_alert_checks` + `_check_new_critical_vulns`** ([alerts.py](../../../backend/app/notifications/alerts.py)) — the every-tick alert scaffold; ALERT-01 adds `_check_new_kev_epss` beside it (D-03). `_notification_exists` + `_email_owners_and_admins` are directly reusable.
- **`email.py`** — SMTP; email channel for alerts + owner digests (no new integration).
- **Phase 36 channel config** — masked, Fernet-encrypted webhook/API-key storage + per-transition routing; alerting reuses the credentials (D-19).
- **`SettingsSidebarShell`/`SaveBar`/`useDirtyState`** (Phase 14/36) — the new "Alerting & Digests" pane (D-17).
- **`audit()`** ([audit.py:143](../../../backend/app/audit.py#L143)) — fail-closed audit for config changes (D-18).

### Established Patterns
- **Scheduler tick + 24h-gate idiom** (`_last_ticket_sync`, [scheduler.py:342](../../../backend/app/connectors/scheduler.py#L342)) — digests reuse the in-process scheduler; SC2 explicitly forbids new infra. Send-hour timing (D-12) refines the gate into a wall-clock check.
- **Tenant JSONB config** (`sla_config`/`smtp_config`/`syslog_config`) — `alerting_config` follows this precedent (D-18).
- **Alembic migrations** (24+ existing) — the D-05 guard table + `alerting_config` column follow the established flow.
- **Phase 39 exclusion predicate** — reused verbatim so excepted/suppressed findings never appear in alerts/digests (D-20).

### Integration Points
- **`_scheduler_loop()`** — `_check_new_kev_epss` + digest dispatch hook here (D-05/D-12), alongside the existing SLA pass and `run_alert_checks`.
- **`repropagate_enrichment`** — the value that ALERT-01 keys off is written here **without transition capture**; ALERT-01 owns its own alerted-state (D-05).
- **`Tenant.alerting_config`** — new JSONB holding thresholds/cadence/send-hour/routing/enablement.
- **New guard table** — `(tenant_id, cve_id, asset_id, trigger_type)` once-only alerted-state (D-05/D-06).

</code_context>

<specifics>
## Specific Ideas

- Default EPSS threshold **0.5** (D-01, tenant-overridable).
- Default cadence **daily** with a configurable morning **send-hour in tenant timezone** (D-11/D-12).
- Digest sections in order: **due, breaching, newly-critical, expiring-exceptions** (D-13).
- Digest per-section cap illustratively **top 10 by risk** + "and N more" + dashboard deep-link (D-15).
- Cold-start = **seed baseline silently** so day-one produces zero backlog alerts (D-06).

</specifics>

<deferred>
## Deferred Ideas

- **Per-recipient (per-user) notification preferences** — cadence/channel chosen per person rather than per tenant. Its own phase; needs a user-preference store.
- **Per-owner Slack/Teams DM routing** — requires an owner→channel/handle mapping with no current data source (IdP/MDM/HR give email, not Slack IDs). Revisit if a directory→chat mapping lands.
- **Generic rule-builder engine** (`when <condition> then notify <channel>`) — rejected for this phase (D-16) in favor of fixed settings; candidate for a later "advanced alerting" phase if demand appears.
- **PagerDuty for ALERT-01** — Phase 36 wired PagerDuty for SLA transitions; whether new-KEV/EPSS also pages is left as a channel-routing option, not a mandated behavior. Not expanded here.

</deferred>

---

*Phase: 40-proactive-alerting-digests*
*Context gathered: 2026-08-19*
