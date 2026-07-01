---
phase: 03-update-path-reconciliation
plan: "01"
subsystem: infra/provisioning/docs
tags: [cron-removal, deploy-path, prod-hardening, PROD-03]
dependency_graph:
  requires: []
  provides:
    - "install.sh with no cron-install code (PROD-03-01)"
    - "infra/{gcp,aws,azure}/startup.sh with no cron-install code (PROD-03-02)"
    - "scripts/auto-update.sh absent from git tree (PROD-03-02)"
    - "docs/02-architecture.md: CRON node and edges removed"
    - "docs/07-project-structure.md: auto-update.sh entry and cron mention removed"
    - "docs/17-troubleshooting.md: B1 rewritten as one-time VM cron-residue cleanup"
  affects:
    - ".github/workflows/cd.yml (Plan 03-02 owns)"
    - "docs/13-deployment.md (Plan 03-02 owns)"
    - "docs/12-pipelines-cicd.md (Plan 03-02 owns)"
tech_stack:
  added: []
  patterns:
    - "No-op placeholder comment replaces removed cron blocks (idempotent; grep-safe)"
key_files:
  created: []
  modified:
    - install.sh
    - infra/gcp/startup.sh
    - infra/aws/startup.sh
    - infra/azure/startup.sh
    - infra/gcp/main.tf
    - infra/aws/main.tf
    - infra/azure/main.tf
    - docs/02-architecture.md
    - docs/07-project-structure.md
    - docs/17-troubleshooting.md
  deleted:
    - scripts/auto-update.sh
decisions:
  - "Cleanup comment in install.sh references docs/17-troubleshooting.md §B1 (not the bare rm command) to satisfy the grep-c=0 gate while preserving discoverability"
  - "Step counter in install.sh updated from [7/8] to [7/7] for the demo-data step; earlier step numbering inconsistency (pre-existing) left as-is"
metrics:
  duration: "~15 minutes"
  completed: "2026-07-01"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 11
  files_deleted: 1
requirements:
  - PROD-03-01
  - PROD-03-02
---

# Phase 03 Plan 01: Hard-remove auto-update cron from provisioning scripts and docs

Hard-removes the auto-update cron install from all three cloud provisioning scripts and install.sh, git-rm's scripts/auto-update.sh, and cleans every cron reference from the architecture/structure/troubleshooting docs — making the deploy race structurally impossible per D-02/D-03.

## Tasks

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | Hard-remove cron from install.sh + 3x startup.sh; update main.tf comments; git rm auto-update.sh | 7128409 | install.sh, infra/*/startup.sh, infra/*/main.tf, scripts/auto-update.sh (deleted) |
| 2 | Remove CRON node from architecture mermaid; clean project-structure doc; rewrite troubleshooting B1 | 15c5acd | docs/02-architecture.md, docs/07-project-structure.md, docs/17-troubleshooting.md |

## Verification Results

All acceptance criteria passed:

```
grep -c "getvul-update" install.sh                    → 0  (PROD-03-01)
grep -c "getvul-update" infra/gcp/startup.sh          → 0  (PROD-03-02)
grep -c "getvul-update" infra/aws/startup.sh          → 0
grep -c "getvul-update" infra/azure/startup.sh        → 0
git ls-files scripts/auto-update.sh                   → (empty)  (PROD-03-02)
grep -c "auto-update" infra/gcp/main.tf               → 0
grep -c "auto-update" infra/aws/main.tf               → 0
grep -c "auto-update" infra/azure/main.tf             → 0
bash -n install.sh                                    → exit 0
bash -n infra/gcp/startup.sh                          → exit 0
bash -n infra/aws/startup.sh                          → exit 0
bash -n infra/azure/startup.sh                        → exit 0
grep -c "GitHub Actions CD" install.sh                → 1
grep -c "CRON" docs/02-architecture.md                → 0
grep -c "auto-update.sh" docs/07-project-structure.md → 0
grep -c "cron)" docs/07-project-structure.md          → 0
grep -q "sudo rm -f /etc/cron.d/getvul-update" docs/17-troubleshooting.md → match
grep -c "Or disable CD until Phase 3" docs/17-troubleshooting.md → 0
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] install.sh cleanup comment adjusted to satisfy grep-c=0 gate**
- **Found during:** Task 1 verification
- **Issue:** The plan's verbatim replacement block for Step 8 contained `getvul-update` in the cleanup hint comment (`sudo rm -f /etc/cron.d/getvul-update /usr/local/bin/getvul-update`), which would have failed the `grep -c "getvul-update" install.sh → 0` acceptance criterion.
- **Fix:** The cleanup hint in install.sh was changed to reference `docs/17-troubleshooting.md §B1` (where the actual cleanup commands live) rather than inlining the `rm` command. The full cleanup commands appear correctly in docs/17-troubleshooting.md §B1 which is intentionally exempt from the zero-grep gate.
- **Files modified:** install.sh
- **Commit:** 7128409

## Known Stubs

None — this plan performs removals and doc rewrites; no data sources are stubbed.

## Threat Flags

No new network endpoints, auth paths, file access patterns, or schema changes introduced. This plan removes a security threat surface (T-03-01: unauthorized cron deploy path).

## Self-Check: PASSED

- install.sh exists and has no getvul-update references: CONFIRMED
- infra/gcp/startup.sh has no getvul-update references: CONFIRMED
- scripts/auto-update.sh absent from git tree: CONFIRMED
- docs/02-architecture.md has no CRON node: CONFIRMED
- docs/17-troubleshooting.md §B1 cleanup command documented: CONFIRMED
- Task 1 commit 7128409 exists: CONFIRMED
- Task 2 commit 15c5acd exists: CONFIRMED
