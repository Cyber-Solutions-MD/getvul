# Phase 4: Doc/Code Parity - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-02
**Phase:** 4-Doc/Code Parity
**Areas discussed:** Secrets Manager decision, CSP/COOP header content, VulnSource enum scope, Verification / ZAP rule

---

## Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Secrets Manager decision | Implement vs remove dead aws_region/secrets_manager_prefix + boto3 | ✓ |
| CSP/COOP header content | Backend CSP value, COOP value, placement | ✓ |
| VulnSource enum scope | Parity-only add vs wire into validation; regression shape | ✓ |
| Verification / ZAP rule | How strictly to prove headers emitted | ✓ |

**User's choice:** All four.
**Notes:** README scanner-count (PROD-04-02) noted up front as already satisfied — treated as verify-only regardless of selection.

---

## Secrets Manager decision

| Option | Description | Selected |
|--------|-------------|----------|
| Remove it entirely | Delete config vars + boto3 + refs; Fernet-in-.env stays | ✓ |
| Implement end-to-end | Wire Secrets Manager as a real credential backend | |
| Keep config, remove boto3 | Leave vars as placeholders, drop dep | |

**User's choice:** Remove it entirely.

### Removal scope

| Option | Description | Selected |
|--------|-------------|----------|
| Config + dep + all refs | config.py + pyproject/uv.lock + docs (05, 03) + .env/.env.example | ✓ |
| Config + dep only | Two vars + boto3, leave docs/infra sweep to follow-up | |
| Note as tombstone | Leave a comment/ADR that the path was dropped | |

**User's choice:** Config + dep + all refs.
**Notes:** Scout confirmed reference surface = config.py:38-39, pyproject.toml:17 (+uv.lock), docs/05-configuration.md:84-85, docs/03-tech-stack.md:23, .env/.env.example:14-15. No infra/aws Terraform refs found.

---

## CSP/COOP header content

**Q: CSP value on backend API responses**

| Option | Description | Selected |
|--------|-------------|----------|
| Locked-down API CSP | default-src 'none'; frame-ancestors 'none'; base-uri 'none' | ✓ |
| Mirror frontend CSP | Copy next.config.js CSP | |
| Report-only first | CSP-Report-Only before enforcing | |

**User's choice:** Locked-down API CSP.

**Q: Placement**

| Option | Description | Selected |
|--------|-------------|----------|
| Backend middleware only | Add to SecurityHeadersMiddleware (main.py:86) | ✓ |
| Backend + Nginx | Middleware + nginx.conf defense-in-depth | |
| Nginx only | Edge only | |

**User's choice:** Backend middleware only.

**Q: COOP value**

| Option | Description | Selected |
|--------|-------------|----------|
| same-origin | Matches frontend (next.config.js:16), standard hardening | ✓ |
| same-origin-allow-popups | Keeps window.opener for popup flows | |

**User's choice:** same-origin.
**Notes:** OIDC is redirect-based, so no popup depends on window.opener. Enforcing mode from the start (not report-only) since an API loads no resources.

---

## VulnSource enum scope

**Q: How far PROD-04-03 goes**

| Option | Description | Selected |
|--------|-------------|----------|
| Add members for parity | Add QUALYS+RAPID7, no migration/backfill | ✓ |
| Add + wire into validation | Enforce enum on write / filter type | |
| Add + connect to connectors | Reference enum from each connector source_name | |

**User's choice:** Add members for parity.

**Q: Regression test shape (PROD-04-04)**

| Option | Description | Selected |
|--------|-------------|----------|
| API-level filter test | Seed vulns, hit endpoint with source=QUALYS/RAPID7, assert rows | ✓ |
| Repository/query-level test | Test DB query layer directly | |
| You decide | Let planning pick based on suite patterns | |

**User's choice:** API-level filter test.
**Notes:** Enum is dead code today; source column is String(30) so no migration/backfill needed. Wiring the enum live was declined as scope creep (recorded as deferred idea).

---

## Verification / ZAP rule

**Q: How to prove headers emitted (SC#1)**

| Option | Description | Selected |
|--------|-------------|----------|
| Pytest header assertion | Assert CSP+COOP present with expected values, runs in CI | |
| Pytest + ZAP rule | Above + ZAP as secondary net | ✓ |
| Curl in a smoke script | Shell/curl check | |

**User's choice:** Pytest + ZAP rule (pytest = primary gate, ZAP = advisory secondary).

**Q: Touch ZAP config?**

| Option | Description | Selected |
|--------|-------------|----------|
| Leave ZAP as-is | No ZAP gating changes; pytest is the guard | ✓ |
| Add explicit ZAP alert check | Author a CSP-presence ZAP rule | |

**User's choice:** Leave ZAP as-is.
**Notes:** Phase 2 settled ZAP as advisory/nightly-only; this phase does not reopen that. ZAP will simply stop reporting missing-CSP once the header ships.

## Claude's Discretion

- Exact pytest file/location + fixture reuse for header assertion and source-filter regression.
- Whether CSP applies to all responses or is path-scoped like the existing Cache-Control block (default: all responses).
- uv.lock regeneration mechanics after dropping boto3.

## Deferred Ideas

- Make VulnSource a live/enforced enum (validate on write / reference from connectors) — future hardening pass.
- Belt-and-suspenders CSP/COOP at Nginx — declined; possible future edge-hardening.
