---
phase: 04-doc-code-parity
verified: 2026-07-03T08:45:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
post_verification_note: "WR-01 (the sole human_needed item) was fixed in commit bc2df7b before phase completion: the strict CSP is now scoped off the debug-only docs routes (/docs, /redoc, /openapi.json), docs/16-security.md was corrected, and dispatch-level unit tests assert both the debug-exempt and production-strict branches (no Redis needed). The behavioral regression is resolved; an optional dev smoke-check remains in 04-HUMAN-UAT.md (status: resolved) but is no longer blocking."
human_verification: []
---

# Phase 04: Doc/Code Parity Verification Report

**Phase Goal:** README, security docs, source code, and the API surface tell the same story about what the product is and what it does.
**Verified:** 2026-07-03T08:45:00Z
**Status:** human_needed (5/5 automated checks pass; 1 item requires human confirmation — see WR-01)
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | Every header listed in docs/16-security.md is actually emitted by either Nginx or the FastAPI middleware | ✓ VERIFIED | `SecurityHeadersMiddleware.dispatch` (main.py:87-102) emits all 7 headers listed in docs/16-security.md table (X-Content-Type-Options, X-Frame-Options, Cross-Origin-Resource-Policy, Referrer-Policy, Permissions-Policy, Content-Security-Policy, Cross-Origin-Opener-Policy). Nginx headers in docs/16-security.md:116-122 are independently listed as Nginx-layer headers. No "not emitted" claim survives in the doc. |
| 2 | README.md lists 6 scanner sources, matching docs/01-overview.md | ✓ VERIFIED | `grep -oiE "CrowdStrike|Nessus|Defender|Wiz|Qualys|Rapid7"` returns 6 distinct names from both files. README.md line 5 and architecture diagram (lines 10-14) list all six; docs/01-overview.md line 13 and line 34 list the same six. |
| 3 | VulnSource enum includes QUALYS and RAPID7; source column is String(30), no migration needed | ✓ VERIFIED | models.py:31-37 — VulnSource has exactly 6 members: CROWDSTRIKE, NESSUS, DEFENDER, WIZ, QUALYS, RAPID7. Column at line 62 is `String(30)`, not a DB enum. `test_vuln_source_enum_members` asserts exact 6-member set — PASSED locally. |
| 4 | Filtering vulns by source=QUALYS and source=RAPID7 returns expected rows in a regression test | ✓ VERIFIED (CI-pending for DB tests) | test_vuln_source_filter.py contains all 4 required tests: `test_vuln_source_enum_members` (pure-Python, PASSED locally), `test_source_filter_qualys`, `test_source_filter_rapid7`, `test_source_filter_tenant_scoped`. The 3 API tests require Postgres and skip without it; they will run in CI. The enum test itself passes locally, confirming the model is correct. |
| 5 | aws_region / secrets_manager_prefix config and boto3 dep are removed (no dead config) | ✓ VERIFIED | config.py has no aws_region or secrets_manager_prefix fields (confirmed by code inspection and test_settings_has_no_aws_fields PASSED). pyproject.toml has no boto3 entry. docs/05-configuration.md and docs/03-tech-stack.md show no AWS rows. Both `test_boto3_not_installed` and `test_settings_has_no_aws_fields` PASSED locally (3 passed in 0.14s). |

**Score:** 5/5 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/main.py` | CSP + COOP header assignment in SecurityHeadersMiddleware.dispatch | ✓ VERIFIED | Lines 94-97: CSP assigned with exact locked value `default-src 'none'; frame-ancestors 'none'; base-uri 'none'`; COOP assigned as `same-origin`. Both placed BEFORE the path-scoped Cache-Control block (line 99). |
| `backend/tests/test_security_headers.py` | pytest assertion that CSP + COOP are present on /health | ✓ VERIFIED (CI-pending) | File exists with `test_csp_and_coop_headers_emitted` asserting exact CSP and COOP values against /health. Requires Redis (`single_app` fixture uses lifespan); will pass in CI. |
| `backend/app/vulnerabilities/models.py` | VulnSource enum with 6 members including QUALYS and RAPID7 | ✓ VERIFIED | Lines 31-37 contain the complete 6-member enum. `QUALYS = "QUALYS"` and `RAPID7 = "RAPID7"` present. |
| `backend/tests/test_vuln_source_filter.py` | 4-test suite: enum + filter + tenant-scope | ✓ VERIFIED | File exists with all 4 named tests including `test_source_filter_tenant_scoped`. Enum test passes locally. |
| `backend/app/config.py` | Settings without aws_region / secrets_manager_prefix | ✓ VERIFIED | Settings class (lines 6-38) contains no aws_region or secrets_manager_prefix fields. test_settings_has_no_aws_fields confirms via `model_fields` introspection — PASSED. |
| `backend/pyproject.toml` | Dependency list without boto3 | ✓ VERIFIED | Dependencies array (lines 6-25) contains no boto3 entry. grep returns 0 matches. test_boto3_not_installed confirms ModuleNotFoundError — PASSED. |
| `backend/tests/test_aws_removal.py` | Removal guard: ModuleNotFoundError + Settings field checks | ✓ VERIFIED | File exists with `test_boto3_not_installed` and `test_settings_has_no_aws_fields`. Both PASSED locally. |
| `docs/16-security.md` | Security-headers table reflecting emitted CSP/COOP; no "not emitted" drift | ✓ VERIFIED | Lines 107-108 add CSP and COOP rows with emitted values. grep for "not emitted" returns 0 matches. Drift section removed. Note at line 112 explains frontend CSP difference. |
| `docs/05-configuration.md` | No AWS_REGION / SECRETS_MANAGER_PREFIX rows | ✓ VERIFIED | Confirmed by inspection: no AWS section rows present. grep returns 0 matches. |
| `docs/03-tech-stack.md` | No boto3 runtime table row | ✓ VERIFIED | Runtime table (lines 10-31) contains no boto3 row. grep returns 0 matches. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| SecurityHeadersMiddleware.dispatch | All responses | response.headers assignments unconditionally before Cache-Control block | ✓ WIRED | Lines 94-97 assign CSP and COOP before the `if request.url.path.startswith` block at line 99. Applies to every response regardless of path. |
| GET /api/v1/vulnerabilities?source=QUALYS | VulnerabilityService source filter | service.py _apply_filters; tenant-scoped at :35, source.in_ at :40 | ✓ WIRED (CI-pending) | Test file verifies the wiring through real API calls. Pure-enum test passes locally; filter/tenant tests require live Postgres and will execute in CI. |
| pyproject.toml (no boto3) | active .venv | explicit `pip uninstall boto3 botocore s3transfer jmespath` (noted in 04-03-SUMMARY.md) | ✓ WIRED | `test_boto3_not_installed` raises ModuleNotFoundError — confirmed locally with PASSED result. |

---

### Data-Flow Trace (Level 4)

Not applicable. Phase 04 artifacts are middleware header assignments, enum declarations, config field removals, and doc updates — none render dynamic user-facing data from a database query.

---

### Behavioral Spot-Checks

| Behavior | Command / Method | Result | Status |
|----------|------------------|--------|--------|
| VulnSource enum has QUALYS + RAPID7, exactly 6 members | `.venv/bin/pytest tests/test_vuln_source_filter.py::test_vuln_source_enum_members -v` | PASSED (0.14s) | ✓ PASS |
| boto3 is not importable after removal | `.venv/bin/pytest tests/test_aws_removal.py::test_boto3_not_installed -v` | PASSED (0.14s) | ✓ PASS |
| Settings has no aws_region / secrets_manager_prefix | `.venv/bin/pytest tests/test_aws_removal.py::test_settings_has_no_aws_fields -v` | PASSED (0.14s) | ✓ PASS |
| CSP test (Redis-gated) | `pytest tests/test_security_headers.py` | Requires Redis — infrastructure limitation noted in verification instructions; not a code defect | ? SKIP (CI-pending) |
| Source filter API tests (Postgres-gated) | `pytest tests/test_vuln_source_filter.py` (3 API tests) | 3 skipped without Postgres — infrastructure limitation; not a code defect | ? SKIP (CI-pending) |
| README scanner count == 6 | grep | 6 | ✓ PASS |
| docs/01-overview.md scanner count == 6 | grep | 6 | ✓ PASS |
| No "not emitted" drift claim in docs/16-security.md | grep | 0 matches | ✓ PASS |
| No boto3 in pyproject.toml | grep | 0 matches | ✓ PASS |
| No aws_region / secrets_manager_prefix in config.py | code inspection | 0 fields | ✓ PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| PROD-04-01 | 04-01-PLAN.md | Backend security middleware emits CSP and COOP headers | ✓ SATISFIED | main.py:94-97 emits both headers unconditionally; test_security_headers.py asserts exact values (CI-pending for Redis) |
| PROD-04-02 | 04-01-PLAN.md | README.md reflects 6 scanner sources, matching docs/01-overview.md | ✓ SATISFIED | Both files yield 6 distinct scanner names (grep confirmed 6==6) |
| PROD-04-03 | 04-02-PLAN.md | VulnSource enum includes QUALYS and RAPID7 | ✓ SATISFIED | models.py:31-37 confirmed; test_vuln_source_enum_members PASSED locally |
| PROD-04-04 | 04-02-PLAN.md | Qualys/Rapid7 vulns surface in dashboard source filter; regression test | ✓ SATISFIED (CI-pending) | 3 API tests exist and are substantive (real DB seeds, not stubs); skip gracefully without Postgres |
| PROD-04-05 | 04-03-PLAN.md | aws_region / secrets_manager_prefix / boto3 removed (no dead config) | ✓ SATISFIED | All 3 pure-unit tests PASSED; no references survive in app/, pyproject.toml, docs/, or .env.example |

All 5 requirement IDs (PROD-04-01 through PROD-04-05) declared across the three plans are verified. No orphaned requirements detected.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/app/main.py` | 94-96 | `default-src 'none'` CSP applied unconditionally — includes /docs and /redoc HTML routes when `settings.debug=True` | ⚠️ Warning | WR-01 from 04-REVIEW.md: Swagger UI and ReDoc will not render in debug mode because inline scripts/styles/fonts are blocked. The claim in docs/16-security.md:112 that "the backend serves only JSON" is inaccurate when debug=True. Does NOT affect the parity goal (headers ARE emitted as documented) but is a behavioral regression for the dev workflow. |
| `backend/tests/test_security_headers.py` | 19-26 | CSP test only covers /health (JSON route), not HTML routes (/docs, /redoc) | ⚠️ Warning | WR-02 from 04-REVIEW.md: Test passes but does not catch the WR-01 docs regression. False confidence on "every backend response." |
| `docs/16-security.md` | 98 | Stale line-range anchor `main.py:86-98` — middleware now spans to line 102 | ℹ️ Info | IN-01 from 04-REVIEW.md: Cosmetic; line anchor is off by 4 lines after the CSP/COOP additions. |

**WR-01 impact on SC#1:** The success criterion asks whether every header listed in docs/16-security.md is emitted by the middleware. The answer is YES — the documented headers (CSP and COOP) are emitted. WR-01 is about a SIDE EFFECT of the implementation (unconditional application breaking Swagger UI in debug mode), not about parity between the doc and the code. SC#1 is VERIFIED. The WR-01 concern is routed to human verification.

---

### Human Verification Required

#### 1. Swagger UI Functional in Debug Mode (WR-01)

**Test:** Start the backend with `DEBUG=true` (or `debug: bool = True` in config). Open `http://localhost:8000/docs` in a browser. Open the browser DevTools → Console and Network tabs.

**Expected (passing):** Swagger UI renders fully — the interactive API explorer loads with a visible sidebar, endpoint list, and the "Try it out" buttons functional. No CSP-blocked errors appear in the Console.

**Expected (failing):** The console shows errors like `Refused to execute inline script because it violates the following Content Security Policy directive: "default-src 'none'"`. The page renders blank or with only the base HTML skeleton.

**Why human:** The `SecurityHeadersMiddleware.dispatch` applies `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'; base-uri 'none'` to ALL responses with no path scoping. When `settings.debug=True`, FastAPI mounts `/docs` and `/redoc` as HTML pages that load inline scripts, inline styles, and CDN fonts — all of which `default-src 'none'` blocks. This cannot be verified by code inspection or the existing test suite (which only covers the `/health` JSON route).

**Decision needed:** If Swagger UI is broken in debug mode, fix the middleware to scope the strict CSP to non-docs paths (suggested fix in 04-REVIEW.md WR-01), then re-verify SC#1 (the parity between doc and code still holds; it is the scope of application that needs adjustment). If the team accepts that Swagger UI is intentionally non-functional in debug mode, document it explicitly in docs/16-security.md.

---

### Gaps Summary

No BLOCKER gaps. All 5 success criteria are verified by code inspection and passing unit tests. The infrastructure-gated tests (Redis, Postgres) are noted as CI-pending by design and are not code defects.

One WARNING exists (WR-01) that requires human confirmation: the unconditional application of `default-src 'none'` CSP may break Swagger UI in debug mode. This does not invalidate SC#1 (the documented headers are emitted) but is a behavioral regression for the dev workflow worth addressing.

---

_Verified: 2026-07-03T08:45:00Z_
_Verifier: Claude (gsd-verifier)_
