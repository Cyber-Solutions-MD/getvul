---
phase: 03-update-path-reconciliation
plan: "02"
subsystem: deployment
tags: [cd, github-actions, rollback, documentation, devops]
dependency_graph:
  requires: []
  provides: [tag-pinned-cd, rollback-runbook, PROD-03-03, PROD-03-04]
  affects: [.github/workflows/cd.yml, docs/13-deployment.md, docs/12-pipelines-cicd.md, docs/diagrams/pipelines-cicd.mmd]
tech_stack:
  added: []
  patterns:
    - "github.event.release.tag_name || inputs.release_tag for dual-trigger tag resolution"
    - "Unquoted SSH heredoc delimiter (DEPLOY) to allow runner-side variable interpolation"
    - "Escaped \\$(date) / \\$(seq) inside heredoc for VM-side evaluation"
key_files:
  created: []
  modified:
    - .github/workflows/cd.yml
    - docs/13-deployment.md
    - docs/12-pipelines-cicd.md
    - docs/diagrams/pipelines-cicd.mmd
decisions:
  - "release_tag string input (not ref or tag) consistent with operator expectation for semver tags"
  - "Unquoted DEPLOY heredoc delimiter enables runner to expand DEPLOY_TAG into the SSH session; VM-side vars use backslash escaping"
  - "Migration caveat placed in Step 2 (BEFORE the trigger step) per research Pitfall 5"
  - "gh workflow run cd.yml --field release_tag=<prior-tag> as the canonical rollback command"
metrics:
  duration: "~10 minutes"
  completed: "2026-07-01"
  tasks_completed: 2
  files_modified: 4
---

# Phase 03 Plan 02: Tag-Pinned CD + Rollback Runbook Summary

Tag-pinned CD deploy via `git fetch --tags --force && git checkout --force` with a `release_tag` workflow_dispatch input; 4-step operator rollback runbook with prominent DB migration caveat; all cron and `reset --hard` references in the three CD-owned doc files removed.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Rewrite cd.yml for tag-pinned deploys with release_tag dispatch input | 56514c1 | .github/workflows/cd.yml |
| 2 | Rollback runbook in docs/13 + reconcile docs/12 + mermaid source | b4994e7 | docs/13-deployment.md, docs/12-pipelines-cicd.md, docs/diagrams/pipelines-cicd.mmd |

## What Was Built

### Task 1 — cd.yml tag-pinned deploy rewrite (PROD-03-03)

Replaced the `force` boolean `workflow_dispatch` input with a `release_tag` string input. Added a "Resolve deploy tag" step as the first step after checkout — it resolves `DEPLOY_TAG` from `github.event.release.tag_name || inputs.release_tag` and fails fast (exit 1) if no tag resolves (guards against bare manual dispatches). Changed the SSH heredoc delimiter from quoted `<< 'DEPLOY'` to unquoted `<< DEPLOY` so the runner expands `${{ env.DEPLOY_TAG }}` into the heredoc body; all VM-side shell vars inside the heredoc are backslash-escaped (`\$(date)`, `\$(seq 1 30)`, `\$i`). Swapped `git fetch origin main && git reset --hard origin/main` with `git fetch --tags --force && git checkout --force "${{ env.DEPLOY_TAG }}"`. Updated verify step success message to reference the tag. YAML validates with pyyaml.

### Task 2 — Rollback runbook + docs reconciliation (PROD-03-04, D-03)

**docs/13-deployment.md:**
- `§Rollback` — completely replaced the placeholder with a 4-step runbook: (1) identify prior tag via `gh release list --limit 5`, (2) prominent WARNING blockquote before the trigger step — A CODE ROLLBACK DOES NOT REVERT DATABASE MIGRATIONS with explicit `pg_dump` restore guidance, (3) `gh workflow run cd.yml --field release_tag=<prior-tag>` trigger command, (4) verify via Actions run health check.
- `§Release process` — rewritten to single canonical path, removing the two-flows description and the "PROD-03 will pick one" placeholder.
- Install step summaries (Azure, AWS, GCP sections) — removed "hourly auto-update cron" from the 8-step list; now 7 steps.
- `§Production Checklist` — replaced "Verify auto-update cron is active" with "Confirm no legacy auto-update cron remains".
- `§Provisioning-Terraform` — removed the daily cron clause and the hourly/daily divergence blockquote (resolved).

**docs/12-pipelines-cicd.md:**
- Inline mermaid: updated PULL node label to `git fetch --tags + checkout release tag`; removed CRON node.
- CD Triggers block: replaced `force` boolean with `release_tag` string input.
- Deploy step: added "Resolve deploy tag" step description, updated code block to `git fetch --tags --force` / `git checkout --force "$DEPLOY_TAG"`.
- Known issues: replaced PROD-03 four-bullet list with one-line "PROD-03 — resolved" notice.

**docs/diagrams/pipelines-cicd.mmd:**
- Updated PULL node: `git fetch --tags + checkout release tag`.
- Removed CRON node entirely.
- Updated note text to reflect Phase 2 hard-fail reality.

## Acceptance Criteria Verification

```
grep -c "reset --hard origin/main" .github/workflows/cd.yml    -> 0  PASS (PROD-03-03)
grep -c "checkout --force" .github/workflows/cd.yml            -> 1  PASS (PROD-03-03)
grep -c "git fetch --tags --force" .github/workflows/cd.yml    -> 1  PASS
grep -c "github.event.release.tag_name || inputs.release_tag"  -> 1  PASS (D-04/D-06)
grep -c "force:" .github/workflows/cd.yml                      -> 0  PASS
grep -c "release_tag:" .github/workflows/cd.yml                -> 1  PASS (D-06)
grep -c "github.ref_name" .github/workflows/cd.yml             -> 0  PASS (anti-pattern absent)
python3 yaml.safe_load(cd.yml)                                 -> exits 0  PASS
grep -c "## Rollback" docs/13-deployment.md                    -> 1  PASS (PROD-03-04)
grep -c "gh workflow run cd.yml" docs/13-deployment.md         -> 1  PASS (D-06 rollback path)
grep -c "DOES NOT REVERT DATABASE MIGRATIONS" docs/13-deployment.md -> 1  PASS (D-08)
grep -c "reset --hard origin/main" docs/13-deployment.md       -> 0  PASS
grep -c "reset --hard origin/main" docs/12-pipelines-cicd.md   -> 0  PASS
grep -c "reset --hard origin/main" docs/diagrams/pipelines-cicd.mmd -> 0  PASS
grep -c "getvul-update" docs/13-deployment.md                  -> 0  PASS (D-03)
grep -c "CRON" docs/diagrams/pipelines-cicd.mmd                -> 0  PASS
grep -c "release_tag" docs/12-pipelines-cicd.md                -> 1  PASS
```

## Threat Mitigations Applied

| Threat ID | Mitigation |
|-----------|------------|
| T-03-04 | `set -e` in heredoc + empty-string guard step exits 1 before SSH if no tag resolved; `git checkout` rejects unresolvable refs under `set -e` |
| T-03-05 | `git fetch --tags --force` updates re-created/moved tag refs before checkout |
| T-03-06 | `github.event.release.tag_name \|\| inputs.release_tag` used (not `github.ref_name`); zero occurrences of `github.ref_name` verified |
| T-03-07 | WARNING blockquote placed in Step 2 (BEFORE the trigger step) per D-08 / research Pitfall 5 |

## Manual UAT Required (SC#4)

SC#4 is a human-only item and is NOT automated by this plan:

- Dry-run rollback on a test VM: cut a throwaway release tag, deploy via CD, then trigger `cd.yml` workflow_dispatch with `release_tag=<prior-tag>`, confirm `/health` returns 200 on the prior version.
- Requires real GCE infra + credentials.
- Record outcome in `.planning/phases/03-update-path-reconciliation/03-VERIFICATION.md`.

## Deviations from Plan

None — plan executed exactly as written. The mermaid note text was updated from the Phase 2 placeholder to reflect current hard-fail reality (minor reconciliation improvement consistent with the plan's "reconcile to current reality" objective).

## Self-Check: PASSED

- [x] `.github/workflows/cd.yml` modified — commit 56514c1
- [x] `docs/13-deployment.md` modified — commit b4994e7
- [x] `docs/12-pipelines-cicd.md` modified — commit b4994e7
- [x] `docs/diagrams/pipelines-cicd.mmd` modified — commit b4994e7
- [x] `03-02-SUMMARY.md` created — this file
- [x] All acceptance criteria PASS (verified above)
