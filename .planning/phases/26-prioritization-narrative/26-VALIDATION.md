---
phase: 26
slug: prioritization-narrative
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-30
---

# Phase 26 — Validation Strategy

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

> getvul backend pytest env: set `ENCRYPTION_KEY` (real Fernet) + `JWT_SECRET_KEY`, run AI tests per-glob (`tests/test_ai_*.py`) — whole-`tests/` runs yield false failures. Postgres + Redis containers already up.

---

## Sampling Rate

- **After every task commit:** quick run for the touched side (backend / frontend)
- **After every plan wave:** full suite command(s)
- **Before `/gsd-verify-work`:** full suite green
- **Max feedback latency:** ~90 seconds

---

## Per-Task Verification Map

*Filled by the planner (each task's `<automated>` verify) and reconciled by validate-phase / nyquist-auditor.*

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | — | — | AIP-01 / AIP-02 | T-26-xx | no-rank schema/UI; batch cost booked at 50%; owner-PII excluded; budget fail-closed before batch submit | unit | `pytest tests/test_ai_*.py -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- Existing AI test infrastructure (`backend/tests/test_ai_*.py`, conftest fixtures, frontend `ai-*.test.tsx`) covers Phase 26. One new durable `AiBatchJob` table + migration (RESEARCH finding #3) needs its own test file (`tests/test_ai_batch_*.py`), created inline (TDD), not deferred.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live prioritization narrative render + the "being prepared" queued card; confirm NO sortable AI rank appears in any list/view | AIP-01 | Requires live Docker stack + configured Anthropic key + browser observation (same class as Phase 24/25 waived items) | Configure key → open a top-N finding → Prioritization section shows cited narrative; open a not-yet-batched finding → "being prepared" card; scan every list view → no AI rank column/sort |
| Live end-to-end batch: nightly job submits a Message Batch, polls to completion, writes narratives into cache | AIP-02 | Async batch (minutes–24h) through the real Anthropic Batches API needs a live key + wall-clock; automated tests use a fake batches client | Trigger the batch job for a seeded tenant; confirm an AiBatchJob row transitions submitted→completed and narratives become cache hits |

*Automated coverage proves the batch submit/poll/retrieve state machine (fake client), the top-N query, the 50%-cost booking, the budget pre-estimate gate, the no-rank schema, and the on-demand fallback in isolation; the live async round-trip is manual.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (AiBatchJob table/migration test)
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
