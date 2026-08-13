# Phase 36: Remediation SLA Engine & Escalation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-13
**Phase:** 36-remediation-sla-engine-escalation
**Areas discussed:** SLA state model, Escalation channels, Transition tracking, MTTR capture, Old-SLA coexistence, Escalation routing, Escalation scope, Admin UI

---

## SLA State Model (tier mapping, "approaching", NULL-score fallback)

| Option | Description | Selected |
|--------|-------------|----------|
| % of window + score fallback | 'Approaching' = configurable % of SLA window elapsed, scaling per-tier; NULL score → severity fallback | ✓ |
| Fixed lead-time window | 'Approaching' = fixed lead time before due, same for all tiers | |
| Absolute per-tier config | Admin sets both SLA days AND approaching-lead-days per tier | |

**User's choice:** % of window + score fallback
**Notes:** Self-scaling across the 7d→90d spread; severity-keyed SLA retained specifically as the fallback for un-scored findings. Keys off raw `risk_exposure_score`, independent of the default-OFF cutover flag.

---

## Escalation Channels (which to build, how configured)

| Option | Description | Selected |
|--------|-------------|----------|
| Webhook-based, all four | Slack + Teams incoming webhooks + PagerDuty Events API + existing SMTP; no OAuth apps | ✓ |
| Email + one webhook now | Email + Slack now; stub Teams/PagerDuty | |
| Generic webhook + email | One generic outbound webhook + email | |

**User's choice:** Webhook-based, all four
**Notes:** Covers all four SLA-03 channels with least integration weight; channel-specific payload formatting per vendor.

---

## Transition Tracking ("exactly once", history visibility)

| Option | Description | Selected |
|--------|-------------|----------|
| Escalation-event table | Row per (finding, from_state, to_state, channel, fired_at); once-only via row absence; user-visible history | ✓ |
| State columns on Vulnerability | sla_state + last_escalated_state columns; fire when current != last | |

**User's choice:** Escalation-event table
**Notes:** Gives auditable, user-visible escalation history plus clean once-only semantics. New table via Alembic (one-way).

---

## MTTR Capture (tier attribution, storage)

| Option | Description | Selected |
|--------|-------------|----------|
| Tier-at-remediation, event row | Remediation-event row with final tier + duration; MTTR = aggregate | ✓ |
| Tier-at-detection, event row | Same row, attribute to tier when first detected | |
| Compute-on-read from columns | Derive MTTR at query time; no event table | |

**User's choice:** Tier-at-remediation, event row
**Notes:** MTTR reflects the finding's final assessed risk; durable history for Phases 42/43.

---

## Old-SLA Coexistence

| Option | Description | Selected |
|--------|-------------|----------|
| Tier engine owns state; keep boolean derived | New engine is source of truth; `sla_breached` kept as derived mirror; old in-app breach becomes escalation's in-app twin | ✓ |
| Rip out severity SLA entirely | Delete severity path + boolean; migrate all consumers | |
| Parallel, new engine additive | Leave old path running; tier engine additive | |

**User's choice:** Tier engine owns state; keep boolean derived
**Notes:** Prevents breakage of shipped consumers (tickets SlaPill, metrics, dashboard); one breach = one escalation across channels + in-app, never two signals.

---

## Escalation Routing (approaching vs breach)

| Option | Description | Selected |
|--------|-------------|----------|
| Per-transition-type routing | Tenant maps approaching → [channels], breached → [channels] independently | ✓ |
| Single channel set, both fire | One channel set; both transitions fire to all | |

**User's choice:** Per-transition-type routing
**Notes:** Example endorsed — approaching → Slack; breach → Slack + PagerDuty.

---

## Escalation Scope (which tiers escalate)

| Option | Description | Selected |
|--------|-------------|----------|
| Configurable tier floor | Admin sets minimum tier that escalates; lower tiers track state silently | ✓ |
| All tracked tiers escalate | Every policy tier escalates | |

**User's choice:** Configurable tier floor
**Notes:** Prevents alert fatigue on 90d moderate windows; all tiers still show a state badge — the floor only gates escalation firing.

---

## Admin UI

| Option | Description | Selected |
|--------|-------------|----------|
| New Settings pane, full policy | Dedicated "SLA & Escalation" pane in /settings; per-tier days + approaching % + channel config + routing + floor | ✓ |
| Extend existing SLA settings | Grow current SLA config UI in place | |
| Policy now, channels later screen | Policy editor now; richer channel UI deferred to Phase 40 | |

**User's choice:** New Settings pane, full policy
**Notes:** Follows the Phase 14 SettingsSidebarShell + SaveBar + useDirtyState pattern, RBAC-gated to admin/owner.

---

## Claude's Discretion

- Schema/column names, migration structure, shared infra between the two new tables.
- Exact placement of transition-detection + escalation-firing in the 60s scheduler loop.
- Per-channel webhook payload shapes.
- Default approaching-% value.
- Retry/failure semantics for a failed channel POST (audit + surface, don't block the transition record).

## Deferred Ideas

- Richer channel routing UI / digests → Phase 40.
- OAuth-based channel apps (vs incoming webhooks) → out of scope.
- Two-way remediation verification → Phase 37.
- MTTR trend/burndown visualization → Phase 42.
- Executive/compliance SLA reporting → Phase 43.
