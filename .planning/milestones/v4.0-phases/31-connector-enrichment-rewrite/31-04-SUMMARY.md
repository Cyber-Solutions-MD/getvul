---
phase: 31-connector-enrichment-rewrite
plan: 04
subsystem: backend/connectors
tags: [qualys, rapid7, qds, risk-score, source-signals, python, pytest]

# Dependency graph
requires:
  - phase: 31-01
    provides: "native_priority_score/native_priority_rating/source_signals dataclass fields on NormalizedVulnerability, and the sync.py _lookup_enrichment choke point that makes the CISA KEV reference table (not any connector's own guess) the sole authority for the cisa_kev column"
provides:
  - "Qualys native_priority_score populated from the raw per-DETECTION QDS value (1-100), read from the `detection` dict itself — never `kb_cache` (Pitfall 4) — with `show_qds_factors=1` added to the detection-list request params"
  - "Qualys source_signals allowlist (TYPE, QDS_FACTORS) built from the raw detection dict, missing-vs-negative, excluding QDS itself (already promoted) and PII/promoted columns"
  - "Rapid7 native_priority_score populated from the raw riskScore value (0-1000) read off the per-asset AssetVulnerability association entry (vuln_entry) — never the vendor-neutral `detail` resource (Pitfall 5) — captured once before the per-CVE fanout loop"
  - "Rapid7 source_signals captures raw `status` (InsightVM match-confidence enum) + a derived `status_confirmed` boolean (provenance only, mirrors crowdstrike.py's raw+derived pair), missing-vs-negative, excluding riskScore itself"
  - "4 of 6 connectors (Defender from Plan 01, CrowdStrike+Nessus from Plan 03, Qualys+Rapid7 from this plan) now fully compliant with ENRICH-03/04/06's missing-vs-negative + no-PII/no-promoted-duplication contract"
affects: ["31-05 (Wiz + the cross-6 ENRICH-06 parametrized sweep in test_connector_normalization.py depends on this plan's Qualys+Rapid7 work landing first — Plan 05 is the last of the 4 declaring plans for ENRICH-03/04/06)"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "base-dict + per-CVE-fanout threading (reused from Nessus/Plan 03, extended to Qualys): native_priority_score/native_priority_rating/source_signals are computed once per detection/vuln_entry and placed into the same `base`/inline-kwargs dict every per-CVE NormalizedVulnerability(...) construction already draws from, so a single detection/vuln_entry fanning out to N CVEs gets identical enrichment on all N findings"
    - "Defensive single-candidate probe (Qualys QDS, Rapid7 riskScore): unlike Nessus's 2-candidate VPR probe (Plan 03), both this plan's fields have exactly ONE named candidate in the plan's own interfaces block/research, so each probe (`_get_qds`, `_get_risk_score`) tries only that one key (dual-case for Qualys, matching this file's own qid/severity convention) — float-coerces defensively, soft-nulls on absence or a bad type, never raises"
    - "Raw-value + derived-boolean pair for a single source_signals key (Rapid7 status/status_confirmed): reuses CrowdStrike's own exploit_status/exploit_status_kev_guess shape (Plan 03) rather than the multi-key-loop allowlist idiom (Defender/Nessus/Qualys) — appropriate here because Rapid7 has exactly one substantively-justified raw field to capture, not several"

key-files:
  created: []
  modified:
    - backend/app/connectors/qualys.py
    - backend/app/connectors/rapid7.py
    - backend/tests/test_connectors/test_qualys_connector.py
    - backend/tests/test_connectors/test_rapid7_connector.py

key-decisions:
  - "Qualys's source_signals allowlist is (TYPE, QDS_FACTORS) — TYPE is the well-documented per-detection confirmation status (Confirmed/Potential/Info, detection-confidence-relevant) and QDS_FACTORS is the threat-intel breakdown this task's own `show_qds_factors=1` param addition unlocks. Neither is named verbatim in 31-RESEARCH.md/31-PATTERNS.md (unlike Nessus's exploit_available/exploitability_ease, which mirrored pre-existing code reads) — this is a Claude's Discretion choice (CONTEXT.md: 'exact per-connector allowlist field sets... bounded by D-05/D-07/D-08'), deliberately scoped to fields that are genuinely exploit/confidence-relevant and not already modeled elsewhere"
  - "Rapid7's riskScore probe uses a single candidate key (`riskScore`) with no fallback candidates — unlike Nessus's VPR probe (2 candidates), the plan's own interfaces block and 31-RESEARCH.md Assumption A2 name exactly one candidate for Rapid7, so inventing additional untested candidate names would add unverifiable complexity without a stated basis"
  - "Rapid7's source_signals allowlist is `status` (+ a derived `status_confirmed` boolean) rather than a multi-key tuple — the connector currently discards every vuln_entry field except `id`, and `status` is the one substantively-justified, genuinely exploit/confidence-relevant field with no existing precedent to build a longer list from; this mirrors CrowdStrike's raw+derived single-signal shape (Plan 03) rather than Defender/Nessus/Qualys's multi-key allowlist-loop shape"
  - "ENRICH-03/04/06 left `[ ]` Pending in REQUIREMENTS.md — shared-ID gate (mirrors Plan 01 and Plan 03's own precedent): all three IDs are also declared by 31-05 (Wiz + the cross-6 ENRICH-06 parametrized sweep, confirmed via direct read of 31-05-PLAN.md's frontmatter — `depends_on: [01, 03, 04]`, `requirements: [ENRICH-03, ENRICH-04, ENRICH-06]`). This plan completes native_priority_* coverage for all 4 connectors that have a genuine vendor composite (Defender is intentionally null, Plan 01; CrowdStrike+Nessus, Plan 03; Qualys+Rapid7, this plan) but the IDs flip complete only when Plan 05 lands and the full 6-connector sweep passes"

patterns-established: []  # This plan extends Plan 01/03's established patterns (single-choke-point enrichment, source_signals-built-from-raw-dict, explicit-None-for-no-composite, base-dict/raw+derived-pair threading) to the 2 remaining composite-signal connectors; it does not introduce new architectural patterns of its own.

requirements-completed: []  # ENRICH-03/04/06 shared-ID gated on 31-05 -- see key-decisions

# Metrics
duration: ~16min
completed: 2026-08-05
---

# Phase 31 Plan 04: Qualys + Rapid7 Native-Priority Enrichment Summary

**Qualys's Detection Score (QDS) and Rapid7's Risk Score now populate `native_priority_score` straight from the correct-but-non-obvious source location for each vendor (the per-detection record, not the QID knowledge base; the per-asset association entry, not the vendor-neutral vulnerability definition), completing native-priority coverage for all 4 composite-signal connectors, with both connectors' risk-relevant fields threaded into `source_signals` using missing-vs-negative semantics.**

## Performance

- **Duration:** ~16 min
- **Started:** 2026-08-05T11:25Z (approx, immediately following Plan 03's completion per STATE.md session marker)
- **Completed:** 2026-08-05T11:41Z
- **Tasks:** 2 (each RED → GREEN)
- **Files modified:** 4 (2 source, 2 test — no new files)

## Accomplishments

- Qualys's `_fetch_all_detections` now requests `show_qds_factors=1` alongside its existing params, and `_normalize_detection` reads the Qualys Detection Score (QDS, 1-100 scale) from the **per-detection** `detection` dict via a new `_get_qds()` defensive probe — explicitly **not** from `kb_cache` (Pitfall 4: QDS is computed at detection time from exploit-maturity/threat-intel factors, a fundamentally different kind of field than the QID-level knowledge-base constants `kb_cache` already holds). A dedicated regression test proves a `kb_cache` entry carrying a QDS-shaped key does **not** leak into `native_priority_score` — only the detection record's own value does.
- Rapid7's `fetch_vulnerabilities` now captures `risk_score = vuln_entry.get("riskScore")` (via a new `_get_risk_score()` helper) **before** the inner per-CVE loop, reading it off `vuln_entry` — the per-asset `AssetVulnerability` association entry from `/api/3/assets/{id}/vulnerabilities` — rather than `detail`, the vendor-neutral vulnerability-definition resource shared by every asset that has the same CVE (Pitfall 5). A dedicated test proves a `detail` payload carrying a `riskScore`-shaped key is ignored; only `vuln_entry`'s own value populates the column.
- Both connectors correctly model **missing vs. negative** in `source_signals`, built inline from the raw dict in the same scope that has it (never from the already-coerced dataclass): Qualys's allowlist (`TYPE`, `QDS_FACTORS`) and Rapid7's `status` (+ a derived `status_confirmed` boolean, mirroring CrowdStrike's own raw+derived-guess shape from Plan 03) — proven with dedicated test fixtures asserting a present-but-empty/weaker-match field is distinguishable from a genuinely-absent one in the same finding, and that no PII-adjacent (`hostname`, `ip_addresses`) or already-promoted (`cve_id`, `cvss`, `severity`, `epss`, `native_priority`) key ever leaks in. Both connectors exclude their own promoted field (QDS, riskScore) from `source_signals` per D-08.
- `native_priority_rating` stays explicit `None` for both connectors (QDS and Risk Score are numeric-only — neither vendor publishes a separate categorical rating), and all 3 new dataclass fields are proven to be explicitly set (never omitted, never a crash) even when every relevant vendor field is absent.
- This completes `native_priority_*` coverage for **all 4** connectors with a genuine vendor-authored composite signal (Defender/Wiz are intentionally null by design, per Pitfall 6 — out of this plan's scope).

## Task Commits

Each task was committed atomically (strict RED → GREEN TDD):

1. **Task 1: Qualys QDS → native_priority_score + source_signals (RED)** - `30ce0b6` (test)
2. **Task 1: Qualys QDS → native_priority_score + source_signals (GREEN)** - `f2ff2e2` (feat)
3. **Task 2: Rapid7 riskScore → native_priority_score + source_signals (RED)** - `ffa5112` (test)
4. **Task 2: Rapid7 riskScore → native_priority_score + source_signals (GREEN)** - `310b4d4` (feat)

**Plan metadata:** (this commit, docs: complete plan)

_TDD gate compliance: for each task, a `test(...)` commit (verified genuinely failing pre-implementation via direct pytest execution — 4/6 new assertions failed for real each time, the other 2 passed trivially since `None` is correct both pre- and post-implementation for those specific "absent"/"wrong-source" scenarios) precedes a `feat(...)` commit (verified passing, 12/12 each file). Both gates present in git log for both tasks — compliant._

## Files Created/Modified

- `backend/app/connectors/qualys.py` - `_fetch_all_detections` gains `"show_qds_factors": 1` in its params dict; new `_SOURCE_SIGNAL_ALLOWLIST = ("TYPE", "QDS_FACTORS")` + `_get_qds()` helper; `_normalize_detection`'s `base` dict gains `native_priority_score`/`native_priority_rating`(`=None`)/`source_signals`, propagating to every per-CVE fanout call (and the QID-fallback single-result path). Updated the Plan-01 `base` dict comment (stale "doesn't populate yet" language) to reflect that this plan is the one that now populates it.
- `backend/app/connectors/rapid7.py` - New `_get_risk_score()` module-level helper (bottom-of-file "Normalisation helpers" section — this file's first, mirroring qualys.py/nessus.py's own module structure even though rapid7.py previously had no free-function helpers). `fetch_vulnerabilities`'s per-`vuln_entry` loop now captures `native_priority_score` + builds `source_signals` (`status`/`status_confirmed`) once, before the per-CVE loop, and both are passed to every `NormalizedVulnerability(...)` construction inside it alongside `native_priority_rating=None`.
- `backend/tests/test_connectors/test_qualys_connector.py` - 6 new unit tests calling `_normalize_detection` directly (no HTTP mocking needed): QDS-present → populated, QDS-absent → soft-null, QDS-must-come-from-detection-not-kb_cache (Pitfall 4 regression guard), missing-vs-negative + no-PII/no-promoted-dup, QDS_FACTORS-present-but-empty is negative not missing, and all-3-fields-always-set even with zero relevant keys present.
- `backend/tests/test_connectors/test_rapid7_connector.py` - 6 new `fetch_vulnerabilities()`-level tests (this connector has no extractable pure-normalize function to unit-test directly, matching its pre-existing test file's own established end-to-end-via-MockTransport style): riskScore-present → populated, riskScore-absent → soft-null, riskScore-must-come-from-vuln_entry-not-detail (Pitfall 5 regression guard), missing-vs-negative + no-PII/no-promoted-dup, status_confirmed true-vs-absent across 2 assets in one run, and all-3-fields-always-set using the file's own pre-existing baseline fixture. `ruff format` also reformatted one pre-existing, unrelated line in this file (whitespace only, incidental to formatting the whole file — zero behavior change).

## Decisions Made

- Qualys's `source_signals` allowlist (`TYPE`, `QDS_FACTORS`) and Rapid7's (`status` + derived `status_confirmed`) are both Claude's-Discretion choices, not fields named verbatim in the plan/research — see key-decisions above for the full rationale (both are genuinely exploit/confidence-relevant, currently entirely discarded by their connectors, and never overlap PII-adjacent or already-promoted fields).
- Both native-priority probes (`_get_qds`, `_get_risk_score`) use a single named candidate key each (no invented fallback candidates), unlike Nessus's 2-candidate VPR probe — because the plan's own interfaces block and 31-RESEARCH.md each name exactly one candidate for Qualys/Rapid7.
- ENRICH-03/04/06 left `[ ]` Pending in REQUIREMENTS.md (shared-ID gate with 31-05, confirmed by directly reading 31-05-PLAN.md's frontmatter — mirrors Plan 01/03's own precedent).

## Deviations from Plan

None — plan executed exactly as written. Both connectors' allowlist field choices were exercises of the plan's own explicitly-granted discretion (CONTEXT.md: "Exact per-connector allowlist field sets... bounded by D-05/D-07/D-08"), not deviations from a specified field list (neither the plan nor 31-RESEARCH.md/31-PATTERNS.md named specific source_signals keys for Qualys/Rapid7, unlike Nessus's exploit_available/exploitability_ease).

## Issues Encountered

- **mypy-baseline "new: 3" report is the same confirmed pre-existing flake documented in Plan 01/03's summaries, re-verified independently for both this plan's files.** Running the project's exact CI gate (`mypy app/ | mypy-baseline filter --allow-unsynced`) after each GREEN commit reported `fixed: 15 / new: 3` both times. Per-file diffing against `mypy-baseline.txt` (line-agnostic `:0:`-style message matching) confirmed every qualys.py/rapid7.py error present in the live run is already baselined verbatim — zero new file-specific violations. Additionally re-verified via `git stash` (isolating just the qualys.py GREEN change) + `rm -rf .mypy_cache` before/after: the identical "new: 3" (the same `app/auth/dependencies.py:10: note:` jose-stub-missing hints) appeared on the clean, pre-GREEN tree too, proving it is fully unrelated to this plan's changes. Matches the precedent already documented in Plan 01/03's SUMMARYs and Phase 29's SUMMARY (project MEMORY.md `getvul-backend-test-harness-rot`). Not fixed (out of scope — pre-existing, unrelated to any file this plan touches).
- No other issues. Both external-field-name assumptions (Qualys's `QDS`/`show_qds_factors` param, Rapid7's `riskScore` field/location) are unverified against a live vendor instance — flagged explicitly below per the plan's `<output>` instruction, not silently assumed correct.

## User Setup Required

None — no external service configuration required. Both connectors' new fields are populated entirely from data already fetched by existing API calls (Rapid7's `vuln_entry`, already fetched by the pre-existing `_fetch_asset_vulns` call) or a single additive request parameter with a documented soft-failure mode if wrong (Qualys's `show_qds_factors=1` — Qualys APIs are generally tolerant of unrecognized params).

## Empirical Re-verification Flags (carried per plan's `<output>` instruction)

- **Qualys QDS element name + `show_qds_factors` param (A3):** 31-RESEARCH.md's Assumptions Log lists both the exact XML/JSON element name for QDS and the `show_qds_factors` param name as unverified this session (WebFetch attempts against the specific Qualys doc page 404'd). This plan's implementation reads `detection.get("QDS")` (dual-case `qds` fallback), verified only to soft-null cleanly when absent and to float-coerce correctly against a synthetic fixture. **Recommend verifying against a live Qualys VMDR account** — if the real element name differs, or if `show_qds_factors=1` is not the correct/complete parameter, `native_priority_score` will silently stay `None` for every Qualys finding (soft failure, not a crash — by design). The `TYPE`/`QDS_FACTORS` source_signals allowlist keys are similarly unverified for exact casing/shape against a live response — the `_xml_to_dict` fallback already in this file will surface whatever keys Qualys actually returns, so a live probe is the fastest way to confirm or correct these choices.
- **Rapid7 riskScore field name + resource location (A2):** 31-RESEARCH.md's Assumptions Log (A2) flags both the exact field name (`riskScore`) and its resource location (the `AssetVulnerability` association entry rather than the `Vulnerability` definition) as unverified this session (automated fetches against Rapid7's interactive Swagger UI returned no usable content, likely a JS-rendered SPA). **Recommend verifying against a live/trial InsightVM console or its Swagger UI directly** (`help.rapid7.com/insightvm/en-us/api/`) — if the real field name or location differs, `native_priority_score` will silently stay `None` for every Rapid7 finding (soft failure, not a crash, by design). The `status` enum values assumed for `source_signals`/`status_confirmed` (`vulnerable`/`vulnerable-version`/`vulnerable-potential`/etc.) are likewise unverified this session and should be reconciled against a real payload.

## Next Phase Readiness

- 4 of 6 connectors (Defender from Plan 01 — intentionally null; CrowdStrike + Nessus from Plan 03; Qualys + Rapid7 from this plan) now fully populate `native_priority_score`/`native_priority_rating`/`source_signals` per the established pattern. Only Wiz (also intentionally null for `native_priority_*` per Pitfall 6, but with its own richer `source_signals` fields still to add) remains — Plan 05's scope.
- No blockers. `test_qualys_connector.py` (12/12), `test_rapid7_connector.py` (12/12), `test_connector_normalization.py` (22/22, unedited by this plan — regression-clean), and `test_vulnerability_enrichment.py` (2/2, Plan 01's integration tests — regression-clean) all green. `ruff check`/`ruff format --check` clean on all 4 touched files. mypy-baseline gate shows zero new qualys.py/rapid7.py-specific violations (see Issues Encountered for the pre-existing flake explanation, re-verified via git-stash isolation).
- Plan 05's cross-6 sweep should be able to assert, for Qualys and Rapid7 specifically: `native_priority_rating` always `None` (both numeric-only), `native_priority_score` populated-or-None, and `source_signals` always a dict (never `None`) with the documented allowlist keys (`TYPE`/`QDS_FACTORS` for Qualys; `status`/`status_confirmed` for Rapid7).

---
*Phase: 31-connector-enrichment-rewrite*
*Completed: 2026-08-05*

## Self-Check: PASSED

All 4 modified source/test files confirmed present on disk; all 4 task commit hashes (`30ce0b6`, `f2ff2e2`, `ffa5112`, `310b4d4`) confirmed in `git log`.
