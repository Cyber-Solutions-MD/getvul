---
phase: 27
slug: ticket-auto-drafting
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-01
---

# Phase 27 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Backend: pytest 7.x · Frontend: vitest |
| **Config file** | backend: `backend/pyproject.toml` · frontend: `frontend/vitest.config.ts` |
| **Quick run command** | backend: `cd backend && ENCRYPTION_KEY=<fernet> JWT_SECRET_KEY=test python -m pytest tests/test_ticketing_dispatch.py -q` · frontend: `cd frontend && npx vitest run drill-panel ai-explanation-section` |
| **Full suite command** | backend: `cd backend && python -m pytest tests/test_ticketing_dispatch.py tests/test_ai_*.py -q` · frontend: `cd frontend && npx vitest run` |
| **Estimated runtime** | ~40s backend; ~90s frontend |

> getvul backend pytest env: real Fernet ENCRYPTION_KEY + JWT_SECRET_KEY, per-file runs. Postgres + Redis up.

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
| TBD | — | — | AID-01 | T-27-xx | title override mass-assignment-safe (extra=forbid, max_length 255); never auto-submits; resourceId-keyed compose guard | unit | `pytest tests/test_ticketing_dispatch.py -q` / `vitest run drill-panel` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- Existing infra (`backend/tests/test_ticketing_dispatch.py`, frontend `drill-panel*.test.tsx` / `ai-explanation-section.test.tsx`) covers Phase 27. No new framework install. No new migration (drafts are ephemeral client state; the `title` field is a schema-only addition, no DB column on Ticket).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live: opening the create dialog auto-populates title + composed body from cached outputs; editing every field; Create ships once | AID-01 | Requires live stack + configured key + cached AI outputs + browser (same class as Phase 24-26 waived items) | Generate explain/remediation for a finding → open create dialog → confirm pre-fill, edit, Create; also verify no-key → manual flow unchanged, and switching vulns doesn't carry a draft over |

*Automated coverage proves the title override + fallback, the 255-cap validation, the resourceId-keyed compose guard, the never-auto-submit path, and provider threading in isolation; the live browser flow is manual.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
