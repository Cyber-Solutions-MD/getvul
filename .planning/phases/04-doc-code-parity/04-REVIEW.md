---
phase: 04-doc-code-parity
reviewed: 2026-07-24T00:00:00Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - backend/app/config.py
  - backend/app/main.py
  - backend/app/vulnerabilities/models.py
  - backend/pyproject.toml
  - backend/tests/test_aws_removal.py
  - backend/tests/test_security_headers.py
  - backend/tests/test_vuln_source_filter.py
  - .env.example
  - docs/03-tech-stack.md
  - docs/05-configuration.md
  - docs/16-security.md
findings:
  critical: 0
  warning: 0
  info: 7
  total: 7
status: issues_found
reconciliation: "Re-review of shipped v1.0 phase against CURRENT code (2026-07-24). Both prior Warnings (WR-01, WR-02) verified FIXED and dropped. Prior Info items IN-01..IN-04 verified STILL PRESENT and retained. Three NEW Info-severity doc/code drift items surfaced (IN-05..IN-07). No Critical/Warning issues in current tree."
prior_warnings_verified_resolved:
  - "WR-01: docs CSP breakage — FIXED. main.py:171 DOCS_PATHS + main.py:184 debug-scoped exemption."
  - "WR-02: CSP test coverage gap — FIXED. test_security_headers.py adds 3 dispatch-level unit tests."
---

# Phase 4: Code Review Report (Re-Review)

**Reviewed:** 2026-07-24T00:00:00Z
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found (Info-only)

## Summary

This is a re-review of the shipped v1.0 doc/code-parity phase, verifying the
stale 2026-07-03 REVIEW.md (`status: resolved`) against the CURRENT tree after
v2.0/v2.1/v2.2 shipped. Each prior finding was re-checked against live code.

**Both prior Warnings are confirmed FIXED and are dropped from the active list:**

- **WR-01** (`default-src 'none'` CSP breaks Swagger UI / ReDoc in debug mode)
  is resolved. `main.py:171` now declares `DOCS_PATHS = frozenset({"/docs",
  "/redoc", "/openapi.json"})` and `main.py:184` skips the strict CSP for those
  paths **only when `settings.debug` is True** (`if not (settings.debug and
  request.url.path in DOCS_PATHS)`). In production (`debug=False`) the strict
  policy still covers the entire surface, and the docs routes are unmounted
  anyway (`main.py:288-289`). Verified against current code.
- **WR-02** (CSP test only covered a JSON route) is resolved.
  `test_security_headers.py` now adds three dispatch-level unit tests
  (`test_strict_csp_on_api_path`, `test_docs_routes_exempt_from_strict_csp_when_debug`,
  `test_docs_paths_get_strict_csp_when_not_debug`) that exercise the middleware
  branch directly — covering exactly the docs-exemption logic the `/health`
  integration test structurally could not. Verified against current code.

The AWS removal remains clean: `test_aws_removal.py` still guards that `boto3`
is uninstalled and that `Settings` has no `aws_region` / `secrets_manager_prefix`
fields, and `config.py` confirms no AWS fields remain. The `VulnSource` enum still
carries all six members including `QUALYS`/`RAPID7` (`models.py:31-37`), and the
insecure-looking config defaults (`jwt_secret_key`, `encryption_key` placeholders)
are gated by the production hard-fail in `_check_secrets_at_startup`
(`main.py:52-90`) — not a finding.

The four prior Info items all still exist in the current tree and are retained.
Three additional Info-severity doc/code drift items surfaced during this pass —
all documentation-accuracy issues in the very files this phase owns, so they are
squarely in scope for a doc/code-parity milestone. **No Critical or Warning
issues exist in the current tree.**

## Info

### IN-01: Stale `main.py` line-range anchor in security doc (verified against current code — now worse)

**File:** `docs/16-security.md:98`
**Issue:** The heading still reads
`SecurityHeadersMiddleware ([main.py:86-98](../backend/app/main.py#L86-L98))`.
In the current tree `SecurityHeadersMiddleware` lives at `main.py:174-191`; lines
`86-98` now fall inside `_check_secrets_at_startup` / the `lifespan` context
manager and point at completely unrelated code. This is the same stale anchor
flagged in 2026-07-03, and it has drifted further as `main.py` grew across later
milestones. Since this is a doc/code-parity artifact, the anchor should be
corrected.
**Fix:** Update the anchor to `main.py:174-191` (the current `SecurityHeadersMiddleware.dispatch`
span). The header value table itself (`16-security.md:100-112`) is accurate and
already documents the debug-only docs-route exemption.

### IN-02: `frame-ancestors 'none'` duplicates `X-Frame-Options: DENY` (verified — by design, no action)

**File:** `backend/app/main.py:178` and `main.py:185`
**Issue:** The middleware still sets both `X-Frame-Options: DENY` (line 178) and
CSP `frame-ancestors 'none'` (line 185). These express the same clickjacking
protection. Still present, still harmless belt-and-suspenders (modern browsers
honor `frame-ancestors`; older ones fall back to `X-Frame-Options`).
Informational only.
**Fix:** None required. Optionally note in `docs/16-security.md` that the two
overlap by design.

### IN-03: Frontend source-filter list still out of parity with the backend enum (verified — AWS residue relevant to this phase)

**File:** `frontend/src/app/(authed)/dashboard/vulnerabilities/page.tsx:27`
(out of the changed-file scope; noted for the parity backlog)
**Issue:** The backend `VulnSource` enum is
`{CROWDSTRIKE, NESSUS, DEFENDER, WIZ, QUALYS, RAPID7}` (`models.py:31-37`), but
the frontend still hardcodes
`SOURCES = ['QUALYS', 'TENABLE', 'RAPID7', 'CROWDSTRIKE', 'AWS_INSPECTOR', 'WIZ', 'MOCK']`.
The frontend list contains values not in the backend enum (`TENABLE`,
`AWS_INSPECTOR`, `MOCK`) and omits two that are (`NESSUS`, `DEFENDER`). Selecting
`TENABLE`/`AWS_INSPECTOR` in the UI yields zero rows, while `NESSUS`/`DEFENDER`
data is unfilterable from the dropdown. Notably, `AWS_INSPECTOR` is still offered
in the UI even though this phase removed AWS Secrets Manager / boto3 from the
backend — a small AWS-removal parity residue directly on this phase's theme. The
frontend file is unchanged since the original review, so this is unchanged drift.
**Fix:** Reconcile the frontend `SOURCES` constant with the backend `VulnSource`
enum (ideally derive it from an API-provided facet list), and capture the decision
on `TENABLE`/`AWS_INSPECTOR`/`MOCK`. Track as a follow-up parity item.

### IN-04: `source` query param still not validated against `VulnSource` (verified against current code)

**File:** `backend/app/vulnerabilities/router.py:55` (`source: list[str] | None = Query(None)`)
(out of the changed-file scope; behavioral context for the enum extension)
**Issue:** The list endpoint still accepts `source` as a free-form `list[str]`
and filters it directly against the `String(30)` column. An unknown value (e.g.
`?source=BOGUS`) silently returns an empty result set rather than a 422 — so the
extended `VulnSource` enum remains a documentation/test artifact rather than an
enforced API contract. Consistent with the pre-existing design; not introduced
by this phase. Note the endpoint DOES enforce `Literal` typing on `sort`, `order`,
and `group` (`router.py:66-84`), so `source` is a deliberate exception.
**Fix:** If enforcement is desired, type the query param as `list[VulnSource]` so
FastAPI rejects unknown sources with 422. Otherwise no change needed — just be
aware the enum does not gate the API.

### IN-05: Stale `main.py` line anchors in the configuration doc (new)

**File:** `docs/05-configuration.md:27`, `:28`, `:35`
**Issue:** Three cross-reference anchors in the config variable table point at
line ranges that no longer describe the referenced behavior in the current
`main.py`:
- Line 27 (`DEBUG`): anchors `main.py:174-181` for "Exposes `/docs`/`/redoc`;
  widens CORS to `http://localhost:3000`". Those lines are now the
  `SecurityHeadersMiddleware` header block; docs mounting is at `main.py:288-289`
  and CORS at `main.py:293-307`.
- Line 28 (`ENVIRONMENT`): anchors `main.py:40` for the scheduler start. Line 40
  is an import; the scheduler start is at `main.py:106-109`.
- Line 35 (`REDIS_URL`): anchors `main.py:45-50` for the lifespan Redis init.
  Lines 45-50 are the `ENCRYPTION_KEY_PLACEHOLDER` comment; Redis init is at
  `main.py:117-126`.
These are documentation-accuracy defects (no behavioral/security impact) but land
in a doc whose stated contract is to map each variable to where it is read. The
line drift accumulated as `main.py` grew across later milestones.
**Fix:** Repoint the three anchors (CORS/docs `288-307`, scheduler `106-109`,
Redis `117-126`), or replace brittle line-number anchors with symbol/section
references that survive refactors.

### IN-06: Tech-stack doc lists loose dev-tool versions that contradict the pinned `pyproject.toml` (new)

**File:** `docs/03-tech-stack.md:40-42`
**Issue:** The doc opens with "Every version below is read directly from the
lockfiles or workflow files," but the dev/test table lists `ruff >=0.8` and
`mypy >=1.13`, whereas `pyproject.toml:34-36` now pins `ruff==0.15.21` and
`mypy==2.1.0` (both hard-pinned specifically to keep the CI lint/type gate
deterministic) and adds `mypy-baseline==0.7.4`, which the doc omits entirely. The
pins were introduced after the original review, so the doc silently drifted. This
is a doc/code-parity defect in two files that are both in this phase's scope
(`docs/03-tech-stack.md` and `backend/pyproject.toml`).
**Fix:** Update the dev/test table to `ruff==0.15.21`, `mypy==2.1.0`, and add a
`mypy-baseline==0.7.4` row, noting the pins are intentional (CI determinism).

### IN-07: Configuration doc frames the AWS-removal decision as pending future work, though it is already done (new)

**File:** `docs/05-configuration.md:150`
**Issue:** The "Secret-management roadmap" closes with: "…Phase 4 (PROD-04-05)
will decide whether to wire AWS Secrets Manager or remove the unused config
fields." That decision has already been made and executed — this very phase
removed the AWS config fields and uninstalled `boto3`, and `test_aws_removal.py`
guards it. The doc still describes the outcome as undecided future work,
misdescribing the current state on exactly this phase's core deliverable (AWS
removal). Documentation-accuracy issue; no behavioral/security impact.
**Fix:** Rewrite the sentence to past tense — e.g. "Phase 4 (PROD-04-05) removed
the unused AWS Secrets Manager config fields and the `boto3` dependency; a KMS
integration remains out of scope." (`docs/03-tech-stack.md:108` retaining an
`infra/aws/main.tf` AWS *deploy-target* base image is correct and unrelated — that
is a Terraform deploy target, not the removed Secrets Manager/Inspector coupling.)

---

_Reviewed: 2026-07-24T00:00:00Z (re-review of 2026-07-03 original)_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
