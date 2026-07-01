---
phase: 02
slug: ci-gating
status: verified
threats_open: 0
asvs_level: 1
created: 2026-07-01
---

# Phase 02 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| contributor commit/PR → protected `main` | Untrusted/unverified code attempts to enter the protected branch via push or PR; CI + branch protection are the controls that inspect and gate it. | source code, CI status |
| GitHub Actions runner → external services | CI jobs reach semgrep.dev and ZAP targets using the repo secret `SEMGREP_APP_TOKEN`. | SAST token, scan traffic |
| operator `gh` CLI (admin token) → GitHub repo settings | An admin-scoped token mutates `main` branch-protection policy; the committed JSON body + human-verify checkpoint make the mutation reviewed, auditable, and reproducible. | repo protection policy |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-02-01 | Tampering | ci.yml mypy mask | mitigate | `mypy app/ \| mypy-baseline filter` (with `set +o pipefail`) replaces `mypy app/ \|\| true`; committed baseline `backend/mypy-baseline.txt`; `strict = true` preserved. New type errors fail the build. (ci.yml:66-67) | closed |
| T-02-02 | Tampering | frontend lint/tsc masks | mitigate | `\|\| true` removed from `npm run lint` (ci.yml:103) and `npx tsc --noEmit` (ci.yml:105); `grep -c '\|\| true' ci.yml` → 0. | closed |
| T-02-03 | Elevation/Bypass | dast advisory job | accept | ZAP stays `continue-on-error` (ci.yml:173/182/191) and off PRs (`if: github.event_name != 'pull_request'`, ci.yml:146); not a required check. Accepted per CONTEXT D-04/D-06. | closed |
| T-02-04 | Tampering | terraform required-but-skipped | mitigate | terraform job runs unconditionally (no `if:`/`paths:` filter, ci.yml:111-128) so the required check never hangs Pending; registered as required in branch-protection.json. | closed |
| T-02-05 | Elevation of Privilege | merge to main without green CI | mitigate | Branch protection requires 4 checks (Backend, Frontend, Semgrep SAST, Terraform Validate) + a PR before merge; empirically proven — deliberate-failure PR #13 → `mergeStateStatus: BLOCKED`. | closed |
| T-02-06 | Spoofing/Bypass | wrong required-check names silently not enforced | mitigate | Exact display-name strings registered in branch-protection.json; `verify-branch-protection.py` does an exact-set comparison and fails if any check is missing or if `OWASP ZAP DAST` is required. Live read-back exit 0. | closed |
| T-02-07 | Repudiation | click-ops protection not reproducible | mitigate | Protection body committed at `.github/branch-protection.json`; the exact `gh api --method PUT` command + read-back documented in `docs/13-deployment.md`; `verify-docs.sh` exit 0. | closed |
| T-02-08 | Elevation | admin bypass via enforce_admins:false | accept | `"enforce_admins": false` (branch-protection.json:11) is a documented operator decision (CONTEXT D-07); surfaced to the operator via the Task 1 checkpoint before the PUT; `enforce_admins: true` noted in docs/13 as the harder option. | closed |
| T-02-09 | Tampering | unreviewed live repo-setting mutation | mitigate | The `gh api PUT` was gated behind a `checkpoint:human-verify` (02-02-PLAN Task 1, `gate="blocking"`); operator approved the exact JSON body + command before it fired (02-02-SUMMARY). | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-02-01 | T-02-03 | ZAP DAST is intentionally advisory — its value is the nightly/post-merge report, not merge-gating. Kept `continue-on-error` and off PRs. | Operator (CONTEXT D-04/D-06) | 2026-07-01 |
| AR-02-02 | T-02-08 | `enforce_admins: false` — repo admins may push directly in a pinch. Deliberate trade-off; `enforce_admins: true` documented as the harder-enforcement option in docs/13. | Operator (CONTEXT D-07) | 2026-07-01 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-01 | 9 | 9 | 0 | gsd-security-auditor (verify-all) |

Notes:
- 7 mitigations verified present in committed code/config; 2 accepted-risk conditions (T-02-03, T-02-08) confirmed to match reality and documented.
- Process/live-state controls (T-02-05 empirical BLOCK, T-02-09 checkpoint) corroborated from 02-02-SUMMARY.md, not in-repo artifacts.
- No unregistered threat flags surfaced in either SUMMARY (CI-config-only change; no new endpoints, auth paths, file access, or schema).

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-01
