# Phase 40: Proactive Alerting & Digests - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-19
**Phase:** 40-proactive-alerting-digests
**Areas discussed:** ALERT-01 trigger & thresholds, Alert & digest routing, Digest schedule & content, Config surface & rules model, First-run cold-start, EPSS-crossing detection, Digest email format & depth, Owner-resolution fallback

---

## ALERT-01 Trigger & Thresholds

| Question | Options | Selected |
|----------|---------|----------|
| High-EPSS trigger | Tenant-overridable score threshold (default 0.5) / Percentile-based (≥95th) / KEV-only | Tenant-overridable threshold, default 0.5 |
| Fire model | Transition-only / Any current match deduped by age | Transition-only (fire once when newly qualifies) |
| Code path | Add distinct `_check_new_kev_epss` / Extend `_check_new_critical_vulns` | Add distinct `_check_new_kev_epss` |
| Granularity | Per (CVE, asset) / Per CVE tenant-wide | Per (CVE, asset) transition |

**Notes:** All recommended options chosen (→ D-01..D-04).

---

## Alert & Digest Routing

| Question | Options | Selected |
|----------|---------|----------|
| ALERT-01 "right channel" | Tenant channel + email to owner(s)/admins / Per-owner directory→channel map / Tenant-wide only | Tenant alert channel (Slack/Teams) + email to matched owner(s)/admins |
| Digest scope | Both per-owner & per-team / Per-owner only / Per-team only | Both (owner email + AssetGroup) |
| Channel reuse | Reuse Phase 36 credentials, independent routing / Separate dedicated config | Reuse credentials, independent enablement/routing |
| Digest channel split | Owner→email, team→shared Slack/Teams / Admin picks freely | Owner→email; team→shared Slack/Teams (email optional) |

**Notes:** All recommended options chosen (→ D-07..D-09). Owner-Slack DM routing ruled out — no data source for owner→channel mapping.

---

## Digest Schedule & Content

| Question | Options | Selected |
|----------|---------|----------|
| Cadence | Daily/weekly configurable, default daily / Fixed daily / Per-recipient | Tenant-configurable daily or weekly, default daily |
| Send timing | Configurable hour in tenant tz / Simple 24h gate | Configurable target hour in tenant timezone |
| Content sections | Due+breaching+newly-critical+expiring-exceptions / Only the three named | Include expiring-exceptions (closes Phase 39 deferral) |
| Empty digest | Suppress / Always send "all clear" | Suppress — send nothing |

**Notes:** → D-11..D-14. Expiring-exceptions section fulfills Phase 39 D-18's explicit deferral to Phase 40.

---

## Config Surface & Rules Model

| Question | Options | Selected |
|----------|---------|----------|
| Rules model | Fixed structured settings / Flexible rule builder | Fixed structured settings |
| Settings pane | New "Alerting & Digests" pane / Extend Phase 36 SLA pane | New dedicated pane |
| Storage & audit | Tenant JSONB + fail-closed audit() / Dedicated table | `alerting_config` JSONB + audit() |
| Exclusions & overlap | Exclude excepted/suppressed everywhere, push+digest overlap by design / Also dedup already-pushed | Exclude everywhere; overlap by design |

**Notes:** → D-16..D-21. Rule-builder rejected as over-engineering for 3 requirements.

---

## First-run Cold-start

| Question | Options | Selected |
|----------|---------|----------|
| First-run backlog | Seed baseline (mark current qualifiers already-alerted) / Fire full backlog / Time-box last N hours | Seed a baseline silently on first run |

**Notes:** → D-06. Prevents launch-day alert storm.

---

## EPSS-crossing Detection Mechanism

| Question | Options | Selected |
|----------|---------|----------|
| Detection | Per-tenant "already-alerted" guard table (cve, asset, trigger) / Snapshot prior values in feed job | Per-tenant guard table |

**Notes:** → D-05. Grounded by code reality: `repropagate_enrichment` overwrites `cisa_kev`/`epss_score` in place with no transition capture; feed job is tenant-agnostic so cannot honor per-tenant EPSS thresholds.

---

## Digest Email Format & Depth

| Question | Options | Selected |
|----------|---------|----------|
| Format & depth | HTML top-N + "and N more" + deep-links / Plaintext all findings / HTML uncapped | HTML, top-N per section with "and N more" + deep-links |

**Notes:** → D-15. Reuse `email.py`; bounded to avoid provider size limits.

---

## Owner-resolution Fallback

| Question | Options | Selected |
|----------|---------|----------|
| Unowned / multi-owner | No owner→admins+tenant channel; multi→all; no group→owner digest only / Skip unowned / Tenant channel only | Admins+tenant channel fallback; notify all owners; no-group→owner digest only |

**Notes:** → D-10. No exposure silently dropped.

## Claude's Discretion

- Guard-table schema/column names + whether it shares infra with Phase 36's escalation-event table
- `alerting_config` JSONB schema shape and exact defaults
- Scheduler-loop placement of `_check_new_kev_epss` + digest dispatch
- Per-channel digest payload formatting (reuse `dispatch_channel` builders vs. digest-specific)
- Top-N cap value + deep-link URL construction
- Channel POST retry/failure semantics (reuse Phase 36 retry+audit)
- Whether team-digest iteration skips empty AssetGroups

## Deferred Ideas

- Per-recipient (per-user) notification preferences — own phase, needs preference store
- Per-owner Slack/Teams DM routing — no owner→channel data source
- Generic rule-builder engine — rejected here, candidate for future "advanced alerting"
- PagerDuty for ALERT-01 (new-KEV/EPSS paging) — left as a routing option, not mandated
