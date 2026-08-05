---
phase: 31-connector-enrichment-rewrite
plan: 05
subsystem: backend/connectors
tags: [wiz, graphql, epss, exploitability, source-signals, python, pytest]

# Dependency graph
requires:
  - phase: 31-01
    provides: "native_priority_score/native_priority_rating/source_signals dataclass fields on NormalizedVulnerability, and the sync.py _lookup_enrichment choke point that makes the CISA KEV reference table (not any connector's own guess) the sole authority for the cisa_kev column"
  - phase: 31-03
    provides: "CrowdStrike (native_priority_rating) + Nessus (native_priority_score) enrichment, and the per-connector source_signals allowlist pattern this plan's cross-6 sweep reuses"
  - phase: 31-04
    provides: "Qualys (native_priority_score via QDS) + Rapid7 (native_priority_score via riskScore) enrichment — the last 2 of 4 composite-signal connectors before this plan's Wiz + sweep"
provides:
  - "Wiz native_priority_score/native_priority_rating explicit None (Pitfall 6: no vendor-authored composite priority signal) -- final connector to land this contract"
  - "Wiz's 5 richer EPSS/exploitability sub-scores (epssSeverity/epssPercentile/epssProbability/exploitabilityScore/impactScore) + raw hasCisaKevExploit (provenance-only) threaded into source_signals via a guarded GraphQL query"
  - "VULNERABILITY_QUERY_ENRICHED + WizGraphQLSchemaError guard: fetch_vulnerabilities() tries the enriched query first and falls back to the unchanged, current/base VULNERABILITY_QUERY on a GraphQL schema error, so an unverified field-name guess degrades gracefully instead of breaking the whole Wiz sync (A4, the phase's hardest-failure risk)"
  - "Cross-6 ENRICH-06 parametrized sweep (test_connector_normalization.py) proving all 6 connectors always explicitly set native_priority_score/native_priority_rating/source_signals -- populated for CrowdStrike (rating)/Nessus/Qualys/Rapid7 (score), explicit None for Defender/Wiz (Pitfall 6) and for the *_rating half on every numeric-only connector"
  - "All 6 connectors (CrowdStrike, Nessus, Defender, Wiz, Qualys, Rapid7) now fully compliant with ENRICH-03/04/06 -- Phase 31's connector-side work is complete"
affects: ["Phase 33 (Risk-Exposure Model Definition) -- consumes these raw native_priority_*/source_signals columns as inputs; this plan captures them faithfully raw, no cross-scale normalization (D-06)", "Phase 31 verification (/gsd-verify-work 31)"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Guarded-query-with-fallback for GraphQL connectors: a dedicated exception subtype (WizGraphQLSchemaError, a RuntimeError) raised specifically when a GraphQL response body carries an `errors` array, caught ONLY around the enriched-query attempt so a schema/field-name error degrades to a known-good base query while other failure modes (rate-limit exhaustion, auth, transport) propagate unchanged -- first guarded-fallback pattern in this codebase's connectors"
    - "Sweep test with maybe-await + uniform monkeypatch signature: a single parametrized test spans 4 pure-sync normalize functions and 2 HTTP/GraphQL-mocked async fetch_vulnerabilities() calls by giving every builder function the same (monkeypatch) signature and resolving the return value through a tiny `_maybe_await()` helper (asyncio.iscoroutine check) -- avoids splitting the cross-connector proof into a sync test + a separate async test"

key-files:
  created: []
  modified:
    - backend/app/connectors/wiz.py
    - backend/tests/test_connectors/test_wiz_connector.py
    - backend/tests/test_connector_normalization.py

key-decisions:
  - "WizGraphQLSchemaError(RuntimeError) is a new, narrowly-scoped exception subclass raised only when _graphql() sees an `errors` key in the response body -- lets fetch_vulnerabilities() catch specifically the schema-error-on-enriched-query case for its A4 guard without accidentally swallowing the pre-existing 'rate-limit retries exhausted' RuntimeError or any httpx transport/auth error, which still propagate unchanged"
  - "VULNERABILITY_QUERY (the current/base field set) is kept byte-for-byte unchanged as a separate constant from the new VULNERABILITY_QUERY_ENRICHED, rather than mutating the original query in place -- guarantees the fallback path is provably identical to pre-Plan-05 behavior, not a second, independently-drifting copy"
  - "hasCisaKevExploit is folded into the SAME _SOURCE_SIGNAL_ALLOWLIST tuple as the 5 new EPSS/exploitability fields (one key-presence-check loop), rather than a separate one-off branch -- matches the established Nessus/Qualys/Defender allowlist-loop idiom exactly and correctly threads through BOTH the enriched and the fallback query paths (hasCisaKevExploit exists in both queries; the 5 new fields only exist in the enriched one, so they're naturally 'missing' on the fallback path -- no special-casing needed)"
  - "The cross-6 sweep (Task 2) asserts a connector-specific expect_score_populated/expect_rating_populated pair rather than a single uniform assertion -- CrowdStrike is the only connector whose genuine native signal is the *_rating half (ExPRT.AI, categorical); Nessus/Qualys/Rapid7's genuine signal is the *_score half (VPR/QDS/RiskScore, all numeric-only, so their *_rating always stays None); Defender/Wiz have neither (Pitfall 6). A single 'is populated' assertion could not express this without being wrong for 5 of 6 connectors"
  - "Rapid7 and Wiz sweep cases build a fully self-contained httpx.MockTransport handler inline in test_connector_normalization.py rather than importing test_rapid7_connector.py's/test_wiz_connector.py's private `_install_mock_transport`/handler helpers -- keeps this test file independent of another test file's internals, matching the project's existing convention of no cross-test-file imports"
  - "ENRICH-03/04/06 now marked [x] Complete in REQUIREMENTS.md -- this was the last of the 4 declaring plans (01, 03, 04, 05); all 6 connectors + the cross-6 sweep are done"

patterns-established:
  - "Guarded-query-with-fallback (WizGraphQLSchemaError): the shape any future GraphQL-connector field addition in this codebase should follow when the target schema can't be verified live -- try the enriched query, catch the dedicated schema-error exception, retry with the last-known-good query, never a bare `except RuntimeError` that could also swallow unrelated failures"

requirements-completed: [ENRICH-03, ENRICH-04, ENRICH-06]

# Metrics
duration: ~23min
completed: 2026-08-05
---

# Phase 31 Plan 05: Wiz Guarded Enrichment + Cross-6 Integrity Sweep Summary

**Wiz's 5 richer EPSS/exploitability sub-scores now land in `source_signals` behind a GraphQL schema-error-guarded query (native priority columns stay explicit `None` — Wiz has no vendor composite), and a new cross-6 parametrized sweep proves all 6 connectors (CrowdStrike, Nessus, Defender, Wiz, Qualys, Rapid7) always explicitly set `native_priority_score`/`native_priority_rating`/`source_signals`, closing out Phase 31's ENRICH-03/04/06 requirements.**

## Performance

- **Duration:** ~23 min
- **Started:** 2026-08-05T11:44:10Z (approx, per STATE.md session marker, immediately following Plan 04's completion)
- **Completed:** 2026-08-05T12:07:00Z (approx)
- **Tasks:** 2 (Task 1: RED → GREEN; Task 2: single test commit, no production code change)
- **Files modified:** 3 (0 created, 3 modified — no new files)

## Accomplishments

- `wiz.py` gained a new `VULNERABILITY_QUERY_ENRICHED` GraphQL query (the existing `VULNERABILITY_QUERY` kept byte-for-byte unchanged as the fallback) adding `epssSeverity`/`epssPercentile`/`epssProbability`/`exploitabilityScore`/`impactScore` after `hasCisaKevExploit`. `fetch_vulnerabilities()` tries the enriched query first; a new `WizGraphQLSchemaError` (raised by `_graphql()` specifically when a GraphQL response carries an `errors` array) triggers a fallback to the unchanged base query — so an unverified field-name guess (A4) degrades gracefully instead of breaking the entire Wiz sync, the phase's hardest-failure risk per 31-RESEARCH.md.
- Wiz's `source_signals` is now built inline per GraphQL node from a `_SOURCE_SIGNAL_ALLOWLIST` of 6 raw keys (`hasCisaKevExploit` + the 5 new sub-scores), each captured only when the key is actually present in the node (never `.get()` with a default) — so a vendor-omitted field (missing) stays distinguishable from a vendor-returned-falsy one (negative), and the KEV-ish provenance is read from the RAW node value, never the already-`bool()`-coerced `cisa_kev` local (Pitfall 2). `native_priority_score`/`native_priority_rating` are explicit `None` for every Wiz finding (Pitfall 6: no vendor-authored composite).
- A new cross-6 parametrized test (`test_all_6_connectors_set_native_priority_and_source_signals` in `test_connector_normalization.py`) exercises a representative fixture through each connector's normalize path (4 pure-sync function calls for CrowdStrike/Nessus/Defender/Qualys, 2 HTTP/GraphQL-MockTransport-driven `fetch_vulnerabilities()` calls for Rapid7/Wiz) and proves all 3 new dataclass fields are always explicitly set attributes — populated for CrowdStrike's rating (ExPRT.AI) and Nessus/Qualys/Rapid7's score (VPR/QDS/RiskScore), explicit `None` for Defender/Wiz and for every numeric-only connector's `*_rating` half — with a no-PII/no-promoted-column-leak assertion applied uniformly across all 6.
- Mutation-verified the sweep has real discriminating power: temporarily inverting the CrowdStrike case's expected populated/None flags made the test fail for the exact expected reason, then reverted — confirming the assertions are not tautological `hasattr` checks alone.
- This completes `native_priority_*`/`source_signals` coverage for all 6 connectors — Phase 31's connector-side ENRICH-03/04/06 work is done.

## Task Commits

Each task was committed atomically:

1. **Task 1: Wiz guarded GraphQL sub-score fields → source_signals, native explicit None (RED)** - `7c0acc4` (test)
2. **Task 1: Wiz guarded GraphQL sub-score fields → source_signals, native explicit None (GREEN)** - `5c04574` (feat)
3. **Task 2: Cross-6 ENRICH-06 normalization sweep** - `fc8aed1` (test)

**Plan metadata:** (this commit, docs: complete plan)

_TDD gate compliance: Task 1 — a `test(...)` commit (`7c0acc4`, verified genuinely failing pre-implementation via direct pytest execution against the pre-change wiz.py: `source_signals` was `None`/not-subscriptable, not the expected dict) precedes a `feat(...)` commit (`5c04574`, verified passing, 7/7). Both gates present in git log — compliant. Task 2 — a single `test(...)` commit (`fc8aed1`); no separate literal RED phase, since Task 2 adds zero production code (all 6 connectors' enrichment logic already lands from Plans 01/03/04 + this plan's Task 1) — mirrors the established route-level `tdd=true` "no separate literal RED phase" precedent already documented in this project (31-01-SUMMARY.md's AIE-03 note, Phase 25-03/26-03)._

## Files Created/Modified

- `backend/app/connectors/wiz.py` - New `WizGraphQLSchemaError` exception; new `VULNERABILITY_QUERY_ENRICHED` query (5 EPSS/exploitability fields added after `hasCisaKevExploit`); new `_SOURCE_SIGNAL_ALLOWLIST` (6 keys); `_graphql()`'s GraphQL-errors branch now raises the new exception type instead of a bare `RuntimeError`; `fetch_vulnerabilities()` tries the enriched query, falls back to the unchanged base query on the new exception, and builds `source_signals` inline per node while setting `native_priority_score`/`native_priority_rating` explicitly `None`.
- `backend/tests/test_connectors/test_wiz_connector.py` - 3 new async tests: enriched-query success maps all 5 new fields + `hasCisaKevExploit` into `source_signals`; a GraphQL schema-error response on the enriched query falls back to the base query and still returns findings; missing-vs-negative + no-PII/no-promoted-key proof (mirrors the other 5 connectors' analogous fixtures from Plans 01/03/04).
- `backend/tests/test_connector_normalization.py` - New imports (`asyncio`, `httpx`, `qualys._normalize_detection`, `wiz.WizConnector`); 6 new per-connector sweep-fixture builder functions (`_build_crowdstrike_findings` … `_build_wiz_findings`, the latter 2 async with self-contained `httpx.MockTransport` handlers) + a `_maybe_await()` helper + one new parametrized test (`test_all_6_connectors_set_native_priority_and_source_signals`, 6 cases) proving ENRICH-06 across all 6 connectors in a single sweep.

## Decisions Made

- `WizGraphQLSchemaError(RuntimeError)` scopes the enriched-query fallback catch to exactly "GraphQL returned an `errors` array" — not a bare `except RuntimeError`, which would also catch the pre-existing "rate-limit retries exhausted" case and could mask a genuine outage as a schema-guess problem.
- `VULNERABILITY_QUERY` (base) is left byte-for-byte unchanged as its own constant; `VULNERABILITY_QUERY_ENRICHED` is additive — the fallback path is therefore provably identical to pre-Plan-05 Wiz behavior, not a second query that could independently drift.
- `hasCisaKevExploit` shares the same allowlist-loop idiom as the 5 new fields (one `if key in node` loop) rather than a special-cased branch — simpler, and it naturally handles "present on both queries" vs. "present only on the enriched one" without extra logic.
- The cross-6 sweep encodes per-connector `expect_score_populated`/`expect_rating_populated` flags rather than one shared assertion, since the "genuine signal" lands in different halves of the pair depending on the connector (CrowdStrike: rating; Nessus/Qualys/Rapid7: score; Defender/Wiz: neither).
- Rapid7/Wiz sweep builders are self-contained (own inline `httpx.MockTransport` handler) rather than importing the sibling test files' private helpers, keeping `test_connector_normalization.py` independent.
- ENRICH-03/ENRICH-04/ENRICH-06 flipped to `[x]` Complete in REQUIREMENTS.md — this plan is the last of the 4 declaring plans (01, 03, 04, 05); all 6 connectors and the cross-6 sweep are now done.

## Deviations from Plan

None - plan executed exactly as written. `WizGraphQLSchemaError` and the exact `_SOURCE_SIGNAL_ALLOWLIST` contents were exercises of the plan's own implementation discretion (the plan specified the guard *behavior* — "wrap in a try/fallback" — and the allowlist *contents* — the 5 new fields + raw `hasCisaKevExploit` provenance — not the literal Python symbol names), not deviations from a specified design.

## Issues Encountered

- Confirmed the mypy-baseline "new: 3" report (`fixed: 15 / new: 3`) is the same pre-existing flake already documented in Plans 01/03/04's summaries — re-verified independently via the project's own `git checkout <pre-plan-commit> -- .` + `rm -rf .mypy_cache` protocol: the identical 3 `app/auth/dependencies.py:10: note:` (`jose`-stub-missing hint) lines reproduce byte-for-byte on the clean, pre-Plan-05 tree. `grep`-confirmed zero new violations mention `wiz.py` or `test_connector_normalization.py`. Not fixed (out of scope — pre-existing, unrelated to any file this plan touches).
- No other issues. The Wiz field names (`epssSeverity`/`epssPercentile`/`epssProbability`/`exploitabilityScore`/`impactScore`) are unverified against a live Wiz GraphQL schema — flagged below per the plan's `<output>` instruction, not silently assumed correct.

## User Setup Required

None — no external service configuration required. Wiz's new fields are read from data the existing GraphQL query already fetches (once the enriched query succeeds); no new credentials, endpoints, or scopes.

## Empirical Re-verification Flags (carried per plan's `<output>` instruction)

- **A4 — Wiz's 5 EPSS/exploitability field names are unverified against a live schema.** 31-RESEARCH.md's Assumptions Log flags `epssSeverity`/`epssPercentile`/`epssProbability`/`exploitabilityScore`/`impactScore` as WebSearch-cited, not directly schema-verified this session. This plan's guard (`WizGraphQLSchemaError` + fallback to the unchanged base query) means a wrong guess degrades gracefully — `source_signals` will simply never carry those 5 keys for any Wiz finding, and the sync keeps working — rather than breaking Wiz ingestion entirely. **Recommend verifying the real field names via a live Wiz GraphQL schema introspection query** (`{ __type(name: "VulnerabilityFinding") { fields { name } } }` against a real Wiz tenant) before relying on these 5 fields being populated in production. If the real names differ, update `VULNERABILITY_QUERY_ENRICHED`'s field list and `_SOURCE_SIGNAL_ALLOWLIST` together (both must stay in sync — this is a one-connector, ~10-line change).
- Wiz's final `source_signals` allowlist: `("hasCisaKevExploit", "epssSeverity", "epssPercentile", "epssProbability", "exploitabilityScore", "impactScore")` — 1 pre-existing field captured as raw provenance + 5 new sub-scores.

## Next Phase Readiness

- All 6 connectors (Defender — Plan 01; CrowdStrike + Nessus — Plan 03; Qualys + Rapid7 — Plan 04; Wiz — this plan) now fully populate `native_priority_score`/`native_priority_rating`/`source_signals` per the established pattern, proven together in one cross-6 parametrized sweep. Phase 31's connector-side work (ENRICH-03/04/06) is complete; ENRICH-01/02/05 were already complete from Plans 01/02.
- No blockers. `test_wiz_connector.py` (7/7), `test_connector_normalization.py` (28/28), and the other 5 connectors' test files (`test_crowdstrike_connector.py` 9/9, `test_nessus_connector.py` 10/10, `test_qualys_connector.py` 12/12, `test_rapid7_connector.py` 12/12, `test_defender_connector.py` 7/7) plus `test_vulnerability_enrichment.py` (2/2, Plan 01's integration tests) all green — full regression-clean. `ruff check`/`ruff format --check` clean on all 3 touched files. mypy-baseline gate shows zero new violations attributable to either touched file (re-verified via checkout-and-diff, see Issues Encountered).
- REQUIREMENTS.md: ENRICH-01/02/03/04/05/06 all now `[x]` Complete — Phase 31 is 5/5 plans complete, ready for `/gsd-verify-work 31`. Per this plan's explicit instruction, STATE.md's `status:` field is left as `executing` (not flipped to complete) — the orchestrator marks the phase complete after verification.
- The one open empirical-verification item (A4, Wiz's 5 field names) is a soft-failure-by-design gap, not a blocker: if wrong, Wiz findings simply keep their pre-Plan-05 behavior (base query, no 5 new `source_signals` keys) rather than breaking ingestion.

---
*Phase: 31-connector-enrichment-rewrite*
*Completed: 2026-08-05*
