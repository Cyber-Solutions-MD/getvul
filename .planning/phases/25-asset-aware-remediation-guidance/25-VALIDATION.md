---
phase: 25
slug: asset-aware-remediation-guidance
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-30
---

# Phase 25 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Backend: pytest 7.x · Frontend: vitest |
| **Config file** | backend: `backend/pyproject.toml` · frontend: `frontend/vitest.config.ts` |
| **Quick run command** | backend: `cd backend && ENCRYPTION_KEY=<fernet> JWT_SECRET_KEY=test python -m pytest tests/test_ai_*.py -q` · frontend: `cd frontend && npx vitest run ai-` |
| **Full suite command** | backend: `cd backend && python -m pytest tests/test_ai_*.py -q` · frontend: `cd frontend && npx vitest run` |
| **Estimated runtime** | ~60s backend AI suite; ~90s frontend suite |

> Note (getvul backend pytest env): set `ENCRYPTION_KEY` (a real Fernet key) + `JWT_SECRET_KEY`, and run AI tests per-file/per-glob (`tests/test_ai_*.py`) — running the whole `tests/` dir yields false failures.

---

## Sampling Rate

- **After every task commit:** Run the quick run command for the touched side (backend / frontend)
- **After every plan wave:** Run the full suite command(s)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~90 seconds

---

## Per-Task Verification Map

*Filled by the planner (each task's `<automated>` verify) and reconciled by validate-phase / nyquist-auditor.*

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | — | — | AIR-01 / AIR-02 | T-25-xx | cite-or-refuse; dangerous-command refusal; no key leak | unit | `pytest tests/test_ai_*.py -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- Existing AI test infrastructure (`backend/tests/test_ai_*.py`, `backend/tests/conftest.py` fixtures, frontend `ai-*.test.tsx`) covers all Phase 25 requirements — Phase 24 established it. No new framework install needed.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Cited remediation steps render in the live drill panel with correct two-tier tinting; refusal + safety-refusal cards display correctly | AIR-01 | Requires live Docker stack + dev Anthropic key + browser observation (same class as Phase 24's waived live items) | Configure key → open a finding with vendor remediation text → "Get remediation guidance"; then a finding with none → expect insufficient-evidence card |

*Automated coverage proves the gate logic, schema, denylist, and API behavior in isolation; the live visual render is manual.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
