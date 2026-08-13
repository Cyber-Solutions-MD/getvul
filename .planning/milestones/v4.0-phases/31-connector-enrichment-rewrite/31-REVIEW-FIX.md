---
phase: 31-connector-enrichment-rewrite
fixed_at: 2026-08-05T14:19:22Z
review_path: .planning/phases/31-connector-enrichment-rewrite/31-REVIEW.md
iteration: 1
findings_in_scope: 2
fixed: 2
skipped: 0
status: all_fixed
---

# Phase 31: Code Review Fix Report

**Fixed at:** 2026-08-05T14:19:22Z
**Source review:** .planning/phases/31-connector-enrichment-rewrite/31-REVIEW.md
**Iteration:** 1

**Scope note:** This pass was explicitly scoped to exactly two findings —
CR-01 and WR-03 — per the fixer's task instructions. WR-01, WR-02, WR-04,
and IN-01 were explicitly out of scope and were not attempted (see "Out of
Scope" section below; this is distinct from "skipped," which would imply an
attempted-but-failed fix).

**Summary:**
- Findings in scope: 2
- Fixed: 2
- Skipped: 0

## Fixed Issues

### CR-01: `repropagate_enrichment`'s unconditional KEV UPDATE corrupts `cisa_kev` to NULL for any vulnerability with a NULL `cve_id`

**Files modified:** `backend/app/connectors/enrichment_feeds.py`, `backend/tests/test_enrichment_feeds.py`
**Commit:** `e2b4b65`
**Applied fix:** Added a `WHERE cve_id IS NOT NULL` guard to the KEV re-propagation `UPDATE` statement in `repropagate_enrichment` (matches the review's suggested fix verbatim, reformatted onto one line to satisfy this project's `ruff format` 120-col line length). Rows with a NULL `cve_id` (reachable via CrowdStrike's `_normalize_vuln`/Wiz's `cve_id=node.get("name")`, both of which lack a fallback-exhausted guard) now keep their existing `cisa_kev` value instead of being silently set to SQL NULL — preserving the D-04 "catalog is sole authority, flips both directions" semantics for every row that actually has a `cve_id`. Also extended the function's docstring with a short note explaining why the guard exists (matches this file's existing dense in-code documentation convention: D-XX/Pitfall/CR-XX cross-references).

Added a regression test, `test_repropagate_enrichment_preserves_cisa_kev_for_null_cve_id_row`, seeding a `cve_id=None` `Vulnerability` row with a non-empty `cisa_kev` catalog (required for the bug to manifest — an empty catalog makes `x IN (<empty subquery>)` evaluate to `FALSE` regardless of `x`, masking the missing guard) and asserting `cisa_kev` survives `repropagate_enrichment` unchanged. Verified this test actually catches the regression: temporarily reverted only the source fix (via `git stash`, keeping the test change) and confirmed the test fails with `assert None is True` — i.e., it reproduces the exact corruption described in the review — before restoring the fix.

All 4 requested test files re-verified green after the fix: `test_enrichment_feeds.py` (11 passed, incl. the new test), `test_scheduler_enrichment_refresh.py` (8 passed), `test_vulnerability_enrichment.py` (2 passed). `ruff check` and `ruff format --check` both clean on the 2 modified files.

### WR-03: Qualys's new `source_signals` allowlist only checks the uppercase key spelling, breaking this file's own dual-case convention

**Files modified:** `backend/app/connectors/qualys.py`, `backend/tests/test_connectors/test_qualys_connector.py`
**Commit:** `fc262d4`
**Applied fix:** Replaced the uppercase-only `_SOURCE_SIGNAL_ALLOWLIST` tuple with `_SOURCE_SIGNAL_KEYS`, a tuple of `(upper, lower)` pairs (`("TYPE", "type")`, `("QDS_FACTORS", "qds_factors")`), and changed the extraction loop to probe both casings — uppercase first, falling back to lowercase — always normalizing the captured value into `source_signals` under the canonical uppercase key regardless of which casing the response actually used. This mirrors the file's existing dual-case convention (`qid`/`severity`/`dns` at lines ~612-621, `_get_qds`'s own uppercase-then-lowercase `QDS` probe). Renamed the constant since it's no longer a flat allowlist of key names; confirmed via grep that no other file/test imports `_SOURCE_SIGNAL_ALLOWLIST` from `qualys.py` (each connector — defender.py/nessus.py/wiz.py — defines its own independent module-level constant of the same name, untouched). Extended the explanatory comment block above the constant to document the dual-case rationale (matches this file's existing documentation density).

Added two regression tests: `test_normalize_detection_source_signals_dual_case_lowercase_json_path` (lowercase `type`/`qds_factors` keys, as a JSON-response would yield, now populate `source_signals["TYPE"]`/`source_signals["QDS_FACTORS"]`) and `test_normalize_detection_source_signals_uppercase_preferred_when_both_cases_present` (documents/locks in the upper-then-lower precedence order when a response somehow carries both casings for the same field). Verified the lowercase-path test actually catches the regression: temporarily reverted only the source fix (via `git stash`, keeping the test changes) and confirmed it fails with `KeyError: 'TYPE'` — the exact "silently captures nothing" failure mode described in the review — before restoring the fix.

All 12 pre-existing Qualys connector tests continued to pass unmodified (the fix is backward-compatible with the uppercase-only XML path). Full affected-file re-run green: `test_connectors/test_qualys_connector.py` (14 passed, incl. the 2 new tests) and, as a broader safety net, `test_connector_normalization.py` (28 passed, incl. the cross-6-connector `source_signals` sanity check). `ruff check` and `ruff format --check` both clean on the 2 modified files.

## Out of Scope (excluded by this pass's task instructions, not attempted)

These findings from `31-REVIEW.md` were explicitly excluded from this fix pass per the fixer's task instructions and were not read for fix intent, not edited, and are not reflected in the counts above:

- **WR-01** — `refresh_enrichment_reference_data`'s DB-write phase has no error handling (`enrichment_feeds.py:216-231`)
- **WR-02** — `_fetch_and_parse_kev` has no malformed-row-fraction guard analogous to EPSS's (`enrichment_feeds.py:168-191`)
- **WR-04** — Wiz's `WizGraphQLSchemaError` is raised for any GraphQL `errors` response, not just query-shape mismatches (`wiz.py:20-31`, `321-323`, `379-384`)
- **IN-01** — Dead code: computed value never used (`defender.py:295`)

---

_Fixed: 2026-08-05T14:19:22Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
