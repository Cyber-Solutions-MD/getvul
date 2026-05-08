# STATE — GetVul GSD Session Memory

## Project Reference

See: [.planning/PROJECT.md](PROJECT.md) (updated 2026-05-08)

**Core value:** A vuln-triage analyst can open one dashboard, see the same CVE-on-host correlated across multiple scanners, identify the asset's owner from IdP/MDM/HR, and ship a Jira/Asana ticket — without ever opening a scanner console.

**Current focus:** v1.0 Production Readiness — Phase 1 (Multi-Replica State) is the recommended starting phase.

## Current Position

| Field | Value |
|-------|-------|
| Active milestone | v1.0 Production Readiness |
| Active phase | Phase 1 — Multi-Replica State (Ready to execute) |
| Last action | 2026-05-08 — `/gsd-plan-phase 1` complete; 4 plans across 3 waves committed (`178fb3c`) |
| Resume file | [.planning/phases/01-multi-replica-state/01-00-PLAN.md](phases/01-multi-replica-state/01-00-PLAN.md) |
| Next action | `/clear` then `/gsd-execute-phase 1` |

## Audit Reference

The roadmap is sourced from a codebase audit performed 2026-05-08 against commit `8cede77`. Audit lives in conversation history; key findings:

- **Production blockers** (audit §5): in-process state across replicas, CI disabled, dual update mechanisms, doc/code drift, no encryption-key backup story, default admin password, single-VM topology, thin tests.
- **Top 5 next steps** (audit §8): CI gating, Redis-backed state, single update path, doc reconciliation, connector test coverage.
- **Open questions for maintainer** (audit §7): SaaS vs single-tenant intent, CI quiet period, `boto3` dead code, dual update mechanism canonical choice. **These should surface during `/gsd-discuss-phase` for the relevant phases.**

## Decisions Pending Discuss-Phase

These need maintainer input before planning the corresponding phase:

| Phase | Decision |
|-------|----------|
| 2 | ZAP findings: gate the build above an agreed severity, or run as labeled non-blocking workflow? |
| 3 | Which update mechanism is canonical — GH-Actions release CD or hourly cron? |
| 4 | Implement Secrets Manager integration end-to-end, or remove the `boto3` dep + `aws_*` config as dead code? |
| 5 | Where is `ENCRYPTION_KEY` backed up? (KMS, password manager, sealed secret, customer's responsibility?) |

## Workflow Notes

- GSD installed locally to `.claude/` via `npx get-shit-done-cc@latest --claude --local` on 2026-05-08.
- Planning artifacts seeded directly from audit (not via `/gsd-new-project`) — research outputs under `.planning/research/` are intentionally absent for this milestone.
- v0.1 features in [PROJECT.md](PROJECT.md) "Validated Requirements" are inferred from existing code; treat as a snapshot, refine if any are actually broken.

---
*Last updated: 2026-05-08 — initial seed from audit*
