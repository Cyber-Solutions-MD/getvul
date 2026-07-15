---
phase: 3
slug: update-path-reconciliation
status: complete
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-01
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: `03-RESEARCH.md` §Validation Architecture. This phase modifies existing
> YAML + shell + docs; there is **no new backend code**, so verification is
> grep/lint-based plus one human UAT (SC#4 dry-run rollback).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | grep-based smoke checks + YAML lint (`actionlint` preferred, `yamllint` fallback); pytest exists but no new tests this phase |
| **Config file** | none new — `pyproject.toml` already configures pytest |
| **Quick run command** | `grep -c "reset --hard origin/main" .github/workflows/cd.yml; grep -rc "getvul-update" install.sh infra/gcp/startup.sh` |
| **Full suite command** | `actionlint .github/workflows/cd.yml || yamllint .github/workflows/cd.yml` + the quick grep suite |
| **Estimated runtime** | ~3 seconds |

---

## Sampling Rate

- **After every task commit:** Run the quick grep suite (cron/`reset --hard` absence must trend to 0)
- **After every plan wave:** Run the full suite (grep suite + `cd.yml` lint)
- **Before `/gsd-verify-work`:** All grep checks return 0, `scripts/auto-update.sh` absent from git tree, rollback runbook section present and non-trivial in `docs/13-deployment.md`
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

> Task IDs assigned during planning (step below). Rows populated by the planner /
> gsd-nyquist-auditor once PLAN.md files exist. Requirement→check mapping is fixed:

| Requirement | Automated Check (grep/lint) | Test Type | Notes |
|-------------|-----------------------------|-----------|-------|
| PROD-03-01 | `grep -c "getvul-update" install.sh` → 0 | smoke | canonical cron removed from install.sh Step 8 |
| PROD-03-02 | `grep -c "getvul-update" infra/gcp/startup.sh` → 0; `git ls-files scripts/auto-update.sh` → empty | smoke | cron removed from startup.sh + updater git-rm'd |
| PROD-03-03 | `grep -c "reset --hard origin/main" .github/workflows/cd.yml` → 0; `grep -c "checkout --force" .github/workflows/cd.yml` → ≥1; `cd.yml` lints clean | smoke + lint | tag-pinned checkout replaces main HEAD reset |
| PROD-03-04 | `docs/13-deployment.md` §Rollback present with real commands + migration caveat callout | manual review + grep | see Manual-Only below for the VM dry-run |

*Status per task: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements.* No new test files or framework
install required — this phase edits YAML, shell, and docs; all automatable verification is
grep/lint on files that already exist.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Dry-run rollback on a test VM | PROD-03-04 (SC#4) | ROADMAP SC#4 is explicitly a human UAT item; a real rollback requires triggering `workflow_dispatch` against a live/test GCE VM (real infra + creds), out of scope for automated CI here | Cut a throwaway release, deploy it via CD, then trigger `cd.yml` `workflow_dispatch` with `ref=<prior tag>`; confirm `/health` returns 200 on the prior version and record in phase VERIFICATION.md |
| Live-VM cron residue removed | PROD-03-01/02 | Editing `install.sh`/`startup.sh` does not touch the already-running GCE VM's `/etc/cron.d/getvul-update` | On the live VM: `sudo rm -f /etc/cron.d/getvul-update /usr/local/bin/getvul-update` then confirm `ls /etc/cron.d/ | grep getvul` is empty (documented as an operator step, not automatable in CI) |

---

## Validation Sign-Off

- [ ] All tasks have automated verify (grep/lint) or a Manual-Only entry with instructions
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (none this phase)
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

---

## Validation Audit 2026-07-15 (post-BL-05 backend sweep)

Reconciled against the codebase. All four grep/lint checks re-run and pass; the map has no
status column (grep/lint smoke checks, not pytest).

| Metric | Count |
|--------|-------|
| Automated rows | 4 |
| Covered (green) | 4 |
| Gaps found | 0 |
| New tests written | 0 |
| Escalated to manual-only | 1 (SC#4 live-VM rollback dry-run — needs real GCE infra) |

Evidence: `getvul-update` absent from install.sh/startup.sh · `auto-update.sh` git-rm'd ·
cd.yml has no `reset --hard origin/main`, uses tag-pinned `checkout --force` · rollback runbook
+ migration caveat present in docs/13-deployment.md. **Nyquist-compliant.**
