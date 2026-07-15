---
phase: 4
slug: doc-code-parity
status: complete
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-02
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3 + pytest-asyncio 0.24 (`asyncio_mode = "auto"`) |
| **Config file** | `backend/pyproject.toml` `[tool.pytest.ini_options]` (`testpaths = ["tests"]`) |
| **Quick run command** | `cd backend && pytest tests/test_security_headers.py tests/test_vuln_source_filter.py -v` |
| **Full suite command** | `cd backend && pytest -v --cov=app --cov-report=xml` |
| **Estimated runtime** | ~30 seconds (quick) / ~2–4 min (full suite) |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && pytest tests/test_security_headers.py tests/test_vuln_source_filter.py -v`
- **After every plan wave:** Run `cd backend && pytest -v --cov=app --cov-report=xml`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds (quick), 240 seconds (full)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-* | 01 | 1 | PROD-04-01 | T-04-01 / T-04-02 | `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'; base-uri 'none'` and `Cross-Origin-Opener-Policy: same-origin` present on all responses | unit/middleware | `pytest tests/test_security_headers.py -v` | ✅ | ✅ green |
| 04-02-* | 02 | 1 | PROD-04-03 | — | VulnSource enum contains QUALYS and RAPID7 | unit | `pytest tests/test_vuln_source_filter.py::test_vuln_source_enum_members -v` | ✅ | ✅ green |
| 04-02-* | 02 | 1 | PROD-04-04 | T-04-03 | `GET /api/v1/vulnerabilities?source=QUALYS` (and `RAPID7`) returns only matching rows, tenant-scoped | integration | `pytest tests/test_vuln_source_filter.py -v` | ✅ | ✅ green |
| 04-03-* | 03 | 1 | PROD-04-05 | — | `boto3` not importable; `aws_region` / `secrets_manager_prefix` absent from Settings | unit | `pytest tests/test_aws_removal.py -v` (or assertion in test_security_headers.py) | ✅ | ✅ green |
| 04-01-* | 01 | 1 | PROD-04-02 | — | README lists same 6 scanners as docs/01-overview.md | verify-only | `grep -c "CrowdStrike\|Nessus\|Defender\|Wiz\|Qualys\|Rapid7" README.md` | N/A | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_security_headers.py` — stubs for PROD-04-01 (CSP + COOP presence + exact values)
- [ ] `backend/tests/test_vuln_source_filter.py` — stubs for PROD-04-03 (enum members) + PROD-04-04 (API source filter + tenant scope)
- [ ] `backend/tests/test_aws_removal.py` (optional) — stub for PROD-04-05, OR fold boto3/config assertions into `test_security_headers.py`

*Existing infrastructure (pytest, conftest.py fixtures: `client`, `client_factory`, `db_session`, `tenant_a`, `tenant_b`, `analyst_user`, `single_app`) covers all harness needs — no framework install required.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `.env` AWS lines removed on dev VM | PROD-04-05 | `.env` is not git-tracked; may require operator write access | Run `sed -i '/^AWS_REGION=/d; /^SECRETS_MANAGER_PREFIX=/d' .env`; confirm lines gone. Harmless no-op if config.py fields already removed (pydantic ignores unknown vars). |
| `docs/16-security.md` drift rows flipped | PROD-04-01 | Doc prose accuracy, not machine-assertable value | Confirm lines ~112-117 no longer say "✗ not emitted" for CSP/COOP; reflect emitted values. `grep -c "not emitted" docs/16-security.md` should not match CSP/COOP rows. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 240s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

---

## Validation Audit 2026-07-15 (post-BL-05 backend sweep)

Reconciled against the shipped suite. Pre-execution statuses were `⬜ pending` / `❌ W0`; every
automated row now maps to an existing, passing test (Backend CI green on main).

| Metric | Count |
|--------|-------|
| Automated rows | 5 |
| Covered (green) | 5 |
| Gaps found | 0 |
| New tests written | 0 |
| Escalated to manual-only | 0 |

Evidence: `test_security_headers.py` (CSP/COOP), `test_vuln_source_filter.py` (enum + source
filter + tenant scope), `test_aws_removal.py` (boto3 unimportable + settings fields absent),
README/overview 6-scanner parity grep. **Nyquist-compliant.**
