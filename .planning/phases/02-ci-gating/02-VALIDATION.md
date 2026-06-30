---
phase: 2
slug: ci-gating
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-30
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Phase 2 is CI/workflow infrastructure — most verification is via **live CI runs** and **`gh api` inspection**, not new unit tests. No Wave 0 test files needed (research §"Wave 0 Gaps": none).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend), vitest (frontend), `gh` CLI 2.95 (CI-gate verification) |
| **Config file** | `backend/pyproject.toml` (`[tool.mypy] strict = true`), `frontend/vitest.config.mts`, `.github/workflows/ci.yml` |
| **Quick run command** | Local: `cd frontend && npx tsc --noEmit` · `cd backend && .venv/bin/mypy app/ \| mypy-baseline filter` |
| **Full suite command** | `gh run list --repo Cyber-Solutions-MD/getvul --limit 5` then `gh run view <id>` (live CI) |
| **Estimated runtime** | Local checks ~30–60s; full CI run ~several min (incl. DAST on push-to-main only) |

---

## Sampling Rate

- **After every task commit:** Run the relevant local check (`tsc --noEmit`, or `mypy app/ | mypy-baseline filter`, or `yamllint`/parse of ci.yml)
- **After every plan wave:** Push to a test branch and confirm the expected CI job statuses via `gh run view`
- **Before `/gsd-verify-work`:** All four required checks (`Backend`, `Frontend`, `Semgrep SAST`, `Terraform Validate`) green on a real PR; branch protection confirmed via `gh api`
- **Max feedback latency:** ~60s local; CI runs async

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| triggers | 01 | 1 | PROD-02-01 | — | CI runs on push + PR (not just manual) | smoke | `gh run list --limit 5` shows `push`/`pull_request` events | ✅ (ci.yml) | ⬜ pending |
| frontend-tsc | 01 | 1 | PROD-02-02 | — | tsc failures block CI | smoke | `cd frontend && npx tsc --noEmit` exits 0 after fix | ✅ | ⬜ pending |
| frontend-lint | 01 | 1 | PROD-02-02 | — | lint failures block CI | smoke | `cd frontend && npm run lint` exits 0 | ✅ | ⬜ pending |
| mypy-baseline | 01 | 1 | PROD-02-02 | — | NEW mypy errors block CI; 619 legacy in baseline | integration | `mypy app/ \| mypy-baseline filter` exits 0; an injected new error exits non-zero | ✅ | ⬜ pending |
| zap-advisory | 01 | 1 | PROD-02-03 | — | DAST runs on push+schedule, skipped on PR, non-blocking | inspection | `gh run view <pr-run>` shows `OWASP ZAP DAST` absent/skipped | ✅ (via CI) | ⬜ pending |
| branch-protect | 02 | 2 | PROD-02-04 | — | PR with failing check cannot merge to main | integration | `gh api .../branches/main/protection` lists the 4 checks; failing PR merge blocked | ✅ (via gh api) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements — no new test files needed. CI workflow, pytest, vitest, and Redis service already exist (research §5). Verification is via live CI runs and `gh api`.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Failing PR is merge-blocked | PROD-02-04 | Requires opening a real PR against the live repo with a deliberate failure | Create branch with an injected new type/tsc error → open PR → confirm merge button blocked (required check red) → close PR |
| DAST absent on PR runs | PROD-02-03 | Requires a real PR-triggered CI run to inspect | `gh run view <pr-run-id>` — confirm `OWASP ZAP DAST` job did not run on the PR event |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or live-CI/`gh api` verification
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (N/A — none)
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s (local) / async (CI)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
