# Roadmap: GetVul

## Overview

GetVul is a unified vulnerability-triage platform: one dashboard correlates the same CVE-on-host across
multiple scanners, identifies the asset's owner via IdP/MDM/HR, scores and explains real risk exposure,
and ships a Jira/Asana/GitHub ticket — without opening a scanner console. All milestones through **v4.0**
are shipped and archived; see [MILESTONES.md](MILESTONES.md) for the full log and `.planning/milestones/`
for per-milestone detail (roadmap + requirements + audit + archived phase dirs).

## Milestones

- ✅ **v1.0 Production Readiness** — Phases 1–8 (SHIPPED 2026-07-14)
- ✅ **v2.0 UI/UX Redesign** — Phases 9–15 (SHIPPED 2026-06-30) — [archive](milestones/v2.0-ROADMAP.md)
- ✅ **v2.1 Polish & Tech Debt** — BL-01..05 (SHIPPED 2026-07-15)
- ✅ **v2.2 Deferred UI Features** — Phases 16–22 (SHIPPED 2026-07-22) — [archive](milestones/v2.2-ROADMAP.md)
- ✅ **v3.0 AI-Assisted Triage ("Triage Copilot")** — Phases 23–29 (SHIPPED 2026-08-04) — [archive](milestones/v3.0-ROADMAP.md)
- ✅ **v4.0 Enriched Risk Exposure & Source-Aware Triage** — Phases 30–35 (SHIPPED 2026-08-13) — [archive](milestones/v4.0-ROADMAP.md)
- 📋 **v5.0 Close the Loop — Remediation Orchestration & Assurance** — PROPOSED (not started) — [proposal](milestones/v5.0-PROPOSAL.md) · [requirements stub](milestones/v5.0-REQUIREMENTS.md)

## Phases

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

## Next

**v5.0 "Close the Loop"** is drafted but not started — activate via `/gsd-new-milestone` (it will seed a
fresh REQUIREMENTS.md from the [v5.0 requirements stub](milestones/v5.0-REQUIREMENTS.md): 32 requirements
across 10 families — SLA engine, two-way ticket sync + rescan-verified auto-close, remediation campaigns,
exception/risk-acceptance, proactive alerting, coverage/blind-spot detection, risk-trend analytics,
executive + compliance reporting, NL query assistant, public API/webhooks).
