# Phase 4: Doc/Code Parity - Context

**Gathered:** 2026-07-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Make README, security docs, source code, and the API surface tell the same story
about what the product is and does. Four concrete parity fixes:

1. Ship the CSP + COOP response headers the security doc references but the backend
   never emitted.
2. Confirm the README scanner count matches reality (already 6 — verify-only).
3. Extend the `VulnSource` enum to list all 6 sources and prove Qualys/Rapid7 vulns
   filter correctly.
4. Resolve the dead AWS Secrets Manager config: remove it.

This is a parity/cleanup phase. It does NOT add capabilities. It does NOT touch the
encryption-key lifecycle (that is Phase 5 / PROD-05) — the only intersection is that
removing the Secrets Manager config reaffirms Fernet-in-`.env` as the credential story.

</domain>

<decisions>
## Implementation Decisions

### Secrets Manager (PROD-04-05) — REMOVE
- **D-01:** Remove AWS Secrets Manager entirely. Nothing consumes `aws_region` /
  `secrets_manager_prefix` or `boto3`; the deploy model is single-VM (HA/multi-region
  is Out of Scope); connector credentials are encrypted with Fernet-in-`.env`. There
  is no product need for a second secret backend.
- **D-02:** Removal is exhaustive — **config vars + dep + all references**. Every one
  of these must be scrubbed so no dangling reference survives:
  - `backend/app/config.py:38-39` — delete `aws_region` and `secrets_manager_prefix`
  - `backend/pyproject.toml:17` — remove `boto3>=1.35` **and** regenerate/prune `uv.lock`
  - `docs/05-configuration.md:84-85` — delete the `AWS_REGION` / `SECRETS_MANAGER_PREFIX` rows
  - `docs/03-tech-stack.md:23` — delete the `boto3` row
  - `.env:14-15` and `.env.example:14-15` — delete both AWS lines
- **D-03:** No tombstone comment/ADR requested — a clean removal. (Rationale lives in
  this CONTEXT + the phase commit; that is sufficient provenance.)
- **D-04:** No `infra/` Terraform references to the config were found during scout — but
  planning should re-grep `infra/` to confirm nothing was missed before declaring done.

### CSP / COOP headers (PROD-04-01) — SHIP ON BACKEND MIDDLEWARE
- **D-05:** Emit both headers from the backend `SecurityHeadersMiddleware`
  (`backend/app/main.py:86`) **only** — not Nginx. This makes the `docs/16-security.md`
  claim true at the source, keeps one source of truth, and survives direct-to-backend
  calls that bypass Nginx. (SC#1 permits Nginx OR middleware; middleware chosen.)
- **D-06:** CSP value is the locked-down API policy:
  `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'; base-uri 'none'`.
  The backend serves JSON API + auth responses that load no resources, so the tightest
  policy is correct and cannot break rendering (the frontend renders HTML with its own
  CSP in `next.config.js`). Do NOT mirror the frontend CSP — that creates drift.
- **D-07:** COOP value is `Cross-Origin-Opener-Policy: same-origin` — matches the value
  the frontend already sets (`next.config.js:16`) and is the standard hardening value.
  Not `same-origin-allow-popups`: GetVul OIDC is redirect-based, no popup depends on
  `window.opener`.
- **D-08:** Enforcing mode from the start (NOT `Content-Security-Policy-Report-Only`) —
  an API that loads nothing has no observation phase to justify; report-only would just
  add a reporting endpoint for no benefit.
- **D-09:** After shipping, update `docs/16-security.md` — the table at lines ~112-117
  currently documents CSP/COOP as "✗ not emitted (PROD-04-01)"; flip those rows to
  reflect the now-emitted headers and their values.

### VulnSource enum + regression (PROD-04-03 / PROD-04-04) — PARITY ONLY
- **D-10:** Add `QUALYS = "QUALYS"` and `RAPID7 = "RAPID7"` to the `VulnSource` enum at
  `backend/app/vulnerabilities/models.py:31`. That is the whole enum change.
- **D-11:** **No DB migration and no backfill.** The `source` column is `String(30)`
  (models.py:60), not a DB enum, so Qualys/Rapid7 rows already persist as strings and no
  validation gate rejects them. The enum is currently dead code (imported nowhere in
  `backend/app/`); adding members keeps it a canonical reference list.
- **D-12:** Do NOT wire the enum into write-validation or connector `source_name` in this
  phase. That expands blast radius across connectors/API and is scope creep for a parity
  fix. (Noted as a deferred idea below.)
- **D-13:** Regression test is **API-level** (PROD-04-04): seed Qualys + Rapid7 vulns for
  a tenant, call the vulnerabilities list endpoint with `source=QUALYS` and `source=RAPID7`,
  assert the correct rows return and remain tenant-scoped. Tests the real dashboard filter
  path, not just the query layer. Planning should follow existing vulnerabilities-test
  patterns in the suite for fixtures/harness.

### README scanner count (PROD-04-02) — VERIFY-ONLY
- **D-14:** `README.md:5` and `README.md:11` already list all 6 scanners (CrowdStrike,
  Nessus, Defender, Wiz, Qualys, Rapid7), matching `docs/01-overview.md`. Treat as a
  verification checkbox — assert parity, no edit expected. If a diff against
  `docs/01-overview.md` surfaces a discrepancy, fix README to match.

### Verification strategy (SC#1)
- **D-15:** Primary gate is a **pytest assertion**: hit a representative endpoint and
  assert `Content-Security-Policy` and `Cross-Origin-Opener-Policy` are present with the
  expected values. This runs on every PR via the Phase 2 CI gate — fast, deterministic,
  the real regression guard.
- **D-16:** ZAP is a **secondary, advisory** safety net only. It will naturally stop
  reporting the missing-CSP finding once the header ships. **Do NOT modify ZAP gating or
  config** — Phase 2 deliberately settled ZAP as advisory/nightly-only, and this phase
  does not reopen that policy. No new ZAP rule authored.

### Claude's Discretion
- Exact pytest file/location and fixture reuse for both the header assertion (D-15) and
  the source-filter regression (D-13) — follow existing backend test conventions.
- Whether the CSP header applies to all responses or is scoped like the existing
  `Cache-Control` block in the middleware — default to all responses unless a conflict
  surfaces.
- `uv.lock` regeneration mechanics after dropping `boto3`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` §"Phase 4: Doc/Code Parity" — goal + 5 success criteria
- `.planning/REQUIREMENTS.md` — PROD-04-01 through PROD-04-05

### CSP / COOP headers (PROD-04-01)
- `backend/app/main.py:86` — `SecurityHeadersMiddleware.dispatch` (where CSP+COOP get added)
- `docs/16-security.md` §"Security headers" (~lines 96-133) — the doc claims to reconcile;
  lines ~112-117 currently mark CSP/COOP as "✗ not emitted" and must be flipped after ship
- `frontend/next.config.js:12-18` — the frontend's existing CSP/COOP values (reference for
  COOP `same-origin`; the backend policy is deliberately different/stricter, not a copy)
- `nginx/nginx.conf:29-32,119` — existing edge headers; context only — CSP/COOP are NOT
  being added here (D-05)

### VulnSource enum + regression (PROD-04-03 / 04)
- `backend/app/vulnerabilities/models.py:31` — `VulnSource` enum (add QUALYS + RAPID7)
- `backend/app/vulnerabilities/models.py:60` — `source` column is `String(30)` (why no migration)
- `backend/app/connectors/qualys.py:32`, `backend/app/connectors/rapid7.py:23` — connectors
  already emit `source_name = "QUALYS"/"RAPID7"` (parity target)

### Secrets Manager removal (PROD-04-05)
- `backend/app/config.py:38-39` — `aws_region`, `secrets_manager_prefix`
- `backend/pyproject.toml:17` — `boto3>=1.35` (+ `backend/uv.lock`)
- `docs/05-configuration.md:84-85` — env-var doc rows
- `docs/03-tech-stack.md:23` — boto3 tech-stack row
- `.env:14-15`, `.env.example:14-15` — AWS env lines

### README parity (PROD-04-02)
- `README.md:5,11` — scanner list (already 6)
- `docs/01-overview.md` — the source of truth README must match

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SecurityHeadersMiddleware` (`backend/app/main.py:86`): already emits X-Content-Type-Options,
  X-Frame-Options, Cross-Origin-Resource-Policy, Referrer-Policy, Permissions-Policy, and a
  path-scoped Cache-Control block. CSP + COOP are two more `response.headers[...] =` lines in
  the same `dispatch` method — no new middleware needed.
- Existing vulnerabilities test suite provides the fixture/harness patterns for the D-13
  source-filter regression test.

### Established Patterns
- `source` is stored as a free `String(30)` column, deduped by
  `UniqueConstraint(tenant_id, cve_id, asset_id, source)` — the enum is advisory Python-side
  only, so extending it is non-breaking and migration-free.
- Phase 2 settled CI/ZAP policy: mypy/lint/tsc gate on PRs; ZAP DAST is advisory
  (continue-on-error, push/nightly only, not a required check). Header verification must ride
  the pytest gate, not ZAP.

### Integration Points
- CSP/COOP land in one method (`main.py:86`) → immediately covered by any middleware-level test.
- The doc-parity loop closes in `docs/16-security.md` (headers), `docs/05-configuration.md` +
  `docs/03-tech-stack.md` (Secrets Manager removal), and `README.md` (scanner count verify).

</code_context>

<specifics>
## Specific Ideas

- Backend CSP is intentionally the strictest possible API policy
  (`default-src 'none'; frame-ancestors 'none'; base-uri 'none'`) precisely because the
  backend returns JSON, never HTML — this is a different concern from the frontend's
  resource-loading CSP and must not be conflated with it.

</specifics>

<deferred>
## Deferred Ideas

- **Make `VulnSource` a live/enforced enum** — validate `source` on write and/or reference
  the enum from each connector's `source_name` so the two can't drift again. Deliberately
  out of scope for this parity phase (D-12); it touches all connectors + the write path.
  Candidate for a future hardening/refactor pass.
- **Belt-and-suspenders CSP/COOP at Nginx** — considered and declined (D-05). Could be
  revisited if a future edge-hardening pass wants defense-in-depth at the proxy.

None of the above expands Phase 4 scope — they are noted so they aren't re-surfaced as gaps.

</deferred>

---

*Phase: 04-doc-code-parity*
*Context gathered: 2026-07-02*
