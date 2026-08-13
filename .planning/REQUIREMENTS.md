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

- [ ] **SLA-01**: Risk-tier SLA policy (default critical 7d / high 30d / moderate 90d), tenant-configurable, computed off the v4.0 risk-exposure tier
- [ ] **SLA-02**: Each open finding shows a live SLA state (on-track / approaching / breached) derived from that policy
- [ ] **SLA-03**: Approaching/breach transitions auto-escalate to a configured channel (Slack / Microsoft Teams / email / PagerDuty), fired exactly once per transition, audited
- [ ] **SLA-04**: MTTR is captured per risk tier and exposed for reporting (feeds RPT/TREND)

### Two-Way Ticket Sync & Remediation Verification (SYNC) — Phase 37

- [ ] **SYNC-01**: Ticket status writes back from Jira / Asana / GitHub into the linked GetVul finding (bi-directional, not create-only)
- [ ] **SYNC-02**: A finding absent from N consecutive post-fix scanner syncs auto-closes as rescan-verified, with an audit trail
- [ ] **SYNC-03**: A recurrence after auto-close reopens the finding rather than silently creating a duplicate
- [ ] **SYNC-04**: Sync is resilient to connector/API failure (retry, last-sync surfaced, no data loss)

### Remediation Campaigns (CAMP) — Phase 38

- [ ] **CAMP-01**: Group findings by shared fix (CVE / patch / product) across multiple assets and owners into a campaign in one action
- [ ] **CAMP-02**: Bulk-create/assign tickets for a campaign, respecting existing owner routing
- [ ] **CAMP-03**: Live per-campaign progress (open / in-progress / done, % remediated) and campaign MTTR
- [ ] **CAMP-04**: All campaign actions are audited

### Exception & Risk-Acceptance Workflow (EXC) — Phase 39

- [ ] **EXC-01**: Mark false-positive / accept-risk with required justification, approver, and scope (finding / asset / asset-group)
- [ ] **EXC-02**: Mandatory expiry; excluded from active queues, SLA timers, and dashboards until expiry
- [ ] **EXC-03**: Every exception emits an audit event (who / why / scope / expiry)
- [ ] **EXC-04**: Expired exceptions auto-resurface into the active queue

### Proactive Alerting & Digests (ALERT) — Phase 40

- [ ] **ALERT-01**: Fire a targeted alert when a newly KEV-listed or high-EPSS CVE matches one of the tenant's own assets
- [ ] **ALERT-02**: Scheduled per-owner / per-team digests (Slack / Teams / email) of due / breaching / newly-critical findings, on the in-process scheduler
- [ ] **ALERT-03**: Alert rules and delivery channels are tenant-configurable and audited

### Coverage & Blind-Spot Detection (COV) — Phase 41

- [ ] **COV-01**: Reconcile authoritative inventory (IdP / MDM / HR / CMDB) against scanner-seen assets; list assets with zero findings / never scanned
- [ ] **COV-02**: Per-connector coverage % and stale-source gaps
- [ ] **COV-03**: A newly-discovered unmanaged asset can be routed to an owner

### Risk Trend Analytics & Burndown (TREND) — Phase 42

- [ ] **TREND-01**: Tenant / team / asset-group risk-exposure trend lines over a selectable window
- [ ] **TREND-02**: Backlog aging (open findings by age × severity) and burndown rate
- [ ] **TREND-03**: Trends are risk-model-version-boundary aware (annotate, never blend across a v4.0 model version change)

### Executive & Compliance Reporting (RPT) — Phase 43

- [ ] **RPT-01**: Exportable exec/board report (PDF) with risk trend + MTTR-by-tier + SLA compliance for a selected period
- [ ] **RPT-02**: Role-scoped dashboards (analyst / IT-ops / compliance / leadership), tenant-scoped
- [ ] **RPT-03**: Compliance view mapping findings to framework controls (SOC 2 / ISO 27001 / PCI DSS / NIST CSF)

### Natural-Language Query Assistant (NLQ) — Phase 44 · (AINL-01, deferred from v3.1)

- [ ] **NLQ-01**: Plain-English questions over the tenant's own vuln/asset/ticket data return grounded, tenant-scoped answers with the underlying result set shown
- [ ] **NLQ-02**: Queries are constrained to a safe schema (no free-form SQL, no injection, no cross-tenant reach)
- [ ] **NLQ-03**: Inert until the tenant configures their own Anthropic key (BYOK), reusing the v3.0 scaffold + guardrails

### Public API, Webhooks & SDK (API) — Phase 45

- [ ] **API-01**: Tenant-scoped, RBAC-gated, rate-limited, audited REST API (read + write for findings / tickets / exceptions / campaigns)
- [ ] **API-02**: Signed event webhooks with retry (finding created / SLA breached / ticket synced / exception granted)
- [ ] **API-03**: Published OpenAPI spec + a minimal client SDK covering the core read/write surface

## Traceability (to fill at activation)

| Requirement family | Proposed phase | Depends on |
|--------------------|----------------|------------|
| SLA-01..04 | 36 | v4.0 risk model |
| SYNC-01..04 | 37 | ticketing connectors |
| CAMP-01..04 | 38 | cross-asset-by-CVE grouping, owner routing |
| EXC-01..04 | 39 | asset-ignored / exposure-override precedent |
| ALERT-01..03 | 40 | v4.0 enrichment feeds, notifications |
| COV-01..03 | 41 | IdP/MDM/HR asset data |
| TREND-01..03 | 42 | v4.0 Phase 34 recompute (score history) |
| RPT-01..03 | 43 | SLA (36) + TREND (42) |
| NLQ-01..03 | 44 | v3.0 AI scaffold |
| API-01..03 | 45 | event surface from 36–39 |

**Coverage:** 32 proposed requirements across 10 families → 10 phases. Re-confirm scope, wording, and
IDs at activation (market shifts; re-validate against fresh research).
