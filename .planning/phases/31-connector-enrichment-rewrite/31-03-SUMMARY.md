---
phase: 31-connector-enrichment-rewrite
plan: 03
subsystem: backend/connectors
tags: [crowdstrike, nessus, vpr, exprt-ai, source-signals, python, pytest]

# Dependency graph
requires:
  - phase: 31-01
    provides: "native_priority_score/native_priority_rating/source_signals dataclass fields on NormalizedVulnerability, and the sync.py _lookup_enrichment choke point that makes the CISA KEV reference table (not any connector's own guess) the sole authority for the cisa_kev column"
provides:
  - "CrowdStrike native_priority_rating populated from the already-cached cve_meta.exprt_rating (raw ExPRT.AI category, zero new API calls)"
  - "CrowdStrike native_priority_score defensive probe for an unconfirmed numeric ExPRT companion field (exprt_score) -- stays None when absent"
  - "CrowdStrike source_signals provenance: raw exploit_status value + the derived >=50 KEV-ish guess, explicitly NOT authoritative for the cisa_kev column"
  - "Nessus native_priority_score populated via a defensive VPR probe (vpr_score, falling back to vpr) mirroring the file's own _check_exploit_available idiom; native_priority_rating explicit None (VPR is numeric-only)"
  - "Nessus source_signals allowlist (exploit_available, exploitability_ease) threaded through the base dict so it fans out to every per-CVE NormalizedVulnerability"
  - "2 of 6 connectors (CrowdStrike, Nessus) now fully compliant with ENRICH-03/04/06's missing-vs-negative + no-PII/no-promoted-duplication contract"
affects: ["31-05 (cross-6 ENRICH-06 parametrized sweep in test_connector_normalization.py depends on this plan's CrowdStrike+Nessus work landing first)"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Ad-hoc attribute attach for already-declared dataclass fields: CrowdStrike sets native_priority_rating/native_priority_score/source_signals via post-construction attribute assignment (vuln.field = value), matching this file's own existing remediation_id/exploit_status_id idiom, even though these 3 fields ARE real dataclass fields (unlike remediation_id) -- a deliberate plan choice for file-local consistency, not a technical requirement"
    - "Defensive multi-candidate field probe: Nessus's _get_vpr_score() tries an ordered list of unverified field-name candidates (vpr_score, then vpr), coercing to float and soft-nulling on absence/bad-type -- the same shape CrowdStrike's exprt_score probe uses for its own single unconfirmed candidate"

key-files:
  created: []
  modified:
    - backend/app/connectors/crowdstrike.py
    - backend/app/connectors/nessus.py
    - backend/tests/test_connectors/test_crowdstrike_connector.py
    - backend/tests/test_connectors/test_nessus_connector.py

key-decisions:
  - "CrowdStrike source_signals captures exploit_status (raw int) AND a distinctly-named derived exploit_status_kev_guess boolean (exploit_status_id >= 50) -- not just the raw number -- so the plan's 'preserved ... for provenance' language is unambiguously testable, while never using the literal key name 'cisa_kev' (which would visually collide with the promoted column D-08 forbids duplicating)"
  - "CrowdStrike's numeric ExPRT companion is probed under the candidate key exprt_score (mirrors exprt_rating's own key shape) -- RESEARCH.md confirms no vendor schema verifies this field exists at all (Tertiary/unconfirmed); flagged below for live re-verification, exactly like Nessus's VPR field name (A1)"
  - "Nessus's source_signals allowlist is deliberately narrow (exploit_available, exploitability_ease only) -- the 2 fields this codebase's own pre-existing _check_exploit_available already reads from real Nessus plugin_attributes payloads. Did not add speculative Nessus exploit_framework_* fields since neither RESEARCH.md nor this codebase verifies their presence -- expanding the allowlist later is a one-line change (D-08)"
  - "Comment-only fix to crowdstrike.py's module docstring: corrected the stale '>= 30' CISA KEV threshold description to match the live code's actual '>= 30' -> '>= 50' check (Pitfall 3) -- the code's threshold itself is byte-for-byte unchanged; only the misleading prose was corrected, since PATTERNS.md explicitly flagged this as worth a comment-only fix and leaving it uncorrected while editing the very next line would be actively misleading to the next reader"
  - "ENRICH-03/04/06 left [ ] Pending in REQUIREMENTS.md -- shared-ID gate (mirrors Plan 01's own precedent): all three IDs are also declared by 31-04 (Qualys/Rapid7) and 31-05 (Wiz + the cross-6 ENRICH-06 parametrized sweep). This plan proves the pattern on 2 more connectors (3 of 6 total including Plan 01's Defender); the IDs flip complete only when their last declaring plan (31-05) lands and the full 6-connector sweep passes"

patterns-established: []  # This plan extends Plan 01's established patterns (single-choke-point enrichment, source_signals-built-from-raw-dict, explicit-None-for-no-composite) to 2 more connectors; it does not introduce new architectural patterns of its own.

requirements-completed: []  # ENRICH-03/04/06 shared-ID gated on 31-04/31-05 -- see key-decisions

# Metrics
duration: ~17min
completed: 2026-08-05
---

# Phase 31 Plan 03: CrowdStrike + Nessus Native-Priority Enrichment Summary

**CrowdStrike's ExPRT.AI rating and Nessus's VPR score now populate `native_priority_rating`/`native_priority_score` straight from already-fetched vendor payloads (zero new API calls for CrowdStrike, one defensive probe for Nessus), with both connectors' risk-relevant fields threaded into `source_signals` using missing-vs-negative semantics and a hard no-PII/no-promoted-duplicate boundary.**

## Performance

- **Duration:** ~17 min
- **Started:** 2026-08-05T11:03Z (approx, immediately following Plan 02's completion per STATE.md session marker)
- **Completed:** 2026-08-05T11:20Z
- **Tasks:** 2 (each RED -> GREEN)
- **Files modified:** 4 (2 source, 2 test — no new files)

## Accomplishments

- CrowdStrike's `_normalize_vuln` reads `cve_meta.get("exprt_rating")` right beside the existing `exploit_status` read (same already-cached `/spotlight/entities/vulnerabilities/v2` response, confirmed **zero new API calls**) and attaches the raw ExPRT.AI category (`"HIGH"`, `"CRITICAL"`, etc.) to `native_priority_rating` verbatim — no re-scaling, per D-06. A defensive probe for an unconfirmed numeric companion field (`exprt_score`) populates `native_priority_score` when present, `None` otherwise.
- CrowdStrike's own KEV-ish heuristic (`exploit_status >= 50`, CISA KEV's "Used in the Wild" tier) is now captured into `source_signals` as two keys — the raw `exploit_status` int and a derived `exploit_status_kev_guess` boolean — strictly as **provenance**, never touching the `cisa_kev` column's authority (that remains Plan 01's `_lookup_enrichment` ref-table lookup, untouched by this plan).
- Nessus's `_normalize_vuln` gained `_get_vpr_score()`, a new module-level helper that mirrors the file's own pre-existing `_check_exploit_available` defensive-probe idiom: it tries `plugin_attributes.get("vpr_score")` then falls back to `.get("vpr")`, coercing to `float` and soft-nulling (never crashing) on absence or a non-numeric value. The result — plus a 2-key `source_signals` allowlist (`exploit_available`, `exploitability_ease`) built from the same raw `plugin_attributes` dict — is threaded through the `base` dict so every per-CVE fanout `NormalizedVulnerability(cve_id=cve, **base)` call gets it, matching the file's existing multi-CVE-per-plugin architecture.
- Both connectors now correctly model **missing vs. negative**: a vendor-returned `False`/`"false"` value is captured in `source_signals` (present, negative), while a genuinely-never-returned field is omitted entirely (missing) — proven by dedicated test fixtures on both files, with an additional assertion in every new test that no PII-adjacent (`hostname`, `ip_addresses`) or already-promoted (`cve_id`, `cvss`, `severity`, `epss`, `native_priority`) key ever leaks into `source_signals`.
- Found and fixed a stale, factually-wrong docstring line while editing the exact code it mis-describes (see Deviations) — a zero-behavior-change, comment-only correctness fix.

## Task Commits

Each task was committed atomically (strict RED -> GREEN TDD):

1. **Task 1: CrowdStrike ExPRT rating -> native_priority_rating + source_signals (RED)** - `dd6e2ee` (test)
2. **Task 1: CrowdStrike ExPRT rating -> native_priority_rating + source_signals (GREEN)** - `350bc1b` (feat)
3. **Task 2: Nessus VPR defensive probe -> native_priority_score + source_signals (RED)** - `0a759e4` (test)
4. **Task 2: Nessus VPR defensive probe -> native_priority_score + source_signals (GREEN)** - `b3aefa1` (feat)

**Plan metadata:** (this commit, docs: complete plan)

_TDD gate compliance: for each task, a `test(...)` commit (verified genuinely failing pre-implementation via direct pytest execution — no false-pass) precedes a `feat(...)` commit (verified passing). Both gates present in git log for both tasks — compliant._

## Files Created/Modified

- `backend/app/connectors/crowdstrike.py` - `_normalize_vuln` gains ExPRT.AI rating capture (`native_priority_rating`), a defensive numeric-companion probe (`native_priority_score`), and inline `source_signals` construction from the raw `cve_meta` dict; all 3 attached via the file's existing post-construction ad-hoc-attribute idiom. Module docstring's stale CISA KEV threshold description corrected (comment-only).
- `backend/app/connectors/nessus.py` - New `_SOURCE_SIGNAL_ALLOWLIST` tuple + `_get_vpr_score()` helper (mirrors `_check_exploit_available`'s defensive-probe shape); `_normalize_vuln`'s `base` dict gains `native_priority_score`/`native_priority_rating`(`=None`)/`source_signals`, propagating to every per-CVE fanout call. `base`'s dict literal given an explicit `dict[str, Any]` annotation (proactive mypy hygiene, mirrors Plan 01's `qualys.py` fix — verified to introduce zero new mypy errors either way).
- `backend/tests/test_connectors/test_crowdstrike_connector.py` - 3 new unit tests calling `_normalize_vuln` directly (no HTTP mocking needed): ExPRT rating mapping + source_signals provenance, absent-exprt_rating soft-null, and no-cached-metadata-at-all soft-null.
- `backend/tests/test_connectors/test_nessus_connector.py` - 5 new unit tests calling the module-level `_normalize_vuln` directly: `vpr_score` mapping (2-CVE fanout), `vpr` fallback-candidate mapping, absent-VPR soft-null, missing-vs-negative + no-PII/no-promoted-duplicate proof, and all-3-fields-always-set-even-with-no-plugin_attributes-at-all.

## Decisions Made

- CrowdStrike's `source_signals` carries both the raw `exploit_status` value and a distinctly-named `exploit_status_kev_guess` derived boolean (rather than only the raw number) — see key-decisions above for the full D-08 collision-avoidance rationale.
- CrowdStrike's numeric ExPRT companion probe uses the candidate key `exprt_score` — an educated guess (mirrors `exprt_rating`'s key shape) since RESEARCH.md confirms this field's existence is entirely unverified (Tertiary source only). Flagged below for live re-verification.
- Nessus's `source_signals` allowlist is deliberately scoped to the 2 fields this codebase's own existing code already demonstrates reading from real Nessus payloads (`exploit_available`, `exploitability_ease`) rather than speculatively adding unverified `exploit_framework_*`-style fields.
- ENRICH-03/04/06 left `[ ]` Pending in REQUIREMENTS.md (shared-ID gate with 31-04/31-05, mirroring Plan 01's own precedent for ENRICH-01/02/03/04/06).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected CrowdStrike's stale/factually-wrong module docstring (comment-only)**
- **Found during:** Task 1 (reading `crowdstrike.py:350-408` per the plan's own `<read_first>`, which explicitly flagged this discrepancy)
- **Issue:** The module docstring (line 11) stated `"CISA KEV: derived from exploit_status >= 30"`, but the live code (now confirmed at the exact line I was editing) checks `>= 50`. This is a pre-existing, already-documented discrepancy (31-RESEARCH.md Pitfall 3, 31-PATTERNS.md's CrowdStrike section) — not something I introduced, but directly adjacent to the exact lines this task modifies, and actively misleading to a future reader of the very block I was extending with provenance logic that itself depends on the `>= 50` threshold.
- **Fix:** Corrected the docstring's prose to describe the actual `>= 50` behavior and explicitly note that, as of Plan 01, this connector's own guess is provenance-only (the `cisa_kev` column's sole authority is `sync.py`'s `_lookup_enrichment`). The code's threshold value itself (`exploit_status_id >= 50`) was left byte-for-byte unchanged, per the plan's explicit prohibition against "fixing" the code to match the stale docstring (the prohibition runs the other direction: never let the wrong docstring justify changing correct code).
- **Files modified:** `backend/app/connectors/crowdstrike.py` (docstring only, lines 9-13)
- **Verification:** `ruff check`/`ruff format --check` clean; full `test_crowdstrike_connector.py` suite (9/9) green before and after; zero logic/behavior change (diff is comment-text only).
- **Committed in:** `350bc1b` (Task 1 GREEN commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — comment-only documentation-correctness fix, zero behavior change)
**Impact on plan:** No scope creep. The fix touches only prose adjacent to code this task was already modifying, and was explicitly anticipated as an acceptable comment-only correction by both 31-RESEARCH.md (Pitfall 3) and 31-PATTERNS.md.

## Issues Encountered

- **mypy-baseline "new: 3" report is a confirmed pre-existing flake, not caused by this plan.** Running the project's exact CI gate (`mypy app/ | mypy-baseline filter --allow-unsynced`) after both GREEN commits reported `fixed: 15 / new: 3`. Per-file diffing (`grep crowdstrike.py`/`grep nessus.py` against both the live run and `mypy-baseline.txt`, normalizing line numbers) proved the exact same error-message set exists in both files before and after this plan's changes — zero new crowdstrike.py/nessus.py-specific errors. The "new: 3" is fully explained by a previously-documented nondeterministic flake (a `jose`-stub-missing `note:` hint that mypy attaches to a different importing file each run — baselined against `app/connectors/google_workspace.py`, this run attached it to `app/auth/dependencies.py` instead) — confirmed identical via the project's own `git stash` + `rm -rf .mypy_cache` before/after verification protocol (same result on the clean, pre-Task-1 tree). Matches the precedent already documented in Plan 01's SUMMARY and Phase 29's SUMMARY (see project MEMORY.md `getvul-backend-test-harness-rot` history). Not fixed (out of scope — pre-existing, unrelated to any file this plan touches).
- No other issues. Both external-field-name assumptions (CrowdStrike's `exprt_score` numeric companion, Nessus's VPR field name) are unverified against a live vendor instance — flagged explicitly below per the plan's `<output>` instruction, not silently assumed correct.

## User Setup Required

None — no external service configuration required. Both connectors' new fields are populated entirely from data already fetched by existing API calls (CrowdStrike) or a defensive read of an already-fetched response field (Nessus) — no new credentials, endpoints, or scopes.

## Empirical Re-verification Flags (carried per plan's `<output>` instruction)

- **CrowdStrike ExPRT numeric companion (`exprt_score`):** RESEARCH.md's Assumptions Log lists CrowdStrike's numeric ExPRT companion as **Tertiary/unconfirmed** — no vendor schema documents its existence at all, let alone a field name. This plan's probe key (`exprt_score`) is an educated guess (mirrors `exprt_rating`'s shape under the same `cve` object), verified only to soft-null cleanly when absent. **Recommend verifying against a live Falcon instance's actual `/spotlight/entities/vulnerabilities/v2` response** before relying on this field being populated in production; if the real field name differs (or doesn't exist), `native_priority_score` will silently stay `None` for every CrowdStrike finding (soft failure, not a crash — by design).
- **Nessus VPR field name (`vpr_score` / `vpr`):** RESEARCH.md's Assumptions Log (A1) flags the exact REST JSON field name as unverified this session. This plan probes both candidates in the order recommended by RESEARCH.md. **Recommend verifying against a real Nessus 10.5+ instance's scan-result JSON** (VPR was only added to Nessus Professional in that version) — if neither candidate matches the real field name, `native_priority_score` will silently stay `None` for every Nessus finding (soft failure, not a crash — by design, per the plan's explicit requirement).

## Next Phase Readiness

- 3 of 6 connectors (Defender from Plan 01, CrowdStrike + Nessus from this plan) now fully populate `native_priority_score`/`native_priority_rating`/`source_signals` per the established pattern. Plans 04 (Qualys, Rapid7) and 05 (Wiz + the cross-6 `ENRICH-06` parametrized sweep in `test_connector_normalization.py`) can each extend the exact same shape to the remaining 3 connectors.
- No blockers. `test_crowdstrike_connector.py` (9/9), `test_nessus_connector.py` (10/10), `test_connector_normalization.py` (22/22, unedited by this plan — regression-clean), and `test_vulnerability_enrichment.py` (2/2, Plan 01's integration tests — regression-clean) all green. `ruff check`/`ruff format --check` clean on all 4 touched files. mypy-baseline gate shows zero new violations attributable to either touched source file (see Issues Encountered for the pre-existing flake explanation).
- Plan 05's cross-6 sweep should be able to assert, for CrowdStrike and Nessus specifically: `native_priority_rating` populated-or-None (CrowdStrike only; Nessus is always `None`), `native_priority_score` populated-or-None (both), and `source_signals` always a dict (never `None`) with the documented allowlist keys.

---
*Phase: 31-connector-enrichment-rewrite*
*Completed: 2026-08-05*

## Self-Check: PASSED

All 4 modified source/test files confirmed present on disk; all 4 task commit hashes (`dd6e2ee`, `350bc1b`, `0a759e4`, `b3aefa1`) confirmed in `git log`.
