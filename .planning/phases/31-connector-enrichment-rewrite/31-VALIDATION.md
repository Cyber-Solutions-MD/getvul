---
phase: 31
slug: connector-enrichment-rewrite
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-05
---

# Phase 31 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `31-RESEARCH.md` §Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest `>=8.3` + `pytest-asyncio>=0.24` (backend/pyproject.toml dev extras) |
| **Config file** | `backend/pyproject.toml` (dev extras) — no separate `pytest.ini` |
| **Quick run command** | `ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") JWT_SECRET_KEY=test-secret pytest tests/<one-file>.py -x` |
| **Full suite command** | Same env vars; run each affected test file individually (NOT `pytest tests/` in one invocation) |
| **Estimated runtime** | ~5–15 s per file |

> **MEMORY: `getvul-backend-pytest-env`** — set `ENCRYPTION_KEY`/`JWT_SECRET_KEY` and run per-file; running the whole `tests/` directory at once produces false failures.
>
> **HTTP mocking convention** — no `respx`/`pytest-httpx` in this repo. Established pattern is monkeypatching `httpx.AsyncClient.__init__` to inject an `httpx.MockTransport(handler)` (the `_install_mock_transport` helper reused across every `tests/test_connectors/test_*_connector.py`). New EPSS/KEV fetch tests MUST follow this convention — do not add a mocking library.

---

## Sampling Rate

- **After every task commit:** Run the per-file quick command for the file(s) that task touched.
- **After every plan wave:** Run each touched test file individually — `test_connector_normalization.py`, the six `tests/test_connectors/test_*_connector.py` files, `test_scheduler_enrichment_refresh.py`, plus `test_connector_health.py` / `test_scheduler_ai_batch.py` as regression guards on the existing scheduler dispatch idioms.
- **Before `/gsd-verify-work`:** Full suite (per-file) must be green.
- **Max feedback latency:** ~15 seconds.

---

## Per-Task Verification Map

> Populated by the planner as tasks are assigned plan/wave IDs. Requirement → behavior → test mapping below is the authoritative source; task IDs are filled once PLAN.md exists.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| _tbd_ | — | — | ENRICH-01 | — | EPSS score+percentile populated at `_upsert_vulnerability` for a finding from any source | integration | `pytest tests/test_connector_normalization.py -k epss -x` | ❌ W0 | ⬜ pending |
| _tbd_ | — | — | ENRICH-02 | — | KEV-listed CVE → `cisa_kev=True` for every connector; Defender flips from its old hardcode | integration | `pytest tests/test_connector_normalization.py -k kev -x` | ❌ W0 | ⬜ pending |
| _tbd_ | — | — | ENRICH-03 | — | `native_priority_score`/`rating` populated per connector; DB-level `ORDER BY` sortable | unit + integration | `pytest tests/test_connectors/test_crowdstrike_connector.py -k exprt -x` (+ siblings) | ❌ W0 | ⬜ pending |
| _tbd_ | — | — | ENRICH-04 | V8 | Missing vs negative fixture (Defender always-present exploit booleans vs confirmed-absent VPR-equiv) | unit | `pytest tests/test_connectors/test_defender_connector.py -k source_signals -x` | ❌ W0 | ⬜ pending |
| _tbd_ | — | — | ENRICH-05 | T-31 (feed) | 24h-gate + eager-first-run + atomic-swap-keeps-last-good | unit + integration | `pytest tests/test_scheduler_enrichment_refresh.py -x` | ❌ W0 | ⬜ pending |
| _tbd_ | — | — | ENRICH-06 | — | All 6 connectors' `_normalize_vuln` set the 3 new dataclass fields (None for Defender/Wiz intentionally) | unit (parametrized ×6) | `pytest tests/test_connector_normalization.py -x` | ✅ (extends) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_scheduler_enrichment_refresh.py` — new file, mirrors `test_scheduler_ai_batch.py` structure (24h-gate test, eager-first-run test, atomic-swap-keeps-last-good test via a monkeypatched fetcher that raises mid-parse)
- [ ] EPSS/KEV fixture rows for `db_session` — small hand-authored 3–5 CVE fixture (NOT the full 355k/1.6k real feed) for integration tests
- [ ] SC#4 fixture — anchor on **Defender**: `exploitVerified`/`publicExploit` are confirmed always-present booleans and Defender has no VPR-equivalent, making the "missing" half of the assertion a structurally guaranteed true negative
- [ ] EPSS/KEV feed-fetch/parse unit tests using the `MockTransport` convention (comment-header EPSS CSV; `{catalogVersion,count,vulnerabilities[]}` KEV JSON)

*No new test framework/config install needed — pytest/pytest-asyncio/httpx already present; only new test files + fixtures.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real live-feed fetch against FIRST.org / CISA endpoints | ENRICH-05 | Network egress + large payload; not run in CI | One-off: trigger the refresh async-def against real URLs in a dev shell, confirm ref tables populate + row counts (~355k EPSS, ~1.6k KEV) |

*All automated-testable behaviors have automated verification above; only the real-network fetch is manual.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
