# Roadmap: GetVul

## Overview

GetVul is a unified vulnerability-triage platform: one dashboard correlates the same CVE-on-host across
multiple scanners, identifies the asset's owner via IdP/MDM/HR, scores and explains real risk exposure,
and ships a Jira/Asana/GitHub ticket — without opening a scanner console. All milestones through **v4.0**
are shipped and archived; see [MILESTONES.md](MILESTONES.md) for the full log and `.planning/milestones/`
for per-milestone detail (roadmap + requirements + audit + archived phase dirs).

**Current milestone: v5.0 — Close the Loop: Remediation Orchestration & Assurance.** v4.0 solved *seeing
and deciding* (correlation, enrichment, a deterministic risk-exposure score, source-aware provenance).
v5.0 closes the loop downstream of that score: route findings to owners, drive them to fixed under
risk-based SLAs with automatic escalation, verify the fix on rescan, orchestrate bulk campaigns, govern
exceptions/risk-acceptance, alert proactively on new KEV/EPSS matches, find coverage blind spots, chart
risk-trend/burndown, produce executive + compliance reporting, answer natural-language questions
(BYOK), and expose it all through a public API/webhooks/SDK. Continues phase numbering from Phase 35
(last shipped phase, v4.0).

## Milestones

- ✅ **v1.0 Production Readiness** — Phases 1–8 (SHIPPED 2026-07-14)
- ✅ **v2.0 UI/UX Redesign** — Phases 9–15 (SHIPPED 2026-06-30) — [archive](milestones/v2.0-ROADMAP.md)
- ✅ **v2.1 Polish & Tech Debt** — BL-01..05 (SHIPPED 2026-07-15)
- ✅ **v2.2 Deferred UI Features** — Phases 16–22 (SHIPPED 2026-07-22) — [archive](milestones/v2.2-ROADMAP.md)
- ✅ **v3.0 AI-Assisted Triage ("Triage Copilot")** — Phases 23–29 (SHIPPED 2026-08-04) — [archive](milestones/v3.0-ROADMAP.md)
- ✅ **v4.0 Enriched Risk Exposure & Source-Aware Triage** — Phases 30–35 (SHIPPED 2026-08-13) — [archive](milestones/v4.0-ROADMAP.md)
- 🚧 **v5.0 Close the Loop — Remediation Orchestration & Assurance** — Phases 36–45 (IN PROGRESS, started 2026-08-13)

## Phases

**Phase Numbering:**

- Integer phases (36, 37, 38...): Planned milestone work
- Decimal phases (36.1, 36.2): Urgent insertions (marked with INSERTED)

<details>
<summary>✅ v4.0 Enriched Risk Exposure & Source-Aware Triage (Phases 30–35) — SHIPPED 2026-08-13</summary>

- [x] Phase 30: Correlation Schema Fix (2/2 plans) — completed 2026-08-05
- [x] Phase 31: Connector Enrichment Rewrite (5/5 plans) — completed 2026-08-10
- [x] Phase 32: Asset Exposure Context (5/5 plans) — completed 2026-08-11
- [x] Phase 33: Risk-Exposure Model Definition (4/4 plans) — completed 2026-08-11
- [x] Phase 34: Historical Recompute & Consumer Cutover (5/5 plans) — completed 2026-08-12
- [x] Phase 35: Source-Aware Filtering & Provenance Badges (5/5 plans) — completed 2026-08-13

33/33 v1 requirements (CORR/ENRICH/EXPO/RISK/SRC) complete. Audit: [v4.0-MILESTONE-AUDIT.md](milestones/v4.0-MILESTONE-AUDIT.md)
(passed, override_closeout — accepted live-validation debt, environment-driven). Full detail:
[v4.0-ROADMAP.md](milestones/v4.0-ROADMAP.md).

</details>

Earlier milestones (v1.0–v3.0) are archived under `.planning/milestones/`.

**v5.0 Close the Loop — Remediation Orchestration & Assurance (IN PROGRESS — Phases 36–45):**

- [ ] **Phase 36: Remediation SLA Engine & Escalation** — Risk-tier SLA policy, live SLA state per finding, auto-escalation, MTTR-by-tier
- [ ] **Phase 37: Two-Way Ticket Sync & Remediation Verification** — Bi-directional ticket status sync + rescan-verified auto-close + reopen guard
- [ ] **Phase 38: Remediation Campaigns** — Bulk-group findings by shared fix, bulk ticket create/assign, live campaign progress + MTTR
- [ ] **Phase 39: Exception & Risk-Acceptance Workflow** — First-class false-positive/accept-risk with justification, approver, scope, mandatory expiry
- [ ] **Phase 40: Proactive Alerting & Digests** — New-KEV/high-EPSS targeted alerts + scheduled owner/team digests
- [ ] **Phase 41: Coverage & Blind-Spot Detection** — Reconcile authoritative inventory vs. scanner-seen assets; per-connector coverage %
- [ ] **Phase 42: Risk Trend Analytics & Burndown** — Trend lines, backlog aging/burndown, version-boundary-aware
- [ ] **Phase 43: Executive & Compliance Reporting** — Exec/board PDF, role-scoped dashboards, framework-control compliance view
- [ ] **Phase 44: Natural-Language Query Assistant** — BYOK plain-English Q&A over tenant data, safe-schema constrained
- [ ] **Phase 45: Public API, Webhooks & SDK** — Tenant-scoped REST API, signed event webhooks, OpenAPI spec + SDK

## Phase Details

### Phase 36: Remediation SLA Engine & Escalation

**Goal**: Every open finding carries a live, tenant-configurable SLA state driven by its v4.0 risk tier, escalates automatically to the right channel exactly once per state transition, and accumulates MTTR-by-tier data for later reporting — replacing today's flat severity-keyed SLA with a real engine.
**Depends on**: Nothing (first phase of v5.0; extends the v4.0 risk-exposure model, already shipped — never re-derives it)
**Requirements**: SLA-01, SLA-02, SLA-03, SLA-04
**Success Criteria** (what must be TRUE):

  1. A tenant-configurable, risk-tier-keyed SLA policy exists (default critical 7d / high 30d / moderate 90d), computed off the v4.0 risk-exposure tier, editable on an admin settings page
  2. Every open finding shows a live SLA state (on-track / approaching / breached) derived from that policy, visible on the finding row and drill panel
  3. An approaching-or-breach state transition fires the tenant-configured escalation channel (Slack / Microsoft Teams / email / PagerDuty) exactly once per transition, and every escalation is audited
  4. MTTR is captured per risk tier and is queryable (feeds Phase 42 trend + Phase 43 reporting)

**Plans**: 6/6 plans executed
**Wave 1**

- [x] 36-01-PLAN.md — LEAD TRACER: tier-SLA engine + live SLA state on the finding row (SLA-01/02)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 36-02-PLAN.md — Escalation channel infra: escalation-event table + Slack/Teams/PagerDuty/email senders (SLA-03)
- [x] 36-05-PLAN.md — SLA policy + channel-config settings backend: Fernet + mask + validation + RBAC + audit (SLA-01/03)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 36-03-PLAN.md — Escalation dispatch: exactly-once transition firing + D-08 reconcile + history endpoint (SLA-03)

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 36-04-PLAN.md — MTTR capture: remediation-event table + mark_vulnerability_remediated helper + MTTR-by-tier (SLA-04)
- [x] 36-06-PLAN.md — Frontend: SLA & Escalation admin pane + drill-panel SLA pill + escalation history (SLA-01/02/03) *(committed + live-verified 2026-08-14; SLA-03 live webhook delivery is the one open manual gate — see 36-VERIFICATION.md addendum)*

**UI hint**: yes

### Phase 37: Two-Way Ticket Sync & Remediation Verification

**Goal**: Ticket state stops being one-way (GetVul → Jira/Asana/GitHub only); a fix is verified by the scanner itself re-scanning clean, not by a human remembering to close the loop.
**Depends on**: Nothing (independent of Phase 36; extends the existing ticketing connectors)
**Requirements**: SYNC-01, SYNC-02, SYNC-03, SYNC-04
**Success Criteria** (what must be TRUE):

  1. A ticket status change in Jira, Asana, or GitHub writes back onto the linked GetVul finding without any manual action
  2. A finding absent from N consecutive post-fix scanner syncs auto-closes as rescan-verified, with a full audit trail of the auto-close decision
  3. A later recurrence of an auto-closed finding reopens it rather than silently creating a duplicate finding/ticket
  4. A connector or provider API outage never loses sync data — failed syncs retry, and the last-successful-sync state is surfaced per connector

**Plans**: TBD

### Phase 38: Remediation Campaigns

**Goal**: An analyst can act on a whole class of findings at once — group by shared fix across every affected asset/owner, bulk-create/assign tickets respecting existing routing, and watch the campaign burn down live — instead of ticketing one finding at a time.
**Depends on**: Nothing new (independent; builds on GetVul's existing cross-asset-by-CVE grouping and owner-routing logic)
**Requirements**: CAMP-01, CAMP-02, CAMP-03, CAMP-04
**Success Criteria** (what must be TRUE):

  1. An analyst groups findings sharing a fix (CVE / patch / product) across multiple assets and owners into a single campaign in one action, from a dedicated campaign view
  2. Bulk ticket create/assign for a campaign respects each finding's existing owner routing (no re-derivation, no owner overrides silently dropped)
  3. Per-campaign progress (open / in-progress / done, % remediated) and campaign MTTR update live as linked tickets/findings change
  4. Every campaign action (create, bulk-assign, close) is audited

**Plans**: TBD
**UI hint**: yes

### Phase 39: Exception & Risk-Acceptance Workflow

**Goal**: False-positive and accept-risk decisions become first-class, governed records — not an ad-hoc suppress flag — with a mandatory expiry so nothing is silently ignored forever.
**Depends on**: Nothing new (independent; extends the existing per-asset "ignored" / exposure-override precedent from v4.0)
**Requirements**: EXC-01, EXC-02, EXC-03, EXC-04
**Success Criteria** (what must be TRUE):

  1. An analyst can mark a finding/asset/asset-group false-positive or accept-risk via a form requiring justification, an approver, and an explicit scope
  2. An accepted-risk item is excluded from active queues, SLA timers, and dashboards until its mandatory expiry date — never permanently silenced
  3. Every exception records who/why/scope/expiry as a tenant-scoped audit event
  4. An expired exception automatically resurfaces into the active queue with no manual re-trigger

**Plans**: TBD
**UI hint**: yes

### Phase 40: Proactive Alerting & Digests

**Goal**: Analysts and owners learn about a new critical exposure or a looming SLA breach from GetVul pushing to them, not from opening the dashboard and finding out late.
**Depends on**: Phase 36 (ALERT-02's due/breaching digest content reads the SLA state machine Phase 36 introduces); also extends the v4.0 EPSS/KEV enrichment feeds (already shipped) and the existing notification primitives
**Requirements**: ALERT-01, ALERT-02, ALERT-03
**Success Criteria** (what must be TRUE):

  1. A newly KEV-listed or high-EPSS CVE that matches one of the tenant's own assets fires a targeted alert to the right channel
  2. Scheduled per-owner / per-team digests (Slack / Teams / email) of due, breaching, and newly-critical findings deliver on the in-process scheduler, no new infra
  3. Alert rules and delivery channels are tenant-configurable on a settings page and every configuration change is audited

**Plans**: TBD
**UI hint**: yes

### Phase 41: Coverage & Blind-Spot Detection

**Goal**: GetVul tells a tenant what it doesn't know — assets the IdP/MDM/HR/CMDB knows about but no scanner has ever touched — instead of only reporting on what scanners already found.
**Depends on**: Nothing new (independent; extends GetVul's existing IdP/MDM/HR asset-enrichment data)
**Requirements**: COV-01, COV-02, COV-03
**Success Criteria** (what must be TRUE):

  1. A coverage view reconciles the authoritative inventory (IdP / MDM / HR / CMDB) against scanner-seen assets and lists assets with zero findings or no last-seen date
  2. Per-connector coverage percentage and stale-source gaps (a connector that hasn't reported in N days) are visible
  3. A newly-discovered unmanaged asset can be routed to an owner directly from the coverage view

**Plans**: TBD
**UI hint**: yes

### Phase 42: Risk Trend Analytics & Burndown

**Goal**: A tenant can see whether its risk posture is actually improving over time and how fast the backlog is burning down — not just today's snapshot.
**Depends on**: Nothing new (independent; extends v4.0 Phase 34's historical recompute, already shipped, for a clean score history)
**Requirements**: TREND-01, TREND-02, TREND-03
**Success Criteria** (what must be TRUE):

  1. Tenant / team / asset-group risk-exposure trend lines render on a dashboard over a selectable time window
  2. Backlog aging (open findings by age × severity) and a burndown rate are visible on the same dashboard
  3. Trends annotate risk-model version boundaries rather than blending across them — a v4.0 model version change never produces a false cliff or false improvement

**Plans**: TBD
**UI hint**: yes

### Phase 43: Executive & Compliance Reporting

**Goal**: A CISO or compliance owner can prove the program is working — and where findings sit against a named framework — without an analyst hand-building a slide deck.
**Depends on**: Phase 36 (MTTR-by-tier + SLA compliance data) and Phase 42 (risk trend + burndown data) — the capstone reporting layer over both
**Requirements**: RPT-01, RPT-02, RPT-03
**Success Criteria** (what must be TRUE):

  1. An exec/board PDF exports risk trend + MTTR-by-tier + SLA compliance for a selected period
  2. Role-scoped dashboards (analyst / IT-ops / compliance / leadership) render, each tenant-scoped and each showing only what that role needs
  3. A compliance view maps findings to framework controls (SOC 2 / ISO 27001 / PCI DSS / NIST CSF)

**Plans**: TBD
**UI hint**: yes

### Phase 44: Natural-Language Query Assistant

**Goal**: An analyst can ask a plain-English question over their own vuln/asset/ticket data and get a grounded, tenant-scoped answer with the underlying result set shown — reusing the v3.0 BYOK AI scaffold rather than building a second AI stack.
**Depends on**: Nothing hard (extends the v3.0 AI scaffold, already shipped); sequenced late in v5.0 so answers can meaningfully reference the SLA/exception/campaign/coverage data model Phases 36–41 introduce
**Requirements**: NLQ-01, NLQ-02, NLQ-03
**Success Criteria** (what must be TRUE):

  1. A plain-English question over the tenant's own vuln/asset/ticket data returns a grounded, tenant-scoped answer through a query interface, with the underlying result set shown alongside the answer
  2. Queries are constrained to a safe, predefined schema — no free-form SQL generation, no injection path, no cross-tenant reach
  3. The assistant is inert (a "configure AI" state) until the tenant configures their own Anthropic key (BYOK), reusing the v3.0 scaffold and guardrails verbatim — no shared/fallback key

**Plans**: TBD
**UI hint**: yes

### Phase 45: Public API, Webhooks & SDK

**Goal**: A SOAR/ITSM/data-pipeline integrator can read and write GetVul's core objects and subscribe to its key events without opening the dashboard — the capstone platform layer over everything v5.0 ships.
**Depends on**: Phases 36–39 (the event surface — SLA breach, ticket sync, exception grant, campaign action — that the webhook payloads and write API expose)
**Requirements**: API-01, API-02, API-03
**Success Criteria** (what must be TRUE):

  1. A tenant-scoped API key is RBAC-gated, rate-limited, and every call is audited; the API covers read + write for findings, tickets, exceptions, and campaigns, with keys managed from an admin settings page
  2. Signed event webhooks (finding created / SLA breached / ticket synced / exception granted) deliver with retry on failure
  3. A published OpenAPI spec and a minimal client SDK cover the core read/write surface

**Plans**: TBD

## Progress

**Execution Order:** Phase 36 is the first v5.0 phase; Phase 37 can run independently/parallel with 36 (no shared files). Phases 38, 39, 41, 42 are each independent of 36/37/one another. Phase 40 requires Phase 36 (SLA state feeds its digest content). Phase 43 requires Phase 36 + Phase 42. Phase 44 has no hard v5.0-internal dependency but is sequenced after 36–41 for maximum answer coverage. Phase 45 requires Phases 36–39 (event surface).

| Phase | Plans Complete | Status | Completed |
|-------|-----------------|--------|-----------|
| 36. Remediation SLA Engine & Escalation | 5/6 | In Progress | - |
| 37. Two-Way Ticket Sync & Remediation Verification | 0/? | Not started | - |
| 38. Remediation Campaigns | 0/? | Not started | - |
| 39. Exception & Risk-Acceptance Workflow | 0/? | Not started | - |
| 40. Proactive Alerting & Digests | 0/? | Not started | - |
| 41. Coverage & Blind-Spot Detection | 0/? | Not started | - |
| 42. Risk Trend Analytics & Burndown | 0/? | Not started | - |
| 43. Executive & Compliance Reporting | 0/? | Not started | - |
| 44. Natural-Language Query Assistant | 0/? | Not started | - |
| 45. Public API, Webhooks & SDK | 0/? | Not started | - |

## Next

`/gsd-plan-phase 36`
