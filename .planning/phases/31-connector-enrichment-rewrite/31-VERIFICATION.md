---
phase: 31-connector-enrichment-rewrite
verified: 2026-08-05T12:25:12Z
status: human_needed
score: 5/5 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Confirm the unverified vendor field-name assumptions against live scanner accounts: CrowdStrike's numeric ExPRT companion (probed as `exprt_score`), Nessus VPR's exact JSON field (`vpr_score`/`vpr`), Qualys QDS's exact element name + `show_qds_factors` param, Rapid7 `riskScore`'s field name/location on the AssetVulnerability association, and Wiz's 5 GraphQL field names (`epssSeverity`/`epssPercentile`/`epssProbability`/`exploitabilityScore`/`impactScore`)."
    expected: "Each connector's native_priority_score/native_priority_rating (and Wiz's 5 source_signals sub-scores) populate with real, non-null values on a live sync against a real vendor tenant, not just soft-null on the synthetic test fixtures."
    why_human: "No live CrowdStrike/Nessus/Qualys/Rapid7/Wiz credentials are available in this session. These are external-service-schema assumptions (5 of RESEARCH.md's Assumptions Log entries, A1-A4 plus the ExPRT numeric companion) that the code soft-nulls safely if wrong (never crashes, never breaks ingestion — verified), but only a live vendor payload can confirm the exact field name/path guesses are correct. All 5 plan SUMMARYs independently self-flagged this same item as needing live re-verification."
---

# Phase 31: Connector Enrichment Rewrite Verification Report

**Phase Goal:** Every connector captures and persists the richer native signal each scanner actually provides, so v4.0's enrichment claims are real data, not permanently-null columns.
**Verified:** 2026-08-05T12:25:12Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

All 5 ROADMAP success criteria are structurally VERIFIED against the actual codebase (not SUMMARY claims) — via direct code reads, independent pytest execution of every claimed test file, live-Postgres schema introspection, and an isolated worktree diff to rule out a false regression. One residual, already-self-flagged risk (exact vendor field-name assumptions, unverifiable without live vendor credentials) is surfaced as Human Verification — it does not invalidate any of the 5 truths below, all of which hold regardless of whether those specific field-name guesses turn out correct in production.

### Observable Truths

| #   | Truth (ROADMAP Success Criterion)                                                                                                                  | Status     | Evidence |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | -------- |
| 1   | EPSS score + percentile populated on newly-ingested findings for every one of the 6 connectors (today's `epss_score` populated by none) | ✓ VERIFIED | `sync.py::_lookup_enrichment` (lines 314-329) is called unconditionally at the top of `_upsert_vulnerability` (line 336) — the single choke point ALL 6 connector types pass through via `run_sync`'s generic `CONNECTOR_CLASSES` loop (sync.py:63-70, 152-162). Both `existing`/insert branches set `epss_score`/`epss_percentile` from the ref-table lookup, never from the connector. `test_vulnerability_enrichment.py` (2/2 passed, re-run independently) proves a seeded `EpssScore` row populates the column at ingest. Live dev Postgres: `epss_scores` table has 355,094 real rows (confirmed via `docker exec ... psql`), proving the daily feed-fetch mechanism actually works end-to-end, not just against mocks. |
| 2   | CISA KEV status populated per finding from a real authoritative feed for every connector, including Defender (whose `cisa_kev=False` hardcode is fixed) | ✓ VERIFIED | `defender.py:303` still hardcodes `cisa_kev=False` on the dataclass (correct — plan explicitly required the fix downstream, not in the parser). `sync.py::_lookup_enrichment` returns `kev_hit is not None` purely from the `CisaKev` table select — `v.cisa_kev` (the connector's guess) is never read for the persisted column in either upsert branch (grep-confirmed: `existing.cisa_kev = cisa_kev` / `cisa_kev=cisa_kev` both reference the lookup's return, not `v.cisa_kev`). `test_vulnerability_enrichment.py::test_upsert_vulnerability_populates_epss_and_kev_from_ref_tables` explicitly asserts `row.cisa_kev is True` even though the Defender-shaped fixture's dataclass field is `cisa_kev=False` — a genuinely falsifiable, non-tautological proof the hardcode is overridden. Live DB: `cisa_kev` table has 1,660 real rows. |
| 3   | Vendor-native exploitability/priority signals land in promoted typed columns that can be sorted/filtered, not flattened to booleans at ingestion | ✓ VERIFIED | Migration 035 adds `native_priority_score Numeric(7,2)` + `native_priority_rating String(50)` with btree indexes `ix_vulnerabilities_native_priority_score`/`ix_vulnerabilities_epss_score` (confirmed live via `\d vulnerabilities` — both indexes exist). All 6 connectors explicitly set both fields on every emitted finding (proven by the cross-6 parametrized sweep, 6/6 passed): CrowdStrike sets `native_priority_rating` from raw `exprt_rating` (categorical, verbatim, no rescale); Nessus/Qualys/Rapid7 set `native_priority_score` from raw VPR/QDS/riskScore; Defender/Wiz explicitly set both to `None` (no vendor composite exists for either — correctly NOT synthesized, matching RESEARCH.md Pitfall 6's explicit prohibition). Qualys's QDS is read from the per-detection dict, not `kb_cache` (Pitfall 4 regression-tested); Rapid7's riskScore is read from `vuln_entry`, not `detail` (Pitfall 5 regression-tested). See Human Verification for the residual field-name-guess risk. |
| 4   | Long-tail scanner-native fields land in a queryable `source_signals` JSONB field per finding, with a fixture proving "missing" is distinguishable from "negative" | ✓ VERIFIED | Migration 035 adds `source_signals JSONB`. Every one of the 6 connectors builds `source_signals` inline from the RAW vendor dict in the same scope (never from the already-bool()-coerced dataclass field — Pitfall 2 correctly avoided everywhere, spot-checked in all 6 files), adding a key ONLY when present in the raw payload (`if key in record`/`if key in node`/`if key in attrs`, never `.get()` with a default). `test_defender_connector.py::test_defender_normalize_vuln_source_signals_missing_vs_negative` (re-run, passing) is a genuinely falsifiable fixture: `source_signals["exploitVerified"] is False` (present+negative) AND `"exploitInKit" not in source_signals` / `"vpr" not in source_signals` (genuinely absent from the raw record — missing) in the SAME returned finding. No PII-adjacent keys (`hostname`/`ip_addresses`/`last_login_user`/`serial_number`) or already-promoted columns leak into any connector's allowlist (grep-confirmed across all 6 files + asserted in tests). |
| 5   | A dedicated daily job in the existing in-process scheduler refreshes global, tenant-independent `epss_scores`/`cisa_kev` reference tables, decoupled from any individual connector's sync cadence | ✓ VERIFIED | `enrichment_feeds.py` (257 lines) implements `_fetch_and_parse_epss`/`_fetch_and_parse_kev` (pure, DB-free, real gzip/redirect/JSON handling) + `refresh_enrichment_reference_data` (D-09 atomic-swap: fetch+parse fully before ANY DB write; on any exception, returns `{"status":"failed"}` without touching the DB) + `repropagate_enrichment` (D-01/D-02 raw `UPDATE...FROM`, bidirectional KEV recompute). `scheduler.py` wires `_dispatch_enrichment_refresh` (24h-gated, lock-guarded against a genuine concurrency race the executor found and fixed) into both `_scheduler_loop()`'s per-tick body (line 339) AND an eager first-run in `start_scheduler()` (line 360) — D-10. `start_scheduler()` is confirmed called from `main.py`'s lifespan (not orphaned). `epss_scores`/`cisa_kev` confirmed to have NO `tenant_id` column via live `\d` introspection (D-11). Entirely decoupled from connector sync: no connector file imports `enrichment_feeds` or touches the DB (grep-confirmed zero `sqlalchemy`/`AsyncSession` imports in any of the 6 connector files). 8/8 scheduler tests independently re-run and passing, including the 24h-gate, atomic-swap-keeps-last-good, and concurrency-race regression tests. Live DB proof: `epss_scores`=355,094 rows, `cisa_kev`=1,660 rows — the mechanism has actually run against the real feeds in this environment, not just against mocks. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | ----------- | ------ | ------- |
| `backend/alembic/versions/035_add_enrichment_columns.py` | 4 new `vulnerabilities` columns + 2 sort indexes | ✓ VERIFIED | Exists, chains `034→035`, symmetric `upgrade()`/`downgrade()`, applied live (`alembic heads` = single head `036_add_enrichment_ref_tables`) |
| `backend/alembic/versions/036_add_enrichment_ref_tables.py` | `epss_scores`/`cisa_kev` global tables | ✓ VERIFIED | Exists, chains `035→036`, `cve_id` PK, NO `tenant_id` (confirmed live via psql `\d`) |
| `backend/app/vulnerabilities/models.py` | 4 new `Vulnerability` columns + `EpssScore`/`CisaKev` ORM models | ✓ VERIFIED | All present with correct types (Numeric(5,4)/(7,2)/String(50)/JSONB); `EpssScore`/`CisaKev` compose `Base, TimestampMixin` only (no tenant_id/UUID mixin, per D-11) |
| `backend/app/connectors/base.py` | `native_priority_score`/`native_priority_rating`/`source_signals` dataclass fields | ✓ VERIFIED | Present, typed `dict[str, Any] \| None` (strict-mypy-correct, not the interfaces block's literal bare `dict`) |
| `backend/app/connectors/sync.py` | `_lookup_enrichment` + catalog-authoritative wiring in both branches | ✓ VERIFIED | Confirmed both `existing.*` and insert branches use the lookup's return, never `v.cisa_kev` |
| `backend/app/connectors/defender.py` | source_signals allowlist + explicit-null native + untouched hardcode | ✓ VERIFIED | `_SOURCE_SIGNAL_ALLOWLIST` (6 raw keys, no PII); `cisa_kev=False` hardcode present at line 303, byte-for-byte as before |
| `backend/app/connectors/crowdstrike.py` | ExPRT rating → native_priority_rating; KEV-guess provenance-only | ✓ VERIFIED | `exprt_rating` read at line 378 beside pre-existing `exploit_status` read (zero new API calls); `exploit_status`/`exploit_status_kev_guess` in source_signals, never sets the `cisa_kev` column |
| `backend/app/connectors/nessus.py` | VPR defensive probe → native_priority_score | ✓ VERIFIED | `_get_vpr_score()` tries `vpr_score` then `vpr`, soft-nulls; threaded through the `base` dict so every per-CVE fanout finding gets it |
| `backend/app/connectors/qualys.py` | `show_qds_factors=1` + QDS from detection dict (not kb_cache) | ✓ VERIFIED | Param added to `_fetch_all_detections`; `_get_qds()` reads `detection.get("QDS"/"qds")`, never `kb_cache` — regression test proves a kb_cache QDS-shaped key does NOT leak in |
| `backend/app/connectors/rapid7.py` | riskScore from `vuln_entry` (not `detail`) | ✓ VERIFIED | `_get_risk_score(vuln_entry)` captured before the per-CVE loop; regression test proves a `detail`-side riskScore-shaped key is ignored |
| `backend/app/connectors/wiz.py` | Guarded enriched GraphQL query + explicit-null native | ✓ VERIFIED | `VULNERABILITY_QUERY_ENRICHED` (5 new fields) tried first; `WizGraphQLSchemaError` triggers fallback to the unchanged base `VULNERABILITY_QUERY`; `native_priority_score/rating` explicit `None` |
| `backend/app/connectors/enrichment_feeds.py` | EPSS/KEV fetch+parse, atomic swap, re-propagation | ✓ VERIFIED | 257 lines; all 4 functions present and match D-09/D-01/D-02 contracts exactly |
| `backend/app/connectors/scheduler.py` | `_dispatch_enrichment_refresh` + eager first-run + lock | ✓ VERIFIED | Present, wired into both `_scheduler_loop()` and `start_scheduler()`; `_enrichment_refresh_lock` closes a genuine, live-reproduced concurrency race |
| `backend/app/vulnerabilities/schemas.py` | `VulnerabilityResponse` gains the 4 new fields | ✓ VERIFIED | Present, `= None` trailing style matching `exploit_status_id` precedent |
| `backend/tests/test_vulnerability_enrichment.py` | SC#1/SC#2 integration proof | ✓ VERIFIED | 2/2 tests, re-run independently, genuinely falsifiable (asserts catalog overrides the connector's own `False` guess) |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | --- | --- | ------ | ------- |
| `sync.py::_upsert_vulnerability` | `epss_scores`/`cisa_kev` tables | `_lookup_enrichment` select-by-`cve_id` | ✓ WIRED | Called unconditionally at line 336, before either branch runs |
| `run_sync` (all 6 `CONNECTOR_CLASSES`) | `_upsert_vulnerability` | per-finding loop (sync.py:152-162) | ✓ WIRED | No connector-specific bypass exists — confirmed single generic path for CrowdStrike/Nessus/Defender/Wiz/Qualys/Rapid7 |
| `defender.py::_normalize_vuln` | `NormalizedVulnerability.source_signals` | inline raw-dict allowlist build | ✓ WIRED | Same pattern independently confirmed in crowdstrike.py/nessus.py/qualys.py/rapid7.py/wiz.py |
| `scheduler.py::_scheduler_loop` / `start_scheduler` | `enrichment_feeds.refresh_enrichment_reference_data` + `repropagate_enrichment` | `_dispatch_enrichment_refresh` inline `await` | ✓ WIRED | Both call sites confirmed (line 339 per-tick, line 360 eager); inline-await (not `create_task`), matching the plan's explicit deviation rationale |
| `main.py` lifespan | `scheduler.start_scheduler()` | direct call | ✓ WIRED | Confirmed at `main.py:110` — the scheduler (and therefore the enrichment refresh) is not dead/orphaned code |
| `enrichment_feeds.py` | `vulnerabilities` table | raw `text()` `UPDATE ... FROM epss_scores`/`cisa_kev` subquery | ✓ WIRED | Both statements present, unscoped by tenant (correct — CVE-level fact), proven bidirectional (flips both True→catalog-member and False→non-member) by 2 dedicated tests |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `vulnerabilities.epss_score`/`epss_percentile` | `_lookup_enrichment` return | `epss_scores` table, refreshed by `enrichment_feeds._fetch_and_parse_epss` against the real FIRST.org feed | Yes — live dev Postgres has 355,094 real rows (verified via direct `psql` query, not a test fixture) | ✓ FLOWING |
| `vulnerabilities.cisa_kev` | `_lookup_enrichment` return | `cisa_kev` table, refreshed against the real CISA JSON catalog | Yes — live dev Postgres has 1,660 real rows | ✓ FLOWING |
| `vulnerabilities.native_priority_score`/`rating` | connector dataclass fields | each connector's own already-fetched vendor payload (no DB, no external dependency) | Structurally yes (raw values flow through unmodified); the live `vulnerabilities` table itself has 0 rows in this dev environment (no connector has been run against a real vendor tenant here), so the *actual populated values* in production depend on the vendor field-name assumptions — see Human Verification | ⚠️ STRUCTURAL (see note) |
| `vulnerabilities.source_signals` | connector dataclass field | each connector's raw vendor payload, key-presence-checked | Structurally yes, same caveat as above | ⚠️ STRUCTURAL (see note) |

Note: the "STRUCTURAL" flag above is not a wiring defect — the code path is fully connected and correctly implemented (proven by 100+ passing unit/integration tests using synthetic fixtures shaped like real vendor payloads). It reflects that this dev environment has no live-vendor-connected sync to observe end-to-end with real production data, which is exactly the Human Verification item already listed.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Alembic chain resolves to single head | `alembic heads` | `036_add_enrichment_ref_tables (head)` | ✓ PASS |
| Live schema has the 4 new columns + 2 indexes | `psql \d vulnerabilities` (docker) | `epss_percentile`, `native_priority_score`, `native_priority_rating`, `source_signals` + both indexes present | ✓ PASS |
| Live ref tables have no `tenant_id`, `cve_id` PK | `psql \d epss_scores` / `\d cisa_kev` (docker) | Confirmed — no `tenant_id` column, `cve_id` is PK on both | ✓ PASS |
| Live ref tables are populated with real feed data | `psql SELECT count(*)` (docker) | `epss_scores`=355,094, `cisa_kev`=1,660 | ✓ PASS |
| Defender connector tests | `pytest tests/test_connectors/test_defender_connector.py` | 7 passed | ✓ PASS |
| EPSS/KEV write-path integration tests | `pytest tests/test_vulnerability_enrichment.py` | 2 passed | ✓ PASS |
| Enrichment feed fetch/parse/swap/repropagate tests | `pytest tests/test_enrichment_feeds.py` | 10 passed | ✓ PASS |
| Scheduler dispatch tests (24h-gate, atomic-swap, concurrency race) | `pytest tests/test_scheduler_enrichment_refresh.py` | 8 passed | ✓ PASS |
| CrowdStrike + Nessus connector tests | `pytest tests/test_connectors/test_crowdstrike_connector.py tests/test_connectors/test_nessus_connector.py` | 19 passed | ✓ PASS |
| Qualys + Rapid7 connector tests | `pytest tests/test_connectors/test_qualys_connector.py tests/test_connectors/test_rapid7_connector.py` | 24 passed | ✓ PASS |
| Wiz connector tests | `pytest tests/test_connectors/test_wiz_connector.py` | 7 passed | ✓ PASS |
| Cross-6 ENRICH-06 normalization sweep | `pytest tests/test_connector_normalization.py` | 28 passed (incl. 6/6 parametrized cross-connector cases) | ✓ PASS |
| Scheduler/connector-health regression | `pytest tests/test_scheduler_ai_batch.py tests/test_connector_health.py` | 16 passed | ✓ PASS |
| Downstream Vulnerability-model consumers (dashboard/SLA/sort/facets/filter/group/router) | `pytest tests/{test_dashboard_tiles,test_sla_service,test_top_vuln,test_vuln_facets,test_vuln_group_host,test_vuln_sort,test_vuln_source_filter,test_vulnerabilities}.py` | 47 passed total, zero regressions | ✓ PASS |
| Lint | `ruff check app/connectors/ app/vulnerabilities/models.py app/vulnerabilities/schemas.py alembic/versions/035_*.py alembic/versions/036_*.py` | All checks passed | ✓ PASS |
| Type-check regression isolation | `mypy app/ \| mypy-baseline filter` then independently re-run against a `git worktree` checkout of the pre-Phase-31 commit (`83cc38b`) | Both trees show the identical `app/auth/dependencies.py:10/124/133` 3-error set — confirmed pre-existing flake, NOT a Phase 31 regression (independently reproduced, not just trusting the SUMMARY's claim) | ✓ PASS |
| All 18 task commit hashes across 5 SUMMARYs | `git log --oneline --all \| grep -E "<18 hashes>"` | All 18 present | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
| ----------- | ---------- | ----------- | ------ | -------- |
| ENRICH-01 | 31-01, 31-02 | EPSS score+percentile captured per finding, populated for every connector | ✓ SATISFIED | `_lookup_enrichment` (Plan 01) + real feed refresh (Plan 02); REQUIREMENTS.md marked `[x]` Complete |
| ENRICH-02 | 31-01, 31-02 | Real CISA KEV status from authoritative feed, Defender hardcode fixed | ✓ SATISFIED | Catalog-authoritative lookup (Plan 01) + real feed refresh (Plan 02); test proves hardcode override |
| ENRICH-03 | 31-01, 31-03, 31-04, 31-05 | Vendor-native priority signals in typed, sortable/filterable columns | ✓ SATISFIED | All 4 composite-signal connectors (CrowdStrike/Nessus/Qualys/Rapid7) populate raw; Defender/Wiz correctly null (Pitfall 6) |
| ENRICH-04 | 31-01, 31-03, 31-04, 31-05 | Long-tail fields in queryable `source_signals`, missing-vs-negative | ✓ SATISFIED | All 6 connectors build allowlists from raw payload; SC#4 fixture proven on Defender, mirrored on all others |
| ENRICH-05 | 31-02 | Global ref tables refreshed by dedicated daily job, decoupled from connector cadence | ✓ SATISFIED | `enrichment_feeds.py` + scheduler wiring; live DB proves it actually ran against real feeds |
| ENRICH-06 | 31-01, 31-03, 31-04, 31-05 | All 6 connectors thread native signals, never permanently null/inconsistent | ✓ SATISFIED | Cross-6 parametrized sweep (`test_connector_normalization.py`), 6/6 passing, mutation-verified for real discriminating power per 31-05-SUMMARY |

No orphaned requirements: REQUIREMENTS.md's traceability table maps all 6 ENRICH IDs to Phase 31 with status `Complete`, and the "Unmapped: 0" line confirms full coverage. Every requirement ID declared across the 5 plans' frontmatter is accounted for above; none declared in REQUIREMENTS.md are missing from a plan's `requirements:` field.

### Anti-Patterns Found

None at BLOCKER or WARNING severity. Specifically checked and ruled out:
- No `return null`/empty-stub implementations in any of the 11 modified/created source files.
- No TODO/FIXME/PLACEHOLDER markers introduced by this phase's changes.
- No hardcoded empty `source_signals = {}` that's never populated — every connector's dict is populated via a real per-key presence-check loop reading a real payload variable in scope.
- The `defender.py` `cisa_kev=False` hardcode is NOT a stub — it's the plan's explicitly-required, correctly-preserved artifact (the fix lives downstream by design, verified above).
- The `native_priority_score=None`/`native_priority_rating=None` explicit-null lines in `defender.py`/`wiz.py` are NOT anti-patterns — they are the deliberate, RESEARCH-mandated behavior for the 2 connectors with no vendor-authored composite (Pitfall 6), correctly distinguished from omission by being explicitly set rather than left to dataclass defaults.

ℹ️ INFO: `31-VALIDATION.md`'s frontmatter still has `nyquist_compliant: false` / `status: draft` — per this project's own MEMORY.md precedent (`getvul-nyquist-validation-state`: pre-exec planning artifacts that don't get flipped post-hoc are a known, already-triaged, project-wide pattern, not a phase-specific gap), this is not treated as a Phase 31 blocker.

### Human Verification Required

### 1. Live vendor field-name confirmation for the 4-5 composite-signal connectors

**Test:** Run each connector's real sync against a genuine vendor tenant (CrowdStrike Falcon, Tenable Nessus 10.5+, Qualys VMDR, Rapid7 InsightVM, Wiz) and inspect the resulting `vulnerabilities.native_priority_score`/`native_priority_rating`/`source_signals` for real, non-null values (or, for Wiz, confirm the enriched GraphQL query doesn't fall back to the base query due to a schema error).
**Expected:** CrowdStrike's `exprt_rating` populates `native_priority_rating` (high confidence per RESEARCH.md); Nessus's VPR, Qualys's QDS, Rapid7's `riskScore`, CrowdStrike's numeric ExPRT companion, and Wiz's 5 GraphQL sub-scores populate their target fields with real values, not silently staying `None`/absent forever.
**Why human:** No live vendor credentials are available in this session. These are the exact 5 items each plan's SUMMARY.md itself flagged under "Empirical Re-verification Flags" (RESEARCH.md Assumptions Log A1-A4 + the CrowdStrike ExPRT numeric companion) — the code's soft-null-on-absence design is correctly implemented and tested (verified above), but only a live vendor payload can confirm the specific field-name/path guesses are actually correct, since GraphQL/REST schemas can't be introspected without live credentials. This is squarely "external service integration" verification per the standard human-verification categories, not a code-level gap.

### Gaps Summary

No gaps. All 5 ROADMAP success criteria are VERIFIED with strong, independently-reproduced evidence (not just SUMMARY claims): direct code reads of all 11 touched/created files, independent re-execution of every test file cited across all 5 SUMMARYs (all counts matched exactly), live Postgres schema introspection confirming the migration was actually applied with the correct shape, live row counts proving the daily feed-refresh job has genuinely run against the real EPSS/CISA feeds (not just mocks), an isolated `git worktree` comparison against the pre-Phase-31 commit to independently rule out the "mypy new: 3" figure as a real regression (confirmed pre-existing), and a full downstream regression sweep (47 additional tests across dashboard/SLA/sort/facets/filter/group-by-host/router) with zero breakage.

The phase is functionally complete and the goal is achieved: all 6 connectors now correctly attempt to capture, and the write-path correctly persists, real EPSS/KEV/native-priority/source_signals data — the "permanently-null columns" problem this phase existed to fix is structurally resolved. The single residual item is whether 4-5 specific vendor field-name *guesses* (already self-flagged by the executors, backed by a soft-null-safe design) turn out correct against real vendor schemas — this requires live vendor access this session cannot provide, hence `human_needed` rather than `passed`. It does not block proceeding to the next phase; it is an operational follow-up (confirm/adjust field names against live tenants when available) that the existing soft-null design already protects against failing loudly if wrong.

---

_Verified: 2026-08-05T12:25:12Z_
_Verifier: Claude (gsd-verifier)_
