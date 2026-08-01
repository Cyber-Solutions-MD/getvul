---
phase: 28
slug: eval-cost-observability-gate
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-08-01
---

# Phase 28 — Validation Strategy

> Per-phase validation contract. This phase IS largely about validation infrastructure (evals + red-team + breaker coverage), so its own tests are the deliverable.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Backend: pytest 7.x (+ DeepEval for evals) · Frontend: vitest · CI: GitHub Actions (.github/workflows/ci.yml) |
| **Config file** | backend: `backend/pyproject.toml` · frontend: `frontend/vitest.config.ts` · CI: `.github/workflows/ci.yml` |
| **Quick run command** | backend: `cd backend && ENCRYPTION_KEY=<fernet> JWT_SECRET_KEY=test python -m pytest tests/evals tests/test_ai_injection_redteam.py tests/test_ai_budget_coverage.py -q` · frontend: `cd frontend && npx vitest run ai-usage settings` |
| **Full suite command** | backend: `cd backend && python -m pytest tests/test_ai_*.py tests/evals -q` · frontend: `cd frontend && npx vitest run` |
| **Estimated runtime** | ~60-90s backend (keyless deterministic eval + red-team + coverage); ~90s frontend |

> KEYLESS-CI constraint (D-01): the CI-BLOCKING eval + red-team tiers make ZERO model calls — they assert over captured golden fixtures + built prompts. The opt-in LLM-judge/live-promptfoo tier is `if: secrets.<KEY>` guarded and NON-blocking. getvul backend pytest env: real Fernet ENCRYPTION_KEY + JWT_SECRET_KEY, per-file runs. Postgres + Redis up.

---

## Sampling Rate

- **After every task commit:** quick run for the touched side
- **After every plan wave:** full suite command(s)
- **Before `/gsd-verify-work`:** full suite green
- **Max feedback latency:** ~90 seconds

---

## Per-Task Verification Map

*Filled by the planner (each task's `<automated>` verify) and reconciled by validate-phase / nyquist-auditor.*

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | — | — | AIE-01/02/03/04 | T-28-xx | keyless-CI evals; injection isolation; no AI call bypasses the budget guard; admin-only usage view; user_email batch split | unit / integration / e2e | `pytest tests/evals tests/test_ai_injection_redteam.py -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- New: `backend/tests/evals/` (DeepEval keyless structural metrics + golden fixtures), `tests/test_ai_injection_redteam.py` (consolidated keyless red-team), `tests/test_ai_budget_coverage.py` (no-bypass coverage), `.github/workflows/ci.yml` job additions. Golden fixtures are captured once (dev-key, redacted) and committed — a documented one-time op, not a CI dependency.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live admin AI usage/cost pane renders month-to-date cost vs budget + per-capability breakdown + breaker status; live cost breaker degrades every surface when a tenant exceeds budget | AIE-03/AIE-04 | Requires a live stack + real usage/spend + browser; same waived-class as Phase 24-27 live items | As admin, open the AI settings pane; verify usage aggregates; force budget-exceeded and confirm every AI surface degrades to deterministic-only |
| Opt-in key-gated live LLM-judge eval + real promptfoo red-team | AIE-01/AIE-02 | Requires a dev Anthropic key (non-blocking CI tier) | Run the key-gated job locally with a dev key |

*The CI-BLOCKING tiers (deterministic evals, keyless red-team, breaker coverage) are fully automated + keyless; the live-observation + key-gated items are manual.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (evals dir, red-team + coverage tests, ci.yml jobs, golden fixtures)
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
