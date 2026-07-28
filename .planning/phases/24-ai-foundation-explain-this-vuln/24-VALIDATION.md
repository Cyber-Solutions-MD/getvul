---
phase: 24
slug: ai-foundation-explain-this-vuln
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-28
---

# Phase 24 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from RESEARCH.md `## Validation Architecture`. Per-task map is filled during execution / `/gsd-validate-phase`.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend) / vitest + Playwright (frontend) |
| **Config file** | backend/pyproject.toml · frontend/vitest.config.ts |
| **Quick run command** | `cd backend && pytest tests/test_ai_*.py` |
| **Full suite command** | `cd backend && pytest` |
| **Estimated runtime** | ~60 seconds (backend AI subset) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_ai_*.py`
- **After every plan wave:** Run `pytest`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| _(seeded — planner/executor fills per-task rows against AI-01..AI-06)_ | | | | | | | | | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_ai_config.py` — stubs for AI-01 (per-tenant key, inert-until-keyed)
- [ ] `backend/tests/test_ai_prompt_builder.py` — stubs for AI-02 (untrusted-content-as-data, PII allowlist)
- [ ] `backend/tests/test_ai_explain.py` — stubs for AI-03/AI-04 (streaming, schema validation, two-tier citation)
- [ ] `backend/tests/test_ai_audit_cache.py` — stubs for AI-05/AI-06 (audit log, cross-tenant cache isolation)
- [ ] `backend/tests/conftest.py` — reuse existing `tenant_a`/`tenant_b`/`flushed_redis`/role fixtures + Anthropic client mock

*Existing conftest.py fixtures cover nearly every AI-01..AI-06 test need; the Anthropic client mock is the one new fixture.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `effort: "low"` actually works on `claude-haiku-4-5` | AI-01 | Requires a live tenant key; documented as unsupported in Anthropic effort docs (RESEARCH open question #1) | Configure a Haiku key, run one Explain call, confirm no API error |
| nginx does not buffer the incremental SSE stream | AI-03 | Requires the full nginx→backend deployment; unit tests can't observe proxy buffering | Run the drill-panel Explain against the Docker Compose stack, confirm token-by-token arrival |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
