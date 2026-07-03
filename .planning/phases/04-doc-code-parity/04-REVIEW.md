---
phase: 04-doc-code-parity
reviewed: 2026-07-03T08:21:54Z
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
  warning: 2
  info: 4
  total: 6
status: issues_found
---

# Phase 4: Code Review Report

**Reviewed:** 2026-07-03T08:21:54Z
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

This phase performs three doc/code-parity changes: (1) adds `Content-Security-Policy`
and `Cross-Origin-Opener-Policy` headers to `SecurityHeadersMiddleware`, (2) extends
the `VulnSource` enum with `QUALYS` and `RAPID7`, and (3) removes AWS Secrets
Manager / boto3 config exhaustively (dependency, config fields, `.env.example`
entries, and doc tables). Three new test modules guard each change.

The AWS removal is clean and exhaustive — no residual references remain in `app/`
code (only unrelated third-party `pydantic_settings`/`mypy` stdlib references, which
are irrelevant). The enum extension matches the values written by the existing
`qualys.py` (`source_name = "QUALYS"`) and `rapid7.py` (`source_name = "RAPID7"`)
connectors, and requires no DB migration because `Vulnerability.source` is a plain
`String(30)` column, not a Postgres native enum. All test fixtures referenced by the
new tests (`single_app`, `client`, `client_factory`, `db_session`, `tenant_a`,
`tenant_b`, `analyst_user`) exist in `conftest.py`.

Two correctness concerns are worth flagging. First, the new `default-src 'none'`
CSP is applied to **every** response — including the Swagger UI (`/docs`) and ReDoc
(`/redoc`) HTML pages that the app serves when `settings.debug=True`. That CSP will
break those interactive docs pages in the browser, and no test covers an HTML route.
Second, the new CSP test only asserts against `/health` (JSON), so it cannot detect
the docs regression above and gives a false sense of full coverage.

## Warnings

### WR-01: `default-src 'none'` CSP breaks Swagger UI / ReDoc in debug mode

**File:** `backend/app/main.py:94-96` (applied unconditionally in `dispatch`)
**Issue:** `SecurityHeadersMiddleware.dispatch` sets
`Content-Security-Policy: default-src 'none'; frame-ancestors 'none'; base-uri 'none'`
on **all** responses. But `create_app` still mounts interactive API docs when
`settings.debug` is true (`docs_url="/docs"`, `redoc_url="/redoc"`,
`backend/app/main.py:178-179`). Swagger UI and ReDoc are HTML pages that load
inline scripts, inline styles, and (for Swagger UI) fonts/images — all of which a
`default-src 'none'` policy with no `script-src`/`style-src`/`img-src`/`connect-src`
directives will block. In a debug/dev deployment the `/docs` and `/redoc` pages will
render blank or non-functional. The doc rationale ("the backend serves only JSON",
`docs/16-security.md:112`) is inaccurate: the backend also serves these HTML pages
when debug is on. This is a behavioral regression for the dev workflow, not just a
style nit.
**Fix:** Scope the strict CSP to non-docs paths, or relax it for the docs routes.
For example, skip the API-oriented CSP for the docs paths and let FastAPI's docs
render:
```python
async def dispatch(self, request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    # Docs pages need a relaxed CSP; JSON API gets the strict one.
    if request.url.path in ("/docs", "/redoc", "/openapi.json") or \
            request.url.path.startswith("/docs"):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: https://fastapi.tiangolo.com; frame-ancestors 'none'"
        )
    else:
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        )
    ...
```
Alternatively, if breaking `/docs` under debug is acceptable, document that
explicitly and confirm docs are never mounted in any environment that matters.

### WR-02: CSP test only covers a JSON route, so it cannot catch the docs regression

**File:** `backend/tests/test_security_headers.py:19-26`
**Issue:** `test_csp_and_coop_headers_emitted` only hits `/health` (a JSON
endpoint). It confirms the headers are emitted but provides no coverage for HTML
routes (`/docs`, `/redoc`), which is exactly where the `default-src 'none'` policy
causes the WR-01 regression. The test's own docstring
(`test_security_headers.py:5`, "every backend response carries…") overstates what is
actually verified. Passing this test gives false confidence that the CSP is safe for
all response types.
**Fix:** Either (a) add a test that fetches `/docs` under `settings.debug=True` and
asserts the docs HTML is served with a CSP that permits its own scripts/styles, or
(b) after fixing WR-01, keep the strict-CSP assertion on `/health` and add a second
assertion that the docs path receives the relaxed policy. At minimum, tighten the
docstring to say "every JSON API response" rather than "every backend response".

## Info

### IN-01: Stale line-range reference in security doc for the middleware

**File:** `docs/16-security.md:98`
**Issue:** The heading references
`SecurityHeadersMiddleware ([main.py:86-98](../backend/app/main.py#L86-L98))`.
After this phase added the CSP + COOP lines, the middleware class now spans
`main.py:86-102`, and the closing `return response` plus the cache-control block sit
at lines 98-102. The `86-98` range now truncates mid-method. Since this is
explicitly a doc/code-parity phase, the line anchor should be corrected.
**Fix:** Update the anchor to `main.py:86-102` (or a stable range that covers the
full `dispatch` method).

### IN-02: `frame-ancestors 'none'` duplicates existing `X-Frame-Options: DENY`

**File:** `backend/app/main.py:90` and `main.py:95`
**Issue:** The middleware sets both `X-Frame-Options: DENY` (line 90) and CSP
`frame-ancestors 'none'` (line 95). These express the same clickjacking protection.
This is harmless (modern browsers honor `frame-ancestors`; older ones fall back to
`X-Frame-Options`) and is arguably intentional belt-and-suspenders, so this is
informational only — no action required unless you want to trim redundancy.
**Fix:** None required. Optionally note in `docs/16-security.md` that the two
overlap by design.

### IN-03: Frontend source filter list is out of parity with the backend enum

**File:** `frontend/src/app/(authed)/dashboard/vulnerabilities/page.tsx:27`
(out of the changed-file scope for this phase; noted for the parity backlog)
**Issue:** The backend `VulnSource` enum is now
`{CROWDSTRIKE, NESSUS, DEFENDER, WIZ, QUALYS, RAPID7}`, but the frontend hardcodes
`SOURCES = ['QUALYS', 'TENABLE', 'RAPID7', 'CROWDSTRIKE', 'AWS_INSPECTOR', 'WIZ', 'MOCK']`.
The frontend list contains values not in the backend enum (`TENABLE`,
`AWS_INSPECTOR`, `MOCK`) and omits two that are (`NESSUS`, `DEFENDER`). A user can
select `TENABLE`/`AWS_INSPECTOR` in the UI and get zero rows, while `NESSUS`/
`DEFENDER` data is unfilterable from the dropdown. This drift is pre-existing (the
frontend file is unchanged by this phase) and is out of the reviewed scope, but a
doc/code-parity milestone is the right place to log it.
**Fix:** Reconcile the frontend `SOURCES` constant with the backend `VulnSource`
enum (ideally derive it from an API-provided facet list rather than hardcoding), and
capture the decision on `TENABLE`/`AWS_INSPECTOR`/`MOCK` (drop them or add backend
support). Track as a follow-up parity item.

### IN-04: `source` query param is not validated against `VulnSource`

**File:** `backend/app/vulnerabilities/router.py:55` (`source: list[str] | None`)
(out of the changed-file scope; behavioral context for the enum extension)
**Issue:** The extended `VulnSource` enum is used only in the model definition and
the new test — the vulnerabilities list endpoint accepts `source` as a free-form
`list[str]` and filters it directly against the `String(30)` column. An unknown
value (e.g. `?source=BOGUS`) silently returns an empty result set rather than a 422.
This is consistent with the pre-existing design and not introduced by this phase, so
it is informational. It does mean the enum is a documentation/test artifact rather
than an enforced API contract.
**Fix:** If enforcement is desired, type the query param as `list[VulnSource]` so
FastAPI rejects unknown sources with 422. Otherwise, no change needed — just be
aware the enum does not gate the API.

---

_Reviewed: 2026-07-03T08:21:54Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
