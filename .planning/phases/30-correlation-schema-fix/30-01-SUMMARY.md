---
phase: 30-correlation-schema-fix
plan: 01
subsystem: database
tags: [postgresql, sqlalchemy, alembic, correlation, array, jsonb, gin-index, tdd]

# Dependency graph
requires: []
provides:
  - "vulnerability_correlations.sources ARRAY(String) + GIN index (ix_vulnerability_correlations_sources), covering all 6 VulnSource values forward-compatibly"
  - "vulnerability_correlations.source_vuln_ids JSONB linkage map ({SOURCE: str(vuln_uuid)})"
  - "correlation_service.py generalized over the full VulnSource enum via _SOURCE_ORDER; SOURCE_COLUMN_MAP removed"
  - "SC#4 regression proof: a Qualys+Rapid7-only correlation (previously silently dropped) now round-trips end-to-end (model -> migration -> service -> API-shaping)"
  - "migration 034_add_correlation_sources (baseline backfill from the 4 legacy columns, then drops them)"
affects: [30-02, 31, 33, 35]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "ARRAY(String)+GIN column mirrors the shipped assets.tags pattern (025_add_asset_tags.py)"
    - "JSONB linkage-only map (no GIN) mirrors Asset.mdm_details"
    - "Canonical-order enum iteration (_SOURCE_ORDER = [s.value for s in VulnSource]) replaces a hardcoded per-source column map"

key-files:
  created:
    - backend/tests/test_correlation_service.py
    - backend/alembic/versions/034_add_correlation_sources.py
    - .planning/phases/30-correlation-schema-fix/deferred-items.md
  modified:
    - backend/app/vulnerabilities/models.py
    - backend/app/vulnerabilities/correlation_service.py
    - backend/mypy-baseline.txt

key-decisions:
  - "Checkpoint (Task 2, gate=blocking, non-autonomous plan) resolved = proceed with the irreversible D-01/D-03/D-06 schema-drop, per explicit user/coordinator approval — not self-selected despite auto-mode-bypass nominally being available under gate=\"blocking\", since auto-mode was inactive and this plan's frontmatter marks it non-autonomous"
  - "mypy-baseline.txt extended by one bare-dict type-arg entry for source_vuln_ids rather than deviating from RESEARCH's locked Mapped[dict | None] shape — mirrors the already-baselined identical pattern on Vulnerability.file_paths (same file) and Asset.mdm_details"
  - "CORR-01/CORR-03 intentionally left [ ] Pending in REQUIREMENTS.md — shared-ID gate: sibling plan 30-02 also declares CORR-01/CORR-02/CORR-03 and hasn't produced a SUMMARY yet; all three flip together when 30-02 (the last declaring plan) finishes"

requirements-completed: [CORR-01, CORR-03]

coverage:
  - id: D1
    description: "A Qualys+Rapid7-only finding (previously silently dropped) now correlates: sources == ['QUALYS','RAPID7'], sources_count == 2, confidence == 'MEDIUM', source_vuln_ids maps both to str(uuid)"
    requirement: "CORR-01"
    verification:
      - kind: integration
        ref: "backend/tests/test_correlation_service.py#test_qualys_rapid7_only_correlation_no_longer_silently_dropped"
        status: pass
    human_judgment: false
  - id: D2
    description: "vulnerability_correlations gains sources ARRAY(String)+GIN and source_vuln_ids JSONB; the 4 legacy per-source FK columns (crowdstrike/nessus/defender/wiz_vuln_id) are dropped"
    requirement: "CORR-01"
    verification:
      - kind: other
        ref: "alembic upgrade head (exit 0) + psql \\d vulnerability_correlations"
        status: pass
    human_judgment: false
  - id: D3
    description: "correlation_service.py loops the full VulnSource enum via one canonical _SOURCE_ORDER list; SOURCE_COLUMN_MAP removed; sources_count and the source-name list derive from the same list so they can never disagree"
    requirement: "CORR-03"
    verification:
      - kind: other
        ref: "grep -c SOURCE_COLUMN_MAP backend/app/vulnerabilities/correlation_service.py == 0; grep -n _SOURCE_ORDER backend/app/vulnerabilities/correlation_service.py"
        status: pass
    human_judgment: false
  - id: D4
    description: "Tenant scoping and auth on the correlation read path are preserved unchanged: _find_correlated_groups/_prune_stale_correlations are byte-for-byte unedited, and router.py's require_viewer-gated GET /{vuln_id}/correlation route needed zero edits (D-09's dict-spread shape change flows through automatically)"
    verification:
      - kind: other
        ref: "git diff backend/app/vulnerabilities/router.py (0 lines) + git diff backend/app/vulnerabilities/correlation_service.py (confirms only run_correlations/get_correlation_for_vuln bodies changed)"
        status: pass
    human_judgment: false

duration: 21min
completed: 2026-08-04
status: complete
---

# Phase 30 Plan 01: Correlation Schema Fix — Generalized Source-Set Summary

**Replaced the 4-of-6-source hardcoded FK-column shape on `vulnerability_correlations` with a `sources ARRAY(String)`+GIN / `source_vuln_ids` JSONB pair generalized over the full 6-value `VulnSource` enum, proving end-to-end that a previously-silently-dropped Qualys+Rapid7 correlation now round-trips correctly through model → migration → service → API-shaping.**

## Performance

- **Duration:** 21 min
- **Started:** 2026-08-04T13:03:16Z
- **Completed:** 2026-08-04T13:24:06Z
- **Tasks:** 3 (RED test → blocking checkpoint:decision → GREEN tracer)
- **Files modified:** 6 (3 new, 3 modified)

## Accomplishments

- `VulnerabilityCorrelation` model gains `sources: Mapped[list[str] | None]` (ARRAY(String), GIN-indexed) and `source_vuln_ids: Mapped[dict | None]` (JSONB); the 4 hardcoded per-source FK columns (`crowdstrike_vuln_id`/`nessus_vuln_id`/`defender_vuln_id`/`wiz_vuln_id`) are removed
- New migration `034_add_correlation_sources` (revision id 27 chars, `down_revision = "033_add_ai_batch_job"`): adds both new columns, baseline-backfills them from the 4 legacy columns via raw SQL (`ARRAY_REMOVE`/`jsonb_strip_nulls`), then drops the 4 FK columns (auto-dropping their inline FK constraints) — applied cleanly against the live dev `postgres:16-alpine` (`alembic upgrade head` exit 0, confirmed via `\d vulnerability_correlations`)
- `correlation_service.py` generalized: `SOURCE_COLUMN_MAP` deleted; module-level `_SOURCE_ORDER = [s.value for s in VulnSource]` drives both the `sources` list and `sources_count` from one canonical-order code path (CORR-03 — structurally cannot disagree); confidence bands recalibrated per the already-locked D-08 (`HIGH>=4`/`MEDIUM 2-3`/`LOW 1`); `source_vuln_ids` values `str()`-cast before the JSONB write (raw `uuid.UUID` is not JSON-serializable)
- `get_correlation_for_vuln` rewritten to return `corr.sources or []` / `corr.source_vuln_ids or {}` directly, replacing the old 4-if reconstruction block; tenant/cve/asset `.where()` scoping preserved verbatim
- `_find_correlated_groups` and `_prune_stale_correlations` left byte-for-byte unchanged (confirmed via `git diff`); `router.py`'s `GET /{vuln_id}/correlation` needed zero edits — the `{"correlated": True, **corr}` dict-spread automatically carries the new shape through
- SC#4 regression test (`test_qualys_rapid7_only_correlation_no_longer_silently_dropped`) written RED in Task 1 (genuine failure against the unmodified 4-column schema: `corr["sources"] == []` instead of `['QUALYS','RAPID7']`), confirmed GREEN after Task 3's rewrite

## Task Commits

Each task was committed atomically:

1. **Task 1: Write the SC#4 Qualys+Rapid7 regression test (RED)** — `792e684` (test)
2. **[Checkpoint] Task 2: irreversible schema-drop decision** — resolved **proceed** via explicit coordinator/user approval (no commit; decision recorded in STATE.md at `d991274`)
3. **Task 3: Generalized source-set — model + migration + service rewrite (GREEN, tracer)** — `a0de97f` (feat)

**Interim tracking commit:** `d991274` (docs — recorded the Task 1-complete / Task 2-checkpoint-pause position in STATE.md before the decision arrived)

**Plan metadata:** *(this commit)*

## Files Created/Modified

- `backend/tests/test_correlation_service.py` (NEW) — SC#4 regression test + `_seed_asset`/`_seed_vuln` helpers
- `backend/alembic/versions/034_add_correlation_sources.py` (NEW) — schema migration: add `sources`+GIN, add `source_vuln_ids`, baseline backfill, drop 4 FK columns
- `backend/app/vulnerabilities/models.py` — `VulnerabilityCorrelation`: +`sources`, +`source_vuln_ids`, -4 FK columns
- `backend/app/vulnerabilities/correlation_service.py` — `SOURCE_COLUMN_MAP` removed; `_SOURCE_ORDER` added; `run_correlations`/`get_correlation_for_vuln` rewritten over the canonical source list
- `backend/mypy-baseline.txt` — +1 baselined `type-arg` entry for the new `source_vuln_ids` field (mirrors the pre-existing, already-accepted bare-`dict` pattern)
- `.planning/phases/30-correlation-schema-fix/deferred-items.md` (NEW) — logs an unrelated, pre-existing mypy `note` nondeterminism investigated during this plan (not fixed, out of scope)

## Decisions Made

- Checkpoint Task 2 (irreversible schema-drop: add `sources`+GIN + `source_vuln_ids`, DROP the 4 legacy FK columns) resolved **proceed** by explicit coordinator/user approval mid-execution. The executor did not self-select this despite `gate="blocking"` nominally permitting an auto-mode bypass — auto-mode was inactive (`workflow._auto_chain_active`/`workflow.auto_advance` both false) and the plan's own frontmatter (`autonomous: false`) marks the whole plan non-autonomous, so the decision correctly stopped for a human regardless.
- `mypy-baseline.txt` gained one new "Missing type arguments for generic type dict" entry for `source_vuln_ids` rather than typing it as `dict[str, str] | None` to dodge the baseline edit — RESEARCH Pattern 2 explicitly locks the bare `Mapped[dict | None]` shape (mirroring `Asset.mdm_details`), and that exact error class is already an accepted, baselined pattern elsewhere in this same file (`Vulnerability.file_paths`). Verified zero net-new unbaselined violations: `mypy app/ | mypy-baseline filter --allow-unsynced` shows `fixed=3/new=3`, identical to a completely clean-HEAD run (git-stash + `rm -rf .mypy_cache` before/after diff).
- `CORR-01`/`CORR-03` deliberately left `[ ]` Pending in `REQUIREMENTS.md` even though this plan's own frontmatter declares them — the shared-ID gate applies: sibling plan `30-02` also declares `CORR-01`/`CORR-02`/`CORR-03` and has not produced a SUMMARY yet. All three flip to Complete together when `30-02` (the last declaring plan) finishes, mirroring the `AIE-01/02` (Phase 28) and `AID-01` (Phase 27) precedents already in this project's history.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Extended mypy-baseline.txt for the new source_vuln_ids field**
- **Found during:** Task 3, post-implementation type-check pass
- **Issue:** `source_vuln_ids: Mapped[dict | None] = mapped_column(JSONB, nullable=True)` (the exact shape RESEARCH Pattern 2 locks) introduces a new "Missing type arguments for generic type dict" mypy error on `models.py` that isn't yet in `mypy-baseline.txt`. CI's actual gate (`mypy app/ | mypy-baseline filter --allow-unsynced`) fails on any *new*, unbaselined error — this would have blocked CI despite being byte-identical to an already-accepted pattern (`Vulnerability.file_paths` in the same file, `Asset.mdm_details` elsewhere).
- **Fix:** Added one duplicate line to `mypy-baseline.txt` for `app/vulnerabilities/models.py`'s "Missing type arguments for generic type dict" error, matching the pre-existing entry's exact text.
- **Files modified:** `backend/mypy-baseline.txt`
- **Verification:** `mypy app/ | mypy-baseline filter --allow-unsynced` (CI's exact command) shows `fixed=3/new=3`, matching a clean-HEAD baseline run exactly (verified via `git stash` + `rm -rf .mypy_cache` before/after diff — see Issues Encountered for the investigation that ruled out a real regression).
- **Committed in:** `a0de97f` (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking — CI gate)
**Impact on plan:** Necessary to keep the CI mypy gate green while following the plan's own verbatim-specified model shape. No scope creep — the fix is a one-line baseline addition mirroring an already-accepted pattern, not new production logic.

## Issues Encountered

- **Transient mypy `note`-line nondeterminism, investigated and confirmed pre-existing.** The first `mypy app/ | mypy-baseline filter --allow-unsynced` run after Task 3's edits showed 5 "new" lines instead of the expected 3 (2 extra `app/assets/service.py` `AssetSummary`/`AssetResponse` notes). Rather than assume this was caused by my changes, I investigated per the exact methodology already documented for this project's identical Phase 29 flake: `git stash` the Task 3 diff + `rm -rf .mypy_cache`, then re-ran mypy twice on a completely clean HEAD. The clean-HEAD runs were stable at 3 new lines (the `app/auth/dependencies.py:10` jose-stub-missing hint) on both attempts; popping the stash and re-running with the exact same Task 3 diff present *also* settled back to 3. This proves the transient 5-line reading was itself an instance of the same pre-existing, already-documented (Phase 29) nondeterminism — not something introduced by this plan's changes to `models.py`/`correlation_service.py` (neither touches `app/auth/dependencies.py` or `app/assets/service.py`). Logged to `deferred-items.md`, not fixed — out of scope.
- **Migration's baseline backfill exercised against an empty table in this environment.** The live dev Postgres had 0 rows in `vulnerability_correlations` at migration time (the SC#4 test's row was cleaned up by `conftest.py`'s post-test `TRUNCATE ... CASCADE`), so the backfill `UPDATE` statements ran as a correct no-op here rather than against populated legacy data. The backfill SQL's correctness against actually-populated rows (including the exact pre-fix Qualys/Rapid7 bug signature) was already verified via RESEARCH.md's own separate disposable-container dry run (Pitfall 5) — not re-derived in this environment, since D-06/D-07 already characterize this table as small/rebuildable and this repo's dev DB happened to be clear.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- **Ready for 30-02:** The schema (`sources`+GIN, `source_vuln_ids` JSONB) and the generalized `correlation_service.py` are fully in place and proven via SC#4. Plan 02 builds the `_recorrelate_tenant`/`recorrelate_all_tenants.py` per-tenant data-recovery script, the runtime zero-loss verification test (`COALESCE(array_length(sources,1),0) != sources_count`), and the broader 1-of-6-through-6-of-6 combinatorial coverage (banding/invariant/tenant-scope) on top of this plan's foundation — no blockers.
- **REQUIREMENTS.md:** `CORR-01`/`CORR-02`/`CORR-03` remain `[ ]` Pending by design (shared-ID gate with 30-02); expect all three to flip to `[x]` Complete when 30-02's SUMMARY lands.
- **ROADMAP.md:** Phase 30's own checkbox and the `30-02-PLAN.md` line remain unchecked; only the `30-01-PLAN.md` line is now checked (1/2 plans complete).
- No blockers, no auth gates, no user setup pending.

## Self-Check: PASSED

- FOUND: `backend/tests/test_correlation_service.py`
- FOUND: `backend/alembic/versions/034_add_correlation_sources.py`
- FOUND: `.planning/phases/30-correlation-schema-fix/deferred-items.md`
- FOUND: `backend/app/vulnerabilities/models.py`
- FOUND: `backend/app/vulnerabilities/correlation_service.py`
- FOUND: `backend/mypy-baseline.txt`
- FOUND commit: `792e684` (Task 1 — RED test)
- FOUND commit: `d991274` (interim checkpoint-pause tracking)
- FOUND commit: `a0de97f` (Task 3 — GREEN tracer)
- Re-ran plan-level `<verification>`: `alembic current` → `034_add_correlation_sources (head)`; `pytest tests/test_correlation_service.py -v` → 1 passed; `grep -c SOURCE_COLUMN_MAP` → 0; `git diff` on `router.py` → empty, on `correlation_service.py` → confirms only the two target functions changed. All acceptance criteria for Tasks 1 and 3 re-verified PASS.

---
*Phase: 30-correlation-schema-fix*
*Plan: 01*
*Completed: 2026-08-04*
