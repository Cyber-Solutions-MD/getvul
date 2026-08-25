# Requirements: GetVul v5.0 — Close the Loop: Remediation Orchestration & Assurance

> **ACTIVE** milestone requirements (started 2026-08-13, via `/gsd-new-milestone`). Companion:
> [v5.0-PROPOSAL.md](milestones/v5.0-PROPOSAL.md). Phase numbers finalized by the roadmapper below (36–45).
> The Traceability table is filled by the roadmap. All items `[ ]` Pending until executed.

**Started:** 2026-08-13 · **Phases:** 36–45 (continuing numbering from v4.0's Phase 35) · **Depends on:** v4.0 (shipped)

**Core Value:** A vuln-triage analyst opens one dashboard, sees the same CVE-on-host correlated
across scanners, identifies the asset's owner from IdP/MDM/HR, and ships a ticket — without opening
a scanner console. **v5.0 closes the loop: it routes findings to owners, drives them to fixed under
risk-based SLAs, verifies the fix, governs exceptions, and proves the program to leadership.**

## Foundational principles (carried forward)

- **v4.0 risk score is authoritative** — v5.0 acts on the deterministic, versioned risk-exposure
  score; it never re-derives it.
- **Lane discipline** — GetVul is a triage/ownership/orchestration layer on top of existing
  scanners. v5.0 adds **no** scanner, patch-deployer, or agent.
- **BYOK-only AI** — the NL query assistant uses the tenant's own Anthropic key and stays inert
  until configured (no shared/fallback key, tenant-scoped only).
- **Infra constraint** — single-VM Docker Compose + in-process asyncio scheduler only; no new infra.
- **Auditability** — every new mutating action (SLA policy change, exception/risk-acceptance,
  campaign action, API write) emits a tenant-scoped audit event.

## Proposed v1 requirements — all Pending

### Remediation SLA Engine & Escalation (SLA) — Phase 36

- [x] **SLA-01**: Risk-tier SLA policy (default critical 7d / high 30d / moderate 90d), tenant-configurable, computed off the v4.0 risk-exposure tier
- [x] **SLA-02**: Each open finding shows a live SLA state (on-track / approaching / breached) derived from that policy
- [ ] **SLA-03**: Approaching/breach transitions auto-escalate to a configured channel (Slack / Microsoft Teams / email / PagerDuty), fired exactly once per transition, audited *(code-complete + UI-verified; pending live webhook-delivery sign-off — 36-06 Task 3)*
- [x] **SLA-04**: MTTR is captured per risk tier and exposed for reporting (feeds RPT/TREND)

### Two-Way Ticket Sync & Remediation Verification (SYNC) — Phase 37

- [x] **SYNC-01**: Ticket status writes back from Jira / Asana / GitHub into the linked GetVul finding (bi-directional, not create-only)
- [x] **SYNC-02**: A finding absent from N consecutive post-fix scanner syncs auto-closes as rescan-verified, with an audit trail
- [x] **SYNC-03**: A recurrence after auto-close reopens the finding rather than silently creating a duplicate
- [x] **SYNC-04**: Sync is resilient to connector/API failure (retry, last-sync surfaced, no data loss)

### Remediation Campaigns (CAMP) — Phase 38

- [x] **CAMP-01**: Group findings by shared fix (CVE / patch / product) across multiple assets and owners into a campaign in one action
- [x] **CAMP-02**: Bulk-create/assign tickets for a campaign, respecting existing owner routing
- [x] **CAMP-03**: Live per-campaign progress (open / in-progress / done, % remediated) and campaign MTTR
- [x] **CAMP-04**: All campaign actions are audited

### Exception & Risk-Acceptance Workflow (EXC) — Phase 39

- [x] **EXC-01**: Mark false-positive / accept-risk with required justification, approver, and scope (finding / asset / asset-group)
- [x] **EXC-02**: Mandatory expiry; excluded from active queues, SLA timers, and dashboards until expiry
- [x] **EXC-03**: Every exception emits an audit event (who / why / scope / expiry)
- [x] **EXC-04**: Expired exceptions auto-resurface into the active queue

### Proactive Alerting & Digests (ALERT) — Phase 40

- [x] **ALERT-01**: Fire a targeted alert when a newly KEV-listed or high-EPSS CVE matches one of the tenant's own assets
- [x] **ALERT-02**: Scheduled per-owner / per-team digests (Slack / Teams / email) of due / breaching / newly-critical findings, on the in-process scheduler
- [x] **ALERT-03**: Alert rules and delivery channels are tenant-configurable and audited

### Coverage & Blind-Spot Detection (COV) — Phase 41

- [x] **COV-01**: Reconcile authoritative inventory (IdP / MDM / HR / CMDB) against scanner-seen assets; list assets with zero findings / never scanned *(Phase 41-01/41-02, 2026-08-20)*
- [x] **COV-02**: Per-connector coverage % and stale-source gaps *(Phase 41-03, 2026-08-21)*
- [x] **COV-03**: A newly-discovered unmanaged asset can be routed to an owner *(Phase 41-04/41-05, 2026-08-21)*

### Risk Trend Analytics & Burndown (TREND) — Phase 42

- [x] **TREND-01**: Tenant / team / asset-group risk-exposure trend lines over a selectable window *(Phase 42-01/42-03, 2026-08-21)*
- [x] **TREND-02**: Backlog aging (open findings by age × severity) and burndown rate *(Phase 42-02, 2026-08-21)*
- [x] **TREND-03**: Trends are risk-model-version-boundary aware (annotate, never blend across a v4.0 model version change) *(Phase 42-01/42-03, 2026-08-21)*

### Executive & Compliance Reporting (RPT) — Phase 43

- [x] **RPT-01**: Exportable exec/board report (PDF) with risk trend + MTTR-by-tier + SLA compliance for a selected period *(Phase 43-02/43-03, 2026-08-24)*
- [x] **RPT-02**: Role-scoped dashboards (analyst / IT-ops / compliance / leadership), tenant-scoped *(Phase 43-04, 2026-08-24)*
- [x] **RPT-03**: Compliance view mapping findings to framework controls (SOC 2 / ISO 27001 / PCI DSS / NIST CSF)

### Natural-Language Query Assistant (NLQ) — Phase 44 · (AINL-01, deferred from v3.1)

- [x] **NLQ-01**: Plain-English questions over the tenant's own vuln/asset/ticket data return grounded, tenant-scoped answers with the underlying result set shown *(Phase 44-01/44-02, 2026-08-25 — all three entities (vulnerabilities/assets/tickets) wired end-to-end)*
- [x] **NLQ-02**: Queries are constrained to a safe schema (no free-form SQL, no injection, no cross-tenant reach) *(Phase 44-01/44-06, 2026-08-25 — extra="forbid" schema + recheck_nlq_filter_exclusivity + no tenant_id field anywhere; now provable in CI via test_nlq_golden_evals.py's FilterCorrectnessMetric + the extended test_ai_injection_redteam.py's 6th capability)*
- [ ] **NLQ-03**: Inert until the tenant configures their own Anthropic key (BYOK), reusing the v3.0 scaffold + guardrails

### Public API, Webhooks & SDK (API) — Phase 45

- [ ] **API-01**: Tenant-scoped, RBAC-gated, rate-limited, audited REST API (read + write for findings / tickets / exceptions / campaigns)
- [ ] **API-02**: Signed event webhooks with retry (finding created / SLA breached / ticket synced / exception granted)
- [ ] **API-03**: Published OpenAPI spec + a minimal client SDK covering the core read/write surface

## Traceability

| Requirement | Phase | Depends on |
|-------------|-------|------------|
| SLA-01 | 36 | v4.0 risk model (shipped) |
| SLA-02 | 36 | v4.0 risk model (shipped) |
| SLA-03 | 36 | v4.0 risk model (shipped) |
| SLA-04 | 36 | v4.0 risk model (shipped) |
| SYNC-01 | 37 | existing ticketing connectors |
| SYNC-02 | 37 | existing ticketing connectors |
| SYNC-03 | 37 | existing ticketing connectors |
| SYNC-04 | 37 | existing ticketing connectors |
| CAMP-01 | 38 | cross-asset-by-CVE grouping, owner routing |
| CAMP-02 | 38 | cross-asset-by-CVE grouping, owner routing |
| CAMP-03 | 38 | cross-asset-by-CVE grouping, owner routing |
| CAMP-04 | 38 | cross-asset-by-CVE grouping, owner routing |
| EXC-01 | 39 | asset-ignored / exposure-override precedent |
| EXC-02 | 39 | asset-ignored / exposure-override precedent |
| EXC-03 | 39 | asset-ignored / exposure-override precedent |
| EXC-04 | 39 | asset-ignored / exposure-override precedent |
| ALERT-01 | 40 | v4.0 enrichment feeds (KEV/EPSS, shipped) |
| ALERT-02 | 40 | Phase 36 (SLA state feeds digest content) |
| ALERT-03 | 40 | v4.0 enrichment feeds, notifications |
| COV-01 | 41 | IdP/MDM/HR asset data |
| COV-02 | 41 | IdP/MDM/HR asset data |
| COV-03 | 41 | IdP/MDM/HR asset data |
| TREND-01 | 42 | v4.0 Phase 34 recompute (score history, shipped) |
| TREND-02 | 42 | v4.0 Phase 34 recompute (score history, shipped) |
| TREND-03 | 42 | v4.0 Phase 34 recompute (score history, shipped) |
| RPT-01 | 43 | Phase 36 (MTTR/SLA) + Phase 42 (trends) |
| RPT-02 | 43 | Phase 36 (MTTR/SLA) + Phase 42 (trends) |
| RPT-03 | 43 | Phase 36 (MTTR/SLA) + Phase 42 (trends) |
| NLQ-01 | 44 | v3.0 AI scaffold (shipped) |
| NLQ-02 | 44 | v3.0 AI scaffold (shipped) |
| NLQ-03 | 44 | v3.0 AI scaffold (shipped) |
| API-01 | 45 | event surface from Phases 36-39 |
| API-02 | 45 | event surface from Phases 36-39 |
| API-03 | 45 | event surface from Phases 36-39 |

**Coverage:** 34/34 v5.0 requirements mapped, 100% coverage, no orphans. Note: the proposal
([v5.0-PROPOSAL.md](milestones/v5.0-PROPOSAL.md)) and this file's own header both said "32 proposed
requirements" — the literal per-family bullet count above (SLA x4 + SYNC x4 + CAMP x4 + EXC x4 +
ALERT x3 + COV x3 + TREND x3 + RPT x3 + NLQ x3 + API x3) is actually **34**; corrected here at
roadmap creation, no scope was dropped or added.

Dependency refinement vs. the proposal (flagged per roadmapper review, not silently applied): Phase 40
(ALERT) is sequenced to depend on Phase 36 because ALERT-02's "breaching" digest content needs Phase 36's
SLA state machine to exist first — the proposal listed ALERT's dependency only as "v4.0 enrichment feeds
+ existing notification primitives" (both already shipped), which under-stated this one real intra-v5.0
dependency. All other phase pairs are independent of one another and could execute in any order; they are
sequenced 36->45 to match the proposal's narrative arc (route -> verify -> orchestrate-in-bulk ->
govern-exceptions -> alert -> find-blind-spots -> analyze-trend -> report -> ask-questions -> integrate).
