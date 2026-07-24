---
phase: 02-ci-gating
fixed_at: 2026-07-24T00:00:00Z
review_path: .planning/phases/02-ci-gating/02-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 2
skipped: 1
status: partial
---

# Phase 2: Code Review Fix Report

**Fixed at:** 2026-07-24
**Source review:** `.planning/phases/02-ci-gating/02-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope (Critical + Warning): 3
- Fixed: 2 (WR-01, WR-02)
- Skipped: 1 (WR-04)

## Fixed Issues

### WR-01 / WR-02: docs/12 regressed to pre-Phase-2 state + stale `ci.yml` line anchors

**Files modified:** `docs/12-pipelines-cicd.md`
**Commit:** `0ee0076`
**Applied fix:**

WR-01 and WR-02 are the same documentation regression on overlapping lines, and
WR-02 explicitly directs "fold this into the WR-01 re-apply," so both were fixed
in one atomic commit. Every claim was verified against the **current**
`.github/workflows/ci.yml` (not blindly restored from `d8c1585`).

- **Mermaid trigger nodes** (was `manual dispatch / workflow_dispatch only / see
  PROD-02`) now read `on: push · pull_request + nightly schedule +
  workflow_dispatch`, matching `ci.yml:3-10`.
- **Triggers YAML block + note** replaced the commented-out `push`/`pull_request`
  and the false "Today CI runs only on manual dispatch" line with the actual
  armed triggers (`workflow_dispatch`, `push`, `pull_request`, nightly
  `schedule`) and a note that the required checks gate merges into `main`.
- **Backend mypy row:** `mypy app/ || true` (⚠ soft, `#L59`) →
  `set +o pipefail; mypy app/ | mypy-baseline filter --allow-unsynced`
  (hard-fail on new errors, `#L69`), matching `ci.yml:69-71`.
- **Frontend lint/tsc rows:** `npm run lint || true` (`#L95`) and
  `npx tsc --noEmit || true` (`#L97`), both ⚠ soft → hard-fail with corrected
  anchors `#L107` and `#L109` (`ci.yml:107,109`).
- **DAST section:** added the `if: github.event_name != 'pull_request'` PR-gating
  note; recomputed the three ZAP `continue-on-error` anchors `#L164/#L173/#L182`
  → `#L177/#L186/#L195` (`ci.yml:177,186,195`).
- **"Soft-fail summary (Phase 2 cleanup target)" section + pending PROD-02
  checklist** replaced with a "Gating status (PROD-02 — complete)" section
  documenting all four deliverables as shipped.
- **CD trigger prose** (line 160) tightened from "or **manual dispatch**" to
  "or a manual **`workflow_dispatch`** run" — accurate for `cd.yml`, and it
  clears the last substring that `verify-docs.sh:16` would otherwise flag,
  so the corrected doc passes that guard (rather than merely relocating the
  false positive from the CI section to the CD section).

**Verification:**
- Tier 1: re-read all edited regions; text present, tables/mermaid intact.
- Tier 2 (structural): `verify-docs.sh`'s docs/12 stale-trigger grep
  (`workflow_dispatch only|manual dispatch`) now returns **no match** (was
  matching the old line 57). The only residual `|| true` string in docs/12 is
  inside the PROD-02-02 bullet stating the masks were *removed* — correct
  historical context, not a live-mask claim.
- The three ZAP `continue-on-error` masks were intentionally kept (advisory by
  design), consistent with the current `ci.yml`.

## Skipped Issues

### WR-04: `Semgrep SAST` is a required merge gate coupled to an external SaaS + secret

**File:** `.github/workflows/ci.yml:134-144`, `.github/branch-protection.json:7`
**Reason:** skipped — accepted architectural tradeoff, not a mechanical defect.
The REVIEW.md itself classifies this as "previously *accepted* as out-of-scope
architecture; re-surfaced, not re-litigated." The suggested fix is ambiguous
(two alternatives: (a) swap `semgrep ci` for a self-contained
`semgrep scan --config auto --error` gating check plus a separate advisory
publish step, or (b) document the token as a hard merge-gate dependency + add
expiry alerting). Option (a) changes the runtime behavior of a **required merge
gate** on an already-shipped v1.0 phase — not a safe/unambiguous change for a
review-fix pass, and it warrants a deliberate design decision + CI validation
run rather than a doc/config patch. Per the fix guidance, an explicitly accepted
design tradeoff is skipped rather than force-changed.
**Original issue:** If `SEMGREP_APP_TOKEN` is unset/expired or semgrep.dev is
unreachable, the required `Semgrep SAST` check can hard-fail for reasons
unrelated to code quality, blocking every merge (unlike the self-contained
Backend/Frontend/Terraform checks).
**Recommendation for the team (not applied):** option (b) — a docs-only note in
docs/12 documenting the token as a hard merge-gate dependency — is the safe
minimal mitigation if you want to close this without altering gate behavior.

## Out-of-scope observation (not a Warning; reported for honesty)

While validating with `.github/verify-docs.sh` (run from the repo root), the
verifier still exits 1 — but the four remaining failures are all against
**`docs/13-deployment.md`**, not docs/12:

```
FAIL: docs/13-deployment.md missing '## CI Gating & Branch Protection' section
FAIL: docs/13-deployment.md does not reference the committed branch-protection.json body
FAIL: docs/13 missing required check 'Semgrep SAST'
FAIL: docs/13 missing required check 'Terraform Validate'
```

`docs/13-deployment.md` genuinely lacks that section and those strings in the
current tree (confirmed by grep). This looks like a **second** stale-base
regression, parallel to WR-01/WR-02 but in docs/13 — and it is not captured as a
Critical/Warning finding in this REVIEW.md (IN-03 assumed the docs/13 heading
existed). It is therefore outside the scope of this fix pass. Flagging it so the
docs/12 fix is not mistaken for making `verify-docs.sh` fully green — the docs/13
gap needs its own finding/fix.

---

_Fixed: 2026-07-24_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
